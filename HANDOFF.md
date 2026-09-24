# Project handoff

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
provenance): raw verified coverage OpenMRS 57.7%, Spree 58.1%, FLEX2
38.2%, jBilling 25.6%; solvable-rules coverage (excluding COLLECT,
`code_external` facts, and the out-of-scope blob-level rules) OpenMRS
73.2%, Spree 81.8%, FLEX2 39.6%, jBilling 66.7%.

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

## 7. Planned / open work

Full, itemized list with root causes and what fixing each would require:
**`validation_oracle/KNOWN_ISSUES.md` → "Open issues"**. Headlines:

- Spree: 1 row-finding gap remains (`Promotion Customer Group
  Eligibility`, needing a disclosed join-construction override —
  `Promotion Usage Limit Exceeded` is now closed, see §6 above). One
  further, narrower gap in the now-closed decision:
  `Promotion Usage Limit Exceeded::rule_3` itself still doesn't verify
  (no constructed subject reaches `adjustedCreditsCount >= usageLimit`)
  — a distinct, not-yet-investigated issue.
- FLEX2: 5 multi-table backward-join gaps (same category already solved
  for Spree/jBilling elsewhere); `Course Replacement Eligibility`
  (likely a one-line fix, reusing existing infrastructure); `Course Load
  Limit` — both validator bugs blocking it are now fixed (§6 above); the
  remaining 0/11 is a genuine generator-side leaf-alignment gap, not yet
  investigated further; an audit question on `Attendance Eligibility
  For Final Exam`.
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
