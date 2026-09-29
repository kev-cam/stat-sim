#!/usr/bin/env python3
"""Isolate WHICH junction term drives the LOW-node leakage difference.

Observation to explain: on the LOW node (OFF pMOS with |Vds| = rail) the
'REAL' junction arm leaks 2.95x MORE than the shim-default arm, even though
REAL has a SMALLER bottom area (2.516e-13 vs 1e-12 m^2).  So bottom area is not
the driver.

Mechanism hypothesis, from PSP103_module.include with SWJUNCAP=3:
    ABD_i = AD ;  LSD_i = PD - jww ;  LGD_i = jww      (jww = effective width)
and LSD is CLIPPED LOW AT 0.  The shim leaves PD at the PSP103 default 1.0e-6 m.
For the campaign-standard pMOS, W = 1.12e-6 > 1.0e-6, so
    LSD_i = 1.0e-6 - 1.12e-6 < 0  ->  CLIPPED TO ZERO
i.e. the pMOS STI-edge junction is ENTIRELY ABSENT at the default geometry.
For the campaign-standard nMOS, W = 0.74e-6 < 1.0e-6, so LSD_i = 0.26e-6 and the
nMOS STI edge is PRESENT (just short).  That would explain why the HIGH node
(nMOS-dominated) is insensitive to the junction while the LOW node
(pMOS-dominated) is not.

Arms, all pMOS 1.12u/0.13u, LOW node, same rail set:
  a  AD=1e-12      PD=2.16e-6   default AREA, long perimeter
  b  AD=2.516e-13  PD=1e-6      small area, default (clipped) perimeter
  c  AD=3.808e-13  PD=2.92e-6   the PDK's OWN pMOS geometry for this cell
If (a) ~ REAL and (b) ~ DEF, perimeter is the driver and area is irrelevant.
"""
import os

HDR = """.hdl "/usr/local/share/xyce/verilog-a/psp103/psp103.va"
.include "/usr/local/src/kestrel/sim/models/sg13g2_psp103_tt.lib"
.OPTIONS TIMEINT METHOD=GEAR RELTOL=1e-6 ABSTOL=1e-17 CHGTOL=1e-19
"""

RAILS = [0.5217, 0.5594, 0.6077, 0.7000, 1.0000]
ARMS = {
    "a": "AD=1e-12 AS=1e-12 PD=2.16e-6 PS=2.16e-6",
    "b": "AD=0.2516e-12 AS=0.2516e-12 PD=1e-6 PS=1e-6",
    "c": "AD=0.3808e-12 AS=0.3808e-12 PD=2.92e-6 PS=2.92e-6",
}


def tagf(r):
    return ("r%0.4f" % r).replace(".", "p")


def main():
    nl = ["* SKEPT junction-term isolation, pMOS 1.12u LOW node", HDR.rstrip()]
    pr = []
    for r in RAILS:
        t = tagf(r)
        nl.append("* ---- rail %.4f" % r)
        nl.append(f"VRAIL{t} rail{t} 0 {r:.6f}")
        # gmin reference for this rail: a known 1e12 ohm
        nl.append(f"VBR{t} qr{t} 0 {r:.6f}")
        nl.append(f"RR{t} qr{t} 0 1e12")
        pr.append(f"I(VBR{t})")
        for a, j in ARMS.items():
            nl.append(f"VB{a}{t} q{a}{t} 0 0.0")
            nl.append(f"C{a}{t} q{a}{t} 0 2f")
            nl.append(f"M{a}{t} q{a}{t} rail{t} rail{t} rail{t} "
                      f"sg13g2_pmos W=1.12u L=0.13u {j}")
            pr.append(f"I(VB{a}{t})")
    nl.append(".tran 0.2n 60n 0 2n")
    nl.append(".print tran format=noindex " + " ".join(pr))
    nl.append(".end")
    d = os.path.dirname(os.path.abspath(__file__))
    open(os.path.join(d, "lk_iso.cir"), "w").write("\n".join(nl) + "\n")
    print("wrote lk_iso.cir")


if __name__ == "__main__":
    main()
