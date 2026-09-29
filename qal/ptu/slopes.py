#!/usr/bin/env python3
"""D1, THE MECHANISM MEASUREMENT: max |dV/dt| on the TOPPED rail.

The brief's claim is that a switched clamp to an ideal source delivers a VOLTAGE
STEP (which couples capacitively into the predecessor's LOW outputs) while a
pulsed inductor delivers a CURRENT RAMP (which cannot, because di/dt limits the
rail's slope).  That is a statement about dV/dt and it is directly measurable
from the .prn files that already exist.

Read only.  No simulation.  Reported for rail3 (topped in both forms) and for
rail2 (the FEEDING bank, where the coupling is alleged to land).
"""
import json, os, sys

sys.path.insert(0, "/usr/local/src/stat-sim/qal/skip4")
import skip as SK

SKIPTU = "/usr/local/src/stat-sim/qal/skiptu"
HERE = os.path.dirname(os.path.abspath(__file__))

# the common delivery window: both forms fire inside bank 3's hold, which starts
# at hop 1's measured open (~298-304 ps) and ends at bank 3's boundary (401 ps).
# The clamp conducts 305.68-325.68 ps; the pulsed form fires 307.98 and is cut at
# its own measured zero (up to 469 ps).  [300, 500] contains both in full.
WIN = (300.0, 500.0)


def slope(prn, node, t0, t1):
    hdr, rows = SK.read_prn(prn)
    want = "v(%s)" % node
    col = None
    for c in hdr:
        if c.strip().lower() == want:
            col = hdr.index(c); break
    if col is None:
        return None
    # skip.read_prn returns TIME in SI seconds in column 1 (column 0 is the index)
    seg = [(r[1] * 1e12, r[col]) for r in rows if t0 <= r[1] * 1e12 <= t1]
    if len(seg) < 3:
        return None
    best, bt, bdir = 0.0, None, 0
    vmin = vmax = seg[0][1]
    for j in range(1, len(seg) - 1):
        dt = seg[j + 1][0] - seg[j - 1][0]
        if dt <= 0:
            continue
        dv = seg[j + 1][1] - seg[j - 1][1]
        s = dv / dt * 1e3                      # V/ps -> V/ns
        if abs(s) > best:
            best, bt, bdir = abs(s), seg[j][0], (1 if s > 0 else -1)
        vmin = min(vmin, seg[j][1]); vmax = max(vmax, seg[j][1])
    # the largest RISING slope specifically -- that is the delivery event
    up, upt = 0.0, None
    for j in range(1, len(seg) - 1):
        dt = seg[j + 1][0] - seg[j - 1][0]
        if dt <= 0:
            continue
        s = (seg[j + 1][1] - seg[j - 1][1]) / dt * 1e3
        if s > up:
            up, upt = s, seg[j][0]
    return {"max_abs_dVdt_V_per_ns": round(best, 3), "at_ps": round(bt, 3),
            "sign": bdir,
            "max_RISING_dVdt_V_per_ns": round(up, 3),
            "rising_at_ps": round(upt, 3) if upt else None,
            "V_min": round(vmin, 6), "V_max": round(vmax, 6),
            "V_excursion_mV": round(1e3 * (vmax - vmin), 3),
            "n_samples": len(seg)}


def main():
    decks = sorted(f[:-4] for f in os.listdir(SKIPTU)
                   if f.endswith(".prn") and f.startswith("r_s4_")
                   and "_T200_dv1200_" in f)
    out = {"_what": "D1 max |dV/dt| on the topped rail (rail3) and the feeding "
                    "rail (rail2), over the common window %s ps" % (WIN,),
           "_window_contains": "clamp conduction 305.68-325.68 ps; pulsed fire "
                               "307.98 ps and its measured cut (to 469 ps)",
           "_units": "V/ns",
           "_note_ptu": "PRE-CNA / A6-DISQUALIFIED as physics; the SLOPE is still "
                        "the honest signature of how the two forms deliver.",
           "rows": {}}
    for d in decks:
        prn = os.path.join(SKIPTU, d + ".prn")
        mode = "ptu" if "_ptu_" in d else ("rtu" if "_rtu_" in d else "free")
        rec = {"mode": mode}
        for nd in ("rail3", "rail2", "rail4"):
            s = slope(prn, nd, *WIN)
            if s:
                rec[nd] = s
        out["rows"][d] = rec
    json.dump(out, open(os.path.join(HERE, "SLOPES.json"), "w"), indent=1)

    print("%-42s %-4s | %12s %12s | %10s | %10s" %
          ("deck", "mode", "rail3 |dV/dt|", "rail3 rise", "r3 excurs", "rail2 |dV/dt|"))
    print("%-42s %-4s | %12s %12s | %10s | %10s" %
          ("", "", "V/ns", "V/ns", "mV", "V/ns"))
    for d in sorted(out["rows"]):
        r = out["rows"][d]
        if "rail3" not in r:
            continue
        a, b = r["rail3"], r.get("rail2", {})
        print("%-42s %-4s | %12.3f %12.3f | %10.1f | %10.3f" %
              (d[:42], r["mode"], a["max_abs_dVdt_V_per_ns"],
               a["max_RISING_dVdt_V_per_ns"], a["V_excursion_mV"],
               b.get("max_abs_dVdt_V_per_ns", float("nan"))))


if __name__ == "__main__":
    main()
