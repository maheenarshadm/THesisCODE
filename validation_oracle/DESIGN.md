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

Still not started: `coverage.py` + the three CSV/JSON output files, the
remaining spec'd test cases (UNIQUE violation, join-based input against
real data, merge-induced regression as an explicit test rather than an
ad hoc script, duplicate-output disambiguation), and extending beyond
the decisions exercised so far to the rest of OpenMRS/FLEX2 and to
Spree/jBilling.

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
