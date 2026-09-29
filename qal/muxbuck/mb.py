#!/usr/bin/env python3
"""qal/muxbuck deck generators.

Cells, switch, park, tank and buck block are taken VERBATIM from the committed
decks (qal/lsweep/h_L15_W30_dv120.cir, qal/banktank/c_m10_*.cir, qal/ptu/p*_ptu_*.cir).
Nothing here invents a device size.
"""
import sys

HDR = """.hdl "/usr/local/share/xyce/verilog-a/psp103/psp103.va"
.include "/usr/local/src/kestrel/sim/models/sg13g2_psp103_tt.lib"
.include "/usr/local/src/stat-sim/qal/sg13lv_compat.sp"
.OPTIONS TIMEINT METHOD=GEAR RELTOL=1e-6 ABSTOL=1e-15 CHGTOL=1e-17
"""

# committed banktank bank-1 input pattern (4 high / 4 low, verbatim)
PAT8 = [1.2, 1.2, 1.2, 0, 1.2, 0, 0, 1.2]

# committed banktank bank-1 ZCS windows at m=10, dV=1.2, T=200, H=4
T_RISE_WIN = 318.184 - 200.0      # 118.184 ps
T_RET_WIN  = 1129.37 - 1000.0     # 129.370 ps


def integ(name, expr):
    return (f"CX{name} x{name} 0 1\n"
            f"BX{name} 0 x{name} I={{ {expr} }}\n"
            f"RX{name} x{name} 0 0.01\n")


def droop_deck(ngate, ctank_f, lt_nh, ncyc, period=1600.0, path="mb_droop.cir", rs=10.0,
               vt0=0.66, rise_win=None, ret_win=None):
    """One tank -> L -> R -> TG -> one bank of `ngate` inverters, `ncyc` repeated
    rise/return cycles on the committed bank-1 window, no top-up at all."""
    s = [HDR]
    s.append("VHI vhi 0 1.5\n")
    s.append("VMG gn 0 0\n")
    pat = [PAT8[i % 8] for i in range(ngate)]
    for i, v in enumerate(pat):
        s.append(f"VI{i} in{i} 0 {v}\n")
        s.append(f"XP{i} o{i} in{i} rail rail sg13_lv_pmos w=1.12u l=0.13u\n")
        s.append(f"XN{i} o{i} in{i} gn gn sg13_lv_nmos w=0.74u l=0.13u\n")
        s.append(f"CL{i} o{i} gn 2f\n")
    s.append(f"CT tnk 0 {ctank_f}f\n")
    s.append(f"LT tnk mid {lt_nh}n\n")
    s.append(f"RT mid sw {rs}\n")
    s.append("XSWN sw gt rail 0 sg13_lv_nmos w=10u l=0.13u\n")
    s.append("XSWP sw gtp rail vhi sg13_lv_pmos w=20u l=0.13u\n")
    s.append("XPK sw pk tnk tnk sg13_lv_nmos w=2u l=0.13u\n")

    # gate schedule: transfer gate closed during rise and during return, park anti-phase
    gt, gtp, pk = [], [], []
    marks = []
    rw = T_RISE_WIN if rise_win is None else rise_win
    qw = T_RET_WIN if ret_win is None else ret_win
    for k in range(ncyc):
        tc = 200.0 + period * k            # rise close
        ta = tc + rw                       # rise open  (ZCS)
        tr = 1000.0 + period * k           # return close
        tb = tr + qw                       # return open (ZCS)
        marks.append((k, tc, ta, tr, tb))
        for (t0, t1) in ((tc, ta), (tr, tb)):
            gt += [(t0 - 2, 0.0), (t0, 1.5), (t1, 1.5), (t1 + 2, 0.0)]
            gtp += [(t0 - 2, 1.5), (t0, 0.0), (t1, 0.0), (t1 + 2, 1.5)]
            pk += [(t0 - 2, 1.5), (t0, 0.0), (t1, 0.0), (t1 + 2, 1.5)]

    def pwl(name, node, pts, v0):
        body = f"0 {v0} " + " ".join(f"{t}p {v}" for t, v in pts)
        return f"{name} {node} 0 PWL({body})\n"

    s.append(pwl("VGT", "gt", gt, 0.0))
    s.append(pwl("VGTP", "gtp", gtp, 1.5))
    s.append(pwl("VPK", "pk", pk, 1.5))

    # metering: 1 F integrators, t0-referenced at extraction
    s.append(integ("qlt", "I(LT)"))
    s.append(integ("er", f"I(LT)*I(LT)*{rs}"))
    s.append(integ("qg", "I(VMG)"))
    s.append(integ("egt", "-V(gt)*I(VGT)-V(gtp)*I(VGTP)-V(pk)*I(VPK)"))
    isum = "+".join(f"I(VI{i})" for i in range(ngate))
    s.append(integ("qin", f"-({isum})"))

    v0 = vt0   # committed pre-charge is 0.66 V = dV(m+1)/2m at m=10, dV=1.2
    s.append(f".ic V(tnk)={v0} V(rail)=0 V(sw)={v0}\n")

    tstop = 200.0 + period * (ncyc - 1) + 1000.0 - 200.0 + T_RET_WIN + 600.0
    s.append(f".tran 0.1p {tstop:.3f}p 0 0.25p\n")

    m = []
    m.append(".measure tran QLT_Z FIND V(xqlt) AT=1.500000p\n")
    m.append(".measure tran ER_Z FIND V(xer) AT=1.500000p\n")
    m.append(".measure tran QG_Z FIND V(xqg) AT=1.500000p\n")
    m.append(".measure tran EGT_Z FIND V(xegt) AT=1.500000p\n")
    m.append(".measure tran QIN_Z FIND V(xqin) AT=1.500000p\n")
    for (k, tc, ta, tr, tb) in marks:
        m.append(f".measure tran VT{k}A FIND V(tnk) AT={tc-1.0:.6f}p\n")     # tank before rise
        m.append(f".measure tran VT{k}B FIND V(tnk) AT={ta+0.5:.6f}p\n")     # tank after rise
        m.append(f".measure tran VT{k}C FIND V(tnk) AT={tr-1.0:.6f}p\n")     # tank before return
        m.append(f".measure tran VT{k}D FIND V(tnk) AT={tb+0.5:.6f}p\n")     # tank after return
        m.append(f".measure tran VR{k}O FIND V(rail) AT={ta+0.5:.6f}p\n")    # delivered rail at ZCS open
        m.append(f".measure tran VR{k}P MAX V(rail) FROM={tc:.6f}p TO={ta:.6f}p\n")
        m.append(f".measure tran VR{k}H FIND V(rail) AT={ta+300.0:.6f}p\n")  # held rail 300 ps later
        m.append(f".measure tran VR{k}E FIND V(rail) AT={tr-1.0:.6f}p\n")    # rail just before return
        m.append(f".measure tran IZ{k}R FIND I(LT) AT={ta:.6f}p\n")
        m.append(f".measure tran IZ{k}Q FIND I(LT) AT={tb:.6f}p\n")
        m.append(f".measure tran QLT{k}A FIND V(xqlt) AT={tc-1.0:.6f}p\n")
        m.append(f".measure tran QLT{k}D FIND V(xqlt) AT={tb+0.5:.6f}p\n")
        m.append(f".measure tran ER{k}A FIND V(xer) AT={tc-1.0:.6f}p\n")
        m.append(f".measure tran ER{k}D FIND V(xer) AT={tb+0.5:.6f}p\n")
        m.append(f".measure tran QG{k}A FIND V(xqg) AT={tc-1.0:.6f}p\n")
        m.append(f".measure tran QG{k}D FIND V(xqg) AT={tb+0.5:.6f}p\n")
        m.append(f".measure tran QIN{k}A FIND V(xqin) AT={tc-1.0:.6f}p\n")
        m.append(f".measure tran QIN{k}D FIND V(xqin) AT={tb+0.5:.6f}p\n")
        m.append(f".measure tran EGT{k}A FIND V(xegt) AT={tc-1.0:.6f}p\n")
        m.append(f".measure tran EGT{k}D FIND V(xegt) AT={tb+0.5:.6f}p\n")
        for i in range(ngate):
            m.append(f".measure tran O{i}_{k} FIND V(o{i}) AT={ta+300.0:.6f}p\n")
    s += m
    pr = " ".join(["V(tnk)", "V(rail)", "V(sw)", "I(LT)", "V(xqlt)"] +
                  [f"V(o{i})" for i in range(min(ngate, 8))])
    s.append(f".print tran {pr}\n.end\n")
    open(path, "w").write("".join(s))
    return path, marks


def mux_deck(ntap, path, ctank_f=359.79, vtank0=0.66):
    """Committed ptu buck block feeding tank 1 through its OUT/mux switch, with
    ntap-1 additional mux switches (same size) hung OFF on the shared node, each
    going to its own idle tank.  One pulse.  Answers: does delivered charge per
    pulse fall as the number of idle taps grows, and what does the mux gate cost."""
    s = [HDR]
    s.append("VHI vhi 0 1.5\n")
    s.append("VSUP tsup 0 1.2\n")
    # buck: HS pmos 10u, freewheel nmos 10u, LTU 1n, RTU 10 -- verbatim qal/ptu
    s.append("CNA na 0 8f\n")
    s.append("XTUSW na gtu tsup tsup sg13_lv_pmos w=10u l=0.13u\n")
    s.append("XTUFW na gfw 0 0 sg13_lv_nmos w=10u l=0.13u\n")
    s.append("LTU na ntm 1n\n")
    s.append("RTU ntm nb 10\n")
    s.append("VMTU nb nbx 0\n")
    # shared buck output node = nbx.  mux switch = committed OUT TG (5u/10u).
    for j in range(ntap):
        s.append(f"XMXN{j} nbx gmn{j} tnk{j} 0 sg13_lv_nmos w=5u l=0.13u\n")
        s.append(f"XMXP{j} nbx gmp{j} tnk{j} vhi sg13_lv_pmos w=10u l=0.13u\n")
        s.append(f"CT{j} tnk{j} 0 {ctank_f}f\n")
    # committed ptu pulse timing, shifted to start at 0: HS on 314->366, FW ramp
    # 317.978->341.978, OUT on 339.978->372.042 (all minus 300 ps)
    s.append("VGTU gtu 0 PWL(0 1.5 9.978p 1.5 13.978p 0 65.978p 0 67.978p 1.5)\n")
    s.append("VGFW gfw 0 PWL(0 1.5 17.978p 1.5 41.978p 0 65.978p 0 67.978p 1.5)\n")
    # tap 0 is the SELECTED tank; taps 1..N-1 stay OFF for the whole run
    s.append("VGMN0 gmn0 0 PWL(0 0 39.978p 0 41.978p 1.5 72.042p 1.5 74.042p 0)\n")
    s.append("VGMP0 gmp0 0 PWL(0 1.5 39.978p 1.5 41.978p 0 72.042p 0 74.042p 1.5)\n")
    for j in range(1, ntap):
        s.append(f"VGMN{j} gmn{j} 0 0\n")
        s.append(f"VGMP{j} gmp{j} 0 1.5\n")
    s.append(integ("qsup", "-I(VSUP)"))
    s.append(integ("esup", "-1.2*I(VSUP)"))
    s.append(integ("qdel", "I(VMTU)"))
    s.append(integ("egm", "-V(gmn0)*I(VGMN0)-V(gmp0)*I(VGMP0)"))
    s.append(integ("qgm", "-I(VGMN0)"))
    ic = " ".join([f"V(tnk{j})={vtank0}" for j in range(ntap)])
    s.append(f".ic V(na)=0 V(nb)=0 V(nbx)={vtank0} {ic}\n")
    s.append(".tran 0.05p 200p 0 0.0884183p\n")
    s.append(".measure tran QSUP_Z FIND V(xqsup) AT=1.500000p\n")
    s.append(".measure tran QSUP_E FIND V(xqsup) AT=199.000000p\n")
    s.append(".measure tran ESUP_Z FIND V(xesup) AT=1.500000p\n")
    s.append(".measure tran ESUP_E FIND V(xesup) AT=199.000000p\n")
    s.append(".measure tran QDEL_Z FIND V(xqdel) AT=1.500000p\n")
    s.append(".measure tran QDEL_E FIND V(xqdel) AT=199.000000p\n")
    s.append(".measure tran EGM_Z FIND V(xegm) AT=1.500000p\n")
    s.append(".measure tran EGM_E FIND V(xegm) AT=199.000000p\n")
    s.append(".measure tran QGM_Z FIND V(xqgm) AT=1.500000p\n")
    s.append(".measure tran QGM_E FIND V(xqgm) AT=199.000000p\n")
    s.append(".measure tran VNBXPK MAX V(nbx) FROM=0 TO=199p\n")
    s.append(".measure tran VNBXMN MIN V(nbx) FROM=0 TO=199p\n")
    s.append(".measure tran VNAPK MAX V(na) FROM=0 TO=199p\n")
    s.append(".measure tran ILPK MAX I(LTU) FROM=0 TO=199p\n")
    s.append(".measure tran VT0E FIND V(tnk0) AT=199.000000p\n")
    if ntap > 1:
        s.append(".measure tran VT1E FIND V(tnk1) AT=199.000000p\n")
    s.append(".print tran V(na) V(nbx) V(tnk0) I(LTU) V(xqdel) V(xqsup)\n.end\n")
    open(path, "w").write("".join(s))
    return path


if __name__ == "__main__":
    what = sys.argv[1]
    if what == "droop8":
        p, m = droop_deck(8, 359.79, 15, 3, path="mb_droop8.cir")
        print(p, m)
    elif what == "droop48":
        p, m = droop_deck(48, 2158.74, 2.5, 2, path="mb_droop48.cir", rs=1.66667)
        print(p, m)
    elif what == "mux":
        for n in (1, 4, 16):
            print(mux_deck(n, f"mb_mux_N{n}.cir"))
