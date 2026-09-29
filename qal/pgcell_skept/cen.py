#!/usr/bin/env python3
"""Independent re-census: cells, devices, total device width, logic DEPTH and the
maximum consecutive PASS-GATE run, computed here from the netlists + the PDK
spice.  Written so the Phase-2 cost table rests on something other than its own
counter."""
import json, os, re, sys, collections

PDK = ("/usr/local/src/IHP-Open-PDK/ihp-sg13g2/libs.ref/sg13g2_stdcell/spice/"
       "sg13g2_stdcell.spice")
OUT = "/usr/local/src/stat-sim/qal/pgcell/p2/out"
CMOS = "/usr/local/src/stat-sim/qal/synth/threeway/work/sha_slice.cmos.v"
HERE = os.path.dirname(os.path.abspath(__file__))

# hand-built pass-gate cells: (devices, total width um) from qal/pgcell/pg.py
# tgM = 0.74u n / 1.12u p pass devices; control inverters 1.12u p / 0.74u n
TWN, TWP, WP, WN = 0.74, 1.12, 1.12, 0.74
PG = {
    # 2 inverters (4 dev) + 2 TGs (4 dev) = 8 dev
    "pg_xor2":  (8, 2 * (WP + WN) + 2 * (TWN + TWP)),
    "pg_xnor2": (8, 2 * (WP + WN) + 2 * (TWN + TWP)),
    # 1 inverter (2 dev) + 2 TGs (4 dev) = 6 dev
    "pg_mux2":  (6, 1 * (WP + WN) + 2 * (TWN + TWP)),
}
PASSGATE = set(PG)


def pdk_cells():
    """device count and total width of each PDK subckt, from the PDK spice"""
    cur, n, w, out = None, 0, 0.0, {}
    npm = {}
    for ln in open(PDK):
        s = ln.strip()
        if s.lower().startswith(".subckt"):
            cur, n, w, npm = s.split()[1], 0, 0.0, {"n": 0, "p": 0}
        elif s.lower().startswith(".ends"):
            if cur:
                out[cur] = (n, w, dict(npm))
            cur = None
        elif cur and s and s[0].upper() == "X":
            p = s.split()
            # MY OWN BUG, caught by the cmos row disagreeing with both the run's
            # census and the sibling's: the PDK spice writes some widths in
            # NANOMETRES (w=740.00n) and my first regex only matched `u`, so
            # every n-suffixed device was silently dropped (cmos read 160 dev
            # instead of 406).  Both suffixes are now handled and the row agrees.
            m = re.search(r"w=([0-9.eE+-]+)([un])", s)
            if m:
                n += 1
                w += float(m.group(1)) * (1.0 if m.group(2) == "u" else 1e-3)
                npm["p" if "pmos" in s else "n"] += 1
    return out


INST = re.compile(r"^\s*([A-Za-z_][\w$]*)\s+([A-Za-z_][\w$\\]*)\s*\(", re.M)


def parse(path):
    """returns [(celltype, instname, {port: net})]"""
    txt = open(path).read()
    txt = re.sub(r"//[^\n]*", "", txt)
    out = []
    for m in re.finditer(r"([A-Za-z_]\w*)\s+(\\?[\w$\.]+)\s*\(([^;]*?)\)\s*;",
                         txt, re.S):
        cell, inst, body = m.group(1), m.group(2), m.group(3)
        if cell in ("module", "input", "output", "wire", "assign", "endmodule"):
            continue
        conns = {}
        for pm in re.finditer(r"\.(\w+)\s*\(\s*([^)]*?)\s*\)", body):
            conns[pm.group(1)] = pm.group(2).strip()
        if conns:
            out.append((cell, inst, conns))
    return out


OUTPIN = {"Y", "X", "L_HI", "L_LO"}


def depth(insts, primary_in):
    """longest path in cell levels from a primary input to any output"""
    drv = {}
    for cell, inst, c in insts:
        for p, net in c.items():
            if p in OUTPIN:
                drv[net] = (cell, inst, c)
    memo = {}

    def lv(net):
        if net in memo:
            return memo[net]
        if net not in drv or net in primary_in:
            return 0
        memo[net] = 0          # cycle guard
        cell, inst, c = drv[net]
        d = 1 + max([lv(n) for p, n in c.items() if p not in OUTPIN] or [0])
        memo[net] = d
        return d

    outs = []
    for cell, inst, c in insts:
        for p, net in c.items():
            if p in OUTPIN:
                outs.append(lv(net))
    return max(outs) if outs else 0, memo, drv


def pg_run(insts, primary_in):
    """longest consecutive PASS-GATE run along any path (path-based)"""
    drv = {}
    for cell, inst, c in insts:
        for p, net in c.items():
            if p in OUTPIN:
                drv[net] = (cell, inst, c)
    memo = {}

    def run(net):
        if net in memo:
            return memo[net]
        if net not in drv or net in primary_in:
            return 0
        memo[net] = 0
        cell, inst, c = drv[net]
        ups = [run(n) for p, n in c.items() if p not in OUTPIN] or [0]
        memo[net] = (max(ups) + 1) if cell in PASSGATE else 0
        return memo[net]

    best = 0
    for cell, inst, c in insts:
        for p, net in c.items():
            if p in OUTPIN:
                best = max(best, run(net))
    return best


def census(path, pdk):
    insts = parse(path)
    txt = open(path).read()
    pi = set()
    for m in re.finditer(r"input\s+(?:\[[^\]]*\]\s*)?([\w,\s]+);", txt):
        for nm in m.group(1).split(","):
            pi.add(nm.strip())
    hist = collections.Counter(c for c, _, _ in insts)
    dev = w = 0
    unknown = []
    for c, k in hist.items():
        if c in PG:
            dev += PG[c][0] * k
            w += PG[c][1] * k
        elif c in pdk:
            dev += pdk[c][0] * k
            w += pdk[c][1] * k
        else:
            unknown.append(c)
    d, memo, drv = depth(insts, pi)
    # bank profile: number of cells at each level
    lvl = collections.Counter()
    for c, i, conns in insts:
        o = [n for p, n in conns.items() if p in OUTPIN]
        if o:
            lvl[memo.get(o[0], 0)] += 1
    prof = [lvl[k] for k in range(1, d + 1)]
    return dict(path=path, cells=len(insts), devices=dev, width_um=round(w, 2),
                depth=d, runTG=pg_run(insts, pi), hist=dict(hist),
                level_profile=prof, unknown_cells=unknown)


if __name__ == "__main__":
    pdk = pdk_cells()
    names = sys.argv[1:] or ["cmos", "pgp", "pgp1", "pgp1c", "pgp2", "pgp2c",
                             "pgr1", "pgr1c", "abc_nand_resyn2", "abc_nand_area",
                             "abc_pg_resyn2", "abc_pg_area"]
    R = {}
    print("%-18s %6s %8s %9s %6s %6s" % ("variant", "cells", "devices", "W(um)",
                                         "depth", "runTG"))
    for n in names:
        p = CMOS if n == "cmos" else os.path.join(OUT, "sha_slice.%s.v" % n)
        if not os.path.exists(p):
            continue
        c = census(p, pdk)
        R[n] = c
        print("%-18s %6d %8d %9.2f %6d %6d%s"
              % (n, c["cells"], c["devices"], c["width_um"], c["depth"],
                 c["runTG"], "  UNKNOWN:%s" % c["unknown_cells"] if c["unknown_cells"] else ""))
    json.dump(R, open(os.path.join(HERE, "CENSUS_SKEPT.json"), "w"), indent=1)
    print("wrote CENSUS_SKEPT.json")
