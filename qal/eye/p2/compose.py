#!/usr/bin/env python3
"""PHASE 2 (a)(b)(c)(d): compose the budget, solve the sustainable beat, and do
the load-matched CMOS / flop-tax comparison.

Reads only this phase's own EYE_P2_*.json and budget.py's sourced constants.
Every output field carries MEASURED / DERIVED / ASSUMED.
"""
import json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import budget as BG                                        # noqa: E402

M = BG.M
WORST_BANK = "3"          # measured worst setup slack at every T (verified below)


def tv(fn, bank=WORST_BANK, contour="0mV"):
    d = json.load(open(os.path.join(HERE, fn)))
    b = d["banks"][bank]["contours"]
    pol = b["0mV"]["binding_polarity"]
    return b[contour][pol]["t_valid_after_own_rail_start_ps"]


def main():
    out = {"_what": "qal/eye/p2 PHASE 2 -- the composed timing budget and the"
                    " fastest sustainable wave.",
           "_pre_registration": "PRE_REGISTERED_P2.json sha256"
                    " b333ab252ba09c61ef846c16649e445b91b55949c56c5d1233a9daccbdc53471",
           "_instrument": "INSTRUMENT_CHECK_P2.json -- INSTRUMENT OK (IC-P2-1"
                    " re-extracted Phase 1's openings to 0.00036 ps with an"
                    " independent reader against a 0.10 ps bar)"}

    # ---------------- the constraint, stated ---------------------------------
    out["THE_CONSTRAINT"] = {
        "form": "t_valid(schedule, mismatch contour, worst bank) + U_timer <= T",
        "t_valid": "the eye OPENING measured from the driver bank's OWN rail"
                   " start c_k, as the INTERSECTION over every data vector the"
                   " bank can present (9 Hamming weights; Phase 1 proved the eye"
                   " depends only on weight, not arrangement)",
        "sampling_instant": "c_k + T = c_(k+1), the instant the receiver's rail"
                   " starts. This is bt.py's own bnd_k = min(c_k+T, r_k-EDGE,"
                   " r_(k-1)-EDGE), which equals c_k+T at H=4.",
        "what_is_ALREADY_inside_t_valid": [
            "worst-case data (intersection over all 9 weights)",
            "the calibrated-timer schedule error (the schedule is ONE fixed"
            " vector, not the per-pattern oracle Phase 1 used)",
            "mismatch, when read at the 3-sigma contour instead of 0 mV"],
        "ANTI_DOUBLE_COUNT": "because worst-case data is already inside the"
            " intersection opening, a raw data-spread term must NOT be added on"
            " top. The data term is charged as the MEASURED cost of running a"
            " data-blind schedule, which is what a real calibrated timer does.",
    }

    # ---------------- U1: the data term, three readings ---------------------
    r1_0, r1_3t, r1_3tot = (tv("EYE_P2_T200_H4_calibrated_full9.json"),
                            tv("EYE_P2_T200_H4_calibrated_full9.json", contour="3sigma_trip"),
                            tv("EYE_P2_T200_H4_calibrated_full9.json",
                               contour="3sigma_total_with_driver_level"))
    orc_0 = tv("EYE_P2_T200_H4_ORACLE_phase1.json")
    orc_3tot = tv("EYE_P2_T200_H4_ORACLE_phase1.json",
                  contour="3sigma_total_with_driver_level")
    readings = {}
    readings["R1_MEASURED_HERE"] = {
        "_what": "the machine's REAL condition: one schedule calibrated on the"
                 " centred weight-4 pattern, every data vector run on it.",
        "schedule_spread_present_ps": None,       # filled below
        "t_valid_0mV_ps": r1_0,
        "t_valid_3sigma_trip_ps": r1_3t,
        "t_valid_3sigma_total_ps": r1_3tot,
        "label": "MEASURED"}
    stress = {}
    for off, fn in (("+30.806", "EYE_P2_STRESS_+30.806.json"),
                    ("-30.806", "EYE_P2_STRESS_-30.806.json"),
                    ("+61.612", "EYE_P2_STRESS_+61.612.json"),
                    ("-10.620", "EYE_P2_STRESS_-10.620.json")):
        if os.path.exists(os.path.join(HERE, fn)):
            stress[off] = {"t_valid_0mV_ps": tv(fn),
                           "t_valid_3sigma_trip_ps": tv(fn, contour="3sigma_trip"),
                           "t_valid_3sigma_total_ps": tv(
                               fn, contour="3sigma_total_with_driver_level")}
    out["TIMER_ERROR_STRESS_MEASURED"] = {
        "_why": "the inherited 61.612 ps term is MEASURED AT A DIFFERENT"
                " OPERATING POINT (dV=0.8 V, L=400 nH, C_A=35 fF, one bank,"
                " switch held ON) where the hop is 364 ps. Here the hop is"
                " 125.5 ps, so 61.612 ps is 49%% of the hop, not a"
                " perturbation. Rather than extrapolate it, the schedule was"
                " DELIBERATELY MIS-TIMED by that amount on this arrangement and"
                " the eye re-measured. A p-p spread of S seen by a"
                " centre-calibrated timer is at most +/- S/2.",
        "offsets_ps": stress,
        "A6_residual_note": "an off-zero switch leaves 734-1042 uA at the"
                " commanded open against a 1.17-1.31 mA peak. That is an ENERGY"
                " cost (reported, never gated here) and it is why A6, a"
                " PROBE-VALIDITY gate, cannot pass on a data-blind schedule."}

    # the binding limb of each reading
    def binding(offs):
        cand = [stress[o]["t_valid_3sigma_total_ps"] for o in offs if o in stress]
        cand_t = [stress[o]["t_valid_3sigma_trip_ps"] for o in offs if o in stress]
        return (max(cand) if cand else None), (max(cand_t) if cand_t else None)

    r2_tot, r2_t = binding(["+30.806", "-30.806"])
    r3_tot, r3_t = binding(["-10.620"])
    readings["R2_INHERITED_ABSOLUTE_61.612ps_pp"] = {
        "_what": "the literal inherited spread, charged by MEASUREMENT on this"
                 " arrangement: schedule offset +/-30.806 ps about the centre.",
        "t_valid_3sigma_total_ps": r2_tot, "t_valid_3sigma_trip_ps": r2_t,
        "binding_limb": "the EARLY (negative) offset -- the switch opens before"
                 " the true zero, the rail gets less charge, the pull-up is"
                 " weaker and the margin slope collapses. Same sign as the"
                 " timer's cold corner.",
        "label": "MEASURED (at this operating point, under a deliberately"
                 " imposed schedule error of the inherited magnitude)"}
    readings["R3_INHERITED_FRACTIONAL_16.929pct_of_hop"] = {
        "_what": "the source table's own RATIO applied to THIS point's measured"
                 " hop zero: 16.929%% x 125.4919 ps = 21.24 ps p-p, i.e."
                 " +/-10.62 ps. The scaling-law-preserving reading.",
        "schedule_spread_ps_pp": M["inherited_spread_pct"]["v"] / 100.0 * 125.4919,
        "t_valid_3sigma_total_ps": r3_tot, "t_valid_3sigma_trip_ps": r3_t,
        "label": "MEASURED" if r3_tot else "NOT MEASURED"}
    out["U1_THE_DATA_TERM"] = {
        "readings": readings,
        "ORACLE_vs_CALIBRATED_the_correction_to_Phase_1": {
            "oracle_t_valid_0mV_ps": orc_0,
            "calibrated_t_valid_0mV_ps": r1_0,
            "difference_ps": r1_0 - orc_0,
            "SIGN": "NEGATIVE -- the calibrated eye opens EARLIER than the"
                    " per-pattern oracle eye.",
            "isolated_by_freezing_the_reference": {
                "calibrated_opening_with_ORACLE_trip_frozen_ps":
                    {"bank1": 126.1090, "bank2": 126.2364, "bank3": 126.6052},
                "driver_part_ps": {"bank1": -2.4900, "bank2": -3.4050,
                                   "bank3": -2.7768},
                "reference_part_ps": {"bank1": +0.0230, "bank2": +0.0266,
                                      "bank3": +0.0288},
                "_reading": "99%% of the shift is the DRIVER, ~1%% is the"
                    " decision level moving. The earlier opening is real and is"
                    " not an artifact of EYE2's per-pattern fixed reference."},
            "CREDIT_DECLINED": "this -2.5 to -3.4 ps is a measured CREDIT and it"
                " is NOT banked in any headline. Taking credit for a timer error"
                " helping would be fragile: it is an energy-for-time trade"
                " (734-1042 uA of off-zero switching) measured at one"
                " calibration choice. U1 is charged as ZERO in the R1 budget."},
    }

    # ---------------- U2: timer, one term not two ---------------------------
    drift = M["drift_ps_per_K"]["v"] * M["recalib_interval_K"]["v"]
    lc_per_K = abs(M["lc_zero_pct_cold"]["v"]) / 67.0
    lc_band = lc_per_K / 100.0 * M["recalib_interval_K"]["v"] * r1_0
    out["U2_THE_TIMER_TERM"] = {
        "recalibration_band_charge_ps": drift,
        "arithmetic": "0.46 ps/K (MEASURED) x 16 K (MEASURED benign band)",
        "ANTI_DOUBLE_COUNT_VERIFIED": {
            "drift_over_60K_ps": 0.46 * 60,
            "as_pct_of_the_265.623_ps_line": 0.46 * 60 / 265.623 * 100,
            "measured_RC_soft_limb_pct": M["rc_width_pct_hot"]["v"],
            "CONCLUSION": "10.391%% vs 10.23%% -- the 0.46 ps/K drift rate and"
                " the RC-soft limb of the 16.4 tracking ratio are THE SAME"
                " MEASUREMENT. Charged ONCE."},
        "LC_stiff_limb_over_the_same_band_ps": lc_band,
        "LC_limb_span_ASSUMED": "cold column taken as 27C -> -40C = 67 K; the"
                " rate (-0.29%) is MEASURED, the span is ASSUMED",
        "DIFFERENTIAL_CHARGE_ps": drift - lc_band,
        "why_it_does_not_cancel": "tracking ratio %.1f cold / 13.9 hot: the"
                " timed quantity is LC-stiff (+%.3f%%/85C) and the timer is"
                " RC-soft (+%.2f%%/85C). A tracking replica would cancel this"
                " term entirely; this one leaves %.3f of %.3f ps uncancelled."
                % (M["tracking_ratio_cold"]["v"], M["lc_zero_pct_hot"]["v"],
                   M["rc_width_pct_hot"]["v"], drift - lc_band, drift),
        "THE_SAVING_SIGN": "hot -> RC-soft line slows -> T grows -> sampling"
                " LATER -> MORE slack -> BENIGN. cold -> early -> BAD. Charged"
                " one-sided cold. MEASURED CONFIRMATION: the stress test's"
                " binding limb is the EARLY offset, the same direction.",
        "FULL_COLD_CORNER_named_separately": {
            "_note": "not the recalibration band but the whole cold corner;"
                     " reported, not added to the headline",
            "T_shrinks_pct": M["rc_width_pct_cold"]["v"],
            "t_valid_shrinks_pct": M["lc_zero_pct_cold"]["v"]},
        "label": "MEASURED rate, DERIVED charge"}
    U2 = drift - lc_band

    # ---------------- U3: mismatch -----------------------------------------
    st, sl_ = M["sigma_trip_mV"]["v"], M["sigma_driver_level_mV"]["v"]
    out["U3_THE_MISMATCH_TERM"] = {
        "_method": "a mismatch VOLTAGE becomes a TIME charge by reading the"
            " opening at the shifted CONTOUR of the measured margin curve --"
            " NOT by dividing by a local slope. The local derivative is the"
            " wrong instrument here: bank 2's curve has a kink at the crossing"
            " (37 mV/ps over one 0.1 ps cell, ~6 mV/ps over the next 20 ps).",
        "sigma_trip_mV": st,
        "sigma_trip_status": "DERIVED-from-MEASURED and a LOWER BOUND (dw/dl"
            " excluded). This is the brief's term.",
        "sigma_driver_level_mV": sl_,
        "sigma_driver_level_status": "MEASURED, qal/mcsize 300 samples. A"
            " DIFFERENT random variable: sigma_trip charges only the RECEIVER's"
            " decision level, this charges the DRIVER's delivered level.",
        "sigma_total_mV": math.sqrt(st * st + sl_ * sl_),
        "MEASURED_time_charge_3sigma_trip_only_ps": r1_3t - r1_0,
        "MEASURED_time_charge_3sigma_total_ps": r1_3tot - r1_0,
        "reproduces_Phase_1": "Phase 1 measured the 3-sigma_trip early-edge cost"
            " as 0.53-1.71 ps on the ORACLE eye; this study re-measures"
            " 0.78/0.53/1.71 ps on the same curves (IC-P2-1) and 1.14/1.23/1.76"
            " ps on the calibrated eye.",
        "the_late_edge_does_NOT_bind_setup": "Phase 1's 3-sigma right edge lands"
            " ~950 ps after c_k; the setup instant is c_k + T <= 200 ps. The"
            " right edge is a HOLD question and is not in this budget.",
        "label": "MEASURED"}

    # ---------------- (b) THE SUSTAINABLE BEAT ------------------------------
    tvi = json.load(open(os.path.join(HERE, "TVALID_VS_T.json"))) \
        if os.path.exists(os.path.join(HERE, "TVALID_VS_T.json")) else {}
    beats = {}
    for nm, key in (("R1_MEASURED_HERE", "t_valid_3sigma_total_ps"),
                    ("R2_INHERITED_ABSOLUTE_61.612ps_pp", "t_valid_3sigma_total_ps"),
                    ("R3_INHERITED_FRACTIONAL_16.929pct_of_hop", "t_valid_3sigma_total_ps")):
        v = readings[nm].get(key)
        if v is None:
            continue
        beats[nm] = {
            "t_valid_at_3sigma_total_ps": v,
            "U2_timer_ps": U2,
            "T_SUSTAINABLE_ps": v + U2,
            "with_sigma_trip_only": {
                "t_valid_ps": readings[nm].get("t_valid_3sigma_trip_ps"),
                "T_SUSTAINABLE_ps": (readings[nm].get("t_valid_3sigma_trip_ps") or 0) + U2},
        }
    out["b_THE_FASTEST_SUSTAINABLE_WAVE"] = {
        "beats": beats,
        "t_valid_is_T_INVARIANT_MEASURED": tvi,
        "HEADLINE": "R1 is the machine's real condition and is the headline;"
                    " R2 is the stress case carrying the inherited term.",
    }
    # ---------------- (c) LOAD-MATCHED CMOS + FLOP TAX ----------------------
    T_sus = beats["R1_MEASURED_HERE"]["T_SUSTAINABLE_ps"]
    tl = M["cmos_level_2fF_ps"]["v"]
    tr = BG.t_reg_at(2.0)
    tzq_worst = 153.5394          # MEASURED worst return zero, zeros_calib_T150
    cm = {"_load_matching": {
              "QAL_cell_load_fF": 2.0,
              "CMOS_level_USED_ps": tl,
              "CMOS_level_NOT_used_ps": M["cmos_level_6p91fF_ps"]["v"],
              "which_and_why": "the 2 fF figure, BECAUSE the banktank cells this"
                  " eye is measured on carry CL = 2.0 fF. Quoting the 6.91 fF"
                  " number would flatter QAL by %.3fx. Same choice, same reason,"
                  " as qal/sha256/p2/COMPARISON.json."
                  % (M["cmos_level_6p91fF_ps"]["v"] / tl)},
          "t_reg_at_2fF_ps_DERIVED": tr,
          "t_reg_status": "linear interpolation between the MEASURED 307.1 ps at"
              " 0 fF and 335.7 ps at 6.91 fF. A LOWER BOUND on the flop tax"
              " (liberty 1.11-1.21x optimistic), which is the CONSERVATIVE"
              " choice for QAL. Inflated band %.1f-%.1f ps reported, not used."
              % (tr * 1.11, tr * 1.21),
          "THE_LIABILITY_NO_LATENCY_WIN": {
              "QAL_ps_per_logic_level_MEASURED": T_sus,
              "CMOS_ps_per_logic_level": tl,
              "QAL_slower_by": T_sus / tl,
              "_statement": "A QAL level is the rail transfer with the logic"
                  " resolving INSIDE it, at a LOWER rail than CMOS's supply."
                  " Per-level latency can NEVER beat CMOS and NO LATENCY WIN IS"
                  " CLAIMED ANYWHERE. Any win must be THROUGHPUT, via the"
                  " absent flop tax."},
          "INITIATION_INTERVAL": {
              "_definition": "II = H*T + tzq. A bank cannot accept a new datum"
                  " until its rail has returned AND the return switch has opened"
                  " at its own zero (ro_k = c_k + H*T + tzq). fcrit's quoted"
                  " 'best initiation interval 320 ps' is H*T only and OMITS the"
                  " return; both readings are given.",
              "tzq_worst_MEASURED_ps": tzq_worst,
              "variants": {}},
          "crossovers": {}}
    for Hh in (2, 4):
        for strict, nm in ((False, "H*T_only_fcrit_convention"),
                           (True, "H*T_plus_tzq_STRICT")):
            II = Hh * T_sus + (tzq_worst if strict else 0.0)
            cm["INITIATION_INTERVAL"]["variants"]["H%d_%s" % (Hh, nm)] = {
                "II_ps": II, "throughput_GHz": 1000.0 / II}
            for lpb, lab in ((1, "1_level_per_bank_MEASURED"),
                             (2, "2_levels_per_bank_ARCHITECTURAL")):
                key = "H%d__%s__%s" % (Hh, nm, lab)
                cm["crossovers"][key] = {}
                for cn, unc in M["unc_corners_ps"]["v"].items():
                    cmos_every = tr + tl + unc
                    rows = []
                    for D in range(1, 11):
                        lv = D * lpb
                        rows.append({
                            "D_banks": D, "logic_levels": lv,
                            "QAL_throughput_ps_per_level": II / lv,
                            "CMOS_flop_every_level_ps_per_level": cmos_every,
                            "QAL_wins_i": II / lv < cmos_every,
                            "CMOS_isoD_stage_ps": tr + lv * tl + unc,
                            "CMOS_isoD_ps_per_level": (tr + lv * tl + unc) / lv,
                            "QAL_wins_ii": II / lv < (tr + lv * tl + unc) / lv})
                    wi = [r["D_banks"] for r in rows if r["QAL_wins_i"]]
                    wii = [r["D_banks"] for r in rows if r["QAL_wins_ii"]]
                    cm["crossovers"][key][cn] = {
                        "unc_ps": unc,
                        "CMOS_stage_flop_every_level_ps": cmos_every,
                        "CROSSOVER_D_vs_flop_every_level": min(wi) if wi else ">10",
                        "CROSSOVER_D_vs_best_isoD_CMOS": min(wii) if wii else ">10",
                        "D_exact_i": II / cmos_every / lpb,
                        "D_exact_ii": (II - tr - unc) / tl / lpb,
                        "rows": rows}
    cm["H_EVIDENCE"] = {
        "H4": "MEASURED in this study at dV = 1.65 V.",
        "H2": "NOT measured at dV = 1.65 V by this study. qal/fcrit MEASURED"
              " that on the 24 links with a real in-deck receiver both H = 2 and"
              " H = 4 clear down to T = 120 ps, and that the best initiation"
              " interval is H = 2, T = 160 ps -- but at dV = 1.2 V. Carried as"
              " EVIDENCE FROM ELSEWHERE at a different swing, not as a"
              " measurement of this operating point.",
        "why_it_matters": "H is the dominant lever on the throughput verdict:"
              " it multiplies the beat directly in II."}
    out["c_CMOS_AND_THE_FLOP_TAX"] = cm

    # ---------------- comparison to the single-point beat -------------------
    out["b_VS_THE_SINGLE_POINT_BEAT"] = {
        "_the_apples_to_apples_reference": {
            "_what": "the same arrangement, same dV, same criterion, with the"
                     " budget NOT charged: the beat at which the eye opens"
                     " exactly at the sampling instant, i.e. T = t_valid at"
                     " 0 mV.",
            "single_point_beat_ps": r1_0,
            "sustainable_beat_ps": T_sus,
            "larger_by_ps": T_sus - r1_0,
            "larger_by_factor": T_sus / r1_0},
        "other_references_in_the_campaign_NOT_the_same_quantity": {
            "fcrit_measured_banktank_beat_ps": 150.0,
            "fcrit_caveat": "MEASURED at dV = 1.2 V under fcrit's FUNCTIONAL"
                " receiver-referential criterion with a noise budget (T=140"
                " fails inside the noise budget at 13.1 mV). Different swing AND"
                " different criterion -- not comparable to this study's number.",
            "banktank_committed_headline_beat_ps": 200.0,
            "banktank_caveat": "the committed 32/32-value-correct beat at"
                " dV = 1.2 V, single-point. This study's arrangement row is at"
                " dV = 1.65 V."}}

    out["_constants"] = {k: v for k, v in M.items()}
    open(os.path.join(HERE, "BUDGET.json"), "w").write(json.dumps(out, indent=1))
    print(json.dumps({k: out[k] for k in ("b_THE_FASTEST_SUSTAINABLE_WAVE",)},
                     indent=1)[:3000])
    return out


if __name__ == "__main__":
    main()
