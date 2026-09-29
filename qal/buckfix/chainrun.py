#!/usr/bin/env python3
"""Run a fixed top-up schedule on the FULL committed chain deck.

Protocol per schedule, in order:
  1. PROBE deck  -- identical to the result deck except the OUT switch gate is
     held past the transient end, so I(LTU_k) runs free and its TRUE first zero
     after the peak can be measured (A6).  One probe per schedule, per bank.
  2. RESULT deck -- the same gate schedule with OUT cut at that measured zero.
  3. Extraction with qal/ptusk/sk_extract.py, unmodified.
"""
import json, os, sys, bisect
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chainfix as CF
import extract as X

HERE = os.path.dirname(os.path.abspath(__file__))


def zeros_from(prn, banks=(3, 4), after={3: 313.137, 4: 510.096}):
    p = X.SX.PRN(prn)
    out = {}
    for k in banks:
        c = p.col("I(LTU%d)" % k)
        t0 = after.get(k, after.get(str(k), 313.137))
        pk, tpk = 0.0, None
        for j, t in enumerate(p.t):
            if t >= t0 and p.rows[j][c] > pk:
                pk, tpk = p.rows[j][c], t
        if tpk is None:
            out[k] = None
            continue
        z = None
        for j in range(1, len(p.t)):
            if p.t[j] <= tpk:
                continue
            i1, i2 = p.rows[j - 1][c], p.rows[j][c]
            if i2 <= 0.0 < i1:
                z = p.t[j - 1] + (p.t[j] - p.t[j - 1]) * i1 / (i1 - i2)
                break
            if i2 <= 0.0:
                z = p.t[j]
                break
        out[k] = dict(t_zero_ps=z, i_peak_uA=pk * 1e6, t_peak_ps=tpk)
    return out


def do(name, t_on=12.0, tag=None, ltu_nh=None, after=None):
    tag = tag or name
    lines, hits = CF.build(name, t_on, probe=True, ltu_nh=ltu_nh)
    pfn = "PC_%s.cir" % tag
    p, pmsg = CF.run(pfn, lines)
    rec = dict(schedule=name, t_on_ps=t_on, tag=tag, ltu_nH=ltu_nh, gate_lines_replaced=hits,
               probe_deck=pfn, probe_msg=pmsg)
    if p is None:
        return rec
    z = zeros_from(p + ".prn", after=(after or {3: 313.137, 4: 510.096}))
    rec["topup_zeros"] = z
    if any(v is None or v.get("t_zero_ps") is None for v in z.values()):
        rec["error"] = "no top-up zero found"
        return rec
    cuts = {k: round(v["t_zero_ps"], 4) for k, v in z.items()}
    rec["out_open_ps"] = cuts
    lines, hits = CF.build(name, t_on, zeros=cuts, ltu_nh=ltu_nh)
    rfn = "RC_%s.cir" % tag
    r, rmsg = CF.run(rfn, lines)
    rec["result_deck"] = rfn
    rec["run_msg"] = rmsg
    if r is None:
        return rec
    row, prn, S = X.row(r + ".prn", mode="ptu", label=tag)
    rec["row"] = row
    rec["A6_hop"] = X.hop_zero_check(r + ".prn", S)
    rec["A6_topup"] = X.topup_zero_check(r + ".prn", cuts)
    m = {}
    for line in open(r + ".mt0"):
        if "=" in line:
            k, v = line.split("=", 1)
            try:
                m[k.strip().upper()] = float(v.strip().split()[0])
            except ValueError:
                pass
    fC = 1e15
    q = {}
    for nm in ("QTU3", "QTU4", "QIND3", "QIND4", "QSUP", "QGABS"):
        if "%s_Z" % nm in m:
            q[nm] = round((m["%s_D" % nm] - m["%s_Z" % nm]) * fC, 4)
    rec["charge_fC"] = q
    if q.get("QSUP"):
        rec["Qdel_over_Qsup"] = round((q.get("QTU3", 0) + q.get("QTU4", 0))
                                      / q["QSUP"], 5)
    return rec


if __name__ == "__main__":
    jobs = json.loads(sys.argv[1])
    outname = sys.argv[2]
    res = []
    with ThreadPoolExecutor(max_workers=int(sys.argv[3]) if len(sys.argv) > 3 else 2) as ex:
        for r in ex.map(lambda j: do(**j), jobs):
            res.append(r)
    json.dump(res, open(os.path.join(HERE, outname), "w"), indent=1)
    for r in res:
        print("===", r["tag"], r.get("probe_msg"), "|", r.get("run_msg"))
        if "row" in r:
            w = r["row"]
            print("   rails", w["rail_at_bound_V"], " settling", w["settling_worst_by_stage"])
            print("   A1 %.2f%% pass=%s | A2 %.6f pass=%s | sep %s"
                  % (w["A1_worst_pct"], w["A1_pass"], w["A2_min_delivered_HIGH_V"],
                     w["A2_pass"], w["separation_mV_by_bank"]))
            print("   charge", r.get("charge_fC"), "Qdel/Qsup", r.get("Qdel_over_Qsup"))
            print("   A6 hop", r["A6_hop"], "A6 topup", r["A6_topup"])
        else:
            print("   ", r.get("error"), r.get("probe_msg"), r.get("run_msg"))
    print("wrote", outname)
