#!/usr/bin/env python3
"""(b) THE LEAKAGE BUDGET OVER ONE BEAT -- measured on the real devices at the
QAL rail.  This licenses or refutes the whole 'ephemeral values need no keeper'
premise, so it runs FIRST and its result is reported whichever way it falls.

Three independent measurements, deliberately redundant:

  L1  DC off-state current of each device at the QAL rail (Vgs = 0, |Vds| = rail).
      Unambiguous; the charge over a beat is then Id * T_beat (DERIVED).
  L2  DC GATE-terminal current of an ON device (Vgs = rail).  PSP103 carries gate
      tunnelling; if it is non-negligible it belongs in the budget and the
      'subthreshold only' framing of the brief would be incomplete.
  L3  TRANSIENT hold: a real 2 fF node precharged to the rail with the real
      off-devices of a stripped cell hung on it, held for 2 ns.  Measures the
      droop DIRECTLY, with no Id * t arithmetic.  Run with and without a keeper.
      2 ns is used (not one beat) because ~1 nA on 2 fF moves ~0.1 mV in 200 ps;
      the long run makes the slope unambiguous and the one-beat number is then
      read off the same waveform at 150 / 200 / 300 ps.

DECLARED MODEL BIAS (pre-registered): sg13lv_compat.sp zeroes ad/as/pd/ps, so
drain/source JUNCTION leakage is ABSENT.  Every leakage number here is therefore
a LOWER BOUND and the budget is OPTIMISTIC on the leakage side.  The same
omission removes drain junction CAPACITANCE, which makes the node LIGHTER than
reality and so OVERSTATES the lost fraction -- that bias cuts the other way and
is quantified in the output.
"""
import json, os, sys
import common as C

HERE = C.HERE
RAILS = [0.50, 0.55, 0.5571, 0.60, 0.6077, 0.65, 0.70, 0.75]
# 0.5571 and 0.6077 are the MEASURED delivered rails (VBEND) of the committed
# dV = 1.2 and dV = 1.5 single-hop points -- the actual QAL rail of this study.


# ---------------------------------------------------------------- L1: off-state
def deck_off():
    """Vgs = 0, |Vds| swept.  One instance per (type, width) of interest.
    nMOS: d = node (high), g = 0, s = 0, b = 0        -> subthreshold off-leak
    pMOS: s = rail, b = rail, g = rail, d = 0         -> subthreshold off-leak
    Each device is fed from its OWN 0 V ammeter source so the current is exact."""
    devs = [("n", 0.74), ("n", 1.12), ("n", 0.15),
            ("p", 1.12), ("p", 0.56), ("p", 0.15)]
    L = C.head() + ["VR r 0 0.6"]
    tags = []
    for k, (t, w) in enumerate(devs):
        tg = "%s%s" % (t, str(w).replace(".", "p"))
        tags.append((tg, t, w))
        if t == "n":
            # drain held at the rail through a 0 V ammeter
            L += ["VA%d r da%d 0" % (k, k),
                  "XM%d da%d 0 0 0 sg13_lv_nmos w=%gu l=0.13u" % (k, k, w)]
        else:
            # source+bulk on the rail, gate on the rail (off), drain at 0 V
            L += ["VA%d db%d 0 0" % (k, k),
                  "XM%d db%d r r r sg13_lv_pmos w=%gu l=0.13u" % (k, k, w)]
    L += [".DC VR 0.40 0.80 0.01",
          ".print dc " + " ".join("I(VA%d)" % k for k in range(len(devs))),
          ".end"]
    return L, tags


# ------------------------------------------------------------------- L2: gate
def deck_gate():
    """Gate-terminal current of an ON device at the QAL rail (PSP103 tunnelling).
    nMOS: g = rail, d = s = b = 0.  pMOS: g = 0, s = d = b = rail."""
    devs = [("n", 0.74), ("n", 1.12), ("p", 1.12), ("p", 0.56)]
    L = C.head() + ["VR r 0 0.6"]
    tags = []
    for k, (t, w) in enumerate(devs):
        tags.append(("%s%s" % (t, str(w).replace(".", "p")), t, w))
        if t == "n":
            L += ["VG%d r g%d 0" % (k, k),
                  "XG%d 0 g%d 0 0 sg13_lv_nmos w=%gu l=0.13u" % (k, k, w)]
        else:
            L += ["VG%d 0 g%d 0" % (k, k),
                  "XG%d r g%d r r sg13_lv_pmos w=%gu l=0.13u" % (k, k, w)]
    L += [".DC VR 0.40 0.80 0.01",
          ".print dc " + " ".join("I(VG%d)" % k for k in range(len(devs))),
          ".end"]
    return L, tags


# ----------------------------------------------------------- L3: transient hold
def deck_hold(rail, keeper, tend_ps=2000.0):
    """A REAL stripped-cell output node held for tend_ps.

    Node Q is precharged to `rail` and carries CL = 2 fF.  Hung on it, exactly as
    in the stripped cell:
       * its own nMOS tree device, OFF (gate at 0)          -> subthreshold
       * the opposite cross-coupled pMOS, OFF (gate at rail) -> subthreshold
    The node is otherwise FLOATING: no pull-up, no keeper.  That is the ephemeral
    case.  `keeper=True` adds a conventional staticiser -- a weak feedback
    inverter driving a weak pMOS/nMOS pair -- so the two can be compared in ONE
    harness.  NOTE the keeper is measured for its LEAKAGE/HOLD contribution here;
    its ENERGY cost is the 24.4 fJ / 55%-of-cell figure the campaign already has.
    """
    L = C.head() + ["VR r 0 %g" % rail,
                    "CQ q 0 %gf" % C.CLOAD,
                    # the cell's own tree nMOS, held OFF
                    "XNT q 0 0 0 sg13_lv_nmos w=%gu l=0.13u" % C.WTREE,
                    # the opposite cross-coupled pMOS, held OFF (gate on rail)
                    "XPX q r r r sg13_lv_pmos w=%gu l=0.13u" % C.WXC]
    if keeper:
        L += ["XKPI ki q r r sg13_lv_pmos w=0.15u l=0.13u",
              "XKNI ki q 0 0 sg13_lv_nmos w=0.15u l=0.13u",
              "XKP q ki r r sg13_lv_pmos w=0.15u l=0.13u",
              "XKN q ki 0 0 sg13_lv_nmos w=0.15u l=0.13u"]
    L += [".ic V(q)=%g" % rail,
          ".tran 0.5p %gp 0 1p" % tend_ps,
          ".print tran V(q)" + (" V(ki)" if keeper else ""),
          ".end"]
    return L


def main():
    out = {"_declared_bias": (
        "sg13lv_compat.sp zeroes ad/as/pd/ps: drain/source JUNCTION leakage is "
        "ABSENT, so every current here is a LOWER BOUND and the budget is "
        "OPTIMISTIC on leakage. The same omission removes drain junction "
        "CAPACITANCE, which makes the node LIGHTER than reality and therefore "
        "OVERSTATES the lost FRACTION -- that bias cuts the other way.")}

    # ---- L1
    L, tags = deck_off()
    p, msg, w = C.run("leak_off.cir", L, timeout=300)
    print("L1", msg)
    if p:
        wv = C.W(p + ".prn", tscale=1.0)
        cols = [c for c in wv.hdr if c.startswith("I(VA")]
        d = {}
        for k, (tg, t, wid) in enumerate(tags):
            nm = "I(VA%d)" % k
            d[tg] = {"type": t, "w_um": wid,
                     "Id_off_nA": {("%.4f" % r): abs(wv.at(nm, r)) * 1e9
                                   for r in RAILS}}
        out["L1_offstate_dc"] = d
        out["L1_cols"] = cols

    # ---- L2
    L, tags = deck_gate()
    p, msg, w = C.run("leak_gate.cir", L, timeout=300)
    print("L2", msg)
    if p:
        wv = C.W(p + ".prn", tscale=1.0)
        d = {}
        for k, (tg, t, wid) in enumerate(tags):
            nm = "I(VG%d)" % k
            d[tg] = {"type": t, "w_um": wid,
                     "Ig_on_nA": {("%.4f" % r): abs(wv.at(nm, r)) * 1e9
                                  for r in RAILS}}
        out["L2_gate_dc"] = d

    # ---- L3
    hold = {}
    for rail in (0.5571, 0.6077):
        for keeper in (False, True):
            tag = "rail%.4f_%s" % (rail, "keeper" if keeper else "bare")
            fn = "leak_hold_%s.cir" % tag.replace(".", "p")
            p, msg, w = C.run(fn, deck_hold(rail, keeper), timeout=300)
            print("L3", tag, msg)
            if not p:
                hold[tag] = {"error": msg}
                continue
            wv = C.W(p + ".prn")
            v0 = wv.at("V(q)", 0.0)
            row = {"rail_V": rail, "keeper": keeper, "V0": v0, "wall_s": w}
            for t in (150.0, 200.0, 300.0, 500.0, 1000.0, 2000.0):
                vt = wv.at("V(q)", t)
                row["V_at_%gps" % t] = vt
                row["droop_mV_at_%gps" % t] = (v0 - vt) * 1e3
                row["frac_lost_pct_at_%gps" % t] = (v0 - vt) / v0 * 100.0
            # implied leakage current from the 2 ns slope (t0-referenced)
            dv = wv.at("V(q)", 0.0) - wv.at("V(q)", 2000.0)
            row["implied_I_leak_nA_from_2ns_slope"] = \
                dv * C.CLOAD * 1e-15 / (2000.0e-12) * 1e9
            hold[tag] = row
    out["L3_transient_hold"] = hold
    json.dump(out, open(os.path.join(HERE, "LEAKAGE.json"), "w"), indent=1)
    print(json.dumps(out, indent=1)[:4000])


if __name__ == "__main__":
    main()
