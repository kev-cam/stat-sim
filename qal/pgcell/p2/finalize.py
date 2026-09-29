#!/usr/bin/env python3
"""PHASE 2 -- assemble RESULTS_P2.json from the measured artefacts of this run."""
import json, os, subprocess, sys, collections

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
P1 = os.path.dirname(HERE)
SIB = "/usr/local/src/stat-sim/qal/sha256"
COMMITTED = "/usr/local/src/stat-sim/qal/synth/threeway/work/sha_slice.cmos.v"

sys.path.insert(0, HERE)
import census as C

C.build_dev_table()

# ------------------------------------------------------------------ censuses
NETS = [("committed", COMMITTED),
        ("pgp", OUT + "/sha_slice.pgp.v"),
        ("pgp2", OUT + "/sha_slice.pgp2.v"),
        ("pgp2c", OUT + "/sha_slice.pgp2c.v"),
        ("pgp1", OUT + "/sha_slice.pgp1.v"),
        ("pgp1c", OUT + "/sha_slice.pgp1c.v"),
        ("pgr1_naive", OUT + "/sha_slice.pgr1.v"),
        ("pgr2_naive", OUT + "/sha_slice.pgr2.v"),
        ("pgr1c_naive", OUT + "/sha_slice.pgr1c.v"),
        ("abc_pg_area", OUT + "/sha_slice.abc_pg_area.v"),
        ("abc_pg_del", OUT + "/sha_slice.abc_pg_del.v"),
        ("abc_pg_resyn2", OUT + "/sha_slice.abc_pg_resyn2.v"),
        ("abc_pgnor_resyn2", OUT + "/sha_slice.abc_pgnor_resyn2.v"),
        ("abc_nand_area", OUT + "/sha_slice.abc_nand_area.v"),
        ("abc_nand_del", OUT + "/sha_slice.abc_nand_del.v"),
        ("abc_nand_resyn2", OUT + "/sha_slice.abc_nand_resyn2.v")]
EXTRA = [HERE + "/pgcells.v", HERE + "/minicells.v"]
cen = {k: C.census(p, EXTRA) for k, p in NETS}

# -------------------------------------------- Phase 1 MEASURED per-cell rail draw
RAIL_fC = {                      # MEASURED, qal/pgcell/RAILDRAW*.json, 0.7138163 V
    "pg_mux2":        (3.16,   "MEASURED whole TG-MUX2, FIXED well, 8 vectors"),
    "sg13g2_inv_1":   (3.0865, "MEASURED sg13g2_inv_1, 2 vectors"),
    "sg13g2_mux2_1":  (10.9195, "MEASURED sg13g2_mux2_1, 8 vectors"),
    "sg13g2_xnor2_1": (8.8278, "MEASURED sg13g2_xnor2_1, 4 vectors"),
}
RAIL_DERIVED = {
    # Phase 1's own stated mechanism: a TG cell's only rail-connected devices are
    # its control inverter(s); a TG-MUX2 therefore counts as ONE inverter (MEASURED
    # to the digit: 3.16 vs 3.0865 fC) and a TG-XOR/XNOR as TWO.  The fixed-well
    # TG-XNOR2 draw was NOT metered directly, so this row is DERIVED from that
    # MEASURED mechanism, not measured.
    "pg_xor2":  (2 * 3.0865, "DERIVED from the MEASURED mechanism (2 control "
                             "inverters); the fixed-well TG-XNOR2 draw was not "
                             "metered directly"),
    "pg_xnor2": (2 * 3.0865, "DERIVED, same"),
}


def rail(c):
    tot, cov, miss = 0.0, 0, collections.Counter()
    for t, n in c["types"]:
        if t in RAIL_fC:
            tot += RAIL_fC[t][0] * n
            cov += n
        elif t in RAIL_DERIVED:
            tot += RAIL_DERIVED[t][0] * n
            cov += n
        else:
            miss[t] += n
    return {"q_rail_fC_covered_cells": round(tot, 2),
            "cells_covered": cov, "cells_total": c["cells"],
            "coverage_pct": round(100.0 * cov / c["cells"], 1),
            "cells_with_NO_measured_rail_draw": dict(miss)}


# --------------------------------------------------------------- verification
V = json.load(open(OUT + "/VERIFY.json"))
RULE = json.load(open(OUT + "/RESTORE_RULE.json"))
M2 = {m["variant"]: m for m in json.load(open(OUT + "/REMAP2_META.json"))}
M1 = {m["variant"]: m for m in json.load(open(OUT + "/REMAP_META.json"))}
BASE = {"committed": "sha_slice.cmos.v"}


def vkey(tag, path):
    return os.path.basename(path)


rows = {}
for tag, path in NETS:
    c = cen[tag]
    v = V.get(os.path.basename(path), {})
    rows[tag] = {
        "path": path,
        "cells": c["cells"], "devices": c["devices"],
        "n_nmos": c["n_nmos"], "n_pmos": c["n_pmos"],
        "W_tot_um": c["W_tot_um"],
        "depth_levels": c["depth"],
        "profile": c["profile"],
        "types": dict(c["types"]),
        "bank_profile": c["bank_profile"],
        "max_passgate_run_on_any_path": c["max_passgate_run_on_any_path"],
        "passgate_run_histogram": c["passgate_run_histogram"],
        "x_committed": {
            "cells": round(c["cells"] / cen["committed"]["cells"], 3),
            "devices": round(c["devices"] / cen["committed"]["devices"], 3),
            "W": round(c["W_tot_um"] / cen["committed"]["W_tot_um"], 3),
            "depth": round(c["depth"] / cen["committed"]["depth"], 3),
            "banks": round(c["bank_profile"]["total_banks"] /
                           cen["committed"]["bank_profile"]["total_banks"], 3),
        },
        "rail_draw_partial": rail(c),
        "VERIFY": {k: v.get(k) for k in ("E5_PORT_FIDELITY", "E1_SAT_MITER",
                                         "E2_EQUIV", "E3_VECTORS", "vectors",
                                         "mismatches", "ALL_PASS")},
    }

res = {
    "_doc": "PHASE 2 of the pass-gate cell study: remap sha_slice onto the Phase 1 "
            "TG-XOR/TG-MUX cells and price it. Pre-registration "
            "PRE_REGISTERED_P2.json (sha256 in PRE_REGISTERED_P2.sha256), written "
            "before any netlist, liberty or script of this run existed.",
    "G0_ANCHOR": {},
    "restoration_rule": RULE,
    "remap_meta_polarity_aware": M2,
    "remap_meta_naive": M1,
    "rows": rows,
}

# ----------------------------------------------------------------- G0 anchor
sib = json.load(open(SIB + "/REMAP.json"))
res["G0_ANCHOR"] = {
    "committed_census_THIS_RUN": {k: cen["committed"][k] for k in
                                  ("cells", "devices", "W_tot_um", "depth", "profile")},
    "committed_census_SIBLING_qal_sha256": {k: sib["committed"][k] for k in
                                            ("cells", "depth", "profile")},
    "types_match": dict(cen["committed"]["types"]) ==
                   {t: n for t, n in sib["committed"]["types"]},
    "AGREE": (cen["committed"]["cells"] == sib["committed"]["cells"] and
              cen["committed"]["depth"] == sib["committed"]["depth"] and
              cen["committed"]["profile"] == sib["committed"]["profile"]),
    "G0B_committed_netlist_passes_MY_formal_flow":
        V.get("sha_slice.cmos.v", {}).get("ALL_PASS"),
    "BRIEF_CORRECTION_depth": {
        "brief_says": "the committed mapped sha_slice is 56 cells, depth 10",
        "MEASURED_this_run": "56 cells, depth 8",
        "sibling_independently": "56 cells, depth 8",
        "where_10_comes_from": "the committed QAL projection counts GENERIC gates "
            "($_AND_/$_OR_/$_XOR_/$_NOT_) and 10 GENERIC levels "
            "(qal/sha256/REMAP_CONSEQUENCE.json -> committed_reference). That is "
            "not the mapped netlist's depth. Re-mapping the RTL to that generic "
            "set in this run gives 91 cells, confirming it is a different object.",
        "consequence": "every depth ratio in this file is taken against the "
            "MEASURED mapped depth 8, which is the harder comparison for the "
            "pass-gate remap, not the flattering one.",
    },
}

# ----------------------------------------------- NAND2-only cross-check
mine = cen["abc_nand_resyn2"]
mine_nobuf = {t: n for t, n in mine["types"] if t != "sg13g2_buf_1"}
res["NAND2_only_cross_check"] = {
    "sibling_qal_sha256_nand_mincell": {"cells": sib["nand_mincell"]["cells"],
                                        "depth": sib["nand_mincell"]["depth"],
                                        "types": dict(sib["nand_mincell"]["types"])},
    "mine_abc_nand_resyn2": {"cells": mine["cells"], "depth": mine["depth"],
                             "types": dict(mine["types"])},
    "mine_excluding_depth_buffers": {"cells": sum(mine_nobuf.values()),
                                     "types": mine_nobuf},
    "AGREE": (mine_nobuf == dict(sib["nand_mincell"]["types"]) and
              mine["depth"] == sib["nand_mincell"]["depth"]),
    "note": "my ABC script adds `buffer,-N,2`, which the sibling's did not; "
            "excluding those %d buffers the two runs land on the SAME 97 nand2 + "
            "41 inv at the SAME depth 19. Independent confirmation of the "
            "NAND2-only reference point."
            % dict(mine["types"]).get("sg13g2_buf_1", 0),
    "brief_estimate_check": {
        "brief_says": "NAND2-only costs ~4 cells and ~2 levels per XOR or MUX over "
                      "20 cells",
        "that_would_predict_cells": 56 - 20 + 20 * 4,
        "MEASURED": sib["nand_mincell"]["cells"],
        "verdict": "the brief's estimate UNDERSTATES the NAND2-only cost by %d "
                   "cells, because the 14 AOI/OAI cells must decompose too -- the "
                   "20 XOR/MUX cells are not the whole bill."
                   % (sib["nand_mincell"]["cells"] - (56 - 20 + 20 * 4)),
    },
}

# ------------------------------------------------- AOI/OAI decomposition answer
res["AOI_OAI_decomposition"] = {
    "committed_AOI_OAI_cells": {"sg13g2_a21oi_1": 6, "sg13g2_o21ai_1": 5,
                                "sg13g2_a21o_1": 3, "total": 14,
                                "devices": 6 * 6 + 5 * 6 + 3 * 8},
    "WHAT_I_USED": "NO NAND2 decomposition at all. The 14 AOI/OAI cells ARE the "
        "block's carry chain and majority, and both of those functions are "
        "literally 2:1 muxes:  maj(a,b,c) = (a^b) ? c : a  and  c_out = (a^b) ? "
        "c_in : a.  A transmission gate is natively a 2:1 mux, so each AOI/OAI "
        "cell is ABSORBED into one pg_mux2 rather than expanded into a NAND2 "
        "tree. The identity is PROVEN by the E1 SAT miter over all 2^48 inputs, "
        "not asserted.",
    "second_saving": "the half-sum a^b is SHARED three ways -- one pg_xor2 drives "
        "maj[i], the carry mux and the sum xor. The committed netlist recomputes "
        "that term separately in the maj cone (27 cells) and the sum cone (21 "
        "cells).",
    "structure": {
        "p[i] = a[i]^b[i]": "8 x pg_xor2 (shared)",
        "maj[i] = p[i] ? c[i] : a[i]": "8 x pg_mux2",
        "ch[i] = e[i] ? f[i] : g[i]": "8 x pg_mux2",
        "k[i+1] = p[i] ? k[i] : a[i]": "7 x pg_mux2 (k[0]=0 makes the first one a&b)",
        "sum[0] = p[0]; sum[i] = p[i]^k[i]": "7 x pg_xor2",
        "total": "38 cells, 258 devices",
    },
}


# --------------------------------------------- pre-registered prediction scoring
PR = json.load(open(HERE + "/PRE_REGISTERED_P2.json"))
cm, pg, pg1, pg1n = rows["committed"], rows["pgp"], rows["pgp1"], rows["pgr1_naive"]
res["preregistered_predictions_scored"] = {
 "P1_cells_le_45": {
   "stated": PR["PRE_STATED_PREDICTIONS_to_be_scored"]["P1_cells"],
   "MEASURED": {"pure pass-gate remap pgp": pg["cells"],
                "restored pgp1": pg1["cells"],
                "NAND2-only": res["NAND2_only_cross_check"]
                              ["sibling_qal_sha256_nand_mincell"]["cells"]},
   "VERDICT": "SPLIT. CONFIRMED for the unrestricted remap (38 <= 45) and it is "
              "far below the NAND2-only 138. REFUTED for the restored remap: "
              "pgp1 is 56 cells, exactly the committed cell count, and pgp1c is "
              "103. I predicted a bound on the wrong object -- the number that "
              "matters is the RESTORED one, and it misses my bound."},
 "P2_devices_le_300": {
   "stated": PR["PRE_STATED_PREDICTIONS_to_be_scored"]["P2_devices"],
   "MEASURED": {"pgp": pg["devices"], "pgp1": pg1["devices"],
                "pgp1c": rows["pgp1c"]["devices"], "committed": cm["devices"]},
   "VERDICT": "CONFIRMED for pgp (258) and pgp1 (294), both below both 300 and "
              "the committed 406. REFUTED for the chain-legal pgp1c (388), which "
              "is still below the committed 406 but above my stated bound."},
 "P3_depth_worse": {
   "stated": PR["PRE_STATED_PREDICTIONS_to_be_scored"]["P3_depth"],
   "MEASURED": {"committed": cm["depth_levels"], "pgp": pg["depth_levels"],
                "pgp1": pg1["depth_levels"], "pgp2": rows["pgp2"]["depth_levels"]},
   "VERDICT": "CONFIRMED, and by more than the direction alone suggests: the "
              "unrestricted remap is only 9 vs 8, but every RESTORED variant is "
              "16-19, i.e. 2.0-2.4x the committed depth. The depth cost is not "
              "in the mux ripple, it is in the restoration the ripple forces."},
 "P4_restoration_doubles_cells": {
   "stated": PR["PRE_STATED_PREDICTIONS_to_be_scored"]["P4_restoration_cost"],
   "MEASURED": {"naive pgr1 / pgp": round(pg1n["cells"] / pg["cells"], 2),
                "polarity-aware pgp1 / pgp": round(pg1["cells"] / pg["cells"], 2),
                "pgp1 devices vs committed pct":
                    round(100 * (pg1["devices"] / cm["devices"] - 1), 1),
                "pgr1 devices vs committed pct":
                    round(100 * (pg1n["devices"] / cm["devices"] - 1), 1)},
   "VERDICT": "SPLIT, and the half I got wrong is the interesting one. CONFIRMED "
              "for NAIVE restoration: 2.08x the cells and -16.3% devices vs the "
              "committed netlist, inside my +-25% band. REFUTED for the "
              "polarity-aware restoration I had not anticipated: only 1.47x the "
              "cells and -27.6% devices, outside the band on the good side. "
              "Carrying the carry in ALTERNATING polarity instead of undoing "
              "every restoring inversion is worth 23 cells and 6 levels, and I "
              "did not pre-register it."},
 "P5_formal_passes_electrical_fails": {
   "stated": PR["PRE_STATED_PREDICTIONS_to_be_scored"]["P5_verdict"],
   "MEASURED": {"all 16 netlists E1+E2+E3+E5": all(
                   r["VERIFY"]["ALL_PASS"] for r in rows.values()),
                "vectors": pg["VERIFY"]["vectors"],
                "N_VAL_fixed_well": RULE["N_VAL"],
                "pure remap max pass-gate run": pg["max_passgate_run_on_any_path"]},
   "VERDICT": "CONFIRMED on both halves. Every variant passes SAT over all 2^48 "
              "inputs, the independent equiv_induct engine, port fidelity and "
              "155,600 vectors with 0 mismatches. And the pure remap needs a "
              "9-deep pass-gate run where the measured budget is 1 (rail well) "
              "or 0 (fixed well)."},
}

# ------------------------------------------------------------ admission verdict
res["ADMISSION_VERDICT"] = {
 "rule": "N_VAL = %d (fixed well) / 1 (rail well); N_SEP = %d"
         % (RULE["N_VAL"], RULE["N_SEP"]),
 "fixed_well": "CLOSED. N_VAL = 0 means the measured fixed-well chain delivers "
               "ZERO value-correct pass-gate levels, and any pass-gate remap "
               "contains at least one. No pass-gate mapping of sha_slice is "
               "admissible in that tie, at any cell count.",
 "rail_well": "ADMITS pgp1 / pgp1c, the only variants whose measured "
              "max-pass-gate-run on any path is 1. Cost against the committed "
              "netlist: %s cells, %s devices, %s depth, %s banks."
              % (pg1["x_committed"]["cells"], pg1["x_committed"]["devices"],
                 pg1["x_committed"]["depth"], pg1["x_committed"]["banks"]),
 "separation_budget_N_SEP_2": "admits pgp2 (48 cells, 278 devices, depth 16) but "
              "N_SEP is NOT the binding rule -- ALT_vhi bank 2 sits at 8.6x the "
              "floor and is still value-wrong. Reported for completeness only.",
 "unmeasured_gap": "Phase 1 measured HOMOGENEOUS banks (all-inv or all-tg). Every "
              "restored variant here produces levels containing BOTH pass-gate "
              "cells and inverters. A MIXED bank was never measured, so the "
              "admission of pgp1 rests on a configuration adjacent to, not "
              "identical to, the one that was characterised. That gap is not "
              "closed by this phase.",
 "mixed_levels": {t: rows[t]["bank_profile"]["n_levels_MIXED"] for t in
                  ("pgp", "pgp1", "pgp1c", "pgp2")},
}


# ------------------------------- head-to-head: the two RULE-COMPLIANT remaps
sib_nand = sib["nand_mincell"]
INV_fC = RAIL_fC["sg13g2_inv_1"][0]
cmr = rows["committed"]["rail_draw_partial"]
n_unmet = cmr["cells_total"] - cmr["cells_covered"]
res["HEAD_TO_HEAD_rule_compliant"] = {
 "_doc": "Both of these satisfy the shallow-stack requirement AND the Phase 1 "
         "pass-gate run-length rule. The committed netlist satisfies neither: it "
         "carries 5 o21ai + 5 nor2 + 6 a21oi + 3 a21o with 2-high pull-up stacks. "
         "This is the comparison the brief asked the two sibling runs to bound.",
 "rows": {
   "passgate_chain_legal_pgp1c": {k: rows["pgp1c"][k] for k in
      ("cells", "devices", "W_tot_um", "depth_levels")},
   "NAND2_only_sibling_nand_mincell": {"cells": sib_nand["cells"], "devices": 470,
      "W_tot_um": 437.1, "depth_levels": sib_nand["depth"],
      "source": "qal/sha256/REMAP_CONSEQUENCE.json, the sibling run's MEASUREMENT"},
   "NAND2_only_mine_abc_nand_resyn2": {k: rows["abc_nand_resyn2"][k] for k in
      ("cells", "devices", "W_tot_um", "depth_levels")},
 },
 "passgate_vs_NAND2_sibling": {
   "cells": round(rows["pgp1c"]["cells"] / sib_nand["cells"], 3),
   "devices": round(rows["pgp1c"]["devices"] / 470.0, 3),
   "W": round(rows["pgp1c"]["W_tot_um"] / 437.1, 3),
   "depth": round(rows["pgp1c"]["depth_levels"] / float(sib_nand["depth"]), 3)},
 "passgate_vs_NAND2_mine": {
   "cells": round(rows["pgp1c"]["cells"] / rows["abc_nand_resyn2"]["cells"], 3),
   "devices": round(rows["pgp1c"]["devices"] / rows["abc_nand_resyn2"]["devices"], 3),
   "W": round(rows["pgp1c"]["W_tot_um"] / rows["abc_nand_resyn2"]["W_tot_um"], 3),
   "depth": round(rows["pgp1c"]["depth_levels"] /
                  float(rows["abc_nand_resyn2"]["depth_levels"]), 3)},
 "VERDICT": "At IDENTICAL depth 19, the chain-legal pass-gate remap is 0.75x the "
            "cells and 0.83x the devices of the sibling's NAND2-only mapping "
            "(0.67x / 0.73x against my own). Among SHALLOW-STACK remaps the "
            "pass-gate route wins on every axis. Against the COMMITTED deep-stack "
            "netlist it is device-neutral (0.96x) and 2.38x deeper -- the "
            "pass-gate cells' device saving is eaten almost exactly by the "
            "restoring inverters the measured rule forces.",
}

res["rail_draw_notes"] = {
 "_doc": "Phase 1 metered only 4 of the cell types that appear here. Coverage is "
         "reported per row and no uncovered cell is imputed a value in the "
         "q_rail_fC column.",
 "MEASURED_per_cell_fC": {k: v[0] for k, v in RAIL_fC.items()},
 "DERIVED_per_cell_fC": {k: round(v[0], 4) for k, v in RAIL_DERIVED.items()},
 "committed_is_only_%d_pct_covered" % int(cmr["coverage_pct"]): {
   "q_rail_from_covered_cells_fC": cmr["q_rail_fC_covered_cells"],
   "cells_covered": cmr["cells_covered"], "cells_total": cmr["cells_total"],
   "uncovered": cmr["cells_with_NO_measured_rail_draw"]},
 "STRICTLY_MEASURED_statement": "the ENTIRE pure pass-gate remap draws %.1f fC "
   "from the bank rail (100%% of its 38 cells metered or mechanism-derived), "
   "which is already BELOW the %.1f fC that %d of the committed netlist's 56 "
   "cells draw on their own. The committed block's full draw is strictly greater "
   "than %.1f fC and was not measured."
   % (rows["pgp"]["rail_draw_partial"]["q_rail_fC_covered_cells"],
      cmr["q_rail_fC_covered_cells"], cmr["cells_covered"],
      cmr["q_rail_fC_covered_cells"]),
 "ASSUMED_floor_for_the_committed_block": {
   "assumption": "each of the %d unmetered committed cells draws AT LEAST one "
                 "sg13g2_inv_1 (%.4f fC) -- they all have 4-8 devices against the "
                 "inverter's 2, so this is a floor, but it is an ASSUMPTION and "
                 "not a measurement" % (n_unmet, INV_fC),
   "committed_floor_fC": round(cmr["q_rail_fC_covered_cells"] + n_unmet * INV_fC, 1),
   "comparison_against_that_floor": {t: {
       "q_rail_fC": rows[t]["rail_draw_partial"]["q_rail_fC_covered_cells"],
       "vs_committed_floor": round(
           rows[t]["rail_draw_partial"]["q_rail_fC_covered_cells"] /
           (cmr["q_rail_fC_covered_cells"] + n_unmet * INV_fC), 3),
       "BELOW_the_floor": bool(
           rows[t]["rail_draw_partial"]["q_rail_fC_covered_cells"] <
           cmr["q_rail_fC_covered_cells"] + n_unmet * INV_fC)}
     for t in ("pgp", "pgp2", "pgp1", "pgp2c", "pgp1c")},
   "consequence": "THE RAIL-DRAW ADVANTAGE DOES NOT SURVIVE THE RESTORATION. The "
                  "unrestricted remap (165.3 fC) and the input-restored pgp1 "
                  "(220.8 fC) are well under the committed block's assumed floor "
                  "of 292.9 fC, but the CHAIN-LEGAL pgp1c is 365.9 fC -- 1.25x "
                  "that floor. The 65 restoring inverters cost 200.6 fC, which is "
                  "more than the entire pass-gate saving. I had this backwards on "
                  "the first pass of this file and caught it by computing the "
                  "comparison instead of asserting it."},
}

json.dump(res, open(OUT + "/RESULTS_P2.json", "w"), indent=1)

# -------------------------------------------------------------------- report
hdr = ("%-18s %5s %6s %8s %6s %6s %6s  %-5s %s" %
       ("variant", "cells", "dev", "W(um)", "depth", "banks", "runTG", "FORMAL", "xCommitted c/d/dep"))
print(hdr)
print("-" * len(hdr))
for tag, _ in NETS:
    r = rows[tag]
    print("%-18s %5d %6d %8.2f %6d %6d %6d  %-5s %.2f/%.2f/%.2f" % (
        tag, r["cells"], r["devices"], r["W_tot_um"], r["depth_levels"],
        r["bank_profile"]["total_banks"],
        r["max_passgate_run_on_any_path"],
        r["VERIFY"].get("ALL_PASS"),
        r["x_committed"]["cells"], r["x_committed"]["devices"],
        r["x_committed"]["depth"]))
print("\nG0 anchor AGREE with sibling census:", res["G0_ANCHOR"]["AGREE"],
      "| committed passes my formal flow:",
      res["G0_ANCHOR"]["G0B_committed_netlist_passes_MY_formal_flow"])
print("NAND2-only cross-check AGREE:", res["NAND2_only_cross_check"]["AGREE"])
print("N_SEP =", RULE["N_SEP"], " N_VAL =", RULE["N_VAL"])
print()
print("%-18s %10s %8s %6s  %s" % ("variant","q_rail fC","cover%","mixedL","banks/level"))
for tag,_ in NETS:
    r=rows[tag]; rd=r["rail_draw_partial"]
    print("%-18s %10.1f %8.1f %6d  %s" % (tag, rd["q_rail_fC_covered_cells"],
          rd["coverage_pct"], r["bank_profile"]["n_levels_MIXED"],
          r["bank_profile"]["banks_per_level"]))
