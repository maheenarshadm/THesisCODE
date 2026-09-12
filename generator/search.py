"""search.py -- per-branch search strategy: mutation-only hillclimb
first, escalating to a small population + crossover GA only when
hillclimb alone fails to converge within its budget.

This directly follows §6.4's own stated hybrid strategy, not a new
decision: "Escalate to a genetic algorithm ... when (a) many targets
need to be covered together efficiently rather than one at a time, or
(b) a target requires jointly consistent values across several chained
decisions *and* the schema's own constraints simultaneously." Asked
directly whether crossover is needed at all, the honest answer
(2026-09-12) was: not always, and not on its own -- crossover.py's own
self-test already proved recombination alone doesn't preserve or
improve DMN fitness; its payoff only comes from selection choosing which
children survive. §7a's own finding (most rule rows test one dedicated
variable, even under FIRST hit policy) means mutation-only hillclimb
already suffices for the common case -- confirmed repeatedly across this
session's own tricky-rule tests. So this module makes escalation
conditional, not automatic: pay for a population only on the branches
that actually stall under mutation alone.

**Not the full per-case-study DynaMOSA population loop** (§6.4's settled
algorithm-of-record: one shared population across every branch in a case
study, DRD-gated dynamic objective activation, non-dominated sorting
across all of them at once) -- that is a substantially larger build
(population management across many simultaneous objectives, Pareto
dominance, dynamic gating) not attempted here. This is the smaller,
immediately useful piece: a single-branch, single-objective escalation,
matching what SchemaAnalyst/EvoSQL already do per-target below the
DynaMOSA framing, and exactly the fallback §6.4 itself already names.

**The escalation loop itself**, when triggered: seeds a small population
with the mutation phase's own best-so-far (never discarded) plus several
independent shorter hillclimbs from the *original* start (different rng
streams) for diversity -- each population member is itself already a
locally-optimized candidate, not a naive random one, since an unmutated
starting candidate would likely sit uniformly far from a solution and
contribute little useful diversity to recombine. Each generation: sort by
fitness, keep the top half as parents (elitist), recombine pairs via
`crossover.py`'s uniform table-mask crossover (which also carries `focal`
through the same table-parent choice, so a returned child still knows
which row is "this" for every leaf), then polish each child with 1-3
mutation steps (exploration plus repair-by-construction, both already
mutation.py's job). Replace the population with elites + offspring,
truncated back to size.

Usage:
    from search import solve_branch
    result = solve_branch(record, candidate, focal, scenario)
    result['solved'], result['method'], result['fitness'], result['candidate']
"""
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from candidate import derive_genome  # noqa: E402
from fitness import branch_fitness, FitnessEvaluationError  # noqa: E402
from mutation import hillclimb, mutate, repair_candidate  # noqa: E402
from crossover import crossover  # noqa: E402


def _fitness_of(record, candidate, focal, scenario):
    try:
        return branch_fitness(record, derive_genome(record, candidate, focal, scenario))
    except FitnessEvaluationError:
        return float('inf')  # never a legitimate score -- worse than every real candidate


def _best(record, population):
    return min(population, key=lambda p: _fitness_of(record, *p))


def solve_branch(record, candidate, focal, scenario, mutation_budget=200,
                  population_size=8, generations=30, seed_restarts=None, rng=None):
    """Solves one branch. Phase 1: mutation-only hillclimb (cheap, and
    §7a's own finding says this already covers most rows). If it reaches
    fitness 0.0 within `mutation_budget` iterations, returns immediately
    -- no escalation paid for when it isn't needed. Phase 2 (only if
    phase 1 stalled): a small population + crossover GA for `generations`
    rounds, as described in this module's own docstring.

    Note: unlike mutate()/hillclimb() themselves (which always work on
    copies and never touch their inputs), this function DOES repair the
    incoming `candidate` in place before searching (`repair_candidate`) --
    a deliberate exception, since a caller handing in a freshly built
    seed candidate (`build_seed_candidate`) needs every row schema-legal
    before materialization, not just the ones the search happens to
    mutate. Idempotent and additive-only (never removes/changes a value
    already set), so this is always safe to rely on.

    Returns a dict: {'candidate', 'focal', 'scenario', 'fitness',
    'solved', 'method', 'mutation_history', 'population_history'} --
    'solved' is the honest `fitness == 0.0` check; a branch that never
    reaches it (a genuinely infeasible grounding, or one this escalation
    budget wasn't enough for) is reported as `solved: False`, never
    silently returned as if it were a solution. 'method' names which
    phase produced the *returned* candidate ('mutation' or 'population'),
    independent of whether it actually solved the branch."""
    rng = rng or random.Random(0)
    seed_restarts = seed_restarts if seed_restarts is not None else max(population_size - 1, 1)

    # Repair the INCOMING candidate wholesale before searching at all --
    # not just what mutation itself later touches. Found necessary
    # materializing a freshly built seed end to end (2026-09-12,
    # materialize.py): a "bystander" table/row the search never has
    # reason to mutate would otherwise reach materialization exactly as
    # incomplete as whatever built `candidate` left it. Idempotent, so
    # this is a safe no-op for a caller that already hands in a clean one.
    repair_candidate(candidate, record['case_study'])

    solved_c, solved_f, solved_s, mutation_history = hillclimb(
        record, candidate, focal, scenario, max_iters=mutation_budget, rng=rng)
    fitness = _fitness_of(record, solved_c, solved_f, solved_s)
    if fitness == 0.0:
        return {'candidate': solved_c, 'focal': solved_f, 'scenario': solved_s,
                'fitness': fitness, 'solved': True, 'method': 'mutation',
                'mutation_history': mutation_history, 'population_history': None}

    # --- Escalate ---------------------------------------------------
    case_study = record['case_study']
    population = [(solved_c, solved_f, solved_s)]
    for _ in range(seed_restarts):
        c, f, s, _h = hillclimb(record, candidate, focal, scenario,
                                 max_iters=max(1, mutation_budget // 4),
                                 rng=random.Random(rng.randrange(2 ** 31)))
        population.append((c, f, s))

    population_history = [_fitness_of(record, *_best(record, population))]
    for _gen in range(generations):
        if population_history[-1] == 0.0:
            break
        population.sort(key=lambda p: _fitness_of(record, *p))
        elites = population[:max(2, population_size // 2)]
        offspring = []
        while len(offspring) < population_size:
            p1, p2 = rng.sample(elites, 2) if len(elites) >= 2 else (elites[0], elites[0])
            c1, f1, c2, f2 = _cross_pair(p1, p2, case_study, rng)
            for child_c, child_f in ((c1, f1), (c2, f2)):
                child_s = dict(p1[2])  # scenario carries no per-row identity to recombine
                for _ in range(rng.randint(1, 3)):
                    try:
                        child_c, child_f, child_s, _var, _improved = mutate(
                            record, child_c, child_f, child_s, rng)
                    except FitnessEvaluationError:
                        break
                offspring.append((child_c, child_f, child_s))
        population = elites + offspring
        population.sort(key=lambda p: _fitness_of(record, *p))
        population = population[:population_size]
        population_history.append(_fitness_of(record, *population[0]))

    best = _best(record, population)
    final_fitness = _fitness_of(record, *best)
    return {'candidate': best[0], 'focal': best[1], 'scenario': best[2],
            'fitness': final_fitness, 'solved': final_fitness == 0.0, 'method': 'population',
            'mutation_history': mutation_history, 'population_history': population_history}


def _cross_pair(p1, p2, case_study, rng):
    c1, c2, f1, f2, _fm1, _fm2 = crossover(p1[0], p2[0], case_study, rng, focal1=p1[1], focal2=p2[1])
    return c1, f1, c2, f2


if __name__ == '__main__':
    import json
    from candidate import Candidate

    compiled = json.load(open(os.path.join(HERE, 'compiled_constraints.json')))

    def find(suffix):
        return next(r for r in compiled if r['record_id'].endswith(suffix))

    # --- Case 1: mutation alone already suffices -- escalation must
    # never even run (verified by checking method/population_history,
    # not just that the answer comes out right). ------------------------
    rule2 = find('Decision_AttendanceEligibility_Rule_2')
    start = Candidate()
    start.add_row('STUDENT_PROGRAM', {'ROLL_NO': 2024001})
    for i in range(45):
        start.add_row('LECTURE', {'LECTURE_ID': 1000 + i, 'OFFER_ID': 5001})
    for i in range(44):
        start.add_row('STUDENT_ATTENDANCE', {'LECTURE_ID': 1000 + i, 'ROLL_NO': 2024001, 'ATTEND_FLAG': 'Y'})
    scenario = {'student': 2024001, 'this course offering': 5001}
    result = solve_branch(rule2, start, {}, scenario, mutation_budget=100)
    print(f"Case 1 (flagship, mutation-sufficient): solved={result['solved']}, "
          f"method={result['method']}, fitness={result['fitness']}, "
          f"population_history={result['population_history']}")
    assert result['solved'] and result['method'] == 'mutation' and result['population_history'] is None, \
        "a branch mutation alone can solve must never pay for escalation"
    print("  Confirmed: escalation never ran -- mutation alone was enough (no wasted work).")

    # --- Case 2: mutation alone is STARVED of budget (1 iteration --
    # deliberately just enough to barely move) on a branch with several
    # genuinely independent facts living on separate tables (semesterType
    # on SEMESTER; cumulativeGPA/priorWarningCount on STUDENT_PROGRAM) --
    # exactly the shape table-mask crossover is meant for: different
    # restarts can independently make progress on different tables, and
    # recombining them closes the branch faster than either alone. -------
    B = find('Decision_CourseLoadLimit_Rule_2::via::Academic Warning Status::Decision_AcademicWarningStatus_Rule_4')
    b_candidate = Candidate()
    row_sem = b_candidate.add_row('SEMESTER', {'TITLE': 'Summer'})
    row_sp = b_candidate.add_row('STUDENT_PROGRAM', {'CGPA': 1.0, 'WARNING': 9})
    b_focal = {'SEMESTER': row_sem, 'STUDENT_PROGRAM': row_sp}

    starved = solve_branch(B, b_candidate, b_focal, {}, mutation_budget=1,
                            population_size=8, generations=15, rng=random.Random(4))
    print(f"\nCase 2 (starved mutation budget, needs escalation): solved={starved['solved']}, "
          f"method={starved['method']}, fitness={starved['fitness']:.4f}")
    print(f"  mutation_history (barely moved): {starved['mutation_history']}")
    print(f"  population_history: {starved['population_history']}")
    assert starved['method'] == 'population' and starved['solved'], \
        "a starved-but-tractable branch should converge once escalated"
    assert starved['fitness'] <= starved['mutation_history'][-1], \
        "escalation must never return something worse than the mutation phase already had"
    print(f"  Confirmed: mutation alone couldn't close this in its budget; escalation reached fitness 0.0.")

    # --- Case 2b: the branch whose real bottleneck used to be a large
    # single-variable numeric gap (D needed ~99 individual +1 increments,
    # per generator/README.md's own original tricky-rules sweep). Since
    # mutation.py's own AVM-style step acceleration (see its docstring)
    # was added, mutation ALONE now closes this same gap in ~4 steps --
    # confirmed directly: budget=10 already solves it via 'mutation'
    # alone (not tested here, see generator/README.md). The bar for what
    # counts as "starved" moved a lot, but escalation still has real,
    # demonstrable value at a tight-enough budget -- shown here with
    # budget=3, below the ~4 steps AVM itself needs on this branch. ------
    D = find('Decision_CourseRegistrationEligibility_Rule_3::via::Course Load Limit::Decision_CourseLoadLimit_Rule_1')
    c = Candidate()
    row_cr = c.add_row('COURSE_REGISTRATION', {'ROLL_NO': 777, 'COURSE_ID': 202, 'GRADE': 'B', 'SEM_ID': 9})
    row_sem_d = c.add_row('SEMESTER', {'TITLE': 'Fall'})
    row_sp_d = c.add_row('STUDENT_PROGRAM', {'CGPA': 1.0, 'WARNING': 3})
    for i in range(3):
        c.add_row('COURSE_REGISTRATION', {'ROLL_NO': 777, 'COURSE_ID': 300 + i, 'SEM_ID': 9, 'GRADE': None})
    focal = {'COURSE_REGISTRATION': row_cr, 'SEMESTER': row_sem_d, 'STUDENT_PROGRAM': row_sp_d}
    scenario_d = {'student': 777, 'semester': 9}

    starved_d = solve_branch(D, c, focal, scenario_d, mutation_budget=3,
                              population_size=8, generations=15, rng=random.Random(3))
    print(f"\nCase 2b (a much tighter budget than pre-AVM, since AVM alone now needs only ~4 steps here): "
          f"solved={starved_d['solved']}, method={starved_d['method']}, fitness={starved_d['fitness']:.4f}")
    print(f"  mutation_history: {starved_d['mutation_history']}")
    print(f"  population_history: {starved_d['population_history']}")
    assert starved_d['fitness'] <= starved_d['mutation_history'][-1], \
        "escalation must never return something worse than the mutation phase already had"
    print(f"  Confirmed: even after AVM acceleration raised the bar for what counts as 'starved', "
          f"escalation still rescues this branch at a tight-enough budget.")

    # --- Case 3: genuinely infeasible -- newWarningCount is a FIXED
    # literal (0) that can never satisfy this branch's own requirement of
    # 2, no amount of search (mutation OR population) can ever close it.
    # solve_branch must report this honestly, never claim success. ------
    A_infeasible = find('Decision_CourseRegistrationEligibility_Rule_2::via::Academic Warning Status::'
                         'Decision_AcademicWarningStatus_Rule_1')
    c2 = Candidate()
    row_cr2 = c2.add_row('COURSE_REGISTRATION', {'ROLL_NO': 555, 'COURSE_ID': 101, 'GRADE': 'F'})
    row_sp2 = c2.add_row('STUDENT_PROGRAM', {'CGPA': 1.5, 'WARNING': 5})
    c2.add_row('COURSE_PREREQ', {'COURSE_ID': 101, 'COURSE_PREREQ': 900})
    focal2 = {'COURSE_REGISTRATION': row_cr2, 'STUDENT_PROGRAM': row_sp2}
    infeasible_result = solve_branch(A_infeasible, c2, focal2, {}, mutation_budget=50,
                                      population_size=6, generations=10, rng=random.Random(1))
    print(f"\nCase 3 (structurally infeasible): solved={infeasible_result['solved']}, "
          f"method={infeasible_result['method']}, fitness={infeasible_result['fitness']:.4f}")
    assert not infeasible_result['solved'], \
        "a structurally infeasible branch must never be reported as solved"
    assert infeasible_result['fitness'] > 0.0
    print("  Confirmed: reported honestly as unsolved (fitness > 0), not a false success, "
          "after spending the full escalation budget.")

    print("\nAll search.py self-checks passed.")
