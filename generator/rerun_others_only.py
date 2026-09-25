"""Re-runs run_dynamosa (dynamosa_nsga2, budget 1x, seed 0) for Spree,
FLEX2, and jBilling -- same population/generations/seed convention as
rerun_dynamosa_nsga2_all.py, just scoped to these 3 so OpenMRS's own
archive (re-run separately via rerun_openmrs_only.py) isn't touched again.
Overwrites generator/experiment_runs/<CaseStudy>__dynamosa_nsga2__budget1x__seed0.pkl/.json
for these 3 case studies only."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from dynamosa import run_dynamosa  # noqa: E402
from run_experiments import _run_one, POPULATION_SIZE, BASE_GENERATIONS  # noqa: E402

CASE_STUDIES = ('Spree', 'FLEX2', 'jBilling')

if __name__ == '__main__':
    compiled = json.load(open(os.path.join(HERE, 'compiled_constraints.json')))
    print(f"population_size={POPULATION_SIZE}, generations={BASE_GENERATIONS}, seed=0\n")
    for cs in CASE_STUDIES:
        records = [r for r in compiled if r['case_study'] == cs]
        _run_one(run_dynamosa, records, cs, 'dynamosa_nsga2', budget_multiplier=1, seed=0,
                  generations=BASE_GENERATIONS)
