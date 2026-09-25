"""Runs coverage.py against each case study's (freshly rebuilt) fixture
and prints + saves ONE concise summary table across all 4 case studies
-- the final step of the "full pipeline" the user asked for 2026-09-25
(re-run search -> rebuild fixtures -> verify -> summarize).

**"In scope" / "out of scope" here is a MECHANICAL, code-derivable
proxy, NOT a re-run of the full 2026-09-25 manual audit recorded in
HANDOFF.md / COVERAGE_REPORT.md** (which also folds in real judgment
calls -- discard-candidates, search-limited-vs-permanent classification,
jBilling's own still-unaudited ~9 never-compiled rules -- none of which
are encoded anywhere in the compiled corpus itself, only in that audit's
own prose). Out of scope here means only the three PERMANENT, structural
categories this codebase can tell apart WITHOUT a human audit:
  - COLLECT hit policy (rule_evaluator.py doesn't support it)
  - every one of a rule's own variables resolving to a code_external fact
  - a rule explicitly listed in out_of_scope_rules.py's own registry
If this table's own numbers disagree with COVERAGE_REPORT.md's own
recorded figures, trust COVERAGE_REPORT.md for anything that matters --
treat this table as a fast, mechanical sanity check after a pipeline
re-run, not a replacement for the recorded, audited numbers.
"""
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
GENERATOR_DIR = os.path.join(HERE, '..', '..', 'generator')
VALIDATION_ORACLE_DIR = os.path.join(HERE, '..')
sys.path.insert(0, GENERATOR_DIR)
sys.path.insert(0, VALIDATION_ORACLE_DIR)

from coverage import run_coverage  # noqa: E402
from out_of_scope_rules import OUT_OF_SCOPE_RULES, is_out_of_scope  # noqa: E402

CASE_STUDIES = ('OpenMRS', 'Spree', 'FLEX2', 'jBilling')
FIXTURE_NAME = {
    'OpenMRS': 'openmrs_merged.db',
    'Spree': 'spree_merged.db',
    'FLEX2': 'flex2_merged.db',
    'jBilling': 'jbilling_merged.db',
}
# Same disclosed override every jBilling coverage.py invocation has used
# throughout this project's history -- never derived from search state.
NOT_PERSISTED = {
    'jBilling': {'__today__': 20000, 'candidateDateProvided': True, 'candidateDate': 0},
}


def _is_code_external_only(record):
    kinds = {node.get('kind') for node in record.get('variable_resolution', {}).values()}
    return bool(kinds) and kinds <= {'code_external'}


def _mechanical_out_of_scope(case_study, records_by_rule):
    """As of 2026-09-26, every COLLECT/all-code_external rule has been
    physically removed from `compiled_constraints.json` itself (archived
    at `validation_oracle/out_of_scope/permanent/`, on the user's own
    request -- not just filtered at runtime anymore), so `records_by_rule`
    (built from that now-smaller corpus by every caller) should never
    contain one going forward -- this function's own fresh recomputation
    of the two structural criteria should always come back empty, matching
    an equally-empty registry. Kept anyway, unchanged, as a standing guard:
    if a FUTURE recompile ever reintroduces a COLLECT or all-code_external
    rule (a DMN edit, a new case study), this raises loudly instead of
    silently letting it slip back into "in scope" unnoticed -- the same
    discipline this project's other disclosed-override files already
    follow. `out_of_scope_rules.OUT_OF_SCOPE_RULES` remains the source of
    truth for whatever registry-based exclusions still apply (e.g. Spree's
    one remaining one-to-many-join entry)."""
    freshly_computed = set()
    for rule_id, recs in records_by_rule.items():
        if any(r['hit_policy'] == 'COLLECT' for r in recs):
            freshly_computed.add(rule_id)
        elif all(_is_code_external_only(r) for r in recs):
            freshly_computed.add(rule_id)

    registered = {rule_id for rule_id in records_by_rule
                  if is_out_of_scope(case_study, rule_id)
                  and OUT_OF_SCOPE_RULES[(case_study, rule_id)] in
                  ('COLLECT hit policy', 'all facts code_external')}

    if freshly_computed != registered:
        missing = freshly_computed - registered
        stale = registered - freshly_computed
        raise ValueError(
            f"{case_study}: out_of_scope_rules.py's structural entries have drifted from "
            f"a fresh recomputation against the current compiled_constraints.json -- "
            f"missing (structurally out of scope but not registered): {sorted(missing)}; "
            f"stale (registered as structural but no longer meets either criterion): "
            f"{sorted(stale)}. Update out_of_scope_rules.py's own structural section, "
            f"never silently trust either side.")

    return {rule_id for rule_id in records_by_rule if is_out_of_scope(case_study, rule_id)}


def summarize(out_dir):
    compiled = json.load(open(os.path.join(GENERATOR_DIR, 'compiled_constraints.json')))
    rows = []
    for cs in CASE_STUDIES:
        records = [r for r in compiled if r['case_study'] == cs]
        records_by_rule = {}
        for r in records:
            records_by_rule.setdefault(r['rule_id'], []).append(r)
        total_rules = len(records_by_rule)
        objectives = len(records)

        out_of_scope = _mechanical_out_of_scope(cs, records_by_rule)
        in_scope = total_rules - len(out_of_scope)

        db_path = os.path.join(HERE, 'fixtures', FIXTURE_NAME[cs])
        run_out_dir = os.path.join(out_dir, cs)
        summary = run_coverage(
            db_path, cs, 'dynamosa_nsga2', 'full_pipeline', 'merged_archive',
            archive=None, out_dir=run_out_dir,
            not_persisted_overrides=NOT_PERSISTED.get(cs))
        validated = summary['verified_covered_rules']

        rows.append({
            'case_study': cs, 'total_rules': total_rules, 'objectives': objectives,
            'in_scope': in_scope, 'out_of_scope': len(out_of_scope), 'validated': validated,
            'pct_all': (validated / total_rules * 100) if total_rules else 0.0,
            'pct_in_scope': (validated / in_scope * 100) if in_scope else 0.0,
        })
    return rows


def print_table(rows):
    headers = ['Case study', 'Total rules', 'Objectives', 'In scope', 'Out of scope',
               'Validated', '% of all', '% of in-scope']
    widths = [12, 11, 10, 8, 12, 9, 8, 13]

    def fmt_row(vals):
        return '  '.join(str(v).rjust(w) for v, w in zip(vals, widths))

    print(fmt_row(headers))
    print('  '.join('-' * w for w in widths))
    for r in rows:
        print(fmt_row([r['case_study'], r['total_rules'], r['objectives'], r['in_scope'],
                        r['out_of_scope'], r['validated'], f"{r['pct_all']:.1f}%",
                        f"{r['pct_in_scope']:.1f}%"]))


def save_table(rows, path):
    with open(path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['case_study', 'total_rules', 'objectives', 'in_scope',
                                           'out_of_scope', 'validated', 'pct_all', 'pct_in_scope'])
        w.writeheader()
        w.writerows(rows)


if __name__ == '__main__':
    out_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'full_pipeline_out')
    os.makedirs(out_dir, exist_ok=True)
    rows = summarize(out_dir)
    print()
    print_table(rows)
    csv_path = os.path.join(out_dir, 'summary_table.csv')
    save_table(rows, csv_path)
    print(f"\nSaved: {csv_path}")
