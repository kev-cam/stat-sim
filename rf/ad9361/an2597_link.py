#!/usr/bin/env python3
# Part of stat-sim. PolyForm Noncommercial License 1.0.0; commercial use needs a separate license (see LICENSE, COMMERCIAL.md).
"""
an2597_link.py -- the radio link of Analog Devices AN-2597, with the AD9361s driven from software.

AN-2597 ("An OFDM-Based HDL Reference Modem Using the AD936x RF Transceivers") puts an
802.11n-like OFDM modem in the FPGA of an ADRV9361-Z7035 (AD9361 + Zynq) at each end of a
drone / controller link: 5, 10 or 20 MHz channels in the 2.4 GHz and 5.2 GHz ISM bands, BPSK
to 64-QAM.  Here the HDL modem is replaced by software (ofdm.py: the same numerology, no
coding), which hands samples to and takes samples from two AD9361 models (ad9361.py) through
the calls a program uses on the real chip under Linux (pyadi-iio's names: tx(), rx(), rx_lo,
gain_control_mode_chan0, ...).  The two radios stand in free space (ad9361.Arena).

For each distance the drone sends packets in each modulation to the controller, whose
receiver runs the fast-attack AGC.  Printed per distance: the received power the link budget
gives, the gain the AGC settled at, EVM and uncoded bit error rate per modulation, and the EVM
a noise budget predicts (thermal noise in the used subcarriers and the two radios' EVM floors,
times 1.5 for a channel estimate taken from two training symbols).

    an2597_link.py                       2.437 GHz, 20 MHz channel, bare chips, 2 dBi antennas
    an2597_link.py --lo 5.2e9 --fs 10e6  5.2 GHz band, 10 MHz channel
    an2597_link.py --pa 20 --lna 15 --lna-nf 1.5   external PA and LNA at both ends
    an2597_link.py --speed               simulated samples per second of wall time
"""
import argparse
import csv
import math
import sys
import time

import numpy as np

import ad9361
import ofdm
from ad9361 import AD9361, Arena

MODS = ("bpsk", "qpsk", "16qam", "64qam")
BACKOFF_DB = -12.0          # packet rms against DAC full scale (OFDM peaks are about 10 dB over rms)
GAP = 400                   # idle samples between packets (the fast AGC needs 128 to unlock)


def make_radio(name, args, seed, ppm):
    r = AD9361(name, seed=seed)
    r.rx_lo = r.tx_lo = args.lo
    r.sample_rate = args.fs
    r.rx_rf_bandwidth = r.tx_rf_bandwidth = 0.9 * args.fs
    r.xo_ppm = ppm
    r.gain_control_mode_chan0 = args.agc
    r.tx_hardwaregain_chan0 = -args.atten
    return r


def make_link(args, distance, seed):
    drone = make_radio("drone", args, seed, args.ppm[0])
    ctrl = make_radio("controller", args, seed + 1000, args.ppm[1])
    arena = Arena()
    kw = dict(antenna_gain_dbi=args.ant, pa_gain_db=args.pa, lna_gain_db=args.lna, lna_nf_db=args.lna_nf)
    arena.add(drone, (0.0, 0.0, 0.0), **kw)
    arena.add(ctrl, (distance, 0.0, 0.0), **kw)
    return drone, ctrl, arena


def budget(args, distance):
    """Link budget: (average received power at the chip's RX port in dBm, the EVM in dB that
    thermal noise and the two EVM floors predict)."""
    r = make_radio("b", args, 0, 0.0)
    ptx = r.tx_full_scale_dbm() + BACKOFF_DB + args.pa
    lam = ad9361.C0 / args.lo
    prx_ant = ptx + 2.0 * args.ant + 20.0 * math.log10(lam / (4.0 * math.pi * distance))
    f_chip = 10.0 ** (ad9361.band("rx_nf", args.lo) / 10.0)
    if args.lna:
        g = 10.0 ** (args.lna / 10.0)
        f_sys = 10.0 ** ((args.lna_nf or 0.0) / 10.0) + (f_chip - 1.0) / g
    else:
        f_sys = f_chip
    noise = ad9361.w_to_dbm(ad9361.K_BOLTZ * ad9361.T0 * args.fs * f_sys)
    snr_sc = 10.0 ** ((prx_ant - noise) / 10.0) * ofdm.N_FFT / len(ofdm.USED)
    floors = 10.0 ** (ad9361.band("tx_evm", args.lo) / 10.0) + 10.0 ** (ad9361.band("rx_evm", args.lo) / 10.0)
    return prx_ant + args.lna, 10.0 * math.log10(1.5 * (1.0 / snr_sc + floors))


def send_packets(tx_radio, rx_radio, mod, npkt, nsym, rng, fs):
    """npkt packets from tx_radio to rx_radio.  Returns (detected, evm power ratios, bit errors,
    bits, gains in use during the packets)."""
    scale = 32768.0 * 10.0 ** (BACKOFF_DB / 20.0)
    plen = ofdm.packet_length(nsym)
    detected, evms, errors, nbits, gains = 0, [], 0, 0, []
    for _ in range(npkt):
        bits = rng.integers(0, 2, nsym * len(ofdm.DATA) * ofdm.BITS[mod])
        pkt, sent = ofdm.modulate(bits, mod)
        tx_radio.tx(np.concatenate([np.zeros(GAP), pkt * scale, np.zeros(GAP)]))
        rx_radio.rx_flush()
        rx_radio.rx_buffer_size = plen + 2 * GAP + 200      # filter and flight delay stay inside the tail gap
        base = rx_radio.rx_sample_count                     # RX sample index of r[0]
        r = rx_radio.rx()
        at = ofdm.detect(r)
        d = None if at is None else ofdm.demodulate(r, at, nsym, mod, fs, sent)
        nbits += len(bits)
        if d is None:
            errors += len(bits) // 2                        # a lost packet: half the bits wrong
            continue
        detected += 1
        evms.append(10.0 ** (d["evm_db"] / 10.0))
        errors += d["bit_errors"]
        gains.append(rx_radio.rx_gain_at(base + d["start"] + 160))      # at the first data symbol
        # let the tail gap pass so the AGC unlocks before the next packet
        rx_radio.rx_buffer_size = GAP
        rx_radio.rx()
    return detected, evms, errors, nbits, gains


def cmd_sweep(args):
    rng = np.random.default_rng(args.seed)
    rows = []
    r0 = make_radio("b", args, 0, 0.0)
    print("AN-2597 link, AD9361 at both ends driven from software: LO %.1f MHz, %.0f MHz channel (%.2f MSPS), "
          "rf bandwidth %.1f MHz" % (args.lo / 1e6, args.fs / 1e6, args.fs / 1e6, 0.9 * args.fs / 1e6))
    print("TX attenuation %.2f dB: full-scale tone %.1f dBm, packets %.1f dBm average%s; antennas %.1f dBi; "
          "reference offsets %+.1f / %+.1f ppm (carrier offset %.1f kHz); AGC %s"
          % (args.atten, r0.tx_full_scale_dbm(), r0.tx_full_scale_dbm() + BACKOFF_DB,
             (" + %.0f dB PA, %.0f dB LNA (NF %.1f dB)" % (args.pa, args.lna, args.lna_nf or 0.0)) if args.pa or args.lna else "",
             args.ant, args.ppm[0], args.ppm[1], (args.ppm[0] - args.ppm[1]) * 1e-6 * args.lo / 1e3, args.agc))
    print("RX noise in the sampled band %.1f dBm (NF %.1f dB), full scale at maximum gain %.1f dBm"
          % (r0.rx_noise_floor_dbm(), ad9361.band("rx_nf", args.lo), r0.rx_full_scale_dbm()))
    head = "%8s %8s %6s %7s" % ("dist m", "Prx dBm", "gain", "budget")
    for m in MODS:
        head += " | %5s %6s %8s" % (m, "EVM", "BER")
    print(head)
    for d in args.distances:
        prx, evm_budget = budget(args, d)
        drone, ctrl, arena = make_link(args, d, args.seed)
        drone.ensm_mode, ctrl.ensm_mode = "tx", "rx"         # half duplex: the drone sends, the controller listens
        line = ""
        row = dict(distance_m=d, prx_dbm=round(prx, 2), evm_budget_db=round(evm_budget, 2))
        allgains = []
        for m in MODS:
            det, evms, errors, nbits, gains = send_packets(drone, ctrl, m, args.packets, args.symbols, rng, args.fs)
            allgains += gains
            evm = 10.0 * math.log10(np.mean(evms)) if evms else float("nan")
            ber = errors / nbits
            line += " | %2d/%-2d %6.1f %8.1e" % (det, args.packets, evm, ber)
            row.update({m + "_detected": det, m + "_evm_db": round(evm, 2) if evms else "", m + "_ber": "%.3e" % ber})
        gain = float(np.median(allgains)) if allgains else float("nan")
        row["rx_gain_db"] = gain
        rows.append(row)
        print("%8.0f %8.1f %6.1f %7.1f%s" % (d, prx, gain, evm_budget, line))
    if args.csv:
        with open(args.csv, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print("wrote %s" % args.csv)
    return 0


def cmd_speed(args):
    """Wall-clock cost: both radios transmitting packets back to back, both receiving."""
    drone, ctrl, arena = make_link(args, 100.0, args.seed)
    rng = np.random.default_rng(args.seed)
    bits = rng.integers(0, 2, 20 * len(ofdm.DATA) * 4)
    pkt, _ = ofdm.modulate(bits, "16qam")
    buf = np.concatenate([pkt * 32768.0 * 10.0 ** (BACKOFF_DB / 20.0), np.zeros(GAP)])
    for r in (drone, ctrl):
        r.tx_cyclic_buffer = True
        r.tx(buf)
    for block in (1 << 12, 1 << 16, 1 << 20):
        n = max(1 << 21, block)
        for r in (drone, ctrl):
            r.rx_flush()
        t0 = time.perf_counter()
        done = 0
        while done < n:
            arena.run(block)
            done += block
            for r in (drone, ctrl):
                r.rx_flush()
        dt = time.perf_counter() - t0
        print("block %8d samples: %6.2f M samples/s per radio pair, %.3f x real time at %.0f MSPS (AGC %s)"
              % (block, done / dt / 1e6, done / dt / args.fs, args.fs / 1e6, args.agc))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--lo", type=float, default=2.437e9, help="carrier, Hz (2.412e9 .. 2.462e9 or 5.18e9 .. 5.24e9 in AN-2597)")
    ap.add_argument("--fs", type=float, default=20e6, help="sample rate = channel width: 20e6, 10e6 or 5e6")
    ap.add_argument("--atten", type=float, default=0.0, help="TX attenuation, dB")
    ap.add_argument("--ant", type=float, default=2.0, help="antenna gain at each end, dBi")
    ap.add_argument("--pa", type=float, default=0.0, help="external PA gain at each end, dB (ideal)")
    ap.add_argument("--lna", type=float, default=0.0, help="external LNA gain at each end, dB")
    ap.add_argument("--lna-nf", type=float, default=None, help="external LNA noise figure, dB")
    ap.add_argument("--ppm", type=float, nargs=2, default=(1.0, -1.5), help="reference clock error of drone and controller")
    ap.add_argument("--agc", default="fast_attack", choices=("fast_attack", "slow_attack", "manual"))
    ap.add_argument("--distances", type=float, nargs="+", default=[1, 3, 10, 30, 100, 300, 1000, 3000])
    ap.add_argument("--packets", type=int, default=10)
    ap.add_argument("--symbols", type=int, default=20, help="OFDM data symbols per packet")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--csv", default="")
    ap.add_argument("--speed", action="store_true", help="measure simulation speed instead")
    args = ap.parse_args(argv)
    return cmd_speed(args) if args.speed else cmd_sweep(args)


if __name__ == "__main__":
    sys.exit(main())
