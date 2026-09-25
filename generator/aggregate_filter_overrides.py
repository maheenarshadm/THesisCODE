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
}


def get_filter_text_override(case_study, var_name):
    return _FILTER_TEXT_OVERRIDES.get((case_study, var_name))
