#!/usr/bin/env python3
"""SKEPTIC crux analysis: fit t = a + b/s per variant, then decompose the load.

THE DECOMPOSITION, and why my cross-check is NOT tautological.

With drive conductance proportional to s and a load made of
  C_j   the cell's OWN drain junction  -- W-INDEPENDENT here, because
        qal/sg13lv_compat.sp DISCARDS ad/as/pd/ps, so AD = AS = 1e-12 m^2 at
        every width,
  C_w   the wiring load, EXACTLY 2.00 fF, set in the deck,
  C_g1  one x1 cell's gate load,
the model gives, with k = 1/G the ps-per-fF slope and t_i an intrinsic term:

  A  (cells scale, C_w fixed)   t = t_i + C_g1*k     + (C_j + C_w)*k / s
  B  (pure coscale, C_w = 2s)   t = t_i + (C_w+C_g1)*k +  C_j       *k / s
  C  (load stays x1)            t = t_i +  0         + (C_j+C_w+C_g1)*k / s

So
  b_A - b_B = C_w * k        -> k, from TWO measured slopes and an EXACT 2.00 fF
  C_j       = b_B / k
  C_g1      = (b_C - b_A) / k

and the model then PREDICTS, with nothing left to fit,

  a_B - a_A = C_w * k = b_A - b_B          <-- GENUINE cross-check

The record's write-up says its own version of this check "returns ~1e-16 and is
TAUTOLOGICAL" and corrects itself.  It is tautological only if b_C is used in
the solve.  The identity above uses the INTERCEPTS on the left and the SLOPES on
the right; both sides are measured, neither is fitted from the other, and the
model has no freedom left.  If it holds, the decomposition is real.
"""
import glob, json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
C_WIRE = 2.00
SCALES = (1.0, 2.0, 4.0, 8.0)


def fit(S, Y):
    x = [1.0 / s for s in S]
    n = len(S)
    sx, sy, sxx = sum(x), sum(Y), sum(v * v for v in x)
    sxy = sum(v * w for v, w in zip(x, Y))
    d = n * sxx - sx * sx
    b = (n * sxy - sx * sy) / d
    a = (sy - b * sx) / n
    yb = sy / n
    sst = sum((w - yb) ** 2 for w in Y)
    ssr = sum((w - (a + b * v)) ** 2 for v, w in zip(x, Y))
    return a, b, (1.0 - ssr / sst if sst else None)


def collect(rail=1.65):
    pts = {}
    for f in glob.glob(os.path.join(HERE, "ck_ck_r*.json")):
        d = json.load(open(f))
        if abs(d["rail"] - rail) > 1e-9:
            continue
        pts.setdefault(d["variant"], {})[d["scale"]] = d
    return pts


def main():
    rail = float(sys.argv[1]) if len(sys.argv) > 1 else 1.65
    pts = collect(rail)
    out = dict(_rail_V=rail, _metric="worst_t_set90_ps (MEASURED)", variants={},
               decomposition={}, cross_checks={})
    for v in sorted(pts):
        S = sorted(pts[v])
        Y = [pts[v][s]["worst_t_set90_ps"] for s in S]
        if any(y is None for y in Y) or len(S) < 3:
            out["variants"][v] = dict(scales=S, t_set90=Y, note="incomplete")
            continue
        a, b, r2 = fit(S, Y)
        lo, hi = Y[0], Y[-1]
        out["variants"][v] = dict(
            scales=S, t_set90_ps=Y, a_ps=a, b_ps=b, R2=r2,
            ratio_s8_over_s1=hi / lo, pct_change=100.0 * (hi / lo - 1.0),
            exp_in_s=(math.log(hi / lo) / math.log(S[-1] / S[0])),
            asymptote_frac_of_s1=(a / (a + b) if (a + b) else None))
    V = out["variants"]
    if all(x in V and "a_ps" in V[x] for x in ("A", "B", "C")):
        bA, bB, bC = V["A"]["b_ps"], V["B"]["b_ps"], V["C"]["b_ps"]
        aA, aB = V["A"]["a_ps"], V["B"]["a_ps"]
        k = (bA - bB) / C_WIRE
        cj = bB / k
        cg = (bC - bA) / k
        out["decomposition"] = dict(
            _solve="k from (b_A - b_B)/C_wire with C_wire EXACTLY 2.00 fF; "
                   "C_j from b_B/k; C_g1 from (b_C - b_A)/k",
            k_ps_per_fF=k, C_junction_fF=cj, C_gate_x1_fF=cg,
            C_gate_per_um_total_width=cg / 1.86,
            load_x1_total_fF=cj + C_WIRE + cg,
            frac_of_x1_load_that_does_NOT_scale=(
                (cj + C_WIRE) / (cj + C_WIRE + cg)))
        pred = C_WIRE * k
        meas = aB - aA
        out["cross_checks"]["intercepts_vs_slopes"] = dict(
            _identity="a_B - a_A must equal C_wire*k = b_A - b_B; the left side "
                      "is INTERCEPTS, the right side SLOPES, neither fitted "
                      "from the other -- this is NOT tautological",
            predicted_ps=pred, measured_ps=meas,
            rel_err=((meas - pred) / pred if pred else None),
            PASS=bool(pred and abs((meas - pred) / pred) <= 0.20))
        if "D" in V and "a_ps" in V["D"]:
            out["cross_checks"]["variant_D_outside_the_solve"] = dict(
                _what="D is not used in the solve, so its implied C_gate is a "
                      "genuine second opinion",
                C_gate_from_D_fF=(V["C"]["b_ps"] - V["D"]["b_ps"]) / k,
                C_gate_from_A_fF=cg)
        if "E" in V and "a_ps" in V["E"]:
            # E = A plus (s-1)*C_j explicit, i.e. junction forced to scale.
            # model: t = t_i + (C_j + C_g1)*k + C_w*k/s
            out["cross_checks"]["variant_E_junction_forced_to_scale"] = dict(
                _what="the control the record did NOT run: emulates AD "
                      "proportional to W, which the shim prevents",
                predicted_b_ps=C_WIRE * k, measured_b_ps=V["E"]["b_ps"],
                predicted_ratio_s8_over_s1=None,
                measured_ratio=V["E"]["ratio_s8_over_s1"],
                variant_A_ratio=V["A"]["ratio_s8_over_s1"],
                E_is_FLATTER_than_A=bool(V["E"]["ratio_s8_over_s1"]
                                         > V["A"]["ratio_s8_over_s1"]),
                verdict=("E flatter than A => the shim's W-independent junction "
                         "makes the record's 28-32%% an UPPER bound and the "
                         "invariance is STRONGER than published"
                         if V["E"]["ratio_s8_over_s1"] > V["A"]["ratio_s8_over_s1"]
                         else "E steeper than A => the record's caveat is "
                              "BACKWARDS and I must say so"))
    json.dump(out, open(os.path.join(HERE, "SK_CRUX_FIT.json"), "w"), indent=1)
    print("rail %.4f V   metric worst_t_set90_ps" % rail)
    print("%-3s %-34s %8s %8s %8s %8s %8s" %
          ("v", "t_set90 s=1/2/4/8 (ps)", "a", "b", "R2", "r8/r1", "exp"))
    for v in sorted(V):
        d = V[v]
        if "a_ps" not in d:
            print("%-3s %s  INCOMPLETE" % (v, d["t_set90"])); continue
        print("%-3s %-34s %8.3f %8.3f %8.5f %8.4f %+8.3f"
              % (v, " / ".join("%.3f" % y for y in d["t_set90_ps"]),
                 d["a_ps"], d["b_ps"], d["R2"], d["ratio_s8_over_s1"],
                 d["exp_in_s"]))
    if out["decomposition"]:
        D = out["decomposition"]
        print("\nk = %.4f ps/fF   C_j = %.4f fF   C_g1 = %.4f fF (%.4f fF/um)"
              % (D["k_ps_per_fF"], D["C_junction_fF"], D["C_gate_x1_fF"],
                 D["C_gate_per_um_total_width"]))
        print("non-scaling fraction of the x1 load = %.1f%%"
              % (100.0 * D["frac_of_x1_load_that_does_NOT_scale"]))
        X = out["cross_checks"]["intercepts_vs_slopes"]
        print("CROSS-CHECK a_B-a_A vs C_w*k : predicted %.4f measured %.4f "
              "rel %.4f PASS=%s"
              % (X["predicted_ps"], X["measured_ps"], X["rel_err"], X["PASS"]))
    print("\nwrote SK_CRUX_FIT.json")


if __name__ == "__main__":
    main()
