"""A new, separate boolean evaluator over Phase 1's compiled `condition`
tree structure, and FIRST/UNIQUE rule-selection on top of it. Never
imports or calls generator/fitness.py or dynamosa.py's evaluate_objective
-- those compute a continuous FITNESS DISTANCE for search guidance; this
computes a plain True/False match, the different question a coverage
oracle actually needs to answer. Reuses Phase 1's `condition` structure
itself (the declarative parse of a rule's FEEL text) -- the one allowed
exception, same as elsewhere in this package -- not Phase 1's or
fitness.py's own evaluation code.

FIRST/UNIQUE are derived directly from a decision's OWN rule order and
conditions (`dmn_walk.py`'s `Rule.index` + each rule's Phase 1 compiled
`condition`) -- this module does not consume `hit_policy_context`'s own
`earlier_rows` at all, since evaluating every rule in real document
order and taking the first true one is a complete, self-sufficient
implementation of FIRST on its own, independent of how fitness.py
represents the same idea (a suppression-distance sum over earlier rows).
"""


def _eval_operand(node, values):
    kind = node.get('kind')
    if kind == 'variable':
        if node['ref'] not in values:
            raise KeyError(f"condition references {node['ref']!r}, not in resolved values "
                            f"{sorted(values)}")
        return values[node['ref']]
    if kind == 'literal':
        return node['value']
    if 'op' in node:
        return evaluate_expression(node, values)
    raise NotImplementedError(f"Unhandled operand kind {kind!r}: {node!r}")


_ARITHMETIC = {
    '+': lambda a, b: a + b,
    '-': lambda a, b: a - b,
    '*': lambda a, b: a * b,
    '/': lambda a, b: a / b if b else None,
}


def evaluate_expression(expr, values):
    """A `substituted_decision` node's own `expression` tree -- the SAME
    op/left/right/kind shape `condition` uses, but with ARITHMETIC
    operators instead of comparisons (this is a literal-expression
    decision's own formula, inlined; see DESIGN.md's note on literal-
    expression decisions having no rule/hit-policy concept of their
    own). `values` is {var_name: resolved_value} for every free variable
    the expression references, already independently resolved (never
    from search state)."""
    if 'op' not in expr:
        return _eval_operand(expr, values)
    op = expr['op']
    if op in _ARITHMETIC:
        left = _eval_operand(expr['left'], values)
        right = _eval_operand(expr['right'], values)
        return _ARITHMETIC[op](left, right)
    raise NotImplementedError(f"Unhandled expression operator {op!r}: {expr!r}")


def _ordered_compare(op, a, b):
    """FEEL semantics for an ordering comparison: a comparison against
    None, or between incomparable types (e.g. the database holding a
    placeholder string like 'X' in a column another objective's rows
    treat as numeric -- a real, disclosed artifact of this project's own
    merge-time filler values, not a bug in THIS evaluator), is simply
    NOT satisfied -- never an error. This is a defined semantic decision,
    not a silent fallback: it reflects how FEEL itself treats an
    undefined/incomparable comparison, and it is documented here rather
    than swallowed."""
    if a is None or b is None:
        return False
    try:
        return op(a, b)
    except TypeError:
        return False


_COMPARATORS = {
    '=': lambda a, b: a == b,
    '!=': lambda a, b: a != b,
    '>': lambda a, b: _ordered_compare(lambda x, y: x > y, a, b),
    '>=': lambda a, b: _ordered_compare(lambda x, y: x >= y, a, b),
    '<': lambda a, b: _ordered_compare(lambda x, y: x < y, a, b),
    '<=': lambda a, b: _ordered_compare(lambda x, y: x <= y, a, b),
}


def evaluate_condition(condition, values):
    """`condition` is Phase 1's compiled predicate tree; `values` is
    {var_name: resolved_value} for every variable that condition
    references (from `db_resolver.resolve`, never from search state).
    Returns True/False. Raises on an operator this evaluator does not
    yet handle -- never silently treats an unsupported construct as
    covered, per this project's own research constraints."""
    if 'op' not in condition:
        # A default/catch-all rule (every input entry '-') compiles to a
        # bare {'kind': 'literal', 'value': true} with no comparison at
        # all -- confirmed real: OpenMRS's own Numeric Absolute Range
        # Validity::Rule_3. Evaluate it as a plain operand, not an error.
        value = _eval_operand(condition, values)
        if not isinstance(value, bool):
            raise NotImplementedError(
                f"A condition with no 'op' must be a boolean literal, got {value!r}: {condition!r}")
        return value
    op = condition.get('op')
    if op == 'and':
        return all(evaluate_condition(c, values) for c in condition['clauses'])
    if op == 'or':
        return any(evaluate_condition(c, values) for c in condition['clauses'])
    if op in _COMPARATORS:
        left = _eval_operand(condition['left'], values)
        right = _eval_operand(condition['right'], values)
        return _COMPARATORS[op](left, right)
    raise NotImplementedError(f"Unhandled condition operator {op!r}: {condition!r}")


class UniqueViolation(Exception):
    """Raised when a UNIQUE-hit-policy decision has more than one rule
    matching the same case -- a real semantic violation to surface, per
    the original specification, never silently resolved by picking one."""
    def __init__(self, decision_name, matched_rule_ids):
        self.decision_name = decision_name
        self.matched_rule_ids = matched_rule_ids
        super().__init__(f"UNIQUE violation in {decision_name!r}: "
                          f"{len(matched_rule_ids)} rules matched: {matched_rule_ids}")


def select_rule(hit_policy, rules_with_conditions, values):
    """`rules_with_conditions` is [(rule_id, index, condition), ...] in
    document order (dmn_walk.py's own Rule.index). Returns
    (matched_rule_ids, selected_rule_id) -- selected_rule_id is None if
    nothing matched. Raises UniqueViolation for a real UNIQUE conflict
    rather than silently choosing one."""
    matched = [rid for rid, _idx, cond in rules_with_conditions if evaluate_condition(cond, values)]

    if hit_policy == 'FIRST':
        selected = matched[0] if matched else None
        return matched, selected
    if hit_policy == 'UNIQUE':
        if len(matched) > 1:
            raise UniqueViolation(
                rules_with_conditions[0][0].rsplit('_Rule_', 1)[0] if rules_with_conditions else '?',
                matched)
        selected = matched[0] if matched else None
        return matched, selected
    raise NotImplementedError(f"Hit policy {hit_policy!r} not yet supported "
                               f"(only FIRST/UNIQUE, matching this project's own scope)")


if __name__ == '__main__':
    import json
    import os
    import sqlite3

    from db_resolver import resolve

    HERE = os.path.dirname(os.path.abspath(__file__))
    conn = sqlite3.connect(os.path.join(HERE, 'tests', 'fixtures', 'openmrs_merged.db'))
    compiled = json.load(open(os.path.join(HERE, '..', 'generator', 'compiled_constraints.json')))
    recs = {r['rule_id']: r for r in compiled
            if r['case_study'] == 'OpenMRS' and r['decision_name'] == 'Preferred Identifier Requirement'}
    rules_with_conditions = [(rid, i, r['condition']) for i, (rid, r) in enumerate(recs.items())]

    # Different rules of the same decision can reference different
    # subsets of its variables (a rule's own compiled record only
    # resolves what ITS OWN condition mentions) -- union across every
    # rule's own variable_resolution, not just one.
    all_resolutions = {}
    for r in recs.values():
        all_resolutions.update(r['variable_resolution'])

    for pk in (34000001, 35000001, 36000001):
        values = {}
        for var, node in all_resolutions.items():
            values[var] = resolve(conn, node, 'patient_identifier', 'patient_identifier_id', pk).value
        matched, selected = select_rule('FIRST', rules_with_conditions, values)
        print(f"patient_identifier_id={pk}  values={values}")
        print(f"  matched={matched}  selected={selected}")
