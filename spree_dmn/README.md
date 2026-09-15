# Spree Commerce — DMN business rule extraction (first pass, 2026-09-10)

## Summary

- **14 decisions across 3 DMN files, 32 rule rows** (5 literal-expression helper
  decisions + 9 decision tables, 1 of which is COLLECT).
- **Revised 2026-09-10 (removal)**: `Price Rule Volume Applicability` removed.
- **Revised 2026-09-10 (addition, then further redesigned)**: `Price Adjustment Tier
  Validity` added, then split into a COLLECT violations table + a small downstream
  result decision — see "Redesign, round 3" below.
- **Revised 2026-09-10 (redesign, two rounds)**: `Promotion Item Total Eligibility`
  restructured twice — round 1 moved the operator strings into two upstream
  calculations; round 2 (final) collapsed the table to 2 columns / 4 rules with a FEEL
  range literal and switched to UNIQUE hit policy, validated exhaustive and
  non-overlapping by an in-session brute-force sweep. See "Redesign" sections below.
- Tier 2: mined directly from real Ruby source in `spree/spree` (BSD-3-Clause, core repo),
  read in full via `git sparse-checkout` against the live `main` branch, 2026-09-10.
- Schema-grounded against the real Spree schema extracted in the companion
  `spree_schema_summary.json` (197 tables, parsed from the squashed base migration +
  276 incremental Rails migrations — see `../spree_research/scripts/parse_spree_migrations.py`).

## Explicit design goal for this pass: minimize boolean-collapsed inputs

Unlike OpenMRS/OFBiz's initial drafts (74%/54% boolean-only decisions before the
FEEL-promotion revision), this pass was mined directly into FEEL-exposed form from the
start, the same way jBilling was. Result:

- **0 of 9 decision tables are boolean-only** (every table has at least one numeric,
  date, or derived-aggregate input driving real branch distance).
- **27 total decision-table inputs, of which 9 (33.3%) are boolean** — and every one of
  those 9 is a documented existence/presence check (`amountMaxSet`, `expiresAtSet`,
  `usageLimitSet`, `customerIdPresent`, `promotionTargetGroupsConfigured`,
  `quantitySet`, `maxQuantitySet`, `userOrEmailPresent`, `customerPresent`), not a
  pre-collapsed comparison — the same exception category §7c of the design doc already
  established for OpenMRS, not a new pattern.
- Three genuinely count-based facts that Spree's own source computes as booleans
  (`completed_orders.blank?`, `promotion.used_by?`, the array-intersection `.any?` in
  `CustomerGroup#eligible?`) were deliberately **un-collapsed into derived-aggregate
  counts** (`priorCompletedOrderCount`, `priorPromotionUsageCount`,
  `matchingCustomerGroupCount`) rather than left as booleans, each via its own
  literal-expression decision feeding a downstream decision table by DRD edge — directly
  reusing the FLEX2 attendance-percentage pattern (§4.2 revision 3 of the design doc) for
  a new domain.

## Redesign, round 1: operator resolved upstream (2026-09-10)

**The problem.** The original table modeled `operatorMin`/`operatorMax` (Spree's real
`OPERATORS_MIN = ['gt','gte']` / `OPERATORS_MAX = ['lt','lte']` constants) as
decision-table string columns, with `itemTotal`/`amountMin`/`amountMax` left as `"-"`
wildcards in every row — because plain DMN unary tests cannot parametrize a comparison
*operator* by another column's runtime value. That's a real DMN limitation, not a
mistake, but it produced a 6-column, 7-rule table that was mostly dashes and pushed the
actual numeric comparison out into a documented compile-time-substitution requirement
for `compile_constraints.py` rather than letting the DMN itself express it.

**The fix.** Reframed as a business modeler would: the operator isn't a business
decision a reviewer reads off a checklist — it only affects *where the threshold sits*.
So it's resolved once, upstream, into a single concrete number, the same "move the
arithmetic into a literal-expression decision" pattern already used for FLEX2's
attendance percentage (§4.2 Revision 3 of the design doc) and this case study's own
Customer Group Match Count / Prior Completed Order Count.

- **`Effective Minimum Amount Threshold`** (literal expression) =
  `if operatorMin = "gte" then amountMin else amountMin + 0.01`
- **`Effective Maximum Amount Threshold`** (literal expression) =
  `if operatorMax = "lte" then amountMax else amountMax - 0.01`
  (0.01 = one cent, matching Spree's decimal-money precision — not an arbitrary
  epsilon; documented as an assumption, same spirit as FLEX2's `Flex1.sql` seed-data
  caveats)
- **`Promotion Item Total Eligibility`** now takes these two thresholds as inputs
  instead of the raw operator strings, and shrinks to 4 columns / 3 rules with only
  one remaining dash-bearing column (`amountMaxSet`, a legitimate existence check):

  | itemTotal | effectiveMinThreshold | amountMaxSet | effectiveMaxThreshold | → eligible |
  |---|---|---|---|---|
  | `>= effectiveMinThreshold` | — | `false` | — | `true` |
  | `>= effectiveMinThreshold` | — | `true` | `<= effectiveMaxThreshold` | `true` |
  | — | — | — | — | `false` |

**What this actually buys, beyond readability:** the earlier version *documented* that
`compile_constraints.py` would need special-case logic to expand operator-selector rows
into literal FEEL comparisons before this decision was usable. That special case is now
gone — every FEEL comparison in this table is already the literal comparison the
generator needs, exactly like every other decision in this pass. One fewer documented
compiler special-case across the whole program.

## Redesign, round 2: UNIQUE + range literal (2026-09-10)

Went further than the round-1 redesign above. Two changes, applied together:

1. **Range literal**: `itemTotal`'s unary test became a FEEL interval —
   `[effectiveMinThreshold..effectiveMaxThreshold]` — instead of two separate bare
   comparisons (`>= effectiveMinThreshold`, `<= effectiveMaxThreshold`) sitting in two
   columns. The compiler now sees one shape ("value tested against a range") instead of
   two related-but-separately-named comparisons it has to know go together.
2. **UNIQUE hit policy**: made every row self-contained and non-overlapping (no reliance
   on row order or a final wildcard), which removes the FIRST-hit suppression term for
   this decision entirely — the design doc identifies that suppression term as the
   dominant source of search difficulty across 82.8% of the program's decision tables.

**Final shape — 2 columns, 4 rules, zero wildcards:**

| itemTotal | amountMaxSet | → itemTotalEligible |
|---|---|---|
| `>= effectiveMinThreshold` | `false` | `true` |
| `< effectiveMinThreshold` | `false` | `false` |
| `[effectiveMinThreshold..effectiveMaxThreshold]` | `true` | `true` |
| `not([effectiveMinThreshold..effectiveMaxThreshold])` | `true` | `false` |

**Completeness/uniqueness validated in-session** (not just asserted): a brute-force
sweep over `itemTotal` x `amountMaxSet` (202 combinations against representative
threshold values) confirmed exactly one rule matches every combination — zero gaps,
zero overlaps — the same guarantee a real DMN engine's static UNIQUE-hit-policy check
would provide. This is the strongest validation standard applied to any single decision
in this pass, going beyond the project's usual "XML well-formedness + arity" bar.

This decision was chosen for the B1 treatment specifically because both branches
(`amountMaxSet=false`/`true`) partition their respective `itemTotal` domains exactly by
construction (`>= t` / `< t`, and "in range" / "not in range"), which is what makes an
*exhaustive* UNIQUE rewrite provable rather than just plausible — not every decision in
this program has that property, so this treatment doesn't generalize to all of them
automatically (see the design-discussion turn preceding this revision for the fuller
menu of techniques and why UNIQUE-B1 specifically needs provable partition, not just
"seems to cover everything").

## Redesign, round 3: FIRST → COLLECT for Price Adjustment Tier Validity (2026-09-10)

**Why this decision specifically, and not the seven UNIQUE candidates above.** In
auditing all 8 remaining decisions for the UNIQUE treatment, `Price Adjustment Tier
Validity` was identified as fundamentally different: its five checks
(`minQuantity<=1`, `percentage<=-100`, `percentage>=1000`, `percentage=0`,
`siblingTierCount>=10`) are **independent, not nested** — two can be true
simultaneously (e.g. `minQuantity=0` and `percentage=0` at once). UNIQUE would have
required silently picking one priority order and calling it proven, which it wouldn't
have been. FIRST was honest about the priority-ordering but had a real faithfulness
cost: real Rails/ActiveRecord validations don't stop at the first failure — they
accumulate every violated validator into `record.errors`. FIRST could only ever report
one reason per invalid tier, even when the real system would report several.

**The change.** Split into two decisions:
- `Price Adjustment Tier Validity Violations` — now **COLLECT** hit policy, single
  output column (`invalidReason`), 5 independently-evaluable rules, no wildcard row.
  Every rule whose condition is true fires and contributes its reason to a list.
- `Price Adjustment Tier Validity` — a new, small literal-expression decision
  downstream (`count(invalidReasons) = 0`), replacing the `tierValid` column the old
  FIRST-hit table had.

**Consistency decision, discussed explicitly rather than made silently.** OpenMRS's
validator-mined decisions hit this exact same fork earlier in the project (several
`PersonValidator`/etc. checks are also independent, simultaneously-true-capable Java
`if` statements) and were deliberately kept FIRST at the time, documented as
*"collapses what the source implements as multiple independent if statements ... into
one FIRST-hit-policy verdict + single reason code ... at the cost of a more complex
downstream fitness function."* The user chose to revisit that decision and apply
COLLECT to **both** Spree and OpenMRS for consistency across the program, rather than
leave Spree as an unexplained exception. **The OpenMRS side of this change is not yet
applied** — `openmrs_dmn.zip`/`build_openmrs_dmn.py` are not present in this
environment (only the markdown write-up describing that earlier session's work is),
so nothing there could be edited without fabricating a change to a file this session
never had. This is tracked as an explicit, open follow-up, not silently dropped: once
that package is available, the same COLLECT treatment should be applied to whichever
OpenMRS decisions have the same independent-simultaneous-violations shape.

**What COLLECT costs, stated plainly rather than glossed over:**
- `invalidReason` is now a list, not a scalar — every downstream consumer (this
  mapping CSV, the English-language doc, eventually a SQL validation compiler) has to
  handle a collection.
- "Coverage" for this decision now needs a stated convention: target "this specific
  rule fires" (ignoring co-firing rules) rather than one of 2^5 possible co-firing
  combinations. This project adopts the former, consistent with how every other
  decision's "one target branch = one rule row" framing already works.
- This is the first COLLECT decision in the program (previously only FIRST and UNIQUE
  appeared), so §7a's hit-policy statistics (48/58 tables were FIRST, 82.8%) will need
  a third category once this is folded into the taxonomy CSVs.
- In exchange, COLLECT removes the FIRST-hit suppression term for this specific
  decision entirely, since every rule is independently evaluable — genuinely simpler
  for the fitness function, not just more faithful to the source.

## The 3 files / 14 decisions

- `Promotion_Order_Level_Eligibility.dmn` — Effective Minimum Amount Threshold (literal)
  and Effective Maximum Amount Threshold (literal) → Promotion Item Total Eligibility
  (DRD chain, redesigned per above); Promotion Temporal Availability; Promotion Usage
  Limit Exceeded
- `Customer_Segment_Eligibility.dmn` — Customer Group Match Count (literal) →
  Promotion Customer Group Eligibility (DRD chain); Prior Completed Order Count
  (literal) → First-Order Promotion Eligibility (DRD chain); One-Use-Per-User
  Promotion Eligibility
- `Volume_and_Tiered_Pricing.dmn` — Promotion Tiered Percent Discount Selection,
  Price List Volume Adjustment Tier Selection, **Price Adjustment Tier Validity
  Violations** (COLLECT) → **Price Adjustment Tier Validity** (DRD chain)

## Added decision (2026-09-10, later redesigned to COLLECT per "Redesign, round 3" above)

**`Price Adjustment Tier Validity Violations`** — mines the *other* half of
`price_adjustment_tier.rb` that Decision 10 (`Price List Volume Adjustment Tier
Selection`) doesn't cover: the real ActiveRecord validations that gate whether a tier
row can be created at all, rather than which tier applies at read time.
- `minQuantity <= 1` → violation (`numericality: greater_than: 1`)
- `percentage <= -100` → violation; `percentage >= 1000` → violation; `percentage = 0` →
  violation (`numericality: greater_than: -100, less_than: 1000, other_than: 0`)
- `siblingTierCount >= 10` → violation, capped by `Spree::Price::MAXIMUM_BREAKS_PER_VARIANT`
  (`spree/core/app/models/spree/price.rb:25`) — **a genuine fixed constant in source**,
  unlike Decisions 9/10's merchant-configured tier breakpoints, so this rule needed no
  Tier-4 illustrative-value caveat.
- All matching violations fire together (COLLECT); `Price Adjustment Tier Validity`
  (downstream) is `true` only when the violations list is empty.

Notably, this decision's `minQuantity` and `percentage` inputs are both **direct**
column hits (`spree_price_adjustment_tiers.min_quantity`/`.percentage`) — the same
genuine dedicated columns Decision 10 already used — so adding it improved the
mapping's `direct` share without needing any new schema-gap inputs.

## Removed decisions

- **`Price Rule Volume Applicability`** (was: `spree/core/app/models/spree/price_rules/volume_rule.rb:7-14`,
  4 rule rows) — removed 2026-09-10 on direct instruction, as this pass's one
  **fully-untargetable decision**: every input (`quantity`/`quantitySet`,
  `minQuantity`/`maxQuantity`/`maxQuantitySet`) was flagged `not-persisted` or
  `SCHEMA GAP (partial)`, so the branch could not be driven by generated data at all.
  Removal follows FLEX2's Revision-2 precedent (§4.2 of the design doc:
  `Academic_Honesty_Penalty.dmn`, `Honor_List_Eligibility.dmn`).
  **One difference from that precedent, worth stating plainly**: FLEX2's removed
  rules had *zero relational representation anywhere* (no table/column could ever
  store the fact). Here, `minQuantity`/`maxQuantity` genuinely are persisted — just
  opaquely, inside `spree_price_rules.preferences` (a serialized text blob) — and
  `quantity` is a legitimate runtime scenario parameter (the FLEX2 analogue is
  `offer_id`/`student_id`, which were *kept*, not removed, being expected external
  bindings rather than database gaps). This decision was removed on scope/preference
  grounds, the same kind of judgment call as the PrestaShop→jBilling swap, not because
  the underlying facts are structurally absent. Kept in
  `scripts/build_spree_dmn.py` as a commented-out, documented removal rather than
  silently deleted, so it can be reinstated if a future pass adds JSON-path-aware
  SQL compilation for the `preferences` blob pattern (see finding #2 below), which
  would resolve its schema gap without needing the rule itself to change.

**`Price List Volume Adjustment Tier Selection`** is the decision that most directly
matches the rule shape this case study was selected to cover — its first rule row
(`purchaseQuantity >= 100 -> adjustmentPercentage = -20`) is grounded in
`Spree::PriceAdjustmentTier`'s real validations (`min_quantity > 1`, `percentage` in
`(-100, 1000)` excluding 0) even though the specific breakpoint numbers are illustrative
(see Tier note below).

## Notable schema/code findings

1. **Spree has an explicit, code-commented "no DB-level foreign keys" convention** —
   `20260728000003_rename_user_id_to_customer_id.rb` (the migration that renamed
   `user_id`→`customer_id` across 9 tables as part of a 2026 user/customer model split)
   contains the comment *"Drop the lone DB-level FK constraint (Spree convention: no
   foreign key constraints)"* while removing the one remaining `add_foreign_key` on
   `spree_payment_sources`. This is a **stated, intentional convention**, not an
   accident of incremental migration history — a stronger, more citable version of the
   FK-light finding than a bare count (6 FKs / 197 tables) would have been on its own.
2. **A new opaque-storage pattern, a 4th instance of the "one generic column/table,
   many logical roles" finding this project keeps surfacing per case study** (OpenMRS:
   Boolean-via-`value_coded`; OFBiz: `WorkEffort` reused for production runs/tasks;
   jBilling: pricing delegated to an external, unavailable Drools engine): **every
   `Spree::PromotionRule` and `Spree::PriceRule` subtype's actual parameters
   (`amount_min`, `operator_min`, `min_quantity`, `customer_group_ids`, etc.) are
   serialized into one shared `preferences` text column**, discriminated only by the
   row's `type` STI string. Nothing is missing from the database — the value genuinely
   is persisted — but it is not a directly SQL-addressable column the way
   `spree_price_adjustment_tiers.percentage` is; §6.7's SQL-compiled validation step
   would need a JSON/YAML-path expression rather than a plain column reference for 11 of
   this pass's 43 mapped variables (25.6%, all flagged `SCHEMA GAP (partial)` rather
   than a full gap, since the fact is stored, just not in a directly queryable place).
   Worth proposing as a genuinely new §7b construct category (e.g. "Serialized
   Preference/Config Blob") rather than folding it into the existing "Not-Persisted"
   bucket, since it is a different translatability problem than a true schema gap.
3. **`spree_orders.customer_id` (and 8 other columns) did not exist under that name
   until 2026-07-28** — the base squashed migration and most of Spree's history used
   `user_id`; the rename migration cited above retrofits the newer "Customer" domain
   model onto the older "User" one. A researcher citing an older Spree fork/tag would
   find `user_id`, not `customer_id` — flagged here since this project's source was
   read against the live `main` branch on 2026-09-10, not a pinned older release the
   way jBilling deliberately used a pinned 2011 commit.
4. **Tiered-discount breakpoints are runtime data, not source code** — both
   `Calculator::TieredPercent#compute` and the domain logic behind
   `spree_price_adjustment_tiers` implement a *mechanism* (sort tiers descending, take
   the first whose threshold the amount/quantity clears) rather than fixed numbers. The
   mechanism is Tier 2 (real, cited code); the specific breakpoint literals used in this
   pass's rule rows (500/200, 100/50) are Tier 4 (researcher-illustrative instances of
   that mechanism), consistent with how the design doc already treats FLEX2's own
   derived-calculation decisions with no numbered source clause.

## Mapping summary (44 variables across all 14 decisions)

| mapping_type | count | % |
|---|---|---|
| not-persisted | 14 | 31.8% |
| direct | 8 | 18.2% |
| SCHEMA GAP (partial) | 8 | 18.2% |
| derived | 8 | 18.2% |
| derived-aggregate | 6 | 13.6% |

Combined gap share (not-persisted + SCHEMA GAP) is **50.0%**. This ticked up slightly
from 47.6% purely because the redesign added two new `not-persisted` formula-output
variables (`effectiveMinThreshold`/`effectiveMaxThreshold`) without changing how many
underlying facts are actually gap-affected — `operatorMin`/`amountMin`/`operatorMax`/
`amountMax` were gap-flagged before the redesign too, they've just moved to a different
decision name. Worth stating plainly so this isn't misread as the redesign making the
schema-mapping picture worse: it didn't change a single fact's grounding, only where in
the DMN that fact is consumed.

**Decision-level and input-only stats:**

| Metric | Value |
|---|---|
| Decisions with >=1 gap variable (any input/output) | 11/11 (100%) |
| Fully-untargetable decisions (every INPUT a gap) | **0** |

Same caveat as before applies to the 100% figure — see the prior revision's note.

## Deliverable structure

```
spree_dmn/
├── README.md
├── dmn/                                   3 DMN 1.3 files, 11 decisions
├── scripts/
│   ├── dmn_builder.py                     minimal DMN 1.3 + DRD generator (decision tables + literal expressions)
│   └── build_spree_dmn.py                 the 11 decisions as data
└── provenance/
    ├── rule_provenance_matrix.csv         one row per rule group: file, lines, tier, note
    └── variable_to_schema_mapping.csv     one row per DMN variable: schema location / mapping type / note
```

## Caveats

- XML well-formedness and per-rule input/output arity validated in-session (all 3 files
  pass; script re-run confirmed `ALL CLEAR`) — not executed against a live Camunda 7
  engine, consistent with this project's existing validation standard for all other case
  studies (see the design doc's §10).
- The `Promotion Item Total Eligibility` table encodes `operatorMin`/`operatorMax` as
  row-selector inputs rather than parametrizing the comparison operator itself, since
  plain DMN unary tests cannot do that — `compile_constraints.py` (§6.1 of the design
  doc) will need to expand each matched row into the literal FEEL comparison
  (`itemTotal >= amountMin` vs. `itemTotal > amountMin`) rather than treat the `"-"`
  placeholders in this table as real wildcards.
- This is a first pass (9 decisions, 3 files) — smaller in scale than OpenMRS's 19 or
  jBilling's 16 initial passes. `Spree::Promotion::Rules::Product`, `Taxon`,
  `OptionValue`, `Country`, `Currency`, `Channel`, `Market` and the shipping-side
  calculators (`FlexiRate`, `PerItem`) were not mined in this pass and remain natural
  candidates for a follow-up, the same way FLEX2 and OpenMRS both had deferred-rule
  sections after their first pass.
- `Calculator` preferences (the `base_percent`/`tiers` hash backing
  `Promotion Tiered Percent Discount Selection`) live on the polymorphic
  `spree_calculators` table, which was not pulled into this schema extraction pass —
  flagged in the mapping CSV as a gap in this pass's schema coverage, not a gap in
  Spree's schema itself.
