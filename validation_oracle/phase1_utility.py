"""The ONE explicit, documented exception to validation_oracle's
independence from `generator/` (see DESIGN.md, "Architectural separation
requirement"): reads `generator/compiled_constraints.json` directly, as a
plain JSON file -- never imports any `generator/` Python module. This is
declarative, compile-time metadata (which table/column each DMN input
resolves to, DRD grounding, hit-policy suppression context) produced once
by `compile_constraints.py`/`feel_parser.py`, before any search runs --
not a search-time computed value, cached fitness, or verdict.

Every OTHER validation_oracle module reads this utility's output, never
compiled_constraints.json directly -- so the one dependency on Phase 1's
output is isolated to this single file, inspectable and swappable in one
place.
"""
import json
import os

COMPILED_CONSTRAINTS_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', 'generator', 'compiled_constraints.json')
COMPILE_REPORT_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', 'generator', 'compile_report.json')


def load_records(case_study, path=COMPILED_CONSTRAINTS_PATH):
    """Every compiled objective (record) for one case study, exactly as
    `compile_constraints.py` produced it -- record_id, decision_name,
    rule_id, condition, variable_resolution, hit_policy_context,
    fk_closure_tables, grounded_upstream_branches, feasibility."""
    with open(path) as f:
        compiled = json.load(f)
    return [r for r in compiled if r['case_study'] == case_study]


def records_by_decision(case_study, path=COMPILED_CONSTRAINTS_PATH):
    """{decision_name: [record, ...]} -- every objective grounded on that
    decision's own rules, regardless of which upstream branch grounds it
    (a decision with DRD fan-out has several records per rule; see
    generator/DECISIONS_ALGORITHM.md's own objective/rule relationship
    finding -- one rule can have several objectives, one objective always
    has exactly one rule)."""
    by_decision = {}
    for r in load_records(case_study, path):
        by_decision.setdefault(r['decision_name'], []).append(r)
    return by_decision


def statically_infeasible_count(case_study, path=COMPILE_REPORT_PATH):
    """How many of this case study's rules were removed BEFORE search as
    provably infeasible (three-valued constant folding) -- specifically
    `reason == 'infeasible'` among compile_report.json's own
    `blocked_records`, NOT the broader 'blocked' total (which also
    includes `unresolved_variable`/`chained_dependency_unexpandable` --
    schema-gap-style blocks, a different category from proven-false;
    conflating them would misreport the denominator per this project's
    own DECISIONS_EXPERIMENT.md discipline on this exact distinction)."""
    with open(path) as f:
        report = json.load(f)
    return sum(1 for r in report['blocked_records']
               if r['case_study'] == case_study and r['reason'] == 'infeasible')
