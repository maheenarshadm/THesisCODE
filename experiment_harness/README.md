# Experiment harness

Repeated, equal-budget comparison of DynaMOSA against two random baselines, with every run checked by the independent validator. Built 2026-09-26.

## What is compared

| Setup | What it is | Budgets |
|---|---|---|
| `dynamosa` | `generator/dynamosa.py` `run_dynamosa`: the search | 1x, 5x, 10x |
| `random_walk` | `generator/random_baseline.py` `run_random_search`: 30 lineages, each mutated at random, with no crossover and no selection | 1x, 5x, 10x |
| `random_sample` | `generator/random_sampling.py` `run_random_sampling`: every attempt is a brand-new random individual, and the best one per objective is kept | 1x, 5x, 10x |

**Budget = fitness evaluations**, where one evaluation is one `branch_fitness` call (one record scored on one individual). The search's "try this value" calls also count. Generations are never used as the budget.

**B**, the 1x budget, is fixed per case study by `calibrate`. It is the median number of evaluations the search uses at the project's usual setting of population 30 × 40 generations. Each run stops at exactly k·B evaluations, or earlier if every objective is covered.

**All three setups start from the same seed individual** (`_seed_shared_population`), and anything that seed already satisfies counts for every algorithm alike.

**Seeds:** `seed = 1000·k + rep`, so the 1x, 5x and 10x runs are independent of each other. Each run is a separate process with `PYTHONHASHSEED=0`, so any run can be reproduced exactly from its seed.

## What is measured, per run

- **Claimed coverage:** rules whose fitness reached 0 in the search.
- **Verified coverage:** rules the independent validator confirms on a real SQLite database. Each individual is materialized with exactly the same pipeline as `per_individual_archive_coverage.py --mode optimized`; the harness imports that module's functions rather than copying them.
- **Three output variants:**
  - `archive`: individuals from the archive.
  - `final`: the final population. This exists only for `dynamosa` and `random_walk`.
  - `union`: final + archive, computed as the union of the two verified sets.
- **Scope:** only in-scope rules are counted. The disclosed `not_persisted` override files are used exactly as in the manual validation commands. For jBilling, coverage is the union over its two override files.
- **Speed:** `auc_claimed_first_1x` is the area under the claimed-coverage curve over the first B evaluations, normalized to 0–1.

## Commands (PowerShell, from the repo root)

```powershell
& ".venv/Scripts/python.exe" experiment_harness/harness.py calibrate --name thesis30
& ".venv/Scripts/python.exe" experiment_harness/harness.py run --name thesis30 --reps 30 --workers 6
& ".venv/Scripts/python.exe" experiment_harness/harness.py status --name thesis30
& ".venv/Scripts/python.exe" experiment_harness/harness.py summarize --name thesis30
& ".venv/Scripts/python.exe" experiment_harness/stats.py --name thesis30
```

- **Resumable:** stop any time with Ctrl+C and run the same `run` command again. Finished runs are skipped because they carry `SEARCH_DONE` / `VALIDATED` marker files.
- **Split the work:** `--case-studies FLEX2`, `--setups dynamosa random_walk`, `--budgets 1`.
- **Search now, validate later:** `run ... --no-validate`, then `validate --name thesis30`.
- **Keep the databases:** `--keep-dbs` keeps every validated SQLite database. By default they are deleted to save disk space.

## Output: `experiment_harness/out/<name>/`

```
calibration.json   B per case study, with calibration seeds, git commit and corpus hash
config.json        this experiment's settings (and the history of earlier `run` invocations)
runs.csv           one row per run: evaluations, runtime, claimed/verified for archive/final/union, AUC
summary.csv        one row per run × output variant, in long format (what stats.py reads)
stats/             descriptive.csv, search_vs_random.csv, search_variants.csv, budget_effect.csv, per_rule.csv
<CaseStudy>/<setup>/b<k>x/rep_<ii>/
    archive/individuals.pkl   the archive individuals; also works with per_individual_archive_coverage.py --archive-pickle
    archive/verification.csv  per rule: verified?, which individual verified it first, which override file
    final/individuals.pkl     the final population (population-based setups only)
    final/verification.csv
    per_record.csv            per compiled record: archive fitness, best final-population fitness,
                              evaluation at which it was first covered, claimed/verified flags,
                              input values of the archived individual, and the rule's outputs
    per_rule.csv              per rule: claimed/verified for archive/final/union
    trace.csv                 evaluation count at which each record first reached fitness 0
    meta.json, log.txt
```

## Statistics (`stats.py`, standard library only)

| File | Comparison | Test |
|---|---|---|
| `search_vs_random.csv` | every DynaMOSA group vs every random archive group | Mann-Whitney U, Vargha-Delaney A12, Holm correction per (case study, metric); `same_budget` marks the equal-budget pairs |
| `search_variants.csv` | DynaMOSA union vs archive vs final, on the same runs | Wilcoxon signed-rank, paired by rep |
| `budget_effect.csv` | 1x vs 5x vs 10x within each setup | Mann-Whitney U, A12 |
| `per_rule.csv` | how many reps verified each rule, per group | Fisher's exact test: DynaMOSA 1x union vs each random group, Holm across rules |

**How to read A12:** A12 > 0.5 means DynaMOSA tends to score higher. The magnitude labels follow Vargha & Delaney (2000):

| Distance from 0.5 | Label |
|---|---|
| < 0.06 | negligible |
| < 0.14 | small |
| < 0.21 | medium |
| otherwise | large |

**p-values:** Mann-Whitney U and Wilcoxon use the normal approximation with tie and continuity correction, which is what R uses whenever ties are present. This was checked against reference values.
