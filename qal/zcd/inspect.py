#!/usr/bin/env python3
"""Text-dump key node trajectories from a zcd prn at coarse time grid."""
import sys
sys.path.insert(0, "/usr/local/src/stat-sim/qal/zcd")
from qal_zcd import read_prn, col

prn = sys.argv[1]
hdr, rows = read_prn(prn)
names = [h for h in hdr if h not in ("INDEX",)]
pick = [n for n in ["TIME", "V(SIGP)", "V(ZINN)", "V(MID)", "V(SW)", "I(LT)",
                    "V(ZX1)", "V(ZX2)", "V(ZY)", "V(ZOUT)", "V(ZTAIL)",
                    "I(VZC)", "V(XQZC)", "V(XEZC)", "V(XEARM)", "V(BKB)"]
        if any(n in h for h in hdr)]
idx = {n: col(hdr, n) for n in pick}
print(" ".join("%12s" % n for n in pick))
step = float(sys.argv[2]) if len(sys.argv) > 2 else 20.0
tnext = 0.0
for r in rows:
    t = r[idx["TIME"]] * 1e12
    if t + 1e-9 >= tnext:
        print(" ".join("%12.5g" % (r[idx[n]] * (1e12 if n == "TIME" else 1))
                       for n in pick))
        tnext += step
