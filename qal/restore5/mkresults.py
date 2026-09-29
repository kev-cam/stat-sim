#!/usr/bin/env python3
"""Assemble RESULTS.json from rows.json + the reference decks.  No new simulation."""
import hashlib, json, os, subprocess, sys, time

import econ, ref

HERE = os.path.dirname(os.path.abspath(__file__))
L = lambda n: json.load(open(os.path.join(HERE, n)))


def mt(n):
    p = os.path.join(HERE, n)
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(os.path.getmtime(p))) \
        if os.path.exists(p) else None


def main():
    rows = L("rows.json")
    R = {}
    R["_doc"] = (
        "RESTORING STAGES EVERY k BANKS in a hop-powered QAL chain. Answers the ask "
        "'Add restoring stages every few banks and see what it costs.' Every number "
        "is labelled MEASURED / DERIVED / ASSUMED. Pre-registration was written "
        "before any deck in this directory existed; amendments in AMENDMENT.md each "
        "state what forced them and when.")
    R["_provenance"] = dict(
        pre_registration="qal/restore5/PRE_REGISTERED.json",
        pre_registration_sha256=hashlib.sha256(
            open(os.path.join(HERE, "PRE_REGISTERED.json"), "rb").read()).hexdigest(),
        amendments="qal/restore5/AMENDMENT.md",
        pyms_vae_cache="scratchpad/vae_cache_restore5 (own, built from scratch)",
        model="SG13G2 / PSP103 tt via qal/sg13lv_compat.sp",
        lower_bound_caveat=(
            "qal/sg13lv_compat.sp ZEROES ad/as/pd/ps, so junction capacitance is "
            "ABSENT everywhere. Every capacitance, charge, energy, hop time and "
            "settling time in this file is therefore a LOWER BOUND: real silicon is "
            "slower and costs more. Restated on the numbers it touches."),
        shallow_stack_caveat=(
            "the ALU dominant mapped cell sg13g2_o21ai_1 NEVER settles anywhere in "
            "the PDK envelope (2-high pMOS stack, no headroom on a 0.52-0.69 V "
            "rail), so this study uses the INVERTER-class bank and EVERY number is a "
            "SHALLOW-STACK number."),
        mtimes_proving_order={n: mt(n) for n in (
            "PRE_REGISTERED.json", "AMENDMENT.md", "rest.py", "extract.py", "go.py",
            "ref.py", "econ.py", "table.py", "qpre.cir", "cinv.cir", "rtrip.cir",
            "ia_hop.cir", "ia_chain.cir", "rows.json", "RESULTS.json")},
        energy_exclusion_untouched=(
            "the committed energy EXCLUSION verdict (complete timer ledger 23.213 "
            "fJ/bank/hop against a pre-stated 12.7467 fJ, stat-sim c814e52) is NOT "
            "reopened, NOT re-litigated and NOT affected by anything here: it is "
            "about the switch TIMING hardware, not about restoration."))
    # ---- the instrument check and the reference measurements (all MEASURED)
    R["instrument_check"] = dict(
        _what=("(b) of the ask: reproduce the committed single hop digit-checked, "
               "and reproduce one FAILING no-restore chain row so the harness is "
               "anchored to the known negative."),
        committed_single_hop=ref.ia_hop(),
        failing_no_restore_chain_row_chain3_a277_free=ref.ia_chain(),
        receiver_trip_points=ref.rtrip(),
        cmos_inverter_reference=ref.cinv(),
        per_segment_precharge=ref.qpre())
    R["rows"] = rows
    v1 = os.path.join(HERE, "v1_standard_receiver", "rows_v1_raw.json")
    if os.path.exists(v1):
        R["rows_v1_standard_receiver_VOID"] = dict(
            _what=("the pre-AMENDMENT-A4 run with the campaign-standard 1.12u/0.74u "
                   "restoring stage. VOID for acceptance: that cell's trip point "
                   "(0.6452 V MEASURED) is ABOVE the delivered QAL level its own "
                   "input load produces (0.6007 V MEASURED), so it restored every "
                   "HIGH as a LOW. Kept because it is AMENDMENT A4's evidence."),
            rows=json.load(open(v1)))
    json.dump(R, open(os.path.join(HERE, "RESULTS.json"), "w"), indent=1,
              default=str)
    print("wrote RESULTS.json with %d rows" % len(rows))


if __name__ == "__main__":
    main()
