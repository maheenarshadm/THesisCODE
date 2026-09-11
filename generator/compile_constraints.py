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
    ('derived-aggregate', 'derived'),
    ('derived - aggregate', 'derived'),
    ('derived', 'derived'),
    ('direct', 'direct'),
]


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


def _try_extract_aggregate_recipe(text):
    """Best-effort structured recipe extraction for the two mechanically-
    recognizable aggregate shapes actually seen in the hand-curated
    notes/schema-field text: "COUNT(TABLE) WHERE <filter>" (§6.1's own
    worked example resolves lecturesAttended/lecturesHeldForOffering
    exactly this way) and "TABLE (COUNT WHERE <filter>)" (the reversed
    word order several other case studies' notes happen to use). This is
    deliberately not a general WHERE-clause parser -- the filter text is
    kept verbatim for a human (or a later, more targeted pass) to turn
    into the design doc's fully structured {"filter": [...]} shape;
    extracting the aggregate function and target table mechanically is
    what turns an otherwise unresolved/generic-derived block into the
    richer 'derived_aggregate' resolution the design doc's own example
    uses, without inventing filter semantics this script has no
    case-study-specific knowledge to get right."""
    if not text:
        return None
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
    return {'kind': 'derived_aggregate', 'aggregate': aggregate, 'table': table,
            'filter_text': filter_text, 'source_text': text}


_EXISTENCE_WORDS = re.compile(
    r'\b(IS NOT NULL|IS NULL|existence check|null-check|null check)\b', re.I)
_ANY_OF_WORDS = re.compile(r'\b(OR of|either|any of|either populated)\b', re.I)
_EXISTS_ROW_WORDS = re.compile(
    r'\bexistence of\b|\(existence\)|\bEXISTS\(|self-join', re.I)
_JOINED_VIA_RE = re.compile(r'joined via ([A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*)', re.I)
_CONSTANT_RE = re.compile(r'(?:constant|=)\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(-?\d+)')


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

    agg = _try_extract_aggregate_recipe(notes) or _try_extract_aggregate_recipe(raw)
    if agg:
        return agg

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
        m = _JOINED_VIA_RE.search(notes)
        if m and len(pairs) >= 1:
            local_table, local_column = m.group(1).split('.')
            target_table, target_column = pairs[-1]  # the last-mentioned pair is the joined-to fact, by convention of how these notes are written
            node = {'kind': 'join_lookup',
                    'via': {'local_table': local_table, 'local_column': local_column},
                    'result_table': target_table, 'result_column': target_column, 'notes': notes}
            if _EXISTENCE_WORDS.search(notes):
                node['kind'] = 'join_null_check'
            return node
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
        m = re.match(r'\s*([A-Za-z_][A-Za-z0-9_]*)\s*\(', raw)
        if m:
            return {'kind': 'exists', 'candidate_tables': [m.group(1)],
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
    elif node.get('kind') == 'derived':
        for t, _c in node.get('table_hints', []):
            tables.add(t)
    elif node.get('kind') == 'derived_aggregate':
        tables.add(node['table'])
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


def compile_case_study(cs, mapping_source='ground_truth'):
    by_id, by_name = load_case_study_decisions(cs)
    gt = load_case_study_ground_truth(cs)
    fk_graph, all_tables = load_schema_fk_graph(cs)
    citations = load_provenance_citation(cs)

    records = []
    blocked = []

    for decision in by_name.values():
        if not decision.is_table:
            continue  # literal-expression decisions are only ever inlined via substitution, never their own branch target

        for row_idx, rule in enumerate(decision.rules):
            record_id = f"{cs}::{decision.name}::{rule['id']}"
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
                blocked.append({'record_id': record_id, 'reason': 'feel_parse_error', 'detail': parse_errors})
                continue

            if not column_predicates:
                condition = {'kind': 'literal', 'value': True, 'type': 'boolean'}  # all-wildcard row
            elif len(column_predicates) == 1:
                condition = column_predicates[0]
            else:
                condition = {'op': 'and', 'clauses': column_predicates}

            referenced_vars = sorted(set(find_all_variable_refs(condition)))
            variable_resolution = {}
            blocking = []
            for var in referenced_vars:
                res = resolve_and_substitute(cs, gt, decision, var, by_id, by_name)
                variable_resolution[var] = res
                blocking.extend(find_blocking_issues(var, res))

            if blocking:
                blocked.append({'record_id': record_id, 'reason': 'unresolved_variable',
                                 'blocking_variables': [{'variable': v, 'kind': k, 'detail': d}
                                                         for v, k, d in blocking]})
                continue

            outputs = {}
            for (out_name, _typeref), out_text in zip(decision.outputs, rule['output_texts']):
                out_text = (out_text or '').strip()
                if out_text.startswith('"') and out_text.endswith('"'):
                    outputs[out_name] = {'kind': 'literal', 'value': out_text[1:-1], 'type': 'string'}
                elif out_text in ('true', 'false'):
                    outputs[out_name] = {'kind': 'literal', 'value': out_text == 'true', 'type': 'boolean'}
                elif re.match(r'^-?\d+(\.\d+)?$', out_text):
                    outputs[out_name] = {'kind': 'literal',
                                          'value': float(out_text) if '.' in out_text else int(out_text),
                                          'type': 'number'}
                else:
                    outputs[out_name] = {'kind': 'literal', 'value': out_text, 'type': 'string'}

            hit_policy_context = {'earlier_rows': []}
            if decision.hit_policy in ('FIRST', 'UNIQUE'):
                for earlier_idx in range(row_idx):
                    earlier_rule = decision.rules[earlier_idx]
                    earlier_preds = []
                    ok = True
                    for (col_var, _t), text in zip(decision.inputs, earlier_rule['input_texts']):
                        try:
                            n = parse_unary_test(text, col_var)
                        except UnsupportedFeelConstruct:
                            ok = False
                            break
                        if n is not None:
                            earlier_preds.append(n)
                    if not ok:
                        continue
                    if not earlier_preds:
                        earlier_cond = {'kind': 'literal', 'value': True, 'type': 'boolean'}
                    elif len(earlier_preds) == 1:
                        earlier_cond = earlier_preds[0]
                    else:
                        earlier_cond = {'op': 'and', 'clauses': earlier_preds}
                    hit_policy_context['earlier_rows'].append(
                        {'rule_id': earlier_rule['id'], 'condition': earlier_cond})

            tables = set()
            for res in variable_resolution.values():
                collect_tables_from_resolution(res, tables)
            fk_tables = fk_closure(tables, fk_graph, all_tables)

            cross_variable_reference = any(
                isinstance(node, dict) and node.get('kind') == 'variable'
                for pred in column_predicates
                for node in (pred.get('right'), pred.get('low'), pred.get('high'))
                if isinstance(pred, dict)
            ) or any(
                isinstance(v, dict) and v.get('kind') == 'variable'
                for pred in column_predicates if isinstance(pred, dict)
                for v in pred.get('values', [])
            )

            records.append({
                'record_id': record_id,
                'case_study': cs,
                'dmn_file': decision.dmn_file,
                'decision_name': decision.name,
                'hit_policy': decision.hit_policy,
                'rule_id': rule['id'],
                'source_citation': citations.get(decision.name, rule.get('description', '')),
                'condition': condition,
                'outputs': outputs,
                'hit_policy_context': hit_policy_context,
                'variable_resolution': variable_resolution,
                'fk_closure_tables': fk_tables,
                'cross_variable_reference': cross_variable_reference,
            })

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
