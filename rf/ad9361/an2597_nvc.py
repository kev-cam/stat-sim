#!/usr/bin/env python3
# Part of stat-sim. PolyForm Noncommercial License 1.0.0; commercial use needs a separate license (see LICENSE, COMMERCIAL.md).
"""
an2597_nvc.py -- run the AN-2597 link in nvc (--std=2040, spectral event-driven) and tabulate it.

Writes the resolver network (wires between chip pins and antenna feeds, the arena between the four
antennas) and the wrapper with the design's generics, compiles ad9361_pkg / rf_spectrum_pkg /
ad9361_spectral_pkg / ad9361 / rf_spec_antenna / ofdm_soft_pkg / an2597_link, runs, and prints per
distance the EVM and uncoded bit error rate of each modulation next to the link budget.  With
--compare the same distances are also run through the Python time-domain model (an2597_link.py).

    an2597_nvc.py --nvc /usr/local/src/nvc-build/bin/nvc
    an2597_nvc.py --lo 5.2e9 --distances 1 10 30 100 --compare
"""
import argparse
import math
import os
import re
import subprocess
import sys
import tempfile
import time

import numpy as np

import ad9361
import ad9361_vhdl
import an2597_link
import arena_resolver
import ofdm

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCES = ("rf_spectrum_pkg.vhd", "ad9361_spectral_pkg.vhd", "ad9361.vhd", "rf_spec_antenna.vhd", "ofdm_soft_pkg.vhd",
           "an2597_link.vhd")
WIRES = [["drone_chip.tx1", "drone_ant_tx.feed"], ["drone_chip.rx1", "drone_ant_rx.feed"],
         ["ctrl_chip.tx1", "ctrl_ant_tx.feed"], ["ctrl_chip.rx1", "ctrl_ant_rx.feed"]]
ARENA = ["drone_ant_tx", "drone_ant_rx", "ctrl_ant_tx", "ctrl_ant_rx"]
MODS = ("bpsk", "qpsk", "16qam", "64qam")


def vreal(x):
    s = "%.9e" % x
    return "(%s)" % s if s.startswith("-") else s


def nvc_libdir(nvc):
    """The directory that holds nvc's compiled `rf` library."""
    root = os.path.dirname(os.path.dirname(os.path.realpath(nvc)))
    for d in (os.environ.get("NVC_LIBDIR", ""), os.path.join(root, "lib"), os.path.join(root, "lib", "nvc")):
        if d and os.path.isdir(os.path.join(d, "rf")):
            return d
    raise SystemExit("cannot find nvc's rf library next to %s; set NVC_LIBDIR" % nvc)


def run(args):
    if len(args.distances) > 8:
        raise SystemExit("at most 8 distances per run")
    tmp = tempfile.mkdtemp(prefix="an2597_nvc_")
    generics = dict(lo=vreal(args.lo), fs=vreal(args.fs), atten_db=vreal(args.atten), ant_dbi=vreal(args.ant),
                    drone_ppm=vreal(args.ppm[0]), ctrl_ppm=vreal(args.ppm[1]), packets=str(args.packets),
                    symbols=str(args.symbols))
    for i, d in enumerate(args.distances):
        generics["d%d" % i] = vreal(d)
    with open(os.path.join(tmp, "ad9361_pkg.vhd"), "w") as fh:
        fh.write(ad9361_vhdl.emit())
    with open(os.path.join(tmp, "resolver_an2597_link.vhd"), "w") as fh:
        fh.write(arena_resolver.emit("an2597_link", WIRES, ARENA, generics))
    lib = nvc_libdir(args.nvc)
    base = [args.nvc, "--std=2040", "-L", lib]
    # nvc 1.19-devel r619 (da8ece172) crashes in its signal-driver fast path once a process that
    # allocates (the chip model) has deposited to a 'driver signal some tens of times; its eval arena
    # is what goes wrong, and switching it off avoids the crash (see README: "nvc notes")
    env = dict(os.environ)
    if args.eval_arena:
        env.pop("NVC_NO_EVAL_ARENA", None)
    else:
        env["NVC_NO_EVAL_ARENA"] = "1"

    def sh(*cmd):
        r = subprocess.run(base + list(cmd), cwd=tmp, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           universal_newlines=True, env=env)
        if r.returncode != 0:
            raise SystemExit("%s\n%s\nfailed (rc %d), files in %s" % (" ".join(base + list(cmd)), r.stdout[-6000:],
                                                                      r.returncode, tmp))
        return r.stdout

    t0 = time.perf_counter()
    sh("-a", "ad9361_pkg.vhd", *[os.path.join(HERE, f) for f in SOURCES], "resolver_an2597_link.vhd")
    sh("-e", "resolved_an2597_link")
    t1 = time.perf_counter()
    out = sh("-r", "resolved_an2597_link")
    t2 = time.perf_counter()
    rows = {}
    for m in re.finditer(r"AN2597 dist=(\S+) mod=(\d) packets=(\d+) detected=(\d+) evm_db=(\S+) bit_errors=(\d+) "
                         r"bits=(\d+) gain_db=(\S+)", out):
        d = float(m.group(1))
        rows.setdefault(d, {})[MODS[int(m.group(2))]] = dict(
            packets=int(m.group(3)), detected=int(m.group(4)), evm=float(m.group(5)),
            ber=int(m.group(6)) / int(m.group(7)), gain=float(m.group(8)))
    if "AN2597 done" not in out:
        raise SystemExit("the run did not finish:\n%s\nfiles in %s" % (out[-4000:], tmp))
    if args.keep:
        print("files kept in %s" % tmp)
    else:
        subprocess.run(["rm", "-rf", tmp])
    return rows, t1 - t0, t2 - t1


def python_rows(args):
    """The same sweep through the Python time-domain model."""
    rng = np.random.default_rng(args.seed)
    rows = {}
    a = argparse.Namespace(**vars(args))
    a.agc, a.pa, a.lna, a.lna_nf = "fast_attack", 0.0, 0.0, None
    for d in args.distances:
        drone, ctrl, arena = an2597_link.make_link(a, d, args.seed)
        drone.ensm_mode, ctrl.ensm_mode = "tx", "rx"
        rows[d] = {}
        for m in MODS:
            det, evms, errors, nbits, gains = an2597_link.send_packets(drone, ctrl, m, args.packets, args.symbols, rng, args.fs)
            rows[d][m] = dict(packets=args.packets, detected=det,
                              evm=10.0 * math.log10(np.mean(evms)) if evms else float("nan"), ber=errors / nbits,
                              gain=float(np.median(gains)) if gains else float("nan"))
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--nvc", default=os.environ.get("NVC", "nvc"))
    ap.add_argument("--lo", type=float, default=2.437e9)
    ap.add_argument("--fs", type=float, default=20e6)
    ap.add_argument("--atten", type=float, default=0.0)
    ap.add_argument("--ant", type=float, default=2.0)
    ap.add_argument("--ppm", type=float, nargs=2, default=(1.0, -1.5))
    ap.add_argument("--distances", type=float, nargs="+", default=[1, 3, 10, 30, 100, 300, 1000, 3000])
    ap.add_argument("--packets", type=int, default=10)
    ap.add_argument("--symbols", type=int, default=20)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--compare", action="store_true", help="also run the Python time-domain model")
    ap.add_argument("--keep", action="store_true", help="keep the scratch directory")
    ap.add_argument("--eval-arena", action="store_true",
                    help="leave nvc's eval arena on (reproduces the nvc crash this script otherwise avoids)")
    args = ap.parse_args(argv)
    args.pa, args.lna, args.lna_nf, args.agc = 0.0, 0.0, None, "fast_attack"

    rows, t_build, t_run = run(args)
    events = len(args.distances) * len(MODS) * args.packets * (args.symbols + 6)
    air = events * ofdm.N_FFT * 1.25 / args.fs
    print("AN-2597 link in nvc --std=2040 (spectral events): LO %.1f MHz, %.0f MHz channel, TX attenuation %.2f dB, "
          "antennas %.1f dBi, reference offsets %+.1f / %+.1f ppm"
          % (args.lo / 1e6, args.fs / 1e6, args.atten, args.ant, args.ppm[0], args.ppm[1]))
    print("compile and elaborate %.1f s; run %.2f s for %d symbol events (%.1f ms of air time): %.3f x real time"
          % (t_build, t_run, events, air * 1e3, air / t_run))
    ref = python_rows(args) if args.compare else None
    head = "%8s %8s %6s %7s" % ("dist m", "Prx dBm", "gain", "budget")
    for m in MODS:
        head += " | %5s %6s %8s" % (m, "EVM", "BER")
    print(head)
    worst = 0.0
    for d in args.distances:
        prx, evm_budget = an2597_link.budget(args, d)
        r = rows.get(float(d), {})
        gains = [r[m]["gain"] for m in MODS if m in r and r[m]["detected"]]
        line = "%8.0f %8.1f %6.1f %7.1f" % (d, prx, float(np.mean(gains)) if gains else float("nan"), evm_budget)
        for m in MODS:
            x = r.get(m)
            line += " | %2d/%-2d %6.1f %8.1e" % (x["detected"], x["packets"], x["evm"], x["ber"]) if x else " | (no line)"
            if x and x["detected"] == x["packets"]:
                worst = max(worst, abs(x["evm"] - evm_budget))
        print(line)
        if ref:
            line = "%8s %8s %6.1f %7s" % ("", "python", ref[d]["bpsk"]["gain"], "")
            for m in MODS:
                x = ref[d][m]
                line += " | %2d/%-2d %6.1f %8.1e" % (x["detected"], x["packets"], x["evm"], x["ber"])
            print(line)
    print("largest |EVM - budget| where every packet was found: %.2f dB" % worst)
    return 0


if __name__ == "__main__":
    sys.exit(main())
