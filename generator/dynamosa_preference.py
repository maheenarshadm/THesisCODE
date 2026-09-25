"""True DynaMOSA: dynamosa.py's own dynamic-gated population loop, plus
the preference criterion (Panichella et al.) that dynamosa.py's own
`run_dynamosa` never had. Separate file, not a flag on `run_dynamosa`,
so both selection mechanisms stay independently runnable and
byte-for-byte comparable -- dynamosa.py itself untouched.

Ordinary Pareto non-domination (dynamosa.py's own `fast_non_dominated_sort`
alone) can bury an individual that is the SOLE best answer for one
active objective, if that same individual is dominated on every OTHER
active objective -- crowding then has no reason to protect it. The
preference criterion fixes this: for each active objective, whichever
individual(s) achieve the minimal fitness on THAT ONE objective are
guaranteed into front 0, before ordinary non-dominated sorting runs on
everyone else. This is the one piece of the literature's DynaMOSA that
dynamosa.py's own docstring never claimed -- its `dynamic_gating` flag
only ever isolated the "Dyna" (dependency-gated activation) half.

Everything else here is reused, unmodified, from dynamosa.py: seeding,
archive discipline, activation gating (`is_active`), crossover
(unconditional, whole-candidate, exactly as dynamosa.py's own docstring
describes), mutation (gated to `active`, multi-pick + local-burst),
non-dominated sorting and crowding distance as the fallback tiebreak
once the preference front is carved out. Only the front-construction
step, right before population selection, differs.

Usage:
    from dynamosa_preference import run_dynamosa_preference
    archive, coverage_history, population = run_dynamosa_preference(
        records, case_study, population_size=20, generations=50)
"""
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from dynamosa import (  # noqa: E402
    _seed_shared_population, is_active, _branch_key, _mutations_per_child,
    _local_burst_size, _mutate_objective, evaluate_objective,
    fast_non_dominated_sort, crowding_distance, _KICK_PROBABILITY,
)
from crossover import crossover  # noqa: E402


def _preference_front(fitness_vectors, active):
    """Indices (into `fitness_vectors`) of every individual that is the
    best -- or tied for best -- on at least one active objective. Ties
    all count: DynaMOSA's own preference criterion protects every
    co-optimal individual, not an arbitrary single winner. Empty when
    `active` is empty (nothing to prefer against yet)."""
    if not active:
        return []
    preferred = set()
    for j in range(len(active)):
        col = [fv[j] for fv in fitness_vectors]
        best = min(col)
        preferred.update(i for i, v in enumerate(col) if v == best)
    return sorted(preferred)


def run_dynamosa_preference(records, case_study, population_size=20, generations=50, rng=None,
                             mutations_per_child='auto', kick_probability=_KICK_PROBABILITY,
                             dynamic_gating=True, use_local_burst=True):
    """Same signature, same return shape `(archive, coverage_history,
    population)`, same semantics for every parameter as dynamosa.py's
    own `run_dynamosa` -- see that function's docstring for what each
    one does. The ONLY behavioral difference is the population-selection
    step: this version carves out the preference front first (see
    `_preference_front`) and only runs ordinary non-dominated sorting on
    whichever individuals the preference front didn't already claim."""
    rng = rng or random.Random(0)
    table_cache = {}
    population = _seed_shared_population(records, case_study, population_size)

    archive = {r['record_id']: (float('inf'), population[0]) for r in records}

    def update_archive(individual):
        candidate, focal_maps, scenario_maps = individual
        for r in records:
            rid = r['record_id']
            f = evaluate_objective(r, candidate, focal_maps, scenario_maps, table_cache)
            if f < archive[rid][0]:
                archive[rid] = (f, individual)

    for ind in population:
        update_archive(ind)

    coverage_history = []
    for _gen in range(generations):
        covered_keys = {_branch_key(r) for r in records
                         if archive.get(r['record_id'], (float('inf'), None))[0] == 0.0}
        active = records if not dynamic_gating else [r for r in records if is_active(r, covered_keys)]

        k = _mutations_per_child(active, population_size, mutations_per_child)

        offspring = []
        while len(offspring) < population_size:
            p1, p2 = rng.sample(population, 2) if len(population) >= 2 else (population[0], population[0])
            (p1_c, p1_fm, p1_sm), (p2_c, p2_fm, p2_sm) = p1, p2
            c1, c2, _f1, _f2, fm1, fm2, sm1, sm2 = crossover(
                p1_c, p2_c, case_study, rng, focal_maps1=p1_fm, focal_maps2=p2_fm,
                scenario_maps1=p1_sm, scenario_maps2=p2_sm)
            for child_c, child_fm, child_sm in ((c1, fm1, sm1), (c2, fm2, sm2)):
                if active:
                    for r in rng.sample(active, min(k, len(active))):
                        burst = _local_burst_size(r) if use_local_burst else 1
                        for _ in range(burst):
                            child_c, child_fm, child_sm, _improved = _mutate_objective(
                                r, child_c, child_fm, child_sm, table_cache, rng,
                                kick_probability=kick_probability)
                offspring.append((child_c, child_fm, child_sm))
        offspring = offspring[:population_size]

        for child in offspring:
            update_archive(child)

        combined = population + offspring
        fitness_vectors = [[evaluate_objective(r, ind[0], ind[1], ind[2], table_cache)
                             for r in active] for ind in combined]

        # Preference criterion first: guaranteed front 0. Ordinary
        # non-dominated sorting then runs ONLY on whoever it didn't
        # already claim, so nobody is double-counted across two fronts.
        pref_front = _preference_front(fitness_vectors, active)
        pref_set = set(pref_front)
        remaining = [i for i in range(len(combined)) if i not in pref_set]
        remaining_vectors = [fitness_vectors[i] for i in remaining]
        local_fronts = fast_non_dominated_sort(remaining_vectors) if remaining else []
        mapped_fronts = [[remaining[j] for j in front] for front in local_fronts]
        fronts = ([pref_front] if pref_front else []) + mapped_fronts

        new_population = []
        for front in fronts:
            if len(new_population) + len(front) <= population_size:
                new_population.extend(combined[i] for i in front)
            else:
                cd = crowding_distance(front, fitness_vectors)
                front_sorted = sorted(front, key=lambda i: -cd[i])
                new_population.extend(combined[i] for i in front_sorted[:population_size - len(new_population)])
                break
        population = new_population or population

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

    records = [
        find('Decision_AcademicWarningStatus_Rule_1'),
        find('Decision_AcademicWarningStatus_Rule_2'),
        find('Decision_CourseLoadLimit_Rule_1::via::Academic Warning Status::Decision_AcademicWarningStatus_Rule_1'),
        find('Decision_CourseLoadLimit_Rule_1::via::Academic Warning Status::Decision_AcademicWarningStatus_Rule_2'),
    ]
    for r in records:
        print(f"  {r['record_id']} <- {r.get('grounded_upstream_branches')}")

    start = time.time()
    rng = random.Random(0)
    archive, coverage_history, _final_population = run_dynamosa_preference(
        records, 'FLEX2', population_size=12, generations=25, rng=rng)
    elapsed = time.time() - start

    print(f"\nCoverage history across {len(coverage_history)} generations: {coverage_history}")
    print(f"Elapsed: {elapsed:.1f}s for {len(records)} objectives, population 12, 25 generations")
    for r in records:
        f, _c = archive.get(r['record_id'], (float('inf'), None))
        print(f"  {'COVERED' if f == 0.0 else f'fitness={f:.4f}'}  {r['record_id']}")

    assert all(coverage_history[i] <= coverage_history[i + 1] for i in range(len(coverage_history) - 1)), \
        "the archive's own covered-count must never regress across generations"
    print("\nConfirmed: coverage is monotonically non-decreasing (the archive never regresses).")

    covered_keys = {_branch_key(r) for r in records if archive.get(r['record_id'], (float('inf'), None))[0] == 0.0}
    for r in records:
        f, _c = archive.get(r['record_id'], (float('inf'), None))
        if f == 0.0 and r.get('grounded_upstream_branches'):
            for dep_key in r['grounded_upstream_branches']:
                assert dep_key in covered_keys, \
                    f"{r['record_id']} covered but dependency {dep_key} is not -- gating broken"
    print("Confirmed: DRD-gating invariant holds (no covered objective with an uncovered dependency).")
