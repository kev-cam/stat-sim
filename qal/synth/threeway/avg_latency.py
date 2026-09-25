#!/usr/bin/env python3
"""Data-dependent (average-case) completion time for a QDI TH netlist.

Worst-case static timing charges every op the longest structural path.  A QDI
block does not work that way: a cell asserts when its THRESHOLD IS MET, which
for this data may be the 2nd of 3 asserted inputs, and a cell that does not fire
this op is not on the timing path at all.  `done` rises when the completion tree
sees every output rail -- so the honest throughput number for the async arm is
the DISTRIBUTION of done-times, not just its maximum.

Per vector: rise[net] = the time the net's THRESHOLD is met, computed from the
weights in verify_direct.WT over the arrival times of the ASSERTED inputs only.
Arc delays are the MEASURED ones (compose_async.D), at the per-instance C_L.
"""
import sys

sys.path.insert(0, "/usr/local/src/stat-sim/qal/synth/threeway")
import collections
import random

import compose_async as A
import verify_direct as V


def analyse(vfile, top="sha_slice", nv=2000, seed=99):
    cells, ports = V.load(vfile, top)
    caps = A.C.pin_caps()
    sink = collections.defaultdict(list)
    for t, ins, y in cells:
        for p, n in zip(A.PINS, ins):
            sink[n].append((t, p))
    CL = {}
    for t, ins, y in cells:
        cl = A.EXT if not sink[y] else 0.0
        for st, sp in sink[y]:
            cl += caps.get((st, sp), 0.0)
        CL[y] = cl
    net = V.Net(cells, ports)
    rnd = random.Random(seed)
    out = []
    for _ in range(nv):
        val = net.drive({k: rnd.randrange(256) for k in "abcefg"})
        rise = {}
        for b in net.inbits:
            rise[b] = 0.0
        rise["0"] = float("inf"); rise["1"] = 0.0
        for t, ins, y in net.cells:
            if not val[y]:
                rise[y] = float("inf")      # never asserts this op
                continue
            w, T = V.WT[t]
            # time at which the weighted sum of ASSERTED inputs first reaches T
            ev = sorted((rise[i], w[j]) for j, i in enumerate(ins) if val[i])
            acc, tmet, prev = 0, 0.0, 0.0
            for tm, wi in ev:
                acc += wi
                if acc >= T:
                    tmet, prev = tm, (ev[ev.index((tm, wi)) - 1][0]
                                      if ev.index((tm, wi)) > 0 else tm)
                    break
            key = "th23s" if (t == "th23" and tmet - prev < 50.0) else t
            t0, s = A.D[key]
            rise[y] = tmet + t0 + s * CL[y]
        # completion = last output rail / done
        if "done" in ports:
            done = max(rise[b] for b in ports["done"])
        else:
            done = max(rise[b] for p, bits in ports.items()
                       for b in bits if b not in net.inbits and val.get(b))
        out.append(done)
    out.sort()
    return out


def stats(name, o):
    n = len(o)
    print("  %-34s mean %6.3f  p50 %6.3f  p95 %6.3f  p99 %6.3f  max %6.3f ns"
          % (name, sum(o) / n / 1000, o[n // 2] / 1000, o[int(.95 * n)] / 1000,
             o[int(.99 * n)] / 1000, o[-1] / 1000))
    return sum(o) / n / 1000, o[-1] / 1000


if __name__ == "__main__":
    W = "/usr/local/src/stat-sim/qal/synth/threeway/work/"
    print("DATA-DEPENDENT completion time (2000 random DATA vectors)")
    for f in ("sha_slice_direct_cd.v", "sha_slice_direct_spice.v", "sha_slice_th_clean.v"):
        stats(f, analyse(W + f))
