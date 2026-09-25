"""Disclosed override for a rule whose <inputEntry> unary-test TEXT was
authored under the WRONG decision-table column -- distinct from every
other override module in this project (all of which correct a ground-
truth CSV row's own resolution/label): the mistake here is inside the
.dmn rule TABLE itself, not the provenance CSV.

Found real, not hypothetical, auditing jBilling's own
Order_Cancellation_and_Validity.dmn, `Order Period Already Invoiced`::
Rule_3/Rule_4. Both rules' 4th input column ("Next Billable Day", bound
variable `nextBillableDay`) carries the unary-test text
">= nextBillableDay" / "< nextBillableDay" -- `feel_parser.parse_unary_test`
faithfully binds that text to ITS OWN column's bound variable (per its
own documented contract), producing a SELF-comparison
(`nextBillableDay >= nextBillableDay`, always true; `nextBillableDay <
nextBillableDay`, always false) instead of the real cross-field date
comparison the DMN plainly intends. Both rules leave their 3rd input
column ("Candidate Date", bound variable `candidateDate`) as a bare
wildcard `-`.

Confirmed against the real cited source, not just the rules' own prose:
`OrderBL.java`'s own `isDateInvoiced(Date date)` (source_documents/
OrderBL.java, ~L1104-1107) is exactly
    date != null && order.getNextBillableDay() != null &&
        date.before(order.getNextBillableDay())
-- i.e. `candidateDate < nextBillableDay` -> already invoiced (true),
matching Rule_4's own description ("candidate date falls before ... a
period that was already going to be invoiced is being shortened" ->
true) and Rule_3's ("candidate date is not before the next billable
day" -> false). This confirms the test was meant to run with
`candidateDate` as the LEFT operand, authored under the wrong column,
not a hypothetical reading.

Corrected here, disclosed and inspectable, rather than silently hand-
edited into the source .dmn file (treated as an immutable ground-truth
artifact, same discipline as every CSV-side override in this project)
or left to silently produce a tautology/contradiction pair that makes
Rule_4 permanently unreachable under FIRST hit policy.

Keyed by rule_id alone (not (case_study, rule_id)): every case study's
own DMN decisions use a case-study-specific `Decision_<Name>_Rule_N`
naming scheme with no cross-case-study collisions, confirmed by
inspection -- the same assumption `dmn_walk.py`'s/this compiler's own
rule `id` already relies on for stability elsewhere.
"""

_COLUMN_OVERRIDES = {
    'Decision_OrderPeriodAlreadyInvoiced_Rule_3': {'nextBillableDay': 'candidateDate'},
    'Decision_OrderPeriodAlreadyInvoiced_Rule_4': {'nextBillableDay': 'candidateDate'},
}


def get_column_override(rule_id, col_var):
    """Returns the column variable `parse_unary_test` should bind this
    cell's text to for this rule_id -- `col_var` unchanged (the normal
    case) unless a disclosed override says this specific cell was
    authored under the wrong column."""
    return _COLUMN_OVERRIDES.get(rule_id, {}).get(col_var, col_var)
