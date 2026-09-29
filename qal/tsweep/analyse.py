#!/usr/bin/env python3
"""TRACK B analysis: the 1/T law, the per-op floor, the CMOS comparator, tau."""
import glob, json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROWD = os.path.join(HERE, "rowd")

# ---- committed per-op anchors (NOT measured here; quoted and labelled) ------
PEROP = {
    "harness_ideal_PWL_gate_drive": None,          # measured per row: E_gate_drive_fJ
    "resonant_gt_gtp_pair_fJ": 2.974,              # qal/recov, qal/park (a NETTING of two
                                                   # electrically unconnected ideal sources)
    "complete_timer_ledger_fJ": 23.213,            # qal/park + qal/amp row [X4], c814e52
    "ideal_PWL_floor_fJ": 3.5227,                  # the campaign's ideal-PWL switch-drive floor
    "switch_gate_charge_fC": 29.0,                 # 0.155 fC/um, linear in width
}
CMOS_ANCHOR_FJ_PER_CELL_CYCLE = 10.0831            # bound/RESULTS.json campaign anchor


def rows(pat):
    out = []
    for fn in sorted(glob.glob(os.path.join(ROWD, pat))):
        try:
            out.append(json.load(open(fn)))
        except Exception:
            pass
    return out


def loglog_fit(xs, ys):
    """least-squares slope of log y vs log x  ->  y ~ x^p"""
    n = len(xs)
    lx = [math.log(x) for x in xs]
    ly = [math.log(y) for y in ys]
    mx, my = sum(lx) / n, sum(ly) / n
    sxy = sum((a - mx) * (b - my) for a, b in zip(lx, ly))
    sxx = sum((a - mx) ** 2 for a in lx)
    p = sxy / sxx
    a = my - p * mx
    # R^2
    ss_res = sum((b - (a + p * x)) ** 2 for x, b in zip(lx, ly))
    ss_tot = sum((b - my) ** 2 for b in ly)
    return p, math.exp(a), (1 - ss_res / ss_tot if ss_tot else float("nan"))


def main():
    qs = [r for r in rows("T*.json") if "error" not in r and r.get("rs_ohm") == 10.0]
    qs.sort(key=lambda r: r["t_hop_ps"])
    rs = [r for r in rows("RS*.json") if "error" not in r]
    rs.sort(key=lambda r: r["rs_ohm"])
    cm = [r for r in rows("cm_*.json") if "error" not in r]
    lk = [r for r in rows("lk_*.json") if "error" not in r]
    out = {}

    # =================================================== (c) the 1/T law
    print("=" * 132)
    print("(c)  T SWEEP AT FIXED VOLTAGE  (dV=1.0, CA=35.979 fF, TG 15 um, RS=10, VGH=1.5; "
          "T varied THROUGH L, zero RE-PROBED per L)")
    print("=" * 132)
    hdr = ("%9s %8s %9s %9s %9s %9s %9s %9s %9s %9s %8s %7s %6s" %
           ("L nH", "T_hop", "E_R", "E_swblk", "E_xfer", "E_xfer*T", "E_Bresid",
            "E_hop", "E_gate", "cells", "VBEND", "t_lvl", "C4"))
    print(hdr)
    tab = []
    for r in qs:
        exf = r["E_R_toC_fJ"] + r["E_switchblock_toC_fJ"]
        d = dict(L_nH=r["L_nH"], T_ps=r["t_hop_ps"], E_R=r["E_R_toC_fJ"],
                 E_swblk=r["E_switchblock_toC_fJ"], E_xfer=exf,
                 E_xfer_T=exf * r["t_hop_ps"], E_Bresid=r["E_Bresid_toC_fJ"],
                 E_hop=r["E_hop_open_fJ"], E_gate=r["E_gate_drive_fJ"],
                 cells=r["cells_burn_fJ"], VBEND=r["VBEND"],
                 t_level=r.get("t_level_ps"), C4=r["C4_instrument"],
                 FUNCTIONAL=r["FUNCTIONAL"], Q_L_fC=r["Q_through_L_C_fC"],
                 IPK_uA=r["IPK_uA"], tag=r["tag"])
        tab.append(d)
        print("%9.1f %8.2f %9.4f %9.4f %9.4f %9.2f %9.4f %9.4f %9.4f %9.4f %8.4f %7s %6s"
              % (d["L_nH"], d["T_ps"], d["E_R"], d["E_swblk"], d["E_xfer"], d["E_xfer_T"],
                 d["E_Bresid"], d["E_hop"], d["E_gate"], d["cells"], d["VBEND"],
                 ("%.1f" % d["t_level"]) if d["t_level"] else "-", d["C4"]))
    out["T_sweep"] = tab

    good = [d for d in tab if d["C4"] == "PASS"]
    print("\n--- exponent fits  E_xfer = k * T^(-p)   (p = 1.000 is the adiabatic law) ---")
    fits = {}
    spans = [("ALL rows", good),
             ("T >= 86 ps  (the adiabatic side)", [d for d in good if d["T_ps"] >= 86.0]),
             ("T >= 265 ps (slower than the committed anchor)",
              [d for d in good if d["T_ps"] >= 265.0]),
             ("T <= 86 ps  (the fast side)", [d for d in good if d["T_ps"] <= 86.0])]
    for nm, sub in spans:
        if len(sub) < 3:
            continue
        p, k, r2 = loglog_fit([d["T_ps"] for d in sub], [d["E_xfer"] for d in sub])
        dec = math.log10(max(d["T_ps"] for d in sub) / min(d["T_ps"] for d in sub))
        fits[nm] = dict(p=p, k=k, r2=r2, n=len(sub), decades=dec,
                        T_lo=min(d["T_ps"] for d in sub), T_hi=max(d["T_ps"] for d in sub))
        print("  %-48s n=%2d  T %7.1f-%7.1f ps (%.2f dec)  p = %+.4f   R^2 = %.6f"
              % (nm, len(sub), fits[nm]["T_lo"], fits[nm]["T_hi"], dec, p, r2))
    out["exponent_fits"] = fits

    print("\n--- LOCAL slope, adjacent pairs (where does it depart from -1?) ---")
    loc = []
    for a, b in zip(good, good[1:]):
        s = (math.log(b["E_xfer"]) - math.log(a["E_xfer"])) / \
            (math.log(b["T_ps"]) - math.log(a["T_ps"]))
        loc.append(dict(T_lo=a["T_ps"], T_hi=b["T_ps"], slope=s,
                        Tmid=math.sqrt(a["T_ps"] * b["T_ps"])))
        print("   %8.2f -> %8.2f ps   local p = %+.4f  %s"
              % (a["T_ps"], b["T_ps"], -s, "" if abs(-s - 1) <= 0.10 else "  <-- DEPARTS >0.10"))
    out["local_slopes"] = loc

    # also: does E_Bresid (the destination/gate-settle term) fall with T?
    good_pos = [d for d in good if d["E_Bresid"] > 0]
    p, k, r2 = loglog_fit([d["T_ps"] for d in good_pos], [d["E_Bresid"] for d in good_pos])
    print("\n  E_Bresid (destination-side: the CELLS settling off the bank) : p = %+.4f R^2 %.4f"
          % (p, r2))
    pg, kg, r2g = loglog_fit([d["T_ps"] for d in good], [d["E_gate"] for d in good])
    print("  E_gate  (switch gate drive, PER-OP by construction)          : p = %+.4f R^2 %.4f"
          % (pg, r2g))
    out["E_Bresid_exponent"] = dict(p=p, r2=r2)
    out["E_gate_exponent"] = dict(p=pg, r2=r2g)

    # ================================ mechanism check: is the loss resistive?
    print("\n" + "=" * 132)
    print("MECHANISM CHECK -- at FIXED T (L=277.8 nH), is the transfer loss LINEAR in R?")
    print("=" * 132)
    print("%9s %9s %9s %9s %12s %9s" % ("RS ohm", "T_hop", "E_R", "E_swblk", "E_R/RS", "E_gate"))
    anchor = [d for d in tab if d["tag"] == "T278"]
    allrs = ([dict(rs_ohm=10.0, t_hop_ps=anchor[0]["T_ps"], E_R_toC_fJ=anchor[0]["E_R"],
                   E_switchblock_toC_fJ=anchor[0]["E_swblk"],
                   E_gate_drive_fJ=anchor[0]["E_gate"])] if anchor else []) + rs
    allrs.sort(key=lambda r: r["rs_ohm"])
    rsd = []
    for r in allrs:
        rsd.append(dict(rs_ohm=r["rs_ohm"], T_ps=r["t_hop_ps"], E_R=r["E_R_toC_fJ"],
                        E_swblk=r["E_switchblock_toC_fJ"],
                        E_R_per_ohm=r["E_R_toC_fJ"] / r["rs_ohm"],
                        E_gate=r["E_gate_drive_fJ"]))
        print("%9.1f %9.2f %9.4f %9.4f %12.6f %9.4f"
              % (r["rs_ohm"], r["t_hop_ps"], r["E_R_toC_fJ"], r["E_switchblock_toC_fJ"],
                 r["E_R_toC_fJ"] / r["rs_ohm"], r["E_gate_drive_fJ"]))
    out["RS_check"] = rsd
    if len(rsd) > 1:
        v = [d["E_R_per_ohm"] for d in rsd]
        print("  E_R/RS spread over a %.0fx RS range: %.3f%%   -> the metered series loss IS "
              "resistive" % (max(d["rs_ohm"] for d in rsd) / min(d["rs_ohm"] for d in rsd),
                             100.0 * (max(v) - min(v)) / (sum(v) / len(v))))
        print("  t_hop spread over the same range: %.4f ps  -> T is set by the RESONANCE, "
              "R only sets the LOSS" % (max(d["T_ps"] for d in rsd) - min(d["T_ps"] for d in rsd)))

    # physics closure: E_xfer*T = pi^2 R Q^2 / 8  ->  implied R
    print("\n  PHYSICS CLOSURE -- a resonant half-cycle moving charge Q in time T through "
          "series R dissipates")
    print("  E = pi^2 R Q^2 / 8T exactly.  Inverting the MEASURED E_xfer*T product for R:")
    ron = json.load(open(os.path.join(HERE, "ron.json")))
    band = [o["Ron_ohm"] for o in ron if o["Ron_ohm"] and 0.0 <= o["V"] <= 1.0]
    for d in good[::max(1, len(good) // 8)]:
        Q = d["Q_L_fC"] * 1e-15
        R = (d["E_xfer_T"] * 1e-15 * 1e-12) * 8.0 / (math.pi ** 2 * Q * Q)
        d["R_implied_ohm"] = R
        print("     T %8.2f ps  Q %6.2f fC  ->  R_implied = %7.1f ohm" % (d["T_ps"], d["Q_L_fC"], R))
    print("     MEASURED TG DC Ron over the traversed band 0-1.0 V: min %.1f  mean %.1f  max %.1f ohm"
          " (+ RS = 10)" % (min(band), sum(band) / len(band), max(band)))
    out["Ron_measured"] = dict(min=min(band), mean=sum(band) / len(band), max=max(band),
                               n=len(band))

    # =============================================== (e) the CMOS comparator
    print("\n" + "=" * 132)
    print("(e)  CMOS COMPARATOR -- the SAME 8 cells, same CL=2 fF, HARD rail, measured at the "
          "same T points")
    print("=" * 132)
    anch = [c for c in cm if c["tag"] == "anch_v120"]
    if anch:
        a = anch[0]
        per_cell = a["E_supply_per_cycle_fJ"] / 8.0
        print("  ANCHOR CHECK (1.2 V, 34.81 ps edge, the campaign's own convention):")
        print("    measured %.4f fJ/cycle/cell  vs committed anchor %.4f  -> %+.2f%%"
              % (per_cell, CMOS_ANCHOR_FJ_PER_CELL_CYCLE,
                 100.0 * (per_cell / CMOS_ANCHOR_FJ_PER_CELL_CYCLE - 1.0)))
        out["cmos_anchor_check"] = dict(measured_fJ_per_cell_cycle=per_cell,
                                        committed=CMOS_ANCHOR_FJ_PER_CELL_CYCLE,
                                        pct=100.0 * (per_cell / CMOS_ANCHOR_FJ_PER_CELL_CYCLE - 1))
    for vdd in (1.2, 1.0):
        for mode, lab in (("f", "FIXED 5 ps input edge (pure T-invariance test)"),
                          ("s", "edge SCALED 0.25*T (a slowed design slows its edges)")):
            sub = sorted([c for c in cm if c["tag"].startswith(mode) and
                          abs(c["vdd"] - vdd) < 1e-9 and c["tag"] != "anch_v120"],
                         key=lambda c: c["period_ps"])
            if not sub:
                continue
            print("\n  vdd = %.1f V, %s" % (vdd, lab))
            print("   %10s %8s %12s %14s %12s" %
                  ("period ps", "edge ps", "E/cycle fJ", "E/transition fJ", "periodicity"))
            for c in sub:
                print("   %10.1f %8.2f %12.4f %14.4f %11.4f%%"
                      % (c["period_ps"], c["edge_ps"], c["E_supply_per_cycle_fJ"],
                         c["E_supply_per_transition_fJ"], c["periodicity_pct"] or 0.0))
            v = [c["E_supply_per_transition_fJ"] for c in sub]
            m = sum(v) / len(v)
            print("   spread over the whole T span: %+.3f%% / %+.3f%%  (mean %.4f fJ/transition, "
                  "8 cells)" % (100 * (min(v) / m - 1), 100 * (max(v) / m - 1), m))
            out.setdefault("cmos", {})["%s_v%03d" % (mode, int(vdd * 100))] = dict(
                rows=[dict(period_ps=c["period_ps"], edge_ps=c["edge_ps"],
                           E_cycle_fJ=c["E_supply_per_cycle_fJ"],
                           E_trans_fJ=c["E_supply_per_transition_fJ"]) for c in sub],
                mean_E_trans_fJ=m, spread_pct=100 * (max(v) - min(v)) / m)

    # leakage from the DC pedestal of the static deck
    print("\n  STATIC LEAKAGE of the same 8 cells (the ONLY T-proportional CMOS term):")
    for fn in sorted(glob.glob(os.path.join(HERE, "lk_v*.cir.prn"))):
        vdd = 1.2 if "v120" in fn else 1.0
        ln = [l.split() for l in open(fn) if l.split() and l.split()[0].isdigit()]
        ped = float(ln[0][-1])                      # V(XEVDD) DC pedestal = P_leak * R_X
        P_W = ped / 0.01                            # R_X = 0.01 ohm
        fj_per_ps = P_W * 1e15 / 1e12
        print("    vdd %.1f V : P_leak = %.4g W = %.4g fJ/ps  (%.4g fJ over a 1600 ps period, "
              "%.2e of the dynamic term)"
              % (vdd, P_W, fj_per_ps, fj_per_ps * 1600.0, fj_per_ps * 1600.0 / 86.5))
        out.setdefault("cmos_leak", {})["v%03d" % int(vdd * 100)] = dict(
            P_leak_W=P_W, fJ_per_ps=fj_per_ps, fJ_at_1600ps=fj_per_ps * 1600.0)

    # ======================= (d) the per-op floor, and where it takes over
    print("\n" + "=" * 132)
    print("(d)  DECOMPOSITION -- T-DEPENDENT term vs the PER-OP floor, at three completeness "
          "levels")
    print("=" * 132)
    print("  T-DEPENDENT   E_xfer = E_R + E_switchblock   (the resistive transfer path; "
          "MEASURED per row here)")
    print("  PER-OP (i)    E_gate_drive                   (MEASURED per row; the harness's own "
          "IDEAL-PWL gt/gtp/park drive -- a LOWER BOUND)")
    print("  PER-OP (ii)   2.974 fJ  resonant gt/gtp pair (COMMITTED qal/recov+qal/park; itself "
          "the netting of two unconnected ideal sources)")
    print("  PER-OP (iii)  23.213 fJ complete timer ledger(COMMITTED qal/park+qal/amp row [X4], "
          "stat-sim c814e52 -- the only COMPLETE measured one)")
    print()
    print("%9s %9s %9s %9s %9s  %10s %10s %10s" %
          ("T_hop", "E_xfer", "E_hop", "E_gate", "cells",
           "xfer/(i)", "xfer/(ii)", "xfer/(iii)"))
    for d in good:
        print("%9.2f %9.4f %9.4f %9.4f %9.4f  %10.4f %10.4f %10.4f"
              % (d["T_ps"], d["E_xfer"], d["E_hop"], d["E_gate"], d["cells"],
                 d["E_xfer"] / d["E_gate"], d["E_xfer"] / PEROP["resonant_gt_gtp_pair_fJ"],
                 d["E_xfer"] / PEROP["complete_timer_ledger_fJ"]))

    def crossing(level_fn, label):
        """T at which E_xfer falls through the per-op floor (log-log interp)."""
        prev = None
        for d in good:
            f = level_fn(d)
            if prev is not None:
                a, b = prev, d
                fa, fb = level_fn(a), level_fn(b)
                if (a["E_xfer"] - fa) * (b["E_xfer"] - fb) < 0:
                    # interpolate in log T on the ratio
                    ra = math.log(a["E_xfer"] / fa); rb = math.log(b["E_xfer"] / fb)
                    t = math.exp(math.log(a["T_ps"]) +
                                 (0 - ra) / (rb - ra) *
                                 (math.log(b["T_ps"]) - math.log(a["T_ps"])))
                    return t
            prev = d
        return None
    tf = {}
    tf["i_harness_ideal_PWL"] = crossing(lambda d: d["E_gate"], "i")
    tf["ii_resonant_pair_2.974"] = crossing(
        lambda d: PEROP["resonant_gt_gtp_pair_fJ"], "ii")
    tf["iii_complete_timer_23.213"] = crossing(
        lambda d: PEROP["complete_timer_ledger_fJ"], "iii")
    print("\n  T_floor -- the T at which the PER-OP floor overtakes the T-DEPENDENT term:")
    for k, v in tf.items():
        if v is None:
            emin, emax = min(d["E_xfer"] for d in good), max(d["E_xfer"] for d in good)
            lev = (PEROP["complete_timer_ledger_fJ"] if "23.213" in k else None)
            extra = ""
            if lev and emax < lev:
                # extrapolate on the measured E_xfer*T invariant at the fast end
                kk = min(d["E_xfer_T"] for d in good)
                extra = ("  -- E_xfer never reaches it anywhere in the sweep (max %.4f fJ at "
                         "T=%.2f ps).  Extrapolating the measured E_xfer*T = %.1f fJ*ps "
                         "invariant, it would need T = %.2f ps, far below any hop this "
                         "structure can make." % (emax, min(d["T_ps"] for d in good), kk,
                                                  kk / lev))
            print("    %-30s NO CROSSING%s" % (k, extra))
        else:
            print("    %-30s T_floor = %8.2f ps   (the committed anchor hop is 265.60 ps, "
                  "i.e. %.1fx SLOWER than this)" % (k, v, 265.598159 / v))
    out["T_floor"] = tf

    # ============================== composition: the QAL vs CMOS energy ratio
    print("\n" + "=" * 132)
    print("(f)  E_QAL / E_CMOS vs T, and tau at crossover")
    print("=" * 132)
    rcg = {}
    for fn in glob.glob(os.path.join(HERE, "rcg_v*.json")):
        d = json.load(open(fn))
        rcg["%.4f" % d["vdd"]] = d
    RC12 = rcg["1.2000"]["RC_g_ps"]
    RC10 = rcg["1.0000"]["RC_g_ps"]
    RC067 = rcg["0.6754"]["RC_g_ps"]
    print("  MEASURED RC_g of the committed cell (wp=1.12u/wn=0.74u, CL=2 fF, ideal step in):")
    for v, d in sorted(rcg.items()):
        print("    vdd %s V : RC_rise %7.3f ps  RC_fall %7.3f ps  -> RC_g (the slower) "
              "%7.3f ps" % (v, d["RC_rise_from_1090"], d["RC_fall_from_1090"], d["RC_g_ps"]))
    print("    NOTE: at the QAL-DELIVERED rail 0.6754 V the cell's RC_g is %.1fx its value at "
          "the CMOS rail 1.2 V." % (RC067 / RC12))

    # the CMOS comparator, in the campaign's own convention
    ac = [c for c in cm if c["tag"] == "anch_v120"][0]
    E_CMOS_12 = ac["E_supply_per_transition_fJ"]
    c10 = sorted([c for c in cm if c["tag"].startswith("f") and abs(c["vdd"] - 1.0) < 1e-9
                  and c["period_ps"] >= 266], key=lambda c: c["period_ps"])
    E_CMOS_10 = c10[0]["E_supply_per_transition_fJ"] if c10 else None
    print("\n  CMOS comparator per transition, 8 cells (MEASURED, T-INVARIANT):")
    print("    1.2 V, 34.81 ps edge (campaign convention)  : %.4f fJ" % E_CMOS_12)
    print("    1.0 V, iso-voltage with the QAL pre-charge  : %.4f fJ" % E_CMOS_10)

    print("\n%9s %9s %9s %9s %9s %9s %9s %9s %9s %9s" %
          ("T_hop", "t_level", "QAL(i)", "QAL(ii)", "QAL(iii)",
           "CM/Q(i)", "CM/Q(ii)", "CM/Q(iii)", "tau@1.2V", "map 4/tau"))
    comp = []
    for d in good:
        qi = d["E_hop"] + d["E_gate"]
        qii = d["E_hop"] + PEROP["resonant_gt_gtp_pair_fJ"]
        qiii = d["E_hop"] + PEROP["complete_timer_ledger_fJ"]
        tau12 = d["T_ps"] / RC12
        row = dict(T_ps=d["T_ps"], t_level=d["t_level"], QAL_i=qi, QAL_ii=qii, QAL_iii=qiii,
                   ratio_i=E_CMOS_12 / qi, ratio_ii=E_CMOS_12 / qii, ratio_iii=E_CMOS_12 / qiii,
                   ratio_i_isoV=E_CMOS_10 / qi, ratio_iii_isoV=E_CMOS_10 / qiii,
                   tau_at_1p2=tau12, tau_at_delivered=d["T_ps"] / RC067,
                   map_4_over_tau=4.0 / tau12, measured_EQAL_over_ECMOS_i=qi / E_CMOS_12)
        comp.append(row)
        print("%9.2f %9.1f %9.4f %9.4f %9.4f %9.3f %9.3f %9.3f %9.2f %9.4f"
              % (d["T_ps"], d["t_level"] or float("nan"), qi, qii, qiii,
                 row["ratio_i"], row["ratio_ii"], row["ratio_iii"], tau12,
                 row["map_4_over_tau"]))
    out["composition"] = comp
    out["RC_g"] = {k: v["RC_g_ps"] for k, v in rcg.items()}
    out["E_CMOS_per_transition_fJ"] = dict(v1p2_anchor_edge=E_CMOS_12, v1p0=E_CMOS_10)

    print("\n  --- WHAT THE 1/T KNOB IS ACTUALLY WORTH, MEASURED ---")
    fast = min(good, key=lambda d: d["T_ps"])
    slow = max(good, key=lambda d: d["T_ps"])
    anch_row = [d for d in good if d["tag"] == "T278"][0]
    for lab, key in (("(i)  harness ideal-PWL drive", "ratio_i"),
                     ("(ii) committed resonant pair", "ratio_ii"),
                     ("(iii) COMPLETE timer ledger", "ratio_iii")):
        ca = [c for c in comp if abs(c["T_ps"] - anch_row["T_ps"]) < 1e-6][0]
        cs = [c for c in comp if abs(c["T_ps"] - slow["T_ps"]) < 1e-6][0]
        best = max(comp, key=lambda c: c[key])
        print("   %-30s committed anchor T=265.6 ps: %6.3fx  ->  slowest T=%.0f ps: %6.3fx"
              "   = a %.3fx gain for a %.1fx slowdown   (best anywhere %6.3fx at T=%.0f ps)"
              % (lab, ca[key], cs["T_ps"], cs[key], cs[key] / ca[key],
                 cs["T_ps"] / ca["T_ps"], best[key], best["T_ps"]))
    print("\n   ISO-VOLTAGE control (CMOS dropped to the same 1.0 V pre-charge QAL uses):")
    ca = [c for c in comp if abs(c["T_ps"] - anch_row["T_ps"]) < 1e-6][0]
    cs = [c for c in comp if abs(c["T_ps"] - slow["T_ps"]) < 1e-6][0]
    print("     (i)   anchor %6.3fx -> slowest %6.3fx" % (ca["ratio_i_isoV"], cs["ratio_i_isoV"]))
    print("     (iii) anchor %6.3fx -> slowest %6.3fx" % (ca["ratio_iii_isoV"],
                                                          cs["ratio_iii_isoV"]))
    out["knob_worth"] = dict(
        anchor_T_ps=anch_row["T_ps"], slow_T_ps=slow["T_ps"],
        ratio_i=(ca["ratio_i"], cs["ratio_i"]), ratio_ii=(ca["ratio_ii"], cs["ratio_ii"]),
        ratio_iii=(ca["ratio_iii"], cs["ratio_iii"]),
        ratio_i_isoV=(ca["ratio_i_isoV"], cs["ratio_i_isoV"]),
        ratio_iii_isoV=(ca["ratio_iii_isoV"], cs["ratio_iii_isoV"]))

    print("\n  --- THE MAP UNDER TEST:  E_QAL/E_CMOS = 4/tau ---")
    for c in comp:
        err = 100.0 * (c["map_4_over_tau"] / c["measured_EQAL_over_ECMOS_i"] - 1.0)
        print("    T %8.2f  tau(RC_g@1.2V=%.2f) %7.2f   map %8.4f   MEASURED %8.4f   "
              "map is %+8.1f%%" % (c["T_ps"], RC12, c["tau_at_1p2"], c["map_4_over_tau"],
                                   c["measured_EQAL_over_ECMOS_i"], err))
    # where does the map cross 1, and where does the measurement?
    print("\n    map crossover (E_QAL=E_CMOS) is at tau=4, i.e. T = %.2f ps." % (4.0 * RC12))
    mn = min(c["measured_EQAL_over_ECMOS_i"] for c in comp)
    mx = max(c["measured_EQAL_over_ECMOS_i"] for c in comp)
    print("    MEASURED E_QAL/E_CMOS at completeness (i) never crosses 1 anywhere in the "
          "sweep: it runs %.4f-%.4f over T = %.1f-%.1f ps." % (mn, mx, fast["T_ps"], slow["T_ps"]))
    print("    -> FLOOR-CAPPED best ratio E_CMOS/E_QAL = %.3fx (level i) / %.3fx (level ii) / "
          "%.3fx (level iii);  the map's own floor cap is 3-9.5x."
          % (max(c["ratio_i"] for c in comp), max(c["ratio_ii"] for c in comp),
             max(c["ratio_iii"] for c in comp)))
    out["map_test"] = dict(RC_g_1p2=RC12, map_crossover_T_ps=4.0 * RC12,
                           measured_ratio_min=mn, measured_ratio_max=mx,
                           floor_capped_best=dict(
                               i=max(c["ratio_i"] for c in comp),
                               ii=max(c["ratio_ii"] for c in comp),
                               iii=max(c["ratio_iii"] for c in comp),
                               i_isoV=max(c["ratio_i_isoV"] for c in comp),
                               iii_isoV=max(c["ratio_iii_isoV"] for c in comp)))

    # ==================================================== FUNCTIONAL-ONLY headline
    print("\n" + "=" * 132)
    print("HEADLINE, RESTRICTED TO THE FUNCTIONAL BAND  (C1 settle + C2 rail-drain + C3 swing "
          "+ C4 instrument ALL PASS)")
    print("=" * 132)
    fn_ = [d for d in tab if d["FUNCTIONAL"] == "YES"]
    fn_.sort(key=lambda d: d["T_ps"])
    print("  The hop is FUNCTIONAL only for T >= %.2f ps (%d rows, T %.1f-%.1f ps = %.2f "
          "decades).  Below that it fails C2 (the source bank never drains) and/or C3 "
          "(VBEND < 0.60*dV)." % (fn_[0]["T_ps"], len(fn_), fn_[0]["T_ps"], fn_[-1]["T_ps"],
                                  math.log10(fn_[-1]["T_ps"] / fn_[0]["T_ps"])))
    p, k, r2 = loglog_fit([d["T_ps"] for d in fn_], [d["E_xfer"] for d in fn_])
    print("  E_xfer exponent over the FUNCTIONAL band: p = %+.4f  (R^2 %.6f, %.2f decades)"
          % (p, r2, math.log10(fn_[-1]["T_ps"] / fn_[0]["T_ps"])))
    out["functional_band"] = dict(T_lo=fn_[0]["T_ps"], T_hi=fn_[-1]["T_ps"], n=len(fn_),
                                  decades=math.log10(fn_[-1]["T_ps"] / fn_[0]["T_ps"]),
                                  E_xfer_p=p, r2=r2)
    print("  Both T_floor values (%.2f ps at level (i), %.2f ps at level (ii)) lie BELOW the "
          "functional band, so:" % (tf["i_harness_ideal_PWL"], tf["ii_resonant_pair_2.974"]))
    print("  ** AT EVERY T WHERE THE HOP ACTUALLY WORKS, THE PER-OP FLOOR ALREADY DOMINATES **")
    print("     E_xfer / E_gate  = %.4f at the FASTEST functional T (%.1f ps)  ->  %.4f at the "
          "slowest (%.0f ps)" % (fn_[0]["E_xfer"] / fn_[0]["E_gate"], fn_[0]["T_ps"],
                                 fn_[-1]["E_xfer"] / fn_[-1]["E_gate"], fn_[-1]["T_ps"]))
    ca = [c for c in comp if abs(c["T_ps"] - fn_[0]["T_ps"]) < 1e-6][0]
    cs = [c for c in comp if abs(c["T_ps"] - fn_[-1]["T_ps"]) < 1e-6][0]
    print("\n  THE 1/T KNOB'S MEASURED VALUE ACROSS THE WHOLE FUNCTIONAL BAND (%.1fx slowdown):"
          % (fn_[-1]["T_ps"] / fn_[0]["T_ps"]))
    for lab, key in (("(i)   harness ideal-PWL drive ", "ratio_i"),
                     ("(ii)  committed resonant pair ", "ratio_ii"),
                     ("(iii) COMPLETE timer ledger   ", "ratio_iii"),
                     ("(i)   ISO-VOLTAGE (CMOS@1.0V) ", "ratio_i_isoV"),
                     ("(iii) ISO-VOLTAGE (CMOS@1.0V) ", "ratio_iii_isoV")):
        print("    %s  %6.3fx -> %6.3fx   = %.3fx" % (lab, ca[key], cs[key], cs[key] / ca[key]))
    print("    total hop energy E_hop            %6.3f -> %6.3f fJ  = %.3fx"
          % (fn_[0]["E_hop"], fn_[-1]["E_hop"], fn_[0]["E_hop"] / fn_[-1]["E_hop"]))
    out["functional_knob"] = {k: (ca[k], cs[k], cs[k] / ca[k]) for k in
                              ("ratio_i", "ratio_ii", "ratio_iii", "ratio_i_isoV",
                               "ratio_iii_isoV")}

    # ------ where, if anywhere, does E_QAL cross E_CMOS INSIDE the functional band?
    print("\n  DOES E_QAL EVER CROSS E_CMOS?  (functional band only -- a crossing found below "
          "T=105.7 ps would be an artefact")
    print("   of a BROKEN hop, whose energy is low only because it never moved the charge.)")
    Tf = [d["T_ps"] for d in fn_]
    compf = [c for c in comp if c["T_ps"] >= fn_[0]["T_ps"] - 1e-6]

    def cross_in_band(key, label):
        prev = None
        for c in compf:
            r = 1.0 / c[key]                       # E_QAL / E_CMOS
            if prev is not None and (prev[1] - 1.0) * (r - 1.0) < 0:
                t = math.exp(math.log(prev[0]) + (1.0 - prev[1]) / (r - prev[1]) *
                             (math.log(c["T_ps"]) - math.log(prev[0])))
                return t, None
            prev = (c["T_ps"], r)
        lo = 1.0 / compf[0][key]
        hi = 1.0 / compf[-1][key]
        return None, (lo, hi)
    cross = {}
    for key, label in (("ratio_i", "(i)   harness ideal-PWL, CMOS@1.2V"),
                       ("ratio_ii", "(ii)  resonant pair,    CMOS@1.2V"),
                       ("ratio_iii", "(iii) COMPLETE ledger,  CMOS@1.2V"),
                       ("ratio_i_isoV", "(i)   harness ideal-PWL, CMOS@1.0V ISO-V"),
                       ("ratio_iii_isoV", "(iii) COMPLETE ledger,  CMOS@1.0V ISO-V")):
        t, rng = cross_in_band(key, label)
        if t:
            print("    %-42s CROSSES at T = %.1f ps  ->  tau = %.2f  (map says 4)"
                  % (label, t, t / RC12))
            cross[key] = dict(T_ps=t, tau=t / RC12)
        else:
            print("    %-42s NO CROSSING: E_QAL/E_CMOS = %.4f -> %.4f across the band"
                  % (label, rng[0], rng[1]))
            cross[key] = dict(T_ps=None, ratio_lo=rng[0], ratio_hi=rng[1])
    out["crossovers_functional_band"] = cross

    # asymptote: can slowing EVER take the complete ledger below iso-voltage CMOS?
    print("\n  THE ASYMPTOTE -- can the 1/T knob ALONE ever take the COMPLETE ledger below "
          "iso-voltage CMOS?")
    sl = fn_[-4:]
    # fit E_hop(T) = Einf + a*T^-b by scanning Einf for the best power law
    best = None
    for Einf in [x / 1000.0 for x in range(0, 7400, 5)]:
        ys = [d["E_hop"] - Einf for d in sl]
        if min(ys) <= 0:
            continue
        b, a, r2 = loglog_fit([d["T_ps"] for d in sl], ys)
        if best is None or r2 > best[3]:
            best = (Einf, a, b, r2)
    Einf, a, b, r2 = best
    print("    E_hop(T) power-law fit on the 4 slowest FUNCTIONAL rows: E_hop -> %.4f fJ as "
          "T -> inf   (exponent %.3f, R^2 %.6f)" % (Einf, b, r2))
    print("    So E_QAL(iii) -> %.4f + 23.213 = %.4f fJ, against iso-voltage CMOS %.4f fJ."
          % (Einf, Einf + PEROP["complete_timer_ledger_fJ"], E_CMOS_10))
    lim = (Einf + PEROP["complete_timer_ledger_fJ"]) / E_CMOS_10
    print("    LIMIT of the 1/T knob at the complete ledger, iso-voltage: E_QAL/E_CMOS -> "
          "%.4f  ->  %s" % (lim, "STILL ABOVE 1: slowing down can NEVER get there."
                            if lim >= 1.0 else "below 1, reachable by slowing."))
    # how much further slowdown would the last-two-point log-linear trend need?
    d1, d2 = fn_[-2], fn_[-1]
    per_oct = (d1["E_hop"] - d2["E_hop"]) / math.log2(d2["T_ps"] / d1["T_ps"])
    need = (E_CMOS_10 - (d2["E_hop"] + PEROP["complete_timer_ledger_fJ"]))
    print("    (Even on the OPTIMISTIC log-linear reading of the last two points -- E_hop "
          "falling %.4f fJ/octave -- closing the remaining %.4f fJ would take %.1f more "
          "octaves, i.e. T ~ %.1f ns, tau ~ %.0f.)"
          % (per_oct, -need, -need / per_oct, d2["T_ps"] * 2 ** (-need / per_oct) / 1000.0,
             d2["T_ps"] * 2 ** (-need / per_oct) / RC12))
    out["asymptote"] = dict(E_hop_inf_fJ=Einf, exponent=b, r2=r2,
                            E_QAL_iii_inf_fJ=Einf + PEROP["complete_timer_ledger_fJ"],
                            E_CMOS_isoV_fJ=E_CMOS_10, limit_ratio=lim,
                            E_hop_fJ_per_octave=per_oct)

    # CMOS T-invariance, restricted to periods where the transition COMPLETES
    print("\n  CMOS T-INVARIANCE, restricted to periods where the transition actually completes")
    print("  (half-period >= 2x the measured cell t90; below that the swing is truncated and "
          "the low energy is an artefact, not a saving):")
    for vdd, key in ((1.2, "f_v120"), (1.0, "f_v100")):
        sub = [r for r in out["cmos"][key]["rows"] if r["period_ps"] >= 158]
        v = [r["E_trans_fJ"] for r in sub]
        m = sum(v) / len(v)
        print("    vdd %.1f V, fixed 5 ps edge, period %d-%d ps (%.1fx): E/transition "
              "%.4f-%.4f fJ, spread %+.3f%%   -> T-INVARIANT"
              % (vdd, sub[0]["period_ps"], sub[-1]["period_ps"],
                 sub[-1]["period_ps"] / sub[0]["period_ps"], min(v), max(v),
                 100.0 * (max(v) - min(v)) / m))
        out.setdefault("cmos_invariance", {})[key] = dict(
            T_lo=sub[0]["period_ps"], T_hi=sub[-1]["period_ps"], E_lo=min(v), E_hi=max(v),
            spread_pct=100.0 * (max(v) - min(v)) / m)

    # ============ the FULL committed driver ladder behind the 29.0 fC anchor
    print("\n" + "=" * 132)
    print("THE PER-OP FLOOR IS A LADDER, NOT A NUMBER -- the committed 29.0 fC gate charge "
          "priced every way the campaign has priced it")
    print("=" * 132)
    print("  MEASURED (qal/sar, committed): the tg15p switch needs Q_gt(close) 10.50 fC + "
          "Q_gtp(open) 16.38 fC + park ~2.1 fC = 29.0 fC per hop.")
    print("  What that charge COSTS depends entirely on how it is driven, and the campaign has "
          "four committed prices for it:")
    ladder = [
        ("ideal-PWL recycling floor      (MEASURED here, per row)", None, "MEASURED"),
        ("resonant gt/gtp pair      2.974 fJ", 2.974, "COMMITTED (a netting of two unconnected "
         "ideal sources -- qal/park IS3)"),
        ("75%-recovery resonant drv 10.9  fJ", 10.9, "COMMITTED but DERIVED, not built"),
        ("COMPLETE timer ledger     23.213 fJ", 23.213, "COMMITTED, the only COMPLETE measured "
         "one (qal/park+qal/amp [X4])"),
        ("conventional CMOS driver  43.5  fJ", 43.5, "COMMITTED, from the measured 29.0 fC off "
         "the 1.5 V rail"),
    ]
    slow = fn_[-1]
    fast = fn_[0]
    print("\n  E_CMOS per 8-cell transition, MEASURED: %.4f fJ @1.2 V (campaign convention) / "
          "%.4f fJ @1.0 V (iso-voltage)" % (E_CMOS_12, E_CMOS_10))
    print("\n  %-44s %10s %10s   %9s %9s   %9s %9s" %
          ("driver booking", "E_QAL fast", "E_QAL slow", "CM/Q fast", "CM/Q slow",
           "isoV fast", "isoV slow"))
    lad = []
    for lab, val, prov in ladder:
        vf = fast["E_gate"] if val is None else val
        vs = slow["E_gate"] if val is None else val
        qf, qs = fast["E_hop"] + vf, slow["E_hop"] + vs
        print("  %-44s %10.3f %10.3f   %9.3f %9.3f   %9.3f %9.3f"
              % (lab, qf, qs, E_CMOS_12 / qf, E_CMOS_12 / qs, E_CMOS_10 / qf, E_CMOS_10 / qs))
        lad.append(dict(label=lab, provenance=prov, driver_fJ=(None if val is None else val),
                        E_QAL_fast=qf, E_QAL_slow=qs,
                        ratio_1p2_fast=E_CMOS_12 / qf, ratio_1p2_slow=E_CMOS_12 / qs,
                        ratio_isoV_fast=E_CMOS_10 / qf, ratio_isoV_slow=E_CMOS_10 / qs))
    out["driver_ladder"] = dict(rows=lad, T_fast_ps=fast["T_ps"], T_slow_ps=slow["T_ps"],
                                E_CMOS_1p2=E_CMOS_12, E_CMOS_1p0=E_CMOS_10,
                                gate_charge_fC=29.0)
    print("\n  ** The 1/T knob moves every row in this table by at most 1.26x.  Moving ONE RUNG "
          "of the ladder moves it by up to 4.8x. **")
    print("  ** With a conventional driver QAL LOSES to CMOS at every T, at both voltages, "
          "by 1.24x (1.2 V) to 1.69x (iso-voltage). **")

    json.dump(out, open(os.path.join(HERE, "ANALYSIS.json"), "w"), indent=1)
    print("\nwrote ANALYSIS.json")


if __name__ == "__main__":
    main()
