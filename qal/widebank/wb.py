#!/usr/bin/env python3
"""WIDEBANK -- the BANK-WIDTH SWEEP.  Phase 1 of the QAL amortisation question.

Architecture, cell, switch triple, park referencing, gate phases, true-ZCS
probe-then-cut protocol, 1F-integrator metering and .OPTIONS are
qal/banktank/bt.py VERBATIM (sha256 5b3582be..., recorded in
DISK_STATE_BEFORE.txt).  What is NEW here and nowhere else:

  * the bank POPULATION N is the swept axis: N in {8,16,32,64,128,256} identical
    inverters per bank, pattern PAT tiled N/8 times so the HIGH fraction is
    exactly 5/8 at every N.
  * C_bank(N) = CBANK8 * N/8 and C_tank(N) = m * C_bank(N).  L and RS are HELD
    FIXED, so t_hop grows as sqrt(N) by construction -- that is the trade under
    test, not an oversight.
  * the switch nominal total width grows as W0 * sqrt(N/8), from the pre-stated
    constant-Q requirement (PRE_REGISTERED.json : SCALING LAWS).
  * NBANK = 3 (ideal head / BANK UNDER TEST / real receiver), validated at N=8
    against the NBANK=4 committed configuration (acceptance A0b).
  * .print carries only rails/tanks/I(L)/sw and TWO class representatives per
    bank; ALL N outputs of every bank are sampled by .measure.  This is a DISK
    decision (8.0 G free), declared in the pre-registration.
  * max timestep scaled as 0.25*sqrt(N/8) ps, falsified at N=64 by A8.

Stages:  warm | probe <N> <dv> [T H] | row <N> <T> <H> <dv> <mode> <zeros.json>
         [--nb K] [--wmul X] [--mstep S] [--tag S]
"""
import json, math, os, re, subprocess, sys, time

HERE  = os.path.dirname(os.path.abspath(__file__))
XYCE  = "/usr/local/src/xyce-build/src/Xyce"
VA    = "/usr/local/share/xyce/verilog-a/psp103/psp103.va"
MODEL = "/usr/local/src/kestrel/sim/models/sg13g2_psp103_tt.lib"
SHIM  = "/usr/local/src/stat-sim/qal/sg13lv_compat.sp"
CACHE = os.environ.get("PYMS_VAE_CACHE") or \
    "/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6/scratchpad/vae_cache_widebank"
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
def cbank(n):
    """DERIVED: bank capacitance scales with population.  A9 checks it."""
    return CBANK8 * n / 8.0


def wtot(n, wmul=1.0):
    """PRE-STATED: constant-Q requires R_on ~ 1/sqrt(N), hence W ~ sqrt(N)."""
    return W0 * math.sqrt(n / 8.0) * wmul


def widths(total_um):
    """committed tg15p triple: 1:2 n:p TG + park = total/15."""
    return dict(wn=total_um / 3.0, wp=2.0 * total_um / 3.0, park=total_um / 15.0)


def mstep_of(n, override=None):
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


def bank_cells(k, dv, n, P):
    L = ["VMG%d gn%d 0 0" % (k, k)]
    if k == 1:
        for i in range(n):
            L.append("VI1_%d in1_%d 0 %g" % (i, i, dv if in_hi(1, i, P) else 0.0))
    for i in range(n):
        s = in_net(k, i)
        L.append("XP%d_%d o%d_%d %s rail%d rail%d sg13_lv_pmos w=%gu l=0.13u"
                 % (k, i, k, i, s, k, k, WP))
        L.append("XN%d_%d o%d_%d %s gn%d gn%d sg13_lv_nmos w=%gu l=0.13u"
                 % (k, i, k, i, s, k, k, WN))
        L.append("CL%d_%d o%d_%d gn%d %gf" % (k, i, k, i, k, CLOAD))
    return L


PARK_AMMETER = os.environ.get("WB_NO_PARK_AMMETER", "") == ""


def tank_branch(k, m, total_um, l_nh, rs, n):
    """committed banktank tank branch with the A6 TANK-REFERENCED park."""
    w = widths(total_um)
    if not PARK_AMMETER:
        # TRANSPARENCY CONTROL: the committed wiring, park source straight on
        # tnk{k}, no ammeter.  Used once at N=8 to prove the ammeter changes
        # nothing measurable.
        return ["CT%d tnk%d 0 %gf" % (k, k, m * cbank(n)),
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
    return ["CT%d tnk%d 0 %gf" % (k, k, m * cbank(n)),
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
         tzr=None, tzq=None, probe=None, nb=NBANK, mstep=None, P=None):
    P = P or pat(n)
    total_um = wtot(n, wmul)
    tzr = tzr or [TZ8 * math.sqrt(n / 8.0)] * nb
    tzq = tzq or [TZ8 * math.sqrt(n / 8.0)] * nb
    S = schedule(T, H, dv, tzr, tzq, nb)
    vt0 = dv if mode == "vfull" else vtank0(m, dv)
    big = S["tend"] * 4.0
    ms = mstep_of(n, mstep)

    L = head_lines() + ["VHI vhi 0 %g" % VGH]
    for k in range(1, nb + 1):
        L += bank_cells(k, dv, n, P)
    for k in range(1, nb + 1):
        L += tank_branch(k, m, total_um, l_nh, rs, n)

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
               * math.sqrt(l_nh / L_REF)
    else:
        tend = S["r"][probe[1]] + 2.6 * TZ8 * math.sqrt(n / 8.0) \
               * math.sqrt(l_nh / L_REF)

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
            for src in ("qgt", "qgp", "qpk"):
                for nm, tt in (("P", S["c"][k] - EDGE - 1.0),
                               ("A", S["c"][k] + EDGE + 1.0),
                               ("B", S["o"][k] - 1.0),
                               ("C", S["o"][k] + EDGE + 1.0)):
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
def stage_warm():
    ws = sorted(set([WN, WP] + [x for n in (8, 16, 32, 64, 128, 256)
                                for x in widths(wtot(n)).values()]
                    + [x for n in (32, 256) for w in (0.5, 2.0)
                       for x in widths(wtot(n, w)).values()]))
    L = head_lines() + ["V1 a 0 0.5", "V2 b 0 0.5"]
    k = 0
    for x in ws:
        L.append("XWN%d d%d a 0 0 sg13_lv_nmos w=%gu l=0.13u" % (k, k, x))
        L.append("RN%d d%d b 1k" % (k, k)); k += 1
        L.append("XWP%d e%d a b b sg13_lv_pmos w=%gu l=0.13u" % (k, k, x))
        L.append("RP%d e%d 0 1k" % (k, k)); k += 1
    L += [".tran 1p 10p", ".print tran V(a)", ".end"]
    p, msg = run("warm_wb.cir", L, timeout=1800)
    print(msg, flush=True)
    return p is not None


def do_probe(n, dv, T, H, m=10.0, l_nh=L_REF, nb=NBANK, wmul=1.0, tag="",
             P=None):
    """committed sequential true-ZCS probe, at the row's OWN T and H (A7)."""
    tg = tag or "n%d_dv%g_T%g_H%d" % (n, dv * 1000, T, H)
    if wmul != 1.0:
        tg += "_w%g" % wmul
    tzr, tzq = [], []
    for ph in ("rise", "ret"):
        lst = tzr if ph == "rise" else tzq
        for k in range(1, nb + 1):
            padr = (tzr + [TZ8 * math.sqrt(n / 8.0)] * nb)[:nb]
            padq = (tzq + [TZ8 * math.sqrt(n / 8.0)] * nb)[:nb]
            lines, S = deck(n, m, T, H, dv, l_nh=l_nh, wmul=wmul, nb=nb,
                            tzr=padr, tzq=padq, probe=(ph, k), P=P)
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
                H_probe=H, tzr=tzr, tzq=tzq)


def tag_of(n, T, H, dv, mode, wmul=1.0, nb=NBANK, extra=""):
    t = "n%d_T%g_H%d_dv%g_%s_nb%d" % (n, T, H, dv * 1000, mode, nb)
    if wmul != 1.0:
        t += "_w%g" % wmul
    if extra:
        t += "_" + extra
    return t


def do_row(n, T, H, dv, mode, z, m=10.0, l_nh=L_REF, wmul=1.0, nb=NBANK,
           mstep=None, extra="", P=None, timeout=5400):
    lines, S = deck(n, m, T, H, dv, mode=mode, l_nh=l_nh, wmul=wmul, nb=nb,
                    tzr=z["tzr"], tzq=z["tzq"], mstep=mstep, P=P)
    fn = "c_%s.cir" % tag_of(n, T, H, dv, mode, wmul, nb, extra)
    p, msg = run(fn, lines, timeout=timeout)
    print("  row %s" % msg, flush=True)
    return (p, S, msg) if p else (None, None, msg)


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] == "warm":
        sys.exit(0 if stage_warm() else 1)
    if a[0] == "probe":
        n, dv, T, H = int(a[1]), float(a[2]), float(a[3]), int(a[4])
        nb = int(a[5]) if len(a) > 5 else NBANK
        wmul = float(a[6]) if len(a) > 6 else 1.0
        z = do_probe(n, dv, T, H, nb=nb, wmul=wmul)
        if z is None:
            sys.exit(1)
        nm = "zeros_n%d_dv%g_T%g_H%d_nb%d%s.json" % (
            n, dv * 1000, T, H, nb, ("_w%g" % wmul) if wmul != 1.0 else "")
        open(os.path.join(HERE, nm), "w").write(json.dumps(z, indent=1))
        print(nm, flush=True)
    elif a[0] == "row":
        n, T, H, dv, mode, zf = (int(a[1]), float(a[2]), int(a[3]),
                                 float(a[4]), a[5], a[6])
        nb = int(a[7]) if len(a) > 7 else NBANK
        wmul = float(a[8]) if len(a) > 8 else 1.0
        ms = float(a[9]) if len(a) > 9 and a[9] != "-" else None
        extra = a[10] if len(a) > 10 else ""
        z = json.load(open(os.path.join(HERE, zf)))
        p, S, msg = do_row(n, T, H, dv, mode, z, nb=nb, wmul=wmul,
                           mstep=ms, extra=extra)
        sys.exit(0 if p else 1)
