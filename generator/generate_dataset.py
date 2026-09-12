"""generate_dataset.py -- ties `dynamosa.py` (the search) and
`materialize.py` (the output) together into the actual "generate a real
dataset for one case study" entry point. Everything up to this point
(fitness/candidate/mutation/crossover/AVM/escalation/materialize/
DynaMOSA) was built and tested piece by piece; this is the first module
that runs the whole thing end to end and produces real files.

**Two honest coverage numbers, not one, because they answer different
questions**:

- **Archive coverage** -- how many objectives reached fitness 0.0 *at
  some point* during the run, possibly on different individuals at
  different generations. This is the search's own progress metric
  (DynaMOSA's own archive discipline), and the number `dynamosa.py`'s
  own self-test already reports.
- **Final-dataset coverage** -- how many objectives are *simultaneously*
  satisfied by the ONE real candidate this module actually materializes.
  This is the honest, deliverable number: a dataset is one concrete
  set of rows, not a scrapbook of per-objective snapshots taken at
  different moments. `dynamosa.py`'s own "first row per table" scope
  decision (see its module docstring) means these two numbers can
  genuinely differ -- confirmed, not assumed, by computing both and
  reporting them side by side.

The final candidate materialized is the individual in the LAST
generation's own population that simultaneously satisfies the most
objectives -- a real, self-consistent, already-evolved candidate, not an
ad hoc merge of different objectives' own best (and mutually
inconsistent) archived snapshots.

Usage:
    from generate_dataset import generate_case_study_dataset
    result = generate_case_study_dataset('FLEX2', out_dir='./generated_flex2')
"""
import json
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from dynamosa import run_dynamosa, evaluate_objective  # noqa: E402
from materialize import to_sql_inserts, write_csv_files, validate_with_sqlite  # noqa: E402
from mutation import _schema_for  # noqa: E402
from candidate import build_seed_candidate  # noqa: E402


def _covered_count(candidate, records, scenario_cache, table_cache):
    return sum(1 for r in records
               if evaluate_objective(r, candidate, scenario_cache[r['record_id']], table_cache) == 0.0)


def generate_case_study_dataset(case_study, records=None, out_dir=None,
                                 population_size=30, generations=40, rng=None):
    """Runs DynaMOSA over `records` (default: every compiled record for
    `case_study`), picks the final population's own best individual, and
    materializes + validates it for real. Returns a dict: {'archive',
    'coverage_history', 'archive_covered', 'final_covered', 'candidate',
    'sql_statements', 'sql_warnings', 'csv_files', 'validate_ok',
    'validate_errors', 'elapsed_seconds'} -- every number in it is
    computed, never assumed."""
    rng = rng or random.Random(0)
    if records is None:
        compiled = json.load(open(os.path.join(HERE, 'compiled_constraints.json')))
        records = [r for r in compiled if r['case_study'] == case_study]

    start = time.time()
    archive, coverage_history, population = run_dynamosa(
        records, case_study, population_size=population_size, generations=generations, rng=rng)
    elapsed = time.time() - start

    scenario_cache = {r['record_id']: build_seed_candidate(r)[2] for r in records}
    table_cache = {}

    archive_covered = sum(1 for r in records if archive[r['record_id']][0] == 0.0)
    final_candidate = max(population, key=lambda ind: _covered_count(ind, records, scenario_cache, table_cache))
    final_covered = _covered_count(final_candidate, records, scenario_cache, table_cache)

    schema = _schema_for(case_study)
    sql_statements, sql_warnings = to_sql_inserts(final_candidate, schema)
    validate_ok, validate_errors = validate_with_sqlite(final_candidate, schema)
    csv_files = write_csv_files(final_candidate, out_dir) if out_dir else []

    return {
        'archive': archive,
        'coverage_history': coverage_history,
        'archive_covered': archive_covered,
        'final_covered': final_covered,
        'total_objectives': len(records),
        'candidate': final_candidate,
        'sql_statements': sql_statements,
        'sql_warnings': sql_warnings,
        'csv_files': csv_files,
        'validate_ok': validate_ok,
        'validate_errors': validate_errors,
        'elapsed_seconds': elapsed,
    }


if __name__ == '__main__':
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument('--case-study', default='FLEX2')
    ap.add_argument('--population-size', type=int, default=30)
    ap.add_argument('--generations', type=int, default=40)
    ap.add_argument('--out-dir', default=os.path.join(HERE, '_generated_flex2'))
    ap.add_argument('--seed', type=int, default=0)
    args = ap.parse_args()

    result = generate_case_study_dataset(
        args.case_study, out_dir=args.out_dir,
        population_size=args.population_size, generations=args.generations,
        rng=random.Random(args.seed))

    print(f"Case study: {args.case_study}  ({result['total_objectives']} compiled branches, "
          f"population={args.population_size}, generations={args.generations})")
    print(f"Elapsed: {result['elapsed_seconds']:.1f}s")
    print(f"Coverage history (archive, per generation): {result['coverage_history']}")
    print()
    print(f"Archive coverage (ever covered, at some point, by SOME individual): "
          f"{result['archive_covered']}/{result['total_objectives']} "
          f"({result['archive_covered'] / result['total_objectives'] * 100:.1f}%)")
    print(f"Final-dataset coverage (this ONE materialized candidate, simultaneously): "
          f"{result['final_covered']}/{result['total_objectives']} "
          f"({result['final_covered'] / result['total_objectives'] * 100:.1f}%)")
    if result['archive_covered'] != result['final_covered']:
        print(f"  (These differ by {result['archive_covered'] - result['final_covered']} -- the real, "
              f"measured cost of dynamosa.py's own 'first row per table' scope decision: some objectives "
              f"covered at some point during the search were covered by a DIFFERENT individual than the "
              f"one this dataset actually is.)")
    print()
    print(f"Materialized {len(result['sql_statements'])} INSERT statements across "
          f"{len(result['candidate'].as_dict())} tables ({len(result['sql_warnings'])} ordering warnings).")
    print(f"Wrote {len(result['csv_files'])} CSV files to {args.out_dir}")
    print(f"validate_with_sqlite: ok={result['validate_ok']}, {len(result['validate_errors'])} error(s)")
    for e in result['validate_errors'][:10]:
        print("   ", e)

    sql_path = os.path.join(args.out_dir, f"{args.case_study}_generated.sql")
    os.makedirs(args.out_dir, exist_ok=True)
    with open(sql_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(result['sql_statements']) + '\n')
    print(f"Wrote {sql_path}")
