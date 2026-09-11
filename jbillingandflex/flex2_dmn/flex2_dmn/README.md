# FLEX2 — DMN business rules (first drafting pass, revised)

This is the first case study's worth of DMN decision models for the research
paper, drafted from NUCES's official *"Academic Rules and Regulations for
Undergraduate Programs, Revised August 2020"* and grounded in the actual
FLEX2 Oracle schema (`Flex1.sql`, analyzed earlier in this project).

**Revision note:** the original drafting pass produced 12 decisions across 8
files. After building `provenance/variable_to_schema_mapping.csv`, every
rule/input/decision that turned out to have **no matching table or column
anywhere in FLEX2's 220 tables** was removed, rather than kept as an
unenforceable rule. See "What was removed and why" below for the full list.
A second revision then split the attendance rule into two linked decisions
so it runs off raw, course-specific lecture counts instead of an
already-computed percentage — see "The attendance rule" below. This is the
current, revised set: **11 decisions across 6 files**.

## Revision: boolean-reduction pass (2026-09-10)

Same audit applied to Spree and OpenMRS was extended to FLEX2 and jBilling. FLEX2
started in decent shape already — the design doc's own claim that "FLEX2 has zero
boolean-only decisions" held up on re-check — but had **15/33 boolean inputs (45.5%)**
across its 10 decision tables, several of which were pre-collapsed comparisons or
EXISTS-style facts hiding a real, checkable value.

**7 variables converted, each verified against the actual schema mapping notes before
touching anything:**

| Variable | Decision | Real fact | Fix |
|---|---|---|---|
| `maxDurationExceeded` | Admission Closure Eligibility | Date arithmetic vs. a 7-year cap | Exposed as `yearsSinceProgramStart`, tested `> 7` |
| `suspendedRegistrationNotRestored` | Admission Closure Eligibility | Real status code (`D_STUDENT_REG_STATUS`) | Exposed as `regStatus`, tested against the real code |
| `allPrerequisitesPassed` | Course Registration Eligibility | EXISTS over `COURSE_PREREQ` join | Count → `unmetPrerequisiteCount > 0` |
| `isMandatoryReregistration` | Course Registration Eligibility | Grade-history list membership | Exposed as `previousGradeInCourse`, tested via a FEEL list (`{F,D,D+,C-}`) |
| `isCoreCourse` | Course Replacement Eligibility | `D_COURSE_TYPE` lookup | Exposed as `courseTypeId`, tested `= "CORE"` |
| `degreeRequirementsCompletedOrCompletingThisSemester` | Course Replacement Eligibility | Credits-earned vs. degree total | Exposed as `creditsEarned`/`degreeTotalCredits`, cross-variable `<` |
| `isResearchCourseOrProject` | Summer Semester Registration | Same `D_COURSE_TYPE` lookup | `courseTypeId = "RESEARCH"` |
| `isNewCourseRequest` | Summer Semester Registration | "no prior registration" (EXISTS) | Count → `priorRegistrationCount = 0` |
| `minimumTenStudentsEnrolled` | Summer Semester Registration | `COUNT(COURSE_REGISTRATION)` | Count → `enrolledStudentCount >= 10` |
| `prerequisiteCourseAlsoPassed` | Credit Transfer Exemption | EXISTS over `COURSE_PREREQ`+`COURSE_REGISTRATION` | Count → `unmetPrerequisiteAlsoPassedCount = 0` |

Everything else audited (`newAdmissionEligibilityNotMet`, `courseOfferedInFollowingSemesters`,
`replacingCoursePassedAtLeastOneSemesterAfter`, `isElectiveTaughtByVisitingScholarUnavailableOtherwise`)
is a genuine complex join/EXISTS or an already-direct column — left as documented,
legitimate booleans, matching this project's established exception categories.

**Result:**

| Metric | Before | After |
|---|---|---|
| Boolean decision-table inputs | 15/33 (45.5%) | **5/34 (14.7%)** |
| All-boolean decision tables | 0/10 | **0/10** (unchanged — FLEX2 never had one) |

Validated: XML well-formedness + arity clean across all 6 files (11 decisions); full
DMN↔mapping-CSV cross-check clean (one false-positive flag in the checker script
itself, for `Attendance Percentage`'s formula-referenced variables not being parsed
out of its literal-expression text — a pre-existing checker limitation, not a real
inconsistency, confirmed by inspection).



```
flex2_dmn/
├── README.md                          <- this file
├── dmn/                                <- 6 Camunda-7-compatible DMN 1.3 files, open directly in Camunda Modeler
│   ├── Academic_Standing.dmn               4 linked decisions (Warning → Course Load / Admission Closure / Registration)
│   ├── Grading_and_Attendance.dmn          3 decisions (Attendance % calculation → Attendance eligibility, plus Grade points/interpretation lookup)
│   ├── Course_Replacement_Eligibility.dmn  1 decision
│   ├── Graduation_Eligibility.dmn          1 decision
│   ├── Summer_Semester_Registration.dmn    1 decision
│   └── Credit_Transfer_Exemption.dmn       1 decision
├── scripts/
│   ├── dmn_builder.py                  Minimal DMN 1.3 + DRD/DMNDI XML generator (reusable for other case studies; now also supports plain "literal expression" calculation decisions)
│   └── build_flex2_dmn.py              Defines all 11 decisions as plain Python data and emits the .dmn files + provenance CSV
├── provenance/
│   ├── rule_provenance_matrix.csv      One row per DMN rule (56 rows): source clause(s), page(s), input/output condition
│   └── variable_to_schema_mapping.csv  One row per DMN variable (59 rows): which FLEX2 table.column it maps to (or a flagged partial gap)
└── source_documents/                   The two files you uploaded, kept alongside for a self-contained artifact
    ├── Academic_Rules_revised_August_2020.pdf
    └── View_Course_PreReqs.xlsx
```

## What was removed and why

Two whole decisions were dropped, and three more had specific inputs/rules
stripped out, because there is no FLEX2 table or column that could ever
populate them — not "not yet populated," but structurally absent from the
220-table schema.

**Removed entirely:**

- **Academic Honesty Penalty** (rules 8.14–8.18) — every input (`referredTo`,
  `isExtremeActOrRepeatOffense`) depended on a Disciplinary Committee /
  case-referral table that doesn't exist anywhere in FLEX2, and two of its
  three outputs (`penaltyScope`, `disqualifiedFromHonors`) had nothing to
  write back to either. The one output that partially mapped (`maxPenalty`,
  via `COURSE_REGISTRATION.GRADE` for the "F in course" outcome) wasn't
  enough to keep a decision whose branching logic is otherwise entirely
  unmappable.
- **Honor List Eligibility** (rules 7.3–7.8) — the inputs do map fine
  (`STUDENT_SEMESTER.SGPA`, etc.), but the *only output*,
  `honorCategory` (Rector's/Dean's List membership), has no flag column
  anywhere in FLEX2. Rules 7.4/7.7 themselves describe it as
  issued/displayed on the university website — i.e., presentation-layer,
  never persisted. A decision whose sole output can't be written to the
  schema isn't useful for schema-grounded data generation.

**Partially trimmed (decision kept, unmappable input/rule removed):**

- **Admission Closure Eligibility** — dropped `disciplinaryCommitteeRecommendsClosure`
  (rule 3.27) entirely, since no Disciplinary Committee / case table exists
  and that rule had no other condition to fall back on. Also dropped
  `extensionApproved` (rule 3.25's "unless extension is approved" carve-out) —
  no duration-extension-approval table/column exists — while **keeping** the
  mappable half of that rule (`maxDurationExceeded` → Closed), since that
  fact is derivable from `STUDENT_PROGRAM.CREATED_DATE` vs. `CAMP_SEMESTER`
  dates.
- **Attendance Eligibility For Final Exam** — dropped `hodCondonationApproved`
  (rule 1.21's "HoD may condone up to 20% absence" carve-out) — no
  condonation-approval column exists in FLEX2. See "The attendance rule" below.
- **Credit Transfer Exemption** — dropped `gpaInCourseAtPreviousInstitution`
  and rule 3.10 entirely (only a free-text `EXEMPTED_COURSES.REMARKS` column
  exists, not a structured grade/GPA field, so this condition can never be
  evaluated from the schema).

**Kept despite an imperfect mapping:** `Summer_Semester_Registration`'s
`isElectiveTaughtByVisitingScholarUnavailableOtherwise` is marked
"SCHEMA GAP (partial)" rather than removed — it has no direct flag column,
but it is derivable via a join (`EMPLOYEE`/`D_EMP_TYPE` cross-referenced
with `COURSE_OFFER`'s instructor), unlike the fully-unmappable items above.

This is now the schema-grounded finding for the paper: several policy rules
have **zero relational representation** in a real production system, not
merely unenforced constraints — a stronger and more specific claim than "the
rules exist but aren't formalized as CHECK constraints."

## The attendance rule

`Grading_and_Attendance.dmn` now has **two linked decisions** for this,
specifically so the rule can be driven off raw counts your data generator
actually produces, rather than an already-computed percentage:

```
Attendance Percentage  ──▶  Attendance Eligibility For Final Exam
(literal-expression          (decision table: ≥80% not debarred,
 calculation)                 <80% debarred, FA grade)
```

**1. `Attendance Percentage`** — a plain calculation (no branching):
```
attendancePercentage = (lecturesAttended / lecturesHeldForOffering) * 100
```
Both raw inputs are **course-wise and duration-driven**, taken from FLEX2's
actual tables rather than assumed as a fixed number:
- `lecturesHeldForOffering` = `COUNT(LECTURE)` where `OFFER_ID` = this
  specific course offering. `LECTURE` is FLEX2's real record of how many
  sessions were actually held for that course in that semester — it varies
  per course (credit hours, weekly frequency) and per offering
  (`COURSE_OFFER.START_DATE`/`END_DATE`), so a 3-credit course might have 45
  `LECTURE` rows and a 1-credit lab 15 — never a hardcoded "30" for every
  course.
- `lecturesAttended` = `COUNT(STUDENT_ATTENDANCE)` where `ROLL_NO` = this
  student, `LECTURE_ID` is one of that offering's `LECTURE` rows, and
  `ATTEND_FLAG = 'Y'`.

**2. `Attendance Eligibility For Final Exam`** — the threshold rule, now fed
by `attendancePercentage` from decision 1 instead of assuming it arrives
pre-computed: attendance **≥ 80% → eligible, not debarred**; attendance
**< 80% → debarred from the final exam, `FA` grade** — sourced from rules
1.21/1.22:

> "Students are required to maintain 100% attendance... Absence of a maximum
> of 20% of the total attendance may be condoned by the HoD..." (1.21)
> "Failure to meet attendance requirements... will render the student
> ineligible to appear in the final examination..." (1.22)

(The HoD-condonation middle branch from the first draft — attendance
60–80% but condoned → still eligible — stays removed, per the schema-mapping
pass above: FLEX2 has no condonation-approval column.)

**Why this split matters for data generation:** to make a synthetic student
land on either side of this rule for a given course offering, your generator
now has a direct, schema-level target — generate `lecturesHeldForOffering`
rows in `LECTURE` for that `OFFER_ID` (sized to that course's real duration),
then generate `lecturesAttended` matching `STUDENT_ATTENDANCE` rows with
`ATTEND_FLAG='Y'` — at least 80% of them for a "not debarred" case, fewer for
a "debarred" one. Nothing in the rule needs to know a specific lecture count
like 30 in advance; it falls out of however many `LECTURE` rows that course
offering actually has.

## Why 11 decisions across 6 files, not 150

Per your call, this is a **curated core set** — the clauses that are
genuinely decision-table-shaped (a condition maps to an outcome) and
consequential for data generation, not the purely procedural rules (who
signs which form, what a committee's composition is), and now further
narrowed to only what FLEX2's schema can actually represent. See
`provenance/rule_provenance_matrix.csv` for the exact clause-to-rule
mapping, and "What was left out this round" below for what wasn't
converted (for reasons other than a schema gap).

## Naming convention

Per your instruction, DMN variables use **readable, business-analyst-style
names** (`cumulativeGPA`, `newWarningCount`, `canRegisterCourse`) rather than
raw FLEX2 column names (`CGPA`, `WARNING`). `provenance/variable_to_schema_mapping.csv`
is the mapping layer between the two — that's the file your inference code
should read to know, for each DMN input/output, which FLEX2 table.column it
corresponds to (or that it's a derived/computed value).

## How the decisions connect (the DRD in `Academic_Standing.dmn`)

```
Academic Warning Status  ──▶  Course Load Limit  ──▶  Course Registration Eligibility
        │                                                      ▲
        └────────────────▶  Admission Closure Eligibility      │
        └──────────────────────────────────────────────────────┘
```

`Academic Warning Status` computes a student's new warning count and
admission status from their CGPA and prior warning count (rules 5.4-5.7).
That `newWarningCount` output feeds directly into `Course Load Limit`
(rules 1.19/4.3/4.4c/6.6), `Admission Closure Eligibility` (rules
3.24-3.28, minus the removed 3.27), and `Course Registration Eligibility`
(rules 1.20/4.4e), which also consumes `Course Load Limit`'s
`maxCoursesAllowed`. This mirrors how the policy document itself chains
these rules together.

The other 3 decisions (Grading/Attendance, Course Replacement, Graduation,
Summer Registration, Credit Transfer) are independent of this chain and of
each other — the source document doesn't state a dependency between them,
so none was invented.

## What was left out this round (candidates for a second pass)

These weren't dropped for a schema-gap reason — they just weren't in this
first curated batch:

- The SGPA/CGPA arithmetic formulas (rules 2.4-2.7) — these are aggregation
  formulas over a variable-length list of courses, not branching decision
  logic, so they don't naturally fit a DMN decision table. Treated as
  pre-computed input data to the decisions above instead. A DMN "literal
  expression" / boxed-context decision could model this if you want it
  formalized too — flag if so.
- Add/drop timing windows (4.19-4.21), withdrawal rules (4.22-4.26),
  suspension/restoration (4.16-4.17), FYP registration (4.10-4.15),
  rechecking of final exams (5.18-5.24), transfer between campuses
  (3.20-3.22) — all genuinely decision-shaped, just not in this first
  curated batch. Say the word and I'll draft the next set the same way
  (and check each against the schema before including it, this time as
  the first pass rather than a correction afterward).

## Opening in Camunda Modeler

Each `.dmn` file opens as its own Decision Requirements Diagram. Files with
one decision (Course Replacement, Graduation, Summer Registration, Credit
Transfer) show a single box — click it to see the decision table.
`Academic_Standing.dmn` and `Grading_and_Attendance.dmn` show multiple
linked boxes.

Regenerate any file after editing `scripts/build_flex2_dmn.py`:
```bash
cd scripts && python3 build_flex2_dmn.py
```

## Known caveats

- FEEL expressions were hand-checked for valid Camunda 7 syntax (unary
  tests, `not(...)` for negation, `null` literal, cross-input comparisons
  like `> maxCoursesAllowed`), and every file was re-validated (XML
  well-formedness + input/output arity per rule) in this session after the
  schema-mapping revision — but none of these decision tables have been
  executed yet against a running Camunda 7 engine or test data. Treat this
  as a drafting pass ready for your review, not a verified/tested artifact.
- Several boolean/derived inputs (e.g. `allPrerequisitesPassed`,
  `attendancePercentage`, `isMandatoryReregistration`) are **computed**
  values your application/inference code will need to derive from raw
  FLEX2 rows before calling these decisions — they aren't stored directly.
  `variable_to_schema_mapping.csv` marks each one as `derived` with a note
  on how to compute it.
- Some coded values (e.g. `admissionStatus` "Active"/"Closed" mapping to
  `STUDENT_PROGRAM.PROG_STATUS`'s numeric `STATUS_ID`) need to be confirmed
  against the real `D_STUDENT_STATUS`/`D_STUDENT_REG_STATUS` reference data —
  this DDL-only export has no seed rows, so the actual code values weren't
  visible to me.
</content>
