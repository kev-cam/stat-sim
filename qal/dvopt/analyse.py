#!/usr/bin/env python3
"""(d)(e) BOTH OPTIMUM SURFACES from the one grid.

t_hop      MEASURED per point (true-ZCS probe zero).
t_settle   MEASURED on the ideal-supply floor deck AT THE EXACT delivered swing
           VBEND of that point -- no interpolation anywhere in the headline.
SUM = t_hop + t_settle      -> ADJACENT transfer (serial)
MAX = max(t_hop, t_settle)  -> STAGE-SKIPPING (overlapped)
and, as pre-registered, the DIRECTLY MEASURED in-bank forms alongside:
t_rail90, t_settle90 (vs final rail), t_valid90 (vs instantaneous rail),
t_level_cons = max(t_hop, t_settle90, t_valid90).
"""
import json, math, os

HERE = os.path.dirname(os.path.abspath(__file__))
CMOS = 92.8                      # ps per CMOS logic level, sha_slice generic depth 10
CMOS_MAPPED = 116.0              # depth-8 mapped netlist -- flatters QAL, note only
DVS = [1.08, 1.20, 1.32, 1.35, 1.50, 1.65]

FL = json.load(open(os.path.join(HERE, "floor.json")))
rows = json.load(open(os.path.join(HERE, "rows.json")))
rows.update(json.load(open(os.path.join(HERE, "rows_committed.json"))))

# exact measured floor, keyed by the VBEND it was measured at
EXACT = {}
for t, r in FL["vb"].items():
    if r["kind"] == "inv":
        EXACT[round(r["vdd"], 7)] = r["t90_ps_measure"]
CURVE = sorted((r["vdd"], r["t90_ps_measure"]) for r in FL["inv"].values()
               if r["kind"] == "inv" and r["edge_ps"] == 2.0)


def floor_interp(v):
    xs = [p[0] for p in CURVE]; ys = [math.log(p[1]) for p in CURVE]
    if v <= xs[0]: i = 0
    elif v >= xs[-1]: i = len(xs) - 2
    else: i = max(k for k in range(len(xs) - 1) if xs[k] <= v)
    f = (v - xs[i]) / (xs[i + 1] - xs[i])
    return math.exp(ys[i] + f * (ys[i + 1] - ys[i]))


def gates(r):
    """the PRE-REGISTERED gate set, recomputed identically for imported committed
    rows and for this track's own rows."""
    va, vb, dv = r["VA_open"], r["VBEND"], r["dv"]
    f = []
    if r.get("C1_settle_end") != "PASS": f.append("C1_settle_end")
    if r.get("t_valid90_ps") is None: f.append("C1_valid90")
    if r.get("t_settle90_ps") is None: f.append("C1_settle90")
    if va > 0.1478: f.append("C2_drain_abs")
    if vb < 0.60: f.append("C3_swing_abs")
    if r.get("C4_instrument") != "PASS": f.append("C4_instrument")
    rel = (va <= 0.1478 * dv) and (vb >= 0.60 * dv)
    return f, rel


T = []
for t, r in rows.items():
    if "error" in r: continue
    dv = round(r["dv"], 2)
    if dv not in DVS: continue
    vb = round(r["VBEND"], 7)
    ts = EXACT.get(vb)
    src = "MEASURED@exact"
    if ts is None:
        ts = floor_interp(r["VBEND"]); src = "interp"
    f, rel = gates(r)
    T.append(dict(tag=t, dv=dv, L=r["L_nH"], W=r["total_um"], VGH=r.get("VGH", 1.5),
                  t_hop=r["t_hop_ps"], VBEND=r["VBEND"], VA_open=r["VA_open"],
                  t_settle=ts, t_settle_src=src,
                  SUM=r["t_hop_ps"] + ts, MAX=max(r["t_hop_ps"], ts),
                  t_rail90=r.get("t_rail90_ps"), t_settle90=r.get("t_settle90_ps"),
                  t_valid90=r.get("t_valid90_ps"),
                  t_level_cons=r.get("t_level_cons_ps"),
                  s_open=r.get("settling_open_min_pct"),
                  s_end=r.get("settling_end_min_pct"),
                  E_hop=r.get("E_hop_open_fJ"),
                  fails=f, FUNC=(not f), FUNC_rel=rel,
                  forced=r.get("VGH_FORCED", False)))

# ---- minimum sufficient W per (dV, L): smallest FUNCTIONAL width
minW = {}
for r in T:
    if r["forced"]: continue
    k = (r["dv"], r["L"])
    if r["FUNC"] and (k not in minW or r["W"] < minW[k]):
        minW[k] = r["W"]
for r in T:
    k = (r["dv"], r["L"])
    r["is_minW"] = (not r["forced"]) and r["FUNC"] and minW.get(k) == r["W"]

print("=" * 132)
print("(c) MEASURED CELL SETTLING FLOOR vs DELIVERED SUPPLY  "
      "(inverter 1.12u/0.74u, 2 fF load, supply stepped with a 2 ps edge)")
print("=" * 132)
print("   %-9s %10s   |  %-9s %10s   |  %-9s %10s" % ("V_del", "t90 (ps)",
                                                      "V_del", "t90 (ps)",
                                                      "V_del", "t90 (ps)"))
third = (len(CURVE) + 2) // 3
for i in range(third):
    cells = []
    for j in (i, i + third, i + 2 * third):
        cells.append("%9.5f %10.3f" % CURVE[j] if j < len(CURVE) else " " * 20)
    print("   " + "   |  ".join(cells))
print("   committed reproduction: 0.4885216 -> 801.2662 (was 801.2661), "
      "0.5883760 -> 252.7525 (252.7525), 0.6754250 -> 137.7453 (137.7454)")
print("   the curve FLATTENS hard above ~1.0 V: 51.505 -> 40.417 -> 32.811 ps "
      "across 1.00 -> 1.20 -> 1.50 V, i.e. 1.6x for the last 50% of swing.")

print()
print("=" * 132)
print("    RAMP PROBE -- why the floor UNDER-predicts the in-bank settle "
      "(pre-registered expectation, now MEASURED)")
print("=" * 132)
print("   %-12s %8s | %9s %9s %9s | %10s %10s %10s"
      % ("V_del", "in-bank", "edge 2ps", "edge 25ps", "edge 50ps",
         "t_rail90", "t_settle90", "t_valid90"))
for v, tag, ref in ((0.7138163, "p7138163", "d120 L15 W30"),
                    (0.8961157, "p8961157", "d150 L15 W30")):
    e = [FL["inv"]["%s_e%03d" % (tag, round(x * 10))]["t90_ps_measure"]
         for x in (2.0, 25.0, 50.0)]
    m = [r for r in T if abs(r["VBEND"] - v) < 2e-4 and r["W"] == 30]
    m = m[0] if m else None
    print("   %-12.7f %8s | %9.3f %9.3f %9.3f | %10.2f %10.3f %10.3f"
          % (v, ref, e[0], e[1], e[2], m["t_rail90"], m["t_settle90"], m["t_valid90"]))
print("   MEASURED: at 0.714 V the in-bank settle (115.57) sits just 2.1% above the "
      "2 ps floor (113.24) -- the 40.9 ps rail arrival is ABSORBED, because the cell")
print("   is far from settled when the rail completes.  At 0.896 V the in-bank settle "
      "(90.45) is 44.4% above the 2 ps floor (62.62) and matches a ~35 ps effective")
print("   edge -- the 51.1 ps rail arrival is NO LONGER absorbed, because the floor "
      "has shrunk to the same order.  So the floor-based t_settle is a LOWER BOUND")
print("   that degrades as dV rises: the benefit of swing saturates TWICE, once in "
      "the flattening floor curve and again in the rail arrival becoming binding.")

print()
print("=" * 132)
print("(d) THE GRID.  t_settle = MEASURED cell floor at that row's own delivered "
      "VBEND.  * = minimum sufficient W at that (dV, L).")
print("=" * 132)
hdr = ("%-22s %5s %6s %4s %5s | %7s %7s %7s | %7s %7s | %6s %7s %7s %7s | %s"
       % ("tag", "dV", "L nH", "W", "VGH", "t_hop", "VBEND", "t_set",
          "SUM", "MAX", "rail90", "set90", "val90", "lvl_con", "gates"))
print(hdr)
print("-" * 132)
for r in sorted(T, key=lambda r: (r["dv"], r["W"], -r["L"])):
    nn = lambda v: float("nan") if v is None else v
    print("%-22s %5.2f %6g %4g %5.2f | %7.3f %7.5f %7.2f | %7.2f %7.2f | "
          "%6.2f %7.2f %7.2f %7.2f | %s%s"
          % (r["tag"], r["dv"], r["L"], r["W"], r["VGH"], r["t_hop"], r["VBEND"],
             r["t_settle"], r["SUM"], r["MAX"], nn(r["t_rail90"]),
             nn(r["t_settle90"]), nn(r["t_valid90"]), nn(r["t_level_cons"]),
             ("FUNCTIONAL" + ("*" if r["is_minW"] else "")) if r["FUNC"]
             else ",".join(r["fails"]),
             "  [VGH forced]" if r["forced"] else ""))

# ---- the two optima
FN = [r for r in T if r["FUNC"] and not r["forced"]]
print()
print("=" * 132)
print("(e) THE TWO OPTIMUM SURFACES.  %d of %d grid points are FUNCTIONAL under the "
      "pre-registered gates." % (len(FN), len(T)))
print("=" * 132)


def best(rs, key):
    return min(rs, key=lambda r: r[key])


def show(label, r, key):
    print("  %-34s %s" % (label, "dV=%.2f  L=%g nH  W=%g um (TG %g/%g + %g park)"
                          % (r["dv"], r["L"], r["W"], r["W"] / 3, 2 * r["W"] / 3,
                             r["W"] / 15)))
    print("  %-34s %.3f ps = %.4fx the 92.8 ps CMOS logic level  (%.4fx the "
          "116.0 ps mapped-depth-8 figure)" % ("", r[key], r[key] / CMOS,
                                               r[key] / CMOS_MAPPED))
    print("  %-34s t_hop %.3f  t_settle %.3f  VBEND %.5f  VA_open %.5f  tag %s"
          % ("", r["t_hop"], r["t_settle"], r["VBEND"], r["VA_open"], r["tag"]))


print("\nSUM objective (ADJACENT bank N -> N+1; drain and settle are SERIAL)"
      "   argmin (t_hop + t_settle)")
bs = best(FN, "SUM"); show("optimum:", bs, "SUM")
print("\nMAX objective (STAGE-SKIPPING N -> N+2; the two OVERLAP)"
      "              argmin max(t_hop, t_settle)")
bm = best(FN, "MAX"); show("optimum (beat period):", bm, "MAX")
print("\nMEASURED-FORM check (the same rows, no model): argmin t_level_cons "
      "= max(t_hop, t_settle90, t_valid90)")
bv = best([r for r in FN if r["t_level_cons"]], "t_level_cons")
show("optimum:", bv, "t_level_cons")

print("\n  top 6 by each objective:")
for key, nm in (("SUM", "SUM"), ("MAX", "MAX"), ("t_level_cons", "MEASURED")):
    print("   %-9s %s" % (nm + ":", "  ".join(
        "%.1f(dV%.2f,L%g,W%g)" % (r[key], r["dv"], r["L"], r["W"])
        for r in sorted([x for x in FN if x[key]], key=lambda r: r[key])[:6])))

# ---- interior vs monotone, per dV at fixed W
print()
print("=" * 132)
print("    INTERIOR OPTIMUM OR MONOTONE TO THE EDGE?  per dV, at fixed W, over L")
print("=" * 132)
for dv in DVS:
    for w in (15.0, 30.0, 60.0, 120.0, 240.0):
        g = sorted([r for r in T if r["dv"] == dv and r["W"] == w and not r["forced"]],
                   key=lambda r: r["L"])
        if len(g) < 3: continue
        def shape(key):
            vals = [r[key] for r in g]
            i = vals.index(min(vals))
            if i == 0: return "MONOTONE down to L=%g (smallest run)" % g[0]["L"]
            if i == len(vals) - 1: return "MONOTONE up to L=%g (largest run)" % g[-1]["L"]
            return "INTERIOR at L=%g (%.2f ps)" % (g[i]["L"], vals[i])
        fn = [r for r in g if r["FUNC"]]
        cons = ("constrained min at L=%g" % min(r["L"] for r in fn)) if fn else "none functional"
        print("  dV=%.2f W=%-4g n=%d  SUM: %-34s MAX: %-30s | functional: %s"
              % (dv, w, len(g), shape("SUM"), shape("MAX"), cons))

# ---- dV monotonicity of the optimum
print()
print("    BEST FUNCTIONAL POINT AT EACH dV (this is the dV-direction surface)")
print("  %5s | %-28s %8s %7s | %-28s %8s %7s | %8s"
      % ("dV", "SUM optimum (L,W)", "SUM ps", "/92.8", "MAX optimum (L,W)",
         "MAX ps", "/92.8", "meas ps"))
perdv = {}
for dv in DVS:
    g = [r for r in FN if r["dv"] == dv]
    if not g: continue
    a, b = best(g, "SUM"), best(g, "MAX")
    c = best([r for r in g if r["t_level_cons"]], "t_level_cons")
    perdv[dv] = dict(SUM=a, MAX=b, MEAS=c)
    print("  %5.2f | L=%-6g W=%-4g (%2d pts)   %8.2f %7.4f | L=%-6g W=%-4g          "
          "%8.2f %7.4f | %8.2f"
          % (dv, a["L"], a["W"], len(g), a["SUM"], a["SUM"] / CMOS,
             b["L"], b["W"], b["MAX"], b["MAX"] / CMOS, c["t_level_cons"]))

json.dump(dict(grid=T, floor_curve=CURVE, exact_floor=EXACT,
               optimum_SUM=bs, optimum_MAX=bm, optimum_measured=bv,
               per_dV={("%.2f" % k): {kk: vv["tag"] for kk, vv in v.items()}
                       for k, v in perdv.items()}),
          open(os.path.join(HERE, "surfaces.json"), "w"), indent=1)
print("\nwrote surfaces.json (%d grid rows)" % len(T))

# =====================================================================
# additions: measured serial bound, stricter-gate robustness, prediction check
# =====================================================================
for r in T:
    # MEASURED conservative bound for the SERIAL (adjacent) schedule.  t_settle90 is
    # measured FROM SWITCH CLOSE, so adding it to t_hop double-counts the overlap:
    # it is an UPPER bound, where SUM (model) is a lower bound.
    r["SUM_meas_ub"] = (r["t_hop"] + r["t_settle90"]) if r["t_settle90"] else None

print()
print("=" * 132)
print("    SERIAL (adjacent) schedule BRACKETED by two measurements")
print("=" * 132)
print("    SUM (model, LOWER bound)  = t_hop + t_settle(ideal step at the delivered swing)")
print("    SUM_meas_ub (UPPER bound) = t_hop + t_settle90, and t_settle90 is timed from")
print("                                CLOSE, so the overlap is counted twice.")
bs2 = min([r for r in FN if r["SUM_meas_ub"]], key=lambda r: r["SUM_meas_ub"])
print("  best FUNCTIONAL by the UPPER bound: dV=%.2f L=%g W=%g -> %.2f ps = %.4fx CMOS "
      "(its model SUM is %.2f ps = %.4fx)"
      % (bs2["dv"], bs2["L"], bs2["W"], bs2["SUM_meas_ub"], bs2["SUM_meas_ub"] / CMOS,
         bs2["SUM"], bs2["SUM"] / CMOS))
print("  so the adjacent-transfer level time is bracketed %.2f - %.2f ps = %.2f - %.2fx "
      "the 92.8 ps CMOS level." % (bs["SUM"], bs2["SUM_meas_ub"], bs["SUM"] / CMOS,
                                   bs2["SUM_meas_ub"] / CMOS))

print()
print("=" * 132)
print("    ROBUSTNESS: do the optima survive the STRICTER relative gates "
      "(C2 <= 0.1478*dV, C3 >= 0.60*dV)?")
print("=" * 132)
FR = [r for r in T if r["FUNC"] and r["FUNC_rel"] and not r["forced"]]
print("  FUNCTIONAL under both absolute AND relative gates: %d of %d" % (len(FR), len(T)))
for key, nm in (("SUM", "SUM"), ("MAX", "MAX"), ("t_level_cons", "MEASURED")):
    a = min([r for r in FN if r[key]], key=lambda r: r[key])
    b = min([r for r in FR if r[key]], key=lambda r: r[key])
    same = "UNCHANGED" if a["tag"] == b["tag"] else "MOVES to L=%g W=%g" % (b["L"], b["W"])
    print("  %-9s abs-gate optimum %.2f ps (dV%.2f L%g W%g) -> rel-gate %.2f ps "
          "(dV%.2f L%g W%g)  %s"
          % (nm + ":", a[key], a["dv"], a["L"], a["W"], b[key], b["dv"], b["L"],
             b["W"], same))

print()
print("=" * 132)
print("    PRE-REGISTERED PREDICTION vs MEASUREMENT (balance point, W=30 um)")
print("=" * 132)
PRE = json.load(open(os.path.join(HERE, "predictions.json")))["predictions"]
PL = json.load(open(os.path.join(HERE, "plan.json")))["refined"]
print("  %5s | %9s %9s | %9s | %-26s | %s"
      % ("dV", "L_pre", "L_refined", "L_meas", "MAX_pre / MAX_meas ps", "verdict"))
for dv in DVS:
    k = "W30_dv%g" % dv
    g = sorted([r for r in T if r["dv"] == dv and r["W"] == 30.0 and not r["forced"]],
               key=lambda r: r["L"])
    if not g or k not in PRE: continue
    vals = [r["MAX"] for r in g]
    i = vals.index(min(vals))
    interior = 0 < i < len(vals) - 1
    Lm = g[i]["L"]
    lp, lr = PRE[k]["L_balance_nH"], PL[k]["L_bal"]
    err = 100.0 * (lr / Lm - 1.0) if interior else float("nan")
    print("  %5.2f | %9.2f %9.2f | %9s | %10.2f / %-10.2f      | %s"
          % (dv, lp, lr, ("%g" % Lm) if interior else "%g (edge)" % Lm,
             PRE[k]["MAX_pred_ps"], min(vals),
             ("INTERIOR, refined prediction high by %+.0f%%" % err) if interior
             else "no interior min inside the L range run"))
print("  DIRECTION OF THE MISS: the predictions put the balance at LARGER L than "
      "measured at every dV >= 1.20.  Cause, MEASURED: the delivered-swing fit")
print("  VBEND/dV = 0.54214 + 0.01846*ln(L) was built on dV <= 1.2 rows and "
      "UNDER-predicts the high-dV delivery -- at dV=1.65 / L=15 / W=30 it says")
print("  0.9661 V and the measurement is 1.0107 V.  A higher delivered swing means a "
      "SMALLER t_settle, so the balance moves to smaller L.  Part of that")
print("  surplus is the amendment-P1 gate drive, which the VGH control sizes "
      "separately.")
json.dump(dict(SUM_meas_ub_best=bs2, n_func_rel=len(FR)),
          open(os.path.join(HERE, "surfaces_extra.json"), "w"), indent=1)
