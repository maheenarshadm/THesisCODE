"""Explicit, DISCLOSED "exclude this row itself" columns for a
`derived_aggregate` whose own "for COL" self-correlation
(`compile_constraints.py`'s `AGGREGATE_FOR_CORRELATION_RE`) targets the
SAME table as the decision's own subject -- meaning the subject's own
row always matches its own correlation filter, so the count can never
read 0 for any real row. Same status as `aggregate_self_table.py`/
`join_disambiguation.py`: a researcher's disclosed domain call, never
silently guessed by the generic "for COL" mechanical translation itself
(which has no way to infer "except this one" from generic ground-truth
text).

Format: {(case_study, var_name): exclude_column}. The named column gets
an extra ` AND COLUMN != :COLUMN` conjunct appended to the already-
translated filter_text -- resolved by the SAME `:COLUMN` self-reference
machinery (`validation_oracle/db_resolver.py`'s own
`_substitute_self_and_colon`, and `candidate.py`'s/`mutation.py`'s own
mirror fix) already used for the base correlation, so this needs no new
resolution capability, just one more conjunct.
"""

# FLEX2's `priorRegistrationCount` (Summer Semester Registration): counts
# a student's OTHER registrations for the SAME course (ROLL_NO+COURSE_ID
# correlation). `COURSE_REGISTRATION`'s own subject row always matches
# that same filter (it IS a COURSE_REGISTRATION row for this ROLL_NO/
# COURSE_ID pair), so without excluding it, the count can never be 0 for
# any real row -- confirmed 2026-09-25 investigating why Summer Semester
# Registration::Rule_2 never verifies. Excluding by OFFER_ID (not the
# full composite PK) is the real, intended meaning, not an arbitrary
# choice: two DIFFERENT OFFER_ID rows sharing the same (ROLL_NO,
# COURSE_ID) is exactly what "a prior registration for this course"
# describes -- an earlier semester's own offering of the same course,
# confirmed against the real schema (COURSE_REGISTRATION's PK is
# (OFFER_ID, ROLL_NO); OFFER_ID is a real FK to COURSE_OFFER, which
# carries its own SEM_ID).
_EXCLUDE_SELF_COLUMN = {
    ('FLEX2', 'priorRegistrationCount'): 'OFFER_ID',
}


def get_exclude_self_column(case_study, var_name):
    return _EXCLUDE_SELF_COLUMN.get((case_study, var_name))
