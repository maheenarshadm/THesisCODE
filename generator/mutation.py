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
replacement value for the chosen variable, keep whichever scores lowest
on the **combined objective** -- `branch_fitness` (the DMN term) *plus*
`candidate_constraint_fitness` (the schema/DB constraint term: NOT NULL,
UNIQUE/PK, FK, CHECK) -- then adopt that winning state.

This wasn't always true: the operator originally scored candidates by a
cheap, in-genome `branch_fitness`-only hypothetical, with no schema
awareness at all. Asked directly whether row mutation checks FK/schema
constraints, the honest answer (2026-09-12) was no, demonstrated
concretely: a candidate that reached `branch_fitness == 0.0` (DMN-perfect)
scored `candidate_constraint_fitness == 68.3` on the exact same rows --
M2 had added ~96 near-empty rows with no FK linkage, missing NOT NULL
columns, and duplicate PK keys, entirely invisible to a DMN-only
objective. Since the constraint term needs real materialized rows (NOT
NULL/UNIQUE/FK/CHECK can't be read off a flat genome), the cheap
in-genome hypothetical had to go: every candidate value is now actually
applied to a real, deep-copied candidate before being scored, and the
copy with the lowest combined fitness is adopted -- more work per
mutation, but the only way the constraint half can be evaluated at all.
This lets one mutation function keep handling every leaf kind uniformly,
rather than needing per-kind direction logic duplicated.

Known remaining gap, stated plainly: this makes constraint violations
*count* toward whether a mutation is accepted, but it does not yet give
the operator any way to *fix* one on its own -- M2's row-builder still
only fills in the columns the DMN filter text names, so a table's other
NOT NULL/FK columns stay unset regardless of which candidate value wins.
Combined fitness can therefore plateau above 0.0 for aggregate-heavy
branches even once the DMN term itself is fully satisfied. Closing that
needs a real repair step in M2 (fill NOT NULL columns with a valid
placeholder, pick a real existing PK for FK columns) -- a follow-up, not
attempted here.

Usage:
    from mutation import mutate, hillclimb
    new_candidate, new_focal, new_scenario, var, improved, fitness = \\
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
                      candidate_constraint_fitness)
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
    """The real objective mutation optimizes: `branch_fitness` (the DMN
    branch-distance term) plus `candidate_constraint_fitness` (the
    schema/DB constraint term -- NOT NULL, UNIQUE/PK, FK, CHECK) over the
    same candidate. Both terms are already normalized to the same 0..1
    per-clause scale (fitness.py's own `normalize`), so an unweighted sum
    keeps them comparable -- no weighting scheme is named anywhere in the
    design doc's own §6.3 equation, and this is the single-objective
    hillclimb's own stand-in for DynaMOSA's proper multi-objective
    comparison (each term would be its own objective there, per §6.4)."""
    genome = derive_genome(record, candidate, focal, scenario)
    return branch_fitness(record, genome) + candidate_constraint_fitness(candidate.as_dict(), schema)


def best_value_for(record, candidate, focal, scenario, var_name, node, case_study):
    """Tries every candidate replacement value for var_name, each one
    actually APPLIED to a real, deep-copied candidate -- not a cheap
    in-genome guess, since the constraint half of the combined objective
    needs real materialized rows (NOT NULL/UNIQUE/FK/CHECK can't be read
    off a flat genome at all). Returns
    (best_candidate, best_focal, best_scenario, best_fitness, improved)
    -- 'improved' is False when nothing beats the current combined
    fitness, meaning this variable is already locally optimal and
    mutate() should try a different one instead. A value that can't
    legitimately be applied at all (apply_mutation refuses it, or the
    resulting candidate can't even be scored) is skipped, not treated as
    a tie -- the same "never pick an invalid trial" discipline the old
    genome-only version had, now enforced by construction rather than a
    float('inf') sentinel."""
    schema = _schema_for(case_study)
    current = derive_genome(record, candidate, focal, scenario).get(var_name)
    current_fitness = _combined_fitness(record, candidate, focal, scenario, schema)
    best_candidate, best_focal, best_scenario, best_fitness = candidate, focal, scenario, current_fitness
    for value in candidate_values(record, var_name, node, current, case_study):
        trial_candidate = copy.deepcopy(candidate)
        trial_focal = copy.deepcopy(focal)
        trial_scenario = dict(scenario)
        try:
            apply_mutation(record, trial_candidate, trial_focal, trial_scenario, var_name, node, value, current)
            f = _combined_fitness(record, trial_candidate, trial_focal, trial_scenario, schema)
        except FitnessEvaluationError:
            continue  # this value can't legitimately be applied/scored -- never a candidate
        if f < best_fitness:
            best_candidate, best_focal, best_scenario, best_fitness = trial_candidate, trial_focal, trial_scenario, f
    return best_candidate, best_focal, best_scenario, best_fitness, best_candidate is not candidate


# ---------------------------------------------------------------------------
# 3. Applying the winning value to the *real* Candidate -- M1 (field) or
# M2 (row-count), chosen by the leaf's own resolution kind, never guessed.
# ---------------------------------------------------------------------------

def _apply_field_mutation(node, value, candidate, focal):
    """M1: write one row's one column. For a boolean-valued leaf
    (null_check et al.), True/False means "make the underlying fact hold
    or not" -- realized as setting the column non-null vs null, the same
    semantics classify_derived's own null_check kind already carries."""
    kind = node['kind']
    if kind == 'schema_column':
        table, column = node['table'], node['column']
        row = focal.setdefault(table.upper(), {})
        if table.upper() not in {t for t in candidate.as_dict()} or row not in candidate.rows(table):
            candidate.add_row(table, row)
        row[column] = value
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
    elif kind == 'null_check':
        table, column = node['table'], node['column']
        row = focal.setdefault(table.upper(), {})
        if row not in candidate.rows(table):
            candidate.add_row(table, row)
        row[column] = (row.get(column, 1) if value else None) if value else None
        if value and row.get(column) is None:
            row[column] = 1  # any non-null placeholder satisfies "is set"
    elif kind == 'any_not_null':
        # True: ensure at least one of the columns is set; False: null all
        for c in node['columns']:
            row = focal.setdefault(c['table'].upper(), {})
            if row not in candidate.rows(c['table']):
                candidate.add_row(c['table'], row)
            row[c['column']] = None
        if value:
            first = node['columns'][0]
            focal[first['table'].upper()][first['column']] = 1
    elif kind in ('join_lookup', 'join_null_check'):
        local_row = focal.setdefault(node['via']['local_table'].upper(), {})
        if local_row not in candidate.rows(node['via']['local_table']):
            candidate.add_row(node['via']['local_table'], local_row)
        if kind == 'join_null_check' and not value:
            local_row[node['via']['local_column']] = None
            return
        target_row = focal.setdefault(node['result_table'].upper(), {})
        if target_row not in candidate.rows(node['result_table']):
            candidate.add_row(node['result_table'], target_row)
        key = target_row.setdefault(node['result_column'], 1)
        local_row[node['via']['local_column']] = key
        if kind == 'join_lookup':
            target_row[node['result_column']] = value
    elif kind == 'regex_match':
        vrow = focal.setdefault(node['value_column']['table'].upper(), {})
        prow = focal.setdefault(node['pattern_column']['table'].upper(), {})
        if vrow not in candidate.rows(node['value_column']['table']):
            candidate.add_row(node['value_column']['table'], vrow)
        if prow not in candidate.rows(node['pattern_column']['table']):
            candidate.add_row(node['pattern_column']['table'], prow)
        prow.setdefault(node['pattern_column']['column'], '.*')
        vrow[node['value_column']['column']] = 'MATCH' if value else ''


def _apply_row_count_mutation(node, value, candidate, scenario, current, focal=None):
    """M2: add or remove a whole row -- one row per mutation call, moving
    one step toward `value`, using the same mechanically-recognized
    filter_text conjuncts candidate.py's own _mechanical_filter_predicate
    already extracts (in reverse: turned into a new row's column values,
    not just a match test)."""
    if node['kind'] == 'exists':
        table = (node.get('candidate_tables') or [None])[0]
        if table is None:
            return
        if value and not candidate.rows(table):
            candidate.add_row(table, {})
        elif not value:
            candidate._tables[table.upper()] = []
        return
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
        if value > (current or 0):
            # a fresh prerequisite course id this student has no passing
            # registration for -- guaranteed unmet since nothing else
            # names it yet.
            used_ids = set()
            for r in prereq_rows:
                try:
                    used_ids.add(_row_get(r, node['prereq_target_column']))
                except FitnessEvaluationError:
                    pass
            new_prereq_id = 900001
            while new_prereq_id in used_ids:
                new_prereq_id += 1
            candidate.add_row(node['prereq_table'], {
                node['prereq_course_column']: course_id,
                node['prereq_target_column']: new_prereq_id})
        elif value < (current or 0) and prereq_rows:
            # simplest correct decrease: this course no longer requires
            # one of its prerequisites, rather than inventing a passing
            # grade for a course this student was never registered for --
            # equally valid (the count is over COURSE_PREREQ rows), and
            # never touches COURSE_REGISTRATION/previousGradeInCourse's
            # own row.
            row = prereq_rows[0]
            candidate.rows(node['prereq_table']).remove(row)
        return
    tables = [t.strip() for t in node['table'].split(',')]
    table = tables[0]
    predicate, _skipped = _mechanical_filter_predicate(node.get('filter_text'), scenario)
    if value > (current or 0):
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
    elif value < (current or 0):
        rows = candidate.rows(table)
        matching = [r for r in rows if predicate(r)] or rows
        if matching:
            rows.remove(matching[0])


def apply_mutation(record, candidate, focal, scenario, var_name, node, value, current):
    kind = node.get('kind')
    if kind in FIELD_LEAF_KINDS:
        _apply_field_mutation(node, value, candidate, focal)
    elif kind in AGGREGATE_LEAF_KINDS:
        _apply_row_count_mutation(node, value, candidate, scenario, current, focal)
    elif kind == 'not_persisted':
        scenario[var_name] = value
    elif kind == 'raw_sql_boolean':
        raise FitnessEvaluationError(
            f"{var_name!r} (raw_sql_boolean) has no automatic mutation -- too bespoke a "
            f"compound fact to edit generically; needs a fact-specific operator")
    else:
        raise FitnessEvaluationError(f"mutation has no handling for resolution kind {kind!r}")


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
    replacement value by the combined objective (each candidate value
    actually applied to a real, deep-copied candidate/focal/scenario --
    parents are never mutated in place), and adopts whichever copy scores
    lowest. Returns (new_candidate, new_focal, new_scenario, mutated_var,
    improved, new_fitness) -- when nothing improves, the "new" state is
    just the unchanged input and new_fitness is the current combined
    fitness, so callers never need to recompute it separately.

    A leaf whose only candidate values apply_mutation refuses (e.g.
    raw_sql_boolean, deliberately unmutatable) or that can't even be
    scored is handled inside best_value_for itself now -- every value is
    tried inside its own try/except, so a refusal just removes that value
    from consideration rather than propagating out and crashing the
    search (a real crash this fixed, found testing tricker rules,
    2026-09-11: raw_sql_boolean is listed in BOOLEAN_LEAF_KINDS, so the
    old genome-only hypothetical was happy to call it "improvable" even
    though apply_mutation always refused it)."""
    rng = rng or random
    genome = derive_genome(record, candidate, focal, scenario)
    leaves = [(v, n) for v, n in _leaf_variables(record) if v in genome]
    if not leaves:
        return candidate, focal, scenario, None, False, None
    var_name, node = rng.choice(leaves)
    new_candidate, new_focal, new_scenario, new_fitness, improved = best_value_for(
        record, candidate, focal, scenario, var_name, node, record['case_study'])
    return new_candidate, new_focal, new_scenario, var_name, improved, new_fitness


def hillclimb(record, candidate, focal, scenario, max_iters=200, rng=None):
    """Repeated mutation, keeping only non-worsening moves -- a (1+1)
    local search exercising `mutate` end to end, scored on the combined
    objective (DMN branch distance + schema/DB constraint distance, see
    `_combined_fitness`) rather than the DMN term alone. Not DynaMOSA
    itself (no population, no crossover, no multi-objective sorting), but
    a valid standalone way to prove the mutation operator actually
    converges, and a legitimate cheap mode in its own right for a branch
    simple enough not to need the full loop (§6.4's own allowance).

    Note the combined objective can plateau above 0.0 even once the DMN
    term is fully satisfied, for a branch whose M2-added rows are missing
    NOT NULL/FK data the current candidate-value vocabulary has no lever
    to fix -- an honest, expected outcome (see this module's own
    docstring), not a bug in the search loop."""
    rng = rng or random.Random(0)
    schema = _schema_for(record['case_study'])
    history = []
    current_fitness = _combined_fitness(record, candidate, focal, scenario, schema)
    history.append(current_fitness)
    for _ in range(max_iters):
        if current_fitness == 0.0:
            break
        new_c, new_f, new_s, var, improved, new_fitness = mutate(record, candidate, focal, scenario, rng)
        if not improved:
            continue
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
    print(f"  DMN branch_fitness={f1:.6f}, schema/DB constraint_fitness={constraint_f1:.6f}")
    print(f"Combined-fitness trajectory (what hillclimb actually optimizes): {history}")
    assert f1 == 0.0, "mutation operator failed to converge the DMN term on the flagship rule from a wrong start"
    assert all(history[i] >= history[i + 1] for i in range(len(history) - 1)), \
        "combined fitness must be monotonically non-increasing across accepted mutations"
    print("Mutation operator converged the DMN term correctly and monotonically. Self-check passed.")
    if constraint_f1 > 0.0:
        # Expected, not a bug -- see this module's own docstring ("Known
        # remaining gap"): the combined objective makes a constraint
        # violation *count*, but M2's row-builder has no repair lever to
        # actually close one on its own. Concretely, here: LECTURE.OFFER_ID
        # has a real FK to COURSE_OFFER.OFFER_ID (flex2_schema_full.json),
        # and this candidate never gained a COURSE_OFFER row -- nothing in
        # candidate_values' vocabulary lets mutation add one.
        print(f"  (Residual {constraint_f1:.4f} of schema/DB constraint distance remains -- expected: "
              f"the mutation vocabulary has no lever yet to add the missing COURSE_OFFER row "
              f"LECTURE.OFFER_ID's own FK needs; see this module's docstring.)")

    print()
    print("derived_case regression check (semesterType, found while first testing this module):")
    load_rec = next(r for r in data if r['record_id'] == 'FLEX2::Course Load Limit::Decision_CourseLoadLimit_Rule_4')
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
