#!/usr/bin/env python3
"""SKEPTIC chain metrics, computed from MY .prn traces only.

Chain structure, read off the deck (not taken from anyone's report):
  inputs in1_k alternate 1.2 / 0, k even HIGH.
  bank b cell k is an inverter: pMOS source = rail_b, nMOS source = gn_b (0 V).
  -> bank1 pull-UP cells are ODD k, bank2 EVEN, bank3 ODD, bank4 EVEN.
  Per-bank evaluation boundary, from the deck's own O<b>_kS measures:
     bank1 199 ps, bank2 399 ps, bank3 401 ps, bank4 601 ps.
  rail1/rail2 are driven from vdv=1.2 through gates that OPEN at 180/380 ps,
  so both float at their boundary. rail3/rail4 are charged by the hops.
"""
import sys, os, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from anal import Trace, read_mt0, P

BOUND = {1: 199.0, 2: 399.0, 3: 401.0, 4: 601.0}
# pull-up cells per bank (input LOW -> output should reach the rail)
PU = {1: [1,3,5,7], 2: [0,2,4,6], 3: [1,3,5,7], 4: [0,2,4,6]}

def bank_metrics(tr, b):
    t = BOUND[b] * P
    rail = tr.at("V(rail%d)" % b, t)
    pu, pd = [], []
    cells = {}
    for k in range(8):
        v = tr.at("V(o%d_%d)" % (b, k), t)
        cells[k] = v
        if k in PU[b]:
            pu.append(v)
        else:
            pd.append(v)
    # settling: how far each cell got toward its own target
    set_pu = [v / rail for v in pu] if rail != 0 else [float("nan")] * len(pu)
    set_pd = [1.0 - v / rail for v in pd] if rail != 0 else [float("nan")] * len(pd)
    worst = min(set_pu + set_pd)
    return dict(bank=b, t_ps=BOUND[b], rail=rail,
                pu_min=min(pu), pu_max=max(pu), pd_min=min(pd), pd_max=max(pd),
                set_pu_min=min(set_pu), set_pd_min=min(set_pd),
                worst_settle=worst,
                worst_kind=("pull-up" if min(set_pu) <= min(set_pd) else "pull-down"),
                separation_mV=(min(pu) - max(pd)) * 1e3,
                cells=cells)

def analyse(prn, label):
    tr = Trace(prn)
    banks = [bank_metrics(tr, b) for b in (1, 2, 3, 4)]
    sep = [b["separation_mV"] for b in banks]
    rails = [b["rail"] for b in banks]
    # per-hop separation ratios (adjacent banks in the logic chain)
    sep_ratio = [sep[i+1] / sep[i] if sep[i] else float("nan") for i in range(3)]
    # geometric mean of the separation ratios (signs are all positive here; if
    # any is negative the geomean is reported as nan and the raw list stands)
    try:
        gm_sep = math.exp(sum(math.log(r) for r in sep_ratio) / len(sep_ratio))
    except ValueError:
        gm_sep = float("nan")
    # per-hop RAIL collapse: the skip chain's actual hops are 1->3 and 2->4
    r13 = rails[2] / rails[0]
    r24 = rails[3] / rails[1]
    gm_rail = math.sqrt(r13 * r24)
    return dict(label=label, prn=os.path.basename(prn),
                banks=banks, separation_mV=sep, rails=rails,
                sep_ratio=sep_ratio, sep_ratio_geomean=gm_sep,
                rail_ratio_1to3=r13, rail_ratio_2to4=r24,
                rail_collapse_geomean=gm_rail,
                worst_settle_pct=[b["worst_settle"] * 100 for b in banks])

def depth_to(v0, ratio, floor):
    """DERIVED: hops until v0*ratio^n <= floor."""
    if ratio <= 0 or ratio >= 1 or v0 <= floor:
        return None
    return math.ceil(math.log(floor / v0) / math.log(ratio))

if __name__ == "__main__":
    out = {}
    for arg in sys.argv[1:]:
        lbl, prn = arg.split("=", 1)
        out[lbl] = analyse(prn, lbl)
    print(json.dumps(out, indent=1))
