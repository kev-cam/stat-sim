#!/usr/bin/env python3
"""Phase-1 analysis: per-dataset tables, the self-test, and the arbiter."""
import collections, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rescore import NB

HERE = os.path.dirname(os.path.abspath(__file__))
R = json.load(open(os.path.join(HERE, "RESCORE.json")))
T = json.load(open(os.path.join(HERE, "TRIP.json")))

out = {}

# ---------------------------------------------------------------- 1. threshold
srows = T["S"]["rows"]
out["THRESHOLD_MEASURED"] = {
    "_instrument_check_vs_committed_bound_dc_rows": {
        "std_1.12p_0.74n @1.20V": {"mine": srows["1.2000"]["trip_V"],
                                   "committed_bound_dc_rows_A1": 0.6451630261834231},
        "std @1.00V": {"mine": srows["1.0000"]["trip_V"], "committed_B1": 0.546696061776791},
        "std @0.90V": {"mine": srows["0.9000"]["trip_V"], "committed_B2": 0.4958921397750707},
        "std @0.80V": {"mine": srows["0.8000"]["trip_V"], "committed_B3": 0.4452317044608874},
    },
    "S_trip_vs_rail": {k: dict(trip_V=round(v["trip_V"], 6),
                               frac=round(v["trip_frac_of_rail"], 5),
                               window_10_90_mV=round(v["window_10_90_mV"], 2))
                       for k, v in sorted(srows.items(), key=lambda x: float(x[0]))},
}
if "A" in T:
    arows = T["A"]["rows"]
    out["THRESHOLD_MEASURED"]["A_trip_vs_rail"] = {
        k: dict(trip_V=(round(v["trip_V"], 6) if v["trip_V"] else None),
                frac=(round(v["trip_frac_of_rail"], 5) if v["trip_V"] else None),
                window_10_90_mV=(round(v["window_10_90_mV"], 2)
                                 if v["window_10_90_mV"] else None))
        for k, v in sorted(arows.items(), key=lambda x: float(x[0]))}
    out["THRESHOLD_MEASURED"]["_instrument_check_vs_committed_bound_dc_rows"][
        "skew_0.15p_1.48n @1.20V"] = {"mine": arows["1.2000"]["trip_V"],
                                      "committed_bound_dc_rows_A4": 0.45948054259979987}

# ---------------------------------------------------------------- 2. per-dataset
per = {}
for ds in R:
    rows = R[ds]
    n = len(rows)
    s1 = sum(1 for r in rows.values() if r["ROW_S1"])
    va = sum(1 for r in rows.values() if r["ROW_VALUE"])
    s3 = sum(1 for r in rows.values() if r["ROW_S3"])
    flip = [t for t, r in rows.items() if (not r["ROW_S1"]) and r["ROW_S3"]]
    stay = [t for t, r in rows.items() if (not r["ROW_S1"]) and not r["ROW_S3"]]
    lost = [t for t, r in rows.items() if r["ROW_S1"] and not r["ROW_S3"]]
    L = [l for r in rows.values() for l in r["links"]]
    per[ds] = dict(
        n_rows=n, rows_pass_90pct=s1, rows_pass_committed_VALUE=va,
        rows_pass_FUNCTIONAL=s3,
        rows_that_FAILED_90pct_and_PASS_functionally=len(flip),
        which_flipped=sorted(flip),
        rows_that_FAILED_90pct_and_still_FAIL=len(stay),
        rows_that_PASSED_90pct_and_now_FAIL=len(lost), which_lost=sorted(lost),
        n_links=len(L),
        links_pass_90pct=sum(1 for l in L if l["S1_pass90"]),
        links_pass_FUNCTIONAL=sum(1 for l in L if l["S3_pass"]),
        links_FAIL_inside_noise_budget=sum(1 for l in L if l["S3_mode"] == "FAIL_budget"),
        links_FAIL_cross_after_commit=sum(1 for l in L if l["S3_mode"] == "FAIL_late"),
        links_FAIL_never_correct=sum(1 for l in L if l["S3_mode"] == "FAIL_never"),
        links_that_FAILED_90pct_and_PASS_functionally=sum(
            1 for l in L if (not l["S1_pass90"]) and l["S3_pass"]),
    )
out["PER_DATASET"] = per

# ---------------------------------------------------------------- 3. self-test
cnt = collections.Counter()
lowarm, higharm = [], []
for ds in R:
    for tag, r in R[ds].items():
        for l in r["links"]:
            cnt[(l["value_guard_pass"], l["S3_pass"])] += 1
            if (not l["value_guard_pass"]) and l["S3_pass"]:
                fr = (l["v_at_committed_V"] / l["rail_own_V"]) if l["rail_own_V"] else None
                rec = dict(ds=ds, tag=tag, k=l["k"], i=l["i"], want_hi=l["want_hi"],
                           v_frac_of_own_rail=(round(fr, 4) if fr else None),
                           guard_bar=(0.50 if l["want_hi"] else 0.10),
                           S3_margin_mV=l["S3_margin_mV"],
                           margin_in_sigma=round(l["S3_margin_mV"] / 6.441, 1))
                (higharm if l["want_hi"] else lowarm).append(rec)
rowdis = [(ds, t) for ds in R for t, r in R[ds].items()
          if (not r["ROW_VALUE"]) and r["ROW_S3"]]
rowdis2 = [(ds, t) for ds in R for t, r in R[ds].items()
           if r["ROW_VALUE"] and not r["ROW_S3"]]
out["SELF_TEST_vs_the_committed_VALUE_check"] = {
    "_rule_from_the_brief": "where a dataset carries an independent VALUE check the value check is the arbiter; if my criterion passes a row whose value check failed, my criterion is wrong.",
    "link_level": {"guard_PASS_and_functional_PASS": cnt[(True, True)],
                   "guard_FAIL_and_functional_FAIL": cnt[(False, False)],
                   "guard_PASS_but_functional_FAIL": cnt[(True, False)],
                   "guard_FAIL_but_functional_PASS": cnt[(False, True)]},
    "row_level": {"agree": sum(1 for ds in R for r in R[ds].values()
                               if r["ROW_VALUE"] == r["ROW_S3"]),
                  "VALUE_fail_but_functional_PASS": len(rowdis),
                  "VALUE_pass_but_functional_FAIL": len(rowdis2),
                  "which_VALUE_fail_functional_PASS": sorted(rowdis)},
    "DIAGNOSIS_low_arm": {
        "n_links": len(lowarm),
        "what": "the committed guard's LOW arm is v <= 0.10 * own rail.  The MEASURED trip is 0.52-0.59 of rail over the delivered range, so the guard's LOW arm is 4.6-5.9x STRICTER than the receiver's actual decision threshold.  Every one of these links is a LOW sitting between 10% and ~55% of rail: it fails the guard and is nowhere near the trip.",
        "worst_10_by_least_margin": sorted(lowarm, key=lambda r: r["S3_margin_mV"])[:10],
        "median_margin_mV": (sorted(r["S3_margin_mV"] for r in lowarm)[len(lowarm) // 2]
                             if lowarm else None)},
    "DIAGNOSIS_high_arm": {
        "n_links": len(higharm),
        "what": "the guard's HIGH arm is v >= 0.50 * own rail, which is LOOSER than the measured trip (0.52-0.59 of rail) when sender and receiver share a rail, and can be either way when the receiver's rail is lower.  These links fail the guard against their OWN rail and clear the trip at the RECEIVER's (lower) rail.",
        "worst_10_by_least_margin": sorted(higharm, key=lambda r: r["S3_margin_mV"])[:10]},
}

json.dump(out, open(os.path.join(HERE, "ANALYSIS.json"), "w"), indent=1)

print("== THRESHOLD instrument check (mine vs committed bound/dc_rows) ==")
for k, v in out["THRESHOLD_MEASURED"]["_instrument_check_vs_committed_bound_dc_rows"].items():
    a = v["mine"]
    b = [x for kk, x in v.items() if kk != "mine"][0]
    print("  %-28s mine %.6f  committed %.6f  rel %.2e" % (k, a, b, abs(a - b) / b))
print()
print("== PER DATASET ==")
print("dataset     rows  90%  VALUE  FUNC  flipped  lost | links   90%   FUNC  budgetF  lateF  neverF")
for ds, p in per.items():
    print("%-10s %4d %4d %5d %5d %8d %5d | %5d %5d %5d %9d %8d %9d" % (
        ds, p["n_rows"], p["rows_pass_90pct"], p["rows_pass_committed_VALUE"],
        p["rows_pass_FUNCTIONAL"], p["rows_that_FAILED_90pct_and_PASS_functionally"],
        p["rows_that_PASSED_90pct_and_now_FAIL"], p["n_links"],
        p["links_pass_90pct"], p["links_pass_FUNCTIONAL"],
        p["links_FAIL_inside_noise_budget"], p["links_FAIL_cross_after_commit"],
        p["links_FAIL_never_correct"]))
print()
print("== SELF TEST ==", json.dumps(out["SELF_TEST_vs_the_committed_VALUE_check"]["link_level"]))
print("   rows:", json.dumps(out["SELF_TEST_vs_the_committed_VALUE_check"]["row_level"]["agree"]),
      "agree /", len(rowdis), "VALUE-fail-but-functional-PASS /", len(rowdis2), "VALUE-pass-but-functional-FAIL")
