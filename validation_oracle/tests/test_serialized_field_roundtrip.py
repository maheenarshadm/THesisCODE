"""Locks in the `serialized_field` resolution kind end to end: a mutation
writes into an in-memory nested dict, `materialize.py` turns it into real
YAML column text, and `db_resolver.py` (validation_oracle's own,
independent read-side implementation of the SAME agreed convention --
this project's architectural separation rule: validation_oracle never
imports generator code AT RUNTIME) reads it back out of a real SQLite
database. See DESIGN.md's own writeup for the full design and Spree's
real-source confirmation (`serialize :preferences, type: Hash, coder:
YAML`) this convention is built on.

This is the SECOND file (after `build_fixture_from_generator.py`)
explicitly allowed to import generator/ code -- needed here only to
exercise the WRITE side for the test's own setup; `db_resolver.resolve`
itself, the thing actually being verified, never does.

Run: python3 test_serialized_field_roundtrip.py
"""
import os
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..'))
GENERATOR_DIR = os.path.join(HERE, '..', '..', 'generator')
sys.path.insert(0, GENERATOR_DIR)

from candidate import Candidate  # noqa: E402
from mutation import apply_mutation, _schema_for  # noqa: E402
from materialize import to_sql_inserts, create_table_ddl, topological_table_order  # noqa: E402

from db_resolver import resolve  # noqa: E402


def test_write_then_read_real_value():
    node = {'kind': 'serialized_field', 'table': 'spree_promotion_rules', 'column': 'preferences',
            'key': 'amount_min', 'default': 100.0}
    record = {'case_study': 'Spree'}
    candidate = Candidate()
    focal = {}
    apply_mutation(record, candidate, focal, {}, 'amountMin', node, 250.0, None)

    schema = _schema_for('Spree')
    order, _w = topological_table_order(schema, candidate.as_dict().keys())
    conn = sqlite3.connect(':memory:')
    for table in order:
        ddl = create_table_ddl(table, schema, set(order))
        if ddl:
            conn.execute(ddl)
    sql_statements, _w = to_sql_inserts(candidate, schema)
    for stmt in sql_statements:
        conn.execute(stmt)
    conn.commit()

    row_id = conn.execute('SELECT id FROM spree_promotion_rules LIMIT 1').fetchone()[0]
    result = resolve(conn, node, 'spree_promotion_rules', ['id'], (row_id,))
    assert result.value == 250.0, \
        f"the value a mutation wrote (250.0) must survive real YAML round-trip: got {result.value!r}"
    assert result.resolution_type == 'serialized_field'
    print("test_write_then_read_real_value: PASS")
    print(f"  wrote amountMin=250.0 via a real mutation, materialized to real SQL, "
          f"read back independently by db_resolver as {result.value!r}")


def test_default_fallback_for_unset_key():
    conn = sqlite3.connect(':memory:')
    conn.execute('CREATE TABLE spree_promotion_rules (id INTEGER PRIMARY KEY, preferences TEXT)')
    # A real row whose blob sets a DIFFERENT key, never this one -- same
    # shape as an admin who only configured operator_min, leaving
    # amount_min at its declared default.
    conn.execute("INSERT INTO spree_promotion_rules (preferences) VALUES (':operator_min: gte')")
    conn.commit()
    node = {'kind': 'serialized_field', 'table': 'spree_promotion_rules', 'column': 'preferences',
            'key': 'amount_min', 'default': 100.0}
    result = resolve(conn, node, 'spree_promotion_rules', ['id'], (1,))
    assert result.value == 100.0, f"an unset key must fall back to its declared default: got {result.value!r}"
    print("test_default_fallback_for_unset_key: PASS")


def test_default_fallback_for_null_blob():
    conn = sqlite3.connect(':memory:')
    conn.execute('CREATE TABLE spree_promotion_rules (id INTEGER PRIMARY KEY, preferences TEXT)')
    conn.execute('INSERT INTO spree_promotion_rules (id) VALUES (1)')  # preferences stays NULL
    conn.commit()
    node = {'kind': 'serialized_field', 'table': 'spree_promotion_rules', 'column': 'preferences',
            'key': 'amount_min', 'default': 100.0}
    result = resolve(conn, node, 'spree_promotion_rules', ['id'], (1,))
    assert result.value == 100.0, f"a row with no blob at all must fall back to its declared default: got {result.value!r}"
    print("test_default_fallback_for_null_blob: PASS")


if __name__ == '__main__':
    test_write_then_read_real_value()
    test_default_fallback_for_unset_key()
    test_default_fallback_for_null_blob()
