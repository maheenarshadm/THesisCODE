# How a DMN rule becomes a search objective — the exact mechanism

**Purpose:** a precise, example-grounded walkthrough of what
`generator/compile_constraints.py` actually does to turn one row of one
real DMN decision table into a compiled JSON record the search can
optimize against — including every distinct pattern ("resolution kind")
used to map a DMN variable onto a real table/column/row, and the one
mechanism that can turn a single rule into several separate objectives.
Every example below is a real value pulled from the current
`compiled_constraints.json`, not invented.

See `QUICK_REFERENCE.md` for the short glossary version of "rule" vs.
"objective" if that's all you need. This file is the full mechanism.

---

## 1. The pipeline, top to bottom

For each real DMN decision table, for each of its rules (rows), in
order:

1. **Parse the rule's own condition** into a structured predicate tree
   (`build_rule_condition`) — never a FEEL string kept around, always a
   real tree of `and`/`or`/`not`/comparison/`variable`/`literal` nodes.
2. **Find every free variable** that condition tree references
   (`find_all_variable_refs`).
3. **Resolve each variable** to a real schema fact — this is where the
   "resolution kind" classification (§2 below) happens
   (`resolve_and_substitute` → `resolve_variable` → `classify_derived`).
4. **Resolve the earlier rows too**, for FIRST/UNIQUE hit policy (the
   suppression term — "and no earlier row's own condition holds") — same
   resolution machinery, same variables possibly reused.
5. **If any variable's resolution depends on an upstream multi-rule
   decision** (not a single value, but "whichever of that decision's own
   rules fires"), **expand into one compiled record per viable upstream
   rule** — this is the one-rule-to-many-objectives mechanism (§3).
6. **Fold the fully-assembled condition** using only what's fixed at
   compile time (three-valued constant folding) — a record whose
   condition is now PROVABLY false (e.g. a genuine tautology's negation)
   is dropped as `infeasible`, never handed to the search to waste time
   on.
7. **Emit one JSON record** (`record_id`, `condition`,
   `variable_resolution`, `hit_policy_context`, `fk_closure_tables`, ...)
   — this is the actual search objective.

A rule that can't get all the way through step 3–5 is `blocked`, not
silently dropped — `compile_report.json` names exactly why (an
unresolved variable, a genuinely unexpandable chain, or a FEEL parse
error).

## 2. Resolving ONE variable to a real schema fact — the kind taxonomy

Every ground-truth CSV row (`<case_study>_dmn/provenance/
variable_to_schema_mapping.csv`) has a `mapping_type` column, normalized
into one of 4 buckets, each dispatching to one or more "resolution
kinds" — the actual tagged shape a compiled `variable_resolution` entry
carries. This is the real classification the search/validator code
switches on everywhere.

### Bucket: `not-persisted` / `not persisted` → kind `not_persisted`

The fact has **no real table backing at all** — a genuine scenario/
runtime parameter (never silently defaulted; needs an explicit,
disclosed override at verification time).

Example — OpenMRS, `Order Date Activated Consistency Violations` →
`evaluationTime`:

```json
{"kind": "not_persisted"}
```

### Bucket: `schema gap` → kind `schema_gap`

An explicit, disclosed "we know this fact has no clean resolution" —
never silently guessed at, never forced into a wrong shape.

Example — Spree, `Promotion Customer Group Eligibility` →
`promotionTargetGroupIds`:

```json
{"kind": "schema_gap",
 "notes": "CustomerGroup rule's customer_group_ids array lives in the serialized preferences blob, not a dedicated join table..."}
```

### Bucket: `serialized-field` / `serialized field` → kind `serialized_field` or `null_check` (with `key`)

Syntax: `table.column[key]` or `table.column[key=default]` — one named
key inside an already schema-declared serialized (YAML/JSON) column.
- Notes describe an existence check ("IS NOT NULL"/"existence") →
  **`null_check` with a `key`** (was this key ever set inside the blob,
  never mind its value).
- Otherwise → **`serialized_field`** (read the key's real value, with an
  optional default for when it's unset).

Example — Spree, `Promotion Item Total Eligibility` → `amountMin`:

```json
{"kind": "serialized_field", "table": "spree_promotion_rules",
 "column": "preferences", "key": "amount_min", "default": 100.0}
```

### Bucket: `direct` → kind `schema_column` (usually)

The straightforward case: the variable **is** a real column.

Example — FLEX2, `Academic Warning Status` → `cumulativeGPA`:

```json
{"kind": "schema_column", "table": "student_program", "column": "cgpa",
 "also_valid_in": [["student_semester", "cgpa"]]}
```

One safety check before accepting this at face value: if a row is
labeled `direct` but its own schema-field TEXT actually describes an
aggregate recipe (a real, surveyed FLEX2 mislabeling — `lecturesAttended`/
`lecturesHeldForOffering` are labeled `direct` but read `"COUNT(
STUDENT_ATTENDANCE) WHERE ..."`), it's re-classified as `derived_aggregate`
instead of trusted verbatim — the source label is kept as a note, not
silently "corrected" without a trace.

### Bucket: `derived` / `derived-aggregate` → 14 ordered sub-patterns

This is the richest bucket. `classify_derived` runs the ground truth's
free-text `notes`/schema-field through an **ordered list of pattern
checks** — more specific and more information-preserving first — and
whichever matches first wins. Nothing here is a general NLP parse; each
check targets one concretely-surveyed real shape.

| # | Trigger (in notes or schema field) | Resulting kind | Real example |
|---|---|---|---|
| 1 | `"COUNT via X join Y.Z"` prerequisite-gap phrasing | `derived_join_count` | FLEX2 `unmetPrerequisiteCount`: `COUNT via COURSE_PREREQ join COURSE_REGISTRATION.GRADE` |
| 2 | `AGG(TABLE) WHERE <filter>`, `TABLE (AGG WHERE <filter>)`, or `AGG(TABLE.COL) [FROM ...] WHERE <filter>` | `derived_aggregate` | FLEX2 `projectedTotalCoursesThisRegistration`: `COUNT(COURSE_REGISTRATION) WHERE ROLL_NO=<student> AND SEM_ID=<semester>` |
| 3 | `CASE_MAP: table.column: 'a'->'x', 'b'->'y', ...` | `derived_case` | FLEX2 `semesterType`: `SEMESTER.TITLE` — `'Fall'/'Spring' -> 'Regular'`, `'Summer' -> 'Summer'` |
| 4 | `RAW_SQL: <expr> TABLES: <t1,t2,...>` | `raw_sql_boolean` | FLEX2 `isElectiveTaughtByVisitingScholarUnavailableOtherwise` — a hand-written correlated SQL boolean, the escape hatch for a fact no structured shape captures |
| 5 | `"joined via TABLE.COLUMN"` + a named target pair | `join_lookup` (or `join_null_check` if existence-worded too) | OpenMRS `encounterDatetime`: joined via `orders.encounter_id` → `encounter.encounter_datetime` |
| 6 | Existence wording (`IS NOT NULL`/`IS NULL`/`existence check`) + 1+ named pairs, no "any of" wording | `null_check` (+ `negate: true` if the wording is the negative-polarity kind, e.g. "...Blank"/"IS NULL") | OpenMRS `hiAbsoluteSet`: `concept_numeric.hi_absolute IS NOT NULL` |
| 7 | Exactly 2 named pairs + `"regex"` wording | `regex_match` | OpenMRS `identifierMatchesFormat`: `patient_identifier.identifier` against `patient_identifier_type.format` |
| 8 | Exactly 1 named pair, nothing more specific matched | `schema_column` (discovered via `derived` rather than `direct`) | — |
| 9 | 2+ named pairs + `"any of"/"either"` wording | `any_not_null` | OpenMRS `anyValueFieldSet`: any of `obs.value_coded`/`value_complex`/`value_datetime`/... |
| 10 | 2+ named pairs + `"existence of"/"(existence)"/"EXISTS("/"self-join"` wording | `exists` | FLEX2 `courseOfferedInFollowingSemesters`: existence of another `COURSE_OFFER` row for this course |
| 11 | 2+ named pairs, nothing more specific | `schema_column` on the first pair (degraded — `also_valid_in` keeps the rest) | — |
| 12 | No named pairs, but a parenthesized table name (`TABLE(...)`) | `exists` with just `candidate_tables`, or with a mechanically-built `filter_text` if the parenthesized content is a real `col`/`col=value` list rather than the bare word "existence" | jBilling `hasEntitySpecificExchange`-style facts: `currency_exchange(entity_id, currency_id)` |
| 13 | Raw text is literally `"n/a"`, no columns at all | `code_external` | jBilling `expiryDate`: computed by `BasicAgeingTask`/`BusinessDayAgeingTask` application code, no single column holds it |
| 14 | Nothing matched | generic `derived` with `table_hints` (never forced into a wrong shape) | — |

## 3. The chaining layer — how ONE rule becomes SEVERAL objectives

Sometimes a variable a rule's condition needs isn't a schema fact at
all — it's the **output of another decision** (a DRD upstream link,
`informationRequirement` in the DMN XML). Two different shapes here:

- **The upstream decision is a literal-expression decision** (one FEEL
  formula, not a rule table — e.g. Spree's `Prior Completed Order
  Count`). Its formula gets parsed (or, if unparseable,
  `literal_expression_overrides.py` supplies a disclosed hand-translation)
  into a real expression tree, inlined as kind **`substituted_decision`**
  — still exactly ONE compiled record, since there's only one possible
  value.

Example — FLEX2, `Attendance Eligibility For Final Exam` →
`attendancePercentage` (its two free variables, `lecturesAttended` and
`lecturesHeldForOffering`, are each their own real `derived_aggregate`
node — omitted below for brevity, not shown as `{...}` since that isn't
valid JSON):

```json
{"kind": "substituted_decision", "substituted_from": "Attendance Percentage",
 "expression": {"op": "*",
   "left": {"op": "/",
     "left": {"kind": "variable", "ref": "lecturesAttended"},
     "right": {"kind": "variable", "ref": "lecturesHeldForOffering"}},
   "right": {"kind": "literal", "value": 100}},
 "free_variable_resolutions": {
   "lecturesAttended": "(its own derived_aggregate node, omitted here)",
   "lecturesHeldForOffering": "(its own derived_aggregate node, omitted here)"}}
```

- **The upstream decision is itself a multi-rule decision table**
  (`chained_decision_output`) — there is no single answer, because
  WHICH of the upstream table's own rules fires determines the value.
  `_grounding_options` enumerates **every rule of the upstream decision
  that could produce the needed output**, checking that rule's own
  condition (and, recursively, anything IT needs from further upstream)
  can be fully grounded. Each viable upstream rule becomes its own
  **separate compiled record** — same downstream rule, a different
  `record_id` suffix (`::via::<upstream decision>::<upstream rule>`),
  the upstream rule's own value inlined as kind
  **`literal_via_upstream_branch`**, and the upstream rule's own truth
  condition ANDed onto the downstream rule's condition (so this
  variant's own fitness function correctly requires BOTH conditions to
  hold on the same real data).

  ```
  FLEX2::Course Load Limit::Decision_CourseLoadLimit_Rule_1
    ::via::Academic Warning Status::Decision_AcademicWarningStatus_Rule_1
  FLEX2::Course Load Limit::Decision_CourseLoadLimit_Rule_1
    ::via::Academic Warning Status::Decision_AcademicWarningStatus_Rule_2
  FLEX2::Course Load Limit::Decision_CourseLoadLimit_Rule_1
    ::via::Academic Warning Status::Decision_AcademicWarningStatus_Rule_3
  ```
  **One DMN rule, three compiled objectives** — because `Academic
  Warning Status` (the upstream decision `newWarningCount`/
  `priorWarningCount` come from) has 3 rules, and any of them could be
  the one that actually fires for a given real student.

  A shared `commitment` dict prevents a real, previously-measured bug:
  if the SAME upstream decision is needed twice in one record (once
  directly, once nested inside a further chain), both occurrences are
  forced to agree on the same chosen upstream rule — otherwise one
  record could require a fact to be simultaneously `0` (from upstream
  Rule_1) and `1` (from upstream Rule_2), unsatisfiable by construction.
  This exact bug, before the fix, affected 192 of FLEX2's 391
  then-compiled records (49%).

  **This is the entire reason "compiled objectives" and "distinct DMN
  rules" aren't always the same count** — see `QUICK_REFERENCE.md`'s
  glossary. Confirmed today: FLEX2 has 9 rules that expand this way
  (98 objectives, 55 distinct rules); jBilling has 1 (40 objectives, 39
  distinct rules). OpenMRS and Spree have none of this chaining shape at
  all currently, so their objective and rule counts coincide.

  A rule blocked ONLY by an unexpandable chain (every upstream option
  fails to ground) becomes `chained_dependency_unexpandable` in
  `compile_report.json` — still honestly reported, never silently
  dropped.

## 4. From a compiled objective to real database rows

Briefly — the search/materialization side, which switches on the exact
same resolution kinds:

- **`fitness.py`'s `distance_to_true`/`evaluate_expression`** walk the
  compiled `condition` tree (and any `substituted_decision`/
  `literal_via_upstream_branch` value inline) to score a candidate
  genome — completely kind-agnostic at the leaf level (`genome[var_name]`),
  so a new resolution kind never needs a `fitness.py` change.
- **`candidate.py`'s `build_seed_candidate`** has one seeding rule per
  kind (e.g. `schema_column`/`null_check` → a placeholder row;
  `derived_aggregate`/`exists` → a real, filter-matching row when the
  filter's conjuncts are mechanically parseable; `not_persisted` → a
  scenario value) — giving the search a schema-legal starting point.
- **`mutation.py`'s M1 (field) / M2 (row-count) operators** likewise
  dispatch per kind to change a real column value or add/remove real
  rows, moving the genome toward `branch_fitness = 0`.
- **`materialize.py`** turns the winning candidate into real SQL DDL/
  INSERT — the one place a `serialized_field`'s in-memory dict becomes
  real YAML text, for example.
- **`validation_oracle/db_resolver.py`** independently re-implements the
  READ side of the exact same kind taxonomy against real SQL, never
  importing the generator's own write-side code — this is what makes
  the whole project's "verified" number mean something.

## 5. Where this mapping currently runs out — pointer, not detail

Every kind above has real, working read AND write support somewhere in
the pipeline. The current open gaps are about the WRITE side not yet
knowing how to construct certain filter shapes for `derived_aggregate`/
`exists` (most notably `COLUMN IN (SELECT ... WHERE ...)`, an
IN-subquery join), not about the classification taxonomy itself being
incomplete. See `validation_oracle/KNOWN_ISSUES.md` for the exact,
currently-open instances of this.
