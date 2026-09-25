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

from db_resolver import resolve, UnresolvableForCase
from rule_evaluator import evaluate_condition, evaluate_expression, UniqueViolation


def _condition_variable_refs(node):
    """Every `{'kind': 'variable', 'ref': ...}` leaf reachable anywhere
    inside one rule's compiled `condition` tree -- a generic structural
    walk (recurses into every dict value and list item, keyed on nothing
    but `kind == 'variable'`) rather than one hardcoded per operator
    shape (and/or/not/in/between/comparators/arithmetic), so it can't
    silently miss a ref if the condition grammar grows a new operator
    later. Used to fix a real bug (2026-09-25, found investigating why
    `jBilling`'s `Ageing Step Config Validation`, `Is Ageing Required` and
    `Daily Pro-Rate Amount` decisions came back wholesale `unresolved`):
    `variable_resolution` can carry an entry for a variable a rule's own
    `condition` never actually reads (a DMN row's default/catch-all
    variant -- bare `condition: {'kind': 'literal', 'value': true}` --
    still gets the decision's full variable_resolution dict attached,
    unused). `run_decision`'s own per-variant loop used to resolve every
    key in `variable_resolution` unconditionally; if that unused
    variable's own kind is something `db_resolver.resolve` has no case
    for (`code_external`), it raises a bare `NotImplementedError` --
    never caught by this loop's own `UngroundedForCase` handling (that's
    for a per-case data gap, not a structurally-never-resolvable kind),
    so it propagated out of `run_decision` entirely and got caught only
    at the whole-decision level, marking every OTHER rule in that same
    decision unresolved too, even ones (like `Ageing Step Config
    Validation`'s own Rule_1/Rule_2) whose own inputs have nothing wrong
    with them at all."""
    refs = set()

    def walk(n):
        if isinstance(n, dict):
            if n.get('kind') == 'variable' and 'ref' in n:
                refs.add(n['ref'])
            for v in n.values():
                walk(v)
        elif isinstance(n, list):
            for item in n:
                walk(item)

    walk(node)
    return refs


def _distinct_subject_keys(conn, subject_table, pk_cols):
    cols_sql = ', '.join(f'"{c}"' for c in pk_cols)
    cur = conn.execute(f'SELECT DISTINCT {cols_sql} FROM "{subject_table}"')
    return [row for row in cur.fetchall()]


def _rules_with_conditions(records):
    """One condition per DISTINCT rule_id, in real document order, kept
    ONLY by first occurrence. Correction (2026-09-24): a decision CAN
    have several objectives sharing one rule_id with DIFFERENT own
    conditions/variable_resolution -- one per upstream branch it could be
    chained on (DRD fan-out; see compile_constraints.py's own
    `_grounding_options`), not the same condition as this function's own
    docstring used to (wrongly) assert. `run_decision` no longer uses
    this function for evaluation (it now tries every variant of a
    rule_id independently -- see its own docstring); this helper remains
    only for `coverage.py`'s own cosmetic per-rule index lookup
    (`rule_index_by_id`), where picking one arbitrary variant's index is
    harmless."""
    seen_rules = {}
    for r in records:
        if r['rule_id'] not in seen_rules:
            seen_rules[r['rule_id']] = r['condition']
    return [(rid, i, cond) for i, (rid, cond) in enumerate(seen_rules.items())]


def _rule_outputs(records):
    """{rule_id: {output_name: value}} -- every rule's own declared
    output, for `decision_trace.json`'s own `decision_output` field
    (spec item C/F: coverage must be identified by rule ID, never by
    output value, since two different rules CAN share an output --
    tracking the output value here is for inspection only, never used
    anywhere in rule SELECTION, which only ever compares conditions).
    Every output seen across every real record so far is a plain
    literal; a non-literal output raises rather than guessing its
    value."""
    outputs_by_rule = {}
    for r in records:
        if r['rule_id'] in outputs_by_rule:
            continue
        values = {}
        for name, node in r.get('outputs', {}).items():
            if node.get('kind') != 'literal':
                raise NotImplementedError(
                    f"Rule {r['rule_id']!r} output {name!r} is not a literal "
                    f"(kind={node.get('kind')!r}) -- not yet supported")
            values[name] = node['value']
        outputs_by_rule[r['rule_id']] = values
    return outputs_by_rule


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

    def __init__(self, conn, case_study, records_by_decision, subject_tables,
                 not_persisted_overrides=None):
        self.conn = conn
        self.case_study = case_study
        self.records_by_decision = records_by_decision
        # {decision_name: (subject_table, pk_cols, join_paths)}, pre-derived
        # by the caller via subject_table.subject_table_for_decision for
        # every decision this run might need to chain into.
        self.subject_tables = subject_tables
        self.not_persisted_overrides = not_persisted_overrides
        self._cache = {}  # {(decision_name, subject_pk_vals): run_decision() result}

    def run(self, decision_name, subject_pk_vals):
        key = (decision_name, tuple(subject_pk_vals))
        if key not in self._cache:
            records = self.records_by_decision[decision_name]
            subject_table, pk_cols, join_paths = self.subject_tables[decision_name]
            self._cache[key] = run_decision(
                self.conn, decision_name, records, subject_table, pk_cols,
                join_paths=join_paths, runner=self, only_case=subject_pk_vals,
                not_persisted_overrides=self.not_persisted_overrides)
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
            # `hop['from_column']` carries the schema's own declared casing
            # (uppercase), but `_row_for_table`'s own returned dict keys
            # are lowercase (real SQLite column names, same convention
            # `db_resolver.py`'s own single-decision join-hop walk already
            # normalizes for via this exact `.lower()` -- this cross
            # -decision copy of the same pattern omitted it, so every
            # lookup silently missed and returned None, misreported as "no
            # corresponding upstream row" rather than a real case never
            # reached (confirmed directly against FLEX2's own real fixture
            # data, 2026-09-24).
            if 'from_columns' in hop:
                # A composite-key hop (`schema_utility.composite_backward_edges`)
                # -- same casing gap as the single-column case below.
                fk_values = [row.get(c.lower()) for c in hop['from_columns']]
                row = _row_for_table(self.conn, hop['to_table'], hop['to_table'],
                                      hop['to_columns'], fk_values, {}) \
                    if all(v is not None for v in fk_values) else None
            else:
                fk_value = row.get(hop['from_column'].lower())
                row = _row_for_table(self.conn, hop['to_table'], hop['to_table'],
                                      [hop['to_column']], [fk_value], {}) if fk_value is not None else None
        if row is None:
            return None
        # Same casing gap as `hop['from_column']` above -- `upstream_pk_cols`
        # carries the schema's own declared casing, `row`'s keys are the
        # real lowercase SQLite column names.
        return tuple(row[c.lower()] for c in upstream_pk_cols)


def _resolve_one(conn, case_study, var, node, subject_table, subject_pk_cols, subject_pk_vals,
                  join_paths, runner, decision_name, trace=None, not_persisted_overrides=None):
    if node.get('kind') == 'not_persisted':
        overrides = not_persisted_overrides or {}
        if var not in overrides:
            raise NotImplementedError(
                f"not_persisted variable {var!r} has no declared override -- pass "
                f"not_persisted_overrides={{{var!r}: <value>}} explicitly, disclosed, "
                f"never read from search state (see DESIGN.md known gaps)")
        result = resolve(conn, node, subject_table, subject_pk_cols, subject_pk_vals,
                          join_paths, declared_not_persisted_value=overrides[var], case_study=case_study)
        if trace is not None:
            trace[var] = {'value': result.value, 'resolution_type': result.resolution_type,
                          'source_table': None}
        return result.value

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
        try:
            result = resolve(conn, node['value'], subject_table, subject_pk_cols, subject_pk_vals, join_paths,
                              case_study=case_study)
        except UnresolvableForCase as e:
            raise UngroundedForCase(f"{var}: {e}")
        if trace is not None:
            trace[var] = {'value': result.value, 'resolution_type': 'literal_via_upstream_branch',
                          'source_table': None, 'upstream_decision': upstream_decision,
                          'upstream_selected_rule': actual_selected}
        return result.value

    if node.get('kind') == 'substituted_decision':
        free_values = {}
        for free_var, free_node in node['free_variable_resolutions'].items():
            free_values[free_var] = _resolve_one(
                conn, case_study, free_var, free_node, subject_table, subject_pk_cols,
                subject_pk_vals, join_paths, runner, decision_name, trace, not_persisted_overrides)
        value = evaluate_expression(node['expression'], free_values)
        if trace is not None:
            trace[var] = {'value': value, 'resolution_type': 'substituted_decision',
                          'source_table': None, 'free_variables': free_values}
        return value

    try:
        result = resolve(conn, node, subject_table, subject_pk_cols, subject_pk_vals, join_paths,
                          case_study=case_study)
    except UnresolvableForCase as e:
        raise UngroundedForCase(f"{var}: {e}")
    if trace is not None:
        trace[var] = {'value': result.value, 'resolution_type': result.resolution_type,
                      'source_table': result.source_table}
    return result.value


def run_decision(conn, decision_name, records, subject_table, subject_pk_cols,
                  join_paths=None, runner=None, only_case=None, collect_trace=False,
                  not_persisted_overrides=None):
    """`records` is every compiled objective for this decision (Phase 1,
    via phase1_utility.records_by_decision), used only for their own
    `rule_id`/`condition`/`variable_resolution` -- never for row
    identity. `subject_pk_cols` is always a sequence (single-column PKs
    included). `runner` (a `DecisionRunner`) is required when any
    objective needs an upstream decision's real output; `only_case`
    (a pk-value tuple) restricts enumeration to one subject, used by
    `DecisionRunner` itself, recursively -- a top-level call omits it and
    enumerates every real case. `collect_trace=True` additionally
    populates `'trace'` in the return value: {pk_vals_tuple:
    {'resolved_inputs': {var: {value, resolution_type, source_table}},
    'matched_rule_ids', 'selected_rule_id'}} -- for `coverage.py`'s own
    `decision_trace.json`; off by default since most callers (including
    `DecisionRunner`'s own recursive upstream runs) don't need it.
    `not_persisted_overrides` is an explicit, disclosed {var_name: value}
    a caller supplies for any `not_persisted` variable this decision
    needs -- never derived from search state; a `not_persisted` variable
    with no matching entry here raises (see `_resolve_one`), it is never
    silently treated as covered.

    A rule_id can appear on several of `records`' own entries with
    DIFFERENT condition/variable_resolution (DRD fan-out variants, one
    per upstream branch it could be chained on). Each real case tries
    EVERY variant of EVERY rule_id independently, never a merged union
    of their variable_resolution (that previously collapsed all variants
    to one arbitrary definition -- a real bug, fixed 2026-09-24, that
    silently mis-evaluated any decision with more than one variant per
    rule_id). A variant whose own resolution raises `UngroundedForCase`
    (or a per-row data gap such as `derived_case` hitting an
    uncovered real value, translated to the same exception by
    `_resolve_one`) simply does not count as matched for that variant;
    other variants of the same rule_id, and every other rule_id, are
    still tried for this same real case -- a resolution failure no
    longer aborts the WHOLE decision for that case (a second real bug,
    fixed alongside the first).
    Returns a dict: {
        'matched_by_case': {pk_vals_tuple: [rule_id, ...]},
        'selected_by_case': {pk_vals_tuple: rule_id_or_None},
        'verified_covered_rule_ids': set(),
        'unique_violations': [...],
        'trace': {...} (only if collect_trace),
    }"""
    case_study = records[0]['case_study']
    rule_outputs = _rule_outputs(records) if collect_trace else None
    hit_policy = records[0]['hit_policy']

    # A decision can have several compiled records sharing the SAME
    # rule_id but DIFFERENT condition/variable_resolution -- one per
    # upstream branch it could be chained on (DRD fan-out; see
    # compile_constraints.py's own `_grounding_options`). Group by
    # rule_id, preserving first-appearance document order (needed for
    # FIRST hit policy), and try EACH variant independently per real
    # case -- never merge variants' own variable_resolution/condition
    # together (that silently collapsed to one arbitrary variant's own
    # definition for the whole decision, a real bug fixed 2026-09-24).
    # A rule_id counts as matched for a case if ANY of its own variants
    # both grounds (no UngroundedForCase) and evaluates true.
    variants_by_rule_id = {}
    for r in records:
        variants_by_rule_id.setdefault(r['rule_id'], []).append(r)
    ordered_rule_ids = list(variants_by_rule_id.keys())

    subject_keys = [tuple(only_case)] if only_case is not None else \
        _distinct_subject_keys(conn, subject_table, subject_pk_cols)

    matched_by_case = {}
    selected_by_case = {}
    verified_covered = set()
    violations = []
    trace_by_case = {} if collect_trace else None

    for pk_vals in subject_keys:
        # A FEEL today() call can appear directly as a condition operand
        # (rule_evaluator._eval_operand), not routed through
        # variable_resolution's own not_persisted at all -- reuses the
        # SAME disclosed not_persisted_overrides dict, under the SAME
        # '__today__' key generator/candidate.py's own convention uses,
        # rather than a separate parameter.
        base_values = {}
        if not_persisted_overrides and '__today__' in not_persisted_overrides:
            base_values['__today__'] = not_persisted_overrides['__today__']

        matched = []
        # Diagnostic-only merge of every variant that successfully
        # grounded for this case, across every rule_id tried (last write
        # wins on a variable name shared by two variants with DIFFERENT
        # own resolutions -- e.g. two "via" variants of the same free
        # variable name under different upstream-branch assumptions).
        # Never used for matched/selected correctness, which is decided
        # per-variant below, independently.
        overall_var_trace = {} if collect_trace else None
        any_variant_grounded = False

        for rule_id in ordered_rule_ids:
            rule_matched = False
            for variant in variants_by_rule_id[rule_id]:
                values = dict(base_values)
                var_trace = {} if collect_trace else None
                ungrounded = False
                needed_vars = _condition_variable_refs(variant['condition'])
                for var, node in variant['variable_resolution'].items():
                    if var not in needed_vars:
                        # Declared on this rule variant but never actually
                        # read by ITS OWN condition (see
                        # _condition_variable_refs's own docstring) --
                        # resolving it anyway risks an unrelated
                        # structurally-unresolvable kind (code_external et
                        # al.) aborting this whole decision for every rule,
                        # over a variable this specific variant never
                        # needed an answer for.
                        continue
                    try:
                        values[var] = _resolve_one(conn, case_study, var, node, subject_table,
                                                    subject_pk_cols, pk_vals, join_paths or {},
                                                    runner, decision_name, var_trace, not_persisted_overrides)
                    except UngroundedForCase:
                        ungrounded = True
                        break
                if ungrounded:
                    continue  # this variant doesn't apply to this real case; try the next one
                any_variant_grounded = True
                if collect_trace:
                    overall_var_trace.update(var_trace)
                if evaluate_condition(variant['condition'], values):
                    rule_matched = True
                    break  # one grounded+true variant is enough for this rule_id
            if rule_matched:
                matched.append(rule_id)

        if hit_policy == 'FIRST':
            selected = matched[0] if matched else None
        elif hit_policy == 'UNIQUE':
            if len(matched) > 1:
                violations.append((pk_vals, UniqueViolation(decision_name, matched)))
                continue
            selected = matched[0] if matched else None
        else:
            raise NotImplementedError(f"Hit policy {hit_policy!r} not yet supported "
                                       f"(only FIRST/UNIQUE, matching this project's own scope)")

        matched_by_case[pk_vals] = matched
        selected_by_case[pk_vals] = selected
        if selected:
            verified_covered.add(selected)
        if collect_trace:
            trace_by_case[pk_vals] = {
                'resolved_inputs': overall_var_trace, 'matched_rule_ids': matched,
                'selected_rule_id': selected, 'ungrounded': not any_variant_grounded,
                'decision_output': rule_outputs.get(selected) if selected else None,
            }

    result = {
        'matched_by_case': matched_by_case,
        'selected_by_case': selected_by_case,
        'verified_covered_rule_ids': verified_covered,
        'unique_violations': violations,
    }
    if collect_trace:
        result['trace'] = trace_by_case
    return result


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
