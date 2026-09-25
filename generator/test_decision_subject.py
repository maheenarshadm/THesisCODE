"""Regression tests for generator-owned decision subject metadata.

Run from generator/: python test_decision_subject.py
"""
import json
import pathlib
import unittest

from compile_constraints import (
    _decision_subject_tables_referenced, _pick_subject_root,
    _load_raw_schema, compute_decision_subject,
)
from candidate import build_seed_candidate
from search import solve_branch
from dynamosa import merge_archive_candidate


class DecisionSubjectTests(unittest.TestCase):
    def test_query_targets_are_not_direct_row_dependencies(self):
        nodes = {
            'sql': {'kind': 'raw_sql_boolean', 'tables': ['EMPLOYEE'],
                    'sql_template': 'SELECT 1 WHERE OFFER_ID=<this course offering>'},
            'missing_correlation': {'kind': 'derived_aggregate', 'table': 'REPEAT_COURSE',
                                    'filter_text': None},
        }
        self.assertEqual(_decision_subject_tables_referenced('FLEX2',
            {'variable_resolution': nodes}), {'COURSE_OFFER'})
        # The same dependency must survive an inlined upstream expression.
        nested = {'variable_resolution': {'upstream': {'kind': 'substituted_decision',
                  'free_variable_resolutions': nodes}}}
        self.assertEqual(_decision_subject_tables_referenced('FLEX2', nested), {'COURSE_OFFER'})

    def test_unfiltered_exists_still_requires_its_row(self):
        record = {'variable_resolution': {'x': {'kind': 'exists', 'candidate_tables': ['PATIENT']}}}
        self.assertEqual(_decision_subject_tables_referenced('OpenMRS', record), {'PATIENT'})

    def test_override_cannot_invent_reachability(self):
        schema = {'A': {}, 'B': {}}
        self.assertIsNone(_pick_subject_root(schema, {'A', 'B'}, {'A', 'B'}))
        with self.assertRaisesRegex(ValueError, 'Stale subject-root override'):
            _pick_subject_root(schema, {'A', 'B'}, {'A', 'B'}, 'A')

    def test_ambiguous_roots_require_disclosed_choice(self):
        edge = {'column': 'parent_id', 'ref_table': 'P', 'ref_column': 'id'}
        schema = {'P': {}, 'A': {'fk_columns': [edge]}, 'B': {'fk_columns': [edge]}}
        self.assertIsNone(_pick_subject_root(schema, {'P'}, set(schema)))
        self.assertEqual(_pick_subject_root(schema, {'P'}, set(schema), 'A'), 'A')

    def test_real_summer_research_course_has_a_registration(self):
        records = [r for r in json.loads((pathlib.Path(__file__).parent /
                   'compiled_constraints.json').read_text())
                   if r['decision_name'] == 'Summer Semester Registration']
        subject = compute_decision_subject('FLEX2', records, _load_raw_schema('FLEX2'))
        self.assertEqual(subject['table'], 'COURSE_REGISTRATION')
        self.assertEqual(subject['pk_columns'], ['OFFER_ID', 'ROLL_NO'])
        rule = next(r for r in records if r['rule_id'].endswith('_Rule_1'))
        c, f, s = build_seed_candidate(rule)
        result = solve_branch(rule, c, f, s)
        self.assertTrue(result['solved'])
        rid = rule['record_id']
        archive = {rid: (result['fitness'], (result['candidate'],
                   {rid: result['focal']}, {rid: result['scenario']}))}
        merged, focal, _, _ = merge_archive_candidate(archive, records, 'FLEX2')
        rows = focal[rid]
        reg = rows['COURSE_REGISTRATION']
        course = rows.get('COURSE') or rows.get('course')
        offering = rows['COURSE_OFFER']
        self.assertEqual(course.get('COURSE_TYPE_ID', course.get('course_type_id')), 'RESEARCH')
        self.assertEqual(reg['COURSE_ID'], course['COURSE_ID'])
        self.assertEqual(reg['OFFER_ID'], offering['OFFER_ID'])
        self.assertIsNotNone(reg['ROLL_NO'])


if __name__ == '__main__':
    unittest.main()
