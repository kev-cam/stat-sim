#!/usr/bin/env python3
"""PHASE 2 runner: the CALIBRATED-SCHEDULE eye at a given beat period T.

Two modes, exactly as PRE_REGISTERED_P2.json B2/B4 declare:

  calib T        -- probe the CALIBRATION pattern (P3, Hamming weight 4, the
                    centred pattern) with the FULL 8-run sequential true-ZCS
                    protocol at this T, and A6-gate that probe.  Writes
                    zeros_calib_T<T>_H<H>.json.

  row T PAT      -- run data pattern PAT on the CALIBRATION pattern's schedule.
                    This is the ONE new declared override versus Phase 1: the
                    zeros vector handed to bt.do_row is the calibration
                    pattern's, NOT the running pattern's.  A real machine has
                    one calibrated timer; Phase 1's per-pattern re-probe was an
                    oracle.  A6 is EXPECTED to fail here for off-centre
                    patterns and the residual |I(L)| is REPORTED as the measured
                    cost of a calibrated timer, not treated as an error.

  oracle T PAT   -- control: pattern PAT on its OWN re-probed zeros, i.e. Phase
                    1's protocol at this T.  Used only where the oracle-to-
                    calibrated difference is being isolated.

Everything else -- netlist, cells, .print/.measure lists, tg15p triple, A6
tank-referenced park, 1F-integrator metering, probe protocol -- is bt.py's,
imported verbatim through Phase 1's eyeharness.py.
"""
import json, os, sys

sys.path.insert(0, "/usr/local/src/stat-sim/qal/eye")
import eyeharness as EH                       # noqa: E402  (Phase 1's harness)

M, DV, MODE = 10.0, 1.65, "free"
PSTEP, MSTEP = 0.05, 0.10                     # identical to Phase 1
CALIB = "P3"                                  # weight 4, the centred pattern
HERE = os.path.dirname(os.path.abspath(__file__))


def zpath(T, H):
    return os.path.join(HERE, "zeros_calib_T%g_H%d.json" % (T, H))


def a6(z, S, mt0):
    """The inherited A6 gate, unchanged: |I(L)| at every commanded open."""
    import re
    d = {}
    for ln in open(mt0):
        m = re.match(r"\s*(\S+)\s*=\s*(\S+)", ln)
        if m:
            try:
                d[m.group(1).lower()] = float(m.group(2))
            except ValueError:
                pass
    out = {}
    for k in range(1, 5):
        for nm in ("iz%d" % k, "izq%d" % k):
            if nm in d:
                out[nm + "_uA"] = d[nm] * 1e6
    w = max([abs(v) for v in out.values()] or [0.0])
    out["worst_abs_uA"] = w
    out["A6_pass_1uA"] = w <= 1.0
    return out


def do_calib(T, H):
    sub = os.path.join(HERE, "T%g_H%d" % (T, H), "CALIB_" + CALIB)
    os.makedirs(sub, exist_ok=True)
    EH.redirect(); EH.bt.HERE = sub
    EH.set_pattern(EH.PATTERNS[CALIB]); EH.set_steps(PSTEP, MSTEP)
    EH.bt.TPROBE, EH.bt.HPROBE = T, H
    print("=== CALIBRATION probe %s (w4) T=%g H=%d dv=%g FULL 8-run ==="
          % (CALIB, T, H, DV), flush=True)
    if os.path.exists(zpath(T, H)):
        print("  zeros already present, reusing", flush=True)
        return 0
    z = EH.bt.do_probe(M, DV, T=T, H=H)
    if z is None:
        print("  F1: PROBE FAILED -- no zero found", flush=True)
        return 1
    z.update(calibration_pattern=CALIB, calibration_bits=EH.PATTERNS[CALIB],
             T=T, H=H, mstep_ps=MSTEP, probe_protocol="full8_sequential")
    # A6-gate the calibration probe itself (PRE_REGISTERED F2)
    p, S = EH.bt.do_row(M, T, H, DV, MODE, z)
    if p is None:
        print("  ROW FAILED on the calibration pattern", flush=True)
        return 1
    z["calib_row_A6"] = a6(z, S, p + ".mt0")
    z["calib_row_prn"] = p + ".prn"
    open(zpath(T, H), "w").write(json.dumps(z, indent=1))
    open(os.path.join(sub, "sched.json"), "w").write(
        json.dumps(dict(S, pattern=CALIB, prn=p + ".prn"), indent=1, default=str))
    print("  calib A6:", json.dumps(z["calib_row_A6"]), flush=True)
    return 0


def do_row(T, H, pname, oracle=False):
    tag = "ORACLE_" if oracle else ""
    sub = os.path.join(HERE, "T%g_H%d" % (T, H), tag + pname)
    os.makedirs(sub, exist_ok=True)
    EH.redirect(); EH.bt.HERE = sub
    EH.set_pattern(EH.PATTERNS[pname]); EH.set_steps(PSTEP, MSTEP)
    EH.bt.TPROBE, EH.bt.HPROBE = T, H
    print("=== %s%s bits=%s T=%g H=%d ===" % (tag, pname,
          EH.PATTERNS[pname], T, H), flush=True)
    if oracle:
        zp = os.path.join(sub, "zeros_own.json")
        if os.path.exists(zp):
            z = json.load(open(zp))
        else:
            z = EH.bt.do_probe(M, DV, T=T, H=H)
            if z is None:
                print("  F1: PROBE FAILED", flush=True); return 1
            open(zp, "w").write(json.dumps(z, indent=1))
        schedule_source = "OWN re-probed zeros (Phase-1 oracle protocol)"
    else:
        if not os.path.exists(zpath(T, H)):
            print("  no calibration zeros at this T -- run 'calib' first",
                  flush=True)
            return 1
        z = json.load(open(zpath(T, H)))
        schedule_source = ("CALIBRATION pattern %s zeros (single fixed timer)"
                           % CALIB)
    p, S = EH.bt.do_row(M, T, H, DV, MODE, z)
    if p is None:
        print("  ROW FAILED", flush=True); return 1
    S = dict(S)
    S.update(pattern=pname, pattern_bits=EH.PATTERNS[pname],
             schedule_source=schedule_source,
             tzr_used=z["tzr"], tzq_used=z["tzq"],
             prn=p + ".prn", mt0=p + ".mt0", T=T, H=H,
             A6_residual=a6(z, S, p + ".mt0"))
    open(os.path.join(sub, "sched.json"), "w").write(
        json.dumps(S, indent=1, default=str))
    print("  OK -> %s   A6 residual worst %.4f uA (pass=%s)"
          % (p + ".prn", S["A6_residual"]["worst_abs_uA"],
             S["A6_residual"]["A6_pass_1uA"]), flush=True)
    return 0


def do_stress(T, H, pname, off_ps):
    """STRESS TEST: pattern PAT on the calibration schedule DELIBERATELY
    MIS-TIMED by off_ps on the rail-raise OPEN instant.

    This is how the inherited 61.6 ps term is charged at THIS operating point
    instead of being extrapolated.  The timer sets o_k = c_k + tzr_k, so a timer
    error is exactly an offset on tzr.  A p-p spread of S ps seen by a timer
    calibrated at the CENTRE is at most +/- S/2."""
    sub = os.path.join(HERE, "T%g_H%d" % (T, H),
                       "STRESS_%s_%+.3fps" % (pname, off_ps))
    os.makedirs(sub, exist_ok=True)
    EH.redirect(); EH.bt.HERE = sub
    EH.set_pattern(EH.PATTERNS[pname]); EH.set_steps(PSTEP, MSTEP)
    EH.bt.TPROBE, EH.bt.HPROBE = T, H
    z = json.load(open(zpath(T, H)))
    z = dict(z)
    z["tzr"] = [x + off_ps for x in z["tzr"]]
    print("=== STRESS %s T=%g H=%d  tzr offset %+.3f ps ==="
          % (pname, T, H, off_ps), flush=True)
    p, S = EH.bt.do_row(M, T, H, DV, MODE, z)
    if p is None:
        print("  ROW FAILED", flush=True); return 1
    S = dict(S)
    S.update(pattern=pname, pattern_bits=EH.PATTERNS[pname],
             schedule_source="CALIBRATION zeros DELIBERATELY OFFSET by %+.3f ps"
                             " on the rail-raise OPEN instant (timer-error"
                             " stress test)" % off_ps,
             stress_offset_ps=off_ps,
             tzr_used=z["tzr"], tzq_used=z["tzq"],
             prn=p + ".prn", mt0=p + ".mt0", T=T, H=H,
             A6_residual=a6(z, S, p + ".mt0"))
    open(os.path.join(sub, "sched.json"), "w").write(
        json.dumps(S, indent=1, default=str))
    print("  OK -> %s   A6 residual worst %.4f uA"
          % (p + ".prn", S["A6_residual"]["worst_abs_uA"]), flush=True)
    return 0


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "calib":
        sys.exit(do_calib(float(a[1]), int(a[2])))
    if a[0] == "row":
        sys.exit(do_row(float(a[1]), int(a[2]), a[3]))
    if a[0] == "oracle":
        sys.exit(do_row(float(a[1]), int(a[2]), a[3], oracle=True))
    if a[0] == "stress":
        sys.exit(do_stress(float(a[1]), int(a[2]), a[3], float(a[4])))
    print(__doc__); sys.exit(2)
