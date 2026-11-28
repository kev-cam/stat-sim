#!/usr/bin/env python3
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# SPDX-FileCopyrightText: 2026 D. Kevin Cameron
# Part of stat-sim. PolyForm Noncommercial License 1.0.0; commercial use needs a separate license (see LICENSE, COMMERCIAL.md).
"""
wiphy_pair.py -- bladeRF-wiphy's complete modem (wlan_top) in nvc, on a wire with frames from the
reference transmitter (../wifi_phy.py) or with a second copy of itself, and everything it puts on the
wire judged by the reference receiver and MAC (../wifi_mac.py).  The bench is wiphy_pair_tb.vhd.

    wiphy_pair.py [options] ack | send | defer | pair | levels | all

    ack     reference frames at every rate to the modem's address, and frames it must not answer:
            the acknowledgements, their timing, what its host is handed
    send    its host sends: a broadcast, a frame nobody answers (retries, status), one that is answered
    defer   its host has a frame while the wire is busy: when it starts
    pair    two modems: one sends to the other, which acknowledges
    levels  one frame at a row of input levels: where the receiver works

    --src DIR         a bladeRF-wiphy checkout (WIPHY_SRC)
    --host-pkg FILE   fifo_readwrite_p.vhd of the bladeRF's hdl (WIPHY_HOST_PKG)
    --nvc-build DIR   an nvc build (NB)
    --work DIR        where the libraries and the runs go
    --keep            do not rebuild the libraries

Times are in microseconds from the start of the simulation; the wire carries 20 MS/s samples on the
modem's 40 MHz clock.  A frame "ends" where its last OFDM symbol does.
"""
import argparse
import os
import shutil
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
import wifi_mac
import wifi_phy
import wiphy_build

DUT_MAC = bytes.fromhex("70b3d57d8001")      # wlan_rx.vhd gives its framer this address (bss_mac)
TESTER = bytes.fromhex("020000000002")
OTHER = bytes.fromhex("020000000077")
BROADCAST = b"\xff" * 6
RATES = (6, 9, 12, 18, 24, 36, 48, 54)
US = 40                                      # clocks in a microsecond


def mac(a):
    return ":".join("%02x" % x for x in a)


def nominal_samples(rate, octets):
    return 320 + 80 * (1 + wifi_phy.data_symbol_count(rate, octets))


class Burst:
    """One transmission on the wire.  who: a station's number, or "ref" for an injected frame."""

    def __init__(self, who, c0, x, known=None):
        self.who, self.c0, self.n = who, c0, len(x)
        if known is not None:
            self.rate, self.psdu, self.evm = known[0], known[1], None
            self.rx = None
            self.ok = True
        else:
            rms = float(np.sqrt(np.mean(np.abs(x[:160]) ** 2))) or 1.0
            self.rx = wifi_phy.decode(np.concatenate((np.zeros(60), x / rms, np.zeros(240))))
            self.ok = self.rx.ok
            self.rate, self.psdu = self.rx.rate, self.rx.psdu
            self.evm = self.rx.evm_db
            self.rms = rms
        self.frame = wifi_mac.Frame(self.psdu) if self.ok else None
        self.nominal = nominal_samples(self.rate, len(self.psdu)) if self.ok else self.n

    @property
    def start(self):
        return self.c0 / US

    @property
    def end(self):
        """Where the last OFDM symbol of the frame ends (by its SIGNAL field, not by the samples sent)."""
        return (self.c0 + 2 * self.nominal) / US

    def __repr__(self):
        who = "ref  " if self.who == "ref" else "sta %d" % self.who
        if not self.ok:
            return "%9.2f  %s  %d samples, not decoded: %s" % (self.start, who, self.n, self.rx.why)
        s = "%9.2f  %s  %2g Mb/s  %s" % (self.start, who, self.rate, self.frame)
        if self.who != "ref":
            s += "  [EVM %.0f dB" % self.evm
            if abs(self.n - self.nominal) > 2:
                s += ", %d samples where the frame is %d" % (self.n, self.nominal)
            s += "]"
        return s


class HostPacket:
    """What a modem handed its host: a received frame (kind 1) or a transmit status (2: acknowledged,
    3: not)."""

    def __init__(self, clk, words):
        self.clk, self.words = clk, words
        self.kind = words[0] & 0xFFFF
        self.rate = RATES[(words[0] >> 24) & 0xF] if ((words[0] >> 24) & 0xF) < 8 else None
        self.cookie = self.octets = None
        if self.kind == 1:
            self.length = words[1] & 0xFFFF
            raw = b"".join(w.to_bytes(4, "little") for w in words[4:])
            self.octets = raw[:self.length]
            self.frame = wifi_mac.Frame(self.octets)
        else:
            self.cookie = words[1]

    @property
    def t(self):
        return self.clk / US

    def __repr__(self):
        if self.kind == 1:
            return "%9.2f  host: received at %s Mb/s: %s%s" % (
                self.t, self.rate, self.frame, "" if len(self.octets) == self.length else "  (SHORT: %d of %d octets)" % (len(self.octets), self.length))
        return "%9.2f  host: transmit status %d (%s), cookie %d, rate %s Mb/s" % (
            self.t, self.kind, {2: "acknowledged", 3: "no acknowledgement"}.get(self.kind, "?"), self.cookie, self.rate)


class Scenario:
    def __init__(self, stations=1, gain=2.17, noise=2.0, level=1000.0):
        self.stations, self.gain, self.noise, self.level = stations, gain, noise, level
        self.injected = []               # (c0, samples, rate, psdu)
        self.scripts = [[] for _ in range(stations)]
        self.mutes = []

    @staticmethod
    def clk(t_us):
        return 2 * int(round(t_us * US / 2))

    def inject(self, t_us, psdu, rate, level=None):
        """A reference frame on the wire, its first sample at t_us.  Returns the time its last symbol ends."""
        x = wifi_phy.encode(psdu, rate).samples() * (self.level if level is None else level)
        c0 = self.clk(t_us)
        self.injected.append((c0, x, rate, bytes(psdu)))
        return (c0 + 2 * nominal_samples(rate, len(psdu))) / US

    def send(self, station, t_us, rate, frame, cookie=0):
        """Station's host hands its modem a frame (without the FCS) at t_us."""
        self.scripts[station].append((self.clk(t_us), RATES.index(rate), cookie, bytes(frame)))

    def mute(self, frm, to, t0_us, t1_us):
        """Cut the wire from `frm` (a station, or "ref") to station `to` between the two times."""
        self.mutes.append((self.stations if frm == "ref" else frm, to, self.clk(t0_us), self.clk(t1_us)))

    def run(self, build, run_us, name="run"):
        d = os.path.join(build.work, name)
        os.makedirs(d, exist_ok=True)
        for s in range(self.stations):
            with open(os.path.join(d, "sta%d.script" % s), "w") as f:
                for c, r, cookie, frame in sorted(self.scripts[s]):
                    f.write("%d %d %d %s\n" % (c, r, cookie, " ".join("%02X" % o for o in frame)))
        air = {}
        for c0, x, _, _ in self.injected:
            for k, v in enumerate(x):
                air[c0 + 2 * k] = air.get(c0 + 2 * k, 0) + v
        with open(os.path.join(d, "inject.csv"), "w") as f:
            for c in sorted(air):
                f.write("%d %d %d\n" % (c, int(round(air[c].real)), int(round(air[c].imag))))
        with open(os.path.join(d, "mute.txt"), "w") as f:
            for m in self.mutes:
                f.write("%d %d %d %d\n" % m)
        for n in ("air.log",) + tuple("sta%d.log" % s for s in range(self.stations)):
            if os.path.exists(os.path.join(d, n)):
                os.remove(os.path.join(d, n))
        build.elaborate("wiphy_pair_tb", "-gSTATIONS=%d" % self.stations, "-gRUN_CLOCKS=%d" % int(run_us * US),
                        "-gGAIN_M=%d" % round(self.gain * 1000), "-gNOISE_M=%d" % round(self.noise * 1000))
        t0 = time.time()
        code, out = build.simulate("wiphy_pair_tb", d)
        took = time.time() - t0
        bad = [l for l in out.splitlines() if ("rror" in l or "atal" in l or "ailure" in l) and "End of Simulation" not in l]
        if code != 0 or bad:
            keep = [l for l in out.splitlines() if l.strip() and "metavalue" not in l and "LUT" not in l
                    and "wlan_dsss_p_norm" not in l and "numeric_std-body" not in l]
            raise SystemExit("simulation of %s stopped (exit %d):\n%s" % (name, code, "\n".join(keep[-25:])))
        return Result(self, d, took, run_us)


class Result:
    def __init__(self, sc, d, took, run_us):
        self.dir, self.took, self.run_us = d, took, run_us
        per = {}
        self.ota = []
        for l in open(os.path.join(d, "air.log")):
            t = l.split()
            if t[0] == "T":
                per.setdefault(int(t[1]), []).append((int(t[2]), int(t[3]), int(t[4])))
            elif t[0] == "O":
                self.ota.append((int(t[2]) / US, int(t[1]), int(t[3])))
        self.bursts = [Burst("ref", c0, x, known=(rate, psdu)) for c0, x, rate, psdu in sc.injected]
        for s, rows in per.items():
            at = 0
            while at < len(rows):
                end = at
                while end + 1 < len(rows) and rows[end + 1][0] - rows[end][0] <= 4:
                    end += 1
                seg = rows[at:end + 1]
                x = np.array([complex(i, q) for _, i, q in seg])
                nz = np.nonzero(np.abs(x) > 0)[0]
                if len(nz):
                    self.bursts.append(Burst(s, seg[nz[0]][0], x[nz[0]:nz[-1] + 1]))
                at = end + 1
        self.bursts.sort(key=lambda b: b.c0)
        self.host = []
        for s in range(sc.stations):
            pk, cur = [], None
            for l in open(os.path.join(d, "sta%d.log" % s)):
                t = l.split()
                if t[0] != "RX":
                    continue
                if t[2] == "1" or cur is None:
                    cur = [int(t[1]), []]
                cur[1].append(int(t[4], 16))
                if t[3] == "1":
                    pk.append(HostPacket(cur[0], cur[1]))
                    cur = None
            self.host.append(pk)

    def after(self, burst, who=None, within_us=400.0):
        """The first transmission that starts after `burst` ends (from `who`, if given)."""
        for b in self.bursts:
            if b.c0 > burst.c0 and b.start >= burst.end - 1.0 and b.start <= burst.end + within_us and (who is None or b.who == who):
                return b
        return None

    def timeline(self, limit=60):
        rows = [(b.c0, repr(b)) for b in self.bursts]
        for s, pk in enumerate(self.host):
            rows += [(p.clk, repr(p).replace("host:", "host %d:" % s)) for p in pk]
        rows.sort()
        return "\n".join("    " + r for _, r in rows[:limit])


# ------------------------------------------------------------------------------------------- the checks
class Report:
    def __init__(self):
        self.lines = []
        self.failed = 0

    def add(self, ok, name, detail):
        self.lines.append("%-5s %-16s %s" % ("PASS" if ok else ("FAIL" if ok is False else "NOTE"), name, detail))
        if ok is False:
            self.failed += 1
        print(self.lines[-1])
        sys.stdout.flush()


def whole_frames(rep, res, name="whole frames"):
    """Every frame the modem sent has all its OFDM symbols: the count that its SIGNAL field implies."""
    mine = [b for b in res.bursts if b.who != "ref" and b.ok]
    short = [b for b in mine if b.nominal - b.n >= 40]
    if not mine:
        return
    detail = "%d frame(s) sent, all with the symbols their length calls for" % len(mine)
    if short:
        detail = "%d of %d frame(s) a symbol short: %s (16 + 8 x octets + 6 tail bits need one symbol more than 16 + 8 x octets)" % (
            len(short), len(mine), ", ".join(sorted(set("%d octets at %g Mb/s" % (len(b.psdu), b.rate) for b in short))))
    rep.add(not short, name, detail)


def to_dut(octets, seq=1, frm=TESTER, to=DUT_MAC, payload=None):
    """A data frame for the modem, `octets` long with its FCS, from a station to its access point."""
    rng = np.random.default_rng(100 + seq)
    body = bytes(rng.integers(0, 256, octets - 28, dtype=np.uint8)) if payload is None else payload
    return wifi_mac.data(to, frm, to, body, 44, to_ds=True, seq=seq)


def run_ack(build, rep, verbose):
    sc = Scenario(stations=1)
    t = 300.0
    cases = []
    for k, rate in enumerate(RATES):
        psdu = to_dut(100, seq=k + 1)
        cases.append(("ack %g" % rate, t, psdu, rate, True))
        t = sc.inject(t, psdu, rate) + 160.0
    extra = [("other address", wifi_mac.data(OTHER, TESTER, OTHER, b"\x55" * 40, 44, to_ds=True, seq=20), 24, False),
             ("broadcast", wifi_mac.data(BROADCAST, TESTER, DUT_MAC, b"\x66" * 40, 0, seq=21), 24, False),
             ("bad FCS", to_dut(100, seq=22)[:-1] + b"\x00", 24, False),
             ("probe request", wifi_mac.probe_request(TESTER, b"net", seq=23)[:4] + DUT_MAC + wifi_mac.probe_request(TESTER, b"net", seq=23)[10:-4], 6, True),
             ("long frame", to_dut(1536, seq=24), 54, True),
             ("shortest data", to_dut(28, seq=25), 54, True)]
    for name, psdu, rate, expect in extra:
        if name == "probe request":
            psdu = psdu + wifi_mac.fcs(psdu)
        cases.append((name, t, psdu, rate, expect))
        t = sc.inject(t, psdu, rate) + 160.0
    rts = wifi_mac.finish(wifi_mac.header(wifi_mac.CTRL, wifi_mac.RTS, DUT_MAC, TESTER, duration=200))
    t_rts = t
    t = sc.inject(t, rts, 24) + 160.0
    res = sc.run(build, t + 100.0, "ack")
    if verbose:
        print(res.timeline())
    refs = {b.c0: b for b in res.bursts if b.who == "ref"}
    gaps, rates_used = [], set()
    for name, t0, psdu, rate, expect in cases:
        ref = refs[Scenario.clk(t0)]
        nxt = res.after(ref, who=0, within_us=120.0)
        got = [p for p in res.host[0] if p.kind == 1 and p.octets == psdu]
        if expect:
            ok = nxt is not None and nxt.ok and nxt.frame.fcs_ok and nxt.frame.name == "ACK" and nxt.frame.addr1 == psdu[10:16]
            detail = "no acknowledgement" if nxt is None else repr(nxt).split("  ", 2)[-1].strip()
            if ok:
                gap = nxt.start - ref.end
                gaps.append(gap)
                rates_used.add(nxt.rate)
                detail = "ACK at %g Mb/s, %.2f us after the frame; host got the frame: %s" % (nxt.rate, gap, "yes" if got else "NO")
                ok = bool(got)
            rep.add(ok, name, detail)
        else:
            rep.add(nxt is None, name, ("nothing sent" if nxt is None else "SENT " + repr(nxt).split("  ", 2)[-1].strip())
                    + "; host got the frame: %s" % ("yes" if got else "no"))
    if gaps:
        rep.add(all(abs(g - 16.0) <= 0.9 for g in gaps), "sifs",
                "acknowledgements start %.2f to %.2f us after the frame (16 us, +-0.9)" % (min(gaps), max(gaps)))
        want = sorted(set(wifi_mac.ack_rate(r) for r in RATES))
        rep.add(None, "ack rate", "always %s Mb/s (with 6, 12 and 24 basic the standard asks for %s by the frame's rate)"
                % ("/".join("%g" % r for r in sorted(rates_used)), "/".join("%g" % r for r in want)))
    cts = res.after(refs[Scenario.clk(t_rts)], who=0, within_us=120.0)
    cts_ok = cts is not None and cts.ok and cts.frame.fcs_ok and cts.frame.name == "CTS" and cts.frame.addr1 == TESTER
    rep.add(cts_ok, "rts", ("CTS %.2f us after the RTS" % (cts.start - refs[Scenario.clk(t_rts)].end)) if cts_ok
            else ("an RTS to it gets " + ("no answer" if cts is None else repr(cts).split("  ", 2)[-1].strip()) + " (a CTS is due)"))
    whole_frames(rep, res)
    return res


def run_send(build, rep, verbose):
    # pass 1: what the modem does with nobody answering
    def scenario():
        sc = Scenario(stations=1)
        bc = wifi_mac.data(BROADCAST, DUT_MAC, DUT_MAC, b"hello, everybody" * 3, 0, from_ds=True, seq=1)[:-4]
        uni = wifi_mac.data(TESTER, DUT_MAC, DUT_MAC, bytes(range(60)), 44, from_ds=True, seq=2)[:-4]
        uni2 = wifi_mac.data(TESTER, DUT_MAC, DUT_MAC, bytes(range(100, 172)), 44, from_ds=True, seq=3)[:-4]
        sc.send(0, 300.0, 12, bc, cookie=11)
        sc.send(0, 900.0, 24, uni, cookie=22)
        sc.send(0, 2600.0, 36, uni2, cookie=33)
        return sc, bc, uni, uni2
    sc, bc, uni, uni2 = scenario()
    res = sc.run(build, 3600.0, "send1")
    if verbose:
        print(res.timeline())
    mine = [b for b in res.bursts if b.who == 0]
    b_bc = [b for b in mine if b.ok and b.psdu[:-4] == bc]
    rep.add(len(b_bc) == 1 and b_bc[0].frame.fcs_ok and b_bc[0].rate == 12, "broadcast",
            "sent %d time(s)%s" % (len(b_bc), (", at %g Mb/s, FCS right, %.2f us after its host gave it" % (b_bc[0].rate, b_bc[0].start - 300.0)) if b_bc else ""))
    def same(b, f):
        return b.ok and b.psdu[:1] == f[:1] and b.psdu[2:-4] == f[2:] and (b.psdu[1] & ~0x08) == f[1]
    tries = [b for b in mine if same(b, uni)]
    st = [p for p in res.host[0] if p.kind in (2, 3) and p.cookie == 22]
    detail = "%d transmission(s)" % len(tries)
    if tries:
        detail += ": " + ", then ".join("%g Mb/s%s" % (b.rate, " (retry bit)" if b.psdu[1] & 0x08 else "") for b in tries)
        if len(tries) > 1:
            detail += "; %.1f us from the end of one to the start of the next" % (tries[1].start - tries[0].end)
    detail += "; host told: %s" % (", ".join({2: "acknowledged", 3: "no acknowledgement"}[p.kind] for p in st) or "nothing")
    rep.add(len(tries) >= 2 and all(b.psdu[1] & 0x08 for b in tries[1:]) and not (tries[0].psdu[1] & 0x08)
            and len(st) == 1 and st[0].kind == 3, "no answer", detail)
    rep.add(None, "retry limit", "%d transmissions of an unanswered frame (the standard's default is 7 for a short frame)" % len(tries))
    whole_frames(rep, res)
    # pass 2: the same, with the third frame acknowledged where pass 1 shows it
    third = [b for b in mine if same(b, uni2)]
    if not third:
        rep.add(False, "answered", "the frame was not sent in the first pass")
        return res
    sc2, _, _, _ = scenario()
    sc2.inject(third[0].end + 16.0, wifi_mac.ack(DUT_MAC), 24)
    res2 = sc2.run(build, 3600.0, "send2")
    if verbose:
        print(res2.timeline())
    tries2 = [b for b in res2.bursts if b.who == 0 and same(b, uni2)]
    st2 = [p for p in res2.host[0] if p.kind in (2, 3) and p.cookie == 33]
    rep.add(len(tries2) == 1 and len(st2) == 1 and st2[0].kind == 2, "answered",
            "acknowledged 16 us after its end: sent %d time(s); host told: %s" % (
                len(tries2), ", ".join({2: "acknowledged", 3: "no acknowledgement"}[p.kind] for p in st2) or "nothing"))
    return res2


def run_defer(build, rep, verbose):
    sc = Scenario(stations=1)
    busy = to_dut(400, seq=1, to=OTHER)                        # 6 Mb/s: over half a millisecond
    end = sc.inject(300.0, busy, 6)
    f1 = wifi_mac.data(BROADCAST, DUT_MAC, DUT_MAC, b"\x11" * 40, 0, from_ds=True, seq=5)[:-4]
    f2 = wifi_mac.data(BROADCAST, DUT_MAC, DUT_MAC, b"\x22" * 40, 0, from_ds=True, seq=6)[:-4]
    f3 = wifi_mac.data(BROADCAST, DUT_MAC, DUT_MAC, b"\x33" * 40, 0, from_ds=True, seq=7)[:-4]
    sc.send(0, 450.0, 24, f1, cookie=1)                        # while the wire is busy
    sc.send(0, 450.0, 24, f2, cookie=2)                        # and a second behind it
    sc.send(0, end + 700.0, 24, f3, cookie=3)                  # when it has long been idle
    res = sc.run(build, end + 1100.0, "defer")
    if verbose:
        print(res.timeline())
    mine = [b for b in res.bursts if b.who == 0 and b.ok]
    b1 = [b for b in mine if b.psdu[:-4] == f1]
    b2 = [b for b in mine if b.psdu[:-4] == f2]
    b3 = [b for b in mine if b.psdu[:-4] == f3]
    if b1:
        gap = b1[0].start - end
        rep.add(gap >= 34.0 - 0.9, "defer", "frame handed over while the wire was busy starts %.2f us after the busy frame ends "
                "(DIFS is 34 us, and a backoff of 0 to 15 slots of 9 us follows it)" % gap)
    else:
        rep.add(False, "defer", "the frame was not sent")
    if b1 and b2:
        gap = b2[0].start - b1[0].end
        rep.add(gap >= 34.0 - 0.9, "own next", "its next frame starts %.2f us after its own (DIFS and a backoff: 34 us at least)" % gap)
    if b3:
        rep.add(None, "idle access", "a frame handed over on an idle wire starts %.2f us later" % (b3[0].start - (end + 700.0)))
    if not b3:
        return res
    # A frame that waits while the wire turns busy AGAIN: the host hands over two frames, the first is
    # acknowledged 16 us after its end (which is busy wire to the second, whose first wait has run out by
    # then).  The first starts as on any idle wire, so the acknowledgement can be put in place beforehand.
    lead = b3[0].c0 - Scenario.clk(end + 700.0)
    sc = Scenario(stations=1)
    pairs = []
    for k, t in enumerate((300.0, 2100.0, 3900.0, 5700.0)):
        g1 = wifi_mac.data(TESTER, DUT_MAC, DUT_MAC, bytes(range(60)), 44, from_ds=True, seq=10 + 2 * k)[:-4]
        g2 = wifi_mac.data(TESTER, DUT_MAC, DUT_MAC, bytes(range(60, 120)), 44, from_ds=True, seq=11 + 2 * k)[:-4]
        sc.send(0, t, 24, g1, cookie=100 + k)
        sc.send(0, t, 24, g2, cookie=200 + k)
        end1 = (Scenario.clk(t) + lead + 2 * nominal_samples(24, len(g1) + 4)) / US
        pairs.append((g1, g2, end1, sc.inject(end1 + 16.0, wifi_mac.ack(DUT_MAC), 24)))
    res2 = sc.run(build, 7500.0, "defer2")
    if verbose:
        print(res2.timeline())
    mine = [b for b in res2.bursts if b.who == 0 and b.ok]
    waits, placed = [], True
    for g1, g2, end1, ack_end in pairs:
        first = [b for b in mine if b.psdu[2:-4] == g1[2:]]
        second = [b for b in mine if b.psdu[2:-4] == g2[2:]]
        placed = placed and len(first) == 1 and abs(first[0].end - end1) < 0.05
        if second:
            waits.append(second[0].start - ack_end)
    if not placed or len(waits) != len(pairs):
        rep.add(False, "backoff", "the scenario did not come out as planned (first frames not where expected, or a second frame missing)")
    else:
        ok = all(34.0 - 0.9 <= w <= 34.0 + 15 * 9.0 + 0.9 for w in waits)
        rep.add(ok, "backoff", "with a frame waiting, the wire turns busy again (the ACK of the frame before it): it starts %s us after that ACK "
                "(DIFS and 0 to 15 slots: 34 to 169 us)" % ", ".join("%.2f" % w for w in waits))
    return res


def run_pair(build, rep, verbose):
    sc = Scenario(stations=2)
    f = wifi_mac.data(DUT_MAC, DUT_MAC, DUT_MAC, bytes(range(80)), 44, seq=9)[:-4]
    sc.send(0, 300.0, 36, f, cookie=7)
    res = sc.run(build, 1300.0, "pair")
    if verbose:
        print(res.timeline())
    sent = [b for b in res.bursts if b.who == 0 and b.ok and b.psdu[2:-4] == f[2:]]
    acks = [b for b in res.bursts if b.who == 1 and b.ok and b.frame.name == "ACK"]
    st = [p for p in res.host[0] if p.kind in (2, 3)]
    got = [p for p in res.host[1] if p.kind == 1 and p.octets[:-4] == f]
    detail = "sent %d time(s); the other acknowledged %d time(s)" % (len(sent), len(acks))
    if sent and acks:
        detail += ", %.2f us after the frame" % (acks[0].start - sent[0].end)
    detail += "; the other's host got the frame: %s; sender's host told: %s" % (
        "yes" if got else "NO", ", ".join({2: "acknowledged", 3: "no acknowledgement"}[p.kind] for p in st) or "nothing")
    rep.add(len(sent) == 1 and len(acks) == 1 and bool(got) and len(st) == 1 and st[0].kind == 2, "pair", detail)
    return res


def run_levels(build, rep, verbose):
    """The same 54 Mb/s frame at a row of levels at the ADC (rms, in counts of a 12-bit converter)."""
    sc = Scenario(stations=1)
    levels = (150, 300, 450, 600, 800, 1000, 1200, 1400, 1700, 2000)
    t, at = 300.0, []
    for k, level in enumerate(levels):
        psdu = to_dut(100, seq=40 + k)
        at.append((level, t, psdu))
        t = sc.inject(t, psdu, 54, level=float(level)) + 160.0
    res = sc.run(build, t + 100.0, "levels")
    if verbose:
        print(res.timeline())
    good = [level for level, _, psdu in at if any(p.kind == 1 and p.octets == psdu for p in res.host[0])]
    bad = [level for level, _, _ in at if level not in good]
    rep.add(None, "input level", "a 54 Mb/s frame is received at %s rms and not at %s (a 12-bit converter's full scale is 2047)" % (
        ", ".join(str(v) for v in good) or "no level", ", ".join(str(v) for v in bad) or "none of them"))
    return res


def make_build(a):
    if not a.keep:
        shutil.rmtree(a.work, ignore_errors=True)
    b = wiphy_build.Build(a.src, a.nvc_build, a.work, verbose=not a.keep)
    if not a.keep:
        b.libraries(nuand=[a.host_pkg])
        b.modem()
    b.analyse("wlan", os.path.join(HERE, "wiphy_pair_tb.vhd"), relaxed=True)
    return b


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", choices=("ack", "send", "defer", "pair", "levels", "all"))
    ap.add_argument("--src", default=os.environ.get("WIPHY_SRC"))
    ap.add_argument("--host-pkg", default=os.environ.get("WIPHY_HOST_PKG"))
    ap.add_argument("--nvc-build", default=os.environ.get("NB"))
    ap.add_argument("--work", required=True)
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("-v", "--verbose", action="store_true", help="the timeline of every run")
    a = ap.parse_args()
    if not (a.src and a.host_pkg and a.nvc_build):
        raise SystemExit("needs --src, --host-pkg and --nvc-build (or WIPHY_SRC, WIPHY_HOST_PKG, NB)")
    b = make_build(a)
    rep = Report()
    for name, fn in (("ack", run_ack), ("send", run_send), ("defer", run_defer), ("pair", run_pair), ("levels", run_levels)):
        if a.what in (name, "all"):
            t0 = time.time()
            fn(b, rep, a.verbose)
            print("      (%s: %.0f s)" % (name, time.time() - t0))
    print("%d check(s) failed" % rep.failed if rep.failed else "all checks passed")
    return 1 if rep.failed else 0


if __name__ == "__main__":
    sys.exit(main())
