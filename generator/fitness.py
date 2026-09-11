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
    raise FitnessEvaluationError(f"expression node with unhandled op {op!r}: {node!r}")


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
