#!/usr/bin/env python3
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# SPDX-FileCopyrightText: 2026 D. Kevin Cameron
# Part of stat-sim. PolyForm Noncommercial License 1.0.0; commercial use needs a separate license (see LICENSE, COMMERCIAL.md).
"""
ble_phy.py -- the Bluetooth LE physical layer and packet format, from the Bluetooth Core Specification.

What a radio needs that its data sheet does not give: GFSK modulation, the RF channels, the packet
formats of the four PHYs (LE 1M, LE 2M, LE Coded S=2 and S=8), whitening, the CRC and the Coded PHY's
convolutional code.  Nothing here belongs to one chip; cc2652r.py puts a chip's radio round it.

Where it comes from (Core Specification 6.1, Vol 6; status as in cc2652r.py):
  "spec"  read on 2026-11-24 from the HTML edition: Part A (GFSK BT 0.5, modulation index 0.45-0.55,
          1 and 2 Msym/s, 40 channels 2402-2480 MHz), Part B up to 2.4 (bit order, packet fields, the
          advertising access address, PDU types, channel index table, Coded PHY fields and durations).
  "rec"   written from recollection, the text (Part B 3.x, 4.x) could not be read: the CRC polynomial
          and its advertising initial value, the whitening LFSR, the FEC polynomials and pattern mapper.
  Every "rec" item is checked by `ble_phy.py check` against the specification's own sample data
  (Part C: whitening sequences, a complete advertising packet, the Coded PHY encoder example), which
  it reproduces bit for bit.

Bits are in transmission order throughout (the LSB of an octet first); a symbol stream is a numpy
array of 0 / 1, one per symbol on the air.
"""
import math
import sys

import numpy as np

ADV_ACCESS_ADDRESS = 0x8E89BED6          # spec: advertising physical channel
TEST_ACCESS_ADDRESS = 0x71764129         # rec: Direct Test Mode sync word (packets are not whitened)
CRC_INIT_ADV = 0x555555                  # rec: advertising channels and test packets
T_IFS = 150e-6                           # rec: inter frame space, s

PHYS = {
    # name: (symbol rate, S; S = 1: uncoded)
    "1m": (1e6, 1), "2m": (2e6, 1), "s2": (1e6, 2), "s8": (1e6, 8),
}
BIT_RATE = {"1m": 1e6, "2m": 2e6, "s2": 500e3, "s8": 125e3}

# advertising physical channel PDU types (spec, Part B table 2.3)
ADV_IND, ADV_DIRECT_IND, ADV_NONCONN_IND, SCAN_REQ, SCAN_RSP, CONNECT_IND, ADV_SCAN_IND = range(7)
PDU_NAMES = ("ADV_IND", "ADV_DIRECT_IND", "ADV_NONCONN_IND", "SCAN_REQ", "SCAN_RSP", "CONNECT_IND", "ADV_SCAN_IND")


def channel_frequency(index):
    """Centre frequency (Hz) of a channel index: 37, 38, 39 advertise at 2402, 2426, 2480 MHz (spec)."""
    if index == 37:
        return 2402e6
    if index == 38:
        return 2426e6
    if index == 39:
        return 2480e6
    if 0 <= index <= 10:
        return 2404e6 + 2e6 * index
    if 11 <= index <= 36:
        return 2428e6 + 2e6 * (index - 11)
    raise ValueError("channel index %r" % (index,))


def rf_channel_frequency(k):
    """Centre frequency of RF channel k (0 .. 39), as Direct Test Mode numbers them: 2402 + 2 k MHz."""
    if not 0 <= k <= 39:
        raise ValueError("RF channel %r" % (k,))
    return 2402e6 + 2e6 * k


def bits_of(octets):
    return np.unpackbits(np.frombuffer(bytes(octets), np.uint8), bitorder="little")


def octets_of(bits):
    return np.packbits(np.asarray(bits, np.uint8), bitorder="little").tobytes()


def int_bits(value, n):
    """n bits of an integer, least significant first."""
    return np.array([(value >> i) & 1 for i in range(n)], np.uint8)


def whitening(channel, n):
    """n bits of the whitening sequence of a channel index: x^7 + x^4 + 1, position 0 set, the channel
    index in positions 1 .. 6 with its MSB in position 1 (rec; Part C 4.1 sequences reproduced)."""
    reg = [1] + [(channel >> (5 - i)) & 1 for i in range(6)]
    out = np.empty(n, np.uint8)
    for i in range(n):
        o = reg[6]
        out[i] = o
        reg = [o, reg[0], reg[1], reg[2], reg[3] ^ o, reg[4], reg[5]]
    return out


def crc24(bits, init=CRC_INIT_ADV):
    """The 24 CRC bits of a PDU in transmission order: x^24 + x^10 + x^9 + x^6 + x^4 + x^3 + x + 1, the
    register preset to `init`, its most significant position sent first (rec; Part C packet reproduced)."""
    crc = init
    for b in bits:
        fb = ((crc >> 23) & 1) ^ int(b)
        crc = (crc << 1) & 0xFFFFFF
        if fb:
            crc ^= 0x00065B
    return np.array([(crc >> (23 - i)) & 1 for i in range(24)], np.uint8)


def fec_encode(bits, state=0):
    """Rate 1/2, constraint length 4 convolutional code of the Coded PHY: G0 = 1 + D + D^2 + D^3,
    G1 = 1 + D^2 + D^3, a0 before a1 (rec; Part C 2.2 reproduced).  Returns (coded bits, state)."""
    out = np.empty(2 * len(bits), np.uint8)
    for i, b in enumerate(bits):
        b = int(b)
        d1, d2, d3 = state & 1, (state >> 1) & 1, (state >> 2) & 1
        out[2 * i] = b ^ d1 ^ d2 ^ d3
        out[2 * i + 1] = b ^ d2 ^ d3
        state = (b | (state << 1)) & 7
    return out, state


def pattern_map(coded, s):
    """Coded bits to symbols: S = 2 as they are, S = 8 each bit as 0011 (0) or 1100 (1) (rec)."""
    if s == 2:
        return np.asarray(coded, np.uint8)
    c = np.asarray(coded, np.uint8)
    return np.stack([c, c, 1 - c, 1 - c], axis=-1).reshape(c.shape[:-1] + (-1,))


CODED_PREAMBLE = np.tile(np.array([0, 0, 1, 1, 1, 1, 0, 0], np.uint8), 10)      # spec


def coded_block1(access_address, s):
    """Symbols of FEC block 1 (access address, CI, TERM1; always S = 8) and nothing else."""
    ci = int_bits(0 if s == 8 else 1, 2)
    b, st = fec_encode(np.concatenate([int_bits(access_address, 32), ci, np.zeros(3, np.uint8)]))
    assert st == 0
    return pattern_map(b, 8)


def packet_symbols(phy, pdu, channel=None, access_address=ADV_ACCESS_ADDRESS, crc_init=CRC_INIT_ADV):
    """The symbols on the air of one packet.  pdu: octets (header and payload).  channel: the channel
    index that whitens PDU and CRC; None for no whitening (Direct Test Mode)."""
    body = bits_of(pdu)
    body = np.concatenate([body, crc24(body, crc_init)])
    if channel is not None:
        body = body ^ whitening(channel, len(body))
    rate, s = PHYS[phy]
    aa = int_bits(access_address, 32)
    if s == 1:
        npre = 8 if phy == "1m" else 16
        pre = (np.arange(npre) + aa[0]) % 2                # alternating, starting as the access address does
        return np.concatenate([pre.astype(np.uint8), aa, body])
    b2, st = fec_encode(np.concatenate([body, np.zeros(3, np.uint8)]))
    return np.concatenate([CODED_PREAMBLE, coded_block1(access_address, s), pattern_map(b2, s)])


def packet_duration(phy, pdu_len):
    """Seconds on the air of a packet with a PDU of pdu_len octets."""
    rate, s = PHYS[phy]
    if s == 1:
        return ((1 if phy == "1m" else 2) + 4 + pdu_len + 3) * 8 / rate
    return (80 + 256 + 16 + 24 + (8 * pdu_len + 24 + 3) * s) / rate


def adv_pdu(pdu_type, payload, tx_add=0, rx_add=0, ch_sel=0):
    """An advertising physical channel PDU: 16-bit header (type 4 bits, RFU, ChSel, TxAdd, RxAdd, length 8)
    and the payload."""
    if not 1 <= len(payload) <= 255:
        raise ValueError("advertising payload of %d octets" % len(payload))
    return bytes([pdu_type | (ch_sel << 5) | (tx_add << 6) | (rx_add << 7), len(payload)]) + bytes(payload)


def address_octets(addr):
    """A device address written the usual way ("C1:A2:A3:A4:A5:A6") as its six octets on the air."""
    return bytes(reversed(bytes.fromhex(addr.replace(":", ""))))


def address_text(octets):
    return ":".join("%02X" % b for b in reversed(bytes(octets)))


def prbs9(n):
    """n bits of the PRBS9 test sequence (x^9 + x^5 + 1, all ones to start), transmission order."""
    reg = 0x1FF
    out = np.empty(n, np.uint8)
    for i in range(n):
        out[i] = reg & 1
        reg = (reg >> 1) | (((reg ^ (reg >> 4)) & 1) << 8)
    return out


def test_pdu(length, payload_type=0):
    """A Direct Test Mode packet PDU: header (payload type, length) and `length` octets of PRBS9."""
    if payload_type != 0:
        raise ValueError("only the PRBS9 payload is modelled")
    return bytes([payload_type, length]) + octets_of(prbs9(8 * length))


# ---------------------------------------------------------------------------------------------
# GFSK
# ---------------------------------------------------------------------------------------------
def gaussian_taps(sps, bt=0.5, span=4):
    """The Gaussian filter of GFSK convolved with one symbol, at sps samples per symbol; sums to 1."""
    t = (np.arange(span * sps + 1) - span * sps / 2.0) / sps
    g = np.exp(-2.0 * (math.pi * bt * t) ** 2 / math.log(2.0))
    h = np.convolve(g, np.ones(sps))
    return h / h.sum() * sps


def gfsk(symbols, sps, h=0.5, bt=0.5, phase0=0.0, lead=None):
    """Unit-amplitude complex envelope of a symbol stream: 1 is a positive frequency deviation of
    h / 2 times the symbol rate.  Returns (envelope of len(symbols) * sps samples, the final phase).
    Symbol k is centred on sample k * sps + (sps - 1) / 2."""
    nrz = np.repeat(2.0 * np.asarray(symbols, float) - 1.0, sps)
    taps = gaussian_taps(sps, bt) / sps
    f = np.convolve(nrz, taps)[(len(taps) - 1) // 2:][:len(nrz)]
    phase = phase0 + np.cumsum(f) * (math.pi * h / sps)
    return np.exp(1j * phase), float(phase[-1]) if len(phase) else phase0


def discriminate(y, sps):
    """Phase advance over one symbol period ending at each sample (rad): positive for a 1."""
    z = np.zeros(len(y), complex)
    z[sps:] = y[sps:] * np.conj(y[:-sps])
    return np.angle(z)


def sequence_detect(soft, taps):
    """Symbols from the discriminator's output, allowing for what a narrow channel filter does to it:
    soft[k] = taps[0] m[k-1] + taps[1] m[k] + taps[2] m[k+1] + noise, m = +-1.  The most likely
    sequence (four states), over the last axis of soft.  Returns bits of soft's shape."""
    soft = np.asarray(soft, float)
    lead = soft.shape[:-1]
    n = soft.shape[-1]
    m = (-1.0, 1.0)
    # new state s' = b[k] | b[k+1] << 1, from state x | b[k] << 1
    prev = np.array([[x | ((sp & 1) << 1) for x in (0, 1)] for sp in range(4)])
    expect = np.array([[taps[0] * m[x] + taps[1] * m[sp & 1] + taps[2] * m[sp >> 1] for x in (0, 1)] for sp in range(4)])
    pm = np.zeros(lead + (4,))
    choice = np.empty((n,) + lead + (4,), np.uint8)
    for k in range(n):
        cand = pm[..., prev] - (soft[..., k, None, None] - expect) ** 2
        c = cand[..., 1] > cand[..., 0]
        choice[k] = c
        pm = np.where(c, cand[..., 1], cand[..., 0])
    state = np.argmax(pm, axis=-1)
    bits = np.empty(lead + (n,), np.uint8)
    for k in range(n - 1, -1, -1):
        bits[..., k] = state & 1
        x = np.take_along_axis(choice[k], state[..., None], axis=-1)[..., 0]
        state = x.astype(np.int64) | ((state & 1) << 1)
    return bits


def sequence_detect_stream(soft, taps, row=256, overlap=8):
    """sequence_detect over one long stream, cut into overlapping rows that are decoded together."""
    soft = np.asarray(soft, float)
    n = len(soft)
    if n <= row + 2 * overlap:
        return sequence_detect(soft, taps)
    pad = np.concatenate([np.zeros(overlap), soft, np.zeros(row + overlap)])
    starts = np.arange(0, n, row)
    got = sequence_detect(pad[starts[:, None] + np.arange(row + 2 * overlap)], taps)
    return got[:, overlap: overlap + row].ravel()[:n]


# ---------------------------------------------------------------------------------------------
# Viterbi decoder for the Coded PHY
# ---------------------------------------------------------------------------------------------
_PREV = np.array([[(sp >> 1) | (x << 2) for x in (0, 1)] for sp in range(8)])       # [state, x] -> previous state


def _branch_signs():
    s0 = np.empty((8, 2))
    s1 = np.empty((8, 2))
    for sp in range(8):
        for x in (0, 1):
            prev = _PREV[sp, x]
            b = sp & 1
            d1, d2, d3 = prev & 1, (prev >> 1) & 1, (prev >> 2) & 1
            s0[sp, x] = 2.0 * (b ^ d1 ^ d2 ^ d3) - 1.0
            s1[sp, x] = 2.0 * (b ^ d2 ^ d3) - 1.0
    return s0, s1


_S0, _S1 = _branch_signs()


def viterbi(llr, terminated=True):
    """Decode soft coded bits.  llr: shape (..., n, 2), positive for a coded 1 (a0, a1 of each of n
    bits); the encoder starts in state 0 and, if `terminated`, ends there.  Returns bits (..., n)."""
    llr = np.asarray(llr, float)
    lead = llr.shape[:-2]
    n = llr.shape[-2]
    pm = np.full(lead + (8,), -1e30)
    pm[..., 0] = 0.0
    choice = np.empty((n,) + lead + (8,), np.uint8)
    for k in range(n):
        cand = pm[..., _PREV] + _S0 * llr[..., k, 0, None, None] + _S1 * llr[..., k, 1, None, None]
        c = cand[..., 1] > cand[..., 0]
        choice[k] = c
        pm = np.where(c, cand[..., 1], cand[..., 0])
    state = np.zeros(lead, np.int64) if terminated else np.argmax(pm, axis=-1)
    bits = np.empty(lead + (n,), np.uint8)
    for k in range(n - 1, -1, -1):
        bits[..., k] = state & 1
        x = np.take_along_axis(choice[k], state[..., None], axis=-1)[..., 0]
        state = (state >> 1) | (x.astype(np.int64) << 2)
    return bits


def pattern_llr(soft, s):
    """Soft symbols (positive for 1) of pattern-mapped coded bits -> llr of the coded bits, (..., n, 2)."""
    soft = np.asarray(soft, float)
    if s == 8:
        q = soft.reshape(soft.shape[:-1] + (-1, 4))
        soft = q[..., 0] + q[..., 1] - q[..., 2] - q[..., 3]
    return soft.reshape(soft.shape[:-1] + (-1, 2))


# ---------------------------------------------------------------------------------------------
# check: the specification's sample data (Core 6.1, Vol 6 Part C)
# ---------------------------------------------------------------------------------------------
def _b(text):
    return np.array([int(c) for c in text if c in "01"], np.uint8)


def cmd_check():
    bad = 0

    def same(what, got, want):
        nonlocal bad
        ok = len(got) == len(want) and bool(np.all(np.asarray(got) == np.asarray(want)))
        bad += not ok
        print("  %-58s %s" % (what, "same" if ok else "DIFFERS"))

    print("Bluetooth Core 6.1 Vol 6 Part C sample data")
    for ch, want in ((0, "00000010 01001101 00111101 11000011 11111000 11101100 01010010 11111010"),
                     (1, "10010001 00000010 01001101 00111101 11000011 11111000 11101100 01010010"),
                     (37, "10110001 01001011 11101010 10000101 10111100 11100101 01100110 00001101"),
                     (38, "01101011 10100011 00100010 00000100 10011010 01111011 10000111 11110001"),
                     (39, "11111000 11101100 01010010 11111010 10100001 01101111 00111001 01011001")):
        same("4.1 whitening sequence, channel %d (64 bits)" % ch, whitening(ch, 64), _b(want))
    pdu = adv_pdu(ADV_NONCONN_IND, address_octets("C1:A2:A3:A4:A5:A6") + bytes([1, 2, 3]), tx_add=1)
    same("4.2.1 ADV_NONCONN_IND header", bits_of(pdu[:2]), _b("0100 0 0 1 0 10010000"))
    same("4.2.1 CRC", crc24(bits_of(pdu)), _b("10110101 00101101 11010111"))
    want = _b("01010101 01101011 01111101 10010001 01110001 00101001 00110011 01000111 10100001 10111111"
              " 10111110 11000010 01110010 01011000 11100101 00110101 11110111 11110011 10100101")
    same("4.2.1 complete packet on channel 38 (152 bits)", packet_symbols("1m", pdu, 38), want)
    aa_in = _b("0 1 1 0 1 0 1 1 0 1 1 1 1 1 0 1 1 0 0 1 0 0 0 1 0 1 1 1 0 0 0 1")
    aa_out = _b("0 0 1 1 0 1 0 1 1 1 0 1 0 0 1 0 0 1 1 1 1 0 1 0 0 1 0 1 1 0 1 1"
                " 1 0 0 1 0 0 0 0 1 0 1 1 1 1 1 1 1 0 0 0 1 0 1 0 1 0 0 0 1 1 1 1")
    same("2.2 access address as the encoder's input", int_bits(ADV_ACCESS_ADDRESS, 32), aa_in)
    same("2.2 FEC encoder output for the access address", fec_encode(aa_in)[0], aa_out)
    ref = bytes.fromhex("000342 4C45".replace(" ", ""))
    same("2.1 reference packet CRC (29 0A CE)", octets_of(crc24(bits_of(ref))), bytes.fromhex("290ACE"))
    for phy, us in (("s2", 510), ("s8", 912)):
        n = len(packet_symbols(phy, ref))
        same("2.3 / 2.4 reference packet duration, %s: %d us" % (phy.upper(), us), [n], [us])
    rng = np.random.default_rng(1)
    bits = rng.integers(0, 2, (5, 200)).astype(np.uint8)
    bits[:, -3:] = 0
    coded = np.stack([fec_encode(r)[0] for r in bits])
    same("Viterbi decoder returns what the encoder was given (S=2)", viterbi(pattern_llr(2.0 * coded - 1.0, 2)), bits)
    same("the same through the S=8 pattern mapper", viterbi(pattern_llr(2.0 * pattern_map(coded, 8) - 1.0, 8)), bits)
    print("%d difference(s)" % bad)
    return 1 if bad else 0


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "check":
        sys.exit(cmd_check())
    print("usage: ble_phy.py check", file=sys.stderr)
    sys.exit(2)
