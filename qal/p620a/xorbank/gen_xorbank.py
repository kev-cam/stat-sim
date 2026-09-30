#!/usr/bin/env python3
"""128-cell XOR2 bank with tank + switch + inductor (the AddRoundKey shape).
Emits the SAME circuit as a Xyce deck (xorbank.cir) and a VACASK deck
(xorbank.sim). Scale-timing benchmark for AES-round feasibility.

Cell: static-CMOS XOR2, 12T (2 rail-powered input inverters + 2x2 PUN +
2x2 PDN), committed cell widths WP=1.12u WN=0.74u l=0.13u, CL=2 fF per
output into the bank's ground return (ammeter VMG).

Bank supply: one tank cap -> inductor -> series R -> committed TG triple
(nmos+pmos transfer gate + park nmos, banktank widths() rule), driving the
single rail of all 128 cells.

Sizing (DERIVED, declared): per-XOR rail-side device load ~4x an inverter's;
committed 8-inv bank measured 35.979 fF -> C_bank_est = 35.979f * (128*4)/8
= 2.302 pF. Tank C_t = C_bank_est (m=1 rule, vtank0 -> V_t0 = dv).
L chosen for the committed ~265 ps quarter-wave: L=(t/pi)^2/Ceff,
Ceff = Ct*Cb/(Ct+Cb) = C/2 -> L = 6.2 nH. Switch total_um scaled by the
same C ratio: 15u * 64 = 960u -> wn=320u wp=640u park=64u (widths() 1:2 + /15).
Timing: close 50p (2p edge), open at 50p+265p (ANALYTIC hop, not ZCS-measured
-- declared), park closes open+2p, end open+500p tail.
Patterns: a = bits of 0x6A09E667BB67AE85_3C6EF372A54FF53A_510E527F9B05688C_1F83D9ABFB41BD6B
          b = bits of 0x428A2F9871374491_B5C0FBCFE9B5DBA5_3956C25B59F111F1_923F82A4AB1C5ED5
expected out_i = a_i XOR b_i.
"""
import sys

WP, WN, LCH = 1.12, 0.74, 0.13
N = 128
DV = 1.2
CBANK_EST_F = 35.979e-15 * (N * 4) / 8.0        # 2.3026e-12 F
LT_H = 6.2e-9
RS = 10.0
WSW_N, WSW_P, WPK = 320.0, 640.0, 64.0
T_CLOSE = 50.0       # ps
T_HOP = 265.0        # ps (analytic)
T_OPEN = T_CLOSE + T_HOP
T_PARK = T_OPEN + 2.0
T_END = T_OPEN + 500.0
EDGE = 2.0

A_HEX = ("6A09E667BB67AE85" "3C6EF372A54FF53A" "510E527F9B05688C" "1F83D9ABFB41BD6B")
B_HEX = ("428A2F9871374491" "B5C0FBCFE9B5DBA5" "3956C25B59F111F1" "923F82A4AB1C5ED5")
A = int(A_HEX, 16)
B = int(B_HEX, 16)
abit = [(A >> i) & 1 for i in range(N)]
bbit = [(B >> i) & 1 for i in range(N)]
xbit = [a ^ b for a, b in zip(abit, bbit)]

def xyce():
    L = ["* 128-cell XOR2 bank, tank+switch+inductor (AddRoundKey shape)",
         '.hdl "/usr/local/share/xyce/verilog-a/psp103/psp103.va"',
         '.include "/usr/local/src/kestrel/sim/models/sg13g2_psp103_tt.lib"',
         '.include "/usr/local/src/stat-sim/qal/sg13lv_compat.sp"',
         ".OPTIONS TIMEINT METHOD=GEAR RELTOL=1e-6 ABSTOL=1e-15",
         "VHI vhi 0 1.5",
         "CT tnk 0 %.6gf" % (CBANK_EST_F * 1e15),
         "LT tnk mid %.6gn" % (LT_H * 1e9),
         "RT mid sw %g" % RS,
         "VGT gt 0 PWL(0 0 %gp 0 %gp 1.5 %gp 1.5 %gp 0)"
         % (T_CLOSE - EDGE, T_CLOSE, T_OPEN, T_OPEN + EDGE),
         "VGTP gtp 0 PWL(0 1.5 %gp 1.5 %gp 0 %gp 0 %gp 1.5)"
         % (T_CLOSE - EDGE, T_CLOSE, T_OPEN, T_OPEN + EDGE),
         "VPK pk 0 PWL(0 0 %gp 0 %gp 1.5)" % (T_PARK, T_PARK + EDGE),
         "XSWN sw gt rail 0 sg13_lv_nmos w=%gu l=%gu" % (WSW_N, LCH),
         "XSWP sw gtp rail vhi sg13_lv_pmos w=%gu l=%gu" % (WSW_P, LCH),
         "XPK sw pk tnk tnk sg13_lv_nmos w=%gu l=%gu" % (WPK, LCH),
         "VMG gn 0 0",
         ".ic V(tnk)=%g V(rail)=0" % DV]
    for i in range(N):
        L.append("VA%d a%d 0 %g" % (i, i, DV if abit[i] else 0.0))
        L.append("VB%d b%d 0 %g" % (i, i, DV if bbit[i] else 0.0))
        # input inverters (rail powered)
        L.append("XIAP%d an%d a%d rail rail sg13_lv_pmos w=%gu l=%gu" % (i, i, i, WP, LCH))
        L.append("XIAN%d an%d a%d gn gn sg13_lv_nmos w=%gu l=%gu" % (i, i, i, WN, LCH))
        L.append("XIBP%d bn%d b%d rail rail sg13_lv_pmos w=%gu l=%gu" % (i, i, i, WP, LCH))
        L.append("XIBN%d bn%d b%d gn gn sg13_lv_nmos w=%gu l=%gu" % (i, i, i, WN, LCH))
        # PUN: rail -[P g=an]- p1 -[P g=b]- o   |  rail -[P g=a]- p2 -[P g=bn]- o
        L.append("XU1A%d p1_%d an%d rail rail sg13_lv_pmos w=%gu l=%gu" % (i, i, i, WP, LCH))
        L.append("XU1B%d o%d b%d p1_%d rail sg13_lv_pmos w=%gu l=%gu" % (i, i, i, i, WP, LCH))
        L.append("XU2A%d p2_%d a%d rail rail sg13_lv_pmos w=%gu l=%gu" % (i, i, i, WP, LCH))
        L.append("XU2B%d o%d bn%d p2_%d rail sg13_lv_pmos w=%gu l=%gu" % (i, i, i, i, WP, LCH))
        # PDN: o -[N g=a]- n1 -[N g=b]- gn  |  o -[N g=an]- n2 -[N g=bn]- gn
        L.append("XD1A%d o%d a%d n1_%d gn sg13_lv_nmos w=%gu l=%gu" % (i, i, i, i, WN, LCH))
        L.append("XD1B%d n1_%d b%d gn gn sg13_lv_nmos w=%gu l=%gu" % (i, i, i, WN, LCH))
        L.append("XD2A%d o%d an%d n2_%d gn sg13_lv_nmos w=%gu l=%gu" % (i, i, i, i, WN, LCH))
        L.append("XD2B%d n2_%d bn%d gn gn sg13_lv_nmos w=%gu l=%gu" % (i, i, i, WN, LCH))
        L.append("CL%d o%d gn 2f" % (i, i))
    L.append(".tran 0.1p %gp 0 0.25p" % T_END)
    L.append(".print tran V(rail) V(tnk) I(LT) V(o0) V(o1) V(o63) V(o126) V(o127)")
    for i in range(N):
        L.append(".measure tran OE%d FIND V(o%d) AT=%gp" % (i, i, T_END - 5.0))
    L.append(".measure tran RAILE FIND V(rail) AT=%gp" % (T_END - 5.0))
    L.append(".measure tran TNKE FIND V(tnk) AT=%gp" % (T_END - 5.0))
    L.append(".end")
    return "\n".join(L) + "\n"

def vacask():
    L = ["128-cell XOR2 bank, tank+switch+inductor (AddRoundKey shape)",
         "",
         'load "psp103v4.osdi"',
         'load "capacitor.osdi"',
         'load "inductor.osdi"',
         'load "spice/resistor.osdi"',
         'include "sg13g2_models.inc"',
         "model v vsource",
         "model rmod sp_resistor",
         "model cmod capacitor",
         "model lmod inductor",
         "",
         "subckt sg13_lv_nmos (d g s b)",
         "  parameters w=0.15u l=0.13u",
         "  m1 (d g s b) sg13g2_nmos w=w l=l",
         "ends",
         "subckt sg13_lv_pmos (d g s b)",
         "  parameters w=0.15u l=0.13u",
         "  m1 (d g s b) sg13g2_pmos w=w l=l",
         "ends",
         "",
         "vhi (vhi 0) v dc=1.5",
         "ct (tnk 0) cmod c=%.6gf" % (CBANK_EST_F * 1e15),
         "lt (tnk mid) lmod l=%.6gn" % (LT_H * 1e9),
         "rt (mid sw) rmod r=%g" % RS,
         'vgt (gt 0) v type="pwl" wave=[%gp,0, %gp,1.5, %gp,1.5, %gp,0]'
         % (T_CLOSE - EDGE, T_CLOSE, T_OPEN, T_OPEN + EDGE),
         'vgtp (gtp 0) v type="pwl" wave=[%gp,1.5, %gp,0, %gp,0, %gp,1.5]'
         % (T_CLOSE - EDGE, T_CLOSE, T_OPEN, T_OPEN + EDGE),
         'vpk (pk 0) v type="pwl" wave=[%gp,0, %gp,1.5]' % (T_PARK, T_PARK + EDGE),
         "xswn (sw gt rail 0) sg13_lv_nmos w=%gu l=%gu" % (WSW_N, LCH),
         "xswp (sw gtp rail vhi) sg13_lv_pmos w=%gu l=%gu" % (WSW_P, LCH),
         "xpk (sw pk tnk tnk) sg13_lv_nmos w=%gu l=%gu" % (WPK, LCH),
         "vmg (gn 0) v dc=0"]
    for i in range(N):
        L.append("va%d (a%d 0) v dc=%g" % (i, i, DV if abit[i] else 0.0))
        L.append("vb%d (b%d 0) v dc=%g" % (i, i, DV if bbit[i] else 0.0))
        L.append("xiap%d (an%d a%d rail rail) sg13_lv_pmos w=%gu l=%gu" % (i, i, i, WP, LCH))
        L.append("xian%d (an%d a%d gn gn) sg13_lv_nmos w=%gu l=%gu" % (i, i, i, WN, LCH))
        L.append("xibp%d (bn%d b%d rail rail) sg13_lv_pmos w=%gu l=%gu" % (i, i, i, WP, LCH))
        L.append("xibn%d (bn%d b%d gn gn) sg13_lv_nmos w=%gu l=%gu" % (i, i, i, WN, LCH))
        L.append("xu1a%d (p1_%d an%d rail rail) sg13_lv_pmos w=%gu l=%gu" % (i, i, i, WP, LCH))
        L.append("xu1b%d (o%d b%d p1_%d rail) sg13_lv_pmos w=%gu l=%gu" % (i, i, i, i, WP, LCH))
        L.append("xu2a%d (p2_%d a%d rail rail) sg13_lv_pmos w=%gu l=%gu" % (i, i, i, WP, LCH))
        L.append("xu2b%d (o%d bn%d p2_%d rail) sg13_lv_pmos w=%gu l=%gu" % (i, i, i, i, WP, LCH))
        L.append("xd1a%d (o%d a%d n1_%d gn) sg13_lv_nmos w=%gu l=%gu" % (i, i, i, i, WN, LCH))
        L.append("xd1b%d (n1_%d b%d gn gn) sg13_lv_nmos w=%gu l=%gu" % (i, i, i, WN, LCH))
        L.append("xd2a%d (o%d an%d n2_%d gn) sg13_lv_nmos w=%gu l=%gu" % (i, i, i, i, WN, LCH))
        L.append("xd2b%d (n2_%d bn%d gn gn) sg13_lv_nmos w=%gu l=%gu" % (i, i, i, WN, LCH))
        L.append("cl%d (o%d gn) cmod c=2f" % (i, i))
    L += ["", "control",
          '  options tran_method="gear" reltol=1e-5',
          "  save v(rail) v(tnk) i(lt)"]
    for i in range(0, N, 8):
        L.append("  save " + " ".join("v(o%d)" % k for k in range(i, i + 8)))
    L += ["  analysis xbtr tran step=0.1p stop=%gp maxstep=0.25p icmode=\"op\" ic=[\"tnk\"; %g; \"mid\"; %g; \"sw\"; %g; \"rail\"; 0.0]"
          % (T_END, DV, DV, DV),
          "endc", ""]
    return "\n".join(L)

if __name__ == "__main__":
    open("xorbank.cir", "w").write(xyce())
    open("xorbank.sim", "w").write(vacask())
    exp = "".join(str(b) for b in xbit)
    open("expected_bits.txt", "w").write(
        "bit i (o%d..o0 order reversed): out_i = a_i xor b_i\n" % (N - 1) + exp + "\n")
    print("wrote xorbank.cir xorbank.sim; expected out bits (i=0 first):")
    print(exp)
