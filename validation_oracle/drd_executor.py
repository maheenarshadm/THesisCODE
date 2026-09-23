"""Enumerates real subject entities for a decision from the live
database (no anchoring, no search-time tagging -- see DESIGN.md), and
evaluates that decision's rule table fresh for each one, using
db_resolver.py + rule_evaluator.py.

Subject identity is always a (pk_cols, pk_vals) pair of tuples, even for
a single-column key -- matches `schema_utility.pk_columns`'s own
always-a-list convention (composite PKs are real here: FLEX2's
STUDENT_SEMESTER, discovered as Course Load Limit's own subject table,
has PK [SEM_ID, ROLL_NO]).

DRD-ordered chaining (`literal_via_upstream_branch`/`substituted_decision`)
is implemented via `DecisionRunner` -- a small memoized recursion: a
downstream decision's own objectives may need an upstream decision's
REAL selected rule (`literal_via_upstream_branch`) or an upstream
literal-expression decision's own formula, inlined with free variables
resolved fresh (`substituted_decision`). Both are resolved by running
the upstream decision through this SAME independent pipeline first --
never by injecting an assumed/expected value.
"""
import sqlite3

from db_resolver import resolve
from rule_evaluator import select_rule, evaluate_expression, UniqueViolation


def _distinct_subject_keys(conn, subject_table, pk_cols):
    cols_sql = ', '.join(f'"{c}"' for c in pk_cols)
    cur = conn.execute(f'SELECT DISTINCT {cols_sql} FROM "{subject_table}"')
    return [row for row in cur.fetchall()]


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
    (decision_name, subject_pk_vals) so an upstream decision needed by
    several downstream objectives is only actually run once per real
    case. Owns the live connection and the whole case study's compiled
    records/DMN structure/schema join-path cache."""

    def __init__(self, conn, case_study, records_by_decision, subject_tables):
        self.conn = conn
        self.case_study = case_study
        self.records_by_decision = records_by_decision
        # {decision_name: (subject_table, pk_cols, join_paths)}, pre-derived
        # by the caller via subject_table.subject_table_for_decision for
        # every decision this run might need to chain into.
        self.subject_tables = subject_tables
        self._cache = {}  # {(decision_name, subject_pk_vals): run_decision() result}

    def run(self, decision_name, subject_pk_vals):
        key = (decision_name, tuple(subject_pk_vals))
        if key not in self._cache:
            records = self.records_by_decision[decision_name]
            subject_table, pk_cols, join_paths = self.subject_tables[decision_name]
            self._cache[key] = run_decision(
                self.conn, decision_name, records, subject_table, pk_cols,
                join_paths=join_paths, runner=self, only_case=subject_pk_vals)
        return self._cache[key]

    def upstream_subject_value(self, upstream_decision_name, downstream_subject_table,
                                downstream_pk_cols, downstream_pk_vals):
        """The upstream decision's own subject-row key that corresponds
        to the CURRENT downstream case -- found by joining from the
        downstream subject row to the upstream decision's own subject
        table, via schema_utility's forward-only FK path (same mechanism
        `subject_table.py` uses within one decision, applied here BETWEEN
        two decisions' subject tables). Raises if no such path exists --
        never guesses which upstream row a downstream case corresponds
        to. Returns a tuple of pk values, or None if no real row exists."""
        from schema_utility import build_join_path
        from db_resolver import _row_for_table

        upstream_table, upstream_pk_cols, _upstream_joins = self.subject_tables[upstream_decision_name]
        if upstream_table == downstream_subject_table:
            return tuple(downstream_pk_vals)

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
                              downstream_pk_cols, downstream_pk_vals, {})
        for hop in path:
            if row is None:
                return None
            fk_value = row.get(hop['from_column'])
            row = _row_for_table(self.conn, hop['to_table'], hop['to_table'],
                                  [hop['to_column']], [fk_value], {}) if fk_value is not None else None
        if row is None:
            return None
        return tuple(row[c] for c in upstream_pk_cols)


def _resolve_one(conn, case_study, var, node, subject_table, subject_pk_cols, subject_pk_vals,
                  join_paths, runner, decision_name):
    if node.get('kind') == 'literal_via_upstream_branch':
        upstream_decision = node['from_decision']
        upstream_pk_vals = runner.upstream_subject_value(
            upstream_decision, subject_table, subject_pk_cols, subject_pk_vals)
        if upstream_pk_vals is None:
            raise UngroundedForCase(f"{var}: no corresponding {upstream_decision!r} row")
        upstream_result = runner.run(upstream_decision, upstream_pk_vals)
        actual_selected = upstream_result['selected_by_case'].get(tuple(upstream_pk_vals))
        if actual_selected != node['from_rule_id']:
            raise UngroundedForCase(
                f"{var}: upstream {upstream_decision!r} selected {actual_selected!r}, "
                f"not the required {node['from_rule_id']!r}")
        return resolve(conn, node['value'], subject_table, subject_pk_cols, subject_pk_vals, join_paths).value

    if node.get('kind') == 'substituted_decision':
        free_values = {}
        for free_var, free_node in node['free_variable_resolutions'].items():
            free_values[free_var] = _resolve_one(
                conn, case_study, free_var, free_node, subject_table, subject_pk_cols,
                subject_pk_vals, join_paths, runner, decision_name)
        return evaluate_expression(node['expression'], free_values)

    return resolve(conn, node, subject_table, subject_pk_cols, subject_pk_vals, join_paths).value


def run_decision(conn, decision_name, records, subject_table, subject_pk_cols,
                  join_paths=None, runner=None, only_case=None):
    """`records` is every compiled objective for this decision (Phase 1,
    via phase1_utility.records_by_decision), used only for their own
    `rule_id`/`condition`/`variable_resolution` -- never for row
    identity. `subject_pk_cols` is always a sequence (single-column PKs
    included). `runner` (a `DecisionRunner`) is required when any
    objective needs an upstream decision's real output; `only_case`
    (a pk-value tuple) restricts enumeration to one subject, used by
    `DecisionRunner` itself, recursively -- a top-level call omits it and
    enumerates every real case. Returns a dict: {
        'matched_by_case': {pk_vals_tuple: [rule_id, ...]},
        'selected_by_case': {pk_vals_tuple: rule_id_or_None},
        'verified_covered_rule_ids': set(),
        'unique_violations': [...],
    }"""
    case_study = records[0]['case_study']
    all_resolutions = {}
    for r in records:
        all_resolutions.update(r['variable_resolution'])

    rules_with_conditions = _rules_with_conditions(records)
    hit_policy = records[0]['hit_policy']

    subject_keys = [tuple(only_case)] if only_case is not None else \
        _distinct_subject_keys(conn, subject_table, subject_pk_cols)

    matched_by_case = {}
    selected_by_case = {}
    verified_covered = set()
    violations = []

    for pk_vals in subject_keys:
        values = {}
        ungrounded = False
        for var, node in all_resolutions.items():
            try:
                values[var] = _resolve_one(conn, case_study, var, node, subject_table,
                                            subject_pk_cols, pk_vals, join_paths or {},
                                            runner, decision_name)
            except UngroundedForCase:
                ungrounded = True
                break
        if ungrounded:
            matched_by_case[pk_vals] = []
            selected_by_case[pk_vals] = None
            continue
        try:
            matched, selected = select_rule(hit_policy, rules_with_conditions, values)
        except UniqueViolation as e:
            violations.append((pk_vals, e))
            continue
        matched_by_case[pk_vals] = matched
        selected_by_case[pk_vals] = selected
        if selected:
            verified_covered.add(selected)

    return {
        'matched_by_case': matched_by_case,
        'selected_by_case': selected_by_case,
        'verified_covered_rule_ids': verified_covered,
        'unique_violations': violations,
    }


if __name__ == '__main__':
    import os
    import pickle
    import sys

    from phase1_utility import records_by_decision
    from subject_table import subject_table_for_decision

    HERE = os.path.dirname(os.path.abspath(__file__))
    # Only needed to unpickle the archive for THIS demo script's own
    # search-vs-verified comparison printout -- the oracle's actual
    # pipeline (everything above this line) never does this.
    sys.path.insert(0, os.path.join(HERE, '..', 'generator'))
    conn = sqlite3.connect(os.path.join(HERE, 'tests', 'fixtures', 'openmrs_merged.db'))

    decision_name = 'Preferred Identifier Requirement'
    records = records_by_decision('OpenMRS')[decision_name]
    subject_table, pk_cols, join_paths = subject_table_for_decision(records, 'OpenMRS')
    result = run_decision(conn, decision_name, records, subject_table, pk_cols, join_paths=join_paths)

    print(f"{decision_name} -- {len(result['selected_by_case'])} real cases enumerated\n")
    for pk_vals, selected in sorted(result['selected_by_case'].items()):
        print(f"  {pk_cols}={pk_vals}: selected={selected}  matched={result['matched_by_case'][pk_vals]}")

    print(f"\nVerified covered rule IDs: {sorted(result['verified_covered_rule_ids'])}")

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
