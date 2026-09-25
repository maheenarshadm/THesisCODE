#!/usr/bin/env python3
"""
Generic DMN variable extractor: reads every .dmn file for a case study and
produces one row per input/output variable per decision:

    case_study, dmn_file, decision_name, io, variable_name, feel_type,
    literal_values (union of quoted-string literals seen in that column's
    unary tests across all rules, semicolon-separated -- a cheap proxy for
    a declared enumeration when the DMN doesn't have an explicit
    <inputValues> list), label

This is the DMN-side counterpart to schema_extract.py's unified column
table. Together they are the two inputs the mapper (mapper.py) scores
against each other.

Usage:
    python3 dmn_extract.py --out dmn_variables.csv
(case-study DMN directories are hard-coded below, relative to the repo root)

Fixed 2026-09-11: CASE_STUDY_DIRS previously pointed at a different
session's scratchpad layout (flex2_dmn/, openmrs_dmn/, ofbiz_dmn/,
prestashop_dmn/ directly under this script's parent directory) -- none of
those paths exist in this repository, and OFBiz/PrestaShop are no longer
part of the active case-study program in any case (superseded by Spree and
jBilling, design doc §13.1/§7e). Repointed at the actual current package
locations and case-study set.
"""
import os
import re
import csv
import glob
import argparse
from xml.etree import ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(HERE))

DMN_NS = "https://www.omg.org/spec/DMN/20191111/MODEL/"


def q(tag):
    return f'{{{DMN_NS}}}{tag}'


CASE_STUDY_DIRS = {
    'FLEX2': os.path.join(REPO_ROOT, 'jbillingandflex', 'flex2_dmn', 'flex2_dmn', 'dmn'),
    'OpenMRS': os.path.join(REPO_ROOT, 'openmrs_dmn', 'dmn'),
    'Spree': os.path.join(REPO_ROOT, 'spree_dmn', 'dmn'),
    'jBilling': os.path.join(REPO_ROOT, 'jbillingandflex', 'jbilling_dmn', 'jbilling_dmn', 'dmn'),
}


def extract_string_literals(text):
    return set(re.findall(r'"([^"]*)"', text or ''))


# FEEL reserved words and built-in function names that can appear as bare
# identifiers in a literal expression's text without being a real input
# variable. Needed once Spree's literal expressions (FEEL list filters/
# "for x in ... where ... return ...", "if ... then ... else ...") are in
# scope -- FLEX2's/OpenMRS's own literal expressions never needed more than
# excluding and/or/not/true/false, since they're plain arithmetic formulas.
FEEL_KEYWORDS = {
    'and', 'or', 'not', 'true', 'false', 'null',
    'if', 'then', 'else', 'for', 'in', 'return', 'where',
    'some', 'every', 'satisfies', 'instance', 'of',
}
FEEL_BUILTIN_FUNCTIONS = {
    'count', 'sum', 'min', 'max', 'mean', 'median', 'mode', 'stddev',
    'product', 'intersection', 'union', 'distinct', 'values', 'flatten',
    'sort', 'append', 'insert', 'before', 'remove', 'reverse', 'index',
    'contains', 'starts', 'ends', 'matches', 'substring', 'string',
    'number', 'date', 'time', 'duration', 'upper', 'lower', 'case',
    'length', 'list',
}


def extract_free_identifiers(expr_text, exclude=()):
    """Free (external) identifiers referenced in a FEEL literal expression,
    for use as a literal-expression decision's pseudo-inputs.

    Handles what FLEX2's/OpenMRS's plain arithmetic formulas never needed
    to: string literals (stripped first, so words inside them are never
    mistaken for identifiers), a "for X in ..." loop-bound variable X
    (excluded -- it's locally bound, not an external input), dotted-path
    field access (order.customer -> only the root "order" is the real free
    reference; the rest is a property access on it), and FEEL reserved
    words / built-in function names (excluded via the lists above).
    """
    if not expr_text:
        return []
    text = re.sub(r'"[^"]*"', ' ', expr_text)
    bound_vars = set(re.findall(r'\bfor\s+([A-Za-z_][A-Za-z0-9_]*)\s+in\b', text))
    tokens = re.findall(r'[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*', text)
    roots = {tok.split('.', 1)[0] for tok in tokens}
    excluded = FEEL_KEYWORDS | FEEL_BUILTIN_FUNCTIONS | bound_vars | set(exclude)
    return sorted(roots - excluded)


def extract_case_study(case_study, dmn_dir):
    rows = []
    for path in sorted(glob.glob(os.path.join(dmn_dir, '*.dmn'))):
        tree = ET.parse(path)
        root = tree.getroot()
        fname = os.path.basename(path)
        for dec in root.findall(q('decision')):
            dname = dec.get('name')
            dt = dec.find(q('decisionTable'))
            if dt is None:
                # literal-expression decision (FLEX2's Attendance Percentage):
                # no declared <input> elements -- the formula's free
                # identifiers ARE its inputs, so extract them as pseudo-inputs
                # (type unknown -- a literal expression doesn't declare one
                # per identifier) rather than silently dropping them.
                var_el = dec.find(q('variable'))
                if var_el is not None:
                    rows.append({
                        'case_study': case_study, 'dmn_file': fname,
                        'decision_name': dname, 'io': 'output',
                        'variable_name': var_el.get('name'),
                        'feel_type': var_el.get('typeRef', ''),
                        'literal_values': '', 'label': '',
                    })
                lit_el = dec.find(q('literalExpression'))
                if lit_el is not None:
                    text_el = lit_el.find(q('text'))
                    expr_text = text_el.text if text_el is not None else ''
                    out_name = var_el.get('name') if var_el is not None else ''
                    idents = extract_free_identifiers(expr_text, exclude={out_name} if out_name else ())
                    for ident in idents:
                        rows.append({
                            'case_study': case_study, 'dmn_file': fname,
                            'decision_name': dname, 'io': 'input',
                            'variable_name': ident, 'feel_type': '',
                            'literal_values': '', 'label': '',
                        })
                continue

            inputs = dt.findall(q('input'))
            outputs = dt.findall(q('output'))
            input_exprs = []
            literals_by_col = {i: set() for i in range(len(inputs))}
            for idx, inp in enumerate(inputs):
                expr_el = inp.find(q('inputExpression'))
                text_el = expr_el.find(q('text')) if expr_el is not None else None
                expr = text_el.text if text_el is not None else ''
                input_exprs.append(expr)
                typeref = expr_el.get('typeRef', '') if expr_el is not None else ''
                label = inp.get('label', '')
                iv = inp.find(q('inputValues'))
                declared_values = ''
                if iv is not None:
                    ivtext = iv.find(q('text'))
                    if ivtext is not None and ivtext.text:
                        declared_values = ivtext.text
                rows.append({
                    'case_study': case_study, 'dmn_file': fname,
                    'decision_name': dname, 'io': 'input',
                    'variable_name': expr, 'feel_type': typeref,
                    'literal_values': declared_values, 'label': label,
                })

            for rule in dt.findall(q('rule')):
                entries = rule.findall(q('inputEntry'))
                for idx, entry in enumerate(entries):
                    text_el = entry.find(q('text'))
                    t = text_el.text if text_el is not None else ''
                    if idx in literals_by_col:
                        literals_by_col[idx] |= extract_string_literals(t)

            # merge observed literals into the input rows just appended
            n_inputs = len(inputs)
            base = len(rows) - n_inputs
            for idx in range(n_inputs):
                existing_raw = rows[base + idx]['literal_values']
                existing = extract_string_literals(existing_raw) or \
                    {v.strip() for v in existing_raw.split(',') if v.strip()}
                merged = existing | literals_by_col.get(idx, set())
                if merged:
                    rows[base + idx]['literal_values'] = ';'.join(sorted(merged))

            for outp in outputs:
                oname = outp.get('name')
                otyperef = outp.get('typeRef', '')
                rows.append({
                    'case_study': case_study, 'dmn_file': fname,
                    'decision_name': dname, 'io': 'output',
                    'variable_name': oname, 'feel_type': otyperef,
                    'literal_values': '', 'label': outp.get('label', ''),
                })

            var_el = dec.find(q('variable'))
            if var_el is not None and dt is not None:
                # decision's own output variable (redundant with <output> in
                # most of our files, but harmless if it duplicates)
                pass
    return rows


def build_all():
    rows = []
    for cs, d in CASE_STUDY_DIRS.items():
        rows += extract_case_study(cs, d)
    return rows


def write_csv(rows, path):
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['case_study', 'dmn_file', 'decision_name', 'io',
                     'variable_name', 'feel_type', 'literal_values', 'label'])
        for r in rows:
            w.writerow([r['case_study'], r['dmn_file'], r['decision_name'],
                        r['io'], r['variable_name'], r['feel_type'],
                        r['literal_values'], r['label']])


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='dmn_variables.csv')
    args = ap.parse_args()
    rows = build_all()
    write_csv(rows, args.out)
    from collections import Counter
    by_cs = Counter(r['case_study'] for r in rows)
    print(f"Total variable rows extracted: {len(rows)}")
    for cs, n in by_cs.items():
        print(f"  {cs}: {n} rows")
    print(f"Written to {args.out}")
