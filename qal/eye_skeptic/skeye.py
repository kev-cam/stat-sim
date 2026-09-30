#!/usr/bin/env python3
"""SK1 / SK2: rebuild the eye from MY OWN transients with MY OWN extractor.

Reports, per bank 1..3 (MEASURED receivers only):
  - the opening (t_valid after the bank's own rail start) at every contour
  - the CLOSING edge at every contour -- including the contour the BUDGET
    actually charges (3*sigma_total = 69.92 mV), which nobody has taken a
    width at
  - the same three ways: P0 alone, the claimed-binding pattern alone, and the
    pointwise INTERSECTION -- the SK2 envelope test
  - the height at the actual sampling instant c_k + T, in mV and in BOTH
    sigma units (sigma_trip, which they quote, and sigma_total, which their own
    budget uses)
"""
import json, math, os, sys
from array import array
import skharness as SK
import skcalc as SC

HERE = SK.HERE
T, H = 200.0, 4
PATS = [p for p in ("P0", "P1", "P2", "P3")
        if os.path.exists(os.path.join(HERE, p, "sched.json"))]


def close_edge(curve, n, from_idx, thresh):
    """First fall of curve below thresh strictly after from_idx, sub-grid."""
    a = from_idx + 1
    while a < n:
        if not (curve[a] > thresh):
            y0, y1 = curve[a - 1], curve[a]
            if y0 <= thresh:
                return dict(close_ps=a * SC.GRID, set_by="not_a_crossing")
            if y1 == y0:
                return dict(close_ps=a * SC.GRID, set_by="flat")
            return dict(close_ps=(a - 1) * SC.GRID + (thresh - y0) * SC.GRID / (y1 - y0),
                        set_by="margin_crossing")
        a += 1
    return dict(close_ps=None, set_by="NO_CLOSE_INSIDE_DECK")


def main():
    loaded, A6 = {}, {}
    for p in PATS:
        S = json.load(open(os.path.join(HERE, p, "sched.json")))
        A6[p] = S["A6"]
        # AMENDMENT SA1: A6 is NOT a validity gate on a CALIBRATED row.  A
        # data-blind schedule cannot open at the true zero for any vector but
        # the calibration vector -- that is what "one timer, not an oracle"
        # means.  Excluding A6-failing rows would throw out the BINDING pattern
        # and manufacture the best-case envelope this audit exists to police.
        # Every calibrated row enters the intersection; A6 is carried, not gated.
        if not S["A6"]["A6_pass_1uA"]:
            print("A6 FAIL %s worst %.4f uA -- KEPT (see AMENDMENT SA1), "
                  "off-zero switching is the definition of a data-blind schedule"
                  % (p, S["A6"]["worst_abs_uA"]))
        m, C, n, meta = SC.margins(S["prn"], S["mt0"], S["bits"], T, float(S["tend"]))
        loaded[p] = dict(m=m, n=n, meta=meta,
                         c={int(k): float(v) for k, v in S["c"].items()},
                         r={int(k): float(v) for k, v in S["r"].items()},
                         ro={int(k): float(v) for k, v in S["ro"].items()},
                         tend=float(S["tend"]), rail={}, bits=S["bits"])
        for k in range(1, 4):
            loaded[p]["rail"][k] = m[k]["rail_at_rx_boundary_V"]
        print("loaded %s  n=%d  solver_pts=%d dt_max=%.4f ps  A6 worst %.4f uA"
              % (p, n, meta["n_solver_pts"], meta["solver_dt_max_ps"],
                 S["A6"]["worst_abs_uA"]), flush=True)

    good = list(loaded)
    nmin = min(loaded[p]["n"] for p in good)
    out = dict(_what="SKEPTIC independent rebuild of the eye",
               _patterns=good, _grid_ps=SC.GRID,
               _n_common=nmin,
               _contours_mV={nm: v for nm, v in SC.CONTOURS},
               _sigma=dict(sigma_trip_mV=SC.SIG_TRIP,
                           sigma_driver_level_mV=SC.SIG_LEVEL,
                           sigma_total_mV=SC.SIG_TOT),
               _A6=A6, banks={})

    for k in range(1, 4):
        ck = max(loaded[p]["c"][k] for p in good)
        rk = max(loaded[p]["r"][k] for p in good)
        rec = dict(receiver="bank %d (MEASURED)" % (k + 1),
                   own_rail_start_c_ps=ck, return_close_r_ps=rk,
                   sampling_instant_ps=ck + T,
                   decision_level_V={p: loaded[p]["m"][k]["rail_at_rx_boundary_V"]
                                     for p in good},
                   n_HIGH_gates={p: loaded[p]["m"][k]["n_HIGH"] for p in good},
                   n_LOW_gates={p: loaded[p]["m"][k]["n_LOW"] for p in good})

        # --- SK2: the three constructions
        sets = {}
        for p in good:
            sets["SINGLE_" + p] = [loaded[p]["m"][k]["DATA_all"]]
        sets["INTERSECTION_all_patterns"] = [loaded[p]["m"][k]["DATA_all"] for p in good]

        rec["constructions"] = {}
        for nm, curves in sets.items():
            cur, n = SC.intersect(curves)
            e = {}
            for cn, cv in SC.CONTOURS:
                op = SC.first_run_edge(cur, n, ck, cv)
                if op is None:
                    e[cn] = dict(EYE="EMPTY")
                    continue
                ai = int(math.ceil(op["open_ps"] / SC.GRID))
                cl = close_edge(cur, n, ai, cv)
                e[cn] = dict(opening_ps=round(op["open_ps"], 4),
                             t_valid_after_own_rail_start_ps=round(op["open_ps"] - ck, 4),
                             opening_set_by=op["set_by"],
                             closing_ps=(round(cl["close_ps"], 4)
                                         if cl["close_ps"] is not None else None),
                             closing_set_by=cl["set_by"],
                             WIDTH_ps=(round(cl["close_ps"] - op["open_ps"], 4)
                                       if cl["close_ps"] is not None else None),
                             WIDTH_IS_LOWER_BOUND=(cl["close_ps"] is None))
            # post-return margin floor
            ar = int(round(rk / SC.GRID))
            fl = min((cur[a], a) for a in range(min(ar, n - 1), n))
            e["_post_return_floor_mV"] = round(fl[0], 4)
            e["_post_return_floor_at_ps"] = round(fl[1] * SC.GRID, 4)
            e["_floor_in_sigma_trip"] = round(fl[0] / SC.SIG_TRIP, 3)
            e["_floor_in_sigma_total"] = round(fl[0] / SC.SIG_TOT, 3)
            # height at the actual sampling instant
            asamp = min(n - 1, int(round((ck + T) / SC.GRID)))
            e["_height_at_sampling_instant_mV"] = round(cur[asamp], 4)
            e["_height_in_sigma_trip"] = round(cur[asamp] / SC.SIG_TRIP, 2)
            e["_height_in_sigma_total"] = round(cur[asamp] / SC.SIG_TOT, 2)
            rec["constructions"][nm] = e

        # --- polarity diagnostic (NOT the headline; the headline is all-gates)
        rec["polarity_diagnostic"] = {}
        for pol in ("HIGH", "LOW"):
            cs = [loaded[p]["m"][k]["DATA_pol"][pol] for p in good
                  if loaded[p]["m"][k]["DATA_pol"][pol] is not None]
            if not cs:
                continue
            cur, n = SC.intersect(cs)
            op = SC.first_run_edge(cur, n, ck, 0.0)
            rec["polarity_diagnostic"][pol] = dict(
                n_patterns_with_this_polarity=len(cs),
                opening_ps=(round(op["open_ps"], 4) if op else None),
                t_valid_ps=(round(op["open_ps"] - ck, 4) if op else None),
                set_by=(op["set_by"] if op else None))
        out["banks"][k] = rec

    json.dump(out, open(os.path.join(HERE, "SKEPTIC_EYE.json"), "w"), indent=1)

    # ------------------------------------------------------------- report
    print("\n" + "=" * 96)
    print("SK1  MY OWN t_valid (opening - own rail start), DATA reference, "
          "min over ALL 8 GATES then over patterns")
    print("=" * 96)
    print("%-6s %-34s %10s %10s %10s %10s" %
          ("bank", "construction", "0mV", "1sig_trip", "3sig_trip", "3sig_tot"))
    for k in (1, 2, 3):
        for nm in sorted(out["banks"][k]["constructions"]):
            e = out["banks"][k]["constructions"][nm]
            vals = []
            for cn, _ in SC.CONTOURS:
                v = e[cn]
                vals.append("%10.4f" % v["t_valid_after_own_rail_start_ps"]
                            if "t_valid_after_own_rail_start_ps" in v else "%10s" % "EMPTY")
            print("%-6d %-34s %s" % (k, nm, "".join(vals)))
        print()

    print("=" * 96)
    print("SK2  WIDTH and CLOSING at each contour -- INTERSECTION, and the floor")
    print("=" * 96)
    for k in (1, 2, 3):
        e = out["banks"][k]["constructions"]["INTERSECTION_all_patterns"]
        print("bank %d  post-return floor %.4f mV  (%.2f sigma_trip, %.2f sigma_total) at %.1f ps"
              % (k, e["_post_return_floor_mV"], e["_floor_in_sigma_trip"],
                 e["_floor_in_sigma_total"], e["_post_return_floor_at_ps"]))
        print("        height at sampling instant %.4f mV = %.2f sigma_trip = %.2f sigma_total"
              % (e["_height_at_sampling_instant_mV"], e["_height_in_sigma_trip"],
                 e["_height_in_sigma_total"]))
        for cn, cv in SC.CONTOURS:
            v = e[cn]
            print("        %-14s (%6.3f mV)  open %9.4f  close %-12s width %-12s %s"
                  % (cn, cv, v["opening_ps"],
                     ("%.4f" % v["closing_ps"]) if v["closing_ps"] is not None else "NONE",
                     ("%.4f" % v["WIDTH_ps"]) if v["WIDTH_ps"] is not None else "LOWER BOUND",
                     v["closing_set_by"]))
        print()

    print("=" * 96)
    print("SK2  POLARITY DIAGNOSTIC (0 mV, DATA ref) -- which polarity limits the early edge")
    print("=" * 96)
    for k in (1, 2, 3):
        for pol, v in out["banks"][k]["polarity_diagnostic"].items():
            print("bank %d  %-5s  n_pat=%d  t_valid %s ps  (%s)"
                  % (k, pol, v["n_patterns_with_this_polarity"],
                     v["t_valid_ps"], v["set_by"]))
    print("\nwrote SKEPTIC_EYE.json")


if __name__ == "__main__":
    main()
