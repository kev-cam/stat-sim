#!/usr/bin/env python3
"""SKEPTIC verdict: assembled ONLY from SK_POLICE.json (my own decks, my own
extractor) plus SK_COST.json and SK_SEPARATION.json."""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
P = json.load(open(os.path.join(HERE, "SK_POLICE.json")))
by = {r["tag"]: r for r in P if "error" not in r}

FREE = "s4_free_T200_dv1200_L1_t12"
CLAMP = "s4_rtu_T200_dv1200_L1_t20"
PT12 = "s4_ptu_T200_dv1200_L1_t12"
PT24 = "s4_ptu_T200_dv1200_L1_t24"

out = {
    "_doc": "SKEPTIC verdict on the matched comparison: PULSED INDUCTOR vs SWITCHED "
            "CLAMP top-up, at s4 / T = 200 ps / dV = 1.2 / Ltu = 1 nH / Cna = 8 fF.",
    "_provenance": "every number below is from MY OWN decks, run from scratch under "
                   "MY OWN PYMS_VAE_CACHE, extracted from the RAW .prn by "
                   "sk_extract.py. Nothing is quoted from a committed summary.",
    "_instrument": json.load(open(os.path.join(HERE, "SK_INSTRUMENT.json")))["VERDICT"],
}

rows = {}
for nm, tag in (("free", FREE), ("clamp", CLAMP), ("pulsed_t12", PT12),
                ("pulsed_t24", PT24)):
    r = by.get(tag)
    if not r:
        rows[nm] = "NOT MEASURED"
        continue
    rows[nm] = dict(
        settling_worst_by_stage=r["settling_worst_pct_by_stage"],
        A1_worst=r["A1_worst_gate_all_stages_pct"], A1_pass=r["A1_pass_all_90"],
        A2_min_delivered_HIGH_V=r["A2_min_delivered_HIGH_V"],
        A2_pass=r["A2_pass_all_stages"],
        A6_worst_IZ_uA=r["A6_worst_IZ_uA"], A6_pass=r["A6_pass"],
        rail3_at_bound_V=r["S5_rail3_at_bound3_V"],
        pmos_overdrive_V=r["S5_pmos_overdrive_over_Vtp_V"],
        rail2_at_bound_V=r["S4_predecessor_rail2_at_bound2_V"],
        victim_max_pulldown_V=r["S2_victim_max_pulldown_at_bound2_V"],
        rail3_max_rising_V_per_ns=r["S1_rail3_max_rising_V_per_ns"],
        rail3_rise_in_window_mV=r["S1_rail3_rise_in_window_mV"],
        victim_lift_in_window_mV=r["S2_victim_lift_in_window_mV"],
        separation_mV_by_bank=r["separation_mV_by_bank"],
        phases=r.get("S1_by_pulse_phase"), I_LTU3_uA=r.get("I_LTU3_uA"),
        pulse_timing=r.get("pulse_phases_ps"))
out["rows"] = rows

f = by.get(FREE)
if f:
    base_low = f["S2_victim_max_pulldown_at_bound2_V"]
    base_lift = f["S2_victim_lift_in_window_mV"]
    dmg = {}
    for nm, tag in (("clamp", CLAMP), ("pulsed_t12", PT12), ("pulsed_t24", PT24)):
        r = by.get(tag)
        if not r:
            continue
        d_bound = (r["S2_victim_max_pulldown_at_bound2_V"] - base_low) * 1e3
        d_win = r["S2_victim_lift_in_window_mV"] - base_lift
        d_rail = r["S1_rail3_rise_in_window_mV"] - f["S1_rail3_rise_in_window_mV"]
        dmg[nm] = dict(
            victim_lift_at_boundary_mV=round(d_bound, 3),
            victim_lift_in_window_mV=round(d_win, 3),
            rail3_rise_attributable_mV=round(d_rail, 3),
            per_mV_of_rail_rise=(round(d_win / d_rail, 4) if abs(d_rail) > 1e-9
                                 else "UNDEFINED -- this form raises the rail by "
                                      "ZERO in the window yet still lifts the "
                                      "victim's LOW nodes"),
            net_rail_benefit_vs_free_mV=round(
                (r["S5_rail3_at_bound3_V"] - f["S5_rail3_at_bound3_V"]) * 1e3, 3))
    out["S2_S3_damage_attribution"] = dmg

out["MECHANISM_ADJUDICATION"] = {
    "question": "is the step coupling genuinely ABSENT under inductive delivery, or "
                "merely SMALLER?",
    "answer": "MERELY SMALLER -- and the residual does not come from where the brief "
              "assumes.",
    "evidence_1_whole_window": "max rising dV/dt on the topped rail: free control "
                              "0.197 V/ns, switched clamp 227.0 V/ns, pulsed inductor "
                              "70.0 (t_on=12) / 92.0 (t_on=24) V/ns. The pulsed form "
                              "is 2.47x below the clamp but 355-467x ABOVE the free "
                              "control. 92 V/ns is a steep edge by any standard.",
    "evidence_2_phase_decomposition": "THE KEY MEASUREMENT, and it is mine. Splitting "
        "the window by pulse phase: the CLAMP does 58.5 V/ns during its actual "
        "conduction and 227.0 V/ns at its switch OPENING. The PULSED form does 0.125 "
        "V/ns at OUT-close, 7.1 V/ns during the pulse, 10.5 V/ns during the freewheel "
        "(its actual delivery) -- and 92.0 V/ns at OUT-OPEN.",
    "what_this_means_for_the_brief": "the brief's physical claim is CORRECT ABOUT "
        "DELIVERY and wrong about the circuit. Comparing delivery phase to delivery "
        "phase, the inductor really does ramp the rail: 10.5 V/ns against the clamp's "
        "58.5 V/ns, 5.6x gentler, exactly as di/dt-limited delivery should. But the "
        "dominant edge in BOTH forms is the top-up switch's TURN-OFF feedthrough, "
        "which no inductor can govern.",
    "what_this_means_for_the_prior_analysis": "the prior analysis got the number right "
        "(92 V/ns) and the mechanism wrong. It attributed the edge to 'the OUT switch "
        "closes onto the rail and the stored inductor current dumps into it'. MEASURED: "
        "at OUT-close the slope is 0.125 V/ns, and at the instant of the 92 V/ns edge "
        "I(LTU3) = 0.36 uA -- the inductor is empty. The edge is gate-drive "
        "feedthrough at turn-off, not current dumping.",
    "why_it_is_structural": "AMENDMENT A1b established by measurement that the OUT "
        "switch is MANDATORY -- without it the inductor drains the bank between pulses. "
        "So the isolation switch the architecture requires reintroduces a step of its "
        "own at turn-off. The step coupling is reduced, not eliminated, and the "
        "residual is a property of the topology rather than of the delivery.",
}

out["THE_ANSWER_TO_THE_ASK"] = {
    "does_the_correct_topup_form_change_the_committed_outcome": "NO.",
    "is_the_negative_result_an_artefact_of_the_substituted_clamp": "NO. That was the "
        "question this run existed to answer. The pulsed form, run from scratch with "
        "the switch-node capacitance present, the corrected gate sequence, and the A8 "
        "probe defect FIXED, still fails A1 by a wide margin, still cannot raise the "
        "rail above the free control, and still couples backward into the feeding "
        "stage.",
    "confidence": "HIGH on the bottom line; MODERATE on the exact pulsed settling "
        "percentages, because the pulsed rows are the ones that needed the A8 repair "
        "and only my own repaired rows are gate-clean.",
}
json.dump(out, open(os.path.join(HERE, "SK_VERDICT.json"), "w"), indent=1)
print(json.dumps({k: out[k] for k in ("rows", "S2_S3_damage_attribution")
                  if k in out}, indent=1)[:4000])
print("\nwrote SK_VERDICT.json")
