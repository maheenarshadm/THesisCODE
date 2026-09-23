"""Live SQL translation of a Phase 1 `variable_resolution` node into a
real value, queried fresh from an already-materialized SQLite database.
Never reads generator/candidate.py's in-memory row objects, never calls
fitness.py/evaluate_objective. See DESIGN.md's per-resolution-kind table
for the design this implements.

Current scope, disclosed: every kind that resolves through a SINGLE
subject-table row (matched by an explicit column=value condition) is
implemented. Kinds whose own `filter_text`/`sql_template` contains
`<placeholder>` bind-parameters (most real uses of `derived_aggregate`,
`derived_join_count`, and some `raw_sql_boolean`) are NOT yet
implemented -- resolving them independently requires deciding how the
validator obtains a bind-parameter's value without reading search state,
which is the same open question as `not_persisted` inputs (DESIGN.md,
"known gaps"). `resolve()` raises `NotImplementedError` for these,
naming exactly what is missing, rather than silently returning a wrong
value.
"""
import re

_PLACEHOLDER_RE = re.compile(r'<([A-Za-z_][A-Za-z0-9_ ]*)>')


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


def _one_row(conn, table, where_col, where_val):
    cur = conn.execute(f'SELECT * FROM "{table}" WHERE "{where_col}" = ?', (where_val,))
    row = cur.fetchone()
    cols = [d[0] for d in cur.description] if cur.description else []
    return dict(zip(cols, row)) if row is not None else None


def resolve(conn, node, subject_table, subject_pk_column, subject_pk_value):
    """`node` is one Phase 1 `variable_resolution` entry. `subject_table`/
    `subject_pk_column`/`subject_pk_value` identify the real case under
    test (e.g. patient_identifier / patient_identifier_id / 35000001) --
    the ONE piece of identity the caller supplies; every value returned
    here is a fresh query against the live database, never a cached one.
    """
    kind = node.get('kind')

    if kind == 'schema_column':
        table = node['table']
        if table == subject_table:
            row = _one_row(conn, table, subject_pk_column, subject_pk_value)
            query = f'SELECT "{node["column"]}" FROM "{table}" WHERE "{subject_pk_column}" = {subject_pk_value}'
            value = row[node['column']] if row is not None else None
            return ResolvedValue(value, 'schema_column', table, query, row)
        raise NotImplementedError(
            f"schema_column on {table!r} != subject table {subject_table!r} -- "
            f"cross-table schema_column needs a join path, not yet implemented")

    if kind == 'null_check':
        table = node['table']
        row = _one_row(conn, table, subject_pk_column, subject_pk_value)
        value = (row[node['column']] is None) if row is not None else True
        query = f'SELECT "{node["column"]}" IS NULL FROM "{table}" WHERE "{subject_pk_column}" = {subject_pk_value}'
        return ResolvedValue(value, 'null_check', table, query, row)

    if kind == 'any_not_null':
        row = None
        value = False
        cols_checked = []
        for c in node['columns']:
            r = _one_row(conn, c['table'], subject_pk_column, subject_pk_value)
            cols_checked.append(f"{c['table']}.{c['column']}")
            if r is not None and r.get(c['column']) is not None:
                value = True
                row = r
        query = f"ANY NOT NULL among {cols_checked}"
        return ResolvedValue(value, 'any_not_null', node['columns'][0]['table'], query, row)

    if kind == 'regex_match':
        vc, pc = node['value_column'], node['pattern_column']
        vrow = _one_row(conn, vc['table'], subject_pk_column, subject_pk_value)
        prow = _one_row(conn, pc['table'], subject_pk_column, subject_pk_value)
        value_str = vrow[vc['column']] if vrow else None
        pattern = prow[pc['column']] if prow else None
        matched = bool(pattern and value_str is not None and re.fullmatch(pattern, str(value_str)))
        query = f"regex_match({vc['table']}.{vc['column']}, pattern={pc['table']}.{pc['column']})"
        return ResolvedValue(matched, 'regex_match', vc['table'], query, {'value': value_str, 'pattern': pattern})

    if kind in ('join_lookup', 'join_null_check'):
        via = node['via']
        local_row = _one_row(conn, via['local_table'], subject_pk_column, subject_pk_value)
        if local_row is None:
            return ResolvedValue(None, kind, node['result_table'], 'local row not found', None)
        fk_value = local_row.get(via['local_column'])
        # result_table's own PK column name isn't in the node -- assume
        # the FK's target column shares the FK column's own name unless
        # told otherwise (OpenMRS's own encounter_id -> encounter.encounter_id
        # pattern, confirmed directly against this project's schema style).
        result_row = _one_row(conn, node['result_table'], via['local_column'], fk_value) \
            if fk_value is not None else None
        raw_value = result_row.get(node['result_column']) if result_row else None
        value = (raw_value is None) if kind == 'join_null_check' else raw_value
        query = (f'{via["local_table"]}.{via["local_column"]} -> '
                 f'{node["result_table"]}.{node["result_column"]}')
        return ResolvedValue(value, kind, node['result_table'], query, result_row)

    if kind == 'exists':
        found = False
        checked = []
        for cc in node['candidate_columns']:
            row = _one_row(conn, cc['table'], subject_pk_column, subject_pk_value)
            checked.append(f"{cc['table']}.{cc['column']}")
            if row is not None and row.get(cc['column']) is not None:
                found = True
        query = f"EXISTS among {checked} (filter={node.get('filter_text')!r})"
        return ResolvedValue(found, 'exists', node['candidate_tables'][0], query, None)

    if kind == 'raw_sql_boolean':
        if _PLACEHOLDER_RE.search(node['sql_template']):
            raise NotImplementedError(
                f"raw_sql_boolean has bind-parameter placeholder(s) "
                f"{_PLACEHOLDER_RE.findall(node['sql_template'])} -- not yet resolvable "
                f"independently of scenario state (see module docstring)")
        cur = conn.execute(node['sql_template'])
        row = cur.fetchone()
        value = row[0] if row else None
        return ResolvedValue(value, 'raw_sql_boolean', ','.join(node['tables']), node['sql_template'], None)

    if kind in ('derived_aggregate', 'derived_join_count'):
        raise NotImplementedError(
            f"{kind} resolution ({node.get('source_text', node)}) needs bind-parameter "
            f"values (e.g. <student>, <semester>) this validator does not yet resolve "
            f"independently -- see module docstring")

    if kind in ('literal',):
        return ResolvedValue(node['value'], 'literal', None, 'literal', None)

    if kind in ('not_persisted',):
        raise NotImplementedError(
            "not_persisted has no table/column to query by definition -- "
            "caller must supply a declared scenario value explicitly and "
            "flag it as not-database-derived (see DESIGN.md known gaps)")

    raise NotImplementedError(f"Unhandled variable_resolution kind {kind!r}: {node!r}")


if __name__ == '__main__':
    import json
    import os
    import sqlite3

    HERE = os.path.dirname(os.path.abspath(__file__))
    conn = sqlite3.connect(os.path.join(HERE, 'tests', 'fixtures', 'openmrs_merged.db'))

    compiled = json.load(open(os.path.join(HERE, '..', 'generator', 'compiled_constraints.json')))
    rec = next(r for r in compiled if r['record_id'] ==
               'OpenMRS::Preferred Identifier Requirement::Decision_PreferredIdentifierRequirement_Rule_2')

    # Find a real patient_identifier row to use as the subject -- any one
    # will do for this smoke test; drd_executor.py will later enumerate
    # ALL of them for real coverage.
    cur = conn.execute('SELECT patient_identifier_id FROM patient_identifier LIMIT 5')
    for (pk,) in cur.fetchall():
        print(f"\npatient_identifier_id={pk}:")
        for var, node in rec['variable_resolution'].items():
            try:
                result = resolve(conn, node, 'patient_identifier', 'patient_identifier_id', pk)
                print(f"  {var} = {result.value!r}  ({result.resolution_type}, {result.source_query})")
            except NotImplementedError as e:
                print(f"  {var}: NOT IMPLEMENTED -- {e}")
