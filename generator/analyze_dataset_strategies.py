"""Applies generate_dataset.py's own two dataset-construction strategies
(final-population's best single individual, and the merged archive) to
the RAW archive + final_population already saved by run_experiments.py
-- no re-running the search. Reuses generate_dataset.py's own
`_covered_set` and dynamosa.py's own `merge_archive_candidate`
unmodified, so these numbers are computed the exact same way
generate_dataset.py already computes them for real dataset construction,
not a separate one-off metric.

For every already-saved run, reports THREE coverage numbers side by
side: archive (the loosest -- any individual, any generation, ever),
final-population (one real, self-consistent candidate: the single best
individual in the last generation), and merged-archive (one real,
self-consistent candidate: every objective's own best-ever archived row
merged together, then re-verified after repair -- can regress, see
`merged_archive_regressions`).
"""
import json
import os
import pickle
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from dynamosa import merge_archive_candidate  # noqa: E402
from generate_dataset import _covered_set  # noqa: E402

RUNS_DIR = os.path.join(HERE, 'experiment_runs')


def analyze(meta_path):
    meta = json.load(open(meta_path))
    with open(os.path.join(RUNS_DIR, meta['raw_output_file']), 'rb') as f:
        raw = pickle.load(f)
    archive, population = raw['archive'], raw['final_population']

    compiled = json.load(open(os.path.join(HERE, 'compiled_constraints.json')))
    records = [r for r in compiled if r['case_study'] == meta['case_study']]
    table_cache = {}

    archive_covered = sum(1 for r in records if archive[r['record_id']][0] == 0.0)

    pop_sets = [_covered_set(ind, records, table_cache) for ind in population]
    best_pop_idx = max(range(len(population)), key=lambda i: len(pop_sets[i]))
    final_population_covered = pop_sets[best_pop_idx]

    merged_candidate, merged_focal_maps, merged_scenario_maps, merged_expected = merge_archive_candidate(
        archive, records, meta['case_study'])
    merged_covered = _covered_set(
        (merged_candidate, merged_focal_maps, merged_scenario_maps), records, table_cache)
    merged_regressions = merged_expected - merged_covered

    return {
        **meta,
        'archive_covered_check': archive_covered,
        'final_population_covered': len(final_population_covered),
        'merged_archive_expected': len(merged_expected),
        'merged_archive_covered': len(merged_covered),
        'merged_archive_regressions': sorted(merged_regressions),
    }


def main():
    results = []
    for fname in sorted(os.listdir(RUNS_DIR)):
        if fname.endswith('.json') and fname != 'runs_index.json':
            results.append(analyze(os.path.join(RUNS_DIR, fname)))

    header = (f"{'case':10s} {'algorithm':20s} {'budget':7s} {'total':>5s} "
              f"{'archive':>8s} {'finalpop':>9s} {'merged':>7s} {'regress':>8s}")
    print(header)
    for r in results:
        print(f"{r['case_study']:10s} {r['algorithm']:20s} {str(r['budget_multiplier'])+'x':7s} "
              f"{r['total_objectives']:>5d} {r['archive_covered_check']:>8d} "
              f"{r['final_population_covered']:>9d} {r['merged_archive_covered']:>7d} "
              f"{len(r['merged_archive_regressions']):>8d}")

    with open(os.path.join(RUNS_DIR, 'dataset_strategy_analysis.json'), 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nFull breakdown (incl. regression record_ids) saved to "
          f"{os.path.join(RUNS_DIR, 'dataset_strategy_analysis.json')}")


if __name__ == '__main__':
    main()
