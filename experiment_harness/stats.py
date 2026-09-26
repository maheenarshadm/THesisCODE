"""experiment_harness/stats.py -- statistical tests over harness.py's
summary.csv / per_rule.csv (standard library only).

Usage:  python experiment_harness/stats.py --name X [--metric verified]

Writes experiment_harness/out/<name>/stats/:
  descriptive.csv       n, mean, sd, median, IQR, min, max per
                        (case study, setup, budget, output variant, metric)
  search_vs_random.csv  every DynaMOSA group (1x/5x/10x x archive/final/union)
                        vs every random group (random_walk / random_sample,
                        1x/5x/10x, archive): Mann-Whitney U (two-sided,
                        normal approximation with tie correction and
                        continuity correction), Vargha-Delaney A12, Holm-
                        adjusted p within (case study, metric).
                        A12 > 0.5 means DynaMOSA tends to score HIGHER.
                        `same_budget` marks the equal-budget comparisons.
  search_variants.csv   DynaMOSA only, same run measured three ways: union
                        vs archive, union vs final, archive vs final --
                        Wilcoxon signed-rank (paired by rep; zero
                        differences dropped; normal approximation with tie
                        correction), Holm within (case study, metric).
  budget_effect.csv     each setup's 1x vs 5x vs 10x (Mann-Whitney U, A12).
  per_rule.csv          per rule: in how many reps each group verified it,
                        and Fisher's exact test (two-sided) DynaMOSA 1x
                        union vs each random group, Holm across rules
                        within each comparison.

Metrics: verified (default headline: in-scope rules the independent
validator confirmed), claimed (fitness 0 in the search), and
auc_claimed_first_1x (how fast claimed coverage grows over the first B
evaluations -- archive curve, the same horizon for every budget).

A12 magnitude thresholds (Vargha & Delaney 2000): |A12-0.5| < 0.06
negligible, < 0.14 small, < 0.21 medium, else large.
"""
import argparse
import csv
import math
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_ROOT = os.path.join(HERE, 'out')
METRICS = ('verified', 'claimed', 'auc_claimed_first_1x')


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------

def _phi_sf2(z):
    """Two-sided p-value for a standard-normal z."""
    return math.erfc(abs(z) / math.sqrt(2))


def _ranks(values):
    """Average ranks (1-based), and the tie-group sizes."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    ties = []
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + j) / 2 + 1
        for t in range(i, j + 1):
            ranks[order[t]] = avg
        ties.append(j - i + 1)
        i = j + 1
    return ranks, ties


def mann_whitney_u(x, y):
    """(U for x, two-sided p). Normal approximation, tie- and continuity-
    corrected (what R's wilcox.test uses whenever ties are present, which
    is always the case for integer coverage counts)."""
    n1, n2 = len(x), len(y)
    if n1 == 0 or n2 == 0:
        return float('nan'), float('nan')
    ranks, ties = _ranks(list(x) + list(y))
    r1 = sum(ranks[:n1])
    u1 = r1 - n1 * (n1 + 1) / 2
    n = n1 + n2
    mean = n1 * n2 / 2
    var = n1 * n2 / 12 * ((n + 1) - sum(t ** 3 - t for t in ties) / (n * (n - 1)))
    if var <= 0:
        return u1, 1.0
    z = (abs(u1 - mean) - 0.5) / math.sqrt(var)
    return u1, min(1.0, _phi_sf2(max(z, 0.0)))


def a12(x, y):
    """Vargha-Delaney A12: P(X > Y) + 0.5 P(X = Y)."""
    if not x or not y:
        return float('nan')
    gt = sum(1 for a in x for b in y if a > b)
    eq = sum(1 for a in x for b in y if a == b)
    return (gt + 0.5 * eq) / (len(x) * len(y))


def a12_magnitude(v):
    if v != v:
        return ''
    d = abs(v - 0.5)
    return 'negligible' if d < 0.06 else 'small' if d < 0.14 else 'medium' if d < 0.21 else 'large'


def wilcoxon_signed_rank(x, y):
    """(W+, n_nonzero, two-sided p) for paired samples."""
    d = [a - b for a, b in zip(x, y) if a != b]
    n = len(d)
    if n == 0:
        return 0.0, 0, 1.0
    ranks, ties = _ranks([abs(v) for v in d])
    w_plus = sum(r for r, v in zip(ranks, d) if v > 0)
    mean = n * (n + 1) / 4
    var = n * (n + 1) * (2 * n + 1) / 24 - sum(t ** 3 - t for t in ties) / 48
    if var <= 0:
        return w_plus, n, 1.0
    z = (abs(w_plus - mean) - 0.5) / math.sqrt(var)
    return w_plus, n, min(1.0, _phi_sf2(max(z, 0.0)))


def fisher_exact(a, b, c, d):
    """Two-sided Fisher exact test for [[a, b], [c, d]]."""
    r1, r2, c1 = a + b, c + d, a + c
    n = r1 + r2

    def logp(x):
        return (math.lgamma(r1 + 1) - math.lgamma(x + 1) - math.lgamma(r1 - x + 1)
                + math.lgamma(r2 + 1) - math.lgamma(c1 - x + 1) - math.lgamma(r2 - c1 + x + 1)
                - math.lgamma(n + 1) + math.lgamma(c1 + 1) + math.lgamma(n - c1 + 1))
    lo, hi = max(0, c1 - r2), min(r1, c1)
    p_obs = logp(a)
    total = sum(math.exp(logp(x)) for x in range(lo, hi + 1) if logp(x) <= p_obs + 1e-7)
    return min(1.0, total)


def holm(pvalues):
    m = len(pvalues)
    order = sorted(range(m), key=lambda i: pvalues[i])
    adj = [0.0] * m
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * pvalues[i]))
        adj[i] = running
    return adj


# ---------------------------------------------------------------------------
# data
# ---------------------------------------------------------------------------

def _read(path):
    with open(path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def _write(path, rows):
    if not rows:
        return
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def _fmt(v, nd=6):
    return '' if v != v else round(v, nd)


def _group_label(setup, k, variant):
    return f"{setup}@{k}x/{variant}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--name', required=True)
    ap.add_argument('--alpha', type=float, default=0.05)
    a = ap.parse_args()
    exp = os.path.join(OUT_ROOT, a.name)
    summary_path = os.path.join(exp, 'summary.csv')
    if not os.path.exists(summary_path):
        sys.exit(f"No {summary_path} -- run: harness.py summarize --name {a.name}")
    out = os.path.join(exp, 'stats')
    os.makedirs(out, exist_ok=True)
    rows = _read(summary_path)

    # values[(cs, setup, k, variant, metric)] = {rep: value}
    values = {}
    for r in rows:
        for m in METRICS:
            values.setdefault((r['case_study'], r['setup'], int(r['budget_multiplier']), r['variant'], m),
                              {})[int(r['rep'])] = float(r[m])
    case_studies = sorted({k[0] for k in values})

    # descriptive
    desc = []
    for (cs, setup, k, v, m), reps in sorted(values.items()):
        xs = sorted(reps.values())
        q = statistics.quantiles(xs, n=4) if len(xs) >= 2 else [xs[0]] * 3
        desc.append({'case_study': cs, 'setup': setup, 'budget': f'{k}x', 'variant': v, 'metric': m,
                     'n': len(xs), 'mean': _fmt(statistics.mean(xs)),
                     'sd': _fmt(statistics.stdev(xs)) if len(xs) > 1 else '',
                     'median': _fmt(statistics.median(xs)), 'q1': _fmt(q[0]), 'q3': _fmt(q[2]),
                     'min': _fmt(xs[0]), 'max': _fmt(xs[-1])})
    _write(os.path.join(out, 'descriptive.csv'), desc)

    def mwu_rows(pairs, extra):
        res = []
        for (ga, gb) in pairs:
            x, y = list(values[ga].values()), list(values[gb].values())
            u, p = mann_whitney_u(x, y)
            e = a12(x, y)
            res.append(dict(extra(ga, gb), n_a=len(x), n_b=len(y),
                            mean_a=_fmt(statistics.mean(x)), mean_b=_fmt(statistics.mean(y)),
                            median_a=_fmt(statistics.median(x)), median_b=_fmt(statistics.median(y)),
                            U=_fmt(u, 2), p=p, A12=_fmt(e, 4), effect=a12_magnitude(e)))
        adj = holm([r['p'] for r in res])
        for r, pa in zip(res, adj):
            r['p'] = _fmt(r['p'], 8)
            r['p_holm'] = _fmt(pa, 8)
            r['significant_holm'] = pa < a.alpha
        return res

    # search vs random
    svr = []
    for cs in case_studies:
        for m in METRICS:
            search = sorted(g for g in values if g[0] == cs and g[1] == 'dynamosa' and g[4] == m)
            rand = sorted(g for g in values if g[0] == cs and g[1] != 'dynamosa' and g[3] == 'archive'
                          and g[4] == m)
            pairs = [(s, r) for s in search for r in rand]
            svr += mwu_rows(pairs, lambda ga, gb: {
                'case_study': ga[0], 'metric': ga[4], 'group_a': _group_label(*ga[1:4]),
                'group_b': _group_label(*gb[1:4]), 'same_budget': ga[2] == gb[2]})
    _write(os.path.join(out, 'search_vs_random.csv'), svr)

    # budget effect within each setup
    be = []
    for cs in case_studies:
        for m in METRICS:
            pairs = []
            for setup in ('dynamosa', 'random_walk', 'random_sample'):
                for v in ('archive', 'final', 'union'):
                    gs = sorted(g for g in values if g[0] == cs and g[1] == setup and g[3] == v and g[4] == m)
                    pairs += [(gs[i], gs[j]) for i in range(len(gs)) for j in range(i + 1, len(gs))]
            be += mwu_rows(pairs, lambda ga, gb: {
                'case_study': ga[0], 'metric': ga[4], 'group_a': _group_label(*ga[1:4]),
                'group_b': _group_label(*gb[1:4])})
    _write(os.path.join(out, 'budget_effect.csv'), be)

    # search variants (paired)
    sv = []
    for cs in case_studies:
        for m in METRICS:
            block = []
            for k in sorted({g[2] for g in values if g[0] == cs and g[1] == 'dynamosa'}):
                for va, vb in (('union', 'archive'), ('union', 'final'), ('archive', 'final')):
                    ga, gb = (cs, 'dynamosa', k, va, m), (cs, 'dynamosa', k, vb, m)
                    if ga not in values or gb not in values:
                        continue
                    reps = sorted(set(values[ga]) & set(values[gb]))
                    x = [values[ga][r] for r in reps]
                    y = [values[gb][r] for r in reps]
                    w, n_nz, p = wilcoxon_signed_rank(x, y)
                    block.append({'case_study': cs, 'metric': m, 'budget': f'{k}x', 'variant_a': va,
                                  'variant_b': vb, 'n_pairs': len(reps), 'n_nonzero_diffs': n_nz,
                                  'mean_a': _fmt(statistics.mean(x)), 'mean_b': _fmt(statistics.mean(y)),
                                  'W_plus': _fmt(w, 2), 'p': p})
            for r, pa in zip(block, holm([r['p'] for r in block])):
                r['p'] = _fmt(r['p'], 8)
                r['p_holm'] = _fmt(pa, 8)
                r['significant_holm'] = pa < a.alpha
            sv += block
    _write(os.path.join(out, 'search_variants.csv'), sv)

    # per rule
    per_rule = _per_rule(exp, a.alpha)
    _write(os.path.join(out, 'per_rule.csv'), per_rule)

    print(f"Wrote {out}/: descriptive.csv, search_vs_random.csv, search_variants.csv, budget_effect.csv, "
          f"per_rule.csv")
    print(f"\nEqual-budget comparisons on verified coverage (DynaMOSA union vs random archive):")
    print(f"{'Case study':<10} {'DynaMOSA':<24} {'Random':<28} {'mean A':>7} {'mean B':>7} {'A12':>6} "
          f"{'effect':<10} {'p_holm':>9}")
    for r in svr:
        if r['metric'] == 'verified' and r['same_budget'] and r['group_a'].endswith('/union'):
            print(f"{r['case_study']:<10} {r['group_a']:<24} {r['group_b']:<28} {r['mean_a']:>7} "
                  f"{r['mean_b']:>7} {r['A12']:>6} {r['effect']:<10} {r['p_holm']:>9}")


def _per_rule(exp, alpha):
    """counts[(cs, setup, k, variant)][rule] = number of reps it was verified in."""
    import json
    counts, nreps, in_scope = {}, {}, {}
    for cs in sorted(os.listdir(exp)):
        cs_dir = os.path.join(exp, cs)
        if not os.path.isdir(cs_dir) or cs == 'stats':
            continue
        for setup in sorted(os.listdir(cs_dir)):
            for bdir in sorted(os.listdir(os.path.join(cs_dir, setup))):
                k = int(bdir[1:-1])
                for rdir in sorted(os.listdir(os.path.join(cs_dir, setup, bdir))):
                    path = os.path.join(cs_dir, setup, bdir, rdir, 'per_rule.csv')
                    if not os.path.exists(path):
                        continue
                    for v in ('archive', 'final', 'union'):
                        key = (cs, setup, k, v)
                        rows = _read(path)
                        if rows and rows[0][f'verified_{v}'] == '':
                            continue
                        nreps[key] = nreps.get(key, 0) + 1
                        c = counts.setdefault(key, {})
                        for r in rows:
                            in_scope[(cs, r['rule_id'])] = r['in_scope'] == 'True'
                            c[r['rule_id']] = c.get(r['rule_id'], 0) + (r[f'verified_{v}'] == 'True')
    del json
    out = []
    for cs in sorted({k[0] for k in counts}):
        ref = (cs, 'dynamosa', 1, 'union')
        others = sorted(k for k in counts if k[0] == cs and k[1] != 'dynamosa' and k[3] == 'archive')
        rules = sorted({r for k in counts if k[0] == cs for r in counts[k]})
        ps = {o: [] for o in others}
        rows = []
        for rule in rules:
            row = {'case_study': cs, 'rule_id': rule, 'in_scope': in_scope.get((cs, rule), '')}
            for key in sorted(k for k in counts if k[0] == cs):
                row[f'{_group_label(*key[1:])}_verified_in'] = f"{counts[key].get(rule, 0)}/{nreps[key]}"
            if ref in counts:
                a_hit, a_n = counts[ref].get(rule, 0), nreps[ref]
                for o in others:
                    b_hit, b_n = counts[o].get(rule, 0), nreps[o]
                    p = fisher_exact(a_hit, a_n - a_hit, b_hit, b_n - b_hit)
                    row[f'fisher_p_vs_{_group_label(*o[1:])}'] = p
                    ps[o].append(p)
            rows.append(row)
        for o in others:
            if ref not in counts:
                break
            for row, pa in zip(rows, holm(ps[o])):
                label = _group_label(*o[1:])
                row[f'fisher_p_vs_{label}'] = _fmt(row[f'fisher_p_vs_{label}'], 8)
                row[f'fisher_p_holm_vs_{label}'] = _fmt(pa, 8)
        out += rows
    # union of all keys so DictWriter gets one consistent header
    keys = []
    for r in out:
        for k in r:
            if k not in keys:
                keys.append(k)
    return [{k: r.get(k, '') for k in keys} for r in out]


if __name__ == '__main__':
    main()
