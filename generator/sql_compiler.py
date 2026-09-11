#!/usr/bin/env python3
"""
compile_constraints.py's compiled predicate/expression trees -> real SQL,
per design doc §6.7: "the search loop runs on the JSON predicate; SQL is
compiled from that same JSON afterward, purely for validation." This is
that compiler -- the second of §12 item 7's two prerequisite artifacts
(compile_constraints.py was the first).

What it produces, per compiled branch record: one SQL boolean expression
(`SELECT (...) AS branch_holds;`) that re-evaluates the branch's condition
against real rows once a candidate has been materialized -- exactly the
"DMN semantic re-check, compiled to SQL rather than re-implemented in the
host language" pass §6.7 designs, mechanical because §7b's construct
taxonomy already enumerates which SQL construct each variable category
needs (WHERE, JOIN, EXISTS, COUNT+GROUP BY/subquery, IN, CASE, REGEXP).

Design choice, matching the design doc's own worked example's idiom
(`(SELECT COUNT(*) FROM STUDENT_ATTENDANCE WHERE ...) * 100.0 / (SELECT
COUNT(*) FROM LECTURE WHERE ...) < 80`): every resolved variable compiles
to an independent scalar subquery parameterized by bind variables (one per
referenced table's own primary key, e.g. `:student_program_pk`) rather than
one flat query with a shared FROM/JOIN graph across the whole branch. This
mirrors how the branches themselves are independent per §6.1, and needs no
assumption about how a validation harness's candidate rows are laid out
beyond "you can bind a value for this table's PK."

Honesty, not completeness, where source data doesn't support more: a
`derived_aggregate`/`exists` resolution's filter is often free-text prose
("LECTURE_ID IN (LECTURE for that OFFER_ID)", not valid SQL) rather than a
clean WHERE clause. This compiler only emits a filter when a direct
mechanical check (placeholder substitution + a prose-marker blocklist)
finds it SQL-shaped; otherwise it emits a syntactically-valid placeholder
subquery with the raw text preserved as a comment and records a warning,
never guessing at what a human-written note actually meant.

Usage:
    python3 sql_compiler.py --compiled compiled_constraints.json --out validation_queries.json
"""
import os
import sys
import re
import json
import argparse
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from compile_constraints import CASE_STUDY_SCHEMA_JSON  # noqa: E402 -- reused, not reimplemented


# ---------------------------------------------------------------------------
# Schema PK lookup (needed to parameterize a scalar-subquery's WHERE clause)
# ---------------------------------------------------------------------------

def load_schema_pks(cs):
    with open(CASE_STUDY_SCHEMA_JSON[cs], encoding='utf-8') as f:
        data = json.load(f)
    pks = {}
    for table, info in data.items():
        pk = info.get('pk')
        if isinstance(pk, str):
            pks[table] = [pk]
        elif isinstance(pk, list):
            pks[table] = pk
        else:
            pks[table] = []
    return pks


class SqlContext:
    """Per-record compilation state: which tables got a bind-parameterized
    scalar subquery (so the same table referenced twice reuses the same
    bind param name), warnings for anything not cleanly compilable, and
    the schema's own PK info (case-insensitive lookup, since ground-truth
    table names and the schema JSON's own casing don't always agree --
    the same mismatch `fk_closure()` already has to handle)."""

    def __init__(self, schema_pks):
        self._pks_lower = {t.lower(): (t, cols) for t, cols in schema_pks.items()}
        self.bind_params = {}  # name -> description
        self.warnings = []
        self._free_param_seed = Counter()

    def pk_columns(self, table):
        real_table, cols = self._pks_lower.get(table.lower(), (table, []))
        if not cols:
            self.warn(f"no declared primary key found for {table} -- used a placeholder bind param instead")
            return real_table, [f"{table}_row"]
        return real_table, cols

    def register_pk_binds(self, table):
        real_table, pk_cols = self.pk_columns(table)
        names = []
        for col in pk_cols:
            name = f"{real_table.lower()}_{col.lower()}"
            self.bind_params.setdefault(name, f"{real_table}.{col} of the specific candidate row")
            names.append(name)
        return real_table, pk_cols, names

    def register_free_param(self, hint):
        slug = re.sub(r'[^A-Za-z0-9_]+', '_', hint).strip('_').lower() or 'param'
        self._free_param_seed[slug] += 1
        if self._free_param_seed[slug] > 1:
            slug = f"{slug}_{self._free_param_seed[slug]}"
        self.bind_params.setdefault(slug, hint)
        return slug

    def warn(self, msg):
        if msg not in self.warnings:
            self.warnings.append(msg)


def sql_quote_string(s):
    return "'" + str(s).replace("'", "''") + "'"


def compile_literal(node):
    v, t = node.get('value'), node.get('type')
    if t == 'string':
        return sql_quote_string(v)
    if t == 'boolean':
        return 'TRUE' if v else 'FALSE'
    return str(v)


def as_boolean(value_sql):
    """Wraps a scalar TRUE/FALSE-valued SQL expression for use as a
    predicate (WHERE/CASE WHEN position)."""
    if value_sql in ('TRUE', 'FALSE'):
        return value_sql
    return f"({value_sql} = TRUE)"


def scalar_boolean_as_value(bool_sql):
    """Wraps a SQL predicate for use as a scalar value (comparison/
    arithmetic operand position) -- a portable CASE-based boolean-to-
    scalar cast rather than assuming the engine treats booleans as 0/1."""
    return f"(CASE WHEN {bool_sql} THEN TRUE ELSE FALSE END)"


_PLACEHOLDER_RE = re.compile(r'<([^>]+)>')
# A deliberately small, targeted blocklist -- surveyed from this program's
# own actual filter_text/notes strings, not a general English-detector.
# Anything matching one of these reads as prose describing intent
# ("LECTURE_ID IN (LECTURE for that OFFER_ID)"), not an executable WHERE
# clause, and should never be emitted as if it were valid SQL.
_PROSE_MARKERS_RE = re.compile(
    r'\bfor that\b|\bheld for\b|\bthat is\b|\brequested\b|\bon the\b|\bthis (?:order|course|customer)\b',
    re.I)


def sqlify_filter_text(text, ctx):
    """Best-effort: substitutes <placeholder> markers with bind params and
    accepts the result only if a mechanical check finds it SQL-shaped.
    Returns (sql_or_None, ok). The prose-marker check runs on the text with
    every <placeholder> span masked out first -- content inside <...> is
    by definition destined to become a bind parameter, not literal SQL, so
    an English phrase there (e.g. "<this course offering>") must never
    disqualify otherwise-clean surrounding SQL (a real bug this compiler's
    own first version had: checking the raw text let a placeholder's own
    prose reject a genuinely valid filter)."""
    if not text:
        return None, False
    masked = _PLACEHOLDER_RE.sub('__PARAM__', text)
    if _PROSE_MARKERS_RE.search(masked):
        return None, False

    def repl(m):
        return f":{ctx.register_free_param(m.group(1))}"

    sql = _PLACEHOLDER_RE.sub(repl, text)
    if sql.count('(') != sql.count(')'):
        return None, False
    return sql, True


# ---------------------------------------------------------------------------
# Resolution-node -> SQL value expression (one scalar subquery per fact)
# ---------------------------------------------------------------------------

def scalar_column_subquery(table, column, ctx):
    real_table, pk_cols, bind_names = ctx.register_pk_binds(table)
    where = ' AND '.join(f"{real_table}.{col} = :{name}" for col, name in zip(pk_cols, bind_names))
    return f"(SELECT {real_table}.{column} FROM {real_table} WHERE {where})"


def join_subquery(res, ctx):
    local_table = res['via']['local_table']
    local_column = res['via']['local_column']
    target_table = res['result_table']
    target_column = res['result_column']
    real_local, pk_cols, bind_names = ctx.register_pk_binds(local_table)
    where = ' AND '.join(f"{real_local}.{col} = :{name}" for col, name in zip(pk_cols, bind_names))
    # Heuristic, stated plainly: assumes the target table's matching join
    # column has the same name as the local FK column -- true for every
    # join_lookup fact actually surveyed in this program (e.g.
    # orders.encounter_id = encounter.encounter_id, encounter.visit_id =
    # visit.visit_id), but a naming convention, not a schema guarantee.
    return (f"(SELECT {target_table}.{target_column} FROM {real_local} "
            f"JOIN {target_table} ON {real_local}.{local_column} = {target_table}.{local_column} "
            f"WHERE {where})")


def aggregate_subquery(res, ctx):
    table = res['table']
    agg = res['aggregate']
    value_column = res.get('value_column')
    if value_column:
        # A real named target column (e.g. SUM(COURSE.CREDIT_HRS), FLEX2's
        # degreeTotalCredits) -- compiles to the actual aggregate, not a
        # placeholder, and needs no warning: this is exactly as clean as
        # a COUNT(*).
        fn = f"{agg}({value_column})"
    else:
        fn = f"{agg}(*)" if agg == 'COUNT' else f"{agg}(1)"
        if agg != 'COUNT':
            ctx.warn(f"{agg}({table}) has no target column identified in its filter text -- "
                      f"used {agg}(1) as a placeholder; needs a real column")
    filter_sql, ok = sqlify_filter_text(res.get('filter_text'), ctx)
    if not ok:
        ctx.warn(f"{table}'s aggregate filter is prose, not SQL -- needs manual completion: "
                  f"{(res.get('filter_text') or '')[:100]!r}")
        escaped = (res.get('filter_text') or '').replace('*/', '* /')
        return f"(SELECT {fn} FROM {table} /* NEEDS MANUAL WHERE CLAUSE: {escaped} */)"
    return f"(SELECT {fn} FROM {table} WHERE {filter_sql})"


def exists_subquery(res, ctx):
    tables = res.get('candidate_tables') or []
    if not tables:
        ctx.warn("an 'exists' fact named no candidate table at all -- cannot compile even a placeholder")
        return 'FALSE /* UNRESOLVED: no candidate table */'
    table = tables[0]
    cols = [c for c in res.get('candidate_columns', []) if c['table'] == table]
    if not cols:
        ctx.warn(f"'exists' fact on {table} has no key columns identified -- needs a manual WHERE clause")
        return f"EXISTS (SELECT 1 FROM {table} /* NEEDS MANUAL WHERE CLAUSE */)"
    conds = []
    for c in cols:
        name = ctx.register_free_param(f"{table}_{c['column']}")
        conds.append(f"{table}.{c['column']} = :{name}")
    return f"EXISTS (SELECT 1 FROM {table} WHERE {' AND '.join(conds)})"


def compile_resolution_as_value(res, ctx, var_name=None):
    kind = res.get('kind')
    if kind == 'literal':
        return compile_literal(res)
    if kind == 'not_persisted':
        # Not always an output verdict: ground truth also uses this bucket
        # for a genuine scenario/runtime parameter with no stored column at
        # all by design (OpenMRS's evaluationTime -- "time of validation,
        # not a stored column"), which is a perfectly legitimate INPUT --
        # this function is only ever reached from a condition's operand
        # position in the first place, so a not_persisted resolution
        # reaching it is always this input case, never the output case
        # (outputs are compiled separately, by compile_constraints.py's
        # own parse_output_value, never through here). Compiles to a bind
        # parameter the validation harness supplies directly, exactly like
        # a scenario's PK values already are.
        name = ctx.register_free_param(var_name or 'runtime_parameter')
        return f":{name}"
    if kind == 'schema_column':
        return scalar_column_subquery(res['table'], res['column'], ctx)
    if kind == 'null_check':
        return scalar_boolean_as_value(f"{scalar_column_subquery(res['table'], res['column'], ctx)} IS NOT NULL")
    if kind == 'any_not_null':
        parts = [f"{scalar_column_subquery(c['table'], c['column'], ctx)} IS NOT NULL"
                 for c in res['columns']]
        return scalar_boolean_as_value('(' + ' OR '.join(parts) + ')')
    if kind == 'join_lookup':
        return join_subquery(res, ctx)
    if kind == 'join_null_check':
        return scalar_boolean_as_value(f"{join_subquery(res, ctx)} IS NOT NULL")
    if kind == 'derived_aggregate':
        return aggregate_subquery(res, ctx)
    if kind == 'exists':
        return scalar_boolean_as_value(exists_subquery(res, ctx))
    if kind == 'regex_match':
        left = scalar_column_subquery(res['value_column']['table'], res['value_column']['column'], ctx)
        right = scalar_column_subquery(res['pattern_column']['table'], res['pattern_column']['column'], ctx)
        ctx.warn("REGEXP is not portable SQL -- MySQL/MariaDB syntax used here (§7b's own 'not portable' finding)")
        return scalar_boolean_as_value(f"{left} REGEXP {right}")
    if kind == 'raw_sql_boolean':
        # A fully hand-worked-out boolean SQL expression a ground-truth row
        # named directly (RAW_SQL:/TABLES: marker, compile_constraints.py)
        # for a fact too bespoke for any structured shape -- still put
        # through the same <placeholder>-substitution and prose-shape
        # checks as every other filter text, never trusted blindly.
        sql, ok = sqlify_filter_text(res['sql_template'], ctx)
        if not ok:
            ctx.warn(f"a raw_sql_boolean fact's template didn't pass the SQL-shape check -- "
                      f"needs manual completion: {res['sql_template'][:100]!r}")
            escaped = res['sql_template'].replace('*/', '* /')
            return f"NULL /* NEEDS MANUAL RAW SQL: {escaped} */"
        return scalar_boolean_as_value(sql)
    if kind == 'literal_via_upstream_branch':
        return compile_value_expr(res['value'], ctx, {})
    if kind == 'substituted_decision':
        return compile_value_expr(res['expression'], ctx, res.get('free_variable_resolutions', {}))
    if kind == 'derived':
        ctx.warn(f"an unclassified 'derived' fact was left as a NULL placeholder: "
                  f"{(res.get('notes') or '')[:100]!r}")
        return 'NULL /* UNRESOLVED DERIVED FACT -- see notes in compiled_constraints.json */'
    # schema_gap/code_external/unresolved/chained_decision_output should never
    # actually reach here -- compile_constraints.py already refuses to compile
    # a branch depending on one as an input (not_persisted, handled above, is
    # the one exception -- see its own comment for why it's legitimate here).
    # Surfaced loudly rather than silently, in case that invariant is ever
    # broken by a future change.
    ctx.warn(f"resolution kind {kind!r} should never reach the SQL compiler for a compiled branch")
    return f"NULL /* INVARIANT VIOLATION: kind={kind} */"


def compile_value_expr(node, ctx, resolution_map):
    """Compiles an expression-tree node (a condition's operand, or a
    substituted literal-expression formula) to a SQL scalar value."""
    if not isinstance(node, dict):
        ctx.warn("malformed expression node")
        return 'NULL'
    kind = node.get('kind')
    if kind == 'literal':
        return compile_literal(node)
    if kind == 'variable':
        res = resolution_map.get(node['ref'])
        if res is None:
            ctx.warn(f"variable {node['ref']!r} has no resolution in this context")
            return 'NULL /* UNRESOLVED VARIABLE */'
        return compile_resolution_as_value(res, ctx, node['ref'])
    if kind == 'call':
        args = ', '.join(compile_value_expr(a, ctx, resolution_map) for a in node.get('args', []))
        ctx.warn(f"function call {node.get('name')}(...) carried through as-is -- not a portable "
                  f"SQL translation, needs engine-specific review")
        return f"{node.get('name')}({args})"
    if kind == 'opaque_formula':
        ctx.warn(f"an opaque (unparsed) FEEL formula was left as a NULL placeholder: "
                  f"{node.get('feel_text', '')[:100]!r}")
        return 'NULL /* OPAQUE FORMULA */'
    op = node.get('op')
    if op in ('+', '-', '*', '/'):
        left = compile_value_expr(node['left'], ctx, resolution_map)
        right = compile_value_expr(node['right'], ctx, resolution_map)
        return f"({left} {op} {right})"
    if op == 'if':
        cond = compile_condition(node['cond'], ctx, resolution_map)
        then_v = compile_value_expr(node['then'], ctx, resolution_map)
        else_v = compile_value_expr(node['else'], ctx, resolution_map)
        return f"(CASE WHEN {cond} THEN {then_v} ELSE {else_v} END)"
    # A comparison/and/or/not/in/between node used in a value position
    # (rare -- e.g. a boolean sub-expression compared to another value).
    return scalar_boolean_as_value(compile_condition(node, ctx, resolution_map))


def _try_simplify_null_check_comparison(op, left_node, right_node, ctx, resolution_map):
    """"dateActivatedSet = true" (a null_check-resolved variable compared
    to a boolean literal) compiles far more directly to "col IS NOT NULL"
    than the generic round-trip (CASE WHEN col IS NOT NULL THEN TRUE ELSE
    FALSE END) = TRUE would -- checked in both operand orders. Returns
    the simplified SQL string, or None if this pattern doesn't apply."""
    if op not in ('=', '!='):
        return None
    for value_side, bool_side in ((left_node, right_node), (right_node, left_node)):
        if not (isinstance(bool_side, dict) and bool_side.get('kind') == 'literal'
                and bool_side.get('type') == 'boolean'):
            continue
        if not (isinstance(value_side, dict) and value_side.get('kind') == 'variable'):
            continue
        res = resolution_map.get(value_side['ref'])
        if not (res and res.get('kind') in ('null_check', 'join_null_check')):
            continue
        underlying = (join_subquery(res, ctx) if res['kind'] == 'join_null_check'
                      else scalar_column_subquery(res['table'], res['column'], ctx))
        wants_true = bool_side['value']
        if op == '!=':
            wants_true = not wants_true
        return f"({underlying} IS {'NOT NULL' if wants_true else 'NULL'})"
    return None


_SQL_COMPARISON_OPS = {'=': '=', '!=': '<>', '<': '<', '<=': '<=', '>': '>', '>=': '>='}


def compile_condition(node, ctx, resolution_map):
    """Compiles a predicate node to a SQL boolean expression."""
    if not isinstance(node, dict):
        ctx.warn("malformed condition node")
        return 'FALSE'
    if node.get('kind') == 'literal' and node.get('type') == 'boolean':
        return 'TRUE' if node['value'] else 'FALSE'
    if node.get('kind') == 'variable':
        res = resolution_map.get(node['ref'])
        if res is None:
            ctx.warn(f"variable {node['ref']!r} used as a bare condition has no resolution")
            return 'FALSE'
        return as_boolean(compile_resolution_as_value(res, ctx, node['ref']))

    op = node.get('op')
    if op in _SQL_COMPARISON_OPS:
        simplified = _try_simplify_null_check_comparison(op, node['left'], node['right'], ctx, resolution_map)
        if simplified is not None:
            return simplified
        left = compile_value_expr(node['left'], ctx, resolution_map)
        right = compile_value_expr(node['right'], ctx, resolution_map)
        return f"({left} {_SQL_COMPARISON_OPS[op]} {right})"
    if op == 'and':
        return '(' + ' AND '.join(compile_condition(c, ctx, resolution_map) for c in node['clauses']) + ')'
    if op == 'or':
        return '(' + ' OR '.join(compile_condition(c, ctx, resolution_map) for c in node['clauses']) + ')'
    if op == 'not':
        return f"(NOT {compile_condition(node['clause'], ctx, resolution_map)})"
    if op == 'in':
        left = compile_value_expr(node['left'], ctx, resolution_map)
        values = ', '.join(compile_value_expr(v, ctx, resolution_map) for v in node['values'])
        return f"({left} IN ({values}))"
    if op == 'between':
        left = compile_value_expr(node['left'], ctx, resolution_map)
        low = compile_value_expr(node['low'], ctx, resolution_map)
        high = compile_value_expr(node['high'], ctx, resolution_map)
        return f"({left} BETWEEN {low} AND {high})"
    ctx.warn(f"unrecognized condition operator {op!r}")
    return 'FALSE'


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def compile_record(record, schema_pks):
    ctx = SqlContext(schema_pks)
    condition_sql = compile_condition(record['condition'], ctx, record['variable_resolution'])
    sql = f"SELECT {condition_sql} AS branch_holds;"
    return {
        'record_id': record['record_id'],
        'case_study': record['case_study'],
        'sql': sql,
        'bind_parameters': sorted(ctx.bind_params.items()),
        'warnings': ctx.warnings,
        'clean': not ctx.warnings,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--compiled', default='compiled_constraints.json')
    ap.add_argument('--out', default='validation_queries.json')
    args = ap.parse_args()

    with open(args.compiled, encoding='utf-8') as f:
        records = json.load(f)

    schema_pks_by_cs = {}
    results = []
    for record in records:
        cs = record['case_study']
        if cs not in schema_pks_by_cs:
            schema_pks_by_cs[cs] = load_schema_pks(cs)
        results.append(compile_record(record, schema_pks_by_cs[cs]))

    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=1)

    total = len(results)
    clean = sum(1 for r in results if r['clean'])
    print(f"Compiled {total} validation queries: {clean} clean ({clean/total:.1%}), "
          f"{total - clean} need manual completion")

    warning_counter = Counter()
    for r in results:
        for w in r['warnings']:
            # bucket by the leading phrase so similar warnings group together
            key = w.split(':')[0].split(' -- ')[0][:60]
            warning_counter[key] += 1
    print("\nWarning reasons (by record, may double-count a record with 2+ warnings):")
    for reason, n in warning_counter.most_common():
        print(f"  {n:>4}  {reason}")

    from collections import Counter as C
    by_cs = C()
    clean_by_cs = C()
    for r in results:
        by_cs[r['case_study']] += 1
        if r['clean']:
            clean_by_cs[r['case_study']] += 1
    print("\nPer case study:")
    for cs in by_cs:
        print(f"  {cs}: {clean_by_cs[cs]}/{by_cs[cs]} clean ({clean_by_cs[cs]/by_cs[cs]:.1%})")

    print(f"\nWritten to {args.out}")


if __name__ == '__main__':
    main()
