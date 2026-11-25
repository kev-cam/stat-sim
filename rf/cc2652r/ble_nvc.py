#!/usr/bin/env python3
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# SPDX-FileCopyrightText: 2026 D. Kevin Cameron
# Part of stat-sim. PolyForm Noncommercial License 1.0.0; commercial use needs a separate license (see LICENSE, COMMERCIAL.md).
"""
ble_nvc.py -- run the CC2652R / Bluetooth LE model in nvc (--std=2040, spectral event-driven).

Writes cc2652r_pkg.vhd (cc2652r_vhdl.py), compiles the model, has nvc's resolver plugin generate the
network of ble_link (wires between chip pins and antenna feeds, the arena between the antennas, with
the physical delay of every path), runs it and tabulates what the devices report.

    ble_nvc.py selftest                      tb_cc2652r: packets against ble_phy.py, chip to chip
    ble_nvc.py range [--phy 1m] [--dist 10 300 700 1000] [--packets 40] [--compare]
                                             Direct Test Mode range; --compare: ble_host.py's model too
    ble_nvc.py scan [--time 2.0] [--dist 10]
                                             a beacon, a neighbour and an active scanner
    ble_nvc.py connect [--dist 10] [--events 40] [--time 2.0]
                                             the tester (a central and its host) puts a peripheral through
                                             its tests; exit status 1 if a test fails
    ... --fed                                also as two simulations sharing the arena (the transmitting
                                             side and the other), which must report the same lines

--nvc-build (or NB): an nvc build with the arena support (lib/sv2vhdl/libresolver.so, libarena.so).
"""
import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
RF = os.path.dirname(HERE)
# None: cc2652r_pkg.vhd, written into the working directory
SOURCES = [os.path.join(RF, "ad9361", "rf_spectrum_pkg.vhd"), os.path.join(HERE, "ble_phy_pkg.vhd"), None] + [
    os.path.join(HERE, f) for f in ("cc2652r_spectral_pkg.vhd", "cc2652r.vhd", "rf_spec_antenna_td.vhd", "ble_ll_pkg.vhd", "btle_phy_radio_pkg.vhd", "ucb_bmc_radio_pkg.vhd", "ble_controller.vhd", "ble_tester.vhd",
                                    "ble_link.vhd", "tb_cc2652r.vhd")]
# the modules of btle_phy (github.com/JiaoXianjun/BTLE, verilog/)
BTLE_MODULES = ("btle_phy btle_rx btle_rx_core gfsk_demodulation search_unique_bit_sequence scramble_core crc24_core "
                "serial_in_ram_out sdpram_two_clk sdpram_one_clk btle_tx crc24 scramble gfsk_modulation bit_repeat_upsample "
                "gauss_filter vco").split()
DUTS = {"cc2652r": ("0", "a CC2652R"), "btle": ("1", "the open BTLE baseband (btle_phy, through sv2ghdl)"),
        "btle-tail": ("2", "the open BTLE baseband (btle_phy, through sv2ghdl), its last symbol completed"),
        "bmc": ("3", "the Berkeley baseband-modem (BMC, through sv2ghdl)"),
        "bmc-txend": ("4", "the Berkeley baseband-modem (BMC, through sv2ghdl), its transmissions ended by the host")}
# selftest: the bench of a radio and its generics
BENCH = {"cc2652r": ("tb_cc2652r", []), "btle": ("tb_btle_phy_radio", []), "btle-tail": ("tb_btle_phy_radio", ["-gtx_tail=true"]),
         "bmc": ("tb_ucb_bmc_radio", []), "bmc-txend": ("tb_ucb_bmc_radio", ["-gtx_end=true"])}
PHY_CODE = {"1m": 1, "2m": 2, "s8": 3, "s2": 4}
BAND = "ism2g4_td"


class Build:
    def __init__(self, args):
        self.nb = args.nvc_build or os.environ.get("NB")
        if not self.nb or not os.path.isfile(os.path.join(self.nb, "bin", "nvc")):
            raise SystemExit("give --nvc-build (or NB): an nvc build directory with bin/nvc")
        self.nvc = [os.path.join(self.nb, "bin", "nvc"), "--std=2040", "-H", args.heap, "-L", os.path.join(self.nb, "lib")]
        self.sv = args.sv2vhdl
        if not self.sv:
            with open(os.path.join(self.nb, "Makefile")) as fh:
                m = re.search(r"^abs_top_srcdir = (.*)$", fh.read(), re.M)
            self.sv = os.path.join(m.group(1), "lib", "sv2vhdl")
        self.work = args.work or tempfile.mkdtemp(prefix="ble_nvc_")
        os.makedirs(self.work, exist_ok=True)
        self.env = dict(os.environ, NVC_NO_EVAL_ARENA="1")
        if args.accel:
            self.env["NVC_ACCEL"] = "1"   # nvc --accel: a translated design runs as one compiled model
        import cc2652r_vhdl
        self.pkg = os.path.join(self.work, "cc2652r_pkg.vhd")
        with open(self.pkg, "w") as fh:
            fh.write(cc2652r_vhdl.emit())
        self.sources = [self.pkg if f is None else f for f in SOURCES]
        self.dut = args.dut
        # entity btle_phy_radio, before ble_link: the baseband and its radio, or nothing
        at = self.sources.index(os.path.join(HERE, "ble_link.vhd"))
        if args.dut.startswith("btle"):
            self.sources[at:at] = [self.translate_btle(args), os.path.join(HERE, "btle_phy_radio.vhd"),
                                   os.path.join(HERE, "tb_btle_phy_radio.vhd")]
        else:
            self.sources[at:at] = [os.path.join(HERE, "btle_phy_radio_none.vhd")]
        # ... and entity ucb_bmc_radio
        at = self.sources.index(os.path.join(HERE, "ble_link.vhd"))
        if args.dut.startswith("bmc"):
            self.sources[at:at] = [self.translate_bmc(args), os.path.join(HERE, "ucb_bmc_radio.vhd"),
                                   os.path.join(HERE, "tb_ucb_bmc_radio.vhd")]
        else:
            self.sources[at:at] = [os.path.join(HERE, "ucb_bmc_radio_none.vhd")]

    def translate_bmc(self, args):
        """BMC.v (the Berkeley baseband-modem's Verilog, which ucb_bmc/emit.sh makes), Verilog to VHDL by
        sv2ghdl.  It takes a minute, so the VHDL is kept in the working directory until BMC.v is newer."""
        src = args.bmc_verilog or os.environ.get("BMC_V")
        sv2ghdl = args.sv2ghdl or os.environ.get("SV2GHDL")
        if not src or not sv2ghdl:
            raise SystemExit("--dut bmc (or bmc-txend) needs --bmc-verilog (or BMC_V: BMC.v, see ucb_bmc/README.md) "
                             "and --sv2ghdl (or SV2GHDL: an sv2ghdl checkout)")
        if not os.path.isfile(src):
            raise SystemExit("%s is not there" % src)
        out = os.path.join(self.work, "bmc")
        vhd = os.path.join(out, "design.vhd")
        if os.path.isfile(vhd) and os.path.getmtime(vhd) >= os.path.getmtime(src):
            return vhd
        shutil.rmtree(out, ignore_errors=True)
        env = dict(NVC=self.nvc[0])
        if args.iverilog or os.environ.get("IVERILOG"):
            env["IVERILOG"] = args.iverilog or os.environ["IVERILOG"]
        self.sh(self.work, os.path.join(sv2ghdl, "bin", "iverilog-sv2ghdl"), "-g2012", "-o", out, "-s", "BMC", src,
                env=env, nvc=False)
        if not os.path.isfile(vhd):
            raise SystemExit("sv2ghdl wrote no %s (see %s/iverilog.log)" % (vhd, out))
        return vhd

    def translate_btle(self, args):
        """btle_phy and what is under it, Verilog to VHDL: sv2ghdl's iverilog wrapper (iverilog -tvhdl over
        nvc's sv2vhdl library).  Returns the VHDL file."""
        src = args.btle_src or os.environ.get("BTLE_SRC")
        sv2ghdl = args.sv2ghdl or os.environ.get("SV2GHDL")
        if not src or not sv2ghdl:
            raise SystemExit("--dut btle (or btle-tail) needs --btle-src (or BTLE_SRC: the verilog directory of a JiaoXianjun/BTLE checkout) "
                             "and --sv2ghdl (or SV2GHDL: an sv2ghdl checkout)")
        files = [os.path.join(src, m + ".v") for m in BTLE_MODULES]
        for f in files:
            if not os.path.isfile(f):
                raise SystemExit("%s is not there" % f)
        out = os.path.join(self.work, "btle")
        shutil.rmtree(out, ignore_errors=True)
        env = dict(NVC=self.nvc[0])
        if args.iverilog or os.environ.get("IVERILOG"):
            env["IVERILOG"] = args.iverilog or os.environ["IVERILOG"]
        self.sh(self.work, os.path.join(sv2ghdl, "bin", "iverilog-sv2ghdl"), "-g2012", "-o", out, "-s", "btle_phy", *files,
                env=env, nvc=False)
        vhd = os.path.join(out, "design.vhd")
        if not os.path.isfile(vhd):
            raise SystemExit("sv2ghdl wrote no %s (see %s/iverilog.log)" % (vhd, out))
        return vhd

    def sh(self, cwd, *cmd, env=None, nvc=True, ok=(0,)):
        full = (self.nvc if nvc else []) + list(cmd)
        r = subprocess.run(full, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True,
                           env=dict(self.env, **(env or {})))
        if r.returncode not in ok:
            raise SystemExit("%s\n%s\nfailed (rc %d) in %s" % (" ".join(full), r.stdout[-6000:], r.returncode, cwd))
        return r.stdout

    def generate(self, name, generics):
        """Compile ble_link with these generics in <work>/<name> and generate its resolver network;
        leaves resolved_ble_link elaborated there.  Returns the directory."""
        d = os.path.join(self.work, name)
        shutil.rmtree(d, ignore_errors=True)
        os.makedirs(os.path.join(d, "gen"))
        self.sh(d, "-a", *self.sources)
        self.sh(d, "-e", "ble_link", *["-g%s=%s" % kv for kv in generics.items()])
        self.sh(d, "-r", "--stop-time=1fs", "--load=" + os.path.join(self.nb, "lib", "sv2vhdl", "libresolver.so"), "ble_link",
                env=dict(NVC_RESOLVER_DIR=os.path.join(d, "gen"), NVC_RCMODE="none", SV2VHDL_FORWARD_GENERICS="1",
                         PYTHONPATH=self.sv))
        gen = sorted(f for f in os.listdir(os.path.join(d, "gen")) if f.endswith(".vhd"))
        wrapper = [f for f in gen if f.endswith("_wrapper.vhd")]
        if not wrapper:
            raise SystemExit("the resolver plugin wrote no wrapper in %s/gen" % d)
        self.sh(d, "-a", *[os.path.join("gen", f) for f in gen if f not in wrapper], os.path.join("gen", wrapper[0]),
                "-e", "resolved_ble_link")
        return d

    def run(self, d):
        t0 = time.perf_counter()
        out = self.sh(d, "-r", "--load=" + os.path.join(self.nb, "lib", "sv2vhdl", "libarena.so"), "resolved_ble_link")
        return lines_of(out), time.perf_counter() - t0

    def federated(self, generics):
        """The same design as two simulations in one arena: role 1 and role 2.  Returns (lines, seconds)."""
        dirs = {}
        for name, role in (("side_a", 1), ("side_b", 2)):
            dirs[name] = self.generate(name, dict(generics, role=str(role)))
        cmd = self.nvc + ["-r", "--load=" + os.path.join(self.nb, "lib", "sv2vhdl", "libarena.so"), "resolved_ble_link"]
        fed = {"arenas": {"lab": {"vlan": "rf-lab"}}, "bands": {BAND: "lab"},
               "simulations": [{"name": n, "cwd": d, "gen": os.path.join(d, "gen"), "cmd": cmd} for n, d in dirs.items()]}
        with open(os.path.join(self.work, "federation.json"), "w") as fh:
            json.dump(fed, fh, indent=1)
        logs = os.path.join(self.work, "logs")
        shutil.rmtree(logs, ignore_errors=True)
        t0 = time.perf_counter()
        self.sh(self.work, sys.executable, os.path.join(self.sv, "arena_ctl.py"), "run", "federation.json", "--logdir", logs,
                nvc=False)
        dt = time.perf_counter() - t0
        out = []
        for n in dirs:
            with open(os.path.join(logs, n + ".log")) as fh:
                out += lines_of(fh.read())
        return out, dt


def lines_of(text):
    return [m.group(1) for m in re.finditer(r"(BLE (?:test|adv|scan|tester|periph) .*)$", text, re.M)]


def fields(line):
    return dict(kv.split("=", 1) for kv in line.split()[2:] if "=" in kv)


def compare_fed(b, generics, mono, args):
    if not args.fed:
        return 0
    fed, dt = b.federated(generics)
    same = sorted(fed) == sorted(mono)
    print("federated (two simulations, one arena): %.1f s; %s" % (
        dt, "the same %d lines as the one simulation" % len(mono) if same else "DIFFERS from the one simulation:"))
    if not same:
        for l in sorted(set(fed) ^ set(mono)):
            print("  %s %s" % ("fed " if l in fed else "mono", l))
    return 0 if same else 1


def cmd_selftest(args):
    b = Build(args)
    d = os.path.join(b.work, "tb")
    os.makedirs(d, exist_ok=True)
    b.sh(d, "-a", *b.sources)
    tb, generics = BENCH[b.dut]
    b.sh(d, "-e", tb, *generics)
    out = b.sh(d, "-r", tb)
    for m in re.finditer(r"(TB .*)$", out, re.M):
        print(m.group(1))
    m = re.search(r"TB done failures=(\d+)", out)
    return 0 if m and m.group(1) == "0" else 1


def cmd_range(args):
    sys.path.insert(0, HERE)
    import ble_phy as ble
    import cc2652r as cc
    import ble_host
    if len(args.dist) > 8:
        raise SystemExit("at most 8 distances per run")
    b = Build(args)
    g = dict(scenario="0", role="0", phy_code=str(PHY_CODE[args.phy]), rf_channel=str(args.channel), length=str(args.length),
             tx_dbm="%.6f" % args.power, packets=str(args.packets), ppm_a="%.6f" % args.ppm[0], ppm_b="%.6f" % args.ppm[1])
    for i, x in enumerate(args.dist):
        g["d%d" % i] = "%.6f" % x
    if args.lead:
        g["tx_lead"] = args.lead
    t0 = time.perf_counter()
    d = b.generate("mono", g)
    t_build = time.perf_counter() - t0
    mono, t_run = b.run(d)
    rows = {int(f["window"]): f for f in map(fields, mono)}
    air = len(args.dist) * args.packets * ble.packet_duration(args.phy, args.length + 2)
    print("Direct Test Mode in nvc --std=2040 (spectral events), %s, RF channel %d, %d-octet PRBS9 packets, %g dBm, isotropic"
          " antennas, crystals %+g / %+g ppm" % (cc.RX[args.phy]["name"], args.channel, args.length, args.power, *args.ppm))
    print("compile, generate and elaborate %.1f s; run %.1f s for %.1f ms of packets on the air (%.4f x real time)"
          % (t_build, t_run, air * 1e3, air / t_run))
    print("data sheet sensitivity %g dBm (BER 1e-3: a %d-octet packet then fails %.0f %% of the time)"
          % (cc.RX[args.phy]["sens"], args.length, 100.0 * (1.0 - (1.0 - 1e-3) ** (8 * (args.length + 5)))))
    ref = {}
    if args.compare:
        for dist in args.dist:
            a = ble_host.Controller("tester", "C0:00:00:00:00:01", seed=1, fs=32e6)
            dut = ble_host.Controller("dut", "C0:00:00:00:00:02", position=(dist, 0.0, 0.0), seed=2, fs=32e6)
            a.set_tx_power(args.power)
            a.le_transmitter_test(args.channel, args.length, 0, PHY_CODE[args.phy])
            dut.le_receiver_test(args.channel, min(PHY_CODE[args.phy], 3))
            if args.phy == "s2":
                dut.test["phy"] = "s2"
            step = math.ceil((ble.packet_duration(args.phy, args.length + 2) + 249e-6) / ble_host.SLOT) * ble_host.SLOT
            ble_host.Arena([a, dut]).run(args.packets * step)
            ref[dist] = dut.le_test_end()
    print("%9s %12s %10s %10s %8s%s" % ("distance", "budget dBm", "RSSI dBm", "received", "PER", "   python" if ref else ""))
    for k, dist in enumerate(args.dist):
        f = rows.get(k)
        budget = ble_host.link_budget(cc.CC2652R().tx_power_legal(args.power), dist, ble.rf_channel_frequency(args.channel))
        if f is None:
            print("%7g m %12.1f   (no line)" % (dist, budget))
            continue
        got = int(f["received"])
        line = "%7g m %12.1f %10s %6d/%-4d %7.1f%%" % (dist, budget, "%.1f" % float(f["rssi"]) if got else "-", got,
                                                      args.packets, 100.0 * (1.0 - got / args.packets))
        if ref:
            line += "   %d/%d" % (ref[dist], args.packets)
        print(line)
    return compare_fed(b, g, mono, args)


def cmd_scan(args):
    b = Build(args)
    g = dict(scenario="1", role="0", dut=DUTS[args.dut][0], tx_dbm="%.6f" % args.power, dist="%.6f" % args.dist,
             run_time="%dus" % round(args.time * 1e6), ppm_a="%.6f" % args.ppm[0], ppm_b="%.6f" % args.ppm[1])
    if args.lead:
        g["tx_lead"] = args.lead
    t0 = time.perf_counter()
    d = b.generate("mono", g)
    t_build = time.perf_counter() - t0
    mono, t_run = b.run(d)
    print("%.1f s in nvc --std=2040 (spectral events): beacon (ADV_IND every 100 ms) at 0 m, a neighbour (ADV_NONCONN_IND"
          " every 20 ms) and an active scanner (30 ms of every 60 ms) at %g m" % (args.time, args.dist))
    print("compile, generate and elaborate %.1f s; run %.1f s (%.4f x real time)" % (t_build, t_run, args.time / t_run))
    budget = {0xA6: ("beacon", args.dist), 0x99: ("neighbour", 2.0)}
    names = {"a": "beacon", "c": "neighbour"}
    for l in mono:
        f = fields(l)
        if l.startswith("BLE adv"):
            print("  %-9s %s advertising events, %s scan requests heard, %s scan responses sent"
                  % (names.get(f["node"], f["node"]), f["events"], f["scan_requests"], f["scan_responses"]))
        elif "from" in f:
            who, dd = budget.get(int(f["from"]), ("?", None))
            lb = args.power + 20.0 * math.log10(299792458.0 / 2440e6 / (4.0 * math.pi * dd)) if dd else float("nan")
            print("  scanner: from the %s %s ADV_IND, %s ADV_NONCONN_IND, %s SCAN_RSP; RSSI %.0f dBm (budget %.1f)"
                  % (who, f["adv_ind"], f["adv_nonconn_ind"], f["scan_rsp"], float(f["rssi"]), lb))
        else:
            print("  scanner: %s SCAN_REQ sent, %s packets with a bad CRC" % (f["scan_requests"], f["crc_errors"]))
    return compare_fed(b, g, mono, args)


def cmd_connect(args):
    b = Build(args)
    g = dict(scenario="2", role="0", dut=DUTS[args.dut][0], tx_dbm="%.6f" % args.power, dist="%.6f" % args.dist, packets=str(args.events),
             run_time="%dus" % round(args.time * 1e6), ppm_a="%.6f" % args.ppm[0], ppm_b="%.6f" % args.ppm[1])
    if args.lead:
        g["tx_lead"] = args.lead
    t0 = time.perf_counter()
    d = b.generate("mono", g)
    t_build = time.perf_counter() - t0
    mono, t_run = b.run(d)
    print("the tester (central) at 0 m and a peripheral at %g m whose radio is %s, %g dBm, in nvc --std=2040 (spectral events)"
          % (args.dist, DUTS[args.dut][1], args.power))
    print("compile, generate and elaborate %.1f s; run %.1f s" % (t_build, t_run))
    failed = True
    for l in mono:
        f = fields(l)
        if l.startswith("BLE tester test="):
            rest = " ".join("%s=%s" % kv for kv in f.items() if kv[0] not in ("test", "verdict"))
            print("  %-4s %-10s %s" % (f["verdict"], f["test"], rest))
            if f["test"] == "summary":
                failed = f["verdict"] != "PASS"
        elif l.startswith("BLE tester service"):
            print("       service    handles %s - %s, UUID 0x%s" % (f["start"], f["end"], f["uuid"]))
    for l in mono:
        if l.startswith("BLE periph"):
            f = fields(l)
            print("  peripheral: %s advertising events, %s connection, %s connection events (%s missed, %s bad CRC), "
                  "terminated %s, lost %s" % (f["adv_events"], f["connections"], f["events"], f["missed"], f["crc_errors"],
                                              f["terminated"], f["lost"]))
    return max(compare_fed(b, g, mono, args), int(failed))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--nvc-build", help="nvc build directory (default: $NB)")
    p.add_argument("--sv2vhdl", help="nvc's lib/sv2vhdl source directory (default: from the build's Makefile)")
    p.add_argument("--work", help="working directory (default: a new temporary one)")
    p.add_argument("--heap", default="256m", help="nvc heap (-H)")
    p.add_argument("--accel", action="store_true",
                   help="nvc --accel for the translated design (--dut bmc...); needs sv2ghdl's gen_statemachine, "
                        "$GEN_STATEMACHINE if it is not where nvc looks; first run compiles the model, minutes")
    p.add_argument("--fed", action="store_true", help="also run as two simulations sharing the arena")
    p.add_argument("--lead", help="every antenna's transmit latency, e.g. 1us (lets a federation run further ahead)")
    p.add_argument("--ppm", type=float, nargs=2, default=[0.0, 0.0], help="crystal errors of the two sides")
    p.add_argument("--power", type=float, default=0.0)
    p.add_argument("--dut", default="cc2652r", choices=list(DUTS),
                   help="the radio of the device under test (selftest, scan, connect): the CC2652R model, or btle: "
                        "btle_phy of github.com/JiaoXianjun/BTLE translated by sv2ghdl behind btle_phy_radio; btle-tail: "
                        "the same with the last symbol of its packets, which its modulator cuts off, completed; bmc: BMC of "
                        "github.com/ucb-bar/baseband-modem translated by sv2ghdl behind ucb_bmc_radio (slow: some 20 s of run "
                        "time a packet; give --heap 2g); bmc-txend: the same with its transmissions ended by the host")
    p.add_argument("--bmc-verilog", help="--dut bmc, bmc-txend: BMC.v, as ucb_bmc/emit.sh makes it (default: $BMC_V)")
    p.add_argument("--btle-src", help="--dut btle, btle-tail: the verilog directory of a BTLE checkout (default: $BTLE_SRC)")
    p.add_argument("--sv2ghdl", help="--dut btle, btle-tail: an sv2ghdl checkout (default: $SV2GHDL)")
    p.add_argument("--iverilog", help="--dut btle, btle-tail: an iverilog with the VHDL back end (default: $IVERILOG, or sv2ghdl's choice)")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("selftest")
    r = sub.add_parser("range")
    r.add_argument("--phy", default="1m", choices=list(PHY_CODE))
    r.add_argument("--dist", type=float, nargs="+", default=[10.0, 300.0, 700.0, 1000.0])
    r.add_argument("--packets", type=int, default=40)
    r.add_argument("--length", type=int, default=37)
    r.add_argument("--channel", type=int, default=19)
    r.add_argument("--compare", action="store_true", help="the same distances through ble_host.py")
    s = sub.add_parser("scan")
    s.add_argument("--dist", type=float, default=10.0)
    s.add_argument("--time", type=float, default=2.0)
    c = sub.add_parser("connect")
    c.add_argument("--dist", type=float, default=10.0)
    c.add_argument("--events", type=int, default=40, help="connection events of the packet error test")
    c.add_argument("--time", type=float, default=2.0, help="the simulations stop then")
    args = p.parse_args(argv)
    sys.path.insert(0, HERE)
    return {"selftest": cmd_selftest, "range": cmd_range, "scan": cmd_scan, "connect": cmd_connect}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
