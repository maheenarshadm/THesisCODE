#!/usr/bin/env python3
"""
Merges the plain algorithmic mapper's output (mapping_auto.csv) with the
LLM-assisted second pass's output (mapping_llm.csv) into one final
mapping (mapping_final.csv), in the same row shape mapping_auto.csv uses
-- so validate_mapper.py scores it unchanged, directly comparable to the
algorithmic-only baseline it already reports.

Merge rule: a row mapper.py was already confident about (direct/derived/
not-persisted) is kept exactly as mapper.py predicted it -- the LLM pass
never touches those. A row mapper.py flagged needs-review/likely-derived
is overridden by mapper_llm.py's verdict: 'confirmed' replaces the
predicted table/column with the LLM-confirmed one; 'no confident match'
relabels it as an LLM-confirmed likely gap; 'unknown' is left exactly as
mapper.py had it (the LLM pass added no information for that row).

This is the number that actually matters for the paper's "how much of the
manual mapping does automation replace" question -- not the algorithmic
pass alone, not the LLM pass alone (which is only ever scored on the
subset it touched), but the combined two-stage pipeline end to end.

Known metric artifact, documented rather than hidden: validate_mapper.py's
derived-fact-recall metric checks whether the *predicted label* contains
the literal word "derived". mapper.py's own low-confidence labels always
did ("likely derived, needs review"), even with no idea which column;
once the LLM pass confirms a real column or explicitly rejects all
candidates, the merged label no longer says "derived" even though the row
is now *more* resolved, not less -- so this metric goes down after the
merge for a reason that isn't a real quality regression. Reported anyway
in evaluate's output, not suppressed.

Usage:
    python3 combine_and_evaluate.py --auto mapping_auto.csv --llm mapping_llm.csv \
        --out mapping_final.csv
    python3 validate_mapper.py --auto mapping_final.csv
"""
import csv
import argparse


def combine(auto_path, llm_path, out_path):
    auto_rows = list(csv.DictReader(open(auto_path, encoding='utf-8')))
    llm_by_key = {}
    with open(llm_path, encoding='utf-8') as f:
        for row in csv.DictReader(f):
            key = (row['case_study'], row['dmn_file'], row['decision_name'],
                   row['variable_name'], row['io'])
            llm_by_key[key] = row

    out_rows = []
    n_confirmed = n_rejected = n_unknown = n_untouched = 0
    for row in auto_rows:
        key = (row['case_study'], row['dmn_file'], row['decision_name'],
               row['variable_name'], row['io'])
        llm = llm_by_key.get(key)
        new = dict(row)
        if llm is None:
            n_untouched += 1
        elif llm['llm_verdict'] == 'confirmed':
            new['predicted_table'] = llm['llm_predicted_table']
            new['predicted_column'] = llm['llm_predicted_column']
            new['predicted_mapping_type'] = 'direct (LLM-confirmed)'
            new['top3_candidates'] = f"{llm['llm_predicted_table']}.{llm['llm_predicted_column']} (LLM-confirmed)"
            n_confirmed += 1
        elif 'no confident match' in llm['llm_verdict']:
            new['predicted_mapping_type'] = 'needs review (LLM rejected all candidates -- likely schema gap)'
            n_rejected += 1
        else:
            n_unknown += 1  # leave row exactly as mapper.py had it
        out_rows.append(new)

    with open(out_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
        w.writeheader()
        w.writerows(out_rows)

    print(f"Wrote {len(out_rows)} rows to {out_path}")
    print(f"  Untouched (mapper.py already confident): {n_untouched}")
    print(f"  LLM-confirmed a column: {n_confirmed}")
    print(f"  LLM-rejected all candidates: {n_rejected}")
    print(f"  LLM-unknown (left as mapper.py had it): {n_unknown}")


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--auto', default='mapping_auto.csv')
    ap.add_argument('--llm', default='mapping_llm.csv')
    ap.add_argument('--out', default='mapping_final.csv')
    args = ap.parse_args()
    combine(args.auto, args.llm, args.out)
