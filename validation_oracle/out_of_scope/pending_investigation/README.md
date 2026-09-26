# Pending-investigation rules (30) — NOT confirmed permanent

Removed from `generator/compiled_constraints.json` on 2026-09-26, on the
user's own explicit request, same mechanism as `../permanent/`. **The
difference from that folder matters: these are not proven unfixable.** Each
one fails today for a concrete, previously-fixed-elsewhere category of gap
— a missing schema override, or a not-yet-supplied disclosed value — not a
tooling limitation like COLLECT/code_external. Read this file before ruling
any of them out for good.

**`records.json`** holds the full compiled record for all 30 rules (47
records counting DRD fan-out variants), unchanged from what was in
`compiled_constraints.json` before removal.

## The 30, grouped by why they're currently unresolvable

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

### 4. jBilling rules the search claimed but couldn't independently verify, on the user's own explicit request (9 rules) — kept active elsewhere this session; moved out here specifically so they stop competing for search/validator time while `Ageing Step Config Validation` stays under active investigation

Unlike categories 1-3 above (each traced to ONE specific, common root
cause across several rules), these 9 are the LEFTOVER, still-unresolved
jBilling gaps from this session's own rule-by-rule tracing (2026-09-26)
after cat A/B/C's own fixes -- each individually diagnosed already (see
`validation_oracle/KNOWN_ISSUES.md`'s matching entries for the full
writeup of each), just not yet actually fixed, and moved out on request
rather than left cluttering the active search/validation runs. Removed
together as a single user decision, not because they share one root cause:

- **`Ageing Status Change Order Action::Rule_1`/`Rule_2`/`Rule_3`** --
  `newStatusIsDeleted`'s own `compared_to_named_constant` fix (this
  session) is confirmed correct, but the search hasn't independently
  claimed a genuinely satisfying individual for these 3 specific rules
  (only `Rule_4` has, so far).
- **`Currency Exchange Rate Source::Rule_1`** -- needs
  `hasEntitySpecificExchange=True`; the `base_user` correlation fix (this
  session) is confirmed correct and DID unlock `Rule_2`, but `Rule_1`'s
  own reachability wasn't separately investigated.
- **`Order Period Already Invoiced::Rule_3`** -- needs `candidateDate`
  fixed to something `>= 1` (its own real `next_billable_day`), a THIRD
  distinct `not_persisted` override assumption that would break `Rule_2`/
  `Rule_4`'s own already-working confirmation under `candidateDate=0` in
  the same run -- see `KNOWN_ISSUES.md`'s catB entry for the full
  writeup.
- **`Blacklist Filter Enabled::Rule_2`** -- `blacklistPluginId`'s own
  `compared_to_named_constant` (`PREFERENCE_USE_BLACKLIST=43`) is
  recorded correctly, but no individual has been confirmed to actually
  read the RIGHT `preference` row (`type_id=43`) rather than an arbitrary
  one -- not separately traced this session.
- **`Tax Calculation Needed::Rule_1`/`Rule_3`/`Rule_4`** -- the
  GLOBAL-`exists`-fact fitness fix (this session, catA) is confirmed
  correct (no longer FALSELY claims coverage), but the search hasn't yet
  found a genuinely clean individual within the tried population/
  generation budget -- a search-coverage/budget question, not a further
  code gap; see `KNOWN_ISSUES.md`'s catA entry.

`Ageing Step Config Validation::Rule_2`/`Rule_5` are DELIBERATELY NOT
included here, on the user's own explicit instruction -- kept in the
active corpus for continued investigation, even though they share the
identical "search hasn't claimed this branch yet" shape as several rules
above.

**Precedent for closing these**: each one's own `KNOWN_ISSUES.md` entry
already names the specific next step (a longer/bigger search re-run for
the coverage-budget cases; a third override run for `Rule_3`; tracing the
real subject row for `Blacklist Filter Enabled`) -- nothing here needs a
NEW investigation, just doing the already-identified next step.

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
