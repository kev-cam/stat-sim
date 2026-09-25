#!/usr/bin/env python3
"""Nominal per-cell ENERGY characterization for the full-swing arms (async TH cells,
CMOS stdcells) -- deterministic, no MC.

WHY NOMINAL ONLY (user's point, verified): accumulated power over many cells tends to
the mean. Measured per-cell energy spread from the MC deck is sigma/mu = 0.56% (set) /
1.61% (reset), and a sum of N cells shrinks that as 1/sqrt(N) -> 0.055% at 105 cells,
0.006% at 9267. So block power needs the MEAN only; MC is reserved for DELAY, where the
composition is a max-over-paths and the tail IS the answer.

MODEL: E_cell(C_load) = E0 + k*C_load  (E0 = internal/self switching + crowbar + keeper,
k ~ V^2 for the driven load). Two+ loads give E0 and k by least squares; the netlist's
actual per-instance fanout then composes the block energy.

STIMULUS is in-context correct:
  th22 = Muller C-element -> BOTH inputs must go DATA to fire.
  th12/th13 = dual-rail minterm COLLECTORS (OR) -> the minterms are mutually exclusive,
  so exactly ONE input fires per op; the others stay at 0. Driving all inputs high would
  overstate their energy.
One op = a full DATA -> NULL cycle (return-to-zero), matching the async protocol.
"""
import os, re, subprocess, sys, json

XYCE  = "/usr/local/src/xyce-build/src/Xyce"
VA    = "/usr/local/share/xyce/verilog-a/psp103/psp103.va"
MODEL = "/usr/local/src/kestrel/sim/models/sg13g2_psp103_tt.lib"
INC   = ["/usr/local/src/ldx/asic/cells/th22.sp",
         "/usr/local/src/ldx/asic/cells/th_gates.sp",
         "/usr/local/src/mylex/nulex/lib/th_cells_sg13g2.sp"]
VDD   = 1.2
LOADS = [1.0, 3.0, 10.0]          # fF
OUT   = "cell_energy_nominal.json"

# cell -> (ports before Y, n_fire)  n_fire = how many inputs switch per op
CELLS = {
    "th22": (["A", "B"], 2),      # C-element: both fire
    "th12": (["A", "B"], 1),      # collector: one minterm fires
    "th13": (["A", "B", "C"], 1), # collector: one minterm fires
}

def deck(cell, ins, nfire, cl_ff):
    L = ['* nominal energy: %s, CL=%gfF' % (cell, cl_ff),
         '.hdl "%s"' % VA, '.include "%s"' % MODEL]
    L += ['.include "%s"' % i for i in INC]
    L += ["VDD vdd 0 %g" % VDD, "VSS vss 0 0"]
    # DATA at 2n (0.1n edge), NULL at 6n; measure the full cycle 1.9n..10n
    for k, p in enumerate(ins):
        if k < nfire:
            L.append("V%s %s 0 PWL(0 0 1.9n 0 2n %g 5.9n %g 6n 0 12n 0)" % (p, p.lower(), VDD, VDD))
        else:
            L.append("V%s %s 0 0" % (p, p.lower()))
    nodes = " ".join(p.lower() for p in ins)
    L += ["X1 %s y vdd vss %s" % (nodes, cell),
          "CL y 0 %gf" % cl_ff,
          ".tran 2p 12n",
          ".print tran V(y)",
          ".measure tran QOP INTEG I(VDD) from=1.9n to=10n",
          ".measure tran EOP PARAM {%g*QOP}" % (-VDD),
          ".measure tran YMAX MAX V(y) from=1.9n to=10n",
          ".measure tran TD TRIG V(%s) VAL=%g RISE=1 TARG V(y) VAL=%g RISE=1"
              % (ins[0].lower(), VDD/2, VDD/2),
          ".end"]
    return "\n".join(L) + "\n"

def run(cell, ins, nfire, cl):
    fn = "ce_%s_%g.cir" % (cell, cl)
    open(fn, "w").write(deck(cell, ins, nfire, cl))
    env = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS")
    try:
        o = subprocess.run([XYCE, fn], capture_output=True, text=True,
                           timeout=300, env=env).stdout
    except subprocess.TimeoutExpired:
        return None
    g = {}
    for k in ("EOP", "YMAX", "TD"):
        m = re.search(r"^%s\s*=\s*(\S+)" % k, o, re.M)
        if m:
            try: g[k] = float(m.group(1))
            except ValueError: pass
    return g if "EOP" in g else None

def fit(xs, ys):
    n = len(xs)
    if n < 2: return ys[0] if ys else 0.0, 0.0
    mx = sum(xs)/n; my = sum(ys)/n
    den = sum((x-mx)**2 for x in xs)
    k = sum((x-mx)*(y-my) for x, y in zip(xs, ys))/den if den else 0.0
    return my - k*mx, k

def main():
    res = {}
    for cell, (ins, nfire) in CELLS.items():
        pts = []
        for cl in LOADS:
            g = run(cell, ins, nfire, cl)
            if g is None:
                print("  %-6s CL=%-5g FAILED" % (cell, cl)); continue
            e_fJ = g["EOP"] * 1e15
            pts.append((cl, e_fJ))
            print("  %-6s CL=%5gfF  E=%8.3f fJ/op  Ymax=%.3f  td=%.0f ps"
                  % (cell, cl, e_fJ, g.get("YMAX", 0), g.get("TD", 0)*1e12))
        if not pts: continue
        E0, k = fit([p[0] for p in pts], [p[1] for p in pts])
        res[cell] = {"E0_fJ": round(E0, 4), "k_fJ_per_fF": round(k, 4),
                     "n_fire": nfire, "points": [[p[0], round(p[1], 4)] for p in pts]}
        print("  %-6s -> E(CL) = %.3f + %.3f*CL[fF]  fJ/op" % (cell, E0, k))
    json.dump({"_doc": "nominal per-cell energy, SG13G2 PSP103, DATA->NULL cycle, "
                       "Vdd=1.2V. E(CL)=E0+k*CL. Nominal only: block power tends to the "
                       "mean (per-cell sigma/mu 0.56-1.6%, /sqrt(N)).",
               "vdd": VDD, "cells": res}, open(OUT, "w"), indent=1)
    print("wrote %s" % OUT)

if __name__ == "__main__":
    main()
