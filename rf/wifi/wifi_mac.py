#!/usr/bin/env python3
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# SPDX-FileCopyrightText: 2026 D. Kevin Cameron
# Part of stat-sim. PolyForm Noncommercial License 1.0.0; commercial use needs a separate license (see LICENSE, COMMERCIAL.md).
"""
wifi_mac.py -- IEEE 802.11 MAC frames, as much as a tester needs to hold an exchange with a station
or an access point: the frame formats, the frame check sequence, the management frames of joining
a network (beacon, probe, authentication, association), data and ACK, and the timing rules between
them.  The physical layer under it is wifi_phy.py.

  frame bytes are what the PHY carries as its PSDU: MAC header, body, FCS; the octets in the order
  sent, each LSB first on the air.

Where it comes from (IEEE Std 802.11-2020 clauses 9 and 10; status marks as in wifi_phy.py):
  "rec"  written from recollection: the frame control layout and the type and subtype codes, the
         header fields, the fixed fields and elements of the management frames, the rate encoding,
         the FCS (the CRC-32 of ISO 3309, as in Ethernet), SIFS, slot and DIFS for the OFDM PHY in
         both bands, and the rule for the rate of an ACK.
  `check` holds the FCS against a known frame and the builders against the parser.
"""
import struct
import sys
import zlib

import wifi_phy

BROADCAST = b"\xff" * 6

# type, subtype
MGMT, CTRL, DATA = 0, 1, 2
ASSOC_REQ, ASSOC_RESP, PROBE_REQ, PROBE_RESP, BEACON, DISASSOC, AUTH, DEAUTH = 0, 1, 4, 5, 8, 10, 11, 12
RTS, CTS, ACK = 11, 12, 13
DATA_DATA, DATA_NULL, DATA_QOS = 0, 4, 8
NAMES = {(MGMT, ASSOC_REQ): "association request", (MGMT, ASSOC_RESP): "association response",
         (MGMT, PROBE_REQ): "probe request", (MGMT, PROBE_RESP): "probe response", (MGMT, BEACON): "beacon",
         (MGMT, DISASSOC): "disassociation", (MGMT, AUTH): "authentication", (MGMT, DEAUTH): "deauthentication",
         (CTRL, RTS): "RTS", (CTRL, CTS): "CTS", (CTRL, ACK): "ACK",
         (DATA, DATA_DATA): "data", (DATA, DATA_NULL): "null", (DATA, DATA_QOS): "QoS data"}

# frame control flags (second octet)
TO_DS, FROM_DS, MORE_FRAG, RETRY, PWR_MGT, MORE_DATA, PROTECTED, ORDER = (1 << i for i in range(8))

# elements
E_SSID, E_RATES, E_DS, E_TIM, E_ERP, E_EXT_RATES = 0, 1, 3, 5, 42, 50

# capability information
CAP_ESS, CAP_IBSS, CAP_PRIVACY, CAP_SHORT_PREAMBLE, CAP_SHORT_SLOT = 1 << 0, 1 << 1, 1 << 4, 1 << 5, 1 << 10

OFDM_RATES = (6, 9, 12, 18, 24, 36, 48, 54)
BASIC_RATES = (6, 12, 24)                # the mandatory rates of the OFDM PHY


class Timing:
    """The intervals of the OFDM PHY, in seconds: band "5" (clause 17) or "2.4" (clause 18, ERP-OFDM,
    whose frames end with 6 us of silence, the signal extension)."""

    def __init__(self, band="2.4", short_slot=True):
        self.band = band
        self.signal_extension = band == "2.4"
        self.sifs = 10e-6 if band == "2.4" else 16e-6
        self.slot = 9e-6 if (band == "5" or short_slot) else 20e-6
        self.pifs = self.sifs + self.slot
        self.difs = self.sifs + 2 * self.slot
        self.rx_start_delay = 20e-6      # aRxPHYStartDelay: preamble and SIGNAL

    def txtime(self, rate, octets):
        return wifi_phy.txtime(rate, octets, self.signal_extension)

    def ack_timeout(self):
        return self.sifs + self.slot + self.rx_start_delay

    def response_gap(self):
        """From the end of a frame's last symbol to the start of the response's preamble: SIFS, counted
        from the end of the signal extension where there is one."""
        return self.sifs + (6e-6 if self.signal_extension else 0.0)


def fcs(octets):
    """The four FCS octets of a frame (header and body), in the order sent."""
    return struct.pack("<I", zlib.crc32(bytes(octets)) & 0xFFFFFFFF)


def fcs_ok(frame):
    return len(frame) >= 4 and fcs(frame[:-4]) == bytes(frame[-4:])


def ack_rate(rate, basic=BASIC_RATES):
    """The rate a response to a frame sent at `rate` goes at: the highest basic rate not above it."""
    return max([r for r in basic if r <= rate] or [min(basic)])


def rates_element(rates, basic=BASIC_RATES):
    """Supported Rates (and Extended Supported Rates when there are more than eight)."""
    codes = bytes((2 * r) | (0x80 if r in basic else 0) for r in rates)
    out = bytes([E_RATES, min(len(codes), 8)]) + codes[:8]
    if len(codes) > 8:
        out += bytes([E_EXT_RATES, len(codes) - 8]) + codes[8:]
    return out


def element(eid, payload):
    return bytes([eid, len(payload)]) + bytes(payload)


def header(ftype, subtype, addr1, addr2=None, addr3=None, duration=0, seq=0, flags=0):
    fc = bytes([(subtype << 4) | (ftype << 2), flags])
    h = fc + struct.pack("<H", duration) + bytes(addr1)
    if addr2 is not None:
        h += bytes(addr2)
    if addr3 is not None:
        h += bytes(addr3) + struct.pack("<H", (seq & 0xFFF) << 4)
    return h


def finish(h, body=b""):
    return h + bytes(body) + fcs(h + bytes(body))


# ---------------------------------------------------------------------------------------------- frames
def ack(ra, duration=0):
    return finish(header(CTRL, ACK, ra, duration=duration))


def beacon(bssid, ssid, channel, timestamp_us=0, interval_tu=100, seq=0, rates=OFDM_RATES, capability=None, band="2.4"):
    cap = CAP_ESS | CAP_SHORT_SLOT if capability is None else capability
    body = struct.pack("<QHH", timestamp_us, interval_tu, cap) + element(E_SSID, ssid) + rates_element(rates)
    body += element(E_DS, [channel]) + element(E_TIM, [0, 1, 0, 0])
    if band == "2.4":
        body += element(E_ERP, [0])
    return finish(header(MGMT, BEACON, BROADCAST, bssid, bssid, seq=seq), body)


def probe_request(sta, ssid=b"", seq=0, rates=OFDM_RATES):
    return finish(header(MGMT, PROBE_REQ, BROADCAST, sta, BROADCAST, seq=seq), element(E_SSID, ssid) + rates_element(rates))


def probe_response(bssid, sta, ssid, channel, duration, timestamp_us=0, interval_tu=100, seq=0, rates=OFDM_RATES,
                   capability=None, band="2.4"):
    cap = CAP_ESS | CAP_SHORT_SLOT if capability is None else capability
    body = struct.pack("<QHH", timestamp_us, interval_tu, cap) + element(E_SSID, ssid) + rates_element(rates)
    body += element(E_DS, [channel])
    if band == "2.4":
        body += element(E_ERP, [0])
    return finish(header(MGMT, PROBE_RESP, sta, bssid, bssid, duration=duration, seq=seq), body)


def authentication(to, frm, bssid, transaction, duration, status=0, seq=0):
    """Open System authentication: transaction 1 is the request, 2 the response."""
    return finish(header(MGMT, AUTH, to, frm, bssid, duration=duration, seq=seq), struct.pack("<HHH", 0, transaction, status))


def association_request(bssid, sta, ssid, duration, listen_interval=10, seq=0, rates=OFDM_RATES, capability=None):
    cap = CAP_ESS | CAP_SHORT_SLOT if capability is None else capability
    body = struct.pack("<HH", cap, listen_interval) + element(E_SSID, ssid) + rates_element(rates)
    return finish(header(MGMT, ASSOC_REQ, bssid, sta, bssid, duration=duration, seq=seq), body)


def association_response(bssid, sta, aid, duration, status=0, seq=0, rates=OFDM_RATES, capability=None):
    cap = CAP_ESS | CAP_SHORT_SLOT if capability is None else capability
    body = struct.pack("<HHH", cap, status, 0xC000 | aid) + rates_element(rates)
    return finish(header(MGMT, ASSOC_RESP, sta, bssid, bssid, duration=duration, seq=seq), body)


def data(to, frm, bssid, payload, duration, to_ds=False, from_ds=False, seq=0, retry=False):
    """A data frame; the three addresses are placed by the To DS and From DS bits (receiver, transmitter,
    then the third: BSSID, source or destination)."""
    flags = (TO_DS if to_ds else 0) | (FROM_DS if from_ds else 0) | (RETRY if retry else 0)
    if to_ds and not from_ds:            # station to access point: BSSID, source, destination
        a = (bssid, frm, to)
    elif from_ds and not to_ds:          # access point to station: destination, BSSID, source
        a = (to, bssid, frm)
    else:
        a = (to, frm, bssid)
    return finish(header(DATA, DATA_DATA, a[0], a[1], a[2], duration=duration, seq=seq, flags=flags), payload)


def llc_snap(ethertype, payload):
    """The usual body of a data frame: LLC/SNAP header and the packet."""
    return b"\xaa\xaa\x03\x00\x00\x00" + struct.pack(">H", ethertype) + bytes(payload)


# ---------------------------------------------------------------------------------------------- parse
class Frame:
    """A received frame taken apart.  ok: long enough and the FCS is right."""

    def __init__(self, octets):
        b = self.octets = bytes(octets)
        self.ok = fcs_ok(b) and len(b) >= 14
        self.fcs_ok = fcs_ok(b)
        self.type = self.subtype = self.flags = None
        self.duration = 0
        self.addr1 = self.addr2 = self.addr3 = None
        self.seq = self.frag = None
        self.body = b""
        self.elements = {}
        self.fixed = {}
        if len(b) < 14:
            return
        self.type, self.subtype, self.flags = (b[0] >> 2) & 3, b[0] >> 4, b[1]
        self.version = b[0] & 3
        self.duration = struct.unpack_from("<H", b, 2)[0]
        self.addr1 = b[4:10]
        if self.type == CTRL:
            if self.subtype == RTS and len(b) >= 20:
                self.addr2 = b[10:16]
            return
        if len(b) < 28:
            self.ok = False
            return
        self.addr2, self.addr3 = b[10:16], b[16:22]
        sc = struct.unpack_from("<H", b, 22)[0]
        self.frag, self.seq = sc & 0xF, sc >> 4
        at = 24 + (6 if (self.flags & TO_DS and self.flags & FROM_DS) else 0)
        if self.type == DATA and self.subtype & 8:
            at += 2                      # QoS control
        self.body = b[at:-4]
        if self.type == MGMT:
            fixed = {BEACON: ("<QHH", ("timestamp", "interval", "capability")),
                     PROBE_RESP: ("<QHH", ("timestamp", "interval", "capability")),
                     AUTH: ("<HHH", ("algorithm", "transaction", "status")),
                     ASSOC_REQ: ("<HH", ("capability", "listen_interval")),
                     ASSOC_RESP: ("<HHH", ("capability", "status", "aid")),
                     DEAUTH: ("<H", ("reason",)), DISASSOC: ("<H", ("reason",))}.get(self.subtype)
            p = 0
            if fixed:
                n = struct.calcsize(fixed[0])
                if len(self.body) >= n:
                    self.fixed = dict(zip(fixed[1], struct.unpack_from(fixed[0], self.body, 0)))
                p = n
            while p + 2 <= len(self.body):
                eid, n = self.body[p], self.body[p + 1]
                self.elements.setdefault(eid, self.body[p + 2:p + 2 + n])
                p += 2 + n

    @property
    def name(self):
        return NAMES.get((self.type, self.subtype), "type %s subtype %s" % (self.type, self.subtype))

    def rates(self):
        codes = self.elements.get(E_RATES, b"") + self.elements.get(E_EXT_RATES, b"")
        return [(c & 0x7F) / 2 for c in codes], [(c & 0x7F) / 2 for c in codes if c & 0x80]

    def __repr__(self):
        def mac(a):
            return ":".join("%02x" % x for x in a) if a else "-"
        s = "%s%s to %s" % (self.name, "" if self.fcs_ok else " (FCS WRONG)", mac(self.addr1))
        if self.addr2:
            s += " from %s" % mac(self.addr2)
        if self.type != CTRL and self.seq is not None:
            s += " seq %d" % self.seq
        if E_SSID in self.elements:
            s += " ssid %r" % self.elements[E_SSID].decode("latin1")
        return s + ", %d octets, duration %d us" % (len(self.octets), self.duration)


# ---------------------------------------------------------------------------------------------- checks
def check(verbose=True):
    failed = 0

    def say(ok, what, detail=""):
        nonlocal failed
        failed += 0 if ok else 1
        if verbose:
            print("  %s %-58s %s" % ("ok  " if ok else "FAIL", what, detail))

    # the CRC-32 check value ("123456789" -> CBF43926) and the residue of a frame with its FCS
    say(zlib.crc32(b"123456789") == 0xCBF43926, "CRC-32 check value")
    a = ack(bytes.fromhex("0012 3456 789a"))
    say(len(a) == 14 and a[0] == 0xD4 and fcs_ok(a) and zlib.crc32(a) == 0x2144DF1C, "ACK: 14 octets, FCS, CRC residue")
    ap, sta = bytes.fromhex("02 00 00 00 00 01"), bytes.fromhex("02 00 00 00 00 02")
    b = Frame(beacon(ap, b"stat-sim", 6, timestamp_us=123456, seq=7))
    say(b.ok and b.name == "beacon" and b.addr1 == BROADCAST and b.addr2 == ap and b.addr3 == ap and b.seq == 7
        and b.fixed["timestamp"] == 123456 and b.fixed["interval"] == 100 and b.elements[E_SSID] == b"stat-sim"
        and b.elements[E_DS] == b"\x06" and b.rates() == ([6, 9, 12, 18, 24, 36, 48, 54], [6, 12, 24]), "beacon builds and parses", repr(b))
    p = Frame(probe_request(sta, b"stat-sim", seq=1))
    say(p.ok and p.name == "probe request" and p.addr2 == sta and p.elements[E_SSID] == b"stat-sim", "probe request", repr(p))
    r = Frame(probe_response(ap, sta, b"stat-sim", 6, 44, seq=2))
    say(r.ok and r.name == "probe response" and r.addr1 == sta and r.duration == 44, "probe response", repr(r))
    au = Frame(authentication(ap, sta, ap, 1, 44, seq=3))
    say(au.ok and au.fixed == {"algorithm": 0, "transaction": 1, "status": 0}, "authentication", repr(au))
    aq = Frame(association_request(ap, sta, b"stat-sim", 44, seq=4))
    ar = Frame(association_response(ap, sta, 1, 44, seq=5))
    say(aq.ok and ar.ok and ar.fixed["aid"] == 0xC001 and ar.fixed["status"] == 0, "association request and response", repr(ar))
    d = Frame(data(ap, sta, ap, llc_snap(0x0800, b"payload"), 44, to_ds=True, seq=6))
    say(d.ok and d.name == "data" and d.addr1 == ap and d.addr2 == sta and d.addr3 == ap and d.flags & TO_DS
        and d.body.endswith(b"payload"), "data frame to the access point", repr(d))
    bad = bytearray(d.octets)
    bad[30] ^= 1
    say(not Frame(bad).ok, "a flipped bit fails the FCS")
    say([ack_rate(r) for r in OFDM_RATES] == [6, 6, 12, 12, 24, 24, 24, 24], "ACK rate for each data rate")
    t5, t24 = Timing("5"), Timing("2.4")
    say(abs(t5.sifs - 16e-6) < 1e-12 and abs(t5.difs - 34e-6) < 1e-12 and abs(t24.sifs - 10e-6) < 1e-12
        and abs(t24.difs - 28e-6) < 1e-12 and abs(t24.response_gap() - 16e-6) < 1e-12, "SIFS, DIFS and the response gap in both bands")
    say(abs(t5.txtime(6, 14) - 44e-6) < 1e-12 and abs(t5.txtime(24, 14) - 28e-6) < 1e-12, "an ACK lasts 44 us at 6 Mb/s, 28 us at 24")
    return failed


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "check":
        n = check()
        print("%d failed" % n if n else "all passed")
        sys.exit(1 if n else 0)
    print(__doc__)
