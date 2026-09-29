#!/usr/bin/env python3
"""STANDALONE BUCK FIXTURE -- the converter alone, every branch metered.

Topology, one bank's top-up cell lifted verbatim out of qal/ptusk/SR_s4_ptu_*.cir:

    tsup --VMSUP--> tsp --[XTUSW pMOS w=10u]--> na
                                    ground <--VMFW-- nfs <--[XTUFW nMOS w=10u]-- na
                                                     na --VMCNA--> nac --[CNA]--> 0
    na --[LTU]-- ntm --[RTU 10]-- nb --VMTU--> nbx --[OUT T-gate]--> rnode --VMBK--> rail --[CBANK]

THE LEDGER, exact by KCL at na (derivation in PRE_REGISTERED.json / CHARGE_AUDIT.json):

    I(VMSUP) = I(VMFW) + I(LTU) + I(VMCNA) + I(VGTU) + I(VGFW)

    charge out    charge to    charge into   switch-node   gate overlap charge
    of supply     ground via   the inductor  capacitance   pulled out of na by
                  freewheel                                the two gate drivers

Every term is a 1F integrator, t0-referenced at 0.5 ps.  Phase boundaries are
.measure FIND points, so each phase's charge is a difference of two reads.
"""
import json, os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
XYCE = "/usr/local/src/xyce-build/src/Xyce"
CACHE = ("/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6"
         "/scratchpad/vae_cache_buckfix")
ENV = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS", PYMS_VAE_CACHE=CACHE)

HEAD = ['.hdl "/usr/local/share/xyce/verilog-a/psp103/psp103.va"',
        '.include "/usr/local/src/kestrel/sim/models/sg13g2_psp103_tt.lib"',
        '.include "/usr/local/src/stat-sim/qal/sg13lv_compat.sp"',
        '.OPTIONS TIMEINT METHOD=GEAR RELTOL=1e-6 ABSTOL=1e-15 CHGTOL=1e-17']

VGH = 1.5
VSUP = 1.2
CNA_FF = 8.0          # ASSUMED, inherited from the run under test (AMENDMENT A6)
WSW = 10.0
WON, WOP = 5.0, 10.0  # OUT transmission gate, as built in the committed deck
LTU_NH = 1.0
RSTU = 10.0

# ------------------------------------------------------------------ schedules
# Every time is the ABSOLUTE ps of the committed deck, so the phase boundaries
# line up with the reported waveform exactly.
E = 2.0               # ps, the harness EDGE constant


def sched_committed(t_on=12.0):
    """qal/ptusk/SR_s4_ptu_T200_dv1200_L1_t{12,24}.cir, read off the PWLs."""
    tf = 313.137
    a = tf + 24.0 + 4 * E          # 345.137 -- SLEW + 4*EDGE
    b = a + t_on
    return dict(name="C1_committed",
                hs_off_lo=(tf, tf + 2 * E),        # gate 1.5 -> 0  (HS turns ON)
                hs_on_hi=(b, b + E),               # gate 0 -> 1.5  (HS turns OFF)
                fw_off=(a - 24.0, a),              # gate 1.5 -> 0  (FW turns OFF), 24 ps
                fw_on=(b, b + E),                  # gate 0 -> 1.5  (FW turns ON)
                out_close=(a - E, a),
                out_open=None,                     # filled by the ZCS probe
                pulse=(a, b), t_on=t_on, t_fire=tf)


def sched_fix1(t_on=12.0):
    """C2 -- ONE change: break-before-make at TURN-ON.
    The freewheel gate is taken fully low 2 ps BEFORE the high-side gate starts
    to move.  Every other absolute time is byte-for-byte the committed one."""
    s = sched_committed(t_on)
    s = dict(s, name="C2_bbm_turn_on")
    tf = s["t_fire"]
    s["fw_off"] = (tf - 2 * E, tf - E)             # 309.137 -> 311.137
    return s


def sched_fix2(t_on=12.0):
    """C3 = C2 + dead time at TURN-OFF: HS fully off, 2 ps dead, then FW on."""
    s = sched_fix1(t_on)
    s = dict(s, name="C3_bbm_both_edges")
    b = s["pulse"][1]
    s["hs_on_hi"] = (b, b + E)                     # HS off, unchanged
    s["fw_on"] = (b + 2 * E, b + 3 * E)            # FW on after a 2 ps dead time
    return s


def sched_fix3(t_on=12.0):
    """C4 = C3 + the OUT switch closed across the WHOLE conduction+freewheel.
    OUT closes 2 ps before the HS turns on (so the inductor has a path from the
    first instant of conduction) and opens at the RE-PROBED inductor zero."""
    s = sched_fix2(t_on)
    s = dict(s, name="C4_out_spans_pulse")
    tf = s["t_fire"]
    # HS turns on right after the break-before-make, not 32 ps later.
    hs_on = tf
    s["hs_off_lo"] = (hs_on, hs_on + E)
    s["out_close"] = (hs_on - E, hs_on)
    b = hs_on + E + s["t_on"]
    s["pulse"] = (hs_on + E, b)
    s["hs_on_hi"] = (b, b + E)
    s["fw_on"] = (b + 2 * E, b + 3 * E)
    return s


def sched_fix4(t_on=12.0, dead=2.0):
    """C5 -- THE TEXTBOOK SYNCHRONOUS-BUCK SEQUENCE, in the only order that works:

        1. FW OFF                       (break before make)
        2. HS ON   -> na charges to tsup through CNA.  This is the switch-node
                      charging cost, 8 fF x 1.2 V = 9.6 fC, and it is intrinsic
                      to a hard-switched buck, not a defect.
        3. OUT CLOSE -> only NOW is the inductor connected, and it is connected
                      with na ALREADY above the rail, so the current ramps up
                      from zero in the delivering direction.
        4. conduct t_on
        5. HS OFF, dead time, FW ON  -> freewheel, still delivering
        6. OUT OPEN at the RE-PROBED inductor zero (ZCS)

    C4's failure is instructive and is why the order matters: C4 closed OUT while
    na was still at 0, so the bank rang into the L-C tank (I_pk = V*sqrt(C/L) =
    2.2 mA) and drained itself before the pulse even started."""
    tf = 313.137
    e = E
    fw0, fw1 = tf - 3 * e, tf - 2 * e          # 307.137 -> 309.137  FW off
    hs0, hs1 = tf - 2 * e, tf - e              # 309.137 -> 311.137  HS on
    o0, o1 = tf - e, tf                        # 311.137 -> 313.137  OUT close
    b = tf + t_on                              # end of conduction
    return dict(name="C5_textbook_buck",
                hs_off_lo=(hs0, hs1), hs_on_hi=(b, b + e),
                fw_off=(fw0, fw1), fw_on=(b + e + dead, b + 2 * e + dead),
                out_close=(o0, o1), out_open=None,
                pulse=(tf, b), t_on=t_on, t_fire=tf)


def sched_fix5(t_on=12.0, dead=2.0):
    """C6 -- the OTHER way to stop the switch node being yanked: turn the HS ON
    FIRST so the pMOS CLAMPS na at tsup, then take the FW off with a FAST 2 ps
    edge.  This is deliberate make-before-break, but bounded to ~1.5 ps of
    overlap instead of the committed schedule's 24 ps -- the engineering trade
    between a brief cross-conduction and a 0.4 V switch-node yank, tested rather
    than assumed."""
    tf = 313.137
    e = E
    hs0, hs1 = tf - 4 * e, tf - 3 * e          # 305.137 -> 307.137  HS on FIRST
    fw0, fw1 = tf - 3 * e, tf - 2 * e          # 307.137 -> 309.137  FW off FAST
    o0, o1 = tf - e, tf                        # 311.137 -> 313.137  OUT close
    b = tf + t_on
    return dict(name="C6_clamped_bbm",
                hs_off_lo=(hs0, hs1), hs_on_hi=(b, b + e),
                fw_off=(fw0, fw1), fw_on=(b + e + dead, b + 2 * e + dead),
                out_close=(o0, o1), out_open=None,
                pulse=(tf, b), t_on=t_on, t_fire=tf)


def sched_fix6(t_on=12.0, dead=2.0):
    """C7 -- THE TOPOLOGICAL FIX.  Delete the OUT isolation switch from the
    control problem entirely (leave it permanently CLOSED, so it is only a
    series resistance) and isolate the bank the way a synchronous buck actually
    does it: turn the FREEWHEEL device OFF at the current zero.  With both
    HS and FW off, the inductor is open at BOTH ends -- nothing can drain the
    bank -- which is what AMENDMENT A1b's OUT switch was invented to achieve.

    This removes three defects at once:
      * no OUT-switch turn-off feedthrough (the committed run's dominant 92 V/ns
        edge was exactly that switch opening),
      * no floating nbx node between pulses, so no L-C tank ringing into the
        bank when OUT closes,
      * the switch node only has to swing from the RAIL to tsup, not from 0 to
        tsup, so its charging cost falls from Cna*Vin to Cna*(Vin - Vrail).

    Sequence: park both off (na floats at the rail through the inductor, no DC
    path) -> HS ON, conduct t_on -> HS OFF, dead, FW ON -> freewheel -> FW OFF
    at the RE-PROBED zero."""
    tf = 313.137
    e = E
    b = tf + e + t_on
    return dict(name="C7_no_out_switch", no_out=True,
                hs_off_lo=(tf, tf + e), hs_on_hi=(b, b + e),
                fw_off=None,                       # set from the probed zero
                fw_on=(b + e + dead, b + 2 * e + dead),
                out_close=(0.0, 0.0), out_open=None,
                pulse=(tf + e, b), t_on=t_on, t_fire=tf)


def sched_fix7(t_on=12.0, dead=2.0, settle=8.0):
    """C8 -- C6's clamped break-before-make, with the switch node given TIME.

    C6 closed the OUT switch 4 ps after the freewheel released.  MEASURED, the
    high-side pMOS is current limited to ~0.9 mA, so charging the 8 fF switch
    node to tsup is a ~3 ps RC -- 4 ps leaves it ~25% short, and OUT then closes
    onto a switch node BELOW the rail, which makes the bank drive current
    BACKWARDS through the inductor.  `settle` is that wait, made explicit and
    swept.

        HS ON (clamps na at tsup)  ->  FW OFF, fast  ->  settle  ->  OUT CLOSE
        ->  conduct t_on  ->  HS OFF  ->  dead  ->  FW ON  ->  OUT OPEN at ZCS
    """
    tf = 313.137
    e = E
    hs0 = tf - settle - 4 * e
    hs1 = hs0 + e
    fw0, fw1 = hs1, hs1 + e
    o0, o1 = tf - e, tf
    b = tf + t_on
    return dict(name="C8_settled_bbm",
                hs_off_lo=(hs0, hs1), hs_on_hi=(b, b + e),
                fw_off=(fw0, fw1), fw_on=(b + e + dead, b + 2 * e + dead),
                out_close=(o0, o1), out_open=None,
                pulse=(tf, b), t_on=t_on, t_fire=tf, settle_ps=settle)


def sched_fix8(t_on=12.0, dead=2.0, settle=8.0, t_fire=313.137):
    """C9 -- ASYNCHRONOUS (DIODE) FREEWHEEL.  The freewheel nMOS gate is held at
    0 for the WHOLE run; the inductor freewheels through that device's own
    drain-bulk junction instead.

    Why this is worth measuring rather than dismissing: MEASURED on this fixture,
    the two 10 um switches' gate charge is ~20 fC per 1.5 V transition, and the
    whole useful pulse at the best C8 point is only 19.2 fC.  Deleting the
    freewheel device's two gate transitions removes ~40 fC of charge that was
    being drawn from the supply and dumped to ground through the device itself.
    The price is a ~0.7 V junction drop during the freewheel, which shortens the
    delivery phase -- a real trade, measured both ways."""
    tf = t_fire
    e = E
    hs0 = tf - settle - 2 * e
    hs1 = hs0 + e
    o0, o1 = tf - e, tf
    b = tf + t_on
    return dict(name="C9_diode_freewheel", diode_fw=True,
                hs_off_lo=(hs0, hs1), hs_on_hi=(b, b + e),
                fw_off=(hs0, hs1), fw_on=(b + e + dead, b + 2 * e + dead),
                out_close=(o0, o1), out_open=None,
                pulse=(tf, b), t_on=t_on, t_fire=tf, settle_ps=settle)


def pwl(pairs):
    return "PWL(" + " ".join("%gp %g" % (t, v) if t else "%g %g" % (t, v)
                             for t, v in pairs) + ")"


def gate_lines(s):
    (h0, h1), (h2, h3) = s["hs_off_lo"], s["hs_on_hi"]
    (f2, f3) = s["fw_on"]
    (o0, o1) = s["out_close"]
    oo = s["out_open"]
    L = ["VGTU gtu 0 " + pwl([(0, VGH), (h0, VGH), (h1, 0), (h2, 0), (h3, VGH)])]
    if s.get("diode_fw"):
        L += ["VGFW gfw 0 " + pwl([(0, 0), (4400, 0)])]
        if oo is None:
            L += ["VGTO gto 0 " + pwl([(0, 0), (o0, 0), (o1, VGH), (4400, VGH)]),
                  "VGTOP gtop 0 " + pwl([(0, VGH), (o0, VGH), (o1, 0), (4400, 0)])]
        else:
            L += ["VGTO gto 0 " + pwl([(0, 0), (o0, 0), (o1, VGH), (oo, VGH), (oo + E, 0)]),
                  "VGTOP gtop 0 " + pwl([(0, VGH), (o0, VGH), (o1, 0), (oo, 0), (oo + E, VGH)])]
        return L
    if s.get("no_out"):
        # FW is OFF from t=0 (nothing must drain the bank during the park), ON
        # for the freewheel, and OFF again at the RE-PROBED zero.
        fz = s.get("fw_cut")
        pts = [(0, 0), (f2, 0), (f3, VGH)]
        if fz is not None:
            pts += [(fz, VGH), (fz + E, 0)]
        else:
            pts += [(4400, VGH)]
        L += ["VGFW gfw 0 " + pwl(pts),
              "VGTO gto 0 " + pwl([(0, VGH), (4400, VGH)]),
              "VGTOP gtop 0 " + pwl([(0, 0), (4400, 0)])]
        return L
    (f0, f1) = s["fw_off"]
    L += ["VGFW gfw 0 " + pwl([(0, VGH), (f0, VGH), (f1, 0), (f2, 0), (f3, VGH)])]
    if oo is None:                      # probe form: OUT never opens
        L += ["VGTO gto 0 " + pwl([(0, 0), (o0, 0), (o1, VGH), (4400, VGH)]),
              "VGTOP gtop 0 " + pwl([(0, VGH), (o0, VGH), (o1, 0), (4400, 0)])]
    else:
        L += ["VGTO gto 0 " + pwl([(0, 0), (o0, 0), (o1, VGH), (oo, VGH), (oo + E, 0)]),
              "VGTOP gtop 0 " + pwl([(0, VGH), (o0, VGH), (o1, 0), (oo, 0), (oo + E, VGH)])]
    return L


INTEG = [  # (integrator node, expression)
    ("qsup",  "-I(VTSUP)"),            # charge DELIVERED by the top-up supply
    ("qhs",   "I(VMSUP)"),             # same, metered in the HS leg (cross-check)
    ("qfw",   "I(VMFW)"),              # charge to GROUND through the freewheel
    ("qcna",  "I(VMCNA)"),             # charge into the switch-node capacitance
    ("qind",  "I(LTU)"),               # charge through the inductor
    ("qdel",  "I(VMTU)"),              # charge past the inductor meter
    ("qbk",   "I(VMBK)"),              # charge INTO the bank, past the OUT switch
    ("qgtu",  "I(VGTU)"),              # HS gate-drive current (ledger term)
    ("qgfw",  "I(VGFW)"),              # FW gate-drive current (ledger term)
    ("qgto",  "I(VGTO)+I(VGTOP)"),     # OUT gate-drive current
    ("esup",  "%g*(-I(VTSUP))" % VSUP),          # energy out of the supply
    ("ebk",   "V(rail)*I(VMBK)"),                # energy into the bank
    ("efw",   "V(na)*I(VMFW)"),                  # energy burned in the FW leg
    ("erl",   "I(LTU)*I(LTU)*%g" % RSTU),        # I^2R in the inductor's own R
    ("qbs",   "I(VBS)"),                         # the 1 MEG bias path's own leak
]


def deck(s, cb_fF, tstop, marks, ltu_nh=LTU_NH, cna_ff=CNA_FF, vrail0=0.766,
         wsw=WSW):
    L = list(HEAD)
    L += ["VHI vhi 0 %g" % VGH,
          "VTSUP tsup 0 %g" % VSUP,
          "VMSUP tsup tsp 0",
          "XTUSW na gtu tsp tsp sg13_lv_pmos w=%gu l=0.13u" % wsw,
          "XTUFW na gfw nfs nfs sg13_lv_nmos w=%gu l=0.13u" % wsw,
          "VMFW nfs 0 0",
          "VMCNA na nac 0",
          "CNA nac 0 %gf" % cna_ff,
          "LTU na ntm %gn" % ltu_nh,
          "RTU ntm nb %g" % RSTU,
          "VMTU nb nbx 0",
          "XTUON nbx gto rnode 0 sg13_lv_nmos w=%gu l=0.13u" % WON,
          "XTUOP nbx gtop rnode vhi sg13_lv_pmos w=%gu l=0.13u" % WOP,
          "VMBK rnode rail 0",
          "CBANK rail 0 %gf" % cb_fF,
          # The bank is otherwise a FLOATING node (a capacitor and two off
          # switches), so .ic -- which Xyce RELEASES after the operating point --
          # does not hold it.  A 1 Mohm bias path makes the DCOP well posed and
          # sets the rail exactly.  MEASURED leakage is metered on its own integrator (qbs) and is ~0.05 fC, five orders below the charges of interest.
          "VBS vbs 0 %g" % vrail0,
          "RBS vbs rail 1MEG"]
    L += gate_lines(s)
    for n, e in INTEG:
        L += ["CX%s x%s 0 1" % (n, n),
              "BX%s 0 x%s I={ %s }" % (n, n, e),
              "RX%s x%s 0 0.01" % (n, n)]
    # rnode is tied to rail by the 0 V ammeter VMBK, so it MUST carry the same
    # initial condition -- forcing it to 0 over-constrains the op point.
    # With no OUT switch, both power devices are off during the park and the
    # switch node floats to the rail through the inductor -- so it STARTS there.
    n0 = vrail0 if s.get("no_out") else 0.0
    L += [".ic V(rail)=%g V(rnode)=%g V(na)=%g V(nac)=%g V(nb)=%g V(nbx)=%g V(ntm)=%g"
          % (vrail0, vrail0, n0, n0, n0, n0, n0),
          ".tran 0.1p %gp 0 0.0884183p" % tstop]
    for tag, t in marks:
        for n, _ in INTEG:
            L.append(".measure tran %s_%s FIND V(x%s) AT=%.6fp" % (n.upper(), tag, n, t))
        L.append(".measure tran VRAIL_%s FIND V(rail) AT=%.6fp" % (tag, t))
        L.append(".measure tran VNA_%s FIND V(na) AT=%.6fp" % (tag, t))
        L.append(".measure tran ILTU_%s FIND I(LTU) AT=%.6fp" % (tag, t))
    L.append(".measure tran ILPK MAX I(LTU) FROM=%gp TO=%gp"
             % (s["t_fire"] - 5, tstop - 1))
    L.append(".print tran I(VMSUP) I(VMFW) I(LTU) I(VMTU) I(VMBK) I(VMCNA) "
             "V(na) V(nb) V(rail) V(gtu) V(gfw) V(gto) I(VTSUP)")
    L.append(".end")
    return L


def run(fn, lines, timeout=600):
    p = os.path.join(HERE, fn)
    open(p, "w").write("\n".join(lines) + "\n")
    t0 = time.monotonic()
    try:
        r = subprocess.run([XYCE, fn], capture_output=True, text=True,
                           timeout=timeout, cwd=HERE, env=ENV)
    except subprocess.TimeoutExpired:
        return None, "TIMEOUT %gs" % timeout
    w = time.monotonic() - t0
    if r.returncode != 0 or not os.path.exists(p + ".prn"):
        err = "; ".join(l.strip() for l in r.stdout.splitlines()
                        if "rror" in l or "bort" in l)[:400]
        return None, "XYCE FAIL %s (%.1fs) %s" % (fn, w, err or r.stdout[-300:])
    return p, "ran %s in %.1fs" % (fn, w)


def mt0(path):
    d = {}
    for line in open(path + ".mt0"):
        if "=" in line:
            k, v = line.split("=", 1)
            try:
                d[k.strip().upper()] = float(v.strip().split()[0])
            except ValueError:
                pass
    return d


def prn(path):
    rows, hdr = [], None
    for line in open(path + ".prn"):
        t = line.split()
        if not t:
            continue
        if t[0] == "Index":
            hdr = t
            continue
        if hdr and t[0].lstrip("-").isdigit():
            try:
                rows.append([float(x) for x in t])
            except ValueError:
                pass
    return hdr, rows


def col(hdr, name):
    for i, h in enumerate(hdr):
        if h.upper() == name.upper():
            return i
    raise KeyError(name + " not in " + " ".join(hdr))
