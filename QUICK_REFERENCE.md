# Quick reference — FAQ, glossary, and "where do I find X"

**Purpose:** stop re-searching the whole repo for the same things. Check
here first; only grep/read the actual source if this file doesn't have
the answer or pointer. Keep this updated whenever the same question gets
asked twice, or a search turns out to take more than a couple of tool
calls to resolve.

---

## 1. Glossary (read this before quoting any coverage number)

| Term | Meaning |
|---|---|
| **Rule** | One row of one real DMN decision table (e.g. `Decision_PromotionTemporalAvailability_rule_2`). The unit a person means by "a business rule." |
| **Objective** | One entry in `compiled_constraints.json` — what the DynaMOSA search actually optimizes a fitness function for. **Usually, but not always, 1:1 with a rule.** |
| **Why they can differ** | A rule whose condition depends on an upstream decision via `substituted_decision` chaining compiles to ONE OBJECTIVE PER POSSIBLE UPSTREAM RULE that could have produced the substituted value. Confirmed cases (2026-09-24): FLEX2 has 98 compiled objectives but only 55 distinct rules; jBilling has 40 objectives but 39 distinct rules. OpenMRS and Spree have no divergence. `coverage.py`'s own `verified_rule_coverage_percent` already divides by the deduplicated rule count — trust its printed percentage over a manual recomputation from a raw "compiled" count. |
| **`search_covered`** | The search's OWN claim: some individual in its saved archive reached fitness 0.0 for this objective. Not verified against real data. |
| **`verified_rule_selected` / verified coverage** | The validation oracle's independent finding: a REAL row in the materialized database, run through real SQL and real DMN rule selection, actually selects this rule. This is the trustworthy number. |
| **`agreement_class`** | `confirmed` (search claimed + verified agree, both true), `false_positive` (search claimed covered, validator disagrees — the search overclaimed), `false_negative` (search never claimed it, validator found a real case anyway — usually means the saved archive is stale/from before a fix), `agreed_uncovered` (neither claims it). |
| **Solvable vs. not solvable** | Not solvable = structurally unreachable by data generation at all (COLLECT hit policy, `code_external` app-only facts, explicitly out-of-scope blob-level facts). Undetermined = currently marked non-table-backed but never individually audited for a possible mis-mapping. Solvable = everything else. See `validation_oracle/COVERAGE_REPORT.md` for the current per-case-study breakdown. |
| **`[ASSUMED]` / `[CONFIRMED]`** | A ground-truth note's own disclosure tag. `[CONFIRMED]` = checked against real source (schema, cloned upstream repo, etc.). `[ASSUMED]` = a disclosed researcher interpretation, not independently verified against a real sample — never silently presented as fact. |
| **Disclosed override** | A hand-authored Python dict, in its own named file, recording a human judgment call the mechanical pipeline can't make on its own (an ambiguous join, a missing FK edge, an unparseable formula). Never a heuristic buried inline — see §3 below for the actual files. |
| **`not_persisted`** | A ground-truth fact declared to have no real backing table column at all (a genuine scenario/runtime parameter). Needs an explicit, disclosed override value passed to `coverage.py --not-persisted-json` to be validated — never silently defaulted or read from search state. |
| **`negate`** | A flag on a compiled `null_check` node (added 2026-09-24) for the rare ground-truth fact worded as "...IS NULL" / "...Blank" (true = EMPTY) instead of the majority "...Set"/"...Present" convention (true = SET). See `compile_constraints.py`'s `_null_check_is_negated`. |
| **COLLECT** | A DMN hit policy (return every matching rule, not just one) that `rule_evaluator.py` does not implement. Permanently out of scope until someone builds it; excluded from every coverage number everywhere. |
| **Subject table** | The one real table a decision's cases get enumerated over (e.g. `spree_orders` for an order-eligibility decision). Picked by `subject_table.py`'s `subject_table_for_decision`, which refuses to guess when no single table in the FK closure can reach every other table the decision's facts need. |
| **Fixture** | A real, materialized SQLite database (`validation_oracle/tests/fixtures/<cs>_merged.db`) built by merging every covered objective's own best-ever individual from a saved search archive. Built by `validation_oracle/tests/build_fixture_from_generator.py`. |

## 2. Common questions → where the answer lives

| Question | Answer lives in |
|---|---|
| "What's the current coverage?" | `validation_oracle/COVERAGE_REPORT.md` — do NOT recompute, read the recorded snapshot. |
| "What's broken right now, and what's already fixed?" | `validation_oracle/KNOWN_ISSUES.md` |
| "Why was X designed this way?" (search/mutation/fitness side) | `generator/DECISIONS_ALGORITHM.md`, or `generator/README.md` for the full chronological story |
| "Why was X designed this way?" (validation/verification side) | `validation_oracle/DESIGN.md` |
| "What experiments have actually been run, with what budgets/seeds?" | `generator/DECISIONS_EXPERIMENT.md`, raw data in `generator/experiment_runs/` |
| "What's the overall research narrative / elevator pitch?" | `HANDOFF.md` §1, or `docs/complete_approach_writeup.md` for the long version (check it isn't stale against `KNOWN_ISSUES.md` first) |
| "How does the DMN-to-schema mapping actually work, mechanically?" | `docs/dmn_to_schema_mapping.md`, or `generator/compile_constraints.py`'s own docstrings (`classify_derived` especially) |
| "What resolution kinds exist and what do they mean, and exactly how does a DMN rule turn into an objective?" | `RULE_TO_OBJECTIVE_MAPPING.md` — the full, example-grounded walkthrough. `generator/compile_constraints.py` (where they're produced) + `generator/candidate.py`'s `derive_value` (canonical read-side semantics) for the source itself. |
| "Is this specific gap a bug or a deliberate scope decision?" | `validation_oracle/KNOWN_ISSUES.md` — scope decisions get their own explicit "OUT OF SCOPE" entries, distinct from ordinary open bugs |
| "What are ALL the disclosed-override files, and what does each cover?" | See §3 immediately below |

## 3. Disclosed-override files (the "human judgment call, named and reviewable" pattern)

| File | Covers |
|---|---|
| `validation_oracle/join_disambiguation.py` | Ambiguous FK columns (more than one plausible path) |
| `validation_oracle/supplementary_fk_edges.py` | Real FK edges the schema extractor missed entirely |
| `validation_oracle/filter_placeholder_sources.py` | Which table a `filter_text` `<placeholder>` comes from when it isn't a column on the subject row |
| `generator/literal_expression_overrides.py` | Hand-translated FEEL formulas `feel_parser.py` can't parse (literal-expression decisions) |
| `<case_study>_dmn/provenance/variable_to_schema_mapping.csv` | The base layer: every DMN variable's own hand-curated mapping to a real schema fact, with `[ASSUMED]`/`[CONFIRMED]` notes |

## 4. Common commands

Run each from the directory shown (imports are directory-relative).

```bash
# Recompile ALL case studies' ground truth into compiled_constraints.json
cd generator && python3 compile_constraints.py
# One case study only:
cd generator && python3 compile_constraints.py --case-study Spree

# Full regression suite (run after ANY change to generator/ or validation_oracle/)
cd generator && python3 candidate.py            # full-corpus seeding sweep + flagship self-check
cd generator && python3 mutation.py             # mutation operator self-check
cd generator && python3 fitness.py              # fitness function self-check
cd validation_oracle && python3 tests/test_spec_cases.py
cd validation_oracle && python3 tests/test_drd_chaining_synthetic.py
cd validation_oracle && python3 tests/test_serialized_field_roundtrip.py
cd validation_oracle && python3 drd_executor.py  # OpenMRS acceptance test

# Re-run a case study's search (all 5 algorithm/budget configs) and save the archive
cd generator && python3 run_experiments.py       # ALL 4 case studies -- slow, be deliberate

# Rebuild one case study's fixture DB from an already-saved archive
cd validation_oracle/tests && python3 -c "
from build_fixture_from_generator import build
build(case_study='Spree',
      pickle_path='../../generator/experiment_runs/Spree__dynamosa_nsga2__budget1x__seed0.pkl',
      out_db_path='fixtures/spree_merged.db')
"

# Independently verify coverage for one case study against its fixture
cd validation_oracle && python3 coverage.py \
  --db tests/fixtures/spree_merged.db --case-study Spree \
  --algorithm dynamosa_nsga2 --run-id <label> --construction-strategy merged_archive \
  --archive-pickle ../generator/experiment_runs/Spree__dynamosa_nsga2__budget1x__seed0.pkl \
  --not-persisted-json <path-to-json>   # only if the case study has a not_persisted fact
  --out-dir coverage_out/spree
# NOTE: per standing instruction, don't run this speculatively -- only when
# asked to (re-)verify, and record the result in COVERAGE_REPORT.md after.
```

## 5. Before/after diff discipline (non-negotiable project convention)

Any change to shared, cross-case-study code (`candidate.py`, `mutation.py`,
`fitness.py`, `compile_constraints.py`, `db_resolver.py`, `subject_table.py`)
gets checked against ALL 4 case studies before being trusted, not just the
one being worked on:
1. Diff `compiled_constraints.json`'s record-ID set before/after recompiling
   (`added`/`removed` should almost always be empty — a change should not
   silently gain or drop records).
2. Re-run the full regression suite (§4).
3. If touching read/verification logic, diff the exact verified-rule-ID
   SETS (not just counts) across all 4 case studies' existing fixtures —
   a flipped rule can hide inside an unchanged total count (this caught
   the `null_check` polarity fix's own real edge case, `identifierBlank`).

## 6. Frequently re-asked questions (answered once, don't re-derive)

- **"Are you talking about rules or objectives?"** — see the glossary
  (§1). Default assumption when a number isn't labeled: it's probably
  the raw compiled-objective count, which only differs from the
  distinct-rule count for FLEX2 and jBilling (see the table in
  `COVERAGE_REPORT.md`).
- **"Why doesn't `Promotion Customer Group Eligibility` verify even
  though its own logic is correct?"** — a one-to-many backward join
  (`spree_orders` → `spree_promotion_rules`/`spree_order_promotions`)
  the validator correctly refuses to guess at, not a logic bug. Needs a
  disclosed override, tracked in `KNOWN_ISSUES.md`.
- **"Can we just decode the blob column to close more rules?"** — no,
  by explicit scope decision (`HANDOFF.md` §4, `KNOWN_ISSUES.md`'s
  scope-decision entry). The mechanism exists (`serialized_field`) but
  isn't being extended further.
- **"Why is FLEX2's coverage denominator sometimes 98 and sometimes
  55?"** — see the glossary's objectives-vs-rules entry. 98 = compiled
  objectives, 55 = distinct DMN rules. Use 55 for a rule-level
  percentage; use 98 only when explicitly talking about search
  objectives.
