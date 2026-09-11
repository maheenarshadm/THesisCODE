# DMN-to-Schema Mapper (prototype)

A generic tool that takes any case study's DMN decision files plus its
schema source and automatically produces a `variable_to_schema_mapping.csv`
— the file the generator (§6 of the design doc) reads as its input, so the
manual DMN↔schema lookup step (§5.2) does not have to be repeated by hand
again. Originally built and validated 2026-09-08 against the case studies
in the project at the time (FLEX2, OpenMRS, OFBiz, PrestaShop), using
their existing 291 hand-built mapping rows as ground truth.

## Fixed 2026-09-11 — the tool was stale and, in one script, entirely broken

Checked directly against this repository rather than assumed current: this
package had fallen out of sync with two case-study swaps (OFBiz→Spree,
PrestaShop→jBilling, design doc §7e/§13.1) that happened after it was
built, and one of its three pipeline scripts didn't run at all.

- **`schema_extract.py` raised `ModuleNotFoundError` on import** — it
  pulled `parse_oracle_mysql_ddl` from a `paper_supplementary/scripts/`
  directory that does not exist anywhere in this repository. Its cached
  `schema_columns.csv` also only ever covered `FLEX2, OFBiz, OpenMRS,
  PrestaShop` — neither Spree nor jBilling, the two case studies that
  actually replaced them, appeared in it at all — and contained visibly
  corrupted rows (stray fragments like `'301'`, `)"` sitting where a
  case-study name should be) from whatever produced it.
- **`dmn_extract.py`'s `CASE_STUDY_DIRS`** pointed at a different session's
  scratchpad layout (`flex2_dmn/dmn`, `ofbiz_dmn/dmn`, ... directly under
  this script's own parent directory) — none of those paths exist here,
  and two of the four case studies they named are no longer in the active
  program regardless.
- **`validate_mapper.py`'s `GT_FILES`** hard-coded absolute paths into yet
  another session's scratchpad (`/tmp/claude-0/-home-claude/...`), again
  naming the pre-swap case-study set.
- **OpenMRS's and Spree's own DMN packages weren't in this repository at
  all** (only FLEX2's and jBilling's were) — added in a separate commit
  before this fix, validated against the design doc's current numbers
  (24 decisions/71 rules and 14 decisions/32 rules respectively) before
  this tool was pointed at them.

**What was changed**: `schema_extract.py` now reads `all_schema_extraction`'s
already-working, already-validated per-case-study JSON (FLEX2, OpenMRS,
Spree, jBilling) instead of re-parsing raw DDL itself — one documented
fidelity trade-off from this (`fk_target_table` is now a table-level,
deduplicated target list rather than a true per-column resolution) costs
nothing in practice, since `mapper.py`'s own scoring never reads that field
(grep-confirmed) — it was always carried through as documentation only.
`dmn_extract.py` and `validate_mapper.py` now point at this repo's actual
package locations and the current four-case-study set. `dmn_extract.py`'s
literal-expression identifier extraction was also hardened: it previously
only excluded `and/or/not/true/false`, which was enough for FLEX2's and
OpenMRS's plain arithmetic formulas but leaked FEEL keywords
(`if/then/else/for/in/where`), built-in function names (`count`,
`intersection`), and a `for x in ...` loop's own bound variable as if they
were real input variables once Spree's more complex FEEL (list
filters/comprehensions) was in scope — now excludes all three properly and
collapses dotted-path references (`order.customer`) to their root
identifier.

OFBiz and PrestaShop are out of scope for this tool now, matching the
current program (§13.1/§7e) — both are backup case studies, and neither
has a schema JSON in `all_schema_extraction/` to read from; re-adding them
would mean writing new parsers, not just repointing this one.

**Re-validated end to end** (`schema_extract.py` → `dmn_extract.py` →
`mapper.py` → `validate_mapper.py`), against the current, correct ground
truth (274 rows across the current four case studies' own
`variable_to_schema_mapping.csv` files):

| Case study | Not-persisted accuracy | Top-1 (of grounded) | Top-3 hit rate | Derived-fact recall |
|---|---|---|---|---|
| FLEX2 | 100.0% (n=4) | 17.2% (n=29) | 37.9% | 39.1% (n=23) |
| OpenMRS | 100.0% (n=41) | 42.4% (n=66) | 69.7% | 11.8% (n=34) |
| jBilling | 89.7% (n=29) | 21.4% (n=28) | 50.0% | 3.2% (n=31) |
| Spree | 88.9% (n=9) | 29.2% (n=24) | 45.8% | 38.5% (n=13) |
| **Overall** | **95.2% (n=83)** | **31.3% (n=147)** | **55.8%** | **18.8% (n=101)** |

Same broad shape as the original pre-swap numbers (89.0%/31.6%/53.1%/24.5%)
— the headline "not-persisted detection is strong, top-1 alone isn't
trustworthy unattended, top-3 is the more honest usefulness measure,
derived-fact recall is the weakest link" reading from §5.5 of the design
doc still holds, now computed against the case studies actually in the
program rather than the retired ones.

**A residual, bounded extraction mismatch, left as documented rather than
chased further**: `dmn_extract.py` and each case study's hand-built ground
truth disagree on a small number of rows (OpenMRS: 5; Spree: 5 one way,
8 the other; `validate_mapper.py` reports these as `unmatch` and simply
excludes them from every metric above, rather than silently mis-scoring
them). Two distinct, inspected causes, neither an extractor bug:
1. **DRD-substitution pseudo-inputs** (OpenMRS's 5, one of Spree's) — a
   downstream literal-expression decision's FEEL text references an
   upstream COLLECT decision's own output (e.g. `count(violationReasons) =
   0`); the extractor correctly reports `violationReasons` as a free
   identifier, but the hand-built mapping CSV doesn't re-list it under the
   downstream decision since it already has its own row under the
   decision that actually produces it. Same category the FLEX2 README
   already documents for `Attendance Percentage`.
2. **A handful of Spree literal-expression decisions have no `<variable
   name=...>` element in the DMN XML at all** (confirmed by direct
   inspection, e.g. `Customer Group Match Count`) — the hand-built mapping
   CSV documents a conceptual output name (`matchingCustomerGroupCount`,
   `effectiveMaxThreshold`, ...) that simply isn't discoverable from the
   XML by any extractor, since it was never written into it. A genuine gap
   in that package's own authoring, not something to paper over here.

## Pipeline

```
schema source (DDL / Liquibase XML / OFBiz entitydef XML)
        │  schema_extract.py
        ▼
schema_columns.csv   (case_study, table, column, sql_type, abstract_type,
                       nullable, is_pk, fk_target_table, fk_target_column)

DMN files (.dmn)
        │  dmn_extract.py
        ▼
dmn_variables.csv    (case_study, dmn_file, decision_name, io,
                       variable_name, feel_type, literal_values, label)

        │  mapper.py  (candidate generation + confidence scoring)
        ▼
mapping_auto.csv     (predicted_table, predicted_column, confidence,
                       predicted_mapping_type, top3_candidates)

        │  validate_mapper.py (against the 4 hand-built ground-truth CSVs)
        ▼
accuracy report
```

Each stage is a separate, re-runnable script and a separate CSV, exactly
the same shape as the manual process's own inputs/outputs (§5.2 of the
design doc) — nothing about the generator's downstream contract changes.

## `schema_extract.py`

Normalizes all four schema sources into one unified column-level table.
Reuses the existing `paper_supplementary/scripts` parsers' table-block/
changeSet-replay logic (imported, not reimplemented) and adds the
column-level detail (name, type, nullable, PK, FK target) those parsers
didn't originally need. `abstract_type` collapses every source's native
typing (Oracle `NUMBER`, MySQL `TINYINT(1)`, Liquibase `datetime(0)`, OFBiz
field-type-names like `indicator`/`very-long`) into the same four-way
vocabulary (`number`/`string`/`date`/`boolean`) `build_taxonomy.py` already
uses, so it plugs straight into the scoring step. One case-study-specific
normalization was needed and is called out in the code: PrestaShop's
install DDL uses a literal `PREFIX_` placeholder for the table prefix
(substituted by the installer at deploy time), stripped so table names
match the logical names used everywhere else in the project.

10,599 columns extracted across the four schemas (FLEX2 2,081; OpenMRS
1,539; OFBiz 5,387; PrestaShop 1,592).

## `dmn_extract.py`

Parses every `.dmn` file into one row per input/output variable: variable
name, declared FEEL type, and — for categorical inputs — the union of every
quoted-string literal that appears in that column's unary tests across all
rules (a proxy for an enumeration when the DMN has no explicit
`<inputValues>` element). Also handles the one literal-expression decision
in the program (FLEX2's `Attendance Percentage`), whose "inputs" are free
identifiers inside a FEEL formula rather than declared `<input>` elements.

291 variable rows extracted, matching the 291 rows across the four
hand-built mapping CSVs exactly (59/101/56/75).

## `mapper.py` — the actual matching logic

For every DMN variable, scores every column in that case study's schema and
keeps the top 3. The score combines:

1. **Token similarity** — Jaccard overlap on camelCase/snake_case-tokenized
   words, plus a raw string sequence-ratio, so `attendancePercentage` and
   `attendance_percentage`-shaped columns score well even with zero
   substring overlap in their original casing.
2. **Type compatibility** — a soft gate: a DMN `number` input against a
   schema `date` column is heavily discounted (×0.35), not eliminated,
   because both sides' typing is itself heuristic (§ schema_extract.py's
   OFBiz field-type mapping in particular is a naming convention, not a
   real type system).
3. **Enum-name bonus** — a small bonus when a categorical DMN variable is
   matched against a column whose own name looks status/type/flag-shaped.
   This is a naming heuristic only: none of the four schemas ship seed
   data, so there is no way to check a candidate column's *actual* stored
   values against the DMN's declared value list (§10 of the design doc
   already flags this as an open, unresolved gap for all four case
   studies).
4. **Decision-context bonus** — a small bonus when a word from the decision
   name / DMN file name also appears in the candidate table's name.

**Never a forced single guess.** Below `CONFIDENCE_THRESHOLD` (0.45), the
row is marked `needs review (no confident match)` rather than committing to
the highest-scoring candidate regardless of how weak it is — the same
principle the manual process used ("no match" is a valid, informative
outcome, not a failure, §5.2 step 5). A variable whose name itself suggests
a derived fact (contains `count`, `percentage`, `ratio`, `total`, `exists`,
`cumulative`, etc.) is flagged `derived` / `likely derived` instead of a
column match, since these are the cases §5.1 already documents as needing a
formula, not a single column, regardless of how well any one column scores.
Every DMN **output** variable defaults to `not-persisted`, since the large
majority of outputs in this program are decision verdicts/control-flow
values (§7b: 6/291 variables are write-back targets, the rest are
not-persisted by design).

## Validation against the 291 hand-built ground-truth rows *(superseded 2026-09-11 — see the table near the top of this README for the current, correct numbers against the current four case studies)*

Kept below as the historical record of the original 2026-09-08 validation
run, against the case-study set active at the time (FLEX2, OpenMRS, OFBiz,
PrestaShop). `validate_mapper.py` compares `mapping_auto.csv` against all four existing
`variable_to_schema_mapping.csv` files (parsing each one's free-text 5th
column for `table.column`-shaped references as the ground truth).

| Case study | Not-persisted classification accuracy | Top-1 exact match (of grounded vars) | Top-3 hit rate | Derived-fact detection recall |
|---|---|---|---|---|
| FLEX2 | 100.0% (n=4) | 13.8% (n=29) | 37.9% | 25.0% (n=24) |
| OpenMRS | 100.0% (n=35) | 45.5% (n=66) | 77.3% | 13.3% (n=30) |
| OFBiz | 78.9% (n=19) | 14.7% (n=34) | 23.5% | 25.0% (n=20) |
| PrestaShop | 79.2% (n=24) | 35.4% (n=48) | 50.0% | 35.7% (n=28) |
| **Overall** | **89.0% (n=82)** | **31.6% (n=177)** | **53.1%** | **24.5% (n=102)** |

**What this means in practice, honestly stated:**

- **Not-persisted/schema-gap detection is the strongest result (89%)** —
  the tool is reliably good at recognizing when a DMN output or a
  service-parameter input has no schema target at all, which is exactly
  the paper's own empirical finding (§4.4/§7b) about how common this is.
- **Top-1 exact-match accuracy (31.6% overall) is far from good enough to
  trust unattended.** This is not a surprise — it is a direct, quantified
  confirmation of §5.1's own claimed difficulty: FLEX2's business-analyst
  variable names were *deliberately* chosen to have little string
  similarity to its abbreviated legacy column names, and FLEX2 scores the
  **worst** of the four case studies (13.8%) for exactly that reason. This
  is a finding worth reporting in the paper in its own right, not just a
  tool limitation: automated schema matching struggles precisely where the
  paper already argued naming-convention mismatch is the core difficulty.
- **Top-3 hit rate (53.1%) is the more honest measure of usefulness** — it
  says that, roughly half the time, a human reviewer doesn't need to
  search the schema at all, just pick from 3 pre-ranked candidates instead
  of a cold search across hundreds to thousands of columns. That is a real
  time-saving even though it is not "input to the generator with no human
  in the loop."
- **Derived-fact detection recall is weak (24.5%)** — the keyword-based
  heuristic only catches variable names that literally contain a word like
  "count" or "ratio"; many genuinely derived/aggregate facts in this
  program (e.g. anything phrased as a plain adjective, `isEligible`,
  `hasCompleted`) don't announce themselves lexically. This is the
  component most worth replacing with something smarter (an LLM pass, or a
  classifier trained on the 102 known derived examples across the four
  ground-truth files) before this tool could actually replace the manual
  step end-to-end.

**Bottom line for the "no more manual DMN↔schema mapping before
generation" goal stated at the start of this task**: not yet, on its own.
This prototype is a genuinely useful *first pass* — reliable schema-gap
detection, and a shortlist that contains the right answer about half the
time — but at 31.6% top-1 accuracy it cannot be trusted to feed the
generator unattended without a human (or LLM, §5.4) reviewing every row
below the confidence threshold, which is the majority of grounded
variables. The realistic framing for the paper is: **automation collapses
most of the manual search space (from "every column in the schema" to "the
top 3, or a flagged not-persisted/derived case"), but does not yet remove
the human-in-the-loop step entirely.**

## Regenerating

```bash
cd mapper
python3 schema_extract.py --out schema_columns.csv
python3 dmn_extract.py --out dmn_variables.csv
python3 mapper.py --schema schema_columns.csv --dmn dmn_variables.csv --out mapping_auto.csv
python3 validate_mapper.py --auto mapping_auto.csv
```

## Known limitations / next steps

- **No seed data for any of the four schemas** (design doc §10) means the
  enum-value-matching signal (§5.3 step 4) could never be implemented as
  designed — it degraded to a naming heuristic (does the column look
  enum-shaped) rather than an actual value-set comparison. This is the
  single biggest reason top-1 accuracy is capped where it is; it would
  improve meaningfully with even one seed/test dataset per case study.
- **(No longer applicable — OFBiz is out of scope, §7e/§13.1)** OFBiz's
  field-type → abstract-type mapping was a naming-convention heuristic, not
  a real type system read from a DDL; kept as a historical note only since
  OFBiz isn't part of the active four-case-study program this tool now
  targets.
- **The derived-fact heuristic is a fixed keyword list.** Per §5.4, the
  natural next step is an LLM-assisted second pass — restricted to the
  rows this tool already marked `needs review`/`likely derived`, choosing
  only among the pre-generated top-3 candidates (never inventing a column
  name), majority-voted across repeated calls — evaluated against the same
  274-row ground truth this prototype is now validated against.
- **Multi-column/join/aggregate facts are only flagged, never resolved.**
  This tool intentionally does not attempt to construct a join path or
  aggregate formula automatically — §7b's construct taxonomy shows this
  would need to handle at least 6 structurally distinct construct types
  (join, aggregate, existence, global-config-lookup, arithmetic-of-derived,
  row-ordering), which is a separate, larger design problem from candidate
  column matching.
