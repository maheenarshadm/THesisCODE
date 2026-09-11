#!/usr/bin/env python3
"""
Generic schema extractor: normalizes the current four case studies' schema
sources into one unified column-level table:

    case_study, table, column, sql_type, abstract_type, nullable, is_pk,
    fk_target_table, fk_target_column, source

abstract_type is one of: number, string, date, boolean, unknown -- the same
coarse vocabulary the mapper's type-compatibility check (mapper.py) uses
against a DMN variable's typeRef.

Fixed 2026-09-11: this script previously imported
`parse_oracle_mysql_ddl` from a `paper_supplementary/scripts` directory
that does not exist anywhere in this repository (ModuleNotFoundError on
import), and its hard-coded case-study list (FLEX2, OpenMRS, OFBiz,
PrestaShop) was the *original* pre-swap program -- neither Spree nor
jBilling, the two case studies that actually replaced OFBiz and
PrestaShop, ever appeared in its output. It now reads the already-working,
already-validated per-case-study JSON that `all_schema_extraction/`
produces for the *current* four case studies (FLEX2, OpenMRS, Spree,
jBilling) instead of re-parsing raw DDL/XML/migrations itself.

One documented fidelity trade-off from this rewrite: `all_schema_extraction`
records `fks` as a deduplicated set of *target tables* per table (see its
own README), not a per-column FK resolution the way the original
DDL-parsing version of this script did. `fk_target_column` is therefore
always left blank now, and `fk_target_table` holds every FK target table
for that column's table (semicolon-joined), not necessarily the one this
specific column points to. This is a real, deliberate narrowing -- stated
here rather than silently absorbed -- but not a loss of function for
mapper.py's actual scoring: grep confirms `fk_target_table`/
`fk_target_column` are declared in this CSV's header but never read by
mapper.py's `score_candidate()`, only carried through as documentation.

OFBiz and PrestaShop are out of scope here, matching the current program
(design doc §13.1, §7e) -- both are backup case studies now, and neither
has a schema JSON in `all_schema_extraction/` to read from. Re-adding them
would mean writing new parsers, not just repointing this script.

Usage:
    python3 schema_extract.py --out schema_columns.csv
"""
import re
import csv
import os
import json
import argparse

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(HERE))
SCHEMA_JSON_DIR = os.path.join(
    REPO_ROOT, 'all_schema_extraction', 'all_schema_extraction', 'output')

CASE_STUDY_JSON = {
    'FLEX2': 'flex2_schema_full.json',
    'OpenMRS': 'openmrs_schema_full.json',
    'Spree': 'spree_schema_full.json',
    'jBilling': 'jbilling_schema_full.json',
}


# ---------------------------------------------------------------------------
# Abstract type normalization (shared vocabulary across all four sources:
# Oracle DDL types (FLEX2), MySQL/Liquibase types (OpenMRS), PostgreSQL DDL
# types (jBilling), and Rails/ActiveRecord migration types (Spree))
# ---------------------------------------------------------------------------

_TYPE_RE = re.compile(r'^([A-Za-z_ ]+)(?:\(([^)]*)\))?')


def abstract_sql_type(raw_type):
    raw = (raw_type or '').strip()
    m = _TYPE_RE.match(raw)
    base = (m.group(1).strip().upper() if m else raw.upper())
    args = (m.group(2) or '').strip() if m else ''

    if base in ('BIT', 'TINYINT') and args == '1':
        return 'boolean'  # common MySQL boolean convention
    if base.startswith('TIMESTAMP') or base in ('DATE', 'DATETIME', 'TIME'):
        return 'date'
    if base in ('BOOLEAN', 'BOOL'):
        return 'boolean'
    if base in ('NUMBER', 'DECIMAL', 'NUMERIC', 'INT', 'INTEGER', 'SMALLINT',
                'BIGINT', 'FLOAT', 'DOUBLE', 'REAL', 'TINYINT', 'MEDIUMINT',
                'DEC'):
        return 'number'
    if base in ('VARCHAR', 'VARCHAR2', 'CHAR', 'NCHAR', 'NVARCHAR2', 'TEXT',
                'CLOB', 'LONGTEXT', 'MEDIUMTEXT', 'TINYTEXT', 'ENUM', 'SET',
                'STRING', 'JSON'):
        return 'string'
    return 'unknown'


# ---------------------------------------------------------------------------
# Driver -- reads all_schema_extraction's uniform per-table JSON shape:
#   {"TABLE_NAME": {"pk": str|list|null, "columns": {"COL": {"type", "null_false"}},
#                    "fks": [...], "indexes": [...], "checks": [...]}}
# ---------------------------------------------------------------------------

def extract_case_study(case_study, json_path):
    with open(json_path, encoding='utf-8') as f:
        data = json.load(f)

    rows = []
    for table_name, info in data.items():
        pk = info.get('pk')
        if isinstance(pk, str):
            pk_cols = {pk}
        elif isinstance(pk, list):
            pk_cols = set(pk)
        else:
            pk_cols = set()
        fk_targets = ';'.join(sorted(set(info.get('fks') or [])))

        for col_name, meta in (info.get('columns') or {}).items():
            rows.append({
                'case_study': case_study,
                'table': table_name,
                'column': col_name,
                'sql_type': meta.get('type', ''),
                'abstract_type': abstract_sql_type(meta.get('type', '')),
                'nullable': not meta.get('null_false', False),
                'is_pk': col_name in pk_cols,
                'fk_target_table': fk_targets,
                'fk_target_column': '',
                'source': os.path.basename(json_path),
            })
    return rows


def build_all():
    rows = []
    for cs, fname in CASE_STUDY_JSON.items():
        rows += extract_case_study(cs, os.path.join(SCHEMA_JSON_DIR, fname))
    return rows


def write_csv(rows, path):
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['case_study', 'table', 'column', 'sql_type', 'abstract_type',
                     'nullable', 'is_pk', 'fk_target_table', 'fk_target_column', 'source'])
        for r in rows:
            w.writerow([r['case_study'], r['table'], r['column'], r['sql_type'],
                        r['abstract_type'], r['nullable'], r['is_pk'],
                        r['fk_target_table'], r['fk_target_column'], r['source']])


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='schema_columns.csv')
    args = ap.parse_args()
    rows = build_all()
    write_csv(rows, args.out)
    from collections import Counter
    by_cs = Counter(r['case_study'] for r in rows)
    print(f"Total columns extracted: {len(rows)}")
    for cs, n in by_cs.items():
        print(f"  {cs}: {n} columns")
    print(f"Written to {args.out}")
