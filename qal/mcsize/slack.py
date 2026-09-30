#!/usr/bin/env python3
"""qal/mcsize/slack.py -- TIMING SLACK under mismatch, from a grid-measured MC run.

The banktank chain's nominal margin at the committed boundary is large (+278 mV) and
NEGATIVE at the hop-open instant (-55 mV).  So the binding resource is not headroom,
it is TIME: the question mismatch actually decides is *how early can the receiver be
allowed to commit*.  This script answers it per sample.

For each sample and each link (k -> k+1) it finds t_valid = the earliest grid instant
at which ALL EIGHT of the receiving bank's outputs are on the correct side of their own
mid-rail, and stays so through the committed boundary.  The chain's t_valid is the max
over links, expressed as SLACK = bound - t_valid (ps): how much earlier than the
committed boundary the chain could have been sampled.

Slack is the mismatch-sensitive quantity, the one a sizing change has to buy back, and
it is reported as a DISTRIBUTION with its low tail, not as a mean.
"""
import re, os, json, glob, math, argparse
import numpy as np

def read_ms(p):
    v = {}
    for ln in open(p):
        m = re.match(r'\s*\{?([A-Za-z_0-9]+)\}?\s*=\s*([-\d.eE+]+)\s*$', ln)
        if m:
            try: v[m.group(1).upper()] = float(m.group(2))
            except ValueError: pass
    return v

def sample_files(base):
    """Xyce names per-sample .measure output by ANALYSIS TYPE: .msN for a .dc
    analysis, .mtN for a .tran analysis. The chain DUTs are transient, so they
    produce .mtN -- globbing only .ms* silently found ZERO measure sets while the
    .res draws were all present. Accept both, in sample-index order."""
    import glob as _g
    for ext in ('.mt', '.ms'):
        hits = _g.glob(base + ext + '*')
        hits = [h for h in hits if h[len(base)+len(ext):].isdigit()]
        if hits:
            return [(int(h[len(base)+len(ext):]), h) for h in hits]
    return []

def read_res(p):
    lines = open(p).read().splitlines()
    hdr = lines[0].split()
    names = [h.split(':')[0].upper() for h in hdr[1:]]
    rows = [[float(x) for x in ln.split()[1:]]
            for ln in lines[1:] if len(ln.split()) == len(hdr) and ln.split()[0].isdigit()]
    return names, np.array(rows)

def cp(k, n, alpha=0.05):
    """exact (Clopper-Pearson) CI on a binomial proportion. No scipy dependency.
    Both bounds are solved with a direction-detecting bisection: the earlier
    single-convention version silently returned 0.0 for the UPPER bound whenever
    k < n, because binom_cdf is decreasing in p and the solver assumed increasing."""
    import math as _m
    if n == 0: return 0.0, 1.0
    def binom_cdf(p, kk, nn):
        if p <= 0.0: return 1.0
        if p >= 1.0: return 0.0 if kk < nn else 1.0
        return sum(_m.comb(nn, i) * p**i * (1-p)**(nn-i) for i in range(kk+1))
    def bisect(f, a, b):
        fa = f(a)
        for _ in range(300):
            m = 0.5*(a+b)
            fm = f(m)
            if (fm > 0) == (fa > 0): a, fa = m, fm
            else: b = m
        return 0.5*(a+b)
    lo = 0.0 if k == 0 else bisect(lambda p: binom_cdf(p, k-1, n) - (1-alpha/2), 0.0, 1.0)
    hi = 1.0 if k == n else bisect(lambda p: binom_cdf(p, k, n) - alpha/2, 0.0, 1.0)
    return lo, hi

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tag', required=True)
    ap.add_argument('--decks', nargs='+', required=True)
    ap.add_argument('--gridspec', required=True)
    ap.add_argument('--links', required=True)
    ap.add_argument('--pattern', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()

    grid = json.load(open(a.gridspec))
    links = json.loads(a.links)
    pat = {int(k): v for k, v in json.loads(a.pattern).items()}

    S, names, draws = [], None, []
    for deck in a.decks:
        for _i, path in sorted(sample_files(deck)):
            S.append(read_ms(path))
        if os.path.exists(deck + '.res'):
            nm, dd = read_res(deck + '.res')
            if names is None: names = nm
            draws.append(dd)
    D = np.vstack(draws) if draws else None
    N = len(S)
    if D is not None and len(D) > N: D = D[:N]

    NG = max(int(m.group(1)) for k in grid for m in [re.search(r'G(\d+)$', k)] if m) + 1
    rep = dict(tag=a.tag, N=N, n_grid=NG, decks=a.decks)

    tv_link, slack_link = {}, {}
    for (k, r) in links:
        ts = [grid[f'L{k}{r}G{g}']['t_ps'] for g in range(NG)]
        bound = ts[-1]
        ok = np.ones((N, NG), dtype=bool)
        for g in range(NG):
            tg = f'M_L{k}{r}G{g}_'
            rail = np.array([s.get(tg + f'RAIL{r}', np.nan) for s in S])
            for i in range(8):
                v = np.array([s.get(tg + f'O{r}_{i}', np.nan) for s in S])
                th = rail/2.0
                good = (v > th) if pat[r][i] == 1 else (v < th)
                ok[:, g] &= good
        # earliest instant from which it is correct and STAYS correct to the boundary
        tv = np.full(N, np.nan)
        for j in range(N):
            g = NG - 1
            if not ok[j, g]:
                tv[j] = np.inf                 # wrong even at the boundary -> functional FAIL
                continue
            while g > 0 and ok[j, g-1]:
                g -= 1
            tv[j] = ts[g]
        tv_link[f'{k}->{r}'] = dict(
            bound_ps=bound, grid_ps=ts,
            t_valid_mean=float(np.mean(tv[np.isfinite(tv)])) if np.isfinite(tv).any() else None,
            t_valid_max=float(np.max(tv[np.isfinite(tv)])) if np.isfinite(tv).any() else None,
            n_fail_at_bound=int(np.isinf(tv).sum()),
            slack_ps_mean=float(np.mean(bound - tv[np.isfinite(tv)])) if np.isfinite(tv).any() else None,
            slack_ps_min=float(np.min(bound - tv[np.isfinite(tv)])) if np.isfinite(tv).any() else None,
            censored_at_grid_start=int((tv == ts[0]).sum()))
        slack_link[f'{k}->{r}'] = bound - tv

    # chain slack = min over links of that link's own slack
    allsl = np.vstack([slack_link[f'{k}->{r}'] for (k, r) in links])
    chain_slack = allsl.min(axis=0)
    finite = np.isfinite(chain_slack)
    nfail = int((~finite).sum() + (chain_slack[finite] < 0).sum())
    lo, hi = cp(N - nfail, N)
    q = lambda p: float(np.percentile(chain_slack[finite], p)) if finite.any() else None
    rep['chain_slack_ps'] = dict(
        definition='bound - earliest instant from which every scored gate is correct through the boundary; '
                   'min over links. CENSORED BELOW at the grid start (hop-open instant), so a value equal to '
                   'the full grid span means "valid at or before the open instant" and is a LOWER bound on slack.',
        grid_span_ps={f'{k}->{r}': tv_link[f'{k}->{r}']['grid_ps'][-1] - tv_link[f'{k}->{r}']['grid_ps'][0]
                      for (k, r) in links},
        mean=float(np.mean(chain_slack[finite])) if finite.any() else None,
        sd=float(np.std(chain_slack[finite], ddof=1)) if finite.sum() > 1 else None,
        min=float(np.min(chain_slack[finite])) if finite.any() else None,
        p01=q(1), p05=q(5), p50=q(50), p95=q(95),
        n_fail_at_bound=int((~finite).sum()),
        yield_at_bound=(N - int((~finite).sum()))/N,
        yield_CI95=[lo, hi])
    rep['per_link'] = tv_link

    # sensitivity of chain slack to each device's draw
    if D is not None and finite.any():
        y = chain_slack.copy()
        y[~finite] = np.nan
        m = ~np.isnan(y)
        sens = []
        for j, nm in enumerate(names):
            x = D[m, j]*1000.0
            if x.std(ddof=1) < 1e-12: continue
            b = np.polyfit(x, y[m], 1)[0]
            sens.append(dict(device=nm, sigma_mV=float(x.std(ddof=1)),
                             dSlack_ps_per_mV=float(b),
                             contrib_ps=float(abs(b)*x.std(ddof=1)),
                             corr=float(np.corrcoef(x, y[m])[0, 1])))
        sens.sort(key=lambda z: -z['contrib_ps'])
        cls = {}
        for s in sens:
            nm = s['device']
            key = ('swN_10u' if nm.startswith('XSWN') else 'swP_20u' if nm.startswith('XSWP') else
                   'park_2u' if nm.startswith('XPK') else
                   'cellP_1u12' if re.match(r'XP\d', nm) else
                   'cellN_0u74' if re.match(r'XN\d', nm) else 'other')
            c = cls.setdefault(key, dict(n=0, var=0.0, sigma_mV=s['sigma_mV']))
            c['n'] += 1; c['var'] += (s['dSlack_ps_per_mV']*s['sigma_mV'])**2
        tot = sum(c['var'] for c in cls.values()) or 1.0
        for c in cls.values():
            c['rms_contrib_ps'] = math.sqrt(c['var']); c['variance_share'] = c['var']/tot; del c['var']
        rep['slack_sensitivity'] = dict(top=sens[:15],
                                        by_class=dict(sorted(cls.items(), key=lambda z: -z[1]['variance_share'])))
    json.dump(rep, open(a.out, 'w'), indent=1)
    cs = rep['chain_slack_ps']
    print(f'{a.tag}: N={N}  chain slack mean={cs["mean"]} sd={cs["sd"]} min={cs["min"]} '
          f'p05={cs["p05"]}  fail@bound={cs["n_fail_at_bound"]}')
    if 'slack_sensitivity' in rep:
        print('  class share:', {k: round(v['variance_share'], 4) for k, v in rep['slack_sensitivity']['by_class'].items()})

main()
