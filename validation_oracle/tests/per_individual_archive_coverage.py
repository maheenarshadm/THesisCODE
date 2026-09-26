"""FIXTURE-BUILDING + VALIDATION TOOL, not part of either generator/ or
validation_oracle/ proper -- mirrors build_fixture_from_generator.py's
own bridging role (the one place besides that file allowed to import
BOTH generator/ code, for materializing a candidate, AND
validation_oracle/coverage.py, for verifying one).

Built at the user's own explicit request, 2026-09-25, as a deliberate
ALTERNATIVE to dynamosa.py's own merge_archive_candidate/
merge_archive_candidate_full: instead of MERGING multiple search
individuals into one shared database, this keeps every individual
completely SEPARATE -- one standalone SQLite database per DISTINCT
individual held in a saved archive pickle, each one independently
verified against the WHOLE compiled corpus for its case study (every
rule, not just the objective it happened to be archived for) -- to see
whether one individual, on its own, happens to satisfy more than one
rule at once.

ARCHIVE individuals only, for now -- the final-generation population
(`top['final_population']`) is a deliberately separate, not-yet-built
follow-up (see the conversation this was built from: the archive and
the final population are confirmed-different, only partially-
overlapping sets, per dynamosa.py's own strict-improvement archive
update rule).

Deduplicates by individual IDENTITY first: multiple record_ids in the
archive can share the exact literal same best-ever individual (dynamosa.py's
own merge_archive_candidate docstring notes this explicitly -- "a single
crossover child happened to be the best-ever answer for BOTH at once").
Without deduplication, that one individual would get materialized and
verified as several "different" databases for no reason, and its own
coverage count would be split across duplicate rows rather than
attributed once.

Each individual is repaired (mutation.py's own repair_candidate, on a
fresh deep copy -- NEVER mutating the archived individual in place,
since it may still be referenced by other record_ids in the same
archive dict) before materializing, exactly like merge_archive_candidate
already does before handing its own result to a caller -- a standalone
individual has never been asked to stand alone as an entire database
before, so this is not assumed safe, it's verified the same way
everything else in this project's history has been: build it, then
actually run the independent validator against it and read the real
result.

Writes, per individual: its own database (`dbs/individual_NNN.db`) and
its own full coverage.py run output (`runs/individual_NNN/`). Writes,
once at the end, two aggregated files at the top of --out-dir:
  - per_individual_coverage_long.csv   -- one row per (individual, rule):
    individual_index, origin_record_ids, rule_id, decision_name, verified
  - per_individual_coverage_summary.csv -- one row per individual, sorted
    by how many DISTINCT rules it verified (descending): individual_index,
    origin_record_ids, num_origin_objectives, num_rules_verified,
    verified_rule_ids

A per-individual failure (repair/materialize/coverage-run raising) is
caught, logged, and does NOT abort the batch -- honestly reported in the
summary as verified=0 rows with the error message, matching this
project's own "one failure shouldn't abort everything" discipline
(coverage.py's own build_subject_tables docstring states the same
principle for one decision's own resolution failure).

TWO modes, both always available (--mode full / --mode optimized, `run`/
`run_optimized` below), deliberately kept side by side rather than one
replacing the other -- they answer different questions:
  - full (default): every individual re-verified against the WHOLE
    corpus, unconditionally -- the only way to see exactly which rules a
    SPECIFIC individual verifies (per_individual_coverage_summary.csv /
    per_individual_coverage_long.csv).
  - optimized: a single global "remaining unverified rules" set shrinks
    as individuals are processed; a later individual only gets checked
    against DECISIONS that still hold at least one still-unverified rule
    (and is skipped entirely once nothing remains) -- much cheaper when
    the only real question is "what's the fastest achievable UNION
    coverage," at the cost of not knowing every rule each LATER
    individual could also have verified had it been fully checked
    (per_individual_coverage_summary_optimized.csv /
    per_individual_new_rules_long.csv). See `run_optimized`'s own
    docstring for the full reasoning.
"""
import argparse
import csv
import json
import os
import pickle
import sqlite3
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
VALIDATION_ORACLE_DIR = os.path.join(HERE, '..')
GENERATOR_DIR = os.path.join(HERE, '..', '..', 'generator')
sys.path.insert(0, GENERATOR_DIR)
sys.path.insert(0, VALIDATION_ORACLE_DIR)

from candidate import _OWNER_KEY  # noqa: E402
from materialize import to_sql_inserts, topological_table_order, create_table_ddl  # noqa: E402
from mutation import _schema_for, repair_candidate  # noqa: E402
from dynamosa import (_key_columns_for, _own_solo_unique_columns_for,  # noqa: E402
                       _dedup_composite_keys, _SEED_KEY_OFFSET_UNIT,
                       _deep_copy_individual, _build_decision_subject_row,
                       _apply_cross_table_placeholder_correlations, _scenario_keys_needing_offset)
from coverage import run_coverage, build_subject_tables  # noqa: E402
from phase1_utility import records_by_decision  # noqa: E402
from summarize_coverage import _mechanical_out_of_scope  # noqa: E402
from drd_executor import DecisionRunner, run_decision  # noqa: E402
from out_of_scope_rules import is_out_of_scope  # noqa: E402


def _build_decision_subject_rows_for_individual(candidate, focal_maps, records_by_id, schema=None):
    """Calls `dynamosa._build_decision_subject_row` once per record this
    individual has its own focal rows for -- the SAME junction-row
    synthesis `merge_archive_candidate` already does (compile_constraints.
    py's own `decision_subject` field), ported here 2026-09-26 after a
    real gap was found: this file's own no-merge pipeline never called
    `merge_archive_candidate` at all, so a decision whose real DMN subject
    is a pure junction table no leaf ever reads directly (e.g. Spree's
    `Promotion Customer Group Eligibility`, real subject `spree_order_
    promotions`) never got that row built here, even after the compile
    -time `decision_subject` fix -- confirmed directly: the archived
    individual's own database had zero rows in that table, so independent
    verification had no real subject to enumerate at all, regardless of
    what the search's own per-leaf facts said. Must run AFTER `_offset_
    rows_by_owner` (so a freshly-synthesized row's own key values land in
    the same offset range as everything else this individual owns) and
    BEFORE `repair_candidate` (which fills in whatever this pass leaves
    incomplete), mirroring `merge_archive_candidate`'s own call order
    exactly. `focal_maps`/`records_by_id` must already correspond to
    `candidate`'s own (already copied) rows by real object identity -- see
    `dynamosa._deep_copy_individual`, the only supported way to get that."""
    for rid, rec_focal in focal_maps.items():
        r = records_by_id.get(rid)
        if r is not None:
            _build_decision_subject_row(candidate, rec_focal, r, rid, schema)


def _apply_cross_table_placeholder_correlations_for_individual(candidate, focal_maps, scenario_maps,
                                                                 records_by_id, records_index, schema):
    """Calls `dynamosa._apply_cross_table_placeholder_correlations` once
    per record this individual has its own focal rows for -- the SAME
    correlation `merge_archive_candidate` already applies
    (compile_constraints.py's own `cross_table_placeholders` field),
    ported here 2026-09-26 after a real gap was found tracing jBilling's
    `Currency Exchange Rate Source`: this file's own no-merge pipeline
    never called `merge_archive_candidate` at all, so a placeholder like
    `<entity_id>` never got copied onto its correlated `base_user` row
    here either, even after the compile-time `cross_table_placeholders`
    fix -- same shape as `_build_decision_subject_rows_for_individual`'s
    own gap, fixed the same way. Must run in the SAME relative position
    `merge_archive_candidate` uses -- AFTER `_offset_rows_by_owner` (so a
    freshly-synthesized row's own key values land in the same offset
    range as everything else this individual owns), and BEFORE
    `_build_decision_subject_rows_for_individual` (for the same reason
    `_merge_archive_candidate_impl` orders them that way: the correlated
    table can be the SAME one a subject hop reads FROM to wire the
    subject row itself).

    `scenario_maps` is this individual's OWN (un-offset, straight from
    the archive pickle) `{record_id: {placeholder: value}}` -- each
    record's own offsettable keys are bumped by that record's own
    `records_index`-based offset here, mirroring `_merge_archive_
    candidate_impl`'s identical `i * _SEED_KEY_OFFSET_UNIT` formula
    (`_offset_rows_by_owner`'s own docstring explains why the SAME
    formula, keyed the SAME way, applies within one individual)."""
    for rid, rec_focal in focal_maps.items():
        r = records_by_id.get(rid)
        if r is None:
            continue
        raw_scenario = scenario_maps.get(rid, {})
        offset = records_index.get(rid, 0) * _SEED_KEY_OFFSET_UNIT
        offsettable_keys = _scenario_keys_needing_offset(r) if offset else set()
        rec_scenario = {
            k: (v + offset if k in offsettable_keys and isinstance(v, (int, float)) and not isinstance(v, bool) else v)
            for k, v in raw_scenario.items()
        }
        _apply_cross_table_placeholder_correlations(candidate, rec_focal, rec_scenario, r, rid, schema)


def _offset_rows_by_owner(candidate, schema, records_index, case_study):
    """Found real, not hypothetical (2026-09-25, testing this file's own
    first smoke run): a SINGLE archived individual can carry dedicated
    rows for MANY different objectives at once, not just the one it's
    archived under -- DynaMOSA runs one shared population across every
    objective in the case study, so an individual that happens to also
    satisfy several OTHER objectives along the way keeps their own
    owner-tagged rows too. In the normal flow (dynamosa.py's own
    merge_archive_candidate), this never collides: each objective's own
    rows arrive from a SEPARATE archive entry and get that entry's own
    unique per-record offset. Materializing ONE individual whole, with no
    offsetting at all, means every objective's own rows meet for the
    first time right here -- confirmed directly: 11 different rule_ids'
    own CONCEPT_NUMERIC rows, from 3 unrelated decisions, all defaulting
    the same un-offset `concept_id=1`, a real `UNIQUE constraint failed`.

    Fixed by reusing merge_archive_candidate's OWN proven mechanism
    (`_key_columns_for` + `_SEED_KEY_OFFSET_UNIT`, the identical
    `i * _SEED_KEY_OFFSET_UNIT` formula), just keyed differently: instead
    of one offset per ARCHIVE ENTRY being merged in, one offset per
    OWNER TAG (`_OWNER_KEY`) found within this ONE individual's own row
    set -- `i` is that owner's own index in the compiled `records` list,
    the exact same index merge_archive_candidate would have used had
    this row instead arrived via a normal cross-individual merge. A row
    with no owner tag at all (genuine shared/seed background data, never
    touched by any specific objective's own search) is left completely
    alone -- single, untouched, canonical, same as always.

    Same-owner, same-table, same-solo-unique-column collisions (a single
    owner legitimately holding 2+ rows on one table, each independently
    repaired at a different point in this individual's own history) get
    the SAME dedup-bump `used_key_values` already applies in
    merge_archive_candidate -- the identical plain increment-until-free
    loop, not a new mechanism, just scoped to one individual instead of
    the whole merged output.

    Deliberately NOT attempted here, a real, disclosed limitation: the
    structural filter_text/join-aware cross-reference propagation
    merge_archive_candidate's own `get_copy` also does (`filter_cols`/
    `join_cols`) -- this only offsets a row's own declared PK/UNIQUE/FK
    columns, consistently, within that row's own owner group. A row
    whose FK crosses from one owner's rows into a DIFFERENT owner's
    dedicated row (rather than into the untouched shared baseline) is
    not tracked and could still end up pointing at the wrong place after
    offsetting. Not yet found to matter in practice (the archive entries
    inspected so far -- see the CONCEPT_NUMERIC case above -- were each
    fully self-contained per owner), but not proven absent either; this
    is exactly why every individual still gets independently verified
    against the real validator afterward rather than trusted on the
    strength of this reasoning alone.

    **2026-09-25, fixed**: after each row's own key columns are offset
    above, also calls `dynamosa._dedup_composite_keys` (the SAME shared
    helper `merge_archive_candidate`'s own `get_copy` now calls too) --
    see that function's own docstring for the real FLEX2 `STUDENT_
    ATTENDANCE` composite-PK collision this closes, confirmed by directly
    reproducing it here before the fix and re-running the same individual
    after it.

    **2026-09-26, fixed a THIRD real collision, found running a full,
    un-limited FLEX2 sweep for the first time (the STUDENT_ATTENDANCE fix
    above let individuals PAST the point where they used to always crash,
    reaching this for the first time)**: two or more UNTAGGED rows on the
    SAME table can independently already share the identical value on a
    solo-unique column -- confirmed directly, `individual_037`'s own raw
    (pre-offset, straight from the pickle) `LECTURE` table already carries
    46 separate, genuinely distinct row objects, every one `LECTURE_ID=1`,
    none owner-tagged. Untagged rows are deliberately left alone by the
    main offset/dedup loop below (see this docstring's own "genuine
    shared/seed background data" note) -- correct for a SINGLE shared
    value, but 46 DIFFERENT row objects landing on the identical value is
    never legitimate sharing, it's 46 rows racing to be "the" row at
    `LECTURE_ID=1`, a real `UNIQUE constraint failed` the moment SQL sees
    more than one of them. Unlike the composite-key fix above, this needs
    NO domain judgment call at all -- a solo-unique column, BY DEFINITION,
    can never legitimately hold the same value on two distinct real rows,
    tagged or not, so keeping the FIRST untagged row at its own value and
    bumping every later untagged duplicate to a fresh one is always safe,
    for any table, not just LECTURE. Runs FIRST, before the pre-seed pass
    below (which then correctly sees the already-deduplicated state)."""
    used_key_values = {}

    # Deduplicate UNTAGGED rows against EACH OTHER on every solo-unique
    # column, before anything else -- see this function's own 2026-09-26
    # docstring note for the real LECTURE_ID=1 collision this closes. Only
    # untagged rows are touched here; tagged rows are handled by the main
    # offset/dedup loop further below, which already has its own bump
    # logic scoped to each owner.
    for table, rows in candidate.as_dict().items():
        solo_unique_cols = _own_solo_unique_columns_for(schema, table)
        if not solo_unique_cols:
            continue
        for row in rows:
            if row.get(_OWNER_KEY):
                continue
            for col in list(row):
                if col.upper() not in solo_unique_cols:
                    continue
                val = row[col]
                if not isinstance(val, (int, float)) or isinstance(val, bool):
                    continue
                used = used_key_values.setdefault((table.upper(), col.upper()), set())
                if val in used:
                    new_val = val
                    while new_val in used:
                        new_val += 1
                    row[col] = new_val
                    used.add(new_val)
                else:
                    used.add(val)

    # Pre-seed with every value ALREADY occupying a solo-unique key column
    # anywhere in this candidate, tagged AND untagged rows alike, BEFORE
    # any offsetting below -- a second, real collision found testing this
    # (2026-09-25, same individual as the CONCEPT_NUMERIC case): an
    # UNTAGGED (never touched by any specific objective) CONCEPT row can
    # already be sitting on a value like `concept_id=9000001`, left over
    # from an EARLIER, unrelated application of this exact same
    # `i * _SEED_KEY_OFFSET_UNIT` formula (`_seed_shared_population`'s own
    # seed-time offsetting, keyed by a DIFFERENT record's index than
    # whichever owner is being processed here) -- confirmed directly.
    # Without this pre-seed, a freshly-computed offset is only checked
    # against OTHER OWNERS' rows processed so far in this same pass, never
    # against a pre-existing, untouched value already occupying that same
    # number for an unrelated historical reason.
    for table, rows in candidate.as_dict().items():
        solo_unique_cols = _own_solo_unique_columns_for(schema, table)
        for row in rows:
            for col, val in row.items():
                if col.upper() in solo_unique_cols and isinstance(val, (int, float)) \
                        and not isinstance(val, bool):
                    used_key_values.setdefault((table.upper(), col.upper()), set()).add(val)

    def offset_for(owner):
        i = records_index.get(owner)
        if i is None:
            return 0  # an owner tag not found in this case study's own compiled records -- leave alone
        return i * _SEED_KEY_OFFSET_UNIT

    for table, rows in candidate.as_dict().items():
        key_cols = _key_columns_for(schema, table)
        solo_unique_cols = _own_solo_unique_columns_for(schema, table)
        for row in rows:
            owner = row.get(_OWNER_KEY)
            if not owner:
                continue
            offset = offset_for(owner)
            if not offset:
                continue
            for col in list(row):
                val = row[col]
                if not isinstance(val, (int, float)) or isinstance(val, bool):
                    continue
                if col.upper() not in key_cols:
                    continue
                new_val = val + offset
                if col.upper() in solo_unique_cols:
                    used = used_key_values.setdefault((table.upper(), col.upper()), set())
                    while new_val in used:
                        new_val += 1
                    used.add(new_val)
                row[col] = new_val
            _dedup_composite_keys(schema, table, row, used_key_values, case_study)


def _distinct_archive_individuals(archive):
    """{id(individual): (individual, [record_id, ...])} -- every DISTINCT
    (by object identity) individual the archive holds, with every
    record_id it was ever archived as the best answer for. A record_id
    whose own archive entry is the permanent (float('inf'), <initial
    seed>) placeholder every record starts with (dynamosa.py's own
    run_dynamosa: "every record gets a real entry from the start, even
    one that turns out permanently unresolvable") is INCLUDED like any
    other -- it's a real individual, just one that never got a chance to
    improve; the coverage run against it will honestly show whatever it
    actually verifies, if anything."""
    by_identity = {}
    for record_id, (fitness, individual) in archive.items():
        key = id(individual)
        if key not in by_identity:
            by_identity[key] = (individual, fitness, [])
        by_identity[key][2].append(record_id)
    return by_identity


def _materialize(candidate, case_study, out_db_path):
    schema = _schema_for(case_study)
    if os.path.exists(out_db_path):
        os.remove(out_db_path)
    conn = sqlite3.connect(out_db_path)
    cur = conn.cursor()
    order, _warnings = topological_table_order(schema, candidate.as_dict().keys())
    for table in order:
        ddl = create_table_ddl(table, schema, set(order))
        if ddl is None:
            continue
        cur.execute(ddl)
    sql_statements, _warnings = to_sql_inserts(candidate, schema)
    for stmt in sql_statements:
        cur.execute(stmt)
    conn.commit()
    conn.close()
    return len(sql_statements)


def _print_summary_line(case_study, records, archive, validated_rule_ids):
    """One concise line, printed at the end of both `run` and
    `run_optimized` -- same columns/definitions as `summarize_coverage.py`
    /`summarize_per_individual.py`'s own multi-case-study table (total
    rules, in/out of scope via `_mechanical_out_of_scope`'s own PERMANENT,
    structural proxy -- COLLECT hit policy / all-code_external / the
    out_of_scope_rules.py registry -- NOT the full manual audit), computed
    directly from THIS run's own in-memory results rather than a second
    pass over `summarize_per_individual.py` (which needs all 4 case
    studies' own output directories present under one shared --base-dir,
    an awkward fit for running one case study standalone, which is how
    the user actually runs this script day to day). `claimed_fulfilled`
    reads the SAME already-loaded `archive` dict `run`/`run_optimized`
    both hold, never a second `pickle.load`."""
    by_rule = {}
    for r in records:
        by_rule.setdefault(r['rule_id'], []).append(r)
    total_rules = len(by_rule)
    out_of_scope = _mechanical_out_of_scope(case_study, by_rule)
    in_scope = total_rules - len(out_of_scope)
    # A real bug found running this against Spree (2026-09-26): counting
    # every fitness==0.0 archive entry with NO scope filtering, while
    # `in_scope`/`out_of_scope` DO filter via `_mechanical_out_of_scope`,
    # let `claimed` exceed `in_scope` outright (29 vs 25) -- 5 of Spree's
    # own claimed entries are `PriceAdjustmentTierValidity_rule_1..5`,
    # COLLECT hit policy, out of scope by the SAME mechanical definition
    # `in_scope`/`out_of_scope` already use. The search's own fitness
    # function doesn't care about hit policy and can genuinely reach
    # fitness=0.0 on a COLLECT rule; the validator structurally can't
    # independently check it either way (`rule_evaluator.py` doesn't
    # support COLLECT) -- filtering here just makes this table's own two
    # columns consistent with each other, using the SAME scope definition
    # for both, not a claim about which underlying number was "wrong."
    # A second real bug, found running this against FLEX2 (2026-09-26):
    # summing raw archive ENTRIES (one per record_id) rather than
    # deduplicating by trailing rule_id let `claimed` exceed `total_rules`
    # outright (77 vs 50) -- a decision with DRD fan-out variants (e.g.
    # FLEX2's own `Course Registration Eligibility::Rule_3::via::...`,
    # several distinct record_ids all sharing the SAME trailing rule_id)
    # is counted once per VARIANT here, while `total_rules`/`in_scope`/
    # `validated` all count once per distinct RULE. A rule is "claimed"
    # if ANY of its variants reached fitness=0.0, not once per variant
    # that did.
    claimed = len({rid.split('::')[-1] for rid, (fitness, _ind) in archive.items()
                   if fitness == 0.0} - out_of_scope)
    validated = len(validated_rule_ids)
    pct_all = (validated / total_rules * 100) if total_rules else 0.0
    pct_in_scope = (validated / in_scope * 100) if in_scope else 0.0
    print(f"\n{'Case study':<10}  {'Total':>5}  {'Claimed':>7}  {'In scope':>8}  "
          f"{'Out scope':>9}  {'Validated':>9}  {'% all':>7}  {'% in-scope':>10}")
    print(f"{case_study:<10}  {total_rules:>5}  {claimed:>7}  {in_scope:>8}  "
          f"{len(out_of_scope):>9}  {validated:>9}  {pct_all:>6.1f}%  {pct_in_scope:>9.1f}%")


def run(case_study, archive_pickle_path, out_dir, algorithm='dynamosa_nsga2',
        not_persisted_overrides=None, limit=None):
    os.makedirs(out_dir, exist_ok=True)
    dbs_dir = os.path.join(out_dir, 'dbs')
    runs_dir = os.path.join(out_dir, 'runs')
    os.makedirs(dbs_dir, exist_ok=True)
    os.makedirs(runs_dir, exist_ok=True)

    schema = _schema_for(case_study)
    compiled = json.load(open(os.path.join(GENERATOR_DIR, 'compiled_constraints.json')))
    records = [r for r in compiled if r['case_study'] == case_study]
    # Same index every objective would get from merge_archive_candidate's
    # own per-record offset, if this row had instead arrived through a
    # normal cross-individual merge (see _offset_rows_by_owner's own
    # docstring for why this individual needs the identical treatment
    # applied WITHIN itself, not just across individuals).
    records_index = {r['record_id']: i for i, r in enumerate(records)}
    records_by_id = {r['record_id']: r for r in records}

    with open(archive_pickle_path, 'rb') as f:
        top = pickle.load(f)
    archive = top['archive']

    by_identity = _distinct_archive_individuals(archive)
    items = list(by_identity.items())
    if limit:
        items = items[:limit]

    print(f"{len(archive)} archive record_ids -> {len(by_identity)} distinct individuals "
          f"({len(items)} will be processed this run)")

    long_rows = []
    summary_rows = []

    for idx, (_key, (individual, own_best_fitness, origin_record_ids)) in enumerate(items):
        t0 = time.time()
        tag = f"individual_{idx:03d}"
        origin_str = '; '.join(sorted(r.split('::')[-1] for r in origin_record_ids))
        print(f"[{idx + 1}/{len(items)}] {tag} (archived for {len(origin_record_ids)} "
              f"record_id(s), own best fitness {own_best_fitness}) ...", end=' ', flush=True)
        try:
            work_candidate, work_focal_maps, work_scenario_maps = _deep_copy_individual(individual)
            _offset_rows_by_owner(work_candidate, schema, records_index, case_study)
            _apply_cross_table_placeholder_correlations_for_individual(
                work_candidate, work_focal_maps, work_scenario_maps, records_by_id, records_index, schema)
            _build_decision_subject_rows_for_individual(work_candidate, work_focal_maps, records_by_id, schema)
            repair_candidate(work_candidate, case_study)

            db_path = os.path.join(dbs_dir, tag + '.db')
            n_rows = _materialize(work_candidate, case_study, db_path)

            run_out_dir = os.path.join(runs_dir, tag)
            summary = run_coverage(
                db_path, case_study, algorithm, run_id=tag,
                construction_strategy='per_individual_archive',
                archive=None, out_dir=run_out_dir,
                not_persisted_overrides=not_persisted_overrides)

            results_csv = os.path.join(run_out_dir, 'objective_results.csv')
            verified_rule_ids = []
            with open(results_csv, newline='') as rf:
                for row in csv.DictReader(rf):
                    verified = row['verified_rule_selected'] == 'True'
                    long_rows.append({
                        'individual_index': idx, 'origin_record_ids': origin_str,
                        'rule_id': row['rule_id'], 'decision_name': row['decision_id'],
                        'verified': verified,
                    })
                    if verified:
                        verified_rule_ids.append(row['rule_id'])

            distinct_verified = sorted(set(verified_rule_ids))
            summary_rows.append({
                'individual_index': idx, 'origin_record_ids': origin_str,
                'num_origin_objectives': len(origin_record_ids),
                'num_rules_verified': len(distinct_verified),
                'verified_rule_ids': '; '.join(distinct_verified),
                'db_rows': n_rows, 'error': '',
            })
            print(f"{len(distinct_verified)} rule(s) verified ({time.time() - t0:.1f}s)")
        except Exception as e:  # noqa: BLE001 -- one bad individual must not abort the batch
            print(f"FAILED: {e}")
            traceback.print_exc()
            summary_rows.append({
                'individual_index': idx, 'origin_record_ids': origin_str,
                'num_origin_objectives': len(origin_record_ids),
                'num_rules_verified': 0, 'verified_rule_ids': '',
                'db_rows': 0, 'error': f'{type(e).__name__}: {e}',
            })

    summary_rows.sort(key=lambda r: r['num_rules_verified'], reverse=True)

    long_path = os.path.join(out_dir, 'per_individual_coverage_long.csv')
    with open(long_path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['individual_index', 'origin_record_ids', 'rule_id',
                                           'decision_name', 'verified'])
        w.writeheader()
        w.writerows(long_rows)

    summary_path = os.path.join(out_dir, 'per_individual_coverage_summary.csv')
    with open(summary_path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['individual_index', 'origin_record_ids',
                                           'num_origin_objectives', 'num_rules_verified',
                                           'verified_rule_ids', 'db_rows', 'error'])
        w.writeheader()
        w.writerows(summary_rows)

    multi = [r for r in summary_rows if r['num_rules_verified'] > 1]
    print(f"\nWrote {long_path}")
    print(f"Wrote {summary_path}")
    print(f"{len(multi)}/{len(summary_rows)} individuals verified MORE THAN ONE rule.")
    if multi:
        print("Top 10 by rules verified:")
        for r in multi[:10]:
            print(f"  {r['individual_index']:>4}  {r['num_rules_verified']:>3} rules  "
                  f"(archived for {r['num_origin_objectives']}: {r['origin_record_ids']})")

    validated_rule_ids = set()
    for r in summary_rows:
        if r['verified_rule_ids']:
            validated_rule_ids.update(r['verified_rule_ids'].split('; '))
    _print_summary_line(case_study, records, archive, validated_rule_ids)


def _verify_decision_subset(conn, case_study, decisions_by_name, decision_names, not_persisted_overrides):
    """Mirrors coverage.py's own run_coverage per-decision loop EXACTLY
    (out-of-scope filtering via in_scope_by_name, build_subject_tables,
    DecisionRunner, run_decision, the same NotImplementedError/
    OperationalError/KeyError = 'unresolved, not verified' handling) --
    reused rather than re-derived, so this optimized path can never
    silently diverge from what the full, every-rule-every-individual path
    (`run`, above) would have found for the SAME decision. The only
    difference: scoped to `decision_names` only, not the whole corpus --
    this file's own optimization (`run_optimized`, below) calls this with
    a SHRINKING set as rules get verified, skipping decisions no longer
    worth re-checking. Returns {rule_id: verified_bool} for every rule in
    every one of `decision_names`."""
    subset = {d: decisions_by_name[d] for d in decision_names if d in decisions_by_name}
    in_scope_by_name = {
        name: [r for r in records if not is_out_of_scope(case_study, r['rule_id'])]
        for name, records in subset.items()
    }
    resolved, unresolved = build_subject_tables(case_study, in_scope_by_name)
    runner = DecisionRunner(conn, case_study, in_scope_by_name, resolved,
                             not_persisted_overrides=not_persisted_overrides)

    result = {}
    for decision_name, records in subset.items():
        verified_rule_ids = set()
        if decision_name not in unresolved:
            subject_table, pk_cols, join_paths = resolved[decision_name]
            try:
                run_result = run_decision(
                    conn, decision_name, in_scope_by_name[decision_name], subject_table, pk_cols,
                    join_paths=join_paths, runner=runner, collect_trace=False,
                    not_persisted_overrides=not_persisted_overrides)
                verified_rule_ids = run_result['verified_covered_rule_ids']
            except NotImplementedError:
                pass
            except (sqlite3.OperationalError, KeyError):
                pass
        for r in records:
            result[r['rule_id']] = r['rule_id'] in verified_rule_ids
    return result


def run_optimized(case_study, archive_pickle_path, out_dir, algorithm='dynamosa_nsga2',
                   not_persisted_overrides=None, limit=None):
    """The SAME per-individual materialization as `run`, above (identical
    _deep_copy_individual / _offset_rows_by_owner /
    _apply_cross_table_placeholder_correlations_for_individual /
    _build_decision_subject_rows_for_individual / repair_candidate /
    _materialize pipeline -- nothing about HOW an individual becomes a
    database changes here). What's different: `run` re-verifies the
    ENTIRE compiled corpus against every individual, even for a rule
    dozens of earlier individuals have already verified. This tracks a
    single, global `remaining` set of not-yet-verified rule_ids, and for
    each individual only checks the DECISIONS that still hold at least
    one rule in `remaining` (`_verify_decision_subset`, above) -- a
    decision every one of whose rules is already globally verified costs
    nothing on a later individual. Once `remaining` is empty, every
    further individual is skipped entirely (still recorded in the
    summary, as `error='skipped (nothing left to verify)'`), since
    nothing more can be learned.

    Trade-off, disclosed: this answers a DIFFERENT question than `run`'s
    own per-individual output. `run` tells you exactly which rules EVERY
    individual verifies (useful for the "does one individual satisfy
    several rules" question this whole tool was built for). This tells
    you only WHICH rule first got verified by WHICH individual, and how
    many individuals were needed in total before the achievable set
    stopped growing -- the two are complementary, not redundant, which is
    why both stay available (--mode full / --mode optimized) rather than
    one replacing the other.

    Writes per_individual_coverage_summary_optimized.csv (one row per
    individual processed or skipped) and per_individual_new_rules_long.csv
    (one row per rule newly verified, tagged with which individual first
    verified it) -- deliberately different filenames from `run`'s own
    outputs, so running both modes into the same --out-dir never
    clobbers either."""
    os.makedirs(out_dir, exist_ok=True)
    dbs_dir = os.path.join(out_dir, 'dbs')
    os.makedirs(dbs_dir, exist_ok=True)

    schema = _schema_for(case_study)
    compiled = json.load(open(os.path.join(GENERATOR_DIR, 'compiled_constraints.json')))
    records = [r for r in compiled if r['case_study'] == case_study]
    records_index = {r['record_id']: i for i, r in enumerate(records)}
    records_by_id = {r['record_id']: r for r in records}

    decisions_by_name = records_by_decision(case_study)
    rule_ids_by_decision = {d: {r['rule_id'] for r in recs} for d, recs in decisions_by_name.items()}
    all_rule_ids = {r['rule_id'] for r in records}
    remaining = set(all_rule_ids)

    with open(archive_pickle_path, 'rb') as f:
        top = pickle.load(f)
    archive = top['archive']
    by_identity = _distinct_archive_individuals(archive)
    items = list(by_identity.items())
    if limit:
        items = items[:limit]

    print(f"{len(archive)} archive record_ids -> {len(by_identity)} distinct individuals "
          f"({len(items)} will be processed this run); {len(all_rule_ids)} rule(s) to track")

    long_rows = []
    summary_rows = []

    for idx, (_key, (individual, own_best_fitness, origin_record_ids)) in enumerate(items):
        tag = f"individual_{idx:03d}"
        origin_str = '; '.join(sorted(r.split('::')[-1] for r in origin_record_ids))

        if not remaining:
            print(f"[{idx + 1}/{len(items)}] {tag}: SKIPPED -- every rule already verified "
                  f"by an earlier individual")
            summary_rows.append({
                'individual_index': idx, 'origin_record_ids': origin_str,
                'num_origin_objectives': len(origin_record_ids), 'decisions_checked': 0,
                'num_new_rules_verified': 0, 'new_verified_rule_ids': '', 'db_rows': 0,
                'error': 'skipped (nothing left to verify)',
            })
            continue

        decisions_to_check = {d for d, rids in rule_ids_by_decision.items() if rids & remaining}
        t0 = time.time()
        print(f"[{idx + 1}/{len(items)}] {tag} (archived for {len(origin_record_ids)} record_id(s), "
              f"checking {len(decisions_to_check)}/{len(rule_ids_by_decision)} decisions still "
              f"holding {len(remaining)} unverified rule(s)) ...", end=' ', flush=True)
        try:
            work_candidate, work_focal_maps, work_scenario_maps = _deep_copy_individual(individual)
            _offset_rows_by_owner(work_candidate, schema, records_index, case_study)
            _apply_cross_table_placeholder_correlations_for_individual(
                work_candidate, work_focal_maps, work_scenario_maps, records_by_id, records_index, schema)
            _build_decision_subject_rows_for_individual(work_candidate, work_focal_maps, records_by_id, schema)
            repair_candidate(work_candidate, case_study)

            db_path = os.path.join(dbs_dir, tag + '.db')
            n_rows = _materialize(work_candidate, case_study, db_path)

            conn = sqlite3.connect(db_path)
            try:
                verified = _verify_decision_subset(conn, case_study, decisions_by_name,
                                                    decisions_to_check, not_persisted_overrides)
            finally:
                conn.close()

            newly = sorted(rid for rid, ok in verified.items() if ok and rid in remaining)
            remaining.difference_update(newly)
            for rid in newly:
                long_rows.append({'individual_index': idx, 'origin_record_ids': origin_str, 'rule_id': rid})

            summary_rows.append({
                'individual_index': idx, 'origin_record_ids': origin_str,
                'num_origin_objectives': len(origin_record_ids),
                'decisions_checked': len(decisions_to_check),
                'num_new_rules_verified': len(newly), 'new_verified_rule_ids': '; '.join(newly),
                'db_rows': n_rows, 'error': '',
            })
            print(f"{len(newly)} NEW rule(s) verified, {len(remaining)} still remaining "
                  f"({time.time() - t0:.1f}s)")
        except Exception as e:  # noqa: BLE001 -- one bad individual must not abort the batch
            print(f"FAILED: {e}")
            traceback.print_exc()
            summary_rows.append({
                'individual_index': idx, 'origin_record_ids': origin_str,
                'num_origin_objectives': len(origin_record_ids),
                'decisions_checked': len(decisions_to_check),
                'num_new_rules_verified': 0, 'new_verified_rule_ids': '', 'db_rows': 0,
                'error': f'{type(e).__name__}: {e}',
            })

    long_path = os.path.join(out_dir, 'per_individual_new_rules_long.csv')
    with open(long_path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['individual_index', 'origin_record_ids', 'rule_id'])
        w.writeheader()
        w.writerows(long_rows)

    summary_path = os.path.join(out_dir, 'per_individual_coverage_summary_optimized.csv')
    with open(summary_path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['individual_index', 'origin_record_ids',
                                           'num_origin_objectives', 'decisions_checked',
                                           'num_new_rules_verified', 'new_verified_rule_ids',
                                           'db_rows', 'error'])
        w.writeheader()
        w.writerows(summary_rows)

    print(f"\nWrote {long_path}")
    print(f"Wrote {summary_path}")
    total_verified = len(all_rule_ids) - len(remaining)
    print(f"{total_verified}/{len(all_rule_ids)} rules verified across every individual processed.")
    if remaining:
        print(f"{len(remaining)} rule(s) never verified by any individual: {sorted(remaining)}")

    _print_summary_line(case_study, records, archive, all_rule_ids - remaining)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--case-study', required=True)
    ap.add_argument('--archive-pickle', required=True,
                     help='Path to an experiment_runs/*.pkl (e.g. '
                          'generator/experiment_runs/OpenMRS__dynamosa_nsga2__budget1x__seed0.pkl)')
    ap.add_argument('--out-dir', required=True)
    ap.add_argument('--mode', choices=['full', 'optimized'], default='full',
                     help="'full' (default): every individual re-verified against the WHOLE corpus "
                          "-- use this to see which rules a SPECIFIC individual verifies. "
                          "'optimized': a global remaining-rules set shrinks as individuals are "
                          "processed, skipping decisions (and eventually whole individuals) that can "
                          "no longer teach us anything new -- use this only to find the fastest "
                          "achievable UNION coverage, not per-individual detail.")
    ap.add_argument('--algorithm', default='dynamosa_nsga2',
                     help='Label only (this run never compares against search-claimed coverage)')
    ap.add_argument('--not-persisted-json', default=None,
                     help='Optional path to a JSON {var_name: value} of explicit, disclosed '
                          'not_persisted overrides (same convention as coverage.py\'s own flag)')
    ap.add_argument('--limit', type=int, default=None,
                     help='Process only the first N distinct individuals (for a quick smoke test '
                          'before committing to the full run)')
    args = ap.parse_args()

    not_persisted_overrides = None
    if args.not_persisted_json:
        with open(args.not_persisted_json) as f:
            not_persisted_overrides = json.load(f)

    fn = run if args.mode == 'full' else run_optimized
    fn(args.case_study, args.archive_pickle, args.out_dir, algorithm=args.algorithm,
       not_persisted_overrides=not_persisted_overrides, limit=args.limit)
