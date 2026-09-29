#!/usr/bin/env python3
"""PHASE 2 / G0 ANCHOR -- independent census of a mapped netlist.

Written for THIS run.  Nothing is imported from qal/sha256/ (the sibling
NAND2-only run); its numbers are read back later purely as a cross-check.

Reports, per netlist:
  cells        instance count
  types        histogram of cell types
  devices      transistor count, MEASURED from the PDK spice netlist
               (/usr/local/src/IHP-Open-PDK/.../sg13g2_stdcell.spice) for library
               cells, and from the Phase 1 emitted TG netlists for the pass-gate
               cells (qal/pgcell/pg.py -- imported, not re-typed)
  W_tot_um     sum of device widths, same sources
  depth        logic depth in CELL LEVELS: level(cell) = 1 + max(level of driving
               cells), primary inputs at level 0.  Purely combinational.
  profile      cells per level, level 1 first

The netlist is read through YOSYS write_json, not a hand parser: the RTL declares
six names in one `input [7:0] a, b, c, ...` and a regex gets that wrong.
"""
import json, os, re, subprocess, sys, collections

HERE = os.path.dirname(os.path.abspath(__file__))
PDK_SPICE = ("/usr/local/src/IHP-Open-PDK/ihp-sg13g2/libs.ref/sg13g2_stdcell/"
             "spice/sg13g2_stdcell.spice")
OUT = os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)


# ---------------------------------------------------------------- PDK devices
def pdk_devices():
    """MEASURED device count and total width per library cell, from the PDK's own
    spice netlist.  A '.subckt X ...' block; every line beginning with M or X that
    names a sg13_lv_{n,p}mos is one transistor."""
    txt = open(PDK_SPICE).read()
    cells, cur, name = {}, None, None
    for ln in txt.splitlines():
        s = ln.strip()
        if s.lower().startswith(".subckt"):
            name = s.split()[1]
            cur = {"n_dev": 0, "W_um": 0.0, "n_n": 0, "n_p": 0}
        elif s.lower().startswith(".ends"):
            if name:
                cells[name] = cur
            cur, name = None, None
        elif cur is not None and s and s[0] in "XMxm":
            m = re.search(r"sg13_lv_(n|p)mos", s)
            if not m:
                continue
            w = re.search(r"\bw\s*=\s*([0-9.eE+-]+)\s*([munp]?)", s)
            if not w:
                continue
            val, suf = float(w.group(1)), w.group(2)
            um = {"u": 1.0, "n": 1e-3, "m": 1e3, "p": 1e-6, "": 1e6}[suf] * val
            cur["n_dev"] += 1
            cur["W_um"] += um
            cur["n_n" if m.group(1) == "n" else "n_p"] += 1
    return cells


# ---------------------------------------------- pass-gate cells, from Phase 1
def pg_devices():
    """Device count / width of the Phase 1 TG cells.  pg.py is IMPORTED so the
    numbers come from the netlist generator that Phase 1 actually simulated, not
    from a re-typed table."""
    sys.path.insert(0, os.path.dirname(HERE))
    import pg
    wn, wp = pg.TGW["tgM"]                  # the REPORTED cell: 0.74u n / 1.12u p
    # The two control inverters are campaign-standard statics (pg._inv uses
    # WP/WN = 1.12/0.74); at tgM the pass switches carry the same widths, so the
    # per-cell totals below are 4n+4p / 3n+3p of (WN, WP).  Cross-checked against
    # the emitted netlists in check_pg_netlist() rather than asserted.
    assert (pg.WN, pg.WP) == (wn, wp), (pg.WN, pg.WP, wn, wp)
    return {
        # inv_A + inv_B (2 dev each) + TG1 (n+p) + TG2 (n+p)
        "pg_xor2":  {"n_dev": 8, "n_n": 4, "n_p": 4, "W_um": 4 * wn + 4 * wp},
        "pg_xnor2": {"n_dev": 8, "n_n": 4, "n_p": 4, "W_um": 4 * wn + 4 * wp},
        # inv_S (2 dev) + TG0 (n+p) + TG1 (n+p)
        "pg_mux2":  {"n_dev": 6, "n_n": 3, "n_p": 3, "W_um": 3 * wn + 3 * wp},
    }, (wn, wp)


def check_pg_netlist():
    """MEASURE the TG cell device counts and widths off the Phase 1 EMITTED
    netlist instead of trusting the table above."""
    sys.path.insert(0, os.path.dirname(HERE))
    import pg
    w = pg.TGW["tgM"]
    got = {}
    for nm, lines in (
            ("pg_xnor2", pg.tg_xnor2("t", "Y", "A", "B", "VR", "0", w)),
            ("pg_xor2",  pg.tg_xnor2("t", "Y", "A", "B", "VR", "0", w, xor_form=True)),
            ("pg_mux2",  pg.tg_mux2("t", "X", "A0", "A1", "S", "VR", "0", w))):
        n = wsum = nn = npp = 0
        for ln in lines:
            m = re.search(r"sg13_lv_(n|p)mos\s+w=([0-9.]+)u", ln)
            if not m:
                continue
            n += 1
            wsum += float(m.group(2))
            if m.group(1) == "n":
                nn += 1
            else:
                npp += 1
        got[nm] = {"n_dev": n, "n_n": nn, "n_p": npp, "W_um": round(wsum, 6)}
    return got


# --------------------------------------------------------------- netlist read
def read_netlist(path, extra_reads=()):
    js = os.path.join(OUT, "nl_%s.json" % re.sub(r"\W+", "_", os.path.basename(path)))
    sc = js.replace(".json", ".ys")
    open(sc, "w").write("\n".join(
        ["read_verilog %s" % p for p in extra_reads] +
        ["read_verilog %s" % path,
         "hierarchy -top sha_slice",
         "write_json %s" % js]) + "\n")
    r = subprocess.run(["yosys", "-q", "-s", sc], capture_output=True, text=True)
    if r.returncode:
        raise SystemExit("yosys read failed for %s:\n%s" % (path, (r.stderr or r.stdout)[-2000:]))
    return json.load(open(js))["modules"]["sha_slice"]


OUTPUT_PORT = {"Y", "X", "Q", "Z"}          # library convention; verified below


def census(path, extra_reads=(), dirmap=None):
    mod = read_netlist(path, extra_reads)
    ports = mod["ports"]
    cells = mod["cells"]

    # driver map: net bit -> driving cell.  Port directions come from the cell's
    # own port_directions when yosys knows them (it does for the blackbox models
    # we read in), else from OUTPUT_PORT.
    driver, inbits = {}, set()
    for pn, p in ports.items():
        if p["direction"] == "input":
            inbits |= {b for b in p["bits"] if isinstance(b, int)}
    for cn, c in cells.items():
        pd = c.get("port_directions", {})
        for pin, bits in c["connections"].items():
            d = pd.get(pin) or ("output" if pin in OUTPUT_PORT else "input")
            if d == "output":
                for b in bits:
                    if isinstance(b, int):
                        driver[b] = cn

    memo = {}

    def lvl(cn, stack=()):
        if cn in memo:
            return memo[cn]
        if cn in stack:
            raise SystemExit("combinational loop at %s" % cn)
        c = cells[cn]
        pd = c.get("port_directions", {})
        best = 0
        for pin, bits in c["connections"].items():
            d = pd.get(pin) or ("output" if pin in OUTPUT_PORT else "input")
            if d != "input":
                continue
            for b in bits:
                if isinstance(b, int) and b in driver:
                    best = max(best, lvl(driver[b], stack + (cn,)))
        memo[cn] = best + 1
        return memo[cn]

    lv = {cn: lvl(cn) for cn in cells}
    depth = max(lv.values()) if lv else 0

    # PATH-BASED pass-gate run length -- the quantity the Phase 1 restoration
    # rule actually caps.  run(cell) = 0 for a rail-restoring cell, else
    # 1 + max(run of driving cells).  Two adjacent LEVELS both containing a
    # pass-gate cell are harmless if no signal crosses from one to the other;
    # the level-based metric below is only an upper bound, this one is exact.
    PG = {"pg_xor2", "pg_xnor2", "pg_mux2"}
    rmemo = {}

    def prun(cn):
        if cn in rmemo:
            return rmemo[cn]
        rmemo[cn] = 0                      # guard; the graph is acyclic (checked)
        c = cells[cn]
        if c["type"] not in PG:
            rmemo[cn] = 0
            return 0
        pd = c.get("port_directions", {})
        best = 0
        for pin, bits in c["connections"].items():
            d = pd.get(pin) or ("output" if pin in OUTPUT_PORT else "input")
            if d != "input":
                continue
            for b in bits:
                if isinstance(b, int) and b in driver:
                    best = max(best, prun(driver[b]))
        rmemo[cn] = best + 1
        return rmemo[cn]

    pruns = {cn: prun(cn) for cn in cells}
    max_path_run = max(pruns.values()) if pruns else 0
    prof = [0] * depth
    for cn, L in lv.items():
        prof[L - 1] += 1

    # per-level type composition -> the BANK PROFILE.  A QAL bank is the set of
    # cells that settle together on one beat, i.e. one logic level; the measured
    # banktank bank is 8 cells wide (qal/banktank, 8 cells/bank, T = 200 ps beat).
    level_types = [collections.Counter() for _ in range(depth)]
    for cn, L in lv.items():
        level_types[L - 1][cells[cn]["type"]] += 1
    PASSGATE = {"pg_xor2", "pg_xnor2", "pg_mux2"}
    banks_per_level = [-(-n // BANK_W) for n in prof]
    kinds = []
    for lt in level_types:
        has_pg = any(t in PASSGATE for t in lt)
        has_st = any(t not in PASSGATE for t in lt)
        kinds.append("tg" if has_pg and not has_st else
                     "static" if has_st and not has_pg else "MIXED")

    types = collections.Counter(c["type"] for c in cells.values())
    dev = DEV
    n_dev = sum(dev[t]["n_dev"] * n for t, n in types.items())
    w_tot = sum(dev[t]["W_um"] * n for t, n in types.items())
    n_n = sum(dev[t]["n_n"] * n for t, n in types.items())
    n_p = sum(dev[t]["n_p"] * n for t, n in types.items())
    unknown = [t for t in types if t not in dev]
    if unknown:
        raise SystemExit("no device data for %s" % unknown)
    return {
        "path": path,
        "cells": len(cells),
        "types": sorted(types.items(), key=lambda kv: (-kv[1], kv[0])),
        "devices": n_dev, "n_nmos": n_n, "n_pmos": n_p,
        "W_tot_um": round(w_tot, 4),
        "depth": depth,
        "profile": prof,
        "bank_profile": {
            "bank_width_cells": BANK_W,
            "cells_per_level": prof,
            "banks_per_level": banks_per_level,
            "total_banks": sum(banks_per_level),
            "beats": depth,
            "level_kind": kinds,
            "level_types": [dict(lt) for lt in level_types],
            "n_levels_MIXED": kinds.count("MIXED"),
            "n_levels_tg_only": kinds.count("tg"),
            "n_levels_static_only": kinds.count("static"),
            "max_consecutive_tg_levels_UPPER_BOUND": _max_run(kinds),
        },
        "max_passgate_run_on_any_path": max_path_run,
        "passgate_run_histogram": dict(collections.Counter(pruns.values())),
        "ports": sorted((n, p["direction"], len(p["bits"])) for n, p in ports.items()),
    }


BANK_W = 8          # MEASURED banktank bank width: 8 cells per bank


def _max_run(kinds):
    """Longest run of levels that contain a pass-gate cell -- the quantity the
    Phase 1 restoration rule caps.  A MIXED level counts as containing one."""
    best = cur = 0
    for k in kinds:
        cur = cur + 1 if k in ("tg", "MIXED") else 0
        best = max(best, cur)
    return best


DEV = {}


def build_dev_table():
    global DEV
    DEV = dict(pdk_devices())
    pg, w = pg_devices()
    DEV.update(pg)
    return w


if __name__ == "__main__":
    w = build_dev_table()
    emitted = check_pg_netlist()
    for k, v in emitted.items():
        tbl = {kk: (round(vv, 6) if isinstance(vv, float) else vv)
               for kk, vv in DEV[k].items()}
        if tbl != v:
            raise SystemExit("TG table disagrees with the EMITTED netlist for %s:"
                             " table %s vs emitted %s" % (k, tbl, v))
    res = {"_tg_widths_um": {"n": w[0], "p": w[1]},
           "_tg_from_emitted_netlist_MEASURED": emitted,
           "_pdk_spice": PDK_SPICE, "runs": {}}
    args = sys.argv[1:]
    extra = []
    paths = []
    for a in args:
        (extra if a.startswith("+") else paths).append(a.lstrip("+"))
    for p in paths:
        c = census(p, extra)
        res["runs"][os.path.basename(p)] = c
        print("%-34s cells %3d  dev %4d  W %8.2f um  depth %2d  profile %s"
              % (os.path.basename(p), c["cells"], c["devices"], c["W_tot_um"],
                 c["depth"], c["profile"]))
        print("   types: " + ", ".join("%s x%d" % t for t in c["types"]))
    json.dump(res, open(os.path.join(OUT, "CENSUS.json"), "w"), indent=1)
