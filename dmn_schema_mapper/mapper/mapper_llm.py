#!/usr/bin/env python3
"""
LLM-assisted second pass over the algorithmic mapper's low-confidence rows,
per design doc §5.4/§5.5. This is the "restricted to exactly the rows the
prototype marks needs review/likely derived, choosing only among its
pre-generated top-3 candidates" pass §5.5 named as the natural next step
and left unbuilt.

Design, matching §5.4 point by point:
  1. Never given the whole schema. Only mapper.py's own top-3 pre-filtered
     candidates for one variable are ever shown to the model in one call.
  2. Yes/no/unknown per candidate pair, not open-ended "what's the match" --
     one call judges exactly one (variable, candidate) pair.
  3. Majority-vote across repeated calls (--repeats, default 3) to dampen
     inconsistency/hallucination.
  4. The model is never asked to name a column -- it only ever answers
     yes/no/unknown about a candidate mapper.py already verified exists in
     schema_columns.csv. A response that isn't recognizably yes/no/unknown
     is recorded as 'unknown', never coerced into a guess.
  5. Evaluated against variable_to_schema_mapping.csv exactly the way
     validate_mapper.py evaluates the plain algorithmic pass (see
     evaluate_llm_pass.py) -- same ground truth, same metrics, so the two
     passes are directly comparable.

Scope: only rows mapper.py itself flagged 'needs review (no confident
match)' or 'likely derived (auto, low confidence -- needs review)' --
every other row (direct/derived/not-persisted) is left exactly as the
algorithmic pass produced it, untouched.

Judge backend: calls the real Claude API (via the `anthropic` package)
when ANTHROPIC_API_KEY is set in the environment. Every individual
(variable, candidate, attempt) judgment is cached to --cache (a JSON file,
keyed so a later run with more repeats or a fixed row only makes the calls
it's missing) -- both so a long run can be resumed, and so genuine
judgments (from a real API run, or supplied by hand/by an LLM session that
has no API key of its own -- see --cache's format below) can be reused
without ever needing to be re-requested or fabricated.

Usage:
    export ANTHROPIC_API_KEY=...
    python3 mapper_llm.py --auto mapping_auto.csv --out mapping_llm.csv \
        --cache llm_judgments_cache.json --repeats 3

Without an API key, this script cannot make real judgments -- it will say
so and exit rather than fabricate results. A --cache file already
containing real judgments (from a prior run, or supplied directly) is
still usable with no key at all: pass --no-live to force cache-only mode.
"""
import os
import csv
import re
import json
import time
import argparse
from collections import defaultdict, Counter

HERE = os.path.dirname(os.path.abspath(__file__))

DEFAULT_MODEL = 'claude-haiku-4-5-20251001'
REVIEW_TYPES = ('needs review', 'likely derived')

PROMPT_TEMPLATE = """You are verifying one candidate schema mapping for a DMN (Decision Model and Notation) business-rule variable, as part of a research pipeline. You will answer about exactly ONE candidate column. You must never propose a different column -- only judge the one given.

Case study: {case_study}
DMN file: {dmn_file}
Decision: {decision_name}
Variable: {variable_name} (io={io}, FEEL type={feel_type}{label_part}{literal_part})

Candidate schema column: {table}.{column} (abstract type: {abstract_type}{pk_part})

Question: does this DMN variable's value plausibly come FROM this exact schema column (i.e. would a data generator read this column to obtain the variable's value)? Consider the variable's business meaning, not just name similarity.

Answer with exactly one word: yes, no, or unknown. Do not explain, do not suggest an alternative column."""


def load_review_rows(auto_path):
    rows = []
    with open(auto_path, encoding='utf-8') as f:
        for row in csv.DictReader(f):
            if any(t in row['predicted_mapping_type'] for t in REVIEW_TYPES):
                rows.append(row)
    return rows


def load_schema_index(schema_path):
    idx = {}
    with open(schema_path, encoding='utf-8') as f:
        for row in csv.DictReader(f):
            idx[(row['case_study'], row['table'], row['column'])] = row
    return idx


def load_dmn_context(dmn_path):
    idx = {}
    with open(dmn_path, encoding='utf-8') as f:
        for row in csv.DictReader(f):
            key = (row['case_study'], row['dmn_file'], row['decision_name'],
                   row['variable_name'], row['io'])
            idx[key] = row
    return idx


CAND_RE = re.compile(r'\s*([A-Za-z0-9_]+)\.([A-Za-z0-9_]+)\s*\(([\d.]+)\)')


def parse_top3(top3_str):
    return [(m.group(1), m.group(2), float(m.group(3)))
            for m in CAND_RE.finditer(top3_str or '')]


def build_prompt(row, dmn_ctx, candidate_col_info, table, column):
    label = dmn_ctx.get('label', '') if dmn_ctx else ''
    literal_values = dmn_ctx.get('literal_values', '') if dmn_ctx else ''
    label_part = f", label='{label}'" if label else ''
    literal_part = f", declared/observed values: {literal_values}" if literal_values else ''
    pk_part = ', PRIMARY KEY' if candidate_col_info and candidate_col_info.get('is_pk') == 'True' else ''
    abstract_type = candidate_col_info.get('abstract_type', 'unknown') if candidate_col_info else 'unknown'
    return PROMPT_TEMPLATE.format(
        case_study=row['case_study'], dmn_file=row['dmn_file'],
        decision_name=row['decision_name'], variable_name=row['variable_name'],
        io=row['io'], feel_type=row['feel_type'] or 'unspecified',
        label_part=label_part, literal_part=literal_part,
        table=table, column=column, abstract_type=abstract_type, pk_part=pk_part,
    )


def parse_verdict(text):
    t = (text or '').strip().lower()
    m = re.match(r'^(yes|no|unknown)\b', t)
    return m.group(1) if m else 'unknown'


class LiveJudge:
    """Calls the real Claude API. Requires ANTHROPIC_API_KEY."""

    def __init__(self, model):
        import anthropic
        self.client = anthropic.Anthropic()
        self.model = model

    def ask(self, prompt):
        for attempt in range(3):
            try:
                resp = self.client.messages.create(
                    model=self.model, max_tokens=8,
                    messages=[{'role': 'user', 'content': prompt}],
                )
                text = ''.join(
                    b.text for b in resp.content if getattr(b, 'type', '') == 'text')
                return parse_verdict(text)
            except Exception as e:
                if attempt == 2:
                    print(f"  [warn] API call failed after 3 attempts: {e}")
                    return 'unknown'
                time.sleep(2 ** attempt)


def cache_key(row, table, column, attempt):
    return '|'.join([row['case_study'], row['dmn_file'], row['decision_name'],
                      row['variable_name'], row['io'], table, column, str(attempt)])


def load_cache(path):
    if path and os.path.exists(path):
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_cache(path, cache):
    if not path:
        return
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(cache, f, indent=1, sort_keys=True)


def run(auto_path, schema_path, dmn_path, out_path, cache_path, repeats, model, live):
    rows = load_review_rows(auto_path)
    schema_idx = load_schema_index(schema_path)
    dmn_idx = load_dmn_context(dmn_path)
    cache = load_cache(cache_path)

    judge = None
    if live:
        if not os.environ.get('ANTHROPIC_API_KEY'):
            raise SystemExit(
                "No ANTHROPIC_API_KEY in the environment -- refusing to fabricate "
                "judgments. Set the key to run live, or pass --no-live to use only "
                "what's already recorded in --cache.")
        judge = LiveJudge(model)

    out_rows = []
    n_calls_made = 0
    n_calls_cached = 0

    for row in rows:
        dmn_key = (row['case_study'], row['dmn_file'], row['decision_name'],
                   row['variable_name'], row['io'])
        dmn_ctx = dmn_idx.get(dmn_key, {})
        candidates = parse_top3(row['top3_candidates'])

        per_candidate = []  # (table, column, orig_score, verdict, votes_str)
        for table, column, orig_score in candidates:
            col_info = schema_idx.get((row['case_study'], table, column))
            prompt = build_prompt(row, dmn_ctx, col_info, table, column)
            votes = []
            for attempt in range(repeats):
                key = cache_key(row, table, column, attempt)
                if key in cache:
                    votes.append(cache[key])
                    n_calls_cached += 1
                elif judge is not None:
                    v = judge.ask(prompt)
                    cache[key] = v
                    votes.append(v)
                    n_calls_made += 1
                else:
                    votes.append('unknown')  # no cached judgment, no live judge
            counts = Counter(votes)
            verdict = counts.most_common(1)[0][0] if votes else 'unknown'
            per_candidate.append((table, column, orig_score, verdict, dict(counts)))

        # Resolution: among candidates the LLM majority-voted 'yes', keep the
        # one mapper.py itself scored highest (never let the LLM pass override
        # the algorithmic ranking among its own yes-votes -- it only confirms
        # or rejects, per §5.4 point 4).
        yes_candidates = [c for c in per_candidate if c[3] == 'yes']
        if yes_candidates:
            best = max(yes_candidates, key=lambda c: c[2])
            llm_table, llm_column = best[0], best[1]
            llm_verdict = 'confirmed'
        elif any(c[3] == 'unknown' for c in per_candidate):
            llm_table, llm_column = '', ''
            llm_verdict = 'unknown (model could not judge confidently)'
        else:
            llm_table, llm_column = '', ''
            llm_verdict = 'no confident match (LLM rejected all candidates)'

        votes_str = '; '.join(
            f'{t}.{c} ({v}, {orig:.2f}, votes={counts})'
            for t, c, orig, v, counts in per_candidate)

        out_rows.append({
            'case_study': row['case_study'], 'dmn_file': row['dmn_file'],
            'decision_name': row['decision_name'], 'io': row['io'],
            'variable_name': row['variable_name'], 'feel_type': row['feel_type'],
            'mapper_predicted_type': row['predicted_mapping_type'],
            'mapper_confidence': row['confidence'],
            'llm_verdict': llm_verdict,
            'llm_predicted_table': llm_table, 'llm_predicted_column': llm_column,
            'candidate_votes': votes_str,
        })

        # Save incrementally so a long live run can be interrupted/resumed
        # without losing work already paid for.
        save_cache(cache_path, cache)

    with open(out_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=[
            'case_study', 'dmn_file', 'decision_name', 'io', 'variable_name',
            'feel_type', 'mapper_predicted_type', 'mapper_confidence',
            'llm_verdict', 'llm_predicted_table', 'llm_predicted_column',
            'candidate_votes'])
        w.writeheader()
        w.writerows(out_rows)

    print(f"Rows processed: {len(out_rows)} (of {len(rows)} needing review)")
    print(f"Judgment calls made live: {n_calls_made}; served from cache: {n_calls_cached}")
    c = Counter(r['llm_verdict'] for r in out_rows)
    for k, v in c.most_common():
        print(f"  {k}: {v}")
    print(f"Written to {out_path}")


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--auto', default='mapping_auto.csv')
    ap.add_argument('--schema', default='schema_columns.csv')
    ap.add_argument('--dmn', default='dmn_variables.csv')
    ap.add_argument('--out', default='mapping_llm.csv')
    ap.add_argument('--cache', default='llm_judgments_cache.json',
                     help='JSON cache of individual (variable, candidate, attempt) '
                          'judgments -- resumable, and reusable without a live key.')
    ap.add_argument('--repeats', type=int, default=3,
                     help='Judgments per candidate, majority-voted (design doc §5.4 point 3).')
    ap.add_argument('--model', default=DEFAULT_MODEL)
    ap.add_argument('--no-live', dest='live', action='store_false',
                     help='Never call the API -- use only what is already in --cache '
                          '(missing judgments count as unknown, never fabricated).')
    args = ap.parse_args()
    run(args.auto, args.schema, args.dmn, args.out, args.cache,
        args.repeats, args.model, args.live)
