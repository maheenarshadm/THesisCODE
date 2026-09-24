# Coverage report — recorded values, not live computation

**Purpose of this file, per explicit instruction:** every time a real
`coverage.py` run (or an equivalent direct computation over
`compiled_constraints.json`/`objective_results.csv`) produces coverage
numbers, they get written down here. When asked a coverage question
afterward, the answer comes from THIS FILE, not a fresh recomputation —
no `coverage.py` invocation, no requery of the database, no re-run of
the search, unless explicitly asked to re-run. If a number below looks
like it might be stale for what's being asked, say so and ask whether to
re-run, rather than silently recomputing.

**How to keep this file current:** after any run that produces new
coverage numbers, add/update the relevant entry below with the run's
own provenance (commit, fixture, archive, invocation), before reporting
the numbers back in chat.

---

## Latest snapshot

**As of commit `f8a64150` (2026-09-24), after:** the 3 requested Spree
fixes (`One-Use-Per-User Promotion Eligibility::rule_2` re-expression,
`Promotion Temporal Availability::rule_2` DMN fix, `First-Order
Promotion Eligibility::rule_3` shadowing-gap fix) + the `null_check`
polarity/`negate` fix (affects OpenMRS and jBilling too).

**Objectives vs. distinct DMN rules — read this before the tables.**
Most DMN rules compile to exactly one DynaMOSA search objective, but a
rule whose condition depends on an upstream decision via
`substituted_decision` chaining compiles to ONE OBJECTIVE PER POSSIBLE
UPSTREAM RULE that could have produced the substituted value — so a
single DMN rule can correspond to several compiled objectives. Confirmed
by direct query of `compiled_constraints.json` (2026-09-24): FLEX2 has
98 compiled objectives but only 55 distinct DMN rules (9 rules,
concentrated in `Course Load Limit`, `Admission Closure Eligibility`,
`Course Registration Eligibility`, expand to 2–11 objectives each);
jBilling has 40 objectives but 39 distinct rules (`Payment Balance
Assignment::Rule_2` alone expands to 2). OpenMRS (71) and Spree (31)
have no such expansion — objectives and distinct rules coincide.
`coverage.py`'s own `verified_rule_coverage_percent` already divides by
the DEDUPLICATED distinct-rule count, not the raw objective count — an
earlier version of this file's own "Raw coverage" column mistakenly
recomputed FLEX2/jBilling's percentage using the inflated objective
count instead of trusting the tool's own printed percentage; corrected
below (2026-09-24 correction, prompted by a user double-check).

### Raw verified coverage (`coverage.py`'s own
`verified_rule_coverage_percent` — denominator is DISTINCT DMN rules,
not raw compiled objectives; see the note above)

| Case study | Compiled objectives | Distinct DMN rules | Verified | Raw coverage |
|---|---|---|---|---|
| OpenMRS | 71 | 71 | 41 | 57.7% |
| Spree | 31 | 31 | 14 | 45.2% |
| FLEX2 | 98 | 55 | 21 | 38.2% |
| jBilling | 40 | 39 | 10 | 25.6% |
| **Total** | **240** | **196** | **86** | **43.9%** |

### Solvable-rules coverage (excludes rules that are structurally not
reachable by data generation at all — see category definitions below;
all counts are DISTINCT DMN rules)

| Case study | Distinct rules | Not solvable | Undetermined | Solvable | Verified | Solvable coverage |
|---|---|---|---|---|---|---|
| OpenMRS | 71 | 15 | 0 | 56 | 41 | 73.2% |
| Spree | 31 | 9 | 0 | 22 | 14 | 63.6% |
| FLEX2 | 55 | 0 | 2 | 53 | 21 | 39.6% |
| jBilling | 39 | 3 | 21 | 15 | 10 | 66.7% |
| **Total** | **196** | **27** | **23** | **146** | **86** | **58.9%** |

**Category definitions:**
- **Not solvable (permanent):** COLLECT hit policy (`rule_evaluator.py`
  doesn't support it — OpenMRS 15 rules across 5 decisions, Spree 5
  rules in `Price Adjustment Tier Validity Violations`), `code_external`
  facts genuinely computed by application code and never in any table
  (jBilling's `Ageing Step Config Validation`, 3 rules), and the
  explicitly scoped-out Spree blob-level facts (`Promotion Item Total
  Eligibility`, 4 rules — see `KNOWN_ISSUES.md`'s scope-decision entry).
- **Undetermined:** currently `not_persisted`/no-table-backed-input per
  ground truth, but never individually audited for a possible
  mis-mapping (the same species of error `purchaseQuantity` turned out
  to be before it was corrected to a real column). FLEX2's `Attendance
  Eligibility For Final Exam` (2 rules); jBilling's 6 "no table-backed
  input" decisions (13 distinct rules) + 2 decisions needing a
  `not_persisted` override (8 rules) = 21 rules.
- **Solvable:** distinct rules minus the two categories above — either
  already verified, or open with a known, in-principle-fixable cause
  (a disclosed join-construction override, more search budget/seeds, or
  a quick-win placeholder mapping already scoped in `KNOWN_ISSUES.md`).

**New finding surfaced while computing the corrected table (not yet in
`KNOWN_ISSUES.md`): FLEX2's `Course Load Limit` is 0/4 verified** and
isn't currently listed anywhere in that file's Open Issues section —
worth adding and investigating, not yet done.

### Per-case-study provenance (fixture / archive / invocation used to
produce the numbers above)

- **OpenMRS**: `tests/fixtures/openmrs_merged.db`,
  `generator/experiment_runs/OpenMRS__dynamosa_nsga2__budget1x__seed0.pkl`,
  no `--not-persisted-json`.
- **Spree**: `tests/fixtures/spree_merged.db` (rebuilt this session from
  the re-run archive), `generator/experiment_runs/
  Spree__dynamosa_nsga2__budget1x__seed0.pkl`, `--not-persisted-json`
  `{"evaluationTime": 20000}`.
- **FLEX2**: `tests/fixtures/flex2_merged.db`, `generator/experiment_runs/
  FLEX2__dynamosa_nsga2__budget1x__seed0.pkl`, no override.
- **jBilling**: `tests/fixtures/jbilling_merged.db`,
  `generator/experiment_runs/jBilling__dynamosa_nsga2__budget1x__seed0.pkl`,
  no override.

All 4 runs used `--algorithm dynamosa_nsga2 --construction-strategy
merged_archive`. Decision-table coverage (≥1 rule verified per
decision, COLLECT decisions excluded): OpenMRS 14/14 (100%), Spree 5/8,
FLEX2 2/10, jBilling 6/16 — unchanged by this session's fixes except
Spree (previously 4/8).

---

## Run history

### 2026-09-24 — correction: objectives vs. distinct DMN rules
No new run performed. In response to a user double-check ("for one rule
there could be multiple objectives?"), re-examined the ALREADY-COMPILED
`compiled_constraints.json` and the ALREADY-GENERATED
`objective_results.csv` files from the `f8a64150` run below — confirmed
9 DMN rules (FLEX2: 7, jBilling: 1, with one of jBilling's own objective
pairs collapsing into 1 rule) each expand into multiple compiled
objectives via `substituted_decision` chaining. This file's own prior
"Latest snapshot" had manually recomputed FLEX2/jBilling's "raw
coverage" percentage using the inflated objective count (98, 40)
instead of the tool's own already-correct distinct-rule denominator (55,
39) — corrected above. No case study's underlying verified/compiled
truth changed; only this file's own arithmetic did.

### 2026-09-24, commit `f8a64150` — the 3 Spree fixes + null_check/negate fix
Numbers: see "Latest snapshot" above. Full before/after diff (exact
verified rule ID sets, not just counts) run across all 4 case studies
before trusting this; zero unexplained regressions (the one flipped
OpenMRS rule, `Identifier Format Validity::Rule_2`, was a bug artifact
of the very inversion being fixed, confirmed against real data). See
`KNOWN_ISSUES.md` for the full narrative.

### 2026-09-24, commit `f79d33f` — Spree search re-run (pre null_check fix)
Spree: 12/31 verified (38.7%), 5/8 decision-table. Superseded by the run
above (the null_check/negate fix changed 3 of these 31 rules' outcomes).

### 2026-09-24, commit `8dda681` — `serialized_field` mechanism shipped
Spree compiled record count 27/32 → 31/32 (compile-time only; this
commit predates any search re-run against the new ground truth, so no
new verified-coverage number came out of it).
