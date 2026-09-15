"""crossover.py -- the crossover operator (design doc §6.4's DynaMOSA,
the other half of one generational step of it, alongside mutation.py's
mutate()/hillclimb()).

**Uniform table-mask crossover.** Recombines two parent `Candidate`s
(§6.2's `{table: [row, ...]}` representation) into two complementary
children by choosing, independently per table, which parent's *entire*
row-set for that table the child inherits -- a coin flip per table, the
same "uniform crossover" discipline a GA applies per-locus to a
fixed-length chromosome, except the locus here is a whole table's
row-list, not a scalar gene.

Why table, not row, is the unit of recombination: individual rows across
two unrelated parent candidates have no stable identity to align
gene-by-gene the way two same-length chromosomes would -- parent1's 5th
`STUDENT_ATTENDANCE` row and parent2's 5th are arbitrary, unrelated list
entries, not homologous genes there's any principled way to pair up. A
whole table's row-set, by contrast, is a clean, atomic, well-defined unit
every candidate shares regardless of population history -- exactly the
"table-mask" shape this operator was specified as, back when mutation.py
was built first (mutation converges on real branches by itself and is
independently testable; crossover only pays off once a population of
diverse candidates already exists to recombine -- §6.4's own reasoning
for building mutation before this).

**Mandatory FK-repair pass.** Swapping a table's row-set wholesale from a
different parent very often leaves a dangling FK -- e.g. the child's
`STUDENT_ATTENDANCE` rows, inherited from parent1, reference `LECTURE_ID`
values that only exist in parent1's own `LECTURE` rows, but the child
took `LECTURE` from parent2. This reuses `mutation.py`'s own
`_repair_row` directly -- the same schema-legal-by-construction discipline
mutation's M1/M2 already apply after every row they touch (2026-09-12,
found necessary the same way: NOT NULL/UNIQUE/FK are mechanically
decidable from the schema alone, so they're fixed by construction, never
left for a fitness term to maybe discover) -- not a second, competing
repair mechanism. Reusing it here means a crossover child and a mutation
child are schema-legal by the exact same rule, not two independently
-maintained notions of "valid."

Two children, not one: standard uniform-crossover practice -- the
complementary table mask is applied too, so no parent material is
discarded.

Usage:
    from crossover import crossover
    child1, child2, f1, f2, fm1, fm2, sm1, sm2 = crossover(parent1, parent2, case_study, rng)
"""
import copy
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from candidate import Candidate  # noqa: E402
from mutation import _repair_row  # noqa: E402 -- reused, not reimplemented


def crossover(parent1, parent2, case_study, rng=None, focal1=None, focal2=None,
              focal_maps1=None, focal_maps2=None, scenario_maps1=None, scenario_maps2=None):
    """Uniform table-mask crossover with mandatory FK-repair. Returns
    (child1, child2, child_focal1, child_focal2, child_focal_maps1,
    child_focal_maps2, child_scenario_maps1, child_scenario_maps2) --
    complementary children built from the same mask and its inverse, each
    independently repaired for NOT NULL/FK by construction. Neither
    parent is mutated (each row is deep-copied into its child, the same
    "parents are never touched" discipline mutation.py's own mutate()
    follows).

    `scenario_maps1`/`scenario_maps2` (optional -- default `{}`,
    2026-09-13, dynamosa.py's own per-individual scenario fix) are
    dynamosa.py's own `{record_id: scenario}` per-objective bind-parameter
    state -- NOT recombined by the table mask at all, unlike focal:
    a `not_persisted` variable (e.g. `purchaseQuantity`) belongs entirely
    to ONE record's own resolution and is never physically shared or
    aliased across records or tables the way a candidate row can be, so
    there is no "which parent supplied this table" question to answer
    for it. Each child simply inherits its own originating parent's own
    scenario_maps wholesale (deep-copied, parents untouched) --
    `child_scenario_maps1` from `parent1`'s own `scenario_maps1`,
    `child_scenario_maps2` from `parent2`'s own `scenario_maps2` --
    exactly mirroring which parent's OWN candidate/focal each child is
    itself built to diverge from, even though individual tables within
    that child may still come from the OTHER parent via the mask below.

    `focal1`/`focal2` (optional -- default `{}`, in which case the
    returned child focals are also `{}`) are the per-branch "which row is
    *this* one" views mutation.py's own mutate()/hillclimb() need to keep
    operating on the result -- added when wiring crossover into a real
    escalation loop (2026-09-12): a focal row for a table that swaps
    parents must swap with it (whichever parent supplied a table's rows
    also supplies that table's focal row), copied via the SAME joint
    `copy.deepcopy` call as that table's own row list -- exactly
    mutation.py's own `(candidate, focal)` aliasing fix, applied here too,
    since a focal row is frequently the identical object as one of that
    table's own rows and copying them apart would silently break that.

    `focal_maps1`/`focal_maps2` (optional -- default `{}`) generalize the
    same idea to dynamosa.py's own shared-population representation,
    where a SINGLE candidate carries not one but MANY objectives' own
    dedicated focal rows at once (`{record_id: {table: row}}`, added
    2026-09-12 building the focal-per-objective refinement -- see
    dynamosa.py's own module docstring): every record's own entry for a
    table that swaps parents must swap with it too, exactly like
    `focal1`/`focal2` above, just for every record_id at once rather than
    one. Still one joint `copy.deepcopy` call per table -- covering that
    table's row list AND every record's own focal entry for it
    together -- since a dedicated focal row is frequently the identical
    object as one of that table's own rows (by construction -- see
    dynamosa.py's own `_focal_for_mutate`), and copying them apart would
    silently break that the same way splitting `focal1` from a table's
    rows would."""
    rng = rng or random
    focal1, focal2 = focal1 or {}, focal2 or {}
    focal_maps1, focal_maps2 = focal_maps1 or {}, focal_maps2 or {}
    scenario_maps1, scenario_maps2 = scenario_maps1 or {}, scenario_maps2 or {}
    record_ids = sorted(set(focal_maps1) | set(focal_maps2))
    # sorted(), not a raw set iteration -- found necessary while testing
    # (2026-09-12): Python's string hashing is randomized per process by
    # default, so iterating a bare `set` of table names visits them in a
    # different order across runs, meaning the *same* rng seed would
    # silently produce a *different* table mask (and therefore a
    # different crossover result) depending on process-level hash
    # randomization alone -- a real reproducibility bug for anything that
    # needs a deterministic replay from a fixed seed (as a search run
    # generally does).
    tables = sorted(set(parent1.as_dict()) | set(parent2.as_dict()) | set(focal1) | set(focal2)
                     | {t for fm in focal_maps1.values() for t in fm}
                     | {t for fm in focal_maps2.values() for t in fm})
    from_parent1 = {table: rng.random() < 0.5 for table in tables}

    def build(mask):
        child = Candidate()
        child_focal = {}
        child_focal_maps = {rid: {} for rid in record_ids}
        for table in tables:
            if mask[table]:
                source, source_focal, source_focal_maps = parent1, focal1, focal_maps1
            else:
                source, source_focal, source_focal_maps = parent2, focal2, focal_maps2
            per_record_entries = {rid: source_focal_maps[rid][table]
                                   for rid in record_ids
                                   if table in source_focal_maps.get(rid, {})}
            rows_copy, focal_copy, per_record_copy = copy.deepcopy(
                (source.rows(table), source_focal.get(table), per_record_entries))
            for row in rows_copy:
                child.add_row(table, row)
            if focal_copy is not None:
                child_focal[table] = focal_copy
            for rid, row_copy in per_record_copy.items():
                child_focal_maps[rid][table] = row_copy
        return child, child_focal, child_focal_maps

    inverted = {table: not v for table, v in from_parent1.items()}
    (child1, child_focal1, child_focal_maps1), (child2, child_focal2, child_focal_maps2) = (
        build(from_parent1), build(inverted))

    # Scenario is never table-shaped -- each child simply inherits its
    # own originating parent's own scenario_maps wholesale (deep-copied,
    # parent untouched), mirroring which parent build(from_parent1) vs
    # build(inverted) each child itself defaults to.
    child_scenario_maps1 = copy.deepcopy(scenario_maps1)
    child_scenario_maps2 = copy.deepcopy(scenario_maps2)

    for child in (child1, child2):
        # list(...) snapshots, not a live dict view -- a real bug found
        # testing search.py's escalation loop (2026-09-12): _repair_row's
        # FK-repair branch can add a brand-new table key to `child`
        # (synthesizing a minimal parent row for a table the mask never
        # selected at all), which raises "dictionary changed size during
        # iteration" if this loop is still iterating child.as_dict()
        # live. Safe to snapshot rather than also visit newly-added
        # tables: any row _repair_row itself creates is already repaired
        # recursively before it returns (see _repair_row's own
        # docstring), so there is nothing left for this outer loop to do
        # for a table it never touches directly.
        for table, rows in list(child.as_dict().items()):
            for row in list(rows):
                _repair_row(child, table, row, case_study)
    return (child1, child2, child_focal1, child_focal2, child_focal_maps1, child_focal_maps2,
            child_scenario_maps1, child_scenario_maps2)


if __name__ == '__main__':
    # A deliberate FK-crossing scenario: two independently-valid parents
    # that share no row identity across their crossed-over tables, so
    # crossover's own table swap is *guaranteed* to produce a dangling FK
    # somewhere -- not a hopeful example that happens to work out.
    import json
    from fitness import branch_fitness, candidate_constraint_fitness
    from candidate import derive_genome
    from mutation import _schema_for

    data = json.load(open(os.path.join(HERE, 'compiled_constraints.json')))
    rule2 = next(r for r in data if r['record_id'].endswith('Decision_AttendanceEligibility_Rule_2'))
    schema = _schema_for('FLEX2')

    def make_fully_clean(candidate):
        """Every hand-seeded row here only sets the columns the DMN branch
        itself cares about -- reuses _repair_row (the same construction
        discipline mutation.py's own M1/M2 already apply) to close every
        other NOT NULL/FK gap, rather than hand-writing FLEX2's real FK
        closure (COURSE_OFFER -> CAMPUS/SEMESTER/COURSE/SECTION,
        STUDENT_PROGRAM -> PROGRAM/BATCH/..., several levels deep) by hand
        here just to build two test fixtures."""
        for table, rows in list(candidate.as_dict().items()):
            for row in list(rows):
                _repair_row(candidate, table, row, 'FLEX2')

    # Parent 1: a "low attendance" solution -- 45 lectures under OFFER_ID
    # 5001, only 30 attended (66.7% < 80%, branch_fitness == 0.0).
    p1 = Candidate()
    p1.add_row('STUDENT_PROGRAM', {'ROLL_NO': 2024001})
    p1.add_row('COURSE_OFFER', {'OFFER_ID': 5001})
    for i in range(45):
        p1.add_row('LECTURE', {'LECTURE_ID': 1000 + i, 'OFFER_ID': 5001})
    for i in range(30):
        p1.add_row('STUDENT_ATTENDANCE', {'LECTURE_ID': 1000 + i, 'ROLL_NO': 2024001, 'ATTEND_FLAG': 'Y'})
    make_fully_clean(p1)

    # Parent 2: a "few lectures" solution -- a DIFFERENT offering
    # (OFFER_ID 6002, LECTURE_IDs 2000+) with only 4 lectures, 3 attended
    # (75% < 80%, branch_fitness == 0.0). Deliberately no row-identity
    # overlap with parent1 at all.
    p2 = Candidate()
    p2.add_row('STUDENT_PROGRAM', {'ROLL_NO': 3030030})
    p2.add_row('COURSE_OFFER', {'OFFER_ID': 6002})
    for i in range(4):
        p2.add_row('LECTURE', {'LECTURE_ID': 2000 + i, 'OFFER_ID': 6002})
    for i in range(3):
        p2.add_row('STUDENT_ATTENDANCE', {'LECTURE_ID': 2000 + i, 'ROLL_NO': 3030030, 'ATTEND_FLAG': 'Y'})
    make_fully_clean(p2)

    scenario1 = {'student': 2024001, 'this course offering': 5001}
    scenario2 = {'student': 3030030, 'this course offering': 6002}
    for label, p, scenario in [('parent1', p1, scenario1), ('parent2', p2, scenario2)]:
        g = derive_genome(rule2, p, {}, scenario)
        print(f"{label}: genome={g}, branch_fitness={branch_fitness(rule2, g):.4f}, "
              f"constraint_fitness={candidate_constraint_fitness(p.as_dict(), schema):.4f}")
    assert branch_fitness(rule2, derive_genome(rule2, p1, {}, scenario1)) == 0.0
    assert branch_fitness(rule2, derive_genome(rule2, p2, {}, scenario2)) == 0.0
    assert candidate_constraint_fitness(p1.as_dict(), schema) == 0.0
    assert candidate_constraint_fitness(p2.as_dict(), schema) == 0.0
    print("Both parents independently valid: DMN-solved and schema-clean.")

    # Show the UNREPAIRED table-mask swap first -- the raw crossover
    # mechanism with no repair -- to prove the dangling FK is real, not
    # hypothetical, before showing the actual (always-repaired) operator.
    print()
    print("Unrepaired table-mask swap (STUDENT_ATTENDANCE from parent2, LECTURE from parent1):")
    raw_child = Candidate()
    for table in ('STUDENT_PROGRAM',):
        for row in p1.rows(table):
            raw_child.add_row(table, dict(row))
    for row in p1.rows('LECTURE'):
        raw_child.add_row('LECTURE', dict(row))
    for row in p2.rows('STUDENT_ATTENDANCE'):
        raw_child.add_row('STUDENT_ATTENDANCE', dict(row))
    raw_constraint_fitness = candidate_constraint_fitness(raw_child.as_dict(), schema)
    print(f"  STUDENT_ATTENDANCE rows reference LECTURE_ID {[r['LECTURE_ID'] for r in raw_child.rows('STUDENT_ATTENDANCE')]}, "
          f"but LECTURE only has {sorted(r['LECTURE_ID'] for r in raw_child.rows('LECTURE'))[:3]}...")
    print(f"  constraint_fitness (no repair) = {raw_constraint_fitness:.4f} -- a real, non-hypothetical dangling FK")
    assert raw_constraint_fitness > 0.0, "the deliberately-crossed scenario should produce a real FK gap pre-repair"

    # Now the real operator: mandatory repair included.
    print()
    print("crossover() -- with its mandatory FK-repair pass:")
    rng = random.Random(2)
    child1, child2, child_focal1, child_focal2, _fm1, _fm2, _sm1, _sm2 = crossover(p1, p2, 'FLEX2', rng)
    for label, child in [('child1', child1), ('child2', child2)]:
        cf = candidate_constraint_fitness(child.as_dict(), schema)
        print(f"  {label}: tables={sorted(child.as_dict())}, constraint_fitness={cf:.6f}")
        assert cf == 0.0, f"{label} should be fully schema-legal after repair -- got constraint_fitness={cf}"
    print("Both children fully schema-legal (NOT NULL/FK) immediately after crossover -- "
          "repair closed every gap the table swap introduced.")

    # The two children are complementary: every table came from exactly
    # one parent in child1 and the OTHER parent in child2. Only checkable
    # via content on tables where the two parents' own rows actually
    # differ -- a repair-synthesized lookup row (e.g. BATCH) can coincide
    # in content across both parents (both got _fresh_key_value's same
    # "1" starting from empty), making origin unrecoverable from content
    # alone; that's a limit of this content-based check, not of crossover
    # itself, which decides the mask before repair ever runs.
    checked = 0
    for table in sorted(set(p1.as_dict()) | set(p2.as_dict())):
        if p1.rows(table) == p2.rows(table):
            continue
        c1_from_p1 = child1.rows(table)[:len(p1.rows(table))] == p1.rows(table)
        c2_from_p1 = child2.rows(table)[:len(p1.rows(table))] == p1.rows(table)
        assert c1_from_p1 != c2_from_p1, f"{table} should come from opposite parents in the two children"
        checked += 1
    assert checked >= 4, "expected LECTURE/STUDENT_ATTENDANCE/STUDENT_PROGRAM/COURSE_OFFER to all be content-distinguishable"
    print(f"Confirmed complementary on {checked} content-distinguishable tables: each comes from "
          f"opposite parents across the two children.")

    # Parents are never mutated.
    assert len(p1.rows('LECTURE')) == 45 and len(p2.rows('LECTURE')) == 4
    print("Confirmed parents untouched by crossover.")

    # Honest final observation, not asserted either way: crossover
    # guarantees schema-legality unconditionally (just shown above), but
    # makes no promise at all about DMN branch fitness -- a child built
    # from two parents solving *different* scenarios (different student,
    # different course offering here) can easily end up with a genuinely
    # invalid genome for either parent's own scenario (e.g. the child's
    # LECTURE table came from the other parent, so this scenario's
    # OFFER_ID now matches zero lectures -- a real 0/0 division, not a
    # crash: fitness.py's own _safe_div raises a clear
    # FitnessEvaluationError instead). This is expected, ordinary GA
    # behavior -- a population's fitness improves via selection pressure
    # across many crossover events and generations, not because every
    # single recombination individually preserves it.
    print()
    print("DMN branch_fitness on each child (informative only -- crossover never promises this):")
    for label, child, scenario in [('child1', child1, scenario1), ('child2', child2, scenario2)]:
        try:
            g = derive_genome(rule2, child, {}, scenario)
            print(f"  {label} (parent1's own scenario): branch_fitness={branch_fitness(rule2, g):.4f}")
        except Exception as e:
            print(f"  {label} (parent1's own scenario): not evaluable for this scenario -- {e}")
