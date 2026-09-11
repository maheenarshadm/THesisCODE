import re, os, glob, json
from collections import defaultdict, OrderedDict

MIGRATE_DIR = "/home/claude/spree_research/spree/spree/core/db/migrate"

files = sorted(glob.glob(os.path.join(MIGRATE_DIR, "*.rb")),
                key=lambda f: os.path.basename(f)[:14])

tables = {}  # name -> {'columns': {col: {'null_false':bool,'type':str}}, 'indexes':[], 'fks': set(), 'checks': [], 'pk': 'id'}

def ensure_table(name):
    if name not in tables:
        tables[name] = {'columns': OrderedDict(), 'indexes': [], 'fks': set(), 'checks': [], 'pk': 'id', 'dropped': False}
    tables[name]['dropped'] = False
    return tables[name]

COL_LINE = re.compile(r'^\s*t\.(\w+)\s+[:"\']([\w]+)["\']?\s*(.*)$')
CREATE_TABLE_RE = re.compile(r'create_table\s+[:"\']([\w\.]+)["\']?\s*(.*?)do')
CHANGE_TABLE_RE = re.compile(r'change_table\s+[:"\']([\w\.]+)["\']?')
DROP_TABLE_RE = re.compile(r'drop_table\s+[:"\']([\w\.]+)["\']?')
RENAME_TABLE_RE = re.compile(r'rename_table\s+[:"\']([\w\.]+)["\']?\s*,\s*[:"\']([\w\.]+)["\']?')
ADD_COLUMN_RE = re.compile(r'add_column\s+[:"\']([\w\.]+)["\']?\s*,\s*[:"\']([\w]+)["\']?\s*,\s*[:"\']?(\w+)["\']?\s*(.*)$')
REMOVE_COLUMN_RE = re.compile(r'remove_column\s+[:"\']([\w\.]+)["\']?\s*,\s*[:"\']([\w]+)["\']?')
ADD_INDEX_RE = re.compile(r'add_index\s+[:"\']([\w\.]+)["\']?\s*,\s*(\[[^\]]+\]|[:"\']?[\w]+["\']?)\s*(.*)$')
ADD_FK_RE = re.compile(r'add_foreign_key\s+[:"\']([\w\.]+)["\']?\s*,\s*[:"\']([\w\.]+)["\']?')
REMOVE_FK_RE = re.compile(r'remove_foreign_key\s+[:"\']([\w\.]+)["\']?\s*,\s*[:"\']([\w\.]+)["\']?')
CHECK_CONSTRAINT_RE = re.compile(r't\.check_constraint\s+[\'"]([^\'"]+)[\'"]')

BLOCK_OPENER_RE = re.compile(r'^(if|unless|class|def|begin|case|module)\b')
DO_END_RE = re.compile(r'\bdo(\s*\|[^|]*\|)?\s*$')

def process_file(path):
    with open(path) as f:
        lines = f.readlines()

    stack = []  # (table_name, depth_at_open)
    depth = 0
    current_table = None
    n = len(lines)
    for i, raw in enumerate(lines):
        line = raw.rstrip("\n")
        stripped = line.strip()

        m = CREATE_TABLE_RE.search(line)
        if m:
            tname = m.group(1)
            opts = m.group(2)
            t = ensure_table(tname)
            if 'id: false' in opts:
                t['pk'] = None
            depth += 1
            current_table = tname
            stack.append((tname, depth))
            continue

        m = CHANGE_TABLE_RE.search(line)
        if m and DO_END_RE.search(line):
            tname = m.group(1)
            ensure_table(tname)
            depth += 1
            current_table = tname
            stack.append((tname, depth))
            continue

        # generic block openers/closers that don't establish a new table context
        # but must be tracked so a nested "end" doesn't prematurely close the table
        if stripped != 'end' and not m:
            if DO_END_RE.search(line):
                depth += 1
                continue
            if BLOCK_OPENER_RE.match(stripped) and not re.search(r'\bend\b\s*$', stripped):
                depth += 1
                continue

        m = DROP_TABLE_RE.search(line)
        if m:
            tname = m.group(1)
            if tname in tables:
                tables[tname]['dropped'] = True
            continue

        m = RENAME_TABLE_RE.search(line)
        if m:
            old, new = m.group(1), m.group(2)
            if old in tables:
                tables[new] = tables.pop(old)
            continue

        m = ADD_FK_RE.search(line)
        if m:
            tname, ref = m.group(1), m.group(2)
            ensure_table(tname)['fks'].add(ref)
            continue

        m = REMOVE_FK_RE.search(line)
        if m:
            tname, ref = m.group(1), m.group(2)
            if tname in tables:
                tables[tname]['fks'].discard(ref)
            continue

        m = ADD_COLUMN_RE.search(line)
        if m:
            tname, col, ctype, rest = m.group(1), m.group(2), m.group(3), m.group(4)
            t = ensure_table(tname)
            t['columns'][col] = {'type': ctype, 'null_false': 'null: false' in rest, 'ref': ctype in ('references',)}
            continue

        m = REMOVE_COLUMN_RE.search(line)
        if m:
            tname, col = m.group(1), m.group(2)
            if tname in tables and col in tables[tname]['columns']:
                del tables[tname]['columns'][col]
            continue

        m = ADD_INDEX_RE.search(line)
        if m and not stripped.startswith('#'):
            tname, cols, rest = m.group(1), m.group(2), m.group(3)
            ensure_table(tname)['indexes'].append({'unique': 'unique: true' in rest, 'cols': cols})
            continue

        m = CHECK_CONSTRAINT_RE.search(line)
        if m and current_table:
            tables[current_table]['checks'].append(m.group(1))
            continue

        # inside a create_table/change_table block: t.<type> :col ...
        if current_table:
            m = COL_LINE.match(line)
            if m:
                ctype, col, rest = m.group(1), m.group(2), m.group(3)
                if ctype in ('index',):
                    unique = 'unique: true' in rest
                    tables[current_table]['indexes'].append({'unique': unique, 'cols': col})
                elif ctype in ('references', 'belongs_to'):
                    fk = 'foreign_key: true' in rest
                    null_false = 'null: false' in rest
                    tables[current_table]['columns'][col + '_id'] = {'type': 'bigint(ref)', 'null_false': null_false}
                    if fk:
                        tables[current_table]['fks'].add(col)
                elif ctype == 'timestamps':
                    tables[current_table]['columns']['created_at'] = {'type': 'datetime', 'null_false': 'null: false' in rest}
                    tables[current_table]['columns']['updated_at'] = {'type': 'datetime', 'null_false': 'null: false' in rest}
                else:
                    null_false = 'null: false' in rest
                    tables[current_table]['columns'][col] = {'type': ctype, 'null_false': null_false}
                continue

        if stripped == 'end':
            if stack and depth == stack[-1][1]:
                stack.pop()
                current_table = stack[-1][0] if stack else None
            depth -= 1
            continue

for f in files:
    try:
        process_file(f)
    except Exception as e:
        print("ERROR", f, e)

# summarize
active_tables = {k: v for k, v in tables.items() if not v['dropped'] and k.startswith('spree_') or (not v['dropped'] and k=='friendly_id_slugs')}
# also include any non-spree_ prefixed tables not dropped (e.g. friendly_id_slugs, versions if paper_trail used)
active_tables = {k: v for k, v in tables.items() if not v['dropped']}

total_tables = len(active_tables)
total_pk = sum(1 for t in active_tables.values() if t['pk'] != None)
total_fk = sum(len(t['fks']) for t in active_tables.values())
total_unique = sum(1 for t in active_tables.values() for idx in t['indexes'] if idx['unique'])
total_checks = sum(len(t['checks']) for t in active_tables.values())
total_notnull = sum(1 for t in active_tables.values() for c, meta in t['columns'].items() if meta.get('null_false'))

print(f"Total tables (active, not dropped): {total_tables}")
print(f"Tables with PK (default id): {total_pk}")
print(f"Total FK declarations (add_foreign_key + references/belongs_to foreign_key:true): {total_fk}")
print(f"Total UNIQUE indexes: {total_unique}")
print(f"Total CHECK constraints: {total_checks}")
print(f"Total NOT NULL column declarations: {total_notnull}")
print()
print("Sample of tables with declared FKs:")
count=0
for name, t in active_tables.items():
    if t['fks']:
        print(" ", name, "->", sorted(t['fks']))
        count+=1
        if count>15: break

with open('/home/claude/spree_research/scripts/spree_schema_summary.json','w') as out:
    json.dump({k: {'columns': list(v['columns'].keys()), 'fks': sorted(v['fks']), 'unique_count': sum(1 for i in v['indexes'] if i['unique']), 'check_count': len(v['checks']), 'pk': v['pk']} for k,v in active_tables.items()}, out, indent=2)
print()
print("Total migration files processed:", len(files))
