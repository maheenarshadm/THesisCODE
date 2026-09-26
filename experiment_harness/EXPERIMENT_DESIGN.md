# Experiment design: DynaMOSA vs random search for DMN test-data generation

This document describes the design and the reasons behind each choice. How to run it is in [README.md](README.md). Written 2026-09-26.

## 1. Research questions

| | Question |
|---|---|
| **RQ1: effectiveness** | With the same budget, does DynaMOSA **verify** more DMN rules than random search? |
| **RQ2: budget** | Does DynaMOSA's advantage hold when random search gets 5× or 10× the budget? How does each approach scale with budget? |
| **RQ3: claimed vs verified** | How much of the coverage the search *claims* (fitness 0) does the independent validator confirm on a real database? |
| **RQ4: output choice** | Which output should be used as the test suite: the archive, the final population, or both? |
| **RQ5: efficiency** | How many test databases (individuals) does each approach need to reach its verified coverage? |

## 2. Subjects

Four real-world case studies, each with DMN decision tables compiled into search objectives (`generator/compiled_constraints.json`):

| Case study | Compiled objectives | In-scope rules |
|---|---|---|
| jBilling | 20 | 20 |
| Spree | 22 | 21 |
| OpenMRS | 55 | 55 |
| FLEX2 | 77 | 50 |

- An **objective** is one compiled record, one per rule or per DRD variant of a rule.
- A **rule** is a DMN decision-table row.
- Coverage is reported over **in-scope rules**, using the same scope definition as the per-case-study validation commands. A rule with several DRD variants counts once.

## 3. Algorithms

| Setup | What it does | Why it's included |
|---|---|---|
| `dynamosa` | Many-objective DynaMOSA with NSGA-II selection, crossover, fitness-guided mutation (AVM-style value search), dependency-gated objectives and an archive | The approach under evaluation |
| `random_walk` | 30 lineages, each mutated at random every generation; no fitness guidance, no crossover, no selection | Isolates the value of **guidance and selection**: it uses the same moves as the search, applied blindly |
| `random_sample` | Each attempt is a new, independent random individual; the best per objective is kept | Classic **random testing**, the standard SBSE baseline; nothing carries over between attempts |

**Why two random baselines.** They answer different questions. The random walk moves through the search space the way the search does, so the difference measures what fitness guidance and selection add. Random sampling is the textbook baseline reviewers expect. If DynaMOSA beats both, the result doesn't depend on how "random" is defined.

**Fairness, so that only the strategy differs:**
- **Same representation and repair.** All three use the same representation, moves (`candidate_values` / `apply_mutation`), repair and archive rule (keep the strictly better individual per objective).
- **Same fitness function.** The fitness function is unchanged for all three.
- **Same seed individual** (`_seed_shared_population`). Anything the constructive seed already satisfies counts for every algorithm alike, so no algorithm gets an advantage from it.
- **No domain knowledge for random.** The random baselines don't get the domain-expert value pinning (`known_constants.json`). A random process has no such knowledge, and giving it would blur the comparison.
- **Random sampling values.** Each leaf value is drawn from the search's own move menu with a random step of 1–40 around the seeded value. This is the search's own random-jump distribution, widened to include ±1. Enumerable domains and booleans are sampled uniformly.

## 4. Budget

### 4.1 Unit: fitness evaluations
One evaluation is one `branch_fitness` call, which scores one objective on one individual. The counter sits inside the fitness function, so every call counts for every algorithm, including the search's hypothetical "try this value" calls during mutation.

**Why not generations:** one generation costs very different amounts per algorithm. DynaMOSA spends thousands of evaluations per generation on value search and NSGA-II ranking. The random walk spends only 30 × objectives, and random sampling has no generations at all. Measured at equal evaluations:

| Setup | What it did at equal evaluations |
|---|---|
| DynaMOSA | ~40 generations |
| random walk | ~130 generations |
| random sampling | ~3,900 samples |

Equal generations would give random search about a third of the search's work. Fitness evaluations are the standard budget in SBSE (EvoSuite, the DynaMOSA papers), because they measure the actual work each algorithm does whatever its internal structure.

**Why not wall-clock time:** it depends on the machine, on load and on implementation speed. Runtime is recorded but not used as the budget.

### 4.2 Calibration: B
B, the 1x budget, is the **median** number of evaluations DynaMOSA uses at the project's established setting (population 30, 40 generations) over 3 calibration seeds. It is fixed per case study:

| Case study | B | seeds 0 / 1 / 2 |
|---|---|---|
| jBilling | 78,970 | 78,970 / 79,177 / 78,701 |
| Spree | 86,297 | 86,319 / 85,943 / 86,297 |
| OpenMRS | 207,920 | 207,920 / 208,003 / 207,677 |
| FLEX2 | 301,532 | 299,832 / 303,738 / 301,532 |

**Why:** B keeps the search at its tuned, established setting, about 40 generations at 1x, and only restates it in a unit every algorithm shares. The seeds agree within about 1%. Calibration records the git commit and a hash of the corpus; the harness warns if the corpus changes afterwards.

### 4.3 Budget levels: 1x, 5x, 10x
- **Every algorithm runs at every level.** Random at 5x or 10x tests whether random search catches up with the search if given more work (RQ2). DynaMOSA at 5x and 10x is needed too; otherwise "random with 10× budget vs search with 1×" can't be separated from "any algorithm improves with budget".
- **Stopping rule.** A run stops at exactly k·B evaluations, or earlier if every objective is covered. The stop happens inside the fitness call, so no algorithm overshoots its budget.

## 5. Repetitions and seeds

- **N = 10 independent repetitions** per (case study, setup, budget). That makes 4 × 3 × 3 × 10 = **360 runs**.
  - *Why 10:* it is a practical compromise, about 22 h of computation on 6 cores, against the 30 that Arcuri & Briand (2011) recommend. With n = 10, large effects like those seen in the pilot are detected reliably, but small effects may not reach significance.
  - The design **extends to 30 without redoing anything.** Seeds are fixed per repetition, so running `--reps 30` adds repetitions 10–29 and gives exactly what a 30-repetition run would have.
- **Seed rule:** `seed = 1000·k + rep`.
  - *Why distinct per budget:* with one shared seed, a 5x run would repeat its 1x run's first B evaluations exactly, so the two runs wouldn't be independent.
  - The same seed number across algorithms doesn't correlate anything, because the algorithms use their random streams differently.
- **Reproducibility.** Each run is a separate process with `PYTHONHASHSEED=0`, a seeded `random.Random` and a seeded global `random`. Re-running a run gives byte-identical results; this was verified in the pilot.

## 6. What is measured

Everything is recorded per run: every objective's fitness, input values and outputs; every rule's claimed and verified status; the individuals themselves. See README for the file layout.

| Measure | Definition | RQ |
|---|---|---|
| **Verified coverage** (headline) | In-scope rules the independent validator confirms on a real SQLite database built from the individuals | RQ1, RQ2 |
| **Claimed coverage** | In-scope rules with at least one objective at fitness 0 | RQ3 |
| **Output variants** | `archive`: best individual per objective<br>`final`: the last population (population-based setups only)<br>`union`: both together | RQ4 |
| **AUC** (`auc_claimed_first_1x`) | Area under the claimed-coverage-vs-evaluations curve over the first B evaluations, normalized to 0–1. The horizon is the same for every budget level | speed of coverage |
| **Suite size** | Number of individuals needed to reach the verified coverage: exact minimum (`--validation full`) plus greedy; a first-fit upper bound in optimized mode | RQ5 |

**Why verified coverage is the headline:** fitness 0 is the search's own claim. Earlier work on this project found real cases where claimed coverage didn't hold on the actual database (see `validation_oracle/DESIGN.md` and `KNOWN_ISSUES.md`). The validator is deliberately independent of `generator/fitness.py`.

**Why three output variants:** they are different candidate test suites. The archive keeps the best-ever individual per objective, even ones found early and later lost. The final population is what the search ends with. The union is what a user would get by keeping both. Which is best is an empirical question (RQ4), not an assumption.

## 7. Validation

- **Same pipeline as the manual runs.** Each individual is materialized with exactly the pipeline used by `validation_oracle/tests/per_individual_archive_coverage.py` (row offsets, placeholder correlation, subject-row wiring, repair, SQLite). The harness imports those functions rather than copying them, so its numbers cannot drift from the validation commands. In the pilot they reproduced the manual results exactly: Spree 21/21, jBilling 18/20.
- **Disclosed overrides.** The validator uses the same disclosed `not_persisted` override files as the manual commands. jBilling has two mutually exclusive scenarios, so its coverage is the union over both files.
- **Two validation modes:**

| Mode | What it checks | Cost | Gives |
|---|---|---|---|
| `optimized` (default) | each rule only until one individual verifies it | cheapest | coverage and a first-fit suite size (upper bound) |
| `full` | every individual (archive + final pooled, de-duplicated by content) against every rule | ~20 min per FLEX2 run | coverage, the complete individual × rule table (`matrix.csv`) and the **exact minimum suite** |

- **Both modes give the same coverage;** this was confirmed on every pilot run. `full` is needed only for RQ5.
- **Minimum suite:** an exact minimum set cover by branch and bound, after removing duplicate and dominated individuals, with greedy reported alongside. It was checked against brute force on 300 random instances. A 120 s time limit applies; if it is hit, `suite_min_optimal = False` and the best cover found is reported.

## 8. Statistical analysis

All tests are two-sided at α = 0.05, implemented with the standard library only in `stats.py`. Each was checked against reference values.

| Comparison | Test | Why this test |
|---|---|---|
| DynaMOSA groups vs random groups (RQ1, RQ2) | **Mann-Whitney U** + **Vargha-Delaney A12** | Coverage counts are discrete, bounded and often not normal, so a non-parametric test fits. A12 is the effect size recommended for randomized algorithms (Arcuri & Briand 2011) |
| 1x vs 5x vs 10x within a setup (RQ2) | Mann-Whitney U + A12 | same |
| archive vs final vs union, same runs (RQ4) | **Wilcoxon signed-rank**, paired by repetition | The three variants come from the same run, so they are paired, not independent |
| Per rule: DynaMOSA 1x vs each random group (RQ1) | **Fisher's exact test** on "verified in x of n repetitions" | Shows which rules only the search reaches; exact for small counts |
| Multiple comparisons | **Holm** correction within each family (case study × metric, or across rules) | Many comparisons per case study; Holm controls the family-wise error rate and is less conservative than Bonferroni |

- **p-values:** Mann-Whitney U and Wilcoxon use the normal approximation with tie and continuity correction. Integer coverage counts always have ties, and this is what R uses in that situation.
- **A12 magnitude labels** follow Vargha & Delaney (2000): negligible below 0.06 from 0.5, small below 0.14, medium below 0.21, large otherwise.
- **The primary comparisons** for RQ1 are the **equal-budget** pairs (`same_budget = True`).

## 9. Threats to validity

**Internal:**
- **Seed coverage is shared.** The constructive seed already satisfies some objectives for every algorithm. Absolute coverage is therefore not "from nothing", but the comparison stays fair.
- **Random sampling's value distribution is a design choice.** Values are within ±40 of the seeded value. A wider or uniform-domain distribution could do better or worse. It was chosen to match the search's own random-jump distribution.
- **Infeasible evaluations cost budget.** A fitness call that raises "not evaluable yet" still counts, for all algorithms alike.
- **B is tied to one setting.** B inherits DynaMOSA's 30 × 40 configuration. A different tuning would give a different B.

**Construct:**
- **Verification is per rule, not per DRD variant.** The validator checks whether a rule is selected on the database; it cannot say which variant the database satisfied.
- **Disclosed researcher assumptions are in effect.** These include the `not_persisted` values and some mapping and filter translations, documented in `KNOWN_ISSUES.md` and the override registries. They apply equally to every algorithm.
- **Some rules can't be verified at all.** An example is FLEX2 Summer Semester `Rule_2` (a raw-SQL input the search can't construct), which caps the maximum coverage for every algorithm alike.

**Conclusion validity:**
- **n = 10 detects large effects, but not necessarily small ones** (see §5). Normal approximations are used for the rank tests, which is standard in the presence of ties.

**External:**
- **Four case studies** with hand-curated DMN models. Results may not generalize to other domains or to rule sets mined automatically.

## 10. Execution order

- **Smallest first.** Jobs run in the order jBilling, Spree, OpenMRS, FLEX2, and by repetition within each. Complete results for the three small case studies are available (for `summarize` / `stats.py`) long before FLEX2 finishes.
- **One shared queue.** All jobs share one worker pool (`--workers 6` on an 8-core machine), so no core sits idle.
- **Resumable.** Every step can be stopped with Ctrl+C and restarted with the same command.
- **Several machines.** Machines can each run a different range of repetitions (`--first-rep`). Each part is written to its own folder, `out/<name>__from_repNN/`, and all machines use the same tracked calibration. `merge.py` combines the parts. It refuses parts with a different budget B or a different corpus, and merges a duplicated repetition only once. Because each run's seed depends only on its repetition number and budget level, which machine ran it has no effect on the results.

## References

- Arcuri, A., & Briand, L. (2011). A practical guide for using statistical tests to assess randomized algorithms in software engineering. *ICSE 2011*.
- Vargha, A., & Delaney, H. D. (2000). A critique and improvement of the CL common language effect size statistics of McGraw and Wong. *Journal of Educational and Behavioral Statistics*, 25(2).
- Panichella, A., Kifetew, F. M., & Tonella, P. (2018). Automated test case generation as a many-objective optimisation problem with dynamic selection of the targets (DynaMOSA). *IEEE TSE*, 44(2).
- Holm, S. (1979). A simple sequentially rejective multiple test procedure. *Scandinavian Journal of Statistics*, 6(2).
