# Permanently out-of-scope rules (27)

Removed from `generator/compiled_constraints.json` on 2026-09-26, on the
user's own explicit request — not just filtered out at runtime anymore, but
physically absent from the corpus the search and validator both read. This
means the search no longer spends any generations on these objectives, and
the validator never has to resolve/skip a subject table for them either.

**`records.json`** in this folder holds the full compiled record for every
one of the 27 rules (condition tree, variable_resolution, outputs — the
complete record, byte-for-byte what was in `compiled_constraints.json`
before removal), so nothing is lost if they're ever needed again.

## Why these 22, specifically

Two structural criteria, both confirmed to make independent verification
impossible **regardless of what data the search ever builds** — not a data
gap, a tooling/representation gap:

1. **COLLECT hit policy (20 rules)** — `validation_oracle/rule_evaluator.py`
   only implements FIRST and UNIQUE rule selection; it has no COLLECT
   implementation at all. A COLLECT decision asks "find every row that
   violates this rule" (a set, not a single selected rule) — a different
   kind of question this oracle was never built to answer.
   - OpenMRS (15): `Order Date Activated Consistency Violations` (4),
     `Death Date Consistency Violations` (2),
     `Program Enrollment Date Consistency Violations` (3),
     `Relationship Date Validity Violations` (2),
     `Encounter Datetime Validity Violations` (4)
   - Spree (5): `Price Adjustment Tier Validity Violations` (5)

2. **Every compiled variant's own facts resolve to `code_external` (2
   rules)** — the fact is computed by application code (a Java constant, a
   UI-only transient value, a runtime calculation) with no schema
   representation at all, not even an approximate one.
   - jBilling (2): `Is Ageing Required::Rule_2`, `Daily Pro-Rate Amount::Rule_3`

(A rule with only SOME code_external facts, mixed with real schema-backed
ones — e.g. jBilling's `Ageing Step Config Validation::Rule_5` — was
deliberately NOT included here; it may still be genuinely resolvable via
its other, real facts, and stays in the active corpus.)

3. **A ground-truth fact whose real logic genuinely branches on a variable
   this project has no compiled representation for, and can't be safely
   auto-extracted without guessing (1 rule)** — OpenMRS's own
   `Identifier Uniqueness Check::Rule_4` needs `duplicateWithinSamePatient`
   AND `inUseByAnotherPatient` both `False`; `inUseByAnotherPatient`'s own
   ground truth was a complete, literal SQL `EXISTS(...)` statement (fixed
   2026-09-26, see `KNOWN_ISSUES.md`'s cat4 entry), but `duplicateWithin
   SamePatient`'s own notes are vague, conditional prose ("globally-unique
   type, or same/null location match") depending on a THIRD variable
   (`uniquenessBehavior`) — not a literal query, and the real condition
   doesn't fit this project's existing flat-AND `exists`+`filter_text`
   shape at all. Fixing it properly means reading the real
   `PatientIdentifierValidator.java` source (lines 112-130) and adding a
   new conditional/branching resolution kind — real, scoped work, but not
   attempted; moved out rather than guessed.
   - OpenMRS (1): `Identifier Uniqueness Check::Rule_4`

4. **A ground-truth fact that only cross-references another fact by prose,
   never restating its own real logic (4 rules)** — `Obs Group Value
   Exclusivity`'s own `isObsGroup` notes are literally `"same as above"`,
   pointing at `Obs Value Required By Datatype`'s own (separately fixed)
   `isObsGroup` fact rather than describing its own. Resolving this would
   mean following a cross-row textual reference at compile time — a
   different, easy-to-get-wrong shape from either pattern cat3's fix
   actually implemented — deliberately left unattempted rather than
   guessed, and since ALL 4 of this decision's rules read `isObsGroup`,
   the whole decision moves.
   - OpenMRS (4): `Obs Group Value Exclusivity::Rule_1`-`Rule_4`

## If this ever needs to change

Restoring a rule: copy its record(s) back into `compiled_constraints.json`
(keep the same record_id — it's how the archive/search machinery keys
everything) and re-run `generator/rerun_dynamosa_nsga2_all.py` for the
affected case study, since the old archive pickle never searched for it.
Worth doing for criteria 1/2 only if `rule_evaluator.py` ever gains
COLLECT support, or a `code_external` fact is later found to have a real
schema mapping after all. Worth doing for criterion 3 if
`duplicateWithinSamePatient` is ever compiled properly (a new conditional
resolution kind, informed by the real Java source). Worth doing for
criterion 4 if `isObsGroup`'s cross-row reference is ever resolved at
compile time.
