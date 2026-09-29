#!/usr/bin/env python3
"""SKEPTIC threshold + receiver decks.

vt.cir   Vtn and |Vtp| by the campaign convention: Id = 100 nA * W/L at
         |Vds| = 0.1 V.  MEASURED here, not inherited, because the whole
         "is the |Vtp| wall removed" question turns on whether Vtn > |Vtp|.
         N independent copies at stepped Vgs in ONE deck, read at a true
         steady state (.DC does not return under the PyMS-compiled PSP103).

rcv.cir  The receiver's DC threshold and its 90-10% transition window, on the
         receiver's OWN rail, at a true 50 ns steady state.  Read early and a
         near-threshold pull-up charging 2 fF looks like a trip point of
         ~0.09 x rail, which is a settling artefact, not a threshold.
"""
import os

HDR = """.hdl "/usr/local/share/xyce/verilog-a/psp103/psp103.va"
.include "/usr/local/src/kestrel/sim/models/sg13g2_psp103_tt.lib"
.include "/usr/local/src/stat-sim/qal/sg13lv_compat.sp"
.OPTIONS TIMEINT METHOD=GEAR RELTOL=1e-6 ABSTOL=1e-16 CHGTOL=1e-18
"""

WN, WP, L = "0.74u", "1.12u", "0.13u"
VDS = 0.1


def vt_deck():
    nl = [ "* SKEPT Vt deck: Id = 100 nA * W/L at |Vds| = 0.1 V", HDR.rstrip() ]
    pr = []
    meta = {"nmos": [], "pmos": []}
    # nMOS: source/bulk at 0, drain at +VDS through an ammeter, gate stepped
    k = 0
    vg = 0.30
    while vg <= 0.7501:
        k += 1
        t = "n%03d" % k
        nl.append(f"VG{t} g{t} 0 {vg:.4f}")
        nl.append(f"VD{t} d{t} 0 {VDS:.4f}")
        nl.append(f"X{t} d{t} g{t} 0 0 sg13_lv_nmos w={WN} l={L}")
        pr.append(f"I(VD{t})")
        meta["nmos"].append([f"I(VD{t})".lower(), round(vg, 4)])
        vg += 0.005
    # pMOS: source/bulk at 0 V reference -> use a local rail at 0 and drive
    # drain to -VDS, gate to -vg, so |Vgs| = vg and |Vds| = VDS.
    k = 0
    vg = 0.30
    while vg <= 0.7501:
        k += 1
        t = "p%03d" % k
        nl.append(f"VG{t} g{t} 0 {-vg:.4f}")
        nl.append(f"VD{t} d{t} 0 {-VDS:.4f}")
        nl.append(f"X{t} d{t} g{t} 0 0 sg13_lv_pmos w={WP} l={L}")
        pr.append(f"I(VD{t})")
        meta["pmos"].append([f"I(VD{t})".lower(), round(vg, 4)])
        vg += 0.005
    nl.append(".tran 0.5n 30n 0 2n")
    nl.append(".print tran format=noindex " + " ".join(pr))
    nl.append(".end")
    return "\n".join(nl) + "\n", meta


RCV_RAILS = [0.4500, 0.5571, 0.6077, 0.7000, 1.0000]


def rcv_deck():
    nl = ["* SKEPT receiver deck: static campaign-standard inverter (1.12u/0.74u)",
          "* on its OWN rail, N independent copies at constant input, 50 ns steady state",
          HDR.rstrip()]
    pr = []
    meta = []
    for ri, r in enumerate(RCV_RAILS):
        rt = "r%d" % ri
        nl.append(f"VR{rt} rail{rt} 0 {r:.6f}")
        k = 0
        vin = 0.0
        while vin <= r + 1e-9:
            k += 1
            t = "%s_%03d" % (rt, k)
            nl.append(f"VI{t} i{t} 0 {vin:.5f}")
            nl.append(f"XP{t} o{t} i{t} rail{rt} rail{rt} sg13_lv_pmos w={WP} l={L}")
            nl.append(f"XN{t} o{t} i{t} 0 0 sg13_lv_nmos w={WN} l={L}")
            nl.append(f"CO{t} o{t} 0 2f")
            pr.append(f"V(o{t})")
            meta.append([r, round(vin, 5), f"V(o{t})".lower()])
            vin += 0.005
    nl.append(".tran 1n 50n 0 5n")
    nl.append(".print tran format=noindex " + " ".join(pr))
    nl.append(".end")
    return "\n".join(nl) + "\n", meta


if __name__ == "__main__":
    import json
    d = os.path.dirname(os.path.abspath(__file__))
    t, m = vt_deck()
    open(os.path.join(d, "vt.cir"), "w").write(t)
    json.dump(m, open(os.path.join(d, "VT_META.json"), "w"), indent=1)
    print("vt.cir M-cards:", sum(1 for x in t.splitlines() if x.startswith("X")))
    t, m = rcv_deck()
    open(os.path.join(d, "rcv.cir"), "w").write(t)
    json.dump(m, open(os.path.join(d, "RCV_META.json"), "w"), indent=1)
    print("rcv.cir M-cards:", sum(1 for x in t.splitlines() if x.startswith("X")))
