"""Builds the SAME concise summary table as summarize_coverage.py, but
from per_individual_archive_coverage.py's own OUTPUT (never-merged,
one-database-per-individual results) instead of coverage.py against a
single merged fixture -- built 2026-09-25 specifically because
dynamosa.merge_archive_candidate currently crashes on FLEX2 (see
KNOWN_ISSUES.md's own "STUDENT_ATTENDANCE" open entry), so the merge-
based pipeline (summarize_coverage.py) can't currently produce FLEX2
numbers at all. This one never merges anything, so it isn't affected.

Reads, per case study, whichever per_individual_archive_coverage.py
output already exists under --base-dir/<CaseStudy>/ -- optimized mode
(per_individual_coverage_summary_optimized.csv) is tried first (cheaper
to read, already gives the exact "first individual to verify each rule"
union directly), falling back to full mode
(per_individual_coverage_long.csv) if that's what was actually run
instead. "Validated" is the UNION of rules verified across every
individual processed for that case study, matching the definition
already established earlier this session, not a per-individual number.

"In scope" / "out of scope" and "claimed fulfilled" are the SAME
mechanical/code-derivable proxies summarize_coverage.py already uses and
documents (see that file's own docstring for the exact, disclosed
limits versus the full manual audit in HANDOFF.md/COVERAGE_REPORT.md) --
reused here via direct import, not re-derived a second way.
"""
import csv
import json
import os
import pickle
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
GENERATOR_DIR = os.path.join(HERE, '..', '..', 'generator')
VALIDATION_ORACLE_DIR = os.path.join(HERE, '..')
sys.path.insert(0, GENERATOR_DIR)
sys.path.insert(0, VALIDATION_ORACLE_DIR)

from summarize_coverage import _mechanical_out_of_scope  # noqa: E402

CASE_STUDIES = ('OpenMRS', 'Spree', 'FLEX2', 'jBilling')


def _validated_union(case_dir):
    optimized_path = os.path.join(case_dir, 'per_individual_coverage_summary_optimized.csv')
    if os.path.exists(optimized_path):
        validated = set()
        with open(optimized_path, newline='') as f:
            for row in csv.DictReader(f):
                ids = row.get('new_verified_rule_ids') or ''
                if ids:
                    validated.update(ids.split('; '))
        return validated

    long_path = os.path.join(case_dir, 'per_individual_coverage_long.csv')
    if os.path.exists(long_path):
        validated = set()
        with open(long_path, newline='') as f:
            for row in csv.DictReader(f):
                if row['verified'] == 'True':
                    validated.add(row['rule_id'])
        return validated

    raise FileNotFoundError(
        f"No per_individual_archive_coverage.py output found under {case_dir} "
        f"(expected per_individual_coverage_summary_optimized.csv or "
        f"per_individual_coverage_long.csv) -- run that script for this case study first.")


def _claimed_fulfilled(archive_pickle_path, out_of_scope):
    """`out_of_scope` is the SAME `_mechanical_out_of_scope` result
    `summarize`'s own `in_scope`/`out_of_scope` columns already use --
    excluded here too. A real bug found running this against Spree
    (2026-09-26): counting every fitness==0.0 archive entry with no scope
    filtering let `claimed_fulfilled` exceed `in_scope` outright (29 vs
    25) -- 5 of Spree's own claimed entries are `PriceAdjustmentTier
    Validity_rule_1..5`, COLLECT hit policy, out of scope by the SAME
    mechanical definition `in_scope`/`out_of_scope` already use. The
    search's own fitness function doesn't care about hit policy and can
    genuinely reach fitness=0.0 on a COLLECT rule; the validator
    structurally can't independently check it either way
    (`rule_evaluator.py` doesn't support COLLECT) -- filtering here just
    makes this table's own columns consistent with each other, using the
    SAME scope definition for both. Same fix already applied to
    `per_individual_archive_coverage.py`'s own `_print_summary_line`."""
    with open(archive_pickle_path, 'rb') as f:
        top = pickle.load(f)
    archive = top['archive']
    return sum(1 for rid, (fitness, _ind) in archive.items()
               if fitness == 0.0 and rid.split('::')[-1] not in out_of_scope), len(archive)


def summarize(base_dir):
    compiled = json.load(open(os.path.join(GENERATOR_DIR, 'compiled_constraints.json')))
    rows = []
    for cs in CASE_STUDIES:
        records = [r for r in compiled if r['case_study'] == cs]
        by_rule = {}
        for r in records:
            by_rule.setdefault(r['rule_id'], []).append(r)
        total_rules = len(by_rule)
        objectives = len(records)

        out_of_scope = _mechanical_out_of_scope(cs, by_rule)
        in_scope = total_rules - len(out_of_scope)

        archive_pickle = os.path.join(
            GENERATOR_DIR, 'experiment_runs', f'{cs}__dynamosa_nsga2__budget1x__seed0.pkl')
        claimed, archive_total = _claimed_fulfilled(archive_pickle, out_of_scope)

        case_dir = os.path.join(base_dir, cs)
        validated = len(_validated_union(case_dir))

        rows.append({
            'case_study': cs, 'total_rules': total_rules, 'objectives': objectives,
            'claimed_fulfilled': claimed, 'in_scope': in_scope,
            'out_of_scope': len(out_of_scope), 'validated': validated,
            'pct_all': (validated / total_rules * 100) if total_rules else 0.0,
            'pct_in_scope': (validated / in_scope * 100) if in_scope else 0.0,
        })
    return rows


def print_table(rows):
    headers = ['Case study', 'Total', 'Objectives', 'Claimed', 'In scope', 'Out scope',
               'Validated', '% all', '% in-scope']
    widths = [10, 6, 10, 8, 8, 9, 9, 7, 10]

    def fmt(vals):
        return '  '.join(str(v).rjust(w) for v, w in zip(vals, widths))

    print(fmt(headers))
    print('  '.join('-' * w for w in widths))
    for r in rows:
        print(fmt([r['case_study'], r['total_rules'], r['objectives'], r['claimed_fulfilled'],
                    r['in_scope'], r['out_of_scope'], r['validated'],
                    f"{r['pct_all']:.1f}%", f"{r['pct_in_scope']:.1f}%"]))


def save_table(rows, path):
    with open(path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['case_study', 'total_rules', 'objectives',
                                           'claimed_fulfilled', 'in_scope', 'out_of_scope',
                                           'validated', 'pct_all', 'pct_in_scope'])
        w.writeheader()
        w.writerows(rows)


if __name__ == '__main__':
    base_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'per_individual_out')
    rows = summarize(base_dir)
    print()
    print_table(rows)
    out_path = os.path.join(base_dir, 'coverage_summary_all.csv')
    save_table(rows, out_path)
    print(f"\nSaved: {out_path}")
