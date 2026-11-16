#!/usr/bin/env python3
# Part of stat-sim. PolyForm Noncommercial License 1.0.0; commercial use needs a separate license (see LICENSE, COMMERCIAL.md).
"""
an2597_gpu.py -- the AN-2597 link's spectral event model on a GPU: check it, and time it.

Builds the scenario from the tables in ../ad9361.py (the two radios' constants in their control state,
the coupling between them, the symbols the drone's software sends), runs ./ad9361_gpu on it, and
demodulates what the controller's data port delivers with a software modem on spectra (the numpy twin
of ofdm_soft_pkg.vhd).  Prints, per distance, EVM and uncoded bit error rate next to the link budget;
then the real-time factor of the GPU and of the same code on the CPU for a range of window sizes.

    make                         (or smak) builds ad9361_gpu
    an2597_gpu.py                the distance sweep, then timings
    an2597_gpu.py --radios 8     timings with 8 radios all hearing each other (no demodulation)
"""
import argparse
import math
import os
import re
import subprocess
import sys
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import ad9361          # noqa: E402
import an2597_link     # noqa: E402
import ofdm            # noqa: E402

NK = 64
SYMBOL_SAMPLES = 80
MODS = ("bpsk", "qpsk", "16qam", "64qam")
TX = np.dtype([("on", "i4"), ("amp", "f4"), ("ip3", "f4"), ("res_sigma", "f4"), ("pn_sigma", "f4"), ("pn_a", "f4"),
               ("pn_w", "f4"), ("leak_re", "f4"), ("leak_im", "f4"), ("noise_sigma", "f4"), ("h_re", "f4", NK),
               ("h_im", "f4", NK)], align=True)
RX = np.dtype([("on", "i4"), ("res_sigma", "f4"), ("pn_sigma", "f4"), ("pn_a", "f4"), ("pn_w", "f4"),
               ("noise_sigma", "f4"), ("iq_g", "f4"), ("iq_c", "f4"), ("iq_s", "f4"), ("iip3_max_dbm", "f4"),
               ("gmax_db", "f4"), ("iip3_ceil_dbm", "f4"), ("fs0_w", "f4")], align=True)
PAIR = np.dtype([("on", "i4"), ("eps", "f4"), ("dphi", "f8"), ("c_re", "f4", NK), ("c_im", "f4", NK)], align=True)
AGC = np.dtype([("mode", "i4"), ("manual_db", "f4"), ("gmax_db", "f4"), ("gmin_db", "f4"), ("detect", "f4"),
                ("target", "f4"), ("clip_step", "f4"), ("stronger", "f4"), ("lost", "f4"),
                ("settle_iterations", "i4"), ("lost_blocks", "i4")], align=True)


def line_offsets(fs):
    """Frequency of each line against the carrier, FFT order."""
    return np.fft.fftfreq(NK, 1.0 / fs)


# ---- the software modem on spectra (numpy twin of ofdm_soft_pkg.vhd) -------------------------
USED = ofdm.USED % NK
DATA = ofdm.DATA % NK
PILOT = ofdm.PILOTS % NK
STF_K = np.array(sorted(ofdm._STF_SIGN)) % NK


def stf_lines():
    x = np.zeros(NK, complex)
    for k, sgn in ofdm._STF_SIGN.items():
        x[k % NK] = sgn * (1 + 1j) / math.sqrt(24.0)
    return x


def ltf_lines():
    x = np.zeros(NK, complex)
    x[USED] = ofdm._LTF[ofdm.USED + 26] / math.sqrt(52.0)
    return x


def data_lines(points):
    x = np.zeros(NK, complex)
    x[DATA] = points / math.sqrt(52.0)
    x[PILOT] = ofdm.PILOT_VALUES / math.sqrt(52.0)
    return x


def is_stf(x):
    total = np.sum(np.abs(x) ** 2)
    return total > 0.0 and np.sum(np.abs(x[STF_K]) ** 2) > 0.5 * total


def correct(x, eps, symbol):
    """Remove a carrier offset of eps line spacings from the event `symbol` periods after the reference."""
    t = np.fft.ifft(x) * np.exp(-2j * np.pi * eps * np.arange(NK) / NK)
    return np.fft.fft(t) * np.exp(-2j * np.pi * eps * SYMBOL_SAMPLES / NK * symbol)


def demodulate(lines, sent, nsym):
    """lines: (B, 64) data-port lines at the receiver; sent: per packet a list of (mod, points (nsym, 48)).
    Returns per packet None (not found) or (evm power ratio, bit errors, index of the first data symbol)."""
    out = [None] * len(sent)
    plen = nsym + 6
    for pk, (mod, pts) in enumerate(sent):
        seg = lines[pk * plen:(pk + 1) * plen]
        state, b = "idle", 0
        ltf1 = None
        while b < plen:
            x = seg[b]
            if state == "idle":
                if is_stf(x):
                    state = "stf"
            elif state == "stf":
                if not is_stf(x):
                    ltf1, state = x, "ltf1"
            elif state == "ltf1":
                eps = np.angle(np.sum(np.conj(ltf1[USED]) * x[USED])) / (2.0 * math.pi) * NK / SYMBOL_SAMPLES
                l1, l2 = correct(ltf1, eps, 0), correct(x, eps, 1)
                h = np.zeros(NK, complex)
                h[USED] = (l1[USED] + l2[USED]) / 2.0 / (ofdm._LTF[ofdm.USED + 26] / math.sqrt(52.0))
                first = b + 1
                if first + nsym > plen:
                    break
                const = ofdm.constellation(mod)
                err = ref = 0.0
                bit_errors = 0
                for n in range(nsym):
                    y = correct(seg[first + n], eps, 2 + n)
                    ph = np.angle(np.sum(y[PILOT] * np.conj(h[PILOT] * ofdm.PILOT_VALUES)))
                    eq = y[DATA] / h[DATA] * np.exp(-1j * ph) * math.sqrt(52.0)
                    want = pts[n]
                    err += np.sum(np.abs(eq - want) ** 2)
                    ref += np.sum(np.abs(want) ** 2)
                    got = np.argmin(np.abs(eq.reshape(-1, 1) - const.reshape(1, -1)), axis=1)
                    was = np.argmin(np.abs(want.reshape(-1, 1) - const.reshape(1, -1)), axis=1)
                    bit_errors += int(sum(bin(int(v)).count("1") for v in (got ^ was)))
                out[pk] = (err / ref, bit_errors, first)
                break
            b += 1
    return out


# ---- scenario ---------------------------------------------------------------------------------
def radio_records(r, tx_on, rx_on):
    """The constants of one radio in its present control state, as the kernels want them."""
    fs = r.sample_rate
    off = line_offsets(fs)
    a = math.exp(-2.0 * math.pi * r.m["pn_corner"] / fs)
    t = np.zeros((), TX)
    att = 10.0 ** (r.tx_hardwaregain_chan0 / 10.0)
    pn = math.radians(ad9361.band("lo_pn_rms", r.tx_lo))
    h = r._analog_response("tx", off)
    leak = math.sqrt(r._tx_leak_w(att)) * np.exp(1j * r._tx_leak_phase[0])
    t["on"], t["amp"], t["ip3"] = tx_on, math.sqrt(r._tx_lin_w() * att), ad9361.dbm_to_w(ad9361.band("tx_oip3", r.tx_lo))
    t["res_sigma"], t["pn_sigma"], t["pn_a"], t["pn_w"] = math.sqrt(r._residual("tx") / 2.0), pn, a, pn * math.sqrt(1 - a * a)
    t["leak_re"], t["leak_im"] = leak.real, leak.imag
    t["noise_sigma"] = math.sqrt(max(ad9361.dbm_to_w(ad9361.band("tx_noise", r.tx_lo)) * att, ad9361.K_BOLTZ * ad9361.T0) * fs / 2.0)
    t["h_re"], t["h_im"] = h.real, h.imag
    x = np.zeros((), RX)
    pn = math.radians(ad9361.band("lo_pn_rms", r.rx_lo))
    e, p = ad9361.scalar("rx_quad_gain_err") / 100.0, math.radians(ad9361.scalar("rx_quad_phase_err"))
    x["on"], x["res_sigma"], x["pn_sigma"], x["pn_a"], x["pn_w"] = rx_on, math.sqrt(r._residual("rx") / 2.0), pn, a, pn * math.sqrt(1 - a * a)
    x["noise_sigma"] = math.sqrt(ad9361.K_BOLTZ * ad9361.T0 * fs * 10.0 ** (ad9361.band("rx_nf", r.rx_lo) / 10.0) / 2.0)
    x["iq_g"], x["iq_c"], x["iq_s"] = 1.0 + e, math.cos(p), math.sin(p)
    x["iip3_max_dbm"], x["gmax_db"], x["iip3_ceil_dbm"] = ad9361.band("rx_iip3", r.rx_lo), r.rx_gain_max, r.m["rx_iip3_ceiling"]
    x["fs0_w"] = ad9361.dbm_to_w(ad9361.scalar("adc_fs_at_0db"))
    g = np.zeros((), AGC)
    m = r.m
    g["mode"] = 1 if r.gain_control_mode_chan0 == "fast_attack" else 0
    g["manual_db"], g["gmax_db"], g["gmin_db"] = r.rx_hardwaregain_chan0, r.rx_gain_max, ad9361.scalar("rx_gain_min")
    g["detect"], g["target"], g["clip_step"], g["stronger"], g["lost"] = (m["fast_detect"], m["fast_target"], m["fast_clip_step"],
                                                                         m["fast_stronger"], m["fast_lost"])
    g["settle_iterations"], g["lost_blocks"] = m["fast_settle_iterations"], m["fast_lost_blocks"]
    return t, x, g


def pair_record(rx, tx, distance, ant_dbi, t_sym):
    """Receiver rx hearing transmitter tx over `distance` metres."""
    fs = tx.sample_rate
    df = tx.tx_lo_actual - rx.rx_lo_actual
    f = tx.tx_lo_actual + line_offsets(fs)
    c = 10.0 ** (2.0 * ant_dbi / 20.0) * ad9361.C0 / (4.0 * math.pi * distance * f) * np.exp(-2j * np.pi * (f * distance / ad9361.C0 % 1.0))
    # the receiver's baseband filter on the sender's grid, at the frequencies the receiver sees
    c = c * rx._analog_response("rx", line_offsets(fs) + df)
    p = np.zeros((), PAIR)
    p["on"], p["eps"], p["dphi"] = 1, df / (fs / NK), df * t_sym
    p["c_re"], p["c_im"] = c.real, c.imag
    return p


def write_scenario(path, txs, rxs, pairs, agcs, bins, t_sym):
    m, b = bins.shape[0], bins.shape[1]
    with open(path, "wb") as fh:
        np.array([0x41393336, m, b, 0, TX.itemsize, RX.itemsize, PAIR.itemsize, AGC.itemsize], "i4").tofile(fh)
        np.array([t_sym], "f8").tofile(fh)
        np.array(txs, TX).tofile(fh)
        np.array(rxs, RX).tofile(fh)
        np.array(pairs, PAIR).reshape(m * m).tofile(fh)
        np.array(agcs, AGC).tofile(fh)
        inter = np.empty(bins.shape + (2,), "f4")
        inter[..., 0], inter[..., 1] = bins.real, bins.imag
        inter.tofile(fh)


def run_gpu(scenario, windows, cpu_windows=3, seed=1):
    out = scenario + ".out"
    r = subprocess.run([os.path.join(HERE, "ad9361_gpu"), scenario, out, "--windows", str(windows), "--cpu-windows",
                        str(cpu_windows), "--seed", str(seed)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       universal_newlines=True)
    if r.returncode != 0:
        raise SystemExit("ad9361_gpu failed:\n%s" % r.stdout)
    res = dict(re.findall(r"(\w+)=(\S+)", " ".join(l[7:] for l in r.stdout.splitlines() if l.startswith("RESULT "))))
    with open(out, "rb") as fh:
        m, b = np.fromfile(fh, "i4", 2)
        gains = np.fromfile(fh, "f4", m * b * 4).reshape(m, b, 4)
        raw = np.fromfile(fh, "f4", m * b * NK * 2).reshape(m, b, NK, 2)
    os.remove(out)
    return res, gains, raw[..., 0] + 1j * raw[..., 1]


def link_scenario(args, distance, npk, rng, mod=None):
    """Drone (radio 0) sending npk packets to the controller (radio 1).  Returns the scenario parts and
    what was sent."""
    a = argparse.Namespace(**vars(args))
    a.agc = "fast_attack"
    drone = an2597_link.make_radio("drone", a, args.seed, args.ppm[0])
    ctrl = an2597_link.make_radio("controller", a, args.seed + 1000, args.ppm[1])
    t_sym = SYMBOL_SAMPLES / args.fs
    t0, x0, g0 = radio_records(drone, 1, 0)
    t1, x1, g1 = radio_records(ctrl, 0, 1)
    pairs = np.zeros((2, 2), PAIR)
    pairs[1, 0] = pair_record(ctrl, drone, distance, args.ant, t_sym)
    amp = 32768.0 * 10.0 ** (an2597_link.BACKOFF_DB / 20.0)
    plen = args.symbols + 6
    bins = np.zeros((2, npk * plen, NK), complex)
    sent = []
    for pk in range(npk):
        m = mod or MODS[pk * len(MODS) // npk]
        const = ofdm.constellation(m)
        pts = const[rng.integers(0, len(const), (args.symbols, 48))]
        rows = [stf_lines(), stf_lines(), ltf_lines(), ltf_lines()] + [data_lines(p) for p in pts]
        bins[0, pk * plen:pk * plen + len(rows)] = np.array(rows) * amp
        sent.append((m, pts))
    return ([t0, t1], [x0, x1], pairs, [g0, g1], bins, t_sym), sent


def cmd_sweep(args, tmp):
    rng = np.random.default_rng(args.seed)
    print("AN-2597 link, spectral events on the GPU: LO %.1f MHz, %.0f MHz channel, antennas %.1f dBi, reference offsets "
          "%+.1f / %+.1f ppm, %d packets of %d symbols per modulation" % (args.lo / 1e6, args.fs / 1e6, args.ant,
                                                                         args.ppm[0], args.ppm[1], args.packets, args.symbols))
    head = "%8s %8s %6s %7s" % ("dist m", "Prx dBm", "gain", "budget")
    for m in MODS:
        head += " | %5s %6s %8s" % (m, "EVM", "BER")
    print(head)
    worst = 0.0
    mismatch = 0
    maxdiff = 0.0
    for d in args.distances:
        parts, sent = link_scenario(args, d, args.packets * len(MODS), rng)
        path = os.path.join(tmp, "link.bin")
        write_scenario(path, *parts)
        res, gains, lines = run_gpu(path, 1, 1, args.seed)
        mismatch += int(res["gpu_cpu_gain_mismatches"])
        maxdiff = max(maxdiff, float(res["gpu_cpu_max_line_diff"]))
        dem = demodulate(lines[1], sent, args.symbols)
        prx, evm_budget = an2597_link.budget(args, d)
        plen = args.symbols + 6
        line = ""
        gl = []
        for m in MODS:
            idx = [i for i, (mm, _) in enumerate(sent) if mm == m]
            found = [dem[i] for i in idx if dem[i] is not None]
            nbits = len(idx) * args.symbols * 48 * ofdm.BITS[m]
            errors = sum(f[1] for f in found) + (len(idx) - len(found)) * (nbits // len(idx)) // 2
            evm = 10.0 * math.log10(np.mean([f[0] for f in found])) if found else float("nan")
            gl += [gains[1, i * plen + f[2], 0] for i, f in zip(idx, [dem[i] for i in idx]) if f is not None]
            line += " | %2d/%-2d %6.1f %8.1e" % (len(found), len(idx), evm, errors / nbits)
            if len(found) == len(idx):
                worst = max(worst, abs(evm - evm_budget))
        print("%8.0f %8.1f %6.1f %7.1f%s" % (d, prx, float(np.median(gl)) if gl else float("nan"), evm_budget, line))
    print("largest |EVM - budget| where every packet was found: %.2f dB" % worst)
    print("GPU against the CPU reference (same random numbers), first window of each run: %d gain mismatches, largest "
          "difference of a received line %.3g (data-port units)" % (mismatch, maxdiff))


def cmd_speed(args, tmp):
    rng = np.random.default_rng(args.seed)
    plen = args.symbols + 6
    print("\nreal-time factor (air time of a window / wall time), %d radio(s), %.0f MSPS, symbol %.1f us"
          % (args.radios, args.fs / 1e6, SYMBOL_SAMPLES / args.fs * 1e6))
    print("%10s %10s | %12s %9s | %12s %9s | %9s %9s" % ("symbols", "air ms", "GPU+AGC ms", "x real", "GPU held ms",
                                                          "x real", "CPU 1 thr", "CPU all"))
    for npk in args.windows:
        if args.radios == 2:
            parts, _ = link_scenario(args, 30.0, npk, rng, mod="16qam")
        else:
            parts = many_radios(args, npk, rng)
        path = os.path.join(tmp, "speed.bin")
        write_scenario(path, *parts)
        b = npk * plen
        res, _, _ = run_gpu(path, max(5, min(200, 400000 // b)), 2, args.seed)
        air = b * SYMBOL_SAMPLES / args.fs * 1e3
        cpu_all = [k for k in res if re.fullmatch(r"cpu\d+_rtf", k) and k != "cpu1_rtf"]
        print("%10d %10.2f | %12s %9s | %12.3f %9.2f | %9.3f %9.3f"
              % (b, air, res.get("gpu_agc_window_ms", "-"), res.get("gpu_agc_rtf", "-"), float(res["gpu_held_window_ms"]),
                 float(res["gpu_held_rtf"]), float(res["cpu1_rtf"]), float(res[cpu_all[0]]) if cpu_all else float("nan")))


def many_radios(args, npk, rng):
    """`radios` radios on a 30 m circle, every one transmitting and receiving (FDD), all hearing each other."""
    n = args.radios
    a = argparse.Namespace(**vars(args))
    a.agc = "fast_attack"
    t_sym = SYMBOL_SAMPLES / args.fs
    radios = [an2597_link.make_radio("r%d" % i, a, args.seed + i, float(rng.uniform(-2.0, 2.0))) for i in range(n)]
    recs = [radio_records(r, 1, 1) for r in radios]
    pos = [(30.0 * math.cos(2 * math.pi * i / n), 30.0 * math.sin(2 * math.pi * i / n)) for i in range(n)]
    pairs = np.zeros((n, n), PAIR)
    for i in range(n):
        for j in range(n):
            if i != j:
                pairs[i, j] = pair_record(radios[i], radios[j], math.dist(pos[i], pos[j]), args.ant, t_sym)
    amp = 32768.0 * 10.0 ** (an2597_link.BACKOFF_DB / 20.0)
    plen = args.symbols + 6
    bins = np.zeros((n, npk * plen, NK), complex)
    const = ofdm.constellation("16qam")
    for i in range(n):
        for pk in range(npk):
            pts = const[rng.integers(0, len(const), (args.symbols, 48))]
            rows = [stf_lines(), stf_lines(), ltf_lines(), ltf_lines()] + [data_lines(p) for p in pts]
            bins[i, pk * plen:pk * plen + len(rows)] = np.array(rows) * amp
    return [r[0] for r in recs], [r[1] for r in recs], pairs, [r[2] for r in recs], bins, t_sym


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--lo", type=float, default=2.437e9)
    ap.add_argument("--fs", type=float, default=20e6)
    ap.add_argument("--atten", type=float, default=0.0)
    ap.add_argument("--ant", type=float, default=2.0)
    ap.add_argument("--ppm", type=float, nargs=2, default=(1.0, -1.5))
    ap.add_argument("--distances", type=float, nargs="+", default=[1, 3, 10, 30, 100, 300, 1000])
    ap.add_argument("--packets", type=int, default=10, help="per modulation and distance")
    ap.add_argument("--symbols", type=int, default=20)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--radios", type=int, default=2, help="2: the link; more: timing only, all hearing each other")
    ap.add_argument("--windows", type=int, nargs="+", default=[4, 16, 64, 256, 1024, 4096],
                    help="window sizes for the timing, in packets")
    args = ap.parse_args(argv)
    args.pa, args.lna, args.lna_nf, args.agc = 0.0, 0.0, None, "fast_attack"
    if not os.path.exists(os.path.join(HERE, "ad9361_gpu")):
        raise SystemExit("build ad9361_gpu first (smak, or make, in %s)" % HERE)
    with tempfile.TemporaryDirectory(prefix="an2597_gpu_") as tmp:
        if args.radios == 2:
            cmd_sweep(args, tmp)
        cmd_speed(args, tmp)
    return 0


if __name__ == "__main__":
    sys.exit(main())
