#!/usr/bin/env python3
# Part of stat-sim. PolyForm Noncommercial License 1.0.0; commercial use needs a separate license (see LICENSE, COMMERCIAL.md).
"""
ofdm.py -- a software OFDM modem with the 802.11a/g numerology, for driving a radio model.

64-point FFT, 52 used subcarriers (48 data, 4 pilots at -21, -7, 7, 21), 16-sample cyclic
prefix; a packet is the short training field (10 x 16 samples), the long training field
(32-sample guard, 2 x 64 samples) and the data symbols.  The channel width follows the sample
rate: 20 MSPS gives the 20 MHz channel (312.5 kHz spacing, 4 us symbols), 10 and 5 MSPS the
half and quarter channels.

Not 802.11: there is no SIGNAL field, scrambler, coding or interleaving, and the pilots keep
one polarity.  Bits go straight to BPSK / QPSK / 16-QAM / 64-QAM (Gray), so what comes out is
EVM and uncoded bit errors.  It stands in for the HDL modem of AN-2597 (which is 802.11n-like,
with an HT-mixed preamble, convolutional coding and STBC) where only the radio is under test.
"""
import math

import numpy as np

N_FFT = 64
N_CP = 16
PILOTS = np.array([-21, -7, 7, 21])
PILOT_VALUES = np.array([1.0, 1.0, 1.0, -1.0])
USED = np.array([k for k in range(-26, 27) if k != 0])
DATA = np.array([k for k in USED if k not in PILOTS])
BITS = {"bpsk": 1, "qpsk": 2, "16qam": 4, "64qam": 6}

# long training symbol, subcarriers -26 .. 26
_LTF = np.array([1, 1, -1, -1, 1, 1, -1, 1, -1, 1, 1, 1, 1, 1, 1, -1, -1, 1, 1, -1, 1, -1, 1, 1, 1, 1, 0,
                 1, -1, -1, 1, 1, -1, 1, -1, 1, -1, -1, -1, -1, -1, 1, 1, -1, -1, 1, -1, 1, -1, 1, 1, 1, 1], float)
# short training symbol: every fourth subcarrier, sqrt(13/6) (+-1 +-j)
_STF_SIGN = {-24: 1, -20: -1, -16: 1, -12: -1, -8: -1, -4: 1, 4: -1, 8: -1, 12: 1, 16: 1, 20: 1, 24: 1}


def _to_time(spec_by_k):
    """Subcarrier values {k: X} -> one 64-sample symbol with unit mean power for unit-power carriers."""
    x = np.zeros(N_FFT, complex)
    for k, v in spec_by_k.items():
        x[k % N_FFT] = v
    return np.fft.ifft(x) * N_FFT / math.sqrt(len(USED))


def _pam(bits_per_axis):
    """Gray-coded amplitude levels for one axis: index (bits as an integer, MSB first) -> level."""
    n = 1 << bits_per_axis
    lv = np.zeros(n)
    for i in range(n):
        g = i ^ (i >> 1)                     # position i along the axis carries Gray code g
        lv[g] = 2 * i - (n - 1)
    return lv


def constellation(mod):
    """Points indexed by the symbol's bits (MSB first; first half of the bits on I), unit mean power."""
    nb = BITS[mod]
    if mod == "bpsk":
        return np.array([-1.0, 1.0], complex)
    half = nb // 2
    lv = _pam(half)
    idx = np.arange(1 << nb)
    pts = lv[idx >> half] + 1j * lv[idx & ((1 << half) - 1)]
    return pts / math.sqrt(np.mean(np.abs(pts) ** 2))


def stf():
    s = _to_time({k: math.sqrt(13.0 / 6.0) * sgn * (1 + 1j) for k, sgn in _STF_SIGN.items()})
    return np.tile(s[:16], 10)


def ltf():
    s = _to_time({k: _LTF[k + 26] for k in USED})
    return np.concatenate([s[-32:], s, s])


def modulate(bits, mod):
    """Bits (0/1 array, a multiple of 48 x bits-per-symbol) -> (packet samples, data symbols sent).
    The packet has unit mean power in every field."""
    nb = BITS[mod]
    bits = np.asarray(bits, int)
    nsym = len(bits) // (len(DATA) * nb)
    if nsym * len(DATA) * nb != len(bits) or nsym == 0:
        raise ValueError("need a whole number of OFDM symbols: %d bits each for %s" % (len(DATA) * nb, mod))
    idx = bits.reshape(-1, nb) @ (1 << np.arange(nb - 1, -1, -1))
    syms = constellation(mod)[idx].reshape(nsym, len(DATA))
    out = [stf(), ltf()]
    for s in syms:
        spec = dict(zip(DATA, s))
        spec.update(zip(PILOTS, PILOT_VALUES))
        t = _to_time(spec)
        out.append(np.concatenate([t[-N_CP:], t]))
    return np.concatenate(out), syms


def packet_length(nsym):
    return 320 + nsym * (N_FFT + N_CP)


def detect(r, start=0, threshold=0.6, window=48):
    """Index near the start of the next packet at or after `start`, or None.  Normalised
    autocorrelation at lag 16 (the short training field repeats every 16 samples) with little
    correlation at lag 8; the packet is taken to begin where that first holds for `window` samples."""
    r = np.asarray(r)[start:]
    if len(r) < 16 + 2 * window:
        return None
    prod = r[:-16] * np.conj(r[16:])
    pw = np.abs(r[16:]) ** 2
    c = np.concatenate([[0], np.cumsum(prod)])
    p = np.concatenate([[0], np.cumsum(pw)])
    corr = np.abs(c[window:] - c[:-window])
    powr = p[window:] - p[:-window]
    # a carrier (the other radio's LO leakage, any narrow-band signal) repeats at every lag; the
    # short training field has no correlation at half its period, so require that as well
    prod8 = r[:-16] * np.conj(r[8:-8])
    c8 = np.concatenate([[0], np.cumsum(prod8)])
    corr8 = np.abs(c8[window:] - c8[:-window])
    over = (corr > threshold * np.maximum(powr, 1e-30)) & (corr8 < 0.5 * corr)
    run = np.concatenate([[0], np.cumsum(over)])
    full = np.nonzero(run[window:] - run[:-window] == window)[0]
    return None if len(full) == 0 else start + int(full[0])


def demodulate(r, at, nsym, mod, fs, sent=None, backoff=4):
    """Demodulate the packet detected near index `at` in r.

    Returns a dict: 'start' (index of the first sample of the long training guard), 'cfo' (Hz),
    'syms' (equalised data symbols, nsym x 48), 'bits', and with `sent` (the symbols modulate()
    returned) 'evm_db' and 'bit_errors'.  None if the packet does not fit in r."""
    r = np.asarray(r)
    # coarse CFO from the short training field (unambiguous to fs / 32)
    seg = r[at + 16:at + 16 + 96]
    if len(seg) < 96:
        return None
    cfo = -np.angle(np.sum(seg[:-16] * np.conj(seg[16:]))) * fs / (2.0 * math.pi * 16.0)
    # fine timing: the long training symbol, searched after the detection point
    lt = ltf()[32:96]
    lo, hi = at + 64, at + 400
    if hi + 64 > len(r):
        return None
    w = r[lo:hi + 64] * np.exp(-2j * np.pi * cfo * np.arange(hi + 64 - lo) / fs)
    xc = np.abs(np.correlate(w, lt, mode="valid"))
    pair = xc[:-64] + xc[64:]                       # the two long symbols are 64 samples apart
    first = lo + int(np.argmax(pair))               # start of the first long symbol
    start = first - 32
    end = first + 128 + nsym * (N_FFT + N_CP)
    if start < 0 or end > len(r):
        return None
    n = np.arange(start, end)
    x = r[start:end] * np.exp(-2j * np.pi * cfo * (n - start) / fs)
    # fine CFO from the two long symbols
    l1, l2 = x[32:96], x[96:160]
    fine = -np.angle(np.sum(l1 * np.conj(l2))) * fs / (2.0 * math.pi * 64.0)
    x = x * np.exp(-2j * np.pi * fine * (n - start) / fs)
    cfo += fine
    # channel estimate; every FFT window starts `backoff` samples early, inside its guard
    f1 = np.fft.fft(x[32 - backoff:96 - backoff])
    f2 = np.fft.fft(x[96 - backoff:160 - backoff])
    h = (f1[USED % N_FFT] + f2[USED % N_FFT]) / 2.0 / _LTF[USED + 26]
    hmap = dict(zip(USED, h))
    hd = np.array([hmap[k] for k in DATA])
    hp = np.array([hmap[k] for k in PILOTS])
    syms = np.zeros((nsym, len(DATA)), complex)
    for i in range(nsym):
        s0 = 160 + i * (N_FFT + N_CP) + N_CP - backoff
        f = np.fft.fft(x[s0:s0 + N_FFT])
        yp = f[PILOTS % N_FFT]
        ph = np.angle(np.sum(yp * np.conj(hp * PILOT_VALUES)))        # common phase of this symbol
        syms[i] = f[DATA % N_FFT] / hd * np.exp(-1j * ph)
    nb = BITS[mod]
    pts = constellation(mod)
    idx = np.argmin(np.abs(syms.reshape(-1, 1) - pts.reshape(1, -1)), axis=1)
    bits = ((idx.reshape(-1, 1) >> np.arange(nb - 1, -1, -1)) & 1).reshape(-1)
    out = dict(start=start, cfo=cfo, syms=syms, bits=bits)
    if sent is not None:
        err = np.mean(np.abs(syms - sent) ** 2) / np.mean(np.abs(sent) ** 2)
        out["evm_db"] = 10.0 * math.log10(max(err, 1e-30))
        sent_idx = np.argmin(np.abs(np.asarray(sent).reshape(-1, 1) - pts.reshape(1, -1)), axis=1)
        sent_bits = ((sent_idx.reshape(-1, 1) >> np.arange(nb - 1, -1, -1)) & 1).reshape(-1)
        out["bit_errors"] = int(np.sum(bits != sent_bits))
    return out


def selftest():
    """Loop the modem back on itself: exact without a channel, and through delay, CFO and noise."""
    rng = np.random.default_rng(1)
    fs = 20e6
    ok = True
    for mod in BITS:
        bits = rng.integers(0, 2, 10 * 48 * BITS[mod])
        pkt, sent = modulate(bits, mod)
        power = np.mean(np.abs(pkt) ** 2)
        r = np.concatenate([np.zeros(200, complex), pkt, np.zeros(200, complex)])
        d = demodulate(r, detect(r), 10, mod, fs, sent)
        clean = d["evm_db"]
        # 30 dB SNR over the sampled band, 40 kHz offset, a two-tap channel
        ch = np.convolve(r, [1.0, 0.0, 0.3j])[:len(r)]
        ch = ch * np.exp(2j * np.pi * 40e3 * np.arange(len(r)) / fs)
        ch = ch + (rng.standard_normal(len(r)) + 1j * rng.standard_normal(len(r))) * math.sqrt(power * 1e-3 / 2.0)
        at = detect(ch)
        d2 = demodulate(ch, at, 10, mod, fs, sent)
        print("%-6s power %.3f  clean: EVM %7.1f dB, %d bit errors;  channel: detect %d (packet at 200), CFO %.1f kHz, "
              "EVM %.1f dB, %d bit errors" % (mod, power, clean, d["bit_errors"], at, d2["cfo"] / 1e3, d2["evm_db"],
                                               d2["bit_errors"]))
        ok = ok and clean < -100.0 and d["bit_errors"] == 0 and abs(d2["cfo"] - 40e3) < 2e3 and d2["evm_db"] < -24.0
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(selftest())
