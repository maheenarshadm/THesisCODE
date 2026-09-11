#!/usr/bin/env python3
"""
Builds the jBilling DMN case-study artifacts (fourth and final case study,
replacing PrestaShop -- decided 2026-09-10):
  - 5 .dmn files (Camunda 7 compatible) under ../dmn/
  - provenance/rule_provenance_matrix.csv (Tier-2: file path + line citations
    into jBilling Java source, mirroring OpenMRS/OFBiz's validator/service
    mining approach)

All 16 decisions below are mined from real Java source classes in a local
sparse-checkout clone of the jBilling repository (fork: mosabsalih/jBilling,
branch master, commit 748ed1d "Fixed exception with more than one
subscription to an item", 2011-09-27 -- this is the same jBilling snapshot
this project's earlier case-study-selection research already had a static
schema/table count for), read in full from
scratchpad/schemas/jbilling/src/java/com/sapienter/jbilling/... on 2026-09-10.
Source files used for citation are additionally copied into
scratchpad/jbilling_sources/*.java for self-containment (matching FLEX2's
source_documents/ precedent, since this is a local clone rather than a
GitHub-raw fetch like OpenMRS/OFBiz/PrestaShop used).

Unlike OpenMRS's single-purpose validator classes, jBilling's business logic
lives inside a mix of small "BL" (business-logic) façade classes, pluggable
Quartz-scheduled Task classes (the ageing/dunning module), and pluggable
Task classes that partly delegate to an external Drools rules engine (item
pricing) which this source tree does not include -- see the Proration_and_Tax
and Currency_Exchange_Rules sections' notes for exactly where that boundary
falls.
"""
import csv
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from dmn_builder import write_dmn


def R(inp, out, desc=None):
    return {'in': inp, 'out': out, 'desc': desc}


REPO = "mosabsalih/jBilling"
BRANCH = "master"
COMMIT = "748ed1d"


def src(module_path, file, lines, method=None):
    m = f" ({method})" if method else ""
    return f"{module_path}/{file}:{lines}{m} [{REPO}@{BRANCH}, commit {COMMIT}]"


PROCESS_PATH = "src/java/com/sapienter/jbilling/server/process"
PROCESS_TASK_PATH = "src/java/com/sapienter/jbilling/server/process/task"
PAYMENT_PATH = "src/java/com/sapienter/jbilling/server/payment"
BLACKLIST_PATH = "src/java/com/sapienter/jbilling/server/payment/blacklist"
ORDER_PATH = "src/java/com/sapienter/jbilling/server/order"
ORDER_TASK_PATH = "src/java/com/sapienter/jbilling/server/order/task"
ORDER_VALIDATOR_PATH = "src/java/com/sapienter/jbilling/server/order/validator"
ITEM_PATH = "src/java/com/sapienter/jbilling/server/item"
ITEM_TASK_PATH = "src/java/com/sapienter/jbilling/server/item/tasks"

# ---------------------------------------------------------------------------
# SOURCE_MAP: decision id -> provenance citation
# ---------------------------------------------------------------------------
SOURCE_MAP = {
    # -- Ageing_and_Dunning.dmn --
    'Decision_IsAgeingRequired': src(PROCESS_TASK_PATH, 'BasicAgeingTask.java', 'L230-248', 'isAgeingRequired')
        + " / " + src(PROCESS_TASK_PATH, 'BusinessDayAgeingTask.java', 'L80-98', 'isAgeingRequired override'),
    'Decision_InvoiceOverdue': src(PROCESS_TASK_PATH, 'BasicAgeingTask.java', 'L206-220', 'isInvoiceOverdue')
        + " / " + src(PROCESS_TASK_PATH, 'BusinessDayAgeingTask.java', 'L63-78', 'isInvoiceOverdue override'),
    'Decision_AgeingStepAdvancement': src(PROCESS_TASK_PATH, 'BasicAgeingTask.java', 'L150-195', 'ageUser'),
    'Decision_AgeingStatusChangeOrderAction': src(PROCESS_TASK_PATH, 'BasicAgeingTask.java', 'L300-375', 'setUserStatus'),
    'Decision_AgeingStepConfigValidation': src(PROCESS_PATH, 'AgeingBL.java', 'L182-231', 'validate'),
    # -- Payment_Authorization_and_Blacklist.dmn --
    'Decision_PaymentOutcomeResolution': src(PAYMENT_PATH, 'PaymentBL.java', 'L302-344', 'processPayment'),
    'Decision_PaymentBalanceAssignment': src(PAYMENT_PATH, 'PaymentBL.java', 'L346-351', 'processPayment'),
    'Decision_BlacklistFilterEnabled': src(BLACKLIST_PATH, 'BlacklistBL.java', 'L114-131', 'getBlacklistPluginId / isBlacklistEnabled'),
    # -- Order_Cancellation_and_Validity.dmn --
    'Decision_CancellationFeeEligibility': src(ORDER_TASK_PATH, 'CancellationFeeRulesTask.java', 'L70-109', 'process'),
    'Decision_OrderPeriodAlreadyInvoiced': src(ORDER_PATH, 'OrderBL.java', 'L1105-1108', 'isDateInvoiced'),
    'Decision_OrderDateRangeValid': src(ORDER_VALIDATOR_PATH, 'DateRangeValidator.java', 'L57-85', 'isValid'),
    # -- Proration_and_Tax.dmn --
    'Decision_CycleStartSource': src(PROCESS_TASK_PATH, 'ProRateOrderPeriodTask.java', 'L76-87', 'calculateCycleStarts'),
    'Decision_DailyProRateAmount': src(PROCESS_TASK_PATH, 'DailyProRateCompositionTask.java', 'L38-58', 'calculatePeriodAmount'),
    'Decision_TaxCalculationNeeded': src(PROCESS_TASK_PATH, 'SimpleTaxCompositionTask.java', 'L160-179', 'isTaxCalculationNeeded'),
    'Decision_TaxCalculationMode': src(PROCESS_TASK_PATH, 'SimpleTaxCompositionTask.java', 'L97-146', 'apply'),
    # -- Currency_Exchange_Rules.dmn --
    'Decision_CurrencyExchangeRateSource': src(ITEM_PATH, 'CurrencyBL.java', 'L324-336', 'findExchange'),
}

DECISION_DESC = {
    'Decision_IsAgeingRequired': "Determines whether a user who is already sitting in an ageing (dunning) step has spent long enough in that step to be pushed to the next one.",
    'Decision_InvoiceOverdue': "Determines whether a single invoice is overdue once the entity-wide grace period is applied to its due date.",
    'Decision_AgeingStepAdvancement': "Decides, for one user being reviewed, whether they should be advanced to the next configured ageing step and why (first entry into ageing, normal step expiry, or recovery from an invalid/removed step configuration).",
    'Decision_AgeingStatusChangeOrderAction': "Given an ageing status transition for one user, decides what happens to that user's active orders (suspend, reactivate, delete the account, or nothing), based on the login-capability of the old vs. new status.",
    'Decision_AgeingStepConfigValidation': "Validates a single ageing-step configuration row (per user status) before it is saved: welcome-message presence, non-zero day thresholds, and the special zero-day rule for the last configured step.",
    'Decision_PaymentOutcomeResolution': "Resolves the final payment result code once every configured pluggable payment-processor task has been tried, forcing an UNAVAILABLE code if no processor ever became reachable.",
    'Decision_PaymentBalanceAssignment': "Sets a payment's outstanding balance to the full amount on success/manually-entered, or zero on failure/unavailable, based on the resolved outcome.",
    'Decision_BlacklistFilterEnabled': "Determines whether entity-level fraud/blacklist payment filtering is active, based on a plug-in id stored in the generic entity preference table.",
    'Decision_CancellationFeeEligibility': "Decides whether a cancellation-fee-triggering event (an order's end date pulled earlier, or a line's quantity reduced) should actually generate a fee, or be silently skipped as a non-cancelling change.",
    'Decision_OrderPeriodAlreadyInvoiced': "Determines whether a given date falls before an order's already-committed next billable day, meaning a billing period that was already invoiced would be cut short.",
    'Decision_OrderDateRangeValid': "Generic validation rule enforcing that an annotated start-date field is chronologically before its paired end-date field, tolerating missing dates and treating reflection/parse failures as invalid.",
    'Decision_CycleStartSource': "Picks which date seeds a subscription's next billing cycle: the order's next-billable-day, its cycle-start date, or the caller-supplied period start, in that priority order.",
    'Decision_DailyProRateAmount': "Computes the day-based prorated charge for a partial billing period, with short-circuit guards for one-time orders and for full (non-partial) periods.",
    'Decision_TaxCalculationNeeded': "Decides whether an invoice should get a tax line at all, based on an optional customer tax-exemption custom contact field.",
    'Decision_TaxCalculationMode': "Decides whether the configured tax item is applied as a percentage of the invoice total or as a flat additional charge.",
    'Decision_CurrencyExchangeRateSource': "Decides which currency_exchange row (entity-specific, system-default, or none) supplies the rate used for a currency conversion.",
}

# ---------------------------------------------------------------------------
# File 1: Ageing_and_Dunning.dmn
# ---------------------------------------------------------------------------

d_is_ageing_required = {
    'id': 'Decision_IsAgeingRequired', 'name': 'Is Ageing Required',
    'hit_policy': 'FIRST', 'requires': [],
    'inputs': [
        # DERIVED: lastStatusChange (or createDatetime if null) + currentStep.days,
        # computed as calendar days (BasicAgeingTask) or business days -- skipping
        # weekends and an optional holiday file -- (BusinessDayAgeingTask). Both
        # subclasses compute this date differently but apply the identical
        # comparison rule below, so one table covers both pluggable-task variants;
        # the date-math strategy itself is not DMN-comparison-shaped and lives
        # upstream of this table.
        {'label': 'Expiry Date', 'expr': 'expiryDate', 'type': 'date'},
    ],
    'outputs': [
        {'label': 'Ageing Required', 'name': 'ageingRequired', 'type': 'boolean'},
    ],
    'rules': [
        R(['<= today()'], ['true'],
          'BasicAgeingTask.java L239-243 (mirrored in BusinessDayAgeingTask.java L89-93): '
          'expiryDate.equals(today) || expiryDate.before(today) -> ageing required (note: <=, i.e. equals-or-before)'),
        R(['-'], ['false'],
          'BasicAgeingTask.java L245-247 (mirrored in BusinessDayAgeingTask.java L95-97): otherwise not yet required'),
    ],
}

d_invoice_overdue = {
    'id': 'Decision_InvoiceOverdue', 'name': 'Invoice Overdue Check',
    'hit_policy': 'FIRST', 'requires': [],
    'inputs': [
        # DERIVED: invoice.due_date + the entity's process.grace_period preference,
        # added as calendar days (BasicAgeingTask) or business days (BusinessDayAgeingTask).
        {'label': 'Invoice Due Date Plus Grace', 'expr': 'dueDatePlusGrace', 'type': 'date'},
    ],
    'outputs': [
        {'label': 'Invoice Overdue', 'name': 'invoiceOverdue', 'type': 'boolean'},
    ],
    'rules': [
        R(['< today()'], ['true'],
          'BasicAgeingTask.java L211-215 (mirrored in BusinessDayAgeingTask.java L69-73): '
          'dueDate+gracePeriod.before(today) -> overdue (strict <, unlike the <= used in Is Ageing Required -- '
          'a step that expires exactly "today" is due for advancement, but an invoice due exactly "today" is '
          'NOT yet overdue -- a real one-day boundary inconsistency between the two checks)'),
        R(['-'], ['false'],
          'BasicAgeingTask.java L217-219 (mirrored in BusinessDayAgeingTask.java L75-77): otherwise not overdue'),
    ],
}

d_ageing_step_advancement = {
    'id': 'Decision_AgeingStepAdvancement', 'name': 'Ageing Step Advancement',
    'hit_policy': 'FIRST', 'requires': ['Decision_IsAgeingRequired'],
    'inputs': [
        {'label': 'Current Status Is Active', 'expr': 'currentStatusIsActive', 'type': 'boolean'},
        # boolean by deliberate exception: pure existence check (does an
        # ageing_entity_step row exist for entity_id+status_id, via
        # AgeingEntityStepDAS.findStep) -- not a value comparison a DMN column
        # could express any richer than true/false.
        {'label': 'Ageing Step Config Found', 'expr': 'ageingStepConfigFound', 'type': 'boolean'},
        {'label': 'Ageing Required', 'expr': 'ageingRequired', 'type': 'boolean'},
    ],
    'outputs': [
        {'label': 'Advance To Next Step', 'name': 'advanceToNextStep', 'type': 'boolean'},
        {'label': 'Advancement Reason', 'name': 'advancementReason', 'type': 'string',
         'values': '"INITIAL_STEP","STEP_EXPIRED","INVALID_STEP_RECOVERY","NO_ACTION"'},
    ],
    'rules': [
        R(['true', '-', '-'], ['true', '"INITIAL_STEP"'],
          'L157-159: currentStatusId==STATUS_ACTIVE -> nextStatus = getNextAgeingStep(steps, ACTIVE) (send welcome step)'),
        R(['false', 'false', '-'], ['true', '"INVALID_STEP_RECOVERY"'],
          'L163,172-177: ageingStep lookup returns null (removed/bad config) -> force-advance to next step regardless '
          'of elapsed time, logged as a warning'),
        R(['false', 'true', 'true'], ['true', '"STEP_EXPIRED"'],
          'L163-171 (isAgeingRequired call at L167): step config found and user has spent >= configured days in it -> advance'),
        R(['false', 'true', 'false'], ['false', '"NO_ACTION"'],
          'L165-171 implicit else: step config found but not yet expired -> nextStatus stays null, no advancement'),
    ],
}

d_ageing_status_change_order_action = {
    'id': 'Decision_AgeingStatusChangeOrderAction', 'name': 'Ageing Status Change Order Action',
    'hit_policy': 'FIRST', 'requires': ['Decision_AgeingStepAdvancement'],
    'inputs': [
        {'label': 'New Status Is Deleted', 'expr': 'newStatusIsDeleted', 'type': 'boolean'},
        {'label': 'Old Status Can Login', 'expr': 'oldStatusCanLogin', 'type': 'boolean'},
        {'label': 'New Status Can Login', 'expr': 'newStatusCanLogin', 'type': 'boolean'},
    ],
    'outputs': [
        {'label': 'Order Action', 'name': 'orderAction', 'type': 'string',
         'values': '"DELETE_USER","SUSPEND_ACTIVE_ORDERS","REACTIVATE_SUSPENDED_ORDERS","NO_ORDER_ACTION"'},
    ],
    'rules': [
        R(['true', '-', '-'], ['"DELETE_USER"'],
          'L336-340: new status == STATUS_DELETED -> new UserBL(user.getId()).delete(executorId); return (terminal, orders untouched here)'),
        R(['false', 'true', 'false'], ['"SUSPEND_ACTIVE_ORDERS"'],
          'L344-353: couldLogin (old status canLogin==1) transitions to newStatus.canLogin==0 -> every ACTIVE order for '
          'the user is set to ORDER_STATUS_SUSPENDED_AGEING'),
        R(['false', 'false', 'true'], ['"REACTIVATE_SUSPENDED_ORDERS"'],
          'L357-366: !couldLogin transitions to newStatus.canLogin==1 -> every order in ORDER_STATUS_SUSPENDED_AGEING '
          'is set back to ORDER_STATUS_ACTIVE'),
        R(['false', '-', '-'], ['"NO_ORDER_ACTION"'],
          'L342-366 implicit: neither the suspend nor reactivate canLogin-transition condition matches -> no order-status '
          'changes; only the callback/notification fire'),
    ],
}

d_ageing_step_config_validation = {
    'id': 'Decision_AgeingStepConfigValidation', 'name': 'Ageing Step Config Validation',
    'hit_policy': 'FIRST', 'requires': [],
    'inputs': [
        {'label': 'Status Is Active', 'expr': 'statusIsActive', 'type': 'boolean'},
        {'label': 'Status Is Deleted', 'expr': 'statusIsDeleted', 'type': 'boolean'},
        {'label': 'Is Last Selected Step', 'expr': 'isLastSelectedStep', 'type': 'boolean'},
        # DERIVED/effective value: AgeingBL.validate() L194-196 force-sets inUse=true
        # whenever statusIsActive, BEFORE this gate is evaluated -- so for the ACTIVE
        # row this column is always effectively true regardless of what was submitted.
        {'label': 'In Use', 'expr': 'inUse', 'type': 'boolean'},
        {'label': 'Welcome Message Present', 'expr': 'welcomeMessagePresent', 'type': 'boolean'},
        {'label': 'Days', 'expr': 'days', 'type': 'number'},
    ],
    'outputs': [
        {'label': 'Validation Result', 'name': 'validationResult', 'type': 'string',
         'values': '"OK","ERROR_NULL_WELCOME_MESSAGE","ERROR_ZERO_DAYS","ERROR_LAST_STEP_DAYS_MUST_BE_ZERO"'},
    ],
    'rules': [
        R(['-', '-', '-', 'false', '-', '-'], ['"OK"'],
          'AgeingBL.java L198: if (!steps[f].getInUse()) the entire validation block (L199-227) is skipped -> row trivially passes'),
        R(['-', 'false', '-', 'true', 'false', '-'], ['"ERROR_NULL_WELCOME_MESSAGE"'],
          'AgeingBL.java L200-205: in-use, not the DELETED step, welcomeMessage is null -> throws config.ageing.error.null.message'),
        R(['false', 'false', 'false', 'true', '-', '<= 0'], ['"ERROR_ZERO_DAYS"'],
          'AgeingBL.java L208-216: in-use, not ACTIVE, not DELETED, not last-selected step, days <= 0 -> throws config.ageing.error.zero.days'),
        R(['-', '-', 'true', 'true', '-', '> 0'], ['"ERROR_LAST_STEP_DAYS_MUST_BE_ZERO"'],
          'AgeingBL.java L220-225: this row is the last-selected (highest-index in-use) step and days > 0 -> throws config.ageing.error.lastDay'),
        R(['-', '-', '-', '-', '-', '-'], ['"OK"'],
          'AgeingBL.java L226: last-selected step with days <= 0 is silently normalized to days=0; every other combination falls through with no exception'),
    ],
}

# ---------------------------------------------------------------------------
# File 2: Payment_Authorization_and_Blacklist.dmn
# ---------------------------------------------------------------------------

d_payment_outcome_resolution = {
    'id': 'Decision_PaymentOutcomeResolution', 'name': 'Payment Outcome Resolution',
    'hit_policy': 'FIRST', 'requires': [],
    'inputs': [
        {'label': 'Processor Unavailable After All Tasks Tried', 'expr': 'processorUnavailable', 'type': 'boolean'},
        {'label': 'Last Task Payment Result Id (1=OK,2=FAIL,3=UNAVAILABLE,4=ENTERED)', 'expr': 'paymentResultId', 'type': 'number'},
    ],
    'outputs': [
        {'label': 'Resolved Result Code', 'name': 'resultCode', 'type': 'number'},
    ],
    'rules': [
        R(['true', '-'], ['3'],
          'PaymentBL.java L340-341: if the while-loop over pluggable payment tasks exits with processorUnavailable '
          'still true, the outcome is forced to RESULT_UNAVAILABLE (3), overriding whatever result code the last '
          'attempted task left on the payment'),
        R(['false', '-'], ['paymentResultId'],
          'PaymentBL.java L342-344: otherwise (a task actually completed, success or decline) the outcome is exactly '
          'the last task\'s payment result id, passed through unchanged'),
    ],
}

d_payment_balance_assignment = {
    'id': 'Decision_PaymentBalanceAssignment', 'name': 'Payment Balance Assignment',
    'hit_policy': 'FIRST', 'requires': ['Decision_PaymentOutcomeResolution'],
    'inputs': [
        {'label': 'Resolved Result Code', 'expr': 'resultCode', 'type': 'number'},
        {'label': 'Payment Amount', 'expr': 'paymentAmount', 'type': 'number'},
    ],
    'outputs': [
        {'label': 'Balance', 'name': 'balance', 'type': 'number'},
    ],
    'rules': [
        R(['1,4', '-'], ['paymentAmount'],
          'PaymentBL.java L347-348: if RESULT_OK or RESULT_ENTERED, payment.setBalance(payment.getAmount()) -- a '
          'successful or manually-entered payment carries its full amount as available balance'),
        R(['-', '-'], ['0'],
          'PaymentBL.java L349-350: else payment.setBalance(ZERO) -- a failed or processor-unavailable payment has '
          'no usable balance'),
    ],
}

d_blacklist_filter_enabled = {
    'id': 'Decision_BlacklistFilterEnabled', 'name': 'Blacklist Filter Enabled',
    'hit_policy': 'UNIQUE', 'requires': [],
    'inputs': [
        {'label': 'Blacklist Plug-in Id (entity preference PREFERENCE_USE_BLACKLIST=43)', 'expr': 'blacklistPluginId', 'type': 'number'},
    ],
    'outputs': [
        {'label': 'Blacklist Filtering Enabled', 'name': 'blacklistEnabled', 'type': 'boolean'},
    ],
    'rules': [
        R(['0'], ['false'],
          'BlacklistBL.java L129-131 (return getBlacklistPluginId(entityId) != 0) and L178-181: plug-in id 0 means no '
          'payment-filter plug-in was ever configured for the entity, so filtering is off'),
        R(['!= 0'], ['true'],
          'BlacklistBL.java L129-131: any non-zero plug-in id (a real row found via PluggableTaskDAS) means the '
          'blacklist/payment filter plug-in is active for the entity'),
    ],
}

# ---------------------------------------------------------------------------
# File 3: Order_Cancellation_and_Validity.dmn
# ---------------------------------------------------------------------------

d_cancellation_fee_eligibility = {
    'id': 'Decision_CancellationFeeEligibility', 'name': 'Cancellation Fee Eligibility',
    'hit_policy': 'FIRST', 'requires': [],
    'inputs': [
        {'label': 'Event Type', 'expr': 'eventType', 'type': 'string', 'values': '"NEW_ACTIVE_UNTIL","NEW_QUANTITY"'},
        {'label': 'New Active-Until Provided', 'expr': 'newActiveUntilProvided', 'type': 'boolean'},
        {'label': 'Old Active-Until Provided', 'expr': 'oldActiveUntilProvided', 'type': 'boolean'},
        {'label': 'New Active-Until', 'expr': 'newActiveUntil', 'type': 'date'},
        {'label': 'Old Active-Until', 'expr': 'oldActiveUntil', 'type': 'date'},
        {'label': 'New Quantity', 'expr': 'newQuantity', 'type': 'number'},
        {'label': 'Old Quantity', 'expr': 'oldQuantity', 'type': 'number'},
    ],
    'outputs': [
        {'label': 'Process Cancellation Fee', 'name': 'processCancellationFee', 'type': 'boolean'},
    ],
    'rules': [
        R(['"NEW_ACTIVE_UNTIL"', 'false', '-', '-', '-', '-', '-'], ['false'],
          'CancellationFeeRulesTask.java L76-83: newActiveUntil == null -> nothing to evaluate, skip'),
        R(['"NEW_ACTIVE_UNTIL"', 'true', 'true', '-', '<= newActiveUntil', '-', '-'], ['false'],
          'L76-83: old date exists and the new one is not earlier, so nothing was actually cancelled, skip -- exposed as a real cross-variable date comparison (oldActiveUntil <= newActiveUntil), replacing newActiveUntilBeforeOld (redesigned 2026-09-10)'),
        R(['"NEW_ACTIVE_UNTIL"', 'true', 'true', '-', '> newActiveUntil', '-', '-'], ['true'],
          'L85-128 (implicit else): old date exists and new date is genuinely earlier -- a real period was cut short, proceed'),
        R(['"NEW_ACTIVE_UNTIL"', 'true', 'false', '-', '-', '-', '-'], ['true'],
          'L85-128 (implicit else): no old active-until to compare against, so the L76-83 guard never trips -- proceed'),
        R(['"NEW_QUANTITY"', '-', '-', '-', '-', '> oldQuantity', '-'], ['false'],
          'L90-92: newQuantity > oldQuantity -- quantity went up, not a cancellation, skip -- exposed as a real cross-variable comparison, replacing quantityDecreased'),
        R(['"NEW_QUANTITY"', '-', '-', '-', '-', '<= oldQuantity', '-'], ['true'],
          'L94-109 (implicit else): quantity decreased or stayed the same -- build a copy of the order with the '
          'cancelled quantity and proceed'),
    ],
}

d_order_period_already_invoiced = {
    'id': 'Decision_OrderPeriodAlreadyInvoiced', 'name': 'Order Period Already Invoiced',
    'hit_policy': 'FIRST', 'requires': [],
    'inputs': [
        {'label': 'Candidate Date Provided', 'expr': 'candidateDateProvided', 'type': 'boolean'},
        {'label': 'Next Billable Day Provided', 'expr': 'nextBillableDayProvided', 'type': 'boolean'},
        {'label': 'Candidate Date', 'expr': 'candidateDate', 'type': 'date'},
        {'label': 'Next Billable Day', 'expr': 'nextBillableDay', 'type': 'date'},
    ],
    'outputs': [
        {'label': 'Period Already Invoiced', 'name': 'periodAlreadyInvoiced', 'type': 'boolean'},
    ],
    'rules': [
        R(['false', '-', '-', '-'], ['false'],
          'OrderBL.java L1106-1107: a null candidate date can never be "already invoiced"'),
        R(['true', 'false', '-', '-'], ['false'],
          'L1106-1107: no next-billable-day set -> nothing to compare against, false'),
        R(['true', 'true', '-', '>= nextBillableDay'], ['false'],
          'L1107: candidate date is not before the next billable day -- exposed as a real cross-variable date comparison, replacing candidateDateBeforeNextBillableDay (redesigned 2026-09-10)'),
        R(['true', 'true', '-', '< nextBillableDay'], ['true'],
          "L1105-1108: candidate date falls before the order's next billable day -- a period that was already going "
          'to be invoiced is being shortened'),
    ],
}

d_order_date_range_valid = {
    'id': 'Decision_OrderDateRangeValid', 'name': 'Order Date Range Valid',
    'hit_policy': 'FIRST', 'requires': [],
    'inputs': [
        {'label': 'Reflection/Parse Error Occurred', 'expr': 'parseOrAccessError', 'type': 'boolean'},
        {'label': 'Start Date Provided', 'expr': 'startDateProvided', 'type': 'boolean'},
        {'label': 'End Date Provided', 'expr': 'endDateProvided', 'type': 'boolean'},
        {'label': 'Start Date', 'expr': 'startDate', 'type': 'date'},
        {'label': 'End Date', 'expr': 'endDate', 'type': 'date'},
    ],
    'outputs': [
        {'label': 'Date Range Valid', 'name': 'dateRangeValid', 'type': 'boolean'},
    ],
    'rules': [
        R(['true', '-', '-', '-', '-'], ['false'],
          'DateRangeValidator.java L74-84: any reflection or date-parsing failure is treated as invalid'),
        R(['false', 'false', '-', '-', '-'], ['true'],
          'L63-64: a missing start date is vacuously valid'),
        R(['false', 'true', 'false', '-', '-'], ['true'],
          'L66-67: a missing end date is likewise vacuously valid'),
        R(['false', 'true', 'true', '-', '> startDate'], ['true'],
          'L69-72: both dates present and start genuinely precedes end -- exposed as a real cross-variable date comparison, replacing startBeforeEnd (redesigned 2026-09-10)'),
        R(['false', 'true', 'true', '-', '<= startDate'], ['false'],
          'L69-72: both dates present but start is on/after end -- invalid'),
    ],
}

# ---------------------------------------------------------------------------
# File 4: Proration_and_Tax.dmn
# ---------------------------------------------------------------------------

# NOTE on output type: 'Resolved Cycle Start Date' is modeled as a STRING label
# naming the real source (not a literal FEEL date value), the same convention
# OFBiz's "Order Item Cancelable Quantity" used for its two string-labeled
# outputs -- because the winning value is "whatever purchase_order.next_billable_day
# holds", not a value this table computes itself.
d_cycle_start_source = {
    'id': 'Decision_CycleStartSource', 'name': 'Cycle Start Source',
    'hit_policy': 'FIRST', 'requires': [],
    'inputs': [
        {'label': 'Order Has Next Billable Day Set', 'expr': 'hasNextBillableDay', 'type': 'boolean'},
        {'label': 'Order Has Cycle Starts Date Set', 'expr': 'hasCycleStarts', 'type': 'boolean'},
    ],
    'outputs': [
        {'label': 'Resolved Cycle Start Date Source', 'name': 'cycleStartDateSource', 'type': 'string'},
    ],
    'rules': [
        R(['true', '-'], ['"purchase_order.next_billable_day"'],
          "ProRateOrderPeriodTask.java L78-79: order.getNextBillableDay() != null -> use it as the cycle start"),
        R(['false', 'true'], ['"purchase_order.cycle_start"'],
          "L80-81: else if order.getCycleStarts() != null -> use the order's cycle-start date instead "
          "(getter name is plural, column is singular -- a real naming mismatch)"),
        R(['false', 'false'], ['"periodStart (caller-supplied billing-period start parameter)"'],
          "L82-83: else fall back to the periodStart parameter passed in by the caller"),
    ],
}

# NOTE: fullPrice is included as a real input column (not a bare label) since
# it genuinely feeds the arithmetic; output type is 'number' with real FEEL
# arithmetic entries referencing the table's own input variables (cross-column
# reference), following the same precedent as OFBiz's Refund Amount Validity
# (comparing 'returnAmount' against another input, 'orderGrandTotal').
d_daily_prorate_amount = {
    'id': 'Decision_DailyProRateAmount', 'name': 'Daily Pro-Rate Amount',
    # NOTE on 'requires': deliberately left empty rather than chained to
    # Decision_CycleStartSource. The real data flow between them is indirect --
    # CycleStartSource's winning date becomes an argument to
    # BasicOrderPeriodTask.calculateEnd (a superclass not read as part of this
    # mining pass), whose own cycle-walking loop is what actually produces the
    # PeriodOfTime this decision's daysInCycle/daysInPeriod come from. Asserting
    # a direct DRD edge here would overstate what was actually verified in the
    # source read for this case study.
    'hit_policy': 'FIRST', 'requires': [],
    'inputs': [
        {'label': 'Days In Cycle', 'expr': 'daysInCycle', 'type': 'number'},
        {'label': 'Days In Period', 'expr': 'daysInPeriod', 'type': 'number'},
        {'label': 'Full Price', 'expr': 'fullPrice', 'type': 'number'},
    ],
    'outputs': [
        {'label': 'Prorated Amount', 'name': 'proratedAmount', 'type': 'number'},
    ],
    'rules': [
        R(['0', '-', '-'], ['fullPrice'],
          "DailyProRateCompositionTask.java L45-47: daysInCycle == 0 means this is a one-time order amount, not a "
          "real period of time -> return fullPrice unchanged"),
        R(['daysInPeriod', '-', '-'], ['fullPrice'],
          "L50-52: daysInCycle == daysInPeriod -> not a fraction of a period, don't prorate, return fullPrice "
          "unchanged (cell tests daysInCycle for equality against the daysInPeriod input variable)"),
        R(['-', '-', '-'], ['(fullPrice / daysInCycle) * daysInPeriod'],
          "L54-57: otherwise divide fullPrice by daysInCycle to get a one-day rate, then multiply by daysInPeriod"),
    ],
}

d_tax_calculation_needed = {
    'id': 'Decision_TaxCalculationNeeded', 'name': 'Tax Calculation Needed',
    'hit_policy': 'FIRST', 'requires': [],
    'inputs': [
        {'label': 'Customer-Exemption Custom Field Configured', 'expr': 'customContactFieldConfigured', 'type': 'boolean'},
        {'label': 'Customer Has Primary Contact', 'expr': 'primaryContactFound', 'type': 'boolean'},
        {'label': 'Matching Contact Field Value', 'expr': 'matchingFieldValue', 'type': 'string', 'values': '"EXEMPT_VALUE","OTHER"'},
    ],
    'outputs': [
        {'label': 'Tax Calculation Needed', 'name': 'taxCalculationNeeded', 'type': 'boolean'},
    ],
    'rules': [
        R(['false', '-', '-'], ['true'],
          "SimpleTaxCompositionTask.java L161-163: no custom_contact_field_id plugin parameter configured -> tax is "
          "always calculated (no exemption mechanism active)"),
        R(['true', 'false', '-'], ['true'],
          "L164-167: field configured but no primary contact found for the customer -> tax still calculated (fails open)"),
        R(['true', 'true', '"EXEMPT_VALUE"'], ['false'],
          "L169-174: a contact field of the configured type has content case-insensitively equal to \"yes\"/\"true\" "
          "-> customer is tax-exempt"),
        R(['true', 'true', '"OTHER"'], ['true'],
          "L169-178: no matching exempt-value contact field found -> falls through to the default 'true' at L178"),
    ],
}

d_tax_calculation_mode = {
    'id': 'Decision_TaxCalculationMode', 'name': 'Tax Calculation Mode',
    'hit_policy': 'UNIQUE', 'requires': ['Decision_TaxCalculationNeeded'],
    'inputs': [
        {'label': 'Tax Item Has Percentage Set', 'expr': 'taxItemHasPercentage', 'type': 'boolean'},
    ],
    'outputs': [
        {'label': 'Tax Calculation Mode', 'name': 'taxCalculationMode', 'type': 'string', 'values': '"PERCENTAGE","FLAT"'},
    ],
    'rules': [
        R(['true'], ['"PERCENTAGE"'],
          "SimpleTaxCompositionTask.java L101: taxItem.getPercentage() != null -> tax calculated as a percentage of "
          "the invoice total"),
        R(['false'], ['"FLAT"'],
          "L145-146: taxItem.getPercentage() is null -> tax item treated as a flat additional charge, priced via "
          "item_price"),
    ],
}

# ---------------------------------------------------------------------------
# File 5: Currency_Exchange_Rules.dmn
# ---------------------------------------------------------------------------

d_currency_exchange_rate_source = {
    'id': 'Decision_CurrencyExchangeRateSource', 'name': 'Currency Exchange Rate Source',
    'hit_policy': 'FIRST', 'requires': [],
    'inputs': [
        {'label': 'Entity-Specific Exchange Rate Exists', 'expr': 'hasEntitySpecificExchange', 'type': 'boolean'},
        {'label': 'System Default Exchange Rate Exists (entity_id = 0)', 'expr': 'hasSystemDefaultExchange', 'type': 'boolean'},
    ],
    'outputs': [
        {'label': 'Exchange Rate Source', 'name': 'exchangeRateSource', 'type': 'string',
         'values': '"ENTITY_SPECIFIC","SYSTEM_DEFAULT","ERROR_NO_RATE"'},
    ],
    'rules': [
        R(['true', '-'], ['"ENTITY_SPECIFIC"'],
          "CurrencyBL.java L325-326: a currency_exchange row scoped to this entity exists -> use it"),
        R(['false', 'true'], ['"SYSTEM_DEFAULT"'],
          "L327-329: no entity-specific row -> fall back to the currency_exchange row for the sentinel entity_id = 0 "
          "(\"0 is the default\", per the code comment)"),
        R(['false', 'false'], ['"ERROR_NO_RATE"'],
          "L330-333: neither an entity-specific nor a system-default (entity_id=0) row exists -> throws "
          "SessionInternalError"),
    ],
}

# ---------------------------------------------------------------------------
# File groupings
# ---------------------------------------------------------------------------
FILES = {
    'Ageing_and_Dunning': [d_is_ageing_required, d_invoice_overdue, d_ageing_step_advancement,
                            d_ageing_status_change_order_action, d_ageing_step_config_validation],
    'Payment_Authorization_and_Blacklist': [d_payment_outcome_resolution, d_payment_balance_assignment,
                                             d_blacklist_filter_enabled],
    'Order_Cancellation_and_Validity': [d_cancellation_fee_eligibility, d_order_period_already_invoiced,
                                         d_order_date_range_valid],
    'Proration_and_Tax': [d_cycle_start_source, d_daily_prorate_amount, d_tax_calculation_needed,
                           d_tax_calculation_mode],
    'Currency_Exchange_Rules': [d_currency_exchange_rate_source],
}

ALL_DECISIONS = [d for decs in FILES.values() for d in decs]

DMN_DIR = os.path.join(os.path.dirname(__file__), '..', 'dmn')
PROV_DIR = os.path.join(os.path.dirname(__file__), '..', 'provenance')


def build_dmn_files():
    os.makedirs(DMN_DIR, exist_ok=True)
    for file_stub, decisions in FILES.items():
        out_path = os.path.join(DMN_DIR, f'{file_stub}.dmn')
        write_dmn(decisions, f'Definitions_{file_stub}', file_stub.replace('_', ' '), out_path)
        print(f'wrote {out_path} ({len(decisions)} decisions, '
              f'{sum(len(d["rules"]) for d in decisions)} rules)')


def condition_type_for(dec):
    types = set()
    for inp in dec['inputs']:
        t = inp['type']
        if t == 'boolean':
            types.add('boolean')
        elif t == 'number':
            types.add('numeric-threshold')
        elif t == 'string':
            types.add('enumerated-string')
        elif t == 'date':
            types.add('date-threshold')
    return '+'.join(sorted(types)) if types else 'n/a'


def build_provenance_matrix():
    os.makedirs(PROV_DIR, exist_ok=True)
    out_path = os.path.join(PROV_DIR, 'rule_provenance_matrix.csv')
    fieldnames = [
        'Decision Name', 'DMN File', 'Source Class', 'Source Citation',
        'Source Tier', 'Hit Policy', '#Inputs', '#Rules', 'Condition Type',
        'Decision Description', 'Notes',
    ]
    dec_to_file = {}
    for file_stub, decs in FILES.items():
        for d in decs:
            dec_to_file[d['id']] = f'{file_stub}.dmn'

    with open(out_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for dec in ALL_DECISIONS:
            citation = SOURCE_MAP[dec['id']]
            source_class = citation.split('/')[-1].split(':')[0]
            w.writerow({
                'Decision Name': dec['name'],
                'DMN File': dec_to_file[dec['id']],
                'Source Class': f'com.sapienter.jbilling...{source_class.replace(".java", "")}',
                'Source Citation': citation,
                'Source Tier': 'Tier 2 (mined from mosabsalih/jBilling Java source code, local clone)',
                'Hit Policy': dec['hit_policy'],
                '#Inputs': len(dec['inputs']),
                '#Rules': len(dec['rules']),
                'Condition Type': condition_type_for(dec),
                'Decision Description': DECISION_DESC[dec['id']],
                'Notes': '',
            })
    print(f'wrote {out_path} ({len(ALL_DECISIONS)} decision rows)')


if __name__ == '__main__':
    build_dmn_files()
    build_provenance_matrix()
    total_rules = sum(len(d['rules']) for d in ALL_DECISIONS)
    print(f'\nTotal: {len(FILES)} files, {len(ALL_DECISIONS)} decisions, {total_rules} rule rows')
