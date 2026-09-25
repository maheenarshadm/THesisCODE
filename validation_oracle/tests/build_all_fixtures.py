"""Rebuilds ALL 4 case studies' committed test fixtures
(validation_oracle/tests/fixtures/<cs>_merged.db) from their CURRENT
experiment_runs/*.pkl archives -- generalizes build_fixture_from_
generator.py's own single-case-study __main__ block (OpenMRS only) to
all four, for the "full pipeline" the user asked for 2026-09-25
(re-run search -> rebuild fixtures -> re-verify -> summarize).

WARNING: overwrites the COMMITTED tests/fixtures/*.db files this
project's own coverage numbers have always been recorded against. They
are git-tracked -- `git diff --stat validation_oracle/tests/fixtures/`
shows exactly what changed, `git checkout -- validation_oracle/tests/
fixtures/` recovers the previous committed state. Every currently-
verified rule's own status can shift after this -- expected, the whole
point of rebuilding after the corpus changed -- but it must be
independently re-verified (coverage.py) and diffed against the
previously-recorded numbers before trusting it, never assumed from the
search's own claims alone.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
GENERATOR_DIR = os.path.join(HERE, '..', '..', 'generator')
sys.path.insert(0, GENERATOR_DIR)

from build_fixture_from_generator import build  # noqa: E402

CASE_STUDIES = ('OpenMRS', 'Spree', 'FLEX2', 'jBilling')
FIXTURE_NAME = {
    'OpenMRS': 'openmrs_merged.db',
    'Spree': 'spree_merged.db',
    'FLEX2': 'flex2_merged.db',
    'jBilling': 'jbilling_merged.db',
}

if __name__ == '__main__':
    for cs in CASE_STUDIES:
        pickle_path = os.path.join(
            GENERATOR_DIR, 'experiment_runs', f'{cs}__dynamosa_nsga2__budget1x__seed0.pkl')
        out_db = os.path.join(HERE, 'fixtures', FIXTURE_NAME[cs])
        build(cs, pickle_path, out_db)
