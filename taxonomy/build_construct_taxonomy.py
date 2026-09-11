#!/usr/bin/env python3
"""
Rebuilds the DMN-to-SQL/DDL construct taxonomy (design doc §7b) as an
actual, current, code-computed artifact.

Why this exists: the design doc's prose describes a `taxonomy/` directory
(`extract_structure.py`, `classify_constructs.py`, `rule_taxonomy.csv`,
`dmn_to_ddl_construct_taxonomy.md`) as already built -- none of it exists
anywhere in this repository, confirmed by an exhaustive search. Same root
cause as the OpenMRS/Spree DMN packages gap fixed earlier: apparently
produced in a prior session's context and never actually committed. On
top of that, the specific 17-category, 291-row table the design doc
quotes is *also* already stale on content grounds -- it sums to 291 and
names PrestaShop-specific constructs (`specific_price`/`tax_rule`
precedence, the `idShop` vs `"0, contextShopId"` FEEL-list pattern),
predating both the PrestaShop->jBilling swap (§7e) and the OFBiz->Spree
swap (§13.1).

This is a rebuild, not a byte-for-byte reproduction of the lost original
-- its category boundaries are freshly designed and documented here, not
reverse-engineered to match unrecoverable numbers. It is also more
rigorous than what the design doc describes the original as having been:
where the original was built by rule-based classification of
`variable_to_schema_mapping.csv`'s free-text notes alone, this version
combines that (via compile_constraints.py's own `resolve_variable`/
`classify_derived` -- reused, not reimplemented, so there is exactly one
source of truth for "how is this variable resolved") with the *parsed
FEEL predicate trees* `generator/compiled_constraints.py` already
produced for every compiled branch, which answer several usage-shape
questions (is this compared to another variable? is this a set-membership
test? a range test?) far more reliably than guessing from prose ever
could.

Two outputs:
    construct_taxonomy.csv   -- one row per ground-truth variable, tagged
                                 with its storage-shape category
    usage_shapes.csv         -- one row per compiled branch's condition,
                                 tagged with the FEEL-operator shapes it uses

Usage:
    python3 build_construct_taxonomy.py --out-dir .
"""
import os
import sys
import csv
import json
import argparse
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO_ROOT, 'generator'))
sys.path.insert(0, os.path.join(REPO_ROOT, 'dmn_schema_mapper', 'mapper'))

from compile_constraints import (  # noqa: E402
    load_case_study_ground_truth, resolve_variable, classify_derived,
    CASE_STUDY_DMN_DIRS, find_all_variable_refs,
)
import validate_mapper as vm  # noqa: E402


# ---------------------------------------------------------------------------
# Storage-shape categories -- computed from each ground-truth row's own
# resolution (reusing compile_constraints.py's resolve_variable, so this
# taxonomy can never silently drift from what the compiler itself believes
# about a given variable).
# ---------------------------------------------------------------------------

CATEGORY_ORDER = [
    'Direct Attribute Reference',
    'Not-Persisted',
    'Schema Gap',
    'Single-Column Predicate',
    'Aggregate Function',
    'Cross-Table Join',
    'Existence / Correlated Subquery',
    'Multi-Column Existence (any-of)',
    'Pattern/Regex Match',
    'Decision Output / Write-Back Target',
    'Compound / Unclassified Derivation',
    'Chained Decision Output',
    'Code-External (no schema representation)',
]


def categorize(io, resolution):
    kind = resolution.get('kind')
    if kind == 'not_persisted':
        return 'Not-Persisted'
    if kind == 'schema_gap':
        return 'Schema Gap'
    if kind == 'schema_column':
        if io == 'output':
            return 'Decision Output / Write-Back Target'
        return 'Direct Attribute Reference'
    if kind == 'null_check':
        return 'Single-Column Predicate'
    if kind == 'derived_aggregate':
        return 'Aggregate Function'
    if kind in ('join_lookup',):
        return 'Cross-Table Join'
    if kind in ('exists', 'join_null_check'):
        return 'Existence / Correlated Subquery'
    if kind == 'any_not_null':
        return 'Multi-Column Existence (any-of)'
    if kind == 'regex_match':
        return 'Pattern/Regex Match'
    if kind == 'derived':
        return 'Compound / Unclassified Derivation'
    if kind == 'chained_decision_output':
        return 'Chained Decision Output'
    if kind == 'code_external':
        return 'Code-External (no schema representation)'
    if kind == 'unresolved':
        return 'Compound / Unclassified Derivation'  # not found in ground truth at all -- rare, folded in rather than a 13th one-off bucket
    return f'UNCLASSIFIED:{kind}'


def build_storage_taxonomy():
    rows = []
    for cs in CASE_STUDY_DMN_DIRS:
        gt = load_case_study_ground_truth(cs)
        # Spree's ground truth has no io column at all -- load_case_study_
        # ground_truth (compile_constraints.py) indexes every such row
        # under BOTH ('input') and ('output') as a lookup convenience, so
        # dedup on (case_study, decision_name, variable_name) identity
        # (the underlying row object), not the 3-part key, or every Spree
        # variable is counted twice.
        seen_rows = set()
        for (decision_name, var_name, io), row in gt.items():
            row_identity = id(row)
            if row_identity in seen_rows:
                continue
            seen_rows.add(row_identity)
            resolution = resolve_variable(cs, gt, decision_name, var_name, io)
            category = categorize(io, resolution)
            rows.append({
                'case_study': cs, 'decision_name': decision_name, 'variable_name': var_name,
                'io': io, 'category': category, 'mapping_type_raw': row['bucket'],
                'notes': row['notes'],
            })
    return rows


# ---------------------------------------------------------------------------
# Usage-shape tagging -- walks compiled_constraints.json's own parsed
# condition trees (not re-parsing FEEL text) since those are already
# validated at 100% coverage against the program's real DMN files.
# ---------------------------------------------------------------------------

def tag_usage_shapes(condition):
    shapes = set()

    def walk(node):
        if not isinstance(node, dict):
            return
        op = node.get('op')
        if op in ('<', '<=', '>', '>=', '=', '!='):
            for side in ('left', 'right'):
                if isinstance(node.get(side), dict) and node[side].get('kind') == 'variable' and side == 'right':
                    shapes.add('cross-variable comparison')
            walk(node.get('left'))
            walk(node.get('right'))
        elif op == 'in':
            shapes.add('set-membership (IN)')
            if any(isinstance(v, dict) and v.get('kind') == 'variable' for v in node.get('values', [])):
                shapes.add('set-membership with a variable member')
            walk(node.get('left'))
        elif op == 'between':
            shapes.add('range test (BETWEEN)')
            for side in ('low', 'high'):
                if isinstance(node.get(side), dict) and node[side].get('kind') == 'variable':
                    shapes.add('range test with a variable bound')
        elif op == 'not':
            shapes.add('negation (NOT)')
            walk(node.get('clause'))
        elif op == 'and':
            for c in node.get('clauses', []):
                walk(c)
        elif op in ('+', '-', '*', '/'):
            walk(node.get('left'))
            walk(node.get('right'))

    walk(condition)
    return sorted(shapes) or ['plain single comparison']


def build_usage_shapes(compiled_path):
    with open(compiled_path, encoding='utf-8') as f:
        records = json.load(f)
    rows = []
    for r in records:
        shapes = tag_usage_shapes(r['condition'])
        rows.append({
            'case_study': r['case_study'], 'record_id': r['record_id'],
            'decision_name': r['decision_name'], 'hit_policy': r['hit_policy'],
            'usage_shapes': '; '.join(shapes),
        })
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out-dir', default='.')
    ap.add_argument('--compiled', default=os.path.join(REPO_ROOT, 'generator', 'compiled_constraints.json'))
    args = ap.parse_args()

    storage_rows = build_storage_taxonomy()
    with open(os.path.join(args.out_dir, 'construct_taxonomy.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['case_study', 'decision_name', 'variable_name', 'io',
                                           'category', 'mapping_type_raw', 'notes'])
        w.writeheader()
        w.writerows(storage_rows)

    usage_rows = build_usage_shapes(args.compiled)
    with open(os.path.join(args.out_dir, 'usage_shapes.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['case_study', 'record_id', 'decision_name', 'hit_policy', 'usage_shapes'])
        w.writeheader()
        w.writerows(usage_rows)

    total = len(storage_rows)
    c = Counter(r['category'] for r in storage_rows)
    print(f"Total ground-truth variables classified: {total}")
    for cat in CATEGORY_ORDER:
        n = c.get(cat, 0)
        print(f"  {n:>4}  ({n/total:.1%})  {cat}")
    for cat, n in c.items():
        if cat not in CATEGORY_ORDER:
            print(f"  {n:>4}  ({n/total:.1%})  {cat}  [unexpected -- check categorize()]")

    print()
    usage_counter = Counter()
    for r in usage_rows:
        for shape in r['usage_shapes'].split('; '):
            usage_counter[shape] += 1
    print(f"Total compiled branches tagged: {len(usage_rows)}")
    for shape, n in usage_counter.most_common():
        print(f"  {n:>4}  ({n/len(usage_rows):.1%})  {shape}")


if __name__ == '__main__':
    main()
