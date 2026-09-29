#!/usr/bin/env python3
"""qal/muxbuck_sk -- SKEPTIC decks against qal/muxbuck.

Every device size, every gate timing edge and every initial condition is taken
VERBATIM from the balance run's decks (which in turn took them from the committed
qal/ptu and qal/banktank decks).  The ONLY things I vary are the three things I
pre-registered as challenges:
  * WHEN the mux gate closes (committed 41.978p  vs  early t=0)   -> H1 / S1
  * the mux TG WIDTH (2.5u/5u, 5u/10u committed, 10u/20u)         -> S2
  * the NUMBER of back-to-back buck pulses (1 vs 2)               -> transient vs steady
"""
import sys

HDR = """.hdl "/usr/local/share/xyce/verilog-a/psp103/psp103.va"
.include "/usr/local/src/kestrel/sim/models/sg13g2_psp103_tt.lib"
.include "/usr/local/src/stat-sim/qal/sg13lv_compat.sp"
.OPTIONS TIMEINT METHOD=GEAR RELTOL=1e-6 ABSTOL=1e-15 CHGTOL=1e-17
"""

CT_F = 359.79          # committed tank, fF
PERIOD = 64.064        # committed ptu pulse cycle, ps  (9.978 -> 74.042)


def integ(name, expr):
    return (f"CX{name} x{name} 0 1\n"
            f"BX{name} 0 x{name} I={{ {expr} }}\n"
            f"RX{name} x{name} 0 0.01\n")


def mux_deck(path, n, wn=5.0, wp=10.0, early=False, npulse=1, tstop=200.0,
             na0=0.0, qdel=True):
    """Committed ptu buck block -> shared node nbx -> N mux TGs -> N tanks.
    Tap 0 is selected; taps 1..N-1 are held OFF on the shared node."""
    s = [HDR]
    s.append("VHI vhi 0 1.5\n")
    s.append("VSUP tsup 0 1.2\n")
    s.append("CNA na 0 8f\n")
    s.append("XTUSW na gtu tsup tsup sg13_lv_pmos w=10u l=0.13u\n")
    s.append("XTUFW na gfw 0 0 sg13_lv_nmos w=10u l=0.13u\n")
    s.append("LTU na ntm 1n\n")
    s.append("RTU ntm nb 10\n")
    s.append("VMTU nb nbx 0\n")
    for k in range(n):
        s.append(f"XMXN{k} nbx gmn{k} tnk{k} 0 sg13_lv_nmos w={wn}u l=0.13u\n")
        s.append(f"XMXP{k} nbx gmp{k} tnk{k} vhi sg13_lv_pmos w={wp}u l=0.13u\n")
        s.append(f"CT{k} tnk{k} 0 {CT_F}f\n")

    # ---- gate schedules, committed edges, repeated every PERIOD ps ----
    gtu, gfw, gmn, gmp = [], [], [], []
    marks = []
    for p in range(npulse):
        d = PERIOD * p
        gtu += [(0.0 + d, 1.5), (9.978 + d, 1.5), (13.978 + d, 0.0),
                (65.978 + d, 0.0), (67.978 + d, 1.5)]
        gfw += [(0.0 + d, 1.5), (17.978 + d, 1.5), (41.978 + d, 0.0),
                (65.978 + d, 0.0), (67.978 + d, 1.5)]
        if early:
            # mux closed from the start of this pulse: nbx never floats away
            # from the selected tank.  Same OPEN edge as committed.
            gmn += [(0.0 + d, 1.5), (72.042 + d, 1.5), (74.042 + d, 0.0)]
            gmp += [(0.0 + d, 0.0), (72.042 + d, 0.0), (74.042 + d, 1.5)]
        else:
            gmn += [(0.0 + d, 0.0), (39.978 + d, 0.0), (41.978 + d, 1.5),
                    (72.042 + d, 1.5), (74.042 + d, 0.0)]
            gmp += [(0.0 + d, 1.5), (39.978 + d, 1.5), (41.978 + d, 0.0),
                    (72.042 + d, 0.0), (74.042 + d, 1.5)]
        marks.append((p, 41.978 + d, 74.042 + d))

    def pwl(name, node, pts):
        # strip duplicate leading time-0 points that a repeat would create
        out, last_t = [], None
        for t, v in pts:
            if last_t is not None and t <= last_t:
                t = last_t + 1e-4
            out.append(f"{t:g}p {v}")
            last_t = t
        return f"V{name} {node} 0 PWL(" + " ".join(out) + ")\n"

    s.append(pwl("GTU", "gtu", gtu))
    s.append(pwl("GFW", "gfw", gfw))
    s.append(pwl("GMN0", "gmn0", gmn))
    s.append(pwl("GMP0", "gmp0", gmp))
    for k in range(1, n):
        s.append(f"VGMN{k} gmn{k} 0 0\n")
        s.append(f"VGMP{k} gmp{k} 0 1.5\n")

    s.append(integ("qsup", "-I(VSUP)"))
    metered = [("QSUP", "xqsup")]
    if qdel:
        s.append(integ("qdel", "I(VMTU)"))
        s.append(integ("qgm", "-I(VGMN0)"))
        metered += [("QDEL", "xqdel"), ("QGM", "xqgm")]

    ics = (f"V(na)={na0} V(nb)={na0} V(nbx)=0.66 "
           + " ".join(f"V(tnk{k})=0.66" for k in range(n)))
    s.append(f".ic {ics}\n")
    s.append(f".tran 0.05p {tstop:g}p 0 0.0884183p\n")

    for nm, node in metered:
        s.append(f".measure tran {nm}_Z FIND V({node}) AT=1.500000p\n")
        s.append(f".measure tran {nm}_E FIND V({node}) AT={tstop-1:.6f}p\n")
    # tank 0 sampled while the mux is OPEN (tank isolated) after each pulse
    for p, t_on, t_off in marks:
        s.append(f".measure tran VT0_P{p} FIND V(tnk0) AT={t_off+12.0:.6f}p\n")
        s.append(f".measure tran VNBX_ON{p} FIND V(nbx) AT={t_on-0.1:.6f}p\n")
    s.append(f".measure tran VT0E FIND V(tnk0) AT={tstop-1:.6f}p\n")
    if n > 1:
        s.append(f".measure tran VT1E FIND V(tnk1) AT={tstop-1:.6f}p\n")
        s.append(f".measure tran VTLE FIND V(tnk{n-1}) AT={tstop-1:.6f}p\n")
    s.append(f".measure tran VNBXPK MAX V(nbx) FROM=0 TO={tstop-1:g}p\n")
    s.append(f".measure tran VNBXMN MIN V(nbx) FROM=0 TO={tstop-1:g}p\n")
    s.append(f".measure tran ILPK MAX I(LTU) FROM=0 TO={tstop-1:g}p\n")
    pr = "V(na) V(nbx) V(tnk0) I(LTU)" + (" V(xqdel)" if qdel else "")
    s.append(f"\n.print tran {pr}\n.end\n")
    open(path, "w").write("".join(s))
    return path


# committed banktank bank-1 input pattern (4 high / 4 low), verbatim
PAT8 = [1.2, 1.2, 1.2, 0, 1.2, 0, 0, 1.2]


def droop_deck(path, ngate=8, ctank=CT_F, lt=15.0, rs=10.0, vt0=0.66):
    """ONE tank -> L -> R -> committed TG -> ONE bank, ONE rise+return cycle
    on the committed bank-1 ZCS window.  No top-up of any kind."""
    s = [HDR]
    s.append("VHI vhi 0 1.5\n")
    s.append("VMG gn 0 0\n")
    pat = [PAT8[i % 8] for i in range(ngate)]
    for i, v in enumerate(pat):
        s.append(f"VI{i} in{i} 0 {v}\n")
        s.append(f"XP{i} o{i} in{i} rail rail sg13_lv_pmos w=1.12u l=0.13u\n")
        s.append(f"XN{i} o{i} in{i} gn gn sg13_lv_nmos w=0.74u l=0.13u\n")
        s.append(f"CL{i} o{i} gn 2f\n")
    s.append(f"CT tnk 0 {ctank}f\n")
    s.append(f"LT tnk mid {lt}n\n")
    s.append(f"RT mid sw {rs}\n")
    s.append("XSWN sw gt rail 0 sg13_lv_nmos w=10u l=0.13u\n")
    s.append("XSWP sw gtp rail vhi sg13_lv_pmos w=20u l=0.13u\n")
    s.append("XPK sw pk tnk tnk sg13_lv_nmos w=2u l=0.13u\n")
    tc, ta = 200.0, 318.184          # rise  close / open (committed ZCS)
    tr, tb = 1000.0, 1129.370        # return close / open (committed ZCS)
    gt = f"PWL(0 0.0 {tc-2}p 0.0 {tc}p 1.5 {ta}p 1.5 {ta+2}p 0.0 {tr-2}p 0.0 {tr}p 1.5 {tb}p 1.5 {tb+2}p 0.0)"
    gtp = f"PWL(0 1.5 {tc-2}p 1.5 {tc}p 0.0 {ta}p 0.0 {ta+2}p 1.5 {tr-2}p 1.5 {tr}p 0.0 {tb}p 0.0 {tb+2}p 1.5)"
    s.append(f"VGT gt 0 {gt}\n")
    s.append(f"VGTP gtp 0 {gtp}\n")
    s.append(f"VPK pk 0 {gtp}\n")
    s.append(integ("qlt", "I(LT)"))
    s.append(integ("qin", "-(" + "+".join(f"I(VI{i})" for i in range(ngate)) + ")"))
    s.append(f".ic V(tnk)={vt0} V(rail)=0 V(sw)={vt0}\n")
    s.append(".tran 0.1p 1400.000p 0 0.25p\n")
    s.append(".measure tran QLT_Z FIND V(xqlt) AT=1.500000p\n")
    s.append(".measure tran QIN_Z FIND V(xqin) AT=1.500000p\n")
    # tank, sampled while the transfer gate is OPEN (tank isolated)
    s.append(f".measure tran VT_A FIND V(tnk) AT={tc-1:.6f}p\n")       # before rise
    s.append(f".measure tran VT_B FIND V(tnk) AT={ta+2.5:.6f}p\n")     # after rise open
    s.append(f".measure tran VT_C FIND V(tnk) AT={tr-1:.6f}p\n")       # before return
    s.append(f".measure tran VT_D FIND V(tnk) AT={tb+2.5:.6f}p\n")     # after return open
    # delivered rail
    s.append(f".measure tran VR_ZCS FIND V(rail) AT={ta:.6f}p\n")      # AT the ZCS instant
    s.append(f".measure tran VR_FT FIND V(rail) AT={ta+2.5:.6f}p\n")   # after the 2 ps gate ramp
    s.append(f".measure tran VR_PK MAX V(rail) FROM={tc:.6f}p TO={ta:.6f}p\n")
    s.append(f".measure tran VR_H100 FIND V(rail) AT={ta+102.5:.6f}p\n")
    s.append(f".measure tran VR_H300 FIND V(rail) AT={ta+302.5:.6f}p\n")
    s.append(f".measure tran VR_END FIND V(rail) AT={tr-1:.6f}p\n")
    # ZCS residual at both commanded opens
    s.append(f".measure tran IZ_R FIND I(LT) AT={ta:.6f}p\n")
    s.append(f".measure tran IZ_Q FIND I(LT) AT={tb:.6f}p\n")
    # L-integrator over the RISE sub-window only (where it must agree with C dV)
    s.append(f".measure tran QLT_A FIND V(xqlt) AT={tc-1:.6f}p\n")
    s.append(f".measure tran QLT_B FIND V(xqlt) AT={ta:.6f}p\n")
    s.append(f".measure tran QLT_D FIND V(xqlt) AT={tb+2.5:.6f}p\n")
    for i in range(ngate):
        s.append(f".measure tran O{i}S FIND V(o{i}) AT={ta+302.5:.6f}p\n")
    s.append("\n.print tran V(tnk) V(rail) V(sw) I(LT) V(xqlt)\n.end\n")
    open(path, "w").write("".join(s))
    return path


if __name__ == "__main__":
    made = []
    # --- controls: byte-faithful re-runs of the balance run's mux decks ---
    made.append(mux_deck("sk_mx_c1.cir",  1))
    made.append(mux_deck("sk_mx_c16.cir", 16))
    # --- H1 / S1: mux closed from t=0 so the shared node never floats away ---
    made.append(mux_deck("sk_mx_e1.cir",  1,  early=True))
    made.append(mux_deck("sk_mx_e16.cir", 16, early=True))
    # --- S2: width sweep at N=16 on the committed schedule ---
    made.append(mux_deck("sk_mx_w16h.cir", 16, wn=2.5, wp=5.0))
    made.append(mux_deck("sk_mx_w16d.cir", 16, wn=10.0, wp=20.0))
    # --- transient vs steady state: two back-to-back pulses ---
    made.append(mux_deck("sk_mx_p2_c16.cir", 16, npulse=2, tstop=200.0))
    made.append(mux_deck("sk_mx_p2_e16.cir", 16, early=True, npulse=2, tstop=200.0))
    # --- my own tank droop ---
    made.append(droop_deck("sk_droop8.cir", ngate=8))
    for m in made:
        print(m)
