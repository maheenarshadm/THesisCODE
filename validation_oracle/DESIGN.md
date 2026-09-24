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
- **`Promotion Customer Group Eligibility` -- assessed and declined,
  not a bug or an oversight.** Its own blocker traces deeper than the
  existence-check ambiguity it first looked like: `matchingCustomerGroupCount`
  needs the promotion's own list of targeted customer-group IDs, which
  lives only inside a serialized preferences blob with NO real,
  normalized table backing it at all (unlike every other disclosed fix
  in this project, which reused REAL, existing columns with a merely
  under-encoded correlation). Closing this would mean inventing a join
  against a table structure that does not exist in the real schema, not
  disclosing an assumed filter on real ones -- a materially different,
  larger claim than this project's own `[ASSUMED]` discipline has made
  anywhere else. Left disclosed and unresolved rather than fabricated.
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
