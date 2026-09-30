#!/usr/bin/env python3
"""Assemble RESULTS.json for qal/widebank PHASE 1.  Nothing here simulates."""
import glob, json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import wbx

CMOS_BLK, CMOS_INV, CMOS_LVL = 4.14, 10.0831, 92.8
FLOOR = "idealPWL_floor_MEASURED__timer0_BOUND"
FLOORT = "idealPWL_floor_MEASURED__timer_floor_ASSUMED_3p5227"
CONV = "conventional_from_own_measured_charge__timer0_BOUND"
CONVT = "conventional_from_own_measured_charge__timer_floor_ASSUMED_3p5227"


def load():
    out = []
    for f in sorted(glob.glob(os.path.join(HERE, "row_n*.json"))):
        d = json.load(open(f))
        d["_file"] = os.path.basename(f)
        d["_tag"] = os.path.basename(f)[4:-5]
        out.append(d)
    return out


def brief(d):
    e = d["energy_per_bank"]["2"]
    L = d["LEDGER"]
    R = L["rows"]
    A2 = d["A2_functional"] or {}
    n = d["N"]
    return dict(
        tag=d["_tag"], N=n, wmul=d["wmul"], W_nominal_um=d["W_nominal_um"],
        T_ps=d["T_ps"], nb=d["nb"], mstep_ps=d["mstep_ps"],
        # --- gates
        A1_value_all_gates=d["A1_value_all_banks_pass"],
        A1_fail_count=d["A1_value_fail_count"],
        A2_functional_bare=A2.get("PASS_bare"),
        A2_margin_min_mV=A2.get("margin_min_mV"),
        A2_pass_3sigma_continuity_only=A2.get("PASS_3sigma_CONTINUITY_ONLY"),
        A3_settle90=d["A3_settling_pass_90"], worst_gate_pct=d["worst_gate_pct"],
        A4_zcs=d["A4_zcs_pass"],
        A4_worst_residual_uA=max(max(abs(v) for v in d["IZ_uA"].values()),
                                 max(abs(v) for v in d["IZQ_uA"].values())),
        A4_residual_energy_fJ=0.5 * 15e-9
        * (1e-6 * max(max(abs(v) for v in d["IZ_uA"].values()),
                      max(abs(v) for v in d["IZQ_uA"].values()))) ** 2 * 1e15,
        A5_path_identity=d["A5_path_identity_pass"],
        A6_tank_closure=d["A6_tank_closure_pass"],
        A9_C_ratio=d["A9_C_bank_ratio_measured_over_derived"],
        ACCEPTED=bool(d["A1_value_all_banks_pass"] and A2.get("PASS_bare")
                      and d["A4_zcs_pass"] and d["A5_path_identity_pass"]
                      and d["A6_tank_closure_pass"]),
        # --- time
        t_hop_rise_ps=d["t_hop_rise_ps"], t_hop_return_ps=d["t_hop_return_ps"],
        t_settle90_from_rail_start_ps=d["LEVEL_TIME_measured_bank2_ps"],
        t_settle_functional_ps=d["LEVEL_TIME_measured_functional_bank2_ps"],
        level_time_ps=d["T_ps"], x_CMOS_level=d["T_ps"] / CMOS_LVL,
        gates_per_ps=n / d["T_ps"],
        # --- current / switch
        I_pk_uA=d["IPK_uA"]["2"],
        Q_gate_MEASURED_fC=L["Q_gate_MEASURED_fC"],
        Q_gate_MEASURED_per_um=L["Q_gate_MEASURED_per_um"],
        Q_gate_lsweep_fit_fC=L["Q_gate_DERIVED_lsweep_fC"],
        Q_gate_measured_over_fit=L["Q_gate_MEASURED_fC"]
        / L["Q_gate_DERIVED_lsweep_fC"],
        # --- energy terms
        E_tank_loss_fJ=L["E_tank_loss_fJ"],
        E_tank_loss_per_gate_fJ=L["E_tank_loss_fJ"] / n,
        E_switch_conduction_fJ=e["E_switchblock_rise_fJ"],
        E_switch_conduction_per_gate_fJ=e["E_switchblock_rise_fJ"] / n,
        E_seriesR_fJ=e["E_seriesR_rise_fJ"],
        E_seriesR_per_gate_fJ=e["E_seriesR_rise_fJ"] / n,
        E_park_path_fJ=e["E_out_of_tank_via_park_cycle_fJ"],
        E_park_path_per_gate_fJ=e["E_out_of_tank_via_park_cycle_fJ"] / n,
        resonant_share_of_tank_loss_pct=L["E_resonant_share_of_tank_loss_pct"],
        recycle_fraction_pct=e["recycle_fraction_pct"],
        E_out_of_tank_rise_fJ=e["E_out_of_tank_rise_fJ"],
        E_gate_drive_idealPWL_per_bank_fJ=L["E_gate_drive_idealPWL_per_bank_fJ"],
        E_gate_drive_conventional_fJ=L["E_gate_drive_conventional_from_measured_fJ"],
        E_wellrail_per_bank_fJ=d["E_wellrail_total_fJ"] / d["nb"],
        # --- the four headline ledger rows
        E_per_gate_floor_timer0_fJ=R[FLOOR]["E_per_gate_fJ"],
        x_CMOS_floor_timer0=R[FLOOR]["x_vs_CMOS_block_4p14"],
        E_per_gate_floor_timerfloor_fJ=R[FLOORT]["E_per_gate_fJ"],
        x_CMOS_floor_timerfloor=R[FLOORT]["x_vs_CMOS_block_4p14"],
        E_per_gate_conv_timer0_fJ=R[CONV]["E_per_gate_fJ"],
        x_CMOS_conv_timer0=R[CONV]["x_vs_CMOS_block_4p14"],
        E_per_gate_conv_timerfloor_fJ=R[CONVT]["E_per_gate_fJ"],
        x_CMOS_conv_timerfloor=R[CONVT]["x_vs_CMOS_block_4p14"],
        x_CMOS_inv_cycle_floor=R[FLOOR]["x_vs_CMOS_inv_cycle"],
        x_CMOS_block_isoswing_floor=R[FLOOR]["x_vs_CMOS_block_isoswing_DERIVED"],
        # --- area
        tank_um2=d["area"]["tank_um2"], tank_um2_per_gate=d["area"]["tank_um2_per_gate"],
        switch_um2=d["area"]["switch_um2"], cells_um2=d["area"]["cells_um2"],
        tank_over_cell_active=d["area"]["tank_um2"] / d["area"]["cells_um2"],
        intra_class_spread_max_mV=max(max(v.values()) for v in
                                      d["intra_class_spread_mV"].values()),
        ICROSS_nonhopping_uA={k: v for k, v in
                              d["ICROSS_at_bank2_zcs_uA"].items() if k != "2"},
        wall_s=d.get("wall_s"))


def expo(a, b, ka, kb=None):
    kb = kb or ka
    if not (a[ka] and b[kb]) or a[ka] <= 0 or b[kb] <= 0 or a["N"] == b["N"]:
        return None
    return round(math.log(b[kb] / a[ka]) / math.log(b["N"] / a["N"]), 4)


def main():
    rows = [brief(d) for d in load()]
    prim = [r for r in rows if r["wmul"] == 1.0 and "rnd" not in r["tag"]
            and "noamm" not in r["tag"] and "ms025" not in r["tag"]
            and r["nb"] == 3]
    # ACCEPTED point per N = smallest T that clears every gate
    acc = {}
    for r in prim:
        if not r["ACCEPTED"]:
            continue
        if r["N"] not in acc or r["T_ps"] < acc[r["N"]]["T_ps"]:
            acc[r["N"]] = r
    series = [acc[n] for n in sorted(acc)]
    # flagged tight-beat rows (A4 only)
    flagged = [r for r in prim if not r["ACCEPTED"]]

    out = {}
    out["_doc"] = ("qal/widebank PHASE 1 -- the bank-width sweep. Every number "
                   "MEASURED off a .mt0/.prn in this directory unless the key "
                   "says DERIVED or ASSUMED. Pre-registration "
                   "PRE_REGISTERED.json sha256 c98fa108..., 20808 B, mtime "
                   "2026-09-29 19:21:28 -0700, written after "
                   "DISK_STATE_BEFORE.txt (19:19:10) and before the first deck.")
    out["CMOS_REFERENCES"] = dict(
        block_per_cell_per_op_fJ=CMOS_BLK,
        block_basis="232 fJ/op / 56 cells, SG13G2 typ 1.2 V (qal/sha256)",
        inverter_full_cycle_fJ=CMOS_INV,
        inverter_basis="bound/PRE_REGISTERED.json CMOS_inverter_anchor, the "
                       "SAME 1.12p/0.74n cell, 1.2 V",
        block_level_ps=CMOS_LVL, level_basis="928 ps / 10 levels",
        iso_swing_block_fJ_DERIVED=wbx.CMOS_BLOCK_PER_CELL_ISO_FJ,
        iso_swing_inverter_fJ_DERIVED=wbx.CMOS_INV_CYCLE_ISO_FJ,
        swing_note="QAL is run at dV=1.65 V because below Vtn+|Vtp|=0.9642 V "
                   "the cascade is not level-restoring; CMOS references are at "
                   "1.2 V. The PRIMARY comparison charges QAL that 1.891x "
                   "swing penalty (the not-flattering reading).")
    out["B_INSTRUMENT_CHECK"] = json.load(
        open(os.path.join(HERE, "INSTRUMENT_CHECK.json")))
    out["C_SWEEP_ACCEPTED_SERIES"] = series
    out["C_SWEEP_ALL_ROWS"] = rows
    out["C_TIGHT_BEAT_ROWS_A4_FLAGGED"] = flagged

    # ---- (d) scaling
    ex = {}
    keys = ["E_per_gate_floor_timer0_fJ", "E_per_gate_conv_timer0_fJ",
            "E_tank_loss_fJ", "E_tank_loss_per_gate_fJ", "E_switch_conduction_fJ",
            "E_switch_conduction_per_gate_fJ", "E_seriesR_fJ",
            "E_seriesR_per_gate_fJ", "E_park_path_fJ", "E_park_path_per_gate_fJ",
            "E_out_of_tank_rise_fJ", "Q_gate_MEASURED_fC",
            "E_gate_drive_conventional_fJ", "t_hop_rise_ps", "I_pk_uA",
            "level_time_ps", "A9_C_ratio", "recycle_fraction_pct"]
    for k in keys:
        ex[k] = dict(
            per_step=[dict(N_from=a["N"], N_to=b["N"], exponent=expo(a, b, k))
                      for a, b in zip(series, series[1:])],
            end_to_end=expo(series[0], series[-1], k) if len(series) > 1 else None,
            values={r["N"]: r[k] for r in series})
    out["D_SCALING_EXPONENTS_in_N"] = ex
    imp = [dict(N_from=a["N"], N_to=b["N"],
                pct_energy_improvement_floor=round(
                    100 * (1 - b["E_per_gate_floor_timer0_fJ"]
                           / a["E_per_gate_floor_timer0_fJ"]), 3),
                pct_energy_improvement_conv=round(
                    100 * (1 - b["E_per_gate_conv_timer0_fJ"]
                           / a["E_per_gate_conv_timer0_fJ"]), 3),
                pct_level_time_cost=round(100 * (b["level_time_ps"]
                                                 / a["level_time_ps"] - 1), 3),
                pct_t_hop_cost=round(100 * (b["t_hop_rise_ps"]
                                            / a["t_hop_rise_ps"] - 1), 3))
           for a, b in zip(series, series[1:])]
    out["D_IMPROVEMENT_PER_DOUBLING"] = imp
    out["D_KNEE"] = dict(
        first_step_under_10pct_floor=next(
            (x["N_to"] for x in imp if x["pct_energy_improvement_floor"] < 10.0),
            None),
        first_step_under_10pct_conv=next(
            (x["N_to"] for x in imp if x["pct_energy_improvement_conv"] < 10.0),
            None))
    # asymptote of the floor row from the last two points assuming a + b/sqrt(N)
    if len(series) >= 2:
        a1, a2 = series[-2], series[-1]
        r = math.sqrt(a2["N"] / a1["N"])   # y1-a = r*(y2-a)
        y1 = a1["E_per_gate_floor_timer0_fJ"]; y2 = a2["E_per_gate_floor_timer0_fJ"]
        # y = a + b/sqrt(N):  y1 - a = r*(y2 - a)  ->  a = (y1 - r*y2)/(1-r)
        out["D_FLOOR_ASYMPTOTE_fJ_per_gate_DERIVED"] = dict(
            value=(y1 - r * y2) / (1 - r), from_N=[a1["N"], a2["N"]],
            x_vs_CMOS_block=((y1 - r * y2) / (1 - r)) / CMOS_BLK,
            method="two-point solve of y = a + b/sqrt(N) on the top two "
                   "accepted points; DERIVED, an extrapolation, not measured")

    # ---- (e) the crossing
    cross = {}
    for lbl, k in (("floor_timer0", "E_per_gate_floor_timer0_fJ"),
                   ("floor_timerfloor_3p5227", "E_per_gate_floor_timerfloor_fJ"),
                   ("conventional_timer0", "E_per_gate_conv_timer0_fJ"),
                   ("conventional_timerfloor_3p5227",
                    "E_per_gate_conv_timerfloor_fJ")):
        hit = [r for r in series if r[k] < CMOS_BLK]
        first = min(hit, key=lambda r: r["N"]) if hit else None
        # interpolate N_min in 1/sqrt(N) across the bracketing pair
        nmin = None
        for a, b in zip(series, series[1:]):
            if (a[k] - CMOS_BLK) * (b[k] - CMOS_BLK) < 0:
                x1, x2 = 1 / math.sqrt(a["N"]), 1 / math.sqrt(b["N"])
                xt = x1 + (CMOS_BLK - a[k]) * (x2 - x1) / (b[k] - a[k])
                nmin = 1 / xt ** 2
                break
        best = min(series, key=lambda r: r[k])
        cross[lbl] = dict(
            crosses_within_swept_range=bool(hit),
            first_N_that_crosses=(first["N"] if first else None),
            E_per_gate_at_first_N_fJ=(first[k] if first else None),
            x_CMOS_at_first_N=(first[k] / CMOS_BLK if first else None),
            level_time_at_first_N_ps=(first["level_time_ps"] if first else None),
            x_CMOS_level_at_first_N=(first["x_CMOS_level"] if first else None),
            t_hop_at_first_N_ps=(first["t_hop_rise_ps"] if first else None),
            N_min_interpolated_in_1_over_sqrtN=nmin,
            best_N=best["N"], best_E_per_gate_fJ=best[k],
            best_x_CMOS=best[k] / CMOS_BLK,
            best_level_time_ps=best["level_time_ps"],
            best_x_CMOS_level=best["x_CMOS_level"])
    out["E_CROSSING"] = cross

    # ---- switch-width sub-sweep (the falsification controls)
    wsw = {}
    for n in sorted(set(r["N"] for r in rows if r["wmul"] != 1.0)):
        pts = [r for r in rows if r["N"] == n and "rnd" not in r["tag"]
               and "noamm" not in r["tag"] and "ms025" not in r["tag"]]
        # one T per N for a fair W comparison: prefer the T all W points share
        Ts = {}
        for r in pts:
            Ts.setdefault(r["T_ps"], []).append(r)
        T = max(Ts, key=lambda t: len(Ts[t]))
        grp = sorted(Ts[T], key=lambda r: r["wmul"])
        wsw[n] = dict(
            T_ps=T,
            points=[dict(wmul=r["wmul"], W_um=r["W_nominal_um"],
                         t_hop_ps=r["t_hop_rise_ps"], I_pk_uA=r["I_pk_uA"],
                         Q_gate_fC=r["Q_gate_MEASURED_fC"],
                         E_tank_per_gate_fJ=r["E_tank_loss_per_gate_fJ"],
                         E_per_gate_floor_fJ=r["E_per_gate_floor_timer0_fJ"],
                         E_per_gate_conv_fJ=r["E_per_gate_conv_timer0_fJ"],
                         A1=r["A1_value_all_gates"], A2=r["A2_functional_bare"],
                         A2_margin_min_mV=r["A2_margin_min_mV"],
                         worst_gate_pct=r["worst_gate_pct"],
                         E_switch_conduction_fJ=r["E_switch_conduction_fJ"])
                    for r in grp],
            energy_optimal_wmul_floor=min(grp,
                key=lambda r: r["E_per_gate_floor_timer0_fJ"])["wmul"],
            energy_optimal_wmul_conventional=min(grp,
                key=lambda r: r["E_per_gate_conv_timer0_fJ"])["wmul"],
            speed_optimal_wmul=min(grp, key=lambda r: r["t_hop_rise_ps"])["wmul"])
    out["F_SWITCH_WIDTH_SUBSWEEP"] = wsw

    # ---- G: the BEST measured QAL point on each ledger row over EVERY row in
    # the study (so the switch-width optimum is inside the crossing answer, not
    # only the pre-registered constant-Q width)
    allok = [r for r in rows if r["A1_value_all_gates"] and r["A2_functional_bare"]
             and r["nb"] == 3]
    g = {}
    for lbl, k in (("floor_timer0", "E_per_gate_floor_timer0_fJ"),
                   ("conventional_timer0", "E_per_gate_conv_timer0_fJ"),
                   ("conventional_timerfloor_3p5227",
                    "E_per_gate_conv_timerfloor_fJ")):
        b = min(allok, key=lambda r: r[k])
        g[lbl] = dict(tag=b["tag"], N=b["N"], wmul=b["wmul"],
                      W_um=b["W_nominal_um"], T_ps=b["T_ps"],
                      t_hop_ps=b["t_hop_rise_ps"],
                      E_per_gate_fJ=b[k], x_CMOS_block=b[k] / CMOS_BLK,
                      x_CMOS_level_at_T=b["x_CMOS_level"],
                      x_CMOS_level_at_t_hop=b["t_hop_rise_ps"] / CMOS_LVL,
                      A4_zcs=b["A4_zcs"], ACCEPTED=b["ACCEPTED"],
                      tank_um2_per_gate=b["tank_um2_per_gate"],
                      note="best measured point ANYWHERE in the study on this "
                           "ledger row, including the switch-width sub-sweep")
    out["G_BEST_MEASURED_POINT_ANY_WIDTH"] = g

    # ---- H: the energy x time product, to expose the hyperbola
    out["H_ENERGY_TIME_PRODUCT"] = [
        dict(tag=r["tag"], N=r["N"], wmul=r["wmul"],
             E_per_gate_conv_fJ=r["E_per_gate_conv_timer0_fJ"],
             t_hop_ps=r["t_hop_rise_ps"],
             product_fJ_ps=r["E_per_gate_conv_timer0_fJ"] * r["t_hop_rise_ps"],
             E_per_gate_floor_fJ=r["E_per_gate_floor_timer0_fJ"],
             product_floor_fJ_ps=r["E_per_gate_floor_timer0_fJ"]
             * r["t_hop_rise_ps"])
        for r in sorted(allok, key=lambda x: (x["N"], x["wmul"]))]
    open(os.path.join(HERE, "RESULTS.json"), "w").write(
        json.dumps(out, indent=1, default=str))
    print("wrote RESULTS.json")
    print("\nACCEPTED SERIES")
    print("  N    T  t_hop  E/g_floor xCM   E/g_conv xCM   xCMOSlvl  tank_um2/g")
    for r in series:
        print("%4d %4.0f %6.1f   %8.4f %5.3f  %8.4f %5.3f  %7.2f %10.2f"
              % (r["N"], r["T_ps"], r["t_hop_rise_ps"],
                 r["E_per_gate_floor_timer0_fJ"], r["x_CMOS_floor_timer0"],
                 r["E_per_gate_conv_timer0_fJ"], r["x_CMOS_conv_timer0"],
                 r["x_CMOS_level"], r["tank_um2_per_gate"]))
    print("\nCROSSING")
    for k, v in out["E_CROSSING"].items():
        print(" %-32s crosses=%-5s firstN=%-5s x=%s Nmin=%s bestN=%s best_x=%.4f"
              % (k, v["crosses_within_swept_range"], v["first_N_that_crosses"],
                 (round(v["x_CMOS_at_first_N"], 4)
                  if v["x_CMOS_at_first_N"] else None),
                 (round(v["N_min_interpolated_in_1_over_sqrtN"], 1)
                  if v["N_min_interpolated_in_1_over_sqrtN"] else None),
                 v["best_N"], v["best_x_CMOS"]))
    print("\nKNEE", out["D_KNEE"])
    print("ASYMPTOTE", out.get("D_FLOOR_ASYMPTOTE_fJ_per_gate_DERIVED"))


if __name__ == "__main__":
    main()
