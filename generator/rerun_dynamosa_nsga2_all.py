"""Re-runs run_dynamosa (dynamosa_nsga2, budget 1x) for all 4 case
studies against the CURRENT compiled_constraints.json -- built
2026-09-25 because the corpus changed since the committed
experiment_runs/*.pkl archives were last produced (the Preferred
Identifier Requirement COUNT-mechanism fix, 4 new OpenMRS Concept Name
rules, the Spree Promotion Customer Group Eligibility::rule_4 out-of-
scope exclusion, the FLEX2/jBilling discard decisions).

Deliberately scoped to dynamosa_nsga2/budget1x/seed0 ONLY, not
run_experiments.py's own full matrix (which also runs
dynamosa_preference and random search at 3 budgets, for the project's
own search-vs-random research narrative) -- nothing this session's own
tools consume (coverage.py's --archive-pickle,
build_fixture_from_generator.py, validation_oracle/tests/
per_individual_archive_coverage.py) reads any algorithm/budget other
than this one, so re-running the rest here would just be extra time
spent on archives nothing currently needs refreshed.

Reuses run_experiments.py's own _run_one/_save_run (population 30,
generations 40, seed 0 -- this project's own established convention,
not a new one) so the saved pickle/json format is byte-identical in
shape to every existing archive -- every current consumer keeps working
against the result unchanged, no code elsewhere needs to change.

WARNING -- this OVERWRITES the committed
generator/experiment_runs/<CaseStudy>__dynamosa_nsga2__budget1x__seed0.pkl
(and matching .json) files for ALL 4 case studies. They are git-tracked,
so `git diff --stat generator/experiment_runs/` shows exactly what
changed afterward, and `git checkout -- generator/experiment_runs/`
recovers the previous committed state if anything looks wrong. Does NOT
rebuild any fixture database (tests/fixtures/*_merged.db) -- the search
archive and the materialized SQLite fixture are two separate artifacts,
and refreshing the fixture (build_fixture_from_generator.py) to actually
reflect these new archives, then re-verifying with coverage.py and
diffing against the currently-recorded numbers before trusting it, is
a deliberate, separate, later step -- not attempted here.

Expect this to take a few minutes total: OpenMRS's own 79-record corpus
took ~40s alone earlier this session; FLEX2 (151 total / 98 searchable
records, real DRD chaining) is likely the slowest of the four.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from dynamosa import run_dynamosa  # noqa: E402
from run_experiments import _run_one, POPULATION_SIZE, BASE_GENERATIONS  # noqa: E402

CASE_STUDIES = ('OpenMRS', 'Spree', 'FLEX2', 'jBilling')

if __name__ == '__main__':
    compiled = json.load(open(os.path.join(HERE, 'compiled_constraints.json')))
    print(f"population_size={POPULATION_SIZE}, generations={BASE_GENERATIONS}, seed=0\n")
    for cs in CASE_STUDIES:
        records = [r for r in compiled if r['case_study'] == cs]
        _run_one(run_dynamosa, records, cs, 'dynamosa_nsga2', budget_multiplier=1, seed=0,
                  generations=BASE_GENERATIONS)
