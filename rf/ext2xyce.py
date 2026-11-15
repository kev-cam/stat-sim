#!/usr/bin/env python3
# Part of stat-sim. PolyForm Noncommercial License 1.0.0; commercial use needs a separate license (see LICENSE, COMMERCIAL.md).
"""
ext2xyce.py -- turn a KLayout-extracted sky130 netlist into one Xyce can run.

Extract first with the PDK's LVS deck (any schematic will do, the comparison result is ignored):

    klayout -b -r $PDK/libs.tech/klayout/lvs/sky130.lvs -rd input=/abs/x.gds \\
        -rd schematic=/abs/dummy.cir -rd target_netlist=/abs/x_ext.cir -rd report=/abs/x.lvsdb \\
        -rd run_mode=deep -rd net_only=true -rd spice_net_names=true ...

Then:  ext2xyce.py x_ext.cir -o x_xyce.cir [--pin NET=NAME ...] [--report]

What it does: renames `\\$123` nets to n123 (or the name given with --pin), turns MOS
lines into X instances of the PDK subcircuits, replaces poly resistors and MiM capacitors
by ideal elements using the extracted R= / C= values, and finger (VPP) capacitors, for
which the PDK has no model under the extracted name, by a fixed ideal value (--vpp).
Parasitics are not extracted; this is the drawn circuit.
"""
import argparse
import collections
import re
import sys


def clean(n, pins):
    n = n.replace("\\", "")
    if n in pins:
        return pins[n]
    return ("n" + n[1:].replace("$", "_")) if n.startswith("$") else n.replace("$", "_")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("netlist")
    ap.add_argument("-o", "--out")
    ap.add_argument("--pin", action="append", default=[], help="NET=NAME, e.g. '$604=in' (repeatable)")
    ap.add_argument("--gnd", default="sky130_gnd", help="extracted substrate net to tie to node 0")
    ap.add_argument("--vpp", type=float, default=1e-13, help="value used for VPP finger capacitors, farads")
    ap.add_argument("--keep-dangling", action="store_true", help="keep R/C elements with an unconnected terminal")
    ap.add_argument("--no-merge", action="store_true", help="keep every finger as its own device")
    ap.add_argument("--report", action="store_true", help="print a connectivity summary to help find pins")
    a = ap.parse_args()
    pins = dict(p.split("=", 1) for p in a.pin)
    pins[a.gnd] = "0"

    text = open(a.netlist).read().replace("\n+", " ")
    out, top = [], None
    deg = collections.defaultdict(collections.Counter)
    for ln in text.splitlines():
        t = ln.split()
        if not t or t[0].startswith("*"):
            continue
        if t[0].upper() == ".SUBCKT":
            top = t[1]
            continue
        if t[0].upper() in (".ENDS", ".END"):
            continue
        name = t[0].replace("$", "_")
        kv = dict(x.split("=", 1) for x in t if "=" in x)
        pos = [x for x in t[1:] if "=" not in x]
        model = next((x for x in pos if x.startswith("sky130_fd_pr__")), None)
        nodes = [clean(x, pins) for x in pos if x != model]
        k = t[0][0].upper()
        if k == "M":
            d, g, s, b = nodes[:4]
            par = " ".join(f"{p.lower()}={v}" for p, v in kv.items())
            out.append(f"X{name} {d} {g} {s} {b} {model} {par} nf=1 mult=1")
            kind = "nfet" if "nfet" in model else "pfet"
            for role, n in zip(("d", "g", "s", "b"), (d, g, s, b)):
                deg[n][f"{kind}.{role}"] += 1
        elif k == "R":
            out.append(f"{name} {nodes[0]} {nodes[1]} {float(kv['R']):.6g}")
            for n in nodes[:2]:
                deg[n]["res"] += 1
        elif k == "C":
            val = float(kv["C"]) if "C" in kv else a.vpp
            # VPP lines are (shield/bulk, c0, c1); MiM lines are (c0, c1)
            n0, n1 = (nodes[1], nodes[2]) if "C" not in kv and len(nodes) >= 3 else (nodes[0], nodes[1])
            out.append(f"{name} {n0} {n1} {val:.6g}")
            for n in (n0, n1):
                deg[n]["cap"] += 1
        else:
            sys.exit(f"unhandled device line: {ln[:80]}")

    # Dummy resistors/capacitors are left floating in the layout; a two-terminal element
    # with a terminal nothing else touches cannot carry current, so drop it (repeat until stable).
    dropped = 0
    while not a.keep_dangling:
        use = collections.Counter()
        for ln in out:
            t = ln.split()
            for n in (t[1:5] if t[0][0] == "X" else t[1:3]):
                use[n] += 1
        keep = [ln for ln in out if ln[0] == "X" or all(use[n] > 1 or n == "0" or n in pins.values() for n in ln.split()[1:3])]
        if len(keep) == len(out):
            break
        dropped += len(out) - len(keep)
        out = keep
    if dropped:
        print(f"dropped {dropped} dangling R/C elements")
    # Layout draws wide devices as many identical fingers: fold identical parallel MOS into
    # one instance with m=N (same model bin, far fewer unknowns), and drop dummies whose
    # drain and source are the same net.
    if not a.no_merge:
        groups, rest, dummies = collections.OrderedDict(), [], 0
        for ln in out:
            t = ln.split()
            if t[0][0] != "X":
                rest.append(ln)
                continue
            if t[1] == t[3]:
                dummies += 1
                continue
            d, g, s_, b = t[1:5]
            geom = tuple(x for x in t[5:] if x.split("=")[0] in ("l", "w") or "=" not in x)
            key = (frozenset((d, s_)), g, b, geom)
            groups.setdefault(key, []).append(ln)
        merged = []
        for lns in groups.values():
            t = lns[0].split()
            keep = [x for x in t if x.split("=")[0] not in ("mult",)]
            merged.append(" ".join(keep) + f" mult={len(lns)} m={len(lns)}")
        print(f"folded {sum(len(v) for v in groups.values())} MOS fingers into {len(merged)} devices, dropped {dummies} dummy MOS")
        out = merged + rest
    hdr = [f"* {top}: KLayout extraction converted by ext2xyce.py (drawn devices only, no parasitics)"]
    body = "\n".join(hdr + out) + "\n"
    if a.out:
        open(a.out, "w").write(body)
        print(f"{len(out)} devices written to {a.out}")
    if a.report:
        print("net: device terminals   (gate-only nets are inputs/biases; nets with few terminals are likely pins)")
        for n, c in sorted(deg.items(), key=lambda kv: -sum(kv[1].values())):
            tot = sum(c.values())
            if tot >= 13:
                print(f"  {n:10s} {tot:4d}  " + " ".join(f"{k}:{v}" for k, v in sorted(c.items())))


if __name__ == "__main__":
    main()
