#!/usr/bin/env python3
"""One data pattern end to end, in its OWN subdirectory so nothing collides and
three patterns can run concurrently.

  1. RE-PROBE the true-ZCS zeros at T = 200 ps, H = 4, dv = 1.65 with the FULL
     8-run sequential protocol (bt.do_probe).  The committed
     zeros_m10_dv1650.json is at T_probe = 120 ps and does NOT transfer: the
     committed T=200 row reports A6_zcs_pass = FALSE.  See PRE_REGISTERED.json
     STEP_c_EYE_PROTOCOL.
  2. Run the measured row.
  3. Write zeros_<P>.json and sched_<P>.json.  The eye is extracted later from
     the .prn -- ONE transient, swept by reading the waveform.

Usage: python3 run_pattern.py P3
"""
import json, os, sys
import eyeharness as EH

M, T, H, DV, MODE = 10.0, 200.0, 4, 1.65, "free"
PSTEP, MSTEP = 0.05, 0.10          # PRE_REGISTERED TIME_RESOLUTION


def main(pname):
    bits = EH.PATTERNS[pname]
    sub = os.path.join(EH.HERE, pname)
    os.makedirs(sub, exist_ok=True)
    EH.redirect()
    EH.bt.HERE = sub                       # every .cir/.prn for this pattern
    EH.set_pattern(bits)
    EH.set_steps(PSTEP, MSTEP)
    print("=== %s bits=%s  T=%g H=%d dv=%g  grid=%g ps ==="
          % (pname, bits, T, H, DV, MSTEP), flush=True)

    # AMENDMENT E2: FULL 8-run sequential protocol for P0 (the committed pattern,
    # the anchor back to the instrument); the COMMITTED, already-validated 4-run
    # odd/even reduction for the rest -- taken at THIS study's own T=200, H=4,
    # not at bt.py's inherited 120 ps reference -- with the unchanged A6 gate as
    # the catch.  A pattern whose row fails A6 is RE-PROBED in full.
    EH.bt.TPROBE, EH.bt.HPROBE = T, H
    full = (pname == "P0") or ("--full" in sys.argv)
    zp = os.path.join(sub, "zeros.json")
    if os.path.exists(zp):
        z = json.load(open(zp))
        print("  reusing zeros", z["tzr"], flush=True)
    else:
        z = EH.bt.do_probe(M, DV, T=T, H=H) if full \
            else EH.bt.do_probe_oddeven(M, DV)
        if z is None:
            print("  PROBE FAILED"); return 1
        z["pattern"] = pname
        z["pattern_bits"] = bits
        z["mstep_ps"] = MSTEP
        z["probe_protocol"] = "full8_sequential" if full else "oddeven4_at_T200_H4"
        open(zp, "w").write(json.dumps(z, indent=1))

    p, S = EH.bt.do_row(M, T, H, DV, MODE, z)
    if p is None:
        print("  ROW FAILED"); return 1
    S = dict(S)
    S["pattern"] = pname
    S["pattern_bits"] = bits
    S["prn"] = p + ".prn"
    S["mt0"] = p + ".mt0"
    open(os.path.join(sub, "sched.json"), "w").write(
        json.dumps(S, indent=1, default=str))
    print("  OK ->", p + ".prn", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
