#!/usr/bin/env python3
"""Consolidate the PHASE 2 answers into PHASE2_ANSWER.json.

Nothing here simulates.  Inputs are RESULTS_PHASE2.json, CRUX.json,
CRUX_CDECOMP.json and SCORED_PHASE2.json.
"""
import json, math, os

HERE = os.path.dirname(os.path.abspath(__file__))
CMOS_BLK, CMOS_LVL = 4.14, 92.8


def main():
    R = json.load(open(os.path.join(HERE, "RESULTS_PHASE2.json")))
    C = json.load(open(os.path.join(HERE, "CRUX.json")))
    CD = json.load(open(os.path.join(HERE, "CRUX_CDECOMP.json")))
    SC = json.load(open(os.path.join(HERE, "SCORED_PHASE2.json")))
    T = {t["tag"]: t for t in R["TABLE"]}
    tab = R["TABLE"]

    def main_series(n):
        return sorted([t for t in tab if t["N"] == n and not t["extra"]
                       and len(set(t["scale_per_bank"])) == 1
                       and abs(t["L_nH"] - 15.0) < 1e-9],
                      key=lambda t: t["sc_scored"])

    # ---- the mechanism law, across BOTH axes
    law = []
    for t in sorted(tab, key=lambda x: (x["N"], x["sc_scored"])):
        if t["extra"] or len(set(t["scale_per_bank"])) > 1 \
                or abs(t["L_nH"] - 15.0) > 1e-9:
            continue
        law.append(dict(N=t["N"], scale=t["sc_scored"], t_hop_ps=t["t_hop_ps"],
                        C_bank_measured_fF=t["C_meas_fF"],
                        C_tank_fF=t["C_tank_fF"],
                        k_ps_per_sqrt_fF=t["t_hop_ps"]
                        / math.sqrt(t["C_meas_fF"])))
    ks = [x["k_ps_per_sqrt_fF"] for x in law]
    cts = [x["C_tank_fF"] for x in law]

    b = T["n64_T440_H4_dv1650_free_nb3"]
    e6 = T["n64_T260_H4_dv1650_free_nb3_E6Lcut"]
    e3 = T["n64_T440_H4_dv1650_free_nb3_s4_E3isohop"]
    s4 = T["n64_T790_H4_dv1650_free_nb3_s4"]
    e1 = T["n64_T790_H4_dv1650_free_nb3_s4-4-1_E1load"]

    # iso-swing correction for E6: it delivers a LOWER rail, and energy ~ V^2
    sw = b["A2_mV"], e6["A2_mV"]
    rail_b, rail_e6 = 0.9422477, 0.740495      # rail_at_own_boundary, MEASURED
    iso = (rail_b / rail_e6) ** 2

    out = dict(
        _doc="qal/upsize PHASE 2 -- CELL UPSIZING AS THE SPEED LEVER. The "
             "answers to (a) crux, (b) numbers, (c) trade curve and exchange "
             "rate, (d) per-gate settling and VALUE. MEASURED unless a key "
             "says DERIVED or ASSUMED.",

        A_THE_CRUX=dict(
            question="in a real chain the driver AND its load both scale -- "
                     "does t_settle fall at all, or is it scale-INVARIANT?",
            ANSWER="NEARLY SCALE-INVARIANT. 8x the cell width buys only "
                   "28.2% less settling time in the real chain (32.2% with the "
                   "QAL-bias load), and the whole improvement is the 1/s "
                   "dilution of a FIXED load component. t = a + b/s fits with "
                   "R2 = 0.9995. Even INFINITE width can only reach 0.676 of "
                   "the x1 delay. The area-for-speed trade does NOT exist at "
                   "the cell level.",
            instrument="CELL-LEVEL, fixed DC rail, 5-stage inverter chain, "
                       "stage 3 measured so its input edge is cell-generated "
                       "and its load is a real cell. NEVER quoted as a chain "
                       "result.",
            why_a_separate_instrument="in the 3-bank chain t_settle is measured "
                                      "from the bank's own rail start and is "
                                      "RAIL-DELIVERY-BOUND; at N=64 the gates "
                                      "finish 65.93 ps BEFORE the rail does, so "
                                      "the chain cannot isolate cell drive.",
            variants=C["_variants"],
            worst_edge_t_set90_ps={
                k: dict(scales=v["scales"],
                        values=v["worst_t_set90_ps"]["values"],
                        ratio_x1_to_x8=v["worst_t_set90_ps"]
                        ["ratio_last_over_first"],
                        pct_change=v["worst_t_set90_ps"]["pct_change_x1_to_x8"],
                        exponent_in_s=v["worst_t_set90_ps"]["exponent_in_s"],
                        fit=v["worst_t_set90_ps"]["fit_a_plus_b_over_s"])
                for k, v in C["ANSWER"].items()},
            capacitance_decomposition=CD["decomposition"],
            shim_caveat=CD["_shim_defect"],
            B10_gate="PASSED: R2 = 0.99951 on variant A at 1.65 V, against the "
                     "pre-registered 0.98. The mechanism claim stands rather "
                     "than being withdrawn."),

        B_CHAIN_NUMBERS=dict(
            _keys=R["_time_keys"],
            N8=main_series(8), N64=main_series(64)),

        C_TRADE_AND_EXCHANGE_RATE=dict(
            ANSWER="THERE IS NO POSITIVE EXCHANGE RATE ON THIS AXIS. Every "
                   "upsized point is worse than s=1 on ALL THREE axes at once "
                   "-- slower, more energy, more area. The 'trade curve' is a "
                   "single dominated ray, not a frontier. Pareto frontier in "
                   "(level_floor, E/gate) = {s=1} at both N.",
            per_N=R["TRADE_per_N"],
            headline_N64=[dict(
                scale=v["scale"], pct_level_time=v["pct_level_floor_change"],
                pct_energy=v["pct_energy_change"],
                pct_area=v["pct_area_change"], verdict=v["verdict"])
                for v in R["TRADE_per_N"]["64"]["VS_S1"]],
            headline_N8=[dict(
                scale=v["scale"], pct_level_time=v["pct_level_floor_change"],
                pct_energy=v["pct_energy_change"],
                pct_area=v["pct_area_change"], verdict=v["verdict"])
                for v in R["TRADE_per_N"]["8"]["VS_S1"]]),

        D_SETTLING_AND_VALUE=dict(
            A1_value_failures_total=sum(t["A1_fail"] for t in tab),
            gate_nodes_checked=sum(3 * t["N"] for t in tab),
            n_rows=len(tab),
            every_row_A2_bare_pass=all(t["A2"] for t in tab),
            every_row_A2_3sigma_pass=all(t["A2_3sig"] for t in tab),
            worst_gate_pct_range=[min(t["worst_gate_pct"] for t in tab),
                                  max(t["worst_gate_pct"] for t in tab)],
            A2_margin_mV_range=[min(t["A2_mV"] for t in tab),
                                max(t["A2_mV"] for t in tab)],
            intra_class_spread_mV_max=max(
                max(max(v.values()) for v in t["intra_class_spread"].values())
                for t in tab),
            per_row=[dict(tag=t["tag"], N=t["N"], scale=t["sc_scored"],
                          A1_fail=t["A1_fail"], worst_gate_pct=t["worst_gate_pct"],
                          worst_per_bank=t["worst_per_bank"],
                          A2_margin_mV=t["A2_mV"], sep_min_mV=t["sep_min_mV"],
                          ACCEPTED=t["ACCEPTED"]) for t in tab]),

        E_MECHANISM=dict(
            LAW="t_hop = k * sqrt(C_bank_MEASURED), with k CONSTANT while "
                "C_tank moves 64x. So the hop is set by C_bank -- which IS the "
                "cells' rail-side capacitance -- and NOT by the tank. Growing "
                "the cells necessarily lengthens the hop, and no tank-sizing "
                "or switch-width choice can avoid it.",
            k_ps_per_sqrt_fF_range=[min(ks), max(ks)],
            k_spread_pct=100.0 * (max(ks) / min(ks) - 1.0),
            C_tank_range_fF=[min(cts), max(cts)],
            C_tank_span_x=max(cts) / min(cts),
            points=law,
            phase1_cross_check="Phase 1's N-sweep gives k = 12.70-13.27 "
                               "ps/sqrt(fF) over a 32x range of N, and its "
                               "exponents agree to 2.6% (C_bank ~ N^0.831, "
                               "t_hop ~ N^0.426 vs the predicted 0.415). "
                               "Phase 2 extends the SAME law to the cell-scale "
                               "axis.",
            WHY_THE_LEVER_IS_INVERTED="in CMOS, upsizing a gate pays for itself "
                                      "in the NEXT stage's load -- a local, "
                                      "linear cost, and the speed-up is real. "
                                      "In QAL the same capacitance IS the "
                                      "resonant load of the hop that charges "
                                      "the whole bank, and the hop goes as "
                                      "sqrt(LC). So a factor s of cell width "
                                      "costs sqrt(s) on the ENTIRE LEVEL while "
                                      "buying back only the fixed-load fraction "
                                      "of ONE cell's settling.",
            E2_answered_without_running_it="the pre-registered E2 control "
                                           "(tank sized from the MEASURED C) "
                                           "was NOT run. Its question -- is the "
                                           "C_tank sizing rule a confound? -- "
                                           "is answered by this law: C_tank "
                                           "varies 64x across these points "
                                           "while k stays constant to 6.7%, so "
                                           "the hop does not depend on C_tank."),

        F_THE_MATCHED_PAIR=R.get("MATCHED_PAIR_same_tank_same_switch"),

        G_WHERE_THE_SPEED_LEVER_ACTUALLY_IS=dict(
            ANSWER="THE INDUCTOR, and it is CHEAP -- which is what makes cell "
                   "upsizing not merely weak but DOMINATED.",
            at_s4_cut_L_4x=dict(
                from_tag=s4["tag"], to_tag=e3["tag"],
                L_nH=[s4["L_nH"], e3["L_nH"]],
                level_floor_ps=[s4["level_floor_ps"], e3["level_floor_ps"]],
                faster_x=s4["level_floor_ps"] / e3["level_floor_ps"],
                E_per_gate_fJ=[s4["E_g_floor"], e3["E_g_floor"]],
                energy_pct=100.0 * (e3["E_g_floor"] / s4["E_g_floor"] - 1)),
            at_s1_cut_L_4x=dict(
                from_tag=b["tag"], to_tag=e6["tag"],
                L_nH=[b["L_nH"], e6["L_nH"]],
                level_floor_ps=[b["level_floor_ps"], e6["level_floor_ps"]],
                faster_x=b["level_floor_ps"] / e6["level_floor_ps"],
                E_per_gate_fJ=[b["E_g_floor"], e6["E_g_floor"]],
                energy_pct=100.0 * (e6["E_g_floor"] / b["E_g_floor"] - 1),
                CAVEAT="E6's recycle fraction goes NEGATIVE (-11.8% vs +27.8%) "
                       "and its delivered rail droops 21% (0.9422 -> 0.7405 V), "
                       "so it has STOPPED BEING ADIABATIC and its +15.6% is NOT "
                       "an iso-swing figure. See AMENDMENT A8, including the "
                       "hypothesis I formed and then falsified.",
                iso_swing_correction_DERIVED=dict(
                    rail_V=[rail_b, rail_e6], factor=iso,
                    E_per_gate_iso_fJ=e6["E_g_floor"] * iso,
                    x_CMOS_iso=e6["E_g_floor"] * iso / CMOS_BLK,
                    speed_x=b["level_floor_ps"] / e6["level_floor_ps"],
                    exchange_speed_over_energy=(b["level_floor_ps"]
                                                / e6["level_floor_ps"])
                    / iso / (e6["E_g_floor"] / b["E_g_floor"]) * 1.0,
                    note="energy ~ V^2 applied to the MEASURED delivered "
                         "rails. A proper iso-swing point would re-run E6 at a "
                         "higher dV; that was NOT run.")),
            DOMINANCE=dict(
                _what="at the SAME L = 3.75 nH, s=1 (E6) vs s=4 (E3)",
                level_floor_ps=[e6["level_floor_ps"], e3["level_floor_ps"]],
                E_per_gate_fJ=[e6["E_g_floor"], e3["E_g_floor"]],
                total_um2_per_gate=[e6["total_um2_pg"], e3["total_um2_pg"]],
                s1_faster_x=e3["level_floor_ps"] / e6["level_floor_ps"],
                s1_cheaper_x=e3["E_g_floor"] / e6["E_g_floor"],
                s1_smaller_x=e3["total_um2_pg"] / e6["total_um2_pg"],
                VERDICT="cell upsizing is STRICTLY DOMINATED by inductor "
                        "reduction on all three axes simultaneously"),
            X10_WAS_WRONG="I pre-stated that buying the speed back with L would "
                          "cost QUADRATICALLY (45-90 fJ/gate at s=4). MEASURED "
                          "12.13 fJ/gate, i.e. +5.3% over the same-scale "
                          "L=15 row. Reducing L is a CHEAP speed lever, not an "
                          "expensive one. That is a bigger correction than it "
                          "looks: it means the axis the brief asked about is "
                          "not merely weak, it is beaten outright."),

        H_E1_LOAD_NOT_SCALED=dict(
            _what="N=64 with banks 1,2 at s=4 and bank 3 (the receiver) left "
                  "at s=1, so the measured bank drives an UNSCALED load inside "
                  "the REAL chain -- the crux's variant C, in the chain.",
            tag=e1["tag"],
            t_settle90_ps=[s4["t_set90_ps"], e1["t_set90_ps"]],
            settle_improvement_pct=100.0 * (1 - e1["t_set90_ps"]
                                            / s4["t_set90_ps"]),
            t_hop_ps=[s4["t_hop_ps"], e1["t_hop_ps"]],
            level_floor_ps=[s4["level_floor_ps"], e1["level_floor_ps"]],
            bound_by=e1["bound_by"],
            vs_s1_baseline_floor_ps=b["level_floor_ps"],
            VERDICT="the pre-stated E1 signature FIRED: bank 2's settling "
                    "improves 16.0% when its load does not scale, and the "
                    "level time still does not improve, because the level is "
                    "HOP-bound and the hop is set by bank 2's OWN bank "
                    "capacitance. Confirms the crux inside the chain."),

        I_SCORING=SC["summary"],
        I_SCORING_DETAIL=SC["scored"])

    open(os.path.join(HERE, "PHASE2_ANSWER.json"), "w").write(
        json.dumps(out, indent=1, default=str))
    print("PHASE2_ANSWER.json written")
    print()
    print("CRUX: %s" % out["A_THE_CRUX"]["ANSWER"][:200])
    print()
    print("MECHANISM: k = %.4f .. %.4f ps/sqrt(fF) (%.1f%%) while C_tank spans "
          "%.0fx" % (min(ks), max(ks), out["E_MECHANISM"]["k_spread_pct"],
                     out["E_MECHANISM"]["C_tank_span_x"]))
    print()
    print("E6 iso-swing DERIVED: %.4f fJ/gate (%.3fx CMOS) for %.3fx speed"
          % (e6["E_g_floor"] * iso, e6["E_g_floor"] * iso / CMOS_BLK,
             b["level_floor_ps"] / e6["level_floor_ps"]))
    print()
    print("SCORING: %s" % json.dumps(SC["summary"]))


if __name__ == "__main__":
    main()
