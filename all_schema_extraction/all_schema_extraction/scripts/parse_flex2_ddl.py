#!/usr/bin/env python3
"""
parse_flex2_ddl.py

Parses FLEX2's Oracle DDL export (Flex1.sql) into the same JSON shape used for
Spree Commerce (parse_spree_migrations.py's output): one dict per table, with
columns (name -> {type, null_false}), fks (list of target tables), indexes
(unique flag + columns), checks, and pk (column name or list, or None).

Oracle DDL structure this parser targets (confirmed against the actual file,
2026-09-11):
  CREATE TABLE "FLEX2"."TABLE_NAME"
     (  "COL1" NUMBER(8,0),
        "COL2" VARCHAR2(50),
        ...
     ) ;
  ...
  ALTER TABLE "FLEX2"."TABLE_NAME" ADD CONSTRAINT "PK_..." PRIMARY KEY ("COL1") ENABLE;
  ALTER TABLE "FLEX2"."TABLE_NAME" ADD CONSTRAINT "UK_..." UNIQUE ("COL2") ENABLE;
  ALTER TABLE "FLEX2"."CHILD" ADD CONSTRAINT "FK_..." FOREIGN KEY ("COL")
      REFERENCES "FLEX2"."PARENT" ("COL") ENABLE;

Run: python3 parse_flex2_ddl.py /path/to/Flex1.sql
Writes: flex2_schema_full.json (next to this script, or --out to override)

KNOWN LIMITATIONS:
  - NOT NULL is inferred only from inline "NOT NULL" tokens on the column
    definition line; Oracle exports occasionally express constraints via a
    separate ALTER TABLE ... MODIFY, which this parser does not track.
  - CHECK constraints (if any) are captured by a dedicated regex but FLEX2's
    export is known to declare zero (confirmed by direct grep before writing
    this parser -- see case-study-selection.md).
  - Multi-column PK/UNIQUE/FK constraints are captured as a list of columns,
    not decomposed further.
"""
import argparse
import json
import re


CREATE_TABLE_RE = re.compile(
    r'CREATE TABLE\s+"FLEX2"\."(\w+)"\s*\(\s*(.*?)\)\s*;',
    re.S | re.I,
)
CREATE_GTT_RE = re.compile(
    r'CREATE GLOBAL TEMPORARY TABLE\s+"FLEX2"\."(\w+)"\s*\(\s*(.*?)\)\s*(?:ON COMMIT|;)',
    re.S | re.I,
)
ORACLE_TEXT_HOUSEKEEPING_PREFIX = 'DR$'
COLUMN_LINE_RE = re.compile(
    r'"(\w+)"\s+([A-Z0-9_]+(?:\([^)]*\))?)\s*((?:DEFAULT\s+\S+\s*)?(?:NOT NULL)?)',
    re.I,
)
PK_RE = re.compile(
    r'ALTER TABLE\s+"FLEX2"\."(\w+)"\s+ADD(?:\s+CONSTRAINT\s+"\w+")?\s+PRIMARY KEY\s*\(([^)]+)\)',
    re.I,
)
UNIQUE_RE = re.compile(
    r'ALTER TABLE\s+"FLEX2"\."(\w+)"\s+ADD(?:\s+CONSTRAINT\s+"\w+")?\s+UNIQUE\s*\(([^)]+)\)',
    re.I,
)
FK_RE = re.compile(
    r'ALTER TABLE\s+"FLEX2"\."(\w+)"\s+ADD CONSTRAINT\s+"\w+"\s+FOREIGN KEY\s*\(([^)]+)\)\s*'
    r'REFERENCES\s+"FLEX2"\."(\w+)"\s*\(([^)]+)\)',
    re.I | re.S,
)
CHECK_RE = re.compile(
    r'ALTER TABLE\s+"FLEX2"\."(\w+)"\s+ADD CONSTRAINT\s+"\w+"\s+CHECK\s*\(([^)]+)\)',
    re.I,
)


def quoted_cols(s):
    return [c.strip().strip('"') for c in s.split(',')]


def parse_columns(body):
    """Split an Oracle column-definition body on top-level commas (not commas
    nested inside a type's precision/scale parens, e.g. NUMBER(8,0)) and parse
    each into (name, type, null_false)."""
    depth = 0
    parts = []
    buf = []
    for ch in body:
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        if ch == ',' and depth == 0:
            parts.append(''.join(buf))
            buf = []
        else:
            buf.append(ch)
    if buf:
        parts.append(''.join(buf))

    cols = {}
    for part in parts:
        # skip inline PRIMARY KEY(...) clauses inside index-organized tables --
        # these are handled by the standalone PK_RE pass instead, and are not
        # column definitions
        if re.match(r'\s*PRIMARY KEY', part, re.I):
            continue
        cm = COLUMN_LINE_RE.search(part)
        if not cm:
            continue
        col, ctype, rest = cm.group(1), cm.group(2), cm.group(3) or ''
        cols[col] = {
            'type': ctype.split('(')[0].upper(),
            'null_false': 'NOT NULL' in rest.upper(),
        }
    return cols


def parse(text):
    tables = {}

    for regex in (CREATE_TABLE_RE, CREATE_GTT_RE):
        for m in regex.finditer(text):
            tname, body = m.group(1), m.group(2)
            if tname.startswith(ORACLE_TEXT_HOUSEKEEPING_PREFIX):
                continue  # Oracle-Text housekeeping table, excluded per this
                          # project's established methodology (case-study-selection.md)
            tables[tname] = {
                'pk': None, 'columns': parse_columns(body), 'fks': set(),
                'indexes': [], 'checks': [],
            }

    for m in PK_RE.finditer(text):
        tname, cols = m.group(1), quoted_cols(m.group(2))
        if tname in tables:
            tables[tname]['pk'] = cols[0] if len(cols) == 1 else cols

    for m in UNIQUE_RE.finditer(text):
        tname, cols = m.group(1), quoted_cols(m.group(2))
        if tname in tables:
            tables[tname]['indexes'].append({'unique': True, 'cols': cols})

    for m in FK_RE.finditer(text):
        tname, _fkcols, ref_table, _refcols = m.group(1), m.group(2), m.group(3), m.group(4)
        if tname in tables:
            tables[tname]['fks'].add(ref_table)

    for m in CHECK_RE.finditer(text):
        tname, body = m.group(1), m.group(2)
        if tname in tables:
            tables[tname]['checks'].append(body.strip())

    return tables


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('ddl_path')
    ap.add_argument('--out', default='flex2_schema_full.json')
    args = ap.parse_args()

    with open(args.ddl_path, encoding='utf-8', errors='replace') as f:
        text = f.read()

    tables = parse(text)

    export = {
        name: {
            'pk': t['pk'],
            'columns': t['columns'],
            'fks': sorted(t['fks']),
            'indexes': t['indexes'],
            'checks': t['checks'],
        }
        for name, t in tables.items()
    }

    with open(args.out, 'w') as f:
        json.dump(export, f, indent=2)

    n_tables = len(export)
    n_pk = sum(1 for t in export.values() if t['pk'])
    n_fk_relationships = sum(len(t['fks']) for t in export.values())
    n_fk_raw = len(FK_RE.findall(text))
    n_unique = sum(1 for t in export.values() for idx in t['indexes'] if idx['unique'])
    n_checks = sum(len(t['checks']) for t in export.values())
    print(f"Tables: {n_tables}")
    print(f"Tables with PK: {n_pk}")
    print(f"Raw FK constraint declarations (ALTER TABLE ... ADD CONSTRAINT FOREIGN KEY statements): {n_fk_raw}")
    print(f"Distinct table-to-table FK relationships (deduplicated -- what's stored in the JSON's 'fks' list): {n_fk_relationships}")
    print(f"  (the two differ when a table has multiple FK columns pointing at the same parent table)")
    print(f"Total UNIQUE constraints: {n_unique}")
    print(f"Total CHECK constraints: {n_checks}")
    print(f"Wrote {args.out}")


if __name__ == '__main__':
    main()
