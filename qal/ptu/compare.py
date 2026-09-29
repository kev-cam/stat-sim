#!/usr/bin/env python3
"""STEP 5-7: THE MATCHED COMPARISON, THE SEPARATION TEST, THE RE-VERDICT.

Puts the CORRECTED pulsed-inductor rows (ROWS_*.json, built here) side by side
with the committed clamp (rtu) and control (free) rows at the SAME operating
points, and judges them by the SAME pre-registered acceptance.

The clamp/control comparators are skiptu's own committed rows.  They are NOT
re-run: my own extractor reproduced every one of their worst-gate percentages
digit-for-digit from their .mt0 (see EXISTING.json), so the comparison is
like-for-like through one validated code path.
"""
import json, os, sys

sys.path.insert(0, "/usr/local/src/stat-sim/qal/skip4")
import skip as SK

HERE = os.path.dirname(os.path.abspath(__file__))
SKIPTU = "/usr/local/src/stat-sim/qal/skiptu"
SIGMA_VT_MV = 3.42       # PDK sigma-Vt, stat-sim e4c980b (qal/restore5)
VTP_ABS = 0.4403         # MEASURED |Vtp|
A2_GATE = 0.4400


def committed_rows():
    return json.load(open(os.path.join(SKIPTU, "rows.json")))


def mine():
    out = []
    for f in sorted(os.listdir(HERE)):
        if f.startswith("ROWS_") and f.endswith(".json"):
            for r in json.load(open(os.path.join(HERE, f))):
                if "error" not in r:
                    out.append(r)
    return out


def key(r):
    return (r["scheme"], r["T_ps"], r["dv"])


def sep_by_stage(r):
    """D6: HIGH/LOW separation within each stage = min(pull-up V(o)) - max(pull-down
    V(o)), in mV, at that stage's own boundary."""
    out = {}
    for k, v in r.get("settling", {}).items():
        pg = v.get("per_gate", {})
        hi = [g["v_o"] for g in pg.values() if g["kind"] == "pullup"]
        lo = [g["v_o"] for g in pg.values() if g["kind"] == "pulldown"]
        if hi and lo:
            out[str(k)] = round(1e3 * (min(hi) - max(lo)), 4)
    return out


def maxlow_by_stage(r):
    out = {}
    for k, v in r.get("settling", {}).items():
        pg = v.get("per_gate", {})
        lo = [g["v_o"] for g in pg.values() if g["kind"] == "pulldown"]
        if lo:
            out[str(k)] = round(max(lo), 6)
    return out


def rails(r):
    d = r.get("rail_by_stage_at_its_boundary_V", {})
    return {str(k): v for k, v in d.items()}


def worst(r):
    d = r.get("worst_gate_by_stage_pct", {})
    return {str(k): v for k, v in d.items()}


def a1_pass(r):
    w = worst(r)
    return bool(w) and min(v for v in w.values() if v is not None) >= 90.0


def _tu(r):
    return ((r.get("cost") or {}).get("topup") or {})


SLEW_PREP_PS = 24.0 + 4 * 2.0    # the corrected sequence's preparation: LS slew + 4*EDGE


def topup_schedule(r):
    """Does the top-up pulse -- INCLUDING the corrected sequence's preparation and
    its measured freewheel -- actually COMPLETE before the bank's stage boundary?

    This matters and it is not bookkeeping.  tucell.py's corrected gate sequence
    costs SLEW + 4*EDGE = 32 ps of preparation before the pulse even starts (the
    HS must be fully on while the LS still clamps na, or na is yanked negative --
    AMENDMENT A6).  At a short beat there may be no room for 32 ps + t_on + tfw
    between the charging hop's measured zero and the stage boundary.  A row whose
    top-up completes AFTER the boundary has not been topped up at the instant the
    settling is read, and saying so is the difference between a measurement and an
    artefact.  chain3's own A5 lesson is the same shape from the other side: a
    restoration landing close to the boundary moves the goalpost.
    """
    tu_ = (r.get("cost", {}) or {}).get("topup")
    if not tu_ or "per_bank" not in tu_:
        return None
    out = {}
    for k, v in tu_["per_bank"].items():
        tf, ton = v.get("t_fire_ps"), v.get("t_on_ps")
        tfw = v.get("t_freewheel_ps")
        bnd = (r.get("bound_ps") or {}).get(str(k), (r.get("bound_ps") or {}).get(k))
        if None in (tf, ton, tfw, bnd):
            continue
        a = tf + SLEW_PREP_PS            # pulse start
        b = a + ton                      # pulse end (HS off)
        z = b + tfw                      # OUT opens = delivery complete
        out[str(k)] = dict(t_fire_ps=round(tf, 2), pulse_start_ps=round(a, 2),
                           pulse_end_ps=round(b, 2), delivery_complete_ps=round(z, 2),
                           boundary_ps=round(bnd, 2),
                           margin_to_boundary_ps=round(bnd - z, 2),
                           COMPLETES_BEFORE_BOUNDARY=bool(z <= bnd))
    return out or None


def summarise(r, mode):
    return dict(
        mode=mode, scheme=r["scheme"], T_ps=r["T_ps"], dv=r["dv"],
        ltu_nH=r.get("ltu_nH"), t_on_ps=r.get("t_on_ps"),
        Cna_fF=r.get("Cna_fF"), deck=r.get("deck"),
        bound_ps=r.get("bound_ps"),
        worst_by_stage_pct=worst(r),
        worst_all_stages_pct=r.get("worst_gate_all_stages_pct"),
        rail_at_bound_V=rails(r),
        max_LOW_V_by_stage=maxlow_by_stage(r),
        separation_mV_by_stage=sep_by_stage(r),
        A2_min_delivered_high_V=r.get("A2_min_delivered_high_V"),
        A2_all_stages_clear=r.get("A2_all_stages_clear_0p4400"),
        A1_all_stages_90pct=a1_pass(r),
        A6_IZ_uA=(r.get("A6_instrument", {}) or {}).get("IZ_uA"),
        A6_gate=(r.get("A6_instrument", {}) or {}).get("IZ_gate_1uA"),
        topup_schedule=topup_schedule(r),
        topup_q_delivered_fC=_tu(r).get("q_delivered_total_fC"),
        topup_Qmult=_tu(r).get("charge_multiplication_Qdel_over_Qsup"),
        topup_E_gate_fJ=_tu(r).get("E_SWITCH_GATE_DRIVE_fJ"))


def main():
    com = committed_rows()
    new = mine()
    rows = [summarise(r, r["mode"]) for r in com] + \
           [summarise(r, "ptu_CORRECTED") for r in new]

    out = {"_what": "matched comparison: CORRECTED pulsed-inductor top-up vs the "
                    "committed switched-clamp (rtu) and the control (free), at the "
                    "same operating points, judged by the same acceptance.",
           "_acceptance": {
               "A1": "every gate in every stage >= 90% settled at its own boundary",
               "A2": "delivered input HIGH >= %.4f V at every stage" % A2_GATE},
           "_sigma_vt_mV": SIGMA_VT_MV,
           "_Vtp_abs_V": VTP_ABS,
           "rows": rows}

    # ---- the matched table
    print("\n=== D4/D5/D2: MATCHED per-stage settling, rail, predecessor LOW ===")
    print("%-14s %-3s %5s %4s | %-26s | %-30s | %-22s | %-6s" %
          ("mode", "sch", "T", "dv", "worst%/stage", "rail@bound V",
           "maxLOW V", "A1"))
    seen = {}
    for r in rows:
        seen.setdefault((r["scheme"], r["T_ps"], r["dv"]), []).append(r)
    for k in sorted(seen, key=lambda x: (x[0], x[2], x[1])):
        for r in sorted(seen[k], key=lambda z: z["mode"]):
            f = lambda D: " ".join("%s:%s" % (s, D[s]) for s in sorted(D))
            print("%-14s %-3s %5g %4g | %-26s | %-30s | %-22s | %-6s" %
                  (r["mode"], r["scheme"], r["T_ps"], r["dv"],
                   f(r["worst_by_stage_pct"])[:26],
                   f(r["rail_at_bound_V"])[:30],
                   f(r["max_LOW_V_by_stage"])[:22],
                   "PASS" if r["A1_all_stages_90pct"] else "FAIL"))
        print()

    # ---- D6 separation
    print("=== D6: HIGH/LOW separation by bank depth (mV), floor = sigma-Vt %.2f mV ==="
          % SIGMA_VT_MV)
    for k in sorted(seen, key=lambda x: (x[0], x[2], x[1])):
        for r in sorted(seen[k], key=lambda z: z["mode"]):
            s = r["separation_mV_by_stage"]
            flags = " ".join("%s:%s%s" % (st, s[st],
                                          "*" if abs(s[st]) < SIGMA_VT_MV else "")
                             for st in sorted(s))
            print("%-14s %-3s T=%-5g dv=%-4g | %s" %
                  (r["mode"], r["scheme"], r["T_ps"], r["dv"], flags))
        print()
    print("* = below the PDK sigma-Vt floor of %.2f mV" % SIGMA_VT_MV)

    # ---- re-verdict
    a1 = [r for r in rows if r["A1_all_stages_90pct"]]
    pt = [r for r in rows if r["mode"] == "ptu_CORRECTED"]
    out["RE_VERDICT"] = {
        "A1_any_row_all_stages_90pct": bool(a1),
        "A1_rows_passing": [r["deck"] for r in a1],
        "A1_best_worst_gate_over_ALL_rows_pct": (
            max((r["worst_all_stages_pct"] for r in rows
                 if r["worst_all_stages_pct"] is not None), default=None)),
        "A1_best_worst_gate_over_CORRECTED_PTU_rows_pct": (
            max((r["worst_all_stages_pct"] for r in pt
                 if r["worst_all_stages_pct"] is not None), default=None)),
        "A2_any_ptu_row_clears_all_stages": any(r["A2_all_stages_clear"]
                                                for r in pt),
        "n_corrected_ptu_rows": len(pt)}
    json.dump(out, open(os.path.join(HERE, "COMPARE.json"), "w"), indent=1)
    print("\n=== RE-VERDICT ===")
    print(json.dumps(out["RE_VERDICT"], indent=1))


if __name__ == "__main__":
    main()
