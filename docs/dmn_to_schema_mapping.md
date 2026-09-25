# How DMN Variables Get Mapped to the Relational Schema

## A complete explanation of the compile-time mapping mechanism, with real numbers, real regex patterns, and a worked example

---

## 0. The two-layer design, in one paragraph

A DMN rule's condition talks about named business facts — `customerCategory`, `identifierMatchesFormat`, `attendancePercentage` — never about real tables and columns. Turning each such fact into something a search algorithm can actually read from a real database row happens in **two layers**: (1) a **human-curated ground-truth CSV**, one row per DMN variable, that traces each fact back to the real application source code that implements it and records, in a small structured vocabulary plus free-text notes, *what kind of thing* it is and *roughly where* it lives; and (2) a **mechanical classifier** (`classify_derived` in `compile_constraints.py`) that re-parses that free text with a fixed, ordered set of pattern rules into one of eleven precise, machine-executable resolution kinds — never guessing, never using an LLM or generic NLP parse, and explicitly reporting "I don't know" rather than silently assuming a shape that isn't really there.

This document explains both layers in full, with the real regex patterns used and real measured numbers from the compiled corpus (1,081 leaf variables across all four case studies).

---

## 1. Layer 1 — the ground-truth CSV

**File**: `<case_study>_dmn/provenance/variable_to_schema_mapping.csv`, one per case study (`spree_dmn/`, `openmrs_dmn/`, `flex2_dmn/`, `jbilling_dmn/`).

**Columns**: `decision(_name), variable(_name), mapping_type, schema_location, notes` (exact column names vary slightly per case study — Spree's own CSV uses `decision`/`variable` and has no separate `io` column, the other three use `decision_name`/`variable_name` with one; `load_case_study_ground_truth` normalizes over these differences).

**Where the content comes from — provenance, not guesswork.** Every row exists because a human traced the DMN fact back to the *real* application source code that computes it in the real system — a Java validator class, a Ruby model method, a SQL migration — and cites exactly where. Compiled records carry this forward as `source_citation`, e.g. `"PatientValidator L92 (size()!=1 short-circuits)"` or `"CurrencyBL.java L325-326: a currency_exchange row scoped to this entity exists -> use it"`. This is why a ground-truth error is treated as seriously as a code bug rather than an assumption to patch around: one real instance (a Spree row citing a migration that was never actually applied) was found, verified against the real schema file, and only corrected after explicit sign-off, precisely because this data is asserted to be traceable to ground truth, not inferred.

### 1.1 The `mapping_type` column — a small, deliberately coarse vocabulary

Real values actually found across all four CSVs: `direct`, `direct - exact match`, `direct - aggregate`, `direct-coded`, `derived`, `derived-aggregate`, `not-persisted`, `SCHEMA GAP`, `SCHEMA GAP (partial)`.

`normalize_mapping_type` collapses these into five buckets by substring match, most-specific first:

```
'schema gap'          -> schema_gap
'not-persisted' /
'not persisted'        -> not_persisted
'derived-aggregate' /
'derived - aggregate' /
'derived'              -> derived
'direct'               -> direct
(anything else)        -> unresolved
```

Only **`derived`** needs the full machinery in §2 below — `direct` almost always becomes a plain `schema_column` read, `not_persisted` becomes a scenario bind-parameter, and `schema_gap`/`unresolved` are flagged and excluded from the search rather than forced into a shape that isn't real.

### 1.2 A real example row (Spree)

```csv
decision,variable,mapping_type,schema_location,note
Promotion Item Total Eligibility,itemTotal,direct,spree_orders.item_total,
Effective Minimum Amount Threshold,operatorMin,SCHEMA GAP (partial),spree_promotion_rules.preferences,
  "serialized text blob (t.text ""preferences""), discriminated by type=...; no dedicated column"
Effective Minimum Amount Threshold,effectiveMinThreshold,not-persisted,n/a,
  "formula output; resolves operatorMin into one concrete number"
```

`itemTotal` is a clean, direct column read. `operatorMin` is a real, honestly-flagged schema gap — the fact genuinely exists in the real system, but only inside a serialized blob no SQL query can cleanly filter on, so it is *not* silently mapped to something wrong. `effectiveMinThreshold` is a pure computed/bind-parameter value.

---

## 2. Layer 2 — `classify_derived`: turning free text into a structured resolution

For every ground-truth row bucketed `derived`, `classify_derived(row)` runs an **ordered cascade of pattern checks** against the row's own `notes` and `schema_location` (called `raw_schema_field` internally) text. Order matters deliberately — more specific, more information-preserving checks run first, since two different signals can co-occur in the same sentence (e.g. a join-based null-check contains both "joined via" and "IS NOT NULL" language, and the join form must win because it preserves the source table a plain null-check would lose).

### 2.1 Explicit author-written escape hatches (checked first)

Three special marker syntaxes let a ground-truth author hand-specify an exact mechanism when no automatic pattern would capture it correctly — used sparingly, for genuinely bespoke facts:

- **`CASE_MAP: table.column: 'RawValue1' -> 'Category1', 'RawValue2' -> 'Category2', ...`** → kind `derived_case`. An *exhaustive* enumeration (deliberately no default/else) of which real stored value maps to which derived category. Built after a real bug: `semesterType` was first mapped as a bare passthrough of `SEMESTER.TITLE`, but the DMN rules compared it against `'Regular'`/`'Summer'` — a different two-category vocabulary than `TITLE`'s own three real values (`'Fall'/'Spring'/'Summer'`) — so the search "solved" the branch by writing the literally impossible value `TITLE = 'Regular'` into a row. `CASE_MAP` makes both directions honest: reading maps the real value forward, and mutation inverts the same table to write a real value back — an unlisted real value surfaces as an explicit "don't know how to categorize this," never a silent fallthrough.
- **`RAW_SQL: <SQL boolery template with <placeholder> substitution> TABLES: t1, t2`** → kind `raw_sql_boolean`. The one true escape hatch for a compound fact that doesn't fit any structured shape at all (e.g. FLEX2's `isElectiveTaughtByVisitingScholarUnavailableOtherwise` — "this offering's instructor is of a named type AND no *other* offering of the same course this semester has a different-typed instructor"). The template still goes through the same placeholder-substitution and prose-shape checks as every other filter text before being trusted.
- **`COUNT via TableA join TableB.column`** → kind `derived_join_count`, a narrow but real shape for "how many of *this* row's own related rows in another table fail some condition" (e.g. `unmetPrerequisiteCount`: how many of a student's own prerequisite courses they haven't yet passed). Found necessary when the generic aggregate-recipe regexes below all required a literal `AGG(...)` call and this phrasing used none.

### 2.2 Aggregate recipes — `derived_aggregate`

Three regex shapes, checked in order of specificity:

```
AGG(TABLE.COLUMN)                      -- e.g. SUM(COURSE.CREDIT_HRS)
AGG(TABLE)                             -- e.g. COUNT(STUDENT_ATTENDANCE)
TABLE(AGG ...)                         -- e.g. spree_price_adjustment_tiers (COUNT WHERE ...)
```

An optional `FROM <tables> WHERE <filter>` after the aggregate call supplies the filter — everything after `WHERE` becomes the node's own `filter_text`, later parsed mechanically into real row-matching conjuncts (§3). Without a `WHERE`, the whole table is the (unfiltered) population.

### 2.3 Join-based facts — `join_lookup` / `join_null_check`

Notes phrased as **"joined via `local_table.local_column`"** — checked *before* the plain existence check below on purpose, because a fact can be described both ways at once ("joined via orders.encounter_id; IS NOT NULL"), and the join form carries strictly more information (it names the *source* table holding the foreign key, which a bare null-check on the *target* table alone would lose — needed for correct FK-closure computation). The last schema pair named in the row becomes the joined-to `(result_table, result_column)`; if the note also contains existence language, the kind becomes `join_null_check` instead of `join_lookup`.

### 2.4 Plain column presence — `null_check`

A single schema pair plus language like **"IS NOT NULL"**, **"IS NULL"**, **"existence check"**, **"null-check"** (and *not* "any of"/"either" — that's a different, multi-column shape, §2.6) → `null_check`. When the ground truth names a second alternative real column for the same fact, it's kept as `also_valid_in` metadata rather than discarded.

### 2.5 Regex facts — `regex_match`

Exactly two schema pairs plus the word **"regex"** → `regex_match`, one column holding the value, the other holding the pattern (e.g. OpenMRS's `identifierMatchesFormat`: `patient_identifier.identifier` matched against `patient_identifier_type.format`).

### 2.6 The plain, majority case — `schema_column`

A single clean schema pair with none of the above signals → `schema_column`, the direct 1:1 read. If the notes also mention an explicit named constant (`_CONSTANT_RE`, e.g. `"constant STATUS_ACTIVE = 1"`), that's attached as `compared_to_named_constant` metadata.

### 2.7 Multi-column facts without a sharper shape

Two or more schema pairs, in order of specificity:

- **"any of" / "either" / "either populated"** → `any_not_null` (true if *any* of the named columns is set).
- **"existence of" / "(existence)" / "EXISTS(" / "self-join"** → `exists` (true if a matching row is present at all).
- Nothing more specific → falls back to `schema_column` on the first pair, recording the rest as `also_valid_in` — real column names attached beat leaving the row fully unresolved.

### 2.8 `exists` with no clean schema pair at all, but a parenthesized raw field

When ground truth names only a bare table with existence language and a parenthesized field like `"currency_exchange (entity_id, currency_id)"` or `"currency_exchange (entity_id=0, currency_id)"` — rather than the bare `"(existence)"` sentinel — the parenthesized content is parsed **token by token** into a real `filter_text`: a bare column name becomes `column = <column>` (an auto-named placeholder), `column=literal` becomes a literal-value conjunct, joined by `AND`. This reuses the *exact same* mechanical filter machinery `derived_aggregate` already has (§3), rather than a second, competing implementation. Any token that doesn't parse as a clean `col` or `col=value` shape aborts the *whole* parse — never a partial, silently-wrong filter — and falls through to a bare "does any row exist" node instead.

This specific extension exists because of a real, confirmed limitation found running jBilling: two different `exists`-kind facts on the same table (`hasEntitySpecificExchange`, `hasSystemDefaultExchange`) had no way to ever read as different booleans, despite their own ground truth clearly describing two different filters on the same table — without a real `filter_text`, `exists` degrades to a bare "does *any* row exist at all" check, and two facts with no filter on the same table are structurally identical.

### 2.9 What happens when nothing matches

If none of the above patterns fire, the row becomes a generic `derived` node carrying only table hints (never guessed further), or is classified `code_external` (the fact is genuinely computed by application code at runtime — a multi-column date computation, a UI-only transient value — never persisted as any single column the schema could ever expose) or `schema_gap`/`unresolved`. All three are **flagged and excluded from the search denominator**, never silently treated as solvable. This is a deliberate design stance: *targeted, individually-justified pattern rules over a small, human-curated vocabulary, never a general NLP parse* — a pattern that doesn't match is a real, reportable gap, not a wrong guess dressed up as an answer.

---

## 3. The mechanical filter-text parser (shared by `derived_aggregate` and `exists`)

Once a `filter_text` string exists (from either §2.2 or §2.8), it is parsed the same way everywhere by `_mechanical_filter_predicate`/`_row_from_filter_conjuncts`: split on `AND`, and keep only conjuncts of the shape `COLUMN = VALUE` or `COLUMN = <placeholder>`. Anything else — a genuine cross-table join conjunct like `PROGRAM_COURSE.COURSE_ID = COURSE.COURSE_ID`, or free prose — is reported as **skipped**, and the resulting predicate is an honest **over-count** on exactly the skipped conjuncts' account, never a silent wrong answer. (An earlier version treated a bare `TABLE.COLUMN` on the right-hand side as a literal *string* to match against, which no real integer column could ever equal — silently *zeroing* an aggregate that should have counted real rows; reporting it as skipped instead was a deliberate, measured fix.)

---

## 4. Cross-decision facts — the DRD grounding layer

A fact that is the *output* of an upstream DMN decision (`customerCategory`, the output of a "Customer Category" decision consumed by "Order Discount") is resolved differently from every kind above: `resolve_and_substitute` walks the Decision Requirements Diagram's own information-requirement edges, picks a concrete rule of the upstream decision to *ground* the reference to, and recursively inlines that upstream rule's *own* free-variable resolutions directly into the downstream record's compiled tree (kind `substituted_decision` / `chained_decision_output`). This is what makes a compiled record fully self-contained — evaluating it never needs to "trust" that some other decision was separately solved; its own genome must reproduce the upstream inputs too.

**The consistency guarantee**: a single, shared `commitment: {decision_name -> chosen_rule_id}` dictionary (`_grounding_options`, `_enumerate_needs`) is threaded through every grounding need of one record, including deeply nested ones. Once a decision is committed to a rule anywhere while grounding a record, every *other* reference to that same decision — however deeply nested — is forced to reuse the identical rule, with real backtracking when a genuinely different top-level choice needs its own independent pick. Without this, the same upstream decision referenced twice through two different paths could be grounded to two conflicting rules, pinning one variable to two different literal values at once — mathematically unsatisfiable by construction. This exact bug, found and fixed this way, dropped FLEX2's own compiled record count from 391 to 151 (192 of the 391 carried this self-contradiction).

---

## 5. What a fully compiled record looks like

After classification and grounding, every compiled record (one entry of `compiled_constraints.json`) carries: its own condition tree, a fully-resolved `variable_resolution` map (every leaf now one of the eleven kinds above, with concrete `table`/`column`/`filter_text`/`via` fields), its `hit_policy_context` (every earlier row in the same FIRST/UNIQUE table it must also suppress), its `fk_closure_tables` (every table reachable by following foreign keys outward from the tables this record touches — needed so schema repair knows the *full* neighborhood a dangling reference might need to synthesize), and its `source_citation` (the human provenance trail).

---

## 6. Real numbers from the current corpus

**Compiled objective counts** (`compile_report.json`):

| Case study | Compiled | Blocked (infeasible / unresolved / schema-gap / code-external) |
|---|---|---|
| FLEX2 | 98 | 53 |
| OpenMRS | 71 | 0 |
| Spree | 27 | 5 |
| jBilling | 40 | 15 |
| **Total** | **236** | **73** |

Blocked reasons: 55 `infeasible`, 16 `unresolved_variable`, 2 `chained_dependency_unexpandable`. Of the blocking leaves behind the `unresolved_variable` reason: 5 `schema_gap`, 6 `unresolved`, 12 `code_external` — i.e. most of *that* bucket is genuinely computed by application code at runtime, not a mapping the classifier merely failed to find. The `infeasible` reason is a separate mechanism entirely: a record whose fully-assembled condition (own cells, plus any grounded upstream branch clauses, plus hit-policy earlier-row suppression) is proven unsatisfiable by three-valued constant folding *before* it ever reaches this file at all (`_fold_condition_three_valued` in `compile_constraints.py`; see `docs/complete_approach_writeup.md` §3.2) — 53 of FLEX2's original 151 rules and 2 of jBilling's original 42, none of which the search could ever have reached regardless.

**Leaf-kind distribution across all 236 compiled records (756 total leaf variables)**:

| Kind | Count | % |
|---|---:|---:|
| `schema_column` | 393 | 52.0% |
| `literal_via_upstream_branch` | 79 | 10.4% |
| `null_check` | 72 | 9.5% |
| `derived_aggregate` | 43 | 5.7% |
| `not_persisted` | 43 | 5.7% |
| `derived_case` | 33 | 4.4% |
| `derived_join_count` | 26 | 3.4% |
| `derived` (unclassified, table hints only) | 23 | 3.0% |
| `exists` | 17 | 2.2% |
| `any_not_null` | 7 | 0.9% |
| `raw_sql_boolean` | 4 | 0.5% |
| `join_lookup` | 4 | 0.5% |
| `code_external` | 4 | 0.5% |
| `regex_match` | 3 | 0.4% |
| `substituted_decision` | 2 | 0.3% |
| `schema_gap` | 2 | 0.3% |
| `join_null_check` | 1 | 0.1% |

Roughly half of every leaf variable in the whole corpus is a plain, direct column read — which is exactly why the remaining half needed this much machinery: a system that only handled `schema_column` would have left the majority of the *interesting* facts (aggregates, existence checks, cross-decision outputs, categorical derivations) completely unaddressed. (These counts are lower than an earlier revision of this document reported — 236 compiled records/756 leaves rather than 291/1,081 — because the 55 records now correctly filtered out by the `infeasible` feasibility check no longer contribute their own leaves to this corpus at all; see the blocked-counts table above.)

---

## 7. A complete worked example

**Ground truth** (jBilling, raw): `Currency Exchange Rate Source` decision, variable `hasSystemDefaultExchange`, `mapping_type = derived`, `schema_location = "currency_exchange (entity_id=0, currency_id)"`, `notes = "Boolean derived from existence of a currency_exchange row keyed by the undocumented sentinel entity_id=0; nothing in the schema marks entity_id=0 as special."`

**Classification walk**: `notes` contains no `AGG(`/`CASE_MAP:`/`RAW_SQL:`/`COUNT via`/"joined via"/"regex" signal → falls through to §2.8 (existence language, no clean schema pair, a parenthesized raw field). The parenthesized content `entity_id=0, currency_id` splits into tokens `entity_id=0` (a literal-value conjunct) and `currency_id` (a bare column, becomes an auto-placeholder). Both tokens parse cleanly, so:

```json
{
  "kind": "exists",
  "candidate_tables": ["currency_exchange"],
  "candidate_columns": [
    {"table": "currency_exchange", "column": "entity_id"},
    {"table": "currency_exchange", "column": "currency_id"}
  ],
  "filter_text": "entity_id = 0 AND currency_id = <currency_id>",
  "raw_schema_field": "currency_exchange (entity_id=0, currency_id)"
}
```

At search time, this `filter_text` is what lets `derive_value`/`build_seed_candidate`/the M2 mutation operator all check or construct a *real, matching* `CURRENCY_EXCHANGE` row (`entity_id = 0`, `currency_id` equal to whatever the record's own scenario currently holds) — rather than the earlier, bare "does *any* row exist" check that could never tell this fact apart from its own sibling, `hasEntitySpecificExchange` (`filter_text = "entity_id = <entity_id> AND currency_id = <currency_id>"`), on the very same table.

---

## 8. Why this design, and what it deliberately does not try to do

- **A small, fixed vocabulary of ~11 resolution kinds, not a generic expression evaluator.** Every kind corresponds to a real, recurring shape actually found by surveying the whole ground-truth corpus by hand, not an abstract taxonomy designed up front.
- **Pattern rules over human-curated prose, never an LLM or generic NLP parse.** The free-text notes were written by a person who already traced the fact to real source code; the classifier's only job is to make that already-correct human judgment machine-executable, mechanically and deterministically, not to *infer* correctness from ambiguous text.
- **A pattern that doesn't match is a reported gap, never a guess.** `schema_gap`, `unresolved`, and the generic `derived` fallback all exist so that "we don't have a mechanical way to compute this" is a first-class, countable outcome — not something quietly forced into the nearest available shape.
- **Order-sensitive checks, justified individually.** Every ordering decision in the cascade (§2) exists because two signals were found, in real data, to co-occur in a way that would otherwise pick the less-informative shape — each one traced to a specific record, not a theoretical concern.
- **The same filter machinery serves two different kinds** (`derived_aggregate` and `exists`), rather than two independently-maintained parsers that could silently drift apart from each other.

---

## 9. Where the actual code lives

- `compile_constraints.py` — everything in this document: `normalize_mapping_type`, `classify_derived` and its escape-hatch extractors (`_try_extract_aggregate_recipe`, `_try_extract_case_map`, `_try_extract_raw_sql_boolean`, `_try_extract_prereq_gap_count`), `resolve_variable`/`resolve_and_substitute`/`_grounding_options` (DRD grounding and the commitment-respecting backtracking search), `fk_closure`.
- `candidate.py` — `_mechanical_filter_predicate`/`_row_from_filter_conjuncts`, the shared filter-text parser §3 describes.
- `<case_study>_dmn/provenance/variable_to_schema_mapping.csv` — the raw, human-curated ground truth for each case study.
- `compiled_constraints.json` / `compile_report.json` — the actual, current output of this whole pipeline for all four case studies.
