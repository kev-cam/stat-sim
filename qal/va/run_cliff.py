#!/usr/bin/env python3
"""Functional-cliff probe: settling collapses when the rail cannot clear |Vtp|.

T0 ANCHOR (measured, transistor): gate settling in the fixed-topology hop is
34.8% @dV=0.6, 77.1% @0.8, 100% @1.0, 100% @1.2 (qal_hop_corrected.json _doc,
baked into qal_isocurrent.py SETTLE), where settling %% = V(o1)/V_bank at hold
(qal_bodybias.py:33) and V_bank is the ACHIEVED bank voltage after the hop --
V_B_end = 0.37251 / 0.46688 / 0.58291 / 0.7179 V for dV = 0.6/0.8/1.0/1.2 at
L=400 nH (qal_hop_corrected.json rows). So the apples-to-apples probe is: ramp
the rail 0 -> V_RAIL over a hop-like 400 ps, hold, and read V(y)/V_RAIL.

EXPECTED QUALITATIVE SHAPE: with the corrected source reference and the fitted
VTP=0.50, conduction requires rail > VTP -- settling collapses for rails that
cannot clear it (0.373, 0.467) and completes for rails above it with margin.
KNOWN SHARPNESS CAVEAT, report it, do not hide it: the cell has NO subthreshold
conduction (hard overdrive clamp + linear GM0=1e-12 leak), so below the cliff it
settles to ~0%% where silicon shows 34.8%%/77.1%% -- the transistor's partial
settling IS subthreshold current, which is a disclosed non-feature (README |7).
"""
import os, re, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
XYCE = "/usr/local/src/xyce-build/src/Xyce"
KEEP = os.path.join(HERE, "probe_runs")

# (label dV, achieved rail V from qal_hop_corrected.json L=400 rows, T0 settle %)
ANCHOR = [(0.6, 0.37251, 34.8), (0.8, 0.46688, 77.1),
          (1.0, 0.58291, 100.0), (1.2, 0.7179, 100.0)]

DECK = """* qal_gate cliff probe: INV settling on a rail that peaks at %(vr)gV
.hdl "%(here)s/qal_gate.va"
.model qm qal_gate TOPO=0 RON_N=2.5e3 RON_P=6229 VTN=0.35 VTP=0.50
+ VREF=1.2 CY=2f CIN=2f CX=0.1f CW=0.1f GM0=1e-12 ESCALE=1e15
* hop-like ramp: 0 -> VR over 400 ps (the L=400nH half-cycle), then hold
VPC pc 0 PWL(0 0 400p %(vr)g 2n %(vr)g)
VA a 0 0
VB b 0 0
YQAL_GATE X1 a b y pc 0 ed er eq 0 qm
.tran 1p 2n UIC
.measure tran YHOLD FIND V(y) AT=1.99n
.measure tran RAIL  FIND V(pc) AT=1.99n
.end
"""

def wait_xyce_free():
    for _ in range(60):
        if subprocess.run(["pgrep", "Xyce"], capture_output=True).stdout.strip() == b"":
            return
        time.sleep(5)
    sys.exit("Xyce never freed up")

def main():
    os.makedirs(KEEP, exist_ok=True)
    print("qal_gate functional cliff (INV, in=0, 400ps hop-like ramp, VTP=0.50 fitted)")
    print("%6s %10s %10s %12s %14s" % ("dV", "rail(V)", "Y@hold", "model settle", "T0 settle"))
    for dv, vr, t0 in ANCHOR:
        deck = os.path.join(KEEP, "cliff_dv%03d.cir" % int(dv * 100))
        open(deck, "w").write(DECK % {"vr": vr, "here": HERE})
        wait_xyce_free()
        subprocess.run([XYCE, deck], capture_output=True, text=True, timeout=300, cwd=KEEP)
        d = {}
        for ln in open(deck + ".mt0"):
            m = re.match(r"\s*(\w+)\s*=\s*(\S+)", ln)
            if m:
                try:
                    d[m.group(1).upper()] = float(m.group(2))
                except ValueError:
                    pass
        pct = d["YHOLD"] / d["RAIL"] * 100.0
        print("%6.1f %10.4f %10.4f %11.1f%% %13.1f%%" % (dv, d["RAIL"], d["YHOLD"], pct, t0))

if __name__ == "__main__":
    main()
