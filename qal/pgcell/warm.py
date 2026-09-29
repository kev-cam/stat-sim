#!/usr/bin/env python3
"""Pre-build the PyMS vae .so for every DISTINCT (type, W) this run needs.

MEASURED TRAP (this run): the PyMS vae cache key folds the DEVICE PARAMETERS,
and W is one of them -- `vae_PSP103VA_<hash>.so.params` carries `W=7.4e-07`,
`W=1.12e-06`, ... one .so per width per type.  So a WIDTH SWEEP does not cost one
GiNaC C++ compile, it costs one PER WIDTH (~3-5 min each on this box), and a deck
that introduces a new width stalls before its first timestep.  That is why the
committed harnesses pin a small width set and carry a `stage_warm()`.

Each width is warmed in its OWN tiny deck so the builds run in PARALLEL (distinct
cache keys -- the campaign's "one at a time" rule is about the SAME key).
"""
import os, sys
import pg

NEED_N = [0.37, 0.55, 0.64, 0.74, 1.48, 2.0, 10.0]
NEED_P = [0.56, 0.84, 1.0, 1.12, 2.24, 20.0]


def deck(typ, w):
    d = "sg13_lv_nmos" if typ == "n" else "sg13_lv_pmos"
    b = "0" if typ == "n" else "vdd"
    L = pg.head() + ["Vdd vdd 0 0.7", "Vg g 0 0.35",
                     "X1 d g 0 %s %s w=%gu l=0.13u" % (b, d, w) if typ == "n"
                     else "X1 d g vdd %s %s w=%gu l=0.13u" % (b, d, w),
                     "R1 d vdd 1k" if typ == "n" else "R1 d 0 1k",
                     ".tran 1p 10p", ".print tran V(d)", ".end"]
    return L


if __name__ == "__main__":
    typ, w = sys.argv[1], float(sys.argv[2])
    p = pg.run("warm_%s%g.cir" % (typ, w), deck(typ, w), timeout=1500)
    print("warm %s %g -> %s" % (typ, w, "ok" if p else "FAIL"))
