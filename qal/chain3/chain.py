#!/usr/bin/env python3
"""THREE-BANK UNBUFFERED QAL CHAIN.

Cells, transfer switch, series R, .OPTIONS, dV, gate phases, park phase, the
TRUE-ZCS probe-then-cut protocol and the 1F-integrator metering discipline are
qal/lsweep/lsw.py VERBATIM (which is sar/sar_observable.py verbatim, which is
swsweep/sw_hop_meter.py verbatim, which is gateb's committed harness verbatim).

WHAT IS NEW HERE and nowhere else:
  * three banks of real gates instead of one bank fed by a lumped cap;
  * o<i> of bank N IS in<i> of bank N+1 -- the same net.  No buffer of any kind;
  * a small head pre-charge gate on bank 1 and the optional per-stage top-up
    transmission gate on banks 2 and 3 (see AMENDMENT.md A1/A2);
  * per-hop, per-bank, per-gate extraction at STAGE-BOUNDARY checkpoints.

Pre-registration: PRE_REGISTERED.json, written before this file existed.

Stages:  warm | vt | point <tag> <L> <W> <mode> | show
"""
import json, math, os, re, subprocess, sys, time

HERE  = os.path.dirname(os.path.abspath(__file__))
QAL   = os.path.normpath(os.path.join(HERE, ".."))
XYCE  = "/usr/local/src/xyce-build/src/Xyce"
VA    = "/usr/local/share/xyce/verilog-a/psp103/psp103.va"
MODEL = "/usr/local/src/kestrel/sim/models/sg13g2_psp103_tt.lib"
SHIM  = "/usr/local/src/stat-sim/qal/sg13lv_compat.sp"
CACHE = os.environ.get("PYMS_VAE_CACHE") or \
    "/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6/scratchpad/vae_cache_chain3"
ENV = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS", PYMS_VAE_CACHE=CACHE)

# ---- inherited constants (committed; do not touch) -------------------------
DV        = 1.0
RS_REF    = 10.0
VGH       = 1.5
WP, WN    = 1.12, 0.74          # cell inverter widths
MGATE     = 8
CLOAD     = 2.0                 # fF per cell output
CA_FF     = 35.979              # MEASURED secant C of one 8-cell bank at 1.0 V
L_REF     = 277.8               # nH, committed energy-rule inductance
TZ_REF    = 266.755223          # ps, committed tg15p true zero
EDGE      = 2.0                 # ps, committed gate edge
LAG_PS    = 1.0                 # MEASURED .measure-FIND lag in this Xyce build
NBANK     = 3
T1        = 200.0               # ps, hop 1 closes (pre-roll for the chain head)
HEAD_LEAD = 40.0                # ps, head gate cut STARTS this far before T1
HEAD_EDGE = 20.0                # ps, AMENDMENT A2: soft head cut (committed 2 ps
                                #     edge retained for every transfer-switch phase)
HEAD_WN, HEAD_WP = 1.0, 1.12    # um, AMENDMENT A2: small head pre-charge gate
TAIL      = 500.0               # ps, post-stage-3 eventual-settle tail
TOPUP_W   = 20.0                # ps, top-up conduction window (at the gap START)

# pre-registered stagger DELTA(L) = ceil(t_valid90 - t_hop) from qal/lsweep/rows.json
DELTA_TBL = {277.8: 27.0, 200.0: 36.0, 150.0: 43.0, 120.0: 49.0, 100.0: 53.0,
             80.0: 59.0, 60.0: 65.0, 50.0: 69.0, 45.0: 72.0, 40.0: 74.0,
             35.0: 77.0, 30.0: 81.0, 10.0: 108.0, 3.0: 162.0}


def delta_ps(l_nh):
    if l_nh in DELTA_TBL:
        return DELTA_TBL[l_nh]
    ks = sorted(DELTA_TBL)
    for a, b in zip(ks, ks[1:]):
        if a <= l_nh <= b:
            f = (l_nh - a) / (b - a)
            return round(DELTA_TBL[a] + f * (DELTA_TBL[b] - DELTA_TBL[a]), 1)
    raise ValueError("L outside the pre-registered DELTA table: %g" % l_nh)


def t_est(l_nh):
    """DERIVED sqrt(L) scaling, used ONLY to size timesteps and run lengths."""
    return TZ_REF * math.sqrt(l_nh / L_REF)


def widths(total_um):
    """1:2 n:p TG + park = total/15.  total=15 reproduces committed tg15p."""
    return dict(wn=total_um / 3.0, wp=2.0 * total_um / 3.0, park=total_um / 15.0)


def is_hi(k, i):
    """Bank k cell i has a logic-HIGH input (pull-DOWN cell) iff (i+k) is odd.
    Bank 1 inputs alternate 1,0,1,0..., and every bank inverts, so every bank
    has 4 pull-UP and 4 pull-DOWN cells at every stage."""
    return (i + k) % 2 == 1


def in_net(k, i):
    """THE POINT OF THE WHOLE DECK: bank k's input net for cell i.
    k == 1 -> an ideal source (the chain head).  k > 1 -> literally o{k-1}_{i}."""
    return "in1_%d" % i if k == 1 else "o%d_%d" % (k - 1, i)


# --------------------------------------------------------------- deck pieces
def head():
    return ['.hdl "%s"' % VA, '.include "%s"' % MODEL, '.include "%s"' % SHIM,
            '.OPTIONS TIMEINT METHOD=GEAR RELTOL=1e-6 ABSTOL=1e-15 CHGTOL=1e-17']


def bank_cells(k, dv=DV):
    """One level of logic.  Cell definition is the committed one verbatim:
    pMOS w=1.12u with supply AND bulk on the bank rail, nMOS w=0.74u, CL 2 fF."""
    L = ["VMG%d gn%d 0 0" % (k, k)]
    if k == 1:
        for i in range(MGATE):
            L.append("VI1_%d in1_%d 0 %g" % (i, i, dv if is_hi(1, i) else 0.0))
    for i in range(MGATE):
        s = in_net(k, i)
        L.append("XP%d_%d o%d_%d %s rail%d rail%d sg13_lv_pmos w=%gu l=0.13u"
                 % (k, i, k, i, s, k, k, WP))
        L.append("XN%d_%d o%d_%d %s gn%d gn%d sg13_lv_nmos w=%gu l=0.13u"
                 % (k, i, k, i, s, k, k, WN))
        L.append("CL%d_%d o%d_%d gn%d %gf" % (k, i, k, i, k, CLOAD))
    return L


def transfer_switch(k, total_um, srccut=True):
    """Hop k's transfer switches.

    DESTINATION side (always): the committed tg15p triple between the inductor
    node sw{k} and rail{k+1} -- the committed receiving-side-cut topology, verbatim.

    SOURCE side (srccut=True, AMENDMENT A3): an IDENTICAL tg15p triple between
    rail{k} and the inductor's near node a{k}, sharing hop k's SAME gate phases,
    plus its own park.  MEASURED reason it is required: with the committed
    receiving-side-only cut the next stage's inductor stays wired to the bank
    being charged, and it diverted 42.3% of hop 1's charge and left hop 2 starting
    with -34.9 uA already circulating (c_a277_free_rxonly).  srccut=False
    reproduces that non-composing topology as a recorded row."""
    w = widths(total_um)
    L = ["XSWN%d sw%d gt%d rail%d 0 sg13_lv_nmos w=%gu l=0.13u"
         % (k, k, k, k + 1, w["wn"]),
         "XSWP%d sw%d gtp%d rail%d vhi sg13_lv_pmos w=%gu l=0.13u"
         % (k, k, k, k + 1, w["wp"]),
         "XPK%d sw%d pk%d 0 0 sg13_lv_nmos w=%gu l=0.13u" % (k, k, k, w["park"])]
    if srccut:
        L += ["XSWSN%d a%d gt%d rail%d 0 sg13_lv_nmos w=%gu l=0.13u"
              % (k, k, k, k, w["wn"]),
              "XSWSP%d a%d gtp%d rail%d vhi sg13_lv_pmos w=%gu l=0.13u"
              % (k, k, k, k, w["wp"]),
              ]
        # NO park on the source-side inductor node a{k}.  A park there has to be
        # released before the switch closes (leaving a{k} momentarily isolated ->
        # MEASURED "time step too small" abort at exactly that instant) or after
        # (shorting the source rail to ground through the park for one edge ->
        # ~3 fC, 9% of the bank charge).  a{k} simply floats, pinned by .ic: with
        # BOTH of hop k's switches off there is no source driving L{k}, so the idle
        # inductor stays at rest, which is the whole point of the source-side cut.
    return L


def supply_tg(k, total_um, win, present=True):
    """Bank k's connection to the ideal dV rail, with a 0 V series source so its
    charge is metered exactly.  win = (t_on, t_off) or None for 'never enabled'.

    k == 1 is the CHAIN HEAD pre-charge gate: small (AMENDMENT A2), soft 20 ps
    cut, always present -- without it the chain head cannot be pre-charged, since
    a bare .ic lets bank 1's cells charge their own outputs out of their own rail
    and drop it ~0.22 V before the hop ever starts.

    k >= 2 is the optional per-stage TOP-UP device at tg15p sizing.  present=False
    removes it entirely: that is the free-running chain (AMENDMENT A1) and, with
    win=None, the control run that isolates its capacitance."""
    if k >= 2 and not present:
        return []
    w = widths(total_um)
    wn, wp = (HEAD_WN, HEAD_WP) if k == 1 else (w["wn"], w["wp"])
    e = HEAD_EDGE if k == 1 else EDGE
    # NOTE: no 0 V series source in this branch.  Metering bank k's supply charge
    # as I(VTU{k}) is DEGENERATE once the gate opens -- the branch current of a 0 V
    # source feeding an open circuit -- and MEASURED, that single integrator aborts
    # the run ("time step too small") at the first gate edge; bisection over all 18
    # integrators isolated it to qtu1 alone.  The supply charge is metered on the
    # always-connected ideal source VDV instead, and split by checkpoint: the head
    # and the two top-up windows are DISJOINT by construction, so differencing
    # qdv between checkpoints gives each one exactly.
    L = ["XTUN%d rail%d tun%d vdv 0 sg13_lv_nmos w=%gu l=0.13u" % (k, k, k, wn),
         "XTUP%d rail%d tup%d vdv vhi sg13_lv_pmos w=%gu l=0.13u" % (k, k, k, wp)]
    if win is None:
        L += ["VTUN%d tun%d 0 0" % (k, k), "VTUP%d tup%d 0 %g" % (k, k, VGH)]
    else:
        a, b = win
        if a <= 0.0:                       # on from t=0 (the chain head)
            L += ["VTUN%d tun%d 0 PWL(0 %g %gp %g %gp 0)" % (k, k, VGH, b, VGH, b + e),
                  "VTUP%d tup%d 0 PWL(0 0 %gp 0 %gp %g)" % (k, k, b, b + e, VGH)]
        else:
            L += ["VTUN%d tun%d 0 PWL(0 0 %gp 0 %gp %g %gp %g %gp 0)"
                  % (k, k, a, a + e, VGH, b, VGH, b + e),
                  "VTUP%d tup%d 0 PWL(0 %g %gp %g %gp 0 %gp 0 %gp %g)"
                  % (k, k, VGH, a, VGH, a + e, b, b + e, VGH)]
    return L


def integ(tg, expr):
    return ["CX%s x%s 0 1" % (tg, tg), "BX%s 0 x%s I={ %s }" % (tg, tg, expr),
            "RX%s x%s 0 0.01" % (tg, tg)]


def hop_integrators(rs, no_tg=False, srccut=True):
    L, tags = [], []
    for k in (1, 2):
        for nm, ex in (("qlt%d" % k, "I(L%d)" % k),
                       ("ea%d" % k, "V(rail%d)*I(L%d)" % (k, k)),
                       ("ean%d" % k, "V(%s)*I(L%d)"
                        % (("a%d" % k) if srccut else ("rail%d" % k), k)),
                       ("eb%d" % k, "V(rail%d)*I(L%d)" % (k + 1, k)),
                       ("er%d" % k, "I(L%d)*I(L%d)*%g" % (k, k, rs)),
                       ("esw%d" % k, "V(sw%d)*I(L%d)" % (k, k))):
            L += integ(nm, ex); tags.append(nm)
    for k in range(1, NBANK + 1):
        L += integ("qg%d" % k, "I(VMG%d)" % k); tags.append("qg%d" % k)
        if not (no_tg and k >= 2):
            L += integ("egtu%d" % k, "-V(tun%d)*I(VTUN%d)-V(tup%d)*I(VTUP%d)"
                       % (k, k, k, k)); tags.append("egtu%d" % k)
    # total charge out of the dV supply; windows are disjoint so checkpoint
    # differences give the head and each top-up separately
    L += integ("qdv", "-I(VDV)"); tags.append("qdv")
    L += integ("qi1", "-(" + "+".join("I(VI1_%d)" % i for i in range(MGATE)) + ")")
    tags.append("qi1")
    L += integ("egt", "-" + "-".join(
        "V(gt%d)*I(VGT%d)-V(gtp%d)*I(VGTP%d)-V(pk%d)*I(VPK%d)" % (k, k, k, k, k, k)
        for k in (1, 2)))
    tags.append("egt")
    return L, tags


# ---------------------------------------------------------------- the decks
def timing(l_nh, tz1=None, tz2=None, dov=None):
    d = dov if dov else delta_ps(l_nh)
    te = t_est(l_nh)
    z1 = tz1 if tz1 else te
    z2 = tz2 if tz2 else te
    o1 = T1 + z1
    t2 = o1 + d
    o2 = t2 + z2
    # Stage-boundary checkpoints.  Bank k is read at the instant its successor's
    # switch gate BEGINS to move (T_{k+1} - EDGE), i.e. the last instant bank k's
    # data is still undisturbed.  This is the pre-registered boundary made STRICT:
    # it gives each bank LESS settling time, not more, and it avoids measuring a
    # rail that has already started to drain.
    return dict(delta=d, t_est=te, T1=T1, t_open1=o1, T2=t2, t_open2=o2,
                ck1=T1 - EDGE, ck2=t2 - EDGE, ck3=o2 + d, tend=o2 + d + TAIL,
                head_off=T1 - HEAD_LEAD,
                pstep=min(0.1, te / 2000.0), mstep=min(0.25, te / 1000.0))


def chain_lines(l_nh, total_um, mode, tz1=None, tz2=None, rs=RS_REF, dv=DV,
                probe=None, srccut=True, dov=None):
    """probe=1 -> hop 1 closes and never opens, hop 2 held off (t_zcs(1) probe).
       probe=2 -> hop 1 cut at tz1, hop 2 closes at T2 and never opens.
       probe=None -> the measured deck: both hops cut at their own zeros."""
    T = timing(l_nh, tz1, tz2, dov)
    big = T["tend"] * 4.0
    L = head() + [".param LT=%gn RS=%g" % (l_nh, rs), "VHI vhi 0 %g" % VGH,
                  "VDV vdv 0 %g" % dv]
    # --- the three banks, with bank N's outputs feeding bank N+1 directly
    for k in range(1, NBANK + 1):
        L += bank_cells(k, dv)
    # --- supply / top-up transmission gates.  AMENDMENT A1: banks 2 and 3 carry
    # the device ONLY in the top-up variant and in the 'ctrl' control run.
    wins = {1: (0.0, T["head_off"]), 2: None, 3: None}
    if mode == "hold" and probe is None:
        # CAUSAL CONTROL.  hop 2 NEVER closes, so bank 2's rail is never drained;
        # bank 3 is powered ONLY by its own top-up.  Bank 3's pull-down cells
        # therefore keep their HIGH gate drive for the whole evaluation.  If bank 3
        # then settles, the chain's pull-down failure is caused specifically by the
        # forward charge transfer collapsing the predecessor's HIGH level, and not
        # by rail droop, the switch, L, the stage time, or the cells themselves.
        wtu = max(2 * EDGE, min(TOPUP_W, T["delta"] - 6 * EDGE))
        wins[2] = (T["t_open1"] + 2 * EDGE, T["t_open1"] + 2 * EDGE + wtu)
        wins[3] = (T["T2"] + 2 * EDGE, T["T2"] + 2 * EDGE + wtu)
    if mode == "topup" and probe != 1:
        # The top-up sits at the START of the inter-hop gap: RESTORE the rail
        # first, then let the cells settle against the restored rail for the rest
        # of the gap.  Spanning the whole gap (the first thing tried) restores the
        # rail 2 ps before the stage boundary, so the settling ratio V(o)/V(rail)
        # is read against a rail that has just jumped -- it moves the goalpost and
        # MEASURED it reads 44.7% at bank 2 on a chain whose rail is fine.
        wtu = max(2 * EDGE, min(TOPUP_W, T["delta"] - 6 * EDGE))
        wins[2] = (T["t_open1"] + 2 * EDGE, T["t_open1"] + 2 * EDGE + wtu)
        if probe is None:
            wins[3] = (T["t_open2"] + 2 * EDGE, T["t_open2"] + 2 * EDGE + wtu)
    present = mode in ("topup", "ctrl", "hold")
    for k in range(1, NBANK + 1):
        L += supply_tg(k, total_um, wins[k], present)
    # --- the two transfer hops
    for k in (1, 2):
        near = ("a%d" % k) if srccut else ("rail%d" % k)
        L += ["L%d %s mid%d {LT}" % (k, near, k),
              "R%d mid%d sw%d {RS}" % (k, k, k)] + \
             transfer_switch(k, total_um, srccut)
    # --- gate phases
    def phases(k, tc, to, srccut=srccut):
        if tc is None:                                   # never closes
            # park MUST stay OFF: sw{k} is tied to rail{k} through R{k}/L{k}, so
            # parking it would short that rail to ground through the inductor --
            # exactly the committed AMENDMENT-A3 instrument failure.
            # idle hop: destination park OFF (parking it would short the rail to
            # ground through the inductor -- the committed AMENDMENT-A3 failure),
            # SOURCE park ON, which is what holds the idle inductor at rest.
            # idle hop.  WITH a source-side cut the destination park can be HELD
            # ON while the hop is idle -- the committed AMENDMENT-A3 hazard (park
            # shorts the source rail to ground through the inductor) is exactly
            # what the source cut removes.  Holding it PINS the inductor island
            # {a,mid,sw}, which is otherwise floating between two off switches:
            # MEASURED, leaving it floating aborts the run ("time step too small")
            # at the first gate edge.
            return ["VGT%d gt%d 0 0" % (k, k), "VGTP%d gtp%d 0 %g" % (k, k, VGH),
                    "VPK%d pk%d 0 %g" % (k, k, VGH if srccut else 0.0)]
        if to is None:                                   # closes, never opens
            return ["VGT%d gt%d 0 PWL(0 0 %gp 0 %gp %g %gp %g)"
                    % (k, k, tc - EDGE, tc, VGH, big, VGH),
                    "VGTP%d gtp%d 0 PWL(0 %g %gp %g %gp 0 %gp 0)"
                    % (k, k, VGH, tc - EDGE, VGH, tc, big),
                    "VPK%d pk%d 0 %s" % (k, k,
                        ("PWL(0 %g %gp %g %gp 0)" % (VGH, tc, VGH, tc + EDGE))
                        if srccut else "0")]
        return ["VGT%d gt%d 0 PWL(0 0 %gp 0 %gp %g %gp %g %gp 0)"
                % (k, k, tc - EDGE, tc, VGH, to, VGH, to + EDGE),
                "VGTP%d gtp%d 0 PWL(0 %g %gp %g %gp 0 %gp 0 %gp %g)"
                % (k, k, VGH, tc - EDGE, VGH, tc, to, to + EDGE, VGH),
                ("VPK%d pk%d 0 PWL(0 %g %gp %g %gp 0 %gp 0 %gp %g)"
                 % (k, k, VGH, tc, VGH, tc + EDGE, to + EDGE, to + 2 * EDGE, VGH))
                if srccut else
                ("VPK%d pk%d 0 PWL(0 0 %gp 0 %gp %g)"
                 % (k, k, to + EDGE, to + 2 * EDGE, VGH))]
    if probe == 1:
        L += phases(1, T["T1"], None) + phases(2, None, None)
        tend = T1 + 1.6 * T["t_est"]
    elif probe == 2:
        L += phases(1, T["T1"], T["t_open1"]) + phases(2, T["T2"], None)
        tend = T["T2"] + 1.6 * T["t_est"]
    elif mode == "hold":
        L += phases(1, T["T1"], T["t_open1"]) + phases(2, None, None)
        tend = T["tend"]
    else:
        L += phases(1, T["T1"], T["t_open1"]) + phases(2, T["T2"], T["t_open2"])
        tend = T["tend"]
    # --- metering
    if probe is None:
        ig, tags = hop_integrators(rs, mode not in ("topup", "ctrl", "hold"), srccut)
        L += ig
    else:
        tags = []
    ics = ".ic V(rail1)=%g V(rail2)=0 V(rail3)=0" % dv
    if srccut:
        ics += " V(a1)=0 V(a2)=0"
    L.append(ics)
    L.append(".tran %gp %gp 0 %gp" % (T["pstep"], tend, T["mstep"]))

    g = lambda t: t + LAG_PS
    if probe is None:
        cks = [("Z", 0.5), ("B1", T["t_open1"]), ("C1", T["t_open1"] + 7.0),
               ("B2", T["t_open2"]), ("C2", T["t_open2"] + 7.0),
               ("K1", T["ck1"]), ("K2", T["ck2"]), ("K3", T["ck3"]),
               ("D", tend - 5.0)]
        for tg in tags:
            for nm, tt in cks:
                L.append(".measure tran %s_%s FIND V(x%s) AT=%.6fp"
                         % (tg.upper(), nm, tg, g(tt)))
        # rails at every checkpoint, plus the pre-hop head level and peaks
        for nm, tt in cks + [("H", T1 - 2 * EDGE)]:
            for k in range(1, NBANK + 1):
                L.append(".measure tran VR%d%s FIND V(rail%d) AT=%.6fp"
                         % (k, nm, k, g(tt)))
        for k in range(1, NBANK + 1):
            L.append(".measure tran VR%dPK MAX V(rail%d) FROM=%gp TO=%gp"
                     % (k, k, T1, tend))
        # per-gate outputs at each bank's OWN stage-boundary checkpoint
        ckof = {1: ("K1", T["ck1"]), 2: ("K2", T["ck2"]), 3: ("K3", T["ck3"])}
        for k in range(1, NBANK + 1):
            nm, tt = ckof[k]
            for i in range(MGATE):
                L.append(".measure tran O%d_%dS FIND V(o%d_%d) AT=%.6fp"
                         % (k, i, k, i, g(tt)))
                L.append(".measure tran O%d_%dE FIND V(o%d_%d) AT=%.6fp"
                         % (k, i, k, i, g(tend - 5.0)))
        for k in (1, 2):
            L.append(".measure tran IZ%d FIND I(L%d) AT=%.6fp"
                     % (k, k, g(T["t_open%d" % k])))
            L.append(".measure tran IPK%d MAX I(L%d) FROM=%gp TO=%gp" % (k, k, T1, tend))
        pr = ["V(rail1)", "V(rail2)", "V(rail3)", "I(L1)", "I(L2)"] + \
             ["V(o%d_%d)" % (k, i) for k in range(1, NBANK + 1) for i in range(MGATE)] + \
             ["V(x%s)" % t for t in tags if t.startswith(("ea", "esw", "er"))] + \
             ["V(sw1)", "V(sw2)"] + (["V(a1)", "V(a2)"] if srccut else [])
    else:
        pr = ["I(L1)", "I(L2)", "V(rail1)", "V(rail2)", "V(rail3)",
              "V(sw1)", "V(sw2)"] + (["V(a1)", "V(a2)"] if srccut else [])
    L.append(".print tran " + " ".join(pr))
    L.append(".end")
    return L, T


# --------------------------------------------------------------------- utils
def run(fn, lines, timeout=900):
    path = os.path.join(HERE, fn)
    open(path, "w").write("\n".join(lines) + "\n")
    t0 = time.monotonic()
    try:
        r = subprocess.run([XYCE, fn], capture_output=True, text=True,
                           timeout=timeout, cwd=HERE, env=ENV)
    except subprocess.TimeoutExpired:
        return None, "TIMEOUT after %gs" % timeout
    wall = time.monotonic() - t0
    ok = os.path.exists(path + ".prn")
    if r.returncode != 0 or not ok:
        err = "; ".join(l.strip() for l in r.stdout.splitlines()
                        if "rror" in l or "bort" in l)[:400]
        return None, "XYCE FAIL %s (%.1fs): %s" % (fn, wall, err or r.stdout[-400:])
    return path, "ran %s in %.1fs" % (fn, wall)


def parse_mt0(path):
    d = {}
    for ln in open(path):
        m = re.match(r"\s*(\w+)\s*=\s*(\S+)", ln)
        if m:
            try:
                d[m.group(1).upper()] = float(m.group(2))
            except ValueError:
                pass
    return d


def read_prn(path):
    rows, hdr = [], None
    for ln in open(path):
        p = ln.split()
        if hdr is None and p and p[0].lower() == "index":
            hdr = [h.upper() for h in p]
            continue
        if hdr and p and p[0][0].isdigit():
            try:
                rows.append([float(x) for x in p])
            except ValueError:
                pass
    return hdr, rows


def zero_after_peak(hdr, rows, sig, t_from, t_to):
    """TRUE-ZCS probe, committed protocol: the FIRST downward zero crossing
    AFTER the current peak (anchoring on the peak makes it robust at small L,
    where the close-edge feedthrough is a large fraction of the hop)."""
    ii = hdr.index(sig)
    post = [r for r in rows if t_from <= r[1] * 1e12 <= t_to]
    if not post:
        return None, "probe window empty"
    ipk = max(r[ii] for r in post)
    tpk = [r for r in post if r[ii] == ipk][0][1] * 1e12
    prev = prevt = None
    for r in post:
        tt, cur = r[1] * 1e12, r[ii]
        if tt < tpk:
            prev, prevt = cur, tt
            continue
        if prev is not None and prev > 0 and cur <= 0:
            tz = prevt + (tt - prevt) * prev / (prev - cur)
            return dict(tz=tz, ipk_uA=ipk * 1e6, tpk=tpk), "zero"
        prev, prevt = cur, tt
    for r in post:
        if r[1] * 1e12 >= tpk and abs(r[ii]) < 0.01 * ipk:
            return dict(tz=r[1] * 1e12, ipk_uA=ipk * 1e6, tpk=tpk), "OVERDAMPED"
    return None, "no zero and no 1%% decay after the peak for %s" % sig


if __name__ == "__main__":
    print(json.dumps({k: v for k, v in
                      dict(CACHE=CACHE, DELTA_277p8=delta_ps(277.8)).items()}))
