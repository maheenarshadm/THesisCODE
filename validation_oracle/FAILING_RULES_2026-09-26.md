# Rules that fail to independently validate (2026-09-26)

Fresh run, all 4 case studies, `--mode optimized`, taken **after** today's three
fixes (`drd_executor.py`'s cross-rule variable poisoning, the permanent
out-of-scope registry, and the two FLEX2 materialization collisions). "Fails
to validate" means: across every archived best-individual actually tested,
**no individual's own database ever independently confirmed this rule** —
either because the rule is permanently out of reach of a database-only
oracle, or because none of the tested individuals happened to build data
that satisfies it.

| Case study | Total rules | In scope | Out of scope | Validated | Never validated |
|---|---|---|---|---|---|
| OpenMRS  | 79 | 64 | 15 | 30 | 49 |
| Spree    | 31 | 25 |  6 | 16 | 15 |
| FLEX2    | 55 | 55 |  0 | 32 | 23 |
| jBilling | 39 | 37 |  2 | 17 | 22 |

Every rule below is real, taken directly from this run's own output
(`validation_oracle/tests/per_individual_out/<CaseStudy>/per_individual_coverage_summary_optimized.csv`),
cross-checked against `compiled_constraints.json`'s own condition tree — not
guessed.

---

## 1. Permanently out of scope (not a bug — structurally can't be checked)

These can never be independently verified by this oracle, regardless of
data, and are excluded from "in scope" in the table above. The search's own
fitness function doesn't know about this distinction, so it can still claim
`fitness=0.0` on some of them — that's expected, not a discrepancy.

**COLLECT hit policy** — `rule_evaluator.py` has no COLLECT implementation
at all (it only does FIRST/UNIQUE):
- OpenMRS: `Death Date Consistency Violations` (2 rules), `Encounter Datetime Validity Violations` (4), `Order Date Activated Consistency Violations` (4), `Program Enrollment Date Consistency Violations` (3), `Relationship Date Validity Violations` (2) — all 5 decisions are "find every record that violates a date rule," a COLLECT-shaped question by nature.
- Spree: `Price Adjustment Tier Validity Violations` (5 rules) — same shape, "flag every invalid tier."

**All facts `code_external`** — genuinely nothing in any table, computed only by application code:
- jBilling: `Is Ageing Required::Rule_2`, `Daily Pro-Rate Amount::Rule_3`.

**Manually curated (registry, pre-existing)**:
- Spree: `Promotion Customer Group Eligibility::rule_4` — needs a genuine one-to-many backward join with no honest single-row answer (see `KNOWN_ISSUES.md`).

---

## 2. Structurally unresolvable right now (real, current gaps — not yet registered as permanently out of scope)

Unlike section 1, these are **not yet confirmed permanent** — they're decisions
`build_subject_tables` currently can't find a usable subject for at all, so
every rule under them is untestable today. Worth investigating further
before deciding whether they're a permanent limitation or a fixable gap.

| Decision | Case study | What it checks | Why it's unresolvable |
|---|---|---|---|
| Promotion Item Total Eligibility (4 rules) | Spree | Which price-break tier an order's item total falls into | No single table can reach both `spree_orders` and `spree_promotion_rules` — 0 candidate root tables qualify |
| Admission Closure Eligibility (5 rules) | FLEX2 | Whether a student's academic standing forces admission closure | No single table can reach both `ADM_MERIT_LIST` and `STUDENT_PROGRAM` — 0 candidate root tables qualify |
| Order Date Range Valid (5 rules) | jBilling | Whether a requested order date range is well-formed | Every input (`parseOrAccessError`, `startDateProvided`, etc.) is a transient runtime parameter — no table-backed fact to enumerate real cases from at all |
| Payment Outcome Resolution (1 of 2 rules)* | jBilling | Whether a payment processor was reachable | Same as above — `processorUnavailable` is purely runtime |
| Payment Balance Assignment (1 rule) | jBilling | How to apply a payment when the processor was unavailable | Chains from Payment Outcome Resolution's own unresolvable input |

\* `Payment Outcome Resolution` has 2 rules total, both unresolvable — listed once here, both counted in section 3's totals below for clarity.

---

## 3. Resolvable, but no individual actually satisfied it

The decision itself works fine (a real subject table was found, real
conditions were checked against real data) — these specific rules just
never came up true for any of the individuals in the current archive. This
is the most informative bucket for "is the search finding enough varied
data," but a full root-cause trace (like the one done earlier for jBilling's
`Currency Exchange Rate Source` / `Order Period Already Invoiced`) hasn't
been done for every rule below — only a real, data-backed pattern check
(comparing against verified sibling rules in the same decision).

**Recurring, evidence-backed pattern**: in decision after decision, the rule
verifying is the "normal"/default case, while the rule(s) never verifying
are the ones that require the search to deliberately construct an
**extreme, violating, or edge-case value** (a count crossing a threshold, a
value outside a normal range, a rare enum branch). That's consistent with a
real search-coverage gap (the search isn't reliably constructing that kind
of data), not a validator defect — but this is a pattern observation, not a
confirmed root cause for each individual rule.

### OpenMRS (34 rules, decision resolves fine)

| Decision | Rules never verified | What they check | Verified sibling shows |
|---|---|---|---|
| Birthdate Validity | Rule_1, 2, 3 (all 3) | Birthdate in the future / age > 140yrs / normal age | No sibling verified either — whole decision never matched by any individual |
| Concept Fully-Specified-Name Presence Requirement | Rule_1 | ≥1 fully-specified name exists | Rule_2 (fewer than 1) verifies — search builds "missing," not "present" |
| Concept Fully-Specified-Name Uniqueness Per Locale | Rule_1 | ≥2 duplicate names in one locale | Rule_2 (no duplicate) verifies — search never builds the duplicate |
| Concept Locale-Preferred-Name Uniqueness | Rule_1 | ≥2 locale-preferred names | Rule_2 (no duplicate) verifies |
| Concept Preferred Name Validity | Rule_2, 3, 4, 5 | 4 different locale-preferred-name sub-cases (index term / short name / voided combinations) | Rule_1 (not locale-preferred at all) verifies |
| Concept Short-Name Uniqueness Per Locale | Rule_1 | ≥2 duplicate short names | Rule_2 (no duplicate) verifies |
| Identifier Format Validity | Rule_1, 2, 3 | Blank identifier / format mismatch / format match | Rule_4 verifies — the one case not needing a real regex match |
| Identifier Location Requirement | Rule_2, 3 | Location missing when required / missing when not-used | Rule_1 verifies (location present) |
| Identifier Uniqueness Check | Rule_1, 3, 4 | Non-unique-allowed / in-use-by-another-patient combinations | Rule_2 verifies |
| Numeric Absolute Range Validity | Rule_1, 2 | Value above hi-absolute / below lo-absolute | Rule_3 (within range) verifies — search never builds out-of-range values |
| Numeric Interpretation Classification | Rule_1, 2, 3, 4 | Hi-critical / hi-normal / lo-critical / lo-normal thresholds | Rule_5 (normal) verifies — same pattern, extremes never built |
| Numeric Precision Validity | Rule_1, 2, 3 | Decimals allowed / not-allowed-and-integer / not-allowed-and-fraction | No sibling verified — whole decision never matched |
| Obs Value Required By Datatype | Rule_2, 3, 4, 5, 6 | Boolean / Coded / (2 more datatypes) / Numeric / Text concept | Rule_1 (obs-group case) verifies — non-group, specific-datatype cases don't |
| Preferred Identifier Requirement | Rule_1 | ≥1 identifier marked preferred | Rule_2, 3 verify (0 preferred identifiers) — search never marks one preferred |

### Spree (9 rules, decision resolves fine)

| Decision | Rules never verified | What they check | Verified sibling shows |
|---|---|---|---|
| Promotion Customer Group Eligibility | rule_1, rule_2 | No customer on order / no target groups configured | (rule_3 doesn't exist in this decision's compiled set; rule_4 is separately out of scope) — neither of these two ever matched |
| Promotion Temporal Availability | rule_1, rule_2 | Promotion starts in the future / already expired | rule_3 (catch-all "currently active") is ALSO never verified — whole decision never matched by any individual |

### FLEX2 (18 rules, decision resolves fine)

| Decision | Rules never verified | What they check | Verified sibling shows |
|---|---|---|---|
| Attendance Eligibility For Final Exam | Rule_1, Rule_2 (both) | ≥80% attendance / <80% attendance | Neither verifies — the `STUDENT_ATTENDANCE` data this depends on materializes correctly now (see today's fix), but no individual's actual attendance count lands on either side cleanly under real verification |
| Course Load Limit | Rule_1, 2, 3, 4 (all 4) | Max courses allowed under 4 warning-count/semester-type combinations | No sibling verified — whole decision never matched |
| Course Registration Eligibility | Rule_2, 3, 4 | Grade-based / overload / catch-all registration blocks | Rule_1 verifies (a different upstream-branch variant) |
| Course Replacement Eligibility | Rule_1, 3, 4 | Core course / credits-below-target / course-offered-again cases | Rule_2, 5, 6 verify — the narrower core/credit-specific cases don't |
| Credit Transfer Exemption | Rule_1, 2 | >50% exempted credits / 0 unmet-prerequisite count | Rule_3 verifies |
| Summer Semester Registration | Rule_1, 2, 3, 5 | Research course / prior-registration / repeat-count / catch-all | Rule_4 verifies — again, the specific/extreme branches don't |

### jBilling (9 rules, decision resolves fine)

| Decision | Rules never verified | What they check | Verified sibling shows |
|---|---|---|---|
| Ageing Status Change Order Action | Rule_2, 3 | Login access being revoked / being granted on status change | Rule_1, 4 verify |
| Ageing Step Config Validation | Rule_2, 5 | In-use step missing welcome message / catch-all default | Rule_1 verifies (fixed today — see below); Rule_5's own FIRST-policy position means it can only fire when nothing earlier matches, and Rule_1 already catches most individuals first |
| Blacklist Filter Enabled | Rule_1 | Blacklist plugin ID = 0 (disabled) | Rule_2 (plugin ID ≠ 0, enabled) verifies |
| Currency Exchange Rate Source | Rule_1, 2 | Entity-specific rate exists / system-default rate exists | Rule_3 (neither exists) verifies — **known, disclosed gap**: `base_user`'s own `entity_id`/`currency_id` columns are never populated by the generator, so these can structurally never be reached under the current subject choice (see `KNOWN_ISSUES.md`'s "Currency Exchange Rate Source" entry) |
| Order Period Already Invoiced | Rule_1, 3 | Candidate date not provided / date ≥ next billable day | Rule_2, 4 verify — **expected consequence of the disclosed `not_persisted` override** (`candidateDateProvided` forced `true`, `candidateDate=0`), documented in `KNOWN_ISSUES.md` |
| Tax Calculation Needed | Rule_1, 3, 4 | No custom field configured / exempt value / other value | Rule_2 verifies |

---

## 4. Have these always been the failing ones?

Honest answer: **only partially checkable from this session's own history** —
a full historical baseline wasn't kept for every rule before today.

**Confirmed changed today**:
- jBilling `Ageing Step Config Validation::Rule_1` — **used to fail** (the
  whole decision was `unresolved`, crashing on an unrelated unused
  `code_external` variable in `Rule_5`'s own dict). **Now verifies**, after
  today's `drd_executor.py` fix. `Rule_2`/`Rule_5` were also blocked by the
  same crash before, but still don't verify now — for a different,
  legitimate reason (their own data never gets constructed / FIRST-policy
  ordering), not the crash.
- FLEX2 `Attendance Eligibility For Final Exam::Rule_1/Rule_2` — **used to
  be untestable at all** (every individual crashed materializing
  `STUDENT_ATTENDANCE` before reaching verification). **Now resolves
  cleanly** but still doesn't verify — flipped from "unknown, blocked" to
  "known, genuinely unmatched."
- All FLEX2 rules that depend on `STUDENT_ATTENDANCE` or the untagged
  `LECTURE` duplicate — same story: previously 0/84 or 78/84 individuals
  could even be tested; now 84/84 can, so today's numbers are the first
  ones that mean anything for this case study.

**Not independently confirmed either way** (no earlier per-rule baseline
was recorded in this conversation to compare against): every OpenMRS rule
in section 3, every Spree rule in section 3 except the ones noted, and
jBilling's `Ageing Status Change Order Action`, `Blacklist Filter Enabled`,
`Tax Calculation Needed` rules. These were flagged as "genuinely open,
not yet root-caused" in `KNOWN_ISSUES.md`'s 2026-09-25 audit entry and
remain in that same state today — consistent with, but not independently
re-proven against, today's fresh run.
