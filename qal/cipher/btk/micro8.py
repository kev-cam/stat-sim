#!/usr/bin/env python3
"""PHASE 1 (e) -- THE DECISIVE COMPARISON, ONE HOP of the COMMITTED 8-CELL BANK.

CORRECTION to my own first attempt (micro.py, which ran and is kept on disk as
R_QAL_*_cw*_dv1650.json): micro.py used ONE cell against the committed tg15p
transfer switch, which is sized for EIGHT (wn = 10 um / wp = 20 um / park = 2 um
on a 4.50 fF load instead of a 35.98 fF one).  The switch's own parasitic
capacitance then dominates the load, the delivered rail collapsed to 0.78 V
against the chain's 1.18 V, and the incremental wire term was diluted by a
harness artefact.  Those rows are NOT used for any ratio.  This file is the
corrected harness: the full committed 8-cell bank, one hop.

Both sides are the SAME eight cells (wp = 1.12u / wn = 0.74u, CL = 2 fF), the
SAME committed pattern PAT = [1,1,1,0,1,0,0,1] (so the same THREE nodes swing
and the same five sit at 0), the SAME models, the SAME .OPTIONS, the SAME 2 ps
edges, the SAME wire capacitors.

  QAL   tank -> L(15 nH) -> R(10) -> tg15p(30 um) -> rail -> the bank.  Rail
        raised at the MEASURED ZCS, held, returned at the MEASURED ZCS.
        HEADLINE energy = 1/2 C_t (V0^2 - V1^2) on a LINEAR tank: no integrator
        convention, no sign convention.
  CMOS  ideal VDD -> the same bank.  The three pull-up cells' inputs are driven
        VDD -> 0 -> VDD so their nodes make a full 0 -> VDD -> 0 excursion; the
        other five hold.  Energy = 1F integrator of -VDD*I(VDD), cross-checked
        against VDD*Q from an independent charge integrator.
        VDD is SET EQUAL to the QAL variant's MEASURED node peak, so neither
        side moves its capacitance through a larger voltage (gate G9).

Only ONE capacitor moves between a pair, so the headline is the DIFFERENCE and
every fixed overhead cancels exactly.
"""
import json, math, os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bt
from bt import (MGATE, WP, WN, CLOAD, CBANK, RS_REF, L_REF, VGH, EDGE, LAG_PS,
                PAT, widths, in_hi, out_hi, head_lines, integ, parse_mt0,
                read_prn, zero_after_peak)

XYCE = "/usr/local/src/xyce-build/src/Xyce"
CACHE = os.environ.get("PYMS_VAE_CACHE") or \
    "/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6/scratchpad/vae_cache_cipher"
ENV = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS", PYMS_VAE_CACHE=CACHE)

M = 10
T1, HOLD, TAIL = 200.0, 600.0, 600.0
TZ0 = 65.49500982344826
NHI = sum(1 for i in range(MGATE) if out_hi(1, i))       # 3
SPAN = 3.6                       # qal/cipher AMENDMENT A1


def run(fn, lines, timeout=1800):
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


def cells(supply, dv, wpx=1.0):
    """The committed bank_cells(1, dv) with the supply node parameterised and an
    OPTIONAL pull-up width multiplier (wpx != 1 is a labelled MECHANISM PROBE,
    not a scored row: it departs from the committed cell)."""
    L = ["VMG gn 0 0"]
    for i in range(MGATE):
        L.append("VI%d in%d 0 %g" % (i, i, dv if in_hi(1, i) else 0.0))
    for i in range(MGATE):
        L += ["XP%d o%d in%d %s %s sg13_lv_pmos w=%gu l=0.13u"
              % (i, i, i, supply, supply, WP * wpx),
              "XN%d o%d in%d gn gn sg13_lv_nmos w=%gu l=0.13u" % (i, i, i, WN),
              "CL%d o%d gn %gf" % (i, i, CLOAD)]
    return L


def wire(cw, place):
    if cw <= 0.0 or place == "none":
        return []
    if place == "rail":
        return ["CWR rail gn %.6ff" % (NHI * cw)]
    return ["CW%d o%d gn %.6ff" % (i, i, cw) for i in range(MGATE)]


# ===================================================================== QAL
def qal_deck(cw, place, dv, ct_fF=None, tzr=None, tzq=None, probe=None,
             l_nh=L_REF, rs=RS_REF, total_um=30.0, wpx=1.0):
    w = widths(total_um)
    ct = ct_fF if ct_fF is not None else M * CBANK
    vt0 = dv * (M + 1.0) / (2.0 * M)
    tzr = TZ0 if tzr is None else tzr
    tzq = TZ0 if tzq is None else tzq
    tclose, topen = T1, T1 + tzr
    tret, tretopen = T1 + HOLD, T1 + HOLD + tzq
    if probe == "rise":
        tend = tclose + SPAN * TZ0 * math.sqrt(l_nh / L_REF)
    elif probe == "ret":
        tend = tret + SPAN * TZ0 * math.sqrt(l_nh / L_REF)
    else:
        tend = tretopen + TAIL
    big = tend * 4.0

    L = head_lines() + ["VHI vhi 0 %g" % VGH]
    L += cells("rail", dv, wpx) + wire(cw, place)
    L += ["CT tnk 0 %.6ff" % ct, "L1 tnk mid %gn" % l_nh, "R1 mid sw %g" % rs,
          "XSWN sw gt rail 0 sg13_lv_nmos w=%gu l=0.13u" % w["wn"],
          "XSWP sw gtp rail vhi sg13_lv_pmos w=%gu l=0.13u" % w["wp"],
          "XPK sw pk tnk tnk sg13_lv_nmos w=%gu l=0.13u" % w["park"]]

    wins = ([(tclose, None)] if probe == "rise" else
            [(tclose, topen), (tret, None)] if probe == "ret" else
            [(tclose, topen), (tret, tretopen)])
    pn, pp, pk = [(0.0, 0.0)], [(0.0, VGH)], [(0.0, VGH)]
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

    L.append(".ic V(tnk)=%g V(rail)=0 V(sw)=%g %s"
             % (vt0, vt0, " ".join("V(o%d)=0" % i for i in range(MGATE))))
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
            L.append(".measure tran VT%s FIND V(tnk) AT=%.6fp" % (nm, g(tt)))
            L.append(".measure tran VR%s FIND V(rail) AT=%.6fp" % (nm, g(tt)))
            L.append(".measure tran VS%s FIND V(sw) AT=%.6fp" % (nm, g(tt)))
            for i in range(MGATE):
                L.append(".measure tran VO%d%s FIND V(o%d) AT=%.6fp"
                         % (i, nm, i, g(tt)))
        L.append(".measure tran VRPK MAX V(rail) FROM=%gp TO=%gp" % (tclose, tend))
        for i in range(MGATE):
            L.append(".measure tran VO%dPK MAX V(o%d) FROM=%gp TO=%gp"
                     % (i, i, tclose, tend))
        L += [".measure tran IZ FIND I(L1) AT=%.6fp" % g(topen),
              ".measure tran IZQ FIND I(L1) AT=%.6fp" % g(tretopen),
              ".measure tran IPK MAX I(L1) FROM=%gp TO=%gp" % (tclose, tend)]
    L.append(".print tran V(tnk) V(rail) V(sw) I(L1) "
             + " ".join("V(o%d)" % i for i in range(MGATE)))
    L.append(".end")
    return L, dict(tclose=tclose, topen=topen, tret=tret, tretopen=tretopen,
                   tend=tend, ct_fF=ct, vt0=vt0)


def qal_probe(cw, place, dv, ct_fF, l_nh=L_REF, wpx=1.0):
    tag = "m8_%s_cw%.0f_ct%.0f_L%.0f_wx%.0f" % (place, cw * 1000, ct_fF * 10,
                                                l_nh * 10, wpx * 10)
    out = {}
    for ph in ("rise", "ret"):
        lines, S = qal_deck(cw, place, dv, ct_fF=ct_fF, tzr=out.get("tzr"),
                            probe=ph, l_nh=l_nh, wpx=wpx)
        fn = "%s_%s.cir" % (tag, ph)
        path = os.path.join(HERE, fn)
        cached = (os.path.exists(path) and os.path.exists(path + ".prn")
                  and open(path).read() == "\n".join(lines) + "\n")
        p, msg = (path, "reused %s" % fn) if cached else run(fn, lines)
        print("  %s" % msg, flush=True)
        if p is None:
            return None
        hdr, rows = read_prn(p + ".prn")
        t0 = S["tclose"] if ph == "rise" else S["tret"]
        z, pkv = zero_after_peak(hdr, rows, "I(L1)", t0)
        if z is None:
            print("  NO ZERO %s" % ph); return None
        out["tzr" if ph == "rise" else "tzq"] = z - t0
        print("    %s t_zcs = %.4f ps (Ipk %.2f uA)" % (ph, z - t0, pkv * 1e6),
              flush=True)
    return out


def qal_row(cw, place, dv, ct_fF, l_nh=L_REF, wpx=1.0):
    z = qal_probe(cw, place, dv, ct_fF, l_nh=l_nh, wpx=wpx)
    if z is None:
        return None
    lines, S = qal_deck(cw, place, dv, ct_fF=ct_fF, tzr=z["tzr"], tzq=z["tzq"],
                        l_nh=l_nh, wpx=wpx)
    fn = "M8Q_%s_cw%.0f_ct%.0f_L%.0f_wx%.0f.cir" % (place, cw * 1000, ct_fF * 10,
                                                    l_nh * 10, wpx * 10)
    p, msg = run(fn, lines)
    print("  %s" % msg, flush=True)
    if p is None:
        return None
    mt = parse_mt0(p + ".mt0")
    gi = lambda tg, ck: (mt["%s_%s" % (tg.upper(), ck)]
                         - mt["%s_Z" % tg.upper()]) * 1e15
    ct = S["ct_fF"]
    hi = [i for i in range(MGATE) if out_hi(1, i)]
    r = dict(kind="QAL8", cw_fF=cw, place=place, dv=dv, ct_fF=ct, vt0=S["vt0"],
             L_nH=l_nh, wp_scale=wpx, wp_um=WP * wpx,
             n_swinging=len(hi), swinging=hi, tzr=z["tzr"], tzq=z["tzq"],
             deck=os.path.basename(p),
             V_tank_t0=mt["VTZ"], V_tank_after_rise=mt["VTO"],
             V_tank_after_return=mt["VTQ"], V_tank_end=mt["VTD"],
             V_rail_at_open=mt["VRO"], V_rail_peak=mt["VRPK"],
             V_rail_end=mt["VRD"],
             V_node_peak={i: mt["VO%dPK" % i] for i in range(MGATE)},
             V_node_at_open={i: mt["VO%dO" % i] for i in range(MGATE)},
             V_node_end={i: mt["VO%dD" % i] for i in range(MGATE)},
             IZ_uA=1e6 * mt["IZ"], IZQ_uA=1e6 * mt["IZQ"], IPK_uA=1e6 * mt["IPK"],
             E_tank_lost_cycle_fJ=0.5 * ct * (mt["VTZ"] ** 2 - mt["VTQ"] ** 2),
             E_tank_lost_to_end_fJ=0.5 * ct * (mt["VTZ"] ** 2 - mt["VTD"] ** 2),
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
    r["recycle_fraction_pct"] = (100.0 * r["E_back_into_tank_return_fJ"] /
                                 r["E_into_rail_rise_fJ"]) \
        if r["E_into_rail_rise_fJ"] else None
    if cw > 0.0 and place == "node":
        r["E_wire_stored_peak_fJ"] = sum(0.5 * cw * mt["VO%dPK" % i] ** 2
                                         for i in hi)
        r["E_wire_stranded_end_fJ"] = sum(0.5 * cw * mt["VO%dD" % i] ** 2
                                          for i in hi)
        r["V_node_peak_mean_swinging"] = sum(mt["VO%dPK" % i] for i in hi) / len(hi)
        r["V_node_end_mean_swinging"] = sum(mt["VO%dD" % i] for i in hi) / len(hi)
    elif cw > 0.0 and place == "rail":
        r["E_wire_stored_peak_fJ"] = 0.5 * NHI * cw * mt["VRPK"] ** 2
        r["E_wire_stranded_end_fJ"] = 0.5 * NHI * cw * mt["VRD"] ** 2
        r["V_node_peak_mean_swinging"] = mt["VRPK"]
        r["V_node_end_mean_swinging"] = mt["VRD"]
    else:
        r["E_wire_stored_peak_fJ"] = 0.0
        r["E_wire_stranded_end_fJ"] = 0.0
        r["V_node_peak_mean_swinging"] = sum(mt["VO%dPK" % i] for i in hi) / len(hi)
        r["V_node_end_mean_swinging"] = sum(mt["VO%dD" % i] for i in hi) / len(hi)
    return r


# ==================================================================== CMOS
def cmos_deck(cw, vdd):
    t_lo, t_hi, tend = 300.0, 900.0, 1500.0
    L = head_lines() + ["VDD vdd 0 %.9g" % vdd, "VMG gn 0 0"]
    for i in range(MGATE):
        if out_hi(1, i):
            # this node must swing 0 -> vdd -> 0, so its input falls then rises
            L.append("VI%d in%d 0 PWL(0 %.9g %gp %.9g %gp 0 %gp 0 %gp %.9g "
                     "%gp %.9g)"
                     % (i, i, vdd, t_lo - EDGE, vdd, t_lo, t_hi, t_hi + EDGE,
                        vdd, tend, vdd))
        else:
            L.append("VI%d in%d 0 %.9g" % (i, i, vdd))
    for i in range(MGATE):
        L += ["XP%d o%d in%d vdd vdd sg13_lv_pmos w=%gu l=0.13u" % (i, i, i, WP),
              "XN%d o%d in%d gn gn sg13_lv_nmos w=%gu l=0.13u" % (i, i, i, WN),
              "CL%d o%d gn %gf" % (i, i, CLOAD)]
    L += wire(cw, "node" if cw > 0 else "none")
    tags = []
    for nm, ex in (("evd", "-%.9g*I(VDD)" % vdd), ("qvd", "-I(VDD)")):
        L += integ(nm, ex); tags.append(nm)
    L.append(".ic " + " ".join("V(o%d)=0" % i for i in range(MGATE)))
    L.append(".tran 0.1p %gp 0 0.25p" % tend)
    g = lambda t: t + LAG_PS
    cks = [("Z", 0.5), ("A", t_hi - 5.0), ("D", tend - 5.0)]
    for tg in tags:
        for nm, tt in cks:
            L.append(".measure tran %s_%s FIND V(x%s) AT=%.6fp"
                     % (tg.upper(), nm, tg, g(tt)))
    for nm, tt in cks:
        for i in range(MGATE):
            L.append(".measure tran VO%d%s FIND V(o%d) AT=%.6fp" % (i, nm, i, g(tt)))
    for i in range(MGATE):
        L.append(".measure tran VO%dPK MAX V(o%d) FROM=0 TO=%gp" % (i, i, tend))
    L += [".print tran I(VDD) " + " ".join("V(o%d)" % i for i in range(MGATE)),
          ".end"]
    return L, dict(t_lo=t_lo, t_hi=t_hi, tend=tend)


def cmos_row(cw, vdd):
    lines, S = cmos_deck(cw, vdd)
    fn = "M8C_cw%.0f_vdd%.0f.cir" % (cw * 1000, vdd * 100000)
    p, msg = run(fn, lines)
    print("  %s" % msg, flush=True)
    if p is None:
        return None
    mt = parse_mt0(p + ".mt0")
    gi = lambda tg, ck: (mt["%s_%s" % (tg.upper(), ck)]
                         - mt["%s_Z" % tg.upper()]) * 1e15
    hi = [i for i in range(MGATE) if out_hi(1, i)]
    r = dict(kind="CMOS8", cw_fF=cw, vdd=vdd, deck=os.path.basename(p),
             n_swinging=len(hi), swinging=hi,
             V_node_peak={i: mt["VO%dPK" % i] for i in range(MGATE)},
             V_node_end={i: mt["VO%dD" % i] for i in range(MGATE)},
             E_supply_rise_fJ=gi("evd", "A"),
             E_supply_cycle_fJ=gi("evd", "D"),
             Q_supply_rise_fC=gi("qvd", "A"),
             Q_supply_cycle_fC=gi("qvd", "D"))
    r["E_supply_cycle_QV_fJ"] = vdd * r["Q_supply_cycle_fC"]
    r["E_integrator_vs_QV_residual_fJ"] = r["E_supply_cycle_fJ"] - \
        r["E_supply_cycle_QV_fJ"]
    r["E_textbook_CV2_fJ"] = len(hi) * (CLOAD + cw) * vdd * vdd
    return r


if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "qal":
        cw, place, dv, ct = float(a[1]), a[2], float(a[3]), float(a[4])
        lh = float(a[5]) if len(a) > 5 else L_REF
        wx = float(a[6]) if len(a) > 6 else 1.0
        r = qal_row(cw, place, dv, ct, l_nh=lh, wpx=wx)
        if r is None:
            sys.exit(1)
        nm = "M8_QAL_%s_cw%.0f_ct%.0f%s.json" % (place, cw * 1000, ct * 10,
             "" if (lh == L_REF and wx == 1.0) else "_L%.0f_wx%.0f" % (lh*10, wx*10))
        open(os.path.join(HERE, nm), "w").write(json.dumps(r, indent=1))
        print("wrote %s  Etank_cycle=%.4f fJ  rail_pk=%.4f  node_pk=%.4f  "
              "node_end=%.4f" % (nm, r["E_tank_lost_cycle_fJ"], r["V_rail_peak"],
                                 r["V_node_peak_mean_swinging"],
                                 r["V_node_end_mean_swinging"]))
    elif a and a[0] == "cmos":
        cw, vdd = float(a[1]), float(a[2])
        r = cmos_row(cw, vdd)
        if r is None:
            sys.exit(1)
        nm = "M8_CMOS_cw%.0f_vdd%.0f.json" % (cw * 1000, vdd * 100000)
        open(os.path.join(HERE, nm), "w").write(json.dumps(r, indent=1))
        print("wrote %s  E_cycle=%.4f fJ (QV %.4f, textbook %.4f)"
              % (nm, r["E_supply_cycle_fJ"], r["E_supply_cycle_QV_fJ"],
                 r["E_textbook_CV2_fJ"]))
    else:
        print(__doc__)
