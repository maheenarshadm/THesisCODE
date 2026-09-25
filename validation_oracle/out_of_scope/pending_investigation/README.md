# Pending-investigation rules (21) — NOT confirmed permanent

Removed from `generator/compiled_constraints.json` on 2026-09-26, on the
user's own explicit request, same mechanism as `../permanent/`. **The
difference from that folder matters: these are not proven unfixable.** Each
one fails today for a concrete, previously-fixed-elsewhere category of gap
— a missing schema override, or a not-yet-supplied disclosed value — not a
tooling limitation like COLLECT/code_external. Read this file before ruling
any of them out for good.

**`records.json`** holds the full compiled record for all 21 rules (38
records counting DRD fan-out variants), unchanged from what was in
`compiled_constraints.json` before removal.

## The 21, grouped by why they're currently unresolvable

### 1. Join-path/schema-reachability gap (9 rules) — the same category this project has fixed before, repeatedly

Error, verbatim: *"Cannot pick a unique root reaching [...] — 0 candidate(s)
qualify."* `subject_table_for_decision` couldn't find any single table that
reaches every table these facts need via a real FK path.

- **Spree — `Promotion Item Total Eligibility` (4 rules: rule_1-4)** — needs
  a root reaching both `spree_orders` and `spree_promotion_rules`.
- **FLEX2 — `Admission Closure Eligibility` (5 rules: Rule_1-5)** — needs a
  root reaching both `ADM_MERIT_LIST` and `STUDENT_PROGRAM`.

**Precedent this project already has for closing exactly this kind of gap**:
`subject_root_overrides.py` (naming which of several qualifying candidate
tables to use when more than one technically reaches everything) and
`supplementary_fk_edges.py` (declaring a real FK relationship the schema
extractor missed) — both used to fix other decisions this same way already
(e.g. FLEX2's own `Course Load Limit`). Nobody has checked yet whether
either applies here, or whether the schema genuinely has no such path.

### 2. Every input is `not_persisted` (8 rules) — same category as jBilling's own already-partially-fixed decisions

Error, verbatim: *"No table-backed inputs found ... every input is
non-table-backed (literal/upstream/not_persisted); this decision cannot be
independently entity-enumerated from the database alone."*

- **jBilling — `Order Date Range Valid` (5 rules: Rule_1-5)** — every input
  (`parseOrAccessError`, `startDateProvided`, `endDateProvided`, `startDate`,
  `endDate`) is a transient runtime parameter.
- **jBilling — `Payment Outcome Resolution` (2 rules: Rule_1-2)** — `processorUnavailable`.
- **jBilling — `Payment Balance Assignment` (1 rule: Rule_2)** — chains from
  `Payment Outcome Resolution`'s own unresolvable input.

**Precedent this project already has for closing exactly this kind of gap**:
`--not-persisted-json` (a disclosed, explicit override value supplied per
run — e.g. `jbilling_not_persisted.json`'s own `candidateDateProvided`/
`candidateDate`/`__today__`) already partially resolved jBilling's `Order
Period Already Invoiced` this exact way. Nobody has tried supplying values
for `parseOrAccessError`/`startDateProvided`/`processorUnavailable` etc. yet.

### 3. A derived arithmetic/date formula silently dropped at compile time (2 rules) — `compile_constraints.py`'s own `classify_derived()` gap

Ground truth correctly names a real formula (e.g. `variable_to_schema_
mapping.csv`: `yearsSinceBirthdate -> TIMESTAMPDIFF(YEAR, birthdate,
CURRENT_DATE)`), but `classify_derived()` has no pattern-matcher for
date-arithmetic or modulo-arithmetic formulas at all -- neither matches any
of its specific checks (aggregate recipe, case-map, raw-SQL-boolean, join,
existence, regex), so both fall through to the generic single-pair
fallback, which silently discards the formula and returns a bare
`schema_column` reading the WRONG raw value instead of the computed one.
Confirmed via a full-corpus scan (2026-09-26): exactly these 2 instances,
not widespread.

- **OpenMRS — `Birthdate Validity::Rule_2`/`Rule_3`** — `yearsSinceBirthdate`
  compiles as `schema_column: person.birthdate` instead of the real
  `TIMESTAMPDIFF(YEAR, birthdate, evaluationTime)`, so `Rule_2`'s own
  `yearsSinceBirthdate > 140` compares a raw birthdate placeholder against
  140, essentially never true regardless of real age. (`Rule_1`, which
  doesn't reference `yearsSinceBirthdate` at all, is unaffected and stays
  in the active corpus.)
- **OpenMRS — `Numeric Precision Validity::Rule_2`/`Rule_3`** —
  `valueNumericHasFraction` compiles as `schema_column: obs.value_numeric`
  instead of the real `MOD(value_numeric, 1) <> 0`, so both rules compare
  a raw number against a boolean literal, never correctly. (`Rule_1`,
  which doesn't reference it, is unaffected and stays active.)

**No existing precedent closes this one yet** -- unlike the two categories
above, this needs new capability, not just a disclosed data override:
nothing in `fitness.py`/`candidate.py`/`db_resolver.py` today has a
resolution kind for "a value computed by arithmetic over two OTHER already
-resolvable sibling facts" (the closest existing shape,
`substituted_decision`'s own `expression`/`free_variable_resolutions`, is
built for chaining onto an UPSTREAM decision's output, not two facts
within the SAME record -- though its underlying `evaluate_expression`/
`_ARITH` arithmetic engine could plausibly be reused rather than
duplicated). Also a real open methodological question, not just an
implementation gap: `birthdate`/`evaluationTime` are placeholder integers
in the search's own representation, not real calendar dates, so "years
between them" only has a principled meaning under a disclosed day-count
convention (this project already has precedent for such conventions
elsewhere, e.g. `__today__`) -- not yet confirmed one way or the other.

## If this ever needs to change

Restoring a rule (or a whole decision): copy its record(s) back into
`compiled_constraints.json` (same record_id), then actually attempt the fix
that category suggests above (a `subject_root_overrides.py`/
`supplementary_fk_edges.py` entry, or a new `--not-persisted-json` value) —
re-verify with `coverage.py`/`per_individual_archive_coverage.py` before
declaring it resolved. If investigated and found genuinely unfixable, move
the record(s) to `../permanent/` instead, with the real reason documented,
the same way this project's other scope decisions are made — never silently
re-excluded without saying why.
