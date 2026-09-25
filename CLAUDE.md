# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A thesis pipeline for search-based test-data generation from DMN business-rule models. Business rules for four real-world case-study applications (FLEX2, jBilling, OpenMRS, Spree) are authored/mined as DMN decision tables, compiled into constraint objectives, and used to drive a many-objective genetic search (DynaMOSA) that produces a concrete SQL/SQLite test database satisfying as many decision branches as possible. A separate, largely decoupled oracle then independently re-verifies that the generated database really satisfies what the search claims to have covered.

Pure Python, standard library only — there is no `requirements.txt`, `pyproject.toml`, or `package.json` anywhere in the repo, and nothing to install beyond Python itself. `.venv` is Python 3.14.7. There is no CI, Makefile, or pytest config; every module is run directly (`python3 script.py`) and most have an `if __name__ == '__main__':` self-test block instead of a pytest suite.

## Data flow / architecture

```
Raw schema sources (Flex1.sql, Liquibase XML, jbilling_test.sql, Spree migrations)
        │  all_schema_extraction/all_schema_extraction/parse_*.py
        ▼
Per-case-study schema JSON ({TABLE: {pk, columns, fks, indexes, checks}})
        │
Hand-authored/mined DMN rules (openmrs_dmn/, spree_dmn/, jbillingandflex/*_dmn/)
        │                       \
        │                        dmn_schema_mapper/mapper/*.py (auto-mapper; ablation-only,
        │                        ~31-55% top-1 accuracy, NOT trusted unattended)
        ▼                             │
                          variable_to_schema_mapping.csv (hand-curated; this is what
                          compile_constraints.py actually reads by default)
        ▼
generator/compile_constraints.py (+ feel_parser.py for FEEL expressions)
        ▼
generator/compiled_constraints.json  (one record per branch/objective: condition
        │                             tree, hit_policy, variable_resolution,
        │                             outputs, fk_closure_tables)
        ├──► taxonomy/ (classifies each variable/branch into a DMN→SQL/DDL
        │              construct taxonomy; reuses compile_constraints.py's
        │              resolution logic)
        ▼
generator/dynamosa.py + search.py/mutation.py/crossover.py/fitness.py
        (DynaMOSA: one shared population, one dynamically-activated objective
        per compiled branch, NSGA-II-style non-dominated sorting)
        ▼
generator/materialize.py → generate_dataset.py → real SQL/CSV/SQLite test database
        ▼
validation_oracle/ (drd_executor.py + rule_evaluator.py — deliberately
        independent of generator/fitness.py) re-executes DMN rule selection
        against the generated DB to catch cases where claimed coverage isn't real
        (e.g. a subject table the search never actually populated).
```

### Key directories

- `all_schema_extraction/all_schema_extraction/` — one DDL/schema parser per case study, each emits a `*_schema_full.json`.
- `dmn_schema_mapper/mapper/` — prototype auto-mapper (`schema_extract.py` → `dmn_extract.py` → `mapper.py` → `validate_mapper.py`) producing `variable_to_schema_mapping.csv`. Low accuracy; the hand-curated CSV is the trusted default input to the generator.
- `openmrs_dmn/`, `spree_dmn/`, `jbillingandflex/flex2_dmn/flex2_dmn/`, `jbillingandflex/jbilling_dmn/jbilling_dmn/` — the DMN rule packages themselves (`.dmn` files under e.g. `openmrs_dmn/dmn/`). There is no separate `rules/` directory — the DMN decision-table rows *are* the rules, later compiled into `generator/compiled_constraints.json`.
- `generator/` — the core pipeline: FEEL parsing (`feel_parser.py`), constraint compilation (`compile_constraints.py`), and the DynaMOSA search itself (`dynamosa.py`, `candidate.py`, `mutation.py`, `crossover.py`, `fitness.py`, `search.py`, `materialize.py`, `generate_dataset.py`, `sql_compiler.py`, `random_baseline.py` for baseline comparison, `run_experiments.py` / `rerun_dynamosa_nsga2_all.py` as experiment drivers).
- `validation_oracle/` — independent oracle. `drd_executor.py` runs a full decision (DRD chaining); `rule_evaluator.py` is a boolean condition-tree evaluator + FIRST/UNIQUE hit-policy selector, intentionally kept independent from `generator/fitness.py`; `db_resolver.py`, `subject_table.py`, `schema_utility.py`, `dmn_walk.py`, `phase1_utility.py` support it (`phase1_utility.py` is the only module allowed to touch generator internals); `coverage.py`, `join_disambiguation.py`, `out_of_scope_rules.py`, `subject_root_overrides.py`, `supplementary_fk_edges.py` round it out. See `validation_oracle/DESIGN.md` for the rationale (documents real cases where search-claimed coverage didn't hold against the actual merged DB).
- `taxonomy/` — classifies every ground-truth variable/compiled branch into a DMN→SQL/DDL construct taxonomy (`construct_taxonomy.csv`, `usage_shapes.csv`).
- `schemas/`, `docs/` — raw source schema files (e.g. `Flex1.sql`, Liquibase XML) and misc docs.
- Root `HANDOFF.md`, `QUICK_REFERENCE.md`, `RULE_TO_OBJECTIVE_MAPPING.md` — running session-handoff and design logs, not code. Check `HANDOFF.md` for the latest state of in-progress work before starting a task.

## Commands

There's no unified build/test runner — invoke scripts directly per component.

**Schema extraction** (`all_schema_extraction/all_schema_extraction/`):
```bash
python3 parse_flex2_ddl.py Flex1.sql
python3 parse_openmrs_liquibase.py schema.xml update.xml
python3 parse_jbilling_ddl.py jbilling_test.sql
python3 parse_spree_migrations.py   # then generate_schema_rb.py
```

**DMN builds** (jbillingandflex):
```bash
# flex2_dmn
python3 scripts/build_flex2_dmn.py   # uses scripts/dmn_builder.py, emits .dmn + provenance CSV
# jbilling_dmn
python3 scripts/build_jbilling_dmn.py
python3 scripts/build_jbilling_mapping.py
python3 validate_dmn.py              # XML well-formedness, arity, DMN<->CSV consistency
```

**Constraint compilation** (`generator/`):
```bash
cd generator
python3 compile_constraints.py --out compiled_constraints.json --report compile_report.json
# single case study:
python3 compile_constraints.py --case-study FLEX2 --out flex2_only.json --report flex2_report.json
```

**Validation oracle tests** (`validation_oracle/tests/`) — no pytest, run scripts directly:
```bash
python3 test_spec_cases.py               # 10 hand-built FIRST/UNIQUE/aggregate/join spec cases
python3 test_drd_chaining_synthetic.py
python3 test_serialized_field_roundtrip.py
```
Fixtures live in `validation_oracle/tests/fixtures/` (real merged SQLite DBs: `flex2_merged.db`, `openmrs_merged.db`, `jbilling_merged.db`, `spree_merged.db`, plus `synthetic_T_schema.json`).

## Notes for working in this repo

- When touching DMN rules or the mapping CSV, prefer the hand-curated `variable_to_schema_mapping.csv` over the auto-mapper's output — the auto-mapper is an ablation/experimental path, not the trusted default.
- Keep `validation_oracle/`'s rule evaluation logic independent from `generator/fitness.py` — that separation is intentional (it's what lets the oracle catch cases where the search's self-reported coverage is wrong), so don't casually import one into the other.
- `generator/dynamosa.py`'s docstring records several past correctness fixes (focal-per-objective row ownership, aggregate row-sharing via `_OWNER_KEY`, persisting mutated `not_persisted` placeholders across generations) — read it before modifying individual/objective handling, since these were non-obvious bugs.
- Scratch/experimental output (e.g. files under `validation_oracle/tests/per_i/`, `per_individual_out/`, or stray `.db`/`.json` dumps) tends to accumulate untracked in `validation_oracle/tests/` — check `git status` before assuming such files are part of the real test suite.
