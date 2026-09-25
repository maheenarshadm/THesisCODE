#!/usr/bin/env python3
"""
Builds the OpenMRS DMN case-study artifacts:
  - 6 .dmn files (Camunda 7 compatible) under ../dmn/
  - provenance/rule_provenance_matrix.csv  (Tier-2: file path + line citations
    into openmrs-core validator source, mirroring FLEX2's Tier-1 page-citation
    matrix)

All 19 decisions below are mined from real validator classes in the
openmrs-core GitHub repository (org.openmrs.validator package, `master`
branch, fetched into scratchpad/openmrs_validators/*.java on 2026-09-07).
Every rule traces to a specific method + line range in one of those files.
This is the OpenMRS analogue of FLEX2's Tier-1 policy-clause citations,
except sourced from code (Tier 2) since OpenMRS has no equivalent business
rules PDF.

Each decision dict follows dmn_builder.py's schema. R() is a small rule
helper: R(inputs, outputs, description).
"""
import csv
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from dmn_builder import write_dmn


def R(inp, out, desc=None):
    return {'in': inp, 'out': out, 'desc': desc}


REPO = "openmrs/openmrs-core"
BRANCH = "master"
PKG_PATH = "api/src/main/java/org/openmrs/validator"


def src(file, lines, method=None):
    """Build a provenance citation string for a validator source range."""
    m = f" ({method})" if method else ""
    return f"{PKG_PATH}/{file}:{lines}{m} [{REPO}@{BRANCH}]"


# ---------------------------------------------------------------------------
# SOURCE_MAP: decision id -> provenance metadata used to auto-generate the
# rule provenance matrix (mirrors FLEX2's PAGE_MAP / pages_for() mechanism,
# but keyed on validator-file + line-range citations instead of PDF pages).
# ---------------------------------------------------------------------------
SOURCE_MAP = {
    'Decision_BirthdateValidity': src('PersonValidator.java', 'L161-167,193-213',
                                       'validateBirthDate/rejectIfFutureDate/rejectDateIfBefore140YearsAgo'),
    'Decision_DeathRecordConsistency': src('PersonValidator.java', 'L145-153', 'validateDeathCause'),
    'Decision_DeathDateConsistencyViolations': src('PersonValidator.java', 'L175-184,193-197,222-226',
                                          'validateDeathDate/rejectIfFutureDate/rejectDeathDateIfBeforeBirthDate'),
    'Decision_DeathDateConsistency': src('PersonValidator.java', 'L175-184,193-197,222-226',
                                          'validateDeathDate (downstream verdict)'),
    'Decision_PreferredIdentifierRequirement': src('PatientValidator.java', 'L81-94', 'validate'),
    'Decision_IdentifierLocationRequirement': src('PatientIdentifierValidator.java', 'L95-101', 'validateIdentifier(PatientIdentifier)'),
    'Decision_IdentifierUniquenessCheck': src('PatientIdentifierValidator.java', 'L103-130', 'validateIdentifier(PatientIdentifier)'),
    'Decision_IdentifierFormatAndCheckDigitValidity': src('PatientIdentifierValidator.java', 'L148-169,186-207',
                                                           'validateIdentifier(String,PatientIdentifierType)/checkIdentifierAgainstFormat'),
    'Decision_ObsValueRequiredByDatatype': src('ObsValidator.java', 'L164-222', 'validateHelper'),
    'Decision_ObsGroupValueExclusivity': src('ObsValidator.java', 'L115-157', 'validateHelper'),
    'Decision_NumericPrecisionValidity': src('ObsValidator.java', 'L192-201', 'validateHelper'),
    'Decision_NumericAbsoluteRangeValidity': src('ObsValidator.java', 'L307-326', 'validateAbsoluteRanges'),
    'Decision_NumericInterpretationClassification': src('ObsValidator.java', 'L387-403', 'setObsInterpretation'),
    'Decision_ConceptPreferredNameValidity': src('ConceptValidator.java', 'L136-153', 'validate'),
    'Decision_OrderDateActivatedConsistencyViolations': src('OrderValidator.java', 'L109-131', 'validateDateActivated'),
    'Decision_OrderDateActivatedConsistency': src('OrderValidator.java', 'L109-131', 'validateDateActivated (downstream verdict)'),
    'Decision_OrderScheduledDateUrgencyConsistency': src('OrderValidator.java', 'L141-150', 'validateScheduledDate'),
    'Decision_ProgramEnrollmentDateConsistencyViolations': src('PatientProgramValidator.java', 'L99-112', 'validate'),
    'Decision_ProgramEnrollmentDateConsistency': src('PatientProgramValidator.java', 'L99-112', 'validate (downstream verdict)'),
    'Decision_PatientStateDateValidity': src('PatientProgramValidator.java', 'L169-177', 'validate'),
    'Decision_RelationshipDateValidityViolations': src('RelationshipValidator.java', 'L54-64', 'validate'),
    'Decision_RelationshipDateValidity': src('RelationshipValidator.java', 'L54-64', 'validate (downstream verdict)'),
    'Decision_EncounterDatetimeValidityViolations': src('EncounterValidator.java', 'L82-104', 'validate'),
    'Decision_EncounterDatetimeValidity': src('EncounterValidator.java', 'L82-104', 'validate (downstream verdict)'),
}

DECISION_DESC = {
    'Decision_BirthdateValidity': "A person's birthdate must not be in the future or imply an age over 140 years.",
    'Decision_DeathRecordConsistency': "A dead person must have exactly one of causeOfDeath / causeOfDeathNonCoded set.",
    'Decision_DeathDateConsistencyViolations': "Every independent reason a person's death date could be invalid, all reported together (COLLECT): not in the future, and not before their birthdate.",
    'Decision_DeathDateConsistency': "A person's death date is valid iff Death Date Consistency Violations reports nothing.",
    'Decision_PreferredIdentifierRequirement': "A patient with more than one identifier must have exactly one flagged preferred.",
    'Decision_IdentifierLocationRequirement': "A patient identifier needs a location unless its type's locationBehavior is NOT_USED.",
    'Decision_IdentifierUniquenessCheck': "Uniqueness of a patient identifier value depends on its type's uniquenessBehavior.",
    'Decision_IdentifierFormatAndCheckDigitValidity': "A patient identifier value must satisfy its type's regex format. (Check-digit validation removed 2026-09-10 -- the algorithm has zero relational representation; see README.)",
    'Decision_ObsValueRequiredByDatatype': "A leaf (non-group) Obs must populate the value_* column matching its concept's datatype.",
    'Decision_ObsGroupValueExclusivity': "An Obs is either a value-bearing leaf or a value-free group -- never both.",
    'Decision_NumericPrecisionValidity': "A numeric Obs value must be a whole number unless its concept allows decimals.",
    'Decision_NumericAbsoluteRangeValidity': "A numeric Obs value must fall within its concept's absolute high/low bounds.",
    'Decision_NumericInterpretationClassification': "A numeric Obs value is classified against critical/normal reference thresholds.",
    'Decision_ConceptPreferredNameValidity': "A concept's locale-preferred name must not be an index term, a short name, or voided.",
    'Decision_OrderDateActivatedConsistencyViolations': "Every independent reason an order's dateActivated could be invalid, all reported together (COLLECT), except the future-date check which short-circuits the other three in the real source.",
    'Decision_OrderDateActivatedConsistency': "An order's dateActivated is valid iff Order Date Activated Consistency Violations reports nothing.",
    'Decision_OrderScheduledDateUrgencyConsistency': "scheduledDate and urgency=ON_SCHEDULED_DATE must be set together or not at all.",
    'Decision_ProgramEnrollmentDateConsistencyViolations': "Every independent reason a program enrollment's dates could be invalid, all reported together (COLLECT): neither date future-dated, and completion not before enrollment.",
    'Decision_ProgramEnrollmentDateConsistency': "Program enrollment dates are valid iff Program Enrollment Date Consistency Violations reports nothing.",
    'Decision_PatientStateDateValidity': "A patient's program-workflow state end date must not precede its start date.",
    'Decision_RelationshipDateValidityViolations': "Every independent reason a relationship's dates could be invalid, all reported together (COLLECT): start not after end, start not in the future.",
    'Decision_RelationshipDateValidity': "A relationship's dates are valid iff Relationship Date Validity Violations reports nothing.",
    'Decision_EncounterDatetimeValidityViolations': "Every independent reason an encounter's datetime could be invalid, all reported together (COLLECT): visit/patient match, not future-dated, within the visit's date range.",
    'Decision_EncounterDatetimeValidity': "An encounter's datetime is valid iff Encounter Datetime Validity Violations reports nothing.",
}

# ---------------------------------------------------------------------------
# File 1: Person_Demographics_Validation.dmn
# ---------------------------------------------------------------------------

d_birthdate = {
    'id': 'Decision_BirthdateValidity', 'name': 'Birthdate Validity',
    'hit_policy': 'FIRST', 'requires': [],
    'inputs': [
        {'label': 'Birthdate', 'expr': 'birthdate', 'type': 'date'},
        {'label': 'Evaluation Time', 'expr': 'evaluationTime', 'type': 'date'},
        {'label': 'Years Since Birthdate', 'expr': 'yearsSinceBirthdate', 'type': 'number'},
    ],
    'outputs': [
        {'label': 'Birthdate Valid', 'name': 'birthdateValid', 'type': 'boolean'},
        {'label': 'Reason Code', 'name': 'reasonCode', 'type': 'string'},
    ],
    'rules': [
        R(['> evaluationTime', '-', '-'], ['false', '"birthdate.future"'], 'rejectIfFutureDate on birthdate (L193-197) -- exposed as a real date comparison against an explicit evaluationTime scenario parameter, replacing the pre-collapsed birthdateIsFutureDate boolean (redesigned 2026-09-10)'),
        R(['<= evaluationTime', '-', '> 140'], ['false', '"birthdate.olderThan140Years"'], 'rejectDateIfBefore140YearsAgo (L199-213)'),
        R(['<= evaluationTime', '-', '<= 140'], ['true', '"none"'], 'passes both checks'),
    ],
}

d_death_cause = {
    'id': 'Decision_DeathRecordConsistency', 'name': 'Death Record Consistency',
    'hit_policy': 'FIRST', 'requires': [],
    'inputs': [
        {'label': 'Dead', 'expr': 'dead', 'type': 'boolean'},
        {'label': 'Cause Of Death Set', 'expr': 'causeOfDeathSet', 'type': 'boolean'},
        {'label': 'Cause Of Death Non Coded Set', 'expr': 'causeOfDeathNonCodedSet', 'type': 'boolean'},
    ],
    'outputs': [
        {'label': 'Death Record Valid', 'name': 'deathRecordValid', 'type': 'boolean'},
        {'label': 'Reason Code', 'name': 'reasonCode', 'type': 'string'},
    ],
    'rules': [
        R(['false', '-', '-'], ['true', '"notApplicable"'], 'validateDeathCause only runs if dead (L146)'),
        R(['true', 'true', 'true'], ['false', '"Person.dead.shouldHaveOnlyOneCauseOfDeathOrCauseOfDeathNonCodedSet"'], 'both set (L147-148)'),
        R(['true', 'false', 'false'], ['false', '"Person.dead.causeOfDeathAndCauseOfDeathNonCodedNull"'], 'neither set (L149-150)'),
        R(['true', 'true', 'false'], ['true', '"codedCauseOnly"'], 'exactly one set'),
        R(['true', 'false', 'true'], ['true', '"nonCodedCauseOnly"'], 'exactly one set'),
    ],
}

d_death_date_violations = {
    'id': 'Decision_DeathDateConsistencyViolations', 'name': 'Death Date Consistency Violations',
    'hit_policy': 'COLLECT', 'requires': [],
    'inputs': [
        {'label': 'Death Date Set', 'expr': 'deathDateSet', 'type': 'boolean'},
        {'label': 'Death Date', 'expr': 'deathDate', 'type': 'date'},
        {'label': 'Evaluation Time', 'expr': 'evaluationTime', 'type': 'date'},
        {'label': 'Birthdate', 'expr': 'birthdate', 'type': 'date'},
    ],
    'outputs': [
        {'label': 'Violation Reason', 'name': 'violationReasons', 'type': 'string'},
    ],
    'rules': [
        R(['true', '> evaluationTime', '-', '-'], ['"error.date.future"'],
          'rejectIfFutureDate on deathDate (L179,193-197) -- exposed as a real date comparison, replacing deathDateIsFutureDate; verified 2026-09-10: no return before the before-birthdate check below, so both can fire on the same deathDate'),
        R(['true', '< birthdate', '-', '-'], ['"error.deathdate.before.birthdate"'],
          'rejectDeathDateIfBeforeBirthDate (L183,222-226) -- exposed as a real cross-variable date comparison against the sibling birthdate input, replacing deathDateBeforeBirthdate; independent of the future check, no return between them'),
    ],
}

d_death_date = {
    'id': 'Decision_DeathDateConsistency', 'name': 'Death Date Consistency',
    'kind': 'literal_expression', 'requires': ['Decision_DeathDateConsistencyViolations'],
    'variable': {'name': 'deathDateValid', 'type': 'boolean'},
    'expression': 'count(violationReasons) = 0',
}

# ---------------------------------------------------------------------------
# File 2: Patient_Identifier_Validation.dmn
# ---------------------------------------------------------------------------

d_preferred_id = {
    'id': 'Decision_PreferredIdentifierRequirement', 'name': 'Preferred Identifier Requirement',
    'hit_policy': 'FIRST', 'requires': [],
    'inputs': [
        {'label': 'Preferred Identifier Count', 'expr': 'preferredIdentifierCount', 'type': 'number'},
        {'label': 'Identifier Count', 'expr': 'identifierCount', 'type': 'number'},
    ],
    'outputs': [
        {'label': 'Preferred Identifier Valid', 'name': 'preferredIdentifierValid', 'type': 'boolean'},
        {'label': 'Reason Code', 'name': 'reasonCode', 'type': 'string'},
    ],
    'rules': [
        R(['>= 1', '-'], ['true', '"preferredChosen"'], "PatientValidator L87-90 -- exposed as a COUNT(identifiers WHERE preferred=true) >= 1, replacing the pre-collapsed anyPreferredFlagged boolean; matches this project's own established count-instead-of-EXISTS pattern (redesigned 2026-09-10)"),
        R(['0', '1'], ['true', '"singleIdentifierExempt"'], 'PatientValidator L92 (size()!=1 short-circuits)'),
        R(['0', '!= 1'], ['false', '"error.preferredIdentifier"'], 'PatientValidator L92-94'),
    ],
}

d_id_location = {
    'id': 'Decision_IdentifierLocationRequirement', 'name': 'Identifier Location Requirement',
    'hit_policy': 'FIRST', 'requires': [],
    'inputs': [
        {'label': 'Location Set', 'expr': 'locationSet', 'type': 'boolean'},
        {'label': 'Location Behavior', 'expr': 'locationBehavior', 'type': 'string',
         'values': '"REQUIRED","NOT_USED"'},
    ],
    'outputs': [
        {'label': 'Location Requirement Valid', 'name': 'locationRequirementValid', 'type': 'boolean'},
        {'label': 'Reason Code', 'name': 'reasonCode', 'type': 'string'},
    ],
    'rules': [
        R(['true', '-'], ['true', '"locationProvided"'], 'L97 location != null'),
        R(['false', '"REQUIRED"'], ['false', '"PatientIdentifier.location.null"'], 'L96-101 (null behavior defaults to REQUIRED)'),
        R(['false', '"NOT_USED"'], ['true', '"locationNotRequired"'], 'L97 condition false when behavior is NOT_USED'),
    ],
}

d_id_uniqueness = {
    'id': 'Decision_IdentifierUniquenessCheck', 'name': 'Identifier Uniqueness Check',
    'hit_policy': 'FIRST', 'requires': [],
    'inputs': [
        {'label': 'Uniqueness Behavior', 'expr': 'uniquenessBehavior', 'type': 'string',
         'values': '"UNIQUE","LOCATION","NON_UNIQUE"'},
        {'label': 'In Use By Another Patient', 'expr': 'inUseByAnotherPatient', 'type': 'boolean'},
        {'label': 'Duplicate Within Same Patient At Same Or Null Location', 'expr': 'duplicateWithinSamePatient', 'type': 'boolean'},
    ],
    'outputs': [
        {'label': 'Identifier Uniqueness Valid', 'name': 'identifierUniquenessValid', 'type': 'boolean'},
        {'label': 'Reason Code', 'name': 'reasonCode', 'type': 'string'},
    ],
    'rules': [
        R(['"NON_UNIQUE"', '-', '-'], ['true', '"nonUniqueTypeExempt"'], 'L103-104 short-circuits the isIdentifierInUseByAnotherPatient check'),
        R(['-', 'true', '-'], ['false', '"IdentifierNotUniqueException"'], 'L103-110'),
        R(['-', 'false', 'true'], ['false', '"DuplicateIdentifierException"'], 'L112-130'),
        R(['-', 'false', 'false'], ['true', '"unique"'], 'no matching identifier found'),
    ],
}

d_id_format = {
    'id': 'Decision_IdentifierFormatAndCheckDigitValidity', 'name': 'Identifier Format Validity',
    'hit_policy': 'FIRST', 'requires': [],
    'inputs': [
        {'label': 'Identifier Blank', 'expr': 'identifierBlank', 'type': 'boolean'},
        {'label': 'Format Set', 'expr': 'formatSet', 'type': 'boolean'},
        {'label': 'Identifier Matches Format', 'expr': 'identifierMatchesFormat', 'type': 'boolean'},
    ],
    'outputs': [
        {'label': 'Identifier Format Valid', 'name': 'identifierFormatValid', 'type': 'boolean'},
        {'label': 'Reason Code', 'name': 'reasonCode', 'type': 'string'},
    ],
    'rules': [
        R(['true', '-', '-'], ['false', '"PatientIdentifier.error.nullOrBlank"'], 'L156-158,191-193,226-228'),
        R(['false', 'true', 'false'], ['false', '"InvalidIdentifierFormatException"'], 'checkIdentifierAgainstFormat L200-205'),
        R(['false', 'true', 'true'], ['true', '"none"'], 'passes format check'),
        R(['false', 'false', '-'], ['true', '"none"'], 'no format configured (L160-166)'),
    ],
}
# REMOVED (2026-09-10, user instruction): checkDigitValid and validatorSet (the
# check-digit half of the original Decision_IdentifierFormatAndCheckDigitValidity),
# via checkIdentifierAgainstValidator (PatientIdentifierValidator.java L221-247).
# This is the ONE genuine zero-relational-representation rule found across all 24
# OpenMRS decisions on re-audit: patient_identifier_type.validator stores only the
# check-digit algorithm's CLASS NAME (e.g. "LuhnIdentifierValidator"); the algorithm
# itself is Java code with no relational representation at all -- distinct from every
# other "documented boolean exception" in this package (identifierMatchesFormat,
# valueNumericHasFraction, anyValueFieldSet, etc.), each of which stands on a REAL
# persisted column and is merely awkward to express in FEEL/SQL. Removed following
# the FLEX2 Revision-2 precedent (partial trim: decision kept, unmappable rule/input
# dropped, mappable remainder kept) -- see the design doc's own §4.4 finding, which
# this rule was previously the clearest OpenMRS-side illustration of. Kept as a
# documented removal in this comment, not silently dropped -- see README.md.

# ---------------------------------------------------------------------------
# File 3: Concept_and_Observation_Validation.dmn
# ---------------------------------------------------------------------------

d_obs_required_value = {
    'id': 'Decision_ObsValueRequiredByDatatype', 'name': 'Obs Value Required By Datatype',
    'hit_policy': 'UNIQUE', 'requires': [],
    'inputs': [
        {'label': 'Is Obs Group', 'expr': 'isObsGroup', 'type': 'boolean'},
        {'label': 'Concept Datatype', 'expr': 'conceptDatatype', 'type': 'string',
         'values': '"Boolean","Coded","Datetime","Date","Time","Numeric","Text"'},
    ],
    'outputs': [
        {'label': 'Required Value Column', 'name': 'requiredValueColumn', 'type': 'string'},
    ],
    'rules': [
        R(['true', '-'], ['"none (obs group must carry no value column)"'], 'L117-150'),
        R(['false', '"Boolean"'], ['"value_coded (via true/false concept -- no value_boolean column exists)"'], 'L168-173'),
        R(['false', '"Coded"'], ['"value_coded"'], 'L174-179'),
        R(['false', '"Datetime","Date","Time"'], ['"value_datetime"'], 'L180-185'),
        R(['false', '"Numeric"'], ['"value_numeric"'], 'L186-191'),
        R(['false', '"Text"'], ['"value_text"'], 'L204-210'),
    ],
}

d_obs_group_exclusivity = {
    'id': 'Decision_ObsGroupValueExclusivity', 'name': 'Obs Group Value Exclusivity',
    'hit_policy': 'UNIQUE', 'requires': [],
    'inputs': [
        {'label': 'Is Obs Group', 'expr': 'isObsGroup', 'type': 'boolean'},
        {'label': 'Any Value Field Set', 'expr': 'anyValueFieldSet', 'type': 'boolean'},
    ],
    'outputs': [
        {'label': 'Obs Structure Valid', 'name': 'obsStructureValid', 'type': 'boolean'},
        {'label': 'Reason Code', 'name': 'reasonCode', 'type': 'string'},
    ],
    'rules': [
        R(['true', 'true'], ['false', '"error.not.null (group carries a value field)"'], 'L117-150'),
        R(['true', 'false'], ['true', '"validGroup"'], 'L117-150 all value-field checks pass'),
        R(['false', 'false'], ['false', '"error.noValue"'], 'L151-157'),
        R(['false', 'true'], ['true', '"validLeafObs"'], 'at least one value present'),
    ],
}

d_numeric_precision = {
    'id': 'Decision_NumericPrecisionValidity', 'name': 'Numeric Precision Validity',
    'hit_policy': 'FIRST', 'requires': [],
    'inputs': [
        {'label': 'Allow Decimal', 'expr': 'allowDecimal', 'type': 'boolean'},
        {'label': 'Value Numeric Has Fraction', 'expr': 'valueNumericHasFraction', 'type': 'boolean'},
    ],
    'outputs': [
        {'label': 'Precision Valid', 'name': 'precisionValid', 'type': 'boolean'},
        {'label': 'Reason Code', 'name': 'reasonCode', 'type': 'string'},
    ],
    'rules': [
        R(['true', '-'], ['true', '"decimalAllowed"'], 'L195 short-circuits when allow_decimal is true'),
        R(['false', 'false'], ['true', '"integerValue"'], 'Math.ceil(v)==v (L195)'),
        R(['false', 'true'], ['false', '"Obs.error.precision"'], 'Math.ceil(v)!=v (L195-201)'),
    ],
}

d_numeric_abs_range = {
    'id': 'Decision_NumericAbsoluteRangeValidity', 'name': 'Numeric Absolute Range Validity',
    'hit_policy': 'FIRST', 'requires': [],
    'inputs': [
        {'label': 'Hi Absolute Set', 'expr': 'hiAbsoluteSet', 'type': 'boolean'},
        {'label': 'Low Absolute Set', 'expr': 'lowAbsoluteSet', 'type': 'boolean'},
        {'label': 'Value Numeric', 'expr': 'valueNumeric', 'type': 'number'},
        {'label': 'Hi Absolute', 'expr': 'hiAbsolute', 'type': 'number'},
        {'label': 'Low Absolute', 'expr': 'lowAbsolute', 'type': 'number'},
    ],
    'outputs': [
        {'label': 'Absolute Range Valid', 'name': 'absoluteRangeValid', 'type': 'boolean'},
        {'label': 'Reason Code', 'name': 'reasonCode', 'type': 'string'},
    ],
    'rules': [
        R(['true', '-', '> hiAbsolute', '-', '-'], ['false', '"error.value.outOfRange.high"'],
          'L309-316 -- exposed as a real cross-variable comparison (valueNumeric > hiAbsolute), replacing the pre-collapsed valueExceedsHiAbsolute boolean (redesigned 2026-09-10)'),
        R(['-', 'true', '< lowAbsolute', '-', '-'], ['false', '"error.value.outOfRange.low"'],
          'L318-326 -- exposed as a real cross-variable comparison (valueNumeric < lowAbsolute), replacing valueBelowLowAbsolute'),
        R(['-', '-', '-', '-', '-'], ['true', '"withinRange"'], 'neither absolute bound violated'),
    ],
}

d_numeric_interpretation = {
    'id': 'Decision_NumericInterpretationClassification', 'name': 'Numeric Interpretation Classification',
    'hit_policy': 'FIRST', 'requires': [],
    'inputs': [
        {'label': 'Value Numeric', 'expr': 'valueNumeric', 'type': 'number'},
        {'label': 'Hi Critical', 'expr': 'hiCritical', 'type': 'number'},
        {'label': 'Hi Normal', 'expr': 'hiNormal', 'type': 'number'},
        {'label': 'Low Critical', 'expr': 'lowCritical', 'type': 'number'},
        {'label': 'Low Normal', 'expr': 'lowNormal', 'type': 'number'},
    ],
    'outputs': [
        {'label': 'Interpretation', 'name': 'interpretation', 'type': 'string'},
    ],
    'rules': [
        R(['>= hiCritical', '-', '-', '-', '-'], ['"CRITICALLY_HIGH"'],
          'L393-394 -- exposed as a real FIRST-hit threshold ladder over valueNumeric against the four reference-range columns, replacing four pre-collapsed booleans (redesigned 2026-09-10); same pattern as the Spree tiered-percent decision'),
        R(['> hiNormal', '-', '-', '-', '-'], ['"HIGH"'], 'L395-396 -- valueGtHiNormal was strictly ">", preserved exactly (not loosened to ">=")'),
        R(['<= lowCritical', '-', '-', '-', '-'], ['"CRITICALLY_LOW"'], 'L397-398'),
        R(['< lowNormal', '-', '-', '-', '-'], ['"LOW"'], 'L399-400 -- valueLtLowNormal was strictly "<", preserved exactly (not loosened to "<=")'),
        R(['-', '-', '-', '-', '-'], ['"NORMAL"'], 'L401-402 (else branch)'),
    ],
}

d_concept_name = {
    'id': 'Decision_ConceptPreferredNameValidity', 'name': 'Concept Preferred Name Validity',
    'hit_policy': 'FIRST', 'requires': [],
    'inputs': [
        {'label': 'Locale Preferred', 'expr': 'localePreferred', 'type': 'boolean'},
        {'label': 'Is Index Term', 'expr': 'isIndexTerm', 'type': 'boolean'},
        {'label': 'Is Short Name', 'expr': 'isShortName', 'type': 'boolean'},
        {'label': 'Voided', 'expr': 'voided', 'type': 'boolean'},
    ],
    'outputs': [
        {'label': 'Preferred Name Valid', 'name': 'preferredNameValid', 'type': 'boolean'},
        {'label': 'Reason Code', 'name': 'reasonCode', 'type': 'string'},
    ],
    'rules': [
        R(['false', '-', '-', '-'], ['true', '"notApplicable"'], 'ConceptValidator L136-153 only guards preferred names'),
        R(['true', 'true', '-', '-'], ['false', '"Concept.error.preferredName.is.indexTerm"'], 'L138-141'),
        R(['true', 'false', 'true', '-'], ['false', '"Concept.error.preferredName.is.shortName"'], 'L142-145'),
        R(['true', 'false', 'false', 'true'], ['false', '"Concept.error.preferredName.is.voided"'], 'L146-149'),
        R(['true', 'false', 'false', 'false'], ['true', '"none"'], 'passes all three checks'),
    ],
}

# ---------------------------------------------------------------------------
# File 4: Order_Validation.dmn
# ---------------------------------------------------------------------------

d_order_date_activated_violations = {
    'id': 'Decision_OrderDateActivatedConsistencyViolations', 'name': 'Order Date Activated Consistency Violations',
    'hit_policy': 'COLLECT', 'requires': [],
    'inputs': [
        {'label': 'Date Activated Set', 'expr': 'dateActivatedSet', 'type': 'boolean'},
        {'label': 'Date Activated', 'expr': 'dateActivated', 'type': 'date'},
        {'label': 'Evaluation Time', 'expr': 'evaluationTime', 'type': 'date'},
        {'label': 'Date Stopped Set', 'expr': 'dateStoppedSet', 'type': 'boolean'},
        {'label': 'Date Stopped', 'expr': 'dateStopped', 'type': 'date'},
        {'label': 'Auto Expire Date Set', 'expr': 'autoExpireDateSet', 'type': 'boolean'},
        {'label': 'Auto Expire Date', 'expr': 'autoExpireDate', 'type': 'date'},
        {'label': 'Encounter Datetime Set', 'expr': 'encounterDatetimeSet', 'type': 'boolean'},
        {'label': 'Encounter Datetime', 'expr': 'encounterDatetime', 'type': 'date'},
    ],
    'outputs': [
        {'label': 'Violation Reason', 'name': 'violationReasons', 'type': 'string'},
    ],
    'rules': [
        R(['true', '> evaluationTime', '-', '-', '-', '-', '-', '-', '-'], ['"Order.error.dateActivatedInFuture"'],
          'L112-115 -- exposed as a real date comparison against an explicit evaluationTime, replacing dateActivatedIsFuture; verified: this check DOES return early in the real source, so it is mutually exclusive with the three checks below by construction (redesigned 2026-09-10)'),
        R(['true', '> dateStopped', '-', 'true', '-', '-', '-', '-', '-'], ['"Order.error.dateActivatedAfterDiscontinuedDate"'],
          'L116-120 -- exposed as a real cross-variable date comparison (dateActivated > dateStopped), replacing dateActivatedAfterDateStopped; verified 2026-09-10: no return after this check, independent of the two below'),
        R(['true', '> autoExpireDate', '-', '-', '-', 'true', '-', '-', '-'], ['"Order.error.dateActivatedAfterAutoExpireDate"'],
          'L121-125 -- exposed as a real cross-variable date comparison (dateActivated > autoExpireDate), replacing dateActivatedAfterAutoExpireDate; verified: can co-fire with the discontinued-date and encounter checks'),
        R(['true', '-', '-', '-', '-', '-', '-', 'true', '> dateActivated'], ['"Order.error.encounterDatetimeAfterDateActivated"'],
          'L126-130 -- exposed as a real cross-variable date comparison (encounterDatetime > dateActivated), replacing encounterDatetimeAfterDateActivated; verified: no return before this, the last check in the method; can co-fire with either check above'),
    ],
}

d_order_date_activated = {
    'id': 'Decision_OrderDateActivatedConsistency', 'name': 'Order Date Activated Consistency',
    'kind': 'literal_expression', 'requires': ['Decision_OrderDateActivatedConsistencyViolations'],
    'variable': {'name': 'dateActivatedValid', 'type': 'boolean'},
    'expression': 'count(violationReasons) = 0',
}

d_order_scheduled = {
    'id': 'Decision_OrderScheduledDateUrgencyConsistency', 'name': 'Order Scheduled Date Urgency Consistency',
    'hit_policy': 'UNIQUE', 'requires': [],
    'inputs': [
        {'label': 'Scheduled Date Set', 'expr': 'scheduledDateSet', 'type': 'boolean'},
        {'label': 'Urgency', 'expr': 'urgency', 'type': 'string', 'values': '"ON_SCHEDULED_DATE","ROUTINE","STAT"'},
    ],
    'outputs': [
        {'label': 'Scheduled Date Urgency Valid', 'name': 'scheduledDateUrgencyValid', 'type': 'boolean'},
        {'label': 'Reason Code', 'name': 'reasonCode', 'type': 'string'},
    ],
    'rules': [
        R(['true', '"ON_SCHEDULED_DATE"'], ['true', '"none"'],
          'L141-149 -- exposed as a real categorical test against the actual urgency column, replacing the pre-collapsed urgencyIsOnScheduledDate boolean (redesigned 2026-09-10)'),
        R(['true', '!= "ON_SCHEDULED_DATE"'], ['false', '"Order.error.urgencyNotOnScheduledDate"'], 'L144-146'),
        R(['false', '"ON_SCHEDULED_DATE"'], ['false', '"Order.error.scheduledDateNullForOnScheduledDateUrgency"'], 'L147-149'),
        R(['false', '!= "ON_SCHEDULED_DATE"'], ['true', '"none"'], 'L141-149 both conditions false'),
    ],
}

# ---------------------------------------------------------------------------
# File 5: Program_Enrollment_Validation.dmn
# ---------------------------------------------------------------------------

d_enrollment_dates_violations = {
    'id': 'Decision_ProgramEnrollmentDateConsistencyViolations', 'name': 'Program Enrollment Date Consistency Violations',
    'hit_policy': 'COLLECT', 'requires': [],
    'inputs': [
        {'label': 'Date Enrolled', 'expr': 'dateEnrolled', 'type': 'date'},
        {'label': 'Evaluation Time', 'expr': 'evaluationTime', 'type': 'date'},
        {'label': 'Date Completed Set', 'expr': 'dateCompletedSet', 'type': 'boolean'},
        {'label': 'Date Completed', 'expr': 'dateCompleted', 'type': 'date'},
    ],
    'outputs': [
        {'label': 'Violation Reason', 'name': 'violationReasons', 'type': 'string'},
    ],
    'rules': [
        R(['> evaluationTime', '-', '-', '-'], ['"error.patientProgram.enrolledDateDateCannotBeInFuture"'],
          'L100-102 -- exposed as a real date comparison against an explicit evaluationTime, replacing dateEnrolledIsFuture; verified 2026-09-10: no return after this check; independent of the two below (redesigned 2026-09-10)'),
        R(['-', '-', 'true', '> evaluationTime'], ['"error.patientProgram.completionDateCannotBeInFuture"'],
          'L104-106 -- exposed as a real date comparison, replacing dateCompletedIsFuture; verified: no return before or after; a program can have BOTH its enrollment date AND completion date in the future simultaneously'),
        R(['-', '-', 'true', '< dateEnrolled'], ['"error.patientProgram.enrolledDateShouldBeBeforecompletionDate"'],
          'L108-112 -- exposed as a real cross-variable date comparison (dateCompleted < dateEnrolled), replacing dateCompletedBeforeDateEnrolled; verified: runs unconditionally after the two checks above; all three can co-fire on the same PatientProgram'),
    ],
}

d_enrollment_dates = {
    'id': 'Decision_ProgramEnrollmentDateConsistency', 'name': 'Program Enrollment Date Consistency',
    'kind': 'literal_expression', 'requires': ['Decision_ProgramEnrollmentDateConsistencyViolations'],
    'variable': {'name': 'enrollmentDatesValid', 'type': 'boolean'},
    'expression': 'count(violationReasons) = 0',
}

d_patient_state_dates = {
    'id': 'Decision_PatientStateDateValidity', 'name': 'Patient State Date Validity',
    'hit_policy': 'FIRST', 'requires': [],
    'inputs': [
        {'label': 'Start Date Set', 'expr': 'startDateSet', 'type': 'boolean'},
        {'label': 'End Date Set', 'expr': 'endDateSet', 'type': 'boolean'},
        {'label': 'Start Date', 'expr': 'startDate', 'type': 'date'},
        {'label': 'End Date', 'expr': 'endDate', 'type': 'date'},
    ],
    'outputs': [
        {'label': 'Patient State Dates Valid', 'name': 'patientStateDatesValid', 'type': 'boolean'},
        {'label': 'Reason Code', 'name': 'reasonCode', 'type': 'string'},
    ],
    'rules': [
        R(['true', 'true', '-', '< startDate'], ['false', '"PatientState.error.endDateCannotBeBeforeStartDate"'],
          'L169-171 -- exposed as a real cross-variable date comparison (endDate < startDate), replacing endDateBeforeStartDate, for the normal case where both dates are set (redesigned 2026-09-10)'),
        R(['false', 'true', '-', '-'], ['false', '"PatientState.error.endDateCannotBeBeforeStartDate"'],
          'L169 (null start treated as earliest by compareWithNullAsLatest) -- deliberately kept boolean-keyed rather than exposed as a comparison: startDate is null here, so there is no real date to compare endDate against; this row encodes a Java comparator quirk, not a graduated threshold'),
        R(['true', 'true', '-', '>= startDate'], ['true', '"closedStateValid"'], 'end after start'),
        R(['-', 'false', '-', '-'], ['true', '"openEndedState"'], 'no end date recorded yet'),
    ],
}

# ---------------------------------------------------------------------------
# File 6: Relationship_and_Encounter_Validation.dmn
# ---------------------------------------------------------------------------

d_relationship_dates_violations = {
    'id': 'Decision_RelationshipDateValidityViolations', 'name': 'Relationship Date Validity Violations',
    'hit_policy': 'COLLECT', 'requires': [],
    'inputs': [
        {'label': 'Start Date Set', 'expr': 'startDateSet', 'type': 'boolean'},
        {'label': 'End Date Set', 'expr': 'endDateSet', 'type': 'boolean'},
        {'label': 'Start Date', 'expr': 'startDate', 'type': 'date'},
        {'label': 'Evaluation Time', 'expr': 'evaluationTime', 'type': 'date'},
        {'label': 'End Date', 'expr': 'endDate', 'type': 'date'},
    ],
    'outputs': [
        {'label': 'Violation Reason', 'name': 'violationReasons', 'type': 'string'},
    ],
    'rules': [
        R(['true', 'true', '> endDate', '-', '-'], ['"Relationship.InvalidEndDate.error"'],
          'L54-58 -- exposed as a real cross-variable date comparison (startDate > endDate), replacing startDateAfterEndDate; verified 2026-09-10 against live source: no return after this check (redesigned 2026-09-10)'),
        R(['true', '-', '> evaluationTime', '-', '-'], ['"error.date.future"'],
          'L60-64 -- exposed as a real date comparison against an explicit evaluationTime, replacing startDateIsFuture; verified: independent of the end-date check, no return between them'),
    ],
}

d_relationship_dates = {
    'id': 'Decision_RelationshipDateValidity', 'name': 'Relationship Date Validity',
    'kind': 'literal_expression', 'requires': ['Decision_RelationshipDateValidityViolations'],
    'variable': {'name': 'relationshipDatesValid', 'type': 'boolean'},
    'expression': 'count(violationReasons) = 0',
}

d_encounter_datetime_violations = {
    'id': 'Decision_EncounterDatetimeValidityViolations', 'name': 'Encounter Datetime Validity Violations',
    'hit_policy': 'COLLECT', 'requires': [],
    'inputs': [
        {'label': 'Visit Patient Id', 'expr': 'visitPatientId', 'type': 'string'},
        {'label': 'Encounter Patient Id', 'expr': 'encounterPatientId', 'type': 'string'},
        {'label': 'Encounter Datetime', 'expr': 'encounterDatetime', 'type': 'date'},
        {'label': 'Evaluation Time', 'expr': 'evaluationTime', 'type': 'date'},
        {'label': 'Visit Set', 'expr': 'visitSet', 'type': 'boolean'},
        {'label': 'Visit Start Datetime', 'expr': 'visitStartDatetime', 'type': 'date'},
        {'label': 'Visit Stop Datetime', 'expr': 'visitStopDatetime', 'type': 'date'},
    ],
    'outputs': [
        {'label': 'Violation Reason', 'name': 'violationReasons', 'type': 'string'},
    ],
    'rules': [
        R(['-', '!= visitPatientId', '-', '-', '-', '-', '-'], ['"Encounter.visit.patients.dontMatch"'],
          'L82-85 -- exposed as a real ID-inequality comparison (encounterPatientId != visitPatientId), replacing visitPatientMismatch; verified 2026-09-10: no return after this check (redesigned 2026-09-10)'),
        R(['-', '-', '> evaluationTime', '-', '-', '-', '-'], ['"Encounter.datetimeShouldBeBeforeCurrent"'],
          'L89-92 -- exposed as a real date comparison against an explicit evaluationTime, replacing encounterDatetimeIsFuture; verified: independent of the visit-mismatch check and the two visit-range checks'),
        R(['-', '-', '< visitStartDatetime', '-', 'true', '-', '-'], ['"Encounter.datetimeShouldBeInVisitDatesRange"'],
          'L96-99 -- exposed as a real cross-variable date comparison, replacing encounterDatetimeBeforeVisitStart; verified: can co-fire with the future-date check and the visit-mismatch check'),
        R(['-', '-', '> visitStopDatetime', '-', 'true', '-', '-'], ['"Encounter.datetimeShouldBeInVisitDatesRange"'],
          'L101-104 -- exposed as a real cross-variable date comparison, replacing encounterDatetimeAfterVisitStop; verified: same message id as the row above but a genuinely distinct real check'),
    ],
}

d_encounter_datetime = {
    'id': 'Decision_EncounterDatetimeValidity', 'name': 'Encounter Datetime Validity',
    'kind': 'literal_expression', 'requires': ['Decision_EncounterDatetimeValidityViolations'],
    'variable': {'name': 'encounterDatetimeValid', 'type': 'boolean'},
    'expression': 'count(violationReasons) = 0',
}

# ---------------------------------------------------------------------------
# File groupings (mirrors FLEX2's one-file-per-domain-area layout)
# ---------------------------------------------------------------------------
FILES = {
    'Person_Demographics_Validation': [d_birthdate, d_death_cause, d_death_date_violations, d_death_date],
    'Patient_Identifier_Validation': [d_preferred_id, d_id_location, d_id_uniqueness, d_id_format],
    'Concept_and_Observation_Validation': [
        d_obs_required_value, d_obs_group_exclusivity, d_numeric_precision,
        d_numeric_abs_range, d_numeric_interpretation, d_concept_name,
    ],
    'Order_Validation': [d_order_date_activated_violations, d_order_date_activated, d_order_scheduled],
    'Program_Enrollment_Validation': [d_enrollment_dates_violations, d_enrollment_dates, d_patient_state_dates],
    'Relationship_and_Encounter_Validation': [
        d_relationship_dates_violations, d_relationship_dates,
        d_encounter_datetime_violations, d_encounter_datetime,
    ],
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
              f'{sum(len(d["rules"]) for d in decisions if d.get("kind") != "literal_expression")} rules)')


def condition_type_for(dec):
    if dec.get('kind') == 'literal_expression':
        return 'derived-calculation'
    types = set()
    for inp in dec['inputs']:
        t = inp['type']
        if t == 'boolean':
            types.add('boolean')
        elif t == 'number':
            types.add('numeric-threshold')
        elif t == 'string':
            types.add('enumerated-string')
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
            is_literal = dec.get('kind') == 'literal_expression'
            w.writerow({
                'Decision Name': dec['name'],
                'DMN File': dec_to_file[dec['id']],
                'Source Class': f'org.openmrs.validator.{source_class.replace(".java", "")}',
                'Source Citation': citation,
                'Source Tier': 'Tier 2 (mined from openmrs-core validator source code)',
                'Hit Policy': dec.get('hit_policy', 'n/a (literal expression)'),
                '#Inputs': len(dec['inputs']) if not is_literal else 0,
                '#Rules': len(dec['rules']) if not is_literal else 1,
                'Condition Type': condition_type_for(dec),
                'Decision Description': DECISION_DESC[dec['id']],
                'Notes': '',
            })
    print(f'wrote {out_path} ({len(ALL_DECISIONS)} decision rows)')


if __name__ == '__main__':
    build_dmn_files()
    build_provenance_matrix()
    total_rules = sum(len(d['rules']) for d in ALL_DECISIONS if d.get('kind') != 'literal_expression')
    print(f'\nTotal: {len(FILES)} files, {len(ALL_DECISIONS)} decisions, {total_rules} rule rows')
