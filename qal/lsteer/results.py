#!/usr/bin/env python3
"""qal/lsteer -- assemble RESULTS.json from runs/*/OUT.json (tables + ledger + verdict)."""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
E_LEDGER, E_HARM, BASE_EYE, BASE_MARGIN, GATE = 240.292, 534.0, 129.0, 509.67, 69.924


def load_all():
    R = {}
    rd = os.path.join(HERE, "runs")
    for tag in sorted(os.listdir(rd)):
        oj = os.path.join(rd, tag, "OUT.json")
        if os.path.exists(oj):
            R[tag] = json.load(open(oj))
    return R


def row(tag, o):
    if "summary" not in o:
        return dict(tag=tag, error=o.get("error"))
    s, ls = o["summary"], o["lsteer"]
    led = ls["ledger"]
    return dict(
        tag=tag, regime=o["regime"], construction=o.get("zero_clamp"), t1_frac=o.get("t1_frac"),
        N_banks_per_phase=o["N_per_phase"], banks_on_inductor=led["n_banks_on_inductor"],
        L_nH=o["L_nH"], R_L_ohm=o["RL_ohm"], Ct_fF=o["Ct_fF"], switches=o["sw"], pattern=o["pat"],
        softstart=o.get("softstart", False), I0_seed_mA=o["I0_seed_mA"],
        I_mean_mA=s["I_mean_mA"], I_max_mA=ls["inductor"]["I_max_mA"], I_min_mA=ls["inductor"]["I_min_mA"],
        ripple_pp_mA=s["ripple_pp_mA"], ripple_pct=s["ripple_pct"], drift_pct_per_cycle=s["drift_pct"],
        I_at_nT_mA=ls["inductor"]["I_at_nT_mA"], zero_crossings=ls["zero_crossings"]["n"],
        E_stored_fJ=ls["inductor"]["E_stored_mean_fJ"],
        rail_rise_end_minus_dV_mV=s["arrival_rise_mV"], hold_clamp_step_mV=ls["arrival"]["hold_clamp_step_mV"],
        rail_fall_end_before_clamp_mV=s["arrival_fall_mV"], rail_min_V=s["rail_min_V"], rail_max_V=s["rail_max_V"],
        terminal_excursion=s["terminals"], hold_rail_bank4=s["hold_rail_4"],
        value_PASS=(s["value_fail"] == 0), value_fail=s["value_fail"],
        worst_margin_mV=s["worst_margin_mV"], worst_overlap_ps=s["worst_overlap_ps"],
        standing_eye_ps=s["standing_eye_ps"], eye_vs_129_ps=(round(s["standing_eye_ps"] - BASE_EYE, 2)
                                                         if s["standing_eye_ps"] else None),
        widths_w3=s["widths"], erosion_sign=s["sign"], PASS=s["PASS"], copies_value_PASS=s["copies"],
        E_dc_rail_fJ=s["E_dc"], Q_dc_rail_fC=led["Q_dc_rail_fC_per_bank"], Q_zero_rail_fC=led["Q_zero_rail_fC_per_bank"],
        E_resistive_L_fJ=s["E_R"], E_switch_conduction_fJ=s["E_sw"],
        E_gate_metered_fJ=s["E_gate_metered"], E_gate_fit_fJ=s["E_gate_fit"],
        E_gate_net_adiabatic_fJ=led["E_gate_net_adiabatic_fJ_per_bank"],
        E_bank_books_fJ=led["E_bank_mean_fJ_per_bank_from_books"],
        E_total_sources_fJ=s["E_total_sources"], E_total_with_gate_fit_fJ=s["E_total_gate_fit"],
        E_total_with_gate_metered_fJ=s["E_total_gate_metered"],
        vs_ledger_pct=led.get("vs_ledger_240p3_pct"), vs_ledger_with_gate_fit_pct=led.get("vs_ledger_240p3_with_gate_fit_pct"),
        vs_harmonic_with_gate_fit_pct=led.get("vs_harmonic_534_with_gate_fit_pct"),
        balance_mismatch_pct=led.get("balance_check", {}).get("mismatch_pct"),
        gate_detail=ls.get("gate_detail"), crowbar_bank4_w3=o["crowbar"].get("4", o["crowbar"].get(4)),
        xyce_wall_note=None)


if __name__ == "__main__":
    R = load_all()
    rows = {t: row(t, o) for t, o in R.items()}
    json.dump(rows, open(os.path.join(HERE, "TABLES.json"), "w"), indent=1)
    for t, r in rows.items():
        print(t, {k: r.get(k) for k in ("PASS", "worst_margin_mV", "standing_eye_ps", "I_mean_mA", "ripple_pct",
                                        "drift_pct_per_cycle", "rail_rise_end_minus_dV_mV", "E_total_sources_fJ",
                                        "E_total_with_gate_metered_fJ", "E_total_with_gate_fit_fJ")})


# ----------------------------------------------------------------- RESULTS.json
def compose(rows):
    g = lambda t: rows.get(t)
    def pick(t, keys):
        r = g(t)
        if r is None:
            return None
        return {k: r.get(k) for k in keys}
    K_I = ["PASS", "value_PASS", "worst_margin_mV", "worst_overlap_ps", "standing_eye_ps", "eye_vs_129_ps",
           "I0_seed_mA", "I_mean_mA", "ripple_pct", "ripple_pct_third", "drift_pct_per_cycle",
           "rail_rise_end_minus_dV_mV", "hold_clamp_step_mV", "rail_fall_end_before_clamp_mV", "rail_min_V",
           "rail_max_V", "terminal_excursion", "L_nH", "R_L_ohm", "Ct_fF", "construction", "t1_frac", "softstart",
           "E_dc_rail_fJ", "E_resistive_L_fJ", "E_switch_conduction_fJ", "E_total_sources_fJ",
           "E_gate_fit_fJ", "E_total_with_gate_fit_fJ", "balance_mismatch_pct", "copies_value_PASS"]
    for t, r in rows.items():
        if "error" in r:
            continue
        o = json.load(open(os.path.join(HERE, "runs", t, "OUT.json")))
        r["ripple_pct_third"] = o["lsteer"]["inductor"].get("ripple_pct_per_third")
        r["ripple_pp_third_mA"] = o["lsteer"]["inductor"].get("ripple_pp_per_third_mA")
    regime_i = {t: pick(t, K_I) for t in rows if t.startswith("ccm_") and "ideal" in t}
    regime_ii = {t: pick(t, K_I) for t in rows if t.startswith("dcm_")}
    real = {t: pick(t, K_I + ["E_gate_metered_fJ", "E_total_with_gate_metered_fJ", "gate_detail", "switches",
                              "vs_harmonic_with_gate_fit_pct"]) for t in rows if "_nmos_" in t or "_tg" in t}
    bugs = {t: "indd window generated for phase A only (L open-circuited at the in-side for the last (1-t1) of B/C fall thirds); kept as a record, NOT scored" for t in rows if t.startswith("BUG_")}
    return dict(regime_i_CCM=regime_i, regime_ii_DCM=regime_ii, real_switch_rows=real, quarantined_rows=bugs)


if __name__ == "__main__" and os.environ.get("LSTEER_COMPOSE"):
    R = load_all()
    rows = {t: row(t, o) for t, o in R.items()}
    json.dump(compose(rows), open(os.path.join(HERE, "RESULTS_rows.json"), "w"), indent=1)
    print("RESULTS_rows.json written:", len(rows), "rows")
