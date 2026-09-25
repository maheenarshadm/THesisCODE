#!/usr/bin/env python3
"""
parse_jbilling_ddl.py

Parses jBilling's PostgreSQL DDL export (jbilling_test.sql) into the same JSON
shape used for Spree/FLEX2. Note: despite the filename and this project's earlier
documentation describing jBilling's schema as a "MySQL/HSQLDB DDL export," the
actual uploaded file (2026-09-11) is a PostgreSQL dump ("-- PostgreSQL database
dump"). This parser targets what the file actually is.

PostgreSQL DDL structure this parser targets:
  CREATE TABLE table_name (
      col1 integer NOT NULL,
      col2 character varying(40),
      ...
  );
  ...
  ALTER TABLE ONLY table_name
      ADD CONSTRAINT table_name_pkey PRIMARY KEY (col1);
  ALTER TABLE ONLY child_table
      ADD CONSTRAINT child_table_fk_1 FOREIGN KEY (col) REFERENCES parent_table(col);

Run: python3 parse_jbilling_ddl.py /path/to/jbilling_test.sql
Writes: jbilling_schema_full.json

KNOWN LIMITATIONS:
  - UNIQUE constraints: confirmed by direct grep before writing this parser that
    the file declares zero (matches this project's own documented 0 UNIQUE for
    jBilling) -- the UNIQUE-constraint regex is included for completeness/future
    reproducibility but is not expected to match anything in this file.
  - CHECK constraints: same treatment; confirmed 0 in this file.
  - DEFAULT values, sequences, and non-constraint DDL (SET statements, OWNER TO,
    COMMENT ON) are ignored entirely.

FIXED 2026-09-11 (while extending generator/fitness.py's FK constraint
distance term to jBilling, matching the same fix already applied to
FLEX2's own parser): FK detail was being discarded down to just the
target table name (`_fkcols`/`_refcols` captured by FK_RE and thrown
away) -- insufficient for a real per-column FK distance, which needs to
know *which* column to check, not just which tables are related. Now
preserved as `fk_columns` (local column -> ref table.column), one entry
per local/ref column pair for composite FKs.
"""
import argparse
import json
import re


CREATE_TABLE_RE = re.compile(
    r'CREATE TABLE\s+(?:public\.)?(\w+)\s*\(\s*(.*?)\n\);',
    re.S | re.I,
)
COLUMN_LINE_RE = re.compile(
    r'^\s*(\w+)\s+([\w\s.]+?)(?:\s+DEFAULT\s+.+?)?(\s+NOT NULL)?,?\s*$',
    re.I,
)
PK_RE = re.compile(
    r'ALTER TABLE ONLY\s+(?:public\.)?(\w+)\s*\n?\s*ADD CONSTRAINT\s+\w+\s+PRIMARY KEY\s*\(([^)]+)\)',
    re.I,
)
UNIQUE_RE = re.compile(
    r'ALTER TABLE ONLY\s+(?:public\.)?(\w+)\s*\n?\s*ADD CONSTRAINT\s+\w+\s+UNIQUE\s*\(([^)]+)\)',
    re.I,
)
FK_RE = re.compile(
    r'ALTER TABLE ONLY\s+(?:public\.)?(\w+)\s*\n?\s*ADD CONSTRAINT\s+\w+\s+FOREIGN KEY\s*\(([^)]+)\)\s*'
    r'REFERENCES\s+(?:public\.)?(\w+)\s*\(([^)]+)\)',
    re.I,
)
CHECK_RE = re.compile(
    r'ALTER TABLE ONLY\s+(?:public\.)?(\w+)\s*\n?\s*ADD CONSTRAINT\s+\w+\s+CHECK\s*\(([^)]+)\)',
    re.I,
)


def plain_cols(s):
    return [c.strip() for c in s.split(',')]


def parse(text):
    tables = {}

    for m in CREATE_TABLE_RE.finditer(text):
        tname, body = m.group(1), m.group(2)
        cols = {}
        for raw_line in body.split('\n'):
            line = raw_line.strip().rstrip(',')
            if not line:
                continue
            cm = COLUMN_LINE_RE.match(raw_line)
            if not cm:
                continue
            col, ctype, notnull = cm.group(1), cm.group(2).strip(), cm.group(3)
            cols[col] = {
                'type': ctype.split('(')[0].strip().lower(),
                'null_false': bool(notnull),
            }
        tables[tname] = {
            'pk': None, 'columns': cols, 'fks': set(), 'fk_columns': [], 'indexes': [], 'checks': [],
        }

    for m in PK_RE.finditer(text):
        tname, cols = m.group(1), plain_cols(m.group(2))
        if tname in tables:
            tables[tname]['pk'] = cols[0] if len(cols) == 1 else cols

    for m in UNIQUE_RE.finditer(text):
        tname, cols = m.group(1), plain_cols(m.group(2))
        if tname in tables:
            tables[tname]['indexes'].append({'unique': True, 'cols': cols})

    for m in FK_RE.finditer(text):
        tname, fkcols, ref_table, refcols = m.group(1), plain_cols(m.group(2)), m.group(3), plain_cols(m.group(4))
        if tname in tables:
            tables[tname]['fks'].add(ref_table)
            for local_col, ref_col in zip(fkcols, refcols):
                tables[tname]['fk_columns'].append(
                    {'column': local_col, 'ref_table': ref_table, 'ref_column': ref_col})

    for m in CHECK_RE.finditer(text):
        tname, body = m.group(1), m.group(2)
        if tname in tables:
            tables[tname]['checks'].append(body.strip())

    return tables


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('ddl_path')
    ap.add_argument('--out', default='jbilling_schema_full.json')
    args = ap.parse_args()

    with open(args.ddl_path, encoding='utf-8', errors='replace') as f:
        text = f.read()

    tables = parse(text)

    export = {
        name: {
            'pk': t['pk'],
            'columns': t['columns'],
            'fks': sorted(t['fks']),
            'fk_columns': t['fk_columns'],
            'indexes': t['indexes'],
            'checks': t['checks'],
        }
        for name, t in tables.items()
    }

    with open(args.out, 'w') as f:
        json.dump(export, f, indent=2)

    n_tables = len(export)
    n_pk = sum(1 for t in export.values() if t['pk'])
    n_fk_raw = len(FK_RE.findall(text))
    n_fk_relationships = sum(len(t['fks']) for t in export.values())
    n_fk_columns = sum(len(t['fk_columns']) for t in export.values())
    n_unique = sum(1 for t in export.values() for idx in t['indexes'] if idx['unique'])
    n_checks = sum(len(t['checks']) for t in export.values())
    print(f"Tables: {n_tables}")
    print(f"Tables with PK: {n_pk}")
    print(f"Raw FK constraint declarations: {n_fk_raw}")
    print(f"Distinct table-to-table FK relationships (deduplicated): {n_fk_relationships}")
    print(f"Per-column FK entries (local column -> ref table.column, 'fk_columns'): {n_fk_columns}")
    print(f"Total UNIQUE constraints: {n_unique}")
    print(f"Total CHECK constraints: {n_checks}")
    print(f"Wrote {args.out}")


if __name__ == '__main__':
    main()
