#!/usr/bin/env python3
"""SK1 step 1: the CALIBRATION probe.  FULL 8-run sequential true-ZCS protocol on
the centred weight-4 pattern P3 at T=200, H=4, dV=1.65, exactly as Phase 2's
calibration does -- because a real machine has ONE timer, not a per-pattern
oracle.  Writes zeros_skeptic_T200_H4.json.

The reduced oddeven4 protocol is NOT used: the audited study MEASURED that it
fails bt.py's own A6 gate at this swing (13.8-45.0 uA against a 1 uA budget), so
using it would knowingly start from an invalid schedule.
"""
import json, os, sys, time
import skharness as SK

T, H, DV, M = 200.0, 4, 1.65, 10.0

def main():
    d = SK.redirect("CAL")
    SK.set_steps(0.05, 0.10)
    SK.set_pattern(SK.PATTERNS["P3"])
    print("=== SKEPTIC calibration probe: P3 (w4) T=%g H=%d dv=%g FULL 8-run ==="
          % (T, H, DV), flush=True)
    print("cache=%s (built from empty)" % SK.CACHE, flush=True)
    t0 = time.time()
    if not os.path.exists(os.path.join(d, "warm.cir.prn")):
        print("warming PyMS cache from EMPTY ...", flush=True)
        SK.bt.stage_warm()
    z = SK.bt.do_probe(M, DV, T=T, H=H)
    if z is None:
        print("PROBE FAILED"); sys.exit(1)
    z["protocol"] = "full8_sequential_trueZCS"
    z["calibration_pattern"] = "P3"
    z["calibration_bits"] = SK.PATTERNS["P3"]
    z["T_row"], z["H_row"] = T, H
    out = os.path.join(SK.HERE, "zeros_skeptic_T200_H4.json")
    json.dump(z, open(out, "w"), indent=1)
    print("tzr =", ["%.6f" % x for x in z["tzr"]], flush=True)
    print("tzq =", ["%.6f" % x for x in z["tzq"]], flush=True)
    print("wrote %s in %.1fs" % (out, time.time() - t0), flush=True)

if __name__ == "__main__":
    main()
