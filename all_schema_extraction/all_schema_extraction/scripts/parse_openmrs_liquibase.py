#!/usr/bin/env python3
"""
parse_openmrs_liquibase.py

Parses OpenMRS's Liquibase changelog XML files into the same JSON shape used for
Spree/FLEX2/jBilling. Handles the two files this project has used for OpenMRS's
table/constraint counts: the main schema-only changelog (hundreds of createTable
changeSets plus addForeignKeyConstraint/addUniqueConstraint changeSets) and the
small incremental "update-to-latest" changelog (addColumn changeSets).

Liquibase elements this parser handles:
  <createTable tableName="...">
    <column name="..." type="..."> <constraints nullable="false" primaryKey="true"/> </column>
  </createTable>
  <addForeignKeyConstraint baseTableName="..." baseColumnNames="..."
                            referencedTableName="..." referencedColumnNames="..."/>
  <addUniqueConstraint tableName="..." columnNames="..." constraintName="..."/>
  <addColumn tableName="...">
    <column name="..." type="..."/>
  </addColumn>
  <addPrimaryKey tableName="..." columnNames="..."/>
  <dropTable tableName="..."/>

Run: python3 parse_openmrs_liquibase.py schema.xml [update.xml ...]
Writes: openmrs_schema_full.json

KNOWN LIMITATIONS:
  - CHECK constraints: Liquibase's <sql> escape-hatch changeSets (raw SQL, used
    for things this parser can't and shouldn't try to interpret generically,
    e.g. the update file's CREATE EXTENSION statements) are not parsed for
    embedded CHECK constraints; if OpenMRS declares any CHECK constraints via
    raw <sql> rather than a dedicated Liquibase element, they will not be
    captured. (This project's own documented OpenMRS CHECK count is 0.)
  - Multiple changelog files are processed in the order given on the command
    line; if a later file alters a table defined in an earlier one (addColumn,
    dropColumn, etc.), file order matters and should match real deployment order.
"""
import argparse
import json
import xml.etree.ElementTree as ET


NS = {'lb': 'http://www.liquibase.org/xml/ns/dbchangelog'}
RAW_FK_COUNT = [0]  # mutable counter, since multiple FK constraints can target
                     # the same (table, ref_table) pair and get deduplicated in
                     # the per-table 'fks' set -- mirrors the same raw-vs-
                     # deduplicated distinction found in FLEX2's/jBilling's DDL


def local(tag):
    """Strip the namespace off an ElementTree tag, e.g. '{ns}createTable' -> 'createTable'."""
    return tag.split('}')[-1] if '}' in tag else tag


def ensure_table(tables, name):
    if name not in tables:
        tables[name] = {'pk': None, 'columns': {}, 'fks': set(), 'indexes': [], 'checks': []}
    return tables[name]


def parse_column_el(col_el):
    name = col_el.get('name')
    ctype = (col_el.get('type') or 'VARCHAR').split('(')[0].upper()
    null_false = False
    is_pk = False
    is_unique = False
    for child in col_el:
        if local(child.tag) == 'constraints':
            null_false = child.get('nullable') == 'false'
            is_pk = child.get('primaryKey') == 'true'
            is_unique = child.get('unique') == 'true'
    return name, {'type': ctype, 'null_false': null_false}, is_pk, is_unique


def parse_file(path, tables):
    tree = ET.parse(path)
    root = tree.getroot()

    for changeset in root:
        if local(changeset.tag) != 'changeSet':
            continue
        for el in changeset:
            tag = local(el.tag)

            if tag == 'createTable':
                tname = el.get('tableName')
                t = ensure_table(tables, tname)
                pk_cols = []
                for col_el in el:
                    if local(col_el.tag) != 'column':
                        continue
                    name, meta, is_pk, is_unique = parse_column_el(col_el)
                    t['columns'][name] = meta
                    if is_pk:
                        pk_cols.append(name)
                    if is_unique:
                        t['indexes'].append({'unique': True, 'cols': [name]})
                if pk_cols:
                    t['pk'] = pk_cols[0] if len(pk_cols) == 1 else pk_cols

            elif tag == 'addColumn':
                tname = el.get('tableName')
                t = ensure_table(tables, tname)
                for col_el in el:
                    if local(col_el.tag) != 'column':
                        continue
                    name, meta, is_pk, is_unique = parse_column_el(col_el)
                    t['columns'][name] = meta
                    if is_pk and not t['pk']:
                        t['pk'] = name
                    if is_unique:
                        t['indexes'].append({'unique': True, 'cols': [name]})

            elif tag == 'dropColumn':
                tname = el.get('tableName')
                cname = el.get('columnName')
                if tname in tables and cname:
                    tables[tname]['columns'].pop(cname, None)

            elif tag == 'dropTable':
                tname = el.get('tableName')
                tables.pop(tname, None)

            elif tag == 'renameTable':
                old, new = el.get('oldTableName'), el.get('newTableName')
                if old in tables:
                    tables[new] = tables.pop(old)

            elif tag == 'addForeignKeyConstraint':
                tname = el.get('baseTableName')
                ref = el.get('referencedTableName')
                if tname and ref:
                    ensure_table(tables, tname)['fks'].add(ref)
                    RAW_FK_COUNT[0] += 1

            elif tag == 'addUniqueConstraint':
                tname = el.get('tableName')
                cols = el.get('columnNames', '')
                if tname:
                    ensure_table(tables, tname)['indexes'].append(
                        {'unique': True, 'cols': [c.strip() for c in cols.split(',')]}
                    )

            elif tag == 'addPrimaryKey':
                tname = el.get('tableName')
                cols = el.get('columnNames', '')
                if tname:
                    col_list = [c.strip() for c in cols.split(',')]
                    t = ensure_table(tables, tname)
                    t['pk'] = col_list[0] if len(col_list) == 1 else col_list


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('xml_paths', nargs='+')
    ap.add_argument('--out', default='openmrs_schema_full.json')
    args = ap.parse_args()

    tables = {}
    for path in args.xml_paths:
        parse_file(path, tables)

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
    n_unique = sum(1 for t in export.values() for idx in t['indexes'] if idx['unique'])
    n_checks = sum(len(t['checks']) for t in export.values())
    print(f"Tables: {n_tables}")
    print(f"Tables with PK: {n_pk}")
    print(f"Raw FK constraint declarations (addForeignKeyConstraint elements): {RAW_FK_COUNT[0]}")
    print(f"Distinct table-to-table FK relationships (deduplicated): {n_fk_relationships}")
    print(f"Total UNIQUE constraints (inline column unique=\"true\" + addUniqueConstraint): {n_unique}")
    print(f"Total CHECK constraints: {n_checks}")
    print(f"Wrote {args.out}")


if __name__ == '__main__':
    main()
