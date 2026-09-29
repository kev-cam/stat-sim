#!/usr/bin/env python3
"""SKEPT: the COMMITTED differential definition, reimplemented independently:
step_at_logic = max_t |V_topped(t) - V_free(t)| on a feeding-stage output over
the top-up window.  Validated against tankfed's published 248.997 / 31.411."""
import sys, os, json, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sklib
QAL = "/usr/local/src/stat-sim/qal"

def diff_step(cir_top, prn_top, prn_free, gates, tail):
    wt = sklib.W(prn_top); wf = sklib.W(prn_free)
    out = []
    for (k, ta, tb) in sklib.topup_windows(cir_top):
        kf = k - 1
        tb2 = (tb if tb else wt.t[-1]) + tail
        g = np.arange(ta, tb2, 0.05)
        best = (0.0, None, None); per = {}
        for i in gates:
            col = "V(O%d_%d)" % (kf, i)
            if not (wt.has(col) and wf.has(col)):
                continue
            a = np.interp(g, wt.t, wt.s(col))
            b = np.interp(g, wf.t, wf.s(col))
            d = np.abs(a - b)
            j = int(np.argmax(d)); st = float(d[j] * 1e3)
            per["o%d_%d" % (kf, i)] = round(st, 3)
            if st > best[0]:
                best = (st, "o%d_%d" % (kf, i), float(g[j]))
        out.append(dict(topped_bank=k, feeder=kf, win=[ta, tb],
                        step_at_logic_mV=round(best[0], 3), gate=best[1],
                        at_ps=best[2], per_gate=per))
    return out

print("=== VALIDATION: tankfed free-vs-clamp, my implementation ===")
for tag, deck, ref in (("matched_m2", "r_bank_matched_m2", 248.997),
                       ("uniform_m6", "r_bank_uniform_m6", 31.411)):
    ct = os.path.join(QAL, "tankfed", deck + "_clamp_T340_dv1200.cir")
    pt = ct + ".prn"
    pf = os.path.join(QAL, "tankfed", deck + "_free_T340_dv1200.cir.prn")
    if not (os.path.exists(pt) and os.path.exists(pf)):
        print(tag, "missing"); continue
    for tail in (0.0, 24.0, 60.0):
        r = diff_step(ct, pt, pf, range(0, 60), tail)
        print(" %-11s tail=%4.0f ps : %s   (committed %.3f)"
              % (tag, tail, ["b%d %s %.3f mV @%.1f" % (x["topped_bank"], x["gate"],
                  x["step_at_logic_mV"], x["at_ps"] or -1) for x in r], ref))
