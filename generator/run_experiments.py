"""Experiment runner: executes true DynaMOSA (dynamosa_preference.py),
NSGA2-style dynamic-gated DynaMOSA (dynamosa.py), and random search
(random_baseline.py) at 1x/2x/5x generation budget, across all 4 case
studies, and persists every run's RAW archive + final population +
generation-level coverage history to disk.

Deliberately touches nothing else -- dynamosa.py, dynamosa_preference.py,
random_baseline.py, fitness.py, compile_constraints.py are all called
exactly as they already exist, unmodified. This script only calls and
persists, so that a later change to how "coverage" is defined or
verified never requires re-running the search itself: the archive and
final population are the raw material a different coverage mechanism
would need, saved once, here.

Population size (30) and base generation count (40) match this
project's own prior ablation convention (see the mutation-budget-
scaling ablation run earlier this session). SEEDS is deliberately a
single seed for now -- matching that same prior convention -- not the
~30-seeds-per-cell a full statistical study would want; expanding this
tuple is the only change needed to add more repetitions later.
"""
import json
import os
import pickle
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from dynamosa import run_dynamosa  # noqa: E402
from dynamosa_preference import run_dynamosa_preference  # noqa: E402
from random_baseline import run_random_search  # noqa: E402

OUT_DIR = os.path.join(HERE, 'experiment_runs')
os.makedirs(OUT_DIR, exist_ok=True)

CASE_STUDIES = ('FLEX2', 'OpenMRS', 'Spree', 'jBilling')
POPULATION_SIZE = 30
BASE_GENERATIONS = 40
SEEDS = (0,)


def _save_run(meta, archive, population, coverage_history):
    tag = (f"{meta['case_study']}__{meta['algorithm']}"
           f"__budget{meta['budget_multiplier']}x__seed{meta['seed']}")

    # Raw, unmodified outputs -- the actual Candidate/focal_maps/
    # scenario_maps individuals, not a coverage summary of them -- so
    # ANY later coverage mechanism can be re-run against this exact
    # search output without re-searching.
    pkl_path = os.path.join(OUT_DIR, tag + '.pkl')
    with open(pkl_path, 'wb') as f:
        pickle.dump({'archive': archive, 'final_population': population}, f)

    json_meta = dict(meta)
    json_meta['coverage_history'] = coverage_history
    json_meta['raw_output_file'] = os.path.basename(pkl_path)
    json_path = os.path.join(OUT_DIR, tag + '.json')
    with open(json_path, 'w') as f:
        json.dump(json_meta, f, indent=2)
    return json_meta


def _run_one(fn, records, cs, algorithm, budget_multiplier, seed, generations, **kwargs):
    t0 = time.time()
    archive, hist, population = fn(
        records, cs, population_size=POPULATION_SIZE, generations=generations,
        rng=random.Random(seed), **kwargs)
    runtime = time.time() - t0
    total = len(records)
    covered = sum(1 for r in records if archive[r['record_id']][0] == 0.0)
    meta = {
        'case_study': cs, 'algorithm': algorithm, 'budget_multiplier': budget_multiplier,
        'seed': seed, 'population_size': POPULATION_SIZE, 'generations': generations,
        'total_objectives': total, 'final_covered': covered, 'runtime_seconds': runtime,
    }
    saved = _save_run(meta, archive, population, hist)
    print(f"{cs:10s} {algorithm:20s} budget={budget_multiplier}x seed={seed}: "
          f"{covered}/{total} covered  ({runtime:.1f}s)", flush=True)
    return saved


def main():
    compiled = json.load(open(os.path.join(HERE, 'compiled_constraints.json')))
    index = []

    for cs in CASE_STUDIES:
        records = [r for r in compiled if r['case_study'] == cs]

        for seed in SEEDS:
            index.append(_run_one(run_dynamosa_preference, records, cs,
                                   'dynamosa_preference', 1, seed, BASE_GENERATIONS))
            index.append(_run_one(run_dynamosa, records, cs,
                                   'dynamosa_nsga2', 1, seed, BASE_GENERATIONS))
            for mult in (1, 2, 5):
                index.append(_run_one(run_random_search, records, cs,
                                       'random', mult, seed, BASE_GENERATIONS * mult))

    with open(os.path.join(OUT_DIR, 'runs_index.json'), 'w') as f:
        json.dump(index, f, indent=2)
    print(f"\n{len(index)} runs saved to {OUT_DIR}")


if __name__ == '__main__':
    main()
