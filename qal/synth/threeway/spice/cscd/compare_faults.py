#!/usr/bin/env python3
"""Golden vs fault-injected supply-current signatures, window by window.

Reports the separation a current sensor would have to resolve, expressed as
(a) the fractional change in per-window dynamic charge, (b) the change in the
quiescent floor, and (c) whether either exceeds the golden vector-to-vector
spread (the real noise floor)."""
import sys, json, os

def load(p): return json.load(open(p))

def main(goldp, faults):
    g = load(goldp)
    gw = {w["window"]: w for w in g["windows"]}
    print("=== quiescent floor (end of window), nA ===")
    hdr = "%-3s %-22s %7s %10s" % ("W", "vector", "togs", "golden")
    for f, _ in faults: hdr += " %12s" % f
    print(hdr)
    for k in sorted(gw):
        w = gw[k]
        line = "%-3d %-22s %7s %10.4f" % (k, w["name"], w["net_toggles"],
                                          w["I_quiescent_A"] * 1e9)
        for f, d in faults:
            fw = {x["window"]: x for x in d["windows"]}[k]
            line += " %9.4f(%+.0f%%)" % (fw["I_quiescent_A"] * 1e9,
                100 * (fw["I_quiescent_A"] / w["I_quiescent_A"] - 1))
        print(line)

    print()
    print("=== per-window dynamic charge, fC ===")
    print(hdr)
    for k in sorted(gw):
        w = gw[k]
        line = "%-3d %-22s %7s %10.3f" % (k, w["name"], w["net_toggles"],
                                          w["Q_dynamic_C"] * 1e15)
        for f, d in faults:
            fw = {x["window"]: x for x in d["windows"]}[k]
            gq = w["Q_dynamic_C"] * 1e15
            line += " %9.3f(%+.0f%%)" % (fw["Q_dynamic_C"] * 1e15,
                100 * (fw["Q_dynamic_C"] / w["Q_dynamic_C"] - 1) if gq else 0)
        print(line)

    print()
    print("=== peak current, mA ===")
    print(hdr)
    for k in sorted(gw):
        w = gw[k]
        line = "%-3d %-22s %7s %10.4f" % (k, w["name"], w["net_toggles"],
                                          w["I_peak_A"] * 1e3)
        for f, d in faults:
            fw = {x["window"]: x for x in d["windows"]}[k]
            line += " %9.4f(%+.0f%%)" % (fw["I_peak_A"] * 1e3,
                100 * (fw["I_peak_A"] / w["I_peak_A"] - 1))
        print(line)

    # the noise floor: golden spread across DATA vectors with similar activity
    act = [w for w in g["windows"] if (w["net_toggles"] or 0) > 0]
    if act:
        qs = [w["Q_dynamic_C"] * 1e15 for w in act]
        ts = [w["net_toggles"] for w in act]
        print()
        print("=== golden data variation (active windows only) ===")
        print("  dynamic charge fC: min=%.3f max=%.3f  ratio=%.2fx" % (min(qs), max(qs), max(qs)/min(qs)))
        print("  net toggles      : min=%d max=%d  ratio=%.2fx" % (min(ts), max(ts), max(ts)/min(ts)))
        print("  charge per toggle: %s" % ", ".join("%.2f" % (q/t) for q, t in zip(qs, ts)))
        iqs = [w["I_quiescent_A"] * 1e9 for w in g["windows"]]
        print("  quiescent floor nA over ALL windows: min=%.4f max=%.4f spread=%.1f%%"
              % (min(iqs), max(iqs), 100 * (max(iqs)/min(iqs) - 1)))

if __name__ == "__main__":
    gold = sys.argv[1]
    fl = []
    for a in sys.argv[2:]:
        nm, p = a.split("=", 1)
        fl.append((nm, load(p)))
    main(gold, fl)
