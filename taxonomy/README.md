# DMN-to-SQL/DDL Construct Taxonomy (design doc §7b) — rebuilt 2026-09-11

## Why this needed rebuilding, not just re-running

The design doc's §7b describes a `taxonomy/` directory (`extract_structure.py`,
`classify_constructs.py`, `rule_taxonomy.csv`, `dmn_to_ddl_construct_taxonomy.md`)
as already built and delivered. **None of it exists anywhere in this
repository** — confirmed by an exhaustive search, not assumed. Same root
cause as the OpenMRS/Spree DMN packages gap found and fixed earlier this
program: apparently produced in a prior session's context and never
actually committed here.

The specific 17-category table quoted from that prior write-up is, on top
of that, *already* stale on content grounds even if it had survived: it
sums to 291 rows and names PrestaShop-specific constructs (`specific_price`
/`tax_rule` precedence, the `idShop` vs `"0, contextShopId"` FEEL-list
pattern) — predating both the PrestaShop→jBilling swap (§7e) and the
OFBiz→Spree swap (§13.1). Two case-study swaps have happened since that
table was current.

**This is a rebuild, not a byte-for-byte reproduction of the lost
original.** Its category boundaries are freshly designed and documented
below, not reverse-engineered to hit unrecoverable numbers.

## What's different (and better) about this version

The original, per the design doc's own description, was built by
rule-based classification of `variable_to_schema_mapping.csv`'s free-text
notes alone. This version does that (via `generator/compile_constraints.py`'s
own `resolve_variable`/`classify_derived` — **reused directly, not
reimplemented**, so there is exactly one source of truth for "how is this
variable resolved" across the whole program, and this taxonomy can never
silently drift from what the compiler itself believes), *and* separately
tags every compiled branch's actual **parsed FEEL condition tree**
(`generator/compiled_constraints.json`) for usage-shape questions — is
this compared to another variable? a set-membership test? a range test? —
that free-text notes could only ever be guessed at. The FEEL parser
those trees come from is validated at 100% coverage against every real
condition in the program (`generator/feel_parser.py`), so this half of
the taxonomy is measured, not inferred.

## Storage-shape taxonomy (`construct_taxonomy.csv`) — one row per ground-truth variable

Computed over the current, correct 274-row ground truth across all four
current case studies (FLEX2, OpenMRS, Spree, jBilling — matches §13.5's
own total exactly, and its Not-Persisted/Schema-Gap percentages exactly,
since both are computed from the same source data).

**Updated 2026-09-11, three times.** A first pass moved `semesterType`
from category 8 (`Compound / Unclassified Derivation`) to category 5
(`Schema Gap`), reasoning from DDL evidence alone that FLEX2's schema
had no semester-type column anywhere. **That conclusion was wrong** —
the project owner's own domain knowledge confirmed `SEMESTER.TITLE` *is*
the semester-type field (a clean 3-value categorical column:
`Fall`/`Spring`/`Summer`, not free text), something no amount of
DDL-only inspection could have settled either way; `semesterType` moved
to category 1 (`Direct Attribute Reference`). A third pass, after the
project owner asked for the closest table for every other `Schema Gap`
row, resolved two more (`degreeMinimumCreditHours` → category 1,
`degreeTotalCredits` → category 6 as a real `SUM` aggregate,
`isElectiveTaughtByVisitingScholarUnavailableOtherwise` → category 7 as
a compound join+`NOT EXISTS` check) the same way. See
`generator/README.md`'s "Two ground-truth fixes, one of them corrected"
and "A third round" sections for the full sequence, including the wrong
conclusions along the way, not just the corrections.

| # | Category | Count | % | What it means | SQL/DDL construct a translator would emit |
|---|---|---|---|---|---|
| 1 | **Direct Attribute Reference** | 93 | 33.9% | The DMN input variable *is* a column value, untransformed. | Plain column reference / `SELECT column`. |
| 2 | **Not-Persisted** | 82 | 29.9% | A decision's own output/verdict — never meant to be stored (§ "what is not persisted" from an earlier session). | None — by design, not a gap. |
| 3 | **Single-Column Predicate** | 28 | 10.2% | An existence check (`IS NOT NULL`) or a comparison against a named constant, over one real column. | `WHERE column IS NOT NULL`, `column = <constant>`. |
| 4 | **Decision Output / Write-Back Target** | 12 | 4.4% | An *output* variable that genuinely gets written back to a column (e.g. FLEX2's `newWarningCount` → `STUDENT_PROGRAM.WARNING`) — the opposite direction from category 1. | `INSERT`/`UPDATE` target, not a `SELECT`-side construct. |
| 5 | **Schema Gap** | 10 | 3.6% | The fact has no column anywhere in the schema — not unenforced, structurally absent. | None — the genuine "cannot translate" case. |
| 6 | **Aggregate Function** | 10 | 3.6% | A `COUNT`/`SUM`-style aggregate over related rows. | `COUNT(*)`/`SUM(...)` with `GROUP BY` or a scalar subquery. |
| 7 | **Existence / Correlated Subquery** | 9 | 3.3% | "Does at least one related row satisfy X" — including existence reached by following one FK first, and a compound join+`NOT EXISTS` check (the new `raw_sql_boolean` resolution kind). | `EXISTS (SELECT 1 FROM ... WHERE ...)`, or a hand-worked-out correlated `NOT EXISTS`. |
| 8 | **Compound / Unclassified Derivation** | 18 | 6.6% | The catch-all: a real derived fact whose free text didn't match any of this taxonomy's mechanical patterns — needs a human (or a future, more targeted pass) to turn into a concrete recipe. | Not determinable from this taxonomy alone. |
| 9 | **Cross-Table Join** | 4 | 1.5% | The fact lives on a different table, reached by walking one named FK. | `INNER/LEFT JOIN`. |
| 10 | **Multi-Column Existence (any-of)** | 2 | 0.7% | An OR-of-existence-checks across several named columns (e.g. "customer or email present"). | `WHERE col_a IS NOT NULL OR col_b IS NOT NULL`. |
| 11 | **Code-External (no schema representation)** | 5 | 1.8% | Genuinely computed by application code — a Java constant, a UI-only transient value, a runtime-only calculation — never a column at all, not even an unenforced one. New category; the original taxonomy's design didn't need it since it predates this finding (§13.11). | None — but for a reason distinct from Schema Gap: this was never meant to be a column, vs. Schema Gap's "should be a column, isn't." |
| 12 | **Pattern/Regex Match** | 1 | 0.4% | Format validation against a regex stored in another column. | Not portable SQL — an engine-specific `REGEXP` operator, or pushed to the application layer. |
| — | **Chained Decision Output** | 0 | 0.0% | See "Known limitation" below — genuinely present in the program (9 occurrences, `generator/compile_report.json`), just invisible from this taxonomy's per-ground-truth-row view. | — |

## Usage-shape taxonomy (`usage_shapes.csv`) — one row per compiled branch's condition

A genuinely new axis the original design doc's own §7b never had access
to, since it requires the parsed condition trees this program didn't have
until `generator/compile_constraints.py` was built:

| Usage shape | Count | % of 242 compiled branches |
|---|---|---|
| Plain single comparison | 149 | 61.6% |
| Cross-variable comparison (right-hand side is another variable, not a literal) | 59 | 24.4% |
| Negation (`not(...)`) | 55 | 22.7% |
| Set-membership (`IN (...)`) | 9 | 3.7% |

(These are close to the original chained-decision-output-expansion
figures, confirmed to have survived both the `semesterType` correction
and the third round's own fixes intact — the 3 newly-compiled FLEX2
branches (`degreeMinimumCreditHours`/`degreeTotalCredits`/visiting-
scholar facts) added a small amount to the plain/cross-variable/negation
counts without changing the overall shape. A first, mistaken fix to
`semesterType` had briefly removed the chained-expansion variants —
dropping negation's share back to 8.2% — but that fix was wrong, per
`generator/README.md`'s "Two ground-truth fixes, one of them corrected"
section, and correcting it brought this table back to its pre-mistake
state. Negation's ~23% share reflects a real, understood construct: every expanded record's compound
condition literally encodes its upstream rule's FIRST/UNIQUE hit-policy
suppression as `{"op": "not", ...}` clauses — "this upstream rule fires
AND NOT any earlier upstream rule" — not classifier drift.)

The cross-variable share (24.4%) is consistent with — in the same range
as — the design doc's own program-wide estimate of ~17–19% of decisions
using this pattern (§7a/§13.4), a useful independent cross-check from a
completely different measurement method (parsed condition trees vs.
manual decision-level counting).

## Known limitation: "Chained Decision Output" reads as zero here

This is real and not a bug, and still true after `generator/`'s
chained-decision-output resolution pass (2026-09-11): this taxonomy
classifies each ground-truth row using `resolve_variable` directly, keyed
only by that row's own `(decision_name, variable_name)` — the same call
`compile_constraints.py` makes for a decision's *own* declared inputs.
`chained_decision_output` is a property of the *resolution walk*
(`resolve_and_substitute`, DRD-aware), not of a row in isolation; it only
shows up when `compile_constraints.py` is actually resolving a specific
branch's dependency, with that branch's own DRD edges in view.

**Note this no longer means every dependency is unresolved, though** —
`generator/compile_constraints.py`'s `enumerate_upstream_groundings`
(added 2026-09-11) expands such a dependency into several fully
self-contained compiled records (one per upstream branch that could
produce the needed value) whenever at least one upstream branch actually
resolves. Of the original 9 occurrences, **7 are successfully expanded
(56 new records)**, and **2 remain genuinely blocked**: jBilling's
`Ageing Step Advancement` (its own upstream dependency is itself
`code_external`, a true dead end).

A same-day ground-truth fix to `semesterType` briefly took one of the 7
back to blocked, by reclassifying it `schema_gap` on DDL evidence alone
(no dedicated semester-type column found anywhere in the schema). That
reclassification was **wrong** — corrected once the project owner's own
domain knowledge confirmed `SEMESTER.TITLE` really is the semester-type
field (a clean 3-value categorical column), which the DDL alone could
never settle either way. With the correction applied, `Course Load
Limit` compiles again and `Course Registration Eligibility`'s expanded
variants are restored, back to the 7-expanded/2-blocked figures above.
See `generator/README.md`'s "Two ground-truth fixes, one of them
corrected" section for the full sequence, including the wrong
conclusion. Measuring the program's real chained-dependency structure
and its resolution means reading `generator/compile_report.json` and
`generator/README.md`'s "Chained decision output" section, not this
file.

## Regenerating

```bash
cd taxonomy
python3 build_construct_taxonomy.py --out-dir .
```

Depends on `generator/compiled_constraints.json` already being current
(regenerate that first via `generator/compile_constraints.py` if the DMN
files or ground-truth mapping CSVs changed) and reuses
`generator/compile_constraints.py`'s and
`dmn_schema_mapper/mapper/validate_mapper.py`'s own code directly rather
than re-implementing any classification or ground-truth-loading logic.
