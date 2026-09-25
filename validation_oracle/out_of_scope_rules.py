"""Explicit, DISCLOSED registry of individual DMN rules declared
permanently out of scope for verification -- excluded from a decision's
own subject-table computation and from real-case evaluation, but still
emitted in `objective_results.csv` (always `verified_rule_selected=False`)
for full transparency, never silently dropped from the report or from
`total_dmn_rules`/`searchable_objectives`.

Distinct from `filter_placeholder_sources.py`/`subject_root_overrides.py`
(which help a decision or variable RESOLVE): this registry stops one
SPECIFIC rule from participating in subject-determination or evaluation
at all, because a researcher has already decided -- for a disclosed
reason -- that this rule will never be verified (e.g. it needs a genuine
one-to-many backward join with no honest single-row answer, or reads
blob-level serialized content out of this project's stated scope, see
KNOWN_ISSUES.md's scope-decision entry). A sibling rule of the SAME
decision that does not itself need the excluded rule's own table is then
free to resolve a real subject using only the tables the IN-SCOPE rules
need -- without this registry, one out-of-scope rule's own unreachable
table requirement silently poisons `subject_table_for_decision`'s shared
union for the WHOLE decision, blocking siblings that never even touch
that table.

Format: {(case_study, rule_id): "reason"}
"""

OUT_OF_SCOPE_RULES = {
    ('Spree', 'Decision_PromotionCustomerGroupEligibility_rule_4'):
        "matchingCustomerGroupCount needs a genuine one-to-many backward "
        "join to spree_customer_group_users (one user belongs to many "
        "customer groups) -- no honest single-row subject-table answer, "
        "same 'refusing to guess' category as this project's other "
        "one-to-many backward-join gaps (see KNOWN_ISSUES.md). Confirmed "
        "2026-09-25: left unexcluded, its own table requirement poisons "
        "subject_table_for_decision for the WHOLE 'Promotion Customer "
        "Group Eligibility' decision, blocking rule_1/rule_2 too even "
        "though neither reads spree_customer_group_users at all.",
}


def is_out_of_scope(case_study, rule_id):
    return (case_study, rule_id) in OUT_OF_SCOPE_RULES


def reason(case_study, rule_id):
    return OUT_OF_SCOPE_RULES.get((case_study, rule_id))
