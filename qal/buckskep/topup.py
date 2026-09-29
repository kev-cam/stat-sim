#!/usr/bin/env python3
"""Measure what the top-up actually DOES to each rail, and test whether its
effect is ADDITIVE (fixed charge into a fixed bank) or MULTIPLICATIVE (a fixed
ratio). This matters because every 'depth to the thermodynamic floor' number in
this campaign -- the committed ones and the prior agent's -- is a GEOMETRIC
extrapolation of a per-hop rail ratio measured on exactly TWO first-generation
hops (rail1->rail3 and rail2->rail4), both starting from a 1.2 V source rail.
If the top-up delivers a roughly fixed charge, the rail sequence is not
geometric and the extrapolated depth is not licensed by the data."""
import sys, os, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from anal import Trace, read_mt0, P

FC = 1e-15
# just before each top-up fires, and each bank's own boundary
PRE3, POST3 = 304.0, 401.0
PRE4, POST4 = 501.0, 601.0

def measure(prn, label):
    tr = Trace(prn)
    r3pre = tr.at("V(rail3)", PRE3 * P); r3post = tr.at("V(rail3)", POST3 * P)
    r4pre = tr.at("V(rail4)", PRE4 * P); r4post = tr.at("V(rail4)", POST4 * P)
    out = dict(label=label,
               rail3_pre=r3pre, rail3_post=r3post, dV3_mV=(r3post - r3pre) * 1e3,
               rail4_pre=r4pre, rail4_post=r4post, dV4_mV=(r4post - r4pre) * 1e3,
               ratio3=r3post / r3pre if r3pre else None,
               ratio4=r4post / r4pre if r4pre else None)
    # charge actually delivered through each OUT switch over the top-up window
    if tr.has("I(VMTU3)"):
        out["Qdel3_fC"] = tr.integ("I(VMTU3)", PRE3 * P, POST3 * P) / FC
    if tr.has("I(VMTU4)"):
        out["Qdel4_fC"] = tr.integ("I(VMTU4)", PRE4 * P, POST4 * P) / FC
    # supply charge drawn over each window
    if tr.has("I(VTSUP)"):
        out["Qsup3_fC"] = -tr.integ("I(VTSUP)", PRE3 * P, POST3 * P) / FC
        out["Qsup4_fC"] = -tr.integ("I(VTSUP)", PRE4 * P, POST4 * P) / FC
    # effective bank capacitance implied by charge / voltage change
    for n in (3, 4):
        q = out.get("Qdel%d_fC" % n); dv = out.get("dV%d_mV" % n)
        if q is not None and dv:
            out["Cbank%d_fF_implied" % n] = (q * FC) / (dv * 1e-3) / 1e-15
    return out

if __name__ == "__main__":
    res = {}
    for spec in sys.argv[1:]:
        lbl, prn = spec.split("=", 1)
        if os.path.exists(prn):
            res[lbl] = measure(prn, lbl)
    print(json.dumps(res, indent=1))
