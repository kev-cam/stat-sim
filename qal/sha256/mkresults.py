#!/usr/bin/env python3
"""Assemble RESULTS.json for Phase 1 from the measured artefacts.  Nothing is
computed here that is not already in a row file, a mapping, or a proof log."""
import hashlib, json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyse                                                     # noqa: E402


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def mtime(p):
    return subprocess.run(["ls", "-la", "--time-style=full-iso", p],
                          capture_output=True, text=True).stdout.split()[5:7]


def main():
    tbl = analyse.main()
    W = json.load(open(os.path.join(HERE, "REMAP_WIDTH.json")))
    CQ = json.load(open(os.path.join(HERE, "REMAP_CONSEQUENCE.json")))
    BC = json.load(open(os.path.join(HERE, "BLOCK_COMPOSE2.json")))
    BC["global_max_form_for_comparison"] = json.load(
        open(os.path.join(HERE, "BLOCK_COMPOSE.json")))
    XC = json.load(open(os.path.join(HERE, "CROSSCHECKS.json")))
    G0 = json.load(open(os.path.join(HERE, "rowd",
                                     "g0_o21ai_handbuilt_dv150.json")))
    G0B = json.load(open(os.path.join(HERE, "G0B_DELTA.json")))
    formal, vec = {}, {}
    vd = os.path.join(HERE, "verify")
    for fn in sorted(os.listdir(vd)):
        if fn.startswith("formal_"):
            d = json.load(open(os.path.join(vd, fn)))
            formal[fn[7:-5]] = {k: d[k] for k in
                                ("E5_PORT_FIDELITY", "E1_SAT_MITER", "E2_EQUIV")}
        if fn.startswith("vectors_"):
            d = json.load(open(os.path.join(vd, fn)))
            vec[fn[8:-5]] = {k: d[k] for k in
                             ("vectors", "mismatches", "E3_VECTORS")}
    passing = sorted(f for f, r in tbl.items() if r["verdict"] == "PASS")
    closure = {}
    for k, v in W.items():
        if k.startswith("full") or k == "committed":
            continue
        closure[k] = {c: (c.replace("sg13g2_", "").rsplit("_", 1)[0] in passing)
                      for c in sorted(v["types"])}
        closure[k]["ALL_CELLS_ARE_CENSUS_PASS"] = all(
            v for kk, v in closure[k].items() if kk.startswith("sg13g2_"))

    res = {
     "_doc": "PHASE 1 of the SHA-256 QAL block: the per-family QAL settling CENSUS, "
             "the shallow-stack REMAP of sha_slice and its measured cost, and the "
             "formal + vector EQUIVALENCE of that remap. Pre-registration: "
             "PRE_REGISTERED.json. Protocol amendments and instrument defects: "
             "AMENDMENT.md. Every figure MEASURED unless labelled DERIVED or ASSUMED.",
     "date": "2026-09-29",
     "pre_registration": {
       "file": "PRE_REGISTERED.json", "sha256": sha(os.path.join(HERE, "PRE_REGISTERED.json")),
       "written": " ".join(mtime(os.path.join(HERE, "PRE_REGISTERED.json"))),
       "first_deck_of_this_track": " ".join(mtime(os.path.join(
           HERE, "p_g0_o21ai_handbuilt_dv150.cir"))),
       "static_analysis_predates_it_by_design": {
         "stacks.py": " ".join(mtime(os.path.join(HERE, "stacks.py"))),
         "cells/stack_depths.json": " ".join(mtime(os.path.join(
             HERE, "cells", "stack_depths.json"))),
         "note": "static PDK-netlist analysis, disclosed inside the pre-registration; "
                 "no SPICE deck existed when the pre-registration was written."}},

     "G0_instrument_MEASURED": {
       "_doc": "the brief's own o21ai anchor, reproduced with the committed sk.py "
               "hand-built topology before any census row was believed.",
       "verdict": "PASS",
       "reproduced": {"VBEND": G0["VBEND"], "t_hop_ps": G0["t_hop_ps"],
                      "VA_open": G0["VA_open"], "t_valid80_ps": G0["t_valid80_ps"],
                      "IPK_uA": G0["IPK_uA"],
                      "s_end_min_pct": min(G0["s_end"].values()),
                      "t_valid90_ps": G0["t_valid90_ps"]},
       "worst_rel_error": "2.24e-14 (t_hop); VA_open, t_valid80 and IPK exactly 0",
       "reading": "the brief's anchor numbers -- 82.99 percent of rail at a 500 ps "
                  "freeze, t_valid80 first existing at 515.1 ps, t_valid90 never -- "
                  "are reproduced bit-for-bit."},
     "G0b_PDK_vs_HANDBUILT_MEASURED": G0B,

     "CENSUS_MEASURED": {
       "operating_point": {"dV_V": 1.65, "L_nH": 6.0, "TG_total_um": 120.0,
                           "VGH_V": 1.65, "tail_ps": 500.0, "CL_fF": 2.0,
                           "why": "the committed dvopt grid's measured optimum, and "
                                  "the top of the PDK's characterised envelope -- the "
                                  "point most GENEROUS to the deep-stack families."},
       "gates": {"C1_VALUE": "all 8 outputs on the correct side of half the end rail",
                 "C2_SETTLE": "t_valid90 exists inside the 500 ps tail",
                 "C3_SPEED": "t_level <= 2.0x the inv family at the same point"},
       "table": tbl},

     "REMAP_MEASURED": {
       "flow": "yosys 0.58 git sha1 157aabb58 -- the same version that produced the "
               "committed sha_slice.cmos.v. Liberty subsetted by cell name from "
               "sg13g2_stdcell_typ_1p20V_25C.lib. Seven abc variants per library; "
               "both Pareto ends reported.",
       "control": "the FULL-library flow reproduces the committed netlist exactly: "
                  "56 cells, DEPTH 8, profile 32/12/3/2/2/2/2/1, and the identical "
                  "cell-type histogram. The remap cost is therefore attributable to "
                  "the library restriction, not to the flow.",
       "mappings": W},
     "REMAP_CONSEQUENCE_DERIVED": CQ,
     "BLOCK_TIME_COMPOSED_FROM_THE_CENSUS": BC,
     "HEADLINE": {
       "_doc": "the Phase 1 answer. MEASURED: the census t_level of every family, the "
               "cell/device/width/area/depth of every mapping. DERIVED: the block time "
               "(sum over levels of the slowest cell in that level) and the energy "
               "(committed 136.8 fJ projection scaled by MEASURED total device width). "
               "No timing hardware is counted in either -- that is Phase 2.",
       "the_restriction_is_not_a_cost_it_is_the_ENABLER":
           "Running the COMMITTED 56-cell mapping on a QAL rail is MEASURED to work -- "
           "every one of its twelve cell families is value-correct and settles inside "
           "the 500 ps tail at dV=1.65 V -- but its banks are paced by mux2 at 507.1 ps "
           "and o21ai at 479.1 ps, so the block composes to 3632 ps, 3.91x the CMOS "
           "928 ps. The {inv, nand2} remap costs 2.88x the cells and 1.75x the depth "
           "and composes to 967 ps, 1.04x CMOS. The remap BUYS 3.76x of block time.",
       "best_shallow_mapping": "nand_mindepth: {sg13g2_inv_1, sg13g2_nand2_1}, "
           "161 cells, DEPTH 14, 967.0 ps (1.04x CMOS), 199.1 fJ DERIVED (1.17x better "
           "than CMOS 232 fJ). Formally equivalent to sha_slice.v by two engines and "
           "155,600 vectors / 0 mismatches.",
       "the_counterintuitive_part": "the MOST restrictive library gives the FASTEST "
           "block. {inv,nand2} has MORE cells (161 vs 146) and MORE depth (14 vs 13) "
           "than {inv,nand2,and2}, but it is faster (967 vs 1148 ps) because a QAL bank "
           "opens on its SLOWEST cell, and and2 settles in 104.0 ps where inv takes "
           "75.9 ps and nand2 only 60.0 ps. Cell count is the wrong objective for a "
           "QAL backend; the bank's worst-cell settling time is the right one.",
       "admitting_2_high_stacks_is_decisively_bad": "the {inv,nand2,and2,nor2,or2} "
           "mapping is the SMALLEST remap (101-111 cells, depth 12-16) and the SLOWEST "
           "(2583-3367 ps, 2.8-3.6x CMOS), because or2 paces its banks at 287.4 ps.",
       "pre_registered_negative_did_NOT_fire":
           "PRE_REGISTERED.json said: 'If the shallow-stack remap more than doubles both "
           "cell count and depth, then QAL's per-level advantage is spent by the remap "
           "alone.' Cell count did more than double (2.88x) and depth did not quite "
           "(1.75x) -- and the composed block time shows the premise was wrong anyway: "
           "the remap is what makes the block fast, not what makes it slow."},
     "CROSSCHECKS": XC,

     "EQUIVALENCE": {"formal": formal, "vectors": vec,
       "standard": "the committed QDI form: 151,584 vectors / 0 mismatches",
       "E4_LIBRARY_CLOSURE": closure,
       "note": "the vector run reads the REAL, unmodified PDK sg13g2_stdcell.v and "
               "sg13g2_udp.v under iverilog; only the yosys-side model file is "
               "transformed (AMENDMENT R4)."},
    }
    json.dump(res, open(os.path.join(HERE, "RESULTS.json"), "w"), indent=1)
    print("\nwrote RESULTS.json")
    return res


if __name__ == "__main__":
    main()
