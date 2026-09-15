# OpenMRS — DMN business rules (second case study, Tier-2 code-mined)

This is the second case study's worth of DMN decision models for the
research paper. Unlike FLEX2 (drafted from an official Academic Rules PDF —
**Tier 1** sourcing), OpenMRS has no equivalent business-rules policy
document, so every rule here is **mined directly from openmrs-core's real
validator source code** on GitHub (`openmrs/openmrs-core@master`,
`api/src/main/java/org/openmrs/validator/`) — **Tier 2** sourcing, per the
project's established provenance framework. Every decision cites the exact
`.java` file and line range it was read from, the same way FLEX2's rules
cite policy clause numbers and PDF page numbers.

Schema grounding is against OpenMRS's own Liquibase schema definition
(`schemas/openmrs/liquibase-schema-only-2.9.x.xml` and
`liquibase-update-to-latest-3.0.x.xml`), the same schema files used in this
project's earlier per-case-study table/constraint count.

## Revision: FIRST → COLLECT for 5 decisions (2026-09-10)

**Trigger.** While auditing Spree's `Price Adjustment Tier Validity` for the same
FIRST-vs-COLLECT question, the project's own earlier documented stance on OpenMRS was
revisited: this package's original README stated that several decisions "collapse what
the source implements as multiple independent `if` statements ... into one FIRST-hit
verdict + single reason code ... at the cost of a more complex downstream fitness
function." The user chose to apply COLLECT to both Spree and OpenMRS for consistency
rather than leave that collapsing undocumented as a permanent modeling choice.

**Verification method.** Rather than trust the original summary, all candidate
decisions were re-checked against the **live openmrs-core `master` source**
(`PersonValidator.java`, `OrderValidator.java`, `PatientProgramValidator.java`,
`RelationshipValidator.java`, `EncounterValidator.java`, `ConceptValidator.java`,
`PatientValidator.java`, `PatientIdentifierValidator.java`, `ObsValidator.java`
fetched fresh 2026-09-10) for the specific property that matters: does the method have
an early `return` between its `errors.rejectValue()`/`errors.reject()` calls (single
violation only, by construction), or do independent checks run unconditionally one
after another (multiple violations genuinely possible on the same object)?

**5 decisions confirmed as genuine COLLECT candidates** (independent checks, no early
return, real co-occurrence possible):

| Decision | Independent checks that can co-fire | Verified against |
|---|---|---|
| Death Date Consistency | future-date, before-birthdate | `PersonValidator.validateDeathDate` (no return between the two `rejectIfFutureDate`/`rejectDeathDateIfBeforeBirthDate` calls) |
| Order Date Activated Consistency | after-date-stopped, after-auto-expire, encounter-after-activated (the future-date check itself still short-circuits these three, confirmed by its own `return`) | `OrderValidator.validateDateActivated` |
| Program Enrollment Date Consistency | enrolled-date-future, completed-date-future, completed-before-enrolled | `PatientProgramValidator.validate` |
| Relationship Date Validity | end-before-start, start-in-future | `RelationshipValidator.validate` |
| Encounter Datetime Validity | visit/patient mismatch, datetime-future, before-visit-start, after-visit-stop | `EncounterValidator.validate` |

**14 decisions confirmed NOT to need COLLECT**, kept as FIRST/UNIQUE, each verified
rather than assumed — the two disqualifying reasons found:
- **Explicit early return / thrown exception between checks** (genuinely single-violation
  by construction): `Patient State Date Validity` (`return` after every `rejectValue`
  in its per-state loop), `Identifier Location Requirement` and `Identifier Uniqueness
  Check` (both throw an exception immediately — Java `throw` halts execution, so a
  second violation can never even be reached), `Identifier Format And Check-Digit
  Validity` (format check throws before the check-digit check ever runs).
- **Arithmetically/logically mutually exclusive despite no early return**: `Birthdate
  Validity` (a date can't simultaneously be in the future and >140 years in the past),
  `Order Scheduled Date Urgency Consistency` (the two conditions require
  `urgencyIsOnScheduledDate` to be both true and false), `Numeric Absolute Range
  Validity` (a value can't exceed the high bound and fall below the low bound at once,
  absent a misconfigured inverted range, which this decision isn't modeling),
  `Concept Preferred Name Validity` and `Death Record Consistency` (both genuine
  `if`/`else if` chains in the source, mutually exclusive by Java's own control flow).

**The redesign pattern**, applied identically to all 5 (mirroring Spree's `Price
Adjustment Tier Validity` split): each decision became two —
- `<Decision Name> Violations` — COLLECT hit policy, one output column
  (`violationReasons`), one rule per independent check, no wildcard row (an empty
  match list is exactly "no violations found").
- `<Decision Name>` — a small literal-expression decision downstream
  (`count(violationReasons) = 0`), replacing the boolean/reason-code output pair the
  original FIRST table had.

**What this changes about the program's numbers.** Decision count rose from 19 to
**24** (5 new downstream verdict decisions), rule-row count from 85 to **75**
table rule rows (fewer rows overall, since COLLECT drops the wildcard/wrap-up rows
FIRST needed, even though 5 decisions became 10). §7a's hit-policy taxonomy now has a
third category (COLLECT) for this case study, matching Spree's — the project-wide
FIRST/UNIQUE-only statistics (e.g. "48/58 tables, 82.8%, are FIRST") need to be
recomputed once both case studies' changes are final, per the earlier explicit decision
to hold off on that recomputation until now.

**Faithfulness gain, stated plainly.** The old FIRST tables could only ever report one
reason per invalid record, even when the real OpenMRS validator would report several
simultaneously (e.g. a relationship whose start date is both after its end date and in
the future gets **two** rejected fields in real OpenMRS, not one). The new COLLECT
tables report all of them, matching Spring's `Errors` object accumulation semantics
that the original Java code actually relies on.

## Revision: boolean-reduction pass, pushed harder using Spree-derived techniques (2026-09-10)

**Trigger.** After redesigning Spree's decisions to expose real FEEL comparisons
instead of pre-collapsed booleans, the same question was asked of this package: does
it hold here too? It did, more so — **59 of 64 decision-table inputs (92.2%) were
boolean**, and **14 of 19 decision tables (73.7%) were 100% boolean-input**, including
every single date/number comparison in the package. This package predates the
FEEL-promotion revision documented elsewhere in the project (`openmrs_dmn_revised.zip`,
§7c of the design doc) — that revision was applied to a different file this session
never had access to, so this pass effectively redoes that work from scratch, using
techniques developed since (Spree's upstream-threshold-resolution and count-instead-of-
EXISTS patterns) that weren't available at the time of the original revision.

**Method: audit every decision, convert only genuine pre-collapsed comparisons.**
Every boolean input across all 19 decisions was individually checked against the real
source (already re-fetched for the COLLECT audit above) and classified into one of two
buckets:
- **Convert**: the boolean stands in for a real column-vs-column or column-vs-now()
  comparison that FEEL can express directly — expose the real column(s) and let the
  rule's unary test do the comparison.
- **Keep boolean, documented**: a genuine real boolean column (e.g. `person.dead`), an
  existence/null check, a regex match, code-only arithmetic with no relational
  representation (check-digit, fractional-part), or a Java `if`/`else if` chain that's
  already mutually exclusive by construction — the same exception categories this
  project already established for the original FEEL-promotion revision.

**11 decisions converted, 8 left boolean with a documented reason each:**

| Kept boolean, unchanged | Why |
|---|---|
| Death Record Consistency | `dead` is a real boolean column; the other two are existence checks |
| Identifier Location Requirement | `locationSet` is an existence check; `locationBehavior` was already a real enum |
| Identifier Uniqueness Check | Both booleans are EXISTS/JOIN facts (`isIdentifierInUseByAnotherPatient`, a duplicate-scan loop) |
| Identifier Format And Check-Digit Validity | Existence checks, a regex match, and check-digit arithmetic with zero relational representation -- all previously documented exceptions |
| Obs Value Required By Datatype | `isObsGroup` is an existence-shaped fact; `conceptDatatype` was already a real enum |
| Obs Group Value Exclusivity | `anyValueFieldSet` is a documented OR-of-seven-existence-checks exception |
| Numeric Precision Validity | `valueNumericHasFraction` is a documented FEEL-modulo-inexpressibility exception |
| Concept Preferred Name Validity | All four are a real column or genuine category/tag-membership facts inside an `if`/`else if` chain, already mutually exclusive |

**11 decisions converted** (real column(s) exposed, real FEEL comparison written):
`Birthdate Validity`, `Death Date Consistency Violations`, `Preferred Identifier
Requirement` (boolean → `COUNT(...) >= 1`, the same count-instead-of-EXISTS pattern
used for Spree's `Customer Group Match Count`), `Numeric Absolute Range Validity`,
`Numeric Interpretation Classification` (now a clean single-column FIRST-hit threshold
ladder, directly mirroring Spree's `Promotion Tiered Percent Discount Selection`),
`Order Date Activated Consistency Violations`, `Order Scheduled Date Urgency
Consistency` (boolean → categorical `= "ON_SCHEDULED_DATE"` test), `Program Enrollment
Date Consistency Violations`, `Patient State Date Validity`, `Relationship Date
Validity Violations`, `Encounter Datetime Validity Violations` (including one
comparison converted to a genuine cross-table ID-equality test, `encounterPatientId
!= visitPatientId`, rather than a pre-computed mismatch flag).

**A correctness fix found along the way, not just a readability one.** While
converting `Patient State Date Validity`, the original 3-rule table was checked for
completeness against its 3 boolean inputs and found to have a genuine gap: the
combination `startDateSet=true, endDateSet=true, endDateBeforeStartDate=true` (the
single most common real-world invalid case: both dates present, end before start)
matched **no rule at all** in the original table. This was silently incomplete, not
merely hard to read. The redesign's rule set covers it explicitly.

**Result:**

| Metric | Before this pass | After |
|---|---|---|
| Boolean decision-table inputs | 59/64 (92.2%) | **34/73 (46.6%)** |
| All-boolean decision tables | 14/19 (73.7%) | **5/19 (26.3%)** |

Every remaining boolean is one of the 8 documented-exception decisions above, or a
genuine existence/gate check inside a converted decision (e.g. `dateCompletedSet`
still gates whether `Program Enrollment Date Consistency Violations`' completion-date
checks apply at all) -- none is a silently-left pre-collapsed comparison.

**Validated, not just asserted**: all 6 files re-checked for XML well-formedness and
per-rule input/output arity (clean), plus an exact 1:1 cross-check between every
`(decision, variable)` pair in the regenerated DMN XML and the regenerated
`variable_to_schema_mapping.csv` (109 rows) -- zero orphans in either direction, the
same validation standard this project already applies to every other case study.

## Removal: check-digit validation (2026-09-10)

On re-auditing all 24 decisions for genuine zero-relational-representation content
(distinct from the milder "real column, awkward to express in FEEL" exceptions
catalogued above), **check-digit validation was the one confirmed case** and was
removed on direct instruction.

`patient_identifier_type.validator` stores only the check-digit algorithm's **class
name** (e.g. `"LuhnIdentifierValidator"`) — the algorithm itself
(`checkIdentifierAgainstValidator`, `PatientIdentifierValidator.java` L221-247) is
Java code with no relational representation at all. This is different in kind from
every other documented boolean exception in this package: `identifierMatchesFormat`'s
underlying format string, `valueNumericHasFraction`'s underlying numeric value, and
`anyValueFieldSet`'s seven underlying value columns are all real, persisted columns —
only the *operation* on them is awkward in FEEL/SQL. Check-digit validation has no
underlying column to point to for the algorithm itself, only for which algorithm to
run.

**Trimmed, not deleted** — following the FLEX2 Revision-2 precedent (partial trim:
keep the decision, drop the unmappable rule/input, keep the mappable remainder).
`Decision_IdentifierFormatAndCheckDigitValidity` → renamed `Identifier Format
Validity`, `validatorSet`/`checkDigitValid` inputs removed, rules collapsed from 8 to
4 (format-blank / format-mismatch / format-match / no-format-configured — all fully
groundable against real columns). The decision's `id` was kept unchanged so existing
citations/DRD edges elsewhing aren't broken by the rename.

**This removal is itself a finding worth keeping visible, not one to erase quietly**:
it was previously this package's clearest illustration of the design doc's §4.4
thesis (a real business rule can have zero relational representation). Removing the
rule from the DMN doesn't remove the underlying empirical fact — it's now recorded
here and in `build_openmrs_dmn.py`'s own removal comment instead of as a live decision.



```
openmrs_dmn/
├── README.md                                    <- this file
├── dmn/                                          <- 6 Camunda-7-compatible DMN 1.3 files, open directly in Camunda Modeler
│   ├── Person_Demographics_Validation.dmn            3 decisions (Birthdate / Death Record / Death Date)
│   ├── Patient_Identifier_Validation.dmn             4 decisions (Preferred ID / Location / Uniqueness / Format+CheckDigit)
│   ├── Concept_and_Observation_Validation.dmn        6 decisions (Obs value-by-datatype, Obs group exclusivity, numeric precision/range/interpretation, Concept preferred name)
│   ├── Order_Validation.dmn                          2 decisions (dateActivated consistency, scheduledDate/urgency)
│   ├── Program_Enrollment_Validation.dmn             2 decisions (enrollment dates, patient-state dates)
│   └── Relationship_and_Encounter_Validation.dmn     2 decisions (relationship dates, encounter datetime)
├── scripts/
│   ├── dmn_builder.py                            Same reusable DMN 1.3 + DRD/DMNDI generator used for FLEX2 (unmodified)
│   ├── build_openmrs_dmn.py                      Defines all 19 decisions as plain Python data; emits the .dmn files + rule provenance CSV
│   └── build_openmrs_mapping.py                  Emits variable_to_schema_mapping.csv (one row per DMN input/output)
└── provenance/
    ├── rule_provenance_matrix.csv                 One row per decision (19 rows): source class, file:line citation, tier, hit policy, rule/input counts
    └── variable_to_schema_mapping.csv             One row per DMN variable (100 rows): which openmrs-core table.column it maps to, or why it doesn't
```

The raw validator source files that were fetched and read to mine these
rules are kept in `scratchpad/openmrs_validators/*.java` in this session
(10 files, pulled via `curl` from `raw.githubusercontent.com` on
2026-09-07) — not bundled into this zip since they're openmrs-core's own
code, not a project deliverable, but every line-range citation below can be
independently re-verified against the live GitHub repository at the pinned
class name + line numbers.

## Which validator classes were mined

| Validator class | Decisions drawn from it |
|---|---|
| `PersonValidator.java` | Birthdate Validity, Death Record Consistency, Death Date Consistency |
| `PatientValidator.java` | Preferred Identifier Requirement |
| `PatientIdentifierValidator.java` | Identifier Location Requirement, Identifier Uniqueness Check, Identifier Format And Check-Digit Validity |
| `ObsValidator.java` | Obs Value Required By Datatype, Obs Group Value Exclusivity, Numeric Precision Validity, Numeric Absolute Range Validity, Numeric Interpretation Classification |
| `ConceptValidator.java` | Concept Preferred Name Validity |
| `OrderValidator.java` | Order Date Activated Consistency, Order Scheduled Date Urgency Consistency |
| `PatientProgramValidator.java` | Program Enrollment Date Consistency, Patient State Date Validity |
| `RelationshipValidator.java` | Relationship Date Validity |
| `EncounterValidator.java` | Encounter Datetime Validity |

`ConceptNumericValidator`, `ProgramWorkflowValidator`,
`ProgramWorkflowStateValidator`, and `PatientStateValidator` were checked
for and confirmed **not to exist** as separate classes in openmrs-core
(404 from the raw source URL) — the numeric-range and state-transition
logic those names might suggest actually lives inside `ObsValidator` and
`PatientProgramValidator` respectively, which is why the decisions above
are grouped the way they are rather than one-decision-per-guessed-class.

## Why 19 decisions across 6 files, and 85 rule rows

**Note: these are the package's original, first-pass numbers.** After the three
revisions above (COLLECT split, boolean-reduction, check-digit removal), the current
totals are **24 decisions, 71 rule rows** — see each revision section for the
running tally. This section is kept as the original curation rationale, which still
holds.

Same curation principle as FLEX2: every decision here is genuinely
decision-table-shaped (a combination of field states maps to a validity
verdict + reason code), not a bare `not-null` check with no branching.
OpenMRS's validators are considerably richer in branching logic than a
single policy PDF section, so this set is larger than FLEX2's 11 — but the
same exclusion rule applies. Left out as **not** decision-table-shaped:

- Plain required-field rejections with no alternative branch (e.g.
  `OrderValidator`'s `voided`/`concept`/`patient`/`encounter`/`orderer`
  null-checks at lines 79-88) — these are simple `NOT NULL` constraints,
  already captured by the schema's own column constraints, not business
  rules that need a decision table.
- `ConceptValidator`'s duplicate-name and multiple-preferred-name checks
  (lines 154-213) — these require iterating a variable-length collection
  of `ConceptName` rows to detect duplicates, which isn't a fixed-arity
  decision table the way "is *this* name's own flags consistent" is (the
  one part of that logic, at lines 136-153, that *is* single-row-shaped is
  kept as `Concept Preferred Name Validity`).
- `PatientProgramValidator`'s cross-state overlap/duplication checks
  (lines 172-217) — these compare a `PatientState` against *every other*
  state in the same workflow (a set-level invariant, like FLEX2's
  attendance-eligibility "at least 80% of N rows" pattern), not a
  single-row decision table. `Patient State Date Validity` keeps the part
  of that logic (`endDate` vs `startDate`) that is single-row-shaped.

## Naming convention

Same as FLEX2: DMN variables use readable, business-analyst-style names
(`birthdateIsFutureDate`, `interpretation`) rather than raw column names.
`provenance/variable_to_schema_mapping.csv` is the mapping layer — for every
DMN input/output it records the `table.column` it corresponds to, whether
that's a **direct** stored value or a **derived** one your generator/query
layer must compute, or a genuine **schema gap**.

## Traceability: Tier 2 vs. FLEX2's Tier 1

`provenance/rule_provenance_matrix.csv` cites every decision as:

```
api/src/main/java/org/openmrs/validator/<Class>.java:L<start>-<end> (<method>) [openmrs/openmrs-core@master]
```

instead of FLEX2's `"<policy clause> (p.<page>)"`. Both are equally
independently re-verifiable citations — one into a versioned PDF, one into
a versioned, publicly-browsable GitHub repository at a pinned branch — which
is what "traceable" means for this case study, matching the project's own
plan for OpenMRS (Tier 2: mine validator source, cite by path+line).

## Notable schema-mapping findings (read before generating data)

A few things surfaced while building `variable_to_schema_mapping.csv` that
are worth keeping for the paper's discussion of schema-vs-code business
logic, mirroring FLEX2's "What was removed and why" section:

- **`obs` has no `value_boolean` column.** `ObsValidator` code and Javadoc
  talk about `valueBoolean`, but OpenMRS actually stores a Boolean-datatype
  observation's answer via `obs.value_coded`, pointing at the system's
  `TRUE`/`FALSE` concepts. `Obs Value Required By Datatype`'s "Boolean"
  branch is annotated with this in both the DMN rule description and the
  mapping CSV — a rule can name a Java-level concept (`valueBoolean`) that
  has **no 1:1 physical column**, without that being a schema gap in the
  FLEX2 sense (the value *is* representable, just via a different column).
- **Check-digit validation algorithms are not in the database at all.**
  `patient_identifier_type.validator` stores the *class name* of an
  `IdentifierValidator` (e.g. `LuhnIdentifierValidator`), but the check-digit
  arithmetic itself is Java code with no relational representation. This is
  flagged `SCHEMA GAP (partial)` in the mapping CSV for `checkDigitValid` —
  a data generator can pick a valid/invalid *class name* from that column,
  but cannot derive "is this specific identifier string's check digit
  correct" from the schema alone; it needs the actual validator algorithm
  (a small, enumerable set of known classes shipped with OpenMRS).
- **Numeric reference ranges have two competing schema homes.** Since
  OpenMRS 2.7, a numeric concept's hi/lo thresholds can come from the
  older, static `concept_numeric` table (one fixed range per concept) *or*
  the newer `concept_reference_range` table (multiple criteria-conditional
  ranges per concept, e.g. by age or gender, via its `criteria` column).
  `ObsValidator.getReferenceRange()` (line 293-298) resolves this at
  runtime; `Numeric Absolute Range Validity` and `Numeric Interpretation
  Classification`'s mapping rows note both possible sources rather than
  picking one, since a realistic data generator needs to reproduce whichever
  one a given OpenMRS install actually populates.
- **`Order Date Activated Consistency` needed 8 inputs** to mirror
  `OrderValidator.validateDateActivated()` faithfully (dateActivated's
  future-check, plus three independent pairwise comparisons against
  dateStopped, autoExpireDate, and the parent encounter's datetime) — the
  richest single decision table in this set, comparable in complexity to
  FLEX2's multi-input academic-standing rules.

## How the decisions connect

Unlike FLEX2's `Academic_Standing.dmn` (a genuine 4-decision DRD chain),
none of OpenMRS's validator methods call into each other in a way that
produces a DRD dependency — each validator class validates one domain
object independently (Spring's `Validator` interface is invoked per-object
by the service layer, not chained object-to-object). All 19 decisions here
are therefore modeled as independent decision tables with no
`informationRequirement` edges, which is a faithful reflection of the
source code's actual structure, not a simplification. Each `.dmn` file's
diagram shows its decisions as separate, unconnected boxes.

## Opening in Camunda Modeler

Each `.dmn` file opens as its own Decision Requirements Diagram; every box
is an independent decision table (see "How the decisions connect" above).

Regenerate after editing the build scripts:
```bash
cd scripts
python3 build_openmrs_dmn.py       # .dmn files + rule_provenance_matrix.csv
python3 build_openmrs_mapping.py   # variable_to_schema_mapping.csv
```

## Known caveats

- These decision tables have been validated for XML well-formedness and
  input/output arity (every rule's entry count matches its decision's
  input/output count) in this session, but **not** executed against a
  running Camunda 7 engine or real OpenMRS data — same drafting-pass status
  as FLEX2's artifact.
- Every boolean/derived input (e.g. `birthdateIsFutureDate`,
  `dateActivatedAfterAutoExpireDate`) is a **computed** value your
  generator/inference code must derive from raw column values before
  calling these decisions — none of them are stored directly.
  `variable_to_schema_mapping.csv` marks each one `derived` with the exact
  comparison to compute.
- A handful of decisions collapse what the source code implements as
  several independent `if` statements (which can each raise their own
  error simultaneously) into a single `FIRST`-hit-policy decision table
  with one verdict + one reason code — the same simplification FLEX2 used
  for its FIRST-hit-policy decisions. This is documented per-decision in
  `rule_provenance_matrix.csv`'s hit-policy column; a stricter model could
  use `COLLECT` to surface every simultaneous violation, at the cost of a
  more complex fitness function downstream.
- `PatientIdentifierType.UniquenessBehavior` and `.LocationBehavior` enum
  literal values (`UNIQUE`/`LOCATION`/`NON_UNIQUE`,
  `REQUIRED`/`NOT_USED`) were taken from the Java enum names referenced in
  `PatientIdentifierValidator.java`'s imports and code; this DDL-only
  schema export has no seed data, so the actual column-storage
  representation (string vs. ordinal) should be confirmed against a live
  OpenMRS database before generating data.
