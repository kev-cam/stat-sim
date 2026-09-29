#!/usr/bin/env python3
"""A6/A8 CLOSURE: re-probe every current zero on the RESULT deck itself and
re-cut, iterating until every interrupted current is below the 1 uA gate.

This is the discipline the pre-registration calls for: 'true current zeros
RE-PROBED per L, per hop and per top-up bank, separately, for EVERY schedule
change'.  A zero measured on a PROBE deck is not the zero of the RESULT deck,
because the result deck's rails differ -- so the probe only seeds the iteration."""
import json, os, re, sys
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chainfix as CF, extract as X
HERE = os.path.dirname(os.path.abspath(__file__))
E = 2.0

def fz(p, name, t_from):
    c = p.col(name); prev = None
    for j, t in enumerate(p.t):
        if t < t_from: prev = (t, p.rows[j][c]); continue
        cur = (t, p.rows[j][c])
        if prev and prev[1] > 0.0 >= cur[1]:
            t1, i1 = prev; t2, i2 = cur
            return t1 + (t2 - t1) * i1 / (i1 - i2)
        prev = cur
    return None

def retime_hop(lines, h, t_open):
    """Move hop h's switch-open (and its park) to t_open.  A8."""
    out = []
    for L in lines:
        m = re.match(r"^(VGT%d|VGTP%d|VPK%d)\s" % (h, h, h), L)
        if not m: out.append(L); continue
        nums = re.findall(r"([0-9.]+)p", L)
        if m.group(1).startswith("VPK"):
            new = "%s %s 0 PWL(0 %s %sp %s %sp %s %gp %s %gp %s)" % (
                m.group(1), L.split()[1], "1.5", nums[0], "1.5", nums[1], "0",
                t_open + E, "0", t_open + 2 * E, "1.5")
        elif m.group(1).startswith("VGTP"):
            new = "%s %s 0 PWL(0 1.5 %sp 1.5 %sp 0 %gp 0 %gp 1.5)" % (
                m.group(1), L.split()[1], nums[0], nums[1], t_open, t_open + E)
        else:
            new = "%s %s 0 PWL(0 0 %sp 0 %sp 1.5 %gp 1.5 %gp 0)" % (
                m.group(1), L.split()[1], nums[0], nums[1], t_open, t_open + E)
        out.append(new)
    return out

def one(j):
    cuts = dict(j["cuts"]); hop2 = j.get("hop2")
    hist = []
    for it in range(3):
        lines, hits = CF.build(j["name"], j["t_on"], zeros=cuts, ltu_nh=j["ltu"])
        if hop2: lines = retime_hop(lines, 2, hop2)
        fn = "RF_%s.cir" % j["tag"]
        p, msg = CF.run(fn, lines)
        if p is None: return dict(tag=j["tag"], error=msg)
        pr = X.SX.PRN(p + ".prn")
        z3 = fz(pr, "I(LTU3)", j["t3"]); z4 = fz(pr, "I(LTU4)", j["t4"])
        zl2 = fz(pr, "I(L2)", 450.0)
        i3 = abs(pr.at("I(LTU3)", cuts[3])) * 1e6
        i4 = abs(pr.at("I(LTU4)", cuts[4])) * 1e6
        il2 = abs(pr.at("I(L2)", hop2 or 498.096)) * 1e6
        il1 = abs(pr.at("I(L1)", 301.137)) * 1e6
        hist.append(dict(iter=it, msg=msg, cuts=dict(cuts), hop2=hop2,
                         IZ_topup3_uA=round(i3, 6), IZ_topup4_uA=round(i4, 6),
                         IZ_hop1_uA=round(il1, 6), IZ_hop2_uA=round(il2, 6)))
        if max(i3, i4, il1, il2) < 1.0:
            break
        if z3: cuts[3] = round(z3, 4)
        if z4: cuts[4] = round(z4, 4)
        if zl2: hop2 = round(zl2, 4)
    row, prn, S = X.row(p + ".prn", mode="ptu", label=j["tag"])
    m = {}
    for line in open(p + ".mt0"):
        if "=" in line:
            k, v = line.split("=", 1)
            try: m[k.strip().upper()] = float(v.strip().split()[0])
            except ValueError: pass
    q = {nm: round((m["%s_D" % nm] - m["%s_Z" % nm]) * 1e15, 4)
         for nm in ("QTU3","QTU4","QIND3","QIND4","QSUP","QGABS") if "%s_Z" % nm in m}
    e = {nm: round((m["%s_D" % nm] - m["%s_Z" % nm]) * 1e15, 5)
         for nm in ("ETU3","ETU4","EGTU") if "%s_Z" % nm in m}
    return dict(tag=j["tag"], schedule=j["name"], t_on_ps=j["t_on"], ltu_nH=j["ltu"],
                deck="RF_%s.cir" % j["tag"], iterations=hist, final_cuts=cuts,
                final_hop2_open_ps=hop2, row=row, charge_fC=q, energy_fJ=e,
                Qdel_over_Qsup=(round((q.get("QTU3",0)+q.get("QTU4",0))/q["QSUP"], 5)
                                if q.get("QSUP") else None),
                A6=dict(worst_uA=round(max(hist[-1]["IZ_topup3_uA"], hist[-1]["IZ_topup4_uA"],
                                           hist[-1]["IZ_hop1_uA"], hist[-1]["IZ_hop2_uA"]), 6),
                        pass_=bool(max(hist[-1]["IZ_topup3_uA"], hist[-1]["IZ_topup4_uA"],
                                       hist[-1]["IZ_hop1_uA"], hist[-1]["IZ_hop2_uA"]) < 1.0)))

JOBS = [dict(name="C2", t_on=12.0, tag="C2", ltu=None, t3=357.2, t4=554.2,
             cuts={3: 362.506, 4: 559.6426}, hop2=498.096),
        dict(name="C3", t_on=12.0, tag="C3", ltu=None, t3=361.2, t4=558.2,
             cuts={3: 365.4964, 4: 562.5454}, hop2=498.096),
        dict(name="C9", t_on=35.0, tag="C9_L10_t35", ltu=10.0, t3=340.2, t4=537.2,
             cuts={3: 380.3768, 4: 576.9285}, hop2=498.2206)]

if __name__ == "__main__":
    res = []
    with ThreadPoolExecutor(max_workers=3) as ex:
        for r in ex.map(one, JOBS): res.append(r)
    json.dump(res, open(os.path.join(HERE, "CHAIN_FINAL.json"), "w"), indent=1)
    for r in res:
        if "row" not in r: print("===", r["tag"], "FAILED", r.get("error")); continue
        w = r["row"]
        print("===", r["tag"], "iters", len(r["iterations"]), "A6", r["A6"])
        print("   rails", w["rail_at_bound_V"])
        print("   settling", w["settling_worst_by_stage"], "A1", w["A1_worst_pct"], w["A1_pass"])
        print("   A2 %.6f %s | sep %s" % (w["A2_min_delivered_HIGH_V"], w["A2_pass"], w["separation_mV_by_bank"]))
        print("   charge", r["charge_fC"], "Qd/Qs", r["Qdel_over_Qsup"], "energy", r["energy_fJ"])
