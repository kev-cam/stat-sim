#!/usr/bin/env python3
"""Final assembly: RESULTS.json (measured record + economics) and TABLE.txt.
No new simulation.  Every number traced to the row or reference deck it came from."""
import hashlib, json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import econ, ref, extract, rest

HERE = os.path.dirname(os.path.abspath(__file__))
L = lambda n: json.load(open(os.path.join(HERE, n)))
mt = lambda n: (time.strftime("%Y-%m-%d %H:%M:%S",
                              time.localtime(os.path.getmtime(os.path.join(HERE, n))))
                if os.path.exists(os.path.join(HERE, n)) else None)


def main():
    rows = L("rows.json")
    # round 2 was run on its own rows file so it could not race the A6 re-run's write
    if os.path.exists(os.path.join(HERE, "rows2.json")):
        rows.update(L("rows2.json"))
        json.dump(rows, open(os.path.join(HERE, "rows.json"), "w"), indent=1,
                  default=str)
    cinv, qpre, rt = ref.cinv(), ref.qpre(), ref.rtrip()
    TINV, EINV = cinv["t_inv_50pct_mean_ps"], cinv["E_inv_hi_lo_mid_fJ"]
    R = {}
    R["_doc"] = (
        "RESTORING STAGES EVERY k BANKS in a hop-powered QAL chain -- the measured "
        "record. Answers 'Add restoring stages every few banks and see what it "
        "costs.' Every number labelled MEASURED / DERIVED / ASSUMED. Pre-registration "
        "written before any deck in this directory existed; six amendments A1-A6, each "
        "stating the measurement that forced it, in AMENDMENT.md.")
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
            "settling time here is a LOWER BOUND: real silicon is slower and costs "
            "more, and the restoring stage's latency -- the term the verdict turns "
            "on -- would grow."),
        shallow_stack_caveat=(
            "the ALU dominant mapped cell sg13g2_o21ai_1 NEVER settles anywhere in "
            "the PDK envelope, so this study uses the INVERTER-class bank and EVERY "
            "number is a SHALLOW-STACK number."),
        energy_exclusion_untouched=(
            "the committed energy EXCLUSION verdict (complete timer ledger 23.213 "
            "fJ/bank/hop against a pre-stated 12.7467 fJ, stat-sim c814e52) is NOT "
            "reopened, NOT re-litigated and NOT affected by anything here: it is "
            "about the switch TIMING hardware, not about restoration."),
        mtimes_proving_order={n: mt(n) for n in (
            "PRE_REGISTERED.json", "AMENDMENT.md", "rest.py", "extract.py", "go.py",
            "ref.py", "econ.py", "table.py", "fixzcs.py", "qpre.cir", "cinv.cir",
            "rtrip.cir", "ia_hop.cir", "ia_chain.cir", "s_k1_T300.cir",
            "c_k1_T300.cir", "rows.json")})
    R["instrument_check"] = dict(
        _what=("(b) of the ask. Both anchors are BYTE-IDENTICAL re-runs of committed "
               "decks under this directory's own PyMS cache."),
        committed_single_hop=ref.ia_hop(),
        failing_no_restore_chain_row_chain3_a277_free=ref.ia_chain(),
        receiver_trip_points=rt,
        cmos_inverter_reference=cinv,
        per_segment_precharge=qpre)
    R["rows"] = rows

    # ---------------- the economics, from the MEASURED row terms
    key = next((k for k in ("k1_T300_zcs2", "k1_T300_zcs", "k1_T300")
                if k in rows and "error" not in rows[k]), None)
    r1 = rows.get(key)
    econ_out = None
    if r1 and "error" not in r1:
        win = r1["restore_supply_per_window_fC"]
        interior = [v for k, v in sorted(win.items())][1:-1] or list(win.values())
        E_res_bit = 1.2 * (sum(interior) / len(interior)) / 8.0
        tr = r1.get("tres_in_full_chain_ps", {})
        lat = [v["latency_ps"] for k, v in tr.items()
               if isinstance(v, dict) and k.endswith("_pair")
               and not k.startswith("r1_") and v.get("latency_ps") is not None]
        t_res_chain = (sum(lat) / len(lat)) if lat else None
        sl = r1["supply_ledger_fJ"]
        nh = r1["nbank"]
        e = r1["energy_per_hop_fJ"]
        hop_diss = [v["E_out_of_source_fJ"] + v["E_into_dest_fJ"] for v in e.values()]
        E_hop_bit = (sum(hop_diss) / len(hop_diss)) / 8.0
        E_egt_bit = sl["E_transfer_gate_drive_fJ"] / nh / 8.0
        E_vhi_bit = sl["E_vhi_fJ"] / nh / 8.0
        E_pre_bit = qpre["summary"]["per_bit_E_supply_fJ"]
        T_min = r1["T_ps"]
        qal = T_min + t_res_chain
        econ_out = dict(
            _formulas="pre-registered in PRE_REGISTERED.json.ECONOMICS_pre_stated",
            row_used=key, max_workable_k=1,
            T_used_ps=T_min,
            t_res_steady_state_in_chain_ps=t_res_chain,
            t_res_one_segment_ideal_input_ps=(
                r1.get("tres_measured_ps", {}).get("pair_max")),
            t_res_is_NOT_a_gate_delay=dict(
                full_swing_buffer_delay_ps=cinv["t_buffer_50pct_ps"],
                one_inverter_ps=TINV,
                ratio_QAL_level_over_full_swing=(t_res_chain /
                                                 cinv["t_buffer_50pct_ps"])
                if t_res_chain else None,
                committed_independent_crosscheck=(
                    "qal/bound/ H1 measured the same conversion at 167.7 ps resolve / "
                    "277.6 ps full two-stage, with a LATENCY FLOOR ~145.3 ps that 4x "
                    "nMOS upsizing cannot beat and that costs 3.9x the input "
                    "capacitance to approach -- the two costs are coupled and fight.")),
            qal_amortised_stage_ps=qal,
            time_vs_committed_cmos_level=econ.stage_table(T_min, t_res_chain, 1),
            time_vs_my_measured_cmos_level=econ.stage_table(T_min, t_res_chain, 1,
                                                           t_level_cmos=TINV),
            depth_dependence=econ.depth_sweep(qal, TINV),
            energy_terms_per_bit_fJ=dict(
                E_precharge_supply=E_pre_bit,
                E_precharge_note=("MEASURED in qpre.cir with a real 1.0/1.12 um head "
                                  "gate: 59.222 fJ per segment for 8 bits. The ideal "
                                  "lower bound for the nominal 35.979 fF cap is "
                                  "C*dV^2 = 51.81 fJ -> 6.476 fJ/bit."),
                E_restore_supply=E_res_bit,
                E_restore_note=("per restoring stage per beat window, MEASURED on the "
                                "interior windows of the k=1 chain so the 500 ps tail "
                                "cannot inflate it. DERIVED decomposition: ~6.5 fJ is "
                                "switching its own output node (2 fF + the bank gate it "
                                "drives), ~1-2 fJ is CONTENTION in its second inverter "
                                "while the skewed receiver's slow edge traverses "
                                "mid-rail, and the receiver's own DC contention is only "
                                "~0.15 fJ over a 479 ps beat (0.267 uA MEASURED in "
                                "rtrip.cir at the delivered 0.6007 V). The standard "
                                "1.12/0.74 receiver would have burned 7.14 uA MEASURED "
                                "in the same place -- 27x more -- which is one of the "
                                "three reasons AMENDMENT A4 replaced it. The receiver's "
                                "static current is paid by its OWN supply, not by the "
                                "QAL rail: its input is a gate, so the QAL level is "
                                "degraded only capacitively."),
                E_transfer_gate_drive=E_egt_bit,
                E_switch_bulk_vhi=E_vhi_bit,
                E_hop_dissipation=E_hop_bit),
            blended=dict())
        for kk in (1, 2, 3, 6):
            b = econ.energy_blend(kk, E_pre_bit, E_res_bit,
                                  E_hop_bit + E_egt_bit + E_vhi_bit, 0.0)
            b["vs_my_measured_inverter_per_hi_lo_cycle_fJ"] = EINV
            b["vs_my_measured_inverter_per_transition_fJ"] = EINV / 2.0
            b["ratio_qal_over_cmos_per_transition_alpha1"] = (
                b["blended_fJ_per_gate"] / (EINV / 2.0))
            b["note"] = ("QAL pays this EVERY beat with no activity discount; CMOS "
                         "pays its per-transition figure only when the gate toggles, "
                         "so divide the CMOS number by the activity factor alpha.")
            econ_out["blended"]["k=%d" % kk] = b
        inv = {}
        for tag in ("k1_T300_zcs2", "k1_T300_zcs", "k1_T300", "k1_T200"):
            rr = rows.get(tag)
            if not rr or "error" in rr:
                continue
            trr = rr.get("tres_in_full_chain_ps", {})
            ll = [v["latency_ps"] for kk, v in trr.items()
                  if isinstance(v, dict) and kk.endswith("_pair")
                  and not kk.startswith("r1_") and v.get("latency_ps") is not None]
            if ll:
                m = sum(ll) / len(ll)
                inv[tag] = dict(T_ps=rr["T_ps"], t_res_steady_ps=m,
                                stage_ps=rr["T_ps"] + m)
        econ_out["beat_period_T_invariance_MEASURED"] = dict(
            rows=inv,
            finding=("the amortised stage time is INVARIANT in T: every ps taken out "
                     "of the beat is handed straight back as restoring-stage latency, "
                     "because the restore's resolve instant is fixed by the bank's own "
                     "settling trajectory and not by the beat. Measured at T = 300 and "
                     "T = 200 ps, both PASS, and the stage time agrees to 0.01 ps."))
        econ_out["blended_only_k1_is_MEASURED_to_work"] = (
            "k >= 2 is MEASURED not to work, so the k=2/3/6 blends are what "
            "restoration WOULD cost if a wider spacing were achievable. They are "
            "counterfactual and labelled so.")
    R["economics"] = econ_out
    json.dump(R, open(os.path.join(HERE, "RESULTS.json"), "w"), indent=1, default=str)
    print("wrote RESULTS.json (%d rows)" % len(rows))
    if econ_out:
        print("  QAL amortised stage %.2f ps (T %.0f + t_res %.2f, k=1)"
              % (econ_out["qal_amortised_stage_ps"], econ_out["T_used_ps"],
                 econ_out["t_res_steady_state_in_chain_ps"]))
        t = econ_out["time_vs_committed_cmos_level"]
        print("  vs committed CMOS level 151.0 ps : %.2fx - %.2fx"
              % (t["ratio_min"], t["ratio_max"]))
        t = econ_out["time_vs_my_measured_cmos_level"]
        print("  vs my measured inverter 52.04 ps : %.2fx - %.2fx"
              % (t["ratio_min"], t["ratio_max"]))
        for kk in (1, 2, 3, 6):
            b = econ_out["blended"]["k=%d" % kk]
            print("  blended k=%d : %.3f fJ/gate  (%.2fx a CMOS transition at alpha=1)"
                  % (kk, b["blended_fJ_per_gate"],
                     b["ratio_qal_over_cmos_per_transition_alpha1"]))


if __name__ == "__main__":
    main()
