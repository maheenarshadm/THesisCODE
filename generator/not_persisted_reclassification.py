"""Disclosed override for a variable the ground-truth CSV buckets as
`not-persisted` whose OWN notes/raw_schema_field text actually names a
real, queryable table -- the same class of mis-mapping this project
already found and fixed for FLEX2's `purchaseQuantity`/`semesterType`
(see KNOWN_ISSUES.md), just caught in the `not_persisted` bucket
instead of `direct`. Mirrors `literal_expression_overrides.py`'s own
precedent: the ground truth's own bucket/label is kept as `notes` on
the replacement node rather than silently corrected in the CSV itself,
since this is the source data's own labeling, not this compiler's
judgment call -- but the compiled resolution actually used is the real
one, not the mis-labeled `not_persisted`.

Found real, not hypothetical: jBilling's `Tax Calculation Needed::
customContactFieldConfigured`. `variable_to_schema_mapping.csv` labels
it `not-persisted` with raw_schema_field "n/a (plugin param
custom_contact_field_id)" and notes "A pluggable_task_parameter
configuration value, not a row in a business table." But
`pluggable_task_parameter` IS a real, queryable table in jBilling's own
schema (confirmed directly against
all_schema_extraction/output/jbilling_schema_full.json: columns `id`,
`task_id`, `int_value`, `optlock`, `name`, `str_value`, `float_value`,
real FK `task_id -> pluggable_task.id`) -- a real business-configuration
table, not a Java-only/transient value. The DMN's own rule descriptions
confirm the semantics: Rule_1's description reads "no
custom_contact_field_id plugin parameter configured -> tax is always
calculated" (Proration_and_Tax.dmn / build_jbilling_dmn.py), i.e. this
is a GLOBAL, system-wide "has this plugin parameter been configured at
all" check -- not per-customer/per-entity -- matching an `exists` query
against `pluggable_task_parameter` filtered by
`name = 'custom_contact_field_id'` with no subject correlation needed
(the parameter's name is the one disclosed, cited identifier this
project already has -- from BOTH the DMN description text and
build_jbilling_mapping.py's own schema-mapping tuple -- not a guessed
string).

This is a GLOBAL fact (same value for every candidate row), which
`db_resolver.resolve`'s own `exists`-with-`filter_text` branch already
supports directly: a `filter_text` with no `<placeholder>` or `self`
token needs no join path at all, executing the identical
`SELECT EXISTS(SELECT 1 FROM "pluggable_task_parameter" WHERE
name = 'custom_contact_field_id')` for every subject row -- a real,
disclosed simplification, not a fabricated per-row correlation.
"""

_RECLASSIFICATIONS = {
    ('jBilling', 'customContactFieldConfigured'): {
        'kind': 'exists',
        'candidate_tables': ['pluggable_task_parameter'],
        'candidate_columns': [],
        'filter_text': "name = 'custom_contact_field_id'",
        'notes': (
            "ground truth labeled this 'not-persisted' ('A pluggable_task_parameter "
            "configuration value, not a row in a business table'), but "
            "pluggable_task_parameter is a real table in jBilling's own schema; "
            "reclassified as a global exists-check, see "
            "not_persisted_reclassification.py for the full disclosure"
        ),
    },
}


def get_reclassification(case_study, var_name):
    """Returns a full replacement resolution node for (case_study,
    var_name), or None if this variable's own `not_persisted`
    classification is genuinely correct (the common case)."""
    override = _RECLASSIFICATIONS.get((case_study, var_name))
    return dict(override) if override else None
