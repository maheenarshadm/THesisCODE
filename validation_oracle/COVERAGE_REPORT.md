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

### 2026-09-25 — jBilling: two real fixes + declared not_persisted overrides (commit `48ed425`)

Two code fixes (see `KNOWN_ISSUES.md`'s jBilling entry for full detail):
`Order Period Already Invoiced`::Rule_3/Rule_4 (a DMN-authoring column
swap, confirmed against `OrderBL.java`'s real `isDateInvoiced()`) and
`Tax Calculation Needed`::`customContactFieldConfigured` (a
`not_persisted` mis-mapping — `pluggable_task_parameter` is a real
table, same class as `purchaseQuantity`/`semesterType`; this one's real
effect is still blocked by a fixture gap, `pluggable_task_parameter`
never materialized).

Separately, confirmed that supplying the ALREADY-ESTABLISHED disclosed
`not_persisted` overrides (`__today__`, used for jBilling's `Invoice
Overdue Check` since the `today()` fix; `candidateDateProvided`/
`candidateDate`, needed by the Rule_3/Rule_4 fix above) at coverage-run
time — no new code — closes 2 more decisions outright:

Invocation: `coverage.py --db tests/fixtures/jbilling_merged.db
--case-study jBilling --algorithm dynamosa_nsga2 --construction-strategy
merged_archive --archive-pickle generator/experiment_runs/
jBilling__dynamosa_nsga2__budget1x__seed0.pkl --not-persisted-json
'{"__today__": 20000, "candidateDateProvided": true, "candidateDate": 0}'`

| | Before (no override) | After (combined override) |
|---|---:|---:|
| verified_covered_rules | 10 | **14** |
| unresolved_decisions | 10 | **8** |
| verified_rule_coverage_percent | 25.6% | 35.9% |

Rule-level: `Invoice Overdue Check`'s both rules flip `false_positive`
→`confirmed` (real: `invoice.due_date` vs. the fixed `__today__=20000`
constant, same value used everywhere else in this project).
`Order Period Already Invoiced::Rule_2` flips `false_positive`→
`confirmed`; `Rule_4` flips `agreed_uncovered`→`false_negative` (a real,
honest finding that the search itself never explored this branch, not a
validator bug — `candidateDate=0 < next_billable_day=1` matches
`OrderBL.java`'s real semantics); `Rule_3` stays `false_positive` under
this particular `candidateDate=0` choice (the fixture's only real
`next_billable_day` value is `1`, never satisfying `>=`) — the same open
"one fixed value can't hit every branch" methodology question
`evaluationTime` already carries, not a new gap. `Tax Calculation
Needed`'s 4 rules stay `false_positive` (blocked by the fixture gap
above, unaffected by these overrides).

OpenMRS/Spree/FLEX2 untouched by this round (jBilling-only overrides).
Full regression suite re-run and passing (see the commit's own message).

### 2026-09-25 — generator subject wiring verification (Codex)

Baseline commit: `6a9b80151d277e2958ac90a3146919758b45007d`.
Same saved `generator/experiment_runs/<CaseStudy>__dynamosa_nsga2__budget1x__seed0.pkl`
archives before/after; baseline committed fixtures versus rebuilt fixtures using
`tests/build_fixture_from_generator.py:build`. Coverage invoked with
`algorithm=dynamosa_nsga2`, `construction_strategy=merged_archive`, archive
comparison enabled and **no not_persisted overrides in either pass**.

| Case study | Before verified | After verified | Rule-set changes | Schema valid |
|---|---:|---:|---|---|
| FLEX2 | 36/55 (65.5%) | 37/55 (67.3%) | Summer Semester Registration Rule_1 added; none removed | Yes |
| OpenMRS | 42/71 (59.2%) | 42/71 (59.2%) | None | Yes |
| Spree | 16/31 (51.6%) | 16/31 (51.6%) | None | Yes |
| jBilling | 10/39 (25.6%) | 10/39 (25.6%) | None | Yes |

FLEX2 rows: 1853 -> 1869; unresolved decisions remain 2; DMN validation valid.
Summer: 0/5 -> 1/5. FLEX2 solvable-rule coverage under the existing denominator:
37/53 = 69.8%. Only the FLEX2 rebuilt fixture is committed. Spree's 16 here must
not be silently compared with historical 18 from differently configured runs;
this is an explicitly no-override regression comparison, not a correction to
that older experiment. The latest handoff headline takes precedence over older
FLEX2 counts below.

Separate diagnostic, not the saved experiment: all five summer objectives
refreshed with `solve_branch` defaults and `random.Random(0)` per rule, replacing
only their entries in a scratch copy of the saved archive. Rule fitness values
were 0, 0.5, 0, 0, 0.5. Rebuilt scratch database: 1709 rows, 36/55 verified,
96/98 search-covered objectives, 3 unresolved decisions, schema/DMN valid.
Its verified-rule set exactly matches the 36-rule baseline. Missing EMPLOYEE
causes the oracle to refuse the whole summer decision, even though Rule_1's
individual search succeeds. This diagnostic was NOT promoted to the fixture
or mislabeled as a fresh DynaMOSA experiment. See KNOWN_ISSUES.md.

Reproduce the primary result by rebuilding FLEX2 from the unchanged archive
with `build_fixture_from_generator.build`, then using the coverage command in
QUICK_REFERENCE.md with no `--not-persisted-json`. Run
`python generator/test_decision_subject.py` for the focused regression tests.


**As of the 2026-09-25 `Summer Semester Registration` three-part fix**
(`subject_root_overrides.py` [new] + a `raw_sql_boolean` executor bug fix
+ `derived_aggregate`'s `filter_text: None` now raises `UnresolvableForCase`
instead of crashing, all built on request) — verified-rule counts are
UNCHANGED (still FLEX2 36; confirmed via a full per-rule before/after
diff of `objective_results.csv`, zero flips anywhere). What changed:
`Summer Semester Registration` is no longer an "unresolved decision" —
it now resolves its subject (`COURSE_REGISTRATION`, via a new kind of
disclosed root-tiebreak override) and runs `run_decision` end to end
without crashing, but is honestly 0/5 verified: `Rule_1` needs a
`course_type_id = 'RESEARCH'` registration that doesn't exist among the
545 real rows in this fixture; `Rule_2`'s own conditions aren't jointly
true for any of them; `Rule_3`/`Rule_4`/`Rule_5` stay ungrounded on
`repeatCourseCountRequested`, a real correlation gap (its ground truth's
"per USER_ID" doesn't even trace to a student in the schema) left
disclosed rather than guessed. One side effect: `Attendance Eligibility
For Final Exam`'s own unresolved reason changed (same table lookup, `<this
course offering>`, now resolves partway before hitting an unrelated
`<student>` gap) — same 0/2 verified outcome, confirmed via the same
diff. See `KNOWN_ISSUES.md`'s own entry for the full three-part writeup.

**As of the 2026-09-25 `AGGREGATE_FOR_CORRELATION_RE` compile-time fix**
(`compile_constraints.py`, built on request as "option 2" — a general
parser fix, not a one-off override) — FLEX2 33→36 verified rules
(60.0%→65.5% raw, 62.3%→67.9% solvable), decision-table coverage
6/10→7/10. Closes the compile-time gap the composite-join fix below had
surfaced: ground truth's own "for COL"/"for COL1+COL2" correlation
phrasing (`variable_to_schema_mapping.csv`) was never recognized by
`_try_extract_aggregate_recipe`, leaving `filter_text: null` for 7
records corpus-wide (confirmed via an order-independent diff of the
whole recompiled `compiled_constraints.json` — exactly these 7 changed,
nothing else). `Graduation Eligibility` jumps from 0/5 to **3/5 verified**
(`Rule_1`/`Rule_2`/`Rule_3`); `Rule_4`/`Rule_5` don't verify for a
confirmed ordinary data-coverage reason (hit policy `FIRST`, and all 148
real `STUDENT_PROGRAM` rows in the fixture already match an earlier
rule — none reaches the catch-all). `Summer Semester Registration` is
unchanged (its own separate `<this course offering>` blocker is
untouched by this fix). Full `coverage.py` re-run confirms zero flips
anywhere else in FLEX2 or in OpenMRS/Spree/jBilling.

**As of the 2026-09-25 composite-key join fix** (`schema_utility.
composite_backward_edges`, built on request for `Graduation
Eligibility`) — FLEX2 32→33 verified rules (58.2%→60.0% raw, 60.4%→62.3%
solvable), decision-table coverage 5/10→6/10. `Course Registration
Eligibility::Rule_1` newly confirmed, as a side effect of the SAME shared
mechanism (`Rule_2`/`Rule_3`/`Rule_4` remain unverified for an ordinary
data-coverage reason, not a validator bug). `Graduation Eligibility`'s
own join-mechanism limitation is genuinely fixed (root now resolves
cleanly to `STUDENT_PROGRAM` with a real composite join to
`BATCH_PROGRAM`), but running it through `run_decision` immediately
surfaces a SEPARATE, previously-unreachable compile-time bug
(`semestersElapsed`'s own `derived_aggregate` node has `filter_text:
null` despite its `source_text` describing a real subject correlation) —
still 0/5 verified for this decision; see `KNOWN_ISSUES.md`'s own entry
for the full writeup. Full `coverage.py` re-run confirms zero flips
anywhere else in FLEX2 or in OpenMRS/Spree/jBilling (identical
`validation_summary.csv` for all three).

**As of the 2026-09-25 `subject_table.py` extractor fixes** (`derived_
join_count`/`raw_sql_boolean`) — see "Run history" below for the full
writeup. Tables above already reflect this: FLEX2 31→32 verified rules
(56.4%→58.2% raw, 58.5%→60.4% solvable), decision-table coverage
4/10→5/10 — `Credit Transfer Exemption` now fully resolved (1/3
verified). `Course Registration Eligibility` and `Summer Semester
Registration` each moved past subject-picking into a different, more
precisely diagnosed but still-open gap; zero flips anywhere else in
FLEX2 or in OpenMRS/Spree/jBilling.

**As of the 2026-09-25 subject-hop placeholder correlation fix** — FLEX2
30→31 verified rules (54.5%→56.4% raw, 56.6%→58.5% solvable) — `Course
Replacement Eligibility::Rule_4` newly confirmed, closing this decision
fully at 6/6; zero flips anywhere else in FLEX2 or in
OpenMRS/Spree/jBilling.

**As of the 2026-09-24 cross-table filter_text placeholder fix** —
FLEX2 29→30 verified rules (52.7%→54.5% raw, 54.7%→56.6% solvable) —
`Course Replacement Eligibility::Rule_3` newly confirmed; zero flips
anywhere else in FLEX2 or in OpenMRS/Spree/jBilling.

**As of the 2026-09-24 `dynamosa.py` junction-row wiring fix** — FLEX2
28→29 verified rules (50.9%→52.7% raw, 52.8%→54.7% solvable) —
`Course Replacement Eligibility::Rule_1` newly confirmed, and
`creditsEarned` now correctly resolves for `Rule_3`/`Rule_4`/`Rule_5`;
zero flips anywhere else in FLEX2 or in OpenMRS/Spree/jBilling.

**As of the 2026-09-24 `Course Replacement Eligibility` placeholder fix**
— see "Run history" below for the full writeup. FLEX2 25→28 verified
rules (45.5%→50.9% raw, 47.2%→52.8% solvable), decision-table coverage
3/10→4/10 (`Rule_2`/`Rule_5`/`Rule_6` newly confirmed); OpenMRS/Spree/
jBilling unchanged (confirmed by a full per-objective diff, not just
totals).

**As of the 2026-09-24 `run_decision`/`rule_evaluator.py` three-bug fix
(FLEX2's `Course Load Limit`, 0/11 → 11/11 confirmed)** — see "Run
history" below for the full writeup and `KNOWN_ISSUES.md`'s
cross-case-study entry for the root-cause detail. FLEX2 21→25 verified
rules (38.2%→45.5% raw, 39.6%→47.2% solvable), decision-table coverage
2/10→3/10; OpenMRS/Spree/jBilling unchanged (confirmed by a full
per-objective diff, not just totals).

**As of the 2026-09-24 Spree IN-subquery/merge-offsetting round (after
`f8a64150`), covering:** the two root-cause fixes for the 8 Spree rules
the search claimed but the validator couldn't confirm --
(A) `COLUMN IN (SELECT ... WHERE ...)` filter construction, previously
entirely unrecognized by the mechanical row-builder (new
`_construct_subquery_parent`/`aggregate_self_table.py` disclosed `self`
override, closes `Promotion Usage Limit Exceeded` 3/4 and `One-Use-Per-
User Promotion Eligibility::rule_3`), and (B) a real schema-extraction
gap (`spree_discounts.fk_columns` was `[]` despite every column being a
real FK) that broke `dynamosa.py`'s own merge-time key-offsetting
consistency between a row and its own FK-referencing rows. Fixing (B)
surfaced a third, previously-masked bug: `materialize.py`'s
`to_sql_inserts`/`validate_with_sqlite` left any row missing its own
table's single surrogate key for SQLite's own NULL-rowid auto-assignment
to fill in -- silently collision-prone against this pipeline's own
explicit, offset-derived ids in the same table once those ids and
SQLite's own lazy auto-rowid sequencing could actually intersect (they
hadn't before (B) was fixed). Fixed by `_fill_missing_surrogate_keys`:
every id-less row now gets an explicit, collision-free id computed with
full knowledge of every id already used in that table, before any INSERT
runs at all. Full before/after diff across all 4 case studies confirmed
this shared `materialize.py` fix reproduces OpenMRS/FLEX2/jBilling's
already-recorded numbers below exactly (they were unaffected in the end
-- see Run history for the one intermediate false alarm this produced
against a stale `coverage_out/` artifact) and moves Spree from 14 to 18
verified -- all 8 of the originally-unverified-but-search-claimed rules
now confirmed, after a follow-up fix closed the one that remained
(`Promotion Usage Limit Exceeded::rule_3`; see the "promotion_actions FK
gap" Run history entry below).

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
| OpenMRS | 71 | 71 | 42 | 59.2% |
| Spree | 31 | 31 | 18 | 58.1% |
| FLEX2 | 98 | 55 | 36 | 65.5% |
| jBilling | 40 | 39 | 10 | 25.6% |
| **Total** | **240** | **196** | **106** | **54.1%** |

### Solvable-rules coverage (excludes rules that are structurally not
reachable by data generation at all — see category definitions below;
all counts are DISTINCT DMN rules)

| Case study | Distinct rules | Not solvable | Undetermined | Solvable | Verified | Solvable coverage |
|---|---|---|---|---|---|---|
| OpenMRS | 71 | 15 | 0 | 56 | 42 | 75.0% |
| Spree | 31 | 9 | 0 | 22 | 18 | 81.8% |
| FLEX2 | 55 | 0 | 2 | 53 | 36 | 67.9% |
| jBilling | 39 | 3 | 21 | 15 | 10 | 66.7% |
| **Total** | **196** | **27** | **23** | **146** | **106** | **72.6%** |

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

**Investigated 2026-09-24, root cause CORRECTED then fixed the same
day (see `KNOWN_ISSUES.md`'s cross-case-study entry for the full
writeup, including the retracted first diagnosis).** The "Course Load
Limit 0/4" finding above turned out to affect all 57 compiled records
corpus-wide using the `literal_via_upstream_branch` kind (55 FLEX2, 2
jBilling) -- all `search_covered=True`, `verified=False`. First
suspected the search's own fitness function never enforced the upstream
rule's condition; that was WRONG -- `compile_constraints.py` already
splices it in correctly at compile time, confirmed by inspecting the
actual compiled condition. The REAL bug: `drd_executor.py`'s
`upstream_subject_value` compared schema-cased column names
(`ROLL_NO`) against a row dict whose real keys are lowercase
(`roll_no`) with no `.lower()` -- the same normalization
`db_resolver.py`'s own single-decision join code already does, just
missing from this newer cross-decision copy of the same pattern. Every
lookup silently returned `None`, misreported as "no corresponding
upstream row." Fixed (2 lines, `drd_executor.py`); verified directly
against real FLEX2 data that every previously-`None` lookup now
resolves a real upstream rule. That fix unmasked a second, separate,
previously-unreached gap: the validator never implemented the
`derived_case` resolution kind at all (33 FLEX2 records use it,
including `Course Load Limit`'s own `semesterType`) -- implemented the
same day, a direct port of `candidate.py`'s own handling. **Net effect
on the numbers above: none of the case-study totals move** -- FLEX2
stays 21 verified, jBilling stays 10 (its own 2 chained records were
never reachable through this code path at all, blocked earlier by an
unrelated, pre-existing gap). What DID change, confirmed via a fresh
coverage.py run: `Course Load Limit` moved out of `unresolved_decisions`
entirely (FLEX2's own count: 8 -> 7) -- every one of its 11 objectives
is now genuinely, fully evaluated (real resolved inputs, a real
rule-selection attempt) for the first time, rather than failing before
ever reaching that point. It's still 0/11 verified, but now for a real,
disclosed reason: the handful of real subjects whose upstream branch
genuinely matches still don't satisfy Course Load Limit's own condition
with their other 3 leaves (`semesterType`/`cumulativeGPA`/
`priorWarningCount`) simultaneously -- a genuine, separate,
generator-side construction gap, not a validator bug; not pursued
further as part of this investigation. Full regression suite re-run and
passing after both fixes.

**That "generator-side construction gap" was investigated further and
partially fixed 2026-09-24 (see `KNOWN_ISSUES.md`'s cross-case-study
entry for the full writeup).** Checked every decision in every case
study for the same shape (a real, unique DMN subject the generator's
own leaf-driven focal-row logic never builds) and found it in exactly
2: FLEX2's `Course Load Limit` and OpenMRS's `Identifier Uniqueness
Check` (a third suspect, Spree's `Promotion Customer Group
Eligibility`, turned out on deeper investigation to be a genuine
one-to-many backward-join gap instead, once a real bug in
`subject_table.py` itself was found and fixed -- see below). Built the
fix as `compile_constraints.py`'s own new `decision_subject` compile-
time field (a generator-owned, narrower-scoped port of
`subject_table_for_decision`'s algorithm, chosen over importing it
directly to preserve `DESIGN.md`'s "no overlap in function calls with
the search approach" in both directions) plus a new merge-time
consumer in `dynamosa.py`'s `merge_archive_candidate` that constructs
the missing subject row once, after search, with real FK links to the
SAME already-solved focal rows -- no search-loop/fitness change at all.

Verifying this surfaced two more real, independent bugs, both fixed the
same day: `subject_table.py`'s own `substituted_decision` handling was
dead code (listed in a set checked before its own dedicated recursion
branch, so it never actually ran -- confirmed load-bearing, not
cosmetic, for Spree's `Promotion Customer Group Eligibility::rule_4`);
and `fitness.py`'s `_unique_key_sets` did a case-SENSITIVE schema
lookup, unlike its own caller one line earlier -- invisible until this
fix needed multiple same-table fresh-PK repairs in one pass for the
first time, at which point it silently handed OpenMRS's own
`PATIENT_IDENTIFIER` rows an identical, colliding placeholder id.

**Verified result** (fresh per-objective before/after diff across all 4
case studies, not just totals, after re-running the Spree search --
needed since fixing the second bug also required a third instance of
this session's own `fk_columns: []` schema gap, in
`spree_order_promotions`/`spree_promotion_rules` -- and rebuilding every
fixture): **OpenMRS 41->42 verified** (`Identifier Uniqueness
Check::rule_1` flips false_positive -> confirmed), zero flips anywhere
else in OpenMRS, and zero flips in FLEX2/Spree/jBilling.
`Course Load Limit` was STILL 0/11 at this point -- the junction row now
genuinely existed and correctly cross-referenced the same objective's
other rows (confirmed directly), attributed at the time to a
"composite-leaf value alignment" gap -- **RETRACTED same day**, see the
"run_decision/rule_evaluator.py three-bug fix" entry at the top of "Run
history" below: the real cause was three validator bugs, fixed the same
day, bringing this decision to 11/11. Full self-test suite re-run and
passing.

### Per-case-study provenance (fixture / archive / invocation used to
produce the numbers above)

- **OpenMRS**: `tests/fixtures/openmrs_merged.db` (rebuilt 2026-09-24
  after the `decision_subject` junction-row fix and the `fitness.py`
  `_unique_key_sets` casing fix -- see "Latest snapshot" above),
  `generator/experiment_runs/OpenMRS__dynamosa_nsga2__budget1x__seed0.pkl`,
  no `--not-persisted-json`.
- **Spree**: `tests/fixtures/spree_merged.db` (rebuilt 2026-09-25 after
  the subject-hop placeholder correlation fix above -- gains one extra
  `spree_order_promotions` row for `Promotion Customer Group
  Eligibility`'s own already-unresolved decision, confirmed harmless;
  originally rebuilt 2026-09-24 after the IN-subquery construction
  mechanism, `spree_discounts.fk_columns` schema fix, and the
  `materialize.py` surrogate-key fill fix -- see "Latest snapshot"
  above), `generator/experiment_runs/
  Spree__dynamosa_nsga2__budget1x__seed0.pkl` (re-run to pick up the
  IN-subquery mechanism), `--not-persisted-json`
  `{"evaluationTime": 20000}`.
- **FLEX2**: `tests/fixtures/flex2_merged.db` (rebuilt 2026-09-25 after
  the subject-hop placeholder correlation fix above), `generator/
  experiment_runs/FLEX2__dynamosa_nsga2__budget1x__seed0.pkl`, no
  override.
- **jBilling**: `tests/fixtures/jbilling_merged.db`,
  `generator/experiment_runs/jBilling__dynamosa_nsga2__budget1x__seed0.pkl`,
  no override.

All 4 runs used `--algorithm dynamosa_nsga2 --construction-strategy
merged_archive`. Decision-table coverage (≥1 rule verified per
decision, COLLECT decisions excluded): OpenMRS 14/14 (100%), Spree 6/8,
FLEX2 4/10 (previously 2/10; `Course Load Limit` and `Course Replacement
Eligibility` newly covered — see the two 2026-09-24 entries in Run
history below), jBilling 6/16.

---

## Run history

### 2026-09-25 — subject_table.py extractor fixes (closes `Credit Transfer Exemption` fully; re-diagnoses two more)
Numbers: FLEX2 31->32 verified rules (56.4%->58.2% raw, 58.5%->60.4%
solvable), decision-table coverage 4/10->5/10. Investigating FLEX2's
remaining 5 "backward-join" refusals found they were never one category:
2 (`Course Registration Eligibility`, `Credit Transfer Exemption`) were a
real, shared compile-time bug; the other 3 are genuinely distinct gaps.

`subject_table.py`'s own `_TABLE_EXTRACTORS['derived_join_count']`
unconditionally required BOTH `prereq_table` and `registration_table` to
be forward-reachable from the subject. But `db_resolver.resolve()`'s own
`derived_join_count` branch queries `prereq_table` via a raw,
UNCORRELATED scan (`SELECT COUNT(*) FROM "COURSE_PREREQ" p WHERE NOT
EXISTS (...)`, no WHERE binding on `p` from the subject at all) -- the
SAME "self-contained, no join path needed" shape `derived_aggregate`/
`exists` were already exempted for, never extended to this kind. Fixed
by dropping `prereq_table`, keeping only `registration_table` (which
`resolve()`'s own runtime check requires be the subject itself, via
`registration_roll_column`). Confirmed corpus-wide: `derived_join_count`
is used only by these two decisions -- zero collateral anywhere else.

Verified: both decisions now resolve to `COURSE_REGISTRATION` via
`subject_table_for_decision`. `Credit Transfer Exemption` is now fully
resolved AND verified 1/3 (`Rule_3` flips false_positive->confirmed).
`Course Registration Eligibility` moved past subject-picking but hit a
DIFFERENT, deeper gap: it chains to `Course Load Limit` (subject
`STUDENT_SEMESTER`, composite PK `[SEM_ID, ROLL_NO]`) via
`literal_via_upstream_branch`, and `DecisionRunner.upstream_subject_
value`'s own single-continuous-FK-chain join-path builder can't express
that `COURSE_REGISTRATION` already has BOTH of `STUDENT_SEMESTER`'s own
composite-PK columns directly (a genuinely unambiguous correspondence,
just not expressible as one hop chain) -- not yet fixed, needs a real
new capability, not a one-line extractor change.

Testing the SAME idea against `_TABLE_EXTRACTORS['raw_sql_boolean']`
(the same over-strict shape, confirmed used only by FLEX2's `Summer
Semester Registration`) found and fixed a second real bug the same way
(mirroring `derived_aggregate`'s own extractor). This resolves subject-
picking to `COURSE`, but running `coverage.py` shows it just trades one
refusal for a more precise one: a `<this course offering>` placeholder
needs `offer_id`, not on `COURSE`. Tested a `filter_placeholder_
sources.py` override pointing it at `COURSE_OFFER` -- this does NOT
cleanly resolve either: `COURSE_OFFER`, `COURSE_REGISTRATION`, and
`REPEAT_COURSE` all independently qualify as valid roots once
`COURSE_OFFER` is required too, a genuine 3-way ambiguity needing a
domain-informed disambiguation decision. That override was reverted, not
committed; the `raw_sql_boolean` extractor fix itself was kept (correct
and independently justified, zero side effects, even though it alone
doesn't verify anything new for this decision yet).

The other 2 of the original 5 are genuinely distinct, deeper gaps, not
bugs: `Admission Closure Eligibility`'s own `ADM_MERIT_LIST` has NO
primary key or foreign key declared anywhere in the real DDL (confirmed
directly against `schemas/flex2/Flex1.sql`) -- no relationship exists to
disclose an override for at all. `Graduation Eligibility`'s own
`STUDENT_PROGRAM.(BATCH_NO, PROG_ID)` jointly correspond exactly to
`BATCH_PROGRAM`'s own composite PK, but the schema only captured them as
two separate single-column FKs, and this project's own join-path builder
is deliberately scoped to single-column hops only -- closing this needs
a genuinely new composite-join capability.

Verified via a full `subject_table_for_decision` sweep across every
decision in all 4 case studies (zero collateral) and a full per-objective
`coverage.py` diff (exactly one flip: `Credit Transfer Exemption::
Rule_3`). Full regression suite re-run and passing; no fixture rebuild
needed (`subject_table.py` never touches the generator/search/merge
pipeline).

### 2026-09-25 — subject-hop placeholder correlation fix (closes `Course Replacement Eligibility::Rule_4`, decision now 6/6)
Numbers: FLEX2 30->31 verified rules (54.5%->56.4% raw, 56.6%->58.5%
solvable), decision-table coverage unchanged at 4/10. `Rule_4`'s own
`courseOfferedInFollowingSemesters` (an `exists` check needing a second
`COURSE_OFFER` row for the same subject's own `COURSE_ID`) resolved
`False` for every one of the 545 real subjects -- the SAME bug SHAPE as
`Rule_3`'s own fix the day before, mirrored within one table pair
instead of across two: `COURSE_OFFER.COURSE_ID` correctly tracks
`scenario['COURSE_ID']` throughout search (both shift together under
the SAME per-record offset), while the SAME record's own
`COURSE.COURSE_ID` -- never independently set by any leaf -- only ever
gets a value from a global, cross-record fresh-key repair, unrelated to
either. Unlike `<program>`/`<batch>`, the validator never even reaches
`filter_placeholder_sources.py` for `<COURSE_ID>`: it resolves directly
off the subject row's own `course_id` column (already wired to
`COURSE.COURSE_ID` by the earlier junction-row fix), so the gap is
purely generator-side.

Extended `compile_constraints.py`'s own `cross_table_placeholders` field
with a second compile-time source: a conjunct whose own column matches
the decision's own subject row's real FK column (per `decision_subject
['joins']`) needs no declared override at all -- the target table/column
is read straight off that hop. Reordered `dynamosa.py`'s own consumption
to run BEFORE the subject-junction wiring step (not after, as the
2026-09-24 version did): for this shape the correlated table (`COURSE`)
is the SAME one a subject hop reads FROM, so the correction must land
before that hop is wired. Also taught the consumer to synthesize the
correlated row when none exists yet.

A genuine collision surfaced verifying this: `degreeTotalCredits`'s own
`derived_aggregate` seeding independently builds 3 of its OWN separate
`COURSE` rows for the SAME record (numbered 1,2,3 pre-offset, the same
starting point `<COURSE_ID>`'s own scenario default uses) -- after the
identical per-record offset, the correlated row and the first of those 3
rows landed on the identical `COURSE_ID`, a real `UNIQUE constraint
failed` reproduced directly rebuilding the fixture. Fixed by checking,
after writing the correlated value, whether it's now a genuine PK/UNIQUE
collision with a DIFFERENT row this record owns, and if so bumping that
OTHER row to a fresh, collision-safe value via `mutation.py`'s own
`_fresh_key_value`.

Verified via a full per-objective before/after diff across all 4 case
studies: `Rule_4` flips false_positive->confirmed, `Course Replacement
Eligibility` now fully 6/6; zero flips anywhere else (Spree's fixture
also gained rows here -- the same consumer's new row-synthesis behavior
building an extra `spree_order_promotions` row for `Promotion Customer
Group Eligibility`'s own already-unresolved decision -- confirmed
harmless: Spree's own `objective_results.csv` is byte-identical before
and after). Full regression suite re-run and passing.

### 2026-09-24 — cross-table filter_text placeholder correlation fix (closes `Course Replacement Eligibility::Rule_3`)
Numbers: FLEX2 29→30 verified rules (52.7%→54.5% raw, 54.7%→56.6%
solvable), decision-table coverage unchanged at 4/10. `Rule_3`'s own
`degreeTotalCredits` needed `PROGRAM_COURSE.PROG_ID=<program> AND
.BATCH_NO=<batch>` to correlate with the SAME record's own
`STUDENT_PROGRAM.PROG_ID`/`.BATCH_NO` -- nothing in the search pipeline
ever made that connection.

**Correction to the prior investigation's own diagnosis, same day**: the
earlier writeup guessed `PROGRAM_COURSE.PROG_ID=64000001` came from
`repair_candidate`'s generic NOT-NULL fallback (implying the seeded
conjunct was silently skipped). Checking the raw, pre-merge
`scenario_map` directly showed this was wrong: `scenario['program']` is
ALSO `64000001` for that record -- `candidate.py`'s own seeding and
`PROGRAM_COURSE.PROG_ID` stay perfectly self-consistent throughout
seeding, search, and merge-time offsetting (both shift together under
the identical per-record offset). `candidate.py` was never actually
broken. The REAL gap: `STUDENT_PROGRAM.PROG_ID`/`.BATCH_NO` are never
independently set by any leaf (`creditsEarned` only reads
`credits_earned`, no placeholder involved) -- they only ever get a value
from `mutation.py`'s own `_repair_row` generic NOT-NULL fallback, a
plain constant `1`, completely unrelated to `scenario['program']`'s own
value. Neither `candidate.py`'s seeding/mutation nor `fitness.py`'s
evaluation ever cross-references a live `STUDENT_PROGRAM` row for this
placeholder -- both only ever compare it against the flat
`scenario['program']` scalar.

Fixed at merge time (`dynamosa.py`, same layer as the `decision_subject`
junction-row fix -- a post-search correction, not a search-loop/
fitness/mutation change): a new compile-time field,
`compile_constraints.py`'s `cross_table_placeholders` (reusing its own
`_DECISION_SUBJECT_PLACEHOLDER_SOURCES` mirror of
`filter_placeholder_sources.py`, now also carrying FLEX2's `program`/
`batch` entries), attached to each `derived_aggregate`/`exists` node
with such a placeholder. `merge_archive_candidate` copies the record's
own (already-offset) `scenario[placeholder]` value onto the correlated
table's own focal row/column before `repair_candidate` runs, so its
later generic fallback never fires for it. Only applied when a focal row
for the correlated table already exists.

Verified via a full per-objective before/after diff across all 4 case
studies (code-only difference, `compiled_constraints.json` re-diffed
field-by-field: only the new field, on exactly 6 nodes): `Rule_3` flips
false_positive->confirmed; zero flips anywhere else. `Rule_4` still
doesn't verify -- a separate, unrelated, not-yet-investigated reason
(`courseOfferedInFollowingSemesters` resolves `False` for every real
subject; `Rule_4`'s own condition never references `degreeTotalCredits`
at all). Full regression suite re-run and passing.

### 2026-09-24 — `dynamosa.py` decision_subject junction-row wiring fix (two bugs)
Numbers: FLEX2 28→29 verified rules (50.9%→52.7% raw, 52.8%→54.7%
solvable), decision-table coverage unchanged at 4/10. Investigating why
`Course Replacement Eligibility::Rule_1` still didn't verify after the
placeholder fix below found two bugs in `dynamosa.py`'s own
`decision_subject` junction-row builder (from the earlier 2026-09-24
`Course Load Limit`/`Identifier Uniqueness Check` fix), both fixed the
same day:

1. The builder only ever ran when the subject table was completely
   absent from a record's own focal rows -- it never synthesized a
   missing SIBLING row a hop needed to link through. `Rule_1`'s own
   solved candidate has a dedicated `COURSE` row (for `courseTypeId`)
   but no `STUDENT_PROGRAM` row at all (nothing in `Rule_1`'s own
   condition needs it), yet the subject (`COURSE_REGISTRATION`)
   structurally needs both -- so the whole junction row was silently
   abandoned. Fixed: synthesize a fresh, minimal row for a missing hop
   target instead of aborting; `repair_candidate`, called right after,
   fills in whatever else it still needs.
2. Checking `Rule_3`/`Rule_4` (same decision/subject) after fixing (1)
   found a second, related gap: the fix only fired when the subject row
   was missing ENTIRELY, but it can already exist (built naturally by
   ANOTHER leaf, e.g. `Rule_3`'s own `gradeInCourseToReplace` on
   `COURSE_REGISTRATION`) while a DIFFERENT leaf of the SAME record
   builds its own separate row on a table the subject needs to link
   through (e.g. `creditsEarned` on `STUDENT_PROGRAM`) -- and nothing
   ever wired the subject's own FK column to that sibling row's PK,
   since the whole block was skipped once the subject was already
   present. Fixed by always attempting to wire every `subject['joins']`
   hop onto the subject row (new or pre-existing), skipping only a hop
   whose own FK column already has a real value.

Verified via a full per-objective before/after diff across all 4 case
studies: `Rule_1` flips false_positive->confirmed; zero flips anywhere
else. `creditsEarned` now correctly resolves the real per-subject value
for `Rule_3`/`Rule_4`/`Rule_5` (confirmed in `decision_trace.json`:
1/32/32/18 instead of `None`), but `Rule_3`/`Rule_4` themselves still
don't verify -- root-caused to a THIRD, distinct, generator-side bug:
`degreeTotalCredits`'s own filter_text placeholders (`<program>`/
`<batch>`) only resolve via a join to `STUDENT_PROGRAM`, but
`candidate.py`'s own `_row_from_filter_conjuncts` (which seeds
`PROGRAM_COURSE`'s rows during search) has no equivalent mechanism --
confirmed directly against the pre-merge archive: `Rule_3`'s own
`PROGRAM_COURSE` rows get `PROG_ID=BATCH_NO=64000001` (a fresh-key
fallback) while its own sibling `STUDENT_PROGRAM` row gets
`PROG_ID=BATCH_NO=1` -- never unified, even before merge/offset. See
`KNOWN_ISSUES.md`'s own entry for the fix this would need (not yet
built). Full regression suite re-run and passing.

### 2026-09-24 — `Course Replacement Eligibility` filter_text placeholder fix (partial)
Numbers: FLEX2 25→28 verified rules (45.5%→50.9% raw, 47.2%→52.8%
solvable), decision-table coverage 3/10→4/10. `degreeTotalCredits`'s own
compiled `derived_aggregate` reads `PROGRAM_COURSE.PROG_ID=<program> AND
PROGRAM_COURSE.BATCH_NO=<batch>` -- neither `prog_id` nor `batch_no` is a
column on this decision's own subject row (`COURSE_REGISTRATION`), the
same shape as Spree's already-solved `Promotion Customer Group
Eligibility::promotion_id` gap. Confirmed both are real columns on
`STUDENT_PROGRAM`, reachable via `COURSE_REGISTRATION.ROLL_NO`'s own
real forward FK to `STUDENT_PROGRAM.ROLL_NO`. Fixed with two new
`filter_placeholder_sources.py` entries (`('FLEX2', 'program')`,
`('FLEX2', 'batch')`, both `'STUDENT_PROGRAM'`) -- no new mechanism, the
join-aware placeholder resolver built for Spree already handles this
generically.

Surfaced a second, independent, previously-unreached bug in
`db_resolver.py`'s own `derived_aggregate` SQL construction:
`degreeTotalCredits`'s own `table` field is a real, old-style
implicit-join LIST (`"PROGRAM_COURSE, COURSE"`, the join condition
itself already living in `filter_text`'s own WHERE clause), but the SQL
builder quoted the WHOLE string as ONE identifier, raising `no such
table: PROGRAM_COURSE, COURSE` the moment resolution actually reached it
(this decision's own placeholder gap had always intercepted it first).
Confirmed via corpus query: the only `derived_aggregate` record anywhere
with a comma in `table`. Fixed by quoting each comma-separated table
name individually, and keeping `value_column` fully qualified rather
than stripped to a bare column name (costs nothing for the existing
single-table case -- checked against jBilling's own
`ageing_entity_step.days`, unaffected -- but is necessary once `table`
names more than one).

Verified via a fresh per-objective before/after diff across all 4 case
studies (code-only difference): `Rule_2`/`Rule_5`/`Rule_6` flip
`false_positive`->`confirmed`; zero flips anywhere else in FLEX2 or in
OpenMRS/Spree/jBilling. This decision's own `Rule_1`/`Rule_3`/`Rule_4`
remain unverified -- ALL 544 real subjects resolve `courseTypeId`/
`creditsEarned`/`degreeTotalCredits`/`courseOfferedInFollowingSemesters`
to the exact same value with zero variation (`None`/`None`/`None`/
`False`) -- not a resolution bug (the underlying columns DO have real
non-null values elsewhere in the database, just never on a row any real
`COURSE_REGISTRATION` subject actually joins to; `program_course` has
only 9 real rows total). A separate, disclosed, not-yet-investigated
gap -- see `KNOWN_ISSUES.md`'s FLEX2 section. Full regression suite
re-run and passing.

### 2026-09-24 — `run_decision`/`rule_evaluator.py` three-bug fix (closes FLEX2's `Course Load Limit`)
Numbers: FLEX2 21→25 verified rules (38.2%→45.5% raw, 39.6%→47.2%
solvable), decision-table coverage 2/10→3/10. `Course Load Limit`'s own
0/11 result (previously attributed, wrongly, to a generator-side
"composite-leaf value alignment" gap — see `KNOWN_ISSUES.md`'s explicit
retraction of that diagnosis) turned out to be three compounding
validator-side bugs in `drd_executor.py`/`rule_evaluator.py`:

1. `run_decision` merged every DRD-fan-out variant of a decision (several
   compiled records can share one `rule_id` with DIFFERENT own
   `condition`/`variable_resolution` — one per upstream branch, via
   `compile_constraints.py`'s `_grounding_options`) into ONE dict via
   `dict.update()`, silently keeping only the LAST-processed variant's
   own definition for any variable name shared across variants —
   `Course Load Limit::Rule_4` alone has 6 such variants.
2. No per-subject/per-variant isolation around a resolution failure other
   than `UngroundedForCase` — `derived_case` hitting a real column value
   uncovered by any declared case raised a plain `NotImplementedError`,
   which aborted the WHOLE decision for EVERY subject rather than just
   the one subject that hit it (27 of FLEX2's 39 real `STUDENT_SEMESTER`
   subjects belong to other decisions and have no matching `SEMESTER`
   row at all).
3. `rule_evaluator.evaluate_condition` never implemented `not`/`between`
   (unlike `fitness.py`'s own full support) — 54 compiled records
   corpus-wide use `not` (52 FLEX2, 1 Spree, 1 jBilling), none of which
   could ever have verified regardless of bugs 1/2.

Fixed: (1) `run_decision` restructured to try every variant of a
`rule_id` independently per real subject, a rule counted as matched if
ANY variant both grounds and evaluates true; (2) `db_resolver.py`'s
`derived_case` now raises a new, distinct `UnresolvableForCase`,
translated by `drd_executor.py`'s `_resolve_one` into `UngroundedForCase`
so it is isolated to the one variant/subject it affects, never the whole
decision; (3) `not`/`between` added to `evaluate_condition`, mirroring
`fitness.py`'s own key names exactly.

Verified via a fresh, per-objective before/after diff across all 4 case
studies (identical `coverage.py` invocation, code-only difference):
`Course Load Limit`'s all 4 distinct rule_ids (`Rule_1`–`Rule_4`, 11
compiled objectives) flip `false_positive`→`confirmed`; zero flips
anywhere else — OpenMRS/Spree/jBilling's `objective_results.csv`
agreement classes are byte-identical before and after, across all 240
objectives, not just totals. Full regression suite (`candidate.py`,
`mutation.py`, `materialize.py`, `dynamosa.py`, `subject_table.py`,
`rule_evaluator.py`'s own self-test, `drd_executor.py`'s own OpenMRS
acceptance test, `test_spec_cases.py`, `test_drd_chaining_synthetic.py`,
`test_serialized_field_roundtrip.py`) re-run and passing.

**Separately disclosed, found while establishing the true before/after
baseline, NOT part of this fix:** re-running OpenMRS's coverage on the
PRE-fix code WITH `--not-persisted-json {"evaluationTime": 20000}`
already shows 44 verified rules (`Birthdate Validity::Rule_2`/`Rule_3`
newly confirmed), not the 42 recorded in this file's own tables above —
the original run that produced "42" (see its own provenance note below)
used no `--not-persisted-json` at all. jBilling shows the same shape (12
vs. the recorded 10, with `--not-persisted-json {"__today__": 20000}`).
This is an orthogonal coverage-run methodology question, not touched or
"corrected" here — re-establishing OpenMRS/jBilling's own official
numbers needs its own deliberate, separately-verified pass.

### 2026-09-24 — `spree_promotion_actions.promotion_id` FK gap (closes the last of the original 8)
Numbers: Spree 17→18 verified. `Promotion Usage Limit Exceeded::rule_3`
(the one rule left open after the round below) never had any subject
where `adjustedCreditsCount >= usageLimit` — traced to a THIRD instance
of the same schema-extraction gap: `spree_promotion_actions.fk_columns`
was also `[]` despite `promotion_id` being a real FK to
`spree_promotions.id` (confirmed against `schemas/spree_schema.rb`'s own
`t.bigint "promotion_id"` declaration, same convention-over-configuration
class as the other two Spree FK gaps fixed this session). Symptom before
the fix: `spree_promotion_actions.promotion_id` never got included in
either `_seed_shared_population`'s or `merge_archive_candidate`'s own
key-column offsetting, so it stayed at its raw, pre-offset placeholder
value while the `spree_promotions` row it targets got shifted --
breaking the join `adjustedCreditsCount`'s own filter depends on, so the
validator's real SQL always found 0 matching `spree_discounts` rows
regardless of how many were actually constructed.

**A second, more general lesson found fixing this one:** the schema
JSON is read at TWO separate offsetting stages --
`_seed_shared_population` (per-objective, at initial seeding) and
`merge_archive_candidate` (at final merge) -- and both must see the SAME
schema for their two offset passes to compose correctly. Editing
`fk_columns` and then only rebuilding the fixture from an
ALREADY-EXISTING archive pickle (skipping the search re-run) leaves the
pickle's own baked-in per-objective offsets computed under the OLD
schema, while the merge step re-offsets under the NEW schema --
double-offsetting a column that was already shifted once at seed time,
while single-offsetting one (like `promotion_id` here) that wasn't
shifted before at all, corrupting the correspondence between them (a
real, reproduced intermediate failure this round, fixed by re-running
`rerun_spree_search.py` before rebuilding the fixture, per this
project's own established discipline: any `fk_columns` schema edit
needs a full search re-run, not just a fixture rebuild, to take effect
consistently).

Verified via full re-run + fixture rebuild + `coverage.py`, plus the
same self-test/regression suite as the round above -- all pass
unchanged (this fix is Spree-only, `spree_promotion_actions` doesn't
exist in the other 3 case studies' schemas).

### 2026-09-24 — Spree IN-subquery mechanism + merge-offsetting fixes
Numbers: see "Latest snapshot" above (Spree 14→17 verified, 5/8→6/8
decisions). Root-caused, from already-recorded `objective_results.csv`/
`decision_trace.json` only, why 8 search-claimed-solvable Spree rules
never verified: (A) `COLUMN IN (SELECT ... WHERE ...)` filter shape
entirely unrecognized by the mechanical row-builder (`candidate.py`'s
`_mechanical_filter_predicate` silently drops any conjunct it can't
parse, so the search's own fitness degrades to "match anything" and
stops well before a correctly-bound row exists) -- fixed with a new,
disclosed `self`-token table binding (`generator/aggregate_self_table.py`)
plus real IN-subquery parent-row construction in `candidate.py`/
`mutation.py`. (B) `spree_discounts.fk_columns` was `[]` in the schema
JSON despite every column being a real FK (same class of extraction gap
as `spree_order_promotions`/`spree_promotion_rules`, fixed earlier this
session) -- `dynamosa.py`'s own merge-time key-offsetting reads this
field, so with it empty, `spree_discounts`'s own FK columns never got
offset in step with the rows they reference, breaking the correspondence
after merge. Fixing (B) surfaced (C), a third, previously-masked bug:
`materialize.py` left every row missing its own table's single surrogate
key for SQLite's own NULL-rowid auto-assignment, whose value has zero
visibility into this pipeline's own explicit offset-derived ids
elsewhere in the same table -- a real `UNIQUE constraint failed:
SPREE_ORDERS.id` once (B)'s fix made the two schemes' outputs actually
collide (confirmed by direct trace: an SQLite-auto-assigned id landed on
the exact value a later, unrelated, offset-derived row explicitly
carried). Fixed with `_fill_missing_surrogate_keys` in `materialize.py`
(applies to every case study, not just Spree, since the underlying gap
was pipeline-wide, not Spree-specific).

**Cross-case-study regression check, and the one false alarm it caught:**
since fix (C) is shared code, all 4 fixtures were rebuilt and
`coverage.py` re-run. The first pass appeared to show OpenMRS/jBilling
regressions (37→41 up, but also unrelated flips in `Birthdate
Validity`/`Invoice Overdue Check`) -- traced to comparing against
`coverage_out/*`'s own committed CSVs, which turned out to be STALE
relative to this file's own already-recorded "Latest snapshot" numbers
from the `f8a64150` round (a separate provenance store that hadn't been
regenerated since). Re-compared against this file's own recorded
OpenMRS=41/jBilling=10/FLEX2=21 instead: the new run reproduces all
three exactly, so fix (C) causes zero net change outside Spree. (The
`coverage_out/*` CSVs themselves are now stale in the other direction
and should be regenerated, not re-trusted as a diff baseline, next time
any of this is touched.)

Verified via: `materialize.py`/`candidate.py`/`mutation.py` self-tests,
`validation_oracle/tests/test_serialized_field_roundtrip.py`,
`test_spec_cases.py`, `test_drd_chaining_synthetic.py`, `drd_executor.py`
-- all pass unchanged.

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
