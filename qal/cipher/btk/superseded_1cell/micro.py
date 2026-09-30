#!/usr/bin/env python3
"""PHASE 1 (e) -- THE DECISIVE COMPARISON, single hop, one cell, one harness.

The SAME wire capacitance, the SAME cell (wp = 1.12u / wn = 0.74u, the committed
banktank cell), the SAME models, the SAME .OPTIONS, the SAME 2 ps edges, the
SAME metering discipline, run two ways:

  QAL   tank -> L -> R -> tg15p -> rail -> cell -> node.   The rail is raised at
        the MEASURED ZCS and returned at the MEASURED ZCS, exactly as the
        committed banktank hop does.  Headline energy = the tank's own
        1/2 C_t (V0^2 - V1^2) on a LINEAR capacitor: no integrator convention.

  CMOS  ideal VDD -> the same cell -> the same node.  Input driven through a full
        0 -> 1 -> 0 cycle with the same 2 ps edges, so the node makes the same
        excursion.  Energy = 1F integrator of -VDD*I(VDD), cross-checked against
        VDD * Q with Q from an independent charge integrator.

THE ONLY THING THAT MOVES between a pair is the one capacitor, so the reported
number is the INCREMENTAL wire energy and every fixed overhead -- the cell's own
load, the input gate drive, the switch gate drive, the tank's own baseline loss
-- cancels EXACTLY in the difference.  That is why the difference, and not the
absolute, is the headline.

THREE QAL placements:
  cw on the NODE  (signal wire: behind the cell's pMOS, OUTSIDE the LC loop)
  cw on the RAIL  (rail/clock wire: ON the resonant node, INSIDE the LC loop)
  cw = 0          (the control)

FAIRNESS (pre-registered G9): the CMOS supply is set equal to the MEASURED peak
the QAL node reaches, so neither side moves its capacitance through a larger
voltage than the other.  Two VDD values are run -- the Q0 node peak and the Q1
node peak -- and both ratios are reported, because V enters squared.
"""
import json, math, os, re, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bt
from bt import (WP, WN, CLOAD, CBANK, RS_REF, L_REF, VGH, EDGE, LAG_PS,
                widths, head_lines, integ, parse_mt0, read_prn, zero_after_peak)

XYCE = "/usr/local/src/xyce-build/src/Xyce"
CACHE = os.environ.get("PYMS_VAE_CACHE") or \
    "/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6/scratchpad/vae_cache_cipher"
ENV = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS", PYMS_VAE_CACHE=CACHE)

CB1   = CBANK / 8.0        # 4.497375 fF -- one cell's share of the committed
                           # MEASURED 8-cell bank secant C.  DERIVED.
M     = 10                 # the committed tank multiplier
T1    = 200.0              # rail-raise closes (pre-roll), committed
HOLD  = 600.0              # ps the rail is held before the return closes
TAIL  = 600.0              # ps after the last event
TZ0   = 65.49500982344826  # committed single-hop zero anchor, used only to size
                           # the probe window


def run(fn, lines, timeout=1200):
    path = os.path.join(HERE, fn)
    open(path, "w").write("\n".join(lines) + "\n")
    t0 = time.monotonic()
    try:
        r = subprocess.run([XYCE, fn], capture_output=True, text=True,
                           timeout=timeout, cwd=HERE, env=ENV)
    except subprocess.TimeoutExpired:
        return None, "TIMEOUT %gs" % timeout
    wall = time.monotonic() - t0
    if r.returncode != 0 or not os.path.exists(path + ".prn"):
        err = "; ".join(l.strip() for l in r.stdout.splitlines()
                        if "rror" in l or "bort" in l)[:400]
        return None, "XYCE FAIL %s (%.1fs): %s" % (fn, wall, err or r.stdout[-300:])
    return path, "ran %s in %.1fs" % (fn, wall)


# ===================================================================== QAL
def qal_deck(cw, place, dv, l_nh=L_REF, rs=RS_REF, total_um=30.0,
             ct_fF=None, tzr=None, tzq=None, probe=None):
    """place in ('none','node','rail').  probe in (None,'rise','ret')."""
    w = widths(total_um)
    ct = ct_fF if ct_fF is not None else M * CB1
    vt0 = dv * (M + 1.0) / (2.0 * M)
    tzr = TZ0 if tzr is None else tzr
    tzq = TZ0 if tzq is None else tzq
    tclose, topen = T1, T1 + tzr
    tret, tretopen = T1 + HOLD, T1 + HOLD + tzq
    if probe == "rise":
        tend = tclose + 2.6 * TZ0 * math.sqrt(l_nh / L_REF)
    elif probe == "ret":
        tend = tret + 2.6 * TZ0 * math.sqrt(l_nh / L_REF)
    else:
        tend = tretopen + TAIL
    big = tend * 4.0

    L = head_lines() + ["VHI vhi 0 %g" % VGH, "VMG gn 0 0", "VIN in 0 0"]
    # the cell, VERBATIM widths/load of the committed banktank cell
    L += ["XP o in rail rail sg13_lv_pmos w=%gu l=0.13u" % WP,
          "XN o in gn gn sg13_lv_nmos w=%gu l=0.13u" % WN,
          "CL o gn %gf" % CLOAD]
    if cw > 0.0 and place == "node":
        L.append("CW o gn %.6ff" % cw)
    if cw > 0.0 and place == "rail":
        L.append("CW rail gn %.6ff" % cw)
    # the tank branch, VERBATIM structure of bt.tank_branch (A6 park)
    L += ["CT tnk 0 %.6ff" % ct,
          "L1 tnk mid %gn" % l_nh,
          "R1 mid sw %g" % rs,
          "XSWN sw gt rail 0 sg13_lv_nmos w=%gu l=0.13u" % w["wn"],
          "XSWP sw gtp rail vhi sg13_lv_pmos w=%gu l=0.13u" % w["wp"],
          "XPK sw pk tnk tnk sg13_lv_nmos w=%gu l=0.13u" % w["park"]]

    # phases: committed break-before-make, park anti-phase (bt.phase_pwl)
    if probe == "rise":
        wins = [(tclose, None)]
    elif probe == "ret":
        wins = [(tclose, topen), (tret, None)]
    else:
        wins = [(tclose, topen), (tret, tretopen)]
    pn = [(0.0, 0.0)]
    pp = [(0.0, VGH)]
    pk = [(0.0, VGH)]
    for (tc, to) in wins:
        pn += [(tc - EDGE, 0.0), (tc, VGH)]
        pp += [(tc - EDGE, VGH), (tc, 0.0)]
        pk += [(tc - EDGE, VGH), (tc, 0.0)]
        if to is None:
            pn += [(big, VGH)]; pp += [(big, 0.0)]; pk += [(big, 0.0)]
            break
        pn += [(to, VGH), (to + EDGE, 0.0)]
        pp += [(to, 0.0), (to + EDGE, VGH)]
        pk += [(to, 0.0), (to + EDGE, VGH)]
    f = lambda pts: " ".join("%gp %g" % (t, v) if t > 0 else "0 %g" % v
                             for t, v in pts)
    L += ["VGT gt 0 PWL(%s)" % f(pn), "VGTP gtp 0 PWL(%s)" % f(pp),
          "VPK pk 0 PWL(%s)" % f(pk)]

    tags = []
    if probe is None:
        for nm, ex in (("qlt", "I(L1)"), ("ea", "V(tnk)*I(L1)"),
                       ("eb", "V(rail)*I(L1)"), ("esw", "V(sw)*I(L1)"),
                       ("er", "I(L1)*I(L1)*%g" % rs), ("qg", "I(VMG)"),
                       ("egt", "-V(gt)*I(VGT)-V(gtp)*I(VGTP)-V(pk)*I(VPK)"),
                       ("ehi", "-%g*I(VHI)" % VGH)):
            L += integ(nm, ex); tags.append(nm)

    L.append(".ic V(tnk)=%g V(rail)=0 V(sw)=%g V(o)=0" % (vt0, vt0))
    L.append(".tran 0.1p %gp 0 0.25p" % tend)
    g = lambda t: t + LAG_PS
    if probe is None:
        cks = [("Z", 0.5), ("O", topen), ("R", tret - EDGE), ("Q", tretopen),
               ("D", tend - 5.0)]
        for tg in tags:
            for nm, tt in cks:
                L.append(".measure tran %s_%s FIND V(x%s) AT=%.6fp"
                         % (tg.upper(), nm, tg, g(tt)))
        for nm, tt in cks:
            for sig, pre in (("V(tnk)", "VT"), ("V(rail)", "VR"), ("V(o)", "VO"),
                             ("V(sw)", "VS")):
                L.append(".measure tran %s%s FIND %s AT=%.6fp"
                         % (pre, nm, sig, g(tt)))
        L += [".measure tran VOPK MAX V(o) FROM=%gp TO=%gp" % (tclose, tend),
              ".measure tran VRPK MAX V(rail) FROM=%gp TO=%gp" % (tclose, tend),
              ".measure tran IZ FIND I(L1) AT=%.6fp" % g(topen),
              ".measure tran IZQ FIND I(L1) AT=%.6fp" % g(tretopen),
              ".measure tran IPK MAX I(L1) FROM=%gp TO=%gp" % (tclose, tend)]
    L.append(".print tran V(tnk) V(rail) V(o) V(sw) I(L1)")
    L.append(".end")
    return L, dict(tclose=tclose, topen=topen, tret=tret, tretopen=tretopen,
                   tend=tend, ct_fF=ct, vt0=vt0, cw=cw, place=place, dv=dv)


def qal_probe(cw, place, dv, ct_fF=None):
    """Sequential true-ZCS probe, committed protocol: the rise zero first, then
    the return zero with the rise cut at its own measured zero."""
    tag = "q_%s_cw%.0f_dv%.0f" % (place, cw * 1000, dv * 1000)
    out = {}
    for ph in ("rise", "ret"):
        lines, S = qal_deck(cw, place, dv, ct_fF=ct_fF,
                            tzr=out.get("tzr"), probe=ph)
        fn = "%s_%s.cir" % (tag, ph)
        path = os.path.join(HERE, fn)
        cached = (os.path.exists(path) and os.path.exists(path + ".prn")
                  and open(path).read() == "\n".join(lines) + "\n")
        p, msg = (path, "reused %s" % fn) if cached else run(fn, lines)
        print("  %s %s" % (tag, msg), flush=True)
        if p is None:
            return None
        hdr, rows = read_prn(p + ".prn")
        t0 = S["tclose"] if ph == "rise" else S["tret"]
        z, pkv = zero_after_peak(hdr, rows, "I(L1)", t0)
        if z is None:
            print("  NO ZERO"); return None
        out["tzr" if ph == "rise" else "tzq"] = z - t0
        print("    %s t_zcs = %.4f ps (Ipk %.2f uA)" % (ph, z - t0, pkv * 1e6),
              flush=True)
    return out


def qal_row(cw, place, dv, ct_fF=None):
    z = qal_probe(cw, place, dv, ct_fF=ct_fF)
    if z is None:
        return None
    lines, S = qal_deck(cw, place, dv, ct_fF=ct_fF, tzr=z["tzr"], tzq=z["tzq"])
    fn = "Q_%s_cw%.0f_dv%.0f_ct%.0f.cir" % (place, cw * 1000, dv * 1000,
                                            S["ct_fF"] * 10)
    p, msg = run(fn, lines)
    print("  %s" % msg, flush=True)
    if p is None:
        return None
    mt = parse_mt0(p + ".mt0")
    gi = lambda tg, ck: (mt["%s_%s" % (tg.upper(), ck)] - mt["%s_Z" % tg.upper()]) * 1e15
    ct = S["ct_fF"]
    r = dict(kind="QAL", cw_fF=cw, place=place, dv=dv, ct_fF=ct, vt0=S["vt0"],
             tzr=z["tzr"], tzq=z["tzq"], deck=os.path.basename(p),
             V_tank_t0=mt["VTZ"], V_tank_after_rise=mt["VTO"],
             V_tank_after_return=mt["VTQ"], V_tank_end=mt["VTD"],
             V_rail_at_open=mt["VRO"], V_rail_peak=mt["VRPK"],
             V_node_at_open=mt["VOO"], V_node_peak=mt["VOPK"],
             V_node_at_return_open=mt["VOQ"], V_node_end=mt["VOD"],
             IZ_uA=1e6 * mt["IZ"], IZQ_uA=1e6 * mt["IZQ"], IPK_uA=1e6 * mt["IPK"],
             # HEADLINE, convention-free: a LINEAR tank cap
             E_tank_lost_cycle_fJ=0.5 * ct * (mt["VTZ"] ** 2 - mt["VTQ"] ** 2),
             E_tank_lost_to_end_fJ=0.5 * ct * (mt["VTZ"] ** 2 - mt["VTD"] ** 2),
             # integrator cross-checks
             E_out_of_tank_rise_fJ=gi("ea", "O"),
             E_into_rail_rise_fJ=gi("eb", "O"),
             E_seriesR_rise_fJ=gi("er", "O"),
             E_switchblock_rise_fJ=gi("esw", "O") - gi("eb", "O"),
             path_identity_rise_fJ=gi("ea", "O") - gi("esw", "O") - gi("er", "O"),
             E_back_into_tank_return_fJ=-(gi("ea", "Q") - gi("ea", "R")),
             E_out_of_tank_whole_run_fJ=gi("ea", "D"),
             E_gate_drive_fJ=gi("egt", "D"), E_vhi_fJ=gi("ehi", "D"),
             Q_through_L_rise_fC=gi("qlt", "O"))
    r["tank_closure_residual_fJ"] = r["E_out_of_tank_whole_run_fJ"] - \
        r["E_tank_lost_to_end_fJ"]
    r["E_node_stored_at_peak_fJ"] = 0.5 * (CLOAD + (cw if place == "node" else 0.0)) \
        * mt["VOPK"] ** 2
    r["E_wire_stored_at_peak_fJ"] = (0.5 * cw * mt["VOPK"] ** 2) if place == "node" \
        else (0.5 * cw * mt["VRPK"] ** 2)
    r["E_wire_stranded_at_end_fJ"] = (0.5 * cw * mt["VOD"] ** 2) if place == "node" \
        else (0.5 * cw * mt["VRD"] ** 2 if "VRD" in mt else 0.5 * cw * mt["VRO"] ** 2)
    return r


# ==================================================================== CMOS
def cmos_deck(cw, vdd, tag):
    """The SAME cell and the SAME load driven from an ideal VDD through a full
    0 -> 1 -> 0 node cycle, same 2 ps edges.  The 2 ps input edge MINIMISES
    CMOS short-circuit current, which FAVOURS CMOS -- stated, not hidden."""
    t_lo, t_hi, tend = 300.0, 900.0, 1500.0
    L = head_lines() + ["VDD vdd 0 %.9g" % vdd, "VMG gn 0 0"]
    # input starts HIGH (node LOW), falls at t_lo (node charges), rises at t_hi
    L += ["VIN in 0 PWL(0 %.9g %gp %.9g %gp 0 %gp 0 %gp %.9g %gp %.9g)"
          % (vdd, t_lo - EDGE, vdd, t_lo, t_hi, t_hi + EDGE, vdd, tend, vdd),
          "XP o in vdd vdd sg13_lv_pmos w=%gu l=0.13u" % WP,
          "XN o in gn gn sg13_lv_nmos w=%gu l=0.13u" % WN,
          "CL o gn %gf" % CLOAD]
    if cw > 0.0:
        L.append("CW o gn %.6ff" % cw)
    tags = []
    for nm, ex in (("evd", "-%.9g*I(VDD)" % vdd), ("qvd", "-I(VDD)"),
                   ("qgn", "I(VMG)")):
        L += integ(nm, ex); tags.append(nm)
    L.append(".ic V(o)=0")
    L.append(".tran 0.1p %gp 0 0.25p" % tend)
    g = lambda t: t + LAG_PS
    cks = [("Z", 0.5), ("A", t_hi - 5.0), ("D", tend - 5.0)]
    for tg in tags:
        for nm, tt in cks:
            L.append(".measure tran %s_%s FIND V(x%s) AT=%.6fp"
                     % (tg.upper(), nm, tg, g(tt)))
    for nm, tt in cks:
        L.append(".measure tran VO%s FIND V(o) AT=%.6fp" % (nm, g(tt)))
    L += [".measure tran VOPK MAX V(o) FROM=0 TO=%gp" % tend,
          ".print tran V(o) V(in) I(VDD)", ".end"]
    return L, dict(t_lo=t_lo, t_hi=t_hi, tend=tend, vdd=vdd, cw=cw)


def cmos_row(cw, vdd):
    lines, S = cmos_deck(cw, vdd, "")
    fn = "C_cw%.0f_vdd%.0f.cir" % (cw * 1000, vdd * 10000)
    p, msg = run(fn, lines)
    print("  %s" % msg, flush=True)
    if p is None:
        return None
    mt = parse_mt0(p + ".mt0")
    gi = lambda tg, ck: (mt["%s_%s" % (tg.upper(), ck)] - mt["%s_Z" % tg.upper()]) * 1e15
    r = dict(kind="CMOS", cw_fF=cw, vdd=vdd, deck=os.path.basename(p),
             V_node_peak=mt["VOPK"], V_node_at_A=mt["VOA"], V_node_end=mt["VOD"],
             E_supply_rise_fJ=gi("evd", "A"),
             E_supply_cycle_fJ=gi("evd", "D"),
             Q_supply_rise_fC=gi("qvd", "A"),
             Q_supply_cycle_fC=gi("qvd", "D"))
    # integrator-free cross-check: an ideal fixed source delivers E = V * Q
    r["E_supply_cycle_QV_fJ"] = vdd * r["Q_supply_cycle_fC"]
    r["E_integrator_vs_QV_residual_fJ"] = r["E_supply_cycle_fJ"] - \
        r["E_supply_cycle_QV_fJ"]
    return r


if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "qal":
        cw, place, dv = float(a[1]), a[2], float(a[3])
        ct = float(a[4]) if len(a) > 4 else None
        r = qal_row(cw, place, dv, ct_fF=ct)
        if r is None:
            sys.exit(1)
        nm = "R_QAL_%s_cw%.0f_dv%.0f%s.json" % (place, cw * 1000, dv * 1000,
                                                "" if ct is None else "_ctm")
        open(os.path.join(HERE, nm), "w").write(json.dumps(r, indent=1))
        print(json.dumps({k: v for k, v in r.items()
                          if k.startswith(("E_", "V_", "IZ", "IPK"))}, indent=1))
    elif a and a[0] == "cmos":
        cw, vdd = float(a[1]), float(a[2])
        r = cmos_row(cw, vdd)
        if r is None:
            sys.exit(1)
        nm = "R_CMOS_cw%.0f_vdd%.0f.json" % (cw * 1000, vdd * 10000)
        open(os.path.join(HERE, nm), "w").write(json.dumps(r, indent=1))
        print(json.dumps(r, indent=1))
    else:
        print(__doc__)
