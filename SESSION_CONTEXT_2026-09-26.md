# Session context — for a new chat picking up this work

**Purpose of this file**: a self-contained handoff of everything decided
and done in the Claude session that ended 2026-09-26, so a FRESH chat
(no memory of this conversation) can continue correctly. Read this FIRST,
before touching code. `CLAUDE.md` (repo root) already explains the
project's own architecture/commands — this file is about what happened
in THIS session specifically: what was fixed, what's still open, what
the user cares about, and how they like to work.

---

## 1. What this session did, in one paragraph

Systematically traced and closed the gap between what the DynaMOSA
search *claims* it covers (a rule/objective reaching `fitness=0.0`) and
what the independent validation oracle can *actually verify* against the
real, materialized database — for three of the four case studies
(OpenMRS, jBilling, FLEX2; Spree was NOT touched this session). Found
and fixed **~20 real, distinct bugs** across the generator (search) and
the validator, each one root-caused with real evidence (never guessed),
verified via a semantic diff of `compiled_constraints.json` and/or a
direct simulation against the archive BEFORE asking the user to spend
time on a real re-run, and logged in full in
`validation_oracle/KNOWN_ISSUES.md`. Also made two deliberate SCOPE
decisions (moving genuinely out-of-scope/deferred rules out of the
active corpus) on the user's own explicit request.

## 2. Current, real, honestly-verified coverage (as of this session's last re-run of each)

| Case study | Total rules | Claimed | Validated | % |
|---|---|---|---|---|
| OpenMRS | 60 | 57 | 51 | 85.0% |
| jBilling | 20 (trimmed from 29 — see §4) | ~19 | 18 (combined across 2 override runs — see §4) | 90% |
| FLEX2 | 50 | 43 | 36 | 72.0% |
| Spree | 22 | — | — | **not touched this session** |

These numbers came from the user actually running the search + validator
themselves each time (per their own explicit standing rule — see §6) and
pasting the summary line back. Do not assume a number is current without
seeing a fresh paste — several fixes needed 2-3 re-run rounds before
landing, and search re-runs have real, non-regression variance run to
run (a shared DynaMOSA population's coverage shifts when the objective
set changes, even with a fixed seed).

## 3. The full bug list (see `validation_oracle/KNOWN_ISSUES.md` for complete root-cause writeups — search by case-study name or by the header text below)

### OpenMRS (42 → 51 validated)
1. `compute_decision_subject`'s forward-FK-only root-picking couldn't
   find a subject needing a backward hop (e.g. `obs -> concept <-
   concept_numeric`). Fixed by porting `functional_backward_edges` +
   a join-disambiguation override + fixing a 4th, independently-found
   `also_valid_in`-reachability bug in the same area.
2. `classify_derived()` silently dropped two real ground-truth facts
   (`isIndexTerm`/`isShortName` — literal-equality; `isObsGroup` —
   self-join EXISTS prose), both mis-compiled as a bare `schema_column`.
3. A genuinely NEW bug in the VALIDATOR (`subject_table.py`), found while
   chasing fix #2's own regression: a `:column`/`self` filter_text
   reference resolves EXCLUSIVELY off the subject row (no join-path
   fallback the way a `<placeholder>` has) — `subject_table.py`'s own
   table-extractor never drew that distinction. Fixed in the validator
   itself, not just the generator (this is the one case this session
   where the validator, not the generator, had the real bug).

### jBilling (17/29 at session start → 18/20 combined, on a trimmed 20-rule corpus)
1. A GLOBAL (subject-independent) `exists` fact
   (`customContactFieldConfigured`) was scoped to the search's own
   per-owner rows during fitness evaluation, letting sibling objectives
   needing CONTRADICTORY values of the same global fact both falsely
   claim `fitness=0.0`. Fixed the read side (`candidate.py`) to check the
   WHOLE candidate table for a genuinely global fact, matching the
   validator's own real-SQL semantics.
2. `entity_id`/`currency_id`/`status_id` never correlated onto a real
   `base_user` row — the correlation mechanism existed
   (`compute_cross_table_placeholder_correlations`) but its own
   placeholder-source dict, `_DECISION_SUBJECT_PLACEHOLDER_SOURCES`,
   wasn't decision-scoped, risking a real cross-decision collision if
   widened carelessly. Fixed by adding `decision_name` to the key.
   **Along the way, found and fixed a real mistake in the FIRST attempt**
   at this widening: wrongly assumed every EXISTING placeholder name was
   already unique to one decision (2 FLEX2 placeholders, `student`/`this
   course offering`, weren't — caught via a full corpus survey before
   shipping, not after). Also ported the correlation mechanism's own
   RUNTIME wiring into the no-merge per-individual tool (it only ever ran
   in the merge path before).
3. A boolean fact compiled as a bare `schema_column`
   (`newStatusIsDeleted`, `currentStatusIsActive`) had its literal
   `True`/`False` written straight into a PRIMARY KEY column, corrupting
   it. Fixed by teaching `_CONSTANT_RE`/a new cross-reference resolver
   about `compared_to_named_constant`, then making BOTH the read side
   (`candidate.py`/`db_resolver.py`) and write side (`mutation.py`)
   actually consult it (previously write-only, dead metadata). This also
   surfaced a SECOND bug: `mutation.py`'s own `_domain_escape_value`
   didn't know a boolean domain has no third "escape" value (was
   producing literal strings like `'False_'`).
4. `Order Period Already Invoiced::Rule_1` needs the OPPOSITE
   `not_persisted` assumption from its own siblings. **Confirmed this is
   NOT a bug** — `coverage.py`'s own docstring already explains why
   `not_persisted_overrides` is deliberately never read from the search's
   own `scenario_maps` (to avoid a circular, self-confirming validator).
   Closed with a SECOND, disclosed override file
   (`validation_oracle/tests/jbilling_not_persisted_rule1.json`,
   `{"candidateDateProvided": false, "candidateDate": 0}`) and a second
   validator run — same precedent as OpenMRS's own `evaluationTime` pick.
   **jBilling's real coverage is the UNION of both runs' verified sets.**
5. **Scope decision, on the user's own explicit request**: 9 of
   jBilling's remaining unvalidated rules moved to `validation_oracle/
   out_of_scope/pending_investigation/` (category 4 there has the full
   list + each one's own already-known next step), physically removed
   from `compiled_constraints.json`. `Ageing Step Config
   Validation::Rule_2`/`Rule_5` were DELIBERATELY KEPT ACTIVE for
   continued investigation (per the user's own instruction) — `Rule_2`
   sits at `fitness=0.5` (search hasn't claimed it); `Rule_5` isn't even
   claimed at all despite a `literal: true` fallback condition — this is
   the most concrete open thread for jBilling.

### FLEX2 (0% at first real attempt → 36/50 = 72.0%)
FLEX2 had NEVER been run through the per-individual validator this
session before this work — first attempt found EVERY ONE of 77 archived
individuals crashing at materialization.
1. **Universal crash**: `_build_decision_subject_row`'s hop-target lookup
   was focal-only, so a record already owning a real row on a hop's
   target table (just never registered as its own focal row) got a
   SECOND, colliding row manufactured for it. Fixed by also checking the
   whole candidate for an owner-tagged row first. **0% → 36/50
   immediately.**
2. `cross_table_placeholders` computation/consumption never recursed
   into a `substituted_decision`'s own nested `free_variable_
   resolutions` — a placeholder living on a NESTED aggregate
   (`Attendance Eligibility For Final Exam::attendancePercentage`'s own
   `lecturesAttended`/`lecturesHeldForOffering`) never got correlated.
   Fixed both the compile-time pass and the runtime consumer to recurse.
3. `_construct_subquery_parent` never tagged the row it creates with
   `_OWNER_KEY` — harmless at SEED time (a later pass re-tags
   everything), but a real gap at MUTATION time (no such pass exists
   there). Fixed by threading `owner_id` through.
4. `_decision_subject_tables_referenced` required a join path to
   `derived_join_count`'s own `prereq_table` too, but that table is
   queried via a raw, uncorrelated scan needing no join at all — left
   `Credit Transfer Exemption` (and, as a genuine bonus, `Course
   Registration Eligibility` — 26 more records) with ZERO qualifying
   subject-root candidates. Fixed by requiring only `registration_table`.
5. Enabling `decision_subject` for two more decisions at once (fix 4)
   exposed a SECOND collision bug: `_build_decision_subject_row` had NO
   collision-check at all (unlike its own sibling function). DRD chaining
   legitimately reuses an upstream case's own scenario value across
   DIFFERENT records, so two records can land on the identical hop-target
   PK. Fixed by extracting a shared `_bump_colliding_rows` helper. **This
   surfaced a THIRD, deeper, LATENT bug from EARLIER in this SAME
   session's own OpenMRS cat1 self-correlation fix**: its "register this
   row as the self-table's own anchor" fallback assumed `self_table`
   always equals the row's own destination table — true for the original
   motivating case, wrong for `semestersElapsed` (`self_table=
   'STUDENT_PROGRAM'`, row being built is `STUDENT_SEMESTER`). Fixed by
   threading an explicit `table` parameter through `_row_from_filter_
   conjuncts` (both independent copies, candidate.py and mutation.py) and
   only aliasing when they genuinely match.

**Not fixed, flagged only**: `OperationalError: table PROGRAM_COURSE has
no column named CREDIT_HRS` (3 individuals) — `degreeTotalCredits`'s own
`SUM` over a joined `PROGRAM_COURSE, COURSE` FROM-list puts `CREDIT_HRS`
on the wrong side of the join somewhere in construction. Pre-existing,
unrelated to the fixes above, not investigated.

**Remaining FLEX2 gaps, not yet traced**: `Credit Transfer
Exemption::Rule_2`, `Graduation Eligibility::Rule_1`-`Rule_5` (all 5 still
show zero verified even after the `semestersElapsed` fix — worth
checking if they're even CLAIMED now), `Summer Semester
Registration::Rule_2`/`Rule_3` (on the original gap list, not
re-checked after the later fixes).

## 4. Important nuances a new chat needs to not re-litigate

- **"Claimed" can be a lie the search tells itself, or the print tool
  can lie about the count.** Two SEPARATE things were fixed this
  session: (a) real fitness-function bugs where the search HONESTLY
  computed `fitness=0.0` from a wrong/incomplete check (catA, the
  boolean-into-PK bugs, etc.) — these needed CODE fixes; (b) a pure
  REPORTING bug in `_print_summary_line` where `Claimed` summed raw
  archive records instead of deduplicating by rule_id, inflating FLEX2's
  own count to 77 against a Total of 50 (DRD fan-out variants). Don't
  confuse the two categories when a `Claimed > Total` number looks wrong.
- **A search re-run can look like a regression when it isn't.** DynaMOSA
  shares ONE population across every objective. Removing/adding
  objectives (an out-of-scope move) or changing WHICH facts the fitness
  function correctly rejects (a code fix) shifts selection pressure for
  the WHOLE population, so OTHER, unrelated rules can gain or lose
  coverage between runs even with the same seed. Confirmed multiple
  times this session (e.g. OpenMRS 51→47→51 jitter, jBilling 18→17→18).
  Before calling something a regression, check whether any NEW crash/
  error appeared — if not, it's probably just stochastic variance.
- **`not_persisted` overrides are deliberately never read from the
  search's own `scenario_maps`** — this is a documented design
  principle (`coverage.py`'s own docstring), not an oversight. A
  decision needing genuinely OPPOSITE assumptions across its own rules
  (jBilling's `Order Period Already Invoiced`) needs MULTIPLE disclosed
  override files and multiple validator runs, unioned by hand — never a
  single "smarter" override that reads the search's own per-record value
  (that would be circular/self-confirming, exactly what independent
  verification exists to prevent).
- **A pure compile-time fix (`decision_subject`, `cross_table_
  placeholders`, an out-of-scope move) only needs a fresh VALIDATOR run**
  against the EXISTING archive — the search never reads either field
  during evaluation. A fix inside `candidate.py`'s or `mutation.py`'s own
  construction/mutation logic needs a fresh SEARCH re-run first (the
  existing archive has the bug baked into its own rows). Getting this
  wrong wastes the user's time on an unnecessary multi-minute search run
  — always check which kind of fix it is before asking for a re-run.
- **`candidate.py` and `mutation.py` maintain INDEPENDENT, parallel
  copies** of several functions (`_row_from_filter_conjuncts`, boolean-
  literal parsing, etc.) — a documented, deliberate project convention
  ("the parsing rules must stay identical, so any change to one belongs
  in the other too"). Every fix to one of these shared shapes this
  session was mirrored into BOTH copies; check for this pattern before
  declaring a fix complete.

## 5. What was OUT of scope / deliberately not done

- Spree was not touched at all this session (no rule-by-rule tracing).
- `Order Period Already Invoiced::Rule_3` (jBilling) — needs a THIRD
  distinct `not_persisted` override assumption, would break `Rule_2`/
  `Rule_4`'s own already-working confirmation in the same run — flagged,
  not attempted.
- The `PROGRAM_COURSE.CREDIT_HRS` bug (FLEX2) — found, not fixed.
- 9 jBilling rules moved to `pending_investigation/` per the user's own
  explicit request (see §3, jBilling item 5) — each has a known next step
  recorded there, none attempted.
- A separate, one-off deliverable was also produced this session (NOT
  part of the thesis pipeline itself): `PROJECT_GOAL_PROMPT.md` plus two
  zip bundles (`project_goal_bundle.zip` — OpenMRS+FLEX2 DMN/schemas,
  `spree_jbilling_bundle.zip` — Spree+jBilling DMN/schemas), for the user
  to hand to someone else as a goal-only spec (no implementation
  details). These are untracked in git, not part of the real codebase.

## 6. How the user likes to work (saved as durable memory on this account — a fresh chat on a DIFFERENT account/machine won't have these automatically, so they're restated here)

- **PowerShell only for commands given to the user to run** — always
  `& "./.venv/Scripts/python.exe" ...` syntax, never bare `python3` or
  bash-style commands. The user runs everything themselves in PowerShell;
  Claude's own internal Bash tool use is fine, just never surfaced to
  the user as something to paste.
- **Never push to git without being asked in THAT turn**, even if a
  broad "commit and push" instruction was given earlier in the session.
  Commit freely once asked for commits in general; always stop after
  `git commit` and wait for an explicit "push" each time.
- **Never mark a fix "RESOLVED" in `KNOWN_ISSUES.md` until the user's
  own re-run actually confirms it.** It's fine to say a fix is
  "implemented" and describe how it was verified statically (semantic
  diff, matches the validator's own resolution, a direct simulation
  against the archive) — but the status header itself only flips to
  RESOLVED after a real, user-run re-run comes back.
- **General working rhythm this whole session**: trace a claimed-but-
  unverified rule using real evidence (dump the archived individual's
  own rows/scenario, run `drd_executor`/`db_resolver` directly against
  the materialized DB, never guess) → identify the exact root cause →
  implement the narrowest fix that closes it → verify via a semantic,
  record-id-keyed diff of `compiled_constraints.json` (NEVER a raw `git
  diff`, which is misleading once record counts change) + the full
  regression suite → tell the user what to re-run and why → wait for
  their real numbers → update `KNOWN_ISSUES.md` with the confirmed
  result. Repeat. The user is comfortable with genuinely deep,
  multi-hour tracing sessions and wants HONEST intermediate results
  (including "this made things temporarily worse, here's why, here's
  the real fix") rather than a rosier story.
- The user asked, mid-session, for a separate goal-only prompt + DMN/
  schema bundles to hand to someone else (see §5) — a one-off tangent,
  not part of the ongoing bug-fixing thread, but shows they're also
  thinking about how to communicate this work externally.

## 7. Regression-suite / verification commands (see `COMMANDS.md` for the full reference)

```powershell
cd D:\maheen\THesisCODE
& ".venv/Scripts/python.exe" generator/candidate.py
& ".venv/Scripts/python.exe" generator/mutation.py
& ".venv/Scripts/python.exe" validation_oracle/tests/test_spec_cases.py
& ".venv/Scripts/python.exe" validation_oracle/tests/test_drd_chaining_synthetic.py
& ".venv/Scripts/python.exe" validation_oracle/tests/test_serialized_field_roundtrip.py
```

Scoped search re-runs (only when the fix touched search-time code):
`generator/rerun_openmrs_only.py`, `generator/rerun_jbilling_only.py`,
`generator/rerun_flex2_only.py` (all new this session), `generator/
rerun_others_only.py` (pre-existing, Spree+FLEX2+jBilling together).

Validator re-run (per case study, after either kind of fix):
```powershell
& "./.venv/Scripts/python.exe" validation_oracle/tests/per_individual_archive_coverage.py --case-study <CS> --archive-pickle generator/experiment_runs/<CS>__dynamosa_nsga2__budget1x__seed0.pkl [--not-persisted-json <path>] --out-dir validation_oracle/tests/per_individual_out/<CS> --mode optimized
```

## 8. Where to read more

- `validation_oracle/KNOWN_ISSUES.md` — the full, chronological, detailed
  root-cause log. This session's own entries are all near the TOP (most
  recent first) — read down until you hit dates before 2026-09-26 to
  know where this session's own work starts/ends.
- `HANDOFF.md` — two new entries at the top (this session's OpenMRS+
  jBilling work, then FLEX2 work), same content as this file's §3 but in
  the project's own long-running handoff-log format/style.
- `validation_oracle/out_of_scope/pending_investigation/README.md` —
  category 4 there is the 9 jBilling rules moved out this session.
- `COMMANDS.md` — updated this session with the new scoped rerun scripts
  and the jBilling dual-override pattern.
