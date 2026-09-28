#!/usr/bin/env python3
"""TRACK B extractor: amplitude regulation, the energy ledger and eta_amp."""
import sys, math, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run

BEAT = 580.0

def beats(w, n0, n1):
    """per-beat amplitude of gts and gtsn over beat indices n0..n1"""
    out = []
    for k in range(n0, n1):
        lo, hi = w.env('V(GTS)', k*BEAT, (k+1)*BEAT)
        lo2, hi2 = w.env('V(GTSN)', k*BEAT, (k+1)*BEAT)
        lo3, hi3 = w.env('V(GPS)', k*BEAT, (k+1)*BEAT)
        out.append(((hi-lo)/2.0, (hi+lo)/2.0, (hi2-lo2)/2.0, lo, hi,
                    (hi3-lo3)/2.0, (hi3+lo3)/2.0, lo3, hi3))
    return out

LIND = [0.0, 0.0, 0.0]

def ledger(w, t0, t1):
    g = lambda n: w.E(n, t1, t0)
    d = dict(E_gt=g('V(XEGT)'), E_gtp=g('V(XEGTP)'),
             E_VA=g('V(XEVA)'), E_VB=g('V(XEVB)'), E_VBG=g('V(XEVBG)'),
             E_sup=g('V(XESUP)'), E_RP=g('V(XERP)'), E_RN=g('V(XERN)'),
             E_RBQ=g('V(XERBQ)'), E_M1=g('V(XED1)'), E_M2=g('V(XED2)'),
             E_MT=g('V(XEDT)'), E_core=g('V(XECORE)'),
             Q_gt=g('V(XQGT)'), Q_gtp=g('V(XQGTP)'))
    d['E_tap'] = d['E_gt'] + d['E_gtp']
    d['E_tankR'] = d['E_RP'] + d['E_RN'] + d['E_RBQ']
    d['E_dev'] = d['E_M1'] + d['E_M2'] + d['E_MT']
    # stored energy in the three inductors, exactly
    def eL(cur, L):
        return 0.5*L*(w.at(cur, t1)**2 - w.at(cur, t0)**2)*1e15
    def eL(cur, L):
        try: return 0.5*L*(w.at(cur, t1)**2 - w.at(cur, t0)**2)*1e15
        except Exception: return 0.0
    d['dE_L'] = eL('I(LP)', LIND[0]) + eL('I(LN)', LIND[1]) + eL('I(LBQ)', LIND[2])
    d['E_HI'] = g('V(XEHI)') if w.has('V(XEHI)') else 0.0
    d['E_taps_plus_losses'] = d['E_tap'] + d['E_tankR'] + d['E_dev'] + d['dE_L']
    d['closure_fJ'] = d['E_sup'] + d['E_HI'] - d['E_taps_plus_losses']
    d['eta_tap'] = d['E_tap']/d['E_sup'] if d['E_sup'] else float('nan')
    d['eta_core'] = (d['E_tap']+d['E_tankR'])/d['E_sup'] if d['E_sup'] else float('nan')
    return d

def show(nm, nb0=5, nb1=8, L=(0, 0, 0)):
    w = run.W(nm + ".cir.prn")
    tend = w.t[-1]*1e12
    nb = int(tend//BEAT)
    print("== %s   tend=%.0f ps (%d beats) ==" % (nm, tend, nb))
    bs = beats(w, 0, nb)
    print("  beat  amp(gts) mid(gts) amp(gtsn) | amp(gps) mid(gps)  gps_lo gps_hi | gts_lo gts_hi")
    for i, b in enumerate(bs):
        print("   %2d   %7.4f %7.4f  %7.4f  | %7.4f %7.4f  %7.4f %7.4f | %7.4f %7.4f"
              % (i, b[0], b[1], b[2], b[5], b[6], b[7], b[8], b[3], b[4]))
    # period
    z = w.zeros('V(GTS)', w.at('V(GTS)', tend*0.9), 2*BEAT)
    if len(z) > 2:
        p = [z[i+1]-z[i] for i in range(len(z)-1)]
        print("  period (last beats): %s ps" % ["%.1f" % x for x in p[-4:]])
    t0, t1 = nb0*BEAT, nb1*BEAT
    d = ledger(w, t0, t1)
    n = nb1-nb0
    print("  LEDGER over beats %d..%d  (per beat, fJ/bank):" % (nb0, nb1))
    for k in ('E_gt', 'E_gtp', 'E_tap', 'E_VA', 'E_VB', 'E_VBG', 'E_sup',
              'E_RP', 'E_RN', 'E_RBQ', 'E_tankR', 'E_M1', 'E_M2', 'E_MT',
              'E_dev', 'closure_fJ'):
        print("     %-10s %+10.4f" % (k, d[k]/n))
    print("     Q_gt %+8.4f fC/beat  Q_gtp %+8.4f fC/beat" % (d['Q_gt']/n, d['Q_gtp']/n))
    print("     eta_tap  = E_tap/E_sup      = %6.2f %%" % (100*d['eta_tap']))
    print("     eta_core = (tap+tankR)/Esup = %6.2f %%" % (100*d['eta_core']))
    print("     closure  = %.3f %% of E_sup" % (100*d['closure_fJ']/d['E_sup'] if d['E_sup'] else float('nan')))
    return d, bs

if __name__ == '__main__':
    for nm in sys.argv[1:]:
        try: show(nm)
        except Exception as e: print(nm, "ERR", e)
        print()
