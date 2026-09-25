# Scope exclusions — for thesis discussion (2026-09-26)

This note exists to be cited from the paper's methodology/limitations
section. It records, precisely, which DMN-compiled rules were excluded from
the active corpus, why, and — critically — which exclusions are permanent
tooling/representation limits versus which are just not-yet-attempted
fixes. The underlying data (full compiled records) lives alongside this
file in `permanent/records.json` and `pending_investigation/records.json`;
this file is the human-readable summary for citing, not the source of
truth.

## Corpus size, before and after

| | Original | Current | Removed |
|---|---|---|---|
| Total distinct rules, all 4 case studies | 204 | 161 | 43 |
| OpenMRS | 79 | 60 | 19 |
| Spree | 31 | 22 | 9 |
| FLEX2 | 55 | 50 | 5 |
| jBilling | 39 | 29 | 10 |

(Two rounds: 39 removed 2026-09-26 morning in the initial permanent/pending
split (22 permanent + 17 pending), then 4 more OpenMRS rules moved to
`pending_investigation/` the same day after a real, distinct bug was found
tracing a per-individual verification gap -- see category 3 below. See
each folder's own README for the exact rule_id lists.)

## Two categories, one important distinction

**22 rules are permanently out of scope** — removed because the *tooling*
or the *fact itself* structurally cannot support independent database
verification, regardless of how much or what kind of test data exists:

- 20 use **COLLECT hit policy**, a DMN construct this project's independent
  oracle (`rule_evaluator.py`) never implemented (it only supports FIRST and
  UNIQUE selection). COLLECT asks "which rows violate this constraint,"
  a set-valued question, not a single-selected-rule one.
- 2 have every one of their own facts computed entirely by application code
  (`code_external`), with no schema representation of any kind — a Java
  constant, a transient UI-only value, or a runtime calculation.

**These are worth reporting as a genuine, disclosed methodological
boundary of the independent-verification approach itself**, not a gap in
this particular pipeline's implementation — a different rule-evaluation
engine that supported COLLECT, or ground-truth documentation exposing the
`code_external` facts' real computation, would be needed to close them, not
more or better test data.

**21 rules are pending investigation** — removed from the active corpus for
now (so they don't get silently recomputed against on every run), but
**explicitly not claimed as a permanent limitation**. Each fails today for
a reason this project has a known, previously-successful (or at least
previously-scoped) fix pattern, just not yet applied here:

- 9 rules (2 decisions: Spree's `Promotion Item Total Eligibility`, FLEX2's
  `Admission Closure Eligibility`) fail because no single table in the
  schema has a discoverable join path reaching every fact the decision
  needs — the same shape of gap already closed for other decisions via a
  one-line `subject_root_overrides.py`/`supplementary_fk_edges.py` entry.
- 8 rules (3 decisions, all jBilling: `Order Date Range Valid`, `Payment
  Outcome Resolution`, `Payment Balance Assignment`) fail because every one
  of their own facts is a transient runtime parameter with no persisted
  representation — the same shape of gap already partially closed for
  jBilling's own `Order Period Already Invoiced` via a disclosed
  `--not-persisted-json` override value.
- 4 rules (2 OpenMRS decisions: `Birthdate Validity::Rule_2`/`Rule_3`,
  `Numeric Precision Validity::Rule_2`/`Rule_3`) fail because
  `compile_constraints.py`'s own compiler silently drops a real, correctly
  -labeled ground-truth formula (`TIMESTAMPDIFF(YEAR, birthdate,
  CURRENT_DATE)`; `MOD(value_numeric, 1) <> 0`) and substitutes the wrong
  raw column value instead — confirmed via a full-corpus scan to be exactly
  these 2 instances, not widespread. Unlike the two categories above, no
  existing mechanism in this pipeline closes this one yet (it needs a new
  "arithmetic over sibling facts" resolution kind, not just a disclosed
  override value) — real, scoped future work, not yet started.

**If the paper reports a "coverage" or "in-scope" percentage, the honest
framing is**: of 161 currently-active rules, X were independently verified.
Separately, disclose that 22 further rules are permanently outside what an
independent database oracle can check by construction, and 21 more are
currently unattempted pending a known (if not always yet implemented) class
of fix — neither group should be silently folded into a "failed to verify"
count, since neither was ever given a fair chance to verify (the 22
structurally can't; the 21 haven't been tried).
