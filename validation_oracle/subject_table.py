"""Derives each decision's SUBJECT TABLE -- the table whose rows
represent "one case" to enumerate when independently validating that
decision -- from Phase 1's own `variable_resolution` metadata
(`phase1_utility.py`), never from search-time row tagging. See
DESIGN.md's "No anchoring, no search-time tagging" section for why this
exists and what it replaces.

Current scope, disclosed rather than silently assumed: handles decisions
where every input resolves against a SINGLE table (confirmed true of
OpenMRS's Preferred Identifier Requirement, this validator's first real
target). A genuinely multi-table decision -- inputs spanning more than
one table with no single common one -- is NOT yet handled; `subject_table_for`
raises rather than guessing a join strategy, per this project's own
research constraint against silent fallbacks. Extending this to real
multi-table decisions is open work (see DESIGN.md's open issues).

Note on `chained_decision_output`: this kind name appears in DESIGN.md's
own text but does NOT occur anywhere in the current compiled_constraints.json
(confirmed by direct search) -- by the time compilation finishes, an
upstream-decision-dependent value is resolved into either
`literal_via_upstream_branch` (a literal value known from a specific
upstream rule) or `substituted_decision` (an expression over upstream
free variables). Both are handled here as "no direct table -- needs the
upstream decision's real output," not as a table reference.
"""

# Resolution kinds that read one or more tables directly. Maps kind ->
# a function extracting the set of table names it references.
_TABLE_EXTRACTORS = {
    'schema_column': lambda n: {n['table']},
    'null_check': lambda n: {n['table']},
    'derived_case': lambda n: {n['table']},
    'derived_aggregate': lambda n: {n['table']},
    'derived_join_count': lambda n: {n['prereq_table'], n['registration_table']},
    'exists': lambda n: set(n['candidate_tables']),
    'raw_sql_boolean': lambda n: set(n['tables']),
    'any_not_null': lambda n: {c['table'] for c in n['columns']},
    'join_lookup': lambda n: {n['via']['local_table'], n['result_table']},
    'join_null_check': lambda n: {n['via']['local_table'], n['result_table']},
    'regex_match': lambda n: {n['value_column']['table'], n['pattern_column']['table']},
}

# Resolution kinds that do NOT read a table directly -- either a fixed
# value, an upstream decision's own output (handled by drd_executor.py,
# not a table lookup), or a genuinely non-database value.
_NON_TABLE_KINDS = {
    'literal', 'literal_via_upstream_branch', 'substituted_decision',
    'not_persisted', 'code_external', 'schema_gap', 'unresolved', 'variable',
}


def tables_referenced(node):
    """Every table one `variable_resolution` node reads directly. Empty
    set for a non-table kind (see `_NON_TABLE_KINDS`) -- NOT an error;
    the caller must check kind, not assume an empty set means failure."""
    kind = node.get('kind')
    if kind in _TABLE_EXTRACTORS:
        return _TABLE_EXTRACTORS[kind](node)
    if kind in _NON_TABLE_KINDS:
        return set()
    if kind == 'substituted_decision':
        tables = set()
        for sub_node in node.get('free_variable_resolutions', {}).values():
            tables |= tables_referenced(sub_node)
        return tables
    raise ValueError(f"Unrecognized variable_resolution kind {kind!r} -- "
                      f"fail loudly rather than silently skip (node={node!r})")


def subject_table_for_decision(records):
    """`records` is every compiled objective for ONE decision (from
    `phase1_utility.records_by_decision`). Returns the single subject
    table name if every input across every objective resolves against
    exactly one common table; raises otherwise, naming what was found,
    rather than guessing which table is "the" subject."""
    all_tables = set()
    for r in records:
        for node in r.get('variable_resolution', {}).values():
            all_tables |= tables_referenced(node)

    if len(all_tables) == 0:
        raise ValueError(
            f"No table-backed inputs found for decision {records[0]['decision_name']!r} -- "
            f"every input is non-table-backed (literal/upstream/not_persisted); "
            f"this decision cannot be independently entity-enumerated from the database alone.")
    if len(all_tables) > 1:
        raise ValueError(
            f"Decision {records[0]['decision_name']!r} references multiple tables "
            f"{sorted(all_tables)} -- multi-table subject-table derivation is not yet "
            f"implemented (see validation_oracle/DESIGN.md open issues); refusing to guess.")
    return next(iter(all_tables))


if __name__ == '__main__':
    from phase1_utility import records_by_decision

    for decision_name, records in records_by_decision('OpenMRS').items():
        try:
            subject = subject_table_for_decision(records)
            print(f"{decision_name!r} -> subject table: {subject}")
        except ValueError as e:
            print(f"{decision_name!r} -> UNRESOLVED: {e}")
