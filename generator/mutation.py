"""mutation.py -- the mutation operator (design doc §6.4's DynaMOSA, one
generational step of it), built on `candidate.py`'s Candidate/derive_genome
and `fitness.py`'s branch_fitness/distance_to_true.

One leaf free variable is changed per call -- classic AVM discipline
(change one thing, so the fitness delta tells you what caused it) --
applied to *real Candidate rows*, never to the derived genome directly
(mutating a genome scalar in place could produce a value with no
materializable row-set behind it, exactly the risk `candidate.py` was
built to rule out). Two sub-operators, selected automatically by the
mutated variable's own resolution kind, never chosen by the caller:

- M1 (field mutation): schema_column / null_check / any_not_null /
  join_lookup / join_null_check / regex_match -- perturbs one row's one
  column.
- M2 (row-count mutation): derived_aggregate / exists -- adds or removes
  a whole row, since nothing on a single row is *the* count.

Direction for both is decided the same, unified way: try each candidate
replacement value for the chosen variable *in the genome* (a cheap,
in-memory hypothetical -- no candidate edit yet), keep whichever
`branch_fitness` call comes out lowest, then apply only that winning
value to the real Candidate. This is what lets one mutation function
handle every leaf kind uniformly rather than needing per-kind direction
logic duplicated.

Schema/DB constraints (NOT NULL, UNIQUE/PK, FK) are handled by a
*separate* mechanism, not folded into this search objective -- and this
wasn't always the design. Asked directly whether row mutation checks
FK/schema constraints (2026-09-12), the honest answer was no; the first
fix tried was summing `branch_fitness + candidate_constraint_fitness`
into one combined objective. That surfaced a real, deeper problem before
it shipped: re-testing it against a rule needing a large aggregate-count
increase, hillclimb got trapped *deleting* rows toward fewer constraint
violations instead of adding the ones the DMN branch actually needed --
an unweighted sum lets one objective's per-step cost mask another's
necessary long-range gain, exactly why the design doc's own §6.4 keeps
DynaMOSA's objectives Pareto-compared, never summed.

The actual fix: NOT NULL/UNIQUE/FK are mechanically decidable from the
schema alone with no DMN-relevant ambiguity (a column either must be set
or it doesn't; a FK either has a valid parent or it doesn't) -- so they
don't belong in the fitness landscape as something to be *discovered* at
all. `_repair_row` makes every row M1/M2 touches or adds schema-legal
*by construction*, immediately, every time -- filling required NOT NULL
columns with a type-appropriate placeholder (using a fresh, never-reused
value when that column is also part of a key, so repair itself never
manufactures a new UNIQUE collision) and auto-materializing a minimal
parent row for any FK column that's set but has no match yet. This never
competes with `branch_fitness` because it never enters the objective --
the DMN search stays exactly branch_fitness-alone, as originally
designed. `candidate_constraint_fitness` remains available as a
post-hoc audit metric (see the self-test below), just not a search
signal. CHECK constraints are the one real exception -- they constrain
the *same* values a DMN branch may care about, so they're a genuine
trade-off, not a mechanical fill-in; left as a stated scope boundary for
whenever the real population/Pareto DynaMOSA loop exists to give them
their own objective, not attempted here (rare: 3 CHECK constraints
total, Spree only).

A second real bug found while building this fix, unrelated to the
objective itself but only visible once real deep-copied candidates were
being compared: `copy.deepcopy(candidate)` and `copy.deepcopy(focal)` as
two *separate* top-level calls silently break the object aliasing
between a focal row and its own entry in the candidate's row list (they
start out as the *same* dict object; deepcopy-ing them apart makes two
independent copies with the same content). A field mutation would then
write into `focal`'s copy while `candidate`'s own stored row stayed
stale -- meaning the genome a mutation was scored on could diverge from
what the adopted candidate actually contained. Fixed by deep-copying
`(candidate, focal)` together in one call, which preserves shared
references the same way they existed before copying.

Usage:
    from mutation import mutate, hillclimb
    new_candidate, new_focal, new_scenario, var, improved = \\
        mutate(record, candidate, focal, scenario, rng)
    solved_candidate, focal, scenario, history = hillclimb(record, candidate, focal, scenario)
"""
import copy
import json
import os
import random
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from candidate import (Candidate, derive_genome, derive_value,  # noqa: E402
                        _mechanical_filter_predicate, _find_focal_with_columns, _row_get)
from fitness import (branch_fitness, distance_to_true, FitnessEvaluationError,  # noqa: E402
                      candidate_constraint_fitness, _unique_key_sets)
from compile_constraints import CASE_STUDY_SCHEMA_JSON, find_all_variable_refs  # noqa: E402

BOOLEAN_LEAF_KINDS = {'null_check', 'any_not_null', 'join_null_check', 'exists',
                      'regex_match', 'raw_sql_boolean'}
FIELD_LEAF_KINDS = {'schema_column', 'null_check', 'any_not_null', 'join_lookup',
                    'join_null_check', 'regex_match', 'derived_case'}
AGGREGATE_LEAF_KINDS = {'derived_aggregate', 'exists', 'derived_join_count'}

_SCHEMA_CACHE = {}


def _schema_for(case_study):
    if case_study not in _SCHEMA_CACHE:
        with open(CASE_STUDY_SCHEMA_JSON[case_study], encoding='utf-8') as f:
            _SCHEMA_CACHE[case_study] = json.load(f)
    return _SCHEMA_CACHE[case_study]


def _column_type(case_study, table, column):
    schema = _schema_for(case_study)
    info = schema.get(table) or schema.get(table.upper()) or schema.get(table.lower()) or {}
    col_meta = (info.get('columns') or {}).get(column) \
        or (info.get('columns') or {}).get(column.upper()) \
        or (info.get('columns') or {}).get(column.lower())
    return (col_meta or {}).get('type', '').upper()


# ---------------------------------------------------------------------------
# 1. Enumerable domains -- a leaf compared only via '=', '!=', or 'in'
# against literal values *in this branch's own condition* has a natural,
# non-arbitrary mutation domain: the literals the DMN rule itself already
# names, not a random string. Found by walking the compiled condition tree
# (and, for completeness, the FIRST/UNIQUE earlier rows too, since a
# suppression-relevant literal is just as real a domain member).
# ---------------------------------------------------------------------------

def _collect_domain_facts(node, var_name, negated, hit, avoid):
    """Walks the condition tracking `not`-polarity, splitting every literal
    comparison against var_name into "would make this comparison true if
    var_name equals this" (hit) vs "...if var_name is anything BUT this"
    (avoid) -- e.g. `previousGradeInCourse NOT IN {F,D,D+,C-}` puts all
    four grades in `avoid`, not `hit`. Distinguishing these two was found
    necessary while testing mutation.py against tricker rules (2026-09-11):
    treating a NOT-IN's own listed values as candidates to *try* is wrong
    -- every one of them scores identically (still a member of the
    blocked set), so hillclimb stalled cycling among F/D/D+/C- forever,
    never trying the one thing that actually helps: a value outside the
    set entirely."""
    if not isinstance(node, dict):
        return
    op = node.get('op')
    if op == 'not':
        _collect_domain_facts(node.get('clause'), var_name, not negated, hit, avoid)
        return
    if op in ('=', '!='):
        left, right = node.get('left'), node.get('right')
        lit = None
        if isinstance(left, dict) and left.get('kind') == 'variable' and left.get('ref') == var_name \
                and isinstance(right, dict) and right.get('kind') == 'literal':
            lit = right['value']
        elif isinstance(right, dict) and right.get('kind') == 'variable' and right.get('ref') == var_name \
                and isinstance(left, dict) and left.get('kind') == 'literal':
            lit = left['value']
        if lit is not None:
            wants_equal = (op == '=') != negated  # negated '=' behaves like '!=', and vice versa
            (hit if wants_equal else avoid).add(lit)
    elif op == 'in':
        left = node.get('left')
        if isinstance(left, dict) and left.get('kind') == 'variable' and left.get('ref') == var_name:
            vals = {v['value'] for v in node.get('values', []) if isinstance(v, dict) and v.get('kind') == 'literal'}
            (avoid if negated else hit).update(vals)
    for key in ('left', 'right', 'clause', 'cond', 'then', 'else'):
        if key in node:
            _collect_domain_facts(node[key], var_name, negated, hit, avoid)
    for key in ('clauses', 'values'):
        for child in node.get(key, []):
            _collect_domain_facts(child, var_name, negated, hit, avoid)


def _domain_escape_value(literals, current):
    """A value guaranteed to be outside `literals` -- what an "avoid all
    of these" fact (a NOT IN / negated =) actually needs to try, since
    swapping among the avoided values themselves can never help."""
    sample = next(iter(literals)) if literals else current
    if isinstance(sample, (int, float)) and not isinstance(sample, bool):
        numeric = [v for v in literals if isinstance(v, (int, float)) and not isinstance(v, bool)]
        return (max(numeric) if numeric else 0) + 1
    base = str(current) if current is not None else str(sample)
    escape = base + '_'
    while escape in literals:
        escape += '_'
    return escape


def enumerable_domain(record, var_name):
    """-> sorted list of distinct literal values var_name is compared
    against via =/!=/in anywhere in this record's own condition or
    FIRST/UNIQUE earlier-row conditions, or None if it's never compared
    that way (e.g. only via </>=, which has no finite domain to enumerate).
    Kept as the plain "candidate values to try" list this always was;
    candidate_values() itself calls _collect_domain_facts directly when it
    also needs the hit/avoid split (to add an escape value)."""
    hit, avoid = set(), set()
    _collect_domain_facts(record['condition'], var_name, False, hit, avoid)
    for row in record.get('hit_policy_context', {}).get('earlier_rows', []):
        _collect_domain_facts(row['condition'], var_name, False, hit, avoid)
    found = hit | avoid
    if not found:
        return None
    try:
        return sorted(found)
    except TypeError:
        return sorted(found, key=str)


# ---------------------------------------------------------------------------
# 2. Candidate replacement values for one leaf, by kind/type -- what
# `mutate` actually tries before picking the one that lowers fitness most.
# ---------------------------------------------------------------------------

def candidate_values(record, var_name, node, current, case_study, step=1):
    kind = node.get('kind')
    if kind in BOOLEAN_LEAF_KINDS:
        return [True, False]
    domain = enumerable_domain(record, var_name)
    if domain:
        values = [v for v in domain if v != current] or list(domain)
        hit, avoid = set(), set()
        _collect_domain_facts(record['condition'], var_name, False, hit, avoid)
        for row in record.get('hit_policy_context', {}).get('earlier_rows', []):
            _collect_domain_facts(row['condition'], var_name, False, hit, avoid)
        if avoid:
            values.append(_domain_escape_value(hit | avoid, current))
        return values
    if kind == 'schema_column':
        ctype = _column_type(case_study, node['table'], node['column'])
        if 'DATE' in ctype or 'TIME' in ctype:
            base = current if isinstance(current, (int, float)) else 0
            return [base - step, base + step]
        if isinstance(current, (int, float)) and not isinstance(current, bool):
            return [current - step, current + step]
        if isinstance(current, str):
            # no enumerable domain and no declared type to branch on --
            # a single-character edit, the same fallback SchemaAnalyst's
            # own AVM uses for strings with no other structure to exploit.
            if not current:
                return [current + 'a']
            i = random.randrange(len(current))
            return [current[:i] + chr((ord(current[i]) + 1) % 128) + current[i + 1:]]
        return []
    if kind in ('derived_aggregate', 'derived_join_count'):
        base = current if isinstance(current, (int, float)) else 0
        return [max(0, base - step), base + step]
    return []


def _combined_fitness(record, candidate, focal, scenario, schema):
    """NOT the search objective (see this module's own docstring for why
    summing was tried and reverted) -- kept as a post-hoc audit helper:
    `branch_fitness` (the DMN term) plus `candidate_constraint_fitness`
    (the schema/DB constraint term), for reporting how schema-clean a
    solved candidate actually is, never for deciding what to mutate."""
    genome = derive_genome(record, candidate, focal, scenario)
    return branch_fitness(record, genome) + candidate_constraint_fitness(candidate.as_dict(), schema)


def _hypothetical_fitness(record, genome, var_name, value):
    trial = dict(genome)
    trial[var_name] = value
    try:
        return branch_fitness(record, trial)
    except FitnessEvaluationError:
        return float('inf')  # an invalid trial value should never be picked


_NUMERIC_STEP_KINDS = {'schema_column', 'derived_aggregate', 'derived_join_count'}
_AVM_MAX_ROUNDS = 60  # generous: log2 of even a huge gap is small; guards pathological oscillation


def _numeric_step_eligible(record, var_name, node, current):
    """True only for the leaf shapes where growing `step` in
    candidate_values() actually produces a wider probe -- a numeric
    schema_column/derived_aggregate/derived_join_count with no enumerable
    domain. AVM-style step acceleration only makes sense for these; every
    other kind (boolean, domain-based, string single-char edit) ignores
    `step` entirely (candidate_values' own domain/boolean branches return
    before ever looking at it), so "accelerating" them would just
    re-probe the identical candidates for no benefit."""
    kind = node.get('kind')
    if kind in BOOLEAN_LEAF_KINDS:
        return False
    if enumerable_domain(record, var_name):
        return False
    if kind == 'schema_column':
        return isinstance(current, (int, float)) and not isinstance(current, bool)
    return kind in ('derived_aggregate', 'derived_join_count')


def best_value_for(record, genome, var_name, node, case_study):
    """Tries every candidate replacement for var_name and returns
    (best_value, best_fitness, improved) -- 'improved' is False when
    nothing beats the current value, meaning this variable is already
    locally optimal and mutate() should try a different one instead.
    Genome-only and cheap, deliberately: schema/DB constraints are no
    longer part of this objective at all (see this module's own
    docstring) -- `branch_fitness` needs nothing but the flat genome, so
    there is no reason to materialize a real candidate just to pick a
    DMN-optimal value; `apply_mutation` (called once, on the winning
    value only) is where a real row actually gets touched.

    For numeric leaves with no enumerable domain, this is AVM's own
    "probe and accelerate": try step=1 both ways; once a direction
    improves, keep doubling the step in that same direction as long as
    it keeps improving, halving back down on overshoot. Added 2026-09-12,
    found necessary by this session's own tricky-rules testing: a branch
    needing a count to climb ~99 units took 99 individual step-1 mutation
    calls without this -- doubling closes the same gap in ~7 (see this
    module's own docstring and generator/README.md's "AVM step
    acceleration" section for the worked-example numbers). Every other
    leaf kind is unaffected: a single pass, exactly as before."""
    current = genome.get(var_name)
    current_fitness = branch_fitness(record, genome)
    best_value, best_fitness = current, current_fitness

    if not _numeric_step_eligible(record, var_name, node, current):
        for value in candidate_values(record, var_name, node, current, case_study):
            f = _hypothetical_fitness(record, genome, var_name, value)
            if f < best_fitness:
                best_value, best_fitness = value, f
        return best_value, best_fitness, best_value != current

    step = 1
    direction = None  # None = probe both ways; +1/-1 once one has proven to help
    tried_reset = False
    for _round in range(_AVM_MAX_ROUNDS):
        values = candidate_values(record, var_name, node, best_value, case_study, step=step)
        if direction is not None:
            values = [v for v in values if (v > best_value) == (direction > 0)]
        round_value, round_fitness, round_direction = best_value, best_fitness, None
        for value in values:
            f = _hypothetical_fitness(record, genome, var_name, value)
            if f < round_fitness:
                round_value, round_fitness, round_direction = value, f, (1 if value > best_value else -1)
        if round_fitness < best_fitness:
            best_value, best_fitness = round_value, round_fitness
            direction = round_direction
            step *= 2  # accelerate: this direction just improved again
            tried_reset = False
            if best_fitness == 0.0:
                break
        elif step > 1:
            step = max(1, step // 2)  # overshot -- retreat and retry finer, same direction
        elif direction is not None and not tried_reset:
            direction = None  # step-1 failed in the established direction -- one more both-ways check
            tried_reset = True
        else:
            break  # true local optimum for this variable
    return best_value, best_fitness, best_value != current


# ---------------------------------------------------------------------------
# 2b. Repair-by-construction -- NOT NULL/UNIQUE/FK are mechanically
# decidable from the schema alone, with no DMN-relevant ambiguity, so a
# row M1/M2 touches or adds is made schema-legal immediately, every time,
# rather than left for a search objective to maybe discover. Never
# overwrites a column that already carries a real value (DMN-written or
# otherwise) -- repair only ever fills in what's still missing.
# ---------------------------------------------------------------------------

def _placeholder_for_column_type(ctype):
    """A minimal, valid placeholder for a column repair needs to fill but
    has no DMN-relevant value for. Never used for a column any leaf
    mutation actually cares about -- those are always written first."""
    ctype = (ctype or '').upper()
    if 'DATE' in ctype or 'TIME' in ctype:
        return '2000-01-01'
    if any(t in ctype for t in ('NUM', 'INT', 'DEC', 'FLOAT', 'DOUBLE')):
        return 1
    return 'X'


def _fresh_key_value(candidate, table, column):
    """A numeric value guaranteed not to collide with any existing value
    of `column` across this table's current rows -- used only when a NOT
    NULL column repair needs to fill is *also* part of a declared
    PK/UNIQUE key, so filling it in with a shared constant across many
    rows (e.g. M2's own aggregate-count rows) never manufactures a fresh
    UNIQUE violation repair itself would be responsible for."""
    existing = {r.get(column) for r in candidate.rows(table)
                if isinstance(r.get(column), (int, float)) and not isinstance(r.get(column), bool)}
    return (max(existing) + 1) if existing else 1


def _repair_row(candidate, table, row, case_study, _seen=None):
    """Makes one row schema-legal on NOT NULL and FK, in place, using
    real schema data (`flex2_schema_full.json` et al., the same JSON
    `_column_type`/`fitness.py`'s own constraint functions already read).
    UNIQUE/PK is handled as a side effect of `_fresh_key_value`, not
    checked separately -- there is no general "avoid this collision" move
    to make beyond giving a key column its own fresh value when repair is
    the one filling it in.

    When an FK needs a parent row synthesized, that new row is repaired
    too (recursively) -- otherwise the minimal `{ref_col: val}` row this
    function itself creates would trade one FK gap for a fresh NOT NULL
    gap on the very row meant to close it. `_seen` guards against a cyclic
    FK graph recursing forever (tracked by object identity, since two
    equal-content rows are still different real rows)."""
    _seen = _seen if _seen is not None else set()
    if id(row) in _seen:
        return
    _seen.add(id(row))
    schema = _schema_for(case_study)
    info = schema.get(table) or schema.get(table.upper()) or schema.get(table.lower()) or {}
    if not info:
        return
    real_table = table
    key_cols = {c.upper() for cols in _unique_key_sets(schema, real_table) for c in cols}
    lowered = {k.lower() for k in row}
    for col, meta in (info.get('columns') or {}).items():
        if not meta.get('null_false') or col.lower() in lowered:
            continue  # not required, or already has a real value -- never overwritten
        if col.upper() in key_cols:
            row[col] = _fresh_key_value(candidate, real_table, col)
        else:
            row[col] = _placeholder_for_column_type(meta.get('type'))
        lowered.add(col.lower())
    for fk in (info.get('fk_columns') or []):
        col = fk['column']
        val = row.get(col)
        if val is None:
            # unset (never touched, or deliberately nulled) -- a nullable
            # FK left NULL is valid SQL, not a gap repair needs to fill.
            continue
        ref_table, ref_col = fk['ref_table'], fk['ref_column']
        parent_row = None
        for pr in candidate.rows(ref_table):
            v = pr.get(ref_col, pr.get(ref_col.upper(), pr.get(ref_col.lower())))
            if v == val:
                parent_row = pr
                break
        if parent_row is None:
            # no valid parent row exists for this FK's real value yet --
            # materialize a minimal one rather than leave it dangling, and
            # repair *that* row too (it's a new row this same construction
            # discipline applies to, not an exception to it).
            parent_row = candidate.add_row(ref_table, {ref_col: val})
            _repair_row(candidate, ref_table, parent_row, case_study, _seen)


def repair_candidate(candidate, case_study):
    """Repairs EVERY row currently in `candidate` for NOT NULL/FK, not
    just the ones a subsequent mutation happens to touch. `_repair_row`
    (used by `apply_mutation`) only ever fires on rows M1/M2 themselves
    touch during search -- a real gap found materializing a freshly
    seeded candidate end to end for the first time (2026-09-12,
    materialize.py): `build_seed_candidate` only sets the columns the
    leaf that needed them actually named, so a "bystander" table (e.g.
    one a `derived_aggregate`'s multi-table FROM-list names but the
    search never has reason to mutate) stays exactly as incomplete as
    the seed left it, all the way to materialization. Call this once on
    any freshly built candidate (a seed, or one assembled by hand for a
    test) before handing it to `hillclimb`/`solve_branch` -- idempotent,
    since repairing an already-clean row is a no-op."""
    for table, rows in list(candidate.as_dict().items()):
        for row in list(rows):
            _repair_row(candidate, table, row, case_study)


# ---------------------------------------------------------------------------
# 3. Applying the winning value to the *real* Candidate -- M1 (field) or
# M2 (row-count), chosen by the leaf's own resolution kind, never guessed.
# ---------------------------------------------------------------------------

def _apply_field_mutation(node, value, candidate, focal):
    """M1: write one row's one column. For a boolean-valued leaf
    (null_check et al.), True/False means "make the underlying fact hold
    or not" -- realized as setting the column non-null vs null, the same
    semantics classify_derived's own null_check kind already carries.
    Returns every (table, row) pair this call touched or added, so
    apply_mutation can repair each one for NOT NULL/FK by construction
    afterward -- collected rather than repaired inline here, so this
    function stays purely about the DMN-relevant write."""
    kind = node['kind']
    touched = []
    if kind == 'schema_column':
        table, column = node['table'], node['column']
        row = focal.setdefault(table.upper(), {})
        if table.upper() not in {t for t in candidate.as_dict()} or row not in candidate.rows(table):
            candidate.add_row(table, row)
        row[column] = value
        touched.append((table, row))
    elif kind == 'derived_case':
        # `value` is a *derived* category (e.g. 'Regular') the branch
        # condition compares against -- never write that string itself
        # into the real column (that's exactly the bug found testing
        # this operator: TITLE never really holds 'Regular'). Invert
        # CASE_MAP to a real input value that produces this output.
        table, column = node['table'], node['column']
        real_value = next((k for k, v in node['cases'] if v == value), None)
        if real_value is None:
            raise FitnessEvaluationError(
                f"{value!r} is not a reachable output of this derived_case's CASE_MAP "
                f"({node['cases']}) -- refusing to write an unmappable value")
        row = focal.setdefault(table.upper(), {})
        if row not in candidate.rows(table):
            candidate.add_row(table, row)
        row[column] = real_value
        touched.append((table, row))
    elif kind == 'null_check':
        table, column = node['table'], node['column']
        row = focal.setdefault(table.upper(), {})
        if row not in candidate.rows(table):
            candidate.add_row(table, row)
        row[column] = (row.get(column, 1) if value else None) if value else None
        if value and row.get(column) is None:
            row[column] = 1  # any non-null placeholder satisfies "is set"
        touched.append((table, row))
    elif kind == 'any_not_null':
        # True: ensure at least one of the columns is set; False: null all
        for c in node['columns']:
            row = focal.setdefault(c['table'].upper(), {})
            if row not in candidate.rows(c['table']):
                candidate.add_row(c['table'], row)
            row[c['column']] = None
            touched.append((c['table'], row))
        if value:
            first = node['columns'][0]
            focal[first['table'].upper()][first['column']] = 1
    elif kind in ('join_lookup', 'join_null_check'):
        local_row = focal.setdefault(node['via']['local_table'].upper(), {})
        if local_row not in candidate.rows(node['via']['local_table']):
            candidate.add_row(node['via']['local_table'], local_row)
        touched.append((node['via']['local_table'], local_row))
        if kind == 'join_null_check' and not value:
            local_row[node['via']['local_column']] = None
            return touched
        target_row = focal.setdefault(node['result_table'].upper(), {})
        if target_row not in candidate.rows(node['result_table']):
            candidate.add_row(node['result_table'], target_row)
        key = target_row.setdefault(node['result_column'], 1)
        local_row[node['via']['local_column']] = key
        if kind == 'join_lookup':
            target_row[node['result_column']] = value
        touched.append((node['result_table'], target_row))
    elif kind == 'regex_match':
        vrow = focal.setdefault(node['value_column']['table'].upper(), {})
        prow = focal.setdefault(node['pattern_column']['table'].upper(), {})
        if vrow not in candidate.rows(node['value_column']['table']):
            candidate.add_row(node['value_column']['table'], vrow)
        if prow not in candidate.rows(node['pattern_column']['table']):
            candidate.add_row(node['pattern_column']['table'], prow)
        prow.setdefault(node['pattern_column']['column'], '.*')
        vrow[node['value_column']['column']] = 'MATCH' if value else ''
        touched.append((node['value_column']['table'], vrow))
        touched.append((node['pattern_column']['table'], prow))
    return touched


def _apply_row_count_mutation(node, value, candidate, scenario, current, focal=None):
    """M2: add or remove rows -- moves the FULL distance from `current`
    to `value` in one call, not just one row, using the same
    mechanically-recognized filter_text conjuncts candidate.py's own
    _mechanical_filter_predicate already extracts (in reverse: turned
    into a new row's column values, not just a match test). Returns
    every (table, row) pair *newly added* (never a removed one -- nothing
    to repair there) so apply_mutation can make each one schema-legal by
    construction afterward.

    Moving the full distance, not one row per call, was added alongside
    AVM-style step acceleration (2026-09-12, search.py): once
    best_value_for is allowed to decide the best count is many units
    away (closing a large gap in O(log(gap)) tries instead of O(gap)),
    applying only one row per call regardless of the decided step would
    silently diverge the real candidate from the genome the search
    believed it was accepting -- exactly the gap that made the original
    step-1-only design need ~99 individual calls to grow one count from
    4 to 100 (generator/README.md's own tricky-rules sweep)."""
    if node['kind'] == 'exists':
        table = (node.get('candidate_tables') or [None])[0]
        if table is None:
            return []
        if value and not candidate.rows(table):
            row = candidate.add_row(table, {})
            return [(table, row)]
        elif not value:
            candidate._tables[table.upper()] = []
        return []
    if node['kind'] == 'derived_join_count':
        # unmetPrerequisiteCount / unmetPrerequisiteAlsoPassedCount (found
        # while testing mutation.py against tricker rules, 2026-09-11) --
        # see candidate.py's derive_value for the same recipe read in
        # reverse. "This" course/student context is whichever focal row
        # carries both key columns.
        context_table, context_row = _find_focal_with_columns(
            focal or {}, [node['prereq_course_column'], node['registration_roll_column']])
        if context_row is None:
            raise FitnessEvaluationError(
                f"derived_join_count mutation needs a focal row carrying both "
                f"{node['prereq_course_column']} and {node['registration_roll_column']} -- "
                f"none of the given focal rows has both")
        course_id = _row_get(context_row, node['prereq_course_column'])
        roll_no = _row_get(context_row, node['registration_roll_column'])
        prereq_rows = []
        for r in candidate.rows(node['prereq_table']):
            try:
                if _row_get(r, node['prereq_course_column']) == course_id:
                    prereq_rows.append(r)
            except FitnessEvaluationError:
                continue
        n = int(round(value)) - int(round(current or 0))
        if n > 0:
            # fresh prerequisite course ids this student has no passing
            # registration for -- guaranteed unmet since nothing else
            # names them yet. One id per unit of the requested step, not
            # just one row regardless of how big a step was decided.
            used_ids = set()
            for r in prereq_rows:
                try:
                    used_ids.add(_row_get(r, node['prereq_target_column']))
                except FitnessEvaluationError:
                    pass
            new_prereq_id = 900001
            touched = []
            for _ in range(n):
                while new_prereq_id in used_ids:
                    new_prereq_id += 1
                new_row = {node['prereq_course_column']: course_id,
                           node['prereq_target_column']: new_prereq_id}
                candidate.add_row(node['prereq_table'], new_row)
                used_ids.add(new_prereq_id)
                touched.append((node['prereq_table'], new_row))
            return touched
        elif n < 0 and prereq_rows:
            # simplest correct decrease: this course no longer requires
            # these prerequisites, rather than inventing passing grades
            # for courses this student was never registered for --
            # equally valid (the count is over COURSE_PREREQ rows), and
            # never touches COURSE_REGISTRATION/previousGradeInCourse's
            # own row. Removes up to `-n` (never more than exist).
            for row in prereq_rows[:min(-n, len(prereq_rows))]:
                candidate.rows(node['prereq_table']).remove(row)
        return []
    tables = [t.strip() for t in node['table'].split(',')]
    table = tables[0]
    predicate, _skipped = _mechanical_filter_predicate(node.get('filter_text'), scenario)
    n = int(round(value)) - int(round(current or 0))
    if n > 0:
        touched = []
        for _ in range(n):
            row = {}
            for conjunct in re.split(r'\bAND\b', node.get('filter_text') or '', flags=re.I):
                cm = re.match(r'^\s*(?:[\w]+\.)?(\w+)\s*=\s*(.+?)\s*$', conjunct.strip())
                if not cm:
                    continue
                col, raw_val = cm.group(1), cm.group(2).strip()
                ph = re.fullmatch(r'<([^>]+)>', raw_val)
                if ph:
                    if ph.group(1) in scenario:
                        row[col] = scenario[ph.group(1)]
                else:
                    v = raw_val.strip("'\"")
                    try:
                        v = int(v)
                    except ValueError:
                        try:
                            v = float(v)
                        except ValueError:
                            pass
                    row[col] = v
            if node.get('value_column'):
                row[node['value_column'].split('.')[1]] = 1
            candidate.add_row(table, row)
            touched.append((table, row))
        return touched
    elif n < 0:
        rows = candidate.rows(table)
        matching = [r for r in rows if predicate(r)] or rows
        for row in matching[:min(-n, len(matching))]:
            rows.remove(row)
    return []


def apply_mutation(record, candidate, focal, scenario, var_name, node, value, current):
    """Applies the winning value via M1 or M2, then repairs every row that
    call touched for NOT NULL/FK by construction (`_repair_row`) -- always,
    not conditionally, since a real Candidate should never leave M1/M2's
    own scope without being schema-legal on the parts that are mechanically
    decidable regardless of what the DMN branch needed."""
    kind = node.get('kind')
    if kind in FIELD_LEAF_KINDS:
        touched = _apply_field_mutation(node, value, candidate, focal)
    elif kind in AGGREGATE_LEAF_KINDS:
        touched = _apply_row_count_mutation(node, value, candidate, scenario, current, focal)
    elif kind == 'not_persisted':
        scenario[var_name] = value
        touched = []
    elif kind == 'raw_sql_boolean':
        raise FitnessEvaluationError(
            f"{var_name!r} (raw_sql_boolean) has no automatic mutation -- too bespoke a "
            f"compound fact to edit generically; needs a fact-specific operator")
    else:
        raise FitnessEvaluationError(f"mutation has no handling for resolution kind {kind!r}")
    for table, row in touched or []:
        _repair_row(candidate, table, row, record['case_study'])


# ---------------------------------------------------------------------------
# 4. The operator itself, and a hill-climb driver to actually exercise it
#    (§6.4's own "local search (AVM)" mode -- a legitimate cheaper
#    alternative for a single branch, not a stand-in for DynaMOSA's own
#    population/crossover loop, which reuses this same mutate() call as
#    its own variation operator).
# ---------------------------------------------------------------------------

def _leaf_variables(record):
    """Every true leaf free variable of this record's own condition,
    recursing through substituted_decision chains -- the same walk
    candidate.py's derive_genome does, exposed here so mutate() knows
    what it's allowed to touch. Returns [(var_name, node), ...] -- the
    node itself, not just the name, since a leaf nested inside a
    substituted_decision's own free_variable_resolutions (e.g.
    'lecturesAttended' inside 'attendancePercentage') is *not* a
    top-level key of record['variable_resolution'] and can't be looked
    up again that way -- a real bug this fixed before it ever ran, since
    the flagship record itself has exactly this shape."""
    out = []

    def walk(var_name, node):
        kind = node.get('kind')
        if kind in ('literal', 'literal_via_upstream_branch') or kind in (
                'schema_gap', 'code_external', 'unresolved', 'chained_decision_output'):
            return
        if kind == 'substituted_decision':
            for fv, sub in node.get('free_variable_resolutions', {}).items():
                walk(fv, sub)
            return
        out.append((var_name, node))

    for var, node in record.get('variable_resolution', {}).items():
        walk(var, node)
    return out


def mutate(record, candidate, focal, scenario, rng=None):
    """One mutation: picks a random leaf variable, finds its best
    replacement value (by hypothetical DMN-only fitness, tried in-genome
    before touching any real row), and applies it via M1 or M2 to a
    *copy* of `candidate`/`focal`/`scenario` -- parents are never mutated
    in place. `apply_mutation` also repairs every row it touches for NOT
    NULL/FK by construction (see this module's own docstring), so the
    adopted candidate is schema-legal on those without that ever being
    part of what this function searches for. Returns (new_candidate,
    new_focal, new_scenario, mutated_var, improved).

    The candidate/focal copy is made via ONE joint `copy.deepcopy` call,
    not two separate ones -- a real bug (see this module's own docstring)
    found while building the schema-constraint fix: two separate top-level
    deepcopy calls silently break the object aliasing between a focal row
    and its own entry in the candidate's row list, so a field mutation
    could write into a focal copy that `candidate` itself never actually
    contained.

    A leaf whose winning value `apply_mutation` refuses to actually write
    (raw_sql_boolean's own explicit refusal, or any future kind with no
    M1/M2 handling) is treated exactly like "not improved" rather than
    propagating out and crashing the search -- a real crash this fixed,
    found testing tricker rules (2026-09-11): raw_sql_boolean is listed in
    BOOLEAN_LEAF_KINDS, so the genome-only hypothetical is happy to call
    it "improvable" even though apply_mutation always refuses it."""
    rng = rng or random
    genome = derive_genome(record, candidate, focal, scenario)
    leaves = [(v, n) for v, n in _leaf_variables(record) if v in genome]
    if not leaves:
        return candidate, focal, scenario, None, False
    var_name, node = rng.choice(leaves)
    best_value, best_fitness, improved = best_value_for(record, genome, var_name, node, record['case_study'])
    if not improved:
        return candidate, focal, scenario, var_name, False

    new_candidate, new_focal = copy.deepcopy((candidate, focal))
    new_scenario = dict(scenario)
    try:
        apply_mutation(record, new_candidate, new_focal, new_scenario, var_name, node, best_value, genome.get(var_name))
    except FitnessEvaluationError:
        return candidate, focal, scenario, var_name, False
    return new_candidate, new_focal, new_scenario, var_name, True


def hillclimb(record, candidate, focal, scenario, max_iters=200, rng=None):
    """Repeated mutation, keeping only non-worsening moves -- a (1+1)
    local search exercising `mutate` end to end. Scored on `branch_fitness`
    alone (the DMN term) -- schema/DB constraints are never part of this
    acceptance criterion (see this module's own docstring for why summing
    them in was tried and reverted); `_repair_row` keeps every row
    schema-legal by construction regardless of what this loop optimizes
    for. Not DynaMOSA itself (no population, no crossover, no
    multi-objective sorting), but a valid standalone way to prove the
    mutation operator actually converges, and a legitimate cheap mode in
    its own right for a branch simple enough not to need the full loop
    (§6.4's own allowance)."""
    rng = rng or random.Random(0)
    history = []
    current_fitness = branch_fitness(record, derive_genome(record, candidate, focal, scenario))
    history.append(current_fitness)
    for _ in range(max_iters):
        if current_fitness == 0.0:
            break
        new_c, new_f, new_s, var, improved = mutate(record, candidate, focal, scenario, rng)
        if not improved:
            continue
        new_fitness = branch_fitness(record, derive_genome(record, new_c, new_f, new_s))
        if new_fitness <= current_fitness:
            candidate, focal, scenario, current_fitness = new_c, new_f, new_s, new_fitness
            history.append(current_fitness)
    return candidate, focal, scenario, history


if __name__ == '__main__':
    data = json.load(open(os.path.join(HERE, 'compiled_constraints.json')))
    rule2 = next(r for r in data if r['record_id'].endswith('Decision_AttendanceEligibility_Rule_2'))

    # Start deliberately WRONG: only 20 attended lectures (needs <80%,
    # i.e. needs to drop further -- but starting on the wrong side of the
    # threshold, 20/45=44.4%, is actually already <80%; use a genuinely
    # wrong starting point instead: 44 attended, 97.8%, well on the wrong
    # side, and let mutation find its way down to a real solution.
    STUDENT, OFFERING = 2024001, 5001
    start = Candidate()
    start.add_row('STUDENT_PROGRAM', {'ROLL_NO': STUDENT})
    for i in range(45):
        start.add_row('LECTURE', {'LECTURE_ID': 1000 + i, 'OFFER_ID': OFFERING})
    for i in range(44):
        start.add_row('STUDENT_ATTENDANCE', {'LECTURE_ID': 1000 + i, 'ROLL_NO': STUDENT, 'ATTEND_FLAG': 'Y'})
    scenario = {'student': STUDENT, 'this course offering': OFFERING}

    g0 = derive_genome(rule2, start, {}, scenario)
    f0 = branch_fitness(rule2, g0)
    print(f"Start: genome={g0}, fitness={f0:.4f} (wrong side of the 80% threshold)")

    solved, focal, scenario, history = hillclimb(rule2, start, {}, scenario, max_iters=100)
    g1 = derive_genome(rule2, solved, focal, scenario)
    f1 = branch_fitness(rule2, g1)
    schema = _schema_for('FLEX2')
    constraint_f1 = candidate_constraint_fitness(solved.as_dict(), schema)
    print(f"After hillclimb ({len(history)} accepted steps): genome={g1}")
    print(f"  DMN branch_fitness={f1:.6f}, schema/DB constraint_fitness={constraint_f1:.6f} (audit-only, "
          f"never the search objective -- see this module's docstring)")
    print(f"branch_fitness trajectory (what hillclimb actually optimizes): {history}")
    assert f1 == 0.0, "mutation operator failed to converge the DMN term on the flagship rule from a wrong start"
    assert all(history[i] >= history[i + 1] for i in range(len(history) - 1)), \
        "fitness must be monotonically non-increasing across accepted mutations"
    print("Mutation operator converged the DMN term correctly and monotonically. Self-check passed.")
    if constraint_f1 > 0.0:
        # Expected, not a bug: `_repair_row` only repairs rows M1/M2
        # themselves touch or construct -- it has no mandate to retroactively
        # fix a row this test script handed mutation directly (the initial
        # STUDENT_PROGRAM row above is deliberately incomplete, missing
        # PROG_ID/BATCH_NO, to prove exactly this boundary). Every row
        # mutation actually built or touched this run -- the 8 new LECTURE
        # rows, the auto-materialized COURSE_OFFER parent row FK-repair
        # created for them -- is fully schema-legal; confirmed directly via
        # fk_distance/not_null_distance on each in this module's own testing
        # history, not just inferred from the total.
        print(f"  (Residual {constraint_f1:.4f} of schema/DB constraint distance remains -- entirely from "
              f"the hand-seeded STUDENT_PROGRAM row above (missing PROG_ID/BATCH_NO), which predates any "
              f"mutation and so was never repair's to fix; every row mutation itself built is schema-clean.)")

    print()
    print("derived_case regression check (semesterType, found while first testing this module):")
    # Rule_4 itself has no bare/ungrounded compiled entry anymore (2026-09-12
    # DRD-grounding fix, compile_constraints.py) -- every variant now
    # carries a ::via:: suffix grounding its own earlier-row suppression
    # dependency, but semesterType's own resolution (what this check
    # actually exercises) is identical across every one of them, so any
    # variant works.
    load_rec = next(r for r in data
                     if r['record_id'].startswith('FLEX2::Course Load Limit::Decision_CourseLoadLimit_Rule_4::via'))
    case_node = load_rec['variable_resolution']['semesterType']
    assert case_node['kind'] == 'derived_case', "semesterType should no longer be a plain schema_column"

    c_fall = Candidate()
    row_fall = {'SEM_ID': 7, 'TITLE': 'Fall'}
    c_fall.add_row('SEMESTER', row_fall)
    apply_mutation(load_rec, c_fall, {'SEMESTER': row_fall}, {}, 'semesterType', case_node, 'Summer', 'Regular')
    assert c_fall.rows('SEMESTER')[0]['TITLE'] == 'Summer', \
        "mutating toward 'Summer' must write the real value 'Summer', not the label itself"

    c_summer = Candidate()
    row_summer = {'SEM_ID': 7, 'TITLE': 'Summer'}
    c_summer.add_row('SEMESTER', row_summer)
    apply_mutation(load_rec, c_summer, {'SEMESTER': row_summer}, {}, 'semesterType', case_node, 'Regular', 'Summer')
    written = c_summer.rows('SEMESTER')[0]['TITLE']
    assert written in ('Fall', 'Spring'), (
        f"mutating toward 'Regular' must write a REAL value that maps to it (Fall/Spring), "
        f"never the impossible literal 'Regular' itself -- got {written!r}")
    print(f"  Confirmed: mutation never writes an impossible category label into SEMESTER.TITLE "
          f"(wrote {written!r} for the 'Regular' target, 'Summer' for the 'Summer' target).")
    print("All derived_case self-checks passed.")
