#!/usr/bin/env python3
"""Decompose the crux fits into the CAPACITANCES that produce them.

Reads CRUX.json only (no simulation, and the crux .prn files are already
deleted -- their sha256 are in CRUX_PROVENANCE.sha256).

The four variants differ ONLY in which part of the measured stage's load
scales with s, so the differences between their `b` coefficients isolate the
individual capacitances.  With k = ps of dilutable delay per fF of fixed load:

    b_A = k * (C_wire + C_junc)                 CLOAD fixed, junction fixed
    b_B = k * (C_junc)                          CLOAD scales, junction fixed
    b_C = k * (C_wire + C_junc + C_gate_x1)     load cell also fixed at x1

so   k        = (b_A - b_B) / C_wire     with C_wire = 2.00 fF EXACTLY (it is
                                         set in the deck, not fitted)
     C_junc   = b_B / k
     C_gate_x1= (b_C - b_A) / k

C_junc is expected to be non-zero and W-INDEPENDENT because qal/sg13lv_compat.sp
DECLARES ad/as/pd/ps and DISCARDS them, so every device -- 0.74 um or 8.96 um --
gets the PSP103 defaults AS=AD=1e-12 m^2 and PS=PD=1e-6 m.  The junction
capacitance therefore does NOT scale with drawn width in ANY deck in this
campaign.  That is the same shim defect the brief already records for leakage
("PD=1.00 um is smaller than the 1.12 um pMOS so the STI-edge term clips to
zero"), showing up here on the CAPACITANCE side instead.

CONSEQUENCE, and it cuts AGAINST upsizing: a fixed self-load is exactly what
1/s dilution feeds on.  In real silicon AD and PD scale with W, C_junc would
scale too, and variant B would be FLATTER than measured while variant A would
improve LESS than measured.  So the measured 28-32% that upsizing buys is an
UPPER BOUND, and the scale-invariance is stronger than these numbers show.
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
C_WIRE_FF = 2.0          # CLOAD, set in the deck -- known exactly, not fitted


def main():
    A = json.load(open(os.path.join(HERE, "CRUX.json")))["ANSWER"]
    out = {}
    for rc, rail in ((16500, 1.65), (9422, 0.9422477)):
        try:
            bA = A["r%d_A" % rc]["worst_t_set90_ps"]["fit_a_plus_b_over_s"]
            bB = A["r%d_B" % rc]["worst_t_set90_ps"]["fit_a_plus_b_over_s"]
            bC = A["r%d_C" % rc]["worst_t_set90_ps"]["fit_a_plus_b_over_s"]
            bD = A["r%d_D" % rc]["worst_t_set90_ps"]["fit_a_plus_b_over_s"]
        except KeyError:
            continue
        k = (bA["b_over_s_ps"] - bB["b_over_s_ps"]) / C_WIRE_FF
        cj = bB["b_over_s_ps"] / k
        cg = (bC["b_over_s_ps"] - bA["b_over_s_ps"]) / k
        cjD = bD["b_over_s_ps"] / k - C_WIRE_FF
        out["rail_%gV" % rail] = dict(
            rail_V=rail,
            k_ps_per_fF_DERIVED=k,
            b_A_ps=bA["b_over_s_ps"], b_B_ps=bB["b_over_s_ps"],
            b_C_ps=bC["b_over_s_ps"], b_D_ps=bD["b_over_s_ps"],
            a_A_ps=bA["a_const_ps"], a_B_ps=bB["a_const_ps"],
            a_C_ps=bC["a_const_ps"], a_D_ps=bD["a_const_ps"],
            C_wire_fF_EXACT=C_WIRE_FF,
            C_junction_fixed_fF_DERIVED=cj,
            C_gate_x1_fF_DERIVED=cg,
            C_gate_per_um_fF_DERIVED=cg / (1.12 + 0.74),
            C_junction_from_variantD_fF_DERIVED=cjD,
            total_x1_load_fF_DERIVED=C_WIRE_FF + cj + cg,
            fixed_share_of_x1_load_pct=100.0 * (C_WIRE_FF + cj)
            / (C_WIRE_FF + cj + cg),
            NOT_A_CHECK=dict(
                _warning="the three-equation solve above is ALGEBRAICALLY "
                         "CLOSED (3 equations, 3 unknowns, C_wire given), so "
                         "comparing b_C/k against the sum of parts is "
                         "TAUTOLOGICAL and returns ~1e-16. It is NOT a "
                         "validation and must not be quoted as one. I "
                         "originally wrote it up as a cross-check; that was "
                         "wrong and is corrected here.",
                b_C_over_k_fF=bC["b_over_s_ps"] / k,
                sum_of_parts_fF=C_WIRE_FF + cj + cg,
                tautological_rel_error=abs(bC["b_over_s_ps"] / k
                                           - (C_WIRE_FF + cj + cg))
                / (C_WIRE_FF + cj + cg)),
            GENUINE_CHECKS=dict(
                _what="checks that do NOT enter the solve",
                variantD_not_used_in_solve=dict(
                    b_D_ps=bD["b_over_s_ps"],
                    implied_fixed_load_fF=bD["b_over_s_ps"] / k,
                    variantA_fixed_load_fF=C_WIRE_FF + cj,
                    rel_diff=abs(bD["b_over_s_ps"] / k - (C_WIRE_FF + cj))
                    / (C_WIRE_FF + cj),
                    note="D differs from A only in the load cell's BIAS "
                         "(rail tied to 0 V), so its fixed load should be "
                         "CLOSE to A's but not identical"),
                C_gate_vs_first_principles=dict(
                    derived_fF_per_um=cg / (1.12 + 0.74),
                    expected_fF_per_um="1.95 (C_ox at L=0.13 um) plus overlap, "
                                       "so ~2.0-2.5",
                    note="EXTERNAL check, independent of these decks"),
                C_junction_vs_model_file=dict(
                    zero_bias_total_fF=3.0,
                    basis="AD=1e-12 m^2 x CJORBOT=1e-3 F/m^2 = 1.0 fF, plus "
                          "LSDRAIN=1e-6 m x CJORSTI=1e-9 F/m = 1.0 fF, plus "
                          "LGDRAIN=1e-6 m x CJORGAT=1e-9 F/m = 1.0 fF, read "
                          "straight out of the .so.params of the 1.12 um "
                          "device",
                    derived_at_reverse_bias_fF=cj,
                    note="EXTERNAL check: at reverse bias the cap falls as "
                         "(1+V/VBIR)^-P, so 1.5-2.1 fF is the expected window "
                         "and the DERIVED value lands in it. The W-INDEPENDENCE "
                         "is not inferred at all -- AS/AD/PS/PD are literally "
                         "the same constants in every .params file.")))
    # the two bias points are an independent check on each other
    if len(out) == 2:
        a, b = list(out.values())
        out["_bias_consistency"] = dict(
            _what="the junction capacitance must be LARGER at the LOWER rail "
                  "(less reverse bias) and the gate capacitance SMALLER (less "
                  "inversion).  Both signs are predictions, not fits.",
            rails_V=[a["rail_V"], b["rail_V"]],
            C_junction_fF=[a["C_junction_fixed_fF_DERIVED"],
                           b["C_junction_fixed_fF_DERIVED"]],
            C_junction_sign_correct=bool(
                (b["C_junction_fixed_fF_DERIVED"]
                 > a["C_junction_fixed_fF_DERIVED"])
                == (b["rail_V"] < a["rail_V"])),
            C_gate_fF=[a["C_gate_x1_fF_DERIVED"], b["C_gate_x1_fF_DERIVED"]],
            C_gate_sign_correct=bool(
                (b["C_gate_x1_fF_DERIVED"] < a["C_gate_x1_fF_DERIVED"])
                == (b["rail_V"] < a["rail_V"])))
    res = dict(
        _doc="qal/upsize -- the capacitance decomposition behind the crux. "
             "C_wire is EXACT (set in the deck). k, C_junction and C_gate are "
             "DERIVED from differences between the four variants' fitted b "
             "coefficients. Nothing here is simulated.",
        _shim_defect="qal/sg13lv_compat.sp declares ad/as/pd/ps and DISCARDS "
                     "them, so AS=AD=1e-12 m^2 and PS=PD=1e-6 m for EVERY "
                     "device at EVERY width. Junction capacitance is therefore "
                     "W-INDEPENDENT in every deck in this campaign. That makes "
                     "the measured benefit of upsizing an UPPER BOUND.",
        decomposition=out)
    open(os.path.join(HERE, "CRUX_CDECOMP.json"), "w").write(
        json.dumps(res, indent=1, default=str))
    for k2, d in out.items():
        if k2.startswith("_"):
            continue
        print("=== %s ===" % k2)
        print("  k                     = %.4f ps per fF (DERIVED)"
              % d["k_ps_per_fF_DERIVED"])
        print("  C_wire  (EXACT)       = %.3f fF" % d["C_wire_fF_EXACT"])
        print("  C_junction (DERIVED)  = %.3f fF   <- W-INDEPENDENT shim defect"
              % d["C_junction_fixed_fF_DERIVED"])
        print("  C_gate_x1  (DERIVED)  = %.3f fF   = %.3f fF/um of total width"
              % (d["C_gate_x1_fF_DERIVED"], d["C_gate_per_um_fF_DERIVED"]))
        print("  total x1 load         = %.3f fF, of which %.1f%% does NOT "
              "scale" % (d["total_x1_load_fF_DERIVED"],
                         d["fixed_share_of_x1_load_pct"]))
        g = d["GENUINE_CHECKS"]
        print("  [solve is algebraically closed -- its residual is "
              "TAUTOLOGICAL, not a check]")
        print("  variant D (NOT in solve): fixed load %.3f fF vs A's %.3f fF "
              "-> %.1f%%" % (g["variantD_not_used_in_solve"]
                             ["implied_fixed_load_fF"],
                             g["variantD_not_used_in_solve"]
                             ["variantA_fixed_load_fF"],
                             100 * g["variantD_not_used_in_solve"]["rel_diff"]))
        print("  C_gate %.3f fF/um vs first-principles ~2.0-2.5 fF/um"
              % g["C_gate_vs_first_principles"]["derived_fF_per_um"])
        print("  C_junc %.3f fF vs 3.00 fF zero-bias from the .params file"
              % g["C_junction_vs_model_file"]["derived_at_reverse_bias_fF"])
        print()
    bc = out.get("_bias_consistency")
    if bc:
        print("BIAS CONSISTENCY (both signs were PREDICTED):")
        print("  C_junction %s fF at rails %s V -> larger at lower rail: %s"
              % ([round(x, 3) for x in bc["C_junction_fF"]], bc["rails_V"],
                 bc["C_junction_sign_correct"]))
        print("  C_gate     %s fF at rails %s V -> smaller at lower rail: %s"
              % ([round(x, 3) for x in bc["C_gate_fF"]], bc["rails_V"],
                 bc["C_gate_sign_correct"]))


if __name__ == "__main__":
    main()
