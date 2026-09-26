# Common commands (PowerShell)

Everything here runs from the repo root (`D:\maheen\THesisCODE`) in
PowerShell, using the project's own venv Python (`./.venv/Scripts/python.exe`)
— never a bare `python`/`python3`. Native call syntax (`&`) is required
whenever the command starts with a quoted path.

---

## 1. Re-running the search

The search only needs re-running after a change to `generator/` (fitness,
mutation, candidate, dynamosa) or to `compiled_constraints.json` itself —
never after a `validation_oracle/`-only change (the validator reads
whatever archive already exists).

```powershell
# All 4 case studies (slow — FLEX2 alone can take several minutes)
& "./.venv/Scripts/python.exe" generator/rerun_dynamosa_nsga2_all.py

# OpenMRS only (doesn't touch the other 3 archives)
& "./.venv/Scripts/python.exe" generator/rerun_openmrs_only.py

# jBilling only
& "./.venv/Scripts/python.exe" generator/rerun_jbilling_only.py

# FLEX2 only
& "./.venv/Scripts/python.exe" generator/rerun_flex2_only.py

# Spree, FLEX2, jBilling only (doesn't touch OpenMRS's archive)
& "./.venv/Scripts/python.exe" generator/rerun_others_only.py
```

A **pure compile-time** fix (`decision_subject`, `cross_table_
placeholders`, out-of-scope moves) only needs a fresh VALIDATOR run
against the EXISTING archive — no search re-run needed, since the search
never reads either field during evaluation. A fix inside `candidate.py`'s
or `mutation.py`'s own construction/mutation logic (or anything the search
DOES read) needs a fresh search re-run first. When in doubt, both is
always safe, just slower.

Each overwrites the matching, git-tracked
`generator/experiment_runs/<CaseStudy>__dynamosa_nsga2__budget1x__seed0.pkl`
(+ `.json`). `git diff --stat generator/experiment_runs/` shows exactly
what changed; `git checkout -- generator/experiment_runs/<file>` reverts
one if a run looks wrong.

---

## 2. Per-individual verification (the "no-merge" tool)

The main day-to-day tool this session — keeps every archived individual
as its own standalone database, never merges them, and independently
verifies each one against the real validator.

```powershell
& "./.venv/Scripts/python.exe" validation_oracle/tests/per_individual_archive_coverage.py `
  --case-study <OpenMRS|Spree|FLEX2|jBilling> `
  --archive-pickle generator/experiment_runs/<CaseStudy>__dynamosa_nsga2__budget1x__seed0.pkl `
  --out-dir validation_oracle/tests/per_individual_out/<CaseStudy> `
  --mode optimized
```

- **`--mode optimized`** (recommended for day-to-day use): fast, gives the
  union coverage number — a global "still unverified" set shrinks as
  individuals are processed, skipping decisions once every rule in them
  is already verified.
- **`--mode full`** instead: much slower, but gives full per-individual
  -vs-every-rule detail (needed for deep tracing, e.g. "does this specific
  archived individual verify the rule it was claimed for").
- **jBilling and Spree need `--not-persisted-json`** (their decisions have
  `not_persisted` facts with no table-backed value):
  ```powershell
  --not-persisted-json validation_oracle/tests/jbilling_not_persisted.json
  --not-persisted-json validation_oracle/tests/spree_not_persisted.json
  ```
- **OpenMRS also needs one** now (`Birthdate Validity`'s own `evaluationTime`):
  ```powershell
  --not-persisted-json validation_oracle/tests/openmrs_not_persisted.json
  ```
- Prints a summary line automatically at the end (case study, total,
  claimed, in scope, out of scope, validated, % all, % in-scope).
- Overwrites `--out-dir` in place — untracked scratch output, safe to
  overwrite freely.

**All 4 case studies in one go** (paste as 4 separate commands, or run
one at a time and paste results back):

```powershell
& "./.venv/Scripts/python.exe" validation_oracle/tests/per_individual_archive_coverage.py --case-study OpenMRS --archive-pickle generator/experiment_runs/OpenMRS__dynamosa_nsga2__budget1x__seed0.pkl --not-persisted-json validation_oracle/tests/openmrs_not_persisted.json --out-dir validation_oracle/tests/per_individual_out/OpenMRS --mode optimized

& "./.venv/Scripts/python.exe" validation_oracle/tests/per_individual_archive_coverage.py --case-study Spree --archive-pickle generator/experiment_runs/Spree__dynamosa_nsga2__budget1x__seed0.pkl --not-persisted-json validation_oracle/tests/spree_not_persisted.json --out-dir validation_oracle/tests/per_individual_out/Spree --mode optimized

& "./.venv/Scripts/python.exe" validation_oracle/tests/per_individual_archive_coverage.py --case-study FLEX2 --archive-pickle generator/experiment_runs/FLEX2__dynamosa_nsga2__budget1x__seed0.pkl --out-dir validation_oracle/tests/per_individual_out/FLEX2 --mode optimized

& "./.venv/Scripts/python.exe" validation_oracle/tests/per_individual_archive_coverage.py --case-study jBilling --archive-pickle generator/experiment_runs/jBilling__dynamosa_nsga2__budget1x__seed0.pkl --not-persisted-json validation_oracle/tests/jbilling_not_persisted.json --out-dir validation_oracle/tests/per_individual_out/jBilling --mode optimized
```

**jBilling's `Order Period Already Invoiced` needs a SECOND run with a
DIFFERENT, still-fixed override** (2026-09-26) -- `Rule_1` needs the
OPPOSITE `candidateDateProvided` assumption from its own siblings, which
one single override file can never satisfy at once (this is by design,
not a bug — see `KNOWN_ISSUES.md`'s catB entry). Run into a SEPARATE
`--out-dir` so the first run's own results aren't overwritten, then union
the two runs' own verified-rule sets by hand for jBilling's real combined
picture:

```powershell
& "./.venv/Scripts/python.exe" validation_oracle/tests/per_individual_archive_coverage.py --case-study jBilling --archive-pickle generator/experiment_runs/jBilling__dynamosa_nsga2__budget1x__seed0.pkl --not-persisted-json validation_oracle/tests/jbilling_not_persisted_rule1.json --out-dir validation_oracle/tests/per_individual_out/jBilling_rule1 --mode optimized
```

Then combine into one table across all 4:

```powershell
& "./.venv/Scripts/python.exe" validation_oracle/tests/summarize_per_individual.py validation_oracle/tests/per_individual_out
```

---

## 3. Merge path (rebuilds the classic merged-fixture `.db` files)

A different, older verification path — merges every covered archive entry
into ONE shared database per case study (`dynamosa.merge_archive_candidate`)
instead of keeping individuals separate. Useful for cross-checking the
no-merge tool's own results, or for decisions whose junction row only gets
synthesized at merge time.

```powershell
# Rebuilds all 4 committed fixtures (tests/fixtures/*_merged.db)
& "./.venv/Scripts/python.exe" validation_oracle/tests/build_all_fixtures.py
```

Then verify one directly:

```powershell
& "./.venv/Scripts/python.exe" -c "
import sys
sys.path.insert(0, 'generator')
sys.path.insert(0, 'validation_oracle')
from coverage import run_coverage
summary = run_coverage('validation_oracle/tests/fixtures/spree_merged.db', 'Spree', 'dynamosa_nsga2', 'check', 'merged_archive', archive=None, out_dir='validation_oracle/tests/merge_check_out', not_persisted_overrides=None)
print(summary)
"
```

---

## 4. Regression suite (run after ANY change to `generator/` or `validation_oracle/`)

```powershell
& "./.venv/Scripts/python.exe" generator/candidate.py
& "./.venv/Scripts/python.exe" generator/mutation.py
& "./.venv/Scripts/python.exe" generator/fitness.py
& "./.venv/Scripts/python.exe" generator/dynamosa.py

& "./.venv/Scripts/python.exe" validation_oracle/tests/test_spec_cases.py
& "./.venv/Scripts/python.exe" validation_oracle/tests/test_drd_chaining_synthetic.py
& "./.venv/Scripts/python.exe" validation_oracle/tests/test_serialized_field_roundtrip.py
```

All are self-contained self-tests (no CLI args) — each prints its own
pass/fail confirmation at the end. Run them together after any change to
`fitness.py`, `mutation.py`, `candidate.py`, `dynamosa.py`, `db_resolver.py`,
or `drd_executor.py`.

---

## 5. Recompiling the ground truth (`compiled_constraints.json`)

Only needed after a real ground-truth/mapping change (a DMN edit, a new
override file entry) — **not** needed for anything in this file's other
sections. Be aware: a fresh, unfiltered recompile from source will
regenerate the FULL original rule set, including the 43 rules currently
moved out to `validation_oracle/out_of_scope/` — re-applying that removal
is a separate, manual step (see `validation_oracle/out_of_scope/*/README.md`),
not automatic.

```powershell
& "./.venv/Scripts/python.exe" generator/compile_constraints.py --out generator/compiled_constraints.json --report generator/compile_report.json
```

---

## 6. Before/after diff discipline (non-negotiable)

Any time `compiled_constraints.json` is edited (by hand, by a script, or
by recompiling), verify the change is exactly what was intended — a raw
`git diff` on this file is close to useless once record order shifts
(looks like a full rewrite even for a 2-record change). Use a semantic,
`record_id`-keyed diff instead:

```powershell
& "./.venv/Scripts/python.exe" -c "
import json, subprocess
old = json.loads(subprocess.run(['git','show','HEAD:generator/compiled_constraints.json'], capture_output=True, text=True).stdout)
new = json.load(open('generator/compiled_constraints.json'))
old_by_id = {r['record_id']: r for r in old}
new_by_id = {r['record_id']: r for r in new}
removed = set(old_by_id) - set(new_by_id)
added = set(new_by_id) - set(old_by_id)
common = set(old_by_id) & set(new_by_id)
changed = [rid for rid in common if json.dumps(old_by_id[rid], sort_keys=True) != json.dumps(new_by_id[rid], sort_keys=True)]
print('removed:', len(removed), ' added:', len(added), ' changed:', len(changed))
for rid in changed: print(' CHANGED:', rid)
"
```
