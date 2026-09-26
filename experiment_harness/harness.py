"""experiment_harness/harness.py -- repeated, equal-budget experiments for
the thesis's search-vs-random evaluation (built 2026-09-26).

Compares, per case study, over N independent repetitions:
  dynamosa       run_dynamosa (NSGA-II DynaMOSA)                  1x 5x 10x
  random_walk    random_baseline.run_random_search (mutate only)   1x 5x 10x
  random_sample  random_sampling.run_random_sampling (fresh
                 random individual each attempt, keep best)        1x 5x 10x

Budget = FITNESS EVALUATIONS (one `branch_fitness` call; see fitness.py's
`reset_evaluation_counter`), never generations. B (the 1x budget) is fixed
per case study by `calibrate`: the median number of evaluations the
search uses at the project's established 30 x 40 setting. Every run then
stops at exactly k*B evaluations (or when every objective is covered).

Every run is independently validated: its archive individuals and (for the
two population-based algorithms) its final-population individuals are each
materialized into SQLite and re-checked by the independent validator
(validation_oracle), exactly as per_individual_archive_coverage.py
--mode optimized does -- the same helper functions, imported, not copied.
Coverage is reported for archive only, final only, and final+archive
(the union of the two verified sets -- no third validation pass needed).

Subcommands (run from the repo root with .venv's python):
  calibrate  --name X [--calibration-seeds 3]
  run        --name X [--reps 30] [--workers 4] [--case-studies ...]
             [--setups ...] [--budgets 1 5 10] [--no-validate] [--keep-dbs]
  validate   --name X [--workers 4] [--keep-dbs]   (runs searched with --no-validate)
  summarize  --name X                               (-> summary.csv, runs.csv)
  status     --name X
Everything is resumable: a finished step leaves a marker file and is skipped
next time. Each job runs in its own process (PYTHONHASHSEED=0, seeded rng)
so every run is reproducible from its seed.

Output: experiment_harness/out/<name>/
  calibration.json, config.json, summary.csv, runs.csv
  <CaseStudy>/<setup>/b<k>x/rep_<ii>/
      archive/individuals.pkl   {'archive': {record_id: (fitness, individual)}}
                                (directly usable with per_individual_archive_coverage.py)
      archive/verification.csv  rule_id, verified, first_individual, override_file
      final/individuals.pkl     {'final_population': [...]}   (not for random_sample)
      final/verification.csv
      per_record.csv            one row per compiled record: fitness, claims,
                                verification, input values, rule outputs
      per_rule.csv              one row per rule (what the stats use)
      trace.csv                 evaluations, record_id -- first time each record hit 0
      meta.json, log.txt, SEARCH_DONE, VALIDATED
"""
import argparse
import concurrent.futures
import csv
import datetime
import hashlib
import json
import os
import pickle
import random
import shutil
import sqlite3
import statistics
import subprocess
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GENERATOR_DIR = os.path.join(ROOT, 'generator')
ORACLE_DIR = os.path.join(ROOT, 'validation_oracle')
ORACLE_TESTS_DIR = os.path.join(ORACLE_DIR, 'tests')
for _p in (ORACLE_TESTS_DIR, ORACLE_DIR, GENERATOR_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

COMPILED_PATH = os.path.join(GENERATOR_DIR, 'compiled_constraints.json')
OUT_ROOT = os.path.join(HERE, 'out')

CASE_STUDIES = ('FLEX2', 'OpenMRS', 'Spree', 'jBilling')
SETUPS = ('dynamosa', 'random_walk', 'random_sample')
BUDGETS = (1, 5, 10)
POPULATION_SIZE = 30          # this project's established convention (run_experiments.py)
CALIBRATION_GENERATIONS = 40  # likewise
POPULATION_SETUPS = ('dynamosa', 'random_walk')

# Disclosed not_persisted overrides the validator uses per case study -- the
# same files the per-case-study validation commands have always used. More
# than one file = coverage is the UNION over them (jBilling: candidateDate
# provided / not provided are mutually exclusive scenarios).
NOT_PERSISTED_FILES = {
    'FLEX2': ['flex2_not_persisted.json'],
    'OpenMRS': ['openmrs_not_persisted.json'],
    'Spree': ['spree_not_persisted.json'],
    'jBilling': ['jbilling_not_persisted.json', 'jbilling_not_persisted_rule1.json'],
}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _load_records(case_study):
    with open(COMPILED_PATH, encoding='utf-8') as f:
        return [r for r in json.load(f) if r['case_study'] == case_study]


def _sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def _git_commit():
    try:
        out = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True)
        dirty = subprocess.run(['git', 'status', '--porcelain', '--untracked-files=no'], cwd=ROOT,
                               capture_output=True, text=True).stdout.strip()
        return out.stdout.strip() + (' (uncommitted changes present)' if dirty else '')
    except OSError:
        return 'unknown'


def _exp_dir(name):
    return os.path.join(OUT_ROOT, name)


def _run_dir(name, cs, setup, k, rep):
    return os.path.join(_exp_dir(name), cs, setup, f'b{k}x', f'rep_{rep:02d}')


def _seed_for(k, rep):
    # Distinct seed per (budget, rep): a 5x run is an independent run, not
    # the 1x run's own continuation (with one shared seed the first B
    # evaluations of both would be identical, breaking independence).
    return 1000 * k + rep


def _scope(case_study, records):
    from summarize_coverage import _mechanical_out_of_scope
    by_rule = {}
    for r in records:
        by_rule.setdefault(r['rule_id'], []).append(r)
    out_of_scope = _mechanical_out_of_scope(case_study, by_rule)
    return by_rule, out_of_scope


def _jsonable(v):
    return json.dumps(v, default=str, sort_keys=True)


def _write_csv(path, fieldnames, rows):
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def _read_csv(path):
    with open(path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------------------
# one search run (executed inside its own subprocess)
# ---------------------------------------------------------------------------

def _run_algorithm(setup, records, case_study, budget, seed, trace):
    import dynamosa
    import random_baseline
    import random_sampling
    random.seed(seed)  # a few move generators use the global `random` module
    rng = random.Random(seed)
    if setup == 'dynamosa':
        return dynamosa.run_dynamosa(records, case_study, population_size=POPULATION_SIZE,
                                     generations=None, rng=rng, max_evaluations=budget, trace=trace)
    if setup == 'random_walk':
        return random_baseline.run_random_search(records, case_study, population_size=POPULATION_SIZE,
                                                 generations=None, rng=rng, max_evaluations=budget,
                                                 trace=trace)
    if setup == 'random_sample':
        return random_sampling.run_random_sampling(records, case_study, max_evaluations=budget,
                                                   rng=rng, trace=trace)
    raise ValueError(setup)


def _record_claims(records, archive, population):
    """Per record: archive fitness, best final-population fitness, and the
    input values (genome) of the archived individual. Computed AFTER the
    budget is closed (these evaluations are bookkeeping, not search)."""
    from candidate import derive_genome
    from dynamosa import evaluate_objective, _focal_for_read
    from fitness import FitnessEvaluationError
    table_cache = {}
    out = {}
    for r in records:
        rid = r['record_id']
        fit, ind = archive[rid]
        cand, fm, sm = ind
        try:
            genome = derive_genome(r, cand, _focal_for_read(r, fm), sm.get(rid, {}), owner_id=rid)
            genome = {k: v for k, v in genome.items()}
        except FitnessEvaluationError as e:
            genome = {'__not_evaluable__': str(e)[:200]}
        final_best = min((evaluate_objective(r, c, f, s, table_cache) for c, f, s in population),
                         default=None)
        out[rid] = {'archive_fitness': fit, 'final_best_fitness': final_best, 'inputs': genome}
    return out


def job_search(run_dir, case_study, setup, k, rep, seed, budget):
    from fitness import evaluations_used
    records = _load_records(case_study)
    os.makedirs(os.path.join(run_dir, 'archive'), exist_ok=True)
    trace = []
    t0 = time.time()
    archive, history, population = _run_algorithm(setup, records, case_study, budget, seed, trace)
    runtime = time.time() - t0
    evals = evaluations_used()

    with open(os.path.join(run_dir, 'archive', 'individuals.pkl'), 'wb') as f:
        pickle.dump({'archive': archive}, f)
    if setup in POPULATION_SETUPS:
        os.makedirs(os.path.join(run_dir, 'final'), exist_ok=True)
        with open(os.path.join(run_dir, 'final', 'individuals.pkl'), 'wb') as f:
            pickle.dump({'final_population': population}, f)

    claims = _record_claims(records, archive, population)
    with open(os.path.join(run_dir, 'claims.json'), 'w', encoding='utf-8') as f:
        json.dump(claims, f, default=str)
    _write_csv(os.path.join(run_dir, 'trace.csv'), ['evaluations', 'record_id'],
               [{'evaluations': e, 'record_id': rid} for e, rid in trace])

    meta = {
        'case_study': case_study, 'setup': setup, 'budget_multiplier': k, 'rep': rep, 'seed': seed,
        'budget_evaluations': budget, 'evaluations_used': evals,
        'stopped_because': 'budget' if evals >= budget else 'all_objectives_covered',
        'iterations': len(history),  # generations (population setups) / samples incl. seed (random_sample)
        'population_size': POPULATION_SIZE if setup in POPULATION_SETUPS else None,
        'runtime_seconds': round(runtime, 2),
        'claimed_records_archive': sum(1 for c in claims.values() if c['archive_fitness'] == 0.0),
        'finished_at': datetime.datetime.now().isoformat(timespec='seconds'),
    }
    with open(os.path.join(run_dir, 'meta.json'), 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=2)
    open(os.path.join(run_dir, 'SEARCH_DONE'), 'w').close()
    print(f"search done: {evals}/{budget} evaluations, {meta['iterations']} iterations, "
          f"{meta['claimed_records_archive']}/{len(records)} records claimed, {runtime:.1f}s")


# ---------------------------------------------------------------------------
# validation of one run (executed inside its own subprocess)
# ---------------------------------------------------------------------------

def _distinct(individuals):
    seen, out = set(), []
    for ind in individuals:
        if id(ind) not in seen:
            seen.add(id(ind))
            out.append(ind)
    return out


def _verify_set(case_study, individuals, dbs_dir, label):
    """per_individual_archive_coverage.run_optimized's own loop, over an
    arbitrary list of individuals and every disclosed not_persisted
    override file for this case study: the materialization pipeline and
    `_verify_decision_subset` are imported from that module, not
    re-derived, so this can never diverge from what the user's own
    validation command reports. Returns {rule_id: (individual_index,
    override_file)} for every verified rule."""
    import per_individual_archive_coverage as pia
    from mutation import _schema_for, repair_candidate
    from phase1_utility import records_by_decision

    schema = _schema_for(case_study)
    records = _load_records(case_study)
    records_index = {r['record_id']: i for i, r in enumerate(records)}
    records_by_id = {r['record_id']: r for r in records}
    decisions_by_name = records_by_decision(case_study)
    rule_ids_by_decision = {d: {r['rule_id'] for r in recs} for d, recs in decisions_by_name.items()}
    remaining = {r['rule_id'] for r in records}
    verified = {}
    errors = []
    os.makedirs(dbs_dir, exist_ok=True)

    db_paths = {}
    for override_file in NOT_PERSISTED_FILES[case_study]:
        with open(os.path.join(ORACLE_TESTS_DIR, override_file), encoding='utf-8') as f:
            overrides = json.load(f)
        for idx, individual in enumerate(individuals):
            if not remaining:
                break
            decisions_to_check = {d for d, rids in rule_ids_by_decision.items() if rids & remaining}
            try:
                db_path = db_paths.get(idx)
                if db_path is None:
                    work_c, work_fm, work_sm = pia._deep_copy_individual(individual)
                    pia._offset_rows_by_owner(work_c, schema, records_index, case_study)
                    pia._apply_cross_table_placeholder_correlations_for_individual(
                        work_c, work_fm, work_sm, records_by_id, records_index, schema)
                    pia._build_decision_subject_rows_for_individual(work_c, work_fm, records_by_id, schema)
                    repair_candidate(work_c, case_study)
                    db_path = os.path.join(dbs_dir, f'{label}_{idx:03d}.db')
                    pia._materialize(work_c, case_study, db_path)
                    db_paths[idx] = db_path
                conn = sqlite3.connect(db_path)
                try:
                    result = pia._verify_decision_subset(conn, case_study, decisions_by_name,
                                                         decisions_to_check, overrides)
                finally:
                    conn.close()
            except Exception as e:  # noqa: BLE001 -- one bad individual must not abort the run
                errors.append(f'{label} individual {idx} ({override_file}): {type(e).__name__}: {e}')
                traceback.print_exc()
                continue
            for rule_id, ok in result.items():
                if ok and rule_id in remaining:
                    remaining.discard(rule_id)
                    verified[rule_id] = (idx, override_file)
    return verified, errors


def job_validate(run_dir, case_study, keep_dbs):
    records = _load_records(case_study)
    by_rule, out_of_scope = _scope(case_study, records)
    with open(os.path.join(run_dir, 'meta.json'), encoding='utf-8') as f:
        meta = json.load(f)
    with open(os.path.join(run_dir, 'claims.json'), encoding='utf-8') as f:
        claims = json.load(f)
    dbs_dir = os.path.join(run_dir, 'dbs')
    t0 = time.time()

    with open(os.path.join(run_dir, 'archive', 'individuals.pkl'), 'rb') as f:
        archive = pickle.load(f)['archive']
    archive_inds = _distinct(ind for _fit, ind in archive.values())
    v_archive, errs = _verify_set(case_study, archive_inds, dbs_dir, 'archive')
    _write_csv(os.path.join(run_dir, 'archive', 'verification.csv'),
               ['rule_id', 'verified', 'first_individual', 'override_file'],
               [{'rule_id': rid, 'verified': rid in v_archive,
                 'first_individual': v_archive.get(rid, ('', ''))[0],
                 'override_file': v_archive.get(rid, ('', ''))[1]} for rid in sorted(by_rule)])

    has_final = os.path.exists(os.path.join(run_dir, 'final', 'individuals.pkl'))
    v_final = {}
    final_count = 0
    if has_final:
        with open(os.path.join(run_dir, 'final', 'individuals.pkl'), 'rb') as f:
            population = pickle.load(f)['final_population']
        final_inds = _distinct(population)
        final_count = len(final_inds)
        v_final, errs_f = _verify_set(case_study, final_inds, dbs_dir, 'final')
        errs += errs_f
        _write_csv(os.path.join(run_dir, 'final', 'verification.csv'),
                   ['rule_id', 'verified', 'first_individual', 'override_file'],
                   [{'rule_id': rid, 'verified': rid in v_final,
                     'first_individual': v_final.get(rid, ('', ''))[0],
                     'override_file': v_final.get(rid, ('', ''))[1]} for rid in sorted(by_rule)])
    if not keep_dbs:
        shutil.rmtree(dbs_dir, ignore_errors=True)

    first_hit = {}
    for row in _read_csv(os.path.join(run_dir, 'trace.csv')):
        first_hit.setdefault(row['record_id'], int(row['evaluations']))

    def yn(b):
        return 'True' if b else 'False'

    per_record = []
    for r in records:
        rid, rule = r['record_id'], r['rule_id']
        c = claims[rid]
        fin = c['final_best_fitness']
        per_record.append({
            'record_id': rid, 'decision': r['decision_name'], 'rule_id': rule,
            'hit_policy': r['hit_policy'], 'in_scope': yn(rule not in out_of_scope),
            'archive_fitness': c['archive_fitness'],
            'final_best_fitness': '' if fin is None else fin,
            'first_covered_at_evaluation': first_hit.get(rid, ''),
            'claimed_archive': yn(c['archive_fitness'] == 0.0),
            'claimed_final': '' if not has_final else yn(fin == 0.0),
            'rule_verified_archive': yn(rule in v_archive),
            'rule_verified_final': '' if not has_final else yn(rule in v_final),
            'rule_verified_union': yn(rule in v_archive or rule in v_final),
            'inputs': _jsonable(c['inputs']),
            'outputs': _jsonable({k: v.get('value', v) if isinstance(v, dict) else v
                                  for k, v in (r.get('outputs') or {}).items()}),
        })
    _write_csv(os.path.join(run_dir, 'per_record.csv'), list(per_record[0]), per_record)

    per_rule = []
    for rule, recs in sorted(by_rule.items()):
        rows = [p for p in per_record if p['rule_id'] == rule]
        ca = any(p['claimed_archive'] == 'True' for p in rows)
        cf = has_final and any(p['claimed_final'] == 'True' for p in rows)
        per_rule.append({
            'rule_id': rule, 'decision': recs[0]['decision_name'], 'in_scope': yn(rule not in out_of_scope),
            'num_records': len(recs),
            'claimed_archive': yn(ca), 'claimed_final': '' if not has_final else yn(cf),
            'claimed_union': yn(ca or cf),
            'verified_archive': yn(rule in v_archive),
            'verified_final': '' if not has_final else yn(rule in v_final),
            'verified_union': yn(rule in v_archive or rule in v_final),
        })
    _write_csv(os.path.join(run_dir, 'per_rule.csv'), list(per_rule[0]), per_rule)

    meta.update({
        'archive_individuals_validated': len(archive_inds),
        'final_individuals_validated': final_count if has_final else None,
        'validation_errors': errs, 'validation_seconds': round(time.time() - t0, 1),
    })
    with open(os.path.join(run_dir, 'meta.json'), 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=2)
    open(os.path.join(run_dir, 'VALIDATED'), 'w').close()
    in_scope = [p for p in per_rule if p['in_scope'] == 'True']
    print(f"validated: archive {sum(p['verified_archive'] == 'True' for p in in_scope)}, "
          f"final {sum(p['verified_final'] == 'True' for p in in_scope) if has_final else '-'}, "
          f"union {sum(p['verified_union'] == 'True' for p in in_scope)} of {len(in_scope)} in-scope rules "
          f"({len(errs)} errors, {time.time() - t0:.1f}s)")


# ---------------------------------------------------------------------------
# orchestration
# ---------------------------------------------------------------------------

def _spawn(args, log_path):
    env = dict(os.environ, PYTHONHASHSEED='0', PYTHONIOENCODING='utf-8')
    with open(log_path, 'a', encoding='utf-8') as log:
        log.write(f"\n=== {datetime.datetime.now().isoformat(timespec='seconds')} {' '.join(args)}\n")
        log.flush()
        proc = subprocess.run([sys.executable, os.path.abspath(__file__)] + args,
                              stdout=log, stderr=subprocess.STDOUT, env=env, cwd=ROOT)
    return proc.returncode


def _load_calibration(name):
    path = os.path.join(_exp_dir(name), 'calibration.json')
    if not os.path.exists(path):
        sys.exit(f"No calibration for '{name}' -- run: harness.py calibrate --name {name}")
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def cmd_calibrate(a):
    exp = _exp_dir(a.name)
    os.makedirs(exp, exist_ok=True)
    import dynamosa
    from fitness import reset_evaluation_counter, evaluations_used
    path = os.path.join(exp, 'calibration.json')
    calib = json.load(open(path, encoding='utf-8')) if os.path.exists(path) else {}
    if os.environ.get('PYTHONHASHSEED') != '0':
        # re-exec so calibration is exactly as reproducible as every run
        env = dict(os.environ, PYTHONHASHSEED='0')
        sys.exit(subprocess.run([sys.executable] + sys.argv, env=env).returncode)
    for cs in a.case_studies:
        if cs in calib and not a.force:
            print(f"{cs}: already calibrated (B={calib[cs]['budget_1x']}); --force to redo")
            continue
        records = _load_records(cs)
        per_seed = []
        for seed in range(a.calibration_seeds):
            random.seed(seed)
            reset_evaluation_counter(None)
            t0 = time.time()
            archive, _h, _p = dynamosa.run_dynamosa(records, cs, population_size=POPULATION_SIZE,
                                                    generations=CALIBRATION_GENERATIONS,
                                                    rng=random.Random(seed))
            used = evaluations_used()
            covered = sum(1 for r in records if archive[r['record_id']][0] == 0.0)
            per_seed.append({'seed': seed, 'evaluations': used, 'runtime_seconds': round(time.time() - t0, 1),
                             'claimed_records': covered})
            print(f"{cs} calibration seed {seed}: {used} evaluations, {covered}/{len(records)} "
                  f"records claimed, {time.time() - t0:.1f}s", flush=True)
        budget = int(statistics.median(p['evaluations'] for p in per_seed))
        calib[cs] = {'budget_1x': budget, 'population_size': POPULATION_SIZE,
                     'generations': CALIBRATION_GENERATIONS, 'seeds': per_seed,
                     'median_runtime_seconds': statistics.median(p['runtime_seconds'] for p in per_seed),
                     'compiled_constraints_sha256': _sha256(COMPILED_PATH),
                     'git_commit': _git_commit(),
                     'calibrated_at': datetime.datetime.now().isoformat(timespec='seconds')}
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(calib, f, indent=2)
        print(f"{cs}: B = {budget} fitness evaluations (median of {len(per_seed)} seeds)")
    print(f"\nWrote {path}")


def _jobs(a, calib):
    jobs = []
    for rep in range(a.reps):
        for cs in a.case_studies:
            for setup in a.setups:
                for k in a.budgets:
                    jobs.append((cs, setup, k, rep, _seed_for(k, rep), k * calib[cs]['budget_1x']))
    return jobs


def _write_config(a, calib):
    path = os.path.join(_exp_dir(a.name), 'config.json')
    config = {'reps': a.reps, 'case_studies': a.case_studies, 'setups': a.setups, 'budgets': a.budgets,
              'population_size': POPULATION_SIZE, 'seed_rule': 'seed = 1000 * budget_multiplier + rep',
              'budget_1x': {cs: calib[cs]['budget_1x'] for cs in a.case_studies},
              'not_persisted_files': {cs: NOT_PERSISTED_FILES[cs] for cs in a.case_studies},
              'compiled_constraints_sha256': _sha256(COMPILED_PATH), 'git_commit': _git_commit(),
              'written_at': datetime.datetime.now().isoformat(timespec='seconds')}
    for cs in a.case_studies:
        if calib[cs].get('compiled_constraints_sha256') != config['compiled_constraints_sha256']:
            print(f"WARNING: compiled_constraints.json changed since {cs} was calibrated -- "
                  f"consider `calibrate --force` before relying on B.")
    history = []
    if os.path.exists(path):
        with open(path, encoding='utf-8') as f:
            old = json.load(f)
        history = old.pop('history', []) + [old]
        if old.get('compiled_constraints_sha256') != config['compiled_constraints_sha256']:
            print("WARNING: compiled_constraints.json differs from the last `run` of this experiment -- "
                  "new runs will not be comparable with the ones already on disk.")
    config['history'] = history
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2)


def _execute(jobs, workers, fn, label):
    total = len(jobs)
    done = [0]
    t0 = time.time()

    def wrapped(job):
        rc = fn(job)
        done[0] += 1
        elapsed = time.time() - t0
        print(f"[{done[0]}/{total}] {label(job)} -> {'ok' if rc == 0 else f'FAILED (exit {rc}), see log.txt'} "
              f"({elapsed / 60:.1f} min elapsed)", flush=True)
        return rc

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        rcs = list(pool.map(wrapped, jobs))
    failed = sum(1 for rc in rcs if rc != 0)
    print(f"\n{total - failed}/{total} succeeded" + (f", {failed} FAILED (see each run's log.txt)" if failed else ''))


def cmd_run(a):
    calib = _load_calibration(a.name)
    missing = [cs for cs in a.case_studies if cs not in calib]
    if missing:
        sys.exit(f"Not calibrated: {missing} -- run calibrate first")
    _write_config(a, calib)
    todo = []
    for job in _jobs(a, calib):
        cs, setup, k, rep, seed, budget = job
        d = _run_dir(a.name, cs, setup, k, rep)
        need_search = not os.path.exists(os.path.join(d, 'SEARCH_DONE'))
        need_val = not a.no_validate and not os.path.exists(os.path.join(d, 'VALIDATED'))
        if need_search or need_val:
            todo.append((job, d, need_search, need_val))
    print(f"{len(todo)} run(s) to do ({len(_jobs(a, calib)) - len(todo)} already finished), "
          f"{a.workers} worker(s)\n")

    def fn(item):
        (cs, setup, k, rep, seed, budget), d, need_search, need_val = item
        os.makedirs(d, exist_ok=True)
        log = os.path.join(d, 'log.txt')
        if need_search:
            for marker in ('VALIDATED',):
                if os.path.exists(os.path.join(d, marker)):
                    os.remove(os.path.join(d, marker))
            rc = _spawn(['_search', d, cs, setup, str(k), str(rep), str(seed), str(budget)], log)
            if rc != 0:
                return rc
        if need_val:
            return _spawn(['_validate', d, cs] + (['--keep-dbs'] if a.keep_dbs else []), log)
        return 0

    _execute(todo, a.workers, fn, lambda item: f"{item[0][0]} {item[0][1]} b{item[0][2]}x rep_{item[0][3]:02d}")


def _all_run_dirs(name):
    exp = _exp_dir(name)
    for cs in sorted(os.listdir(exp)) if os.path.isdir(exp) else []:
        for setup in SETUPS:
            base = os.path.join(exp, cs, setup)
            if not os.path.isdir(base):
                continue
            for bdir in sorted(os.listdir(base)):
                for rdir in sorted(os.listdir(os.path.join(base, bdir))):
                    yield cs, setup, int(bdir[1:-1]), int(rdir[4:]), os.path.join(base, bdir, rdir)


def cmd_validate(a):
    todo = [(cs, d) for cs, _s, _k, _r, d in _all_run_dirs(a.name)
            if os.path.exists(os.path.join(d, 'SEARCH_DONE'))
            and (a.force or not os.path.exists(os.path.join(d, 'VALIDATED')))]
    print(f"{len(todo)} run(s) to validate, {a.workers} worker(s)\n")
    _execute(todo, a.workers,
             lambda item: _spawn(['_validate', item[1], item[0]] + (['--keep-dbs'] if a.keep_dbs else []),
                                 os.path.join(item[1], 'log.txt')),
             lambda item: os.path.relpath(item[1], _exp_dir(a.name)))


def _auc(events, in_scope_rules, rule_of, horizon):
    """Normalized area under the claimed-coverage curve (in-scope rules,
    archive) over [0, horizon] evaluations, in [0, 1]."""
    if not in_scope_rules or horizon <= 0:
        return 0.0
    seen, points = set(), []
    for ev, rid in events:
        rule = rule_of.get(rid)
        if rule in in_scope_rules and rule not in seen:
            seen.add(rule)
            points.append((ev, len(seen)))
    area, prev_x, prev_y = 0.0, 0, 0
    for x, y in points:
        x = min(x, horizon)
        area += (x - prev_x) * prev_y
        prev_x, prev_y = x, y
    area += (horizon - prev_x) * prev_y
    return area / (horizon * len(in_scope_rules))


def cmd_summarize(a):
    exp = _exp_dir(a.name)
    calib = _load_calibration(a.name)
    runs, long_rows = [], []
    records_cache = {}
    for cs, setup, k, rep, d in _all_run_dirs(a.name):
        if not os.path.exists(os.path.join(d, 'SEARCH_DONE')):
            continue
        with open(os.path.join(d, 'meta.json'), encoding='utf-8') as f:
            meta = json.load(f)
        if cs not in records_cache:
            recs = _load_records(cs)
            _by_rule, oos = _scope(cs, recs)
            records_cache[cs] = ({r['record_id']: r['rule_id'] for r in recs},
                                 {r['rule_id'] for r in recs} - oos, len({r['rule_id'] for r in recs}))
        rule_of, in_scope_rules, total_rules = records_cache[cs]
        events = [(int(r['evaluations']), r['record_id']) for r in _read_csv(os.path.join(d, 'trace.csv'))]
        auc_own = _auc(events, in_scope_rules, rule_of, meta['budget_evaluations'])
        auc_1x = _auc(events, in_scope_rules, rule_of, calib[cs]['budget_1x'])
        validated = os.path.exists(os.path.join(d, 'VALIDATED'))
        counts = {}
        if validated:
            per_rule = [p for p in _read_csv(os.path.join(d, 'per_rule.csv')) if p['in_scope'] == 'True']
            for v in ('archive', 'final', 'union'):
                if per_rule and per_rule[0][f'verified_{v}'] == '':
                    continue
                counts[v] = (sum(p[f'claimed_{v}'] == 'True' for p in per_rule),
                             sum(p[f'verified_{v}'] == 'True' for p in per_rule))
        base = {'case_study': cs, 'setup': setup, 'budget_multiplier': k, 'rep': rep, 'seed': meta['seed'],
                'budget_evaluations': meta['budget_evaluations'], 'evaluations_used': meta['evaluations_used'],
                'iterations': meta['iterations'], 'runtime_seconds': meta['runtime_seconds'],
                'total_rules': total_rules, 'in_scope_rules': len(in_scope_rules),
                'auc_claimed_own_budget': round(auc_own, 6), 'auc_claimed_first_1x': round(auc_1x, 6)}
        run_row = dict(base, validated=validated)
        for v in ('archive', 'final', 'union'):
            c = counts.get(v)
            run_row[f'claimed_{v}'] = '' if c is None else c[0]
            run_row[f'verified_{v}'] = '' if c is None else c[1]
            if c is not None:
                long_rows.append(dict(base, variant=v, claimed=c[0], verified=c[1],
                                      verified_pct_in_scope=round(100 * c[1] / len(in_scope_rules), 3)
                                      if in_scope_rules else 0.0))
        runs.append(run_row)
    if not runs:
        sys.exit('Nothing finished yet.')
    _write_csv(os.path.join(exp, 'runs.csv'), list(runs[0]), runs)
    if long_rows:
        _write_csv(os.path.join(exp, 'summary.csv'), list(long_rows[0]), long_rows)
    print(f"Wrote {os.path.join(exp, 'runs.csv')} ({len(runs)} runs)")
    print(f"Wrote {os.path.join(exp, 'summary.csv')} ({len(long_rows)} rows: one per run x output variant)")

    groups = {}
    for r in long_rows:
        groups.setdefault((r['case_study'], r['setup'], r['budget_multiplier'], r['variant']), []).append(r['verified'])
    print(f"\n{'Case study':<10} {'Setup':<14} {'Budget':>6} {'Output':<8} {'n':>3} {'mean':>7} {'median':>7} "
          f"{'min':>4} {'max':>4}   (verified in-scope rules)")
    for (cs, setup, k, v), vals in sorted(groups.items()):
        print(f"{cs:<10} {setup:<14} {str(k) + 'x':>6} {v:<8} {len(vals):>3} {statistics.mean(vals):>7.2f} "
              f"{statistics.median(vals):>7.1f} {min(vals):>4} {max(vals):>4}")


def cmd_status(a):
    calib = _load_calibration(a.name)
    cfg_path = os.path.join(_exp_dir(a.name), 'config.json')
    if os.path.exists(cfg_path):
        with open(cfg_path, encoding='utf-8') as f:
            cfg = json.load(f)
        print(f"reps={cfg['reps']} setups={cfg['setups']} budgets={cfg['budgets']} B={cfg['budget_1x']}")
    counts = {}
    for cs, setup, k, _rep, d in _all_run_dirs(a.name):
        c = counts.setdefault((cs, setup, k), [0, 0, 0])
        c[0] += 1
        c[1] += os.path.exists(os.path.join(d, 'SEARCH_DONE'))
        c[2] += os.path.exists(os.path.join(d, 'VALIDATED'))
    print(f"{'Case study':<10} {'Setup':<14} {'Budget':>6} {'started':>8} {'searched':>9} {'validated':>10}")
    for (cs, setup, k), (s, sd, v) in sorted(counts.items()):
        print(f"{cs:<10} {setup:<14} {str(k) + 'x':>6} {s:>8} {sd:>9} {v:>10}")
    for cs, c in calib.items():
        print(f"calibration {cs}: B={c['budget_1x']} (search 1x ~{c['median_runtime_seconds']}s per run)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)

    def common(p, runs=False):
        p.add_argument('--name', required=True, help='experiment name (folder under experiment_harness/out/)')
        p.add_argument('--case-studies', nargs='+', default=list(CASE_STUDIES), choices=CASE_STUDIES)
        if runs:
            p.add_argument('--workers', type=int, default=4, help='parallel processes (default 4)')
            p.add_argument('--keep-dbs', action='store_true',
                           help='keep every validated individual\'s SQLite DB (large); default: delete after validating')

    p = sub.add_parser('calibrate')
    common(p)
    p.add_argument('--calibration-seeds', type=int, default=3)
    p.add_argument('--force', action='store_true')
    p.set_defaults(fn=cmd_calibrate)

    p = sub.add_parser('run')
    common(p, runs=True)
    p.add_argument('--reps', type=int, default=30)
    p.add_argument('--setups', nargs='+', default=list(SETUPS), choices=SETUPS)
    p.add_argument('--budgets', nargs='+', type=int, default=list(BUDGETS))
    p.add_argument('--no-validate', action='store_true', help='search only; validate later with `validate`')
    p.set_defaults(fn=cmd_run)

    p = sub.add_parser('validate')
    common(p, runs=True)
    p.add_argument('--force', action='store_true', help='re-validate runs already validated')
    p.set_defaults(fn=cmd_validate)

    p = sub.add_parser('summarize')
    common(p)
    p.set_defaults(fn=cmd_summarize)

    p = sub.add_parser('status')
    common(p)
    p.set_defaults(fn=cmd_status)

    a = ap.parse_args()
    a.fn(a)


if __name__ == '__main__':
    # internal single-job entry points (one process per job)
    if len(sys.argv) > 1 and sys.argv[1] == '_search':
        d, cs, setup, k, rep, seed, budget = sys.argv[2:9]
        job_search(d, cs, setup, int(k), int(rep), int(seed), int(budget))
    elif len(sys.argv) > 1 and sys.argv[1] == '_validate':
        job_validate(sys.argv[2], sys.argv[3], '--keep-dbs' in sys.argv)
    else:
        main()
