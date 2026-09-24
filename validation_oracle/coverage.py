"""Aggregates independent verification results across every decision in
a case study, for ONE already-materialized database (produced elsewhere
-- see module docstring in `tests/build_fixture_from_generator.py` for
how the test fixtures were built; a real pipeline would materialize the
same way, outside this package), and writes the three machine-readable
output artifacts:

- `objective_results.csv` -- one row per compiled objective
- `validation_summary.csv` -- one row per (case_study, algorithm, run_id,
  construction_strategy)
- `decision_trace.json` -- one entry per (decision, real case)

Never imports `generator/fitness.py`/`evaluate_objective`. `archive`
(when given) is read directly from an already-saved raw pickle
(`generator/experiment_runs/*.pkl`) purely for the `search_covered`/
`best_search_fitness` comparison columns -- the verification itself
(`verified_rule_selected`, `matched_rule_ids`, `selected_rule_id`) never
depends on it.

Decisions this validator cannot yet resolve a subject table for (see
`subject_table.subject_table_for_decision`'s own disclosed limits) are
NOT silently skipped: their objectives appear in `objective_results.csv`
with `verified_rule_selected=False` and `agreement_class` computed
accordingly, and the decision itself is recorded in
`validation_summary.csv`'s own `unresolved_decisions` count -- never
counted as verified, never dropped from the denominator.
"""
import csv
import json
import os
import sqlite3

from phase1_utility import records_by_decision, statically_infeasible_count
from subject_table import subject_table_for_decision
from drd_executor import DecisionRunner, run_decision, _rules_with_conditions

OBJECTIVE_RESULTS_COLUMNS = [
    'case_id', 'algorithm', 'run_id', 'construction_strategy', 'objective_id',
    'decision_id', 'rule_id', 'rule_index', 'hit_policy', 'best_search_fitness',
    'search_covered', 'verified_rule_selected', 'first_generation_covered', 'agreement_class',
]

VALIDATION_SUMMARY_COLUMNS = [
    'case_id', 'algorithm', 'run_id', 'construction_strategy', 'total_dmn_rules',
    'statically_infeasible_rules', 'searchable_objectives', 'search_covered_objectives',
    'verified_covered_rules', 'search_coverage_percent', 'verified_rule_coverage_percent',
    'coverage_retention_percent', 'schema_valid', 'dmn_validation_valid', 'total_rows',
    'unresolved_decisions',
]


def _schema_valid(conn):
    """Independent, generic check -- PRAGMA foreign_key_check against
    the ALREADY-MATERIALIZED database, not a call into
    generator/materialize.py. True only if the live database has zero
    dangling FK references, exactly like materialize.py's own
    validate_with_sqlite checks, just re-derived here so this module
    never imports generator/ code to answer it."""
    cur = conn.execute('PRAGMA foreign_key_check')
    return len(cur.fetchall()) == 0


def _total_rows(conn):
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    return sum(conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in tables)


def _agreement_class(search_covered, verified_selected):
    if search_covered and verified_selected:
        return 'confirmed'
    if search_covered and not verified_selected:
        return 'false_positive'
    if not search_covered and verified_selected:
        return 'false_negative'
    return 'agreed_uncovered'


def build_subject_tables(case_study, decisions_by_name):
    """{decision_name: (subject_table, pk_cols, join_paths)} for every
    decision that resolves, and {decision_name: error_message} for every
    one that doesn't -- both returned, so the caller can process the
    resolvable ones and still honestly report the unresolved ones,
    rather than one failure aborting the whole case study."""
    resolved = {}
    unresolved = {}
    for name, records in decisions_by_name.items():
        try:
            resolved[name] = subject_table_for_decision(records, case_study)
        except ValueError as e:
            unresolved[name] = str(e)
    return resolved, unresolved


def run_coverage(db_path, case_study, algorithm, run_id, construction_strategy,
                  archive=None, out_dir='.', not_persisted_overrides=None):
    """`archive` is the already-loaded {record_id: (fitness, individual)}
    dict from a saved run's own pickle (never re-derived from fitness.py
    here) -- omit it to report verified-only results with
    search_covered/best_search_fitness left blank (e.g. when validating
    a database that didn't come from this project's own search at all).
    `not_persisted_overrides` is an explicit, disclosed {var_name: value}
    for any `not_persisted` variable a decision needs -- never read from
    search state (see DESIGN.md's own discussion of why `evaluationTime`
    specifically should NOT be taken from any archived individual's own
    scenario: the search tunes it independently per rule, not as one
    fixed "current time" a real evaluation run would use). A
    `not_persisted` variable with no entry here is recorded as an
    unresolved decision, never silently treated as covered.
    Writes the three output files into `out_dir` (created if needed) and
    returns the summary dict that also becomes `validation_summary.csv`'s
    one row."""
    os.makedirs(out_dir, exist_ok=True)
    conn = sqlite3.connect(db_path)
    decisions_by_name = records_by_decision(case_study)
    resolved, unresolved = build_subject_tables(case_study, decisions_by_name)

    runner = DecisionRunner(conn, case_study, decisions_by_name, resolved,
                             not_persisted_overrides=not_persisted_overrides)

    objective_rows = []
    decision_traces = []
    verified_covered_rule_ids_overall = set()
    unique_violation_count = 0

    for decision_name, records in decisions_by_name.items():
        rules_with_conditions = _rules_with_conditions(records)
        rule_index_by_id = {rid: idx for rid, idx, _cond in rules_with_conditions}

        verified_rule_ids = set()
        trace_entries = []
        if decision_name not in unresolved:
            subject_table, pk_cols, join_paths = resolved[decision_name]
            try:
                result = run_decision(conn, decision_name, records, subject_table, pk_cols,
                                       join_paths=join_paths, runner=runner, collect_trace=True,
                                       not_persisted_overrides=not_persisted_overrides)
            except NotImplementedError as e:
                # A resolution kind this validator doesn't yet handle
                # independently (not_persisted with no declared value,
                # derived_join_count edge cases, ...) -- record it as
                # unresolved for THIS decision rather than crashing the
                # whole report; every other decision still gets verified.
                unresolved[decision_name] = f"run_decision failed: {e}"
            else:
                verified_rule_ids = result['verified_covered_rule_ids']
                verified_covered_rule_ids_overall |= verified_rule_ids
                unique_violation_count += len(result['unique_violations'])

                for pk_vals, entry in result['trace'].items():
                    trace_entries.append({
                        'case_id': case_study, 'algorithm': algorithm, 'run_id': run_id,
                        'decision_id': decision_name, 'decision_name': decision_name,
                        'subject_pk_columns': list(pk_cols), 'subject_pk_values': list(pk_vals),
                        'resolved_inputs': entry['resolved_inputs'],
                        'matched_rule_ids': entry['matched_rule_ids'],
                        'selected_rule_id': entry['selected_rule_id'],
                        'decision_output': entry['decision_output'],
                        'ungrounded': entry['ungrounded'],
                        'hit_policy': records[0]['hit_policy'],
                    })
        decision_traces.extend(trace_entries)

        for r in records:
            best_fitness = archive[r['record_id']][0] if archive is not None else None
            search_covered = (best_fitness == 0.0) if archive is not None else None
            verified_selected = r['rule_id'] in verified_rule_ids
            objective_rows.append({
                'case_id': case_study, 'algorithm': algorithm, 'run_id': run_id,
                'construction_strategy': construction_strategy,
                'objective_id': r['record_id'], 'decision_id': decision_name,
                'rule_id': r['rule_id'], 'rule_index': rule_index_by_id.get(r['rule_id']),
                'hit_policy': r['hit_policy'], 'best_search_fitness': best_fitness,
                'search_covered': search_covered, 'verified_rule_selected': verified_selected,
                'first_generation_covered': None,  # not tracked by the raw archive -- see DESIGN.md
                'agreement_class': (_agreement_class(search_covered, verified_selected)
                                     if archive is not None else
                                     ('verified' if verified_selected else 'not_verified')),
            })

    searchable_objectives = len(objective_rows)
    infeasible = statically_infeasible_count(case_study)
    search_covered_objectives = sum(1 for r in objective_rows if r['search_covered']) \
        if archive is not None else None
    all_rule_ids = {r['rule_id'] for r in objective_rows}
    verified_covered_rules = len(verified_covered_rule_ids_overall)

    search_covered_rule_ids = {r['rule_id'] for r in objective_rows if r['search_covered']} \
        if archive is not None else set()
    retention = (len(verified_covered_rule_ids_overall & search_covered_rule_ids) /
                 len(search_covered_rule_ids) * 100) if search_covered_rule_ids else None

    summary = {
        'case_id': case_study, 'algorithm': algorithm, 'run_id': run_id,
        'construction_strategy': construction_strategy,
        'total_dmn_rules': searchable_objectives + infeasible,
        'statically_infeasible_rules': infeasible,
        'searchable_objectives': searchable_objectives,
        'search_covered_objectives': search_covered_objectives,
        'verified_covered_rules': verified_covered_rules,
        'search_coverage_percent': (
            search_covered_objectives / searchable_objectives * 100
            if archive is not None and searchable_objectives else None),
        'verified_rule_coverage_percent': (
            verified_covered_rules / len(all_rule_ids) * 100 if all_rule_ids else None),
        'coverage_retention_percent': retention,
        'schema_valid': _schema_valid(conn),
        'dmn_validation_valid': unique_violation_count == 0,
        'total_rows': _total_rows(conn),
        'unresolved_decisions': len(unresolved),
    }

    with open(os.path.join(out_dir, 'objective_results.csv'), 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=OBJECTIVE_RESULTS_COLUMNS)
        writer.writeheader()
        writer.writerows(objective_rows)

    with open(os.path.join(out_dir, 'validation_summary.csv'), 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=VALIDATION_SUMMARY_COLUMNS)
        writer.writeheader()
        writer.writerow(summary)

    with open(os.path.join(out_dir, 'decision_trace.json'), 'w') as f:
        json.dump(decision_traces, f, indent=2, default=str)

    if unresolved:
        with open(os.path.join(out_dir, 'unresolved_decisions.json'), 'w') as f:
            json.dump(unresolved, f, indent=2)

    return summary


if __name__ == '__main__':
    import argparse
    import pickle
    import sys

    # Only needed to unpickle a raw archive (Candidate/focal_maps objects
    # need generator/candidate.py importable) for the OPTIONAL search-
    # coverage comparison columns -- run_coverage()'s own verification
    # path above never imports generator/ code.
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'generator'))

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--db', required=True, help='Path to an already-materialized SQLite database')
    ap.add_argument('--case-study', required=True)
    ap.add_argument('--algorithm', required=True)
    ap.add_argument('--run-id', required=True)
    ap.add_argument('--construction-strategy', required=True)
    ap.add_argument('--archive-pickle', default=None,
                     help='Optional path to a raw experiment_runs/*.pkl for search-coverage comparison')
    ap.add_argument('--not-persisted-json', default=None,
                     help='Optional path to a JSON {var_name: value} of explicit, disclosed '
                          'not_persisted overrides -- never derived from search state')
    ap.add_argument('--out-dir', default='.')
    args = ap.parse_args()

    not_persisted_overrides = None
    if args.not_persisted_json:
        with open(args.not_persisted_json) as f:
            not_persisted_overrides = json.load(f)

    archive = None
    if args.archive_pickle:
        with open(args.archive_pickle, 'rb') as f:
            archive = pickle.load(f)['archive']

    summary = run_coverage(args.db, args.case_study, args.algorithm, args.run_id,
                            args.construction_strategy, archive=archive, out_dir=args.out_dir,
                            not_persisted_overrides=not_persisted_overrides)
    print(json.dumps(summary, indent=2, default=str))
