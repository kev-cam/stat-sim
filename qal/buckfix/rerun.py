#!/usr/bin/env python3
import json, os, sys, subprocess
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chainfix as CF, extract as X
HERE = os.path.dirname(os.path.abspath(__file__))
Z = json.load(open(os.path.join(HERE, "ZEROS_fixed.json")))
JOBS = [dict(name="C2", t_on=12.0, tag="C2", zkey="PC_C2", ltu=None),
        dict(name="C3", t_on=12.0, tag="C3", zkey="PC_C3", ltu=None),
        dict(name="C9", t_on=35.0, tag="C9_L10_t35", zkey="PC_C9_L10_t35", ltu=10.0)]

def one(j):
    cuts = {int(k): round(v["t_zero_ps"], 4) for k, v in Z[j["zkey"]].items()}
    lines, hits = CF.build(j["name"], j["t_on"], zeros=cuts, ltu_nh=j["ltu"])
    fn = "RC_%s.cir" % j["tag"]
    p, msg = CF.run(fn, lines)
    rec = dict(tag=j["tag"], schedule=j["name"], t_on_ps=j["t_on"], ltu_nH=j["ltu"],
               out_open_ps=cuts, lines_replaced=hits, deck=fn, run_msg=msg,
               zcs_probe=Z[j["zkey"]])
    if p is None:
        return rec
    row, prn, S = X.row(p + ".prn", mode="ptu", label=j["tag"])
    rec["row"] = row
    rec["A6_hop"] = X.hop_zero_check(p + ".prn", S)
    rec["A6_topup"] = X.topup_zero_check(p + ".prn", cuts)
    m = {}
    for line in open(p + ".mt0"):
        if "=" in line:
            k, v = line.split("=", 1)
            try: m[k.strip().upper()] = float(v.strip().split()[0])
            except ValueError: pass
    q = {nm: round((m["%s_D" % nm] - m["%s_Z" % nm]) * 1e15, 4)
         for nm in ("QTU3","QTU4","QIND3","QIND4","QSUP","QGABS") if "%s_Z" % nm in m}
    rec["charge_fC"] = q
    if q.get("QSUP"):
        rec["Qdel_over_Qsup"] = round((q.get("QTU3",0)+q.get("QTU4",0))/q["QSUP"], 5)
    return rec

if __name__ == "__main__":
    res = []
    with ThreadPoolExecutor(max_workers=3) as ex:
        for r in ex.map(one, JOBS): res.append(r)
    json.dump(res, open(os.path.join(HERE, "CHAIN_FIXED.json"), "w"), indent=1)
    for r in res:
        print("===", r["tag"], r["run_msg"])
        if "row" in r:
            w = r["row"]
            print("   rails", w["rail_at_bound_V"])
            print("   settling", w["settling_worst_by_stage"], "A1", w["A1_worst_pct"], w["A1_pass"])
            print("   A2 %.6f %s | sep %s" % (w["A2_min_delivered_HIGH_V"], w["A2_pass"], w["separation_mV_by_bank"]))
            print("   charge", r.get("charge_fC"), "Qdel/Qsup", r.get("Qdel_over_Qsup"))
            print("   A6 hop", r["A6_hop"]); print("   A6 topup", r["A6_topup"])
