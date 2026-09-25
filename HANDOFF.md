# Project handoff

## Latest continuation — 2026-09-25 (Claude, Attendance Eligibility audit)

Audited FLEX2's `Attendance Eligibility For Final Exam` for the same kind
of mis-mapping `purchaseQuantity`/`semesterType` turned out to be — NOT a
mis-mapping (already correctly modeled as a `substituted_decision`), but
fixed real subject-picking (same shape as `Summer Semester Registration`
— new `('FLEX2', 'student'): 'COURSE_REGISTRATION'` placeholder-source
entry on both validator and generator sides) plus FOUR real, generalizable
bugs found along the way, all fixed: (1) a hand-translation of informal,
non-SQL ground-truth prose into a real subquery (new, disclosed
`generator/aggregate_filter_overrides.py`); (2) that override was silently
never applied at all, because `resolve_variable` has two separate code
paths that can produce a `derived_aggregate` node and only one of them
consulted overrides — fixed by unifying both into one `_apply_aggregate_
overrides` helper; (3) `candidate.py`'s own IN-subquery bridge hardcoded a
bare `'id'` lookup instead of using the subquery's own real `SELECT <col>`
name — correct only for Spree's Rails-convention PK naming, silently
under-counting to 0 for FLEX2's own named-PK convention (`LECTURE_ID`);
(4) fixing #3 exposed a latent bug where `_construct_subquery_parent`'s
own `self_table` branch fired whenever a non-`None` `self_table` was
passed at all, never checking whether the inner WHERE actually references
`self` — stamped a schema-invalid `id` column onto a real row. Also fixed
a real, generalizable bug in `validation_oracle/rule_evaluator.py`: its
own arithmetic operators didn't propagate FEEL `null` consistently (only
`/` guarded, incompletely), so a real zero-lecture course offering crashed
the WHOLE decision with an uncaught `TypeError` instead of correctly
evaluating to `null`.

Net result: the decision now resolves and runs cleanly against the real,
committed fixture (`unresolved_decisions` 2→1) — genuinely 0/2 verified
for a confirmed, disclosed, non-bug reason (the fixture's own real
`LECTURE` and `COURSE_REGISTRATION` data are disconnected islands, zero
overlap). Confirmed via a fresh `solve_branch` run that BOTH rules ARE
genuinely solvable with correct, connected data — but reflecting that in
the committed fixture hit a separate, undiagnosed gap in `dynamosa.py`'s
own `merge_archive_candidate` (a from-scratch rebuild from just these
patched objectives loses the `STUDENT_ATTENDANCE` table entirely), not
fixed here — the real fixture was left untouched. Full writeup in
`KNOWN_ISSUES.md`'s own newest entry.

## Latest continuation — 2026-09-25 (Claude, after Codex's subject-wiring fix)

Fixed the "prior-count self-inclusion" issue Codex's own entry below
flagged as unresolved: `priorRegistrationCount`'s filter always matched
its own subject row, so it could never read 0. New, disclosed
`generator/aggregate_self_exclusions.py` appends an `OFFER_ID != :OFFER_ID`
exclusion conjunct (real schema justification: two different offerings of
the same course for the same student is exactly what "a prior
registration" means); also generalized the generator's own fitness bridge
to understand `COLUMN != :COLUMN` self-exclusion, not just self-equality.
Confirmed via `solve_branch`: `priorRegistrationCount` now genuinely
resolves to 0. `Rule_2` still doesn't fully verify — blocked by the
SEPARATE, already-known `isNeededToGraduateThisSummer` no-mutation-support
gap — so the committed fixture's own verified count is unchanged at 37/55
(confirmed via full regression, zero flips). Full writeup in
`KNOWN_ISSUES.md`'s own newest entry, directly above Codex's.

## Latest continuation — 2026-09-25 (Codex)

Generator-side Summer Semester Registration subject wiring is now fixed and
independently verified: Rule_1 changed from false positive to confirmed.
The committed FLEX2 fixture now verifies 37/55 distinct rules (67.3% raw,
37/53 = 69.8% under the existing solvable-rule denominator). Summer itself is
1/5, not fully closed. Read the newest KNOWN_ISSUES.md entry for the unresolved
repeat-request identity, prior-count self-inclusion, raw-SQL mutation and
fresh-archive fixture-completeness issues. These supersede the missing-subject
status in historical items 18 / section 7 below. The saved search archives are
unchanged. Changes are on the user-requested Claude branch; rollback checkpoint
is 6a9b80151d277e2958ac90a3146919758b45007d (codex/thesis-fixes).


**Purpose of this file:** the single entry point for picking this project
back up — in a new session, with a different LLM, or after time away —
without re-explaining the project from scratch. It answers: what is
this, what's been decided and why, what's been done, what's next, and
what's genuinely hard about it. Deep detail lives in the files this
document points to; this one stays a map, not the territory.

**Maintenance rule:** update this file whenever a decision, a completed
action, a plan, or a challenge changes materially — not on every commit,
but whenever an LLM picking this file up cold would otherwise be missing
something a person would want to tell them. Keep it concise; push detail
into the linked files instead of inlining it here.

**Repo:** `maheenarshadm/THesisCODE`, branch `claude/clever-maxwell-dr0vnl`.

---

## 1. What this project is

A research pipeline that generates synthetic relational test data for
real, DMN-governed systems, using search (a DynaMOSA-based evolutionary
algorithm), and then **independently verifies** how much of the claimed
coverage is real — via a second, separately-built "validation oracle"
that never trusts the search's own bookkeeping and re-derives everything
from real SQL against the materialized database.

Four independently-sourced case studies, each a real open-source system
with its own real relational schema and its own DMN decision tables
(business rules extracted from that system's real logic, chained into a
Decision Requirements Diagram where one decision's output feeds another):

- **OpenMRS** — open-source medical records system
- **FLEX2** — university academic-regulations system
- **jBilling** — billing system
- **Spree** — e-commerce platform

**The research question:** for a data-intensive system governed by
business rules, does a search-based generator actually construct data
that exercises those rules — and when it claims to, is that claim real?
The whole point of the second half (the validation oracle) is to catch
the search overclaiming, not just to report a number.

## 2. Repo map

```
generator/            The search side (DynaMOSA). Generates candidate databases.
  compile_constraints.py   DMN + hand-curated CSV -> one compiled JSON record per rule
  candidate.py              Candidate/genome representation, derive_value (read), seeding
  mutation.py               Mutation operators (M1 field, M2 row-count), AVM step search
  fitness.py                Branch-distance fitness function (the DMN term)
  dynamosa.py / dynamosa_preference.py / random_baseline.py   Search algorithms
  materialize.py            Candidate -> real SQL DDL/INSERT
  literal_expression_overrides.py / (validation_oracle/)join_disambiguation.py /
  supplementary_fk_edges.py / filter_placeholder_sources.py
                             Disclosed, human, inspectable overrides (see §4)
  compiled_constraints.json / compile_report.json   Generated output, checked in
  experiment_runs/          Saved search archives (.pkl + .json) per case study/algorithm/budget
  README.md                 Chronological build log (long, detailed)
  DECISIONS_ALGORITHM.md    Algorithm decisions register (representation/mutation/etc.)
  DECISIONS_EXPERIMENT.md   Evaluation/experiment design decisions register

validation_oracle/    The independent verification side. Never imports search internals
                      for the actual verification path (only optionally, for the
                      search-vs-verified comparison column).
  db_resolver.py            Reads a real fact off a real materialized row via real SQL
  subject_table.py          Picks which table to enumerate real cases over
  rule_evaluator.py         DMN rule selection (FIRST/UNIQUE; COLLECT NOT supported)
  drd_executor.py           Runs a full decision (handles substituted_decision chains)
  coverage.py               Aggregates verified vs search-claimed coverage, writes CSVs
  DESIGN.md                 Chronological build log (long, detailed)
  KNOWN_ISSUES.md           Open/Fixed issues tracker -- READ THIS for current gaps
  COVERAGE_REPORT.md        Recorded coverage numbers -- READ THIS, don't recompute
  tests/                    Regression suite + fixtures/ (one real merged SQLite DB per case study)

<case_study>_dmn/ (spree_dmn/, openmrs_dmn/, and jbillingandflex/{flex2,jbilling}_dmn/)
  dmn/                      The real DMN decision-table XML sources
  provenance/variable_to_schema_mapping.csv   Hand-curated ground truth: DMN variable -> real schema fact

all_schema_extraction/all_schema_extraction/output/  Extracted real schema JSON per case study

docs/                 Higher-level narrative writeups (may lag behind the latest
                      session's numbers -- check dates/numbers before trusting over
                      KNOWN_ISSUES.md / COVERAGE_REPORT.md):
  complete_approach_writeup.md, generationalgorithmdesign.md,
  dmn_to_schema_mapping.md, challenges_and_solutions.txt

QUICK_REFERENCE.md    FAQ + "where do I find X" index + glossary. Check this before
                      re-searching the repo for something already answered.

RULE_TO_OBJECTIVE_MAPPING.md   Exactly how one DMN rule becomes one (or several)
                      compiled objectives -- the full resolution-kind taxonomy
                      with real examples, and the chaining mechanism that
                      produces multiple objectives from one rule. Read this for
                      "what exactly is the compiler doing," not just the summary
                      in §3 below.
```

## 3. Core pipeline, briefly

1. **Compile**: `compile_constraints.py` reads each case study's DMN
   files + its own `variable_to_schema_mapping.csv`, and emits one JSON
   record per DMN decision-table rule (`compiled_constraints.json`) — a
   structured condition tree plus a `variable_resolution` map (how each
   free variable maps to a real schema fact: `schema_column`,
   `null_check`, `derived_aggregate`, `serialized_field`, `exists`,
   `join_lookup`, `not_persisted`, ...). A rule that can't be resolved is
   `blocked`, not silently dropped (`compile_report.json` names why).
2. **Search**: `dynamosa.py`/`dynamosa_preference.py` run a many-objective
   evolutionary search — one branch-distance fitness function per
   compiled rule (`fitness.py`), mutated via `mutation.py`'s field/row
   operators — against a shared population, saving the best-ever
   individual per rule into an archive (`experiment_runs/*.pkl`).
3. **Materialize**: `build_fixture_from_generator.py` merges every
   covered rule's own best individual into one shared candidate and
   writes it out as a real SQLite database (`tests/fixtures/*.db`).
4. **Verify, independently**: `coverage.py` re-enumerates real rows from
   that database, re-resolves every fact via real SQL
   (`db_resolver.py`), re-runs DMN rule selection (`rule_evaluator.py`,
   `drd_executor.py`), and reports what's *actually* true — compared
   against what the search *claimed* — writing `objective_results.csv`
   / `decision_trace.json` / `validation_summary.csv`.

## 4. Key decisions and why

- **Radical honesty over completeness — the project's own standing
  ethos.** Never fabricate ground truth. Every guess is marked
  `[ASSUMED]` (a disclosed researcher call, not verified against a real
  sample) vs `[CONFIRMED]` (checked against real source, e.g. Spree's
  actual GitHub source was cloned and read directly rather than guessed
  at). A negative or mixed result gets reported as such, not massaged.
- **Disclosed-override files, never silent guessing**, for anything
  needing human domain judgment the mechanical pipeline can't resolve on
  its own: `join_disambiguation.py` (ambiguous FK columns),
  `supplementary_fk_edges.py` (missing FK edges the extractor didn't
  find), `filter_placeholder_sources.py` (which table a filter
  placeholder comes from when not on the subject row),
  `literal_expression_overrides.py` (hand-translated FEEL formulas the
  parser can't handle). Each override is a named, reviewable entry, not
  a heuristic buried in code.
- **The validation oracle is architecturally independent of the
  generator.** It re-derives every fact from real SQL rather than
  trusting the search's own bookkeeping — that's the whole point (a
  search claiming 90% coverage while independent verification finds 45%
  is the actual research finding, not a bug to explain away).
- **COLLECT hit policy is out of scope**, not implemented
  (`rule_evaluator.py` only handles FIRST/UNIQUE). Explicitly excluded
  from all coverage numbers everywhere rather than silently dragging a
  denominator down.
- **Blob-level data generation is out of scope, by explicit decision
  (2026-09-24).** Deliberately generating/verifying a value at the
  granularity of one key inside a serialized column's own content (e.g.
  Spree's `spree_promotion_rules.preferences` YAML blob) goes beyond
  this project's intended scope — resolving data-backend dependencies at
  the row/column level, not decoding attribute-level structure within a
  column — even where the schema/format is fully known. The mechanism to
  do it (`serialized_field`, a real resolution kind) was already built
  and stays in the codebase, but is not being extended or exercised
  further; the rules that only verify via it are tracked as out of scope,
  not pending work. See `validation_oracle/KNOWN_ISSUES.md`'s
  scope-decision entry.
- **"Rule" and "objective" are usually but not always the same
  count** — see `QUICK_REFERENCE.md`'s glossary. This tripped up a
  coverage report once already; check it before quoting a denominator.

## 5. Current status

**Don't recompute — read `validation_oracle/COVERAGE_REPORT.md`
first.** Per explicit instruction, coverage numbers are recorded there
after each real run, and a coverage question gets answered from that
file's last recorded values, not a fresh `coverage.py` invocation,
unless a re-run is explicitly requested.

Latest recorded snapshot (see that file for the full table and
provenance): raw verified coverage OpenMRS 59.2%, Spree 58.1%, FLEX2
58.2%, jBilling 25.6%; solvable-rules coverage (excluding COLLECT,
`code_external` facts, and the out-of-scope blob-level rules) OpenMRS
75.0%, Spree 81.8%, FLEX2 60.4%, jBilling 66.7%.

## 6. Recent actions (most recent session)

Chronological detail lives in `validation_oracle/KNOWN_ISSUES.md`'s
"Fixed issues" section and `DESIGN.md`. Brief summary:

1. Built the `serialized_field` mechanism (schema-declared YAML blob
   read/write, confirmed against Spree's real source) — closed 4 of 5
   originally-blocked Spree facts at compile time.
2. Re-ran the Spree DynaMOSA search against the refreshed ground truth
   for the first time — surfaced and fixed 3 real, generic (not
   Spree-specific) generator bugs along the way (a seeding gap for the
   new resolution kinds, a raw-arithmetic crash on a legitimately-null
   operand, a SQL-tautology `1=1` misparsed as a column literally named
   `"1"`).
3. Fixed 3 specific open Spree issues on request: `One-Use-Per-User
   Promotion Eligibility::rule_2` (re-expressed a compile bug),
   `Promotion Temporal Availability::rule_2` (a real DMN authoring bug —
   `expiresAt > expiresAt`, a tautology), `First-Order Promotion
   Eligibility::rule_3` (a shadowing gap that turned out to be a real
   generator/validator mismatch — the mechanical filter-text parser
   didn't understand `IS NOT NULL` or OR-groups).
4. Found and fixed a significant, independent bug while chasing #3:
   `db_resolver.py`'s `null_check` resolution was flatly inverted
   relative to the generator's own canonical definition, affecting 54
   compiled records across all 4 case studies. Fixed at the root with a
   `negate` flag set at compile time for the (rare) opposite-polarity
   facts, verified via a full before/after diff of exact verified-rule
   sets across all 4 case studies before trusting it.
5. Created `KNOWN_ISSUES.md` and `COVERAGE_REPORT.md` as living
   trackers; corrected a real error in the latter (objectives vs.
   distinct DMN rules, see §4) after a user double-check caught it.
6. Built the `COLUMN IN (SELECT ... WHERE ...)` construction mechanism
   (`generator/aggregate_self_table.py`, extensions to `candidate.py`/
   `mutation.py`), closing all 8 of Spree's originally search-claimed-
   but-never-verified rules across two decisions (`Promotion Usage
   Limit Exceeded`, `One-Use-Per-User Promotion Eligibility::rule_3`).
   Two supporting fixes found chasing it: a real schema-extraction gap
   (`fk_columns: []` where real FKs existed) hit THREE separate times
   (`spree_order_promotions`/`spree_promotion_rules`,
   `spree_discounts`, `spree_promotion_actions`), and a `materialize.py`
   gap where a row missing its own table's surrogate key was left for
   SQLite's own NULL-rowid auto-assignment, which could silently
   collide with this pipeline's own explicit offset-derived ids (fixed
   pipeline-wide with an explicit surrogate-key fill). Spree: 14→18
   verified rules.
7. Investigated why FLEX2's `literal_via_upstream_branch`-chained
   objectives (55 FLEX2, 2 jBilling) never verify despite the search
   claiming coverage — an initial diagnosis blaming the search's own
   fitness function was WRONG and retracted (the compiler already
   correctly ANDs the upstream rule's condition in at compile time,
   confirmed by inspecting the real compiled record). The actual bug:
   a case-sensitivity mismatch in `drd_executor.py`'s cross-decision
   join lookup (`upstream_subject_value`), comparing schema-declared
   uppercase column names against real lowercase SQLite row keys with
   no `.lower()` — every cross-decision lookup silently failed. Fixed;
   verified directly against real data. That fix unmasked a second,
   separate, previously-unreached validator gap: `derived_case` (a
   categorical column mapping) was never implemented in
   `db_resolver.py`'s `resolve()` at all — implemented the same day, a
   direct port of `candidate.py`'s own existing logic. Net effect: both
   validator bugs are now fixed and verified, but the FLEX2/jBilling
   verified-rule counts don't move — `Course Load Limit` is no longer
   stuck in `unresolved_decisions` (every one of its 11 objectives now
   gets a genuine, complete evaluation for the first time), but it's
   still 0/11 verified, now for a real, disclosed, generator-side
   reason (the search's own merge never aligns all 4 of this composite
   record's own independent leaves onto one consistent real subject) —
   out of this investigation's own scope, not pursued further.
8. Investigated and fixed the "generator-side leaf-alignment gap" #7
   flagged above — turned out to be a more structural problem than
   "values don't align": `dynamosa.py`'s own per-objective row
   construction has zero concept of a decision's real DMN subject
   table, driven entirely by which tables a leaf reads. Checked every
   decision in every case study for this shape; found it in exactly 2
   (FLEX2's `Course Load Limit`, OpenMRS's `Identifier Uniqueness
   Check` — a third suspect, Spree's `Promotion Customer Group
   Eligibility`, turned out to be a genuine one-to-many backward-join
   gap once a real bug in `subject_table.py` was found and fixed, see
   below). Fixed by extending `compile_constraints.py` with a new
   `decision_subject` compile-time field (a generator-owned port of
   `validation_oracle/subject_table.py`'s own algorithm, chosen over
   importing it directly to preserve architectural separation in both
   directions) and a new merge-time consumer in `dynamosa.py` that
   builds the missing subject row once, post-search, with real FK links
   to the same already-solved rows. Found and fixed two more real,
   independent bugs verifying this: `subject_table.py`'s own
   `substituted_decision` handling was dead code (silently missing a
   real table dependency for Spree's `Promotion Customer Group
   Eligibility::rule_4`), and `fitness.py`'s `_unique_key_sets` did a
   case-sensitive schema lookup that silently broke OpenMRS's own PK
   repair the moment multiple same-table rows needed a fresh PK in one
   pass. Result, verified via a fresh per-objective diff across all 4
   case studies: OpenMRS 41→42 (`Identifier Uniqueness Check::rule_1`),
   zero regressions anywhere. `Course Load Limit` remains 0/11 — the
   junction row now genuinely exists and cross-references correctly,
   but the search's own values still don't jointly satisfy the DMN
   condition for one real subject — a separate, disclosed gap this fix
   was never scoped to solve.
9. **RETRACTED #8's closing claim, same day: `Course Load Limit`'s 0/11
   was never actually a generator-side value-alignment problem** — that
   conclusion was inferred from "no rule selected," never checked
   against real resolved values. Direct hand-evaluation of a grounded
   variant's own compiled condition against its real resolved values
   showed every clause should be true. The real cause: three compounding
   validator bugs in `drd_executor.py`/`rule_evaluator.py`. (1)
   `run_decision` merged every DRD-fan-out variant of a decision (several
   compiled records can share one `rule_id` with different own
   `condition`/`variable_resolution`, one per upstream branch —
   `Course Load Limit::Rule_4` alone has 6) into one dict via
   `dict.update()`, silently keeping only the last-processed variant's
   own definition for a shared variable name. (2) No per-subject/
   per-variant isolation existed around a resolution failure other than
   `UngroundedForCase` — `derived_case` hitting a real value uncovered by
   any declared case raised a plain `NotImplementedError` that aborted
   the WHOLE decision for every subject, not just the one that hit it.
   (3) `rule_evaluator.evaluate_condition` never implemented `not`/
   `between` at all (unlike `fitness.py`'s own full support) — 54
   compiled records corpus-wide use `not` (52 FLEX2, 1 Spree, 1
   jBilling). User approved fixing all three. Fixed: `run_decision` now
   tries every variant of a `rule_id` independently per real case (a
   rule matches if any variant both grounds and evaluates true);
   `db_resolver.py`'s `derived_case` now raises a distinct
   `UnresolvableForCase`, translated by `drd_executor.py`'s
   `_resolve_one` into `UngroundedForCase` so it's isolated to the one
   variant/subject it affects; `not`/`between` added to
   `evaluate_condition`. Verified via a full per-objective before/after
   diff across all 4 case studies (identical `coverage.py` invocation,
   code-only difference): `Course Load Limit` 0/11 → 11/11 confirmed
   (all 4 distinct rule_ids), zero flips anywhere else — FLEX2 21→25
   verified rules, decision-table coverage 2/10→3/10. Also surfaced,
   separately, an unrelated coverage-run-methodology finding (OpenMRS/
   jBilling's own officially-recorded numbers appear to have been
   produced without `--not-persisted-json`, undercounting by 2 rules
   each) — flagged in `KNOWN_ISSUES.md`/`COVERAGE_REPORT.md` but not
   corrected here, since it's orthogonal to this fix and needs its own
   deliberate pass.
10. **Fixed FLEX2's `Course Replacement Eligibility` filter_text
    placeholder gap, on request — partially.** `degreeTotalCredits`'s
    own `derived_aggregate` needed `PROGRAM_COURSE.PROG_ID`/`.BATCH_NO`,
    neither on the subject row (`COURSE_REGISTRATION`) — same shape as
    Spree's already-solved `promotion_id` gap. Both are real columns on
    `STUDENT_PROGRAM`, reachable via a real FK. Fixed with two new
    `filter_placeholder_sources.py` entries — no new mechanism needed.
    Surfaced a second bug in `db_resolver.py`'s `derived_aggregate` SQL
    construction: `degreeTotalCredits`'s own `table` field is a real,
    comma-separated implicit-join list (`"PROGRAM_COURSE, COURSE"`), but
    the SQL builder quoted the whole string as one identifier, raising
    `no such table`. Fixed by quoting each table name individually and
    keeping the aggregate's own column reference fully qualified.
    Verified via a full per-objective diff across all 4 case studies:
    `Rule_2`/`Rule_5`/`Rule_6` flip false_positive→confirmed (FLEX2
    25→28 verified, decision-table 3/10→4/10), zero flips elsewhere.
    This decision's own `Rule_1`/`Rule_3`/`Rule_4` remain open — a
    separate, unrelated data-construction gap (every real subject
    resolves the same 4 variables to the identical never-satisfying
    value, zero variation) — not yet investigated further.
11. **Investigated that data-construction gap, on request — found and
    fixed two real bugs, found and precisely diagnosed (not yet fixed) a
    third.** `dynamosa.py`'s own `decision_subject` junction-row builder
    (from item 8's fix) only ever ran when the subject table was
    completely absent from a record's own focal rows, never when it
    already existed but needed its FK links wired to sibling rows built
    for OTHER leaves of the same record. Fixed both: (a) synthesize a
    fresh row for a missing hop target instead of aborting the whole
    junction; (b) always wire every hop onto the subject row, new or
    pre-existing, skipping only an already-set FK column. Verified:
    `Rule_1` flips false_positive→confirmed (FLEX2 28→29 verified),
    `creditsEarned` now correctly resolves for `Rule_3`/`Rule_4`/
    `Rule_5`, zero flips elsewhere. `Rule_3`/`Rule_4` themselves still
    don't verify — root-caused to a THIRD, distinct, generator-side bug,
    fixed in item 12 below.
12. **Fixed that third bug, on request.** CORRECTION to item 11's own
    diagnosis, same day: checking the raw `scenario_map` directly showed
    `candidate.py` was never actually broken — `scenario['program']`
    (`64000001`) already matches `PROGRAM_COURSE.PROG_ID` throughout
    seeding/search/offset. The real gap: `STUDENT_PROGRAM.PROG_ID`/
    `.BATCH_NO` are never independently set by any leaf, so they only
    ever get `mutation.py`'s own generic NOT-NULL fallback (a plain `1`)
    — completely unrelated to `scenario['program']`'s own value; nothing
    anywhere cross-references a live `STUDENT_PROGRAM` row for this
    placeholder. Fixed at merge time (`dynamosa.py`, same layer as the
    `decision_subject` fix): a new compile-time field,
    `compile_constraints.py`'s `cross_table_placeholders` (reusing its
    own generator-owned mirror of `filter_placeholder_sources.py`, now
    also carrying FLEX2's `program`/`batch` entries), lets
    `merge_archive_candidate` copy the record's own already-offset
    scenario value onto the correlated table's own column before repair
    runs. Verified: `Rule_3` flips false_positive→confirmed (FLEX2
    29→30 verified), zero flips elsewhere. `Rule_4` did not yet verify —
    closed the next day, same bug shape, item 13 below.
13. **Investigated and fixed `Rule_4`, on request.** Same bug shape as
    item 12, mirrored within one table pair instead of across two:
    `courseOfferedInFollowingSemesters` needed a second `COURSE_OFFER`
    row for the subject's own `COURSE_ID`, but `COURSE.COURSE_ID` —
    never independently set by any leaf — only ever got a value from a
    global, cross-record fresh-key repair, unrelated to
    `scenario['COURSE_ID']` (which `COURSE_OFFER`'s own row correctly
    tracks). Unlike `<program>`/`<batch>`, the validator resolves
    `<COURSE_ID>` directly off the subject row's own column, never
    reaching `filter_placeholder_sources.py` at all — a purely
    generator-side gap. Extended `cross_table_placeholders` with a
    second compile-time source: a conjunct column matching the
    decision's own subject-FK hop needs no declared override, just a
    lookup against the already-computed `decision_subject['joins']`.
    Reordered `dynamosa.py`'s consumption to run BEFORE the
    subject-junction wiring step (this correlated table is the SAME one
    a subject hop reads FROM) and taught it to synthesize a missing
    correlated row. Found and fixed a genuine PK/UNIQUE collision along
    the way (`degreeTotalCredits`'s own separate `COURSE` row-building
    landed on the identical `COURSE_ID` after offsetting) by bumping the
    other, non-authoritative row via `mutation.py`'s own
    `_fresh_key_value`. Verified: `Rule_4` flips false_positive→confirmed
    (FLEX2 30→31 verified), `Course Replacement Eligibility` now fully
    6/6, zero flips elsewhere across all 4 case studies.
14. **Investigated FLEX2's remaining 5 "backward-join" refusals, on
    request — found they were never one category, fixed 2 real bugs.**
    `Course Registration Eligibility`/`Credit Transfer Exemption` shared
    a bug in `subject_table.py`'s own `_TABLE_EXTRACTORS
    ['derived_join_count']`: it unconditionally required both
    `prereq_table` and `registration_table` reachable, but
    `prereq_table` is queried via a raw, uncorrelated scan needing no
    join path at all (same shape `derived_aggregate`/`exists` were
    already exempted for). Fixed by dropping `prereq_table`. Confirmed
    corpus-wide, this kind is used only by these two decisions — zero
    collateral anywhere else. Verified: `Credit Transfer Exemption` now
    fully resolved and 1/3 verified (FLEX2 31→32); `Course Registration
    Eligibility` moved past subject-picking into a DIFFERENT, deeper gap
    (chains to `Course Load Limit`'s composite-PK subject
    `STUDENT_SEMESTER`, and the cross-decision join builder can't
    express a composite-PK match via two separate single-column FKs —
    not yet fixed). Testing the same idea on `raw_sql_boolean`'s own
    extractor found and fixed a second real bug the same way (used only
    by `Summer Semester Registration`) — resolves subject-picking to
    `COURSE`, but only trades one refusal for a more precise one
    (`<this course offering>` needs `offer_id`, not on `COURSE`); tested
    a `filter_placeholder_sources.py` override pointing at
    `COURSE_OFFER`, which surfaces a genuine 3-way root ambiguity
    instead — reverted, not committed, the extractor fix itself kept.
    The other 2 of the original 5 are genuinely distinct, not bugs:
    `Admission Closure Eligibility`'s own `ADM_MERIT_LIST` has no PK/FK
    declared anywhere in the real DDL at all; `Graduation Eligibility`'s
    own composite-key correspondence to `BATCH_PROGRAM` needs a
    multi-column join capability this project's own join builder is
    deliberately scoped without.
15. **Built the composite-key join capability for `Graduation
    Eligibility`, on request.** New `schema_utility.
    composite_backward_edges(case_study, table)`: when a table `T`'s own
    composite (>=2-column) PK is entirely reconstructable from the
    current table's own single-column FK values (every one of `T`'s PK
    columns is itself an FK to the exact same `(ref_table, ref_column)`
    the current table already FKs to — a real, schema-declared value
    correspondence, confirmed exactly for `STUDENT_PROGRAM.(BATCH_NO,
    PROG_ID)` vs `BATCH_PROGRAM`'s own PK), `build_join_path` now emits a
    multi-column hop for it. Deliberately tried ONLY at the BFS's own
    starting node — testing found that trying it a few hops in let ANY
    table with an ordinary FK straight to `STUDENT_PROGRAM` (e.g.
    `STUDENT_SEMESTER`) transitively "reach" `BATCH_PROGRAM` too,
    manufacturing a spurious second root candidate. `_row_for_table`
    (`db_resolver.py`) and `upstream_subject_value` (`drd_executor.py`)
    both updated to walk the new `from_columns`/`to_columns` hop shape
    alongside the existing single-column one. Verified via a full
    subject-table sweep (every decision, all 4 case studies) and a full
    `coverage.py` re-run per case study, before/after: zero collateral
    anywhere outside FLEX2, zero change to any other FLEX2 decision.
    `Graduation Eligibility` now resolves its subject cleanly (root
    `STUDENT_PROGRAM`, composite join to `BATCH_PROGRAM`) — genuinely
    fixed — but running it through `run_decision` immediately hits a
    SEPARATE, previously-unreachable bug: `semestersElapsed`'s own
    `derived_aggregate` node has `filter_text: null` despite its
    `source_text` explicitly describing a needed subject correlation
    ("... for ROLL_NO"), producing malformed SQL
    (`WHERE ` with nothing after it). A Phase 1/`compile_constraints.py`
    compile-time gap, disclosed rather than patched around — still 0/5
    verified for this decision. As a side effect of the SAME shared
    mechanism, `Course Registration Eligibility`'s own separate
    upstream-chaining gap (item 14 above) is also now fixed:
    `Rule_1` verifies for all 545 real cases (`Rule_2`/`3`/`4` don't, but
    with nothing `ungrounded` — an ordinary data-coverage gap, not a
    bug). FLEX2 32→33 verified rules (58.2%→60.0% raw, 60.4%→62.3%
    solvable), decision-table coverage 5/10→6/10.
16. **Fixed the `semestersElapsed` compile-time bug from item 15, on
    request ("build option 2" — a general parser fix, not a one-off
    override).** Traced to the real ground truth itself
    (`jbillingandflex/flex2_dmn/.../provenance/variable_to_schema_mapping
    .csv` line 37): the raw text reads "derived COUNT(STUDENT_SEMESTER)
    for ROLL_NO" — "for COL" phrasing instead of a `WHERE` clause, which
    `compile_constraints.py`'s own `_try_extract_aggregate_recipe` had
    never been taught to recognize at all. New `AGGREGATE_FOR_CORRELATION
    _RE` matches "for COL"/"for COL1+COL2" immediately after the
    aggregate/table match (anchored there, never a bare `search`
    elsewhere in the text) and translates it into the SAME `:column`
    self-reference syntax `db_resolver.py`'s `_substitute_self_and_colon`
    already resolves (used elsewhere: Spree's `price_list_id =
    :price_list_id AND id != self`) — no new validator capability needed,
    just a compile-time translation into an existing mechanism. Confirmed
    via an order-independent diff of the whole recompiled
    `compiled_constraints.json`: exactly 7 records changed (`Graduation
    Eligibility`'s 3 `semestersElapsed` variants, `Summer Semester
    Registration`'s 4 `priorRegistrationCount`/`enrolledStudentCount`
    variants), zero others — `Summer Semester Registration`'s own THIRD,
    differently-worded fact (`repeatCourseCountRequested`: "COUNT per
    USER_ID/semester") correctly stayed untouched, since "per COL/word"
    is a different phrasing this fix deliberately doesn't attempt to
    parse. Verified against the real FLEX2 fixture (no rebuild needed):
    `Graduation Eligibility` jumped from 0/5 to 3/5 verified (`Rule_1`/
    `Rule_2`/`Rule_3`); `Rule_4`/`Rule_5` don't verify for a confirmed,
    ordinary data-coverage reason (hit policy `FIRST`, `Rule_5` an
    unconditional catch-all, and all 148 real `STUDENT_PROGRAM` rows in
    the fixture already match an earlier rule first — none falls through
    that far). `Summer Semester Registration` is unchanged (its own
    separate `<this course offering>` blocker is untouched by this fix).
    Full regression across all 4 case studies confirms zero collateral.
    FLEX2 33→36 verified rules (60.0%→65.5% raw, 62.3%→67.9% solvable),
    decision-table coverage 6/10→7/10.
17. **Fixed `Summer Semester Registration`'s remaining blocker, on
    request — three separate real things, built together.** (1) New
    `subject_root_overrides.py`: once `<this course offering>` resolves
    to `COURSE_OFFER`, `_pick_root` finds 3 mechanically-valid roots
    (`COURSE_OFFER`, `COURSE_REGISTRATION`, `REPEAT_COURSE`). Re-examined
    against the schema: `COURSE_OFFER`/`REPEAT_COURSE` both have a bare
    `OFFER_ID` PK (no per-student column — `REPEAT_COURSE.USER_ID` traces
    only to `APPUSER` → `EMPLOYEE`, no path to a student at all);
    `COURSE_REGISTRATION` is the only one with composite PK
    `(OFFER_ID, ROLL_NO)`, the exact granularity this decision's own
    variables need. A new kind of disclosed override (none of the
    existing ones cover "which of several valid roots"), still requires
    the override to be an actually-qualifying candidate. (2) A real,
    previously-unreached bug in `db_resolver.py`'s `raw_sql_boolean`
    branch: `conn.execute(sql)` on a bare boolean expression, not a full
    statement — SQLite rejected it. Fixed by wrapping `SELECT ({sql})`.
    (3) `derived_aggregate` now raises `UnresolvableForCase` (not a
    crash) when `filter_text` is `None` — `repeatCourseCountRequested`'s
    own "COUNT per USER_ID/semester" is a genuinely different, more
    complex correlation than the "for COL" fix (item 16) parses, and
    `REPEAT_COURSE.USER_ID` doesn't even trace to a student in the
    schema, so this stays an open, disclosed gap rather than a guess.
    Previously this crashed the WHOLE decision (same shape as item 15/16's
    `semestersElapsed` bug); now `drd_executor.py`'s existing
    `UnresolvableForCase` → `UngroundedForCase` translation (already used
    for `derived_case`) isolates it to just the rule variants that need
    it. Net result, verified against the real fixture: the decision now
    resolves and runs cleanly (no longer in `unresolved_decisions.json`),
    but genuinely 0/5 verified — `Rule_1` needs a `course_type_id =
    'RESEARCH'` registration absent from the fixture; `Rule_2`'s own
    conditions aren't jointly true for any real row; `Rule_3`/`4`/`5` all
    stay ungrounded on the still-unresolved correlation. A full per-rule
    before/after diff confirms ZERO flips anywhere (FLEX2 verified count
    unchanged at 36) — this is a diagnosis upgrade (unresolved → precisely
    diagnosed), not a verified-count change. Side effect: `Attendance
    Eligibility For Final Exam`'s own unresolved reason changed too (same
    `<this course offering>` placeholder), same 0/2 outcome either way.
18. **Found and fixed a real, generalizable GENERATOR-side "grounding"
    bug, on request — confirmed it works, but a separate, deeper gap
    still blocks it from becoming a real verified row.** The existing
    archive claims `fitness=0.0` (fully covered) for ALL 5 of `Summer
    Semester Registration`'s rules — a textbook false positive. Root
    cause: `candidate.py`'s own `_mechanical_filter_predicate`/`_row_
    from_filter_conjuncts` (the search's in-memory fitness/mutation
    bridge) had no support for the `:COLUMN` self-reference syntax the
    "for COL" fix (item 16) introduced — it silently treated `:COLUMN`
    as a literal string no real row could match, forcing the search to
    believe `priorRegistrationCount`/`enrolledStudentCount` were always
    0, the same "generator-vs-validator mismatch" class of bug this
    module's own `_IS_NOT_NULL_RE` comment already documents for a
    different shape. Fixed generally in both files (kept as independent
    copies per their own stated convention): resolves `:COLUMN` against
    the decision's own subject/self row (`focal[self_table]`), falling
    back to the aggregate's own table by default, using the EXISTING
    `aggregate_self_table.py` disclosed-override mechanism (extended to
    also trigger on `:COLUMN`, not just bare `self`) for the one case
    that needs a different table (`semestersElapsed`). Zero hardcoded
    facts about this decision — a real, reusable capability, verified via
    `candidate.py`'s/`mutation.py`'s own self-tests (byte-identical
    output, zero regression) and confirmed working via `search.py`'s own
    `solve_branch` run fresh on this decision's 5 records (8.8s): `Rule_
    1`/`3`/`4`/`5` now reach real `fitness=0.0` for the RIGHT reason;
    `Rule_2` still doesn't, but for a separate, pre-existing, already-
    disclosed reason (`isNeededToGraduateThisSummer`'s `raw_sql_boolean`
    has no automatic mutation support at all). **But**: merging this
    freshly-solved archive into a real, materialized FLEX2 database and
    re-running `coverage.py` shows `Rule_1` still doesn't verify —
    `decision_subject` (the field `dynamosa.py`'s merge step uses to tie
    a decision's facts to ONE real subject row) is `None` for this whole
    decision on the generator side; the solved candidate's own `COURSE`
    row correctly has `course_type_id='RESEARCH'`, but has NO owning
    `COURSE_REGISTRATION` row at all, so nothing ties it to one real,
    enumerable case. Closing this needs porting today's own validator-
    side subject-determination work to the generator too — a separate,
    substantial task, not attempted here.

## 7. Planned / open work

Full, itemized list with root causes and what fixing each would require:
**`validation_oracle/KNOWN_ISSUES.md` → "Open issues"**. Headlines:

- Spree: 1 row-finding gap remains (`Promotion Customer Group
  Eligibility`, rules 1/2/4 — confirmed 2026-09-24 to be a genuine
  one-to-many backward-join gap to `spree_customer_group_users`
  (`rule_4`'s own need), needing a disclosed backward-join override,
  same category as FLEX2's 5 below, not a "missing junction row" issue
  — `Promotion Usage Limit Exceeded` is now closed, see §6 above). One
  further, narrower gap in the now-closed decision:
  `Promotion Usage Limit Exceeded::rule_3` itself still doesn't verify
  (no constructed subject reaches `adjustedCreditsCount >= usageLimit`)
  — a distinct, not-yet-investigated issue.
- FLEX2: `Course Load Limit` (§6 items 8/9: 11/11) and `Course
  Replacement Eligibility` (§6 items 10-13: 6/6) are fully closed;
  `Credit Transfer Exemption` (§6 item 14) is fully resolved (1/3
  verified); `Course Registration Eligibility` (§6 items 14/15) is
  resolved through `run_decision` (1/4 distinct rule_ids verified, the
  rest an ordinary data-coverage gap); `Graduation Eligibility` (§6 items
  15/16) has both its join-mechanism limitation AND the compile-time bug
  it surfaced fixed (3/5 verified; `Rule_4`/`Rule_5` are an ordinary
  data-coverage gap); `Summer Semester Registration` (§6 item 17) now
  resolves and runs cleanly (subject-root override + `raw_sql_boolean`
  executor fix + isolated correlation gap) but is 0/5 verified for
  confirmed data-coverage/gap reasons, not a bug; a real generator-side
  "grounding" bug (§6 item 18, `:COLUMN` self-reference support in
  `candidate.py`/`mutation.py`) is also fixed and confirmed working in
  isolation, but a still-missing `decision_subject` wiring on the
  generator side (a separate, substantial task) keeps it from showing up
  as an actual verified row yet. Remaining: `Admission Closure
  Eligibility` has no declared FK relationship at all in the real schema.
  An audit question remains on `Attendance Eligibility For Final Exam`.
- jBilling: an audit question on 8 decisions currently marked
  non-table-backed or needing a `not_persisted` override — genuine, or a
  `purchaseQuantity`-style mis-mapping? Not yet checked.
- Cross-case-study: COLLECT hit-policy support (real new code, currently
  out of scope) if the project's scope is ever extended to it.

## 8. Known challenges (structural, not just "not done yet")

- **One-to-many backward joins.** When a decision's subject can reach a
  needed fact only via a table that could hold *many* matching rows (not
  a clean FK-unique backward edge), `subject_table_for_decision`
  correctly refuses to guess which one is "the" row — by design, not a
  bug. Closing one of these always needs a disclosed, case-specific
  override, never a generic fix.
- **Ground-truth completeness vs. honesty is a real tension.** Several
  facts are marked `not_persisted`/no-table-backed-input by the
  hand-curated CSVs; some of these have already turned out to be
  mis-mapped real columns once challenged (`purchaseQuantity`), and
  others (jBilling's audit list above) haven't been checked yet. The
  project's own discipline requires checking the real schema before
  accepting a "not persisted" call at face value, but that's slow,
  manual work — not something to batch-guess through.
- **Search budget vs. genuine infeasibility look identical from the
  outside** (search claims covered, validator disagrees) until someone
  actually re-runs the search and inspects `decision_trace.json`. Some
  gaps really do close with a re-run (`Price List Volume Adjustment Tier
  Selection` did); others don't, even with the same budget tried twice
  (`First-Order Promotion Eligibility::rule_3` didn't, until the real
  generator bug behind it was found and fixed) — a stale "should resolve
  with more budget" note in this file's own history turned out wrong
  once actually tested. Don't trust that prediction without re-testing it.
- **COLLECT hit policy and blob-level generation are permanent, not
  temporary, scope boundaries** (see §4) — don't spend effort trying to
  incrementally close them without a fresh, explicit decision to expand
  scope first.
- **Rule vs. objective counting** (see §4, §7 of `QUICK_REFERENCE.md`)
  is an easy place to silently introduce a wrong denominator — always
  sanity-check a percentage against `coverage.py`'s own printed value
  rather than manually recomputing from a raw "compiled" count.

## 9. Picking this up cold — suggested reading order

1. This file.
2. `QUICK_REFERENCE.md` — glossary + where things live.
3. `RULE_TO_OBJECTIVE_MAPPING.md` — how compilation actually works, if
   you're about to touch `compile_constraints.py` or need to understand
   why a coverage denominator looks the way it does.
4. `validation_oracle/COVERAGE_REPORT.md` — current numbers.
5. `validation_oracle/KNOWN_ISSUES.md` — what's open, what's fixed, why.
6. Whichever of `generator/README.md` / `validation_oracle/DESIGN.md` /
   `generator/DECISIONS_ALGORITHM.md` / `generator/DECISIONS_EXPERIMENT.md`
   covers the specific area you're about to touch — these are long,
   read the relevant section, not the whole thing cold.

To verify nothing is broken before changing anything: run
`python3 generator/candidate.py`, `python3 generator/mutation.py`,
`python3 generator/fitness.py`, `python3 validation_oracle/tests/test_spec_cases.py`,
`test_drd_chaining_synthetic.py`, `test_serialized_field_roundtrip.py`,
and `python3 validation_oracle/drd_executor.py` (the OpenMRS acceptance
test) — all from their own directories. All should pass with zero
regressions; see `QUICK_REFERENCE.md` for the exact commands.
