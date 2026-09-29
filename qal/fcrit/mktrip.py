#!/usr/bin/env python3
"""Build TRIP.json from whichever trip_*.cir.prn are finished."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trip import read_prn, xing, RAILS, CELLS

HERE = os.path.dirname(os.path.abspath(__file__))
out = {}
for tag, (wp, wn) in CELLS.items():
    p = os.path.join(HERE, "trip_%s.cir.prn" % tag)
    if not os.path.exists(p):
        print("skip", tag, "(not finished)")
        continue
    hdr, rows = read_prn(p)
    ic = hdr.index("V(IN)")
    vin = [r[ic] for r in rows]
    res = {}
    for j, vdd in enumerate(RAILS):
        if "V(O%d)" % j not in hdr:
            continue
        io = hdr.index("V(O%d)" % j)
        vo = [r[io] for r in rows]
        n = max(i for i in range(len(vin)) if vin[i] <= vdd + 1e-9) + 1
        vi, vv = vin[:n], vo[:n]
        t50, t90, t10 = (xing(vi, vv, 0.5 * vdd), xing(vi, vv, 0.9 * vdd),
                         xing(vi, vv, 0.1 * vdd))
        res["%.4f" % vdd] = dict(
            vdd=vdd, trip_V=t50, trip_frac_of_rail=(t50 / vdd if t50 else None),
            vin_at_vout90_V=t90, vin_at_vout10_V=t10,
            window_10_90_mV=(1000.0 * (t10 - t90) if (t10 and t90) else None),
            vout_at_vin0=vv[0], vout_at_vin_vdd=vv[-1])
    out[tag] = dict(wp=wp, wn=wn, rows=res)
json.dump(out, open(os.path.join(HERE, "TRIP.json"), "w"), indent=1)
print("wrote TRIP.json with receivers:", list(out))
