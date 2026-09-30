#!/usr/bin/env python3
"""Warm the PSP103 .so cache for EVERY geometry Phase 2 needs, in ONE deck.

PyMS builds one .so per (model, geometry) by GiNaC codegen plus a g++ compile,
about three minutes each.  Six Xyce processes each demanding the same missing
geometries race, duplicate the work and block: measured, six probe decks sat 15
minutes without emitting a result while 33 .so were built.  Building them all
once, up front, from a single trivial deck removes that entirely.
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cg, run
from cg import CELLS, PDK_SPICE, head_lines, widths, switch_um

need_n, need_p = set(), set()
# every switch geometry Phase 2 will ask for
for nm, cw in (("aes", 4.608), ("aes", 0.0), ("qrxor", 7.767), ("qrxor", 0.0),
               ("ks8", -1.0), ("rip8", -1.0), ("ks32", -1.0)):
    ch = run.make(nm, cw)
    for k in range(1, ch.nb + 1):
        w = widths(switch_um(ch, k))
        need_n |= {round(w["wn"], 6), round(w["park"], 6)}
        need_p |= {round(w["wp"], 6)}

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
# every PDK CELL Phase 2 instantiates, so their internal geometries build too
for j, kind in enumerate(sorted(CELLS)):
    sub, nin = CELLS[kind][0], CELLS[kind][1]
    L.append("XC%d y%d %s b 0 %s" % (j, j, " ".join(["a"] * nin), sub))
    L.append("RC%d y%d 0 1k" % (j, j))
L += [".tran 1p 20p", ".print tran V(a)", ".end"]
print("warming %d nmos + %d pmos switch geometries and %d PDK cells"
      % (len(need_n), len(need_p), len(CELLS)))
print("  nmos:", sorted(need_n))
print("  pmos:", sorted(need_p))
p, msg, wall = cg.run("warm_p2.cir", L, timeout=7200)
print(msg)
sys.exit(0 if p else 1)
