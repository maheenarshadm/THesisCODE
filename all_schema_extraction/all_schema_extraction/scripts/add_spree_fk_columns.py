#!/usr/bin/env python3
"""
add_spree_fk_columns.py

Adds per-column FK detail (`fk_columns`) to spree_schema_full.json --
the same fix already applied to FLEX2's, OpenMRS's, and jBilling's own
parsers (2026-09-11, while extending generator/fitness.py's FK
constraint distance term to all four case studies).

Why this is a separate, new script rather than a fix to
parse_spree_migrations.py/generate_schema_rb.py directly: those two
scripts parse Spree's historical migration files
(/home/claude/spree_research/spree/spree/core/db/migrate/*.rb), which
were only ever available in a prior session's own environment and were
never checked into this repository -- only their derived JSON output
was. That source is not re-parseable here at all, so this script instead
parses `add_foreign_key` directly out of `schemas/spree_schema.rb` (the
already-checked-in, already-used-elsewhere-this-session consolidated
schema dump) -- arguably a *better* source than replaying migration
history anyway, since it's the one definitive final state rather than a
reconstruction.

Spree declares exactly 6 add_foreign_key calls, all in the simple
two-argument form (no explicit column:/primary_key: options), which
Rails resolves via its default convention: local column =
singularize(second_arg) + "_id", ref column = "id". Verified directly
against every one of the 6 target tables' own create_table column list
before trusting the convention (all 6 confirmed present, 2026-09-11) --
not assumed.

Run: python3 add_spree_fk_columns.py
Reads: ../../../schemas/spree_schema.rb, output/spree_schema_full.json
Writes: output/spree_schema_full.json (in place, fk_columns field added)
"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMA_RB = os.path.join(HERE, '..', '..', '..', 'schemas', 'spree_schema.rb')
SCHEMA_JSON = os.path.join(HERE, '..', 'output', 'spree_schema_full.json')

ADD_FK_RE = re.compile(r'add_foreign_key\s+"([\w.]+)"\s*,\s*"([\w.]+)"(.*)$', re.M)
COLUMN_OPT_RE = re.compile(r'column:\s*"?(\w+)"?')
PRIMARY_KEY_OPT_RE = re.compile(r'primary_key:\s*"?(\w+)"?')


def singularize(name):
    """Minimal Rails-style singularization -- only what's needed for the
    6 real target table names this schema actually declares (all plain
    "...s" plurals, no irregular forms); not a general inflector."""
    if name.endswith('s'):
        return name[:-1]
    return name


def main():
    with open(SCHEMA_RB, encoding='utf-8') as f:
        schema_rb = f.read()
    with open(SCHEMA_JSON, encoding='utf-8') as f:
        schema = json.load(f)

    added = 0
    for m in ADD_FK_RE.finditer(schema_rb):
        table, ref_table, opts = m.group(1), m.group(2), m.group(3)
        col_m = COLUMN_OPT_RE.search(opts)
        pk_m = PRIMARY_KEY_OPT_RE.search(opts)
        local_col = col_m.group(1) if col_m else singularize(ref_table) + '_id'
        ref_col = pk_m.group(1) if pk_m else 'id'

        if table not in schema:
            print(f"WARNING: {table!r} (from add_foreign_key) not found in schema JSON -- skipped")
            continue
        real_cols = schema[table].get('columns', {})
        if local_col not in real_cols:
            print(f"WARNING: expected local column {local_col!r} not found on {table!r} "
                  f"-- Rails default-convention guess didn't hold, skipped rather than guessed further")
            continue

        entry = {'column': local_col, 'ref_table': ref_table, 'ref_column': ref_col}
        existing = schema[table].setdefault('fk_columns', [])
        if entry in existing:
            continue  # re-run safety -- don't duplicate an entry already added
        existing.append(entry)
        added += 1
        print(f"{table}.{local_col} -> {ref_table}.{ref_col}")

    # Every table without an add_foreign_key still gets an explicit empty
    # fk_columns list (not just tables that got one added above) -- so
    # generator/fitness.py's fk_distance can tell "confirmed zero FKs"
    # apart from "this case study's schema JSON was never given FK-column
    # detail at all" (its own documented distinction, see its own scope
    # note) for every one of Spree's other 196 tables, not only these 6.
    for table in schema:
        schema[table].setdefault('fk_columns', [])

    with open(SCHEMA_JSON, 'w', encoding='utf-8') as f:
        json.dump(schema, f, indent=2)

    print(f"\nAdded {added} fk_columns entries. Wrote {SCHEMA_JSON}")


if __name__ == '__main__':
    main()
