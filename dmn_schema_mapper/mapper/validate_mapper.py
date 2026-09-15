#!/usr/bin/env python3
"""
Validates mapper.py's output against the current four hand-built
variable_to_schema_mapping.csv ground-truth files (274 rows total, per
design doc §13.5) across the current case-study program.

Ground truth's schema-location column (name/shape varies per case study --
see GT_CONFIG) is free text, not a strict schema -- it can be
"table.column", multiple comma-separated "table.column" pairs, "n/a",
"not-persisted", or a prose description of a derived/aggregate fact. We
extract every "word.word" token pair from it as the set of true (table,
column) references, case-insensitive.

Metrics reported, per case study and overall:
  - Not-persisted / schema-gap classification accuracy (did the mapper
    correctly predict 'not-persisted' for ground-truth not-persisted rows,
    and NOT predict it for ground-truth-grounded rows?)
  - Top-1 exact match rate (predicted table.column == a true pair), among
    ground-truth rows that DO have a real column reference
  - Top-3 hit rate (true pair appears anywhere in the top-3 candidates)
  - Derived-fact detection recall (did the mapper flag a variable as
    'derived'/'likely derived' when ground truth's mapping_type was
    'derived' or its notes describe a multi-column/aggregate/join fact?)

This is the number that answers "is this actually usable as an input to
the generator, or does someone still have to check every row" -- reported
honestly, not rounded up.

Fixed 2026-09-11: GT_FILES previously hard-coded absolute paths into a
different session's scratchpad (`/tmp/claude-0/-home-claude/...`), none of
which exist in this repository, and covered the pre-swap case-study set
(FLEX2/OpenMRS/OFBiz/PrestaShop) -- neither Spree nor jBilling, which
actually replaced OFBiz and PrestaShop, were ever validated against. This
now points at the real, current ground-truth files for all four current
case studies (design doc §13.1/§7e). Spree's mapping CSV uses a different,
simpler column layout than the other three (decision/variable instead of
decision_name/variable_name, and no dmn_file/io columns at all -- it was
built by a different session's build script) -- GT_CONFIG captures that
difference per case study instead of assuming one fixed header shape.
"""
import csv
import os
import re
import argparse
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(HERE))

# key_cols determines how a ground-truth row is matched to a mapper
# prediction: the standard four case studies were mined with the full
# (dmn_file, decision_name, variable_name, io) key mapper.py's own output
# uses; Spree's ground truth only recorded decision+variable, so it's
# matched on that narrower key instead (safe here since no decision in
# Spree's 14-decision program reuses one variable name as both an input
# and an output).
GT_CONFIG = {
    'FLEX2': {
        'path': os.path.join(REPO_ROOT, 'jbillingandflex', 'flex2_dmn', 'flex2_dmn',
                              'provenance', 'variable_to_schema_mapping.csv'),
        'decision_col': 'decision_name', 'variable_col': 'variable_name',
        'schema_col': 'flex2_table_column', 'notes_col': 'notes',
        'key_cols': ('dmn_file', 'decision_name', 'variable_name', 'io'),
    },
    'OpenMRS': {
        'path': os.path.join(REPO_ROOT, 'openmrs_dmn',
                              'provenance', 'variable_to_schema_mapping.csv'),
        'decision_col': 'decision_name', 'variable_col': 'variable_name',
        'schema_col': 'openmrs_table_column', 'notes_col': 'notes',
        'key_cols': ('dmn_file', 'decision_name', 'variable_name', 'io'),
    },
    'jBilling': {
        'path': os.path.join(REPO_ROOT, 'jbillingandflex', 'jbilling_dmn', 'jbilling_dmn',
                              'provenance', 'variable_to_schema_mapping.csv'),
        'decision_col': 'decision_name', 'variable_col': 'variable_name',
        'schema_col': 'jbilling_column', 'notes_col': 'notes',
        'key_cols': ('dmn_file', 'decision_name', 'variable_name', 'io'),
    },
    'Spree': {
        'path': os.path.join(REPO_ROOT, 'spree_dmn',
                              'provenance', 'variable_to_schema_mapping.csv'),
        'decision_col': 'decision', 'variable_col': 'variable',
        'schema_col': 'schema_location', 'notes_col': 'note',
        'key_cols': ('decision_name', 'variable_name'),
    },
}

PAIR_RE = re.compile(r'\b([A-Za-z][A-Za-z0-9_]*)\.([A-Za-z][A-Za-z0-9_]*)\b')


def true_pairs(text):
    return {(t.lower(), c.lower()) for t, c in PAIR_RE.findall(text or '')}


def is_gt_not_persisted(mapping_type, schema_field_text):
    mt = (mapping_type or '').lower()
    txt = (schema_field_text or '').strip().lower()
    return 'not-persisted' in mt or txt in ('n/a', 'not-persisted', '')


def is_gt_derived(mapping_type, notes):
    mt = (mapping_type or '').lower()
    return 'derived' in mt or ('schema gap' in mt and 'derived' in (notes or '').lower())


def load_ground_truth(cs):
    cfg = GT_CONFIG[cs]
    rows = {}
    with open(cfg['path'], encoding='utf-8') as f:
        for row in csv.DictReader(f):
            decision_name = row[cfg['decision_col']]
            variable_name = row[cfg['variable_col']]
            schema_field = row.get(cfg['schema_col'], '')
            if 'dmn_file' in cfg['key_cols']:
                key = (row['dmn_file'], decision_name, variable_name, row['io'])
            else:
                key = (decision_name, variable_name)
            rows[key] = {
                'mapping_type': row.get('mapping_type', ''),
                'schema_field': schema_field,
                'notes': row.get(cfg['notes_col'], ''),
                'true_pairs': true_pairs(schema_field),
            }
    return rows


def load_predictions(path):
    """Two indices over mapping_auto.csv: the full (dmn_file, decision_name,
    variable_name, io) key every case study's predictions carry, and a
    narrower (decision_name, variable_name) key for case studies (Spree)
    whose ground truth doesn't record dmn_file/io."""
    full_index = {}
    short_index = {}
    with open(path, encoding='utf-8') as f:
        for row in csv.DictReader(f):
            top3 = set()
            for part in row['top3_candidates'].split(';'):
                m = re.match(r'\s*([A-Za-z0-9_]+)\.([A-Za-z0-9_]+)', part)
                if m:
                    top3.add((m.group(1).lower(), m.group(2).lower()))
            pred = {
                'predicted_table': row['predicted_table'],
                'predicted_column': row['predicted_column'],
                'predicted_mapping_type': row['predicted_mapping_type'],
                'top3': top3,
            }
            cs = row['case_study']
            full_key = (cs, row['dmn_file'], row['decision_name'], row['variable_name'], row['io'])
            short_key = (cs, row['decision_name'], row['variable_name'])
            full_index[full_key] = pred
            short_index.setdefault(short_key, pred)  # first match wins on collision
    return full_index, short_index


def evaluate(cs, gt, full_index, short_index):
    cfg = GT_CONFIG[cs]
    uses_short_key = 'dmn_file' not in cfg['key_cols']

    n_total = 0
    n_np_correct = n_np_total = 0
    n_grounded_total = 0
    n_top1 = 0
    n_top3 = 0
    n_derived_gt = n_derived_caught = 0
    unmatched_keys = 0

    for key, g in gt.items():
        n_total += 1
        if uses_short_key:
            p = short_index.get((cs,) + key)
        else:
            dmn_file, decision_name, variable_name, io = key
            p = full_index.get((cs, dmn_file, decision_name, variable_name, io))
        if p is None:
            unmatched_keys += 1
            continue

        gt_np = is_gt_not_persisted(g['mapping_type'], g['schema_field'])
        pred_np = 'not-persisted' in p['predicted_mapping_type'].lower() or \
                  'needs review' in p['predicted_mapping_type'].lower()
        if gt_np:
            n_np_total += 1
            if pred_np:
                n_np_correct += 1
        else:
            if g['true_pairs']:
                n_grounded_total += 1
                pred_pair = (p['predicted_table'].lower(), p['predicted_column'].lower()) \
                    if p['predicted_table'] else None
                if pred_pair and pred_pair in g['true_pairs']:
                    n_top1 += 1
                if p['top3'] & g['true_pairs']:
                    n_top3 += 1

        if is_gt_derived(g['mapping_type'], g['notes']):
            n_derived_gt += 1
            if 'derived' in p['predicted_mapping_type'].lower():
                n_derived_caught += 1

    return {
        'case_study': cs, 'n_total': n_total, 'unmatched_keys': unmatched_keys,
        'not_persisted_accuracy': (n_np_correct / n_np_total) if n_np_total else None,
        'n_not_persisted': n_np_total,
        'grounded_top1_rate': (n_top1 / n_grounded_total) if n_grounded_total else None,
        'grounded_top3_rate': (n_top3 / n_grounded_total) if n_grounded_total else None,
        'n_grounded': n_grounded_total,
        'derived_recall': (n_derived_caught / n_derived_gt) if n_derived_gt else None,
        'n_derived_gt': n_derived_gt,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--auto', default='mapping_auto.csv')
    args = ap.parse_args()

    full_index, short_index = load_predictions(args.auto)

    all_results = []
    for cs in GT_CONFIG:
        gt = load_ground_truth(cs)
        res = evaluate(cs, gt, full_index, short_index)
        all_results.append(res)

    print(f"{'Case study':<12} {'N':>4} {'unmatch':>7} {'NP-acc':>7} {'NP-n':>5} "
          f"{'Top1':>6} {'Top3':>6} {'Grnd-n':>6} {'DerivRec':>8} {'Der-n':>5}")
    for r in all_results:
        def fmt(x):
            return f'{x:.1%}' if x is not None else 'n/a'
        print(f"{r['case_study']:<12} {r['n_total']:>4} {r['unmatched_keys']:>7} "
              f"{fmt(r['not_persisted_accuracy']):>7} {r['n_not_persisted']:>5} "
              f"{fmt(r['grounded_top1_rate']):>6} {fmt(r['grounded_top3_rate']):>6} "
              f"{r['n_grounded']:>6} {fmt(r['derived_recall']):>8} {r['n_derived_gt']:>5}")

    # overall
    tot_np_c = sum((r['not_persisted_accuracy'] or 0) * r['n_not_persisted'] for r in all_results)
    tot_np_n = sum(r['n_not_persisted'] for r in all_results)
    tot_t1 = sum((r['grounded_top1_rate'] or 0) * r['n_grounded'] for r in all_results)
    tot_t3 = sum((r['grounded_top3_rate'] or 0) * r['n_grounded'] for r in all_results)
    tot_gr = sum(r['n_grounded'] for r in all_results)
    tot_dr = sum((r['derived_recall'] or 0) * r['n_derived_gt'] for r in all_results)
    tot_dn = sum(r['n_derived_gt'] for r in all_results)
    print(f"\nOverall: not-persisted-accuracy={tot_np_c/tot_np_n:.1%} (n={tot_np_n}), "
          f"top1={tot_t1/tot_gr:.1%} (n={tot_gr}), top3={tot_t3/tot_gr:.1%}, "
          f"derived-recall={tot_dr/tot_dn:.1%} (n={tot_dn})")


if __name__ == '__main__':
    main()
