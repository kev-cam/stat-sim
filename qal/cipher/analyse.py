#!/usr/bin/env python3
"""PHASE 1 analysis.  Reads only this run's own row_*.json / M8_*.json and the
PDK figures in WIRE_MODEL.json.  Nothing is re-simulated.

THE HEADLINE METRIC AND WHY IT IS A DIFFERENCE
----------------------------------------------
The convention-free statement of what a capacitor costs in this topology is what
the TANKS permanently gave up, because a tank is a LINEAR capacitor and
1/2 C (V0^2 - V1^2) needs no integrator and no sign convention:

    E_tank_lost = sum_k 1/2 C_t(k) (V_tnk(t0)^2 - V_tnk(return-open)^2)

and the cost of the wire is the DIFFERENCE between two decks that are identical
apart from one capacitor:

    dE_QAL = E_tank_lost(Cw) - E_tank_lost(0)

Every fixed overhead -- the cells' own load, the gate drives, the switch loss,
the baseline tank loss -- cancels exactly.

The CMOS comparator on the SAME capacitance at the SAME measured swing is
likewise taken as a difference of two real decks (M8_CMOS_cw2400 - M8_CMOS_cw0),
which reproduces n*Cw*V^2 to 0.4-0.6 % and so validates the harness.

TWO BOUNDS, because charge left on a node is not the same as charge burnt:
    dE_QAL                        stranded charge treated as DISSIPATED  (worst)
    dE_QAL - E_wire_stranded_end  stranded charge treated as REUSED      (best)
"""
import glob, json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
BTK = os.path.join(HERE, "btk")


def load_rows():
    rows = {}
    for f in sorted(glob.glob(os.path.join(BTK, "row_m10_T150_H4_dv1650_free_*.json"))):
        d = json.load(open(f))
        if "wire_mode" not in d:
            continue
        rows["%s/%s/%.3f" % (d["wire_mode"], d["ct_mode"], d["cw_fF"])] = d
    return rows


def load_m8():
    out = {}
    for f in sorted(glob.glob(os.path.join(BTK, "M8_*.json"))):
        d = json.load(open(f))
        if d["kind"] == "QAL8":
            k = "Q|%s|%.3f|%.2f" % (d["place"], d["cw_fF"], d["ct_fF"])
            if d.get("L_nH", 15.0) != 15.0:
                k += "|L%.0f" % (d["L_nH"] * 10)
            if d.get("wp_scale", 1.0) != 1.0:
                k += "|wx%.0f" % (d["wp_scale"] * 10)
            out[k] = d
        else:
            out["C|%.3f|%.4f" % (d["cw_fF"], d["vdd"])] = d
    return out


def main():
    W = json.load(open(os.path.join(HERE, "WIRE_MODEL.json")))
    SC = json.load(open(os.path.join(HERE, "SCORE.json")))
    rows, m8 = load_rows(), load_m8()
    base = rows["none/fixed/0.000"]
    R = {"_what": "qal/cipher PHASE 1 results", "wire_model": W["layers"]["Metal2"],
         "rotate_geometry": W["rotate_geometry"]}

    # ------------------------------------------------------- the chain table
    order = ["none/fixed/0.000", "signal/fixed/2.400", "rail/fixed/2.400",
             "signal/matched/2.400", "rail/matched/2.400", "pi/matched/2.400",
             "signal/matched/1.488", "signal/matched/3.489",
             "signal/matched/9.216"]
    tab = {}
    print("=" * 150)
    print("(d) THE COMMITTED 8-GATE-PER-BANK CHAIN, 4 BANKS, m=10 T=150 H=4 dV=1.65, "
          "WITH AND WITHOUT AN EXPLICIT 32-BIT-ROTATE WIRE LOAD")
    print("=" * 150)
    hdr = ("%-24s %6s %7s %7s %7s | %7s %7s %7s | %6s %6s %6s %6s | %6s %5s %6s"
           % ("config", "Cw_fF", "Etank", "dE_QAL", "dE_best", "Ewire_pk",
              "E_str", "CMOSref", "railmn", "worst%", "stage", "thop2",
              "S3", "G2", "Tarea"))
    print(hdr)
    for key in order:
        d = rows[key]
        dE = d["E_tank_lost_chain_fJ"] - base["E_tank_lost_chain_fJ"]
        est = d.get("E_wire_stranded_end_chain_fJ", 0.0)
        ref = d.get("E_CMOS_reference_same_wire_fJ", 0.0)
        deck = os.path.splitext(d["deck"])[0]
        s3 = SC["rows"][deck]["S3_pass"] if deck in SC["rows"] else None
        n3 = SC["rows"][deck]["n_gates"] if deck in SC["rows"] else None
        e = dict(
            cw_fF=d["cw_fF"], wire_mode=d["wire_mode"], ct_mode=d["ct_mode"],
            E_tank_lost_chain_fJ=d["E_tank_lost_chain_fJ"],
            dE_QAL_worst_fJ=dE, dE_QAL_best_fJ=dE - est,
            E_wire_stored_peak_fJ=d.get("E_wire_stored_peak_chain_fJ", 0.0),
            E_wire_stranded_end_fJ=est, E_CMOS_reference_fJ=ref,
            net_cost_over_wire_stored_energy=(dE / d["E_wire_stored_peak_chain_fJ"])
            if d.get("E_wire_stored_peak_chain_fJ") else None,
            CMOS_cost_over_wire_stored_energy=2.0,
            ratio_CMOS_over_QAL_worst=(ref / dE) if dE else None,
            ratio_CMOS_over_QAL_best=(ref / (dE - est)) if (dE - est) > 0 else None,
            best_case_credit_exceeds_cost=bool((dE - est) <= 0),
            rail_min_V=d["rail_min_V"], rail_at_boundary_V=d["rail_at_own_boundary_V"],
            rail_end_V=None,
            G7_level_restoring=d["G7_level_restoring_pass"],
            worst_gate_pct=d["worst_gate_pct"],
            committed_90_bar_pass=d["A1_settling_pass_90"],
            value_check_pass=d["A2_value_pass"],
            separation_min_mV=d["separation_min_mV"],
            fcrit_S3_pass=s3, fcrit_S3_of=n3,
            fcrit_S3_row_pass=(SC["rows"][deck]["ROW_S3"] if deck in SC["rows"] else None),
            fcrit_worst_S3_margin_mV=(SC["rows"][deck]["worst_S3_margin_mV"]
                                      if deck in SC["rows"] else None),
            stage_time_deepest_ps=d["stage_time_deepest_ps"],
            t_hop_rise_ps=d["t_hop_measured_rise_ps"],
            t_hop_return_ps=d["t_hop_measured_return_ps"],
            tank_area_um2=d["tank_area_um2_per_chain_MIM"],
            C_tank_fF=d["C_tank_fF"], m_effective=d["m_effective"],
            G2_zcs_pass=d["G2_zcs_pass"], G3_path_identity_pass=d["G3_path_identity_pass"],
            IZ_uA=d["IZ_uA"], IZQ_uA=d["IZQ_uA"])
        # incremental recycle fraction of the wire charge, per bank and total
        inc_in = inc_bk = 0.0
        per = {}
        for k in d["energy_per_bank"]:
            a, b = d["energy_per_bank"][k], base["energy_per_bank"][k]
            di = a["E_into_rail_rise_fJ"] - b["E_into_rail_rise_fJ"]
            db = a["E_back_into_tank_return_fJ"] - b["E_back_into_tank_return_fJ"]
            inc_in += di
            inc_bk += db
            per[k] = dict(d_into_rail_fJ=di, d_back_into_tank_fJ=db,
                          incremental_recycle_pct=(100.0 * db / di) if di else None,
                          baseline_recycle_pct=b["recycle_fraction_pct"],
                          loaded_recycle_pct=a["recycle_fraction_pct"])
        e["incremental_per_bank"] = per
        e["d_into_rail_chain_fJ"] = inc_in
        e["d_back_into_tank_chain_fJ"] = inc_bk
        e["incremental_recycle_pct_chain"] = (100.0 * inc_bk / inc_in) if inc_in else None
        tab[key] = e
        print("%-24s %6.3f %7.3f %7.3f %7.3f | %7.3f %7.3f %7.3f | %6.4f %6.2f "
              "%6.2f %6.2f | %2s/%-2s %5s %6.0f"
              % (key, d["cw_fF"], d["E_tank_lost_chain_fJ"], dE, dE - est,
                 e["E_wire_stored_peak_fJ"], est, ref, d["rail_min_V"],
                 d["worst_gate_pct"], d["stage_time_deepest_ps"] or -1,
                 d["t_hop_measured_return_ps"]["2"], s3, n3,
                 "PASS" if d["G2_zcs_pass"] else "FAIL", d["tank_area_um2_per_chain_MIM"]))
    R["chain"] = tab

    print()
    print("ratios (CMOS same-wire same-swing / QAL incremental):")
    for key in order[1:]:
        e = tab[key]
        bc = e["ratio_CMOS_over_QAL_best"]
        print("  %-24s PRIMARY %6.3fx   (stranded-credit bound %s)   "
              "net cost / wire stored energy %6.3f  (CMOS = 2.000)   "
              "incremental recycle into the tank %s"
              % (key, e["ratio_CMOS_over_QAL_worst"],
                 ("%6.3fx" % bc) if bc else "unbounded",
                 e["net_cost_over_wire_stored_energy"],
                 ("%7.2f %%" % e["incremental_recycle_pct_chain"])
                 if e["incremental_recycle_pct_chain"] is not None else "n/a"))

    # ---------------------------------------------------- (e) the micro table
    print()
    print("=" * 150)
    print("(e) THE DECISIVE COMPARISON -- ONE HOP OF THE COMMITTED 8-CELL BANK, "
          "SAME CELLS / SAME LOAD / SAME EDGES / SAME MODELS, QAL vs CMOS")
    print("=" * 150)
    q0 = m8["Q|none|0.000|359.79"]
    print("CMOS harness validation (measured incremental supply energy vs n*Cw*V^2, "
          "n = 3 swinging nodes, Cw = 2.400 fF):")
    cm = {}
    for vdd in sorted(set(float(k.split("|")[2]) for k in m8 if k.startswith("C|"))):
        a = m8["C|0.000|%.4f" % vdd]
        b = m8["C|2.400|%.4f" % vdd]
        dE = b["E_supply_cycle_fJ"] - a["E_supply_cycle_fJ"]
        txt = 3.0 * 2.400 * vdd * vdd / 1.0
        cm[vdd] = dict(E_cw0_fJ=a["E_supply_cycle_fJ"], E_cw2400_fJ=b["E_supply_cycle_fJ"],
                       dE_CMOS_fJ=dE, nCV2_fJ=txt, ratio_to_nCV2=dE / txt,
                       integrator_vs_QV_residual_fJ=b["E_integrator_vs_QV_residual_fJ"])
        print("   VDD %.4f V   E(cw0) %7.4f   E(cw2.4) %7.4f   dE %7.4f fJ   "
              "n*Cw*V^2 %7.4f fJ   ratio %.4f   integrator-vs-QV residual %.2e fJ"
              % (vdd, a["E_supply_cycle_fJ"], b["E_supply_cycle_fJ"], dE, txt,
                 dE / txt, b["E_integrator_vs_QV_residual_fJ"]))
    R["cmos_validation"] = cm

    print()
    print("%-34s %8s %8s %8s %8s | %8s %9s %9s %9s"
          % ("QAL variant", "Ct_fF", "Etank", "dE_QAL", "E_str", "swing_pk",
             "dE_CMOS", "RATIO_wc", "RATIO_bc"))
    mic = {}
    for key in ["Q|node|2.400|359.79", "Q|rail|2.400|359.79",
                "Q|node|2.400|431.79", "Q|rail|2.400|431.79"]:
        d = m8[key]
        dE = d["E_tank_lost_cycle_fJ"] - q0["E_tank_lost_cycle_fJ"]
        est = d["E_wire_stranded_end_fJ"]
        sw = d["V_node_peak_mean_swinging"]
        # voltage-matched CMOS comparator (gate G9): pick the measured VDD row
        # closest to this variant's own measured swing peak
        vdd = min(cm, key=lambda v: abs(v - sw))
        dC = cm[vdd]["dE_CMOS_fJ"] * (sw * sw) / (vdd * vdd)   # tiny V^2 trim
        mic[key] = dict(
            place=d["place"], ct_fF=d["ct_fF"], cw_fF=d["cw_fF"],
            E_tank_lost_cycle_fJ=d["E_tank_lost_cycle_fJ"], dE_QAL_worst_fJ=dE,
            dE_QAL_best_fJ=dE - est, E_wire_stored_peak_fJ=d["E_wire_stored_peak_fJ"],
            E_wire_stranded_end_fJ=est, swing_peak_V=sw,
            node_end_V=d["V_node_end_mean_swinging"],
            rail_peak_V=d["V_rail_peak"], rail_end_V=d["V_rail_end"],
            cmos_vdd_used_V=vdd, dE_CMOS_fJ=dC,
            net_cost_over_wire_stored_energy=dE / d["E_wire_stored_peak_fJ"]
            if d["E_wire_stored_peak_fJ"] else None,
            ratio_worst=dC / dE if dE else None,
            ratio_best=dC / (dE - est) if (dE - est) > 0 else None,
            best_case_credit_exceeds_cost=bool((dE - est) <= 0),
            recycle_fraction_pct=d["recycle_fraction_pct"],
            t_hop_rise_ps=d["tzr"], t_hop_return_ps=d["tzq"],
            IZ_uA=d["IZ_uA"], IZQ_uA=d["IZQ_uA"],
            path_identity_rise_fJ=d["path_identity_rise_fJ"])
        print("%-34s %8.2f %8.4f %8.4f %8.4f | %8.4f %9.4f %9.3f %9s"
              % (key, d["ct_fF"], d["E_tank_lost_cycle_fJ"], dE, est, sw, dC,
                 dC / dE,
                 ("%.3f" % (dC / (dE - est))) if (dE - est) > 0 else "unbounded"))
    R["micro"] = mic
    # ------------------------------------------- MECHANISM PROBES (labelled)
    print()
    print("MECHANISM PROBES (single hop, fixed tank, signal wire on the node).  "
          "Each departs from the committed point in ONE stated way and is NOT a "
          "scored row.")
    print("%-40s %7s %7s %8s %8s %8s %8s %8s %8s"
          % ("probe", "L_nH", "wp_um", "t_hop", "Etank0", "Etank_w", "dE_QAL",
             "net/Epk", "RATIO"))
    probes = {}
    for nm, b0, b1 in (
            ("committed  L=15 nH, wp=1.12 um",
             "Q|none|0.000|359.79", "Q|node|2.400|359.79"),
            ("SLOWER RAMP  L=60 nH (t_hop x2.07)",
             "Q|none|0.000|359.79|L600", "Q|node|2.400|359.79|L600"),
            ("WIDER PULL-UP  wp=4.48 um (4x)",
             "Q|none|0.000|359.79|wx40", "Q|node|2.400|359.79|wx40")):
        if b0 not in m8 or b1 not in m8:
            continue
        a, b = m8[b0], m8[b1]
        dE = b["E_tank_lost_cycle_fJ"] - a["E_tank_lost_cycle_fJ"]
        epk = b["E_wire_stored_peak_fJ"]
        ratio = 2.0 * epk / dE if dE else None
        probes[nm] = dict(
            L_nH=b.get("L_nH", 15.0), wp_um=b.get("wp_um", 1.12),
            t_hop_rise_ps=b["tzr"], E_tank_lost_cw0_fJ=a["E_tank_lost_cycle_fJ"],
            E_tank_lost_cw2400_fJ=b["E_tank_lost_cycle_fJ"], dE_QAL_fJ=dE,
            E_wire_stored_peak_fJ=epk, node_peak_V=b["V_node_peak_mean_swinging"],
            node_end_V=b["V_node_end_mean_swinging"], rail_peak_V=b["V_rail_peak"],
            net_cost_over_wire_stored_energy=dE / epk if epk else None,
            ratio_CMOS_over_QAL=ratio,
            recycle_pct_cw0=a["recycle_fraction_pct"],
            recycle_pct_cw2400=b["recycle_fraction_pct"])
        print("%-40s %7.1f %7.2f %8.2f %8.4f %8.4f %8.4f %8.3f %8.3f"
              % (nm, probes[nm]["L_nH"], probes[nm]["wp_um"], b["tzr"],
                 a["E_tank_lost_cycle_fJ"], b["E_tank_lost_cycle_fJ"], dE,
                 dE / epk, ratio))
    R["mechanism_probes"] = probes
    print("   the CMOS comparator for a probe row is 2.000 x its own measured "
          "wire stored energy, which the CMOS decks reproduce to 0.4-0.6 %.")

    R["micro_baseline"] = dict(
        E_tank_lost_cycle_fJ=q0["E_tank_lost_cycle_fJ"],
        rail_peak_V=q0["V_rail_peak"], rail_end_V=q0["V_rail_end"],
        node_peak_V=q0["V_node_peak_mean_swinging"],
        node_end_V=q0["V_node_end_mean_swinging"],
        recycle_fraction_pct=q0["recycle_fraction_pct"],
        IZ_uA=q0["IZ_uA"], IZQ_uA=q0["IZQ_uA"])

    # ------------------------------------------------------- derived context
    CB, CT, L, Rs = 35.979e-15, 359.79e-15, 15e-9, 10.0
    ce = CT * CB / (CT + CB)
    R["loop_quality_reference"] = dict(
        C_eff_fF=ce * 1e15, Z0_ohm=math.sqrt(L / ce), R_ohm=Rs,
        adiabatic_ratio_2_over_pi_Z0_over_R=(2 / math.pi) * math.sqrt(L / ce) / Rs,
        note="the ratio an IDEAL series-LCR charge transfer would give on a "
             "capacitance INSIDE the loop; the measured rail-wire ratio is the "
             "fraction of it that survives real devices, and the measured "
             "signal-wire ratio is what is left once the wire sits behind the "
             "cell's own pull-up device")
    json.dump(R, open(os.path.join(HERE, "ANALYSIS.json"), "w"), indent=1,
              default=str)
    print()
    print("ideal series-LCR reference on a capacitance INSIDE the loop: "
          "(2/pi)*sqrt(L/Ceff)/R = %.2fx   (Ceff %.3f fF, Z0 %.0f ohm, R %g ohm)"
          % (R["loop_quality_reference"]["adiabatic_ratio_2_over_pi_Z0_over_R"],
             ce * 1e15, math.sqrt(L / ce), Rs))
    print("wrote ANALYSIS.json")


if __name__ == "__main__":
    main()
