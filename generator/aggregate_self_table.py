"""Explicit, DISCLOSED table binding for the `self` token inside a
`derived_aggregate`'s own `filter_text`, when that filter_text contains a
nested `COLUMN IN (SELECT ... WHERE ... self ...)` subquery -- same
status as `join_disambiguation.py`/`supplementary_fk_edges.py`/
`filter_placeholder_sources.py`: a researcher's disclosed, reviewable
judgment call, never a silent guess.

`self` always means "the decision's own subject row's primary key" --
the SAME convention `validation_oracle/db_resolver.py`'s own
`_substitute_self_and_colon` already uses at verification time. The
validator gets this for free (it's handed `subject_table`/`subject_pk_vals`
explicitly by `subject_table_for_decision`); the GENERATOR side has no
equivalent per-record "subject table" computation, so it's named
explicitly here instead of inferred (inference would mean guessing which
of a record's several focal tables is "the" subject -- exactly the kind
of guess this project's own discipline refuses to make silently).

Format: {(case_study, variable_name): table_name}. Consulted once, at
compile time (`compile_constraints.py`'s own `resolve_variable`), and
baked into the compiled node as `self_table` -- so every runtime
consumer (`candidate.py`, `mutation.py`) just reads `node['self_table']`
directly, never re-deriving or re-guessing it.
"""

# Spree's `adjustedCreditsCount` (Promotion Usage Limit Exceeded):
# `COUNT(spree_discounts) WHERE promotion_action_id IN (SELECT id FROM
# spree_promotion_actions WHERE promotion_id = self) AND 1=1` -- this
# decision's own OTHER facts (usageLimitSet/usageLimit) read
# spree_promotions, confirming that's the decision's real subject.
_SELF_REFERENCE_TABLE = {
    ('Spree', 'adjustedCreditsCount'): 'spree_promotions',
}


def get_self_table(case_study, var_name):
    return _SELF_REFERENCE_TABLE.get((case_study, var_name))
