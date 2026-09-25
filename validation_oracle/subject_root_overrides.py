"""Explicit, DISCLOSED human overrides for a decision's own ROOT table,
consulted ONLY when `subject_table._pick_root` finds more than one
table that mechanically qualifies (reaches every directly-referenced
table) -- same status as `join_disambiguation.py`/`filter_placeholder_
sources.py`: a researcher's domain-knowledge call, made explicit and
inspectable here, never silently guessed by the root-picking search
itself.

An override does NOT let a table become the root just because it's
named here -- `_pick_root` still requires it to be one of the tables
that ALREADY mechanically qualifies (reaches everything `all_tables`
needs); this file only breaks a tie among several structurally-valid
candidates, using a real semantic reason (e.g. which candidate actually
carries the right GRANULARITY for what the decision's own variables
need), never an arbitrary pick. A tie with no override here is still
refused, exactly as before this file existed.

Format: {(case_study, decision_name): table_name}
Table names must match the schema JSON's own canonical casing
(`schema_utility.canonical_table_name`).
"""

SUBJECT_ROOT_OVERRIDES = {
    # FLEX2's `Summer Semester Registration`: once `<this course
    # offering>` is resolved via `filter_placeholder_sources.py` (->
    # COURSE_OFFER), `_pick_root` finds 3 mechanically-valid candidates
    # reaching both COURSE and COURSE_OFFER: COURSE_OFFER,
    # COURSE_REGISTRATION, and REPEAT_COURSE (confirmed against
    # flex2_schema_full.json, 2026-09-25). COURSE_OFFER's own PK is
    # bare OFFER_ID (no per-student column at all); REPEAT_COURSE's own
    # PK is ALSO bare OFFER_ID (its own USER_ID is a plain FK column,
    # not part of its key, and traces only to APPUSER -> EMPLOYEE, with
    # no schema path to a student at all -- not a student identity).
    # COURSE_REGISTRATION is the ONLY candidate whose own PK is the
    # composite (OFFER_ID, ROLL_NO) -- a specific student's specific
    # registration for a specific offering, exactly the granularity
    # every one of this decision's own variables needs
    # (priorRegistrationCount by student+course, enrolledStudentCount
    # by offering, isElectiveTaughtByVisitingScholarUnavailableOtherwise
    # by offering) -- the decision is literally named "...Registration",
    # a per-registration-event fact, not a per-offering or per-course
    # one. [Researcher domain call from the real schema's own PK shapes,
    # not from external documentation -- disclosed here rather than
    # silently guessed.]
    ('FLEX2', 'Summer Semester Registration'): 'COURSE_REGISTRATION',
}


def get_override(case_study, decision_name):
    return SUBJECT_ROOT_OVERRIDES.get((case_study, decision_name))
