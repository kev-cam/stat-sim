#!/usr/bin/env python3
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# SPDX-FileCopyrightText: 2026 D. Kevin Cameron
# Part of stat-sim. PolyForm Noncommercial License 1.0.0; commercial use needs a separate license (see LICENSE, COMMERCIAL.md).
"""
ext2xyce.py -- turn a KLayout-extracted sky130 netlist into one Xyce can run.

Extract first with the PDK's LVS deck (any schematic will do, the comparison result is ignored):

    klayout -b -r $PDK/libs.tech/klayout/lvs/sky130.lvs -rd input=/abs/x.gds \\
        -rd schematic=/abs/dummy.cir -rd target_netlist=/abs/x_ext.cir -rd report=/abs/x.lvsdb \\
        -rd run_mode=deep -rd net_only=true -rd spice_net_names=true ...

Then:  ext2xyce.py x_ext.cir -o x_xyce.cir [--pin NET=NAME ...] [--report] [--rc x_rc.json]

What it does: renames `\\$123` nets to n123 (or the name given with --pin), turns MOS
lines into X instances of the PDK subcircuits, replaces poly resistors and MiM capacitors
by ideal elements using the extracted R= / C= values, and finger (VPP) capacitors, for
which the PDK has no model under the extracted name, by a fixed ideal value (--vpp).

Without --rc this is the drawn circuit.  With --rc (the output of layrc.py, which takes the
wiring R/C from mylex's layopt) every net gets its wiring capacitance to ground and every
device terminal its wiring resistance to the net node; the legs of folded fingers go in
parallel.  --rc-mode c|r|rc selects which, --rmin drops negligible resistors.
"""
import argparse
import collections
import json
import re
import sys


def clean(n, pins):
    n = n.replace("\\", "")
    if n in pins:
        return pins[n]
    return ("n" + n[1:].replace("$", "_")) if n.startswith("$") else n.replace("$", "_")


# KLayout's SPICE writer emits a device's nodes in terminal order; for MOS that is S G D B, so
# the first node of an M line (SPICE's drain) is the extraction's terminal "S".  POS names the
# node positions the SPICE way, for the inserted node names.
TERMS = {"M": ("S", "G", "D", "B"), "R": ("A", "B", "W"), "C": ("A", "B", "W")}
POS = {"M": "dgsb", "R": "ab", "C": "ab"}


class Dev:
    """One output element: nodes are rewritten in place, tail is everything after them."""

    def __init__(self, name, nodes, tail, ident, kind):
        self.name, self.nodes, self.tail = name, list(nodes), tail
        # per node position: the extracted device terminals ("$id:T") this node stands for
        self.keys = [[f"{ident}:{t}"] for t in TERMS[kind][:len(nodes)]]
        self.pos = POS[kind]

    def line(self):
        return f"{self.name} {' '.join(self.nodes)} {self.tail}"


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
    ap.add_argument("--leak", type=float, default=1e9, help="resistor to ground for nets with no DC path, ohms (0: none)")
    ap.add_argument("--rc", help="wiring parasitics from layrc.py (JSON): adds a capacitor per net and a resistor per device terminal")
    ap.add_argument("--rc-mode", choices=("rc", "c", "r"), default="rc", help="which parasitics to insert")
    ap.add_argument("--rmin", type=float, default=0.1, help="terminal wiring resistance below this is left out, ohms")
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
        ident = t[0][1:]
        kv = dict(x.split("=", 1) for x in t if "=" in x)
        pos = [x for x in t[1:] if "=" not in x]
        model = next((x for x in pos if x.startswith("sky130_fd_pr__")), None)
        nodes = [clean(x, pins) for x in pos if x != model]
        k = t[0][0].upper()
        if k == "M":
            d, g, s, b = nodes[:4]
            par = " ".join(f"{p.lower()}={v}" for p, v in kv.items())
            out.append(Dev("X" + name, nodes[:4], f"{model} {par} nf=1 mult=1", ident, k))
            kind = "nfet" if "nfet" in model else "pfet"
            for role, n in zip(("d", "g", "s", "b"), (d, g, s, b)):
                deg[n][f"{kind}.{role}"] += 1
        elif k == "R":
            out.append(Dev(name, nodes[:2], f"{float(kv['R']):.6g}", ident, k))
            for n in nodes[:2]:
                deg[n]["res"] += 1
        elif k == "C":
            # the two plates come first; a finger (VPP) capacitor has a third, substrate, terminal
            val = float(kv["C"]) if "C" in kv else a.vpp
            out.append(Dev(name, nodes[:2], f"{val:.6g}", ident, k))
            for n in nodes[:2]:
                deg[n]["cap"] += 1
        else:
            sys.exit(f"unhandled device line: {ln[:80]}")

    # Dummy resistors/capacitors are left floating in the layout, and so are banks whose other
    # side is only wired up at a higher level (decoupling capacitors).  A net that is not a pin,
    # touches no transistor, and from which every R/C leads to one and the same other net can
    # carry no current: drop those elements (repeat until stable).  To keep such a bank, name
    # its floating net with --pin (e.g. tie it to the supply it reaches at the top level).
    dropped, inert = 0, []
    while not a.keep_dangling:
        touch = collections.defaultdict(list)
        for dv in out:
            for n in set(dv.nodes):
                touch[n].append(dv)
        drop = set()
        for n, dvs in touch.items():
            if n == "0" or n in pins.values() or any(dv.name[0] == "X" for dv in dvs):
                continue
            if len({m for dv in dvs for m in dv.nodes if m != n}) <= 1:
                drop.update(id(dv) for dv in dvs)
                if len(dvs) > 1:
                    inert.append(f"{n} ({len(dvs)})")
        if not drop:
            break
        dropped += len(drop)
        out = [dv for dv in out if id(dv) not in drop]
    if dropped:
        print(f"dropped {dropped} dangling R/C elements"
              + (f"; floating nets with several elements to one net: {' '.join(inert)}" if inert else ""))
    # Layout draws wide devices as many identical fingers: fold identical parallel MOS into
    # one instance with m=N (same model bin, far fewer unknowns), and drop dummies whose
    # drain and source are the same net.
    if not a.no_merge:
        groups, rest, dummies = collections.OrderedDict(), [], 0
        for dv in out:
            if dv.name[0] != "X":
                rest.append(dv)
                continue
            d, g, s_, b = dv.nodes
            if d == s_:
                dummies += 1
                continue
            t = dv.tail.split()
            geom = tuple(x for x in t if x.split("=")[0] in ("l", "w") or "=" not in x)
            groups.setdefault((frozenset((d, s_)), g, b, geom), []).append(dv)
        merged = []
        for dvs in groups.values():
            m = dvs[0]
            for dv in dvs[1:]:
                order = (0, 1, 2, 3) if dv.nodes[0] == m.nodes[0] else (2, 1, 0, 3)   # finger drawn source/drain swapped
                for i, j in enumerate(order):
                    m.keys[i] += dv.keys[j]
            m.tail = " ".join(x for x in m.tail.split() if x.split("=")[0] != "mult") + f" mult={len(dvs)} m={len(dvs)}"
            merged.append(m)
        print(f"folded {sum(len(v) for v in groups.values())} MOS fingers into {len(merged)} devices, dropped {dummies} dummy MOS")
        out = merged + rest

    # Nodes with no DC path (series-stacked decoupling capacitors, internal gate-only nets) make
    # the DC and harmonic-balance matrices singular: give each such island a leak to ground.
    # Resistors and MOS drain/source/bulk conduct DC; capacitors and gates do not; pins are
    # assumed to be driven from outside.
    extra = []
    if a.leak > 0:
        parent = {}
        def find(n):
            parent.setdefault(n, n)
            while parent[n] != n:
                parent[n] = parent[parent[n]]
                n = parent[n]
            return n
        for dv in out:
            if dv.name[0] == "X":
                d, g, s_, b = dv.nodes
                find(g)
                parent[find(d)] = find(s_); parent[find(b)] = find(s_)
            elif dv.name[0] == "R":
                parent[find(dv.nodes[0])] = find(dv.nodes[1])
            else:
                find(dv.nodes[0]); find(dv.nodes[1])
        driven = {find(n) for n in list(parent) if n == "0" or n in pins.values()}
        islands = sorted({find(n) for n in parent} - driven)
        for n in islands:
            extra.append(f"Rleak_{n} {n} 0 {a.leak:.4g}")
        if islands:
            print(f"{len(islands)} nets have no DC path; tied to ground through {a.leak:.3g} ohm: {' '.join(islands[:8])}{' ...' if len(islands) > 8 else ''}")

    what = "drawn devices only, no parasitics"
    if a.rc:
        nets = json.load(open(a.rc))["nets"]
        leg = {key: (kn, r) for kn, v in nets.items() for key, r in v["terms"].items()}
        cnet = collections.defaultdict(set)              # output net -> layrc nets it stands for
        nr = 0
        for dv in out:
            for i, n in enumerate(dv.nodes):
                hits = [leg[k] for k in dv.keys[i] if k in leg]
                if not hits:
                    continue
                cnet[n].update(kn for kn, _ in hits)
                r = 1.0 / sum(1.0 / max(x, 1e-6) for _, x in hits)   # the fingers' legs in parallel
                if a.rc_mode != "c" and r >= a.rmin:
                    tn = f"{n}_{dv.name}_{dv.pos[i]}"
                    extra.append(f"Rw_{dv.name}_{i} {tn} {n} {r:.4g}")
                    dv.nodes[i] = tn
                    nr += 1
        mixed = sorted(n for n, kns in cnet.items() if len(kns) > 1)
        if mixed:
            print(f"WARNING: {len(mixed)} nets match more than one extracted net ({' '.join(mixed[:6])}): "
                  "the netlist and the --rc file disagree on device ids or terminal order")
        nc, ctot = 0, 0.0
        for n, kns in sorted(cnet.items()):
            c = sum(nets[kn]["c_fF"] for kn in kns)
            if a.rc_mode != "r" and n != "0" and c > 0:
                extra.append(f"Cw_{n} {n} 0 {c:.4g}f")
                nc += 1; ctot += c
        print(f"wiring parasitics: {nr} terminal resistors, {nc} net capacitors totalling {ctot:.1f} fF")
        what = f"drawn devices + layopt wiring parasitics ({a.rc_mode}) from {a.rc}"
    hdr = [f"* {top}: KLayout extraction converted by ext2xyce.py ({what})"]
    body = "\n".join(hdr + [dv.line() for dv in out] + extra) + "\n"
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
