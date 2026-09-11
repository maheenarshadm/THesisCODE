import sys, os, csv
sys.path.insert(0, os.path.dirname(__file__))
from dmn_builder import build_dmn_file

NS = "https://spree-dmn.research/case-study"

# ---------------------------------------------------------------------------
# FILE 1: Promotion_Order_Level_Eligibility.dmn
# ---------------------------------------------------------------------------

d_effective_min = {
    'kind': 'literal', 'id': 'Decision_EffectiveMinimumAmountThreshold',
    'name': 'Effective Minimum Amount Threshold',
    'output': {'type': 'number'},
    'expression': 'if operatorMin = "gte" then amountMin else amountMin + 0.01',
}

d_effective_max = {
    'kind': 'literal', 'id': 'Decision_EffectiveMaximumAmountThreshold',
    'name': 'Effective Maximum Amount Threshold',
    'output': {'type': 'number'},
    'expression': 'if operatorMax = "lte" then amountMax else amountMax - 0.01',
}

d_item_total = {
    'kind': 'table', 'id': 'Decision_ItemTotalEligibility',
    'name': 'Promotion Item Total Eligibility',
    'hit_policy': 'UNIQUE',
    'requires': ['Decision_EffectiveMinimumAmountThreshold', 'Decision_EffectiveMaximumAmountThreshold'],
    'inputs': [
        {'var': 'itemTotal', 'label': 'Order item total', 'type': 'number'},
        {'var': 'amountMaxSet', 'label': 'Maximum amount configured?', 'type': 'boolean'},
    ],
    'outputs': [{'var': 'itemTotalEligible', 'label': 'Item-total rule eligible', 'type': 'boolean'}],
    'rules': [
        {'conditions': ['>= effectiveMinThreshold', 'false'], 'outputs': ['true'],
         'annotation': 'no maximum configured; meets the resolved minimum'},
        {'conditions': ['< effectiveMinThreshold', 'false'], 'outputs': ['false'],
         'annotation': 'no maximum configured; fails the resolved minimum'},
        {'conditions': ['[effectiveMinThreshold..effectiveMaxThreshold]', 'true'], 'outputs': ['true'],
         'annotation': 'maximum configured; within the resolved [min,max] range'},
        {'conditions': ['not([effectiveMinThreshold..effectiveMaxThreshold])', 'true'], 'outputs': ['false'],
         'annotation': 'maximum configured; outside the resolved [min,max] range'},
    ],
}

d_temporal = {
    'kind': 'table', 'id': 'Decision_PromotionTemporalAvailability',
    'name': 'Promotion Temporal Availability',
    'hit_policy': 'FIRST',
    'inputs': [
        {'var': 'evaluationTime', 'label': 'Time of eligibility check', 'type': 'date and time'},
        {'var': 'startsAt', 'label': 'Promotion starts_at', 'type': 'date and time'},
        {'var': 'expiresAtSet', 'label': 'expires_at configured?', 'type': 'boolean'},
        {'var': 'expiresAt', 'label': 'Promotion expires_at', 'type': 'date and time'},
    ],
    'outputs': [{'var': 'availabilityStatus', 'label': 'Availability status', 'type': 'string'}],
    'rules': [
        {'conditions': ['< startsAt', '-', '-', '-'], 'outputs': ['"NOT_YET_STARTED"']},
        {'conditions': ['-', '-', 'true', '> expiresAt'], 'outputs': ['"EXPIRED"']},
        {'conditions': ['-', '-', '-', '-'], 'outputs': ['"ACTIVE"']},
    ],
}

d_usage_limit = {
    'kind': 'table', 'id': 'Decision_PromotionUsageLimitExceeded',
    'name': 'Promotion Usage Limit Exceeded',
    'hit_policy': 'FIRST',
    'inputs': [
        {'var': 'usageLimitSet', 'label': 'usage_limit configured?', 'type': 'boolean'},
        {'var': 'usageLimit', 'label': 'Configured usage limit', 'type': 'number'},
        {'var': 'adjustedCreditsCount', 'label': 'Credits already used (adjusted)', 'type': 'number'},
    ],
    'outputs': [{'var': 'usageLimitExceeded', 'label': 'Usage limit exceeded', 'type': 'boolean'}],
    'rules': [
        {'conditions': ['false', '-', '-'], 'outputs': ['false']},
        {'conditions': ['true', '<= 0', '-'], 'outputs': ['false']},
        {'conditions': ['true', '> 0', '>= usageLimit'], 'outputs': ['true']},
        {'conditions': ['-', '-', '-'], 'outputs': ['false']},
    ],
}

FILE1_DECISIONS = [d_effective_min, d_effective_max, d_item_total, d_temporal, d_usage_limit]

# ---------------------------------------------------------------------------
# FILE 2: Customer_Segment_Eligibility.dmn
# ---------------------------------------------------------------------------

d_group_match_count = {
    'kind': 'literal', 'id': 'Decision_CustomerGroupMatchCount',
    'name': 'Customer Group Match Count',
    'output': {'type': 'number'},
    'expression': 'count(intersection(customerGroupIds, promotionTargetGroupIds))',
}

d_customer_group_eligibility = {
    'kind': 'table', 'id': 'Decision_PromotionCustomerGroupEligibility',
    'name': 'Promotion Customer Group Eligibility',
    'hit_policy': 'FIRST',
    'requires': ['Decision_CustomerGroupMatchCount'],
    'inputs': [
        {'var': 'customerIdPresent', 'label': 'order.customer_id present?', 'type': 'boolean'},
        {'var': 'promotionTargetGroupsConfigured', 'label': 'promotion targets >=1 customer group?', 'type': 'boolean'},
        {'var': 'matchingCustomerGroupCount', 'label': 'Customer Group Match Count (upstream)', 'type': 'number'},
    ],
    'outputs': [{'var': 'customerGroupEligible', 'label': 'Customer-group rule eligible', 'type': 'boolean'}],
    'rules': [
        {'conditions': ['false', '-', '-'], 'outputs': ['false']},
        {'conditions': ['-', 'false', '-'], 'outputs': ['false']},
        {'conditions': ['-', '-', '> 0'], 'outputs': ['true']},
        {'conditions': ['-', '-', '-'], 'outputs': ['false']},
    ],
}

d_prior_completed_orders = {
    'kind': 'literal', 'id': 'Decision_PriorCompletedOrderCount',
    'name': 'Prior Completed Order Count',
    'output': {'type': 'number'},
    'expression': 'count(order for order in store.orders where (order.customer = customer or order.email = email) and order.state = "complete" and order != currentOrder)',
}

d_first_order = {
    'kind': 'table', 'id': 'Decision_FirstOrderPromotionEligibility',
    'name': 'First-Order Promotion Eligibility',
    'hit_policy': 'FIRST',
    'requires': ['Decision_PriorCompletedOrderCount'],
    'inputs': [
        {'var': 'userOrEmailPresent', 'label': 'customer or email identified?', 'type': 'boolean'},
        {'var': 'priorCompletedOrderCount', 'label': 'Prior Completed Order Count (upstream)', 'type': 'number'},
    ],
    'outputs': [{'var': 'firstOrderEligible', 'label': 'First-order rule eligible', 'type': 'boolean'}],
    'rules': [
        {'conditions': ['false', '-'], 'outputs': ['false']},
        {'conditions': ['-', '0'], 'outputs': ['true']},
        {'conditions': ['-', '-'], 'outputs': ['false']},
    ],
}

d_one_use_per_user = {
    'kind': 'table', 'id': 'Decision_OneUsePerUserEligibility',
    'name': 'One-Use-Per-User Promotion Eligibility',
    'hit_policy': 'FIRST',
    'inputs': [
        {'var': 'customerPresent', 'label': 'order.customer present?', 'type': 'boolean'},
        {'var': 'priorPromotionUsageCount', 'label': 'Prior uses of this promotion by this customer', 'type': 'number'},
    ],
    'outputs': [{'var': 'oneUsePerUserEligible', 'label': 'One-use-per-user rule eligible', 'type': 'boolean'}],
    'rules': [
        {'conditions': ['false', '-'], 'outputs': ['false']},
        {'conditions': ['-', '0'], 'outputs': ['true']},
        {'conditions': ['-', '-'], 'outputs': ['false']},
    ],
}

FILE2_DECISIONS = [d_group_match_count, d_customer_group_eligibility,
                    d_prior_completed_orders, d_first_order, d_one_use_per_user]

# ---------------------------------------------------------------------------
# FILE 3: Volume_and_Tiered_Pricing.dmn
# ---------------------------------------------------------------------------

d_tiered_percent = {
    'kind': 'table', 'id': 'Decision_PromotionTieredPercentSelection',
    'name': 'Promotion Tiered Percent Discount Selection',
    'hit_policy': 'FIRST',
    'inputs': [{'var': 'orderAmount', 'label': 'Amount the calculator computes against', 'type': 'number'}],
    'outputs': [{'var': 'discountPercent', 'label': 'Percent applied by TieredPercent calculator', 'type': 'number'}],
    'rules': [
        {'conditions': ['>= 500'], 'outputs': ['20'], 'annotation': 'illustrative tier instance — preferred_tiers is a merchant-configured runtime hash, not a fixed set of breaks in the source'},
        {'conditions': ['>= 200'], 'outputs': ['10'], 'annotation': 'illustrative tier instance'},
        {'conditions': ['-'], 'outputs': ['basePercent'], 'annotation': 'falls through to preferred_base_percent when no configured tier threshold is met'},
    ],
}

d_price_adjustment_tier = {
    'kind': 'table', 'id': 'Decision_PriceListAdjustmentTierSelection',
    'name': 'Price List Volume Adjustment Tier Selection',
    'hit_policy': 'FIRST',
    'inputs': [{'var': 'purchaseQuantity', 'label': 'Quantity being priced', 'type': 'number'}],
    'outputs': [{'var': 'adjustmentPercentage', 'label': 'Percentage adjustment applied to base price', 'type': 'number'}],
    'rules': [
        {'conditions': ['>= 100'], 'outputs': ['-20'], 'annotation': 'illustrative band instance (>1 required, <1000, !=0 per PriceAdjustmentTier validations); mirrors the qty>100 example this case study was chosen to cover'},
        {'conditions': ['>= 50'], 'outputs': ['-10'], 'annotation': 'illustrative band instance'},
        {'conditions': ['-'], 'outputs': ['priceListBasePercentage'], 'annotation': 'falls through to the price_adjustment_percentage column when no band matches'},
    ],
}

d_tier_validity = {
    'kind': 'table', 'id': 'Decision_PriceAdjustmentTierValidity',
    'name': 'Price Adjustment Tier Validity Violations',
    'hit_policy': 'COLLECT',
    'inputs': [
        {'var': 'minQuantity', 'label': 'Tier min_quantity', 'type': 'number'},
        {'var': 'percentage', 'label': 'Tier percentage', 'type': 'number'},
        {'var': 'siblingTierCount', 'label': "Other tiers already on this list", 'type': 'number'},
    ],
    'outputs': [
        {'var': 'invalidReason', 'label': 'Validation failure reason', 'type': 'string'},
    ],
    'rules': [
        {'conditions': ['<= 1', '-', '-'], 'outputs': ['"min_quantity must be greater than 1"']},
        {'conditions': ['-', '<= -100', '-'], 'outputs': ['"percentage must be greater than -100"']},
        {'conditions': ['-', '>= 1000', '-'], 'outputs': ['"percentage must be less than 1000"']},
        {'conditions': ['-', '0', '-'], 'outputs': ['"percentage cannot be exactly zero"']},
        {'conditions': ['-', '-', '>= 10'], 'outputs': ['"too many tiers on this price list (cap is MAXIMUM_BREAKS_PER_VARIANT = 10)"']},
    ],
}

d_tier_valid_result = {
    'kind': 'literal', 'id': 'Decision_PriceAdjustmentTierValid',
    'name': 'Price Adjustment Tier Validity',
    'requires': ['Decision_PriceAdjustmentTierValidity'],
    'output': {'type': 'boolean'},
    'expression': 'count(invalidReasons) = 0',
}

FILE3_DECISIONS = [d_tiered_percent, d_price_adjustment_tier, d_tier_validity, d_tier_valid_result]
# REMOVED (2026-09-10, user instruction): Decision_PriceRuleVolumeApplicability
# ("Price Rule Volume Applicability", spree/core/app/models/spree/price_rules/volume_rule.rb:7-14).
# This was the program's one fully-untargetable decision for Spree (every input a
# schema gap: quantity/quantitySet are runtime scenario parameters, minQuantity/
# maxQuantity/maxQuantitySet live only in the opaque spree_price_rules.preferences
# blob). Removed on direct instruction, following the FLEX2 Revision-2 precedent
# (Academic_Honesty_Penalty.dmn, Honor_List_Eligibility.dmn) -- though note this
# case differs from that precedent: FLEX2's removed rules had zero relational
# representation anywhere, whereas here the values are persisted, just not in a
# directly-addressable column. Kept as a documented removal, not silently dropped
# -- see README.md's "Removed decisions" section.

# ---------------------------------------------------------------------------
FILES = {
    'Promotion_Order_Level_Eligibility.dmn': ('Promotion_Order_Level_Eligibility', FILE1_DECISIONS),
    'Customer_Segment_Eligibility.dmn': ('Customer_Segment_Eligibility', FILE2_DECISIONS),
    'Volume_and_Tiered_Pricing.dmn': ('Volume_and_Tiered_Pricing', FILE3_DECISIONS),
}

def main():
    out_dir = '/home/claude/spree_dmn/dmn'
    os.makedirs(out_dir, exist_ok=True)
    total_decisions = 0
    total_rules = 0
    for fname, (dname, decisions) in FILES.items():
        path = os.path.join(out_dir, fname)
        build_dmn_file(NS, dname, decisions, path)
        total_decisions += len(decisions)
        total_rules += sum(len(d['rules']) for d in decisions if d['kind'] == 'table')
        print(f"wrote {path}  ({len(decisions)} decisions)")
    print(f"\nTOTAL: {len(FILES)} files, {total_decisions} decisions, {total_rules} rule rows")

if __name__ == '__main__':
    main()
