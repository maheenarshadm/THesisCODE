"""Synthetic (no generator/ involvement, no real case-study data) tests
for drd_executor.py's DecisionRunner -- literal_via_upstream_branch
chaining and substituted_decision expression evaluation. Uses small,
hand-built compiled-record dicts (the SAME shape compiled_constraints.json
produces) and an in-memory SQLite database, so these mechanisms are
verified independent of any real case study's own schema quirks (FLEX2's
real decisions needing this chaining also need a composite-key subject
grain this validator doesn't yet support -- see DESIGN.md's "known
gaps" -- these synthetic tests isolate the chaining mechanism itself
from that separate, harder problem).

Run: python3 test_drd_chaining_synthetic.py
"""
import os
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..'))

from drd_executor import DecisionRunner, run_decision  # noqa: E402
import schema_utility  # noqa: E402

# Register a small, real (on-disk, same JSON shape as all_schema_extraction's
# own output) synthetic schema for case_study 'T' -- exercises the REAL
# schema_utility.py join-path code, not a mocked-out version of it.
schema_utility.SCHEMA_JSON_PATHS['T'] = os.path.join(HERE, 'fixtures', 'synthetic_T_schema.json')


def _rec(case_study, decision_name, rule_id, hit_policy, condition, variable_resolution):
    return {
        'case_study': case_study, 'decision_name': decision_name, 'rule_id': rule_id,
        'record_id': f'{case_study}::{decision_name}::{rule_id}',
        'hit_policy': hit_policy, 'condition': condition,
        'variable_resolution': variable_resolution, 'fk_closure_tables': ['student', 'course_load'],
    }


def build_db():
    conn = sqlite3.connect(':memory:')
    conn.execute('CREATE TABLE student (student_id INTEGER PRIMARY KEY, gpa REAL)')
    conn.execute('CREATE TABLE course_load (course_load_id INTEGER PRIMARY KEY, student_id INTEGER, units INTEGER)')
    conn.executemany('INSERT INTO student VALUES (?, ?)', [
        (1, 3.8),   # D1 selects Rule_1 (honors) for this student
        (2, 2.9),   # D1 selects Rule_2 (normal) for this student
    ])
    conn.executemany('INSERT INTO course_load VALUES (?, ?, ?)', [
        (10, 1, 21),   # belongs to the honors student -> literal_via_upstream_branch APPLIES
        (11, 2, 21),   # belongs to the normal student -> literal_via_upstream_branch does NOT apply
    ])
    conn.commit()
    return conn


def build_records():
    d1_rule1 = _rec('T', 'D1', 'D1_Rule_1', 'FIRST',
                     {'op': '>=', 'left': {'kind': 'variable', 'ref': 'gpa'},
                      'right': {'kind': 'literal', 'value': 3.5, 'type': 'number'}},
                     {'gpa': {'kind': 'schema_column', 'table': 'student', 'column': 'gpa'}})
    d1_rule2 = _rec('T', 'D1', 'D1_Rule_2', 'FIRST',
                     {'op': '<', 'left': {'kind': 'variable', 'ref': 'gpa'},
                      'right': {'kind': 'literal', 'value': 3.5, 'type': 'number'}},
                     {'gpa': {'kind': 'schema_column', 'table': 'student', 'column': 'gpa'}})

    d2_rule1 = _rec('T', 'D2', 'D2_Rule_1', 'FIRST',
                     {'op': '>=', 'left': {'kind': 'variable', 'ref': 'bonusUnits'},
                      'right': {'kind': 'literal', 'value': 5, 'type': 'number'}},
                     {'bonusUnits': {'kind': 'literal_via_upstream_branch',
                                     'value': {'kind': 'literal', 'value': 5, 'type': 'number'},
                                     'from_decision': 'D1', 'from_rule_id': 'D1_Rule_1'}})

    d3_rule1 = _rec('T', 'D3', 'D3_Rule_1', 'FIRST',
                     {'op': '>=', 'left': {'kind': 'variable', 'ref': 'totalUnits'},
                      'right': {'kind': 'literal', 'value': 21, 'type': 'number'}},
                     {'totalUnits': {
                         'kind': 'substituted_decision', 'substituted_from': 'UnitTotal',
                         'expression': {'op': '+',
                                        'left': {'kind': 'variable', 'ref': 'units'},
                                        'right': {'kind': 'literal', 'value': 0, 'type': 'number'}},
                         'free_variable_resolutions': {
                             'units': {'kind': 'schema_column', 'table': 'course_load', 'column': 'units'}}}})

    return {
        'D1': [d1_rule1, d1_rule2],
        'D2': [d2_rule1],
        'D3': [d3_rule1],
    }


def test_literal_via_upstream_branch():
    conn = build_db()
    records_by_decision = build_records()
    subject_tables = {
        'D1': ('student', {}),
        'D2': ('course_load', {}),
    }
    runner = DecisionRunner(conn, 'T', records_by_decision, subject_tables)

    result = run_decision(conn, 'D2', records_by_decision['D2'], 'course_load', 'course_load_id',
                           join_paths={}, runner=runner)

    # course_load_id=10 belongs to student_id=1, who D1 selects Rule_1 for
    # -- bonusUnits=5 applies, 5 >= 5 is true -> D2_Rule_1 selected.
    assert result['selected_by_case'][10] == 'D2_Rule_1', result['selected_by_case']
    # course_load_id=11 belongs to student_id=2, who D1 selects Rule_2 for
    # -- literal_via_upstream_branch's own precondition FAILS -> ungrounded, not selected.
    assert result['selected_by_case'][11] is None, result['selected_by_case']
    print("test_literal_via_upstream_branch: PASS")
    print(f"  selected_by_case = {result['selected_by_case']}")


def test_substituted_decision_expression():
    conn = build_db()
    records_by_decision = build_records()
    result = run_decision(conn, 'D3', records_by_decision['D3'], 'course_load', 'course_load_id', join_paths={})

    # Both course_load rows have units=21 -> totalUnits = 21 + 0 = 21 -> >= 21 true.
    assert result['selected_by_case'][10] == 'D3_Rule_1', result['selected_by_case']
    assert result['selected_by_case'][11] == 'D3_Rule_1', result['selected_by_case']
    print("test_substituted_decision_expression: PASS")
    print(f"  selected_by_case = {result['selected_by_case']}")


if __name__ == '__main__':
    test_literal_via_upstream_branch()
    test_substituted_decision_expression()
