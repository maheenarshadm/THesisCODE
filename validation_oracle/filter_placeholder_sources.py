"""Explicit, DISCLOSED human overrides naming which table a `filter_text`
`<placeholder>` actually comes from, when it is NOT a same-named column
on the SUBJECT row itself -- same status/precedent as
`join_disambiguation.py` and `supplementary_fk_edges.py`: a researcher's
domain-knowledge call, made explicit and inspectable here, never
silently guessed.

`db_resolver._resolve_placeholders` tries the subject row first, exactly
as before this file existed -- every placeholder already resolvable that
way (jBilling's `entity_id`/`status_id`, Spree's own
`price_list_id`/`user_id`/`email`) is completely unaffected, since none
of them has an entry here. Only when a placeholder is NOT found on the
subject row does it consult this table; a placeholder with no override
here and no subject-row column still raises exactly as before (never a
silent guess).

Naming the SOURCE table here is only half the job -- `subject_table.py`'s
`tables_referenced()` also lists this table so the decision's own root-
picking and join-path construction (`schema_utility.build_join_path`,
completely unmodified) include it, and `_resolve_placeholders` then reads
the real value off the ALREADY-JOINED row via the SAME `_row_for_table`
hop-walker every other cross-table kind already uses -- no new
join-finding logic anywhere.

Format: {(case_study, placeholder_name): table_name}
Table names must match the schema JSON's own canonical casing
(`schema_utility.canonical_table_name`).
"""

FILTER_PLACEHOLDER_SOURCES = {
    ('Spree', 'promotion_id'): 'spree_order_promotions',
    # Case study 'T' is this project's own synthetic test namespace
    # (tests/test_spec_cases.py) -- this entry is exercised only by
    # test_case_11_filter_placeholder_via_join, never by real data.
    ('T', 'region'): 'customer',
}


def get_source_table(case_study, placeholder):
    return FILTER_PLACEHOLDER_SOURCES.get((case_study, placeholder))
