# jBilling DMN Package (Case Study #4, replacing PrestaShop, 2026-09-10)

16 decisions / 5 files / 53 rule rows, mined from a local sparse-checkout clone
of jBilling (fork `mosabsalih/jBilling`, branch `master`, commit `748ed1d`,
"Fixed exception with more than one subscription to an item", 2011-09-27),
following the identical Tier-2 code-mining methodology used for OpenMRS and
Apache OFBiz (real source read in full, cited file+line+method, only
fixed-arity/single-row/genuinely-branching logic modeled, real thresholds
promoted to FEEL comparisons rather than left as pre-collapsed booleans except
for documented deliberate exceptions).

## Revision: boolean-reduction pass (2026-09-10)

Same audit as Spree/OpenMRS/FLEX2. jBilling started at **30/42 boolean inputs
(71.4%)**, higher than FLEX2's original 45.5% and closer to OpenMRS's pre-revision
state. Every boolean in all 16 decisions was checked against the real Java source in
`source_documents/` before deciding convert-vs-keep.

**4 variables converted** (all genuine pre-collapsed date/number comparisons):

| Variable | Decision | Real fact | Fix |
|---|---|---|---|
| `startBeforeEnd` | Order Date Range Valid | Date comparison between two DTO fields | Exposed as `startDate`/`endDate`, cross-variable `<`/`>=` |
| `newActiveUntilBeforeOld` | Cancellation Fee Eligibility | Date comparison, `purchase_order.active_until` old vs. new | Exposed as `newActiveUntil`/`oldActiveUntil`, cross-variable |
| `quantityDecreased` | Cancellation Fee Eligibility | Number comparison, `order_line.quantity` old vs. new | Exposed as `newQuantity`/`oldQuantity`, cross-variable |
| `candidateDateBeforeNextBillableDay` | Order Period Already Invoiced | Date comparison vs. `purchase_order.next_billable_day` | Exposed as `candidateDate`/`nextBillableDay`, cross-variable |

**Everything else re-confirmed as genuinely boolean, not left unchecked**:
`Ageing Step Advancement`'s `ageingStepConfigFound` is a documented pure-existence
check (comment already in the source); `Ageing Status Change Order Action`'s three
booleans (`newStatusIsDeleted`, `oldStatusCanLogin`, `newStatusCanLogin`) are real
schema columns (`can_login`, confirmed in this project's own earlier case-study
findings); `Payment Outcome Resolution`'s `processorUnavailable` is a real loop-exit
state flag with `paymentResultId` already numeric passthrough;
`Ageing Step Config Validation`'s status/existence flags are genuine, matching the
design doc's own prior characterization.

**Result:**

| Metric | Before | After |
|---|---|---|
| Boolean decision-table inputs | 30/42 (71.4%) | **26/46 (56.5%)** |
| All-boolean decision tables | 7/16 (43.8%) | **5/16 (31.3%)** |

Validated: XML well-formedness + arity clean across all 5 files (16 decisions); full
DMN↔mapping-CSV cross-check clean (63 rows).

## Structure



```
jbilling_dmn/
├── README.md
├── dmn/                                  5 Camunda-7-compatible DMN 1.3 files
│   ├── Ageing_and_Dunning.dmn                 5 decisions / 17 rules
│   ├── Payment_Authorization_and_Blacklist.dmn 3 decisions / 6 rules
│   ├── Order_Cancellation_and_Validity.dmn    3 decisions / 15 rules
│   ├── Proration_and_Tax.dmn                  4 decisions / 12 rules
│   └── Currency_Exchange_Rules.dmn            1 decision / 3 rules
├── scripts/
│   ├── dmn_builder.py                    reused, unmodified DMN 1.3 + DRD/DMNDI generator
│   ├── build_jbilling_dmn.py             the 16 decisions as data + provenance-CSV generator
│   └── build_jbilling_mapping.py         schema mapping CSV generator
├── provenance/
│   ├── rule_provenance_matrix.csv        one row per decision: citation, tier, hit policy, description
│   └── variable_to_schema_mapping.csv    one row per DMN variable: jBilling table.column / formula / gap flag (59 rows)
└── source_documents/                     mined Java source files, kept for self-containment
```

## Notable findings

- **Pluggable-task architecture**: ageing/dunning logic lives in `BasicAgeingTask`
  and a `BusinessDayAgeingTask` subclass that recomputes the same date-driven
  checks in business days instead of calendar days — both variants collapse to
  the same DMN comparison logic, so one table covers both.
- **A real boundary inconsistency, preserved rather than silently fixed**: a step
  that expires exactly "today" is due for advancement (`<=`), but an invoice due
  exactly "today" is *not yet* overdue (`<`) — see decisions 1–2.
- **A genuinely new exclusion finding**: `server/item/tasks`' pricing logic
  delegates to an external Drools `.drl` rules engine not present in this source
  tree — an opaque, code-external rules layer, excluded rather than mined as a
  false decision table (distinct from every other case study's exclusion reasons).
- **One deliberately un-chained DRD edge**: Daily Pro-Rate Amount is *not* linked
  to Cycle Start Source in the DRD, even though they look related, because the
  real data path between them runs through an unread superclass
  (`BasicOrderPeriodTask`) — documented as a code comment rather than asserted.

## Validation

`validate_dmn.py` (XML well-formedness, per-rule arity, cross-variable FEEL
reference resolution, exact DMN↔mapping-CSV variable-set consistency):
**ALL CLEAR** — 59 DMN variables = 59 CSV variables, 0 issues.

## Context

This case study replaced PrestaShop as case study #4 in the ongoing
four-case-study program (FLEX2, OpenMRS, Apache OFBiz, jBilling) — see
`case-study-selection.md`'s "PrestaShop → jBilling swap" section and
`generation-algorithm-design.md` §2/§7e for the full rationale, gains, and
losses.
