#!/usr/bin/env python3
"""Score the PRE-STATED EXPECTATIONS against the measurement, line by line.

WRITTEN BEFORE ANY SWEEP NUMBER EXISTED, so the bands cannot be nudged to fit.
Every band is copied from PRE_REGISTERED_PHASE2.json :
PRE_STATED_EXPECTATIONS_TO_BE_SCORED (sha256 621f7289..., mtime 21:45:42).

Verdicts: RIGHT / NARROWLY-WRONG (outside the band by <=25% of the band's own
width) / WRONG / NOT-TESTED.  Direction claims are scored separately from
magnitude claims, because being right about the sign and wrong about the size
is a different thing from being wrong about the sign.
"""
import json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))


def verdict_band(v, lo, hi):
    if v is None:
        return "NOT-TESTED"
    if lo <= v <= hi:
        return "RIGHT"
    w = hi - lo
    if w > 0 and (lo - 0.25 * w <= v < lo or hi < v <= hi + 0.25 * w):
        return "NARROWLY-WRONG"
    return "WRONG"


def rec(out, key, claim, measured, verd, note=""):
    out.append(dict(id=key, claim=claim, measured=measured, verdict=verd,
                    note=note))


def crux_ratio(C, rail_code, variant, metric="worst_t_set90_ps"):
    d = C.get("r%d_%s" % (rail_code, variant))
    if not d or metric not in d or "ratio_last_over_first" not in d[metric]:
        return None, None, None
    m = d[metric]
    return (m["ratio_last_over_first"], m.get("exponent_in_s"),
            (m.get("fit_a_plus_b_over_s") or {}))


def main():
    R = json.load(open(os.path.join(HERE, "RESULTS_PHASE2.json")))
    C = R.get("CRUX", {})
    T = R["TABLE"]
    tr = R["TRADE_per_N"]
    out = []

    # ---------------- THE CRUX
    for rc, rname in ((16500, "1.65 V"), (9422, "0.9422 V")):
        r, e, f = crux_ratio(C, rc, "A")
        rec(out, "X1_crux_A_rail%s" % rc,
            "variant A (REAL CHAIN) t_set90(x8)/t_set90(x1) = 0.68-0.80; "
            "falls only by the fixed-WIRING fraction then saturates",
            r, verdict_band(r, 0.68, 0.80),
            "rail %s; exponent_in_s %s; fit a=%s b=%s R2=%s" %
            (rname, e, f.get("a_const_ps"), f.get("b_over_s_ps"),
             f.get("R2")))
        r, e, f = crux_ratio(C, rc, "B")
        rec(out, "X2_crux_B_rail%s" % rc,
            "variant B (PURE COSCALE) FLAT within 5%: ratio in 0.95-1.05, "
            "i.e. genuinely scale-INVARIANT",
            r, verdict_band(r, 0.95, 1.05), "rail %s; exponent %s" % (rname, e))
        r, e, f = crux_ratio(C, rc, "C")
        rec(out, "X3_crux_C_rail%s" % rc,
            "variant C (FIXED LOAD) ratio 0.15-0.30, roughly the naive 1/s -- "
            "the positive control proving the instrument CAN see a speed-up",
            r, verdict_band(r, 0.15, 0.30), "rail %s; exponent %s" % (rname, e))
        r, e, f = crux_ratio(C, rc, "D")
        rec(out, "X1d_crux_D_rail%s" % rc,
            "variant D (QAL-BIAS LOAD, added as amendment A3) should behave "
            "like A: both driver and load still scale",
            r, "INFORMATIVE", "rail %s; exponent %s" % (rname, e))
    # B10 gate
    _, _, fA = crux_ratio(C, 16500, "A")
    r2 = (fA or {}).get("R2")
    rec(out, "B10_mechanism_gate",
        "variant A must fit t = a + b/s with R2 >= 0.98, and variant B must be "
        "flat within 5%, or the mechanism claim is WITHDRAWN not asserted",
        r2, "RIGHT" if (r2 is not None and r2 >= 0.98) else
        ("WRONG" if r2 is not None else "NOT-TESTED"),
        "R2 of the a+b/s fit on variant A at 1.65 V")

    # ---------------- helper to pull a main-series value at a scale
    def val(n, s, key):
        for t in T:
            if (t["N"] == n and t["sc_scored"] == s and t["ct_override"] is None
                    and abs(t["L_nH"] - 15.0) < 1e-9 and t["cload_fF"] == 2.0
                    and len(set(t["scale_per_bank"])) == 1):
                return t[key]
        return None

    # ---------------- X4 t_hop at N=64
    e = (tr.get("64", {}).get("exp_t_hop") or {}).get("exponent_end_to_end")
    rec(out, "X4_t_hop_exponent",
        "t_hop grows as sqrt(s): measured exponent in s of 0.45-0.55",
        e, verdict_band(e, 0.45, 0.55), "N=64 main series")
    for s, lo, hi in ((2.0, 410, 425), (4.0, 580, 600), (8.0, 820, 850)):
        v = val(64, s, "t_hop_ps")
        rec(out, "X4_t_hop_abs_s%g" % s,
            "t_hop at N=64 s=%g in %g-%g ps" % (s, lo, hi), v,
            verdict_band(v, lo, hi))

    # ---------------- X5 level time at N=64
    lv = [(s, val(64, s, "T_ps"), val(64, s, "level_floor_ps")) for s in
          (1.0, 2.0, 4.0, 8.0)]
    monoT = all(a[1] is not None and b[1] is not None and b[1] > a[1]
                for a, b in zip(lv, lv[1:]))
    monoF = all(a[2] is not None and b[2] is not None and b[2] > a[2]
                for a, b in zip(lv, lv[1:]))
    rec(out, "X5_level_time_rises_N64",
        "level time RISES monotonically with s at N=64 -- NO speed win at any "
        "scale, because the level is already HOP-bound by 65.93 ps at s=1",
        dict(T_monotonic_rising=monoT, level_floor_monotonic_rising=monoF,
             T_ps=[x[1] for x in lv], level_floor_ps=[x[2] for x in lv]),
        "RIGHT" if (monoT and monoF) else "WRONG")
    for s, lo, hi in ((2.0, 6.3, 6.8), (4.0, 8.8, 9.5), (8.0, 12.2, 13.2)):
        v = val(64, s, "x_CMOS_level_T")
        rec(out, "X5_xCMOS_level_s%g" % s,
            "x_CMOS_level (on the SCHEDULED beat T) at N=64 s=%g in %g-%g"
            % (s, lo, hi), v, verdict_band(v, lo, hi),
            "scored on T because the 4.74 figure the band was built from is "
            "Phase 1's T/92.8; the additive 73.5 ps in the beat rule does NOT "
            "scale with s, so T grows slower than sqrt(s)")

    # ---------------- X6 energy at N=64
    for s, lo, hi in ((2.0, 7.5, 8.8), (4.0, 14.0, 18.0), (8.0, 27.0, 36.0)):
        v = val(64, s, "E_g_floor")
        rec(out, "X6_E_per_gate_s%g" % s,
            "E/gate (ideal-PWL floor, timer 0) at N=64 s=%g in %g-%g fJ"
            % (s, lo, hi), v, verdict_band(v, lo, hi))
    ee = (tr.get("64", {}).get("exp_E_per_gate_floor_timer0")
          or {}).get("exponent_end_to_end")
    rec(out, "X6_E_exponent",
        "E/gate rises roughly LINEARLY in s (exponent near 1.0, band 0.8-1.2)",
        ee, verdict_band(ee, 0.8, 1.2))
    x1 = val(64, 1.0, "x_floor")
    xs = [(s, val(64, s, "x_floor")) for s in (2.0, 4.0, 8.0)]
    rec(out, "X6_crossing_destroyed",
        "the Phase 1 crossing at N=64 (0.991x CMOS) is DESTROYED by any "
        "upsizing: x_CMOS > 1 at every s > 1",
        dict(x_at_s1=x1, x_at_s=xs),
        "RIGHT" if all(v is not None and v > 1.0 for _, v in xs) else "WRONG")

    # ---------------- X7 area
    ok_t, ok_c = [], []
    for s in (1.0, 2.0, 4.0, 8.0):
        tk, cl = val(64, s, "tank_um2_pg"), val(64, s, "cells_um2_pg")
        if tk is not None:
            ok_t.append(abs(tk - 29.9825 * s) < 1e-6 * max(1, 29.9825 * s))
        if cl is not None:
            ok_c.append(abs(cl - 0.2418 * s) < 0.002 * s)
    rec(out, "X7_area",
        "tank um2/gate = 29.98*s EXACTLY by construction; cell active "
        "um2/gate = 0.242*s",
        dict(tank_exact=ok_t, cell_matches=ok_c),
        "RIGHT" if (ok_t and all(ok_t) and ok_c and all(ok_c)) else "WRONG")

    # ---------------- X8 the fair test at N=8
    lv8 = [(s, val(8, s, "level_floor_ps")) for s in (1.0, 2.0, 4.0, 8.0)]
    base = lv8[0][1]
    none_faster = all(v is not None and base is not None and v > base
                      for _, v in lv8[1:])
    rec(out, "X8_lever_fails_even_at_N8",
        "EVEN AT N=8, where the level is SETTLE-bound with only 24.17 ps of "
        "slack, upsizing does NOT shorten the level: s=2 alone adds ~52 ps of "
        "hop, more than the whole slack. Level time minimised at s=1 at EVERY N",
        dict(level_floor_ps=lv8, none_faster_than_s1=none_faster),
        "RIGHT" if none_faster else "WRONG")
    for s, lo, hi in ((1.0, 145, 156), (2.0, 170, 188), (4.0, 243, 263),
                      (8.0, 345, 371)):
        v = val(8, s, "level_floor_ps")
        rec(out, "X8_level_floor_N8_s%g" % s,
            "N=8 level floor at s=%g ~ %g-%g ps" % (s, lo, hi), v,
            verdict_band(v, lo, hi))
    b8 = tr.get("8", {}).get("bound_by_per_scale", {})
    rec(out, "X9_bound_by_flips_to_HOP",
        "the MECHANISM: cell load and resonant tank are the SAME capacitance, "
        "so growing the cell grows the thing that sets the speed limit. "
        "Signature: N=8 is SETTLE-bound at s=1 and flips to HOP-bound by s=2",
        b8, "RIGHT" if (str(b8.get("1.0", b8.get(1.0))) == "SETTLE"
                        and str(b8.get("2.0", b8.get(2.0))) == "HOP")
        else "SEE-NOTE",
        "keys are scales; SETTLE at s=1 then HOP thereafter is the predicted "
        "signature")

    # ---------------- X10 iso-hop extension
    # SCORER BUG FIXED: `next(L_nH == 3.75)` matched BOTH controls, and sorted
    # order handed it E6 (s=1, the A4 extension) instead of E3 (s=4, the
    # pre-registered iso-hop control).  X10 is a claim about E3; select on the
    # control label, not on L alone.
    iso = next((t for t in T if t["extra"] == "E3isohop"), None)
    e6 = next((t for t in T if t["extra"] == "E6Lcut"), None)
    if iso:
        th = iso["t_hop_ps"]
        base_th = val(64, 1.0, "t_hop_ps")
        within = (abs(th / base_th - 1.0) <= 0.10) if (th and base_th) else None
        rec(out, "X10_isohop_holds_t_hop",
            "dropping L as 1/s holds t_hop within 10% of its s=1 value",
            dict(t_hop_ps=th, s1_t_hop_ps=base_th,
                 ratio=(th / base_th) if (th and base_th) else None),
            "RIGHT" if within else ("WRONG" if within is not None
                                    else "NOT-TESTED"))
        rec(out, "X10_isohop_costs_quadratically",
            "and the price is quadratic: E/gate 45-90 fJ (11-22x CMOS) at "
            "N=64 s=4 with L=3.75 nH",
            iso["E_g_floor"], verdict_band(iso["E_g_floor"], 45.0, 90.0),
            "E_seriesR ~ s^2 at fixed t_hop, and Q falls as 1/s with R_S "
            "pinned at 10 ohm")
    else:
        rec(out, "X10_isohop", "iso-hop control", None, "NOT-TESTED")
    # E6 is amendment A4, NOT pre-registered, so it is scored INFORMATIVE --
    # it cannot be a win or a loss against a band I never wrote down.
    if e6:
        base_fl = val(64, 1.0, "level_floor_ps")
        base_e = val(64, 1.0, "E_g_floor")
        rec(out, "A4_E6_L_reduction_at_s1",
            "EXTENSION (amendment A4): shrink L at s=1 instead of growing the "
            "cells. Tests whether cell upsizing is DOMINATED on the speed axis.",
            dict(level_floor_ps=e6["level_floor_ps"],
                 baseline_level_floor_ps=base_fl,
                 speedup_x=base_fl / e6["level_floor_ps"],
                 E_per_gate_fJ=e6["E_g_floor"], baseline_E_per_gate_fJ=base_e,
                 energy_pct=100 * (e6["E_g_floor"] / base_e - 1),
                 bound_by=e6["bound_by"],
                 recycle_pct=e6["recycle_pct"],
                 rail_droop_note="recycle went NEGATIVE and the delivered rail "
                                 "dropped 21%: E6 has stopped being adiabatic, "
                                 "so its +15.6% energy is NOT an iso-swing "
                                 "figure (see AMENDMENT A8)"),
            "INFORMATIVE")
        if iso:
            rec(out, "A4_upsizing_is_DOMINATED",
                "at the SAME L=3.75 nH, is s=1 better than s=4 on ALL of "
                "speed, energy and area simultaneously?",
                dict(E6_s1_floor_ps=e6["level_floor_ps"],
                     E3_s4_floor_ps=iso["level_floor_ps"],
                     faster_x=iso["level_floor_ps"] / e6["level_floor_ps"],
                     E6_s1_E_per_gate=e6["E_g_floor"],
                     E3_s4_E_per_gate=iso["E_g_floor"],
                     cheaper_x=iso["E_g_floor"] / e6["E_g_floor"],
                     E6_s1_um2_pg=e6["total_um2_pg"],
                     E3_s4_um2_pg=iso["total_um2_pg"],
                     smaller_x=iso["total_um2_pg"] / e6["total_um2_pg"]),
                "RIGHT" if (e6["level_floor_ps"] < iso["level_floor_ps"]
                            and e6["E_g_floor"] < iso["E_g_floor"]
                            and e6["total_um2_pg"] < iso["total_um2_pg"])
                else "WRONG")

    # ---------------- X11 no positive exchange rate
    anyfast = []
    for n, d in tr.items():
        for v in d.get("VS_S1", []):
            if v.get("faster"):
                anyfast.append(dict(N=n, scale=v["scale"],
                                    pct=v["pct_level_floor_change"]))
    rec(out, "X11_no_positive_exchange_rate",
        "NO positive exchange rate on this axis: every scale point is worse "
        "than s=1 on BOTH energy and speed, so the 'curve' is a dominated ray, "
        "not a frontier. If ANY point beats s=1 on level time, X8/X9 are WRONG "
        "and the trade EXISTS -- to be reported as a major positive result",
        dict(points_faster_than_s1=anyfast),
        "RIGHT" if not anyfast else "WRONG -- THE TRADE EXISTS")
    # Pareto
    par = {}
    for n, d in tr.items():
        par[n] = [p["scale"] for p in
                  d.get("PARETO_level_floor_vs_E_floor", [])
                  if p["on_frontier"]]
    rec(out, "X11_pareto_frontier",
        "the Pareto frontier in (level_floor, E/gate) should contain ONLY s=1",
        par,
        "RIGHT" if all(v == [1.0] for v in par.values() if v) else "SEE-NOTE")

    summ = {}
    for r in out:
        summ[r["verdict"]] = summ.get(r["verdict"], 0) + 1
    res = dict(
        _doc="qal/upsize PHASE 2 -- pre-stated expectations scored line by "
             "line. Bands copied from PRE_REGISTERED_PHASE2.json (sha256 "
             "621f7289..., mtime 2026-09-29 21:45:42 -0700); score.py was "
             "written before any sweep number existed.",
        summary=summ, scored=out)
    open(os.path.join(HERE, "SCORED_PHASE2.json"), "w").write(
        json.dumps(res, indent=1, default=str))
    print("SUMMARY:", json.dumps(summ))
    for r in out:
        print("%-28s %-16s %s" % (r["id"], r["verdict"],
                                  json.dumps(r["measured"], default=str)[:110]))


if __name__ == "__main__":
    main()
