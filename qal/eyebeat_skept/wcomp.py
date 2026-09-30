#!/usr/bin/env python3
"""SK_B discrimination: draining/rising tracking lag vs cell width at fixed
T=300, pattern P0.  Gate-by-gate ratios on identical gate sets.
Pre-stated (SKEPTIC_PREREG SK_B): lag(w050)/lag(w100) >= 1.5 AND
lag(w200)/lag(w100) <= 0.67 -> RC-tracking attribution stands;
<20% movement across the 4x R_on span -> attribution fails."""
import json, os
import numpy as np
import skx

HERE = os.path.dirname(os.path.abspath(__file__))
T = 300.0


def lane_lags(root):
    L = skx.load_lane(root, "P0")
    n = L["n"]
    g = L["g"][:n]
    res = {}
    for k in (1, 2, 3):
        rail = L["C"]["V(RAIL%d)" % k][:n]
        vpk = L["mt0"]["VR%dPK" % k]
        rop, rkp, ckp = L["sch"]["ro"][k], L["sch"]["r"][k], L["sch"]["c"][k]
        lvl = 0.5 * vpk
        tr = skx.cross(g, rail, lvl, ckp - skx.EDGE, rkp, +1)
        ir0 = min(n - 1, int(round(rkp / skx.GRID)))
        ir1 = min(n - 1, int(round(min(rkp + 2 * (rop - rkp), g[-1]) / skx.GRID)))
        vfloor = float(np.min(rail[ir0:ir1 + 1]))
        vref_d = 0.5 * (float(rail[ir0]) + vfloor)
        trd = skx.cross(g, rail, vref_d, rkp - skx.EDGE, g[-1], -1)
        wend = min(rop + 200.0, g[-1])
        i0 = max(0, int(round((rkp - skx.EDGE) / skx.GRID)))
        i1 = min(n - 1, int(round(wend / skx.GRID)))
        gates = {}
        for i in range(skx.MG):
            if not skx.out_hi(L["bits"], k, i):
                continue
            vo = L["C"]["V(O%d_%d)" % (k, i)][:n]
            to = skx.cross(g, vo, lvl, ckp - skx.EDGE, rkp, +1)
            tod = skx.cross(g, vo, vref_d, rkp - skx.EDGE, wend, -1)
            jm = int(np.argmin(vo[i0:i1 + 1])) + i0
            dr = (1000.0 * (float(vo[ir0]) - float(vo[jm]))
                  / max(g[jm] - rkp, 1e-9)) if g[jm] > rkp else None
            gates[i] = dict(
                lag_rise=(None if (tr is None or to is None) else round(to - tr, 4)),
                lag_drain=(None if trd is None else
                           ("CENSORED" if tod is None else round(tod - trd, 4))),
                strand_V=round(float(vo[jm]), 5),
                droop_mV_ps=(round(dr, 4) if dr is not None else None))
        res[k] = dict(vref_drain_V=round(vref_d, 5), rail_floor_V=round(vfloor, 5),
                      vpk_V=round(vpk, 5), gates=gates,
                      A6_worst_uA=L["A6_worst"], A6=L["A6"])
    return res


out = {}
for tag, sub in (("w100_baseline", "T300"), ("w050_Ron_x2", "w050/T300"),
                 ("w200_Ron_x0p5", "w200/T300")):
    root = os.path.join(HERE, sub)
    if not os.path.exists(os.path.join(root, "P0", "sched.json")):
        print(tag, "MISSING")
        continue
    out[tag] = lane_lags(root)
    print("--", tag)
    for k in (1, 2, 3):
        r = out[tag][k]
        print("  bank%d vref %.3f floor %.3f A6 %s(%.3g uA)" %
              (k, r["vref_drain_V"], r["rail_floor_V"], r["A6"], r["A6_worst_uA"] or -1))
        for i, gg in sorted(r["gates"].items()):
            print("    o%d rise %-9s drain %-9s strand %.4f droop %s" %
                  (i, gg["lag_rise"], gg["lag_drain"], gg["strand_V"],
                   gg["droop_mV_ps"]))

if "w050_Ron_x2" in out and "w200_Ron_x0p5" in out:
    print()
    print("== gate-by-gate ratios vs baseline (drain lag; CENSORED -> inf) ==")
    for k in (1, 2, 3):
        for i in out["w100_baseline"][k]["gates"]:
            b = out["w100_baseline"][k]["gates"][i]["lag_drain"]
            h = out["w050_Ron_x2"][k]["gates"][i]["lag_drain"]
            d = out["w200_Ron_x0p5"][k]["gates"][i]["lag_drain"]
            def rat(x):
                if x == "CENSORED":
                    return "CENS"
                if b in (None, "CENSORED") or x is None or b == 0:
                    return "n/a"
                return round(x / b, 3)
            print("  bank%d o%d base %-9s w050 %-9s (x%s)  w200 %-9s (x%s)" %
                  (k, i, b, h, rat(h), d, rat(d)))
json.dump(out, open(os.path.join(HERE, "WSCALE.json"), "w"), indent=1)
print("wrote WSCALE.json")
