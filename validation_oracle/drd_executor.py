"""Enumerates real subject entities for a decision from the live
database (no anchoring, no search-time tagging -- see DESIGN.md), and
evaluates that decision's rule table fresh for each one, using
db_resolver.py + rule_evaluator.py.

Current scope, disclosed: handles a SINGLE decision with no upstream
DRD dependency (confirmed true of OpenMRS's Preferred Identifier
Requirement, the acceptance-test target). Full DRD-ordered multi-decision
execution -- evaluating an upstream decision first and feeding its real
output into a downstream one -- is not yet implemented; `run_decision`
raises if any of the decision's objectives reference a
`literal_via_upstream_branch`/`substituted_decision` variable, rather
than silently ignoring the dependency.
"""
import sqlite3


def _distinct_subject_values(conn, subject_table, subject_pk_column):
    cur = conn.execute(f'SELECT DISTINCT "{subject_pk_column}" FROM "{subject_table}"')
    return [row[0] for row in cur.fetchall()]


def run_decision(conn, decision_name, records, subject_table, subject_pk_column):
    """`records` is every compiled objective for this decision (Phase 1,
    via phase1_utility.records_by_decision), used only for their own
    `rule_id`/`condition`/`variable_resolution` -- never for row
    identity. Returns a dict: {
        'matched_by_case': {subject_pk_value: [rule_id, ...]},
        'selected_by_case': {subject_pk_value: rule_id_or_None},
        'verified_covered_rule_ids': set(),
    }"""
    from db_resolver import resolve
    from rule_evaluator import select_rule, UniqueViolation

    all_resolutions = {}
    for r in records:
        for var, node in r['variable_resolution'].items():
            if node.get('kind') in ('literal_via_upstream_branch', 'substituted_decision'):
                raise NotImplementedError(
                    f"{decision_name!r} objective {r['record_id']!r} needs upstream decision "
                    f"output ({var}) -- DRD-ordered multi-decision execution not yet "
                    f"implemented (see DESIGN.md open issues)")
            all_resolutions[var] = node

    # One condition per DISTINCT rule_id, in real document order. A
    # decision can have several objectives per rule (DRD fan-out --
    # see generator/DECISIONS_ALGORITHM.md's own rule/objective finding)
    # but they all share the same rule_id and condition; dedupe by
    # first occurrence, in the order Phase 1 already lists them.
    seen_rules = {}
    for r in records:
        if r['rule_id'] not in seen_rules:
            seen_rules[r['rule_id']] = r['condition']
    rules_with_conditions = [(rid, i, cond) for i, (rid, cond) in enumerate(seen_rules.items())]
    hit_policy = records[0]['hit_policy']

    matched_by_case = {}
    selected_by_case = {}
    verified_covered = set()
    violations = []

    for subject_val in _distinct_subject_values(conn, subject_table, subject_pk_column):
        values = {}
        for var, node in all_resolutions.items():
            values[var] = resolve(conn, node, subject_table, subject_pk_column, subject_val).value
        try:
            matched, selected = select_rule(hit_policy, rules_with_conditions, values)
        except UniqueViolation as e:
            violations.append((subject_val, e))
            continue
        matched_by_case[subject_val] = matched
        selected_by_case[subject_val] = selected
        if selected:
            verified_covered.add(selected)

    return {
        'matched_by_case': matched_by_case,
        'selected_by_case': selected_by_case,
        'verified_covered_rule_ids': verified_covered,
        'unique_violations': violations,
    }


if __name__ == '__main__':
    import json
    import os
    import sys

    from phase1_utility import records_by_decision

    HERE = os.path.dirname(os.path.abspath(__file__))
    # Only needed to unpickle the archive for THIS demo script's own
    # search-vs-verified comparison printout -- the oracle's actual
    # pipeline (everything above this line) never does this.
    sys.path.insert(0, os.path.join(HERE, '..', 'generator'))
    conn = sqlite3.connect(os.path.join(HERE, 'tests', 'fixtures', 'openmrs_merged.db'))

    decision_name = 'Preferred Identifier Requirement'
    records = records_by_decision('OpenMRS')[decision_name]
    result = run_decision(conn, decision_name, records, 'patient_identifier', 'patient_identifier_id')

    print(f"{decision_name} -- {len(result['selected_by_case'])} real cases enumerated\n")
    for pk, selected in sorted(result['selected_by_case'].items()):
        print(f"  patient_identifier_id={pk}: selected={selected}  matched={result['matched_by_case'][pk]}")

    print(f"\nVerified covered rule IDs: {sorted(result['verified_covered_rule_ids'])}")

    # Compare against search coverage (archive) for the SAME objectives --
    # reading only the already-saved raw archive, never fitness.py.
    with open(os.path.join(HERE, '..', 'generator', 'experiment_runs',
                            'OpenMRS__dynamosa_nsga2__budget1x__seed0.json')) as f:
        pass  # metadata only has coverage_history, not per-objective; use the pickle instead
    import pickle
    with open(os.path.join(HERE, '..', 'generator', 'experiment_runs',
                            'OpenMRS__dynamosa_nsga2__budget1x__seed0.pkl'), 'rb') as f:
        archive = pickle.load(f)['archive']

    print(f"\n{'objective_id':<90} {'search_covered':<15} {'verified_selected'}")
    for r in records:
        search_covered = archive[r['record_id']][0] == 0.0
        verified_selected = r['rule_id'] in result['verified_covered_rule_ids']
        agreement = (
            'confirmed' if search_covered and verified_selected else
            'FALSE POSITIVE' if search_covered and not verified_selected else
            'false negative' if not search_covered and verified_selected else
            'agreed uncovered')
        print(f"{r['record_id']:<90} {str(search_covered):<15} {str(verified_selected):<18} {agreement}")
