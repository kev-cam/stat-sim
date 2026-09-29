#!/usr/bin/env python3
"""(c) the charge audit + (d) the simultaneous-conduction test, on the fixture."""
import json, os, sys
from concurrent.futures import ThreadPoolExecutor
import buck as B, audit as A

HERE = os.path.dirname(os.path.abspath(__file__))
CB = 100.0          # fF, ASSUMED bank capacitance; DERIVED ~108 fF from the
                    # committed pair (9.26 fC delivered / 85.64 mV rail rise).
VRAIL0 = 0.766      # V, the committed no-top-up control rail3


def one(name, t_on=12.0, cb=CB, ltu=B.LTU_NH, cna=B.CNA_FF, vrail0=VRAIL0):
    mk = {"C1_committed": B.sched_committed, "C2_bbm_turn_on": B.sched_fix1,
          "C3_bbm_both_edges": B.sched_fix2, "C4_out_spans_pulse": B.sched_fix3,
          "C5_textbook_buck": B.sched_fix4}
    s = mk[name](t_on)
    tag = "t%g_C%g_L%g" % (t_on, cb, ltu)
    # A6: RE-PROBE the true inductor zero for THIS schedule
    z, zmsg = A.probe_zero(s, cb, 460.0, ltu, cna, vrail0, tag)
    rec = dict(schedule=name, t_on_ps=t_on, C_bank_fF=cb, Ltu_nH=ltu,
               Cna_fF=cna, vrail0_V=vrail0, probe=z, probe_msg=zmsg)
    if z is None:
        return rec
    if name == "C1_committed":
        # the committed deck cut OUT at 363.355 ps (MEASURED off the file); keep
        # that exact cut so the reproduction is of the reported circuit.
        s = dict(s, out_open=363.355)
        rec["out_open_ps"] = 363.355
        rec["out_open_source"] = "the committed deck's own cut, verbatim"
    else:
        s = dict(s, out_open=round(z["t_zero_ps"], 4))
        rec["out_open_ps"] = round(z["t_zero_ps"], 4)
        rec["out_open_source"] = "RE-PROBED for this schedule (A6)"
    led, msg = A.ledger(s, cb, 460.0, ltu, cna, vrail0, tag)
    rec["run_msg"] = msg
    if led is None:
        return rec
    rec["ledger"] = led
    rec["crossconduction"] = A.crossconduction(s, cb, 460.0, tag)
    rec["schedule_ps"] = {k: v for k, v in s.items()
                          if k in ("hs_off_lo", "hs_on_hi", "fw_off", "fw_on",
                                   "out_close", "out_open", "pulse")}
    return rec


if __name__ == "__main__":
    which = sys.argv[1:] or ["C1_committed"]
    out = {}
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(one, w): w for w in which}
        for f in futs:
            w = futs[f]
            try:
                out[w] = f.result()
            except Exception as e:
                out[w] = dict(error=repr(e))
    p = os.path.join(HERE, "AUDIT_%s.json" % "_".join(w[:2] for w in which))
    json.dump(out, open(p, "w"), indent=1)
    for w, r in out.items():
        print("=== %s" % w)
        if "error" in r:
            print("   ERROR", r["error"]); continue
        print("   probe:", r.get("probe"), r.get("probe_msg"))
        L = r.get("ledger", {}).get("LEDGER")
        if L:
            print("   Qsup %.4f fC | to-ground %.4f | into-L %.4f | CNA %.4f | "
                  "gateHS %.4f | gateFW %.4f | resid %.5f (%.4f%%)"
                  % (L["q_supply_fC"], L["sinks"]["to_ground_via_freewheel_fC"],
                     L["sinks"]["into_inductor_fC"], L["sinks"]["into_switch_node_CNA_fC"],
                     L["sinks"]["HS_gate_overlap_fC"], L["sinks"]["FW_gate_overlap_fC"],
                     L["KCL_residual_fC"], L["KCL_residual_pct_of_supply"] or 0.0))
            print("   Qbank %.4f fC | Qdel/Qsup %.5f | eta_E %.5f | rail rise %.4f mV"
                  % (L["q_into_bank_fC"], L["Qdel_over_Qsup"] or 0.0,
                     L["eta_energy"] or 0.0, r["ledger"]["rail_rise_mV"]))
        X = r.get("crossconduction")
        if X:
            print("   BOTH-ON windows %s  total %.3f ps  peak %.1f uA  Q_shoot %.3f fC"
                  % (X["windows_ps"], X["total_both_on_ps"],
                     X["peak_shootthrough_uA"], X["Q_shootthrough_fC"]))
    print("wrote", p)
