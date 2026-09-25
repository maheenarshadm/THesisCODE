"""Disclosed generator-side subject-granularity decisions.

Kept independent of validation_oracle: these are schema/domain metadata,
not oracle results. An override is accepted only if the generator's own
FK traversal proves that the table reaches every required input table.
"""

SUBJECT_ROOT_OVERRIDES = {
    # Existing researcher decision documented in the oracle's matching
    # override: COURSE_REGISTRATION has PK (OFFER_ID, ROLL_NO), representing
    # one student's registration. COURSE_OFFER and REPEAT_COURSE instead
    # have an OFFER_ID-only PK; the latter's USER_ID refers to APPUSER /
    # EMPLOYEE, not a schema-declared student identity. This breaks a tie
    # among structurally qualifying roots; it does not invent an FK.
    ('FLEX2', 'Summer Semester Registration'): 'COURSE_REGISTRATION',
}
