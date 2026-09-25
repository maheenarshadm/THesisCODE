#!/usr/bin/env python3
"""
Builds provenance/variable_to_schema_mapping.csv for the OpenMRS DMN case
study, following the same manual 6-step mapping methodology used for FLEX2
(understand meaning -> find candidate tables -> direct-vs-derived ->
value-list matching for enums -> accept "no match" where genuine -> record),
against openmrs-core's Liquibase schema
(schemas/openmrs/liquibase-schema-only-2.9.x.xml,
liquibase-update-to-latest-3.0.x.xml).

IMPORTANT: always open CSV files with newline='' (see FLEX2 postmortem on
CSV corruption from omitting this).
"""
import csv
import os

OUT_PATH = os.path.join(os.path.dirname(__file__), '..', 'provenance', 'variable_to_schema_mapping.csv')

# Each row: (dmn_file, decision_name, variable_name, io, table_column, mapping_type, notes)
ROWS = [
    # --- Person_Demographics_Validation.dmn ---
    ('Person_Demographics_Validation.dmn', 'Birthdate Validity', 'birthdateIsFutureDate', 'input',
     'person.birthdate', 'derived', 'birthdate > CURRENT_DATE'),
    ('Person_Demographics_Validation.dmn', 'Birthdate Validity', 'yearsSinceBirthdate', 'input',
     'person.birthdate', 'derived', 'TIMESTAMPDIFF(YEAR, birthdate, CURRENT_DATE)'),
    ('Person_Demographics_Validation.dmn', 'Birthdate Validity', 'birthdateValid', 'output',
     'n/a', 'not-persisted', 'validation outcome only, not stored'),
    ('Person_Demographics_Validation.dmn', 'Birthdate Validity', 'reasonCode', 'output',
     'n/a', 'not-persisted', 'validation outcome only, not stored'),

    ('Person_Demographics_Validation.dmn', 'Death Record Consistency', 'dead', 'input',
     'person.dead', 'direct - exact match', ''),
    ('Person_Demographics_Validation.dmn', 'Death Record Consistency', 'causeOfDeathSet', 'input',
     'person.cause_of_death', 'derived', 'cause_of_death IS NOT NULL (FK to concept)'),
    ('Person_Demographics_Validation.dmn', 'Death Record Consistency', 'causeOfDeathNonCodedSet', 'input',
     'person.cause_of_death_non_coded', 'derived', 'cause_of_death_non_coded IS NOT NULL'),
    ('Person_Demographics_Validation.dmn', 'Death Record Consistency', 'deathRecordValid', 'output',
     'n/a', 'not-persisted', ''),
    ('Person_Demographics_Validation.dmn', 'Death Record Consistency', 'reasonCode', 'output',
     'n/a', 'not-persisted', ''),

    ('Person_Demographics_Validation.dmn', 'Death Date Consistency', 'deathDateSet', 'input',
     'person.death_date', 'derived', 'death_date IS NOT NULL'),
    ('Person_Demographics_Validation.dmn', 'Death Date Consistency', 'deathDateIsFutureDate', 'input',
     'person.death_date', 'derived', 'death_date > CURRENT_DATE'),
    ('Person_Demographics_Validation.dmn', 'Death Date Consistency', 'deathDateBeforeBirthdate', 'input',
     'person.death_date, person.birthdate', 'derived', 'death_date < birthdate'),
    ('Person_Demographics_Validation.dmn', 'Death Date Consistency', 'deathDateValid', 'output',
     'n/a', 'not-persisted', ''),
    ('Person_Demographics_Validation.dmn', 'Death Date Consistency', 'reasonCode', 'output',
     'n/a', 'not-persisted', ''),

    # --- Patient_Identifier_Validation.dmn ---
    ('Patient_Identifier_Validation.dmn', 'Preferred Identifier Requirement', 'anyPreferredFlagged', 'input',
     'patient_identifier.preferred', 'derived',
     'EXISTS(SELECT 1 FROM patient_identifier WHERE patient_id=? AND preferred=true)'),
    ('Patient_Identifier_Validation.dmn', 'Preferred Identifier Requirement', 'identifierCount', 'input',
     'patient_identifier.patient_id', 'direct - aggregate',
     'COUNT(*) FROM patient_identifier GROUP BY patient_id (active or all, per patient.voided)'),
    ('Patient_Identifier_Validation.dmn', 'Preferred Identifier Requirement', 'preferredIdentifierValid', 'output',
     'n/a', 'not-persisted', ''),
    ('Patient_Identifier_Validation.dmn', 'Preferred Identifier Requirement', 'reasonCode', 'output',
     'n/a', 'not-persisted', ''),

    ('Patient_Identifier_Validation.dmn', 'Identifier Location Requirement', 'locationSet', 'input',
     'patient_identifier.location_id', 'derived', 'location_id IS NOT NULL'),
    ('Patient_Identifier_Validation.dmn', 'Identifier Location Requirement', 'locationBehavior', 'input',
     'patient_identifier_type.location_behavior', 'direct - exact match',
     'stored enum-like VARCHAR; null treated as REQUIRED per validator L96'),
    ('Patient_Identifier_Validation.dmn', 'Identifier Location Requirement', 'locationRequirementValid', 'output',
     'n/a', 'not-persisted', ''),
    ('Patient_Identifier_Validation.dmn', 'Identifier Location Requirement', 'reasonCode', 'output',
     'n/a', 'not-persisted', ''),

    ('Patient_Identifier_Validation.dmn', 'Identifier Uniqueness Check', 'uniquenessBehavior', 'input',
     'patient_identifier_type.uniqueness_behavior', 'direct - exact match', ''),
    ('Patient_Identifier_Validation.dmn', 'Identifier Uniqueness Check', 'inUseByAnotherPatient', 'input',
     'patient_identifier.identifier, patient_identifier.identifier_type, patient_identifier.patient_id',
     'derived',
     'EXISTS(SELECT 1 FROM patient_identifier pi2 WHERE pi2.identifier=this.identifier AND '
     'pi2.identifier_type=this.identifier_type AND pi2.patient_id<>this.patient_id AND pi2.voided=false)'),
    ('Patient_Identifier_Validation.dmn', 'Identifier Uniqueness Check', 'duplicateWithinSamePatient', 'input',
     'patient_identifier.identifier, patient_identifier.location_id, patient_identifier.patient_identifier_id',
     'derived',
     'self-join over the same patient_id per PatientIdentifierValidator L112-130 '
     '(globally-unique type, or same/null location match)'),
    ('Patient_Identifier_Validation.dmn', 'Identifier Uniqueness Check', 'identifierUniquenessValid', 'output',
     'n/a', 'not-persisted', ''),
    ('Patient_Identifier_Validation.dmn', 'Identifier Uniqueness Check', 'reasonCode', 'output',
     'n/a', 'not-persisted', ''),

    ('Patient_Identifier_Validation.dmn', 'Identifier Format And Check-Digit Validity', 'identifierBlank', 'input',
     'patient_identifier.identifier', 'derived', 'identifier IS NULL OR TRIM(identifier) = \'\''),
    ('Patient_Identifier_Validation.dmn', 'Identifier Format And Check-Digit Validity', 'formatSet', 'input',
     'patient_identifier_type.format', 'derived', 'format IS NOT NULL'),
    ('Patient_Identifier_Validation.dmn', 'Identifier Format And Check-Digit Validity', 'identifierMatchesFormat', 'input',
     'patient_identifier.identifier, patient_identifier_type.format', 'derived',
     'regex match of identifier against format (application-level, format is a regex string column)'),
    ('Patient_Identifier_Validation.dmn', 'Identifier Format And Check-Digit Validity', 'validatorSet', 'input',
     'patient_identifier_type.validator', 'derived', 'validator IS NOT NULL (stores an IdentifierValidator class name)'),
    ('Patient_Identifier_Validation.dmn', 'Identifier Format And Check-Digit Validity', 'checkDigitValid', 'input',
     'patient_identifier.identifier, patient_identifier_type.validator', 'SCHEMA GAP (partial)',
     'check-digit ALGORITHM itself lives in Java (e.g. LuhnIdentifierValidator), not in the DB; '
     'only the class-name pointer is a real column'),
    ('Patient_Identifier_Validation.dmn', 'Identifier Format And Check-Digit Validity', 'identifierFormatValid', 'output',
     'n/a', 'not-persisted', ''),
    ('Patient_Identifier_Validation.dmn', 'Identifier Format And Check-Digit Validity', 'reasonCode', 'output',
     'n/a', 'not-persisted', ''),

    # --- Concept_and_Observation_Validation.dmn ---
    ('Concept_and_Observation_Validation.dmn', 'Obs Value Required By Datatype', 'isObsGroup', 'input',
     'obs.obs_group_id', 'derived', 'EXISTS child obs rows with obs_group_id = this.obs_id (self-referencing FK)'),
    ('Concept_and_Observation_Validation.dmn', 'Obs Value Required By Datatype', 'conceptDatatype', 'input',
     'concept.datatype_id -> concept_datatype.name', 'direct - exact match',
     'join obs.concept_id -> concept.concept_id -> concept.datatype_id -> concept_datatype.concept_datatype_id'),
    ('Concept_and_Observation_Validation.dmn', 'Obs Value Required By Datatype', 'requiredValueColumn', 'output',
     'n/a', 'not-persisted', 'generation-guidance label; the value itself names a real obs.value_* column (see decision rules)'),

    ('Concept_and_Observation_Validation.dmn', 'Obs Group Value Exclusivity', 'isObsGroup', 'input',
     'obs.obs_group_id', 'derived', 'same as above'),
    ('Concept_and_Observation_Validation.dmn', 'Obs Group Value Exclusivity', 'anyValueFieldSet', 'input',
     'obs.value_coded, obs.value_drug, obs.value_datetime, obs.value_numeric, obs.value_modifier, '
     'obs.value_text, obs.value_complex', 'derived',
     'OR of IS NOT NULL across all value_* columns; NOTE: there is no obs.value_boolean column -- '
     'boolean answers are stored via value_coded pointing at the TRUE/FALSE concept'),
    ('Concept_and_Observation_Validation.dmn', 'Obs Group Value Exclusivity', 'obsStructureValid', 'output',
     'n/a', 'not-persisted', ''),
    ('Concept_and_Observation_Validation.dmn', 'Obs Group Value Exclusivity', 'reasonCode', 'output',
     'n/a', 'not-persisted', ''),

    ('Concept_and_Observation_Validation.dmn', 'Numeric Precision Validity', 'allowDecimal', 'input',
     'concept_numeric.allow_decimal', 'direct - exact match', 'joined via obs.concept_id = concept_numeric.concept_id'),
    ('Concept_and_Observation_Validation.dmn', 'Numeric Precision Validity', 'valueNumericHasFraction', 'input',
     'obs.value_numeric', 'derived', 'MOD(value_numeric, 1) <> 0'),
    ('Concept_and_Observation_Validation.dmn', 'Numeric Precision Validity', 'precisionValid', 'output',
     'n/a', 'not-persisted', ''),
    ('Concept_and_Observation_Validation.dmn', 'Numeric Precision Validity', 'reasonCode', 'output',
     'n/a', 'not-persisted', ''),

    ('Concept_and_Observation_Validation.dmn', 'Numeric Absolute Range Validity', 'hiAbsoluteSet', 'input',
     'concept_numeric.hi_absolute (or concept_reference_range.hi_absolute)', 'derived',
     'IS NOT NULL; OpenMRS >=2.7 prefers a matching concept_reference_range row when criteria matches the person'),
    ('Concept_and_Observation_Validation.dmn', 'Numeric Absolute Range Validity', 'valueExceedsHiAbsolute', 'input',
     'obs.value_numeric', 'derived', 'value_numeric > hi_absolute'),
    ('Concept_and_Observation_Validation.dmn', 'Numeric Absolute Range Validity', 'lowAbsoluteSet', 'input',
     'concept_numeric.low_absolute (or concept_reference_range.low_absolute)', 'derived', 'IS NOT NULL'),
    ('Concept_and_Observation_Validation.dmn', 'Numeric Absolute Range Validity', 'valueBelowLowAbsolute', 'input',
     'obs.value_numeric', 'derived', 'value_numeric < low_absolute'),
    ('Concept_and_Observation_Validation.dmn', 'Numeric Absolute Range Validity', 'absoluteRangeValid', 'output',
     'n/a', 'not-persisted', ''),
    ('Concept_and_Observation_Validation.dmn', 'Numeric Absolute Range Validity', 'reasonCode', 'output',
     'n/a', 'not-persisted', ''),

    ('Concept_and_Observation_Validation.dmn', 'Numeric Interpretation Classification', 'valueGeHiCritical', 'input',
     'concept_numeric.hi_critical, obs.value_numeric', 'derived', 'value_numeric >= hi_critical'),
    ('Concept_and_Observation_Validation.dmn', 'Numeric Interpretation Classification', 'valueGtHiNormal', 'input',
     'concept_numeric.hi_normal, obs.value_numeric', 'derived', 'value_numeric > hi_normal'),
    ('Concept_and_Observation_Validation.dmn', 'Numeric Interpretation Classification', 'valueLeLowCritical', 'input',
     'concept_numeric.low_critical, obs.value_numeric', 'derived', 'value_numeric <= low_critical'),
    ('Concept_and_Observation_Validation.dmn', 'Numeric Interpretation Classification', 'valueLtLowNormal', 'input',
     'concept_numeric.low_normal, obs.value_numeric', 'derived', 'value_numeric < low_normal'),
    ('Concept_and_Observation_Validation.dmn', 'Numeric Interpretation Classification', 'interpretation', 'output',
     'obs.interpretation', 'direct - exact match', 'the ONE output in this rule set that is itself a persisted column'),

    ('Concept_and_Observation_Validation.dmn', 'Concept Preferred Name Validity', 'localePreferred', 'input',
     'concept_name.locale_preferred', 'direct - exact match', ''),
    ('Concept_and_Observation_Validation.dmn', 'Concept Preferred Name Validity', 'isIndexTerm', 'input',
     'concept_name.concept_name_type', 'derived', "concept_name_type = 'INDEX_TERM'"),
    ('Concept_and_Observation_Validation.dmn', 'Concept Preferred Name Validity', 'isShortName', 'input',
     'concept_name.concept_name_type', 'derived', "concept_name_type = 'SHORT'"),
    ('Concept_and_Observation_Validation.dmn', 'Concept Preferred Name Validity', 'voided', 'input',
     'concept_name.voided', 'direct - exact match', ''),
    ('Concept_and_Observation_Validation.dmn', 'Concept Preferred Name Validity', 'preferredNameValid', 'output',
     'n/a', 'not-persisted', ''),
    ('Concept_and_Observation_Validation.dmn', 'Concept Preferred Name Validity', 'reasonCode', 'output',
     'n/a', 'not-persisted', ''),

    # --- Order_Validation.dmn ---
    ('Order_Validation.dmn', 'Order Date Activated Consistency', 'dateActivatedSet', 'input',
     'orders.date_activated', 'derived', 'IS NOT NULL'),
    ('Order_Validation.dmn', 'Order Date Activated Consistency', 'dateActivatedIsFuture', 'input',
     'orders.date_activated', 'derived', 'date_activated > CURRENT_TIMESTAMP'),
    ('Order_Validation.dmn', 'Order Date Activated Consistency', 'dateStoppedSet', 'input',
     'orders.date_stopped', 'derived', 'IS NOT NULL'),
    ('Order_Validation.dmn', 'Order Date Activated Consistency', 'dateActivatedAfterDateStopped', 'input',
     'orders.date_activated, orders.date_stopped', 'derived', 'date_activated > date_stopped'),
    ('Order_Validation.dmn', 'Order Date Activated Consistency', 'autoExpireDateSet', 'input',
     'orders.auto_expire_date', 'derived', 'IS NOT NULL'),
    ('Order_Validation.dmn', 'Order Date Activated Consistency', 'dateActivatedAfterAutoExpireDate', 'input',
     'orders.date_activated, orders.auto_expire_date', 'derived', 'date_activated > auto_expire_date'),
    ('Order_Validation.dmn', 'Order Date Activated Consistency', 'encounterDatetimeSet', 'input',
     'encounter.encounter_datetime', 'derived', 'joined via orders.encounter_id; IS NOT NULL'),
    ('Order_Validation.dmn', 'Order Date Activated Consistency', 'encounterDatetimeAfterDateActivated', 'input',
     'encounter.encounter_datetime, orders.date_activated', 'derived', 'encounter_datetime > date_activated'),
    ('Order_Validation.dmn', 'Order Date Activated Consistency', 'dateActivatedValid', 'output',
     'n/a', 'not-persisted', ''),
    ('Order_Validation.dmn', 'Order Date Activated Consistency', 'reasonCode', 'output',
     'n/a', 'not-persisted', ''),

    ('Order_Validation.dmn', 'Order Scheduled Date Urgency Consistency', 'scheduledDateSet', 'input',
     'orders.scheduled_date', 'derived', 'IS NOT NULL'),
    ('Order_Validation.dmn', 'Order Scheduled Date Urgency Consistency', 'urgencyIsOnScheduledDate', 'input',
     'orders.urgency', 'derived', "urgency = 'ON_SCHEDULED_DATE'"),
    ('Order_Validation.dmn', 'Order Scheduled Date Urgency Consistency', 'scheduledDateUrgencyValid', 'output',
     'n/a', 'not-persisted', ''),
    ('Order_Validation.dmn', 'Order Scheduled Date Urgency Consistency', 'reasonCode', 'output',
     'n/a', 'not-persisted', ''),

    # --- Program_Enrollment_Validation.dmn ---
    ('Program_Enrollment_Validation.dmn', 'Program Enrollment Date Consistency', 'dateEnrolledIsFuture', 'input',
     'patient_program.date_enrolled', 'derived', 'date_enrolled > CURRENT_DATE'),
    ('Program_Enrollment_Validation.dmn', 'Program Enrollment Date Consistency', 'dateCompletedSet', 'input',
     'patient_program.date_completed', 'derived', 'IS NOT NULL'),
    ('Program_Enrollment_Validation.dmn', 'Program Enrollment Date Consistency', 'dateCompletedIsFuture', 'input',
     'patient_program.date_completed', 'derived', 'date_completed > CURRENT_DATE'),
    ('Program_Enrollment_Validation.dmn', 'Program Enrollment Date Consistency', 'dateCompletedBeforeDateEnrolled', 'input',
     'patient_program.date_completed, patient_program.date_enrolled', 'derived', 'date_completed < date_enrolled'),
    ('Program_Enrollment_Validation.dmn', 'Program Enrollment Date Consistency', 'enrollmentDatesValid', 'output',
     'n/a', 'not-persisted', ''),
    ('Program_Enrollment_Validation.dmn', 'Program Enrollment Date Consistency', 'reasonCode', 'output',
     'n/a', 'not-persisted', ''),

    ('Program_Enrollment_Validation.dmn', 'Patient State Date Validity', 'startDateSet', 'input',
     'patient_state.start_date', 'derived', 'IS NOT NULL'),
    ('Program_Enrollment_Validation.dmn', 'Patient State Date Validity', 'endDateSet', 'input',
     'patient_state.end_date', 'derived', 'IS NOT NULL'),
    ('Program_Enrollment_Validation.dmn', 'Patient State Date Validity', 'endDateBeforeStartDate', 'input',
     'patient_state.end_date, patient_state.start_date', 'derived', 'end_date < start_date'),
    ('Program_Enrollment_Validation.dmn', 'Patient State Date Validity', 'patientStateDatesValid', 'output',
     'n/a', 'not-persisted', ''),
    ('Program_Enrollment_Validation.dmn', 'Patient State Date Validity', 'reasonCode', 'output',
     'n/a', 'not-persisted', ''),

    # --- Relationship_and_Encounter_Validation.dmn ---
    ('Relationship_and_Encounter_Validation.dmn', 'Relationship Date Validity', 'startDateSet', 'input',
     'relationship.start_date', 'derived', 'IS NOT NULL'),
    ('Relationship_and_Encounter_Validation.dmn', 'Relationship Date Validity', 'endDateSet', 'input',
     'relationship.end_date', 'derived', 'IS NOT NULL'),
    ('Relationship_and_Encounter_Validation.dmn', 'Relationship Date Validity', 'startDateAfterEndDate', 'input',
     'relationship.start_date, relationship.end_date', 'derived', 'start_date > end_date'),
    ('Relationship_and_Encounter_Validation.dmn', 'Relationship Date Validity', 'startDateIsFuture', 'input',
     'relationship.start_date', 'derived', 'start_date > CURRENT_DATE'),
    ('Relationship_and_Encounter_Validation.dmn', 'Relationship Date Validity', 'relationshipDatesValid', 'output',
     'n/a', 'not-persisted', ''),
    ('Relationship_and_Encounter_Validation.dmn', 'Relationship Date Validity', 'reasonCode', 'output',
     'n/a', 'not-persisted', ''),

    ('Relationship_and_Encounter_Validation.dmn', 'Encounter Datetime Validity', 'visitPatientMismatch', 'input',
     'visit.patient_id, encounter.patient_id, encounter.visit_id', 'derived',
     'joined via encounter.visit_id = visit.visit_id; visit.patient_id <> encounter.patient_id'),
    ('Relationship_and_Encounter_Validation.dmn', 'Encounter Datetime Validity', 'encounterDatetimeIsFuture', 'input',
     'encounter.encounter_datetime', 'derived', 'encounter_datetime > CURRENT_TIMESTAMP'),
    ('Relationship_and_Encounter_Validation.dmn', 'Encounter Datetime Validity', 'visitSet', 'input',
     'encounter.visit_id', 'derived', 'IS NOT NULL'),
    ('Relationship_and_Encounter_Validation.dmn', 'Encounter Datetime Validity', 'encounterDatetimeBeforeVisitStart', 'input',
     'encounter.encounter_datetime, visit.date_started', 'derived', 'encounter_datetime < date_started'),
    ('Relationship_and_Encounter_Validation.dmn', 'Encounter Datetime Validity', 'encounterDatetimeAfterVisitStop', 'input',
     'encounter.encounter_datetime, visit.date_stopped', 'derived', 'encounter_datetime > date_stopped'),
    ('Relationship_and_Encounter_Validation.dmn', 'Encounter Datetime Validity', 'encounterDatetimeValid', 'output',
     'n/a', 'not-persisted', ''),
    ('Relationship_and_Encounter_Validation.dmn', 'Encounter Datetime Validity', 'reasonCode', 'output',
     'n/a', 'not-persisted', ''),
]


def build():
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['dmn_file', 'decision_name', 'variable_name', 'io', 'openmrs_table_column', 'mapping_type', 'notes'])
        for row in ROWS:
            w.writerow(row)
    print(f'wrote {OUT_PATH} ({len(ROWS)} rows)')


if __name__ == '__main__':
    build()
