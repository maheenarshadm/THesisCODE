"""dynamosa.py -- the DynaMOSA population loop (design doc §6.4's settled
algorithm-of-record): one shared population per case study, every
compiled branch is one objective, DRD-gated dynamic objective
activation, non-dominated sorting.

**Focal-per-objective (2026-09-12, replacing the earlier "first row per
table" scope decision)**: real DynaMOSA (and this design doc's own §6.4)
evolves ONE shared row-set where different rows serve as the "focal"
context for different branches at once (a student's own attendance
covers one branch, another student's course registration covers
another, in the SAME candidate). The first version of this module took a
deliberate, smaller scope instead -- every objective's focal row for a
table was always that table's *first* row in the candidate -- which
stayed implementable and testable, but a real, measured diagnostic on
the full FLEX2 case study found this was the DOMINANT cause of low
coverage: 58 of 83 uncovered branches (~70%) failed outright with a
missing-column `FitnessEvaluationError`, because different objectives
needing different columns/values on the very same physical row
overwrote each other. This module now gives every objective its OWN
dedicated row per table it needs a focal row for (never another
objective's), created lazily the first time that objective is actually
picked for mutation (`_focal_for_mutate`), and looked up read-only,
never created, during fitness evaluation (`_focal_for_read` -- called far
more often, once per objective per individual per generation, so it must
never itself grow the candidate). Individuals are therefore no longer
bare `Candidate` objects but `(candidate, focal_maps)` pairs, where
`focal_maps` is `{record_id: {table: row}}` -- see `_focal_for_read`/
`_focal_for_mutate`/`_mutate_objective`'s own docstrings for the exact
mechanics, and `crossover.py`'s own `focal_maps1`/`focal_maps2`
parameters (added alongside this) for how a table swap during crossover
carries every objective's own dedicated row for that table along with
it, not just one record's.

Not every table a record's own resolution mentions gets a dedicated
focal row -- only the ones a leaf kind actually *reads through* a focal
row at all (`_focal_tables_for_leaf`): `derived_aggregate`/`exists`
kinds scan `candidate.rows(table)` directly, across the WHOLE shared
candidate, and never consult focal -- handing them a fresh, empty
dedicated row would be actively wrong for an unconditional
`derived_aggregate` (an empty row can trivially match a filter with no
real conjuncts, silently inflating the count by one for a row that
carries no real data at all). This uneven table-sharing for
aggregate/exists kinds is a real, known, DELIBERATELY UNCHANGED scope
limitation carried over unmodified from the original design -- fixing it
(so that different objects' rows don't cross-pollute each other's
counts) is a distinct, larger refinement not attempted here.

**Reused, not reimplemented**: `mutate()`'s own building blocks --
`best_value_for`/`apply_mutation`/`_leaf_variables` (this module's own
`_mutate_objective` reimplements `mutate()`'s own control flow rather
than calling it directly, since `mutate()`'s own `copy.deepcopy((candidate,
focal))` only ever covers ONE record's own single `focal` dict -- calling
it as-is here would silently break the aliasing between `candidate`'s
rows and every OTHER objective's own focal entries still sitting in the
same individual's `focal_maps`) -- `crossover()` (extended, not
reimplemented, with the new `focal_maps1`/`focal_maps2` parameters),
`repair_candidate`/`_repair_row` (schema-legal-by-construction),
`build_seed_candidate` (per-record placeholder seeding, used once per
objective to build that objective's own dedicated seed rows),
`branch_fitness`/`derive_genome` (unchanged). `compile_constraints.py`'s
own `collect_tables_from_resolution` (the earlier design's "every table
this record's resolution mentions at all" walk) is no longer used here --
`_focal_tables_for_leaf`/`_focal_table_set_for` replace it with a
narrower, focal-specific walk (see above).

**DRD-gated activation**: each compiled record already carries its own
`grounded_upstream_branches` -- the exact list of `"decision::rule_id"`
branches its own condition depends on (populated by compile_constraints.py
from the DRD `informationRequirement` edges it walked at compile time,
not re-derived here). An objective is active once every branch it names
has been *covered* (fitness 0.0) by some individual across the whole
run's own archive -- not the current population, since DynaMOSA's own
archive of best-per-objective solutions only grows, never regresses.

**Non-dominated sorting**: a standard NSGA-II fast-non-dominated-sort +
crowding distance, computed only over currently-active objectives (the
"Dyna" part of DynaMOSA: objectives outside the active set exert zero
selection pressure at all, per §6.4's own framing).

Usage:
    from dynamosa import run_dynamosa
    archive, coverage_history, population = run_dynamosa(records, case_study, population_size=20, generations=50)
"""
import copy
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from candidate import Candidate, derive_genome, build_seed_candidate  # noqa: E402
from fitness import branch_fitness, FitnessEvaluationError, _unique_key_sets  # noqa: E402
from mutation import (repair_candidate, best_value_for, apply_mutation,  # noqa: E402
                       _leaf_variables, _schema_for)
from crossover import crossover  # noqa: E402


def _focal_tables_for_leaf(node):
    """The specific table(s) THIS leaf node's own kind actually reads
    through a *focal* row (see candidate.py's derive_value) -- a strict
    subset of "every table this record's resolution mentions at all"
    (`compile_constraints.py`'s own `collect_tables_from_resolution`,
    used by the earlier "first row per table" design). `derived_aggregate`/
    `exists`/`raw_sql_boolean` kinds scan `candidate.rows(table)` directly
    across the WHOLE shared candidate and never consult focal at all --
    deliberately excluded here (see this module's own docstring on why
    handing them a dedicated-but-empty row would be actively wrong, not
    just unnecessary). `join_lookup`/`join_null_check`'s own
    `result_table` is likewise excluded: it's found by a primary-key scan
    over the whole candidate (`_find_row_by_pk`), never through focal --
    only `local_table` (the row that supplies the join key) is read
    through focal."""
    kind = node.get('kind')
    if kind in ('schema_column', 'null_check', 'derived_case'):
        return {node['table']}
    if kind == 'any_not_null':
        return {c['table'] for c in node.get('columns', [])}
    if kind in ('join_lookup', 'join_null_check'):
        return {node['via']['local_table']}
    if kind == 'regex_match':
        return {node['value_column']['table'], node['pattern_column']['table']}
    if kind == 'derived_join_count':
        return {node['registration_table']}
    return set()


def _focal_table_set_for(record):
    """Every table SOME leaf of this record's own condition reads through
    a focal row -- recurses through substituted_decision chains exactly
    like `_leaf_variables`'s own walk (a leaf nested inside a
    substituted_decision's own free_variable_resolutions isn't a
    top-level key of record['variable_resolution'] either)."""
    tables = set()

    def walk(node):
        if not isinstance(node, dict):
            return
        if node.get('kind') == 'substituted_decision':
            for sub in node.get('free_variable_resolutions', {}).values():
                walk(sub)
            return
        tables.update(_focal_tables_for_leaf(node))

    for node in record.get('variable_resolution', {}).values():
        walk(node)
    return tables


def _focal_for_read(record, focal_maps):
    """Read-only lookup of this objective's own dedicated focal row per
    table -- NEVER any other objective's, the actual fix for this
    module's earlier "first row per table" scope decision -- and NEVER
    creates a row (row creation is `_focal_for_mutate`'s job alone,
    triggered only when this objective is actually picked for mutation;
    this function is called once per objective per individual per
    generation during fitness evaluation, far more often than mutation
    attempts, so it must stay strictly read-only).

    A table this objective hasn't been given its own dedicated row for
    yet is simply omitted from the returned dict -- exactly like the
    original design's own behavior when a table had zero rows at all:
    `derive_value`'s lookup-based kinds (`_lookup(focal, table, column)`)
    raise `FitnessEvaluationError` naturally for a table genuinely
    missing from focal (an honest "not yet evaluable", never silently
    borrowing some OTHER objective's own row instead), while
    `derived_aggregate`/`exists` kinds never consult focal in the first
    place and are unaffected either way."""
    return dict(focal_maps.get(record['record_id'], {}))


def _focal_for_mutate(record, candidate, focal_maps, table_cache):
    """Like `_focal_for_read`, but creates (via `candidate.add_row`) a
    brand-new, empty dedicated row the FIRST time this objective needs
    one for a given table, recording it in
    `focal_maps[record_id][table]` for all future reuse -- both future
    mutation attempts and read-only evaluation from then on. Only called
    once this objective has actually been chosen to mutate this
    generation (never during fitness evaluation itself), so row creation
    stays bounded by mutation attempts, not by the much larger number of
    fitness evaluations NSGA-II's own sorting performs every generation."""
    tables = table_cache.get(record['record_id'])
    if tables is None:
        tables = _focal_table_set_for(record)
        table_cache[record['record_id']] = tables
    rec_focal = focal_maps.setdefault(record['record_id'], {})
    focal = {}
    for t in tables:
        tU = t.upper()
        row = rec_focal.get(tU)
        if row is None:
            row = candidate.add_row(t, {})
            rec_focal[tU] = row
        focal[tU] = row
    return focal


def evaluate_objective(record, candidate, focal_maps, scenario, table_cache):
    try:
        focal = _focal_for_read(record, focal_maps)
        genome = derive_genome(record, candidate, focal, scenario)
        return branch_fitness(record, genome)
    except FitnessEvaluationError:
        return float('inf')  # not yet evaluable against this individual -- never "covered"


def _mutate_objective(record, candidate, focal_maps, scenario_cache, table_cache, rng=None):
    """The population loop's own variation step for a single objective --
    reimplements mutation.py's own `mutate()` control flow (pick a random
    leaf variable, find its best replacement value via `best_value_for`,
    apply it via M1/M2) rather than calling `mutate()` directly, because
    `mutate()`'s own `copy.deepcopy((candidate, focal))` only ever covers
    ONE record's own single `focal` dict -- calling it as-is from here
    would silently break the aliasing between `candidate`'s rows and
    every OTHER objective's own focal entries still sitting in this same
    individual's `focal_maps` (the exact class of bug crossover.py's own
    `focal_maps1`/`focal_maps2` extension was built to avoid, applied
    here too). `candidate`/`focal_maps` are only ever replaced together,
    in one joint deepcopy, never touched in place -- parents are never
    mutated, the same discipline `mutate()` itself follows.

    Returns (new_candidate, new_focal_maps, improved) -- a scenario
    mutation (the `not_persisted` leaf kind) is applied to a throwaway
    copy of `scenario` and then discarded, exactly like the population
    loop's own previous direct use of `mutate()` already did (that
    `_new_scenario` return value was likewise never propagated back into
    `scenario_cache`) -- a real, pre-existing, unchanged limitation, not
    a new one introduced here.

    Both the initial genome computation AND `best_value_for` itself are
    wrapped in one try/except, exactly the same real crash `mutate()`'s
    own former direct use in this module's population loop was already
    found to need guarding against (2026-09-12) -- `best_value_for`'s own
    first call is `branch_fitness(record, genome)`, itself unguarded
    internally, since `mutate()` never wrapped it either (this module's
    population loop always wrapped the WHOLE `mutate()` call from
    outside instead). A freshly-created, still-empty dedicated row
    (`_focal_for_mutate` seeds it with `{}`, not real values) can leave
    some OTHER leaf of this same record (e.g. a `chained_decision_output`
    fact this branch's own suppression term depends on, or
    `derived_join_count`'s own context-row search) genuinely
    unresolvable against the current candidate even though the record
    itself compiles fine -- an honest "not evaluable yet," not a bug to
    crash on."""
    rng = rng or random
    rid = record['record_id']
    scenario = scenario_cache[rid]
    focal = _focal_for_mutate(record, candidate, focal_maps, table_cache)
    try:
        genome = derive_genome(record, candidate, focal, scenario)
        leaves = [(v, n) for v, n in _leaf_variables(record) if v in genome]
        if not leaves:
            return candidate, focal_maps, False
        var_name, node = rng.choice(leaves)
        best_value, _best_fitness, improved = best_value_for(record, genome, var_name, node, record['case_study'])
    except FitnessEvaluationError:
        return candidate, focal_maps, False
    if not improved:
        return candidate, focal_maps, False

    new_candidate, new_focal_maps = copy.deepcopy((candidate, focal_maps))
    new_focal = new_focal_maps[rid]
    scenario_copy = dict(scenario)
    try:
        apply_mutation(record, new_candidate, new_focal, scenario_copy, var_name, node, best_value, genome.get(var_name))
    except FitnessEvaluationError:
        return candidate, focal_maps, False
    return new_candidate, new_focal_maps, True


def _branch_key(record):
    return f"{record['decision_name']}::{record['rule_id']}"


def is_active(record, covered_keys):
    deps = record.get('grounded_upstream_branches') or []
    return all(d in covered_keys for d in deps)


# ---------------------------------------------------------------------------
# Standard NSGA-II machinery -- unmodified from its own textbook form,
# applied here to whichever objective set is currently active.
# ---------------------------------------------------------------------------

def _dominates(a, b):
    return all(x <= y for x, y in zip(a, b)) and any(x < y for x, y in zip(a, b))


def fast_non_dominated_sort(fitness_vectors):
    n = len(fitness_vectors)
    dominated_by = [set() for _ in range(n)]
    domination_count = [0] * n
    fronts = [[]]
    for p in range(n):
        for q in range(n):
            if p == q:
                continue
            if _dominates(fitness_vectors[p], fitness_vectors[q]):
                dominated_by[p].add(q)
            elif _dominates(fitness_vectors[q], fitness_vectors[p]):
                domination_count[p] += 1
        if domination_count[p] == 0:
            fronts[0].append(p)
    i = 0
    while fronts[i]:
        next_front = []
        for p in fronts[i]:
            for q in dominated_by[p]:
                domination_count[q] -= 1
                if domination_count[q] == 0:
                    next_front.append(q)
        i += 1
        fronts.append(next_front)
    return [f for f in fronts if f]


def crowding_distance(front, fitness_vectors):
    distances = {i: 0.0 for i in front}
    if not front or not fitness_vectors[front[0]]:
        return distances
    num_obj = len(fitness_vectors[front[0]])
    for m in range(num_obj):
        front_sorted = sorted(front, key=lambda i: fitness_vectors[i][m])
        distances[front_sorted[0]] = float('inf')
        distances[front_sorted[-1]] = float('inf')
        vmin, vmax = fitness_vectors[front_sorted[0]][m], fitness_vectors[front_sorted[-1]][m]
        if vmax == vmin or vmax == float('inf'):
            continue
        for k in range(1, len(front_sorted) - 1):
            distances[front_sorted[k]] += (
                (fitness_vectors[front_sorted[k + 1]][m] - fitness_vectors[front_sorted[k - 1]][m])
                / (vmax - vmin))
    return distances


# ---------------------------------------------------------------------------
# The loop itself.
# ---------------------------------------------------------------------------

def _key_columns_for(schema, table):
    """Every column that's part of `table`'s own declared PK/UNIQUE key,
    or a declared FK on `table` -- the set `_seed_shared_population`'s
    own per-objective offsetting must shift consistently, so that two
    independently-seeded objectives' own dedicated rows never collide on
    the exact same small placeholder key value (a real bug found testing
    this refinement at full FLEX2 scale, 2026-09-12: many different
    objectives each seeding their own COURSE row with the identical
    placeholder COURSE_ID produced real UNIQUE-constraint failures
    `validate_with_sqlite` caught immediately -- the earlier "first row
    per table" design never hit this, since it only ever had ONE row per
    table, total, across every objective). Deliberately narrow -- a
    genuine business-value column (a lecture count, a GPA, ...) a DMN
    branch actually searches over must never be shifted, or hillclimb's
    own starting point for it would be dragged arbitrarily far from a
    real target for no reason."""
    real = table if table in schema else (
        table.upper() if table.upper() in schema else (
            table.lower() if table.lower() in schema else table))
    info = schema.get(real, {})
    cols = {c.upper() for keyset in _unique_key_sets(schema, real) for c in keyset}
    cols |= {fk['column'].upper() for fk in (info.get('fk_columns') or [])}
    return cols


_SEED_KEY_OFFSET_UNIT = 1_000_000  # generous: FLEX2 has ~250 records, nowhere near exhausting int range


def _seed_shared_population(records, case_study, population_size):
    """One shared starting candidate, built once by giving every
    objective its OWN dedicated seed rows (from that record's own
    `build_seed_candidate` output) -- added as fresh, ADDITIONAL rows on
    the shared base candidate, never deduplicated/merged against another
    objective's own seed rows the way the earlier "first row per table"
    design did (see this module's own docstring on why that sharing was
    the dominant, measured cause of low coverage). `base_focal_maps
    [record_id]` records exactly which of those newly-added rows belong
    to that objective, found via an `id(row)` correspondence between
    `build_seed_candidate`'s own returned `focal` dict (its "this is the
    row this leaf actually reads" view) and the copies actually inserted
    into `base` -- not every table `build_seed_candidate`'s own candidate
    has rows for shows up in its own `focal` (`derived_aggregate`/
    `exists`/`raw_sql_boolean` kinds add rows directly, never through
    focal -- see `_focal_tables_for_leaf`), so this naturally seeds ONLY
    the tables this refinement actually needs a per-objective row for;
    the rest is created lazily by `_focal_for_mutate` the first time some
    other leaf kind needs it.

    Every objective's own key/FK column values (see `_key_columns_for`)
    are shifted by a per-objective offset (`i * _SEED_KEY_OFFSET_UNIT`)
    before merging into `base` -- the fix for the real UNIQUE-collision
    bug `_key_columns_for`'s own docstring describes. The SAME offset is
    also applied to every numeric value in this objective's own seeded
    `scenario` (`build_seed_candidate`'s own `<placeholder>` bindings,
    e.g. `<student>` -> `scenario['student']`), not just its rows: a
    `derived_aggregate` seed row built by `_row_from_filter_conjuncts`
    sets a key column (e.g. `ROLL_NO`) directly FROM the matching
    scenario value (`ROLL_NO = <student>` -> `row['ROLL_NO'] =
    scenario['student']`) -- offsetting the row's own copy without
    offsetting `scenario` by the identical amount would silently break
    that equality the moment the filter predicate re-reads `scenario` at
    match time, found exactly this way testing this fix. `__today__`
    (a date, not a key) is deliberately excluded.

    Repaired once, wholesale, after every objective's own rows are in --
    the population's common ancestor. Each individual starts as an
    independent joint deep copy of `(base, base_focal_maps)` so
    mutation/crossover on one never touches another (the same "parents
    are never mutated in place" discipline mutate()/crossover() already
    follow, extended to the population itself)."""
    schema = _schema_for(case_study)
    scenario_cache = {}
    base = Candidate()
    base_focal_maps = {}
    for i, r in enumerate(records):
        rid = r['record_id']
        c, f, s = build_seed_candidate(r)
        offset = i * _SEED_KEY_OFFSET_UNIT
        for key, val in s.items():
            if key != '__today__' and isinstance(val, (int, float)) and not isinstance(val, bool):
                s[key] = val + offset
        scenario_cache[rid] = s
        id_to_copy = {}
        for table, rows in c.as_dict().items():
            key_cols = _key_columns_for(schema, table)
            for row in rows:
                if key_cols:
                    for col in list(row):
                        if col.upper() in key_cols and isinstance(row[col], (int, float)) \
                                and not isinstance(row[col], bool):
                            row[col] = row[col] + offset
                row_copy = dict(row)
                base.add_row(table, row_copy)
                id_to_copy[id(row)] = row_copy
        rec_focal = {table: id_to_copy[id(row)] for table, row in f.items() if id(row) in id_to_copy}
        if rec_focal:
            base_focal_maps[rid] = rec_focal
    repair_candidate(base, case_study)
    population = [copy.deepcopy((base, base_focal_maps)) for _ in range(population_size)]
    return population, scenario_cache


def run_dynamosa(records, case_study, population_size=20, generations=50, rng=None):
    """Runs the population loop over `records` (compiled branches from
    ONE case study -- mixing case studies makes no sense, since a shared
    candidate's tables are case-study-specific). Returns
    (archive, coverage_history, population) -- `archive` is {record_id:
    (best_fitness_ever_found, individual_that_achieved_it)}, growing
    monotonically across the whole run (DynaMOSA's own archive
    discipline: a target's best answer is never lost even if the current
    population moves on); `coverage_history[g]` is how many objectives
    had reached fitness 0.0 by the end of generation g, for watching
    convergence honestly rather than only reporting the final number;
    `population` is the final generation's own individuals -- exposed so
    a caller (generate_dataset.py) can pick ONE real, self-consistent
    candidate to actually materialize, rather than the archive's own
    per-objective-best snapshots, which were captured at different points
    in the run and were never guaranteed consistent with each other.

    Each "individual" throughout this function is a `(candidate,
    focal_maps)` pair, not a bare `Candidate` -- `focal_maps` is
    `{record_id: {table: row}}`, this module's own focal-per-objective
    refinement (see the module docstring): every objective's own
    dedicated row per table travels WITH its candidate through crossover
    and mutation, rather than every objective sharing whichever row
    happens to be "first" in a bare `Candidate`."""
    rng = rng or random.Random(0)
    table_cache = {}
    population, scenario_cache = _seed_shared_population(records, case_study, population_size)

    # Every record gets a real entry from the start, even one that turns
    # out permanently unresolvable (inf against every individual all run)
    # -- a real KeyError found wiring this into generate_dataset.py
    # (2026-09-12): update_archive's own strict `<` comparison never
    # improves on inf with inf, so a record that's inf for every
    # individual, always, never got a key at all, and any caller that
    # didn't defensively .get() the archive crashed. An honest "never
    # covered, inf" entry is the correct initial state, not an absent key.
    archive = {r['record_id']: (float('inf'), population[0]) for r in records}

    def update_archive(individual):
        candidate, focal_maps = individual
        for r in records:
            rid = r['record_id']
            f = evaluate_objective(r, candidate, focal_maps, scenario_cache[rid], table_cache)
            if f < archive[rid][0]:
                archive[rid] = (f, individual)

    for ind in population:
        update_archive(ind)

    coverage_history = []
    for _gen in range(generations):
        covered_keys = {_branch_key(r) for r in records
                         if archive.get(r['record_id'], (float('inf'), None))[0] == 0.0}
        active = [r for r in records if is_active(r, covered_keys)]

        offspring = []
        while len(offspring) < population_size:
            p1, p2 = rng.sample(population, 2) if len(population) >= 2 else (population[0], population[0])
            (p1_c, p1_fm), (p2_c, p2_fm) = p1, p2
            c1, c2, _f1, _f2, fm1, fm2 = crossover(
                p1_c, p2_c, case_study, rng, focal_maps1=p1_fm, focal_maps2=p2_fm)
            for child_c, child_fm in ((c1, fm1), (c2, fm2)):
                if active:
                    r = rng.choice(active)
                    # _mutate_objective already guards its own genome
                    # computation against FitnessEvaluationError (see its
                    # own docstring) -- a freshly-created, still-empty
                    # dedicated row can leave some OTHER leaf of the same
                    # record genuinely unresolvable, an honest "not
                    # evaluable yet," never a crash.
                    child_c, child_fm, _improved = _mutate_objective(
                        r, child_c, child_fm, scenario_cache, table_cache, rng)
                offspring.append((child_c, child_fm))
        offspring = offspring[:population_size]

        for child in offspring:
            update_archive(child)

        combined = population + offspring
        fitness_vectors = [[evaluate_objective(r, ind[0], ind[1], scenario_cache[r['record_id']], table_cache)
                             for r in active] for ind in combined]
        fronts = fast_non_dominated_sort(fitness_vectors)
        new_population = []
        for front in fronts:
            if len(new_population) + len(front) <= population_size:
                new_population.extend(combined[i] for i in front)
            else:
                cd = crowding_distance(front, fitness_vectors)
                front_sorted = sorted(front, key=lambda i: -cd[i])
                new_population.extend(combined[i] for i in front_sorted[:population_size - len(new_population)])
                break
        population = new_population or population  # never leave the population empty

        covered_count = sum(1 for r in records
                             if archive.get(r['record_id'], (float('inf'), None))[0] == 0.0)
        coverage_history.append(covered_count)

    return archive, coverage_history, population


if __name__ == '__main__':
    import json
    import time

    compiled = json.load(open(os.path.join(HERE, 'compiled_constraints.json')))

    def find(suffix):
        return next(r for r in compiled if r['record_id'].endswith(suffix))

    # A small, deliberately mixed slice: two root objectives (Academic
    # Warning Status has no upstream dependency at all) and two objectives
    # chained on them (Course Load Limit::Rule_1, via each of those same
    # two roots) -- real DRD data, not synthesized, exercising activation
    # gating on a case genuinely present in the corpus.
    records = [
        find('Decision_AcademicWarningStatus_Rule_1'),
        find('Decision_AcademicWarningStatus_Rule_5'),
        find('Decision_CourseLoadLimit_Rule_1::via::Academic Warning Status::Decision_AcademicWarningStatus_Rule_1'),
        find('Decision_CourseLoadLimit_Rule_1::via::Academic Warning Status::Decision_AcademicWarningStatus_Rule_5'),
    ]
    for r in records:
        print(f"  {r['record_id']} <- {r.get('grounded_upstream_branches')}")

    start = time.time()
    rng = random.Random(0)
    archive, coverage_history, _final_population = run_dynamosa(records, 'FLEX2', population_size=12, generations=25, rng=rng)
    elapsed = time.time() - start

    print(f"\nCoverage history across {len(coverage_history)} generations: {coverage_history}")
    print(f"Elapsed: {elapsed:.1f}s for {len(records)} objectives, population 12, 25 generations")
    for r in records:
        f, _c = archive.get(r['record_id'], (float('inf'), None))
        print(f"  {'COVERED' if f == 0.0 else f'fitness={f:.4f}'}  {r['record_id']}")

    assert all(coverage_history[i] <= coverage_history[i + 1] for i in range(len(coverage_history) - 1)), \
        "the archive's own covered-count must never regress across generations"
    print("\nConfirmed: coverage is monotonically non-decreasing (the archive never regresses).")

    # DRD-gating invariant: any covered chained objective's own dependency
    # must ALSO be covered -- if this ever fails, activation gating is
    # broken (a chained target got credit without its prerequisite).
    covered_keys = {_branch_key(r) for r in records if archive.get(r['record_id'], (float('inf'), None))[0] == 0.0}
    for r in records:
        if archive.get(r['record_id'], (float('inf'), None))[0] == 0.0:
            deps = r.get('grounded_upstream_branches') or []
            for d in deps:
                assert d in covered_keys, (
                    f"{r['record_id']} was covered but its own dependency {d!r} was not -- "
                    f"DRD activation gating is broken")
    print("Confirmed: every covered chained objective's own DRD dependency was covered too (gating is real, not bypassed).")

    print(f"\nCovered {sum(1 for r in records if archive.get(r['record_id'], (float('inf'), None))[0] == 0.0)}"
          f"/{len(records)} objectives via the shared population.")

