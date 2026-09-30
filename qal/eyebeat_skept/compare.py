#!/usr/bin/env python3
"""Side-by-side: my re-run (T{T}/SKX.json) vs the sweep's claims
(qal/eyebeat/T{T}/EYEBEAT.json).  Deviations in ps/mV/V per field."""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
EB = "/usr/local/src/stat-sim/qal/eyebeat"
T = sys.argv[1]

mine = json.load(open(os.path.join(HERE, "T%s" % T, "SKX.json")))
ref = json.load(open(os.path.join(EB, "T%s" % T, "EYEBEAT.json")))

print("=== T=%s: skeptic re-run vs sweep claim ===" % T)
print("A6 mine:", {p: v["worst_uA"] for p, v in mine["a6"].items()},
      " sweep:", {p: v["worst_uA"] for p, v in ref["a6"].items()})
mv = {p: v["bits_wrong"] for p, v in mine["value_check"].items()}
rv = {p: (0 if v["all_32_gates_value_correct"] else len(v["fails"]))
      for p, v in ref["value_check"].items()}
print("value bits wrong mine:", mv, " sweep:", rv)
worst_dev = {}
for k in ("1", "2", "3"):
    mb, rb = mine["banks"][k], ref["banks"][k]
    for tn in ("0mV", "3sigma"):
        mz = mb["EYES"]["EYE2"].get(tn, {})
        rz = rb["EYES"]["EYE2"].get(tn, {})
        if "EYE" in mz or "EYE" in rz:
            print("bank%s %-7s mine %s sweep %s" %
                  (k, tn, "EMPTY" if "EYE" in mz else "eye",
                   "EMPTY" if "EYE" in rz else "eye"))
            continue
        rows = []
        for f, scale in (("opening_minus_c_ps", 1), ("WIDTH_ps", 1),
                         ("setup_slack_ps", 1),
                         ("HEIGHT_at_sampling_HIGH_mV", 1),
                         ("HEIGHT_at_sampling_LOW_mV", 1)):
            a, b = mz.get(f), rz.get(f)
            if a is None or b is None:
                continue
            d = a - b
            rows.append("%s %+.4f" % (f.split("_")[0], d))
            worst_dev[f] = max(worst_dev.get(f, 0.0), abs(d))
        clip = "LBm" if mz.get("WIDTH_IS_LOWER_BOUND") else "   "
        clip += "/LBs" if rz.get("WIDTH_IS_LOWER_BOUND") else "/  "
        print("bank%s %-7s open_c %9.4f vs %9.4f  W %9.3f vs %9.3f %s | dev: %s"
              % (k, tn, mz["opening_minus_c_ps"], rz["opening_minus_c_ps"],
                 mz["WIDTH_ps"], rz["WIDTH_ps"], clip, "  ".join(rows)))
    mf, rf = mb["POST_RETURN_FLOOR_EYE2"], rb["POST_RETURN_FLOOR_EYE2"]
    print("bank%s floor mine %9.4f mV @r+%7.2f | sweep %9.4f @r+%7.2f | dev %+8.4f"
          % (k, mf["floor_mV"], mf["at_t_minus_r_ps"],
             rf["floor_mV"], rf["at_t_minus_r_ps"],
             mf["floor_mV"] - rf["floor_mV"]))
    ms, rs = mb["STRANDED_HIGH"], rb["STRANDED_HIGH"]
    print("bank%s strand mine %.5f V sweep %.5f V dev %+.5f | droop med mine %s sweep %s"
          % (k, ms["min_HIGH_during_drain_V"], rs["min_HIGH_during_drain_V"],
             ms["min_HIGH_during_drain_V"] - rs["min_HIGH_during_drain_V"],
             ms["droop_slope_mV_per_ps"] and ms["droop_slope_mV_per_ps"]["median"],
             rs["droop_slope_mV_per_ps"] and rs["droop_slope_mV_per_ps"]["median"]))
    mt, rt = mb["TRACKING_LAG"], rb["TRACKING_LAG"]
    for f_m, f_r in (("rising_LAG_A_ps",) * 2, ("rising_LAG_B_ps", "rising_LAG_B_rail_to_data_ps"),
                     ("draining_LAG_A_ps",) * 2):
        a, b = mt.get(f_m), rt.get(f_r)
        if a and b:
            print("bank%s %-18s med mine %8.4f sweep %8.4f dev %+8.4f (n %d vs %d)"
                  % (k, f_m[:18], a["median"], b["median"],
                     a["median"] - b["median"], a["n"], b["n"]))
    print("bank%s censored mine %d sweep %d" %
          (k, mt["draining_censored"], rt["draining_censored_gates"]))
print("worst eye-field deviations:", {f: round(v, 4) for f, v in worst_dev.items()})
