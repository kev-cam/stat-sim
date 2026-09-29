#!/usr/bin/env python3
"""Correct a criterion I got wrong in a mid-run patch, and report both readings.

When dV became a parameter I scaled the pre-registered C2/C3 thresholds by dV.
That is WRONG for C3 on my own stated rationale: C3's threshold (0.60 V) was
pre-registered as an ABSOLUTE floor, justified by the MEASURED functional cliff
at dV=0.6 where the cell pMOS never clears Vt -- a device-threshold phenomenon,
not a fraction of the pre-charge.  C2's pre-registered form (VA_open <= 0.09778
+ 0.05 V, the AMENDMENT.md A1 rule) is likewise written as an absolute voltage,
though "the rail drained" is arguably a fraction-of-dV notion.

This pass recomputes both readings for every row and takes FUNCTIONAL on the
ABSOLUTE (pre-registered, harsher) forms.  Nothing is dropped: the relative
reading is reported beside it on every row.
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
C2_ABS, C3_ABS = 0.1478, 0.60


def main():
    fn = os.path.join(HERE, "rows.json")
    R = json.load(open(fn))
    n = 0
    for tag, r in sorted(R.items()):
        if "error" in r:
            continue
        dv = r.get("dv", 1.0)
        va, vb = r["VA_open"], r["VBEND"]
        c2a, c2r = va <= C2_ABS, va <= C2_ABS * dv
        c3a, c3r = vb >= C3_ABS, vb >= C3_ABS * dv
        c1e = r["C1_settle_end"] == "PASS"
        c4 = r["C4_instrument"] == "PASS"
        c1v = r.get("C1_settle90_reached", "PASS") == "PASS"
        r["C2_rail_drain_abs"] = "PASS" if c2a else "FAIL"
        r["C2_rail_drain_rel_dv"] = "PASS" if c2r else "FAIL"
        r["C3_swing_abs"] = "PASS" if c3a else "FAIL"
        r["C3_swing_rel_dv"] = "PASS" if c3r else "FAIL"
        r["C2_rail_drain"] = r["C2_rail_drain_abs"]
        r["C3_swing"] = r["C3_swing_abs"]
        r["FUNCTIONAL"] = "YES" if (c1e and c1v and c2a and c3a and c4) else "NO"
        r["FUNCTIONAL_rel_dv"] = "YES" if (c1e and c1v and c2r and c3r and c4) else "NO"
        fails = [n for n, ok in (("C1_end", c1e), ("C1_valid", c1v),
                                 ("C2_drain", c2a), ("C3_swing", c3a),
                                 ("C4_instr", c4)) if not ok]
        r["fails"] = fails
        n += 1
    json.dump(R, open(fn, "w"), indent=1)
    print("refixed %d rows" % n)
    print("%-20s %5s %8s %8s %8s %8s %6s %6s %-22s"
          % ("tag", "dv", "VAopen", "VBEND", "t_hop", "t_levelC", "abs", "rel", "fails(abs)"))
    for tag, r in sorted(R.items(), key=lambda kv: (kv[1].get("dv", 1.0),
                                                    -kv[1]["L_nH"],
                                                    kv[1]["total_um"])):
        if "error" in r:
            continue
        print("%-20s %5.2f %8.4f %8.4f %8.3f %8.2f %6s %6s %-22s"
              % (tag, r.get("dv", 1.0), r["VA_open"], r["VBEND"], r["t_hop_ps"],
                 r.get("t_level_cons_ps") or float("nan"),
                 r["FUNCTIONAL"], r["FUNCTIONAL_rel_dv"], ",".join(r["fails"]) or "-"))


if __name__ == "__main__":
    main()
