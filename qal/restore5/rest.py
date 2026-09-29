#!/usr/bin/env python3
"""RESTORING STAGES EVERY k BANKS in a hop-powered QAL chain.

Cells, transfer switch (with the mandatory source-side cut), series R, .OPTIONS,
dV, gate phases, park phase, head pre-charge gate, the TRUE-ZCS probe-then-cut
protocol, the 1F-integrator metering discipline, the +1.0 ps .measure-FIND lag and
the per-gate settling convention are qal/skip4/skip.py VERBATIM, which is
qal/chain3/chain.py verbatim, which is qal/lsweep/lsw.py verbatim, which is
swsweep/sw_hop_meter.py verbatim, which is gateb's committed harness verbatim.

WHAT IS NEW HERE AND NOWHERE ELSE: a RESTORING STAGE -- a full-rail CMOS inverter
PAIR powered from the fixed supply, not from a hop -- inserted every k banks, and
with it a per-SEGMENT charge reservoir.

  segment = 1 pre-charged reservoir (CA = 35.979 fF, the committed single hop's
            own source; NOT a logic level)
            + k hop-powered logic banks, bank N's outputs wired STRAIGHT to bank
              N+1's inputs (same net, no buffer of any kind WITHIN a segment)
  restore = an inverter pair per bit between the LAST bank of one segment and the
            FIRST bank of the next.  The last bank of a segment has no outgoing
            hop, so its rail is never drained and its outputs are stable -- that
            is what makes a restoring stage able to work at all.

Every configuration has 6 logic banks and 6 hops; only the restore placement
differs.  k=6 is the NO-RESTORE control (one segment, zero internal restores).

Pre-registration: PRE_REGISTERED.json (written before this file existed).
Amendments: AMENDMENT.md.

Stages: warm | probe <k> <T> | row <k> <T> <tz_json> <tres>
"""
import json, math, os, re, subprocess, sys, time

HERE  = os.path.dirname(os.path.abspath(__file__))
XYCE  = "/usr/local/src/xyce-build/src/Xyce"
VA    = "/usr/local/share/xyce/verilog-a/psp103/psp103.va"
MODEL = "/usr/local/src/kestrel/sim/models/sg13g2_psp103_tt.lib"
SHIM  = "/usr/local/src/stat-sim/qal/sg13lv_compat.sp"
CACHE = os.environ.get("PYMS_VAE_CACHE") or \
    "/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6/scratchpad/vae_cache_restore5"
ENV = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS", PYMS_VAE_CACHE=CACHE)

# ---- inherited constants (committed; not touched) --------------------------
RS_REF    = 10.0
VGH       = 1.5
WP, WN    = 1.12, 0.74          # cell inverter widths (also the RESTORE cell)
MGATE     = 8
CLOAD     = 2.0                 # fF per output (also on both restore nodes)
EDGE      = 2.0                 # ps, committed transfer-gate edge
LAG_PS    = 1.0                 # MEASURED .measure-FIND lag in this Xyce build
HEAD_EDGE = 20.0                # chain3 A2: soft head cut (2 ps aborts the run)
HEAD_LEAD = 40.0                # ps, head cut STARTS this far before its beat
HEAD_WN, HEAD_WP = 1.0, 1.12    # um, small head pre-charge gate (qpre.cir only)
RES_WP1, RES_WN1 = 0.15, 1.48   # um, AMENDMENT A4: the SKEWED receiving inverter of
                                #     the restoring stage (committed bound/ H1 cell
                                #     A4, MEASURED trip point 0.4595 V).  The
                                #     standard 1.12/0.74 cell trips at 0.6452 V and
                                #     MEASURED does NOT restore -- see AMENDMENT.md
TAIL      = 500.0               # ps, post-last-stage eventual-settle tail
T1        = 200.0               # ps, beat 1 closes (pre-roll for the head)
CA_FF     = 35.979              # fF, committed reservoir = MEASURED secant C of
                                #     one 8-cell bank at 1.0 V
TZ_ANCHOR = 65.49500982344826   # ps, committed L=15/W30/dV1.2 single-hop zero
CHAIN_F   = 1.35                # DERIVED sizing factor only (chain3 measured 1.326x)
NBANK     = 6                   # logic banks, in EVERY configuration
L_NH      = 15.0
W_UM      = 30.0
DV        = 1.2


def widths(total_um):
    """1:2 n:p TG + park = total/15.  total=30 is the committed robust point."""
    return dict(wn=total_um / 3.0, wp=2.0 * total_um / 3.0, park=total_um / 15.0)


def is_hi(j, i):
    """Bank j cell i has a logic-HIGH input (pull-DOWN cell) iff (i+j) is odd.
    Unchanged across a restore because the restoring stage is NON-inverting, so
    every bank has 4 pull-UP and 4 pull-DOWN cells at every stage."""
    return (i + j) % 2 == 1


# ------------------------------------------------------------------ topology
def topo(k, nbank=NBANK):
    """Segment structure.  seg[j] = 0-based segment of bank j; pos[j] = 0-based
    position of bank j inside its segment; S = number of segments."""
    assert nbank % k == 0, "k must divide %d" % nbank
    S = nbank // k
    seg = {j: (j - 1) // k for j in range(1, nbank + 1)}
    pos = {j: (j - 1) % k for j in range(1, nbank + 1)}
    first = {s: s * k + 1 for s in range(S)}
    last = {s: s * k + k for s in range(S)}
    # internal restoring stages: one per segment boundary (AMENDMENT A1)
    restore_into = {first[s]: s for s in range(1, S)}      # bank -> restore id
    return dict(k=k, S=S, nbank=nbank, seg=seg, pos=pos, first=first, last=last,
                restore_into=restore_into)


def src_node(k, j):
    """Hop j's SOURCE: its segment's reservoir if bank j is segment-first,
    otherwise bank j-1's rail (which the hop thereby DRAINS)."""
    return ("res%d" % ((j - 1) // k + 1)) if (j - 1) % k == 0 else ("rail%d" % (j - 1))


def has_srccut(k, j):
    """AMENDMENT A3: the chain3-A3 source-side cut is mandatory on a bank->bank hop
    and absent on a reservoir hop."""
    return (j - 1) % k != 0


def in_net(k, j, i, ideal_head=True):
    """THE POINT OF THE WHOLE DECK -- bank j's input net for cell i.
      * j == 1            -> ideal DC source in1_{i} (the chain head, chain3 verbatim)
      * segment-first j>1 -> rb{r}_{i}, the RESTORING stage's output
      * otherwise         -> literally o{j-1}_{i}, the predecessor's own output net,
                             NO buffer of any kind."""
    if j == 1:
        return "in1_%d" % i
    if (j - 1) % k == 0:
        return "rb%d_%d" % ((j - 1) // k, i)
    return "o%d_%d" % (j - 1, i)


# ------------------------------------------------------------------ schedule
def schedule(k, T, tres, nbank=NBANK):
    """Every time in the deck, from (k, T, tres) alone.

    Segment s's hops close at t_s, t_s+T, ..., t_s+(k-1)T.  The segment's last
    bank's data is valid at its boundary, the restoring stage needs tres, so
    t_{s+1} = t_s + k*T + tres.  Amortised time per logic stage = T + tres/k.
    """
    tp = topo(k, nbank)
    S = tp["S"]
    tseg = {s: T1 + s * (k * T + tres) for s in range(S)}
    close = {j: tseg[tp["seg"][j]] + tp["pos"][j] * T for j in range(1, nbank + 1)}
    # bank j is DRAINED by hop j+1 iff j+1 is in the same segment
    drain = {j: (close[j + 1] if tp["pos"][j] < k - 1 else None)
             for j in range(1, nbank + 1)}
    bound = {}
    for j in range(1, nbank + 1):
        b = close[j] + T
        if drain[j] is not None:
            b = min(b, drain[j] - EDGE)
        bound[j] = b
    tend = max(bound.values()) + TAIL
    te = TZ_ANCHOR * CHAIN_F
    tp.update(T=T, tres=tres, tseg=tseg, close=close, drain=drain, bound=bound,
              tend=tend, t_est=te, pstep=0.1, mstep=min(0.25, te / 1000.0),
              head_cut={s: tseg[s] - HEAD_LEAD for s in range(S)})
    return tp


# --------------------------------------------------------------- deck pieces
def head_lines():
    return ['.hdl "%s"' % VA, '.include "%s"' % MODEL, '.include "%s"' % SHIM,
            '.OPTIONS TIMEINT METHOD=GEAR RELTOL=1e-6 ABSTOL=1e-15 CHGTOL=1e-17']


def bank_cells(k, j, dv):
    """One level of logic.  Committed cell verbatim: pMOS w=1.12u with supply AND
    bulk on the BANK RAIL, nMOS w=0.74u, CL 2 fF."""
    L = ["VMG%d gn%d 0 0" % (j, j)]
    if j == 1:
        for i in range(MGATE):
            L.append("VI1_%d in1_%d 0 %g" % (i, i, dv if is_hi(1, i) else 0.0))
    for i in range(MGATE):
        s = in_net(k, j, i)
        L.append("XP%d_%d o%d_%d %s rail%d rail%d sg13_lv_pmos w=%gu l=0.13u"
                 % (j, i, j, i, s, j, j, WP))
        L.append("XN%d_%d o%d_%d %s gn%d gn%d sg13_lv_nmos w=%gu l=0.13u"
                 % (j, i, j, i, s, j, j, WN))
        L.append("CL%d_%d o%d_%d gn%d %gf" % (j, i, j, i, j, CLOAD))
    return L


def restore_stage(r, src_bank):
    """THE RESTORING STAGE.  One CMOS inverter PAIR per data bit, CL 2 fF on BOTH
    its internal node and its output -- so each of its two inverters carries
    exactly a bank cell's load.

    POWERED FROM THE FIXED SUPPLY vres, WITH BOTH pMOS BULKS ON vres.  That is what
    makes it restoring: its output level is referenced to a supply, not to a bank
    rail that the next hop drains.  It does NOT participate in the charge transfer
    -- which is exactly why the segment it feeds needs its own reservoir.

    Its INPUT is bank src_bank, the LAST bank of the preceding segment, which has
    no outgoing hop and is therefore never drained.

    AMENDMENT A4 -- SIZING.  The FIRST (receiving) inverter is SKEWED,
    pMOS 0.15u / nMOS 1.48u: committed qal/bound/ H1 cell A4, MEASURED trip point
    0.4595 V.  The campaign-standard 1.12u/0.74u cell does NOT work here and it was
    MEASURED not working in this very directory: its trip point is 0.6452 V, and its
    own 8 input gates drag the delivered QAL level from 0.7138 V to 0.6007 V, i.e.
    44.5 mV BELOW its own trip point, so it restores a HIGH as a LOW.  A4 is also
    LIGHTER (1.63 um of gate against 1.86 um), so it loads the bank it reads less,
    and its static contention is 0.0339 uA against 8.78 uA.
    The SECOND inverter stays the campaign standard 1.12u/0.74u: its input is a
    full-swing 0/1.2 V node, so there is nothing to skew for, and a PAIR keeps the
    stage non-inverting so the is_hi convention carries across a restore unchanged.
    """
    L = []
    for i in range(MGATE):
        s = "o%d_%d" % (src_bank, i)
        L += ["XRP%d_%da rm%d_%d %s vres vres sg13_lv_pmos w=%gu l=0.13u"
              % (r, i, r, i, s, RES_WP1),
              "XRN%d_%da rm%d_%d %s 0 0 sg13_lv_nmos w=%gu l=0.13u"
              % (r, i, r, i, s, RES_WN1),
              "CRM%d_%d rm%d_%d 0 %gf" % (r, i, r, i, CLOAD),
              "XRP%d_%db rb%d_%d rm%d_%d vres vres sg13_lv_pmos w=%gu l=0.13u"
              % (r, i, r, i, r, i, WP),
              "XRN%d_%db rb%d_%d rm%d_%d 0 0 sg13_lv_nmos w=%gu l=0.13u"
              % (r, i, r, i, r, i, WN),
              "CRB%d_%d rb%d_%d 0 %gf" % (r, i, r, i, CLOAD)]
    return L


def reservoir(s, dv):
    """Segment s's charge source: the committed CA = 35.979 fF lumped cap,
    pre-charged to dV in the DC operating point by .ic -- verbatim the committed
    single hop's own `CA bka 0 {CA}` + `.ic V(bka)=1.2`.

    AMENDMENT A3: no head gate.  chain3-A2's head gate exists because a bare .ic
    lets a BANK's cells charge their own outputs out of their own rail; a lumped
    capacitor has no cells.  The per-segment pre-charge is therefore MEASURED in
    its own deck (qpre.cir, real 1.0u/1.12u head gate, own metered supply) and
    carried into the economics from there, exactly as chain3-A4 treats it."""
    return ["CRES%d res%d 0 %gf" % (s + 1, s + 1, CA_FF)]


def transfer_switch(j, src, total_um, srccut):
    """Hop j between src and rail{j}.

    DESTINATION side (always): the committed tg15p triple between the inductor
    node sw{j} and rail{j}, verbatim.

    SOURCE side: the chain3-A3 identical triple between src and the inductor's
    near node a{j}, on the SAME phases, with no park on a{j}.  MANDATORY on every
    bank->bank hop -- without it 42.3% of a hop's charge is diverted into the idle
    next-stage inductor and the idle ring (tau = 2L/R = 55.6 ns) never damps.
    ABSENT on a reservoir hop (AMENDMENT A3): a reservoir is never charged by a
    hop, so it is never the state that failure describes, and the committed single
    hop -- which has no source-side cut -- is exactly that topology."""
    w = widths(total_um)
    L = ["XSWN%d sw%d gt%d rail%d 0 sg13_lv_nmos w=%gu l=0.13u"
         % (j, j, j, j, w["wn"]),
         "XSWP%d sw%d gtp%d rail%d vhi sg13_lv_pmos w=%gu l=0.13u"
         % (j, j, j, j, w["wp"]),
         "XPK%d sw%d pk%d 0 0 sg13_lv_nmos w=%gu l=0.13u" % (j, j, j, w["park"])]
    if srccut:
        L += ["XSWSN%d a%d gt%d %s 0 sg13_lv_nmos w=%gu l=0.13u"
              % (j, j, j, src, w["wn"]),
              "XSWSP%d a%d gtp%d %s vhi sg13_lv_pmos w=%gu l=0.13u"
              % (j, j, j, src, w["wp"])]
    return L


def phases(j, tc, to, big, srccut):
    """Committed phase set, verbatim.  tc=None -> hop idle.  to=None -> closes and
    never opens (the ZCS probe).

    PARK.  With a source-side cut the park may be HELD ON while the hop is idle,
    and that is what pins the otherwise-floating inductor island {a,mid,sw}.
    WITHOUT one (a reservoir hop) the source is permanently wired to the inductor,
    so an early park would discharge the reservoir to ground through L and R: the
    park must stay OFF until after the switch opens.  That is the committed single
    hop's own phase, `VPK pk 0 PWL(0 0 117.495p 0 119.495p 1.5)`.  The island is
    not floating in that case either -- it hangs off the pre-charged reservoir
    through L and R."""
    if tc is None:                                     # idle
        return ["VGT%d gt%d 0 0" % (j, j), "VGTP%d gtp%d 0 %g" % (j, j, VGH),
                "VPK%d pk%d 0 %g" % (j, j, VGH if srccut else 0.0)]
    if to is None:                                     # closes, never opens
        return ["VGT%d gt%d 0 PWL(0 0 %gp 0 %gp %g %gp %g)"
                % (j, j, tc - EDGE, tc, VGH, big, VGH),
                "VGTP%d gtp%d 0 PWL(0 %g %gp %g %gp 0 %gp 0)"
                % (j, j, VGH, tc - EDGE, VGH, tc, big),
                "VPK%d pk%d 0 %s" % (j, j,
                    ("PWL(0 %g %gp %g %gp 0)" % (VGH, tc, VGH, tc + EDGE))
                    if srccut else "0")]
    return ["VGT%d gt%d 0 PWL(0 0 %gp 0 %gp %g %gp %g %gp 0)"
            % (j, j, tc - EDGE, tc, VGH, to, VGH, to + EDGE),
            "VGTP%d gtp%d 0 PWL(0 %g %gp %g %gp 0 %gp 0 %gp %g)"
            % (j, j, VGH, tc - EDGE, VGH, tc, to, to + EDGE, VGH),
            ("VPK%d pk%d 0 PWL(0 %g %gp %g %gp 0 %gp 0 %gp %g)"
             % (j, j, VGH, tc, VGH, tc + EDGE, to + EDGE, to + 2 * EDGE, VGH))
            if srccut else
            ("VPK%d pk%d 0 PWL(0 0 %gp 0 %gp %g)"
             % (j, j, to + EDGE, to + 2 * EDGE, VGH))]


def integ(tg, expr):
    return ["CX%s x%s 0 1" % (tg, tg), "BX%s 0 x%s I={ %s }" % (tg, tg, expr),
            "RX%s x%s 0 0.01" % (tg, tg)]


def integrators(S, k, nbank, rs):
    L, tags = [], []
    for j in range(1, nbank + 1):
        sn = src_node(k, j)
        near = ("a%d" % j) if has_srccut(k, j) else sn
        for nm, ex in (("qlt%d" % j, "I(L%d)" % j),
                       ("ea%d" % j, "V(%s)*I(L%d)" % (sn, j)),
                       ("ean%d" % j, "V(%s)*I(L%d)" % (near, j)),
                       ("eb%d" % j, "V(rail%d)*I(L%d)" % (j, j)),
                       ("er%d" % j, "I(L%d)*I(L%d)*%g" % (j, j, rs)),
                       ("esw%d" % j, "V(sw%d)*I(L%d)" % (j, j))):
            L += integ(nm, ex); tags.append(nm)
    for j in range(1, nbank + 1):
        L += integ("qg%d" % j, "I(VMG%d)" % j); tags.append("qg%d" % j)
    # the fixed supplies, each ALWAYS connected (so no chain3-A4 degeneracy)
    L += integ("qres", "-I(VRES)"); tags.append("qres")       # RESTORING stages
    L += integ("qhi", "-I(VHI)");  tags.append("qhi")         # switch pMOS bulks
    L += integ("qi1", "-(" + "+".join("I(VI1_%d)" % i for i in range(MGATE)) + ")")
    tags.append("qi1")
    L += integ("egt", "-" + "-".join(
        "V(gt%d)*I(VGT%d)-V(gtp%d)*I(VGTP%d)-V(pk%d)*I(VPK%d)" % (j, j, j, j, j, j)
        for j in range(1, nbank + 1)))
    tags.append("egt")
    return L, tags


# --------------------------------------------------------------------- decks
def deck(k, T, tres, nbank=NBANK, dv=DV, l_nh=L_NH, total_um=W_UM, rs=RS_REF,
         tz=None, probe=None, trailing_restore=True):
    """probe = j -> hops 1..j-1 cut at their measured zeros, hop j closes at its
    beat and NEVER opens (the true-ZCS probe for hop j), later hops idle.
    probe = None -> the measured deck.

    trailing_restore: load the LAST bank with a restoring stage even though there
    is no next segment.  Used on the one-segment probe/tres deck so that its last
    bank carries the same output load it carries inside the full chain."""
    S = schedule(k, T, tres, nbank)
    nb = nbank
    tz = tz or [TZ_ANCHOR * CHAIN_F] * nb
    big = S["tend"] * 4.0
    L = head_lines() + [".param LT=%gn RS=%g" % (l_nh, rs),
                        "VHI vhi 0 %g" % VGH, "VRES vres 0 %g" % dv]
    # --- reservoirs (one per segment): the per-segment PRE-CHARGE
    for s in range(S["S"]):
        L += reservoir(s, dv)
    # --- restoring stages (internal only; AMENDMENT A1)
    for jb, r in sorted(S["restore_into"].items()):
        L += restore_stage(r, jb - 1)
    if trailing_restore and nb not in S["restore_into"]:
        L += restore_stage(S["S"], nb)        # loads the last bank identically
    # --- the banks.  Inside a segment, bank N's outputs ARE bank N+1's inputs.
    for j in range(1, nb + 1):
        L += bank_cells(k, j, dv)
    # --- the hops.  A bank->bank hop's inductor sits behind the source-side cut at
    #     a{j}; a reservoir hop's inductor connects DIRECTLY to the reservoir
    #     (AMENDMENT A3), which is the committed single hop's own topology.
    for j in range(1, nb + 1):
        sn = src_node(k, j)
        near = ("a%d" % j) if has_srccut(k, j) else sn
        L += ["L%d %s mid%d {LT}" % (j, near, j), "R%d mid%d sw%d {RS}" % (j, j, j)]
        L += transfer_switch(j, sn, total_um, has_srccut(k, j))
    # --- gate phases
    op = {}
    for j in range(1, nb + 1):
        tc, to = S["close"][j], S["close"][j] + tz[j - 1]
        sc = has_srccut(k, j)
        op[j] = to
        if probe is None or j < probe:
            L += phases(j, tc, to, big, sc)
        elif j == probe:
            L += phases(j, tc, None, big, sc)
        else:
            L += phases(j, None, None, big, sc)
    S["open"] = op
    tend = S["tend"] if probe is None else (S["close"][probe] + 1.8 * S["t_est"])
    tags = []
    if probe is None:
        ig, tags = integrators(S["S"], k, nb, rs)
        L += ig
    ic = ["V(res%d)=%g" % (s + 1, dv) for s in range(S["S"])] + \
         ["V(rail%d)=0" % j for j in range(1, nb + 1)] + \
         ["V(a%d)=0" % j for j in range(1, nb + 1) if has_srccut(k, j)]
    L.append(".ic " + " ".join(ic))
    L.append(".tran %gp %gp 0 %gp" % (S["pstep"], tend, S["mstep"]))

    g = lambda t: t + LAG_PS
    if probe is None:
        cks = [("Z", 0.5)] + [("B%d" % j, op[j]) for j in range(1, nb + 1)] \
              + [("K%d" % j, S["bound"][j]) for j in range(1, nb + 1)] \
              + [("D", tend - 5.0)]
        ckd = dict(cks)
        for tg in tags:
            for nm, tt in cks:
                L.append(".measure tran %s_%s FIND V(x%s) AT=%.6fp"
                         % (tg.upper(), nm, tg, g(tt)))
        for nm, tt in cks:
            for j in range(1, nb + 1):
                L.append(".measure tran VR%d%s FIND V(rail%d) AT=%.6fp"
                         % (j, nm, j, g(tt)))
            for s in range(S["S"]):
                L.append(".measure tran VS%d%s FIND V(res%d) AT=%.6fp"
                         % (s + 1, nm, s + 1, g(tt)))
        for j in range(1, nb + 1):
            L.append(".measure tran VR%dPK MAX V(rail%d) FROM=%gp TO=%gp"
                     % (j, j, T1, tend))
            for i in range(MGATE):
                # per-gate output at this bank's OWN stage boundary and at the end
                L.append(".measure tran O%d_%dS FIND V(o%d_%d) AT=%.6fp"
                         % (j, i, j, i, g(S["bound"][j])))
                L.append(".measure tran O%d_%dE FIND V(o%d_%d) AT=%.6fp"
                         % (j, i, j, i, g(tend - 5.0)))
                # THE MECHANISM: the gate drive this cell actually has at its own
                # boundary, and the worst excursion of that drive over the window
                # from its own hop closing to its own boundary.
                s = in_net(k, j, i)
                L.append(".measure tran G%d_%dB FIND V(%s) AT=%.6fp"
                         % (j, i, s, g(S["bound"][j])))
                L.append(".measure tran G%d_%dC FIND V(%s) AT=%.6fp"
                         % (j, i, s, g(S["close"][j] - EDGE)))
                fn = "MIN" if is_hi(j, i) else "MAX"
                L.append(".measure tran G%d_%dX %s V(%s) FROM=%gp TO=%gp"
                         % (j, i, fn, s, S["close"][j], S["bound"][j]))
            L.append(".measure tran IZ%d FIND I(L%d) AT=%.6fp" % (j, j, g(op[j])))
            L.append(".measure tran IPK%d MAX I(L%d) FROM=%gp TO=%gp"
                     % (j, j, T1, tend))
        # full per-gate traces on the cheap ONE-SEGMENT decks (nb < NBANK), where
        # the settling-vs-time curve is read; only two representative gates per
        # bank on the full 6-bank rows, to keep the .prn from filling the disk.
        bits = range(MGATE) if nb < NBANK else (0, 1)
        pr = ["V(rail%d)" % j for j in range(1, nb + 1)] + \
             ["V(res%d)" % (s + 1) for s in range(S["S"])] + \
             ["I(L%d)" % j for j in range(1, nb + 1)] + \
             ["V(o%d_%d)" % (j, i) for j in range(1, nb + 1) for i in bits]
    else:
        pr = ["I(L%d)" % j for j in range(1, nb + 1)] + \
             ["V(rail%d)" % j for j in range(1, nb + 1)] + \
             ["V(res%d)" % (s + 1) for s in range(S["S"])] + \
             ["V(sw%d)" % j for j in range(1, nb + 1)] + \
             ["V(a%d)" % j for j in range(1, nb + 1) if has_srccut(k, j)]
    # the RESTORING stage's own waveform: its input is the previous segment's last
    # bank, its output feeds the next segment's first bank.  Printed so tres is
    # MEASURED off the waveform, not assumed to be a gate delay.
    nres = S["S"] if (trailing_restore and nb not in S["restore_into"]) else 0
    rids = sorted(set(list(S["restore_into"].values()) + ([nres] if nres else [])))
    for r in rids:
        pr += ["V(rm%d_0)" % r, "V(rb%d_0)" % r, "V(rm%d_1)" % r, "V(rb%d_1)" % r]
    L.append(".print tran " + " ".join(pr))
    L.append(".end")
    return L, S


# --------------------------------------------------------------------- utils
def run(fn, lines, timeout=1800):
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
        if hdr is None or not p or p[0].lower().startswith("end"):
            continue
        try:
            rows.append([float(x) for x in p])
        except ValueError:
            continue
    return hdr, rows


def zero_after_peak(hdr, rows, col, t_close):
    """The TRUE ZCS instant for one hop: first sign change of I(L) after its peak,
    linearly interpolated (lsweep's refined rule)."""
    ic = hdr.index(col)
    pk, tpk = 0.0, None
    for r in rows:
        t = r[1] * 1e12
        if t < t_close:
            continue
        if abs(r[ic]) > abs(pk):
            pk, tpk = r[ic], t
    if tpk is None:
        return None, None
    prev = None
    for r in rows:
        t = r[1] * 1e12
        if t <= tpk:
            prev = (t, r[ic])
            continue
        if prev is not None and (r[ic] == 0.0 or (prev[1] > 0) != (r[ic] > 0)):
            t0, v0 = prev
            t1, v1 = t, r[ic]
            tz = t0 if v1 == v0 else t0 + (0.0 - v0) * (t1 - t0) / (v1 - v0)
            return tz, pk
        prev = (t, r[ic])
    return None, pk


def trace(hdr, rows, col, ta, tb):
    ic = hdr.index(col)
    return [(r[1] * 1e12, r[ic]) for r in rows if ta <= r[1] * 1e12 <= tb]


def at(hdr, rows, col, tt):
    ic = hdr.index(col)
    best, bt = None, None
    for r in rows:
        t = r[1] * 1e12
        if bt is None or abs(t - tt) < abs(bt - tt):
            bt, best = t, r[ic]
    return best


# -------------------------------------------------------------------- stages
def do_probe(k, T, tres, dv=DV):
    """Sequential true-ZCS probe on a ONE-SEGMENT deck (AMENDMENT A2): hop 1's
    zero, then hop 2's with hop 1 cut at its own zero, and so on for the k hops of
    one segment.  The zeros are then reused for every segment of the full chain and
    VALIDATED there by the per-hop ZCS gate A4."""
    tz = []
    for h in range(1, k + 1):
        lines, S = deck(k, T, tres, nbank=k,
                        tz=tz + [TZ_ANCHOR * CHAIN_F] * (k - len(tz)), probe=h)
        fn = "p%d_k%d_T%g.cir" % (h, k, T)
        path = os.path.join(HERE, fn)
        cached = (os.path.exists(path) and os.path.exists(path + ".prn")
                  and open(path).read() == "\n".join(lines) + "\n")
        if cached:
            p, msg = path, "reused %s (byte-identical deck already run)" % fn
        else:
            p, msg = run(fn, lines)
        print("  probe%d %s" % (h, msg), flush=True)
        if p is None:
            return None
        hdr, rows = read_prn(p + ".prn")
        z, pk = zero_after_peak(hdr, rows, "I(L%d)" % h, S["close"][h])
        if z is None:
            print("  probe%d NO ZERO" % h)
            return None
        tz.append(z - S["close"][h])
        print("    hop%d t_zcs = %.4f ps (Ipk %.2f uA)" % (h, tz[-1], pk * 1e6),
              flush=True)
    return tz


def do_seg(k, T, tres, tz):
    """The ONE-SEGMENT measured deck: same segment as the chain, plus its trailing
    restoring stage.  Used to MEASURE tres off the restoring stage's own waveform."""
    lines, S = deck(k, T, tres, nbank=k, tz=tz)
    fn = "s_k%d_T%g.cir" % (k, T)
    path = os.path.join(HERE, fn)
    if (os.path.exists(path) and os.path.exists(path + ".prn")
            and os.path.exists(path + ".mt0")
            and open(path).read() == "\n".join(lines) + "\n"):
        print("  seg reused %s (byte-identical deck already run)" % fn, flush=True)
        return path, S
    p, msg = run(fn, lines)
    print("  seg %s" % msg, flush=True)
    return (p, S) if p else None


def do_row(k, T, tres, tz):
    lines, S = deck(k, T, tres, nbank=NBANK, tz=tz * (NBANK // k))
    fn = "c_k%d_T%g.cir" % (k, T)
    p, msg = run(fn, lines)
    print("  row %s" % msg, flush=True)
    return (p, S) if p else None


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "probe":
        print(json.dumps(do_probe(int(a[1]), float(a[2]), float(a[3]))))
    elif a[0] == "seg":
        do_seg(int(a[1]), float(a[2]), float(a[3]), json.loads(a[4]))
    elif a[0] == "row":
        do_row(int(a[1]), float(a[2]), float(a[3]), json.loads(a[4]))
    elif a[0] == "dump":
        k, T, tres = int(a[1]), float(a[2]), float(a[3])
        lines, S = deck(k, T, tres, nbank=NBANK)
        print("\n".join(lines))
