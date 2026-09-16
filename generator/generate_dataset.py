"""generate_dataset.py -- ties `dynamosa.py` (the search) and
`materialize.py` (the output) together into the actual "generate a real
dataset for one case study" entry point. Everything up to this point
(fitness/candidate/mutation/crossover/AVM/escalation/materialize/
DynaMOSA) was built and tested piece by piece; this is the first module
that runs the whole thing end to end and produces real files.

**Three honest coverage numbers, not one, because they answer different
questions**:

- **Archive coverage** -- how many objectives reached fitness 0.0 *at
  some point* during the run, possibly on different individuals at
  different generations. This is the search's own progress metric
  (DynaMOSA's own archive discipline), and the number `dynamosa.py`'s
  own self-test already reports.
- **Final-population coverage** -- how many objectives are
  *simultaneously* satisfied by the single best individual found in the
  LAST generation's own population. This was, until 2026-09-13, this
  module's only "final-dataset" strategy; measured directly to sit far
  below archive coverage (17-20/151 vs 81/151 on FLEX2) for a
  structural reason unrelated to any bug: DynaMOSA/NSGA-II deliberately
  SPREADS a population across Pareto-front *specialists*, never
  converges it onto one *generalist* individual (see
  `docs/generationalgorithmdesign.md` §13.42).
- **Merged-archive coverage** (2026-09-13, §13.42's own named follow-up)
  -- how many objectives are simultaneously satisfied by ONE candidate
  built by `dynamosa.py`'s own `merge_archive_candidate`: every covered
  objective's own best-ever rows, merged together rather than hoping one
  generation's population happens to contain a single all-purpose
  winner. This is RE-VERIFIED here by re-`evaluate_objective`-ing every
  objective against the actual merged, repaired result -- never assumed
  correct just because the rows were carried over unchanged, since
  `repair_candidate`'s own FK-stub-synthesis pass, run once on the fully
  merged whole, could in principle still disturb some objective's
  aggregate/exists count (an untagged stub row is globally visible by
  design -- see `_OWNER_KEY`'s own docstring). A finding either way
  (verified intact, or a real regression) is reported honestly, not
  assumed.

The dataset actually materialized is whichever of the final-population
candidate and the merged-archive candidate has the higher VERIFIED
final coverage -- ties broken toward the merged-archive candidate, since
it is the structurally more sound strategy of the two (built from
verified per-objective bests, not a specialist that happened to also
cover a few extra objectives by chance).

Usage:
    from generate_dataset import generate_case_study_dataset
    result = generate_case_study_dataset('FLEX2', out_dir='./generated_flex2')
"""
import json
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from dynamosa import run_dynamosa, evaluate_objective, merge_archive_candidate  # noqa: E402
from materialize import to_sql_inserts, write_csv_files, validate_with_sqlite  # noqa: E402
from mutation import _schema_for  # noqa: E402


def _covered_set(individual, records, table_cache):
    """`individual` is a `(candidate, focal_maps, scenario_maps)` triple
    -- dynamosa.py's own per-individual representation (`scenario_maps`
    added 2026-09-13, its own per-individual scenario fix -- see
    dynamosa.py's own module docstring for the real `not_persisted`
    -mutation bug this replaced; no separate `scenario_cache` is needed
    or accepted anymore, since every individual already carries its own
    current scenario). Returns the SET of covered record_ids (not just a
    count) so a caller can diff two strategies' own coverage, not just
    compare their totals."""
    candidate, focal_maps, scenario_maps = individual
    return {r['record_id'] for r in records
            if evaluate_objective(r, candidate, focal_maps, scenario_maps, table_cache) == 0.0}


def generate_case_study_dataset(case_study, records=None, out_dir=None,
                                 population_size=30, generations=40, rng=None):
    """Runs DynaMOSA over `records` (default: every compiled record for
    `case_study`), builds BOTH final-dataset candidates (final-population
    best individual, and the merged archive -- see this module's own
    docstring), verifies each for real, and materializes + validates
    whichever verified higher. Returns a dict: {'archive',
    'coverage_history', 'archive_covered', 'final_population_covered',
    'merged_archive_expected', 'merged_archive_covered',
    'merged_archive_regressions', 'final_covered', 'final_strategy',
    'candidate', 'sql_statements', 'sql_warnings', 'csv_files',
    'validate_ok', 'validate_errors', 'elapsed_seconds'} -- every number
    in it is computed, never assumed."""
    rng = rng or random.Random(0)
    if records is None:
        compiled = json.load(open(os.path.join(HERE, 'compiled_constraints.json')))
        records = [r for r in compiled if r['case_study'] == case_study]

    start = time.time()
    # No separate scenario_cache to thread through anymore (2026-09-13's
    # own per-individual scenario fix, dynamosa.py's own module docstring):
    # every individual in `population`, and every archived one, already
    # carries its own current `scenario_maps` as the third element of its
    # own `(candidate, focal_maps, scenario_maps)` triple.
    archive, coverage_history, population = run_dynamosa(
        records, case_study, population_size=population_size, generations=generations, rng=rng)
    elapsed = time.time() - start

    table_cache = {}

    archive_covered = sum(1 for r in records if archive[r['record_id']][0] == 0.0)

    # Strategy 1 (the original, 2026-09-12): the final population's own
    # best individual.
    pop_sets = [_covered_set(ind, records, table_cache) for ind in population]
    best_pop_idx = max(range(len(population)), key=lambda i: len(pop_sets[i]))
    final_population_individual = population[best_pop_idx]
    final_population_covered = pop_sets[best_pop_idx]

    # Strategy 2 (2026-09-13): merge every covered objective's own
    # best-ever archived rows into one candidate. `merged_archive_expected`
    # is the archive's own claim (what SHOULD be covered); re-verified
    # immediately below against the actual merged+repaired result, since
    # a merge is exactly the kind of change that must never be trusted
    # just because it looks right on paper (this project's own standing
    # rule -- see e.g. §13.34/§13.41's own found-not-assumed bugs).
    merged_candidate, merged_focal_maps, merged_scenario_maps, merged_archive_expected = merge_archive_candidate(
        archive, records, case_study)
    merged_archive_covered = _covered_set(
        (merged_candidate, merged_focal_maps, merged_scenario_maps), records, table_cache)
    merged_archive_regressions = merged_archive_expected - merged_archive_covered

    # Pick whichever strategy actually verifies higher -- ties toward the
    # merged archive (see this module's own docstring for why).
    if len(merged_archive_covered) >= len(final_population_covered):
        final_strategy = 'merged_archive'
        final_covered_set = merged_archive_covered
        final_candidate = merged_candidate
    else:
        final_strategy = 'final_population'
        final_covered_set = final_population_covered
        # Only the bare Candidate half of the (candidate, focal_maps) pair
        # is relevant from here on -- focal_maps is pure search-time
        # bookkeeping, irrelevant to materialize.py's own SQL/CSV output.
        final_candidate = final_population_individual[0]

    schema = _schema_for(case_study)
    sql_statements, sql_warnings = to_sql_inserts(final_candidate, schema)
    validate_ok, validate_errors = validate_with_sqlite(final_candidate, schema)
    csv_files = write_csv_files(final_candidate, out_dir) if out_dir else []

    return {
        'archive': archive,
        'coverage_history': coverage_history,
        'archive_covered': archive_covered,
        'final_population_covered': len(final_population_covered),
        'merged_archive_expected': len(merged_archive_expected),
        'merged_archive_covered': len(merged_archive_covered),
        'merged_archive_regressions': sorted(merged_archive_regressions),
        'final_covered': len(final_covered_set),
        'final_strategy': final_strategy,
        'total_objectives': len(records),
        'candidate': final_candidate,
        'sql_statements': sql_statements,
        'sql_warnings': sql_warnings,
        'csv_files': csv_files,
        'validate_ok': validate_ok,
        'validate_errors': validate_errors,
        'elapsed_seconds': elapsed,
    }


if __name__ == '__main__':
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument('--case-study', default='FLEX2')
    ap.add_argument('--population-size', type=int, default=30)
    ap.add_argument('--generations', type=int, default=40)
    ap.add_argument('--out-dir', default=os.path.join(HERE, '_generated_flex2'))
    ap.add_argument('--seed', type=int, default=0)
    args = ap.parse_args()

    result = generate_case_study_dataset(
        args.case_study, out_dir=args.out_dir,
        population_size=args.population_size, generations=args.generations,
        rng=random.Random(args.seed))

    print(f"Case study: {args.case_study}  ({result['total_objectives']} compiled branches, "
          f"population={args.population_size}, generations={args.generations})")
    print(f"Elapsed: {result['elapsed_seconds']:.1f}s")
    print(f"Coverage history (archive, per generation): {result['coverage_history']}")
    print()
    total = result['total_objectives']
    print(f"Archive coverage (ever covered, at some point, by SOME individual): "
          f"{result['archive_covered']}/{total} ({result['archive_covered'] / total * 100:.1f}%)")
    print(f"Final-population strategy (best individual in the last generation): "
          f"{result['final_population_covered']}/{total} "
          f"({result['final_population_covered'] / total * 100:.1f}%)")
    print(f"Merged-archive strategy (every covered objective's own best-ever rows, merged): "
          f"expected {result['merged_archive_expected']}/{total}, "
          f"VERIFIED {result['merged_archive_covered']}/{total} "
          f"({result['merged_archive_covered'] / total * 100:.1f}%)")
    if result['merged_archive_regressions']:
        print(f"  WARNING: merging regressed {len(result['merged_archive_regressions'])} objective(s) that "
              f"the archive itself had covered -- the merge+repair pass disturbed them:")
        for rid in result['merged_archive_regressions'][:10]:
            print(f"     {rid}")
    else:
        print(f"  Confirmed: every objective the merge expected to cover, it actually covers -- "
              f"merging archived bests together introduced zero regressions.")
    print()
    print(f"Materializing via the '{result['final_strategy']}' strategy "
          f"({result['final_covered']}/{total} -- the higher of the two, verified).")
    print()
    print(f"Materialized {len(result['sql_statements'])} INSERT statements across "
          f"{len(result['candidate'].as_dict())} tables ({len(result['sql_warnings'])} ordering warnings).")
    print(f"Wrote {len(result['csv_files'])} CSV files to {args.out_dir}")
    print(f"validate_with_sqlite: ok={result['validate_ok']}, {len(result['validate_errors'])} error(s)")
    for e in result['validate_errors'][:10]:
        print("   ", e)

    sql_path = os.path.join(args.out_dir, f"{args.case_study}_generated.sql")
    os.makedirs(args.out_dir, exist_ok=True)
    with open(sql_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(result['sql_statements']) + '\n')
    print(f"Wrote {sql_path}")
