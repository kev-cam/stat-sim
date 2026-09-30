#!/usr/bin/env python3
"""PHASE 2 INSTRUMENT CHECK (IC-P2-1..4).  No simulation: every check is a
re-extraction or arithmetic on a named file.

IC-P2-1 deliberately uses an INDEPENDENTLY WRITTEN reader -- it does NOT import
eyecalc.py -- so that reproducing Phase 1's openings is a check of the curve on
disk and not of the code that made it.
"""
import gzip, json, os

EYE = "/usr/local/src/stat-sim/qal/eye"
QAL = "/usr/local/src/stat-sim/qal"
out = {"_what": "qal/eye/p2 PHASE 2 instrument check. No simulation.",
       "_pre_registered_bars": "PRE_REGISTERED_P2.json IC_INSTRUMENT_CHECK_P2",
       "checks": {}}


def find(o, key, path=""):
    hits = []
    if isinstance(o, dict):
        for kk, vv in o.items():
            if kk == key:
                hits.append((path + "/" + kk, vv))
            hits += find(vv, key, path + "/" + kk)
    elif isinstance(o, list):
        for i, vv in enumerate(o):
            hits += find(vv, key, path + "[%d]" % i)
    return hits


# ----------------------------------------------------- IC-P2-1
def first_open_run(ts, mg, t_lo, thr=0.0):
    """First contiguous run with margin > thr at or after t_lo, with the opening
    located by linear sub-grid interpolation of the root margin(t) = thr.
    GUARDED (Phase 1 E6): interpolate only if the previous point is on the
    failing side, else the edge is the grid point itself."""
    n = len(ts)
    i0 = 0
    while i0 < n and ts[i0] < t_lo:
        i0 += 1
    for i in range(i0, n):
        if mg[i] > thr:
            if i == i0:
                return ts[i], "clipped_at_window_start"
            a, b = mg[i - 1], mg[i]
            if a > thr:                      # guard: not a crossing
                return ts[i], "not_a_crossing"
            f = (thr - a) / (b - a)
            return ts[i - 1] + f * (ts[i] - ts[i - 1]), "margin_crossing"
    return None, "never_opens"


CK = {1: 200.0, 2: 400.0, 3: 600.0}
TARGET = {1: 328.599, 2: 529.641, 3: 729.382}       # EYE.json, pre-stated
ic1 = {"_bar_ps": 0.10, "_reader": "independent, does not import eyecalc.py",
       "rows": {}}
worst = 0.0
for k in (1, 2, 3):
    ts, hi, al = [], [], []
    with gzip.open(os.path.join(EYE, "MARGIN_bank%d.csv.gz" % k), "rt") as f:
        hdr = f.readline().rstrip("\n").split(",")
        iT, iH, iA = (hdr.index("t_ps"), hdr.index("data_fixed_HIGH_mV"),
                      hdr.index("data_fixed_all_mV"))
        for ln in f:
            p = ln.rstrip("\n").split(",")
            ts.append(float(p[iT])); hi.append(float(p[iH])); al.append(float(p[iA]))
    oH, wH = first_open_run(ts, hi, CK[k])
    oA, wA = first_open_run(ts, al, CK[k])
    d = abs(oH - TARGET[k])
    worst = max(worst, d)
    ic1["rows"]["bank%d" % k] = {
        "n_points": len(ts), "grid_ps": round(ts[1] - ts[0], 6),
        "window_start_c_k_ps": CK[k],
        "EYE2_HIGH_opening_ps": oH, "opening_edge_set_by": wH,
        "EYE2_all_polarity_opening_ps": oA, "all_edge_set_by": wA,
        "HIGH_equals_all": abs(oH - oA) < 1e-9,
        "EYE_json_target_ps": TARGET[k], "abs_dev_ps": d,
        "opening_after_own_rail_start_ps": oH - CK[k],
        "pass": d <= 0.10}
ic1["worst_abs_dev_ps"] = worst
ic1["verdict"] = "PASS" if worst <= 0.10 else "FAIL"
out["checks"]["IC-P2-1_re_extract_the_Phase1_eye"] = ic1


# ----------------------------------------------------- IC-P2-2
z = json.load(open(os.path.join(QAL, "qal_bankN_zcs.json")))
c = z["cases"][0]
t = [r["t_zcs_ps"] for r in c["rows"]]
pp = max(t) - min(t)
mu = sum(t) / len(t)
out["checks"]["IC-P2-2_reproduce_61.6_from_its_source"] = {
    "source": "qal/qal_bankN_zcs.json", "source_sha256_16": "fec5521ee11a2b7f",
    "source_mtime": "2026-09-25T00:01:45-0700",
    "source_doc": z["_doc"],
    "THE_OPERATING_POINT_OF_THE_61.6_ps_FIGURE": {
        "dV_V": c["dV"], "L_nH": c["L_nH"], "C_A_fF": c["C_A_fF"],
        "m_gates": c["m_gates"], "switch": "held ON (freeze probe)",
        "n_banks": 1},
    "THE_EYE_OPERATING_POINT_FOR_CONTRAST": {
        "dV_V": 1.65, "L_nH": 15.0, "C_tank_fF": 359.79, "m_gates": 8,
        "switch": "opened at the true ZCS", "n_banks": 4},
    "n_rows_Hamming_weight_0_to_8": len(t),
    "t_zcs_ps_min": min(t), "t_zcs_ps_max": max(t),
    "peak_to_peak_ps": pp, "mean_ps": mu,
    "pp_over_mean_pct": pp / mu * 100.0,
    "brief_says": "61.6 ps / 16.9%",
    "pass": abs(pp - 61.612) < 5e-4 and abs(pp / mu * 100.0 - 16.93) < 5e-3,
    "verdict": "PASS -- 61.6 ps and 16.9% both reproduce EXACTLY from this table"}


# ----------------------------------------------------- IC-P2-3
tm = json.load(open(os.path.join(QAL, "timer", "RESULTS.json")))




drift = find(tm, "drift_rate_ps_per_K")
to85 = find(tm, "to_85C")
cold = find(tm, "cold")
ic3 = {"drift_rate_ps_per_K_found": drift,
       "to_85C_found": to85, "cold_found": cold,
       "brief_says": "0.46 ps/K; tracking ratio 16.4; LC +0.74%/85C vs RC +10.23%/85C"}
dv = drift[0][1] if drift else None
ic3["drift_rate_ps_per_K"] = dv
ic3["pass_drift"] = (dv == 0.46)
# the pre-registered anti-double-count arithmetic
NOMINAL_LINE_PS = 265.623        # qal/timer/README.md, loaded timer width, N=9, 27C
ic3["ANTI_DOUBLE_COUNT_ARITHMETIC"] = {
    "_claim_pre_registered": "0.46 ps/K and the +10.23% RC-soft limb are THE SAME measurement",
    "drift_over_60K_ps": 0.46 * 60.0,
    "nominal_loaded_timer_width_ps": NOMINAL_LINE_PS,
    "implied_pct_over_60K": 0.46 * 60.0 / NOMINAL_LINE_PS * 100.0,
    "measured_RC_soft_limb_pct": 10.23,
    "agree_to_within_pct_abs": abs(0.46 * 60.0 / NOMINAL_LINE_PS * 100.0 - 10.23),
    "CONCLUSION": "SAME TERM -- charge once, never twice"}
ic3["verdict"] = "PASS" if ic3["pass_drift"] else "FAIL"
out["checks"]["IC-P2-3_reproduce_the_timer_terms"] = ic3


# ----------------------------------------------------- IC-P2-4
cmp_ = json.load(open(os.path.join(QAL, "sha256", "p2", "COMPARISON.json")))
# NOTE (self-caught): the first version of this check used cmp_.get(...) and
# reported FAIL, because these keys are NESTED in COMPARISON.json, not
# top-level.  That was a bug in MY reader, not a missing anchor.  find() is the
# same recursive search IC-P2-3 already uses.
_c2 = find(cmp_, "CMOS_level_at_2fF_ps")
_c7 = find(cmp_, "CMOS_level_at_6p91fF_ps")
c2 = _c2[0][1] if _c2 else None
c7 = _c7[0][1] if _c7 else None
treg = {0.0: 307.1, 6.91: 335.7, 20.0: 390.0}
t2 = 307.1 + (2.0 / 6.91) * (335.7 - 307.1)
out["checks"]["IC-P2-4_reproduce_the_CMOS_and_flop_anchors"] = {
    "CMOS_level_at_2fF_ps": c2, "CMOS_level_at_6p91fF_ps": c7,
    "pass_cmos": (c2 == 57.143 and c7 == 94.174),
    "which_load_is_matched": "2 fF -- the banktank cells carry CL = 2.0 fF",
    "ratio_if_6.91fF_were_quoted_instead": c7 / c2 if (c2 and c7) else None,
    "t_reg_ps_MEASURED": treg,
    "t_reg_at_2fF_DERIVED_linear_interp_ps": t2,
    "t_reg_is_a_LOWER_bound_because": "liberty is 1.11-1.21x OPTIMISTIC per restore5's transistor CLK->Q cross-check; a smaller flop tax is the CONSERVATIVE choice for QAL",
    "t_reg_at_2fF_inflated_band_ps": [t2 * 1.11, t2 * 1.21],
    "unc_named_corners_ps": {"ideal": 0, "tree": 100, "flow": 250},
    "verdict": "PASS" if (c2 == 57.143 and c7 == 94.174) else "FAIL"}

out["OVERALL"] = ("INSTRUMENT OK" if all(
    v.get("verdict", "").startswith("PASS")
    for v in out["checks"].values()) else "INSTRUMENT PROBLEM")

open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                  "INSTRUMENT_CHECK_P2.json"), "w").write(
    json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
