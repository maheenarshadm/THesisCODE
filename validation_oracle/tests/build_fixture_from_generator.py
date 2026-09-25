"""FIXTURE-BUILDING TOOL ONLY -- not part of the validation oracle itself.

Produces a real, on-disk SQLite database file from one of the already-
saved experiment_runs/ pickles, for the oracle's own modules to be
tested against. This script is the one place allowed to import
generator/ code (materialize.py's DDL/INSERT construction) -- it plays
the role of "however a real database got produced," which the oracle
treats as a given, external input (see DESIGN.md: "Assume I have a
database as an output"). No module under validation_oracle/ (dmn_walk.py,
subject_table.py, db_resolver.py, rule_evaluator.py, drd_executor.py,
coverage.py) imports this file or anything it imports.
"""
import os
import pickle
import sqlite3
import sys

GENERATOR_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'generator')
sys.path.insert(0, GENERATOR_DIR)

from dynamosa import merge_archive_candidate  # noqa: E402
from materialize import to_sql_inserts, topological_table_order, create_table_ddl  # noqa: E402
from mutation import _schema_for  # noqa: E402
import json  # noqa: E402


def build(case_study, pickle_path, out_db_path):
    with open(pickle_path, 'rb') as f:
        raw = pickle.load(f)
    archive = raw['archive']

    compiled = json.load(open(os.path.join(GENERATOR_DIR, 'compiled_constraints.json')))
    records = [r for r in compiled if r['case_study'] == case_study]

    merged_candidate, _fm, _sm, _expected = merge_archive_candidate(archive, records, case_study)
    schema = _schema_for(case_study)

    if os.path.exists(out_db_path):
        os.remove(out_db_path)
    conn = sqlite3.connect(out_db_path)
    cur = conn.cursor()
    order, _warnings = topological_table_order(schema, merged_candidate.as_dict().keys())
    created = set()
    for table in order:
        ddl = create_table_ddl(table, schema, set(order))
        if ddl is None:
            continue
        cur.execute(ddl)
        created.add(table)

    sql_statements, _warnings = to_sql_inserts(merged_candidate, schema)
    for stmt in sql_statements:
        cur.execute(stmt)
    conn.commit()
    conn.close()
    print(f"Built {out_db_path} -- {len(created)} tables, {len(sql_statements)} rows, "
          f"from {case_study}'s merged-archive candidate ({pickle_path})")


if __name__ == '__main__':
    build(
        case_study='OpenMRS',
        pickle_path=os.path.join(
            GENERATOR_DIR, 'experiment_runs', 'OpenMRS__dynamosa_nsga2__budget1x__seed0.pkl'),
        out_db_path=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  'fixtures', 'openmrs_merged.db'))
