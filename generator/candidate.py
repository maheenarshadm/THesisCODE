"""candidate.py -- bridges fitness.py's flat genome contract to a real,
shared row-set (design doc §6.2's "candidate solution ... a proposed set
of rows across the tables relevant to one generation target").

This closes the open question raised while explaining fitness.py: does
the branch-distance formula still work when a fact like `lecturesAttended`
is *derived from actual candidate rows* rather than hand-picked as a free
scalar? `fitness.py`'s own genome contract (`{free_variable_name: value}`)
never assumed the caller picks those values out of thin air -- it only
requires *some* concrete value per free variable. `derive_genome()` here
is what a real search loop would call before every `branch_fitness()`:
given one shared `Candidate` (the population individual DynaMOSA would
actually evolve) plus a `focal` row per table (which of the candidate's
own rows this specific branch's scenario is "about") and a `scenario`
dict (bind-parameter values for not_persisted/<placeholder> facts, the
same role sql_compiler.py's bind params play), it walks a compiled
record's `variable_resolution` and computes each leaf variable's REAL
current value the same way sql_compiler.py would compile it to SQL --
just evaluated in-memory against real rows instead.

Usage:
    from candidate import Candidate, derive_genome
    genome = derive_genome(record, candidate, focal, scenario)
    score = branch_fitness(record, genome)   # fitness.py, unchanged
"""
import json
import os
import re
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from fitness import FitnessEvaluationError  # noqa: E402 -- reused, not reimplemented
from compile_constraints import CASE_STUDY_SCHEMA_JSON  # noqa: E402 -- safe: compile_constraints.py
# depends on neither candidate.py nor mutation.py, so no circularity (mutation.py depends on
# candidate.py, so candidate.py must never import mutation.py itself).

_PLACEHOLDER_RE = re.compile(r'<([^>]+)>')
_SEED_SCHEMA_CACHE = {}


def _schema_for_seeding(case_study):
    if case_study not in _SEED_SCHEMA_CACHE:
        with open(CASE_STUDY_SCHEMA_JSON[case_study], encoding='utf-8') as f:
            _SEED_SCHEMA_CACHE[case_study] = json.load(f)
    return _SEED_SCHEMA_CACHE[case_study]


def _real_columns_of(case_study, table):
    schema = _schema_for_seeding(case_study)
    info = schema.get(table) or schema.get(table.upper()) or schema.get(table.lower()) or {}
    return {c.upper() for c in (info.get('columns') or {})}


class Candidate:
    """A proposed row-set: {table_name: [row_dict, ...]}. Deliberately
    thin -- no schema awareness, no validation -- those are `derive_genome`
    and `fitness.py`'s own constraint-distance functions' job, not this
    class's. Case-insensitive table lookup (candidate_constraint_fitness
    and fk_closure both already have to handle the same real-world casing
    mismatch between ground-truth table names and the schema JSON's own)."""

    def __init__(self):
        self._tables = {}

    def add_row(self, table, row):
        self._tables.setdefault(table.upper(), []).append(row)
        return row

    def rows(self, table):
        return self._tables.get(table.upper(), [])

    def as_dict(self):
        """The {table: [row, ...]} view fitness.py's own constraint-
        distance functions (not_null_distance, unique_distance, ...) take
        directly."""
        return self._tables


# A reserved, non-schema row key marking which objective a row was
# created FOR -- the fix for a real, previously-flagged row-sharing bug
# (2026-09-13, dynamosa.py's own module docstring): derived_aggregate/
# exists/derived_join_count leaves used to scan a table's ENTIRE row set
# with zero isolation, so two different DynaMOSA objectives sharing one
# candidate could count each OTHER's own unrelated rows, actively
# interfering once merged into one final materialized dataset (measured
# directly: final-dataset coverage stuck at 20/151 regardless of rng
# seed, versus 81/151 objectives the search could reach individually).
# `materialize.py`'s own to_sql_inserts/write_csv_files strip this key
# before emitting real SQL/CSV -- it is bookkeeping, never a real column.
_OWNER_KEY = '__owner__'


def _owned_rows(candidate, table, owner_id):
    """Every row of `table` visible to objective `owner_id`'s own
    aggregate/exists/derived_join_count leaves: rows never tagged with
    ANY owner (untagged -- e.g. `_repair_row`'s own synthesized FK-parent
    rows, which genuinely are shared reference data every objective
    should be able to see) plus rows explicitly tagged as belonging to
    `owner_id` itself. Rows tagged for a DIFFERENT objective are
    invisible. `owner_id=None` (the single-objective case -- search.py's
    own solve_branch/hillclimb, which never shares a candidate across
    objectives at all, and every existing self-test's own hand-built
    fixtures, which never tag anything) disables filtering entirely,
    returning every row exactly like this function never existed --
    a pure, backward-compatible addition, not a behavior change for any
    caller that doesn't opt in by passing a real owner_id."""
    rows = candidate.rows(table)
    if owner_id is None:
        return rows
    return [r for r in rows if r.get(_OWNER_KEY) in (None, owner_id)]


# ---------------------------------------------------------------------------
# Known real-world constants (2026-09-13) -- a general, config-driven
# mechanism for the gap found asking why the generated data showed only 5
# STUDENT_ATTENDANCE rows for `Attendance Eligibility For Final Exam`: the
# search has NO notion of "a real course offering holds ~30 lectures" --
# `lecturesHeldForOffering` is just a free `derived_aggregate` leaf, and
# `best_value_for` (mutation.py) always converges to the CHEAPEST value
# that proves the branch (here, as few real rows as the DMN's own >=80%/
# <80% threshold needs), never a value chosen for real-world plausibility.
# This is not a bug -- the search was never asked to optimize for realism,
# only for DMN/schema correctness -- but it is a real, named gap: some
# leaf variables have a known, domain-true value a generated dataset
# should honor regardless of what the DMN's own arithmetic strictly
# requires. `known_constants.json` lets a domain expert name those
# variables once, by their own real business name, and have every rule
# that resolves to that same var_name -- there is no other case in FLEX2
# right now, but this is deliberately NOT special-cased to Attendance
# Eligibility -- pin to it, uniformly, without touching that rule's own
# compiled resolution or hand-coding the value into any one leaf kind's
# own logic.
# ---------------------------------------------------------------------------
_KNOWN_CONSTANTS_PATH = os.path.join(HERE, 'known_constants.json')
_known_constants_cache = None


def known_constant(case_study, var_name):
    """The pinned real-world value for `var_name` in `case_study`, or
    None if this variable isn't pinned -- the single lookup every
    consumer (`best_value_for`, `build_seed_candidate`, dynamosa.py's own
    kick-mutation guard) shares, so a domain expert only ever has to edit
    `known_constants.json` once for the pin to take effect everywhere a
    leaf resolves to that same variable name. Loaded once and cached
    (mirrors `_schema_for`'s own pattern in mutation.py) -- the file is
    static config, not something any run mutates."""
    global _known_constants_cache
    if _known_constants_cache is None:
        try:
            with open(_KNOWN_CONSTANTS_PATH) as f:
                _known_constants_cache = json.load(f)
        except FileNotFoundError:
            _known_constants_cache = {}
    return _known_constants_cache.get(case_study, {}).get(var_name)


def _row_get(row, column, table_for_error=None):
    """Case-insensitive column lookup: ground-truth resolutions carry
    lowercased table.column names (compile_constraints.py's own
    true_pairs()), but real rows are built with whatever casing the
    schema/candidate actually uses -- matched case-insensitively, the
    same accommodation fk_closure() and sql_compiler.py's SqlContext
    already make for the identical mismatch."""
    if column in row:
        return row[column]
    lowered = {k.lower(): v for k, v in row.items()}
    if column.lower() not in lowered:
        where = f" in {table_for_error!r}" if table_for_error else ""
        raise FitnessEvaluationError(f"no column {column!r} found{where}: {sorted(row)}")
    return lowered[column.lower()]


def _lookup(focal, table, column):
    row = focal.get(table.upper())
    if row is None:
        raise FitnessEvaluationError(
            f"no focal row given for table {table!r} -- can't read {table}.{column} "
            f"from a candidate with no row there yet")
    return _row_get(row, column, table)


def _find_focal_with_columns(focal, columns):
    """Finds whichever focal row carries all of `columns` (case-
    insensitively) -- used by derived_join_count, whose ground-truth text
    only names the join tables, not which of the record's own focal rows
    is "this" course/student context (that's COURSE_REGISTRATION itself
    for Course Registration Eligibility, but EXEMPTED_COURSES for Credit
    Transfer Exemption -- both real tables happen to carry their own
    ROLL_NO + COURSE_ID columns, DDL-confirmed, so this is a real
    heuristic match, not a guess at an arbitrary table)."""
    wanted = {c.lower() for c in columns}
    for table, row in focal.items():
        if wanted <= {k.lower() for k in row}:
            return table, row
    return None, None


def _find_row_by_pk(candidate, table, pk_column, value):
    for row in candidate.rows(table):
        try:
            if _row_get(row, pk_column) == value:
                return row
        except FitnessEvaluationError:
            continue
    return None


# ---------------------------------------------------------------------------
# derived_aggregate's filter_text: still deliberately informal prose in
# general (compile_constraints.py's own documented choice -- see its
# _try_extract_aggregate_recipe docstring), so only the mechanically
# recognizable conjuncts get turned into a real filter; anything else is
# skipped and reported, never silently assumed to mean "no filter."
# ---------------------------------------------------------------------------
_SIMPLE_EQ_CONJUNCT_RE = re.compile(r'^\s*(?:[\w]+\.)?([\w]+)\s*=\s*(.+?)\s*$')
_BARE_TABLE_DOT_COLUMN_RE = re.compile(r'^[A-Za-z_]\w*\.[A-Za-z_]\w*$')
# A second recognized conjunct shape, found necessary running Spree's
# `First-Order Promotion Eligibility::rule_3` for the first time
# (2026-09-24): `literal_expression_overrides.py`'s own `Prior Completed
# Order Count` filter_text uses `completed_at IS NOT NULL` (real SQL the
# validator's own db_resolver.py runs correctly) to mean "this order is
# complete" -- but neither this predicate nor `_row_from_filter_
# conjuncts` recognized this shape at all, so it was silently SKIPPED
# (no `=` sign, doesn't match `_SIMPLE_EQ_CONJUNCT_RE`): the predicate
# treated it as "no constraint," and the row-builder never set
# `completed_at` on a seeded/mutated "prior order" row. Net effect: the
# search's own approximate fitness saw every candidate row as already
# "a prior completed order" (an over-count), reaching fitness 0.0 from
# the very first seeded candidate -- while the real validator, running
# the actual `IS NOT NULL` check against rows that were never given a
# real `completed_at`, correctly found none. A systematic generator-vs-
# validator mismatch, not a search-budget problem.
_IS_NOT_NULL_RE = re.compile(r'^\s*(?:[\w]+\.)?(\w+)\s+IS\s+NOT\s+NULL\s*$', re.I)
_IS_NULL_RE = re.compile(r'^\s*(?:[\w]+\.)?(\w+)\s+IS\s+NULL\s*$', re.I)
# A third recognized conjunct shape, found necessary 2026-09-25 running
# FLEX2's `Graduation Eligibility`/`Summer Semester Registration` for the
# first time: `compile_constraints.py`'s own `AGGREGATE_FOR_CORRELATION_RE`
# fix translates ground truth's "for COL" phrasing into a `COLUMN =
# :COLUMN` self-reference (the SAME convention `validation_oracle/
# db_resolver.py`'s own `_substitute_self_and_colon` already resolves at
# verification time: "this row's own value for COLUMN", read off the
# decision's own subject/self row, not a `scenario` binding or literal
# value). Before this fix, `_SIMPLE_EQ_CONJUNCT_RE`'s generic `COLUMN =
# (.+?)` capture still matched a `:COLUMN` conjunct, but with no bracket
# `<placeholder>` and no scenario binding, it fell through to being
# treated as a literal STRING value (the bare text ':COLUMN') -- which no
# real row's own column could ever equal, so the search's own approximate
# fitness would treat the aggregate as unconditionally forced to 0
# matching rows, exactly the same "systematic generator-vs-validator
# mismatch" class of bug `_IS_NOT_NULL_RE`'s own comment above already
# documents for a different conjunct shape. Resolved via `self_row` (the
# decision's own subject row, from `focal`), passed in by every caller
# that already has `focal` in scope.
_COLON_SELF_REF_RE = re.compile(r'^:([A-Za-z_]\w*)$')
# A fourth shape, found necessary 2026-09-25 fixing `priorRegistration
# Count`'s own self-inclusion bug (`aggregate_self_exclusions.py`): a
# `COLUMN != :COLUMN` conjunct, excluding the decision's own subject row
# from an aggregate that would otherwise always count it (the subject IS
# one of the rows its own filter matches). `_SIMPLE_EQ_CONJUNCT_RE` only
# ever recognizes `=`, so this needs its own check, same self-reference
# resolution as the `=` case above -- just negated.
_NEQ_COLON_SELF_REF_RE = re.compile(r'^\s*(?:[\w]+\.)?(\w+)\s*!=\s*:([A-Za-z_]\w*)\s*$')


def _self_row_value(self_row, column):
    """Case-insensitive lookup, matching `_row_get`'s own convention
    elsewhere in this module -- `self_row` (from `focal`) may use either
    the schema's own declared casing or a real materialized column's
    lowercase name, depending on which stage produced it."""
    if self_row is None:
        return None, False
    for key in (column, column.upper(), column.lower()):
        if key in self_row:
            return self_row[key], True
    return None, False


def _top_level_and_conjuncts(filter_text):
    """Splits `filter_text` on 'AND', but only at paren-depth 0. A naive
    `re.split(r'\\bAND\\b', ...)` doesn't know an 'AND' inside a
    parenthesized IN-subquery (e.g. `adjustedCreditsCount`'s own
    `promotion_action_id IN (SELECT ... WHERE a AND b)`) describes the
    SUBQUERY's own filter, on a DIFFERENT table than the one this
    filter_text's own top-level conjuncts apply to -- it must never be
    treated as one of THIS filter's own conjuncts. A real bug found
    2026-09-24, the same day `_IS_NOT_NULL_RE` was added:
    `priorPromotionUsageCount`'s subquery-internal `completed_at IS NOT
    NULL` (a fact about spree_orders) was misread as a top-level
    conjunct of the OUTER filter (about spree_discounts), stamping a
    nonexistent `completed_at` column onto a spree_discounts row --
    only surfaced once IS NOT NULL conjuncts started being recognized
    at all; before that, the same misread fragment was harmlessly
    skipped since it never matched the plain `COLUMN = VALUE` shape
    either. Any fragment starting inside an unclosed paren from an
    earlier fragment is dropped here, restoring this project's own
    long-standing default for text a conjunct-level parser can't
    attribute to the right table: silently not a conjunct, never a
    wrong guess. Checked against every filter_text in the current
    compiled corpus that mixes '(' and 'AND' (3, across Spree/FLEX2) --
    none of the other two regress, since their own parenthesized spans
    already net to zero parens by the time a later 'AND' is reached.

    Upgraded 2026-09-24 from a filter-the-naive-split pass to a real,
    character-level depth-aware split: the original version only kept
    whichever depth-0 FRAGMENT the naive `re.split` happened to produce,
    silently truncating a top-level conjunct that itself contains a
    nested AND (e.g. `priorPromotionUsageCount`'s own subquery, `order_id
    IN (SELECT id FROM spree_orders WHERE user_id = <user_id> AND
    completed_at IS NOT NULL AND id != self)`, used to come back missing
    everything after its own first internal AND). That truncation was
    harmless as long as nothing ever tried to READ the inside of such a
    conjunct -- true until IN-subquery construction (below) needed the
    complete, balanced text to build a real matching row. Behaviorally
    identical to the old version for every conjunct shape already in use
    (none of them were ever successfully parsed past their own first
    internal AND either way)."""
    text = filter_text or ''
    parts, current, depth, i, n = [], [], 0, 0, len(text)
    while i < n:
        ch = text[i]
        if ch == '(':
            depth += 1
            current.append(ch)
            i += 1
        elif ch == ')':
            depth -= 1
            current.append(ch)
            i += 1
        elif depth == 0 and text[i:i + 3].upper() == 'AND' \
                and (i == 0 or not (text[i - 1].isalnum() or text[i - 1] == '_')) \
                and (i + 3 == n or not (text[i + 3].isalnum() or text[i + 3] == '_')):
            parts.append(''.join(current))
            current = []
            i += 3
        else:
            current.append(ch)
            i += 1
    parts.append(''.join(current))
    return parts


# Recognizes `COLUMN IN (SELECT SELCOL FROM TABLE WHERE inner_where)` --
# an IN-subquery join, e.g. `adjustedCreditsCount`'s own
# `promotion_action_id IN (SELECT id FROM spree_promotion_actions WHERE
# promotion_id = self)` or `priorPromotionUsageCount`'s `order_id IN
# (SELECT id FROM spree_orders WHERE user_id = <user_id> AND
# completed_at IS NOT NULL AND id != self)`. Added 2026-09-24: until
# this, the shape was entirely unrecognized (never matched `=`/`IS NOT
# NULL`), so the outer column it names was never bound to anything --
# the row-builder skipped it and the predicate treated the whole
# conjunct as absent, meaning the search's own approximate fitness
# counted every row as a match regardless of whether it was really
# attributable to the right parent. See `_conjunct_value_bindings` and
# `_construct_subquery_parent` for what actually closes the gap.
_IN_SUBQUERY_RE = re.compile(
    r'^\s*(?:[\w]+\.)?(\w+)\s+IN\s*\(\s*SELECT\s+(\w+)\s+FROM\s+(\w+)\s+WHERE\s+(.+)\)\s*$',
    re.I | re.S)
_SELF_TOKEN_RE = re.compile(r'self', re.I)


def _conjunct_value_bindings(where_text, scenario, self_value=None):
    """The construction-side counterpart to `_mechanical_filter_predicate`,
    scoped to ONE inner WHERE clause (an IN-subquery's own text, or --
    equally -- an ordinary top-level filter_text): returns
    `{column: value}` for every conjunct this bridge can mechanically
    bind (`COLUMN = VALUE`, `COLUMN = <placeholder>` when the placeholder
    is in `scenario`, `COLUMN IS NOT NULL` as a generic non-null
    placeholder, `COLUMN = self` when `self_value` is given). A conjunct
    it can't bind (an exclusion like `id != self`, an unrecognized
    shape) is silently omitted, never guessed at -- the same honesty
    convention `_row_from_filter_conjuncts` already uses, just factored
    out so IN-subquery construction can reuse it for the SUBQUERY's own
    inner clause without a third reimplementation."""
    bindings = {}
    for c in _top_level_and_conjuncts(where_text):
        c_stripped = c.strip()
        m = _IS_NOT_NULL_RE.match(c_stripped)
        if m:
            bindings[m.group(1)] = 1
            continue
        if _IS_NULL_RE.match(c_stripped):
            continue
        m = _SIMPLE_EQ_CONJUNCT_RE.match(c_stripped)
        if not m:
            continue
        col, raw_val = m.group(1), m.group(2).strip()
        if col.isdigit():
            continue
        if _SELF_TOKEN_RE.fullmatch(raw_val):
            if self_value is not None:
                bindings[col] = self_value
            continue
        if _BARE_TABLE_DOT_COLUMN_RE.match(raw_val):
            continue
        ph = _PLACEHOLDER_RE.fullmatch(raw_val)
        if ph:
            if ph.group(1) in scenario:
                bindings[col] = scenario[ph.group(1)]
            continue
        v = raw_val.strip("'\"")
        try:
            v = int(v)
        except ValueError:
            try:
                v = float(v)
            except ValueError:
                pass
        bindings[col] = v
    return bindings


def _fresh_id_value(candidate, table):
    """A numeric `id` value guaranteed not to collide with any existing
    `id` already on a row of `table` in this candidate -- the same
    guarantee `mutation.py`'s own `_fresh_key_value` provides for a
    declared PK/UNIQUE column repair, duplicated here in miniature
    (scoped to the literal column name `id`, which every table this
    mechanism targets actually uses) rather than imported, since
    candidate.py has no dependency on mutation.py."""
    existing = {r.get('id', r.get('ID')) for r in candidate.rows(table)
                if isinstance(r.get('id', r.get('ID')), (int, float))
                and not isinstance(r.get('id', r.get('ID')), bool)}
    return (max(existing) + 1) if existing else 1


def _construct_subquery_parent(match, candidate, focal, scenario, self_table):
    """Given an `_IN_SUBQUERY_RE` match, builds (or reuses) a real row in
    the subquery's own table satisfying whatever of its WHERE clause is
    mechanically bindable, and returns the value the OUTER column should
    be set to (that row's own real `id`) -- or None if `candidate` isn't
    available (a caller with no candidate to build into, e.g. a bare
    predicate check with no construction role). `self_table`, when the
    inner WHERE references `self` and this fact declared one (see
    `generator/aggregate_self_table.py`), is resolved to that table's
    OWN focal row's real id -- assigning one now, via `_fresh_id_value`,
    if it doesn't have one yet, so this row and any sibling leaf that
    later reads the SAME focal row agree on one real identity."""
    if candidate is None:
        return None
    outer_col, select_col, inner_table, inner_where = match.groups()
    self_value = None
    # A real, latent bug found 2026-09-25 running FLEX2's own
    # `lecturesAttended` for the first time: this branch used to fire
    # whenever the CALLER passed a non-None `self_table`, regardless of
    # whether `inner_where` actually references `self` at all -- harmless
    # as long as every caller only ever passed `self_table` for a
    # genuinely self-referencing fact, but `_row_from_filter_conjuncts`'s
    # own default (falling back to the aggregate's own table when no
    # explicit override exists, added the same day for `priorRegistration
    # Count`) now passes a non-None `self_table` unconditionally, which
    # stamped a bogus, schema-invalid `id` column onto a real table
    # (STUDENT_ATTENDANCE has no `id` column at all) purely because
    # `lecturesAttended`'s OWN inner_where ("OFFER_ID = <this course
    # offering>") happens to share a filter_text with an IN-subquery,
    # never mentioning `self`. Now gated on the inner WHERE actually
    # containing the literal word `self`, matching this function's own
    # docstring, which already described this as the intended condition.
    if self_table and focal is not None and _SELF_TOKEN_RE.search(inner_where):
        self_row = focal.setdefault(self_table.upper(), {})
        if self_row not in candidate.rows(self_table):
            candidate.add_row(self_table, self_row)
        self_value = self_row.get('id', self_row.get('ID'))
        if self_value is None:
            self_value = _fresh_id_value(candidate, self_table)
            self_row['id'] = self_value
    bindings = _conjunct_value_bindings(inner_where, scenario, self_value)
    inner_row = dict(bindings)
    # The subquery's own "SELECT <col>" names `inner_table`'s real key --
    # a real, generalizable bug (see `subquery_check`'s own mirror fix,
    # same day): this used to hardcode a bare 'id', correct only for
    # Spree's own Rails-convention PK naming (the only case study this
    # mechanism had been exercised against before), but wrong for a named
    # PK like FLEX2's own LECTURE_ID -- a constructed row would carry a
    # key ('id') the real schema doesn't have at all, and the read-side
    # match (looking for the REAL key) would then never find it either.
    inner_row[select_col] = _fresh_id_value(candidate, inner_table)
    candidate.add_row(inner_table, inner_row)
    return inner_row[select_col]


def _mechanical_filter_predicate(filter_text, scenario, candidate=None, self_row=None):
    """-> (predicate(row) -> bool, [skipped conjunct strings]). Splits on
    ' AND ' (the only combinator actually seen in these facts' filter
    text) and keeps only conjuncts of the plain `COLUMN = VALUE` or
    `COLUMN = <placeholder>` shape; anything else (a join description in
    prose, a genuine cross-table join conjunct like `PROGRAM_COURSE.
    COURSE_ID = COURSE.COURSE_ID` -- a real bug found materializing
    degreeTotalCredits end to end, 2026-09-12: this used to treat the
    bare `TABLE.COLUMN` on the right as a literal STRING value to match
    against, which no real row's own COURSE_ID integer could ever equal,
    silently zeroing the aggregate rather than honestly reporting the
    join as unparseable) is reported as skipped rather than guessed at,
    and the resulting predicate is a real over-count on exactly the
    skipped conjuncts' account -- an honest approximation, not a silent
    exact (or silently wrong) answer.

    `candidate`, when given, additionally lets a `COLUMN IN (SELECT ...
    WHERE ...)` conjunct (2026-09-24) be checked for real -- does
    `row`'s own `COLUMN` equal the real `id` of some row, already in
    `candidate`, that itself satisfies the subquery's own mechanically
    bindable conjuncts? Without a `candidate` (a bare predicate check
    with no construction context), this shape is skipped like any other
    the read side can't resolve -- consistent, not a wrong guess.

    `self_row`, when given, is the decision's own subject/self row (from
    `focal`, keyed by whichever table `node.get('self_table')` names, or
    the aggregate's own `node['table']` by default -- see the caller),
    letting a `COLUMN = :COLUMN` conjunct (2026-09-25) resolve against
    THIS ROW's own same-named column, the same self-reference convention
    `validation_oracle/db_resolver.py`'s `_substitute_self_and_colon`
    already uses at verification time. Without `self_row`, or when the
    named column isn't actually on it, the conjunct is skipped -- same
    honest-approximation convention as every other unparseable shape."""
    if not filter_text:
        return (lambda row: True), []
    conjuncts = _top_level_and_conjuncts(filter_text)
    checks = []
    skipped = []
    for c in conjuncts:
        c_stripped = c.strip()
        m = _IN_SUBQUERY_RE.match(c_stripped)
        if m:
            if candidate is None:
                skipped.append(c_stripped)
                continue
            outer_col, select_col, inner_table, inner_where = m.groups()
            inner_bindings = _conjunct_value_bindings(inner_where, scenario, self_value=None)

            def subquery_check(row, outer_col=outer_col, inner_table=inner_table,
                                inner_bindings=inner_bindings, select_col=select_col):
                try:
                    outer_val = _row_get(row, outer_col)
                except FitnessEvaluationError:
                    return False
                if outer_val is None:
                    return False
                for inner_row in candidate.rows(inner_table):
                    # The subquery's own "SELECT <col>" names which column
                    # of `inner_table` this IN-list is really built from --
                    # a real, generalizable bug, found 2026-09-25 running
                    # FLEX2's own `lecturesAttended` for the first time
                    # (`LECTURE_ID IN (SELECT LECTURE_ID FROM LECTURE
                    # WHERE ...)`): this used to hardcode a bare 'id'/'ID'
                    # key instead, a real, correct assumption for Spree's
                    # own Rails-convention PK naming (the only case study
                    # this subquery mechanism had been exercised against
                    # before), but wrong for FLEX2 (and any other schema
                    # using named PKs like LECTURE_ID) -- every real
                    # LECTURE row has no bare 'id' key at all, so the
                    # match NEVER succeeded, silently under-counting to 0
                    # regardless of how many real matching rows existed.
                    inner_id = inner_row.get(select_col, inner_row.get(
                        select_col.upper(), inner_row.get(select_col.lower())))
                    if inner_id != outer_val:
                        continue
                    if all(inner_row.get(k, inner_row.get(k.upper())) == v
                           for k, v in inner_bindings.items()):
                        return True
                return False

            checks.append((None, 'custom', subquery_check))
            continue
        neq_m = _NEQ_COLON_SELF_REF_RE.match(c_stripped)
        if neq_m:
            self_value, found = _self_row_value(self_row, neq_m.group(2))
            if not found:
                skipped.append(c_stripped)
                continue
            checks.append((neq_m.group(1), 'neq', self_value))
            continue
        m = _IS_NOT_NULL_RE.match(c_stripped)
        if m:
            checks.append((m.group(1), 'not_null', None))
            continue
        m = _IS_NULL_RE.match(c_stripped)
        if m:
            checks.append((m.group(1), 'is_null', None))
            continue
        m = _SIMPLE_EQ_CONJUNCT_RE.match(c_stripped)
        if not m:
            skipped.append(c_stripped)
            continue
        col, raw_val = m.group(1), m.group(2).strip()
        if col.isdigit():
            # A SQL tautology guard like the real Spree fact's own
            # trailing `AND 1=1` -- found running the fresh Spree search
            # against `adjustedCreditsCount` for the first time
            # (2026-09-24): `_SIMPLE_EQ_CONJUNCT_RE` mechanically read
            # "1" as a COLUMN NAME to compare against 1, not the
            # always-true no-op it actually is in real SQL (no real
            # schema column is ever a bare digit string). Genuinely,
            # correctly a no-op -- not an approximation the way an
            # unparseable conjunct is, so it's simply omitted, never
            # added to `skipped` (which exists to flag prose this bridge
            # couldn't handle, not conjuncts it handled exactly right).
            continue
        if _BARE_TABLE_DOT_COLUMN_RE.match(raw_val):
            skipped.append(c.strip())  # a real cross-table join, not a value comparison -- see docstring
            continue
        colon_m = _COLON_SELF_REF_RE.fullmatch(raw_val)
        if colon_m:
            self_value, found = _self_row_value(self_row, colon_m.group(1))
            if not found:
                skipped.append(c_stripped)
                continue
            checks.append((col, 'eq', self_value))
            continue
        ph = _PLACEHOLDER_RE.fullmatch(raw_val)
        if ph:
            if ph.group(1) not in scenario:
                raise FitnessEvaluationError(
                    f"filter text needs scenario binding {raw_val!r}, none supplied")
            expected = scenario[ph.group(1)]
        else:
            expected = raw_val.strip("'\"")
            # numeric literals compare as numbers, not strings
            try:
                expected = int(expected)
            except ValueError:
                try:
                    expected = float(expected)
                except ValueError:
                    pass
        checks.append((col, 'eq', expected))

    def predicate(row):
        for col, mode, expected in checks:
            if mode == 'custom':
                if not expected(row):  # `expected` holds the check callable for this mode
                    return False
                continue
            try:
                value = _row_get(row, col)
            except FitnessEvaluationError:
                return False  # row doesn't even have this column -- can't match
            if mode == 'not_null':
                if value is None:
                    return False
            elif mode == 'is_null':
                if value is not None:
                    return False
            elif mode == 'neq':
                if value == expected:
                    return False
            elif value != expected:
                return False
        return True

    return predicate, skipped


def _row_from_filter_conjuncts(filter_text, scenario, candidate=None, focal=None, self_table=None):
    """The construction mirror of `_mechanical_filter_predicate`: builds
    a real row dict satisfying every mechanically-recognized `COLUMN =
    VALUE`/`COLUMN = <placeholder>` conjunct in `filter_text`, the exact
    same shape `mutation.py`'s own M2 "add a row" logic already builds
    (kept independent, not imported, since candidate.py has no
    dependency on mutation.py -- but the parsing rules must stay
    identical, so any change to one belongs in the other too). A conjunct
    this can't parse is simply skipped (no key added for it), same
    honesty convention as `_mechanical_filter_predicate`'s own
    `skipped` list -- a row missing an unparseable conjunct's column is
    an approximation, never a silent wrong guess at its value.

    `candidate`/`focal`/`self_table`, when given, additionally let a
    `COLUMN IN (SELECT ... WHERE ...)` conjunct (2026-09-24) actually
    construct a real, matching parent row via `_construct_subquery_parent`
    instead of being silently skipped -- without `candidate`, this shape
    degrades to the old skip-it behavior (a caller with no construction
    context, e.g. a bare seed for a leaf this project doesn't yet thread
    candidate/focal through for). `focal`/`self_table` also let a
    `COLUMN = :COLUMN` conjunct (2026-09-25, same self-reference
    convention as `_mechanical_filter_predicate`'s own) copy the real
    value straight off the decision's own subject/self row -- without
    both given, or when the named column isn't on that row, the conjunct
    is skipped, same as any other unparseable shape. A `COLUMN != :COLUMN`
    self-EXCLUSION conjunct (`aggregate_self_exclusions.py`, 2026-09-25)
    is deliberately left unhandled here too -- it names a value the new
    row must NOT take, not one to assign, and `_SIMPLE_EQ_CONJUNCT_RE`
    (`=` only) already skips it silently; leaving the column unset lets
    `repair_candidate`'s own generic filler pick something, which only
    coincides with the excluded self-value by the same low-probability
    chance any other skipped conjunct already accepts."""
    self_row = focal.get(self_table.upper()) if (focal and self_table) else None
    row = {}
    for c in _top_level_and_conjuncts(filter_text):
        c_stripped = c.strip()
        m = _IN_SUBQUERY_RE.match(c_stripped)
        if m:
            outer_val = _construct_subquery_parent(m, candidate, focal, scenario, self_table)
            if outer_val is not None:
                row[m.group(1)] = outer_val
            continue
        m = _IS_NOT_NULL_RE.match(c_stripped)
        if m:
            # A generic non-null placeholder -- same convention as every
            # other untyped placeholder in this module (e.g. ensure_row's
            # own default val=1). Good enough to satisfy IS NOT NULL for
            # any column type SQLite will actually store it as; the real,
            # typed value (if the branch needs one) comes from whatever
            # OTHER leaf/mutation targets this same column directly.
            row[m.group(1)] = 1
            continue
        if _IS_NULL_RE.match(c_stripped):
            continue  # leave the column unset -- absent already means None
        m = _SIMPLE_EQ_CONJUNCT_RE.match(c_stripped)
        if not m:
            continue
        col, raw_val = m.group(1), m.group(2).strip()
        if col.isdigit():
            continue  # a SQL tautology guard (e.g. "1=1"), never a real column -- see the predicate's own docstring
        if _BARE_TABLE_DOT_COLUMN_RE.match(raw_val):
            continue  # a real cross-table join conjunct, not a value to assign -- see the predicate's own docstring
        colon_m = _COLON_SELF_REF_RE.fullmatch(raw_val)
        if colon_m:
            self_value, found = _self_row_value(self_row, colon_m.group(1))
            if found:
                row[col] = self_value
            continue
        ph = _PLACEHOLDER_RE.fullmatch(raw_val)
        if ph:
            if ph.group(1) in scenario:
                row[col] = scenario[ph.group(1)]
        else:
            v = raw_val.strip("'\"")
            try:
                v = int(v)
            except ValueError:
                try:
                    v = float(v)
                except ValueError:
                    pass
            row[col] = v
    return row


def _raw_sql_boolean_value(node, candidate, scenario, warnings):
    """The one resolution kind with no structured tree to walk at all
    (generator/compile_constraints.py's own documented escape hatch,
    §13.17) -- evaluated the only honest way available: materialize just
    the tables it names into a throwaway in-memory SQLite database and
    run the real query. This is exactly the fallback §6.5 itself names
    ("EvoSQL's alternative approach ... worth considering") applied to
    the one construct that actually needs it, not adopted program-wide."""
    conn = sqlite3.connect(':memory:')
    cur = conn.cursor()
    for table in node['tables']:
        # A table this leaf names can also carry rows written by a
        # COMPLETELY DIFFERENT record's own leaf sharing the same shared
        # candidate (raw_sql_boolean is, unlike derived_aggregate/exists,
        # never owner-scoped -- it scans the whole table) -- and different
        # leaf kinds write column keys under different casing conventions
        # (a schema_column resolution's own lowercase ground-truth name vs.
        # this SQL's own uppercase alias, e.g. real bug found running FLEX2
        # end to end, 2026-09-22: 'credits_earned' and 'CREDITS_EARNED'
        # both present on STUDENT_PROGRAM). SQLite's own column names are
        # case-insensitive, so keeping both as distinct CREATE TABLE
        # columns raises a real "duplicate column name" error the moment
        # both appear on the same table. Deduplicated case-insensitively
        # here, keeping one canonical (first-seen) casing per column, and
        # each row's own value looked up the same case-insensitive way
        # `_row_get` already does everywhere else in this module, so a row
        # that only has the OTHER casing isn't silently read as missing.
        seen = {}
        for row in candidate.rows(table):
            for c in row:
                seen.setdefault(c.lower(), c)
        cols = sorted(seen.values())
        if not cols:
            cols = ['_dummy']
        cur.execute(f'CREATE TABLE {table} ({", ".join(cols)})')
        for row in candidate.rows(table):
            placeholders = ', '.join('?' for _ in cols)
            values = []
            for c in cols:
                try:
                    values.append(_row_get(row, c))
                except FitnessEvaluationError:
                    values.append(None)
            cur.execute(f'INSERT INTO {table} ({", ".join(cols)}) VALUES ({placeholders})', values)
    sql = _PLACEHOLDER_RE.sub(lambda m: str(scenario.get(m.group(1), 'NULL')), node['sql_template'])
    try:
        cur.execute(f'SELECT ({sql})')
        result = cur.fetchone()[0]
    except sqlite3.Error as e:
        raise FitnessEvaluationError(f"raw_sql_boolean query failed against the materialized candidate: {e}")
    finally:
        conn.close()
    return bool(result)


def derive_value(var_name, node, candidate, focal, scenario, warnings=None, owner_id=None):
    """The in-memory-row-set analogue of fitness.py's evaluate_resolution
    and sql_compiler.py's compile_resolution_as_value: given a *real*
    candidate (not a hand-picked scalar), compute this leaf variable's
    actual current value.

    `owner_id` (see `_owned_rows`'s own docstring) scopes
    `derived_aggregate`/`exists`/`derived_join_count`'s own table scans
    to one objective's own rows when given -- `None` (the default, used
    by every single-objective caller: search.py's own solve_branch/
    hillclimb, and every existing self-test's hand-built fixtures) keeps
    this function's original, unscoped behavior exactly. Only
    dynamosa.py's own shared-population code passes a real owner_id."""
    warnings = warnings if warnings is not None else []
    kind = node.get('kind')
    if kind == 'schema_column':
        return _lookup(focal, node['table'], node['column'])
    if kind == 'serialized_field':
        # The blob column's own value is still just an in-memory nested
        # dict at this point -- real YAML serialization only happens in
        # materialize.py, the one place that turns a candidate into real
        # INSERT text (see that module's own comment there). A missing
        # ROW is a genuine error (same as `_lookup`'s own, for the same
        # reason: nothing yet gave this record a focal row to read at
        # all); a missing COLUMN/KEY on an otherwise-real row is NOT an
        # error the way it is for a plain schema_column -- it just means
        # no mutation has touched this particular key yet, i.e. it's
        # still at its declared default (or None, absent one).
        row = focal.get(node['table'].upper())
        if row is None:
            raise FitnessEvaluationError(
                f"no focal row given for table {node['table']!r} -- can't read "
                f"{node['table']}.{node['column']}[{node['key']}]")
        try:
            blob = _row_get(row, node['column'], node['table']) or {}
        except FitnessEvaluationError:
            blob = {}
        return blob.get(node['key'], node.get('default'))
    if kind == 'null_check':
        # A null_check's own boolean means "is the fact SET" (`is not
        # None`) UNLESS the ground truth's own notes described the
        # opposite polarity (e.g. OpenMRS's identifierBlank: "identifier
        # IS NULL OR TRIM(identifier) = ''" -- true means EMPTY, not
        # populated) -- compile_constraints.py's own `negate` flag,
        # confirmed against the notes text, not guessed here.
        negate = bool(node.get('negate'))
        if node.get('key'):
            # null_check on a serialized_field's own key (e.g. Spree's
            # amountMaxSet) -- mirrors the plain-column branch below
            # exactly (`is not None`), just one level of dict access
            # deeper, and deliberately WITHOUT the plain serialized_field
            # read's own default substitution (existence must reflect
            # whether THIS row's own blob actually set the key).
            row = focal.get(node['table'].upper())
            if row is None:
                raise FitnessEvaluationError(
                    f"no focal row given for table {node['table']!r} -- can't read "
                    f"{node['table']}.{node['column']}[{node['key']}]")
            blob = row.get(node['column']) or {}
            is_set = blob.get(node['key']) is not None
            return (not is_set) if negate else is_set
        is_set = _lookup(focal, node['table'], node['column']) is not None
        return (not is_set) if negate else is_set
    if kind == 'any_not_null':
        return any(_lookup(focal, c['table'], c['column']) is not None for c in node['columns'])
    if kind in ('join_lookup', 'join_null_check'):
        local_val = _lookup(focal, node['via']['local_table'], node['via']['local_column'])
        target_row = _find_row_by_pk(candidate, node['result_table'], node['result_column'], local_val) \
            if local_val is not None else None
        # a join *to* a row keyed by result_column only works when
        # result_column is genuinely that table's own identifying key;
        # for the (common) case where it's the same key the FK points at,
        # this is exactly right -- documented as the scope this bridges,
        # not a general arbitrary-join evaluator.
        value = _row_get(target_row, node['result_column']) if target_row else None
        return value if kind == 'join_lookup' else value is not None
    if kind == 'regex_match':
        val = _lookup(focal, node['value_column']['table'], node['value_column']['column'])
        pattern = _lookup(focal, node['pattern_column']['table'], node['pattern_column']['column'])
        if val is None or pattern is None:
            return False
        try:
            return re.search(pattern, str(val)) is not None
        except re.error as e:
            raise FitnessEvaluationError(f"{var_name!r}'s pattern column holds an invalid regex: {e}")
    if kind == 'derived_aggregate':
        self_table = node.get('self_table') or node['table']
        self_row = focal.get(self_table.upper()) if focal else None
        predicate, skipped = _mechanical_filter_predicate(node.get('filter_text'), scenario, candidate, self_row)
        if skipped:
            warnings.append(f"{var_name}: derived_aggregate filter has prose this bridge can't "
                             f"mechanically apply, counted without it: {skipped}")
        tables = [t.strip() for t in node['table'].split(',')]
        rows = _owned_rows(candidate, tables[0], owner_id)
        matching = [r for r in rows if predicate(r)]
        if node.get('value_column'):
            value_table, col = node['value_column'].split('.')
            if value_table.upper() == tables[0].upper():
                return sum((_row_get(r, col) or 0) for r in matching)
            # value_column lives on a DIFFERENT, joined-in table than
            # tables[0] -- e.g. FLEX2's degreeTotalCredits:
            # "SUM(COURSE.CREDIT_HRS) FROM PROGRAM_COURSE, COURSE". A
            # real, pre-existing bug found materializing this end to end
            # (2026-09-12): this used to read `col` straight off
            # tables[0]'s own rows regardless, which only ever "worked"
            # because build_seed_candidate's own (also-fixed) seeding
            # happened to stash it there too -- never a genuine join, and
            # never a real schema column on tables[0] either. Joined via
            # the "<TABLE>_ID" naming convention join_lookup's own
            # docstring already documents as this program's real,
            # surveyed FK convention.
            join_col = f'{value_table.upper()}_ID'
            value_rows = _owned_rows(candidate, value_table, owner_id)
            total = 0
            for r in matching:
                try:
                    key = _row_get(r, join_col)
                except FitnessEvaluationError:
                    continue
                target = next((vr for vr in value_rows
                               if vr.get(join_col, vr.get(join_col.lower())) == key), None)
                if target is not None:
                    total += _row_get(target, col) or 0
            return total
        return len(matching)
    if kind == 'exists':
        table = (node.get('candidate_tables') or [None])[0]
        if table is None:
            return False
        # A real fix (2026-09-13, the "known exists-kind filter gap"):
        # `_mechanical_filter_predicate` already degrades to "match
        # everything" when `filter_text` is None/absent, so this reduces
        # to the exact old bare "does ANY owned row exist" check for
        # every `exists`-kind leaf that has no filter (the overwhelming
        # majority) -- only a leaf whose own compiled node NOW carries a
        # real filter_text (compile_constraints.py's own classify_derived,
        # extended the same day) narrows the count to matching rows,
        # letting two differently-filtered `exists` facts on the SAME
        # table (e.g. jBilling's `hasEntitySpecificExchange` vs
        # `hasSystemDefaultExchange`, both over `currency_exchange`)
        # finally read as genuinely different booleans instead of
        # collapsing to the identical "any row at all" answer.
        self_table = node.get('self_table') or table
        self_row = focal.get(self_table.upper()) if focal else None
        predicate, _skipped = _mechanical_filter_predicate(node.get('filter_text'), scenario, candidate, self_row)
        return any(predicate(r) for r in _owned_rows(candidate, table, owner_id))
    if kind == 'raw_sql_boolean':
        return _raw_sql_boolean_value(node, candidate, scenario, warnings)
    if kind == 'derived_case':
        real_value = _lookup(focal, node['table'], node['column'])
        for k, v in node['cases']:
            if real_value == k:
                return v
        raise FitnessEvaluationError(
            f"{var_name!r}: real value {real_value!r} in {node['table']}.{node['column']} "
            f"isn't covered by any CASE_MAP case ({node['cases']}) -- an unmapped real value, "
            f"not silently defaulted to one of the known categories")
    if kind == 'derived_join_count':
        # unmetPrerequisiteCount / unmetPrerequisiteAlsoPassedCount (found
        # while testing mutation.py, 2026-09-11): count of this row's own
        # course's COURSE_PREREQ entries for which this row's own student
        # has no passing COURSE_REGISTRATION. "This row's own course/
        # student" is whichever focal row carries both key columns, not a
        # fixed table name -- see _find_focal_with_columns's docstring.
        context_table, context_row = _find_focal_with_columns(
            focal, [node['prereq_course_column'], node['registration_roll_column']])
        if context_row is None:
            raise FitnessEvaluationError(
                f"{var_name!r} (derived_join_count) needs a focal row carrying both "
                f"{node['prereq_course_column']} and {node['registration_roll_column']} "
                f"to know which course/student this count is about; none of the given "
                f"focal rows ({sorted(focal)}) has both")
        course_id = _row_get(context_row, node['prereq_course_column'], context_table)
        roll_no = _row_get(context_row, node['registration_roll_column'], context_table)
        prereq_rows = []
        for r in _owned_rows(candidate, node['prereq_table'], owner_id):
            try:
                if _row_get(r, node['prereq_course_column']) == course_id:
                    prereq_rows.append(r)
            except FitnessEvaluationError:
                continue
        unmet = 0
        for pr in prereq_rows:
            try:
                prereq_course_id = _row_get(pr, node['prereq_target_column'])
            except FitnessEvaluationError:
                continue
            passed = False
            for rr in _owned_rows(candidate, node['registration_table'], owner_id):
                try:
                    if _row_get(rr, node['registration_roll_column']) != roll_no:
                        continue
                    if _row_get(rr, node['registration_course_column']) != prereq_course_id:
                        continue
                    grade = _row_get(rr, node['registration_grade_column'])
                except FitnessEvaluationError:
                    continue
                if grade is not None and grade not in node['fail_grades']:
                    passed = True
                    break
            if not passed:
                unmet += 1
        return unmet
    if kind == 'not_persisted':
        if var_name not in scenario:
            raise FitnessEvaluationError(
                f"{var_name!r} is not_persisted (a scenario/runtime parameter) -- "
                f"no value supplied in `scenario`")
        return scenario[var_name]
    if kind == 'derived':
        # The generic catch-all classify_derived() itself couldn't pattern-
        # match into any structured shape (§7b's "Compound / Unclassified
        # Derivation" category, ~7% of ground truth) -- there is no more
        # structure here for this bridge to compute from than there was
        # for classify_derived to begin with, so this is a real, expected
        # limitation, not a missing case to add. sql_compiler.py's own
        # equivalent (compile_value_expr) emits a NULL placeholder with a
        # warning rather than refusing outright; this bridge raises
        # instead, deliberately, since a fitness *value* silently
        # standing in for "unknown" would corrupt the branch-distance
        # arithmetic (NULL has no defined distance), where SQL's own NULL
        # semantics at least make the resulting query visibly non-answering.
        raise FitnessEvaluationError(
            f"{var_name!r} is an unclassified 'derived' fact (compile_constraints.py's own "
            f"classify_derived never matched it to a structured shape) -- no mechanical value "
            f"to derive from a candidate; needs a human or a more targeted classifier pass, "
            f"the same as it does for SQL compilation")
    raise FitnessEvaluationError(f"derive_value has no handling for resolution kind {kind!r} ({var_name!r})")


def derive_genome(record, candidate, focal, scenario, warnings=None, owner_id=None):
    """Walks `record['variable_resolution']`, recursing through
    `substituted_decision`/`literal_via_upstream_branch` chains (those
    are formulas fitness.py's own evaluate_resolution already knows how
    to recompute from their free variables -- not genes themselves, so
    not populated here), and returns a genome with every true leaf
    variable's *real*, candidate-derived value -- ready to hand straight
    to `fitness.branch_fitness` unchanged.

    `owner_id` is threaded straight through to `derive_value` (see its
    own docstring) -- `None` by default, so every existing single-
    objective caller (search.py, every self-test) is completely
    unaffected; only dynamosa.py's own shared-population code passes a
    real one."""
    warnings = warnings if warnings is not None else []
    genome = {}
    if '__today__' in scenario:
        # A real, general gap found running this pipeline against
        # jBilling for the first time (2026-09-13): `fitness.py`'s own
        # `_leaf_value` reads `genome['__today__']` directly whenever a
        # record's own CONDITION calls FEEL's `today()` (e.g. `dueDate
        # PlusGrace < today()`) -- but `__today__` is a scenario-level
        # construct, never a named entry in `variable_resolution`, so
        # the walk below never had a reason to copy it into the genome
        # unless some OTHER leaf happened to be `not_persisted` and
        # coincidentally shared that exact name (it never does). Every
        # such record was stuck at a permanent, spurious
        # `FitnessEvaluationError` ("genome is missing the scenario
        # -level '__today__' gene"), string-identical regardless of how
        # good a candidate the search built, since nothing upstream of
        # `branch_fitness` ever put it there. Copied unconditionally
        # here (harmless when absent from `scenario`, and harmless as
        # an unused genome key for a record whose own condition never
        # calls `today()` at all) rather than requiring every such
        # record to awkwardly declare a fake leaf just to smuggle it
        # through.
        genome['__today__'] = scenario['__today__']

    def walk(var_name, node):
        kind = node.get('kind')
        if kind == 'literal':
            return
        if kind == 'substituted_decision':
            for fv, sub in node.get('free_variable_resolutions', {}).items():
                walk(fv, sub)
            return
        if kind == 'literal_via_upstream_branch':
            return
        if kind in ('schema_gap', 'code_external', 'unresolved', 'chained_decision_output'):
            return  # never a real gene -- fitness.py itself raises if this is actually needed
        genome[var_name] = derive_value(var_name, node, candidate, focal, scenario, warnings, owner_id=owner_id)

    for var, node in record.get('variable_resolution', {}).items():
        walk(var, node)
    return genome


def _leaf_kinds_for_seeding(var_name, node, out, blocking_kinds):
    kind = node.get('kind')
    if kind == 'substituted_decision':
        for fv, sub in node.get('free_variable_resolutions', {}).items():
            _leaf_kinds_for_seeding(fv, sub, out, blocking_kinds)
    elif kind not in ('literal', 'literal_via_upstream_branch') and kind not in blocking_kinds:
        out.append((var_name, kind, node))


_SEEDING_BLOCKING_KINDS = {'schema_gap', 'code_external', 'unresolved', 'chained_decision_output'}


def build_seed_candidate(record, today=20000):
    """Builds a minimal, generic starting `(candidate, focal, scenario)`
    for a compiled record -- no per-record hand-holding, no case-study
    -specific knowledge, just one row per table each leaf resolution
    needs, seeded with placeholder values a mutation/search pass can then
    refine. Extracted from `candidate.py`'s own full-corpus sweep
    self-check (built 2026-09-11 to answer "does genome derivation reach
    this far without hand-built fixtures") into a real, reusable
    materialization entry point -- proven already: 218/242 currently
    -compiled records produce a fully evaluable genome from exactly this
    construction, per `generator/README.md`'s own honest tally.

    Every placeholder is a real, if arbitrary, concrete value (never a
    guess at case-study semantics) -- a mutation/search pass is what
    turns these into a value that actually satisfies the branch; this
    function's only job is giving the search somewhere real to start
    from. Any `filter_text`/`sql_template` placeholder (e.g. `<student>`)
    found along the way is seeded into `scenario` too, defaulting to `1`,
    plus `__today__` for FEEL's `today()` calls."""
    leaves = []
    for var, node in record.get('variable_resolution', {}).items():
        _leaf_kinds_for_seeding(var, node, leaves, _SEEDING_BLOCKING_KINDS)

    candidate = Candidate()
    focal = {}
    scenario = {'__today__': today}
    for _var, _kind, node in leaves:
        for field in ('filter_text', 'sql_template'):
            for m in _PLACEHOLDER_RE.finditer(node.get(field) or ''):
                scenario.setdefault(m.group(1), 1)

    def ensure_row(table, col=None, val=1):
        row = focal.get(table.upper())
        if row is None:
            row = {}
            focal[table.upper()] = row
            candidate.add_row(table, row)
        if col:
            row[col] = val
        return row

    for var, kind, node in leaves:
        if kind == 'schema_column':
            ensure_row(node['table'], node['column'], 1)
        elif kind == 'null_check':
            if node.get('key'):
                # A null_check on a serialized_field's own key (e.g.
                # Spree's amountMaxSet) shares its (table, column) with
                # every OTHER key inside the same blob -- seeding
                # row[column] = 1 here (this branch's old, kind-blind
                # behaviour) stamps a bare scalar over what must stay a
                # nested dict, so a LATER read of any key on this same
                # row (plain or null_check) crashes with "'int' object
                # has no attribute 'get'". Seed a real one-key dict
                # instead, matching what a real serialized_field mutation
                # would itself write.
                row = ensure_row(node['table'])
                row.setdefault(node['column'], {})[node['key']] = 1
            else:
                ensure_row(node['table'], node['column'], 1)
        elif kind == 'serialized_field':
            row = ensure_row(node['table'])
            row.setdefault(node['column'], {})[node['key']] = node.get('default', 1)
        elif kind == 'any_not_null':
            for x in node['columns']:
                ensure_row(x['table'], x['column'], 1)
        elif kind in ('join_lookup', 'join_null_check'):
            ensure_row(node['via']['local_table'], node['via']['local_column'], 42)
            ensure_row(node['result_table'], node['result_column'], 42)
        elif kind == 'regex_match':
            ensure_row(node['value_column']['table'], node['value_column']['column'], 'abc')
            ensure_row(node['pattern_column']['table'], node['pattern_column']['column'], 'a.*')
        elif kind == 'derived_aggregate':
            # A real, filter-matching row, not a bare {'X': i} placeholder
            # -- found necessary materializing the flagship rule end to
            # end (2026-09-12, materialize.py): a row with no columns the
            # branch's own filter_text conjuncts actually name can never
            # match that filter, so the aggregate always counted 0
            # regardless of how many rows were seeded, producing an
            # immediate 0/0 division before hillclimb could even start.
            # Reuses _row_from_filter_conjuncts -- the exact same
            # mechanically-recognized-conjunct construction
            # mutation.py's own M2 "add a row" logic already uses, so a
            # seeded row and a mutation-added row are built the same way.
            tables = [t.strip() for t in node['table'].split(',')]
            value_table, value_col = (node['value_column'].split('.') if node.get('value_column') else (None, None))
            joined_value_table = value_table and value_table.upper() != tables[0].upper()
            # 3 by default (just enough to prove a >0-style branch cheaply)
            # -- but a var_name with a known, pinned real-world constant
            # (known_constants.json, e.g. lecturesHeldForOffering=30) is
            # seeded at that count directly, so the generated dataset is
            # realistic from generation 0 rather than relying on search to
            # ever happen to pick this leaf for mutation before the run
            # ends (best_value_for's own pin still applies if it IS picked
            # -- this is belt-and-braces, not the only enforcement point).
            seed_count = known_constant(record['case_study'], var) or 3
            for i in range(1, seed_count + 1):
                row = _row_from_filter_conjuncts(node.get('filter_text'), scenario,
                                                  candidate, focal, node.get('self_table') or tables[0])
                # no artificial distinguishing key needed -- these are
                # still 3 separate row objects in the list even with
                # identical content, and a fake 'X' column would only
                # break real SQLite validation later (found exactly this
                # way, 2026-09-12: "table LECTURE has no column named X").
                if value_table and not joined_value_table:
                    row[value_col] = 10
                elif joined_value_table:
                    # value_column lives on a DIFFERENT, joined-in table
                    # -- build a REAL joinable pair, not a column stamped
                    # onto the wrong table's row (a real bug found the
                    # same way: materialize.py's real SQLite validation
                    # was the first thing to ever check these seed rows
                    # against the actual schema). See derive_value's own
                    # matching fix for the "<TABLE>_ID" join convention.
                    join_col = f'{value_table.upper()}_ID'
                    row[join_col] = i
                    candidate.add_row(value_table, {join_col: i, value_col: 10})
                candidate.add_row(tables[0], row)
            for t in tables[1:]:
                if joined_value_table and t.upper() == value_table.upper():
                    continue  # already seeded with real, joinable rows above
                # An empty row, not a bogus {'X': 0} placeholder -- a real
                # bug found running this pipeline against jBilling for the
                # first time (2026-09-13): derive_value's own
                # derived_aggregate branch NEVER reads a bystander table
                # (anything past tables[0], other than value_column's own
                # joined-in table) at all, so 'X' served no functional
                # purpose here, ever -- it was pure placeholder filler
                # that also happened to not be a real schema column
                # anywhere, and nothing ever stripped it before real SQL
                # emission (unlike _OWNER_KEY, which materialize.py's own
                # _real_columns explicitly strips). `_repair_row` (called
                # once, wholesale, by repair_candidate/apply_mutation)
                # already fills in whatever real NOT NULL columns this
                # table's own schema actually requires -- an empty row
                # gives it nothing extra to accidentally leave behind.
                candidate.add_row(t, {})
        elif kind == 'exists':
            table = (node.get('candidate_tables') or [None])[0]
            if table:
                # A real, matching row when this `exists`-kind leaf
                # carries a `filter_text` (2026-09-13's own exists-kind
                # filter-support fix) -- reuses `_row_from_filter_
                # conjuncts`, the exact same construction `derived_
                # aggregate`'s own seed rows already use, so a seeded
                # `exists` row actually satisfies its OWN specific filter
                # from generation 0 rather than merely being present.
                # When there's no filter_text (the overwhelming majority
                # of `exists`-kind leaves), an empty row -- not a bogus
                # {'X': 1} placeholder: derive_value's own `exists`
                # branch degrades to a bare row-COUNT check in that case
                # (`_mechanical_filter_predicate` matches everything when
                # given no filter), so the row's presence is all that
                # ever mattered, and 'X' was never a real schema column
                # either (see the derived_aggregate case above, same bug,
                # same fix).
                if node.get('filter_text'):
                    candidate.add_row(table, _row_from_filter_conjuncts(
                        node['filter_text'], scenario, candidate, focal, node.get('self_table') or table))
                else:
                    candidate.add_row(table, {})
        elif kind == 'raw_sql_boolean':
            # A real, found-not-guessed bug (2026-09-12, discovered only
            # once materialize.py's real SQLite validation checked these
            # seed rows against the actual schema for the first time --
            # the in-memory raw_sql_boolean evaluator builds its own
            # throwaway table from whatever columns happen to be present,
            # so it never caught this): the old version pulled every
            # `alias.column` mention out of the WHOLE sql_template (which
            # names several different tables via several different
            # aliases -- e.g. CO/E/DT for COURSE_OFFER/EMPLOYEE/
            # D_EMP_TYPE) and stamped that ENTIRE mixed set onto EVERY
            # one of `node['tables']` -- so COURSE_OFFER's seed row ended
            # up carrying EMPLOYEE's and D_EMP_TYPE's own columns too.
            # Filtered per table now, against that table's real declared
            # schema columns.
            all_cols = set(re.findall(r'\b\w+\.(\w+)\b', node['sql_template']))
            for t in node['tables']:
                real_cols = _real_columns_of(record['case_study'], t)
                cols = {c for c in all_cols if c.upper() in real_cols} if real_cols else set()
                candidate.add_row(t, {col: 1 for col in cols} or {'X': 1})
        elif kind == 'derived_case':
            ensure_row(node['table'], node['column'], node['cases'][0][0])
        elif kind == 'derived_join_count':
            ctx = ensure_row(node['registration_table'], node['prereq_course_column'], 1)
            ctx[node['registration_roll_column']] = 1
            candidate.add_row(node['prereq_table'],
                               {node['prereq_course_column']: 1, node['prereq_target_column']: 2})
            candidate.add_row(node['registration_table'],
                               {node['registration_roll_column']: 1,
                                node['registration_course_column']: 2,
                                node['registration_grade_column']: 'A'})
        elif kind == 'not_persisted':
            scenario[var] = 1
    return candidate, focal, scenario


if __name__ == '__main__':
    # Two checks: (1) the flagship worked example, this time with a REAL
    # candidate row-set (including noise rows a correct filter must
    # exclude) rather than a hand-picked scalar -- the concrete answer to
    # "does the fitness design still work once real rows, not abstract
    # numbers, are behind it"; (2) a full-corpus sweep building a
    # (deliberately minimal, auto-generated) candidate for every currently
    # compiled record, to see how far genome derivation actually reaches
    # without per-record hand-holding.
    import json
    from fitness import branch_fitness, FitnessEvaluationError

    compiled = json.load(open(os.path.join(HERE, 'compiled_constraints.json')))
    rule1 = next(r for r in compiled if r['record_id'].endswith('Decision_AttendanceEligibility_Rule_1'))
    rule2 = next(r for r in compiled if r['record_id'].endswith('Decision_AttendanceEligibility_Rule_2'))

    c = Candidate()
    STUDENT, OFFERING = 2024001, 5001
    for i in range(45):
        c.add_row('LECTURE', {'LECTURE_ID': 1000 + i, 'OFFER_ID': OFFERING})
    for i in range(40):
        c.add_row('STUDENT_ATTENDANCE', {'LECTURE_ID': 1000 + i, 'ROLL_NO': STUDENT, 'ATTEND_FLAG': 'Y'})
    for i in range(40, 43):  # noise: a different student, must be excluded
        c.add_row('STUDENT_ATTENDANCE', {'LECTURE_ID': 1000 + i, 'ROLL_NO': 9999999, 'ATTEND_FLAG': 'Y'})
    for i in range(43, 45):  # noise: this student, but absent, must be excluded
        c.add_row('STUDENT_ATTENDANCE', {'LECTURE_ID': 1000 + i, 'ROLL_NO': STUDENT, 'ATTEND_FLAG': 'N'})
    scenario = {'student': STUDENT, 'this course offering': OFFERING}
    warnings = []
    genome = derive_genome(rule2, c, {}, scenario, warnings)
    print(f"Derived from {sum(len(v) for v in c.as_dict().values())} real candidate rows: {genome} "
          f"(expect lecturesAttended=40, lecturesHeldForOffering=45 -- noise rows correctly excluded)")
    print(f"Honest warnings about prose this bridge couldn't mechanically filter on: {warnings}")
    assert genome == {'lecturesAttended': 40, 'lecturesHeldForOffering': 45}
    f = branch_fitness(rule2, genome)
    print(f"branch_fitness(Rule_2) on the derived genome = {f:.4f} "
          f"(matches fitness.py's own hand-picked-scalar test exactly)")
    assert abs(f - 1.8163265306122448) < 1e-9

    # a materializable candidate: reduce attendance below the threshold
    # and confirm fitness reaches exactly 0 -- not just "close"
    c2 = Candidate()
    for i in range(45):
        c2.add_row('LECTURE', {'LECTURE_ID': 1000 + i, 'OFFER_ID': OFFERING})
    for i in range(35):
        c2.add_row('STUDENT_ATTENDANCE', {'LECTURE_ID': 1000 + i, 'ROLL_NO': STUDENT, 'ATTEND_FLAG': 'Y'})
    genome2 = derive_genome(rule2, c2, {}, scenario)
    assert branch_fitness(rule2, genome2) == 0.0
    assert branch_fitness(rule1, derive_genome(rule1, c, {}, scenario)) == 0.0
    print("Flagship real-candidate self-checks passed.")

    print()
    print("Full-corpus sweep: how far genome derivation reaches with a minimal auto-built "
          "candidate (see generator/README.md's 'candidate.py' section for the honest tally).")
    ok, errs = 0, {}
    for rec in compiled:
        auto, focal, auto_scenario = build_seed_candidate(rec)
        try:
            g = {'__today__': 20000}
            g.update(derive_genome(rec, auto, focal, auto_scenario))
            branch_fitness(rec, g)
            ok += 1
        except FitnessEvaluationError as e:
            errs.setdefault(str(e).split(' -- ')[0][:70], []).append(rec['record_id'])
        except Exception as e:
            errs.setdefault(f'UNEXPECTED {type(e).__name__}', []).append(rec['record_id'])

    print(f"Evaluable via a real (if minimal) candidate row-set: {ok}/{len(compiled)} ({ok/len(compiled)*100:.1f}%)")
    for k, v in sorted(errs.items(), key=lambda kv: -len(kv[1])):
        print(f"  {len(v):3} {k}")
