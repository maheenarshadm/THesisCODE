#!/usr/bin/env bash
# Full pipeline, NO-MERGE variant: re-run DynaMOSA search -> keep every
# individual SEPARATE (never merged into one shared database) -> verify
# each individual independently -> print/save the same concise summary
# table across all 4 case studies. Built 2026-09-25, on request, as the
# no-merge counterpart to run_full_pipeline.sh -- that script's own
# fixture-rebuild step currently crashes on FLEX2
# (dynamosa.merge_archive_candidate, see KNOWN_ISSUES.md's own
# "STUDENT_ATTENDANCE" open entry, deferred, not fixed here); this one
# sidesteps that entirely, since per_individual_archive_coverage.py never
# calls merge_archive_candidate at all.
#
# Uses --mode optimized (per_individual_archive_coverage.py's own faster
# path: a global remaining-rules set shrinks as individuals are
# processed, skipping decisions/individuals that can no longer teach us
# anything new) -- this script only needs the final UNION coverage
# number per case study, not full per-individual-vs-every-rule detail
# (use --mode full directly, per case study, if you want that instead).
#
# EACH search re-run OVERWRITES the committed, git-tracked
# generator/experiment_runs/<cs>__dynamosa_nsga2__budget1x__seed0.pkl
# archives (`git diff --stat generator/experiment_runs/` shows what
# changed, `git checkout -- <path>` reverts). Nothing here touches any
# committed *_merged.db fixture -- every database this script builds is
# a fresh, standalone per-individual one under
# validation_oracle/tests/per_individual_out/<CaseStudy>/dbs/, never a
# committed file.
#
# Usage: bash run_full_pipeline_no_merge.sh
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

PY="./.venv/Scripts/python.exe"
OUT_BASE="validation_oracle/tests/per_individual_out"
NOT_PERSISTED_JBILLING="validation_oracle/tests/jbilling_not_persisted.json"

echo "=================================================================="
echo "1/3  Re-running DynaMOSA (nsga2, budget1x, seed0) -- all 4 case studies"
echo "=================================================================="
"$PY" generator/rerun_dynamosa_nsga2_all.py

echo
echo "=================================================================="
echo "2/3  Materializing + verifying every individual SEPARATELY (no merge)"
echo "=================================================================="

echo "-- OpenMRS --"
"$PY" validation_oracle/tests/per_individual_archive_coverage.py \
  --case-study OpenMRS \
  --archive-pickle generator/experiment_runs/OpenMRS__dynamosa_nsga2__budget1x__seed0.pkl \
  --out-dir "$OUT_BASE/OpenMRS" \
  --mode optimized

echo "-- Spree --"
"$PY" validation_oracle/tests/per_individual_archive_coverage.py \
  --case-study Spree \
  --archive-pickle generator/experiment_runs/Spree__dynamosa_nsga2__budget1x__seed0.pkl \
  --out-dir "$OUT_BASE/Spree" \
  --mode optimized

echo "-- FLEX2 --"
"$PY" validation_oracle/tests/per_individual_archive_coverage.py \
  --case-study FLEX2 \
  --archive-pickle generator/experiment_runs/FLEX2__dynamosa_nsga2__budget1x__seed0.pkl \
  --out-dir "$OUT_BASE/FLEX2" \
  --mode optimized

echo "-- jBilling --"
"$PY" validation_oracle/tests/per_individual_archive_coverage.py \
  --case-study jBilling \
  --archive-pickle generator/experiment_runs/jBilling__dynamosa_nsga2__budget1x__seed0.pkl \
  --not-persisted-json "$NOT_PERSISTED_JBILLING" \
  --out-dir "$OUT_BASE/jBilling" \
  --mode optimized

echo
echo "=================================================================="
echo "3/3  Summarizing (union coverage per case study)"
echo "=================================================================="
"$PY" validation_oracle/tests/summarize_per_individual.py "$OUT_BASE"

echo
echo "Done. Per-individual databases + coverage detail are under:"
echo "  $OUT_BASE/<CaseStudy>/dbs/  and  $OUT_BASE/<CaseStudy>/runs/ (or /"
echo "  per_individual_coverage_summary_optimized.csv for optimized mode)"
echo "Summary table CSV:"
echo "  $OUT_BASE/coverage_summary_all.csv"
