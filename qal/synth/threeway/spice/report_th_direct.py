#!/usr/bin/env python3
"""Fit report + cross-check for the direct-threshold TH cell characterization.

Reads cell_energy_th_direct.json (written by char_energy_th_direct.py) and prints
E0/k with residuals, delay, and -- for any arc that has a point at a load NOT in
the {1,3,10} fF fit set -- the extrapolation error of the fitted model at that load.
That held-out check is what makes the model trustworthy (th22 was checked this way
to 0.7% at 5 fF).
"""
import json, sys

FITSET = {1.0, 3.0, 10.0}
REF = {  # already-measured cells, for context (char_energy_nominal.py)
    "th22": (39.398, 1.7369), "th12": (23.004, 1.4697), "th13": (31.861, 1.4688),
}


def fit(pts):
    n = len(pts)
    mx = sum(p[0] for p in pts)/n; my = sum(p[1] for p in pts)/n
    den = sum((p[0]-mx)**2 for p in pts)
    k = sum((p[0]-mx)*(p[1]-my) for p in pts)/den if den else 0.0
    return my - k*mx, k


def main():
    db = json.load(open(sys.argv[1] if len(sys.argv) > 1
                        else "cell_energy_th_direct.json"))
    print("%-15s %-8s %9s %9s %9s   %s" %
          ("arc", "cell", "E0_fJ", "k_fJ/fF", "maxresid", "points (CL fF -> E fJ / td ps)"))
    print("-"*118)
    for arc, rec in db["arcs"].items():
        pts = sorted((float(k), v) for k, v in rec["points"].items())
        base = [(cl, v["E_fJ"]) for cl, v in pts if cl in FITSET]
        held = [(cl, v["E_fJ"]) for cl, v in pts if cl not in FITSET]
        if len(base) < 2:
            print("%-15s %-8s  (only %d fit points)" % (arc, rec["cell"], len(base)))
            continue
        E0, k = fit(base)
        resid = [y - (E0 + k*x) for x, y in base]
        ptxt = "  ".join("%g->%.2f/%.0fps" % (cl, v["E_fJ"], v["td_ps"]) for cl, v in pts)
        print("%-15s %-8s %9.4f %9.4f %9.4f   %s" %
              (arc, rec["cell"], E0, k, max(abs(r) for r in resid), ptxt))
        for cl, y in held:
            pred = E0 + k*cl
            print("%-15s   HELD-OUT CROSS-CHECK CL=%gfF: measured %.4f  predicted %.4f"
                  "  err %+.4f fJ (%+.2f%%)"
                  % ("", cl, y, pred, y-pred, 100*(y-pred)/y))
    print()
    print("sanity (yend should be ~0 = full return to NULL; ymax ~1.2 if the arc fires,"
          " ~0 if it does not):")
    for arc, rec in db["arcs"].items():
        for cl, v in sorted((float(k), v) for k, v in rec["points"].items()):
            flag = ""
            if abs(v["yend"]) > 0.05: flag += " <-- DID NOT RETURN TO NULL"
            if rec["fires_output"] and v["ymax"] < 0.9: flag += " <-- EXPECTED FIRE, DID NOT"
            if not rec["fires_output"] and v["ymax"] > 0.3: flag += " <-- UNEXPECTED GLITCH"
            print("  %-15s CL=%5g  ymax=%7.4f yend=%9.5f%s" % (arc, cl, v["ymax"], v["yend"], flag))


if __name__ == "__main__":
    main()
