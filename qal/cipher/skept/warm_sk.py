#!/usr/bin/env python3
"""Warm MY OWN PSP103 .so cache for exactly the geometries the AES vehicle
needs -- nothing more.  The parent's warm.py warmed 15 switch geometries plus
12 PDK cells (47 .so, 231 MB) because it ran five vehicles.  I re-run ONE
vehicle, so I warm ONLY what it asks for: nmos 8/16/40/80 um, pmos 80/160 um,
plus the internals of the PDK cells AddRoundKey actually instantiates.

Building them in ONE deck, alone, to completion, is the parent's own B11
finding: PyMS builds do not proceed independently across processes, so
concurrent Xyce runs demanding the same missing geometry queue and the wall
time becomes the SUM of every build.
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, "/usr/local/src/stat-sim/qal/cipher/btk")
sys.path.insert(0, "/usr/local/src/stat-sim/qal/fcrit")
import cg, run
from cg import CELLS, head_lines, widths, switch_um

ch = run.make("aes", 4.608)
need_n, need_p = set(), set()
for k in range(1, ch.nb + 1):
    w = widths(switch_um(ch, k))
    need_n |= {round(w["wn"], 6), round(w["park"], 6)}
    need_p |= {round(w["wp"], 6)}

# the cell kinds AddRoundKey instantiates, read off the chain itself
kinds = sorted(set(c.kind for lvl in ch.levels for c in lvl))
print("AES cell kinds:", kinds)
print("need nmos:", sorted(need_n), " pmos:", sorted(need_p))

L = head_lines() + ["V1 a 0 0.5", "V2 b 0 0.5"]
k = 0
for x in sorted(need_n):
    L += ["XWN%d d%d a 0 0 sg13_lv_nmos w=%gu l=0.13u" % (k, k, x),
          "RN%d d%d b 1k" % (k, k)]
    k += 1
for x in sorted(need_p):
    L += ["XWP%d e%d a b b sg13_lv_pmos w=%gu l=0.13u" % (k, k, x),
          "RP%d e%d 0 1k" % (k, k)]
    k += 1
for j, kind in enumerate(kinds):
    sub, nin = CELLS[kind][0], CELLS[kind][1]
    L.append("XC%d y%d %s b 0 %s" % (j, j, " ".join(["a"] * nin), sub))
    L.append("RC%d y%d 0 1k" % (j, j))
L += [".tran 1p 20p", ".print tran V(a)", ".end"]

p, msg, wall = cg.run("warm_sk.cir", L, timeout=7200)
print(msg, flush=True)
sys.exit(0 if p else 1)
