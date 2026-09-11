# Schema extraction — all four case studies

Static, heuristic DDL/changelog parsers producing one uniform JSON shape per case
study, for use by this project's DMN-to-schema mapper and (eventually)
`compile_constraints.py`. Consistent with this project's established methodology
(regex/XML parsers over raw schema sources, not live DB introspection), applied
uniformly across all four format types this program covers: Oracle DDL, PostgreSQL
DDL, Liquibase XML, and Rails migrations.

## Uniform output shape

Every parser emits the same per-table structure:

```json
{
  "TABLE_NAME": {
    "pk": "COLUMN_NAME" | ["COL1", "COL2"] | null,
    "columns": {
      "COLUMN_NAME": {"type": "VARCHAR2", "null_false": true}
    },
    "fks": ["REFERENCED_TABLE_1", "REFERENCED_TABLE_2"],
    "indexes": [{"unique": true, "cols": ["COL1", "COL2"]}],
    "checks": ["raw check-constraint expression text"]
  }
}
```

`fks` is a **deduplicated set of target tables**, not a raw count of FK constraint
declarations — a table with multiple FK columns pointing at the same parent table
(common in all four case studies) collapses to one entry. Each parser's own summary
output reports both the raw declaration count and the deduplicated relationship
count explicitly, so the two are never silently conflated.

## Per-case-study results (validated against this project's own documented numbers)

| Case study | Source format | Tables | PK | Raw FK declarations | UNIQUE | CHECK | Match? |
|---|---|---|---|---|---|---|---|
| FLEX2 | Oracle DDL (`Flex1.sql`) | 220 | 140 | 225 | 14 | 0 | ✅ exact |
| OpenMRS | Liquibase XML (2 files) | 119 | 117 | 448 | 120 | 0 | ✅ exact |
| Spree Commerce | Rails migrations (276 files) | 197 | 196 | 6 | 104 | 3 | ✅ exact (this project's own first extraction, not a re-verification of a prior number) |
| jBilling | PostgreSQL DDL (`jbilling_test.sql`) | 98 | 85 | 120 | 0 | 0 | ✅ exact |

Every number above for FLEX2, OpenMRS, and jBilling was independently reproduced
from the raw schema source and matches this project's previously documented figures
exactly — nothing was tuned to hit a target number. Three genuine parsing bugs were
found and fixed *during* this process, each because a first pass's numbers didn't
match the documented totals and were traced to a real cause rather than adjusted to
match:

- **FLEX2**: initially missed `CREATE GLOBAL TEMPORARY TABLE` syntax (16 tables) and
  two unnamed-constraint forms (`ADD PRIMARY KEY (...)` / `ADD UNIQUE (...)` without
  a named `CONSTRAINT` clause, used by 11 PK and 2 UNIQUE declarations respectively).
  Also excluded 4 Oracle-Text housekeeping tables (`DR$...` prefix), matching this
  project's own established exclusion.
- **OpenMRS**: initially missed inline `<constraints unique="true"/>` on column
  definitions (117 of the 120 UNIQUE constraints are declared this way, only 3 via
  a standalone `addUniqueConstraint` changeset) — a real, non-obvious Liquibase
  authoring convention, not an edge case.
- **jBilling**: no fix needed — matched exactly on the first run.

## Per-case-study scripts

- `parse_flex2_ddl.py Flex1.sql` → `flex2_schema_full.json`
- `parse_openmrs_liquibase.py schema.xml update.xml` → `openmrs_schema_full.json`
- `parse_jbilling_ddl.py jbilling_test.sql` → `jbilling_schema_full.json`
- `parse_spree_migrations.py` (reads a hardcoded local clone path; see its own
  docstring) + `generate_schema_rb.py` → `spree_schema_full.json` and
  `spree_schema.rb` (a single consolidated schema file, since Spree — a Rails
  engine, not an app — has no `db/schema.rb` of its own)

Each script's own docstring documents its specific known limitations (see each file
directly) — the common ones across all four:
- DEFAULT values are not tracked by any of the four parsers.
- None of the four evaluates runtime/conditional logic embedded in the schema
  source (e.g. Ruby `if`/`else` branches in Rails migrations); where present, this
  is documented per-parser rather than silently resolved one way or the other.
- Column types are reported as declared in the source DDL/DSL, not normalized to a
  common type system across the four case studies — a consumer needing cross-case-
  study type comparability (e.g. the mapper) should normalize on read.

## Source files (not redistributed here)

`Flex1.sql`, `jbilling_test.sql`, and the two OpenMRS Liquibase XML files are this
project's own data, supplied directly rather than fetched. `spree_schema_full.json`
was produced from a live `git clone` of `github.com/spree/spree` (BSD-3-Clause,
`main` branch, 2026-09-10) — see `parse_spree_migrations.py`'s docstring for the
exact clone/checkout details, since Spree's source is not bundled in this package
either.
