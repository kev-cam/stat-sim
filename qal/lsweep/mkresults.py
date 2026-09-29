#!/usr/bin/env python3
"""Assemble RESULTS_LSWEEP.json from rows.json + cellcmp*.json + the gate logs."""
import json, math, os

HERE = os.path.dirname(os.path.abspath(__file__))
CMOS_LEVEL_PS, CMOS_INV_PS, CMOS_INV_FJ, NC = 92.8, 34.81, 10.0831, 8
KEEP = ["L_nH", "total_um", "w_wn", "w_wp", "w_park", "dv", "ca_fF", "rs_ohm",
        "edge_ps", "tail_ps", "t_hop_ps", "t_hop_pred_ps", "IPK_uA", "IZ_uA",
        "VBPK", "VBEND", "VBOPEN", "VAEND", "VA_open", "xc_VA_open",
        "t_rail90_ps", "t_valid80_ps", "t_valid90_ps", "t_valid95_ps",
        "t_settle80_ps", "t_settle90_ps", "t_settle95_ps",
        "t_level_ps", "t_level_cons_ps",
        "settling_open_min_pct", "settling_end_min_pct", "settling_open_pct",
        "settling_end_pct", "E_hop_open_fJ", "xc_E_hop_open_fJ",
        "xc_E_hop_at_zero_fJ", "E_hop_D_fJ", "E_R_toC_fJ",
        "E_switchblock_toC_fJ", "cells_burn_fJ", "switch_related_open_fJ",
        "Q_gate_drive_fC", "E_gate_drive_fJ", "rails_net_fJ",
        "closure_Q_pct", "closure_E_pct", "identity_at_B_fJ", "xc_identity_B_fJ",
        "xc_dEhop_pct", "timestep_ps", "probe_no_zero",
        "C1_settle_end", "C1_settle90_reached", "C2_rail_drain_abs",
        "C2_rail_drain_rel_dv", "C3_swing_abs", "C3_swing_rel_dv",
        "C4_instrument", "FUNCTIONAL", "FUNCTIONAL_rel_dv", "fails"]


def main():
    R = json.load(open(os.path.join(HERE, "rows.json")))
    cc = json.load(open(os.path.join(HERE, "cellcmp.json")))
    cc2 = json.load(open(os.path.join(HERE, "cellcmp2.json")))

    def trim(r):
        return {k: r[k] for k in KEEP if k in r}

    equal = {}     # CA = committed 35.979 fF: the pre-registered experiment
    uneq = {}      # CA > CB: a labelled EXCURSION, C2 does not apply
    bad = {}
    for t, r in R.items():
        if "error" in r:
            bad[t] = r["error"]
        elif abs(r.get("ca_fF", 35.979) - 35.979) > 1e-9:
            uneq[t] = trim(r)
        else:
            equal[t] = trim(r)

    def best(pool, key, cond=lambda r: True):
        c = [(t, r) for t, r in pool.items() if cond(r) and r.get(key)]
        return min(c, key=lambda kv: kv[1][key]) if c else (None, None)

    fF = lambda r: r.get("FUNCTIONAL") == "YES"
    t_lv, r_lv = best(equal, "t_level_cons_ps", fF)
    t_lv2, r_lv2 = best(equal, "t_level_ps", fF)
    t_hp, r_hp = best(equal, "t_hop_ps", fF)
    t_any, r_any = best(equal, "t_hop_ps")
    t_ex, r_ex = best(uneq, "t_level_cons_ps")

    # measured scaling-law residuals
    law = []
    for t, r in sorted(equal.items(), key=lambda kv: -kv[1]["L_nH"]):
        if (r["total_um"] == 15.0 and r["dv"] == 1.0 and r["rs_ohm"] == 10.0
                and r["edge_ps"] == 2.0 and r["tail_ps"] == 500.0):
            L = r["L_nH"]
            cser = ((r["t_hop_ps"] * 1e-12) / math.pi) ** 2 / (L * 1e-9) * 1e15
            ron = (10.0 * r["E_switchblock_toC_fJ"] / r["E_R_toC_fJ"]
                   if r["E_R_toC_fJ"] else None)
            z0 = math.sqrt((L * 1e-9) / (cser * 1e-15))
            cond = r["E_R_toC_fJ"] + r["E_switchblock_toC_fJ"]
            law.append(dict(L_nH=L, t_hop_ps=r["t_hop_ps"],
                            t_hop_sqrtL_pred_ps=266.755223 * math.sqrt(L / 277.8),
                            ratio=r["t_hop_ps"] / (266.755223 * math.sqrt(L / 277.8)),
                            IPK_uA=r["IPK_uA"],
                            IPK_pred_uA=194.3655 * math.sqrt(277.8 / L),
                            IPK_ratio=r["IPK_uA"] / (194.3655 * math.sqrt(277.8 / L)),
                            C_ser_eff_fF=cser, Z0_ohm=z0, Ron_sw_eff_ohm=ron,
                            Q_measured=z0 / (10.0 + ron) if ron else None,
                            E_conduction_fJ=cond,
                            E_conduction_pct=100 * cond / r["E_hop_open_fJ"],
                            E_charge_residual_fJ=(r["E_hop_open_fJ"] - cond
                                                  - r["cells_burn_fJ"]),
                            VBEND=r["VBEND"],
                            VBEND_loss_vs_anchor=1 - r["VBEND"] / 0.675425))

    out = {
     "_doc": "TRACK 1 RESULT: the L-DOWN SPEED SWEEP of the QAL bank-to-bank hop on "
             "SG13G2 (PSP103, sg13lv_compat.sp). SPEED is the primary metric; energy "
             "is reported but gates nothing. Pre-registration: PRE_REGISTERED_LSWEEP.json "
             "(written before any deck existed). Protocol amendments: AMENDMENT_LSWEEP.md. "
             "Every figure below is MEASURED unless labelled DERIVED or ASSUMED.",
     "date": "2026-09-28",
     "instrument": {
      "G0a_extractor_vs_committed_mt0": "PASS, rel 0.00e+00 on all eight committed tg15p "
        "headlines (E_hop_open 8.3828171771408 fJ, VBEND 0.6758936, VBPK 0.7374377, "
        "VA_open 0.09778203952305342, cells_burn 1.6954746104994207 fJ, E_R_toC "
        "0.049543034863200004 fJ, IZ -0.3793985 uA, IPK 194.3655 uA) -- digit-identical.",
      "G0b_committed_deck_under_my_cache": "PASS, rel 0.00e+00 on the same eight. The "
        "committed deck sw_tg15p_z.cir re-run byte-identical in this workdir with a "
        "private PYMS_VAE_CACHE reproduces the committed mt0 exactly.",
      "G0c_probe_zero": "PASS under the committed rule. My generated probe deck is "
        "electrically identical to the committed one (Ipk 194.3663 uA, t_Ipk 128.113 ps, "
        "same zero bracket). Under the COMMITTED zero rule (first .prn point after the "
        "crossing, no max time step) it returns 266.7552 ps -- digit-identical to the "
        "committed 266.755223 ps. Under MY refined rule (linear interpolation of the "
        "crossing + an L-scaled max time step) it returns 265.598 ps. The 1.157 ps "
        "difference is 1.13 ps of next-point-vs-interpolated quantisation plus 0.24 ps "
        "of finer max step: the committed .prn rows sit on the SOLVER grid, not the print "
        "grid, so the committed 'true zero' is one solver step late. The refined value is "
        "used for the sweep (it is needed at small L) and costs the anchor -0.43% in t_hop "
        "and +0.16% in E_hop_open -- it moves no conclusion.",
      "G0d_non_perturbation": "PASS at 0.16% on E_hop_open, 0.07% on VBEND; the residual "
        "is entirely the 1.157 ps open-time difference above, not the added .measure lines.",
      "INSTRUMENT_DEFECT_FOUND": {
       "what": "In this Xyce build, '.measure tran <NAME> FIND <expr> AT=T' returns the "
               "waveform value at T - 1.0 ps. Constant 1.0 ps, independent of the offset, "
               "of the expression (branch current I(LT) and B-source node V(qt) behave "
               "identically), of L, and of the timestep settings.",
       "how_found": "The pre-registered C4 closure gate failed at L=3 and L=1 nH: the .mt0 "
               "reported I(LT) = +423.2 uA at the switch-open zero where the .prn shows "
               "+0.012 uA, and the 1F-integrator books agreed with the .mt0 "
               "(identity ea-esw-er at the zero = 0.08954 fJ = 0.5*L*(423.2uA)^2 exactly). "
               "diag_find.py then measured an 11-point offset ladder in one run: mt0 FIND "
               "at (t_open + 1.0 ps) = -0.0089 uA equals the .prn value at t_open; the "
               "waveform identity at the zero is 0.000023 fJ.",
       "cross_check_across_the_whole_pre_fix_sweep": "the implied lag from IZ/(dI/dt) was "
               "0.74-0.97 ps on all 14 pre-fix rows over 278x in L -- one constant, not a "
               "physics effect.",
       "fix": "every .measure AT time is requested LAG_PS = 1.0 ps late (lsw.py LAG_PS). "
               "After the fix |IZ| <= 0.021 uA on all 29 primary rows (was up to 423 uA), "
               "the .mt0 identity at the zero is <= 0.010 fJ, the independent waveform "
               "identity is <= 0.0001 fJ, mt0-vs-waveform E_hop agrees to <= 0.21%, and "
               "Q/E closure is <= 0.05%. C4 PASSES on every row.",
       "consequence_for_the_committed_campaign": "the committed decks carry the "
               "uncorrected lag. It is benign there BECAUSE the committed 'true zero' was "
               "itself ~1.1 ps late, which cancelled it (the committed row's IZ reads "
               "-0.379 uA, i.e. ~0). Two errors of opposite sign. The committed headline "
               "numbers are not materially wrong; a campaign that fixed only the zero "
               "without fixing the lag WOULD have been.",
       "status": "NOT a physics finding. Reported so no later run re-discovers it, and so "
               "the committed ledger's checkpoint arithmetic is understood."
      },
      "per_row_gates": "C4 = Q closure <= 1%, E closure <= 1%, WAVEFORM identity at the "
        "zero <= 0.02 fJ, and mt0-vs-waveform E_hop agreement <= 1%. Every reported row PASSES."
     },
     "protocol_note_C2_C3": "When dV became a parameter a mid-run patch scaled the "
        "pre-registered C2/C3 thresholds by dV. That is wrong for C3 on my own stated "
        "rationale (the 0.60 V floor is a device-Vt fact, not a fraction of the "
        "pre-charge), so refix.py restored the ABSOLUTE, pre-registered forms and takes "
        "FUNCTIONAL on them. Both readings are carried on every row "
        "(C2/C3_abs and C2/C3_rel_dv, FUNCTIONAL and FUNCTIONAL_rel_dv). The absolute "
        "form is the harsher one at dV=1.2.",
     "derived_law_check_MEASURED": law,
     "rows_equal_bank_MEASURED": equal,
     "rows_unequal_bank_EXCURSION": uneq,
     "rows_failed_extraction": bad,
     "cell_floor_MEASURED": {"cellcmp": cc, "cellcmp2": cc2},
     "headline": {
      "fastest_t_hop_any_row": dict(tag=t_any, **({k: r_any[k] for k in
          ("L_nH", "total_um", "dv", "t_hop_ps", "VBEND", "VA_open",
           "E_hop_open_fJ", "FUNCTIONAL")} if r_any else {})),
      "fastest_t_hop_FUNCTIONAL": dict(tag=t_hp, **({k: r_hp[k] for k in
          ("L_nH", "total_um", "dv", "t_hop_ps", "t_level_cons_ps", "VBEND",
           "VA_open", "E_hop_open_fJ")} if r_hp else {})),
      "fastest_t_level_FUNCTIONAL_conservative": dict(tag=t_lv, **({k: r_lv[k] for k in
          ("L_nH", "total_um", "dv", "t_hop_ps", "t_valid90_ps", "t_settle90_ps",
           "t_level_cons_ps", "t_level_ps", "VBEND", "VA_open", "E_hop_open_fJ",
           "Q_gate_drive_fC", "E_gate_drive_fJ", "rails_net_fJ")} if r_lv else {})),
      "fastest_t_level_FUNCTIONAL_settling_definition": dict(tag=t_lv2, **({k: r_lv2[k]
          for k in ("L_nH", "total_um", "dv", "t_hop_ps", "t_level_ps", "VBEND")}
          if r_lv2 else {})),
      "fastest_t_level_UNEQUAL_BANK_EXCURSION": dict(tag=t_ex, **({k: r_ex[k] for k in
          ("L_nH", "total_um", "dv", "ca_fF", "t_hop_ps", "t_valid90_ps",
           "t_settle90_ps", "t_level_cons_ps", "VBEND", "VA_open", "E_hop_open_fJ",
           "FUNCTIONAL", "fails")} if r_ex else {})),
      "comparators_ASSUMED_from_the_record": dict(
          sha_slice_cmos_level_ps=CMOS_LEVEL_PS,
          sha_slice_source="0.928 ns combinational over DEPTH 10, no flop overhead",
          cmos_inverter_ps=CMOS_INV_PS, cmos_inverter_fJ_per_cycle=CMOS_INV_FJ,
          my_independent_remeasurement="cellcmp c120: the SAME 1.12u/0.74u inverter into "
          "2 fF at 1.2 V gives t50 = 30.358 ps and t90 = 57.143 ps with a 2 ps input "
          "edge. That brackets the committed 34.81 ps anchor to 13%, the residual being "
          "input-edge slope. The anchor is used as given; my own number is the one the "
          "cell-vs-cell comparison rests on.")
     }
    }
    cf = cc2
    out["verdict"] = {
     "Q1_is_L_the_speed_knob": "YES, MEASURED and unambiguous. t_hop follows pi*sqrt(L*C) "
       "over 278x in L to within 1.7%: measured/predicted = 0.9957 at 277.8 nH falling to "
       "0.9831 at 10 nH and back to 0.9952 at 1 nH, with a fitted C_ser_eff that is flat at "
       "25.1-25.7 fF. t_hop goes 265.6 / 158.1 / 86.2 / 49.8 / 27.3 / 15.9 ps at L = 277.8 / "
       "100 / 30 / 10 / 3 / 1 nH on the committed tg15p switch. The published 'QAL is slower "
       "than CMOS' reading WAS an artefact of an energy-chosen L: the reframing is correct.",
     "Q2_is_the_HOP_faster_than_a_CMOS_logic_level": "YES. The fastest FUNCTIONAL hop measured "
       "is t_hop = 43.38 ps (L=6 nH, TG 20/40 um + 4 um park, dV=1.2), which is 0.47x the "
       "92.8 ps sha_slice CMOS logic level -- 2.14x FASTER. The fastest hop of any kind is "
       "15.86 ps, 5.9x faster than a CMOS level and 2.2x faster than the 34.81 ps CMOS "
       "inverter, but that row transfers only 40% of the rail and is NOT functional.",
     "Q3_is_a_complete_QAL_LEVEL_faster_than_a_CMOS_logic_level": "NO. The fastest FUNCTIONAL "
       "level time is t_level = 123.44 ps (conservative definition) / 115.57 ps (settling "
       "definition) at L=15 nH, TG 10/20 um + 2 um park, dV=1.2 -- 1.33x / 1.25x SLOWER than "
       "the 92.8 ps CMOS logic level and 3.5x / 3.3x slower than the 34.81 ps CMOS inverter. "
       "The hop is not the limit; the cells the hop feeds are.",
     "Q4_why_the_level_is_slower_than_the_hop_MEASURED": {
      "mechanism": "The hop delivers a RAIL; the gates on that rail then have to settle, and "
        "they run at the DELIVERED swing, not at the pre-charge. MEASURED on the committed "
        "anchor: the rail reaches 99.1% of its final value at the open checkpoint (V(bkb) "
        "0.66978 of 0.67589) but the lo-input cell output is only at 82.09% of the rail, and "
        "t_valid90 = 292.15 ps against t_hop = 266.76 ps. The cells were ALREADY the binding "
        "term in the committed, shipped row, by 25 ps, before L was touched.",
      "cell_floor_vs_delivered_swing_MEASURED_ps_to_90pct": {
        "0.4885_V": 801.3, "0.5422_V": 397.9, "0.5884_V": 252.8, "0.6196_V": 197.0,
        "0.6497_V": 160.5, "0.6754_V": 137.7, "0.800_V": 81.0, "1.000_V": 51.5,
        "1.200_V": 40.4},
      "so": "the cell floor is L-INDEPENDENT and explodes as the swing falls. Taking L down "
        "raises the loss (MEASURED Q falls 23.4 -> 1.87 from 277.8 to 1 nH), the loss eats "
        "the swing (VBEND 0.6754 -> 0.4885), and the swing slows the cells faster than the "
        "smaller L speeds the hop. t_level therefore has an INTERIOR MINIMUM: at dV=1.0 / "
        "W=15 it bottoms at 157.4 ps around L=10 nH and rises again to 316.2 ps at L=1 nH."
     },
     "Q5_the_switch_must_pass_the_current": {
      "answer": "Widening the transfer switch is NOT a route to speed, MEASURED. It buys "
        "rail drain and costs swing, time and charge.",
      "minimum_passing_width_per_L_dV1p0": {"L>=45nH": "15 um (the committed optimum)",
        "L=30nH": "30 um", "L<=10nH": "NONE in {15,30,60,120,240} um -- widening fixes the "
        "drain (VA_open 0.230 -> 0.059 at L=10) but the added switch capacitance drops the "
        "delivered swing below the 0.60 V floor (VBEND 0.588 -> 0.557)"},
      "minimum_passing_width_per_L_dV1p2": {"L=45-278nH": "15 um", "L=15-30nH": "30 um",
        "L=6-10nH": "60 um", "L<6nH": "not reached in this family"},
      "gate_charge_MEASURED": "Q_gate scales linearly with total width: 1.97 / 4.05 / 8.68 / "
        "18.46 / 38.98 fC at 15 / 30 / 60 / 120 / 240 um (0.155 fC/um), and the ideal "
        "gate-drive energy with it: 4.08 / 7.29 / 14.63 / 29.09 / 58.45 fJ. At 240 um the "
        "gate drive alone (58.4 fJ) is 6.2x the hop it enables (9.47 fJ).",
      "width_saturation_MEASURED": "at L=1 nH the loop Q saturates near 7 even at 240 um, "
        "because each doubling of W cuts the channel resistance and raises the resonant C at "
        "similar rates, so Z0=sqrt(L/C) falls as fast as R. VA_open only improves 0.598 -> "
        "0.344: at 1 nH the hop leaves a third of the rail behind at ANY width.",
      "Ipk_MEASURED": "I_pk tracks the 1/sqrt(L) prediction to 1% down to 30 nH and then "
        "falls short of it: ratio 0.925 / 0.857 / 0.750 at 10 / 3 / 1 nH (measured 948 / "
        "1602 / 2430 uA vs 1024 / 1870 / 3240 uA predicted). The switch IS the limiter."
     },
     "Q6_what_the_brief_predicted_vs_what_was_measured": {
      "20_ps_hop": "CONFIRMED as a transfer: 15.93 ps at L=1 nH (the brief's DERIVED 20 ps at "
        "1.13 nH). t_hop is real and the sqrt(L) law holds.",
      "I_pk_5.65_mA": "NOT reached: 2.43 mA measured at L=1 nH / W=15 um (the switch clips it), "
        "3.43 mA at W=240 um.",
      "loss_1.1pct_to_18pct_with_R_10_ohm": "REFUTED as a budget. The 10 ohm series R is not "
        "the limiter: MEASURED effective TG channel resistance during the hop is 96-130 ohm "
        "at W=15 um, i.e. ~12x the assumed series R, so the real Q at L=1 nH is 1.87, not the "
        "brief's 17.7, and the measured swing loss is 27.7% (not 18%) with the transfer only "
        "40% complete. DIRECT TEST: dropping RS from 10 to 1 ohm changes NOTHING -- at L=1 nH "
        "VBEND goes 0.4885 -> 0.4922 and VA_open 0.5976 -> 0.6030, while E_R falls 0.609 -> "
        "0.067 fJ and the switch block absorbs the difference (5.82 -> 6.19 fJ). The "
        "inductor's resistance is not the wall; the switch is.",
      "resistive_vs_switch_charge_swap_point": "FOUND. Conduction (series R + switch block) is "
        "8.3% of E_hop at 277.8 nH, 19.3% at 30 nH, 29.3% at 10 nH, 48.3% at 3 nH and ~101% at "
        "1 nH, while the per-op charge residual is FLAT at 5.6-6.0 fJ from 277.8 down to 30 nH "
        "and then collapses. The two swap roles between L = 10 and 3 nH, i.e. around L ~ 5 nH. "
        "(At 1 nH the bank-A-referenced residual goes NEGATIVE, -1.28 fJ, because the drive "
        "rails inject energy into the banks -- rails_net +10.9 fJ -- that E_hop_open does not "
        "book. The four-way split is not orthogonal there and is reported, not patched.)"
     },
     "Q7_the_structural_claim_reconciled": "MEASURED, and it is the most useful number here. "
       "The QAL settle-not-switch path is genuinely FASTER than CMOS switching at the SAME "
       "rail and the same cell: 137.7 vs 201.3 ps at 0.6759 V, 40.4 vs 57.1 ps at 1.2 V -- "
       "1.41-1.46x, because the pMOS is already on and the supply step feeds through to the "
       "output (at wp=4.48 um the QAL 50% point is 8.6 ps vs CMOS 15.3 ps, i.e. QAL wins the "
       "early edge outright). But the hop delivers only ~60-68% of the pre-charge to the "
       "receiving bank, and this PDK's LV rail caps the pre-charge at 1.2 V, so the QAL cells "
       "run at 0.68-0.83 V against CMOS's 1.2 V. That swing penalty is 2.41x at 0.6754 V, "
       "which swamps the 1.41x structural gain. DERIVED consequence: the crossover map's "
       "1.5-3x 'register-tax elimination' speed claim is the same size as, and opposite in "
       "sign to, the swing penalty measured here -- they approximately cancel. That is why "
       "the level times land within ~1.3x of CMOS rather than 2-3x either way.",
     "Q8_the_one_lever_that_does_beat_CMOS": "UNEQUAL BANKS. Making the source bank larger "
       "than the receiving bank raises the delivered swing (resonant voltage gain: at CA=144 "
       "fF / L=45 nH the receiving rail reaches 1.0795 V from a 1.0 V pre-charge) and that "
       "buys the cell floor directly. MEASURED best: L=3 nH, W=15 um, CA=144 fF -> t_hop "
       "38.32 ps, t_level 79.73 ps (conservative) / 72.50 ps (settling), VBEND 0.8063, "
       "E_hop_open 25.68 fJ. 79.73 ps IS faster than the 92.8 ps CMOS logic level (0.86x). "
       "BUT this is a labelled EXCURSION, not a pass: VA_open = 0.681, i.e. the source bank "
       "keeps 68% of its charge, so the pre-registered C2 transfer-completeness criterion "
       "FAILS -- by construction, because a 4x source bank is not meant to drain in one hop. "
       "C2 as pre-registered describes an EQUAL-bank hop. Whether a large-reservoir / small-"
       "level architecture recovers its charge over many hops is a CHAIN question this "
       "single-hop harness cannot answer, and it is exactly where the user's 'more tailored "
       "boundary handling' instinct points. It is NOT claimed as a result here.",
     "energy_reported_not_gating": {
      "fastest_functional_level": "E_hop_open 14.843 fJ for 8 settled cells = 1.855 fJ/cell, "
        "plus 7.714 fJ of ideal gate drive and 20.051 fJ net drawn from the ideal drive rails. "
        "Against 8 CMOS inverter cycles (8 x 10.0831 = 80.66 fJ) the hop alone is 0.184x and "
        "hop+ideal-gate-drive is 0.280x.",
      "the_speed_costs_energy": "the committed energy-optimal point is E_hop_open 8.394 fJ at "
        "t_level 291.7 ps; the fastest functional point is 14.843 fJ at t_level 123.4 ps. "
        "2.37x the level rate for 1.77x the hop energy -- so on this axis the trade is "
        "FAVOURABLE, which is the opposite of the crossover map's 'faster OR cheaper, not "
        "both' for the register-tax mechanism. It does not overturn the EXCLUSION verdict: "
        "that was taken on the COMPLETE timer ledger (23.213 fJ/bank/hop vs a pre-stated "
        "<= 12.7467 fJ, stat-sim c814e52), and this track's rails are still IDEAL sources.",
      "not_relitigated": "no energy verdict is claimed or overturned here."
     },
     "honest_limits": {
      "junction_caps_absent": "sg13lv_compat.sp zeroes ad/as/pd/ps. Every capacitance, charge "
        "and energy is a LOWER BOUND and every t_hop is optimistic. This bites hardest at the "
        "wide-switch fast points, where junction area is largest. The 43.38 ps functional hop "
        "uses a 60 um TG and is the row most exposed to this.",
      "gate_drive_is_ideal_and_the_edge_matters": "VGT/VGTP/VPK are ideal 2 ps PWL sources. "
        "MEASURED sensitivity at L=1 nH: sharpening the edge to 0.2 ps moves E_hop_open 6.38 "
        "-> 10.80 fJ (+69%) and VA_open 0.598 -> 0.338. A 60-240 um TG gate is 0.1-0.5 pF and "
        "cannot be driven in 2 ps by anything reasonable, so the fast/wide rows EXCLUDE the "
        "driver's own delay and their books are edge-sensitive.",
      "tail_length_is_load_bearing": "MEASURED: shortening the post-open tail from the "
        "committed 500 ps to 150 ps under-reports cells_burn by up to 52% (1.556 -> 0.752 fJ "
        "at L=3 nH) and at L=3 nH the outputs have not reached 90% within it (t_valid90 does "
        "not exist). The committed 500 ps tail is necessary and was kept on every primary row.",
      "cells_settle_they_do_not_switch": "the 8 metered cells have DC inputs; this is a "
        "RAIL-ARRIVAL test, not logic evaluation. Inherited from the committed harness, not "
        "fixed here. A real level also has to propagate a changing input.",
      "one_hop_not_a_chain": "single bank-to-bank hop. The register-tax / pipeline claim is "
        "not tested; per-hop charge recovery over a chain is not tested.",
      "VA_open_convention": "C2 uses the committed checkpoint C (open + 7 ps), which at small "
        "L includes post-open reflux. The ring-free value at the zero itself is carried as "
        "xc_VA_open and is markedly kinder at small L (0.332 vs 0.598 at L=1 nH). The harsher "
        "committed convention is the one gated on."
     }
    }
    json.dump(out, open(os.path.join(HERE, "RESULTS_LSWEEP.json"), "w"), indent=1)
    print("wrote RESULTS_LSWEEP.json: %d equal-bank rows, %d excursion rows, %d failed"
          % (len(equal), len(uneq), len(bad)))
    for k, v in out["headline"].items():
        if k != "comparators_ASSUMED_from_the_record":
            print("  %-46s %s" % (k, json.dumps(v)))


if __name__ == "__main__":
    main()
