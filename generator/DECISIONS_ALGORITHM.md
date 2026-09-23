# BRIDGE search algorithm — decisions register

This document is a decision-by-decision reference for the search algorithm
itself: what was decided, why, and what is still open. It is organized by
*aspect of the algorithm* (representation, crossover, mutation, selection,
archive, dataset construction), not chronologically.

`generator/README.md` is the detailed, chronological build log — the full
story of how each piece was built, the bugs found along the way, and the
evidence behind each fix. This document distills that history into the
decisions that matter for describing and defending the approach; it does
not replace README.md, and where a decision needs the full supporting
evidence, this document points at the relevant README.md section rather
than repeating it.

## 1. Chromosome / candidate representation

**Decision:** a candidate is `{table_name: [row_dict, ...]}` (the
`Candidate` class, `candidate.py`), not a fixed-length vector. Rows are
plain dicts; there is no schema awareness or validation built into
`Candidate` itself — that lives in `fitness.py`'s constraint-distance
functions and in `materialize.py`'s real SQLite validation.

**Population individual:** a `(candidate, focal_maps, scenario_maps)`
triple, not a bare `Candidate`.
- `focal_maps` is `{record_id: {table: row}}` — every objective's own
  dedicated row per table travels WITH the shared candidate through
  crossover and mutation, rather than every objective sharing whichever
  row happens to be first in the candidate.
- `scenario_maps` is `{record_id: scenario}` — every objective's own
  current bind-parameter state (for `not_persisted` inputs) travels with
  it the same way.

**Why:** early designs let every objective read the "first" row in a
shared table, which meant objectives collided on which row represented
their own test case. The focal/scenario refinement fixes this without
giving up the shared-candidate design (every objective still writes into
the same `Candidate`, so cross-objective sharing/reuse of rows is still
possible when it happens to help).

**Row ownership tagging:** every row a leaf writes is tagged with
`_OWNER_KEY` = the record_id it was written for. This is a *search-time*
mechanism for keeping one objective's own scan of a table from
accidentally reading another objective's dedicated row when both objectives
share the same candidate. It is internal to the search; see
`validation_oracle/DESIGN.md` for why it is explicitly *not* reused by the
independent coverage validator.

## 2. Initial population / seeding

`_seed_shared_population` (dynamosa.py) builds `population_size` individuals
sharing one `Candidate` structure per individual, seeded from each
objective's own placeholder/default values. Not documented further here;
see README.md's `dynamosa.py` section.

## 3. Fitness function

**Decision:** `branch_fitness` (fitness.py), `K = 1.0`,
`normalize(d) = d / (d + 1)`, combined via `_min_distance` (a
fault-tolerant min-combinator across a leaf's candidate distance
sources). `branch_fitness = normalize(distance_to_true(own)) +
Σ normalize(distance_to_false(earlier_row))` for FIRST-hit-policy
suppression of preceding rules.

**Schema/DB constraint functions** (`not_null_distance`, `unique_distance`,
`fk_distance`, `check_distance`, `candidate_constraint_fitness`) are
**self-test-only** — never part of the real search objective or the real
dataset-validation path. Real constraint validation happens once, for
real, against a live SQLite database in `materialize.py`'s
`validate_with_sqlite` — a completely separate mechanism from the fitness
function.

**Real DMN evaluation is never executed by an actual DMN engine anywhere
in this pipeline.** Hit-policy/condition semantics are reimplemented
symbolically in Python (fitness.py + `feel_parser.py`'s compiled output),
directly from the same FEEL text as the source DMN files. This is a
genuine, stated construct-validity limitation — see
`validation_oracle/DESIGN.md` for the plan to close (part of) this gap.

## 4. Crossover

**Decision:** `crossover()` (crossover.py) is called **unconditionally**,
once per sampled parent pair, every generation — there is no `if active`
guard around the call. It recombines the **entire shared candidate**:
the table set it operates over is the union of every table either parent
has rows in, and the per-table swap decision uses every `record_id`
present in either parent's `focal_maps` — not filtered to the currently
active objective set.

**Why:** crossover only recombines existing genetic material already
present in some parent — it cannot introduce anything that wasn't already
valid somewhere. Restricting it to active objectives would only reduce
the material available for the (gated) mutation operator to work with,
for no benefit. This is by design, not an oversight: mutation is the one
operator that actively steers rows toward a specific objective's
conditions, so it is the one that needs gating.

## 5. Mutation

**Decision:** mutation is the operator gated to the currently *active*
objective set (see §6). Per generation, per child:
```
if active:
    for r in rng.sample(active, min(k, len(active))):
        burst = _local_burst_size(r) if use_local_burst else 1
        for _ in range(burst):
            _mutate_objective(r, ...)
```

Three stacked refinements, each independently ablatable:

- **Multi-pick** (`mutations_per_child`, `_mutations_per_child`): each
  child attempts mutation against `k` DISTINCT active objectives per
  generation, sequentially (each pick builds on the previous pick's own
  result within the same child), not just one random pick. `k` scales
  with the active-set size:
  `max(1, ceil(len(active) / (2 * population_size)))`.
- **Local burst** (`use_local_burst`, `_local_burst_size`): each pick gets
  a *burst* of attempts proportional to that record's own leaf count, not
  exactly one — needed because a record with several independent leaves
  that must ALL align at once needs proportionally more within-record
  optimization depth to ever reach fitness 0.
- **Kick mutation** (`kick_probability`, default 0.15): with this
  probability, a picked leaf's value is replaced by an unconditional
  random jump instead of the usual greedy best-value pick — an escape
  hatch for genuine local optima under greedy single-leaf search,
  confirmed necessary via a 300-iteration single-record hillclimb that
  plateaued despite more generations. Safe at the population level: the
  archive never regresses from a kick that makes one child temporarily
  worse, and non-dominated sorting discards a kick with no compensating
  gain on its own.

**Why these three, in this order:** each was added only after directly
confirming (not assuming) that the previous fix alone left specific,
identifiable records stuck — see README.md's `dynamosa.py` section and
the mutation-budget ablation for the measured evidence.

## 6. Selection: dynamic gating, NSGA-II core, and the preference criterion

Two independently runnable files exist for this, by deliberate design —
see the "Two implementations" note below.

**Dynamic objective gating (the "Dyna" mechanism):**
`active = records if not dynamic_gating else [r for r in records if
is_active(r, covered_keys)]`. An objective is active once every branch
its own `grounded_upstream_branches` lists is already covered in the
archive. When `dynamic_gating=False`, every objective is active from
generation 1 — functionally equivalent to MOSA (DynaMOSA's direct
predecessor) over the identical representation/archive/NSGA-II core, used
as this project's own RQ2 ablation baseline.

Two things depend on `active`: mutation targeting/budget (§5), and the
fitness-vector dimensionality fed to selection (below). Two things do
NOT: crossover (§4, always global) and the archive (§7, always updated
for every record every generation, regardless of activation — this is
what lets an objective get covered "by accident" before it's ever
targeted).

**NSGA-II core** (`fast_non_dominated_sort`, `crowding_distance`):
standard, unmodified non-dominated sorting and crowding-distance
truncation, applied to `fitness_vectors = [[evaluate_objective(r, ind)
for r in active] for ind in combined]` — the vector's dimensionality is
whatever `active` currently is, so it grows generation over generation as
DRD gates open.

**Two implementations, kept separate on purpose:**
- `dynamosa.py` (`run_dynamosa`) — dynamic gating + plain NSGA-II
  selection. No preference criterion. This was the project's only
  selection mechanism until this session.
- `dynamosa_preference.py` (`run_dynamosa_preference`) — identical in
  every other respect, but selection also applies DynaMOSA's own
  **preference criterion** (Panichella et al.): before ordinary
  non-dominated sorting runs, for each active objective, whichever
  individual(s) achieve the single best fitness on *that one objective*
  are guaranteed into front 0. Only individuals not already claimed by
  this preference front go through ordinary non-dominated sorting for the
  remaining fronts.

**Why two files instead of one flag:** built this way specifically so
both selection mechanisms stay independently runnable and directly
comparable — an explicit ablation axis (RQ3 in the experiment design),
not a silent behavior change to the existing algorithm. Literature
confirms the preference criterion is "the main difference of MOSA
compared to NSGA-II" — i.e. `dynamosa.py` alone, honestly, implements
"NSGA-II with a DRD-dependency-gated, dynamically-scoped objective set,"
not full canonical DynaMOSA; `dynamosa_preference.py` is the
literature-faithful version.

**Measured result so far (single seed, all 4 case studies):** on 3 of 4
case studies (FLEX2, OpenMRS, jBilling) the two are statistically
indistinguishable at this sample size — identical convergence generation,
near-identical or exactly identical AUC. On Spree, they diverge: the
preference criterion converges almost immediately (generation 1) but
plateaus at lower final coverage (21/26); plain NSGA-II-style selection
converges slower (generation 11) but reaches higher final coverage
(22/26) and higher AUC. **Not yet a defensible claim either direction —
single seed, small corpus. See DECISIONS_EXPERIMENT.md's open issues.**

## 7. Archive

**Decision:** `archive[record_id] = (best_fitness_ever_found,
individual_that_achieved_it)`, updated for **every** record, every
generation, for every individual in the population *and* every offspring
— regardless of whether that record is currently in the active set. Never
regresses (`if f < archive[rid][0]`).

**Why unconditional:** this is what lets an objective get covered "by
accident" — e.g. via crossover recombination, or another objective's
mutation touching a shared row — even before it is ever specifically
targeted by mutation. Restricting archive updates to active objectives
would silently lose real coverage.

## 8. Final dataset construction: final-population vs. merged archive

Two strategies exist, both real, both independently computable from a
single search run's raw output (archive + final population) with no
re-running of the search:

- **Final-population strategy:** the single best individual in the last
  generation (highest per-individual coverage count via `_covered_set`).
  A real, self-consistent, already-buildable candidate.
- **Merged-archive strategy** (`merge_archive_candidate`): merges every
  covered objective's own best-ever archived row into ONE candidate,
  applying a per-objective key offset to every row's own PK/UNIQUE/FK
  columns to avoid cross-objective collisions, then **re-verifies** the
  merge for real (a merge can regress a previously-true objective — see
  the OpenMRS finding below) rather than trusting the archive's own claim
  blindly.

**Measured result:** final-population-alone is far below archive
coverage everywhere (10–28 objectives covered vs. 35–98 in the archive,
across the 20-run first experiment batch). Merged-archive recovers
essentially all of archive's coverage on FLEX2, Spree, and jBilling —
exact match in every algorithm/budget configuration tested. **OpenMRS is
the one exception:** a reproducible, exactly-one-objective regression
(`Preferred Identifier Requirement::Rule_2`) on every single OpenMRS run
regardless of algorithm.

**Root cause, confirmed directly (not guessed):** this objective's
`identifierCount = 1` condition is compiled as a literal equality check
against the raw `patient_identifier.patient_id` column value — not a real
COUNT aggregate. The archived individual satisfied it by setting
`patient_id = 1`. The merge step's (legitimate, necessary) per-objective
key-offset renumbering shifted `patient_id` to `35000001` to avoid a real
PK collision with other objectives' own rows — which broke the literal
`= 1` comparison, even though the underlying real-world semantics
(exactly one `patient_identifier` row for that patient) likely still
holds. This is a genuine, new category of limitation: a compile-time
translation style ("count" compiled onto a literal-value comparison
against a key column) that is not safe under merge-time key
renumbering — distinct from the previously-documented "same physical row,
two roles" and "missing count/intersection evaluator" limitation
categories.

## 9. Stopping condition

Fixed generation count (no early-stopping-on-full-coverage implemented).
`population_size=30, generations=40` is this project's own established
default (matches the prior mutation-budget-scaling ablation), used again
for the first full experiment batch this session.

## Open issues

- The Spree preference-criterion divergence (§6) is not yet confirmed as
  a real effect vs. single-seed noise.
- The OpenMRS merge regression (§8) is root-caused but not fixed — no
  decision has been made yet on whether/how to fix the underlying
  compile-time translation style, or simply document it as a known
  limitation.
- No preference-criterion variant exists that also fixes the OpenMRS-style
  regression; the two are orthogonal.
- `dynamosa.py`'s own docstring calls its `dynamic_gating=False` mode
  "functionally equivalent to MOSA" — worth double-checking this framing
  stays accurate now that `dynamosa_preference.py` exists as the more
  literature-faithful DynaMOSA, so as not to overload what "MOSA" vs
  "DynaMOSA" means across the two files when writing the paper.
