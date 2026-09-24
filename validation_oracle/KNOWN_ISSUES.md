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
| OpenMRS | 42/56 (75.0%) | 14/14 (100%) |
| FLEX2 | 21/55 (38.2%) | 2/10 |
| Spree | 18/31 (58.1%) | 6/8 |
| jBilling | 10/40 (25.0%) | 6/16 |

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

- **`literal_via_upstream_branch` chaining — 0/57 verified corpus-wide
  (55 FLEX2, 2 jBilling) at time of writing, found investigating FLEX2's
  `Course Load Limit` (2026-09-24). Root cause CORRECTED same day after
  an initial wrong diagnosis — see below for both, since the correction
  itself is the useful part.**

  **Initial (wrong) diagnosis, retracted**: first suspected
  `generator/fitness.py`'s `evaluate_resolution` treats this node kind as
  an unconditional literal with no check that the search's own candidate
  data would make the upstream rule actually fire. **This was wrong** —
  checking `compile_constraints.py`'s own `_grounding_options`/
  `_enumerate_needs` (the code that BUILDS a "via" record) showed it
  already ANDs the upstream rule's own full condition into the
  downstream record's own compiled `condition` at compile time
  (`extra_clauses.append(opt['condition'])`) — confirmed directly:
  `Course Load Limit::Rule_1::via::Academic Warning Status::Rule_1`'s
  own compiled `condition` field genuinely contains `cumulativeGPA >=
  2.0 AND priorWarningCount = 0`, Academic Warning Status::Rule_1's own
  condition verbatim. The search's own fitness function was never the
  problem; it already has to satisfy both halves at once.

  **Actual root cause, confirmed by direct trace against the real FLEX2
  fixture**: `validation_oracle/drd_executor.py`'s `DecisionRunner.
  upstream_subject_value` — the function that finds which upstream
  decision's real row corresponds to the current downstream subject —
  did `row.get(hop['from_column'])` and `row[c] for c in
  upstream_pk_cols` with no case normalization. `hop['from_column']`/
  `upstream_pk_cols` carry the schema's own declared casing (e.g.
  `ROLL_NO`), but the row dict's own keys are the real lowercase SQLite
  column names (`roll_no`) — the identical pattern `db_resolver.py`'s
  own single-decision join-hop walk already normalizes via
  `hop['from_column'].lower()`, just never applied to this newer,
  cross-decision copy of the same logic. Every lookup silently missed,
  returned `None`, and got misreported as `UngroundedForCase("no
  corresponding upstream row")` — a validator-side false negative fired
  before the (already-correct) upstream condition was ever even
  checked. Confirmed directly: calling `upstream_subject_value` against
  a real FLEX2 subject returned `None`; tracing by hand showed the row
  really did have `roll_no` set, just under a key `.get('ROLL_NO')`
  could never match.

  **Fixed**: both call sites in `upstream_subject_value` now `.lower()`
  the schema-cased column name before the dict lookup, matching
  `db_resolver.py`'s own existing convention exactly. Verified directly:
  every FLEX2 subject that previously returned `None` now correctly
  resolves a real upstream selected rule.

  **Net effect on verified counts, so far: none** — fixing this
  unmasked a SEPARATE, previously-unreached validator gap:
  `db_resolver.py`/`drd_executor.py` never implemented the `derived_case`
  resolution kind at all (a categorical column mapping, e.g.
  `SEMESTER.TITLE`: `'Fall'/'Spring' -> 'Regular'`, `'Summer' ->
  'Summer'` — the generator's own `candidate.py` already handles this
  kind, the validator never needed to until this fix let evaluation
  reach that far). `Course Load Limit`'s own `semesterType` uses it,
  so the WHOLE decision still fails, now with `Unhandled
  variable_resolution kind 'derived_case'` instead of a false
  "ungrounded" — the correct failure this time, not a bug, but still a
  gap. 33 FLEX2 records use this kind corpus-wide. jBilling's own 2
  `literal_via_upstream_branch` records are unaffected either way — the
  decision they belong to (`Payment Balance Assignment`, chained from
  `Payment Outcome Resolution`) was already blocked before reaching this
  code at all, for the pre-existing, unrelated "no table-backed inputs"
  reason above.

  Full regression suite (`test_spec_cases.py`,
  `test_drd_chaining_synthetic.py` — including its own
  `test_literal_via_upstream_branch` case — `test_serialized_field_
  roundtrip.py`, `drd_executor.py`'s own OpenMRS acceptance test)
  re-run and passing unchanged.

  **`derived_case` implemented in `db_resolver.py`'s `resolve()`
  (2026-09-24), closing this gap.** A direct, mechanical port of
  `candidate.py`'s own handling: read the real column via the existing
  `row_for(table)` helper, walk `node['cases']` for a matching real
  value, return the mapped value, or raise (never silently default)
  when the real value isn't covered by any case — same error wording as
  the generator side. Verified directly against the real FLEX2 fixture
  before trusting it (`SEMESTER.TITLE='Fall'` correctly resolves
  `semesterType='Regular'`, etc.), then confirmed via a fresh
  `coverage.py` run: `Course Load Limit` is no longer in
  `unresolved_decisions` at all (FLEX2's own unresolved count: 8→7) —
  every one of its 11 objectives is now genuinely, fully evaluated
  end to end for the first time, with real resolved inputs and a real
  rule-selection attempt, rather than failing before ever reaching
  that point.

  **Net effect on verified counts: still 0/11 for `Course Load
  Limit`, but now for a real, disclosed reason instead of a validator
  bug.** Inspecting `decision_trace.json` directly: most real subjects
  correctly come back `ungrounded` (their real Academic Warning Status
  outcome doesn't match this specific "via" variant's own assumption —
  expected, since only a few subjects should ever ground any one
  variant). The handful that DO ground (e.g. subject `(6, 6)`:
  `newWarningCount=3` from a real, confirmed `Academic Warning
  Status::Rule_6` match, `semesterType='Summer'`, `cumulativeGPA=-2`,
  `priorWarningCount=2`) still select no rule at all — none of Course
  Load Limit's own rule conditions match that real combination. This is
  a genuine, separate, generator-side gap (the search's own merge never
  aligned all 4 of this composite record's own independent leaves —
  `newWarningCount`/`semesterType`/`cumulativeGPA`/`priorWarningCount`
  — onto one mutually-consistent real subject), not a validator issue.
  Both validator-side bugs found chasing this (`upstream_subject_value`'s
  case-sensitivity gap, `derived_case` being unimplemented) are now
  fully fixed; what's left is exactly the gap documented immediately
  below — not a coincidence, the SAME root cause.

- **FIXED 2026-09-24: generator never constructed a decision's own real
  subject row when no leaf reads it directly.** `dynamosa.py`'s own
  per-objective focal-row logic (`_focal_tables_for_leaf`/
  `_focal_table_set_for`) decides which tables get a dedicated row
  PURELY from which tables a record's own leaf variables read, with no
  concept of a decision's real DMN subject grain at all (confirmed by
  direct grep, before this fix: zero references from any generator
  file into `validation_oracle/subject_table.py`). When that subject is
  a pure junction/link table no leaf ever reads (confirmed real in
  FLEX2's `Course Load Limit` — reads only `SEMESTER`/`STUDENT_PROGRAM`,
  no FK between them at all, real subject `STUDENT_SEMESTER` — and
  OpenMRS's `Identifier Uniqueness Check` — subject `patient_identifier`,
  which `exists`-kind leaves scan directly but never anchor a dedicated
  focal row to), the generator never built one at all, so independent
  verification could never find a corresponding real case, even when
  every individual fact was correct in isolation.

  **Option chosen: extend `compile_constraints.py`, not import from
  `validation_oracle/`.** `DESIGN.md`'s own "Architectural separation
  requirement" states, as a hard constraint, "no overlap in function
  calls with the search approach" — written as a rule on what the
  validator may import from the generator, but the same intent (the
  generator must not be shaped by knowledge of how it's independently
  checked) applies in the other direction too. So rather than import
  `subject_table_for_decision`, `compile_constraints.py` now computes
  the SAME fact independently (`compute_decision_subject`, a generator-
  owned port of that module's own forward-FK-BFS algorithm, deliberately
  NARROWER in scope — forward edges only, no disambiguation-override
  support — disclosed in that function's own docstring) and stores it as
  a new `decision_subject: {table, pk_columns, joins}` field on every
  compiled record of a decision, exactly the same precedent already
  established for Phase 1's other compile-time metadata.
  `dynamosa.py`'s `merge_archive_candidate` reads this field ONCE, at
  the very end of merging each covered record's own rows in: if the
  subject table isn't already among that record's own focal tables, it
  builds a real junction row there, with FK columns explicitly set to
  the SAME already-merged, already-offset focal rows for the record's
  other tables (assigning a fresh PK to a referenced row on the spot,
  via `mutation.py`'s existing `_fresh_key_value`, when that row's own
  PK was never otherwise set — never left to `materialize.py`'s later,
  offset-oblivious surrogate-key fill, which has no way to also update
  a cross-reference elsewhere). No leaf ever reads this row during
  search, so nothing about the population loop, mutation, or fitness
  changed at all — this is purely a one-time, post-search synthesis
  step.

  **Two more real, independently-confirmed bugs found verifying this,
  both fixed the same day:**
  1. `validation_oracle/subject_table.py`'s own `tables_referenced` had
     `substituted_decision` listed in BOTH `_TABLE_EXTRACTORS`'-checked
     `_NON_TABLE_KINDS` (returning an empty table set unconditionally)
     AND had its own dedicated recursive-into-free-variables branch
     further down — permanently unreachable dead code, since the
     `_NON_TABLE_KINDS` check ran first. Confirmed real, not cosmetic:
     Spree's `Promotion Customer Group Eligibility::rule_4` has a
     `substituted_decision` (`matchingCustomerGroupCount`) whose own
     free variable reads `spree_customer_group_users` directly, so the
     validator's own `join_paths` was silently missing that table — a
     latent `NotImplementedError` waiting to fire the moment real
     verification ever reached that variable. Fixed by removing
     `substituted_decision` from `_NON_TABLE_KINDS`.
  2. `fitness.py`'s `_unique_key_sets` did a plain, case-SENSITIVE
     `schema.get(table, {})` lookup, unlike its own caller
     (`mutation.py`'s `_repair_row`, one line earlier) which already
     handles case-insensitivity. Invisible until this fix, since it only
     matters when MULTIPLE rows of the SAME table need a fresh PK
     within one `repair_candidate` pass — exactly what this fix's own
     junction-row construction does for the first time. For any
     lowercase-schema case study (OpenMRS), the table name
     `Candidate.add_row` always uppercases internally never matched the
     schema's own lowercase key, so `_repair_row` silently treated the
     table's own declared PK as an ordinary column and filled it with a
     single, shared, non-unique PLACEHOLDER value instead of a real
     fresh one — confirmed directly: 3 new `PATIENT_IDENTIFIER` rows all
     silently received `patient_identifier_id=1`, a real
     `sqlite3.IntegrityError: UNIQUE constraint failed` the moment this
     was actually exercised. Fixed with the same case-insensitive
     fallback `_repair_row`'s own `info` lookup already uses.

  **Verified result, confirmed via a fresh, per-objective before/after
  diff across all 4 case studies (not just totals) after re-running the
  Spree search — needed since fixing bug 2 above touched
  `spree_schema_full.json`'s own `fk_columns` too, see below — and
  rebuilding every fixture:** OpenMRS 41→42 verified
  (`Identifier Uniqueness Check::rule_1` flips `false_positive` →
  `confirmed` — the fix's real, structural win), zero flips anywhere
  else in OpenMRS, and zero flips at all in FLEX2/Spree/jBilling.
  `Course Load Limit` itself is STILL 0/11 — the junction row now
  exists (confirmed directly: a real `STUDENT_SEMESTER` row correctly
  cross-references the SAME objective's own `SEMESTER`/`STUDENT_PROGRAM`
  rows), but the search's own values on each side still don't jointly
  satisfy the DMN condition for any one real subject — a separate,
  disclosed "composite-leaf value alignment" gap (see that decision's
  own earlier entry above) this fix was never scoped to solve; it
  solves the STRUCTURAL correspondence, not the search's own value
  coordination. Full self-test suite (`candidate.py`, `mutation.py`,
  `materialize.py`, `dynamosa.py`, `subject_table.py`,
  `test_spec_cases.py`, `test_drd_chaining_synthetic.py`,
  `test_serialized_field_roundtrip.py`) re-run and passing.

  **While porting this, also needed a THIRD instance of this session's
  own recurring `fk_columns: []` schema-extraction gap** —
  `spree_order_promotions`/`spree_promotion_rules` both had it despite
  real, unambiguous FKs (confirmed against `schemas/spree_schema.rb`),
  previously papered over only via `validation_oracle/
  supplementary_fk_edges.py`'s own additive override (which the
  generator-owned port, by design, does not import) — fixed the same
  way as the other two Spree instances this session, directly in
  `spree_schema_full.json`. This is what let
  `compute_decision_subject` resolve `Promotion Customer Group
  Eligibility`'s own subject at all before bug 1 above was found and
  fixed — see that decision's own corrected entry below for the final
  word on where it landed.

  **Not the same as the "0 candidates qualify, refusing to guess"
  failures** (FLEX2's `Admission Closure Eligibility`/`Course
  Registration Eligibility`/`Credit Transfer Exemption`/`Graduation
  Eligibility`/`Summer Semester Registration`, Spree's `Promotion Item
  Total Eligibility` AND, as of this fix, `Promotion Customer Group
  Eligibility` too — see below) — those fail one stage EARLIER, when
  `subject_table_for_decision` itself can't find a unique root at all.
  Whether any of them would also hit this junction gap once/if that
  earlier problem is resolved is untested.

### Spree

- **OUT OF SCOPE, by explicit decision (2026-09-24): generating/
  verifying data at blob/attribute level, inside a single serialized
  column.** The `serialized_field` mechanism (see "Fixed issues" below)
  was already built and does work — schema-declared, confirmed against
  Spree's real source, round-trip tested — but reaching this deep is a
  materially different, finer-grained kind of work than what this
  project is meant to demonstrate: whether a search-based generator
  resolves a real *data-backend* dependency (does the right ROW/COLUMN
  exist, is it joined correctly), not whether it can also reverse-
  engineer and populate a specific key inside one column's own
  serialized/YAML content. Even where the schema and format are fully
  known (as they are here — this isn't a case of missing information),
  deliberately generating a value at that key-inside-a-column
  granularity goes beyond the project's own scope. Reclassified from
  "open bug to eventually fix" to **out of scope, not pursued further**:
  - `Promotion Item Total Eligibility` (all 4 rules) — every rule reads
    `amountMin`/`operatorMin`/`amountMax`/`operatorMax`/`amountMaxSet`
    out of `spree_promotion_rules.preferences`'s serialized blob. Even
    setting aside this decision's OWN separate row-finding gap (below),
    the underlying facts are blob-level, so the decision stays out of
    scope regardless of whether that gap ever gets fixed.
  - `Promotion Customer Group Eligibility::rule_3` — `promotionTargetGroupIds`
    is a LIST-typed fact inside the same kind of serialized blob, needing
    FEEL `intersection`/`count` over two lists on top of the blob-decode
    itself. `rule_1`/`rule_2` of this same decision are NOT affected —
    they read `spree_promotion_rules.type`, an ordinary real column, not
    blob content — and remain a solvable, in-scope gap (below).

- **1 fixture/row-finding gap (3 rules, 1 decision) remains**, after the
  Spree search re-run closed a 3rd decision
  (`Price List Volume Adjustment Tier Selection`, see "Fixed issues"
  below), the blob-dependent 4th (`Promotion Item Total Eligibility`)
  was reclassified out of scope above, and the IN-subquery construction
  mechanism (see "Fixed issues" below) closed `Promotion Usage Limit
  Exceeded` (3 of 4 rules) and `One-Use-Per-User Promotion
  Eligibility::rule_3`:
  - **`Promotion Customer Group Eligibility` (rules 1, 2, 4 — not
    `rule_3`, out of scope above) — root cause corrected TWICE the same
    day (2026-09-24); final word below.** Originally attributed to a
    one-to-many backward join `subject_table_for_decision` supposedly
    "correctly refuses to guess" at. **Wrong** — it actually resolved
    this decision's subject cleanly, as `spree_order_promotions`, no
    ambiguity. That, in turn, looked like the SAME "generator never
    builds the junction row" gap as FLEX2's `Course Load Limit` (see the
    cross-case-study entry above) — **also not the final answer**:
    building that fix's own generator-side port surfaced a real bug in
    `subject_table.py` itself (`substituted_decision` dead code, see the
    cross-case-study entry's own bug #1) that was silently letting this
    decision's subject resolve AT ALL. Once fixed, `rule_4`'s own
    `matchingCustomerGroupCount` correctly requires reaching
    `spree_customer_group_users` too — a table with NO real forward-FK
    or shared-PK-subtype path from `spree_order_promotions` at all (a
    genuine one-to-many: one user can belong to many customer groups).
    **Final, confirmed answer**: this decision genuinely belongs in the
    SAME "0 candidates qualify, refusing to guess" category as the other
    6 decisions below/above, not the junction-gap category — `rule_4`'s
    own real one-to-many backward-join need blocks a subject from being
    determined for the WHOLE decision (subject is a per-decision fact,
    shared by all its rules), so `rule_1`/`rule_2` don't benefit from
    the junction-row fix either, even though neither of them touches
    `spree_customer_group_users` at all. Needs the same kind of
    disclosed backward-join override as the other "0 candidates"
    decisions, not the generator-side fix built above.


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
  still need real search-generated data to verify (see "3 fixture/
  row-finding gaps" above for what's still blocking that). The 5th fact,
  `promotionTargetGroupIds`, is LIST-typed and deliberately deferred
  (needs FEEL `intersection`/`count` over two lists, a materially larger
  piece of work than a scalar preference read).

- **Re-ran the Spree DynaMOSA search against the current ground truth
  and rebuilt `spree_merged.db` from the fresh archive.** This was the
  actual, real search/experiment-data work the blob-decoding and
  fixture-gap entries above had been deferring pending an explicit
  go-ahead. Running it for the first time against the post-
  `serialized_field` `compiled_constraints.json` surfaced and fixed
  three real bugs, none of them hit by anything compiled before this
  session (each is a genuine gap in generic, case-study-agnostic code,
  not a Spree-specific patch):
  1. `candidate.py`'s `build_seed_candidate` seeded EVERY `null_check`
     leaf with a bare scalar placeholder (`row[column] = 1`), including
     the new key-scoped variant (`null_check` with a `key`, e.g.
     `amountMaxSet`) — stamping a plain `1` directly over what must
     stay a nested dict crashed the very next read of ANY key on that
     same row with `'int' object has no attribute 'get'`. Fixed by
     seeding a real one-key dict for the key-scoped case, and added the
     missing `serialized_field`-kind seeding branch entirely (previously
     absent — a bare `serialized_field` leaf was never seeded at all).
  2. `fitness.py`'s arithmetic evaluator (`evaluate_expression`'s `+-*/`
     dispatch) let a raw Python `TypeError` escape when an operand was
     legitimately `None` (a `serialized_field` with no default, still
     unset) instead of raising this module's own established
     `FitnessEvaluationError` convention — the exact same class of gap
     `_comparison_distance_true` already documents fixing once for
     ordering comparisons, just one level earlier (raw arithmetic, not
     yet a comparison). Fixed with the same numeric-operand guard;
     `mutation.py`'s `best_value_for` also needed a catch around its own
     "current genome" fitness call (mirroring `_hypothetical_fitness`'s
     existing catch-and-treat-as-`inf` convention), since a sibling gene
     on the same row can legitimately be in this not-yet-evaluable state
     when `best_value_for` is asked about a DIFFERENT variable.
  3. `_row_from_filter_conjuncts`/`_mechanical_filter_predicate`
     (candidate.py, and its independent mirror in mutation.py) misread
     the trailing SQL tautology guard `AND 1=1` — present verbatim in
     `adjustedCreditsCount`'s own real `filter_text` — as a real
     `COLUMN = VALUE` conjunct naming a column literally called `"1"`,
     which reached real SQLite as `INSERT INTO spree_discounts (1,
     ...)` and failed with a syntax error. Fixed in all 3 call sites: a
     conjunct whose "column" side is a bare digit string is recognized
     as the always-true no-op it actually is in real SQL, not guessed
     at as a column.
  Re-verified the full regression suite and every module's own
  self-test (`candidate.py`, `fitness.py`, `mutation.py`,
  `test_spec_cases.py`, `test_drd_chaining_synthetic.py`,
  `test_serialized_field_roundtrip.py`) after each fix, all passing,
  before re-running the search again.

  **Result, independently verified (not the search's own optimistic
  claim) via `coverage.py` against the freshly rebuilt fixture, with
  the same disclosed `evaluationTime=20000` override already used
  elsewhere in this project:** verified rule coverage 9/26 (34.6%) →
  12/31 (38.7%); verified decision-table coverage 4/8 → 5/8.
  `Price List Volume Adjustment Tier Selection` (3 rules, previously
  blocked purely by the missing-table half of the fixture gap) is now
  fully verified — closed exactly as predicted, by the search re-run
  alone, no further mechanism needed. `Promotion Temporal Availability`
  rule_1/rule_3 are now verified too (previously blocked on the
  `evaluationTime` override never having been supplied to this
  project's own `coverage.py` invocation for Spree specifically).
  `First-Order Promotion Eligibility::rule_3` did NOT resolve at this
  point (fixed in a later round the same day — see "Fixed the
  First-Order Promotion Eligibility shadowing gap" below). The remaining
  open gaps (`Promotion Customer Group Eligibility`, `Promotion Item
  Total Eligibility`, `Promotion Usage Limit Exceeded`, and the
  COLLECT-only `Price Adjustment Tier Validity Violations`) are
  unchanged by the re-run, exactly as the "2 fixture/row-finding gaps"
  entry above now
  precisely diagnoses for the two of them that are solvable, in-scope
  join gaps. `Promotion Item Total Eligibility` was subsequently
  reclassified as out of scope (blob-level data), not a bug to fix —
  see the scope-decision entry above.

  **Scope note added 2026-09-24, after this mechanism was already
  built and shipped**: on reflection, deliberately generating/verifying
  a value at the granularity of one key inside a serialized column's
  own content — even with the schema/format fully known, as it is
  here — goes beyond this project's intended scope (resolving
  data-backend dependencies at the row/column level, not decoding
  attribute-level structure within a column). The mechanism above
  stays in the codebase (it's real, tested, working code, and closing
  it made the compile-time picture measurably more honest), but it is
  not being extended or exercised further, and the rules that only
  verify via it (`Promotion Item Total Eligibility`,
  `Promotion Customer Group Eligibility::rule_3`) are now tracked as
  out of scope in the Open Issues section above, not as pending work.

- **Re-expressed `One-Use-Per-User Promotion Eligibility::rule_2`'s
  compile bug, closing it.** `priorPromotionUsageCount`'s free-text
  schema_location (`spree_discounts (joined via ...)`) matched none of
  `classify_derived`'s recognized recipe shapes, so it silently compiled
  to `{'kind': 'schema_column', 'table': 'spree_orders', 'column':
  'user_id'}` — comparing a raw `user_id` against `0`, "working" only
  because no real customer has `user_id = 0`. Re-expressed using the
  same `COUNT(TABLE) WHERE <filter>` recipe `adjustedCreditsCount`
  already uses: `COUNT(spree_discounts) WHERE order_id IN (SELECT id
  FROM spree_orders WHERE user_id = <user_id> AND completed_at IS NOT
  NULL AND id != self) AND 1=1`, with the same disclosed simplification
  as `adjustedCreditsCount` (no promotion-scoping is possible — this
  decision's own DMN declares no promotion input at all — so this counts
  ANY prior promotional discount by this customer, not "this promotion"
  specifically). One self-inflicted bug found and fixed while writing
  the note: the note text itself accidentally contained a literal
  `COUNT(TABLE)`-shaped phrase, which `classify_derived` matched (it
  tries `notes` before `raw_schema_field`) before ever reaching the real
  recipe — fixed by rewording the note to describe the shape without
  literally spelling it out. **Verified, not just compiled**: re-ran the
  Spree search; `rule_2` now verifies against real data (a real order
  with zero attributable `spree_discounts` rows is the common case, so
  `priorPromotionUsageCount = 0` is trivially reachable once it's a real
  count instead of an impossible `user_id = 0`).

- **Fixed the `Promotion Temporal Availability::rule_2` DMN authoring
  bug.** The compiled condition was `expiresAt > expiresAt`, a
  self-referential tautology — confirmed in the raw DMN XML
  (`Promotion_Order_Level_Eligibility.dmn`): the rule's `expires_at`
  input-column cell read `<inputEntry><text>&gt; expiresAt</text>
  </inputEntry>`, compared against its own column. Fixed by moving the
  `> expiresAt` unary test to the `evaluationTime` column, where it
  evidently belonged (given the rule's own `"EXPIRED"` output and the
  decision's declared inputs) — the condition now reads `evaluationTime
  > expiresAt AND expiresAtSet = true`. **Verified against real data**
  after also fixing the `null_check` polarity bug below (this rule
  depends on `expiresAtSet`'s own correctness, which the tautology had
  been masking): confirmed via `coverage.py`.

- **Fixed the `First-Order Promotion Eligibility::rule_3` shadowing
  gap — a real generator/validator mismatch, not a search-budget
  problem.** `Prior Completed Order Count`'s own filter_text
  (`literal_expression_overrides.py`) uses `completed_at IS NOT NULL`
  and `(user_id = <user_id> OR email = <email>)`, neither of which
  `_mechanical_filter_predicate`/`_row_from_filter_conjuncts`
  (`generator/candidate.py`, `generator/mutation.py`) understood at
  all — `IS NOT NULL` has no `=` sign (didn't match the only recognized
  conjunct shape), and `(A OR B)` isn't a shape either function has ever
  parsed. Net effect: the search's own approximate fitness reached
  0.0 from the very first seeded candidate (every row silently counted
  as "a prior completed order," since neither constraint was ever
  actually applied), while the real validator, correctly requiring an
  actual matching, completed order, found none — search_covered=True,
  verified=False on every run, regardless of budget. Three real fixes,
  found in sequence chasing this one gap:
  1. Added recognition for `COLUMN IS NOT NULL`/`COLUMN IS NULL` as a
     real conjunct shape, in both the read-side predicate and the two
     write-side row-builders.
  2. That fix alone mis-fired on `adjustedCreditsCount`-style filters:
     `priorPromotionUsageCount`'s new filter_text (above) has an
     `IS NOT NULL` fragment INSIDE a parenthesized IN-subquery, on a
     DIFFERENT table than the outer filter's own — the naive
     `re.split(r'\bAND\b', ...)` doesn't track paren depth, so this
     fragment was misread as a top-level conjunct of the OUTER table,
     stamping a nonexistent column onto the wrong row. Fixed with a new
     shared `_top_level_and_conjuncts` helper (paren-depth-aware split,
     used by all 3 call sites) — checked against every filter_text in
     the compiled corpus that mixes `(` and `AND` (3, across
     Spree/FLEX2) to confirm the other two don't regress.
  3. Simplified `Prior Completed Order Count`'s own filter_text to drop
     the `OR email = <email>` alternative (`(A OR B)` parsing was out of
     scope to build) — a disclosed narrowing (loses the guest-checkout-
     by-email path), same status as `adjustedCreditsCount`'s own
     disclosed simplification, not a guess at missing schema.
  **Verified, not just seeded-to-zero**: re-ran the Spree search;
  `rule_3` now verifies against real data.

- **Found and fixed a `null_check` polarity inversion in
  `validation_oracle/db_resolver.py`, affecting every plain (non-key)
  `null_check` fact across all 4 case studies (54 compiled records).**
  Found while investigating why the `Promotion Temporal Availability`
  DMN fix above still didn't verify: `db_resolver.py`'s `null_check`
  resolution computed `column IS NULL`, while
  `generator/candidate.py`'s own `derive_value` (the canonical
  definition the search itself optimizes against) computes `column IS
  NOT NULL` — flat-out inverted between the two sides that are supposed
  to agree on the exact same fact. Confirmed with an isolated unit test
  (a throwaway 2-row SQLite table) before touching anything: a row with
  the column SET read back as `False`; a row with it `NULL` read back as
  `True`. Fixed in `db_resolver.py` to match `candidate.py`'s
  convention. A blind fix (always `IS NOT NULL`) then broke OpenMRS's
  `identifierBlank` the other way — its own ground truth is worded
  "identifier IS NULL OR TRIM(identifier) = ''", true meaning EMPTY, the
  opposite polarity from every other null_check fact in this corpus
  (`expiresAtSet`/`amountMaxSet`/`customerPresent`/etc., true meaning
  SET) — caught by this project's own required before/after diff across
  all 4 case studies, run precisely because a change this broad
  (touching 54 records) could not be trusted from Spree's own numbers
  alone. Fixed properly at the root: `compile_constraints.py` now adds
  a `negate: true` flag to a compiled `null_check` node when its own
  ground-truth notes say "IS NULL" without also saying "IS NOT NULL"
  (`_null_check_is_negated`), and every consumer — `candidate.py`'s
  `derive_value`/`build_seed_candidate`'s seeding, `mutation.py`'s
  `_apply_field_mutation` (both plain and key-scoped) and
  `_hypothetical_fitness`'s sibling-sync logic, and `db_resolver.py`'s
  `resolve()` — honors the same flag consistently, rather than each
  guessing its own fixed polarity or sniffing variable names. **Result,
  confirmed via the full 4-case-study before/after diff (verified rule
  ID sets, not just counts) before being trusted**: OpenMRS 35→41
  verified (all gains real; the one rule whose `verified` flag flipped
  to False, `Identifier Format Validity::Rule_2`, was itself a bug
  artifact — a `false_negative` the OLD inverted code produced, not a
  real capability lost — confirmed by checking `identifierBlank` against
  real, populated `patient_identifier.identifier` values directly),
  FLEX2 21→21 (no plain null_check fact there is negated or otherwise
  affected), jBilling 9→10. Full regression suite
  (`test_spec_cases.py`, `test_drd_chaining_synthetic.py`, the OpenMRS
  acceptance test in `drd_executor.py`, `test_serialized_field_
  roundtrip.py`) re-run and passing after every incremental step of
  this fix, not just at the end.

- **Built the `COLUMN IN (SELECT ... WHERE ...)` construction mechanism,
  closing `Promotion Usage Limit Exceeded` (3 of 4 rules) and
  `One-Use-Per-User Promotion Eligibility::rule_3` — plus two
  supporting fixes found chasing it (2026-09-24).** Root cause: this
  filter shape was entirely unrecognized by both
  `_mechanical_filter_predicate` (read side) and
  `_row_from_filter_conjuncts` (write side, in both `candidate.py` and
  `mutation.py`) — every conjunct inside it got silently dropped, so the
  search's own fitness degraded to "match anything," reached 0.0 from an
  arbitrary row, and stopped, while the real validator, running the
  actual `IN (SELECT...)` SQL, correctly found no match. Same species of
  generator/validator mismatch as `First-Order Promotion Eligibility::
  rule_3` above, different shape. Fixed with:
  1. `_top_level_and_conjuncts` rewritten from a fragment-filtering pass
     into a real, character-level, paren-depth-aware splitter that
     reconstructs the full conjunct text (the old version safely
     truncated a conjunct containing nested ANDs, since nothing had
     ever needed to read inside one — the IN-subquery's own inner WHERE
     needed exactly that).
  2. New `_construct_subquery_parent` in `candidate.py` (reused, not
     duplicated, by `mutation.py`): recognizes `COLUMN IN (SELECT PK
     FROM TABLE WHERE ...)`, builds or reuses a real row in the
     subquery's own table from whatever conjuncts inside it ARE
     mechanically bindable, and returns that row's real id for the
     outer column. Where the subquery's own WHERE references `self`
     (the decision's own subject row's PK — same convention
     `db_resolver.py`'s `_substitute_self_and_colon` already uses at
     verification time), a new disclosed override,
     `generator/aggregate_self_table.py`, names which table `self`
     means for a given `(case_study, variable_name)` — the generator
     side has no equivalent per-record "subject table" computation the
     way the validator does, so it's named explicitly rather than
     guessed. Currently one entry: `('Spree', 'adjustedCreditsCount'):
     'spree_promotions'`.
  3. A real schema-extraction gap surfaced fixing the above:
     `spree_discounts.fk_columns` was `[]` in `spree_schema_full.json`
     despite every column being typed `bigint(ref)` (same class of gap
     as `spree_order_promotions`/`spree_promotion_rules`, fixed earlier)
     — `dynamosa.py`'s own merge-time key-offsetting reads this field to
     decide which columns to shift in step with the rows they reference,
     so with it empty, `spree_discounts`'s own FK columns silently
     stayed unshifted while the tables they pointed at got shifted,
     breaking the correspondence after merge. Fixed by adding the real
     FK entries directly to the schema JSON.
  4. Fixing (3) surfaced a third, previously-masked bug in
     `materialize.py`: a row missing its own table's surrogate key was
     left for SQLite's own NULL-rowid auto-assignment to fill in at
     INSERT time — a value with zero visibility into this pipeline's own
     explicit, offset-derived ids elsewhere in the same table. Once (3)
     made both id sources actually overlap, this produced a real
     `sqlite3.IntegrityError: UNIQUE constraint failed: SPREE_ORDERS.id`
     (traced directly: an unrelated, id-less `SPREE_ORDERS` row for
     `Promotion Tiered Percent Discount Selection::rule_1` got
     auto-assigned 16000004 by SQLite mid-insert-sequence, and a later,
     equally unrelated row for `One-Use-Per-User Promotion
     Eligibility::rule_3` legitimately carried that same explicit,
     offset-derived id — two rows with no real relationship an FK could
     ever express). Fixed with `_fill_missing_surrogate_keys` in
     `materialize.py` (used by both `to_sql_inserts` and
     `validate_with_sqlite`): every id-less row in a table now gets an
     explicit id, computed past the max of every already-used value in
     that same table, before any INSERT statement is even built — never
     delegated to SQLite's own implicit per-statement behavior. Applies
     pipeline-wide (all 4 case studies), since the gap was in shared
     code, not Spree-specific.
  **Verified, not just constructed in isolation**: re-ran the Spree
  search, rebuilt `spree_merged.db`, re-ran `coverage.py` — 14→17
  verified rules (see `COVERAGE_REPORT.md`'s 2026-09-24 entry for the
  full accounting, including the one false alarm the cross-case-study
  regression check caught and resolved: a stale `coverage_out/`
  artifact, not a real regression). One rule from the original 8,
  `Promotion Usage Limit Exceeded::rule_3`, remained open after this
  round — see the next entry, which closes it.

- **Closed `Promotion Usage Limit Exceeded::rule_3`, the last of the
  original 8 — a THIRD instance of the `fk_columns: []` schema-extraction
  gap (2026-09-24).** Investigating why no constructed subject ever had
  `adjustedCreditsCount >= usageLimit` (confirmed: `matched_rule_ids`
  never included `rule_3` for any real subject in `decision_trace.json`,
  despite rules 1/2/4 of the SAME decision already verifying correctly)
  traced to `spree_promotion_actions.fk_columns` ALSO being `[]` despite
  `promotion_id` being a real FK to `spree_promotions.id` (confirmed
  against `schemas/spree_schema.rb`'s own `t.bigint "promotion_id"`
  declaration — same class of gap as `spree_discounts` and
  `spree_order_promotions`/`spree_promotion_rules`, fixed earlier this
  session). Effect: `promotion_id` was never included in either
  `_seed_shared_population`'s or `merge_archive_candidate`'s own
  key-column offsetting, so it stayed at its raw, pre-offset placeholder
  value while the `spree_promotions` row it targets got shifted,
  breaking the join `adjustedCreditsCount`'s own filter depends on — the
  real validator always found 0 matching `spree_discounts` rows
  regardless of how many were actually constructed.

  **A more general lesson surfaced fixing this one**: the schema JSON is
  read at TWO separate offsetting stages — `_seed_shared_population`
  (per-objective, at initial seeding) and `merge_archive_candidate` (at
  final merge) — and both must see the SAME schema for their two offset
  passes to compose correctly. Editing `fk_columns` and only rebuilding
  the fixture from an ALREADY-EXISTING archive pickle (skipping the
  search re-run) leaves the pickle's own baked-in per-objective offsets
  computed under the OLD schema, while the merge step re-offsets under
  the NEW schema — double-offsetting a column already shifted once at
  seed time, while single-offsetting one (`promotion_id` here) that
  wasn't shifted before at all, corrupting the correspondence between
  them (a real, reproduced intermediate failure this round: rebuilding
  the fixture right after the schema edit, without re-running the
  search first, produced `usage_limit=1` on one row and
  `promotion_id=18000001` pointing at a DIFFERENT, ownerless row — fixed
  by re-running the search before rebuilding). **General takeaway,
  applicable beyond Spree**: any `fk_columns` schema edit needs a full
  search re-run, not just a fixture rebuild, to take effect consistently
  — a fixture rebuilt from a stale archive can silently corrupt exactly
  the correspondence the schema edit was meant to fix.

  **Verified**: re-ran the Spree search, rebuilt `spree_merged.db`,
  re-ran `coverage.py` — 17→18 verified, all 4 rules of `Promotion Usage
  Limit Exceeded` now confirmed, closing all 8 of the originally
  search-claimed-but-unverified rules. Full self-test/regression suite
  re-run and passing (Spree-only fix — `spree_promotion_actions` doesn't
  exist in the other 3 case studies).
