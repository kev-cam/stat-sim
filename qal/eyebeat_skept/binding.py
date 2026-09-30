#!/usr/bin/env python3
"""Policing detail: at a given T, per bank, the EYE2 3sigma opening/closing of
(a) each single pattern, (b) HIGH-only and LOW-only gate sets, (c) the full
intersection -- to show the intersection over patterns AND polarities is the
binding construction, not a decoration.  Runs on any lane root."""
import json, math, os, sys
import numpy as np
import skx

T = float(sys.argv[1])
root = sys.argv[2] if len(sys.argv) > 2 else os.path.join(skx.HERE, "T%g" % T)
pats = ["P0", "P1", "P2"]
lanes = {p: skx.load_lane(root, p) for p in pats}
n = min(lanes[p]["n"] for p in pats)
g = lanes[pats[0]]["g"][:n]
THR = 3 * skx.SIG
out = {}
for k in (1, 2, 3):
    kr = k + 1
    ck = lanes[pats[0]]["sch"]["c"][k]
    a_lo = int(round(ck / skx.GRID))
    a_hi = min(int(round((g[-1] - 1.0) / skx.GRID)), n - 1)
    curves = {}
    for p in pats:
        L = lanes[p]
        vrb = L["mt0"]["VR%dB%d" % (kr, kr)]
        tf, _ = skx.TRIP.at(vrb)
        per_gate = {}
        for i in range(skx.MG):
            vo = L["C"]["V(O%d_%d)" % (k, i)][:n]
            sg = 1.0 if skx.out_hi(L["bits"], k, i) else -1.0
            per_gate[i] = 1000.0 * sg * (vo - float(tf))
        hi_ = [i for i in range(skx.MG) if skx.out_hi(L["bits"], k, i)]
        lo_ = [i for i in range(skx.MG) if not skx.out_hi(L["bits"], k, i)]
        curves[p] = dict(
            all=np.min(list(per_gate.values()), axis=0),
            HIGH=(np.min([per_gate[i] for i in hi_], axis=0) if hi_ else None),
            LOW=(np.min([per_gate[i] for i in lo_], axis=0) if lo_ else None))
    def opening(curve):
        if curve is None:
            return None
        fr = skx.first_run(curve > THR, a_lo, a_hi)
        if fr is None:
            return None
        ta, tb, cl, chp = skx.edge_interp(curve, g, fr[0], fr[1], THR, a_lo, a_hi)
        return dict(open_c=round(float(ta - ck), 4), close=round(float(tb), 4),
                    clipped=bool(chp))
    rec = {}
    for p in pats:
        rec["%s_all" % p] = opening(curves[p]["all"])
        rec["%s_HIGH" % p] = opening(curves[p]["HIGH"])
        rec["%s_LOW" % p] = opening(curves[p]["LOW"])
    inter = np.min([curves[p]["all"] for p in pats], axis=0)
    rec["INTERSECTION"] = opening(inter)
    hi_all = [curves[p]["HIGH"] for p in pats if curves[p]["HIGH"] is not None]
    lo_all = [curves[p]["LOW"] for p in pats if curves[p]["LOW"] is not None]
    rec["INTER_HIGH_only"] = opening(np.min(hi_all, axis=0))
    rec["INTER_LOW_only"] = opening(np.min(lo_all, axis=0))
    out["bank%d" % k] = rec
print(json.dumps(out, indent=1))
