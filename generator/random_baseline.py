"""random_baseline.py -- an undirected random-search baseline, built for
this project's own evaluation section (RQ: does fitness-guided value
selection plus evolutionary population selection actually outperform
undirected search over the identical representation and constraint
machinery?).

Reuses, byte-for-byte, everything about the representation and
correctness machinery `dynamosa.py`/`mutation.py` already provide:
`Candidate`, `derive_genome`/`branch_fitness` (the same fitness function,
never a different or looser one), the same schema-legality repair
(`apply_mutation` -> `_repair_row`), the same per-objective focal/scenario
bookkeeping, the same dependency-gated active-objective computation
(`is_active`), the same per-generation evaluation-budget scaling
(`_mutations_per_child`/`_local_burst_size`), and the same permanent,
best-ever-per-objective archive discipline `update_archive` already
implements in `run_dynamosa`.

Exactly two things are deliberately different, and ONLY these two, so a
coverage difference against `run_dynamosa` is attributable to the search
STRATEGY rather than to an unfairly different representation, move menu,
or evaluation budget:

1. **Value selection is uniform-random, not fitness-guided.** Each
   mutation attempt still targets one randomly chosen leaf of one
   randomly chosen active objective (same as `_mutate_objective`), and
   still draws its candidate replacement values from `candidate_values()`
   -- the identical move menu `best_value_for`'s own AVM search uses --
   but picks UNIFORMLY AT RANDOM from that menu instead of trying every
   candidate's hypothetical fitness and keeping the best. The chosen
   value is applied UNCONDITIONALLY (never rejected for being worse),
   since a real random search has no fitness oracle guiding its moves at
   all, only a menu of structurally valid things to try.

2. **No crossover, no NSGA-II environmental selection.** `population_size`
   independent lineages are held across the whole run; each generation,
   every lineage independently receives the same number of random
   mutation attempts a guided child would receive, with no recombination
   between lineages and no fitness-based survivor selection at all --
   a lineage simply carries forward whatever state its own random walk
   produced, exactly like a plain random-search process, never favoring
   one lineage over another.

Deliberately NOT applied: `known_constants.json`'s domain-expert pinning
(the shortcut `best_value_for`/`_mutate_objective` check before ever
calling `candidate_values`). A real random search has no such domain
intervention available to it -- giving it the pin anyway would let it
"cheat" via directed knowledge it never itself discovered, undermining
the very comparison this module exists to make.

Usage:
    from random_baseline import run_random_search
    archive, coverage_history, population = run_random_search(
        records, case_study, population_size=30, generations=40, rng=random.Random(0))
"""
import copy
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from candidate import derive_genome  # noqa: E402
from fitness import FitnessEvaluationError  # noqa: E402
from mutation import _leaf_variables, candidate_values, apply_mutation, BOOLEAN_LEAF_KINDS  # noqa: E402
from dynamosa import (_seed_shared_population, is_active, _branch_key,  # noqa: E402
                       _mutations_per_child, _local_burst_size, _focal_for_mutate, evaluate_objective)


def _random_value_for(record, genome, var_name, node, case_study, rng):
    """The random-baseline analogue of `best_value_for`: draws the exact
    same candidate menu, but returns one picked uniformly at random
    instead of the hypothetical-fitness-best one -- no fitness evaluation
    at all happens here, by design (a real random search doesn't have an
    oracle telling it which candidate is closest to correct)."""
    current = genome.get(var_name)
    if node.get('kind') in BOOLEAN_LEAF_KINDS:
        return rng.choice([True, False])
    options = candidate_values(record, var_name, node, current, case_study)
    if not options:
        return None
    return rng.choice(options)


def _random_mutate_lineage(record, candidate, focal_maps, scenario_maps, table_cache, rng):
    """One undirected mutation attempt against a single objective, applied
    to one lineage -- mirrors `dynamosa._mutate_objective`'s own control
    flow (pick a random leaf, deep-copy the whole individual jointly,
    apply via M1/M2, repair by construction) with its value-selection step
    swapped for `_random_value_for` and its accept/reject step removed
    entirely (a randomly drawn value is always applied, never checked
    against the current one first)."""
    rid = record['record_id']
    scenario = scenario_maps.get(rid, {})
    focal = _focal_for_mutate(record, candidate, focal_maps, table_cache)
    try:
        genome = derive_genome(record, candidate, focal, scenario, owner_id=rid)
        leaves = [(v, n) for v, n in _leaf_variables(record) if v in genome]
        if not leaves:
            return candidate, focal_maps, scenario_maps
        var_name, node = rng.choice(leaves)
        value = _random_value_for(record, genome, var_name, node, record['case_study'], rng)
        if value is None:
            return candidate, focal_maps, scenario_maps
    except FitnessEvaluationError:
        return candidate, focal_maps, scenario_maps

    new_candidate, new_focal_maps, new_scenario_maps = copy.deepcopy((candidate, focal_maps, scenario_maps))
    new_focal = new_focal_maps[rid]
    new_scenario = new_scenario_maps.setdefault(rid, {})
    try:
        apply_mutation(record, new_candidate, new_focal, new_scenario, var_name, node, value,
                        genome.get(var_name), owner_id=rid)
    except FitnessEvaluationError:
        return candidate, focal_maps, scenario_maps
    return new_candidate, new_focal_maps, new_scenario_maps


def run_random_search(records, case_study, population_size=20, generations=50, rng=None,
                       mutations_per_child='auto', dynamic_gating=True):
    """Undirected random-search baseline over the SAME representation,
    fitness function, repair discipline, and (by default) dependency
    gating as `run_dynamosa` -- see this module's own docstring for
    exactly what is and isn't different. Returns (archive,
    coverage_history, population), the identical shape `run_dynamosa`
    returns, so a caller can compare the two directly."""
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

        new_population = []
        for lineage in population:
            cand, fm, sm = lineage
            if active:
                for r in rng.sample(active, min(k, len(active))):
                    for _ in range(_local_burst_size(r)):
                        cand, fm, sm = _random_mutate_lineage(r, cand, fm, sm, table_cache, rng)
            new_population.append((cand, fm, sm))
        population = new_population

        for ind in population:
            update_archive(ind)

        covered_count = sum(1 for r in records
                             if archive.get(r['record_id'], (float('inf'), None))[0] == 0.0)
        coverage_history.append(covered_count)

    return archive, coverage_history, population


if __name__ == '__main__':
    import json
    import time

    compiled = json.load(open(os.path.join(HERE, 'compiled_constraints.json')))

    for cs in ('FLEX2', 'OpenMRS', 'Spree', 'jBilling'):
        records = [r for r in compiled if r['case_study'] == cs]
        start = time.time()
        archive, coverage_history, _population = run_random_search(
            records, cs, population_size=30, generations=40, rng=random.Random(0))
        elapsed = time.time() - start
        covered = sum(1 for r in records if archive[r['record_id']][0] == 0.0)
        print(f"{cs}: {covered}/{len(records)} ({covered / len(records) * 100:.1f}%) "
              f"random-search archive coverage, {elapsed:.1f}s")
        print(f"  coverage history: {coverage_history}")
