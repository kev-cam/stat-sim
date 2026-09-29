#!/usr/bin/env python3
"""PHASE 2 -- the beat, measured end to end on the running chain, under the
committed 90% bar and under the functional commit criterion, on the SAME
committed waveform.

banktank's committed `data_valid_instant` is: the first instant in the bank's
window at which ALL 8 gates are >= 90% settled AND pattern-correct, referenced
to the rail at that same instant.  The functional analogue is: the first instant
at which ALL 8 gates are on the correct side of the RECEIVER's measured trip, at
the receiver's rail at that instant, by the noise budget.

Nothing here composes a stage time from parts; every number is read off the
running 4-bank chain.
"""
import bisect, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rescore import Trip, Wave, NB, commit_instants, committed_checkpoints

HERE = os.path.dirname(os.path.abspath(__file__))
QAL = os.path.dirname(HERE)
TRIP = Trip(os.path.join(HERE, "TRIP.json"), "S")
PAT = [1, 1, 1, 0, 1, 0, 0, 1]
MG = 8


def out_hi(k, i):
    in_hi = (PAT[i] == 1) if (k % 2 == 1) else (PAT[i] == 0)
    return not in_hi


def valid_90(w, k, t_from, t_to):
    """committed bar, verbatim in form: >=90% settled AND guard-correct."""
    r = w.s("V(RAIL%d)" % k)
    o = [w.s("V(O%d_%d)" % (k, i)) for i in range(MG)]
    for j in range(len(w.t)):
        if not (t_from <= w.t[j] <= t_to) or r[j] <= 0.05:
            continue
        ok = True
        for i in range(MG):
            v, rr = o[i][j], r[j]
            hi = out_hi(k, i)
            sp = 100.0 * ((v / rr) if hi else (1.0 - v / rr))
            gd = (v >= 0.50 * rr) if hi else (v <= 0.10 * rr)
            if sp < 90.0 or not gd:
                ok = False
                break
        if ok:
            return w.t[j]
    return None


def valid_func(w, k, rxk, t_from, t_to, nb):
    """functional bar: every gate on the correct side of the RECEIVER's measured
    trip at the receiver's rail at that instant, by the noise budget."""
    rr = w.s("V(RAIL%d)" % rxk)
    o = [w.s("V(O%d_%d)" % (k, i)) for i in range(MG)]
    for j in range(len(w.t)):
        if not (t_from <= w.t[j] <= t_to) or rr[j] <= 0.05:
            continue
        vt, _ = TRIP(rr[j])
        ok = True
        for i in range(MG):
            v = o[i][j]
            d = (v - vt) if out_hi(k, i) else (vt - v)
            if d < nb:
                ok = False
                break
        if ok:
            return w.t[j]
    return None


def do(cir, nbank=4, nb=NB["free"]):
    w = Wave(cir + ".prn")
    ck = committed_checkpoints(cir)
    tc = commit_instants(w, nbank)
    out = dict(deck=os.path.basename(cir), commit={k: round(tc[k]["t"], 3) for k in tc},
               ck={k: round(v, 3) for k, v in ck.items()})
    v90, vfn = {}, {}
    for k in range(1, nbank + 1):
        # search from the bank's own rail start to the end of its stage
        t0 = tc[k]["t"] - 400.0
        t1 = ck[k] + 100.0
        v90[k] = valid_90(w, k, t0, t1)
        rxk = k + 1 if k + 1 <= nbank else k
        vfn[k] = valid_func(w, k, rxk, t0, t1, nb)
    out["data_valid_90pct_ps"] = {k: (round(v, 3) if v else None) for k, v in v90.items()}
    out["data_valid_FUNCTIONAL_ps"] = {k: (round(v, 3) if v else None) for k, v in vfn.items()}
    out["gain_ps_per_bank"] = {k: (round(v90[k] - vfn[k], 3)
                                   if (v90[k] and vfn[k]) else None) for k in v90}

    def stages(d):
        s = []
        for k in range(2, nbank + 1):
            if d.get(k) and d.get(k - 1):
                s.append(d[k] - d[k - 1])
        return s
    s90, sfn = stages(v90), stages(vfn)
    out["stage_time_90pct_ps"] = [round(x, 3) for x in s90]
    out["stage_time_FUNCTIONAL_ps"] = [round(x, 3) for x in sfn]
    out["steady_stage_90pct_ps"] = round(sum(s90[1:]) / len(s90[1:]), 3) if len(s90) > 1 else None
    out["steady_stage_FUNCTIONAL_ps"] = round(sum(sfn[1:]) / len(sfn[1:]), 3) if len(sfn) > 1 else None
    return out


if __name__ == "__main__":
    res = []
    for c in sys.argv[1:]:
        res.append(do(c))
        print(json.dumps(res[-1], indent=1))
    json.dump(res, open(os.path.join(HERE, "BEAT.json"), "w"), indent=1)
