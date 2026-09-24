# Validation oracle — known issues tracker

A live reference, not a chronological log (that's `DESIGN.md` — every fix
below links back to it for the full story, root-cause investigation, and
verification evidence). This file answers one question at a glance: **is
this specific gap open or fixed, and if fixed, how?**

**How to use this file:** when something below gets fixed, move its entry
from "Open" to "Fixed," and say what the fix actually was (not just "fixed"
— the concrete change, so a reader doesn't have to dig through git log).
When a new gap is found, add it under "Open" in the right case-study
section, using the same shape: what's blocked, why, and what fixing it
would require.

Current status snapshot (non-COLLECT rules; COLLECT is tracked separately,
excluded from all coverage numbers per an explicit decision below):

| Case study | Verified rule coverage | Verified decision-table coverage |
|---|---|---|
| OpenMRS | 37/56 (66.1%) | 14/14 (100%) |
| FLEX2 | 21/55 (38.2%) | 2/10 |
| Spree | 9/26 (34.6%) | 4/8 |
| jBilling | 11/39 (28.2%) | 6/16 |

---

## Open issues

### Cross-case-study

- **COLLECT hit policy not implemented.** `rule_evaluator.select_rule`
  only handles FIRST/UNIQUE (the original specification's own scope).
  Affects OpenMRS (5 decisions: `Order Date Activated Consistency
  Violations`, `Death Date Consistency Violations`, `Program Enrollment
  Date Consistency Violations`, `Relationship Date Validity Violations`,
  `Encounter Datetime Validity Violations`) and Spree (1 decision:
  `Price Adjustment Tier Validity Violations`). **By explicit decision,
  these are excluded from all coverage numbers reported anywhere in this
  file** (not counted as covered or uncovered — just out of scope for
  now), rather than silently dragging the denominator down. Fixing this
  needs real new code: COLLECT returns every matching rule's output
  combined, a materially different coverage question than "which one
  rule wins."

### Spree

- **Blob-decoding — CLOSED for 4 of 5 facts via a new `serialized_field`
  mechanism; `promotionTargetGroupIds` deliberately left for later.**
  See "Fixed issues" below for the full mechanism. `amountMaxSet`/
  `operatorMin`/`amountMin`/`operatorMax`/`amountMax` now compile via a
  confirmed-real (not guessed) YAML read/write convention, closing all 4
  `Promotion Item Total Eligibility` rules at the compile level.
  `Promotion Customer Group Eligibility::rule_3`'s own
  `promotionTargetGroupIds` is a LIST-typed fact needing FEEL
  `intersection`/`count` over two lists — a materially different, larger
  piece of work than the scalar preferences closed here, not yet
  attempted.

- **4 fixture/row-finding gaps (14 rules, 4 decisions) — all the SAME
  underlying category, "compiles correctly but the row can't be found
  or doesn't exist in this materialized database yet."**
  `Promotion Customer Group Eligibility` (3 rules) and `Promotion Item
  Total Eligibility` (4 rules, newly joining this category once its own
  blob-decoding closed) both need to locate a specific
  `spree_promotion_rules`/`spree_order_promotions` row from the
  decision's subject (`spree_orders`) — a one-to-many backward join
  `subject_table_for_decision` correctly refuses to guess at.
  `Promotion Usage Limit Exceeded` (4 rules) needs `spree_discounts`;
  `Price List Volume Adjustment Tier Selection` (3 rules) needs
  `spree_line_items` — both real tables simply missing from
  `spree_merged.db`, since that fixture was built from an archive
  (`Spree__dynamosa_nsga2__budget1x__seed0.pkl`) that predates every
  ground-truth fix made this session. Confirmed directly: rebuilding
  the fixture from the SAME archive reproduces the identical missing
  tables (nothing to extract — the rows never existed, since these
  facts used to be `not_persisted`/`schema_gap`, never materialized to
  begin with). **Fix requires re-running the DynaMOSA search for Spree
  against the current `compiled_constraints.json`**, then rebuilding
  the fixture from the fresh archive — still pending an explicit
  go-ahead (this is real search/experiment-data work, not a quick
  fixture rebuild). Note these are genuinely TWO different remedies
  bundled under one category: the missing-table half (`Promotion Usage
  Limit Exceeded`/`Price List Volume Adjustment Tier Selection`) needs
  the search re-run; the row-finding half (`Promotion Customer Group
  Eligibility`/`Promotion Item Total Eligibility`) needs the
  one-to-many join question resolved (a disclosed override naming
  which single `spree_promotion_rules` row is "the" one for a given
  promotion/type, since a real promotion can have many rule rows) —
  re-running the search alone would NOT close this second half.

- **`One-Use-Per-User Promotion Eligibility::rule_2` — a real
  compile-time bug, not a data gap.** Ground truth says
  `priorPromotionUsageCount` should be `derived-aggregate` (a COUNT of
  `spree_discounts` rows joined through `spree_promotion_actions`/
  `spree_orders.user_id`). The COMPILED record instead shows
  `{'kind': 'schema_column', 'table': 'spree_orders', 'column':
  'user_id'}` — comparing a raw `user_id` against `0`, not a count at
  all. Root cause: the ground-truth note's free-text shape ("joined via
  A and B") matches none of `classify_derived`'s specific recognized
  patterns, so it falls through to the generic multi-pair fallback,
  which grabs the wrong column. It currently "works" by accident only
  because no real `user_id` is ever `0`. **Fixable at the objective
  level**: re-express this ground-truth row using the
  `derived_aggregate`/`filter_text` mechanism already built and proven
  this session (same shape as `adjustedCreditsCount`).

- **`Promotion Temporal Availability::rule_2` — infeasible by nature,
  not a data gap.** Compiled condition is `expiresAt > expiresAt`, a
  self-referential tautology, impossible for any value, ever. Confirmed
  in the raw DMN XML (`Promotion_Order_Level_Eligibility.dmn`): the
  rule's `expires_at` input-column cell reads `<inputEntry><text>&gt;
  expiresAt</text></inputEntry>` — compared against its own column.
  Given the decision's declared inputs (`evaluationTime`, `startsAt`,
  `expiresAtSet`, `expiresAt`) and the rule's own output (`"EXPIRED"`),
  it almost certainly meant `evaluationTime > expiresAt` ("now is past
  the expiry date"). Three-valued constant folding doesn't catch this
  (it folds grounded literal comparisons, not "same free variable
  compared to itself"). **Not fixable at the objective/data level at
  all** — no generated data can satisfy a self-contradiction. Needs the
  DMN source corrected (move the `> expiresAt` unary test to the
  `evaluationTime` column), the same kind of fix as the `<variable>`
  declaration fix already made for the threshold decisions.

- **`First-Order Promotion Eligibility::rule_3` — an ordinary,
  fixable-by-data FIRST-hit-policy gap.** Its condition is the bare
  catch-all (`true`), always shadowed by `rule_1`/`rule_2` across all 8
  real cases in the current database — none represents an identified
  customer who *also* has ≥1 other completed order. The objective
  itself is already correct (`branch_fitness` already requires "own
  condition true AND every earlier row false," confirmed this
  session). **Likely resolves on its own** once the Spree search is
  re-run against current ground truth with enough generations to
  construct that specific combination — same underlying action as the
  fixture-gap re-run above, no separate fix needed.

### FLEX2

- **5 genuine multi-table backward-join gaps**: `Admission Closure
  Eligibility`, `Course Registration Eligibility`, `Credit Transfer
  Exemption`, `Graduation Eligibility`, `Summer Semester Registration`.
  Each needs a table in its own FK closure that forward-reaches every
  table its inputs require, and none exists — same category already
  closed for Spree/jBilling elsewhere, not yet attempted for FLEX2.
- **`Attendance Eligibility For Final Exam`** — no table-backed input
  at all (every condition variable is `not_persisted`/upstream), same
  shape as Spree's `Price List Volume Adjustment Tier Selection` used
  to be before that was corrected to a real column. Worth checking
  whether the SAME kind of mis-mapping exists here before accepting it
  as a genuine non-database fact.
- **`Course Replacement Eligibility` — likely a quick win with
  already-built infrastructure.** Fails with `filter_text placeholder
  <program> binds to column 'prog_id', not present on the subject row`
  — structurally the *exact same shape* as Spree's `Promotion Customer
  Group Eligibility::promotion_id` gap that `filter_placeholder_sources.py`
  was built to solve. `prog_id` likely lives on `STUDENT_PROGRAM`,
  already confirmed reachable from this decision's subject
  (`COURSE_REGISTRATION`) via a real join path. **Probably fixable by
  just adding one entry** — `('FLEX2', 'program'): 'STUDENT_PROGRAM'`
  (name TBD, needs confirming the exact placeholder name and target
  column first) — no new mechanism needed, the join-aware placeholder
  resolver already exists.

### OpenMRS

- COLLECT hit policy — see cross-case-study section above (all 5 of
  OpenMRS's currently-uncovered decisions are COLLECT; excluding them
  brings OpenMRS's own decision-table coverage to 14/14, 100%).

*(Known, expected false-positive **findings** — `Preferred Identifier
Requirement::Rule_2`, `Numeric Precision Validity::Rule_1`, `Numeric
Absolute Range Validity::Rule_1`/`Rule_2`, `Birthdate Validity::Rule_1` —
are not "issues" in this file's sense: they're the validator correctly
catching the search claiming coverage it didn't actually achieve, which
is the whole point of this project. See `DESIGN.md` for each one's own
root-cause writeup.)*

### jBilling

- **6 decisions with no table-backed input at all**: `Is Ageing
  Required`, `Currency Exchange Rate Source`, `Order Date Range Valid`,
  `Payment Outcome Resolution`, `Payment Balance Assignment`, `Daily
  Pro-Rate Amount`. Not yet individually audited the way Spree's
  `purchaseQuantity` was — worth checking whether any of these are
  actually mis-mapped real columns (like `purchaseQuantity` turned out
  to be) rather than genuine non-database facts, before accepting them
  as-is.
- **2 decisions needing a `not_persisted` override**: `Order Period
  Already Invoiced` (`candidateDateProvided`), `Tax Calculation Needed`
  (`customContactFieldConfigured`). Same open question as above — needs
  checking whether these are genuinely scenario-only values (in which
  case a disclosed fixed override, same as `evaluationTime`, closes
  them immediately) or mis-mapped real columns.
- **`Ageing Step Config Validation`** — blocked by `isLastSelectedStep`,
  `code_external`: "computed as the highest array index with `inUse=true`
  across the submitted admin-screen steps array" — genuinely application
  code, never any database table, ever. Not fixable by data generation
  at all, a harder limit than the Spree blob (which is at least *in* a
  database column, just undecoded).
- **`Cancellation Fee Eligibility`** — 0 compiled rules (blocked at
  compile time entirely; invisible to per-objective coverage reporting
  since it produces no records at all). Not yet investigated at all —
  flagged during a decision-table-coverage cross-check, root cause
  unknown.

---

## Fixed issues

Each entry: what was broken, what the fix actually was, and a pointer
into `DESIGN.md` for the full investigation/verification trail. All
verified via the full regression suite (`test_spec_cases.py`,
`test_drd_chaining_synthetic.py`, the OpenMRS acceptance test in
`drd_executor.py`) plus a before/after diff of the full compiled record
set across all 4 case studies, confirming zero unintended adds/removes,
before being counted as fixed here.

- **FLEX2 fixture: every row's own primary key was null.**
  `generator/mutation.py`'s `_repair_row` only assigned a NOT-NULL
  column, and FLEX2's own extracted schema never flags any of its 121
  PK columns `null_false: true` (a schema-extraction artifact unique to
  FLEX2 — zero such gaps in the other 3 case studies). Fixed by also
  repairing a declared PK column regardless of its own `null_false`
  flag. → FLEX2 went from crashing entirely to 0/98 verified.

- **FLEX2: table names compared case-sensitively, manufacturing fake
  root-picking failures.** `variable_resolution` writes some tables
  lowercase (`course_registration`) while `fk_closure_tables` uses the
  schema's real upper-case (`COURSE_REGISTRATION`) for the same table.
  Fixed by canonicalizing every table name through
  `schema_utility.canonical_table_name` before any set operation in
  `subject_table.py`, and made `db_resolver._row_for_table`'s
  table-identity comparisons case-insensitive to match. → Combined with
  the PK fix above, FLEX2 reached 21/98 verified for the first time.

- **`exists`-kind resolution never consulted `filter_text` at all, in
  any prior version of the code.** Silently checked "does the subject's
  own row have a non-null value" regardless of what filter was actually
  declared — meaning jBilling's `Currency Exchange Rate Source`
  (`hasEntitySpecificExchange` vs. `hasSystemDefaultExchange`) had been
  structurally unable to differ, and any previously-reported numbers for
  it were silently wrong. Fixed: `exists` now runs a real correlated
  `SELECT EXISTS(SELECT 1 FROM t WHERE filter_text)` when `filter_text`
  is present.

- **3 underspecified-ground-truth decisions closed with disclosed
  `[ASSUMED]` rows**: Spree's `Promotion Usage Limit Exceeded`
  (`adjustedCreditsCount`, a de-dup COUNT over `spree_discounts`) and
  jBilling's `Ageing Step Advancement`/`Ageing Step Config Validation`
  (an `(entity_id, status_id)` correlation on `ageing_entity_step`).
  Each was a business rule ground truth described in prose but never
  encoded machine-actionably, on REAL, existing columns — not
  fabricated schema structure.

- **A self-inflicted CSV regression, caught before it shipped.** An
  unquoted comma inside a parenthesized column list silently shifted
  that row's own CSV columns, corrupting its `mapping_type` and
  dropping jBilling's compiled count 40→37 with no error. Caught by
  diffing the full compiled record-ID set against a pre-edit baseline,
  not the summary counts alone. Fixed by quoting the field correctly.

- **`First-Order Promotion Eligibility` closed via a new override
  mechanism.** Its dependency, the literal-expression decision `Prior
  Completed Order Count`, has a FEEL list-comprehension formula
  `feel_parser.py` can't parse (degrades to an unevaluable
  `opaque_formula` node without raising the exception the compiler
  already handles for unparseable formulas). Added
  `generator/literal_expression_overrides.py` (same precedent as
  `join_disambiguation.py`) so `resolve_and_substitute` can swap in a
  hand-translated, disclosed `{expression, free_variable_resolutions}`
  pair before attempting the real parse — reusing the existing
  `derived_aggregate`/`filter_text` machinery, no new runtime code.

- **Spree's `purchaseQuantity` ground-truth mapping was itself wrong.**
  Originally `not-persisted` ("a scenario parameter"), but "the
  quantity being purchased" is an ordinary, real, persisted fact:
  `spree_line_items.quantity`. Caught by a user challenge to an
  over-cautious initial assessment. Corrected to `direct` (a confident,
  non-`[ASSUMED]` fix, not a disclosed guess).

- **`Promotion Customer Group Eligibility::rule_2` closed; `rule_3`
  precisely re-diagnosed.** `promotionTargetGroupsConfigured` only
  needed to know a customer-group rule was *configured*, answerable
  from `spree_promotion_rules.type` (a real Rails STI discriminator
  column) — not the same undecoded blob `rule_3` actually needs.
  Getting it to run surfaced two more real bugs, both fixed:
  1. `db_resolver._substitute_self_and_colon`'s own `:column_name`
     regex misread `::` inside a Ruby class-name string literal as a
     placeholder — fixed with a negative-lookaround regex.
  2. The real link to "the promotion" (`spree_order_promotions`) was
     missing from the extracted schema's own `fk_columns` entirely (a
     pre-existing Spree extraction gap). Added
     `validation_oracle/supplementary_fk_edges.py` (same precedent as
     `join_disambiguation.py`, for a MISSING edge) so
     `schema_utility.fk_edges` knows about it.

- **Built a general, join-aware `filter_text` placeholder resolver.**
  `_resolve_placeholders` previously only ever looked at the subject
  row's own columns. Added `validation_oracle/filter_placeholder_sources.py`
  (`{(case_study, placeholder_name): table_name}`) plus a small fallback
  in `_resolve_placeholders` that fetches the value off the
  already-joined row via the existing `_row_for_table` hop-walker when
  the placeholder isn't on the subject row — reusing all existing
  join-path/ambiguity-refusal machinery, no new join-finding logic.
  Locked in with a new synthetic regression test (`test_spec_cases.py`'s
  case 11) since the real Spree case (`spree_order_promotions` missing
  from the fixture) can't itself demonstrate success yet.

- **Missing DMN `<variable>` declaration on Spree's threshold
  decisions.** `Effective Minimum/Maximum Amount Threshold` had a real
  `informationRequirement` link to `Promotion Item Total Eligibility`
  in the DMN XML, but declared no `<variable name="...">` element, so
  `compile_constraints.py` never learned what name they produce and the
  edge was silently invisible to substitution. Fixed by adding the two
  `<variable>` elements, matching this DMN corpus's own existing
  convention. Confirmed this was the right, complete fix for what it
  targeted: the two variables now resolve correctly, but the rules stay
  blocked for the deeper, real reason (the same undecoded-blob gap) —
  a truer diagnosis, not a new failure.

- **Built the `serialized_field` mechanism, closing Spree's
  blob-decoding gap for 4 of 5 facts.** Previously, every fact stored
  inside `spree_promotion_rules.preferences` (a Rails
  `serialize :preferences, type: Hash, coder: YAML` column, confirmed
  against Spree's real source, not guessed) was `schema_gap`/
  `not_persisted` — the generator had no way to write a specific key
  into that blob, and the validator had no way to read one back out.
  Fixed end to end, in the same disclosed-declaration style as every
  other override file this project uses: a new `serialized_columns`
  annotation on the schema (`spree_promotion_rules.preferences`, format
  `yaml_hash`), a new CSV ground-truth syntax
  (`table.column[key]`/`table.column[key=default]`, parsed by a new
  `_SERIALIZED_FIELD_RE`), and a new `serialized_field` resolution kind
  threaded through the full round trip: `compile_constraints.py`
  (parses the syntax, emits the node), `candidate.py` (`derive_value`
  reads/writes an in-memory nested dict), `mutation.py` (mutates a
  specific key, including a `null_check`-with-`key` existence variant),
  `materialize.py` (`serialize_yaml_hash_blob` converts the dict to real
  YAML text only at INSERT time — the one point a candidate becomes
  SQL), and `validation_oracle/db_resolver.py`/`subject_table.py` (reads
  the same YAML back using the same declared format, independently of
  the generator). `fitness.py` needed zero changes — confirmed by
  reading it first — since its fitness read path is already fully
  kind-agnostic. Locked in with a new permanent test,
  `test_serialized_field_roundtrip.py` (write via mutation → materialize
  to real SQLite → read back via `resolve()`; plus both default-fallback
  paths), all 3 passing. Result, confirmed not assumed: Spree's compiled
  record count went 27/32 → 31/32, with `amountMaxSet`/`operatorMin`/
  `amountMin`/`operatorMax`/`amountMax` all resolving correctly against
  real YAML. **This closes the compile-time gap only** — the rules
  still need real search-generated data to verify (see "4 fixture/
  row-finding gaps" above for what's still blocking that). The 5th fact,
  `promotionTargetGroupIds`, is LIST-typed and deliberately deferred
  (needs FEEL `intersection`/`count` over two lists, a materially larger
  piece of work than a scalar preference read).
