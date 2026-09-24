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

import re

_PLACEHOLDER_NAME_RE = re.compile(r'<([A-Za-z_][A-Za-z0-9_ ]*)>')


def _placeholder_source_tables(case_study, filter_text):
    """Every table `filter_placeholder_sources.py` names for one of
    `filter_text`'s own `<placeholder>`s -- empty for every placeholder
    with no override (the common case: it's a same-named column already
    on the subject row, needing no join at all, see `derived_aggregate`/
    `exists`'s own comments below)."""
    from filter_placeholder_sources import get_source_table
    tables = set()
    for name in _PLACEHOLDER_NAME_RE.findall(filter_text or ''):
        table = get_source_table(case_study, name)
        if table:
            tables.add(table)
    return tables


# Resolution kinds that read one or more tables directly. Maps kind ->
# a function extracting the set of table names it references. Every
# entry takes (node, case_study) even where case_study is unused, so
# `tables_referenced` can call them uniformly.
_TABLE_EXTRACTORS = {
    'schema_column': lambda n, cs: {n['table']},
    # Same reachability requirement as schema_column -- a real join path
    # to the row is still needed (db_resolver.resolve calls row_for, same
    # as schema_column does); only WHAT's read off that row differs (one
    # key out of a parsed YAML blob instead of a plain column).
    'serialized_field': lambda n, cs: {n['table']},
    'null_check': lambda n, cs: {n['table']},
    'derived_case': lambda n, cs: {n['table']},
    # derived_aggregate is ALWAYS self-contained for its OWN target table:
    # db_resolver.resolve queries n['table'] directly via a raw SQL WHERE
    # built entirely from substituting the SUBJECT row's own columns
    # (self/colon/<bracket> placeholders) -- it never calls
    # _row_for_table/walks a join path to reach n['table'] itself. But a
    # filter_text placeholder can ALSO need a value from a DIFFERENT
    # table when it's not on the subject row (see
    # filter_placeholder_sources.py) -- that table DOES need a real join
    # path, so it's added here when named.
    'derived_aggregate': lambda n, cs: _placeholder_source_tables(cs, n.get('filter_text')),
    'derived_join_count': lambda n, cs: {n['prereq_table'], n['registration_table']},
    # exists is the SAME story, but only when filter_text is present --
    # then it's a self-contained correlated EXISTS query against its OWN
    # candidate table, identical reasoning to derived_aggregate above
    # (including the same filter_placeholder_sources addition). With NO
    # filter_text (the OpenMRS-style "does the subject's OWN row have a
    # non-null value" pattern, or a genuinely bare "(existence)" with no
    # filter at all), db_resolver DOES call _row_for_table, so a join
    # path is still required there.
    'exists': lambda n, cs: (_placeholder_source_tables(cs, n.get('filter_text'))
                              if n.get('filter_text') else set(n['candidate_tables'])),
    'raw_sql_boolean': lambda n, cs: set(n['tables']),
    'any_not_null': lambda n, cs: {c['table'] for c in n['columns']},
    'join_lookup': lambda n, cs: {n['via']['local_table'], n['result_table']},
    'join_null_check': lambda n, cs: {n['via']['local_table'], n['result_table']},
    'regex_match': lambda n, cs: {n['value_column']['table'], n['pattern_column']['table']},
}

# Resolution kinds that do NOT read a table directly -- either a fixed
# value, an upstream decision's own output (handled by drd_executor.py,
# not a table lookup), or a genuinely non-database value.
_NON_TABLE_KINDS = {
    'literal', 'literal_via_upstream_branch', 'substituted_decision',
    'not_persisted', 'code_external', 'schema_gap', 'unresolved', 'variable',
}


def tables_referenced(node, case_study=None):
    """Every table one `variable_resolution` node reads directly. Empty
    set for a non-table kind (see `_NON_TABLE_KINDS`) -- NOT an error;
    the caller must check kind, not assume an empty set means failure.
    `case_study` is only consulted for a `filter_text` placeholder that
    needs a table other than the node's own (see
    `filter_placeholder_sources.py`); every other kind ignores it."""
    kind = node.get('kind')
    if kind in _TABLE_EXTRACTORS:
        return _TABLE_EXTRACTORS[kind](node, case_study)
    if kind in _NON_TABLE_KINDS:
        return set()
    if kind == 'substituted_decision':
        tables = set()
        for sub_node in node.get('free_variable_resolutions', {}).values():
            tables |= tables_referenced(sub_node, case_study)
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

    def _reaches(root, t):
        # A ValueError here means build_join_path found ONLY an
        # ambiguous/circumventing route -- treat exactly like "no path
        # found" for root-CANDIDACY purposes (this candidate root
        # doesn't cleanly reach `t`), not as a reason to crash the whole
        # search; a genuinely picked root still surfaces the same error
        # for real, later, when subject_table_for_decision actually
        # builds that join path.
        try:
            return build_join_path(case_study, root, t, closure_tables) is not None
        except ValueError:
            return False

    candidate_pool = closure_tables | all_tables
    candidates = [root for root in candidate_pool
                  if all(_reaches(root, t) for t in all_tables - {root})]

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
    from schema_utility import build_join_path, canonical_table_name, pk_columns

    case_study = records[0]['case_study']

    # Canonicalize every table name through the SAME schema-casing lookup
    # `build_join_path`/`fk_edges` already use internally, before any set
    # operation -- a real bug found running this against FLEX2 for the
    # first time: `variable_resolution`'s own `table` fields are written
    # lowercase (`course_registration`) while `fk_closure_tables` (and
    # the schema itself) use FLEX2's real upper-case names
    # (`COURSE_REGISTRATION`). Without this, `_pick_root`'s set logic
    # silently treats the SAME real table as two different ones --
    # either manufacturing a fake "2 candidates qualify" ambiguity (both
    # spellings independently look like valid roots) or a fake "0
    # candidates qualify" failure (a table needed for reachability is
    # never actually counted as reached because it's compared under the
    # wrong spelling) -- confirmed real for 6 of FLEX2's own decisions,
    # every one of which mixes both spellings for the same table.
    all_tables = set()
    closure_tables = set()
    for r in records:
        closure_tables |= {canonical_table_name(case_study, t)
                            for t in r.get('fk_closure_tables', [])}
        for node in r.get('variable_resolution', {}).values():
            all_tables |= {canonical_table_name(case_study, t)
                           for t in tables_referenced(node, case_study)}

    if len(all_tables) == 0:
        raise ValueError(
            f"No table-backed inputs found for decision {records[0]['decision_name']!r} -- "
            f"every input is non-table-backed (literal/upstream/not_persisted); "
            f"this decision cannot be independently entity-enumerated from the database alone.")

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
