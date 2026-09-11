--------------------------------------------------------
--  File created - Monday-March-11-2019
--------------------------------------------------------
--------------------------------------------------------
--  DDL for Table ACTION_LOG
--------------------------------------------------------

   CREATE TABLE "FLEX2"."ACTION_LOG"
   (	"LOG_ID" NUMBER(8,0),
	"FORM_NAME" VARCHAR2(50),
	"ACTION_NAME" VARCHAR2(50),
	"ROLL_NO" NUMBER(12,0),
	"OFFER_ID" NUMBER(12,0),
	"OLD_VALUES" VARCHAR2(100),
	"NEW_VALUES" VARCHAR2(100),
	"CREATED_BY" NUMBER(8,0),
	"CREATED_ON" DATE,
	"COURSE_ID" NUMBER(4,0)
   ) ;
--------------------------------------------------------
--  DDL for Table ADM_MERIT_LIST
--------------------------------------------------------

  CREATE TABLE "FLEX2"."ADM_MERIT_LIST"
   (	"CAMP_ID" NUMBER(2,0),
	"PROG_CODE" VARCHAR2(10),
	"ARN" NUMBER(10,0),
	"TEST_TYPE" NUMBER(3,0),
	"MERIT_MARKS" NUMBER(5,2),
	"CAMP_PREF" NUMBER(1,0),
	"DISP_PREF" NUMBER(1,0),
	"IS_SELECTED" NUMBER(1,0),
	"MERIT_POS" NUMBER(8,0),
	"PROG_LEVEL" NUMBER(1,0)
   ) ;
--------------------------------------------------------
--  DDL for Table ADM_OFFER_SUMMARY
--------------------------------------------------------

  CREATE TABLE "FLEX2"."ADM_OFFER_SUMMARY"
   (	"CAMP_ID" NUMBER(2,0),
	"CAMP_CODE" VARCHAR2(10),
	"PROG_ID" NUMBER(3,0),
	"PROG_CODE" VARCHAR2(10),
	"NU_APPLS" NUMBER(8,0),
	"NTS_APPLS" NUMBER(8,0),
	"NTS_OFFER" NUMBER(8,0),
	"NU_OFFER" NUMBER(8,0),
	"SEATS" NUMBER(8,0) DEFAULT 0,
	"CUT_OFF_NU" NUMBER(5,2),
	"CUT_OFF_NTS" NUMBER(5,2),
	"PROG_LEVEL" NUMBER(1,0)
   ) ;
--------------------------------------------------------
--  DDL for Table APPMENU
--------------------------------------------------------

   CREATE TABLE "FLEX2"."APPMENU"
   (	"MENUID" NUMBER(6,0),
	"TITLE" VARCHAR2(50),
	"PAGEHEADING" VARCHAR2(100),
	"DESCRIPTION" VARCHAR2(100),
	"ICON" VARCHAR2(50),
	"URL" VARCHAR2(50),
	"DISPLAYORDER" NUMBER(3,0),
	"PARENTID" NUMBER(6,0),
	"STATUS" NUMBER(1,0) DEFAULT '1'
   ) ;
--------------------------------------------------------
--  DDL for Table APPROLE
--------------------------------------------------------

  CREATE TABLE "FLEX2"."APPROLE"
   (	"ROLEID" NUMBER,
	"TITLE" VARCHAR2(20),
	"DESCRIPTION" VARCHAR2(30)
   ) ;
--------------------------------------------------------
--  DDL for Table APPROLEDETAIL
--------------------------------------------------------

  CREATE TABLE "FLEX2"."APPROLEDETAIL"
   (	"RM_ID" NUMBER,
	"ROLEID" NUMBER,
	"MENUID" NUMBER(6,0),
	"CANADD" NUMBER(1,0),
	"CANEDIT" NUMBER(1,0),
	"CANDEL" NUMBER(1,0)
   ) ;
--------------------------------------------------------
--  DDL for Table APPUSER
--------------------------------------------------------

   CREATE TABLE "FLEX2"."APPUSER"
   (	"USERID" NUMBER,
	"USERNAME" VARCHAR2(30),
	"USERPASSWORD" VARCHAR2(50),
	"USERTYPE" VARCHAR2(15),
	"IPADDRESS" VARCHAR2(20),
	"LASTLOGIN" DATE,
	"CREATEDDATE" DATE,
	"EMP_ID" NUMBER(8,0),
	"ALLOW_DEPT_ID" VARCHAR2(20)
   ) ;
--------------------------------------------------------
--  DDL for Table APPUSERBOOKMARK
--------------------------------------------------------

   CREATE TABLE "FLEX2"."APPUSERBOOKMARK"
   (	"UM_ID" NUMBER,
	"MENUID" NUMBER(6,0),
	"USERID" NUMBER,
	"DISPLAYORDER" NUMBER(2,0)
   ) ;
--------------------------------------------------------
--  DDL for Table APPUSERCAMPUS
--------------------------------------------------------

   CREATE TABLE "FLEX2"."APPUSERCAMPUS"
   (	"UC_ID" NUMBER,
	"USERID" NUMBER,
	"CAMP_ID" NUMBER(3,0)
   ) ;
--------------------------------------------------------
--  DDL for Table APPUSERDEPARTMENT
--------------------------------------------------------

   CREATE TABLE "FLEX2"."APPUSERDEPARTMENT"
   (	"UD_ID" NUMBER,
	"USERID" NUMBER,
	"DEPT_ID" NUMBER(4,0)
   ) ;
--------------------------------------------------------
--  DDL for Table APPUSERROLE
--------------------------------------------------------

   CREATE TABLE "FLEX2"."APPUSERROLE"
   (	"UR_ID" NUMBER,
	"ROLEID" NUMBER,
	"USERID" NUMBER
   ) ;
--------------------------------------------------------
--  DDL for Table BATCH
--------------------------------------------------------

   CREATE TABLE "FLEX2"."BATCH"
   (	"BATCH_NO" NUMBER(8,0),
	"TITLE" VARCHAR2(30),
	"START_DATE" DATE,
	"SHIFT_ID" CHAR(1),
	"CREATED_BY" NUMBER(8,0),
	"CREATED_DATE" DATE DEFAULT sysdate
   ) ;
--------------------------------------------------------
--  DDL for Table BATCH_PROGRAM
--------------------------------------------------------

  CREATE TABLE "FLEX2"."BATCH_PROGRAM"
   (	"BATCH_NO" NUMBER(8,0),
	"PROG_ID" NUMBER(4,0),
	"MIN_CR_HRS" NUMBER(5,2),
	"MIN_PASS_PNTS" NUMBER(5,2),
	"MAX_RPT_PNTS" NUMBER(5,2),
	"MIN_CGPA" NUMBER(5,2),
	"AVG_COURSE" NUMBER(5,2),
	"AVG_CREDIT" NUMBER(5,2),
	"CREATED_BY" NUMBER(8,0),
	"CREATED_DATE" DATE DEFAULT sysdate
   ) ;
--------------------------------------------------------
--  DDL for Table BATCH_SECTION
--------------------------------------------------------

   CREATE TABLE "FLEX2"."BATCH_SECTION"
   (	"CAMP_ID" NUMBER(3,0),
	"BATCH_NO" NUMBER(8,0),
	"PROG_ID" NUMBER(4,0),
	"SECTION_ID" NUMBER(4,0),
	"SHIFT_ID" CHAR(1),
	"CREATED_BY" NUMBER(8,0),
	"CREATED_DATE" DATE DEFAULT sysdate
   )  ;
--------------------------------------------------------
--  DDL for Table CAMPUS
--------------------------------------------------------

   CREATE TABLE "FLEX2"."CAMPUS"
   (	"CAMP_ID" NUMBER(3,0),
	"NAME" VARCHAR2(30),
	"ABBR" VARCHAR2(4),
	"ADDRESS" VARCHAR2(150),
	"CITY" VARCHAR2(20),
	"TELNO1" VARCHAR2(15),
	"TELNO2" VARCHAR2(15),
	"FAXNO" VARCHAR2(15),
	"EMAIL" VARCHAR2(30),
	"WEB_URL" VARCHAR2(30),
	"CREATED_BY" NUMBER(8,0),
	"CREATED_DATE" DATE DEFAULT sysdate
   )  ;
--------------------------------------------------------
--  DDL for Table CAMPUS_ACTIVITY
--------------------------------------------------------

  CREATE TABLE "FLEX2"."CAMPUS_ACTIVITY"
   (	"CAMP_ACT_ID" NUMBER(5,0),
	"CAMP_ID" NUMBER(3,0),
	"DEPT_ID" NUMBER(4,0),
	"ACTIVITY_NAME" VARCHAR2(50),
	"START_DATE" DATE,
	"END_DATE" DATE,
	"FEEDBACK_ID" NUMBER(6,0)
   ) ;
--------------------------------------------------------
--  DDL for Table CAMPUS_BATCH
--------------------------------------------------------

  CREATE TABLE "FLEX2"."CAMPUS_BATCH"
   (	"CAMP_ID" NUMBER(3,0),
	"BATCH_NO" NUMBER(8,0),
	"STATUS" NUMBER(1,0)
   ) ;
--------------------------------------------------------
--  DDL for Table CAMPUS_DEPT
--------------------------------------------------------

  CREATE TABLE "FLEX2"."CAMPUS_DEPT"
   (	"CAMP_ID" NUMBER(3,0),
	"SCH_ID" NUMBER(4,0),
	"DEPT_ID" NUMBER(4,0)
   ) ;
--------------------------------------------------------
--  DDL for Table CAMPUS_DEPT_PROGRAM
--------------------------------------------------------

  CREATE TABLE "FLEX2"."CAMPUS_DEPT_PROGRAM"
   (	"CAMP_ID" NUMBER(3,0),
	"PROG_ID" NUMBER(4,0),
	"DEPT_ID" NUMBER(4,0)
   ) ;
--------------------------------------------------------
--  DDL for Table CAMPUS_PREFERENCE
--------------------------------------------------------

  CREATE TABLE "FLEX2"."CAMPUS_PREFERENCE"
   (	"ARN" NUMBER(10,0),
	"CAMP_ID" NUMBER(3,0),
	"RATING" NUMBER(1,0),
	"IS_SELECTED" NUMBER(1,0)
   ) ;
--------------------------------------------------------
--  DDL for Table CAMPUS_PROGRAM
--------------------------------------------------------

  CREATE TABLE "FLEX2"."CAMPUS_PROGRAM"
   (	"CAMP_ID" NUMBER(3,0),
	"PROG_ID" NUMBER(4,0),
	"STATUS" NUMBER(1,0)
   ) ;
--------------------------------------------------------
--  DDL for Table CAMP_SEMESTER
--------------------------------------------------------

  CREATE TABLE "FLEX2"."CAMP_SEMESTER"
   (	"CAMP_ID" NUMBER(3,0),
	"SEM_ID" NUMBER(8,0),
	"START_DATE" DATE,
	"END_DATE" DATE,
	"REG_START_DATE" DATE,
	"REG_END_DATE" DATE,
	"ADD_DROP_SDATE" DATE,
	"ADD_DROP_EDATE" DATE,
	"CLASS_START_DATE" DATE,
	"CLASS_END_DATE" DATE,
	"WITH_DRAW_DATE" DATE,
	"FEE_DUE_DATE" DATE,
	"FM_CLOSE_DATE" DATE,
	"STATUS" NUMBER(1,0),
	"CREATED_BY" NUMBER(8,0),
	"CREATED_DATE" DATE DEFAULT sysdate
   ) ;
--------------------------------------------------------
--  DDL for Table CITY
--------------------------------------------------------

  CREATE TABLE "FLEX2"."CITY"
   (	"CITY_ID" NUMBER(5,0),
	"TITLE" VARCHAR2(500)
   ) ;
--------------------------------------------------------
--  DDL for Table CNIC_LOG
--------------------------------------------------------

  CREATE TABLE "FLEX2"."CNIC_LOG"
   (	"ID" NUMBER(7,0),
	"ROLLNO" NUMBER(12,0),
	"OLD_RELATION" NUMBER(10,0),
	"OLD_CNIC" VARCHAR2(16),
	"IS_OLD_FOR_WHTAX" NUMBER(1,0),
	"NEW_RELATION" NUMBER(10,0),
	"NEW_CNIC" VARCHAR2(16),
	"IS_NEW_FOR_WHTAX" NUMBER(1,0),
	"ENTEREDBY" VARCHAR2(250),
	"ENTRYDATE" DATE DEFAULT SYSDATE
   ) ;
--------------------------------------------------------
--  DDL for Table COUNTRY
--------------------------------------------------------

  CREATE TABLE "FLEX2"."COUNTRY"
   (	"COUNTRY_ID" NUMBER(5,0),
	"TITLE" VARCHAR2(500)
   ) ;
--------------------------------------------------------
--  DDL for Table COURSE
--------------------------------------------------------

  CREATE TABLE "FLEX2"."COURSE"
   (	"COURSE_ID" NUMBER(4,0),
	"CODE" VARCHAR2(10),
	"TITLE" VARCHAR2(50),
	"SHORT_TITLE" VARCHAR2(30),
	"CREDIT_HRS" NUMBER(2,0),
	"DISP_CR_HR" VARCHAR2(10),
	"LEVEL_ID" NUMBER(2,0),
	"STATUS" NUMBER(2,0),
	"COURSE_TYPE_ID" NUMBER(2,0),
	"EQUIVALENCE" NUMBER(4,0),
	"DESCRIPTION" VARCHAR2(1000),
	"LAB_ID" NUMBER(4,0),
	"CREATED_BY" NUMBER(8,0),
	"CREATED_DATE" DATE DEFAULT sysdate,
	"DEPT_ID" NUMBER(4,0),
	"MIN_CREDIT_HRS" NUMBER(4,0)
   ) ;
--------------------------------------------------------
--  DDL for Table COURSE_COREQUISITE
--------------------------------------------------------

  CREATE TABLE "FLEX2"."COURSE_COREQUISITE"
   (	"COURSE_ID" NUMBER(4,0),
	"COREQUISITE_COURSE" NUMBER(4,0)
   ) ;
--------------------------------------------------------
--  DDL for Table COURSE_EVALUATION
--------------------------------------------------------

  CREATE TABLE "FLEX2"."COURSE_EVALUATION"
   (	"EVAL_ID" NUMBER(10,0),
	"OFFER_ID" NUMBER(12,0),
	"EVAL_TYPE_ID" NUMBER(3,0),
	"EVAL_NO" NUMBER(2,0),
	"TOTAL_MARKS" NUMBER(5,2),
	"WEIGHT_MARKS" NUMBER(5,2),
	"BEST_OF_MARKS" NUMBER(3,0),
	"CURRENT_SCHEME" NUMBER(2,0),
	"IS_LOCK" NUMBER(1,0),
	"CAMP_ID" NUMBER(3,0),
	"CREATED_BY" NUMBER(8,0),
	"CREATED_DATE" DATE,
	"AVERAGE" NUMBER(5,1),
	"STD_DEV" NUMBER(5,1),
	"EVAL_DATE" DATE,
	"MIN_MARKS" NUMBER(5,2),
	"MAX_MARKS" NUMBER(5,2)
   ) ;
--------------------------------------------------------
--  DDL for Table COURSE_EVALUATION_DETAIL
--------------------------------------------------------

  CREATE TABLE "FLEX2"."COURSE_EVALUATION_DETAIL"
   (	"EVAL_ID" NUMBER(8,0),
	"ROLL_NO" NUMBER(12,0),
	"OBTAINED_MARKS" NUMBER(5,2),
	"OBTAINED_WEIGHT" NUMBER(5,2),
	"CREATED_BY" NUMBER(8,0),
	"CREATED_DATE" DATE
   ) ;
--------------------------------------------------------
--  DDL for Table COURSE_EVAL_SCHEME
--------------------------------------------------------

  CREATE TABLE "FLEX2"."COURSE_EVAL_SCHEME"
   (	"CAMP_ID" NUMBER(3,0),
	"OFFER_ID" NUMBER(12,0),
	"EVAL_TYPE_ID" NUMBER(3,0),
	"BEST_OF" NUMBER(5,0),
	"IS_PROPOSED" NUMBER(1,0),
	"SET_BY_USER" NUMBER(1,0),
	"CREATED_BY" NUMBER(8,0),
	"CREATED_DATE" DATE,
	"WEIGHT" NUMBER(5,2),
	"EQUALLY_CHECK" NUMBER(1,0)
   ) ;
--------------------------------------------------------
--  DDL for Table COURSE_OFFER
--------------------------------------------------------

  CREATE TABLE "FLEX2"."COURSE_OFFER"
   (	"OFFER_ID" NUMBER(12,0),
	"CAMP_ID" NUMBER(3,0),
	"SEM_ID" NUMBER(8,0),
	"COURSE_ID" NUMBER(4,0),
	"SECTION_ID" NUMBER(4,0),
	"BUILDING_NO" VARCHAR2(3),
	"ROOM_NO" VARCHAR2(3),
	"EMP_ID" NUMBER(8,0),
	"OFFER_DEPT_ID" NUMBER(4,0),
	"SHIFT_ID" CHAR(1),
	"OFFER_STATUS" NUMBER(1,0),
	"OFFER_DATE" DATE,
	"MAX_SEATS" NUMBER(3,0),
	"CREATED_BY" NUMBER(8,0),
	"CREATED_DATE" DATE DEFAULT sysdate,
	"START_DATE" DATE DEFAULT sysdate,
	"END_DATE" DATE DEFAULT sysdate
   ) ;
--------------------------------------------------------
--  DDL for Table COURSE_OFFER_DETAIL
--------------------------------------------------------

  CREATE TABLE "FLEX2"."COURSE_OFFER_DETAIL"
   (	"OFFER_ID" NUMBER(12,0),
	"PROG_ID" NUMBER(4,0),
	"BATCH_NO" NUMBER(8,0),
	"BATCH_SECTION" NUMBER(4,0),
	"CAMP_ID" NUMBER(3,0)
   ) ;
--------------------------------------------------------
--  DDL for Table COURSE_PREREQ
--------------------------------------------------------

  CREATE TABLE "FLEX2"."COURSE_PREREQ"
   (	"COURSE_ID" NUMBER(4,0),
	"COURSE_PREREQ" NUMBER(4,0),
	"SCH_ID" NUMBER(4,0),
	"CREATED_BY" NUMBER(8,0),
	"CREATED_DATE" DATE DEFAULT sysdate
   ) ;
--------------------------------------------------------
--  DDL for Table COURSE_REGISTRATION
--------------------------------------------------------

  CREATE TABLE "FLEX2"."COURSE_REGISTRATION"
   (	"OFFER_ID" NUMBER(12,0),
	"ROLL_NO" NUMBER(12,0),
	"CAMP_ID" NUMBER(3,0),
	"SEM_ID" NUMBER(8,0),
	"COURSE_ID" NUMBER(4,0),
	"SECTION_ID" NUMBER(4,0),
	"RELATION_ID" CHAR(2),
	"REG_STATUS" NUMBER(2,0),
	"GRADE_POINT" NUMBER(3,2) DEFAULT 0,
	"GRADE" VARCHAR2(5),
	"IS_REPLACED" NUMBER(2,0),
	"REPLACED_WITH" NUMBER(4,0),
	"REG_APPROVAL_DATE" DATE,
	"CREATED_BY" NUMBER(8,0),
	"CREATED_ON" DATE,
	"LAST_MODIFIED_BY" NUMBER(8,0),
	"LAST_MODIFIED_ON" DATE,
	"FEEDBACK_STATUS" NUMBER(1,0),
	"REPEAT_COURSE_ID" VARCHAR2(10),
	"RESTRICTED_COURSE_ID" VARCHAR2(3)
   ) ;
--------------------------------------------------------
--  DDL for Table COURSE_REGISTRATION_T
--------------------------------------------------------

  CREATE TABLE "FLEX2"."COURSE_REGISTRATION_T"
   (	"OFFER_ID" NUMBER(12,0),
	"ROLL_NO" NUMBER(12,0),
	"CAMP_ID" NUMBER(3,0),
	"SEM_ID" NUMBER(8,0),
	"COURSE_ID" NUMBER(4,0),
	"SECTION_ID" NUMBER(4,0),
	"RELATION_ID" CHAR(2),
	"REG_STATUS" NUMBER(2,0),
	"GRADE_POINT" NUMBER(3,2),
	"GRADE" VARCHAR2(5),
	"IS_REPLACED" NUMBER(2,0),
	"REPLACED_WITH" NUMBER(4,0),
	"REG_APPROVAL_DATE" DATE,
	"CREATED_BY" NUMBER(8,0),
	"CREATED_ON" DATE,
	"LAST_MODIFIED_BY" NUMBER(8,0),
	"LAST_MODIFIED_ON" DATE,
	"FEEDBACK_STATUS" NUMBER(1,0),
	"REPEAT_COURSE_ID" VARCHAR2(10),
	"RESTRICTED_COURSE_ID" VARCHAR2(3)
   ) ;
--------------------------------------------------------
--  DDL for Table C_TEMP
--------------------------------------------------------

  CREATE TABLE "FLEX2"."C_TEMP"
   (	"ROLLNO" NUMBER(10,0),
	"PERCENTAGE" NUMBER(10,0),
	"TESTDATE" DATE
   ) ;
--------------------------------------------------------
--  DDL for Table DEPARTMENT
--------------------------------------------------------

  CREATE TABLE "FLEX2"."DEPARTMENT"
   (	"DEPT_ID" NUMBER(4,0),
	"TITLE" VARCHAR2(50),
	"CODE" CHAR(6),
	"ADDRESS" VARCHAR2(150),
	"CITY" VARCHAR2(20),
	"TEL_NO" VARCHAR2(13),
	"TEL_EXT" VARCHAR2(5),
	"FAX_NO" VARCHAR2(12),
	"DEPT_TYPE_ID" NUMBER(1,0)
   ) ;
--------------------------------------------------------
--  DDL for Table DEPT_PROGRAM
--------------------------------------------------------

  CREATE TABLE "FLEX2"."DEPT_PROGRAM"
   (	"DP_ID" NUMBER(4,0),
	"PROG_ID" NUMBER(4,0),
	"DEPT_ID" NUMBER(4,0)
   ) ;
--------------------------------------------------------
--  DDL for Table DISCIPLINE_PREFERENCE
--------------------------------------------------------

  CREATE TABLE "FLEX2"."DISCIPLINE_PREFERENCE"
   (	"ARN" NUMBER(10,0),
	"PROG_ID" NUMBER(4,0),
	"RATING" NUMBER(1,0),
	"ISSELECTED" NUMBER(1,0),
	"ENTRYTEST_MARKS" NUMBER(5,2),
	"ENTRYTEST_TYPE" NUMBER(1,0)
   ) ;
--------------------------------------------------------
--  DDL for Table DOCUMENT_VERIFICATION
--------------------------------------------------------

  CREATE TABLE "FLEX2"."DOCUMENT_VERIFICATION"
   (	"ID" NUMBER(5,0),
	"ARN" NUMBER(10,0),
	"PROG_ID" NUMBER(4,0),
	"VERIFIED_BY" NUMBER(8,0),
	"VERIFIED_ON" DATE,
	"IS_FACULTY" NUMBER(1,0),
	"IS_ALUMNI" NUMBER(1,0),
	"AVAIL_TRANSPORT" NUMBER(2,0),
	"ADMISSION_TYPE" VARCHAR2(100),
	"MODIFIED_BY" VARCHAR2(50),
	"MODIFIED_ON" DATE,
	"STATUS" NUMBER(2,0)
   ) ;
--------------------------------------------------------
--  DDL for Table DR$TEMP_ADDR_INDEX$I
--------------------------------------------------------

  CREATE TABLE "FLEX2"."DR$TEMP_ADDR_INDEX$I"
   (	"TOKEN_TEXT" VARCHAR2(64),
	"TOKEN_TYPE" NUMBER(3,0),
	"TOKEN_FIRST" NUMBER(10,0),
	"TOKEN_LAST" NUMBER(10,0),
	"TOKEN_COUNT" NUMBER(10,0),
	"TOKEN_INFO" BLOB
   ) ;
--------------------------------------------------------
--  DDL for Table DR$TEMP_ADDR_INDEX$K
--------------------------------------------------------

  CREATE TABLE "FLEX2"."DR$TEMP_ADDR_INDEX$K"
   (	"DOCID" NUMBER(38,0),
	"TEXTKEY" ROWID,
	 PRIMARY KEY ("TEXTKEY") ENABLE
   ) ORGANIZATION INDEX NOCOMPRESS ;
--------------------------------------------------------
--  DDL for Table DR$TEMP_ADDR_INDEX$N
--------------------------------------------------------

  CREATE TABLE "FLEX2"."DR$TEMP_ADDR_INDEX$N"
   (	"NLT_DOCID" NUMBER(38,0),
	"NLT_MARK" CHAR(1),
	 PRIMARY KEY ("NLT_DOCID") ENABLE
   ) ORGANIZATION INDEX NOCOMPRESS ;
--------------------------------------------------------
--  DDL for Table DR$TEMP_ADDR_INDEX$R
--------------------------------------------------------

  CREATE TABLE "FLEX2"."DR$TEMP_ADDR_INDEX$R"
   (	"ROW_NO" NUMBER(3,0),
	"DATA" BLOB
   ) ;
--------------------------------------------------------
--  DDL for Table D_COURSE_EVALUATION
--------------------------------------------------------

  CREATE TABLE "FLEX2"."D_COURSE_EVALUATION"
   (	"EVAL_TYPE_ID" NUMBER(3,0),
	"TITLE" VARCHAR2(50),
	"STATUS" NUMBER(1,0),
	"SHORT_NAME" VARCHAR2(10),
	"DISPLAY_ORDER" NUMBER(2,0)
   ) ;
--------------------------------------------------------
--  DDL for Table D_COURSE_LEVEL
--------------------------------------------------------

  CREATE TABLE "FLEX2"."D_COURSE_LEVEL"
   (	"LEVEL_ID" NUMBER(2,0),
	"TITLE" VARCHAR2(50),
	"STATUS" NUMBER(1,0)
   ) ;
--------------------------------------------------------
--  DDL for Table D_COURSE_RELATION
--------------------------------------------------------

  CREATE TABLE "FLEX2"."D_COURSE_RELATION"
   (	"RELATION_ID" CHAR(2),
	"TITLE" VARCHAR2(50),
	"STATUS" NUMBER(1,0)
   ) ;
--------------------------------------------------------
--  DDL for Table D_COURSE_TYPE
--------------------------------------------------------

  CREATE TABLE "FLEX2"."D_COURSE_TYPE"
   (	"TYPE_ID" NUMBER(2,0),
	"TITLE" VARCHAR2(50),
	"STATUS" NUMBER(1,0)
   ) ;
--------------------------------------------------------
--  DDL for Table D_DEGREE_TYPE
--------------------------------------------------------

  CREATE TABLE "FLEX2"."D_DEGREE_TYPE"
   (	"DT_ID" NUMBER(2,0),
	"TITLE" VARCHAR2(50),
	"STATUS" NUMBER(1,0)
   ) ;
--------------------------------------------------------
--  DDL for Table D_DEPT_EVAL_SCHEME
--------------------------------------------------------

  CREATE TABLE "FLEX2"."D_DEPT_EVAL_SCHEME"
   (	"CAMP_ID" NUMBER(3,0),
	"SCH_ID" NUMBER(4,0),
	"EVAL_TYPE_ID" NUMBER(3,0),
	"WEIGHT_FROM" NUMBER(4,0),
	"WEIGHT_TO" NUMBER(4,0),
	"WEIGHT_DEF_VALUE" NUMBER(4,0),
	"WEIGHT_MSG" VARCHAR2(50),
	"BEST_OF_FROM" NUMBER(4,0),
	"BEST_OF_TO" NUMBER(4,0),
	"BEST_OF_DEF_VALUE" NUMBER(4,0),
	"BEST_OF_MSG" VARCHAR2(50),
	"DISPLAY_ORDER" NUMBER(4,0),
	"IS_DEFAULT" NUMBER(1,0),
	"COURSE_TYPE" NUMBER(2,0)
   ) ;
--------------------------------------------------------
--  DDL for Table D_DEPT_EVAL_SCHEME_
--------------------------------------------------------

  CREATE TABLE "FLEX2"."D_DEPT_EVAL_SCHEME_"
   (	"CAMP_ID" NUMBER(3,0),
	"SCH_ID" NUMBER(4,0),
	"EVAL_TYPE_ID" NUMBER(3,0),
	"WEIGHT_FROM" NUMBER(4,0),
	"WEIGHT_TO" NUMBER(4,0),
	"WEIGHT_DEF_VALUE" NUMBER(4,0),
	"WEIGHT_MSG" VARCHAR2(50),
	"BEST_OF_FROM" NUMBER(4,0),
	"BEST_OF_TO" NUMBER(4,0),
	"BEST_OF_DEF_VALUE" NUMBER(4,0),
	"BEST_OF_MSG" VARCHAR2(50),
	"DISPLAY_ORDER" NUMBER(4,0),
	"IS_DEFAULT" NUMBER(1,0),
	"COURSE_TYPE" NUMBER(2,0)
   ) ;
--------------------------------------------------------
--  DDL for Table D_DEPT_EVAL_SCHEME_T
--------------------------------------------------------

  CREATE TABLE "FLEX2"."D_DEPT_EVAL_SCHEME_T"
   (	"CAMP_ID" NUMBER(3,0),
	"SCH_ID" NUMBER(4,0),
	"EVAL_TYPE_ID" NUMBER(3,0),
	"WEIGHT_FROM" NUMBER(4,0),
	"WEIGHT_TO" NUMBER(4,0),
	"WEIGHT_DEF_VALUE" NUMBER(4,0),
	"WEIGHT_MSG" VARCHAR2(50),
	"BEST_OF_FROM" NUMBER(4,0),
	"BEST_OF_TO" NUMBER(4,0),
	"BEST_OF_DEF_VALUE" NUMBER(4,0),
	"BEST_OF_MSG" VARCHAR2(50),
	"DISPLAY_ORDER" NUMBER(4,0),
	"IS_DEFAULT" NUMBER(1,0),
	"COURSE_TYPE" NUMBER(2,0)
   ) ;
--------------------------------------------------------
--  DDL for Table D_DEPT_EVAL_TEMP
--------------------------------------------------------

  CREATE TABLE "FLEX2"."D_DEPT_EVAL_TEMP"
   (	"EVAL_TYPE_ID" NUMBER(3,0),
	"WEIGHT_FROM" NUMBER(4,0),
	"WEIGHT_TO" NUMBER(4,0),
	"WEIGHT_DEF_VALUE" NUMBER(4,0),
	"WEIGHT_MSG" VARCHAR2(50),
	"BEST_OF_FROM" NUMBER(4,0),
	"BEST_OF_TO" NUMBER(4,0),
	"BEST_OF_DEF_VALUE" NUMBER(4,0),
	"BEST_OF_MSG" VARCHAR2(50),
	"DISPLAY_ORDER" NUMBER(4,0),
	"IS_DEFAULT" NUMBER(1,0),
	"COURSE_TYPE" NUMBER(2,0)
   ) ;
--------------------------------------------------------
--  DDL for Table D_DEPT_TYPE
--------------------------------------------------------

  CREATE TABLE "FLEX2"."D_DEPT_TYPE"
   (	"TYPE_ID" NUMBER(1,0),
	"TITLE" VARCHAR2(50),
	"STATUS" NUMBER(1,0)
   ) ;
--------------------------------------------------------
--  DDL for Table D_EMP_DESIGNATION
--------------------------------------------------------

  CREATE TABLE "FLEX2"."D_EMP_DESIGNATION"
   (	"DESIGNATION_ID" NUMBER(4,0),
	"TITLE" VARCHAR2(30),
	"SHORT_NAME" VARCHAR2(30),
	"DISPLAY_ORDER" NUMBER(3,0),
	"IS_FACULTY" NUMBER(1,0),
	"STATUS" NUMBER(1,0)
   ) ;
--------------------------------------------------------
--  DDL for Table D_EMP_STATUS
--------------------------------------------------------

  CREATE TABLE "FLEX2"."D_EMP_STATUS"
   (	"EMP_STATUS_ID" NUMBER(2,0),
	"TITLE" VARCHAR2(30),
	"DISPLAY_ORDER" NUMBER(2,0),
	"IS_DISPLAY" NUMBER(1,0)
   ) ;
--------------------------------------------------------
--  DDL for Table D_EMP_TYPE
--------------------------------------------------------

  CREATE TABLE "FLEX2"."D_EMP_TYPE"
   (	"EMP_TYPE_ID" NUMBER(1,0),
	"TITLE" VARCHAR2(30),
	"STATUS" NUMBER(1,0)
   ) ;
--------------------------------------------------------
--  DDL for Table D_FAMILY_RELATION
--------------------------------------------------------

  CREATE TABLE "FLEX2"."D_FAMILY_RELATION"
   (	"REL_TYPE_ID" NUMBER(2,0),
	"TITLE" VARCHAR2(50),
	"STATUS" NUMBER(1,0)
   ) ;
--------------------------------------------------------
--  DDL for Table D_GENDER
--------------------------------------------------------

  CREATE TABLE "FLEX2"."D_GENDER"
   (	"GENDER_ID" NUMBER(10,0),
	"GENDER" VARCHAR2(10)
   ) ;
--------------------------------------------------------
--  DDL for Table D_PHD_FUNDEDBY
--------------------------------------------------------

  CREATE TABLE "FLEX2"."D_PHD_FUNDEDBY"
   (	"FUNDED_ID" NUMBER(10,0),
	"FUNDED_TEXT" VARCHAR2(50),
	"SHORT_NAME" VARCHAR2(10)
   ) ;
--------------------------------------------------------
--  DDL for Table D_PROGRAM_LEVEL
--------------------------------------------------------

  CREATE TABLE "FLEX2"."D_PROGRAM_LEVEL"
   (	"LEVEL_ID" NUMBER(2,0),
	"TITLE" VARCHAR2(50),
	"STATUS" NUMBER(1,0)
   ) ;
--------------------------------------------------------
--  DDL for Table D_PROGRAM_SPECIALIZATION
--------------------------------------------------------

  CREATE TABLE "FLEX2"."D_PROGRAM_SPECIALIZATION"
   (	"SP_ID" VARCHAR2(100),
	"TITLE" VARCHAR2(64),
	"PROG_ID" NUMBER(4,0),
	"STATUS" NUMBER(1,0)
   ) ;
--------------------------------------------------------
--  DDL for Table D_REG_STATUS
--------------------------------------------------------

  CREATE TABLE "FLEX2"."D_REG_STATUS"
   (	"STATUS_ID" NUMBER(2,0),
	"TITLE" VARCHAR2(50)
   ) ;
--------------------------------------------------------
--  DDL for Table D_SHIFT
--------------------------------------------------------

  CREATE TABLE "FLEX2"."D_SHIFT"
   (	"SHIFT_ID" CHAR(1),
	"TITLE" VARCHAR2(30),
	"STATUS" NUMBER(1,0) DEFAULT 0
   ) ;
--------------------------------------------------------
--  DDL for Table D_STUDENT_REG_STATUS
--------------------------------------------------------

  CREATE TABLE "FLEX2"."D_STUDENT_REG_STATUS"
   (	"STATUS_ID" NUMBER(1,0),
	"TITLE" VARCHAR2(30),
	"IS_DISPLAY" NUMBER(1,0)
   ) ;
--------------------------------------------------------
--  DDL for Table D_STUDENT_STATUS
--------------------------------------------------------

  CREATE TABLE "FLEX2"."D_STUDENT_STATUS"
   (	"STATUS_ID" NUMBER(1,0),
	"TITLE" VARCHAR2(30),
	"IS_DISPLAY" NUMBER(1,0)
   ) ;
--------------------------------------------------------
--  DDL for Table D_STUDY_PLAN_ELECTIVE
--------------------------------------------------------

  CREATE TABLE "FLEX2"."D_STUDY_PLAN_ELECTIVE"
   (	"ELECTIVE_ID" NUMBER(4,0),
	"CODE" VARCHAR2(8),
	"TITLE" VARCHAR2(60),
	"SCH_DOM_ID" VARCHAR2(5),
	"CREDIT_HRS" NUMBER(4,2)
   ) ;
--------------------------------------------------------
--  DDL for Table D_TEACHER_ACTIVITY
--------------------------------------------------------

  CREATE TABLE "FLEX2"."D_TEACHER_ACTIVITY"
   (	"ACT_ID" NUMBER(4,0),
	"ACT_DESC" VARCHAR2(1000),
	"IS_DDL" NUMBER(1,0) DEFAULT 0,
	"IS_ACTIVE" NUMBER(1,0) DEFAULT 1
   ) ;
--------------------------------------------------------
--  DDL for Table D_USER_TYPE
--------------------------------------------------------

  CREATE TABLE "FLEX2"."D_USER_TYPE"
   (	"USER_TYPE_ID" NUMBER(1,0),
	"TITLE" VARCHAR2(30),
	"STATUS" NUMBER(1,0)
   ) ;
--------------------------------------------------------
--  DDL for Table EMPLOYEE
--------------------------------------------------------

  CREATE TABLE "FLEX2"."EMPLOYEE"
   (	"EMP_ID" NUMBER(8,0),
	"EMP_NAME" VARCHAR2(50),
	"DOB" DATE,
	"CNIC" VARCHAR2(15),
	"GENDER" CHAR(1),
	"EMAIL" VARCHAR2(50),
	"PEC_NUMBER" VARCHAR2(15),
	"CURR_ADDRESS" VARCHAR2(250),
	"CURR_TELNO" VARCHAR2(30),
	"CURR_MOBILE_NO" VARCHAR2(25),
	"PERM_ADDRESS" VARCHAR2(250),
	"PERM_TELNO" VARCHAR2(30),
	"PERM_MOBILE_NO" VARCHAR2(25),
	"DESIGNATION_ID" NUMBER(4,0),
	"CAMP_ID" NUMBER(3,0),
	"HRM_ID" VARCHAR2(12),
	"EMP_TYPE_ID" NUMBER(1,0),
	"IS_HOD" NUMBER(1,0),
	"IS_DIRECTOR" NUMBER(1,0),
	"STATUS" NUMBER(1,0),
	"CREATED_BY" NUMBER(4,0),
	"CREATED_DATE" DATE DEFAULT sysdate,
	"SCH_ID" NUMBER(4,0),
	"DEPT_ID" NUMBER(4,0),
	"HIRE_DATE" DATE,
	"MARITAL_STATUS" VARCHAR2(5),
	"CURR_CITY" NUMBER(5,0),
	"PERM_CITY" NUMBER(5,0),
	"PERM_COUNTRY" NUMBER(5,0),
	"CURR_COUNTRY" NUMBER(5,0),
	"IS_EXAMINER" NUMBER(10,0) DEFAULT 0
   ) ;
--------------------------------------------------------
--  DDL for Table EXCEPTION_DETAIL
--------------------------------------------------------

  CREATE TABLE "FLEX2"."EXCEPTION_DETAIL"
   (	"EXP_ID" NUMBER(10,0),
	"EXCEPTION" VARCHAR2(4000),
	"INNER_EXCEPTION" VARCHAR2(4000),
	"ROLL_NO" NUMBER(12,0),
	"PAGE_NAME" VARCHAR2(50),
	"CREATED_DATE" DATE
   ) ;
--------------------------------------------------------
--  DDL for Table EXEMPTED_COURSES
--------------------------------------------------------

  CREATE TABLE "FLEX2"."EXEMPTED_COURSES"
   (	"ROLL_NO" NUMBER(12,0),
	"COURSE_ID" NUMBER(4,0),
	"REMARKS" VARCHAR2(50),
	"CREATED_BY" NUMBER(8,0),
	"CREATED_DATE" DATE
   ) ;
--------------------------------------------------------
--  DDL for Table FB_CGPA_BAND
--------------------------------------------------------

  CREATE TABLE "FLEX2"."FB_CGPA_BAND"
   (	"CGPA_BAND_ID" NUMBER(1,0),
	"CGPA_BAND" VARCHAR2(20)
   ) ;
--------------------------------------------------------
--  DDL for Table FB_PERFORMA
--------------------------------------------------------

  CREATE TABLE "FLEX2"."FB_PERFORMA"
   (	"PID" NUMBER,
	"TEXT" VARCHAR2(100)
   ) ;
--------------------------------------------------------
--  DDL for Table FB_QUESTIONS
--------------------------------------------------------

  CREATE TABLE "FLEX2"."FB_QUESTIONS"
   (	"QUESTION_ID" NUMBER(3,0),
	"CATEGORY_ID" NUMBER(2,0),
	"TEXT" VARCHAR2(4000),
	"WEIGHT" NUMBER(1,0),
	"DISPLAY_ORDER" NUMBER(2,0),
	"ISACTIVE" NUMBER(1,0),
	"CREATED_BY" NUMBER(8,0),
	"CREATED_ON" DATE,
	"CONTROL_TYPE" NUMBER(2,0)
   ) ;
--------------------------------------------------------
--  DDL for Table FB_QUESTIONS_CATEGORY
--------------------------------------------------------

  CREATE TABLE "FLEX2"."FB_QUESTIONS_CATEGORY"
   (	"CATEGORY_ID" NUMBER(2,0),
	"TEXT" VARCHAR2(800),
	"PID" NUMBER
   ) ;
--------------------------------------------------------
--  DDL for Table FB_QUESTIONS_CHOICE
--------------------------------------------------------

  CREATE TABLE "FLEX2"."FB_QUESTIONS_CHOICE"
   (	"QUESTION_ID" NUMBER(3,0),
	"CHOICE_ID" NUMBER(3,0),
	"TEXT" VARCHAR2(800),
	"WEIGHT" NUMBER(1,0),
	"DISPLAY_ORDER" NUMBER(2,0),
	"CREATED_BY" NUMBER(8,0),
	"CREATED_ON" DATE
   ) ;
--------------------------------------------------------
--  DDL for Table FB_STUDENTREPONSE_DETAIL
--------------------------------------------------------

  CREATE TABLE "FLEX2"."FB_STUDENTREPONSE_DETAIL"
   (	"OFFER_ID" NUMBER(12,0),
	"QUESTION_ID" NUMBER(3,0),
	"CHOICE_ID" NUMBER(3,0),
	"SERIAL_NO" NUMBER(10,0),
	"FEEDBACK_NO" NUMBER(6,0),
	"CGPA_BAND_ID" NUMBER(1,0),
	"ROLL_NO" NUMBER(12,0),
	"SUBMITTED_ON" DATE
   ) ;
--------------------------------------------------------
--  DDL for Table FB_STUDENTREPONSE_DETAIL_TEMP
--------------------------------------------------------

  CREATE TABLE "FLEX2"."FB_STUDENTREPONSE_DETAIL_TEMP"
   (	"OFFER_ID" NUMBER(12,0),
	"QUESTION_ID" NUMBER(3,0),
	"CHOICE_ID" NUMBER(3,0),
	"SERIAL_NO" NUMBER(10,0),
	"FEEDBACK_NO" NUMBER(6,0),
	"CGPA_BAND_ID" NUMBER(1,0),
	"ROLL_NO" NUMBER(12,0),
	"SUBMITTED_ON" DATE
   ) ;
--------------------------------------------------------
--  DDL for Table FB_STUDENTREPONSE_TEXT
--------------------------------------------------------

  CREATE TABLE "FLEX2"."FB_STUDENTREPONSE_TEXT"
   (	"OFFER_ID" NUMBER(12,0),
	"QUESTION_ID" NUMBER(3,0),
	"TEXT" VARCHAR2(4000),
	"SERIAL_NO" NUMBER(10,0),
	"FEEDBACK_NO" NUMBER(6,0),
	"CGPA_BAND_ID" NUMBER(1,0),
	"ROLL_NO" NUMBER(12,0)
   ) ;
--------------------------------------------------------
--  DDL for Table FB_STUDENTREPONSE_TEXT_1031
--------------------------------------------------------

  CREATE TABLE "FLEX2"."FB_STUDENTREPONSE_TEXT_1031"
   (	"OFFER_ID" NUMBER(12,0),
	"QUESTION_ID" NUMBER(3,0),
	"TEXT" VARCHAR2(4000),
	"SERIAL_NO" NUMBER(10,0),
	"FEEDBACK_NO" NUMBER(6,0),
	"CGPA_BAND_ID" NUMBER(1,0),
	"ROLL_NO" NUMBER(12,0)
   ) ;
--------------------------------------------------------
--  DDL for Table FB_STUDENTRESPONSE_TEXT_TEMP
--------------------------------------------------------

  CREATE TABLE "FLEX2"."FB_STUDENTRESPONSE_TEXT_TEMP"
   (	"OFFER_ID" NUMBER(12,0),
	"QUESTION_ID" NUMBER(3,0),
	"TEXT" VARCHAR2(4000),
	"SERIAL_NO" NUMBER(10,0),
	"FEEDBACK_NO" NUMBER(6,0),
	"CGPA_BAND_ID" NUMBER(1,0),
	"ROLL_NO" NUMBER(12,0)
   ) ;
--------------------------------------------------------
--  DDL for Table FB_TEACHER_RESPONSE_TEXT
--------------------------------------------------------

  CREATE TABLE "FLEX2"."FB_TEACHER_RESPONSE_TEXT"
   (	"OFFER_ID" NUMBER(12,0),
	"QUESTION_ID" NUMBER(3,0),
	"TEXT" VARCHAR2(4000),
	"EMP_ID" NUMBER(8,0),
	"SUBMITTED_ON" DATE
   ) ;
--------------------------------------------------------
--  DDL for Table FMBANKSCROLLDETAIL
--------------------------------------------------------

  CREATE TABLE "FLEX2"."FMBANKSCROLLDETAIL"
   (	"ID" NUMBER(10,0),
	"SCROLLID" VARCHAR2(250),
	"CAMPUSID" NUMBER(3,0),
	"ROLLNO" NUMBER(12,0),
	"ARN" NUMBER(10,0),
	"SEMID" NUMBER(8,0),
	"CHALLANNO" NUMBER(18,0),
	"BSCHALLANNO" VARCHAR2(100),
	"AMOUNT" NUMBER(18,0),
	"PAYMENTDATE" DATE,
	"BRANCHCODE" VARCHAR2(100),
	"ENTEREDBY" VARCHAR2(250),
	"ENTRYDATE" DATE,
	"VERIFIEDBY" VARCHAR2(250),
	"VERIFIEDON" DATE,
	"POSTEDBY" VARCHAR2(250),
	"POSTEDON" DATE,
	"STATUS" NUMBER(2,0)
   ) ;
--------------------------------------------------------
--  DDL for Table FMCHALLAN
--------------------------------------------------------

  CREATE TABLE "FLEX2"."FMCHALLAN"
   (	"CHALLANNO" NUMBER(11,0),
	"CAMPUSID" NUMBER(3,0),
	"ROLLNO" NUMBER(12,0),
	"ARN" NUMBER(10,0),
	"SEMID" NUMBER(8,0),
	"DUEDATE" DATE,
	"PRINTSERIALNO" NUMBER(10,0),
	"REMARKS" VARCHAR2(4000),
	"ENTEREDBY" VARCHAR2(50),
	"ENTRYDATE" DATE,
	"MODIFIEDDATE" DATE,
	"LASTMODIFIEDBY" VARCHAR2(50 CHAR),
	"STATUS" NUMBER(2,0)
   ) ;
--------------------------------------------------------
--  DDL for Table FMCHALLANDETAIL
--------------------------------------------------------

  CREATE TABLE "FLEX2"."FMCHALLANDETAIL"
   (	"CHALLANNO" NUMBER(11,0),
	"SUBHEADID" NUMBER(10,0),
	"AMOUNT" NUMBER(18,2),
	"REMARKS" VARCHAR2(4000),
	"ENTEREDBY" VARCHAR2(50),
	"ENTRYDATE" DATE,
	"MODIFIEDDATE" DATE,
	"LASTMODIFIEDBY" VARCHAR2(50),
	"STATUS" NUMBER(2,0)
   ) ;
--------------------------------------------------------
--  DDL for Table FMDEBUG
--------------------------------------------------------

  CREATE TABLE "FLEX2"."FMDEBUG"
   (	"REMARKS" VARCHAR2(500),
	"F1" VARCHAR2(500),
	"F2" VARCHAR2(500),
	"F3" VARCHAR2(500),
	"ENTRYDATE" DATE DEFAULT Sysdate
   ) ;
--------------------------------------------------------
--  DDL for Table FMDEFAULTEREXCEPTION
--------------------------------------------------------

  CREATE TABLE "FLEX2"."FMDEFAULTEREXCEPTION"
   (	"CAMPUSID" NUMBER(3,0),
	"ROLLNO" NUMBER(12,0),
	"SEMID" NUMBER(8,0),
	"REMARKS" VARCHAR2(250 CHAR),
	"ENTEREDBY" VARCHAR2(50 CHAR),
	"ENTRYDATE" DATE
   ) ;
--------------------------------------------------------
--  DDL for Table FMEXECUTIVEREPORTDATA
--------------------------------------------------------

  CREATE TABLE "FLEX2"."FMEXECUTIVEREPORTDATA"
   (	"CAMPUSID" NUMBER(3,0),
	"ROLLNO" NUMBER(12,0),
	"ROLL" VARCHAR2(8),
	"SEMID" NUMBER(8,0),
	"NAME" VARCHAR2(100),
	"PROGRAMID" VARCHAR2(30),
	"BATCHNO" NUMBER(8,0),
	"STATUS" VARCHAR2(50),
	"COURSES" NUMBER(10,0),
	"DEPTID" NUMBER(4,0),
	"DEPTNAME" VARCHAR2(100),
	"SPONSHEAD" VARCHAR2(20),
	"SPONSOR" VARCHAR2(500),
	"ARREAR" NUMBER(38,2),
	"DUE" NUMBER(38,2),
	"NET" NUMBER(38,2),
	"PYBLEADJMNT" NUMBER(38,2),
	"TOTALPAYMENT" NUMBER(38,2),
	"ARREARPAYMENT" NUMBER(38,2),
	"CURRPAYMENT" NUMBER(38,2),
	"SPONSAMOUNT" NUMBER(10,0),
	"BALANCE" NUMBER(38,2),
	"ARRBAL" NUMBER(38,2),
	"CURRBAL" NUMBER(38,2),
	"INSTAMOUNT" NUMBER(38,0),
	"DEFAMOUNT" NUMBER(38,0),
	"LASTUPDATED" DATE,
	"SPONSID" NUMBER(10,0)
   ) ;
--------------------------------------------------------
--  DDL for Table FMFEEDATES
--------------------------------------------------------

  CREATE TABLE "FLEX2"."FMFEEDATES"
   (	"CAMPUSID" NUMBER(3,0),
	"SEMID" NUMBER(5,0),
	"BATCHNO" NUMBER(8,0),
	"PROGRAMID" NUMBER(4,0),
	"SECTIONID" NUMBER(4,0),
	"FEEDUEDDATE" DATE,
	"CLASSESSTARTDATE" DATE,
	"WITHDRAWDATE" DATE,
	"CREATEDBY" VARCHAR2(500),
	"CREATEDDATE" DATE DEFAULT SYSDATE,
	"MODIFIEDBY" VARCHAR2(500),
	"MODIFIEDDATE" DATE DEFAULT SYSDATE,
	"STATUS" NUMBER(3,0) DEFAULT 1
   ) ;
--------------------------------------------------------
--  DDL for Table FMFEERATES
--------------------------------------------------------

  CREATE TABLE "FLEX2"."FMFEERATES"
   (	"FEERATEID" NUMBER(15,0),
	"PROGRAMLEVEL" NUMBER(2,0),
	"PROGRAMID" NUMBER(4,0),
	"BATCHNO" NUMBER(8,0),
	"CAMPUSID" NUMBER(3,0),
	"SEMID" NUMBER(8,0),
	"SUBHEADID" NUMBER(10,0),
	"AMOUNT" NUMBER(10,2),
	"DOCREF" VARCHAR2(250),
	"REMARKS" VARCHAR2(500),
	"ENTEREDBY" VARCHAR2(50),
	"ENTRYDATE" DATE,
	"MODIFIEDBY" VARCHAR2(50),
	"MODIFIEDDATE" DATE,
	"STATUS" NUMBER(2,0)
   ) ;
--------------------------------------------------------
--  DDL for Table FMFEETYPE
--------------------------------------------------------

  CREATE TABLE "FLEX2"."FMFEETYPE"
   (	"FEETYPEID" NUMBER(10,0),
	"TITLE" VARCHAR2(50),
	"ENTEREDBY" VARCHAR2(50),
	"ENTRYDATE" DATE,
	"MODIFIEDBY" VARCHAR2(50),
	"MODIFIEDDATE" DATE,
	"STATUS" NUMBER(2,0)
   ) ;
--------------------------------------------------------
--  DDL for Table FMHEAD
--------------------------------------------------------

  CREATE TABLE "FLEX2"."FMHEAD"
   (	"HEADID" NUMBER(10,0),
	"TITLE" VARCHAR2(100),
	"ORDERNO" NUMBER(10,0),
	"ENTEREDBY" VARCHAR2(50),
	"ENTRYDATE" DATE,
	"MODIFIEDBY" VARCHAR2(50),
	"MODIFIEDDATE" DATE,
	"STATUS" NUMBER(2,0)
   ) ;
--------------------------------------------------------
--  DDL for Table FMINSTALLMENTS
--------------------------------------------------------

  CREATE TABLE "FLEX2"."FMINSTALLMENTS"
   (	"INSTALLMENTID" NUMBER(14,0),
	"CAMPUSID" NUMBER(3,0),
	"ROLLNO" NUMBER(12,0),
	"ARN" NUMBER(10,0),
	"SEMID" NUMBER(8,0),
	"AMOUNT" NUMBER(8,0),
	"DUEDATE" DATE,
	"CHALLANNO" NUMBER(11,0),
	"DOCREF" VARCHAR2(250),
	"REMARKS" VARCHAR2(4000),
	"ENTEREDBY" VARCHAR2(50),
	"ENTRYDATE" DATE,
	"MODIFIEDBY" VARCHAR2(50),
	"MODIFIEDDATE" DATE,
	"STATUS" NUMBER(2,0)
   ) ;
--------------------------------------------------------
--  DDL for Table FMLEDGER_20190114
--------------------------------------------------------

  CREATE TABLE "FLEX2"."FMLEDGER_20190114"
   (	"LEDGERID_OLD" NUMBER(10,0),
	"LEDGERID" NUMBER(14,0),
	"CAMPUSID" NUMBER(3,0),
	"ROLLNO" NUMBER(12,0),
	"ARN" NUMBER(10,0),
	"SEMID" NUMBER(8,0),
	"SUBHEADID" NUMBER(10,0),
	"FEETYPEID" NUMBER(10,0),
	"SPONSORSHIPID" NUMBER(10,0),
	"RECIAVABLE" NUMBER(18,2),
	"PAYMENT" NUMBER(18,2),
	"REMARKS" VARCHAR2(4000),
	"ENTEREDBY" VARCHAR2(50),
	"ENTRYDATE" DATE,
	"TRANSACTIONDATE" DATE,
	"LASTMODIFIEDBY" VARCHAR2(50),
	"STATUS" NUMBER(2,0)
   ) ;
--------------------------------------------------------
--  DDL for Table FMLEDGER_20190118
--------------------------------------------------------

  CREATE TABLE "FLEX2"."FMLEDGER_20190118"
   (	"LEDGERID_OLD" NUMBER(10,0),
	"LEDGERID" NUMBER(14,0),
	"CAMPUSID" NUMBER(3,0),
	"ROLLNO" NUMBER(12,0),
	"ARN" NUMBER(10,0),
	"SEMID" NUMBER(8,0),
	"SUBHEADID" NUMBER(10,0),
	"FEETYPEID" NUMBER(10,0),
	"SPONSORSHIPID" NUMBER(10,0),
	"RECIAVABLE" NUMBER(18,2),
	"PAYMENT" NUMBER(18,2),
	"REMARKS" VARCHAR2(4000),
	"ENTEREDBY" VARCHAR2(50),
	"ENTRYDATE" DATE,
	"TRANSACTIONDATE" DATE,
	"LASTMODIFIEDBY" VARCHAR2(50),
	"STATUS" NUMBER(2,0)
   ) ;
--------------------------------------------------------
--  DDL for Table FMLEDGER_20190129
--------------------------------------------------------

  CREATE TABLE "FLEX2"."FMLEDGER_20190129"
   (	"LEDGERID_OLD" NUMBER(10,0),
	"LEDGERID" NUMBER(14,0),
	"CAMPUSID" NUMBER(3,0),
	"ROLLNO" NUMBER(12,0),
	"ARN" NUMBER(10,0),
	"SEMID" NUMBER(8,0),
	"SUBHEADID" NUMBER(10,0),
	"FEETYPEID" NUMBER(10,0),
	"SPONSORSHIPID" NUMBER(10,0),
	"RECIAVABLE" NUMBER(18,2),
	"PAYMENT" NUMBER(18,2),
	"REMARKS" VARCHAR2(4000),
	"ENTEREDBY" VARCHAR2(50),
	"ENTRYDATE" DATE,
	"TRANSACTIONDATE" DATE,
	"LASTMODIFIEDBY" VARCHAR2(50),
	"STATUS" NUMBER(2,0)
   ) ;
--------------------------------------------------------
--  DDL for Table FMLEDGER_MAKINGPAYABLES
--------------------------------------------------------

  CREATE TABLE "FLEX2"."FMLEDGER_MAKINGPAYABLES"
   (	"LEDGERID_OLD" NUMBER(10,0),
	"LEDGERID" NUMBER(14,0),
	"CAMPUSID" NUMBER(3,0),
	"ROLLNO" NUMBER(12,0),
	"ARN" NUMBER(10,0),
	"SEMID" NUMBER(8,0),
	"SUBHEADID" NUMBER(10,0),
	"FEETYPEID" NUMBER(10,0),
	"SPONSORSHIPID" NUMBER(10,0),
	"RECIAVABLE" NUMBER(18,2),
	"PAYMENT" NUMBER(18,2),
	"REMARKS" VARCHAR2(4000),
	"ENTEREDBY" VARCHAR2(50),
	"ENTRYDATE" DATE,
	"TRANSACTIONDATE" DATE,
	"LASTMODIFIEDBY" VARCHAR2(50),
	"STATUS" NUMBER(2,0)
   ) ;
--------------------------------------------------------
--  DDL for Table FMLEDGER_REFUND
--------------------------------------------------------

  CREATE TABLE "FLEX2"."FMLEDGER_REFUND"
   (	"LEDGERID_OLD" NUMBER(10,0),
	"LEDGERID" NUMBER(14,0),
	"CAMPUSID" NUMBER(3,0),
	"ROLLNO" NUMBER(12,0),
	"ARN" NUMBER(10,0),
	"SEMID" NUMBER(8,0),
	"SUBHEADID" NUMBER(10,0),
	"FEETYPEID" NUMBER(10,0),
	"SPONSORSHIPID" NUMBER(10,0),
	"RECIAVABLE" NUMBER(18,2),
	"PAYMENT" NUMBER(18,2),
	"REMARKS" VARCHAR2(4000),
	"ENTEREDBY" VARCHAR2(50),
	"ENTRYDATE" DATE,
	"TRANSACTIONDATE" DATE,
	"LASTMODIFIEDBY" VARCHAR2(50),
	"STATUS" NUMBER(2,0)
   ) ;
--------------------------------------------------------
--  DDL for Table FMLEDGER_REGLOG
--------------------------------------------------------

  CREATE TABLE "FLEX2"."FMLEDGER_REGLOG"
   (	"CAMPUSID" NUMBER(3,0),
	"LEDGERID_OLD" NUMBER(10,0),
	"REGLOGID_OLD" NUMBER(10,0),
	"LEDGERID" NUMBER(14,0),
	"REGLOGID" NUMBER(14,0),
	"ENTEREDBY" VARCHAR2(50),
	"ENTRYDATE" DATE,
	"MODIFIEDDATE" DATE,
	"LASTMODIFIEDBY" VARCHAR2(50),
	"STATUS" NUMBER(2,0)
   ) ;
--------------------------------------------------------
--  DDL for Table FMLEDGER_REGLOG_20190118
--------------------------------------------------------

  CREATE TABLE "FLEX2"."FMLEDGER_REGLOG_20190118"
   (	"CAMPUSID" NUMBER(3,0),
	"LEDGERID_OLD" NUMBER(10,0),
	"REGLOGID_OLD" NUMBER(10,0),
	"LEDGERID" NUMBER(14,0),
	"REGLOGID" NUMBER(14,0),
	"ENTEREDBY" VARCHAR2(50),
	"ENTRYDATE" DATE,
	"MODIFIEDDATE" DATE,
	"LASTMODIFIEDBY" VARCHAR2(50),
	"STATUS" NUMBER(2,0)
   ) ;
--------------------------------------------------------
--  DDL for Table FMLEDGER_SCROLLDETAIL
--------------------------------------------------------

  CREATE TABLE "FLEX2"."FMLEDGER_SCROLLDETAIL"
   (	"CAMPUSID" NUMBER(3,0),
	"LEDGERID_OLD" NUMBER(10,0),
	"SCROLLDETAILID_OLD" NUMBER(10,0),
	"LEDGERID" NUMBER(14,0),
	"SCROLLDETAILID" NUMBER(14,0),
	"ENTEREDBY" VARCHAR2(50),
	"ENTRYDATE" DATE,
	"MODIFIEDDATE" DATE,
	"LASTMODIFIEDBY" VARCHAR2(50),
	"STATUS" NUMBER(2,0)
   ) ;
--------------------------------------------------------
--  DDL for Table FMLEDGER_SCROLL_20190114
--------------------------------------------------------

  CREATE TABLE "FLEX2"."FMLEDGER_SCROLL_20190114"
   (	"CAMPUSID" NUMBER(3,0),
	"LEDGERID_OLD" NUMBER(10,0),
	"SCROLLDETAILID_OLD" NUMBER(10,0),
	"LEDGERID" NUMBER(14,0),
	"SCROLLDETAILID" NUMBER(14,0),
	"ENTEREDBY" VARCHAR2(50),
	"ENTRYDATE" DATE,
	"MODIFIEDDATE" DATE,
	"LASTMODIFIEDBY" VARCHAR2(50),
	"STATUS" NUMBER(2,0)
   ) ;
--------------------------------------------------------
--  DDL for Table FMLEDGER_SCROLL_20190129
--------------------------------------------------------

  CREATE TABLE "FLEX2"."FMLEDGER_SCROLL_20190129"
   (	"CAMPUSID" NUMBER(3,0),
	"LEDGERID_OLD" NUMBER(10,0),
	"SCROLLDETAILID_OLD" NUMBER(10,0),
	"LEDGERID" NUMBER(14,0),
	"SCROLLDETAILID" NUMBER(14,0),
	"ENTEREDBY" VARCHAR2(50),
	"ENTRYDATE" DATE,
	"MODIFIEDDATE" DATE,
	"LASTMODIFIEDBY" VARCHAR2(50),
	"STATUS" NUMBER(2,0)
   ) ;
--------------------------------------------------------
--  DDL for Table FMLEDGER_SPONS_TEMP
--------------------------------------------------------

  CREATE TABLE "FLEX2"."FMLEDGER_SPONS_TEMP"
   (	"CAMPUSID" NUMBER(3,0),
	"STUDENTSOPNSID_OLD" NUMBER(10,0),
	"STUDENTSPONSID" NUMBER(14,0),
	"LEDGERID_OLD" NUMBER(10,0),
	"LEDGERID" NUMBER(14,0),
	"ENTEREDBY" VARCHAR2(50),
	"ENTRYDATE" DATE,
	"STATUS" NUMBER(2,0)
   ) ;
--------------------------------------------------------
--  DDL for Table FMLEDGER_STUDENTSPONS
--------------------------------------------------------

  CREATE TABLE "FLEX2"."FMLEDGER_STUDENTSPONS"
   (	"CAMPUSID" NUMBER(3,0),
	"STUDENTSPONSID_OLD" NUMBER(10,0),
	"STUDENTSPONSID" NUMBER(14,0),
	"LEDGERID_OLD" NUMBER(10,0),
	"LEDGERID" NUMBER(14,0),
	"ENTEREDBY" VARCHAR2(50),
	"ENTRYDATE" DATE,
	"STATUS" NUMBER(2,0)
   ) ;
--------------------------------------------------------
--  DDL for Table FMPAYMENTMODE
--------------------------------------------------------

  CREATE TABLE "FLEX2"."FMPAYMENTMODE"
   (	"PAYMENTMODEID" NUMBER(10,0),
	"PAYMENTTYPE" NUMBER(10,0),
	"TITLE" VARCHAR2(100),
	"ENTEREDBY" VARCHAR2(50),
	"ENTRYDATE" DATE,
	"STATUS" NUMBER(2,0)
   ) ;
--------------------------------------------------------
--  DDL for Table FMPAYMENTTYPE
--------------------------------------------------------

  CREATE TABLE "FLEX2"."FMPAYMENTTYPE"
   (	"PAYMENTTYPE" NUMBER(10,0),
	"TITLE" VARCHAR2(50),
	"ENTEREDBY" VARCHAR2(50),
	"ENTRYDATE" DATE,
	"MODIFIEDDATE" DATE,
	"LASTMODIFIEDBY" VARCHAR2(50),
	"STATUS" NUMBER(2,0)
   ) ;
--------------------------------------------------------
--  DDL for Table FMRECEIVEDSPONSORAMOUNT
--------------------------------------------------------

  CREATE TABLE "FLEX2"."FMRECEIVEDSPONSORAMOUNT"
   (	"ID" NUMBER(10,0),
	"SCROLLDETAILID" NUMBER(14,0),
	"CAMPUSID" NUMBER(3,0),
	"SPONSORSHIPID" NUMBER(10,0),
	"ROLLNO" NUMBER(12,0),
	"ARN" NUMBER(10,0),
	"SEMID" NUMBER(8,0),
	"AMOUNT" NUMBER(18,0),
	"REMARKS" VARCHAR2(4000),
	"ENTEREDBY" VARCHAR2(50),
	"ENTRYDATE" DATE,
	"MODIFIEDBY" VARCHAR2(50),
	"MODIFIEDDATE" DATE,
	"STATUS" NUMBER(2,0)
   ) ;
--------------------------------------------------------
--  DDL for Table FMREFUND
--------------------------------------------------------

  CREATE TABLE "FLEX2"."FMREFUND"
   (	"REFUNDID" NUMBER(14,0),
	"REFUNDID_OLD" NUMBER(10,0),
	"CAMPUSID" NUMBER(3,0),
	"ROLLNO" NUMBER(12,0),
	"REFUNDTYPE" NUMBER(1,0),
	"REFUNDPERCENT" NUMBER(5,2),
	"REFUNDAMOUNT" NUMBER(18,0),
	"APPLICATIONDATE" DATE,
	"APPROVALDATE" DATE,
	"SEMID" NUMBER(8,0),
	"INSTRUMENTNO" VARCHAR2(100),
	"REMARKS" VARCHAR2(4000),
	"ENTEREDBY" VARCHAR2(50),
	"ENTRYDATE" DATE,
	"MODIFIEDBY" VARCHAR2(50),
	"MODIFIEDDATE" DATE,
	"STATUS" NUMBER(2,0)
   ) ;
--------------------------------------------------------
--  DDL for Table FMREPOSTING_TEMP
--------------------------------------------------------

  CREATE TABLE "FLEX2"."FMREPOSTING_TEMP"
   (	"ROLLNO" NUMBER(14,0),
	"SCROLLDETAILID" NUMBER(14,0),
	"ENTRYDATE" DATE DEFAULT sysdate
   ) ;
--------------------------------------------------------
--  DDL for Table FMREVERSALENTRY_TEMP
--------------------------------------------------------

  CREATE TABLE "FLEX2"."FMREVERSALENTRY_TEMP"
   (	"CAMPUSID" NUMBER(3,0),
	"LEDGERID_OLD" NUMBER(10,0),
	"SCROLLDETAILID_OLD" NUMBER(10,0),
	"LEDGERID" NUMBER(14,0),
	"SCROLLDETAILID" NUMBER(14,0),
	"ENTEREDBY" VARCHAR2(50),
	"ENTRYDATE" DATE,
	"MODIFIEDDATE" DATE,
	"LASTMODIFIEDBY" VARCHAR2(50),
	"STATUS" NUMBER(2,0)
   ) ;
--------------------------------------------------------
--  DDL for Table FMSCROLLDETAIL
--------------------------------------------------------

  CREATE TABLE "FLEX2"."FMSCROLLDETAIL"
   (	"SCROLLDETAILID_OLD" NUMBER(10,0),
	"SCROLLDETAILID" NUMBER(14,0),
	"CAMPUSID" NUMBER(3,0),
	"ROLLNO" NUMBER(12,0),
	"ARN" NUMBER(10,0),
	"SEMID" NUMBER(8,0),
	"CHALLANNO" NUMBER(11,0),
	"PRINTSERIALNO" NUMBER(10,0),
	"PAYMENTMODEID" NUMBER(10,0),
	"INSTRUMENTNO" VARCHAR2(50),
	"AMOUNT" NUMBER(18,0),
	"PAYMENTDATE" DATE,
	"REMARKS" VARCHAR2(4000),
	"SCROLLID" VARCHAR2(1000),
	"BRANCHCODE" VARCHAR2(50),
	"ENTEREDBY" VARCHAR2(50),
	"ENTRYDATE" DATE,
	"MODIFIEDBY" VARCHAR2(50),
	"MODIFIEDDATE" DATE,
	"STATUS" NUMBER(2,0),
	"SPONSORSHIPID" NUMBER(10,0) DEFAULT 0
   ) ;
--------------------------------------------------------
--  DDL for Table FMSCROLLDETAIL_20190114
--------------------------------------------------------

  CREATE TABLE "FLEX2"."FMSCROLLDETAIL_20190114"
   (	"SCROLLDETAILID_OLD" NUMBER(10,0),
	"SCROLLDETAILID" NUMBER(14,0),
	"CAMPUSID" NUMBER(3,0),
	"ROLLNO" NUMBER(12,0),
	"ARN" NUMBER(10,0),
	"SEMID" NUMBER(8,0),
	"CHALLANNO" NUMBER(11,0),
	"PRINTSERIALNO" NUMBER(10,0),
	"PAYMENTMODEID" NUMBER(10,0),
	"INSTRUMENTNO" VARCHAR2(50),
	"AMOUNT" NUMBER(18,0),
	"PAYMENTDATE" DATE,
	"REMARKS" VARCHAR2(4000),
	"SCROLLID" VARCHAR2(1000),
	"BRANCHCODE" VARCHAR2(50),
	"ENTEREDBY" VARCHAR2(50),
	"ENTRYDATE" DATE,
	"MODIFIEDBY" VARCHAR2(50),
	"MODIFIEDDATE" DATE,
	"STATUS" NUMBER(2,0),
	"SPONSORSHIPID" NUMBER(10,0)
   ) ;
--------------------------------------------------------
--  DDL for Table FMSCROLLDETAIL_20190129
--------------------------------------------------------

  CREATE TABLE "FLEX2"."FMSCROLLDETAIL_20190129"
   (	"SCROLLDETAILID_OLD" NUMBER(10,0),
	"SCROLLDETAILID" NUMBER(14,0),
	"CAMPUSID" NUMBER(3,0),
	"ROLLNO" NUMBER(12,0),
	"ARN" NUMBER(10,0),
	"SEMID" NUMBER(8,0),
	"CHALLANNO" NUMBER(11,0),
	"PRINTSERIALNO" NUMBER(10,0),
	"PAYMENTMODEID" NUMBER(10,0),
	"INSTRUMENTNO" VARCHAR2(50),
	"AMOUNT" NUMBER(18,0),
	"PAYMENTDATE" DATE,
	"REMARKS" VARCHAR2(4000),
	"SCROLLID" VARCHAR2(1000),
	"BRANCHCODE" VARCHAR2(50),
	"ENTEREDBY" VARCHAR2(50),
	"ENTRYDATE" DATE,
	"MODIFIEDBY" VARCHAR2(50),
	"MODIFIEDDATE" DATE,
	"STATUS" NUMBER(2,0),
	"SPONSORSHIPID" NUMBER(10,0)
   ) ;
--------------------------------------------------------
--  DDL for Table FMSCROLLDETAIL_WS
--------------------------------------------------------

  CREATE TABLE "FLEX2"."FMSCROLLDETAIL_WS"
   (	"SCROLLDETAILID_OLD" NUMBER(10,0),
	"SCROLLDETAILID" NUMBER(14,0),
	"CAMPUSID" NUMBER(3,0),
	"ROLLNO" NUMBER(12,0),
	"ARN" NUMBER(10,0),
	"SEMID" NUMBER(8,0),
	"CHALLANNO" NUMBER(11,0),
	"PRINTSERIALNO" NUMBER(10,0),
	"PAYMENTMODEID" NUMBER(10,0),
	"INSTRUMENTNO" VARCHAR2(50),
	"AMOUNT" NUMBER(18,0),
	"PAYMENTDATE" DATE,
	"REMARKS" VARCHAR2(4000),
	"SCROLLID" VARCHAR2(1000),
	"BRANCHCODE" VARCHAR2(50),
	"ENTEREDBY" VARCHAR2(50),
	"ENTRYDATE" DATE,
	"MODIFIEDBY" VARCHAR2(50),
	"MODIFIEDDATE" DATE,
	"STATUS" NUMBER(2,0),
	"SPONSORSHIPID" NUMBER(10,0) DEFAULT 0
   ) ;
--------------------------------------------------------
--  DDL for Table FMSCROLLSUMMARY
--------------------------------------------------------

  CREATE TABLE "FLEX2"."FMSCROLLSUMMARY"
   (	"SCROLLID" VARCHAR2(100),
	"CAMPUSID" NUMBER(3,0),
	"BANKCODE" VARCHAR2(50),
	"SCROLLDATE" DATE,
	"SUMOFAMOUNT" NUMBER(18,0),
	"PREPAREDBY" VARCHAR2(50),
	"ENTEREDBY" VARCHAR2(50),
	"ENTRYDATE" DATE,
	"MODIFIEDBY" VARCHAR2(50),
	"MODIFIEDDATE" DATE,
	"STATUS" NUMBER(2,0),
	"FILENAME" VARCHAR2(150),
	"TRANSACTIONCOUNT" NUMBER(10,0)
   ) ;
--------------------------------------------------------
--  DDL for Table FMSEMFEE_20190114
--------------------------------------------------------

  CREATE TABLE "FLEX2"."FMSEMFEE_20190114"
   (	"PARENTCAMPUSID" NUMBER(2,0),
	"CURRENTCAMPUSID" NUMBER(2,0),
	"ROLLNO" NUMBER(12,0),
	"SEMID" NUMBER(8,0),
	"ROLL" VARCHAR2(4000),
	"NAME" VARCHAR2(50),
	"PROGRAMID" CHAR(10),
	"BATCHNO" NUMBER(8,0),
	"TYPE" VARCHAR2(20),
	"SPONSOR" VARCHAR2(500),
	"SPONSHEAD" VARCHAR2(20),
	"SPONSTYPE" VARCHAR2(20),
	"STATUS" VARCHAR2(30),
	"ARREAR" NUMBER,
	"DUE" NUMBER,
	"NET" NUMBER,
	"PAYMENT" NUMBER,
	"ARREARPAYMENT" NUMBER,
	"HOPAYMENT" NUMBER,
	"SPONSAMOUNT" NUMBER,
	"RUNSPONSAMOUNT" NUMBER,
	"BALANCE" NUMBER,
	"SPONSBALANCE" NUMBER,
	"COURSES" NUMBER,
	"UPDATEDON" DATE,
	"SPONSORSHIPID" NUMBER(10,0),
	"SEMTITLE" VARCHAR2(20)
   ) ;
--------------------------------------------------------
--  DDL for Table FMSEMFEE_20190129
--------------------------------------------------------

  CREATE TABLE "FLEX2"."FMSEMFEE_20190129"
   (	"PARENTCAMPUSID" NUMBER(2,0),
	"CURRENTCAMPUSID" NUMBER(2,0),
	"ROLLNO" NUMBER(12,0),
	"SEMID" NUMBER(8,0),
	"ROLL" VARCHAR2(4000),
	"NAME" VARCHAR2(50),
	"PROGRAMID" CHAR(10),
	"BATCHNO" NUMBER(8,0),
	"TYPE" VARCHAR2(20),
	"SPONSOR" VARCHAR2(500),
	"SPONSHEAD" VARCHAR2(20),
	"SPONSTYPE" VARCHAR2(20),
	"STATUS" VARCHAR2(30),
	"ARREAR" NUMBER,
	"DUE" NUMBER,
	"NET" NUMBER,
	"PAYMENT" NUMBER,
	"ARREARPAYMENT" NUMBER,
	"HOPAYMENT" NUMBER,
	"SPONSAMOUNT" NUMBER,
	"RUNSPONSAMOUNT" NUMBER,
	"BALANCE" NUMBER,
	"SPONSBALANCE" NUMBER,
	"COURSES" NUMBER,
	"UPDATEDON" DATE,
	"SPONSORSHIPID" NUMBER(10,0),
	"SEMTITLE" VARCHAR2(20)
   ) ;
--------------------------------------------------------
--  DDL for Table FMSPONSOREDSTUDENT
--------------------------------------------------------

  CREATE TABLE "FLEX2"."FMSPONSOREDSTUDENT"
   (	"STUDENTID" NUMBER(10,0),
	"STUDENT_SPONSID" NUMBER(14,0),
	"CAMPUSID" NUMBER(3,0),
	"ROLLNO" NUMBER(12,0),
	"ARN" NUMBER(10,0),
	"TYPE" VARCHAR2(50),
	"AMOUNT" NUMBER(8,2),
	"SPONSORSHIPID" NUMBER(10,0),
	"SUBHEADID" NUMBER(10,0),
	"SEMID" NUMBER(8,0),
	"DOCREF" VARCHAR2(250),
	"REMARKS" VARCHAR2(4000),
	"ENTEREDBY" VARCHAR2(50),
	"ENTRYDATE" DATE,
	"MODIFIEDBY" VARCHAR2(50),
	"MODIFIEDDATE" DATE,
	"STATUS" NUMBER(2,0)
   ) ;
--------------------------------------------------------
--  DDL for Table FMSPONSORSHIP
--------------------------------------------------------

  CREATE TABLE "FLEX2"."FMSPONSORSHIP"
   (	"SPONSORSHIPID" NUMBER(10,0),
	"CAMPUSID" NUMBER(3,0),
	"CODE" VARCHAR2(10),
	"TITLE" VARCHAR2(500),
	"MINCGPA" NUMBER(3,2),
	"MINSGPA" NUMBER(3,2),
	"STARTSEMID" VARCHAR2(20),
	"DOCREF" VARCHAR2(250),
	"REMARKS" VARCHAR2(4000),
	"ENTEREDBY" VARCHAR2(50),
	"ENTRYDATE" DATE,
	"MODIFIEDBY" VARCHAR2(50),
	"MODIFIEDDATE" DATE,
	"STATUS" NUMBER(2,0),
	"SPONSTYPE" VARCHAR2(20),
	"SPONSHEAD" VARCHAR2(20),
	"ISONFULLLOAD" NUMBER(1,0) DEFAULT 0
   ) ;
--------------------------------------------------------
--  DDL for Table FMSPONSORSHIPDETAIL
--------------------------------------------------------

  CREATE TABLE "FLEX2"."FMSPONSORSHIPDETAIL"
   (	"SPONSORSHIPDETAILID" NUMBER(10,0),
	"SPONSORSHIPID" NUMBER(10,0),
	"AMOUNT" NUMBER(18,0),
	"TYPE" VARCHAR2(50),
	"SUBHEADID" NUMBER(10,0),
	"REMARKS" VARCHAR2(4000),
	"ENTEREDBY" VARCHAR2(50),
	"ENTRYDATE" DATE,
	"MODIFIEDBY" VARCHAR2(50),
	"MODIFIEDDATE" DATE,
	"STATUS" NUMBER(2,0)
   ) ;
--------------------------------------------------------
--  DDL for Table FMSTATUS
--------------------------------------------------------

  CREATE TABLE "FLEX2"."FMSTATUS"
   (	"STATUSID" NUMBER(10,0),
	"TITLE" VARCHAR2(50),
	"DESCRIPTION" VARCHAR2(500),
	"ENTEREDBY" VARCHAR2(50),
	"ENTRYDATE" DATE
   ) ;
--------------------------------------------------------
--  DDL for Table FMSTUDENTFEETYPE
--------------------------------------------------------

  CREATE TABLE "FLEX2"."FMSTUDENTFEETYPE"
   (	"ID" NUMBER(10,0),
	"CAMPUSID" NUMBER(3,0),
	"ROLLNO" NUMBER(12,0),
	"SEMID" NUMBER(8,0),
	"FEETYPEID" NUMBER(10,0),
	"REMARKS" VARCHAR2(4000),
	"ENTEREDBY" VARCHAR2(50),
	"ENTRYDATE" DATE,
	"MODIFIEDDATE" DATE,
	"LASTMODIFIEDBY" VARCHAR2(50),
	"STATUS" NUMBER(2,0)
   ) ;
--------------------------------------------------------
--  DDL for Table FMSTUDENTFEETYPE_B
--------------------------------------------------------

  CREATE TABLE "FLEX2"."FMSTUDENTFEETYPE_B"
   (	"ID" NUMBER(10,0),
	"CAMPUSID" NUMBER(3,0),
	"ROLLNO" NUMBER(12,0),
	"SEMID" NUMBER(8,0),
	"FEETYPEID" NUMBER(10,0),
	"REMARKS" VARCHAR2(4000),
	"ENTEREDBY" VARCHAR2(50),
	"ENTRYDATE" DATE,
	"MODIFIEDDATE" DATE,
	"LASTMODIFIEDBY" VARCHAR2(50),
	"STATUS" NUMBER(2,0)
   ) ;
--------------------------------------------------------
--  DDL for Table FMSTUDENTSPONSORSHIP
--------------------------------------------------------

  CREATE TABLE "FLEX2"."FMSTUDENTSPONSORSHIP"
   (	"CAMPUSID" NUMBER(3,0),
	"ROLLNO" NUMBER(12,0),
	"ARN" NUMBER(10,0),
	"NAME" VARCHAR2(250),
	"PROGRAMID" VARCHAR2(250),
	"SPONSORSHIPID" NUMBER(10,0),
	"STARTSEMID" NUMBER(8,0),
	"ENDSEMID" NUMBER(8,0),
	"TYPE" VARCHAR2(50),
	"AMOUNT" NUMBER(8,2),
	"MINSGPA" NUMBER(3,2),
	"MINCGPA" NUMBER(8,2),
	"MINCOURSES" NUMBER(2,0),
	"MAXCOURSES" NUMBER(2,0),
	"REMARKS" VARCHAR2(4000),
	"ENTEREDBY" VARCHAR2(50),
	"ENTRYDATE" DATE DEFAULT SYSDATE,
	"MODIFIEDBY" VARCHAR2(50),
	"MODIFIEDDATE" DATE,
	"STATUS" NUMBER(2,0) DEFAULT 1
   ) ;
--------------------------------------------------------
--  DDL for Table FMSUBHEAD
--------------------------------------------------------

  CREATE TABLE "FLEX2"."FMSUBHEAD"
   (	"SUBHEADID" NUMBER(10,0),
	"TITLE" VARCHAR2(50),
	"HEADID" NUMBER(10,0),
	"ORDERNO" NUMBER(10,0),
	"ACCOUNTCODE" VARCHAR2(50),
	"ENTEREDBY" VARCHAR2(50),
	"ENTRYDATE" DATE,
	"MODIFIEDBY" VARCHAR2(50),
	"MODIFIEDDATE" DATE,
	"STATUS" NUMBER(2,0)
   ) ;
--------------------------------------------------------
--  DDL for Table FMWHTAXDEPOSITRECORD
--------------------------------------------------------

  CREATE TABLE "FLEX2"."FMWHTAXDEPOSITRECORD"
   (	"SNO" NUMBER(12,0),
	"FILENAME" VARCHAR2(500 CHAR),
	"CERTIFICATENO" VARCHAR2(50 CHAR),
	"RECEIPTNO" NUMBER(19,0),
	"CAMPUSID" NUMBER(3,0),
	"DBROLLNO" NUMBER(12,0),
	"ROLLNO" VARCHAR2(50 CHAR),
	"STUDENTNAME" VARCHAR2(100 CHAR),
	"GAURDIANRELATION" NCHAR(10),
	"GAURDIANNAME" VARCHAR2(200 CHAR),
	"GAURDIANNTN" VARCHAR2(100 CHAR),
	"GAURDIANCNIC" VARCHAR2(20 CHAR),
	"GAURDIANADDRESS" VARCHAR2(500 CHAR),
	"TAXYEAR" VARCHAR2(50 CHAR),
	"FROMDATE" DATE,
	"TODATE" DATE,
	"TAXABLEINCOME" NUMBER(18,0),
	"WHTAXREC" NUMBER(18,0),
	"WHTAXCOLLECTED" NUMBER(18,0),
	"DEPOSITDATE" DATE,
	"DEPOSITSLIPNO" VARCHAR2(50 CHAR),
	"BANK" VARCHAR2(250 CHAR),
	"BRANCHCODE" VARCHAR2(250 CHAR),
	"REMARKS" VARCHAR2(250 CHAR),
	"ENTEREDBY" VARCHAR2(50 CHAR),
	"ENTRYDATE" DATE,
	"MODIFIEDBY" VARCHAR2(50 CHAR),
	"MODIFIEDDATE" DATE,
	"LASTPRINTEDBY" VARCHAR2(50 CHAR),
	"LASTPRINTEDDATE" DATE,
	"STATUS" NUMBER(1,0)
   ) ;
--------------------------------------------------------
--  DDL for Table FMWHTAXDEPOSITRECORD_PWR
--------------------------------------------------------

  CREATE TABLE "FLEX2"."FMWHTAXDEPOSITRECORD_PWR"
   (	"SNO" NUMBER(12,0),
	"FILENAME" VARCHAR2(500 CHAR),
	"CERTIFICATENO" VARCHAR2(50 CHAR),
	"RECEIPTNO" NUMBER(19,0),
	"CAMPUSID" NUMBER(3,0),
	"DBROLLNO" NUMBER(12,0),
	"ROLLNO" VARCHAR2(50 CHAR),
	"STUDENTNAME" VARCHAR2(100 CHAR),
	"GAURDIANRELATION" NCHAR(10),
	"GAURDIANNAME" VARCHAR2(200 CHAR),
	"GAURDIANNTN" VARCHAR2(100 CHAR),
	"GAURDIANCNIC" VARCHAR2(20 CHAR),
	"GAURDIANADDRESS" VARCHAR2(500 CHAR),
	"TAXYEAR" VARCHAR2(50 CHAR),
	"FROMDATE" DATE,
	"TODATE" DATE,
	"TAXABLEINCOME" NUMBER(18,0),
	"WHTAXREC" NUMBER(18,0),
	"WHTAXCOLLECTED" NUMBER(18,0),
	"DEPOSITDATE" DATE,
	"DEPOSITSLIPNO" VARCHAR2(50 CHAR),
	"BANK" VARCHAR2(250 CHAR),
	"BRANCHCODE" VARCHAR2(250 CHAR),
	"REMARKS" VARCHAR2(250 CHAR),
	"ENTEREDBY" VARCHAR2(50 CHAR),
	"ENTRYDATE" DATE,
	"MODIFIEDBY" VARCHAR2(50 CHAR),
	"MODIFIEDDATE" DATE,
	"LASTPRINTEDBY" VARCHAR2(50 CHAR),
	"LASTPRINTEDDATE" DATE,
	"STATUS" NUMBER(1,0)
   ) ;
--------------------------------------------------------
--  DDL for Table FMWHTAXEXEMPTION
--------------------------------------------------------

  CREATE TABLE "FLEX2"."FMWHTAXEXEMPTION"
   (	"ROLLNO" NUMBER(14,0),
	"TAXYEAR" VARCHAR2(10),
	"SEMID" NUMBER(5,0),
	"REMARKS" VARCHAR2(500),
	"ENTEREDBY" VARCHAR2(100),
	"ENTRYDATE" DATE,
	"STATUS" NUMBER(2,0)
   ) ;
--------------------------------------------------------
--  DDL for Table FM_DATES
--------------------------------------------------------

  CREATE TABLE "FLEX2"."FM_DATES"
   (	"ID" NUMBER(10,0),
	"CAMPUSID" NUMBER(2,0),
	"SEMID" NUMBER(5,0),
	"PROGRAMID" NUMBER(3,0),
	"BATCHNO" NUMBER(5,0),
	"SECTIONID" NUMBER(5,0),
	"FEE_DUE_DATE" DATE,
	"WITTDRAW_DATE" DATE,
	"STATUS" NUMBER(2,0) DEFAULT 1
   ) ;
--------------------------------------------------------
--  DDL for Table FM_WRONG_POSTING
--------------------------------------------------------

  CREATE TABLE "FLEX2"."FM_WRONG_POSTING"
   (	"ROLLNO" NUMBER(12,0),
	"SEMID" NUMBER(8,0),
	"SCROLLDETAILID" NUMBER(14,0),
	"CHALLANNO" NUMBER(11,0),
	"AMOUNT" NUMBER(18,0),
	"PAYMENTDATE" DATE,
	"MODIFIEDBY" VARCHAR2(50),
	"MODIFIEDDATE" DATE,
	"ENTRYDATE" DATE,
	"TRANSACTIONDATE" DATE
   ) ;
--------------------------------------------------------
--  DDL for Table GRADE
--------------------------------------------------------

  CREATE TABLE "FLEX2"."GRADE"
   (	"GRADE_ID" VARCHAR2(3),
	"GRADE" VARCHAR2(5),
	"GRADE_POINT" NUMBER(3,2),
	"MIN_POINT" NUMBER(5,2),
	"MAX_POINT" NUMBER(5,2)
   ) ;
--------------------------------------------------------
--  DDL for Table GRADEPOLICY
--------------------------------------------------------

  CREATE TABLE "FLEX2"."GRADEPOLICY"
   (	"GRADEPOLICYID" NUMBER(4,0),
	"GRADE_ID" VARCHAR2(3),
	"STATUS" NUMBER(1,0)
   ) ;
--------------------------------------------------------
--  DDL for Table GRADEPOLICY_COURSE
--------------------------------------------------------

  CREATE TABLE "FLEX2"."GRADEPOLICY_COURSE"
   (	"COURSE_ID" NUMBER(4,0),
	"GRADEPOLICYID" NUMBER(4,0),
	"STARTINGDATE" DATE,
	"ENDINGDATE" DATE
   ) ;
--------------------------------------------------------
--  DDL for Table GRADEPOLICY_COURSETEMP
--------------------------------------------------------

  CREATE TABLE "FLEX2"."GRADEPOLICY_COURSETEMP"
   (	"CODE" VARCHAR2(10),
	"GRADEPOLICYID" NUMBER(4,0),
	"STARTINGDATE" DATE,
	"ENDINGDATE" DATE
   ) ;
--------------------------------------------------------
--  DDL for Table GRADEPOLICY_DETAIL
--------------------------------------------------------

  CREATE TABLE "FLEX2"."GRADEPOLICY_DETAIL"
   (	"GRADEPOLICYID" NUMBER(4,0),
	"DESCRIPTION" VARCHAR2(200)
   ) ;
--------------------------------------------------------
--  DDL for Table GRADING_SCHEME
--------------------------------------------------------

  CREATE TABLE "FLEX2"."GRADING_SCHEME"
   (	"GS_ID" NUMBER(1,0),
	"GS_TEXT" VARCHAR2(150),
	"CORRECTIONGRADE" VARCHAR2(5),
	"AVG_GRADE" VARCHAR2(5),
	"MIN_POINT" NUMBER(5,2),
	"MAX_POINT" NUMBER(5,2),
	"AVG_POINT" NUMBER(5,2)
   ) ;
--------------------------------------------------------
--  DDL for Table GRADING_ZFACTOR
--------------------------------------------------------

  CREATE TABLE "FLEX2"."GRADING_ZFACTOR"
   (	"GZF_ID" NUMBER(2,0),
	"ZF_VALUE" NUMBER(5,2),
	"GS_ID" NUMBER(1,0),
	"GRADE_ID" VARCHAR2(3)
   ) ;
--------------------------------------------------------
--  DDL for Table HR_EMP_DATA_TEMP
--------------------------------------------------------

  CREATE TABLE "FLEX2"."HR_EMP_DATA_TEMP"
   (	"HRMID" VARCHAR2(10),
	"NAME" VARCHAR2(100),
	"DESIGNATION" VARCHAR2(30),
	"CNINC" VARCHAR2(30),
	"CAMPUS" VARCHAR2(50),
	"CADRE" VARCHAR2(50),
	"CAMP_ID" NUMBER(3,0)
   ) ;
--------------------------------------------------------
--  DDL for Table INAME
--------------------------------------------------------

  CREATE TABLE "FLEX2"."INAME"
   (	"NAME" VARCHAR2(50),
	"ID" NUMBER,
	"VERSION" NUMBER,
	"TRIMSTART" NUMBER(1,0) DEFAULT 0
   ) ;
--------------------------------------------------------
--  DDL for Table INSTR_COURSE_PREF
--------------------------------------------------------

  CREATE TABLE "FLEX2"."INSTR_COURSE_PREF"
   (	"PREF_ID" NUMBER(6,0),
	"EMP_ID" NUMBER(8,0),
	"SEM_ID" NUMBER(8,0),
	"COURSE_ID" NUMBER(4,0),
	"PREF_SNO" NUMBER(2,0),
	"REMARKS" VARCHAR2(500),
	"CREATED_BY" NUMBER(8,0),
	"CREATED_DATE" DATE
   ) ;
--------------------------------------------------------
--  DDL for Table LECTURE
--------------------------------------------------------

  CREATE TABLE "FLEX2"."LECTURE"
   (	"LECTURE_ID" NUMBER(10,0),
	"OFFER_ID" NUMBER(12,0),
	"LECTURE_DATE" DATE,
	"LECTURE_NO" NUMBER(2,0),
	"DURATION" NUMBER(2,1),
	"CREATED_BY" NUMBER(8,0),
	"CREATED_ON" DATE
   ) ;
--------------------------------------------------------
--  DDL for Table NUMEN_EMPLOYEEDETAIL
--------------------------------------------------------

  CREATE TABLE "FLEX2"."NUMEN_EMPLOYEEDETAIL"
   (	"CAMPUS" VARCHAR2(5),
	"OFFER_ID" NUMBER(12,0),
	"COURSE_ID" NUMBER(4,0),
	"COURSE" VARCHAR2(10),
	"TITLE" VARCHAR2(50),
	"EMP_ID" NUMBER(8,0),
	"HRM_ID" VARCHAR2(12),
	"EMP_NAME" VARCHAR2(50),
	"REG_STUDENT" NUMBER(5,0),
	"FEEDBACK_RECEIVED" NUMBER(5,0),
	"FEEDBACK_PERCENTAGE" NUMBER(38,20),
	"CAMP_ID" NUMBER(3,0),
	"SECTION" VARCHAR2(50),
	"SECTION_ID" NUMBER(4,0),
	"PROGRAM" CHAR(10),
	"SEMESTER" VARCHAR2(20),
	"SEM_ID" NUMBER(5,0)
   ) ;
--------------------------------------------------------
--  DDL for Table NUTES_SEG_DATA
--------------------------------------------------------

  CREATE TABLE "FLEX2"."NUTES_SEG_DATA"
   (	"YEAR" NUMBER(5,0),
	"TESTCENTER" NUMBER(2,0),
	"ARN" NUMBER(10,0),
	"ROLL_NO" NUMBER(12,0),
	"CAMP_ROLL" VARCHAR2(4000),
	"SHORT_NAME" VARCHAR2(50),
	"PROG_CODE" CHAR(10),
	"FIRST_REG_SEM" NUMBER,
	"LAST_REG_SEM" NUMBER,
	"STATUS" VARCHAR2(30),
	"NODE_NAME" VARCHAR2(500),
	"MATRIC_OBT" NUMBER,
	"MATRIC_TOT" NUMBER,
	"INTER_OBT" NUMBER,
	"INTER_TOT" NUMBER,
	"MARKS" NUMBER(8,3),
	"CGPA" NUMBER
   ) ;
--------------------------------------------------------
--  DDL for Table NUTES_TM_SEG
--------------------------------------------------------

  CREATE TABLE "FLEX2"."NUTES_TM_SEG"
   (	"YEAR" NUMBER(5,0),
	"TESTCENTER" NUMBER(2,0),
	"ARN" NUMBER(30,0),
	"CANDIDATE_ID" NUMBER(8,0),
	"QUESTION_ATTEMPTED" NUMBER(4,0),
	"QUESTION_CORRECT" NUMBER(4,0),
	"QUESTION_WTG" NUMBER(8,2),
	"MARKS" NUMBER(8,3),
	"NODE_NAME" VARCHAR2(500),
	"PROGRAMME_ID" NUMBER(8,0),
	"GROUP_ID" NUMBER(8,0),
	"TEST_DISCIPLINE" VARCHAR2(6)
   ) ;
--------------------------------------------------------
--  DDL for Table ORA_ASPNET_APPLICATIONS
--------------------------------------------------------

  CREATE TABLE "FLEX2"."ORA_ASPNET_APPLICATIONS"
   (	"APPLICATIONNAME" NVARCHAR2(256),
	"LOWEREDAPPLICATIONNAME" NVARCHAR2(256),
	"APPLICATIONID" RAW(16) DEFAULT SYS_GUID(),
	"DESCRIPTION" NVARCHAR2(256)
   ) ;
--------------------------------------------------------
--  DDL for Table ORA_ASPNET_MEMBERSHIP
--------------------------------------------------------

  CREATE TABLE "FLEX2"."ORA_ASPNET_MEMBERSHIP"
   (	"APPLICATIONID" RAW(16),
	"USERID" RAW(16),
	"PASSWORD" NVARCHAR2(128),
	"PASSWORDFORMAT" NUMBER(10,0) DEFAULT 0,
	"PASSWORDSALT" NVARCHAR2(128),
	"MOBILEPIN" NVARCHAR2(16),
	"EMAIL" NVARCHAR2(256),
	"LOWEREDEMAIL" NVARCHAR2(256),
	"PASSWORDQUESTION" NVARCHAR2(256),
	"PASSWORDANSWER" NVARCHAR2(128),
	"ISAPPROVED" NUMBER(10,0),
	"ISLOCKEDOUT" NUMBER(10,0),
	"CREATEDATE" DATE,
	"LASTLOGINDATE" DATE,
	"LASTPASSWORDCHANGEDDATE" DATE,
	"LASTLOCKOUTDATE" DATE,
	"FAILEDPWDATTEMPTCOUNT" NUMBER(10,0),
	"FAILEDPWDATTEMPTWINSTART" DATE,
	"FAILEDPWDANSWERATTEMPTCOUNT" NUMBER(10,0),
	"FAILEDPWDANSWERATTEMPTWINSTART" DATE,
	"COMMENTS" NCLOB
   ) ;
--------------------------------------------------------
--  DDL for Table ORA_ASPNET_PATHS
--------------------------------------------------------

  CREATE TABLE "FLEX2"."ORA_ASPNET_PATHS"
   (	"APPLICATIONID" RAW(16),
	"PATHID" RAW(16) DEFAULT SYS_GUID(),
	"PATH" NVARCHAR2(256),
	"LOWEREDPATH" NVARCHAR2(256)
   ) ;
--------------------------------------------------------
--  DDL for Table ORA_ASPNET_PERSONALIZNALLUSERS
--------------------------------------------------------

  CREATE TABLE "FLEX2"."ORA_ASPNET_PERSONALIZNALLUSERS"
   (	"PATHID" RAW(16),
	"PAGESETTINGS" BLOB,
	"LASTUPDATEDDATE" DATE
   ) ;
--------------------------------------------------------
--  DDL for Table ORA_ASPNET_PERSONALIZNPERUSER
--------------------------------------------------------

  CREATE TABLE "FLEX2"."ORA_ASPNET_PERSONALIZNPERUSER"
   (	"ID" RAW(16) DEFAULT SYS_GUID(),
	"PATHID" RAW(16),
	"USERID" RAW(16),
	"PAGESETTINGS" BLOB,
	"LASTUPDATEDDATE" DATE
   ) ;
--------------------------------------------------------
--  DDL for Table ORA_ASPNET_PROFILE
--------------------------------------------------------

  CREATE TABLE "FLEX2"."ORA_ASPNET_PROFILE"
   (	"USERID" RAW(16),
	"PROPERTYNAMES" NCLOB,
	"PROPERTYVALUESSTRING" NCLOB,
	"PROPERTYVALUESBINARY" BLOB,
	"LASTUPDATEDDATE" DATE
   ) ;
--------------------------------------------------------
--  DDL for Table ORA_ASPNET_ROLES
--------------------------------------------------------

  CREATE TABLE "FLEX2"."ORA_ASPNET_ROLES"
   (	"APPLICATIONID" RAW(16),
	"ROLEID" RAW(16) DEFAULT SYS_GUID(),
	"ROLENAME" NVARCHAR2(256),
	"LOWEREDROLENAME" NVARCHAR2(256),
	"DESCRIPTION" NVARCHAR2(256)
   ) ;
--------------------------------------------------------
--  DDL for Table ORA_ASPNET_SESSIONAPPLICATIONS
--------------------------------------------------------

  CREATE TABLE "FLEX2"."ORA_ASPNET_SESSIONAPPLICATIONS"
   (	"APPID" RAW(16),
	"APPNAME" NVARCHAR2(280)
   ) ;
--------------------------------------------------------
--  DDL for Table ORA_ASPNET_SESSIONS
--------------------------------------------------------

  CREATE TABLE "FLEX2"."ORA_ASPNET_SESSIONS"
   (	"SESSIONID" NVARCHAR2(116),
	"CREATED" DATE DEFAULT SYS_EXTRACT_UTC(SYSTIMESTAMP),
	"EXPIRES" DATE,
	"LOCKDATE" DATE,
	"LOCKDATELOCAL" DATE,
	"LOCKCOOKIE" NUMBER(10,0),
	"TIMEOUT" NUMBER(10,0),
	"LOCKED" NUMBER(10,0),
	"SESSIONITEMSHORT" RAW(2000),
	"SESSIONITEMLONG" BLOB,
	"FLAGS" NUMBER(10,0) DEFAULT 0
   ) ;
--------------------------------------------------------
--  DDL for Table ORA_ASPNET_SITEMAP
--------------------------------------------------------

  CREATE TABLE "FLEX2"."ORA_ASPNET_SITEMAP"
   (	"APPLICATIONID" RAW(16),
	"ID" NUMBER(10,0),
	"TITLE" NVARCHAR2(32),
	"DESCRIPTION" NVARCHAR2(512),
	"URL" NVARCHAR2(512),
	"ROLES" NVARCHAR2(512),
	"PARENT" NUMBER(10,0)
   ) ;
--------------------------------------------------------
--  DDL for Table ORA_ASPNET_USERS
--------------------------------------------------------

  CREATE TABLE "FLEX2"."ORA_ASPNET_USERS"
   (	"APPLICATIONID" RAW(16),
	"USERID" RAW(16) DEFAULT SYS_GUID(),
	"USERNAME" NVARCHAR2(256),
	"LOWEREDUSERNAME" NVARCHAR2(256),
	"MOBILEALIAS" NVARCHAR2(16) DEFAULT NULL,
	"ISANONYMOUS" NUMBER(10,0) DEFAULT 0,
	"LASTACTIVITYDATE" DATE
   ) ;
--------------------------------------------------------
--  DDL for Table ORA_ASPNET_USERSINROLES
--------------------------------------------------------

  CREATE TABLE "FLEX2"."ORA_ASPNET_USERSINROLES"
   (	"USERID" RAW(16),
	"ROLEID" RAW(16)
   ) ;
--------------------------------------------------------
--  DDL for Table ORA_ASPNET_WEBEVENTS
--------------------------------------------------------

  CREATE TABLE "FLEX2"."ORA_ASPNET_WEBEVENTS"
   (	"EVENTID" CHAR(32),
	"EVENTTIMEUTC" DATE,
	"EVENTTIME" DATE,
	"EVENTTYPE" NVARCHAR2(256),
	"EVENTSEQUENCE" NUMBER(19,0),
	"EVENTOCCURENCE" NUMBER(19,0),
	"EVENTCODE" NUMBER(10,0),
	"EVENTDETAILCODE" NUMBER(10,0),
	"MESSAGE" NVARCHAR2(1000),
	"APPLICATIONPATH" NVARCHAR2(256),
	"APPLICATIONVIRTUALPATH" NVARCHAR2(256),
	"MACHINENAME" NVARCHAR2(256),
	"REQUESTURL" NVARCHAR2(256),
	"EXCEPTIONTYPE" NVARCHAR2(256),
	"DETAILS" NCLOB
   ) ;
--------------------------------------------------------
--  DDL for Table PHD_CLOSURE_ADMISSION_DETAIL
--------------------------------------------------------

  CREATE TABLE "FLEX2"."PHD_CLOSURE_ADMISSION_DETAIL"
   (	"PA_ID" NUMBER(10,0),
	"ROLL_NO" NUMBER,
	"CLOSURE_DATE" DATE,
	"BASR_DATE" DATE,
	"REASONS" VARCHAR2(500)
   ) ;
--------------------------------------------------------
--  DDL for Table PHD_COMPREHENSIVETEST
--------------------------------------------------------

  CREATE TABLE "FLEX2"."PHD_COMPREHENSIVETEST"
   (	"CT_ID" NUMBER(10,0),
	"ROLL_NO" NUMBER(10,0),
	"ATTEMPT" NUMBER(10,0),
	"APPLIEDON" DATE,
	"GSCACTIONON" DATE,
	"TESTDATE" DATE,
	"TESTTAKEN" NUMBER(10,0),
	"PERCENTAGE" NUMBER(10,0),
	"PROGRAMID" NUMBER(10,0) DEFAULT 1,
	"CAMPUSID" NUMBER(10,0) DEFAULT 1
   ) ;
--------------------------------------------------------
--  DDL for Table PHD_FOREIGN_EVALUATORS
--------------------------------------------------------

  CREATE TABLE "FLEX2"."PHD_FOREIGN_EVALUATORS"
   (	"FEVAL_ID" NUMBER(10,0),
	"NAME" VARCHAR2(200),
	"DEPARTMENT" VARCHAR2(100),
	"UNIVERSITY" VARCHAR2(100),
	"COUNTRY" VARCHAR2(100)
   ) ;
--------------------------------------------------------
--  DDL for Table PHD_GAT_DETAIL
--------------------------------------------------------

  CREATE TABLE "FLEX2"."PHD_GAT_DETAIL"
   (	"GID" NUMBER(10,0),
	"ROLL_NO" NUMBER(10,0),
	"TEST_ID" NUMBER(10,0),
	"SCORE" NUMBER(10,0),
	"PERCENTILE" NUMBER(10,0),
	"TEST_DATE" VARCHAR2(30)
   ) ;
--------------------------------------------------------
--  DDL for Table PHD_GSC_MEETING_AGENDA
--------------------------------------------------------

  CREATE TABLE "FLEX2"."PHD_GSC_MEETING_AGENDA"
   (	"GMA_ID" NUMBER(10,0),
	"MT_ID" NUMBER(10,0),
	"AGENDA_NO" NUMBER(10,0),
	"TOPIC" VARCHAR2(4000),
	"SUMMARY" VARCHAR2(4000)
   ) ;
--------------------------------------------------------
--  DDL for Table PHD_GSC_MEETING_DETAIL
--------------------------------------------------------

  CREATE TABLE "FLEX2"."PHD_GSC_MEETING_DETAIL"
   (	"MT_ID" NUMBER(10,0),
	"TITLE" VARCHAR2(150 CHAR),
	"VENUE" VARCHAR2(100 CHAR),
	"TIMINGS" DATE,
	"CREATEDBY" VARCHAR2(100 CHAR),
	"CREATEDON" DATE
   ) ;
--------------------------------------------------------
--  DDL for Table PHD_I_DOCUMENTS
--------------------------------------------------------

  CREATE TABLE "FLEX2"."PHD_I_DOCUMENTS"
   (	"D_ID" NUMBER(10,0),
	"NAME" VARCHAR2(100),
	"FOR_STUDENT" NUMBER(10,0)
   ) ;
--------------------------------------------------------
--  DDL for Table PHD_I_DOC_TYPE
--------------------------------------------------------

  CREATE TABLE "FLEX2"."PHD_I_DOC_TYPE"
   (	"ID" NUMBER(10,0),
	"TYPE" VARCHAR2(200)
   ) ;
--------------------------------------------------------
--  DDL for Table PHD_I_GSC_MEMBER
--------------------------------------------------------

  CREATE TABLE "FLEX2"."PHD_I_GSC_MEMBER"
   (	"EMP_ID" NUMBER(10,0),
	"CAMP_ID" NUMBER(10,0)
   ) ;
--------------------------------------------------------
--  DDL for Table PHD_I_STATUS
--------------------------------------------------------

  CREATE TABLE "FLEX2"."PHD_I_STATUS"
   (	"S_ID" NUMBER(10,0),
	"DETAILS" VARCHAR2(50)
   ) ;
--------------------------------------------------------
--  DDL for Table PHD_LOCAL_EVALUATORS
--------------------------------------------------------

  CREATE TABLE "FLEX2"."PHD_LOCAL_EVALUATORS"
   (	"LEVAL_ID" NUMBER(10,0),
	"NAME" VARCHAR2(200),
	"DEPARTMENT" VARCHAR2(100),
	"INSTITUTION" VARCHAR2(200),
	"CITY" VARCHAR2(200)
   ) ;
--------------------------------------------------------
--  DDL for Table PHD_STD_EVALUATORS
--------------------------------------------------------

  CREATE TABLE "FLEX2"."PHD_STD_EVALUATORS"
   (	"STD_EVAL_ID" NUMBER(10,0),
	"ROLL_NO" NUMBER(10,0),
	"FOREIGN_EVAL_I" NUMBER(10,0),
	"FOREIGN_EVAL_II" NUMBER(10,0),
	"FOREIGN_EVAL_III" NUMBER(10,0),
	"LOCAL_EVAL_I" NUMBER(10,0),
	"LOCAL_EVAL_II" NUMBER(10,0),
	"LOCAL_EVAL_III" NUMBER(10,0),
	"INTERNAL_EVALUATOR" NUMBER(10,0)
   ) ;
--------------------------------------------------------
--  DDL for Table PHD_STUDENT_STATUS
--------------------------------------------------------

  CREATE TABLE "FLEX2"."PHD_STUDENT_STATUS"
   (	"ROLL_NO" NUMBER(10,0),
	"STATUS" NUMBER(10,0) DEFAULT 0,
	"FUNDED_BY" NUMBER(10,0) DEFAULT 0,
	"HEC_PIN" VARCHAR2(30),
	"DEFENSE_DATE" DATE
   ) ;
--------------------------------------------------------
--  DDL for Table PHD_STUDENT_SUPERVISOR
--------------------------------------------------------

  CREATE TABLE "FLEX2"."PHD_STUDENT_SUPERVISOR"
   (	"ID" NUMBER(10,0),
	"ARN" NUMBER(10,0),
	"ROLLNO" NUMBER(10,0),
	"EMP_ID" NUMBER(10,0),
	"SUPERVISOR_ID" NUMBER(10,0),
	"STATUS" NUMBER(10,0),
	"REQUESTEDON" DATE,
	"ACTIONON" DATE,
	"REASON" VARCHAR2(4000),
	"THESIS_DETAILS" VARCHAR2(4000)
   ) ;
--------------------------------------------------------
--  DDL for Table PHD_STUDENT_SUPERVISOR_DETAIL
--------------------------------------------------------

  CREATE TABLE "FLEX2"."PHD_STUDENT_SUPERVISOR_DETAIL"
   (	"ID" NUMBER(10,0),
	"STD_SUPERVISOR_ID" NUMBER(10,0),
	"IS_DOC" NUMBER(10,0),
	"IDEA_BY" NUMBER(10,0) DEFAULT 0,
	"CAN_CONTINUE" NUMBER(10,0) DEFAULT 0
   ) ;
--------------------------------------------------------
--  DDL for Table PHD_STUDENT_SUPERVISOR_LOG
--------------------------------------------------------

  CREATE TABLE "FLEX2"."PHD_STUDENT_SUPERVISOR_LOG"
   (	"PSSD_ID" NUMBER(10,0),
	"SUPERVISOR_ID" NUMBER(10,0),
	"ROLL_NO" NUMBER(10,0),
	"STATUS" NUMBER(10,0),
	"REASON" VARCHAR2(400),
	"ACTIONBY" NUMBER(10,0),
	"ACTIONON" DATE,
	"CHANGE_REQUESTED_BY" NUMBER(10,0),
	"CHANGE_REQUESTED_ON" DATE,
	"COMMENTS_FOR_SUPERVISOR" VARCHAR2(400),
	"COMMENTS_FOR_GSC" VARCHAR2(500),
	"SUPERVISOR_COMMENTS" VARCHAR2(600)
   ) ;
--------------------------------------------------------
--  DDL for Table PROGRAM
--------------------------------------------------------

  CREATE TABLE "FLEX2"."PROGRAM"
   (	"PROG_ID" NUMBER(4,0),
	"CODE" CHAR(10),
	"TITLE" VARCHAR2(52),
	"LEVEL_ID" NUMBER(2,0),
	"SHORT_NAME" VARCHAR2(20),
	"SCH_ID" NUMBER(4,0),
	"NO_OF_SEM" NUMBER(1,0),
	"MAX_DURATION_YEAR" NUMBER(1,0),
	"CREATED_BY" NUMBER(4,0),
	"CREATED_ON" DATE DEFAULT sysdate,
	"PROG_RGB" VARCHAR2(10),
	"RPT_TITLE" VARCHAR2(52)
   ) ;
--------------------------------------------------------
--  DDL for Table PROGRAM_CARD_COLOR
--------------------------------------------------------

  CREATE TABLE "FLEX2"."PROGRAM_CARD_COLOR"
   (	"PROG_CODE" VARCHAR2(10),
	"PROG_RGB" VARCHAR2(15)
   ) ;
--------------------------------------------------------
--  DDL for Table PROGRAM_COURSE
--------------------------------------------------------

  CREATE TABLE "FLEX2"."PROGRAM_COURSE"
   (	"BATCH_NO" NUMBER(8,0),
	"PROG_ID" NUMBER(3,0),
	"COURSE_ID" NUMBER(4,0),
	"RELATOIN_ID" CHAR(2),
	"CREATED_BY" NUMBER(8,0),
	"CREATED_DATE" DATE DEFAULT sysdate
   ) ;
--------------------------------------------------------
--  DDL for Table PROG_BATCH_DOMAIN
--------------------------------------------------------

  CREATE TABLE "FLEX2"."PROG_BATCH_DOMAIN"
   (	"BATCH_NO" NUMBER(8,0),
	"PROG_ID" NUMBER(4,0),
	"SCH_DOM_ID" VARCHAR2(6),
	"CORE_CR_HRS" NUMBER(5,2),
	"ELECTIVE_CR_HRS" NUMBER(5,2)
   ) ;
--------------------------------------------------------
--  DDL for Table REGISTRATIONLOG
--------------------------------------------------------

  CREATE TABLE "FLEX2"."REGISTRATIONLOG"
   (	"REGLOGID_OLD" NUMBER(19,0),
	"REGLOGID" NUMBER(14,0),
	"CAMPUSID" NUMBER(3,0),
	"ROLLNO" NUMBER(12,0),
	"OFFERID" NUMBER(12,0),
	"SEMID" NUMBER(6,0),
	"COURSEID" VARCHAR2(10 CHAR),
	"RELATION" VARCHAR2(50 CHAR),
	"REQUESTTYPE" VARCHAR2(50 CHAR),
	"REQUESTEDBY" VARCHAR2(50 CHAR),
	"REQUESTDATE" DATE,
	"ACTION" VARCHAR2(50 CHAR),
	"ACTIONBY" VARCHAR2(50 CHAR),
	"ACTIONDATE" DATE
   ) ;
--------------------------------------------------------
--  DDL for Table REGISTRATIONLOG_20190122
--------------------------------------------------------

  CREATE TABLE "FLEX2"."REGISTRATIONLOG_20190122"
   (	"REGLOGID_OLD" NUMBER(19,0),
	"REGLOGID" NUMBER(14,0),
	"CAMPUSID" NUMBER(3,0),
	"ROLLNO" NUMBER(12,0),
	"OFFERID" NUMBER(12,0),
	"SEMID" NUMBER(6,0),
	"COURSEID" VARCHAR2(10 CHAR),
	"RELATION" VARCHAR2(50 CHAR),
	"REQUESTTYPE" VARCHAR2(50 CHAR),
	"REQUESTEDBY" VARCHAR2(50 CHAR),
	"REQUESTDATE" DATE,
	"ACTION" VARCHAR2(50 CHAR),
	"ACTIONBY" VARCHAR2(50 CHAR),
	"ACTIONDATE" DATE
   ) ;
--------------------------------------------------------
--  DDL for Table REGISTRATIONLOG_TEMP
--------------------------------------------------------

  CREATE TABLE "FLEX2"."REGISTRATIONLOG_TEMP"
   (	"REGLOGID_OLD" NUMBER(19,0),
	"REGLOGID" NUMBER(14,0),
	"CAMPUSID" NUMBER(3,0),
	"ROLLNO" NUMBER(12,0),
	"OFFERID" NUMBER(12,0),
	"SEMID" NUMBER(6,0),
	"COURSEID" VARCHAR2(10 CHAR),
	"RELATION" VARCHAR2(50 CHAR),
	"REQUESTTYPE" VARCHAR2(50 CHAR),
	"REQUESTEDBY" VARCHAR2(50 CHAR),
	"REQUESTDATE" DATE,
	"ACTION" VARCHAR2(50 CHAR),
	"ACTIONBY" VARCHAR2(50 CHAR),
	"ACTIONDATE" DATE
   ) ;
--------------------------------------------------------
--  DDL for Table REPEAT_COURSE
--------------------------------------------------------

  CREATE TABLE "FLEX2"."REPEAT_COURSE"
   (	"OFFER_ID" NUMBER(12,0),
	"USER_ID" NUMBER(10,0),
	"STATUS" NUMBER(1,0)
   ) ;
--------------------------------------------------------
--  DDL for Table ROLLNO_RANGE
--------------------------------------------------------

  CREATE TABLE "FLEX2"."ROLLNO_RANGE"
   (	"CAMP_ID" NUMBER(3,0),
	"SCHOOL_ID" NUMBER(4,0),
	"PROG_ID" NUMBER(4,0),
	"BATCH_NO" NUMBER(4,0),
	"MIN_VALUE" NUMBER(5,0),
	"MAX_VALUE" NUMBER(5,0),
	"CURRENT_VALUE" NUMBER(1,0)
   ) ;
--------------------------------------------------------
--  DDL for Table SCHOOL
--------------------------------------------------------

  CREATE TABLE "FLEX2"."SCHOOL"
   (	"SCH_ID" NUMBER(4,0),
	"CODE" CHAR(5),
	"NAME" VARCHAR2(30),
	"ADDRESS" VARCHAR2(150),
	"CITY" VARCHAR2(20),
	"TELNO" VARCHAR2(12),
	"FAXNO" VARCHAR2(12),
	"SCH_HEAD" VARCHAR2(30),
	"TEAM_NAMES" VARCHAR2(200),
	"CREATED_BY" NUMBER(8,0),
	"CREATED_DATE" DATE DEFAULT sysdate
   ) ;
--------------------------------------------------------
--  DDL for Table SCHOOL_DOMAIN
--------------------------------------------------------

  CREATE TABLE "FLEX2"."SCHOOL_DOMAIN"
   (	"SCH_DOM_ID" VARCHAR2(6),
	"CODE" VARCHAR2(25),
	"TITLE" VARCHAR2(100),
	"DESCRIPTION" VARCHAR2(200),
	"SCH_ID" NUMBER(4,0)
   ) ;
--------------------------------------------------------
--  DDL for Table SECTION
--------------------------------------------------------

  CREATE TABLE "FLEX2"."SECTION"
   (	"SECTION_ID" NUMBER(4,0),
	"TITLE" VARCHAR2(50),
	"CREATED_BY" NUMBER(8,0),
	"CREATED_ON" DATE DEFAULT sysdate
   ) ;
--------------------------------------------------------
--  DDL for Table SEMESTER
--------------------------------------------------------

  CREATE TABLE "FLEX2"."SEMESTER"
   (	"SEM_ID" NUMBER(8,0),
	"TITLE" VARCHAR2(20),
	"STATUS" NUMBER(1,0)
   ) ;
--------------------------------------------------------
--  DDL for Table SEM_TEACHER_ACTIVITY
--------------------------------------------------------

  CREATE TABLE "FLEX2"."SEM_TEACHER_ACTIVITY"
   (	"STA_ID" NUMBER(4,0),
	"EMP_ID" NUMBER(8,0),
	"ACT_ID" NUMBER(4,0),
	"SEM_ID" NUMBER(8,0),
	"PROJ_COORD" NUMBER(2,0) DEFAULT 0,
	"CRETED_BY" NUMBER(4,0),
	"CREATED_ON" DATE,
	"MODIFIED_BY" NUMBER(4,0),
	"MODIFIED_ON" DATE
   ) ;
--------------------------------------------------------
--  DDL for Table STUDENT_ATTENDANCE
--------------------------------------------------------

  CREATE TABLE "FLEX2"."STUDENT_ATTENDANCE"
   (	"LECTURE_ID" NUMBER(10,0),
	"ROLL_NO" NUMBER(12,0),
	"ATTEND_FLAG" VARCHAR2(2),
	"CREATED_BY" NUMBER(8,0),
	"CREATED_ON" DATE
   ) ;
--------------------------------------------------------
--  DDL for Table STUDENT_FAMILY_INFO
--------------------------------------------------------

  CREATE TABLE "FLEX2"."STUDENT_FAMILY_INFO"
   (	"ARN" NUMBER(10,0),
	"REL_TYPE_ID" NUMBER(2,0),
	"FULL_NAME" VARCHAR2(50),
	"GENDER" CHAR(1),
	"CNIC" VARCHAR2(50),
	"USE_FOR_WHTAX" NUMBER(1,0),
	"ADDRESS" VARCHAR2(150),
	"CITY" VARCHAR2(20),
	"PROVINCE" VARCHAR2(20),
	"COUNTRY" CHAR(3),
	"TEL_NO" VARCHAR2(12),
	"MOBILE_NO" VARCHAR2(20),
	"PROFESSION" VARCHAR2(50),
	"JOB_TITLE" VARCHAR2(50),
	"JOB_STATUS" VARCHAR2(50),
	"MONTHLY_INCOME" NUMBER(20,0),
	"USER_NAME" VARCHAR2(50),
	"USER_PASSWORD" VARCHAR2(50),
	"IS_CONTACT_PERSON" NUMBER(1,0),
	"USER_EMAIL" VARCHAR2(100)
   ) ;
--------------------------------------------------------
--  DDL for Table STUDENT_PERSONAL_INFO
--------------------------------------------------------

  CREATE TABLE "FLEX2"."STUDENT_PERSONAL_INFO"
   (	"ARN" NUMBER(10,0),
	"FULL_NAME" VARCHAR2(50),
	"SHORT_NAME" VARCHAR2(50),
	"DOB" DATE,
	"CNIC" VARCHAR2(20),
	"GENDER" CHAR(1),
	"MOBILE_NO" VARCHAR2(25),
	"EMAIL" VARCHAR2(50),
	"NATIONALITY" VARCHAR2(20),
	"CURR_ADDRESS" VARCHAR2(250),
	"CURR_PROVINCE" VARCHAR2(20),
	"CURR_TELNO" VARCHAR2(30),
	"PERM_ADDRESS" VARCHAR2(250),
	"PERM_PROVINCE" VARCHAR2(20),
	"PERM_TELNO" VARCHAR2(30),
	"MAIL_SENT_TO" CHAR(1),
	"NU_EMAIL" VARCHAR2(50),
	"BLOOD_GRP" CHAR(4),
	"CAMP_ID" NUMBER(3,0),
	"CREATED_BY" NUMBER(8,0),
	"CREATED_DATE" DATE DEFAULT sysdate,
	"CURR_COUNTRY" NUMBER(5,0),
	"PERM_COUNTRY" NUMBER(5,0),
	"CURR_CITY" NUMBER(5,0),
	"PERM_CITY" NUMBER(5,0)
   ) ;
--------------------------------------------------------
--  DDL for Table STUDENT_PROGRAM
--------------------------------------------------------

  CREATE TABLE "FLEX2"."STUDENT_PROGRAM"
   (	"ROLL_NO" NUMBER(12,0),
	"ARN" NUMBER(10,0),
	"REG_NO" VARCHAR2(30),
	"CAMP_ID" NUMBER(3,0),
	"PROG_ID" NUMBER(4,0),
	"BATCH_NO" NUMBER(8,0),
	"SPECIALIZATION" VARCHAR2(100),
	"SHIFT" CHAR(1),
	"REG_STATUS" NUMBER(1,0),
	"PROG_STATUS" NUMBER(1,0),
	"CGPA" NUMBER(4,2),
	"CREDITS_EARNED" NUMBER(5,2),
	"CREDITS_ATTEMPTED" NUMBER(5,2),
	"WARNING" NUMBER(2,0),
	"ADMN_CAMP_ID" NUMBER(2,0),
	"CURR_CAMP_ID" NUMBER(3,0),
	"STU_PASSWORD" VARCHAR2(50),
	"STU_PWDHINT" VARCHAR2(50),
	"CREATED_BY" NUMBER(8,0),
	"CREATED_DATE" DATE DEFAULT sysdate,
	"CREDIT_EXEMPTED" NUMBER(5,2),
	"STU_SECTION_ID" NUMBER(4,0)
   ) ;
--------------------------------------------------------
--  DDL for Table STUDENT_QUALIFICATION
--------------------------------------------------------

  CREATE TABLE "FLEX2"."STUDENT_QUALIFICATION"
   (	"ARN" NUMBER(10,0),
	"DEGREE" NUMBER(2,0),
	"SPECIALIZATION" VARCHAR2(50),
	"PASSING_YEAR" VARCHAR2(5),
	"BOARD" VARCHAR2(100),
	"INSTITUTION" VARCHAR2(200),
	"TOTAL_SCORE" NUMBER(10,0),
	"OBTAINED_SCORE" NUMBER(10,0),
	"TOTAL_CGPA" NUMBER(10,0),
	"OBTAINED_CGPA" NUMBER(10,2),
	"PERCENTAGE" NUMBER(10,2),
	"CREATED_BY" NUMBER(8,0),
	"CREATED_ON" DATE,
	"CITY" NUMBER(5,0)
   ) ;
--------------------------------------------------------
--  DDL for Table STUDENT_REMARKS_HISTORY
--------------------------------------------------------

  CREATE TABLE "FLEX2"."STUDENT_REMARKS_HISTORY"
   (	"FORM" VARCHAR2(30),
	"REMARKS" VARCHAR2(30),
	"PRIORITY" NUMBER(1,0),
	"CREATED_BY" NUMBER(8,0),
	"CREATED_DATE" DATE DEFAULT sysdate,
	"SRH_ID" NUMBER(10,0),
	"REFERANCE" VARCHAR2(30),
	"ROLL_NO" NUMBER(12,0)
   ) ;
--------------------------------------------------------
--  DDL for Table STUDENT_SEMESTER
--------------------------------------------------------

  CREATE TABLE "FLEX2"."STUDENT_SEMESTER"
   (	"SEM_ID" NUMBER(8,0),
	"ROLL_NO" NUMBER(12,0),
	"CAMP_ID" NUMBER(3,0),
	"SGPA" NUMBER(4,2),
	"CGPA" NUMBER(4,2),
	"CREDITS_EARNED" NUMBER(5,2),
	"CREDITS_ATTEMPTED" NUMBER(5,2),
	"WARNING" NUMBER(2,0),
	"CREATED_BY" NUMBER(4,0),
	"CREATED_DATE" DATE
   ) ;
--------------------------------------------------------
--  DDL for Table STUDY_PLAN_SEM
--------------------------------------------------------

  CREATE TABLE "FLEX2"."STUDY_PLAN_SEM"
   (	"BATCH_NO" NUMBER(8,0),
	"PROG_ID" NUMBER(4,0),
	"SR_NO" NUMBER(2,0),
	"SEM_ID" NUMBER(8,0),
	"CREATED_BY" NUMBER(8,0),
	"CREATED_DATE" DATE DEFAULT sysdate
   ) ;
--------------------------------------------------------
--  DDL for Table STUDY_TENT_PLAN
--------------------------------------------------------

  CREATE TABLE "FLEX2"."STUDY_TENT_PLAN"
   (	"BATCH_NO" NUMBER(8,0),
	"PROG_ID" NUMBER(4,0),
	"SEM_ID" NUMBER(8,0),
	"SR_NO" NUMBER(2,0),
	"COURSE_ID" NUMBER(4,0),
	"CRS_RELATION" CHAR(2)
   ) ;
--------------------------------------------------------
--  DDL for Table TEMP_ADDRESS_ISSUE
--------------------------------------------------------

  CREATE TABLE "FLEX2"."TEMP_ADDRESS_ISSUE"
   (	"ARN" NUMBER(10,0),
	"FULL_NAME" VARCHAR2(50),
	"SHORT_NAME" VARCHAR2(50),
	"DOB" DATE,
	"CNIC" VARCHAR2(20),
	"GENDER" CHAR(1),
	"MOBILE_NO" VARCHAR2(25),
	"EMAIL" VARCHAR2(50),
	"NATIONALITY" VARCHAR2(20),
	"CURR_ADDRESS" VARCHAR2(250),
	"CURR_PROVINCE" VARCHAR2(20),
	"CURR_TELNO" VARCHAR2(30),
	"PERM_ADDRESS" VARCHAR2(250),
	"PERM_PROVINCE" VARCHAR2(20),
	"PERM_TELNO" VARCHAR2(30),
	"MAIL_SENT_TO" CHAR(1),
	"NU_EMAIL" VARCHAR2(50),
	"BLOOD_GRP" CHAR(4),
	"CAMP_ID" NUMBER(3,0),
	"CREATED_BY" NUMBER(8,0),
	"CREATED_DATE" DATE,
	"CURR_COUNTRY" NUMBER(5,0),
	"PERM_COUNTRY" NUMBER(5,0),
	"CURR_CITY" NUMBER(5,0),
	"PERM_CITY" NUMBER(5,0)
   ) ;
--------------------------------------------------------
--  DDL for Table TEMP_NUTES_SEG_DATA
--------------------------------------------------------

  CREATE TABLE "FLEX2"."TEMP_NUTES_SEG_DATA"
   (	"YEAR" NUMBER(5,0),
	"TESTCENTER" NUMBER(2,0),
	"ARN" NUMBER(10,0),
	"ROLL_NO" NUMBER(12,0),
	"CAMP_ROLL" VARCHAR2(4000),
	"SHORT_NAME" VARCHAR2(50),
	"PROG_CODE" CHAR(10),
	"FIRST_REG_SEM" NUMBER,
	"LAST_REG_SEM" NUMBER,
	"STATUS" VARCHAR2(30),
	"NODE_NAME" VARCHAR2(500),
	"MATRIC_OBT" NUMBER,
	"MATRIC_TOT" NUMBER,
	"INTER_OBT" NUMBER,
	"INTER_TOT" NUMBER,
	"MARKS" NUMBER(8,3),
	"CGPA" NUMBER
   ) ;
--------------------------------------------------------
--  DDL for Table TEMP_REGLOG
--------------------------------------------------------

  CREATE TABLE "FLEX2"."TEMP_REGLOG"
   (	"ROLLNO" NUMBER(12,0)
   ) ;
--------------------------------------------------------
--  DDL for Table TENT_GRADE
--------------------------------------------------------

  CREATE TABLE "FLEX2"."TENT_GRADE"
   (	"OFFER_ID" NUMBER(12,0),
	"PRIORITY" NUMBER(1,0),
	"IS_APPROVED" NUMBER(1,0),
	"IS_CHECKED" NUMBER(1,0),
	"TEACHER_COMMENTS" VARCHAR2(2000),
	"HOD_COMMENTS" VARCHAR2(2000),
	"GS_ID" NUMBER(1,0),
	"GRADING_FACTOR" NUMBER(5,2),
	"MIN_RANGE" NUMBER(2,0),
	"MAX_RANGE" NUMBER(2,0),
	"CORRECTION_GRADE" VARCHAR2(10),
	"DESCRIPTION" VARCHAR2(2000),
	"CLASS_AVG" NUMBER(3,0),
	"CLASS_STD" NUMBER(3,0),
	"SECTION_GROUP" VARCHAR2(1000),
	"SUBMITTED_BY" NUMBER(8,0),
	"SUBMITTED_ON" DATE,
	"MODIFIED_BY" NUMBER(8,0),
	"MODIFIED_ON" DATE
   ) ;
--------------------------------------------------------
--  DDL for Table TENT_GRADE_0114
--------------------------------------------------------

  CREATE TABLE "FLEX2"."TENT_GRADE_0114"
   (	"OFFER_ID" NUMBER(12,0),
	"PRIORITY" NUMBER(1,0),
	"IS_APPROVED" NUMBER(1,0),
	"IS_CHECKED" NUMBER(1,0),
	"TEACHER_COMMENTS" VARCHAR2(2000),
	"HOD_COMMENTS" VARCHAR2(2000),
	"GS_ID" NUMBER(1,0),
	"GRADING_FACTOR" NUMBER(5,2),
	"MIN_RANGE" NUMBER(2,0),
	"MAX_RANGE" NUMBER(2,0),
	"CORRECTION_GRADE" VARCHAR2(10),
	"DESCRIPTION" VARCHAR2(2000),
	"CLASS_AVG" NUMBER(3,0),
	"CLASS_STD" NUMBER(3,0),
	"SECTION_GROUP" VARCHAR2(1000),
	"SUBMITTED_BY" NUMBER(8,0),
	"SUBMITTED_ON" DATE,
	"MODIFIED_BY" NUMBER(8,0),
	"MODIFIED_ON" DATE
   ) ;
--------------------------------------------------------
--  DDL for Table TENT_GRADE_DELETED
--------------------------------------------------------

  CREATE TABLE "FLEX2"."TENT_GRADE_DELETED"
   (	"DEL_ID" NUMBER(8,0),
	"OFFER_ID" NUMBER(12,0),
	"PRIORITY" NUMBER(1,0),
	"IS_APPROVED" NUMBER(1,0),
	"IS_CHECKED" NUMBER(1,0),
	"TEACHER_COMMENTS" VARCHAR2(2000),
	"HOD_COMMENTS" VARCHAR2(2000),
	"GS_ID" NUMBER(1,0),
	"GRADING_FACTOR" NUMBER(5,2),
	"MIN_RANGE" NUMBER(2,0),
	"MAX_RANGE" NUMBER(2,0),
	"CORRECTION_GRADE" VARCHAR2(10),
	"DESCRIPTION" VARCHAR2(2000),
	"CLASS_AVG" NUMBER(3,0),
	"CLASS_STD" NUMBER(3,0),
	"SECTION_GROUP" VARCHAR2(1000),
	"SUBMITTED_BY" NUMBER(8,0),
	"SUBMITTED_ON" DATE,
	"MODIFIED_BY" NUMBER(8,0),
	"MODIFIED_ON" DATE
   ) ;
--------------------------------------------------------
--  DDL for Table TENT_GRADE_DETAIL
--------------------------------------------------------

  CREATE TABLE "FLEX2"."TENT_GRADE_DETAIL"
   (	"OFFER_ID" NUMBER(12,0),
	"ROLL_NO" NUMBER(12,0),
	"TENT_GRADE1" VARCHAR2(5),
	"TENT_GRADE2" VARCHAR2(5),
	"TENT_GRADE3" VARCHAR2(5),
	"MODIFIED_GRADE" VARCHAR2(5),
	"TENT_MARKS" NUMBER(5,2),
	"SUBMITTEDBY" NUMBER(8,0),
	"SUBMITTEDON" DATE,
	"MODIFIEDBY" NUMBER(8,0),
	"MODIFIEDON" DATE,
	"TGD_ID" NUMBER(8,0)
   ) ;
--------------------------------------------------------
--  DDL for Table TENT_GRADE_DETAIL_DELETED
--------------------------------------------------------

  CREATE TABLE "FLEX2"."TENT_GRADE_DETAIL_DELETED"
   (	"DEL_ID" NUMBER(8,0),
	"OFFER_ID" NUMBER(12,0),
	"ROLL_NO" NUMBER(12,0),
	"TENT_GRADE1" VARCHAR2(5),
	"TENT_GRADE2" VARCHAR2(5),
	"TENT_GRADE3" VARCHAR2(5),
	"MODIFIED_GRADE" VARCHAR2(5),
	"TENT_MARKS" NUMBER(5,2),
	"SUBMITTEDBY" NUMBER(8,0),
	"SUBMITTEDON" DATE,
	"MODIFIEDBY" NUMBER(8,0),
	"MODIFIEDON" DATE,
	"TGD_ID" NUMBER(8,0)
   ) ;
--------------------------------------------------------
--  DDL for Table TENT_GRADE_MISSINGSESSIONAL
--------------------------------------------------------

  CREATE TABLE "FLEX2"."TENT_GRADE_MISSINGSESSIONAL"
   (	"OFFER_ID" NUMBER(12,0),
	"ROLL_NO" NUMBER(12,0),
	"MISSING_SESSIONAL" NUMBER(2,0),
	"CREATED_BY" NUMBER(8,0),
	"CREATED_ON" DATE
   ) ;
--------------------------------------------------------
--  DDL for Table TT_STD_REGISTRATION
--------------------------------------------------------

  CREATE TABLE "FLEX2"."TT_STD_REGISTRATION"
   (	"COURSE_ID" NUMBER(4,0),
	"COURSE_CODE" VARCHAR2(8),
	"COURSE_TITLE" VARCHAR2(60),
	"EQUIVALENCE" NUMBER(4,0),
	"CREDIT_HRS" NUMBER(4,2),
	"MIN_CREDIT_HRS" NUMBER(4,2),
	"RELATION_ID" VARCHAR2(2),
	"OFFERS" VARCHAR2(200),
	"REMARKS" VARCHAR2(200)
   ) ;
--------------------------------------------------------
--  DDL for Table TT_V_COLLECTION
--------------------------------------------------------

  CREATE GLOBAL TEMPORARY TABLE "FLEX2"."TT_V_COLLECTION"
   (	"PAYMENTDATE" VARCHAR2(200),
	"AMOUNT" NUMBER(10,0)
   ) ON COMMIT DELETE ROWS ;
--------------------------------------------------------
--  DDL for Table TT_V_INSTALL
--------------------------------------------------------

  CREATE GLOBAL TEMPORARY TABLE "FLEX2"."TT_V_INSTALL"
   (	"CAMPUSID" VARCHAR2(10),
	"ROLLNO" VARCHAR2(30),
	"SEMID" VARCHAR2(30),
	"INSTALLMENTNUMBER" NUMBER(10,0),
	"DUEDATE" DATE,
	"AMOUNT" NUMBER(8,2),
	"PAYMENTDATE" DATE,
	"PAIDAMOUNT" NUMBER(18,0)
   ) ON COMMIT DELETE ROWS ;
--------------------------------------------------------
--  DDL for Table TT_V_SEMFEE
--------------------------------------------------------

  CREATE GLOBAL TEMPORARY TABLE "FLEX2"."TT_V_SEMFEE"
   (	"CAMPUSID" VARCHAR2(10),
	"ROLLNO" VARCHAR2(30),
	"STATUS" VARCHAR2(30),
	"SEMID" VARCHAR2(30),
	"SPONSHEAD" VARCHAR2(30),
	"SPONSOR" VARCHAR2(500),
	"ARREAR" NUMBER(38,2),
	"DUE" NUMBER(38,2),
	"NET" NUMBER(38,2),
	"PAYMENT" NUMBER(38,2),
	"ARREARPAYMENT" NUMBER(38,2),
	"CURRPAYMENT" NUMBER(38,2),
	"BALANCE" NUMBER(38,2),
	"ARRBAL" NUMBER(38,2),
	"CURRBAL" NUMBER(38,2),
	"INSTAMOUNT" NUMBER(38,2),
	"DEFAMOUNT" NUMBER(38,2),
	"SPONSAMOUNT" NUMBER(38,2),
	"COURSES" NUMBER(10,0)
   ) ON COMMIT DELETE ROWS ;
--------------------------------------------------------
--  DDL for Table TT_V_SEMFEE_10
--------------------------------------------------------

  CREATE GLOBAL TEMPORARY TABLE "FLEX2"."TT_V_SEMFEE_10"
   (	"CAMPUSID" VARCHAR2(10),
	"ROLLNO" VARCHAR2(30),
	"SEMID" VARCHAR2(30),
	"SPONSHEAD" VARCHAR2(30),
	"SPONSOR" VARCHAR2(500),
	"ARREAR" NUMBER(38,2),
	"DUE" NUMBER(38,2),
	"NET" NUMBER(38,2),
	"PAYMENT" NUMBER(38,2),
	"ARREARPAYMENT" NUMBER(38,2),
	"CURRPAYMENT" NUMBER(38,2),
	"BALANCE" NUMBER(38,2),
	"INSTAMOUNT" NUMBER(38,2),
	"DEFAMOUNT" NUMBER(38,2),
	"SPONSAMOUNT" NUMBER(38,2),
	"COURSES" NUMBER(10,0)
   ) ON COMMIT DELETE ROWS ;
--------------------------------------------------------
--  DDL for Table TT_V_SEMFEE_2
--------------------------------------------------------

  CREATE GLOBAL TEMPORARY TABLE "FLEX2"."TT_V_SEMFEE_2"
   (	"CAMPUSID" VARCHAR2(10),
	"ROLLNO" VARCHAR2(30),
	"STATUS" VARCHAR2(30),
	"SEMID" VARCHAR2(30),
	"SPONSHEAD" VARCHAR2(30),
	"SPONSOR" VARCHAR2(500),
	"ARREAR" NUMBER(38,2),
	"DUE" NUMBER(38,2),
	"NET" NUMBER(38,2),
	"PAYMENT" NUMBER(38,2),
	"ARREARPAYMENT" NUMBER(38,2),
	"CURRPAYMENT" NUMBER(38,2),
	"BALANCE" NUMBER(38,2),
	"ARRBAL" NUMBER(38,2),
	"CURRBAL" NUMBER(38,2),
	"INSTAMOUNT" NUMBER(38,2),
	"DEFAMOUNT" NUMBER(38,2),
	"SPONSAMOUNT" NUMBER(38,2),
	"COURSES" NUMBER(10,0)
   ) ON COMMIT DELETE ROWS ;
--------------------------------------------------------
--  DDL for Table TT_V_SEMFEE_3
--------------------------------------------------------

  CREATE GLOBAL TEMPORARY TABLE "FLEX2"."TT_V_SEMFEE_3"
   (	"CAMPUSID" VARCHAR2(10),
	"ROLLNO" VARCHAR2(30),
	"STATUS" VARCHAR2(30),
	"SEMID" VARCHAR2(30),
	"SPONSHEAD" VARCHAR2(30),
	"SPONSOR" VARCHAR2(500),
	"ARREAR" NUMBER(38,2),
	"DUE" NUMBER(38,2),
	"NET" NUMBER(38,2),
	"PAYMENT" NUMBER(38,2),
	"ARREARPAYMENT" NUMBER(38,2),
	"CURRPAYMENT" NUMBER(38,2),
	"BALANCE" NUMBER(38,2),
	"ARRBAL" NUMBER(38,2),
	"CURRBAL" NUMBER(38,2),
	"INSTAMOUNT" NUMBER(38,2),
	"DEFAMOUNT" NUMBER(38,2),
	"SPONSAMOUNT" NUMBER(38,2),
	"COURSES" NUMBER(10,0)
   ) ON COMMIT DELETE ROWS ;
--------------------------------------------------------
--  DDL for Table TT_V_SEMFEE_4
--------------------------------------------------------

  CREATE GLOBAL TEMPORARY TABLE "FLEX2"."TT_V_SEMFEE_4"
   (	"CAMPUSID" VARCHAR2(10),
	"ROLLNO" VARCHAR2(30),
	"STATUS" VARCHAR2(30),
	"SEMID" VARCHAR2(30),
	"SPONSHEAD" VARCHAR2(30),
	"SPONSOR" VARCHAR2(500),
	"ARREAR" NUMBER(38,2),
	"DUE" NUMBER(38,2),
	"NET" NUMBER(38,2),
	"PYBLADJMNT" NUMBER(18,0),
	"PAYMENT" NUMBER(38,2),
	"ARREARPAYMENT" NUMBER(38,2),
	"CURRPAYMENT" NUMBER(38,2),
	"BALANCE" NUMBER(38,2),
	"ARRBAL" NUMBER(38,2),
	"CURRBAL" NUMBER(38,2),
	"INSTAMOUNT" NUMBER(38,2),
	"DEFAMOUNT" NUMBER(38,2),
	"SPONSAMOUNT" NUMBER(38,2),
	"COURSES" NUMBER(10,0)
   ) ON COMMIT DELETE ROWS ;
--------------------------------------------------------
--  DDL for Table TT_V_SEMFEE_5
--------------------------------------------------------

  CREATE GLOBAL TEMPORARY TABLE "FLEX2"."TT_V_SEMFEE_5"
   (	"CAMPUSID" VARCHAR2(10),
	"ROLLNO" VARCHAR2(30),
	"STATUS" VARCHAR2(30),
	"SEMID" VARCHAR2(30),
	"SPONSHEAD" VARCHAR2(30),
	"SPONSOR" VARCHAR2(500),
	"ARREAR" NUMBER(38,2),
	"DUE" NUMBER(38,2),
	"NET" NUMBER(38,2),
	"PAYMENT" NUMBER(38,2),
	"ARREARPAYMENT" NUMBER(38,2),
	"CURRPAYMENT" NUMBER(38,2),
	"BALANCE" NUMBER(38,2),
	"ARRBAL" NUMBER(38,2),
	"CURRBAL" NUMBER(38,2),
	"INSTAMOUNT" NUMBER(38,2),
	"DEFAMOUNT" NUMBER(38,2),
	"SPONSAMOUNT" NUMBER(38,2),
	"COURSES" NUMBER(10,0)
   ) ON COMMIT DELETE ROWS ;
--------------------------------------------------------
--  DDL for Table TT_V_SEMFEE_6
--------------------------------------------------------

  CREATE GLOBAL TEMPORARY TABLE "FLEX2"."TT_V_SEMFEE_6"
   (	"CAMPUSID" VARCHAR2(10),
	"ROLLNO" VARCHAR2(30),
	"STATUS" VARCHAR2(30),
	"SEMID" VARCHAR2(30),
	"SPONSHEAD" VARCHAR2(30),
	"SPONSOR" VARCHAR2(500),
	"ARREAR" NUMBER(38,2),
	"DUE" NUMBER(38,2),
	"NET" NUMBER(38,2),
	"PYBLADJMNT" NUMBER(18,0),
	"PAYMENT" NUMBER(38,2),
	"ARREARPAYMENT" NUMBER(38,2),
	"CURRPAYMENT" NUMBER(38,2),
	"BALANCE" NUMBER(38,2),
	"ARRBAL" NUMBER(38,2),
	"CURRBAL" NUMBER(38,2),
	"INSTAMOUNT" NUMBER(38,2),
	"DEFAMOUNT" NUMBER(38,2),
	"SPONSAMOUNT" NUMBER(38,2),
	"COURSES" NUMBER(10,0)
   ) ON COMMIT DELETE ROWS ;
--------------------------------------------------------
--  DDL for Table TT_V_SEMFEE_7
--------------------------------------------------------

  CREATE GLOBAL TEMPORARY TABLE "FLEX2"."TT_V_SEMFEE_7"
   (	"CAMPUSID" VARCHAR2(10),
	"ROLLNO" VARCHAR2(30),
	"STATUS" VARCHAR2(30),
	"SEMID" VARCHAR2(30),
	"SPONSHEAD" VARCHAR2(30),
	"SPONSOR" VARCHAR2(500),
	"ARREAR" NUMBER(38,2),
	"DUE" NUMBER(38,2),
	"NET" NUMBER(38,2),
	"PYBLADJMNT" NUMBER(18,0),
	"PAYMENT" NUMBER(38,2),
	"ARREARPAYMENT" NUMBER(38,2),
	"CURRPAYMENT" NUMBER(38,2),
	"BALANCE" NUMBER(38,2),
	"ARRBAL" NUMBER(38,2),
	"CURRBAL" NUMBER(38,2),
	"INSTAMOUNT" NUMBER(38,2),
	"DEFAMOUNT" NUMBER(38,2),
	"SPONSAMOUNT" NUMBER(38,2),
	"COURSES" NUMBER(10,0)
   ) ON COMMIT DELETE ROWS ;
--------------------------------------------------------
--  DDL for Table TT_V_SEMFEE_8
--------------------------------------------------------

  CREATE GLOBAL TEMPORARY TABLE "FLEX2"."TT_V_SEMFEE_8"
   (	"CAMPUSID" VARCHAR2(10),
	"ROLLNO" VARCHAR2(30),
	"SEMID" VARCHAR2(30),
	"TYPE" VARCHAR2(30),
	"SPONSOR" VARCHAR2(500),
	"ARREAR" NUMBER(38,2),
	"DUE" NUMBER(38,2),
	"NET" NUMBER(38,2),
	"PAYMENT" NUMBER(38,2),
	"BALANCE" NUMBER(38,2),
	"SPONSAMOUNT" NUMBER(38,2),
	"COURSES" NUMBER(10,0)
   ) ON COMMIT DELETE ROWS ;
--------------------------------------------------------
--  DDL for Table TT_V_SEMFEE_9
--------------------------------------------------------

  CREATE GLOBAL TEMPORARY TABLE "FLEX2"."TT_V_SEMFEE_9"
   (	"CAMPUSID" VARCHAR2(10),
	"ROLLNO" VARCHAR2(30),
	"SEMID" VARCHAR2(30),
	"SPONSHEAD" VARCHAR2(30),
	"SPONSOR" VARCHAR2(500),
	"ARREAR" NUMBER(38,2),
	"DUE" NUMBER(38,2),
	"NET" NUMBER(38,2),
	"PAYMENT" NUMBER(38,2),
	"BALANCE" NUMBER(38,2),
	"SPONSAMOUNT" NUMBER(38,2),
	"COURSES" NUMBER(10,0)
   ) ON COMMIT DELETE ROWS ;
--------------------------------------------------------
--  DDL for Table TT_V_T
--------------------------------------------------------

  CREATE GLOBAL TEMPORARY TABLE "FLEX2"."TT_V_T"
   (	"ROLLNO" VARCHAR2(50),
	"TITLE" VARCHAR2(250),
	"COLLECTION" NUMBER(18,0)
   ) ON COMMIT DELETE ROWS ;
--------------------------------------------------------
--  DDL for Table TT_V_T_2
--------------------------------------------------------

  CREATE GLOBAL TEMPORARY TABLE "FLEX2"."TT_V_T_2"
   (	"CAMPUSID" NUMBER(6,0),
	"SCROLLDETAILID" NUMBER(14,0),
	"LEDGERID" NUMBER(14,0),
	"SUBHEADID" NUMBER(10,0),
	"AMOUNT" NUMBER(18,0),
	"ENTEREDBY" DATE,
	"ENTRYDATE" DATE,
	"STATUS" NUMBER(2,0)
   ) ON COMMIT DELETE ROWS ;
--------------------------------------------------------
--  DDL for Table TT_V_T_3
--------------------------------------------------------

  CREATE GLOBAL TEMPORARY TABLE "FLEX2"."TT_V_T_3"
   (	"SCROLLDETAILID" NUMBER(10,0),
	"SUBHEADID" NUMBER(10,0),
	"AMOUNT" NUMBER
   ) ON COMMIT DELETE ROWS ;
--------------------------------------------------------
--  DDL for Table TT_V_WEEKTABLE
--------------------------------------------------------

  CREATE GLOBAL TEMPORARY TABLE "FLEX2"."TT_V_WEEKTABLE"
   (	"WEEKNO" NUMBER(10,0),
	"WEEKSTART" VARCHAR2(200),
	"WEEKEND" VARCHAR2(200)
   ) ON COMMIT DELETE ROWS ;
--------------------------------------------------------
--  Constraints for Table ACTION_LOG
--------------------------------------------------------

  ALTER TABLE "FLEX2"."ACTION_LOG" ADD CONSTRAINT "PK_ACTION_LOG" PRIMARY KEY ("LOG_ID") ENABLE;

--------------------------------------------------------
--  Constraints for Table ADM_OFFER_SUMMARY
--------------------------------------------------------

  ALTER TABLE "FLEX2"."ADM_OFFER_SUMMARY" MODIFY ("CAMP_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."ADM_OFFER_SUMMARY" MODIFY ("CAMP_CODE" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."ADM_OFFER_SUMMARY" MODIFY ("PROG_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."ADM_OFFER_SUMMARY" MODIFY ("PROG_CODE" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."ADM_OFFER_SUMMARY" MODIFY ("NU_APPLS" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."ADM_OFFER_SUMMARY" MODIFY ("NTS_APPLS" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."ADM_OFFER_SUMMARY" MODIFY ("NTS_OFFER" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."ADM_OFFER_SUMMARY" MODIFY ("NU_OFFER" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table APPMENU
--------------------------------------------------------

  ALTER TABLE "FLEX2"."APPMENU" ADD CONSTRAINT "PK_MENU_MENUID" PRIMARY KEY ("MENUID") ENABLE;

  ALTER TABLE "FLEX2"."APPMENU" MODIFY ("TITLE" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."APPMENU" MODIFY ("PAGEHEADING" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table APPROLE
--------------------------------------------------------

  ALTER TABLE "FLEX2"."APPROLE" ADD CONSTRAINT "PK_ROLEID_ID" PRIMARY KEY ("ROLEID") ENABLE;

  ALTER TABLE "FLEX2"."APPROLE" MODIFY ("ROLEID" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table APPROLEDETAIL
--------------------------------------------------------

  ALTER TABLE "FLEX2"."APPROLEDETAIL" ADD CONSTRAINT "PK_RM_ID_ID" PRIMARY KEY ("RM_ID") ENABLE;

  ALTER TABLE "FLEX2"."APPROLEDETAIL" MODIFY ("RM_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."APPROLEDETAIL" MODIFY ("ROLEID" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table APPUSER
--------------------------------------------------------

  ALTER TABLE "FLEX2"."APPUSER" ADD CONSTRAINT "PK_APPUSER_ID" PRIMARY KEY ("USERID") ENABLE;

  ALTER TABLE "FLEX2"."APPUSER" MODIFY ("USERID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."APPUSER" MODIFY ("USERNAME" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."APPUSER" MODIFY ("USERPASSWORD" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."APPUSER" ADD CONSTRAINT "UK_USERNAME" UNIQUE ("USERNAME") ENABLE;
--------------------------------------------------------
--  Constraints for Table APPUSERBOOKMARK
--------------------------------------------------------

   ALTER TABLE "FLEX2"."APPUSERBOOKMARK" ADD CONSTRAINT "PK_UM_ID_ID" PRIMARY KEY ("UM_ID") ENABLE;

  ALTER TABLE "FLEX2"."APPUSERBOOKMARK" MODIFY ("UM_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."APPUSERBOOKMARK" MODIFY ("USERID" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table APPUSERCAMPUS
--------------------------------------------------------

   ALTER TABLE "FLEX2"."APPUSERCAMPUS" ADD CONSTRAINT "PK_UC_ID_ID" PRIMARY KEY ("UC_ID") ENABLE;

  ALTER TABLE "FLEX2"."APPUSERCAMPUS" MODIFY ("UC_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."APPUSERCAMPUS" MODIFY ("USERID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."APPUSERCAMPUS" MODIFY ("CAMP_ID" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table APPUSERDEPARTMENT
--------------------------------------------------------

  ALTER TABLE "FLEX2"."APPUSERDEPARTMENT" ADD CONSTRAINT "PK_UD_ID_ID" PRIMARY KEY ("UD_ID") ENABLE;

  ALTER TABLE "FLEX2"."APPUSERDEPARTMENT" MODIFY ("UD_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."APPUSERDEPARTMENT" MODIFY ("USERID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."APPUSERDEPARTMENT" MODIFY ("DEPT_ID" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table APPUSERROLE
--------------------------------------------------------

   ALTER TABLE "FLEX2"."APPUSERROLE" ADD CONSTRAINT "PK_UR_ID_ID" PRIMARY KEY ("UR_ID") ENABLE;

  ALTER TABLE "FLEX2"."APPUSERROLE" MODIFY ("UR_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."APPUSERROLE" MODIFY ("ROLEID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."APPUSERROLE" MODIFY ("USERID" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table BATCH
--------------------------------------------------------

  ALTER TABLE "FLEX2"."BATCH" ADD CONSTRAINT "PK_BATCH" PRIMARY KEY ("BATCH_NO") ENABLE;

  ALTER TABLE "FLEX2"."BATCH" MODIFY ("BATCH_NO" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."BATCH" MODIFY ("TITLE" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."BATCH" MODIFY ("START_DATE" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."BATCH" ADD CONSTRAINT "UK_BATCH_TITLE" UNIQUE ("TITLE") ENABLE;
--------------------------------------------------------
--  Constraints for Table BATCH_PROGRAM
--------------------------------------------------------

 ALTER TABLE "FLEX2"."BATCH_PROGRAM" ADD CONSTRAINT "PK_BATCH_PROGRAM" PRIMARY KEY ("BATCH_NO", "PROG_ID") ENABLE;

  ALTER TABLE "FLEX2"."BATCH_PROGRAM" MODIFY ("BATCH_NO" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."BATCH_PROGRAM" MODIFY ("PROG_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."BATCH_PROGRAM" MODIFY ("MIN_CR_HRS" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."BATCH_PROGRAM" MODIFY ("MIN_PASS_PNTS" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."BATCH_PROGRAM" MODIFY ("MAX_RPT_PNTS" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."BATCH_PROGRAM" MODIFY ("MIN_CGPA" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."BATCH_PROGRAM" MODIFY ("AVG_COURSE" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."BATCH_PROGRAM" MODIFY ("AVG_CREDIT" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."BATCH_PROGRAM" MODIFY ("CREATED_BY" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table BATCH_SECTION
--------------------------------------------------------

   ALTER TABLE "FLEX2"."BATCH_SECTION" ADD CONSTRAINT "PK_BATCH_SECTION" PRIMARY KEY ("CAMP_ID", "BATCH_NO", "PROG_ID", "SECTION_ID") ENABLE;

  ALTER TABLE "FLEX2"."BATCH_SECTION" MODIFY ("CAMP_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."BATCH_SECTION" MODIFY ("BATCH_NO" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."BATCH_SECTION" MODIFY ("PROG_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."BATCH_SECTION" MODIFY ("SECTION_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."BATCH_SECTION" MODIFY ("SHIFT_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."BATCH_SECTION" MODIFY ("CREATED_BY" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table CAMPUS
--------------------------------------------------------

  ALTER TABLE "FLEX2"."CAMPUS" ADD CONSTRAINT "CAMP_ID_PK" PRIMARY KEY ("CAMP_ID") ENABLE;

  ALTER TABLE "FLEX2"."CAMPUS" MODIFY ("CAMP_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."CAMPUS" MODIFY ("NAME" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."CAMPUS" MODIFY ("ABBR" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."CAMPUS" MODIFY ("ADDRESS" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."CAMPUS" MODIFY ("CITY" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."CAMPUS" MODIFY ("TELNO1" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table CAMPUS_ACTIVITY
--------------------------------------------------------

  ALTER TABLE "FLEX2"."CAMPUS_ACTIVITY" ADD CONSTRAINT "PK_CAID" PRIMARY KEY ("CAMP_ACT_ID") ENABLE;
--------------------------------------------------------
--  Constraints for Table CAMPUS_BATCH
--------------------------------------------------------

  ALTER TABLE "FLEX2"."CAMPUS_BATCH" ADD CONSTRAINT "PK_CAMPUS_BATCH" PRIMARY KEY ("CAMP_ID", "BATCH_NO") ENABLE;

  ALTER TABLE "FLEX2"."CAMPUS_BATCH" MODIFY ("CAMP_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."CAMPUS_BATCH" MODIFY ("BATCH_NO" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table CAMPUS_DEPT
--------------------------------------------------------

  ALTER TABLE "FLEX2"."CAMPUS_DEPT" MODIFY ("CAMP_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."CAMPUS_DEPT" MODIFY ("SCH_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."CAMPUS_DEPT" MODIFY ("DEPT_ID" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table CAMPUS_DEPT_PROGRAM
--------------------------------------------------------

  ALTER TABLE "FLEX2"."CAMPUS_DEPT_PROGRAM" MODIFY ("CAMP_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."CAMPUS_DEPT_PROGRAM" MODIFY ("PROG_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."CAMPUS_DEPT_PROGRAM" MODIFY ("DEPT_ID" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table CAMPUS_PREFERENCE
--------------------------------------------------------

  ALTER TABLE "FLEX2"."CAMPUS_PREFERENCE" ADD CONSTRAINT "PK_CP_ARN" PRIMARY KEY ("ARN", "CAMP_ID") ENABLE;

  ALTER TABLE "FLEX2"."CAMPUS_PREFERENCE" MODIFY ("CAMP_ID" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table CAMPUS_PROGRAM
--------------------------------------------------------

  ALTER TABLE "FLEX2"."CAMPUS_PROGRAM" ADD CONSTRAINT "PK_CAMPUS_PROGRAM" PRIMARY KEY ("CAMP_ID", "PROG_ID") ENABLE;

  ALTER TABLE "FLEX2"."CAMPUS_PROGRAM" MODIFY ("CAMP_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."CAMPUS_PROGRAM" MODIFY ("PROG_ID" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table CAMP_SEMESTER
--------------------------------------------------------

  ALTER TABLE "FLEX2"."CAMP_SEMESTER" ADD CONSTRAINT "PK_CAMP_SEMESTER" PRIMARY KEY ("CAMP_ID", "SEM_ID") ENABLE;

  ALTER TABLE "FLEX2"."CAMP_SEMESTER" MODIFY ("CAMP_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."CAMP_SEMESTER" MODIFY ("SEM_ID" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table CITY
--------------------------------------------------------

  ALTER TABLE "FLEX2"."CITY" ADD CONSTRAINT "PK_CITYID" PRIMARY KEY ("CITY_ID") ENABLE;
--------------------------------------------------------
--  Constraints for Table CNIC_LOG
--------------------------------------------------------

  ALTER TABLE "FLEX2"."CNIC_LOG" ADD CONSTRAINT "CNIC_LOG_PK" PRIMARY KEY ("ID") ENABLE;
--------------------------------------------------------
--  Constraints for Table COUNTRY
--------------------------------------------------------

  ALTER TABLE "FLEX2"."COUNTRY" ADD CONSTRAINT "PK_COUNTRYID" PRIMARY KEY ("COUNTRY_ID") ENABLE;
--------------------------------------------------------
--  Constraints for Table COURSE
--------------------------------------------------------

  ALTER TABLE "FLEX2"."COURSE" ADD CONSTRAINT "PK_COURSE" PRIMARY KEY ("COURSE_ID") ENABLE;

  ALTER TABLE "FLEX2"."COURSE" MODIFY ("COURSE_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."COURSE" MODIFY ("CODE" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."COURSE" MODIFY ("TITLE" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."COURSE" MODIFY ("SHORT_TITLE" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."COURSE" MODIFY ("CREDIT_HRS" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."COURSE" ADD CONSTRAINT "UK_COURSE_CODE" UNIQUE ("CODE") ENABLE;
--------------------------------------------------------
--  Constraints for Table COURSE_COREQUISITE
--------------------------------------------------------

  ALTER TABLE "FLEX2"."COURSE_COREQUISITE" ADD CONSTRAINT "PK_COREQ_CID" PRIMARY KEY ("COURSE_ID") ENABLE;

  ALTER TABLE "FLEX2"."COURSE_COREQUISITE" MODIFY ("COURSE_ID" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table COURSE_EVALUATION
--------------------------------------------------------

  ALTER TABLE "FLEX2"."COURSE_EVALUATION" ADD CONSTRAINT "PK_COURSE_EVALUATION" PRIMARY KEY ("EVAL_ID") ENABLE;

  ALTER TABLE "FLEX2"."COURSE_EVALUATION" MODIFY ("OFFER_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."COURSE_EVALUATION" ADD CONSTRAINT "UK_CRSEVAL_IDOFFEREVALNO" UNIQUE ("OFFER_ID", "EVAL_TYPE_ID", "EVAL_NO") ENABLE;
--------------------------------------------------------
--  Constraints for Table COURSE_EVALUATION_DETAIL
--------------------------------------------------------

  ALTER TABLE "FLEX2"."COURSE_EVALUATION_DETAIL" ADD CONSTRAINT "PK_COURSE_EVALUATION_DETAIL" PRIMARY KEY ("EVAL_ID", "ROLL_NO") ENABLE;

  ALTER TABLE "FLEX2"."COURSE_EVALUATION_DETAIL" MODIFY ("EVAL_ID" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table COURSE_EVAL_SCHEME
--------------------------------------------------------

  ALTER TABLE "FLEX2"."COURSE_EVAL_SCHEME" ADD CONSTRAINT "PK_CES_CRSEVALSCM" PRIMARY KEY ("EVAL_TYPE_ID", "CAMP_ID", "OFFER_ID") ENABLE;
--------------------------------------------------------
--  Constraints for Table COURSE_OFFER
--------------------------------------------------------

  ALTER TABLE "FLEX2"."COURSE_OFFER" ADD CONSTRAINT "PK_COURSE_OFFER" PRIMARY KEY ("OFFER_ID") ENABLE;

  ALTER TABLE "FLEX2"."COURSE_OFFER" MODIFY ("OFFER_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."COURSE_OFFER" MODIFY ("CAMP_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."COURSE_OFFER" MODIFY ("SEM_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."COURSE_OFFER" MODIFY ("COURSE_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."COURSE_OFFER" MODIFY ("SECTION_ID" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table COURSE_OFFER_DETAIL
--------------------------------------------------------

  ALTER TABLE "FLEX2"."COURSE_OFFER_DETAIL" ADD CONSTRAINT "PK_COURSE_OFFER_DETAIL" PRIMARY KEY ("OFFER_ID", "PROG_ID", "BATCH_NO", "BATCH_SECTION") ENABLE;

  ALTER TABLE "FLEX2"."COURSE_OFFER_DETAIL" MODIFY ("OFFER_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."COURSE_OFFER_DETAIL" MODIFY ("PROG_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."COURSE_OFFER_DETAIL" MODIFY ("BATCH_NO" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."COURSE_OFFER_DETAIL" MODIFY ("BATCH_SECTION" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."COURSE_OFFER_DETAIL" MODIFY ("CAMP_ID" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table COURSE_PREREQ
--------------------------------------------------------

  ALTER TABLE "FLEX2"."COURSE_PREREQ" ADD CONSTRAINT "PK_COURSE_PREREQ" PRIMARY KEY ("COURSE_ID", "COURSE_PREREQ") ENABLE;

  ALTER TABLE "FLEX2"."COURSE_PREREQ" MODIFY ("COURSE_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."COURSE_PREREQ" MODIFY ("COURSE_PREREQ" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."COURSE_PREREQ" MODIFY ("SCH_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."COURSE_PREREQ" MODIFY ("CREATED_BY" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table COURSE_REGISTRATION
--------------------------------------------------------

  ALTER TABLE "FLEX2"."COURSE_REGISTRATION" ADD CONSTRAINT "PK_COURSE_REGISTRATION" PRIMARY KEY ("OFFER_ID", "ROLL_NO") ENABLE;

  ALTER TABLE "FLEX2"."COURSE_REGISTRATION" ADD CONSTRAINT "UK_CRSREG_CAMPCRSSEMROLL" UNIQUE ("ROLL_NO", "CAMP_ID", "SEM_ID", "COURSE_ID") ENABLE;


--------------------------------------------------------
--  Constraints for Table DEPARTMENT
--------------------------------------------------------

  ALTER TABLE "FLEX2"."DEPARTMENT" ADD CONSTRAINT "PK_DEPARTMENT" PRIMARY KEY ("DEPT_ID") ENABLE;

  ALTER TABLE "FLEX2"."DEPARTMENT" MODIFY ("DEPT_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."DEPARTMENT" MODIFY ("TITLE" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."DEPARTMENT" MODIFY ("CODE" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."DEPARTMENT" MODIFY ("DEPT_TYPE_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."DEPARTMENT" ADD CONSTRAINT "UK_DEPT_CODE" UNIQUE ("CODE") ENABLE;
--------------------------------------------------------
--  Constraints for Table DEPT_PROGRAM
--------------------------------------------------------

  ALTER TABLE "FLEX2"."DEPT_PROGRAM" ADD CONSTRAINT "PK_DEPT_PROGRAM" PRIMARY KEY ("DP_ID") ENABLE;
--------------------------------------------------------
--  Constraints for Table DISCIPLINE_PREFERENCE
--------------------------------------------------------

  ALTER TABLE "FLEX2"."DISCIPLINE_PREFERENCE" ADD CONSTRAINT "PK_DP_ARN" PRIMARY KEY ("ARN", "PROG_ID") ENABLE;

  ALTER TABLE "FLEX2"."DISCIPLINE_PREFERENCE" MODIFY ("PROG_ID" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table DOCUMENT_VERIFICATION
--------------------------------------------------------

  ALTER TABLE "FLEX2"."DOCUMENT_VERIFICATION" ADD CONSTRAINT "PK_DV_ID" PRIMARY KEY ("ID") ENABLE;
--------------------------------------------------------
--  Constraints for Table DR$TEMP_ADDR_INDEX$I
--------------------------------------------------------

  ALTER TABLE "FLEX2"."DR$TEMP_ADDR_INDEX$I" MODIFY ("TOKEN_TEXT" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."DR$TEMP_ADDR_INDEX$I" MODIFY ("TOKEN_TYPE" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."DR$TEMP_ADDR_INDEX$I" MODIFY ("TOKEN_FIRST" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."DR$TEMP_ADDR_INDEX$I" MODIFY ("TOKEN_LAST" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."DR$TEMP_ADDR_INDEX$I" MODIFY ("TOKEN_COUNT" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table DR$TEMP_ADDR_INDEX$K
--------------------------------------------------------

  ALTER TABLE "FLEX2"."DR$TEMP_ADDR_INDEX$K" ADD PRIMARY KEY ("TEXTKEY") ENABLE;
--------------------------------------------------------
--  Constraints for Table DR$TEMP_ADDR_INDEX$N
--------------------------------------------------------

  ALTER TABLE "FLEX2"."DR$TEMP_ADDR_INDEX$N" MODIFY ("NLT_MARK" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."DR$TEMP_ADDR_INDEX$N" ADD PRIMARY KEY ("NLT_DOCID") ENABLE;

--------------------------------------------------------
--  Constraints for Table D_COURSE_EVALUATION
--------------------------------------------------------

  ALTER TABLE "FLEX2"."D_COURSE_EVALUATION" ADD CONSTRAINT "PK_D_COURSE_EVALUATION" PRIMARY KEY ("EVAL_TYPE_ID") ENABLE;
--------------------------------------------------------
--  Constraints for Table D_COURSE_LEVEL
--------------------------------------------------------

  ALTER TABLE "FLEX2"."D_COURSE_LEVEL" ADD CONSTRAINT "PK_D_COURSE_LEVEL" PRIMARY KEY ("LEVEL_ID") ENABLE;
--------------------------------------------------------
--  Constraints for Table D_COURSE_RELATION
--------------------------------------------------------

  ALTER TABLE "FLEX2"."D_COURSE_RELATION" ADD CONSTRAINT "PK_D_COURSE_RELATION" PRIMARY KEY ("RELATION_ID") ENABLE;
--------------------------------------------------------
--  Constraints for Table D_COURSE_TYPE
--------------------------------------------------------

  ALTER TABLE "FLEX2"."D_COURSE_TYPE" ADD CONSTRAINT "PK_D_COURSE_TYPE" PRIMARY KEY ("TYPE_ID") ENABLE;
--------------------------------------------------------
--  Constraints for Table D_DEGREE_TYPE
--------------------------------------------------------

  ALTER TABLE "FLEX2"."D_DEGREE_TYPE" ADD CONSTRAINT "D_DEGREE_TYPE_PK" PRIMARY KEY ("DT_ID") ENABLE;

  ALTER TABLE "FLEX2"."D_DEGREE_TYPE" MODIFY ("DT_ID" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table D_DEPT_EVAL_SCHEME
--------------------------------------------------------

  ALTER TABLE "FLEX2"."D_DEPT_EVAL_SCHEME" ADD CONSTRAINT "PK_DES_CAMPSCHEVAL" PRIMARY KEY ("CAMP_ID", "SCH_ID", "EVAL_TYPE_ID", "COURSE_TYPE") ENABLE;

  ALTER TABLE "FLEX2"."D_DEPT_EVAL_SCHEME" MODIFY ("CAMP_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."D_DEPT_EVAL_SCHEME" MODIFY ("SCH_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."D_DEPT_EVAL_SCHEME" MODIFY ("EVAL_TYPE_ID" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table D_DEPT_EVAL_SCHEME_
--------------------------------------------------------

  ALTER TABLE "FLEX2"."D_DEPT_EVAL_SCHEME_" MODIFY ("CAMP_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."D_DEPT_EVAL_SCHEME_" MODIFY ("SCH_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."D_DEPT_EVAL_SCHEME_" MODIFY ("EVAL_TYPE_ID" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table D_DEPT_EVAL_SCHEME_T
--------------------------------------------------------

  ALTER TABLE "FLEX2"."D_DEPT_EVAL_SCHEME_T" MODIFY ("CAMP_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."D_DEPT_EVAL_SCHEME_T" MODIFY ("SCH_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."D_DEPT_EVAL_SCHEME_T" MODIFY ("EVAL_TYPE_ID" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table D_DEPT_EVAL_TEMP
--------------------------------------------------------

  ALTER TABLE "FLEX2"."D_DEPT_EVAL_TEMP" MODIFY ("EVAL_TYPE_ID" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table D_DEPT_TYPE
--------------------------------------------------------

  ALTER TABLE "FLEX2"."D_DEPT_TYPE" ADD CONSTRAINT "PK_D_DEPT_TYPE" PRIMARY KEY ("TYPE_ID") ENABLE;

  ALTER TABLE "FLEX2"."D_DEPT_TYPE" MODIFY ("TYPE_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."D_DEPT_TYPE" MODIFY ("TITLE" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."D_DEPT_TYPE" MODIFY ("STATUS" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table D_EMP_DESIGNATION
--------------------------------------------------------

  ALTER TABLE "FLEX2"."D_EMP_DESIGNATION" ADD CONSTRAINT "PK_DEMPDESIGNATION" PRIMARY KEY ("DESIGNATION_ID") ENABLE;

  ALTER TABLE "FLEX2"."D_EMP_DESIGNATION" MODIFY ("DESIGNATION_ID" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table D_EMP_STATUS
--------------------------------------------------------

  ALTER TABLE "FLEX2"."D_EMP_STATUS" ADD CONSTRAINT "PK_DEMPSTATUS" PRIMARY KEY ("EMP_STATUS_ID") ENABLE;

  ALTER TABLE "FLEX2"."D_EMP_STATUS" MODIFY ("EMP_STATUS_ID" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table D_EMP_TYPE
--------------------------------------------------------

  ALTER TABLE "FLEX2"."D_EMP_TYPE" ADD CONSTRAINT "PK_DEMPTYPE" PRIMARY KEY ("EMP_TYPE_ID") ENABLE;

  ALTER TABLE "FLEX2"."D_EMP_TYPE" MODIFY ("EMP_TYPE_ID" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table D_FAMILY_RELATION
--------------------------------------------------------

  ALTER TABLE "FLEX2"."D_FAMILY_RELATION" ADD CONSTRAINT "PK_D_FAMILY_RELATION" PRIMARY KEY ("REL_TYPE_ID") ENABLE;
--------------------------------------------------------
--  Constraints for Table D_GENDER
--------------------------------------------------------

  ALTER TABLE "FLEX2"."D_GENDER" ADD CONSTRAINT "PK_GID" PRIMARY KEY ("GENDER_ID") ENABLE;
--------------------------------------------------------
--  Constraints for Table D_PHD_FUNDEDBY
--------------------------------------------------------

  ALTER TABLE "FLEX2"."D_PHD_FUNDEDBY" ADD CONSTRAINT "D_PHD_FUNDEDBY_PK" PRIMARY KEY ("FUNDED_ID") ENABLE;

  ALTER TABLE "FLEX2"."D_PHD_FUNDEDBY" MODIFY ("FUNDED_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."D_PHD_FUNDEDBY" MODIFY ("FUNDED_TEXT" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table D_PROGRAM_LEVEL
--------------------------------------------------------

  ALTER TABLE "FLEX2"."D_PROGRAM_LEVEL" ADD CONSTRAINT "PK_I_PROGRAM_LEVEL" PRIMARY KEY ("LEVEL_ID") ENABLE;
--------------------------------------------------------
--  Constraints for Table D_PROGRAM_SPECIALIZATION
--------------------------------------------------------

  ALTER TABLE "FLEX2"."D_PROGRAM_SPECIALIZATION" MODIFY ("STATUS" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table D_REG_STATUS
--------------------------------------------------------

  ALTER TABLE "FLEX2"."D_REG_STATUS" ADD CONSTRAINT "PK_D_REG_STATUS" PRIMARY KEY ("STATUS_ID") ENABLE;
--------------------------------------------------------
--  Constraints for Table D_SHIFT
--------------------------------------------------------

  ALTER TABLE "FLEX2"."D_SHIFT" ADD CONSTRAINT "PK_D_SHIFT" PRIMARY KEY ("SHIFT_ID") ENABLE;

  ALTER TABLE "FLEX2"."D_SHIFT" MODIFY ("SHIFT_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."D_SHIFT" MODIFY ("TITLE" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table D_STUDENT_REG_STATUS
--------------------------------------------------------

  ALTER TABLE "FLEX2"."D_STUDENT_REG_STATUS" ADD CONSTRAINT "PK_STUSTATUS" PRIMARY KEY ("STATUS_ID") ENABLE;
--------------------------------------------------------
--  Constraints for Table D_STUDENT_STATUS
--------------------------------------------------------

  ALTER TABLE "FLEX2"."D_STUDENT_STATUS" ADD CONSTRAINT "PK_STUREGSTATUS" PRIMARY KEY ("STATUS_ID") ENABLE;
--------------------------------------------------------
--  Constraints for Table D_STUDY_PLAN_ELECTIVE
--------------------------------------------------------

  ALTER TABLE "FLEX2"."D_STUDY_PLAN_ELECTIVE" ADD CONSTRAINT "PK_D_STUDY_PLAN_ELECTIVE" PRIMARY KEY ("ELECTIVE_ID") ENABLE;

  ALTER TABLE "FLEX2"."D_STUDY_PLAN_ELECTIVE" MODIFY ("ELECTIVE_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."D_STUDY_PLAN_ELECTIVE" MODIFY ("CODE" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."D_STUDY_PLAN_ELECTIVE" MODIFY ("TITLE" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."D_STUDY_PLAN_ELECTIVE" ADD CONSTRAINT "UK_SPE_CODE" UNIQUE ("CODE") ENABLE;
--------------------------------------------------------
--  Constraints for Table D_TEACHER_ACTIVITY
--------------------------------------------------------

  ALTER TABLE "FLEX2"."D_TEACHER_ACTIVITY" ADD CONSTRAINT "D_TEACHER_ACTIVITY_PK" PRIMARY KEY ("ACT_ID") ENABLE;

  ALTER TABLE "FLEX2"."D_TEACHER_ACTIVITY" MODIFY ("ACT_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."D_TEACHER_ACTIVITY" MODIFY ("ACT_DESC" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."D_TEACHER_ACTIVITY" MODIFY ("IS_DDL" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."D_TEACHER_ACTIVITY" MODIFY ("IS_ACTIVE" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table D_USER_TYPE
--------------------------------------------------------

  ALTER TABLE "FLEX2"."D_USER_TYPE" MODIFY ("USER_TYPE_ID" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table EMPLOYEE
--------------------------------------------------------

  ALTER TABLE "FLEX2"."EMPLOYEE" ADD CONSTRAINT "PK_EMPLOYEE" PRIMARY KEY ("EMP_ID") ENABLE;

  ALTER TABLE "FLEX2"."EMPLOYEE" MODIFY ("EMP_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."EMPLOYEE" MODIFY ("EMP_NAME" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."EMPLOYEE" MODIFY ("IS_EXAMINER" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table EXCEPTION_DETAIL
--------------------------------------------------------

  ALTER TABLE "FLEX2"."EXCEPTION_DETAIL" ADD CONSTRAINT "PK_EXPID" PRIMARY KEY ("EXP_ID") ENABLE;
--------------------------------------------------------
--  Constraints for Table EXEMPTED_COURSES
--------------------------------------------------------

  ALTER TABLE "FLEX2"."EXEMPTED_COURSES" ADD CONSTRAINT "PK_EXECOURSE" PRIMARY KEY ("ROLL_NO", "COURSE_ID") ENABLE;
--------------------------------------------------------
--  Constraints for Table FB_CGPA_BAND
--------------------------------------------------------

  ALTER TABLE "FLEX2"."FB_CGPA_BAND" ADD CONSTRAINT "PK_FBCGPABID" PRIMARY KEY ("CGPA_BAND_ID") ENABLE;
--------------------------------------------------------
--  Constraints for Table FB_PERFORMA
--------------------------------------------------------

  ALTER TABLE "FLEX2"."FB_PERFORMA" ADD CONSTRAINT "PK_PERFORMAID" PRIMARY KEY ("PID") ENABLE;
--------------------------------------------------------
--  Constraints for Table FB_QUESTIONS
--------------------------------------------------------

  ALTER TABLE "FLEX2"."FB_QUESTIONS" ADD CONSTRAINT "PK_QID" PRIMARY KEY ("QUESTION_ID") ENABLE;
--------------------------------------------------------
--  Constraints for Table FB_QUESTIONS_CATEGORY
--------------------------------------------------------

  ALTER TABLE "FLEX2"."FB_QUESTIONS_CATEGORY" ADD CONSTRAINT "PK_CID" PRIMARY KEY ("CATEGORY_ID") ENABLE;
--------------------------------------------------------
--  Constraints for Table FB_QUESTIONS_CHOICE
--------------------------------------------------------

  ALTER TABLE "FLEX2"."FB_QUESTIONS_CHOICE" ADD CONSTRAINT "PK_QIDCHID" PRIMARY KEY ("QUESTION_ID", "CHOICE_ID") ENABLE;
--------------------------------------------------------
--  Constraints for Table FB_STUDENTREPONSE_DETAIL
--------------------------------------------------------

  ALTER TABLE "FLEX2"."FB_STUDENTREPONSE_DETAIL" ADD CONSTRAINT "PK_FBSROQSFBNO" PRIMARY KEY ("OFFER_ID", "QUESTION_ID", "FEEDBACK_NO", "ROLL_NO") ENABLE;

  ALTER TABLE "FLEX2"."FB_STUDENTREPONSE_DETAIL" MODIFY ("ROLL_NO" NOT NULL ENABLE);

--------------------------------------------------------
--  Constraints for Table FB_STUDENTREPONSE_TEXT
--------------------------------------------------------

  ALTER TABLE "FLEX2"."FB_STUDENTREPONSE_TEXT" ADD CONSTRAINT "PK_FBSRTOQSFNO" PRIMARY KEY ("OFFER_ID", "QUESTION_ID", "FEEDBACK_NO", "ROLL_NO") ENABLE;

  ALTER TABLE "FLEX2"."FB_STUDENTREPONSE_TEXT" MODIFY ("ROLL_NO" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table FB_STUDENTREPONSE_TEXT_1031
--------------------------------------------------------

  ALTER TABLE "FLEX2"."FB_STUDENTREPONSE_TEXT_1031" MODIFY ("ROLL_NO" NOT NULL ENABLE);

--------------------------------------------------------
--  Constraints for Table FB_TEACHER_RESPONSE_TEXT
--------------------------------------------------------

  ALTER TABLE "FLEX2"."FB_TEACHER_RESPONSE_TEXT" MODIFY ("OFFER_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."FB_TEACHER_RESPONSE_TEXT" MODIFY ("QUESTION_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."FB_TEACHER_RESPONSE_TEXT" ADD PRIMARY KEY ("OFFER_ID", "QUESTION_ID") ENABLE;
--------------------------------------------------------
--  Constraints for Table FMBANKSCROLLDETAIL
--------------------------------------------------------

  ALTER TABLE "FLEX2"."FMBANKSCROLLDETAIL" ADD CONSTRAINT "PK_FMBSDID" PRIMARY KEY ("ID") ENABLE;
--------------------------------------------------------
--  Constraints for Table FMCHALLAN
--------------------------------------------------------

  ALTER TABLE "FLEX2"."FMCHALLAN" ADD CONSTRAINT "FMCHALLAN_PK" PRIMARY KEY ("CHALLANNO") ENABLE;
--------------------------------------------------------
--  Constraints for Table FMCHALLANDETAIL
--------------------------------------------------------

  ALTER TABLE "FLEX2"."FMCHALLANDETAIL" ADD CONSTRAINT "FMCHALLANDETAIL_PK" PRIMARY KEY ("CHALLANNO", "SUBHEADID") ENABLE;

--------------------------------------------------------
--  Constraints for Table FMDEFAULTEREXCEPTION
--------------------------------------------------------

  ALTER TABLE "FLEX2"."FMDEFAULTEREXCEPTION" ADD CONSTRAINT "FMDEFAULTEREXCEPTION_PK" PRIMARY KEY ("CAMPUSID", "ROLLNO", "SEMID") ENABLE;

--------------------------------------------------------
--  Constraints for Table FMFEEDATES
--------------------------------------------------------

  ALTER TABLE "FLEX2"."FMFEEDATES" ADD CONSTRAINT "PK_FMFEEDUEDATE" PRIMARY KEY ("CAMPUSID", "BATCHNO", "PROGRAMID", "SECTIONID", "SEMID") ENABLE;

  ALTER TABLE "FLEX2"."FMFEEDATES" MODIFY ("CAMPUSID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."FMFEEDATES" MODIFY ("SEMID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."FMFEEDATES" MODIFY ("BATCHNO" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."FMFEEDATES" MODIFY ("PROGRAMID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."FMFEEDATES" MODIFY ("SECTIONID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."FMFEEDATES" MODIFY ("CREATEDBY" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."FMFEEDATES" MODIFY ("CREATEDDATE" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."FMFEEDATES" MODIFY ("STATUS" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table FMFEERATES
--------------------------------------------------------

  ALTER TABLE "FLEX2"."FMFEERATES" ADD CONSTRAINT "PK_FMFRPBSSHID" PRIMARY KEY ("FEERATEID") ENABLE;
--------------------------------------------------------
--  Constraints for Table FMFEETYPE
--------------------------------------------------------

  ALTER TABLE "FLEX2"."FMFEETYPE" ADD CONSTRAINT "PK_FMFEETYPE_FEETYPEID" PRIMARY KEY ("FEETYPEID") ENABLE;
--------------------------------------------------------
--  Constraints for Table FMHEAD
--------------------------------------------------------

  ALTER TABLE "FLEX2"."FMHEAD" ADD CONSTRAINT "PK_FMHEAD_HEADID" PRIMARY KEY ("HEADID") ENABLE;
--------------------------------------------------------
--  Constraints for Table FMINSTALLMENTS
--------------------------------------------------------

  ALTER TABLE "FLEX2"."FMINSTALLMENTS" ADD CONSTRAINT "PK_FMIHD" PRIMARY KEY ("INSTALLMENTID", "CAMPUSID") ENABLE;
--------------------------------------------------------
--  Constraints for Table FMLEDGER_20190114
--------------------------------------------------------

  ALTER TABLE "FLEX2"."FMLEDGER_20190114" MODIFY ("ROLLNO" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table FMLEDGER_20190118
--------------------------------------------------------

  ALTER TABLE "FLEX2"."FMLEDGER_20190118" MODIFY ("ROLLNO" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table FMLEDGER_20190129
--------------------------------------------------------

  ALTER TABLE "FLEX2"."FMLEDGER_20190129" MODIFY ("ROLLNO" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table FMLEDGER_MAKINGPAYABLES
--------------------------------------------------------

  ALTER TABLE "FLEX2"."FMLEDGER_MAKINGPAYABLES" MODIFY ("ROLLNO" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table FMLEDGER_REFUND
--------------------------------------------------------

  ALTER TABLE "FLEX2"."FMLEDGER_REFUND" MODIFY ("ROLLNO" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table FMLEDGER_REGLOG
--------------------------------------------------------

  ALTER TABLE "FLEX2"."FMLEDGER_REGLOG" ADD CONSTRAINT "FMLEDGER_REGLOG_PK" PRIMARY KEY ("LEDGERID", "REGLOGID") ENABLE;

--------------------------------------------------------
--  Constraints for Table FMLEDGER_SCROLLDETAIL
--------------------------------------------------------

  ALTER TABLE "FLEX2"."FMLEDGER_SCROLLDETAIL" ADD CONSTRAINT "FMLEDGER_SCROLLDETAIL_PK" PRIMARY KEY ("LEDGERID", "SCROLLDETAILID") ENABLE;



--------------------------------------------------------
--  Constraints for Table FMLEDGER_STUDENTSPONS
--------------------------------------------------------

  ALTER TABLE "FLEX2"."FMLEDGER_STUDENTSPONS" ADD CONSTRAINT "FMLEDGER_STUDENTSPONS_PK" PRIMARY KEY ("STUDENTSPONSID", "LEDGERID") ENABLE;
--------------------------------------------------------
--  Constraints for Table FMPAYMENTMODE
--------------------------------------------------------

  ALTER TABLE "FLEX2"."FMPAYMENTMODE" ADD CONSTRAINT "FMPAYMENTMODE_PK" PRIMARY KEY ("PAYMENTMODEID") ENABLE;
--------------------------------------------------------
--  Constraints for Table FMPAYMENTTYPE
--------------------------------------------------------

  ALTER TABLE "FLEX2"."FMPAYMENTTYPE" ADD CONSTRAINT "FMPAYMENTTYPE_PK" PRIMARY KEY ("PAYMENTTYPE") ENABLE;
--------------------------------------------------------
--  Constraints for Table FMRECEIVEDSPONSORAMOUNT
--------------------------------------------------------

  ALTER TABLE "FLEX2"."FMRECEIVEDSPONSORAMOUNT" MODIFY ("ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."FMRECEIVEDSPONSORAMOUNT" MODIFY ("SPONSORSHIPID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."FMRECEIVEDSPONSORAMOUNT" MODIFY ("AMOUNT" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."FMRECEIVEDSPONSORAMOUNT" MODIFY ("REMARKS" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."FMRECEIVEDSPONSORAMOUNT" MODIFY ("ENTEREDBY" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."FMRECEIVEDSPONSORAMOUNT" MODIFY ("ENTRYDATE" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."FMRECEIVEDSPONSORAMOUNT" MODIFY ("STATUS" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table FMREFUND
--------------------------------------------------------

  ALTER TABLE "FLEX2"."FMREFUND" ADD CONSTRAINT "PK_FMRFID" PRIMARY KEY ("REFUNDID") ENABLE;
--------------------------------------------------------
--  Constraints for Table FMREPOSTING_TEMP
--------------------------------------------------------

  ALTER TABLE "FLEX2"."FMREPOSTING_TEMP" ADD CONSTRAINT "FMREPORTING_TEMP_PK" PRIMARY KEY ("SCROLLDETAILID") ENABLE;

--------------------------------------------------------
--  Constraints for Table FMSCROLLDETAIL
--------------------------------------------------------

  ALTER TABLE "FLEX2"."FMSCROLLDETAIL" ADD CONSTRAINT "FMSCROLLDETAIL_PK" PRIMARY KEY ("SCROLLDETAILID") ENABLE;



--------------------------------------------------------
--  Constraints for Table FMSCROLLSUMMARY
--------------------------------------------------------

  ALTER TABLE "FLEX2"."FMSCROLLSUMMARY" ADD CONSTRAINT "FMSCROLLSUMMARY_PK" PRIMARY KEY ("SCROLLID", "CAMPUSID") ENABLE;
--------------------------------------------------------
--  Constraints for Table FMSEMFEE_20190114
--------------------------------------------------------

  ALTER TABLE "FLEX2"."FMSEMFEE_20190114" MODIFY ("SPONSOR" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table FMSEMFEE_20190129
--------------------------------------------------------

  ALTER TABLE "FLEX2"."FMSEMFEE_20190129" MODIFY ("SPONSOR" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table FMSPONSOREDSTUDENT
--------------------------------------------------------

  ALTER TABLE "FLEX2"."FMSPONSOREDSTUDENT" ADD CONSTRAINT "FMSPONSOREDSTUDENT_PK" PRIMARY KEY ("STUDENT_SPONSID") ENABLE;
--------------------------------------------------------
--  Constraints for Table FMSPONSORSHIP
--------------------------------------------------------

  ALTER TABLE "FLEX2"."FMSPONSORSHIP" ADD CONSTRAINT "FMSPONSORSHIP_PK" PRIMARY KEY ("SPONSORSHIPID") ENABLE;
--------------------------------------------------------
--  Constraints for Table FMSPONSORSHIPDETAIL
--------------------------------------------------------

  ALTER TABLE "FLEX2"."FMSPONSORSHIPDETAIL" ADD CONSTRAINT "FMSPONSORSHIPDETAIL_PK" PRIMARY KEY ("SPONSORSHIPDETAILID") ENABLE;
--------------------------------------------------------
--  Constraints for Table FMSTATUS
--------------------------------------------------------

  ALTER TABLE "FLEX2"."FMSTATUS" ADD CONSTRAINT "FMSTATUS_PK" PRIMARY KEY ("STATUSID") ENABLE;
--------------------------------------------------------
--  Constraints for Table FMSTUDENTFEETYPE
--------------------------------------------------------

  ALTER TABLE "FLEX2"."FMSTUDENTFEETYPE" ADD CONSTRAINT "PK_FMSTRNOSID" PRIMARY KEY ("ROLLNO", "SEMID") ENABLE;

--------------------------------------------------------
--  Constraints for Table FMSTUDENTSPONSORSHIP
--------------------------------------------------------

  ALTER TABLE "FLEX2"."FMSTUDENTSPONSORSHIP" ADD CONSTRAINT "FMSTUDENTSPONSORSHIP_PK" PRIMARY KEY ("CAMPUSID", "ROLLNO", "SPONSORSHIPID", "STARTSEMID") ENABLE;

  ALTER TABLE "FLEX2"."FMSTUDENTSPONSORSHIP" MODIFY ("CAMPUSID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."FMSTUDENTSPONSORSHIP" MODIFY ("ROLLNO" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."FMSTUDENTSPONSORSHIP" MODIFY ("SPONSORSHIPID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."FMSTUDENTSPONSORSHIP" MODIFY ("STARTSEMID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."FMSTUDENTSPONSORSHIP" MODIFY ("ENDSEMID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."FMSTUDENTSPONSORSHIP" MODIFY ("TYPE" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."FMSTUDENTSPONSORSHIP" MODIFY ("AMOUNT" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."FMSTUDENTSPONSORSHIP" MODIFY ("ENTEREDBY" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."FMSTUDENTSPONSORSHIP" MODIFY ("ENTRYDATE" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."FMSTUDENTSPONSORSHIP" MODIFY ("STATUS" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table FMSUBHEAD
--------------------------------------------------------

  ALTER TABLE "FLEX2"."FMSUBHEAD" ADD CONSTRAINT "PK_FMSBHD_SUBHEADID" PRIMARY KEY ("SUBHEADID") ENABLE;
--------------------------------------------------------
--  Constraints for Table FMWHTAXDEPOSITRECORD
--------------------------------------------------------

  ALTER TABLE "FLEX2"."FMWHTAXDEPOSITRECORD" ADD CONSTRAINT "FMWHTAXDEPOSITRECORD_PK" PRIMARY KEY ("SNO") ENABLE;

--------------------------------------------------------
--  Constraints for Table FMWHTAXEXEMPTION
--------------------------------------------------------

  ALTER TABLE "FLEX2"."FMWHTAXEXEMPTION" ADD CONSTRAINT "FMWHTAXEXEMPTION_PK" PRIMARY KEY ("ROLLNO", "TAXYEAR", "SEMID") ENABLE;
--------------------------------------------------------
--  Constraints for Table FM_DATES
--------------------------------------------------------

  ALTER TABLE "FLEX2"."FM_DATES" MODIFY ("ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."FM_DATES" ADD PRIMARY KEY ("ID", "CAMPUSID", "SEMID", "PROGRAMID") ENABLE;

--------------------------------------------------------
--  Constraints for Table GRADE
--------------------------------------------------------

  ALTER TABLE "FLEX2"."GRADE" ADD CONSTRAINT "PK_GRADE" PRIMARY KEY ("GRADE_ID") ENABLE;
--------------------------------------------------------
--  Constraints for Table GRADEPOLICY
--------------------------------------------------------

  ALTER TABLE "FLEX2"."GRADEPOLICY" ADD CONSTRAINT "GP_GPIDGL" PRIMARY KEY ("GRADEPOLICYID", "GRADE_ID") ENABLE;
--------------------------------------------------------
--  Constraints for Table GRADEPOLICY_COURSE
--------------------------------------------------------

  ALTER TABLE "FLEX2"."GRADEPOLICY_COURSE" ADD CONSTRAINT "GPC_CIDGPIDSD" PRIMARY KEY ("COURSE_ID", "GRADEPOLICYID", "STARTINGDATE") ENABLE;

--------------------------------------------------------
--  Constraints for Table GRADEPOLICY_DETAIL
--------------------------------------------------------

  ALTER TABLE "FLEX2"."GRADEPOLICY_DETAIL" ADD CONSTRAINT "GPD_GRADEPOLICYID" PRIMARY KEY ("GRADEPOLICYID") ENABLE;
--------------------------------------------------------
--  Constraints for Table GRADING_SCHEME
--------------------------------------------------------

  ALTER TABLE "FLEX2"."GRADING_SCHEME" ADD CONSTRAINT "PK_GSID" PRIMARY KEY ("GS_ID") ENABLE;
--------------------------------------------------------
--  Constraints for Table GRADING_ZFACTOR
--------------------------------------------------------

  ALTER TABLE "FLEX2"."GRADING_ZFACTOR" ADD CONSTRAINT "PK_GZFID" PRIMARY KEY ("GZF_ID") ENABLE;


--------------------------------------------------------
--  Constraints for Table INSTR_COURSE_PREF
--------------------------------------------------------

  ALTER TABLE "FLEX2"."INSTR_COURSE_PREF" ADD CONSTRAINT "PK_INSTR_COURSE_PREF" PRIMARY KEY ("PREF_ID") ENABLE;
--------------------------------------------------------
--  Constraints for Table LECTURE
--------------------------------------------------------

  ALTER TABLE "FLEX2"."LECTURE" ADD CONSTRAINT "PK_LECTURE" PRIMARY KEY ("LECTURE_ID") ENABLE;

--------------------------------------------------------
--  Constraints for Table NUTES_SEG_DATA
--------------------------------------------------------

  ALTER TABLE "FLEX2"."NUTES_SEG_DATA" MODIFY ("PROG_CODE" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table NUTES_TM_SEG
--------------------------------------------------------

  ALTER TABLE "FLEX2"."NUTES_TM_SEG" MODIFY ("CANDIDATE_ID" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table ORA_ASPNET_APPLICATIONS
--------------------------------------------------------

  ALTER TABLE "FLEX2"."ORA_ASPNET_APPLICATIONS" MODIFY ("APPLICATIONNAME" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."ORA_ASPNET_APPLICATIONS" MODIFY ("LOWEREDAPPLICATIONNAME" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."ORA_ASPNET_APPLICATIONS" MODIFY ("APPLICATIONID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."ORA_ASPNET_APPLICATIONS" ADD PRIMARY KEY ("APPLICATIONID") ENABLE;

  ALTER TABLE "FLEX2"."ORA_ASPNET_APPLICATIONS" ADD UNIQUE ("APPLICATIONNAME") ENABLE;

  ALTER TABLE "FLEX2"."ORA_ASPNET_APPLICATIONS" ADD UNIQUE ("LOWEREDAPPLICATIONNAME") ENABLE;
--------------------------------------------------------
--  Constraints for Table ORA_ASPNET_MEMBERSHIP
--------------------------------------------------------

  ALTER TABLE "FLEX2"."ORA_ASPNET_MEMBERSHIP" MODIFY ("APPLICATIONID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."ORA_ASPNET_MEMBERSHIP" MODIFY ("USERID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."ORA_ASPNET_MEMBERSHIP" MODIFY ("PASSWORD" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."ORA_ASPNET_MEMBERSHIP" MODIFY ("PASSWORDFORMAT" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."ORA_ASPNET_MEMBERSHIP" MODIFY ("PASSWORDSALT" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."ORA_ASPNET_MEMBERSHIP" MODIFY ("ISAPPROVED" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."ORA_ASPNET_MEMBERSHIP" MODIFY ("ISLOCKEDOUT" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."ORA_ASPNET_MEMBERSHIP" MODIFY ("CREATEDATE" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."ORA_ASPNET_MEMBERSHIP" MODIFY ("LASTLOGINDATE" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."ORA_ASPNET_MEMBERSHIP" MODIFY ("LASTPASSWORDCHANGEDDATE" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."ORA_ASPNET_MEMBERSHIP" MODIFY ("LASTLOCKOUTDATE" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."ORA_ASPNET_MEMBERSHIP" MODIFY ("FAILEDPWDATTEMPTCOUNT" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."ORA_ASPNET_MEMBERSHIP" MODIFY ("FAILEDPWDATTEMPTWINSTART" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."ORA_ASPNET_MEMBERSHIP" MODIFY ("FAILEDPWDANSWERATTEMPTCOUNT" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."ORA_ASPNET_MEMBERSHIP" MODIFY ("FAILEDPWDANSWERATTEMPTWINSTART" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."ORA_ASPNET_MEMBERSHIP" ADD PRIMARY KEY ("USERID") ENABLE;
--------------------------------------------------------
--  Constraints for Table ORA_ASPNET_PATHS
--------------------------------------------------------

  ALTER TABLE "FLEX2"."ORA_ASPNET_PATHS" MODIFY ("APPLICATIONID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."ORA_ASPNET_PATHS" MODIFY ("PATHID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."ORA_ASPNET_PATHS" MODIFY ("PATH" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."ORA_ASPNET_PATHS" MODIFY ("LOWEREDPATH" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."ORA_ASPNET_PATHS" ADD PRIMARY KEY ("PATHID") ENABLE;
--------------------------------------------------------
--  Constraints for Table ORA_ASPNET_PERSONALIZNALLUSERS
--------------------------------------------------------

  ALTER TABLE "FLEX2"."ORA_ASPNET_PERSONALIZNALLUSERS" MODIFY ("PAGESETTINGS" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."ORA_ASPNET_PERSONALIZNALLUSERS" MODIFY ("LASTUPDATEDDATE" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table ORA_ASPNET_PERSONALIZNPERUSER
--------------------------------------------------------

  ALTER TABLE "FLEX2"."ORA_ASPNET_PERSONALIZNPERUSER" MODIFY ("ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."ORA_ASPNET_PERSONALIZNPERUSER" MODIFY ("PAGESETTINGS" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."ORA_ASPNET_PERSONALIZNPERUSER" MODIFY ("LASTUPDATEDDATE" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."ORA_ASPNET_PERSONALIZNPERUSER" ADD PRIMARY KEY ("ID") ENABLE;
--------------------------------------------------------
--  Constraints for Table ORA_ASPNET_PROFILE
--------------------------------------------------------

  ALTER TABLE "FLEX2"."ORA_ASPNET_PROFILE" MODIFY ("USERID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."ORA_ASPNET_PROFILE" MODIFY ("PROPERTYNAMES" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."ORA_ASPNET_PROFILE" MODIFY ("PROPERTYVALUESSTRING" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."ORA_ASPNET_PROFILE" MODIFY ("PROPERTYVALUESBINARY" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."ORA_ASPNET_PROFILE" MODIFY ("LASTUPDATEDDATE" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."ORA_ASPNET_PROFILE" ADD PRIMARY KEY ("USERID") ENABLE;
--------------------------------------------------------
--  Constraints for Table ORA_ASPNET_ROLES
--------------------------------------------------------

  ALTER TABLE "FLEX2"."ORA_ASPNET_ROLES" MODIFY ("APPLICATIONID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."ORA_ASPNET_ROLES" MODIFY ("ROLENAME" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."ORA_ASPNET_ROLES" MODIFY ("LOWEREDROLENAME" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."ORA_ASPNET_ROLES" ADD PRIMARY KEY ("ROLEID") ENABLE;
--------------------------------------------------------
--  Constraints for Table ORA_ASPNET_SESSIONAPPLICATIONS
--------------------------------------------------------

  ALTER TABLE "FLEX2"."ORA_ASPNET_SESSIONAPPLICATIONS" MODIFY ("APPID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."ORA_ASPNET_SESSIONAPPLICATIONS" MODIFY ("APPNAME" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."ORA_ASPNET_SESSIONAPPLICATIONS" ADD PRIMARY KEY ("APPID") ENABLE;
--------------------------------------------------------
--  Constraints for Table ORA_ASPNET_SESSIONS
--------------------------------------------------------

  ALTER TABLE "FLEX2"."ORA_ASPNET_SESSIONS" MODIFY ("SESSIONID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."ORA_ASPNET_SESSIONS" MODIFY ("CREATED" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."ORA_ASPNET_SESSIONS" MODIFY ("EXPIRES" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."ORA_ASPNET_SESSIONS" MODIFY ("LOCKDATE" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."ORA_ASPNET_SESSIONS" MODIFY ("LOCKDATELOCAL" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."ORA_ASPNET_SESSIONS" MODIFY ("LOCKCOOKIE" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."ORA_ASPNET_SESSIONS" MODIFY ("TIMEOUT" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."ORA_ASPNET_SESSIONS" MODIFY ("LOCKED" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."ORA_ASPNET_SESSIONS" MODIFY ("FLAGS" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."ORA_ASPNET_SESSIONS" ADD PRIMARY KEY ("SESSIONID") ENABLE;
--------------------------------------------------------
--  Constraints for Table ORA_ASPNET_SITEMAP
--------------------------------------------------------

  ALTER TABLE "FLEX2"."ORA_ASPNET_SITEMAP" ADD CONSTRAINT "PK_SITEMAP_APPID_ID" PRIMARY KEY ("APPLICATIONID", "ID") ENABLE;

  ALTER TABLE "FLEX2"."ORA_ASPNET_SITEMAP" MODIFY ("APPLICATIONID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."ORA_ASPNET_SITEMAP" MODIFY ("ID" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table ORA_ASPNET_USERS
--------------------------------------------------------

  ALTER TABLE "FLEX2"."ORA_ASPNET_USERS" MODIFY ("APPLICATIONID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."ORA_ASPNET_USERS" MODIFY ("USERID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."ORA_ASPNET_USERS" MODIFY ("USERNAME" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."ORA_ASPNET_USERS" MODIFY ("LOWEREDUSERNAME" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."ORA_ASPNET_USERS" MODIFY ("ISANONYMOUS" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."ORA_ASPNET_USERS" MODIFY ("LASTACTIVITYDATE" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."ORA_ASPNET_USERS" ADD PRIMARY KEY ("USERID") ENABLE;
--------------------------------------------------------
--  Constraints for Table ORA_ASPNET_USERSINROLES
--------------------------------------------------------

  ALTER TABLE "FLEX2"."ORA_ASPNET_USERSINROLES" ADD CONSTRAINT "PK_ASPNET_USERSINROLES" PRIMARY KEY ("USERID", "ROLEID") ENABLE;

  ALTER TABLE "FLEX2"."ORA_ASPNET_USERSINROLES" MODIFY ("USERID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."ORA_ASPNET_USERSINROLES" MODIFY ("ROLEID" NOT NULL ENABLE);

--------------------------------------------------------
--  Constraints for Table PHD_CLOSURE_ADMISSION_DETAIL
--------------------------------------------------------

  ALTER TABLE "FLEX2"."PHD_CLOSURE_ADMISSION_DETAIL" ADD CONSTRAINT "PHD_CLOSURE_ADMISSION_DETAILPK" PRIMARY KEY ("PA_ID") ENABLE;

  ALTER TABLE "FLEX2"."PHD_CLOSURE_ADMISSION_DETAIL" MODIFY ("ROLL_NO" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."PHD_CLOSURE_ADMISSION_DETAIL" MODIFY ("CLOSURE_DATE" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."PHD_CLOSURE_ADMISSION_DETAIL" MODIFY ("BASR_DATE" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table PHD_COMPREHENSIVETEST
--------------------------------------------------------

  ALTER TABLE "FLEX2"."PHD_COMPREHENSIVETEST" MODIFY ("CT_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."PHD_COMPREHENSIVETEST" MODIFY ("ROLL_NO" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."PHD_COMPREHENSIVETEST" MODIFY ("ATTEMPT" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."PHD_COMPREHENSIVETEST" MODIFY ("APPLIEDON" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."PHD_COMPREHENSIVETEST" MODIFY ("TESTTAKEN" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."PHD_COMPREHENSIVETEST" MODIFY ("PROGRAMID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."PHD_COMPREHENSIVETEST" MODIFY ("CAMPUSID" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table PHD_FOREIGN_EVALUATORS
--------------------------------------------------------

  ALTER TABLE "FLEX2"."PHD_FOREIGN_EVALUATORS" MODIFY ("FEVAL_ID" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table PHD_GAT_DETAIL
--------------------------------------------------------

  ALTER TABLE "FLEX2"."PHD_GAT_DETAIL" MODIFY ("GID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."PHD_GAT_DETAIL" MODIFY ("ROLL_NO" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."PHD_GAT_DETAIL" MODIFY ("TEST_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."PHD_GAT_DETAIL" MODIFY ("SCORE" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."PHD_GAT_DETAIL" MODIFY ("PERCENTILE" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table PHD_GSC_MEETING_AGENDA
--------------------------------------------------------

  ALTER TABLE "FLEX2"."PHD_GSC_MEETING_AGENDA" ADD CONSTRAINT "PHD_GSC_MEETING_AGENDA_PK" PRIMARY KEY ("GMA_ID") ENABLE;

  ALTER TABLE "FLEX2"."PHD_GSC_MEETING_AGENDA" MODIFY ("GMA_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."PHD_GSC_MEETING_AGENDA" MODIFY ("MT_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."PHD_GSC_MEETING_AGENDA" MODIFY ("AGENDA_NO" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."PHD_GSC_MEETING_AGENDA" MODIFY ("TOPIC" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table PHD_GSC_MEETING_DETAIL
--------------------------------------------------------

  ALTER TABLE "FLEX2"."PHD_GSC_MEETING_DETAIL" ADD CONSTRAINT "PHD_GSC_MEETING_DETAIL_PK" PRIMARY KEY ("MT_ID") ENABLE;

  ALTER TABLE "FLEX2"."PHD_GSC_MEETING_DETAIL" MODIFY ("MT_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."PHD_GSC_MEETING_DETAIL" MODIFY ("TITLE" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."PHD_GSC_MEETING_DETAIL" MODIFY ("VENUE" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."PHD_GSC_MEETING_DETAIL" MODIFY ("TIMINGS" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."PHD_GSC_MEETING_DETAIL" MODIFY ("CREATEDBY" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."PHD_GSC_MEETING_DETAIL" MODIFY ("CREATEDON" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table PHD_I_DOCUMENTS
--------------------------------------------------------

  ALTER TABLE "FLEX2"."PHD_I_DOCUMENTS" MODIFY ("D_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."PHD_I_DOCUMENTS" MODIFY ("NAME" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."PHD_I_DOCUMENTS" MODIFY ("FOR_STUDENT" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table PHD_I_DOC_TYPE
--------------------------------------------------------

  ALTER TABLE "FLEX2"."PHD_I_DOC_TYPE" MODIFY ("ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."PHD_I_DOC_TYPE" MODIFY ("TYPE" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table PHD_I_GSC_MEMBER
--------------------------------------------------------

  ALTER TABLE "FLEX2"."PHD_I_GSC_MEMBER" ADD CONSTRAINT "PHD_I_GSC_MEMBER_PK" PRIMARY KEY ("EMP_ID", "CAMP_ID") ENABLE;

  ALTER TABLE "FLEX2"."PHD_I_GSC_MEMBER" MODIFY ("EMP_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."PHD_I_GSC_MEMBER" MODIFY ("CAMP_ID" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table PHD_I_STATUS
--------------------------------------------------------

  ALTER TABLE "FLEX2"."PHD_I_STATUS" ADD CONSTRAINT "PHD_I_STATUS_PK" PRIMARY KEY ("S_ID") ENABLE;
--------------------------------------------------------
--  Constraints for Table PHD_LOCAL_EVALUATORS
--------------------------------------------------------

  ALTER TABLE "FLEX2"."PHD_LOCAL_EVALUATORS" MODIFY ("LEVAL_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."PHD_LOCAL_EVALUATORS" MODIFY ("NAME" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table PHD_STD_EVALUATORS
--------------------------------------------------------

  ALTER TABLE "FLEX2"."PHD_STD_EVALUATORS" MODIFY ("STD_EVAL_ID" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table PHD_STUDENT_STATUS
--------------------------------------------------------

  ALTER TABLE "FLEX2"."PHD_STUDENT_STATUS" MODIFY ("ROLL_NO" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."PHD_STUDENT_STATUS" MODIFY ("STATUS" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table PHD_STUDENT_SUPERVISOR
--------------------------------------------------------

  ALTER TABLE "FLEX2"."PHD_STUDENT_SUPERVISOR" MODIFY ("ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."PHD_STUDENT_SUPERVISOR" MODIFY ("ARN" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."PHD_STUDENT_SUPERVISOR" MODIFY ("ROLLNO" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."PHD_STUDENT_SUPERVISOR" MODIFY ("EMP_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."PHD_STUDENT_SUPERVISOR" MODIFY ("SUPERVISOR_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."PHD_STUDENT_SUPERVISOR" MODIFY ("STATUS" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table PHD_STUDENT_SUPERVISOR_DETAIL
--------------------------------------------------------

  ALTER TABLE "FLEX2"."PHD_STUDENT_SUPERVISOR_DETAIL" MODIFY ("ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."PHD_STUDENT_SUPERVISOR_DETAIL" MODIFY ("STD_SUPERVISOR_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."PHD_STUDENT_SUPERVISOR_DETAIL" MODIFY ("IS_DOC" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."PHD_STUDENT_SUPERVISOR_DETAIL" MODIFY ("IDEA_BY" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."PHD_STUDENT_SUPERVISOR_DETAIL" MODIFY ("CAN_CONTINUE" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table PHD_STUDENT_SUPERVISOR_LOG
--------------------------------------------------------

  ALTER TABLE "FLEX2"."PHD_STUDENT_SUPERVISOR_LOG" MODIFY ("PSSD_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."PHD_STUDENT_SUPERVISOR_LOG" MODIFY ("SUPERVISOR_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."PHD_STUDENT_SUPERVISOR_LOG" MODIFY ("STATUS" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."PHD_STUDENT_SUPERVISOR_LOG" MODIFY ("ACTIONBY" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table PROGRAM
--------------------------------------------------------

  ALTER TABLE "FLEX2"."PROGRAM" ADD CONSTRAINT "PK_PROGRAM" PRIMARY KEY ("PROG_ID") ENABLE;

  ALTER TABLE "FLEX2"."PROGRAM" MODIFY ("PROG_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."PROGRAM" MODIFY ("CODE" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."PROGRAM" MODIFY ("TITLE" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."PROGRAM" MODIFY ("LEVEL_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."PROGRAM" MODIFY ("SCH_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."PROGRAM" ADD CONSTRAINT "UK_PROGRAM_CODE" UNIQUE ("CODE") ENABLE;

--------------------------------------------------------
--  Constraints for Table PROGRAM_COURSE
--------------------------------------------------------

  ALTER TABLE "FLEX2"."PROGRAM_COURSE" ADD CONSTRAINT "PK_PROGRAM_COURSE" PRIMARY KEY ("BATCH_NO", "PROG_ID", "COURSE_ID") ENABLE;

  ALTER TABLE "FLEX2"."PROGRAM_COURSE" MODIFY ("BATCH_NO" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."PROGRAM_COURSE" MODIFY ("PROG_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."PROGRAM_COURSE" MODIFY ("COURSE_ID" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table PROG_BATCH_DOMAIN
--------------------------------------------------------

  ALTER TABLE "FLEX2"."PROG_BATCH_DOMAIN" ADD CONSTRAINT "PK_PBD" PRIMARY KEY ("BATCH_NO", "PROG_ID", "SCH_DOM_ID") ENABLE;

  ALTER TABLE "FLEX2"."PROG_BATCH_DOMAIN" MODIFY ("BATCH_NO" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."PROG_BATCH_DOMAIN" MODIFY ("PROG_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."PROG_BATCH_DOMAIN" MODIFY ("SCH_DOM_ID" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table REGISTRATIONLOG
--------------------------------------------------------

  ALTER TABLE "FLEX2"."REGISTRATIONLOG" ADD CONSTRAINT "REGISTRATIONLOG_PK" PRIMARY KEY ("REGLOGID") ENABLE;

  ALTER TABLE "FLEX2"."REGISTRATIONLOG" MODIFY ("REGLOGID" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table REGISTRATIONLOG_20190122
--------------------------------------------------------

  ALTER TABLE "FLEX2"."REGISTRATIONLOG_20190122" MODIFY ("REGLOGID" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table REGISTRATIONLOG_TEMP
--------------------------------------------------------

  ALTER TABLE "FLEX2"."REGISTRATIONLOG_TEMP" MODIFY ("REGLOGID" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table REPEAT_COURSE
--------------------------------------------------------

  ALTER TABLE "FLEX2"."REPEAT_COURSE" ADD CONSTRAINT "PK_RC_OID" PRIMARY KEY ("OFFER_ID") ENABLE;
--------------------------------------------------------
--  Constraints for Table ROLLNO_RANGE
--------------------------------------------------------

  ALTER TABLE "FLEX2"."ROLLNO_RANGE" ADD CONSTRAINT "PK_RR" PRIMARY KEY ("CAMP_ID", "SCHOOL_ID", "PROG_ID", "BATCH_NO") ENABLE;
--------------------------------------------------------
--  Constraints for Table SCHOOL
--------------------------------------------------------

  ALTER TABLE "FLEX2"."SCHOOL" ADD CONSTRAINT "PK_SCHOOL" PRIMARY KEY ("SCH_ID") ENABLE;

  ALTER TABLE "FLEX2"."SCHOOL" MODIFY ("SCH_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."SCHOOL" MODIFY ("CODE" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."SCHOOL" MODIFY ("NAME" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."SCHOOL" MODIFY ("CREATED_BY" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."SCHOOL" ADD CONSTRAINT "UK_SCHOOL_CODE" UNIQUE ("CODE") ENABLE;
--------------------------------------------------------
--  Constraints for Table SCHOOL_DOMAIN
--------------------------------------------------------

  ALTER TABLE "FLEX2"."SCHOOL_DOMAIN" ADD CONSTRAINT "PK_SCHOOL_DOMAIN" PRIMARY KEY ("SCH_DOM_ID") ENABLE;

  ALTER TABLE "FLEX2"."SCHOOL_DOMAIN" MODIFY ("SCH_DOM_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."SCHOOL_DOMAIN" ADD CONSTRAINT "UK_SD_CODE" UNIQUE ("CODE") ENABLE;
--------------------------------------------------------
--  Constraints for Table SECTION
--------------------------------------------------------

  ALTER TABLE "FLEX2"."SECTION" ADD CONSTRAINT "PK_SECTON" PRIMARY KEY ("SECTION_ID") ENABLE;

  ALTER TABLE "FLEX2"."SECTION" ADD CONSTRAINT "UK_SECTION_TITLE" UNIQUE ("TITLE") ENABLE;
--------------------------------------------------------
--  Constraints for Table SEMESTER
--------------------------------------------------------

  ALTER TABLE "FLEX2"."SEMESTER" ADD CONSTRAINT "PK_SEMESTER" PRIMARY KEY ("SEM_ID") ENABLE;
--------------------------------------------------------
--  Constraints for Table SEM_TEACHER_ACTIVITY
--------------------------------------------------------

  ALTER TABLE "FLEX2"."SEM_TEACHER_ACTIVITY" ADD CONSTRAINT "SEM_TEACHER_ACTIVITY_PK" PRIMARY KEY ("STA_ID") ENABLE;

  ALTER TABLE "FLEX2"."SEM_TEACHER_ACTIVITY" MODIFY ("STA_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."SEM_TEACHER_ACTIVITY" MODIFY ("EMP_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."SEM_TEACHER_ACTIVITY" MODIFY ("ACT_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."SEM_TEACHER_ACTIVITY" MODIFY ("SEM_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."SEM_TEACHER_ACTIVITY" MODIFY ("PROJ_COORD" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."SEM_TEACHER_ACTIVITY" MODIFY ("CRETED_BY" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."SEM_TEACHER_ACTIVITY" MODIFY ("CREATED_ON" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table STUDENT_ATTENDANCE
--------------------------------------------------------

  ALTER TABLE "FLEX2"."STUDENT_ATTENDANCE" ADD CONSTRAINT "PK_STUDENT_ATTENDANCE" PRIMARY KEY ("LECTURE_ID", "ROLL_NO") ENABLE;

  ALTER TABLE "FLEX2"."STUDENT_ATTENDANCE" MODIFY ("LECTURE_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."STUDENT_ATTENDANCE" MODIFY ("ROLL_NO" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table STUDENT_FAMILY_INFO
--------------------------------------------------------

  ALTER TABLE "FLEX2"."STUDENT_FAMILY_INFO" ADD CONSTRAINT "PK_STUDENT_FAMILY_INFO" PRIMARY KEY ("ARN", "REL_TYPE_ID") ENABLE;
--------------------------------------------------------
--  Constraints for Table STUDENT_PERSONAL_INFO
--------------------------------------------------------

  ALTER TABLE "FLEX2"."STUDENT_PERSONAL_INFO" ADD CONSTRAINT "STUDENT_PERSONAL_INFO" PRIMARY KEY ("ARN") ENABLE;
--------------------------------------------------------
--  Constraints for Table STUDENT_PROGRAM
--------------------------------------------------------

  ALTER TABLE "FLEX2"."STUDENT_PROGRAM" ADD CONSTRAINT "PK_STUDENT_PROGRAM" PRIMARY KEY ("ROLL_NO") ENABLE;

  ALTER TABLE "FLEX2"."STUDENT_PROGRAM" MODIFY ("PROG_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."STUDENT_PROGRAM" MODIFY ("BATCH_NO" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table STUDENT_QUALIFICATION
--------------------------------------------------------

  ALTER TABLE "FLEX2"."STUDENT_QUALIFICATION" ADD CONSTRAINT "PK_SQ_ARN" PRIMARY KEY ("ARN", "DEGREE", "PASSING_YEAR") ENABLE;

  ALTER TABLE "FLEX2"."STUDENT_QUALIFICATION" MODIFY ("DEGREE" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."STUDENT_QUALIFICATION" MODIFY ("PASSING_YEAR" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table STUDENT_REMARKS_HISTORY
--------------------------------------------------------

  ALTER TABLE "FLEX2"."STUDENT_REMARKS_HISTORY" ADD CONSTRAINT "PK_SRH_SRHID" PRIMARY KEY ("SRH_ID") ENABLE;

  ALTER TABLE "FLEX2"."STUDENT_REMARKS_HISTORY" MODIFY ("SRH_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."STUDENT_REMARKS_HISTORY" MODIFY ("ROLL_NO" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table STUDENT_SEMESTER
--------------------------------------------------------

  ALTER TABLE "FLEX2"."STUDENT_SEMESTER" ADD CONSTRAINT "PK_STUDENT_SEMESTER" PRIMARY KEY ("SEM_ID", "ROLL_NO") ENABLE;
--------------------------------------------------------
--  Constraints for Table STUDY_PLAN_SEM
--------------------------------------------------------

  ALTER TABLE "FLEX2"."STUDY_PLAN_SEM" ADD CONSTRAINT "PK_STUDY_PLAN_SEM" PRIMARY KEY ("BATCH_NO", "PROG_ID", "SR_NO") ENABLE;

  ALTER TABLE "FLEX2"."STUDY_PLAN_SEM" MODIFY ("SEM_ID" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table STUDY_TENT_PLAN
--------------------------------------------------------

  ALTER TABLE "FLEX2"."STUDY_TENT_PLAN" ADD CONSTRAINT "PK_STUDY_TENT_PLAN" PRIMARY KEY ("BATCH_NO", "PROG_ID", "SEM_ID", "COURSE_ID", "SR_NO") ENABLE;

--------------------------------------------------------
--  Constraints for Table TEMP_NUTES_SEG_DATA
--------------------------------------------------------

  ALTER TABLE "FLEX2"."TEMP_NUTES_SEG_DATA" MODIFY ("PROG_CODE" NOT NULL ENABLE);

--------------------------------------------------------
--  Constraints for Table TENT_GRADE
--------------------------------------------------------

  ALTER TABLE "FLEX2"."TENT_GRADE" ADD CONSTRAINT "PK_TF_OFFERID" PRIMARY KEY ("OFFER_ID", "PRIORITY") ENABLE;

  ALTER TABLE "FLEX2"."TENT_GRADE" MODIFY ("OFFER_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."TENT_GRADE" MODIFY ("PRIORITY" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table TENT_GRADE_0114
--------------------------------------------------------

  ALTER TABLE "FLEX2"."TENT_GRADE_0114" MODIFY ("OFFER_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."TENT_GRADE_0114" MODIFY ("PRIORITY" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table TENT_GRADE_DELETED
--------------------------------------------------------

  ALTER TABLE "FLEX2"."TENT_GRADE_DELETED" MODIFY ("DEL_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."TENT_GRADE_DELETED" MODIFY ("OFFER_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."TENT_GRADE_DELETED" MODIFY ("PRIORITY" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table TENT_GRADE_DETAIL
--------------------------------------------------------

  ALTER TABLE "FLEX2"."TENT_GRADE_DETAIL" ADD CONSTRAINT "PK_TDE_ID" PRIMARY KEY ("TGD_ID") ENABLE;

  ALTER TABLE "FLEX2"."TENT_GRADE_DETAIL" MODIFY ("TGD_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."TENT_GRADE_DETAIL" ADD CONSTRAINT "UK_TDE_OIDRNO" UNIQUE ("ROLL_NO", "OFFER_ID") ENABLE;
--------------------------------------------------------
--  Constraints for Table TENT_GRADE_DETAIL_DELETED
--------------------------------------------------------

  ALTER TABLE "FLEX2"."TENT_GRADE_DETAIL_DELETED" MODIFY ("DEL_ID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."TENT_GRADE_DETAIL_DELETED" MODIFY ("TGD_ID" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table TENT_GRADE_MISSINGSESSIONAL
--------------------------------------------------------

  ALTER TABLE "FLEX2"."TENT_GRADE_MISSINGSESSIONAL" ADD CONSTRAINT "PK_TGMS" PRIMARY KEY ("OFFER_ID", "ROLL_NO", "MISSING_SESSIONAL") ENABLE;













--------------------------------------------------------
--  Constraints for Table TT_V_T
--------------------------------------------------------

  ALTER TABLE "FLEX2"."TT_V_T" MODIFY ("ROLLNO" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."TT_V_T" MODIFY ("TITLE" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."TT_V_T" MODIFY ("COLLECTION" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table TT_V_T_2
--------------------------------------------------------

  ALTER TABLE "FLEX2"."TT_V_T_2" MODIFY ("SCROLLDETAILID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."TT_V_T_2" MODIFY ("SUBHEADID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."TT_V_T_2" MODIFY ("AMOUNT" NOT NULL ENABLE);
--------------------------------------------------------
--  Constraints for Table TT_V_T_3
--------------------------------------------------------

  ALTER TABLE "FLEX2"."TT_V_T_3" MODIFY ("SCROLLDETAILID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."TT_V_T_3" MODIFY ("SUBHEADID" NOT NULL ENABLE);

  ALTER TABLE "FLEX2"."TT_V_T_3" MODIFY ("AMOUNT" NOT NULL ENABLE);






--------------------------------------------------------
--  Ref Constraints for Table APPROLEDETAIL
--------------------------------------------------------

  ALTER TABLE "FLEX2"."APPROLEDETAIL" ADD CONSTRAINT "FK_APDET_ROLEID" FOREIGN KEY ("ROLEID")
	  REFERENCES "FLEX2"."APPROLE" ("ROLEID") ENABLE;

  ALTER TABLE "FLEX2"."APPROLEDETAIL" ADD CONSTRAINT "FK_ARD_MENUID" FOREIGN KEY ("MENUID")
	  REFERENCES "FLEX2"."APPMENU" ("MENUID") ENABLE;
--------------------------------------------------------
--  Ref Constraints for Table APPUSER
--------------------------------------------------------

  ALTER TABLE "FLEX2"."APPUSER" ADD CONSTRAINT "FK_APPUSER_EMPID" FOREIGN KEY ("EMP_ID")
	  REFERENCES "FLEX2"."EMPLOYEE" ("EMP_ID") ENABLE;
--------------------------------------------------------
--  Ref Constraints for Table APPUSERBOOKMARK
--------------------------------------------------------

   ALTER TABLE "FLEX2"."APPUSERBOOKMARK" ADD CONSTRAINT "FK_AUBM_USERID" FOREIGN KEY ("USERID")
	  REFERENCES "FLEX2"."APPUSER" ("USERID") ENABLE;
--------------------------------------------------------
--  Ref Constraints for Table APPUSERCAMPUS
--------------------------------------------------------

   ALTER TABLE "FLEX2"."APPUSERCAMPUS" ADD CONSTRAINT "FK_AUC_CAMP_ID" FOREIGN KEY ("CAMP_ID")
	  REFERENCES "FLEX2"."CAMPUS" ("CAMP_ID") ENABLE;

  ALTER TABLE "FLEX2"."APPUSERCAMPUS" ADD CONSTRAINT "FK_AUC_USERID" FOREIGN KEY ("USERID")
	  REFERENCES "FLEX2"."APPUSER" ("USERID") ENABLE;
--------------------------------------------------------
--  Ref Constraints for Table APPUSERDEPARTMENT
--------------------------------------------------------

  ALTER TABLE "FLEX2"."APPUSERDEPARTMENT" ADD CONSTRAINT "FK_AUD_DEPTID" FOREIGN KEY ("DEPT_ID")
	  REFERENCES "FLEX2"."DEPARTMENT" ("DEPT_ID") ENABLE;

  ALTER TABLE "FLEX2"."APPUSERDEPARTMENT" ADD CONSTRAINT "FK_AUD_USERID" FOREIGN KEY ("USERID")
	  REFERENCES "FLEX2"."APPUSER" ("USERID") ENABLE;
--------------------------------------------------------
--  Ref Constraints for Table APPUSERROLE
--------------------------------------------------------

   ALTER TABLE "FLEX2"."APPUSERROLE" ADD CONSTRAINT "FK_AUR_ROLEID" FOREIGN KEY ("ROLEID")
	  REFERENCES "FLEX2"."APPROLE" ("ROLEID") ENABLE;

  ALTER TABLE "FLEX2"."APPUSERROLE" ADD CONSTRAINT "FK_AUR_USERID" FOREIGN KEY ("USERID")
	  REFERENCES "FLEX2"."APPUSER" ("USERID") ENABLE;
--------------------------------------------------------
--  Ref Constraints for Table BATCH
--------------------------------------------------------

   ALTER TABLE "FLEX2"."BATCH" ADD CONSTRAINT "FK_BATCH_D_SHIFT_SHIFT_ID" FOREIGN KEY ("SHIFT_ID")
	  REFERENCES "FLEX2"."D_SHIFT" ("SHIFT_ID") ENABLE;
--------------------------------------------------------
--  Ref Constraints for Table BATCH_PROGRAM
--------------------------------------------------------

   ALTER TABLE "FLEX2"."BATCH_PROGRAM" ADD CONSTRAINT "FK_BATCH_BATCH_PROG" FOREIGN KEY ("BATCH_NO")
	  REFERENCES "FLEX2"."BATCH" ("BATCH_NO") ENABLE;

  ALTER TABLE "FLEX2"."BATCH_PROGRAM" ADD CONSTRAINT "FK_PROGRAM_BATCH_PROGRAM" FOREIGN KEY ("PROG_ID")
	  REFERENCES "FLEX2"."PROGRAM" ("PROG_ID") ENABLE;
------------------------------------------------------
--  Ref Constraints for Table BATCH_SECTION
--------------------------------------------------------

   ALTER TABLE "FLEX2"."BATCH_SECTION" ADD CONSTRAINT "FK_BATCH_BATCH_SECTION" FOREIGN KEY ("BATCH_NO")
	  REFERENCES "FLEX2"."BATCH" ("BATCH_NO") ENABLE;

  ALTER TABLE "FLEX2"."BATCH_SECTION" ADD CONSTRAINT "FK_BATCH_SECTION_CAMPUS" FOREIGN KEY ("CAMP_ID")
	  REFERENCES "FLEX2"."CAMPUS" ("CAMP_ID") ENABLE;

  ALTER TABLE "FLEX2"."BATCH_SECTION" ADD CONSTRAINT "FK_BATCH_SECTION_PROGID" FOREIGN KEY ("PROG_ID")
	  REFERENCES "FLEX2"."PROGRAM" ("PROG_ID") ENABLE;

  ALTER TABLE "FLEX2"."BATCH_SECTION" ADD CONSTRAINT "FK_BATCH_SECTION_SECTION" FOREIGN KEY ("SECTION_ID")
	  REFERENCES "FLEX2"."SECTION" ("SECTION_ID") ENABLE;

  ALTER TABLE "FLEX2"."BATCH_SECTION" ADD CONSTRAINT "FK_BATCH_SECTION_SHIFT" FOREIGN KEY ("SHIFT_ID")
	  REFERENCES "FLEX2"."D_SHIFT" ("SHIFT_ID") ENABLE;

--------------------------------------------------------
--  Ref Constraints for Table CAMPUS_ACTIVITY
--------------------------------------------------------

  ALTER TABLE "FLEX2"."CAMPUS_ACTIVITY" ADD CONSTRAINT "FK_CACID" FOREIGN KEY ("CAMP_ID")
	  REFERENCES "FLEX2"."CAMPUS" ("CAMP_ID") ENABLE;

  ALTER TABLE "FLEX2"."CAMPUS_ACTIVITY" ADD CONSTRAINT "FK_CADEPTID" FOREIGN KEY ("DEPT_ID")
	  REFERENCES "FLEX2"."DEPARTMENT" ("DEPT_ID") ENABLE;
--------------------------------------------------------
--  Ref Constraints for Table CAMPUS_BATCH
--------------------------------------------------------

  ALTER TABLE "FLEX2"."CAMPUS_BATCH" ADD CONSTRAINT "FK_CBR_BATCHNO" FOREIGN KEY ("BATCH_NO")
	  REFERENCES "FLEX2"."BATCH" ("BATCH_NO") ENABLE;

  ALTER TABLE "FLEX2"."CAMPUS_BATCH" ADD CONSTRAINT "FK_CBR_CAMPID" FOREIGN KEY ("CAMP_ID")
	  REFERENCES "FLEX2"."CAMPUS" ("CAMP_ID") ENABLE;
--------------------------------------------------------
--  Ref Constraints for Table CAMPUS_DEPT
--------------------------------------------------------

  ALTER TABLE "FLEX2"."CAMPUS_DEPT" ADD CONSTRAINT "FK_CAMPDEPT_DEPTID" FOREIGN KEY ("DEPT_ID")
	  REFERENCES "FLEX2"."DEPARTMENT" ("DEPT_ID") ENABLE;

  ALTER TABLE "FLEX2"."CAMPUS_DEPT" ADD CONSTRAINT "FK_CAMP_DEPT_CAMPUS" FOREIGN KEY ("CAMP_ID")
	  REFERENCES "FLEX2"."CAMPUS" ("CAMP_ID") ENABLE;

  ALTER TABLE "FLEX2"."CAMPUS_DEPT" ADD CONSTRAINT "FK_CAMP_DEPT_SCHOOL" FOREIGN KEY ("SCH_ID")
	  REFERENCES "FLEX2"."SCHOOL" ("SCH_ID") ENABLE;

--------------------------------------------------------
--  Ref Constraints for Table CAMPUS_PREFERENCE
--------------------------------------------------------

  ALTER TABLE "FLEX2"."CAMPUS_PREFERENCE" ADD CONSTRAINT "FK_CP_ARN" FOREIGN KEY ("ARN")
	  REFERENCES "FLEX2"."STUDENT_PERSONAL_INFO" ("ARN") ENABLE;

  ALTER TABLE "FLEX2"."CAMPUS_PREFERENCE" ADD CONSTRAINT "FK_CP_CAMPID" FOREIGN KEY ("CAMP_ID")
	  REFERENCES "FLEX2"."CAMPUS" ("CAMP_ID") ENABLE;
--------------------------------------------------------
--  Ref Constraints for Table CAMPUS_PROGRAM
--------------------------------------------------------

  ALTER TABLE "FLEX2"."CAMPUS_PROGRAM" ADD CONSTRAINT "FK_CPR_CAMPID" FOREIGN KEY ("CAMP_ID")
	  REFERENCES "FLEX2"."CAMPUS" ("CAMP_ID") ENABLE;

  ALTER TABLE "FLEX2"."CAMPUS_PROGRAM" ADD CONSTRAINT "FK_CPR_PROGID" FOREIGN KEY ("PROG_ID")
	  REFERENCES "FLEX2"."PROGRAM" ("PROG_ID") ENABLE;
--------------------------------------------------------
--  Ref Constraints for Table CAMP_SEMESTER
--------------------------------------------------------

  ALTER TABLE "FLEX2"."CAMP_SEMESTER" ADD CONSTRAINT "FK_CAMP_SEM_CAMPUS" FOREIGN KEY ("CAMP_ID")
	  REFERENCES "FLEX2"."CAMPUS" ("CAMP_ID") ENABLE;

  ALTER TABLE "FLEX2"."CAMP_SEMESTER" ADD CONSTRAINT "FK_CAMP_SEM_SEM" FOREIGN KEY ("SEM_ID")
	  REFERENCES "FLEX2"."SEMESTER" ("SEM_ID") ENABLE;



--------------------------------------------------------
--  Ref Constraints for Table COURSE
--------------------------------------------------------

  ALTER TABLE "FLEX2"."COURSE" ADD CONSTRAINT "FK_CRS_CTYPEID" FOREIGN KEY ("COURSE_TYPE_ID")
	  REFERENCES "FLEX2"."D_COURSE_TYPE" ("TYPE_ID") ENABLE;

  ALTER TABLE "FLEX2"."COURSE" ADD CONSTRAINT "FK_CRS_DEPTID" FOREIGN KEY ("DEPT_ID")
	  REFERENCES "FLEX2"."DEPARTMENT" ("DEPT_ID") ENABLE;

  ALTER TABLE "FLEX2"."COURSE" ADD CONSTRAINT "FK_CRS_LEVELID" FOREIGN KEY ("LEVEL_ID")
	  REFERENCES "FLEX2"."D_COURSE_LEVEL" ("LEVEL_ID") ENABLE;
--------------------------------------------------------
--  Ref Constraints for Table COURSE_COREQUISITE
--------------------------------------------------------

  ALTER TABLE "FLEX2"."COURSE_COREQUISITE" ADD CONSTRAINT "FK_COREQ_CID" FOREIGN KEY ("COURSE_ID")
	  REFERENCES "FLEX2"."COURSE" ("COURSE_ID") ENABLE;
--------------------------------------------------------
--  Ref Constraints for Table COURSE_EVALUATION
--------------------------------------------------------

  ALTER TABLE "FLEX2"."COURSE_EVALUATION" ADD CONSTRAINT "FK_COURSE_EVAL_CAMPUS" FOREIGN KEY ("CAMP_ID")
	  REFERENCES "FLEX2"."CAMPUS" ("CAMP_ID") ENABLE;

  ALTER TABLE "FLEX2"."COURSE_EVALUATION" ADD CONSTRAINT "FK_COURSE_EVAL_COURSE_OFFER" FOREIGN KEY ("OFFER_ID")
	  REFERENCES "FLEX2"."COURSE_OFFER" ("OFFER_ID") ENABLE;

  ALTER TABLE "FLEX2"."COURSE_EVALUATION" ADD CONSTRAINT "FK_CRE_EVALTYPEID" FOREIGN KEY ("EVAL_TYPE_ID")
	  REFERENCES "FLEX2"."D_COURSE_EVALUATION" ("EVAL_TYPE_ID") ENABLE;
--------------------------------------------------------
--  Ref Constraints for Table COURSE_EVALUATION_DETAIL
--------------------------------------------------------

  ALTER TABLE "FLEX2"."COURSE_EVALUATION_DETAIL" ADD CONSTRAINT "FK_COURSE_EVAL_DTL_EVAL_DTL" FOREIGN KEY ("EVAL_ID")
	  REFERENCES "FLEX2"."COURSE_EVALUATION" ("EVAL_ID") ENABLE;

  ALTER TABLE "FLEX2"."COURSE_EVALUATION_DETAIL" ADD CONSTRAINT "FK_DCE_ROLLNO" FOREIGN KEY ("ROLL_NO")
	  REFERENCES "FLEX2"."STUDENT_PROGRAM" ("ROLL_NO") ENABLE;
--------------------------------------------------------
--  Ref Constraints for Table COURSE_EVAL_SCHEME
--------------------------------------------------------

  ALTER TABLE "FLEX2"."COURSE_EVAL_SCHEME" ADD CONSTRAINT "FK_CES_CAMPID" FOREIGN KEY ("CAMP_ID")
	  REFERENCES "FLEX2"."CAMPUS" ("CAMP_ID") ENABLE;

  ALTER TABLE "FLEX2"."COURSE_EVAL_SCHEME" ADD CONSTRAINT "FK_CES_ETYPEID" FOREIGN KEY ("EVAL_TYPE_ID")
	  REFERENCES "FLEX2"."D_COURSE_EVALUATION" ("EVAL_TYPE_ID") ENABLE;

  ALTER TABLE "FLEX2"."COURSE_EVAL_SCHEME" ADD CONSTRAINT "FK_CES_OFFERID" FOREIGN KEY ("OFFER_ID")
	  REFERENCES "FLEX2"."COURSE_OFFER" ("OFFER_ID") ENABLE;
--------------------------------------------------------
--  Ref Constraints for Table COURSE_OFFER
--------------------------------------------------------

  ALTER TABLE "FLEX2"."COURSE_OFFER" ADD CONSTRAINT "FK_COURSE_OFFER_CAMP" FOREIGN KEY ("CAMP_ID")
	  REFERENCES "FLEX2"."CAMPUS" ("CAMP_ID") ENABLE;

  ALTER TABLE "FLEX2"."COURSE_OFFER" ADD CONSTRAINT "FK_COURSE_OFFER_COURSE" FOREIGN KEY ("COURSE_ID")
	  REFERENCES "FLEX2"."COURSE" ("COURSE_ID") ENABLE;

  ALTER TABLE "FLEX2"."COURSE_OFFER" ADD CONSTRAINT "FK_COURSE_OFFER_EMPID" FOREIGN KEY ("EMP_ID")
	  REFERENCES "FLEX2"."EMPLOYEE" ("EMP_ID") ENABLE;

  ALTER TABLE "FLEX2"."COURSE_OFFER" ADD CONSTRAINT "FK_COURSE_OFFER_OFRDEPTID" FOREIGN KEY ("OFFER_DEPT_ID")
	  REFERENCES "FLEX2"."DEPARTMENT" ("DEPT_ID") ENABLE;

  ALTER TABLE "FLEX2"."COURSE_OFFER" ADD CONSTRAINT "FK_COURSE_OFFER_SEM" FOREIGN KEY ("SEM_ID")
	  REFERENCES "FLEX2"."SEMESTER" ("SEM_ID") ENABLE;

  ALTER TABLE "FLEX2"."COURSE_OFFER" ADD CONSTRAINT "FK_CRO_SECTION" FOREIGN KEY ("SECTION_ID")
	  REFERENCES "FLEX2"."SECTION" ("SECTION_ID") ENABLE;

  ALTER TABLE "FLEX2"."COURSE_OFFER" ADD CONSTRAINT "FK_CRO_SHIFTID" FOREIGN KEY ("SHIFT_ID")
	  REFERENCES "FLEX2"."D_SHIFT" ("SHIFT_ID") ENABLE;
--------------------------------------------------------
--  Ref Constraints for Table COURSE_OFFER_DETAIL
--------------------------------------------------------

  ALTER TABLE "FLEX2"."COURSE_OFFER_DETAIL" ADD CONSTRAINT "FK_COD_BATCHNO" FOREIGN KEY ("BATCH_NO")
	  REFERENCES "FLEX2"."BATCH" ("BATCH_NO") ENABLE;

  ALTER TABLE "FLEX2"."COURSE_OFFER_DETAIL" ADD CONSTRAINT "FK_COD_CAMPID" FOREIGN KEY ("CAMP_ID")
	  REFERENCES "FLEX2"."CAMPUS" ("CAMP_ID") ENABLE;

  ALTER TABLE "FLEX2"."COURSE_OFFER_DETAIL" ADD CONSTRAINT "FK_COD_PROGID" FOREIGN KEY ("PROG_ID")
	  REFERENCES "FLEX2"."PROGRAM" ("PROG_ID") ENABLE;

  ALTER TABLE "FLEX2"."COURSE_OFFER_DETAIL" ADD CONSTRAINT "FK_CROD_SECTION" FOREIGN KEY ("BATCH_SECTION")
	  REFERENCES "FLEX2"."SECTION" ("SECTION_ID") ENABLE;

  ALTER TABLE "FLEX2"."COURSE_OFFER_DETAIL" ADD CONSTRAINT "FK_CRS_OFF_DTL_CRS_OFFER" FOREIGN KEY ("OFFER_ID")
	  REFERENCES "FLEX2"."COURSE_OFFER" ("OFFER_ID") ENABLE;
--------------------------------------------------------
--  Ref Constraints for Table COURSE_PREREQ
--------------------------------------------------------

  ALTER TABLE "FLEX2"."COURSE_PREREQ" ADD CONSTRAINT "FK_COURSE_PREREQ_SCHOOL_SCH_ID" FOREIGN KEY ("SCH_ID")
	  REFERENCES "FLEX2"."SCHOOL" ("SCH_ID") ENABLE;

  ALTER TABLE "FLEX2"."COURSE_PREREQ" ADD CONSTRAINT "FK_CP_COURSEID" FOREIGN KEY ("COURSE_ID")
	  REFERENCES "FLEX2"."COURSE" ("COURSE_ID") ENABLE;
--------------------------------------------------------
--  Ref Constraints for Table COURSE_REGISTRATION
--------------------------------------------------------

  ALTER TABLE "FLEX2"."COURSE_REGISTRATION" ADD CONSTRAINT "FK_CRG_CAMPID" FOREIGN KEY ("CAMP_ID")
	  REFERENCES "FLEX2"."CAMPUS" ("CAMP_ID") ENABLE;

  ALTER TABLE "FLEX2"."COURSE_REGISTRATION" ADD CONSTRAINT "FK_CRG_COURSEID" FOREIGN KEY ("COURSE_ID")
	  REFERENCES "FLEX2"."COURSE" ("COURSE_ID") ENABLE;

  ALTER TABLE "FLEX2"."COURSE_REGISTRATION" ADD CONSTRAINT "FK_CRG_OFFERID" FOREIGN KEY ("OFFER_ID")
	  REFERENCES "FLEX2"."COURSE_OFFER" ("OFFER_ID") ENABLE;

  ALTER TABLE "FLEX2"."COURSE_REGISTRATION" ADD CONSTRAINT "FK_CRG_RELATIONID" FOREIGN KEY ("RELATION_ID")
	  REFERENCES "FLEX2"."D_COURSE_RELATION" ("RELATION_ID") ENABLE;

  ALTER TABLE "FLEX2"."COURSE_REGISTRATION" ADD CONSTRAINT "FK_CRG_ROLLNO" FOREIGN KEY ("ROLL_NO")
	  REFERENCES "FLEX2"."STUDENT_PROGRAM" ("ROLL_NO") ENABLE NOVALIDATE;

  ALTER TABLE "FLEX2"."COURSE_REGISTRATION" ADD CONSTRAINT "FK_CRG_SECTION" FOREIGN KEY ("SECTION_ID")
	  REFERENCES "FLEX2"."SECTION" ("SECTION_ID") ENABLE;

  ALTER TABLE "FLEX2"."COURSE_REGISTRATION" ADD CONSTRAINT "FK_CRG_SEMID" FOREIGN KEY ("SEM_ID")
	  REFERENCES "FLEX2"."SEMESTER" ("SEM_ID") ENABLE;

  ALTER TABLE "FLEX2"."COURSE_REGISTRATION" ADD CONSTRAINT "FK_CRSREG_REGSTATUSID" FOREIGN KEY ("REG_STATUS")
	  REFERENCES "FLEX2"."D_REG_STATUS" ("STATUS_ID") ENABLE;


--------------------------------------------------------
--  Ref Constraints for Table DEPARTMENT
--------------------------------------------------------

  ALTER TABLE "FLEX2"."DEPARTMENT" ADD CONSTRAINT "FK_DEPT_DEPTYPEID" FOREIGN KEY ("DEPT_TYPE_ID")
	  REFERENCES "FLEX2"."D_DEPT_TYPE" ("TYPE_ID") ENABLE;
--------------------------------------------------------
--  Ref Constraints for Table DEPT_PROGRAM
--------------------------------------------------------

  ALTER TABLE "FLEX2"."DEPT_PROGRAM" ADD CONSTRAINT "FK_DEPTPROG_DEPTID" FOREIGN KEY ("DEPT_ID")
	  REFERENCES "FLEX2"."DEPARTMENT" ("DEPT_ID") ENABLE;

  ALTER TABLE "FLEX2"."DEPT_PROGRAM" ADD CONSTRAINT "FK_DEPT_PROGRAM_PROG_PROG_ID" FOREIGN KEY ("PROG_ID")
	  REFERENCES "FLEX2"."PROGRAM" ("PROG_ID") ENABLE;
--------------------------------------------------------
--  Ref Constraints for Table DISCIPLINE_PREFERENCE
--------------------------------------------------------

  ALTER TABLE "FLEX2"."DISCIPLINE_PREFERENCE" ADD CONSTRAINT "FK_DP_ARN" FOREIGN KEY ("ARN")
	  REFERENCES "FLEX2"."STUDENT_PERSONAL_INFO" ("ARN") ENABLE;

  ALTER TABLE "FLEX2"."DISCIPLINE_PREFERENCE" ADD CONSTRAINT "FK_DP_PROGID" FOREIGN KEY ("PROG_ID")
	  REFERENCES "FLEX2"."PROGRAM" ("PROG_ID") ENABLE;
--------------------------------------------------------
--  Ref Constraints for Table DOCUMENT_VERIFICATION
--------------------------------------------------------

  ALTER TABLE "FLEX2"."DOCUMENT_VERIFICATION" ADD CONSTRAINT "FK_DV_ARN" FOREIGN KEY ("ARN")
	  REFERENCES "FLEX2"."STUDENT_PERSONAL_INFO" ("ARN") ENABLE;

  ALTER TABLE "FLEX2"."DOCUMENT_VERIFICATION" ADD CONSTRAINT "FK_DV_PROG_ID" FOREIGN KEY ("PROG_ID")
	  REFERENCES "FLEX2"."PROGRAM" ("PROG_ID") ENABLE;









--------------------------------------------------------
--  Ref Constraints for Table D_DEPT_EVAL_SCHEME
--------------------------------------------------------

  ALTER TABLE "FLEX2"."D_DEPT_EVAL_SCHEME" ADD CONSTRAINT "FK_DES_CAMPID" FOREIGN KEY ("CAMP_ID")
	  REFERENCES "FLEX2"."CAMPUS" ("CAMP_ID") ENABLE;

  ALTER TABLE "FLEX2"."D_DEPT_EVAL_SCHEME" ADD CONSTRAINT "FK_DES_ETYPEID" FOREIGN KEY ("EVAL_TYPE_ID")
	  REFERENCES "FLEX2"."D_COURSE_EVALUATION" ("EVAL_TYPE_ID") ENABLE;

  ALTER TABLE "FLEX2"."D_DEPT_EVAL_SCHEME" ADD CONSTRAINT "FK_DES_SCHID" FOREIGN KEY ("SCH_ID")
	  REFERENCES "FLEX2"."SCHOOL" ("SCH_ID") ENABLE;
















--------------------------------------------------------
--  Ref Constraints for Table D_STUDY_PLAN_ELECTIVE
--------------------------------------------------------

  ALTER TABLE "FLEX2"."D_STUDY_PLAN_ELECTIVE" ADD CONSTRAINT "FK_SPE_SCHDOMID" FOREIGN KEY ("SCH_DOM_ID")
	  REFERENCES "FLEX2"."SCHOOL_DOMAIN" ("SCH_DOM_ID") ENABLE;


--------------------------------------------------------
--  Ref Constraints for Table EMPLOYEE
--------------------------------------------------------

  ALTER TABLE "FLEX2"."EMPLOYEE" ADD CONSTRAINT "FK_EMP_CAMPID" FOREIGN KEY ("CAMP_ID")
	  REFERENCES "FLEX2"."CAMPUS" ("CAMP_ID") ENABLE;

  ALTER TABLE "FLEX2"."EMPLOYEE" ADD CONSTRAINT "FK_EMP_CCID" FOREIGN KEY ("CURR_CITY")
	  REFERENCES "FLEX2"."CITY" ("CITY_ID") ENABLE;

  ALTER TABLE "FLEX2"."EMPLOYEE" ADD CONSTRAINT "FK_EMP_DEPTID" FOREIGN KEY ("DEPT_ID")
	  REFERENCES "FLEX2"."DEPARTMENT" ("DEPT_ID") ENABLE;

  ALTER TABLE "FLEX2"."EMPLOYEE" ADD CONSTRAINT "FK_EMP_DESIGNATIONID" FOREIGN KEY ("DESIGNATION_ID")
	  REFERENCES "FLEX2"."D_EMP_DESIGNATION" ("DESIGNATION_ID") ENABLE;

  ALTER TABLE "FLEX2"."EMPLOYEE" ADD CONSTRAINT "FK_EMP_EMPTID" FOREIGN KEY ("EMP_TYPE_ID")
	  REFERENCES "FLEX2"."D_EMP_TYPE" ("EMP_TYPE_ID") ENABLE;

  ALTER TABLE "FLEX2"."EMPLOYEE" ADD CONSTRAINT "FK_EMP_PCID" FOREIGN KEY ("PERM_CITY")
	  REFERENCES "FLEX2"."CITY" ("CITY_ID") ENABLE;

  ALTER TABLE "FLEX2"."EMPLOYEE" ADD CONSTRAINT "FK_EMP_PCOUNTRYID" FOREIGN KEY ("CURR_COUNTRY")
	  REFERENCES "FLEX2"."COUNTRY" ("COUNTRY_ID") ENABLE;

  ALTER TABLE "FLEX2"."EMPLOYEE" ADD CONSTRAINT "FK_EMP_SID" FOREIGN KEY ("SCH_ID")
	  REFERENCES "FLEX2"."SCHOOL" ("SCH_ID") ENABLE;
--------------------------------------------------------
--  Ref Constraints for Table EXCEPTION_DETAIL
--------------------------------------------------------

  ALTER TABLE "FLEX2"."EXCEPTION_DETAIL" ADD CONSTRAINT "FK_ROLLNO" FOREIGN KEY ("ROLL_NO")
	  REFERENCES "FLEX2"."STUDENT_PROGRAM" ("ROLL_NO") ENABLE;
--------------------------------------------------------
--  Ref Constraints for Table EXEMPTED_COURSES
--------------------------------------------------------

  ALTER TABLE "FLEX2"."EXEMPTED_COURSES" ADD CONSTRAINT "FK_EXECOURSE_COURSE" FOREIGN KEY ("COURSE_ID")
	  REFERENCES "FLEX2"."COURSE" ("COURSE_ID") ENABLE;

  ALTER TABLE "FLEX2"."EXEMPTED_COURSES" ADD CONSTRAINT "FK_EXECOURSE_ROLLNO" FOREIGN KEY ("ROLL_NO")
	  REFERENCES "FLEX2"."STUDENT_PROGRAM" ("ROLL_NO") ENABLE;


--------------------------------------------------------
--  Ref Constraints for Table FB_QUESTIONS
--------------------------------------------------------

  ALTER TABLE "FLEX2"."FB_QUESTIONS" ADD CONSTRAINT "FK_FBQCID" FOREIGN KEY ("CATEGORY_ID")
	  REFERENCES "FLEX2"."FB_QUESTIONS_CATEGORY" ("CATEGORY_ID") ENABLE;
--------------------------------------------------------
--  Ref Constraints for Table FB_QUESTIONS_CATEGORY
--------------------------------------------------------

  ALTER TABLE "FLEX2"."FB_QUESTIONS_CATEGORY" ADD CONSTRAINT "FK_FBQCPID" FOREIGN KEY ("PID")
	  REFERENCES "FLEX2"."FB_PERFORMA" ("PID") ENABLE;
--------------------------------------------------------
--  Ref Constraints for Table FB_QUESTIONS_CHOICE
--------------------------------------------------------

  ALTER TABLE "FLEX2"."FB_QUESTIONS_CHOICE" ADD CONSTRAINT "FK_QID" FOREIGN KEY ("QUESTION_ID")
	  REFERENCES "FLEX2"."FB_QUESTIONS" ("QUESTION_ID") ENABLE;
--------------------------------------------------------
--  Ref Constraints for Table FB_STUDENTREPONSE_DETAIL
--------------------------------------------------------

  ALTER TABLE "FLEX2"."FB_STUDENTREPONSE_DETAIL" ADD CONSTRAINT "FK_FBSRDOID" FOREIGN KEY ("OFFER_ID")
	  REFERENCES "FLEX2"."COURSE_OFFER" ("OFFER_ID") ENABLE;

  ALTER TABLE "FLEX2"."FB_STUDENTREPONSE_DETAIL" ADD CONSTRAINT "FK_FBSRDQID" FOREIGN KEY ("QUESTION_ID")
	  REFERENCES "FLEX2"."FB_QUESTIONS" ("QUESTION_ID") ENABLE;

  ALTER TABLE "FLEX2"."FB_STUDENTREPONSE_DETAIL" ADD CONSTRAINT "FK_FBSRDRNO" FOREIGN KEY ("ROLL_NO")
	  REFERENCES "FLEX2"."STUDENT_PROGRAM" ("ROLL_NO") ENABLE;

  ALTER TABLE "FLEX2"."FB_STUDENTREPONSE_DETAIL" ADD CONSTRAINT "FK_FBSRTDID" FOREIGN KEY ("CGPA_BAND_ID")
	  REFERENCES "FLEX2"."FB_CGPA_BAND" ("CGPA_BAND_ID") ENABLE;

--------------------------------------------------------
--  Ref Constraints for Table FB_STUDENTREPONSE_TEXT
--------------------------------------------------------

  ALTER TABLE "FLEX2"."FB_STUDENTREPONSE_TEXT" ADD CONSTRAINT "FK_FBSRTBID" FOREIGN KEY ("CGPA_BAND_ID")
	  REFERENCES "FLEX2"."FB_CGPA_BAND" ("CGPA_BAND_ID") ENABLE;

  ALTER TABLE "FLEX2"."FB_STUDENTREPONSE_TEXT" ADD CONSTRAINT "FK_FBSRTOID" FOREIGN KEY ("OFFER_ID")
	  REFERENCES "FLEX2"."COURSE_OFFER" ("OFFER_ID") ENABLE;

  ALTER TABLE "FLEX2"."FB_STUDENTREPONSE_TEXT" ADD CONSTRAINT "FK_FBSRTQID" FOREIGN KEY ("QUESTION_ID")
	  REFERENCES "FLEX2"."FB_QUESTIONS" ("QUESTION_ID") ENABLE;

  ALTER TABLE "FLEX2"."FB_STUDENTREPONSE_TEXT" ADD CONSTRAINT "FK_FBSRTRNO" FOREIGN KEY ("ROLL_NO")
	  REFERENCES "FLEX2"."STUDENT_PROGRAM" ("ROLL_NO") ENABLE;



--------------------------------------------------------
--  Ref Constraints for Table FMBANKSCROLLDETAIL
--------------------------------------------------------

  ALTER TABLE "FLEX2"."FMBANKSCROLLDETAIL" ADD CONSTRAINT "FK_FMBSDARN" FOREIGN KEY ("ARN")
	  REFERENCES "FLEX2"."STUDENT_PERSONAL_INFO" ("ARN") ENABLE;

  ALTER TABLE "FLEX2"."FMBANKSCROLLDETAIL" ADD CONSTRAINT "FK_FMBSDRNO" FOREIGN KEY ("ROLLNO")
	  REFERENCES "FLEX2"."STUDENT_PROGRAM" ("ROLL_NO") ENABLE;
--------------------------------------------------------
--  Ref Constraints for Table FMCHALLAN
--------------------------------------------------------

  ALTER TABLE "FLEX2"."FMCHALLAN" ADD CONSTRAINT "FK_FMC_ARN" FOREIGN KEY ("ARN")
	  REFERENCES "FLEX2"."STUDENT_PERSONAL_INFO" ("ARN") ENABLE;

  ALTER TABLE "FLEX2"."FMCHALLAN" ADD CONSTRAINT "FK_FMC_CAMPUSID" FOREIGN KEY ("CAMPUSID")
	  REFERENCES "FLEX2"."CAMPUS" ("CAMP_ID") ENABLE;

  ALTER TABLE "FLEX2"."FMCHALLAN" ADD CONSTRAINT "FK_FMC_ROLLNO" FOREIGN KEY ("ROLLNO")
	  REFERENCES "FLEX2"."STUDENT_PROGRAM" ("ROLL_NO") ENABLE;

  ALTER TABLE "FLEX2"."FMCHALLAN" ADD CONSTRAINT "FK_FMC_SEMID" FOREIGN KEY ("SEMID")
	  REFERENCES "FLEX2"."SEMESTER" ("SEM_ID") ENABLE;
--------------------------------------------------------
--  Ref Constraints for Table FMCHALLANDETAIL
--------------------------------------------------------

  ALTER TABLE "FLEX2"."FMCHALLANDETAIL" ADD CONSTRAINT "FK_FMCD_SUBHEADID" FOREIGN KEY ("SUBHEADID")
	  REFERENCES "FLEX2"."FMSUBHEAD" ("SUBHEADID") ENABLE;

--------------------------------------------------------
--  Ref Constraints for Table FMDEFAULTEREXCEPTION
--------------------------------------------------------

  ALTER TABLE "FLEX2"."FMDEFAULTEREXCEPTION" ADD CONSTRAINT "FK_FMDE_CAMPUSID" FOREIGN KEY ("CAMPUSID")
	  REFERENCES "FLEX2"."CAMPUS" ("CAMP_ID") ENABLE;

  ALTER TABLE "FLEX2"."FMDEFAULTEREXCEPTION" ADD CONSTRAINT "FK_FMDE_ROLLNO" FOREIGN KEY ("ROLLNO")
	  REFERENCES "FLEX2"."STUDENT_PROGRAM" ("ROLL_NO") ENABLE;

  ALTER TABLE "FLEX2"."FMDEFAULTEREXCEPTION" ADD CONSTRAINT "FK_FMDE_SEMID" FOREIGN KEY ("SEMID")
	  REFERENCES "FLEX2"."SEMESTER" ("SEM_ID") ENABLE;

--------------------------------------------------------
--  Ref Constraints for Table FMFEEDATES
--------------------------------------------------------

  ALTER TABLE "FLEX2"."FMFEEDATES" ADD CONSTRAINT "FK_BATCH_FMFEEDUEDATE" FOREIGN KEY ("BATCHNO")
	  REFERENCES "FLEX2"."BATCH" ("BATCH_NO") ENABLE;

  ALTER TABLE "FLEX2"."FMFEEDATES" ADD CONSTRAINT "FK_FMFEEDUEDATE_CAMPUS" FOREIGN KEY ("CAMPUSID")
	  REFERENCES "FLEX2"."CAMPUS" ("CAMP_ID") ENABLE;

  ALTER TABLE "FLEX2"."FMFEEDATES" ADD CONSTRAINT "FK_FMFEEDUEDATE_PROGID" FOREIGN KEY ("PROGRAMID")
	  REFERENCES "FLEX2"."PROGRAM" ("PROG_ID") ENABLE;

  ALTER TABLE "FLEX2"."FMFEEDATES" ADD CONSTRAINT "FK_FMFEEDUEDATE_SECTION" FOREIGN KEY ("SECTIONID")
	  REFERENCES "FLEX2"."SECTION" ("SECTION_ID") ENABLE;
--------------------------------------------------------
--  Ref Constraints for Table FMFEERATES
--------------------------------------------------------

  ALTER TABLE "FLEX2"."FMFEERATES" ADD CONSTRAINT "FK_FMFRSID" FOREIGN KEY ("SUBHEADID")
	  REFERENCES "FLEX2"."FMSUBHEAD" ("SUBHEADID") ENABLE;

  ALTER TABLE "FLEX2"."FMFEERATES" ADD CONSTRAINT "FK_FMR_PL" FOREIGN KEY ("PROGRAMLEVEL")
	  REFERENCES "FLEX2"."D_PROGRAM_LEVEL" ("LEVEL_ID") ENABLE;

  ALTER TABLE "FLEX2"."FMFEERATES" ADD CONSTRAINT "PK_FMFRBNO" FOREIGN KEY ("BATCHNO")
	  REFERENCES "FLEX2"."BATCH" ("BATCH_NO") ENABLE;

  ALTER TABLE "FLEX2"."FMFEERATES" ADD CONSTRAINT "PK_FMFRCID" FOREIGN KEY ("CAMPUSID")
	  REFERENCES "FLEX2"."CAMPUS" ("CAMP_ID") ENABLE;

  ALTER TABLE "FLEX2"."FMFEERATES" ADD CONSTRAINT "PK_FMFRPID" FOREIGN KEY ("PROGRAMID")
	  REFERENCES "FLEX2"."PROGRAM" ("PROG_ID") ENABLE;

  ALTER TABLE "FLEX2"."FMFEERATES" ADD CONSTRAINT "PK_FMFRSID" FOREIGN KEY ("SEMID")
	  REFERENCES "FLEX2"."SEMESTER" ("SEM_ID") ENABLE;


--------------------------------------------------------
--  Ref Constraints for Table FMINSTALLMENTS
--------------------------------------------------------

  ALTER TABLE "FLEX2"."FMINSTALLMENTS" ADD CONSTRAINT "FK_FMIARN" FOREIGN KEY ("ARN")
	  REFERENCES "FLEX2"."STUDENT_PERSONAL_INFO" ("ARN") ENABLE;

  ALTER TABLE "FLEX2"."FMINSTALLMENTS" ADD CONSTRAINT "FK_FMICID" FOREIGN KEY ("CAMPUSID")
	  REFERENCES "FLEX2"."CAMPUS" ("CAMP_ID") ENABLE;

  ALTER TABLE "FLEX2"."FMINSTALLMENTS" ADD CONSTRAINT "FK_FMIRNO" FOREIGN KEY ("ROLLNO")
	  REFERENCES "FLEX2"."STUDENT_PROGRAM" ("ROLL_NO") ENABLE;

  ALTER TABLE "FLEX2"."FMINSTALLMENTS" ADD CONSTRAINT "FK_FMISID" FOREIGN KEY ("SEMID")
	  REFERENCES "FLEX2"."SEMESTER" ("SEM_ID") ENABLE;





--------------------------------------------------------
--  Ref Constraints for Table FMLEDGER_REGLOG
--------------------------------------------------------

  ALTER TABLE "FLEX2"."FMLEDGER_REGLOG" ADD CONSTRAINT "FK_FLR_CAMPUSID" FOREIGN KEY ("CAMPUSID")
	  REFERENCES "FLEX2"."CAMPUS" ("CAMP_ID") ENABLE;

  ALTER TABLE "FLEX2"."FMLEDGER_REGLOG" ADD CONSTRAINT "FMLEDGER_REGLOG_R01" FOREIGN KEY ("REGLOGID")
	  REFERENCES "FLEX2"."REGISTRATIONLOG" ("REGLOGID") ENABLE;

--------------------------------------------------------
--  Ref Constraints for Table FMLEDGER_SCROLLDETAIL
--------------------------------------------------------

  ALTER TABLE "FLEX2"."FMLEDGER_SCROLLDETAIL" ADD CONSTRAINT "FK_FLS_CAMPUSID" FOREIGN KEY ("CAMPUSID")
	  REFERENCES "FLEX2"."CAMPUS" ("CAMP_ID") ENABLE;

  ALTER TABLE "FLEX2"."FMLEDGER_SCROLLDETAIL" ADD CONSTRAINT "FK_FLS_SCROLLDETAILID" FOREIGN KEY ("SCROLLDETAILID")
	  REFERENCES "FLEX2"."FMSCROLLDETAIL" ("SCROLLDETAILID") ENABLE;



--------------------------------------------------------
--  Ref Constraints for Table FMLEDGER_STUDENTSPONS
--------------------------------------------------------

  ALTER TABLE "FLEX2"."FMLEDGER_STUDENTSPONS" ADD CONSTRAINT "FK_FLSS_CAMPUSID" FOREIGN KEY ("CAMPUSID")
	  REFERENCES "FLEX2"."CAMPUS" ("CAMP_ID") ENABLE;

  ALTER TABLE "FLEX2"."FMLEDGER_STUDENTSPONS" ADD CONSTRAINT "FK_FLSS_STUDENTSPONSID" FOREIGN KEY ("STUDENTSPONSID")
	  REFERENCES "FLEX2"."FMSPONSOREDSTUDENT" ("STUDENT_SPONSID") ENABLE;
--------------------------------------------------------
--  Ref Constraints for Table FMPAYMENTMODE
--------------------------------------------------------

  ALTER TABLE "FLEX2"."FMPAYMENTMODE" ADD CONSTRAINT "PAYMENTTYPE_FK" FOREIGN KEY ("PAYMENTTYPE")
	  REFERENCES "FLEX2"."FMPAYMENTTYPE" ("PAYMENTTYPE") ENABLE;


--------------------------------------------------------
--  Ref Constraints for Table FMREFUND
--------------------------------------------------------

  ALTER TABLE "FLEX2"."FMREFUND" ADD CONSTRAINT "FK_FMRFIDCID" FOREIGN KEY ("CAMPUSID")
	  REFERENCES "FLEX2"."CAMPUS" ("CAMP_ID") ENABLE;

  ALTER TABLE "FLEX2"."FMREFUND" ADD CONSTRAINT "FK_FMRFIDRNO" FOREIGN KEY ("ROLLNO")
	  REFERENCES "FLEX2"."STUDENT_PROGRAM" ("ROLL_NO") ENABLE;

  ALTER TABLE "FLEX2"."FMREFUND" ADD CONSTRAINT "FK_FMRFIDSID" FOREIGN KEY ("SEMID")
	  REFERENCES "FLEX2"."SEMESTER" ("SEM_ID") ENABLE;


--------------------------------------------------------
--  Ref Constraints for Table FMSCROLLDETAIL
--------------------------------------------------------

  ALTER TABLE "FLEX2"."FMSCROLLDETAIL" ADD CONSTRAINT "FK_FSD_ARN" FOREIGN KEY ("ARN")
	  REFERENCES "FLEX2"."STUDENT_PERSONAL_INFO" ("ARN") ENABLE;

  ALTER TABLE "FLEX2"."FMSCROLLDETAIL" ADD CONSTRAINT "FK_FSD_CAMPUSID" FOREIGN KEY ("CAMPUSID")
	  REFERENCES "FLEX2"."CAMPUS" ("CAMP_ID") ENABLE;

  ALTER TABLE "FLEX2"."FMSCROLLDETAIL" ADD CONSTRAINT "FK_FSD_PAYMENTMODEID" FOREIGN KEY ("PAYMENTMODEID")
	  REFERENCES "FLEX2"."FMPAYMENTMODE" ("PAYMENTMODEID") ENABLE;

  ALTER TABLE "FLEX2"."FMSCROLLDETAIL" ADD CONSTRAINT "FK_FSD_SEMID" FOREIGN KEY ("SEMID")
	  REFERENCES "FLEX2"."SEMESTER" ("SEM_ID") ENABLE;



--------------------------------------------------------
--  Ref Constraints for Table FMSCROLLSUMMARY
--------------------------------------------------------

  ALTER TABLE "FLEX2"."FMSCROLLSUMMARY" ADD CONSTRAINT "FK_FSSUM_CAMPUSID" FOREIGN KEY ("CAMPUSID")
	  REFERENCES "FLEX2"."CAMPUS" ("CAMP_ID") ENABLE;


--------------------------------------------------------
--  Ref Constraints for Table FMSPONSOREDSTUDENT
--------------------------------------------------------

  ALTER TABLE "FLEX2"."FMSPONSOREDSTUDENT" ADD CONSTRAINT "FK_FSSTD_ARN" FOREIGN KEY ("ARN")
	  REFERENCES "FLEX2"."STUDENT_PERSONAL_INFO" ("ARN") ENABLE;

  ALTER TABLE "FLEX2"."FMSPONSOREDSTUDENT" ADD CONSTRAINT "FK_FSSTD_CAMPUSID" FOREIGN KEY ("CAMPUSID")
	  REFERENCES "FLEX2"."CAMPUS" ("CAMP_ID") ENABLE;

  ALTER TABLE "FLEX2"."FMSPONSOREDSTUDENT" ADD CONSTRAINT "FK_FSSTD_ROLLNO" FOREIGN KEY ("ROLLNO")
	  REFERENCES "FLEX2"."STUDENT_PROGRAM" ("ROLL_NO") ENABLE;

  ALTER TABLE "FLEX2"."FMSPONSOREDSTUDENT" ADD CONSTRAINT "FK_FSSTD_SPONSORSHIPID" FOREIGN KEY ("SPONSORSHIPID")
	  REFERENCES "FLEX2"."FMSPONSORSHIP" ("SPONSORSHIPID") ENABLE;

  ALTER TABLE "FLEX2"."FMSPONSOREDSTUDENT" ADD CONSTRAINT "FK_FSSTD_SUBHEADID" FOREIGN KEY ("SUBHEADID")
	  REFERENCES "FLEX2"."FMSUBHEAD" ("SUBHEADID") ENABLE;
--------------------------------------------------------
--  Ref Constraints for Table FMSPONSORSHIP
--------------------------------------------------------

  ALTER TABLE "FLEX2"."FMSPONSORSHIP" ADD CONSTRAINT "FK_FSPON_CAMPUSID" FOREIGN KEY ("CAMPUSID")
	  REFERENCES "FLEX2"."CAMPUS" ("CAMP_ID") ENABLE;
--------------------------------------------------------
--  Ref Constraints for Table FMSPONSORSHIPDETAIL
--------------------------------------------------------

  ALTER TABLE "FLEX2"."FMSPONSORSHIPDETAIL" ADD CONSTRAINT "SPONSORSHIPID_FK" FOREIGN KEY ("SPONSORSHIPID")
	  REFERENCES "FLEX2"."FMSPONSORSHIP" ("SPONSORSHIPID") ENABLE;

--------------------------------------------------------
--  Ref Constraints for Table FMSTUDENTFEETYPE
--------------------------------------------------------

  ALTER TABLE "FLEX2"."FMSTUDENTFEETYPE" ADD CONSTRAINT "FK_FMSTCID" FOREIGN KEY ("CAMPUSID")
	  REFERENCES "FLEX2"."CAMPUS" ("CAMP_ID") ENABLE;

  ALTER TABLE "FLEX2"."FMSTUDENTFEETYPE" ADD CONSTRAINT "FK_FMSTFTID" FOREIGN KEY ("FEETYPEID")
	  REFERENCES "FLEX2"."FMFEETYPE" ("FEETYPEID") ENABLE;

  ALTER TABLE "FLEX2"."FMSTUDENTFEETYPE" ADD CONSTRAINT "FK_FMSTRNO" FOREIGN KEY ("ROLLNO")
	  REFERENCES "FLEX2"."STUDENT_PROGRAM" ("ROLL_NO") ENABLE;

  ALTER TABLE "FLEX2"."FMSTUDENTFEETYPE" ADD CONSTRAINT "FK_FMSTSID" FOREIGN KEY ("SEMID")
	  REFERENCES "FLEX2"."SEMESTER" ("SEM_ID") ENABLE;


--------------------------------------------------------
--  Ref Constraints for Table FMSUBHEAD
--------------------------------------------------------

  ALTER TABLE "FLEX2"."FMSUBHEAD" ADD CONSTRAINT "FK_FMSBHD_HEADID" FOREIGN KEY ("HEADID")
	  REFERENCES "FLEX2"."FMHEAD" ("HEADID") ENABLE;






--------------------------------------------------------
--  Ref Constraints for Table GRADEPOLICY
--------------------------------------------------------

  ALTER TABLE "FLEX2"."GRADEPOLICY" ADD CONSTRAINT "GP_GRADEID" FOREIGN KEY ("GRADE_ID")
	  REFERENCES "FLEX2"."GRADE" ("GRADE_ID") ENABLE;

  ALTER TABLE "FLEX2"."GRADEPOLICY" ADD CONSTRAINT "GP_GRADEPOLICYID" FOREIGN KEY ("GRADEPOLICYID")
	  REFERENCES "FLEX2"."GRADEPOLICY_DETAIL" ("GRADEPOLICYID") ENABLE;
--------------------------------------------------------
--  Ref Constraints for Table GRADEPOLICY_COURSE
--------------------------------------------------------

  ALTER TABLE "FLEX2"."GRADEPOLICY_COURSE" ADD CONSTRAINT "GPC_COURSEID" FOREIGN KEY ("COURSE_ID")
	  REFERENCES "FLEX2"."COURSE" ("COURSE_ID") ENABLE;

  ALTER TABLE "FLEX2"."GRADEPOLICY_COURSE" ADD CONSTRAINT "GPC_GRADEPOLICYID" FOREIGN KEY ("GRADEPOLICYID")
	  REFERENCES "FLEX2"."GRADEPOLICY_DETAIL" ("GRADEPOLICYID") ENABLE;



--------------------------------------------------------
--  Ref Constraints for Table GRADING_ZFACTOR
--------------------------------------------------------

  ALTER TABLE "FLEX2"."GRADING_ZFACTOR" ADD CONSTRAINT "FK_GZFGID" FOREIGN KEY ("GRADE_ID")
	  REFERENCES "FLEX2"."GRADE" ("GRADE_ID") ENABLE;

  ALTER TABLE "FLEX2"."GRADING_ZFACTOR" ADD CONSTRAINT "FK_GZFGSID" FOREIGN KEY ("GS_ID")
	  REFERENCES "FLEX2"."GRADING_SCHEME" ("GS_ID") ENABLE;


--------------------------------------------------------
--  Ref Constraints for Table INSTR_COURSE_PREF
--------------------------------------------------------

  ALTER TABLE "FLEX2"."INSTR_COURSE_PREF" ADD CONSTRAINT "FK_ICP_COURSEID" FOREIGN KEY ("COURSE_ID")
	  REFERENCES "FLEX2"."COURSE" ("COURSE_ID") ENABLE;

  ALTER TABLE "FLEX2"."INSTR_COURSE_PREF" ADD CONSTRAINT "FK_ICP_EMPID" FOREIGN KEY ("EMP_ID")
	  REFERENCES "FLEX2"."EMPLOYEE" ("EMP_ID") ENABLE;

  ALTER TABLE "FLEX2"."INSTR_COURSE_PREF" ADD CONSTRAINT "FK_ICP_SEMID" FOREIGN KEY ("SEM_ID")
	  REFERENCES "FLEX2"."SEMESTER" ("SEM_ID") ENABLE;
--------------------------------------------------------
--  Ref Constraints for Table LECTURE
--------------------------------------------------------

  ALTER TABLE "FLEX2"."LECTURE" ADD CONSTRAINT "FK_LEC_OFFERID" FOREIGN KEY ("OFFER_ID")
	  REFERENCES "FLEX2"."COURSE_OFFER" ("OFFER_ID") ENABLE;




--------------------------------------------------------
--  Ref Constraints for Table ORA_ASPNET_MEMBERSHIP
--------------------------------------------------------

  ALTER TABLE "FLEX2"."ORA_ASPNET_MEMBERSHIP" ADD CONSTRAINT "FK_MEMBERSHIP_APPID" FOREIGN KEY ("APPLICATIONID")
	  REFERENCES "FLEX2"."ORA_ASPNET_APPLICATIONS" ("APPLICATIONID") ENABLE;

  ALTER TABLE "FLEX2"."ORA_ASPNET_MEMBERSHIP" ADD CONSTRAINT "FK_MEMBERSHIP_USERID" FOREIGN KEY ("USERID")
	  REFERENCES "FLEX2"."ORA_ASPNET_USERS" ("USERID") ENABLE;
--------------------------------------------------------
--  Ref Constraints for Table ORA_ASPNET_PATHS
--------------------------------------------------------

  ALTER TABLE "FLEX2"."ORA_ASPNET_PATHS" ADD CONSTRAINT "FK_PATHS_APPID" FOREIGN KEY ("APPLICATIONID")
	  REFERENCES "FLEX2"."ORA_ASPNET_APPLICATIONS" ("APPLICATIONID") ENABLE;
--------------------------------------------------------
--  Ref Constraints for Table ORA_ASPNET_PERSONALIZNALLUSERS
--------------------------------------------------------

  ALTER TABLE "FLEX2"."ORA_ASPNET_PERSONALIZNALLUSERS" ADD CONSTRAINT "PERSONALIZATIONALLUSERS_PATHID" FOREIGN KEY ("PATHID")
	  REFERENCES "FLEX2"."ORA_ASPNET_PATHS" ("PATHID") ON DELETE CASCADE ENABLE;
--------------------------------------------------------
--  Ref Constraints for Table ORA_ASPNET_PERSONALIZNPERUSER
--------------------------------------------------------

  ALTER TABLE "FLEX2"."ORA_ASPNET_PERSONALIZNPERUSER" ADD CONSTRAINT "PERSONALIZATIONPERUSER_PATHID" FOREIGN KEY ("PATHID")
	  REFERENCES "FLEX2"."ORA_ASPNET_PATHS" ("PATHID") ENABLE;

  ALTER TABLE "FLEX2"."ORA_ASPNET_PERSONALIZNPERUSER" ADD CONSTRAINT "PERSONALIZATIONPERUSER_USERID" FOREIGN KEY ("USERID")
	  REFERENCES "FLEX2"."ORA_ASPNET_USERS" ("USERID") ENABLE;
--------------------------------------------------------
--  Ref Constraints for Table ORA_ASPNET_PROFILE
--------------------------------------------------------

  ALTER TABLE "FLEX2"."ORA_ASPNET_PROFILE" ADD CONSTRAINT "FK_PROFILE_USERID" FOREIGN KEY ("USERID")
	  REFERENCES "FLEX2"."ORA_ASPNET_USERS" ("USERID") ENABLE;
--------------------------------------------------------
--  Ref Constraints for Table ORA_ASPNET_ROLES
--------------------------------------------------------

  ALTER TABLE "FLEX2"."ORA_ASPNET_ROLES" ADD CONSTRAINT "FK_APPLICATIONID" FOREIGN KEY ("APPLICATIONID")
	  REFERENCES "FLEX2"."ORA_ASPNET_APPLICATIONS" ("APPLICATIONID") ENABLE;


--------------------------------------------------------
--  Ref Constraints for Table ORA_ASPNET_SITEMAP
--------------------------------------------------------

  ALTER TABLE "FLEX2"."ORA_ASPNET_SITEMAP" ADD CONSTRAINT "FK_SITEMAP_APPID" FOREIGN KEY ("APPLICATIONID")
	  REFERENCES "FLEX2"."ORA_ASPNET_APPLICATIONS" ("APPLICATIONID") ON DELETE CASCADE ENABLE;
--------------------------------------------------------
--  Ref Constraints for Table ORA_ASPNET_USERS
--------------------------------------------------------

  ALTER TABLE "FLEX2"."ORA_ASPNET_USERS" ADD CONSTRAINT "FK_USERS_APPID" FOREIGN KEY ("APPLICATIONID")
	  REFERENCES "FLEX2"."ORA_ASPNET_APPLICATIONS" ("APPLICATIONID") ENABLE;
--------------------------------------------------------
--  Ref Constraints for Table ORA_ASPNET_USERSINROLES
--------------------------------------------------------

  ALTER TABLE "FLEX2"."ORA_ASPNET_USERSINROLES" ADD CONSTRAINT "FK_ASPNET_USERSINROLES_ROLEID" FOREIGN KEY ("ROLEID")
	  REFERENCES "FLEX2"."ORA_ASPNET_ROLES" ("ROLEID") ENABLE;

  ALTER TABLE "FLEX2"."ORA_ASPNET_USERSINROLES" ADD CONSTRAINT "FK_ASPNET_USERSINROLES_USERID" FOREIGN KEY ("USERID")
	  REFERENCES "FLEX2"."ORA_ASPNET_USERS" ("USERID") ENABLE;

















--------------------------------------------------------
--  Ref Constraints for Table PROGRAM
--------------------------------------------------------

  ALTER TABLE "FLEX2"."PROGRAM" ADD CONSTRAINT "FK_PROGRAM_LEVELID" FOREIGN KEY ("LEVEL_ID")
	  REFERENCES "FLEX2"."D_PROGRAM_LEVEL" ("LEVEL_ID") ENABLE;

  ALTER TABLE "FLEX2"."PROGRAM" ADD CONSTRAINT "FK_PROGRAM_SCHID" FOREIGN KEY ("SCH_ID")
	  REFERENCES "FLEX2"."SCHOOL" ("SCH_ID") ENABLE;

--------------------------------------------------------
--  Ref Constraints for Table PROGRAM_COURSE
--------------------------------------------------------

  ALTER TABLE "FLEX2"."PROGRAM_COURSE" ADD CONSTRAINT "FK_PC_COURSEID" FOREIGN KEY ("COURSE_ID")
	  REFERENCES "FLEX2"."COURSE" ("COURSE_ID") ENABLE;

  ALTER TABLE "FLEX2"."PROGRAM_COURSE" ADD CONSTRAINT "FK_PRC_BATCHNO" FOREIGN KEY ("BATCH_NO")
	  REFERENCES "FLEX2"."BATCH" ("BATCH_NO") ENABLE;

  ALTER TABLE "FLEX2"."PROGRAM_COURSE" ADD CONSTRAINT "FK_PRC_PROGID" FOREIGN KEY ("PROG_ID")
	  REFERENCES "FLEX2"."PROGRAM" ("PROG_ID") ENABLE;

  ALTER TABLE "FLEX2"."PROGRAM_COURSE" ADD CONSTRAINT "FK_PRC_RELATIONID" FOREIGN KEY ("RELATOIN_ID")
	  REFERENCES "FLEX2"."D_COURSE_RELATION" ("RELATION_ID") ENABLE;
--------------------------------------------------------
--  Ref Constraints for Table PROG_BATCH_DOMAIN
--------------------------------------------------------

  ALTER TABLE "FLEX2"."PROG_BATCH_DOMAIN" ADD CONSTRAINT "FK_PBD_BATCHNO" FOREIGN KEY ("BATCH_NO")
	  REFERENCES "FLEX2"."BATCH" ("BATCH_NO") ENABLE;

  ALTER TABLE "FLEX2"."PROG_BATCH_DOMAIN" ADD CONSTRAINT "FK_PBD_PROGID" FOREIGN KEY ("PROG_ID")
	  REFERENCES "FLEX2"."PROGRAM" ("PROG_ID") ENABLE;

  ALTER TABLE "FLEX2"."PROG_BATCH_DOMAIN" ADD CONSTRAINT "FK_PBD_SCHDOMID" FOREIGN KEY ("SCH_DOM_ID")
	  REFERENCES "FLEX2"."SCHOOL_DOMAIN" ("SCH_DOM_ID") ENABLE;



--------------------------------------------------------
--  Ref Constraints for Table REPEAT_COURSE
--------------------------------------------------------

  ALTER TABLE "FLEX2"."REPEAT_COURSE" ADD CONSTRAINT "FK_RC_OID" FOREIGN KEY ("OFFER_ID")
	  REFERENCES "FLEX2"."COURSE_OFFER" ("OFFER_ID") ENABLE;

  ALTER TABLE "FLEX2"."REPEAT_COURSE" ADD CONSTRAINT "FK_RC_UID" FOREIGN KEY ("USER_ID")
	  REFERENCES "FLEX2"."APPUSER" ("USERID") ENABLE;
--------------------------------------------------------
--  Ref Constraints for Table ROLLNO_RANGE
--------------------------------------------------------

  ALTER TABLE "FLEX2"."ROLLNO_RANGE" ADD CONSTRAINT "FK_RRC_ID" FOREIGN KEY ("CAMP_ID")
	  REFERENCES "FLEX2"."CAMPUS" ("CAMP_ID") ENABLE;

  ALTER TABLE "FLEX2"."ROLLNO_RANGE" ADD CONSTRAINT "FK_RRP_ID" FOREIGN KEY ("PROG_ID")
	  REFERENCES "FLEX2"."PROGRAM" ("PROG_ID") ENABLE;

  ALTER TABLE "FLEX2"."ROLLNO_RANGE" ADD CONSTRAINT "FK_RRS_ID" FOREIGN KEY ("SCHOOL_ID")
	  REFERENCES "FLEX2"."SCHOOL" ("SCH_ID") ENABLE;

--------------------------------------------------------
--  Ref Constraints for Table SCHOOL_DOMAIN
--------------------------------------------------------

  ALTER TABLE "FLEX2"."SCHOOL_DOMAIN" ADD CONSTRAINT "FK_SCHOOL_DOMAIN_SCHOOL_SCH_ID" FOREIGN KEY ("SCH_ID")
	  REFERENCES "FLEX2"."SCHOOL" ("SCH_ID") ENABLE;


--------------------------------------------------------
--  Ref Constraints for Table SEM_TEACHER_ACTIVITY
--------------------------------------------------------

  ALTER TABLE "FLEX2"."SEM_TEACHER_ACTIVITY" ADD CONSTRAINT "FK_STA_ACTID" FOREIGN KEY ("ACT_ID")
	  REFERENCES "FLEX2"."D_TEACHER_ACTIVITY" ("ACT_ID") ENABLE;

  ALTER TABLE "FLEX2"."SEM_TEACHER_ACTIVITY" ADD CONSTRAINT "FK_STA_EMPID" FOREIGN KEY ("EMP_ID")
	  REFERENCES "FLEX2"."EMPLOYEE" ("EMP_ID") ENABLE;

  ALTER TABLE "FLEX2"."SEM_TEACHER_ACTIVITY" ADD CONSTRAINT "FK_STA_SEMID" FOREIGN KEY ("SEM_ID")
	  REFERENCES "FLEX2"."SEMESTER" ("SEM_ID") ENABLE;
--------------------------------------------------------
--  Ref Constraints for Table STUDENT_ATTENDANCE
--------------------------------------------------------

  ALTER TABLE "FLEX2"."STUDENT_ATTENDANCE" ADD CONSTRAINT "FK_STA_LECTUREID" FOREIGN KEY ("LECTURE_ID")
	  REFERENCES "FLEX2"."LECTURE" ("LECTURE_ID") ENABLE;

  ALTER TABLE "FLEX2"."STUDENT_ATTENDANCE" ADD CONSTRAINT "FK_STA_ROLLNO" FOREIGN KEY ("ROLL_NO")
	  REFERENCES "FLEX2"."STUDENT_PROGRAM" ("ROLL_NO") ENABLE;
--------------------------------------------------------
--  Ref Constraints for Table STUDENT_FAMILY_INFO
--------------------------------------------------------

  ALTER TABLE "FLEX2"."STUDENT_FAMILY_INFO" ADD CONSTRAINT "FK_SFI_ARN" FOREIGN KEY ("ARN")
	  REFERENCES "FLEX2"."STUDENT_PERSONAL_INFO" ("ARN") ENABLE;

  ALTER TABLE "FLEX2"."STUDENT_FAMILY_INFO" ADD CONSTRAINT "FK_SFI_RELTYPEID" FOREIGN KEY ("REL_TYPE_ID")
	  REFERENCES "FLEX2"."D_FAMILY_RELATION" ("REL_TYPE_ID") ENABLE;
--------------------------------------------------------
--  Ref Constraints for Table STUDENT_PERSONAL_INFO
--------------------------------------------------------

  ALTER TABLE "FLEX2"."STUDENT_PERSONAL_INFO" ADD CONSTRAINT "FK_SPI_CAMPID" FOREIGN KEY ("CAMP_ID")
	  REFERENCES "FLEX2"."CAMPUS" ("CAMP_ID") ENABLE;

  ALTER TABLE "FLEX2"."STUDENT_PERSONAL_INFO" ADD CONSTRAINT "FK_SPI_CCID" FOREIGN KEY ("CURR_CITY")
	  REFERENCES "FLEX2"."CITY" ("CITY_ID") ENABLE;

  ALTER TABLE "FLEX2"."STUDENT_PERSONAL_INFO" ADD CONSTRAINT "FK_SPI_CID" FOREIGN KEY ("CURR_COUNTRY")
	  REFERENCES "FLEX2"."COUNTRY" ("COUNTRY_ID") ENABLE;

  ALTER TABLE "FLEX2"."STUDENT_PERSONAL_INFO" ADD CONSTRAINT "FK_SPI_PCID" FOREIGN KEY ("PERM_COUNTRY")
	  REFERENCES "FLEX2"."COUNTRY" ("COUNTRY_ID") ENABLE;

  ALTER TABLE "FLEX2"."STUDENT_PERSONAL_INFO" ADD CONSTRAINT "FK_SPI_PCITYID" FOREIGN KEY ("PERM_CITY")
	  REFERENCES "FLEX2"."CITY" ("CITY_ID") ENABLE;
--------------------------------------------------------
--  Ref Constraints for Table STUDENT_PROGRAM
--------------------------------------------------------

  ALTER TABLE "FLEX2"."STUDENT_PROGRAM" ADD CONSTRAINT "FK_STP_ARN" FOREIGN KEY ("ARN")
	  REFERENCES "FLEX2"."STUDENT_PERSONAL_INFO" ("ARN") ENABLE;

  ALTER TABLE "FLEX2"."STUDENT_PROGRAM" ADD CONSTRAINT "FK_STP_BATCHNO" FOREIGN KEY ("BATCH_NO")
	  REFERENCES "FLEX2"."BATCH" ("BATCH_NO") ENABLE;

  ALTER TABLE "FLEX2"."STUDENT_PROGRAM" ADD CONSTRAINT "FK_STP_CAMPID" FOREIGN KEY ("CAMP_ID")
	  REFERENCES "FLEX2"."CAMPUS" ("CAMP_ID") ENABLE;

  ALTER TABLE "FLEX2"."STUDENT_PROGRAM" ADD CONSTRAINT "FK_STP_CURRCAMPID" FOREIGN KEY ("CURR_CAMP_ID")
	  REFERENCES "FLEX2"."CAMPUS" ("CAMP_ID") ENABLE;

  ALTER TABLE "FLEX2"."STUDENT_PROGRAM" ADD CONSTRAINT "FK_STP_PROGID" FOREIGN KEY ("PROG_ID")
	  REFERENCES "FLEX2"."PROGRAM" ("PROG_ID") ENABLE;

  ALTER TABLE "FLEX2"."STUDENT_PROGRAM" ADD CONSTRAINT "FK_STP_PROGSTATUS" FOREIGN KEY ("PROG_STATUS")
	  REFERENCES "FLEX2"."D_STUDENT_STATUS" ("STATUS_ID") ENABLE;

  ALTER TABLE "FLEX2"."STUDENT_PROGRAM" ADD CONSTRAINT "FK_STP_REGSTATUS" FOREIGN KEY ("REG_STATUS")
	  REFERENCES "FLEX2"."D_STUDENT_REG_STATUS" ("STATUS_ID") ENABLE;

  ALTER TABLE "FLEX2"."STUDENT_PROGRAM" ADD CONSTRAINT "FK_STP_SECTIONID" FOREIGN KEY ("STU_SECTION_ID")
	  REFERENCES "FLEX2"."SECTION" ("SECTION_ID") ENABLE;
--------------------------------------------------------
--  Ref Constraints for Table STUDENT_QUALIFICATION
--------------------------------------------------------

  ALTER TABLE "FLEX2"."STUDENT_QUALIFICATION" ADD CONSTRAINT "FK_SQ_CID" FOREIGN KEY ("CITY")
	  REFERENCES "FLEX2"."CITY" ("CITY_ID") ENABLE;

  ALTER TABLE "FLEX2"."STUDENT_QUALIFICATION" ADD CONSTRAINT "FK_SQ_DTID" FOREIGN KEY ("DEGREE")
	  REFERENCES "FLEX2"."D_DEGREE_TYPE" ("DT_ID") ENABLE;

  ALTER TABLE "FLEX2"."STUDENT_QUALIFICATION" ADD CONSTRAINT "FK_SQ_SPIARN" FOREIGN KEY ("ARN")
	  REFERENCES "FLEX2"."STUDENT_PERSONAL_INFO" ("ARN") ENABLE;
--------------------------------------------------------
--  Ref Constraints for Table STUDENT_REMARKS_HISTORY
--------------------------------------------------------

  ALTER TABLE "FLEX2"."STUDENT_REMARKS_HISTORY" ADD CONSTRAINT "FK_SRH_ROLLNO" FOREIGN KEY ("ROLL_NO")
	  REFERENCES "FLEX2"."STUDENT_PROGRAM" ("ROLL_NO") ENABLE;
--------------------------------------------------------
--  Ref Constraints for Table STUDENT_SEMESTER
--------------------------------------------------------

  ALTER TABLE "FLEX2"."STUDENT_SEMESTER" ADD CONSTRAINT "FK_STS_CAMPID" FOREIGN KEY ("CAMP_ID")
	  REFERENCES "FLEX2"."CAMPUS" ("CAMP_ID") ENABLE;

  ALTER TABLE "FLEX2"."STUDENT_SEMESTER" ADD CONSTRAINT "FK_STS_ROLLNO" FOREIGN KEY ("ROLL_NO")
	  REFERENCES "FLEX2"."STUDENT_PROGRAM" ("ROLL_NO") ENABLE NOVALIDATE;

  ALTER TABLE "FLEX2"."STUDENT_SEMESTER" ADD CONSTRAINT "FK_STS_SEMID" FOREIGN KEY ("SEM_ID")
	  REFERENCES "FLEX2"."SEMESTER" ("SEM_ID") ENABLE;
--------------------------------------------------------
--  Ref Constraints for Table STUDY_PLAN_SEM
--------------------------------------------------------

  ALTER TABLE "FLEX2"."STUDY_PLAN_SEM" ADD CONSTRAINT "FK_SPS_BATCHNO" FOREIGN KEY ("BATCH_NO")
	  REFERENCES "FLEX2"."BATCH" ("BATCH_NO") ENABLE;

  ALTER TABLE "FLEX2"."STUDY_PLAN_SEM" ADD CONSTRAINT "FK_SPS_PROGID" FOREIGN KEY ("PROG_ID")
	  REFERENCES "FLEX2"."PROGRAM" ("PROG_ID") ENABLE;

  ALTER TABLE "FLEX2"."STUDY_PLAN_SEM" ADD CONSTRAINT "FK_SPS_SEMID" FOREIGN KEY ("SEM_ID")
	  REFERENCES "FLEX2"."SEMESTER" ("SEM_ID") ENABLE NOVALIDATE;
--------------------------------------------------------
--  Ref Constraints for Table STUDY_TENT_PLAN
--------------------------------------------------------

  ALTER TABLE "FLEX2"."STUDY_TENT_PLAN" ADD CONSTRAINT "FK_STP_BATCHPROGSRNO" FOREIGN KEY ("BATCH_NO", "PROG_ID", "SR_NO")
	  REFERENCES "FLEX2"."STUDY_PLAN_SEM" ("BATCH_NO", "PROG_ID", "SR_NO") ENABLE;

  ALTER TABLE "FLEX2"."STUDY_TENT_PLAN" ADD CONSTRAINT "FK_STP_COURSEID" FOREIGN KEY ("COURSE_ID")
	  REFERENCES "FLEX2"."COURSE" ("COURSE_ID") ENABLE;

  ALTER TABLE "FLEX2"."STUDY_TENT_PLAN" ADD CONSTRAINT "FK_STP_SEMID" FOREIGN KEY ("SEM_ID")
	  REFERENCES "FLEX2"."SEMESTER" ("SEM_ID") ENABLE NOVALIDATE;



--------------------------------------------------------
--  Ref Constraints for Table TENT_GRADE
--------------------------------------------------------

  ALTER TABLE "FLEX2"."TENT_GRADE" ADD CONSTRAINT "FK_TF_GSID" FOREIGN KEY ("GS_ID")
	  REFERENCES "FLEX2"."GRADING_SCHEME" ("GS_ID") ENABLE;

  ALTER TABLE "FLEX2"."TENT_GRADE" ADD CONSTRAINT "FK_TF_OID" FOREIGN KEY ("OFFER_ID")
	  REFERENCES "FLEX2"."COURSE_OFFER" ("OFFER_ID") ENABLE;


--------------------------------------------------------
--  Ref Constraints for Table TENT_GRADE_DETAIL
--------------------------------------------------------

  ALTER TABLE "FLEX2"."TENT_GRADE_DETAIL" ADD CONSTRAINT "FK_TDE_ROLLNO" FOREIGN KEY ("ROLL_NO")
	  REFERENCES "FLEX2"."STUDENT_PROGRAM" ("ROLL_NO") ENABLE;

  ALTER TABLE "FLEX2"."TENT_GRADE_DETAIL" ADD CONSTRAINT "FK_TGD_OID" FOREIGN KEY ("OFFER_ID")
	  REFERENCES "FLEX2"."COURSE_OFFER" ("OFFER_ID") ENABLE;

--------------------------------------------------------
--  Ref Constraints for Table TENT_GRADE_MISSINGSESSIONAL
--------------------------------------------------------

  ALTER TABLE "FLEX2"."TENT_GRADE_MISSINGSESSIONAL" ADD CONSTRAINT "FK_TGMS_OID" FOREIGN KEY ("OFFER_ID")
	  REFERENCES "FLEX2"."COURSE_OFFER" ("OFFER_ID") ENABLE;

  ALTER TABLE "FLEX2"."TENT_GRADE_MISSINGSESSIONAL" ADD CONSTRAINT "FK_TGMS_ROLLNO" FOREIGN KEY ("ROLL_NO")
	  REFERENCES "FLEX2"."STUDENT_PROGRAM" ("ROLL_NO") ENABLE;

















