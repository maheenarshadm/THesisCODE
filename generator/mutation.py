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

Usage:
    from mutation import mutate, hillclimb
    child_candidate = mutate(record, candidate, focal, scenario, rng)
    solved_candidate, history = hillclimb(record, candidate, focal, scenario)
"""
import copy
import json
import os
import random
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from candidate import Candidate, derive_genome, derive_value, _mechanical_filter_predicate  # noqa: E402
from fitness import branch_fitness, distance_to_true, FitnessEvaluationError  # noqa: E402
from compile_constraints import CASE_STUDY_SCHEMA_JSON, find_all_variable_refs  # noqa: E402

BOOLEAN_LEAF_KINDS = {'null_check', 'any_not_null', 'join_null_check', 'exists',
                      'regex_match', 'raw_sql_boolean'}
FIELD_LEAF_KINDS = {'schema_column', 'null_check', 'any_not_null', 'join_lookup',
                    'join_null_check', 'regex_match', 'derived_case'}
AGGREGATE_LEAF_KINDS = {'derived_aggregate', 'exists'}

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

def _collect_literal_comparisons(node, var_name, out):
    if not isinstance(node, dict):
        return
    op = node.get('op')
    if op in ('=', '!='):
        left, right = node.get('left'), node.get('right')
        if isinstance(left, dict) and left.get('kind') == 'variable' and left.get('ref') == var_name \
                and isinstance(right, dict) and right.get('kind') == 'literal':
            out.add(right['value'])
        if isinstance(right, dict) and right.get('kind') == 'variable' and right.get('ref') == var_name \
                and isinstance(left, dict) and left.get('kind') == 'literal':
            out.add(left['value'])
    elif op == 'in':
        left = node.get('left')
        if isinstance(left, dict) and left.get('kind') == 'variable' and left.get('ref') == var_name:
            for v in node.get('values', []):
                if isinstance(v, dict) and v.get('kind') == 'literal':
                    out.add(v['value'])
    for key in ('left', 'right', 'clause', 'cond', 'then', 'else'):
        if key in node:
            _collect_literal_comparisons(node[key], var_name, out)
    for key in ('clauses', 'values'):
        for child in node.get(key, []):
            _collect_literal_comparisons(child, var_name, out)


def enumerable_domain(record, var_name):
    """-> sorted list of distinct literal values var_name is compared
    against via =/!=/in anywhere in this record's own condition or
    FIRST/UNIQUE earlier-row conditions, or None if it's never compared
    that way (e.g. only via </>=, which has no finite domain to enumerate)."""
    found = set()
    _collect_literal_comparisons(record['condition'], var_name, found)
    for row in record.get('hit_policy_context', {}).get('earlier_rows', []):
        _collect_literal_comparisons(row['condition'], var_name, found)
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
        return [v for v in domain if v != current] or domain
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
    if kind == 'derived_aggregate':
        base = current if isinstance(current, (int, float)) else 0
        return [max(0, base - step), base + step]
    return []


def _hypothetical_fitness(record, genome, var_name, value):
    trial = dict(genome)
    trial[var_name] = value
    try:
        return branch_fitness(record, trial)
    except FitnessEvaluationError:
        return float('inf')  # an invalid trial value should never be picked


def best_value_for(record, genome, var_name, node, case_study):
    """Tries every candidate replacement for var_name and returns
    (best_value, best_fitness, improved) -- 'improved' is False when
    nothing beats the current value, meaning this variable is already
    locally optimal and mutate() should try a different one instead."""
    current = genome.get(var_name)
    current_fitness = branch_fitness(record, genome)
    best_value, best_fitness = current, current_fitness
    for value in candidate_values(record, var_name, node, current, case_study):
        f = _hypothetical_fitness(record, genome, var_name, value)
        if f < best_fitness:
            best_value, best_fitness = value, f
    return best_value, best_fitness, best_value != current


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


def _apply_row_count_mutation(node, value, candidate, scenario, current):
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
        _apply_row_count_mutation(node, value, candidate, scenario, current)
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
    replacement value (by hypothetical fitness, tried in-genome before
    touching any real row), and applies it via M1 or M2 to a *copy* of
    `candidate`/`focal`/`scenario` -- parents are never mutated in place.
    Returns (new_candidate, new_focal, new_scenario, mutated_var, improved)."""
    rng = rng or random
    genome = derive_genome(record, candidate, focal, scenario)
    leaves = [(v, n) for v, n in _leaf_variables(record) if v in genome]
    if not leaves:
        return candidate, focal, scenario, None, False
    var_name, node = rng.choice(leaves)
    best_value, best_fitness, improved = best_value_for(record, genome, var_name, node, record['case_study'])
    if not improved:
        return candidate, focal, scenario, var_name, False

    new_candidate = copy.deepcopy(candidate)
    new_focal = copy.deepcopy(focal)
    new_scenario = dict(scenario)
    apply_mutation(record, new_candidate, new_focal, new_scenario, var_name, node, best_value, genome.get(var_name))
    return new_candidate, new_focal, new_scenario, var_name, True


def hillclimb(record, candidate, focal, scenario, max_iters=200, rng=None):
    """Repeated mutation, keeping only non-worsening moves -- a (1+1)
    local search exercising `mutate` end to end. Not DynaMOSA itself (no
    population, no crossover, no multi-objective sorting), but a valid
    standalone way to prove the mutation operator actually converges, and
    a legitimate cheap mode in its own right for a branch simple enough
    not to need the full loop (§6.4's own allowance)."""
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
    print(f"After hillclimb ({len(history)} accepted steps): genome={g1}, fitness={f1:.6f}")
    print(f"Fitness trajectory: {history}")
    assert f1 == 0.0, "mutation operator failed to converge on the flagship rule from a wrong start"
    assert all(history[i] >= history[i + 1] for i in range(len(history) - 1)), \
        "fitness must be monotonically non-increasing across accepted mutations"
    print("Mutation operator converged correctly and monotonically. Self-check passed.")

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
