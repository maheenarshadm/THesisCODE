#!/usr/bin/env python3
"""
compile_constraints.py -- design doc §6.1's compiled constraint record,
built at last. Merges each case study's DMN decision tables with its
hand-curated `variable_to_schema_mapping.csv` (the authoritative ground
truth, not the still-imperfect automated mapper output -- see "Which
mapping source" below) into one JSON record per target branch (one per
decision-table rule), the artifact the generator's fitness function and
search loop (§6.3/§6.4, not yet built) actually read -- never the raw DMN
XML or mapping CSV directly, and never re-parsed at search time.

Per §6.1's own requirement, a record is self-contained: every variable its
condition depends on is resolved -- to a real schema column, a derivation
recipe's raw notes and hinted tables, an explicit not-persisted/schema-gap
marker, or (for a DRD edge into a literal-expression decision) fully
inlined by substitution -- and any DRD edge into another *decision table*
(whose branches aren't a single closed-form expression to inline) is
named explicitly as a scope boundary rather than silently dropped or
half-substituted. §6.6's FK-closure table list is computed from a real BFS
over each case study's schema FK graph, not estimated.

Which mapping source. The design doc's own §5.5 finding was blunt: the
automated mapper (mapping_auto.csv / mapping_final.csv, dmn_schema_mapper/)
is a *collapse-the-search-space* tool, not yet trustworthy enough to feed
the generator unattended (48.3% top-1 even after the LLM-assisted pass).
Since a wrong column here means the eventual generator solves for the
wrong fact entirely, this compiler defaults to each case study's own
hand-curated `variable_to_schema_mapping.csv` -- the actual ground truth
the automated mapper is itself validated against -- and only falls back to
the automated mapping (--mapping-source auto) if explicitly asked, e.g. to
measure how much WORSE compilation coverage would be feeding the
generator from the automated pipeline instead (a natural ablation for
§11, not the default operating mode).

Hard-stop semantics (§6.1: "the compiler should hard-stop and list exactly
which unresolved variables are blocking which branches"). Interpreted here
as: never silently emit an incomplete or wrong record for a blocked
branch, not "crash the whole run on the first blocked branch" -- with 90
of 276 variables still unresolved even after both mapper passes (§ the
mapper's own README), a literal process-exit on first block would produce
zero output. Every branch is attempted; a blocked one is omitted from
compiled_constraints.json and recorded, with its exact blocking
variable(s) and reason, in compile_report.json instead.

Usage:
    python3 compile_constraints.py --out compiled_constraints.json \
        --report compile_report.json
"""
import os
import sys
import csv
import json
import re
import argparse
from collections import deque, Counter
from xml.etree import ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(REPO_ROOT, 'dmn_schema_mapper', 'mapper'))

from feel_parser import parse_unary_test, parse_expression, UnsupportedFeelConstruct  # noqa: E402
from literal_expression_overrides import get_override as get_literal_expression_override  # noqa: E402
from aggregate_self_table import get_self_table  # noqa: E402
import validate_mapper as vm  # noqa: E402 -- reused for GT_CONFIG / ground-truth loading, not re-implemented

DMN_NS = "https://www.omg.org/spec/DMN/20191111/MODEL/"


def q(tag):
    return f'{{{DMN_NS}}}{tag}'


CASE_STUDY_DMN_DIRS = {
    'FLEX2': os.path.join(REPO_ROOT, 'jbillingandflex', 'flex2_dmn', 'flex2_dmn', 'dmn'),
    'OpenMRS': os.path.join(REPO_ROOT, 'openmrs_dmn', 'dmn'),
    'Spree': os.path.join(REPO_ROOT, 'spree_dmn', 'dmn'),
    'jBilling': os.path.join(REPO_ROOT, 'jbillingandflex', 'jbilling_dmn', 'jbilling_dmn', 'dmn'),
}

CASE_STUDY_SCHEMA_JSON = {
    'FLEX2': os.path.join(REPO_ROOT, 'all_schema_extraction', 'all_schema_extraction',
                           'output', 'flex2_schema_full.json'),
    'OpenMRS': os.path.join(REPO_ROOT, 'all_schema_extraction', 'all_schema_extraction',
                             'output', 'openmrs_schema_full.json'),
    'Spree': os.path.join(REPO_ROOT, 'all_schema_extraction', 'all_schema_extraction',
                           'output', 'spree_schema_full.json'),
    'jBilling': os.path.join(REPO_ROOT, 'all_schema_extraction', 'all_schema_extraction',
                              'output', 'jbilling_schema_full.json'),
}

# Citation source for each rule/decision -- rule_provenance_matrix.csv's own
# shape differs by case study (FLEX2/OpenMRS: one row per rule with a
# dmn_file+decision_name+rule-ish key; jBilling/Spree: one row per decision).
# We only need a best-effort human-readable citation string per (dmn_file,
# decision_name) here -- the full matrix stays the authoritative source.
PROVENANCE_PATHS = {
    'FLEX2': os.path.join(REPO_ROOT, 'jbillingandflex', 'flex2_dmn', 'flex2_dmn',
                           'provenance', 'rule_provenance_matrix.csv'),
    'OpenMRS': os.path.join(REPO_ROOT, 'openmrs_dmn', 'provenance', 'rule_provenance_matrix.csv'),
    'Spree': os.path.join(REPO_ROOT, 'spree_dmn', 'provenance', 'rule_provenance_matrix.csv'),
    'jBilling': os.path.join(REPO_ROOT, 'jbillingandflex', 'jbilling_dmn', 'jbilling_dmn',
                              'provenance', 'rule_provenance_matrix.csv'),
}


# ---------------------------------------------------------------------------
# 1. DMN model extraction
# ---------------------------------------------------------------------------

class Decision:
    def __init__(self, id_, name, dmn_file):
        self.id = id_
        self.name = name
        self.dmn_file = dmn_file
        self.hit_policy = None
        self.inputs = []          # [(var_name, feel_type)]
        self.outputs = []         # [(var_name, feel_type)]
        self.rules = []           # [{'id', 'description', 'input_texts': [...], 'output_texts': [...]}]
        self.required_decision_ids = []   # DRD informationRequirement -> href ids
        self.is_literal = False
        self.literal_text = None
        self.own_variable = None  # <variable name=...> -- this decision's own output var, if declared

    @property
    def is_table(self):
        return not self.is_literal


def parse_dmn_file(path):
    """One case study's single .dmn file -> list[Decision]. Reads full
    rule detail (every input/output entry's raw FEEL text, not just the
    lightweight per-variable rows dmn_extract.py's mapper-facing extractor
    produces) since the compiler needs whole rules, not just variable
    names."""
    fname = os.path.basename(path)
    root = ET.parse(path).getroot()
    decisions = []
    for dec_el in root.findall(q('decision')):
        d = Decision(dec_el.get('id'), dec_el.get('name'), fname)
        for ir in dec_el.findall(q('informationRequirement')):
            req = ir.find(q('requiredDecision'))
            if req is not None:
                d.required_decision_ids.append(req.get('href', '').lstrip('#'))

        var_el = dec_el.find(q('variable'))
        if var_el is not None:
            d.own_variable = var_el.get('name')

        dt = dec_el.find(q('decisionTable'))
        if dt is None:
            lit = dec_el.find(q('literalExpression'))
            d.is_literal = True
            text_el = lit.find(q('text')) if lit is not None else None
            d.literal_text = text_el.text if text_el is not None else ''
            decisions.append(d)
            continue

        d.hit_policy = dt.get('hitPolicy', 'UNIQUE')
        for inp in dt.findall(q('input')):
            expr_el = inp.find(q('inputExpression'))
            text_el = expr_el.find(q('text')) if expr_el is not None else None
            typeref = expr_el.get('typeRef', '') if expr_el is not None else ''
            d.inputs.append((text_el.text if text_el is not None else '', typeref))
        for outp in dt.findall(q('output')):
            d.outputs.append((outp.get('name'), outp.get('typeRef', '')))

        for rule_el in dt.findall(q('rule')):
            desc_el = rule_el.find(q('description'))
            input_texts = []
            for entry in rule_el.findall(q('inputEntry')):
                t = entry.find(q('text'))
                input_texts.append(t.text if t is not None else '')
            output_texts = []
            for entry in rule_el.findall(q('outputEntry')):
                t = entry.find(q('text'))
                output_texts.append(t.text if t is not None else '')
            d.rules.append({
                'id': rule_el.get('id'),
                'description': desc_el.text if desc_el is not None else '',
                'input_texts': input_texts,
                'output_texts': output_texts,
            })
        decisions.append(d)
    return decisions


def load_case_study_decisions(cs):
    """Returns (by_id, by_name) indices over every decision in every .dmn
    file for one case study -- DRD hrefs reference the id; substitution
    lookups need the name."""
    by_id, by_name = {}, {}
    for path in sorted(__import__('glob').glob(os.path.join(CASE_STUDY_DMN_DIRS[cs], '*.dmn'))):
        for d in parse_dmn_file(path):
            by_id[d.id] = d
            by_name[d.name] = d
    return by_id, by_name


# ---------------------------------------------------------------------------
# 2. Mapping (variable resolution) -- reuses validate_mapper's GT_CONFIG /
#    ground-truth loader rather than re-implementing CSV-shape handling.
# ---------------------------------------------------------------------------

NORMALIZE_MAPPING_TYPE = [
    # (substring to look for in the raw mapping_type, normalized bucket)
    # order matters: more specific checks first.
    ('schema gap', 'schema_gap'),
    ('not-persisted', 'not_persisted'),
    ('not persisted', 'not_persisted'),
    ('serialized-field', 'serialized_field'),
    ('serialized field', 'serialized_field'),
    ('derived-aggregate', 'derived'),
    ('derived - aggregate', 'derived'),
    ('derived', 'derived'),
    ('direct', 'direct'),
]

# A ground-truth schema field naming a `serialized-field` bucket row:
# `table.column[key]` or `table.column[key=default]` -- e.g.
# `spree_promotion_rules.preferences[amount_min=100.0]`. Never confused
# with the EXISTS-kind `table(col1, col2=value, ...)` bracket syntax
# (different delimiter, different bucket, checked in an entirely
# separate code path) -- this one names ONE key inside an already-
# schema-declared serialized column (see schema_utility.py's own
# `serialized_columns` schema annotation, consulted independently by
# db_resolver.py at validation time), not a filter over real columns.
# `default`, when given, is parsed the same permissive way
# `_EXISTS_FILTER_TOKEN_RE` already parses a literal (int or quoted
# string) -- anything else (a list literal, a decimal needing more than
# that) is left unparsed rather than guessed, and the resolution simply
# has no `default` key, matching `derive_value`'s own `node.get('default')`
# fallback to `None`.
_SERIALIZED_FIELD_RE = re.compile(
    r'^\s*([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)'
    r'\[\s*([A-Za-z_][A-Za-z0-9_]*)\s*(?:=\s*(-?\d+(?:\.\d+)?|\'[^\']*\'))?\s*\]\s*$')


def normalize_mapping_type(raw):
    t = (raw or '').strip().lower()
    for needle, bucket in NORMALIZE_MAPPING_TYPE:
        if needle in t:
            return bucket
    return 'unresolved'


def load_case_study_ground_truth(cs):
    """dict[(decision_name, variable_name, io)] -> {'bucket', 'schema_pairs', 'notes'}
    Built on top of validate_mapper.load_ground_truth(cs), which already
    handles this case study's own CSV column-name differences (Spree's
    decision/variable vs. the other three's decision_name/variable_name,
    §ground-truth GT_CONFIG in dmn_schema_mapper/mapper/validate_mapper.py)."""
    cfg = vm.GT_CONFIG[cs]
    out = {}
    with open(cfg['path'], encoding='utf-8') as f:
        for row in csv.DictReader(f):
            decision_name = row[cfg['decision_col']]
            variable_name = row[cfg['variable_col']]
            io = row.get('io', 'input')  # Spree's CSV has no io column -- both ins/outs recorded together
            schema_field = row.get(cfg['schema_col'], '')
            key = (decision_name, variable_name, io)
            out[key] = {
                'bucket': normalize_mapping_type(row.get('mapping_type', '')),
                'schema_pairs': sorted(vm.true_pairs(schema_field)),
                'notes': row.get(cfg['notes_col'], ''),
                'raw_schema_field': schema_field,
            }
            # Spree's ground truth doesn't distinguish io at all -- also index
            # under 'output' so a lookup that doesn't know which io to ask for
            # (Spree callers) still finds it.
            if 'io' not in row:
                out[(decision_name, variable_name, 'output')] = out[key]
    return out


AGGREGATE_RECIPE_RE = re.compile(
    r'\b(COUNT|SUM|AVG|MIN|MAX)\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)', re.I)
# The reversed word order actually seen in several case studies' notes,
# e.g. "spree_price_adjustment_tiers (COUNT WHERE price_list_id = ...)" --
# same information, table named before the aggregate function instead of
# after it.
AGGREGATE_RECIPE_REVERSED_RE = re.compile(
    r'\b([A-Za-z_][A-Za-z0-9_.]*)\s*\(\s*(COUNT|SUM|AVG|MIN|MAX)\b', re.I)
# A third shape, added for FLEX2's degreeTotalCredits (2026-09-11): the
# aggregate's own target is a real dotted TABLE.COLUMN, e.g.
# "SUM(COURSE.CREDIT_HRS)" -- distinct from the bare-table shapes above,
# which always implicitly aggregate whole rows (COUNT(*), or SUM(1) as a
# placeholder when no column is nameable). Checked first since it's the
# more specific/information-preserving match.
AGGREGATE_RECIPE_DOTTED_RE = re.compile(
    r'\b(COUNT|SUM|AVG|MIN|MAX)\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)\s*\)', re.I)
# An explicit "FROM <table list>" naming the FROM clause when it differs
# from the aggregated column's own table (e.g. a join is needed to reach
# it) -- optional; when absent, the aggregated column's own table is used
# as a single-table FROM, same as the bare-table shapes above.
AGGREGATE_FROM_RE = re.compile(r'\bFROM\s+(.+?)\s+WHERE\b', re.I | re.S)


def _try_extract_aggregate_recipe(text):
    """Best-effort structured recipe extraction for the mechanically-
    recognizable aggregate shapes actually seen in the hand-curated
    notes/schema-field text: "COUNT(TABLE) WHERE <filter>" (§6.1's own
    worked example resolves lecturesAttended/lecturesHeldForOffering
    exactly this way), "TABLE (COUNT WHERE <filter>)" (the reversed word
    order several other case studies' notes happen to use), and
    "SUM(TABLE.COLUMN) [FROM <tables>] WHERE <filter>" (an aggregate over
    a real named column, optionally reached via an explicit FROM/join
    list -- FLEX2's degreeTotalCredits, a SUM over COURSE.CREDIT_HRS
    joined in through PROGRAM_COURSE). This is deliberately not a general
    WHERE-clause parser -- the filter text is kept verbatim for a human
    (or a later, more targeted pass) to turn into the design doc's fully
    structured {"filter": [...]} shape; extracting the aggregate function
    and target table (and, where named, the real target column) is what
    turns an otherwise unresolved/generic-derived block into the richer
    'derived_aggregate' resolution the design doc's own example uses,
    without inventing filter semantics this script has no case-study-
    specific knowledge to get right.

    Caller note (found while adding degreeTotalCredits, 2026-09-11):
    classify_derived() tries `notes` before `raw_schema_field`, so if a
    ground-truth row's `notes` prose happens to *also* mention the
    aggregate call (e.g. explaining it in English) but without the
    schema field's full FROM/WHERE recipe, the notes' incomplete match
    wins and the real recipe in the schema field is never reached.
    Ground-truth authors should keep the literal "AGG(...)" call text
    out of `notes` prose (describe it in words instead) when the schema
    field already carries the full structured recipe."""
    if not text:
        return None
    value_column = None
    m = AGGREGATE_RECIPE_DOTTED_RE.search(text)
    if m:
        aggregate, value_table, col = m.group(1).upper(), m.group(2), m.group(3)
        value_column = f'{value_table}.{col}'
        from_m = AGGREGATE_FROM_RE.search(text, m.end())
        table = from_m.group(1).strip() if from_m else value_table
    else:
        m = AGGREGATE_RECIPE_RE.search(text)
        if m:
            aggregate, table = m.group(1).upper(), m.group(2)
        else:
            m = AGGREGATE_RECIPE_REVERSED_RE.search(text)
            if not m:
                return None
            table, aggregate = m.group(1), m.group(2).upper()
    where_idx = text.upper().find('WHERE', m.end())
    filter_text = text[where_idx + len('WHERE'):].rstrip(') ').strip() if where_idx != -1 else None
    node = {'kind': 'derived_aggregate', 'aggregate': aggregate, 'table': table,
            'filter_text': filter_text, 'source_text': text}
    if value_column:
        node['value_column'] = value_column
    return node


_EXISTENCE_WORDS = re.compile(
    r'\b(IS NOT NULL|IS NULL|existence check|null-check|null check)\b', re.I)
_ANY_OF_WORDS = re.compile(r'\b(OR of|either|any of|either populated)\b', re.I)
# A `null_check`'s own boolean means "is the fact SET" everywhere in this
# corpus EXCEPT the handful of ground-truth rows named/worded the
# opposite way ("identifierBlank": "identifier IS NULL OR TRIM(identifier)
# = ''" -- true means the column is EMPTY, not populated). A real, found
# bug (2026-09-24): every null_check node used to carry the exact same
# shape regardless of which of these two the notes actually described,
# so BOTH generator/candidate.py's derive_value and validation_oracle/
# db_resolver.py's resolve() had to pick ONE fixed polarity -- whichever
# was chosen, it was necessarily right for one family of facts and wrong
# for the other (confirmed directly: OpenMRS's `Identifier Format
# Validity::Rule_1`, gated on `identifierBlank = true`, only verified
# against real data once db_resolver.py's own IS-NOT-NULL fix was
# reverted for exactly this negated case). Fixed at the one place that
# can actually tell the two apart -- the ground truth's own notes text --
# by adding a `negate` flag to the compiled node when the notes say "IS
# NULL" without also saying "IS NOT NULL" (checked in that order so a
# note mentioning both, if one ever does, keeps the ordinary polarity).
# Every OTHER null_check consumer defaults `negate` to falsy via
# `node.get('negate')`, so this is additive -- nothing already using the
# ordinary (non-negated) shape changes.
_NEGATED_NULL_CHECK_WORDS = re.compile(r'\bIS NULL\b', re.I)
_NON_NEGATED_NULL_CHECK_WORDS = re.compile(r'\bIS NOT NULL\b', re.I)


def _null_check_is_negated(notes):
    notes = notes or ''
    return bool(_NEGATED_NULL_CHECK_WORDS.search(notes)) and not _NON_NEGATED_NULL_CHECK_WORDS.search(notes)
_EXISTS_ROW_WORDS = re.compile(
    r'\bexistence of\b|\(existence\)|\bEXISTS\(|self-join', re.I)
# One token inside an `exists`-kind raw schema field's own parenthesized
# column list -- a bare column name (`entity_id`), one with an integer
# literal (`entity_id=0`), or one with a quoted string literal
# (`psudo_column='welcome_message'`, added 2026-09-22 for jBilling's
# generic i18n description table, a real per-language, per-pseudo-column
# lookup that genuinely needs a string key, not a number -- the runtime
# filter machinery, _mechanical_filter_predicate/_row_from_filter_
# conjuncts in candidate.py, already strips and compares quoted string
# conjuncts exactly this way for every OTHER filter-text source, e.g.
# derived_aggregate's own "WHERE ..." recipes; this only extends the
# GROUND-TRUTH-TEXT parser to also accept one). A token that fits none of
# these three shapes still aborts the whole filter-text extraction rather
# than guessing (see classify_derived's own comment on this).
_EXISTS_FILTER_TOKEN_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)(?:\s*=\s*(?:(-?\d+)|'([^']*)'))?$")
_JOINED_VIA_RE = re.compile(r'joined via ([A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*)', re.I)
_CONSTANT_RE = re.compile(r'(?:constant|=)\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(-?\d+)')
# An escape hatch for a genuinely bespoke boolean fact that doesn't fit any
# of the structured shapes above -- added for FLEX2's
# isElectiveTaughtByVisitingScholarUnavailableOtherwise (2026-09-11), a
# compound "this offering's instructor is of a named type AND no other
# offering of the same course this semester has a different-typed
# instructor" fact that a single table.column or join can't express. A
# general marker, not a one-off hack: any ground-truth row this specific
# can name its own fully-worked-out SQL boolean expression directly,
# rather than either forcing it into a shape that loses information or
# leaving it an unresolved placeholder when a human already knows exactly
# what query answers it. RAW_SQL:'s own text still goes through the same
# <placeholder>-substitution and prose-shape checks as every other filter
# text (sql_compiler.py's sqlify_filter_text) -- never trusted blindly.
_RAW_SQL_RE = re.compile(
    r'RAW_SQL:\s*(.+?)\s*TABLES:\s*([A-Za-z_][A-Za-z0-9_]*(?:\s*,\s*[A-Za-z_][A-Za-z0-9_]*)*)\s*$',
    re.I | re.S)


def _try_extract_raw_sql_boolean(text):
    if not text:
        return None
    m = _RAW_SQL_RE.search(text)
    if not m:
        return None
    tables = [t.strip() for t in m.group(2).split(',') if t.strip()]
    return {'kind': 'raw_sql_boolean', 'sql_template': m.group(1).strip(), 'tables': tables}


# A second escape hatch, found necessary while building mutation.py
# (2026-09-11): semesterType was mapped as a plain schema_column
# passthrough of SEMESTER.TITLE, but the DMN rules that consume it
# compare it against 'Regular'/'Summer' -- a *different*, two-category
# vocabulary than TITLE's own three real values ('Fall'/'Spring'/
# 'Summer'). A raw passthrough can never equal 'Regular' for any real
# row, so mutation.py's own operator "solved" the branch by writing an
# impossible value (TITLE='Regular') straight into a candidate row --
# fitness said 0, the row was fiction. `CASE_MAP:` names an explicit,
# *exhaustive* enumeration of every real column value and what derived
# category it maps to (deliberately not an ELSE/default -- an unlisted
# real value should surface as a hard "we don't know how to categorize
# this," not silently fall through to a guess), so both directions stay
# honest: sql_compiler.py/candidate.py read the real value and map
# forward; mutation.py inverts the same table to write a real value back.
_CASE_MAP_RE = re.compile(
    r'CASE_MAP:\s*([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.+)$',
    re.I | re.S)
_CASE_MAP_ENTRY_RE = re.compile(r"'([^']*)'\s*->\s*'([^']*)'")


def _try_extract_case_map(text):
    if not text:
        return None
    m = _CASE_MAP_RE.search(text)
    if not m:
        return None
    table, column, rest = m.group(1), m.group(2), m.group(3)
    cases = _CASE_MAP_ENTRY_RE.findall(rest)
    if not cases:
        return None
    return {'kind': 'derived_case', 'table': table, 'column': column,
            'cases': [[k, v] for k, v in cases]}


# A fourth escape hatch, found necessary while testing mutation.py against
# tricker rules (2026-09-11): unmetPrerequisiteCount's raw text is "COUNT
# via COURSE_PREREQ join COURSE_REGISTRATION.GRADE" -- a real join-based
# aggregate, but _try_extract_aggregate_recipe's three regexes all require
# a literal "AGG(...)" call, so this text matched none of them and fell
# all the way through to the generic len(pairs)==1 fallback, which
# produced a plain schema_column pointing straight at
# course_registration.grade -- the *same* physical column
# previousGradeInCourse also resolves to (a STRING letter grade), even
# though unmetPrerequisiteCount is a NUMBER compared with `> 0`. Confirmed
# as a real bug via mutation.py: writing a string grade into that shared
# column crashed distance_to_false's numeric comparison for
# unmetPrerequisiteCount.
#
# The real semantics (confirmed against schemas/flex2/Flex1.sql's own DDL,
# 2026-09-11): COURSE_PREREQ(COURSE_ID, COURSE_PREREQ) names, per course,
# which other course is a prerequisite for it; a student has satisfied one
# when COURSE_REGISTRATION has a row for (that student, that prerequisite
# course) with a passing GRADE -- "passing" being not in the same
# {F,D,D+,C-} blocklist previousGradeInCourse's own notes already name.
# This phrasing occurs exactly twice in the whole program (grep-verified),
# both in FLEX2, both over this same COURSE_PREREQ/COURSE_REGISTRATION
# pair with the same semantics (count of "this" row's own course's
# prerequisites that "this" row's own student hasn't passed yet) -- only
# which table supplies "this" row differs (COURSE_REGISTRATION itself for
# Course Registration Eligibility, EXEMPTED_COURSES for Credit Transfer
# Exemption); both real tables carry their own ROLL_NO + COURSE_ID columns
# (DDL-confirmed), so candidate.py's bridge finds "this" context by
# looking for whichever focal row carries both, rather than assuming one
# fixed table name.
_COUNT_VIA_JOIN_RE = re.compile(
    r'COUNT via ([A-Za-z_][A-Za-z0-9_]*)\s+join\s+([A-Za-z_][A-Za-z0-9_]*)(?:\.([A-Za-z_][A-Za-z0-9_]*))?',
    re.I)
_PREREQ_FAIL_GRADES = ['F', 'D', 'D+', 'C-']


def _try_extract_prereq_gap_count(text):
    if not text:
        return None
    m = _COUNT_VIA_JOIN_RE.search(text)
    if not m:
        return None
    prereq_table, registration_table = m.group(1), m.group(2)
    return {
        'kind': 'derived_join_count',
        'prereq_table': prereq_table,
        'prereq_course_column': 'COURSE_ID',
        'prereq_target_column': 'COURSE_PREREQ',
        'registration_table': registration_table,
        'registration_course_column': 'COURSE_ID',
        'registration_roll_column': 'ROLL_NO',
        'registration_grade_column': 'GRADE',
        'fail_grades': list(_PREREQ_FAIL_GRADES),
        'source_text': text,
    }


def classify_derived(row):
    """The general classifier for a 'derived'-bucketed ground-truth row --
    replaces a narrow aggregate-only check with pattern rules covering
    every shape a direct survey of all 83 program-wide 'derived' facts
    actually turned up (generator/README.md's own accounting). Ground
    truth's free-text notes/schema-field were never designed to be
    machine-structured, so this stays a set of targeted, individually
    justified pattern rules -- never a general NLP parse -- and anything
    that matches none of them is left exactly as before (a generic
    'derived' node with table_hints), not forced into a wrong shape.

    Order matters: more specific / more information-preserving checks
    first, since e.g. an aggregate mention should win over a same-text
    "existence" mention (COUNT ... WHERE existence-flavored language can
    co-occur).
    """
    notes, raw = row['notes'] or '', row['raw_schema_field'] or ''
    pairs = row['schema_pairs']

    prereq_gap = _try_extract_prereq_gap_count(notes) or _try_extract_prereq_gap_count(raw)
    if prereq_gap:
        prereq_gap['notes'] = notes
        return prereq_gap

    agg = _try_extract_aggregate_recipe(notes) or _try_extract_aggregate_recipe(raw)
    if agg:
        return agg

    case_map = _try_extract_case_map(notes) or _try_extract_case_map(raw)
    if case_map:
        case_map['notes'] = notes
        return case_map

    raw_sql = _try_extract_raw_sql_boolean(notes) or _try_extract_raw_sql_boolean(raw)
    if raw_sql:
        raw_sql['notes'] = notes
        return raw_sql

    # "joined via X.Y" is checked before the plain existence check below,
    # not after -- several facts' notes contain both ("joined via
    # orders.encounter_id; IS NOT NULL", encounterDatetimeSet), and the
    # join form carries strictly more information a plain null_check would
    # lose: the *source* table (the FK holder), which matters for FK
    # closure correctness. fk_closure() only walks FKs forward (a table's
    # own declared targets), so seeding it with only the *target* table
    # ("encounter") would never discover "orders" pointing at it -- only
    # capturing both ends via join_lookup/join_null_check gets this right.
    # Also applies regardless of how many pairs true_pairs() found in the
    # schema field -- a join fact's source column usually only appears in
    # the prose, while the schema field itself names just the target, so
    # this is very often exactly 1 pair, not 2 (an earlier version gated
    # this on len(pairs) >= 2 and so missed every single-pair join fact,
    # e.g. OpenMRS's visitPatientId/visitStartDatetime/visitStopDatetime).
    if pairs:
        m = _JOINED_VIA_RE.search(notes)
        if m:
            local_table, local_column = m.group(1).split('.')
            target_table, target_column = pairs[-1]  # the last-mentioned pair is the joined-to fact, by convention of how these notes are written
            node = {'kind': 'join_lookup',
                    'via': {'local_table': local_table, 'local_column': local_column},
                    'result_table': target_table, 'result_column': target_column, 'notes': notes}
            if _EXISTENCE_WORDS.search(notes):
                node['kind'] = 'join_null_check'
            return node

    # Existence checks apply the same way regardless of how many candidate
    # columns ground truth recorded -- a schema field like "concept_numeric
    # .hi_absolute (or concept_reference_range.hi_absolute)" names two
    # *alternative* real locations for the same IS-NOT-NULL fact, not an
    # OR-of-several-columns condition (that's _ANY_OF_WORDS, a genuinely
    # different shape, checked separately below). Use the first as the
    # primary target, same graceful-degradation convention the 'direct'
    # bucket already uses for its own multi-pair rows.
    if pairs and _EXISTENCE_WORDS.search(notes) and not _ANY_OF_WORDS.search(notes):
        table, column = pairs[0]
        node = {'kind': 'null_check', 'table': table, 'column': column, 'notes': notes}
        if _null_check_is_negated(notes):
            node['negate'] = True
        if len(pairs) > 1:
            node['also_valid_in'] = pairs[1:]
        return node

    # A regex/pattern match between two named columns (§7b's own "Pattern/
    # Regex Match" construct category -- not portable branch-distance
    # comparable, but a real, structured fact a SQL validation pass (§6.7)
    # can still express via an engine's REGEXP operator).
    if len(pairs) == 2 and re.search(r'\bregex\b', notes, re.I):
        (t1, c1), (t2, c2) = pairs
        return {'kind': 'regex_match', 'value_column': {'table': t1, 'column': c1},
                'pattern_column': {'table': t2, 'column': c2}, 'notes': notes}

    if len(pairs) == 1:
        table, column = pairs[0]
        m = _CONSTANT_RE.search(notes)
        node = {'kind': 'schema_column', 'table': table, 'column': column}
        if m:
            node['compared_to_named_constant'] = {'name': m.group(1), 'value': int(m.group(2))}
        node['notes'] = notes
        return node

    if len(pairs) >= 2:
        if _ANY_OF_WORDS.search(notes):
            return {'kind': 'any_not_null', 'columns': [{'table': t, 'column': c} for t, c in pairs],
                    'notes': notes}
        if _EXISTS_ROW_WORDS.search(notes):
            return {'kind': 'exists', 'candidate_tables': sorted({t for t, _ in pairs}),
                     'candidate_columns': [{'table': t, 'column': c} for t, c in pairs], 'notes': notes}
        # Nothing more specific matched, but ground truth still named two or
        # more real candidate columns for this fact (e.g. "base_user
        # .status_id / generic_status.id" for a comparison-against-constant
        # style fact with no single clean target) -- picking the first as
        # primary, same graceful-degradation convention as above, beats
        # leaving a row with real column names attached fully unresolved.
        table, column = pairs[0]
        return {'kind': 'schema_column', 'table': table, 'column': column,
                'also_valid_in': pairs[1:], 'notes': notes}

    if _EXISTS_ROW_WORDS.search(notes) or _EXISTS_ROW_WORDS.search(raw):
        # A table named (often via "(existence)") but no clean column --
        # still worth surfacing the table for FK-closure/materialization
        # purposes even though the exact key columns need a human. If even
        # the table name can't be mechanically extracted, this adds no
        # more information than the generic fallback -- fall through to it
        # instead of returning a hollow, falsely-"resolved"-looking node.
        m = re.match(r'\s*([A-Za-z_][A-Za-z0-9_]*)\s*\(\s*([^)]*?)\s*\)', raw)
        if m:
            table, inner = m.group(1), m.group(2)
            # A real, general fix (2026-09-13, the "known exists-kind
            # filter gap" named in generator/README.md): when the raw
            # schema field's own parenthesized content is a genuine
            # comma-separated column list (e.g. "currency_exchange
            # (entity_id, currency_id)" or "currency_exchange
            # (entity_id=0, currency_id)") rather than the bare "(existence)"
            # sentinel, turn it into a real `filter_text` -- the exact
            # same `COLUMN = VALUE`/`COLUMN = <placeholder>` shape
            # `derived_aggregate` already produces, so `exists`-kind can
            # reuse the SAME already-proven mechanical filter machinery
            # (`_mechanical_filter_predicate`/`_row_from_filter_conjuncts`)
            # instead of the current bare "does ANY row exist" check --
            # which was the root cause of two objectives (jBilling's
            # `hasEntitySpecificExchange`/`hasSystemDefaultExchange`)
            # being structurally unable to differ from each other despite
            # their own ground truth clearly describing different filters
            # on the same table. A column with no literal (`entity_id`
            # alone) becomes an auto-placeholder keyed by its own column
            # name (`entity_id = <entity_id>`); a column with one
            # (`entity_id=0`) becomes a literal-value conjunct. Any token
            # that doesn't parse as a clean `col` or `col=value` shape
            # aborts the whole parse (never a partial, silently-wrong
            # filter) and falls through to the existing bare-table
            # behavior below -- verified against every currently-compiled
            # `exists`-kind record across all 4 case studies: only these
            # 2 records have a non-"(existence)" parenthesized column
            # list, so this is a strictly additive enrichment, not a
            # reclassification risk.
            if inner.strip().lower() != 'existence':
                tokens = [t.strip() for t in inner.split(',') if t.strip()]
                conjuncts, columns, parse_ok = [], [], bool(tokens)
                for t in tokens:
                    tm = _EXISTS_FILTER_TOKEN_RE.match(t)
                    if not tm:
                        parse_ok = False
                        break
                    col, int_lit, str_lit = tm.group(1), tm.group(2), tm.group(3)
                    columns.append(col)
                    if int_lit is not None:
                        conjuncts.append(f"{col} = {int_lit}")
                    elif str_lit is not None:
                        conjuncts.append(f"{col} = '{str_lit}'")
                    else:
                        conjuncts.append(f"{col} = <{col}>")
                if parse_ok:
                    return {'kind': 'exists', 'candidate_tables': [table],
                             'candidate_columns': [{'table': table, 'column': c} for c in columns],
                             'filter_text': ' AND '.join(conjuncts), 'notes': notes, 'raw_schema_field': raw}
            return {'kind': 'exists', 'candidate_tables': [table],
                     'candidate_columns': [], 'notes': notes, 'raw_schema_field': raw}

    if raw.strip().lower() == 'n/a' and not pairs:
        return {'kind': 'code_external', 'notes': notes,
                'reason': 'no schema field was ever recorded for this fact -- genuinely computed by '
                          'application code (a Java constant, a UI-only transient value, a runtime '
                          'calculation over other derived facts), not read from any table at all'}

    return None  # nothing matched -- caller keeps the existing generic 'derived' fallback


def resolve_variable(cs, gt, decision_name, var_name, io='input'):
    """Looks up one variable's ground-truth resolution -> a resolution
    node (never None -- an unmatched lookup becomes an explicit
    'unresolved: not found in ground truth' rather than silently missing)."""
    row = gt.get((decision_name, var_name, io)) or gt.get((decision_name, var_name, 'input')) \
        or gt.get((decision_name, var_name, 'output'))
    if row is None:
        return {'kind': 'unresolved', 'reason': 'not found in ground-truth mapping CSV',
                'decision_name': decision_name, 'variable': var_name}
    bucket = row['bucket']
    if bucket == 'not_persisted':
        return {'kind': 'not_persisted'}
    if bucket == 'schema_gap':
        return {'kind': 'schema_gap', 'notes': row['notes'], 'hinted_pairs': row['schema_pairs']}
    if bucket == 'serialized_field':
        m = _SERIALIZED_FIELD_RE.match(row['raw_schema_field'] or '')
        if not m:
            return {'kind': 'unresolved',
                    'reason': "labeled 'serialized-field' but schema field isn't "
                              "'table.column[key]' or 'table.column[key=default]'",
                    'raw_schema_field': row['raw_schema_field']}
        table, column, key, default_text = m.groups()
        if _EXISTENCE_WORDS.search(row['notes'] or ''):
            # An existence check ON a serialized field (e.g. Spree's
            # amountMaxSet -- "was amount_max ever configured at all")
            # is null_check's own job, just one level of dict access
            # deeper -- reuses that kind directly (with `key` set) rather
            # than inventing a parallel "is this set" kind, the same way
            # `direct`'s own existence-check rows already reuse
            # null_check instead of a schema_column-specific variant.
            node = {'kind': 'null_check', 'table': table, 'column': column, 'key': key, 'notes': row['notes']}
            if _null_check_is_negated(row['notes']):
                node['negate'] = True
            return node
        node = {'kind': 'serialized_field', 'table': table, 'column': column, 'key': key, 'notes': row['notes']}
        if default_text is not None:
            if default_text.startswith("'"):
                node['default'] = default_text[1:-1]
            elif '.' in default_text:
                node['default'] = float(default_text)
            else:
                node['default'] = int(default_text)
        return node
    if bucket == 'direct':
        if row['schema_pairs']:
            table, column = row['schema_pairs'][0]
            node = {'kind': 'schema_column', 'table': table, 'column': column}
            if len(row['schema_pairs']) > 1:
                node['also_valid_in'] = row['schema_pairs'][1:]
            return node
        # No bare table.column pair in a row labeled 'direct' -- check
        # before giving up whether it's actually a mislabeled aggregate
        # recipe hiding behind that label (a real, surveyed FLEX2 case:
        # lecturesAttended/lecturesHeldForOffering are labeled 'direct'
        # but their schema field text is "COUNT(STUDENT_ATTENDANCE)
        # WHERE ..."). Ground truth's own label is kept as a `notes` field
        # rather than silently corrected, since this is the source data's
        # own labeling, not this compiler's judgment call.
        recipe = _try_extract_aggregate_recipe(row['raw_schema_field'])
        if recipe:
            recipe['notes'] = f"ground truth labeled this 'direct'; text describes an aggregate, treated as derived_aggregate"
            return recipe
        return {'kind': 'unresolved', 'reason': "labeled 'direct' but no table.column parsed from its schema field",
                'raw_schema_field': row['raw_schema_field']}
    if bucket == 'derived':
        classified = classify_derived(row)
        if classified:
            if classified.get('kind') == 'derived_aggregate' \
                    and re.search(r'\bself\b', classified.get('filter_text') or '', re.I):
                self_table = get_self_table(cs, var_name)
                if self_table:
                    classified['self_table'] = self_table
            return classified
        return {'kind': 'derived', 'notes': row['notes'], 'table_hints': row['schema_pairs']}
    return {'kind': 'unresolved', 'reason': f'unrecognized ground-truth mapping_type bucket {bucket!r}'}


# ---------------------------------------------------------------------------
# 3. DRD backward-substitution
# ---------------------------------------------------------------------------

def find_all_variable_refs(node, out=None):
    """Recursively collects every {'kind': 'variable', 'ref': ...} leaf in
    a predicate/expression tree."""
    if out is None:
        out = []
    if not isinstance(node, dict):
        return out
    if node.get('kind') == 'variable':
        out.append(node['ref'])
        return out
    for key in ('left', 'right', 'low', 'high', 'clause', 'cond', 'then', 'else'):
        if key in node:
            find_all_variable_refs(node[key], out)
    for key in ('clauses', 'values', 'args'):
        if key in node:
            for child in node[key]:
                find_all_variable_refs(child, out)
    return out


class SubstitutionError(Exception):
    pass


def resolve_and_substitute(cs, gt, decision, var_name, by_id, by_name, seen=None):
    """The core of §6.1's DRD backward-substitution: resolve one variable
    referenced inside `decision`'s own condition. Three cases, in order:

    1. It's one of `decision`'s own declared inputs -> ground-truth lookup.
    2. It isn't declared here, but an upstream decision this one has a DRD
       edge to produces it as its own output/variable:
       a. Upstream is a literal-expression decision -> fully inlined
          (substituted_decision): its formula is parsed and every free
          variable inside THAT formula is itself resolved recursively
          (so a chain of literal-expression decisions inlines all the way
          down to real ground-truth resolutions, not just one level).
       b. Upstream is a decision table -> NOT inlined (a decision table's
          output depends on which of its own rules fires, which isn't a
          single closed-form expression to substitute) -- returned as an
          explicit 'chained_decision_output' scope-boundary marker, per
          §6.1's own worked example never attempting this case either.
    3. Neither -- genuinely unresolved (not declared, not DRD-produced).
    """
    seen = seen or set()
    # DRD substitution takes priority over a flat ground-truth lookup even
    # when the variable is *also* one of this decision's own declared
    # <input> elements -- DMN 1.3 requires a decision table to declare a
    # formal input to reference a value in its rules at all, so a
    # DRD-produced variable is very often declared as an input too (the
    # real, surveyed case: FLEX2's "Attendance Eligibility For Final Exam"
    # declares attendancePercentage as an input AND has an
    # informationRequirement into "Attendance Percentage", which produces
    # it). Preferring substitution here is what actually produces §6.1's
    # own worked example (a fully inlined expression), not a flat "derived,
    # see the upstream decision" ground-truth note that leaves the formula
    # un-inlined.
    for req_id in decision.required_decision_ids:
        upstream = by_id.get(req_id)
        if upstream is None:
            continue
        produced_name = upstream.own_variable if upstream.is_literal else None
        produced_names = [produced_name] if produced_name else [o for o, _ in upstream.outputs]
        if var_name not in produced_names:
            continue
        if upstream.is_literal:
            cache_key = (upstream.name, var_name)
            if cache_key in seen:
                return {'kind': 'unresolved', 'reason': 'circular DRD substitution detected',
                         'decision_chain': sorted(seen)}
            # A DISCLOSED, hand-authored override takes priority over the
            # real parse -- see literal_expression_overrides.py's own
            # module docstring. Needed for formulas feel_parser.py cannot
            # actually parse (e.g. a FEEL list comprehension, which
            # degrades to an unevaluable `opaque_formula` node nested
            # inside an otherwise-successful parse, rather than raising
            # UnsupportedFeelConstruct at the top level -- so this check
            # must happen before attempting the parse at all, not only in
            # the except branch below).
            override = get_literal_expression_override(cs, upstream.name)
            if override is not None:
                return {'kind': 'substituted_decision', 'substituted_from': upstream.name,
                        'expression': override['expression'],
                        'free_variable_resolutions': override['free_variable_resolutions']}
            try:
                expr = parse_expression(upstream.literal_text)
            except UnsupportedFeelConstruct as e:
                return {'kind': 'unresolved', 'reason': f'upstream literal expression not parseable: {e}',
                         'upstream_decision': upstream.name}
            free_vars = sorted(set(find_all_variable_refs(expr)))
            resolutions = {}
            for fv in free_vars:
                resolutions[fv] = resolve_and_substitute(
                    cs, gt, upstream, fv, by_id, by_name, seen | {cache_key})
            return {'kind': 'substituted_decision', 'substituted_from': upstream.name,
                    'expression': expr, 'free_variable_resolutions': resolutions}
        else:
            return {'kind': 'chained_decision_output', 'from_decision': upstream.name,
                    'note': ('requires the upstream decision table to have already selected a '
                             'branch of its own -- not inlined (scope boundary: a decision table\'s '
                             'output depends on which of its own rules fires, which is not a single '
                             'closed-form expression to substitute the way a literal-expression '
                             'decision\'s formula is)')}

    # A literal-expression decision never declares formal <input> elements
    # at all (dmn_extract.py's own convention: its formula's free
    # identifiers are its implicit pseudo-inputs) -- so for it, any free
    # variable not produced by a further upstream DRD edge falls straight
    # to ground-truth resolution, the same way the hand-built mapping CSVs
    # record these (e.g. "Attendance Percentage, lecturesAttended, input,
    # ..."). A decision TABLE's own declared inputs still gate normally.
    if decision.is_literal or var_name in [v for v, _ in decision.inputs]:
        return resolve_variable(cs, gt, decision.name, var_name, 'input')

    return {'kind': 'unresolved',
            'reason': 'not a declared input of this decision, and not produced by any DRD-linked upstream decision'}


# ---------------------------------------------------------------------------
# 4. FK-closure (§6.6) -- real BFS over the schema's FK graph
# ---------------------------------------------------------------------------

def load_schema_fk_graph(cs):
    with open(CASE_STUDY_SCHEMA_JSON[cs], encoding='utf-8') as f:
        data = json.load(f)
    return {table: set(info.get('fks') or []) for table, info in data.items()}, set(data.keys())


def fk_closure(seed_tables, fk_graph, all_tables, max_tables=300):
    """BFS outward from every seed table along its FK edges (§6.6's own
    methodology: walk the direct dependency chain, not estimate it).
    Table names are matched case-insensitively against the schema's own
    keys, since ground-truth mapping CSVs don't consistently match the
    schema JSON's stored casing."""
    lower_index = {t.lower(): t for t in all_tables}
    resolved_seeds = {lower_index[t.lower()] for t in seed_tables if t.lower() in lower_index}
    visited = set(resolved_seeds)
    queue = deque(resolved_seeds)
    while queue and len(visited) < max_tables:
        t = queue.popleft()
        for target in fk_graph.get(t, ()):
            key = target.lower()
            real = lower_index.get(key)
            if real and real not in visited:
                visited.add(real)
                queue.append(real)
    return sorted(visited)


# ---------------------------------------------------------------------------
# 4b. Decision subject table (2026-09-24) -- a generator-owned port of
# validation_oracle/subject_table.py's own algorithm, computed here at
# compile time and attached to every compiled record as a NEW
# `decision_subject` field, rather than imported from validation_oracle/
# directly.
#
# Why a port, not an import: DESIGN.md's own "Architectural separation
# requirement" is explicit that the validator and the search approach
# must have "no overlap in function calls" -- stated as a constraint on
# what the VALIDATOR may import from the generator, but the underlying
# intent (the generator must not be shaped by knowledge of how it is
# independently checked) cuts the same way in the other direction.
# Confirmed by grep, before this change: zero references from any
# generator/*.py file into validation_oracle/subject_table.py or
# schema_utility.py. This keeps that true, by giving the generator its
# OWN, independently-computed answer to the same real, schema-level
# question -- exactly the same precedent DESIGN.md already carves out
# for Phase 1's OWN compile-time metadata ("declarative... not a
# search-time computed value or verdict").
#
# Why this needs to exist at all: found investigating why FLEX2's
# `Course Load Limit` (and, it turned out, Spree's `Promotion Customer
# Group Eligibility` and OpenMRS's `Identifier Uniqueness Check`) never
# verify despite the search claiming coverage -- `dynamosa.py`'s own
# per-objective focal-row construction is driven ENTIRELY by which
# tables a record's own leaf variables read (`_focal_tables_for_leaf`),
# with zero awareness of a decision's real DMN "subject" grain. When
# that subject is a pure junction/link table no leaf ever reads directly
# (confirmed real, not hypothetical, for all 3 decisions above), the
# generator never constructs it at all -- every individual fact it DOES
# build may be correct in isolation, but nothing ever ties them together
# as "the same real case," so independent verification can never find a
# corresponding subject row.
#
# Deliberately NARROWER scope than validation_oracle/subject_table.py's
# own algorithm, disclosed rather than silently assumed equivalent:
# - Forward FK edges only (schema's own `fk_columns`) -- no port of
#   `schema_utility.functional_backward_edges`'s shared-PK-subtype
#   backward traversal. A decision needing that to find a unique root
#   simply gets no `decision_subject` here (same as today, no worse).
# - A genuinely ambiguous edge (more than one distinct FK column between
#   the same two tables) is skipped, never resolved via a
#   `join_disambiguation.py`-style override -- no override data is
#   duplicated here. Skipping can only ever produce "no unique root
#   found" (this pass attaches nothing), never a wrong answer.
# - `filter_placeholder_sources.py`'s own disclosed overrides ARE
#   ported (just the one real, non-test entry that matters for actual
#   compiled data, `('Spree', 'promotion_id') -> 'spree_order_promotions'`)
#   -- confirmed load-bearing: without it, `Promotion Customer Group
#   Eligibility`'s own `spree_order_promotions` subject is unreachable
#   from `all_tables` at all (its own `fk_closure_tables` don't include
#   it either), so the validator's OWN successful resolution of this
#   decision's subject depends on this exact override too.
#
# A failure to resolve a subject here is never a hard compile error --
# `compute_decision_subject` returns None (not attaching the field to
# any of that decision's own records), exactly the same "don't block
# the whole compile" discipline every other soft gap in this file
# already follows. A decision with no `decision_subject` field simply
# gets none of this fix's benefit -- not worse than before this existed.
# ---------------------------------------------------------------------------

_DECISION_SUBJECT_PLACEHOLDER_SOURCES = {
    # Mirrors validation_oracle/filter_placeholder_sources.py's own
    # FILTER_PLACEHOLDER_SOURCES entry for the SAME real-world fact --
    # duplicated, not imported, per this section's own docstring. Kept
    # in sync by hand; if the validator's own copy ever changes, this
    # one needs the same edit.
    ('Spree', 'promotion_id'): 'spree_order_promotions',
    # FLEX2's `Course Replacement Eligibility::degreeTotalCredits` --
    # see validation_oracle/filter_placeholder_sources.py's own matching
    # entries for the full writeup (2026-09-24).
    ('FLEX2', 'program'): 'STUDENT_PROGRAM',
    ('FLEX2', 'batch'): 'STUDENT_PROGRAM',
}

_PLACEHOLDER_NAME_RE = re.compile(r'<([A-Za-z_][A-Za-z0-9_ ]*)>')
_PLACEHOLDER_CONJUNCT_RE = re.compile(r'([A-Za-z_][A-Za-z0-9_]*)\s*=\s*<([A-Za-z_][A-Za-z0-9_ ]*)>')


def _load_raw_schema(cs):
    with open(CASE_STUDY_SCHEMA_JSON[cs], encoding='utf-8') as f:
        return json.load(f)


def _schema_table_entry(raw_schema, table):
    return raw_schema.get(table) or raw_schema.get(table.upper()) or raw_schema.get(table.lower())


def _canonical_table_name(raw_schema, table):
    for candidate in (table, table.upper(), table.lower()):
        if candidate in raw_schema:
            return candidate
    return table


def _pk_columns_for(raw_schema, table):
    pk = (_schema_table_entry(raw_schema, table) or {}).get('pk')
    if pk is None:
        return []
    return pk if isinstance(pk, list) else [pk]


def _fk_edges_for(raw_schema, table):
    entry = _schema_table_entry(raw_schema, table) or {}
    return [{**e, 'ref_table': _canonical_table_name(raw_schema, e['ref_table'])}
            for e in entry.get('fk_columns') or []]


def _decision_subject_tables_referenced(cs, record):
    """Every table this record's own `variable_resolution` reads
    DIRECTLY (needing a real join path from the subject row to reach),
    for root-picking purposes -- reuses this module's own
    `collect_tables_from_resolution` (already built for
    `fk_closure_tables`) for most kinds, EXCEPT `exists`/
    `derived_aggregate` with a `filter_text`: that shape is a
    self-contained correlated query against its own candidate/aggregate
    table, built from a raw WHERE substituting the SUBJECT row's own
    columns/placeholders -- `db_resolver.resolve` queries that table
    directly, never joining to it from the subject, so it needs no join
    path at all (reusing `collect_tables_from_resolution`'s own
    unconditional `candidate_tables`/`table` addition here would wrongly
    demand one). Only a placeholder that ISN'T on the subject row needs
    a real join, via `_DECISION_SUBJECT_PLACEHOLDER_SOURCES`'s disclosed
    source table -- mirrors `validation_oracle/subject_table.py`'s own
    `_TABLE_EXTRACTORS['exists'/'derived_aggregate']` exactly (confirmed
    necessary, not a hypothetical edge case: Spree's own
    `promotionTargetGroupsConfigured` has both a `filter_text` AND a
    `candidate_tables`, and only the placeholder-sourced table is
    actually reachable from this decision's real subject)."""
    tables = set()
    for node in record.get('variable_resolution', {}).values():
        if not isinstance(node, dict):
            continue
        filter_text = node.get('filter_text')
        if node.get('kind') in ('exists', 'derived_aggregate') and filter_text:
            for placeholder in _PLACEHOLDER_NAME_RE.findall(filter_text):
                extra = _DECISION_SUBJECT_PLACEHOLDER_SOURCES.get((cs, placeholder))
                if extra:
                    tables.add(extra)
            continue
        collect_tables_from_resolution(node, tables)
    return tables


def compute_cross_table_placeholder_correlations(cs, node):
    """For a `derived_aggregate`/`exists` node's own `filter_text`, which
    of its `<placeholder>` conjuncts (`COLUMN = <placeholder>`) name a
    placeholder `_DECISION_SUBJECT_PLACEHOLDER_SOURCES` resolves to a
    real OTHER table -- i.e. a value that must equal that SAME real
    record's own column of the identical name on that table, not a free
    scalar the search can tune independently.

    Found real, not hypothetical (2026-09-24, FLEX2's `Course
    Replacement Eligibility::degreeTotalCredits`): `PROGRAM_COURSE.
    PROG_ID=<program>`/`.BATCH_NO=<batch>` need to equal the SAME
    record's own `STUDENT_PROGRAM.PROG_ID`/`.BATCH_NO` (the student
    whose degree the aggregate sums credits for) -- but nothing in
    `candidate.py`'s own seeding/mutation, or `fitness.py`'s own
    evaluation, ever makes that connection: both treat `<program>`/
    `<batch>` as ordinary, independently-tunable `scenario` scalars,
    compared only against `PROGRAM_COURSE`'s own matching column, never
    against a live `STUDENT_PROGRAM` row. Confirmed real via the actual
    solved archive: `PROGRAM_COURSE`'s own `PROG_ID` correctly tracks
    `scenario['program']` throughout (both offset together, staying
    consistent with EACH OTHER), while `STUDENT_PROGRAM.PROG_ID` is a
    plain, generic NOT-NULL repair placeholder (`mutation.py`'s own
    `_repair_row`, called once at the very end) completely unrelated to
    either -- e.g. `PROG_ID=64000001` on one side, `PROG_ID=1` on the
    other, for the exact same record.

    Returns {placeholder_name: {'table': ..., 'column': ...}} -- empty
    if this node has no such correlation. Consumed by `dynamosa.py`'s
    own merge step (`merge_archive_candidate`): once a record's own
    focal rows are known, it copies THIS record's own (already-offset)
    `scenario[placeholder]` value onto the correlated table's own
    column, before `repair_candidate`'s later generic fallback would
    otherwise silently paper over the gap -- a post-search correction
    fully in keeping with `decision_subject`'s own precedent just above,
    not a search-loop, fitness, or mutation-operator change."""
    correlations = {}
    filter_text = node.get('filter_text')
    if node.get('kind') not in ('exists', 'derived_aggregate') or not filter_text:
        return correlations
    for column, placeholder in _PLACEHOLDER_CONJUNCT_RE.findall(filter_text):
        source_table = _DECISION_SUBJECT_PLACEHOLDER_SOURCES.get((cs, placeholder))
        if source_table:
            correlations[placeholder] = {'table': source_table, 'column': column}
    return correlations


def compute_subject_hop_placeholder_correlations(subject, node):
    """A SECOND, related shape a `derived_aggregate`/`exists` node's own
    filter_text placeholder can need correlating against (2026-09-25,
    FLEX2's `Course Replacement Eligibility::courseOfferedInFollowing
    Semesters`): the conjunct's own COLUMN -- not the placeholder's own
    name -- matches the SAME decision's own subject row's real FK column
    (`decision_subject['joins']`'s own `from_column`), rather than a
    `filter_placeholder_sources.py`-declared DIFFERENT table. The
    validator resolves this kind directly off the subject row itself
    (`db_resolver._resolve_placeholders`'s own FIRST priority, "the
    subject row's own column of the same name" -- it never even reaches
    `filter_placeholder_sources.py` for this shape), so nothing about
    this needs a declared override on that side. The generator-side gap
    is the mirror image of `compute_cross_table_placeholder_
    correlations` above: confirmed real via the actual archive,
    `Rule_4`'s own `COURSE_OFFER.COURSE_ID` correctly tracks
    `scenario['COURSE_ID']` throughout (both offset together), while the
    SAME record's own `COURSE.COURSE_ID` -- never independently set by
    any leaf, since `courseTypeId`'s own `course_type_id` read needs no
    placeholder at all -- only ever gets a value from `mutation.py`'s
    `_repair_row`, computed as a GLOBALLY fresh key across the whole
    merged database (not per-record-offset-based at all), e.g.
    `COURSE_ID=65000001` on one side, `COURSE_ID=70000006` on the other,
    for the exact same record.

    Returns {placeholder_name: {'table': ..., 'column': ...}} in the
    SAME shape `compute_cross_table_placeholder_correlations` returns --
    consumed by the identical `dynamosa.py` merge-time step, just fed by
    a second, distinct compile-time source. Unlike that function, this
    one needs `subject` (a specific DECISION's own already-computed
    `decision_subject`, not just the case study), so it runs in
    `compile_case_study`'s own per-decision loop, after `subject` is
    known -- see the call site there for why the DIRECTION of the fix
    (copying `scenario[placeholder]` onto the subject's OWN hop target,
    same as the cross-table case) also means it must run BEFORE
    `merge_archive_candidate`'s own subject-junction wiring step, not
    after: that step reads the hop target's own column to wire the
    subject row itself, and must see the corrected value, not a
    not-yet-repaired one it would otherwise lock in first."""
    correlations = {}
    filter_text = node.get('filter_text')
    if node.get('kind') not in ('exists', 'derived_aggregate') or not filter_text or not subject:
        return correlations
    hops_by_from_column = {}
    for hops in subject['joins'].values():
        for hop in hops:
            if hop['from_table'].upper() == subject['table'].upper():
                hops_by_from_column[hop['from_column'].upper()] = hop
    for column, placeholder in _PLACEHOLDER_CONJUNCT_RE.findall(filter_text):
        hop = hops_by_from_column.get(column.upper())
        if hop and placeholder not in correlations:
            correlations[placeholder] = {'table': hop['to_table'], 'column': hop['to_column']}
    return correlations


def _build_subject_join_path(raw_schema, root, target, allowed_tables):
    """Forward-FK-only BFS from `root` to `target`, restricted to
    `allowed_tables` -- see this section's own docstring for the
    disclosed narrower scope (no functional-backward-edge traversal, no
    disambiguation-override support) relative to
    `schema_utility.build_join_path`. Returns a hop list, or None if
    unreachable/ambiguous within scope."""
    root = _canonical_table_name(raw_schema, root)
    target = _canonical_table_name(raw_schema, target)
    if root == target:
        return []

    allowed = {_canonical_table_name(raw_schema, t) for t in allowed_tables} | {root, target}
    visited = {root}
    queue = [(root, [])]
    while queue:
        current, path = queue.pop(0)
        by_target = {}
        for edge in _fk_edges_for(raw_schema, current):
            nxt = edge['ref_table']
            if nxt in allowed and nxt not in visited:
                by_target.setdefault(nxt, []).append(edge)
        for nxt, candidate_edges in by_target.items():
            distinct_columns = {e['column'] for e in candidate_edges}
            if len(distinct_columns) > 1:
                continue  # genuine ambiguity, no override data here -- skip, never guess
            edge = candidate_edges[0]
            hop = {'from_table': current, 'from_column': edge['column'],
                   'to_table': nxt, 'to_column': edge['ref_column']}
            new_path = path + [hop]
            if nxt == target:
                return new_path
            visited.add(nxt)
            queue.append((nxt, new_path))
    return None


def _pick_subject_root(raw_schema, all_tables, closure_tables):
    candidate_pool = closure_tables | all_tables
    candidates = [
        root for root in candidate_pool
        if all(_build_subject_join_path(raw_schema, root, t, closure_tables) is not None
               for t in all_tables - {root})
    ]
    return candidates[0] if len(candidates) == 1 else None


def compute_decision_subject(cs, decision_records, raw_schema):
    """(table, pk_columns, joins) for ONE decision's real DMN subject
    grain, or None if it can't be determined within this pass's own
    disclosed scope (never a guess -- see this section's own docstring).
    `decision_records` is every compiled record for ONE decision (any
    variant/provenance suffix included; the subject is a property of the
    decision, not of one grounding option)."""
    all_tables = set()
    closure_tables = set()
    for r in decision_records:
        closure_tables |= {_canonical_table_name(raw_schema, t) for t in r.get('fk_closure_tables', [])}
        all_tables |= {_canonical_table_name(raw_schema, t)
                       for t in _decision_subject_tables_referenced(cs, r)}

    if not all_tables:
        return None
    if len(all_tables) == 1:
        table = next(iter(all_tables))
        return {'table': table, 'pk_columns': _pk_columns_for(raw_schema, table), 'joins': {}}

    root = _pick_subject_root(raw_schema, all_tables, closure_tables)
    if root is None:
        return None
    joins = {}
    for t in all_tables:
        if t == root:
            continue
        path = _build_subject_join_path(raw_schema, root, t, closure_tables)
        if path is None:
            return None
        joins[t] = path
    return {'table': root, 'pk_columns': _pk_columns_for(raw_schema, root), 'joins': joins}


# ---------------------------------------------------------------------------
# 5. Record assembly
# ---------------------------------------------------------------------------

def load_provenance_citation(cs):
    """Best-effort (dmn_file, decision_name) -> citation string, for a
    human-readable provenance field -- the full rule_provenance_matrix.csv
    remains the authoritative source; this is a convenience lookup only."""
    path = PROVENANCE_PATHS[cs]
    out = {}
    if not os.path.exists(path):
        return out
    with open(path, encoding='utf-8') as f:
        for row in csv.DictReader(f):
            dname = row.get('decision_name') or row.get('decision', '')
            cite = (row.get('source_clause') or row.get('citation') or
                    row.get('clause') or row.get('source') or '')
            if dname and cite and dname not in out:
                out[dname] = cite
    return out


def find_blocking_issues(var_name, node, out=None):
    """Recursively walks one variable's resolution -- including into a
    substituted_decision's own nested free_variable_resolutions -- for any
    unresolved/schema_gap/chained_decision_output leaf. A top-level
    resolution of kind 'substituted_decision' is not itself blocking, but
    its formula only bottoms out into something usable if every one of ITS
    free variables does too; found by an earlier bug in this compiler
    (blocking was checked only at the top level, so a fully-inlined
    formula whose inputs were still unresolved silently compiled anyway)."""
    out = [] if out is None else out
    if not isinstance(node, dict):
        return out
    if node.get('kind') in ('unresolved', 'schema_gap', 'chained_decision_output', 'code_external'):
        out.append((var_name, node['kind'], node.get('reason') or node.get('notes') or node.get('note', '')))
    elif node.get('kind') == 'substituted_decision':
        for fv, sub in node.get('free_variable_resolutions', {}).items():
            find_blocking_issues(fv, sub, out)
    return out


def collect_tables_from_resolution(node, tables):
    if not isinstance(node, dict):
        return
    if node.get('kind') == 'schema_column':
        tables.add(node['table'])
        for t, _c in node.get('also_valid_in', []):
            tables.add(t)
    elif node.get('kind') == 'serialized_field':
        tables.add(node['table'])
    elif node.get('kind') == 'derived':
        for t, _c in node.get('table_hints', []):
            tables.add(t)
    elif node.get('kind') == 'derived_aggregate':
        # 'table' is usually a single name, but can be an explicit
        # comma-joined FROM list (e.g. "PROGRAM_COURSE, COURSE" for a SUM
        # reached via a join, FLEX2's degreeTotalCredits) -- split rather
        # than adding the whole string as one bogus table name.
        for t in node['table'].split(','):
            t = t.strip().split()[0] if t.strip() else ''
            if t:
                tables.add(t)
        if node.get('value_column'):
            tables.add(node['value_column'].split('.')[0])
    elif node.get('kind') == 'null_check':
        tables.add(node['table'])
    elif node.get('kind') == 'any_not_null':
        for c in node.get('columns', []):
            tables.add(c['table'])
    elif node.get('kind') in ('join_lookup', 'join_null_check'):
        tables.add(node['via']['local_table'])
        tables.add(node['result_table'])
    elif node.get('kind') == 'exists':
        for t in node.get('candidate_tables', []):
            tables.add(t)
        for c in node.get('candidate_columns', []):
            tables.add(c['table'])
    elif node.get('kind') == 'regex_match':
        tables.add(node['value_column']['table'])
        tables.add(node['pattern_column']['table'])
    elif node.get('kind') == 'substituted_decision':
        for sub in node.get('free_variable_resolutions', {}).values():
            collect_tables_from_resolution(sub, tables)
    elif node.get('kind') == 'raw_sql_boolean':
        for t in node.get('tables', []):
            tables.add(t)
    elif node.get('kind') == 'derived_case':
        tables.add(node['table'])
    elif node.get('kind') == 'derived_join_count':
        tables.add(node['prereq_table'])
        tables.add(node['registration_table'])


def build_rule_condition(decision, rule):
    """Shared by the main per-rule loop and the chained-dependency
    expansion below (previously duplicated inline in both places). Returns
    (condition, parse_errors, column_predicates) -- parse_errors non-empty
    means condition is meaningless and must not be used."""
    column_predicates = []
    parse_errors = []
    for (col_var, _typeref), text in zip(decision.inputs, rule['input_texts']):
        try:
            node = parse_unary_test(text, col_var)
        except UnsupportedFeelConstruct as e:
            parse_errors.append(f"{col_var}: {e}")
            node = None
        if node is not None:
            column_predicates.append(node)
    if parse_errors:
        return None, parse_errors, column_predicates
    if not column_predicates:
        condition = {'kind': 'literal', 'value': True, 'type': 'boolean'}
    elif len(column_predicates) == 1:
        condition = column_predicates[0]
    else:
        condition = {'op': 'and', 'clauses': column_predicates}
    return condition, [], column_predicates


def parse_output_value(text):
    """Shared literal-output-cell parser (previously duplicated inline)."""
    text = (text or '').strip()
    if text.startswith('"') and text.endswith('"'):
        return {'kind': 'literal', 'value': text[1:-1], 'type': 'string'}
    if text in ('true', 'false'):
        return {'kind': 'literal', 'value': text == 'true', 'type': 'boolean'}
    if re.match(r'^-?\d+(\.\d+)?$', text):
        return {'kind': 'literal', 'value': float(text) if '.' in text else int(text), 'type': 'number'}
    return {'kind': 'literal', 'value': text, 'type': 'string'}


def build_hit_policy_truth_condition(decision, row_idx):
    """A single boolean predicate that is true exactly when `decision`'s
    rule `row_idx` is the one that actually fires, given its hit policy --
    for FIRST/UNIQUE, that rule's own condition AND NOT(every earlier
    rule's own condition), the same suppression logic §6.3's fitness
    function needs, expressed here as a literal formula for inlining into
    a downstream branch rather than as a search-time distance term (see
    `hit_policy_context` for that use). Not meaningful for COLLECT (no
    single rule "wins" -- not needed for this repo's actual chained-
    dependency cases, none of which currently have a COLLECT upstream).
    Returns (condition, ok) -- ok=False if any rule involved fails to
    parse, so the caller can skip this option rather than guess."""
    own_condition, parse_errors, _ = build_rule_condition(decision, decision.rules[row_idx])
    if parse_errors:
        return None, False
    clauses = [own_condition]
    if decision.hit_policy in ('FIRST', 'UNIQUE'):
        for earlier_idx in range(row_idx):
            earlier_condition, earlier_errors, _ = build_rule_condition(decision, decision.rules[earlier_idx])
            if earlier_errors:
                return None, False
            clauses.append({'op': 'not', 'clause': earlier_condition})
    if len(clauses) == 1:
        return clauses[0], True
    return {'op': 'and', 'clauses': clauses}, True


def _grounding_options(cs, gt, upstream_decision, wanted_var, by_id, by_name, seen, commitment):
    """The actual resolution of `chained_decision_output` (generator/README.md's
    documented scope boundary): rather than silently pick one of
    `upstream_decision`'s rules as "the" answer, or leave the dependency
    unresolved, enumerate every rule of `upstream_decision` that produces
    `wanted_var`, each becoming a self-contained "grounding option" --
    §6.1's own self-contained-record requirement means this has to happen
    at compile time, not deferred to the search loop (which would need
    extra machinery to solve one target before another, exactly what
    inlining exists to avoid).

    `commitment` (a shared, mutated-and-restored dict, decision_name ->
    already-chosen rule_id) is this function's own fix for a real,
    measured compile-time bug found 2026-09-12: the SAME upstream
    decision can be needed at more than one place within one record --
    once directly (e.g. a fact this record's own condition or an earlier
    row's suppression term references), once nested (e.g. INSIDE some
    OTHER upstream decision's own further chained dependency) -- and the
    old code enumerated each occurrence completely independently, with
    no shared memory between them. Concretely, one real FLEX2 record
    ended up requiring `priorWarningCount` to be BOTH 0 (from Academic
    Warning Status::Rule_1, chosen to ground a nested dependency of
    Course Load Limit) AND 1 (from Academic Warning Status::Rule_2,
    chosen independently to ground this record's own earlier-row
    suppression term) simultaneously under one top-level AND --
    mathematically unsatisfiable by construction, not merely hard.
    Measured impact: 192 of FLEX2's 391 compiled records (49%) had this
    exact shape. If `upstream_decision.name` is already in `commitment`,
    this function considers ONLY that already-chosen rule (never
    offering a different one as an alternative); otherwise it tries each
    of the decision's own rules in turn, temporarily committing to it
    while exploring what THAT rule's own further chained dependencies
    need (so a still-deeper reference to the SAME decision, or one this
    decision's own rule condition needs, sees and honors the same
    choice), then backtracks (removes the tentative commitment) before
    trying the next rule if that path doesn't work out.

    A grounding option is only offered if EVERY variable its own truth
    condition depends on resolves cleanly -- recursively, including
    further chained_decision_output dependencies (multi-level DRD chains,
    e.g. FLEX2's Academic Warning Status -> Course Load Limit ->
    Course Registration Eligibility) -- via `_enumerate_needs`, the same
    commitment-respecting backtracking search this function's own further
    dependencies use. A dependency that can't be fully grounded yields no
    options for that rule rather than one silently half-resolved; if that
    empties the option list entirely, the caller (compile_case_study)
    leaves the downstream branch blocked, same as before this function
    existed.

    A generator, not a list: yields {'value', 'condition',
    'extra_resolutions', 'source_rule_id', 'source_decision',
    'provenance'} dicts, one per fully-grounded upstream rule (or per
    further-chained combination beneath it) consistent with `commitment`."""
    key = (upstream_decision.name, wanted_var)
    if key in seen:
        return  # circular DRD dependency guard
    seen = seen | {key}

    out_names = [o for o, _ in upstream_decision.outputs]
    if wanted_var not in out_names:
        return
    out_idx = out_names.index(wanted_var)

    dname = upstream_decision.name
    already_committed = dname in commitment
    row_indices = ([i for i, rule in enumerate(upstream_decision.rules) if rule['id'] == commitment[dname]]
                   if already_committed else range(len(upstream_decision.rules)))

    for row_idx in row_indices:
        rule = upstream_decision.rules[row_idx]
        value_node = parse_output_value(rule['output_texts'][out_idx])
        truth_condition, ok = build_hit_policy_truth_condition(upstream_decision, row_idx)
        if not ok:
            continue

        referenced = sorted(set(find_all_variable_refs(truth_condition)))
        base_resolutions = {}
        needs = []  # [(var_name, further_upstream_decision), ...]
        clean = True
        for var in referenced:
            res = resolve_and_substitute(cs, gt, upstream_decision, var, by_id, by_name)
            issues = find_blocking_issues(var, res)
            if not issues:
                base_resolutions[var] = res
                continue
            if any(k != 'chained_decision_output' for _v, k, _d in issues):
                clean = False  # a genuine schema_gap/unresolved dependency -- no way to ground this option
                break
            further_upstream = by_name.get(res['from_decision'])
            if further_upstream is None:
                clean = False
                break
            needs.append((var, further_upstream))
        if not clean:
            continue

        own_label = f"{dname}::{rule['id']}"
        set_here = not already_committed
        if set_here:
            commitment[dname] = rule['id']
        try:
            if not needs:
                yield {'value': value_node, 'condition': truth_condition,
                       'extra_resolutions': dict(base_resolutions),
                       'source_rule_id': rule['id'], 'source_decision': dname,
                       'provenance': [own_label]}
                continue
            for combo, combo_provenance in _enumerate_needs(cs, gt, needs, by_id, by_name, seen, commitment):
                combo_clauses = [truth_condition]
                combo_resolutions = dict(base_resolutions)
                for var_name, sub_opt in combo.items():
                    combo_resolutions[var_name] = {
                        'kind': 'literal_via_upstream_branch', 'value': sub_opt['value'],
                        'from_decision': sub_opt['source_decision'], 'from_rule_id': sub_opt['source_rule_id']}
                    combo_clauses.append(sub_opt['condition'])
                    combo_resolutions.update(sub_opt['extra_resolutions'])
                combined_condition = combo_clauses[0] if len(combo_clauses) == 1 \
                    else {'op': 'and', 'clauses': combo_clauses}
                yield {'value': value_node, 'condition': combined_condition,
                       'extra_resolutions': combo_resolutions,
                       'source_rule_id': rule['id'], 'source_decision': dname,
                       'provenance': [own_label] + combo_provenance}
        finally:
            # Backtrack: a commitment made HERE (not one this call
            # inherited from an outer caller) must not leak into the
            # NEXT rule of this same decision being tried, nor into a
            # sibling branch of the caller's own search that has nothing
            # to do with this particular choice.
            if set_here:
                del commitment[dname]


def _enumerate_needs(cs, gt, needs, by_id, by_name, seen, commitment):
    """Generator: yields (combo, provenance) for a LIST of (var_name,
    upstream_decision) needs, ALL sharing the SAME `commitment` dict --
    a backtracking search, one need at a time, so two needs that trace
    to the SAME upstream decision (however they were discovered -- both
    top-level, both nested, or one of each) are forced to agree on one
    real rule of it rather than being chosen independently (see
    `_grounding_options`'s own docstring for the real bug this fixes).
    `combo` maps var_name -> the option object that grounds it."""
    if not needs:
        yield {}, []
        return
    (var_name, upstream_decision), *rest = needs
    for opt in _grounding_options(cs, gt, upstream_decision, var_name, by_id, by_name, seen, commitment):
        for rest_combo, rest_provenance in _enumerate_needs(cs, gt, rest, by_id, by_name, seen, commitment):
            combo = {var_name: opt}
            combo.update(rest_combo)
            yield combo, opt['provenance'] + rest_provenance


# ---------------------------------------------------------------------------
# 7. Feasibility analysis -- three-valued constant folding
# ---------------------------------------------------------------------------
#
# Grounding (above) and hit-policy suppression can both add clauses to a
# record's condition that were never in the DMN rule's own input cells --
# an upstream branch's own truth_condition (_grounding_options), or an
# earlier row's NOT(...) suppression term. Occasionally these combine into
# something no database instance can ever satisfy: e.g. a rule's own cell
# reads "semesterType = 'Summer'" while the upstream branch chosen to
# ground one of its chained dependencies can only fire when
# "semesterType != 'Summer'". Nothing upstream of this point ever checks
# for that -- each piece is built to be locally correct on its own. This
# pass is the check: fold the fully-assembled condition tree using ONLY
# facts already fixed at compile time (literal constants, and variables
# whose resolution is a grounded upstream branch value or a
# fully-inlined literal-expression decision), leaving every value the
# generator will only decide later at genuinely "unknown" -- then apply
# three-valued (Kleene) logic through the tree's and/or/not structure. A
# record is only ever dropped when this proves it False; True or unknown
# alike are kept and left to the search (never assumed feasible from
# silence, and never guessed at using anything the generator, not
# compilation, is responsible for choosing).

_NOT_GROUNDED = object()


def _grounded_constant_for_variable(var_name, variable_resolution):
    """The variable's compile-time-fixed value, or `_NOT_GROUNDED` if its
    value is only decided once the generator picks concrete database rows
    (a schema_column, null_check, derived_*, exists, join_*, not_persisted,
    schema_gap, code_external, or any other database-dependent resolution
    kind -- every kind except the two handled below)."""
    res = variable_resolution.get(var_name)
    if not isinstance(res, dict):
        return _NOT_GROUNDED
    kind = res.get('kind')
    if kind == 'literal_via_upstream_branch':
        value_node = res.get('value')
        return value_node.get('value') if isinstance(value_node, dict) else _NOT_GROUNDED
    if kind == 'substituted_decision':
        # Fully inlined already (resolve_and_substitute) -- foldable exactly
        # when every one of ITS OWN free variables is foldable, recursively,
        # against ITS OWN free_variable_resolutions (a separate scope: the
        # same variable name can mean something else in the upstream
        # decision than it does here).
        sub_resolutions = res.get('free_variable_resolutions', {})
        return _evaluate_expr_to_constant(
            res.get('expression'),
            lambda v: _grounded_constant_for_variable(v, sub_resolutions))
    return _NOT_GROUNDED


def _evaluate_expr_to_constant(node, resolve_var):
    """Constant-folds a FEEL expression node (feel_parser.py's vocabulary)
    against `resolve_var`, returning `_NOT_GROUNDED` the moment any part of
    it depends on something not yet fixed."""
    if not isinstance(node, dict):
        return _NOT_GROUNDED
    if node.get('kind') == 'literal':
        return node['value']
    if node.get('kind') == 'variable':
        return resolve_var(node['ref'])
    op = node.get('op')
    if op in ('+', '-', '*', '/'):
        left = _evaluate_expr_to_constant(node['left'], resolve_var)
        right = _evaluate_expr_to_constant(node['right'], resolve_var)
        if left is _NOT_GROUNDED or right is _NOT_GROUNDED:
            return _NOT_GROUNDED
        try:
            if op == '+': return left + right
            if op == '-': return left - right
            if op == '*': return left * right
            if op == '/': return left / right
        except (TypeError, ZeroDivisionError):
            return _NOT_GROUNDED
    if op == 'if':
        cond = _fold_condition_three_valued(node['cond'], None, resolve_var)
        if cond is True:
            return _evaluate_expr_to_constant(node['then'], resolve_var)
        if cond is False:
            return _evaluate_expr_to_constant(node['else'], resolve_var)
        return _NOT_GROUNDED
    return _NOT_GROUNDED  # call / opaque_formula -- never evaluated at compile time


def _fold_condition_three_valued(node, variable_resolution, resolve_var=None):
    """Kleene three-valued evaluation of a condition tree: True, False, or
    None ("unknown"). `resolve_var` lets `_evaluate_expr_to_constant`'s own
    'if' branch reuse this function without needing a `variable_resolution`
    dict of its own (a nested expression's 'if' condition is itself an
    ordinary boolean sub-expression, so it recurses back into this same
    function rather than duplicating the and/or/not propagation rules)."""
    resolve = resolve_var or (lambda v: _grounded_constant_for_variable(v, variable_resolution))
    if not isinstance(node, dict):
        return None
    if node.get('kind') == 'literal':
        return bool(node['value']) if node.get('type') == 'boolean' else None
    op = node.get('op')
    if op == 'and':
        values = [_fold_condition_three_valued(c, variable_resolution, resolve) for c in node['clauses']]
        if any(v is False for v in values):
            return False
        if any(v is None for v in values):
            return None
        return True
    if op == 'or':
        values = [_fold_condition_three_valued(c, variable_resolution, resolve) for c in node['clauses']]
        if any(v is True for v in values):
            return True
        if any(v is None for v in values):
            return None
        return False
    if op == 'not':
        value = _fold_condition_three_valued(node['clause'], variable_resolution, resolve)
        return None if value is None else (not value)
    if op in ('=', '!=', '<', '<=', '>', '>='):
        left = _evaluate_expr_to_constant(node['left'], resolve)
        right = _evaluate_expr_to_constant(node['right'], resolve)
        if left is _NOT_GROUNDED or right is _NOT_GROUNDED:
            return None
        try:
            if op == '=': return left == right
            if op == '!=': return left != right
            if op == '<': return left < right
            if op == '<=': return left <= right
            if op == '>': return left > right
            if op == '>=': return left >= right
        except TypeError:
            return None  # incomparable types -- never guessed at
    if op == 'in':
        left = _evaluate_expr_to_constant(node['left'], resolve)
        if left is _NOT_GROUNDED:
            return None
        values = [_evaluate_expr_to_constant(v, resolve) for v in node['values']]
        if any(v is _NOT_GROUNDED for v in values):
            return None
        try:
            return left in values
        except TypeError:
            return None
    if op == 'between':
        left = _evaluate_expr_to_constant(node['left'], resolve)
        low = _evaluate_expr_to_constant(node['low'], resolve)
        high = _evaluate_expr_to_constant(node['high'], resolve)
        if _NOT_GROUNDED in (left, low, high):
            return None
        try:
            return low <= left <= high
        except TypeError:
            return None
    return None  # 'if' at boolean position, or any unrecognized node -- unknown, safe default


def compile_case_study(cs, mapping_source='ground_truth'):
    by_id, by_name = load_case_study_decisions(cs)
    gt = load_case_study_ground_truth(cs)
    fk_graph, all_tables = load_schema_fk_graph(cs)
    citations = load_provenance_citation(cs)

    records = []
    blocked = []

    def cross_variable_reference_flag(column_predicates):
        return any(
            isinstance(node, dict) and node.get('kind') == 'variable'
            for pred in column_predicates
            for node in (pred.get('right'), pred.get('low'), pred.get('high'))
            if isinstance(pred, dict)
        ) or any(
            isinstance(v, dict) and v.get('kind') == 'variable'
            for pred in column_predicates if isinstance(pred, dict)
            for v in pred.get('values', [])
        )

    for decision in by_name.values():
        if not decision.is_table:
            continue  # literal-expression decisions are only ever inlined via substitution, never their own branch target

        for row_idx, rule in enumerate(decision.rules):
            record_id = f"{cs}::{decision.name}::{rule['id']}"
            condition, parse_errors, column_predicates = build_rule_condition(decision, rule)
            if parse_errors:
                blocked.append({'record_id': record_id, 'reason': 'feel_parse_error', 'detail': parse_errors})
                continue

            referenced_vars = sorted(set(find_all_variable_refs(condition)))
            variable_resolution = {}
            own_blocking = []
            for var in referenced_vars:
                res = resolve_and_substitute(cs, gt, decision, var, by_id, by_name)
                variable_resolution[var] = res
                own_blocking.extend(find_blocking_issues(var, res))

            # Earlier-row (FIRST/UNIQUE suppression) conditions and their
            # own free variables -- resolved HERE, before the
            # chained-expansion decision below, not after it (2026-09-12
            # fix; this used to happen per-variant, further down, well
            # after this rule's own condition had already been decided
            # not to need expansion). A real, measured gap this closes:
            # an earlier row can reference a chained_decision_output fact
            # this rule's OWN condition never does at all (FLEX2's Course
            # Load Limit::Rule_4 -- own condition just `semesterType =
            # 'Summer'`, no chained dependency of its own -- inherited an
            # ungroundable `newWarningCount` purely from Rule_1/2/3's own
            # earlier-row suppression context, permanently unresolvable
            # and never coverable by any search as a result, one of
            # exactly 4 FLEX2 records found in this shape). Only a
            # chained_decision_output issue from an earlier row gets the
            # same grounding-expansion treatment as one this rule's own
            # condition needs -- a genuinely unresolved/schema_gap
            # earlier-row variable is still recorded honestly, as-is, and
            # still never newly blocks this record (unchanged from
            # before this fix): only a consumer that actually needs THAT
            # specific suppression term at evaluation time should ever
            # see it fail.
            earlier_rows = []
            earlier_chained_blocking = []
            if decision.hit_policy in ('FIRST', 'UNIQUE'):
                for earlier_idx in range(row_idx):
                    earlier_condition, earlier_errors, _ = build_rule_condition(decision, decision.rules[earlier_idx])
                    if earlier_errors:
                        continue
                    earlier_rows.append({'rule_id': decision.rules[earlier_idx]['id'], 'condition': earlier_condition})
                    for var in find_all_variable_refs(earlier_condition):
                        if var in variable_resolution:
                            continue  # already resolved -- this rule's own condition, or an even-earlier row
                        res = resolve_and_substitute(cs, gt, decision, var, by_id, by_name)
                        variable_resolution[var] = res
                        earlier_chained_blocking.extend(
                            (v, k, d) for v, k, d in find_blocking_issues(var, res) if k == 'chained_decision_output')

            # A rule blocked ONLY by chained_decision_output dependencies
            # is not a dead end -- _enumerate_needs/_grounding_options
            # expand each such dependency into every upstream rule that
            # could produce it (generator/README.md's documented
            # resolution for this scope boundary), producing one
            # self-contained "variant" record per combination rather than
            # leaving the branch unresolved. A mix of chained + genuinely
            # unresolved/schema_gap blocking still blocks outright --
            # expansion can't fix those. Earlier-row-only chained
            # variables are folded in here too (see above), expanded by
            # the exact same mechanism.
            blocking = own_blocking + earlier_chained_blocking
            chained_blocking = [b for b in own_blocking if b[1] == 'chained_decision_output'] + earlier_chained_blocking
            other_blocking = [b for b in own_blocking if b[1] != 'chained_decision_output']

            if other_blocking:
                blocked.append({'record_id': record_id, 'reason': 'unresolved_variable',
                                 'blocking_variables': [{'variable': v, 'kind': k, 'detail': d}
                                                         for v, k, d in blocking]})
                continue

            variants = [(condition, variable_resolution, [])]  # (condition, variable_resolution, provenance_suffix)
            if chained_blocking:
                # One SHARED `commitment` ({}) across every need of this
                # record -- not a separate, independent enumeration per
                # variable -- so two needs that trace to the SAME
                # upstream decision (however each was discovered) are
                # forced to agree on one real rule of it (see
                # _grounding_options's own docstring for the real,
                # measured bug this fixes: 192 of FLEX2's 391 compiled
                # records, 49%, previously ended up requiring the same
                # fact to hold two different values simultaneously,
                # mathematically unsatisfiable by construction, because
                # a nested grounding and a direct one picked different
                # rules of the same upstream decision independently).
                needs = [(var, by_name.get(variable_resolution[var]['from_decision']))
                         for var, _kind, _detail in chained_blocking]
                variants = []
                for combo, provenance in _enumerate_needs(cs, gt, needs, by_id, by_name, set(), {}):
                    vr = dict(variable_resolution)
                    extra_clauses = [condition]
                    for var_name, opt in combo.items():
                        vr[var_name] = {'kind': 'literal_via_upstream_branch', 'value': opt['value'],
                                         'from_decision': opt['source_decision'], 'from_rule_id': opt['source_rule_id']}
                        vr.update(opt['extra_resolutions'])
                        extra_clauses.append(opt['condition'])
                    combined = extra_clauses[0] if len(extra_clauses) == 1 else {'op': 'and', 'clauses': extra_clauses}
                    variants.append((combined, vr, provenance))
                if not variants:
                    blocked.append({'record_id': record_id, 'reason': 'chained_dependency_unexpandable',
                                     'blocking_variables': [{'variable': v, 'kind': k, 'detail': d}
                                                             for v, k, d in blocking]})
                    continue

            for variant_condition, variant_resolution, provenance_suffix in variants:
                variant_id = record_id if not provenance_suffix else f"{record_id}::via::{'+'.join(provenance_suffix)}"

                outputs = {}
                for (out_name, _typeref), out_text in zip(decision.outputs, rule['output_texts']):
                    outputs[out_name] = parse_output_value(out_text)

                # `earlier_rows` and every earlier-row variable it needs
                # (including any chained_decision_output one now grounded
                # into this specific variant's own `variable_resolution`
                # via the combo loop above) were already resolved once,
                # up front -- identical across every variant of this
                # record, so no reason to redo it per variant.
                hit_policy_context = {'earlier_rows': earlier_rows}

                # Feasibility analysis (§7): fold the fully-assembled
                # condition -- own cells, any grounded upstream branch
                # clauses, everything -- using only what's fixed at
                # compile time. Only ever drops a record when this proves
                # it False; True/unknown are both kept for the search.
                full_condition = variant_condition
                if hit_policy_context['earlier_rows']:
                    full_condition = {'op': 'and', 'clauses': [variant_condition] + [
                        {'op': 'not', 'clause': er['condition']} for er in hit_policy_context['earlier_rows']]}
                feasibility = _fold_condition_three_valued(full_condition, variant_resolution)
                if feasibility is False:
                    blocked.append({'record_id': variant_id, 'reason': 'infeasible',
                                     'detail': 'condition provably unsatisfiable by three-valued '
                                               'constant folding of grounded values'})
                    continue

                tables = set()
                for res in variant_resolution.values():
                    collect_tables_from_resolution(res, tables)
                fk_tables = fk_closure(tables, fk_graph, all_tables)

                record = {
                    'record_id': variant_id,
                    'case_study': cs,
                    'dmn_file': decision.dmn_file,
                    'decision_name': decision.name,
                    'hit_policy': decision.hit_policy,
                    'rule_id': rule['id'],
                    'source_citation': citations.get(decision.name, rule.get('description', '')),
                    'condition': variant_condition,
                    'outputs': outputs,
                    'hit_policy_context': hit_policy_context,
                    'variable_resolution': variant_resolution,
                    'fk_closure_tables': fk_tables,
                    'cross_variable_reference': cross_variable_reference_flag(column_predicates),
                    'feasibility': 'true' if feasibility is True else 'unknown',
                }
                if provenance_suffix:
                    record['grounded_upstream_branches'] = provenance_suffix
                records.append(record)

    # Decision subject table (§4b above) -- computed once per decision
    # name (never per variant/provenance-suffixed record: the subject is
    # a property of the DECISION, not of one grounding option), and
    # attached to every one of that decision's own compiled records. A
    # decision this pass can't resolve simply gets no `decision_subject`
    # field at all -- never a hard compile error, never a guess.
    raw_schema = _load_raw_schema(cs)
    records_by_decision_name = {}
    for r in records:
        records_by_decision_name.setdefault(r['decision_name'], []).append(r)
    for decision_records in records_by_decision_name.values():
        subject = compute_decision_subject(cs, decision_records, raw_schema)
        if subject is not None:
            for r in decision_records:
                r['decision_subject'] = subject

        # Filter_text placeholder correlations (2026-09-24/25) --
        # attached directly to the node that needs it, not the record,
        # since two nodes of the same record could in principle use the
        # same placeholder name for different real facts. Two distinct
        # compile-time sources feed the SAME field, consumed identically
        # by `dynamosa.py`'s own merge step: a `filter_placeholder_
        # sources.py`-declared cross-table reference
        # (`compute_cross_table_placeholder_correlations`, needs only
        # `cs`), and a placeholder whose conjunct column matches the
        # decision's OWN subject row's real FK column
        # (`compute_subject_hop_placeholder_correlations`, needs
        # `subject`, hence computed here rather than in an earlier,
        # subject-agnostic pass).
        for r in decision_records:
            for node in r.get('variable_resolution', {}).values():
                if not isinstance(node, dict):
                    continue
                correlations = compute_cross_table_placeholder_correlations(cs, node)
                correlations.update({
                    k: v for k, v in compute_subject_hop_placeholder_correlations(subject, node).items()
                    if k not in correlations
                })
                if correlations:
                    node['cross_table_placeholders'] = correlations

    return records, blocked


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='compiled_constraints.json')
    ap.add_argument('--report', default='compile_report.json')
    ap.add_argument('--case-study', choices=list(CASE_STUDY_DMN_DIRS), default=None,
                     help='Compile only one case study (default: all four).')
    args = ap.parse_args()

    case_studies = [args.case_study] if args.case_study else list(CASE_STUDY_DMN_DIRS)

    all_records = []
    all_blocked = []
    per_cs_stats = {}
    for cs in case_studies:
        records, blocked = compile_case_study(cs)
        all_records.extend(records)
        for b in blocked:
            b['case_study'] = cs
        all_blocked.extend(blocked)
        per_cs_stats[cs] = {'compiled': len(records), 'blocked': len(blocked)}

    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(all_records, f, indent=1)

    reason_counts = Counter(b['reason'] for b in all_blocked)
    blocking_var_reason_counts = Counter()
    for b in all_blocked:
        if b['reason'] == 'unresolved_variable':
            for bv in b['blocking_variables']:
                blocking_var_reason_counts[bv['kind']] += 1

    report = {
        'per_case_study': per_cs_stats,
        'total_compiled': len(all_records),
        'total_blocked': len(all_blocked),
        'blocked_reason_counts': dict(reason_counts),
        'blocking_variable_kind_counts': dict(blocking_var_reason_counts),
        'blocked_records': all_blocked,
    }
    with open(args.report, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=1)

    print(f"Compiled {len(all_records)} branch records, blocked {len(all_blocked)}")
    for cs, stats in per_cs_stats.items():
        total = stats['compiled'] + stats['blocked']
        pct = stats['compiled'] / total * 100 if total else 0
        print(f"  {cs}: {stats['compiled']}/{total} compiled ({pct:.1f}%)")
    print(f"Blocked reasons: {dict(reason_counts)}")
    print(f"Blocking variable kinds (of unresolved_variable blocks): {dict(blocking_var_reason_counts)}")
    print(f"Written {args.out}, {args.report}")


if __name__ == '__main__':
    main()
