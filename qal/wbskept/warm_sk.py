#!/usr/bin/env python3
"""SKEPTIC warm: compile ONLY the (width, TYPE) pairs this audit instantiates.

Phase 2 amendment A2 found the inherited warm compiles both types at every
width and so spends half its bill on pairs never instantiated.  This warm
enumerates the pairs directly from up.py's own geometry functions, so the set
is DERIVED from the instrument under audit rather than retyped.

Emitted sequentially in ONE deck: PyMS serialises on build_vae_so anyway, and a
single deck cannot race itself.
"""
import math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import up

# rows this audit runs: (N, scale)
CHAIN = [(32, 1.0), (64, 1.0), (256, 1.0), (64, 2.0)]
CRUX_SCALES = [1.0, 2.0, 4.0, 8.0]

nm, pm = set(), set()
for s in CRUX_SCALES:                 # crux cell chain, both rails
    pm.add(round(up.WP * s, 6)); nm.add(round(up.WN * s, 6))
for (n, s) in CHAIN:                  # 3-bank rows: cells + switch triple
    pm.add(round(up.WP * s, 6)); nm.add(round(up.WN * s, 6))
    w = up.widths(up.wtot(n, 1.0, s))
    nm.add(round(w["wn"], 6))         # TG nMOS
    pm.add(round(w["wp"], 6))         # TG pMOS
    nm.add(round(w["park"], 6))       # park nMOS

nm, pm = sorted(nm), sorted(pm)
print("nmos %d: %s" % (len(nm), nm), flush=True)
print("pmos %d: %s" % (len(pm), pm), flush=True)
print("total compiles = %d" % (len(nm) + len(pm)), flush=True)

L = up.head_lines() + ["V1 a 0 0.5", "V2 b 0 0.5"]
for i, x in enumerate(nm):
    L.append("XWN%d dn%d a 0 0 sg13_lv_nmos w=%gu l=0.13u" % (i, i, x))
    L.append("RN%d dn%d b 1k" % (i, i))
for i, x in enumerate(pm):
    L.append("XWP%d dp%d a b b sg13_lv_pmos w=%gu l=0.13u" % (i, i, x))
    L.append("RP%d dp%d 0 1k" % (i, i))
L += [".tran 1p 10p", ".print tran V(a)", ".end"]

p, msg = up.run("warm_sk.cir", L, timeout=7200)
print(msg, flush=True)
sys.exit(0 if p else 1)
