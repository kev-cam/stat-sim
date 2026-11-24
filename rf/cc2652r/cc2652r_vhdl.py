#!/usr/bin/env python3
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# SPDX-FileCopyrightText: 2026 D. Kevin Cameron
# Part of stat-sim. PolyForm Noncommercial License 1.0.0; commercial use needs a separate license (see LICENSE, COMMERCIAL.md).
"""
cc2652r_vhdl.py -- write cc2652r_pkg.vhd: the numbers of the CC2652R model (cc2652r.py) as VHDL.

Everything cc2652r.vhd needs that cc2652r.py works out with numpy is worked out here and written as
constants: the channel filter's taps for each PHY, the symbol timing, the amplitude and the neighbour
taps of the discriminator's output, the Gaussian pulse of the modulator, and the data sheet / model
scalars.  The VHDL model runs at one sample rate for all PHYs (32 MHz: an event of 64 samples is 2 us
and its lines are 500 kHz apart), cc2652r.py's `check` runs the 1 Msym/s PHYs at 16 MHz; the figures
at 32 MHz are within 0.5 dB of those.

Reference packets (ble_phy.py's symbols of one PDU on each PHY) are written too, for tb_cc2652r.vhd.

    cc2652r_vhdl.py [out.vhd]
"""
import sys

import numpy as np

import ble_phy as ble
import cc2652r as cc

FS = 32e6
PHYS = ("1m", "2m", "s2", "s8")                 # ble_phy_pkg.ble_phy's order
REF_PDU = ble.adv_pdu(ble.ADV_NONCONN_IND, ble.address_octets("C1:A2:A3:A4:A5:A6") + bytes([1, 2, 3]), tx_add=1)
REF_CHANNEL = 38


def vreal(x):
    s = "%.17e" % x
    return "(%s)" % s if s.startswith("-") else s


def rows(items, per=4, indent="        "):
    out = []
    for i in range(0, len(items), per):
        out.append(indent + ", ".join(items[i:i + per]))
    return ",\n".join(out)


def emit(fs=FS):
    radios = {}
    for phy in PHYS:
        r = cc.CC2652R(fs=fs)
        r.phy = phy
        r.symbol_offset()
        radios[phy] = r
    o = []
    w = o.append
    w("-- cc2652r_pkg: the numbers of the CC2652R model.  Written by cc2652r_vhdl.py from cc2652r.py; do not edit.")
    w("library ieee;")
    w("use ieee.math_real.all;")
    w("library rf;")
    w("use rf.iq_pkg.all;")
    w("use work.ble_phy_pkg.all;")
    w("")
    w("package cc2652r_pkg is")
    w("    constant CC_FS : real := %s;                 -- Hz, the model's sample rate" % vreal(fs))
    for name, v in (("F_MIN", cc.SCALARS["f_min"][0]), ("F_MAX", cc.SCALARS["f_max"][0]),
                    ("TX_PMAX", cc.SCALARS["tx_pmax"][0]), ("TX_RANGE", cc.SCALARS["tx_range"][0]),
                    ("TX_STEP", cc.MODEL["tx_power_step"]), ("MOD_INDEX", cc.MODEL["mod_index"]),
                    ("AGC_THRESHOLD", cc.MODEL["agc_threshold"]), ("AGC_RANGE", cc.MODEL["agc_range"]),
                    ("DYNAMIC_RANGE", cc.MODEL["dynamic_range"]), ("SYNC_THRESHOLD", cc.MODEL["sync_threshold"]),
                    ("SYNC_THRESHOLD_CODED", cc.MODEL["sync_threshold_coded"]),
                    ("RSSI_FLOOR", cc.MODEL["rssi_floor"]), ("RSSI_RANGE", cc.SCALARS["rssi_range"][0]),
                    ("K_BOLTZ", cc.K_BOLTZ), ("T0", cc.T0)):
        w("    constant CC_%s : real := %s;" % (name, vreal(float(v))))
    w("    constant CC_SYNC_ERRORS : natural := %d;" % cc.MODEL["sync_errors"])
    w("    type cc_real_by_phy is array (ble_phy) of real;")
    w("    type cc_nat_by_phy is array (ble_phy) of natural;")

    def by_phy(name, fn, typ="real"):
        vals = [fn(p) for p in PHYS]
        txt = ", ".join(vreal(float(v)) if typ == "real" else str(int(v)) for v in vals)
        w("    constant CC_%s : cc_%s_by_phy := (%s);" % (name, "real" if typ == "real" else "nat", txt))

    by_phy("SPS", lambda p: radios[p].sps, "nat")
    by_phy("NF", lambda p: radios[p].fit[p]["nf"])                  # dB, fitted
    by_phy("IIP3", lambda p: radios[p].fit[p]["iip3"])              # dBm, fitted
    by_phy("T0_SAMPLES", lambda p: radios[p].symbol_offset(), "nat")
    by_phy("AMP", lambda p: radios[p]._cache[("amp", p, fs)])
    for k in range(3):                                              # neighbour taps as the detector uses them
        by_phy("ISI%d" % k, lambda p: radios[p]._cache[("isi", p, fs)][k] * (1.0 if k == 1 else radios[p].fit[p].get("det", 1.0)))
    ntaps = {p: len(radios[p].channel_filter()) for p in PHYS}
    by_phy("NTAPS", lambda p: ntaps[p], "nat")
    mx = max(ntaps.values())
    w("    constant CC_MAX_TAPS : natural := %d;" % mx)
    w("    type cc_fir_by_phy is array (ble_phy) of iq_array(0 to CC_MAX_TAPS - 1);")
    w("    constant CC_FIR : cc_fir_by_phy := (")
    blocks = []
    for p in PHYS:
        t = list(radios[p].channel_filter()) + [0j] * (mx - ntaps[p])
        blocks.append("      (\n" + rows(["(%s, %s)" % (vreal(c.real), vreal(c.imag)) for c in t], 2) + ")")
    w(",\n".join(blocks) + ");")
    # the modulator's frequency pulse per sample (ble_phy.gfsk: taps / sps), for the two symbol lengths
    for sps in sorted({radios[p].sps for p in PHYS}):
        g = ble.gaussian_taps(sps, cc.MODEL["bt"]) / sps
        w("    constant CC_GAUSS_%d : real_vector(0 to %d) := (" % (sps, len(g) - 1))
        w(rows([vreal(float(v)) for v in g]) + ");")
    # reference packets
    w("    constant CC_REF_CHANNEL : natural := %d;" % REF_CHANNEL)
    w("    constant CC_REF_PDU : ble_octets(0 to %d) := (%s);" % (len(REF_PDU) - 1, ", ".join(str(b) for b in REF_PDU)))
    for p in PHYS:
        s = ble.packet_symbols(p, REF_PDU, REF_CHANNEL)
        w("    constant CC_REF_SYMBOLS_%s : bit_vector(0 to %d) :=" % (p.upper(), len(s) - 1))
        txt = "".join(str(int(b)) for b in s)
        w("        " + " &\n        ".join('"%s"' % txt[i:i + 96] for i in range(0, len(txt), 96)) + ";")
    t = ble.test_pdu(37)
    w("    constant CC_REF_TEST_PDU : ble_octets(0 to %d) := (%s);" % (len(t) - 1, ", ".join(str(b) for b in t)))
    w("end package;")
    return "\n".join(o) + "\n"


if __name__ == "__main__":
    text = emit()
    if len(sys.argv) > 1:
        with open(sys.argv[1], "w") as fh:
            fh.write(text)
    else:
        sys.stdout.write(text)
