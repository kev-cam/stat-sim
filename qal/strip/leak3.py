#!/usr/bin/env python3
"""L4: THE NULL CONTROL, and a long hold that lifts the signal off the floor.

L3 (leak.py) measured a 2 fF node holding 0.5571 V for 2 ns and found a droop of
5.75e-4 mV -- i.e. 575 nV.  RELTOL = 1e-6 on 0.557 V is 557 nV.  THE MEASURED
DROOP IS THE SAME ORDER AS THE SOLVER'S OWN VOLTAGE TOLERANCE, so L3 on its own
cannot distinguish subthreshold leakage from numerical drift, and it must not be
quoted as a leakage number until this deck says which it is.

Three controls, all in one deck so they share a solver trajectory:
  NULL   a 2 fF capacitor with NOTHING attached.  Any droop here is drift.
  BARE   the real stripped-cell node: OFF tree nMOS + OFF opposite pMOS.
  KEEP   the same node with a conventional staticiser.
  NONLY / PONLY  one device each, to attribute the leakage to a terminal.
Held for 100 ns: 50x the L3 window, so a real leakage current shows up 50x
larger while a fixed tolerance floor does not grow with it.
"""
import json, os
import common as C

HERE = C.HERE
TEND = 100000.0     # ps = 100 ns


def deck(rail):
    L = C.head() + ["VR r 0 %g" % rail]
    # NULL: nothing attached at all
    L += ["CN qnull 0 %gf" % C.CLOAD]
    # BARE: the real stripped-cell node
    L += ["CB qbare 0 %gf" % C.CLOAD,
          "XBN qbare 0 0 0 sg13_lv_nmos w=%gu l=0.13u" % C.WTREE,
          "XBP qbare r r r sg13_lv_pmos w=%gu l=0.13u" % C.WXC]
    # NONLY / PONLY
    L += ["CNO qnon 0 %gf" % C.CLOAD,
          "XNO qnon 0 0 0 sg13_lv_nmos w=%gu l=0.13u" % C.WTREE,
          "CPO qpon 0 %gf" % C.CLOAD,
          "XPO qpon r r r sg13_lv_pmos w=%gu l=0.13u" % C.WXC]
    # KEEP: staticised node
    L += ["CK qkeep 0 %gf" % C.CLOAD,
          "XKN qkeep 0 0 0 sg13_lv_nmos w=%gu l=0.13u" % C.WTREE,
          "XKX qkeep r r r sg13_lv_pmos w=%gu l=0.13u" % C.WXC,
          "XKIP ki qkeep r r sg13_lv_pmos w=0.15u l=0.13u",
          "XKIN ki qkeep 0 0 sg13_lv_nmos w=0.15u l=0.13u",
          "XKPP qkeep ki r r sg13_lv_pmos w=0.15u l=0.13u",
          "XKPN qkeep ki 0 0 sg13_lv_nmos w=0.15u l=0.13u"]
    nodes = ["qnull", "qbare", "qnon", "qpon", "qkeep"]
    L.append(".ic " + " ".join("V(%s)=%g" % (n, rail) for n in nodes) +
             " V(ki)=0")
    L.append(".print tran " + " ".join("V(%s)" % n for n in nodes) + " V(ki)")
    L += [".tran 5p %gp 0 20p" % TEND, ".end"]
    return L, nodes


def main():
    out = {"_why": ("L3's 2 ns droop (575 nV) sits at the solver's own RELTOL "
                    "voltage resolution (~557 nV on this rail), so a NULL "
                    "control -- a 2 fF cap with nothing attached -- and a 100 ns "
                    "hold are needed before any leakage number is quoted."),
           "_declared_bias": ("sg13lv_compat.sp zeroes ad/as/pd/ps: junction "
                              "leakage is ABSENT, so all of this is a LOWER "
                              "BOUND on real leakage."),
           "rails": {}}
    for rail in (0.5571, 0.6077):
        L, nodes = deck(rail)
        fn = "leak_null_r%s.cir" % ("%.4f" % rail).replace(".", "p")
        p, msg, wall = C.run(fn, L, timeout=1200)
        print(rail, msg, flush=True)
        if not p:
            out["rails"]["%.4f" % rail] = {"error": msg}
            continue
        w = C.W(p + ".prn")
        d = {"wall_s": wall, "rail_V": rail, "nodes": {}}
        for n in nodes:
            v0 = w.at("V(%s)" % n, 0.0)
            row = {"V0": v0}
            for t in (200.0, 1000.0, 10000.0, 50000.0, 100000.0):
                vt = w.at("V(%s)" % n, t)
                row["droop_uV_at_%gps" % t] = (v0 - vt) * 1e6
            dv = v0 - w.at("V(%s)" % n, TEND)
            row["I_leak_pA_from_100ns_slope"] = \
                dv * C.CLOAD * 1e-15 / (TEND * 1e-12) * 1e12
            d["nodes"][n] = row
        # attribute: subtract the NULL drift from every other node
        nl = d["nodes"]["qnull"]["I_leak_pA_from_100ns_slope"]
        d["null_drift_pA"] = nl
        for n in nodes:
            d["nodes"][n]["I_leak_minus_null_pA"] = \
                d["nodes"][n]["I_leak_pA_from_100ns_slope"] - nl
        out["rails"]["%.4f" % rail] = d
    json.dump(out, open(os.path.join(HERE, "LEAK_NULL.json"), "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
