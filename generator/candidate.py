"""candidate.py -- bridges fitness.py's flat genome contract to a real,
shared row-set (design doc §6.2's "candidate solution ... a proposed set
of rows across the tables relevant to one generation target").

This closes the open question raised while explaining fitness.py: does
the branch-distance formula still work when a fact like `lecturesAttended`
is *derived from actual candidate rows* rather than hand-picked as a free
scalar? `fitness.py`'s own genome contract (`{free_variable_name: value}`)
never assumed the caller picks those values out of thin air -- it only
requires *some* concrete value per free variable. `derive_genome()` here
is what a real search loop would call before every `branch_fitness()`:
given one shared `Candidate` (the population individual DynaMOSA would
actually evolve) plus a `focal` row per table (which of the candidate's
own rows this specific branch's scenario is "about") and a `scenario`
dict (bind-parameter values for not_persisted/<placeholder> facts, the
same role sql_compiler.py's bind params play), it walks a compiled
record's `variable_resolution` and computes each leaf variable's REAL
current value the same way sql_compiler.py would compile it to SQL --
just evaluated in-memory against real rows instead.

Usage:
    from candidate import Candidate, derive_genome
    genome = derive_genome(record, candidate, focal, scenario)
    score = branch_fitness(record, genome)   # fitness.py, unchanged
"""
import os
import re
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from fitness import FitnessEvaluationError  # noqa: E402 -- reused, not reimplemented

_PLACEHOLDER_RE = re.compile(r'<([^>]+)>')


class Candidate:
    """A proposed row-set: {table_name: [row_dict, ...]}. Deliberately
    thin -- no schema awareness, no validation -- those are `derive_genome`
    and `fitness.py`'s own constraint-distance functions' job, not this
    class's. Case-insensitive table lookup (candidate_constraint_fitness
    and fk_closure both already have to handle the same real-world casing
    mismatch between ground-truth table names and the schema JSON's own)."""

    def __init__(self):
        self._tables = {}

    def add_row(self, table, row):
        self._tables.setdefault(table.upper(), []).append(row)
        return row

    def rows(self, table):
        return self._tables.get(table.upper(), [])

    def as_dict(self):
        """The {table: [row, ...]} view fitness.py's own constraint-
        distance functions (not_null_distance, unique_distance, ...) take
        directly."""
        return self._tables


def _row_get(row, column, table_for_error=None):
    """Case-insensitive column lookup: ground-truth resolutions carry
    lowercased table.column names (compile_constraints.py's own
    true_pairs()), but real rows are built with whatever casing the
    schema/candidate actually uses -- matched case-insensitively, the
    same accommodation fk_closure() and sql_compiler.py's SqlContext
    already make for the identical mismatch."""
    if column in row:
        return row[column]
    lowered = {k.lower(): v for k, v in row.items()}
    if column.lower() not in lowered:
        where = f" in {table_for_error!r}" if table_for_error else ""
        raise FitnessEvaluationError(f"no column {column!r} found{where}: {sorted(row)}")
    return lowered[column.lower()]


def _lookup(focal, table, column):
    row = focal.get(table.upper())
    if row is None:
        raise FitnessEvaluationError(
            f"no focal row given for table {table!r} -- can't read {table}.{column} "
            f"from a candidate with no row there yet")
    return _row_get(row, column, table)


def _find_row_by_pk(candidate, table, pk_column, value):
    for row in candidate.rows(table):
        try:
            if _row_get(row, pk_column) == value:
                return row
        except FitnessEvaluationError:
            continue
    return None


# ---------------------------------------------------------------------------
# derived_aggregate's filter_text: still deliberately informal prose in
# general (compile_constraints.py's own documented choice -- see its
# _try_extract_aggregate_recipe docstring), so only the mechanically
# recognizable conjuncts get turned into a real filter; anything else is
# skipped and reported, never silently assumed to mean "no filter."
# ---------------------------------------------------------------------------
_SIMPLE_EQ_CONJUNCT_RE = re.compile(r'^\s*(?:[\w]+\.)?([\w]+)\s*=\s*(.+?)\s*$')


def _mechanical_filter_predicate(filter_text, scenario):
    """-> (predicate(row) -> bool, [skipped conjunct strings]). Splits on
    ' AND ' (the only combinator actually seen in these facts' filter
    text) and keeps only conjuncts of the plain `COLUMN = VALUE` or
    `COLUMN = <placeholder>` shape; anything else (a join description in
    prose, an IN-subquery description, ...) is reported as skipped rather
    than guessed at, and the resulting predicate is a real over-count on
    exactly the skipped conjuncts' account -- an honest approximation,
    not a silent exact answer."""
    if not filter_text:
        return (lambda row: True), []
    conjuncts = re.split(r'\bAND\b', filter_text, flags=re.I)
    checks = []
    skipped = []
    for c in conjuncts:
        m = _SIMPLE_EQ_CONJUNCT_RE.match(c.strip())
        if not m:
            skipped.append(c.strip())
            continue
        col, raw_val = m.group(1), m.group(2).strip()
        ph = _PLACEHOLDER_RE.fullmatch(raw_val)
        if ph:
            if ph.group(1) not in scenario:
                raise FitnessEvaluationError(
                    f"filter text needs scenario binding {raw_val!r}, none supplied")
            expected = scenario[ph.group(1)]
        else:
            expected = raw_val.strip("'\"")
            # numeric literals compare as numbers, not strings
            try:
                expected = int(expected)
            except ValueError:
                try:
                    expected = float(expected)
                except ValueError:
                    pass
        checks.append((col, expected))

    def predicate(row):
        for col, expected in checks:
            try:
                if _row_get(row, col) != expected:
                    return False
            except FitnessEvaluationError:
                return False  # row doesn't even have this column -- can't match
        return True

    return predicate, skipped


def _raw_sql_boolean_value(node, candidate, scenario, warnings):
    """The one resolution kind with no structured tree to walk at all
    (generator/compile_constraints.py's own documented escape hatch,
    §13.17) -- evaluated the only honest way available: materialize just
    the tables it names into a throwaway in-memory SQLite database and
    run the real query. This is exactly the fallback §6.5 itself names
    ("EvoSQL's alternative approach ... worth considering") applied to
    the one construct that actually needs it, not adopted program-wide."""
    conn = sqlite3.connect(':memory:')
    cur = conn.cursor()
    for table in node['tables']:
        cols = sorted({c for row in candidate.rows(table) for c in row})
        if not cols:
            cols = ['_dummy']
        cur.execute(f'CREATE TABLE {table} ({", ".join(cols)})')
        for row in candidate.rows(table):
            placeholders = ', '.join('?' for _ in cols)
            cur.execute(f'INSERT INTO {table} ({", ".join(cols)}) VALUES ({placeholders})',
                        [row.get(c) for c in cols])
    sql = _PLACEHOLDER_RE.sub(lambda m: str(scenario.get(m.group(1), 'NULL')), node['sql_template'])
    try:
        cur.execute(f'SELECT ({sql})')
        result = cur.fetchone()[0]
    except sqlite3.Error as e:
        raise FitnessEvaluationError(f"raw_sql_boolean query failed against the materialized candidate: {e}")
    finally:
        conn.close()
    return bool(result)


def derive_value(var_name, node, candidate, focal, scenario, warnings=None):
    """The in-memory-row-set analogue of fitness.py's evaluate_resolution
    and sql_compiler.py's compile_resolution_as_value: given a *real*
    candidate (not a hand-picked scalar), compute this leaf variable's
    actual current value."""
    warnings = warnings if warnings is not None else []
    kind = node.get('kind')
    if kind == 'schema_column':
        return _lookup(focal, node['table'], node['column'])
    if kind == 'null_check':
        return _lookup(focal, node['table'], node['column']) is not None
    if kind == 'any_not_null':
        return any(_lookup(focal, c['table'], c['column']) is not None for c in node['columns'])
    if kind in ('join_lookup', 'join_null_check'):
        local_val = _lookup(focal, node['via']['local_table'], node['via']['local_column'])
        target_row = _find_row_by_pk(candidate, node['result_table'], node['result_column'], local_val) \
            if local_val is not None else None
        # a join *to* a row keyed by result_column only works when
        # result_column is genuinely that table's own identifying key;
        # for the (common) case where it's the same key the FK points at,
        # this is exactly right -- documented as the scope this bridges,
        # not a general arbitrary-join evaluator.
        value = _row_get(target_row, node['result_column']) if target_row else None
        return value if kind == 'join_lookup' else value is not None
    if kind == 'regex_match':
        val = _lookup(focal, node['value_column']['table'], node['value_column']['column'])
        pattern = _lookup(focal, node['pattern_column']['table'], node['pattern_column']['column'])
        if val is None or pattern is None:
            return False
        try:
            return re.search(pattern, str(val)) is not None
        except re.error as e:
            raise FitnessEvaluationError(f"{var_name!r}'s pattern column holds an invalid regex: {e}")
    if kind == 'derived_aggregate':
        predicate, skipped = _mechanical_filter_predicate(node.get('filter_text'), scenario)
        if skipped:
            warnings.append(f"{var_name}: derived_aggregate filter has prose this bridge can't "
                             f"mechanically apply, counted without it: {skipped}")
        tables = [t.strip() for t in node['table'].split(',')]
        rows = candidate.rows(tables[0])
        matching = [r for r in rows if predicate(r)]
        if node.get('value_column'):
            _, col = node['value_column'].split('.')
            return sum((_row_get(r, col) or 0) for r in matching)
        return len(matching)
    if kind == 'exists':
        table = (node.get('candidate_tables') or [None])[0]
        if table is None:
            return False
        return len(candidate.rows(table)) > 0
    if kind == 'raw_sql_boolean':
        return _raw_sql_boolean_value(node, candidate, scenario, warnings)
    if kind == 'not_persisted':
        if var_name not in scenario:
            raise FitnessEvaluationError(
                f"{var_name!r} is not_persisted (a scenario/runtime parameter) -- "
                f"no value supplied in `scenario`")
        return scenario[var_name]
    if kind == 'derived':
        # The generic catch-all classify_derived() itself couldn't pattern-
        # match into any structured shape (§7b's "Compound / Unclassified
        # Derivation" category, ~7% of ground truth) -- there is no more
        # structure here for this bridge to compute from than there was
        # for classify_derived to begin with, so this is a real, expected
        # limitation, not a missing case to add. sql_compiler.py's own
        # equivalent (compile_value_expr) emits a NULL placeholder with a
        # warning rather than refusing outright; this bridge raises
        # instead, deliberately, since a fitness *value* silently
        # standing in for "unknown" would corrupt the branch-distance
        # arithmetic (NULL has no defined distance), where SQL's own NULL
        # semantics at least make the resulting query visibly non-answering.
        raise FitnessEvaluationError(
            f"{var_name!r} is an unclassified 'derived' fact (compile_constraints.py's own "
            f"classify_derived never matched it to a structured shape) -- no mechanical value "
            f"to derive from a candidate; needs a human or a more targeted classifier pass, "
            f"the same as it does for SQL compilation")
    raise FitnessEvaluationError(f"derive_value has no handling for resolution kind {kind!r} ({var_name!r})")


def derive_genome(record, candidate, focal, scenario, warnings=None):
    """Walks `record['variable_resolution']`, recursing through
    `substituted_decision`/`literal_via_upstream_branch` chains (those
    are formulas fitness.py's own evaluate_resolution already knows how
    to recompute from their free variables -- not genes themselves, so
    not populated here), and returns a genome with every true leaf
    variable's *real*, candidate-derived value -- ready to hand straight
    to `fitness.branch_fitness` unchanged."""
    warnings = warnings if warnings is not None else []
    genome = {}

    def walk(var_name, node):
        kind = node.get('kind')
        if kind == 'literal':
            return
        if kind == 'substituted_decision':
            for fv, sub in node.get('free_variable_resolutions', {}).items():
                walk(fv, sub)
            return
        if kind == 'literal_via_upstream_branch':
            return
        if kind in ('schema_gap', 'code_external', 'unresolved', 'chained_decision_output'):
            return  # never a real gene -- fitness.py itself raises if this is actually needed
        genome[var_name] = derive_value(var_name, node, candidate, focal, scenario, warnings)

    for var, node in record.get('variable_resolution', {}).items():
        walk(var, node)
    return genome


if __name__ == '__main__':
    # Two checks: (1) the flagship worked example, this time with a REAL
    # candidate row-set (including noise rows a correct filter must
    # exclude) rather than a hand-picked scalar -- the concrete answer to
    # "does the fitness design still work once real rows, not abstract
    # numbers, are behind it"; (2) a full-corpus sweep building a
    # (deliberately minimal, auto-generated) candidate for every currently
    # compiled record, to see how far genome derivation actually reaches
    # without per-record hand-holding.
    import json
    from fitness import branch_fitness, FitnessEvaluationError

    compiled = json.load(open(os.path.join(HERE, 'compiled_constraints.json')))
    rule1 = next(r for r in compiled if r['record_id'].endswith('Decision_AttendanceEligibility_Rule_1'))
    rule2 = next(r for r in compiled if r['record_id'].endswith('Decision_AttendanceEligibility_Rule_2'))

    c = Candidate()
    STUDENT, OFFERING = 2024001, 5001
    for i in range(45):
        c.add_row('LECTURE', {'LECTURE_ID': 1000 + i, 'OFFER_ID': OFFERING})
    for i in range(40):
        c.add_row('STUDENT_ATTENDANCE', {'LECTURE_ID': 1000 + i, 'ROLL_NO': STUDENT, 'ATTEND_FLAG': 'Y'})
    for i in range(40, 43):  # noise: a different student, must be excluded
        c.add_row('STUDENT_ATTENDANCE', {'LECTURE_ID': 1000 + i, 'ROLL_NO': 9999999, 'ATTEND_FLAG': 'Y'})
    for i in range(43, 45):  # noise: this student, but absent, must be excluded
        c.add_row('STUDENT_ATTENDANCE', {'LECTURE_ID': 1000 + i, 'ROLL_NO': STUDENT, 'ATTEND_FLAG': 'N'})
    scenario = {'student': STUDENT, 'this course offering': OFFERING}
    warnings = []
    genome = derive_genome(rule2, c, {}, scenario, warnings)
    print(f"Derived from {sum(len(v) for v in c.as_dict().values())} real candidate rows: {genome} "
          f"(expect lecturesAttended=40, lecturesHeldForOffering=45 -- noise rows correctly excluded)")
    print(f"Honest warnings about prose this bridge couldn't mechanically filter on: {warnings}")
    assert genome == {'lecturesAttended': 40, 'lecturesHeldForOffering': 45}
    f = branch_fitness(rule2, genome)
    print(f"branch_fitness(Rule_2) on the derived genome = {f:.4f} "
          f"(matches fitness.py's own hand-picked-scalar test exactly)")
    assert abs(f - 1.8163265306122448) < 1e-9

    # a materializable candidate: reduce attendance below the threshold
    # and confirm fitness reaches exactly 0 -- not just "close"
    c2 = Candidate()
    for i in range(45):
        c2.add_row('LECTURE', {'LECTURE_ID': 1000 + i, 'OFFER_ID': OFFERING})
    for i in range(35):
        c2.add_row('STUDENT_ATTENDANCE', {'LECTURE_ID': 1000 + i, 'ROLL_NO': STUDENT, 'ATTEND_FLAG': 'Y'})
    genome2 = derive_genome(rule2, c2, {}, scenario)
    assert branch_fitness(rule2, genome2) == 0.0
    assert branch_fitness(rule1, derive_genome(rule1, c, {}, scenario)) == 0.0
    print("Flagship real-candidate self-checks passed.")

    print()
    print("Full-corpus sweep: how far genome derivation reaches with a minimal auto-built "
          "candidate (see generator/README.md's 'candidate.py' section for the honest tally).")
    ok, errs = 0, {}

    def leaf_kinds(var_name, node, out, blocking):
        kind = node.get('kind')
        if kind == 'substituted_decision':
            for fv, sub in node.get('free_variable_resolutions', {}).items():
                leaf_kinds(fv, sub, out, blocking)
        elif kind not in ('literal', 'literal_via_upstream_branch') and kind not in blocking:
            out.append((var_name, kind, node))

    blocking_kinds = {'schema_gap', 'code_external', 'unresolved', 'chained_decision_output'}
    for rec in compiled:
        leaves = []
        for var, node in rec.get('variable_resolution', {}).items():
            leaf_kinds(var, node, leaves, blocking_kinds)
        auto = Candidate()
        focal = {}
        auto_scenario = {'__today__': 20000}
        for var, kind, node in leaves:
            for field in ('filter_text', 'sql_template'):
                for m in _PLACEHOLDER_RE.finditer(node.get(field) or ''):
                    auto_scenario.setdefault(m.group(1), 1)

        def ensure_row(table, col=None, val=1):
            row = focal.get(table.upper())
            if row is None:
                row = {}
                focal[table.upper()] = row
                auto.add_row(table, row)
            if col:
                row[col] = val
            return row

        for var, kind, node in leaves:
            if kind in ('schema_column', 'null_check'):
                ensure_row(node['table'], node['column'], 1)
            elif kind == 'any_not_null':
                for x in node['columns']:
                    ensure_row(x['table'], x['column'], 1)
            elif kind in ('join_lookup', 'join_null_check'):
                ensure_row(node['via']['local_table'], node['via']['local_column'], 42)
                ensure_row(node['result_table'], node['result_column'], 42)
            elif kind == 'regex_match':
                ensure_row(node['value_column']['table'], node['value_column']['column'], 'abc')
                ensure_row(node['pattern_column']['table'], node['pattern_column']['column'], 'a.*')
            elif kind == 'derived_aggregate':
                tables = [t.strip() for t in node['table'].split(',')]
                for i in range(1, 4):
                    row = {'X': i}
                    if node.get('value_column'):
                        row[node['value_column'].split('.')[1]] = 10
                    auto.add_row(tables[0], row)
                for t in tables[1:]:
                    auto.add_row(t, {'X': 0})
            elif kind == 'exists':
                table = (node.get('candidate_tables') or [None])[0]
                if table:
                    auto.add_row(table, {'X': 1})
            elif kind == 'raw_sql_boolean':
                for t in node['tables']:
                    cols = set(re.findall(r'\b\w+\.(\w+)\b', node['sql_template']))
                    auto.add_row(t, {col: 1 for col in cols} or {'X': 1})
            elif kind == 'not_persisted':
                auto_scenario[var] = 1
        try:
            g = {'__today__': 20000}
            g.update(derive_genome(rec, auto, focal, auto_scenario))
            branch_fitness(rec, g)
            ok += 1
        except FitnessEvaluationError as e:
            errs.setdefault(str(e).split(' -- ')[0][:70], []).append(rec['record_id'])
        except Exception as e:
            errs.setdefault(f'UNEXPECTED {type(e).__name__}', []).append(rec['record_id'])

    print(f"Evaluable via a real (if minimal) candidate row-set: {ok}/{len(compiled)} ({ok/len(compiled)*100:.1f}%)")
    for k, v in sorted(errs.items(), key=lambda kv: -len(kv[1])):
        print(f"  {len(v):3} {k}")
