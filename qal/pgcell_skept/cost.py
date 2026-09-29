#!/usr/bin/env python3
"""COST CONSISTENCY CHECK on the Phase-2 rail-draw column.

The Phase-2 table quotes the pass-gate remaps' bank-rail charge using the
FIXED-WELL (n-well on +1.5 V) per-cell numbers -- pg_mux2 = 3.16 fC MEASURED,
pg_xor2/pg_xnor2 = 6.173 fC DERIVED as two inverters.  But the same run's own
admission rule closes the fixed well (N_VAL = 0) and admits pgp1/pgp1c only in
the RAIL well, where the same cells were MEASURED at 10.934 fC (pg_mux2) and
13.473 fC (pg_xnor2) -- indistinguishable from the static cells they replace.

So the admissible variant's rail charge is quoted in the tie it is not allowed to
use.  Recomputed here in BOTH ties, from the run's own per-vector RAILDRAW data
and my own independent cell census."""
import json, os, statistics as st

HERE = os.path.dirname(os.path.abspath(__file__))
RUN = "/usr/local/src/stat-sim/qal/pgcell"
r = json.load(open(os.path.join(RUN, "RAILDRAW.json")))
v = json.load(open(os.path.join(RUN, "RAILDRAW_VHI.json")))
cen = json.load(open(os.path.join(HERE, "CENSUS_SKEPT.json")))


def m(d, pre):
    return st.mean([x["q_rail_fC"] for k, x in d.items()
                    if isinstance(x, dict) and k.startswith(pre)])


RUNM = dict(
    inv=m(r, "si"), static_mux=m(r, "sm"), static_xnor=m(r, "sx"),
    pg_mux_rail=m(r, "wm"), pg_xnor_rail=m(r, "wx"),
    pg_mux_vhi=m(v, "qm"))
RUNM["pg_xnor_vhi_DERIVED_2xinv"] = 2 * RUNM["inv"]

PER = {
    "vhi_as_the_run_quoted_it": {
        "pg_mux2": RUNM["pg_mux_vhi"], "pg_xor2": RUNM["pg_xnor_vhi_DERIVED_2xinv"],
        "pg_xnor2": RUNM["pg_xnor_vhi_DERIVED_2xinv"], "sg13g2_inv_1": RUNM["inv"],
        "sg13g2_mux2_1": RUNM["static_mux"], "sg13g2_xnor2_1": RUNM["static_xnor"]},
    "rail_the_tie_the_rule_ADMITS": {
        "pg_mux2": RUNM["pg_mux_rail"], "pg_xor2": RUNM["pg_xnor_rail"],
        "pg_xnor2": RUNM["pg_xnor_rail"], "sg13g2_inv_1": RUNM["inv"],
        "sg13g2_mux2_1": RUNM["static_mux"], "sg13g2_xnor2_1": RUNM["static_xnor"]},
}

OUT = dict(per_cell_fC=PER, run_means_fC=RUNM, rows={})
for nm, c in cen.items():
    row = {}
    for tie, tbl in PER.items():
        tot, cov, unc = 0.0, 0, {}
        for cell, k in c["hist"].items():
            if cell in tbl:
                tot += tbl[cell] * k
                cov += k
            else:
                unc[cell] = k
        row[tie] = dict(q_rail_fC=round(tot, 2), cells_covered=cov,
                        cells_total=c["cells"],
                        coverage_pct=round(100.0 * cov / c["cells"], 1),
                        uncovered=unc)
    OUT["rows"][nm] = row

FLOOR = None
cm = cen["cmos"]
# the run's ASSUMED floor: every unmetered committed cell charged one inverter
cov = sum(k for cell, k in cm["hist"].items()
          if cell in PER["rail_the_tie_the_rule_ADMITS"])
FLOOR = (OUT["rows"]["cmos"]["rail_the_tie_the_rule_ADMITS"]["q_rail_fC"]
         + RUNM["inv"] * (cm["cells"] - cov))
OUT["committed_ASSUMED_floor_fC"] = round(FLOOR, 2)
OUT["ratios_vs_committed_floor"] = {
    nm: {tie: round(row[tie]["q_rail_fC"] / FLOOR, 3) for tie in PER}
    for nm, row in OUT["rows"].items()}

json.dump(OUT, open(os.path.join(HERE, "COST_SKEPT.json"), "w"), indent=1)
print("per-cell q_rail (fC), from the run's own RAILDRAW per-vector data:")
for k, x in RUNM.items():
    print("   %-28s %8.4f" % (k, x))
print("\ncommitted ASSUMED floor = %.2f fC (run quoted 292.9)" % FLOOR)
print("\n%-18s %14s %14s   %8s %8s" % ("variant", "q_rail vhi", "q_rail RAIL",
                                       "x floor", "x floor"))
for nm in ("cmos", "pgp", "pgp1", "pgp1c", "pgp2", "pgp2c", "pgr1", "pgr1c",
           "abc_nand_resyn2", "abc_pg_resyn2"):
    if nm not in OUT["rows"]:
        continue
    a = OUT["rows"][nm]["vhi_as_the_run_quoted_it"]
    b = OUT["rows"][nm]["rail_the_tie_the_rule_ADMITS"]
    print("%-18s %8.1f(%3.0f%%) %8.1f(%3.0f%%)   %8.2f %8.2f"
          % (nm, a["q_rail_fC"], a["coverage_pct"], b["q_rail_fC"],
             b["coverage_pct"],
             OUT["ratios_vs_committed_floor"][nm]["vhi_as_the_run_quoted_it"],
             OUT["ratios_vs_committed_floor"][nm]["rail_the_tie_the_rule_ADMITS"]))
print("\nwrote COST_SKEPT.json")
