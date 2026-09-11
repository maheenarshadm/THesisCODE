"""fitness.py -- the branch-distance fitness function (design doc §6.3).

Turns one compiled branch record (generator/compiled_constraints.json,
compile_constraints.py's own output) plus a candidate *genome* into a
single non-negative fitness score: 0 means the branch's condition holds
(and, for FIRST/UNIQUE hit policy, every earlier row's condition does
not) -- exactly the AVM/GA gradient §6.3 designs, computed entirely
in-memory with no DB round-trip (§6.5's own requirement).

Genome representation (deliberate design choice, not yet stated
elsewhere in the repo -- see generator/README.md's "Fitness function"
section for the reasoning): a flat dict `{free_variable_name: value}`,
one entry per *leaf* free variable a branch's condition and its DRD
substitution chain bottom out at (the same free variables
`compile_constraints.py`'s own `variable_resolution` dict is keyed by,
after fully unwinding any `substituted_decision`). This mirrors EvoSQL's
own genome choice (§8: a proposed set of concrete column-level values)
rather than a fully materialized row set -- turning a proposed genome
into actual INSERT-able rows (e.g. how many STUDENT_ATTENDANCE rows
realize a chosen `lecturesAttended` count) is a separate, deterministic
materialization step (§6.5), not part of fitness evaluation. This keeps
the search loop's inner loop cheap (arithmetic over a handful of numbers,
strings, and booleans) and defers the one thing that genuinely can't be
decided in the abstract -- the exact rows an aggregate/exists/join fact's
still-informal filter_text describes -- to the point where a concrete
schema and scenario are actually being committed to disk.

Usage:
    from fitness import branch_fitness
    score = branch_fitness(compiled_record, genome)
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

K = 1.0  # the small constant the base distance table uses for a boolean/equality mismatch


class FitnessEvaluationError(Exception):
    """Raised when a branch can't be evaluated at all from a genome --
    e.g. a required gene is missing, or the branch depends on a FEEL
    construct (a `call`, an `opaque_formula`) this evaluator doesn't
    give a numeric meaning to. Never silently returns a wrong number for
    an unsupported case."""


# ---------------------------------------------------------------------------
# 1. Resolving a free variable's *current value* from the genome, walking
#    the same variable_resolution structure compile_constraints.py built
#    (substituted_decision chains inlined, everything else a genome lookup)
# ---------------------------------------------------------------------------

def evaluate_resolution(var_name, node, genome):
    """The in-memory analogue of sql_compiler.py's compile_resolution_as_value
    -- same resolution-kind dispatch, but returns a Python value from the
    genome instead of emitting SQL. Every *leaf* kind (schema_column,
    null_check, any_not_null, join_lookup, join_null_check,
    derived_aggregate, exists, regex_match, raw_sql_boolean, not_persisted)
    is, by design, just a genome lookup -- what varies is only how that
    gene eventually gets materialized into real rows (§6.5), not how the
    search reasons about its current candidate value. Only the two
    DRD-substitution kinds (`substituted_decision`, `literal_via_upstream_
    branch`) recurse instead of looking anything up, since they're not
    genes themselves -- they're formulas over genes."""
    kind = node.get('kind')
    if kind == 'literal':
        return node['value']
    if kind == 'literal_via_upstream_branch':
        return evaluate_expression(node['value'], {}, genome)
    if kind == 'substituted_decision':
        return evaluate_expression(node['expression'], node.get('free_variable_resolutions', {}), genome)
    if kind in ('schema_gap', 'code_external', 'unresolved', 'chained_decision_output'):
        # Never a legitimate gene, whether or not a genome happens to
        # carry a stray value under this name: these kinds mean there is
        # structurally no way to resolve this fact at all (no schema
        # column, or a dependency this compiler couldn't ground). For a
        # branch's *own* condition, compile_constraints.py already
        # refuses to compile it if this happened there (the same
        # invariant sql_compiler.py's own compile_value_expr relies on);
        # the one place this legitimately shows up is a FIRST/UNIQUE
        # suppression term for an *earlier* row whose own free variable
        # was never resolvable -- surfaced loudly here too, rather than
        # silently accepting a genome value that would be meaningless.
        raise FitnessEvaluationError(
            f"{var_name!r} has no legitimate value to evaluate -- its resolution kind "
            f"is {kind!r}, a structurally unresolvable fact, not a gene")
    # Every other kind is a leaf gene -- schema_column, null_check,
    # any_not_null, join_lookup, join_null_check, derived_aggregate,
    # exists, regex_match, raw_sql_boolean, not_persisted.
    if var_name not in genome:
        raise FitnessEvaluationError(
            f"genome is missing required gene {var_name!r} (resolution kind={kind!r})")
    return genome[var_name]


_ARITH = {'+': lambda a, b: a + b, '-': lambda a, b: a - b,
          '*': lambda a, b: a * b, '/': lambda a, b: a / b}


def evaluate_expression(node, resolution_map, genome):
    """Arithmetic-evaluates one FEEL expression tree (feel_parser.py's own
    vocabulary: variable/literal/call/opaque_formula leaves, +-*/ and
    if/then/else internal nodes) against a genome, resolving each
    `variable` leaf through `resolution_map` (a substituted_decision's own
    free_variable_resolutions) exactly the way sql_compiler.py's
    compile_value_expr does for SQL text instead of a number."""
    if not isinstance(node, dict):
        raise FitnessEvaluationError(f"not a valid expression node: {node!r}")
    kind = node.get('kind')
    if kind == 'literal':
        return node['value']
    if kind == 'variable':
        ref = node['ref']
        if ref not in resolution_map:
            raise FitnessEvaluationError(
                f"expression references {ref!r} with no resolution recorded for it")
        return evaluate_resolution(ref, resolution_map[ref], genome)
    if kind == 'call':
        name = node.get('name')
        if name == 'today' and not node.get('args'):
            # Not a real gene either -- the same "genuine runtime/scenario
            # parameter, not a stored value" case sql_compiler.py's
            # not_persisted handling already treats as a bind parameter.
            # A scenario-level date convention, supplied once per search
            # run rather than per branch, under a reserved genome key.
            if '__today__' not in genome:
                raise FitnessEvaluationError(
                    "genome is missing the scenario-level '__today__' gene FEEL's today() needs")
            return genome['__today__']
        raise FitnessEvaluationError(
            f"FEEL built-in call {name!r} has no fitness-evaluator "
            f"meaning yet -- not silently treated as zero")
    if kind == 'opaque_formula':
        raise FitnessEvaluationError(
            f"opaque (unparsed) FEEL formula can't be evaluated: {node.get('feel_text', '')[:80]!r}")
    op = node.get('op')
    if op in _ARITH:
        return _ARITH[op](evaluate_expression(node['left'], resolution_map, genome),
                           evaluate_expression(node['right'], resolution_map, genome))
    if op == 'if':
        cond_true = distance_to_true(node['cond'], resolution_map, genome) == 0
        branch = node['then'] if cond_true else node['else']
        return evaluate_expression(branch, resolution_map, genome)
    if op is not None:
        # A comparison/logical node (=, <, and, in, IS NULL's own '=' form,
        # ...) used in a *value* position -- e.g. CHECK's own "(a IS NULL)
        # <> (b IS NULL)", where each side is itself a boolean sub-
        # expression being XOR'd via '<>', not a number to add/subtract.
        # Evaluated as True/False via whether its own distance-to-true is
        # already zero, then fed back through the ordinary comparison
        # machinery by whichever caller wanted a value here.
        return distance_to_true(node, resolution_map, genome) == 0
    raise FitnessEvaluationError(f"expression node with unhandled shape: {node!r}")


def _leaf_value(node, resolution_map, genome):
    """A comparison/in/between operand: either a variable (resolved
    through the genome) or an arithmetic sub-expression/literal."""
    return evaluate_expression(node, resolution_map, genome)


# ---------------------------------------------------------------------------
# 2. Branch distance -- §6.3's base table, plus AND/OR/NOT/IN/BETWEEN
#    composition, plus the FIRST/UNIQUE hit-policy suppression term (the
#    same de Morgan-as-distance idea, reused rather than re-derived).
# ---------------------------------------------------------------------------

_NEGATED_OP = {'=': '!=', '!=': '=', '<': '>=', '>=': '<', '<=': '>', '>': '<='}


def _numeric(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _comparison_distance_true(op, a, b):
    """§6.3's base table, desired outcome = the comparison is TRUE."""
    if op == '=':
        return abs(a - b) if _numeric(a) and _numeric(b) else (0.0 if a == b else K)
    if op == '!=':
        return K if a == b else 0.0
    if op == '<':
        return (a - b) + K if a >= b else 0.0
    if op == '<=':
        return (a - b) + K if a > b else 0.0
    if op == '>':
        return (b - a) + K if a <= b else 0.0
    if op == '>=':
        return (b - a) + K if a < b else 0.0
    raise FitnessEvaluationError(f"unhandled comparison operator {op!r}")


def distance_to_true(node, resolution_map, genome):
    """Distance for `node` (a condition, or a plain boolean-valued leaf
    used as one) to evaluate to TRUE."""
    if not isinstance(node, dict):
        raise FitnessEvaluationError(f"not a valid condition node: {node!r}")
    kind = node.get('kind')
    if kind == 'literal':
        return 0.0 if node['value'] else K
    if kind == 'variable':
        # A bare boolean-valued fact used directly as a rule's whole
        # condition (no comparison wrapper) -- e.g. a null_check/exists/
        # raw_sql_boolean gene consumed as-is.
        return 0.0 if evaluate_resolution(node['ref'], resolution_map.get(node['ref'], node), genome) else K
    op = node.get('op')
    if op in _NEGATED_OP:
        a = _leaf_value(node['left'], resolution_map, genome)
        b = _leaf_value(node['right'], resolution_map, genome)
        return _comparison_distance_true(op, a, b)
    if op == 'and':
        return sum(distance_to_true(c, resolution_map, genome) for c in node['clauses'])
    if op == 'or':
        return min(distance_to_true(c, resolution_map, genome) for c in node['clauses'])
    if op == 'not':
        return distance_to_false(node['clause'], resolution_map, genome)
    if op == 'in':
        left = node['left']
        return min(_comparison_distance_true('=', _leaf_value(left, resolution_map, genome),
                                              _leaf_value(v, resolution_map, genome))
                    for v in node['values'])
    if op == 'between':
        low = _leaf_value(node['low'], resolution_map, genome)
        high = _leaf_value(node['high'], resolution_map, genome)
        left = _leaf_value(node['left'], resolution_map, genome)
        return (_comparison_distance_true('>=', left, low)
                + _comparison_distance_true('<=', left, high))
    raise FitnessEvaluationError(f"unhandled condition node: {node!r}")


def distance_to_false(node, resolution_map, genome):
    """Distance for `node` to evaluate to FALSE -- the FIRST/UNIQUE
    hit-policy suppression term ("make this earlier row's condition not
    fire") uses this directly, and it's also how `not(...)` and `and`/`or`
    composition are defined, so it's implemented as its own mutually
    recursive pair with distance_to_true rather than by literally
    rewriting the tree with De Morgan's laws first."""
    if not isinstance(node, dict):
        raise FitnessEvaluationError(f"not a valid condition node: {node!r}")
    kind = node.get('kind')
    if kind == 'literal':
        return K if node['value'] else 0.0
    if kind == 'variable':
        return K if evaluate_resolution(node['ref'], resolution_map.get(node['ref'], node), genome) else 0.0
    op = node.get('op')
    if op in _NEGATED_OP:
        a = _leaf_value(node['left'], resolution_map, genome)
        b = _leaf_value(node['right'], resolution_map, genome)
        return _comparison_distance_true(_NEGATED_OP[op], a, b)
    if op == 'and':
        return min(distance_to_false(c, resolution_map, genome) for c in node['clauses'])
    if op == 'or':
        return sum(distance_to_false(c, resolution_map, genome) for c in node['clauses'])
    if op == 'not':
        return distance_to_true(node['clause'], resolution_map, genome)
    if op == 'in':
        left = node['left']
        return sum(_comparison_distance_true('!=', _leaf_value(left, resolution_map, genome),
                                              _leaf_value(v, resolution_map, genome))
                   for v in node['values'])
    if op == 'between':
        low = _leaf_value(node['low'], resolution_map, genome)
        high = _leaf_value(node['high'], resolution_map, genome)
        left = _leaf_value(node['left'], resolution_map, genome)
        # false means outside the range -- either side is enough (OR)
        return min(_comparison_distance_true('<', left, low),
                    _comparison_distance_true('>', left, high))
    raise FitnessEvaluationError(f"unhandled condition node: {node!r}")


def normalize(d):
    """Squash an unbounded distance into [0,1) -- §6.3's own normalize-
    then-sum approach (matching SchemaAnalyst), so no single term (a
    percentage-scale gap vs. a 0/1 boolean gap) dominates or gets lost."""
    return d / (d + 1.0)


# ---------------------------------------------------------------------------
# 3. Whole-branch fitness: this row's own condition + FIRST/UNIQUE
#    suppression of every earlier row (§6.3's dominant difficulty driver,
#    82.8% of decision tables per §7a).
# ---------------------------------------------------------------------------

def branch_fitness(record, genome):
    """0.0 means the genome makes this compiled branch's target rule fire
    (its own condition true, and -- for FIRST/UNIQUE hit policy -- every
    earlier row's condition false); positive otherwise, with a gradient
    AVM/GA can climb. `record` is one entry of compiled_constraints.json;
    `genome` is {free_variable_name: value}."""
    resolution_map = record.get('variable_resolution', {})
    own = distance_to_true(record['condition'], resolution_map, genome)
    # §6.3: "squash each into [0,1) before summing" -- normalized per
    # earlier-row term, not the raw sum of all of them, so one very
    # distant earlier row can't swamp the others' own gradients.
    suppression = sum(
        normalize(distance_to_false(row['condition'], resolution_map, genome))
        for row in record.get('hit_policy_context', {}).get('earlier_rows', [])
    )
    return normalize(own) + suppression


# ---------------------------------------------------------------------------
# 4. Schema/DB constraint terms (§6.3's "combining with database integrity
#    constraints" section) -- the same base distance table, applied to a
#    *candidate row set* instead of a DMN condition tree. This is a
#    genuinely different shape of input than the DMN term needs: NOT NULL
#    is about one row in isolation, but UNIQUE/PK and FK are properties of
#    a row *against the rest of the candidate*, so these functions take
#    `candidate_rows: {table_name: [ {column: value, ...}, ... ]}` rather
#    than the flat genome dict branch_fitness uses. Building both views
#    consistent with each other (the genome's variable values matching up
#    with specific columns in candidate_rows) is a materialization-time
#    concern (§6.5), not this module's.
#
# Scope, stated plainly: needs `fk_columns` (local column -> ref
# table.column) and accurate `null_false` in the case-study's schema JSON
# (all_schema_extraction/.../output/<cs>_schema_full.json). As of
# 2026-09-11 this is only true for FLEX2 -- its own parser was fixed
# while building this (NOT NULL was being missed entirely, and per-column
# FK detail was being discarded down to just target-table names, exactly
# like the other three case studies' parsers still do). OpenMRS/Spree/
# jBilling's FK-distance term isn't computable yet for that reason; NOT
# NULL and UNIQUE terms work for them already (their own `null_false`/
# `pk`/`indexes` data was never broken the way FLEX2's was).
# ---------------------------------------------------------------------------

def not_null_distance(row, table, schema):
    """Sum, over every column this table declares NOT NULL, the boolean
    base-table distance (§6.3: "boolean flag -- K if not the desired
    value") for that column actually being non-null in this one
    candidate row."""
    info = schema.get(table, {})
    return sum(K for col, meta in info.get('columns', {}).items()
               if meta.get('null_false') and row.get(col) is None)


def _unique_key_sets(schema, table):
    info = schema.get(table, {})
    keys = []
    pk = info.get('pk')
    if pk:
        keys.append(pk if isinstance(pk, list) else [pk])
    for idx in info.get('indexes', []):
        if idx.get('unique'):
            keys.append(idx['cols'])
    return keys


def unique_distance(rows, table, schema):
    """UNIQUE/PK distance across every row this table's candidate proposes:
    §6.3 calls this "a distance against existing/sibling row values." A
    row with a NULL in the key is never a collision (standard SQL
    semantics -- NULLs are never equal to each other for uniqueness
    purposes); each extra row sharing an otherwise-identical key beyond
    the first contributes one K, the same boolean-mismatch unit the base
    table already uses elsewhere, rather than a fabricated numeric
    distance a duplicate key has no natural graduated form for."""
    d = 0.0
    for cols in _unique_key_sets(schema, table):
        seen = {}
        for row in rows:
            key = tuple(row.get(c) for c in cols)
            if any(v is None for v in key):
                continue
            seen[key] = seen.get(key, 0) + 1
        d += sum(K * (count - 1) for count in seen.values() if count > 1)
    return d


def fk_distance(row, table, schema, candidate_rows):
    """FK distance for one row: §6.3 -- "a distance measuring whether the
    value exists in the parent table," checked against the candidate's
    own in-memory rows (§6.5: no live DB needed during search). A NULL FK
    column is never a violation on its own (a nullable FK left unset is
    valid unless a separate NOT NULL constraint also applies -- that's
    not_null_distance's job, not this one's, so the two terms don't
    double-count the same gap)."""
    info = schema.get(table, {})
    fk_cols = info.get('fk_columns')
    if fk_cols is None:
        raise FitnessEvaluationError(
            f"{table!r}'s schema entry has no 'fk_columns' detail -- FK distance isn't "
            f"computable for this case study yet (see this module's own scope note)")
    d = 0.0
    for fk in fk_cols:
        val = row.get(fk['column'])
        if val is None:
            continue
        parent_values = {r.get(fk['ref_column']) for r in candidate_rows.get(fk['ref_table'], [])}
        if val not in parent_values:
            d += K
    return d


# --- CHECK constraints: a minimal parser for the SQL boolean grammar
# actually surveyed across the program's own declared CHECK bodies
# (Spree's 3: "amount <= 0", "amount >= 0", "(line_item_id IS NULL) <>
# (fulfillment_id IS NULL)") -- deliberately not a general SQL expression
# parser, the same targeted-not-general discipline feel_parser.py used
# for FEEL. Reuses distance_to_true/distance_to_false directly once
# parsed into this module's own node vocabulary -- no new distance logic
# needed, since a CHECK constraint is structurally the same kind of
# boolean tree a DMN condition is.
_CHECK_TOKEN_RE = __import__('re').compile(
    r"'[^']*'|<=|>=|<>|!=|=|<|>|\(|\)|\bIS\s+NOT\s+NULL\b|\bIS\s+NULL\b|\bAND\b|\bOR\b|[\w.]+",
    __import__('re').I)


def parse_check_expression(text):
    """CHECK body -> this module's condition-node vocabulary. Supports
    exactly what's been surveyed: `column OP literal`, `column IS [NOT]
    NULL`, parenthesized sub-expressions, and AND/OR/<>/!= combining them.
    Raises FitnessEvaluationError (not a silent guess) on anything else."""
    tokens = [t for t in _CHECK_TOKEN_RE.findall(text) if t.strip()]
    pos = [0]

    def peek():
        return tokens[pos[0]] if pos[0] < len(tokens) else None

    def advance():
        t = tokens[pos[0]]
        pos[0] += 1
        return t

    def parse_atom():
        t = peek()
        if t is None:
            raise FitnessEvaluationError(f"unexpected end of CHECK expression: {text!r}")
        if t == '(':
            advance()
            node = parse_or()
            if peek() != ')':
                raise FitnessEvaluationError(f"unbalanced parens in CHECK expression: {text!r}")
            advance()
            return node
        advance()
        if t.upper() in ('IS NULL', 'IS NOT NULL'):
            raise FitnessEvaluationError(f"'IS [NOT] NULL' with no preceding operand: {text!r}")
        # a column reference or a literal
        if t.startswith("'"):
            return {'kind': 'literal', 'value': t.strip("'"), 'type': 'string'}
        try:
            return {'kind': 'literal', 'value': float(t) if '.' in t else int(t), 'type': 'number'}
        except ValueError:
            return {'kind': 'variable', 'ref': t}

    def parse_comparison():
        left = parse_atom()
        t = peek()
        if t and t.upper() in ('IS NULL', 'IS NOT NULL'):
            advance()
            node = {'op': '=', 'left': left, 'right': {'kind': 'literal', 'value': None, 'type': 'null'}}
            return node if t.upper() == 'IS NULL' else {'op': 'not', 'clause': node}
        if t in ('=', '<', '>', '<=', '>=', '<>', '!='):
            advance()
            right = parse_atom()
            return {'op': '!=' if t == '<>' else t, 'left': left, 'right': right}
        return left  # a bare boolean-valued reference, no comparison

    def parse_and():
        node = parse_comparison()
        while peek() and peek().upper() == 'AND':
            advance()
            node = {'op': 'and', 'clauses': [node, parse_comparison()]}
        return node

    def parse_or():
        node = parse_and()
        while peek() and peek().upper() == 'OR':
            advance()
            node = {'op': 'or', 'clauses': [node, parse_and()]}
        return node

    result = parse_or()
    if pos[0] != len(tokens):
        raise FitnessEvaluationError(f"trailing tokens in CHECK expression: {text!r} -> {tokens[pos[0]:]}")
    return result


def check_distance(row, table, schema):
    """Sum, over every CHECK constraint this table declares, the distance
    for that row's own values to satisfy it -- the same distance_to_true
    the DMN term uses, since a CHECK body is just another boolean tree."""
    info = schema.get(table, {})
    d = 0.0
    genome = {k: v for k, v in row.items()}
    resolution_map = {k: {'kind': 'schema_column'} for k in row}
    for check_text in info.get('checks', []):
        node = parse_check_expression(check_text)
        d += distance_to_true(node, resolution_map, genome)
    return d


def candidate_constraint_fitness(candidate_rows, schema):
    """The full §6.3 constraint term across an entire candidate: every
    row's NOT NULL and CHECK distance, plus each table's UNIQUE/PK
    distance across its own rows, plus each row's FK distance against the
    candidate's own parent rows -- normalized per-term and summed, the
    same convention branch_fitness uses for the DMN term. Meant to be
    added directly to branch_fitness's own return value once a genome and
    a materialized candidate_rows view of it coexist (§6.5's job, not
    yet built) to get §6.3's full combined score."""
    total = 0.0
    for table, rows in candidate_rows.items():
        for row in rows:
            total += normalize(not_null_distance(row, table, schema))
            total += normalize(check_distance(row, table, schema))
            if schema.get(table, {}).get('fk_columns') is not None:
                total += normalize(fk_distance(row, table, schema, candidate_rows))
        total += normalize(unique_distance(rows, table, schema))
    return total


if __name__ == '__main__':
    # A tiny self-check against the flagship attendance worked example
    # (design doc §6.3's own hand-computed numbers), run directly rather
    # than only exercised via a separate test file, so `python3 fitness.py`
    # alone proves the module against the one worked example the whole
    # design traces back to.
    #
    # Note on what's being checked: §6.3's own worked example ("candidate
    # lecturesAttended=40 gives... distance (88.9-80)+1=9.9") illustrates
    # only the base distance table applied to Rule_2's *own* condition --
    # it doesn't include the FIRST/UNIQUE suppression term, since it's a
    # worked example of the distance table, not the full per-branch
    # formula. `branch_fitness` computes the complete formula (own
    # condition + suppression of every earlier row, each normalized
    # separately then summed, per §6.3's own "squash each...before
    # summing" wording) -- checked below at the lower level (own
    # condition distance alone) against the doc's exact 9.9, and at the
    # full-formula level (branch_fitness) for internal consistency
    # (monotonic, and an exact zero at the doc's own "done" point).
    compiled = json.load(open(os.path.join(HERE, 'compiled_constraints.json')))
    rule1 = next(r for r in compiled if r['record_id'] ==
                 'FLEX2::Attendance Eligibility For Final Exam::Decision_AttendanceEligibility_Rule_1')
    rule2 = next(r for r in compiled if r['record_id'] ==
                 'FLEX2::Attendance Eligibility For Final Exam::Decision_AttendanceEligibility_Rule_2')

    genome_40 = {'lecturesAttended': 40, 'lecturesHeldForOffering': 45}
    genome_35 = {'lecturesAttended': 35, 'lecturesHeldForOffering': 45}

    own_40 = distance_to_true(rule2['condition'], rule2['variable_resolution'], genome_40)
    own_35 = distance_to_true(rule2['condition'], rule2['variable_resolution'], genome_35)
    print(f"lecturesAttended=40/45 -> attendancePercentage=88.9, Rule_2 (<80)'s own distance = {own_40} "
          f"(design doc §6.3's own worked example: 9.9)")
    print(f"lecturesAttended=35/45 -> attendancePercentage=77.8, Rule_2 (<80)'s own distance = {own_35} "
          f"(design doc §6.3's own worked example: 0 -- 'done')")
    # 9.9 in the doc's own prose is itself computed from a rounded display
    # value (88.9%, not the exact 88.888...%) -- so a tolerance wide
    # enough to absorb that one-decimal rounding, not exact equality, is
    # the correct check here.
    assert abs(own_40 - 9.9) < 0.02, "Rule_2 @ 40/45's own condition distance did not match §6.3's worked example"
    assert own_35 == 0.0, "Rule_2 @ 35/45's own condition distance should be exactly 0, per §6.3's 'done'"

    # Full-formula checks (own condition + FIRST/UNIQUE suppression of
    # Rule_1, the one earlier row) -- an exact hit still lands at 0.0
    # (Rule_1's >=80 is also cleanly false at 77.8%), and the full score
    # still strictly worsens the further a still-eligible candidate is
    # from the 80% boundary, exactly the gradient AVM/GA needs to climb.
    f40 = branch_fitness(rule2, genome_40)
    f35 = branch_fitness(rule2, genome_35)
    assert f35 == 0.0, "Rule_2 @ 35/45 should be an exact hit (0 fitness) on the full formula too"
    assert branch_fitness(rule1, genome_40) == 0.0, "Rule_1 @ 40/45 (88.9%) should be an exact hit"
    g_both_high = {'lecturesAttended': 44, 'lecturesHeldForOffering': 45}  # 97.8%
    assert branch_fitness(rule2, g_both_high) > f40, "fitness did not worsen for a candidate further from the boundary"

    print(f"Full branch_fitness(Rule_2, 40/45) = {f40:.4f}, (Rule_2, 35/45) = {f35:.4f} -- both consistent.")
    print("All flagship worked-example self-checks passed.")

    # Constraint-term self-check, against FLEX2's real, verified DDL
    # (schemas/flex2/Flex1.sql) and Spree's real declared CHECK bodies.
    flex2_schema = json.load(open(os.path.join(
        HERE, '..', 'all_schema_extraction', 'all_schema_extraction', 'output', 'flex2_schema_full.json')))
    spree_schema = json.load(open(os.path.join(
        HERE, '..', 'all_schema_extraction', 'all_schema_extraction', 'output', 'spree_schema_full.json')))

    complete_row = {'OFFER_ID': 501, 'CAMP_ID': 1, 'SEM_ID': None, 'COURSE_ID': 10, 'SECTION_ID': 2}
    assert not_null_distance(complete_row, 'COURSE_OFFER', flex2_schema) == K
    assert not_null_distance(dict(complete_row, SEM_ID=7), 'COURSE_OFFER', flex2_schema) == 0
    assert unique_distance(
        [{'LECTURE_ID': 101, 'ROLL_NO': 1}, {'LECTURE_ID': 101, 'ROLL_NO': 1}],
        'STUDENT_ATTENDANCE', flex2_schema) == K
    assert unique_distance(
        [{'LECTURE_ID': 101, 'ROLL_NO': 1}, {'LECTURE_ID': 102, 'ROLL_NO': 1}],
        'STUDENT_ATTENDANCE', flex2_schema) == 0
    assert fk_distance({'SEM_ID': 999}, 'COURSE_OFFER', flex2_schema,
                        {'SEMESTER': [{'SEM_ID': 999}]}) == 0
    assert fk_distance({'SEM_ID': 999}, 'COURSE_OFFER', flex2_schema,
                        {'SEMESTER': [{'SEM_ID': 5}]}) == K
    assert check_distance({'amount': -3}, 'spree_discounts', spree_schema) == 0
    assert check_distance({'amount': 5}, 'spree_discounts', spree_schema) > 0
    assert check_distance({'line_item_id': 1, 'fulfillment_id': None},
                           'spree_commission_lines', spree_schema) == 0
    assert check_distance({'line_item_id': 1, 'fulfillment_id': 2},
                           'spree_commission_lines', spree_schema) == K
    print("All schema-constraint self-checks (NOT NULL/UNIQUE/FK/CHECK, real FLEX2+Spree data) passed.")
