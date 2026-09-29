#!/usr/bin/env python3
"""
SKEPTIC fixture: a PROPERLY TIMED SYNCHRONOUS BUCK.

This is the experiment the prior agent never ran. Their C2/C3 fixed only the
gate dead times and left the OUT isolation switch opening/closing at the wrong
time; their headline C9 DELETED the freewheel device outright (gate tied to 0
for the whole run), which bounds Qdel/Qsup <= 1 BY CONSTRUCTION, because charge
gain in a buck comes entirely from the freewheel phase, in which the inductor
sources charge from GROUND rather than from the supply.

Sequence here (textbook synchronous buck, break-before-make on BOTH edges,
OUT closed across conduction AND freewheel):
    FW off  ->  dead  ->  HS on  ->  OUT close  ->  conduct TON
             ->  HS off  ->  dead  ->  FW on  ->  freewheel to the current zero

Every terminal is metered with a 0 V ammeter and a 1F integrator, so the
ledger is a set of identities with no fitted term.
"""
import sys, os, subprocess, json, math

HDR = """.hdl "/usr/local/share/xyce/verilog-a/psp103/psp103.va"
.include "/usr/local/src/kestrel/sim/models/sg13g2_psp103_tt.lib"
.include "/usr/local/src/stat-sim/qal/sg13lv_compat.sp"
.OPTIONS TIMEINT METHOD=GEAR RELTOL=1e-6 ABSTOL=1e-15 CHGTOL=1e-17
VHI vhi 0 1.5
VTSUP tsup 0 1.2
"""

def deck(path, L=10e-9, TON=35.0, W=10.0, CB=30e-15, VOUT=0.766, CNA=8e-15,
         t0=100.0, dead1=4.0, outdel=4.0, dead2=2.0, tend=600.0, mode="buck"):
    """mode: 'buck'   = freewheel device driven (real synchronous buck)
             'nofw'   = freewheel gate tied low for the whole run (the prior
                        agent's C9 'diode freewheel')
    """
    # --- gate schedule (ps) ---
    fw_off_a, fw_off_b = t0,               t0 + 2.0
    hs_on_a,  hs_on_b  = t0 + dead1,       t0 + dead1 + 2.0
    out_a,    out_b    = hs_on_b + outdel, hs_on_b + outdel + 2.0
    hs_off_a, hs_off_b = out_b + TON,      out_b + TON + 2.0
    fw_on_a,  fw_on_b  = hs_off_b + dead2, hs_off_b + dead2 + 2.0

    s = [HDR]
    s.append("* L=%g TON=%g W=%g CB=%g VOUT=%g mode=%s" % (L, TON, W, CB, VOUT, mode))
    # bank, biased through a very large resistor so the DC operating point is
    # well posed without the bias path carrying meaningful charge
    s.append("VPRE vpre 0 %.6f" % VOUT)
    s.append("RBIAS rail3 vbz 100meg")
    s.append("VMBIAS vbz vpre 0")
    s.append("CBANK rail3 ncb %g" % CB)
    s.append("VMBANK ncb 0 0")
    # high side
    s.append("XTUSW3 nhs3 gtu3 shs3 shs3 sg13_lv_pmos w=%gu l=0.13u" % W)
    s.append("VMHSS3 tsup shs3 0")
    s.append("VMHS3 nhs3 na3 0")
    # freewheel
    s.append("XTUFW3 nfw3 gfw3 sfw3 sfw3 sg13_lv_nmos w=%gu l=0.13u" % W)
    s.append("VMFWS3 sfw3 0 0")
    s.append("VMFW3 nfw3 na3 0")
    # switch node cap
    s.append("CNA3 na3 ncx3 %g" % CNA)
    s.append("VMCNA3 ncx3 0 0")
    # magnetic + series R + OUT transmission gate
    s.append("LTU3 na3 ntm3 %g" % L)
    s.append("RTU3 ntm3 nb3 10")
    s.append("VMTU3 nb3 nbx3 0")
    s.append("XTUON3 nbx3 gto3 rail3 0 sg13_lv_nmos w=5u l=0.13u")
    s.append("XTUOP3 nbx3 gtop3 rail3 vhi sg13_lv_pmos w=10u l=0.13u")
    # gate drives
    s.append("VGTU3 gtu3 0 PWL(0 1.5 %.4fp 1.5 %.4fp 0 %.4fp 0 %.4fp 1.5)"
             % (hs_on_a, hs_on_b, hs_off_a, hs_off_b))
    if mode == "buck":
        s.append("VGFW3 gfw3 0 PWL(0 1.5 %.4fp 1.5 %.4fp 0 %.4fp 0 %.4fp 1.5)"
                 % (fw_off_a, fw_off_b, fw_on_a, fw_on_b))
    else:
        s.append("VGFW3 gfw3 0 PWL(0 0 %.4fp 0)" % tend)
    s.append("VGTO3 gto3 0 PWL(0 0 %.4fp 0 %.4fp 1.5 %.4fp 1.5)"
             % (out_a, out_b, tend))
    s.append("VGTOP3 gtop3 0 PWL(0 1.5 %.4fp 1.5 %.4fp 0 %.4fp 0)"
             % (out_a, out_b, tend))
    # integrators
    def add(n, e):
        s.append("CXq%s xq%s 0 1" % (n, n))
        s.append("BXq%s 0 xq%s I={ %s }" % (n, n, e))
        s.append("RXq%s xq%s 0 0.01" % (n, n))
    add("sup3", "I(VMHSS3)")
    add("hsd",  "I(VMHS3)")
    add("fws",  "I(VMFWS3)")
    add("fwd",  "I(VMFW3)")
    add("cna",  "I(VMCNA3)")
    add("ind",  "I(LTU3)")
    add("bank", "I(VMBANK)")
    add("bias", "I(VMBIAS)")
    add("gtu",  "I(VGTU3)")
    add("gfw",  "I(VGFW3)")
    add("gto",  "I(VGTO3)")
    add("gtop", "I(VGTOP3)")
    add("sup",  "-I(VTSUP)")
    add("out",  "I(VMTU3)")
    add("esup", "-1.2*I(VTSUP)")
    add("ebnk", "V(rail3)*I(VMBANK)")
    add("er",   "I(LTU3)*I(LTU3)*10")
    add("egd",  "-V(gtu3)*I(VGTU3)-V(gfw3)*I(VGFW3)-V(gto3)*I(VGTO3)-V(gtop3)*I(VGTOP3)")
    s.append(".ic V(rail3)=%.6f V(na3)=0 V(nhs3)=0 V(nfw3)=0 V(ncx3)=0 V(shs3)=1.2 V(sfw3)=0 V(nb3)=0 V(nbx3)=0 V(ntm3)=0" % VOUT)
    s.append(".tran 0.02p %.4fp 0 0.02p" % tend)
    s.append(".print tran V(rail3) V(na3) I(LTU3) I(VMHS3) I(VMFWS3) I(VMFW3) I(VMHSS3) I(VMCNA3) I(VMBANK) I(VMBIAS) I(VGTU3) I(VGFW3) V(gtu3) V(gfw3) V(gto3) V(xqsup3) V(xqhsd) V(xqfws) V(xqfwd) V(xqcna) V(xqind) V(xqbank) V(xqbias) V(xqgtu) V(xqgfw) V(xqgto) V(xqgtop) V(xqsup) V(xqout) V(xqesup) V(xqebnk) V(xqer) V(xqegd)")
    s.append(".end")
    open(path, "w").write("\n".join(s) + "\n")
    return dict(path=path, L=L, TON=TON, W=W, CB=CB, VOUT=VOUT, mode=mode,
                t_fw_off=fw_off_b, t_hs_on=hs_on_b, t_out=out_b,
                t_hs_off=hs_off_b, t_fw_on=fw_on_b, tend=tend)

if __name__ == "__main__":
    print(deck("/tmp/x.cir"))
