"""Re-runs run_dynamosa (dynamosa_nsga2, budget 1x, seed 0) for FLEX2
ONLY, against the CURRENT compiled_constraints.json -- same population/
generations/seed convention as rerun_dynamosa_nsga2_all.py, just scoped to
one case study so the other 3 archives aren't touched. Overwrites
generator/experiment_runs/FLEX2__dynamosa_nsga2__budget1x__seed0.pkl/.json
only."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from dynamosa import run_dynamosa  # noqa: E402
from run_experiments import _run_one, POPULATION_SIZE, BASE_GENERATIONS  # noqa: E402

if __name__ == '__main__':
    compiled = json.load(open(os.path.join(HERE, 'compiled_constraints.json')))
    records = [r for r in compiled if r['case_study'] == 'FLEX2']
    print(f"population_size={POPULATION_SIZE}, generations={BASE_GENERATIONS}, seed=0\n")
    _run_one(run_dynamosa, records, 'FLEX2', 'dynamosa_nsga2', budget_multiplier=1, seed=0,
              generations=BASE_GENERATIONS)
