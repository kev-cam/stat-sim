#!/usr/bin/env python3
"""MEASUREMENT 2, ON A SMALL FIXTURE FIRST -- can the buck deliver into a TANK?

The standing directive is to prove a mechanism on a small fixture before
carrying it into the chain.  The question is narrow and a 4-arm fixture answers
it cleanly:

  A  inject -> BANK rail, bank only          the arrangement that measured
                                             Qdel/Qsup = 0.058 into a bank
  B  inject -> BANK rail, bank + tank        tank present, but fed at the bank
  C  inject -> TANK node, bank + tank        THE PROPOSAL
  D  inject -> TANK node, tank only          the load isolated: a pure capacitor,
                                             no cells at all

A vs D separates "the converter is broken" from "the bank is a hard load".
B vs C separates "a tank helps because it is big" from "a tank helps because the
top-up is not landing on the signal node".

The bank is a REAL 19-cell bank of committed inverters (the chain's bank-2 size),
not a capacitor standing in for one.  The tank is a real capacitor strapped to
the bank through the same RSTRAP the chain uses.  The converter, its gate
sequence and its mandatory switch-node capacitance are qal/ptu/chain.py's
corrected cell verbatim.  The only ideal sources in the deck are the 1.2 V
top-up supply and the cell input levels -- both are the boundary of the modelled
system and every number that depends on them is labelled a BOUND.
"""
import json, os, sys
from concurrent.futures import ThreadPoolExecutor
import tf

HERE  = tf.HERE
V0    = 0.765884      # MEASURED free chain rail3 at its boundary (qal/ptu)
MBANK = 19            # cells, the chain's bank-2 size
T_FIRE = 300.0        # ps, after the bank has settled
TEND   = 1600.0
DV_IN  = 1.2


def build(arm, ctk_fF, ltu, ton, tfw, probe=False, seq="early"):
    has_bank = arm in ("A", "B", "C")
    has_tank = arm in ("B", "C", "D")
    dest = "nrail" if arm in ("A", "B") else "ntk"
    e = tf.EDGE
    a = T_FIRE + tf.SLEW + 4 * e
    b = a + ton
    big = TEND * 4.0
    z = big if probe else b + tfw
    L = tf.head_lines() + ["VHI vhi 0 %g" % tf.VGH, "VSUP tsup 0 %g" % tf.VSUP,
                           "VMG gn 0 0"]
    if has_bank:
        for i in range(MBANK):
            L.append("VI%d in%d 0 %g" % (i, i, DV_IN if (i % 2 == 0) else 0.0))
            L.append("XP%d o%d in%d nrail nrail sg13_lv_pmos w=%gu l=0.13u"
                     % (i, i, i, tf.WP))
            L.append("XN%d o%d in%d gn gn sg13_lv_nmos w=%gu l=0.13u"
                     % (i, i, i, tf.WN))
            L.append("CL%d o%d gn %gf" % (i, i, tf.CLOAD))
    else:
        L.append("CRAILSTUB nrail 0 0.001f")   # keeps the node named in arm D
    if has_tank:
        L.append("CTK ntk 0 %.6gf" % ctk_fF)
        if has_bank:
            L.append("RTK ntk nrail %g" % tf.RSTRAP)
    w = tf.widths(tf.TOPUP_WSW * 1.5)
    L += ["CNA na 0 %gf" % tf.CNA_FF,
          "XTUSW na gtu tsup tsup sg13_lv_pmos w=%gu l=0.13u" % tf.TOPUP_WSW,
          "XTUFW na gfw 0 0 sg13_lv_nmos w=%gu l=0.13u" % tf.TOPUP_WSW,
          "LTU na ntm %gn" % ltu,
          "RTU ntm nbb %g" % tf.RSTU,
          "VMTU nbb nbx 0",
          # the OUT switch's own drain node.  sg13lv_compat.sp zeroes ad/as/pd/ps,
          # so without these the inductor island is FLOATING before the OUT switch
          # closes and the solver puts a ~100 uA startup transient on it that
          # swamps the pulse.  CBX is the 5+10 um drain area at ~1 fF/um^2 ->
          # ~0.5 fF (ASSUMED); RBX is a numerical bleed, not a physical element.
          "CBX nbx 0 0.5f", "RBX nbx 0 1e9",
          "XTUON nbx gto %s 0 sg13_lv_nmos w=%gu l=0.13u" % (dest, w["wn"]),
          "XTUOP nbx gtop %s vhi sg13_lv_pmos w=%gu l=0.13u" % (dest, w["wp"]),
          # HS pMOS gate.  seq="early" is qal/ptu/chain.py's committed "corrected"
          # sequence: the high side turns on at t_fire while the low side is STILL
          # clamping na to ground, so tsup is shorted to ground through both
          # 10 um devices for SLEW+4*EDGE = 32 ps before the pulse even starts.
          # seq="bbm" is genuine break-before-make: the high side turns on only
          # after the low side is fully off.  The difference is measured, not argued.
          ("VGTU gtu 0 PWL(0 %g %gp %g %gp 0 %gp 0 %gp %g)"
           % (tf.VGH, T_FIRE, tf.VGH, T_FIRE + 2 * e, b, b + e, tf.VGH)
           if seq == "early" else
           "VGTU gtu 0 PWL(0 %g %gp %g %gp 0 %gp 0 %gp %g)"
           % (tf.VGH, a, tf.VGH, a + e, b, b + e, tf.VGH)),
          "VGFW gfw 0 PWL(0 %g %gp %g %gp 0 %gp 0 %gp %g)"
          % (tf.VGH, a - tf.SLEW, tf.VGH, a, b, b + e, tf.VGH)]
    if probe:
        L += ["VGTO gto 0 PWL(0 0 %gp 0 %gp %g %gp %g)" % (a - e, a, tf.VGH, z, tf.VGH),
              "VGTOP gtop 0 PWL(0 %g %gp %g %gp 0 %gp 0)" % (tf.VGH, a - e, tf.VGH, a, z)]
    else:
        L += ["VGTO gto 0 PWL(0 0 %gp 0 %gp %g %gp %g %gp 0)"
              % (a - e, a, tf.VGH, z, tf.VGH, z + e),
              "VGTOP gtop 0 PWL(0 %g %gp %g %gp 0 %gp 0 %gp %g)"
              % (tf.VGH, a - e, tf.VGH, a, z, z + e, tf.VGH)]
    L += tf.integ("qd", "I(VMTU)")
    L += tf.integ("qs", "-I(VSUP)")
    dn = dest
    L += tf.integ("ed", "V(%s)*I(VMTU)" % dn)
    L += tf.integ("es", "-%g*I(VSUP)" % tf.VSUP)
    L += tf.integ("eg", "-V(gtu)*I(VGTU)-V(gfw)*I(VGFW)-V(gto)*I(VGTO)-V(gtop)*I(VGTOP)")
    L += tf.integ("qx", "-I(VSUP)")   # same meter, read over the overlap window
    ic = ".ic V(nrail)=%g" % V0
    if has_tank:
        ic += " V(ntk)=%g" % V0
    L += [ic, ".tran 0.05p %gp 0 0.05p" % (TEND if not probe else b + 800.0)]
    g = lambda t: t + tf.LAG_PS
    t_before, t_after = T_FIRE - 5.0, TEND - 5.0
    if not probe:
        for tg in ("qd", "qs", "ed", "es", "eg"):
            L.append(".measure tran %s_A FIND V(x%s) AT=%.6fp" % (tg.upper(), tg, g(t_before)))
            L.append(".measure tran %s_B FIND V(x%s) AT=%.6fp" % (tg.upper(), tg, g(t_after)))
        L.append(".measure tran VRA FIND V(nrail) AT=%.6fp" % g(t_before))
        L.append(".measure tran VRB FIND V(nrail) AT=%.6fp" % g(t_after))
        L.append(".measure tran VRPK MAX V(nrail) FROM=%gp TO=%gp" % (T_FIRE, TEND))
        if has_tank:
            L.append(".measure tran VTA FIND V(ntk) AT=%.6fp" % g(t_before))
            L.append(".measure tran VTB FIND V(ntk) AT=%.6fp" % g(t_after))
        L.append(".measure tran IZ FIND I(LTU) AT=%.6fp" % g(b + tfw))
        L.append(".measure tran IPK MAX I(LTU) FROM=%gp TO=%gp" % (a, TEND))
        L.append(".measure tran IMN MIN I(LTU) FROM=%gp TO=%gp" % (a, TEND))
        # SHOOT-THROUGH: charge out of the supply between the HS turning on and
        # the OUT switch closing.  In that window the inductor's far end is open,
        # so ANY supply charge here went straight to ground through the low side.
        L.append(".measure tran QX_0 FIND V(xqx) AT=%.6fp" % g(T_FIRE - 1.0))
        L.append(".measure tran QX_1 FIND V(xqx) AT=%.6fp" % g(a - e))
    pr = ["V(nrail)", "I(LTU)", "V(na)", "I(VMTU)"]
    if has_tank:
        pr.append("V(ntk)")
    if has_bank:
        pr += ["V(o0)", "V(o1)"]
    L += [".print tran " + " ".join(pr), ".end"]
    return L


def one(spec):
    arm, ctk, ltu, ton, seq = spec
    tag = "%s_C%g_L%g_t%g_%s" % (arm, ctk, ltu, ton, seq)
    Lp = build(arm, ctk, ltu, ton, None, probe=True, seq=seq)
    p, msg = tf.run("fxp_%s.cir" % tag, Lp, timeout=900)
    if p is None:
        return dict(arm=arm, tag=tag, error="probe: " + msg)
    hdr, rows = tf.read_prn(p + ".prn")
    e = tf.EDGE
    a = T_FIRE + tf.SLEW + 4 * e
    b = a + ton
    # INSTRUMENT RULE, stated because it had to be fixed: the committed
    # zero_after_peak takes the largest |I| and then the next sign change.  In the
    # PROBE form the OUT switch is held closed forever, so after the pulse the low
    # side re-clamps na to ground and the inductor DRAINS the destination through
    # the still-closed switch -- that reverse current is larger than the delivery
    # current, so "the largest |I|" lands on the drain, and there is no sign
    # change after it.  The freewheel zero we want is the first crossing after the
    # DELIVERY (positive) peak.  This is a fix to the search, not to the circuit.
    ic = hdr.index("I(LTU)")
    ser = [(r[1] * 1e12, r[ic]) for r in rows if a <= r[1] * 1e12 <= b + 300.0]
    pos = [(t, v) for t, v in ser if v > 0]
    z, pk = None, (max(pos, key=lambda x: x[1]) if pos else None)
    if pk:
        prev = None
        for t, v in ser:
            if t <= pk[0]:
                prev = (t, v); continue
            if prev is not None and v <= 0.0:
                z = prev[0] + (0.0 - prev[1]) * (t - prev[0]) / (v - prev[1]) \
                    if v != prev[1] else prev[0]
                break
            prev = (t, v)
        pk = pk[1]
    if z is None:
            return dict(arm=arm, seq=seq, tag=tag, error="probe: no current zero "
                    "(I(LTU) never changes sign after its |peak|)")
    tfw = max(0.0, z - b)
    L = build(arm, ctk, ltu, ton, tfw, seq=seq)
    p, msg = tf.run("fx_%s.cir" % tag, L, timeout=900)
    if p is None:
        return dict(arm=arm, tag=tag, error=msg)
    m = tf.parse_mt0(p + ".mt0")
    d = lambda t: m["%s_B" % t] - m["%s_A" % t]
    qd, qs = d("QD") * 1e15, d("QS") * 1e15
    dest = "nrail" if arm in ("A", "B") else "ntk"
    hdr, rows = tf.read_prn(p + ".prn")
    sl_r, tr = tf.max_slope(hdr, rows, "V(NRAIL)", T_FIRE - 10, TEND)
    sl_i = sl_r
    if "V(NTK)" in hdr:
        sl_i, _ = tf.max_slope(hdr, rows, "V(NTK)", T_FIRE - 10, TEND)
    sl_o = None
    if "V(O0)" in hdr:
        sl_o, _ = tf.max_slope(hdr, rows, "V(O0)", T_FIRE - 10, TEND)
    return dict(arm=arm, seq=seq, tag=tag, ctk_fF=ctk, ltu_nH=ltu, ton_ps=ton,
                tfw_ps=tfw, zero_ps=z, IPK_uA=m.get("IPK", 0) * 1e6,
                IZ_uA=m.get("IZ", 0) * 1e6, dest=dest,
                q_delivered_fC=qd, q_supply_fC=qs,
                Qdel_over_Qsup=(qd / qs if qs else None),
                E_delivered_fJ=d("ED") * 1e15, E_supply_fJ=d("ES") * 1e15,
                E_gate_drive_fJ=d("EG") * 1e15,
                q_shootthrough_fC=(m["QX_1"] - m["QX_0"]) * 1e15,
                IMN_uA=m.get("IMN", 0) * 1e6,
                Edel_over_Esup=(d("ED") / d("ES") if d("ES") else None),
                V_rail_before=m.get("VRA"), V_rail_after=m.get("VRB"),
                V_rail_peak=m.get("VRPK"),
                d_rail_mV=(m.get("VRB", 0) - m.get("VRA", 0)) * 1e3,
                V_tank_before=m.get("VTA"), V_tank_after=m.get("VTB"),
                d_tank_mV=((m.get("VTB", 0) - m.get("VTA", 0)) * 1e3
                           if "VTA" in m else None),
                slope_inject_V_per_ns=sl_i, slope_rail_V_per_ns=sl_r,
                slope_logic_V_per_ns=sl_o, msg=msg)


if __name__ == "__main__":
    ctk = float(sys.argv[1]) if len(sys.argv) > 1 else 522.0
    specs = [(arm, ctk, 1.0, 24.0, sq) for sq in ("bbm", "early")
             for arm in ("A", "B", "C", "D")]
    out = []
    with ThreadPoolExecutor(max_workers=2) as ex:
        for r in ex.map(one, specs):
            out.append(r)
            print("%-3s %-5s %s" % (r["arm"], r.get("seq"), r.get("error") or
                  "Qdel/Qsup %8.4f  qd %9.3f fC  qs %9.3f fC  rail %+.3f mV  tank %s  slope_inj %.1f V/ns"
                  % (r["Qdel_over_Qsup"] or float('nan'), r["q_delivered_fC"],
                     r["q_supply_fC"], r["d_rail_mV"],
                     ("%+.3f mV" % r["d_tank_mV"]) if r["d_tank_mV"] is not None else "-",
                     r["slope_inject_V_per_ns"])), flush=True)
    json.dump(out, open(os.path.join(HERE, "FIXTURE.json"), "w"), indent=1)
    print("wrote FIXTURE.json")
