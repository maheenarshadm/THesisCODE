#!/usr/bin/env python3
"""
Core DMN-to-schema mapper: candidate generation + confidence scoring, per
§5.3 of the project design doc. Never force-picks a single guess -- outputs
ranked candidates plus a confidence-gated "predicted_mapping_type" so a
human (or a later LLM pass, §5.4) reviews anything below the threshold
instead of trusting a low-confidence match silently.

Inputs (produced by schema_extract.py / dmn_extract.py):
    schema_columns.csv   -- case_study, table, column, sql_type,
                             abstract_type, nullable, is_pk,
                             fk_target_table, fk_target_column, source
    dmn_variables.csv    -- case_study, dmn_file, decision_name, io,
                             variable_name, feel_type, literal_values, label

Output: mapping_auto.csv, one row per DMN input/output variable:
    case_study, dmn_file, decision_name, io, variable_name, feel_type,
    predicted_table, predicted_column, confidence, predicted_mapping_type,
    top3_candidates, notes

Scoring (all combined into one 0-1 confidence per candidate column):
  1. token similarity   -- Jaccard over tokenized words + a sequence-ratio
                            term on the joined lowercase strings
  2. type compatibility -- hard gate: incompatible abstract types are
                            heavily discounted, not eliminated (schema
                            typing is heuristic on both sides, see
                            schema_extract.py's docstring)
  3. enum-name bonus    -- small bonus when a categorical DMN variable
                            (non-empty literal_values) is matched against a
                            column whose own name looks enum/status/type-ish
                            (no seed data exists for any of the four schemas
                            to check actual stored values against, so this
                            is a naming heuristic, not a value-set check --
                            see design doc §10's "no seed data" caveat)
  4. decision-context    -- small bonus when a token from the decision
     bonus                 name / DMN file name also appears in the table
                            name (weak topical proximity signal)

Outputs are never a single forced guess: below CONFIDENCE_THRESHOLD the
predicted_mapping_type is 'needs review' rather than a committed match,
mirroring how the hand-built mappings recorded 'no match' as a valid,
informative outcome rather than a failure.
"""
import csv
import re
import argparse
from collections import defaultdict
from difflib import SequenceMatcher

CONFIDENCE_THRESHOLD = 0.45

DERIVED_HINT_WORDS = {
    'count', 'countof', 'percentage', 'percent', 'ratio', 'total', 'sum',
    'average', 'avg', 'exists', 'any', 'all', 'match', 'matches',
    'matched', 'duplicate', 'cumulative', 'elapsed', 'remaining',
    'accumulation', 'aggregate',
}

ENUM_ISH_COL_WORDS = {'status', 'type', 'state', 'flag', 'behavior',
                       'category', 'code', 'kind', 'method'}


def tokenize(name):
    """camelCase / snake_case / space -> lowercase word tokens."""
    s = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', name or '')
    s = re.sub(r'[^A-Za-z0-9]+', '_', s)
    toks = [t.lower() for t in s.split('_') if t]
    return toks


def token_similarity(a_tokens, b_tokens, a_raw, b_raw):
    set_a, set_b = set(a_tokens), set(b_tokens)
    if not set_a or not set_b:
        jaccard = 0.0
    else:
        jaccard = len(set_a & set_b) / len(set_a | set_b)
    seq_ratio = SequenceMatcher(None, a_raw.lower(), b_raw.lower()).ratio()
    return 0.55 * jaccard + 0.45 * seq_ratio


def feel_type_category(feel_type):
    t = (feel_type or '').lower()
    if t in ('date', 'date and time', 'time'):
        return 'date'
    if t == 'boolean':
        return 'boolean'
    if t == 'number':
        return 'number'
    if t == 'string':
        return 'string'
    return 'unknown'


def score_candidate(var_name, var_tokens, feel_cat, literal_values, decision_tokens,
                     table, column, abstract_type, is_pk, source):
    col_tokens = tokenize(column)
    table_tokens = tokenize(table)

    sim = token_similarity(var_tokens, col_tokens, var_name, column)

    # type compatibility gate
    if feel_cat != 'unknown' and abstract_type != 'unknown':
        if feel_cat == abstract_type:
            type_factor = 1.0
        else:
            type_factor = 0.35  # discount hard, don't zero out (typing is heuristic on both sides)
    else:
        type_factor = 0.85  # unknown on either side: don't penalize, but don't reward either

    score = sim * type_factor

    # enum-name bonus
    if literal_values and any(w in col_tokens for w in ENUM_ISH_COL_WORDS):
        score += 0.05

    # decision-context bonus
    if decision_tokens & set(table_tokens):
        score += 0.05

    # mild bonus for matching a primary-key-shaped id variable name to a PK
    if is_pk and var_tokens and var_tokens[-1] in ('id',):
        score += 0.03

    return min(score, 1.0)


def looks_derived(var_tokens):
    return bool(DERIVED_HINT_WORDS & set(var_tokens))


def load_schema(path):
    by_case = defaultdict(list)
    with open(path, encoding='utf-8') as f:
        for row in csv.DictReader(f):
            by_case[row['case_study']].append(row)
    return by_case


def load_dmn_vars(path):
    with open(path, encoding='utf-8') as f:
        return list(csv.DictReader(f))


def map_all(schema_path, dmn_path, out_path, top_n=3):
    schema_by_case = load_schema(schema_path)
    dmn_rows = load_dmn_vars(dmn_path)

    out_rows = []
    for row in dmn_rows:
        cs = row['case_study']
        var_name = row['variable_name']
        if not var_name:
            continue
        var_tokens = tokenize(var_name)
        feel_cat = feel_type_category(row['feel_type'])
        literal_values = row['literal_values']
        decision_tokens = set(tokenize(row['decision_name'])) | set(tokenize(row['dmn_file']))

        candidates = []
        for col in schema_by_case.get(cs, []):
            s = score_candidate(
                var_name, var_tokens, feel_cat, literal_values, decision_tokens,
                col['table'], col['column'], col['abstract_type'],
                col['is_pk'] == 'True', col['source'])
            candidates.append((s, col['table'], col['column'], col['abstract_type']))

        candidates.sort(key=lambda c: c[0], reverse=True)
        top = candidates[:top_n]
        best_score, best_table, best_col, best_abs = top[0] if top else (0.0, '', '', '')

        derived_hint = looks_derived(var_tokens)
        if row['io'] == 'output':
            predicted_type = 'not-persisted (output/control-flow, default)'
            best_table, best_col = '', ''
            confidence = ''
        elif best_score >= CONFIDENCE_THRESHOLD and not derived_hint:
            predicted_type = 'direct (auto, confident)'
            confidence = round(best_score, 3)
        elif best_score >= CONFIDENCE_THRESHOLD and derived_hint:
            predicted_type = 'derived (auto, needs formula review)'
            confidence = round(best_score, 3)
        elif derived_hint:
            predicted_type = 'likely derived (auto, low confidence -- needs review)'
            confidence = round(best_score, 3)
            best_table, best_col = '', ''
        else:
            predicted_type = 'needs review (no confident match)'
            confidence = round(best_score, 3)
            best_table, best_col = '', ''

        top3_str = '; '.join(f'{t}.{c} ({s:.2f})' for s, t, c, _ in top)

        out_rows.append({
            'case_study': cs, 'dmn_file': row['dmn_file'],
            'decision_name': row['decision_name'], 'io': row['io'],
            'variable_name': var_name, 'feel_type': row['feel_type'],
            'predicted_table': best_table, 'predicted_column': best_col,
            'confidence': confidence, 'predicted_mapping_type': predicted_type,
            'top3_candidates': top3_str,
            'notes': 'auto-generated, unreviewed' if 'needs review' in predicted_type
                      or 'low confidence' in predicted_type else 'auto-generated',
        })

    with open(out_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=[
            'case_study', 'dmn_file', 'decision_name', 'io', 'variable_name',
            'feel_type', 'predicted_table', 'predicted_column', 'confidence',
            'predicted_mapping_type', 'top3_candidates', 'notes'])
        w.writeheader()
        w.writerows(out_rows)

    return out_rows


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--schema', default='schema_columns.csv')
    ap.add_argument('--dmn', default='dmn_variables.csv')
    ap.add_argument('--out', default='mapping_auto.csv')
    args = ap.parse_args()

    rows = map_all(args.schema, args.dmn, args.out)
    from collections import Counter
    c = Counter(r['predicted_mapping_type'] for r in rows)
    print(f"Total variable rows mapped: {len(rows)}")
    for k, v in c.most_common():
        print(f"  {k}: {v}")
    print(f"Written to {args.out}")
