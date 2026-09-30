#!/usr/bin/env python3
"""PHASE 2 eye extraction at one (T, H), on the CALIBRATED schedule.

Re-uses Phase 1's eyecalc.per_pattern VERBATIM for the margin definition, so a
Phase-2 eye and a Phase-1 eye are the same instrument pointed at a different
schedule.  Only HERE is redirected, to p2/T<T>_H<H>/.

Emitted per bank: the EYE2 DATA_FIXED opening as the INTERSECTION over the
patterns present, for BOTH polarities, at the 0 mV / 1-sigma / 3-sigma contours,
plus the margin SLOPE at the opening (which is what converts a mismatch voltage
into a time charge) and the setup slack T - t_valid.
"""
import json, os, sys
from array import array

sys.path.insert(0, "/usr/local/src/stat-sim/qal/eye")
import eyeharness as EH                                   # noqa: E402
import eyecalc as EC                                      # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
GRID = EC.GRID
SIG = EC.SIG_TRIP_MV                                      # 6.441 mV
SIG_LEVEL_MV = 22.4      # MEASURED qal/mcsize exit HIGH-class level sigma (worst)
CONTOURS = {"0mV": 0.0, "1sigma_trip": SIG, "3sigma_trip": 3.0 * SIG,
            "3sigma_total_with_driver_level": 3.0 * (SIG ** 2 + SIG_LEVEL_MV ** 2) ** 0.5}


def edge(ts, mg, t_lo, thr):
    """First contiguous run with margin > thr at/after t_lo.  Sub-grid root,
    GUARDED exactly as Phase 1 E6 requires."""
    n = len(ts)
    i0 = 0
    while i0 < n and ts[i0] < t_lo - 1e-9:
        i0 += 1
    for i in range(i0, n):
        if mg[i] > thr:
            if i == i0:
                return ts[i], "clipped_at_window_start", None
            a, b = mg[i - 1], mg[i]
            if a > thr:
                return ts[i], "not_a_crossing", None
            f = (thr - a) / (b - a)
            t = ts[i - 1] + f * (ts[i] - ts[i - 1])
            slope = (b - a) / (ts[i] - ts[i - 1])          # mV/ps
            return t, "margin_crossing", slope
    return None, "never_opens", None


def run(T, H, pats, label, outname, basedir=None):
    """basedir=None -> this phase's own p2/T<T>_H<H>/.  Pass the Phase-1
    directory to aim the IDENTICAL extractor at Phase 1's ORACLE rows."""
    d = basedir or os.path.join(HERE, "T%g_H%d" % (T, H))
    EC.HERE = d
    per, missing = {}, []
    for p in pats:
        if not os.path.exists(os.path.join(d, p, "sched.json")):
            missing.append(p); continue
        per[p] = EC.per_pattern(p)
    if not per:
        print("no patterns present at", d); return None
    any_ = next(iter(per.values()))
    nb, mgt = any_["nb"], any_["mg"]
    # The intersection domain is the COMMON time span.  On the CALIBRATED
    # schedule every pattern shares one zeros vector, so tend -- and hence the
    # grid length -- is identical.  On Phase 1's ORACLE schedule each pattern
    # carries its OWN zeros, so tend differs per pattern and the grids have
    # different lengths; truncating to the shortest is the only correct
    # intersection domain.  (Self-caught: the first version indexed off the
    # first pattern's length and raised IndexError on the oracle set.)
    ng = min(len(P["grid"]) for P in per.values())
    g = any_["grid"][:ng]
    out_span = {"common_span_ps": (ng - 1) * GRID,
                "per_pattern_grid_len": {p: len(P["grid"]) for p, P in per.items()},
                "truncated_to_common_span": len(set(
                    len(P["grid"]) for P in per.values())) > 1}
    out = {"_what": "PHASE 2 calibrated-schedule eye, %s" % label,
           "T_ps": T, "H": H, "patterns_present": sorted(per),
           "patterns_missing": missing,
           "n_patterns": len(per), "grid_ps": GRID,
           "intersection_domain": out_span,
           # .get(): Phase 1's sched.json predates this key, so the SAME
           # extractor can be pointed at Phase 1's ORACLE rows for an
           # apples-to-apples oracle-vs-calibrated difference.
           "schedule_source": {p: json.load(open(
               os.path.join(d, p, "sched.json"))).get(
                   "schedule_source", "PHASE 1 per-pattern OWN zeros (ORACLE)")
               for p in per},
           "A6_residual_uA_per_pattern": {
               p: json.load(open(os.path.join(d, p, "sched.json")))
               .get("A6_residual", {"_note": "PHASE 1 row: A6 in EYE.json _patterns"})
               for p in per},
           "banks": {}}

    for k in range(1, nb + 1):
        ck = any_["c"][k]
        # --- INTERSECTION over patterns of min-over-gates, per polarity
        mn = {"HIGH": array("d", [1e9] * ng), "LOW": array("d", [1e9] * ng),
              "all": array("d", [1e9] * ng)}
        for p, P in per.items():
            for i in range(mgt):
                col = P["mgn_data"][k][i]
                pol = "HIGH" if P["hi"][k][i] else "LOW"
                for a in range(ng):
                    v = col[a]
                    if v < mn[pol][a]:
                        mn[pol][a] = v
                    if v < mn["all"][a]:
                        mn["all"][a] = v
        bank = {"receiver": ("bank %d (MEASURED)" % (k + 1)) if k < nb
                            else "DERIVED (no bank %d in a %d-bank deck)" % (nb + 1, nb),
                "receiver_is_measured": k < nb,
                "own_rail_start_c_ps": ck,
                "transfer_open_o_ps": any_["o"][k],
                "o_minus_c_ps": any_["o"][k] - ck,
                "sampling_instant_ps": ck + T,
                "contours": {}}
        for cn, thr in CONTOURS.items():
            row = {}
            for pol in ("HIGH", "LOW", "all"):
                t, how, sl = edge(g, mn[pol], ck, thr)
                row[pol] = {"opening_ps": t, "set_by": how,
                            "t_valid_after_own_rail_start_ps":
                                (t - ck) if t is not None else None,
                            "setup_slack_ps": (T - (t - ck)) if t is not None else None,
                            "margin_slope_mV_per_ps": sl}
            row["binding_polarity"] = max(
                ("HIGH", "LOW"),
                key=lambda pp: (row[pp]["opening_ps"] if row[pp]["opening_ps"]
                                is not None else -1))
            bank["contours"][cn] = row
        # per-pattern openings, so the spread across data is visible
        pp = {}
        for p, P in per.items():
            m = array("d", [1e9] * ng)
            for i in range(mgt):
                if P["hi"][k][i]:
                    col = P["mgn_data"][k][i]
                    for a in range(ng):
                        if col[a] < m[a]:
                            m[a] = col[a]
            t, how, sl = edge(g, m, ck, 0.0)
            pp[p] = {"opening_ps": t, "set_by": how,
                     "t_valid_ps": (t - ck) if t is not None else None}
        ops = [v["t_valid_ps"] for v in pp.values() if v["t_valid_ps"] is not None]
        bank["per_pattern_HIGH_opening"] = pp
        bank["data_spread_of_opening_ps"] = {
            "n": len(ops), "min": min(ops) if ops else None,
            "max": max(ops) if ops else None,
            "peak_to_peak": (max(ops) - min(ops)) if ops else None,
            "binding_pattern": max(pp, key=lambda p: (
                pp[p]["t_valid_ps"] if pp[p]["t_valid_ps"] is not None else -1))}
        out["banks"][str(k)] = bank
    open(os.path.join(HERE, outname), "w").write(json.dumps(out, indent=1))
    print("wrote", outname)
    for k in ("1", "2", "3"):
        b = out["banks"][k]["contours"]["0mV"]
        print("  bank%s t_valid=%.3f ps  slack=%.3f ps  (pol %s, slope %s)"
              % (k, b[b["binding_polarity"]]["t_valid_after_own_rail_start_ps"],
                 b[b["binding_polarity"]]["setup_slack_ps"],
                 b["binding_polarity"],
                 ("%.2f" % b[b["binding_polarity"]]["margin_slope_mV_per_ps"])
                 if b[b["binding_polarity"]]["margin_slope_mV_per_ps"] else "n/a"))
    return out


if __name__ == "__main__":
    T, H = float(sys.argv[1]), int(sys.argv[2])
    pats = sys.argv[3].split(",")
    label = sys.argv[4] if len(sys.argv) > 4 else "calibrated"
    run(T, H, pats, label, "EYE_P2_T%g_H%d_%s.json" % (T, H, label))
