#!/usr/bin/env python3
"""Warm PYMS_VAE_CACHE for every (W, L) geometry this study uses.

MEASURED property of this toolchain (see the cache directory): PyMS compiles ONE
.so per (L, W) pair -- the .params file next to each .so carries `L=` and `W=`
explicitly -- and each compile costs ~2.5 min.  Warming them once up front keeps
every later deck's wall time to the solve itself.  Split into groups so the
groups can compile concurrently (compiles are serial WITHIN a process).
"""
import sys
import common as C

GEOM = {
    # group: [(type, w_um, l_um), ...]
    "a": [("n", 0.55, 0.13), ("n", 0.64, 0.13)],
    "b": [("p", 0.84, 0.13), ("p", 1.00, 0.13)],
    "c": [("n", 0.74, 0.15), ("p", 1.12, 0.15)],
}


def deck(g):
    L = C.head() + ["VA a 0 0.6", "VB b 0 0.3"]
    for k, (t, w, l) in enumerate(GEOM[g]):
        if t == "n":
            L += ["XW%d d%d a 0 0 sg13_lv_nmos w=%gu l=%gu" % (k, k, w, l),
                  "RW%d d%d b 1k" % (k, k)]
        else:
            L += ["XW%d e%d b a a sg13_lv_pmos w=%gu l=%gu" % (k, k, w, l),
                  "RW%d e%d 0 1k" % (k, k)]
    L += [".tran 1p 10p", ".print tran V(a)", ".end"]
    return L


if __name__ == "__main__":
    g = sys.argv[1]
    p, msg, w = C.run("warm_%s.cir" % g, deck(g), timeout=1800)
    print(msg, flush=True)
