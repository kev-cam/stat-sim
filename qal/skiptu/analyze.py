#!/usr/bin/env python3
"""Score the measured rows against the PRE-REGISTERED criteria and expectations.
Reads rows.json only.  Writes RESULTS.json.  ONE code path for every row."""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))


def load():
    R = json.load(open(os.path.join(HERE, "rows.json")))
    return [r for r in R if "ERROR" not in r], [r for r in R if "ERROR" in r]


def brief(r):
    return dict(tag=r["tag"], T_ps=r["T_ps"], dv=r["dv"], mode=r["mode"],
                ltu_nH=r["ltu_nH"], wsw_um=r["wsw_um"], t_on_ps=r["t_on_ps"],
                fire_off_ps=r["fire_off_ps"],
                worst_gate_pct=r["worst_gate_all_stages_pct"],
                worst_by_stage_pct=r["worst_gate_by_stage_pct"],
                min_delivered_HIGH_V=r["A2_min_delivered_high_V"],
                A1_90pct=r["ACCEPTANCE"]["A1_all_four_stages_90pct"],
                A2_clears=r["ACCEPTANCE"]["A2_all_stages_clear_0p4400"],
                rail_by_stage_V=r["rail_by_stage_at_its_boundary_V"])


def main():
    OK, ERR = load()
    S4 = [r for r in OK if r["scheme"] == "s4"]
    S5 = [r for r in OK if r["scheme"] == "s5"]
    out = {"_doc": ("THE SUSTAINED STAGE-SKIP QAL CHAIN: skip schedule (1->3, 2->4) "
                    "WITH PULSED-INDUCTOR TOP-UP on the held banks. Pre-registration: "
                    "PRE_REGISTERED.json, written before any deck existed."),
           "n_rows_measured": len(OK), "n_rows_error": len(ERR),
           "errors": [dict(tag=r.get("tag"), err=str(r["ERROR"])[:240]) for r in ERR]}

    best = max(OK, key=lambda r: (r["worst_gate_all_stages_pct"] or -1)) if OK else None
    out["HEADLINE"] = dict(
        max_worst_gate_over_all_rows_pct=best["worst_gate_all_stages_pct"] if best else None,
        which_row=best["tag"] if best else None,
        any_row_A1_90pct_all_four_stages=any(
            r["ACCEPTANCE"]["A1_all_four_stages_90pct"] for r in OK),
        any_row_A2_clears_0p4400_all_stages=any(
            bool(r["ACCEPTANCE"]["A2_all_stages_clear_0p4400"]) for r in OK),
        max_min_delivered_HIGH_V=max(
            (r["A2_min_delivered_high_V"] for r in OK
             if r["A2_min_delivered_high_V"] is not None), default=None))

    # ---- (d) my own control WITHOUT top-up, then WITH, at dV=1.2 and 1.5
    cmp_ = {}
    for dv in sorted({r["dv"] for r in S4}):
        for T in sorted({r["T_ps"] for r in S4}):
            f = [r for r in S4 if r["mode"] == "free" and r["dv"] == dv and r["T_ps"] == T]
            p = [r for r in S4 if r["mode"] == "ptu" and r["dv"] == dv and r["T_ps"] == T]
            if not f and not p:
                continue
            bp = max(p, key=lambda r: r["worst_gate_all_stages_pct"] or -1) if p else None
            cmp_["dv%g_T%d" % (dv, T)] = dict(
                control_free=brief(f[0]) if f else None,
                best_topup=brief(bp) if bp else None,
                n_topup_rows=len(p),
                delta_worst_gate_points=(
                    round((bp["worst_gate_all_stages_pct"] or 0)
                          - (f[0]["worst_gate_all_stages_pct"] or 0), 2)
                    if (f and bp) else None),
                delta_min_HIGH_mV=(
                    round(1000.0 * ((bp["A2_min_delivered_high_V"] or 0)
                                    - (f[0]["A2_min_delivered_high_V"] or 0)), 2)
                    if (f and bp) else None))
    out["d_CONTROL_vs_TOPUP"] = cmp_

    # ---- the strength sweep: monotone or interior optimum?
    st = {}
    for dv in sorted({r["dv"] for r in S4}):
        rows = [r for r in S4 if r["mode"] == "ptu" and r["dv"] == dv
                and r["T_ps"] == 200 and r["wsw_um"] == 10.0
                and r["fire_off_ps"] == 0.0]
        if not rows:
            continue
        tbl = sorted([(r["ltu_nH"], r["t_on_ps"], r["worst_gate_all_stages_pct"],
                       r["A2_min_delivered_high_V"],
                       (r["cost"]["topup"] or {}).get("q_delivered_total_fC"),
                       r["rail_by_stage_at_its_boundary_V"].get("3")
                       or r["rail_by_stage_at_its_boundary_V"].get(3))
                      for r in rows])
        st["dv%g_T200" % dv] = dict(
            _columns="Ltu_nH, t_on_ps, worst_gate_pct, min_HIGH_V, q_delivered_fC, rail3_V",
            rows=tbl,
            best=max(tbl, key=lambda x: x[2] or -1))
        wsw = sorted([(r["wsw_um"], r["worst_gate_all_stages_pct"],
                       r["A2_min_delivered_high_V"])
                      for r in S4 if r["mode"] == "ptu" and r["dv"] == dv
                      and r["T_ps"] == 200 and r["t_on_ps"] == 12.0
                      and r["ltu_nH"] == 2.0])
        st["dv%g_switch_width" % dv] = dict(
            _columns="wsw_um, worst_gate_pct, min_HIGH_V", rows=wsw)
    out["e_STRENGTH_SWEEP_shape"] = st

    tm = {}
    for dv in sorted({r["dv"] for r in S4}):
        rows = [r for r in S4 if r["dv"] == dv and r["T_ps"] == 200
                and r["mode"].startswith("ptu")]
        if rows:
            tm["dv%g_T200" % dv] = dict(
                _columns="mode, fire_off_ps, worst_gate_pct, min_HIGH_V, rail3_V",
                rows=sorted([(r["mode"], r["fire_off_ps"],
                              r["worst_gate_all_stages_pct"],
                              r["A2_min_delivered_high_V"],
                              r["rail_by_stage_at_its_boundary_V"].get("3")
                              or r["rail_by_stage_at_its_boundary_V"].get(3))
                             for r in rows], key=lambda x: (x[0], x[1])))
    out["e_TIMING_SWEEP_shape"] = tm

    # ---- measurement 1: the threshold test, every stage, every row
    out["m1_THRESHOLD_TEST"] = dict(
        _gate_V=0.4400,
        _adjacent_chain_comparator="delivered 0.4053 V, short by 34.7 mV",
        per_row={r["tag"]: {str(k): dict(
            min_high_V=v.get("min_high_V"), margin_mV=v.get("margin_mV"),
            clears=v.get("clears_0p4400"),
            predecessor_rail_V=v.get("predecessor_rail_at_this_boundary_V"))
            for k, v in r["threshold_test"].items()} for r in OK})

    # ---- measurement 2: per-gate settling at every stage
    out["m2_PER_GATE_SETTLING"] = {
        r["tag"]: {str(k): dict(
            rail_V=v.get("rail_at_bound_V"), worst_pct=v.get("worst_pct"),
            worst_pullup_pct=v.get("worst_pullup_pct"),
            worst_pulldown_pct=v.get("worst_pulldown_pct"),
            per_gate_pct={str(i): g["settle_pct"] for i, g in v["per_gate"].items()})
            for k, v in r["settling"].items()} for r in OK}

    # ---- measurement 3: the hold, with and without top-up
    out["m3_THE_HOLD"] = {r["tag"]: r["hold"] for r in OK}

    # ---- measurement 4: beat period + overlap
    out["m4_BEAT_AND_OVERLAP"] = {
        r["tag"]: dict(T_ps=r["T_ps"], t_hop_measured_ps=r["t_hop_measured_ps"],
                       T_over_t_hop=r["T_over_t_hop"],
                       boundary_inside_charging_hop=r["boundary_inside_charging_hop"],
                       hops=r["hops_detail"]) for r in OK}

    # ---- measurement 5: accumulated droop
    out["m5_ACCUMULATED_DROOP"] = {
        r["tag"]: dict(rail_by_stage_V=r["rail_by_stage_at_its_boundary_V"],
                       accumulated_mV=r["accumulated_droop_stage1_to_stageN_mV"],
                       vs_120mV_budget=r["accumulated_droop_vs_120mV_budget"])
        for r in OK}

    # ---- measurement 6: COST including the top-up's own gate drive
    out["m6_COST"] = {r["tag"]: r["cost"] for r in OK if r["cost"].get("topup")}
    tu_rows = [r for r in OK if r["cost"].get("topup")]
    if tu_rows:
        out["m6_COST_SUMMARY"] = dict(
            _units="fJ",
            rows=sorted([(r["tag"],
                          r["cost"]["topup"]["E_from_supply_fJ"],
                          r["cost"]["topup"]["E_SWITCH_GATE_DRIVE_fJ"],
                          r["cost"]["topup"]["E_landed_total_fJ"],
                          r["cost"]["topup"]["gate_drive_over_energy_landed"],
                          r["cost"]["topup"]["total_cost_over_energy_landed"],
                          r["cost"]["topup"]["charge_multiplication_Qdel_over_Qsup"])
                         for r in tu_rows]),
            _columns=("tag, E_from_supply_fJ, E_GATE_DRIVE_fJ, E_landed_fJ, "
                      "gate/landed, (supply+gate)/landed, Qdel/Qsup"),
            committed_single_hop_dissipation_fJ=8.3828,
            chain3_topup_cost_fJ_per_bank_per_hop=[15.2, 29.1])

    # ---- the BOUNDING resistive top-up: cost as a DIFFERENTIAL against free
    rt = [r for r in OK if r["cost"].get("rtu")]
    if rt:
        frl = {(r["scheme"], r["dv"], r["T_ps"]): r for r in OK if r["mode"] == "free"}
        rows = []
        for r in rt:
            f = frl.get((r["scheme"], r["dv"], r["T_ps"]))
            qr = r["cost"]["rtu"]["q_from_dV_node_total_fC"]
            qf = f["cost"]["head_precharge_charge_fC"] if f else None
            dq = (qr - qf) if (qr is not None and qf is not None) else None
            rows.append((r["tag"], qr, qf, round(dq, 4) if dq is not None else None,
                         round(dq * r["dv"], 4) if dq is not None else None,
                         r["cost"]["rtu"]["E_SWITCH_GATE_DRIVE_fJ"],
                         r["worst_gate_all_stages_pct"]))
        out["m6_COST_RTU_differential"] = dict(
            _columns=("tag, q_dV_rtu_fC, q_dV_free_fC, delta_q_fC (the top-up's own "
                      "charge), E_topup_fJ = delta_q*dV, E_gate_real_driver_fJ, "
                      "worst_gate_pct"),
            _why_differential=("the resistive top-up draws from the same ideal dV node as "
                               "the head pre-charge gates, so its own share cannot be "
                               "separated inside one deck; the matched free row has the "
                               "head gates and no top-up, so the difference is the "
                               "top-up's charge"),
            rows=rows,
            committed_single_hop_dissipation_fJ=8.3828)

    # ---- the 5-bank rows: the only place a hop-charged bank really drains
    if S5:
        out["m3b_FIVE_BANK_full_two_beat_hold"] = {
            r["tag"]: dict(mode=r["mode"], T_ps=r["T_ps"], dv=r["dv"],
                           hold=r["hold"],
                           worst_by_stage_pct=r["worst_gate_by_stage_pct"],
                           threshold={str(k): v.get("min_high_V")
                                      for k, v in r["threshold_test"].items()})
            for r in S5}

    # ---- A6 instrument state on every row
    out["A6_instrument_state"] = {
        r["tag"]: r["A6_instrument"] for r in OK}
    out["A6_summary"] = dict(
        rows_passing_IZ_gate=sum(1 for r in OK if r["A6_instrument"]["IZ_gate_1uA"] == "PASS"),
        rows_total=len(OK),
        failing=[r["tag"] for r in OK if r["A6_instrument"]["IZ_gate_1uA"] != "PASS"])

    # ---- score the PRE-REGISTERED expectations P1-P6, each with its evidence
    tu_rows2 = [r for r in S4 if r["mode"] == "ptu"]
    fr = {(r["dv"], r["T_ps"]): r for r in S4 if r["mode"] == "free"}
    gains = []
    for r in tu_rows2:
        f = fr.get((r["dv"], r["T_ps"]))
        if f and r["worst_gate_all_stages_pct"] is not None \
                and f["worst_gate_all_stages_pct"] is not None:
            gains.append((round(r["worst_gate_all_stages_pct"]
                                - f["worst_gate_all_stages_pct"], 2), r["tag"]))
    gains.sort(reverse=True)
    rail_vs_gain = [(r["rail_by_stage_at_its_boundary_V"].get("3"),
                     r["worst_gate_all_stages_pct"], r["tag"]) for r in tu_rows2]
    st_rows = [r for r in tu_rows2 if r["T_ps"] == 200 and r["wsw_um"] == 10.0
               and r["dv"] == 1.2 and r["fire_off_ps"] == 0.0]
    st_rows.sort(key=lambda r: (r["ltu_nH"], r["t_on_ps"]))
    tim_rows = sorted([r for r in tu_rows2 if r["T_ps"] == 200 and r["dv"] == 1.2
                       and r["ltu_nH"] == 1.0 and r["wsw_um"] == 10.0],
                      key=lambda r: r["fire_off_ps"])
    costs = [(r["cost"]["topup"]["gate_drive_over_energy_landed"], r["tag"])
             for r in tu_rows2 if r["cost"].get("topup")
             and r["cost"]["topup"].get("gate_drive_over_energy_landed") is not None]
    out["P_SCORED"] = {
        "P1_topup_helps_by_>=30_points_and_via_the_RAIL_not_the_hold": dict(
            best_gain_points=gains[0] if gains else None,
            worst_gain_points=gains[-1] if gains else None,
            all_gains=gains,
            rail3_vs_worstgate_for_every_topup_row=sorted(
                [x for x in rail_vs_gain if x[0] is not None])),
        "P2_the_0p4400_V_gate": dict(
            free_rows_clearing=[r["tag"] for r in S4 if r["mode"] == "free"
                                and r["ACCEPTANCE"]["A2_all_stages_clear_0p4400"]],
            topup_rows_clearing=[r["tag"] for r in tu_rows2
                                 if r["ACCEPTANCE"]["A2_all_stages_clear_0p4400"]],
            best_free_min_high_V=max([r["A2_min_delivered_high_V"] for r in S4
                                      if r["mode"] == "free"
                                      and r["A2_min_delivered_high_V"] is not None],
                                     default=None),
            best_topup_min_high_V=max([r["A2_min_delivered_high_V"] for r in tu_rows2
                                       if r["A2_min_delivered_high_V"] is not None],
                                      default=None)),
        "P3_monotone_then_saturating_in_strength_interior_optimum_in_time": dict(
            strength_table=[(r["ltu_nH"], r["t_on_ps"],
                             r["worst_gate_all_stages_pct"],
                             r["A2_min_delivered_high_V"],
                             (r["cost"]["topup"] or {}).get("q_delivered_total_fC"),
                             r["rail_by_stage_at_its_boundary_V"].get("3"))
                            for r in st_rows],
            _strength_columns="Ltu_nH, t_on_ps, worst_gate_pct, minHIGH_V, q_del_fC, rail3_V",
            timing_table=[(r["mode"], r["fire_off_ps"],
                           r["worst_gate_all_stages_pct"],
                           r["A2_min_delivered_high_V"]) for r in tim_rows],
            _timing_columns="mode, fire_off_ps, worst_gate_pct, minHIGH_V"),
        "P4_cost_gate_drive_EXCEEDS_energy_landed": dict(
            gate_over_landed_ratios=sorted(costs, reverse=True),
            _note=("ratio > 1 means the top-up's own switch gate drive costs more "
                   "than the energy it puts into the bank")),
        "P5_beat_binds_on_t_hop": dict(
            measured_t_hop_ps={t: r["t_hop_measured_ps"] for t, r in
                               sorted((r["tag"], r) for r in S4)[:6]},
            rows_with_boundary_inside_charging_hop=[
                r["tag"] for r in OK if r["boundary_inside_charging_hop"]]),
        "P6_would_make_me_wrong_in_the_interesting_direction": dict(
            _test=("a row that reaches >=90% at ALL FOUR stages WITHOUT the top-up "
                   "restoring the rail to near-dV would mean the mechanism really is "
                   "the hold"),
            rows_at_90pct=[r["tag"] for r in OK
                           if r["ACCEPTANCE"]["A1_all_four_stages_90pct"]])}

    json.dump(out, open(os.path.join(HERE, "RESULTS.json"), "w"), indent=1, default=str)
    print("wrote RESULTS.json  (%d measured rows, %d errors)" % (len(OK), len(ERR)))
    h = out["HEADLINE"]
    print("HEADLINE: max worst-gate %.2f%% (%s)" % (
        h["max_worst_gate_over_all_rows_pct"] or -1, h["which_row"]))
    print("  A1 any row 90%% all four stages : %s" % h["any_row_A1_90pct_all_four_stages"])
    print("  A2 any row clears 0.4400 V     : %s" % h["any_row_A2_clears_0p4400_all_stages"])
    print("  best min delivered HIGH        : %s V" % h["max_min_delivered_HIGH_V"])


if __name__ == "__main__":
    main()
