#!/usr/bin/env python3
"""UPSIZE -- the CELL-SCALE SWEEP.  Phase 2 of the QAL amortisation question.

This file is qal/widebank/wb.py (sha256 188cf264..., recorded in
DISK_STATE_BEFORE.txt) with the CELL SCALE threaded through.  `diff wb.py up.py`
is the audit record and is reproduced in DIFF_wb_to_up.txt.  Everything else --
architecture, switch triple, park referencing, gate phases, true-ZCS
probe-then-cut, 1F-integrator metering, .OPTIONS -- is untouched, and
acceptance B0a REQUIRES that at scale = 1 this file emits decks BYTE-IDENTICAL
to Phase 1's, which is what licenses calling the s=1 point the same experiment.

WHAT IS NEW IN PHASE 2:
  * the CELL scale s is the swept axis: WP = 1.12*s, WN = 0.74*s um, L
    unchanged.  s in {1,2,4,8}.
  * C_bank_nominal(N,s) = CBANK8*(N/8)*s and C_tank = m*C_bank_nominal, so the
    nominal tank ratio is held while the cells grow.
  * the switch grows as W ~ sqrt(N*s) from the same constant-Q argument.
  * max timestep is NOT scaled by s (upsizing makes the cells FASTER while the
    hop gets slower; coarsening the grid there would blur the axis under test).
  * `scale` may be a per-bank list, for the E1 control where the measured bank
    drives an UNSCALED load inside the real chain.
  * stage `cellchain`: the CRUX instrument -- five cells at a FIXED rail, three
    load conventions, which is where the driver-and-load co-scaling question is
    actually answered.  The 3-bank rows cannot answer it (they are
    rail-delivery-bound) and are not asked to.

Inherited from Phase 1 (the bank-width sweep), unchanged:

  * the pattern PAT tiled N/8 times so the HIGH fraction is exactly 5/8.
  * L and RS are HELD FIXED, so t_hop is free to move and the trade is exposed.
  * NBANK = 3 (ideal head / BANK UNDER TEST / real receiver), validated at N=8
    against the NBANK=4 committed configuration (Phase 1 acceptance A0b).
  * .print carries only rails/tanks/I(L)/sw and TWO class representatives per
    bank; ALL N outputs of every bank are sampled by .measure.
  * the park-branch ammeter (Phase 1 A5) and the PRE-CLOSE gate-charge
    reference (Phase 1 A6).

Stages:  warm | cellchain | probe | row
"""
import json, math, os, re, subprocess, sys, time

HERE  = os.path.dirname(os.path.abspath(__file__))
XYCE  = "/usr/local/src/xyce-build/src/Xyce"
VA    = "/usr/local/share/xyce/verilog-a/psp103/psp103.va"
MODEL = "/usr/local/src/kestrel/sim/models/sg13g2_psp103_tt.lib"
SHIM  = "/usr/local/src/stat-sim/qal/sg13lv_compat.sp"
CACHE = os.environ.get("PYMS_VAE_CACHE") or \
    "/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6/scratchpad/vae_cache_upsize"
ENV = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS", PYMS_VAE_CACHE=CACHE)

# ---- inherited constants (committed banktank; NOT touched) -----------------
NBANK   = 3                     # NEW: 3 not 4 (A0b validates the reduction)
WP, WN  = 1.12, 0.74            # cell inverter widths (um) -- Phase 2 sweeps these
CLOAD   = 2.0                   # fF per cell output
CBANK8  = 35.979                # fF, committed MEASURED secant C of one 8-cell bank
RS_REF  = 10.0                  # ohm, inductor series R  -- HELD FIXED
L_REF   = 15.0                  # nH                      -- HELD FIXED
W0      = 30.0                  # um nominal switch total at N=8 (committed tg15p)
VGH     = 1.5                   # V, switch gate drive rail
EDGE    = 2.0                   # ps
LAG_PS  = 1.0                   # ps, MEASURED .measure-FIND lag of this Xyce build
TAIL    = 500.0                 # ps
T1      = 200.0                 # ps, bank 1's rail-raise closes (pre-roll)
TZ8     = 126.49311583817865    # ps, committed banktank dV=1.65 bank-2 rise zero
QGATE_PER_UM = 0.155            # fC/um, committed qal/lsweep MEASURED linear fit

PAT8 = [1, 1, 1, 0, 1, 0, 0, 1]     # 5 HIGH of 8 -- committed declared deviation


# ------------------------------------------------------------------ geometry
def sc_list(scale, nb):
    """PHASE 2: `scale` is a float (all banks) or a list of nb floats (E1, where
    the measured bank drives an UNSCALED load inside the real chain)."""
    if isinstance(scale, (list, tuple)):
        s = [float(x) for x in scale]
        if len(s) != nb:
            raise ValueError("scale list length %d != nb %d" % (len(s), nb))
        return s
    return [float(scale)] * nb


def cbank(n, scale=1.0):
    """DERIVED: bank capacitance scales with population AND with cell width --
    it IS the cells' rail-side junction/overlap parasitics, both ~ W.  Used
    ONLY to size the tank; the real secant C is MEASURED per row (B9)."""
    return CBANK8 * n / 8.0 * scale


def wtot(n, wmul=1.0, scale=1.0):
    """PRE-STATED: constant-Q requires R_on ~ 1/sqrt(C), and C ~ N*s, hence
    W ~ sqrt(N*s).  The two exponents compose."""
    return W0 * math.sqrt(n / 8.0) * wmul * math.sqrt(scale)


def widths(total_um):
    """committed tg15p triple: 1:2 n:p TG + park = total/15."""
    return dict(wn=total_um / 3.0, wp=2.0 * total_um / 3.0, park=total_um / 15.0)


def mstep_of(n, override=None):
    """PHASE 2: deliberately NOT scaled by s.  Upsizing makes the CELLS faster
    while lengthening the hop; scaling the step with the hop would coarsen the
    grid exactly where the dynamics under test sharpen.  B11 falsifies it."""
    return override if override else 0.25 * math.sqrt(n / 8.0)


def pat(n, rnd=None):
    if rnd is not None:
        return rnd
    return PAT8 * (n // 8)


def vtank0(m, dv):
    """committed: lossless linear-LC pre-charge landing the rail at dV."""
    return dv * (m + 1.0) / (2.0 * m)


# --------------------------------------------------------------------- logic
def in_hi(k, i, P):
    return (P[i] == 1) if (k % 2 == 1) else (P[i] == 0)


def out_hi(k, i, P):
    return not in_hi(k, i, P)


def in_net(k, i):
    return "in1_%d" % i if k == 1 else "o%d_%d" % (k - 1, i)


def reps(k, P):
    """one representative index per electrical class (in HIGH / in LOW)."""
    a = next((i for i in range(len(P)) if in_hi(k, i, P)), None)
    b = next((i for i in range(len(P)) if not in_hi(k, i, P)), None)
    return [x for x in (a, b) if x is not None]


# ------------------------------------------------------------------ schedule
def schedule(T, H, dv, tzr, tzq, nb):
    """committed banktank schedule verbatim."""
    c  = {k: T1 + (k - 1) * T for k in range(1, nb + 1)}
    o  = {k: c[k] + tzr[k - 1] for k in range(1, nb + 1)}
    r  = {k: c[k] + H * T for k in range(1, nb + 1)}
    ro = {k: r[k] + tzq[k - 1] for k in range(1, nb + 1)}
    bnd = {}
    for k in range(1, nb + 1):
        b = c[k] + T
        b = min(b, r[k] - EDGE)
        if k > 1:
            b = min(b, r[k - 1] - EDGE)
        bnd[k] = b
    tend = max(max(ro.values()), max(bnd.values())) + TAIL
    return dict(nbank=nb, T=T, H=H, dv=dv, c=c, o=o, r=r, ro=ro, bound=bnd,
                tend=tend, tzr=tzr, tzq=tzq)


# --------------------------------------------------------------- deck pieces
def head_lines():
    return ['.hdl "%s"' % VA, '.include "%s"' % MODEL, '.include "%s"' % SHIM,
            '.OPTIONS TIMEINT METHOD=GEAR RELTOL=1e-6 ABSTOL=1e-15 CHGTOL=1e-17']


def bank_cells(k, dv, n, P, sc=1.0, cload=CLOAD):
    """PHASE 2: cell widths are WP*sc / WN*sc.  cload is the output node's
    WIRING load and is HELD FIXED in the main series -- routing capacitance
    does not scale with transistor width.  The load that DOES scale is the next
    bank's gates, which is structural here (bank k's outputs ARE bank k+1's
    gate nets), so the co-scaling the crux asks about happens by construction."""
    L = ["VMG%d gn%d 0 0" % (k, k)]
    if k == 1:
        for i in range(n):
            L.append("VI1_%d in1_%d 0 %g" % (i, i, dv if in_hi(1, i, P) else 0.0))
    for i in range(n):
        s = in_net(k, i)
        L.append("XP%d_%d o%d_%d %s rail%d rail%d sg13_lv_pmos w=%gu l=0.13u"
                 % (k, i, k, i, s, k, k, WP * sc))
        L.append("XN%d_%d o%d_%d %s gn%d gn%d sg13_lv_nmos w=%gu l=0.13u"
                 % (k, i, k, i, s, k, k, WN * sc))
        L.append("CL%d_%d o%d_%d gn%d %gf" % (k, i, k, i, k, cload))
    return L


PARK_AMMETER = os.environ.get("WB_NO_PARK_AMMETER", "") == ""
# PHASE 2 AMENDMENT A1: return-hop gate-charge checkpoints.  Set UP_NO_RETQG=1
# to regenerate Phase 1's exact deck bytes (used to re-verify B0a after the
# amendment landed).
RETURN_QG = os.environ.get("UP_NO_RETQG", "") == ""


def tank_branch(k, m, total_um, l_nh, rs, n, sc=1.0, ct_fF=None):
    """committed banktank tank branch with the A6 TANK-REFERENCED park.
    PHASE 2: C_tank = m*cbank(n,sc) unless ct_fF overrides it (control E2)."""
    ct = ct_fF if ct_fF is not None else m * cbank(n, sc)
    w = widths(total_um)
    if not PARK_AMMETER:
        # TRANSPARENCY CONTROL: the committed wiring, park source straight on
        # tnk{k}, no ammeter.  Used once at N=8 to prove the ammeter changes
        # nothing measurable.
        return ["CT%d tnk%d 0 %gf" % (k, k, ct),
                "L%d tnk%d mid%d %gn" % (k, k, k, l_nh),
                "R%d mid%d sw%d %g" % (k, k, k, rs),
                "XSWN%d sw%d gt%d rail%d 0 sg13_lv_nmos w=%gu l=0.13u"
                % (k, k, k, k, w["wn"]),
                "XSWP%d sw%d gtp%d rail%d vhi sg13_lv_pmos w=%gu l=0.13u"
                % (k, k, k, k, w["wp"]),
                "XPK%d sw%d pk%d tnk%d tnk%d sg13_lv_nmos w=%gu l=0.13u"
                % (k, k, k, k, k, w["park"]),
                "VPKA%d pks%d tnk%d 0" % (k, k, k),
                "RPKD%d pks%d tnk%d 1e12" % (k, k, k)]
    return ["CT%d tnk%d 0 %gf" % (k, k, ct),
            "L%d tnk%d mid%d %gn" % (k, k, k, l_nh),
            "R%d mid%d sw%d %g" % (k, k, k, rs),
            "XSWN%d sw%d gt%d rail%d 0 sg13_lv_nmos w=%gu l=0.13u"
            % (k, k, k, k, w["wn"]),
            "XSWP%d sw%d gtp%d rail%d vhi sg13_lv_pmos w=%gu l=0.13u"
            % (k, k, k, k, w["wp"]),
            # A5 (widebank amendment): the committed deck's park device is a
            # SECOND conduction path between sw{k} and tnk{k} that does NOT go
            # through L, so the committed tank-closure identity
            # (integral of V(tnk)*I(L) vs the linear cap's own energy change)
            # cannot close by construction -- it misses this branch, and in the
            # committed dV=1.65 row it misses 11.87 fJ of a 47.29 fJ loss (25%).
            # An IDEAL 0 V source is inserted in the park's source lead as an
            # ammeter (electrically transparent; the bulk stays on tnk{k}, the
            # same potential), so the park path becomes MEASURED instead of
            # inferred.  Transparency is verified by a control row at N=8.
            "XPK%d sw%d pk%d pks%d tnk%d sg13_lv_nmos w=%gu l=0.13u"
            % (k, k, k, k, k, w["park"]),
            "VPKA%d pks%d tnk%d 0" % (k, k, k)]


def phase_pwl(k, wins, big):
    """committed anti-phase gate/park PWL verbatim."""
    pn = [(0.0, 0.0)]
    pp = [(0.0, VGH)]
    pk = [(0.0, VGH)]
    for (tc, to) in wins:
        pn += [(tc - EDGE, 0.0), (tc, VGH)]
        pp += [(tc - EDGE, VGH), (tc, 0.0)]
        pk += [(tc - EDGE, VGH), (tc, 0.0)]
        if to is None:
            pn += [(big, VGH)]; pp += [(big, 0.0)]; pk += [(big, 0.0)]
            break
        pn += [(to, VGH), (to + EDGE, 0.0)]
        pp += [(to, 0.0), (to + EDGE, VGH)]
        pk += [(to, 0.0), (to + EDGE, VGH)]
    f = lambda pts: " ".join("%gp %g" % (t, v) if t > 0 else "0 %g" % v
                             for t, v in pts)
    return ["VGT%d gt%d 0 PWL(%s)" % (k, k, f(pn)),
            "VGTP%d gtp%d 0 PWL(%s)" % (k, k, f(pp)),
            "VPK%d pk%d 0 PWL(%s)" % (k, k, f(pk))]


def integ(tg, expr):
    return ["CX%s x%s 0 1" % (tg, tg), "BX%s 0 x%s I={ %s }" % (tg, tg, expr),
            "RX%s x%s 0 0.01" % (tg, tg)]


def integrators(nb, rs, n):
    L, tags = [], []
    for k in range(1, nb + 1):
        for nm, ex in (("qlt%d" % k, "I(L%d)" % k),
                       ("ea%d" % k,  "V(tnk%d)*I(L%d)" % (k, k)),
                       ("eb%d" % k,  "V(rail%d)*I(L%d)" % (k, k)),
                       ("esw%d" % k, "V(sw%d)*I(L%d)" % (k, k)),
                       ("er%d" % k,  "I(L%d)*I(L%d)*%g" % (k, k, rs)),
                       ("qg%d" % k,  "I(VMG%d)" % k),
                       # NEW: per-switch-device GATE CHARGE, so the gate-charge
                       # per um is MEASURED at every width instead of inherited
                       # from a fit.  The committed record carries TWO
                       # inconsistent bases (lsweep 0.155 fC/um linear fit vs
                       # the tap-driver's 29.0 fC for the same 30 um switch);
                       # these integrators settle it in this study's own decks.
                       ("qgt%d" % k, "-I(VGT%d)" % k),
                       ("qgp%d" % k, "-I(VGTP%d)" % k),
                       ("qpk%d" % k, "-I(VPK%d)" % k),
                       # the PARK BRANCH, which the committed ledger never
                       # separated: charge and energy entering tnk{k} through
                       # the park (positive = into the tank).
                       ("qpa%d" % k, "I(VPKA%d)" % k),
                       ("epa%d" % k, "V(tnk%d)*I(VPKA%d)" % (k, k))):
            L += integ(nm, ex); tags.append(nm)
    L += integ("qi1", "-(" + "+".join("I(VI1_%d)" % i for i in range(n)) + ")")
    tags.append("qi1")
    L += integ("ei1", "-(" + "+".join("V(in1_%d)*I(VI1_%d)" % (i, i)
                                      for i in range(n)) + ")")
    tags.append("ei1")
    L += integ("egt", "-" + "-".join(
        "V(gt%d)*I(VGT%d)-V(gtp%d)*I(VGTP%d)-V(pk%d)*I(VPK%d)"
        % (k, k, k, k, k, k) for k in range(1, nb + 1)))
    tags.append("egt")
    L += integ("ehi", "-%g*I(VHI)" % VGH); tags.append("ehi")
    return L, tags


# --------------------------------------------------------------------- decks
def deck(n, m, T, H, dv, mode="free", l_nh=L_REF, rs=RS_REF, wmul=1.0,
         tzr=None, tzq=None, probe=None, nb=NBANK, mstep=None, P=None,
         scale=1.0, cload=CLOAD, ct_fF=None):
    P = P or pat(n)
    SC = sc_list(scale, nb)
    # the switch of bank k is sized for BANK k's OWN capacitance, so under the
    # E1 control (per-bank scales) each bank gets its own constant-Q width.
    tot_um = [wtot(n, wmul, SC[k - 1]) for k in range(1, nb + 1)]
    tzr = tzr or [TZ8 * math.sqrt(n / 8.0) * math.sqrt(SC[k - 1])
                  for k in range(1, nb + 1)]
    tzq = tzq or [TZ8 * math.sqrt(n / 8.0) * math.sqrt(SC[k - 1])
                  for k in range(1, nb + 1)]
    S = schedule(T, H, dv, tzr, tzq, nb)
    vt0 = dv if mode == "vfull" else vtank0(m, dv)
    big = S["tend"] * 4.0
    ms = mstep_of(n, mstep)

    L = head_lines() + ["VHI vhi 0 %g" % VGH]
    for k in range(1, nb + 1):
        L += bank_cells(k, dv, n, P, sc=SC[k - 1], cload=cload)
    for k in range(1, nb + 1):
        L += tank_branch(k, m, tot_um[k - 1], l_nh, rs, n, sc=SC[k - 1],
                         ct_fF=ct_fF)

    for k in range(1, nb + 1):
        if probe is None:
            wins = [(S["c"][k], S["o"][k]), (S["r"][k], S["ro"][k])]
        elif probe[0] == "rise":
            if k < probe[1]:
                wins = [(S["c"][k], S["o"][k])]
            elif k == probe[1]:
                wins = [(S["c"][k], None)]
            else:
                wins = []
        else:
            wins = [(S["c"][k], S["o"][k])]
            if k < probe[1]:
                wins.append((S["r"][k], S["ro"][k]))
            elif k == probe[1]:
                wins.append((S["r"][k], None))
        if not wins:
            L += ["VGT%d gt%d 0 0" % (k, k), "VGTP%d gtp%d 0 %g" % (k, k, VGH),
                  "VPK%d pk%d 0 %g" % (k, k, VGH)]
        else:
            L += phase_pwl(k, wins, big)

    tags = []
    if probe is None:
        ig, tags = integrators(nb, rs, n)
        L += ig
        tend = S["tend"]
    elif probe[0] == "rise":
        tend = S["c"][probe[1]] + 2.6 * TZ8 * math.sqrt(n / 8.0) \
               * math.sqrt(l_nh / L_REF) * math.sqrt(SC[probe[1] - 1])
    else:
        tend = S["r"][probe[1]] + 2.6 * TZ8 * math.sqrt(n / 8.0) \
               * math.sqrt(l_nh / L_REF) * math.sqrt(SC[probe[1] - 1])

    L.append(".ic " + " ".join("V(tnk%d)=%g V(rail%d)=0 V(sw%d)=%g"
                               % (k, vt0, k, k, vt0) for k in range(1, nb + 1)))
    L.append(".tran 0.1p %gp 0 %gp" % (tend, ms))

    g = lambda t: t + LAG_PS
    if probe is None:
        cks = [("Z", 0.5)]
        for k in range(1, nb + 1):
            cks += [("O%d" % k, S["o"][k]), ("B%d" % k, S["bound"][k]),
                    ("R%d" % k, S["r"][k] - EDGE), ("Q%d" % k, S["ro"][k])]
        cks += [("D", tend - 5.0)]
        # integrator checkpoints (committed selection rule)
        for tg in tags:
            kk = re.sub(r"\D", "", tg)
            want = cks if not kk else [x for x in cks
                                       if x[0] in ("Z", "D", "O" + kk, "B" + kk,
                                                   "R" + kk, "Q" + kk)]
            if not kk:
                want = cks
            for nm, tt in want:
                L.append(".measure tran %s_%s FIND V(x%s) AT=%.6fp"
                         % (tg.upper(), nm, tg, g(tt)))
        # rails / tanks / currents
        for k in range(1, nb + 1):
            for nm, tt in cks:
                L.append(".measure tran VR%d%s FIND V(rail%d) AT=%.6fp"
                         % (k, nm, k, g(tt)))
                L.append(".measure tran VT%d%s FIND V(tnk%d) AT=%.6fp"
                         % (k, nm, k, g(tt)))
            L.append(".measure tran VR%dPK MAX V(rail%d) FROM=%gp TO=%gp"
                     % (k, k, S["c"][k], tend))
            L.append(".measure tran IZ%d FIND I(L%d) AT=%.6fp"
                     % (k, k, g(S["o"][k])))
            L.append(".measure tran IZQ%d FIND I(L%d) AT=%.6fp"
                     % (k, k, g(S["ro"][k])))
            L.append(".measure tran IPK%d MAX I(L%d) FROM=%gp TO=%gp"
                     % (k, k, S["c"][k], tend))
            # A7: every NON-hopping inductor at bank 2's rise ZCS
            L.append(".measure tran ICROSS%d FIND I(L%d) AT=%.6fp"
                     % (k, k, g(S["o"][2 if nb >= 2 else 1])))
            # MEASURED gate charge of each switch device across the rise hop:
            # sampled just after the close edge, just before the open edge and
            # just after the open edge, so Q(close) and Q(open) separate.
            #
            # PHASE 2 AMENDMENT A1: the SAME four checkpoints are now taken
            # around the RETURN hop (RP/RA/RB/RC).  Phase 1 metered the RISE
            # hop only and then charged the conventional-driver ledger row that
            # single figure -- but a full QAL cycle closes and opens the switch
            # TWICE (once to deliver the rail, once to recover it), so the
            # conventional row was a ~2x LOWER bound on its own terms.  These
            # are passive .measure statements; transparency is VERIFIED by the
            # B0b control, not asserted.
            ckq = [("P", S["c"][k] - EDGE - 1.0),
                   ("A", S["c"][k] + EDGE + 1.0),
                   ("B", S["o"][k] - 1.0),
                   ("C", S["o"][k] + EDGE + 1.0)]
            if RETURN_QG:
                ckq += [("RP", S["r"][k] - EDGE - 1.0),
                        ("RA", S["r"][k] + EDGE + 1.0),
                        ("RB", S["ro"][k] - 1.0),
                        ("RC", S["ro"][k] + EDGE + 1.0)]
            for src in ("qgt", "qgp", "qpk"):
                for nm, tt in ckq:
                    L.append(".measure tran %s%d_%s FIND V(x%s%d) AT=%.6fp"
                             % (src.upper(), k, nm, src, k, g(tt)))
        # ALL N outputs of every bank at that bank's own stage boundary (A1)
        for k in range(1, nb + 1):
            for i in range(n):
                L.append(".measure tran O%d_%dB FIND V(o%d_%d) AT=%.6fp"
                         % (k, i, k, i, g(S["bound"][k])))
                if k > 1:
                    L.append(".measure tran N%d_%dB FIND V(o%d_%d) AT=%.6fp"
                             % (k, i, k - 1, i, g(S["bound"][k])))
        # A2 functional: bank 2's outputs at the instant bank 3 commits (its
        # own rise ZCS = end of ITS charge delivery), and bank 3's rail there.
        if nb >= 3:
            tx = S["o"][3]
            for i in range(n):
                L.append(".measure tran O2_%dF FIND V(o2_%d) AT=%.6fp"
                         % (i, i, g(tx)))
            L.append(".measure tran VR3F FIND V(rail3) AT=%.6fp" % g(tx))
            L.append(".measure tran VR2F FIND V(rail2) AT=%.6fp" % g(tx))
        # class representatives at end of run
        for k in range(1, nb + 1):
            for i in reps(k, P):
                L.append(".measure tran O%d_%dE FIND V(o%d_%d) AT=%.6fp"
                         % (k, i, k, i, g(tend - 5.0)))
        pr = (["V(rail%d)" % k for k in range(1, nb + 1)] +
              ["V(tnk%d)" % k for k in range(1, nb + 1)] +
              ["I(L%d)" % k for k in range(1, nb + 1)] +
              ["V(sw%d)" % k for k in range(1, nb + 1)] +
              ["V(o%d_%d)" % (k, i) for k in range(1, nb + 1) for i in reps(k, P)])
    else:
        pr = (["I(L%d)" % k for k in range(1, nb + 1)] +
              ["V(rail%d)" % k for k in range(1, nb + 1)] +
              ["V(tnk%d)" % k for k in range(1, nb + 1)])
    L.append(".print tran " + " ".join(pr))
    L.append(".end")
    return L, S


# --------------------------------------------------------------------- utils
def run(fn, lines, timeout=3600):
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
        return None, "XYCE FAIL %s (%.1fs): %s" % (fn, wall, err or r.stdout[-300:])
    return path, "ran %s in %.1fs" % (fn, wall)


def parse_mt0(path):
    d = {}
    for ln in open(path):
        mm = re.match(r"\s*(\w+)\s*=\s*(\S+)", ln)
        if mm:
            try:
                d[mm.group(1).upper()] = float(mm.group(2))
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
    """committed lsweep refined rule: first sign change of I(L) after its peak,
    linearly interpolated."""
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
            return (t0 if v1 == v0 else
                    t0 + (0.0 - v0) * (t1 - t0) / (v1 - v0)), pk
        prev = (t, r[ic])
    return None, pk


# -------------------------------------------------------------------- stages
SCALES = (1.0, 2.0, 4.0, 8.0)


def geom_set():
    """every (w) this study instantiates.  PyMS keys its .so on geometry and
    sg13lv_compat.sp DISCARDS m= (Phase 1 A3), so every distinct width is its
    own compile and the warm must cover all of them."""
    g = set()
    for s in SCALES:
        g.add(round(WP * s, 6)); g.add(round(WN * s, 6))
        for n in (8, 64):
            for x in widths(wtot(n, 1.0, s)).values():
                g.add(round(x, 6))
    # E3 iso-hop and E1 per-bank controls reuse the same widths; E2 changes
    # only C_tank.  Nothing else is instantiated.
    return sorted(g)


def stage_warm():
    ws = geom_set()
    L = head_lines() + ["V1 a 0 0.5", "V2 b 0 0.5"]
    k = 0
    for x in ws:
        L.append("XWN%d d%d a 0 0 sg13_lv_nmos w=%gu l=0.13u" % (k, k, x))
        L.append("RN%d d%d b 1k" % (k, k)); k += 1
        L.append("XWP%d e%d a b b sg13_lv_pmos w=%gu l=0.13u" % (k, k, x))
        L.append("RP%d e%d 0 1k" % (k, k)); k += 1
    L += [".tran 1p 10p", ".print tran V(a)", ".end"]
    print("warming %d geometries: %s" % (len(ws), ws), flush=True)
    p, msg = run("warm_up.cir", L, timeout=3600)
    print(msg, flush=True)
    return p is not None


# ------------------------------------------------------- THE CRUX INSTRUMENT
NSTG = 5          # cells in the chain; stage 3 is measured
STG_MEAS = 3
CC_TSTEP = 0.02   # ps max step -- the cells are fast and get faster with s
CC_EDGE = 2.0     # ps input edge (committed EDGE), two stages upstream


def cellchain_deck(scale, rail, variant, nstg=NSTG, tsw=200.0, tend=600.0):
    """FIVE inverters in series at a FIXED DC rail.  Stage 3 is measured, so
    its input edge is CELL-GENERATED and its load is a REAL CELL.

    variant A  REAL CHAIN    : all cells scale, CLOAD fixed 2 fF   (main series)
    variant B  PURE COSCALE  : all cells scale, CLOAD = 2*s fF
    variant C  FIXED LOAD    : stages 1..STG_MEAS scale, the REST stay x1
                               (drive into a load that does NOT scale)
    variant D  QAL-BIAS LOAD : like A, but the LOAD stages' rail is tied to 0 V.
                               In the real QAL chain bank k+1's rail has NOT yet
                               been raised while bank k settles, so the load the
                               measured cell actually drives is an UNPOWERED
                               gate, whose C_gg bias is different (the pMOS sits
                               in accumulation rather than inversion).  A models
                               the load as powered; D models it as QAL does.
                               Both scale with s, so the SCALING conclusion
                               should be unchanged -- which is why D is measured
                               rather than assumed.

    The input to stage 1 is an ideal PWL edge -- a BOOKING, and it is two
    stages upstream of the measurement precisely so the measured stage never
    sees it."""
    sc = []
    for j in range(1, nstg + 1):
        if variant == "C" and j > STG_MEAS:
            sc.append(1.0)
        else:
            sc.append(float(scale))
    cl = CLOAD * float(scale) if variant == "B" else CLOAD

    L = head_lines() + ["VR rail 0 %.9g" % rail, "VG gnd0 0 0"]
    if variant == "D":
        L.append("VR0 rail0 0 0")
    # a full HIGH->LOW->HIGH input so BOTH edges of the measured stage are seen
    L.append("VIN s0 0 PWL(0 %.9g %gp %.9g %gp 0 %gp 0 %gp %.9g %gp %.9g)"
             % (rail, tsw - CC_EDGE, rail, tsw, tsw + tend / 2.0 - CC_EDGE,
                tsw + tend / 2.0, rail, tend * 2.0, rail))
    for j in range(1, nstg + 1):
        rl = "rail0" if (variant == "D" and j > STG_MEAS) else "rail"
        L.append("XP%d s%d s%d %s %s sg13_lv_pmos w=%gu l=0.13u"
                 % (j, j, j - 1, rl, rl, WP * sc[j - 1]))
        L.append("XN%d s%d s%d gnd0 gnd0 sg13_lv_nmos w=%gu l=0.13u"
                 % (j, j, j - 1, WN * sc[j - 1]))
        L.append("CL%d s%d gnd0 %gf" % (j, j, cl))
    # print step 0.05 ps (DISK: 24k points/deck ~2 MB; 50 fs resolves a 10 ps
    # x8 delay to 0.5% and every reported instant is linearly interpolated
    # between samples anyway), max step 0.02 ps for accuracy.
    L.append(".tran 0.05p %gp 0 %gp" % (tend * 2.0, CC_TSTEP))
    # DISK: / is 98% full and shared with other studies, so .print carries only
    # the nodes that are USED -- s2 (the measured stage's input), s3 (its
    # output), plus s0 to confirm the stimulus and s4 to confirm the load stage
    # is alive (and, in variant D, that it is correctly UNPOWERED).  The print
    # STEP is left at 0.05 ps and the max step at 0.02 ps, so nothing about the
    # solution or its sampling accuracy changes.
    L.append(".print tran " + " ".join(
        "V(s%d)" % j for j in (0, STG_MEAS - 1, STG_MEAS, STG_MEAS + 1)
        if j <= nstg))
    L.append(".end")
    return L


CC_RAILS = (1.65, 0.9422477)


def cc_tag(rail, variant, s):
    return "cc_r%d_%s_s%g" % (round(rail * 10000), variant, s)


def stage_cc(rail, variant, s):
    """ONE crux deck, so the 24-point grid can run several at a time once the
    warm has landed every geometry (no PyMS compile then, so no cache race)."""
    tag = cc_tag(rail, variant, s)
    p, msg = run("%s.cir" % tag, cellchain_deck(s, rail, variant),
                 timeout=1800)
    print("  %s %s" % (tag, msg), flush=True)
    return p is not None


def stage_cellchain():
    """the whole grid sequentially.  Kept for reproducibility; the driver
    normally calls stage_cc per point in parallel."""
    for rail in CC_RAILS:
        for variant in ("A", "B", "C"):
            for s in SCALES:
                if not stage_cc(rail, variant, s):
                    return False
    return True


def do_probe(n, dv, T, H, m=10.0, l_nh=L_REF, nb=NBANK, wmul=1.0, tag="",
             P=None, scale=1.0, cload=CLOAD, ct_fF=None):
    """committed sequential true-ZCS probe, at the row's OWN T, H AND SCALE."""
    # PHASE 2 AMENDMENT A5: the inherited probe tag carried only (N, dv, T, H)
    # and wmul -- NOT the scale, NOT L, NOT the tank override.  Since the beat
    # T is a function of scale and L, several Phase 2 points land on the SAME
    # T and would have written the SAME p_*.cir files: (N=64 s=4, T=790) vs E1
    # (scale 4,4,1, T=790); (N=64 s=8, T=1090) vs E4; (N=64 s=1, T=440) vs E3
    # (s=4, L=3.75, T=440).  do_probe re-runs whenever the deck text differs,
    # so the later point would have OVERWRITTEN the earlier point's probe decks
    # -- harmless for the already-extracted rows but a provenance loss, and an
    # outright corruption if the two ever ran concurrently.  Scale, L and the
    # tank override now all go in the tag.
    tg = tag or "n%d_dv%g_T%g_H%d" % (n, dv * 1000, T, H)
    if wmul != 1.0:
        tg += "_w%g" % wmul
    tg += sctag(scale)
    if abs(l_nh - L_REF) > 1e-12:
        tg += "_L%g" % l_nh
    if ct_fF is not None:
        tg += "_ct%g" % ct_fF
    SC = sc_list(scale, nb)
    tzr, tzq = [], []
    for ph in ("rise", "ret"):
        lst = tzr if ph == "rise" else tzq
        for k in range(1, nb + 1):
            pad = [TZ8 * math.sqrt(n / 8.0) * math.sqrt(SC[j])
                   for j in range(nb)]
            padr = (tzr + pad)[:nb]
            padq = (tzq + pad)[:nb]
            lines, S = deck(n, m, T, H, dv, l_nh=l_nh, wmul=wmul, nb=nb,
                            tzr=padr, tzq=padq, probe=(ph, k), P=P,
                            scale=scale, cload=cload, ct_fF=ct_fF)
            fn = "p_%s_%s%d.cir" % (tg, ph, k)
            path = os.path.join(HERE, fn)
            cached = (os.path.exists(path) and os.path.exists(path + ".prn")
                      and open(path).read() == "\n".join(lines) + "\n")
            p, msg = (path, "reused %s" % fn) if cached else run(fn, lines)
            print("  probe %s%d %s" % (ph, k, msg), flush=True)
            if p is None:
                return None
            hdr, rows = read_prn(p + ".prn")
            t0 = S["c"][k] if ph == "rise" else S["r"][k]
            z, pk = zero_after_peak(hdr, rows, "I(L%d)" % k, t0)
            if z is None:
                print("  probe %s%d NO ZERO" % (ph, k), flush=True)
                return None
            lst.append(z - t0)
            print("    %s%d t_zcs = %.4f ps (Ipk %.2f uA)"
                  % (ph, k, lst[-1], pk * 1e6), flush=True)
            # DISK: probe waveforms are not needed once the zero is read
            try:
                os.remove(p + ".prn")
            except OSError:
                pass
    return dict(N=n, m=m, dv=dv, L_nH=l_nh, wmul=wmul, nb=nb, T_probe=T,
                H_probe=H, tzr=tzr, tzq=tzq, scale=scale, cload=cload,
                ct_fF=ct_fF)


def sctag(scale):
    """PHASE 2: the scale goes in the tag, so a Phase-1 filename can never be
    silently overwritten by a Phase-2 row and vice versa."""
    if isinstance(scale, (list, tuple)):
        return "_s" + "-".join("%g" % float(x) for x in scale)
    return "" if float(scale) == 1.0 else "_s%g" % float(scale)


def tag_of(n, T, H, dv, mode, wmul=1.0, nb=NBANK, extra="", scale=1.0):
    t = "n%d_T%g_H%d_dv%g_%s_nb%d" % (n, T, H, dv * 1000, mode, nb)
    if wmul != 1.0:
        t += "_w%g" % wmul
    t += sctag(scale)
    if extra:
        t += "_" + extra
    return t


def do_row(n, T, H, dv, mode, z, m=10.0, l_nh=L_REF, wmul=1.0, nb=NBANK,
           mstep=None, extra="", P=None, timeout=10800, scale=1.0,
           cload=CLOAD, ct_fF=None):
    lines, S = deck(n, m, T, H, dv, mode=mode, l_nh=l_nh, wmul=wmul, nb=nb,
                    tzr=z["tzr"], tzq=z["tzq"], mstep=mstep, P=P, scale=scale,
                    cload=cload, ct_fF=ct_fF)
    fn = "c_%s.cir" % tag_of(n, T, H, dv, mode, wmul, nb, extra, scale)
    p, msg = run(fn, lines, timeout=timeout)
    print("  row %s" % msg, flush=True)
    return (p, S, msg) if p else (None, None, msg)


SETTLE_PAD_PS = 73.5      # committed Phase 1 beat rule: T = ceil10(t_zcs + pad)


def ceil10(x):
    return 10.0 * math.ceil(x / 10.0)


def zname(n, dv, T, H, nb, scale, l_nh, extra=""):
    s = "zeros_n%d_dv%g_T%g_H%d_nb%d%s" % (n, dv * 1000, T, H, nb,
                                           sctag(scale))
    if abs(l_nh - L_REF) > 1e-12:
        s += "_L%g" % l_nh
    if extra:
        s += "_" + extra
    return s + ".json"


def beat_of(n, scale_scored, l_nh=L_REF):
    """PHASE 1'S COMMITTED BEAT RULE, verified by reverse-engineering the
    accepted series: T = ceil10(TZ8*sqrt(N/8) + 73.5) on the ANALYTIC seed, NOT
    on the measured t_zcs.  It reproduces Phase 1's T at N=16/32/64/128/256
    exactly (260/330/440/580/790); N=8's accepted 160 is Phase 1 walking the
    beat DOWN below the seed, which is a separate tight-beat exercise.

    Using the analytic seed also removes the circularity that an iterated rule
    would introduce: T does not depend on the probe, so probing AT this T is
    self-consistent by construction.  Extended to Phase 2 by the same
    sqrt(C) argument that sets the seed: C ~ N*s and t ~ sqrt(L*C)."""
    return ceil10(TZ8 * math.sqrt(n / 8.0) * math.sqrt(scale_scored)
                  * math.sqrt(l_nh / L_REF) + SETTLE_PAD_PS)


def do_point(n, dv=1.65, H=4, mode="free", scale=1.0, nb=NBANK, l_nh=L_REF,
             wmul=1.0, mstep=None, cload=CLOAD, ct_fF=None, extra="",
             T_force=None):
    """T from the committed analytic rule -> probe AT that T -> row."""
    SC = sc_list(scale, nb)
    T = T_force or beat_of(n, SC[1], l_nh)
    print("[point n=%d s=%s L=%g] T=%g (committed analytic beat rule)"
          % (n, scale, l_nh, T), flush=True)
    z = do_probe(n, dv, T, H, nb=nb, l_nh=l_nh, wmul=wmul, scale=scale,
                 cload=cload, ct_fF=ct_fF)
    if z is None:
        return None
    z["T_used"] = T
    z["T_rule"] = ("FORCED" if T_force else
                   "ceil10(TZ8*sqrt(N/8)*sqrt(s)*sqrt(L/15) + 73.5)")
    z["T_selfconsistent"] = True
    z["cload"] = cload
    z["ct_fF"] = ct_fF
    nm = zname(n, dv, T, H, nb, scale, l_nh, extra)
    open(os.path.join(HERE, nm), "w").write(json.dumps(z, indent=1))
    p, S, msg = do_row(n, T, H, dv, mode, z, nb=nb, l_nh=l_nh, wmul=wmul,
                       mstep=mstep, extra=extra, scale=scale, cload=cload,
                       ct_fF=ct_fF)
    if p is None:
        return None
    return dict(T=T, zeros=nm, deck=p,
                tag=tag_of(n, T, H, dv, mode, wmul, nb, extra, scale))


def _pscale(s):
    return [float(x) for x in s.split(",")] if "," in s else float(s)


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] == "warm":
        sys.exit(0 if stage_warm() else 1)
    if a[0] == "cellchain":
        sys.exit(0 if stage_cellchain() else 1)
    if a[0] == "cc":
        # cc RAIL VARIANT SCALE -- one crux deck
        sys.exit(0 if stage_cc(float(a[1]), a[2], float(a[3])) else 1)
    if a[0] == "point":
        # point N SCALE [L_nH] [mstep] [cload] [ct_fF] [extra] [T_force]
        n = int(a[1]); sc = _pscale(a[2])
        l_nh = float(a[3]) if len(a) > 3 and a[3] != "-" else L_REF
        ms = float(a[4]) if len(a) > 4 and a[4] != "-" else None
        cl = float(a[5]) if len(a) > 5 and a[5] != "-" else CLOAD
        ct = float(a[6]) if len(a) > 6 and a[6] != "-" else None
        ex = a[7] if len(a) > 7 and a[7] != "-" else ""
        tf = float(a[8]) if len(a) > 8 and a[8] != "-" else None
        r = do_point(n, scale=sc, l_nh=l_nh, mstep=ms, cload=cl, ct_fF=ct,
                     extra=ex, T_force=tf)
        if r is None:
            sys.exit(1)
        print("POINT OK %s" % json.dumps(r), flush=True)
    elif a[0] == "deckonly":
        # deckonly N T H dv mode zerosfile [scale] -- B0a transcription check
        n, T, H, dv, mode, zf = (int(a[1]), float(a[2]), int(a[3]),
                                 float(a[4]), a[5], a[6])
        sc = _pscale(a[7]) if len(a) > 7 else 1.0
        z = json.load(open(a[6]) if os.path.exists(a[6])
                      else os.path.join(HERE, zf))
        lines, S = deck(n, 10.0, T, H, dv, mode=mode, tzr=z["tzr"],
                        tzq=z["tzq"], scale=sc)
        sys.stdout.write("\n".join(lines) + "\n")
