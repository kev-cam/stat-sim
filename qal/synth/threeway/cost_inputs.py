#!/usr/bin/env python3
"""Emit the per-cell inputs the async cost model needs from a TH-cell netlist:
cell census by type, TH-level depth, and the EXACT capacitive load on every
instance composed from the SPICE-gold liberty's per-pin capacitances.

C_L(instance) = sum of the `capacitance` of every pin it drives, taken from
  nulex/asic/chr/th_cells_sg13g2_spice.lib   (SPICE-gold: real pin caps, no
  power tables).  NEVER th_cells_sg13g2.lib -- that one realizes th22 as a plain
  AND2 (cell_footprint "AND2", function "(a*b)") and misses the C-element keeper.
A cell driving a primary output has no in-netlist load; its C_L is the external
load assumption passed on the command line (reported separately as n_extern).

Cells with no liberty entry (th34, th23w2, th24, th44) are reported as MISSING:
their driven-pin capacitance is not known and neither is their energy.

usage: cost_inputs.py <netlist.v> <top> [external_load_fF] [--json out.json]
"""
import collections
import json
import re
import subprocess
import sys

LIB = "/usr/local/src/mylex/nulex/asic/chr/th_cells_sg13g2_spice.lib"
PINS = ["a", "b", "c", "d"]
# MEASURED energy models (fJ/op over a full DATA->NULL cycle, SG13G2 PSP103,
# Vdd=1.2 V) from spice/char_energy_nominal.py -- see spice/ce_th*.mt0.
E_MEASURED = {"th22": (39.398, 1.7369), "th12": (23.004, 1.4697),
              "th13": (31.861, 1.4688)}


def pin_caps():
    txt = open(LIB).read()
    caps = {}
    for cm in re.finditer(r"cell \((\w+)\) \{(.*?)\n  \}", txt, re.S):
        cell, body = cm.group(1), cm.group(2)
        for pm in re.finditer(r"pin \((\w+)\) \{(.*?)\n    \}", body, re.S):
            p = pm.group(1)
            c = re.search(r"capacitance\s*:\s*([\d.eE+-]+)", pm.group(2))
            if c and p != "y":
                caps[(cell, p)] = float(c.group(1)) * 1000.0     # pF -> fF
    return caps


def read_netlist(v, top):
    subprocess.run(["yosys", "-q", "-p",
                    "read_verilog %s; hierarchy -top %s; flatten; write_json "
                    "/tmp/cost_inputs.json" % (v, top)], check=True)
    m = json.load(open("/tmp/cost_inputs.json"))["modules"][top]
    cells = []
    for cn, c in m["cells"].items():
        ins = [(p, c["connections"][p][0]) for p in PINS if p in c["connections"]]
        cells.append((c["type"], ins, c["connections"]["y"][0]))
    ports = {p: q["bits"] for p, q in m["ports"].items()}
    return cells, ports


def main():
    v, top = sys.argv[1], sys.argv[2]
    ext = 2.0
    jout = None
    rest = sys.argv[3:]
    if rest and not rest[0].startswith("--"):
        ext = float(rest[0]); rest = rest[1:]
    if "--json" in rest:
        jout = rest[rest.index("--json") + 1]
    caps = pin_caps()
    cells, ports = read_netlist(v, top)

    drv = {c[2]: c for c in cells}
    depth = {}

    def d(n):
        if n in depth:
            return depth[n]
        if n not in drv:
            return 0
        depth[n] = 0
        depth[n] = 1 + max([d(x) for _, x in drv[n][1]] or [0])
        return depth[n]
    worst, wport = 0, None
    for p, bits in ports.items():
        for i, b in enumerate(bits):
            if d(b) > worst:
                worst, wport = d(b), "%s[%d]" % (p, i)

    sink = collections.defaultdict(list)
    for t, ins, y in cells:
        for p, n in ins:
            sink[n].append((t, p))
    per = collections.defaultdict(list)
    missing = set()
    for t, ins, y in cells:
        cl, isext = 0.0, not sink[y]
        if isext:
            cl += ext
        for st, sp in sink[y]:
            if (st, sp) in caps:
                cl += caps[(st, sp)]
            else:
                missing.add("%s.%s" % (st, sp))
        per[t].append((cl, isext))

    out = {"netlist": v, "top": top, "external_load_fF": ext,
           "total_cells": len(cells), "th_levels": worst,
           "critical_output": wport, "cells": {}}
    print("%s: %d TH cells, depth %d TH levels (worst %s)"
          % (v, len(cells), worst, wport))
    print("%-8s %5s %10s %10s %9s %s"
          % ("cell", "n", "meanCL_fF", "sumCL_fF", "n_extern", "energy model"))
    known = 0.0
    unknown = []
    for t in sorted(per):
        L = [c for c, _ in per[t]]
        n = len(L)
        e = ""
        if t in E_MEASURED:
            E0, k = E_MEASURED[t]
            tot = sum(E0 + k * c for c in L)
            known += tot
            e = "MEASURED E=%.3f+%.4f*CL -> %.1f fJ" % (E0, k, tot)
        else:
            e = "*** NO MEASURED ENERGY ***"
            unknown.append(t)
        print("%-8s %5d %10.3f %10.3f %9d %s"
              % (t, n, sum(L) / n, sum(L), sum(1 for _, x in per[t] if x), e))
        out["cells"][t] = {"n": n, "mean_CL_fF": round(sum(L) / n, 4),
                           "sum_CL_fF": round(sum(L), 4),
                           "n_driving_primary_output": sum(1 for _, x in per[t] if x),
                           "loads_fF": [round(c, 4) for c in L],
                           "energy_measured": t in E_MEASURED}
    print("energy from MEASURED cells only: %.1f fJ/op  (cells still unmeasured: %s)"
          % (known, ", ".join(unknown) or "none"))
    if missing:
        print("NO LIBERTY PIN CAP (load underestimated for their drivers): %s"
              % ", ".join(sorted(missing)))
    out["energy_from_measured_cells_fJ"] = round(known, 3)
    out["cells_without_measured_energy"] = unknown
    out["pins_without_liberty_cap"] = sorted(missing)
    if jout:
        json.dump(out, open(jout, "w"), indent=1)
        print("wrote %s" % jout)


if __name__ == "__main__":
    main()
