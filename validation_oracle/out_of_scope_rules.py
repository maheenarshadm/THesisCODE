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

    # -------------------------------------------------------------------
    # 2026-09-26: the 22 PERMANENT, STRUCTURAL exclusions (COLLECT hit
    # policy -- rule_evaluator.py has no COLLECT implementation at all;
    # all-code_external -- genuinely nothing in any table to check) that
    # briefly lived here as registry entries are no longer needed AT ALL.
    # On the user's own explicit request, they've been physically removed
    # from `generator/compiled_constraints.json` (the corpus itself, the
    # search's own objective source, not just this validator-side filter)
    # and archived for reference -- full records, reasons, and how to
    # restore them -- at `validation_oracle/out_of_scope/permanent/`. A
    # rule that isn't in the compiled corpus at all never reaches
    # `is_out_of_scope()` in the first place, so registering it here would
    # be dead code. Same move for 17 further rules whose own decisions
    # currently have no resolvable subject table (Spree's `Promotion Item
    # Total Eligibility`, FLEX2's `Admission Closure Eligibility`,
    # jBilling's `Order Date Range Valid`/`Payment Outcome Resolution`/
    # `Payment Balance Assignment`) -- NOT confirmed permanent, unlike the
    # 22 above, just not yet investigated; archived separately at
    # `validation_oracle/out_of_scope/pending_investigation/` with that
    # caveat stated explicitly. See that folder's own README before ruling
    # either group in or out for good.
    #
    # 2026-09-26 (later, same day): 5 more moved to `permanent/`, same
    # convention (physically removed from compiled_constraints.json, no
    # registry entry needed here) -- `Identifier Uniqueness Check::Rule_4`
    # (needs `duplicateWithinSamePatient`, whose real logic genuinely
    # branches on a 3rd variable, `uniquenessBehavior` -- see
    # KNOWN_ISSUES.md's cat4 entry) and all 4 rules of `Obs Group Value
    # Exclusivity` (its own `isObsGroup` ground truth is just "same as
    # above," a cross-row reference to `Obs Value Required By Datatype`'s
    # own fixed fact, deliberately left unresolved when that fix was made
    # -- a different, easy-to-get-wrong shape from the two patterns fixed
    # there). On the user's own explicit request.
}


def is_out_of_scope(case_study, rule_id):
    return (case_study, rule_id) in OUT_OF_SCOPE_RULES


def reason(case_study, rule_id):
    return OUT_OF_SCOPE_RULES.get((case_study, rule_id))
