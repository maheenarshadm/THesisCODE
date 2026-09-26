"""dynamosa.py -- the DynaMOSA population loop (design doc §6.4's settled
algorithm-of-record): one shared population per case study, every
compiled branch is one objective, DRD-gated dynamic objective
activation, non-dominated sorting.

**Focal-per-objective (2026-09-12, replacing the earlier "first row per
table" scope decision)**: real DynaMOSA (and this design doc's own §6.4)
evolves ONE shared row-set where different rows serve as the "focal"
context for different branches at once (a student's own attendance
covers one branch, another student's course registration covers
another, in the SAME candidate). The first version of this module took a
deliberate, smaller scope instead -- every objective's focal row for a
table was always that table's *first* row in the candidate -- which
stayed implementable and testable, but a real, measured diagnostic on
the full FLEX2 case study found this was the DOMINANT cause of low
coverage: 58 of 83 uncovered branches (~70%) failed outright with a
missing-column `FitnessEvaluationError`, because different objectives
needing different columns/values on the very same physical row
overwrote each other. This module now gives every objective its OWN
dedicated row per table it needs a focal row for (never another
objective's), created lazily the first time that objective is actually
picked for mutation (`_focal_for_mutate`), and looked up read-only,
never created, during fitness evaluation (`_focal_for_read` -- called far
more often, once per objective per individual per generation, so it must
never itself grow the candidate). Individuals are therefore no longer
bare `Candidate` objects but `(candidate, focal_maps)` pairs, where
`focal_maps` is `{record_id: {table: row}}` -- see `_focal_for_read`/
`_focal_for_mutate`/`_mutate_objective`'s own docstrings for the exact
mechanics, and `crossover.py`'s own `focal_maps1`/`focal_maps2`
parameters (added alongside this) for how a table swap during crossover
carries every objective's own dedicated row for that table along with
it, not just one record's.

Not every table a record's own resolution mentions gets a dedicated
focal row -- only the ones a leaf kind actually *reads through* a focal
row at all (`_focal_tables_for_leaf`): `derived_aggregate`/`exists`/
`derived_join_count` kinds scan `candidate.rows(table)` directly, across
the WHOLE shared candidate, and never consult focal -- handing them a
fresh, empty dedicated row would be actively wrong for an unconditional
`derived_aggregate` (an empty row can trivially match a filter with no
real conjuncts, silently inflating the count by one for a row that
carries no real data at all).

**Aggregate row-sharing fix (2026-09-13)**: the uneven table-sharing
above WAS, until this fix, a real, measured cause of a large gap between
archive coverage (how many objectives were EVER covered by SOME
individual across the whole run, 81/151 on FLEX2) and final-dataset
coverage (how many are covered SIMULTANEOUSLY by the ONE candidate
`generate_dataset.py` actually materializes, stuck at exactly 20/151
regardless of rng seed) -- confirmed directly by producing and
inspecting a real `.sql` file, not assumed. Different objectives sharing
an aggregate-relevant table counted/interfered with each other's rows
the moment they were merged into one final candidate: objective A's own
carefully-tuned three matching rows for its `derived_aggregate` could be
outnumbered, diluted, or accidentally satisfied by objective B's own
unrelated rows in the very same table, and vice versa. Fixed via row
ownership tagging: every row this module creates (seed rows in
`_seed_shared_population`, focal rows in `_focal_for_mutate`, and
mutation-added/removed rows in `mutation.py`'s own
`_apply_row_count_mutation`) is stamped with a reserved `_OWNER_KEY`
('__owner__') naming the objective (`record_id`) that owns it;
`derive_value`'s own aggregate/exists/join-count branches (candidate.py)
now scan only rows owned by the CURRENT objective plus untagged rows
(`_owned_rows`) -- untagged rows stay globally visible, which is
exactly right for genuinely shared reference data (e.g. FK-repair
-synthesized parent rows, added once wholesale after every objective's
own seed rows are in, never tagged). `owner_id` defaults to `None`
everywhere outside this module, so every single-objective caller
(`mutate()`/`hillclimb()`/`solve_branch()`, every existing self-test)
is completely unaffected -- the filtering is opt-in, activated only by
DynaMOSA's own population loop, which is the only caller that actually
shares one candidate across many concurrently-active objectives.
`materialize.py` strips `_OWNER_KEY` from every emitted column before
writing real SQL/CSV, since it is bookkeeping, not schema data.

**Per-individual scenario (2026-09-13) -- fixing a real, previously-
flagged-but-unaddressed bug**: a `not_persisted` leaf (a `<placeholder>`
bind-parameter, e.g. `purchaseQuantity`, never a real row/column) is
resolved through `scenario`, not `focal`. Until this fix, EVERY
individual in the population shared the exact SAME scenario dict per
objective (`scenario_cache: {record_id: scenario}`, built once,
read-only from then on) -- `_mutate_objective`'s own mutation of a
`not_persisted` variable was computed and applied to a throwaway COPY of
that scenario, then silently discarded the moment the function returned,
since nothing captured or persisted it anywhere. Confirmed directly
running this pipeline against Spree for the first time (2026-09-13,
after §13.42-13.44's fixes): `Price List Volume Adjustment Tier
Selection::Rule_2`/`Rule_3` both need `purchaseQuantity` to move away
from its seeded value to ever reach fitness 0.0, and both stayed stuck
at a fixed, non-zero residual for the ENTIRE run -- inspecting
`scenario_cache` directly after a full 40-generation run showed
`purchaseQuantity` still sitting at its raw, unmutated per-objective
seed offset, exactly as `build_seed_candidate` first set it, proving the
mutation never once actually stuck. `mutate()`/`hillclimb()`'s own
single-objective path (used by `search.py`'s own escalation loop) never
had this bug -- it already threads `new_scenario` through correctly
(`mutate()` returns it, the caller persists it into the next
generation's own population entry) -- the bug was specific to this
module's own `_mutate_objective`, which reimplements `mutate()`'s
control flow but had never carried scenario along the same way it
already carries `focal_maps`.

Fixed by giving scenario the same per-individual treatment focal_maps
already has: an individual is now a `(candidate, focal_maps,
scenario_maps)` TRIPLE, `scenario_maps: {record_id: scenario}` -- one
scenario dict per objective, per individual, evolving independently
exactly like each objective's own dedicated focal rows already do.
`_seed_shared_population` seeds one shared BASE `scenario_maps` (built
once, offset per objective exactly as before) and deep-copies it into
every initial population member, same as it already does for
`base_focal_maps`; `_mutate_objective` now deep-copies `(candidate,
focal_maps, scenario_maps)` jointly and returns the updated triple,
so a `not_persisted` mutation that improves fitness can now actually
survive into the next generation via ordinary NSGA-II selection, the
same way a row mutation already does. `crossover()`'s own new
`scenario_maps1`/`scenario_maps2` parameters do NOT recombine scenario
by the table mask at all -- a `not_persisted` variable belongs entirely
to one record, never shared/aliased across tables or records the way a
row can be, so each child simply inherits its own originating parent's
scenario_maps wholesale, deep-copied, unmodified by which parent
supplied which table. `run_dynamosa` no longer returns a separate
`scenario_cache` -- it is now redundant: every individual (and every
archived one) already carries its own current scenario state, so
`evaluate_objective`/`merge_archive_candidate`/`generate_dataset.py`
read scenario directly off the individual/archive entry itself instead
of a separately-threaded, run-global cache.

**Reused, not reimplemented**: `mutate()`'s own building blocks --
`best_value_for`/`apply_mutation`/`_leaf_variables` (this module's own
`_mutate_objective` reimplements `mutate()`'s own control flow rather
than calling it directly, since `mutate()`'s own `copy.deepcopy((candidate,
focal))` only ever covers ONE record's own single `focal` dict -- calling
it as-is here would silently break the aliasing between `candidate`'s
rows and every OTHER objective's own focal entries still sitting in the
same individual's `focal_maps`) -- `crossover()` (extended, not
reimplemented, with the new `focal_maps1`/`focal_maps2` parameters),
`repair_candidate`/`_repair_row` (schema-legal-by-construction),
`build_seed_candidate` (per-record placeholder seeding, used once per
objective to build that objective's own dedicated seed rows),
`branch_fitness`/`derive_genome` (unchanged). `compile_constraints.py`'s
own `collect_tables_from_resolution` (the earlier design's "every table
this record's resolution mentions at all" walk) is no longer used here --
`_focal_tables_for_leaf`/`_focal_table_set_for` replace it with a
narrower, focal-specific walk (see above).

**DRD-gated activation**: each compiled record already carries its own
`grounded_upstream_branches` -- the exact list of `"decision::rule_id"`
branches its own condition depends on (populated by compile_constraints.py
from the DRD `informationRequirement` edges it walked at compile time,
not re-derived here). An objective is active once every branch it names
has been *covered* (fitness 0.0) by some individual across the whole
run's own archive -- not the current population, since DynaMOSA's own
archive of best-per-objective solutions only grows, never regresses.

**Non-dominated sorting**: a standard NSGA-II fast-non-dominated-sort +
crowding distance, computed only over currently-active objectives (the
"Dyna" part of DynaMOSA: objectives outside the active set exert zero
selection pressure at all, per §6.4's own framing).

Usage:
    from dynamosa import run_dynamosa
    archive, coverage_history, population = run_dynamosa(
        records, case_study, population_size=20, generations=50)
"""
import copy
import math
import os
import random
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from candidate import (Candidate, derive_genome, build_seed_candidate,  # noqa: E402
                        _OWNER_KEY, known_constant, _PLACEHOLDER_RE,
                        _SIMPLE_EQ_CONJUNCT_RE, _BARE_TABLE_DOT_COLUMN_RE)
from fitness import branch_fitness, FitnessEvaluationError, _unique_key_sets  # noqa: E402
from mutation import (repair_candidate, best_value_for, apply_mutation,  # noqa: E402
                       _leaf_variables, _schema_for, candidate_values, _fresh_key_value)
from crossover import crossover  # noqa: E402


def _focal_tables_for_leaf(node):
    """The specific table(s) THIS leaf node's own kind actually reads
    through a *focal* row (see candidate.py's derive_value) -- a strict
    subset of "every table this record's resolution mentions at all"
    (`compile_constraints.py`'s own `collect_tables_from_resolution`,
    used by the earlier "first row per table" design). `derived_aggregate`/
    `exists`/`raw_sql_boolean` kinds scan `candidate.rows(table)` directly
    across the WHOLE shared candidate and never consult focal at all --
    deliberately excluded here (see this module's own docstring on why
    handing them a dedicated-but-empty row would be actively wrong, not
    just unnecessary). `join_lookup`/`join_null_check`'s own
    `result_table` is likewise excluded: it's found by a primary-key scan
    over the whole candidate (`_find_row_by_pk`), never through focal --
    only `local_table` (the row that supplies the join key) is read
    through focal."""
    kind = node.get('kind')
    if kind in ('schema_column', 'null_check', 'derived_case'):
        return {node['table']}
    if kind == 'any_not_null':
        return {c['table'] for c in node.get('columns', [])}
    if kind in ('join_lookup', 'join_null_check'):
        return {node['via']['local_table']}
    if kind == 'regex_match':
        return {node['value_column']['table'], node['pattern_column']['table']}
    if kind == 'derived_join_count':
        return {node['registration_table']}
    return set()


def _focal_table_set_for(record):
    """Every table SOME leaf of this record's own condition reads through
    a focal row -- recurses through substituted_decision chains exactly
    like `_leaf_variables`'s own walk (a leaf nested inside a
    substituted_decision's own free_variable_resolutions isn't a
    top-level key of record['variable_resolution'] either)."""
    tables = set()

    def walk(node):
        if not isinstance(node, dict):
            return
        if node.get('kind') == 'substituted_decision':
            for sub in node.get('free_variable_resolutions', {}).values():
                walk(sub)
            return
        tables.update(_focal_tables_for_leaf(node))

    for node in record.get('variable_resolution', {}).values():
        walk(node)
    return tables


def _focal_for_read(record, focal_maps):
    """Read-only lookup of this objective's own dedicated focal row per
    table -- NEVER any other objective's, the actual fix for this
    module's earlier "first row per table" scope decision -- and NEVER
    creates a row (row creation is `_focal_for_mutate`'s job alone,
    triggered only when this objective is actually picked for mutation;
    this function is called once per objective per individual per
    generation during fitness evaluation, far more often than mutation
    attempts, so it must stay strictly read-only).

    A table this objective hasn't been given its own dedicated row for
    yet is simply omitted from the returned dict -- exactly like the
    original design's own behavior when a table had zero rows at all:
    `derive_value`'s lookup-based kinds (`_lookup(focal, table, column)`)
    raise `FitnessEvaluationError` naturally for a table genuinely
    missing from focal (an honest "not yet evaluable", never silently
    borrowing some OTHER objective's own row instead), while
    `derived_aggregate`/`exists` kinds never consult focal in the first
    place and are unaffected either way."""
    return dict(focal_maps.get(record['record_id'], {}))


def _focal_for_mutate(record, candidate, focal_maps, table_cache):
    """Like `_focal_for_read`, but creates (via `candidate.add_row`) a
    brand-new, empty dedicated row the FIRST time this objective needs
    one for a given table, recording it in
    `focal_maps[record_id][table]` for all future reuse -- both future
    mutation attempts and read-only evaluation from then on. Only called
    once this objective has actually been chosen to mutate this
    generation (never during fitness evaluation itself), so row creation
    stays bounded by mutation attempts, not by the much larger number of
    fitness evaluations NSGA-II's own sorting performs every generation."""
    tables = table_cache.get(record['record_id'])
    if tables is None:
        tables = _focal_table_set_for(record)
        table_cache[record['record_id']] = tables
    rec_focal = focal_maps.setdefault(record['record_id'], {})
    focal = {}
    for t in tables:
        tU = t.upper()
        row = rec_focal.get(tU)
        if row is None:
            # Tagged with this objective's own record_id even though
            # nothing looks this row up by scanning the table (focal rows
            # are found by direct dict reference, never by
            # `_owned_rows`'s own scan) -- the aggregate row-sharing fix
            # (2026-09-13, candidate.py's `_owned_rows`) needs this row to
            # stay invisible to some OTHER record's `derived_aggregate`/
            # `exists` scan of the SAME physical table, which is exactly
            # the cross-objective interference this tag exists to
            # prevent; an untagged focal row would otherwise silently
            # count towards another objective's aggregate the moment both
            # happen to touch the same table.
            row = candidate.add_row(t, {_OWNER_KEY: record['record_id']})
            rec_focal[tU] = row
        focal[tU] = row
    return focal


def evaluate_objective(record, candidate, focal_maps, scenario_maps, table_cache):
    """`scenario_maps` is the individual's own `{record_id: scenario}`
    (2026-09-13's per-individual scenario fix, see this module's own
    docstring) -- this objective's own current scenario is looked up by
    `record_id` here, exactly like `_focal_for_read` already looks up
    this objective's own focal rows from `focal_maps`, rather than a
    caller pre-extracting one record's own scenario before calling."""
    try:
        focal = _focal_for_read(record, focal_maps)
        scenario = scenario_maps.get(record['record_id'], {})
        genome = derive_genome(record, candidate, focal, scenario, owner_id=record['record_id'])
        return branch_fitness(record, genome)
    except FitnessEvaluationError:
        return float('inf')  # not yet evaluable against this individual -- never "covered"


_KICK_PROBABILITY = 0.15  # a modest diversification rate -- see _kick_value_for's own docstring


def _kick_value_for(record, var_name, node, current, case_study, rng):
    """An UNCONDITIONAL, non-greedy jump for one leaf -- the escape hatch
    for a real, confirmed structural limitation of coordinate-descent
    search (found and verified directly 2026-09-12, not assumed): a
    substantial share of the corpus's stuck-at-a-hard-floor objectives
    (`Course Registration Eligibility`'s own composite-leaf records,
    dominant among the 292 "active with finite residual" records at the
    post-composite-leaf-fix plateau) turned out to be GENUINE local
    optima under single-leaf greedy search, not merely slow-converging --
    confirmed by running a single-record `hillclimb()` with a generous
    300-iteration budget directly against one of them: it stalled after
    only 3 accepted moves at a stable, non-zero `branch_fitness`, with
    the SAME leaf-by-leaf greedy logic every other leaf pick in that
    budget failing to improve at all. This is coordinate descent's own
    textbook failure mode: several leaves need to move TOGETHER for the
    branch's own AND-composed condition to ever reach 0, but a step that
    only ever accepts a single leaf's OWN strictly-improving move can
    never discover a joint change where moving leaf A alone (holding B
    fixed) doesn't help, and vice versa -- no matter how many
    generations or how large the population.

    Reuses `candidate_values` (the exact same value-generation logic
    `best_value_for` itself calls), but with a large, randomized step
    (not just ±1) and picks one of the returned candidates uniformly at
    random rather than the best-scoring one -- a real, if temporarily
    fitness-worsening, perturbation, not a hill-climb step. Safe to
    apply unconditionally at the population level: DynaMOSA's own
    archive discipline never regresses (a kick that makes one child
    worse simply never overwrites a better archived answer), and
    non-dominated sorting will naturally discard an offspring a kick
    made strictly worse with no compensating gain -- the same safety
    property that makes "occasional large mutation" a standard, accepted
    diversification move in population-based search generally."""
    big_step = rng.randint(2, 40)
    options = candidate_values(record, var_name, node, current, case_study, step=big_step)
    return rng.choice(options) if options else None


def _mutate_objective(record, candidate, focal_maps, scenario_maps, table_cache, rng=None,
                       kick_probability=_KICK_PROBABILITY):
    """The population loop's own variation step for a single objective --
    reimplements mutation.py's own `mutate()` control flow (pick a random
    leaf variable, find its best replacement value via `best_value_for`,
    apply it via M1/M2) rather than calling `mutate()` directly, because
    `mutate()`'s own `copy.deepcopy((candidate, focal))` only ever covers
    ONE record's own single `focal` dict -- calling it as-is from here
    would silently break the aliasing between `candidate`'s rows and
    every OTHER objective's own focal entries still sitting in this same
    individual's `focal_maps` (the exact class of bug crossover.py's own
    `focal_maps1`/`focal_maps2` extension was built to avoid, applied
    here too). `candidate`/`focal_maps`/`scenario_maps` are only ever
    replaced together, in one joint deepcopy, never touched in place --
    parents are never mutated, the same discipline `mutate()` itself
    follows.

    Returns (new_candidate, new_focal_maps, new_scenario_maps, improved).
    `scenario_maps` is this individual's own `{record_id: scenario}`
    (2026-09-13's per-individual scenario fix -- see this module's own
    docstring for the real bug it fixes: a `not_persisted` mutation used
    to be applied to a throwaway scenario copy that was silently
    discarded the moment this function returned, so a variable like
    `purchaseQuantity` could never actually move away from its seeded
    value across the whole run, no matter how many generations). This
    objective's own current scenario is now looked up from, and written
    back into, `scenario_maps[record_id]` -- exactly the same "one entry
    per objective, deep-copied jointly with everything else" treatment
    `focal_maps` already had, so a `not_persisted` mutation that improves
    fitness now actually survives into the next generation via ordinary
    NSGA-II selection, the same way a row mutation already does.

    Both the initial genome computation AND `best_value_for` itself are
    wrapped in one try/except, exactly the same real crash `mutate()`'s
    own former direct use in this module's population loop was already
    found to need guarding against (2026-09-12) -- `best_value_for`'s own
    first call is `branch_fitness(record, genome)`, itself unguarded
    internally, since `mutate()` never wrapped it either (this module's
    population loop always wrapped the WHOLE `mutate()` call from
    outside instead). A freshly-created, still-empty dedicated row
    (`_focal_for_mutate` seeds it with `{}`, not real values) can leave
    some OTHER leaf of this same record (e.g. a `chained_decision_output`
    fact this branch's own suppression term depends on, or
    `derived_join_count`'s own context-row search) genuinely
    unresolvable against the current candidate even though the record
    itself compiles fine -- an honest "not evaluable yet," not a bug to
    crash on.

    `kick_probability` (see `_kick_value_for`'s own docstring): with this
    probability, the picked leaf's value is replaced by an UNCONDITIONAL
    random jump instead of `best_value_for`'s own greedy best-value pick
    -- the escape hatch for genuine local optima a purely greedy search
    can never climb out of on its own. Applies uniformly to every
    record/leaf, never targeted at any specific decision -- EXCEPT a
    leaf pinned to a known real-world constant (`known_constants.json`,
    2026-09-13), which always goes through `best_value_for` instead
    (whose own pin-check snaps it straight to that constant): kicking a
    pinned variable would randomly perturb it away from the one value a
    domain expert said it should always carry (e.g.
    `lecturesHeldForOffering`, which should read 30 in every generated
    row, never some large randomized jump `_kick_value_for`'s own
    exploration step would otherwise produce)."""
    rng = rng or random
    rid = record['record_id']
    scenario = scenario_maps.get(rid, {})
    focal = _focal_for_mutate(record, candidate, focal_maps, table_cache)
    try:
        genome = derive_genome(record, candidate, focal, scenario, owner_id=rid)
        leaves = [(v, n) for v, n in _leaf_variables(record) if v in genome]
        if not leaves:
            return candidate, focal_maps, scenario_maps, False
        var_name, node = rng.choice(leaves)
        pinned = known_constant(record['case_study'], var_name)
        if pinned is None and rng.random() < kick_probability:
            value = _kick_value_for(record, var_name, node, genome.get(var_name), record['case_study'], rng)
            if value is None:
                return candidate, focal_maps, scenario_maps, False
        else:
            value, _best_fitness, improved = best_value_for(record, genome, var_name, node, record['case_study'])
            if not improved:
                return candidate, focal_maps, scenario_maps, False
    except FitnessEvaluationError:
        return candidate, focal_maps, scenario_maps, False

    new_candidate, new_focal_maps, new_scenario_maps = copy.deepcopy((candidate, focal_maps, scenario_maps))
    new_focal = new_focal_maps[rid]
    new_scenario = new_scenario_maps.setdefault(rid, {})
    try:
        apply_mutation(record, new_candidate, new_focal, new_scenario, var_name, node, value, genome.get(var_name),
                        owner_id=rid)
    except FitnessEvaluationError:
        return candidate, focal_maps, scenario_maps, False
    return new_candidate, new_focal_maps, new_scenario_maps, True


_LOCAL_BURST_CAP = 8  # bounds worst-case cost for a record with an unusually large leaf count


def _local_burst_size(record):
    """How many sequential `_mutate_objective` attempts a single pick of
    `record` gets, within one child, before moving on to the next pick --
    driven purely by how many leaf variables THIS record's own condition
    has (`_leaf_variables`), never by which decision or record it is (a
    real, measured coverage bottleneck found 2026-09-12: composite
    records needing an aggregate count, a category mapping, a join-based
    count, an upstream-chained literal, AND a plain column comparison to
    ALL align simultaneously -- five independent leaves -- dominated the
    remaining uncovered FLEX2 objectives, ~285 of them sharing that exact
    five-kind shape). Every pick used to get exactly ONE mutation
    attempt regardless of how many leaves the record actually has to
    move -- systematically under-serving a multi-leaf record for a
    purely structural reason (more independent things need to move
    before it can ever reach fitness 0) that has nothing to do with
    which specific record it is. `_mutate_objective` already picks a
    fresh random leaf on every call and is a no-op when that leaf isn't
    actually improvable, so repeating it `len(leaves)`-many times for
    the SAME record naturally rotates through its different leaves over
    the burst rather than wasting every attempt on one that already
    stalled; a single-leaf record (the common case) is completely
    unaffected -- its own burst size is still exactly 1, identical to
    this module's behavior before this fix."""
    return max(1, min(_LOCAL_BURST_CAP, len(_leaf_variables(record))))


def _branch_key(record):
    return f"{record['decision_name']}::{record['rule_id']}"


def is_active(record, covered_keys):
    deps = record.get('grounded_upstream_branches') or []
    return all(d in covered_keys for d in deps)


# ---------------------------------------------------------------------------
# Standard NSGA-II machinery -- unmodified from its own textbook form,
# applied here to whichever objective set is currently active.
# ---------------------------------------------------------------------------

def _dominates(a, b):
    return all(x <= y for x, y in zip(a, b)) and any(x < y for x, y in zip(a, b))


def fast_non_dominated_sort(fitness_vectors):
    n = len(fitness_vectors)
    dominated_by = [set() for _ in range(n)]
    domination_count = [0] * n
    fronts = [[]]
    for p in range(n):
        for q in range(n):
            if p == q:
                continue
            if _dominates(fitness_vectors[p], fitness_vectors[q]):
                dominated_by[p].add(q)
            elif _dominates(fitness_vectors[q], fitness_vectors[p]):
                domination_count[p] += 1
        if domination_count[p] == 0:
            fronts[0].append(p)
    i = 0
    while fronts[i]:
        next_front = []
        for p in fronts[i]:
            for q in dominated_by[p]:
                domination_count[q] -= 1
                if domination_count[q] == 0:
                    next_front.append(q)
        i += 1
        fronts.append(next_front)
    return [f for f in fronts if f]


def crowding_distance(front, fitness_vectors):
    distances = {i: 0.0 for i in front}
    if not front or not fitness_vectors[front[0]]:
        return distances
    num_obj = len(fitness_vectors[front[0]])
    for m in range(num_obj):
        front_sorted = sorted(front, key=lambda i: fitness_vectors[i][m])
        distances[front_sorted[0]] = float('inf')
        distances[front_sorted[-1]] = float('inf')
        vmin, vmax = fitness_vectors[front_sorted[0]][m], fitness_vectors[front_sorted[-1]][m]
        if vmax == vmin or vmax == float('inf'):
            continue
        for k in range(1, len(front_sorted) - 1):
            distances[front_sorted[k]] += (
                (fitness_vectors[front_sorted[k + 1]][m] - fitness_vectors[front_sorted[k - 1]][m])
                / (vmax - vmin))
    return distances


# ---------------------------------------------------------------------------
# The loop itself.
# ---------------------------------------------------------------------------

def _key_columns_for(schema, table):
    """Every column that's part of `table`'s own declared PK/UNIQUE key,
    or a declared FK on `table` -- the set `_seed_shared_population`'s
    own per-objective offsetting must shift consistently, so that two
    independently-seeded objectives' own dedicated rows never collide on
    the exact same small placeholder key value (a real bug found testing
    this refinement at full FLEX2 scale, 2026-09-12: many different
    objectives each seeding their own COURSE row with the identical
    placeholder COURSE_ID produced real UNIQUE-constraint failures
    `validate_with_sqlite` caught immediately -- the earlier "first row
    per table" design never hit this, since it only ever had ONE row per
    table, total, across every objective). Deliberately narrow -- a
    genuine business-value column (a lecture count, a GPA, ...) a DMN
    branch actually searches over must never be shifted, or hillclimb's
    own starting point for it would be dragged arbitrarily far from a
    real target for no reason."""
    real = table if table in schema else (
        table.upper() if table.upper() in schema else (
            table.lower() if table.lower() in schema else table))
    info = schema.get(real, {})
    cols = _own_unique_columns_for(schema, table)
    cols |= {fk['column'].upper() for fk in (info.get('fk_columns') or [])}
    return cols


def _own_unique_columns_for(schema, table):
    """Just `table`'s own declared PK/UNIQUE columns, FLATTENED across
    every keyset -- the subset of `_key_columns_for` that needs
    OFFSETTING (moving in lockstep with the rest of this record's own
    key/FK columns), deliberately excluding FK columns. Used only as
    part of `_key_columns_for` -- NOT safe for `merge_archive_candidate`'s
    own within-record collision DEDUP (`used_key_values`), which needs
    `_own_solo_unique_columns_for` instead (see that function's own
    docstring for why the flattening that's harmless for offsetting is
    actively wrong for dedup)."""
    real = table if table in schema else (
        table.upper() if table.upper() in schema else (
            table.lower() if table.lower() in schema else table))
    return {c.upper() for keyset in _unique_key_sets(schema, real) for c in keyset}


def _own_solo_unique_columns_for(schema, table):
    """Only `table`'s own declared PK/UNIQUE columns that are ALONE
    sufficient for row-level uniqueness -- i.e. a keyset of length 1 --
    used exclusively by `merge_archive_candidate`'s own within-record
    collision dedup (`used_key_values`). A real regression found running
    FLEX2 (2026-09-13, immediately after the dedup fix that motivated
    `_own_unique_columns_for` in the first place): `COURSE_REGISTRATION`'s
    own PK is the COMPOSITE `(OFFER_ID, ROLL_NO)`, and it also carries a
    COMPOSITE unique index on `(ROLL_NO, CAMP_ID, SEM_ID, COURSE_ID)`
    -- `_own_unique_columns_for`'s flattening (correct for OFFSETTING,
    which must shift every column in a composite key regardless) turns
    this into "ROLL_NO and SEM_ID must each be unique ALONE," which is
    flatly wrong: a single student's own `derived_aggregate` rows over
    this table are SUPPOSED to share the identical ROLL_NO/SEM_ID across
    many rows, differing only by COURSE_ID -- that's the entire point of
    counting them. Treating either column as individually dedup-worthy
    bumped it on every one of those legitimate repeats, corrupting 25
    objectives (930 spurious bumps in one run, confirmed directly).
    `CURRENCY_EXCHANGE`'s own PK (`id`, jBilling) and `BASE_USER`/
    `PURCHASE_ORDER`'s own PKs (also bare `id`) that originally motivated
    `used_key_values` are all single-column, so restricting dedup to
    keysets of length 1 still catches every real collision found so far
    while leaving every composite key's own legitimate row-to-row sharing
    alone -- a genuine composite-PK collision (two of a record's own rows
    landing on the exact same full tuple) is a real bug this narrowing
    would miss, but none has been found yet, and guessing which ONE
    column of an unowned composite key to bump would be arbitrary without
    one; revisit if one is ever found."""
    real = table if table in schema else (
        table.upper() if table.upper() in schema else (
            table.lower() if table.lower() in schema else table))
    cols = set()
    for keyset in _unique_key_sets(schema, real):
        if len(keyset) == 1:
            cols.add(keyset[0].upper())
    return cols


_COMPOSITE_KEY_DEDUP_COLUMN = {
    # A genuine composite-PK collision, confirmed real (2026-09-25, first
    # hit running `validation_oracle/tests/per_individual_archive_
    # coverage.py` against a fresh FLEX2 archive, then reproduced directly
    # against `merge_archive_candidate` too): `STUDENT_ATTENDANCE`'s own
    # PK is the composite `(LECTURE_ID, ROLL_NO)`. `Attendance Eligibility
    # For Final Exam`'s own `lecturesAttended` is `COUNT(STUDENT_
    # ATTENDANCE) WHERE ROLL_NO = <student> AND ATTEND_FLAG='Y' AND
    # LECTURE_ID IN (...)` (compiled_constraints.json, confirmed directly)
    # -- ROLL_NO is the aggregate's own GROUPING key, the same student
    # across every counted row BY DESIGN; LECTURE_ID is what's supposed to
    # differ, one per distinct lecture actually attended. The seed
    # mechanism that materializes "N lectures attended" as N copies of one
    # row never varies LECTURE_ID across those copies (confirmed directly
    # against the raw archived individual: 3 literally identical
    # `{ROLL_NO: X, LECTURE_ID: X}` rows under one owner), so all N land on
    # the exact same real PK tuple the moment they're offset into one
    # database -- a real `UNIQUE constraint failed` this project's own
    # `_own_solo_unique_columns_for` deliberately never tried to catch
    # (composite keys were excluded there on purpose, see its own
    # docstring's "revisit if one is ever found" note -- this is that).
    ('FLEX2', 'STUDENT_ATTENDANCE'): 'LECTURE_ID',
}


def _dedup_composite_keys(schema, table, row_copy, used_key_values, case_study=None):
    """Call once a row's own key columns have ALREADY been offset (the
    single-column dedup loop just above/its `_offset_rows_by_owner`
    twin in `validation_oracle/tests/per_individual_archive_coverage.py`
    both call this immediately after that loop, on the SAME `row_copy`
    and the SAME `used_key_values` dict they already thread through for
    solo-unique columns) -- checks every composite (length > 1) PK/UNIQUE
    keyset this table declares for a genuine FULL-TUPLE collision against
    another row already placed in this same dedup scope.

    Deliberately NOT a general "guess which column of any composite key
    to bump" mechanism -- same discipline as `filter_placeholder_
    sources.py`/`subject_root_overrides.py`: which column is safe to vary
    is a real domain judgment call (bump the wrong one -- e.g. `STUDENT_
    ATTENDANCE`'s own `ROLL_NO` instead of `LECTURE_ID` -- and the
    aggregate's own correlating key silently breaks, corrupting a
    DIFFERENT, already-verified objective's own count), so this only
    acts on a table explicitly named in `_COMPOSITE_KEY_DEDUP_COLUMN`
    above. For every other table this is a no-op, by construction --
    `_own_solo_unique_columns_for`'s own long-documented "leaves every
    composite key's own legitimate row-to-row sharing alone" behavior is
    completely unchanged for anything not in that dict (confirmed:
    `COURSE_REGISTRATION`'s own composite keys stay untouched, since it
    has no entry here)."""
    override_col = _COMPOSITE_KEY_DEDUP_COLUMN.get((case_study, table.upper()))
    if override_col is None:
        return
    real = table if table in schema else (
        table.upper() if table.upper() in schema else (
            table.lower() if table.lower() in schema else table))
    for keyset in _unique_key_sets(schema, real):
        if len(keyset) < 2:
            continue
        keyset_upper = [c.upper() for c in keyset]
        if override_col.upper() not in keyset_upper:
            continue

        def _get(col):
            return row_copy.get(col, row_copy.get(col.upper(), row_copy.get(col.lower())))

        tup = tuple(_get(c) for c in keyset)
        if any(v is None for v in tup):
            continue  # not fully populated yet -- nothing to dedup
        used = used_key_values.setdefault((table.upper(), tuple(keyset_upper)), set())
        if tup in used:
            idx = keyset_upper.index(override_col.upper())
            tup_list = list(tup)
            while tuple(tup_list) in used:
                tup_list[idx] += 1
            actual_col = next(c for c in row_copy if c.upper() == override_col.upper())
            row_copy[actual_col] = tup_list[idx]
            tup = tuple(tup_list)
        used.add(tup)


_SEED_KEY_OFFSET_UNIT = 1_000_000  # generous: FLEX2 has ~250 records, nowhere near exhausting int range


def _seed_shared_population(records, case_study, population_size):
    """One shared starting candidate, built once by giving every
    objective its OWN dedicated seed rows (from that record's own
    `build_seed_candidate` output) -- added as fresh, ADDITIONAL rows on
    the shared base candidate, never deduplicated/merged against another
    objective's own seed rows the way the earlier "first row per table"
    design did (see this module's own docstring on why that sharing was
    the dominant, measured cause of low coverage). `base_focal_maps
    [record_id]` records exactly which of those newly-added rows belong
    to that objective, found via an `id(row)` correspondence between
    `build_seed_candidate`'s own returned `focal` dict (its "this is the
    row this leaf actually reads" view) and the copies actually inserted
    into `base` -- not every table `build_seed_candidate`'s own candidate
    has rows for shows up in its own `focal` (`derived_aggregate`/
    `exists`/`raw_sql_boolean` kinds add rows directly, never through
    focal -- see `_focal_tables_for_leaf`), so this naturally seeds ONLY
    the tables this refinement actually needs a per-objective row for;
    the rest is created lazily by `_focal_for_mutate` the first time some
    other leaf kind needs it.

    Every objective's own key/FK column values (see `_key_columns_for`)
    are shifted by a per-objective offset (`i * _SEED_KEY_OFFSET_UNIT`)
    before merging into `base` -- the fix for the real UNIQUE-collision
    bug `_key_columns_for`'s own docstring describes. The SAME offset is
    also applied to every numeric value in this objective's own seeded
    `scenario` (`build_seed_candidate`'s own `<placeholder>` bindings,
    e.g. `<student>` -> `scenario['student']`), not just its rows: a
    `derived_aggregate` seed row built by `_row_from_filter_conjuncts`
    sets a key column (e.g. `ROLL_NO`) directly FROM the matching
    scenario value (`ROLL_NO = <student>` -> `row['ROLL_NO'] =
    scenario['student']`) -- offsetting the row's own copy without
    offsetting `scenario` by the identical amount would silently break
    that equality the moment the filter predicate re-reads `scenario` at
    match time, found exactly this way testing this fix. `__today__`
    (a date, not a key) is deliberately excluded.

    Repaired once, wholesale, after every objective's own rows are in --
    the population's common ancestor. Each individual starts as an
    independent joint deep copy of `(base, base_focal_maps,
    base_scenario_maps)` so mutation/crossover on one never touches
    another (the same "parents are never mutated in place" discipline
    mutate()/crossover() already follow, extended to the population
    itself) -- `base_scenario_maps` (2026-09-13's per-individual
    scenario fix) gives every individual its OWN independently-evolving
    copy of each objective's own scenario, rather than every individual
    forever sharing one frozen, run-global scenario per objective (see
    this module's own docstring for the real bug that caused)."""
    schema = _schema_for(case_study)
    base_scenario_maps = {}
    base = Candidate()
    base_focal_maps = {}
    for i, r in enumerate(records):
        rid = r['record_id']
        c, f, s = build_seed_candidate(r)
        offset = i * _SEED_KEY_OFFSET_UNIT
        for key, val in s.items():
            if key != '__today__' and isinstance(val, (int, float)) and not isinstance(val, bool):
                s[key] = val + offset
        base_scenario_maps[rid] = s
        id_to_copy = {}
        for table, rows in c.as_dict().items():
            key_cols = _key_columns_for(schema, table)
            for row in rows:
                if key_cols:
                    for col in list(row):
                        if col.upper() in key_cols and isinstance(row[col], (int, float)) \
                                and not isinstance(row[col], bool):
                            row[col] = row[col] + offset
                # Tagged with this objective's own record_id -- the
                # aggregate row-sharing fix (2026-09-13): every seed row
                # `build_seed_candidate` produced for THIS record (whether
                # a focal-style row or a `derived_aggregate`/`exists`/
                # `derived_join_count` row added directly, never through
                # focal -- see this record's own leaf handling in
                # candidate.py) must stay invisible to some OTHER
                # objective's own aggregate/exists scan of the same
                # physical table once every objective's seed rows are
                # merged into one shared `base`. Harmless for focal-style
                # rows (schema_column et al.): those are found by direct
                # `focal_maps` dict reference, never by scanning the
                # table, so the extra key changes nothing for their own
                # readers -- it only stops them being miscounted by
                # someone else's aggregate.
                row_copy = dict(row)
                row_copy[_OWNER_KEY] = rid
                base.add_row(table, row_copy)
                id_to_copy[id(row)] = row_copy
        rec_focal = {table: id_to_copy[id(row)] for table, row in f.items() if id(row) in id_to_copy}
        if rec_focal:
            base_focal_maps[rid] = rec_focal
    repair_candidate(base, case_study)
    population = [copy.deepcopy((base, base_focal_maps, base_scenario_maps)) for _ in range(population_size)]
    return population


def _mutations_per_child(active, population_size, mutations_per_child):
    """How many DISTINCT active objectives each child attempts a
    mutation against this generation -- the fix for a real, measured
    attention-dilution bottleneck (design doc §13.34/§13.35): with a
    fixed single pick per child (this module's original design), the
    active set growing into the hundreds (once the DRD-grounding/
    id-collision fixes surfaced FLEX2's real 391-objective scope) meant
    every objective was still competing for the same `population_size *
    2` total picks per generation regardless of how large the active set
    grew -- confirmed empirically: population/generation tuning alone
    plateaued (even regressed slightly) rather than helping.

    'auto' (the default) recomputes a fresh value EVERY generation from
    the CURRENT active-set size (which itself grows over the run as DRD
    gates open), aiming for roughly one attempted mutation per active
    objective per generation across the WHOLE offspring batch:
    `ceil(len(active) / (2 * population_size))`, never less than 1. An
    explicit int overrides this and is used as-is (e.g. for a smaller
    self-test where auto-scaling would round down to 1 anyway)."""
    if mutations_per_child == 'auto':
        return max(1, math.ceil(len(active) / (2 * population_size))) if active else 1
    return mutations_per_child


def _build_decision_subject_row(candidate, rec_focal, r, rid):
    """The decision's own real DMN subject row (2026-09-24, extracted into
    a shared function 2026-09-26) -- `compile_constraints.py`'s own
    `decision_subject` field (a generator-owned port of `validation_oracle/
    subject_table.py`'s algorithm, computed once at compile time -- see
    that module's own docstring for why a port, not an import). No leaf
    variable ever needs this row DURING search (fitness never reads it),
    so this was originally called from exactly one place -- a one-time,
    post-search synthesis step inside `merge_archive_candidate` -- until a
    real gap was found (2026-09-26, tracing Spree's own `Promotion
    Customer Group Eligibility`): `validation_oracle/tests/per_individual_
    archive_coverage.py`'s own no-merge pipeline never calls
    `merge_archive_candidate` at all, so this row never got built there
    either, even after the compile-time `decision_subject` fix -- the
    junction row it depends on simply never existed for ANY individual
    materialized that way, regardless of the fix. Extracted here, called
    from BOTH places now, so they can never drift apart on this again.

    `candidate` is whatever candidate `rec_focal`'s own rows already live
    in (the shared merged candidate, in `merge_archive_candidate`'s own
    case; one individual's own candidate, in the per-individual tool's).
    `rec_focal` is `{table: row}` for record `r` specifically -- either
    `merge_archive_candidate`'s own `merged_rec_focal`, or one entry of a
    single individual's own `focal_maps[record_id]`. `rid` is `r['record_id']`,
    used only to tag a freshly-created row's own `_OWNER_KEY`. Mutates
    `candidate` (via `add_row`) and `rec_focal` in place; returns nothing."""
    subject = r.get('decision_subject')
    if not subject:
        return
    subject_focal = rec_focal.get(subject['table']) or next(
        (v for k, v in rec_focal.items() if k.upper() == subject['table'].upper()), None)
    is_new = subject_focal is None
    if is_new:
        subject_focal = {}
    resolvable = bool(subject['joins'])
    wired_any = False
    for target_table, hops in subject['joins'].items():
        # Deliberately narrow scope, disclosed rather than silently
        # guessed: only a SINGLE hop from the subject to each other table
        # this record needs (the confirmed real shape for every decision
        # this applies to so far) is attempted -- a genuine multi-hop
        # chain would need a fresh intermediate row this pass does not
        # attempt to synthesize, so it's skipped instead of half-built.
        if len(hops) != 1:
            resolvable = False
            break
        hop = hops[0]
        target_focal = rec_focal.get(hop['to_table']) or next(
            (v for k, v in rec_focal.items() if k.upper() == hop['to_table'].upper()), None)
        if target_focal is None:
            # This record's own construction never built a dedicated row
            # for a table the subject needs to link through -- e.g. a
            # rule whose own leaves never touch it at all. Synthesize a
            # fresh, minimal row instead of leaving this hop unresolved:
            # `repair_candidate`, called right after this, fills in
            # whatever else it still needs (NOT NULL columns, its own
            # FKs) -- the same discipline already applied to every other
            # row this pass builds, not a new mechanism.
            target_focal = candidate.add_row(hop['to_table'], {_OWNER_KEY: rid})
            rec_focal[hop['to_table']] = target_focal

        existing_from_value = subject_focal.get(hop['from_column'])
        if existing_from_value is not None:
            # A real, confirmed bug (2026-09-26, OpenMRS's own `Identifier
            # Location Requirement`/`Identifier Format Validity`): the
            # subject row and the target row can EACH already have their
            # own independently-set value here (`identifier_type=
            # 40000001` vs `patient_identifier_type_id=40000002`, e.g.) --
            # two different leaves, or two different repair passes, having
            # nothing to do with each other, both landing on "some real
            # number" without ever correlating. The OLD rule here
            # ("subject already has a value -- never overwritten") assumed
            # "has a value" means "has the RIGHT value," which silently
            # left a genuine mismatch uncorrected -- the real join this
            # decision's own subject depends on then simply never matches
            # at verification time, regardless of what either row's own
            # OTHER facts say. Fixed: if the target's own to_column
            # already agrees with the subject's own from_column, nothing
            # to do (the common, correct case); if they DISAGREE, force
            # the TARGET to conform to the SUBJECT, never the reverse --
            # `target_focal` is this record's own dedicated, private focal
            # row for `hop['to_table']` (never shared with any other
            # record's own focal), so overwriting its own key column here
            # can't dangle any OTHER record's own reference to it, while
            # the subject's own row identity is what every OTHER fact on
            # THIS record already correlates against and must stay fixed.
            if target_focal.get(hop['to_column']) != existing_from_value:
                target_focal[hop['to_column']] = existing_from_value
                wired_any = True
            continue
        pk_value = target_focal.get(hop['to_column'])
        if pk_value is None:
            # The referenced row's own PK was never set by search/seeding.
            # Assigned HERE instead, synchronously, so the new junction
            # row's own FK can actually reference the real, final value --
            # reuses `mutation.py`'s own `_fresh_key_value` (already
            # collision-safe against everything in `candidate` so far),
            # not a fresh ad hoc scheme.
            pk_value = _fresh_key_value(candidate, hop['to_table'], hop['to_column'])
            target_focal[hop['to_column']] = pk_value
        subject_focal[hop['from_column']] = pk_value
        wired_any = True
    if resolvable and is_new and (subject_focal or wired_any):
        subject_focal[_OWNER_KEY] = rid
        candidate.add_row(subject['table'], subject_focal)
        rec_focal[subject['table']] = subject_focal


def _deep_copy_individual(individual):
    """A fresh `(candidate, focal_maps, scenario_maps)`, sharing NOTHING
    mutable with the original -- every row dict copied, with `focal_maps`
    remapped through the SAME `id(original_row) -> copied_row`
    correspondence `merge_archive_candidate`'s own `get_copy` already uses
    for the identical reason, so a focal row and its own candidate-list
    row stay the exact same object post-copy, just as they were before it.

    Real bug this fixes (2026-09-26, found tracing Spree's own
    `Promotion Customer Group Eligibility::Rule_2`): `update_archive`
    used to store `(f, individual)` with `individual` the literal SAME
    object still living in the shared `population` list. DynaMOSA runs
    ONE population across every objective in the case study, and the SAME
    individual can go on being mutated for OTHER objectives after already
    being archived at `fitness=0.0` for this one -- `update_archive`'s own
    strict `f < archive[rid][0]` only ever checks for IMPROVEMENT, never
    re-verifies an already-recorded 0.0 against later changes. Confirmed
    directly: `Rule_2` needs `promotionTargetGroupsConfigured = False`
    (no matching `spree_promotion_rules` row); the archived individual's
    own scenario (`{'promotion_id': 1000001}`) and a REAL, still-present,
    still-owned `spree_promotion_rules` row (`promotion_id=1000001,
    type='...CustomerGroup'`) match EXACTLY -- the fact this rule needed
    false was true again by the time anyone looked, some later generation
    having re-added it while mutating a DIFFERENT objective's own leaf on
    the same shared table. Archiving a deep copy instead means whatever
    got recorded at the moment of archiving is what stays recorded,
    permanently insulated from every later generation's own further
    mutation of the live population -- the same guarantee this project's
    own independent validator already assumes an archived individual
    provides, now actually true of the search's own data structure too."""
    candidate, focal_maps, scenario_maps = individual
    id_to_copy = {}
    new_candidate = Candidate()
    for table, rows in candidate.as_dict().items():
        for row in rows:
            row_copy = dict(row)
            new_candidate.add_row(table, row_copy)
            id_to_copy[id(row)] = row_copy
    new_focal_maps = {}
    for rid, rec_focal in focal_maps.items():
        new_rec_focal = {}
        for table, row in rec_focal.items():
            copy = id_to_copy.get(id(row))
            if copy is not None:
                new_rec_focal[table] = copy
            # else: this focal row is no longer in the candidate at all --
            # a real, confirmed scenario (2026-09-26): a row-count
            # mutation can DECREASE a count later in the search and remove
            # the very row `_row_from_filter_conjuncts`'s own self
            # -correlation fix (candidate.py/mutation.py, same day)
            # registered into `focal` as the new self-reference anchor,
            # leaving `focal` pointing at a row `candidate.as_dict()` no
            # longer has. `focal` is best-effort bookkeeping for reuse,
            # never the source of truth for what's actually in the
            # candidate -- dropping a stale entry here is honest (a later
            # reader that needs this table's own focal row will simply not
            # find one, same as if this objective never touched it), never
            # a silent wrong guess at a row that no longer exists.
        new_focal_maps[rid] = new_rec_focal
    new_scenario_maps = {rid: dict(scenario) for rid, scenario in scenario_maps.items()}
    return (new_candidate, new_focal_maps, new_scenario_maps)


def run_dynamosa(records, case_study, population_size=20, generations=50, rng=None,
                  mutations_per_child='auto', kick_probability=_KICK_PROBABILITY, dynamic_gating=True,
                  use_local_burst=True):
    """Runs the population loop over `records` (compiled branches from
    ONE case study -- mixing case studies makes no sense, since a shared
    candidate's tables are case-study-specific). Returns
    (archive, coverage_history, population) -- `archive` is {record_id:
    (best_fitness_ever_found, individual_that_achieved_it)}, growing
    monotonically across the whole run (DynaMOSA's own archive
    discipline: a target's best answer is never lost even if the current
    population moves on); `coverage_history[g]` is how many objectives
    had reached fitness 0.0 by the end of generation g, for watching
    convergence honestly rather than only reporting the final number;
    `population` is the final generation's own individuals -- exposed so
    a caller (generate_dataset.py) can pick ONE real, self-consistent
    candidate to actually materialize, rather than the archive's own
    per-objective-best snapshots, which were captured at different points
    in the run and were never guaranteed consistent with each other.

    Each "individual" throughout this function is a `(candidate,
    focal_maps, scenario_maps)` TRIPLE, not a bare `Candidate` --
    `focal_maps` is `{record_id: {table: row}}` (this module's own
    focal-per-objective refinement, see the module docstring): every
    objective's own dedicated row per table travels WITH its candidate
    through crossover and mutation, rather than every objective sharing
    whichever row happens to be "first" in a bare `Candidate`.
    `scenario_maps` is `{record_id: scenario}` (2026-09-13's own
    per-individual scenario fix, see the module docstring for the real
    `not_persisted`-mutation bug this replaces): every objective's own
    current bind-parameter state travels WITH its candidate the same
    way, rather than every individual forever sharing one frozen,
    run-global scenario per objective that a mutation could never
    actually update. This also means a caller no longer needs (or gets)
    a separately-returned `scenario_cache` -- every individual, and every
    archived one, already carries its own current scenario, so
    `evaluate_objective`/`merge_archive_candidate` read it directly off
    whichever individual they're given.

    `mutations_per_child` (see `_mutations_per_child`'s own docstring)
    is this module's own multi-pick mutation fix (2026-09-12): each
    child now attempts mutation against SEVERAL distinct active
    objectives per generation, sequentially, each attempt building on
    the previous one's own result within that same child -- not just a
    single random pick, regardless of how large the active set grows.

    Each of those picks, in turn, now gets a LOCAL BURST of attempts
    (see `_local_burst_size`'s own docstring) rather than exactly one --
    this module's own composite-leaf fix (2026-09-12), found necessary
    after the multi-pick fix above still left the corpus's genuinely
    hardest records stuck: a record needing several independent facts
    (an aggregate count, a category mapping, a join-based count, an
    upstream-chained literal, a plain column comparison, ...) to ALL
    align at once needs proportionally more within-record optimization
    depth to ever reach fitness 0 -- purely a function of how many leaf
    variables THAT record's own condition has, never of which specific
    record or decision it is. A single-leaf record's own burst size is
    still exactly 1, so this is a pure addition for multi-leaf records,
    not a behavior change for the common, already-solving case.

    The extra cost is cheap relative to what it buys: each additional
    mutation attempt is one numeric optimization over one leaf, far
    lighter than the O(active²) non-dominated-sort cost that already
    dominates a generation regardless of how many mutations were
    attempted -- so both fixes trade a comparatively small compute
    increase for directly fixing a diagnosed bottleneck, rather than the
    population/generation tuning already found not to work at this
    scale.

    `kick_probability` (see `_kick_value_for`'s own docstring) is this
    module's own local-optimum escape hatch (2026-09-12) -- built after
    confirming directly (a 300-iteration single-record `hillclimb()`
    against one of the stuck records, not assumed) that a large share of
    what's left stuck even after the multi-pick and composite-leaf
    fixes above is a GENUINE local optimum under greedy single-leaf
    search: extending generations 40->70 at the same population produced
    a coverage_history flat at the exact same count for 45 generations
    straight, ruling out "just needs more time." With this probability,
    a picked leaf's value is replaced by an unconditional random jump
    instead of the usual greedy best-value pick, letting the search
    escape a state where no SINGLE leaf's own improving move exists even
    though a JOINT change across several leaves would reach fitness 0.
    Safe at the population level: DynaMOSA's own archive never regresses
    from a kick that makes one child temporarily worse, and
    non-dominated sorting discards a kick with no compensating gain on
    its own.

    `use_local_burst` (True by default -- exactly this function's own
    prior, only behavior, unchanged): the other half of this project's
    own evaluation-comparison ablation, alongside `mutations_per_child`
    (already a parameter, no change needed there -- passing `1` reverts
    to a single random pick per child, the design's own original,
    pre-multi-pick behavior). When False, every pick gets exactly one
    mutation attempt instead of `_local_burst_size`'s own leaf-count
    -scaled repeat count -- isolating this module's own composite-leaf
    fix specifically (see `_local_burst_size`'s own docstring for the
    real, measured bottleneck it was built to fix).

    `dynamic_gating` (True by default -- exactly this function's own
    prior, only behavior, unchanged) controls the "Dyna" part specifically,
    for the ablation this project's own evaluation compares against
    (functionally equivalent to MOSA, DynaMOSA's direct predecessor,
    applied over the identical representation/archive/NSGA-II core):
    when False, every record is active from generation 1 regardless of
    `grounded_upstream_branches`, i.e. dependency-gated activation is
    switched off entirely while every other mechanism -- the archive,
    non-dominated sorting, crowding distance, crossover, mutation --
    stays byte-for-byte identical. This isolates exactly one variable
    (whether unsatisfiable-dependency objectives are allowed to compete
    for selection pressure before they're even reachable) rather than
    comparing against a separately-implemented algorithm with its own,
    potentially unfair, tuning and bugs."""
    rng = rng or random.Random(0)
    table_cache = {}
    population = _seed_shared_population(records, case_study, population_size)

    # Every record gets a real entry from the start, even one that turns
    # out permanently unresolvable (inf against every individual all run)
    # -- a real KeyError found wiring this into generate_dataset.py
    # (2026-09-12): update_archive's own strict `<` comparison never
    # improves on inf with inf, so a record that's inf for every
    # individual, always, never got a key at all, and any caller that
    # didn't defensively .get() the archive crashed. An honest "never
    # covered, inf" entry is the correct initial state, not an absent key.
    archive = {r['record_id']: (float('inf'), population[0]) for r in records}

    def update_archive(individual):
        candidate, focal_maps, scenario_maps = individual
        for r in records:
            rid = r['record_id']
            f = evaluate_objective(r, candidate, focal_maps, scenario_maps, table_cache)
            if f < archive[rid][0]:
                archive[rid] = (f, _deep_copy_individual(individual))

    for ind in population:
        update_archive(ind)

    coverage_history = []
    for _gen in range(generations):
        covered_keys = {_branch_key(r) for r in records
                         if archive.get(r['record_id'], (float('inf'), None))[0] == 0.0}
        active = records if not dynamic_gating else [r for r in records if is_active(r, covered_keys)]

        # Computed once per generation (the active set itself only
        # changes between generations, as DRD gates open) -- not once per
        # child, since every child in this same generation should use the
        # same "how many picks" policy; only WHICH picks differ per child.
        k = _mutations_per_child(active, population_size, mutations_per_child)

        offspring = []
        while len(offspring) < population_size:
            p1, p2 = rng.sample(population, 2) if len(population) >= 2 else (population[0], population[0])
            (p1_c, p1_fm, p1_sm), (p2_c, p2_fm, p2_sm) = p1, p2
            c1, c2, _f1, _f2, fm1, fm2, sm1, sm2 = crossover(
                p1_c, p2_c, case_study, rng, focal_maps1=p1_fm, focal_maps2=p2_fm,
                scenario_maps1=p1_sm, scenario_maps2=p2_sm)
            for child_c, child_fm, child_sm in ((c1, fm1, sm1), (c2, fm2, sm2)):
                if active:
                    # k DISTINCT active objectives, not just one -- this
                    # module's own multi-pick mutation fix (see
                    # _mutations_per_child's own docstring). Applied
                    # sequentially: each pick's mutation attempt builds on
                    # the PREVIOUS pick's own result within this same
                    # child, exactly like a single pick already did.
                    for r in rng.sample(active, min(k, len(active))):
                        # A local burst, not just one attempt, per pick --
                        # this module's own composite-leaf fix (see
                        # _local_burst_size's own docstring): a record
                        # with several independent leaves that must ALL
                        # align gets proportionally more within-record
                        # attempts here, purely as a function of its own
                        # leaf count, never by which record it is.
                        # _mutate_objective already guards its own genome
                        # computation against FitnessEvaluationError (see
                        # its own docstring) -- a freshly-created,
                        # still-empty dedicated row can leave some OTHER
                        # leaf of the same record genuinely unresolvable,
                        # an honest "not evaluable yet," never a crash.
                        burst = _local_burst_size(r) if use_local_burst else 1
                        for _ in range(burst):
                            child_c, child_fm, child_sm, _improved = _mutate_objective(
                                r, child_c, child_fm, child_sm, table_cache, rng,
                                kick_probability=kick_probability)
                offspring.append((child_c, child_fm, child_sm))
        offspring = offspring[:population_size]

        for child in offspring:
            update_archive(child)

        combined = population + offspring
        fitness_vectors = [[evaluate_objective(r, ind[0], ind[1], ind[2], table_cache)
                             for r in active] for ind in combined]
        fronts = fast_non_dominated_sort(fitness_vectors)
        new_population = []
        for front in fronts:
            if len(new_population) + len(front) <= population_size:
                new_population.extend(combined[i] for i in front)
            else:
                cd = crowding_distance(front, fitness_vectors)
                front_sorted = sorted(front, key=lambda i: -cd[i])
                new_population.extend(combined[i] for i in front_sorted[:population_size - len(new_population)])
                break
        population = new_population or population  # never leave the population empty

        covered_count = sum(1 for r in records
                             if archive.get(r['record_id'], (float('inf'), None))[0] == 0.0)
        coverage_history.append(covered_count)

    return archive, coverage_history, population


# ---------------------------------------------------------------------------
# Merge-the-archive final-dataset construction (2026-09-13) -- §13.42's own
# named follow-up: picking one individual from the FINAL population (this
# module's original `generate_dataset.py` strategy) caps out well below
# archive coverage for a reason that has nothing to do with row-sharing --
# DynaMOSA/NSGA-II deliberately SPREADS a population across Pareto-front
# *specialists*, never converges it onto one *generalist* individual, which
# is exactly why the archive (crediting an objective the moment ANY
# individual, ANY generation, solves it) exists as a separate, more
# permissive structure in the first place. This section builds the final
# candidate FROM the archive instead: merge every covered objective's own
# best-ever answer into one shared candidate, rather than hoping one
# generation's population happens to contain a single all-purpose winner.
# ---------------------------------------------------------------------------

def _scenario_keys_needing_offset(record):
    """Which of this record's own scenario keys are tied to a ROW-key
    correspondence -- i.e. genuinely need the SAME per-objective offset
    `merge_archive_candidate` applies to its own rows' PK/UNIQUE/FK
    columns, rather than being a `not_persisted` leaf compared DIRECTLY
    to a literal in the record's own condition (e.g. `purchaseQuantity
    >= 50`), which must be left exactly as the search tuned it.

    A real, second bug found the same day as the PK-collision merge fix
    this helper supports (2026-09-13): the first version of that fix
    blindly offset EVERY numeric scenario value, mirroring
    `_seed_shared_population`'s own blanket approach -- safe THERE only
    because at seed time every `not_persisted` value is still a raw,
    uniform placeholder the search has not yet tuned; applying the
    identical blanket shift a SECOND time, AFTER the search already
    found the one correct value that satisfies a direct literal
    comparison, corrupts it. Confirmed directly: re-running Spree after
    the first version of the merge-time offset fix regressed 3
    objectives that had verified cleanly moments before, including both
    `Price List Volume Adjustment Tier Selection` rules this same
    session's own `not_persisted`-mutation fix (§13.46) had just gotten
    working.

    The real, narrower rule: a scenario key only needs to move in lockstep
    with a row's own key column when some leaf's own `filter_text`/
    `sql_template` actually names it as a `<placeholder>` -- exactly the
    same signal `build_seed_candidate` already uses to discover which
    scenario keys exist in the first place (`_PLACEHOLDER_RE`). A key
    that never appears inside any leaf's own filter/SQL text (like a
    bare `not_persisted` variable with no aggregate/join-count sibling)
    has no row to stay synchronized with, and must be left alone."""
    needed = set()

    def walk(node):
        if not isinstance(node, dict):
            return
        if node.get('kind') == 'substituted_decision':
            for sub in node.get('free_variable_resolutions', {}).values():
                walk(sub)
            return
        for field in ('filter_text', 'sql_template'):
            for m in _PLACEHOLDER_RE.finditer(node.get(field) or ''):
                needed.add(m.group(1))

    for node in record.get('variable_resolution', {}).values():
        walk(node)
    return needed


def _filter_columns_needing_offset(record):
    """{column name (uppercased) -> {placeholder names it's bound to}}
    for every column some leaf's own `filter_text` directly binds to an
    offsettable scenario placeholder via a plain `COLUMN = <placeholder>`
    conjunct -- i.e. exactly the columns `_row_from_filter_conjuncts`
    copies that placeholder's CURRENT value into (`row[col] =
    scenario[ph]`), whether or not that column also happens to be a
    declared PK/UNIQUE/FK (`_key_columns_for`'s own narrower set already
    covers those; this is the wider, structural fix for a column that
    ISN'T one -- jBilling's own `entity_id` on `CURRENCY_EXCHANGE`, never
    declared PK/FK in this schema extraction, yet exactly this kind of
    filter-bound column).

    Structural (parses `filter_text` the same way `_mechanical_filter_
    predicate`/`_row_from_filter_conjuncts` do): merely knowing the
    COLUMN NAME is bound to a placeholder in SOME leaf is not, by
    itself, enough to decide a given ROW's own current value should be
    offset -- a real regression found immediately after this function's
    first version shipped (2026-09-13): `Currency Exchange Rate
    Source::Rule_2` has TWO leaves sharing this same table, one binding
    `entity_id` to the `<entity_id>` placeholder (`hasEntitySpecificExchange`),
    the OTHER using a bare LITERAL `entity_id = 0`
    (`hasSystemDefaultExchange`) -- offsetting every owned row's
    `entity_id` just because the COLUMN NAME appears bound somewhere in
    the record corrupted the second leaf's own literal-0 row into a
    non-zero value, breaking its filter. The caller (`get_copy`) must
    additionally verify, per ROW, that the row's CURRENT value for a
    listed column actually equals the record's own (pre-merge) scenario
    value for one of the returned placeholders before offsetting it --
    never blanket, value-free, whole-column matching (an EARLIER, even
    more permissive version of this same idea -- matching ANY numeric
    column against ANY offsettable scenario value, no structural
    grounding at all -- produced a much worse false-positive regression
    at FLEX2's own scale, 25 objectives broken by 930 spurious matches on
    completely unrelated `derived_aggregate` grouping columns like
    `COURSE_REGISTRATION.ROLL_NO`/`SEM_ID`)."""
    offsettable = _scenario_keys_needing_offset(record)
    cols = {}

    def walk(node):
        if not isinstance(node, dict):
            return
        if node.get('kind') == 'substituted_decision':
            for sub in node.get('free_variable_resolutions', {}).values():
                walk(sub)
            return
        filter_text = node.get('filter_text')
        if not filter_text:
            return
        for c in re.split(r'\bAND\b', filter_text, flags=re.I):
            m = _SIMPLE_EQ_CONJUNCT_RE.match(c.strip())
            if not m:
                continue
            col, raw_val = m.group(1), m.group(2).strip()
            if _BARE_TABLE_DOT_COLUMN_RE.match(raw_val):
                continue
            ph = _PLACEHOLDER_RE.fullmatch(raw_val)
            if ph and ph.group(1) in offsettable:
                cols.setdefault(col.upper(), set()).add(ph.group(1))

    for node in record.get('variable_resolution', {}).values():
        walk(node)
    return cols


def _join_lookup_pairs(record):
    """(local_table, local_column, result_table, result_column) for
    every `join_lookup`/`join_null_check` leaf. `candidate.py`'s own
    `derive_value` (see its own docstring on the join_lookup branch)
    finds the joined-to row by searching for a `result_table` row whose
    OWN `result_column` VALUE equals `local_column`'s FK value --
    result_column doubling as a synthetic join key is a documented,
    narrow-scope trick (not a real PK lookup), but `build_seed_candidate`
    and `mutation.py`'s own M1 join_lookup mutation both keep the two
    values numerically EQUAL by construction, always. Merge-time
    offsetting must preserve that same equality exactly like it already
    does for scenario-placeholder-bound filter columns (see
    `_filter_columns_needing_offset`) -- a real bug found running
    OpenMRS end to end for the first time (2026-09-13): `orders.
    encounter_id` (a declared FK, offset normally by `_key_columns_for`)
    and `encounter.encounter_datetime` (a plain value column, never
    itself a key) are kept numerically equal by this scheme's own
    design; offsetting one without the other broke the join the moment
    `Order Date Activated Consistency Violations::Rule_4` (which needs
    this leaf) was merged -- confirmed directly: pre-merge, both
    happened to already be offset to the identical number by the
    RUN's own earlier seed-time offsetting, so the join "worked" only
    because it was never tested against a SECOND, merge-time shift."""
    pairs = []

    def walk(node):
        if not isinstance(node, dict):
            return
        if node.get('kind') == 'substituted_decision':
            for sub in node.get('free_variable_resolutions', {}).values():
                walk(sub)
            return
        if node.get('kind') in ('join_lookup', 'join_null_check'):
            via = node.get('via') or {}
            if via.get('local_table') and via.get('local_column') \
                    and node.get('result_table') and node.get('result_column'):
                pairs.append((via['local_table'], via['local_column'],
                              node['result_table'], node['result_column']))

    for node in record.get('variable_resolution', {}).values():
        walk(node)
    return pairs


def merge_archive_candidate(archive, records, case_study):
    """Thin wrapper over `_merge_archive_candidate_impl` (`include_all_rows=
    False`) -- see that function for the actual implementation and this
    docstring's own full collision-avoidance writeup, unchanged by the
    `include_all_rows` toggle added 2026-09-25 (see
    `merge_archive_candidate_full`'s own docstring for why that variant
    exists and how it differs)."""
    return _merge_archive_candidate_impl(archive, records, case_study, include_all_rows=False)


def merge_archive_candidate_full(archive, records, case_study):
    """Variant of `merge_archive_candidate`, built 2026-09-25 at the
    user's own explicit request: instead of merging in only each covered
    objective's OWNER-TAGGED rows (that objective's own dedicated focal
    row plus any other row its own search/mutation specifically touched
    -- see `merge_archive_candidate`'s own docstring), this merges in
    EVERY row of each covered objective's ENTIRE candidate, including the
    untouched shared-seed rows every candidate also carries a copy of.

    Reuses `_merge_archive_candidate_impl`'s identical, already-proven
    per-record offset (`i * _SEED_KEY_OFFSET_UNIT`, applied to every
    PK/UNIQUE/FK column in every row this call includes) for collision
    avoidance -- the SAME mechanism `merge_archive_candidate` itself
    relies on, not a new one. Chosen over a content-aware dedup/conflict-
    detection alternative specifically because the uniform per-record
    offset treats each covered objective's ENTIRE candidate as one
    atomic, internally self-consistent unit: every reference (FK) within
    one objective's own contributed rows shifts by the identical amount
    as the row it points to, so internal referential integrity is
    preserved automatically, with no selective/partial FK-rewrite step
    that could target the wrong reference (the class of bug
    `merge_archive_candidate`'s own docstring documents happening for
    even the narrower, owner-tagged-only case -- a value-based rewrite
    heuristic silently broke 25 unrelated FLEX2 objectives before being
    replaced with a structural one). A content-aware dedup strategy would
    need exactly that kind of selective rewrite (reassign THIS row's key,
    but only rewrite the FK references that actually pointed at it,
    leaving every other reference in the same candidate untouched) to
    keep the database compact -- judged not worth the risk for this use.

    The accepted, KNOWN tradeoff, not a bug: since every covered
    objective's candidate starts from the same shared seed template
    (`build_seed_candidate`) and typically mutates only a few rows/fields
    for its own fitness, including every row of every objective's
    candidate means each objective's own untouched copy of the shared
    baseline becomes its own private, uniquely-offset set of rows --
    producing a MUCH larger, more redundant database (up to one near-
    copy of the baseline per covered objective) than
    `merge_archive_candidate`'s compact, single-shared-baseline result.
    This does not affect verification CORRECTNESS (a duplicate-content
    row at a different PK cannot cause a false verification -- a rule
    still needs a real row satisfying its own condition to verify; extra
    rows just mean more enumeration work for `subject_table_for_decision`
    to do), only database size and how "realistic" it reads.

    Everything else -- `used_key_values`'s own same-record/same-table
    dedup-bump, `filter_cols`/`join_cols` structural offsetting,
    `cross_table_placeholders` wiring, `decision_subject` junction
    wiring, and the final `repair_candidate` pass -- is IDENTICAL to
    `merge_archive_candidate`, unmodified, and applies exactly as
    correctly to a full-candidate row as to an owner-tagged one, since
    none of it depends on why a row is being included, only on what
    table/column it's on."""
    return _merge_archive_candidate_impl(archive, records, case_study, include_all_rows=True)


def _merge_archive_candidate_impl(archive, records, case_study, include_all_rows):
    """Builds ONE consistent `(candidate, focal_maps)` by merging, for
    EVERY objective the archive ever covered (fitness 0.0), just that
    objective's own rows from its own best-ever individual -- see this
    section's own module comment for why this is a fundamentally
    different (and structurally more promising) strategy than picking
    one individual out of the final population.

    For each covered record, two DIFFERENT kinds of "own rows" are
    merged in, and -- a real bug found and fixed while building this
    (2026-09-13) -- they must NEVER be conflated:

    1. This record's own dedicated FOCAL rows (`focal_maps[record_id]`,
       exactly the dict `_focal_for_read` would return) -- copied via
       IDENTITY correspondence (`get_copy`) directly into
       `merged_focal_maps[record_id]`, so a later `evaluate_objective`
       call against the merged whole looks up EXACTLY this record's own
       context row, never any other row that merely happens to sit on
       the same table.
    2. Every OTHER row anywhere in the archived candidate tagged
       `_OWNER_KEY == record_id` (covers `derived_aggregate`/`exists`/
       `derived_join_count` kinds, which read a whole SET of rows, not
       one focal row) -- merged into the shared candidate too, but
       NEVER assigned into `merged_focal_maps`.

    The bug: an earlier version funneled BOTH kinds through one combined
    list and reassigned `merged_focal_maps[record_id][table] = row_copy`
    for ANY owned row sitting on a table this record ALSO has a focal
    row for -- so a `derived_join_count` record's own second
    COURSE_REGISTRATION row (the prerequisite's own passing-grade row,
    added by `_apply_row_count_mutation`'s row-ADD path, tagged for this
    same owner but never the dedicated focal row) silently overwrote the
    TRUE focal row (the "this student/this course" context row
    `_find_focal_with_columns` must resolve against) the moment both
    rows lived in the same table -- confirmed directly: `unmetPrerequisite
    Count` read back as 0 instead of the correct 1 after merging, because
    `_find_focal_with_columns` was handed the wrong row as context.
    Fixed by keeping the two loops separate, as above -- `merged_focal_maps`
    is now built ONLY from `focal_maps.get(record_id, {}).items()`,
    never from the owner-tag scan.

    All rows are copied (never aliased -- an archived individual may
    still be referenced elsewhere, e.g. by another record that shares
    the exact same best-ever individual, and must never be mutated by
    this merge or by the `repair_candidate` pass at the end), via a
    GLOBAL `id_to_copy` correspondence so a row shared between two
    DIFFERENT covered records' own archived individuals (the same
    physical row, if a single crossover child happened to be the
    best-ever answer for BOTH at once) is merged in exactly once, not
    duplicated -- the same "no fresh key manufactured where none is
    needed" discipline `_seed_shared_population` already follows for the
    analogous seeding case.

    `repair_candidate` runs exactly ONCE, on the fully assembled whole,
    at the end -- each covered record's own rows were already
    schema-legal in isolation, but a table now holding rows merged in
    from MANY different, independently-evolved individuals was never
    validated as a single combined whole before this, and a value one
    objective's own row references (e.g. a foreign key) may have no
    matching parent among what got merged in from every OTHER objective.
    `_repair_row` only ever ADDS a missing NOT NULL/FK value, never
    overwrites one already present, so no covered objective's own
    carefully-tuned value is at risk from this pass -- verified by the
    caller re-evaluating every objective against the result rather than
    assumed here.

    `merged_scenario_maps` (2026-09-13's own per-individual scenario fix)
    is built the same simple way for every covered record: a plain copy
    of that record's own scenario dict, taken directly from its own
    archived individual's `scenario_maps[record_id]` -- no identity-based
    deduplication needed here the way rows need it, since a scenario
    dict is never physically shared or aliased across different records
    the way a candidate row can be.

    **Merge-time re-offsetting (2026-09-13) -- a real PK/UNIQUE-collision
    bug found running this pipeline against jBilling for the first
    time**: two DIFFERENT covered objectives' own archived individuals
    can each independently synthesize the SAME small "fresh" key value
    (e.g. `id=1`) for a LAZILY-created row (one `_focal_for_mutate`
    creates fresh mid-run, never touched by `_seed_shared_population`'s
    own seed-time offsetting) -- `_fresh_key_value`'s own "max existing
    value in THIS candidate, plus one" is scoped to one individual's own
    candidate, with no way to know what value some OTHER, entirely
    separate individual (from a different objective's own archive entry)
    already used for the same table. Confirmed directly: jBilling's own
    `BASE_USER`/`PURCHASE_ORDER` tables both had multiple covered
    objectives' own rows independently landing on `id=1`, a real
    `UNIQUE constraint failed` once merged (up to 4-way on
    `PURCHASE_ORDER`, not just 2).

    Fixed by giving every covered record's own ENTIRE bundle of rows
    (focal + owner-tagged) a fresh, per-objective-unique offset,
    reusing `_seed_shared_population`'s own exact mechanism
    (`_key_columns_for` + `_SEED_KEY_OFFSET_UNIT`) rather than
    inventing a new one: `i * _SEED_KEY_OFFSET_UNIT` for this record's
    own index `i` in `records` (the same list, same order,
    `run_dynamosa` already seeded from) is added to every PK/UNIQUE/FK
    column value in every row this record contributes, AND to every
    numeric `scenario` value (mirroring `_seed_shared_population`'s own
    reason: a `derived_aggregate` seed row can set a key column directly
    FROM a matching scenario placeholder, e.g. `ROLL_NO = <student>` ->
    `row['ROLL_NO'] = scenario['student']` -- shifting one without the
    other would break that equality). Applying the SAME per-record
    offset to a row that already carries a seed-time offset only makes
    it larger, still uniquely identifying that same objective's own key
    space (no new collision risk: `i` is unique per record, and
    `_SEED_KEY_OFFSET_UNIT` dwarfs any realistic search-induced delta);
    applying it to a NEVER-offset lazily-created row (like the `id=1`
    case above) moves it into that exact same, guaranteed-unique-per
    -objective range for the first time. A row referencing something
    OUTSIDE this record's own bundle (e.g. an untagged parent row from
    the archived individual's own prior repair pass, dropped during this
    merge same as before) was already going to need `repair_candidate`'s
    own FK-stub synthesis regardless of this fix -- offsetting changes
    WHICH number a dangling reference points at, never WHETHER repair
    needs to handle it.

    **A THIRD real bug found the same day, testing jBilling again right
    after the `used_key_values` fix above**: `entity_id` on
    `CURRENCY_EXCHANGE` is a plain business-value column, never declared
    PK/UNIQUE/FK in this schema extraction, yet `_row_from_filter_conjuncts`
    copies a scenario placeholder's value straight into it exactly the
    same way it copies a genuine FK placeholder (`row['entity_id'] =
    scenario['entity_id']`) -- `_key_columns_for`'s own offsetting above
    never touches it, so once `rec_scenario['entity_id']` is offset
    below, the row's own already-frozen copy silently falls out of sync,
    and the `exists`-kind filter predicate's equality check
    (`entity_id = <entity_id>`) breaks post-merge (confirmed directly:
    `Currency Exchange Rate Source::Rule_1` regressed exactly this way --
    its own `hasEntitySpecificExchange` row matched pre-merge, using the
    RUN's own already-offset scenario value, then stopped matching once
    merge applied a SECOND offset to scenario alone). Fixed by having
    `get_copy` also offset any column `_filter_columns_needing_offset`
    names -- STRUCTURALLY, by parsing which columns some leaf's own
    `filter_text` actually binds to an offsettable placeholder, not by
    comparing values: a first version of this fix matched by value
    instead (any numeric column whose CURRENT value happened to equal
    one of the record's own scenario values) and immediately produced a
    much WORSE regression re-testing FLEX2 -- 25 objectives broke,
    unrelated business-value columns that merely happened to coincide
    with some other placeholder's small raw value got wrongly bumped.
    The structural, filter_text-driven version covers every column a
    leaf's own filter actually reads, without ever touching a column
    that just happens to share a number.

    Returns (merged_candidate, merged_focal_maps, merged_scenario_maps,
    covered_record_ids) -- `covered_record_ids` is the archive's own view
    of what SHOULD be covered; it is the caller's job (`generate_dataset.py`)
    to re-`evaluate_objective` every one of them against the actual
    merged, repaired result and report the real, verified number, not
    this expected one, honestly side by side."""
    schema = _schema_for(case_study)
    merged = Candidate()
    merged_focal_maps = {}
    merged_scenario_maps = {}
    id_to_copy = {}
    covered_record_ids = set()
    # (table, column) -> every post-offset key value already assigned --
    # a second, real bug found the same day as the offsetting fix itself
    # (running this against jBilling's own `exists`-kind filter fix,
    # 2026-09-13): the per-record offset above prevents CROSS-record
    # collisions, but a SINGLE record can legitimately own MULTIPLE rows
    # on the SAME table (e.g. `Currency Exchange Rate Source::Rule_2`
    # owns both its own entity-specific and system-default
    # `currency_exchange` rows), and each was independently repaired --
    # possibly at completely different points in its own mutation
    # history -- via `_fresh_key_value`'s own "max existing in THIS
    # candidate, right now" logic, which can hand out the SAME small
    # value (`id=1`) to both if neither saw the other yet at the moment
    # it was repaired. The uniform per-record offset shifts BOTH by the
    # identical amount, so they still collide with EACH OTHER after
    # merging -- confirmed directly: two of `Rule_2`'s own
    # `CURRENCY_EXCHANGE` rows both had `id=1` pre-merge. Tracked here,
    # globally, not per-record: cross-record collisions are already
    # structurally impossible once offset (different records occupy
    # disjoint `_SEED_KEY_OFFSET_UNIT`-wide ranges), so this only ever
    # actually fires for a same-record, same-table, same-column clash.
    used_key_values = {}

    def get_copy(table, row, offset, filter_cols=frozenset(), join_cols=frozenset()):
        key = id(row)
        row_copy = id_to_copy.get(key)
        if row_copy is None:
            row_copy = dict(row)
            if offset:
                key_cols = _key_columns_for(schema, table)
                unique_cols = _own_solo_unique_columns_for(schema, table)
                for col in list(row_copy):
                    val = row_copy[col]
                    if not isinstance(val, (int, float)) or isinstance(val, bool):
                        continue
                    if col.upper() in key_cols:
                        new_val = val + offset
                        # Only a genuine PK/UNIQUE column gets dedup-bumped
                        # on a same-record, same-table clash -- an FK
                        # column (in key_cols for the OFFSET shift above,
                        # never here) can legitimately repeat identically
                        # across this record's own rows (see
                        # `_own_unique_columns_for`'s own docstring).
                        if col.upper() in unique_cols:
                            used = used_key_values.setdefault((table.upper(), col.upper()), set())
                            while new_val in used:
                                new_val += 1
                            used.add(new_val)
                        row_copy[col] = new_val
                    elif col.upper() in filter_cols and val in filter_cols[col.upper()]:
                        # Not a declared PK/UNIQUE/FK column, but some
                        # leaf's own filter_text structurally binds it to
                        # an offsettable scenario placeholder (see
                        # `_filter_columns_needing_offset`'s own
                        # docstring) -- `_row_from_filter_conjuncts`
                        # copies that placeholder's value straight into
                        # this column the exact same way it does for a
                        # declared-key column, so it must move by the
                        # identical offset the matching scenario key is
                        # about to get below, or the `exists`-kind filter
                        # predicate's own equality check breaks post-merge
                        # (confirmed directly: `Currency Exchange Rate
                        # Source::Rule_1`'s own `entity_id`, never
                        # declared PK/FK in this schema extraction). The
                        # column-name check alone is NOT enough -- `val
                        # in filter_cols[col.upper()]` additionally
                        # requires THIS row's own current value to
                        # actually equal the record's own pre-merge
                        # scenario value for one of the placeholders that
                        # bind this column, or a DIFFERENT leaf's own
                        # literal on the SAME column name (e.g. `Rule_2`'s
                        # own `entity_id = 0` for `hasSystemDefaultExchange`,
                        # sharing the table with `hasEntitySpecificExchange`'s
                        # `entity_id = <entity_id>`) gets wrongly offset
                        # too (confirmed directly: an earlier, column
                        # -name-only version of this check corrupted
                        # exactly that literal 0).
                        row_copy[col] = val + offset
                    elif (table.upper(), col.upper()) in join_cols \
                            and val in join_cols[(table.upper(), col.upper())]:
                        # Not a declared PK/UNIQUE/FK column on THIS
                        # table, but some `join_lookup`/`join_null_check`
                        # leaf keeps it numerically equal to a DIFFERENT
                        # row's own FK column by construction (see
                        # `_join_lookup_pairs`'s own docstring) -- e.g.
                        # `encounter.encounter_datetime` doubling as
                        # `orders.encounter_id`'s own synthetic join
                        # target. Table-scoped (unlike `filter_cols`,
                        # which is deliberately cross-table by column
                        # name alone) since this correspondence is
                        # inherently between two SPECIFIC, different
                        # tables, not just a column name.
                        row_copy[col] = val + offset
                _dedup_composite_keys(schema, table, row_copy, used_key_values, case_study)
            merged.add_row(table, row_copy)
            id_to_copy[key] = row_copy
        return row_copy

    for i, r in enumerate(records):
        rid = r['record_id']
        fitness, individual = archive.get(rid, (float('inf'), None))
        if fitness != 0.0 or individual is None:
            continue
        covered_record_ids.add(rid)
        candidate, focal_maps, scenario_maps = individual
        offset = i * _SEED_KEY_OFFSET_UNIT
        raw_scenario = scenario_maps.get(rid, {})
        rec_scenario = dict(raw_scenario)
        offsettable_keys = _scenario_keys_needing_offset(r)
        # {COLUMN -> {this record's own current values for every
        # placeholder some leaf binds it to}} -- the actual per-row
        # value check `get_copy` needs (see `_filter_columns_needing_
        # offset`'s own docstring for why the column name alone isn't
        # enough).
        filter_cols = {
            col: {raw_scenario[ph] for ph in phs
                  if ph in raw_scenario and isinstance(raw_scenario[ph], (int, float))
                  and not isinstance(raw_scenario[ph], bool)}
            for col, phs in _filter_columns_needing_offset(r).items()
        }
        for key, val in rec_scenario.items():
            if key in offsettable_keys and isinstance(val, (int, float)) and not isinstance(val, bool):
                rec_scenario[key] = val + offset
        merged_scenario_maps[rid] = rec_scenario

        # {(result_table, result_column) -> {this record's own current
        # FK values a join_lookup/join_null_check leaf expects it to
        # equal}} -- read from the record's own RAW, pre-copy focal rows
        # (never touched by get_copy), so this reflects exactly what the
        # archived individual actually had, regardless of processing
        # order below (see `_join_lookup_pairs`'s own docstring).
        rec_focal_raw = focal_maps.get(rid, {})
        join_cols = {}
        for local_table, local_column, result_table, result_column in _join_lookup_pairs(r):
            local_row = rec_focal_raw.get(local_table.upper())
            if local_row is None:
                continue
            lv = local_row.get(local_column)
            if isinstance(lv, (int, float)) and not isinstance(lv, bool):
                join_cols.setdefault((result_table.upper(), result_column.upper()), set()).add(lv)

        # (1) This record's own dedicated focal rows -- by identity,
        # never by "which table," so a different owned row on the same
        # table can never be mistaken for it (see this function's own
        # docstring for the real bug this fixes).
        merged_rec_focal = {}
        for table, row in rec_focal_raw.items():
            merged_rec_focal[table] = get_copy(table, row, offset, filter_cols, join_cols)

        # (2) Every OTHER row this record owns anywhere in the candidate
        # (derived_aggregate/exists/derived_join_count's own row SETs) --
        # merged in for scanning, deliberately never touching
        # merged_rec_focal. `include_all_rows` (merge_archive_candidate_full's
        # own toggle, see its docstring) widens this from "only this
        # record's own owner-tagged rows" to literally every row of this
        # record's own candidate, including the untouched shared-seed
        # rows it also carries a copy of -- get_copy's own id_to_copy
        # memoization (keyed by row IDENTITY) means a row already copied
        # via merged_rec_focal above is never processed twice here,
        # whichever mode this is.
        for table, table_rows in candidate.as_dict().items():
            for row in table_rows:
                if include_all_rows or row.get(_OWNER_KEY) == rid:
                    get_copy(table, row, offset, filter_cols, join_cols)

        if merged_rec_focal:
            merged_focal_maps[rid] = merged_rec_focal

        # (3) Filter_text placeholder correlations (2026-09-24/25) --
        # `compile_constraints.py`'s own `cross_table_placeholders` field
        # (computed alongside `decision_subject`, same file, same
        # generator-owned-mirror rationale), fed by two distinct
        # compile-time sources sharing one field/consumer:
        #
        #   (a) a placeholder `filter_placeholder_sources.py` declares a
        #       source table for (e.g. `<program>` -> `STUDENT_PROGRAM`);
        #   (b) a placeholder whose own conjunct COLUMN matches the
        #       decision's own subject row's real FK column (e.g.
        #       `<COURSE_ID>`, via `COURSE_REGISTRATION.COURSE_ID` ->
        #       `COURSE.COURSE_ID`) -- the validator resolves this kind
        #       directly off the subject row itself, its own FIRST
        #       priority, never even reaching `filter_placeholder_
        #       sources.py`.
        #
        # Both share the same underlying bug shape: a `derived_aggregate`/
        # `exists` node's own filter_text binds a placeholder (e.g.
        # `<program>`, `<COURSE_ID>`) to a column search treats as an
        # ordinary, independently-tunable `scenario` scalar -- but the
        # SAME real-world fact also needs to equal this SAME record's own
        # value on a DIFFERENT table. Nothing in `candidate.py`'s own
        # seeding/mutation or `fitness.py`'s own evaluation ever makes
        # that connection -- confirmed real for BOTH: FLEX2's `Course
        # Replacement Eligibility::degreeTotalCredits` correctly keeps
        # `PROGRAM_COURSE.PROG_ID` equal to `scenario['program']`
        # throughout search (both shift together under the SAME offset),
        # while `STUDENT_PROGRAM.PROG_ID` -- never independently set by
        # any leaf -- ends up a plain, generic NOT-NULL repair
        # placeholder instead; `Rule_4`'s own
        # `courseOfferedInFollowingSemesters` correctly keeps
        # `COURSE_OFFER.COURSE_ID` equal to `scenario['COURSE_ID']` the
        # same way, while `COURSE.COURSE_ID` -- never independently set
        # by any leaf either, since `courseTypeId`'s own `course_type_id`
        # read needs no placeholder at all -- only ever gets a value from
        # a GLOBAL fresh-key repair, unrelated to either.
        #
        # Copying the record's own (already-offset) scenario value onto
        # the correlated table's own column HERE, before `repair_
        # candidate` runs below, means that later generic fallback never
        # fires for it (its own guard already skips any column that
        # already has a real value) -- a post-search correction, not a
        # search-loop, fitness, or mutation-operator change. Deliberately
        # placed BEFORE (4)'s own subject-junction wiring below, not
        # after: for the (b) shape, the correlated table (`COURSE`) is
        # often the SAME table a subject hop reads FROM to wire the
        # subject row itself -- running this first means (4) sees the
        # corrected value and correctly propagates it onto the subject
        # row too, rather than locking in its own fresh key first and
        # leaving this step to fix a value nothing downstream still
        # reads. Synthesizes a fresh row for the correlated table the
        # same way (4) does for a missing hop target, for the same
        # reason: nothing else in this record may have built one yet
        # (confirmed real for the (b) shape specifically: a record using
        # ONLY the `exists` leaf and no other leaf on that table).
        #
        # A real collision found testing the (b) shape (2026-09-25):
        # when the correlated column is the target table's own PK/UNIQUE
        # key (e.g. `COURSE.COURSE_ID`), writing `scenario[placeholder]`
        # onto it can coincidentally equal a value some OTHER row this
        # SAME record independently owns on that SAME table already
        # holds -- confirmed real for `Course Replacement Eligibility`'s
        # own `Rule_4`/`Rule_5`/`Rule_6`: `degreeTotalCredits`'s own
        # `derived_aggregate` seeding (candidate.py's `joined_value_table`
        # branch) builds 3 of its OWN separate `COURSE` rows for the SAME
        # record, numbered `1, 2, 3` pre-offset -- the SAME starting
        # point `<COURSE_ID>`'s own scenario default uses, so after the
        # SAME per-record offset, the FIRST of those 3 rows and the
        # correlated focal row can land on the identical `COURSE_ID`,
        # a real `UNIQUE constraint failed` `_fill_missing_surrogate_
        # keys`/materialize.py would only catch much later. Detected and
        # resolved here instead, immediately: if `column` is a genuine
        # PK/UNIQUE key for `table` and the value now collides with a
        # DIFFERENT row already in `merged`, that OTHER row (never the
        # semantically-required correlated one) is bumped to a fresh,
        # collision-safe value the same way `mutation.py`'s own
        # `_fresh_key_value` already resolves every other such clash.
        for node in r.get('variable_resolution', {}).values():
            if not isinstance(node, dict):
                continue
            for placeholder, source in (node.get('cross_table_placeholders') or {}).items():
                value = rec_scenario.get(placeholder)
                if value is None:
                    continue
                target_focal = merged_rec_focal.get(source['table']) or next(
                    (v for k, v in merged_rec_focal.items() if k.upper() == source['table'].upper()), None)
                if target_focal is None:
                    target_focal = merged.add_row(source['table'], {_OWNER_KEY: rid})
                    merged_rec_focal[source['table']] = target_focal
                    merged_focal_maps[rid] = merged_rec_focal
                target_focal[source['column']] = value
                if source['column'].upper() in _own_solo_unique_columns_for(schema, source['table']):
                    for other_row in merged.rows(source['table']):
                        if other_row is not target_focal and other_row.get(source['column']) == value:
                            other_row[source['column']] = _fresh_key_value(merged, source['table'], source['column'])

        # (4) The decision's own real DMN subject row (2026-09-24) --
        # `compile_constraints.py`'s own `decision_subject` field (a
        # generator-owned port of `validation_oracle/subject_table.py`'s
        # algorithm, computed once at compile time -- see that module's
        # own docstring for why a port, not an import). No leaf variable
        # ever needs this row DURING search (fitness never reads it), so
        # this is deliberately the ONLY place it gets built -- a
        # one-time, post-search synthesis step, not a change to the
        # population loop, mutation, or fitness at all.
        #
        # Found real, not hypothetical: a decision whose real subject is
        # a pure junction/link table no leaf ever reads directly (e.g.
        # FLEX2's `Course Load Limit` -- reads only `SEMESTER`/
        # `STUDENT_PROGRAM`, no FK between them at all, real subject
        # `STUDENT_SEMESTER`) never got this row built at all before this
        # fix: every individual fact could be independently correct, but
        # nothing ever tied them together as "the same real case," so
        # independent verification could never find a corresponding
        # subject to enumerate.
        #
        # A SECOND, related gap (found 2026-09-24, same day, fixing
        # FLEX2's `Course Replacement Eligibility`): the subject table
        # can ALREADY be among this record's own focal rows -- built
        # naturally because SOME leaf reads directly off it (e.g.
        # `gradeInCourseToReplace` on `COURSE_REGISTRATION`) -- while a
        # DIFFERENT leaf of the SAME record ALSO builds its own separate
        # dedicated row on ANOTHER table the subject needs to link
        # through (e.g. `creditsEarned` on `STUDENT_PROGRAM`). Nothing
        # ever wired the subject row's own FK column to that sibling
        # row's PK in this case -- the ORIGINAL version of this fix only
        # ran when the subject row was missing ENTIRELY, so an
        # already-present-but-unlinked subject row silently kept a NULL
        # FK forever. Confirmed real: `Rule_3`'s own solved candidate has
        # its own `COURSE_REGISTRATION` AND `STUDENT_PROGRAM` rows, each
        # independently correct, but `ROLL_NO` was never copied from one
        # to the other, so the validator's own live join always saw
        # `creditsEarned=None`. Below now wires every `subject['joins']`
        # hop onto the subject row REGARDLESS of whether that row already
        # existed, skipping only a hop whose own FK column the subject
        # row already has a real value for (never overwritten).
        _build_decision_subject_row(merged, merged_rec_focal, r, rid)
        merged_focal_maps[rid] = merged_rec_focal

    repair_candidate(merged, case_study)
    return merged, merged_focal_maps, merged_scenario_maps, covered_record_ids


if __name__ == '__main__':
    import json
    import time

    compiled = json.load(open(os.path.join(HERE, 'compiled_constraints.json')))

    def find(suffix):
        return next(r for r in compiled if r['record_id'].endswith(suffix))

    # A small, deliberately mixed slice: two root objectives (Academic
    # Warning Status has no upstream dependency at all) and two objectives
    # chained on them (Course Load Limit::Rule_1, via each of those same
    # two roots) -- real DRD data, not synthesized, exercising activation
    # gating on a case genuinely present in the corpus.
    records = [
        find('Decision_AcademicWarningStatus_Rule_1'),
        find('Decision_AcademicWarningStatus_Rule_2'),
        find('Decision_CourseLoadLimit_Rule_1::via::Academic Warning Status::Decision_AcademicWarningStatus_Rule_1'),
        find('Decision_CourseLoadLimit_Rule_1::via::Academic Warning Status::Decision_AcademicWarningStatus_Rule_2'),
    ]
    for r in records:
        print(f"  {r['record_id']} <- {r.get('grounded_upstream_branches')}")

    start = time.time()
    rng = random.Random(0)
    archive, coverage_history, _final_population = run_dynamosa(
        records, 'FLEX2', population_size=12, generations=25, rng=rng)
    elapsed = time.time() - start

    print(f"\nCoverage history across {len(coverage_history)} generations: {coverage_history}")
    print(f"Elapsed: {elapsed:.1f}s for {len(records)} objectives, population 12, 25 generations")
    for r in records:
        f, _c = archive.get(r['record_id'], (float('inf'), None))
        print(f"  {'COVERED' if f == 0.0 else f'fitness={f:.4f}'}  {r['record_id']}")

    assert all(coverage_history[i] <= coverage_history[i + 1] for i in range(len(coverage_history) - 1)), \
        "the archive's own covered-count must never regress across generations"
    print("\nConfirmed: coverage is monotonically non-decreasing (the archive never regresses).")

    # DRD-gating invariant: any covered chained objective's own dependency
    # must ALSO be covered -- if this ever fails, activation gating is
    # broken (a chained target got credit without its prerequisite).
    covered_keys = {_branch_key(r) for r in records if archive.get(r['record_id'], (float('inf'), None))[0] == 0.0}
    for r in records:
        if archive.get(r['record_id'], (float('inf'), None))[0] == 0.0:
            deps = r.get('grounded_upstream_branches') or []
            for d in deps:
                assert d in covered_keys, (
                    f"{r['record_id']} was covered but its own dependency {d!r} was not -- "
                    f"DRD activation gating is broken")
    print("Confirmed: every covered chained objective's own DRD dependency was covered too (gating is real, not bypassed).")

    print(f"\nCovered {sum(1 for r in records if archive.get(r['record_id'], (float('inf'), None))[0] == 0.0)}"
          f"/{len(records)} objectives via the shared population.")

    # merge_archive_candidate self-test: on this same small, real archive,
    # merging every covered objective's own best-ever rows must reproduce
    # AT LEAST the same covered set the archive itself claims -- verified
    # by re-evaluating every objective against the actual merged, repaired
    # result, never assumed correct just because the rows came from an
    # already-solved individual (see merge_archive_candidate's own
    # docstring on why a repair pass run on the merged whole could, in
    # principle, still disturb an objective's own aggregate/exists count).
    # No separate scenario_cache needed here anymore (2026-09-13's own
    # per-individual scenario fix) -- merge_archive_candidate's own
    # merged_scenario_maps already carries each record's own scenario,
    # taken directly from its own archived individual.
    table_cache = {}
    merged_candidate, merged_focal_maps, merged_scenario_maps, expected_covered = merge_archive_candidate(
        archive, records, 'FLEX2')
    actual_covered = {r['record_id'] for r in records
                       if evaluate_objective(r, merged_candidate, merged_focal_maps,
                                              merged_scenario_maps, table_cache) == 0.0}
    regressions = expected_covered - actual_covered
    assert not regressions, f"merge_archive_candidate regressed: {regressions}"
    assert actual_covered == {r['record_id'] for r in records
                               if archive.get(r['record_id'], (float('inf'), None))[0] == 0.0}, \
        "merged-archive coverage should exactly match the archive's own covered set on this small example"
    print(f"Confirmed: merge_archive_candidate reproduces the archive's own {len(expected_covered)}/{len(records)} "
          f"covered objectives simultaneously in ONE merged, repaired candidate -- zero regressions.")

