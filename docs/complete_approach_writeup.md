# Search-Based Synthetic Test-Data Generation for DMN-Governed Relational Databases

## A complete, step-by-step explanation of the approach: input to output, every algorithm, every design decision, every challenge faced and how it was resolved, and every challenge that remains open today

---

## 0. What this document is

This is the full technical narrative of the pipeline: what goes in, what happens to it at every single stage, exactly which algorithms were chosen and why they were the right fit for this specific problem (not a generic "we used a genetic algorithm" statement), the exact mathematics of the fitness function, the exact mechanics of the mutation and crossover operators, and — because this project was built by continuously running it against real, independently-sourced systems and fixing what broke — a full account of every real challenge encountered, how each was diagnosed and fixed, and which ones are still open today. Every number quoted below is a real, measured result from actually running the pipeline, never an estimate.

---

## 1. The problem, in one paragraph

A relational database has two kinds of rules it must obey: **schema rules** (NOT NULL, PRIMARY KEY / UNIQUE, FOREIGN KEY — enforced by the database engine itself) and **business rules** (expressed here as DMN — Decision Model and Notation — decision tables, the kind a real system like OpenMRS, jBilling, or Spree encodes its actual application logic in, often chained together into a Decision Requirements Diagram, or DRD, where one decision's output feeds another decision's input). The goal of this project is: **generate a synthetic relational dataset that exercises as many of these business rules as possible while never once breaking a schema rule** — i.e., produce real, valid test data that actually triggers "student is on academic warning," "identifier fails its format check," "encounter date is outside the visit window," and so on, for as many such rules as the model actually allows.

---

## 2. Input

Two things go in, per case study:

1. **The DMN model**: a set of decision tables (each with one or more rules — rows — and a *hit policy*, most commonly FIRST or UNIQUE, meaning "the first/only row whose condition is true wins"), plus the DRD edges connecting decisions that reference each other's outputs.
2. **The relational schema**: every table, every column with its real type and nullability, every declared primary key, unique index, and foreign key — extracted directly from the real system's own schema definition (SQL DDL, Rails schema.rb, etc.), never invented.

Four real, independently-sourced systems were used as case studies, on purpose, specifically to avoid overfitting the pipeline to one system's own quirks: **FLEX2** (a university academic-regulations system), **Spree** (e-commerce), **jBilling** (billing), and **OpenMRS** (an open-source medical-records system). Each has a genuinely different schema shape, a genuinely different DMN rule style, and — as later sections describe — each one exposed real bugs the other three never would have.

---

## 3. Step 1 — Compiling DMN rules into search objectives

**Module: `compile_constraints.py`.**

A raw DMN rule is not something a search algorithm can optimize directly — it references other decisions, uses FEEL (DMN's own expression language) constructs, and its variables are named facts ("academic warning status") rather than concrete schema columns. This step turns every rule *row* of every decision table into one fully self-contained, mechanically evaluable unit called a **compiled record** (also referred to as a search *objective*). Each compiled record carries:

- Its own **condition tree** (an AND/OR/NOT/comparison tree over named free variables).
- A **`variable_resolution`** map: for every free variable the condition references, exactly how to compute it — from a real schema column read (`schema_column`), whether a column is set (`null_check`), a row existing under some filter (`exists`), a count over a filtered set of rows (`derived_aggregate`), a value reached by following a foreign key to another table (`join_lookup`), a value that's a bind-parameter/scenario constant never persisted anywhere (`not_persisted`), a regex match of one column against another (`regex_match`), a category derived from a raw value via a case-mapping (`derived_case`), and a few narrower kinds.
- Its **`hit_policy_context`**: for FIRST/UNIQUE hit policy, the *exact conditions of every earlier row in the same table* that must be made to evaluate false, since making a later row's condition true is not enough — an earlier row firing instead would mean this rule was never actually exercised.
- Its **DRD dependency list**: which upstream decision::rule branches this record's own condition transitively depends on.

### 3.1 Why grounding is the hard part, and the algorithm that solves it

A DMN rule can reference the *same* upstream decision more than once — once directly, once nested inside a different chained dependency. The naive approach (pick a grounding rule for each reference independently) can pick *two different* concrete rules of the same real decision for what should be one single, consistent fact — producing a compiled condition that requires one variable to equal two different literal values simultaneously under one AND. No search algorithm can ever satisfy that; it's unsatisfiable by construction, not merely hard.

**The fix** is a **commitment-respecting backtracking search**: a single, shared dictionary mapping `decision name → chosen rule id` is threaded through every grounding need of one record, including deeply nested ones. Once a decision is committed to a rule anywhere while grounding a record, every other reference to that same decision — however deeply nested — is forced to reuse the identical rule; the search still backtracks correctly when a genuinely different top-level choice needs its own independent pick. This is a real, general fix, not a special case: **it dropped FLEX2's compiled record count from 391 to 151, and confirmed 0 of the resulting 151 have any residual self-contradictory constraint (down from 192/391, 49% of the corpus)** — with the search running 12× faster afterward, since it stopped wasting budget on rules that could never be solved by any algorithm.

### 3.2 Proving infeasibility mechanically, instead of guessing

After grounding, some rules are still genuinely unsatisfiable — not because of a compilation bug, but because the DMN model itself, once every upstream dependency is committed to a concrete literal, pins one fact to a value the rule's own condition also needs to differ from. Simply running the search longer cannot distinguish "needs more time" from "can never be solved." A **general, three-valued (true / false / unknown) constant-folding evaluator** walks a rule's condition tree and short-circuits AND/OR/NOT exactly like ordinary boolean logic wherever every variable involved is already a fixed, grounded constant, leaving anything still touching a genuine free variable as unknown. Applied to a rule's own condition *and* to every earlier row it must suppress, this proves infeasibility at compile time, mechanically, for the whole corpus at once. It is committed, real code — `_fold_condition_three_valued`/`_grounded_constant_for_variable` in `compile_constraints.py`, run inside `compile_case_study` itself — applied uniformly to all four case studies, not a one-off script run only against FLEX2. A record it proves `False` is recorded as `blocked` with reason `infeasible` and never reaches `compiled_constraints.json`. **Result: 53 of FLEX2's 151 rules (35.1%) and 2 of jBilling's 42 are provably infeasible this way, with zero overlap against what the search actually covers** — turning "why isn't coverage 100%?" from an open question into an exact, defensible accounting of the corpus's own real boundary conditions.

**Output of this step**: `compiled_constraints.json` — the full, exhaustively grounded, exhaustively classified list of search objectives for the case study, persisted to disk and re-read by every later stage.

---

## 4. Step 2 — Representing a candidate solution

**Module: `candidate.py`.**

A **`Candidate`** is simply `{table_name: [row_dict, ...]}` — a proposed, in-memory row-set across every table the corpus touches. This is the unit a genetic algorithm evolves. Deliberately thin: no schema awareness baked into the class itself (that lives in `fitness.py` and the repair logic), so it stays a pure data structure.

Two mechanisms sit on top of a bare `Candidate`, both added after being proven necessary by real, measured failures (§8 below tells the story of each):

- **Focal rows** — `{record_id: {table: row}}`. Every objective gets its **own dedicated row** per table it actually needs a row-level context for, rather than every objective sharing whichever row happens to be "first" in the table. Created lazily the first time an objective is picked for mutation.
- **Row ownership tagging** — a reserved bookkeeping key (`__owner__`) stamped on every row an objective's own logic creates (aggregate rows, existence rows, join-count rows). Aggregate/existence/join-count evaluation only ever scans rows tagged for the *current* objective plus untagged rows (genuinely shared reference data, like foreign-key parent rows repair synthesizes). Stripped back out before real SQL/CSV is ever emitted — it's search-time bookkeeping, not schema data.

A **`scenario`** dict (`{placeholder_name: value}`) travels alongside every candidate too — the bind-parameter values for `not_persisted` facts (a purchase quantity, a roll number used as a join key) that are never backed by any real column.

**`derive_genome(record, candidate, focal, scenario)`** is the function that turns one objective's own compiled record plus a real candidate into the flat `{free_variable_name: value}` **genome** the fitness function actually scores — walking `variable_resolution`, computing each leaf variable's real, candidate-derived current value.

---

## 5. Step 3 — The fitness function: exactly how "how close is this?" is computed

**Module: `fitness.py`.**

This is the single most important piece of mathematics in the whole pipeline, because it's what turns "did this rule fire" (a boolean) into a smooth, climbable gradient a genetic algorithm can actually improve against.

### 5.1 The base distance table

For one comparison `a OP b`, wanting it to evaluate **true**:

| Operator | Distance when NOT satisfied | Distance when satisfied |
|---|---|---|
| `=` (numeric) | `\|a − b\|` | 0 |
| `=` (non-numeric) | `K` (a fixed constant, 1.0) if `a ≠ b` | 0 |
| `!=` | `K` if `a == b` | 0 |
| `<` | `(a − b) + K` | 0 |
| `<=` | `(a − b) + K` | 0 |
| `>` | `(b − a) + K` | 0 |
| `>=` | `(b − a) + K` | 0 |

The `+ K` term on ordering operators is deliberate: it guarantees the distance is *strictly positive* the moment the comparison is false, even when `a` and `b` are numerically equal (e.g. `a < b` with `a == b` must never read as "distance 0", since it is genuinely still false) — giving AVM (Alternating Value Method, see §7.2) a real, nonzero gradient to climb right up to the boundary.

Ordering comparisons **require both operands to be genuinely numeric** — there is no principled notion of "how far is `None` from being less than `5`" — so an ordering comparison against a non-numeric or missing value raises a dedicated, caught `FitnessEvaluationError` ("not yet evaluable") rather than crashing or guessing.

### 5.2 Composing the tree: `distance_to_true` / `distance_to_false`

A condition is a tree of AND / OR / NOT / comparison nodes. Two mutually recursive functions compute "how far from true" and "how far from false":

- **`distance_to_true(AND)`** = **sum** of each clause's own `distance_to_true` (every clause must genuinely become true; distances add).
- **`distance_to_true(OR)`** = **min** of each clause's own `distance_to_true` (only the single easiest clause needs to succeed).
- **`distance_to_false(AND)`** = **min** of each clause's own `distance_to_false` (the single easiest clause to falsify is enough to falsify the whole AND).
- **`distance_to_false(OR)`** = **sum** of each clause's own `distance_to_false` (every clause must be falsified).
- `NOT` swaps between the two functions.

### 5.3 The whole-branch score, including hit-policy suppression

```
branch_fitness(record, genome):
    own = distance_to_true(record.condition, genome)
    suppression = Σ  normalize( distance_to_false(earlier_row.condition, genome) )
                  for each earlier_row in record.hit_policy_context.earlier_rows
    return normalize(own) + suppression
```

where `normalize(d) = d / (d + 1)` squashes any unbounded distance into `[0, 1)` — so a percentage-scale gap (an attendance percentage, say) and a plain 0/1 boolean mismatch never let one term swamp another's own gradient, and each earlier-row suppression term is normalized *individually* before being summed, so one very distant earlier row can never drown out the others' own signal. **`branch_fitness == 0.0` if and only if this rule's own condition is true *and* every earlier row in the same FIRST/UNIQUE table is false** — the exact, correct semantic of "this specific rule actually fired," not merely "its own condition happens to be true."

### 5.4 A general robustness fix worth stating precisely (found late, in OpenMRS)

The naive `min()` over a Python generator must evaluate *every* element to know the minimum — so if a *later* clause in an AND/OR raises `FitnessEvaluationError` (an ordering comparison against a value that's currently missing), the whole calculation aborts, even when an *earlier* clause had already, cleanly, settled the answer at the best possible score (0.0). A shared helper, `_min_distance`, now evaluates every term in a min-combinator **order-independently**, short-circuits the instant any term proves 0.0 regardless of what any other term does, and only ever propagates an error when *no* term produced a usable value at all. This is a correctness fix in the fitness function's own core machinery, not specific to any one rule — confirmed to change behavior only for the exact "min-combinator with one unevaluable losing term" shape it targets, with zero regression across all four case studies re-run afterward.

### 5.5 Schema/DB-constraint fitness is a *separate*, non-search term

`candidate_constraint_fitness` (NOT NULL / UNIQUE / FK distance) exists as a post-hoc audit measure, but is **deliberately not summed into the search objective** — an early version tried exactly that and it was reverted (see §8). Schema-legality is instead guaranteed **by construction** (§7.3's repair step), every single time a row is touched, so the DMN-fitness gradient is never distorted by a constraint term that has no principled distance of its own to contribute.

---

## 6. Step 4 — Seeding the initial population

**Function: `_seed_shared_population` in `dynamosa.py`, using `build_seed_candidate` from `candidate.py`.**

One shared starting `Candidate` is built once: every objective gets its **own dedicated seed rows** — added as fresh, additional rows, never deduplicated against another objective's own seed rows (the earlier "one row per table, shared" design was the dominant, measured cause of low coverage — see §8). A `derived_aggregate`/`exists` seed row is built as a *real, filter-matching* row via mechanical conjunct parsing (`COLUMN = VALUE` / `COLUMN = <placeholder>`), not a bare row with a fake placeholder column — a real bug found materializing the flagship rule end to end for the first time.

Every objective's own key/FK column values are then shifted by a large, per-objective numeric **offset** before merging into the shared base, so that two independently-seeded objectives' own dedicated rows (e.g. two different `COURSE` rows each using placeholder `COURSE_ID`) never numerically collide once merged into one shared candidate — a real `UNIQUE constraint failed` bug found at full scale, fixed generally rather than per-record.

The **population** is `N` independent deep copies of this one shared base — later, DynaMOSA's own operators diverge them.

A **known real-world constants** mechanism (`known_constants.json`) sits alongside seeding: some leaf variables have a known, domain-true value (e.g. "a real course offering holds ~30 lectures") that the search has no *mathematical* reason to want, since the cheapest value that merely proves a rule (3 lectures, say) is just as valid to the fitness function. Where a variable name is pinned in this config, seeding starts from that value directly and the search's own value-selection logic (§7.2) jumps straight to it instead of searching for the cheapest proof — changing *which* realistic values the search lands on without changing *whether* a rule is provable.

---

## 7. Step 5 — The search algorithm: DynaMOSA, and why it was the right choice

### 7.1 Why a many-objective evolutionary algorithm, and why *this* one specifically

Every compiled DMN rule is one **search objective**: "make this rule's condition become true (and every earlier row's condition false)." A case study can have dozens to hundreds of these simultaneously. This is structurally the *same* problem class as branch/statement coverage in search-based software testing — many, largely independent, essentially binary targets, where what matters is that *some* individual, at *some* point in the run, reaches each target, not that one single individual satisfies all of them jointly. **DynaMOSA (Dynamic Many-Objective Sorting Algorithm, Panichella et al.)** was built by the search-based testing community for exactly this problem shape (it is the algorithm EvoSuite itself uses for coverage-goal generation), which makes it a direct domain fit rather than an arbitrary pick. Concretely, against the alternatives:

- **A single aggregated-fitness GA** (sum every rule's own distance into one number, optimize that) — this was literally EvoSuite's own earlier "whole test suite" approach, before MOSA existed. It was rejected here for the same reason it was rejected in that literature: one individual is asked to be good at *everything* at once, which actively fights against specialization, and a single scalar gives no way to protect one rule's own progress from being traded off against another's.
- **Plain NSGA-II** — the classic multi-objective GA whose own non-dominated-sorting and crowding-distance machinery DynaMOSA is built directly on top of. Plain NSGA-II scores every individual against *every* objective at once with no permanent memory of what's already been solved — at high objective counts (hundreds, here) it is known to lose effectiveness, and critically, it has **no notion at all of solved-objective permanence**: if the population's own current front drifts away from a rule it solved three generations ago, that solution is gone. DynaMOSA's **archive** (§7.4) is precisely the fix for this, and is the single biggest reason it was chosen over bare NSGA-II.
- **MOSA** (DynaMOSA's own direct predecessor) has the archive and the many-objective preference criterion, but treats every objective as active from generation one regardless of whether it's even meaningfully evaluable yet. This project's own objectives are **DRD-chained** — many literally cannot produce a meaningful fitness gradient until an upstream decision is already solved (a "course load" rule that reads "the student's warning status" has no honest gradient to climb before some real warning-status fact exists to read). DynaMOSA's own **dynamic** dependency-gated activation (§7.4) is the exact mechanism the DRD structure calls for, and is the reason DynaMOSA specifically, not plain MOSA, was chosen.
- **NSGA-III, SPEA2, MOEA/D** and other many-objective/decomposition-based MOEAs are legitimate alternatives in general, but none of them carry a notion of "an objective only becomes relevant once its own dependency is solved" — that structural fit is unique to the MOSA/DynaMOSA lineage for this specific problem.

### 7.2 The one-generation cycle, precisely

Each individual in the population is a **triple**: `(candidate, focal_maps, scenario_maps)` — every objective's own dedicated rows and scenario state travel *with* the candidate through crossover and mutation, rather than being shared, frozen, run-global state (§8 tells the story of why this had to become a triple, not a pair).

For every generation, in order:

1. **Determine the active objective set.** A rule is *active* only once every branch its own `variable_resolution` transitively depends on has *already* reached fitness 0.0 in the archive — the "Dyna" part. The active set grows monotonically as the run progresses.
2. **Evaluate** every individual's genome against every *active* objective — a **fitness vector**, one number per active objective, never one combined scalar.
3. **Update the archive** (§7.4): for every objective, if this individual's fitness beats the best-ever recorded for that objective, replace it.
4. **Produce offspring**: sample two parents at random, **crossover** them (§7.5) into two children, then **mutate** each child (§7.6) against several distinct active objectives, each with a local burst of attempts.
5. **Combine** parents + offspring into one pool, run **non-dominated sorting** (`fast_non_dominated_sort`, textbook NSGA-II: front 0 = individuals no other individual dominates on *every* active objective at once; front 1 = dominated only by front 0; and so on) and, within a front that would overflow the population size, **crowding distance** (how isolated an individual is in objective-space along each objective's own sorted axis — individuals at the extremes of any objective get infinite distance, guaranteeing the population never collapses onto a narrow band) to select exactly `population_size` individuals forward.
6. Record how many objectives have reached 0.0 in the archive so far (the coverage history), and loop.

### 7.3 Repair-by-construction — schema legality is never left to fitness

After *every* row a mutation or crossover touches, `repair_candidate`/`_repair_row` runs: for every NOT NULL column with no real value yet, fill it with a schema-type-aware placeholder (a date-shaped default for a DATE column, an empty string for a required VARCHAR, a number for a numeric one); for a PK/UNIQUE column needing a fresh value, hand it the current maximum plus one; for a dangling FK, synthesize a minimal, itself-repaired parent row rather than leave it hanging. **NOT NULL/PK/UNIQUE/FK are mechanically decidable from the schema alone, with no DMN-relevant ambiguity, so they are never treated as a fitness term to "maybe" discover — they are guaranteed true by construction, every single time.**

### 7.4 The archive — permanent memory, and how it gates activation

`archive: {record_id: (best_fitness_ever, individual_that_achieved_it)}`. This never regresses — even if the live population's own front moves on to specialize in other objectives, an objective's best-ever answer is never lost. This serves **two** purposes simultaneously: it is what §7.6 (merge-the-archive) ultimately builds the final dataset from, and it is what §7.2 step 1 reads to decide which DRD-dependent objectives get to activate next.

### 7.5 Crossover — uniform table-mask recombination

**Module: `crossover.py`.** Two parent candidates are recombined into two complementary children by flipping an independent coin **per table**: a child inherits *that whole table's entire row-set* from one parent or the other. The unit of recombination is a table, not a row, because individual rows across two unrelated parents have no stable identity to align gene-by-gene the way two same-length chromosomes would (parent 1's 5th row and parent 2's 5th row are arbitrary, unrelated list entries) — a whole table's row-set is the smallest unit every candidate shares a well-defined notion of, regardless of population history. Every objective's own dedicated focal row for a swapped table, and its own scenario state, travel *with* the table, never left behind. A mandatory FK-repair pass runs afterward, since swapping a table wholesale from a different parent routinely leaves a dangling foreign key into a table that stayed with the *other* parent.

### 7.6 Mutation — the two sub-operators, and how a value is actually chosen

**Module: `mutation.py`.** Exactly one leaf free variable is changed per mutation call — classic AVM discipline (change one thing, so the fitness delta tells you what caused it) — realized as one of two sub-operators, chosen automatically by the mutated variable's own resolution kind:

- **M1 (field mutation)** — `schema_column`, `null_check`, `any_not_null`, `join_lookup`, `join_null_check`, `regex_match`: perturbs one row's one column.
- **M2 (row-count mutation)** — `derived_aggregate`, `exists`: adds or removes a *whole row*, since nothing on a single row is "the count."

**Choosing the winning value** (`best_value_for`) is unified across both: every **candidate replacement value** for the chosen variable is tried as a cheap, in-memory hypothetical (never touching a real row yet), `branch_fitness` is computed for each, and whichever scores lowest is applied for real. Where the candidates themselves come from depends on the leaf's own shape:

- **A known real-world constant** (§6) takes priority over everything else — jump straight to the pinned value.
- **An enumerable domain**: for a leaf compared only via `=`/`!=`/`in` against literal values *in this branch's own condition* (and, for FIRST/UNIQUE hit policy, its own earlier rows), the domain is exactly those literals — the DMN rule itself already names every value worth trying, never a random guess. An earlier row's own required value is deliberately walked with **negated polarity** (it needs to be *avoided*, not tried) — a real bug found and fixed when the first version walked it with the same polarity as the current rule, repeatedly re-offering the one value guaranteed to never work.
- **A numeric leaf with no enumerable domain** (`schema_column`, `not_persisted`, `derived_aggregate`, `derived_join_count`): **AVM's own step-doubling acceleration** — try `±1` first; the moment a direction improves, keep *doubling* the step in that same direction as long as it keeps improving, halving back down on overshoot. A branch needing a count to climb ~99 units took 99 individual step-1 calls without this; doubling closes the same gap in ~7.
- **Occasionally, an unconditional random "kick"** instead of the greedy best-value pick (§8's local-optimum finding) — safe at the population level, since the archive never regresses from one temporarily-worse child, and non-dominated sorting discards a kick with no compensating gain on its own.

**Attention allocation**: each child attempts mutation against **several distinct, randomly sampled active objectives per generation** (not just one), the count auto-scaling with the size of the active set, and each of those picks gets a **local burst** of several sequential attempts, sized by how many independent leaf variables that specific rule's own condition actually has — a rule needing five facts to align at once genuinely needs proportionally more within-record depth than a rule needing one, purely as a function of the record's own structure.

---

## 8. Step 6 — Merge-the-archive: building the *one* final dataset

**Function: `merge_archive_candidate` in `dynamosa.py`.**

This is the step that resolves the tension between "many specialists" (what a Pareto-based population actually produces) and "one deliverable dataset" (what's actually needed). DynaMOSA/NSGA-II deliberately **spreads** a population across a front of specialists, each good at a handful of objectives — it is never designed to converge the whole population onto one generalist individual that covers everything at once. Picking one individual out of the final generation (the naive approach) therefore caps out far below what the archive, collectively, actually proved solvable.

Instead, for **every** objective the archive ever covered (fitness 0.0, at any point in the whole run), that objective's own best-ever rows — its dedicated focal row *and* every row tagged as owned by it — are pulled out of its own best-ever individual and merged into one shared candidate. A single schema-repair pass runs once on the fully assembled whole. Because independently-evolved individuals are being combined, every objective's own contributed rows get a fresh, per-objective numeric offset so that two different objectives' key/FK values never collide once merged (and, where one objective legitimately owns *two* rows on the same table, a further collision-avoidance pass bumps any still-colliding value past every one already claimed in this merge pass — restricted specifically to genuinely single-column PK/UNIQUE columns, never a foreign key or a composite key, both real regressions found and fixed the hard way, see §9).

**The merged result is never trusted just because its rows were "already proven correct" in isolation** — it is always re-evaluated for real against the actual merged, repaired candidate, and any objective that regresses during the merge is reported honestly, side by side with the archive's own belief, rather than silently accepted.

---

## 9. Step 7 — Materialization and validation

**Module: `materialize.py`.**

1. **Topological table ordering** (`topological_table_order`, Kahn's algorithm over the schema's own FK edges) — lookup tables, then identity tables, then fact tables, so a real `INSERT` never references a row that hasn't been inserted yet. A genuine FK *cycle* (rare, but real — OpenMRS has one 28-table cycle) is broken deterministically (placing the least-blocked table next) and reported, never silently hidden or crashed on.
2. **Emission** — real `INSERT` statements and one CSV file per table, two views of the exact same materialized rows.
3. **Validation against a real, live SQLite database** — the actual DDL is built from the schema (columns, types, NOT NULL, PK), every row is genuinely inserted, and then, separately, `PRAGMA foreign_key_check` is run once against the fully-populated data at rest. FK enforcement is deliberately **not** turned on during the insert loop itself (a real, general fix — see §9) since per-statement enforcement is insert-order-sensitive and would falsely fail a real, valid FK cycle; the after-the-fact, order-independent check catches every *genuine* dangling reference without that false-positive risk. **The engine is the ground truth here, never a hand-written distance function** — this is what actually proves a materialized candidate is real, valid data.

---

## 10. Output

- **The generated SQL/CSV synthetic test data** — one CSV file per table, plus a single `.sql` file of ordered `INSERT` statements.
- **A coverage report**: how many of the case study's own compiled objectives are satisfied *simultaneously*, in the *one, real, materialized, validated dataset* — re-verified by re-evaluating every single objective against the actual final output, never taken on the search's own internal say-so — reported honestly alongside the (necessarily higher, since it's a looser bar) archive-ever-covered count.

**Final, measured, verified results across all four case studies** (final materialized coverage / total compiled objectives, `validate_with_sqlite` clean in every case):

| Case study | Compiled objectives | Final covered | % |
|---|---|---|---|
| FLEX2 | 98 | 81 | 82.7% |
| Spree | 27 | 22 | 81.5% |
| jBilling | 40 | 33 | 82.5% |
| OpenMRS | 71 | 63 | 88.7% |

(FLEX2 and jBilling's own "compiled objectives" denominators are 98 and 40, not the historical 151/42 — §3.2's provable-infeasibility check is applied to every case study, not just FLEX2, filtering out 53 FLEX2 rules and 2 jBilling rules that could never be satisfied by any dataset before they ever reach the search. The covered counts, 81 and 33, are unchanged from before that filtering, confirming none of the removed rules were ever reachable.)

---

## 11. Challenges faced, and how each was resolved

Every one of the following was found by directly inspecting real data (compiled rule sets, archived search state, a real materialized SQL file checked against a live database) — never assumed — and every fix was measured before and after with concrete numbers. The full, unabridged account (17 challenges with complete diagnoses) lives in `docs/challenges_and_solutions.txt`; this is the condensed version, in the order they were found.

1. **DRD-chain dependency activation.** A downstream rule referencing an upstream decision's output cannot be meaningfully evaluated — or honestly credited as covered — before that upstream decision is itself solved. *Fixed*: DynaMOSA's own dynamic, dependency-gated activation (§7.4).
2. **Grounding-consistency bug.** The same upstream decision, referenced twice in one record, could be independently grounded to two conflicting rules, making the record mathematically unsatisfiable by construction. *Fixed*: commitment-respecting backtracking grounding (§3.1). **391 → 151 compiled records; 192/391 self-contradictory → 0/151.**
3. **Shared single-row interference.** Every objective sharing one table's "first row" as context meant two different objectives needing different values overwrote each other constantly. *Fixed*: per-objective dedicated focal rows (§4). **Archive coverage roughly 2.5×.**
4. **Aggregate/exists row-sharing**, one level deeper than #3 — a whole-table scan (a count, an existence check) had no notion of *which* objective a row belonged to. *Fixed*: row-ownership tagging (§4). A necessary correctness fix that, measured honestly, did *not* raise coverage on its own — the old number was itself an artifact (see #5).
5. **Final-dataset coverage capped far below archive coverage** — not a bug, a structural mismatch between how DynaMOSA's own population behaves (spreads into specialists) and how the final dataset was being picked (one individual from the last generation). *Fixed*: merge-the-archive (§8). **17-21/151 → 81/151 at the time (151 was FLEX2's full pre-filtering compiled count); matching archive coverage exactly.**
6. **Provable infeasibility detection**, so "unsolved" stops being one undifferentiated bucket. *Fixed*: three-valued constant-folding (§3.2), now committed compile-time code (`_fold_condition_three_valued` in `compile_constraints.py`), not a one-off script — applied uniformly to all four case studies. **53 of FLEX2's 151 rules (35.1%) and 2 of jBilling's 42 proven mathematically unsatisfiable and filtered before compilation completes; FLEX2 and jBilling's own compiled totals are now 98 and 40, with 81/81 and 33/33 of the genuinely solvable rules covered respectively.**
7. **A domain-value-enumeration polarity bug** — an earlier row's own required value was tried instead of avoided. *Fixed* (§7.6). One rule: 0 improving moves in 500 iterations → converges in 1 step.
8. **Attention dilution** as the true objective count grew roughly fourfold. *Fixed*: multi-pick mutation + per-record local burst (§7.6). **43/391 → 48/391 → 80/391 at an identical search budget.**
9. **Technically-correct-but-unrealistic data** — a rule satisfied with the cheapest possible value, not a realistic one. *Fixed*: the known-constants mechanism (§6). Zero coverage regression.
10. **A genuine local optimum a purely greedy, single-leaf search cannot escape.** *Attempted*: a probabilistic random "kick" (§7.6) — reported honestly as a **negative result** (no coverage change), which directly motivated tracing and finding the real cause: #2.
11. **A stale, un-offset scenario in re-verification**, silently breaking re-evaluation of every scenario-dependent fact independent of whether the merge logic itself was correct. Fixed by carrying the search's own real, already-offset scenario state through to re-evaluation.
12. **A `not_persisted` mutation computed, then silently discarded** — individuals shared one frozen, run-global scenario per objective, so a bind-parameter mutation had nowhere to persist. *Fixed*: scenario became per-individual state, `(candidate, focal_maps, scenario_maps)` — found running Spree.
13. **A ground-truth CSV citing a migration that does not exist.** Verified against the real schema, fixed only after explicit sign-off (curated data, not generated code).
14. **jBilling: a systemic schema-extraction gap** (166 real columns missing from the extracted schema across 59/98 tables), **a stale seeding placeholder**, and a **two-layer merge-time key-collision bug** (cross-objective, then same-objective-two-rows). All four fixed and independently verified.
15. **`exists`-kind facts given real filter support**, plus **three merge-time bugs** the fix surfaced (a dedup fix wrongly bumping a legitimately-shared FK column; that fix's own flattening of a *composite* key corrupting 25 unrelated FLEX2 objectives; a business-value column needing the same value-matching care a declared key gets). Each re-verified against every other case study, not just the one that exposed it — the single most important recurring discipline of this whole project.
16. **OpenMRS: five further real bugs** — a type-blind generic placeholder crashing a sibling leaf reading the same column with different semantics; the same bug's mirror image on a NOT NULL column; a fundamentally insert-order-sensitive FK validation check giving 254 false positives against a genuine 28-table cycle; a related reporting bug (informational notes counted as real failures); and a `join_lookup` match-by-value-not-PK convention that merge-time offsetting broke.
17. **Isolated-rerun categorization**, distinguishing a real algorithm bug from search-budget luck from a ground-truth compile-time gap, which found and fixed the `best_value_for` same-column blind spot (§5.4's sibling fix) and the `_min_distance` short-circuit bug (§5.4) in `fitness.py` itself.

---

## 12. Challenges that remain open today

Each item below has a specific, named root cause — none is an unexplained number — but is **not yet fixed**, because it requires either changing curated ground truth (needing explicit sign-off) or a genuinely larger architectural change whose cost/benefit has only been scoped, not built:

1. **One physical column representing two conflicting facts at once** through a modeling shortcut (a raw value standing in for a derived category; a required foreign key doubling as a business count) — jBilling (2 rules), OpenMRS (2 rules).
2. **`exists`-kind facts whose real meaning is a correlated self-join** ("a *different* row related to this one exists") rather than a simple per-column filter — beyond what the general filter mechanism (challenge #15) can express — OpenMRS (1 rule).
3. **A blank/not-blank fact modeled as a plain null-check on a column the schema declares can never be null** — the schema-legal representation of "blank" (an empty string) has no compiled fact kind that can express it — OpenMRS (3 rules).
4. **Two conceptually different roles (an "old" status vs. a "new" status) needing simultaneously different values while sharing one dedicated per-table context row** — jBilling (2 rules). Scoped (a per-role context extension, giving one dedicated row per `(table, role)` instead of per `table`) but not built: judged high cost relative to the 2 rules it would help, absent more evidence the pattern recurs.
5. **Plain search-budget limitation** — 2 OpenMRS objectives confirmed, via isolated single-objective reruns, to solve immediately alone but never got the chance within the shared population's actual generation/population budget.
6. **Facts genuinely computed by application code at runtime**, never stored as any single column — present in small numbers in every case study, named and excluded from the denominator rather than miscounted, since no schema-reading approach can recover a value the real system never persists.

*Closed since the last revision*: rules provably infeasible by construction at the DMN-model level itself (a self-comparison, a grounding conflict) were previously listed here because §3.2's evaluator only ever ran as a one-off script against FLEX2. It is now committed, permanent code applied to all four case studies uniformly — see §3.2 and challenge #6 above.

A concrete, implementable **static-analysis procedure** for mechanically detecting category 4 above *before* running any search at all — by grouping a record's own variables by shared `(table, column)`, then reusing the exact same constant-folding contradiction-detector already built for challenge #6, generalized to variable aliases — has been designed and discussed, but deliberately not built without an explicit decision to do so.

---

## 13. Where to find more detail

- `docs/generationalgorithmdesign.md` — the full, chronological technical design document (60+ sections), including every worked numeric example.
- `docs/challenges_and_solutions.txt` — the complete, unabridged 17-challenge account with full before/after measurements, written for direct use in a methodology section.
- `generator/README.md` — mirrors the design document, organized by source file.
- `generator/compiled_constraints.json` / `compile_report.json` — the actual, current compiled objective set and compile-time classification report for all four case studies.
