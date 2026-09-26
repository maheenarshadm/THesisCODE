"""random_sampling.py -- a PURE random-sampling baseline (2026-09-26, built
for experiment_harness/), deliberately kept alongside, never replacing,
random_baseline.py's random WALK:

  - random_baseline.run_random_search: population_size lineages, each
    mutated at random every generation (no fitness guidance, no
    crossover, no selection) -- a random WALK from the seed.
  - run_random_sampling (this module): every attempt is a brand-new,
    independent individual; nothing carries over from one attempt to the
    next except the archive. No mutation, no crossover, no selection.

Each attempt, and only this, is what "random" means here:
  1. Start from a fresh deep copy of the SAME shared seed individual
     `run_dynamosa` starts every generation-0 individual from
     (`_seed_shared_population`) -- so the representation, the per-
     objective focal rows, the key offsets and the repair discipline are
     byte-for-byte what the search itself starts from; only the search
     STRATEGY differs.
  2. Give EVERY leaf variable of EVERY record an independent random value
     (`_sample_value_for`), applied through the same `apply_mutation`
     move the search uses (so aggregate counts become real rows, and
     each move repairs its own rows by construction, as in the search).
  3. Score it against every record with the unchanged fitness function
     and keep, per record, the best individual ever seen (the same
     strict-improvement archive rule run_dynamosa uses).

The seed individual itself is scored once first, exactly as every
algorithm scores its own generation 0 -- any record the constructive seed
already satisfies is credited to every algorithm alike.

Value distribution (`_sample_value_for`): the same move menu the search
itself draws from (`mutation.candidate_values`), with a random step of
1..40 around the seeded value -- i.e. `dynamosa._kick_value_for`'s own
random-jump distribution, widened to include +-1 -- picked uniformly.
Enumerable domains and booleans are sampled uniformly over the whole
menu. `known_constants.json` pinning is NOT applied, for the same reason
random_baseline.py gives: that is domain knowledge a random process has
no access to.

Budget: fitness evaluations only (`max_evaluations`, see fitness.py's
`reset_evaluation_counter`). Building a sample costs no evaluations --
exactly like random_baseline's own mutations -- only scoring does.

Usage:
    archive, trace_history, population = run_random_sampling(
        records, case_study, max_evaluations=500_000, rng=random.Random(0))
`population` is always [] -- a sampler has no final population.
"""
import copy
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from candidate import derive_genome  # noqa: E402
from fitness import (FitnessEvaluationError, EvaluationBudgetExhausted,  # noqa: E402
                     reset_evaluation_counter, clear_evaluation_limit,
                     evaluations_used)
from mutation import (_leaf_variables, candidate_values, apply_mutation,  # noqa: E402
                      BOOLEAN_LEAF_KINDS)
from dynamosa import _seed_shared_population, _focal_for_mutate, evaluate_objective  # noqa: E402

_MAX_STEP = 40  # dynamosa._kick_value_for's own upper step


def _sample_value_for(record, var_name, node, current, case_study, rng):
    if node.get('kind') in BOOLEAN_LEAF_KINDS:
        return rng.choice([True, False])
    options = candidate_values(record, var_name, node, current, case_study,
                               step=rng.randint(1, _MAX_STEP))
    return rng.choice(options) if options else None


def _random_individual(base, records, case_study, table_cache, rng):
    candidate, focal_maps, scenario_maps = copy.deepcopy(base)
    order = list(records)
    rng.shuffle(order)
    for r in order:
        rid = r['record_id']
        scenario = scenario_maps.setdefault(rid, {})
        focal = _focal_for_mutate(r, candidate, focal_maps, table_cache)
        try:
            genome = derive_genome(r, candidate, focal, scenario, owner_id=rid)
        except FitnessEvaluationError:
            continue
        for var_name, node in _leaf_variables(r):
            if var_name not in genome:
                continue
            value = _sample_value_for(r, var_name, node, genome.get(var_name), case_study, rng)
            if value is None:
                continue
            try:
                apply_mutation(r, candidate, focal_maps[rid], scenario, var_name, node, value,
                               genome.get(var_name), owner_id=rid)
            except FitnessEvaluationError:
                continue
    return candidate, focal_maps, scenario_maps


def run_random_sampling(records, case_study, max_evaluations, rng=None, trace=None, max_samples=None):
    """Returns (archive, samples_history, []) -- `archive` in the same
    {record_id: (best_fitness, individual)} shape run_dynamosa returns;
    `samples_history[i]` is how many records were covered after sample i
    (the seed counts as sample 0). Stops when the evaluation budget is
    used up, every record is covered, or `max_samples` (tests only)."""
    rng = rng or random.Random(0)
    table_cache = {}
    base = _seed_shared_population(records, case_study, 1)[0]
    archive = {r['record_id']: (float('inf'), base) for r in records}
    history = []

    def update_archive(individual):
        candidate, focal_maps, scenario_maps = individual
        for r in records:
            rid = r['record_id']
            f = evaluate_objective(r, candidate, focal_maps, scenario_maps, table_cache)
            if f < archive[rid][0]:
                if f == 0.0 and trace is not None:
                    trace.append((evaluations_used(), rid))
                archive[rid] = (f, individual)

    def covered():
        return sum(1 for r in records if archive[r['record_id']][0] == 0.0)

    reset_evaluation_counter(max_evaluations)
    try:
        update_archive(base)
        history.append(covered())
        while (max_samples is None or len(history) <= max_samples) and history[-1] < len(records):
            update_archive(_random_individual(base, records, case_study, table_cache, rng))
            history.append(covered())
    except EvaluationBudgetExhausted:
        pass
    finally:
        clear_evaluation_limit()
    return archive, history, []


if __name__ == '__main__':
    import json
    import time

    compiled = json.load(open(os.path.join(HERE, 'compiled_constraints.json')))
    for cs in ('Spree', 'jBilling'):
        records = [r for r in compiled if r['case_study'] == cs]
        t0 = time.time()
        archive, hist, _ = run_random_sampling(records, cs, max_evaluations=20 * len(records),
                                               rng=random.Random(0))
        n = sum(1 for r in records if archive[r['record_id']][0] == 0.0)
        print(f"{cs}: {n}/{len(records)} covered after {len(hist) - 1} samples "
              f"({time.time() - t0:.1f}s); history {hist}")
