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


def _pick_root(case_study, all_tables, closure_tables):
    """The ROOT is whichever table can reach EVERY directly-referenced
    table (`all_tables`) via a forward FK join path within the decision's
    own fk_closure (`schema_utility.build_join_path` -- real multi-hop
    BFS). Candidates are drawn from `closure_tables`, NOT just
    `all_tables` -- a decision's own inputs may reference no common
    table directly, while a genuine JUNCTION table elsewhere in the
    closure (never itself read by any input) has forward FKs to every
    one of them. Confirmed real, not hypothetical: FLEX2's `Course Load
    Limit` reads only STUDENT_PROGRAM and SEMESTER, which have no FK
    between them at all -- but STUDENT_SEMESTER (in the same decision's
    own fk_closure_tables, referenced by no input) has forward FKs to
    BOTH. Requires EXACTLY ONE table (from the closure OR from
    all_tables itself) to have this reach-everything property; more than
    one (genuine ambiguity between candidate junction tables) or none is
    refused, not guessed."""
    from schema_utility import build_join_path

    candidate_pool = closure_tables | all_tables
    candidates = []
    for root in candidate_pool:
        if all(build_join_path(case_study, root, t, closure_tables) is not None for t in all_tables - {root}):
            candidates.append(root)

    if len(candidates) != 1:
        raise ValueError(
            f"Cannot pick a unique root reaching {sorted(all_tables)} among the closure: "
            f"{len(candidates)} candidate(s) qualify ({sorted(candidates)}) -- "
            f"need exactly 1. Refusing to guess.")
    return candidates[0]


def subject_table_for_decision(records, case_study):
    """`records` is every compiled objective for ONE decision (from
    `phase1_utility.records_by_decision`). Returns
    (subject_table, subject_pk_columns, join_paths) --
    `subject_pk_columns` is the subject table's own real PK column list
    (`schema_utility.pk_columns`, always a list even for a single-column
    PK); `join_paths` is {other_table: [hop, ...]} from
    `schema_utility.build_join_path`, for every table this decision's
    inputs directly reference OTHER than the subject table itself
    (which may not be any of them -- see `_pick_root`). Raises, naming
    what was found, rather than guessing, when no unique root can be
    identified."""
    from schema_utility import build_join_path, pk_columns

    all_tables = set()
    closure_tables = set()
    for r in records:
        closure_tables |= set(r.get('fk_closure_tables', []))
        for node in r.get('variable_resolution', {}).values():
            all_tables |= tables_referenced(node)

    if len(all_tables) == 0:
        raise ValueError(
            f"No table-backed inputs found for decision {records[0]['decision_name']!r} -- "
            f"every input is non-table-backed (literal/upstream/not_persisted); "
            f"this decision cannot be independently entity-enumerated from the database alone.")

    case_study = records[0]['case_study']
    if len(all_tables) == 1:
        subject = next(iter(all_tables))
        return subject, pk_columns(case_study, subject), {}

    root = _pick_root(case_study, all_tables, closure_tables)
    join_paths = {}
    for t in all_tables:
        if t == root:
            continue
        path = build_join_path(case_study, root, t, closure_tables)
        if path is None:
            raise ValueError(f"No FK join path found from root {root!r} to {t!r} "
                              f"within closure {sorted(closure_tables)} -- refusing to guess.")
        join_paths[t] = path
    return root, pk_columns(case_study, root), join_paths


if __name__ == '__main__':
    from phase1_utility import records_by_decision

    for decision_name, records in records_by_decision('OpenMRS').items():
        try:
            subject, pk_cols, join_paths = subject_table_for_decision(records, 'OpenMRS')
            print(f"{decision_name!r} -> subject table: {subject}  pk={pk_cols}  join_paths={join_paths}")
        except ValueError as e:
            print(f"{decision_name!r} -> UNRESOLVED: {e}")
