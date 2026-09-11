#!/usr/bin/env python3
"""
Generic schema extractor: normalizes all four case studies' schema sources
(Oracle DDL, MySQL DDL, Liquibase XML, OFBiz entity-model XML) into one
unified column-level table:

    case_study, table, column, sql_type, abstract_type, nullable, is_pk,
    fk_target_table, fk_target_column, source

abstract_type is one of: number, string, date, boolean, unknown -- the same
coarse vocabulary already used by taxonomy/build_taxonomy.py's
condition_composition(), so downstream scoring can do a type-compatibility
check against a DMN variable's typeRef directly.

This reuses the existing paper_supplementary/scripts parsers' table-finding
logic where practical (imported, not re-implemented) and adds the
column-level detail those parsers deliberately didn't need for their
original purpose (aggregate constraint counts only).

Usage:
    python3 schema_extract.py --out schema_columns.csv
(paths to the four schema sources are hard-coded below, relative to
paper_supplementary/schemas/ -- see PAPER_SUPP_DIR)
"""
import re
import csv
import sys
import os
import glob
import argparse
from xml.etree import ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
SCRATCHPAD = os.path.dirname(HERE)
PAPER_SUPP_DIR = os.path.join(SCRATCHPAD, 'paper_supplementary')

sys.path.insert(0, os.path.join(PAPER_SUPP_DIR, 'scripts'))
import parse_oracle_mysql_ddl as ddl_parser  # noqa: E402


# ---------------------------------------------------------------------------
# Abstract type normalization (shared vocabulary across all four sources)
# ---------------------------------------------------------------------------

def abstract_sql_type(raw_type, type_args=''):
    t = (raw_type or '').upper()
    args = (type_args or '').strip()
    if t in ('DATE', 'TIMESTAMP', 'DATETIME', 'TIME'):
        return 'date'
    if t in ('BOOLEAN', 'BOOL'):
        return 'boolean'
    if t in ('BIT',) and args.strip() == '1':
        return 'boolean'
    if t in ('TINYINT',) and args.strip() == '1':
        return 'boolean'  # common MySQL boolean convention
    if t in ('NUMBER', 'DECIMAL', 'NUMERIC', 'INT', 'INTEGER', 'SMALLINT',
              'BIGINT', 'FLOAT', 'DOUBLE', 'REAL', 'TINYINT', 'MEDIUMINT',
              'DEC'):
        return 'number'
    if t in ('VARCHAR', 'VARCHAR2', 'CHAR', 'NCHAR', 'NVARCHAR2', 'TEXT',
              'CLOB', 'LONGTEXT', 'MEDIUMTEXT', 'TINYTEXT', 'ENUM', 'SET',
              'STRING'):
        return 'string'
    return 'unknown'


def abstract_ofbiz_type(field_type):
    t = (field_type or '').lower()
    if 'date' in t or 'time' in t:
        return 'date'
    if 'indicator' in t:
        return 'boolean'
    if any(k in t for k in ('amount', 'numeric', 'fixed-point',
                              'floating-point', 'integer', 'currency')) \
            and 'id' not in t:
        return 'number'
    # OFBiz id-* fields are alphanumeric generated keys/codes stored as
    # strings, and status/type fields are string constants -- treat all
    # remaining text-ish/id-ish field types as string.
    return 'string'


# ---------------------------------------------------------------------------
# FLEX2 / PrestaShop: Oracle & MySQL DDL (regex, reusing ddl_parser's
# paren-balanced table-block finder)
# ---------------------------------------------------------------------------

def split_top_level(inner):
    """Split the content between a CREATE TABLE(...) 's outer parens into
    top-level comma-separated fragments, respecting nested parens/strings."""
    frags = []
    depth = 0
    buf = []
    in_str = False
    str_ch = ''
    i = 0
    while i < len(inner):
        ch = inner[i]
        if in_str:
            buf.append(ch)
            if ch == '\\' and str_ch == "'":
                i += 1
                if i < len(inner):
                    buf.append(inner[i])
                i += 1
                continue
            if ch == str_ch:
                in_str = False
            i += 1
            continue
        if ch in ("'", '"'):
            in_str = True
            str_ch = ch
            buf.append(ch)
        elif ch == '(':
            depth += 1
            buf.append(ch)
        elif ch == ')':
            depth -= 1
            buf.append(ch)
        elif ch == ',' and depth == 0:
            frags.append(''.join(buf))
            buf = []
        else:
            buf.append(ch)
        i += 1
    if buf:
        frags.append(''.join(buf))
    return frags


COL_DEF_RE = re.compile(
    r'^\s*["`]?(?P<col>[A-Za-z][A-Za-z0-9_]*)["`]?\s+'
    r'(?P<type>[A-Za-z][A-Za-z0-9_]*)'
    r'(?:\s*\(\s*(?P<args>[^)]*)\s*\))?', re.I)

SKIP_FRAG_RE = re.compile(
    r'^\s*(CONSTRAINT|PRIMARY\s+KEY|FOREIGN\s+KEY|UNIQUE|CHECK|KEY|INDEX)\b', re.I)


def extract_ddl_columns(sql_file, case_study, schema_prefix=None):
    with open(sql_file, encoding='utf-8', errors='ignore') as f:
        sql = f.read()
    sql_clean = ddl_parser.strip_comments(sql)
    blocks = ddl_parser.find_table_blocks(sql_clean, schema_prefix)
    tables = ddl_parser.parse(sql_clean, schema_prefix)  # for FK / PK detail

    rows = []
    for table_name, body in blocks:
        # PrestaShop's install DDL uses a literal "PREFIX_" placeholder for
        # the table prefix the installer substitutes at deploy time (e.g.
        # ps_cart_rule) -- strip it so table names match the logical names
        # used everywhere else (DMN mapping notes, taxonomy, code).
        if table_name.startswith('PREFIX_'):
            table_name = table_name[len('PREFIX_'):]
        inner = body.strip()
        if inner.startswith('('):
            inner = inner[1:-1] if inner.endswith(')') else inner[1:]
        frags = split_top_level(inner)
        pk_cols = set()
        t = tables.get(table_name)
        if t and t.get('pk_columns'):
            pk_cols = {c.strip().strip('"').strip('`').upper()
                       for c in t['pk_columns'].split(',') if c.strip()}
        fk_by_col = {}
        if t:
            for cname, cols, reftable, refcols in t.get('fk', []):
                for c in (cols or '').split(','):
                    c = c.strip().strip('"').strip('`').upper()
                    if c:
                        fk_by_col[c] = (reftable, (refcols or '').split(',')[0].strip().strip('"').strip('`'))

        for frag in frags:
            frag_stripped = frag.strip()
            if not frag_stripped or SKIP_FRAG_RE.match(frag_stripped):
                continue
            m = COL_DEF_RE.match(frag_stripped)
            if not m:
                continue
            col = m.group('col')
            raw_type = m.group('type')
            args = m.group('args') or ''
            nullable = 'NOT NULL' not in frag_stripped.upper()
            is_pk = col.upper() in pk_cols
            if is_pk:
                nullable = False
            fk_target = fk_by_col.get(col.upper())
            rows.append({
                'case_study': case_study,
                'table': table_name,
                'column': col,
                'sql_type': raw_type.upper() + (f'({args})' if args else ''),
                'abstract_type': abstract_sql_type(raw_type, args),
                'nullable': nullable,
                'is_pk': is_pk,
                'fk_target_table': fk_target[0] if fk_target else '',
                'fk_target_column': fk_target[1] if fk_target else '',
                'source': os.path.basename(sql_file),
            })
    return rows


# ---------------------------------------------------------------------------
# OpenMRS: Liquibase XML changelog stream (replay createTable/addColumn/
# addForeignKeyConstraint in file order, same approach as
# parse_liquibase_snapshot.py but retaining column type/nullable detail)
# ---------------------------------------------------------------------------

NS = '{http://www.liquibase.org/xml/ns/dbchangelog}'


def _local(tag):
    return tag.replace(NS, '')


def extract_liquibase_columns(xml_files, case_study):
    tables = {}  # tname -> {col: {type, nullable, is_pk, unique}}
    fks = {}  # tname -> {col: (reftable, refcol)}

    for fpath in xml_files:
        tree = ET.parse(fpath)
        root = tree.getroot()
        for cs in root:
            if _local(cs.tag) != 'changeSet':
                continue
            for change in cs:
                tag = _local(change.tag)
                if tag == 'createTable':
                    tname = (change.get('tableName') or '').lower()
                    cols = {}
                    for col in change.findall(f'{NS}column'):
                        cname = col.get('name')
                        ctype = col.get('type', '')
                        constraints = col.find(f'{NS}constraints')
                        is_pk = False
                        nullable = True
                        if constraints is not None:
                            is_pk = constraints.get('primaryKey') == 'true'
                            if constraints.get('nullable') == 'false' or is_pk:
                                nullable = False
                        cols[cname] = {'type': ctype, 'nullable': nullable, 'is_pk': is_pk}
                    tables[tname] = cols
                    fks.setdefault(tname, {})
                elif tag == 'addColumn':
                    tname = (change.get('tableName') or '').lower()
                    tables.setdefault(tname, {})
                    for col in change.findall(f'{NS}column'):
                        cname = col.get('name')
                        ctype = col.get('type', '')
                        constraints = col.find(f'{NS}constraints')
                        nullable = True
                        if constraints is not None and constraints.get('nullable') == 'false':
                            nullable = False
                        tables[tname][cname] = {'type': ctype, 'nullable': nullable, 'is_pk': False}
                elif tag == 'dropTable':
                    tables.pop((change.get('tableName') or '').lower(), None)
                elif tag == 'addForeignKeyConstraint':
                    tname = (change.get('baseTableName') or '').lower()
                    basecols = (change.get('baseColumnNames') or '').split(',')
                    reftable = change.get('referencedTableName', '')
                    refcols = (change.get('referencedColumnNames') or '').split(',')
                    fks.setdefault(tname, {})
                    for bc, rc in zip(basecols, refcols):
                        fks[tname][bc.strip()] = (reftable, rc.strip())

    rows = []
    for tname, cols in tables.items():
        for cname, meta in cols.items():
            fk_target = fks.get(tname, {}).get(cname)
            rtype = meta['type']
            base_type = re.match(r'[A-Za-z_]+', rtype or '')
            base_type = base_type.group(0) if base_type else ''
            args_m = re.search(r'\(([^)]*)\)', rtype or '')
            rows.append({
                'case_study': case_study,
                'table': tname,
                'column': cname,
                'sql_type': rtype,
                'abstract_type': abstract_sql_type(base_type, args_m.group(1) if args_m else ''),
                'nullable': meta['nullable'],
                'is_pk': meta['is_pk'],
                'fk_target_table': fk_target[0] if fk_target else '',
                'fk_target_column': fk_target[1] if fk_target else '',
                'source': os.path.basename(xml_files[-1]),
            })
    return rows


# ---------------------------------------------------------------------------
# OFBiz: declarative entity model XML (<entity><field name= type= .../></>)
# ---------------------------------------------------------------------------

def extract_ofbiz_columns(entitydef_dir, case_study):
    files = glob.glob(os.path.join(entitydef_dir, '**', '*.xml'), recursive=True)
    rows = []
    for fp in files:
        try:
            tree = ET.parse(fp)
        except ET.ParseError:
            continue
        root = tree.getroot()
        for e in root.findall('entity'):
            ename = e.get('entity-name')
            pk_fields = {f.get('field') for f in e.findall('prim-key')}
            fk_by_field = {}
            for rel in e.findall('relation'):
                if rel.get('type') != 'one':
                    continue
                rel_entity = rel.get('rel-entity-name', '')
                for km in rel.findall('key-map'):
                    fk_by_field[km.get('field-name')] = (rel_entity, km.get('rel-field-name', ''))
            for field in e.findall('field'):
                fname = field.get('name')
                ftype = field.get('type', '')
                is_pk = fname in pk_fields
                fk_target = fk_by_field.get(fname)
                rows.append({
                    'case_study': case_study,
                    'table': ename,
                    'column': fname,
                    'sql_type': ftype,
                    'abstract_type': abstract_ofbiz_type(ftype),
                    'nullable': not is_pk,  # OFBiz doesn't declare not-null on most fields
                    'is_pk': is_pk,
                    'fk_target_table': fk_target[0] if fk_target else '',
                    'fk_target_column': fk_target[1] if fk_target else '',
                    'source': os.path.relpath(fp, entitydef_dir),
                })
    return rows


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def build_all():
    rows = []
    rows += extract_ddl_columns(
        os.path.join(PAPER_SUPP_DIR, 'schemas/flex2/Flex1.sql'), 'FLEX2', schema_prefix='FLEX2')
    rows += extract_ddl_columns(
        os.path.join(PAPER_SUPP_DIR, 'schemas/prestashop/db_structure.sql'), 'PrestaShop')
    rows += extract_liquibase_columns(
        [os.path.join(PAPER_SUPP_DIR, 'schemas/openmrs/liquibase-schema-only-2.9.x.xml'),
         os.path.join(PAPER_SUPP_DIR, 'schemas/openmrs/liquibase-update-to-latest-3.0.x.xml')],
        'OpenMRS')
    rows += extract_ofbiz_columns(
        os.path.join(PAPER_SUPP_DIR, 'schemas/ofbiz/entitydef'), 'OFBiz')
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
