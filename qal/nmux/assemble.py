#!/usr/bin/env python3
"""Collect every stage's JSON into RESULTS.json, with provenance and labels."""
import hashlib, json, os, time

HERE = os.path.dirname(os.path.abspath(__file__))


def load(name, default=None):
    p = os.path.join(HERE, name)
    if not os.path.exists(p):
        return default
    try:
        return json.load(open(p))
    except Exception as e:
        return {"LOAD_ERROR": str(e)}


def mt(name):
    p = os.path.join(HERE, name)
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(os.path.getmtime(p))) \
        if os.path.exists(p) else None


def main():
    pre = open(os.path.join(HERE, "PRE_REGISTERED.json"), "rb").read()
    out = {
     "_doc": "qal/nmux -- nMOS-ONLY PASS LOGIC for QAL, measured against a "
             "full-transmission-gate control in one harness.",
     "_provenance": {
       "pre_registration": "qal/nmux/PRE_REGISTERED.json",
       "pre_registration_sha256": hashlib.sha256(pre).hexdigest(),
       "pre_registration_written": mt("PRE_REGISTERED.json"),
       "mtimes_recorded_before_first_deck": "qal/nmux/MTIME_BEFORE_FIRST_DECK.txt",
       "amendments": "qal/nmux/AMENDMENT.md (A1 null-model cache trap, "
                     "A2 gate-source addition, A3 Vt sweep range, A4 Vgs axis bug, "
                     "A5 peer time step, A6 per-geometry compile cost, "
                     "A7 reduced chain geometry, A8 gate G3 dropped)",
       "model": "SG13G2 / PSP103 tt via qal/sg13lv_compat.sp",
       "pyms_vae_cache": "scratchpad/vae_cache_nmux (own, built from scratch)",
       "lower_bound_caveat": "sg13lv_compat.sp ZEROES ad/as/pd/ps. Junction "
         "capacitance is ABSENT, so every energy and every settle time here is "
         "OPTIMISTIC. The nMOS-only vs TG comparison is still like-for-like "
         "because both use the same shim -- but note the TG has TWICE the "
         "junction area being omitted, so the shim flatters the TG MORE than it "
         "flatters the nMOS-only cell. The area and device-count results are "
         "unaffected.",
     },
     "instrument_gates": {
       "G1_Vtn_zero_body": load("vtb_rows.json", {}).get("rows", [{}])[0]
                            if load("vtb_rows.json") else None,
       "G2_peer_committed_deck": (load("gates.json") or {}).get("G2_peer"),
       "G3_tank_committed_chain": "DROPPED -- see AMENDMENT A8",
       "G_contention_anchor": "the standard 1.12p/0.74n receiver at 1.2 V and a "
         "0.6759 V input reproduces the committed boundary study to 0.06 % "
         "(8.7856 vs 8.780 uA; 3.0890 vs 3.0896 fJ; 36.74 vs 36.75 % of hop). "
         "Not pre-registered; found and recorded as a free check.",
     },
     "a_body_effect": {"rows": load("vtb_rows.json"), "fit": load("body_fit.json"),
                       "writeup": "MEASURED_a_body.md"},
     "bd_cells": {"designs": load("cells_designs_fixed.json"),
                  "widths": load("cells_widths_fixed.json"),
                  "stepcheck": load("cells_stepcheck_fixed.json"),
                  "locus_rate_probe": load("locus.json"),
                  "gate_drive_derivation": "DERIVED_gate_drive.md",
                  "writeup": "MEASURED_bd_cells.md",
                  "_note": "rows re-extracted by reextract.py (AMENDMENT A10); the "
                           "raw first-pass files cells_*.json are kept but their "
                           "energy columns are UNSCALED and must not be used"},
     "d_area": {"model": load("area.json"), "writeup": "MEASURED_d_area.md"},
     "c_chain": {"rows": load("chain_rows_w060.json"),
                 "writeup": "MEASURED_c_chain.md",
                 "_geometry": "REDUCED -- see AMENDMENT A7; compare only against "
                              "the `wire` control in this same file"},
     "f_contention": {"rows": load("cont.json"),
                      "writeup": "MEASURED_f_contention.md"},
     "g_transfer_switch_mechanism": {"writeup": "MEASURED_g_mechanism.md"},
    }
    json.dump(out, open(os.path.join(HERE, "RESULTS.json"), "w"), indent=1)
    print("wrote RESULTS.json")
    for k in ("a_body_effect", "bd_cells", "c_chain", "f_contention"):
        v = out[k]
        print("  %-28s %s" % (k, "present" if v else "MISSING"))


if __name__ == "__main__":
    main()
