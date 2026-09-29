#!/usr/bin/env python3
"""qal/tankfed -- TOP-UP DESTINATION (bank vs TANK) x TANK SIZING (uniform vs
per-bank matched), on a chain carrying the REAL sha_slice bank-size profile.

Everything that is not the tank or the top-up destination is the committed
harness VERBATIM: the cell (sg13_lv_pmos w=1.12u / sg13_lv_nmos w=0.74u l=0.13u,
CL 2 fF, supply AND pMOS bulk on the bank node), the tg15p transfer switch
(TG 10/20 um + 2 um park) on BOTH the source and destination side, L = 15 nH,
RS = 10 ohm, the gate phases, the head pre-charge gate, the probe-then-cut TRUE
ZCS protocol, the 1F-integrator metering, the boundary rule and the per-gate
settling convention.  Those come from qal/skip4/skip.py, which is
qal/chain3/chain.py verbatim, which is qal/lsweep/lsw.py verbatim.

WHAT IS NEW HERE AND NOWHERE ELSE:
  1. BANK SIZE IS A PER-BANK PARAMETER (the real 48/19/3/1/2 profile), with the
     predecessor's outputs FANNING OUT where a bank grows.  No buffering.
  2. Every bank carries its own TANK: CTK_k from ntk_k to ground, strapped to
     rail_k through an explicit RSTRAP.  ntk_k is touched by no cell.
  3. The top-up's DESTINATION is a parameter: rail_k (baseline) or ntk_k.
  4. The tank SIZING is a parameter: uniform, or C_tank_k = m * C_bank_k with
     C_bank_k MEASURED per size.

Pre-registration: PRE_REGISTERED.json (sha256 78fc0ac0..., 21518 B,
mtime 2026-09-29 09:02:10.626 -0700, the sole file in this directory then).
"""
import json, os, re, subprocess, sys, time

HERE  = os.path.dirname(os.path.abspath(__file__))
XYCE  = "/usr/local/src/xyce-build/src/Xyce"
VA    = "/usr/local/share/xyce/verilog-a/psp103/psp103.va"
MODEL = "/usr/local/src/kestrel/sim/models/sg13g2_psp103_tt.lib"
SHIM  = "/usr/local/src/stat-sim/qal/sg13lv_compat.sp"
CACHE = "/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6/scratchpad/vae_cache_tankfed"
ENV   = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS", PYMS_VAE_CACHE=CACHE)

# ---- inherited constants (committed; not touched) --------------------------
RS_REF    = 10.0
VGH       = 1.5
WP, WN    = 1.12, 0.74          # cell inverter widths
CLOAD     = 2.0                 # fF per cell output
EDGE      = 2.0                 # ps, committed transfer-gate edge
LAG_PS    = 1.0                 # MEASURED .measure-FIND lag in this Xyce build
HEAD_EDGE = 20.0
HEAD_LEAD = 40.0
HEAD_WN, HEAD_WP = 1.0, 1.12
TAIL      = 500.0
TOPUP_W   = 20.0                # ps, clamp top-up conduction window
T1        = 200.0               # ps, beat 1 closes
TZ_ANCHOR = 65.49500982344826   # ps, committed L=15/W30/dV1.2 single-hop zero
CHAIN_F   = 1.35                # DERIVED sizing factor only

# ---- NEW here --------------------------------------------------------------
PROFILE   = [48, 19, 3, 1, 2]   # the sha_slice-derived bank sizes, depth 5
RSTRAP    = 2.0                 # ohm, tank->rail metal strap.  ASSUMED.
CNA_FF    = 8.0                 # ASSUMED buck switch-node capacitance
SLEW      = 24.0                # ps, corrected low-side turn-off slew (ptu)
RSTU      = 10.0                # ohm, top-up inductor series R
VSUP      = 1.2                 # V, top-up supply (the buck's Vin)
TOPPED    = (3, 4)              # banks that get a top-up
TOPUP_WSW = 10.0                # um, buck high-side/low-side switch width
HOPS      = [(1, 2), (2, 3), (3, 4), (4, 5)]
# .prn columns for the cell outputs are restricted to the banks the time-domain
# coupling measurement actually reads (the feeding stages of the topped banks and
# the topped banks themselves).  Per-gate SETTLING for every bank still comes
# from the .mt0, which carries all 73 outputs -- nothing is aggregated or lost.
PRINT_BANKS = (2, 3, 4)
HEADS     = [1]


def widths(total_um):
    """1:2 n:p TG + park = total/15.  total=30 reproduces the committed tg15p
    pair used in the chain decks (TG 10/20 um + 2 um park)."""
    return dict(wn=total_um / 3.0, wp=2.0 * total_um / 3.0, park=total_um / 15.0)


def is_hi(k, i):
    """Bank k cell i has a logic-HIGH input (a pull-DOWN cell) iff (i+k) is odd.
    Bank 1's inputs alternate 1,0,1,0..., every bank inverts."""
    return (i + k) % 2 == 1


def in_net(k, i, prof):
    """k==1 -> ideal source (chain head); k>1 -> literally o{k-1}_{i mod M_{k-1}},
    the predecessor's output net.  The modulo is the FAN-OUT that a real
    non-monotonic size profile forces when a bank is wider than its predecessor.
    No buffer, no latch, no level shifter."""
    if k == 1:
        return "in1_%d" % i
    return "o%d_%d" % (k - 1, i % prof[k - 2])


def expect_hi(k, i, prof):
    """The EXPECTED logic value of o{k}_{i}: a pull-DOWN cell (HIGH input) drives
    its output LOW, a pull-UP cell drives it HIGH.  Used by the value check."""
    return not is_hi(k, i)


# ------------------------------------------------------------------ schedule
def schedule(T, dv, tz=None, prof=PROFILE):
    nb = len(prof)
    tz = tz or [TZ_ANCHOR * CHAIN_F] * len(HOPS)
    close = [T1 + h * T for h in range(len(HOPS))]
    open_ = [close[h] + tz[h] for h in range(len(HOPS))]
    c, d = {}, {}
    for h, (s, t) in enumerate(HOPS):
        c[t] = close[h]
        d[s] = close[h]
    bound = {}
    for k in range(1, nb + 1):
        if k in c:
            b = c[k] + T
            if k in d:
                b = min(b, d[k] - EDGE)
        else:
            b = d[k] - EDGE
        bound[k] = b
    tend = max(max(bound.values()), max(open_)) + TAIL
    te = TZ_ANCHOR * CHAIN_F
    return dict(nbank=nb, hops=HOPS, heads=HEADS, T=T, close=close, open=open_,
                c=c, d=d, bound=bound, tend=tend, tz=tz, prof=prof,
                head_cut={k: d[k] - HEAD_LEAD for k in HEADS},
                pstep=0.1, mstep=min(0.25, te / 1000.0), t_est=te)


# --------------------------------------------------------------- deck pieces
def head_lines():
    return ['.hdl "%s"' % VA, '.include "%s"' % MODEL, '.include "%s"' % SHIM,
            '.OPTIONS TIMEINT METHOD=GEAR RELTOL=1e-6 ABSTOL=1e-15 CHGTOL=1e-17']


def bank_cells(k, dv, prof):
    """One level of logic.  M_k committed inverter cells."""
    M = prof[k - 1]
    L = ["VMG%d gn%d 0 0" % (k, k)]
    if k == 1:
        for i in range(M):
            L.append("VI%d_%d in%d_%d 0 %g"
                     % (k, i, k, i, dv if is_hi(k, i) else 0.0))
    for i in range(M):
        s = in_net(k, i, prof)
        L.append("XP%d_%d o%d_%d %s rail%d rail%d sg13_lv_pmos w=%gu l=0.13u"
                 % (k, i, k, i, s, k, k, WP))
        L.append("XN%d_%d o%d_%d %s gn%d gn%d sg13_lv_nmos w=%gu l=0.13u"
                 % (k, i, k, i, s, k, k, WN))
        L.append("CL%d_%d o%d_%d gn%d %gf" % (k, i, k, i, k, CLOAD))
    return L


def tank(k, ctk_fF):
    """Bank k's TANK.  ntk_k is touched by NO cell -- it is not a signal-path
    node.  It reaches the bank only through the explicit metal strap RSTRAP."""
    if ctk_fF is None or ctk_fF <= 0:
        return []
    return ["CTK%d ntk%d 0 %.6gf" % (k, k, ctk_fF),
            "RTK%d ntk%d rail%d %g" % (k, k, k, RSTRAP)]


def transfer_switch(h, src, dst, total_um):
    """tg15p triple on the DESTINATION side, plus the mandatory SOURCE-side cut."""
    w = widths(total_um)
    return ["XSWN%d sw%d gt%d rail%d 0 sg13_lv_nmos w=%gu l=0.13u"
            % (h, h, h, dst, w["wn"]),
            "XSWP%d sw%d gtp%d rail%d vhi sg13_lv_pmos w=%gu l=0.13u"
            % (h, h, h, dst, w["wp"]),
            "XPK%d sw%d pk%d 0 0 sg13_lv_nmos w=%gu l=0.13u" % (h, h, h, w["park"]),
            "XSWSN%d a%d gt%d rail%d 0 sg13_lv_nmos w=%gu l=0.13u"
            % (h, h, h, src, w["wn"]),
            "XSWSP%d a%d gtp%d rail%d vhi sg13_lv_pmos w=%gu l=0.13u"
            % (h, h, h, src, w["wp"])]


HEAD_NREP, HEAD_PREP = 5, 3     # parallel copies of the 10 um nMOS / 20 um pMOS


def head_tg(k, total_um, win, ctot_fF=None):
    """The chain head's pre-charge gate.  DEVIATION FROM THE COMMITTED DECK, and
    it is forced.  The committed gate is a fixed 1 um / 1.12 um pair, sized for a
    36.6 fF 8-cell bank (Ron*C ~ 22 ps, fully charged inside the 160 ps
    pre-charge window).  Here the head node is a 48-cell bank PLUS its tank -- up
    to ~1.5 pF, 40x more -- and a fixed 1 um gate has Ron*C ~ 900 ps: it could
    not hold the head rail at dV at all, and would hold it at a DIFFERENT level
    in every tank configuration, confounding the whole matrix with a
    head-charging artefact.

    So the head switch is 5 PARALLEL copies of the 10 um tg15p nMOS (50 um) and
    3 parallel copies of the 20 um tg15p pMOS (60 um), FIXED for every
    configuration.  Two reasons for parallel copies of an existing width rather
    than one wide device: (i) it introduces NO new device geometry, and PyMS
    builds a separate compiled model per width (a ~5 min compile each), and
    (ii) a head width that varied with the tank size would itself be a
    configuration variable.  MEASURED Ron ~ 60 ohm at w=10 um (Track C) gives
    Ron ~ 12 ohm for the parallel nMOS, i.e. Ron*C ~ 18 ps on the largest head
    node -- the committed 22 ps, preserved.

    The head is the BOUNDARY of the modelled system: it is fed by the ideal dV
    source, so every number that depends on the head rail is a BOUND either way.
    """
    e = HEAD_EDGE
    b = win[1]
    L = []
    for j in range(HEAD_NREP):
        L.append("XHDN%d_%d rail%d hdn%d vdv 0 sg13_lv_nmos w=10u l=0.13u"
                 % (k, j, k, k))
    for j in range(HEAD_PREP):
        L.append("XHDP%d_%d rail%d hdp%d vdv vhi sg13_lv_pmos w=20u l=0.13u"
                 % (k, j, k, k))
    return L + [
        "VHDN%d hdn%d 0 PWL(0 %g %gp %g %gp 0)" % (k, k, VGH, b, VGH, b + e),
        "VHDP%d hdp%d 0 PWL(0 0 %gp 0 %gp %g)" % (k, k, b, b + e, VGH)]


def topup_clamp(k, dest, total_um, win, live):
    """THE COMMITTED SWITCHED CLAMP ('rtu').  A tg15p-sized transmission gate
    between the ideal dV source and the DESTINATION node.  Present-but-disabled
    when live is False -- which is the correct free control, because chain3
    measured that merely HAVING the gate present shifts t_zcs by +11.5 ps and
    VBEND2 by -43.4 mV.  The committed study's own free control omits the device
    entirely, so its 'attributable' damage conflates presence with firing; this
    one does not."""
    w = widths(total_um)
    L = ["XTUN%d %s tun%d vdv 0 sg13_lv_nmos w=%gu l=0.13u" % (k, dest, k, w["wn"]),
         "XTUP%d %s tup%d vdv vhi sg13_lv_pmos w=%gu l=0.13u" % (k, dest, k, w["wp"])]
    if not live or win is None:
        return L + ["VTUN%d tun%d 0 0" % (k, k), "VTUP%d tup%d 0 %g" % (k, k, VGH)]
    a, b = win
    e = EDGE
    return L + ["VTUN%d tun%d 0 PWL(0 0 %gp 0 %gp %g %gp %g %gp 0)"
                % (k, k, a, a + e, VGH, b, VGH, b + e),
                "VTUP%d tup%d 0 PWL(0 %g %gp %g %gp 0 %gp 0 %gp %g)"
                % (k, k, VGH, a, VGH, a + e, b, b + e, VGH)]


def topup_buck(k, dest, ltu_nh, t_fire, t_on, tfw, big, live):
    """THE CORRECTED PULSED BUCK ('ptu'), qal/ptu/chain.py::topup_dev_corrected
    verbatim in its gate sequence and its mandatory CNA, re-pointed at `dest`.

        HS pMOS ON at t_fire (while the LS still clamps na at 0)
        LS nMOS released over SLEW ps, ending at a = t_fire + SLEW + 4*EDGE
        OUT switch CLOSES last, [a-EDGE, a]
        HS conducts to b = a + t_on, then HS off / LS on -> freewheel
        OUT OPENS at the MEASURED freewheel current zero, z = b + tfw

    live=False keeps every device present and every gate parked OFF -- the free
    control must carry the same parasitic load as the topped row or the
    difference is not attributable."""
    e = EDGE
    a = t_fire + SLEW + 4 * e
    b = a + t_on
    probe_form = (tfw is None)
    z = big if probe_form else b + tfw
    w = widths(TOPUP_WSW * 1.5)
    L = ["CNA%d na%d 0 %gf" % (k, k, CNA_FF),
         "XTUSW%d na%d gtu%d tsup tsup sg13_lv_pmos w=%gu l=0.13u"
         % (k, k, k, TOPUP_WSW),
         "XTUFW%d na%d gfw%d 0 0 sg13_lv_nmos w=%gu l=0.13u"
         % (k, k, k, TOPUP_WSW),
         "LTU%d na%d ntm%d %gn" % (k, k, k, ltu_nh),
         "RTU%d ntm%d nb%d %g" % (k, k, k, RSTU),
         "VMTU%d nb%d nbx%d 0" % (k, k, k),
         "XTUON%d nbx%d gto%d %s 0 sg13_lv_nmos w=%gu l=0.13u"
         % (k, k, k, dest, w["wn"]),
         "XTUOP%d nbx%d gtop%d %s vhi sg13_lv_pmos w=%gu l=0.13u"
         % (k, k, k, dest, w["wp"])]
    if not live:
        return L + ["VGTU%d gtu%d 0 %g" % (k, k, VGH),
                    "VGFW%d gfw%d 0 %g" % (k, k, VGH),
                    "VGTO%d gto%d 0 0" % (k, k),
                    "VGTOP%d gtop%d 0 %g" % (k, k, VGH)]
    L += ["VGTU%d gtu%d 0 PWL(0 %g %gp %g %gp 0 %gp 0 %gp %g)"
          % (k, k, VGH, t_fire, VGH, t_fire + 2 * e, b, b + e, VGH),
          "VGFW%d gfw%d 0 PWL(0 %g %gp %g %gp 0 %gp 0 %gp %g)"
          % (k, k, VGH, a - SLEW, VGH, a, b, b + e, VGH)]
    if probe_form:
        L += ["VGTO%d gto%d 0 PWL(0 0 %gp 0 %gp %g %gp %g)"
              % (k, k, a - e, a, VGH, z, VGH),
              "VGTOP%d gtop%d 0 PWL(0 %g %gp %g %gp 0 %gp 0)"
              % (k, k, VGH, a - e, VGH, a, z)]
    else:
        L += ["VGTO%d gto%d 0 PWL(0 0 %gp 0 %gp %g %gp %g %gp 0)"
              % (k, k, a - e, a, VGH, z, VGH, z + e),
              "VGTOP%d gtop%d 0 PWL(0 %g %gp %g %gp 0 %gp 0 %gp %g)"
              % (k, k, VGH, a - e, VGH, a, z, z + e, VGH)]
    return L


def integ(tg, expr):
    return ["CX%s x%s 0 1" % (tg, tg), "BX%s 0 x%s I={ %s }" % (tg, tg, expr),
            "RX%s x%s 0 0.01" % (tg, tg)]


def phases(h, tc, to, big):
    if tc is None:
        return ["VGT%d gt%d 0 0" % (h, h), "VGTP%d gtp%d 0 %g" % (h, h, VGH),
                "VPK%d pk%d 0 %g" % (h, h, VGH)]
    if to is None:
        return ["VGT%d gt%d 0 PWL(0 0 %gp 0 %gp %g %gp %g)"
                % (h, h, tc - EDGE, tc, VGH, big, VGH),
                "VGTP%d gtp%d 0 PWL(0 %g %gp %g %gp 0 %gp 0)"
                % (h, h, VGH, tc - EDGE, VGH, tc, big),
                "VPK%d pk%d 0 PWL(0 %g %gp %g %gp 0)" % (h, h, VGH, tc, VGH, tc + EDGE)]
    return ["VGT%d gt%d 0 PWL(0 0 %gp 0 %gp %g %gp %g %gp 0)"
            % (h, h, tc - EDGE, tc, VGH, to, VGH, to + EDGE),
            "VGTP%d gtp%d 0 PWL(0 %g %gp %g %gp 0 %gp 0 %gp %g)"
            % (h, h, VGH, tc - EDGE, VGH, tc, to, to + EDGE, VGH),
            "VPK%d pk%d 0 PWL(0 %g %gp %g %gp 0 %gp 0 %gp %g)"
            % (h, h, VGH, tc, VGH, tc + EDGE, to + EDGE, to + 2 * EDGE, VGH)]


# --------------------------------------------------------------------- decks
def deck(cfg, tz=None, probe=None, tu_probe=None, tfw=None):
    """cfg: dict(T, dv, ctk={k:fF}, dest='bank'|'tank', form='free'|'clamp'|'ptu',
                 ltu, ton, total_um, l_nh, rs)
    probe = h       -> hops 1..h-1 cut at their zeros, hop h closes and never
                       opens (the hop ZCS probe), later hops idle.
    tu_probe = k    -> bank k's top-up OUT switch closes and never opens (the
                       top-up freewheel ZCS probe).
    """
    T, dv = cfg["T"], cfg["dv"]
    prof = cfg.get("prof", PROFILE)
    total_um, l_nh, rs = cfg.get("total_um", 30.0), cfg.get("l_nh", 15.0), cfg.get("rs", RS_REF)
    S = schedule(T, dv, tz, prof)
    big = S["tend"] * 4.0
    nb, nh = S["nbank"], len(S["hops"])
    form, dest = cfg["form"], cfg["dest"]
    L = head_lines() + [".param LT=%gn RS=%g" % (l_nh, rs),
                        "VHI vhi 0 %g" % VGH, "VDV vdv 0 %g" % dv]
    if form == "ptu" or cfg.get("always_sup"):
        L.append("VSUP tsup 0 %g" % VSUP)
    for k in range(1, nb + 1):
        L += bank_cells(k, dv, prof)
    for k in range(1, nb + 1):
        L += tank(k, cfg["ctk"].get(k))
    for k in S["heads"]:
        ct = (cfg["ctk"].get(k) or 0.0) + cfg.get("cbank", {}).get(k, 0.0)
        L += head_tg(k, total_um, (0.0, S["head_cut"][k]), ct)
    # --- the top-up devices: PRESENT on every topped bank in EVERY mode, live
    #     only when the form asks for it (so 'free' is a like-for-like control)
    for k in (() if form == "bare" else TOPPED):
        if k > nb:
            continue
        dnode = ("rail%d" % k) if dest == "bank" else ("ntk%d" % k)
        t_open = S["open"][[t for _, t in S["hops"]].index(k)] if k in S["c"] else None
        t_fire = (t_open + 6 * EDGE) if t_open is not None else None
        if form == "clamp":
            win = (t_fire, t_fire + TOPUP_W) if t_fire is not None else None
            L += topup_clamp(k, dnode, total_um, win, True)
        elif form == "ptu":
            live = True
            tf_k = None if (tu_probe == k) else (tfw or {}).get(k)
            if tu_probe is not None and tu_probe != k:
                live = False
            L += topup_buck(k, dnode, cfg["ltu"], t_fire, cfg["ton"], tf_k, big, live)
        else:
            L += topup_clamp(k, dnode, total_um, None, False)
    for h, (s, t) in enumerate(S["hops"], 1):
        L += ["L%d a%d mid%d {LT}" % (h, h, h), "R%d mid%d sw%d {RS}" % (h, h, h)]
        L += transfer_switch(h, s, t, total_um)
    for h in range(1, nh + 1):
        tc, to = S["close"][h - 1], S["open"][h - 1]
        if probe is None or h < probe:
            L += phases(h, tc, to, big)
        elif h == probe:
            L += phases(h, tc, None, big)
        else:
            L += phases(h, None, None, big)
    # ---- metering (row decks only)
    tags = []
    if probe is None and tu_probe is None:
        for h, (s, t) in enumerate(S["hops"], 1):
            for nm, ex in (("qlt%d" % h, "I(L%d)" % h),
                           ("ea%d" % h, "V(rail%d)*I(L%d)" % (s, h)),
                           ("eb%d" % h, "V(rail%d)*I(L%d)" % (t, h)),
                           ("er%d" % h, "I(L%d)*I(L%d)*%g" % (h, h, rs))):
                L += integ(nm, ex); tags.append(nm)
        for k in range(1, nb + 1):
            L += integ("qg%d" % k, "I(VMG%d)" % k); tags.append("qg%d" % k)
        L += integ("qdv", "-I(VDV)"); tags.append("qdv")
        L += integ("qi1", "-(" + "+".join("I(VI1_%d)" % i for i in range(prof[0])) + ")")
        tags.append("qi1")
        L += integ("egt", "-" + "-".join(
            "V(gt%d)*I(VGT%d)-V(gtp%d)*I(VGTP%d)-V(pk%d)*I(VPK%d)" % (h, h, h, h, h, h)
            for h in range(1, nh + 1)))
        tags.append("egt")
        if form == "ptu":
            L += integ("qsup", "-I(VSUP)"); tags.append("qsup")
            L += integ("esup", "-%g*I(VSUP)" % VSUP); tags.append("esup")
            for k in TOPPED:
                if k > nb:
                    continue
                L += integ("qtu%d" % k, "I(VMTU%d)" % k); tags.append("qtu%d" % k)
                dn = ("rail%d" % k) if dest == "bank" else ("ntk%d" % k)
                L += integ("etu%d" % k, "V(%s)*I(VMTU%d)" % (dn, k)); tags.append("etu%d" % k)
                L += integ("egtu%d" % k,
                           "-V(gtu%d)*I(VGTU%d)-V(gfw%d)*I(VGFW%d)"
                           "-V(gto%d)*I(VGTO%d)-V(gtop%d)*I(VGTOP%d)"
                           % (k, k, k, k, k, k, k, k))
                tags.append("egtu%d" % k)
        elif form == "clamp":
            for k in TOPPED:
                if k > nb:
                    continue
                L += integ("egtu%d" % k,
                           "-V(tun%d)*I(VTUN%d)-V(tup%d)*I(VTUP%d)" % (k, k, k, k))
                tags.append("egtu%d" % k)
    ic = " ".join("V(rail%d)=%g" % (k, dv if k in S["heads"] else 0.0)
                  for k in range(1, nb + 1))
    ic += " " + " ".join("V(ntk%d)=%g" % (k, dv if k in S["heads"] else 0.0)
                         for k in range(1, nb + 1) if cfg["ctk"].get(k))
    L.append(".ic " + ic + " " + " ".join("V(a%d)=0" % h for h in range(1, nh + 1)))
    if probe is not None:
        # AMENDMENT A8: the probe window must be long enough to contain the zero
        # of a HEAVILY DAMPED hop.  The committed 6*t_est is sized for the
        # committed Q; a matched tank raises C_ser until Q approaches 1/2, and a
        # damped half-period is pi/omega_d = pi/(omega_0*sqrt(1-1/(4Q^2))),
        # which diverges as Q -> 1/2.  cfg['probe_span'] is set from the
        # configuration's own DERIVED hop, never from the committed anchor.
        tend = S["close"][probe - 1] + cfg.get("probe_span", 6.0 * S["t_est"])
    elif tu_probe is not None:
        tend = S["bound"][tu_probe] + 2.0 * S["t_est"]
    else:
        tend = S["tend"]
    L.append(".tran %gp %gp 0 %gp" % (S["pstep"], tend, S["mstep"]))
    g = lambda t: t + LAG_PS
    if probe is None and tu_probe is None:
        cks = [("Z", 0.5)] + [("B%d" % h, S["open"][h - 1]) for h in range(1, nh + 1)] \
              + [("K%d" % k, S["bound"][k]) for k in range(1, nb + 1)] \
              + [("D", tend - 5.0)]
        for tg in tags:
            for nm, tt in cks:
                L.append(".measure tran %s_%s FIND V(x%s) AT=%.6fp" % (tg.upper(), nm, tg, g(tt)))
        for nm, tt in cks:
            for k in range(1, nb + 1):
                L.append(".measure tran VR%d%s FIND V(rail%d) AT=%.6fp" % (k, nm, k, g(tt)))
                if cfg["ctk"].get(k):
                    L.append(".measure tran VT%d%s FIND V(ntk%d) AT=%.6fp" % (k, nm, k, g(tt)))
        for k in range(1, nb + 1):
            L.append(".measure tran VR%dPK MAX V(rail%d) FROM=%gp TO=%gp" % (k, k, T1, tend))
            for i in range(prof[k - 1]):
                L.append(".measure tran O%d_%dS FIND V(o%d_%d) AT=%.6fp"
                         % (k, i, k, i, g(S["bound"][k])))
                L.append(".measure tran O%d_%dE FIND V(o%d_%d) AT=%.6fp"
                         % (k, i, k, i, g(tend - 5.0)))
                # the DELIVERED GATE DRIVE: this cell's own input net, read at
                # THIS bank's boundary.  The pattern guard of A4 needs it -- a
                # node that merely sits undisturbed because its driver is off
                # must not be counted as settled.
                L.append(".measure tran G%d_%d FIND V(%s) AT=%.6fp"
                         % (k, i, in_net(k, i, prof), g(S["bound"][k])))
        for h in range(1, nh + 1):
            L.append(".measure tran IZ%d FIND I(L%d) AT=%.6fp" % (h, h, g(S["open"][h - 1])))
            L.append(".measure tran IPK%d MAX I(L%d) FROM=%gp TO=%gp" % (h, h, T1, tend))
        pr = ["V(rail%d)" % k for k in range(1, nb + 1)] + \
             ["V(ntk%d)" % k for k in range(1, nb + 1) if cfg["ctk"].get(k)] + \
             ["I(L%d)" % h for h in range(1, nh + 1)] + \
             ["V(o%d_%d)" % (k, i) for k in PRINT_BANKS if k <= nb
              for i in range(prof[k - 1])]
        if form == "ptu":
            pr += ["I(LTU%d)" % k for k in TOPPED if k <= nb] + \
                  ["V(na%d)" % k for k in TOPPED if k <= nb]
    else:
        pr = ["I(L%d)" % h for h in range(1, nh + 1)] + \
             ["V(rail%d)" % k for k in range(1, nb + 1)] + \
             ["V(ntk%d)" % k for k in range(1, nb + 1) if cfg["ctk"].get(k)]
        if tu_probe is not None:
            pr += ["I(LTU%d)" % tu_probe, "V(na%d)" % tu_probe]
    L.append(".print tran " + " ".join(pr))
    L.append(".end")
    return L, S


# --------------------------------------------------------------------- utils
def run(fn, lines, timeout=1500, reuse=True):
    path = os.path.join(HERE, fn)
    body = "\n".join(lines) + "\n"
    if reuse and os.path.exists(path) and os.path.exists(path + ".prn") \
            and open(path).read() == body:
        return path, "reused %s (byte-identical deck already run)" % fn
    open(path, "w").write(body)
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
            prev = (t, r[ic]); continue
        if prev is not None and (r[ic] == 0.0 or (prev[1] > 0) != (r[ic] > 0)):
            t0, v0 = prev; t1, v1 = t, r[ic]
            tz = t0 if v1 == v0 else t0 + (0.0 - v0) * (t1 - t0) / (v1 - v0)
            return tz, pk
        prev = (t, r[ic])
    return None, pk


def at(hdr, rows, col, tt):
    ic = hdr.index(col)
    best, bt = None, None
    for r in rows:
        t = r[1] * 1e12
        if bt is None or abs(t - tt) < abs(bt - tt):
            bt, best = t, r[ic]
    return best


def max_slope(hdr, rows, col, ta, tb):
    """max |dV/dt| in V/ns by centred finite difference on the printed grid."""
    ic = hdr.index(col)
    s = [(r[1] * 1e12, r[ic]) for r in rows if ta <= r[1] * 1e12 <= tb]
    best, bt = 0.0, None
    for j in range(1, len(s) - 1):
        dt = s[j + 1][0] - s[j - 1][0]
        if dt <= 0:
            continue
        d = abs(s[j + 1][1] - s[j - 1][1]) / dt * 1e3   # V/ps -> V/ns
        if d > best:
            best, bt = d, s[j][0]
    return best, bt
