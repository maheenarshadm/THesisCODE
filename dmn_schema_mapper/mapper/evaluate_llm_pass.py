#!/usr/bin/env python3
"""
Evaluates mapper_llm.py's output (mapping_llm.csv) against the same
ground truth validate_mapper.py uses -- but scoped to exactly the rows the
LLM pass touched (the ones the plain algorithmic mapper itself flagged
'needs review'/'likely derived'). This is the number that actually matters
for the §5.4/§5.5 question: of the rows mapper.py couldn't confidently
resolve on its own, how many did adding an LLM judgment pass fix?

Reuses validate_mapper.py's GT_CONFIG (ground-truth loading, per-case-study
column shapes) rather than duplicating it.

Three outcomes per row, since the LLM pass has three possible verdicts:
  - 'confirmed' with a specific table.column -> checked against ground
    truth exactly like validate_mapper.py's top-1 metric.
  - 'no confident match' (LLM rejected every candidate) -> correct exactly
    when ground truth is itself not-persisted/schema-gap (i.e. the LLM was
    right that none of the 3 candidates was the real answer).
  - 'unknown' -> never counted as either right or wrong; it's an explicit
    "still needs a human" outcome, the same non-answer §5.4 point 4 treats
    as safe by design, not a failure mode to penalize.

Usage:
    python3 evaluate_llm_pass.py --llm mapping_llm.csv
"""
import csv
import re
import argparse
from collections import Counter
import validate_mapper as vm

# Requires a letter to start each side (not just \s*\S+\.\S+) so the score/
# confidence floats embedded in the same string (e.g. "0.23") never match.
CAND_RE = re.compile(r'\b([A-Za-z][A-Za-z0-9_]*)\.([A-Za-z][A-Za-z0-9_]*)\b')


def load_llm_predictions(path):
    preds = {}
    with open(path, encoding='utf-8') as f:
        for row in csv.DictReader(f):
            key = (row['case_study'], row['dmn_file'], row['decision_name'],
                   row['variable_name'], row['io'])
            # candidate_votes lists exactly the 3 (table, column, ...) candidates
            # this row was judged against -- needed below to tell "rejected all
            # 3, and the true answer wasn't even offered" apart from "rejected
            # all 3 including the actually-correct one".
            row['_offered'] = {(m.group(1).lower(), m.group(2).lower())
                                for m in CAND_RE.finditer(row['candidate_votes'] or '')}
            preds[key] = row
    return preds


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--llm', default='mapping_llm.csv')
    args = ap.parse_args()

    llm_preds = load_llm_predictions(args.llm)

    per_cs = Counter()
    outcomes = Counter()
    examples_confirmed_right = []
    examples_confirmed_wrong = []
    examples_rejected_right = []
    examples_rejected_wrong = []

    for cs, cfg in vm.GT_CONFIG.items():
        gt = vm.load_ground_truth(cs)
        uses_short_key = 'dmn_file' not in cfg['key_cols']

        for gt_key, g in gt.items():
            if uses_short_key:
                decision_name, variable_name = gt_key
                # find the matching llm row by (cs, decision_name, variable_name)
                match = next((k for k in llm_preds
                              if k[0] == cs and k[2] == decision_name and k[3] == variable_name),
                             None)
            else:
                dmn_file, decision_name, variable_name, io = gt_key
                match = (cs, dmn_file, decision_name, variable_name, io)
                match = match if match in llm_preds else None
            if match is None:
                continue  # not a row the LLM pass touched (mapper.py was already confident)

            row = llm_preds[match]
            per_cs[cs] += 1
            gt_np = vm.is_gt_not_persisted(g['mapping_type'], g['schema_field'])

            if row['llm_verdict'] == 'confirmed':
                pred_pair = (row['llm_predicted_table'].lower(), row['llm_predicted_column'].lower())
                if pred_pair in g['true_pairs']:
                    outcomes['confirmed_correct'] += 1
                    examples_confirmed_right.append((cs, variable_name, pred_pair))
                else:
                    outcomes['confirmed_wrong'] += 1
                    examples_confirmed_wrong.append((cs, variable_name, pred_pair, g['true_pairs']))
            elif 'no confident match' in row['llm_verdict']:
                # A rejection is only wrong if the true answer was actually
                # one of the 3 candidates offered and got turned down --
                # not merely because ground truth has *some* true pair
                # somewhere else in the schema that was never a candidate
                # here in the first place (that's a mapper.py candidate-
                # generation miss, not an LLM-judgment failure).
                true_was_offered = bool(g['true_pairs'] & row['_offered'])
                if gt_np or not g['true_pairs'] or not true_was_offered:
                    outcomes['rejected_correctly'] += 1
                    examples_rejected_right.append((cs, variable_name))
                else:
                    outcomes['rejected_incorrectly'] += 1
                    examples_rejected_wrong.append((cs, variable_name, g['true_pairs'], row['_offered']))
            else:  # unknown
                outcomes['unknown'] += 1

    total_scored = outcomes['confirmed_correct'] + outcomes['confirmed_wrong'] + \
        outcomes['rejected_correctly'] + outcomes['rejected_incorrectly']
    total_right = outcomes['confirmed_correct'] + outcomes['rejected_correctly']

    print(f"Rows the LLM pass touched and ground truth could score: {total_scored} "
          f"(+ {outcomes['unknown']} left 'unknown', not scored)")
    print(f"  Confirmed a specific column, and it was right:   {outcomes['confirmed_correct']}")
    print(f"  Confirmed a specific column, but it was wrong:    {outcomes['confirmed_wrong']}")
    print(f"  Rejected all 3 candidates, correctly (real gap):  {outcomes['rejected_correctly']}")
    print(f"  Rejected all 3 candidates, incorrectly (a candidate WAS right): {outcomes['rejected_incorrectly']}")
    print(f"\nOverall accuracy on the rows this pass touched: {total_right}/{total_scored} "
          f"({total_right/total_scored:.1%})" if total_scored else "\nNo scoreable rows.")
    print("\n(For comparison: mapper.py itself scored 0/these-same-rows by definition -- "
          "these are exactly the rows it could not confidently resolve on its own.)")

    if examples_confirmed_wrong:
        print(f"\nConfirmed-but-wrong examples (for manual inspection):")
        for cs, var, pred, true in examples_confirmed_wrong[:10]:
            print(f"  [{cs}] {var}: picked {pred[0]}.{pred[1]}, true pair(s): {true}")
    if examples_rejected_wrong:
        print(f"\nRejected-but-a-candidate-was-right examples:")
        for cs, var, true, offered in examples_rejected_wrong[:10]:
            print(f"  [{cs}] {var}: true pair(s) {true} were among the offered {offered} but all rejected")


if __name__ == '__main__':
    main()
