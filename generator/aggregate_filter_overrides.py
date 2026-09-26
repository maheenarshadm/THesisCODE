"""Explicit, DISCLOSED hand-translations of a `derived_aggregate`'s own
`filter_text`, when the raw ground-truth text embeds informal, non-SQL
prose inside what's otherwise a real WHERE clause -- same status as
`literal_expression_overrides.py`: a researcher's translation of the
text's real intent into real SQL, made explicit and inspectable here
rather than silently executed as malformed SQL (a real syntax error) or
silently guessed at.

Consulted only for a variable that already produced a `derived_aggregate`
node via the normal WHERE-clause extraction -- this REPLACES that node's
own `filter_text` with the hand-translated version, changing nothing
else about the node.

Format: {(case_study, var_name): replacement_filter_text}
"""

# FLEX2's `lecturesAttended` (Attendance Percentage / Attendance
# Eligibility For Final Exam): the real ground truth reads "ROLL_NO=
# <student> AND LECTURE_ID IN (LECTURE for that OFFER_ID) AND
# ATTEND_FLAG='Y'" -- "LECTURE for that OFFER_ID" is informal prose, not
# SQL; executed verbatim it is a syntax error (confirmed directly,
# 2026-09-25). Translated to a real subquery: LECTURE_ID must be one of
# the real LECTURE_IDs belonging to the SAME course offering. Reuses the
# SAME two bracket placeholders the surrounding ground truth already
# names (`<student>`, and `<this course offering>` -- already used
# identically by `lecturesHeldForOffering`'s own sibling filter_text and
# by FLEX2's `Summer Semester Registration`), resolved by the SAME
# existing `filter_placeholder_sources.py` mechanism -- no new
# resolution capability needed on either the validator or generator side.
_FILTER_TEXT_OVERRIDES = {
    ('FLEX2', 'lecturesAttended'): (
        "ROLL_NO = <student> AND ATTEND_FLAG = 'Y' "
        "AND LECTURE_ID IN (SELECT LECTURE_ID FROM LECTURE WHERE OFFER_ID = <this course offering>)"
    ),
    # FLEX2's `repeatCourseCountRequested` (Summer Semester Registration
    # ::Rule_3, `> 2`), 2026-09-26 -- RESEARCHER ASSUMPTION, chosen by the
    # user: the curated text is "REPEAT_COURSE (COUNT per USER_ID/
    # semester)", which had no filter at all (a whole-table count the
    # validator correctly refused). Per-student is not expressible in this
    # schema: REPEAT_COURSE.USER_ID FKs to APPUSER.USERID, and APPUSER
    # links only to EMPLOYEE (staff accounts) -- no student table
    # references it. Reinterpreted as the number of repeat-course
    # offerings in THIS registration's semester (REPEAT_COURSE.OFFER_ID ->
    # COURSE_OFFER.SEM_ID). `<semester>` binds to the subject row's own
    # SEM_ID on the validator side (same-named column first) and via
    # compile_constraints.py's decision-scoped placeholder source on the
    # generator side.
    ('FLEX2', 'repeatCourseCountRequested'): (
        "OFFER_ID IN (SELECT OFFER_ID FROM COURSE_OFFER WHERE SEM_ID = <semester>)"
    ),
}


def get_filter_text_override(case_study, var_name):
    return _FILTER_TEXT_OVERRIDES.get((case_study, var_name))
