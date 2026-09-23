"""Live SQL translation of a Phase 1 `variable_resolution` node into a
real value, queried fresh from an already-materialized SQLite database.
Never reads generator/candidate.py's in-memory row objects, never calls
fitness.py/evaluate_objective. See DESIGN.md's per-resolution-kind table
for the design this implements.

Subject-row identity is always a (columns, values) PAIR OF TUPLES, even
for a single-column PK -- matches `schema_utility.pk_columns`'s own
always-a-list convention (confirmed real, not hypothetical: FLEX2's
COURSE_REGISTRATION/STUDENT_SEMESTER both have composite PKs).

Cross-table resolution uses `subject_table.py`'s own forward-only FK
join paths (`schema_utility.build_join_path`) -- a kind whose own table
differs from the subject table is resolved by walking that path, hop by
hop, via real queries, never guessed. A join HOP itself still follows a
single FK column (schema FKs in this project are all single-column) --
landing on a composite-PK table via one FK column could, in principle,
be ambiguous if that one column isn't the WHOLE target key; not yet
guarded against, disclosed here rather than silently assumed safe.

Remaining disclosed gap: kinds whose own `filter_text`/`sql_template`
binds a placeholder (`<student>`, `<semester>`, ...) to a NAMED COLUMN
this validator does not recognize on the subject row are resolved by
matching the placeholder's own conjunct column name against a same-named
column on the subject row (see `_resolve_placeholders`) -- when no such
column exists, `resolve()` raises `NotImplementedError`, naming exactly
what is missing, rather than guessing a value. `not_persisted` has no
database representation by definition; `resolve()` accepts an optional,
EXPLICIT `declared_not_persisted_value` the caller must supply, and
returns a `ResolvedValue` flagged `resolution_type='not_persisted_declared'`
-- visibly NOT database-derived in every trace this produces.
"""
import re

_PLACEHOLDER_RE = re.compile(r'<([A-Za-z_][A-Za-z0-9_ ]*)>')
_CONJUNCT_RE = re.compile(r'([A-Za-z_][A-Za-z0-9_]*)\s*=\s*<([A-Za-z_][A-Za-z0-9_ ]*)>')


class ResolvedValue:
    def __init__(self, value, resolution_type, source_table, source_query, source_row=None):
        self.value = value
        self.resolution_type = resolution_type
        self.source_table = source_table
        self.source_query = source_query
        self.source_row = source_row

    def __repr__(self):
        return (f"ResolvedValue(value={self.value!r}, type={self.resolution_type!r}, "
                f"table={self.source_table!r})")


def _as_tuple(x):
    return tuple(x) if isinstance(x, (list, tuple)) else (x,)


def _one_row(conn, table, where_cols, where_vals):
    """`where_cols`/`where_vals` are same-length sequences -- a single-
    column PK is just a 1-tuple, not a special case."""
    where_cols = _as_tuple(where_cols)
    where_vals = _as_tuple(where_vals)
    clause = ' AND '.join(f'"{c}" = ?' for c in where_cols)
    cur = conn.execute(f'SELECT * FROM "{table}" WHERE {clause}', where_vals)
    row = cur.fetchone()
    cols = [d[0] for d in cur.description] if cur.description else []
    return dict(zip(cols, row)) if row is not None else None


def _row_for_table(conn, target_table, subject_table, subject_pk_cols, subject_pk_vals, join_paths):
    """The real row in `target_table` that corresponds to the current
    subject case -- either the subject row itself, or found by walking
    `join_paths[target_table]` (from `subject_table.py`) hop by hop with
    real queries. Raises if `target_table` needs a join path that was
    never derived (a decision this validator hasn't been told how to
    join), never silently returns the wrong row."""
    if target_table == subject_table:
        return _one_row(conn, subject_table, subject_pk_cols, subject_pk_vals)

    path = join_paths.get(target_table)
    if path is None:
        raise NotImplementedError(
            f"No join path from subject table {subject_table!r} to {target_table!r} -- "
            f"pass it via subject_table.subject_table_for_decision's own join_paths")

    current_row = _one_row(conn, subject_table, subject_pk_cols, subject_pk_vals)
    for hop in path:
        if current_row is None:
            return None
        fk_value = current_row.get(hop['from_column'])
        current_row = _one_row(conn, hop['to_table'], hop['to_column'], fk_value) \
            if fk_value is not None else None
    return current_row


def _resolve_placeholders(conn, filter_text, subject_row):
    """`filter_text` conjuncts of the form `COLUMN = <placeholder>` name
    the target table's own column directly -- the placeholder's real
    value is the SUBJECT ROW's own value for a column of the SAME NAME,
    if one exists (the same matching principle DESIGN.md's per-kind
    table describes). Returns {placeholder_name: value}; raises naming
    the first placeholder it cannot match to any subject-row column,
    rather than silently treating it as NULL/wildcard."""
    bindings = {}
    for column, placeholder in _CONJUNCT_RE.findall(filter_text or ''):
        if column not in subject_row:
            raise NotImplementedError(
                f"filter_text placeholder <{placeholder}> binds to column {column!r}, "
                f"not present on the subject row ({sorted(subject_row)}) -- "
                f"cannot resolve independently of a declared scenario value")
        bindings[placeholder] = subject_row[column]
    return bindings


def resolve(conn, node, subject_table, subject_pk_cols, subject_pk_vals,
            join_paths=None, declared_not_persisted_value=None):
    """`node` is one Phase 1 `variable_resolution` entry. `subject_table`/
    `subject_pk_cols`/`subject_pk_vals` identify the real case under
    test -- the ONE piece of identity the caller supplies (both always
    sequences, even for a single-column key); every value returned here
    is a fresh query against the live database, never a cached one.
    `join_paths` (from `subject_table.subject_table_for_decision`) is
    required when `node`'s own table differs from `subject_table`.

    `declared_not_persisted_value`, if given, is the ONE value the
    caller explicitly declares for THIS `not_persisted` variable (the
    caller knows which variable it's resolving; this function does not,
    since a bare `{'kind': 'not_persisted'}` node carries no name) --
    see module docstring for why this can never be database-derived.
    """
    join_paths = join_paths or {}
    kind = node.get('kind')
    subject_row = _one_row(conn, subject_table, subject_pk_cols, subject_pk_vals)

    def row_for(table):
        return _row_for_table(conn, table, subject_table, subject_pk_cols, subject_pk_vals, join_paths)

    if kind == 'schema_column':
        table = node['table']
        row = row_for(table)
        value = row[node['column']] if row is not None else None
        return ResolvedValue(value, 'schema_column', table, f'{table}.{node["column"]}', row)

    if kind == 'null_check':
        table = node['table']
        row = row_for(table)
        value = (row[node['column']] is None) if row is not None else True
        return ResolvedValue(value, 'null_check', table, f'{table}.{node["column"]} IS NULL', row)

    if kind == 'any_not_null':
        row = None
        value = False
        cols_checked = []
        for c in node['columns']:
            r = row_for(c['table'])
            cols_checked.append(f"{c['table']}.{c['column']}")
            if r is not None and r.get(c['column']) is not None:
                value = True
                row = r
        return ResolvedValue(value, 'any_not_null', node['columns'][0]['table'],
                              f"ANY NOT NULL among {cols_checked}", row)

    if kind == 'regex_match':
        vc, pc = node['value_column'], node['pattern_column']
        vrow, prow = row_for(vc['table']), row_for(pc['table'])
        value_str = vrow[vc['column']] if vrow else None
        pattern = prow[pc['column']] if prow else None
        matched = bool(pattern and value_str is not None and re.fullmatch(pattern, str(value_str)))
        return ResolvedValue(matched, 'regex_match', vc['table'],
                              f"regex_match({vc['table']}.{vc['column']}, pattern={pc['table']}.{pc['column']})",
                              {'value': value_str, 'pattern': pattern})

    if kind in ('join_lookup', 'join_null_check'):
        via = node['via']
        local_row = row_for(via['local_table'])
        if local_row is None:
            return ResolvedValue(None, kind, node['result_table'], 'local row not found', None)
        fk_value = local_row.get(via['local_column'])
        result_row = _one_row(conn, node['result_table'], via['local_column'], fk_value) \
            if fk_value is not None else None
        raw_value = result_row.get(node['result_column']) if result_row else None
        value = (raw_value is None) if kind == 'join_null_check' else raw_value
        return ResolvedValue(value, kind, node['result_table'],
                              f'{via["local_table"]}.{via["local_column"]} -> '
                              f'{node["result_table"]}.{node["result_column"]}', result_row)

    if kind == 'exists':
        found = False
        checked = []
        for cc in node['candidate_columns']:
            row = row_for(cc['table'])
            checked.append(f"{cc['table']}.{cc['column']}")
            if row is not None and row.get(cc['column']) is not None:
                found = True
        return ResolvedValue(found, 'exists', node['candidate_tables'][0],
                              f"EXISTS among {checked} (filter={node.get('filter_text')!r})", None)

    if kind == 'raw_sql_boolean':
        placeholders = _PLACEHOLDER_RE.findall(node['sql_template'])
        sql = node['sql_template']
        if placeholders:
            bindings = _resolve_placeholders(conn, node['sql_template'], subject_row or {})
            for ph, val in bindings.items():
                sql = sql.replace(f'<{ph}>', _sql_literal(val))
        cur = conn.execute(sql)
        row = cur.fetchone()
        value = row[0] if row else None
        return ResolvedValue(value, 'raw_sql_boolean', ','.join(node['tables']), sql, None)

    if kind == 'derived_aggregate':
        bindings = _resolve_placeholders(conn, node['filter_text'], subject_row or {})
        where = node['filter_text']
        for ph, val in bindings.items():
            where = where.replace(f'<{ph}>', _sql_literal(val))
        sql = f'SELECT {node["aggregate"]}(*) FROM "{node["table"]}" WHERE {where}'
        cur = conn.execute(sql)
        value = cur.fetchone()[0]
        return ResolvedValue(value, 'derived_aggregate', node['table'], sql, None)

    if kind == 'derived_join_count':
        # "How many PREREQ_TABLE rows for this course are satisfied by a
        # REGISTRATION_TABLE row (same student, PASSING grade)" -- the
        # placeholder <student> is the only bind-parameter this kind's
        # own fields name (matched the same way derived_aggregate's is);
        # the join itself is fixed by the node's own column names, not a
        # free-form filter_text, so it's built directly rather than
        # through _resolve_placeholders' conjunct parser.
        subject_cols = set(subject_row or {})
        student_col = node['registration_roll_column']
        if student_col not in subject_cols:
            raise NotImplementedError(
                f"derived_join_count needs {student_col!r} on the subject row "
                f"({sorted(subject_cols)}) to bind the student -- not present")
        student_val = subject_row[student_col]
        fail_grades = ', '.join(_sql_literal(g) for g in node['fail_grades'])
        sql = (
            f'SELECT COUNT(*) FROM "{node["prereq_table"]}" p '
            f'WHERE NOT EXISTS ('
            f'  SELECT 1 FROM "{node["registration_table"]}" r '
            f'  WHERE r."{node["registration_course_column"]}" = p."{node["prereq_target_column"]}" '
            f'    AND r."{node["registration_roll_column"]}" = {_sql_literal(student_val)} '
            f'    AND r."{node["registration_grade_column"]}" NOT IN ({fail_grades})'
            f')'
        )
        cur = conn.execute(sql)
        value = cur.fetchone()[0]
        return ResolvedValue(value, 'derived_join_count', node['prereq_table'], sql, None)

    if kind == 'literal':
        return ResolvedValue(node['value'], 'literal', None, 'literal', None)

    if kind == 'not_persisted':
        if declared_not_persisted_value is None:
            raise NotImplementedError(
                "not_persisted has no table/column to query by definition -- "
                "caller must supply declared_not_persisted_value explicitly, flagged as "
                "not-database-derived (see DESIGN.md known gaps)")
        # Visibly distinct resolution_type so every trace this produces
        # shows the value was declared, never queried from the database.
        return ResolvedValue(declared_not_persisted_value, 'not_persisted_declared', None,
                              'declared scenario value, not database-derived', None)

    raise NotImplementedError(f"Unhandled variable_resolution kind {kind!r}: {node!r}")


def _sql_literal(value):
    if value is None:
        return 'NULL'
    if isinstance(value, (int, float)):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


if __name__ == '__main__':
    import os
    import sqlite3

    from subject_table import subject_table_for_decision
    from phase1_utility import records_by_decision

    HERE = os.path.dirname(os.path.abspath(__file__))
    conn = sqlite3.connect(os.path.join(HERE, 'tests', 'fixtures', 'openmrs_merged.db'))

    decision_name = 'Identifier Location Requirement'
    records = records_by_decision('OpenMRS')[decision_name]
    subject_table, pk_cols, join_paths = subject_table_for_decision(records, 'OpenMRS')
    print(f"subject_table={subject_table}  pk={pk_cols}  join_paths={join_paths}\n")

    cols_sql = ', '.join(f'"{c}"' for c in pk_cols)
    cur = conn.execute(f'SELECT {cols_sql} FROM "{subject_table}" LIMIT 5')
    all_resolutions = {}
    for r in records:
        all_resolutions.update(r['variable_resolution'])

    for row in cur.fetchall():
        print(f"{subject_table} pk={row}:")
        for var, node in all_resolutions.items():
            try:
                result = resolve(conn, node, subject_table, pk_cols, row, join_paths)
                print(f"  {var} = {result.value!r}  ({result.resolution_type}, table={result.source_table})")
            except NotImplementedError as e:
                print(f"  {var}: NOT IMPLEMENTED -- {e}")
