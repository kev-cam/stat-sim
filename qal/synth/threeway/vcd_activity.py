#!/usr/bin/env python3
"""Re-compose the async arm on the EXACT input vectors the CMOS arm was measured
on (work/cmos.vcd), instead of an independent uniform-random draw.

The CMOS 232 fJ/op used real-VCD activity (alpha=0.476) from that file; the async
alphas were taken on a separate uniform draw.  This closes that gap so both arms
are driven by the same stimulus.  (Note the async arm is return-to-zero: every op
is NULL->DATA->NULL, so its activity depends only on the DATA VALUE, never on the
previous vector -- unlike CMOS, whose alpha is a transition count.)
"""
import re
import sys

sys.path.insert(0, "/usr/local/src/stat-sim/qal/synth/threeway")
import compose_async as A

VCD = "/usr/local/src/stat-sim/qal/synth/threeway/work/cmos.vcd"


def vectors():
    txt = open(VCD).read()
    head, _, body = txt.partition("$enddefinitions $end")
    sym = {}
    for m in re.finditer(r"\$var wire 8 (\S+) (\w+) \[7:0\] \$end", head):
        sym[m.group(1)] = m.group(2)
    want = {s: p for s, p in sym.items() if p in ("a", "b", "c", "e", "f", "g")}
    cur, out = {}, []
    for line in body.splitlines():
        line = line.strip()
        if line.startswith("#"):
            if len(cur) == 6:
                out.append(dict(cur))
            continue
        m = re.match(r"^b([01xzXZ]+)\s+(\S+)$", line)
        if m and m.group(2) in want:
            v = m.group(1)
            if set(v) <= set("01"):
                cur[want[m.group(2)]] = int(v, 2)
    if len(cur) == 6:
        out.append(dict(cur))
    # dedup consecutive identical vectors, drop the all-zero reset vector
    ded = []
    for v in out:
        if (not ded or v != ded[-1]) and any(v.values()):
            ded.append(v)
    return ded


def run(vfile, vecs, top="sha_slice"):
    import collections
    cells, ports = A.V.load(vfile, top)
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
    net = A.V.Net(cells, ports)
    tot = [0.0, 0.0, 0.0]
    nfire = 0
    for vv in vecs:
        val = net.drive(vv)
        for t, ins, y in net.cells:
            n, lo, hi, _ = A.energy(A.arc(t, [val[i] for i in ins]), CL[y])
            tot[0] += n; tot[1] += lo; tot[2] += hi
            nfire += val[y]
    nv = len(vecs)
    print("  %-46s %3d cells  alpha=%.4f  E=%8.1f fJ/op  [%.1f, %.1f]"
          % (vfile.split("/")[-1], len(cells), nfire / nv / len(cells),
             tot[0] / nv, tot[1] / nv, tot[2] / nv))
    return tot[0] / nv


if __name__ == "__main__":
    vecs = vectors()
    print("VCD stimulus: %d distinct DATA vectors from %s" % (len(vecs), VCD))
    print("  mean popcount of a = %.3f of 8 bits (uniform would be 4.000)"
          % (sum(bin(v["a"]).count("1") for v in vecs) / len(vecs)))
    W = "/usr/local/src/stat-sim/qal/synth/threeway/work/"
    for f in ("sha_slice_th_clean.v", "sha_slice_direct_spice.v", "sha_slice_direct_cd.v"):
        run(W + f, vecs)
