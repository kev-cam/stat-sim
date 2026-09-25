#!/usr/bin/env python3
"""Levelize an SG13G2-mapped structural Verilog netlist (yosys write_verilog -noattr).
Same boundary convention as levelize_alu.py: primary inputs and DFF Q are level-0
sources, DFF D/CLK/RESET_B are sinks.  Output pins of sg13g2 combinational cells are
X (non-inverting) or Y (inverting); sg13g2_dfrbpq_1 drives Q.

usage: levelize_mapped.py <netlist.v> <top>
"""
import collections
import re
import sys

OUTPINS = ("X", "Y")
SEQ_PREFIX = ("sg13g2_dfrbpq", "sg13g2_dfrbp", "sg13g2_sdfbbp", "sg13g2_dlhq")

src = open(sys.argv[1]).read()
top = sys.argv[2]
body = src[src.index("module %s(" % top):]
body = body[:body.index("endmodule")]

# port declarations
pin_ports = set()
for m in re.finditer(r"^\s*input\s+(?:\[(\d+):(\d+)\]\s+)?(\\?[\w$.:\[\]]+)\s*;", body, re.M):
    hi, lo, nm = m.groups()
    if hi is None:
        pin_ports.add(nm)
    else:
        for i in range(int(lo), int(hi) + 1):
            pin_ports.add("%s[%d]" % (nm, i))

cells = {}
for m in re.finditer(r"^\s*(sg13g2_\w+)\s+(\\?\S+)\s*\((.*?)\);", body, re.M | re.S):
    ctype, cname, conns = m.groups()
    pins = dict(re.findall(r"\.(\w+)\(([^)]*)\)", conns))
    pins = {k: v.strip() for k, v in pins.items()}
    cells[cname] = (ctype, pins)

drv, seq, comb = {}, {}, {}
for cn, (ct, pins) in cells.items():
    is_seq = any(ct.startswith(p) for p in SEQ_PREFIX)
    if is_seq:
        seq[cn] = (ct, pins)
    else:
        comb[cn] = (ct, pins)
        for p in OUTPINS:
            if p in pins:
                drv[pins[p]] = cn

srcnets = set(pin_ports)
for cn, (ct, pins) in seq.items():
    if "Q" in pins:
        srcnets.add(pins["Q"])

lvl = {}
order = list(comb)
for start in order:
    stack = [start]
    while stack:
        k = stack[-1]
        if lvl.get(k, 0) > 0:
            stack.pop(); continue
        ct, pins = comb[k]
        ins = [v for p, v in pins.items() if p not in OUTPINS]
        pend = []
        for n in ins:
            if n in srcnets or n in ("1'h0", "1'h1", "1'b0", "1'b1", ""):
                continue
            d = drv.get(n)
            if d is not None and lvl.get(d, 0) == 0:
                pend.append(d)
        if pend:
            stack.extend(pend); continue
        L = 1
        for n in ins:
            if n in srcnets or n not in drv:
                continue
            L = max(L, lvl.get(drv[n], 0) + 1)
        lvl[k] = L
        stack.pop()

D = max(lvl.values())
prof = [sum(1 for v in lvl.values() if v == i) for i in range(1, D + 1)]
print("%s  comb %d  seq %d  DEPTH %d" % (sys.argv[1], len(comb), len(seq), D))
print("profile: %s" % "/".join(map(str, prof)))
print("sum %d" % sum(prof))
mix = collections.Counter(ct for ct, _ in comb.values())
print("top cell types: %s" % mix.most_common(12))
