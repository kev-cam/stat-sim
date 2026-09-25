#!/usr/bin/env python3
"""Topological levelization of a yosys gate-level JSON netlist, the same way
work/levels.json was produced for sha_slice (cost_inputs.py's recursive depth),
but with SEQUENTIAL boundaries handled explicitly:

  * primary inputs and $_DFF_P_ Q outputs are LEVEL-0 SOURCES (a QAL wave starts
    at a register output, exactly as a CMOS cycle does);
  * $_DFF_P_ D and CLK pins are SINKS -- the path terminates there;
  * every combinational cell sits at 1 + max(level of the nets it reads);
  * constant nets ("0"/"1"/"x"/"z") and undriven nets are level 0.

Reports depth, per-level cell counts, per-level type mix, register fan-in
levels, and the per-output-bit arrival level.

usage: levelize_alu.py <netlist.json> <top> [--json out.json]
"""
import collections
import json
import sys

SEQ = {"$_DFF_P_", "$_DFF_N_", "$_DFFE_PP_", "$_SDFF_PP0_", "$_SDFF_PP1_"}
SKIP = {"$scopeinfo"}
# pins of a sequential cell that are read (path terminates), and driven (source)
SEQ_IN = ("D", "C", "E", "R", "S")
SEQ_OUT = ("Q",)


def main():
    path, top = sys.argv[1], sys.argv[2]
    jout = None
    if "--json" in sys.argv:
        jout = sys.argv[sys.argv.index("--json") + 1]

    m = json.load(open(path))["modules"][top]
    cells = m["cells"]
    ports = m["ports"]

    comb = {}      # name -> (type, [in_nets], [out_nets])
    seq = {}
    for cn, c in cells.items():
        t = c["type"]
        if t in SKIP:
            continue
        conns = c["connections"]
        if t in SEQ:
            ins = [b for p in SEQ_IN if p in conns for b in conns[p]]
            outs = [b for p in SEQ_OUT if p in conns for b in conns[p]]
            seq[cn] = (t, ins, outs)
        else:
            ins, outs = [], []
            for p, bits in conns.items():
                # yosys internal gate convention: Y is the only output
                (outs if p == "Y" else ins).extend(bits)
            comb[cn] = (t, ins, outs)

    # net -> driving combinational cell
    drv = {}
    for cn, (t, ins, outs) in comb.items():
        for n in outs:
            drv[n] = cn
    # level-0 sources: primary inputs, DFF Q, constants, undriven
    src = set()
    for p, q in ports.items():
        if q["direction"] in ("input", "inout"):
            src.update(q["bits"])
    for cn, (t, ins, outs) in seq.items():
        src.update(outs)

    lvl_net = {}
    lvl_cell = {}
    sys.setrecursionlimit(100000)

    def net_level(n):
        if isinstance(n, str):          # "0" "1" "x" "z"
            return 0
        if n in src:
            return 0
        if n in lvl_net:
            return lvl_net[n]
        if n not in drv:                # undriven / dangling
            lvl_net[n] = 0
            return 0
        lvl_net[n] = 0                  # cycle guard (should not trigger: acyclic comb)
        L = cell_level(drv[n])
        lvl_net[n] = L
        return L

    def cell_level(cn):
        if cn in lvl_cell:
            return lvl_cell[cn]
        lvl_cell[cn] = 0
        t, ins, outs = comb[cn]
        L = 1 + max([net_level(x) for x in ins] or [0])
        lvl_cell[cn] = L
        return L

    # iterative driver to avoid deep Python recursion blowing the stack
    order = list(comb)
    for cn in order:
        stack = [cn]
        while stack:
            k = stack[-1]
            if k in lvl_cell and lvl_cell[k] > 0:
                stack.pop()
                continue
            t, ins, outs = comb[k]
            pend = []
            for n in ins:
                if isinstance(n, str) or n in src or n in lvl_net:
                    continue
                if n in drv:
                    d = drv[n]
                    if d not in lvl_cell or lvl_cell[d] == 0:
                        pend.append(d)
                else:
                    lvl_net[n] = 0
            if pend:
                stack.extend(pend)
                continue
            L = 1 + max([net_level(x) for x in ins] or [0])
            lvl_cell[k] = L
            for n in outs:
                lvl_net[n] = L
            stack.pop()

    bylvl = collections.defaultdict(list)
    for cn, L in lvl_cell.items():
        bylvl[L].append(cn)
    D = max(bylvl)
    prof = [len(bylvl[i]) for i in range(1, D + 1)]
    typemix = {i: dict(collections.Counter(comb[c][0] for c in bylvl[i]))
               for i in range(1, D + 1)}

    # where the registers sit: level of the deepest comb cell feeding each DFF's D
    ff_arr = []
    for cn, (t, ins, outs) in seq.items():
        d = ins[0] if ins else None
        ff_arr.append(net_level(d) if d is not None else 0)
    # primary-output arrival levels
    po = {}
    for p, q in ports.items():
        if q["direction"] == "output":
            po[p] = [net_level(b) for b in q["bits"]]

    out = {"netlist": path, "top": top, "depth": D,
           "n_comb": len(comb), "n_seq": len(seq),
           "profile": prof, "typemix": typemix,
           "ff_input_levels": dict(collections.Counter(ff_arr)),
           "po_levels": po}
    print("%s  top=%s" % (path, top))
    print("comb cells %d, seq cells %d, depth %d levels" % (len(comb), len(seq), D))
    print("profile: %s" % "/".join(str(x) for x in prof))
    print("sum(profile)=%d" % sum(prof))
    print("\n%4s %6s  %s" % ("lvl", "n", "type mix"))
    for i in range(1, D + 1):
        mix = ", ".join("%s %d" % (k.strip("$_"), v)
                        for k, v in sorted(typemix[i].items(), key=lambda kv: -kv[1]))
        print("%4d %6d  %s" % (i, prof[i - 1], mix))
    print("\nDFF D-pin arrival levels (histogram): %s"
          % sorted(out["ff_input_levels"].items()))
    print("primary-output arrival levels:")
    for p, L in po.items():
        print("  %-14s n=%3d  min %2d  max %2d" % (p, len(L), min(L), max(L)))
    if jout:
        json.dump(out, open(jout, "w"), indent=1)
        print("wrote %s" % jout)


if __name__ == "__main__":
    main()
