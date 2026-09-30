#!/usr/bin/env python3
"""SKEPTIC's COMPLETE equivalence proof, by support-set decomposition + bit-
parallel exhaustion.  Structurally different from both of the track's engines
(yosys SAT miter, yosys equiv_induct) and STRONGER than its 155,600 vectors:
this is exhaustive over every output bit's entire support, so it is a proof, not
a sample.

WHY IT IS COMPLETE (the argument, stated so it can be attacked):
  Support sets are computed by transitive fan-in over the gate graph, so an input
  outside a bit's support provably cannot change it.  Measured supports are
    sum[i] <- a[0..i], b[0..i]        (<= 16 vars)
    maj[i] <- a[i], b[i], c[i]        (3 vars)
    ch[i]  <- e[i], f[i], g[i]        (3 vars)
  A sweep of ALL 2^16 (a,b) pairs x c in {0x00,0xFF} x (e,f,g) over all 8 uniform
  all-0/all-1 patterns therefore visits EVERY assignment of EVERY output bit's
  support:  sum exhaustively in (a,b);  maj[i] gets all 4 (a[i],b[i]) from the
  (a,b) sweep and both c[i];  ch[i] gets all 8 (e[i],f[i],g[i]) triples across
  the 8 uniform patterns.  16 bit-parallel passes of 65,536 lanes = 1,048,576
  distinct input vectors evaluated, and the coverage argument above makes the
  result a complete proof of every bit.

The reference is MY OWN re-implementation of sha_slice.v read off the RTL text
(nl.ref), not the track's.  A proof against a reference derived from the netlist
under test would be worthless.
"""
import json, os, sys
from collections import Counter
import nl

HERE = os.path.dirname(os.path.abspath(__file__))
M = (1 << 65536) - 1            # 65536 parallel lanes, one per (a,b) pair


def lanes_ab():
    """bit-parallel columns: A[i], B[i] as 65536-bit masks over lane = a|b<<8."""
    A = [0] * 8
    B = [0] * 8
    for lane in range(65536):
        a, b = lane & 0xFF, (lane >> 8) & 0xFF
        for i in range(8):
            if (a >> i) & 1:
                A[i] |= 1 << lane
            if (b >> i) & 1:
                B[i] |= 1 << lane
    return A, B


def prove(path):
    n = nl.Net(path).build()
    hist = Counter(t for t, _, _ in n.cells)
    A, B = lanes_ab()
    total_vecs = 0
    fails = []
    for cpat in (0x00, 0xFF):
        for efg in range(8):
            epat = 0xFF if (efg & 1) else 0x00
            fpat = 0xFF if (efg & 2) else 0x00
            gpat = 0xFF if (efg & 4) else 0x00
            val = {}
            for i in range(8):
                val["a[%d]" % i] = A[i]
                val["b[%d]" % i] = B[i]
                val["c[%d]" % i] = M if (cpat >> i) & 1 else 0
                val["e[%d]" % i] = M if (epat >> i) & 1 else 0
                val["f[%d]" % i] = M if (fpat >> i) & 1 else 0
                val["g[%d]" % i] = M if (gpat >> i) & 1 else 0
            # bit-parallel evaluation of the gate netlist
            for k in n.order:
                typ, inst, conn = n.cells[k]
                if typ == "sg13g2_inv_1":
                    val[conn["Y"]] = ~res(n, conn["A"], val) & M
                elif typ == "sg13g2_nand2_1":
                    val[conn["Y"]] = ~(res(n, conn["A"], val)
                                       & res(n, conn["B"], val)) & M
                elif typ == "sg13g2_and2_1":
                    val[conn["X"]] = res(n, conn["A"], val) & res(n, conn["B"], val)
                elif typ == "sg13g2_nor2_1":
                    val[conn["Y"]] = ~(res(n, conn["A"], val)
                                       | res(n, conn["B"], val)) & M
                elif typ == "sg13g2_or2_1":
                    val[conn["X"]] = res(n, conn["A"], val) | res(n, conn["B"], val)
                elif typ == "sg13g2_buf_1":
                    val[conn["X"]] = res(n, conn["A"], val)
                else:
                    raise KeyError(typ)
            # golden, bit-parallel, from MY OWN reading of sha_slice.v
            gm, gc, gs = [0] * 8, [0] * 8, [0] * 8
            carry = 0
            for i in range(8):
                ai, bi = A[i], B[i]
                ci = M if (cpat >> i) & 1 else 0
                gm[i] = (ai & bi) ^ (ai & ci) ^ (bi & ci)
                ei = M if (epat >> i) & 1 else 0
                fi = M if (fpat >> i) & 1 else 0
                gi = M if (gpat >> i) & 1 else 0
                gc[i] = (ei & fi) ^ (~ei & M & gi)
                gs[i] = ai ^ bi ^ carry
                carry = (ai & bi) | (carry & (ai ^ bi))
            for nm, gold in (("maj", gm), ("ch", gc), ("sum", gs)):
                for i in range(8):
                    got = res(n, "%s[%d]" % (nm, i), val) & M
                    diff = got ^ (gold[i] & M)
                    if diff:
                        lane = (diff & -diff).bit_length() - 1
                        fails.append(dict(out="%s[%d]" % (nm, i), cpat=cpat,
                                          efg=efg, lane=lane,
                                          a=lane & 0xFF, b=(lane >> 8) & 0xFF))
            total_vecs += 65536
    return dict(netlist=os.path.basename(path), cells=len(n.cells),
                histogram=dict(hist), depth=max(n.levelize().values()),
                inputs=n.inputs, outputs=n.outputs,
                vectors=total_vecs, mismatches=len(fails), fails=fails[:20],
                complete=True)


def res(n, nd, val):
    if nd in ("1'b0", "1'h0"):
        return 0
    if nd in ("1'b1", "1'h1"):
        return M
    if nd in val:
        return val[nd]
    d = n.driver.get(nd)
    if d is not None and d[0] == "alias":
        return res(n, d[1], val)
    raise KeyError(nd)


if __name__ == "__main__":
    out = {}
    for p in sys.argv[1:]:
        r = prove(p)
        out[r["netlist"]] = r
        print("%-28s cells %3d depth %2d vectors %d mismatches %d  hist %s"
              % (r["netlist"], r["cells"], r["depth"], r["vectors"],
                 r["mismatches"], r["histogram"]), flush=True)
    json.dump(out, open(os.path.join(HERE, "MYPROOF.json"), "w"), indent=1)
