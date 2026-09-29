#!/usr/bin/env python3
"""Fixture sweep: which schedule + switch-node sizing actually makes the buck
deliver?  Every row is a probe deck (A6 ZCS re-probe) plus a result deck."""
import json, os, sys
from concurrent.futures import ThreadPoolExecutor
import buck as B, audit as A

HERE = os.path.dirname(os.path.abspath(__file__))
MK = {"C1": B.sched_committed, "C2": B.sched_fix1, "C3": B.sched_fix2,
      "C4": B.sched_fix3, "C5": B.sched_fix4, "C6": B.sched_fix5,
      "C7": B.sched_fix6, "C8": B.sched_fix7,
      "C9": B.sched_fix8}


def one(cfg):
    name, t_on, cb, ltu, cna, wsw = (cfg["s"], cfg["t_on"], cfg["cb"],
                                     cfg["ltu"], cfg["cna"], cfg["w"])
    s = (B.sched_fix7(t_on, 2.0, cfg.get('settle', 8.0)) if name == 'C8'
         else B.sched_fix8(t_on, 2.0, cfg.get('settle', 8.0), cfg.get('tfire', 313.137)) if name == 'C9'
         else MK[name](t_on))
    tag = "t%g_C%g_L%g_N%g_W%g_S%g_F%g" % (t_on, cb, ltu, cna, wsw, cfg.get('settle', 8.0), cfg.get('tfire', 313.137))
    tstop = max(460.0, s["pulse"][1] + 100.0)
    z, zmsg = A.probe_zero(s, cb, tstop, ltu, cna, 0.766, tag, wsw)
    rec = dict(cfg, tag=tag, probe=z, probe_msg=zmsg)
    if z is None:
        return rec
    if s.get("no_out"):
        s = dict(s, fw_cut=round(z["t_zero_ps"], 4))
        rec["fw_cut_ps"] = s["fw_cut"]
    else:
        s = dict(s, out_open=round(z["t_zero_ps"], 4))
        rec["out_open_ps"] = s["out_open"]
    led, msg = A.ledger(s, cb, tstop, ltu, cna, 0.766, tag, wsw)
    rec["run_msg"] = msg
    if led is None:
        return rec
    rec["L"] = led["LEDGER"]
    rec["rail_rise_mV"] = led["rail_rise_mV"]
    rec["I_L_peak_uA"] = led["I_L_peak_uA"]
    rec["phases"] = led["phases"]
    rec["na_V"] = led["na_V"]
    rec["rail_V"] = led["rail_V"]
    rec["schedule_ps"] = {k: v for k, v in s.items()
                          if k in ("hs_off_lo", "hs_on_hi", "fw_off", "fw_on",
                                   "out_close", "out_open", "fw_cut", "pulse")}
    rec["cross"] = A.crossconduction(s, cb, tstop, tag)
    return rec


if __name__ == "__main__":
    cfgs = json.loads(sys.argv[1])
    out = []
    with ThreadPoolExecutor(max_workers=4) as ex:
        for r in ex.map(one, cfgs):
            out.append(r)
    name = sys.argv[2]
    json.dump(out, open(os.path.join(HERE, name), "w"), indent=1)
    print("%-4s %6s %5s %5s %5s %5s | %9s %9s %9s %9s %8s %8s"
          % ("sch", "t_on", "Cb", "Ltu", "Cna", "W", "Qsup", "Qgnd", "Qbank",
             "Qd/Qs", "eta_E", "railmV"))
    for r in out:
        if "L" not in r:
            print(r["s"], "FAILED", r.get("probe_msg"), r.get("run_msg")); continue
        L = r["L"]
        print("%-4s %6g %5g %5g %5g %5g | %9.3f %9.3f %9.3f %9.4f %8.4f %8.2f"
              % (r["s"], r["t_on"], r["cb"], r["ltu"], r["cna"], r["w"],
                 L["q_supply_fC"], L["sinks"]["to_ground_via_freewheel_fC"],
                 L["q_into_bank_fC"], L["Qdel_over_Qsup"] or 0,
                 L["eta_energy"] or 0, r["rail_rise_mV"]))
    print("wrote", name)
