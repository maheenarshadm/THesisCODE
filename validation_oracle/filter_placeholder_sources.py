"""Explicit, DISCLOSED human overrides naming which table a `filter_text`
`<placeholder>` actually comes from, when it is NOT a same-named column
on the SUBJECT row itself -- same status/precedent as
`join_disambiguation.py` and `supplementary_fk_edges.py`: a researcher's
domain-knowledge call, made explicit and inspectable here, never
silently guessed.

`db_resolver._resolve_placeholders` tries the subject row first, exactly
as before this file existed -- every placeholder already resolvable that
way (jBilling's `entity_id`/`status_id`, Spree's own
`price_list_id`/`user_id`/`email`) is completely unaffected, since none
of them has an entry here. Only when a placeholder is NOT found on the
subject row does it consult this table; a placeholder with no override
here and no subject-row column still raises exactly as before (never a
silent guess).

Naming the SOURCE table here is only half the job -- `subject_table.py`'s
`tables_referenced()` also lists this table so the decision's own root-
picking and join-path construction (`schema_utility.build_join_path`,
completely unmodified) include it, and `_resolve_placeholders` then reads
the real value off the ALREADY-JOINED row via the SAME `_row_for_table`
hop-walker every other cross-table kind already uses -- no new
join-finding logic anywhere.

Format: {(case_study, placeholder_name): table_name}
Table names must match the schema JSON's own canonical casing
(`schema_utility.canonical_table_name`).
"""

FILTER_PLACEHOLDER_SOURCES = {
    ('Spree', 'promotion_id'): 'spree_order_promotions',
    # FLEX2's `Course Replacement Eligibility` (all 6 rules):
    # `degreeTotalCredits`'s own filter_text reads `PROGRAM_COURSE.
    # PROG_ID=<program> AND PROGRAM_COURSE.BATCH_NO=<batch>` -- neither
    # column is on the subject row (`COURSE_REGISTRATION`), but both are
    # real columns on `STUDENT_PROGRAM`, reachable via COURSE_REGISTRATION
    # .ROLL_NO's own real forward FK to STUDENT_PROGRAM.ROLL_NO (confirmed
    # against flex2_schema_full.json, 2026-09-24).
    ('FLEX2', 'program'): 'STUDENT_PROGRAM',
    ('FLEX2', 'batch'): 'STUDENT_PROGRAM',
    # FLEX2's `Summer Semester Registration`: `isElectiveTaughtByVisiting
    # ScholarUnavailableOtherwise`'s own raw SQL reads `CO.OFFER_ID =
    # <this course offering>` -- OFFER_ID is a real column on
    # COURSE_OFFER (its own PK), not on the subject row. Together with
    # `subject_root_overrides.py` (COURSE_REGISTRATION as this
    # decision's own root, which has a real, direct FK to COURSE_OFFER),
    # this lets `<this course offering>` resolve to the subject's own
    # correlated COURSE_OFFER row instead of raising.
    ('FLEX2', 'this course offering'): 'COURSE_OFFER',
    # FLEX2's `Attendance Eligibility For Final Exam`: `lecturesAttended`'s
    # own filter_text (hand-corrected in `generator/aggregate_filter_
    # overrides.py`, the same real ground-truth text this validator reads
    # unchanged) reads `ROLL_NO = <student> AND ...` -- ROLL_NO is a real
    # column on `COURSE_REGISTRATION` (its own FK to STUDENT_PROGRAM),
    # confirmed the correct subject for this decision the same way as
    # `Summer Semester Registration` (composite PK `(OFFER_ID, ROLL_NO)`,
    # the exact granularity "one student's attendance in one course
    # offering" needs). `<student>` is ALSO used by `Course Registration
    # Eligibility`'s own filter_text, but harmlessly -- that decision's
    # own subject already IS `COURSE_REGISTRATION`, so `<student>`
    # already resolves via the subject row's own ROLL_NO column (this
    # validator's first-priority check) without ever consulting this
    # entry at all; confirmed zero collateral via a full before/after
    # subject-table sweep, 2026-09-25.
    ('FLEX2', 'student'): 'COURSE_REGISTRATION',
    # Case study 'T' is this project's own synthetic test namespace
    # (tests/test_spec_cases.py) -- this entry is exercised only by
    # test_case_11_filter_placeholder_via_join, never by real data.
    ('T', 'region'): 'customer',
    # jBilling's `Currency Exchange Rate Source`: `hasEntitySpecificExchange`
    # /`hasSystemDefaultExchange`'s own filter_text (`entity_id = <entity_id>
    # AND currency_id = <currency_id>` / `entity_id = 0 AND currency_id =
    # <currency_id>`) reads real `currency_exchange` columns, but neither
    # `<entity_id>` nor `<currency_id>` is tied to any specific table by the
    # DMN, CSV, or DRD -- both are pure `CurrencyBL.findExchange(Integer
    # entityId, Integer currencyId)` method parameters in the real Java
    # source, with no schema-declared origin at all. GENUINE RESEARCHER
    # JUDGMENT CALL (explicitly asked of, and made by, the user,
    # 2026-09-25 -- not a mechanically-forced choice like every other entry
    # above): `base_user` has its own real `entity_id`/`currency_id`
    # columns (confirmed against jbilling_schema_full.json), so "whose
    # exchange rate" is read as "the currently-relevant user's own entity
    # and billing currency." This is NOT confirmed by any disclosed FK --
    # `base_user.entity_id`/`.currency_id` and `currency_exchange`'s own
    # same-named columns share no declared foreign key at all (confirmed:
    # `currency_exchange`'s own `fk_columns` only has `currency_id ->
    # currency.id`, nothing on `entity_id`), so this decision's `exists`
    # checks query `currency_exchange` directly by value, never via a real
    # join path -- consistent with every other `exists`-with-`filter_text`
    # node (see `subject_table.py`'s own `_TABLE_EXTRACTORS['exists']`).
    # The alternative (`currency_exchange` itself as subject) was rejected
    # as degenerate -- `hasEntitySpecificExchange` would be trivially true
    # for any row it enumerates, permanently precluding Rule_2/Rule_3 --
    # while `base_user` at least leaves all three rules structurally
    # reachable, data permitting. See KNOWN_ISSUES.md's matching entry for
    # the fixture-side caveat this uncovered (`base_user`'s own committed
    # rows have NULL `entity_id`/`currency_id` -- never populated, since no
    # earlier decision needed them).
    ('jBilling', 'entity_id'): 'base_user',
    ('jBilling', 'currency_id'): 'base_user',
}


def get_source_table(case_study, placeholder):
    return FILTER_PLACEHOLDER_SOURCES.get((case_study, placeholder))
