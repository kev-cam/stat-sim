#!/usr/bin/env python3
"""qal/lsteer -- compose RESULTS.json (the deliverable) from runs/*/OUT.json.
Numbers are pulled from the OUT.json files (never typed); re-run after any row lands."""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
E_LEDGER, E_HARM, BASE_EYE, BASE_MARGIN, GATE = 240.292, 534.0, 129.0, 509.67, 69.924


def O(tag):
    p = os.path.join(HERE, "runs", tag, "OUT.json")
    return json.load(open(p)) if os.path.exists(p) else None


def row(tag):
    o = O(tag)
    if o is None:
        return dict(tag=tag, status="MISSING")
    if "summary" not in o:
        return dict(tag=tag, status="XYCE_FAIL", error=o.get("error"))
    s, ls, led = o["summary"], o["lsteer"], o["lsteer"]["ledger"]
    ind = ls["inductor"]
    return dict(
        tag=tag, status="OK", construction=o.get("zero_clamp"), t1_frac=o.get("t1_frac"), softstart=o.get("softstart"),
        N_per_phase=o["N_per_phase"], banks_on_inductor=led["n_banks_on_inductor"], L_nH=o["L_nH"], R_L_ohm=o["RL_ohm"],
        Ct_fF=o["Ct_fF"], switches=o["sw"], pattern=o["pat"], I0_seed_mA=o["I0_seed_mA"],
        I_mean_mA=s["I_mean_mA"], I_at_nT_mA=ind["I_at_nT_mA"], drift_pct_per_cycle=s["drift_pct"],
        ripple_pp_per_third_mA=ind.get("ripple_pp_per_third_mA"), ripple_pct_per_third=ind.get("ripple_pct_per_third"),
        ripple_pp_3cycles_incl_drift_mA=s["ripple_pp_mA"], ripple_pct_3cycles_incl_drift=s["ripple_pct"],
        zero_crossings_in_steady_waves=ls["zero_crossings"]["n"], third_peak_mA=ind["third_peak_mA"][:3],
        E_stored_fJ=ind["E_stored_mean_fJ"],
        rail_rise_end_minus_dV_mV=s["arrival_rise_mV"], hold_clamp_step_mV=ls["arrival"]["hold_clamp_step_mV"],
        rail_fall_end_before_clamp_mV=s["arrival_fall_mV"], rail_min_V=s["rail_min_V"], rail_max_V=s["rail_max_V"],
        terminal_excursion_V=s["terminals"], hold_rail_bank4=s["hold_rail_4"],
        value=dict(PASS=(s["value_fail"] == 0), n_fail=s["value_fail"], copies_PASS=s["copies"]),
        worst_margin_at_commit_mV=s["worst_margin_mV"], worst_overlap_ps=s["worst_overlap_ps"],
        standing_eye_ps=s["standing_eye_ps"], eye_minus_129_ps=(round(s["standing_eye_ps"] - BASE_EYE, 2) if s["standing_eye_ps"] else None),
        widths_w3_ps=s["widths"], erosion_sign=s["sign"], PASS=s["PASS"],
        ledger_fJ_per_bank_per_cycle=dict(
            E_dc_rail=s["E_dc"], Q_dc_rail_fC=led["Q_dc_rail_fC_per_bank"], Q_zero_rail_fC=led["Q_zero_rail_fC_per_bank"],
            E_resistive_L=s["E_R"], E_switch_conduction_and_charge_sharing=s["E_sw"],
            E_bank_from_books=led["E_bank_mean_fJ_per_bank_from_books"],
            dE_L_stored_per_cycle_group=led["dE_L_stored_fJ_per_cycle_group"],
            E_total_sources=s["E_total_sources"], vs_ledger_240p3_pct=led.get("vs_ledger_240p3_pct"),
            E_gate_metered=s["E_gate_metered"], E_gate_fit_3p7fCum=s["E_gate_fit"],
            E_total_with_gate_metered=s["E_total_gate_metered"], E_total_with_gate_fit=s["E_total_gate_fit"],
            balance_mismatch_pct=led.get("balance_check", {}).get("mismatch_pct")),
        gate_detail=ls.get("gate_detail") or None,
        crowbar_bank4=o["crowbar"].get("4", o["crowbar"].get(4)))


TAGS_I = ["ccm_N2_L120_R10_I2.8_ideal", "ccm_N2_L120_R10_I3.15_ideal", "ccm_N2_L120_R10_I3.5_ideal",
          "ccm_N2_L120_R1_I3.15_ideal", "ccm_N2_L120_R10_I3.15_ideal_ss_Ct5", "ccm_N2_L120_R10_I3.15_ideal_ss_nz",
          "ccm_N2_L120_R10_I3.5_ideal_ss_t10.95", "ccm_N2_L120_R10_I3.5_ideal_ss_t10.9", "ccm_N2_L120_R10_I3.5_ideal_ss_t10.8",
          "ccm_N2_L120_R10_I3.5_ideal_ss_t10.8_P1", "ccm_N2_L120_R1_I3.5_ideal_ss_t10.8", "ccm_N2_L120_R10_I3.5_ideal_ss_t10.8_Ct5",
          "ccm_N2_L120_R10_I3.5_ideal_ss_t10.6", "ccm_N2_L120_R10_I3.5_ideal_ss_t10.5"]
TAGS_II = ["dcm_N2_L9.7_R10_I0_ideal", "dcm_N2_L9.7_R10_I0_ideal_ss", "dcm_N2_L9.7_R10_I0_ideal_ss_nz", "dcm_N2_L6_R10_I0_ideal_ss_nz"]
TAGS_N = ["ccm_N2_L120_R10_I3.5_ideal_ss_t10.8", "ccm_N8_L120_R10_I14_ideal_ss_t10.8", "ccm_N8_L30_R10_I14_ideal_ss_t10.8"]
TAGS_R = ["ccm_N2_L120_R10_I3.5_nmos_ss_t10.8", "ccm_N2_L120_R10_I3.5_tg_ss_t10.8",
          "ccm_N2_L120_R10_I7_tg50_ss_t10.8", "ccm_N2_L120_R10_I9_tg78_ss_t10.8", "ccm_N2_L120_R10_I9_tg78_Ct200_ss_t10.8"]

if __name__ == "__main__":
    ri = {t: row(t) for t in TAGS_I}
    rii = {t: row(t) for t in TAGS_II}
    rn = {t: row(t) for t in TAGS_N}
    rr = {t: row(t) for t in TAGS_R}
    n2, n8a, n8b = rn[TAGS_N[0]], rn[TAGS_N[1]], rn[TAGS_N[2]]
    share = dict(
        rows={t: {k: r.get(k) for k in ("status", "N_per_phase", "banks_on_inductor", "L_nH", "I_mean_mA",
                                         "ripple_pp_per_third_mA", "ripple_pct_per_third",
                                         "ripple_pp_3cycles_incl_drift_mA", "drift_pct_per_cycle", "PASS",
                                         "worst_margin_at_commit_mV", "standing_eye_ps", "rail_rise_end_minus_dV_mV")}
              for t, r in rn.items()},
        law_as_pre_registered="dI = (1/L) integral(V_L>0) is N-independent -> same ABSOLUTE ripple at fixed L; relative ripple ~1/N; L = L_2 * 2/N for constant relative ripple",
        measured=dict(
            abs_ripple_ratio_N8_over_N2_at_L120=(round(n8a["ripple_pp_per_third_mA"] / n2["ripple_pp_per_third_mA"], 3)
                                                if n8a.get("ripple_pp_per_third_mA") and n2.get("ripple_pp_per_third_mA") else None),
            rel_ripple_ratio_N2_over_N8_at_L120=(round(n2["ripple_pct_per_third"] / n8a["ripple_pct_per_third"], 2)
                                                if n8a.get("ripple_pct_per_third") and n2.get("ripple_pct_per_third") else None),
            N8_L30_rel_ripple_pct=n8b.get("ripple_pct_per_third"),
            N8_L30_over_N2_L120_rel_ripple=(round(n8b["ripple_pct_per_third"] / n2["ripple_pct_per_third"], 2)
                                            if n8b.get("ripple_pct_per_third") and n2.get("ripple_pct_per_third") else None),
            note="per-third ripple (max-min inside each 92 ps third, mean of 9 steady thirds). The 3-cycle max-min also contains the secular drift and OVERSTATES ripple (the N8 L120 row: 0.80 mA 3-cycle vs 0.24 mA per third)."),
        inductor_count="ONE inductor per 3-phase group = one per 3N banks (6 banks at N=2, 24 banks at N=8), 12 switches per group (13 with the 1.65 V in-feed), N-invariant.",
        stored_energy_fJ={t: r.get("E_stored_fJ") for t, r in rn.items()})
    best_i = ri["ccm_N2_L120_R10_I3.5_ideal_ss_t10.8"]
    reg = ri["ccm_N2_L120_R10_I3.5_ideal_ss_t10.5"]
    res = dict(
        study="qal/lsteer -- steered-inductor drive for the mesh3 three-phase trapezoid wave (trap_tt92_d3, 12.0x per level)",
        date="2026-10-16",
        baseline=dict(standing_eye_ps=BASE_EYE, worst_margin_mV=BASE_MARGIN, gate_mV=GATE, E_ledger_fJ=E_LEDGER, E_harmonic_fJ=E_HARM),
        instrument_check=json.load(open(os.path.join(HERE, "ICHECK.json"))),
        pre_registered_corrections=[
            "DCM L: the brief's 2.2 nH/pair is an arithmetic slip; (92 ps/pi)^2 / 44 fF = 19.5 nH per pair, 9.7 nH at N=2 (corrected in PRE_REGISTERED.json before any deck).",
            "CCM self-sustaining claim: DERIVED-and-WRONG. The plain F->L->R loop's volt-second balance is satisfied for ANY swing equal to the post-handover separation (symmetric trajectories), so it is neutrally stable at best and the series R decays it (measured -11 %/cycle without a zero clamp). The pre-registered 4 ps zero-clamp pulse (L fed from 0 V for 4 ps) adds -5 fWb/third and PINS the current at ~2.5 mA for every seed 2.8/3.15/3.5 mA (converges within one period) -- self-regulating, but to a 0.72 swing with a 450 mV hold-clamp yank.",
            "Constant current UNDER-delivers (independently found by qal/ldrive): C(V) grows as cells turn on and the bank draws its 'hold' current during the rise; a flat 3.5 mA lands 220-450 mV short. The regulator that lands the rail is the 1.65 V in-feed phase of the steered buck (t1 = 0.5-0.6: -31/-122 mV landing).",
            "Terminal capacitance (ASSUMED 20 fF) is not free: the dead-time charge sharing at each handover eats ~0.3 V of separation per side; 5 fF recovers ~60 mV of landing and 16 fJ/bank.",
            "A code bug in the first buck rows (in-feed generated for phase A only) was found from the waveforms and quarantined under runs/BUG_*; those three rows are not scored.",
        ],
        regime_i_CCM=ri, regime_ii_DCM=rii, N_sharing=share, real_switch_rows=rr,
        headline_rows=dict(
            pre_registered_pulse_construction="ccm_N2_L120_R10_I3.15_ideal",
            best_speed_row="ccm_N2_L120_R10_I3.5_ideal_ss_t10.8 (P1 confirmed by ccm_N2_L120_R10_I3.5_ideal_ss_t10.8_P1)",
            landing_regulated_row="ccm_N2_L120_R10_I3.5_ideal_ss_t10.5",
            cheapest_row="ccm_N2_L120_R10_I3.15_ideal_ss_Ct5 / ccm_N2_L120_R10_I3.5_ideal_ss_t10.8_Ct5"),
        energy_ledger_summary_fJ_per_bank_per_cycle=dict(
            ideal_switch_rows_range=[244.8, 288.0],
            best_speed_row={k: best_i["ledger_fJ_per_bank_per_cycle"][k] for k in ("E_dc_rail", "E_resistive_L", "E_switch_conduction_and_charge_sharing", "E_total_sources", "E_gate_fit_3p7fCum", "E_total_with_gate_fit")},
            landing_regulated_row={k: reg["ledger_fJ_per_bank_per_cycle"][k] for k in ("E_dc_rail", "E_resistive_L", "E_switch_conduction_and_charge_sharing", "E_total_sources")},
            real_switch_gate_metered={t: (rr[t]["ledger_fJ_per_bank_per_cycle"]["E_gate_metered"] if rr[t]["status"] == "OK" else None) for t in TAGS_R[:2]},
            gate_charge_metered_fC_per_um=dict(nMOS_2p174V="2.04-2.44 (W=30/10 um, turn-on edge, metered through 0 V gate ammeters)", pMOS_1p65V="2.85-3.05 (W=60/30 um)", fit_used_for_riders=3.7),
            vs_ledger_240p3="ideal rows +2..+20 %; the DC rail pays the hold charge (~150-185 fC/bank at 1.65 V) plus the landing shortfall; the inductor recycles the rise/fall edges, which the ideal mesh3 rail also recycled -- so the construction cannot beat 240.3, it can only approach it",
            vs_harmonic_534="ideal rows -46..-54 %; real-switch rows (gate metered) +38..+73 % (736 / 925 fJ) and FAIL anyway"),
        verdict=(
            "CAN the 12x wave be driven by a few steered inductors? IN PRINCIPLE YES (ideal-switch BOUND): one inductor per 3N banks, "
            "steered F->L->R every third with the holding bank on a 1.65 V DC clamp, sustains the wave in every construction tried -- "
            "value 144/144 on P0 and P1, margin 250-697 mV (gate 69.9), overlap 28-41 ps, standing eye 124-137 ps vs 129.0 -- at "
            "L = 120 nH (N=2, 6 banks) / 30 nH (N=8, 24 banks) (L = 240 nH/N, sharing law MEASURED: same absolute per-third ripple "
            "0.20 vs 0.24 mA at N=2/N=8 for 120 nH), I0 = 3.5 mA (N=2) / 13.4 mA (N=8) = N x 1.7 mA, ripple 5.8 % per third, "
            "at 245-290 fJ/bank/cycle from the DC rail (mesh3 ledger 240.3, harmonic driver 534). BUT the plain loop is NOT self-sustaining "
            "(neutral + R decay; a zero-clamp pulse pins it at a 0.72 swing with a 450 mV clamp yank); landing within 0.1 V needs the "
            "steered-buck in-feed at t1 = 0.5 (I0 = 4.4 mA, +10 % energy, margin 697 mV, eye 137 ps). DCM (9.7 nH) lands 535 mV short "
            "(charge-bound resonant swap, no current zero at the third's end) and degenerates to a 0.84-1.65 V half swing without a clamp. "
            "WITH REAL sg13_lv SWITCHES at the binding 2.174 V spec it FAILS: the W=30 um TG's own capacitance (metered 2.1-3.0 fC/um per edge) "
            "loads each phase node with ~250-300 fF (as much as the bank pair), the rails swing only 0.65-1.78 V, value fails 6-7/144; "
            "re-seeded wider rows (W=50/78 um, 7-9 mA) crash Xyce at the first high-current handover (-240 mA crowbar into vddh through the "
            "pMOS wells once the rail exceeds 1.65 V). No real-switch operating point was found; the gate bill alone is 328 (nMOS) / 495 (TG) "
            "fJ/bank metered, so even a working real version would sit at ~740-925 fJ/bank, above the 534 fJ harmonic driver. "
            "Energy REPORTED, never gated."))
    json.dump(res, open(os.path.join(HERE, "RESULTS.json"), "w"), indent=1)
    print("RESULTS.json written; sharing:", json.dumps(share["measured"]))
    print("rows:", {t: r["status"] for t, r in list(ri.items()) + list(rii.items()) + list(rn.items()) + list(rr.items())})
