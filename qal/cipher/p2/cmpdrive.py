#!/usr/bin/env python3
"""qal/cipher/p2/cmpdrive.py -- run both CMOS comparators for a measured QAL row,
at the supplies gate G9 requires, and write the paired comparison.

GATE G9 says the CMOS supply is the QAL variant's OWN MEASURED delivered rail
peak.  A multi-level chain has one peak PER LEVEL, and there is no single choice
that is conservative in both directions:

  * a HIGHER supply costs CMOS more energy (E = C V^2), which FAVOURS QAL;
  * a LOWER supply makes CMOS SLOWER, which also favours QAL on speed.

So both ends are run and reported as a BRACKET rather than one number being
chosen and the choice being hidden.  The headline energy ratio is quoted at the
MINIMUM rail peak, which is the LEAST energy CMOS can be charged under G9 and
therefore the hardest case for QAL; the headline speed ratio is quoted at the
MAXIMUM rail peak, which is the FASTEST CMOS can be under G9 and again the
hardest case for QAL.  Both extremes are in the JSON.
"""
import json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def run_one(kind, name, vdd, cw):
    cmd = [sys.executable, os.path.join(HERE, "run.py"), kind, name,
           "%.6f" % vdd, "%g" % cw]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=HERE,
                       timeout=7200)
    ok = r.returncode == 0
    print("   %s %s vdd=%.4f -> %s" % (kind, name, vdd,
                                       "ok" if ok else "FAIL"), flush=True)
    if not ok:
        print("     ", r.stdout.strip()[-300:])
    return ok


def main(rowfile):
    row = json.load(open(rowfile))
    if row.get("status") != "OK":
        raise SystemExit("%s is not an OK row" % rowfile)
    name = row["vehicle"]
    veh = {"aes_addroundkey": "aes", "qrxor_w32_r16": "qrxor",
           "ks_w8": "ks8", "ripple_w8": "rip8", "ks_w32": "ks32"}.get(name, name)
    cw = row["cw_per_bit_fF"]
    peaks = [v for v in row["rail_peak_V"].values()]
    vmin, vmax = min(peaks), max(peaks)
    print("== %s  cw=%g  rail peaks %s -> bracket [%.4f, %.4f] V"
          % (row["tag"], cw, [round(p, 4) for p in peaks], vmin, vmax), flush=True)
    done = []
    for vdd in sorted({round(vmin, 6), round(vmax, 6)}):
        for kind in ("twin", "nat"):
            if run_one(kind, veh, vdd, cw):
                done.append((kind, vdd))
    return done


if __name__ == "__main__":
    for f in sys.argv[1:]:
        main(f if os.path.isabs(f) else os.path.join(HERE, f))
