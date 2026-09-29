#!/usr/bin/env python3
"""THE STEP-COUPLING MEASUREMENT, done directly on the victim.

VERDICT.json m2 names the damage mechanism:

  "the topped bank's rail STEP couples backward through its own cell gate
   capacitance into the predecessor's output nodes, lifting the predecessor's
   LOW outputs.  That is the pull-DOWN margin of the feeding stage."

The predecessor of the topped bank 3 is bank 2.  Stage 2's PULL-DOWN cells are
those with SK.is_hi(2, i) true -- i.e. i odd -- and their outputs o2_1, o2_3,
o2_5, o2_7 are the LOW nodes the rail step is alleged to lift.

So: measure, over a window centred on the top-up FIRE and containing nothing
else that switches,

    * rail3's slope and excursion      (the CAUSE)
    * rail2's excursion                (the feeding bank's own rail)
    * each o2_{odd} LOW node's LIFT    (the DAMAGE, on the actual victim)

Read only.  No simulation.
"""
import json, os, sys

sys.path.insert(0, "/usr/local/src/stat-sim/qal/skip4")
import skip as SK

SKIPTU = "/usr/local/src/stat-sim/qal/skiptu"
HERE = os.path.dirname(os.path.abspath(__file__))

# THE FIRE WINDOW.  Chosen from the decks, not from the data:
#   hop 1 opens (rail3 charged)                ~298.98 ps
#   clamp XTUN3/XTUP3 conducts                 305.68 -> 325.68 ps  (+2 ps edges)
#   pulsed HS fires / OUT closes               307.98 ps
#   bank 3's stage boundary                    401.00 ps
#   hop 2 closes (drains rail2)                400.00 ps   <-- MUST be excluded
# [302, 399] contains every top-up delivery event and no hop switching at all.
WIN = (302.0, 399.0)


def col_of(hdr, node):
    want = "v(%s)" % node.lower()
    for c in hdr:
        if c.strip().lower() == want:
            return hdr.index(c)
    return None


def trace(hdr, rows, node, t0, t1):
    c = col_of(hdr, node)
    if c is None:
        return None
    return [(r[1] * 1e12, r[c]) for r in rows if t0 <= r[1] * 1e12 <= t1]


def stats(seg):
    if not seg or len(seg) < 3:
        return None
    vs = [v for _, v in seg]
    up, upt, dn = 0.0, None, 0.0
    for j in range(1, len(seg) - 1):
        dt = seg[j + 1][0] - seg[j - 1][0]
        if dt <= 0:
            continue
        s = (seg[j + 1][1] - seg[j - 1][1]) / dt * 1e3       # V/ns
        if s > up:
            up, upt = s, seg[j][0]
        if s < dn:
            dn = s
    return {"V_start": round(vs[0], 6), "V_end": round(vs[-1], 6),
            "V_min": round(min(vs), 6), "V_max": round(max(vs), 6),
            "rise_from_start_mV": round(1e3 * (max(vs) - vs[0]), 3),
            "net_change_mV": round(1e3 * (vs[-1] - vs[0]), 3),
            "max_RISING_dVdt_V_per_ns": round(up, 3),
            "rising_at_ps": round(upt, 3) if upt else None,
            "max_FALLING_dVdt_V_per_ns": round(dn, 3)}


def main():
    decks = sorted(f[:-4] for f in os.listdir(SKIPTU)
                   if f.endswith(".prn") and f.startswith("r_s4_")
                   and "_T200_dv1200_" in f)
    out = {"_what": "step-coupling measured on the victim: stage 2's PULL-DOWN "
                    "output nodes o2_{1,3,5,7}, over the top-up fire window "
                    "%s ps, which contains every delivery event and no hop "
                    "switching." % (WIN,),
           "_victim_rule": "SK.is_hi(2, i) true -> pull-DOWN cell -> o2_i is a LOW "
                           "node. For bank 2 that is i odd.",
           "_label_ptu": "PRE-CNA / A6-DISQUALIFIED as physics; reported because the "
                         "SLOPE and the COUPLING are what the mechanism claim is about.",
           "rows": {}}

    lowidx = [i for i in range(SK.MGATE) if SK.is_hi(2, i)]
    out["_stage2_pulldown_gates"] = lowidx

    for d in decks:
        prn = os.path.join(SKIPTU, d + ".prn")
        hdr, rows = SK.read_prn(prn)
        mode = "ptu" if "_ptu_" in d else ("rtu" if "_rtu_" in d else "free")
        rec = {"mode": mode}
        for nd in ("rail3", "rail2"):
            s = stats(trace(hdr, rows, nd, *WIN))
            if s:
                rec[nd] = s
        lows = {}
        for i in lowidx:
            s = stats(trace(hdr, rows, "o2_%d" % i, *WIN))
            if s:
                lows["o2_%d" % i] = s
        if lows:
            rec["stage2_LOW_nodes"] = lows
            rec["worst_LOW_lift_mV"] = round(max(v["rise_from_start_mV"]
                                                 for v in lows.values()), 3)
            rec["worst_LOW_net_mV"] = round(max(v["net_change_mV"]
                                                for v in lows.values()), 3)
        out["rows"][d] = rec

    json.dump(out, open(os.path.join(HERE, "COUPLING.json"), "w"), indent=1)

    print("window %s ps   (stage-2 pull-down gates: %s)" % (WIN, lowidx))
    print("%-40s %-4s | %9s %9s %9s | %9s | %9s" %
          ("deck", "mode", "r3 rise", "r3 dV/dt+", "r3 exc", "r2 exc", "LOW lift"))
    print("%-40s %-4s | %9s %9s %9s | %9s | %9s" %
          ("", "", "mV", "V/ns", "mV", "mV", "mV"))
    for d in sorted(out["rows"]):
        r = out["rows"][d]
        if "rail3" not in r:
            continue
        a, b = r["rail3"], r.get("rail2", {})
        print("%-40s %-4s | %9.1f %9.2f %9.1f | %9.2f | %9.3f" %
              (d[:40], r["mode"], a["rise_from_start_mV"],
               a["max_RISING_dVdt_V_per_ns"],
               1e3 * (a["V_max"] - a["V_min"]),
               1e3 * (b.get("V_max", 0) - b.get("V_min", 0)),
               r.get("worst_LOW_lift_mV", float("nan"))))


if __name__ == "__main__":
    main()
