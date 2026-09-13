#!/usr/bin/env python3
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# SPDX-FileCopyrightText: 2026 D. Kevin Cameron
# Noncommercial use is free; commercial use needs a license -- see COMMERCIAL.md.
"""
stat-sim sweep -- find the critical paths by raising the clock until the flops
cannot keep up.  The design bound by bind.py is simulated at a list of clock
periods with the same random vectors; at every rising edge the probe records
each flop's D-node px (1 = still moving at the capture instant) and every
output.  Against the slowest run as the reference, the first period at which
a flop's D shows px, and the first period at which an output differs, name
the endpoints of the critical paths -- and the flops' fan-in cones in the
netlist are the paths.

    sweep.py build/gcd --top gcd [--periods 4,3,2.5,2,1.8,1.6,1.4,1.2,1,0.9,0.8] [--cycles 300]
"""
import os
import re
import subprocess
import sys

NVC = os.environ.get("NVC", "/usr/local/src/nvc/build/bin/nvc")
NVCLIB = os.environ.get("NVCLIB", "/usr/local/src/nvc/build/lib")
STATSIM = os.path.join(os.path.dirname(os.path.abspath(__file__)), "build")


def run(outdir, top, period_ns, cycles, seed=1):
    work = "--work=dut:%s" % os.path.abspath(os.path.join(outdir, "dut"))
    base = [NVC, "--std=2040", "-M", "512m", "-L", NVCLIB, "-L", STATSIM, work]
    trace = os.path.abspath(os.path.join(outdir, "trace_%g.txt" % period_ns))
    r = subprocess.run(base + ["-e", "%s_tb" % top, "-gPERIOD=%gns" % period_ns, "-gSEED=%d" % seed, "-gCYCLES=%d" % cycles, "-gTRACE=%s" % trace,
                                "-r", "--stop-time=%dus" % max(1, int(period_ns * cycles * 1.5e-3) + 1)],
                       capture_output=True, text=True, cwd=outdir, timeout=3600)
    if not os.path.exists(trace):
        raise RuntimeError("no trace for %g ns: %s" % (period_ns, (r.stdout + r.stderr)[-500:]))
    rows = [ln.split() for ln in open(trace) if ln.strip()]
    return {int(c): (f, o) for c, f, o in rows if len(o) > 0} if rows and len(rows[0]) == 3 else {int(r[0]): (r[1], "") for r in rows}


def main():
    a = sys.argv[1:]
    outdir = a[0]; top = a[a.index("--top") + 1]
    periods = [float(x) for x in (a[a.index("--periods") + 1] if "--periods" in a else "8,6,5,4.5,4,3.5,3,2.5,2,1.6,1.2").split(",")]
    cycles = int(a[a.index("--cycles") + 1]) if "--cycles" in a else 300
    warm = int(a[a.index("--warm") + 1]) if "--warm" in a else 8
    flops = [ln.split()[0] for ln in open(os.path.join(outdir, "flops.txt")) if ln.strip()]
    outs = [ln.strip() for ln in open(os.path.join(outdir, "outputs.txt")) if ln.strip()]
    # analyse once
    work = "--work=dut:%s" % os.path.abspath(os.path.join(outdir, "dut"))
    r = subprocess.run([NVC, "--std=2040", "-M", "512m", "-L", NVCLIB, "-L", STATSIM, work, "-a"] + [os.path.join(outdir, f) for f in ("cells.vhd", "top.vhd", "tb.vhd")], capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit("nvc analysis failed:\n" + (r.stdout + r.stderr)[-1500:])
    ref = None
    first_px = {}; first_mismatch = {}
    print("%8s %10s %12s   %s" % ("period", "flops w/px", "outputs off", "first hazards / mismatches"))
    for per in sorted(periods, reverse=True):
        tr = run(outdir, top, per, cycles)
        if ref is None:
            ref = tr
        px_flops = {}; bad_outs = {}
        for c, (f, o) in tr.items():
            if c < warm:
                continue                       # reset and the first vectors: nodes still floating
            for k, ch in enumerate(f):
                if ch == "1":
                    px_flops[k] = px_flops.get(k, 0) + 1
            if c in ref:
                fo = ref[c][1]
                for k, (x, y) in enumerate(zip(o, fo)):
                    if x != y and y != "X":
                        bad_outs[k] = bad_outs.get(k, 0) + 1
        for k in px_flops:
            first_px.setdefault(flops[k], per)
        for k in bad_outs:
            first_mismatch.setdefault(outs[k], per)
        new_px = [flops[k] for k in px_flops if first_px[flops[k]] == per]
        new_bad = [outs[k] for k in bad_outs if first_mismatch[outs[k]] == per]
        print("%7.2f ns %10d %12d   %s%s" % (per, len(px_flops), len(bad_outs),
              ("px first at: " + ", ".join(sorted(new_px)[:6]) + (" ..." if len(new_px) > 6 else "")) if new_px else "",
              ("  outputs first off: " + ", ".join(sorted(new_bad)[:6])) if new_bad else ""))
    if first_px:
        worst = sorted(first_px.items(), key=lambda kv: -kv[1])[:8]
        print("critical endpoints (the flops whose D is first caught moving, slowest period first): %s" % ", ".join("%s @ %g ns" % kv for kv in worst))
    else:
        print("no flop showed px down to %g ns" % min(periods))


if __name__ == "__main__":
    main()
