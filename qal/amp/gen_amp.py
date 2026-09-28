#!/usr/bin/env python3
"""TRACK B deck generator: a REAL SG13G2 sustaining amplifier against a REAL LC
tank carrying the REAL gt/gtp tap loads of the committed QAL hop.

Every deck is a TEXT PATCH of /usr/local/src/stat-sim/qal/recov/skeptic/sk_best.cir
(itself a patch of the committed swsweep/sw_tg15p_z.cir).  REMOVED: the two ideal
PWL tap sources VGTS/VGPS, their 25 ohm series resistors, and the four integrator
blocks that reference I(VGTS)/I(VGPS).  KEPT UNCHANGED: the entire hop network, the
8 cells, the 1.5 V pMOS-bulk rail VHI, and the ideal-PWL park VPK (the park is
track A's term; leaving it untouched keeps this row comparable to the committed one).
ADDED: the tank, the amplifier, its bias, and their own 1F integrators.

TOPOLOGY
--------
  VA(0.85) --RP-- LP -- gts  --RGTS 25-- gt    (nMOS switch gate, C_eff 5.8 fF MEASURED)
  VA(0.85) --RN-- LN -- gtsn --CBLK-- gps --RGPS 25-- gtp (pMOS gate, C_eff 12.5 fF)
                                      gps --LBQ--RBQ-- VB(0.41)
  XM1 (d=gts, g=gtsn), XM2 (d=gtsn, g=gts) cross-coupled nMOS, common source `tail`
  XMT tail nMOS to ground, gate on a DC bias VBG -- a REAL DEVICE, not an ideal
      current source (an ideal tail source is exactly the booking this campaign has
      been burned by three times).

WHY THE DC-BLOCK + CHOKE IS NOT OPTIONAL: the committed waveform needs gt centred at
0.85 V and gtp at 0.41 V, both +-0.75 V, so gtp must be driven to -0.34 V, BELOW the
ground rail of any nMOS core.  A cross-coupled pair clamps its own drain at the tail
node and physically cannot make that excursion.  Isolating the gtp tap behind
CBLK/LBQ (nothing active touches gps) is what makes the sub-ground drive possible.

METERING: 1F integrators only, ALL read t=0-referenced -- the committed decks'
0.01 ohm integrator shunt puts a DC-operating-point offset on every can
(gate leakage x 0.01 ohm reads as fJ; on xegtp it is +12.135 fJ of phantom energy).
"""
import math, re

BASE = "/usr/local/src/stat-sim/qal/recov/skeptic/sk_best.cir"
W0   = 2*math.pi/580e-12            # 1.0833e10 rad/s -- the committed 580 ps beat

INTEG_NODES = []

def integ(tag, expr):
    INTEG_NODES.append('x'+tag)
    return ["CX%s x%s 0 1" % (tag, tag),
            "BX%s 0 x%s I={ %s }" % (tag, tag, expr),
            "RX%s x%s 0 0.01" % (tag, tag)]

def build(name, LP, LN, LBQ=5e-6, QIND=19.0, QBQ=19.0, WX=5.0, WT=2.0, VBG=0.55,
          VAR=0.85, VBR=0.41, CBLK=200e-15, RS=25.0, tend=5800.0, hop=False,
          icv=None, ctp=0.0, ctn=0.0, core="xc", gneg=0.0, kick=0.0, rload=0.0, isat=1e-4):
    src = open(BASE).read().splitlines()
    drop = re.compile(r'^(VGTS|RGTS|VGPS|RGPS|CXegt|BXegt|RXegt|CXqgt|BXqgt|RXqgt'
                      r'|CXegtp|BXegtp|RXegtp|CXqgtp|BXqgtp|RXqgtp)\b', re.I)
    del INTEG_NODES[:]
    RP, RN, RBQ = W0*LP/QIND, W0*LN/QIND, W0*LBQ/QBQ
    A = ["* ==== TRACK B: %s ====" % name,
         "* LP=%.5gH RP=%.4g LN=%.5gH RN=%.4g LBQ=%.4gH RBQ=%.4g Qind=%.4g"
         % (LP, RP, LN, RN, LBQ, RBQ, QIND),
         "* core=%s WX=%gu WT=%gu VBG=%g VA=%g VB=%g CBLK=%.4gF ctp=%.4g ctn=%.4g"
         % (core, WX, WT, VBG, VAR, VBR, CBLK, ctp, ctn),
         "VA va 0 %g" % VAR, "VB vb 0 %g" % VBR, "VBG vbg 0 %g" % VBG,
         "LP gts nap %g" % LP, "RP nap va %g" % RP,
         "LN gtsn nan %g" % LN, "RN nan va %g" % RN,
         "CBLK gtsn gps %g" % CBLK,
         "LBQ gps nbq %g" % LBQ, "RBQ nbq vb %g" % RBQ,
         "RGTS gts gt %g" % RS, "RGPS gps gtp %g" % RS]
    if kick:   # MEASUREMENT STIMULUS ONLY (resonance/ringdown probe). Never in a ledger.
        A += ["IKICK 0 gts PULSE(0 %g 1p 0.2p 0.2p 2p 1e-6)" % kick,
              "IKICKN 0 gtsn PULSE(0 %g 1p 0.2p 0.2p 2p 1e-6)" % (-kick)]
    if rload:   # calibrated EXTRA differential tank load: stands in for the
        # per-beat energy the hop actually extracts from the taps, so the marginal
        # cost of delivering it can be MEASURED rather than modelled.
        A += ["RLOAD gts gtsn %g" % rload]
    if ctp: A.append("CTP gts 0 %g" % ctp)
    if ctn: A.append("CTN gtsn 0 %g" % ctn)
    if core == "xc":
        A += ["VD1 gts d1 0", "XM1 d1 gtsn tail 0 sg13_lv_nmos w=%gu l=0.13u" % WX,
              "VD2 gtsn d2 0", "XM2 d2 gts tail 0 sg13_lv_nmos w=%gu l=0.13u" % WX,
              "VDT tail t0 0", "XMT t0 vbg 0 0 sg13_lv_nmos w=%gu l=0.13u" % WT]
    elif core == "idealneg":       # LOSSLESS negative conductance: a CEILING, labelled
        # tanh-limited so it forms a proper limit cycle; gneg = small-signal G,
        # isat = the limiting current.  This is an IDEAL SOURCE used deliberately
        # as a ceiling -- it has no supply and appears in NO ledger as a cost.
        A += ["BNEG gts gtsn I={ -%g*tanh(%g*(V(gts)-V(gtsn))/%g) }"
              % (isat, gneg, isat),
              "VD1 gts d1 0", "RD1 d1 gts 1e12", "VD2 gtsn d2 0", "RD2 d2 gtsn 1e12",
              "VDT tail t0 0", "RDT t0 0 1e12", "RTL tail 0 1e12"]
    elif core == "none":
        A += ["VD1 gts d1 0", "RD1 d1 gts 1e12", "VD2 gtsn d2 0", "RD2 d2 gtsn 1e12",
              "VDT tail t0 0", "RDT t0 0 1e12", "RTL tail 0 1e12"]
    # ---- metering ----------------------------------------------------------
    A += integ('egt',  'V(gts)*(V(gts)-V(gt))/%g'  % RS)      # committed convention
    A += integ('egtp', 'V(gps)*(V(gps)-V(gtp))/%g' % RS)
    A += integ('qgt',  '(V(gts)-V(gt))/%g'  % RS)
    A += integ('qgtp', '(V(gps)-V(gtp))/%g' % RS)
    A += integ('eva',  '-%g*I(VA)'  % VAR)
    A += integ('evb',  '-%g*I(VB)'  % VBR)
    A += integ('evbg', '-%g*I(VBG)' % VBG)
    A += integ('esup', '-(%g*I(VA)+%g*I(VB)+%g*I(VBG))' % (VAR, VBR, VBG))
    A += integ('erp',  'I(LP)*I(LP)*%g'   % RP)
    A += integ('ern',  'I(LN)*I(LN)*%g'   % RN)
    A += integ('erbq', 'I(LBQ)*I(LBQ)*%g' % RBQ)
    A += integ('ed1',  '(V(gts)-V(tail))*I(VD1)')     # device dissipation, M1
    A += integ('ed2',  '(V(gtsn)-V(tail))*I(VD2)')    # device dissipation, M2
    A += integ('edt',  'V(tail)*I(VDT)')              # device dissipation, tail
    if rload:
        A += integ('erld', '(V(gts)-V(gtsn))*(V(gts)-V(gtsn))/%g' % rload)
    A += integ('ecore','-(V(gts)*I(VD1)+V(gtsn)*I(VD2))')  # core -> tank injection

    ADD = (' V(gtsn) V(tail) V(xeva) V(xevb) V(xevbg) V(xesup) V(xerp) V(xern)'
           ' V(xerbq) V(xed1) V(xed2) V(xedt) V(xecore) I(LP) I(LN) I(LBQ)'
           ' I(VD1) I(VD2) I(VDT) I(VA) I(VB) I(VBG) V(xehi) V(xqhi)'
           + (' V(xerld)' if rload else ''))
    out = []
    for ln in src:
        s = ln.strip()
        if drop.match(s): continue
        if s.startswith('.ic '):
            # EVERY 1F integrator is forced to 0 at the operating point.  Without
            # this the 0.01 ohm shunt pins the can at its DC equilibrium I_dc*0.01
            # and the cap then integrates only the CHANGE in power, not the power:
            # a rail carrying a steady 36 uA reads as ZERO energy.  (The committed
            # decks escape this only because their PWL sources carry no DC at t=0;
            # their residual pedestal is the +12.135 fJ phantom on xegtp.)
            ics = ['V(bka)=%g' % (1.0 if hop else 0.0), 'V(bkb)=0']
            if icv: ics += ['V(%s)=%g' % (k, v) for k, v in icv.items()]
            ics += ['V(%s)=0' % n for n in INTEG_NODES]
            out.append('.ic ' + ' '.join(ics)); continue
        if s.startswith('.tran'):
            out.append('.tran 0.1p %gp 0 0.25p' % tend); continue
        if s.startswith('.print'):
            # PRECISION: the 1F/0.01-ohm integrator convention puts a DC pedestal
            # I_dc*0.01 on every can.  With a rail carrying tens of uA that pedestal
            # is 1e-6 V while the fJ signal is 1e-14 V -- default print precision
            # DESTROYS the measurement.  Raised here; every read is t=0-referenced.
            out.append(ln.replace('.print tran', '.print tran WIDTH=28 PRECISION=17')
                       + ADD); continue
        out.append(ln)
        if s.startswith('.OPTIONS'): out += A
    open(name + ".cir", "w").write("\n".join(out) + "\n")
    return name + ".cir"
