#!/usr/bin/env python3
"""Chain extraction, reusing the COMMITTED extractor (qal/ptusk/sk_extract.py)
unmodified so that my rows and the committed rows are produced by the same code.
"""
import os, sys
sys.path.insert(0, "/usr/local/src/stat-sim/qal/ptusk")
sys.path.insert(0, "/usr/local/src/stat-sim/qal/skiptu")
sys.path.insert(0, "/usr/local/src/stat-sim/qal/skip4")
import sk_extract as SX
import skip as SK
import tu as TU   # tu.py registers SCHED["s4"]/["s5"] on import (skiptu harness)

VTP = 0.4402734                    # MEASURED |Vtp|, committed constant
SIGMA_VT_MV = 3.42                 # MEASURED PDK constant (qal/vtreq/analyse.py)
KT_Q_FLOOR_MV = 35.838             # 2(kT/q)ln2 at 300 K, the Swanson-Meindl bound

# MEASURED off the committed rows (qal/ptusk/SK_ROWS_triple.json)
TZ = {"free": [97.9774, 94.946], "ptu": [101.137, 98.0963]}


def sched(mode="ptu", T=200.0, dv=1.2, scheme="s4"):
    return SK.schedule(scheme, T, dv, TZ[mode])


def row(prn_path, mode="ptu", T=200.0, dv=1.2, scheme="s4", label=""):
    S = sched(mode, T, dv, scheme)
    nb = S["nbank"]
    p = SX.PRN(prn_path)
    st = SX.settling(p, S, nb)
    sep = SX.separation(p, S, nb)
    dl = SX.delivered(p, S, nb)
    o = dict(label=label, prn=os.path.basename(prn_path),
             bound_ps={k: S["bound"][k] for k in S["bound"]},
             settling_worst_by_stage={k: (round(st[k]["worst_pct"], 2)
                                          if st[k]["worst_pct"] is not None else None)
                                      for k in st},
             settling_per_gate={k: {i: dict(v_o=round(v["v_o"], 6), kind=v["kind"],
                                            settle_pct=(round(v["settle_pct"], 2)
                                                        if v["settle_pct"] is not None else None))
                                    for i, v in st[k]["per_gate"].items()} for k in st},
             rail_at_bound_V={k: round(st[k]["rail_at_bound_V"], 6) for k in st},
             separation_mV_by_bank={k: round(sep[k]["separation_mV"], 4) for k in sep},
             separation_inverted={k: sep[k]["inverted"] for k in sep},
             min_delivered_HIGH_V={k: round(dl[k]["min_delivered_HIGH_V"], 6) for k in dl},
             max_pulldown_V_by_bank={k: round(sep[k]["max_pulldown_V"], 6) for k in sep},
             min_pullup_V_by_bank={k: round(sep[k]["min_pullup_V"], 6) for k in sep})
    got = [v for v in o["settling_worst_by_stage"].values() if v is not None]
    o["A1_worst_pct"] = min(got) if got else None
    o["A1_pass"] = bool(o["A1_worst_pct"] is not None and o["A1_worst_pct"] >= 90.0)
    o["A2_min_delivered_HIGH_V"] = min(o["min_delivered_HIGH_V"].values())
    o["A2_pass"] = bool(o["A2_min_delivered_HIGH_V"] >= 0.4400)
    o["rail3_at_bound_V"] = o["rail_at_bound_V"][3]
    o["pmos_overdrive_over_Vtp_V"] = round(o["rail_at_bound_V"][3] - VTP, 6)
    o["victim_max_pulldown_at_bound2_V"] = o["max_pulldown_V_by_bank"][2]
    o["rail2_at_bound_V"] = o["rail_at_bound_V"][2]
    return o, p, S


def hop_zero_check(prn_path, S, names=("I(L1)", "I(L2)")):
    """A6: the interrupted current at each hop switch open, in uA."""
    p = SX.PRN(prn_path)
    out = {}
    for h, nm in enumerate(names):
        t = S["open"][h]
        out[nm] = round(p.at(nm, t) * 1e6, 7)
    out["worst_abs_uA"] = max(abs(v) for k, v in out.items() if k != "worst_abs_uA")
    out["A6_pass"] = bool(out["worst_abs_uA"] < 1.0)
    return out


def topup_zero_check(prn_path, opens):
    """A6 for the TOP-UP inductor: I(LTU_k) at the instant OUT_k opens."""
    p = SX.PRN(prn_path)
    out = {}
    for k, t in opens.items():
        out[str(k)] = round(p.at("I(LTU%d)" % k, t) * 1e6, 7)
    out["worst_abs_uA"] = max(abs(v) for kk, v in out.items() if kk != "worst_abs_uA")
    out["A6_pass"] = bool(out["worst_abs_uA"] < 1.0)
    return out


def collapse_ratio(rails):
    """PER-HOP RAIL COLLAPSE RATIO, measured on the chain's own rails.
    The skip chain's hops are 1->3 and 2->4, so the two measurable hops are
    rail3/rail1 and rail4/rail2, each read at the RECEIVING bank's own boundary
    against the SOURCE bank's rail at ITS own boundary."""
    out = {}
    for src, dst in ((1, 3), (2, 4)):
        a, b = rails[src], rails[dst]
        out["%d->%d" % (src, dst)] = dict(source_rail_V=round(a, 6),
                                          dest_rail_V=round(b, 6),
                                          ratio=round(b / a, 6) if a else None)
    rs = [v["ratio"] for v in out.values() if v["ratio"]]
    out["geomean_ratio"] = round((rs[0] * rs[1]) ** 0.5, 6) if len(rs) == 2 else None
    return out


def depth_to_floor(v0, ratio, floor_mV):
    """Smallest depth n (hops beyond the head) with v0 * ratio**n <= floor."""
    import math
    if not (0 < ratio < 1) or v0 <= 0:
        return None
    return math.ceil(math.log((floor_mV * 1e-3) / v0) / math.log(ratio))
