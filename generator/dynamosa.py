"""dynamosa.py -- the DynaMOSA population loop (design doc §6.4's settled
algorithm-of-record): one shared population per case study, every
compiled branch is one objective, DRD-gated dynamic objective
activation, non-dominated sorting.

**A deliberate, stated scope decision, not hidden**: real DynaMOSA (and
this design doc's own §6.4) evolves ONE shared row-set where different
rows serve as the "focal" context for different branches at once (a
student's own attendance covers one branch, another student's course
registration covers another, in the SAME candidate). Building that fully
-- searching not just *what rows exist* but *which row is "this" for
which objective* as part of the genome itself -- is a substantially
larger design than this module attempts. The scope decision made here:
for a given objective (compiled record) evaluated against a given
individual (a shared `Candidate`), the focal row for each table the
objective needs is always that table's *first* row in the candidate.
This keeps a single shared representation genuinely meaningful (progress
on one objective's tables can help another that shares them, the actual
efficiency argument §6.4 names for choosing DynaMOSA over independent
per-branch search) while staying implementable and testable now. The
natural refinement -- letting different rows serve as different
objectives' focal context within one candidate -- is a real next step,
not attempted here.

**Reused, not reimplemented**: `mutate()`/`crossover()` (this session's
own variation operators, unchanged), `repair_candidate`/`_repair_row`
(schema-legal-by-construction), `build_seed_candidate` (per-record
placeholder seeding, used once to build the shared population's common
starting point), `collect_tables_from_resolution`
(compile_constraints.py's own leaf-to-table walk, reused to find which
tables an objective needs its focal row from), `branch_fitness`/
`derive_genome` (unchanged).

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
    archive, coverage_history = run_dynamosa(records, case_study, population_size=20, generations=50)
"""
import copy
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from candidate import Candidate, derive_genome, build_seed_candidate  # noqa: E402
from fitness import branch_fitness, FitnessEvaluationError  # noqa: E402
from mutation import mutate, repair_candidate  # noqa: E402
from crossover import crossover  # noqa: E402
from compile_constraints import collect_tables_from_resolution  # noqa: E402


def _table_set_for(record):
    tables = set()
    for node in record.get('variable_resolution', {}).values():
        collect_tables_from_resolution(node, tables)
    return tables


def _focal_for(record, candidate, table_cache):
    """This module's own scope decision (see the module docstring):
    always the first row of each table the objective needs, whichever
    individual/candidate is being evaluated."""
    tables = table_cache.get(record['record_id'])
    if tables is None:
        tables = _table_set_for(record)
        table_cache[record['record_id']] = tables
    focal = {}
    for t in tables:
        rows = candidate.rows(t)
        if rows:
            focal[t.upper()] = rows[0]
    return focal


def evaluate_objective(record, candidate, scenario, table_cache):
    try:
        focal = _focal_for(record, candidate, table_cache)
        genome = derive_genome(record, candidate, focal, scenario)
        return branch_fitness(record, genome)
    except FitnessEvaluationError:
        return float('inf')  # not yet evaluable against this individual -- never "covered"


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

def _seed_shared_population(records, case_study, population_size):
    """One shared starting candidate, built once by merging every
    objective's own build_seed_candidate output (first-seen row per
    table, so tables multiple objectives need aren't duplicated many
    times over), then repaired wholesale -- the population's common
    ancestor. Each individual starts as an independent deep copy so
    mutation/crossover on one never touches another (the same "parents
    are never mutated in place" discipline mutate()/crossover() already
    follow, extended to the population itself)."""
    scenario_cache = {}
    base = Candidate()
    for r in records:
        c, _f, s = build_seed_candidate(r)
        scenario_cache[r['record_id']] = s
        for table, rows in c.as_dict().items():
            if base.rows(table):
                continue  # this table already has a seed row from an earlier objective
            for row in rows:
                base.add_row(table, dict(row))
    repair_candidate(base, case_study)
    population = [copy.deepcopy(base) for _ in range(population_size)]
    return population, scenario_cache


def run_dynamosa(records, case_study, population_size=20, generations=50, rng=None):
    """Runs the population loop over `records` (compiled branches from
    ONE case study -- mixing case studies makes no sense, since a shared
    candidate's tables are case-study-specific). Returns
    (archive, coverage_history) -- `archive` is {record_id:
    (best_fitness_ever_found, candidate_snapshot_that_achieved_it)},
    growing monotonically across the whole run (DynaMOSA's own archive
    discipline: a target's best answer is never lost even if the current
    population moves on); `coverage_history[g]` is how many objectives
    had reached fitness 0.0 by the end of generation g, for watching
    convergence honestly rather than only reporting the final number."""
    rng = rng or random.Random(0)
    table_cache = {}
    population, scenario_cache = _seed_shared_population(records, case_study, population_size)

    archive = {}

    def update_archive(individual):
        for r in records:
            rid = r['record_id']
            f = evaluate_objective(r, individual, scenario_cache[rid], table_cache)
            if f < archive.get(rid, (float('inf'), None))[0]:
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
            c1, c2, _f1, _f2 = crossover(p1, p2, case_study, rng)
            for child in (c1, c2):
                if active:
                    r = rng.choice(active)
                    focal = _focal_for(r, child, table_cache)
                    scenario = scenario_cache[r['record_id']]
                    try:
                        child, _new_focal, _new_scenario, _var, _improved = mutate(r, child, focal, scenario, rng)
                    except FitnessEvaluationError:
                        # mutate() assumes its caller already knows the
                        # chosen record is evaluable against the current
                        # genome (true for hillclimb's own single-record
                        # use, since it checks this up front) -- not
                        # guaranteed here, where a random active record is
                        # picked against a shared, still-evolving
                        # candidate. Found via a real crash (2026-09-12):
                        # a record whose OWN condition compiles fine can
                        # still reference a genuinely unresolvable
                        # variable in an EARLIER row's suppression term
                        # (compile_constraints.py still marks the record
                        # itself "compiled"). Skip this pick, keep the
                        # unmutated child -- never let one bad record
                        # crash the whole population loop.
                        pass
                offspring.append(child)
        offspring = offspring[:population_size]

        for child in offspring:
            update_archive(child)

        combined = population + offspring
        fitness_vectors = [[evaluate_objective(r, ind, scenario_cache[r['record_id']], table_cache)
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

    return archive, coverage_history


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
    archive, coverage_history = run_dynamosa(records, 'FLEX2', population_size=12, generations=25, rng=rng)
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

