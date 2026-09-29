#!/usr/bin/env python3
"""ROUTE B / ROUTE N -- independent mapper cross-checks of the hand remap.

Route B  maps the RTL onto the SAME restricted pass-gate cell set with ABC, so
         the hand remap in remap.py is checked against what a mapper finds
         rather than declared optimal.
Route N  maps onto {inv, nand2} only -- my OWN NAND2-only path, so the sibling
         run's NAND2-only numbers (qal/sha256/REMAP.json, read-only input here)
         are cross-checked rather than quoted unchecked.

Both min-area and min-delay ABC scripts are run for every library, because the
brief asks for cell count AND depth and those trade against each other.
"""
import os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
RTL = "/usr/local/src/stat-sim/qal/synth/threeway/sha_slice.v"

SCRIPTS = {
    "area": "+strash;ifraig;scorr;dc2;dretime;strash;dch,-f;map,-a;topo;stime,-p;"
            "buffer,-N,2;upsize;dnsize",
    "del": "+strash;ifraig;scorr;dc2;dretime;strash;dch,-f;map;topo;stime,-p;"
           "buffer,-N,2;upsize;dnsize",
    "resyn2": "+strash;ifraig;scorr;dc2;dretime;strash;&get,-n;&dch,-f;&nf;&put;"
              "buffer,-N,2;upsize;dnsize",
}


def run(lib, script, tag):
    ys = os.path.join(OUT, "syn_%s.ys" % tag)
    v = os.path.join(OUT, "sha_slice.%s.v" % tag)
    open(ys, "w").write("\n".join([
        "read_verilog %s" % RTL,
        "hierarchy -top sha_slice",
        "proc; opt; techmap; opt",
        "abc -liberty %s -script %s" % (lib, script),
        "opt_clean",
        "write_verilog -noattr %s" % v,
        "stat -liberty %s" % lib,
    ]) + "\n")
    r = subprocess.run(["yosys", "-s", ys, "-l", os.path.join(OUT, "syn_%s.log" % tag)],
                       capture_output=True, text=True)
    if r.returncode:
        print("FAIL", tag, (r.stderr or r.stdout)[-800:])
        return None
    return v


if __name__ == "__main__":
    made = []
    for libtag, lib in (("pg", "pg.lib"), ("pgnor", "pgnor.lib"), ("nand", "nand.lib")):
        for stag, script in SCRIPTS.items():
            t = "abc_%s_%s" % (libtag, stag)
            v = run(os.path.join(OUT, lib), script, t)
            if v:
                made.append(v)
                print("made", os.path.basename(v))
    print("\n".join(made))
