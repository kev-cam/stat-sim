#!/usr/bin/env python3
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# SPDX-FileCopyrightText: 2026 D. Kevin Cameron
# Part of stat-sim. PolyForm Noncommercial License 1.0.0; commercial use needs a separate license (see LICENSE, COMMERCIAL.md).
"""
cc2652r.py -- behavioural model of the Texas Instruments CC2652R 2.4 GHz radio in its Bluetooth LE modes.

Unlike a transceiver with a sample port (ad9361/), this chip's software never sees a sample: it hands
the radio a packet and is handed packets back.  So the model is the radio from the antenna pin to the
bits: on transmit, symbols to a GFSK complex envelope at the set power; on receive, the envelope at
the pin through noise, the front end's third-order limit, the AGC, the channel filter and the
demodulator to packets with their CRC result and RSSI.  The Bluetooth side (modulation, packet
formats, whitening, CRC, the Coded PHY) is ble_phy.py, from the Bluetooth Core Specification; the
link layer and the host's commands are ble_host.py.

Signal convention (the one of ad9361.py and nvc's rf.rf_signal_pkg): an RF signal is its complex
envelope around a centre frequency, in sqrt(W).

Numbers.  RX and TX hold the data sheet's typical values (SWRS207J, sections 8.10 and 8.11, read off
the PDF on 2026-11-24).  MODEL holds what the data sheet does not give and this model assumes.  FIT
(cc2652r_fit.py, written by `cc2652r.py fit`) holds what was adjusted until the model, measured the
way the data sheet measures the chip, gives the data sheet's figures: a noise figure per PHY, the
channel filter's rejection at each offset, the input intercept.  `cc2652r.py check` measures and
prints model against data sheet; `cc2652r.py spec` prints the tables.
"""
import argparse
import math
import os
import pprint
import sys
from multiprocessing import Pool

import numpy as np
from scipy import signal

import ble_phy as ble

K_BOLTZ = 1.380649e-23
T0 = 290.0

# ---------------------------------------------------------------------------------------------
# Data sheet, 8.10 Bluetooth Low Energy - Receive: typical, 25 C, 3.0 V, 2440 MHz, BER 1e-3.
# sel: offset of a modulated interferer in MHz -> I/C in dB it is received through, the wanted signal
# at `wanted` dBm.  The image is at -2 MHz (the table's "image frequency" rows are those entries; where
# the image rows and the +-N MHz rows give two values for one offset the +-N MHz row is used: -3 MHz is
# 40 there and 41 in the image row for LE 1M, -4 MHz is 34 and 36 for LE 2M).
# ---------------------------------------------------------------------------------------------
RX = {
    "s8": dict(name="125 kbps (LE Coded)", sens=-105.0, wanted=-79.0, co=-1.5,
               sel={1: 8.0, -1: 4.5, 2: 44.0, -2: 37.0, 3: 46.0, -3: 44.0, 4: 44.0, -4: 46.0,
                    6: 48.0, -6: 44.0, 7: 51.0, -7: 45.0}),
    "s2": dict(name="500 kbps (LE Coded)", sens=-100.0, wanted=-72.0, co=-3.5,
               sel={1: 8.0, -1: 4.0, 2: 43.0, -2: 35.0, 3: 46.0, -3: 46.0, 4: 45.0, -4: 47.0,
                    6: 46.0, -6: 45.0, 7: 49.0, -7: 45.0}),
    "1m": dict(name="1 Mbps (LE 1M)", sens=-97.0, wanted=-67.0, co=-6.0,
               sel={1: 7.0, -1: 4.0, 2: 39.0, -2: 33.0, 3: 36.0, -3: 40.0, 4: 36.0, -4: 45.0, 5: 40.0, -5: 40.0},
               intermod=(-42.0, 3e6, 6e6),          # level; a tone and a modulated signal at these offsets, wanted -64 dBm
               blocking=((30e6, 2000e6, -10.0), (2003e6, 2399e6, -18.0), (2484e6, 2997e6, -12.0),
                         (3000e6, 12.75e9, -2.0))),
    "2m": dict(name="2 Mbps (LE 2M)", sens=-91.0, wanted=-67.0, co=-7.0,
               sel={2: 8.0, -2: 4.0, 4: 36.0, -4: 34.0, 6: 37.0, -6: 36.0},
               intermod=(-38.0, 6e6, 12e6),
               blocking=((30e6, 2000e6, -16.0), (2003e6, 2399e6, -21.0), (2484e6, 2997e6, -15.0),
                         (3000e6, 12.75e9, -12.0))),
}
SCALARS = {
    # name: (value, unit, what it is); all read from SWRS207J
    "f_min": (2360e6, "Hz", "8.9 RF frequency band"),
    "f_max": (2500e6, "Hz", "8.9 RF frequency band"),
    "tx_pmax": (5.0, "dBm", "8.11 maximum output power, into 50 ohm through a balun"),
    "tx_range": (26.0, "dB", "8.11 output power programmable range"),
    "rx_saturation": (5.0, "dBm", "8.10 receiver saturation, given as '> 5' for every PHY"),
    "rssi_range": (70.0, "dB", "8.10 RSSI dynamic range"),
    "rssi_accuracy": (4.0, "dB", "8.10 RSSI accuracy (+/-)"),
    "intermod_wanted": (-64.0, "dBm", "8.10 wanted signal of the intermodulation test"),
    "i_rx": (6.9e-3, "A", "8.6 radio receive current (not used by the model)"),
    "i_tx_0dbm": (7.0e-3, "A", "8.6 radio transmit current at 0 dBm (not used)"),
    "i_tx_5dbm": (9.2e-3, "A", "8.6 radio transmit current at +5 dBm (not used)"),
}

# ---------------------------------------------------------------------------------------------
# What the data sheet does not give: this model's assumptions (CC2652R(name, **overrides)).
# ---------------------------------------------------------------------------------------------
MODEL = {
    "mod_index": 0.5, "bt": 0.5,            # the specification's nominal GFSK
    "tx_power_step": 1.0,                   # dB; settings are taken to be every 1 dB over the 26 dB range
    # Channel filter: flat to +-passband (as a multiple of the symbol rate), then the rejection FIT
    # holds at each offset, straight lines in dB between them; an FIR of fir_symbols symbol periods
    # of LE 1M (half that for LE 2M) carries it at the sample rate.
    "passband": 0.5, "fir_symbols": 10.0, "fir_kaiser_beta": 9.0,
    # AGC: front-end gain comes down dB for dB once the power at the pin (all of the sampled band)
    # is over the threshold, and the input intercept goes up by as much.
    "agc_threshold": -35.0, "agc_range": 45.0,
    # What follows the gain (the ADC) has this much range under the power at the pin.
    "dynamic_range": 65.0,
    # Packet search: correlation of the discriminator's output with preamble and access address
    # against the value a clean signal gives, and the errors allowed in the hard decisions of both.
    "sync_threshold": 0.6, "sync_errors": 2, "sync_threshold_coded": 0.5,
    "rssi_floor": -105.0,                   # RSSI reads no lower; 70 dB of range above it
}

# starting point of `fit`, and what is used when cc2652r_fit.py is not there
FIT_DEFAULT = {phy: {"nf": 6.0, "iip3": -28.0, "det": 0.5, "rej": {o: v + 8.0 for o, v in RX[phy]["sel"].items()}} for phy in RX}
try:
    from cc2652r_fit import FIT
except ImportError:
    FIT = FIT_DEFAULT


def dbm_to_w(dbm):
    return 1e-3 * 10.0 ** (dbm / 10.0)


def w_to_dbm(w):
    return 10.0 * math.log10(max(w, 1e-300) / 1e-3)


def soft_compress(x, ip3_w):
    """Memoryless third-order compression of an envelope, as in ad9361.py: y = x / sqrt(1 + 2 |x|^2 / IP3)."""
    return x / np.sqrt(1.0 + 2.0 * (x.real ** 2 + x.imag ** 2) / ip3_w)


def blocking_level(phy, f):
    """Data sheet out-of-band blocking level (dBm) for a signal at f Hz, None inside 2400 - 2483.5 MHz."""
    for lo, hi, level in RX[phy if "blocking" in RX[phy] else "1m"]["blocking"]:
        if lo <= f <= hi:
            return level
    return None


class CC2652R:
    """One CC2652R radio.  frequency (Hz), phy ("1m", "2m", "s2", "s8") and tx_power (dBm) are what its
    software sets; fs is the rate the model's envelopes are sampled at (a multiple of the symbol rate)."""

    def __init__(self, name="cc2652r", seed=0, fs=16e6, fit=None, **overrides):
        unknown = set(overrides) - set(MODEL)
        if unknown:
            raise ValueError("unknown model parameter(s): %s" % ", ".join(sorted(unknown)))
        self.name = name
        self.fs = float(fs)
        self.m = dict(MODEL)
        self.m.update(overrides)
        self.fit = FIT if fit is None else fit
        self.rng = np.random.default_rng(seed)
        self.enable = {"noise": True, "nonlinear": True, "agc": True, "filter": True}
        self.frequency = 2440e6
        self.phy = "1m"
        self.tx_power = 0.0
        self.xo_ppm = 0.0                    # crystal error: moves the carrier (not the symbol clock)
        self.gain_reduction = 0.0            # status: what the AGC took off for the last receive
        self._tx_phase = 0.0
        self._n_rx = 0
        self._cache = {}

    # ---- controls ---------------------------------------------------------------------------
    @property
    def sps(self):
        s = self.fs / ble.PHYS[self.phy][0]
        if abs(s - round(s)) > 1e-9 or s < 4:
            raise ValueError("%g samples per symbol" % s)
        return int(round(s))

    @property
    def carrier(self):
        return self.frequency * (1.0 + self.xo_ppm * 1e-6)

    def tx_power_legal(self, dbm):
        hi = SCALARS["tx_pmax"][0]
        step = self.m["tx_power_step"]
        return min(max(round(dbm / step) * step, hi - SCALARS["tx_range"][0]), hi)

    # ---- transmit ---------------------------------------------------------------------------
    def transmit(self, symbols):
        """Symbols on the air (0 / 1) -> envelope at the antenna pin, centred on self.carrier."""
        if not SCALARS["f_min"][0] <= self.frequency <= SCALARS["f_max"][0]:
            raise ValueError("%g Hz is outside the radio's band" % self.frequency)
        env, self._tx_phase = ble.gfsk(symbols, self.sps, self.m["mod_index"], self.m["bt"], self._tx_phase)
        return env * math.sqrt(dbm_to_w(self.tx_power_legal(self.tx_power)))

    # ---- receive ----------------------------------------------------------------------------
    def channel_filter(self):
        """Complex FIR taps of the channel filter for the PHY and sample rate in use."""
        key = ("fir", self.phy, self.fs)
        if key not in self._cache:
            rate = ble.PHYS[self.phy][0]
            unit = 2e6 if self.phy == "2m" else 1e6           # offsets of the table are multiples of this
            rej = self.fit[self.phy]["rej"]
            pb = self.m["passband"] * rate
            offs = sorted(rej)
            xs = [o * 1e6 for o in offs if o < 0] + [-pb, pb] + [o * 1e6 for o in offs if o > 0]
            ys = [rej[o] for o in offs if o < 0] + [0.0, 0.0] + [rej[o] for o in offs if o > 0]
            ntaps = int(round(self.m["fir_symbols"] * 1e-6 * self.fs * 1e6 / unit)) | 1
            nfft = 8192
            f = np.fft.fftfreq(nfft, 1.0 / self.fs)
            h = np.fft.fftshift(np.fft.ifft(10.0 ** (-np.interp(f, xs, ys) / 20.0)))
            mid = nfft // 2
            taps = h[mid - ntaps // 2: mid + ntaps // 2 + 1] * np.kaiser(ntaps, self.m["fir_kaiser_beta"])
            self._cache[key] = taps / abs(taps.sum())
        return self._cache[key]

    def front_end(self, env, f_centre=None, blockers=()):
        """Envelope at the pin (centred on f_centre, default this receiver's carrier) -> the signal after
        the channel filter, referred to the pin (sqrt(W)), delayed by the filter.  blockers: (Hz, dBm) of
        signals outside the sampled band, which only raise the noise (the data sheet's blocking levels)."""
        env = np.asarray(env, complex)
        n = len(env)
        x = env
        df = (self.carrier if f_centre is None else f_centre) - self.carrier
        if df != 0.0:
            x = x * np.exp(2j * math.pi * df * ((self._n_rx + np.arange(n)) / self.fs))
        self._n_rx += n
        fit = self.fit[self.phy]
        pw = float(np.mean(x.real ** 2 + x.imag ** 2)) if n else 0.0
        self.gain_reduction = 0.0
        if self.enable["agc"] and pw > 0.0:
            self.gain_reduction = min(max(w_to_dbm(pw) - self.m["agc_threshold"], 0.0), self.m["agc_range"])
        if self.enable["noise"]:
            density = K_BOLTZ * T0 * 10.0 ** (fit["nf"] / 10.0)
            noise = density * self.fs + pw / 10.0 ** (self.m["dynamic_range"] / 10.0)
            for f, dbm in blockers:
                level = blocking_level(self.phy, f)
                if level is not None:      # at the data sheet's level it uses up the wanted signal's margin
                    noise += density * self.fs * 10.0 ** ((RX[self.phy]["wanted"] - RX[self.phy]["sens"] + dbm - level) / 10.0)
            s = math.sqrt(noise / 2.0)
            x = x + (self.rng.standard_normal(n) + 1j * self.rng.standard_normal(n)) * s
        if self.enable["nonlinear"]:
            x = soft_compress(x, dbm_to_w(fit["iip3"] + self.gain_reduction))
        if self.enable["filter"]:
            x = signal.oaconvolve(x, self.channel_filter())[:n]
        return x

    @property
    def filter_delay(self):
        return (len(self.channel_filter()) - 1) // 2 if self.enable["filter"] else 0

    def symbol_offset(self):
        """Sample at which the discriminator's output is taken for symbol 0 of a transmission that
        starts at sample 0: found once per PHY and rate from a clean signal."""
        key = ("t0", self.phy, self.fs, self.enable["filter"])
        if key not in self._cache:
            sps = self.sps
            bits = np.random.default_rng(7).integers(0, 2, 600)
            keep = dict(self.enable)
            self.enable.update(noise=False, nonlinear=False, agc=False)
            n0 = self._n_rx
            soft = ble.discriminate(self.front_end(ble.gfsk(bits, sps, self.m["mod_index"], self.m["bt"])[0]), sps)
            self._n_rx = n0
            self.enable = keep
            best = max(range(self.filter_delay, self.filter_delay + 2 * sps),
                       key=lambda t: float(np.sum((2.0 * bits[:500] - 1.0) * soft[t + sps * np.arange(500)])))
            self._cache[key] = best
            s = soft[best + sps * np.arange(500)]
            self._cache[("amp", self.phy, self.fs)] = float(np.mean(np.abs(s)))
            mm = 2.0 * bits[:501] - 1.0          # what each symbol's neighbours add, for the sequence detector
            a = np.stack([mm[:-2], mm[1:-1], mm[2:]], axis=1)
            self._cache[("isi", self.phy, self.fs)] = np.linalg.lstsq(a, s[1:500], rcond=None)[0]
        return self._cache[key]

    def decide(self, sym):
        """Symbol decisions from discriminator samples taken one per symbol."""
        self.symbol_offset()
        t = self._cache[("isi", self.phy, self.fs)]
        d = self.fit[self.phy].get("det", 1.0)   # how much of the neighbours' part the detector allows for
        return ble.sequence_detect_stream(sym, (d * t[0], t[1], d * t[2]))

    def rssi(self, y):
        """RSSI of a span of the filtered signal: dBm in 1 dB steps over the data sheet's 70 dB range."""
        p = w_to_dbm(float(np.mean(y.real ** 2 + y.imag ** 2))) if len(y) else -300.0
        lo = self.m["rssi_floor"]
        return float(min(max(round(p), lo), lo + SCALARS["rssi_range"][0]))

    def _sync_pattern(self, access_address):
        key = ("pat", self.phy, access_address)
        if key not in self._cache:
            if ble.PHYS[self.phy][1] == 1:
                pat = ble.packet_symbols(self.phy, b"\0\0", None, access_address)[:(40 if self.phy == "1m" else 48)]
            else:
                pat = np.concatenate([ble.CODED_PREAMBLE, ble.coded_block1(access_address, 8)[:256]])
            self._cache[key] = pat
        return self._cache[key]

    def receive(self, env, f_centre=None, channel=None, access_address=ble.ADV_ACCESS_ADDRESS,
                crc_init=ble.CRC_INIT_ADV, blockers=()):
        """Envelope at the pin -> the packets found in it: a list of dicts with pdu (octets), crc_ok,
        rssi (dBm), phy and start (sample of the packet's first symbol at the pin).  channel: the
        channel index the packets were whitened with, None for unwhitened (test) packets."""
        y = self.front_end(env, f_centre, blockers)
        sps = self.sps
        t0 = self.symbol_offset()
        amp = self._cache[("amp", self.phy, self.fs)]
        soft = ble.discriminate(y, sps)[t0:]
        pat = self._sync_pattern(access_address)
        coded = ble.PHYS[self.phy][1] != 1
        ln = len(pat)
        m = len(soft) - (ln - 1) * sps
        found = []
        if m <= 0:
            return found
        p0 = 2.0 * pat - 1.0
        p0 = p0 - p0.mean()
        c = np.zeros(m)
        for k in range(ln):
            c += p0[k] * soft[k * sps: k * sps + m]
        ideal = amp * float(np.sum(p0 * (2.0 * pat - 1.0)))
        thr = self.m["sync_threshold_coded" if coded else "sync_threshold"] * ideal
        over = np.flatnonzero(c > thr)
        n = 0
        while True:
            over = over[over >= n]
            if not len(over):
                break
            n0 = int(over[0])
            n0 += int(np.argmax(c[n0: n0 + sps]))
            sym = soft[n0::sps]
            a = c[n0] / float(np.sum(p0 * p0))
            dc = float(np.mean(sym[:ln])) - a * float(np.mean(2.0 * pat - 1.0))
            pkt = (self._packet_coded if coded else self._packet_uncoded)(sym - dc, pat, channel, access_address, crc_init)
            if pkt is None:
                n = n0 + 1
                continue
            nsym = pkt.pop("symbols")
            pkt["start"] = n0
            pkt["rssi"] = self.rssi(y[t0 + n0: t0 + n0 + ln * sps])
            pkt["phy"] = self.phy
            found.append(pkt)
            n = n0 + nsym * sps
        return found

    def _packet_uncoded(self, sym, pat, channel, access_address, crc_init):
        ln = len(pat)
        if len(sym) < ln + 16:
            return None
        got = self.decide(sym[:ln + 16 + 8 * 255 + 24 + 2])
        if int(np.sum(got[:ln] != pat)) > self.m["sync_errors"]:
            return None
        hdr = got[ln: ln + 16]
        if channel is not None:
            hdr = hdr ^ ble.whitening(channel, 16)
        nbits = 16 + 8 * int(ble.octets_of(hdr[8:])[0]) + 24
        if len(got) < ln + nbits:
            return None
        bits = got[ln: ln + nbits]
        if channel is not None:
            bits = bits ^ ble.whitening(channel, nbits)
        ok = bool(np.all(ble.crc24(bits[:-24], crc_init) == bits[-24:]))
        return dict(pdu=ble.octets_of(bits[:-24]), crc_ok=ok, symbols=ln + nbits)

    def _packet_coded(self, sym, pat, channel, access_address, crc_init):
        if len(sym) < 376 + 32 * 8:
            return None
        b1 = ble.viterbi(ble.pattern_llr(sym[80:376], 8))
        want = ble.int_bits(access_address, 32)
        if int(np.sum(b1[:32] != want)) > 0 or b1[33]:
            return None
        s = 2 if b1[32] else 8
        hdr = ble.viterbi(ble.pattern_llr(sym[376: 376 + 32 * s], s), terminated=False)[:16]
        if channel is not None:
            hdr = hdr ^ ble.whitening(channel, 16)
        nbits = 16 + 8 * int(ble.octets_of(hdr[8:])[0]) + 24
        if len(sym) < 376 + (nbits + 3) * s:
            return None
        bits = ble.viterbi(ble.pattern_llr(sym[376: 376 + (nbits + 3) * s], s))[:nbits]
        if channel is not None:
            bits = bits ^ ble.whitening(channel, nbits)
        ok = bool(np.all(ble.crc24(bits[:-24], crc_init) == bits[-24:]))
        return dict(pdu=ble.octets_of(bits[:-24]), crc_ok=ok, symbols=376 + (nbits + 3) * s, s=s)


# ---------------------------------------------------------------------------------------------
# Measuring the model as the data sheet measures the chip: bit error rate of a wanted signal, with
# interferers, the symbol timing known (no packet search); the level at which it is 1e-3.
# ---------------------------------------------------------------------------------------------
DETUNE = 7.3e3          # Hz


def check_fs(phy):
    return 32e6 if phy == "2m" else 16e6


def ber(phy, wanted_dbm, interferers=(), blockers=(), nbits=200000, seed=1, fit=None):
    """Bit error rate.  interferers: (offset Hz, dBm, "gfsk" | "cw")."""
    r = CC2652R(seed=seed, fs=check_fs(phy), fit=fit)
    r.phy = phy
    rng = np.random.default_rng(seed + 1000)
    rate, s = ble.PHYS[phy]
    sps = r.sps
    if s == 1:
        bits = rng.integers(0, 2, nbits).astype(np.uint8)
        syms = bits
    else:
        rows = max(nbits // 200, 1)
        bits = rng.integers(0, 2, (rows, 200)).astype(np.uint8)
        bits[:, -3:] = 0                    # every row ends the encoder in state 0
        z = np.zeros((rows, 3), np.uint8)
        p = np.concatenate([z, bits], axis=1)
        a0 = p[:, 3:] ^ p[:, 2:-1] ^ p[:, 1:-2] ^ p[:, :-3]
        a1 = p[:, 3:] ^ p[:, 1:-2] ^ p[:, :-3]
        syms = ble.pattern_map(np.stack([a0, a1], axis=-1).reshape(rows, -1), s).ravel()
    x = r.transmit(syms) * math.sqrt(dbm_to_w(wanted_dbm) / dbm_to_w(r.tx_power))
    n = len(x)
    t = np.arange(n) / r.fs
    for off, dbm, kind in interferers:
        if kind == "cw":
            i = np.ones(n, complex)
        else:
            # not locked to the wanted signal: its symbols start anywhere, and it is DETUNE off its
            # nominal offset so that its phase against the wanted signal runs through every value
            k = int(rng.integers(0, sps))
            i = ble.gfsk(rng.integers(0, 2, n // sps + 2), sps)[0][k: k + n]
            off = off + DETUNE
        x = x + i * np.exp(1j * (2.0 * math.pi * off * t + rng.uniform(0.0, 2.0 * math.pi))) * math.sqrt(dbm_to_w(dbm))
    soft = ble.discriminate(r.front_end(x, blockers=blockers), sps)
    t0 = r.symbol_offset()
    nsym = len(syms) - (t0 // sps + 2)
    sym = soft[t0 + sps * np.arange(nsym)]
    if s == 1:
        return float(np.mean(r.decide(sym)[8:-8] != bits[8:nsym - 8]))
    per_row = 400 * (s // 2)
    rows = nsym // per_row
    got = ble.viterbi(ble.pattern_llr(sym[:rows * per_row].reshape(rows, per_row), s))
    return float(np.mean(got[:, :-3] != bits[:rows, :-3]))


def level_at(f, guess, rising, span=16.0, steps=9, target=1e-3):
    """The level (dBm) at which f(level) crosses `target`; rising: BER grows with the level."""
    lo, hi = guess - span, guess + span
    for _ in range(steps):
        mid = 0.5 * (lo + hi)
        if (f(mid) > target) == rising:
            hi = mid
        else:
            lo = mid
    return 0.5 * (lo + hi)


def figures(phy):
    """What the data sheet gives for a PHY, as (key, data sheet value)."""
    d = RX[phy]
    out = [(("sens",), d["sens"]), (("co",), d["co"])]
    out += [(("sel", o), v) for o, v in sorted(d["sel"].items())]
    if "intermod" in d:
        out.append((("intermod",), d["intermod"][0]))
        out += [(("blocking", lo), level) for lo, hi, level in d["blocking"]]
    return out


def measure(job):
    """One figure of one PHY from the model; job = (phy, key, fit, nbits, seed)."""
    phy, key, fit, nbits, seed = job
    d = RX[phy]
    if ble.PHYS[phy][1] != 1:
        nbits = max(nbits // 4, 20000)
    kw = dict(nbits=nbits, seed=seed, fit=fit)
    if key[0] == "sens":
        return level_at(lambda p: ber(phy, p, **kw), d["sens"], False)
    if key[0] == "co":
        return level_at(lambda p: ber(phy, d["wanted"], [(0.0, p, "gfsk")], **kw), d["wanted"] + d["co"], True) - d["wanted"]
    if key[0] == "sel":
        return level_at(lambda p: ber(phy, d["wanted"], [(key[1] * 1e6, p, "gfsk")], **kw),
                        d["wanted"] + d["sel"][key[1]], True, span=24.0, steps=10) - d["wanted"]
    if key[0] == "intermod":
        level, f1, f2 = d["intermod"]
        return level_at(lambda p: ber(phy, SCALARS["intermod_wanted"][0], [(f1, p, "cw"), (f2, p, "gfsk")], **kw), level, True)
    if key[0] == "blocking":
        return level_at(lambda p: ber(phy, d["wanted"], blockers=[(key[1], p)], **kw),
                        blocking_level(phy, key[1]), True)
    raise KeyError(key)


def measure_all(phys, fit, nbits, seed, jobs):
    todo = [(phy, key, fit, nbits, seed) for phy in phys for key, want in figures(phy)]
    with Pool(jobs) as pool:
        got = pool.map(measure, todo, chunksize=1)
    return {(j[0], j[1]): g for j, g in zip(todo, got)}


def cmd_fit(args):
    start = FIT if args.resume else FIT_DEFAULT          # --resume: carry on from cc2652r_fit.py
    fit = {phy: {"nf": v["nf"], "iip3": v["iip3"], "det": v["det"], "rej": dict(v["rej"])} for phy, v in start.items()}
    phys = args.phy or list(RX)
    for it in range(args.iterations):
        got = measure_all(phys, fit, args.bits, 1, args.jobs)
        worst = 0.0
        for phy in phys:
            for key, want in figures(phy):
                d = want - got[(phy, key)]
                if key[0] == "sens":
                    fit[phy]["nf"] += d
                elif key[0] == "sel":
                    fit[phy]["rej"][key[1]] = min(max(fit[phy]["rej"][key[1]] + d, 0.0), 90.0)
                elif key[0] == "intermod":
                    fit[phy]["iip3"] += 1.5 * d
                elif key[0] == "co" and ble.PHYS[phy][1] == 1:
                    fit[phy]["det"] = min(max(fit[phy]["det"] + d / 8.0, 0.0), 1.0)
                if key[0] in ("sens", "sel", "intermod") or (key[0] == "co" and ble.PHYS[phy][1] == 1):
                    worst = max(worst, abs(d))
        print("iteration %d: largest difference fitted on %.2f dB" % (it + 1, worst), flush=True)
    for phy in ("s2", "s8"):                # no intermodulation figure for the Coded PHY: LE 1M's front end
        fit[phy]["iip3"] = fit["1m"]["iip3"]
    for phy in fit:
        fit[phy]["nf"] = round(fit[phy]["nf"], 2)
        fit[phy]["iip3"] = round(fit[phy]["iip3"], 2)
        fit[phy]["det"] = round(fit[phy]["det"], 3)
        fit[phy]["rej"] = {o: round(v, 2) for o, v in sorted(fit[phy]["rej"].items())}
    text = ("# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0\n# SPDX-FileCopyrightText: 2026 D. Kevin Cameron\n"
            "# Part of stat-sim. PolyForm Noncommercial License 1.0.0; commercial use needs a separate license (see LICENSE, COMMERCIAL.md).\n"
            "#\n# Written by `cc2652r.py fit` (%d iterations, %d bits a point): what the model needs to give the\n"
            "# data sheet's figures.  nf: noise figure, dB; iip3: input intercept at full gain, dBm; rej: channel\n"
            "# filter rejection in dB at each offset in MHz; det: how far the uncoded PHYs' sequence detector allows\n"
            "# for neighbouring symbols (0: not at all, 1: fully), which sets the co-channel rejection.\nFIT = " % (args.iterations, args.bits)) + pprint.pformat(fit, width=110) + "\n"
    with open(args.out, "w") as f:
        f.write(text)
    print("wrote", args.out)
    return 0


def cmd_check(args):
    phys = args.phy or list(RX)
    got = measure_all(phys, None, args.bits, args.seed, args.jobs)
    worst = {}
    for phy in phys:
        print("\n%s -- model against the data sheet (typ.), %g MSPS" % (RX[phy]["name"], check_fs(phy) / 1e6))
        print("  %-34s %9s %10s %7s" % ("quantity", "model", "data sheet", "diff"))
        for key, want in figures(phy):
            name = {"sens": "sensitivity, dBm", "co": "co-channel rejection, I/C dB",
                    "intermod": "intermodulation, dBm", "blocking": "blocking from %g MHz, dBm",
                    "sel": "selectivity at %+d MHz, I/C dB"}[key[0]]
            if len(key) > 1:
                name = name % (key[1] / 1e6 if key[0] == "blocking" else key[1])
            d = got[(phy, key)] - want
            worst[key[0]] = max(worst.get(key[0], 0.0), abs(d))
            print("  %-34s %9.1f %10.1f %+7.1f" % (name, got[(phy, key)], want, d))
        b = ber(phy, SCALARS["rx_saturation"][0], nbits=20000, seed=args.seed)
        print("  %-34s %9.1e %10s          BER, wanted signal at +5 dBm ('saturation > 5 dBm')" % ("saturation", b, "< 1e-3"))
    print("\nlargest differences, dB: " + ", ".join("%s %.1f" % kv for kv in worst.items()))
    return 0 if max(worst.values()) < 1.0 else 1


def cmd_spec(args):
    for phy, d in RX.items():
        print("%s: sensitivity %g dBm; with the wanted signal at %g dBm, co-channel %g dB and" % (d["name"], d["sens"], d["wanted"], d["co"]))
        print("    selectivity (MHz: I/C dB) " + ", ".join("%+d: %g" % kv for kv in sorted(d["sel"].items())))
        if "intermod" in d:
            print("    intermodulation %g dBm (offsets %g and %g MHz); blocking " % (d["intermod"][0], d["intermod"][1] / 1e6, d["intermod"][2] / 1e6)
                  + ", ".join("%g-%g MHz: %g dBm" % (lo / 1e6, hi / 1e6, v) for lo, hi, v in d["blocking"]))
    for k, (v, unit, what) in SCALARS.items():
        print("%-16s %-10g %-4s %s" % (k, v, unit, what))
    print("\nmodel assumptions (not from the data sheet):")
    for k, v in MODEL.items():
        print("  %-22s %s" % (k, v))
    print("\nfitted (cc2652r_fit.py):")
    pprint.pprint(FIT, width=110)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, fn, h in (("check", cmd_check, "measure the model and compare with the data sheet"),
                        ("fit", cmd_fit, "adjust noise figure, filter and intercept to the data sheet; writes cc2652r_fit.py")):
        p = sub.add_parser(name, help=h)
        p.add_argument("--phy", action="append", choices=list(RX))
        p.add_argument("--bits", type=int, default=200000)
        p.add_argument("--jobs", type=int, default=os.cpu_count())
        p.add_argument("--seed", type=int, default=5)
        p.add_argument("--iterations", type=int, default=5)
        p.add_argument("--resume", action="store_true")
        p.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "cc2652r_fit.py"))
        p.set_defaults(fn=fn)
    p = sub.add_parser("spec", help="print the data sheet tables, the assumptions and the fit")
    p.set_defaults(fn=cmd_spec)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
