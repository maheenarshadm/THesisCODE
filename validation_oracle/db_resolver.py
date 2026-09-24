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
import yaml

_PLACEHOLDER_RE = re.compile(r'<([A-Za-z_][A-Za-z0-9_ ]*)>')
_CONJUNCT_RE = re.compile(r'([A-Za-z_][A-Za-z0-9_]*)\s*=\s*<([A-Za-z_][A-Za-z0-9_ ]*)>')


class UnresolvableForCase(Exception):
    """Raised when a resolution KIND is structurally understood and
    implemented, but THIS ONE real row's own data doesn't fit it -- e.g.
    `derived_case`'s real column value isn't covered by any declared
    CASE_MAP entry. A per-row data-quality gap, never guessed around, but
    distinct from a genuinely unimplemented resolution kind
    (NotImplementedError): the caller (drd_executor.py's `_resolve_one`)
    treats this as grounds for skipping just this one real case/variant,
    not the whole decision."""


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
    # Column names are lower-cased here because ground truth's own
    # ¡column! names are written lowercase across every case study
    # (schema_pairs/notes text), while the actual materialized schema can
    # use a different case convention per case study -- FLEX2's own
    # SQLite fixture stores every column name upper-case (confirmed real:
    # STUDENT_PROGRAM.CGPA), which crashed with a bare KeyError before this
    # fix (dict keys took cur.description's exact case, ground truth
    # looked up 'cgpa'). SQL identifier matching itself was never the
    # issue -- SQLite's own WHERE/FK comparisons are already ASCII
    # case-insensitive; only this dict's own Python-level lookup wasn't.
    cols = [d[0].lower() for d in cur.description] if cur.description else []
    return dict(zip(cols, row)) if row is not None else None


def _row_for_table(conn, target_table, subject_table, subject_pk_cols, subject_pk_vals, join_paths):
    """The real row in `target_table` that corresponds to the current
    subject case -- either the subject row itself, or found by walking
    `join_paths[target_table]` (from `subject_table.py`) hop by hop with
    real queries. Raises if `target_table` needs a join path that was
    never derived (a decision this validator hasn't been told how to
    join), never silently returns the wrong row.

    `target_table`/`subject_table`/`join_paths`' own keys are compared
    case-INSENSITIVELY: `subject_table.py` canonicalizes every table name
    through the schema's own casing before this point, but `node['table']`
    (the raw `variable_resolution` field feeding `target_table` here) is
    not -- ground truth writes some table references lowercase regardless
    of what the schema/subject_table.py settled on (confirmed real:
    FLEX2's own ground truth mixes `course_registration` and
    `COURSE_REGISTRATION` for the identical real table). A plain `==`
    here would treat the subject's own table as a foreign one needing a
    (nonexistent) join path purely because of spelling."""
    if target_table.upper() == subject_table.upper():
        return _one_row(conn, subject_table, subject_pk_cols, subject_pk_vals)

    path = join_paths.get(target_table)
    if path is None:
        path = next((v for k, v in join_paths.items() if k.upper() == target_table.upper()), None)
    if path is None:
        raise NotImplementedError(
            f"No join path from subject table {subject_table!r} to {target_table!r} -- "
            f"pass it via subject_table.subject_table_for_decision's own join_paths")

    current_row = _one_row(conn, subject_table, subject_pk_cols, subject_pk_vals)
    for hop in path:
        if current_row is None:
            return None
        fk_value = current_row.get(hop['from_column'].lower())
        current_row = _one_row(conn, hop['to_table'], hop['to_column'], fk_value) \
            if fk_value is not None else None
    return current_row


def _resolve_placeholders(conn, filter_text, subject_row, case_study=None,
                           subject_table=None, subject_pk_cols=None,
                           subject_pk_vals=None, join_paths=None):
    """`filter_text` conjuncts of the form `COLUMN = <placeholder>` name
    the target table's own column directly -- the placeholder's real
    value is FIRST the SUBJECT ROW's own value for a column of the SAME
    NAME, if one exists (the same matching principle DESIGN.md's
    per-kind table describes; unchanged from before this fallback
    existed, so every already-working placeholder -- jBilling's
    entity_id/status_id, Spree's own price_list_id/user_id/email -- is
    completely unaffected).

    Only when a placeholder is NOT on the subject row does this consult
    `filter_placeholder_sources.py`: if THAT names a table for it, the
    real value is read off the already-joined row via `_row_for_table`
    (`join_paths[table]`, from `subject_table.subject_table_for_decision`
    -- the SAME hop-walker every other cross-table kind already uses, no
    new join-finding logic). A placeholder with no override there, or
    with one but no `join_paths`/`case_study` supplied by the caller,
    falls through to the original error -- never a silent guess.

    Returns {placeholder_name: value}; raises naming the first
    placeholder it cannot resolve either way."""
    bindings = {}
    for column, placeholder in _CONJUNCT_RE.findall(filter_text or ''):
        column = column.lower()
        if column in subject_row:
            bindings[placeholder] = subject_row[column]
            continue
        source_table = None
        if case_study is not None and join_paths is not None:
            from filter_placeholder_sources import get_source_table
            source_table = get_source_table(case_study, placeholder)
        if source_table is not None:
            joined_row = _row_for_table(conn, source_table, subject_table, subject_pk_cols,
                                         subject_pk_vals, join_paths)
            if joined_row is not None and column in joined_row:
                bindings[placeholder] = joined_row[column]
                continue
        raise NotImplementedError(
            f"filter_text placeholder <{placeholder}> binds to column {column!r}, "
            f"not present on the subject row ({sorted(subject_row)})"
            + (f" or on {source_table!r} (joined, but the column/row wasn't there)"
               if source_table else "")
            + " -- cannot resolve independently of a declared scenario value")
    return bindings


# Excludes `::` (Ruby's own class/module namespace separator, e.g. a
# type-discriminator string literal like 'Spree::Promotion::Rules
# ::CustomerGroup') via the negative look-around on both sides -- a real
# bug found once a filter_text needed to compare against such a literal
# for the first time: the un-guarded version matched EVERY colon inside
# it as if it were a `:column_name` self-reference placeholder, raising
# a spurious "no matching column" error for a token (':promotion' out of
# 'Spree::Promotion::...') that was never meant to be a placeholder at
# all.
_COLON_RE = re.compile(r'(?<!:):(?!:)([A-Za-z_][A-Za-z0-9_]*)')
_SELF_RE = re.compile(r'\bself\b')


def _substitute_self_and_colon(text, subject_row, subject_pk_cols):
    """A second, distinct filter_text convention found in Spree's own
    compiled records (`price_list_id = :price_list_id AND id != self`) --
    NOT a cross-entity placeholder needing external binding at all, both
    tokens are SELF-references to the subject row already being resolved:
    `:column_name` means "this row's own value for `column_name`" (here,
    `price_list_id` names both the SQL parameter AND a real column on the
    SAME table); bare `self` means "this row's own primary key value"
    (used for an exclude-self aggregate: count OTHER rows, not this one).
    Raises rather than guessing when a `:column` isn't on the subject row,
    or when `self` is used against a composite-PK subject (a single
    value doesn't mean anything for a multi-column key)."""
    def _colon_sub(m):
        column = m.group(1).lower()
        if column not in subject_row:
            raise NotImplementedError(
                f"filter_text ':{column}' has no matching column on the subject row "
                f"({sorted(subject_row)}) -- cannot resolve independently")
        return _sql_literal(subject_row[column])

    text = _COLON_RE.sub(_colon_sub, text or '')

    if _SELF_RE.search(text):
        if len(subject_pk_cols) != 1:
            raise NotImplementedError(
                f"filter_text uses 'self' but the subject table has a composite PK "
                f"{subject_pk_cols} -- a single self-value is ambiguous, not resolved")
        self_value = subject_row[subject_pk_cols[0].lower()]
        text = _SELF_RE.sub(_sql_literal(self_value), text)

    return text


def resolve(conn, node, subject_table, subject_pk_cols, subject_pk_vals,
            join_paths=None, declared_not_persisted_value=None, case_study=None):
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

    `case_study`, if given, lets a `filter_text` placeholder not found on
    the subject row fall back to `filter_placeholder_sources.py` (see
    `_resolve_placeholders`) -- omitted, that fallback is simply never
    attempted and behavior is identical to before it existed.
    """
    join_paths = join_paths or {}
    kind = node.get('kind')
    subject_row = _one_row(conn, subject_table, subject_pk_cols, subject_pk_vals)

    def row_for(table):
        return _row_for_table(conn, table, subject_table, subject_pk_cols, subject_pk_vals, join_paths)

    if kind == 'schema_column':
        table = node['table']
        row = row_for(table)
        value = row[node['column'].lower()] if row is not None else None
        return ResolvedValue(value, 'schema_column', table, f'{table}.{node["column"]}', row)

    if kind == 'derived_case':
        # A DMN variable whose real value is a CATEGORICAL REMAPPING of a
        # raw database column, not the column's own value directly --
        # e.g. FLEX2's `semesterType`: `SEMESTER.TITLE` stores 'Fall'/
        # 'Spring'/'Summer', but `Course Load Limit`'s own DMN condition
        # compares against 'Regular'/'Summer', a different two-value
        # vocabulary `compile_constraints.py` maps through at compile
        # time (`cases`: a list of `[real_value, mapped_value]` pairs).
        # Mirrors `generator/candidate.py`'s own `derive_value` handling
        # of the identical kind exactly (never implemented on this side
        # until 2026-09-24 -- found only once a separate `drd_executor.py`
        # bug that had blocked every real case from ever reaching this
        # far was fixed): read the real column, walk `cases` for a
        # match, and raise -- never silently default -- when the real
        # value isn't covered by any case.
        table = node['table']
        row = row_for(table)
        real_value = row[node['column'].lower()] if row is not None else None
        for real, mapped in node['cases']:
            if real_value == real:
                return ResolvedValue(mapped, 'derived_case', table,
                                      f'{table}.{node["column"]} CASE_MAP', row)
        raise UnresolvableForCase(
            f"derived_case: real value {real_value!r} in {table}.{node['column']} isn't"
            f"covered by any CASE_MAP case ({node['cases']}) -- an unmapped real value, "
            f"not silently defaulted to one of the known categories")

    if kind == 'serialized_field':
        # The independent read side of generator/materialize.py's own
        # serialize_yaml_hash_blob (see that function's docstring for the
        # full disclosure -- confirmed against Spree's real source,
        # `serialize :preferences, type: Hash, coder: YAML`). Never
        # imports that function (this project's own architectural
        # separation rule) -- an independent re-implementation of the
        # SAME agreed convention: YAML text, symbol-style keys rendered
        # with a leading `:`. A row that exists but has no value at all
        # for this column (NULL, or a key this row's own blob never set)
        # falls back to `node.get('default')` -- the ONE ground-truth-
        # declared default, matching what a real, unconfigured promotion
        # rule would actually mean, never a silent None.
        table, column, key = node['table'], node['column'], node['key']
        row = row_for(table)
        raw = row.get(column) if row is not None else None
        blob = yaml.safe_load(raw) if raw else None
        value = (blob or {}).get(f':{key}', (blob or {}).get(key, node.get('default')))
        return ResolvedValue(value, 'serialized_field', table,
                              f'{table}.{column}[{key}] (YAML)', row)

    if kind == 'null_check':
        table = node['table']
        row = row_for(table)
        if node.get('key'):
            # A null_check on a serialized_field's own key (e.g. Spree's
            # amountMaxSet -- "was amount_max ever configured at all,"
            # confirmed a real, checkable fact once amount_max's real
            # default (nil) was confirmed against Spree's own source; the
            # ground truth's earlier "genuinely uncertain" call predated
            # that confirmation). Deliberately NO default substitution
            # here (unlike the plain serialized_field read above) --
            # existence must reflect whether the row's OWN blob actually
            # set this key, not whether some other declared default
            # happens to be non-null.
            raw = row.get(node['column']) if row is not None else None
            blob = yaml.safe_load(raw) if raw else None
            stored = (blob or {}).get(f":{node['key']}", (blob or {}).get(node['key'])) if blob else None
            # A null_check's own value means "is the fact SET" (matching
            # every ground-truth variable named this way, e.g.
            # amountMaxSet/expiresAtSet/customerPresent) -- `is not None`,
            # NOT `is None` -- UNLESS the ground truth's own notes
            # described the opposite polarity (e.g. OpenMRS's
            # identifierBlank: "identifier IS NULL OR TRIM(identifier) =
            # ''", true=EMPTY), in which case compile_constraints.py's own
            # `_null_check_is_negated` already set `negate` on this node,
            # confirmed against the notes text, not guessed here.
            # Confirmed against generator/candidate.py's own derive_value,
            # the canonical definition (both branches, and both honor
            # `negate` the same way). This branch and the plain one below
            # were BOTH found flat-out inverted (2026-09-24, while chasing
            # why a DMN-tautology fix -- Promotion Temporal
            # Availability::rule_2's `expiresAt > expiresAt` -- still
            # didn't verify after being corrected to `evaluationTime >
            # expiresAt`): confirmed with an isolated unit test against a
            # throwaway two-row SQLite table (col SET -> this code
            # returned False; col NULL -> returned True) before touching
            # anything. Fixing it blind (always `is not None`) then broke
            # identifierBlank the other way (real, populated identifiers
            # started reading as "blank") -- caught by this project's own
            # required before/after diff across all 4 case studies, which
            # is what surfaced the negated-wording case and led to the
            # `negate` flag instead of a single hardcoded polarity.
            is_set = stored is not None
            value = (not is_set) if node.get('negate') else is_set
            return ResolvedValue(value, 'null_check', table,
                                  f"{table}.{node['column']}[{node['key']}] "
                                  f"{'IS NULL' if node.get('negate') else 'IS NOT NULL'} (YAML)", row)
        is_set = (row[node['column'].lower()] is not None) if row is not None else False
        value = (not is_set) if node.get('negate') else is_set
        return ResolvedValue(value, 'null_check', table,
                              f'{table}.{node["column"]} '
                              f'{"IS NULL" if node.get("negate") else "IS NOT NULL"}', row)

    if kind == 'any_not_null':
        row = None
        value = False
        cols_checked = []
        for c in node['columns']:
            r = row_for(c['table'])
            cols_checked.append(f"{c['table']}.{c['column']}")
            if r is not None and r.get(c['column'].lower()) is not None:
                value = True
                row = r
        return ResolvedValue(value, 'any_not_null', node['columns'][0]['table'],
                              f"ANY NOT NULL among {cols_checked}", row)

    if kind == 'regex_match':
        vc, pc = node['value_column'], node['pattern_column']
        vrow, prow = row_for(vc['table']), row_for(pc['table'])
        value_str = vrow[vc['column'].lower()] if vrow else None
        pattern = prow[pc['column'].lower()] if prow else None
        matched = bool(pattern and value_str is not None and re.fullmatch(pattern, str(value_str)))
        return ResolvedValue(matched, 'regex_match', vc['table'],
                              f"regex_match({vc['table']}.{vc['column']}, pattern={pc['table']}.{pc['column']})",
                              {'value': value_str, 'pattern': pattern})

    if kind in ('join_lookup', 'join_null_check'):
        via = node['via']
        local_row = row_for(via['local_table'])
        if local_row is None:
            return ResolvedValue(None, kind, node['result_table'], 'local row not found', None)
        fk_value = local_row.get(via['local_column'].lower())
        result_row = _one_row(conn, node['result_table'], via['local_column'], fk_value) \
            if fk_value is not None else None
        raw_value = result_row.get(node['result_column'].lower()) if result_row else None
        value = (raw_value is None) if kind == 'join_null_check' else raw_value
        return ResolvedValue(value, kind, node['result_table'],
                              f'{via["local_table"]}.{via["local_column"]} -> '
                              f'{node["result_table"]}.{node["result_column"]}', result_row)

    if kind == 'exists':
        # A real bug found extending to jBilling: when `filter_text` is
        # present, this must run an actual correlated EXISTS query
        # (SELECT EXISTS(SELECT 1 FROM table WHERE filter_text), with
        # the subject row's own values substituted in) -- it was never
        # actually consulted before, meaning any exists-kind node with a
        # REAL, meaningfully different filter per case (jBilling's own
        # Currency Exchange Rate Source: hasEntitySpecificExchange vs.
        # hasSystemDefaultExchange, filtered on entity_id=<entity_id> vs.
        # entity_id=0 respectively) was silently evaluated as "does the
        # SUBJECT's own row have a non-null value," which happens to be
        # trivially true whenever candidate_table == subject_table,
        # regardless of which specific filter was declared. Fixed: when
        # filter_text exists, build the real WHERE clause (self/colon
        # substitution first, then <placeholder> substitution) and query
        # the candidate table directly -- no join path needed, since
        # every value the filter needs comes from the subject row itself
        # (see subject_table.tables_referenced's own matching fix).
        if node.get('filter_text'):
            table = node['candidate_tables'][0]
            where = _substitute_self_and_colon(node['filter_text'], subject_row or {}, subject_pk_cols)
            bindings = _resolve_placeholders(conn, where, subject_row or {}, case_study=case_study,
                                              subject_table=subject_table, subject_pk_cols=subject_pk_cols,
                                              subject_pk_vals=subject_pk_vals, join_paths=join_paths)
            for ph, val in bindings.items():
                where = where.replace(f'<{ph}>', _sql_literal(val))
            sql = f'SELECT EXISTS(SELECT 1 FROM "{table}" WHERE {where})'
            found = bool(conn.execute(sql).fetchone()[0])
            return ResolvedValue(found, 'exists', table, sql, None)

        # No filter_text: the OpenMRS-style pattern (candidate_table ==
        # subject_table, e.g. Identifier Uniqueness Check) -- "does the
        # subject row's own value for this column exist (non-null)."
        # Also the genuinely bare "(existence)" case with empty
        # candidate_columns, which has nothing machine-actionable to
        # check at all and correctly stays False rather than guessing.
        found = False
        checked = []
        for cc in node['candidate_columns']:
            row = row_for(cc['table'])
            checked.append(f"{cc['table']}.{cc['column']}")
            if row is not None and row.get(cc['column'].lower()) is not None:
                found = True
        return ResolvedValue(found, 'exists', node['candidate_tables'][0] if node['candidate_tables'] else None,
                              f"non-null among {checked}" if checked else "no filter_text, no candidate_columns", None)

    if kind == 'raw_sql_boolean':
        sql = _substitute_self_and_colon(node['sql_template'], subject_row or {}, subject_pk_cols)
        if _PLACEHOLDER_RE.search(sql):
            bindings = _resolve_placeholders(conn, sql, subject_row or {}, case_study=case_study,
                                              subject_table=subject_table, subject_pk_cols=subject_pk_cols,
                                              subject_pk_vals=subject_pk_vals, join_paths=join_paths)
            for ph, val in bindings.items():
                sql = sql.replace(f'<{ph}>', _sql_literal(val))
        cur = conn.execute(sql)
        row = cur.fetchone()
        value = row[0] if row else None
        return ResolvedValue(value, 'raw_sql_boolean', ','.join(node['tables']), sql, None)

    if kind == 'derived_aggregate':
        where = _substitute_self_and_colon(node['filter_text'], subject_row or {}, subject_pk_cols)
        bindings = _resolve_placeholders(conn, where, subject_row or {}, case_study=case_study,
                                          subject_table=subject_table, subject_pk_cols=subject_pk_cols,
                                          subject_pk_vals=subject_pk_vals, join_paths=join_paths)
        for ph, val in bindings.items():
            where = where.replace(f'<{ph}>', _sql_literal(val))
        # value_column (e.g. "MAX(ageing_entity_step.days) WHERE ...") is
        # a real, distinct recipe shape compile_constraints.py already
        # produces -- aggregating a NAMED column, not COUNT(*) of rows.
        # Never used before this: extending to jBilling surfaced the
        # first real case (a schema_column read that needed the same
        # entity/status correlation an exists-kind check nearby already
        # needed -- re-expressed as MAX over a single, uniquely-scoped
        # row, since a bare schema_column has no way to carry a filter).
        target = node['value_column'].split('.', 1)[1] if node.get('value_column') else '*'
        sql = f'SELECT {node["aggregate"]}({target}) FROM "{node["table"]}" WHERE {where}'
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
        student_col = node['registration_roll_column'].lower()
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
