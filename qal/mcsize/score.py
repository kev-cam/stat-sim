#!/usr/bin/env python3
"""qal/mcsize/score.py -- score a mismatch-MC run against the FUNCTIONAL criterion.

CRITERION (adopted from qal/fcrit/PRE_REGISTERED.json, mtime 2026-09-29 14:35:08,
which predates qal/mcsize/PRE_REGISTERED.json at 14:38:29) with ONE declared
adaptation and ONE declared correction:

  ADAPTATION -- the noise budget.  fcrit's NB = 3*sigma_trip + coupling + droop.
  Its 3*sigma_trip = 19.323 mV is a STATIC ALLOWANCE for exactly the random Vt
  mismatch that this study DRAWS EXPLICITLY per sample.  Including it here would
  double-count the random term.  The MC therefore scores at NB = the DETERMINISTIC
  terms only (coupling + droop; both ZERO for a free-running no-top-up chain), which
  is fcrit's own "NB=0, pure threshold crossing" column.  fcrit's full NB is also
  reported, labelled as the double-counting conservative bound.

  CORRECTION -- the commit instant.  fcrit defines t_commit as the receiving bank's
  ZCS/open instant and justifies it with claim (ii): "the receiving cells' pull-up
  path can no longer reach any level it has not already reached".  That claim is
  FALSE on the committed waveform: in resv res20, o6_0 rises 0.15906 -> 0.34466 V
  between the open instant (1821.43 ps) and the committed boundary (2000 ps), because
  the cells keep settling out of the now-floating rail's OWN capacitance, not out of
  the inductor.  Both instants are therefore scored and both reported: `bound`
  (= c_k + T, what every committed extractor samples, and the instant the beat
  schedule actually allows) is PRIMARY; `open` is reported as the harsher variant.

  RECEIVER-OUTPUT FORM (MC-native, MEASURED, no composition).  fcrit's threshold is
  "the input at which the receiver, supplied at its delivered rail, has Vout = Vdd/2".
  For a monotone inverting cell that is exactly equivalent to asking whether the
  receiver's OWN OUTPUT has crossed its own mid-rail.  The receiver is physically in
  the deck with its own DELVTO draw, so scoring on the receiver's output needs no
  per-sample trip composition and no sensitivity coefficients at all.  This is the
  primary form.  The sender-side level is also recorded for the absolute-trip check.
"""
import re, os, sys, json, glob, math
import numpy as np

def clopper_pearson(k, n, alpha=0.05):
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

def read_ms(path):
    v = {}
    for ln in open(path):
        m = re.match(r'\s*([A-Za-z_0-9]+)\s*=\s*([-\d.eE+]+)\s*$', ln)
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

def read_res(path):
    """per-sample DELVTO draws: {devname: array}"""
    lines = open(path).read().splitlines()
    hdr = lines[0].split()
    names = [h.split(':')[0] for h in hdr[1:]]
    rows = []
    for ln in lines[1:]:
        p = ln.split()
        if len(p) == len(hdr) and p[0].isdigit():
            rows.append([float(x) for x in p[1:]])
    a = np.array(rows)
    return names, a

def main():
    ap = __import__('argparse').ArgumentParser()
    ap.add_argument('--tag', required=True)
    ap.add_argument('--decks', nargs='+', required=True, help='MC deck .cir paths (chunks)')
    ap.add_argument('--links', required=True, help='json [[k,r],...] link (sender k -> receiver r)')
    ap.add_argument('--pattern', required=True, help='json {bank: [8 intended bits]}')
    ap.add_argument('--abstrips', default='{"RX_SKEW":0.4595,"RX_STD":0.6452}')
    ap.add_argument('--nbfull', type=float, default=19.323, help='mV, fcrit full NB (double counts)')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()

    links = json.loads(a.links)
    pat = {int(k): v for k, v in json.loads(a.pattern).items()}
    abstrips = json.loads(a.abstrips)

    samples = []          # each: dict of measures
    draws_names, draws = None, []
    for deck in a.decks:
        base = deck
        for _i, path in sorted(sample_files(base)):
            samples.append(read_ms(path))
        if os.path.exists(base + '.res'):
            nm, dd = read_res(base + '.res')
            if draws_names is None: draws_names = nm
            assert nm == draws_names, 'device column mismatch between chunks'
            draws.append(dd)
    D = np.vstack(draws) if draws else None
    N = len(samples)
    assert D is None or len(D) == N, f'{len(D)} draws vs {N} measure sets'

    rep = dict(tag=a.tag, N=N, decks=a.decks, criterion_form='receiver-output vs own mid-rail',
               n_devices=(len(draws_names) if draws_names else 0))

    # ---- per-instant, per-link scoring -------------------------------------
    for inst in ('bound', 'open'):
        per_link = {}
        fail_any = np.zeros(N, dtype=bool)
        fail_detail = []
        for (k, r) in links:
            tagk = f'M_L{k}{r}{inst.upper()}_'
            rail = np.array([s.get(tagk + f'RAIL{r}', np.nan) for s in samples])
            gl = {}
            for i in range(8):
                vr = np.array([s.get(tagk + f'O{r}_{i}', np.nan) for s in samples])
                vs = np.array([s.get(tagk + f'O{k}_{i}', np.nan) for s in samples])
                want_rx = pat[r][i]            # intended value AT THE RECEIVER OUTPUT
                th = rail/2.0
                ok = (vr > th) if want_rx == 1 else (vr < th)
                marg = (vr - th)*1000.0 * (1 if want_rx == 1 else -1)   # mV, +ve = correct side
                gl[f'o{r}_{i}'] = dict(
                    intended_rx=want_rx,
                    margin_mV_mean=float(np.nanmean(marg)), margin_mV_sd=float(np.nanstd(marg, ddof=1)),
                    margin_mV_min=float(np.nanmin(marg)),
                    fails=int((~ok).sum()),
                    sender_level_V_mean=float(np.nanmean(vs)))
                fail_any |= ~ok
                if (~ok).sum():
                    fail_detail.append(dict(link=f'{k}->{r}', gate=f'o{r}_{i}',
                                            intended_rx=want_rx, fails=int((~ok).sum()),
                                            polarity=('HIGH_read_LOW' if want_rx == 1 else 'LOW_read_HIGH')))
            per_link[f'{k}->{r}'] = dict(rail_V_mean=float(np.nanmean(rail)),
                                         rail_V_sd=float(np.nanstd(rail, ddof=1)), gates=gl)
        f = int(fail_any.sum())
        lo, hi = clopper_pearson(N - f, N)
        rep[f'{inst}_primary'] = dict(
            failures=f, N=N, yield_point=(N-f)/N,
            yield_CI95=[lo, hi], failure_upper95=1.0 - lo,
            rule_of_three_upper=(3.0/N if f == 0 else None),
            per_link=per_link, failure_detail=fail_detail)

        # conservative fcrit-full-NB variant (double counts the random term)
        nb = a.nbfull/1000.0
        fa2 = np.zeros(N, dtype=bool)
        for (k, r) in links:
            tagk = f'M_L{k}{r}{inst.upper()}_'
            rail = np.array([s.get(tagk + f'RAIL{r}', np.nan) for s in samples])
            for i in range(8):
                vr = np.array([s.get(tagk + f'O{r}_{i}', np.nan) for s in samples])
                th = rail/2.0
                ok = (vr > th + nb) if pat[r][i] == 1 else (vr < th - nb)
                fa2 |= ~ok
        f2 = int(fa2.sum()); lo2, hi2 = clopper_pearson(N-f2, N)
        rep[f'{inst}_fcritNB'] = dict(NB_mV=a.nbfull, failures=f2, yield_point=(N-f2)/N,
                                      yield_CI95=[lo2, hi2], note='DOUBLE COUNTS the random Vt term')

        # absolute-trip (synchronous boundary receiver) on the DEEPEST bank
        deepest = max(r for _, r in links)
        tagd = f'M_L{deepest-1}{deepest}{inst.upper()}_'
        absres = {}
        for rxname, th in abstrips.items():
            fa3 = np.zeros(N, dtype=bool); per = {}
            for i in range(8):
                vs = np.array([s.get(tagd + f'O{deepest}_{i}', np.nan) for s in samples])
                want = pat[deepest][i]
                ok = (vs > th) if want == 1 else (vs < th)
                per[f'o{deepest}_{i}'] = dict(intended=want, fails=int((~ok).sum()),
                                              level_V_mean=float(np.nanmean(vs)),
                                              level_V_sd=float(np.nanstd(vs, ddof=1)))
                fa3 |= ~ok
            f3 = int(fa3.sum()); lo3, hi3 = clopper_pearson(N-f3, N)
            absres[rxname] = dict(trip_V=th, failures=f3, yield_point=(N-f3)/N,
                                  yield_CI95=[lo3, hi3], per_gate=per)
        rep[f'{inst}_abs_deepest_bank{deepest}'] = absres

    # ---- PER-DEVICE SENSITIVITY -------------------------------------------
    if D is not None and N >= 3:
        inst = 'bound'
        # scalar response = the WORST (minimum) margin over every scored gate, per sample
        worst = np.full(N, np.inf); worstwho = [None]*N
        for (k, r) in links:
            tagk = f'M_L{k}{r}{inst.upper()}_'
            rail = np.array([s.get(tagk + f'RAIL{r}', np.nan) for s in samples])
            for i in range(8):
                vr = np.array([s.get(tagk + f'O{r}_{i}', np.nan) for s in samples])
                m = (vr - rail/2.0)*1000.0 * (1 if pat[r][i] == 1 else -1)
                upd = m < worst
                for j in np.where(upd)[0]: worstwho[j] = f'{k}->{r}:o{r}_{i}'
                worst = np.minimum(worst, m)
        dm = D*1000.0                             # mV
        sens = []
        wc = worst - worst.mean()
        for j, nm in enumerate(draws_names):
            x = dm[:, j]
            if x.std(ddof=1) < 1e-12: continue
            b = np.polyfit(x, worst, 1)[0]        # mV margin per mV Vt shift
            rr = np.corrcoef(x, worst)[0, 1]
            sens.append(dict(device=nm, sigma_mV=float(x.std(ddof=1)),
                             dMargin_dVt=float(b), contrib_mV=float(abs(b)*x.std(ddof=1)),
                             corr=float(rr)))
        sens.sort(key=lambda z: -z['contrib_mV'])
        rep['sensitivity_worst_margin'] = dict(
            response='min over all scored gates of the signed margin (mV) at the bound instant',
            worst_margin_mean_mV=float(worst.mean()), worst_margin_sd_mV=float(worst.std(ddof=1)),
            worst_margin_min_mV=float(worst.min()),
            worst_gate_histogram={g: int(sum(1 for w in worstwho if w == g))
                                  for g in sorted(set(worstwho))},
            ranking=sens)
        # class-level roll-up (variance share by geometry class)
        cls = {}
        for s in sens:
            nm = s['device'].upper()
            key = ('rxSkewP_0u15' if re.match(r'XRP\d+_\d+A$', nm) else
                   'rxSkewN_1u48' if re.match(r'XRN\d+_\d+A$', nm) else
                   'restP_1u12'   if re.match(r'XRP\d+_\d+B$', nm) else
                   'restN_0u74'   if re.match(r'XRN\d+_\d+B$', nm) else
                   'srcSwN_10u'   if nm.startswith('XSWSN') else
                   'srcSwP_20u'   if nm.startswith('XSWSP') else
                   'swN_10u'      if nm.startswith('XSWN') else
                   'swP_20u'      if nm.startswith('XSWP') else
                   'park_2u'      if nm.startswith('XPK') else
                   'cellP_1u12'   if re.match(r'XP\d', nm) else
                   'cellN_0u74'   if re.match(r'XN\d', nm) else 'other')
            c = cls.setdefault(key, dict(n=0, var=0.0, sigma_mV=s['sigma_mV']))
            c['n'] += 1; c['var'] += (s['dMargin_dVt']*s['sigma_mV'])**2
        tot = sum(c['var'] for c in cls.values()) or 1.0
        for k2, c in cls.items():
            c['rms_contrib_mV'] = math.sqrt(c['var']); c['variance_share'] = c['var']/tot
            del c['var']
        rep['sensitivity_by_class'] = dict(sorted(cls.items(), key=lambda z: -z[1]['variance_share']))

        # BOTH TAILS: split failures by the sign of the implicated draw
        f_idx = np.where(np.array([False]*N))[0]
        rep['tails'] = {}
        for inst2 in ('bound',):
            fail_any = np.zeros(N, dtype=bool)
            for (k, r) in links:
                tagk = f'M_L{k}{r}{inst2.upper()}_'
                rail = np.array([s.get(tagk + f'RAIL{r}', np.nan) for s in samples])
                for i in range(8):
                    vr = np.array([s.get(tagk + f'O{r}_{i}', np.nan) for s in samples])
                    th = rail/2.0
                    ok = (vr > th) if pat[r][i] == 1 else (vr < th)
                    fail_any |= ~ok
            top = [s['device'] for s in sens[:5]]
            tl = {}
            for nm in top:
                j = draws_names.index(nm)
                x = dm[:, j]
                tl[nm] = dict(
                    mean_draw_all_mV=float(x.mean()),
                    mean_draw_failing_mV=(float(x[fail_any].mean()) if fail_any.any() else None),
                    n_fail=int(fail_any.sum()),
                    pos_tail_frac_all=float((x > 0).mean()),
                    pos_tail_frac_failing=(float((x[fail_any] > 0).mean()) if fail_any.any() else None))
            rep['tails'][inst2] = tl

    json.dump(rep, open(a.out, 'w'), indent=1)
    print(f'{a.out}: N={N}, devices={rep["n_devices"]}')
    for inst in ('bound', 'open'):
        p = rep[f'{inst}_primary']
        print(f'  {inst:6s} primary: {p["failures"]} fail / {p["N"]}  yield={p["yield_point"]*100:.2f}% '
              f'CI95=[{p["yield_CI95"][0]*100:.2f},{p["yield_CI95"][1]*100:.2f}]%')
    if 'sensitivity_by_class' in rep:
        print('  class variance share:',
              {k: round(v['variance_share'], 4) for k, v in rep['sensitivity_by_class'].items()})

main()
