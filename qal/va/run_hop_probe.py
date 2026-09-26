#!/usr/bin/env python3
"""Sweep qal_hop_probe.cir over series R and compare to qal_trackC.py:32 (T6).

loss/hop = 1 - (VAmin^2 + VBpk^2)/dV^2   (the estimator of qal_trackC.py:10-11)
R is Ron ALONE (total series = Ron + RL); resolved from the reference Q column,
see the deck header.
"""
import os, re, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
XYCE = "/usr/local/src/xyce-build/src/Xyce"
BASE = os.path.join(HERE, "qal_hop_probe.cir")
KEEP = os.path.join(HERE, "probe_runs")
MEAS = {15: 6.8, 30: 9.2, 60: 13.6, 90: 17.4, 150: 24.0}   # qal_trackC.py:32
DV, CB, LH, RL = 0.6, 80e-15, 25e-9, 10.0

def run(rtot):
    txt = open(BASE).read()
    txt, n = re.subn(r'(?m)^(\.param DV=.*RONSW=)[-\d.eE+]+$', r'\g<1>%g' % rtot, txt)
    if n != 1: sys.exit("could not patch RONSW")
    deck = os.path.join(KEEP, "hop_R%d.cir" % rtot)
    open(deck, "w").write(txt)
    mt0 = deck + ".mt0"
    if os.path.exists(mt0): os.remove(mt0)
    r = subprocess.run([XYCE, deck], capture_output=True, text=True, timeout=170, cwd=KEEP)
    if not os.path.exists(mt0):
        print("  R=%d FAILED:" % rtot); print("\n".join(r.stdout.strip().split("\n")[-6:])); return None
    d = {}
    for ln in open(mt0):
        m = re.match(r'\s*(\w+)\s*=\s*(\S+)', ln)
        if m:
            try: d[m.group(1).upper()] = float(m.group(2))
            except ValueError: pass
    return d if "VBPK" in d else None

def main():
    os.makedirs(KEEP, exist_ok=True)
    ceff = CB / 2.0
    print("qal_hop single inductive hop vs the MEASURED qal_trackC.py:32 table")
    print("  C_bank=%gfF  L=%gnH  RL=%g  dV=%gV;  R below is Ron alone (total = Ron+RL)\n"
          % (CB*1e15, LH*1e9, RL, DV))
    print("  %6s %7s %9s %9s %10s %10s %9s %9s"
          % ("R", "Q", "VBpk", "VAmin", "loss%", "measured%", "delta_pp", "Esw(fJ)"))
    worst = 0.0
    for r in sorted(MEAS):
        d = run(r)
        if d is None: continue
        vb, va = d["VBPK"], d["VAMIN"]
        loss = (1.0 - (va*va + vb*vb)/(DV*DV)) * 100.0
        q = (LH/ceff)**0.5 / (r + RL)
        delta = loss - MEAS[r]
        worst = max(worst, abs(delta))
        print("  %6d %7.1f %9.4f %9.4f %9.2f%% %9.1f%% %+8.2f %9.4f"
              % (r, q, vb, va, loss, MEAS[r], delta, d.get("ESWL", 0.0)))
    print("\n  worst deviation %.2f percentage points (T6 wants < 2.0 pp) -> %s"
          % (worst, "PASS" if worst < 2.0 else "FAIL"))
    return 0

if __name__ == "__main__":
    sys.exit(main())
