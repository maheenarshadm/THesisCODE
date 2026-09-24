"""Explicit, DISCLOSED human-supplied foreign-key edges for tables whose
REAL foreign keys were not captured by all_schema_extraction/ -- same
status as `join_disambiguation.py`'s own overrides, but for a MISSING
edge rather than an AMBIGUOUS one between several real edges.

Spree's own schema extraction has an already-disclosed limitation
(fitness.py's own module comment: "Spree's original migration-history
source is not available"): several of its join/association tables carry
real foreign keys by Rails convention and column naming
(`order_id`/`promotion_id`, ...) that the extractor's own `fk_columns`
list is simply empty for -- confirmed directly for `spree_order_promotions`
and `spree_promotion_rules`, both `fk_columns: []` in the extracted
schema JSON despite each having an unambiguous, real, singular target.

`schema_utility.fk_edges` consults this to SUPPLEMENT (never replace)
whatever the schema JSON itself declares -- an edge named here is
additional to any the extractor did find, never a correction of one it
got wrong (that is `join_disambiguation.py`'s own, separate job).

Format: {(case_study, table): [{'column', 'ref_table', 'ref_column', 'reason'}, ...]}
Table names must match the schema JSON's own canonical casing
(`schema_utility.canonical_table_name`).
"""

SUPPLEMENTARY_FK_EDGES = {
    ('Spree', 'spree_order_promotions'): [
        {'column': 'order_id', 'ref_table': 'spree_orders', 'ref_column': 'id',
         'reason': ("spree_order_promotions is Spree's own real order<->promotion join table "
                    "(order_id, promotion_id, no other columns beyond timestamps) -- an "
                    "unambiguous, singular FK by Rails convention and column naming, missing "
                    "from the extracted schema's own fk_columns (empty list) purely because "
                    "Spree's migration-history source was unavailable to the extractor, not "
                    "because the relationship is actually ambiguous or uncertain.")},
        {'column': 'promotion_id', 'ref_table': 'spree_promotions', 'ref_column': 'id',
         'reason': "same table, same extraction gap, other half of the join -- see order_id above."},
    ],
    ('Spree', 'spree_promotion_rules'): [
        {'column': 'promotion_id', 'ref_table': 'spree_promotions', 'ref_column': 'id',
         'reason': ("spree_promotion_rules.promotion_id is the rule's own owning promotion -- "
                    "same extraction gap as spree_order_promotions above (fk_columns: [] despite "
                    "an unambiguous, real, singular target).")},
    ],
}


def get_supplementary_edges(case_study, table):
    return SUPPLEMENTARY_FK_EDGES.get((case_study, table), [])
