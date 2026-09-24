"""The 10 test cases from the original validation-oracle specification
(item L), covering the pieces `test_drd_chaining_synthetic.py` doesn't:

  1.  FIRST -- an earlier rule also matches -> earlier one selected, not
      the later target.
  2.  FIRST -- all earlier rules false -> target rule selected.
  3.  UNIQUE -- exactly one rule matches -> that rule selected.
  4.  UNIQUE -- two rules match -> UniqueViolation raised, not silently
      resolved.
  5.  Upstream dependency, correct outcome -- ALREADY COVERED, real data:
      `test_drd_chaining_synthetic.test_literal_via_upstream_branch`'s
      own grounded case (course_load_id=10) is exactly this.
  6.  Upstream dependency, incorrect outcome -- ALREADY COVERED, same
      test's own ungrounded case (course_load_id=11): the downstream
      rule is correctly NOT selected when the upstream decision produced
      a different result.
  7.  Aggregate input (derived_aggregate) drives real rule selection.
  8.  Join-based input (join_lookup) drives real rule selection.
  9.  Final-dataset merge changes data so search-covered != verified --
      ALREADY COVERED, real data: the whole OpenMRS acceptance test
      (`drd_executor.py`'s own `__main__`) IS this case --
      `Preferred Identifier Requirement::Rule_2` is exactly
      search_covered=True, verified_selected=False.
  10. Duplicate decision outputs -- two different rules share an output
      value; coverage is identified by rule ID, never by output.

No generator/ import, no real case-study data -- small, hand-built
compiled-record dicts (the same shape compiled_constraints.json
produces) and in-memory SQLite databases, same pattern as
test_drd_chaining_synthetic.py.

Run: python3 test_spec_cases.py
"""
import os
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..'))

from drd_executor import run_decision  # noqa: E402
from rule_evaluator import select_rule, UniqueViolation  # noqa: E402


def _rec(case_study, decision_name, rule_id, hit_policy, condition, variable_resolution, outputs=None):
    return {
        'case_study': case_study, 'decision_name': decision_name, 'rule_id': rule_id,
        'record_id': f'{case_study}::{decision_name}::{rule_id}',
        'hit_policy': hit_policy, 'condition': condition,
        'variable_resolution': variable_resolution, 'fk_closure_tables': [],
        'outputs': outputs or {},
    }


# ---------------------------------------------------------------------------
# Cases 1 & 2 -- FIRST hit policy precedence
# ---------------------------------------------------------------------------

def _first_policy_records():
    # Rule_1: amount > 100. Rule_2 (the "target"): amount > 10.
    # Any row with amount > 100 matches BOTH -- FIRST must pick Rule_1.
    rule1 = _rec('T', 'D_first', 'Rule_1', 'FIRST',
                 {'op': '>', 'left': {'kind': 'variable', 'ref': 'amount'},
                  'right': {'kind': 'literal', 'value': 100, 'type': 'number'}},
                 {'amount': {'kind': 'schema_column', 'table': 'txn', 'column': 'amount'}})
    rule2 = _rec('T', 'D_first', 'Rule_2', 'FIRST',
                 {'op': '>', 'left': {'kind': 'variable', 'ref': 'amount'},
                  'right': {'kind': 'literal', 'value': 10, 'type': 'number'}},
                 {'amount': {'kind': 'schema_column', 'table': 'txn', 'column': 'amount'}})
    return [rule1, rule2]


def test_case_1_first_earlier_rule_wins():
    conn = sqlite3.connect(':memory:')
    conn.execute('CREATE TABLE txn (txn_id INTEGER PRIMARY KEY, amount REAL)')
    conn.execute('INSERT INTO txn VALUES (1, 500)')  # matches BOTH rules
    conn.commit()
    result = run_decision(conn, 'D_first', _first_policy_records(), 'txn', ['txn_id'])
    assert result['matched_by_case'][(1,)] == ['Rule_1', 'Rule_2'], result['matched_by_case']
    assert result['selected_by_case'][(1,)] == 'Rule_1', \
        "FIRST must select the EARLIER matching rule, not the later target, even though both match"
    print("case 1 (FIRST, earlier rule wins): PASS")


def test_case_2_first_fallthrough_to_target():
    conn = sqlite3.connect(':memory:')
    conn.execute('CREATE TABLE txn (txn_id INTEGER PRIMARY KEY, amount REAL)')
    conn.execute('INSERT INTO txn VALUES (2, 50)')  # fails Rule_1 (not > 100), matches Rule_2
    conn.commit()
    result = run_decision(conn, 'D_first', _first_policy_records(), 'txn', ['txn_id'])
    assert result['matched_by_case'][(2,)] == ['Rule_2'], result['matched_by_case']
    assert result['selected_by_case'][(2,)] == 'Rule_2', \
        "with every earlier rule false, FIRST must fall through to the target rule"
    print("case 2 (FIRST, fallthrough to target): PASS")


# ---------------------------------------------------------------------------
# Cases 3 & 4 -- UNIQUE hit policy
# ---------------------------------------------------------------------------

def _unique_policy_records():
    rule1 = _rec('T', 'D_unique', 'Rule_1', 'UNIQUE',
                 {'op': '=', 'left': {'kind': 'variable', 'ref': 'status'},
                  'right': {'kind': 'literal', 'value': 'gold', 'type': 'string'}},
                 {'status': {'kind': 'schema_column', 'table': 'customer', 'column': 'status'}})
    rule2 = _rec('T', 'D_unique', 'Rule_2', 'UNIQUE',
                 {'op': '=', 'left': {'kind': 'variable', 'ref': 'status'},
                  'right': {'kind': 'literal', 'value': 'silver', 'type': 'string'}},
                 {'status': {'kind': 'schema_column', 'table': 'customer', 'column': 'status'}})
    return [rule1, rule2]


def test_case_3_unique_single_match():
    conn = sqlite3.connect(':memory:')
    conn.execute('CREATE TABLE customer (customer_id INTEGER PRIMARY KEY, status TEXT)')
    conn.execute("INSERT INTO customer VALUES (1, 'gold')")
    conn.commit()
    result = run_decision(conn, 'D_unique', _unique_policy_records(), 'customer', ['customer_id'])
    assert result['matched_by_case'][(1,)] == ['Rule_1']
    assert result['selected_by_case'][(1,)] == 'Rule_1'
    assert result['unique_violations'] == []
    print("case 3 (UNIQUE, single match): PASS")


def test_case_4_unique_violation():
    # A deliberately malformed pair of UNIQUE rules whose conditions
    # overlap (both match status='gold') -- a real semantic violation of
    # the DMN model's own UNIQUE contract, which the validator must
    # report, never silently resolve by picking one.
    rule1 = _rec('T', 'D_unique_bad', 'Rule_1', 'UNIQUE',
                 {'op': '=', 'left': {'kind': 'variable', 'ref': 'status'},
                  'right': {'kind': 'literal', 'value': 'gold', 'type': 'string'}},
                 {'status': {'kind': 'schema_column', 'table': 'customer', 'column': 'status'}})
    rule2 = _rec('T', 'D_unique_bad', 'Rule_2', 'UNIQUE',
                 {'op': '!=', 'left': {'kind': 'variable', 'ref': 'status'},
                  'right': {'kind': 'literal', 'value': 'bronze', 'type': 'string'}},
                 {'status': {'kind': 'schema_column', 'table': 'customer', 'column': 'status'}})
    conn = sqlite3.connect(':memory:')
    conn.execute('CREATE TABLE customer (customer_id INTEGER PRIMARY KEY, status TEXT)')
    conn.execute("INSERT INTO customer VALUES (1, 'gold')")  # matches BOTH: status='gold' AND status!='bronze'
    conn.commit()
    result = run_decision(conn, 'D_unique_bad', [rule1, rule2], 'customer', ['customer_id'])
    assert len(result['unique_violations']) == 1, result['unique_violations']
    pk_vals, violation = result['unique_violations'][0]
    assert isinstance(violation, UniqueViolation)
    assert set(violation.matched_rule_ids) == {'Rule_1', 'Rule_2'}
    assert (1,) not in result['selected_by_case'], \
        "a UNIQUE violation must never produce a selected rule, silently or otherwise"
    print("case 4 (UNIQUE violation): PASS")
    print(f"  reported: {violation}")


# ---------------------------------------------------------------------------
# Case 7 -- aggregate input (derived_aggregate)
# ---------------------------------------------------------------------------

def test_case_7_aggregate_input():
    # "eligible for bulk discount" if this customer has placed >= 3 orders.
    rule_eligible = _rec('T', 'D_aggregate', 'Rule_1', 'FIRST',
                          {'op': '>=', 'left': {'kind': 'variable', 'ref': 'orderCount'},
                           'right': {'kind': 'literal', 'value': 3, 'type': 'number'}},
                          {'orderCount': {'kind': 'derived_aggregate', 'aggregate': 'COUNT',
                                          'table': 'orders', 'filter_text': 'customer_id=<customer>'}})
    rule_default = _rec('T', 'D_aggregate', 'Rule_2', 'FIRST',
                         {'kind': 'literal', 'value': True, 'type': 'boolean'},
                         {'orderCount': {'kind': 'derived_aggregate', 'aggregate': 'COUNT',
                                         'table': 'orders', 'filter_text': 'customer_id=<customer>'}})

    conn = sqlite3.connect(':memory:')
    conn.execute('CREATE TABLE customer (customer_id INTEGER PRIMARY KEY)')
    conn.execute('CREATE TABLE orders (order_id INTEGER PRIMARY KEY, customer_id INTEGER)')
    conn.executemany('INSERT INTO customer VALUES (?)', [(1,), (2,)])
    conn.executemany('INSERT INTO orders (customer_id) VALUES (?)', [
        (1,), (1,), (1,), (1,),  # customer 1: 4 orders -> eligible
        (2,), (2,),              # customer 2: 2 orders -> not eligible
    ])
    conn.commit()

    result = run_decision(conn, 'D_aggregate', [rule_eligible, rule_default], 'customer', ['customer_id'])
    assert result['selected_by_case'][(1,)] == 'Rule_1', \
        f"customer 1 has 4 real orders (>= 3), aggregate input must select Rule_1: {result['selected_by_case']}"
    assert result['selected_by_case'][(2,)] == 'Rule_2', \
        f"customer 2 has 2 real orders (< 3), must fall through to the default: {result['selected_by_case']}"
    print("case 7 (aggregate input, derived_aggregate): PASS")
    print(f"  selected_by_case = {result['selected_by_case']}")


# ---------------------------------------------------------------------------
# Case 8 -- join-based input (join_lookup)
# ---------------------------------------------------------------------------

def test_case_8_join_based_input():
    # order.region comes from a JOIN through customer -> region, not a
    # column on order itself.
    rule_domestic = _rec('T', 'D_join', 'Rule_1', 'FIRST',
                          {'op': '=', 'left': {'kind': 'variable', 'ref': 'region'},
                           'right': {'kind': 'literal', 'value': 'domestic', 'type': 'string'}},
                          {'region': {'kind': 'join_lookup',
                                      'via': {'local_table': 'order', 'local_column': 'customer_id'},
                                      'result_table': 'customer', 'result_column': 'region'}})
    rule_default = _rec('T', 'D_join', 'Rule_2', 'FIRST',
                         {'kind': 'literal', 'value': True, 'type': 'boolean'},
                         {'region': {'kind': 'join_lookup',
                                     'via': {'local_table': 'order', 'local_column': 'customer_id'},
                                     'result_table': 'customer', 'result_column': 'region'}})

    conn = sqlite3.connect(':memory:')
    conn.execute('CREATE TABLE customer (customer_id INTEGER PRIMARY KEY, region TEXT)')
    conn.execute('CREATE TABLE "order" (order_id INTEGER PRIMARY KEY, customer_id INTEGER)')
    conn.executemany('INSERT INTO customer VALUES (?, ?)', [(1, 'domestic'), (2, 'overseas')])
    conn.executemany('INSERT INTO "order" (order_id, customer_id) VALUES (?, ?)', [(10, 1), (11, 2)])
    conn.commit()

    # join_lookup's own `via.local_table` IS the subject table here.
    result = run_decision(conn, 'D_join', [rule_domestic, rule_default], 'order', ['order_id'])
    assert result['selected_by_case'][(10,)] == 'Rule_1', \
        f"order 10's customer is domestic (via a real join, not a local column): {result['selected_by_case']}"
    assert result['selected_by_case'][(11,)] == 'Rule_2', \
        f"order 11's customer is overseas, must fall through: {result['selected_by_case']}"
    print("case 8 (join-based input, join_lookup): PASS")
    print(f"  selected_by_case = {result['selected_by_case']}")


# ---------------------------------------------------------------------------
# Case 10 -- duplicate decision outputs
# ---------------------------------------------------------------------------

def test_case_10_duplicate_outputs():
    # Rule_1 and Rule_2 have DIFFERENT conditions but the IDENTICAL
    # output value -- coverage must be tracked by rule ID, never by
    # output equality (which would incorrectly conflate them).
    rule1 = _rec('T', 'D_dup', 'Rule_1', 'FIRST',
                 {'op': '=', 'left': {'kind': 'variable', 'ref': 'tier'},
                  'right': {'kind': 'literal', 'value': 'A', 'type': 'string'}},
                 {'tier': {'kind': 'schema_column', 'table': 'acct', 'column': 'tier'}},
                 outputs={'approved': {'kind': 'literal', 'value': True, 'type': 'boolean'}})
    rule2 = _rec('T', 'D_dup', 'Rule_2', 'FIRST',
                 {'op': '=', 'left': {'kind': 'variable', 'ref': 'tier'},
                  'right': {'kind': 'literal', 'value': 'B', 'type': 'string'}},
                 {'tier': {'kind': 'schema_column', 'table': 'acct', 'column': 'tier'}},
                 outputs={'approved': {'kind': 'literal', 'value': True, 'type': 'boolean'}})  # SAME output as Rule_1

    conn = sqlite3.connect(':memory:')
    conn.execute('CREATE TABLE acct (acct_id INTEGER PRIMARY KEY, tier TEXT)')
    conn.executemany('INSERT INTO acct VALUES (?, ?)', [(1, 'A'), (2, 'B')])
    conn.commit()

    result = run_decision(conn, 'D_dup', [rule1, rule2], 'acct', ['acct_id'], collect_trace=True)
    assert result['selected_by_case'][(1,)] == 'Rule_1'
    assert result['selected_by_case'][(2,)] == 'Rule_2'
    assert result['verified_covered_rule_ids'] == {'Rule_1', 'Rule_2'}, \
        "both rules must be tracked as distinctly covered even though their outputs are identical"
    # Confirm the trace ALSO records the (identical) output correctly per
    # rule -- proving output tracking never fed back into selection.
    out1 = result['trace'][(1,)]['decision_output']
    out2 = result['trace'][(2,)]['decision_output']
    assert out1 == out2 == {'approved': True}
    print("case 10 (duplicate decision outputs): PASS")
    print(f"  verified_covered_rule_ids = {result['verified_covered_rule_ids']} "
          f"(both tracked despite identical output {out1})")


if __name__ == '__main__':
    test_case_1_first_earlier_rule_wins()
    test_case_2_first_fallthrough_to_target()
    test_case_3_unique_single_match()
    test_case_4_unique_violation()
    test_case_7_aggregate_input()
    test_case_8_join_based_input()
    test_case_10_duplicate_outputs()
    print("\nCases 5, 6, 9 already verified elsewhere:")
    print("  5/6 -- test_drd_chaining_synthetic.test_literal_via_upstream_branch "
          "(grounded + ungrounded cases)")
    print("  9   -- drd_executor.py's own __main__ acceptance test against real "
          "OpenMRS data (Preferred Identifier Requirement::Rule_2)")
