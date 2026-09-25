# Independent rule-coverage validation oracle — design document

**Status: v1 built and passing its acceptance test.** See
"Implementation status" below for exactly what's real, what's verified,
and what's still a disclosed gap. Earlier revisions of this document said
"design only, nothing implemented" — no longer true; treat this section
and "Implementation status" as authoritative over any design prose below
them that hasn't been updated to match.

## Implementation status (kept current, not historical)

Built, in `validation_oracle/`, all independent of `generator/`'s search
path except the two explicit exceptions named in "Architectural
separation requirement": `dmn_walk.py`, `phase1_utility.py`,
`subject_table.py`, `schema_utility.py`, `db_resolver.py`,
`rule_evaluator.py`, `drd_executor.py`.

**Verified working, end to end, against real data:**
- Single-table decision enumeration + rule selection (OpenMRS's
  `Preferred Identifier Requirement`) — the acceptance test: independently
  reproduced the OpenMRS merge regression from `DECISIONS_ALGORITHM.md`
  §8 with zero prior knowledge fed in.
- Multi-table decisions via forward-only FK join paths
  (`schema_utility.build_join_path`, `subject_table._pick_root`) — 17 of
  OpenMRS's 20 real decisions now resolve, verified against real
  cross-table queries (`Identifier Location Requirement`).
- **Composite primary keys.** Subject identity is now always a
  `(pk_cols, pk_vals)` pair of tuples throughout `db_resolver.py`/
  `drd_executor.py`/`subject_table.py` (`schema_utility.pk_columns`
  always returns a list). Verified against FLEX2's real composite-PK
  tables directly.
- **Broadened root search.** `subject_table._pick_root` now searches
  every table in a decision's own `fk_closure_tables`, not only the
  tables its inputs directly reference — a genuine junction table no
  input ever reads can still be the correct subject. Confirmed real
  against FLEX2's `Course Load Limit`: its own inputs reference only
  `STUDENT_PROGRAM` and `SEMESTER` (no FK between them at all), but
  `STUDENT_SEMESTER` — never read by any input, composite PK
  `[SEM_ID, ROLL_NO]` — has forward FKs to both and is correctly found.
- `not_persisted` inputs via an explicit, visibly-flagged
  `declared_not_persisted_value` parameter — verified against a real
  OpenMRS objective (`Birthdate Validity::evaluationTime`).
- `derived_join_count` (unmet-prerequisite-style join+count) — implemented
  and unit-verified (synthetic prerequisite/registration data: 3
  prerequisites, 2 passed, 1 failed → correctly counts 1 unmet).

**Verified working via synthetic tests** (`tests/test_drd_chaining_synthetic.py`):
- `literal_via_upstream_branch` DRD chaining (`DecisionRunner`,
  `UngroundedForCase`) — correctly distinguishes a real case where the
  upstream decision actually selected the required rule (value applies)
  from one where it selected a different rule (objective correctly
  treated as not grounded for that case, not silently matched anyway).
- `substituted_decision` expression evaluation
  (`rule_evaluator.evaluate_expression`) — arithmetic over independently
  resolved free variables.
- `derived_aggregate`'s placeholder-to-column-name matching
  (`db_resolver._resolve_placeholders`) — unit-verified against real
  FLEX2 column names.

**A major real finding, from running the now-complete pipeline against
FLEX2's `Course Load Limit` (composite-PK root + DRD chaining together,
not a synthetic test):** the search's own archive claims **11/11**
`Course Load Limit` objectives covered. Independent verification finds
**0/11** — because `STUDENT_SEMESTER` (the real subject table, per the
broadened-root-search finding above) has **zero rows** in the generated
database. No objective's own fitness function ever reads
`STUDENT_SEMESTER` directly, so the search had no reason to populate it,
even though the real DMN decision structurally cannot be evaluated
without it. This is exactly the kind of discrepancy this validator was
built to surface — a large one, on real data, found by the completed
pipeline, not a synthetic example.

**Correction, and now closed: OpenMRS's 3 `Numeric *` decisions.**
Originally characterized as needing a genuinely one-to-many backward
join — wrong. `concept_numeric`'s own primary key IS `concept_id` (a
shared-PK subtype of `concept`), so its relationship to `concept` is 1:1,
not one-to-many. Built `schema_utility.functional_backward_edges`:
recognizes this pattern generally (any table whose own PK equals an FK
column pointing elsewhere) as safely traversable backward — 6 such
tables exist in OpenMRS's schema alone, so this is a real, reusable
capability, not a one-off.

That fix immediately surfaced the REAL blocker, which was never
cardinality: `obs` has two distinct FK columns to `concept`
(`concept_id` — the concept an observation measures — and `value_coded`
— an unrelated coded answer value). Two real bugs were found and fixed
before this could be trusted: (1) an early version silently picked
whichever column iteration happened to visit first (the wrong one,
`value_coded`) — fixed by refusing to traverse a connection with more
than one distinct FK column unless a disambiguation is on record; (2)
the fix for (1) let the search silently reroute around the refusal
through an unrelated, nonsensical path (`obs → location → concept`, via
a location's own "location type concept") — fixed by refusing any found
path that circumvents a skipped ambiguity between two of its own member
tables, not just the direct edge.

Closing it for real needed one human, disclosed call — `join_disambiguation.py`
now records, explicitly and inspectably (same status as this project's
own `[ASSUMED...]`-marked ground-truth rows): `(OpenMRS, obs, concept) →
concept_id`, with the reasoning written out, checked by
`build_join_path` before it will ever treat multiple FK columns as an
unresolvable ambiguity. Not silent, not automatic guessing — a named,
reviewable override an ambiguity search consults, exactly the same
discipline as everywhere else `variable_resolution` required one.

A third real bug fell out of finally running these end to end:
`evaluate_condition` didn't handle a bare `{'kind': 'literal', 'value':
true}` condition with no comparison operator at all — a legitimate
DMN pattern (a default/catch-all rule, every input entry `-`). Fixed;
this affects any decision with a default rule, not just these three.

**Real result, all 3 decisions, run against the actual OpenMRS merged
database (21 real cases each):** `Numeric Precision Validity` — 1 of 3
rules a **false positive** (`Rule_1`: search claims covered, no real
case selects it). `Numeric Absolute Range Validity` — 2 of 3 rules false
positives (`Rule_1`, `Rule_2`). `Numeric Interpretation Classification`
— all 5 rules confirmed. Three more real, independently-found
discrepancies, on top of the `Preferred Identifier Requirement` and
`Course Load Limit` findings above.

**No gap left open by refusal-to-build** in the original "backward join"
scope. What's left is ordinary unfinished work (below), not a declined
mechanism.

**Fixed a real case-sensitivity bug in `DecisionRunner.
upstream_subject_value` (2026-09-24), found investigating FLEX2's
`Course Load Limit` again** (its own subject table now has real rows,
unlike the earlier "zero rows" finding above — this is a different,
later bug). The function compared schema-declared column casing
(`ROLL_NO`) against a row dict whose real keys are lowercase SQLite
column names (`roll_no`), with no `.lower()` — the identical
normalization `db_resolver.py`'s own single-decision join-hop code
already applies, just missing from this newer cross-decision copy of
the same pattern. Every cross-decision lookup silently returned `None`,
misreported as `UngroundedForCase("no corresponding upstream row")`
for every real case, corpus-wide (all 57 `literal_via_upstream_branch`
records in FLEX2/jBilling) — before the upstream rule's own condition
(already correctly spliced in by `compile_constraints.py` at compile
time; an earlier same-day diagnosis blaming the search's own fitness
function for this was wrong and has been retracted, see
`KNOWN_ISSUES.md`) was ever even checked. Fixed with two `.lower()`
calls; verified directly against real FLEX2 data that every
previously-`None` lookup now resolves a real upstream selected rule.
Unmasked a separate, previously-unreached gap, since fixed the same
day: `derived_case` (a categorical column mapping, e.g. `SEMESTER.
TITLE`: `'Fall'/'Spring' -> 'Regular'`, `'Summer' -> 'Summer'`) was not
implemented anywhere in `db_resolver.py`'s own `resolve()` —
`generator/candidate.py` already handled it on the generation side, the
validator simply never needed to until this fix let evaluation reach
that far. Implemented as a direct, mechanical port of `candidate.py`'s
own logic (read the real column, walk `cases` for a match, raise on an
unmapped value rather than defaulting); verified directly against real
FLEX2 data before trusting it. Confirmed via a fresh `coverage.py` run:
`Course Load Limit` is no longer in `unresolved_decisions` at all — every
one of its 11 objectives is now genuinely, fully evaluated for the
first time. Still 0/11 verified, but now for a real, disclosed,
generator-side reason (the search's own merge never aligned all 4 of
this composite record's own independent leaves onto one
mutually-consistent real subject) rather than either of the two
validator bugs above — that residual gap is generator-side, out of this
investigation's own scope, and not pursued further here.

**That generator-side gap — never constructing a decision's own real
subject row when no leaf reads it directly — was investigated further
and fixed 2026-09-24**, in `generator/compile_constraints.py` (a new
`decision_subject` compile-time field, a generator-owned port of THIS
module's own `subject_table_for_decision` algorithm — chosen over
importing it directly, to preserve the "Architectural separation
requirement" section's own "no overlap in function calls" in both
directions, not just the direction it's literally written for) plus a
new merge-time consumer in `generator/dynamosa.py`'s
`merge_archive_candidate`. Found in exactly 2 decisions (FLEX2's
`Course Load Limit`, OpenMRS's `Identifier Uniqueness Check`) — a
third suspect, Spree's `Promotion Customer Group Eligibility`, turned
out to be a genuine one-to-many backward-join gap instead once a real
bug in THIS module's own `tables_referenced` was found and fixed (see
below). Result: OpenMRS 41→42 verified
(`Identifier Uniqueness Check::rule_1`), zero regressions anywhere;
`Course Load Limit` remains 0/11 for the separate, already-disclosed
value-alignment reason above (the junction row now genuinely exists
and cross-references correctly, confirmed directly — this fix solves
the structural correspondence, not the search's own value coordination
across it). Full details, including two more independently-found bugs
fixed the same day, in `KNOWN_ISSUES.md`'s cross-case-study entry.

**RETRACTED (2026-09-24, same day): the "value-alignment" diagnosis
above for `Course Load Limit`'s 0/11 was wrong — it was never verified
against real resolved values, only inferred from "no rule selected."**
Directly evaluating a grounded variant's own compiled condition by hand
against its real resolved values showed every clause should be true —
the composite leaves WERE correctly aligned. The real cause was three
compounding bugs in `drd_executor.py`/`rule_evaluator.py`: (1)
`run_decision` merged every DRD-fan-out variant of a decision (several
compiled records can share one `rule_id` with DIFFERENT own
`condition`/`variable_resolution`, one per upstream branch — see
"DRD-ordered execution" below) into ONE dict via `dict.update()`,
silently keeping only the last-processed variant's own definition for
a variable name shared across variants (`Course Load Limit::Rule_4`
alone has 6 such variants); (2) no per-subject/per-variant isolation
existed around a resolution failure other than `UngroundedForCase` — a
`derived_case` hitting a real value uncovered by any declared case
raised a plain `NotImplementedError` that aborted the WHOLE decision for
EVERY subject, not just the one that hit it; (3) `rule_evaluator.
evaluate_condition` never implemented `not`/`between` at all (unlike
`fitness.py`'s own full support) — 54 compiled records corpus-wide use
`not`. Fixed, all three: `run_decision` now tries every variant of a
`rule_id` independently per real subject (a rule matches if ANY variant
both grounds and evaluates true); `db_resolver.py`'s `derived_case`
raises a new, distinct `UnresolvableForCase`, translated by
`_resolve_one` into `UngroundedForCase` so it is isolated to the one
variant/subject it affects; `not`/`between` added to
`evaluate_condition`, mirroring `fitness.py`'s own key names. Verified
via a full per-objective before/after diff across all 4 case studies
(identical `coverage.py` invocation, code-only difference): `Course Load
Limit` 0/11 → 11/11 confirmed (all 4 distinct rule_ids), zero flips
anywhere else. Full writeup, including a separately-disclosed, unrelated
coverage-run-methodology finding surfaced while establishing the
before/after baseline, in `KNOWN_ISSUES.md`'s cross-case-study entry and
`COVERAGE_REPORT.md`'s Run history.

**Closed FLEX2's `Course Replacement Eligibility` filter_text
placeholder gap (2026-09-24), partially.** `degreeTotalCredits`'s own
compiled `derived_aggregate` reads `PROGRAM_COURSE.PROG_ID=<program> AND
PROGRAM_COURSE.BATCH_NO=<batch>` — neither column is on the decision's
own subject row (`COURSE_REGISTRATION`), the same shape as Spree's
already-solved `Promotion Customer Group Eligibility::promotion_id` gap.
Both are real columns on `STUDENT_PROGRAM`, reachable via
`COURSE_REGISTRATION.ROLL_NO`'s own real forward FK. Fixed with two new
`filter_placeholder_sources.py` entries — no new mechanism, the
join-aware placeholder resolver already handles this generically.
Surfaced a second, independent bug in `db_resolver.py`'s own
`derived_aggregate` SQL construction: `degreeTotalCredits`'s own `table`
field is a real, old-style implicit-join list (`"PROGRAM_COURSE,
COURSE"`), but the SQL builder quoted the WHOLE string as one
identifier, raising `no such table: PROGRAM_COURSE, COURSE`. Fixed by
quoting each comma-separated table name individually, and keeping
`value_column` fully qualified rather than stripped to a bare column
name (necessary once `table` names more than one; free for the existing
single-table case, checked against jBilling's own
`ageing_entity_step.days`, unaffected). Verified: `Rule_2`/`Rule_5`/
`Rule_6` flip false_positive → confirmed (FLEX2 25→28, decision-table
3/10→4/10), zero flips anywhere else. This decision's own `Rule_1`/
`Rule_3`/`Rule_4` remain open — a separate, unrelated data-construction
gap where every real subject resolves the same four variables to the
exact same (never-satisfying) value with zero variation — see
`KNOWN_ISSUES.md`'s FLEX2 section.

**Investigating that same data-construction gap further (2026-09-24)
found and fixed two more bugs, this time in `generator/dynamosa.py`'s
own `decision_subject` junction-row builder.** (1) The builder only ran
when the subject table was completely absent from a record's own focal
rows — it never synthesized a missing SIBLING row a hop needed to link
through, so `Rule_1` (a dedicated `COURSE` row but no `STUDENT_PROGRAM`
row at all) had its whole junction row silently abandoned. Fixed:
synthesize a fresh, minimal row for a missing hop target instead of
aborting. (2) Checking `Rule_3`/`Rule_4` after fixing (1) found the fix
still only fired when the subject row was missing ENTIRELY — but it can
already exist (built by ANOTHER leaf, e.g. `Rule_3`'s own
`gradeInCourseToReplace` on `COURSE_REGISTRATION`) while a DIFFERENT
leaf of the SAME record builds its own separate row on a table the
subject needs to link through (e.g. `creditsEarned` on
`STUDENT_PROGRAM`), with nothing ever wiring the two together. Fixed by
always attempting to wire every `subject['joins']` hop onto the subject
row, new or pre-existing, skipping only a hop whose own FK column
already has a real value. Verified: `Rule_1` flips false_positive →
confirmed (FLEX2 28→29); `creditsEarned` now correctly resolves the
real per-subject value for `Rule_3`/`Rule_4`/`Rule_5` — but `Rule_3`/
`Rule_4` STILL don't verify, root-caused to a THIRD, distinct,
generator-side bug (fixed separately, see immediately below). Zero
flips anywhere else across all 4 case studies, full regression suite
re-run and passing.

**That third bug, closed 2026-09-24: `<program>`/`<batch>`
(`degreeTotalCredits`'s own filter_text placeholders) were never
correlated with the SAME record's own `STUDENT_PROGRAM.PROG_ID`/
`.BATCH_NO` anywhere in the search pipeline.** CORRECTION to this
investigation's own prior diagnosis, same day: the writeup above guessed
`PROGRAM_COURSE.PROG_ID=64000001` came from `repair_candidate`'s generic
NOT-NULL fallback. Checking the raw, pre-merge `scenario_map` directly
showed this was wrong — `scenario['program']` is ALSO `64000001` for
that record, so `candidate.py`'s own seeding and `PROGRAM_COURSE.
PROG_ID` stay perfectly self-consistent throughout seeding, search, and
merge-time offsetting (both shift together under the identical
per-record offset); `candidate.py` was never actually broken. The REAL
gap: `STUDENT_PROGRAM.PROG_ID`/`.BATCH_NO` are never independently set
by any leaf (`creditsEarned` only reads `credits_earned`, no placeholder
involved) — they only ever get a value from `mutation.py`'s own
`_repair_row` generic NOT-NULL fallback, a plain constant `1`,
unrelated to `scenario['program']`'s own value. Neither `candidate.py`'s
seeding/mutation nor `fitness.py`'s own evaluation ever cross-references
a live `STUDENT_PROGRAM` row for this placeholder — both only ever
compare it against the flat `scenario['program']` scalar. Fixed at merge
time (`dynamosa.py`, same layer as the `decision_subject` fix — a
post-search correction, not a search-loop/fitness/mutation change): a
new compile-time field, `compile_constraints.py`'s
`cross_table_placeholders` (reusing its own
`_DECISION_SUBJECT_PLACEHOLDER_SOURCES` mirror of
`filter_placeholder_sources.py`, now also carrying FLEX2's `program`/
`batch` entries), attached to each `derived_aggregate`/`exists` node
with such a placeholder; `merge_archive_candidate` copies the record's
own already-offset `scenario[placeholder]` value onto the correlated
table's own focal row/column before `repair_candidate` runs. Verified:
`Rule_3` flips false_positive → confirmed (FLEX2 29→30). Zero flips
anywhere else across all 4 case studies; `compiled_constraints.json`
re-diffed field-by-field (only the new field, on exactly 6 nodes). Full
regression suite re-run and passing. `Rule_4` did not yet verify at
this point — closed the next day, same bug shape, see immediately below.

**`Rule_4` closed 2026-09-25 — the SAME bug shape as `Rule_3` above,
mirrored within one table pair instead of across two.**
`courseOfferedInFollowingSemesters` (an `exists` check needing a second
`COURSE_OFFER` row for the same subject's own `COURSE_ID`) resolved
`False` for every real subject: `COURSE_OFFER.COURSE_ID` correctly
tracks `scenario['COURSE_ID']` throughout search, while the SAME
record's own `COURSE.COURSE_ID` only ever gets a value from a global,
cross-record fresh-key repair, unrelated to either. Unlike `<program>`/
`<batch>`, the validator never even reaches `filter_placeholder_
sources.py` for `<COURSE_ID>` — it resolves directly off the subject
row's own `course_id` column (already wired to `COURSE.COURSE_ID` by
the junction-row fix), so the gap is purely generator-side. Extended
`cross_table_placeholders` with a second compile-time source
(`compute_subject_hop_placeholder_correlations`): a conjunct whose own
column matches the decision's own subject row's real FK column (per
`decision_subject['joins']`) needs no declared override — the target is
read straight off that hop. Reordered `dynamosa.py`'s own consumption to
run BEFORE the subject-junction wiring step (not after): for this shape
the correlated table (`COURSE`) is the one a subject hop reads FROM, so
the correction must land first. Also taught the consumer to synthesize
the correlated row when none exists yet. A genuine PK/UNIQUE collision
surfaced verifying this (`degreeTotalCredits`'s own separate `COURSE`
row-building landed on the identical `COURSE_ID` after offsetting) —
fixed by bumping the OTHER, non-authoritative colliding row to a fresh
value via `mutation.py`'s own `_fresh_key_value`, the same mechanism
every other such clash resolves through. Verified: `Rule_4` flips
false_positive → confirmed (FLEX2 30→31), `Course Replacement
Eligibility` now fully 6/6; zero flips anywhere else across all 4 case
studies (Spree's fixture gains one harmless extra row from the same
consumer's new synthesis behavior, confirmed byte-identical
`objective_results.csv`). Full regression suite re-run and passing.

**Investigated FLEX2's remaining 5 "backward-join" refusals (2026-09-25)
and found they were never one category.** 2 (`Course Registration
Eligibility`, `Credit Transfer Exemption`) shared a real, fixable bug in
`subject_table.py`'s own `_TABLE_EXTRACTORS`: `derived_join_count`
unconditionally required BOTH `prereq_table` AND `registration_table` to
be forward-reachable, but `db_resolver.resolve()`'s own implementation
queries `prereq_table` via a raw, uncorrelated scan needing NO join path
at all — the SAME "self-contained" shape `derived_aggregate`/`exists`
were already exempted for. Fixed by dropping `prereq_table`; both
decisions now resolve to `COURSE_REGISTRATION`. Confirmed corpus-wide:
this kind is used only by these two decisions, zero collateral anywhere
else. Verified: `Credit Transfer Exemption` fully resolved and verified
1/3 (FLEX2 31→32); `Course Registration Eligibility` moved past
subject-picking into a DIFFERENT, deeper gap (it chains to `Course Load
Limit`'s composite-PK subject `STUDENT_SEMESTER` via
`literal_via_upstream_branch`, and `DecisionRunner.upstream_subject_
value`'s own single-continuous-FK-chain builder can't express that
`COURSE_REGISTRATION` already has BOTH composite-PK columns directly —
a genuinely unambiguous correspondence the mechanism just can't state;
not yet fixed).

Testing the same idea against `raw_sql_boolean`'s own extractor (same
shape, confirmed used only by `Summer Semester Registration`) found and
fixed a second real bug the same way. This resolves subject-picking to
`COURSE`, but only trades one refusal for a more precise one
(`<this course offering>` needs `offer_id`, not on `COURSE`) — tested a
`filter_placeholder_sources.py` override pointing at `COURSE_OFFER`,
which surfaces a genuine 3-way root ambiguity instead
(`COURSE_OFFER`/`COURSE_REGISTRATION`/`REPEAT_COURSE` all qualify) —
reverted, not committed; the extractor fix itself was kept (correct,
zero side effects, just not sufficient alone).

The remaining 2 are genuinely distinct, not bugs: `Admission Closure
Eligibility`'s own `ADM_MERIT_LIST` has no PK or FK declared anywhere in
the real DDL (`schemas/flex2/Flex1.sql`, checked directly) — no
relationship exists to disclose an override for. `Graduation
Eligibility`'s own `STUDENT_PROGRAM.(BATCH_NO, PROG_ID)` correspond
exactly to `BATCH_PROGRAM`'s own composite PK, but the schema only
captured two separate single-column FKs, and this project's own
join-path builder is deliberately single-column-hop-only — a genuinely
new composite-join capability, out of current scope. Full regression
suite re-run and passing; no fixture rebuild needed.

**Built the composite-join capability above, on request (2026-09-25) —
`Graduation Eligibility`'s own scope limitation is no longer out of
scope.** New `schema_utility.composite_backward_edges(case_study,
table)`: a table `T` with a composite (≥2-column) PK is reachable from
`table` when EVERY one of `T`'s own PK columns is itself an FK to the
exact same `(ref_table, ref_column)` that some column of `table` already
FKs to — both tables independently FK to the same real entity in each
PK slot, a schema-declared correspondence, never a guess. `build_join_
path` tries this ONLY at its own BFS starting node (never a few hops
in): trying it deeper let ANY table with an ordinary FK straight to
`STUDENT_PROGRAM` (e.g. `STUDENT_SEMESTER`) transitively "reach"
`BATCH_PROGRAM` too, by routing through a table (`STUDENT_PROGRAM`) the
decision already needs directly — a spurious second root candidate,
found and eliminated by this restriction. The resulting hop carries
`from_columns`/`to_columns` lists instead of a single `from_column`/
`to_column`; `db_resolver.py`'s `_row_for_table` and `drd_executor.py`'s
`upstream_subject_value` (the two hop-walkers) both handle the new shape
alongside the old one. Verified via a full subject-table sweep (every
decision, all 4 case studies) and a full `coverage.py` re-run per case
study, before/after: zero collateral anywhere outside FLEX2, zero change
to any other FLEX2 decision. `Graduation Eligibility` now resolves its
subject cleanly — but running it through `run_decision` immediately
surfaces a SEPARATE, previously-unreachable bug: `semestersElapsed`'s own
`derived_aggregate` node has `filter_text: null` despite its
`source_text` explicitly describing a needed subject correlation ("...
for ROLL_NO"), producing malformed SQL. A Phase 1/`compile_constraints.
py` compile-time gap, disclosed rather than patched around here — still
0/5 verified for this decision. As a side effect of the SAME shared
mechanism, `Course Registration Eligibility`'s own separate
upstream-chaining gap (above) is also fixed: `Rule_1` verifies for all
545 real cases (`Rule_2`/`3`/`4` don't, with nothing `ungrounded` — an
ordinary data-coverage gap). FLEX2 32→33 verified rules.

**Fixed the `semestersElapsed` compile-time bug above, the same day, on
request ("build option 2" — a general parser fix, not a one-off
override).** Traced to the real ground truth: `jbillingandflex/
flex2_dmn/.../provenance/variable_to_schema_mapping.csv` line 37 reads
"derived COUNT(STUDENT_SEMESTER) for ROLL_NO" — "for COL" phrasing
instead of a `WHERE` clause, which `generator/compile_constraints.py`'s
own `_try_extract_aggregate_recipe` had never been taught to recognize.
New `AGGREGATE_FOR_CORRELATION_RE` matches "for COL"/"for COL1+COL2"
immediately after the aggregate/table match (anchored right there, never
a bare `search` elsewhere in the text, so an unrelated later "for" is
never mistaken for this convention) and translates it into the SAME
`:column` self-reference syntax `_substitute_self_and_colon` already
resolves — no new validator capability needed, just a compile-time
translation into an existing, already-tested mechanism. Confirmed via an
order-independent diff of the whole recompiled `compiled_constraints.
json`: exactly 7 records changed (`Graduation Eligibility`'s 3
`semestersElapsed` variants, `Summer Semester Registration`'s 4
`priorRegistrationCount`/`enrolledStudentCount` variants), zero others —
`Summer Semester Registration`'s own THIRD, differently-worded fact
(`repeatCourseCountRequested`: "COUNT per USER_ID/semester") correctly
stayed untouched, since "per COL/word" is a different phrasing this fix
deliberately doesn't parse. Verified against the real FLEX2 fixture (no
rebuild needed): `Graduation Eligibility` jumped from 0/5 to 3/5 verified
(`Rule_1`/`Rule_2`/`Rule_3`); `Rule_4`/`Rule_5` don't verify for a
confirmed, ordinary data-coverage reason (hit policy `FIRST`, `Rule_5` an
unconditional catch-all, and all 148 real `STUDENT_PROGRAM` rows in the
fixture already match an earlier rule first). `Summer Semester
Registration` is unchanged (its own subject row, `COURSE`, never had the
needed columns regardless). Full regression across all 4 case studies
confirms zero collateral. FLEX2 33→36 verified rules.

**Fixed a real bug in this module's own `tables_referenced` while
building the above (2026-09-24): `substituted_decision` was dead
code.** It was listed in `_NON_TABLE_KINDS` (checked before the dedicated
per-kind dispatch further down, returning an empty table set
unconditionally) AND had its own dedicated recursive-into-
free-variables branch later in this same function — permanently
unreachable, since the `_NON_TABLE_KINDS` check ran first. Confirmed load-bearing, not cosmetic: Spree's `Promotion
Customer Group Eligibility::rule_4` has a `substituted_decision`
(`matchingCustomerGroupCount`) whose own free variable
(`customerGroupIds`) is a plain `schema_column` on
`spree_customer_group_users` — a real table this decision's own
`join_paths` was silently missing, a latent `NotImplementedError`
`_row_for_table` would have raised the moment real verification ever
reached that variable. Fixed by removing `substituted_decision` from
`_NON_TABLE_KINDS`; this decision's own subject then correctly fails to
resolve at all (a genuine one-to-many gap to `spree_customer_group_users`,
no forward-FK or shared-PK-subtype path exists), matching
`KNOWN_ISSUES.md`'s corrected diagnosis for it.

**`coverage.py` built.** Aggregates every decision in a case study
against one already-materialized database and writes the three spec'd
output files: `objective_results.csv` (one row per compiled objective:
search_covered/verified_rule_selected/agreement_class),
`validation_summary.csv` (one row per case_study/algorithm/run_id/
construction_strategy: total_dmn_rules, statically_infeasible_rules
[from `phase1_utility.statically_infeasible_count`, specifically
`reason == 'infeasible'` in compile_report.json's own `blocked_records`
— NOT the broader "blocked" total, which also covers schema-gap-style
blocks, a different category], searchable_objectives,
search_covered_objectives, verified_covered_rules,
coverage_retention_percent, schema_valid [independent
`PRAGMA foreign_key_check` against the live database, no
`generator/materialize.py` import], dmn_validation_valid, total_rows,
unresolved_decisions), and `decision_trace.json` (one entry per real
case per resolvable decision: resolved_inputs with resolution_type/
source_table, matched_rule_ids, selected_rule_id).

**Run for real against OpenMRS's merged-archive database (71 objectives,
19 decisions):** 64/71 search-covered, 35 distinct rule IDs
independently verified, 53.1% coverage retention, schema and DMN
validation both clean, 6 of 19 decisions correctly recorded as
unresolved (all six are the already-disclosed `not_persisted`
`evaluationTime` gap — `unresolved_decisions.json` names each one and
why, not silently dropped from any denominator).

**Two more real bugs found running this end to end, both fixed:**
`evaluate_condition` didn't handle DMN's list-membership `in` operator
(`{'op': 'in', 'left': ..., 'values': [...]}`, e.g. `conceptDatatype in
("Datetime", "Date", "Time")`) — a real, previously-unexercised
construct. And a single decision-level failure (e.g. the
`not_persisted` gap) used to be fatal to the WHOLE report; `run_coverage`
now catches a `NotImplementedError` per decision, records it in
`unresolved_decisions.json`, and keeps verifying every other decision in
the case study.

**`not_persisted` closed for the decisions this scope covers.** A caller
now supplies an explicit, disclosed `not_persisted_overrides`
(`{var_name: value}`) to `coverage.py` (`--not-persisted-json`),
threaded through `DecisionRunner`/`run_decision`/`_resolve_one`. A
`not_persisted` variable with no matching entry is recorded as an
unresolved decision, never silently treated as covered.

**A real, important finding drove the actual override value chosen for
OpenMRS's `evaluationTime`.** Checked the archived individuals' own
`scenario_maps` directly: `evaluationTime` is NOT one fixed "current
time" the search converges on -- it's tuned to a DIFFERENT value per
rule (`-19108862`, `49000006`, `50000001` across `Birthdate Validity`'s
own three rules), while `__today__` (this project's own real "today"
constant, hardcoded at `20000` everywhere else in `generator/candidate.py`)
stays fixed across every individual. A real deployment has exactly one
evaluation time per run, not one invented per rule. Using any of the
search's own per-rule values would smuggle exactly the kind of
search-side contrivance this validator exists to catch back in through
the override mechanism. The override used is `{"evaluationTime": 20000}`
-- the same value as `__today__`, disclosed and documented here, not
one of the search's own values.

**Result:** re-ran `coverage.py` against OpenMRS with this override.
`Birthdate Validity` and 4 others now resolve (down from 6 unresolved to
5); `verified_covered_rules` rose from 35 to 37. New, real finding:
`Birthdate Validity::Rule_1` is a **false positive** under the one real,
fixed evaluation time -- confirming the per-rule-tuning concern is not
hypothetical.

**A new, disclosed scope boundary found, not a bug:** the remaining 5
unresolved decisions (`Order Date Activated Consistency Violations` and
4 others) use DMN's **COLLECT** hit policy, never previously exercised.
`rule_evaluator.select_rule` only implements FIRST/UNIQUE -- exactly the
two hit policies the original specification named -- so this is refused
for a documented reason, not silently mishandled. Supporting COLLECT
(which returns every matching rule's output combined, not one "selected"
rule -- a materially different coverage question) is real, unscoped
future work.

**All 10 spec'd test cases now covered.** `tests/test_spec_cases.py`
covers FIRST precedence (both directions), UNIQUE (single match and
violation), `derived_aggregate`-driven selection, `join_lookup`-driven
selection, and duplicate-output disambiguation (two rules with an
identical output value still tracked as independently covered by rule
ID — `decision_output` in the trace confirmed correct for both). The
upstream-dependency pair and the merge-induced-regression case were
already covered by `test_drd_chaining_synthetic.py` and the OpenMRS
acceptance test respectively — referenced there, not duplicated. One
cosmetic bug found and fixed while writing the UNIQUE-violation case:
`UniqueViolation`'s own decision-name label was derived by string-
splitting a rule_id (nonsensical for a plain `Rule_1`) instead of just
receiving the real `decision_name` the caller already has; `select_rule`
now takes it directly.

`decision_output` is also now tracked in `decision_trace.json` (every
output seen so far is a plain literal per rule; a non-literal output
raises rather than guessing) — purely for inspection, since rule
selection only ever compares conditions, never output values.

**Extended to Spree and jBilling.** Fixtures built the same way as
OpenMRS/FLEX2 (`tests/build_fixture_from_generator.py`, generalized --
`spree_merged.db`, `jbilling_merged.db`). `coverage.py` run end to end
against both real merged-archive databases:

| Case study | Objectives | Search-covered | Verified rule IDs | Coverage retention |
|---|---|---|---|---|
| Spree | 26 | 22 (84.6%) | 7 (26.9%) | 31.8% |
| jBilling | 40 | 35 (87.5%) | 10 (25.6%) | 29.4% |

Both show a much larger search-vs-verified gap than OpenMRS's 53-56%
retention -- expected and explained, not mysterious: over half of each
case study's decisions are currently unresolved, and every single one of
them maps to an ALREADY-DOCUMENTED limitation from earlier in this
project's own history, not a new mystery:
- `schema_gap`-kind variables (Spree's `Promotion Customer Group
  Eligibility`) -- the ground truth itself already marks these
  unresolvable without a real sample row; not a validator gap.
- The one genuinely unparsed FEEL construct (Spree's `First-Order
  Promotion Eligibility`, an `opaque_formula` list-comprehension) --
  `feel_parser.py`'s own documented, pre-existing limit.
- Multi-table decisions needing a backward/shared-parent join with no
  disclosed override on record (Spree's `Promotion Usage Limit
  Exceeded`; jBilling's `Ageing Step Advancement`/`Ageing Step Config
  Validation`) -- same category as OpenMRS's 3 `Numeric *` decisions
  before their override was added; closeable the same way if someone
  supplies the domain-knowledge call.
- Decisions with zero table-backed inputs at all (jBilling's `Is Ageing
  Required`, `Order Date Range Valid`, `Payment Outcome Resolution`,
  `Payment Balance Assignment`, `Daily Pro-Rate Amount`; Spree's `Price
  List Volume Adjustment Tier Selection`) -- entirely `not_persisted`/
  upstream-only, no natural database grain.
- `not_persisted` variables with no principled universal value
  (jBilling's `candidateDateProvided`, `customContactFieldConfigured`,
  and others) -- unlike OpenMRS's `evaluationTime` or the `today()` fix
  below, these represent arbitrary external-system-state flags (e.g. "is
  the payment processor unavailable") with no single real answer;
  declaring one would be a scenario CHOICE, not a fact, so none was
  invented.
- `COLLECT` hit policy (Spree's `Price Adjustment Tier Validity
  Violations`; jBilling has more) -- same disclosed scope boundary as
  OpenMRS.

**Two real, closeable gaps found and fixed while extending to Spree:**
- A second, distinct filter_text convention: `:column_name` (colon-
  prefixed) and bare `self`, found in `Price Adjustment Tier Validity
  Violations`'s own `derived_aggregate` (`price_list_id = :price_list_id
  AND id != self` -- an exclude-self aggregate). Neither is a
  cross-entity placeholder needing external binding; both are
  self-references to the subject row already being resolved
  (`:column_name` = that column's own value; `self` = the row's own PK,
  raising rather than guessing for a composite-PK subject, where a
  single self-value would be ambiguous). Fixed in
  `db_resolver._substitute_self_and_colon`, applied before the existing
  `<placeholder>` substitution.
- FEEL's `today()` appearing directly as a condition operand (jBilling's
  `Invoice Overdue Check`) -- distinct from `not_persisted`'s
  `evaluationTime`, this is a bare function call inside the condition
  tree itself. Fixed by reusing `generator/candidate.py`'s own
  `'__today__'` key name: `not_persisted_overrides={'__today__': 20000}`
  (same disclosed value as everywhere else) is now injected into
  `values` before rule selection, so `today()` resolves the same way
  `__today__` already does throughout the search side, never guessed
  and never a database read.

Still not started: `first_generation_covered` (needs re-instrumenting
`generator/dynamosa.py`'s own archive-update loop, a `generator/`-side
change, not a `coverage.py`-side one), COLLECT hit policy support, and
closing the remaining disclosed gaps above (multi-table backward joins
needing a human override, decisions with no database grain at all).

**2026-09-24: closed the last 3 underspecified-ground-truth decisions
(Spree's `Promotion Usage Limit Exceeded`, jBilling's `Ageing Step
Advancement`/`Ageing Step Config Validation`).** These were never
actually join-path ambiguities -- each needed an aggregate/correlation
rule ground truth had described in prose but never encoded machine-
actionably (Spree: a de-dup COUNT over `spree_discounts`; jBilling: an
`(entity_id, status_id)` correlation on `ageing_entity_step`). Fixed by
editing the ground-truth CSVs with disclosed, explicitly `[ASSUMED]`-
marked rows (same precedent/authorization as the earlier jBilling
`welcomeMessagePresent` fix) -- not a simplification hidden as fact,
each row's note says exactly what was assumed and why it isn't verified
against the real system. Two `db_resolver.py`/`subject_table.py`
mechanisms needed extending to represent these: `exists` now runs a real
correlated `SELECT EXISTS(SELECT 1 FROM t WHERE filter_text)` when
`filter_text` is present (previously it silently ignored `filter_text`
entirely and checked "does the subject's own row have a non-null value,"
which is a SEPARATE, real, more-impactful bug described below);
`derived_aggregate` now supports a named `value_column` (`MAX(t.col)
WHERE ...`), not just bare `COUNT(*)`.

**A real bug in `compile_constraints.py` itself, found and worked around
while writing the Spree fix:** its own filter-text extraction
(`text[...].rstrip(') ')`) blindly strips trailing `)`/space characters,
truncating a nested subquery's own closing paren. Not fixed at the
source (out of today's scope); worked around with a harmless trailing
`AND 1=1` tautology in the ground-truth CSV, verified empirically to
preserve the real closing paren.

**A real, self-inflicted regression caught before it shipped:** editing
the jBilling CSV with an unquoted comma inside a parenthesized column
list (`ageing_entity_step (entity_id, status_id)`, no surrounding
quotes) silently shifted that row's own CSV columns, corrupting its
`mapping_type` into an unrecognized bucket -- `compile_constraints.py`
gave no error, just silently reclassified 3 previously-compiling records
as blocked (jBilling's compiled count dropped from 40 to 37). Caught by
diffing the full compiled record_id set against a pre-edit baseline
(`git show HEAD:...`) before treating the recompile as done -- not
noticed by the summary counts alone, which don't show *which* records
moved. Fixed by quoting the field and rewording the notes text to
include the phrase (`"existence of"`) `compile_constraints.py`'s own
classifier requires to recognize the parenthesized-filter enrichment
shape. Re-verified after the fix: all 4 case studies' compiled record
sets are IDENTICAL to the pre-session baseline except the 3 target
records' own internal resolution shape -- zero unintended adds/removes.

**A second real, previously-undiscovered bug, found running jBilling's
`exists` fix end to end:** `exists`-kind resolution NEVER consulted
`filter_text` at all, in any prior version of this code -- it silently
checked "does the subject's own row have a non-null value for this
column," trivially true whenever `candidate_table == subject_table`
regardless of what filter was actually declared. This affected
`Currency Exchange Rate Source`'s two rules
(`hasEntitySpecificExchange`/`hasSystemDefaultExchange`, filtered on
`entity_id=<entity_id>` vs. `entity_id=0`), which had structurally been
unable to differ from each other -- meaning jBilling's PREVIOUSLY-
REPORTED coverage numbers for this decision were silently wrong. Fixed
(see above); the corrected jBilling numbers below supersede the earlier
report.

**A third real, previously-undiscovered bug, found while trying to run
FLEX2's coverage report end to end for the first time:** every dict
`db_resolver._one_row` built from a live SQLite row used the EXACT case
of `cursor.description` as its keys, while every ground-truth `column`
name is always written lowercase regardless of case study -- silently
fine for OpenMRS/Spree/jBilling (all three's real schemas already use
lowercase column names), but FLEX2's own SQLite fixture stores every
column name upper-case (`STUDENT_PROGRAM.CGPA`), so EVERY FLEX2
`schema_column`/`null_check`/`any_not_null`/etc. resolution crashed with
a bare `KeyError` -- meaning FLEX2's coverage.py report had apparently
NEVER been run to completion before this session (absent from every
previously-reported results table). Fixed by lowercasing both the row
dict's own keys and every column-name lookup against it, throughout
`db_resolver.py`. SQL identifier matching itself was never the issue --
SQLite's own WHERE/FK comparisons are already ASCII case-insensitive;
only this dict's own Python-level lookup wasn't. Also made `coverage.py`
catch `sqlite3.OperationalError`/`KeyError` per-decision (same treatment
already given `NotImplementedError`) so one decision's database/fixture
gap can't crash the whole case study's report -- needed because Spree's
`Promotion Usage Limit Exceeded` fix correctly names `spree_discounts`
(a real Spree table), but the merged fixture database for this case
study was only ever materialized against the OLD (wrong) ground truth,
so that table was never included (`no such table: spree_discounts`) --
a genuine fixture-completeness gap, not a validator bug, disclosed here
rather than silently worked around.

**2026-09-24 (later same day): the FLEX2 fixture is fixed -- two real,
previously-undiscovered bugs, both outside `validation_oracle/` itself,
found tracing WHY `flex2_merged.db` had `CGPA`/`WARNING` null across
every row despite real values existing in the source archive.**

1. **The actual root cause: `generator/mutation.py`'s own `_repair_row`
   never assigns a table's PRIMARY KEY column unless the schema also
   happens to flag it `null_false: true`.** FLEX2's own extracted schema
   never sets that flag on ANY of its 121 PK columns across every table
   (confirmed by direct survey; zero such gaps in OpenMRS/Spree/
   jBilling's schemas, so this was invisible until FLEX2's coverage
   report could run at all) -- a PK is NOT NULL by relational definition
   regardless of what the schema extraction happened to record, but
   nothing in the pipeline ever gave `STUDENT_PROGRAM.ROLL_NO` (or any
   other FLEX2 table's own PK) a value unless some decision's own search
   happened to write it directly, which none of the currently-compiled
   FLEX2 objectives do. Fixed by also repairing a declared PK column
   regardless of its own `null_false` flag. Confirmed zero blast radius
   on the other 3 case studies (0 affected PK columns each) before
   applying; full regression suite re-run clean after. Rebuilt
   `flex2_merged.db` from the SAME archive pickle
   (`FLEX2__dynamosa_nsga2__budget1x__seed0.pkl`) with this fix: every
   one of 149 `STUDENT_PROGRAM` rows now has a real, unique `ROLL_NO`
   (was 0/102 before), and total materialized rows rose from 1163 to
   1809 -- previously, rows sharing a NULL PK were apparently colliding/
   merging silently in ways that are no longer possible once each row
   has real identity.
2. **A second real bug, found immediately after, in `subject_table.py`
   itself: table names from `variable_resolution` and from
   `fk_closure_tables` are not case-consistent, and nothing canonicalized
   them before set operations.** FLEX2's own ground truth writes some
   table references lowercase (`course_registration`) and others in the
   schema's real upper-case (`COURSE_REGISTRATION`) for the IDENTICAL
   real table -- confirmed present in 6 of FLEX2's 9 decisions. Untreated,
   `_pick_root`'s reachability search either manufactured a fake "2
   candidates qualify" ambiguity (both spellings of the same table
   independently looked like valid roots) or a fake "0 candidates
   qualify" failure. Fixed by canonicalizing every table name through
   `schema_utility.canonical_table_name` before any set operation in
   `subject_table_for_decision`, and made `db_resolver._row_for_table`'s
   own table-identity comparisons case-insensitive to match (ground
   truth's raw, uncanonicalized `node['table']` strings still flow into
   it directly). Confirmed real, not cosmetic: `Course Replacement
   Eligibility` went from a manufactured "2 candidates" ambiguity to a
   clean, unique root. Zero change to OpenMRS/Spree/jBilling's own
   numbers (re-verified after).

**Result: FLEX2 now produces a real, non-trivial verified-coverage
number for the first time -- 21/98 (38.2%), up from 0/98.** 7 decisions
remain genuinely unresolved, each for a real, disclosed, different
reason, not swept into one bucket: `Attendance Eligibility For Final
Exam` has no table-backed input at all (unchanged, pre-existing scope
boundary); 5 decisions (`Admission Closure Eligibility`, `Course
Registration Eligibility`, `Credit Transfer Exemption`, `Graduation
Eligibility`, `Summer Semester Registration`) genuinely have NO table in
their own fk_closure that forward-reaches every table their inputs
need -- a real multi-table backward-join gap in the same category as the
ones already closed for Spree/jBilling, not yet attempted here (this
round's scope was the fixture, not chasing every remaining join gap);
`Course Replacement Eligibility` newly surfaces its OWN real, different,
disclosed limitation once its root-picking bug above stopped masking it:
a `filter_text` placeholder (`<program>`) that needs a JOINED table's
column (`STUDENT_PROGRAM.PROG_ID`), not the subject row's own --
`_resolve_placeholders` only ever looks at the subject row itself, a
real, disclosed scope gap, not attempted here.

**Corrected, re-verified coverage numbers, all 4 case studies (re-run
end to end 2026-09-24 with the FLEX2 fixture fix applied):**

| Case study | Objectives | Verified rule IDs | Verified coverage % | Unresolved decisions | Notes |
|---|---|---|---|---|---|
| OpenMRS | 71 | 37 | 52.1% | 5 | unchanged |
| Spree | 26 | 7 | 26.9% | 5 | unchanged; `Promotion Usage Limit Exceeded` still a disclosed fixture gap (see above entry) |
| jBilling | 40 | 11 | 28.2%* | 9 | unchanged from the earlier entry above |
| FLEX2 | 98 | 21 | 38.2%* | 7 | up from 0/0% -- first real FLEX2 result ever produced, via the 2 fixture/resolver fixes above |

*`verified_rule_coverage_percent` exactly as printed by `coverage.py`'s
own summary (not independently recomputed here; its own denominator is
not simply `verified_covered_rules / searchable_objectives`).

All 3 target decisions confirmed closed at the ground-truth/resolution
level (no unintended adds/removes anywhere in the compiled record set);
`Ageing Step Config Validation` compiles and resolves correctly but 0 of
its real cases currently select any of its rules -- a legitimate result
worth flagging, not evidence of a bug (its own 2 unresolvable rules,
`Rule_3`/`Rule_4`, are blocked by the pre-existing, disclosed
`isLastSelectedStep` `code_external` gap, unrelated to this fix).

**2026-09-24 (a third round): a merge/repair feasibility check, and one
more Spree decision closed via a new, disclosed override kind.**

A user question prompted a direct diagnostic before any further ground-
truth edits: does the search's own `branch_fitness` re-verify an
objective's fitness *after* `repair_candidate` runs on the merged
whole, or only before? Traced the actual call order in `dynamosa.py`:
`merge_archive_candidate` calls `repair_candidate` internally before
returning; re-evaluating fitness afterward is the CALLER's own
responsibility (`dynamosa.py`'s own `__main__` self-test does this
explicitly) -- and `tests/build_fixture_from_generator.py`'s `build()`
does NOT do it, discarding the pre-merge covered set it gets back
without ever re-checking post-repair fitness. Replicated that same
self-test pattern for Spree's real archive
(`Spree__dynamosa_nsga2__budget1x__seed0.pkl`, the one `spree_merged.db`
was built from): of 22/26 objectives search-covered pre-merge, only 1
regresses after merge+repair when `branch_fitness` is re-evaluated on
the actual merged, repaired candidate
(`Promotion Usage Limit Exceeded::rule_3`, post-merge fitness 0.6667).
**This is the important, disclosable result: at the search's own
fitness-function level, merge/repair interference explains only 1 of
Spree's ~15 missing rule IDs -- the rest of the objective-vs-verified-
rule gap is validator SCOPE (decisions it cannot check at all yet), not
evidence the search or the merge is systematically wrong.**

Separately, also confirmed by reading `fitness.py`/`dynamosa.py`
directly (correcting an earlier, wrong claim made in conversation before
checking the code): `branch_fitness` already includes a "no earlier row
also matches" suppression term for FIRST/UNIQUE hit policy
(`hit_policy_context.earlier_rows` + `distance_to_false`, summed into
the fitness value) -- this is not a missing piece of the fitness
function; a proposal to add it as a new, separate objective was dropped
once this was found, since it would have exactly duplicated an existing,
already-running mechanism. One real, narrower gap remains disclosed:
`earlier_rows` is only populated from rows *before* the current one, so
it isn't fully rigorous for UNIQUE hit policy (which needs "no OTHER row
matches," not just "no earlier one") -- not applicable to Spree, which
has zero UNIQUE decisions, so not investigated further here.

Of Spree's 5 unresolved decisions, 3 were assessed against the
disclosed-override mechanism used throughout this project; only 1 turned
out to be legitimately closeable that way:
- **`First-Order Promotion Eligibility` -- closed.** Its own
  dependency, the literal-expression decision `Prior Completed Order
  Count`, has a real DMN formula `feel_parser.py` cannot parse (a FEEL
  list comprehension with a filtered `count`), which degraded to an
  unevaluable `opaque_formula` node nested inside an otherwise-successful
  parse -- not caught by the existing `UnsupportedFeelConstruct`
  exception path at all, since the top-level parse "succeeds." A new,
  disclosed override mechanism, `generator/literal_expression_overrides.py`
  (same status/precedent as `join_disambiguation.py`, one level up the
  pipeline), lets `compile_constraints.resolve_and_substitute` swap in a
  hand-translated `{expression, free_variable_resolutions}` pair --
  reusing the SAME already-proven `derived_aggregate`/`filter_text`
  machinery, zero new runtime evaluation code -- before ever attempting
  the real parse. The hand translation itself is disclosed
  `[ASSUMED]`: `order.state = "complete"` is re-expressed as
  `completed_at IS NOT NULL` (no bare state/status column in this
  schema reads "complete"; `completed_at` is Spree's own real,
  well-known completion signal), and `order != currentOrder` as
  `id != self` (the formula's own subject row, already this decision's
  subject table). Re-run against the real database: 3 real cases now
  genuinely verify `rule_1`/`rule_2` via an actual `COUNT` query.
  Spree's `verified_covered_rules` rose from 7 to 9 (26.9% -> 34.6%),
  unresolved decisions from 5 to 4.
- **`Promotion Customer Group Eligibility` -- the first assessment here
  was ALSO too broad (a user challenge caught this one too), correctly
  split into two separately-diagnosed pieces, one closed for real, one
  still blocked but now for the true reason.** rule_2's own blocker
  (`promotionTargetGroupsConfigured`) and rule_3's (`promotionTargetGroupIds`,
  nested inside `matchingCustomerGroupCount`) had been conflated as one
  "blob" problem; they are not the same fact. `promotionTargetGroupsConfigured`
  only needs to know THAT a customer-group rule is configured, which is
  answerable from `spree_promotion_rules.type` -- a real, typed Rails STI
  discriminator column, not blob content at all. Re-mapped to an
  `exists`-kind check (`type = 'Spree::Promotion::Rules::CustomerGroup'`),
  which correctly compiled a NEW record (rule_2, Spree 26 -> 27 compiled;
  confirmed via full before/after diff: zero other adds/removes anywhere
  in any of the 4 case studies).

  Getting this to actually RUN surfaced two further, real, disclosed
  findings:
  1. A genuine bug in `db_resolver._substitute_self_and_colon`: its own
     `:column_name` self-reference regex matched INSIDE the type
     literal's own `Spree::Promotion::Rules::CustomerGroup` text (every
     `::` misread as a `:placeholder`), raising a spurious "no matching
     column" error for a token that was never meant to be a placeholder
     at all. Fixed with a negative-lookaround regex excluding `::`
     specifically; re-verified the existing legitimate `:column_name`
     usage (`Price Adjustment Tier Validity Violations`'s own
     `siblingTierCount`) still substitutes correctly.
  2. The REAL remaining architectural gap, now precisely isolated (not
     "no table exists," which was the earlier, too-broad framing): this
     decision's natural subject row (`spree_orders`) has no `promotion_id`
     column at all -- "the promotion" is never an explicit DMN input
     anywhere in this decision or its upstream chain, and the real link
     (`spree_order_promotions`, a genuine join table) was itself missing
     from the extracted schema's own `fk_columns` (confirmed: `spree_
     order_promotions`/`spree_promotion_rules` both `fk_columns: []`
     despite unambiguous real targets by Rails convention -- an
     already-disclosed, pre-existing Spree extraction gap, not new).
     Added `supplementary_fk_edges.py` (same status/precedent as
     `join_disambiguation.py`, for a MISSING edge rather than an
     ambiguous one) so `schema_utility.fk_edges` now knows about both
     real FKs. This closes the SCHEMA-GRAPH half of the gap, but
     `exists`-with-`filter_text` (`db_resolver.py`) only ever binds a
     `<placeholder>` to a SAME-NAMED column on the SUBJECT row itself --
     it has no mechanism yet to resolve a placeholder via a JOIN hop when
     the value lives on a different, joined table. Confirmed directly:
     `run_decision` now fails with the precise, honest error
     (`filter_text placeholder <promotion_id> ... not present on the
     subject row`) instead of the earlier vague `schema_gap` message.
     Extending `_resolve_placeholders`/`_substitute_self_and_colon` to
     walk a join path for a placeholder not found on the subject row
     would be a real, generalizable capability (useful beyond this one
     decision) but a genuine mechanism change touching shared, heavily-
     used code across all 4 case studies -- not attempted without
     confirming it's wanted first.

  Net, verified result: Spree's `searchable_objectives` rose to 27 (the
  new rule_2 record); `verified_covered_rules` stays at 9 (rule_2 still
  can't run yet); `unresolved_decisions` stays at 4, but this decision's
  own listed reason is now the true one, not the earlier, too-broad "no
  table backs this" framing. Re-verified: zero regressions across all 4
  case studies (identical OpenMRS/FLEX2/jBilling numbers; full
  regression suite unchanged).

**2026-09-24 (a fourth round): built the join-aware `filter_text`
placeholder mechanism, on request, after a user challenge correctly
pushed back on treating it as a bigger architecture change than it is.**
The pushback was right to make explicit: the actual gap has exactly two
separate parts, not one -- (1) a trivial DATA fact (which table a
placeholder's real value lives on), no different in kind from any other
ground-truth mapping in this project, and (2) a small, mechanical CODE
gap (`_resolve_placeholders` had no fallback path at all beyond the
subject row's own columns). Neither part alone needed new architecture;
only (2) needed writing.

Built as three additive pieces, in the SAME disclosed-override tradition
as `join_disambiguation.py`/`supplementary_fk_edges.py`:
- `filter_placeholder_sources.py`: `{(case_study, placeholder_name):
  table_name}`, one real entry (`('Spree', 'promotion_id'):
  'spree_order_promotions'`).
- `subject_table.tables_referenced()`: for `exists`/`derived_aggregate`
  with `filter_text`, now also includes any table this file names for
  one of the filter's own placeholders -- every placeholder with NO
  override (every currently-working case: jBilling's `entity_id`/
  `status_id`, Spree's own `price_list_id`/`user_id`/`email`) is
  completely unaffected, confirmed by the unchanged OpenMRS/FLEX2/
  jBilling numbers below.
- `db_resolver._resolve_placeholders`: tries the subject row first,
  exactly as before; only when a placeholder isn't there does it consult
  the override and fetch the value off the already-joined row via
  `_row_for_table` -- the SAME hop-walker every other cross-table kind
  already uses, reusing `schema_utility.build_join_path`'s own BFS/
  ambiguity-refusal machinery entirely as-is. `case_study` threaded
  through `resolve()`/`_resolve_one`'s existing call chain to reach it
  (both already had a `case_study` value in scope; this only forwards
  it, no new parameter-passing pattern).

**Confirmed working exactly as designed, against the real Spree data:**
`subject_table_for_decision` now picks `spree_order_promotions` as this
decision's root (not `spree_orders`) -- and correctly so, not merely as
a workaround: `_pick_root`'s existing algorithm finds `spree_orders`
cannot itself forward-reach `spree_order_promotions` (that direction is
backward/one-to-many, correctly refused), while `spree_order_promotions`
forward-reaches `spree_orders` in one real hop -- so the mechanism
naturally lands on the more correct per-(order, promotion) grain,
without any decision-specific special-casing. `run_decision` then fails
with `no such table: spree_order_promotions` -- the exact, disclosed
fixture gap flagged before building this (this decision's own PAYOFF
still needs that table added to the fixture, unchanged from the earlier
finding; the mechanism itself is what was being verified here).

**Locked in with a new, standalone regression test**
(`tests/test_spec_cases.py::test_case_11_filter_placeholder_via_join`,
an 11th case beyond the original 10-case spec) since the real Spree case
can't itself demonstrate success yet -- a synthetic `order`/`customer`/
`flagged_regions` scenario where `<region>` resolves via a real join
from `order` to `customer`, hand-verified end to end (`Rule_1`/`Rule_2`
selected correctly for two different real cases). Full regression suite
re-run clean; all 4 case studies' coverage numbers re-verified identical
to the previous round except Spree's own diagnostic message for this one
decision (now the precise fixture-gap reason, per above).

**2026-09-24 (a fifth round): a full audit of Spree's own rule inventory
(requested directly, not a bug hunt) turned up a real, fixable
compile-time bug -- a missing DMN `<variable>` declaration -- distinct
from every other gap found so far.** Auditing every one of Spree's 32
decision-table rules (9 tables; 4 more literal-expression decisions
contribute no rules of their own) confirmed `statically_infeasible_
rules: 0` -- not one Spree rule is logically dead; every blocked rule is
blocked by a missing INPUT, never a self-contradictory condition.

Of the 5 rules blocked at compile time, 4 (`Promotion Item Total
Eligibility`'s own rule_1-4) were blocked partly by `effectiveMinThreshold`/
`effectiveMaxThreshold` reading `unresolved`: "not a declared input... and
not produced by any DRD-linked upstream decision." But the DRD link DOES
exist in the DMN XML (`informationRequirement` to `Effective Minimum/
Maximum Amount Threshold`, confirmed by direct inspection) -- what's
missing is a `<variable name="...">` element on those two literal-
expression decisions themselves. `compile_constraints.py`'s own
`Decision.own_variable` is populated ONLY from that element
(`dec_el.find(q('variable'))`); without it, `resolve_and_substitute`
never learns what name the upstream decision's own formula produces,
so the (real, existing) DRD edge is silently invisible to substitution
-- not a data problem, a DMN-authoring omission, and an unambiguous one:
the expected name is stated verbatim in the very blocking-variable
message. Fixed by adding `<variable name="effectiveMinThreshold"
typeRef="number"/>` / `<variable name="effectiveMaxThreshold"
typeRef="number"/>` to `Promotion_Order_Level_Eligibility.dmn`, matching
the exact convention this same DMN corpus already uses for its OTHER
literal-expression decisions (`Customer_Segment_Eligibility.dmn`'s own
`Customer Group Match Count`/`Prior Completed Order Count`, both already
declared this way).

**Confirmed working as intended, not merely compiling differently:**
after the fix, `effectiveMinThreshold`/`effectiveMaxThreshold` resolve
via `substituted_decision` as designed -- but the underlying formulas
still need `operatorMin`/`amountMin`/`operatorMax`/`amountMax`, which
are the SAME undecoded-preferences-blob gap as `promotionTargetGroupIds`
elsewhere in Spree. So these 4 rules remain blocked, correctly, now
reading `schema_gap` instead of `unresolved` -- a deeper, truer
diagnosis, not a new failure. Re-verified via full before/after diff:
zero record adds/removes anywhere in any of the 4 case studies (Spree's
own compiled count stays 27/32); full regression suite and all 4 case
studies' coverage numbers unchanged (OpenMRS 37/71, FLEX2 21/98, Spree
9/27, jBilling 11/40).

**Also directly answered, on request, without any code change:** whether
Spree's remaining gaps could be closed by treating them as free,
assumable scenario values (the same technique already used for
`evaluationTime`). Checked systematically -- Spree originally had
exactly two genuinely `not_persisted` variables (`evaluationTime`,
already overridden; `purchaseQuantity`, since corrected to a real
column, not overridden) and today has ZERO remaining `not_persisted`
blockers. Every current gap is real backend data the pipeline hasn't
caught up to yet (the undecoded blob, 3 fixture-table gaps, one
validator hit-policy limitation) -- not a case where inventing a
scenario constant would be honest or applicable.

- **`Price List Volume Adjustment Tier Selection` -- the INITIAL
  assessment here was wrong, corrected after being challenged, and then
  actually fixed.** First pass wrongly trusted the ground truth's own
  existing `purchaseQuantity: not-persisted` classification at face
  value, reasoning from that (mistaken) premise that no real table
  column exists for "the quantity being priced," so closing it would
  need an arbitrary anchor table plus one fixed scenario constant,
  capping at most 1 of 3 rules verified by construction. Challenged (correctly):
  a real, persisted quantity for "the quantity being purchased" almost
  certainly exists on a real order line item, and the ORIGINAL ground
  truth's own "not-persisted" call was the actual error here -- the same
  species of mistake this exact CSV already had several corrected
  instances of (e.g. "real column is `user_id`, not `customer_id`").
  Checked the schema directly: `spree_line_items.quantity` is a real,
  persisted column. Corrected the ground truth from `not-persisted` to
  `direct` -> `spree_line_items.quantity` -- a confident, non-`[ASSUMED]`
  correction (an ordinary, well-established Spree domain column), not a
  disclosed guess. `subject_table_for_decision` now resolves this
  decision cleanly, anchored on `spree_line_items`, no scenario constant
  or arbitrary anchor needed -- since every real line item carries its
  own real, varying quantity, all 3 rules are genuinely independently
  verifiable in principle now, not capped at 1.
  **Real, disclosed result today: `spree_line_items` is not among the
  tables in the current `spree_merged.db` fixture** (same category as
  `Promotion Usage Limit Exceeded`'s missing `spree_discounts` --
  confirmed via the same `sqlite3.OperationalError`/`KeyError`
  per-decision handling added earlier this session, which correctly
  keeps this from crashing the report). So `verified_covered_rules`
  stays at 9/26 and `unresolved_decisions` stays at 4 -- unchanged in
  count, but this decision's own listed reason is now honestly
  "database/fixture gap" instead of the earlier, incorrect "no
  table-backed input at all." The ground-truth fix is real and correct;
  it will only pay off in a higher verified count once the fixture is
  rebuilt to include `spree_line_items` (out of this round's scope).

**2026-09-24 (a sixth round): built a general `serialized_field`
resolution kind, closing 4 of the 5 blocked `Promotion Item Total
Eligibility` rules -- on a user's design push-back that correctly
reframed the whole blob problem.** Earlier framing treated the
`spree_promotion_rules.preferences` blob as something to *decode after
the fact*; the user's proposal flipped it: teach the schema that the
column is structured, so the GENERATOR writes a well-formed blob on
purpose and the validator reads it back using the same declared format
-- no guessing on either end, since both sides agree by construction.

Confirmed the exact mechanism by cloning Spree's real source
(`spree/spree` on GitHub, a public repo, read via this session's own
git proxy) rather than continuing to speculate: `lib/spree/core/
preferences/preferable.rb` line 41, `serialize :preferences, type:
Hash, coder: YAML` -- mixed into every `PromotionRule` subclass via the
generic `Preferable` concern. Also read `item_total.rb` and
`customer_group.rb` directly for the real preference keys and defaults
-- catching two things the ground truth had wrong: `amount_max`'s real
default is `nil` (nullable), not the `1000.00` previously guessed, and
`amountMaxSet`'s earlier "genuinely uncertain, no way to check" verdict
was built on that same wrong premise -- it's a real, checkable existence
test after all. (One honest caveat surfaced too: the current cloned
source uses `order.customer_id`, but this case study's own schema has
no such column, only `user_id` -- version skew between the real
upstream repo and this snapshot, consistent with an already-disclosed
note; trusted the schema's own column name as before, not the fetched
source, for anything version-sensitive.)

Built as designed, across the full round trip:
- **Schema annotation**: `spree_promotion_rules.serialized_columns.
  preferences = {"format": "yaml_hash"}` in the real schema JSON.
- **`compile_constraints.py`**: a new `serialized-field` ground-truth
  bucket, parsed from `table.column[key]` / `table.column[key=default]`
  (e.g. `spree_promotion_rules.preferences[amount_min=100.0]`) into a
  `serialized_field` resolution node; an existence-check note (the same
  `_EXISTENCE_WORDS` trigger `direct`'s own null_check path already
  uses) instead reuses `null_check` directly with an added `key` field,
  rather than inventing a parallel "is this set" kind.
- **Search-time fitness evaluation (`fitness.py`) needed ZERO changes**
  -- confirmed by reading `evaluate_resolution` directly: every leaf
  kind is already a flat `genome[var_name]` lookup, completely decoupled
  from table/column structure, so a new kind rides for free there.
- **`candidate.py`'s `derive_value`** (genome ← real candidate, in
  memory): reads the nested dict already sitting on the row; a
  `null_check`-with-`key` variant checks presence with NO default
  substituted (existence must reflect what THIS row's blob actually
  set).
- **`mutation.py`'s `_apply_field_mutation`** (mutation → candidate):
  writes into a nested dict one level under a plain column
  (`row.setdefault(column, {})[key] = value`), added to
  `FIELD_LEAF_KINDS`; the `null_check`-with-`key` variant pops/sets a
  placeholder to represent absent/present.
- **`materialize.py`**: the ONE place serialization actually happens --
  `serialize_yaml_hash_blob` turns a dict-valued column into real YAML
  text (colon-prefixed keys, matching Psych's own rendering of a
  symbol-keyed Ruby Hash) only at `to_sql_inserts` time; everywhere else
  in the search it's an ordinary-looking Python dict.
- **`db_resolver.py`**: an independent read-side implementation of the
  SAME convention (never imports `materialize.py`, this project's own
  separation rule) -- parses the real column's raw YAML text and pulls
  out the named key, falling back to the ground-truth-declared default.

**Locked in with a new, permanent round-trip test**
(`tests/test_serialized_field_roundtrip.py` -- the second file, after
`build_fixture_from_generator.py`, explicitly allowed to import
generator/ code): a real mutation writes a value, `materialize.py`
turns it into real SQL, and `db_resolver.resolve` reads it back
independently, plus both default-fallback edge cases (an unset key, a
NULL blob). All three pass.

**Real, verified result:** Spree's compiled count rose from 27/32 to
31/32 (all 4 `Promotion Item Total Eligibility` rules now compile;
confirmed via full before/after diff: zero adds/removes anywhere else
in any of the 4 case studies). Deliberately left `Promotion Customer
Group Eligibility::rule_3`'s own `promotionTargetGroupIds` OUT of this
round's scope on purpose -- it's a LIST-typed fact needing FEEL
`intersection`/`count` over two lists, a materially different, larger
piece of work than the scalar preferences closed here.

**Confirmed, not just hoped for: this closes the COMPILE gap but not
the RUN gap, exactly as flagged before building it.** `subject_table_
for_decision` still can't find a root reaching both `spree_orders` and
`spree_promotion_rules` -- the same one-to-many "which promotion_rules
row" problem already known from `Promotion Customer Group Eligibility`.
`Promotion Item Total Eligibility` now shows up as a NEW unresolved
decision (5 total, was 4) for exactly this reason, not a crash.
`searchable_objectives` rose to 31; `verified_covered_rules` stays at 9
-- the mechanism is real and proven (via the standalone round-trip
test), but this specific decision's own payoff still needs the
row-finding half solved too, same as `Promotion Customer Group
Eligibility` and the earlier fixture-table gaps. Re-verified: zero
regressions across all 4 case studies (identical OpenMRS/FLEX2/jBilling
numbers; full regression suite, including the new round-trip test,
unchanged/passing).

## Why this exists

Everything the search produces and reports as "coverage" — archive
coverage, final-population coverage, merged-archive coverage (see
`generator/DECISIONS_EXPERIMENT.md`) — is **search coverage**: an
objective is "covered" when the search's own compiled fitness objective
reaches 0. That is a legitimate measure of the *optimizer's* performance,
but it is not, by itself, evidence that the original DMN rule was
actually exercised by the generated database. Two distinct circularity
risks motivate an independent check:

- **Risk 1 — reading the search's own in-memory/cached state instead of
  the real database.** Confirmed as a real, live phenomenon this
  session, not hypothetical: the OpenMRS merge-regression finding
  (`generator/DECISIONS_ALGORITHM.md` §8) is a concrete case where
  archive/search coverage said "covered," but a fresh recomputation from
  the actual merged, materialized database says the condition no longer
  holds (a key-offset renumbering broke a literal-value comparison).
  Nothing in the current pipeline independently re-checks this — it was
  only found because we happened to diff the two by hand.
- **Risk 2 — the compiled `condition`/`variable_resolution` itself being
  a mistranslation of the original DMN/FEEL text** (e.g. `>=` compiled to
  `>`). This risk lives in `feel_parser.py` + `compile_constraints.py`'s
  own classification logic (Phase 1), upstream of both the search and any
  validator that reuses that same compiled structure.

This validator is designed to close **Risk 1 fully**. It does not close
Risk 2 — see "Independence levels" below for why, and what closing Risk 2
would additionally require.

## Architectural separation requirement

This is a hard constraint, not a preference: **no overlap in function
calls with the search approach**, with one narrow, explicit exception.

- **Never imported/called by this validator:** `fitness.py`,
  `evaluate_objective` (dynamosa.py), `dynamosa.py`/`dynamosa_preference.py`
  generally, `candidate.py`'s in-memory `Candidate`/`focal_maps`/
  `scenario_maps` objects, `_OWNER_KEY`/search-time row tagging of any
  kind. The validator only ever reads a materialized database (a real
  file on disk) plus the DMN model and schema — never the search's
  in-process state.
- **The one exception:** Phase 1's compile-time resolution metadata
  (`variable_resolution`, `fk_closure_tables`, `condition`,
  `hit_policy_context`, `grounded_upstream_branches`, all produced by
  `compile_constraints.py`/`feel_parser.py`). This is legitimate to
  reuse — it is declarative metadata about what each rule's inputs *are*,
  built once at compile time before any search runs, not a search-time
  computed value or verdict. Reusing it is analogous to a test harness
  reusing the specification under test, not reusing the system under
  test's own answer.
- **How the exception is consumed:** via a small, dedicated utility
  module in this folder (not yet named/built) that reads
  `compiled_constraints.json` directly — never by importing anything
  from `generator/` at runtime. This keeps the dependency one-directional
  and inspectable: `validation_oracle/` reads a JSON file `generator/`
  happens to produce; it does not import `generator/`'s Python modules.

## Independence levels considered, and the recommendation

Three levels of "independent," from cheapest to most complete:

- **Level A (recommended starting point):** reuse Phase 1's compiled
  `condition`/`variable_resolution`/`hit_policy_context` (the one
  exception above). Build a new, separate SQL-based value resolver and
  rule-selector that never touches `fitness.py`/`evaluate_objective`.
  Closes Risk 1 fully. Does not close Risk 2.
- **Level B:** additionally write a second, independently-implemented
  FEEL evaluator that re-parses the raw `<inputEntry>`/`<outputEntry>`
  text directly from the DMN XML, never calling `feel_parser.py`. Closes
  Risk 2 as well. Meaningfully more engineering — a second interpreter
  for the FEEL subset actually used across the four case studies
  (comparisons, and/or, `count()`/`intersection()`, literals).
- **Level C (external DMN engine):** not recommended. No mature
  Python DMN+FEEL engine exists with the coverage this project needs;
  the strong engines (Camunda, jDMN) are JVM, requiring a subprocess/JVM
  bridge. It also does not solve the actually novel, hard part of this
  problem: no external engine knows how to derive DMN inputs from a
  relational database — `raw_sql_boolean`, `derived_join_count`,
  `chained_decision_output`, `not_persisted` are this project's own
  extensions with no standard-DMN equivalent. That resolver layer must be
  hand-built regardless of which engine evaluates the FEEL logic, so an
  external engine buys comparatively little here.

**Decision: build Level A first.** Disclose in the paper that it closes
Risk 1 (chromosome-vs-real-database circularity) but not Risk 2
(compile-time FEEL-translation correctness), with Level B named as
future work if a reviewer specifically presses on it.

## No anchoring, no search-time tagging

Explicit design constraint, confirmed directly: **the validator does not
use `_OWNER_KEY`/`focal_maps`/any row tagging the search produced.**
Given only a materialized output database and the DMN model, it must
determine independently which rules fire.

**Mechanism:** a DMN decision is evaluated once per real-world "case"
(one patient, one order, one customer). Rather than trusting one
pre-selected row, the validator:

1. Determines each decision's **subject table** — the table whose rows
   represent "one case" for that decision — derived from Phase 1's own
   `variable_resolution`/`fk_closure_tables` (the legitimate exception
   above), not from any search-time metadata.
2. Queries the live materialized database for every distinct primary key
   actually present in that subject table.
3. For each one, independently resolves every input (fresh SQL — see
   below), evaluates the DRD chain in dependency order (upstream
   decisions first, for that same case), applies FIRST/UNIQUE hit-policy
   semantics, and records the selected rule.
4. Across all real cases found in the database, a rule counts as
   **verified covered** if it was selected for at least one of them.

This is deliberately stronger than anchoring to one search-engineered
row: it asks "does this database, examined with no instructions from the
search process, cause rule R to fire for anyone in it" rather than "does
the row search built for objective R still work." It also settles
duplicate-decision-output coverage for free, since coverage is tallied by
selected rule ID across real cases, never by trusting a single row's
intended purpose.

**Open design question, not yet resolved:** deriving each decision's
subject table, and how to follow an FK path from an upstream decision's
own subject table to a downstream decision's subject table when they
differ (e.g. "per patient" upstream, "per patient_identifier row"
downstream). The raw material for this already exists
(`fk_closure_tables`, the schema's own declared FKs) but is not yet
organized as "subject table + join path per decision."

## Per-resolution-kind → live SQL translation

For each `variable_resolution` kind found in `compiled_constraints.json`,
given a known subject-table row (identified in step 2 above, not
anchored):

| Kind | Live query |
|---|---|
| `schema_column {table, column}` | `SELECT column FROM table WHERE <pk> = ?` |
| `null_check` | same, then `IS NULL` / `IS NOT NULL` |
| `derived_aggregate` / `derived_join_count` | `SELECT COUNT(*)` / `SELECT SUM(col)` grouped by the subject row's FK — must count real rows in the live database, not an intended count |
| `exists` | `SELECT EXISTS(SELECT 1 FROM table WHERE <filter>)` |
| `join_lookup` | real `JOIN` following the FK chain from the subject row |
| `raw_sql_boolean` | the resolution already stores a literal SQL template — execute it directly against the live connection |
| `chained_decision_output` / `substituted_decision` | not a database read — the upstream decision's real, freshly-evaluated output, obtained by running that decision through this same pipeline first (never injected) |
| `not_persisted` | **cannot be queried from the database — no table/column exists for it.** Must be carried over from the declared test-scenario input, explicitly logged as "not database-derived." See "known gaps" below. |
| `regex_match` | query the column fresh; the regex pattern itself (declarative rule content) may be reused, the value being matched may not |
| `literal` | fixed, no query |

## DRD-ordered execution

Walk decisions via the DMN XML's own `<informationRequirement>` elements
(plain structural re-walk, not a translation concern — safe to
re-derive independently or reuse, since it is not semantic FEEL content).
For a downstream decision needing an upstream chained/substituted value:
evaluate the upstream decision's own rule table first for the relevant
case, obtain its real selected output, then feed that into the downstream
decision's own input resolution. Never inject an assumed/expected
upstream value.

## Rule selection semantics

- **FIRST:** evaluate rules in table order; multiple rules may match;
  only the first matching rule is selected; coverage counts the selected
  rule only, not every matching rule.
- **UNIQUE:** validate that at most one rule matches. If more than one
  matches, this is recorded as a **validation error / semantic
  violation**, not silently resolved by picking one.
- The validator distinguishes matched rule IDs, the selected rule ID, and
  the decision output — never identifies a rule by its output value alone
  (two rules can share an output value).
- **DRD fan-out variants.** A decision can have several compiled records
  sharing one `rule_id` but DIFFERENT `condition`/`variable_resolution`
  — one per possible upstream branch a `literal_via_upstream_branch`
  input could be chained on (`compile_constraints.py`'s own
  `_grounding_options`). `run_decision` tries EVERY variant of a
  `rule_id` independently for each real case, never a merged union of
  their `variable_resolution` (found and fixed 2026-09-24 — merging
  silently collapsed to one arbitrary variant's own definition,
  corrupting evaluation for any decision with more than one variant per
  rule; see "Implementation status" above). A rule_id counts as matched
  if ANY of its own variants both grounds (no `UngroundedForCase`) and
  evaluates true; a variant that fails to ground (including a per-row
  data-quality gap like `derived_case` hitting an uncovered real value)
  simply doesn't count as matched for THAT variant — every other variant
  of the same rule, and every other rule, is still tried for the same
  real case.

## Known gaps (disclose, do not paper over)

- **`not_persisted` inputs** have no database representation by
  definition — a scenario bind-parameter, not a stored fact. The
  validator cannot independently re-derive these from the database; any
  rule depending on one is validated with that one input taken from the
  declared scenario, explicitly flagged in the trace output as
  not-database-derived, never silently treated as fully verified.
- **Literal-expression decisions** (`<literalExpression>`, e.g. Spree's
  `Decision_CustomerGroupMatchCount`) are not decision tables — no hit
  policy, no rule ID, just a value-producing function. The DRD-ordered
  executor must treat these as pass-through steps distinct from
  rule-selecting decision-table steps.
- **Risk 2 (FEEL mistranslation) is not closed by Level A** — see
  "Independence levels" above.

## Output schema (per the agreed specification)

Three artifacts, machine-readable, one row per objective/decision/run as
appropriate:

- `objective_results.csv` — case_id, algorithm, run_id,
  construction_strategy, objective_id, decision_id, rule_id, rule_index,
  hit_policy, best_search_fitness, search_covered, verified_rule_selected,
  first_generation_covered, agreement_class (the four-way
  confirmed/false-positive/false-negative/agreed-uncovered
  classification).
- `validation_summary.csv` — case_id, algorithm, run_id,
  construction_strategy, total_dmn_rules, statically_infeasible_rules,
  searchable_objectives, search_covered_objectives, verified_covered_rules,
  search_coverage_percent, verified_rule_coverage_percent,
  coverage_retention_percent, schema_valid, dmn_validation_valid,
  total_rows.
- `decision_trace.json` — per decision evaluation: case_id, algorithm,
  run_id, decision_id, decision_name, resolved_inputs (with
  resolution_type and source table/row), upstream_decision_results,
  matched_rule_ids, selected_rule_id, decision_output, hit_policy — the
  artifact that makes "why was/wasn't rule R selected" inspectable.

## Terminology discipline

Per the standing project convention: objectives that survive Phase 1's
feasibility filter are **"searchable objectives"** or **"objectives
retained for search,"** never "feasible objectives" — the feasibility
check is three-valued (true/false/unknown), and only proven-infeasible
objectives are removed. An objective that is searchable but never
verified covered may be a real search/validation gap, or an
undetected-infeasible objective; this ambiguity is a threat to validity
to disclose, not to resolve by terminology alone.

## Open issues

- Subject-table/grain derivation per decision (see above) is not yet
  designed in enough detail to implement — needs a concrete pass over
  each case study's decisions before Step 3 (interfaces) can be finalized.
- No decision yet on whether the utility module that reads
  `compiled_constraints.json` lives entirely inside `validation_oracle/`
  or is a genuinely shared, versioned artifact both `generator/` and
  `validation_oracle/` depend on without either importing the other's
  code.
- Level B (second FEEL evaluator) scope is not estimated in detail.
- No test fixtures exist yet for the ten test cases specified (FIRST
  precedence, FIRST fallthrough, UNIQUE selection, UNIQUE violation,
  correct/incorrect upstream dependency, aggregate input, join-based
  input, merge-induced regression, duplicate-output disambiguation).
