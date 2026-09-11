#!/usr/bin/env python3
"""
Defines the 12 curated FLEX2 decisions (grounded in NUCES "Academic Rules
and Regulations, Revised August 2020") and emits 8 Camunda-7-compatible
DMN 1.3 files, one per decision area, each internally wired as a small DRD
where one decision consumes another's output.

Run: python3 build_flex2_dmn.py
Writes into ../dmn/
"""
import os
from dmn_builder import write_dmn

OUT_DIR = os.path.join(os.path.dirname(__file__), '..', 'dmn')
os.makedirs(OUT_DIR, exist_ok=True)


def R(inp, out, desc=None):
    return {'in': inp, 'out': out, 'desc': desc}


# ---------------------------------------------------------------------------
# FILE 1: Academic_Standing.dmn
# ---------------------------------------------------------------------------
AcademicWarningStatus = {
    'id': 'Decision_AcademicWarningStatus',
    'name': 'Academic Warning Status',
    'hit_policy': 'UNIQUE',
    'requires': [],
    'inputs': [
        {'label': 'Cumulative GPA', 'expr': 'cumulativeGPA', 'type': 'number'},
        {'label': 'Prior Warning Count', 'expr': 'priorWarningCount', 'type': 'number'},
    ],
    'outputs': [
        {'label': 'New Warning Count', 'name': 'newWarningCount', 'type': 'number'},
        {'label': 'Admission Status', 'name': 'admissionStatus', 'type': 'string'},
        {'label': 'Warning Action', 'name': 'warningAction', 'type': 'string'},
    ],
    'rules': [
        R(['>= 2.00', '0'], ['0', '"Active"', '"None"'], 'Rule 5.4'),
        R(['>= 2.00', '1'], ['0', '"Active"', '"Warning cleared"'], 'Rule 5.7'),
        R(['>= 2.00', '2'], ['0', '"Active"', '"Warning cleared"'], 'Rule 5.7'),
        R(['< 2.00', '0'], ['1', '"Active"', '"Issue 1st academic warning"'], 'Rule 5.5'),
        R(['< 2.00', '1'], ['2', '"Active"',
           '"Issue 2nd academic warning; parents/guardian called to campus"'], 'Rules 5.5, 4.4d'),
        R(['< 2.00', '2'], ['3', '"Closed"',
           '"3rd consecutive low-CGPA semester: admission automatically closed"'], 'Rules 5.6, 3.24'),
    ],
}

CourseLoadLimit = {
    'id': 'Decision_CourseLoadLimit',
    'name': 'Course Load Limit',
    'hit_policy': 'UNIQUE',
    'requires': ['Decision_AcademicWarningStatus'],
    'inputs': [
        {'label': 'Semester Type', 'expr': 'semesterType', 'type': 'string',
         'values': '"Regular","Summer"'},
        {'label': 'New Warning Count', 'expr': 'newWarningCount', 'type': 'number'},
    ],
    'outputs': [
        {'label': 'Max Courses Allowed', 'name': 'maxCoursesAllowed', 'type': 'number'},
        {'label': 'Course Load Basis', 'name': 'courseLoadBasis', 'type': 'string'},
    ],
    'rules': [
        R(['"Regular"', '0'], ['99', '"Per approved study plan (rule 1.17) - not capped by this rule"'], 'Rule 1.17'),
        R(['"Regular"', '1'], ['5', '"Capped at 5 due to 1st academic warning"'], 'Rule 4.4c'),
        R(['"Regular"', '2'], ['5',
           '"Capped at 5 due to 2nd academic warning; new-course registration additionally restricted"'], 'Rule 4.4c/4.4e'),
        R(['"Summer"', '-'], ['2', '"Summer semester cap of 2 courses"'], 'Rule 6.6'),
    ],
}

AdmissionClosureEligibility = {
    'id': 'Decision_AdmissionClosureEligibility',
    'name': 'Admission Closure Eligibility',
    'hit_policy': 'FIRST',
    'requires': ['Decision_AcademicWarningStatus'],
    # NOTE: 'extensionApproved' (rule 3.25's "unless extension is approved" carve-out) and
    # 'disciplinaryCommitteeRecommendsClosure' (rule 3.27) were removed from this decision:
    # FLEX2's 220-table schema has no duration-extension-approval table/column and no
    # Disciplinary Committee / case table, so neither could be validated against the DDL.
    # Rule 3.27 is dropped entirely (it had no other mappable condition); rule 3.25 keeps
    # its mappable half (maxDurationExceeded) and drops the unenforceable exception.
    'inputs': [
        {'label': 'New Warning Count', 'expr': 'newWarningCount', 'type': 'number'},
        {'label': 'Years Since Program Start', 'expr': 'yearsSinceProgramStart', 'type': 'number'},
        {'label': 'Registration Status', 'expr': 'regStatus', 'type': 'string',
         'values': '"ACTIVE","SUSPENDED_NOT_RESTORED","..."'},
        {'label': 'New-Admission Eligibility Not Met', 'expr': 'newAdmissionEligibilityNotMet', 'type': 'boolean'},
    ],
    'outputs': [
        {'label': 'Admission Status', 'name': 'admissionStatus', 'type': 'string'},
        {'label': 'Closure Reason', 'name': 'closureReason', 'type': 'string'},
    ],
    'rules': [
        R(['3', '-', '-', '-'],
          ['"Closed"', '"3rd consecutive academic warning (CGPA<2.00 for 3 consecutive semesters)"'], 'Rules 3.24, 5.6'),
        R(['-', '> 7', '-', '-'],
          ['"Closed"', '"Maximum duration to complete degree exceeded"'],
          'Rule 3.25 -- exposed as a real date-derived duration compared against the 7-year cap, replacing maxDurationExceeded (redesigned 2026-09-10)'),
        R(['-', '-', '"SUSPENDED_NOT_RESTORED"', '-'],
          ['"Closed"', '"Failure to restore suspended registration"'],
          "Rule 3.26 -- exposed as a real status-code test against STUDENT_PROGRAM.REG_STATUS (via D_STUDENT_REG_STATUS), replacing suspendedRegistrationNotRestored; the specific code value is unconfirmed since Flex1.sql ships no seed/reference data, same caveat already documented for this schema's other coded values"),
        R(['-', '-', '-', 'true'],
          ['"Closed"', '"Awaited result did not meet eligibility criteria for the degree program"'], 'Rule 3.28'),
        R(['-', '-', '-', '-'], ['"Open"', '"No closure condition met"']),
    ],
}

CourseRegistrationEligibility = {
    'id': 'Decision_CourseRegistrationEligibility',
    'name': 'Course Registration Eligibility',
    'hit_policy': 'FIRST',
    'requires': ['Decision_AcademicWarningStatus', 'Decision_CourseLoadLimit'],
    'inputs': [
        {'label': 'Unmet Prerequisite Count', 'expr': 'unmetPrerequisiteCount', 'type': 'number'},
        {'label': 'New Warning Count', 'expr': 'newWarningCount', 'type': 'number'},
        {'label': 'Previous Grade In This Course', 'expr': 'previousGradeInCourse', 'type': 'string',
         'values': '"F","D","D+","C-","C","..."'},
        {'label': 'Projected Total Courses This Registration', 'expr': 'projectedTotalCoursesThisRegistration', 'type': 'number'},
        {'label': 'Max Courses Allowed', 'expr': 'maxCoursesAllowed', 'type': 'number'},
    ],
    'outputs': [
        {'label': 'Can Register Course', 'name': 'canRegisterCourse', 'type': 'boolean'},
        {'label': 'Reason', 'name': 'reason', 'type': 'string'},
    ],
    'rules': [
        R(['> 0', '-', '-', '-', '-'], ['false', '"Pre-requisite course(s) not passed"'],
          'Rule 1.20 -- exposed as a count over COURSE_PREREQ join COURSE_REGISTRATION.GRADE, replacing allPrerequisitesPassed (redesigned 2026-09-10)'),
        R(['-', '2', 'not("F","D","D+","C-")', '-', '-'],
          ['false', '"On 2nd academic warning: may not register for a new (non-mandatory) course without HoD recommendation + Controller approval"'],
          'Rule 4.4e -- exposed as a real FEEL list-membership test against the previous grade, replacing isMandatoryReregistration'),
        R(['-', '-', '-', '> maxCoursesAllowed', '-'],
          ['false', '"Exceeds maximum permitted course load"'], 'Rules 1.19, 4.3, 4.4c'),
        R(['-', '-', '-', '-', '-'], ['true', '"Eligible"']),
    ],
}

write_dmn(
    [AcademicWarningStatus, CourseLoadLimit, AdmissionClosureEligibility, CourseRegistrationEligibility],
    'Definitions_AcademicStanding', 'Academic Standing',
    os.path.join(OUT_DIR, 'Academic_Standing.dmn'),
)

# ---------------------------------------------------------------------------
# FILE 2: Grading_and_Attendance.dmn
# ---------------------------------------------------------------------------
# AttendancePercentage: a calculation decision (no branching, just a formula),
# inserted so the eligibility rule below is driven off two RAW, per-course-
# offering counts instead of an already-computed percentage. Both counts are
# course-wise and duration-driven, not a fixed number for every course:
#   - lecturesHeldForOffering = COUNT(LECTURE) WHERE OFFER_ID = <this course
#     offering>. LECTURE is FLEX2's actual record of how many sessions were
#     held for THIS course in THIS semester - it varies by course (credit
#     hours, weekly frequency) and by how long that offering's semester ran
#     (COURSE_OFFER.START_DATE/END_DATE), so a 3-credit course might show 45
#     LECTURE rows and a 1-credit lab might show 15 - never a hardcoded "30".
#   - lecturesAttended = COUNT(STUDENT_ATTENDANCE) WHERE ROLL_NO = <student>
#     AND LECTURE_ID IN (those LECTURE rows) AND ATTEND_FLAG = 'Y'.
# This makes the rule directly usable for data generation: to hit a target
# outcome for a given course offering, generate `lecturesHeldForOffering`
# LECTURE rows (sized to that course's actual duration) and however many
# matching STUDENT_ATTENDANCE rows are needed to land above/below 80%.
AttendancePercentage = {
    'id': 'Decision_AttendancePercentage',
    'name': 'Attendance Percentage',
    'kind': 'literal_expression',
    'requires': [],
    'variable': {'name': 'attendancePercentage', 'type': 'number'},
    'expression': '(lecturesAttended / lecturesHeldForOffering) * 100',
}

AttendanceEligibility = {
    'id': 'Decision_AttendanceEligibility',
    'name': 'Attendance Eligibility For Final Exam',
    'hit_policy': 'UNIQUE',
    'requires': ['Decision_AttendancePercentage'],
    # NOTE: 'hodCondonationApproved' (rule 1.21's "HoD may condone up to 20% absence for
    # genuine reasons" carve-out) was removed: FLEX2 has no condonation-approval column, so
    # this branch could not be validated against the schema. What remains is the direct,
    # fully schema-backed threshold, now fed by the AttendancePercentage decision above
    # instead of assuming the percentage arrives pre-computed.
    'inputs': [
        {'label': 'Attendance Percentage', 'expr': 'attendancePercentage', 'type': 'number'},
    ],
    'outputs': [
        {'label': 'Eligible For Final Exam (Not Debarred)', 'name': 'eligibleForFinalExam', 'type': 'boolean'},
        {'label': 'Assigned Grade Override', 'name': 'assignedGradeOverride', 'type': 'string'},
    ],
    'rules': [
        R(['>= 80'], ['true', 'null'], 'Rule 1.21: attendance >= 80% - eligible, not debarred'),
        R(['< 80'], ['false', '"FA"'], 'Rule 1.22: attendance < 80% - debarred from final exam, FA grade'),
    ],
}

GradePointsAndInterpretation = {
    'id': 'Decision_GradePointsAndInterpretation',
    'name': 'Grade Points and Interpretation',
    'hit_policy': 'UNIQUE',
    'requires': [],
    'inputs': [
        {'label': 'Letter Grade', 'expr': 'letterGrade', 'type': 'string',
         'values': '"A+","A","A-","B+","B","B-","C+","C","C-","D+","D","F","FA","I","W"'},
    ],
    'outputs': [
        {'label': 'Grade Points', 'name': 'gradePoints', 'type': 'number'},
        {'label': 'Interpretation', 'name': 'interpretation', 'type': 'string'},
    ],
    'rules': [
        R(['"A+"'], ['4.00', '"Outstanding"'], 'Rules 2.2, 2.3'),
        R(['"A"'], ['4.00', '"Excellent"'], 'Rules 2.2, 2.3'),
        R(['"A-"'], ['3.67', '"Excellent"'], 'Rules 2.2, 2.3'),
        R(['"B+"'], ['3.33', '"Good"'], 'Rules 2.2, 2.3'),
        R(['"B"'], ['3.00', '"Good"'], 'Rules 2.2, 2.3'),
        R(['"B-"'], ['2.67', '"Good"'], 'Rules 2.2, 2.3'),
        R(['"C+"'], ['2.33', '"Adequate"'], 'Rules 2.2, 2.3'),
        R(['"C"'], ['2.00', '"Adequate"'], 'Rules 2.2, 2.3'),
        R(['"C-"'], ['1.67', '"Pass, the student may repeat the course"'], 'Rules 2.2, 2.3'),
        R(['"D+"'], ['1.33', '"Pass, the student may repeat the course"'], 'Rules 2.2, 2.3'),
        R(['"D"'], ['1.00', '"Pass, the student may repeat the course"'], 'Rules 2.2, 2.3'),
        R(['"F"'], ['0.00', '"Fail"'], 'Rules 2.2, 2.3'),
        R(['"FA"'], ['0.00', '"Fail due to shortage of attendance"'], 'Rules 2.2, 2.3'),
        R(['"I"'], ['null', '"Incomplete"'], 'Rules 2.2, 2.9'),
        R(['"W"'], ['null', '"Withdrawn"'], 'Rules 2.2, 2.8'),
    ],
}

write_dmn(
    [AttendancePercentage, AttendanceEligibility, GradePointsAndInterpretation],
    'Definitions_GradingAndAttendance', 'Grading and Attendance',
    os.path.join(OUT_DIR, 'Grading_and_Attendance.dmn'),
)

# ---------------------------------------------------------------------------
# FILE 3: Course_Replacement_Eligibility.dmn
# ---------------------------------------------------------------------------
CourseReplacementEligibility = {
    'id': 'Decision_CourseReplacementEligibility',
    'name': 'Course Replacement Eligibility',
    'hit_policy': 'FIRST',
    'requires': [],
    'inputs': [
        {'label': 'Credits Earned', 'expr': 'creditsEarned', 'type': 'number'},
        {'label': 'Degree Total Credits', 'expr': 'degreeTotalCredits', 'type': 'number'},
        {'label': 'Grade In Course To Replace', 'expr': 'gradeInCourseToReplace', 'type': 'string'},
        {'label': 'Course Offered In Following Semesters', 'expr': 'courseOfferedInFollowingSemesters', 'type': 'boolean'},
        {'label': 'Replacing Course Passed At Least One Semester After',
         'expr': 'replacingCoursePassedAtLeastOneSemesterAfter', 'type': 'boolean'},
        {'label': 'Course Type', 'expr': 'courseTypeId', 'type': 'string', 'values': '"CORE","ELECTIVE","..."'},
    ],
    'outputs': [
        {'label': 'Eligible For Replacement', 'name': 'eligibleForReplacement', 'type': 'boolean'},
        {'label': 'Reason', 'name': 'reason', 'type': 'string'},
    ],
    'rules': [
        R(['-', '-', '-', '-', '-', '"CORE"'], ['false', '"Core courses cannot be replaced"'],
          'Rule 4.28 -- exposed as a real category test against COURSE.COURSE_TYPE_ID (via D_COURSE_TYPE), replacing isCoreCourse (redesigned 2026-09-10)'),
        R(['-', '-', 'not("F")', '-', '-', '-'], ['false', '"Only a course with grade F may be replaced"'], 'Rule 4.27(b)'),
        R(['< degreeTotalCredits', '-', '-', '-', '-', '-'],
          ['false', '"Student has not completed / is not completing degree requirements this semester"'],
          'Rule 4.27(a) -- exposed as a real cross-variable comparison (creditsEarned < degreeTotalCredits), replacing degreeRequirementsCompletedOrCompletingThisSemester'),
        R(['-', '-', '-', 'true', '-', '-'],
          ['false', '"Course to be replaced was offered again in a following semester"'], 'Rule 4.27(c)'),
        R(['-', '-', '-', '-', 'false', '-'],
          ['false', '"Replacing course must be passed at least one semester after the course being replaced"'], 'Rule 4.27(d)'),
        R(['-', '-', '-', '-', '-', '-'],
          ['true', '"Eligible for course replacement, subject to Dean\'s approval"'], 'Rule 4.27'),
    ],
}

write_dmn(
    [CourseReplacementEligibility],
    'Definitions_CourseReplacement', 'Course Replacement Eligibility',
    os.path.join(OUT_DIR, 'Course_Replacement_Eligibility.dmn'),
)

# ---------------------------------------------------------------------------
# FILE 4: Graduation_Eligibility.dmn
# ---------------------------------------------------------------------------
GraduationEligibility = {
    'id': 'Decision_GraduationEligibility',
    'name': 'Graduation Eligibility',
    'hit_policy': 'FIRST',
    'requires': [],
    'inputs': [
        {'label': 'Credit Hours Earned', 'expr': 'creditHoursEarned', 'type': 'number'},
        {'label': 'Degree Minimum Credit Hours', 'expr': 'degreeMinimumCreditHours', 'type': 'number'},
        {'label': 'Cumulative GPA', 'expr': 'cumulativeGPA', 'type': 'number'},
        {'label': 'Semesters Elapsed', 'expr': 'semestersElapsed', 'type': 'number'},
        {'label': 'Years Elapsed', 'expr': 'yearsElapsed', 'type': 'number'},
    ],
    'outputs': [
        {'label': 'Eligible To Graduate', 'name': 'eligibleToGraduate', 'type': 'boolean'},
        {'label': 'Reason', 'name': 'reason', 'type': 'string'},
    ],
    'rules': [
        R(['< degreeMinimumCreditHours', '-', '-', '-', '-'],
          ['false', '"Credit hours earned below the program\'s required minimum"'], 'Rule 1.25'),
        R(['-', '-', '< 2.00', '-', '-'],
          ['false', '"CGPA below the minimum 2.00 required for graduation"'], 'Rule 1.26'),
        R(['-', '-', '-', '< 8', '-'],
          ['false', '"Cannot graduate before completing the minimum duration of 4 years / 8 regular semesters"'], 'Rule 1.23'),
        R(['-', '-', '-', '-', '> 7'],
          ['false', '"Exceeded the maximum allowed duration of 7 years"'], 'Rule 1.23'),
        R(['-', '-', '-', '-', '-'],
          ['true', '"Meets minimum credit-hour, CGPA, and duration requirements for graduation"']),
    ],
}

write_dmn(
    [GraduationEligibility],
    'Definitions_GraduationEligibility', 'Graduation Eligibility',
    os.path.join(OUT_DIR, 'Graduation_Eligibility.dmn'),
)

# ---------------------------------------------------------------------------
# REMOVED: Academic_Honesty_Penalty.dmn (rules 8.14-8.18)
# Every input (referredTo, isExtremeActOrRepeatOffense) and two of the three
# outputs (penaltyScope, disqualifiedFromHonors) had no matching FLEX2 table -
# there is no Disciplinary Committee / case-referral table among FLEX2's 220
# tables at all. The one output that partially mapped (maxPenalty, via
# COURSE_REGISTRATION.GRADE for the "F in course" outcome) isn't enough to
# keep a whole decision whose branching logic depends entirely on unmappable
# inputs. Dropped rather than drafted against a schema that can't represent it.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# REMOVED: Honor_List_Eligibility.dmn (rules 7.3-7.8)
# Inputs (semesterGPA, creditHoursThisSemester, completedRegularCourseLoadPer-
# StudyPlan) do map to FLEX2 (STUDENT_SEMESTER.SGPA etc.), but the decision's
# only output - honorCategory (Rector's/Dean's List membership) - has no flag
# column anywhere in FLEX2; rules 7.4/7.7 themselves describe it as
# issued/displayed on the university website, i.e. presentation-layer, not
# persisted. A decision whose sole output can't be written back to the schema
# isn't useful for schema-grounded data generation, so it's dropped.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# FILE 6: Summer_Semester_Registration.dmn
# ---------------------------------------------------------------------------
SummerSemesterRegistration = {
    'id': 'Decision_SummerSemesterRegistration',
    'name': 'Summer Semester Registration',
    'hit_policy': 'FIRST',
    'requires': [],
    'inputs': [
        {'label': 'Course Type', 'expr': 'courseTypeId', 'type': 'string', 'values': '"RESEARCH","REGULAR","..."'},
        {'label': 'Prior Registration Count (this student, this course)', 'expr': 'priorRegistrationCount', 'type': 'number'},
        {'label': 'Is Elective Taught By Unavailable-Otherwise Visiting Scholar',
         'expr': 'isElectiveTaughtByVisitingScholarUnavailableOtherwise', 'type': 'boolean'},
        {'label': 'Is Needed To Graduate This Summer', 'expr': 'isNeededToGraduateThisSummer', 'type': 'boolean'},
        {'label': 'Repeat Course Count Requested', 'expr': 'repeatCourseCountRequested', 'type': 'number'},
        {'label': 'Enrolled Student Count', 'expr': 'enrolledStudentCount', 'type': 'number'},
    ],
    'outputs': [
        {'label': 'Registration Allowed', 'name': 'registrationAllowed', 'type': 'boolean'},
        {'label': 'Reason', 'name': 'reason', 'type': 'string'},
    ],
    'rules': [
        R(['"RESEARCH"', '-', '-', '-', '-', '-'],
          ['false', '"Research courses/projects are not offered in summer"'],
          'Rule 6.3 -- exposed as a real category test against COURSE.COURSE_TYPE_ID, replacing isResearchCourseOrProject (redesigned 2026-09-10)'),
        R(['not("RESEARCH")', '0', 'false', 'false', '-', '-'],
          ['false', '"New (non-exempt) course registration is not allowed in summer"'],
          'Rule 6.4 -- exposed as a real count (priorRegistrationCount = 0, i.e. no prior COURSE_REGISTRATION row), replacing isNewCourseRequest'),
        R(['not("RESEARCH")', '-', '-', '-', '> 2', '-'],
          ['false', '"Maximum of 2 repeat courses (with associated labs) allowed in summer"'], 'Rule 6.6'),
        R(['not("RESEARCH")', '-', '-', '-', '-', '< 10'],
          ['false', '"Course requires a minimum of 10 registered students to run"'],
          'Rule 6.10 -- exposed as a real count (COUNT(COURSE_REGISTRATION) for the offering), replacing minimumTenStudentsEnrolled'),
        R(['not("RESEARCH")', '-', '-', '-', '-', '-'], ['true', '"Eligible for summer registration"']),
    ],
}

write_dmn(
    [SummerSemesterRegistration],
    'Definitions_SummerRegistration', 'Summer Semester Registration',
    os.path.join(OUT_DIR, 'Summer_Semester_Registration.dmn'),
)

# ---------------------------------------------------------------------------
# FILE 7: Credit_Transfer_Exemption.dmn
# ---------------------------------------------------------------------------
CreditTransferExemption = {
    'id': 'Decision_CreditTransferExemption',
    'name': 'Credit Transfer Exemption',
    'hit_policy': 'FIRST',
    'requires': [],
    # NOTE: 'gpaInCourseAtPreviousInstitution' (rule 3.10's "grade must be C or above at the
    # previous institution") was removed: EXEMPTED_COURSES has only a free-text REMARKS
    # column, not a structured grade/GPA field, so this condition can't be evaluated from
    # the schema. Rule 3.10 is dropped entirely along with it (it had no other condition).
    'inputs': [
        {'label': 'Cumulative Exempted Credit Percent If Granted',
         'expr': 'cumulativeExemptedCreditPercentIfGranted', 'type': 'number'},
        {'label': 'Unmet Prerequisite-Also-Passed Count', 'expr': 'unmetPrerequisiteAlsoPassedCount', 'type': 'number'},
    ],
    'outputs': [
        {'label': 'Exemption Granted', 'name': 'exemptionGranted', 'type': 'boolean'},
        {'label': 'Credit Given For Prerequisite', 'name': 'creditGivenForPrerequisite', 'type': 'boolean'},
        {'label': 'Counts Toward CGPA', 'name': 'countsTowardCGPA', 'type': 'boolean'},
        {'label': 'Reason', 'name': 'reason', 'type': 'string'},
    ],
    'rules': [
        R(['> 50', '-'],
          ['false', 'false', 'false', '"Would exceed the 50% cap on exempted credit hours of the degree program"'], 'Rule 3.7'),
        R(['-', '0'],
          ['true', 'true', 'false', '"Exemption granted; credit also given for the passed pre-requisite course"'],
          'Rules 3.11, 3.12 -- exposed as a count over COURSE_PREREQ join COURSE_REGISTRATION, replacing prerequisiteCourseAlsoPassed (redesigned 2026-09-10)'),
        R(['-', '> 0'],
          ['true', 'false', 'false', '"Exemption granted; only credit hours transfer, CGPA from previous institution does not"'], 'Rule 3.12'),
    ],
}

write_dmn(
    [CreditTransferExemption],
    'Definitions_CreditTransferExemption', 'Credit Transfer Exemption',
    os.path.join(OUT_DIR, 'Credit_Transfer_Exemption.dmn'),
)

print("All 6 DMN files written to", os.path.abspath(OUT_DIR))
for f in sorted(os.listdir(OUT_DIR)):
    print(" -", f)

# ---------------------------------------------------------------------------
# Rule Provenance Matrix (decision-rule granularity), generated straight from
# the same data structures used to build the DMN, so it can never drift from
# the actual rule content.
# ---------------------------------------------------------------------------
import csv

ALL = [
    ('Academic_Standing.dmn', AcademicWarningStatus),
    ('Academic_Standing.dmn', CourseLoadLimit),
    ('Academic_Standing.dmn', AdmissionClosureEligibility),
    ('Academic_Standing.dmn', CourseRegistrationEligibility),
    ('Grading_and_Attendance.dmn', AttendancePercentage),
    ('Grading_and_Attendance.dmn', AttendanceEligibility),
    ('Grading_and_Attendance.dmn', GradePointsAndInterpretation),
    ('Course_Replacement_Eligibility.dmn', CourseReplacementEligibility),
    ('Graduation_Eligibility.dmn', GraduationEligibility),
    ('Summer_Semester_Registration.dmn', SummerSemesterRegistration),
    ('Credit_Transfer_Exemption.dmn', CreditTransferExemption),
]
# Academic_Honesty_Penalty.dmn and Honor_List_Eligibility.dmn were removed
# entirely (see the REMOVED notes above) - every rule in each depended on
# data FLEX2's schema doesn't have.

SOURCE_DOC = "NUCES Academic Rules and Regulations for Undergraduate Programs, Revised August 2020"
PAGE_BY_CLAUSE_PREFIX = {
    '1.1': 2, '1.2': 2, '1.3': 3,  # fallback, refined per-clause below
}
# explicit page map for every clause number cited (from the PDF pages read this session)
PAGE_MAP = {}
for c in ['1.7', '1.8', '1.9', '1.10', '1.11', '1.12', '1.13', '1.14', '1.15', '1.16']:
    PAGE_MAP[c] = 2
for c in ['1.17', '1.18', '1.19', '1.20', '1.21', '1.22', '1.23', '1.24', '1.25', '1.26']:
    PAGE_MAP[c] = 3
for c in ['2.1', '2.2', '2.3', '2.4', '2.5', '2.6', '2.7', '2.8']:
    PAGE_MAP[c] = 4
PAGE_MAP['2.9'] = 5
for c in ['3.1', '3.2', '3.3', '3.4', '3.5', '3.6', '3.7', '3.8', '3.9', '3.10', '3.11', '3.12',
          '3.13', '3.14', '3.15', '3.16', '3.17']:
    PAGE_MAP[c] = 6
for c in ['3.18', '3.19', '3.20', '3.21', '3.22', '3.23', '3.24', '3.25', '3.26', '3.27', '3.28', '3.29']:
    PAGE_MAP[c] = 7
for c in ['4.1', '4.2', '4.3', '4.4', '4.4a', '4.4b', '4.4c', '4.4d', '4.4e',
          '4.5', '4.6', '4.7', '4.8', '4.9', '4.10', '4.11', '4.12', '4.13']:
    PAGE_MAP[c] = 8
for c in ['4.14', '4.15', '4.16', '4.17', '4.18', '4.19', '4.20', '4.21', '4.22', '4.23', '4.24',
          '4.25', '4.26', '4.27', '4.27(a)', '4.27(b)', '4.27(c)', '4.27(d)', '4.28']:
    PAGE_MAP[c] = 9
for c in ['5.1', '5.2', '5.3', '5.4', '5.5', '5.6', '5.7', '5.8', '5.9', '5.10', '5.11', '5.12',
          '5.13', '5.14']:
    PAGE_MAP[c] = 10
for c in ['5.15', '5.16', '5.17', '5.18', '5.19', '5.20', '5.21', '5.22', '5.23', '5.24']:
    PAGE_MAP[c] = 11
for c in ['6.1', '6.2', '6.3', '6.4', '6.5', '6.6', '6.7', '6.8', '6.9', '6.10', '6.11', '6.12', '6.13']:
    PAGE_MAP[c] = 12
for c in ['7.1', '7.2', '7.3', '7.4', '7.5', '7.6', '7.7', '7.8', '7.9', '7.10', '7.11']:
    PAGE_MAP[c] = 13
for c in ['8.1', '8.2', '8.3', '8.4', '8.5', '8.6', '8.7', '8.8', '8.9', '8.10', '8.11', '8.12', '8.13']:
    PAGE_MAP[c] = 14
for c in ['8.14', '8.15', '8.16', '8.17', '8.18']:
    PAGE_MAP[c] = 15


def pages_for(desc):
    if not desc:
        return ''
    import re
    clauses = re.findall(r'\d+\.\d+[a-e]?(?:\([a-d]\))?', desc)
    pages = sorted(set(PAGE_MAP.get(c) for c in clauses if PAGE_MAP.get(c)))
    return ';'.join(str(p) for p in pages)


rows = []
for dmn_file, dec in ALL:
    if dec.get('kind') == 'literal_expression':
        # A calculation decision has no rule table - emit one synthetic row
        # documenting the formula itself, so it's still traceable.
        rows.append({
            'dmn_file': dmn_file,
            'decision_name': dec['name'],
            'hit_policy': '(literal expression - not a decision table)',
            'dmn_rule_id': f"{dec['id']}_Expr",
            'policy_clause(s)': 'Derived calculation (not a numbered policy clause) - '
                                 'feeds Attendance Eligibility (rules 1.21/1.22)',
            'source_document': SOURCE_DOC,
            'source_page(s)': '3',
            'source_tier': 'Tier 4 (researcher-authored formula, standard % calculation)',
            'input_condition': f"formula: {dec['expression']}",
            'output': f"{dec['variable']['name']} = {dec['expression']}",
            'extraction_method': 'Derived from FLEX2 schema (LECTURE, STUDENT_ATTENDANCE) to feed the '
                                  'policy-sourced threshold rule below it',
            'validated_by': '(pending human review by researcher)',
        })
        continue
    for i, rule in enumerate(dec['rules'], start=1):
        rows.append({
            'dmn_file': dmn_file,
            'decision_name': dec['name'],
            'hit_policy': dec.get('hit_policy', 'UNIQUE'),
            'dmn_rule_id': f"{dec['id']}_Rule_{i}",
            'policy_clause(s)': rule.get('desc') or '(no specific clause - default/catch-all row)',
            'source_document': SOURCE_DOC,
            'source_page(s)': pages_for(rule.get('desc')),
            'source_tier': 'Tier 1 (official institutional policy document)',
            'input_condition': ' | '.join(f"{inp['expr']}={val}" for inp, val in zip(dec['inputs'], rule['in'])),
            'output': ' | '.join(f"{outp['name']}={val}" for outp, val in zip(dec['outputs'], rule['out'])),
            'extraction_method': 'Manual transcription from PDF by Claude, reviewed against exact clause wording',
            'validated_by': '(pending human review by researcher)',
        })

prov_path = os.path.join(os.path.dirname(__file__), '..', 'provenance', 'rule_provenance_matrix.csv')
with open(prov_path, 'w', newline='') as f:
    fieldnames = ['dmn_file', 'decision_name', 'hit_policy', 'dmn_rule_id', 'policy_clause(s)',
                  'source_document', 'source_page(s)', 'source_tier', 'input_condition', 'output',
                  'extraction_method', 'validated_by']
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    w.writerows(rows)

print(f"\nRule Provenance Matrix written to {os.path.abspath(prov_path)} ({len(rows)} rule rows across {len(ALL)} decisions)")
