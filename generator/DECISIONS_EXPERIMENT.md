# Evaluation / experiment design — decisions register

Companion to `DECISIONS_ALGORITHM.md`. This document covers decisions
about *how the approach is being evaluated* — research questions,
algorithms compared, metrics, what has actually been run, and what is
still open. It does not cover the validation-oracle/verified-coverage
work, which is a separate, not-yet-implemented concern documented in
`validation_oracle/DESIGN.md`.

## Research questions

Four RQs, each mapped to one axis of the experiment design, each with a
direct precedent in the DynaMOSA/MOSA literature (Panichella et al.):

- **RQ1 — Effectiveness vs. random search.** Does guided many-objective
  search (NSGA2-style / DynaMOSA) achieve higher rule coverage than
  random search, even when random search gets more generations (2x, 5x)?
- **RQ2 — Convergence speed.** At what generation does each algorithm
  first reach its own final coverage? Same axis as the DynaMOSA paper's
  own RQ2 ("how algorithms perform over time"), not just endpoint
  coverage.
- **RQ3 — Contribution of the preference criterion.** Does
  `dynamosa_preference.py`'s preference criterion improve coverage or
  convergence speed over `dynamosa.py`'s plain dynamically-gated NSGA-II
  selection? Directly isolates the one mechanism the two files differ on
  (see `DECISIONS_ALGORITHM.md` §6).
- **RQ4 — Dataset construction strategy.** Does merging archive + final
  population beat either alone? Matches the field's own whole-suite (WS)
  vs. whole-suite-with-archive (WSA) vs. MOSA/DynaMOSA distinction,
  applied here to final-dataset assembly instead of test-suite assembly.

## Algorithms compared

1. **Random search** (`random_baseline.py`, `run_random_search`) — same
   representation, fitness function, repair discipline, and (by default)
   dependency gating as the guided search; picks values uniformly at
   random from the same candidate-value menu instead of by fitness; no
   crossover; no NSGA-II selection (independent lineages random-walk
   forward). Deliberately omits `known_constants.json` pinning.
2. **NSGA2-style dynamic-gated DynaMOSA** (`dynamosa.py`).
3. **True DynaMOSA with preference criterion** (`dynamosa_preference.py`).

## Case studies

FLEX2, OpenMRS, Spree, jBilling — all four, every experiment run to
date.

## Fixed configuration

`population_size=30`, base `generations=40` — matches this project's own
prior ablation convention (the mutation-budget-scaling ablation run
earlier in this project's history), chosen for direct comparability with
that prior work rather than re-tuned per case study.

## Random search budget multipliers

1x, 2x, 5x the guided algorithms' own base generation count (so 40, 80,
200 generations respectively). Rationale: tests whether guided search's
advantage is real guidance, not random search simply needing more time —
directly what RQ1 asks.

## Seeds

**Currently N=1 (seed=0) per configuration.** This is an explicit,
disclosed scope decision, not an oversight: it matches how this
project's prior ablations were run (single-seed, demonstrative), and
keeps the first full batch fast (~7 minutes for all 20 cells) while the
data-persistence infrastructure (below) was being built and verified.
**Open issue:** a proper statistical comparison needs more repetitions
(the field's own convention is often ~30 runs per cell, reported as
median/IQR); N=10 was proposed as a next step and has not yet been run.
Expanding `SEEDS` in `run_experiments.py` is the only change needed —
the harness was built to make this trivial.

## Metrics

- **Final coverage** — `covered/total`, computed from whichever of the
  three coverage notions is being reported (see "coverage notions"
  below).
- **Convergence generation** — first generation at which an algorithm's
  own coverage-over-generations curve reaches its own eventual final
  value. Always reported *alongside* final coverage, never alone — a
  poor algorithm reaching only 40% quickly is not "more efficient" than
  one reaching 95% more slowly.
- **AUC** — normalized area under the coverage-over-generations curve
  (`mean(coverage_at_gen / total)` across all logged generations).
  Specifically added to distinguish "same final coverage, different
  speed" cases that convergence-generation alone can hide or that final
  coverage alone cannot show — e.g. the Spree DynaMOSA-preference-vs-NSGA2
  case, where convergence generation and final coverage tell two
  different, both-true stories (see `DECISIONS_ALGORITHM.md` §6).
- **Generational vs. evaluation-count vs. wall-clock efficiency** — three
  distinct notions, not yet all logged (see open issues). Runtime
  (wall-clock) is logged per run; candidate/fitness evaluation counts are
  not, since capturing them would require instrumenting
  `dynamosa.py`/`dynamosa_preference.py`/`random_baseline.py` internals,
  which was explicitly out of scope for the first data-persistence pass
  ("not in the other structures").

## Coverage notions — three, not one, and this matters

Established directly this session, from real measurement, not assumption:

1. **Archive coverage** — the loosest: any individual, at any point in
   the whole run, ever reached fitness 0 for that objective. This is what
   `run_experiments.py`'s `final_covered` field and `coverage_history`
   report.
2. **Final-population coverage** — one real, self-consistent candidate
   (the single best individual in the last generation).
3. **Merged-archive coverage** — one real, self-consistent candidate
   (every objective's own best-ever archived row merged together,
   re-verified after repair).

All coverage numbers reported in this project to date (until this
distinction was raised) were **archive coverage only**. The three-way
breakdown (`analyze_dataset_strategies.py`) is a separate, later analysis
pass, computed from the *same already-saved raw runs* with no
re-execution of the search — this is precisely why raw archive + final
population are persisted per run (see below).

## Data persistence design

**Decision:** every experimental run persists its raw `archive` and
`final_population` (the actual `Candidate`/`focal_maps`/`scenario_maps`
objects, pickled, not a coverage summary of them) plus the
generation-by-generation `coverage_history`, to
`generator/experiment_runs/`, via `run_experiments.py`.

**Why:** so that a later change to how "coverage" is defined or verified
— including the entire verified-rule-coverage validation pipeline being
designed in `validation_oracle/` — never requires re-running the search
itself. This was an explicit, direct instruction, not an assumption:
"save the outputs... so that if we go about using a different coverage
mechanism... we can use it later on." `analyze_dataset_strategies.py`
already demonstrates the payoff — the final-population/merged-archive
breakdown above was computed entirely from already-saved pickles.

**Scope boundary, also explicit:** this pass touches nothing in
`dynamosa.py`, `dynamosa_preference.py`, `random_baseline.py`,
`fitness.py`, or `compile_constraints.py` — those are called exactly as
they already exist. `run_experiments.py` and `analyze_dataset_strategies.py`
only call and persist/analyze.

## Results obtained so far (first full batch, N=1, seed=0)

| Case | DynaMOSA (pref.) | NSGA2-style | Random 1x | Random 2x | Random 5x |
|---|---|---|---|---|---|
| FLEX2 (98 total) | 98 | 98 | 59 | 68 | 81 |
| OpenMRS (71 total) | 64 | 64 | 56 | 56 | 56 |
| Spree (26 total) | 21 | 22 | 14 | 14 | 15 |
| jBilling (40 total) | 35 | 35 | 32 | 33 | 34 |

(Archive coverage. See `generator/experiment_runs/runs_index.json` for
full per-run metadata including coverage-history, and
`dataset_strategy_analysis.json` for the final-population/merged-archive
breakdown.)

## Open issues

- **N=1 only.** Every result above is single-seed. Nothing here is
  statistically defensible yet — the Spree preference-criterion
  divergence in particular could be pure seed noise.
- **Evaluation-count and per-generation wall-clock granularity** are not
  logged — only total run runtime. A reviewer asking "does one DynaMOSA
  generation cost the same as one random-search generation?" cannot yet
  be answered from saved data alone.
- **The OpenMRS merge regression** (see `DECISIONS_ALGORITHM.md` §8) is
  root-caused but not yet reflected in any experiment-design decision —
  e.g. whether to report merged-archive coverage net of known regressions,
  or investigate/fix the underlying compile-time translation issue first.
- **Coverage as currently measured (archive, or final-population, or
  merged-archive) is still "search coverage," not independently verified
  rule coverage** — the circularity concern that motivated
  `validation_oracle/`. None of the numbers above have been re-validated
  against a fresh, independent re-evaluation of the original DMN model.
