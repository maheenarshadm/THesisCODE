#!/usr/bin/env bash
# Full pipeline: re-run DynaMOSA search -> rebuild fixtures -> verify ->
# print a concise summary table across all 4 case studies. Built
# 2026-09-25 because the compiled corpus changed since the last full
# search/fixture refresh (Preferred Identifier Requirement's COUNT-
# mechanism fix, 4 new OpenMRS Concept Name rules, the Spree rule_4
# out-of-scope exclusion, the FLEX2/jBilling discard decisions).
#
# EACH step below OVERWRITES committed, git-tracked files:
#   generator/experiment_runs/<cs>__dynamosa_nsga2__budget1x__seed0.pkl
#   validation_oracle/tests/fixtures/<cs>_merged.db
# `git diff --stat` after this finishes shows exactly what changed;
# `git checkout -- <path>` recovers the previous committed state for any
# file if the result doesn't look right.
#
# Usage: bash run_full_pipeline.sh
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

PY="./.venv/Scripts/python.exe"

echo "=================================================================="
echo "1/3  Re-running DynaMOSA (nsga2, budget1x, seed0) -- all 4 case studies"
echo "=================================================================="
"$PY" generator/rerun_dynamosa_nsga2_all.py

echo
echo "=================================================================="
echo "2/3  Rebuilding fixtures from the fresh archives"
echo "=================================================================="
"$PY" validation_oracle/tests/build_all_fixtures.py

echo
echo "=================================================================="
echo "3/3  Verifying against the rebuilt fixtures and summarizing"
echo "=================================================================="
"$PY" validation_oracle/tests/summarize_coverage.py validation_oracle/tests/full_pipeline_out

echo
echo "Done. Per-case-study coverage.py output (objective_results.csv,"
echo "decision_trace.json, validation_summary.csv) is under:"
echo "  validation_oracle/tests/full_pipeline_out/<CaseStudy>/"
echo "Summary table CSV:"
echo "  validation_oracle/tests/full_pipeline_out/summary_table.csv"
