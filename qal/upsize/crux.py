#!/usr/bin/env python3
"""THE CRUX: does t_settle fall at all when the driver AND its load both scale?

Reads the cell-chain .prn files written by up.py stage_cellchain and answers
(a) before anything else, as the brief demands.

WHY A DEDICATED INSTRUMENT.  In the 3-bank chain, t_settle is measured from the
bank's own rail start and is therefore RAIL-DELIVERY-BOUND: a cell cannot reach
90% of its rail until the resonant hop has delivered that rail.  Phase 1
MEASURED t_settle_after_hop = -65.93 ps at N=64, i.e. the gates are finished
66 ps BEFORE the rail is.  So the chain rows can say whether the LEVEL moves;
they cannot isolate the cell's drive-into-load time.  This file does that, at a
FIXED rail, and its numbers are labelled CELL-LEVEL and are NEVER quoted as a
chain result.

MEASURED per point, on STAGE 3 of a 5-stage chain (so its input edge is
cell-generated and its load is a real cell):
  * t_pd50   : 50%-crossing delay V(s2)->V(s3), both edges
  * t_set90  : from the instant V(s2) crosses the fcrit trip to the instant
               V(s3) is >=90% settled, both edges.  This is the analogue of the
               chain's t_settle90 and the primary crux number.
  * t_func   : from the same input-trip instant to the instant V(s3) has
               crossed the fcrit trip in the correct direction (deterministic
               budget, 0 mV -- the standing correction: 3*sigma_trip
               double-counts mismatch when mismatch is not being drawn)
"""
import glob, json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, "/usr/local/src/stat-sim/qal/fcrit")
import up
import rescore as FC                      # committed, UNMODIFIED

TRIP = FC.Trip("/usr/local/src/stat-sim/qal/fcrit/TRIP.json", "S")
MEAS = up.STG_MEAS                        # 3


def cross(ts, vs, lvl, rising, t_from=None):
    """MEASURED: first linearly-interpolated crossing of lvl in the given
    direction at or after t_from."""
    for i in range(1, len(ts)):
        if t_from is not None and ts[i] < t_from:
            continue
        a, b = vs[i - 1], vs[i]
        if rising and a < lvl <= b:
            return ts[i - 1] + (lvl - a) * (ts[i] - ts[i - 1]) / (b - a)
        if (not rising) and a > lvl >= b:
            return ts[i - 1] + (lvl - a) * (ts[i] - ts[i - 1]) / (b - a)
    return None


def settle_instant(ts, vs, rail, to_hi, t_from, t_to):
    """MEASURED: first instant in [t_from, t_to] that the node is >=90%
    settled, using the committed convention (pull-UP: V >= 0.90*rail;
    pull-DOWN: V <= 0.10*rail) -- and it must STAY there to the END OF THAT
    HALF PERIOD, so a ringing overshoot cannot score early.

    t_to is MANDATORY and must be the end of the half period: the input flips
    back after it, and scanning past the flip would see the node leave the
    settled band and reset the answer to None for every point."""
    lvl = 0.90 * rail if to_hi else 0.10 * rail
    ok_from = None
    for i in range(len(ts)):
        if ts[i] < t_from or ts[i] > t_to:
            continue
        good = (vs[i] >= lvl) if to_hi else (vs[i] <= lvl)
        if good and ok_from is None:
            ok_from = ts[i]
        elif not good:
            ok_from = None
    return ok_from


def one(path, rail):
    hdr, rows = up.read_prn(path)
    ts = [r[1] * 1e12 for r in rows]
    cin = hdr.index("V(S%d)" % (MEAS - 1))
    cout = hdr.index("V(S%d)" % MEAS)
    vin = [r[cin] for r in rows]
    vout = [r[cout] for r in rows]
    vt, extrap = TRIP(rail)
    out = {}
    # stage 3 of 5: s2 is s0 inverted TWICE, so s2 follows s0.  s0 falls at
    # 200 ps (-> s2 falls, s3 rises) and rises at 500 ps (-> s3 falls).
    # Each window ENDS at the next input flip; see settle_instant.
    for lbl, t_from, t_to, in_rising in (("out_rise", 195.0, 495.0, False),
                                         ("out_fall", 495.0, ts[-1], True)):
        # the input edge (s2) in this window, then the output edge (s3)
        ti = cross(ts, vin, vt, in_rising, t_from)
        t50i = cross(ts, vin, 0.5 * rail, in_rising, t_from)
        t50o = cross(ts, vout, 0.5 * rail, not in_rising, t_from)
        to_hi = not in_rising
        tset = (settle_instant(ts, vout, rail, to_hi, ti, t_to)
                if ti else None)
        tfun = cross(ts, vout, vt, to_hi, ti) if ti else None
        out[lbl] = dict(
            t_in_trip_ps=ti, t_in_50_ps=t50i, t_out_50_ps=t50o,
            t_pd50_ps=(t50o - t50i) if (t50o and t50i) else None,
            t_set90_ps=(tset - ti) if (tset and ti) else None,
            t_func_ps=(tfun - ti) if (tfun and ti) else None,
            v_final_V=vout[-1] if lbl == "out_fall" else None)
    out["vtrip_V"] = vt
    out["vtrip_frac_of_rail"] = vt / rail
    out["vtrip_extrapolated"] = bool(extrap)
    # the slower edge is what a bank waits for: a bank opens when its SLOWEST
    # cell has settled, so the worst edge is the figure of merit.
    for key in ("t_pd50_ps", "t_set90_ps", "t_func_ps"):
        vals = [out[e][key] for e in ("out_rise", "out_fall")
                if out[e][key] is not None]
        out["worst_" + key] = max(vals) if vals else None
        out["mean_" + key] = (sum(vals) / len(vals)) if vals else None
    return out


def fit_a_plus_b_over_s(S, Y):
    """least squares t = a + b/s, with R^2.  The pre-registered decomposition:
    C_load = C_gate_next(~s) + C_wire(fixed), I_drive ~ s, so
    t = (a'*s + C_wire)*dV/(k*s) = a + b/s."""
    X = [1.0 / s for s in S]
    nn = len(S)
    sx, sy = sum(X), sum(Y)
    sxx = sum(x * x for x in X)
    sxy = sum(X[i] * Y[i] for i in range(nn))
    den = nn * sxx - sx * sx
    if abs(den) < 1e-30:
        return None
    b = (nn * sxy - sx * sy) / den
    a = (sy - b * sx) / nn
    pred = [a + b * x for x in X]
    ybar = sy / nn
    ss = sum((Y[i] - pred[i]) ** 2 for i in range(nn))
    st = sum((y - ybar) ** 2 for y in Y)
    return dict(a_const_ps=a, b_over_s_ps=b, R2=(1 - ss / st) if st else None,
                pred_ps=pred,
                asymptote_ps=a,
                fixed_load_share_at_s1_pct=(100.0 * b / (a + b))
                if (a + b) else None)


def discover():
    """decks are found by GLOB, not by a written index, so a parallel run
    cannot disagree with the record of what was run."""
    out = []
    for p in sorted(glob.glob(os.path.join(HERE, "cc_r*_*_s*.cir.prn"))):
        b = os.path.basename(p)[:-8]                 # strip .cir.prn
        parts = b.split("_")                         # cc rNNNN V sS
        rail_code, variant, sc = parts[1], parts[2], parts[3]
        rail = next((r for r in up.CC_RAILS
                     if round(r * 10000) == int(rail_code[1:])), None)
        if rail is None:
            print("SKIP unrecognised rail in %s" % b)
            continue
        out.append(dict(tag=b, rail=rail, variant=variant,
                        scale=float(sc[1:]), path=p))
    return out


def main():
    idx = discover()
    print("found %d crux decks" % len(idx))
    pts = []
    for e in idx:
        r = one(e["path"], e["rail"])
        r.update(tag=e["tag"], rail_V=e["rail"], variant=e["variant"],
                 scale=e["scale"])
        pts.append(r)
    out = dict(
        _doc="qal/upsize THE CRUX -- CELL-LEVEL, fixed rail, 5-stage chain, "
             "stage 3 measured.  MEASURED unless a key says DERIVED.  These "
             "are NOT chain results and are never quoted as such.",
        _variants=dict(
            A="REAL CHAIN: all cells scale, CLOAD 2 fF fixed (wiring does not "
              "scale with transistor width).  This is what the main series runs.",
            B="PURE COSCALE: all cells scale, CLOAD = 2*s fF.  Everything the "
              "driver sees scales -- the theoretical invariance test.",
            C="FIXED LOAD: stages 1-3 scale, stages 4-5 stay x1.  Drive into a "
              "load that does NOT scale -- the naive 1/s expectation, and the "
              "positive control that proves the instrument can see a speed-up.",
            D="QAL-BIAS LOAD: like A, but the load stages' rail is tied to 0 V, "
              "because in the real chain bank k+1's rail has NOT been raised "
              "while bank k settles, so the gate load is UNPOWERED and its C_gg "
              "bias differs.  Both driver and load still scale, so the scaling "
              "conclusion should be unchanged -- measured, not assumed."),
        points=pts)
    # ---- the answer, per rail and variant
    ans = {}
    for rail in sorted(set(p["rail_V"] for p in pts)):
        for v in ("A", "B", "C", "D"):
            sel = sorted([p for p in pts if p["variant"] == v
                          and p["rail_V"] == rail], key=lambda p: p["scale"])
            if len(sel) < 2:
                continue
            S = [p["scale"] for p in sel]
            key = "r%d_%s" % (round(rail * 10000), v)
            d = dict(rail_V=rail, variant=v, scales=S)
            for metric in ("worst_t_set90_ps", "worst_t_pd50_ps",
                           "worst_t_func_ps"):
                Y = [p[metric] for p in sel]
                if any(y is None for y in Y):
                    d[metric] = dict(values=Y, note="incomplete")
                    continue
                d[metric] = dict(
                    values=Y,
                    ratio_last_over_first=Y[-1] / Y[0],
                    pct_change_x1_to_x8=100.0 * (Y[-1] / Y[0] - 1.0),
                    per_doubling_pct=[round(100.0 * (Y[i + 1] / Y[i] - 1), 3)
                                      for i in range(len(Y) - 1)],
                    exponent_in_s=(math.log(Y[-1] / Y[0])
                                   / math.log(S[-1] / S[0])),
                    fit_a_plus_b_over_s=fit_a_plus_b_over_s(S, Y))
            ans[key] = d
    out["ANSWER"] = ans
    open(os.path.join(HERE, "CRUX.json"), "w").write(
        json.dumps(out, indent=1, default=str))

    print("%-28s %6s %8s %8s %8s %8s" % ("rail/variant", "scale", "pd50",
                                         "set90", "func", "vtrip"))
    for rail in sorted(set(p["rail_V"] for p in pts)):
        for v in ("A", "B", "C", "D"):
            for p in sorted([q for q in pts if q["variant"] == v
                             and q["rail_V"] == rail], key=lambda q: q["scale"]):
                print("%-28s %6g %8.3f %8.3f %8.3f %8.4f"
                      % ("rail %.4f  variant %s" % (rail, v), p["scale"],
                         p["worst_t_pd50_ps"] or float("nan"),
                         p["worst_t_set90_ps"] or float("nan"),
                         p["worst_t_func_ps"] or float("nan"),
                         p["vtrip_V"]))
    print()
    for k, d in ans.items():
        m = d.get("worst_t_set90_ps", {})
        if "ratio_last_over_first" in m:
            f = m["fit_a_plus_b_over_s"] or {}
            print("%s  t_set90 x1->x8 ratio %.4f (%.1f%%)  exp_in_s %+.4f  "
                  "fit a=%.3f b=%.3f R2=%.5f  fixed-load share@x1 %.1f%%"
                  % (k, m["ratio_last_over_first"], m["pct_change_x1_to_x8"],
                     m["exponent_in_s"], f.get("a_const_ps", float("nan")),
                     f.get("b_over_s_ps", float("nan")),
                     f.get("R2", float("nan")),
                     f.get("fixed_load_share_at_s1_pct", float("nan"))))


if __name__ == "__main__":
    main()
