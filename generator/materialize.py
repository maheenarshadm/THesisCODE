"""materialize.py -- design doc §6.5: turning a solved in-memory
`Candidate` into a real, ordered dataset, plus the "non-negotiable"
validation pass against a real DBMS rather than trusting hand-written
distance functions alone.

Three things, in the order §6.5 itself describes them:

1. **Ordering** (`topological_table_order`): lookup tables -> identity
   tables -> fact tables, derived from the schema's own `fk_columns`
   data (§6.5: "real INSERT statements, ordered to respect FK
   dependencies") -- a real topological sort (Kahn's algorithm), not a
   guess at table "tiers." A genuine FK cycle (rare, but real schemas
   have them -- a self-referencing manager_id, two tables pointing at
   each other) is broken by placing the least-blocked table next rather
   than crashing, and reported, never silently hidden.

2. **Emission**: `to_sql_inserts` (real `INSERT` statements) and
   `write_csv_files` (one CSV per table) -- two views of the exact same
   materialized rows, since "real generated datasets" was named as the
   deliverable and different consumers want different formats.

3. **Validation** (`validate_with_sqlite`): §6.5's own "non-negotiable"
   check -- attempts the actual inserts against a real SQLite database,
   built from the schema's own declared DDL (columns, types, NOT NULL,
   PK), then checks FK integrity separately via `PRAGMA foreign_key_
   check` against the fully-populated data at rest (order-independent,
   so a genuine FK cycle -- see point 1 -- is never mistaken for a real
   violation), and reports every failure honestly. The engine is the
   ground truth for constraint satisfaction, not `fitness.py`'s own
   hand-written distance functions -- this is what actually proves a
   materialized candidate is real, valid data, independent of whether
   `candidate_constraint_fitness` agrees.

Usage:
    from materialize import to_sql_inserts, write_csv_files, validate_with_sqlite
    statements, warnings = to_sql_inserts(candidate, schema)
    ok, errors = validate_with_sqlite(candidate, schema)
"""
import csv
import os
import re
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from candidate import _OWNER_KEY  # noqa: E402


def _real_columns(row):
    """`row` minus dynamosa.py's own `_OWNER_KEY` bookkeeping tag (the
    aggregate row-sharing fix, 2026-09-13: DynaMOSA-produced candidates
    now stamp every row they create with which objective owns it, purely
    an in-memory scoping device for `candidate.py`'s own `_owned_rows` --
    it names no real schema column and must never reach actual SQL/CSV
    output, or every emitted table would grow a bogus `__owner__` column
    `validate_with_sqlite`'s own real DDL (built from the schema, which
    of course has no such column) would then reject outright."""
    return {k: v for k, v in row.items() if k != _OWNER_KEY}


def topological_table_order(schema, tables):
    """Orders `tables` (any iterable of table names) so every table's own
    FK targets that are *also* in `tables` appear before it. Returns
    (order, warnings) -- warnings name any FK cycle found among the given
    tables (broken by placing the least-blocked table next, not by
    crashing Kahn's algorithm) and never pass silently."""
    tables = {t.upper() for t in tables}
    deps = {t: set() for t in tables}
    for t in tables:
        info = schema.get(t) or schema.get(t.upper()) or schema.get(t.lower()) or {}
        for fk in info.get('fk_columns') or []:
            ref = fk['ref_table'].upper()
            if ref in tables and ref != t:
                deps[t].add(ref)

    order, placed, warnings = [], set(), []
    remaining = dict(deps)
    while remaining:
        ready = sorted(t for t, d in remaining.items() if d <= placed)
        if not ready:
            # a real cycle among the still-remaining tables -- break it
            # deterministically (fewest unmet deps first) rather than
            # looping forever or raising; the cycle is named, not hidden.
            t = min(remaining, key=lambda k: (len(remaining[k]), k))
            warnings.append(f"FK cycle among {sorted(remaining)} -- placed {t!r} out of "
                             f"strict dependency order to break it")
            ready = [t]
        for t in ready:
            order.append(t)
            placed.add(t)
            del remaining[t]
    return order, warnings


def _sql_literal(value):
    if value is None:
        return 'NULL'
    if isinstance(value, bool):
        return 'TRUE' if value else 'FALSE'
    if isinstance(value, (int, float)):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def serialize_yaml_hash_blob(blob):
    """The ONE place a `serialized_field` mutation's in-memory nested dict
    (see mutation.py's own `_apply_field_mutation`/candidate.py's
    `derive_value`) becomes real column text -- everywhere else in the
    search, it's an ordinary-looking Python dict, never touched as a
    string. Mirrors Rails' own default `serialize :col, type: Hash, coder:
    YAML` convention (confirmed directly against Spree's real source,
    `lib/spree/core/preferences/preferable.rb`): keys rendered with a
    leading `:`, the same way Psych renders a Ruby Hash keyed by symbols
    -- not required for this mechanism's own internal correctness (writer
    and reader here always agree with each other regardless), but it
    keeps the materialized database looking like something a real Spree
    instance could have produced, which is the whole point of testing
    against a schema-shaped database in the first place.
    `validation_oracle/db_resolver.py` has its own, independent
    implementation of the read side of this SAME convention (this
    project's own architectural separation rule: validation_oracle never
    imports generator code)."""
    import yaml
    return yaml.safe_dump({f':{k}': v for k, v in blob.items()}, default_flow_style=False)


def _single_pk_column(table, schema):
    """-> the table's own single-column surrogate-key name, or None (no
    PK, or a composite PK -- this function only ever fills in a lone
    auto-increment-style id, never touches a composite key, which is
    always made of real FK/business values a row either already has or
    was never meant to get one from here). Mirrors `create_table_ddl`'s
    own `pk`/`pk_cols` lookup so both read the schema the same way."""
    info = schema.get(table) or schema.get(table.upper()) or schema.get(table.lower()) or {}
    pk = info.get('pk')
    pk_cols = pk if isinstance(pk, list) else ([pk] if pk else [])
    return pk_cols[0] if len(pk_cols) == 1 else None


def _fill_missing_surrogate_keys(table, rows, schema):
    """A row missing its table's own single-column surrogate key (never
    given one during construction/repair -- see e.g. a shared/default
    focal row no covered rule ever needed to anchor via FK) would
    otherwise reach `to_sql_inserts` with that column simply absent, and
    SQLite's own INTEGER PRIMARY KEY column then auto-assigns it the
    next free *rowid at that point in this connection's own insert
    sequence* -- a value with NO knowledge of this same materialization's
    OTHER, unrelated rows that already carry an explicit, offset-derived
    id for the SAME table (dynamosa.py's own per-objective merge-time key
    offsetting, see `_key_columns_for`). Two independent id sources
    (SQLite's lazy per-INSERT auto-rowid vs. this pipeline's own
    explicit offsetting) can legitimately land on the identical number,
    since neither one is aware the other exists -- confirmed directly
    against Spree's own `spree_merged.db` rebuild (2026-09-24):
    `SPREE_ORDERS`'s row for `Promotion Tiered Percent Discount
    Selection::rule_1` (no real FK relationship at all to the row that
    later collided with it) had no `id` set, got auto-assigned 16000004
    by SQLite mid-sequence, and a wholly unrelated, later-emitted row for
    `One-Use-Per-User Promotion Eligibility::rule_3` legitimately carried
    that same explicit offset-derived id -- a real `UNIQUE constraint
    failed` with no FK/schema-declaration gap behind it: the two rows
    share no relationship an FK could express.

    Fixed here, once, with full knowledge of every id this table's rows
    already carry: any row missing this table's single-column surrogate
    key gets assigned one explicitly, past the current max of every
    *already-set* value for that column across this whole table -- so
    it can never coincide with an explicit, already-offset id emitted
    anywhere else in the same run, and SQLite's own auto-rowid is never
    relied upon at all."""
    pk_col = _single_pk_column(table, schema)
    if pk_col is None:
        return rows
    used = [row[pk_col] for row in rows
            if row.get(pk_col) is not None]
    if not all(isinstance(v, (int, float)) for v in used):
        return rows
    next_id = int(max(used)) + 1 if used else 1
    filled = []
    for row in rows:
        if row.get(pk_col) is None:
            row = dict(row)
            row[pk_col] = next_id
            next_id += 1
        filled.append(row)
    return filled


def to_sql_inserts(candidate, schema):
    """-> (statements, warnings). One INSERT per row, tables in FK
    dependency order; a row's own column order is preserved (insertion
    order, not resorted) since SQL INSERT names its columns explicitly.

    Any row still missing its own table's single-column surrogate key
    at this point gets one assigned here, explicitly and with full
    knowledge of every id already used in that same table -- see
    `_fill_missing_surrogate_keys`'s own docstring for the real
    collision this prevents (SQLite's own implicit NULL-rowid
    auto-assignment has no visibility into this pipeline's own
    explicit, offset-derived ids elsewhere in the same table)."""
    as_dict = candidate.as_dict()
    order, warnings = topological_table_order(schema, as_dict.keys())
    statements = []
    for table in order:
        rows = _fill_missing_surrogate_keys(table, candidate.rows(table), schema)
        for row in rows:
            row = _real_columns(row)
            if not row:
                continue
            # A `serialized_field` mutation leaves its column holding a
            # plain in-memory dict (see this module's own
            # serialize_yaml_hash_blob docstring) -- turned into real
            # column text HERE, the one point a candidate becomes actual
            # SQL, never earlier.
            row = {c: (serialize_yaml_hash_blob(v) if isinstance(v, dict) else v)
                   for c, v in row.items()}
            cols = list(row.keys())
            statements.append(
                f"INSERT INTO {table} ({', '.join(cols)}) VALUES "
                f"({', '.join(_sql_literal(row[c]) for c in cols)});")
    return statements, warnings


def write_csv_files(candidate, out_dir):
    """Writes one CSV per non-empty table under `out_dir`. Column set is
    the union of keys actually present across that table's rows (not the
    schema's full declared column list) -- an honest reflection of what
    was actually generated, not padded with columns nothing ever set."""
    os.makedirs(out_dir, exist_ok=True)
    written = []
    for table, raw_rows in candidate.as_dict().items():
        rows = [_real_columns(row) for row in raw_rows]
        if not rows:
            continue
        cols = sorted({c for row in rows for c in row})
        path = os.path.join(out_dir, f"{table}.csv")
        with open(path, 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            for row in rows:
                w.writerow(row)
        written.append(path)
    return written


_VALID_TYPE_SUFFIX = re.compile(r'^\(\s*\d+(\s*,\s*\d+)?\s*\)$')


def _sqlite_type(type_name):
    # SQLite's type affinity is lenient about the exact name -- pass the
    # schema's own declared type straight through (NUMBER/VARCHAR2/CHAR/
    # DATE/...) so the validation DDL matches what the schema actually
    # says, rather than translating to SQLite-native names no one wrote.
    #
    # A parenthetical suffix is only ever real SQL when it's a length/
    # precision modifier (VARCHAR(255), DECIMAL(10,2)) -- kept as-is.
    # Anything else is stripped, not passed through: a real, widespread
    # data-quality artifact found running this pipeline against Spree
    # for the first time (2026-09-13), unrelated to any case study this
    # pipeline had exercised before -- 242 columns in Spree's own
    # ground-truth schema JSON carry a type string like "bigint(ref)"
    # (traced to the source `schema.rb`'s own `t.bigint "col",
    # null: false` line, which names no parenthetical at all -- an
    # artifact of the separate schema-extraction pass that produced this
    # JSON, not of anything in this pipeline). Passed straight through,
    # "bigint(ref)" is not valid SQL and made every CREATE TABLE
    # naming such a column fail outright with a syntax error --
    # confirmed directly via `validate_with_sqlite`, not assumed. FLEX2/
    # OpenMRS have zero such entries (a real data-quality difference
    # between the four case studies' own schema-extraction runs, not
    # something this fix special-cases per case study).
    type_name = type_name or 'TEXT'
    match = re.match(r'^([A-Za-z_][A-Za-z0-9_ ]*)(\(.*\))?$', type_name.strip())
    if not match:
        return type_name
    base, suffix = match.group(1), match.group(2)
    if suffix and not _VALID_TYPE_SUFFIX.match(suffix):
        return base
    return type_name


def create_table_ddl(table, schema, known_tables):
    """-> a real CREATE TABLE statement from the schema's own declared
    columns/types/NOT NULL/PK/FK, or None if this table has no schema
    entry at all (the caller reports that honestly rather than treating
    a placeholder table as validated).

    `known_tables` -- the full set of tables actually being materialized
    this run -- matters for real correctness, not just tidiness: a FK
    clause naming a table that ISN'T part of `known_tables` makes SQLite
    reject the statement with "no such table" the moment FK enforcement
    is on, *regardless of whether any row ever violates it* (a real bug
    found materializing the flagship rule end to end, 2026-09-12: nothing
    in the candidate ever set BATCH.SHIFT_ID -- a nullable FK, never a
    NOT NULL gap repair needed to fill -- yet its declared FK to D_SHIFT
    still broke the CREATE TABLE, since a per-branch materialization only
    ever creates the FK-closure subset relevant to THIS candidate, not
    every table the full schema ever names). So a FK to a table this
    materialization never included is dropped from the DDL -- correct,
    not a workaround: an unset nullable FK column was never checked by
    real SQL anyway, only a *set* one is, and repair_candidate already
    guarantees any FK column that got a real value also got a real
    parent row materialized alongside it."""
    info = schema.get(table) or schema.get(table.upper()) or schema.get(table.lower()) or {}
    columns = info.get('columns') or {}
    if not columns:
        return None
    pk = info.get('pk')
    pk_cols = pk if isinstance(pk, list) else ([pk] if pk else [])
    defs = []
    for col, meta in columns.items():
        parts = [col, _sqlite_type(meta.get('type'))]
        if meta.get('null_false'):
            parts.append('NOT NULL')
        defs.append(' '.join(parts))
    # A declared PK column not itself among `columns` -- another real,
    # widespread schema-JSON artifact found the same run as the type-
    # string one above: Rails' own `schema.rb` never lists its implicit
    # auto-increment `id` column among a table's explicit `t.<type>
    # "col"` lines (it's added automatically by `create_table`), so a
    # schema-extraction pass reading that file faithfully never sees it
    # either -- yet the SAME extraction still records `"pk": "id"`
    # (correctly, Rails' own default). SQLite's own `PRIMARY KEY (...)`
    # table constraint requires every named column to already be
    # declared, so emitting it unconditionally crashed CREATE TABLE with
    # "no such column: id" -- confirmed on 196 of Spree's own tables
    # (jBilling has 3 of the same shape too; FLEX2/OpenMRS have none,
    # since their own extraction always declared PK columns explicitly).
    # Synthesized here as a plain INTEGER column when missing -- SQLite
    # treats a single-column INTEGER PRIMARY KEY as its own rowid alias,
    # which is exactly the right semantics for an implicit Rails id
    # column, and every row this pipeline ever inserts always supplies
    # its own explicit value regardless.
    for col in pk_cols:
        if col not in columns:
            defs.append(f"{col} INTEGER")
    if pk_cols:
        defs.append(f"PRIMARY KEY ({', '.join(pk_cols)})")
    for fk in info.get('fk_columns') or []:
        if fk['ref_table'].upper() in known_tables:
            defs.append(f"FOREIGN KEY ({fk['column']}) REFERENCES {fk['ref_table']}({fk['ref_column']})")
    return f"CREATE TABLE {table} ({', '.join(defs)});"


def validate_with_sqlite(candidate, schema):
    """§6.5's own 'non-negotiable' validation pass: creates a throwaway
    in-memory SQLite database from the schema's real DDL, attempts every
    one of the candidate's own rows as a genuine INSERT, then checks FK
    integrity for real via `PRAGMA foreign_key_check` against the data
    at rest. Returns (ok, errors) -- ok is True only when every table
    got created, every row inserted cleanly, AND no FK check violation
    remains; errors names each failure (which table, which row, the
    engine's own reason), never swallowed. The engine is the ground
    truth here, not candidate_constraint_fitness's own hand-written
    distance math -- this is what actually proves a materialized
    candidate is real, valid data, independent of whether that separate
    check agrees.

    `topological_table_order`'s own FK-cycle notes are informational,
    not failures -- its own docstring already calls them "warnings," and
    (now that FK enforcement during INSERT is off, see below) a cycle
    note no longer implies anything actually went wrong. Kept in the
    returned `errors` list for visibility (a real schema shape worth
    knowing about), but never counted toward `ok` -- a real bug in this
    function's own earlier version, found the same day as the insert
    -order fix below: a dataset that validated perfectly clean (zero
    real INSERT/FK-check failures) was still reported `ok=False` purely
    because its schema happens to have a cycle.

    **FK enforcement is deliberately NOT turned on during the INSERT
    loop itself** (a real bug found running OpenMRS end to end for the
    first time, 2026-09-13): `topological_table_order` already documents
    that a genuine FK cycle is broken by placing one table "out of
    strict dependency order" -- but per-statement `PRAGMA foreign_keys =
    ON` enforcement is fundamentally insert-ORDER-sensitive, so breaking
    a cycle this way ALWAYS makes the row inserted first fail (its own
    FK target genuinely isn't in the table yet), even when the full,
    completed dataset would be entirely FK-consistent -- confirmed
    directly: OpenMRS's own real schema has one large (28-table) FK
    cycle (`USERS` -> `PERSON` -> ... -> `USERS` and similar), and 254 of
    its own rows were flagged as FK failures purely as an artifact of
    insertion order, not because any of them actually dangled. Fixed by
    inserting with FK enforcement OFF (order-independent -- catches only
    genuine per-statement failures: NOT NULL/CHECK/UNIQUE/type), then
    running `PRAGMA foreign_key_check` once against the fully-populated,
    at-rest database -- a read-only, order-independent scan that finds
    every ACTUAL dangling reference (confirmed directly against a
    hand-built 2-table cycle: a legitimately-cyclic pair of rows passes
    clean, a genuinely dangling FK on a third row is still caught) while
    never flagging a row purely for having been inserted before its own
    target."""
    order, cycle_warnings = topological_table_order(schema, candidate.as_dict().keys())
    errors = list(cycle_warnings)
    real_errors = []
    known_tables = set(order)

    def add_error(msg):
        errors.append(msg)
        real_errors.append(msg)

    conn = sqlite3.connect(':memory:')
    cur = conn.cursor()
    created = set()
    for table in order:
        ddl = create_table_ddl(table, schema, known_tables)
        if ddl is None:
            add_error(f"{table}: no schema entry to build DDL from -- its rows are unvalidated")
            continue
        try:
            cur.execute(ddl)
            created.add(table)
        except sqlite3.Error as e:
            add_error(f"{table}: CREATE TABLE failed -- {e} (DDL: {ddl})")
    row_by_rowid = {}
    for table in order:
        if table not in created:
            continue
        rows = _fill_missing_surrogate_keys(table, candidate.rows(table), schema)
        for i, row in enumerate(rows):
            row = _real_columns(row)
            if not row:
                continue
            cols = list(row.keys())
            try:
                cur.execute(f"INSERT INTO {table} ({', '.join(cols)}) VALUES "
                            f"({', '.join('?' for _ in cols)})", [row[c] for c in cols])
                row_by_rowid[(table, cur.lastrowid)] = (i, row)
            except sqlite3.Error as e:
                add_error(f"{table} row {i} {row}: INSERT failed -- {e}")
    for table, rowid, ref_table, fkid in cur.execute('PRAGMA foreign_key_check;').fetchall():
        i, row = row_by_rowid.get((table, rowid), ('?', None))
        add_error(f"{table} row {i} {row}: dangling FK into {ref_table} (constraint #{fkid})")
    conn.close()
    return len(real_errors) == 0, errors


if __name__ == '__main__':
    import json
    from candidate import Candidate, derive_genome, build_seed_candidate
    from fitness import branch_fitness, FitnessEvaluationError
    from mutation import hillclimb, _schema_for, repair_candidate

    compiled = json.load(open(os.path.join(HERE, 'compiled_constraints.json')))
    rule2 = next(r for r in compiled if r['record_id'].endswith('Decision_AttendanceEligibility_Rule_2'))
    schema = _schema_for('FLEX2')

    # --- Test 1: topological_table_order, including a deliberate cycle
    # (a real, if rare, schema shape -- confirm it's broken, not crashed,
    # and reported). ------------------------------------------------------
    cyclic_schema = {
        'A': {'fk_columns': [{'column': 'b_id', 'ref_table': 'B', 'ref_column': 'id'}]},
        'B': {'fk_columns': [{'column': 'a_id', 'ref_table': 'A', 'ref_column': 'id'}]},
        'C': {'fk_columns': [{'column': 'a_id', 'ref_table': 'A', 'ref_column': 'id'}]},
    }
    order, warnings = topological_table_order(cyclic_schema, ['A', 'B', 'C'])
    print(f"Cyclic-schema order: {order}, warnings: {warnings}")
    assert order.index('A') < order.index('C'), "C depends on A -- A must still come first"
    assert warnings, "a real FK cycle must be reported, not silently resolved"
    print("  Confirmed: cycle broken deterministically and reported, dependency outside the cycle still honored.")

    real_order, real_warnings = topological_table_order(schema, ['STUDENT_ATTENDANCE', 'LECTURE', 'COURSE_OFFER'])
    print(f"\nReal FLEX2 order for STUDENT_ATTENDANCE/LECTURE/COURSE_OFFER: {real_order}")
    assert real_order == ['COURSE_OFFER', 'LECTURE', 'STUDENT_ATTENDANCE'], \
        "COURSE_OFFER <- LECTURE <- STUDENT_ATTENDANCE is the real FK chain"
    assert not real_warnings
    print("  Confirmed: matches the real FK chain exactly, no cycle in real data.")

    # --- Test 2: materialize + validate a REAL, hand-verified-clean
    # solved candidate (reusing mutation.py's own flagship self-check
    # setup) -- proves the emission + validation machinery itself is
    # correct against known-good data before testing the fully-generic
    # pipeline below. --------------------------------------------------
    STUDENT, OFFERING = 2024001, 5001
    start = Candidate()
    start.add_row('STUDENT_PROGRAM', {'ROLL_NO': STUDENT})
    for i in range(45):
        start.add_row('LECTURE', {'LECTURE_ID': 1000 + i, 'OFFER_ID': OFFERING})
    for i in range(44):
        start.add_row('STUDENT_ATTENDANCE', {'LECTURE_ID': 1000 + i, 'ROLL_NO': STUDENT, 'ATTEND_FLAG': 'Y'})
    scenario = {'student': STUDENT, 'this course offering': OFFERING}
    repair_candidate(start, 'FLEX2')  # see repair_candidate's own docstring: a hand-built
    # candidate is exactly as informationally-thin as build_seed_candidate's own output
    # on any row the search itself never has reason to touch (STUDENT_PROGRAM here).
    solved, focal, scenario, history = hillclimb(rule2, start, {}, scenario, max_iters=100)
    g = derive_genome(rule2, solved, focal, scenario)
    assert branch_fitness(rule2, g) == 0.0, "hillclimb should have solved this branch"

    statements, sql_warnings = to_sql_inserts(solved, schema)
    print(f"\nMaterialized {len(statements)} INSERT statements ({sum(len(v) for v in solved.as_dict().values())} "
          f"real rows across {len(solved.as_dict())} tables), {len(sql_warnings)} ordering warnings.")
    print("  First 3:", statements[:3])

    ok, errors = validate_with_sqlite(solved, schema)
    print(f"validate_with_sqlite: ok={ok}, {len(errors)} error(s)")
    for e in errors[:5]:
        print("   ", e)
    assert ok, f"a hillclimb-solved, repair-by-construction candidate should validate cleanly -- got: {errors}"
    print("  Confirmed: a real solved candidate materializes and validates cleanly against real SQLite DDL.")

    out_dir = os.path.join(HERE, '_materialize_selftest_csv')
    written = write_csv_files(solved, out_dir)
    print(f"Wrote {len(written)} CSV files to {out_dir}: {[os.path.basename(w) for w in written]}")

    # --- Test 3: honest end-to-end check -- does the fully-generic
    # pipeline (build_seed_candidate, repair_candidate, hillclimb, with NO
    # per-record hand-holding) produce something that validates too? -----
    print()
    print("End-to-end check: build_seed_candidate() -> repair_candidate() -> hillclimb() "
          "-> materialize/validate, no hand-holding:")
    auto, auto_focal, auto_scenario = build_seed_candidate(rule2)
    repair_candidate(auto, 'FLEX2')
    solved2, focal2, scenario2, history2 = hillclimb(rule2, auto, auto_focal, auto_scenario, max_iters=200)
    g2 = derive_genome(rule2, solved2, focal2, scenario2)
    dmn_fitness = branch_fitness(rule2, g2)
    ok2, errors2 = validate_with_sqlite(solved2, schema)
    print(f"  DMN branch_fitness={dmn_fitness}, validates_cleanly={ok2}, {len(errors2)} error(s)")
    for e in errors2[:8]:
        print("   ", e)
    assert dmn_fitness == 0.0 and ok2, (
        f"the fully-generic pipeline (no hand-built fixtures at all) should reach a real, "
        f"schema-clean, DMN-solved dataset for this record -- got fitness={dmn_fitness}, errors={errors2}")
    print("  Confirmed: the fully-generic pipeline -- no hand-built fixtures anywhere -- produces a "
          "real, schema-clean, DMN-solved dataset end to end.")

    print("\nmaterialize.py core self-checks passed (topological order, SQL/CSV emission, SQLite validation).")
