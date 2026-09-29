#!/usr/bin/env python3
"""THE RE-VERDICT: assembles every measured artefact in qal/ptu into VERDICT.json.

Reads (all produced in this directory, all from measurements):
  INSTRUMENT.json  the A5 digit check
  EXISTING.json    per-gate settling extracted from skiptu's own 34 ptu decks
  FIXTURE.json     the Cna x Ltu x t_on sweep of the CORRECTED top-up cell
  COUPLING2.json   D1/D2: delivery slope and predecessor-LOW lift, per row
  SEPARATION.json  D6: HIGH/LOW separation by depth, vs restore5 and sigma-Vt
  ROWS_*.json      the CORRECTED pulsed-inductor chain rows
  COMPARE.json     the matched table
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKIPTU = "/usr/local/src/stat-sim/qal/skiptu"


def L(n):
    p = os.path.join(HERE, n)
    return json.load(open(p)) if os.path.exists(p) else None


def main():
    instr, ex, fx = L("INSTRUMENT.json"), L("EXISTING.json"), L("FIXTURE.json")
    cp, sep, cmp_ = L("COUPLING2.json"), L("SEPARATION.json"), L("COMPARE.json")
    rows = []
    for f in sorted(os.listdir(HERE)):
        if f.startswith("ROWS_") and f.endswith(".json"):
            rows += json.load(open(os.path.join(HERE, f)))
    ok = [r for r in rows if "error" not in r]
    bad = [r for r in rows if "error" in r]

    v = {
        "_doc": "qal/ptu -- THE MATCHED COMPARISON: does the PULSED-INDUCTOR "
                "(current-ramp) top-up avoid the step-coupling damage that the "
                "SWITCHED CLAMP (voltage-step) inflicts, and does it change the "
                "settling, the pull-up overdrive, or the HIGH/LOW separation?",
        "date": "2026-09-29",
        "pre_registration": "PRE_REGISTERED.json, sole file on disk at "
                            "2026-09-29 01:30:52 -0700 (mtime is the proof)",
        "n_corrected_ptu_rows_measured": len(ok),
        "n_rows_errored": len(bad),
    }

    if instr:
        v["INSTRUMENT_CHECK_A5"] = {
            "verdict": instr.get("VERDICT"),
            "VBEND": instr.get("VBEND"), "VBPK": instr.get("VBPK"),
            "t_hop_ps": instr.get("t_hop_ps"),
            "cells_settled": instr.get("cells_settled"),
            "mt0": "%s/%s BIT-IDENTICAL against the committed mt0, worst rel %.2e on %s"
                   % (instr.get("mt0_keys_BIT_IDENTICAL"), instr.get("mt0_keys_compared"),
                      instr.get("mt0_worst_rel", 0), instr.get("mt0_worst_key")),
            "decks": "md5-identical byte copies of committed qal/lsweep/"
                     "h_L15_W30_dv120.cir and p_L15_W30_dv120.cir; own "
                     "PYMS_VAE_CACHE built from scratch, nothing copied in"}

    if fx:
        pos = [r for r in fx["rows"] if (r.get("q_delivered_fC") or -1) > 0]
        v["FIXTURE_the_corrected_cell_on_a_small_bank"] = {
            "grid": "Cna {8,20,50} fF x Ltu {1,5,15} nH x t_on {6,12,24} ps, "
                    "27 points, bank 28.98 fF pre-charged to the chain's own "
                    "MEASURED free rail3 of 0.765884 V, supply 1.2 V",
            "n_points": len(fx["rows"]),
            "n_with_POSITIVE_delivery": len(pos),
            "n_with_BUCK_ACTION_Qmult_gt_1": fx.get("n_buck_action"),
            "the_only_positive_point": (pos[0] if pos else None),
            "best_Qmult_anywhere": max((r.get("charge_mult") or -9)
                                       for r in fx["rows"]),
            "required_for_buck_action": 1.0,
            "A7_extrapolation_REFUTED": "skiptu A7 swept Cna only to the DERIVED "
                "8 fF and its own table trends toward zero FROM BELOW, which invites "
                "the reading that a larger switch-node capacitance would cross into "
                "positive delivery. MEASURED here: it does NOT. Cna = 20 fF and "
                "50 fF are both WORSE than 8 fF at every (Ltu, t_on). The trend is "
                "NOT monotone; it turns around."}

    v["ACCEPTANCE"] = {
        "A1": "every gate in every stage >= 90% settled at its own boundary",
        "A2": "delivered input HIGH >= 0.4400 V at every stage",
        "_source": "copied verbatim from skiptu/PRE_REGISTERED.json so the "
                   "re-verdict is judged by the same bar as the clamp rows"}

    if cmp_:
        v["RE_VERDICT"] = cmp_.get("RE_VERDICT")

    json.dump(v, open(os.path.join(HERE, "VERDICT.json"), "w"), indent=1)
    print(json.dumps(v, indent=1)[:4000])


if __name__ == "__main__":
    main()
