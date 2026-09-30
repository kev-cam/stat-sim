#!/usr/bin/env python3
"""Per-LEVEL block-time composition.

compose.py uses one global maximum over the cell types a mapping contains, which is
an UPPER bound: a level that happens to hold only fast cells is charged for the
slowest cell anywhere in the design.  This composes level by level -- each QAL bank
opens when the slowest cell IN THAT BANK has settled -- so

    T_block = sum over levels of max(t_level of the cell types in that level)

which is the correct composition and is <= the global-max form.  Both are reported.
"""
import collections, json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, "/usr/local/src/stat-sim/qal/synth/threeway")
T = json.load(open(os.path.join(HERE, "CENSUS_TABLE.json")))
W = json.load(open(os.path.join(HERE, "REMAP_WIDTH.json")))
R = json.load(open(os.path.join(HERE, "REMAP.json")))
OUTPINS = ("X", "Y")
CMOS_T, CMOS_E, PROJ_E = 928.0, 232.0, 136.8


def fam(c):
    return c.replace("sg13g2_", "").rsplit("_", 1)[0]


def levels_with_types(path):
    """same levelisation as the committed levelize_mapped.py, but keeping cell TYPE."""
    src = open(path).read()
    body = src[src.index("module sha_slice("):]
    body = body[:body.index("endmodule")]
    pin = set()
    for m in re.finditer(r"^\s*input\s+(?:\[(\d+):(\d+)\]\s+)?(\\?[\w$.:\[\]]+)\s*;",
                         body, re.M):
        hi, lo, nm = m.groups()
        if hi is None:
            pin.add(nm)
        else:
            for i in range(int(lo), int(hi) + 1):
                pin.add("%s[%d]" % (nm, i))
    cells, drv = {}, {}
    for m in re.finditer(r"^\s*(sg13g2_\w+)\s+(\\?\S+)\s*\((.*?)\);", body, re.M | re.S):
        ct, cn, conns = m.groups()
        pins = {k: v.strip() for k, v in re.findall(r"\.(\w+)\(([^)]*)\)", conns)}
        cells[cn] = (ct, pins)
        for p in OUTPINS:
            if p in pins:
                drv[pins[p]] = cn
    lvl = {}
    for start in list(cells):
        st = [start]
        while st:
            k = st[-1]
            if lvl.get(k, 0) > 0:
                st.pop(); continue
            ct, pins = cells[k]
            ins = [v for p, v in pins.items() if p not in OUTPINS]
            pend = [drv[n] for n in ins if n not in pin and n in drv
                    and lvl.get(drv[n], 0) == 0]
            if pend:
                st.extend(pend); continue
            L = 1
            for n in ins:
                if n in pin or n not in drv:
                    continue
                L = max(L, lvl.get(drv[n], 0) + 1)
            lvl[k] = L
            st.pop()
    D = max(lvl.values())
    per = collections.defaultdict(collections.Counter)
    for cn, L in lvl.items():
        per[L][fam(cells[cn][0])] += 1
    return D, {L: dict(per[L]) for L in range(1, D + 1)}


out = {"_doc": __doc__, "rows": {}}
base_W = W["committed"]["W_tot_um"]
for k, r in R.items():
    D, per = levels_with_types(r["path"])
    tl = []
    for L in range(1, D + 1):
        fams = per[L]
        worst = max(fams, key=lambda f: T[f]["t_level_meas_ps"])
        tl.append((L, worst, T[worst]["t_level_meas_ps"], fams))
    Tsum = sum(x[2] for x in tl)
    gmax = max(x[2] for x in tl) * D
    xw = W[k]["W_tot_um"] / base_W
    out["rows"][k] = dict(
        MEASURED=dict(cells=W[k]["cells"], devices=W[k]["devices"],
                      W_tot_um=W[k]["W_tot_um"], area_um2=W[k]["area_um2"], depth=D,
                      per_level=[dict(level=L, limiter=w, t_level_ps=round(t, 3),
                                      families=f) for L, w, t, f in tl]),
        DERIVED=dict(T_block_perlevel_ps=round(Tsum, 1),
                     T_block_globalmax_ps=round(gmax, 1),
                     T_x_CMOS_block=round(Tsum / CMOS_T, 3),
                     x_width=round(xw, 3), x_area=round(W[k]["area_um2"] / W["committed"]["area_um2"], 3),
                     E_scaled_by_width_fJ=round(PROJ_E * xw, 1),
                     E_adv_vs_CMOS=round(CMOS_E / (PROJ_E * xw), 3)))
json.dump(out, open(os.path.join(HERE, "BLOCK_COMPOSE2.json"), "w"), indent=1)
print("%-18s %5s %5s %11s %11s %7s %8s %6s" % ("mapping", "cells", "depth",
      "T perlvl ps", "T gmax ps", "xCMOS", "E fJ", "Eadv"))
for k, v in out["rows"].items():
    m, d = v["MEASURED"], v["DERIVED"]
    print("%-18s %5d %5d %11.1f %11.1f %7.2f %8.1f %6.2f" % (k, m["cells"], m["depth"],
          d["T_block_perlevel_ps"], d["T_block_globalmax_ps"], d["T_x_CMOS_block"],
          d["E_scaled_by_width_fJ"], d["E_adv_vs_CMOS"]))
