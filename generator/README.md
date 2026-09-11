# `compile_constraints.py` — the compiled constraint record (design doc §6.1)

Built 2026-09-11, closing design doc §12 item 7's prerequisite: *"Two
concrete prerequisite artifacts... not yet built: `compile_constraints.py`
(DMN + mapping CSV → one JSON record per target branch)... Both should
exist before the search loop itself, since the search loop's input
contract depends on them."* This is that artifact — the fitness function
and search loop themselves are still not built (next).

## What it does

Merges each case study's DMN decision tables with its hand-curated
`variable_to_schema_mapping.csv` into one self-contained JSON record per
target branch (one per decision-table rule): the branch's condition as a
structured predicate tree (not a FEEL string), every variable it depends
on resolved to a real schema column / a derivation recipe / an explicit
not-persisted/schema-gap marker, DRD backward-substitution already
inlined where the upstream is a literal-expression decision, the
FIRST/UNIQUE hit-policy suppression context, and a real FK-closure table
list computed by BFS over the schema's actual FK graph (§6.6) — not
estimated.

```bash
cd generator
python3 compile_constraints.py --out compiled_constraints.json --report compile_report.json
# or one case study only:
python3 compile_constraints.py --case-study FLEX2 --out flex2_only.json --report flex2_report.json
```

## Two modules

- **`feel_parser.py`** — a small, targeted FEEL parser, not a general
  implementation. Built by first surveying every distinct FEEL construct
  actually present across all four case studies' `.dmn` files (701 unary
  tests, 11 literal-expression formulas), then writing a grammar that
  covers exactly that surveyed set — comparisons (`>`, `>=`, `<`, `<=`,
  `=`, `!=`, including a bare identifier or a zero-arg call like
  `today()` as the right-hand side), `not(...)`, list-membership
  (`"a","b"` / `1,4`), range literals (`[a..b]`), arithmetic (`+ - * /`),
  `if...then...else`, and function calls (`count(...)`,
  `intersection(...)`). **Validated against every single FEEL string in
  the program**: 701/701 unary tests and 11/11 literal expressions parse
  successfully. The one FEEL construct genuinely outside this grammar —
  Spree's one list-filter/comprehension (`count(order for order in
  store.orders where ...)`) — degrades gracefully to an `opaque_formula`
  node nested inside its enclosing `count(...)` call (so "this is a count
  of something" stays visible even though the filter itself isn't
  structurally parsed), rather than crashing or silently mis-parsing.

- **`compile_constraints.py`** — DMN model extraction (decisions, rules,
  DRD `informationRequirement` edges), ground-truth variable resolution
  (reuses `dmn_schema_mapper/mapper/validate_mapper.py`'s `GT_CONFIG`
  rather than re-implementing each case study's CSV-shape handling),
  DRD backward-substitution, FK-closure BFS, and record assembly.

## Which mapping source, and why

Defaults to each case study's own **hand-curated** `variable_to_schema_mapping.csv`
— not the automated mapper's output (`mapping_auto.csv`/`mapping_final.csv`,
`dmn_schema_mapper/mapper/`). The automated pipeline's own README is blunt
about why: 48.3% top-1 even after the LLM-assisted pass is not something
to feed a generator unattended, since a wrong column here means the
eventual search solves for the wrong fact entirely. Using the automated
mapping instead (as a deliberate ablation, not the default) is a natural
follow-up for §11's evaluation design, not built here.

## Hard-stop semantics, interpreted

Design doc §6.1: *"A record whose predicate depends on a variable the
mapper marked `needs review` is refused at compile time... the compiler
should hard-stop and list exactly which unresolved variables are blocking
which branches."* With 90 of 276 variables still unresolved even after
both mapper passes, a literal process-exit on the first blocked branch
would produce zero usable output. Read instead as: **never silently emit
an incomplete or wrong record for a blocked branch** — every branch is
attempted, a blocked one is omitted from `compiled_constraints.json` and
recorded, with its exact blocking variable(s) and reason, in
`compile_report.json`.

## Result, current run (post chained-decision-output expansion — see below)

| Case study | Compiled | Blocked | Rate |
|---|---|---|---|
| FLEX2 | 100 | 3 | 97.1% |
| OpenMRS | 71 | 0 | 100.0% |
| Spree | 27 | 5 | 84.4% |
| jBilling | 41 | 13 | 75.9% |
| **Total** | **239** | **21** | **91.9%** |

Total target-branch count (260, up from 211) is higher than earlier runs
because the chained-decision-output expansion below multiplies certain
rules into several self-contained variants rather than resolving a fixed
set — see "Chained decision output" below for why, and for the historical
183/28 numbers from before that pass.

**Blocking reasons, by kind** (a branch can have more than one blocking
variable): `unresolved` (8) — mostly free variables of an inlined
literal-expression formula whose own ground-truth row couldn't be
resolved to a column, recipe, or gap marker; `schema_gap` (6) — the
branch's condition itself depends on a variable ground truth already
flags as having no schema representation at all (e.g. Spree's
`preferences` serialized-blob findings); `code_external` (12) — the
variable is genuinely computed by application code with no schema field
ever recorded for it at all (a Java constant, a UI-only transient value,
a runtime-only calculation), not merely a column this compiler failed to
find; `chained_dependency_unexpandable` (2, new) — a decision-table DRD
dependency where *every* upstream rule is itself blocked by something
this compiler can't resolve (jBilling's `Ageing Step Advancement`, see
below) — a genuine dead end, not a missed case.

**Compiled-but-not-generator-ready dropped sharply after the
derived/aggregate resolution pass below** (figures as of that pass, before
the chained-decision-output expansion further below changed the total
branch count again): of the 211 total branches at that point, **158
(74.9%) were fully mechanical** — every variable a real schema column,
ready for a generator today — up from 73 (34.6%) before that pass. Only 25
remained in the "compiled, but still needs a human/more automation" tier
(12 `exists` with an unstructured filter, 8 generic `derived` notes still
unclassifiable by pattern, 6 `derived_aggregate`
with unstructured filter text), down from 120. See below for exactly how.

## Resolving derived/aggregate nodes (2026-09-11, second pass)

The first version of this compiler left every `derived`/`derived_aggregate`
fact with only raw notes text or an unstructured filter string — resolved
enough not to block compilation, but not yet actionable by an actual
generator. Rather than hand-classify the (deduplicated) 83 distinct
derived-bucket facts across the program one at a time, a general pattern
classifier (`classify_derived`, `generator/compile_constraints.py`) was
built after first surveying what shapes those 83 facts' free-text
`notes`/`schema_field` actually take — the same survey-before-building
discipline `feel_parser.py` used. Six new resolution kinds, each backed by
a real, surveyed, recurring pattern rather than invented in the abstract:

- **`null_check`** (`table`, `column`) — an "IS NOT NULL"/"IS NULL"
  existence fact ground truth already names a real column for (by far the
  most common shape: ~20 of the 83 facts, e.g. `orders.date_activated`,
  `person.cause_of_death`, `patient_state.start_date`).
- **`any_not_null`** (`columns: [...]`) — an OR-of-existence-checks across
  several named columns (e.g. Spree's "customer or email present").
- **`join_lookup` / `join_null_check`** — a fact reached by following one
  named FK ("joined via encounter.visit_id") to a value or an existence
  check on the target row.
- **`regex_match`** (`value_column`, `pattern_column`) — two real, named
  columns compared via pattern match (§7b's own "Pattern/Regex Match"
  construct category) rather than a portable comparison; not
  branch-distance-friendly the way a numeric threshold is, but a real,
  structured fact a SQL validation pass (§6.7) can still express via an
  engine's `REGEXP` operator.
- **`exists`** — a table (and, where nameable, its key columns) an EXISTS
  check runs against, extended from the "COUNT/SUM WHERE" aggregate
  pattern to also catch the "TABLE (existence)" / "EXISTS(...)" / "TABLE
  (COUNT WHERE ...)" (reversed word order) phrasings the survey actually
  found.
- **`code_external`** — the one new *blocking* kind, and a deliberate,
  informative one: a fact whose `raw_schema_field` was recorded as `n/a`
  because it genuinely has no schema representation at all — a Java
  constant comparison, a UI-only transient boolean, a value computed at
  runtime from other derived facts with no column of its own (jBilling's
  `eventType`, `isLastSelectedStep`, `daysInCycle`, `daysInPeriod`,
  `expiryDate`). **This is a correctness fix, not a regression**, even
  though it *reduced* the raw compiled-branch count (jBilling's rate fell
  from 94.3% to 73.6%): these five facts were previously accepted as a
  generic `derived` node with empty `table_hints` and silently counted as
  "compiled," which was the more dishonest state — there was nothing
  there to generate from either way. Treating them as blocking (the same
  way `schema_gap` already is) surfaces that plainly instead of hiding it
  behind a technically-non-blocking label. A genuinely free-choice subset
  of these (e.g. `eventType`, which already has declared literal values)
  is a plausible candidate for a future, distinct `free_scenario_parameter`
  kind the generator could pick directly without any schema at all — not
  built here, since telling that apart mechanically from a "computed from
  real inputs I haven't captured" case like `expiryDate` (getting it wrong
  would let the search silently violate that formula) needs more care than
  this pass had scope for.

Every existing resolved kind (`schema_column`, `derived_aggregate`) still
takes precedence when it applies; a fact that fits none of these patterns
is left exactly as before — a generic `derived` node with raw notes and
`table_hints` — never forced into a wrong shape. Verified the same way as
the first pass: the recursive `find_blocking_issues` self-check
(§ below) confirmed zero leaked unresolved values across all 183 compiled
records both before and after this change.

**Cross-variable comparisons**: 38 of 193 compiled records (~20%) compare
one resolved variable against another rather than a literal — consistent
with design doc §6.3/§7a's own finding that this is a first-order case
(~17–19% of decisions program-wide), not a rare edge case, and confirming
the fitness function (not yet built) genuinely needs the cross-variable
distance-table extension §6.3 already flags as required.

**FK-closure table counts**: 1–28 tables per branch, mean 12.8. Checked
directly rather than assumed: the maximum (28, FLEX2's `Grade Points and
Interpretation` decision) is a *different* branch from the flagship
attendance worked example below, which computes to **25 tables** — still
landing squarely inside §6.6's own hand-traced estimate for that exact
chain ("roughly 25–30 tables"), a real confirmation of that worked
example, just not from the single largest record in the run.

## The flagship worked example, validated directly against §6.1's own JSON

`compiled_constraints.json`'s record for `FLEX2::Attendance Eligibility
For Final Exam::...Rule_2` matches design doc §6.1's own hand-written
worked example on every structural point: the condition
(`attendancePercentage < 80`), the outputs (`eligibleForFinalExam: false`,
`assignedGradeOverride: "FA"`), the hit-policy suppression context (rule 1's
`>= 80` condition), and — the part that actually exercises DRD
substitution — `attendancePercentage` is fully inlined into
`(lecturesAttended / lecturesHeldForOffering) * 100`, with both of *those*
free variables further resolved into `derived_aggregate` recipes
(`COUNT(STUDENT_ATTENDANCE) WHERE ROLL_NO=... AND ATTEND_FLAG='Y'` and
`COUNT(LECTURE) WHERE OFFER_ID=...`) — the same two facts §6.1's own JSON
names, just carried as a raw filter-text string rather than the fully
structured `{"filter": [...]}` array shown there (see "Known scope
limits" below).

## Bugs found and fixed while building this (kept here, not swept away)

Two real correctness bugs surfaced by validating against the worked
example above, not by inspection alone:

1. **Substitution priority was backwards.** A decision table that both
   declares a variable as one of its own `<input>` elements *and* has a
   DRD edge producing that same variable (the real, surveyed case: FLEX2's
   attendance-eligibility table declares `attendancePercentage` as an
   input, formally required by DMN 1.3 syntax to reference it in a rule at
   all, while also importing it via `informationRequirement`) was resolving
   via a flat ground-truth lookup instead of DRD substitution — producing
   a `derived` note pointing at the upstream decision instead of the fully
   inlined formula §6.1 actually specifies. Fixed by checking DRD edges
   first.
2. **Blocking detection didn't recurse into an inlined formula's own free
   variables.** A `substituted_decision` node's `free_variable_resolutions`
   could contain a genuinely `unresolved` entry while the branch still
   compiled successfully, because the blocking check only inspected each
   *top-level* referenced variable's resolution kind, and
   `substituted_decision` itself isn't a blocking kind. Fixed with a
   recursive `find_blocking_issues` walk, then verified with a self-check
   (`find_blocking_issues` re-run over every compiled record's own
   resolutions, confirming zero leaks) — not just fixed and assumed
   correct.

A third, genuine **data-quality finding** surfaced the same way, in the
source data rather than this compiler: FLEX2's own hand-curated mapping
CSV labels `lecturesAttended`/`lecturesHeldForOffering` `direct` even
though their schema-field text is plainly an aggregate
(`COUNT(STUDENT_ATTENDANCE) WHERE ...`), not a bare column reference. Not
silently corrected — the compiler now recognizes the `COUNT(...)`/`SUM(...)`/etc.
pattern mechanically wherever it appears (regardless of which bucket the
row's own label put it in) and reports the mismatch in the resulting
node's own `notes` field, rather than either trusting the wrong label
(which would have surfaced as an unusable "direct" resolution with no
actual table.column pair) or quietly relabeling the source CSV.

## Chained decision output — resolved via branch enumeration (2026-09-11, third pass)

The first two passes left `chained_decision_output` as a documented dead
end: a decision table's output depends on which of its own rules fires,
which isn't a single closed-form expression to inline the way a
literal-expression decision's formula is, so 9 branches across FLEX2 and
jBilling were blocked rather than guessed at. §6.1's own requirement —
a compiled record must be self-contained and "never trigger a runtime
lookup into another decision" — settles which of the three ways to fix
this is actually correct: not deferring resolution to the search loop
(which would need extra machinery to solve one target before another,
exactly what inlining exists to avoid), and not silently picking one
upstream branch as *the* answer (wrong by construction). The only option
consistent with the self-contained-record contract is **enumeration**:
for each upstream rule that could produce the needed variable, emit a
separate, fully self-contained compiled record — the downstream rule's
own condition **AND** that upstream rule's own "this is the one that
fires" condition (its own predicates plus, for FIRST/UNIQUE, the same
suppression-against-earlier-rows logic `hit_policy_context` already
computes, just expressed here as a literal boolean formula rather than a
search-time distance term).

**Built as three new functions in `compile_constraints.py`** (not a
separate script — the same source of truth every other artifact in this
program reuses): `build_rule_condition`/`parse_output_value` (factored out
of what was previously duplicated inline logic), `build_hit_policy_truth_condition`
("is this specific rule the one that wins"), and
`enumerate_upstream_groundings` — the actual recursive enumeration. It
handles **multi-level chains** (FLEX2's `Academic Warning Status → Course
Load Limit → Course Registration Eligibility` is 3 decisions deep) by
calling itself on any further chained dependency it finds inside an
upstream rule's own truth condition, then taking the cross-product; a
grounding option is only ever offered once *every* variable it depends on
resolves cleanly, recursively — never a half-resolved option presented as
safe.

**Result**: 56 new self-contained records where 9 blocked rule-slots used
to be (some multiply — FLEX2's `Course Registration Eligibility::Rule_3`
is a genuine 2-level chain, 4 `Course Load Limit` rules × 6 `Academic
Warning Status` rules = 24 variants, each independently generatable, no
cross-decision lookup needed at search time). 2 of the original 9 remain
correctly blocked (jBilling's `Ageing Step Advancement`, both rules) —
not a bug, a genuine dead end: its upstream `Is Ageing Required` decision
itself depends on `expiryDate`, already found to be `code_external` (no
schema representation at all, §13.11) — no upstream rule can be grounded,
so `enumerate_upstream_groundings` correctly returns nothing and the
branch stays honestly blocked (`chained_dependency_unexpandable`) rather
than pretending otherwise.

**Program totals moved again**, since expansion multiplies the branch
count itself, not just resolves a fixed set: 260 total target branches
(up from 211), 239 compiled (up from 183), 21 blocked (down from 28).
"Fully mechanical" rose to 172/260 (66.2%) — the raw percentage looks
lower than the pre-expansion 74.9% only because expansion multiplied
*every* variable resolution in the affected rules, including the ones
still in the "needs more work" tier (e.g. FLEX2's `semesterType`, still
an unclassified `derived` note) — the same underlying facts appearing
across more record variants, not new quality problems.

**Verified the same way as every previous pass**: the recursive
`find_blocking_issues` self-check confirmed zero leaked unresolved values
across all 239 compiled records (including every expanded variant), and
the flagship attendance worked example (untouched by this change, no
DRD chain through a decision table) was re-diffed and still matches
exactly.

## `sql_compiler.py` — the JSON→SQL validation compiler (§6.7, built 2026-09-11)

Closes §12 item 7's second prerequisite artifact. §6.7's own framing:
*"the search loop runs on the JSON predicate; SQL is compiled from that
same JSON afterward, purely for validation."* This compiler is that
translation — one SQL boolean expression per compiled branch
(`SELECT (...) AS branch_holds;`), re-evaluating the branch's condition
against real materialized rows, the "DMN semantic re-check, compiled to
SQL rather than re-implemented in the host language" pass §6.7 designs.
Mechanical, not novel design work, since §7b's construct taxonomy already
enumerates which SQL construct each variable category needs.

**Design choice, matching §6.1's own worked example's idiom**: every
resolved variable compiles to an **independent scalar subquery**,
parameterized by a bind variable per referenced table's own primary key
(looked up from the schema JSON, composite keys handled), rather than one
flat query with a shared join graph across the whole branch — mirroring
how the branches themselves are independent per §6.1's own contract, and
needing no assumption about how a validation harness lays out candidate
rows beyond "you can bind a value for this table's PK."

**Every resolution kind `compile_constraints.py` produces gets a
translation**: `schema_column` → a PK-bound scalar subquery;
`null_check`/`join_null_check` → `IS NOT NULL`/`IS NULL` (with a
dedicated simplification for the common `var = true/false` DMN pattern,
so it compiles directly to the null check rather than a clunky
boolean-round-trip); `any_not_null` → OR'd `IS NOT NULL` checks;
`join_lookup` → a real `JOIN`; `derived_aggregate` → `COUNT`/`SUM`/etc.
with `GROUP BY`-equivalent scalar-subquery semantics; `exists` →
`EXISTS (SELECT 1 FROM ... WHERE ...)`; `regex_match` → an engine
`REGEXP` operator, flagged non-portable exactly as §7b's own construct
taxonomy already characterizes it; `literal_via_upstream_branch`/
`substituted_decision` → recursively compiled, the same DRD inlining
`compile_constraints.py` already did; `not_persisted` → a bind parameter
(see the bug note below for why this needed fixing, not assuming).

**Honesty over completeness where the source notes don't support more**:
a `derived_aggregate`/`exists` fact's filter is often free prose
("`LECTURE_ID IN (LECTURE for that OFFER_ID)`", not valid SQL) rather
than a clean WHERE clause. `sqlify_filter_text` only emits a filter when
a mechanical check (placeholder substitution + a small, targeted
prose-marker blocklist, itself surveyed from this program's own real
filter strings) finds it SQL-shaped; otherwise it emits a
syntactically-valid placeholder subquery with the raw text preserved as a
comment, and records a warning — never silently guessing at what a
human-written note meant, and never emitting broken SQL as if it were
runnable.

**Result**: 173 of 239 compiled branches (72.4%) produce a fully clean
validation query with zero warnings — OpenMRS 97.2%, Spree 92.6%,
jBilling 75.6%, FLEX2 48.0% (lower only because the chained-decision-
output expansion above multiplied a handful of still-unresolved `derived`
facts, like `semesterType`, across dozens of variants — the same
underlying gaps repeated, not new ones). The flagship attendance branch
now compiles to `(SELECT COUNT(*) FROM LECTURE WHERE OFFER_ID =
:this_course_offering)` for `lecturesHeldForOffering` — structurally
identical to §6.1's own hand-written `(SELECT COUNT(*) FROM LECTURE WHERE
OFFER_ID=:offer_id)` — while `lecturesAttended`'s messier filter text
(a genuine prose fragment, "`LECTURE_ID IN (LECTURE for that
OFFER_ID)`") is honestly left as a flagged placeholder rather than forced
through as broken SQL.

**Two real bugs found and fixed while validating against that same
flagship example** (not swept away):
1. `not_persisted` was assumed to never reach the compiler as an input
   (compile_constraints.py never blocks on it, but the assumption was
   still "it's always an output verdict"). It's actually also used, by
   ground truth's own deliberate design, for a genuine runtime/scenario
   parameter with no stored column at all (OpenMRS's `evaluationTime` —
   "time of validation, not a stored column"). Fixed to compile to a bind
   parameter, exactly the right answer for that case; this alone raised
   the clean rate from 61.5% to 72.4% before the second fix below.
2. The prose-marker check ran on a filter's raw text *before* `<placeholder>`
   substitution, so an English phrase *inside* the brackets — content
   that's specifically headed for a bind parameter, not literal SQL, e.g.
   `<this course offering>` — could disqualify an otherwise perfectly
   clean filter. Fixed to mask placeholder spans before the prose check
   runs, which is exactly what recovered `lecturesHeldForOffering`'s
   clean compilation above.

## Known scope limits (stated here, not discovered by a reader)

- **Aggregate recipes carry a raw filter-text string, not §6.1's fully
  structured `{"filter": [{"column", "op", "value"}, ...]}` array.**
  Extracting the aggregate function and target table mechanically (via a
  `COUNT(TABLE) WHERE ...` regex) is a defensible, general pattern; parsing
  the WHERE clause itself into structured per-column conditions would
  require case-study-specific semantic knowledge (what `<student>` or
  `<this course offering>` bind to at generation time) this script has no
  principled way to infer automatically. Left as the natural next
  refinement, not attempted here as a guess.
- **No SQL compilation yet.** §6.7 designs a JSON→SQL compiler for the
  post-search validation pass, using this same predicate-tree shape as
  its input — not built in this pass; the fitness function and search
  loop (§6.3/§6.4) are the more immediate next step per §12 item 7, both
  gated on this artifact existing first.
