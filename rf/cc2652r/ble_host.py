#!/usr/bin/env python3
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# SPDX-FileCopyrightText: 2026 D. Kevin Cameron
# Part of stat-sim. PolyForm Noncommercial License 1.0.0; commercial use needs a separate license (see LICENSE, COMMERCIAL.md).
"""
ble_host.py -- a Bluetooth LE controller round the CC2652R model, driven by a host's HCI commands,
and an arena that puts several of them in the same air.

The chip's data sheet stops at the antenna pin and the packet; what a program does with the chip is
the Bluetooth Core Specification's: the host gives the controller commands (Vol 4 Part E, HCI) and
the controller's link layer (Vol 6 Part B) turns them into packets at the right times and channels.
Modelled, with the command names and parameter units of the specification:

    le_set_advertising_parameters / _data / le_set_scan_response_data / le_set_advertising_enable
        legacy advertising: ADV_IND, ADV_SCAN_IND or ADV_NONCONN_IND on channels 37, 38, 39 every
        advInterval + advDelay (0 - 10 ms, random); SCAN_RSP to a SCAN_REQ addressed to it
    le_set_scan_parameters / le_set_scan_enable
        passive or active scanning, scanWindow of every scanInterval, the channel stepping 37, 38, 39;
        each advertisement heard is an LE Advertising Report event (address, data, RSSI) in .events
    le_transmitter_test / le_receiver_test / le_test_end
        Direct Test Mode on any RF channel and any of the four PHYs: PRBS9 packets, a packet count

Not modelled: connections (CONNECT_IND is ignored), extended advertising, directed advertising, the
scanner's backoff, filter policies, privacy.  Status of what is here: command names, PDU types and
payloads were read from the specification (Core 6.1) on 2026-11-24; advInterval / advDelay, T_IFS,
the HCI parameter encodings and the test packet interval are from recollection (ble_phy.py marks them).

    ble_host.py range [--phy 1m] [--dist 10 30 100 ...]   packet error rate against distance, test mode
    ble_host.py scan                                      an advertiser, an active scanner and a neighbour
"""
import argparse
import heapq
import math
import sys

import numpy as np

import ble_phy as ble
from cc2652r import CC2652R, RX, dbm_to_w, w_to_dbm

C0 = 299792458.0
SLOT = 625e-6                                # HCI time unit, s
ADV_PDU_OF_HCI = {0: ble.ADV_IND, 2: ble.ADV_SCAN_IND, 3: ble.ADV_NONCONN_IND}      # HCI Advertising_Type -> PDU
REPORT_OF_PDU = {ble.ADV_IND: 0, ble.ADV_SCAN_IND: 2, ble.ADV_NONCONN_IND: 3, ble.SCAN_RSP: 4}
TEST_PHY = {1: "1m", 2: "2m", 3: "s8", 4: "s2"}                                     # LE Transmitter Test PHY codes
ADV_SPACING = 1.5e-3                         # s between the PDUs of one advertising event (mine; the limit is 10 ms)


class Transmission:
    def __init__(self, node, t, phy, pdu, freq, channel, access_address=ble.ADV_ACCESS_ADDRESS):
        self.node, self.t, self.phy, self.pdu, self.freq, self.channel = node, t, phy, pdu, freq, channel
        self.access_address = access_address
        self.end = t + ble.packet_duration(phy, len(pdu))
        self.env = None

    def envelope(self):
        if self.env is None:
            r = self.node.radio
            r.phy, r.frequency = self.phy, self.freq
            self.carrier = r.carrier
            self.env = r.transmit(ble.packet_symbols(self.phy, self.pdu, self.channel, self.access_address))
        return self.env

    def __lt__(self, other):
        return self.end < other.end


class Controller:
    """One Bluetooth LE controller: link layer and a CC2652R.  address: "C1:A2:A3:A4:A5:A6"."""

    def __init__(self, name, address, position=(0.0, 0.0, 0.0), antenna_gain_dbi=0.0, seed=0, fs=16e6):
        self.name = name
        self.address = ble.address_octets(address)
        self.position = np.array(position, float)
        self.antenna_gain_dbi = antenna_gain_dbi
        self.radio = CC2652R(name, seed=seed, fs=fs)
        self.rng = np.random.default_rng(seed + 77)
        self.events = []                     # HCI events, as dicts
        self.adv = dict(enable=False, interval=0x0800 * SLOT, type=0, channel_map=7, data=b"", scan_rsp=b"")
        self.scan = dict(enable=False, active=False, interval=0x0010 * SLOT, window=0x0010 * SLOT, t0=0.0)
        self.test = None                     # Direct Test Mode: dict(tx=bool, freq, phy, length, count)
        self.sent = []                       # this node's transmissions
        self.listen = []                     # (t0, t1, channel index): the advertiser waiting for a SCAN_REQ
        self.stats = dict(adv=0, scan_req=0, scan_rsp=0, crc_errors=0)

    # ---- HCI commands -----------------------------------------------------------------------
    def set_tx_power(self, dbm):
        """Transmit power (a vendor command on this chip, HCI_EXT_SetTxPower); returns what is set."""
        self.radio.tx_power = self.radio.tx_power_legal(dbm)
        return self.radio.tx_power

    def le_set_advertising_parameters(self, interval_min=0x0800, interval_max=0x0800, advertising_type=0, channel_map=7):
        if advertising_type not in ADV_PDU_OF_HCI:
            raise ValueError("advertising type %d is not modelled" % advertising_type)
        if not 0x0020 <= interval_min <= interval_max <= 0x4000 or not 1 <= channel_map <= 7:
            raise ValueError("invalid HCI command parameters")
        self.adv.update(interval=interval_min * SLOT, type=advertising_type, channel_map=channel_map)

    def le_set_advertising_data(self, data):
        if len(data) > 31:
            raise ValueError("advertising data is at most 31 octets")
        self.adv["data"] = bytes(data)

    def le_set_scan_response_data(self, data):
        if len(data) > 31:
            raise ValueError("scan response data is at most 31 octets")
        self.adv["scan_rsp"] = bytes(data)

    def le_set_advertising_enable(self, enable):
        self.adv["enable"] = bool(enable)

    def le_set_scan_parameters(self, le_scan_type=0, le_scan_interval=0x0010, le_scan_window=0x0010):
        if not 0x0004 <= le_scan_window <= le_scan_interval <= 0x4000:
            raise ValueError("invalid HCI command parameters")
        self.scan.update(active=bool(le_scan_type), interval=le_scan_interval * SLOT, window=le_scan_window * SLOT)

    def le_set_scan_enable(self, le_scan_enable, filter_duplicates=False):
        self.scan.update(enable=bool(le_scan_enable), duplicates=not filter_duplicates, seen=set())

    def le_transmitter_test(self, tx_channel, test_data_length, packet_payload=0, phy=1):
        self.test = dict(tx=True, freq=ble.rf_channel_frequency(tx_channel), phy=TEST_PHY[phy],
                         pdu=ble.test_pdu(test_data_length, packet_payload), count=0)

    def le_receiver_test(self, rx_channel, phy=1):
        self.test = dict(tx=False, freq=ble.rf_channel_frequency(rx_channel), phy={1: "1m", 2: "2m", 3: "s8"}[phy],
                         count=0, rssi=[])

    def le_test_end(self):
        """Ends the test; returns the number of packets received (0 from a transmitter)."""
        t, self.test = self.test, None
        return 0 if t is None or t["tx"] else t["count"]

    # ---- link layer -------------------------------------------------------------------------
    def schedule(self, t_end):
        """The transmissions this controller makes of its own accord up to t_end."""
        out = []
        if self.test and self.test["tx"]:
            d = ble.packet_duration(self.test["phy"], len(self.test["pdu"]))
            step = math.ceil((d + 249e-6) / SLOT) * SLOT
            for k in range(int(t_end / step)):
                out.append(Transmission(self, k * step, self.test["phy"], self.test["pdu"], self.test["freq"], None,
                                        ble.TEST_ACCESS_ADDRESS))
        if self.adv["enable"]:
            typ = ADV_PDU_OF_HCI[self.adv["type"]]
            pdu = ble.adv_pdu(typ, self.address + self.adv["data"], tx_add=1)
            t = float(self.rng.uniform(0.0, self.adv["interval"]))
            while t < t_end:
                tt = t
                for ch in (37, 38, 39):
                    if self.adv["channel_map"] >> (ch - 37) & 1:
                        tx = Transmission(self, tt, "1m", pdu, ble.channel_frequency(ch), ch)
                        out.append(tx)
                        if typ != ble.ADV_NONCONN_IND:
                            self.listen.append((tx.end, tx.end + ble.T_IFS + 300e-6, ch))
                        tt += ADV_SPACING
                t += self.adv["interval"] + float(self.rng.uniform(0.0, 10e-3))
        return out

    def listening(self, t0, t1):
        """The (phy, frequency, channel index, access address) this controller receives on throughout
        t0 .. t1, or None."""
        if any(tx.t < t1 and tx.end > t0 for tx in self.sent):
            return None                      # one radio: not while it transmits
        if self.test and not self.test["tx"]:
            return (self.test["phy"], self.test["freq"], None, ble.TEST_ACCESS_ADDRESS)
        for a, b, ch in self.listen:
            if a <= t0 and t1 <= b:
                return ("1m", ble.channel_frequency(ch), ch, ble.ADV_ACCESS_ADDRESS)
        s = self.scan
        if s["enable"]:
            k0, k1 = int(t0 // s["interval"]), int(t1 // s["interval"])
            if k0 == k1 and t1 - k0 * s["interval"] <= s["window"]:
                ch = 37 + k0 % 3
                return ("1m", ble.channel_frequency(ch), ch, ble.ADV_ACCESS_ADDRESS)
        return None

    def received(self, pkt, tx, t_end):
        """Link layer: a packet from the radio.  Returns the transmissions it answers with."""
        if not pkt["crc_ok"]:
            self.stats["crc_errors"] += 1
            return []
        if self.test:
            self.test["count"] += 1
            self.test["rssi"].append(pkt["rssi"])
            return []
        pdu = pkt["pdu"]
        typ, payload = pdu[0] & 15, pdu[2:]
        s = self.scan
        if s["enable"] and typ in REPORT_OF_PDU and len(payload) >= 6:
            if s["duplicates"] or (typ, payload[:6]) not in s["seen"]:
                s["seen"].add((typ, payload[:6]))
                self.events.append(dict(event="LE Advertising Report", time=t_end, event_type=REPORT_OF_PDU[typ],
                                        address_type=pdu[0] >> 6 & 1, address=ble.address_text(payload[:6]),
                                        data=payload[6:], rssi=pkt["rssi"]))
            if s["active"] and typ in (ble.ADV_IND, ble.ADV_SCAN_IND):
                self.stats["scan_req"] += 1
                req = ble.adv_pdu(ble.SCAN_REQ, self.address + payload[:6], tx_add=1, rx_add=pdu[0] >> 6 & 1)
                self.listen.append((t_end + ble.T_IFS + 176e-6, t_end + 2 * ble.T_IFS + 176e-6 + 400e-6, tx.channel))
                return [Transmission(self, t_end + ble.T_IFS, "1m", req, tx.freq, tx.channel)]
        if self.adv["enable"] and typ == ble.SCAN_REQ and payload[6:12] == self.address and self.adv["type"] != 3:
            self.stats["scan_rsp"] += 1
            rsp = ble.adv_pdu(ble.SCAN_RSP, self.address + self.adv["scan_rsp"], tx_add=1)
            return [Transmission(self, t_end + ble.T_IFS, "1m", rsp, tx.freq, tx.channel)]
        return []


class Arena:
    """Controllers in free space.  Every transmission reaches every other controller through Friis
    coupling (amplitude and carrier phase; the propagation delay, under a microsecond per 300 m, is
    left out), and each receiver is given everything on the air while it listens: the packet meant
    for it and whatever overlaps it, on its own channel or beside it."""

    def __init__(self, nodes):
        self.nodes = list(nodes)
        fs = {n.radio.fs for n in self.nodes}
        if len(fs) != 1:
            raise ValueError("the controllers' radios must share a sample rate")
        self.fs = fs.pop()
        self.log = []

    def coupling(self, a, b, freq):
        d = max(float(np.linalg.norm(a.position - b.position)), 0.01)
        lam = C0 / freq
        g = lam / (4.0 * math.pi * d) * 10.0 ** ((a.antenna_gain_dbi + b.antenna_gain_dbi) / 20.0)
        return g * np.exp(-2j * math.pi * d / lam)

    def run(self, duration):
        heap = []
        for n in self.nodes:
            for tx in n.schedule(duration):
                n.sent.append(tx)
                heapq.heappush(heap, tx)
        air = []                             # transmissions that may still overlap one to come
        guard = 40e-6
        while heap:
            tx = heapq.heappop(heap)
            air = [a for a in air if a.end > tx.t - 20e-3] + [tx]
            self.log.append(tx)
            for n in self.nodes:
                if n is tx.node:
                    continue
                t0, t1 = tx.t - guard, tx.end + guard
                rxs = n.listening(tx.t, tx.end)
                if rxs is None or rxs[0] != tx.phy and not (rxs[0] == "s8" and tx.phy == "s2"):
                    continue
                phy, freq, channel, aa = rxs
                r = n.radio
                r.phy, r.frequency = phy, freq
                if abs(tx.freq - freq) > 1e6:
                    continue                 # not the channel it listens on: heard only as interference to others
                nsamp = int(round((t1 - t0) * self.fs))
                env = np.zeros(nsamp, complex)
                blockers = []
                for a in list(air) + [h for h in heap if h.t < t1]:
                    if a.node is n or a.end <= t0 or a.t >= t1:
                        continue
                    e = a.envelope() * self.coupling(a.node, n, a.freq)
                    df = a.carrier - r.carrier
                    if abs(df) > self.fs / 2.0 - 1.5e6:
                        blockers.append((a.freq, w_to_dbm(float(np.mean(np.abs(e) ** 2)))))
                        continue
                    k = int(round((a.t - t0) * self.fs))
                    i0, i1 = max(k, 0), min(k + len(e), nsamp)
                    if i1 > i0:
                        tt = (np.arange(i0, i1)) / self.fs
                        env[i0:i1] += e[i0 - k: i1 - k] * np.exp(2j * math.pi * df * tt)
                want = int(round(guard * self.fs))
                for pkt in r.receive(env, channel=channel, access_address=aa, blockers=blockers):
                    if abs(pkt["start"] - want) <= 2 * r.sps:
                        for answer in n.received(pkt, tx, tx.end):
                            n.sent.append(answer)
                            heapq.heappush(heap, answer)
        return self.log


# ---------------------------------------------------------------------------------------------
def link_budget(tx_dbm, dist, freq=2440e6, gains_dbi=0.0):
    return tx_dbm + gains_dbi + 20.0 * math.log10(C0 / freq / (4.0 * math.pi * dist))


def cmd_range(args):
    phy_code = {"1m": 1, "2m": 2, "s8": 3, "s2": 4}[args.phy]
    d_pkt = ble.packet_duration(args.phy, args.length + 2)
    step = math.ceil((d_pkt + 249e-6) / SLOT) * SLOT
    print("Direct Test Mode, %s, RF channel %d, %d-octet PRBS9 packets, %g dBm, isotropic antennas, free space"
          % (RX[args.phy]["name"], args.channel, args.length, args.power))
    print("data sheet sensitivity %g dBm (BER 1e-3: a %d-octet packet then fails %.0f %% of the time)"
          % (RX[args.phy]["sens"], args.length, 100.0 * (1.0 - (1.0 - 1e-3) ** (8 * (args.length + 5)))))
    print("%9s %12s %10s %10s %8s" % ("distance", "budget dBm", "RSSI dBm", "received", "PER"))
    for dist in args.dist:
        a = Controller("tester", "C0:00:00:00:00:01", seed=1)
        b = Controller("dut", "C0:00:00:00:00:02", position=(dist, 0.0, 0.0), seed=2)
        a.set_tx_power(args.power)
        a.le_transmitter_test(args.channel, args.length, 0, phy_code)
        b.le_receiver_test(args.channel, min(phy_code, 3))
        Arena([a, b]).run(args.packets * step)
        rssi = b.test["rssi"]
        got = b.le_test_end()
        print("%7g m %12.1f %10s %6d/%-4d %7.1f%%" % (dist, link_budget(a.radio.tx_power, dist, ble.rf_channel_frequency(args.channel)),
                                                     "%.1f" % np.mean(rssi) if rssi else "-", got, args.packets,
                                                     100.0 * (1.0 - got / args.packets)))
    return 0


def cmd_scan(args):
    beacon = Controller("beacon", "C1:A2:A3:A4:A5:A6", seed=1)
    beacon.le_set_advertising_parameters(0x00A0, 0x00A0, advertising_type=0)             # 100 ms, ADV_IND
    beacon.le_set_advertising_data(bytes([2, 1, 6, 7, 9]) + b"stat-1")
    beacon.le_set_scan_response_data(bytes([5, 0xFF, 0x0D, 0x00, 1, 2]))
    beacon.le_set_advertising_enable(True)
    other = Controller("neighbour", "C1:00:00:00:00:99", position=(args.dist, 2.0, 0.0), seed=3)
    other.le_set_advertising_parameters(0x0020, 0x0020, advertising_type=3)              # 20 ms, ADV_NONCONN_IND
    other.le_set_advertising_data(bytes(range(31)))
    other.le_set_advertising_enable(True)
    phone = Controller("scanner", "C0:11:22:33:44:55", position=(args.dist, 0.0, 0.0), seed=2)
    phone.le_set_scan_parameters(le_scan_type=1, le_scan_interval=0x0060, le_scan_window=0x0030)   # active, 30 of 60 ms
    phone.le_set_scan_enable(True)
    log = Arena([beacon, other, phone]).run(args.time)
    print("%.1f s: beacon (ADV_IND every 100 ms) at 0 m, a neighbour (ADV_NONCONN_IND every 20 ms) and an active"
          " scanner (30 ms of every 60 ms) at %g m" % (args.time, args.dist))
    print("on the air: %d packets (%s)" % (len(log), ", ".join(
        "%d %s" % (sum(1 for t in log if t.pdu[0] & 15 == k), ble.PDU_NAMES[k]) for k in sorted({t.pdu[0] & 15 for t in log}))))
    for addr in sorted({e["address"] for e in phone.events}):
        ev = [e for e in phone.events if e["address"] == addr]
        kinds = {0: "ADV_IND", 2: "ADV_SCAN_IND", 3: "ADV_NONCONN_IND", 4: "SCAN_RSP"}
        print("  reports from %s: %s; RSSI %.0f dBm (budget %.1f)" % (
            addr, ", ".join("%d %s" % (sum(1 for e in ev if e["event_type"] == k), v) for k, v in kinds.items()
                            if any(e["event_type"] == k for e in ev)),
            np.mean([e["rssi"] for e in ev]),
            link_budget(0.0, float(np.linalg.norm(phone.position - {beacon.address: beacon, other.address: other}[
                ble.address_octets(addr)].position)), 2440e6)))
    print("  scanner: %d SCAN_REQ sent, %d packets with a bad CRC; beacon: %d SCAN_RSP sent"
          % (phone.stats["scan_req"], phone.stats["crc_errors"], beacon.stats["scan_rsp"]))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("range", help="packet error rate against distance in Direct Test Mode")
    p.add_argument("--phy", default="1m", choices=list(RX))
    p.add_argument("--dist", type=float, nargs="+", default=[10.0, 100.0, 300.0, 500.0, 700.0, 1000.0, 1500.0])
    p.add_argument("--packets", type=int, default=200)
    p.add_argument("--length", type=int, default=37)
    p.add_argument("--channel", type=int, default=19)
    p.add_argument("--power", type=float, default=0.0)
    p.set_defaults(fn=cmd_range)
    p = sub.add_parser("scan", help="an advertiser, an active scanner and a neighbour advertising beside them")
    p.add_argument("--dist", type=float, default=10.0)
    p.add_argument("--time", type=float, default=2.0)
    p.set_defaults(fn=cmd_scan)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
