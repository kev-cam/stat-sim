#!/usr/bin/env python3
"""PHASE 2 (a)(b)(c)(d) -- COMPOSE THE TIMING BUDGET, FIND THE FASTEST
SUSTAINABLE WAVE, AND COMPARE AGAINST LOAD-MATCHED CMOS.

Pure arithmetic on MEASURED terms.  Every constant below carries its source.
No constant is re-derived here and none is taken from the brief without its
provenance having been reproduced in INSTRUMENT_CHECK_P2.json.
"""
import json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))

# ============================== MEASURED CONSTANTS, each with its source =====
M = {}

# --- the eye / the arrangement (Phase 1 of this study, qal/eye) -------------
M["sigma_trip_mV"] = dict(v=6.441, label="DERIVED-from-MEASURED", src=
    "qal/vtaudit via qal/fcrit_skept: sqrt((0.4779*5.766)^2+(0.4630*12.574)^2)"
    " = 6.4409 mV. A LOWER BOUND -- dw/dl excluded, stated on AUDIT.md's face.")
M["sigma_driver_level_mV"] = dict(v=22.4, label="MEASURED", src=
    "qal/mcsize/README.md, 300 MC samples: exit HIGH-class level"
    " 0.6618-0.6657 V +/- 19.4-22.4 mV. Worst taken. This is the DRIVER's"
    " delivered-level mismatch, a DIFFERENT random variable from sigma_trip,"
    " which charges only the RECEIVER's decision level.")

# --- the timer (qal/timer) --------------------------------------------------
M["drift_ps_per_K"] = dict(v=0.46, label="MEASURED", src=
    "qal/timer/RESULTS.json /tracking/drift_rate_ps_per_K")
M["recalib_interval_K"] = dict(v=16.0, label="MEASURED-BAND", src=
    "qal/timer/README.md: +/-16 K between calibrations holds the"
    " measured-benign band.")
M["lc_zero_pct_hot"] = dict(v=0.736, label="MEASURED", src=
    "qal/timer/RESULTS.json /tracking/zero_fractional/to_85C -- the LC-STIFF limb")
M["rc_width_pct_hot"] = dict(v=10.23, label="MEASURED", src=
    "qal/timer/RESULTS.json /tracking/width_fractional/to_85C -- the RC-SOFT limb")
M["tracking_ratio_cold"] = dict(v=16.4, label="MEASURED", src=
    "qal/timer/RESULTS.json /tracking/tracking_ratio/cold")
M["rc_width_pct_cold"] = dict(v=-4.82, label="MEASURED", src=
    "qal/timer/README.md loaded timer width N=9 cold column 265.546 (-4.82%)")
M["lc_zero_pct_cold"] = dict(v=-0.29, label="MEASURED", src=
    "qal/timer/README.md ideal-probe zero cold column 264.842 (-0.29%)")

# --- the inherited data term and its provenance (reproduced IC-P2-2) -------
M["inherited_spread_ps"] = dict(v=61.612, label="MEASURED-ELSEWHERE", src=
    "qal/qal_bankN_zcs.json max-min over the 9 Hamming weights."
    " OPERATING POINT: dV=0.8 V, L=400 nH, C_A=35.0025 fF, ONE bank, switch"
    " HELD ON. NOT this eye's operating point (dV=1.65, L=15 nH,"
    " C_tank=359.79 fF, 4 cascaded banks, switch opened at the true ZCS).")
M["inherited_spread_pct"] = dict(v=16.9294122, label="MEASURED-ELSEWHERE", src=
    "same table: 61.612 / mean(t_zcs) = 61.612 / 363.9347 ps")

# --- CMOS and the flop tax --------------------------------------------------
M["cmos_level_2fF_ps"] = dict(v=57.143, label="MEASURED", src=
    "qal/sha256/p2/COMPARISON.json CMOS_level_at_2fF_ps, from qal/synth/threeway."
    " THIS is the load-matched one: the banktank cells carry CL = 2.0 fF.")
M["cmos_level_6p91fF_ps"] = dict(v=94.174, label="MEASURED", src=
    "same file, CMOS_level_at_6p91fF_ps -- the 6.91 fF convention. Quoting it"
    " here would flatter QAL by 1.648x and it is NOT used in the verdict.")
M["t_reg_0fF_ps"] = dict(v=307.1, label="MEASURED", src=
    "qal/restore5, OpenSTA on the vendor liberty, sg13g2_dfrbpq_1")
M["t_reg_6p91fF_ps"] = dict(v=335.7, label="MEASURED", src="same")
M["t_reg_20fF_ps"] = dict(v=390.0, label="MEASURED", src="same")
M["liberty_optimism"] = dict(v=[1.11, 1.21], label="MEASURED", src=
    "qal/restore5: liberty is 1.11-1.21x OPTIMISTIC vs the transistor-level"
    " CLK->Q 258.9-302.25 ps, so t_reg is a LOWER BOUND on the flop tax --"
    " which is the CONSERVATIVE choice for QAL.")
M["unc_corners_ps"] = dict(v={"ideal": 0, "tree": 100, "flow": 250},
    label="NAMED-CORNERS", src="qal/restore5/PRE_REGISTERED.json")


def t_reg_at(cl_fF):
    """DERIVED: linear interpolation between the MEASURED 0 and 6.91 fF points."""
    return (M["t_reg_0fF_ps"]["v"] + (cl_fF / 6.91) *
            (M["t_reg_6p91fF_ps"]["v"] - M["t_reg_0fF_ps"]["v"]))


# ============================== (a) CHARGE THE UNCERTAINTIES ================
def compose(t_valid_cal, t_valid_oracle, slope_mV_per_ps, T, hop_zcs_ps,
            measured_sched_spread_ps):
    """All four brief terms, charged against the eye.  Returns one budget dict.

    t_valid_cal     -- MEASURED eye opening after own rail start, CALIBRATED
                       schedule, intersection over data patterns, worst bank
    t_valid_oracle  -- the same on Phase 1's per-pattern ORACLE schedule
    slope           -- MEASURED margin slope at the opening (mV/ps)
    hop_zcs_ps      -- MEASURED rail-transfer zero at this operating point
    measured_sched_spread_ps -- MEASURED p-p spread of that zero over the data
    """
    B = {}

    # ---- U1 DATA-DEPENDENT SPREAD ------------------------------------------
    # The ONLY legitimate extra charge is oracle -> calibrated.  The worst-case
    # data is ALREADY inside both t_valid figures (both are intersections over
    # every Hamming weight), so charging a raw spread on top would double count.
    d_meas = t_valid_cal - t_valid_oracle
    sens = (d_meas / measured_sched_spread_ps) if measured_sched_spread_ps else None
    B["U1_data"] = {
        "_rule": "charge ONLY the oracle->calibrated degradation; the worst-case"
                 " data is already inside the intersection opening (anti-double-count,"
                 " pre-registered B3/U1)",
        "R1_MEASURED_HERE_ps": d_meas,
        "R1_source": "t_valid(calibrated) - t_valid(oracle), both intersections"
                     " over all data patterns, same T, same arrangement",
        "measured_schedule_spread_ps": measured_sched_spread_ps,
        "sensitivity_ps_eye_per_ps_schedule": sens,
        "R2_INHERITED_ABSOLUTE_ps": (sens * M["inherited_spread_ps"]["v"]
                                     if sens is not None else None),
        "R2_note": "the literal 61.612 ps schedule error transferred through the"
                   " MEASURED sensitivity above. DERIVED, and the 61.612 ps is"
                   " MEASURED AT A DIFFERENT OPERATING POINT (dV=0.8/L=400nH/35fF).",
        "R3_INHERITED_FRACTIONAL_ps": (
            sens * M["inherited_spread_pct"]["v"] / 100.0 * hop_zcs_ps
            if sens is not None else None),
        "R3_note": "the source table's own RATIO 16.9294%% applied to THIS point's"
                   " measured hop zero %.4f ps = %.4f ps of schedule error,"
                   " transferred through the same sensitivity. This is the"
                   " scaling-law-preserving reading."
                   % (hop_zcs_ps, M["inherited_spread_pct"]["v"] / 100.0 * hop_zcs_ps),
        "R3_schedule_error_ps": M["inherited_spread_pct"]["v"] / 100.0 * hop_zcs_ps,
    }

    # ---- U2 TIMER DRIFT (one term, not two) --------------------------------
    drift = M["drift_ps_per_K"]["v"] * M["recalib_interval_K"]["v"]
    # the LC-stiff limb over the same band, assuming the cold column spans
    # 27C -> -40C = 67 K (NAMED assumption, reported)
    lc_per_K = abs(M["lc_zero_pct_cold"]["v"]) / 67.0
    lc_over_band = lc_per_K / 100.0 * M["recalib_interval_K"]["v"] * t_valid_cal
    B["U2_timer"] = {
        "_rule": "0.46 ps/K and the +10.23%/60K RC-soft limb are THE SAME"
                 " MEASUREMENT (0.46*60/265.623 = 10.391% vs 10.23%), so the"
                 " drift and the tracking ratio are charged ONCE, not twice"
                 " (pre-registered B3/U2, verified IC-P2-3).",
        "recalibration_band_charge_ps": drift,
        "one_sided_because": "hot -> RC-soft line slows -> T grows -> sampling"
                             " LATER -> MORE slack -> BENIGN. cold -> early ->"
                             " THE BAD DIRECTION. Only cold is charged.",
        "LC_stiff_limb_over_same_band_ps": lc_over_band,
        "LC_limb_assumption": "cold column taken as 27C->-40C = 67 K; ASSUMED span,"
                              " the rate itself (-0.29%) is MEASURED",
        "differential_charge_ps": drift - lc_over_band,
        "why_it_does_not_cancel": "tracking ratio %.1f (cold): the timed quantity"
                                  " is LC-stiff (%.3f%%/85C) while the timer is"
                                  " RC-soft (%.2f%%/85C). A perfectly tracking"
                                  " replica would cancel this term; this one"
                                  " leaves %.3f ps of the %.3f ps uncancelled."
                                  % (M["tracking_ratio_cold"]["v"],
                                     M["lc_zero_pct_hot"]["v"],
                                     M["rc_width_pct_hot"]["v"],
                                     drift - lc_over_band, drift),
        "FULL_COLD_CORNER_named_separately": {
            "_what": "not the recalibration band but the whole cold corner",
            "T_shrinks_by_ps": abs(M["rc_width_pct_cold"]["v"]) / 100.0 * T,
            "t_valid_shrinks_by_ps": abs(M["lc_zero_pct_cold"]["v"]) / 100.0 * t_valid_cal,
            "net_slack_loss_ps": (abs(M["rc_width_pct_cold"]["v"]) / 100.0 * T -
                                  abs(M["lc_zero_pct_cold"]["v"]) / 100.0 * t_valid_cal)},
    }

    # ---- U3 MISMATCH, converted to TIME through the MEASURED slope ---------
    st, sl_ = M["sigma_trip_mV"]["v"], M["sigma_driver_level_mV"]["v"]
    s_tot = math.sqrt(st * st + sl_ * sl_)
    B["U3_mismatch"] = {
        "_rule": "a mismatch VOLTAGE becomes a TIME charge only through the"
                 " MEASURED margin slope at the opening.",
        "margin_slope_mV_per_ps_MEASURED": slope_mV_per_ps,
        "sigma_trip_mV": st,
        "sigma_driver_level_mV": sl_,
        "sigma_total_mV": s_tot,
        "charge_3sigma_trip_only_ps": 3 * st / slope_mV_per_ps,
        "charge_3sigma_total_ps": 3 * s_tot / slope_mV_per_ps,
        "note": "sigma_trip alone is the brief's term and is a LOWER bound"
                " (dw/dl excluded). sigma_total adds the MEASURED driver"
                " delivered-level sigma from qal/mcsize and is the physically"
                " complete one. Both reported; the headline uses sigma_total.",
    }

    # ---- U4 EXIT RECEIVER: zero ps, a CELL CONSTRAINT ----------------------
    B["U4_exit_receiver"] = {
        "time_charge_ps": 0.0,
        "_what": "a PRECONDITION, not a budget term (pre-registered B3/U4).",
        "MEASURED": "qal/mcsize: 300 MC samples at the chain exit -- RX_SKEW"
                    " (0.15 um-p / 1.48 um-n, trip 0.4595 V) 0/300 failures;"
                    " RX_STD (1.12 um-p / 0.74 um-n, trip 0.6452 V) 191/300"
                    " failures = 36.33% yield [30.9, 42.1] 95% CI.",
        "THE_PRECONDITION": "every sustainable-beat number here is conditional on"
                            " the EXIT receiver being the SKEWED cell. With the"
                            " standard cell the QAL->synchronous boundary is a"
                            " coin flip at ANY beat and timing is not the"
                            " binding constraint.",
        "independent_confirmation": "qal/mcsize also measured 3694/3900 pull-UP"
                            " gate-instance failures vs 0/3300 pull-DOWN at the"
                            " open instant -- confirming, under mismatch and on a"
                            " different instrument, this study's measured result"
                            " that the binding polarity is HIGH at every bank.",
    }

    # ---- TOTALS -------------------------------------------------------------
    for tag, u1 in (("R1", B["U1_data"]["R1_MEASURED_HERE_ps"]),
                    ("R2", B["U1_data"]["R2_INHERITED_ABSOLUTE_ps"]),
                    ("R3", B["U1_data"]["R3_INHERITED_FRACTIONAL_ps"])):
        if u1 is None:
            continue
        u2 = B["U2_timer"]["differential_charge_ps"]
        u3t = B["U3_mismatch"]["charge_3sigma_total_ps"]
        u3s = B["U3_mismatch"]["charge_3sigma_trip_only_ps"]
        B["TOTAL_" + tag] = {
            "U1_data_ps": u1, "U2_timer_ps": u2,
            "U3_mismatch_3sigma_total_ps": u3t,
            "linear_sum_ps": u1 + u2 + u3t,
            "linear_sum_with_sigma_trip_only_ps": u1 + u2 + u3s,
            "_composition_rule": "LINEAR SUM is the headline: U1 and U2 are"
                " worst-case systematics (a given data vector, a given"
                " temperature), not independent Gaussians, so they add. Only U3"
                " is random. The RSS alternative is reported for contrast and is"
                " NOT the headline.",
            "RSS_alternative_ps": math.sqrt(u1 * u1 + u2 * u2 + u3t * u3t),
        }
    return B


# ============================== (c) CMOS + FLOP TAX =========================
def cmos(II_ps, T_ps, levels_per_bank=1, cl_fF=2.0):
    tl = M["cmos_level_2fF_ps"]["v"]
    tr = t_reg_at(cl_fF)
    out = {"_load_matched_to": "CL = %.1f fF, the banktank cell load" % cl_fF,
           "cmos_level_ps_USED": tl,
           "cmos_level_ps_NOT_used_6p91fF": M["cmos_level_6p91fF_ps"]["v"],
           "flatter_factor_if_misquoted": M["cmos_level_6p91fF_ps"]["v"] / tl,
           "t_reg_at_matched_load_ps_DERIVED": tr,
           "t_reg_inflated_band_ps": [tr * 1.11, tr * 1.21],
           "QAL_beat_ps": T_ps, "QAL_initiation_interval_ps": II_ps,
           "levels_per_bank": levels_per_bank,
           "THE_LIABILITY_per_level_latency": {
               "QAL_ps_per_level": T_ps / levels_per_bank,
               "CMOS_ps_per_level": tl,
               "QAL_is_SLOWER_by": (T_ps / levels_per_bank) / tl,
               "_statement": "A QAL level is the rail transfer with the logic"
                   " resolving INSIDE it, at a LOWER rail than CMOS's supply."
                   " Per-level latency can never beat CMOS. NO LATENCY WIN IS"
                   " CLAIMED. Any win must be THROUGHPUT via the absent flop tax."},
           "corners": {}}
    for cn, unc in M["unc_corners_ps"]["v"].items():
        rows = []
        for D in range(1, 11):
            lv = D * levels_per_bank        # logic levels covered by D banks
            # (i) CMOS flopped EVERY level
            cm_every = tr + tl + unc
            qal_per_level = II_ps / lv
            # (ii) best iso-D CMOS: one flop every `lv` levels
            cm_isoD = tr + lv * tl + unc
            rows.append({
                "D_banks": D, "logic_levels": lv,
                "QAL_throughput_time_per_level_ps": qal_per_level,
                "CMOS_flop_every_level_ps_per_level": cm_every,
                "QAL_wins_vs_flop_every_level": qal_per_level < cm_every,
                "CMOS_isoD_stage_ps": cm_isoD,
                "CMOS_isoD_ps_per_level": cm_isoD / lv,
                "QAL_wins_vs_isoD": qal_per_level < cm_isoD / lv,
                "QAL_latency_ps": D * T_ps,
                "CMOS_isoD_latency_ps": cm_isoD,
            })
        d_i = [r["D_banks"] for r in rows if r["QAL_wins_vs_flop_every_level"]]
        d_ii = [r["D_banks"] for r in rows if r["QAL_wins_vs_isoD"]]
        out["corners"][cn] = {
            "unc_ps": unc,
            "CMOS_stage_flop_every_level_ps": tr + tl + unc,
            "CROSSOVER_D_vs_flop_every_level": (min(d_i) if d_i else None),
            "CROSSOVER_D_vs_best_isoD_CMOS": (min(d_ii) if d_ii else None),
            "D_exact_vs_flop_every_level": II_ps / (tr + tl + unc) / levels_per_bank,
            "D_exact_vs_isoD": ((II_ps - tr - unc) / tl / levels_per_bank
                                if tl else None),
            "rows_D_1_to_10": rows}
    return out


if __name__ == "__main__":
    print(json.dumps({k: v for k, v in M.items()}, indent=1)[:200])
