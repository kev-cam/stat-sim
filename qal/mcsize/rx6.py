#!/usr/bin/env python3
"""qal/mcsize/rx6.py -- score DUT_B's OWN in-deck boundary receiver under mismatch.

resv instantiates a skewed 0.15um-p / 1.48um-n receiver (XRP1_*a / XRN1_*a) on a HARD
1.2 V supply, reading bank 6, followed by a restoring buffer (XRP1_*b / XRN1_*b).  This
is the real QAL->synchronous boundary, and it is the only place in either DUT where the
worst-matched device in the whole study (0.15 um pMOS, sigma 15.754 mV) sits directly in
a decision path.

The threshold here is NOT rail/2: the receiver is hard-supplied, so its own mid-supply is
0.6 V.  Intended values: the a-stage INVERTS bank 6, the b-stage inverts again.
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
    L = open(p).read().splitlines()
    hdr = L[0].split()
    names = [h.split(':')[0].upper() for h in hdr[1:]]
    rows = [[float(x) for x in ln.split()[1:]]
            for ln in L[1:] if len(ln.split()) == len(hdr) and ln.split()[0].isdigit()]
    return names, np.array(rows)

def cp(k, n, alpha=0.05):
    import math as _m
    if n == 0: return 0.0, 1.0
    def bcdf(p, kk, nn):
        if p <= 0.0: return 1.0
        if p >= 1.0: return 0.0 if kk < nn else 1.0
        return sum(_m.comb(nn, i)*p**i*(1-p)**(nn-i) for i in range(kk+1))
    def bis(f, a, b):
        fa = f(a)
        for _ in range(300):
            m = .5*(a+b); fm = f(m)
            if (fm > 0) == (fa > 0): a, fa = m, fm
            else: b = m
        return .5*(a+b)
    lo = 0.0 if k == 0 else bis(lambda p: bcdf(p, k-1, n)-(1-alpha/2), 0., 1.)
    hi = 1.0 if k == n else bis(lambda p: bcdf(p, k, n)-alpha/2, 0., 1.)
    return lo, hi

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--decks', nargs='+', required=True)
    ap.add_argument('--vdd', type=float, default=1.2)
    ap.add_argument('--abstrip', type=float, default=0.4595)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()

    S, names, draws = [], None, []
    for d in a.decks:
        for _i, path in sorted(sample_files(d)):
            S.append(read_ms(path))
        if os.path.exists(d + '.res'):
            nm, dd = read_res(d + '.res')
            if names is None: names = nm
            draws.append(dd)
    D = np.vstack(draws) if draws else None
    N = len(S)
    if D is not None and len(D) > N: D = D[:N]
    mid = a.vdd/2.0
    # bank 6 intended: o6_i HIGH for even i (in1 = 1,0,1,0,...; six inversions -> = in1)
    want6 = [1 if i % 2 == 0 else 0 for i in range(8)]
    rep = dict(N=N, vdd=a.vdd, mid_supply_V=mid, abs_trip_V=a.abstrip, decks=a.decks)

    for inst in ('bound', 'open'):
        tg = f'M_RX6{inst.upper()}_'
        rail6 = np.array([s.get(tg + 'RAIL6', np.nan) for s in S])
        blk = {}
        f_a = np.zeros(N, dtype=bool)     # receiver (a-stage) misreads
        f_s = np.zeros(N, dtype=bool)     # bank-6 signal vs the ABS trip
        f_r = np.zeros(N, dtype=bool)     # rail-referenced (rail6/2) verdict
        for i in range(8):
            v6 = np.array([s.get(tg + f'O6_{i}', np.nan) for s in S])
            vm = np.array([s.get(tg + f'RM1_{i}', np.nan) for s in S])
            vb = np.array([s.get(tg + f'RB1_{i}', np.nan) for s in S])
            w = want6[i]
            ok_a = (vm < mid) if w == 1 else (vm > mid)       # a-stage inverts
            ok_b = (vb > mid) if w == 1 else (vb < mid)       # b-stage restores
            ok_s = (v6 > a.abstrip) if w == 1 else (v6 < a.abstrip)
            ok_r = (v6 > rail6/2) if w == 1 else (v6 < rail6/2)
            f_a |= ~ok_a; f_s |= ~ok_s; f_r |= ~ok_r
            blk[f'lane{i}'] = dict(
                intended_o6=w,
                o6_V_mean=float(np.nanmean(v6)), o6_V_sd=float(np.nanstd(v6, ddof=1)),
                rm1_V_mean=float(np.nanmean(vm)), rb1_V_mean=float(np.nanmean(vb)),
                rx_a_stage_fails=int((~ok_a).sum()), rx_b_stage_fails=int((~ok_b).sum()),
                abs_trip_fails=int((~ok_s).sum()), rail_ref_fails=int((~ok_r).sum()),
                margin_vs_abs_mV=float(np.nanmean((v6 - a.abstrip)*1000*(1 if w == 1 else -1))),
                margin_vs_rail_mV=float(np.nanmean((v6 - rail6/2)*1000*(1 if w == 1 else -1))))
        for nm2, ff in (('real_in_deck_receiver_a_stage', f_a),
                        ('bank6_vs_ABS_trip', f_s),
                        ('bank6_vs_own_rail_half', f_r)):
            k = N - int(ff.sum()); lo, hi = cp(k, N)
            rep.setdefault(inst, {})[nm2] = dict(failures=int(ff.sum()), N=N,
                                                 yield_point=k/N, yield_CI95=[lo, hi])
        rep[inst]['rail6_V_mean'] = float(np.nanmean(rail6))
        rep[inst]['lanes'] = blk

    # which device dominates the bank-6 signal level? response = mean |margin vs ABS|
    if D is not None:
        tg = 'M_RX6BOUND_'
        marg = np.zeros(N)
        for i in range(8):
            v6 = np.array([s.get(tg + f'O6_{i}', np.nan) for s in S])
            marg += (v6 - a.abstrip)*1000*(1 if want6[i] == 1 else -1)
        marg /= 8.0
        sens = []
        for j, nm in enumerate(names):
            x = D[:, j]*1000.0
            if x.std(ddof=1) < 1e-12: continue
            b = np.polyfit(x, marg, 1)[0]
            sens.append(dict(device=nm, sigma_mV=float(x.std(ddof=1)),
                             dMargin_dVt=float(b), contrib_mV=float(abs(b)*x.std(ddof=1)),
                             corr=float(np.corrcoef(x, marg)[0, 1])))
        sens.sort(key=lambda z: -z['contrib_mV'])
        cls = {}
        for s in sens:
            nm = s['device']
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
        for c in cls.values():
            c['rms_contrib_mV'] = math.sqrt(c['var']); c['variance_share'] = c['var']/tot; del c['var']
        rep['bank6_level_sensitivity'] = dict(
            response='mean over 8 lanes of the signed margin of o6 against the 0.4595 V absolute trip (mV)',
            mean_margin_mV=float(marg.mean()), sd_margin_mV=float(marg.std(ddof=1)),
            top=sens[:15], by_class=dict(sorted(cls.items(), key=lambda z: -z[1]['variance_share'])))

    json.dump(rep, open(a.out, 'w'), indent=1)
    print(f'{a.out}: N={N}')
    for inst in ('bound', 'open'):
        for nm2 in ('real_in_deck_receiver_a_stage', 'bank6_vs_ABS_trip', 'bank6_vs_own_rail_half'):
            r = rep[inst][nm2]
            print(f'  {inst:5s} {nm2:32s} {r["failures"]:3d} fail / {r["N"]}  '
                  f'yield={r["yield_point"]*100:6.2f}%  CI95=[{r["yield_CI95"][0]*100:.2f},{r["yield_CI95"][1]*100:.2f}]%')
    if 'bank6_level_sensitivity' in rep:
        print('  bank6 level class share:',
              {k: round(v['variance_share'], 4) for k, v in rep['bank6_level_sensitivity']['by_class'].items()})

main()
