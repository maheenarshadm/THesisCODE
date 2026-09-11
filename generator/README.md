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

## Result, current run

| Case study | Compiled | Blocked | Rate |
|---|---|---|---|
| FLEX2 | 46 | 9 | 83.6% |
| OpenMRS | 71 | 0 | 100.0% |
| Spree | 27 | 5 | 84.4% |
| jBilling | 39 | 14 | 73.6% |
| **Total** | **183** | **28** | **86.7%** |

**Blocking reasons, by kind** (a branch can have more than one blocking
variable): `chained_decision_output` (9) — a decision-table-to-decision-table
DRD edge, the one deliberate, documented scope boundary below;
`unresolved` (8) — mostly free variables of an inlined literal-expression
formula whose own ground-truth row couldn't be resolved to a column,
recipe, or gap marker; `schema_gap` (6) — the branch's condition itself
depends on a variable ground truth already flags as having no schema
representation at all (e.g. Spree's `preferences` serialized-blob
findings); `code_external` (12, new — see "Resolving derived/aggregate
nodes" below) — the variable is genuinely computed by application code
with no schema field ever recorded for it at all (a Java constant, a
UI-only transient value, a runtime-only calculation), not merely a
column this compiler failed to find.

**Compiled-but-not-generator-ready dropped sharply after the
derived/aggregate resolution pass below**: of the 211 total branches,
**158 (74.9%) are now fully mechanical** — every variable a real schema
column, ready for a generator today — up from 73 (34.6%) before that
pass. Only 25 remain in the "compiled, but still needs a human/more
automation" tier (12 `exists` with an unstructured filter, 8 generic
`derived` notes still unclassifiable by pattern, 6 `derived_aggregate`
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

## Known scope limits (stated here, not discovered by a reader)

- **`chained_decision_output` is a deliberate, documented non-goal, not a
  bug**: a decision table's output depends on which of its own rules
  fires, which isn't a single closed-form expression to inline the way a
  literal-expression decision's formula is — inlining it would mean
  either picking one arbitrary upstream branch (silently wrong) or
  exploding into one compiled record per upstream-branch combination
  (a combinatorial blow-up outside this script's scope). §6.1's own
  worked example never attempts this case either. A generator consuming
  these records needs to run the upstream decision's own branches first
  and treat this as a genuine dependency, not a variable to solve for
  directly.
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
