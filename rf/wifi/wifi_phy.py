#!/usr/bin/env python3
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# SPDX-FileCopyrightText: 2026 D. Kevin Cameron
# Part of stat-sim. PolyForm Noncommercial License 1.0.0; commercial use needs a separate license (see LICENSE, COMMERCIAL.md).
"""
wifi_phy.py -- the IEEE 802.11 OFDM physical layer ("802.11a"; in the 2.4 GHz band "802.11g", ERP-OFDM).

A transmitter and a receiver for the 20 MHz non-HT PPDU, 6 to 54 Mb/s: preamble (short and long
training), SIGNAL, and the DATA field with its scrambler, convolutional code, puncturing,
interleaver, constellation mapping and pilots.  Bit for bit what the standard specifies, so that a
frame made here decodes in a conformant receiver and a conformant transmitter's frame decodes here.
Nothing in it belongs to one chip: it is the Wi-Fi counterpart of ../cc2652r/ble_phy.py.

  encode(psdu, rate)         -> Ppdu: the OFDM symbols on their subcarriers, and the 20 MS/s samples
  decode(samples)            -> Reception: rate, length, the PSDU, EVM, what the synchroniser found
  python3 wifi_phy.py check  -> the self-checks (loop-back at every rate through a channel; the
                                standard's own worked example where its numbers are to hand)

Where it comes from (IEEE Std 802.11-2020 clause 17, first published as 802.11a-1999; status marks
as in ../cc2652r/cc2652r.py):
  "rec"  written from recollection of the standard: the rate table and RATE codes, the SIGNAL
         layout, the scrambler x^7 + x^4 + 1, the code (133, 171 octal) and its puncturing, both
         interleaver permutations, the four constellations, the pilot values and their polarity
         sequence (the scrambler's output from the all-ones state), the subcarrier allocation and
         the two training sequences.
  `check` holds each of them against what can be checked without the text (see check()).

Conventions.  Bits are in transmission order, the LSB of an octet first.  A subcarrier is numbered
-32 .. 31 with 0 the carrier; an OFDM symbol in the frequency domain is a numpy array of 64 complex
values in FFT order (subcarrier k at index k mod 64).  Samples are complex, 20 MS/s for the 20 MHz
channel, scaled so that a symbol's 52 used subcarriers at unit mean power give unit mean power.
"""
import math
import sys

import numpy as np

N_FFT = 64
N_CP = 16
N_SYM = N_FFT + N_CP                     # samples in a symbol period
FS = 20e6                                # sample rate of the 20 MHz channel
PILOT_K = (-21, -7, 7, 21)
PILOT_V = (1.0, 1.0, 1.0, -1.0)
DATA_K = tuple(k for k in range(-26, 27) if k != 0 and k not in PILOT_K)   # logical data carrier 0 .. 47
USED_K = tuple(k for k in range(-26, 27) if k != 0)
SCALE = 1.0 / math.sqrt(52.0)            # frequency-domain unit carriers -> unit mean power in time
BACKOFF = 3                              # samples by which the receiver's transform windows start early

# rate (Mb/s) -> modulation, coding rate (n, d), bits per carrier, coded and data bits per symbol, RATE bits R1 .. R4
RATES = {
    6:  ("bpsk",  (1, 2), 1, 48,  24,  (1, 1, 0, 1)),
    9:  ("bpsk",  (3, 4), 1, 48,  36,  (1, 1, 1, 1)),
    12: ("qpsk",  (1, 2), 2, 96,  48,  (0, 1, 0, 1)),
    18: ("qpsk",  (3, 4), 2, 96,  72,  (0, 1, 1, 1)),
    24: ("16qam", (1, 2), 4, 192, 96,  (1, 0, 0, 1)),
    36: ("16qam", (3, 4), 4, 192, 144, (1, 0, 1, 1)),
    48: ("64qam", (2, 3), 6, 288, 192, (0, 0, 0, 1)),
    54: ("64qam", (3, 4), 6, 288, 216, (0, 0, 1, 1)),
}
RATE_OF_BITS = {v[5]: k for k, v in RATES.items()}

# long training symbol on subcarriers -26 .. 26
_LTF = (1, 1, -1, -1, 1, 1, -1, 1, -1, 1, 1, 1, 1, 1, 1, -1, -1, 1, 1, -1, 1, -1, 1, 1, 1, 1, 0,
        1, -1, -1, 1, 1, -1, 1, -1, 1, -1, -1, -1, -1, -1, 1, 1, -1, -1, 1, -1, 1, -1, 1, 1, 1, 1)
# short training symbol: sqrt(13/6) (1 + j) times these signs on every fourth subcarrier
_STF = {-24: 1, -20: -1, -16: 1, -12: -1, -8: -1, -4: 1, 4: -1, 8: -1, 12: 1, 16: 1, 20: 1, 24: 1}


def _freq(values_by_k):
    """{subcarrier: value} -> the 64 values in FFT order."""
    x = np.zeros(N_FFT, complex)
    for k, v in values_by_k.items():
        x[k % N_FFT] = v
    return x


LTF_FREQ = _freq({k: float(v) for k, v in zip(range(-26, 27), _LTF)})
STF_FREQ = _freq({k: math.sqrt(13.0 / 6.0) * s * (1 + 1j) for k, s in _STF.items()})


def to_time(freq):
    """64 frequency-domain values (FFT order) -> the 64 samples of the symbol body."""
    return np.fft.ifft(freq) * N_FFT * SCALE


def to_freq(body):
    """The 64 samples of a symbol body -> its frequency-domain values (FFT order)."""
    return np.fft.fft(body) / (N_FFT * SCALE)


# ---------------------------------------------------------------------------------------------- bits
def bits_of(octets):
    """Octets -> bits in transmission order (LSB of each octet first)."""
    return np.unpackbits(np.frombuffer(bytes(octets), np.uint8), bitorder="little").astype(np.uint8)


def octets_of(bits):
    bits = np.asarray(bits, np.uint8)
    return np.packbits(bits[:len(bits) // 8 * 8], bitorder="little").tobytes()


def scrambler(state, n):
    """n bits of the scrambling sequence, generator x^7 + x^4 + 1.  `state` is the register's seven bits
    x1 .. x7 (the standard's figure), as a string or a sequence: "1011101" is its example.  Each bit put
    out is x7 xor x4, and becomes the new x1."""
    x = [int(c) for c in state]          # x[0] = x1 .. x[6] = x7
    assert len(x) == 7 and any(x), "the scrambler state is seven bits, not all zero"
    out = np.empty(n, np.uint8)
    for i in range(n):
        b = x[6] ^ x[3]                  # x7 xor x4
        out[i] = b
        x = [b] + x[:6]
    return out


def scrambler_state_after(first7):
    """The state the scrambler is in once it has put out these seven bits (the receiver has them as the
    first seven bits of SERVICE, which are sent as zeros): the state to carry on from."""
    return [int(b) for b in reversed(list(first7))]      # x1 is the newest


PILOT_POLARITY = 1.0 - 2.0 * scrambler("1111111", 127)   # p_0 .. p_126


def conv_encode(bits):
    """Rate 1/2, constraint length 7, g0 = 133, g1 = 171 (octal); output A0 B0 A1 B1 ..., encoder
    starting from the all-zero state."""
    d = np.concatenate((np.zeros(6, np.uint8), np.asarray(bits, np.uint8)))
    n = len(bits)
    a = d[6:6 + n] ^ d[4:4 + n] ^ d[3:3 + n] ^ d[1:1 + n] ^ d[0:n]
    b = d[6:6 + n] ^ d[5:5 + n] ^ d[4:4 + n] ^ d[3:3 + n] ^ d[0:n]
    out = np.empty(2 * n, np.uint8)
    out[0::2] = a
    out[1::2] = b
    return out


# which of the mother code's bits are sent, per puncturing period (A0 B0 A1 B1 ...)
_PUNCTURE = {(1, 2): (1, 1), (2, 3): (1, 1, 1, 0), (3, 4): (1, 1, 1, 0, 0, 1)}


def puncture(coded, rate):
    keep = np.resize(np.array(_PUNCTURE[rate], bool), len(coded))
    return coded[keep]


def depuncture(soft, rate):
    """Soft values of the sent bits -> soft values of the mother code, 0 where a bit was not sent."""
    pat = np.array(_PUNCTURE[rate], bool)
    n = len(soft) * len(pat) // int(pat.sum())
    out = np.zeros(n)
    out[np.resize(pat, n)] = soft
    return out


def interleaver(n_cbps, n_bpsc):
    """The index j each coded bit k of a symbol is sent at (both permutations)."""
    s = max(n_bpsc // 2, 1)
    k = np.arange(n_cbps)
    i = (n_cbps // 16) * (k % 16) + k // 16
    return s * (i // s) + (i + n_cbps - (16 * i) // n_cbps) % s


# Gray-coded levels: the bits of one axis, first transmitted first, give the index
_LEVELS = {1: np.array([-1.0, 1.0]),
           2: np.array([-3.0, -1.0, 3.0, 1.0]),
           3: np.array([-7.0, -5.0, -1.0, -3.0, 7.0, 5.0, 1.0, 3.0])}
_KMOD = {"bpsk": 1.0, "qpsk": 1.0 / math.sqrt(2.0), "16qam": 1.0 / math.sqrt(10.0), "64qam": 1.0 / math.sqrt(42.0)}


def map_bits(bits, modulation):
    """Interleaved bits of a symbol -> the 48 constellation points."""
    bits = np.asarray(bits, np.uint8)
    if modulation == "bpsk":
        return _LEVELS[1][bits].astype(complex)
    per_axis = {"qpsk": 1, "16qam": 2, "64qam": 3}[modulation]
    g = bits.reshape(-1, 2 * per_axis)
    weights = 1 << np.arange(per_axis - 1, -1, -1)       # first bit is the most significant of the index
    i = _LEVELS[per_axis][g[:, :per_axis] @ weights]
    q = _LEVELS[per_axis][g[:, per_axis:] @ weights]
    return (i + 1j * q) * _KMOD[modulation]


def demap_soft(points, modulation, weight=None):
    """Constellation points -> a soft value per bit, positive for a 1 (max-log, scaled by `weight`
    per point, which is the carrier's signal-to-noise ratio up to a constant)."""
    points = np.asarray(points)
    w = np.ones(len(points)) if weight is None else np.asarray(weight, float)
    if modulation == "bpsk":
        return points.real * w
    per_axis = {"qpsk": 1, "16qam": 2, "64qam": 3}[modulation]
    lev = _LEVELS[per_axis] * _KMOD[modulation]
    out = np.empty((len(points), 2 * per_axis))
    idx = np.arange(len(lev))
    for axis, v in ((0, points.real), (1, points.imag)):
        d2 = (v[:, None] - lev[None, :]) ** 2
        for b in range(per_axis):
            one = (idx >> (per_axis - 1 - b)) & 1 == 1
            out[:, axis * per_axis + b] = (d2[:, ~one].min(axis=1) - d2[:, one].min(axis=1)) * w
    return out.reshape(-1)


def viterbi(soft):
    """Maximum-likelihood decode of the rate-1/2 mother code from soft values (positive = 1, 0 = not
    sent), encoder started in the all-zero state.  Returns the information bits."""
    soft = np.asarray(soft, float).reshape(-1, 2)
    n = len(soft)
    states = np.arange(64)
    # state = the six previous input bits, the newest in bit 5
    prev = np.empty((64, 2), int)        # the two states a state is reached from
    outs = np.empty((64, 2, 2))          # the code bits (as +-1) on those two branches
    for s in states:
        bit = s >> 5                     # the input bit that led into s
        for j in (0, 1):
            p = ((s << 1) & 0x3F) | j    # predecessor: shifts down, j was its oldest bit
            d = [bit] + [(p >> (5 - t)) & 1 for t in range(6)]      # d[0] newest .. d[6] oldest
            a = d[0] ^ d[2] ^ d[3] ^ d[5] ^ d[6]
            b = d[0] ^ d[1] ^ d[2] ^ d[3] ^ d[6]
            prev[s, j] = p
            outs[s, j] = (2 * a - 1, 2 * b - 1)
    metric = np.full(64, -1e30)
    metric[0] = 0.0
    choice = np.empty((n, 64), np.uint8)
    for t in range(n):
        cand = metric[prev] + outs[:, :, 0] * soft[t, 0] + outs[:, :, 1] * soft[t, 1]
        choice[t] = cand[:, 1] > cand[:, 0]
        metric = cand[states, choice[t]]
    s = int(np.argmax(metric))
    bits = np.empty(n, np.uint8)
    for t in range(n - 1, -1, -1):
        bits[t] = s >> 5
        s = prev[s, choice[t, s]]
    return bits


# ---------------------------------------------------------------------------------------------- transmit
def signal_bits(rate, length):
    """The 24 bits of SIGNAL: RATE, a reserved 0, LENGTH (LSB first), even parity, six tail zeros."""
    assert 1 <= length <= 4095
    b = list(RATES[rate][5]) + [0] + [(length >> i) & 1 for i in range(12)]
    return np.array(b + [sum(b) & 1] + [0] * 6, np.uint8)


def data_symbol_count(rate, length):
    return -(-(16 + 8 * length + 6) // RATES[rate][4])


def txtime(rate, length, signal_extension=False):
    """Air time of the PPDU in seconds (preamble 16 us, SIGNAL 4 us, DATA 4 us a symbol); with the 6 us
    of silence that ERP-OFDM adds in the 2.4 GHz band if asked."""
    return (20 + 4 * data_symbol_count(rate, length) + (6 if signal_extension else 0)) * 1e-6


def ofdm_symbol(points, pilot_index):
    """48 constellation points and the pilots (polarity p_n, n = pilot_index) on their subcarriers."""
    x = np.zeros(N_FFT, complex)
    x[np.array(DATA_K) % N_FFT] = points
    x[np.array(PILOT_K) % N_FFT] = np.array(PILOT_V) * PILOT_POLARITY[pilot_index % 127]
    return x


class Ppdu:
    """One PPDU: `symbols` is the list of frequency-domain symbols after the preamble (SIGNAL, then the
    DATA symbols); samples() is the whole thing at 20 MS/s."""

    def __init__(self, rate, psdu, scrambler_state, symbols, steps):
        self.rate, self.psdu, self.scrambler_state = rate, bytes(psdu), scrambler_state
        self.symbols = symbols
        self.steps = steps               # intermediate bit vectors, by name, for checks

    def samples(self, window=True):
        """The baseband samples.  With `window`, a symbol's first sample is the mean of it and the sample
        that would follow the symbol before it (the standard's time-domain window at 20 MS/s)."""
        short = to_time(STF_FREQ)
        long_ = to_time(LTF_FREQ)
        parts = [np.tile(short, 3)[:161], np.concatenate((long_[32:], long_, long_, long_[:1]))]
        for x in self.symbols:
            body = to_time(x)
            parts.append(np.concatenate((body[-N_CP:], body, body[:1])))
        total = sum(len(p) - 1 for p in parts) + 1
        out = np.zeros(total, complex)
        at = 0
        for p in parts:
            seg = p.copy()
            if window:
                seg[0] *= 0.5
                seg[-1] *= 0.5
            else:
                seg[-1] = 0.0
            out[at:at + len(seg)] += seg
            at += len(seg) - 1
        return out if window else out[:-1]


def encode(psdu, rate, scrambler_state="1011101"):
    """A PSDU (the MAC frame, FCS included) -> its PPDU."""
    modulation, coding, n_bpsc, n_cbps, n_dbps, _ = RATES[rate]
    psdu = bytes(psdu)
    steps = {}
    sig = signal_bits(rate, len(psdu))
    il6 = interleaver(48, 1)
    sig_coded = conv_encode(sig)
    sig_il = np.empty(48, np.uint8)
    sig_il[il6] = sig_coded
    symbols = [ofdm_symbol(map_bits(sig_il, "bpsk"), 0)]
    steps.update(signal=sig, signal_coded=sig_coded, signal_interleaved=sig_il)

    n_sym = data_symbol_count(rate, len(psdu))
    n_data = n_sym * n_dbps
    data = np.zeros(n_data, np.uint8)
    data[16:16 + 8 * len(psdu)] = bits_of(psdu)
    scrambled = data ^ scrambler(scrambler_state, n_data)
    tail = 16 + 8 * len(psdu)
    scrambled[tail:tail + 6] = 0
    coded = puncture(conv_encode(scrambled), coding)
    il = interleaver(n_cbps, n_bpsc)
    interleaved = np.empty_like(coded)
    for n in range(n_sym):
        block = coded[n * n_cbps:(n + 1) * n_cbps]
        out = np.empty(n_cbps, np.uint8)
        out[il] = block
        interleaved[n * n_cbps:(n + 1) * n_cbps] = out
        symbols.append(ofdm_symbol(map_bits(out, modulation), n + 1))
    steps.update(data=data, scrambled=scrambled, coded=coded, interleaved=interleaved)
    return Ppdu(rate, psdu, scrambler_state, symbols, steps)


# ---------------------------------------------------------------------------------------------- receive
class Reception:
    """What decode() found.  ok: SIGNAL was valid and the DATA field was all there.  psdu: the octets
    (check the FCS in the MAC).  evm_db: error-vector magnitude of the DATA carriers against the
    constellation.  cfo_hz, start: the carrier offset and the sample the preamble starts at."""

    def __init__(self):
        self.ok = False
        self.why = ""
        self.rate = self.length = None
        self.psdu = b""
        self.evm_db = self.cfo_hz = self.start = None
        self.scrambler_state = None
        self.symbols = []                # equalised DATA symbols (48 points each)

    def __repr__(self):
        if not self.ok:
            return "Reception(failed: %s)" % self.why
        return "Reception(%g Mb/s, %d octets, EVM %.1f dB, CFO %.0f Hz, start %d)" % (
            self.rate, self.length, self.evm_db, self.cfo_hz, self.start)


def find_preamble(x, threshold=0.6, min_power=1e-12):
    """The sample at which a preamble starts and a coarse carrier offset in Hz, or None.  The short
    training field repeats every 16 samples: where the signal correlates with itself 16 samples on, for
    long enough, it has begun."""
    n = len(x) - 32
    if n < 320:
        return None
    prod = x[16:16 + n + 16] * np.conj(x[:n + 16])
    power = np.abs(x[16:16 + n + 16]) ** 2
    c = np.convolve(prod, np.ones(16), "valid")          # sum over 16 samples starting at each index
    p = np.convolve(power, np.ones(16), "valid")
    m = np.abs(c) / np.maximum(p, min_power)
    good = (m > threshold) & (p > min_power * 16)
    run = 0
    for i, g in enumerate(good):
        run = run + 1 if g else 0
        if run == 96:                    # six short symbols' worth of plateau
            start = i - 95
            cfo = np.angle(np.sum(c[start:start + 96])) / (2 * math.pi * 16) * FS
            return start, cfo
    return None


def decode(samples, start=None, cfo_hz=None, noise_var=None):
    """Samples at 20 MS/s -> a Reception.  `start` and `cfo_hz` skip the synchroniser (start is the first
    sample of the short training field)."""
    r = Reception()
    x = np.asarray(samples, complex)
    if start is None:
        found = find_preamble(x)
        if found is None:
            r.why = "no preamble"
            return r
        coarse_start, coarse_cfo = found
    else:
        coarse_start, coarse_cfo = start, (cfo_hz or 0.0)
    n = np.arange(len(x))
    x = x * np.exp(-2j * math.pi * coarse_cfo / FS * n)

    long_ = to_time(LTF_FREQ)
    if start is None:
        # fine timing: the long symbol, searched round where the short field should end
        lo = max(coarse_start + 160 - 48, 0)
        seg = x[lo:lo + 160 + 96]
        if len(seg) < 64 + 64:
            r.why = "preamble cut short"
            return r
        corr = np.abs(np.correlate(seg, long_, "valid"))
        both = corr[:-64] + corr[64:]
        ltf1 = lo + int(np.argmax(both))                # first sample of the first long symbol
    else:
        ltf1 = coarse_start + 160 + 32
    if ltf1 + 128 + N_SYM > len(x):
        r.why = "preamble cut short"
        return r
    r.start = ltf1 - 192
    # every transform window starts BACKOFF samples early, inside the guard interval: a transmitter's
    # filters put some of each symbol ahead of it, and the channel estimate takes up the phase slope
    ltf1 -= BACKOFF
    l1, l2 = x[ltf1:ltf1 + 64], x[ltf1 + 64:ltf1 + 128]
    fine_cfo = 0.0 if cfo_hz is not None else np.angle(np.vdot(l1, l2)) / (2 * math.pi * 64) * FS
    x = x * np.exp(-2j * math.pi * fine_cfo / FS * (n - ltf1))
    l1, l2 = x[ltf1:ltf1 + 64], x[ltf1 + 64:ltf1 + 128]
    used = np.array(USED_K) % N_FFT
    h = np.zeros(N_FFT, complex)
    f1, f2 = to_freq(l1), to_freq(l2)
    h[used] = (f1[used] + f2[used]) / 2 / LTF_FREQ[used]
    if noise_var is None:
        noise_var = max(float(np.mean(np.abs(f1[used] - f2[used]) ** 2)) / 2, 1e-12)
    r.cfo_hz = coarse_cfo + fine_cfo

    data_idx = np.array(DATA_K) % N_FFT
    pilot_idx = np.array(PILOT_K) % N_FFT
    gain = np.abs(h[data_idx]) ** 2

    def symbol(m, pilot_index):
        """Equalised data points of the m-th symbol after the long training field."""
        at = ltf1 + 128 + m * N_SYM + N_CP
        if at + 64 > len(x):
            return None
        f = to_freq(x[at:at + 64])
        ref = np.array(PILOT_V) * PILOT_POLARITY[pilot_index % 127]
        phase = np.angle(np.sum(f[pilot_idx] * np.conj(h[pilot_idx] * ref)))   # common phase error
        return f[data_idx] * np.exp(-1j * phase) / np.where(gain > 0, h[data_idx], 1.0)

    pts = symbol(0, 0)
    if pts is None:
        r.why = "no SIGNAL"
        return r
    il6 = interleaver(48, 1)
    sig = viterbi(demap_soft(pts, "bpsk", gain)[il6])
    rate = RATE_OF_BITS.get(tuple(int(b) for b in sig[:4]))
    length = int(sum(int(b) << i for i, b in enumerate(sig[5:17])))
    if rate is None or sig[4] != 0 or int(sig[:18].sum()) & 1 or length == 0 or sig[18:].any():
        r.why = "SIGNAL not valid (%s)" % "".join(str(int(b)) for b in sig)
        return r
    r.rate, r.length = rate, length
    modulation, coding, n_bpsc, n_cbps, n_dbps, _ = RATES[rate]
    n_sym = data_symbol_count(rate, length)
    il = interleaver(n_cbps, n_bpsc)
    soft = np.empty(n_sym * n_cbps)
    err = ref_pow = 0.0
    for m in range(n_sym):
        pts = symbol(m + 1, m + 1)
        if pts is None:
            r.why = "DATA cut short (%d of %d symbols)" % (m, n_sym)
            return r
        r.symbols.append(pts)
        soft[m * n_cbps:(m + 1) * n_cbps] = demap_soft(pts, modulation, gain / noise_var).reshape(-1)[il]
        hard = map_bits((demap_soft(pts, modulation) > 0).astype(np.uint8), modulation)
        err += float(np.sum(np.abs(pts - hard) ** 2))
        ref_pow += float(np.sum(np.abs(hard) ** 2))
    bits = viterbi(depuncture(soft, coding))
    state = scrambler_state_after(bits[:7])
    if not any(state):
        r.why = "scrambler state all zero"
        return r
    seq = scrambler("".join(str(b) for b in state), len(bits) - 7)
    plain = bits.copy()
    plain[7:] ^= seq
    plain[:7] = 0
    r.psdu = octets_of(plain[16:16 + 8 * length])
    # the state the transmitter started from: run the generator back seven steps
    reg = list(state)
    for _ in range(7):
        newest, rest = reg[0], reg[1:]       # rest: the old x1 .. x6; the newest bit was old x7 xor old x4
        reg = rest + [newest ^ rest[3]]
    r.scrambler_state = "".join(str(b) for b in reg)
    r.evm_db = 10 * math.log10(max(err / ref_pow, 1e-30))
    r.ok = True
    return r


# ---------------------------------------------------------------------------------------------- checks
def channel(x, snr_db=None, cfo_hz=0.0, delay=0, taps=(1.0,), gain=1.0, rng=None, lead=200, tail=120):
    """A test channel: `lead` samples of noise, the signal through `taps` with a carrier offset, noise."""
    rng = rng or np.random.default_rng(1)
    y = np.convolve(x, np.asarray(taps, complex))
    y = np.concatenate((np.zeros(lead + delay, complex), y, np.zeros(tail, complex))) * gain
    y = y * np.exp(2j * math.pi * cfo_hz / FS * np.arange(len(y)))
    if snr_db is not None:
        sigma = math.sqrt(gain * gain * 10 ** (-snr_db / 10) / 2)
        y = y + sigma * (rng.standard_normal(len(y)) + 1j * rng.standard_normal(len(y)))
    return y


def check(verbose=True):
    """The self-checks; returns the number that failed."""
    failed = 0

    def say(ok, what, detail=""):
        nonlocal failed
        failed += 0 if ok else 1
        if verbose:
            print("  %s %-58s %s" % ("ok  " if ok else "FAIL", what, detail))

    # the scrambling sequence from the all-ones state, as the standard prints it (17.3.5.5)
    printed = ("00001110" "11110010" "11001001" "00000010" "00100110" "00101110" "10110110" "00001100"
               "11010100" "11100111" "10110100" "00101010" "11111010" "01010001" "10111000" "1111111")
    seq = "".join(str(b) for b in scrambler("1111111", 127))
    say(seq == printed, "scrambler sequence from the all-ones state")
    say(len(set(tuple(scrambler("1111111", 254)[i:i + 7]) for i in range(127))) == 127, "its period is 127")
    # the first pilot polarities as the standard lists them
    say(list(PILOT_POLARITY[:16]) == [1, 1, 1, 1, -1, -1, -1, 1, -1, -1, -1, -1, 1, 1, -1, 1], "pilot polarity p_0 .. p_15")
    # SIGNAL of the standard's worked example: 36 Mb/s, 100 octets
    say("".join(str(b) for b in signal_bits(36, 100)) == "101100010011000000000000", "SIGNAL bits, 36 Mb/s and 100 octets")
    # the interleaver is a permutation and its inverse undoes it, for each symbol size
    for rate, (mod, coding, n_bpsc, n_cbps, n_dbps, _) in RATES.items():
        il = interleaver(n_cbps, n_bpsc)
        if sorted(il) != list(range(n_cbps)):
            say(False, "interleaver is a permutation, %d Mb/s" % rate)
    say(True, "interleaver is a permutation at every rate")
    # 16-QAM interleaver: the standard's first indices (k = 0, 1, 2 -> j = 0, 13, 24 ... for N_CBPS 192)
    il = interleaver(192, 4)
    say(list(il[:6]) == [0, 13, 24, 37, 48, 61], "interleaver, N_CBPS 192: first six positions", str(list(il[:6])))
    # code: a single 1 gives the two generators' taps
    imp = conv_encode(np.array([1, 0, 0, 0, 0, 0, 0], np.uint8))
    say("".join(str(b) for b in imp[0::2]) == "1011011" and "".join(str(b) for b in imp[1::2]) == "1111001",
        "convolutional code generators 133, 171 (octal)")
    # constellations: unit mean power and Gray coding
    for mod, nb in (("bpsk", 1), ("qpsk", 2), ("16qam", 4), ("64qam", 6)):
        allbits = np.array([[(v >> (nb - 1 - i)) & 1 for i in range(nb)] for v in range(1 << nb)], np.uint8)
        pts = map_bits(allbits.reshape(-1), mod)
        ok = abs(np.mean(np.abs(pts) ** 2) - 1.0) < 1e-12
        back = (demap_soft(pts, mod) > 0).astype(np.uint8).reshape(-1, nb)
        ok = ok and (back == allbits).all()
        if mod != "bpsk":                # nearest neighbours along an axis differ in one bit
            for a in range(len(pts)):
                for b in range(len(pts)):
                    d = abs(pts[a] - pts[b])
                    if 0 < d < 2.01 * _KMOD[mod] and int((allbits[a] ^ allbits[b]).sum()) != 1:
                        ok = False
        say(ok, "constellation %s: unit power, demaps, Gray" % mod)
    # preamble: unit mean power, period 16 in the short field, 64 in the long
    p = encode(b"\x00" * 30, 6).samples(window=False)
    say(abs(np.mean(np.abs(p[:160]) ** 2) - 1) < 1e-9 and abs(np.mean(np.abs(p[160:320]) ** 2) - 1) < 1e-9,
        "training fields have unit mean power")
    say(np.allclose(p[:144], p[16:160]) and np.allclose(p[192:256], p[256:320]) and np.allclose(p[160:192], p[224:256]),
        "short field repeats every 16 samples, long field as specified")
    # loop-back at every rate: clean, and through a channel with noise, carrier offset and echoes
    rng = np.random.default_rng(7)
    for rate in RATES:
        psdu = bytes(rng.integers(0, 256, 137, dtype=np.uint8))
        tx = encode(psdu, rate, scrambler_state="".join(str(b) for b in rng.integers(0, 2, 6)) + "1")
        rx = decode(tx.samples())
        ok = rx.ok and rx.psdu == psdu and rx.rate == rate and rx.scrambler_state == tx.scrambler_state
        say(ok, "loop-back %2d Mb/s, clean" % rate, repr(rx))
        snr = {6: 8, 9: 11, 12: 11, 18: 14, 24: 18, 36: 21, 48: 26, 54: 28}[rate]
        y = channel(tx.samples(), snr_db=snr, cfo_hz=41e3, delay=int(rng.integers(0, 50)),
                    taps=(1.0, 0.0, 0.25j, 0.0, -0.1), gain=0.02, rng=rng)
        rx = decode(y)
        say(rx.ok and rx.psdu == psdu, "loop-back %2d Mb/s, %d dB SNR, 41 kHz offset, echoes" % (rate, snr), repr(rx))
    # windowing leaves the symbol bodies alone: a windowed frame decodes with known timing
    tx = encode(b"window" * 9, 54)
    rx = decode(tx.samples(window=True), start=0, cfo_hz=0.0)
    say(rx.ok and rx.psdu == b"window" * 9, "windowed samples decode with known timing", repr(rx))
    say(data_symbol_count(36, 100) == 6 and abs(txtime(36, 100) - 44e-6) < 1e-12,
        "36 Mb/s, 100 octets: 6 DATA symbols, 44 us on the air")
    return failed


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "check":
        n = check()
        print("%d failed" % n if n else "all passed")
        sys.exit(1 if n else 0)
    print(__doc__)
