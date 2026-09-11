# Spree Commerce — DMN rules in plain English

Companion to `spree_dmn.zip`'s DMN files, in the same spirit as the project's
`docwork/all_rules_english_open_source.md` for OpenMRS/OFBiz/(historically)PrestaShop.
14 decisions, 3 files, 32 rule rows (post-removal of `Price Rule Volume Applicability`,
post-addition of `Price Adjustment Tier Validity`, post-redesign of `Promotion Item
Total Eligibility` to a UNIQUE-hit-policy, range-literal, fully exhaustive table —
all 2026-09-10).

---

## File 1: `Promotion_Order_Level_Eligibility.dmn`

### Decision 1a — Effective Minimum Amount Threshold *(calculation, feeds Decision 1c)*
*Real-world question: what's the actual number the order total must clear, once we've
resolved whether the merchant meant "at least" or "strictly more than"?*

A formula, not a branch: if the minimum is inclusive, the threshold is just the
configured amount; if it's strict, the threshold is nudged up by one cent (below that
cent, the order is not eligible; at or above it, it is — Spree stores money to cent
precision, so a cent is the smallest meaningful gap).

### Decision 1b — Effective Maximum Amount Threshold *(calculation, feeds Decision 1c)*
Same idea, mirrored for the maximum: if inclusive, use the configured amount as-is; if
strict, nudge it down by one cent.

### Decision 1c — Promotion Item Total Eligibility
*Real-world question: does this order's total qualify it for a "spend at least / at most
this much" promotion (e.g. "10% off orders over $100")?*

A clean, exhaustive checklist against the two already-resolved thresholds from 1a/1b —
every possible order total and every possible "is there a maximum" state is covered by
exactly one row, so there's no fallback/"none of the above" case at all:

1. No maximum is configured, and the order total meets or exceeds the effective minimum → **eligible**.
2. No maximum is configured, and the order total is below the effective minimum → **not eligible**.
3. A maximum is configured, and the order total falls within the effective [minimum, maximum] range → **eligible**.
4. A maximum is configured, and the order total falls outside that range → **not eligible**.

### Decision 2 — Promotion Temporal Availability
*Real-world question: is this promotion live right now, not yet started, or already over?*

1. The evaluation time is before the promotion's start date → **not yet started**.
2. An expiry date is configured and the evaluation time is after it → **expired**.
3. Otherwise → **active**.

### Decision 3 — Promotion Usage Limit Exceeded
*Real-world question: has this promotion been redeemed as many times as the merchant allows?*

1. No usage limit is configured → **not exceeded** (unlimited use).
2. A usage limit is configured but it's zero or negative (effectively disabled) → **not exceeded**.
3. A usage limit is configured, it's positive, and the number of times it's already been
   credited has reached or passed that limit → **exceeded**.
4. Anything else → **not exceeded**.

---

## File 2: `Customer_Segment_Eligibility.dmn`

### Decision 4 — Customer Group Match Count *(calculation, feeds Decision 5)*
*Real-world question: how many of the customer's group memberships overlap with the
groups this promotion is targeting?*

Not a branching rule — a formula: count how many customer-group IDs the customer belongs
to also appear in the promotion's list of targeted customer groups. (This is your "is the
customer Gold?" check, generalized to however many groups a promotion can target at once.)

### Decision 5 — Promotion Customer Group Eligibility
*Real-world question: does this customer belong to a group this promotion is restricted to?*

1. The order has no identified customer → **not eligible**.
2. The promotion isn't actually restricted to any customer group → **not eligible**
   (a promotion with an empty group list matches nobody, by Spree's own design).
3. The customer's group memberships overlap with the promotion's targeted groups by at
   least one group (using Decision 4's count) → **eligible**.
4. Anything else → **not eligible**.

### Decision 6 — Prior Completed Order Count *(calculation, feeds Decision 7)*
*Real-world question: how many completed orders has this customer (or email address)
placed before, at this store, excluding the order currently being checked?*

A count, not a branch — feeds directly into "is this their first order?"

### Decision 7 — First-Order Promotion Eligibility
*Real-world question: does this promotion (e.g. "10% off your first order") apply?*

1. Neither a customer nor an email address is known for this order → **not eligible**
   (nothing to check history against).
2. The customer has zero prior completed orders (using Decision 6's count) → **eligible**.
3. Anything else (they have at least one prior completed order) → **not eligible**.

### Decision 8 — One-Use-Per-User Promotion Eligibility
*Real-world question: has this customer already used this specific promotion before?*

1. The order has no identified customer → **not eligible** (can't check history).
2. This customer has used this promotion zero times before → **eligible**.
3. Anything else (they've used it at least once already) → **not eligible**.

---

## File 3: `Volume_and_Tiered_Pricing.dmn`

### Decision 9 — Promotion Tiered Percent Discount Selection
*Real-world question: what percentage discount does a "bigger spend, bigger discount"
promotion apply, given the order amount?*

The merchant configures a ladder of amount thresholds, each with its own percentage,
plus a base percentage for anyone below the lowest threshold. The order amount is
checked against the ladder from the top down and the first threshold it clears wins.

1. Order amount is $500 or more → **20% off** *(illustrative tier — see note below)*.
2. Order amount is $200 or more (but under $500) → **10% off** *(illustrative tier)*.
3. Anything else → the merchant's configured **base percentage** applies.

*Note: the specific numbers (500/200, 20%/10%) are illustrative stand-ins — Spree stores
the actual thresholds as a merchant-configured table at runtime, not fixed values in the
source code. The **mechanism** (highest-qualifying-threshold-wins) is real and mined
directly from `Calculator::TieredPercent#compute`.*

### Decision 10 — Price List Volume Adjustment Tier Selection
*Real-world question: for a price list that gives volume discounts, what percentage
adjustment applies at a given purchase quantity?* — **this is the closest match to the
original example rule this case study was chosen to cover** ("gold customer buying
100+ units gets 10% off" — here it's "buying 100+ units gets 20% off," with the
customer-segment gating handled separately by Decisions 4–5 and the price-list
assignment itself).

1. Purchase quantity is 100 or more → **20% off** *(illustrative band)*.
2. Purchase quantity is 50 or more (but under 100) → **10% off** *(illustrative band)*.
3. Anything else → the price list's own **base percentage** column applies.

*Same illustrative-numbers caveat as Decision 9 — the band structure and its validation
rules (must be an integer quantity greater than 1, percentage strictly between -100 and
1000, never exactly 0) are real and mined from `PriceAdjustmentTier`; the specific
100/50 breakpoints are researcher-chosen instances of that real structure.*

### Decision 11a — Price Adjustment Tier Validity Violations
*Real-world question: everything wrong with a proposed volume-discount band, all at once.*

This is a different question from Decision 10 — not "which tier applies," but "is this
tier configuration itself valid." Unlike every other gate in this document, this one
doesn't stop at the first problem it finds — it checks all five conditions
independently and reports **every one that applies**, since a real tier could fail more
than one check at the same time (e.g. a zero quantity *and* a zero percentage), and
Spree's own validation layer reports all of them, not just the first:

1. The minimum quantity is 1 or less → **violation**: "min_quantity must be greater than 1."
2. The percentage is -100 or lower → **violation**: "percentage must be greater than -100."
3. The percentage is 1000 or higher → **violation**: "percentage must be less than 1000."
4. The percentage is exactly 0 → **violation**: "percentage cannot be exactly zero" — a
   zero-percent band would mean "no discount," which Spree treats as "remove the band,"
   not "keep a band that does nothing."
5. The price list already has 10 other tiers → **violation**: "too many tiers" — this
   cap, unlike the tier breakpoints in Decisions 9/10, is a real fixed constant in the
   source, not something a merchant configures.

If none of these apply, nothing fires — an empty list of violations.

### Decision 11b — Price Adjustment Tier Validity
*Real-world question: taking all of 11a's findings together, is the tier valid or not?*

A one-line formula: valid if and only if 11a's violation list came back empty.

---

## Quick reference: which decisions are "gates" vs "calculations"

| # | Decision | Type |
|---|---|---|
| 1a | Effective Minimum Amount Threshold | Calculation (feeds #1c) |
| 1b | Effective Maximum Amount Threshold | Calculation (feeds #1c) |
| 1c | Promotion Item Total Eligibility | Gate (eligible / not) |
| 2 | Promotion Temporal Availability | Classification (3-way status) |
| 3 | Promotion Usage Limit Exceeded | Gate |
| 4 | Customer Group Match Count | Calculation (feeds #5) |
| 5 | Promotion Customer Group Eligibility | Gate |
| 6 | Prior Completed Order Count | Calculation (feeds #7) |
| 7 | First-Order Promotion Eligibility | Gate |
| 8 | One-Use-Per-User Promotion Eligibility | Gate |
| 9 | Promotion Tiered Percent Discount Selection | Calculation (picks a %) |
| 10 | Price List Volume Adjustment Tier Selection | Calculation (picks a %) |
| 11a | Price Adjustment Tier Validity Violations | Gate (COLLECT — reports all violations) |
| 11b | Price Adjustment Tier Validity | Calculation (feeds nothing further; final verdict) |

10 gates/classifications, 6 calculations (#1a/#1b resolve an operator into a threshold;
#4/#6 avoid a boolean-collapsed input; #11b reduces a violation list to one verdict).
One decision (#11a) uses COLLECT instead of FIRST/UNIQUE — chosen specifically because
its five checks are independent and can be simultaneously true, unlike every other gate
in this document, where FIRST or UNIQUE's implicit ordering is faithful to the source.
