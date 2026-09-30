#!/usr/bin/env python3
"""Score every row of this run under the FUNCTIONAL commit criterion of
qal/fcrit, reused from disk with no modification: rescore.score_deck with
Trip(qal/fcrit/TRIP.json, "S") -- the wp = 1.12u / wn = 0.74u receiver whose
MEASURED trip fraction runs 0.7281 at 0.20 V down to 0.5179 at 1.50 V -- at the
committed noise budget NB["free"] = 3 sigma = 19.323 mV.

Re-analysis only.  Nothing is re-simulated and nothing in qal/fcrit is written.
"""
import glob, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
QAL = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(QAL, "fcrit"))
from rescore import Trip, score_deck, NB

TRIP = Trip(os.path.join(QAL, "fcrit", "TRIP.json"), "S")
PAT = [1, 1, 1, 0, 1, 0, 0, 1]


def oh_pat(k, i):
    in_hi = (PAT[i] == 1) if (k % 2 == 1) else (PAT[i] == 0)
    return not in_hi


def main():
    out = {"_what": "qal/cipher rows under the qal/fcrit functional criterion",
           "trip_tag": "S", "trip_wp": TRIP.wp, "trip_wn": TRIP.wn,
           "NB_name": "free", "NB_mV": round(1000 * NB["free"], 3), "rows": {}}
    for p in sorted(glob.glob(os.path.join(HERE, "btk", "c_m10_T150_H4_dv1650_*.cir"))):
        b = os.path.basename(p)[:-4]
        if not os.path.exists(p + ".prn"):
            continue
        r = score_deck(p, 4, 8, oh_pat, TRIP, NB["free"], label=b)
        links = r.pop("links")
        r["worst_S3_margin_mV"] = min(L["S3_margin_mV"] for L in links)
        r["worst_S3_link"] = min((L["S3_margin_mV"], L["k"], L["i"]) for L in links)[1:]
        r["worst_S1_settle_pct"] = min(L["settle_pct"] for L in links
                                       if L["settle_pct"] is not None)
        r["fail_list"] = [dict(k=L["k"], i=L["i"], mode=L["S3_mode"],
                               margin_mV=L["S3_margin_mV"],
                               crosses_at_ps=L["crosses_at_ps"])
                          for L in links if not L["S3_pass"]]
        out["rows"][b] = r
        print("%-56s S1 %2d/%2d  VAL %2d/%2d  S2 %2d/%2d  S3 %2d/%2d  "
              "ROW_S3=%-5s worst_S3=%+8.3f mV  (budget %.3f mV)"
              % (b, r["S1_pass"], r["n_gates"], r["value_guard_pass"], r["n_gates"],
                 r["S2_pass"], r["n_gates"], r["S3_pass"], r["n_gates"],
                 r["ROW_S3"], r["worst_S3_margin_mV"], 1000 * NB["free"]))
        if r["fail_list"]:
            for f in r["fail_list"][:6]:
                print("      FAIL bank%d gate%d %-12s margin %+8.3f mV  crosses at %s ps"
                      % (f["k"], f["i"], f["mode"], f["margin_mV"], f["crosses_at_ps"]))
    json.dump(out, open(os.path.join(HERE, "SCORE.json"), "w"), indent=1)
    print("\nwrote SCORE.json")


if __name__ == "__main__":
    main()
