#!/usr/bin/env python3
"""Aggregate the per-bank-tank rows into the deliverables the brief asks for:
 (1) rail-start offset sweep -> earliest CORRECT start + beat period, measured
     directly off the running 4-bank chain;
 (2) the exhaustive interval scan, in picoseconds;
 (3) per-gate correctness at every offset (never aggregated) + the value check;
 (4) fade by depth against the corrected 6.44 mV 1-sigma floor;
 (5) the HEADLINE trade curve: concurrent inductors vs overlap vs beat period,
     plus tank area in um^2;
 (6) energy per hop vs m, with the tank recharge costed or bounded.
"""
import glob, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
CMOS_LEVEL_PS = 94.174        # qal/vtreq device-level comparator at DELVTO=0
QAL_SINGLE_HOP_LEVEL_PS = 123.44311400000001   # committed adjacent single hop
SIGMA_FLOOR_MV = 6.44


def load_rows():
    rows = []
    for p in sorted(glob.glob(os.path.join(HERE, "row_*.json"))):
        try:
            rows.append(json.load(open(p)))
        except Exception as e:
            print("skip", p, e)
    return rows


def key(r):
    return (r["m"], r["T_ps"], r["H"], r["dv"], r["mode"])


def main():
    rows = load_rows()
    out = {"_n_rows": len(rows)}

    # ---------- (1) the rail-start offset sweep
    tbl = []
    for r in sorted(rows, key=key):
        dvd = r["data_valid_delay_from_own_rail_start_ps"]
        off = r["rail_start_offset_vs_pred_dv_ps"]
        tbl.append(dict(
            m=r["m"], T_ps=r["T_ps"], H=r["H"], dv=r["dv"], mode=r["mode"],
            PASS=r["PASS"], A1=r["A1_settling_pass_90"], A2=r["A2_value_pass"],
            worst_gate_pct=round(r["worst_gate_pct"], 3),
            worst_where=r["worst_gate_where"],
            per_bank_worst=({k: round(v, 2) for k, v in r["per_bank_worst_pct"].items()}),
            value_fails=r["value_fail_list"],
            rail_own_boundary=({k: round(v, 5) for k, v in
                                r["rail_at_own_boundary_V"].items()}),
            rail_depth_spread_mV=round(r["rail_depth_spread_mV"], 3),
            sep_mV=({k: round(r["separation_by_depth"][k]["separation_mV"], 3)
                     for k in r["separation_by_depth"]}),
            sep_min_mV=round(r["separation_min_mV"], 3),
            dv_delay_ps=({k: (round(v, 3) if v else None) for k, v in dvd.items()}),
            all_banks_valid=r["all_banks_reach_valid"],
            stage_time_ps=({k: (round(v, 3) if v else None) for k, v in
                            r["steady_state_stage_time_ps"].items()}),
            stage_time_deepest_ps=(round(r["stage_time_deepest_ps"], 3)
                                   if r["stage_time_deepest_ps"] else None),
            rail_start_offset_ps=({k: (round(v, 3) if v else None)
                                   for k, v in off.items()}),
            ramp_x_pred_eval_ps=r["ramp_x_pred_eval_measured_ps"],
            ramp_x_pred_evalfull_ps=r["ramp_x_pred_eval_full_ps"],
            Lconc=r["concurrent_inductors_schedule"],
            Lconc_ramps=r["concurrent_ramps_only_schedule"],
            Lconc_wave=r["concurrent_inductors_waveform_gt1uA"],
            IZ_uA=({k: round(v, 4) for k, v in r["IZ_uA"].items()}),
            IZQ_uA=({k: round(v, 4) for k, v in r["IZQ_uA"].items()}),
            A6_zcs=r["A6_zcs_pass"], A6_ident=r["A6_path_identity_pass"],
            tank_area_um2_per_bank=round(r["tank_area_um2_MIM"], 3),
            tank_area_um2_chain=round(r["tank_area_um2_per_chain"], 3),
        ))
    out["rows"] = tbl

    passing = [t for t in tbl if t["PASS"]]
    out["PASSING_ROWS"] = passing
    out["ANY_PASS"] = bool(passing)

    def earliest(sel):
        p = [t for t in tbl if t["PASS"] and sel(t)]
        return min(p, key=lambda t: t["T_ps"]) if p else None

    # THE PRE-REGISTERED OPERATING POINT: free-running, dV = 1.2, H = 4.
    hd = earliest(lambda t: t["mode"] == "free" and t["dv"] == 1.2 and t["H"] == 4)
    out["HEADLINE_pre_registered_point"] = hd
    out["EARLIEST_CORRECT_BEAT_PERIOD_ps"] = hd["T_ps"] if hd else None
    if hd:
        out["vs_CMOS_logic_level"] = hd["T_ps"] / CMOS_LEVEL_PS
        out["vs_committed_QAL_single_hop_level"] = hd["T_ps"] / QAL_SINGLE_HOP_LEVEL_PS

    # per-m earliest correct beat (the AREA/SPEED trade the user asked for)
    tr = {}
    for mm in sorted({t["m"] for t in tbl}):
        e = earliest(lambda t, mm=mm: t["m"] == mm and t["mode"] == "free"
                     and t["dv"] == 1.2 and t["H"] == 4)
        fails = [t for t in tbl if t["m"] == mm and t["mode"] == "free"
                 and t["dv"] == 1.2 and t["H"] == 4 and not t["PASS"]]
        tr[mm] = dict(
            earliest_correct_T_ps=(e["T_ps"] if e else None),
            worst_gate_at_that_T=(e["worst_gate_pct"] if e else None),
            highest_failing_T_ps=(max(f["T_ps"] for f in fails) if fails else None),
            tank_C_fF=(e or (fails[0] if fails else {})).get("tank_area_um2_per_bank", 0) * 1.5,
            tank_area_um2_per_bank=(e or (fails[0] if fails else {})).get(
                "tank_area_um2_per_bank"),
            tank_area_um2_chain=(e or (fails[0] if fails else {})).get(
                "tank_area_um2_chain"),
            concurrent_inductors=(e["Lconc"] if e else None),
            overlap_at_earliest_correct_ps=(
                max(e["ramp_x_pred_eval_ps"].values())
                if (e and e["ramp_x_pred_eval_ps"]) else None),
            stage_time_deepest_ps=(e.get("stage_time_deepest_ps") if e else None))
    out["M_SWEEP_earliest_correct"] = tr

    # per-H (the hold sweep) and the INITIATION INTERVAL H*T
    hh = {}
    for HH in sorted({t["H"] for t in tbl}):
        e = earliest(lambda t, HH=HH: t["H"] == HH and t["m"] == 10
                     and t["mode"] == "free" and t["dv"] == 1.2)
        hh[HH] = dict(earliest_correct_T_ps=(e["T_ps"] if e else None),
                      initiation_interval_ps=(HH * e["T_ps"] if e else None),
                      concurrent_inductors=(e["Lconc"] if e else None))
    out["H_SWEEP_m10"] = hh

    # side conditions reported separately, never folded into the headline
    out["SIDE_dv1650_m10_H4"] = earliest(
        lambda t: t["dv"] == 1.65 and t["mode"] == "free" and t["m"] == 10)
    out["SIDE_vfull_control_m10_H4"] = earliest(
        lambda t: t["mode"] == "vfull" and t["m"] == 10)

    # THE OVERLAP VERDICT: does any PASSING row show cross-bank concurrency?
    out["OVERLAP_at_passing_rows_ps"] = {
        "%g_%g_%d_%g_%s" % (t["m"], t["T_ps"], t["H"], t["dv"], t["mode"]):
        (max(t["ramp_x_pred_eval_ps"].values()) if t["ramp_x_pred_eval_ps"] else 0.0)
        for t in passing}
    out["MAX_OVERLAP_ON_ANY_PASSING_ROW_ps"] = (
        max(out["OVERLAP_at_passing_rows_ps"].values())
        if out["OVERLAP_at_passing_rows_ps"] else None)

    # ---------- (5) the trade curve
    curve = []
    for t in sorted(tbl, key=lambda x: (x["m"], x["H"], x["T_ps"])):
        ov = t["ramp_x_pred_eval_ps"] or {}
        ovf = t["ramp_x_pred_evalfull_ps"] or {}
        curve.append(dict(m=t["m"], H=t["H"], dv=t["dv"], beat_ps=t["T_ps"],
                          PASS=t["PASS"],
                          overlap_ramp_x_pred_resolving_ps=ov,
                          overlap_ramp_x_pred_evalwindow_ps=ovf,
                          overlap_max_ps=(max(ov.values()) if ov else 0.0),
                          concurrent_inductors=t["Lconc"],
                          concurrent_inductors_ramps_only=t["Lconc_ramps"],
                          concurrent_inductors_waveform=t["Lconc_wave"],
                          tank_area_um2_per_bank=t["tank_area_um2_per_bank"],
                          tank_area_um2_chain=t["tank_area_um2_chain"]))
    out["TRADE_CURVE"] = curve

    # ---------- (6) energy vs m
    en = []
    for r in sorted(rows, key=key):
        e = r["energy_per_bank"]
        en.append(dict(m=r["m"], T_ps=r["T_ps"], H=r["H"], dv=r["dv"],
                       mode=r["mode"], PASS=r["PASS"],
                       C_tank_fF=r["C_tank_fF"], V_tank0=r["V_tank0"],
                       per_bank={k: {kk: (round(vv, 5) if isinstance(vv, float) else vv)
                                     for kk, vv in e[k].items()} for k in e},
                       tank_loss_total_fJ=round(
                           sum(e[k]["tank_energy_lost_fJ"] for k in e), 5),
                       E_gate_drive_total_fJ=round(r["E_gate_drive_total_fJ"], 5),
                       E_vhi_total_fJ=round(r["E_vhi_total_fJ"], 5),
                       E_tank_recharge_measured_fJ=r.get("E_tank_recharge_measured_fJ")))
    out["ENERGY"] = en

    open(os.path.join(HERE, "RESULTS.json"), "w").write(json.dumps(out, indent=1,
                                                                   default=str))
    # ---------- console summary
    print("%-4s %-5s %-3s %-5s %-6s %-6s %-7s %-9s %-8s %-6s %-6s %-9s %-5s" %
          ("m", "T", "H", "dv", "mode", "PASS", "worst%", "sep_min", "ovl_max",
           "Lconc", "allvld", "stage_t", "zcs"))
    for t in tbl:
        ov = t["ramp_x_pred_eval_ps"] or {}
        st = t.get("stage_time_deepest_ps")
        print("%-4g %-5g %-3d %-5g %-6s %-6s %-7.2f %-9.3f %-8.2f %-6d %-6s %-9s %-5s" %
              (t["m"], t["T_ps"], t["H"], t["dv"], t["mode"], t["PASS"],
               t["worst_gate_pct"], t["sep_min_mV"],
               (max(ov.values()) if ov else 0.0), t["Lconc"],
               t.get("all_banks_valid"), ("%.1f" % st) if st else "-",
               t["A6_zcs"]))
    print("\nEARLIEST CORRECT BEAT PERIOD:", out["EARLIEST_CORRECT_BEAT_PERIOD_ps"])


if __name__ == "__main__":
    main()
