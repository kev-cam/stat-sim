#!/usr/bin/env python3
"""Value check re-scored against a FIXED decision threshold.

bt.py's extract() decides each gate against 0.5 * (that bank's OWN delivered
rail).  That is the committed convention and it is right for banks whose rail is
loaded normally.  It misleads for the ALTI diagnostic, whose tgi bank has no
control inverter and therefore almost no rail load, so its tank overshoots to
0.985 V and the 0.5*rail threshold rises with it.  Re-scored here against
0.5 * 0.7138163 V (the committed nominal delivered rail) as well, and both are
reported.  Nothing is re-simulated; only the decision rule changes, and it is
stated."""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
VNOM = 0.7138163
OUT = {}
for nm in ("CTL_vhi", "ALT_vhi", "ALTB_vhi", "ALTI_vhi", "ALT_rail"):
    d = json.load(open(os.path.join(HERE, "CH_%s.json" % nm)))
    row = dict(comp=d["comp"], sep_mV=d["separation_by_depth_mV"],
               rail_V=d["rail_at_own_boundary_V"],
               VALUE_own_rail=d["VALUE_CHECK"], banks={})
    allok = True
    for k in "1234":
        b = d["banks"][k]
        ok = True
        for g, x in b["per_gate"].items():
            thr = 0.5 * VNOM
            good = (x["v"] > thr) if x["want_hi"] else (x["v"] < thr)
            ok &= good
        row["banks"][k] = dict(kind=b["kind"], rail_V=b["rail_V"],
                               min_HIGH_V=b["min_HIGH_V"], max_LOW_V=b["max_LOW_V"],
                               correct_own_rail=b["all_correct"],
                               correct_fixed_thr=bool(ok),
                               pct_of_NOMINAL_rail=(100.0 * b["min_HIGH_V"] / VNOM))
        allok &= ok
    row["VALUE_fixed_thr"] = bool(allok)
    OUT[nm] = row
    print("%-10s VALUE(own rail)=%-5s VALUE(fixed 0.5*0.7138)=%-5s  sep %s"
          % (nm, row["VALUE_own_rail"], row["VALUE_fixed_thr"],
             [round(x, 1) for x in row["sep_mV"]]))
    for k in "1234":
        b = row["banks"][k]
        print("     bank%s %-4s rail %.4f  minHI %.5f (%5.1f%% of NOMINAL)  own=%-5s fixed=%s"
              % (k, b["kind"], b["rail_V"], b["min_HIGH_V"],
                 b["pct_of_NOMINAL_rail"], b["correct_own_rail"], b["correct_fixed_thr"]))
json.dump(OUT, open(os.path.join(HERE, "THRESH.json"), "w"), indent=1)
print("wrote THRESH.json")
