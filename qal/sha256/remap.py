#!/usr/bin/env python3
"""PHASE 1(c): the SHALLOW-STACK REMAP of sha_slice, and its cost.

Builds a liberty subset containing only a named set of cells and re-maps the
COMMITTED qal/synth/threeway/sha_slice.v with the same yosys 0.58 that produced the
committed sha_slice.cmos.v.  Four mappings are produced (PRE_REGISTERED phase1c):

  full     all 84 cells                 -- CONTROL: must reproduce 56 / DEPTH 8
  shallow  {inv, nand2, and2}           -- the census PASS set (primary target)
  nand     {inv, nand2}                 -- does and2 buy anything?
  d2ok     {inv,nand2,and2,nor2,or2}    -- prices the nor2/or2 exclusion alone

usage: remap.py <name>        map one
       remap.py report        levelize + histogram all that exist
"""
import collections, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SYN = os.path.join(HERE, "syn")
RTL = "/usr/local/src/stat-sim/qal/synth/threeway/sha_slice.v"
LIB = ("/usr/local/src/IHP-Open-PDK/ihp-sg13g2/libs.ref/sg13g2_stdcell/lib/"
       "sg13g2_stdcell_typ_1p20V_25C.lib")
LEVELIZE = "/usr/local/src/stat-sim/qal/synth/threeway/levelize_mapped.py"
YOSYS = "yosys"

# AMENDMENT R1 (forced, recorded): abc's liberty mapper REFUSES a library with no
# buffer cell -- "ERROR: ABC failed with status B" on {inv,nand2,and2}.  Adding
# sg13g2_buf_1 fixes it.  buf_1 is TWO CASCADED INVERTERS; its binding pMOS rise
# depth is 1 (stacks.py, verified), so it belongs in the shallow set on the census's
# own criterion and is measured in the census like every other family.
SETS = {
    "full":    None,
    "shallow": ["sg13g2_inv_1", "sg13g2_nand2_1", "sg13g2_and2_1", "sg13g2_buf_1"],
    "nand":    ["sg13g2_inv_1", "sg13g2_nand2_1", "sg13g2_buf_1"],
    "d2ok":    ["sg13g2_inv_1", "sg13g2_nand2_1", "sg13g2_and2_1", "sg13g2_buf_1",
                "sg13g2_nor2_1", "sg13g2_or2_1"],
}


def subset_liberty(keep, out):
    """Emit a liberty containing only `keep` cells.  Brace-balanced extraction of
    each cell{} block, everything outside the cell blocks kept verbatim."""
    txt = open(LIB).read()
    head_end = txt.index("\n  cell (")
    head = txt[:head_end]
    blocks, i = [], head_end
    while True:
        m = re.compile(r"\n  cell \((\S+?)\)").search(txt, i)
        if not m:
            break
        name = m.group(1)
        j = txt.index("{", m.end())
        depth, k = 1, j + 1
        while depth:
            if txt[k] == "{":
                depth += 1
            elif txt[k] == "}":
                depth -= 1
            k += 1
        blocks.append((name, txt[m.start():k]))
        i = k
    sel = [b for n, b in blocks if n in keep]
    missing = set(keep) - {n for n, _ in blocks}
    if missing:
        raise SystemExit("cells not in liberty: %s" % missing)
    open(out, "w").write(head + "".join(sel) + "\n}\n")
    return len(sel), len(blocks)


def run(name):
    os.makedirs(SYN, exist_ok=True)
    keep = SETS[name]
    lib = LIB
    if keep is not None:
        lib = os.path.join(SYN, "lib_%s.lib" % name)
        n, tot = subset_liberty(set(keep), lib)
        print("liberty subset %s: %d of %d cells" % (name, n, tot))
    outv = os.path.join(SYN, "sha_slice.%s.v" % name)
    script = "\n".join([
        "read_verilog %s" % RTL,
        "hierarchy -check -top sha_slice",
        "proc; opt; fsm; opt; memory; opt",
        "techmap; opt",
        "dfflibmap -liberty %s" % lib,
        "abc -liberty %s" % lib,
        "opt_clean",
        "write_verilog -noattr %s" % outv,
        "stat -liberty %s" % lib,
    ])
    sp = os.path.join(SYN, "%s.ys" % name)
    open(sp, "w").write(script + "\n")
    r = subprocess.run([YOSYS, "-q", "-s", sp], capture_output=True, text=True)
    open(os.path.join(SYN, "log_%s.txt" % name), "w").write(r.stdout + r.stderr)
    if r.returncode:
        print(r.stdout[-3000:], r.stderr[-3000:])
        raise SystemExit("yosys failed for %s" % name)
    print("wrote", outv)
    return outv


def levelize(path):
    r = subprocess.run([sys.executable, LEVELIZE, path, "sha_slice"],
                       capture_output=True, text=True)
    return r.stdout.strip()


def report():
    print("%-9s %6s %6s  %s" % ("mapping", "cells", "DEPTH", "profile"))
    for name in ["committed", "full", "shallow", "nand", "d2ok"]:
        p = ("/usr/local/src/stat-sim/qal/synth/threeway/work/sha_slice.cmos.v"
             if name == "committed" else os.path.join(SYN, "sha_slice.%s.v" % name))
        if not os.path.exists(p):
            continue
        out = levelize(p)
        m = re.search(r"comb (\d+).*DEPTH (\d+)", out)
        prof = re.search(r"profile: (\S+)", out).group(1)
        print("%-9s %6s %6s  %s" % (name, m.group(1), m.group(2), prof))
        print("          %s" % re.search(r"top cell types: (.*)", out).group(1))


if __name__ == "__main__":
    if sys.argv[1] == "report":
        report()
    else:
        run(sys.argv[1])
