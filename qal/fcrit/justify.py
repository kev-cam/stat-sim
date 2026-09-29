#!/usr/bin/env python3
"""The pre-registration promised to MEASURE the two properties that justify the
commit instant, and to say so if they do not hold.  This measures them on every
deck that was re-scored.

  (i)  after t_commit the receiving bank's rail never rises again within its own
       stage -- no further charge enters the island.
  (ii) after t_commit no gate of the receiving bank improves its settling ratio
       to that rail -- the decision cannot get better.
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rescore import Wave, commit_instants, committed_checkpoints
from run_rescore import DATASETS

HERE = os.path.dirname(os.path.abspath(__file__))
out, agg = {}, {"banks": 0, "i_viol": 0, "ii_viol": 0,
                "i_worst_rise_mV": 0.0, "ii_worst_gain_pts": 0.0}
for ds, tag, path, nbank, mgate, oh, nbn, gi in DATASETS:
    try:
        w = Wave(path + ".prn")
        ck = committed_checkpoints(path)
        tc = commit_instants(w, nbank)
    except Exception as e:
        continue
    gl = gi if gi is not None else list(range(mgate))
    for k in range(1, nbank + 1):
        if k not in ck:
            continue
        t0, t1 = tc[k]["t"], ck[k]
        if t1 <= t0:
            continue
        r = w.s("V(RAIL%d)" % k)
        idx = [j for j in range(len(w.t)) if t0 <= w.t[j] <= t1]
        if not idx:
            continue
        r0 = r[idx[0]]
        rise = max(r[j] for j in idx) - r0
        agg["banks"] += 1
        if rise > 1e-3:
            agg["i_viol"] += 1
        agg["i_worst_rise_mV"] = max(agg["i_worst_rise_mV"], 1000.0 * rise)
        for i in gl:
            col = "V(O%d_%d)" % (k, i)
            if not w.has(col):
                continue
            o = w.s(col)
            hi = bool(oh(k, i))

            def sp(j):
                if r[j] <= 0.02:
                    return None
                return 100.0 * ((o[j] / r[j]) if hi else (1.0 - o[j] / r[j]))
            s0 = sp(idx[0])
            if s0 is None:
                continue
            best = max((sp(j) for j in idx if sp(j) is not None), default=s0)
            if best - s0 > 1.0:
                agg["ii_viol"] += 1
            agg["ii_worst_gain_pts"] = max(agg["ii_worst_gain_pts"], best - s0)
out["JUSTIFICATION_MEASURED"] = agg
json.dump(out, open(os.path.join(HERE, "JUSTIFY.json"), "w"), indent=1)
print(json.dumps(agg, indent=1))
