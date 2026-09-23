"""Enumerates real subject entities for a decision from the live
database (no anchoring, no search-time tagging -- see DESIGN.md), and
evaluates that decision's rule table fresh for each one, using
db_resolver.py + rule_evaluator.py.

DRD-ordered chaining (`literal_via_upstream_branch`/`substituted_decision`)
is implemented via `DecisionRunner` -- a small memoized recursion: a
downstream decision's own objectives may need an upstream decision's
REAL selected rule (`literal_via_upstream_branch`) or an upstream
literal-expression decision's own formula, inlined with free variables
resolved fresh (`substituted_decision`). Both are resolved by running
the upstream decision through this SAME independent pipeline first --
never by injecting an assumed/expected value. See each kind's own
handler below for exactly what "for the same real case" means when the
two decisions don't share one subject table.
"""
import sqlite3

from db_resolver import resolve
from rule_evaluator import select_rule, evaluate_expression, UniqueViolation


def _distinct_subject_values(conn, subject_table, subject_pk_column):
    cur = conn.execute(f'SELECT DISTINCT "{subject_pk_column}" FROM "{subject_table}"')
    return [row[0] for row in cur.fetchall()]


def _rules_with_conditions(records):
    """One condition per DISTINCT rule_id, in real document order. A
    decision can have several objectives per rule (DRD fan-out -- see
    generator/DECISIONS_ALGORITHM.md's own rule/objective finding) but
    they all share the same rule_id and condition; dedupe by first
    occurrence, in the order Phase 1 already lists them."""
    seen_rules = {}
    for r in records:
        if r['rule_id'] not in seen_rules:
            seen_rules[r['rule_id']] = r['condition']
    return [(rid, i, cond) for i, (rid, cond) in enumerate(seen_rules.items())]


class UngroundedForCase(Exception):
    """Raised internally when a `literal_via_upstream_branch` variable's
    own precondition (the upstream decision must have selected a SPECIFIC
    rule) does not hold for the real case under evaluation -- this
    objective's rule simply is not reachable via this real case, which
    is a normal, expected outcome for most (case, objective) pairs, not
    an error. Caught by `run_decision`'s own per-case loop, which then
    treats that objective's rule as correctly not-matched for this case,
    exactly like any ordinary false condition."""


class DecisionRunner:
    """Recursively evaluates decisions in DRD order, memoized per
    (decision_name, subject_pk_value) so an upstream decision needed by
    several downstream objectives is only actually run once per real
    case. Owns the live connection and the whole case study's compiled
    records/DMN structure/schema join-path cache."""

    def __init__(self, conn, case_study, records_by_decision, subject_tables):
        self.conn = conn
        self.case_study = case_study
        self.records_by_decision = records_by_decision
        # {decision_name: (subject_table, join_paths)}, pre-derived by
        # the caller via subject_table.subject_table_for_decision for
        # every decision this run might need to chain into.
        self.subject_tables = subject_tables
        self._cache = {}  # {(decision_name, subject_pk_value): run_decision() result}

    def run(self, decision_name, subject_pk_value):
        key = (decision_name, subject_pk_value)
        if key not in self._cache:
            records = self.records_by_decision[decision_name]
            subject_table, join_paths = self.subject_tables[decision_name]
            self._cache[key] = run_decision(
                self.conn, decision_name, records, subject_table, f'{subject_table}_id',
                join_paths=join_paths, runner=self, only_case=subject_pk_value)
        return self._cache[key]

    def upstream_subject_value(self, upstream_decision_name, downstream_subject_table,
                                downstream_subject_value):
        """The upstream decision's own subject-row value that corresponds
        to the CURRENT downstream case -- found by joining from the
        downstream subject row to the upstream decision's own subject
        table, via schema_utility's forward-only FK path (same mechanism
        `subject_table.py` uses within one decision, applied here BETWEEN
        two decisions' subject tables). Raises if no such path exists --
        never guesses which upstream row a downstream case corresponds to."""
        from schema_utility import build_join_path
        from db_resolver import _row_for_table

        upstream_table, _upstream_joins = self.subject_tables[upstream_decision_name]
        if upstream_table == downstream_subject_table:
            return downstream_subject_value

        # Search across every decision's own fk_closure_tables for a
        # usable path -- the downstream decision's own closure is what
        # actually matters (it's the one whose row we're starting from).
        downstream_records = next(iter(self.records_by_decision.values()))
        closure = set()
        for recs in self.records_by_decision.values():
            for r in recs:
                closure |= set(r.get('fk_closure_tables', []))
        path = build_join_path(self.case_study, downstream_subject_table, upstream_table, closure)
        if path is None:
            raise NotImplementedError(
                f"No join path from {downstream_subject_table!r} to upstream decision "
                f"{upstream_decision_name!r}'s own subject table {upstream_table!r}")

        row = _row_for_table(self.conn, downstream_subject_table, downstream_subject_table,
                              f'{downstream_subject_table}_id', downstream_subject_value, {})
        for hop in path:
            if row is None:
                return None
            fk_value = row.get(hop['from_column'])
            row = _row_for_table(self.conn, hop['to_table'], hop['to_table'],
                                  hop['to_column'], fk_value, {}) if fk_value is not None else None
        return row[f'{upstream_table}_id'] if row else None


def _resolve_one(conn, case_study, var, node, subject_table, subject_pk_column, subject_val,
                  join_paths, runner, decision_name):
    if node.get('kind') == 'literal_via_upstream_branch':
        upstream_decision = node['from_decision']
        upstream_subject_val = runner.upstream_subject_value(
            upstream_decision, subject_table, subject_val)
        if upstream_subject_val is None:
            raise UngroundedForCase(f"{var}: no corresponding {upstream_decision!r} row")
        upstream_result = runner.run(upstream_decision, upstream_subject_val)
        actual_selected = upstream_result['selected_by_case'].get(upstream_subject_val)
        if actual_selected != node['from_rule_id']:
            raise UngroundedForCase(
                f"{var}: upstream {upstream_decision!r} selected {actual_selected!r}, "
                f"not the required {node['from_rule_id']!r}")
        return resolve(conn, node['value'], subject_table, subject_pk_column, subject_val, join_paths).value

    if node.get('kind') == 'substituted_decision':
        free_values = {}
        for free_var, free_node in node['free_variable_resolutions'].items():
            free_values[free_var] = _resolve_one(
                conn, case_study, free_var, free_node, subject_table, subject_pk_column,
                subject_val, join_paths, runner, decision_name)
        return evaluate_expression(node['expression'], free_values)

    return resolve(conn, node, subject_table, subject_pk_column, subject_val, join_paths).value


def run_decision(conn, decision_name, records, subject_table, subject_pk_column,
                  join_paths=None, runner=None, only_case=None):
    """`records` is every compiled objective for this decision (Phase 1,
    via phase1_utility.records_by_decision), used only for their own
    `rule_id`/`condition`/`variable_resolution` -- never for row
    identity. `runner` (a `DecisionRunner`) is required when any
    objective needs an upstream decision's real output; `only_case`
    restricts enumeration to one subject value (used by `DecisionRunner`
    itself, recursively -- a top-level call omits it and enumerates
    every real case). Returns a dict: {
        'matched_by_case': {subject_pk_value: [rule_id, ...]},
        'selected_by_case': {subject_pk_value: rule_id_or_None},
        'verified_covered_rule_ids': set(),
        'unique_violations': [...],
    }"""
    case_study = records[0]['case_study']
    all_resolutions = {}
    for r in records:
        all_resolutions.update(r['variable_resolution'])

    rules_with_conditions = _rules_with_conditions(records)
    hit_policy = records[0]['hit_policy']

    subject_values = [only_case] if only_case is not None else \
        _distinct_subject_values(conn, subject_table, subject_pk_column)

    matched_by_case = {}
    selected_by_case = {}
    verified_covered = set()
    violations = []

    for subject_val in subject_values:
        values = {}
        ungrounded = False
        for var, node in all_resolutions.items():
            try:
                values[var] = _resolve_one(conn, case_study, var, node, subject_table,
                                            subject_pk_column, subject_val, join_paths or {},
                                            runner, decision_name)
            except UngroundedForCase:
                ungrounded = True
                break
        if ungrounded:
            matched_by_case[subject_val] = []
            selected_by_case[subject_val] = None
            continue
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
