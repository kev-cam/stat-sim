#!/usr/bin/env python3
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# SPDX-FileCopyrightText: 2026 D. Kevin Cameron
# Part of stat-sim. PolyForm Noncommercial License 1.0.0; commercial use needs a separate license (see LICENSE, COMMERCIAL.md).
"""
radar_nvc.py -- run the phased-array radar (phased_radar.vhd) in nvc --std=2040, in the simulator or with
its RF path moved out to the spectral accelerator, and compare what it finds with where the targets are.

Writes the resolver network for n transmit and n receive elements and three targets, compiles, runs,
and prints per look the range, bearing and radial speed the radar's software found beside the truth.

    radar_nvc.py --nvc /usr/local/src/nvc-build/bin/nvc -n 4                 everything in nvc
    radar_nvc.py -n 4 --accel                                                 the RF path on the accelerator
    radar_nvc.py -n 4 --accel --schedule 0:out,7ms:in,9ms:out                 out, back for 2 ms, out again
    radar_nvc.py -n 4 8 16 32 64 --accel                                      a size sweep
    radar_nvc.py -n 4 --both                                                  nvc, then the accelerator
"""
import argparse
import math
import os
import re
import subprocess
import sys
import tempfile
import time

import ad9361
import ad9361_vhdl
import an2597_nvc as base
import arena_resolver

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCES = ("accel/spectral_accel_%s.vhd", "accel/spectral_accel_pkg.vhd", "rf_spectrum_pkg.vhd", "ad9361_spectral_pkg.vhd",
           "ad9361.vhd", "rf_spec_antenna.vhd", "rf_spec_scatterer.vhd", "ofdm_soft_pkg.vhd", "phased_radar.vhd")
TARGETS = [(120.0, 12.0, 10.0, -40.0), (210.0, -25.0, 30.0, 75.0), (160.0, 45.0, 100.0, 120.0)]   # range, bearing, rcs, speed


def run(args, n, accel, looks=None):
    tmp = tempfile.mkdtemp(prefix="radar_nvc_")
    looks = looks or args.looks
    generics = dict(n=str(n), lo=base.vreal(args.lo), fs=base.vreal(args.fs), ant_dbi=base.vreal(args.ant),
                    sep=base.vreal(args.sep), isolate="true" if args.isolate else "false", pri=base.vreal(args.pri),
                    pulses=str(args.pulses), looks=str(looks), blank=base.vreal(args.blank))
    for i, (r, b, c, v) in enumerate(TARGETS):
        generics.update({"r%d" % i: base.vreal(r), "b%d" % i: base.vreal(b), "c%d" % i: base.vreal(c), "v%d" % i: base.vreal(v)})
    wires = [["g(%d).chip.tx1" % i, "g(%d).ant_tx.feed" % i] for i in range(n)]
    wires += [["g(%d).chip.rx1" % i, "g(%d).ant_rx.feed" % i] for i in range(n)]
    arena = ["g(%d).ant_tx" % i for i in range(n)] + ["g(%d).ant_rx" % i for i in range(n)]
    with open(os.path.join(tmp, "ad9361_pkg.vhd"), "w") as fh:
        fh.write(ad9361_vhdl.emit())
    with open(os.path.join(tmp, "resolver_phased_radar.vhd"), "w") as fh:
        fh.write(arena_resolver.emit("phased_radar", wires, arena, generics, scatterers=["tgt0", "tgt1", "tgt2"]))
    cmd = [args.nvc, "-H", "1g", "--std=2040", "-L", base.nvc_libdir(args.nvc)]
    env = dict(os.environ)
    env["NVC_NO_EVAL_ARENA"] = "1"                     # see an2597_nvc.py
    for k in ("SPECTRAL_ACCEL_SCHEDULE", "SPECTRAL_ACCEL_DEVICE"):
        env.pop(k, None)
    load = []
    if accel:
        if not os.path.isfile(base.ACCEL_LIB):
            raise SystemExit("%s is not built: run smak (or make) in %s" % (base.ACCEL_LIB, os.path.dirname(base.ACCEL_LIB)))
        env["SPECTRAL_ACCEL_SEED"] = str(args.seed)
        if args.schedule:
            env["SPECTRAL_ACCEL_SCHEDULE"] = args.schedule
        if args.device:
            env["SPECTRAL_ACCEL_DEVICE"] = args.device
        load = ["--load=" + base.ACCEL_LIB]

    def sh(*a):
        r = subprocess.run(cmd + list(a), cwd=tmp, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, env=env)
        if r.returncode != 0:
            raise SystemExit("%s\n%s\nfailed (rc %d), files in %s" % (" ".join(cmd + list(a)), r.stdout[-6000:], r.returncode, tmp))
        return r.stdout

    t0 = time.perf_counter()
    sources = [f % ("on" if accel else "off") if "%s" in f else f for f in SOURCES]
    sh("-a", "ad9361_pkg.vhd", *[os.path.join(HERE, f) for f in sources], "resolver_phased_radar.vhd")
    sh("-e", "resolved_phased_radar")
    t1 = time.perf_counter()
    out = sh("-r", "--stats", *load, "resolved_phased_radar")
    t2 = time.perf_counter()
    m = re.search(r"setup:(\d+)ms run:(\d+)ms", out)          # nvc's own clock for the run phase
    t_sim = float(m.group(2)) * 1e-3 if m else t2 - t1
    m = re.search(r"start-up ([0-9.]+) ms", out)                # the accelerator's start-up (CUDA) is not simulation
    if m:
        t_sim -= float(m.group(1)) * 1e-3
    found = []
    for m in re.finditer(r"RADAR target=(\d) range=(\S+) bearing=(\S+) speed=(\S+) margin_db=(\S+) look_end=(\S+)", out):
        found.append((int(m.group(1)),) + tuple(float(m.group(i)) for i in range(2, 7)))
    if "RADAR done" not in out:
        raise SystemExit("the run did not finish:\n%s\nfiles in %s" % (out[-4000:], tmp))
    notes = [l for l in out.splitlines() if l.startswith("spectral-accel:")]
    if args.keep:
        print("files kept in %s" % tmp)
    else:
        subprocess.run(["rm", "-rf", tmp])
    return found, t1 - t0, t_sim, notes


def show(args, n, accel):
    found, t_build, t_run, notes = run(args, n, accel)
    lam = ad9361.C0 / args.lo
    events = args.looks * args.pulses
    where = "RF path on the spectral accelerator" + (" (%s)" % args.schedule if args.schedule else "") if accel else "all in nvc"
    print("phased-array radar in nvc --std=2040, %s: %d + %d elements%s, %d pulses per look every %.0f us"
          % (where, n, n, ", arrays isolated" if args.isolate else "", args.pulses, args.pri * 1e6))
    for l in notes:
        print(l)
    print("compile and elaborate %.1f s; run %.2f s for %d pulses (%d spectral events at the chips)"
          % (t_build, t_run, events, events * 2 * n))
    steady = None
    if args.steady:                                    # the same again, much longer: what a pulse costs once nvc is warm
        k = 16 if accel else 3
        _, _, t_long, _ = run(args, n, accel, k * args.looks)
        steady = (t_long - t_run) / ((k - 1) * events)
        print("steady state: %.3f ms per pulse (%.0f pulses per second)" % (1e3 * steady, 1.0 / steady))
    print("%-34s | %-34s | %s" % ("target: range m, bearing deg, m/s", "found", "peak over the rest, dB"))
    bad = 0 if len(found) == args.looks else 1
    if bad:
        print("%d looks reported, %d expected" % (len(found), args.looks))
    for i, fr, fb, fv, margin, t_end in found:
        r, b, c, v = TARGETS[i]
        true_range = r + v * (t_end - args.pulses * args.pri / 2.0)
        ok = abs(fr - true_range) < 4.0 and abs(fv - v) < lam / (2.0 * args.pulses * args.pri) and abs(fb - b) < max(60.0 / n, 0.3)
        bad += 0 if ok else 1
        print("%10.1f %10.1f %10.1f   | %10.1f %10.1f %10.1f   | %5.1f  %s" % (true_range, b, v, fr, fb, fv, margin, "ok" if ok else "MISSED"))
    return bad, found, steady if steady is not None else t_run / events


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--nvc", default=os.environ.get("NVC", "nvc"))
    ap.add_argument("-n", type=int, nargs="+", default=[4], help="elements per array (several: a sweep)")
    ap.add_argument("--lo", type=float, default=2.437e9)
    ap.add_argument("--fs", type=float, default=20e6)
    ap.add_argument("--ant", type=float, default=2.0)
    ap.add_argument("--sep", type=float, default=3.0)
    ap.add_argument("--isolate", action="store_true", help="the two arrays do not hear each other directly")
    ap.add_argument("--pri", type=float, default=100e-6)
    ap.add_argument("--pulses", type=int, default=64)
    ap.add_argument("--looks", type=int, default=3, help="looks, one target after the other")
    ap.add_argument("--steady", action="store_true",
                    help="run each case a second time, 3 (nvc) or 16 (accelerator) times as long, and give the time per "
                    "pulse of the difference")
    ap.add_argument("--blank", type=float, default=45.0)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--accel", action="store_true", help="move the RF path's data and processing out to the spectral accelerator")
    ap.add_argument("--both", action="store_true", help="run in nvc, then with the accelerator")
    ap.add_argument("--schedule", help="with --accel: when the design moves out and comes back, e.g. 0:out,7ms:in,9ms:out")
    ap.add_argument("--device", choices=("gpu", "cpu"), help="with --accel: where the accelerator's stages run")
    ap.add_argument("--keep", action="store_true", help="keep the scratch directory")
    args = ap.parse_args(argv)
    bad = 0
    rows = []
    for n in args.n:
        per = {}
        for accel in ((False, True) if args.both else (args.accel,)):
            b, _, per[accel] = show(args, n, accel)
            bad += b
            print()
        rows.append((n, per))
    if len(rows) > 1 or args.both:
        print("%s time per pulse" % ("steady-state" if args.steady else "whole-run (start-up included)"))
        print("%9s | %14s | %14s" % ("elements", "nvc ms/pulse", "accel ms/pulse"))
        for n, per in rows:
            print("%4d+%-4d | %14s | %14s" % (n, n, "%.2f" % (1e3 * per[False]) if False in per else "-",
                                               "%.2f" % (1e3 * per[True]) if True in per else "-"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
