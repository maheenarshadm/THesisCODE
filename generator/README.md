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

## Result, current run (post domain-knowledge-driven ground-truth fixes — see below)

| Case study | Compiled | Blocked | Rate |
|---|---|---|---|
| FLEX2 | 103 | 0 | 100.0% |
| OpenMRS | 71 | 0 | 100.0% |
| Spree | 27 | 5 | 84.4% |
| jBilling | 41 | 13 | 75.9% |
| **Total** | **242** | **18** | **93.1%** |

FLEX2 is now fully compiled (0 blocked), up from the 239/260 (91.9%)
figures the chained-decision-output expansion pass (below) originally
produced — themselves reached only after correcting an earlier, mistaken
`semesterType` fix (see "Two ground-truth fixes, one of them corrected"
below for that full sequence). The further gain to 242/260 (93.1%) comes
from a *third* round of domain-knowledge-driven fixes, prompted directly
by the project owner after the `semesterType` correction — see "A third
round" further below for the full accounting, including one real
compiler bug this round surfaced but did not fix.

**Blocking reasons, by kind** (a branch can have more than one blocking
variable): `unresolved` (6) — mostly free variables of an inlined
literal-expression formula whose own ground-truth row couldn't be
resolved to a column, recipe, or gap marker; `schema_gap` (5) — the
branch's condition itself depends on a variable ground truth already
flags as having no schema representation at all (e.g. Spree's
`preferences` serialized-blob findings); `code_external` (12) — the
variable is genuinely computed by application code with no schema field
ever recorded for it at all (a Java constant, a UI-only transient value,
a runtime-only calculation), not merely a column this compiler failed to
find; `chained_dependency_unexpandable` (2) — a decision-table DRD
dependency where *every* upstream rule is itself blocked by something
this compiler can't resolve (jBilling's `Ageing Step Advancement`) — a
genuine dead end, not a missed case.

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

## Two ground-truth fixes, one of them corrected: semesterType and projectedTotalCoursesThisRegistration (2026-09-11, fourth and fifth passes)

FLEX2's 52 "needs work" branches (per-rule readiness stats, prior pass)
had two recurring root causes behind most of them. Investigated directly
against `schemas/flex2/Flex1.sql`, with standing permission from the
project owner to ask a clarifying question if one was needed.

**`projectedTotalCoursesThisRegistration` (`Course Registration
Eligibility`'s input, affecting 0 already-compiled records, since it was
already correctly bucketed `derived_aggregate` — just missing a real
filter clause)**: ground truth's own schema-field text already named the
exact aggregate recipe, `COUNT(COURSE_REGISTRATION) for ROLL_NO+SEM_ID`,
but with no `WHERE` keyword, so `_try_extract_aggregate_recipe` had
nothing to extract a `filter_text` from. Verified directly against
`Flex1.sql` that `COURSE_REGISTRATION` really does have both `ROLL_NO`
and `SEM_ID` columns, exactly as the existing note already claimed —
so the fix was purely mechanical: rewrite the schema-field text to
`COUNT(COURSE_REGISTRATION) WHERE ROLL_NO=<student> AND SEM_ID=<semester>`,
which now resolves to a real `derived_aggregate` node with a genuine,
SQL-shaped filter clause. This one needed no domain knowledge beyond the
DDL and stands as fixed.

**`semesterType` (`Course Load Limit`'s input, affecting 43 of the 52
FLEX2 "needs work" records at the time) — first pass, wrong**: ground
truth previously labeled it `derived` with the honest-but-vague note
"exact column not confirmed from DDL alone." DDL-only inspection of
`Flex1.sql` found `SEMESTER` has only `SEM_ID`/`TITLE`/`STATUS`, no other
table carries a type classification, and none of FLEX2's 24 `D_*`
dimension tables cover semester/term type — the pattern every *other*
coded category in this schema uses. From that alone, this was concluded
to be reclassified `SCHEMA GAP (partial)`: no dedicated Regular/Summer
column, `TITLE` dismissed as "free text, reachable only via a fragile
`LIKE '%Summer%'` substring match." **This conclusion was wrong, and it
was wrong for exactly the reason a clarifying question exists to catch**:
DDL shows column definitions, never data, so there was no way to
mechanically tell "TITLE is free text" apart from "TITLE is a clean
categorical column that happens to be typed as text" — and this was
guessed at instead of asked about, despite standing permission to ask.

**Corrected via the project owner's own domain knowledge**: `TITLE` *is*
the semester-type field, with exactly three possible values — `'Fall'`,
`'Spring'`, `'Summer'` — not free text with an embedded year. A plain
equality lookup, not a substring match. Ground truth is now `direct`,
mapped to `SEMESTER.TITLE`, with the correction (and the wrong
conclusion it replaces) documented in the CSV's own notes field rather
than silently overwritten.

**Consequence, both times traced rather than assumed**: the first
(wrong) `SCHEMA GAP` conclusion correctly-given-its-premise blocked every
rule of `Course Load Limit`, which cascaded to block `Course Registration
Eligibility`'s `maxCoursesAllowed` dependency too (no upstream grounding
left to expand) — the program-wide compiled-branch total dropped 260 →
222 as a result. Once `semesterType` was corrected back to a real
column, `Course Load Limit` compiles again and the cascade reverses:
totals are back to 260 total / 239 compiled (91.9%), identical to the
chained-decision-output expansion pass's own original numbers, and
`sql_compiler.py`'s clean rate actually improved past that baseline (see
below) since `projectedTotalCoursesThisRegistration`'s independent fix is
still in effect.

**Verified the same way as every previous pass, after the correction**:
`find_blocking_issues` re-run over all 239 newly-recompiled records found
zero leaks, `semesterType` now resolves to a plain `schema_column`
(`semester.title`), and the flagship attendance worked example (unrelated
to either fix) was re-diffed and still matches exactly.

## A third round: the project owner asked for the remaining Schema Gap variables' closest tables (2026-09-11, sixth pass)

After the `semesterType` correction, the project owner asked directly:
since domain knowledge had already solved one `Schema Gap` row, name the
closest candidate table for every *other* one so they could supply the
real mapping the same way. All 11 `Schema Gap`-bucketed ground-truth rows
(`taxonomy/construct_taxonomy.csv`) were re-examined against the real
DDL rather than re-stating the existing notes, surfacing two more things
this compiler had gotten wrong on its own, and one genuine limitation
that domain knowledge alone couldn't close.

**Resolved without needing to ask (DDL confirmed it directly)**:
- jBilling's `resultCode` (Payment Outcome Resolution) had been filed as
  `Schema Gap` on the strength of only reading `PaymentBL.java`, never
  the DDL. `payment.result_id` is a real FK to `payment_result.id` (data
  has codes `1,2,3,4`). **This was never actually the same kind of gap as
  `semesterType`** — the note's "SCHEMA GAP" concern is genuinely about
  something else (whether the Java code ever writes the computed value
  back onto the row, a write-back-path question `PaymentBL.java` itself
  couldn't settle either way) — corrected the framing in ground truth
  rather than claiming a fix that isn't one.
- jBilling's `taxCalculationMode` (Tax Calculation Mode): re-verified
  directly against the `item` table's real columns (`id,
  internal_number, entity_id, percentage, deleted, has_decimals,
  optlock, gl_code, price_manual`) — genuinely no discriminator column
  exists. This one **stands**, now confirmed rather than merely asserted.

**Needed the project owner's domain knowledge, same workflow as
`semesterType`**:
- FLEX2's `degreeMinimumCreditHours`/`degreeTotalCredits`: `PROGRAM`
  itself turned out to have **no credit-hour column at all** (the old
  ground-truth note claiming one existed had never actually been
  checked either — the same under-investigation pattern as
  `semesterType`, caught this time before being asserted as fact rather
  than after). Closest real candidate was `BATCH_PROGRAM.MIN_CR_HRS`.
  Confirmed: `degreeMinimumCreditHours` **is** `BATCH_PROGRAM.MIN_CR_HRS`
  directly; `degreeTotalCredits` is a genuinely different figure, a
  `SUM(COURSE.CREDIT_HRS)` aggregate over every course linked to the
  program/batch via `PROGRAM_COURSE`, not a stored scalar at all.
- FLEX2's `isElectiveTaughtByVisitingScholarUnavailableOtherwise`:
  closest path was `COURSE_OFFER.EMP_ID → EMPLOYEE.EMP_TYPE_ID →
  D_EMP_TYPE.TITLE` — the same coded-dimension shape as `semesterType`.
  Confirmed: the visiting-faculty `TITLE` value is `'Visiting'`, and the
  fact means "this offering's own instructor is Visiting-type AND no
  other offering of the same course this semester has a non-Visiting
  instructor" — a compound join-plus-negated-existence check, not
  expressible in any of this compiler's existing structured resolution
  shapes.
- jBilling's `resultCode` meaning: confirmed codes `1=approved,
  2=declined, 3=incorrect (data), 4=reject` — recorded as documentation
  even though (per above) it doesn't change this variable's compilation
  status.

**Two new general resolution shapes, built rather than hacked
one-off, since a genuinely new *kind* of fact showed up twice**:
- `derived_aggregate` gained an optional `value_column` field, extracted
  by a new dotted-aggregate regex (`SUM(TABLE.COLUMN)`, optionally with
  an explicit `FROM <tables>` before the `WHERE`) — `degreeTotalCredits`
  is the first real fact needing an aggregate over a *named* column
  reached via a join, rather than the existing `COUNT(*)`-shaped facts.
  `sql_compiler.py`'s `aggregate_subquery` now compiles a real
  `SUM(COURSE.CREDIT_HRS)` when a `value_column` is present, instead of
  always falling back to the `SUM(1)` placeholder — a strictly additive
  change, verified not to touch any of the 9 pre-existing aggregate
  facts (none use the dotted form).
- A new `raw_sql_boolean` resolution kind (`RAW_SQL:`/`TABLES:` marker in
  a ground-truth row's notes) — a deliberate escape hatch, not a hack
  narrowly named for this one variable, for a fact too bespoke for any
  structured shape to express (`isElectiveTaughtByVisitingScholar-
  UnavailableOtherwise`'s compound join-plus-NOT-EXISTS check). Its own
  SQL template still goes through the exact same `<placeholder>`-
  substitution and prose-shape checks as every other filter text before
  being trusted — never accepted blindly. Folded into the taxonomy's
  existing "Existence / Correlated Subquery" category rather than given
  a 14th one-off bucket, since a correlated `NOT EXISTS` subquery is its
  defining construct.
- **A real bug found while wiring the aggregate fix, fixed immediately**:
  `degreeTotalCredits`' own `notes` field described the aggregate in
  English using the same `SUM(COURSE.CREDIT_HRS)` text as the schema
  field's structured recipe — and since `classify_derived` tries `notes`
  before `raw_schema_field`, the prose match (no `FROM`/`WHERE` to find)
  won and the real recipe was never reached, silently producing a
  `filter_text: null` aggregate. Fixed by rewording the notes prose to
  describe the aggregate in words rather than repeating the literal
  `AGG(...)` call text — a caution now documented directly in
  `_try_extract_aggregate_recipe`'s own docstring for future ground-truth
  authors, not just fixed silently.

**Investigated but left genuinely unresolved, honestly, rather than
guessed at further**:
- Spree's other 5 `preferences`-blob facts (`operatorMin`, `amountMin`,
  `operatorMax`, `amountMax`, `promotionTargetGroupIds`, `basePercent`):
  per the project owner's instruction to assume the best domain answer,
  the real serialized preference keys were confirmed directly against
  Spree's own source (`operator_min`/`amount_min`/`operator_max`/
  `amount_max` on `Promotion::Rules::ItemTotal`, `base_percent`/`tiers`
  on `Calculator::TieredPercent`, likely `customer_group_ids` on
  `Promotion::Rules::CustomerGroup`) and recorded in ground truth. **Not
  wired into an actual SQL extraction**, though: these are genuinely
  serialized YAML/text blobs, not JSON columns, and no real sample row
  was available in this repository to confirm the exact serialization
  format a `SUBSTRING`/`REGEXP` pull would need to match — inventing one
  would be exactly the kind of guess this whole exercise exists to avoid.
  `amountMaxSet`/`promotionTargetGroupsConfigured` stay unresolved for a
  *further* reason even with the keys known: `ItemTotal` declares
  `amount_min`/`amount_max` with hard non-null defaults, so "is the key
  present" can't be what these booleans test, and what they actually
  distinguish isn't recoverable without a real sample row.
- **A real compiler bug found, not fixed this pass**: `effectiveMin-
  Threshold`/`effectiveMaxThreshold` show up as "unresolved: not found in
  ground truth" rather than correctly chaining into the blob-preference
  facts above, even though the DRD edges from `Promotion Item Total
  Eligibility` to `Effective Minimum/Maximum Amount Threshold` are
  present and correct in the DMN XML. Root cause, traced directly: both
  upstream decisions are literal expressions with **no `<variable
  name="...">` element declared at all**, so `Decision.own_variable`
  stays `None` and `resolve_and_substitute`'s DRD-priority check
  (`var_name not in produced_names`) never matches, falling through to a
  flat ground-truth lookup under the wrong decision name. A safe general
  fix needs a way to infer the intended variable name for an unnamed
  literal-expression decision without misattributing it when a decision
  has more than one such upstream edge (this one has exactly two, Min
  and Max, so a naive "just accept it" fallback would pick the wrong one
  half the time) — judged out of scope for a same-day fix and left
  documented here rather than patched speculatively.

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

**Result (updated after every ground-truth pass above, including the
third round)**: 218 of 242 compiled branches (90.1%) produce a fully
clean validation query with zero warnings — OpenMRS 97.2%, Spree 92.6%,
FLEX2 90.3%, jBilling 75.6%. FLEX2's clean rate rose sharply from the
original 48.0% baseline to 90.3% — better than the 84.2% the *mistaken*
`schema_gap` reclassification produced along the way, since that
version's apparent gain was partly an artifact of shrinking the
denominator (blocking branches outright rather than compiling them
cleanly). With `semesterType` correctly resolving to `SEMESTER.TITLE` as
a real equality-comparable column, and the third round's
`degreeMinimumCreditHours`/`degreeTotalCredits`/visiting-scholar facts
now compiling clean too, those branches genuinely compile *and* compile
clean rather than just stop blocking; `projectedTotalCoursesThisRegistration`'s
real filter clause independently removes its own "prose, not SQL"
warning. The flagship attendance branch still
compiles to `(SELECT COUNT(*) FROM LECTURE WHERE OFFER_ID =
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

## `fitness.py` — the branch-distance fitness function (§6.3, built 2026-09-11)

The first piece of the search loop itself (§12 item 7's remaining half, now that both prerequisite artifacts exist): a working, tested implementation of §6.3's branch-distance formula, closing the "design fitness function or mutation/crossover operators next" question the same day it was asked — fitness first, since crossover/mutation act on a candidate representation but are meaningless without a fitness signal to guide them, and the fitness function is independently testable against `compiled_constraints.json` right now with no GA loop needed at all.

**Genome representation, a design choice this file documents since nothing else in the repo had settled it yet**: a flat `{free_variable_name: value}` dict, one entry per *leaf* free variable a branch's condition (and its DRD substitution chain) bottoms out at -- mirroring EvoSQL's own genome choice (§8: a proposed set of concrete column-level values) rather than a fully materialized row set. Turning a winning genome into actual INSERT-able rows (e.g. how many `STUDENT_ATTENDANCE` rows realize a chosen `lecturesAttended` count) stays a separate, deterministic materialization step (§6.5), not part of fitness evaluation -- this is what keeps the search loop's inner loop cheap (arithmetic over a handful of values, no DB round-trip) exactly as §6.5 requires.

**What it implements**: the full §6.3 base distance table (`=`,`!=`,`<`,`<=`,`>`,`>=`) plus AND (sum) / OR (min) / NOT / IN / BETWEEN composition, implemented as a mutually-recursive `distance_to_true`/`distance_to_false` pair rather than literally rewriting the tree with De Morgan's laws first (the same underlying idea, reused directly for both `not(...)` and the FIRST/UNIQUE suppression term rather than re-derived twice). Cross-variable comparisons need no special case at all -- both operands go through the same expression evaluator regardless of whether the right-hand side is a literal or another variable, exactly the extension §6.3 flagged as a required, not optional, design item. `substituted_decision`/`literal_via_upstream_branch` chains are arithmetic-evaluated the same way `sql_compiler.py`'s `compile_value_expr` SQL-compiles them, just producing a number instead of SQL text. FEEL's `today()` is treated as a scenario-level gene (`__today__`) under the same "genuine runtime parameter, not a stored value" logic `not_persisted` already gets in `sql_compiler.py`.

**Honesty over completeness, enforced as a hard error, not a silent pass-through**: `schema_gap`/`code_external`/`unresolved`/`chained_decision_output` are never treated as legitimate genes, even if a genome happens to carry a stray value under that name -- `evaluate_resolution` raises `FitnessEvaluationError` naming exactly which variable and why. For a branch's *own* condition this can never actually trigger (`compile_constraints.py` already refuses to compile such a branch), but it's a real, reachable case for a FIRST/UNIQUE suppression term, found while building this: an *earlier* row in the same decision table can reference a variable that's itself unresolvable, and the branch whose own condition is otherwise perfectly fine still can't have its full fitness (own condition + suppression) computed in-memory. **12 of 242 currently-compiled records (5.0%) are in exactly this position** -- their own condition compiles and validates fine (already reflected in `sql_compiler.py`'s clean-rate numbers), but their FIRST/UNIQUE suppression term cannot be fully verified without a live database, since an earlier row depends on a fact like jBilling's `expiryDate` (`code_external`) or Spree's `promotionTargetGroupsConfigured` (`schema_gap`). This is exactly the two-pass split §6.7 already designs for (fitness computed in-memory during search; a live-engine pass as the ground truth afterward) -- not a new gap, but its first concrete instance, worth naming rather than leaving implicit.

**A real, general gap found in `compiled_constraints.json` itself while building this, fixed in `compile_constraints.py` rather than worked around here**: `hit_policy_context.earlier_rows[i].condition` can reference free variables that never appear in the record's own `condition` at all (a FIRST/UNIQUE decision's different rows commonly test different declared inputs row to row) -- and `variable_resolution` previously only ever covered the current rule's own condition, so a downstream consumer needing the *complete* suppression term (this file) had no way to resolve those variables at all. Fixed generally: every earlier row's free variables are now resolved and merged into `variable_resolution` too (never causing the record to newly block -- an earlier row's own variable being itself unresolvable is recorded as-is, the same honesty its own condition's variables already get). Purely additive: re-running the full pipeline after this fix produced identical compiled/blocked counts (242/18) and identical `sql_compiler.py`/taxonomy numbers, confirmed by diffing before/after. Raised the fraction of compiled records whose *complete* fitness (own condition + suppression) is in-memory-evaluable from 162/242 (67.0%, before the fix) to 230/242 (95.0%, after) in this file's own crash-test sweep.

**Verified against the flagship worked example** (§6.3's own hand-computed numbers): `lecturesAttended=40/lecturesHeldForOffering=45` reproduces the doc's own `(88.9-80)+1=9.9` distance for the debarred rule's own condition (within floating-point/rounding tolerance -- the doc's "88.9" is itself a rounded display of the exact 88.888...%); `=35/45` reproduces the doc's own "done" (distance 0) exactly. Run directly via `python3 fitness.py` (self-contained -- no separate test file needed to reproduce this check).

**Not built yet, and deliberately out of scope for this pass**: the DynaMOSA search loop itself (§6.4) -- crossover/mutation operators, population management, non-dominated sorting with the dynamic DRD-edge-gated objective activation §6.4 specifies.

## Schema/DB constraint terms (§6.3's "combining with database integrity constraints", built 2026-09-11, same day)

Asked directly for a worked example of the fitness equation and how schema constraints factor in -- exposed that half of §6.3 wasn't built yet. Added `not_null_distance`, `unique_distance`, `fk_distance`, and `check_distance` (plus `candidate_constraint_fitness`, the per-candidate aggregator), all reusing the exact same base distance table and `normalize`/sum convention `branch_fitness` already uses for the DMN term -- §6.3's own point in stating both halves share one mechanism.

**Genuinely different input shape than the DMN term needs**: NOT NULL is about one row in isolation, but UNIQUE/PK and FK are properties of a row *against the rest of the candidate* -- so these functions take `candidate_rows: {table: [row_dict, ...]}`, not the flat genome dict `branch_fitness` uses. Reconciling the two views (a genome's variable values lining up with specific row columns) is a materialization-time concern (§6.5), not built here.

**A real, non-hypothetical bug found and fixed before any of this could be tested**: went looking for real FLEX2 NOT NULL/FK data to test against and found `flex2_schema_full.json` (the schema JSON `sql_compiler.py` already depends on for PK lookups) had **zero NOT NULL columns recorded across all 2081 columns in the entire schema** -- including declared primary keys. Root cause, traced directly: `parse_flex2_ddl.py`'s own docstring already honestly flagged this as a known limitation ("NOT NULL is inferred only from inline tokens... FLEX2's actual export uses a separate ALTER TABLE ... MODIFY, which this parser does not track") -- a real, previously-documented gap that had just never been followed up on. Separately, every one of the four case studies' own schema parsers discard FK detail down to just the target *table* name, never which column maps to which -- insufficient for a real FK distance, which needs to know exactly which column to check. Fixed both in `parse_flex2_ddl.py` (FLEX2 only, since it's the design doc's own stated first testbed): added the `ALTER TABLE ... MODIFY (col NOT NULL ENABLE)` pattern (328 NOT NULL columns now correctly detected, exactly matching the 328 raw statements found -- zero silently missed), and preserved per-column FK detail as a new `fk_columns` field instead of discarding it. Verified directly against the real DDL (`schemas/flex2/Flex1.sql`): `COURSE_OFFER`'s 5 NOT NULL columns, `STUDENT_ATTENDANCE`'s composite PK, and all 7 of `COURSE_OFFER`'s FK columns (including `SEM_ID -> SEMESTER.SEM_ID`) match exactly. Re-ran the full pipeline afterward -- identical 242/18 compiled/blocked counts and identical `sql_compiler.py`/taxonomy numbers, confirming the fix only added previously-missing detail rather than changing anything already working.

**Update, same day**: FK distance now works across all four case studies, not just FLEX2. `parse_openmrs_liquibase.py` and `parse_jbilling_ddl.py` had the exact same shape of gap as FLEX2's own parser -- OpenMRS's `addForeignKeyConstraint` elements already carry `baseColumnNames`/`referencedColumnNames` attributes (named in the parser's own docstring, just never read), and jBilling's `FK_RE` regex already captured the local/ref column groups and threw them away (`_fkcols`, `_refcols`) -- both fixed the same way FLEX2's was. Verified against real data: OpenMRS's `encounter.patient_id -> patient.patient_id`, jBilling's `payment.result_id -> payment_result.id` (the same column this session traced by hand earlier today). Spree is different: its historical migration files (what `parse_spree_migrations.py` needs) were only ever available in a prior session's own environment and aren't in this repository at all, so a new, small, dedicated script (`add_spree_fk_columns.py`) parses `schemas/spree_schema.rb`'s 6 real `add_foreign_key` declarations directly instead -- each resolved via Rails' default naming convention and *verified* against the target table's real columns before being trusted, not assumed. `fk_distance` still raises `FitnessEvaluationError` rather than silently returning 0 for any table whose schema entry genuinely has no `fk_columns` data at all (there shouldn't be any left now, but the check stays as a loud tripwire, not a silent pass-through, should a schema JSON ever regress).

**CHECK constraints**: a minimal parser (`parse_check_expression`) for the SQL boolean grammar actually surveyed across the program's own 3 declared CHECK bodies (all Spree: `amount <= 0`, `amount >= 0`, `(line_item_id IS NULL) <> (fulfillment_id IS NULL)`) -- comparisons, `IS [NOT] NULL`, parens, `AND`/`OR`/`<>`, deliberately not a general SQL expression parser (the same targeted-not-general discipline `feel_parser.py` used for FEEL). Parses into this module's own condition-node vocabulary and reuses `distance_to_true` directly -- no new distance logic needed, since a CHECK body is structurally the same kind of boolean tree a DMN condition is. **A real gap this surfaced and fixed generally**: the XOR-shaped commission-lines check needs a boolean sub-expression (`line_item_id IS NULL`) used as the *operand* of another comparison (`<>`) -- `evaluate_expression` had no notion of a comparison node used in value position at all. Fixed generally (any comparison/logical node used where a value is expected now evaluates via its own distance-to-true, not just inside a CHECK), not special-cased to this one constraint.

**Verified against real, not hypothetical, values**: `COURSE_OFFER.SEM_ID` (NOT NULL) — `None` scores `1.0`, `7` scores `0`; `STUDENT_ATTENDANCE`'s composite PK — a duplicate `(101, 1)` pair scores `1.0`, distinct rows score `0`; `COURSE_OFFER.SEM_ID -> SEMESTER.SEM_ID` (FK) — a value present among the candidate's own `SEMESTER` rows scores `0`, absent scores `1.0`; Spree's two simple CHECKs and its XOR-shaped one all score correctly against both a satisfying and a violating row. Run directly via `python3 fitness.py` alongside the flagship DMN-term checks.

## `candidate.py` — does the fitness design generalize to real rows? (built 2026-09-11, same day)

Asked directly: will the current fitness design work for all rules? Answering that honestly meant actually checking, not reasoning about it -- `fitness.py`'s own genome (`{free_variable_name: value}`) had only ever been driven by hand-picked scalars (the flagship worked example's `lecturesAttended=40`), never by values computed from real candidate rows the way a search loop would actually have to. `candidate.py` closes that gap: a `Candidate` (`{table: [row, ...]}`, §6.2's own candidate representation) plus `derive_genome()`, which walks a compiled record's `variable_resolution` and computes each free variable's *real* current value from the candidate's actual rows -- the in-memory-row-set analogue of what `sql_compiler.py` does for SQL text, feeding straight into `fitness.branch_fitness` unchanged.

**The flagship example, this time with real rows, not a scalar**: built a candidate with 40 genuine `STUDENT_ATTENDANCE` rows for the student (`ATTEND_FLAG='Y'`) *plus 5 deliberate noise rows* (3 for a different student, 2 marked absent) a correct filter must exclude, and 45 real `LECTURE` rows. `derive_genome` correctly excludes all 5 noise rows and returns `{lecturesAttended: 40, lecturesHeldForOffering: 45}` -- identical to the hand-picked-scalar test, and `branch_fitness` on it reproduces the exact same `1.8163` score. A second candidate with 35 real attended rows reaches fitness `0.0` exactly, and independently re-checked by materializing the same rows into a real SQLite database and running the DMN condition as an actual query against them -- confirming "fitness says 0" and "a real database agrees" for at least this one case.

**Full-corpus honesty check**: built a (deliberately minimal, auto-generated) candidate for every one of the 242 currently-compiled records and asked whether `derive_genome` could produce a complete, evaluable genome for each. **216/242 (89.3%)** could. The other 26 break down into exactly the categories already documented elsewhere, not new surprises:
- **12** already-known suppression-only unresolvable variables (§6.3's own documented 5.0% gap -- an earlier FIRST/UNIQUE row depending on a `code_external`/`schema_gap` fact).
- **9** unclassified `derived`-kind facts (§7b's "Compound / Unclassified Derivation" catch-all, ~7% of ground truth) -- `derive_value` now raises a dedicated, clearly-worded error for this kind rather than falling through to a generic one, but there's no more structure here to compute from than `classify_derived` itself had to work with.
- **2** (from a genuinely fixable bug, see below) an auto-built test candidate that happened to leave an aggregate at 0.

**A real robustness bug found and fixed while running this sweep**: dividing by a `derived_aggregate` gene that lands on 0 (e.g. `lecturesHeldForOffering=0` for a not-yet-populated course offering) crashed the whole evaluation with a raw `ZeroDivisionError` instead of giving the search a value to move away from -- a genuinely reachable candidate state during search, not a hypothetical. Fixed in `fitness.py`'s own arithmetic evaluator (`_safe_div`) to raise a clear `FitnessEvaluationError` instead, consistent with every other "can't evaluate this" case in the module.

**What this answers, and what it doesn't**: it confirms the branch-distance formula itself is consistent whether fed a hand-picked scalar or a value derived from real, noisy candidate rows -- the equation isn't the weak point. It does *not* yet prove every "fitness = 0" genome the eventual search finds is buildable as fully consistent rows across a *shared* candidate spanning multiple branches at once (DynaMOSA's own per-case-study population) -- `derive_genome` is stateless and takes whatever `Candidate` it's given, so nothing prevents passing the same shared one to every branch, but that hasn't been exercised with more than two branches sharing one candidate yet. That's the search loop's own job to exercise, not this bridge's.

**Known, stated-not-discovered limitation**: `_mechanical_filter_predicate` only recognizes plain `COLUMN = VALUE`/`COLUMN = <placeholder>` conjuncts joined by `AND` -- exactly the shape §7b's own survey found, same discipline `feel_parser.py`/`parse_check_expression` already use elsewhere in this program. A conjunct like the flagship's own `"LECTURE_ID IN (LECTURE for that OFFER_ID)"` (a join description in prose, not a clean equality) is skipped and reported as a warning, not silently dropped -- meaning a derived count can be a real *over-count* on exactly the skipped conjuncts' account. This is the same honesty tradeoff `sql_compiler.py` already makes for the identical filter text, applied to in-memory evaluation instead of SQL compilation.

## `mutation.py` — the mutation operator (§6.4, built 2026-09-11, same day)

Two sub-operators, chosen automatically by the mutated leaf's own resolution kind, never chosen by the caller: **M1 (field mutation)** for `schema_column`/`null_check`/`any_not_null`/`join_lookup`/`join_null_check`/`regex_match`/`derived_case` (perturb one row's one column), and **M2 (row-count mutation)** for `derived_aggregate`/`exists` (add/remove a whole row -- nothing on a single row is *the* count). Direction is decided uniformly for both by reusing `branch_fitness` directly (try each candidate replacement value in the genome, keep whichever comes out lowest) rather than hand-derived per-kind logic. Field mutations use an *enumerable domain* drawn straight from the branch's own condition literals (`enumerable_domain`) when one exists -- never a random string -- falling back to numeric step/character-edit otherwise. `mutate()` always edits a *copy* of the candidate (parents untouched); `hillclimb()` wraps it into a (1+1) local search -- not DynaMOSA itself, but a legitimate standalone mode (§6.4's own "local search" allowance) and the way this operator gets exercised end to end.

**A real bug found before it could bite silently**: a leaf nested inside a `substituted_decision`'s own `free_variable_resolutions` (e.g. `lecturesAttended` inside `attendancePercentage` -- exactly the flagship record's own shape) is not a top-level key of `variable_resolution` and can't be looked up again that way. `_leaf_variables` now returns the actual `(var_name, node)` pairs from its own recursive walk, not just names re-looked-up incorrectly afterward.

**Verified on the flagship rule from a deliberately wrong start** (44/45 attended, the wrong side of the 80% threshold): `hillclimb` converges to fitness exactly 0.0 in 11 accepted steps, strictly monotonically non-increasing throughout -- it found this by *increasing* `lecturesHeldForOffering` rather than decreasing `lecturesAttended`, a different but equally valid solution, confirming the operator genuinely explores rather than following one expected path.

### A second real bug this exposed: `semesterType` was still wrong (fixed the same day)

Testing the mutation operator against `Course Load Limit::Rule_1` (which compares `semesterType`) caught a bug in this session's own earlier "fix" for `semesterType` (§13.16/§13.17): the DMN rules compare it against `'Regular'`/`'Summer'` -- a **different, two-category vocabulary** than `SEMESTER.TITLE`'s own three real values (`'Fall'`/`'Spring'`/`'Summer'`, per the project owner's own confirmed domain knowledge). A plain `schema_column` passthrough can never equal `'Regular'` for any real row -- and confirmed directly: the mutation operator exploited exactly that gap, "solving" the branch by writing the impossible value `TITLE='Regular'` straight into a candidate row. Fitness said 0; the row was fiction -- precisely the risk flagged when `candidate.py` was first built, now caught concretely rather than just argued about.

**Fix**: a new resolution kind, `derived_case` -- a real column value mapped through an *exhaustive*, hand-authored enumeration (`CASE_MAP:` marker in the ground-truth notes, parsed by `compile_constraints.py`'s `_try_extract_case_map`) into the DMN's own vocabulary. Deliberately no ELSE/default clause: an unmapped real value should surface as a hard "we don't know how to categorize this," never silently fall through to a guess. `semesterType`'s ground-truth row now reads `CASE_MAP: SEMESTER.TITLE: 'Fall' -> 'Regular'; 'Spring' -> 'Regular'; 'Summer' -> 'Summer'`.

Wired into every consumer that needed it: `candidate.py`'s `derive_value` reads the real column value and maps it forward (raising if a real value shows up that isn't in the table); `sql_compiler.py` compiles it to a real SQL `CASE WHEN ... END` expression (no `ELSE`, same honesty); `mutation.py`'s field mutation **inverts** the mapping when writing back -- mutating toward `'Regular'` writes a real `'Fall'`/`'Spring'` value, never the literal string `'Regular'` itself. `fitness.py` needed no change at all: `derived_case` is just another leaf gene as far as the DMN-term equation is concerned, exactly like `derived_aggregate` already was.

**Verified**: `mutation.py`'s own self-check now confirms both directions explicitly -- mutating toward `'Summer'` writes `'Summer'`; mutating toward `'Regular'` writes `'Fall'` or `'Spring'`, never `'Regular'` itself. Re-ran the full pipeline afterward: identical 242/18 compiled/blocked counts and identical `sql_compiler.py` clean-rate numbers (purely a resolution-shape change, not a new gap or a closed one) -- the only visible shift is `taxonomy/`'s own storage-shape table, where `semesterType` moves from "Direct Attribute Reference" to "Single-Column Predicate" (93→92, 28→29), folded into that category rather than given a 15th one-off bucket since it still decomposes to one real column compared against a named constant, just through a `CASE` expression.

## Testing `mutation.py` against tricker rules (2026-09-11/12) -- three more real bugs found

Explicitly went looking for rules likelier to break the operator than the
flagship attendance rule did: a deeply-nested `AND`/`NOT IN` condition with
a FIRST-hit suppression row (`Course Registration Eligibility::Rule_2`,
both a feasible and a deliberately structurally-infeasible grounding of
it), `derived_case` (`semesterType`) exercised through the full
`mutate()`/`hillclimb()` loop rather than just `apply_mutation` in
isolation (`Course Load Limit::Rule_2`), a branch carrying both a
`raw_sql_boolean` leaf and a permanently-unclassified `derived` leaf
together (`Summer Semester Registration::Rule_2`), and a genuine
cross-variable comparison (`projectedTotalCoursesThisRegistration >
maxCoursesAllowed`) combined with `derived_case` and a 2-level chained
suppression structure (`Course Registration Eligibility::Rule_3`). Found
three real bugs, none of them hypothetical:

**Bug 1 -- `unmetPrerequisiteCount` and `previousGradeInCourse` resolved to
the exact same physical column.** Crashed immediately on the first test
(`TypeError: '>' not supported between 'str' and 'int'`), traced to
`compile_constraints.py`: `unmetPrerequisiteCount`'s raw ground-truth text
is `"COUNT via COURSE_PREREQ join COURSE_REGISTRATION.GRADE"` -- a real
join-based aggregate -- but `_try_extract_aggregate_recipe`'s three regexes
all require a literal `AGG(...)` call syntax, so this text matched none of
them and fell through the generic `len(pairs)==1` fallback straight to a
plain `schema_column` on `course_registration.grade` -- the *same* column
`previousGradeInCourse` (a letter-grade string) also resolves to, even
though `unmetPrerequisiteCount` is a number compared with `> 0`. **Fixed**
with a new resolution kind, `derived_join_count`: a real correlated-COUNT
recipe (confirmed against `schemas/flex2/Flex1.sql`'s own DDL) -- counts a
course's `COURSE_PREREQ` rows for which the student has no passing
`COURSE_REGISTRATION` (grade not in the same `{F,D,D+,C-}` blocklist
`previousGradeInCourse` already uses). Occurs exactly twice in the whole
program (grep-verified), both FLEX2, both this same table pair; "this"
course/student context is found by matching whichever focal row carries
both key columns (`COURSE_REGISTRATION` itself for Course Registration
Eligibility, `EXEMPTED_COURSES` for Credit Transfer Exemption -- both real
tables confirmed via DDL to carry them), not a hardcoded table name. Wired
through all four places a resolution kind needs it: `candidate.py`
(real join+anti-join count over actual rows), `mutation.py` (row-count
mutation: add a row for a fresh unmet prerequisite / remove one to
decrease), `sql_compiler.py` (a real `COUNT ... NOT EXISTS` correlated
subquery), and `taxonomy/`'s categorizer (folded into Aggregate Function).
Re-ran the full pipeline: identical 242/18 compiled/blocked counts;
`candidate.py`'s own full-corpus sweep coverage went *up*, 216/242 (89.3%)
-> 218/242 (90.1%), the two previously-miscounted records now correctly
evaluable.

**Bug 2 -- mutating toward a `NOT IN` target cycled forever among the
blocked values themselves.** `previousGradeInCourse NOT IN {F,D,D+,C-}`:
starting wrong (`'F'`), hillclimb stalled at fitness `0.5` instead of `0`.
Diagnosed directly: `candidate_values`' domain-based candidates for this
leaf were `['D', 'D+', 'C-']` -- every one of them *also* a blocked grade,
so branch-distance scored all three identically to the wrong starting
value. `enumerable_domain`/`_collect_literal_comparisons` collected every
literal a variable is compared against, but never distinguished "hitting
one of these makes the condition true" from "avoiding *all* of these does"
-- a `NOT IN`'s own listed members are exactly the values that must be
escaped, never candidates worth trying. **Fixed** by tracking `not`-polarity
while walking the condition (`_collect_domain_facts`, replacing the old
polarity-blind collector) to split literals into `hit` (try these) vs.
`avoid` (escape these), and adding `_domain_escape_value` -- a value
guaranteed outside the avoid-set (one past the max for a numeric domain, a
suffixed string otherwise) -- as an extra candidate whenever `avoid` is
non-empty. Re-verified: A's feasible grounding now reaches fitness `0.0` in
4 steps (previously stuck at `0.5`); re-ran `mutation.py`'s own flagship
self-check afterward with no change in behavior (that rule never had an
`avoid`-only leaf, so the fix is additive there).

**Bug 3 -- `mutate()` crashed outright the moment a `raw_sql_boolean` leaf
looked improvable.** `raw_sql_boolean` is deliberately unmutatable
(`apply_mutation` explicitly raises for it -- "too bespoke... needs a
fact-specific operator"), but it's *also* listed in `BOOLEAN_LEAF_KINDS`,
so `candidate_values`/`best_value_for` are perfectly happy to say flipping
it would improve fitness. `mutate()` never caught `apply_mutation`'s own
refusal, so the moment hillclimb's random leaf choice landed on such a leaf
*and* flipping it looked like an improvement, the exception propagated
straight out of `mutate()`/`hillclimb()`, killing the whole search --
reproduced directly with a minimal synthetic record (not hypothetical:
this is exactly the shape `Summer Semester Registration::Rule_2`'s own
`isElectiveTaughtByVisitingScholarUnavailableOtherwise` leaf has). **Fixed**
by catching `FitnessEvaluationError` around the `apply_mutation` call in
`mutate()` and treating it exactly like "not improved" -- this leaf isn't
mutatable, so hillclimb tries a different leaf next iteration instead of
dying. Re-verified the repro no longer crashes, and re-ran `mutation.py`'s
own self-check with no change in outcome.

**What survived as a real, honest (non-bug) finding, not fixed today**:
`Course Registration Eligibility::Rule_3`'s `projectedTotalCoursesThisRegistration
> maxCoursesAllowed` needed the count to climb from 4 to 100 -- a 96-unit
gap. With the fixed step size of 1 candidate value per mutation and only
6 leaves to randomly choose among, 500 iterations wasn't enough budget
(stalled at 97/100, fitness 0.75); raising the budget to 5000 iterations
reached fitness exactly `0.0` in 99 accepted, still-monotonic steps --
confirming the operator itself is correct, just that it has no AVM-style
"probe and accelerate" step-doubling yet (the design doc's own §6.4 names
this as AVM's technique, borrowed only in spirit so far) — a real
follow-up worth building before DynaMOSA is expected to close large
numeric gaps in a reasonable iteration budget, not a defect in what's
built today.

Also confirmed (not a bug): `Summer Semester Registration::Rule_2` can
never be fully generated end to end regardless of candidate quality --
`isNeededToGraduateThisSummer` is a permanently-unclassified `derived`
catch-all fact (§7b's own documented ~7% gap), and `derive_genome` raises
for the whole record the moment it hits any such leaf. Verified this is
the *only* remaining blocker by supplying a fully-materialized candidate
for the record's other, initially-untested `raw_sql_boolean` leaf first
(real `COURSE_OFFER`/`EMPLOYEE`/`D_EMP_TYPE` rows) and confirming it
compiles cleanly through SQLite, leaving `isNeededToGraduateThisSummer`
as the one and only failure.

## Wiring schema/DB constraints into the mutation objective (2026-09-12)

Asked directly whether row mutation checks FK/schema constraints. Checked
rather than assumed: no -- `mutation.py` only ever imported and optimized
`branch_fitness` (the DMN term); `fitness.py`'s own constraint-distance
functions (`not_null_distance`, `unique_distance`, `fk_distance`,
`check_distance`, `candidate_constraint_fitness`) existed and worked, but
nothing in `mutation.py` ever called them. Demonstrated concretely before
touching any code: the D test candidate from the tricker-rules sweep
above, having converged to `branch_fitness == 0.0`, scored
`candidate_constraint_fitness == 68.3` on the exact same rows -- 96
near-empty `COURSE_REGISTRATION` rows added purely to satisfy a `COUNT`
aggregate, none with a real `COURSE_ID`, all missing other required
columns, several byte-for-byte duplicates.

**Fix**: mutation's objective is now `branch_fitness + candidate_constraint_fitness`
(`_combined_fitness`), not the DMN term alone. This forced a real
mechanical change, not just an extra addend: `candidate_constraint_fitness`
needs actual materialized rows (NOT NULL/UNIQUE/FK/CHECK can't be read off
a flat genome), so the old "try each candidate value cheaply in-genome"
hypothetical had to go -- `best_value_for` now actually applies every
candidate value to a real, deep-copied `candidate`/`focal`/`scenario` and
scores that copy, adopting whichever scores lowest. This also cleanly
subsumed the earlier "`mutate()` crashes on an unmutatable-but-improvable
leaf" fix (§ above): a value `apply_mutation` refuses now just fails its
own trial's `try/except` and is skipped, no separate patch needed.

**Verified working**: re-ran tests A and B from the tricker-rules sweep.
Both still reach `branch_fitness == 0.0` (the DMN term is still solved),
and now the constraint residual is visible and honestly reported rather
than invisible: A ends at DMN `0.0` / constraint `1.33`, B at DMN `0.0` /
constraint `0.67` -- real, existing violations mutation now *measures*
even though (see below) it can't yet fully repair them. The flagship
attendance self-check now visibly reports a `0.5` constraint residual too
(a real, correctly-identified `LECTURE.OFFER_ID -> COURSE_OFFER.OFFER_ID`
FK violation -- the search deleted every row down to the one it needed,
since `COURSE_OFFER` was never populated).

**A genuine, previously-invisible emergent problem this surfaced, on
test D**: re-running D (the cross-variable-comparison test, needing
`projectedTotalCoursesThisRegistration` to climb from 4 toward >99)
against the combined objective, hillclimb got stuck at combined fitness
`1.657` after only 6 steps and never moved again in 5000 iterations --
worse on the DMN term than where it started. Diagnosed directly, not
guessed: hillclimb had greedily *deleted* rows all the way down to
`projectedTotalCoursesThisRegistration = 0`, because each constraint-
incomplete row `derived_aggregate`'s M2 adds costs a full `K`-scale
constraint penalty (~0.5-1.0 normalized) while contributing only a tiny
fractional DMN improvement toward a target 99 units away -- so *removing*
rows always looked better to a one-step-lookahead greedy search than
*adding* the (still-incomplete) rows actually needed to reach the DMN
target. Confirmed by hand: from the stuck state, trying
`projectedTotalCoursesThisRegistration = 1` scores combined `2.32`,
worse than staying at `0` (`1.657`) -- a real local optimum, not a bug.

This is not a mutation.py defect -- it's the exact, now-demonstrated
reason the design doc's own §6.4 keeps the DMN term and the constraint
term as *separate* DynaMOSA objectives (Pareto-compared per test case,
never summed into one scalar) rather than a single combined number: an
unweighted sum lets one objective's large per-step cost mask another's
real, necessary long-range improvement, exactly what a single-objective
(1+1) hillclimb has no way to see past.

### The actual fix: repair-by-construction, not a search objective (2026-09-12, same day)

Asked directly what to do about this, the recommendation was to stop
treating NOT NULL/UNIQUE/FK as something for the search to *discover* at
all -- they're mechanically decidable from the schema alone with no
DMN-relevant ambiguity (a column either must be set or it doesn't; a FK
either has a valid parent or it doesn't), so summing them into a fitness
landscape was always going to create exactly the kind of masking problem
above found. The real fix: revert `hillclimb`/`best_value_for` to
`branch_fitness` alone (the original, cheap, genome-only design), and
give `apply_mutation` a mandatory repair step (`_repair_row`) that makes
every row M1/M2 touches or constructs schema-legal *immediately*, by
construction -- filling required NOT NULL columns with a type-appropriate
placeholder (a *fresh*, never-reused value when that column is also part
of a declared key, so repair itself never manufactures a new UNIQUE
collision across the many near-identical rows M2 often adds for one
aggregate count), and auto-materializing a minimal parent row for any FK
column that's set but has no match yet -- recursively repairing that new
parent row too, so it doesn't trade one FK gap for a fresh NOT NULL gap
on the row just created to close it. `candidate_constraint_fitness`
stays available, just as a post-hoc audit metric now, never a search
signal. CHECK constraints are the one real exception (they constrain the
*same* values a DMN branch may care about, a genuine trade-off, not a
mechanical fill-in) -- left as a stated scope boundary for whenever a
real population/Pareto DynaMOSA loop exists to give them their own
objective; rare enough (3 CHECK constraints total, Spree only) that this
isn't blocking.

**A second real bug found while building this**, unrelated to the
objective question but only surfacing once real deep-copied candidates
were being compared side by side: `copy.deepcopy(candidate)` and
`copy.deepcopy(focal)` as two *separate* top-level calls silently break
the object aliasing between a focal row and its own entry in the
candidate's row list (they start out as the literal same dict; copying
them apart makes two independent copies with equal-but-diverging
content). A field mutation would then write into `focal`'s copy while
`candidate`'s own stored row stayed stale -- the genome a mutation was
scored on could diverge from what the adopted candidate actually
contained. Fixed by deep-copying `(candidate, focal)` together in one
call, preserving the same shared references they had before copying.

**Verified working, concretely, not just re-passing the old assertions**:
- The flagship attendance self-check (seeded with a deliberately
  incomplete `STUDENT_PROGRAM` row, missing `PROG_ID`/`BATCH_NO`, to
  prove the scope boundary) reaches `branch_fitness == 0.0` and
  `candidate_constraint_fitness == 0.667` -- and that residual is
  entirely the pre-seeded incomplete row repair was never responsible
  for; every row mutation itself built (8 new `LECTURE` rows, the
  auto-materialized `COURSE_OFFER` parent row FK-repair created for
  them) is fully schema-clean, confirmed directly via `fk_distance`/
  `not_null_distance` on each, not just inferred from the total.
- Tests A and B (from the tricker-rules sweep) now reach **`branch_fitness
  == 0.0` AND `candidate_constraint_fitness == 0.0`** -- fully clean,
  not just DMN-solved.
- Test D -- the exact case that got trapped under the summed objective --
  now converges again in 99 steps (matching its original DMN-only
  behavior before any of this session's constraint work), with a residual
  constraint distance of `2.0`, traced entirely to the test's own 4
  hand-seeded `COURSE_REGISTRATION` rows (never touched by mutation, so
  never repair's to fix) rather than anything mutation constructed.

## `crossover.py` -- the crossover operator (§6.4, built 2026-09-12)

**Uniform table-mask crossover**: recombines two parent `Candidate`s into
two complementary children by choosing, independently per table, which
parent's *entire* row-set for that table the child inherits -- a coin
flip per table, the same "uniform crossover" a GA applies per-locus to a
fixed-length chromosome, except the locus here is a whole table's
row-list, not a scalar gene. Table, not row, is the unit of
recombination: individual rows across two unrelated parent candidates
have no stable identity to align gene-by-gene the way two same-length
chromosomes would (parent1's 5th `STUDENT_ATTENDANCE` row and parent2's
5th are arbitrary, unrelated list entries), but a whole table's row-set
is a clean, atomic unit every candidate shares regardless of population
history.

**Mandatory FK-repair pass**: swapping a table's row-set wholesale from a
different parent very often leaves a dangling FK -- reuses
`mutation.py`'s own `_repair_row` directly (the same schema-legal-by
-construction discipline mutation's M1/M2 already apply, 2026-09-12,
§ above), not a second, competing repair mechanism, so a crossover child
and a mutation child are schema-legal by the exact same rule.

**Verified concretely, not just asserted**: built two independently
DMN-solved, schema-clean parents for the flagship attendance rule with
deliberately zero row-identity overlap (different student, different
course offering, disjoint `LECTURE_ID`/`OFFER_ID` ranges), so any
crossed table pairing is *guaranteed* to produce a real dangling FK, not
a hopeful example. Confirmed the raw, unrepaired table swap really does
score `candidate_constraint_fitness == 25.17` (the `STUDENT_ATTENDANCE`
rows reference `LECTURE_ID`s the swapped-in `LECTURE` table doesn't
have), then confirmed the real operator's own repair pass closes it to
exactly `0.0` on both children. Also confirmed: the two children are
complementary (each content-distinguishable table comes from the
opposite parent across the pair), parents are never mutated, and the
mask is fully reproducible from a given `rng` seed.

**A real reproducibility bug found and fixed while testing this**:
iterating a bare `set` of table names to build the coin-flip mask meant
the *same* rng seed could silently produce a *different* mask across
separate process runs, since Python randomizes string hashing (and
therefore set iteration order) per process by default unless
`PYTHONHASHSEED` is fixed. Confirmed directly: three processes with
`PYTHONHASHSEED=1/2/3` printed three different orderings of the same
four-table set. Fixed by iterating `sorted(...)` instead of the raw set;
re-verified three full self-test runs under different `PYTHONHASHSEED`
values now produce byte-identical output.

**Honest, not asserted, closing observation**: crossover guarantees
schema-legality unconditionally, but makes no promise at all about DMN
branch fitness -- a child built from two parents solving *different*
scenarios can end up genuinely invalid for either parent's own scenario
(concretely reproduced: `rng.Random(2)` on these two parents leaves both
children's `lecturesHeldForOffering` at `0` for either original
scenario, a real `0/0` `FitnessEvaluationError`, not a crash). This is
ordinary GA behavior -- a population's fitness improves through selection
pressure across many crossover events and generations, not because every
single recombination individually preserves it.

Self-contained via `python3 generator/crossover.py`.

## `search.py` -- do we need crossover? Escalation, not automatic use (2026-09-12)

Asked directly whether crossover is needed at all. Honest answer: not
always, and not on its own -- `crossover.py`'s own self-test already
proved recombination alone doesn't preserve or improve DMN fitness (its
payoff only comes from *selection* choosing which children survive), and
§7a's own finding (most rule rows test one dedicated variable, even
under FIRST hit policy) means mutation-only hillclimb already suffices
for the common case, confirmed repeatedly across this session's own
tricky-rule tests. Building the full per-case-study DynaMOSA population
loop (§6.4's settled algorithm-of-record) to make crossover pay off
everywhere is a substantially larger build than either operator alone.

**What was actually built**: `solve_branch()` -- mutation-only hillclimb
first (cheap, proven); escalates to a small population + crossover GA
*only* when hillclimb stalls within its iteration budget. This directly
follows §6.4's own already-stated hybrid strategy ("Escalate to a genetic
algorithm ... when (a) many targets need to be covered together
efficiently ... or (b) a target requires jointly consistent values...")
rather than a new decision -- and is explicitly **not** the full
per-case-study population/Pareto loop (one shared population across
every branch, DRD-gated dynamic objective activation, non-dominated
sorting): that's a substantially larger, separate build, not attempted
here. This is the smaller, immediately useful piece -- a single-branch,
single-objective escalation, matching what SchemaAnalyst/EvoSQL already
do per-target below the DynaMOSA framing.

The escalation loop itself: seeds a small population with the mutation
phase's own best-so-far (never discarded) plus several independent
shorter hillclimbs from the *original* start (different rng streams) for
diversity -- each member is itself already a locally-optimized candidate,
not a naive random one. Each generation: sort by fitness, keep the top
half as elite parents, recombine pairs via `crossover.py`'s table-mask
crossover (which now also carries `focal` through the same table-parent
choice -- extended for this, see below), then polish each child with 1-3
mutation steps. Replace the population with elites + offspring, truncate
back to size.

**A real bug in `crossover.py` found while wiring this in**:
`_repair_row`'s FK-repair branch can add a brand-new table key to a
child (synthesizing a minimal parent row for a table the mask never
selected at all) -- `crossover()`'s own repair loop was iterating
`child.as_dict().items()` live, so this raised
`RuntimeError: dictionary changed size during iteration` the first time
a crossed pair actually needed a new table. Fixed by snapshotting with
`list(...)` before iterating (safe: any row `_repair_row` itself creates
is already repaired recursively before it returns, so there's nothing
left for the outer loop to do for a newly-added table).

**`crossover()` extended to carry `focal`**: added optional
`focal1`/`focal2` parameters, returning `child_focal1`/`child_focal2`
built the same way the row-sets are -- whichever parent supplies a
table's rows also supplies that table's focal entry, copied via the same
joint `copy.deepcopy` call as the row list (mutation.py's own
`(candidate, focal)` aliasing fix, §13.25, applied here too, since a
focal row is frequently the identical object as one of that table's own
rows). Needed because `mutate()`/`hillclimb()` require a `focal` to know
which row is "this" for every leaf -- without it, further mutation
polish on a crossed child would silently create disconnected duplicate
rows instead of editing the right one.

**Verified, honestly, with results that go both ways**:
- **Escalation correctly never triggers when unneeded**: the flagship
  attendance rule with a generous budget solves via mutation alone;
  `population_history` stays `None`.
- **Escalation genuinely rescues a budget-starved but tractable branch**:
  `Course Load Limit::Rule_2` (independent facts on two separate tables,
  `SEMESTER` and `STUDENT_PROGRAM` -- exactly the shape table-mask
  crossover targets) given only 1 mutation iteration barely moves
  (`0.909 -> 0.9`), but the population phase reaches fitness exactly
  `0.0` in 2 generations.
- **An honest limit, not hidden**: the same escalation applied to the
  cross-variable `Rule_3` case (needing `projectedTotalCoursesThisRegistration`
  to climb ~99 units) triggers, never regresses below the mutation
  phase's own best, but does **not** rescue it -- table-level
  recombination has no lever for a large single-scalar numeric gap;
  that needs AVM-style step-doubling (a separate, still-unbuilt
  follow-up, unchanged by this work).
- **Structural infeasibility is still reported honestly**: a branch with
  a fixed literal that can never match its own requirement stays
  `solved: False` after the full escalation budget, never a false
  success.

Self-contained via `python3 generator/search.py`.

## AVM step acceleration (2026-09-12)

Built the "still-unbuilt AVM step" flagged in `search.py`'s own Case 2b
finding: mutation's numeric leaves (`schema_column`/`derived_aggregate`/
`derived_join_count` with no enumerable domain) now use AVM's real
"probe and accelerate" discipline in `best_value_for`, not a fixed
step of 1. Try step=1 both ways; once a direction improves, keep
doubling the step in that same direction as long as it keeps improving;
halve back down on overshoot; give up on this variable only once step=1
fails in both directions. Every other leaf kind (boolean, enumerable
-domain, string single-char edit) is completely unaffected -- a small,
explicit eligibility check (`_numeric_step_eligible`) routes only the
step-sensitive kinds through the accelerating loop; everything else
keeps the exact original single-pass behavior.

**A real companion bug this forced into the open**: once `best_value_for`
can legitimately decide the best value for a `derived_aggregate`/
`derived_join_count` leaf is many units away, `_apply_row_count_mutation`
still only ever added or removed *one* row per call regardless of the
decided step -- meaning the genome `best_value_for` scored (many units
away) would silently diverge from what the real candidate actually
gained (one row) the moment it was applied. Fixed by moving the *full*
`value - current` distance in one call (looping the same per-row
construction/removal logic `abs(value - current)` times), for both the
generic aggregate branch and `derived_join_count`.

**Verified with real, dramatic before/after numbers, not just "it still
passes"**:
- The flagship attendance self-check, previously needing 11 accepted
  mutation steps to converge, now converges in **2** -- the very first
  leaf picked jumps `lecturesHeldForOffering` from 45 straight to 60
  (1+2+4+8=15, exactly the doubling sequence), reaching fitness `0.0`
  immediately.
- The cross-variable `Rule_3` test from the tricky-rules sweep, which
  previously needed ~99 individual +1 steps (and a 5000-iteration budget
  to be sure of it), now converges in **4** steps with the *default*
  300-iteration budget.
- `search.py`'s own Case 2b (built specifically to demonstrate
  escalation rescuing this same branch when starved) had to be
  re-measured after this fix: mutation alone now solves it from a
  budget of 10, where it previously needed the full population/crossover
  escalation at a budget of 20. The bar for what counts as "starved"
  moved a lot -- escalation is still real and demonstrable (re-verified
  at a tighter budget of 3), just needed for a much narrower slice of
  branches than before.

Every other test in this session's own record was re-run after this
change: `compile_constraints.py`/`candidate.py`'s counts are unchanged
(this only touches how mutation *searches*, never what a genome/candidate
means), and the full A/B/C/D tricky-rules sweep still passes with the
same DMN-convergence verdicts as before -- just in far fewer steps.

Self-contained via `python3 generator/mutation.py`.

## `materialize.py` -- §6.5: from a solved `Candidate` to a real, validated dataset (2026-09-12)

The first concrete step toward the actual deliverable ("real generated
datasets," not just a search algorithm) -- built as three pieces, in the
order §6.5 itself names them:

1. **`topological_table_order`** -- a real topological sort (Kahn's
   algorithm) over the schema's own `fk_columns` data, so materialized
   output always inserts lookup tables before the fact tables that
   reference them. A genuine FK cycle (rare, but real -- a
   self-referencing column, two tables pointing at each other) is broken
   deterministically (placing the least-blocked table next) and
   *reported*, never silently hidden or left to crash Kahn's algorithm.
2. **`to_sql_inserts`** / **`write_csv_files`** -- two views of the same
   materialized rows: real `INSERT` statements in FK order, or one CSV
   per table.
3. **`validate_with_sqlite`** -- §6.5's own "non-negotiable" validation
   pass: builds a throwaway in-memory SQLite database from the schema's
   *real* declared DDL (columns, types, NOT NULL, PK, FK, with
   `PRAGMA foreign_keys = ON`), then attempts every row as a genuine
   INSERT. The engine is the ground truth here, not
   `candidate_constraint_fitness`'s own hand-written distance math --
   this is what actually proves a materialized candidate is valid data,
   independent of whether that separate check agrees.

**`build_seed_candidate` promoted from a self-test to a real API**: the
generic candidate-construction logic that lived inside `candidate.py`'s
own `__main__` corpus sweep is now `candidate.py`'s own
`build_seed_candidate(record)` -- the actual entry point a real
generation run (or `materialize.py`'s own tests) uses to get a starting
candidate with no per-record hand-holding. The corpus sweep itself now
calls this function instead of duplicating its logic.

**Three real, load-bearing bugs found getting the flagship rule to
materialize and validate cleanly end to end, from a fully generic seed,
for the first time** -- not incidental polish, each one blocked the
whole pipeline until fixed:

1. **Repair only ever covered rows mutation itself touched.**
   `_repair_row` (mutation.py's own NOT NULL/FK construction discipline)
   only fires on rows M1/M2 construct or edit during search --
   `build_seed_candidate`'s own seed rows for a "bystander" table (one a
   `derived_aggregate`'s FROM-list names but the search has no reason to
   ever mutate) stayed exactly as informationally-thin as the seed left
   them, all the way to materialization. Fixed with a new bulk utility,
   `repair_candidate(candidate, case_study)` -- repairs *every* row
   currently in a candidate, not just future mutation targets. `solve_branch`
   now calls this on its own input as a deliberate, documented exception
   to "never touch the caller's objects" (idempotent and additive-only,
   so always safe).
2. **`create_table_ddl` declared FK clauses to tables that were never
   actually part of the materialization.** A nullable FK column that no
   leaf mutation ever set (e.g. `BATCH.SHIFT_ID -> D_SHIFT`) is legitimately
   unset and never checked by real SQL -- but the DDL still *named*
   `D_SHIFT` in a `FOREIGN KEY` clause even though `D_SHIFT` was never
   part of this candidate's own table set, and SQLite (with FK
   enforcement on) rejects `CREATE TABLE` outright with "no such table"
   the moment *any* declared FK target is missing, regardless of whether
   any row ever violates it. Fixed by only emitting a FK clause when its
   target table is actually among the tables being materialized this
   run -- correct, not a workaround: `repair_candidate` already
   guarantees any FK column that got a real *value* also got a real
   parent row materialized alongside it, so this can never hide a genuine
   dangling reference.
3. **`build_seed_candidate`'s own `derived_aggregate` seeding never
   matched the branch's own filter.** The original seed rows were a bare
   `{'X': i}` -- no column the branch's `filter_text` conjuncts (e.g.
   `ROLL_NO=<student>`) actually named, so the aggregate always counted 0
   regardless of how many rows were seeded, producing an immediate `0/0`
   division before `hillclimb` could even take its first step. Fixed
   with a new shared helper, `_row_from_filter_conjuncts` (the
   construction mirror of the module's own `_mechanical_filter_predicate`,
   built to the identical parsing rules mutation.py's own M2 "add a row"
   logic already uses), and dropped the leftover `'X'` placeholder key
   entirely once real columns exist (it isn't needed to keep rows
   distinct, and a fake column name broke real SQLite validation on its
   own account: "table LECTURE has no column named X").

**Verified with a genuinely complete run, not a partial one**: the
flagship rule now goes `build_seed_candidate` -> `repair_candidate` ->
`hillclimb` -> `to_sql_inserts`/`write_csv_files` -> `validate_with_sqlite`
with **zero hand-built fixtures anywhere in the chain** and reaches
`branch_fitness == 0.0` *and* `validate_with_sqlite` reporting `ok=True,
0 errors` against real SQLite DDL. A hand-built, already-tested candidate
(reusing `mutation.py`'s own flagship self-check setup) was verified the
same way first, to separate "does the emission/validation machinery
itself work" from "does the fully-generic pipeline work" -- both do, but
they're two different claims and were checked as two different tests.

**A real, incidental improvement this surfaced**: fixing
`derived_aggregate`'s generic seeding also raised `candidate.py`'s own
full-corpus sweep from 218/242 (89.3%, real-candidate coverage) to
**220/242 (90.9%)** -- two records that used to fail with a division-by
-zero (the exact bug the filter-conjunct fix targeted) now evaluate
cleanly.

**Known scope limit, stated plainly**: this is per-branch
materialization -- one solved `Candidate` in, one validated dataset out.
Combining multiple branches' solutions into one shared, case-study-wide
dataset (so a real generation run covers every branch at once rather
than one at a time) is the population loop's job (§6.4), not yet built.
`exists`/`raw_sql_boolean`'s own seed rows in `build_seed_candidate`
still use a placeholder `'X'` column in the cases where no real column
name can be mechanically extracted -- unaffected by today's fix (that
gap is `raw_sql_boolean`'s and `derived`'s own documented, pre-existing
scope, not new), but worth the same treatment eventually if those kinds
need to materialize too.

Self-contained via `python3 generator/materialize.py`.

## `dynamosa.py` -- the DynaMOSA population loop (§6.4, built 2026-09-12)

The settled algorithm-of-record, finally built: one shared population per
case study, every compiled branch is one objective, DRD-gated dynamic
objective activation, real NSGA-II non-dominated sorting + crowding
distance. Reuses every operator already built this session
(`mutate`/`crossover`/`repair_candidate`/`build_seed_candidate`/
`branch_fitness`) rather than reimplementing anything -- this module is
purely the population/selection/activation scaffolding around them.

**DRD-gated activation reuses data already on the compiled record, not
a new DRD walk**: each compiled record already carries its own
`grounded_upstream_branches` (compile_constraints.py's own resolved list
of `"decision::rule_id"` branches its condition depends on). An objective
is active once every branch it names has been *covered* (fitness 0.0) in
the run's own archive -- which only ever grows, never regresses, exactly
DynaMOSA's own archiving discipline (a target's best answer, once found,
is never lost even if the current population moves past it).

**Focal-per-objective (2026-09-12, replacing the module's original "first
row per table" scope decision)**: real DynaMOSA evolves one shared
row-set where *different* rows serve as the focal context for
*different* objectives at once. The first version of this module took a
smaller scope instead -- every objective's focal row for a table was
always that table's *first* row in the shared candidate -- which stayed
implementable, but a real, measured diagnostic on the full FLEX2 case
study found this was the *dominant* cause of low coverage: 58 of
83 uncovered branches (~70%) failed outright with a missing-column
error, because different objectives needing different columns/values on
the very same physical row overwrote each other. This module now gives
every objective its OWN dedicated row per table, created lazily the
first time it's actually picked for mutation, and looked up read-only
(never created) during fitness evaluation -- an "individual" is
therefore `(candidate, focal_maps)`, `focal_maps: {record_id: {table:
row}}`, not a bare `Candidate`. Not every table a record's resolution
mentions gets a dedicated row -- only the ones a leaf kind actually
reads *through* focal at all (`derived_aggregate`/`exists` scan the
whole shared candidate directly and never consult focal; handing them a
fresh, empty dedicated row would be actively wrong, silently counting as
a match for a filter with no real conjuncts). `crossover.py` was
extended (not reimplemented) with `focal_maps1`/`focal_maps2` so a table
swap during crossover carries every objective's own dedicated row for
it, not just one.

**Verified honestly, and the refinement's own real benefit -- and one
real regression along the way -- were measured, not just described**: a
4-objective test (2 root branches, 2 chained on them) still reaches 3/4
covered in 25 generations, archive coverage still confirmed monotonic
and DRD-gating still confirmed directly (unchanged from before this
refinement -- a genuine regression check, not just a forward-looking
test).

**A real regression found and fixed testing this at full scale**: giving
every objective its own dedicated seed rows meant many different
objectives independently seeding, say, their own `COURSE` row with the
identical small placeholder `COURSE_ID` -- a real UNIQUE-constraint
violation `validate_with_sqlite` caught immediately (60 errors on the
first full-scale run), something the old "one row per table, total"
design could never produce. Fixed by shifting every objective's own
PK/FK column values by a per-objective offset before merging into the
shared base (never touching a genuine business-value column like a
lecture count or GPA), and applying the identical offset to that
objective's own seeded `scenario` values too -- one seeding path builds
a row's key column directly from a matching `scenario` placeholder
(`ROLL_NO = <student>`), and offsetting only one side would silently
break that equality the moment the filter predicate re-reads `scenario`
at match time.

**Measured before/after, full FLEX2 scale** (103 branches, population
30, 40 generations, seed 0):

| | archive coverage | final-dataset coverage | elapsed |
|---|---|---|---|
| Before (first row per table) | 20/103 (19.4%) | 6/103 (5.8%) | 7.7s |
| After (focal-per-objective) | 50/103 (48.5%) | 15/103 (14.6%) | 26.9s |

Both numbers roughly 2.5x -- confirming the coverage diagnostic's own
root cause directly. The archive/final gap grew in absolute terms (14 ->
35) even as both numbers improved a lot relatively -- expected, not a
new problem: with 2.5x more objectives reachable at all, not all of them
land on the same one final individual simultaneously; closing that gap
further is a distinct refinement, not attempted here. Runtime cost
roughly 3.5x -- the real, measured cost of every objective now carrying
its own rows -- reported honestly rather than left unmeasured.
`validate_with_sqlite` still reports `ok=True, 0 errors` at this scale
after the offset fix above.

**A real crash found and fixed while scaling up** (unchanged from the
original version of this module, still guarded against under the new
representation): a chosen leaf's own genome computation, or
`best_value_for`'s own first `branch_fitness` call, can fail against a
freshly-created, still-empty dedicated row (some *other* leaf of the
same record can reference a genuinely unresolvable fact even though the
record itself compiles fine). `_mutate_objective`'s own try/except
around both calls turns this into an honest "not evaluable yet," never a
crash.

Self-contained via `python3 generator/dynamosa.py`.

## `generate_dataset.py` -- running it for real, at full case-study scale (2026-09-12)

Ties `dynamosa.py` (search) and `materialize.py` (output) together into
the actual "generate a real dataset for one case study" entry point --
the first module that runs the whole pipeline end to end and produces
real files, not just a self-test.

**Two honest coverage numbers, not one**, because they answer genuinely
different questions: **archive coverage** -- how many objectives reached
fitness 0.0 *at some point* during the run, possibly on different
individuals at different generations (DynaMOSA's own archive discipline,
a progress metric); **final-dataset coverage** -- how many objectives
are *simultaneously* satisfied by the ONE real candidate this module
actually materializes (the honest, deliverable number -- a dataset is
one concrete row-set, not a scrapbook of per-objective snapshots taken
at different moments).

**Real result, full FLEX2 scale (103 compiled branches, population 30,
40 generations)**: archive coverage **50/103 (48.5%)**, final-dataset
coverage **15/103 (14.6%)**, ~27s, and the materialized dataset
validates **cleanly against real SQLite DDL with FK enforcement on --
`ok=True, 0 errors`**. (Earlier, before `dynamosa.py`'s own
focal-per-objective refinement replaced its original "first row per
table" scope decision: 20/103 archive, 6/103 final, 7.7s -- see
`dynamosa.py`'s own README section above for the full before/after and
the coverage diagnostic that motivated the refinement.)

**This is a historical snapshot, not the current state** -- FLEX2's own
compiled corpus size has changed twice since (391 records after the
DRD-grounding fix surfaced previously-hidden objectives, then 151 after
the grounding-consistency fix removed ~49% that were mathematically
unsatisfiable by construction). `dynamosa.py`'s own README section above
has the full, current before/after chain and the real, latest archive
coverage number (80/151, 53.0%).

**Two more real, previously-latent bugs found only by running this at
full scale** -- both existed since `build_seed_candidate`'s own seeding
logic was written, and neither was ever caught before because nothing
had checked these specific seed rows against the *real* schema until
`validate_with_sqlite` did:

1. **`raw_sql_boolean`'s own seeding stamped ALL of a multi-table SQL
   template's columns onto EVERY table it named.** `isElectiveTaughtByVisitingScholarUnavailableOtherwise`'s
   template references `COURSE_OFFER`/`EMPLOYEE`/`D_EMP_TYPE` via
   aliases (`CO`/`E`/`DT`); the old code pulled every `alias.column`
   mention out of the *whole* template into one flat set and gave that
   *same* set to every one of `node['tables']` -- so `COURSE_OFFER`'s
   seed row ended up carrying `EMPLOYEE`'s and `D_EMP_TYPE`'s own
   columns too (`TITLE`, `EMP_TYPE_ID`), columns that table doesn't
   have. Fixed by filtering each table's own seeded columns against that
   table's real declared schema columns.
2. **A genuine cross-table join conjunct
   (`PROGRAM_COURSE.COURSE_ID = COURSE.COURSE_ID`) was mistaken for a
   literal-string value comparison.** `_mechanical_filter_predicate` (and
   its construction mirror, `_row_from_filter_conjuncts`) matched the
   bare `TABLE.COLUMN` on the right-hand side as if it were a literal
   value to equal -- meaning `degreeTotalCredits`' own filter demanded
   `COURSE_ID == 'COURSE.COURSE_ID'` (the string), which no real
   integer `COURSE_ID` could ever satisfy, silently zeroing the
   aggregate to 0 every time rather than honestly reporting the join as
   unparseable. Fixed by recognizing a bare `TABLE.COLUMN` right-hand
   side as a join conjunct to skip (the same honest "can't mechanically
   apply this" convention already used for prose filters), and by
   implementing a real join in `derive_value`'s own aggregate branch for
   when `value_column` names a *different* table than the aggregate's
   own `FROM` table (via the same `"<TABLE>_ID"` FK-naming convention
   `join_lookup` already documents as this program's real, surveyed
   pattern) -- confirmed directly: `degreeTotalCredits` now correctly
   sums to `30` (3 courses × 10 credit hours each) via a real join,
   instead of silently returning `0`. Bounded, not guessed at: exactly 4
   rule-row variants in the whole corpus use this dotted-`value_column`
   shape, all now fixed.

Both fixes re-verified against the full regression suite (compile/
candidate/fitness/mutation/crossover/search/materialize/dynamosa) with
no change in outcome anywhere else, then the full FLEX2 run was
re-executed: same 20/103 and 6/103 coverage numbers (these bugs were
schema-*validity* bugs, not DMN branch-fitness bugs, so coverage was
never wrong -- only the materialized data's own real-world validity
was), now with `validate_with_sqlite` reporting `ok=True, 0 errors`
where it previously found 9 real, concrete violations.

Self-contained via `python3 generator/generate_dataset.py --case-study FLEX2 --population-size 30 --generations 40`.

## `compile_constraints.py` -- fixing a real DRD-grounding gap, and a real id-collision bug found along the way (2026-09-12)

Asked how to push coverage past the ~48% `dynamosa.py`'s focal-per-objective refinement reached, investigated for real rather than guessing. Categorized every uncovered FLEX2 objective by its actual archived state: 16 never-active (DRD-blocked), 13 stuck at literal `inf`, 24 with a real finite residual.

**Root-caused the 13 stuck-at-`inf`**: 9 reference a genuinely unclassified `derived` fact (no structure captured at compile time at all -- the known ~7% "Compound/Unclassified Derivation" category, needs real DMN-source parsing, out of scope here). The other 4 (`Course Load Limit::Rule_4` and three siblings) all fail on `newWarningCount`, kind `chained_decision_output`. Traced further: each has an OWN condition with *no* chained dependency at all (`Rule_4`'s is just `semesterType = 'Summer'`) -- it only inherits the unresolvable fact from evaluating its `UNIQUE`-hit-policy siblings' (`Rule_1`/`2`/`3`) own conditions as ITS suppression context. Those siblings' OWN conditions directly reference the chained fact and already get properly expanded into `::via::Academic Warning Status::Rule_N` variants; the suppression-context code, by explicit prior design, recorded an earlier row's own unresolved variable "as-is" instead, never expanding it the same way. `Course Load Limit::Rule_4` also turned out to be the single biggest DRD-gating blocker in the whole corpus (blocking 6 downstream objectives from ever activating) -- fixing this one gap was the highest-leverage lever available.

**The fix**: moved earlier-row (FIRST/UNIQUE suppression) variable resolution to run BEFORE the chained-expansion decision (previously per-variant, well after that decision was made), and folded any `chained_decision_output` issue found there into the exact same `enumerate_upstream_groundings` expansion pipeline the record's own condition's chained variables already use. A genuinely unresolved/`schema_gap` earlier-row variable is untouched -- still recorded honestly as-is, still never newly blocks the record.

**A second, real bug found immediately upon recompiling**: FLEX2 exploded from 103 to 391 records -- far more than the 4 targeted. Investigated rather than assumed a runaway bug: the real cause was a separate, pre-existing bug the fix simply amplified into visibility. `enumerate_upstream_groundings`'s own per-option label only ever names the IMMEDIATE upstream rule, never a deeper chain beneath it -- so two genuinely different grounding combos (differing only in which FURTHER-upstream rule grounds one of the immediate rule's own chained dependencies) produced the identical label, and `compile_case_study`'s own `record_id` (built from that label) silently collided. This turned out to BE the previously-flagged "duplicate record" finding, now understood correctly: those 6 "duplicate" copies were never padding -- confirmed directly (6 distinct conditions, 6 distinct `variable_resolution`s, one colliding id) -- they were 6 genuinely different, valid records silently overwriting each other under one shared id everywhere a consumer keys off `record_id` (`dynamosa.py`'s own archive dict, most consequentially). Fixed by having `enumerate_upstream_groundings` return the FULL grounding chain as a `provenance` list, and using it -- not just the immediate rule's label -- to build both `record_id` and `grounded_upstream_branches`. Confirmed: all 531 newly-compiled records now have unique ids (0 collisions). `grounded_upstream_branches` is also deeper/more correct as a side effect: a downstream objective's DRD-gating now genuinely requires every rule in its full dependency chain to be covered, not just the immediate one.

**Verified no regression**: `blocked` count unchanged (18, identical reasons/kinds) across all 4 case studies before and after. Per case study: FLEX2 103->391, OpenMRS 71->71 (unaffected), Spree 27->27 (unaffected), jBilling 41->42 (+1, a smaller instance of the same earlier-row pattern). `candidate.py`'s own full-corpus sweep improved as a direct consequence: 220/242 (90.9%) -> 504/531 (94.9%). Three self-tests broke from records this fix legitimately removed (`Course Load Limit::Rule_4`'s bare/ungrounded entry no longer exists) -- `mutation.py`/`search.py` updated to match by prefix instead of an exact id that no longer exists.

`compiled_constraints.json`/`compile_report.json` regenerated and committed as the new source of truth. Self-contained via `python3 generator/compile_constraints.py`.

**The real, honest coverage number on the corrected corpus**: re-ran `dynamosa.py` at the same budget as `generate_dataset.py`'s own headline number (population 30, generations 40) against FLEX2's now-genuine 391 unique objectives (previously only 83 were even visible -- the rest hidden behind the id-collision bug just fixed). Result: **43/391 (11.0%) in 397s** -- a real absolute gain (40 -> 43 covered) but a much lower percentage, since the honest denominator just grew ~4.7x. Not a regression -- the true problem size was always this large, just invisible.

**Scaling the search budget up does not fix this at the new scale, tested directly**: population 35/generations 40 reached only 41/391 (10.5%) in 479s -- *worse* despite more compute -- and its own coverage history shows a hard plateau after generation ~19 (`..., 39, 39, 39, ..., 41, 41, 41, ...`, 20+ generations producing nothing further). Two larger configurations both had to be killed after 580-590s without even finishing -- per-generation cost has grown much faster than the objective count itself, almost certainly NSGA-II's own O(active²) sorting compounding with the "one random active objective mutated per child per generation" policy now spreading the same one-pick-per-child attention across a much bigger active set.

**Two follow-up fixes built and measured (2026-09-12, see `dynamosa.py`'s own module docstring for the mechanics)**:

1. **Multi-pick mutation per generation** -- each child now mutates `k` DISTINCT active objectives per generation (`_mutations_per_child`, auto-scaled from the current active-set size) instead of exactly one. Measured: **48/391 (12.3%) in 420s** at the same budget -- a real but modest gain.
2. **A targeted, non-hardcoded fix for composite-leaf records** -- asked directly what kind of rules solve vs get stuck: simple, 1-2 leaf records (a plain column comparison, a category lookup) solve easily; the overwhelming majority of what's stuck shares one shape -- 5 independent leaf kinds (`derived_aggregate`, `derived_case`, `derived_join_count`, `literal_via_upstream_branch`, `schema_column`) that must ALL align at once. Root cause: `_mutate_objective` picks one random leaf per call, so a 5-leaf record gets the same "one attempt per pick" as a 1-leaf record. Fixed generically via `_local_burst_size(record)` = `len(_leaf_variables(record))` (capped at 8) -- computed purely from the record's own leaf count, never its name -- giving each pick that many sequential mutation attempts on the same record instead of one; a single-leaf record's own burst is still exactly 1. Measured: **80/391 (20.5%) in 645s** at the time -- nearly double fix #1's own result. `coverage_history` showed steady growth through generation ~25, then a new plateau.
3. **A local-optimum escape hatch (kick mutation)** -- extending generations 40->70 at the same population produced ZERO further improvement (flat at 80 for 45 generations), disproving "just needs more time." Verified directly via a single-record `hillclimb()`: one stuck record hard-stopped at a real local optimum after only 3 accepted moves out of a 300-iteration budget -- coordinate descent's own textbook failure (several leaves need to move TOGETHER, a strictly-improving single-leaf search can never discover that). Built `_kick_value_for`: with probability 0.15, a picked leaf gets an UNCONDITIONAL random jump instead of the greedy best-value pick, applied uniformly to every record. Measured honestly: at the same budget, still exactly 80/391 -- no improvement at this specific ceiling, only a different convergence path. A real, reported negative result, not spun as a win.
4. **The actual root cause: a grounding-consistency bug making ~49% of the corpus mathematically unsatisfiable** -- traced one stuck record's own compiled condition by hand after the kick fix failed to move it: it required `priorWarningCount` to equal BOTH 0 and 1 simultaneously under one AND. Measured: **192 of FLEX2's 391 compiled records (49%) had this exact shape.** Root cause: the same upstream decision (`Academic Warning Status`) was needed twice in one record -- once directly, once nested inside a different chained dependency -- and the old grounding code chose a rule for each occurrence completely independently. Fixed by replacing `enumerate_upstream_groundings` with a commitment-respecting backtracking search (`_grounding_options`/`_enumerate_needs`): a single shared `commitment` dict is threaded through every grounding need of one record, forcing every reference to the same upstream decision to agree on one rule. Verified: 0 of the resulting 151 FLEX2 records are self-contradictory (was 192/391), all still have unique ids, `blocked` count unchanged (18) across all 4 case studies. **Measured: 80/151 (53.0%) in 84.5s** -- the same absolute archive-covered count as before, but against the correct denominator, and 12x faster (no more effort wasted on unsolvable records). At generations=100, still exactly 80/151 -- a smaller, honestly-characterized remaining plateau: of the 71 uncovered, 0 are DRD-blocked, 19 are the already-known compile-time gap (unclassified derived facts), and 52 are real, active, still-searchable objectives.
5. **Worked through the remaining 52 to completion -- 51 turn out infeasible too, 1 was a real, fixable bug.** Traced the highest-residual example by hand: its own condition needs `newWarningCount = 0`, but this specific grounding fixes it to `1` -- infeasible the same way as #4, just "own condition conflicts with its own grounding" instead of "two groundings conflict." Built a general three-valued (True/False/Unknown) constant-folding evaluator to measure the blast radius: walks a condition tree, short-circuits AND/OR/NOT wherever every variable involved is already a fixed grounding literal, leaves anything touching a real leaf as Unknown. **49 records' own condition, plus 4 more via an earlier row that must be suppressed but is permanently forced true** -- **53 of 151 (35.1%) provably infeasible**, zero overlap with the covered set (checked, not assumed). Cross-checked against a fresh archive run: **all 51** finite-residual records are explained by this detector -- zero unexplained. The one exception (`Credit Transfer Exemption::Rule_3`) was a real, general bug in `enumerable_domain`/`candidate_values` (mutation.py): an earlier row's own equality fact was walked with the SAME polarity as the record's own condition, when it needs the OPPOSITE (an earlier row's own fact must be avoided, not hit, since FIRST-hit-policy suppression needs it false) -- so the search kept re-offering the one value that could never work, with no escape value ever computed. Fixed by passing `negated=True` for earlier-row conditions; verified the record now converges in one step, full regression suite passes, `candidate.py`'s own sweep unchanged. Re-ran at scale: **81/151 (53.6%)**, +1 over before. **The corpus is now completely, exhaustively characterized, zero unexplained records**: 81 covered + 53 provably infeasible + 17 compile-gap-blocked = 151 exactly. Excluding the infeasible and compile-gap records entirely: **81 of 81 genuinely-searchable-and-resolvable objectives covered -- 100%.**

## The aggregate row-sharing gap (2026-09-13) -- a real, necessary fix that honestly did NOT raise final-dataset coverage

Asked directly whether a real, schema-and-DMN-satisfying `.sql` file had actually been delivered -- it hadn't. Running `generate_dataset.py` for real (population=30, generations=40) produced a genuine, `validate_with_sqlite`-clean SQL file, but revealed archive coverage (81/151) and final-dataset (simultaneous-in-one-candidate) coverage (20/151) were sharply, suspiciously different -- identical at seed=0 and seed=1.

**Root cause**: `derived_aggregate`/`exists`/`derived_join_count` leaves (candidate.py's `derive_value`) scan the WHOLE shared candidate table with zero per-objective isolation, unlike `schema_column`-style leaves which already read/write a dedicated per-objective `focal` row (the earlier focal-per-objective fix above). Different DynaMOSA objectives sharing an aggregate-relevant table could count/corrupt each other's rows the moment both mutated the same shared population.

**Fix**: row ownership tagging, not another dedicated-row scheme (an aggregate genuinely needs to scan a SET of rows, just its own). A reserved `_OWNER_KEY` bookkeeping key plus `_owned_rows(candidate, table, owner_id)` (candidate.py) -- a row tagged for `owner_id`, or untagged (genuinely shared reference/FK-repair data), is visible; a row tagged for a DIFFERENT objective is not. `owner_id=None` disables all filtering, so every single-objective caller (`mutate()`/`hillclimb()`/`solve_branch()`, every self-test) is unaffected by default. Threaded through `derive_value`/`derive_genome`, `_apply_row_count_mutation`/`apply_mutation` (which also fixed a related bug found along the way: `exists`-kind decrease used to wipe the WHOLE table regardless of which objective wanted the decrease), and `dynamosa.py` (seed rows, lazily-created focal rows, and every mutation/evaluation call now pass `owner_id=record['record_id']`). `materialize.py` strips `_OWNER_KEY` from every emitted row (`_real_columns`) before SQL/CSV output -- confirmed by grep: zero `__owner__` leakage in the generated `.sql`/`.csv` files.

**Verified no regression**: full suite green (`candidate.py` sweep unchanged 264/291; `mutation.py`/`crossover.py`/`search.py`/`materialize.py`/`dynamosa.py` self-tests all pass; freshly regenerated `.sql` still `validate_with_sqlite: ok=True, 0 errors`).

**The honest, measured result: final-dataset coverage went DOWN, not up** -- 17/151 (seed=0) and 19/151 (seed=1), vs the previous constant 20/151, with archive coverage unchanged at 81/151 both before and after. Diagnosed directly (monkeypatched `_owned_rows` to reproduce the old, unisolated behavior on the identical rng seed, diffed exactly which records the final individual covered either way): the differences scatter across mostly unrelated `schema_column` records, consistent with ordinary stochastic drift from an early divergence in aggregate-mutation outcomes, not a systematic loss in aggregate-kind objectives specifically. **The old "20" was itself an artifact**: with no isolation, an `exists`-kind check reads TRUE the instant ANY objective's row has EVER landed in that table -- true for nearly every shared table well before generation 40, regardless of rng seed, which is exactly why it was identical across seeds. The new numbers are honestly seed-sensitive, as a real stochastic search should be.

**The deeper problem this fix correctly does NOT solve**: `generate_dataset.py` picks "the individual in the final population that simultaneously covers the most objectives" -- but DynaMOSA/NSGA-II is designed to spread a population across Pareto-front *specialists*, not converge on one *generalist*, which is precisely why the archive (crediting an objective the moment ANY individual, ANY generation, solves it) exists as a separate structure. Picking one final-population individual was always going to cap out well below archive coverage for a reason unrelated to row-sharing; the bug just papered over part of that gap with an illegitimate number. A real fix would need a different final-dataset construction strategy (e.g. merging archived per-objective bests into one consistent candidate, resolving conflicts explicitly) -- a distinct, larger piece of work, not attempted here. See `docs/generationalgorithmdesign.md` §13.42 for the full trace.

## Merge-the-archive final-dataset construction (2026-09-13) -- final-dataset coverage 17-21/151 → 81/151, matching archive coverage exactly

Built the follow-up the previous section named: instead of picking one individual out of the final population (capped at 17-21/151 for a structural reason -- DynaMOSA/NSGA-II spreads a population across Pareto-front specialists, never converges it onto one generalist), `merge_archive_candidate` (dynamosa.py) builds the final candidate by merging every covered objective's own best-ever rows from the archive into one shared candidate: each objective's own dedicated focal row (by identity) plus every other row anywhere in its own archived individual tagged with its `_OWNER_KEY` (the aggregate/exists/join-count row sets from the fix above), followed by ONE `repair_candidate` pass on the fully assembled whole. `generate_dataset.py` now builds and RE-VERIFIES both strategies for real (never trusting the archive's own expected count without re-`evaluate_objective`-ing every objective against the actual merged, repaired result) and materializes whichever verifies higher.

**Two real bugs found and fixed getting there, neither assumed away:**

1. **A pre-existing, previously-unknown bug in `generate_dataset.py` itself** (unrelated to the merge): it rebuilt its own FRESH, un-offset `scenario_cache` for re-evaluation instead of reusing the one `_seed_shared_population` actually built and offset for the real run -- silently understating coverage for scenario-dependent leaves in EVERY benchmark this module had ever run (confirmed: even a record's own already-fitness-0.0 archived individual raised a spurious "0/0 division" error when re-evaluated this way). Fixed by having `run_dynamosa` return its own internal `scenario_cache` as a 4th value; every caller updated.
2. **A real bug in the merge itself**: a `derived_join_count` record legitimately owns TWO different rows in the same table -- its own dedicated focal/context row, and a separate, merely owner-tagged row (e.g. the prerequisite's own passing-grade registration). The first version funneled both through one list and reassigned `merged_focal_maps[record_id][table]` for ANY owned row on a table the record also has a focal row for, so the second row silently overwrote the true context row the moment both landed in the same table -- corrupting the join-count lookup (read back `0` instead of the correct `1`). Fixed by keeping focal-row assignment (by identity, from `focal_maps` alone) strictly separate from the owner-tag merge scan.

**Final, measured result**: merged-archive coverage is **81/151 (53.6%), VERIFIED, zero regressions** -- exactly matching archive coverage, at both seed=0 and seed=1. A real ~4x improvement over the final-population strategy's own 17-21/151 across the same two seeds, delivered in one real, `validate_with_sqlite`-clean, schema-legal dataset. See `docs/generationalgorithmdesign.md` §13.43 for the full trace.

## Known real-world constants (2026-09-13) -- a general mechanism for domain-realistic values the search has no reason to want on its own

Asked why the generated dataset only had 5 `STUDENT_ATTENDANCE` rows for the Attendance Eligibility rules. Traced directly: only 2 of the 151 compiled records touch that table at all, and `lecturesHeldForOffering` (a `derived_aggregate` count of `LECTURE` rows) is a completely free leaf -- the search always converges to the cheapest value that proves the branch (as few rows as the ≥80%/<80% threshold needs), never a value chosen for realism. Not a bug -- the search was only ever asked to prove DMN/schema correctness -- but a real gap once pointed out: a real course offering holds around 30 lectures, a fact nothing in the DMN, schema, or generator encoded anywhere.

Built a general, config-driven fix rather than a one-off hack for this rule: `known_constants.json` (`{case_study: {var_name: fixed_value}}`, keyed by the leaf's own free-variable name, e.g. `{"FLEX2": {"lecturesHeldForOffering": 30}}`). `known_constant(case_study, var_name)` (candidate.py) is the single shared lookup, consulted in three places: `best_value_for` (mutation.py) jumps straight to the pinned value instead of searching for the cheapest one that merely proves the branch; `build_seed_candidate` seeds a pinned `derived_aggregate` leaf at that count from generation 0 instead of the hardcoded 3; and DynaMOSA's own kick-mutation escape hatch (§ above) excludes pinned variables so it never randomly perturbs one away from its correct real-world value. One entry pins uniformly to every rule that resolves to that same variable name -- no per-decision special-casing anywhere.

**Verified**: full regression suite green, full FLEX2 benchmark still gives **81/151 merged-archive coverage, VERIFIED, zero regressions**. Inspected the real generated SQL directly: both course offerings now carry exactly 30 `LECTURE` rows (up from 3), with `STUDENT_ATTENDANCE` correctly showing 25/30 ≈ 83.3% attended for the eligible student and 3/30 = 10% for the debarred one. See `docs/generationalgorithmdesign.md` §13.44 for the full trace.

## Running the pipeline against Spree for the first time (2026-09-13) -- three real bugs, none FLEX2-shaped

Ran `generate_dataset.py` against Spree for the first time (previously only FLEX2 had gone through the full DynaMOSA population loop and real SQLite validation; the other case studies had only ever been exercised by `compile_constraints.py`/`candidate.py`'s own corpus-sweep self-tests). Found and fixed three real, general bugs:

1. **Uncaught crash comparing `None` with an ordering operator** (`fitness.py`) -- `_comparison_distance_true` had a defined non-numeric fallback for `=`/`!=` but none for `<`/`<=`/`>`/`>=`, crashing outright (`TypeError`) the moment a nullable column (e.g. `expires_at`, correctly `None` while unset) reached an ordering comparison. Fixed by raising this project's own `FitnessEvaluationError` instead -- already handled safely everywhere in the pipeline, just never reached before.
2. **Widespread schema-JSON artifacts `materialize.py` had never been forced to handle** -- measured directly, not assumed from a couple of examples: 242 columns in Spree's own schema JSON carry a malformed type string like `"bigint(ref)"`, and 196 of Spree's own tables declare a PK column (`id`) absent from their own column list (Rails' `schema.rb` never lists its implicit auto-increment `id` explicitly; jBilling has 3 tables of the same shape). `create_table_ddl`/`_sqlite_type` fixed generally: a parenthetical type suffix is kept only when it's a real length/precision modifier, stripped otherwise; a missing PK column is synthesized as a plain `INTEGER` column before the `PRIMARY KEY (...)` clause.
3. **A hallucinated migration in the Spree ground-truth mapping** -- `spree_dmn/provenance/variable_to_schema_mapping.csv` mapped several `spree_orders` facts to a `customer_id` column, citing a migration file that does not exist anywhere in this repo; the real `schemas/spree_schema.rb` still has `user_id`. Confirmed directly before touching it (a curated ground-truth file, not generator code) and corrected with the user's confirmation: 6 CSV rows fixed, `compiled_constraints.json`/`compile_report.json` regenerated (291 compiled records unchanged, 18 blocked unchanged).

**Verified, measured result**: Spree -- **20/27 (74.1%) merged-archive coverage, VERIFIED, zero regressions**, `validate_with_sqlite: ok=True, 0 errors`. All three fixes are general, not Spree-specific, and already benefit jBilling's own affected tables too. See `docs/generationalgorithmdesign.md` §13.45 for the full trace.

## Fixing the not_persisted scenario-mutation bug (2026-09-13) -- two stacked defects

Diagnosed while investigating Spree's own remaining 7 uncovered objectives: two rules needed `purchaseQuantity` (a `not_persisted` bind-parameter) to move away from its seeded value, and neither ever did across a full 40-generation run. Two real, stacked bugs, both required to fix it:

1. **Scenario mutations were computed, then silently discarded.** Every individual shared the exact same scenario dict per objective; `_mutate_objective` mutated a throwaway copy and never persisted it (already flagged as a known limitation in the function's own docstring). Fixed by giving scenario the same per-individual treatment `focal_maps` already has: an individual is now a `(candidate, focal_maps, scenario_maps)` triple, evolving each objective's own scenario independently, deep-copied jointly on every mutation exactly like focal rows already are. `run_dynamosa` no longer returns a separate `scenario_cache` -- it's redundant now that every individual carries its own.
2. **`candidate_values()` had no case at all for a `not_persisted` numeric leaf compared via an ordering operator** (only `=`/`!=`/`in` had a domain; `schema_column`/`derived_aggregate`/`derived_join_count` were the only kind-specific numeric branches) -- found only because re-testing after fix #1 alone showed ZERO change in Spree's coverage. `best_value_for` had nothing to even propose as a replacement value, so fix #1's persistence had nothing to persist. Fixed by adding a `not_persisted`-numeric branch (identical treatment to `schema_column`'s own) plus AVM step-doubling eligibility, since a seeded value can start millions away from its real target.

**Verified, measured result**: full regression suite green throughout, FLEX2 unaffected (still 81/151, verified). Spree: **20/27 (74.1%) → 22/27 (81.5%) merged-archive coverage, VERIFIED, zero regressions** -- confirmed directly which two objectives newly solve and why (`purchaseQuantity=65` correctly inside its required window; `purchaseQuantity=-12554430` correctly below both suppression thresholds). See `docs/generationalgorithmdesign.md` §13.46 for the full trace.

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
