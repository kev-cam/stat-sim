#!/usr/bin/env python3
"""Compose each mapping's block time from the CENSUS, not from a single family.

A QAL bank holds one logic level of MIXED cell types and does not open until every
cell in it has settled, so the bank's level time is the MAXIMUM over the cell types
that level contains.  Using the inverter's 75.9 ps for a mapping that contains nor2
would be quoting the best cell in the bank and ignoring the one that sets the beat.
"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
T = json.load(open(os.path.join(HERE, "CENSUS_TABLE.json")))
W = json.load(open(os.path.join(HERE, "REMAP_WIDTH.json")))
CMOS_T, CMOS_E = 928.0, 232.0
PROJ_E = 136.8

def fam(cell):
    return cell.replace("sg13g2_", "").rsplit("_", 1)[0]

out = {"_doc": "per-mapping block time composed from the MEASURED census: "
                "T = DEPTH x max(t_level over the cell types the mapping uses). "
                "Energy scaled by MEASURED total device width against the committed "
                "mapping. CMOS reference 232 fJ @ 0.928 ns (committed).",
       "rows": {}}
base_W = W["committed"]["W_tot_um"]
for k, v in W.items():
    fams = sorted({fam(c) for c in v["types"]})
    tl = {f: (T[f]["t_level_meas_ps"] if f in T else None) for f in fams}
    if any(x is None for x in tl.values()):
        out["rows"][k] = dict(cell_types=fams, t_level_by_family_ps=tl,
                              note="a cell type in this mapping has no settling row "
                                   "(census FAIL or not measured) -- no block time")
        continue
    worst = max(tl, key=lambda f: tl[f])
    Tb = v["depth"] * tl[worst]
    xw = v["W_tot_um"] / base_W
    out["rows"][k] = dict(
        MEASURED=dict(cells=v["cells"], devices=v["devices"], W_tot_um=v["W_tot_um"],
                      depth=v["depth"], cell_types=fams, t_level_by_family_ps=tl,
                      bank_t_level_ps=tl[worst], bank_limiting_family=worst),
        DERIVED=dict(T_block_ps=round(Tb, 1),
                     T_x_CMOS_block=round(Tb / CMOS_T, 3),
                     x_width_vs_committed=round(xw, 3),
                     E_scaled_fJ=round(PROJ_E * xw, 1),
                     E_adv_vs_CMOS=round(CMOS_E / (PROJ_E * xw), 3)))
json.dump(out, open(os.path.join(HERE, "BLOCK_COMPOSE.json"), "w"), indent=1)
print("%-18s %5s %5s %9s %-8s %10s %8s %8s %6s" % (
    "mapping", "cells", "depth", "bankT ps", "limiter", "T block ps", "xCMOS", "E fJ", "Eadv"))
for k, r in out["rows"].items():
    if "MEASURED" not in r:
        print("%-18s  -- %s" % (k, r["note"])); continue
    m, d = r["MEASURED"], r["DERIVED"]
    print("%-18s %5d %5d %9.2f %-8s %10.1f %8.2f %8.1f %6.2f" % (
        k, m["cells"], m["depth"], m["bank_t_level_ps"], m["bank_limiting_family"],
        d["T_block_ps"], d["T_x_CMOS_block"], d["E_scaled_fJ"], d["E_adv_vs_CMOS"]))
