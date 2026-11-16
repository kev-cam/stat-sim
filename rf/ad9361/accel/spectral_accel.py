#!/usr/bin/env python3
# Part of stat-sim. PolyForm Noncommercial License 1.0.0; commercial use needs a separate license (see LICENSE, COMMERCIAL.md).
"""
spectral_accel.py -- the spectral accelerator (libspectral_accel.so) from Python: check it, and time it.

The library is what nvc loads to move a --std=2040 spectral design's RF path out of the simulator
(spectral_accel_pkg.vhd; run the AN-2597 link that way with ../an2597_nvc.py --accel).  Here the same
library is driven without a simulator:

    spectral_accel.py check      the AN-2597 link: EVM against the link budget, GPU against the same
                                 stages as CPU loops (same random numbers), event by event
    spectral_accel.py radar      a phased-array radar (N transmit and N receive elements on one LO,
                                 point targets in the arena): range and bearing of the targets, and the
                                 time per event against N
    spectral_accel.py mimo       N-antenna base station and U single-antenna users on their own LOs,
                                 every antenna hearing every other: time per event against N

Build the library first: smak (or make) in this directory.
"""
import argparse
import ctypes
import math
import os
import subprocess
import sys
import tempfile
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "gpu"))
import ad9361          # noqa: E402
import an2597_link     # noqa: E402
import ofdm            # noqa: E402

LIB = os.path.join(HERE, "libspectral_accel.so")
SYMBOL_SAMPLES = 80                                   # air time of an OFDM symbol event, in samples (64 + guard)
D, P, I64 = ctypes.c_double, ctypes.POINTER(ctypes.c_double), ctypes.c_int64
PF = ctypes.POINTER(ctypes.c_float)


def chip_params(r, lines=64):
    """The SA_P_* vector of an ad9361.AD9361 in its control state: the numbers
    ad9361_pkg.ad9361_accel_params gives in VHDL (ad9361_vhdl.py check compares the two)."""
    m, fs = r.m, r.sample_rate
    att = 10.0 ** (r.tx_hardwaregain_chan0 / 10.0)
    a = math.exp(-2.0 * math.pi * m["pn_corner"] / fs)
    pn_tx = math.radians(ad9361.band("lo_pn_rms", r.tx_lo))
    pn_rx = math.radians(ad9361.band("lo_pn_rms", r.rx_lo))
    e, ph = ad9361.scalar("rx_quad_gain_err") / 100.0, math.radians(ad9361.scalar("rx_quad_phase_err"))
    kt = ad9361.K_BOLTZ * ad9361.T0
    return [
        1.0, float(lines), fs, float(r.ensm_mode in ("tx", "fdd")), float(r.ensm_mode in ("rx", "fdd")),
        r.tx_lo_actual, r.rx_lo_actual,
        math.sqrt(r._tx_lin_w() * att), ad9361.dbm_to_w(ad9361.band("tx_oip3", r.tx_lo)),
        math.sqrt(r._residual("tx") / 2.0), a, pn_tx * math.sqrt(1.0 - a * a), math.sqrt(r._tx_leak_w(att)),
        math.sqrt(max(ad9361.dbm_to_w(ad9361.band("tx_noise", r.tx_lo)) * att, kt) * fs / 2.0),
        m["tx_bblpf_corner"] * r.tx_rf_bandwidth / 2.0, m["tx_secondary_corner"] * r.tx_rf_bandwidth / 2.0,
        math.sqrt(r._residual("rx") / 2.0), a, pn_rx * math.sqrt(1.0 - a * a),
        math.sqrt(kt * fs * 10.0 ** (ad9361.band("rx_nf", r.rx_lo) / 10.0) / 2.0),
        1.0 + e, math.cos(ph), math.sin(ph),
        ad9361.band("rx_iip3", r.rx_lo), r.rx_gain_max, ad9361.scalar("rx_gain_min"), ad9361.scalar("rx_gain_step"),
        m["rx_iip3_ceiling"], ad9361.dbm_to_w(ad9361.scalar("adc_fs_at_0db")),
        m["rx_bblpf_corner"] * r.rx_rf_bandwidth / 2.0, m["rx_tia_corner"] * r.rx_rf_bandwidth / 2.0,
        math.sqrt(r.rx_lo_leak_w()),
        float({"manual": 0, "slow_attack": 1, "fast_attack": 2}[r.gain_control_mode_chan0]), r._rx_gain_set[0],
        m["fast_detect"], m["fast_target"], m["fast_clip_step"], m["fast_stronger"], m["fast_lost"],
        float(m["fast_block"]), float(m["fast_settle_iterations"]), float(m["fast_lost_blocks"]),
        float(round(m["agc_period"] * fs)), m["agc_inner_high"], m["agc_inner_low"], m["agc_outer_high"],
        m["agc_outer_low"], m["agc_step_inner"], m["agc_step_outer"]]


def _vec(x):
    a = np.ascontiguousarray(x, dtype=np.float64)
    return a, a.ctypes.data_as(P), I64(a.size)


class Accel:
    """The library's functions with their types; one design at a time (reset() starts another)."""

    def __init__(self, lib=LIB):
        if not os.path.isfile(lib):
            raise SystemExit("%s is not built: run smak (or make) in %s" % (lib, HERE))
        c = self.c = ctypes.CDLL(lib)
        for name, n in (("sa_chip_new", 1), ("sa_antenna_new", 2), ("sa_scatterer_new", 1), ("sa_commit", 0),
                        ("sa_lines", 0), ("sa_events", 0), ("sa_device_seconds", 0), ("sa_on_gpu", 0)):
            f = getattr(c, name)
            f.restype, f.argtypes = D, [D] * n
        for name, n in (("sa_wire", 3), ("sa_arena_antenna", 1), ("sa_antenna_position", 4), ("sa_scatterer_position", 4),
                        ("sa_antenna_platform", 2),
                        ("sa_agc_init", 2), ("sa_set_mode", 1), ("sa_step", 1), ("sa_reset", 0), ("sa_touch", 0)):
            f = getattr(c, name)
            f.restype, f.argtypes = None, [D] * n
        c.sa_chip_params.restype, c.sa_chip_params.argtypes = None, [D, P, I64]
        c.sa_push_tx.restype, c.sa_push_tx.argtypes = None, [D, P, I64, P, I64]
        c.sa_pull_tx.restype, c.sa_pull_tx.argtypes = None, [D, P, I64, P, I64]
        c.sa_push_rx.restype, c.sa_push_rx.argtypes = None, [D, P, I64]
        c.sa_pull_rx.restype, c.sa_pull_rx.argtypes = None, [D, P, I64]
        c.sa_tx.restype, c.sa_tx.argtypes = None, [D, D, P, I64]
        c.sa_rx.restype, c.sa_rx.argtypes = D, [D, D, P, I64]
        c.sa_read.restype, c.sa_read.argtypes = I64, [D, PF, I64]
        c.sa_tx_all.restype, c.sa_tx_all.argtypes = None, [PF, I64]
        c.sa_reset()
        self.k = 0

    def chip(self, radio, seed, lines=64, params=None):
        """A chip in the control state of `radio` (or with the vector `params`, to make many alike quickly)."""
        cid = self.c.sa_chip_new(float(seed))
        if params is None:
            self.params(cid, radio, lines)
        else:
            self.c.sa_chip_params(cid, params[1], params[2])
        return cid

    def params(self, cid, radio, lines=64):
        a, p, n = _vec(chip_params(radio, lines))
        self.c.sa_chip_params(cid, p, n)

    def antenna(self, cid, pin, position, gain_dbi=0.0, platform=0):
        """An antenna in the arena, wired to pin 0 (TX1) or 1 (RX1) of chip cid.  Antennas on the same
        platform (not 0) do not hear each other."""
        aid = self.c.sa_antenna_new(float(gain_dbi), 0.0)
        self.c.sa_wire(cid, float(pin), aid)
        self.c.sa_arena_antenna(aid)
        if platform:
            self.c.sa_antenna_platform(aid, float(platform))
        self.c.sa_antenna_position(aid, *[float(v) for v in position])
        return aid

    def scatterer(self, rcs, position):
        sid = self.c.sa_scatterer_new(float(rcs))
        self.c.sa_scatterer_position(sid, *[float(v) for v in position])
        return sid

    def commit(self):
        if self.c.sa_commit() == 0.0:
            raise SystemExit("the accelerator declined the design")
        self.k = int(self.c.sa_lines())
        self.c.sa_set_mode(1.0)

    def push_tx(self, cid, theta=0.0, leak_phase=0.0, on=False, lines=None):
        s, sp, sn = _vec([theta, leak_phase, float(on)])
        x = np.zeros(self.k, complex) if lines is None else lines
        v, vp, vn = _vec(np.asarray(x, complex).view(np.float64))
        self.c.sa_push_tx(cid, sp, sn, vp, vn)

    def pull_tx(self, cid):
        s, sp, sn = _vec(np.zeros(3))
        v, vp, vn = _vec(np.zeros(2 * self.k))
        self.c.sa_pull_tx(cid, sp, sn, vp, vn)
        return s, v.view(np.complex128).copy()

    def push_rx(self, cid, state):
        s, sp, sn = _vec(state)
        self.c.sa_push_rx(cid, sp, sn)

    def pull_rx(self, cid):
        s, sp, sn = _vec(np.zeros(7))
        self.c.sa_pull_rx(cid, sp, sn)
        return s

    def tx(self, cid, lines):
        v, vp, vn = _vec(np.asarray(lines, complex).view(np.float64))
        self.c.sa_tx(cid, 1.0, vp, vn)

    def rx(self, cid, now):
        """(sequence number or 0, lines, gain) of what chip cid's receiver delivers for the event at `now`."""
        v, vp, vn = _vec(np.zeros(2 * self.k + 1))
        seq = self.c.sa_rx(cid, float(now), vp, vn)
        return seq, v[:2 * self.k].view(np.complex128).copy(), v[2 * self.k]

    def tx_all(self, frames):
        """Every transmitter's frame at once: (n_tx, K) complex."""
        f = np.ascontiguousarray(np.asarray(frames, np.complex64)).view(np.float32)
        self.c.sa_tx_all(f.ctypes.data_as(PF), I64(f.size))

    def rx_all(self, n_rx):
        """Every receiver's frame of the last event: (n_rx, K) complex and (n_rx,) gains."""
        buf = np.zeros((n_rx, 2 * self.k + 2), np.float32)
        self.c.sa_read(0.0, buf.ctypes.data_as(PF), I64(buf.size))
        return buf[:, :2 * self.k].copy().view(np.complex64), buf[:, 2 * self.k].copy()


# ---- the AN-2597 link ---------------------------------------------------------------------------------
def link_run(args, distance, npk, rng):
    """The drone sends npk packets to the controller through the accelerator; returns the controller's
    data-port lines (events, K), its gains, and what was sent."""
    import an2597_gpu as soft                          # the software modem on spectra (numpy twin of ofdm_soft_pkg)
    a = argparse.Namespace(**vars(args))
    a.agc = "fast_attack"
    drone = an2597_link.make_radio("drone", a, args.seed, args.ppm[0])
    ctrl = an2597_link.make_radio("controller", a, args.seed + 1000, args.ppm[1])
    drone.ensm_mode, ctrl.ensm_mode = "tx", "rx"
    acc = Accel()
    c_drone, c_ctrl = acc.chip(drone, 11), acc.chip(ctrl, 23)
    acc.antenna(c_drone, 0, (distance, 0.0, 0.0), args.ant)
    acc.antenna(c_drone, 1, (distance, 0.05, 0.0), args.ant)
    acc.antenna(c_ctrl, 0, (0.0, 0.05, 0.0), args.ant)
    acc.antenna(c_ctrl, 1, (0.0, 0.0, 0.0), args.ant)
    acc.commit()
    acc.push_tx(c_drone, leak_phase=1.0)
    acc.push_rx(c_ctrl, [0.0, ctrl.rx_gain_max, 0, 0, 0, 0.0, 0])
    amp = 32768.0 * 10.0 ** (an2597_link.BACKOFF_DB / 20.0)
    t_sym = SYMBOL_SAMPLES / args.fs
    plen = args.symbols + 6
    lines = np.zeros((npk * plen, acc.k), complex)
    gains = np.zeros(npk * plen)
    sent = []
    ev = 0
    for pk in range(npk):
        mod = soft.MODS[pk * len(soft.MODS) // npk]
        const = ofdm.constellation(mod)
        pts = const[rng.integers(0, len(const), (args.symbols, 48))]
        rows = [soft.stf_lines(), soft.stf_lines(), soft.ltf_lines(), soft.ltf_lines()] + [soft.data_lines(p) for p in pts]
        rows += [np.zeros(acc.k, complex)] * 2         # two idle periods: carrier leakage and noise only
        for row in rows:
            acc.tx(c_drone, row * amp)
            seq, lines[ev], gains[ev] = acc.rx(c_ctrl, (ev + 1) * t_sym)
            assert seq != 0.0
            ev += 1
        sent.append((mod, pts))
    return lines, gains, sent, (acc.c.sa_events(), acc.c.sa_device_seconds(), acc.c.sa_on_gpu())


def handover_run(args, events, at, restore):
    """The link for `events` events; after `at` of them the drone transmitter's and the controller
    receiver's state and net data are pulled back, overwritten on the accelerator, and (restore) pushed
    out again.  Returns the controller's lines and gains."""
    import an2597_gpu as soft
    a = argparse.Namespace(**vars(args))
    a.agc = "fast_attack"
    drone = an2597_link.make_radio("drone", a, args.seed, args.ppm[0])
    ctrl = an2597_link.make_radio("controller", a, args.seed + 1000, args.ppm[1])
    drone.ensm_mode, ctrl.ensm_mode = "tx", "rx"
    acc = Accel()
    c_drone, c_ctrl = acc.chip(drone, 11), acc.chip(ctrl, 23)
    acc.antenna(c_drone, 0, (30.0, 0.0, 0.0), args.ant)
    acc.antenna(c_drone, 1, (30.0, 0.05, 0.0), args.ant)
    acc.antenna(c_ctrl, 0, (0.0, 0.05, 0.0), args.ant)
    acc.antenna(c_ctrl, 1, (0.0, 0.0, 0.0), args.ant)
    acc.commit()
    acc.push_tx(c_drone, leak_phase=1.0)
    acc.push_rx(c_ctrl, [0.0, ctrl.rx_gain_max, 0, 0, 0, 0.0, 0])
    rng = np.random.default_rng(args.seed)
    amp = 32768.0 * 10.0 ** (an2597_link.BACKOFF_DB / 20.0)
    const = ofdm.constellation("16qam")
    lines = np.zeros((events, acc.k), complex)
    gains = np.zeros(events)
    for ev in range(events):
        if ev == at:
            tx_state, tx_lines = acc.pull_tx(c_drone)
            rx_state = acc.pull_rx(c_ctrl)
            acc.c.sa_set_mode(0.0)
            acc.push_tx(c_drone, theta=1.0, leak_phase=2.0, on=False)          # whatever was there is gone
            acc.push_rx(c_ctrl, [0.5, 20.0, 1, 2, 3, 100.0, 5])
            acc.c.sa_set_mode(1.0)
            if restore:
                acc.push_tx(c_drone, tx_state[0], tx_state[1], tx_state[2] != 0.0, tx_lines)
                acc.push_rx(c_ctrl, rx_state)
        row = soft.data_lines(const[rng.integers(0, len(const), 48)]) if ev % 4 else soft.stf_lines()
        acc.tx(c_drone, row * amp)
        _, lines[ev], gains[ev] = acc.rx(c_ctrl, (ev + 1) * SYMBOL_SAMPLES / args.fs)
    return lines, gains


def cmd_check(args):
    import an2597_gpu as soft
    if args.dump:                                      # the child: one distance, write what the receiver delivered
        rng = np.random.default_rng(args.seed)
        lines, gains, _, _ = link_run(args, args.distances[0], args.packets * len(soft.MODS), rng)
        np.savez(args.dump, lines=lines, gains=gains)
        return 0
    print("AN-2597 link through the spectral accelerator (one thread per frequency line): LO %.1f MHz, %.0f MHz "
          "channel, antennas %.1f dBi, reference offsets %+.1f / %+.1f ppm, %d packets of %d symbols per modulation"
          % (args.lo / 1e6, args.fs / 1e6, args.ant, args.ppm[0], args.ppm[1], args.packets, args.symbols))
    head = "%8s %8s %6s %7s" % ("dist m", "Prx dBm", "gain", "budget")
    for m in soft.MODS:
        head += " | %5s %6s %8s" % (m, "EVM", "BER")
    print(head + " | GPU vs CPU loops")
    worst = 0.0
    worst_diff = 0.0
    gain_diff = 0
    per_event = []
    for d in args.distances:
        rng = np.random.default_rng(args.seed)
        lines, gains, sent, (events, secs, on_gpu) = link_run(args, d, args.packets * len(soft.MODS), rng)
        per_event.append(secs / events)
        dem = soft.demodulate(lines, sent, args.symbols)
        prx, evm_budget = an2597_link.budget(args, d)
        plen = args.symbols + 6
        line, gl = "", []
        for m in soft.MODS:
            idx = [i for i, (mm, _) in enumerate(sent) if mm == m]
            found = [dem[i] for i in idx if dem[i] is not None]
            nbits = len(idx) * args.symbols * 48 * ofdm.BITS[m]
            errors = sum(f[1] for f in found) + (len(idx) - len(found)) * (nbits // len(idx)) // 2
            evm = 10.0 * math.log10(np.mean([f[0] for f in found])) if found else float("nan")
            gl += [gains[i * plen + dem[i][2]] for i in idx if dem[i] is not None]
            line += " | %2d/%-2d %6.1f %8.1e" % (len(found), len(idx), evm, errors / nbits)
            if len(found) == len(idx):
                worst = max(worst, abs(evm - evm_budget))
        # the same run with the stages as CPU loops, same random numbers
        with tempfile.TemporaryDirectory() as tmp:
            dump = os.path.join(tmp, "cpu.npz")
            env = dict(os.environ, SPECTRAL_ACCEL_DEVICE="cpu")
            cmd = [sys.executable, os.path.abspath(__file__), "check", "--dump", dump, "--distances", str(d)]
            for k in ("lo", "fs", "atten", "ant", "packets", "symbols", "seed"):
                cmd += ["--" + k, str(getattr(args, k))]
            cmd += ["--ppm", str(args.ppm[0]), str(args.ppm[1])]
            r = subprocess.run(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
            if r.returncode != 0:
                raise SystemExit("the CPU run failed:\n%s" % r.stdout)
            ref = np.load(dump)
        diff = float(np.max(np.abs(lines - ref["lines"])))
        ngd = int(np.sum(gains != ref["gains"]))
        worst_diff = max(worst_diff, diff)
        gain_diff += ngd
        print("%8.0f %8.1f %6.1f %7.1f%s | %d gains differ, lines within %.3g"
              % (d, prx, float(np.median(gl)) if gl else float("nan"), evm_budget, line, ngd, diff))
    print("largest |EVM - budget| where every packet was found: %.2f dB" % worst)
    print("%s against the CPU loops, every event of every run: %d gain differences, largest difference of a received "
          "line %.3g (data-port units, one ADC word is 1)" % ("GPU" if on_gpu else "CPU", gain_diff, worst_diff))
    print("time per event on the %s, called one event at a time: %.1f us (an event is %.1f us of air time)"
          % ("GPU" if on_gpu else "CPU", 1e6 * float(np.min(per_event)), 1e6 * SYMBOL_SAMPLES / args.fs))
    # hand-over: is what comes back everything?
    n, at = 240, 97
    straight = handover_run(args, n, -1, True)
    back = handover_run(args, n, at, True)
    lost = handover_run(args, n, at, False)
    same = np.array_equal(straight[0], back[0]) and np.array_equal(straight[1], back[1])
    sensitive = not np.array_equal(straight[0][at:], lost[0][at:])
    print("hand-over: state and net data pulled back after %d events, overwritten on the accelerator, pushed out "
          "again: the following %d events are %s those of the uninterrupted run%s"
          % (at, n - at, "identical to" if same else "DIFFERENT from",
             " (and differ when the state is not put back)" if sensitive else "; the test is NOT sensitive"))
    return 0 if gain_diff == 0 and same and sensitive else 1


# ---- a phased-array radar ---------------------------------------------------------------------------------
def array_radio(args, mode="fdd", ppm=0.0, agc="fast_attack"):
    r = ad9361.AD9361("element", seed=0)
    r.rx_lo = r.tx_lo = args.lo
    r.sample_rate = args.fs
    r.rx_rf_bandwidth = r.tx_rf_bandwidth = 0.9 * args.fs
    r.xo_ppm = ppm
    r.gain_control_mode_chan0 = agc
    r.tx_hardwaregain_chan0 = -args.atten
    r.ensm_mode = mode
    return r


def radar_design(args, n, targets, isolate):
    """n chips on one LO, each with a transmit element (a line along y at z = 0, half a wavelength apart)
    and a receive element (the same line at z = args.sep); targets: (range m, bearing deg, rcs m2, radial
    speed m/s) in the plane half way up.  isolate: the two arrays are one platform and do not hear each
    other directly.  Returns (accelerator, element y positions, scatterer ids)."""
    acc = Accel()
    r = array_radio(args)
    params = _vec(chip_params(r, args.lines))
    y = (np.arange(n) - (n - 1) / 2.0) * (ad9361.C0 / args.lo / 2.0)
    chips = []
    for i in range(n):
        c = acc.chip(None, 100 + i, params=params)
        acc.antenna(c, 0, (0.0, y[i], 0.0), args.ant, platform=1 if isolate else 0)
        acc.antenna(c, 1, (0.0, y[i], args.sep), args.ant, platform=1 if isolate else 0)
        chips.append(c)
    sids = [acc.scatterer(rcs, target_position(args, rng_m, brg, 0.0, 0.0)) for rng_m, brg, rcs, _ in targets]
    acc.commit()
    rng = np.random.default_rng(args.seed)
    for c in chips:
        acc.push_tx(c, leak_phase=float(rng.uniform(0.0, 2.0 * math.pi)))
        acc.push_rx(c, [0.0, r.rx_gain_max, 0, 0, 0, 0.0, 0])
    return acc, y, sids


def target_position(args, range_m, bearing_deg, speed, t):
    b = math.radians(bearing_deg)
    rr = range_m + speed * t
    return (rr * math.cos(b), rr * math.sin(b), args.sep / 2.0)


def steering(args, y, bearing_deg, range_m=1.0e7):
    """Element weights that focus the array on a point at a bearing (from broadside, in the x-y plane) and
    range: each element's own distance to it.  (A long array is in its own near field out to 2 D^2 /
    lambda, 4 km for 256 elements at 2.4 GHz; a plane wave's weights would blur.)"""
    b = np.radians(bearing_deg)
    d = np.sqrt((range_m * np.cos(b)) ** 2 + (range_m * np.sin(b) - y) ** 2 + (args.sep / 2.0) ** 2)
    return np.exp(2j * np.pi * args.lo * (d - range_m) / ad9361.C0)


def cmd_radar(args):
    import an2597_gpu as soft
    if args.lines != 64:                               # the check uses the 64-line OFDM pulse
        radar_timing(args)
        return 0
    targets = [(120.0, 12.0, 10.0, -40.0), (210.0, -25.0, 30.0, 75.0), (160.0, 45.0, 100.0, 120.0)]
    n, m, pri = args.n, args.pulses, args.pri
    lam = ad9361.C0 / args.lo
    sym = soft.ltf_lines()
    used = soft.USED
    amp = 32768.0 * 10.0 ** (an2597_link.BACKOFF_DB / 20.0)
    print("phased-array radar through the spectral accelerator: %d transmit and %d receive elements on one LO at %.1f MHz, "
          "%.0f MHz OFDM pulses of %d lines every %.0f us, %d pulses per look" % (n, n, args.lo / 1e6, args.fs / 1e6, args.lines,
                                                                                 pri * 1e6, m))
    print("%-34s | %-34s | %s" % ("target: range m, bearing deg, m/s", "found", "peak over the rest, dB"))
    acc, y, sids = radar_design(args, n, targets, isolate=False)
    win = np.blackman(m + 2)[1:-1]                                 # pulse to pulse: keeps the leakage's skirt out of the moving bins
    wr = np.zeros(acc.k)                                            # across the lines: range sidelobes
    wr[used] = 0.5 + 0.5 * np.cos(2.0 * np.pi * np.where(used < acc.k // 2, used, used - acc.k) / 54.0)
    os_r = 8
    # what the radar knows about its own hardware: the two baseband filters every echo went through (they
    # delay it by some tens of ns, metres of range); the echoes are divided by them
    radio = array_radio(args)
    off = np.fft.fftfreq(acc.k, 1.0 / args.fs)
    cal = np.ones(acc.k, complex)
    cal[used] = 1.0 / (radio._analog_response("tx", off[used]) * radio._analog_response("rx", off[used]))
    bad = 0
    t = 0.0
    for ti, (rng_m, brg, rcs, speed) in enumerate(targets):
        w = steering(args, y, brg, rng_m)
        frames = (amp * sym[None, :] * w[:, None]).astype(np.complex64)
        h = np.zeros((m, n, acc.k), complex)
        for p in range(m):
            for sid, (r0, b0, _, v0) in zip(sids, targets):
                acc.c.sa_scatterer_position(sid, *target_position(args, r0, b0, v0, t))
            acc.tx_all(frames)
            acc.c.sa_step(t)
            x, g = acc.rx_all(n)
            h[p][:, used] = x[:, used] * cal[used] / sym[used] / (10.0 ** (g[:, None] / 20.0))
            t += pri
        # per element: range (lines -> delay) and Doppler (pulse to pulse)
        rd = np.fft.fft(np.fft.ifft(h * wr, n=acc.k * os_r, axis=2) * win[:, None, None], axis=0)
        beam = np.tensordot(rd, w, axes=([1], [0]))                 # receive beam at the look's bearing
        power = np.abs(beam) ** 2
        power[[0, 1, 2, m - 2, m - 1]] = 0.0                        # what does not move: the direct path between the arrays
        near = int(args.blank * 2.0 * args.fs * os_r / ad9361.C0)    # ... and its phase noise, which stays at its range
        power[:, :near] = 0.0
        power[:, acc.k * os_r - near:] = 0.0
        pb, nb = np.unravel_index(np.argmax(power), power.shape)
        fd = (pb if pb < m / 2 else pb - m) / (m * pri)
        found_range = ad9361.C0 * nb / (2.0 * args.fs * os_r)
        found_speed = -fd * lam / 2.0
        scan = np.linspace(-60.0, 60.0, 2401)
        resp = np.abs(np.array([steering(args, y, a, found_range) for a in scan]) @ rd[pb, :, nb])
        found_brg = scan[np.argmax(resp)]
        rest = power.copy()                                         # everything outside the peak's own main lobe
        rest[np.arange(pb - 4, pb + 5) % m, max(0, nb - 4 * os_r):nb + 4 * os_r + 1] = 0.0
        margin = 10.0 * math.log10(power[pb, nb] / np.max(rest))
        floor = 10.0 * math.log10(power[pb, nb] / np.median(rest[rest > 0.0]))
        true_range = rng_m + speed * (t - m * pri / 2.0)
        ok = (abs(found_range - true_range) < 4.0 and abs(found_speed - speed) < lam / (2.0 * m * pri)
              and abs(found_brg - brg) < max(60.0 / n, 0.3))
        bad += 0 if ok else 1
        print("%10.1f %10.1f %10.1f   | %10.1f %10.1f %10.1f   | %5.1f (%4.1f over the median)  %s"
              % (true_range, brg, speed, found_range, found_brg, found_speed, margin, floor, "ok" if ok else "MISSED"))
    events, secs = acc.c.sa_events(), acc.c.sa_device_seconds()
    print("%d events, %.3f ms each on the %s" % (events, 1e3 * secs / events, "GPU" if acc.c.sa_on_gpu() else "CPU"))
    if args.sizes:
        radar_timing(args)
    return 1 if bad else 0


def timed(acc, n_rx, frames, events, move=None):
    """Seconds per event over `events` events after a few to warm up; move(i): called before event i."""
    for i in range(3):
        acc.tx_all(frames)
        acc.c.sa_step(i * 4e-6)
    acc.rx_all(n_rx)
    t0 = acc.c.sa_device_seconds()
    for i in range(events):
        if move:
            move(i)
        acc.tx_all(frames)
        acc.c.sa_step((i + 3) * 4e-6)
    return (acc.c.sa_device_seconds() - t0) / events


def radar_timing(args):
    targets = [(100.0 + 37.0 * i, -40.0 + 9.0 * i, 10.0, 30.0) for i in range(args.targets)]
    t_sym = SYMBOL_SAMPLES / args.fs * args.lines / 64.0
    print("\ntime per event, one event at a time (%d lines; an event is %.1f us of signal; %d targets):" % (args.lines, t_sym * 1e6, args.targets))
    print("%9s | %-31s | %-31s | %-31s" % ("", "arrays hear each other (N x N)", "arrays isolated: echoes only", "isolated, targets move each event"))
    print("%9s | %10s %9s %10s | %10s %9s %10s | %10s %9s %10s"
          % ("elements", "ms/event", "events/s", "x real", "ms/event", "events/s", "x real", "ms/event", "events/s", "x real"))
    rng = np.random.default_rng(args.seed)
    for n in args.sizes:
        row = "%4d+%-4d" % (n, n)
        for isolate, moving in ((False, False), (True, False), (True, True)):
            acc, y, sids = radar_design(args, n, targets, isolate)
            sym = (rng.integers(0, 2, acc.k) * 2 - 1 + 1j * (rng.integers(0, 2, acc.k) * 2 - 1)) / math.sqrt(2.0 * acc.k)
            frames = (32768.0 * 10.0 ** (an2597_link.BACKOFF_DB / 20.0) * sym[None, :] * steering(args, y, 10.0)[:, None]).astype(np.complex64)
            events = max(5, min(300, int(2.0e8 / (n * n * acc.k)))) if not isolate else max(20, min(500, int(4.0e7 / (n * acc.k))))

            def move(i):
                for sid, (r0, b0, _, v0) in zip(sids, targets):
                    acc.c.sa_scatterer_position(sid, *target_position(args, r0, b0, v0, i * 1e-4))
            per = timed(acc, n, frames, events, move if moving else None)
            row += " | %10.3f %9.0f %10.4f" % (per * 1e3, 1.0 / per, t_sym / per)
        print(row, flush=True)


def cmd_mimo(args):
    """N receive antennas on one LO (a base station) and U users each on its own LO, all transmitting:
    time per event against N."""
    t_sym = SYMBOL_SAMPLES / args.fs * args.lines / 64.0
    print("multi-user uplink through the spectral accelerator: N base-station receive antennas on one LO, %d users each on "
          "its own LO, %d lines; an event is %.1f us of signal" % (args.users, args.lines, t_sym * 1e6))
    print("%9s | %10s %9s %10s" % ("antennas", "ms/event", "events/s", "x real"))
    rng = np.random.default_rng(args.seed)
    for n in args.sizes:
        acc = Accel()
        bs = _vec(chip_params(array_radio(args, "rx"), args.lines))
        y = (np.arange(n) - (n - 1) / 2.0) * (ad9361.C0 / args.lo / 2.0)
        chips = []
        for i in range(n):
            c = acc.chip(None, 100 + i, params=bs)
            acc.antenna(c, 1, (0.0, y[i], 10.0), args.ant, platform=1)
            chips.append(c)
        users = []
        for u in range(args.users):
            c = acc.chip(array_radio(args, "tx", ppm=float(rng.uniform(-2.0, 2.0))), 5000 + u, lines=args.lines)
            b = math.radians(-50.0 + 100.0 * u / max(1, args.users - 1))
            acc.antenna(c, 0, (150.0 * math.cos(b), 150.0 * math.sin(b), 1.5), args.ant)
            users.append(c)
        acc.commit()
        for c in users:
            acc.push_tx(c, leak_phase=float(rng.uniform(0.0, 6.28)))
        for c in chips:
            acc.push_rx(c, [0.0, array_radio(args).rx_gain_max, 0, 0, 0, 0.0, 0])
        sym = (rng.integers(0, 2, (args.users, acc.k)) * 2 - 1 + 1j * (rng.integers(0, 2, (args.users, acc.k)) * 2 - 1)) / math.sqrt(2.0 * acc.k)
        frames = (32768.0 * 10.0 ** (an2597_link.BACKOFF_DB / 20.0) * sym).astype(np.complex64)
        per = timed(acc, n, frames, max(20, min(500, int(4.0e7 / (n * acc.k * args.users)))))
        print("%9d | %10.3f %9.0f %10.4f" % (n, per * 1e3, 1.0 / per, t_sym / per), flush=True)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("radar", "mimo"):
        p = sub.add_parser(name)
        p.add_argument("--lo", type=float, default=2.437e9)
        p.add_argument("--fs", type=float, default=20e6)
        p.add_argument("--atten", type=float, default=0.0)
        p.add_argument("--ant", type=float, default=2.0)
        p.add_argument("--lines", type=int, default=64, help="lines per event (a power of two, 16 to 1024)")
        p.add_argument("--seed", type=int, default=1)
        p.add_argument("--sizes", type=int, nargs="*", default=[8, 16, 32, 64, 128, 256, 512] if name == "radar" else
                       [16, 64, 256, 1024, 4096], help="array sizes for the timing table")
        if name == "radar":
            p.add_argument("-n", type=int, default=64, help="elements per array for the check")
            p.add_argument("--sep", type=float, default=3.0, help="height of the receive array over the transmit array, m")
            p.add_argument("--pulses", type=int, default=64)
            p.add_argument("--pri", type=float, default=100e-6)
            p.add_argument("--targets", type=int, default=4, help="targets in the timing table")
            p.add_argument("--blank", type=float, default=45.0, help="shortest range looked at, m")
        else:
            p.add_argument("--users", type=int, default=8)
    p = sub.add_parser("check")
    p.add_argument("--lo", type=float, default=2.437e9)
    p.add_argument("--fs", type=float, default=20e6)
    p.add_argument("--atten", type=float, default=0.0)
    p.add_argument("--ant", type=float, default=2.0)
    p.add_argument("--ppm", type=float, nargs=2, default=(1.0, -1.5))
    p.add_argument("--distances", type=float, nargs="+", default=[1, 3, 10, 30, 100, 300])
    p.add_argument("--packets", type=int, default=5, help="per modulation")
    p.add_argument("--symbols", type=int, default=20)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--dump", help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    args.pa, args.lna, args.lna_nf, args.agc = 0.0, 0.0, None, "fast_attack"
    return {"check": cmd_check, "radar": cmd_radar, "mimo": cmd_mimo}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
