#!/usr/bin/env python3
"""MY OWN buck-into-tank charge re-run, with two things the committed fixture
does not have.

  1. A SIGN-CONVENTION REFERENCE ARM (R).  The committed result is a NEGATIVE
     Qdel/Qsup in every arm -- an extraordinary claim (the converter is a net
     SINK).  Arm R replaces the whole converter with a resistor from the same
     1.2 V supply to the same destination through the SAME 0 V meter in the SAME
     orientation and the SAME OUT switch.  Its answer is known a priori:
     q_del > 0 and q_del == q_sup.  If R comes out right, the negative sign in
     the buck arms is the circuit, not the instrument.

  2. A FORWARD/REVERSE DECOMPOSITION.  The net charge over a window conflates
     "the converter cannot deliver" with "the freewheel runs backwards past its
     zero".  Integrating I(VMTU) split by sign separates them, and Qfwd/Qsup is
     the quantity that is actually comparable to the DCM bound Vin/Vout.

Arms A (bank only, inject at rail) and D (tank only, no cells, inject at tank)
are the load-exoneration pair.  B and C carry both.
"""
import json, os, sys
from concurrent.futures import ThreadPoolExecutor
import sk

HERE   = sk.HERE
V0     = 0.765884
MBANK  = 19
T_FIRE = 300.0
TEND   = 1600.0
DV_IN  = 1.2
SLEW   = 24.0
RSTU   = 10.0
VSUP   = 1.2
CNA_FF = 8.0
WSW    = 10.0


def build(arm, ctk, ltu, ton, tfw, probe=False, seq="early"):
    has_bank = arm in ("A", "B", "C", "R")
    has_tank = arm in ("B", "C", "D")
    dest = "nrail" if arm in ("A", "B", "R") else "ntk"
    e = sk.EDGE
    a = T_FIRE + SLEW + 4 * e
    b = a + ton
    big = TEND * 4.0
    z = big if probe else b + tfw
    L = sk.head_lines() + ["VHI vhi 0 %g" % sk.VGH, "VSUP tsup 0 %g" % VSUP,
                           "VMG gn 0 0"]
    if has_bank:
        for i in range(MBANK):
            L.append("VI%d in%d 0 %g" % (i, i, DV_IN if (i % 2 == 0) else 0.0))
            L.append("XP%d o%d in%d nrail nrail sg13_lv_pmos w=%gu l=0.13u" % (i, i, i, sk.WP))
            L.append("XN%d o%d in%d gn gn sg13_lv_nmos w=%gu l=0.13u" % (i, i, i, sk.WN))
            L.append("CL%d o%d gn %gf" % (i, i, sk.CLOAD))
    else:
        L.append("CRAILSTUB nrail 0 0.001f")
    if has_tank:
        L.append("CTK ntk 0 %.6gf" % ctk)
        if has_bank:
            L.append("RTK ntk nrail %g" % sk.RSTRAP)
    w = sk.widths(WSW * 1.5)
    if arm == "R":
        # THE SIGN REFERENCE: no inductor, no switching converter.  A resistor
        # from the supply straight through the same meter and the same OUT
        # switch into the same destination.  q_del MUST be positive and equal
        # q_sup.  Any other answer indicts the instrument, not the circuit.
        L += ["RREF tsup nbb 2k", "VMTU nbb nbx 0",
              "CBX nbx 0 0.5f", "RBX nbx 0 1e9",
              "XTUON nbx gto %s 0 sg13_lv_nmos w=%gu l=0.13u" % (dest, w["wn"]),
              "XTUOP nbx gtop %s vhi sg13_lv_pmos w=%gu l=0.13u" % (dest, w["wp"]),
              "VGTU gtu 0 0", "VGFW gfw 0 0"]
    else:
        L += ["CNA na 0 %gf" % CNA_FF,
              "XTUSW na gtu tsup tsup sg13_lv_pmos w=%gu l=0.13u" % WSW,
              "XTUFW na gfw 0 0 sg13_lv_nmos w=%gu l=0.13u" % WSW,
              "LTU na ntm %gn" % ltu, "RTU ntm nbb %g" % RSTU,
              "VMTU nbb nbx 0", "CBX nbx 0 0.5f", "RBX nbx 0 1e9",
              "XTUON nbx gto %s 0 sg13_lv_nmos w=%gu l=0.13u" % (dest, w["wn"]),
              "XTUOP nbx gtop %s vhi sg13_lv_pmos w=%gu l=0.13u" % (dest, w["wp"]),
              ("VGTU gtu 0 PWL(0 %g %gp %g %gp 0 %gp 0 %gp %g)"
               % (sk.VGH, T_FIRE, sk.VGH, T_FIRE + 2 * e, b, b + e, sk.VGH)
               if seq == "early" else
               "VGTU gtu 0 PWL(0 %g %gp %g %gp 0 %gp 0 %gp %g)"
               % (sk.VGH, a, sk.VGH, a + e, b, b + e, sk.VGH)),
              "VGFW gfw 0 PWL(0 %g %gp %g %gp 0 %gp 0 %gp %g)"
              % (sk.VGH, a - SLEW, sk.VGH, a, b, b + e, sk.VGH)]
    if probe:
        L += ["VGTO gto 0 PWL(0 0 %gp 0 %gp %g %gp %g)" % (a - e, a, sk.VGH, z, sk.VGH),
              "VGTOP gtop 0 PWL(0 %g %gp %g %gp 0 %gp 0)" % (sk.VGH, a - e, sk.VGH, a, z)]
    else:
        L += ["VGTO gto 0 PWL(0 0 %gp 0 %gp %g %gp %g %gp 0)"
              % (a - e, a, sk.VGH, z, sk.VGH, z + e),
              "VGTOP gtop 0 PWL(0 %g %gp %g %gp 0 %gp 0 %gp %g)"
              % (sk.VGH, a - e, sk.VGH, a, z, z + e, sk.VGH)]
    L += sk.integ("qd", "I(VMTU)")
    L += sk.integ("qs", "-I(VSUP)")
    L += sk.integ("eg", "-V(gtu)*I(VGTU)-V(gfw)*I(VGFW)-V(gto)*I(VGTO)-V(gtop)*I(VGTOP)")
    ic = ".ic V(nrail)=%g" % V0 + (" V(ntk)=%g" % V0 if has_tank else "")
    L += [ic, ".tran 0.05p %gp 0 0.05p" % (TEND if not probe else b + 800.0)]
    g = lambda t: t + sk.LAG_PS
    ta, tb = T_FIRE - 5.0, TEND - 5.0
    if not probe:
        for tg in ("qd", "qs", "eg"):
            L.append(".measure tran %s_A FIND V(x%s) AT=%.6fp" % (tg.upper(), tg, g(ta)))
            L.append(".measure tran %s_B FIND V(x%s) AT=%.6fp" % (tg.upper(), tg, g(tb)))
        L.append(".measure tran VRA FIND V(nrail) AT=%.6fp" % g(ta))
        L.append(".measure tran VRB FIND V(nrail) AT=%.6fp" % g(tb))
        if has_tank:
            L.append(".measure tran VTA FIND V(ntk) AT=%.6fp" % g(ta))
            L.append(".measure tran VTB FIND V(ntk) AT=%.6fp" % g(tb))
        L.append(".measure tran IZ FIND I(VMTU) AT=%.6fp" % g(b + tfw))
    pr = ["V(nrail)", "I(VMTU)", "V(na)" if arm != "R" else "V(nbx)"]
    if arm != "R":
        pr.append("I(LTU)")
    if has_tank:
        pr.append("V(ntk)")
    if has_bank:
        pr += ["V(o0)", "V(o1)"]
    L += [".print tran " + " ".join(pr), ".end"]
    return L


def split_charge(hdr, rows, col, ta, tb):
    """Trapezoidal integral of `col` over [ta,tb], split by sign of the
    integrand.  Returns (q_fwd, q_rev, q_net) in fC."""
    ic = hdr.index(col)
    s = [(r[1] * 1e12, r[ic]) for r in rows if ta <= r[1] * 1e12 <= tb]
    qf = qr = 0.0
    for j in range(1, len(s)):
        dt = (s[j][0] - s[j - 1][0]) * 1e-12
        i0, i1 = s[j - 1][1], s[j][1]
        if i0 >= 0 and i1 >= 0:
            qf += 0.5 * (i0 + i1) * dt
        elif i0 <= 0 and i1 <= 0:
            qr += 0.5 * (i0 + i1) * dt
        else:                               # sign change inside the step
            f = abs(i0) / (abs(i0) + abs(i1))
            qa, qb = 0.5 * i0 * dt * f, 0.5 * i1 * dt * (1 - f)
            if i0 > 0:
                qf += qa; qr += qb
            else:
                qr += qa; qf += qb
    return qf * 1e15, qr * 1e15, (qf + qr) * 1e15


def one(spec):
    arm, ctk, ltu, ton, seq = spec
    tag = "%s_C%g_L%g_t%g_%s" % (arm, ctk, ltu, ton, seq)
    e = sk.EDGE
    a = T_FIRE + SLEW + 4 * e
    b = a + ton
    if arm == "R":
        tfw, z = 600.0, None
    else:
        Lp = build(arm, ctk, ltu, ton, None, probe=True, seq=seq)
        p, msg = sk.run("sfxp_%s.cir" % tag, Lp, timeout=1200)
        if p is None:
            return dict(arm=arm, seq=seq, tag=tag, error="probe: " + msg)
        hdr, rows = sk.read_prn(p + ".prn")
        ic = hdr.index("I(LTU)")
        ser = [(r[1] * 1e12, r[ic]) for r in rows if a <= r[1] * 1e12 <= b + 300.0]
        pos = [(t, v) for t, v in ser if v > 0]
        z = None
        if pos:
            tpk = max(pos, key=lambda x: x[1])[0]
            prev = None
            for t, v in ser:
                if t <= tpk:
                    prev = (t, v); continue
                if prev is not None and v <= 0.0:
                    z = prev[0] + (0.0 - prev[1]) * (t - prev[0]) / (v - prev[1]) \
                        if v != prev[1] else prev[0]
                    break
                prev = (t, v)
        if z is None:
            return dict(arm=arm, seq=seq, tag=tag,
                        error="probe: no current zero after the delivery peak")
        tfw = max(0.0, z - b)
    L = build(arm, ctk, ltu, ton, tfw, seq=seq)
    p, msg = sk.run("sfx_%s.cir" % tag, L, timeout=1200)
    if p is None:
        return dict(arm=arm, seq=seq, tag=tag, error=msg)
    m = sk.parse_mt0(p + ".mt0")
    d = lambda t: m["%s_B" % t] - m["%s_A" % t]
    qd, qs = d("QD") * 1e15, d("QS") * 1e15
    hdr, rows = sk.read_prn(p + ".prn")
    qf, qr, qn = split_charge(hdr, rows, "I(VMTU)", T_FIRE - 5.0, TEND - 5.0)
    sl_r, _ = sk.max_slope(hdr, rows, "V(NRAIL)", T_FIRE - 10, TEND)
    sl_i = sl_r
    if "V(NTK)" in hdr:
        sl_i, _ = sk.max_slope(hdr, rows, "V(NTK)", T_FIRE - 10, TEND)
    sl_o = None
    if "V(O0)" in hdr:
        sl_o, _ = sk.max_slope(hdr, rows, "V(O0)", T_FIRE - 10, TEND)
    return dict(arm=arm, seq=seq, tag=tag, ctk_fF=ctk, ltu_nH=ltu, ton_ps=ton,
                tfw_ps=tfw, zero_ps=z, dest=("nrail" if arm in ("A", "B", "R") else "ntk"),
                q_delivered_fC=qd, q_supply_fC=qs,
                Qdel_over_Qsup=(qd / qs if qs else None),
                q_fwd_fC=qf, q_rev_fC=qr, q_net_trapz_fC=qn,
                Qfwd_over_Qsup=(qf / qs if qs else None),
                meter_vs_trapz_rel=(abs(qn - qd) / abs(qd) if qd else None),
                IZ_uA=m.get("IZ", 0) * 1e6,
                E_gate_drive_fJ=d("EG") * 1e15,
                V_rail_before=m.get("VRA"), V_rail_after=m.get("VRB"),
                d_rail_mV=(m.get("VRB", 0) - m.get("VRA", 0)) * 1e3,
                d_tank_mV=((m.get("VTB", 0) - m.get("VTA", 0)) * 1e3 if "VTA" in m else None),
                slope_inject_V_per_ns=sl_i, slope_rail_V_per_ns=sl_r,
                slope_logic_V_per_ns=sl_o, msg=msg)


if __name__ == "__main__":
    ctk = float(sys.argv[1]) if len(sys.argv) > 1 else 479.0
    specs = [("R", ctk, 1.0, 24.0, "early")] + \
            [(arm, ctk, 1.0, 24.0, sq) for sq in ("early", "bbm")
             for arm in ("A", "B", "C", "D")]
    out = []
    with ThreadPoolExecutor(max_workers=3) as ex:
        for r in ex.map(one, specs):
            out.append(r)
            if r.get("error"):
                print("%-3s %-5s ERROR %s" % (r["arm"], r.get("seq"), r["error"]), flush=True)
            else:
                print("%-3s %-5s Qdel/Qsup %9.4f  Qfwd/Qsup %8.4f  qd %9.3f  qf %9.3f  "
                      "qr %9.3f  qs %9.3f fC  rail %+8.3f mV  slope_inj %7.1f  "
                      "slope_logic %s"
                      % (r["arm"], r["seq"], r["Qdel_over_Qsup"] or float("nan"),
                         r["Qfwd_over_Qsup"] or float("nan"), r["q_delivered_fC"],
                         r["q_fwd_fC"], r["q_rev_fC"], r["q_supply_fC"],
                         r["d_rail_mV"], r["slope_inject_V_per_ns"],
                         ("%.1f" % r["slope_logic_V_per_ns"])
                         if r["slope_logic_V_per_ns"] else "-"), flush=True)
    json.dump(out, open(os.path.join(HERE, "FIXTURE_SKEPT.json"), "w"), indent=1)
    print("wrote FIXTURE_SKEPT.json")
