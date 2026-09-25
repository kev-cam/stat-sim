#!/usr/bin/env python3
"""Generate the QAL C5 CLOSED-LOOP steady-state rail-draw deck.

WHAT THIS MEASURES
------------------
The true QAL energy per op as the user defines it: the energy drawn from the
+-1.5 V rails, per op, by a RUNNING QAL loop.  No CMOS quantity enters the number
(no E_cell, no f_adia, no model factor) -- it is a supply integral on a closed,
self-sustaining loop built from real SG13G2/PSP103 devices.

TOPOLOGY (C5: permanently-connected 5-tier stack -- the architecture-native recharge)
------------------------------------------------------------------------------------
  VRP(+1.5) --RSER-- s5 --CS5-- s4 --CS4-- s3 --CS3-- s2 --CS2-- s1 --CS1-- VRN(-1.5)
  Tier boundaries land at -1.5/-0.9/-0.3/+0.3/+0.9/+1.5 because 3.0/0.6 = 5 EXACTLY,
  so every tier rail already sits at the bank swing dV: no level conversion, no
  recharge switch, no converter, no magnetics anywhere on the recharge path.

  TIER 3 (lg = s2 = -0.3 V, ls = s3 = +0.3 V) carries the ONE REAL QAL lane:
    - banks BA, BB (CB each) referenced to the tier-local ground lg
    - each bank carries a REAL settling inverter powered bank->lg, so the gate
      SETTLE loss is inside the metered boundary (never added on afterwards)
    - inter-bank inductive recycle BA <-LAB+RAB-> BB through a REAL nMOS switch,
      bidirectional: the wave ping-pongs, one hop = one op, the loop is CLOSED and
      runs to a genuine limit cycle rather than draining a pre-charged bank
    - flycaps CFA/CFB, each PERMANENTLY wired to the tier rail ls through RRC --
      no switch, no inductor, no converter on the recharge path (the C5 point).
      Because ls already sits at dV, the recharge endpoint EQUALS its source
      voltage, so the first-order level-mismatch term (V_rail - dV)*q is
      identically zero; only the second-order 1/2*C*droop^2 term survives.
    - each flycap dumps into its bank through its OWN inductor + its OWN real
      nMOS switch, concurrently with the inter-bank recycle (the user's mechanism)
    - switch gates driven by REAL CMOS inverters powered from stack nodes, so the
      gate-drive energy is drawn from the metered rails

  EVERY TIER (including tier 3) also carries RTLk: one resistor standing in for the
  OTHER lanes sharing that tier in a real chip.  Resistive, not an ideal current
  sink, for two reasons: it can only ABSORB (never source), and it self-regulates,
  which is what holds the series stack balanced.  Its dissipation is metered
  separately (ETL) and subtracted, so it never enters the lane's number.

HAZARD GUARDS BAKED IN
----------------------
  G1  only VRP/VRN supply energy.  No .IC, no .NODESET, no UIC, no tanh()
      conductance, no VSWITCH.  Real PSP103 devices, bulks connected.  DCOP (not
      UIC) sets the operating point, so there is no UIC startup impulse at all.
      Every 0 V source is an ammeter; EAMM asserts they inject exactly zero.
  G2  the checker asserts exit code 0 AND last TIME row >= end of every window.
  G3  metering validated against E_rail = V*Q (m0_meter.cir: 1.500000 V, 0.0000%),
      and re-checked on every run (constant rails => ERAIL/QRAIL must be 3.000 V).
      Metering uses .measure INTEGRAL {expr}; NEVER a B-source, because a
      node/device name collision silently makes V(x) return I(x) inside a B-source
      expression -- found and documented in m0dbg.cir.
  G4  every dissipator is metered, INCLUDING full 4-terminal device power for all
      three switches and both settling gates (ammeters on drain/gate/source, with
      the tier-local ground s2 as the common reference so bulk terms vanish).
      dE_stored sums 1/2CV^2 over every capacitor and 1/2LI^2 over every inductor
      at the two instants bounding the integral.
  G5  the measure window starts after NWARM warm-up periods; the warm-up draw is
      reported as its own line item and excluded.
  G6  per-op rail draw op by op, plus the full state vector (every node voltage,
      every inductor current) at both window bounds, which are period-aligned.
"""
import argparse

HDL = '.hdl "/usr/local/share/xyce/verilog-a/psp103/psp103.va"'
LIB = '.include "/usr/local/src/kestrel/sim/models/sg13g2_psp103_tt.lib"'
CMP = '.include "/usr/local/src/stat-sim/qal/sg13lv_compat.sp"'

# Nodes whose voltage is snapshotted for dE_stored and the state-vector test.
STACK_NODES = ["s1", "s2", "s3", "s4", "s5", "rp", "rn", "drvp", "drvn",
               "gsab", "gsta", "gstb"]
ATTN_NODES = ["dvab", "dvta", "dvtb", "vmid"]
LANE_NODES = ["ba", "bb", "fa", "fb", "oa", "ob", "mab", "mta", "mtb",
              "s_sab", "s_sta", "s_stb"]
# (name, param, +node, -node) for every capacitor in the deck
CAPS = [("CS5", "CS", "s5", "s4"), ("CS4", "CS", "s4", "s3"), ("CS3", "CS", "s3", "s2"),
        ("CS2", "CS", "s2", "s1"), ("CS1", "CS", "s1", "rn")]
LANE_CAPS = [("CBA", "CB", "ba", "s2"), ("CBB", "CB", "bb", "s2"),
             ("CFA", "CFLY", "fa", "s2"), ("CFB", "CFLY", "fb", "s2"),
             ("COA", "CLOAD", "oa", "s2"), ("COB", "CLOAD", "ob", "s2"),
             ("CMAB", "CPAR", "mab", "s2"), ("CMTA", "CPAR", "mta", "s2"),
             ("CMTB", "CPAR", "mtb", "s2")]
LANE_INDS = [("LAB", "LAB"), ("LTA", "LT"), ("LTB", "LT")]


def switch(A, tag, dnode, gnode, snode, w):
    """Emit a real nMOS pass switch with ammeters on drain, gate and source.

    Bulk is tied straight to s2 (the tier-local ground).  Because s2 is used as
    the common reference for the power sum, the bulk term is identically zero, so
    (V_d-V_s2)*I_d + (V_g-V_s2)*I_g + (V_s-V_s2)*I_s is the TOTAL power into the
    device -- conduction plus every displacement/junction/tunnelling component.
    Integrated over an integer number of steady-state periods that is exactly the
    device's dissipation, with no window guessing and no I^2R over a guessed arc.
    """
    A("* NOTE the node names are d_/g_/s_ prefixed: Xyce is CASE-INSENSITIVE, so a")
    A("* gate node spelled g%s would collide with the driver output %s and make the"
      % (tag, gnode))
    A("* ammeter a 0 V source with both ends on ONE node -> singular matrix.")
    A("VM%sD %s d_%s 0" % (tag, dnode, tag))          # into drain
    A("VM%sG %s g_%s 0" % (tag, gnode, tag))          # into gate
    A("VM%sS s_%s %s 0" % (tag, tag, snode))          # OUT of source
    A("X%s d_%s g_%s s_%s s2 sg13_lv_nmos w=%s l=0.13u" % (tag, tag, tag, tag, w))


def switch_power(tag):
    return ("(V(d_%s)-V(s2))*I(VM%sD)+(V(g_%s)-V(s2))*I(VM%sG)"
            "-(V(s_%s)-V(s2))*I(VM%sS)" % (tag, tag, tag, tag, tag, tag))


def deck(p):
    Thop, dV = p.Thop, p.dV
    Tp = 2.0 * Thop * p.duty
    half = Tp / 2.0
    tr = p.tr
    tstop = p.nper * Tp
    t0 = p.nwarm * Tp
    t1 = tstop

    L, A = [], None
    out = []
    A = out.append
    A("* QAL C5 CLOSED-LOOP steady-state rail-draw deck (generated by gen_c5loop.py)")
    A("* dV=%g Thop=%gps Tperiod=%gps nper=%d nwarm=%d window %gp..%gp (%d ops)"
      % (dV, Thop, Tp, p.nper, p.nwarm, t0, t1, 2 * (p.nper - p.nwarm)))
    A("* CB=%s CFLY=%s CS=%s LAB=%s LT=%s RRC=%s RTL=%s" %
      (p.CB, p.CFLY, p.CS, p.LAB, p.LT, p.RRC, p.RTL))
    A("* WSW=%s WDRV=%s/%s WGATE=%s  driver supply %s..%s swing %gV  pattern=%s  lane=%s"
      % (p.WSW, p.WDRV, p.WDRVN, p.WGATE, p.DRVTOP, p.DRVBOT, p.VCKH, p.pattern,
         "YES" if p.lane else "NO"))
    A(HDL); A(LIB); A(CMP)
    A(".OPTIONS TIMEINT METHOD=GEAR RELTOL=%s ABSTOL=%s" % (p.reltol, p.abstol))
    A(".param dV=%g CS=%s CB=%s CFLY=%s CPAR=%s CLOAD=%s"
      % (dV, p.CS, p.CB, p.CFLY, p.CPAR, p.CLOAD))
    A(".param LAB=%s RAB=%s LT=%s RT=%s RRC=%s" % (p.LAB, p.RAB, p.LT, p.RT, p.RRC))
    A(".param RTL=%s RSER=%s RBL=%s VCKH=%g CCP=%s RDC=%s"
      % (p.RTL, p.RSER, p.RBL, p.VCKH, p.CCP if p.CCP != "0" else "1f", p.RDC))
    A("")
    A(".subckt INVQ vdd vss vin vout bp bn wp=1u wn=0.5u")
    A("XP vout vin vdd bp sg13_lv_pmos w={wp} l=0.13u")
    A("XN vout vin vss bn sg13_lv_nmos w={wn} l=0.13u")
    A(".ends")
    A("")
    A("* ============ THE ONLY TWO ENERGY SOURCES IN THE DECK ============")
    A("VRP rp 0 1.5")
    A("VRN rn 0 -1.5")
    A("RSERI rp s5 {RSER}")
    A("* hard-wired 5-tier stack: the recharge path is DC interconnect. No switch.")
    A("CS5 s4 s5 {CS}")
    A("CS4 s3 s4 {CS}")
    A("CS3 s2 s3 {CS}")
    A("CS2 s1 s2 {CS}")
    A("CS1 rn s1 {CS}")
    A("* stand-in lanes: one resistor per tier, identical on all five.")
    A("RTL1 s1 rn {RTL}")
    A("RTL2 s2 s1 {RTL}")
    A("RTL3 s3 s2 {RTL}")
    A("RTL4 s4 s3 {RTL}")
    A("RTL5 s5 s4 {RTL}")
    A("")
    if p.lane:
        A("* ============ TIER 3: THE ONE REAL QAL LANE ============")
        A("* ---- bank A: cap + a REAL settling inverter powered bank->lg ----")
        A("CBA ba s2 {CB}")
        A("RBLA ba s2 {RBL}")
        A("VMGAD ba gav 0")
        A("VMGAB s3 gabp 0")
        A("XGA gav s2 %s oa gabp s2 INVQ wp=%s wn=%s" % (p.pinA, p.WGATE, p.WGATE))
        A("COA oa s2 {CLOAD}")
        A("* ---- bank B ----")
        A("CBB bb s2 {CB}")
        A("RBLB bb s2 {RBL}")
        A("VMGBD bb gbv 0")
        A("VMGBB s3 gbbp 0")
        A("XGB gbv s2 %s ob gbbp s2 INVQ wp=%s wn=%s" % (p.pinB, p.WGATE, p.WGATE))
        A("COB ob s2 {CLOAD}")
        A("")
        A("* ---- inter-bank inductive recycle, bidirectional, opens at ZCS ----")
        A("LAB ba xab {LAB}")
        A("RABS xab mab {RAB}")
        A("CMAB mab s2 {CPAR}")
        switch(A, "SAB", "mab", "gsab", "bb", p.WSW)
        A("")
        A("* ---- flycap A: PERMANENTLY connected to tier rail ls through RRC ----")
        A("CFA fa s2 {CFLY}")
        A("RRCA s3 fa {RRC}")
        A("LTA fa xta {LT}")
        A("RTAS xta mta {RT}")
        A("CMTA mta s2 {CPAR}")
        switch(A, "STA", "mta", "gsta", "ba", p.WSW)
        A("* ---- flycap B ----")
        A("CFB fb s2 {CFLY}")
        A("RRCB s3 fb {RRC}")
        A("LTB fb xtb {LT}")
        A("RTBS xtb mtb {RT}")
        A("CMTB mtb s2 {CPAR}")
        switch(A, "STB", "mtb", "gstb", "bb", p.WSW)
        A("")
    A("* ---- REAL gate drivers, supply %s..%s ----" % (p.DRVTOP, p.DRVBOT))
    A("* MEASURED STRUCTURAL CONSTRAINT: a 0.6 V tier cannot drive its own switch")
    A("* gates (an nMOS passing up to the tier top needs V_top + Vt), so the gate")
    A("* drive has to reach outside the tier.  DRVTOP/DRVBOT expose that choice:")
    A("*   s4..s2 = 1.2 V, two tiers -> within the 1.2 V SG13G2 oxide rating, but")
    A("*            it is a DC bypass current around the tier caps it skips.")
    A("*   rp..rn = 3.0 V, full span -> passes through NO tier cap so it cannot")
    A("*            unbalance the stack, but it is 2.5x the oxide rating.")
    A("* Both are measured rather than assumed. See the report.")
    A("VMDRV %s drvp 0" % p.DRVTOP)
    A("VMDRVN drvn %s 0" % p.DRVBOT)
    o1, o2, o3 = ("dvab", "dvta", "dvtb") if p.CCP != "0" else ("gsab", "gsta", "gstb")
    A("XDAB drvp drvn ckab %s drvp drvn INVQ wp=%s wn=%s" % (o1, p.WDRV, p.WDRVN))
    A("XDTA drvp drvn ckta %s drvp drvn INVQ wp=%s wn=%s" % (o2, p.WDRV, p.WDRVN))
    A("XDTB drvp drvn cktb %s drvp drvn INVQ wp=%s wn=%s" % (o3, p.WDRV, p.WDRVN))
    if p.CCP != "0":
        A("")
        A("* ---- CAPACITIVE GATE ATTENUATOR (the escape from the 3.0 V dilemma) ----")
        A("* MEASURED DILEMMA: on a 5-tier stack at dV=0.6 V, a supply is BALANCED only")
        A("* if it spans all five tiers, i.e. 3.0 V -- 2.5x the SG13G2 oxide rating. Any")
        A("* narrower span is a DC bypass around the tier caps it skips and the stack")
        A("* drifts (measured: tiers 3,4 fell 0.600->0.436 V while 1,2,5 rose to 0.702).")
        A("* ESCAPE: keep the BALANCED full-span driver, then AC-couple its output to")
        A("* the switch gate through CCP and DC-restore the gate through RDC to a")
        A("* tier-local reference. The gate then swings 3.0*CCP/(CCP+Cg) -- back inside")
        A("* rating -- while the only DC current in the restore path is leakage, so the")
        A("* tier balance is preserved. Gate swing is MEASURED (VGABPK/VGABMN), not assumed.")
        A("RVMA s3 vmid 1meg")
        A("RVMB vmid s4 1meg")
        for o, g in (("dvab", "gsab"), ("dvta", "gsta"), ("dvtb", "gstb")):
            A("CCP_%s %s %s {CCP}" % (g, o, g))
            A("RDC_%s %s vmid {RDC}" % (g, g))
    if not p.lane:
        A("* no lane: terminate the switch-gate nodes so they are not floating")
        A("RTG1 gsab drvn 1e12")
        A("RTG2 gsta drvn 1e12")
        A("RTG3 gstb drvn 1e12")
    A("")
    A("* ---- phase clocks: they drive ONLY the driver input gates. ----")
    A("* Active LOW into an inverting driver, so a switch gate is HIGH when ON.")
    A("* SWAB conducts on BOTH hops, so its period is HALF the loop period.")
    A("* Hop occupies the first %gps of each %gps half-period." % (Thop, half))
    A("VCKAB ckab drvn PULSE({VCKH} 0 0 %gp %gp %gp %gp)" % (tr, tr, Thop - tr, half))
    A("VCKTA ckta drvn PULSE({VCKH} 0 %gp %gp %gp %gp %gp)"
      % (half, tr, tr, Thop - tr, Tp))
    A("VCKTB cktb drvn PULSE({VCKH} 0 0 %gp %gp %gp %gp)" % (tr, tr, Thop - tr, Tp))
    A("")
    A(".tran %gp %gp 0 %gp" % (p.tstep, tstop, p.tmax))
    A("")
    W = " FROM=%gp TO=%gp" % (t0, t1)
    A("* ==================== METERS ====================")
    A("* headline: energy and charge drawn from the two rails")
    A(".measure tran ERAIL INTEGRAL {-V(rp)*I(VRP)-V(rn)*I(VRN)}" + W)
    A(".measure tran QRAIL INTEGRAL {-I(VRP)}" + W)
    A(".measure tran ERAILW INTEGRAL {-V(rp)*I(VRP)-V(rn)*I(VRN)} FROM=0 TO=%gp" % t0)
    A(".measure tran ERP INTEGRAL {-V(rp)*I(VRP)}" + W)
    A(".measure tran ERN INTEGRAL {-V(rn)*I(VRN)}" + W)
    A("* not-the-lane: stand-in lanes, stack series R")
    A(".measure tran ETL INTEGRAL {{RTL}*(I(RTL1)*I(RTL1)+I(RTL2)*I(RTL2)"
      "+I(RTL3)*I(RTL3)+I(RTL4)*I(RTL4)+I(RTL5)*I(RTL5))}" + W)
    A(".measure tran ERSER INTEGRAL {{RSER}*I(RSERI)*I(RSERI)}" + W)
    A("* gate-driver supply (the switch gate drive)")
    A("* Driver-domain input power. NOTE it must use BOTH supply leads separately:")
    A("* (V(drvp)-V(drvn))*I(VMDRV) is only valid if the two leads carry equal and")
    A("* opposite current, and they do NOT -- the gate coupling caps are a third path")
    A("* out of the driver domain into the tier. Using the two-terminal form left a")
    A("* 9.19%% hole in the energy balance; this form closes it.")
    A(".measure tran EDRV INTEGRAL {V(drvp)*I(VMDRV)-V(drvn)*I(VMDRVN)}" + W)
    A(".measure tran EDRV2T INTEGRAL {(V(drvp)-V(drvn))*I(VMDRV)}" + W)
    A("* phase-clock PWL sources: energy they inject (declared line item)")
    A(".measure tran ECK INTEGRAL {-(V(ckab)-V(drvn))*I(VCKAB)"
      "-(V(ckta)-V(drvn))*I(VCKTA)-(V(cktb)-V(drvn))*I(VCKTB)}" + W)
    amm = ["-(V(%s)-V(drvp))*I(VMDRV)" % p.DRVTOP,
           "-(V(drvn)-V(%s))*I(VMDRVN)" % p.DRVBOT]
    if p.lane:
        A("* inductor series-R loss (exact I^2R, no window guessing)")
        A(".measure tran ELAB INTEGRAL {{RAB}*I(LAB)*I(LAB)}" + W)
        A(".measure tran ELTA INTEGRAL {{RT}*I(LTA)*I(LTA)}" + W)
        A(".measure tran ELTB INTEGRAL {{RT}*I(LTB)*I(LTB)}" + W)
        A("* flycap RECHARGE loss -- the term that was never simulated before")
        A(".measure tran ERCA INTEGRAL {{RRC}*I(RRCA)*I(RRCA)}" + W)
        A(".measure tran ERCB INTEGRAL {{RRC}*I(RRCB)*I(RRCB)}" + W)
        A("* bank DC bleeds (metering artefact, must be negligible)")
        A(".measure tran EBLD INTEGRAL {{RBL}*(I(RBLA)*I(RBLA)+I(RBLB)*I(RBLB))}" + W)
        A("* TOTAL power into each switch, all terminals, s2 as common reference")
        A(".measure tran ESWAB INTEGRAL {%s}%s" % (switch_power("SAB"), W))
        A(".measure tran ESWTA INTEGRAL {%s}%s" % (switch_power("STA"), W))
        A(".measure tran ESWTB INTEGRAL {%s}%s" % (switch_power("STB"), W))
        A("* TOTAL power into each SETTLING GATE (the adiabatic settle loss)")
        A(".measure tran EGA INTEGRAL {(V(gav)-V(s2))*I(VMGAD)"
          "+(V(gabp)-V(s2))*I(VMGAB)}" + W)
        A(".measure tran EGB INTEGRAL {(V(gbv)-V(s2))*I(VMGBD)"
          "+(V(gbbp)-V(s2))*I(VMGBB)}" + W)
        amm += ["-(V(ba)-V(gav))*I(VMGAD)", "-(V(bb)-V(gbv))*I(VMGBD)",
                "-(V(s3)-V(gabp))*I(VMGAB)", "-(V(s3)-V(gbbp))*I(VMGBB)"]
        for t, dn, sn in (("SAB", "mab", "bb"), ("STA", "mta", "ba"), ("STB", "mtb", "bb")):
            amm += ["-(V(%s)-V(d_%s))*I(VM%sD)" % (dn, t, t),
                    "-(V(gs%s)-V(g_%s))*I(VM%sG)" % (t[1:].lower(), t, t),
                    "-(V(s_%s)-V(%s))*I(VM%sS)" % (t, sn, t)]
    A("* 0 V ammeters must inject exactly zero -- they are ammeters, not sources")
    A(".measure tran EAMM INTEGRAL {%s}%s" % ("".join(amm), W))
    A("")
    A("* ============ stored energy / state vector at both window bounds ============")
    nodes = list(STACK_NODES) + (LANE_NODES if p.lane else [])
    if p.CCP != "0":
        nodes += ATTN_NODES
    for tag, tt in (("A", t0), ("B", t1)):
        for n in nodes:
            A(".measure tran V%s%s FIND V(%s) AT=%gp" % (n.upper(), tag, n, tt))
        for n, _ in (LANE_INDS if p.lane else []):
            A(".measure tran I%s%s FIND I(%s) AT=%gp" % (n, tag, n, tt))
    A("")
    A("* ============ G6: per-op rail draw, op by op ============")
    for k in range(2 * p.nwarm, 2 * p.nper):
        A(".measure tran EOP%d INTEGRAL {-V(rp)*I(VRP)-V(rn)*I(VRN)} FROM=%gp TO=%gp"
          % (k, k * half, (k + 1) * half))
    for k in range(2 * p.nwarm, 2 * p.nper):
        A(".measure tran TOP%d INTEGRAL {{RTL}*(I(RTL1)*I(RTL1)+I(RTL2)*I(RTL2)"
          "+I(RTL3)*I(RTL3)+I(RTL4)*I(RTL4)+I(RTL5)*I(RTL5))} FROM=%gp TO=%gp"
          % (k, k * half, (k + 1) * half))
    A("* switch-gate swing actually achieved (oxide-rating check) + attenuator loss")
    A(".measure tran VGABPK MAX {V(gsab)-V(s2)}" + W)
    A(".measure tran VGABMN MIN {V(gsab)-V(s2)}" + W)
    if p.CCP != "0":
        A(".measure tran EVMID INTEGRAL {(V(s3)-V(vmid))*I(RVMA)+(V(vmid)-V(s4))*I(RVMB)"
          "+{RDC}*(I(RDC_gsab)*I(RDC_gsab)+I(RDC_gsta)*I(RDC_gsta)"
          "+I(RDC_gstb)*I(RDC_gstb))}" + W)
    A("* tier voltages: do they stay near dV and never go negative?")
    for i, (a, b) in enumerate([("s1", "rn"), ("s2", "s1"), ("s3", "s2"),
                                ("s4", "s3"), ("s5", "s4")], 1):
        A(".measure tran TVMIN%d MIN {V(%s)-V(%s)}%s" % (i, a, b, W))
        A(".measure tran TVMAX%d MAX {V(%s)-V(%s)}%s" % (i, a, b, W))
    if p.lane:
        A("* bank swing in the last period: is the wave sustaining at dV?")
        A(".measure tran VBAPK MAX {V(ba)-V(s2)} FROM=%gp TO=%gp" % (t1 - Tp, t1))
        A(".measure tran VBBPK MAX {V(bb)-V(s2)} FROM=%gp TO=%gp" % (t1 - Tp, t1))
        A(".measure tran VBAMN MIN {V(ba)-V(s2)} FROM=%gp TO=%gp" % (t1 - Tp, t1))
        A(".measure tran VBBMN MIN {V(bb)-V(s2)} FROM=%gp TO=%gp" % (t1 - Tp, t1))
        A(".measure tran VFAMN MIN {V(fa)-V(s2)} FROM=%gp TO=%gp" % (t1 - Tp, t1))
        A(".measure tran VFBMN MIN {V(fb)-V(s2)} FROM=%gp TO=%gp" % (t1 - Tp, t1))
        A(".measure tran VOAPK MAX {V(oa)-V(s2)} FROM=%gp TO=%gp" % (t1 - Tp, t1))
    A("")
    pl = "V(rp) V(rn) V(s1) V(s2) V(s3) V(s4) V(s5) V(gsab) I(VRP) I(VRN)"
    if p.lane:
        pl += " V(ba) V(bb) V(fa) V(fb) V(oa) V(ob) I(LAB) I(LTA) I(LTB)"
    A(".print tran format=csv " + pl)
    A(".end")
    A("")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="c5loop.cir")
    ap.add_argument("--dV", type=float, default=0.6)
    ap.add_argument("--Thop", type=float, default=100.0)
    ap.add_argument("--duty", type=float, default=2.0)
    ap.add_argument("--tr", type=float, default=10.0)
    ap.add_argument("--nper", type=int, default=20)
    ap.add_argument("--nwarm", type=int, default=12)
    ap.add_argument("--tstep", type=float, default=0.5)
    ap.add_argument("--tmax", type=float, default=0.5)
    ap.add_argument("--CS", default="2p")
    ap.add_argument("--CB", default="80f")
    ap.add_argument("--CFLY", default="15f")
    ap.add_argument("--CPAR", default="2f")
    ap.add_argument("--CLOAD", default="10f")
    ap.add_argument("--LAB", default="25n")
    ap.add_argument("--RAB", default="10")
    ap.add_argument("--LT", default="80n")
    ap.add_argument("--RT", default="10")
    ap.add_argument("--RRC", default="1k")
    ap.add_argument("--RBL", default="10meg")
    ap.add_argument("--RTL", default="50k")
    ap.add_argument("--RSER", default="5")
    ap.add_argument("--WSW", default="10u")
    ap.add_argument("--WDRV", default="2u")
    ap.add_argument("--WDRVN", default="1u")
    ap.add_argument("--WGATE", default="1u")
    ap.add_argument("--DRVTOP", default="s4")
    ap.add_argument("--DRVBOT", default="s2")
    ap.add_argument("--VCKH", type=float, default=1.2)
    ap.add_argument("--CCP", default="0")    # gate coupling cap; "0" = direct drive
    ap.add_argument("--RDC", default="1meg") # gate DC-restore resistor
    ap.add_argument("--pattern", default="d0")
    ap.add_argument("--nolane", action="store_true")
    ap.add_argument("--reltol", default="1e-5")
    ap.add_argument("--abstol", default="1e-14")
    p = ap.parse_args()
    p.lane = not p.nolane
    p.pinA = "s2" if p.pattern == "d0" else "s3"
    p.pinB = "s2" if p.pattern == "d0" else "s3"
    open(p.out, "w").write(deck(p))
    Tp = 2.0 * p.Thop * p.duty
    print("wrote %s  window %gp..%gp  %d ops  period %gp  tstop %gp"
          % (p.out, p.nwarm * Tp, p.nper * Tp, 2 * (p.nper - p.nwarm), Tp, p.nper * Tp))


if __name__ == "__main__":
    main()
