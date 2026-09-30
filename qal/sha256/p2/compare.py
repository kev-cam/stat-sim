#!/usr/bin/env python3
"""THE DELIVERABLE: the measured QAL sha_slice block against the committed
CMOS / QDI / DIMS numbers, load-matched and said so.

COMMITTED REFERENCES (all from qal/synth/threeway, quoted not re-derived):
  CMOS  56 cells : 232 fJ/op @ 0.928 ns, i.e. DEPTH 10 x 92.8 ps/level.  The
                   same-convention cell comparator is 94.174 ps at a 6.91 fF load
                   and 57.143 ps at 2 fF.
  QDI direct-threshold : 113 cells, 2712 fJ @ 2.533 ns
       + completion detection : 4385.7 fJ @ 4.021 ns
  DIMS  : 524 cells, 6972 fJ @ 5.575 ns
  QAL (COMPOSED PROJECTION, what this run replaces) : 136.8 fJ @ 4.004 ns
        = 1.303 fJ/gate x 105 gates, depth 10 x 400.4 ps, TIMING HARDWARE EXCLUDED.

LOAD MATCHING.  This deck loads every cell output with CL = 2.0 fF (the committed
banktank/skept convention).  The load-matched CMOS comparator is therefore the
2 fF one, 57.143 ps/level -> DEPTH 10 x 57.143 = 571.4 ps for the CMOS block.
The committed 928 ps figure is the 6.91 fF convention.  BOTH are reported and the
load-matched one is the one the verdict uses, because quoting the 6.91 fF CMOS
number against a 2 fF QAL deck would flatter QAL by 1.62x.
"""
import glob, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
CMOS_E, CMOS_T_691 = 232.0, 928.0
CMOS_LEVEL_691, CMOS_LEVEL_2F = 94.174, 57.143
CMOS_DEPTH = 10
CMOS_T_2F = CMOS_DEPTH * CMOS_LEVEL_2F
CMOS_AREA = 627.7824
REF = {
    "CMOS_56cell": dict(cells=56, E_fJ=232.0, T_ps=928.0, T_ps_loadmatched=CMOS_T_2F),
    "QDI_direct_threshold": dict(cells=113, E_fJ=2712.0, T_ps=2533.0),
    "QDI_plus_completion": dict(cells=113, E_fJ=4385.7, T_ps=4021.0),
    "DIMS": dict(cells=524, E_fJ=6972.0, T_ps=5575.0),
    "QAL_COMPOSED_PROJECTION": dict(cells=105, E_fJ=136.8, T_ps=4004.0,
                                    note="EXCLUDES the timing hardware"),
}


def main():
    rows = []
    for p in (sorted(glob.glob(os.path.join(HERE, "ROW_T*.json"))) +
              sorted(glob.glob(os.path.join(HERE, "ROW_H*.json"))) +
              sorted(glob.glob(os.path.join(HERE, "ROW_K*.json")))):
        rows.append(json.load(open(p)))
    rows.sort(key=lambda r: r["T_ps"])
    out = {"_doc": __doc__, "committed_references": REF,
           "load_matching": {
               "this_deck_CL_fF": 2.0,
               "CMOS_level_at_2fF_ps": CMOS_LEVEL_2F,
               "CMOS_level_at_6p91fF_ps": CMOS_LEVEL_691,
               "CMOS_block_loadmatched_ps": CMOS_T_2F,
               "CMOS_block_as_committed_ps": CMOS_T_691,
               "which_the_verdict_uses": "the 2 fF load-matched 571.4 ps"}}
    tbl = []
    for r in rows:
        tbl.append(dict(
            tag=r["tag"], beat_ps=r["T_ps"], PASS=r["PASS"],
            A1=r["A1_settling_pass_90"], A2=r["A2_value_pass"],
            A6=r["A6_zcs_pass"], A6_worst_uA=round(r["A6_worst_uA"], 4),
            worst_gate_pct=round(r["worst_gate_pct"], 3),
            worst_where=r["worst_gate_where"],
            n_value_fail=r["n_value_fail"], n_gates=r["n_gates_checked"],
            block_answer_correct=r["A2b_block_answer_correct"],
            sep_min_mV=(round(r["separation_min_mV"], 3)
                        if r["separation_min_mV"] else None),
            latency_ps=round(r["latency_from_t0_ps"], 1),
            II_beats=r["II_beats"], II_ps=r["II_ps"],
            dv=r["dv"],
            E_per_op_tank_fJ=round(r["E_per_op_TANK_MEASURED_fJ"], 2),
            E_per_op_wall_fJ=(round(r["E_per_op_fJ_WALL_DERIVED"], 2)
                              if r.get("E_per_op_fJ_WALL_DERIVED") else None),
            E_ledger={k: round(v, 2) for k, v in r["ENERGY_LEDGER_fJ"].items()},
            A6_trapped_fJ=round(r["A6_trapped_energy_fJ"], 4),
        ))
    out["ROWS"] = tbl
    passing = [t for t in tbl if t["PASS"]]
    out["PASSING"] = passing
    best = min(passing, key=lambda t: t["beat_ps"]) if passing else None
    out["EARLIEST_CORRECT_BEAT"] = best

    hp = json.load(open(os.path.join(HERE, "PROBE_unir1b_m10_dv1200.json")))
    hh = json.load(open(os.path.join(HERE, "PROBE_unihb_m10_dv1650.json")))
    ht = json.load(open(os.path.join(HERE, "PROBE_tun_m10_dv1200.json")))
    out["HOP_SPREAD"] = {
        "uniform_L_4nH": dict(min_ps=hp["t_hop_min_ps"], max_ps=hp["t_hop_max_ps"],
                              spread_x=hp["t_hop_spread_x"],
                              per_bank={k: round(v["t_hop_ps"], 4)
                                        for k, v in hp["per_bank"].items()}),
        "tuned_L_k_inv_C": dict(min_ps=ht["t_hop_min_ps"], max_ps=ht["t_hop_max_ps"],
                                spread_x=ht["t_hop_spread_x"],
                                per_bank={k: round(v["t_hop_ps"], 4)
                                          for k, v in ht["per_bank"].items()},
                                L_nH={k: round(v["L_nH"], 3)
                                      for k, v in ht["per_bank"].items()}),
        "uniform_L_4nH_dV1p65": dict(min_ps=hh["t_hop_min_ps"],
                                     max_ps=hh["t_hop_max_ps"],
                                     spread_x=hh["t_hop_spread_x"],
                                     per_bank={k: round(v["t_hop_ps"], 4)
                                               for k, v in hh["per_bank"].items()}),
        "VERDICT": ("t_hop spans %.3fx with a uniform 4 nH inductor across a 42.2:1 "
                    "C_bank range -- NOT the sqrt(42.2)=6.50x the sqrt(L*C) law "
                    "predicts, because the quantised transfer-gate width makes the "
                    "small banks Ron-limited rather than LC-limited. Tuning L_k ~ "
                    "1/C_bank collapses the spread to %.3fx but does it by making "
                    "the SMALL banks SLOW (bank 14: %.1f -> %.1f ps), which RAISES "
                    "the beat-setting maximum from %.1f to %.1f ps. The wave is "
                    "therefore left INCOHERENT on purpose: coherence is not needed, "
                    "because every bank is cut at its OWN measured zero, and buying "
                    "it costs %.0f%% of the beat period."
                    % (hp["t_hop_spread_x"], ht["t_hop_spread_x"],
                       hp["per_bank"]["14"]["t_hop_ps"], ht["per_bank"]["14"]["t_hop_ps"],
                       hp["t_hop_max_ps"], ht["t_hop_max_ps"],
                       100.0 * (ht["t_hop_max_ps"] / hp["t_hop_max_ps"] - 1.0)))}

    rc = json.load(open(os.path.join(HERE, "RETIME_COST.json")))
    out["ARCHITECTURE_COST"] = rc

    # the RESTORING THRESHOLD, the finding that decides the whole run
    thr = {}
    for tag in ("T300", "H300"):
        fp = os.path.join(HERE, "ROW_%s.json" % tag)
        if not os.path.exists(fp):
            continue
        rr = json.load(open(fp))
        pk = rr["rail_peak_V"]
        thr[tag] = dict(dv=rr["dv"],
                        rail_peak_min_V=min(pk.values()), rail_peak_max_V=max(pk.values()),
                        banks_clearing_Vtn_plus_Vtp=sum(1 for v in pk.values() if v >= 0.9642),
                        n_value_fail=rr["n_value_fail"], worst_gate_pct=rr["worst_gate_pct"],
                        sep_min_mV=rr["separation_min_mV"])
    out["RESTORING_THRESHOLD"] = dict(
        Vtn_measured=0.5239, Vtp_abs_measured=0.4403, sum_V=0.9642,
        source="qal/chain3/vt.json, MEASURED device constants",
        rows=thr,
        VERDICT=("a static CMOS stage has no gain at mid-rail unless its supply "
                 "exceeds Vtn+|Vtp| = 0.9642 V, so a cascade below that is NOT "
                 "LEVEL-RESTORING.  At dV=1.20 the QAL rail PEAKS at 0.740-0.875 V "
                 "and 0 of 14 banks clear it: 54 of 161 gates are on the wrong side "
                 "of the guard at their own boundary and six banks never reach it at "
                 "ANY offset out to 2000 ps.  At dV=1.65 the rail peaks at "
                 "1.032-1.212 V and 14 of 14 banks clear it: 0 of 161 gates fail. "
                 "The failures are 88% of NAND2 pull-downs and 42% of inverter "
                 "pull-downs -- the n-side -- because on a QAL rail a pull-down's "
                 "gate drive is the PREVIOUS bank's delivered rail, not a full "
                 "supply.  Phase 1 selected {inv,nand2} on binding_pmos_rise_depth, "
                 "the p-side, measured with IDEAL full-dV inputs.  The shallow-stack "
                 "remap did not remove the 2-high stack; it moved it to the side "
                 "that binds in a cascade."))

    # the WALL figure comes from the buck row at the SAME (dV, beat), because only a
    # row that actually carries the converter can measure what the supply must give.
    wall = None
    for t in tbl:
        if (best and t["tag"].startswith("K") and t["dv"] == best["dv"]
                and t["beat_ps"] == best["beat_ps"] and t["E_per_op_wall_fJ"]):
            wall = t
    if wall:
        out["WALL_SOURCE"] = dict(tag=wall["tag"], E_per_op_wall_fJ=wall["E_per_op_wall_fJ"],
                                  E_per_op_tank_fJ=wall["E_per_op_tank_fJ"])
    if best:
        b = best
        if wall:
            b = dict(b); b["E_per_op_wall_fJ"] = wall["E_per_op_wall_fJ"]
        cmp_ = {}
        for nm, ref in REF.items():
            cmp_[nm] = dict(
                their_E_fJ=ref["E_fJ"], their_T_ps=ref["T_ps"],
                QAL_E_fJ=b["E_per_op_tank_fJ"], QAL_latency_ps=b["latency_ps"],
                QAL_II_ps=b["II_ps"],
                E_ratio_QAL_over_them=round(b["E_per_op_tank_fJ"] / ref["E_fJ"], 3),
                E_ratio_WALL_over_them=(round(b["E_per_op_wall_fJ"] / ref["E_fJ"], 3)
                                        if b["E_per_op_wall_fJ"] else None),
                latency_ratio_QAL_over_them=round(b["latency_ps"] / ref["T_ps"], 3),
                throughput_ratio_QAL_II_over_them=round(b["II_ps"] / ref["T_ps"], 3))
        cmp_["CMOS_56cell"]["latency_ratio_LOADMATCHED"] = round(
            b["latency_ps"] / CMOS_T_2F, 3)
        cmp_["CMOS_56cell"]["throughput_ratio_LOADMATCHED"] = round(
            b["II_ps"] / CMOS_T_2F, 3)
        out["THREE_WAY_COMPARISON"] = cmp_
        out["AREA"] = dict(tank_MIM_um2=rc["tank_area_um2"],
                           CMOS_logic_um2=CMOS_AREA,
                           tank_vs_CMOS_logic_x=round(rc["tank_area_um2"] / CMOS_AREA, 2),
                           n_inductors=14)
    json.dump(out, open(os.path.join(HERE, "COMPARISON.json"), "w"), indent=1,
              default=str)

    print("%-5s %-6s %-6s %-5s %-5s %-9s %-9s %-9s %-8s %-9s %-9s" %
          ("dV", "beat", "PASS", "A1", "A2", "worst%", "fails", "sep_mV",
           "lat_ps", "II_ps", "E_tank_fJ"))
    for t in tbl:
        print("%-5g %-6g %-6s %-5s %-5s %-9.2f %-9s %-9s %-8.1f %-9g %-9.1f" %
              (t["dv"], t["beat_ps"], t["PASS"], t["A1"], t["A2"],
               t["worst_gate_pct"], "%d/%d" % (t["n_value_fail"], t["n_gates"]),
               ("%.1f" % t["sep_min_mV"]) if t["sep_min_mV"] else "-",
               t["latency_ps"], t["II_ps"], t["E_per_op_tank_fJ"]))
    print("\nEARLIEST CORRECT BEAT:", best["beat_ps"] if best else "NONE")
    print(out["HOP_SPREAD"]["VERDICT"])


if __name__ == "__main__":
    main()
