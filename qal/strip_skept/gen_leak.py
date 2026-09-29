#!/usr/bin/env python3
"""SKEPTIC leakage decks.

Purpose: price the keeper over one QAL beat, and DECIDE EMPIRICALLY whether
qal/sg13lv_compat.sp really removes junction leakage.

Method: hold the node at a fixed rail with a voltage source and read the
current THROUGH that source at a true steady state.  That source is the
INSTRUMENT (an ammeter at fixed bias), not a supply for the thing being
measured -- the whole quantity of interest is the current it must deliver.
This avoids the RELTOL*rail voltage-resolution floor entirely: a 200 ps droop
of ~60 nV on a 0.6 V rail is far below any solver tolerance and CANNOT be read
off a waveform, so the per-beat droop is DERIVED from a MEASURED current.

Three junction arms, identical otherwise:
  DEF   raw sg13g2 M-card, AD/AS/PD/PS left at PSP103 defaults
        (= exactly what qal/sg13lv_compat.sp delivers, since the shim declares
         ad/as/pd/ps and then never references them in its body)
  ZERO  AD=AS=PD=PS=0                        (what the brief believes it has)
  REAL  AD=AS=0.2516e-12 m^2, PD=PS=2.16e-6 m
        (a contacted 0.34 um diffusion on the campaign-standard widths)

Controls in EVERY deck:
  NULL  a 2 fF capacitor with NOTHING attached -> must read 0 current
  RCAL  a known 1e12 ohm resistor              -> must read rail/1e12
  HOFF  a hard-off device (Vgs reverse by 0.3 V) -> the device floor
"""
import os, sys

HDR = """.hdl "/usr/local/share/xyce/verilog-a/psp103/psp103.va"
.include "/usr/local/src/kestrel/sim/models/sg13g2_psp103_tt.lib"
.OPTIONS TIMEINT METHOD=GEAR RELTOL=1e-6 ABSTOL=1e-17 CHGTOL=1e-19
"""
# ABSTOL is the DECLARED current floor of this harness: 1e-17 A = 0.00001 pA.
# A reading within a few x ABSTOL of zero is "below floor", not a value.

RAILS = [0.5217, 0.5594, 0.6077, 0.7000, 1.0000]
WN = "0.74u"
WP = "1.12u"
L  = "0.13u"
CL = "2f"

# junction suffix per arm
JUNC = {
    "def":  "",
    "zero": " AD=0 AS=0 PD=0 PS=0",
    "real": " AD=0.2516e-12 AS=0.2516e-12 PD=2.16e-6 PS=2.16e-6",
}


def tag(r):
    return ("r%0.4f" % r).replace(".", "p")


def build(arm):
    j = JUNC[arm]
    L_ = []
    pr = []
    L_.append("* SKEPT leak deck, junction arm = %s" % arm)
    L_.append("* junction instance params appended to every M-card: '%s'" % (j or "<PSP103 DEFAULTS>"))
    L_.append(HDR.rstrip())
    for r in RAILS:
        t = tag(r)
        L_.append("* ---- rail %.4f V" % r)
        # the rail net itself (supply for pMOS source/bulk); ideal, declared
        L_.append("VRAIL%s rail%s 0 %.6f" % (t, t, r))

        # ARM 1: nMOS only, node held HIGH at the rail -> OFF nMOS drain junction
        #        reverse biased by the full rail; this is the whole leak path of
        #        a HIGH dynamic node.
        L_.append("VBN%s qn%s 0 %.6f" % (t, t, r))
        L_.append("CN%s qn%s 0 %s" % (t, t, CL))
        L_.append(f"MN{t} qn{t} 0 0 0 sg13g2_nmos W={WN} L={L}{j}")
        pr.append("I(VBN%s)" % t)

        # ARM 2: pMOS only, the OFF cross-coupled device on a HIGH node: source
        #        AND bulk on the rail, gate on the rail (opposite node HIGH),
        #        drain on the node which is ALSO at the rail.  All four
        #        terminals are then at the same potential, so this arm is
        #        DEGENERATE BY CONSTRUCTION and must read ~0.  It is kept as a
        #        control: it says the OFF cross-coupled pMOS contributes nothing
        #        to a HIGH node's droop, so the nMOS tree is the entire path.
        L_.append("VBP%s qp%s 0 %.6f" % (t, t, r))
        L_.append("CP%s qp%s 0 %s" % (t, t, CL))
        L_.append(f"MP{t} qp{t} rail{t} rail{t} rail{t} sg13g2_pmos W={WP} L={L}{j}")
        pr.append("I(VBP%s)" % t)

        # ARM 2b: the NON-degenerate pMOS case -- a LOW node.  Node held at 0 V;
        #         OFF pMOS has Vgs = 0, |Vds| = rail, drain junction reverse
        #         biased by the rail.  This is the path that makes a LOW node
        #         CREEP UP, and it is the pMOS-side leak that actually exists.
        L_.append("VBL%s ql%s 0 0.0" % (t, t))
        L_.append("CLO%s ql%s 0 %s" % (t, t, CL))
        L_.append(f"MLP{t} ql{t} rail{t} rail{t} rail{t} sg13g2_pmos W={WP} L={L}{j}")
        L_.append(f"MLN{t} ql{t} 0 0 0 sg13g2_nmos W={WN} L={L}{j}")
        pr.append("I(VBL%s)" % t)

        # ARM 3: BOTH, the real bare dynamic node of a stripped cell
        L_.append("VBB%s qb%s 0 %.6f" % (t, t, r))
        L_.append("CB%s qb%s 0 %s" % (t, t, CL))
        L_.append(f"MBN{t} qb{t} 0 0 0 sg13g2_nmos W={WN} L={L}{j}")
        L_.append(f"MBP{t} qb{t} rail{t} rail{t} rail{t} sg13g2_pmos W={WP} L={L}{j}")
        pr.append("I(VBB%s)" % t)

        # ARM 4: NULL control -- capacitor, nothing else.  Must read 0.
        L_.append("VBZ%s qz%s 0 %.6f" % (t, t, r))
        L_.append("CZ%s qz%s 0 %s" % (t, t, CL))
        pr.append("I(VBZ%s)" % t)

        # ARM 5: resistor calibration, 1e12 ohm.  Must read r/1e12.
        L_.append("VBR%s qr%s 0 %.6f" % (t, t, r))
        L_.append("CR%s qr%s 0 %s" % (t, t, CL))
        L_.append("RR%s qr%s 0 1e12" % (t, t))
        pr.append("I(VBR%s)" % t)

        # ARM 6: hard-off nMOS, gate driven 0.3 V BELOW source -> device floor
        L_.append("VNEG%s vneg%s 0 -0.3" % (t, t))
        L_.append("VBH%s qh%s 0 %.6f" % (t, t, r))
        L_.append("CH%s qh%s 0 %s" % (t, t, CL))
        L_.append(f"MH{t} qh{t} vneg{t} 0 0 sg13g2_nmos W={WN} L={L}{j}")
        pr.append("I(VBH%s)" % t)

        if arm == "def":
            # ARM 7: KEEPER arm.  Same bare node PLUS a conventional staticiser:
            #   inverter (p WP / n WN) driven by the node, its output driving a
            #   feedback pMOS (source+bulk on rail, drain on the node).
            #   All at geometries already used, so no extra .so build.
            L_.append("VBK%s qk%s 0 %.6f" % (t, t, r))
            L_.append("CK%s qk%s 0 %s" % (t, t, CL))
            L_.append(f"MKN{t} qk{t} 0 0 0 sg13g2_nmos W={WN} L={L}{j}")
            L_.append(f"MKP{t} qk{t} rail{t} rail{t} rail{t} sg13g2_pmos W={WP} L={L}{j}")
            # staticiser inverter
            L_.append(f"MSIP{t} kb{t} qk{t} rail{t} rail{t} sg13g2_pmos W={WP} L={L}{j}")
            L_.append(f"MSIN{t} kb{t} qk{t} 0 0 sg13g2_nmos W={WN} L={L}{j}")
            L_.append("CKB%s kb%s 0 %s" % (t, t, CL))
            # feedback keeper pMOS
            L_.append(f"MSKP{t} qk{t} kb{t} rail{t} rail{t} sg13g2_pmos W={WP} L={L}{j}")
            pr.append("I(VBK%s)" % t)
            pr.append("V(kb%s)" % t)

    if arm == "zero":
        # warm the 0.56u pMOS geometry needed later for the primary's
        # pre-registered cross-coupled width, and get its off-current for free.
        L_.append("* ---- 0.56u pMOS geometry warm + off-current, at 0.6077 V")
        L_.append("VR56 rail56 0 0.607700")
        L_.append("VB56 q56 0 0.607700")
        L_.append("C56 q56 0 %s" % CL)
        L_.append("M56 q56 rail56 rail56 rail56 sg13g2_pmos W=0.56u L=%s" % L)
        pr.append("I(VB56)")

    L_.append(".tran 0.2n 60n 0 2n")
    L_.append(".print tran format=noindex " + " ".join(pr))
    L_.append(".end")
    return "\n".join(L_) + "\n"


if __name__ == "__main__":
    d = os.path.dirname(os.path.abspath(__file__))
    for arm in ("def", "zero", "real"):
        p = os.path.join(d, "lk_%s.cir" % arm)
        with open(p, "w") as f:
            f.write(build(arm))
        print("wrote", p)
