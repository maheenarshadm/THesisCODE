"""Explicit, DISCLOSED human overrides for a literal-expression decision's
own FEEL formula, when `feel_parser.py` cannot parse it into a real
expression tree (falls back to an `opaque_formula` node) -- same status
as this project's own `[ASSUMED...]`-marked ground-truth rows and
`validation_oracle/join_disambiguation.py`'s join overrides: a
researcher's hand-translation of the formula's real intent into the
SAME `{expression, free_variable_resolutions}` shape
`compile_constraints.resolve_and_substitute` would have built itself
from a successful parse, made explicit and inspectable here rather than
silently guessed or left as an unevaluable `opaque_formula` node.

Each override supplies the two pieces `resolve_and_substitute` normally
derives from a real parse:
- `expression`: a FEEL expression tree using ONLY node kinds
  `rule_evaluator._eval_operand`/`fitness.evaluate_expression` already
  handle (comparisons, `variable`, `literal`, `and`/`or`/`not`, `call`
  with a recognized name) -- never `opaque_formula`.
- `free_variable_resolutions`: {name: variable_resolution node} for
  every free variable `expression` references, resolved the same way
  any other ground-truth variable is (so it reuses `derived_aggregate`/
  `exists`/etc.'s own already-proven runtime machinery, never a new
  evaluation path).

`compile_constraints.resolve_and_substitute` consults this BEFORE
calling `feel_parser.parse_expression` on a literal-expression decision;
a decision with no override here still goes through the real parser as
before, and an unparseable formula with no override is still `unresolved`
(no default fallback that could silently produce a wrong formula).

Format: {(case_study, decision_name): {'expression': ..., 'free_variable_resolutions': {...}}}
"""

# Spree's "Prior Completed Order Count" is a literal-expression decision
# whose real DMN formula is a FEEL list comprehension --
# `count(order for order in store.orders where (order.customer = customer
# or order.email = email) and order.state = "complete" and order !=
# currentOrder)` -- a construct feel_parser.py does not parse (the
# comprehension's own body becomes an `opaque_formula` node, which no
# evaluator can execute; confirmed the actual blocking error downstream,
# "Unhandled operand kind 'call'" wrapping that opaque node).
#
# Translated by hand into the equivalent real-column query: COUNT of
# spree_orders rows belonging to the same customer (matched by EITHER
# user_id or email, mirroring the formula's own `or`), that are complete,
# excluding the current order itself. Two disclosed interpretation calls,
# neither verified against a real sample row:
#   1. "order.state = \"complete\"" is re-expressed as
#      `completed_at IS NOT NULL` -- this schema's own extracted columns
#      have no bare `state`/`status` value that reads "complete"
#      (only `shipment_state`/`payment_state`/`status`), while
#      `completed_at` is a real, dedicated timestamp column matching
#      Spree's own well-known convention that an order becomes complete
#      exactly when this column is set.
#   2. "order != currentOrder" is re-expressed as `id != self` -- the
#      formula's own `currentOrder` is this decision's own subject row
#      (spree_orders, confirmed via `userOrEmailPresent`'s own
#      resolution onto the same table), so `self` (this validator's own
#      existing exclude-self convention, already used by Spree's
#      `Price Adjustment Tier Validity Violations::siblingTierCount`) is
#      the correct, already-supported way to express it -- no new
#      db_resolver.py mechanism needed.
# [ASSUMED -- hand-translated from the DMN's own literalExpression text,
# not verified against a real sample spree_orders row; researcher
# interpretation for evaluation-coverage purposes, 2026-09-24]
_PRIOR_COMPLETED_ORDER_COUNT = {
    'expression': {'kind': 'variable', 'ref': '__prior_completed_order_count'},
    'free_variable_resolutions': {
        '__prior_completed_order_count': {
            'kind': 'derived_aggregate',
            'aggregate': 'COUNT',
            'table': 'spree_orders',
            'filter_text': 'user_id = <user_id> AND completed_at IS NOT NULL AND id != self',
            'notes': ('[ASSUMED -- see literal_expression_overrides.py\'s own module '
                      'docstring for the full disclosure] hand-translated from the FEEL '
                      'list comprehension feel_parser.py cannot parse; completed_at IS NOT '
                      'NULL stands in for the formula\'s own order.state = "complete", the '
                      'schema\'s real completion signal since no bare state/status column '
                      'reads "complete". A SECOND disclosed narrowing, added 2026-09-24: '
                      'dropped the formula\'s own "OR email = <email>" guest-checkout '
                      'alternative -- (A OR B) is a shape neither '
                      '_mechanical_filter_predicate nor _row_from_filter_conjuncts '
                      '(generator/candidate.py, generator/mutation.py) understands at all '
                      '(both only recognize a flat AND of single-column conjuncts), so the '
                      'whole parenthesized clause was previously skipped entirely -- no '
                      'user_id OR email constraint ever actually applied to a seeded/mutated '
                      '"prior order" row, which is what let the search claim '
                      'First-Order Promotion Eligibility::rule_3 covered from its very first '
                      'seeded candidate while the real validator (correctly requiring an '
                      'actual matching user_id) disagreed. Matching by user_id alone is a '
                      'real, narrower subset of the formula\'s true "identified by user OR '
                      'email" semantics (loses the guest-checkout-by-email path), not a guess '
                      'at missing schema -- the same kind of narrowing already disclosed for '
                      'adjustedCreditsCount.'),
        },
    },
}

LITERAL_EXPRESSION_OVERRIDES = {
    ('Spree', 'Prior Completed Order Count'): _PRIOR_COMPLETED_ORDER_COUNT,
}


def get_override(case_study, decision_name):
    return LITERAL_EXPRESSION_OVERRIDES.get((case_study, decision_name))
