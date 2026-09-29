#!/usr/bin/env python3
"""PER-BANK TANK CAPACITOR chain: each bank raises its OWN rail from its OWN local
tank through its OWN inductor, and RETURNS the charge to that same tank.

Cells, transfer switch (tg15p class), series R, .OPTIONS, dV, gate phases, the
TRUE-ZCS probe-then-cut protocol, the 1F-integrator metering discipline and the
per-gate settling convention are qal/skip4/skip.py VERBATIM, which is
qal/chain3/chain.py verbatim, which is qal/lsweep/lsw.py verbatim, which is
swsweep/sw_hop_meter.py verbatim, which is gateb's committed harness verbatim.

WHAT IS NEW HERE AND NOWHERE ELSE:
  * the charge source of bank k is C_tank(k) = m * C_bank, a LOCAL linear tank,
    NOT bank k-1.  Nothing but bank k touches tank k.
  * the charge RETURNS to that same tank through the same L at the end of the
    bank's hold window (local recycle; no forward propagation of charge).
  * therefore each bank carries ONE transfer terminal (chain3/skip4 middle banks
    carried TWO, which cost them 1.33-1.58x on the hop time), and the chain3
    finding-(d) SOURCE-side cut is not required: the tank island touches exactly
    one rail, so there is no idle downstream inductor to divert into.
  * the PARK device of the tg15p triple is referenced to THIS BANK'S TANK, not
    to ground (AMENDMENT A6, forced by measurement): it closes the L+R loop
    across the tank whenever the transfer gate is open, clamping the inductor
    voltage to ~0.  Ground-referenced parking (the committed choice, right for a
    deck whose source cap is already drained) would put a charged tank across
    L -> R -> park -> gnd and ring it down; leaving the node unparked (my first
    attempt) let the tank/L/sw island ring at 7 GHz, +/-700 uA, undamped.

DATA: bank 1's 8 inputs are ideal DC sources (it is the chain head, and only it).
For k>1 the gate input net of bank k cell i IS o{k-1}_{i} -- the predecessor's
output node.  No flop, latch, buffer, keeper or level shifter anywhere.

Pre-registration: PRE_REGISTERED.json (sha256 d343dfb0..., 21647 B, 08:45:54,
the ONLY file in this directory at that instant).

Stages: warm | probe <m> <dv> | row <m> <T> <H> <dv> <mode> <zeros.json>
"""
import json, math, os, re, subprocess, sys, time

HERE  = os.path.dirname(os.path.abspath(__file__))
XYCE  = "/usr/local/src/xyce-build/src/Xyce"
VA    = "/usr/local/share/xyce/verilog-a/psp103/psp103.va"
MODEL = "/usr/local/src/kestrel/sim/models/sg13g2_psp103_tt.lib"
SHIM  = "/usr/local/src/stat-sim/qal/sg13lv_compat.sp"
CACHE = os.environ.get("PYMS_VAE_CACHE") or \
    "/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6/scratchpad/vae_cache_banktank"
ENV = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS", PYMS_VAE_CACHE=CACHE)

# ---- inherited constants (committed; NOT touched) --------------------------
NBANK   = 4
MGATE   = 8
WP, WN  = 1.12, 0.74            # cell inverter widths (um)
CLOAD   = 2.0                   # fF per cell output
CBANK   = 35.979                # fF, committed MEASURED secant C of one 8-cell bank
RS_REF  = 10.0                  # ohm, inductor series R
L_REF   = 15.0                  # nH, committed skip4/chain3 primary point
VGH     = 1.5                   # V, switch gate drive from the +1.5 V rail
EDGE    = 2.0                   # ps, committed transfer-gate edge
LAG_PS  = 1.0                   # ps, MEASURED .measure-FIND lag of this Xyce build
TAIL    = 500.0                 # ps, post-last-event eventual-settle tail
T1      = 200.0                 # ps, bank 1's rail-raise closes (pre-roll)
TZ_ANCH = 65.49500982344826     # ps, committed L=15/W30/dV1.2 single-hop zero

# DECLARED DEVIATION (pre-registered): a non-alternating bit pattern, so the
# rail loading differs by depth and there is a real 8-bit value to check.
PAT = [1, 1, 1, 0, 1, 0, 0, 1]      # bank 1's inputs: 5 HIGH, 3 LOW


def widths(total_um):
    """1:2 n:p TG + park = total/15.  total=30 reproduces the committed tg15p
    at the skip4/chain3 primary width (wn=10u, wp=20u, park=2u)."""
    return dict(wn=total_um / 3.0, wp=2.0 * total_um / 3.0, park=total_um / 15.0)


def in_hi(k, i):
    """Bank k cell i sees a logic HIGH input.  Bank 1 sees PAT; every bank is an
    inverter, so bank k sees PAT for odd k and its complement for even k."""
    return (PAT[i] == 1) if (k % 2 == 1) else (PAT[i] == 0)


def out_hi(k, i):
    """The EXPECTED output bit of bank k cell i (an inverter)."""
    return not in_hi(k, i)


def in_net(k, i):
    """THE POINT OF THE WHOLE DECK.  k==1 -> ideal source (chain head);
    k>1 -> literally o{k-1}_{i}, the predecessor's output net."""
    return "in1_%d" % i if k == 1 else "o%d_%d" % (k - 1, i)


def vtank0(m, dv):
    """DERIVED: the lossless linear-LC tank pre-charge that lands the rail at dV
    for a tank of m banks.  A half cycle between C_t and C_b moves
    dQ = 2*V_t0*C_t*C_b/(C_t+C_b), so dV_rail = 2*V_t0*m/(m+1).
    m = 1 gives V_t0 = dV exactly, i.e. the COMMITTED lsweep/swsweep hop deck
    (CA = 35.979 fF pre-charged to dV) -- a built-in control."""
    return dv * (m + 1.0) / (2.0 * m)


# ------------------------------------------------------------------ schedule
def schedule(T, H, dv, tzr=None, tzq=None, nb=NBANK):
    """Every time in the deck derived from the beat period T and hold depth H.

      c_k   rail-raise switch CLOSES  = T1 + (k-1)*T   (the RAIL-START instant)
      o_k   rail-raise switch OPENS   = c_k + tzr_k    (MEASURED ZCS)
      r_k   return switch CLOSES      = c_k + H*T
      ro_k  return switch OPENS       = r_k + tzq_k    (MEASURED ZCS)
      bnd_k bank k's stage boundary   = min(c_k + T, r_{k-1} - EDGE, r_k - EDGE)
            -- the inherited 'one beat to become valid' rule, made STRICT by the
            last-undisturbed-instant clause (it can only move a checkpoint
            EARLIER, never later).
    """
    tzr = tzr or [TZ_ANCH] * nb
    tzq = tzq or [TZ_ANCH] * nb
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
                tend=tend, tzr=tzr, tzq=tzq, pstep=0.1, mstep=0.25)


# --------------------------------------------------------------- deck pieces
def head_lines():
    return ['.hdl "%s"' % VA, '.include "%s"' % MODEL, '.include "%s"' % SHIM,
            '.OPTIONS TIMEINT METHOD=GEAR RELTOL=1e-6 ABSTOL=1e-15 CHGTOL=1e-17']


def bank_cells(k, dv):
    """One level of logic.  Committed cell VERBATIM: pMOS w=1.12u with supply AND
    bulk on the bank rail, nMOS w=0.74u, CL 2 fF.  NOTHING between banks."""
    L = ["VMG%d gn%d 0 0" % (k, k)]
    if k == 1:
        for i in range(MGATE):
            L.append("VI1_%d in1_%d 0 %g" % (i, i, dv if in_hi(1, i) else 0.0))
    for i in range(MGATE):
        s = in_net(k, i)
        L.append("XP%d_%d o%d_%d %s rail%d rail%d sg13_lv_pmos w=%gu l=0.13u"
                 % (k, i, k, i, s, k, k, WP))
        L.append("XN%d_%d o%d_%d %s gn%d gn%d sg13_lv_nmos w=%gu l=0.13u"
                 % (k, i, k, i, s, k, k, WN))
        L.append("CL%d_%d o%d_%d gn%d %gf" % (k, i, k, i, k, CLOAD))
    return L


def tank_branch(k, m, total_um, l_nh, rs):
    """Bank k's OWN tank -> OWN inductor -> committed tg15p triple -> its rail.
    The park is tank-referenced (A6) and anti-phase to the transfer gate."""
    w = widths(total_um)
    return ["CT%d tnk%d 0 %gf" % (k, k, m * CBANK),
            "L%d tnk%d mid%d %gn" % (k, k, k, l_nh),
            "R%d mid%d sw%d %g" % (k, k, k, rs),
            "XSWN%d sw%d gt%d rail%d 0 sg13_lv_nmos w=%gu l=0.13u"
            % (k, k, k, k, w["wn"]),
            "XSWP%d sw%d gtp%d rail%d vhi sg13_lv_pmos w=%gu l=0.13u"
            % (k, k, k, k, w["wp"]),
            # AMENDMENT A6: the park is referenced to THIS BANK'S TANK, not to
            # ground.  It closes the L+R loop across the tank whenever the
            # transfer gate is open, clamping the inductor voltage to ~0 and
            # pinning sw{k} at V(tnk{k}).  A GROUND-referenced park (the
            # committed choice, correct for a deck whose source cap is already
            # drained) would put tank -> L -> R -> park -> gnd across a charged
            # tank and ring it down.  Measurement that forced this: see A6.
            "XPK%d sw%d pk%d tnk%d tnk%d sg13_lv_nmos w=%gu l=0.13u"
            % (k, k, k, k, k, w["park"])]


def phase_pwl(k, wins, big):
    """Switch k conducts over each (close, open) window in `wins`; an open of None
    means 'closes and never opens' (the ZCS probe).  gtp is the exact complement.
    The PARK (A6: referenced to tnk{k}) is the committed anti-phase: ON except
    while the transfer gate conducts, so it never fights the transfer and always
    clamps the inductor the instant the transfer gate lets go."""
    pn = [(0.0, 0.0)]
    pp = [(0.0, VGH)]
    pk = [(0.0, VGH)]
    for (tc, to) in wins:
        pn += [(tc - EDGE, 0.0), (tc, VGH)]
        pp += [(tc - EDGE, VGH), (tc, 0.0)]
        pk += [(tc - EDGE, VGH), (tc, 0.0)]
        if to is None:
            pn += [(big, VGH)]
            pp += [(big, 0.0)]
            pk += [(big, 0.0)]
            break
        pn += [(to, VGH), (to + EDGE, 0.0)]
        pp += [(to, 0.0), (to + EDGE, VGH)]
        pk += [(to, 0.0), (to + EDGE, VGH)]
    f = lambda pts: " ".join("%gp %g" % (t, v) if t > 0 else "0 %g" % v for t, v in pts)
    return ["VGT%d gt%d 0 PWL(%s)" % (k, k, f(pn)),
            "VGTP%d gtp%d 0 PWL(%s)" % (k, k, f(pp)),
            "VPK%d pk%d 0 PWL(%s)" % (k, k, f(pk))]


def integ(tg, expr):
    return ["CX%s x%s 0 1" % (tg, tg), "BX%s 0 x%s I={ %s }" % (tg, tg, expr),
            "RX%s x%s 0 0.01" % (tg, tg)]


def integrators(nb, rs, topup):
    L, tags = [], []
    for k in range(1, nb + 1):
        for nm, ex in (("qlt%d" % k, "I(L%d)" % k),
                       ("ea%d" % k,  "V(tnk%d)*I(L%d)" % (k, k)),
                       ("eb%d" % k,  "V(rail%d)*I(L%d)" % (k, k)),
                       ("esw%d" % k, "V(sw%d)*I(L%d)" % (k, k)),
                       ("er%d" % k,  "I(L%d)*I(L%d)*%g" % (k, k, rs)),
                       ("qg%d" % k,  "I(VMG%d)" % k)):
            L += integ(nm, ex); tags.append(nm)
    L += integ("qi1", "-(" + "+".join("I(VI1_%d)" % i for i in range(MGATE)) + ")")
    tags.append("qi1")
    L += integ("ei1", "-(" + "+".join("V(in1_%d)*I(VI1_%d)" % (i, i)
                                      for i in range(MGATE)) + ")")
    tags.append("ei1")
    L += integ("egt", "-" + "-".join(
        "V(gt%d)*I(VGT%d)-V(gtp%d)*I(VGTP%d)-V(pk%d)*I(VPK%d)" % (k, k, k, k, k, k)
        for k in range(1, nb + 1)))
    tags.append("egt")
    L += integ("ehi", "-%g*I(VHI)" % VGH); tags.append("ehi")
    if topup:
        L += integ("etu", "-V(vrch)*I(VTK)"); tags.append("etu")
        L += integ("qtu", "-I(VTK)"); tags.append("qtu")
    return L, tags


def topup_devices(nb, total_um, S, vt0):
    """COSTED RECHARGE (variant R2): a real tg15p-class device from an ideal rail
    at the tank's own operating voltage into each tank, conducting for one window
    after that tank's return completes.  The supply current is metered by its own
    1F integrator, so the switch loss is INSIDE the measured number.  The
    generation of the vtk rail itself is NOT costed and is labelled a BOUND."""
    w = widths(total_um)
    L = ["VTK vrch 0 %g" % vt0]
    for k in range(1, nb + 1):
        a = S["ro"][k] + EDGE
        b = a + 60.0
        L += ["XTUN%d tnk%d tun%d vrch 0 sg13_lv_nmos w=%gu l=0.13u"
              % (k, k, k, w["wn"]),
              "XTUP%d tnk%d tup%d vrch vhi sg13_lv_pmos w=%gu l=0.13u"
              % (k, k, k, w["wp"]),
              "VTUN%d tun%d 0 PWL(0 0 %gp 0 %gp %g %gp %g %gp 0)"
              % (k, k, a, a + EDGE, VGH, b, VGH, b + EDGE),
              "VTUP%d tup%d 0 PWL(0 %g %gp %g %gp 0 %gp 0 %gp %g)"
              % (k, k, VGH, a, VGH, a + EDGE, b, b + EDGE, VGH)]
    return L


# --------------------------------------------------------------------- decks
def deck(m, T, H, dv, mode="free", l_nh=L_REF, total_um=30.0, rs=RS_REF,
         tzr=None, tzq=None, probe=None, nb=NBANK):
    """probe = ('rise', k) -> switches 1..k-1 cut at their measured zeros, switch k
    closes at its beat and NEVER opens (the true-ZCS probe), later ones idle.
    probe = ('ret', k)  -> all rises cut at their zeros, returns 1..k-1 cut at
    theirs, return k closes and never opens.  probe=None -> the measured deck."""
    S = schedule(T, H, dv, tzr, tzq, nb)
    # CONTROL 'vfull': hold the tank pre-charge at the full dV instead of the
    # pre-registered lossless-linear value dV(m+1)/2m, so that the m sweep's
    # confound (tank SIZE and tank PRE-CHARGE move together by construction) can
    # be separated by measurement rather than argued about.
    vt0 = dv if mode == "vfull" else vtank0(m, dv)
    big = S["tend"] * 4.0
    L = head_lines() + ["VHI vhi 0 %g" % VGH]
    for k in range(1, nb + 1):
        L += bank_cells(k, dv)
    for k in range(1, nb + 1):
        L += tank_branch(k, m, total_um, l_nh, rs)

    # ------------------------------------------------ switch conduction windows
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
        else:                                     # 'ret'
            wins = [(S["c"][k], S["o"][k])]
            if k < probe[1]:
                wins.append((S["r"][k], S["ro"][k]))
            elif k == probe[1]:
                wins.append((S["r"][k], None))
        if not wins:
            L += ["VGT%d gt%d 0 0" % (k, k), "VGTP%d gtp%d 0 %g" % (k, k, VGH),
                  "VPK%d pk%d 0 %g" % (k, k, VGH)]      # idle: park HELD ON
        else:
            L += phase_pwl(k, wins, big)

    topup = (mode == "topup")
    if topup:
        L += topup_devices(nb, total_um, S, vt0)

    tags = []
    if probe is None:
        ig, tags = integrators(nb, rs, topup)
        L += ig
        tend = S["tend"]
        if topup:
            tend = max(tend, max(S["ro"].values()) + EDGE + 60.0 + TAIL)
    elif probe[0] == "rise":
        tend = S["c"][probe[1]] + 2.6 * TZ_ANCH * math.sqrt(l_nh / L_REF)
    else:
        tend = S["r"][probe[1]] + 2.6 * TZ_ANCH * math.sqrt(l_nh / L_REF)

    L.append(".ic " + " ".join("V(tnk%d)=%g V(rail%d)=0 V(sw%d)=%g"
                               % (k, vt0, k, k, vt0) for k in range(1, nb + 1)))
    L.append(".tran %gp %gp 0 %gp" % (S["pstep"], tend, S["mstep"]))

    g = lambda t: t + LAG_PS
    if probe is None:
        cks = [("Z", 0.5)]
        for k in range(1, nb + 1):
            cks += [("O%d" % k, S["o"][k]), ("B%d" % k, S["bound"][k]),
                    ("R%d" % k, S["r"][k] - EDGE), ("Q%d" % k, S["ro"][k])]
        cks += [("D", tend - 5.0)]
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
            for i in range(MGATE):
                L.append(".measure tran O%d_%dB FIND V(o%d_%d) AT=%.6fp"
                         % (k, i, k, i, g(S["bound"][k])))
                L.append(".measure tran O%d_%dE FIND V(o%d_%d) AT=%.6fp"
                         % (k, i, k, i, g(tend - 5.0)))
                if k > 1:
                    L.append(".measure tran N%d_%dB FIND V(o%d_%d) AT=%.6fp"
                             % (k, i, k - 1, i, g(S["bound"][k])))
        pr = (["V(rail%d)" % k for k in range(1, nb + 1)] +
              ["V(tnk%d)" % k for k in range(1, nb + 1)] +
              ["I(L%d)" % k for k in range(1, nb + 1)] +
              ["V(sw%d)" % k for k in range(1, nb + 1)] +
              ["V(o%d_%d)" % (k, i) for k in range(1, nb + 1) for i in range(MGATE)])
    else:
        pr = (["I(L%d)" % k for k in range(1, nb + 1)] +
              ["V(rail%d)" % k for k in range(1, nb + 1)] +
              ["V(tnk%d)" % k for k in range(1, nb + 1)])
    L.append(".print tran " + " ".join(pr))
    L.append(".end")
    return L, S


# --------------------------------------------------------------------- utils
def run(fn, lines, timeout=1200):
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
    """The TRUE ZCS instant: first sign change of I(L) after its peak, linearly
    interpolated (the lsweep refined rule)."""
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
            return (t0 if v1 == v0 else t0 + (0.0 - v0) * (t1 - t0) / (v1 - v0)), pk
        prev = (t, r[ic])
    return None, pk


# -------------------------------------------------------------------- stages
def stage_warm():
    w = widths(30.0)
    need_n = sorted(set([WN, w["wn"], w["park"]]))
    need_p = sorted(set([WP, w["wp"]]))
    L = head_lines() + ["V1 a 0 0.5", "V2 b 0 0.5"]
    k = 0
    for x in need_n:
        L.append("XWN%d d%d a 0 0 sg13_lv_nmos w=%gu l=0.13u" % (k, k, x))
        L.append("RN%d d%d b 1k" % (k, k)); k += 1
    for x in need_p:
        L.append("XWP%d e%d a b b sg13_lv_pmos w=%gu l=0.13u" % (k, k, x))
        L.append("RP%d e%d 0 1k" % (k, k)); k += 1
    L += [".tran 1p 10p", ".print tran V(a)", ".end"]
    p, msg = run("warm.cir", L, timeout=900)
    print(msg)
    return p is not None


TPROBE, HPROBE = 120.0, 4


def do_probe(m, dv, l_nh=L_REF, nb=NBANK, T=None, H=None):
    """Sequential true-ZCS probe: first every bank's RAIL-RAISE zero (1..nb, each
    with its predecessors cut at their own measured zeros), then every bank's
    RETURN zero the same way.

    AMENDMENT A7: T and H default to the reference schedule (TPROBE/HPROBE) but
    may be set to the row's OWN beat period and hold depth, because measurement
    refuted A1's assumption that the zero is beat-period independent: at T = 200
    with T = 120 zeros the residual |I(L)| at the commanded open was 8.8 / 15.3 /
    27.4 uA on banks 2/3/4 (bank 1, whose inputs are ideal sources and therefore
    schedule-independent, stayed at 0.008 uA -- which identifies the mechanism as
    the beat-period dependence of a bank's INPUT levels during its own ramp, and
    hence of its gate loading)."""
    tag = "m%g_dv%g" % (m, dv * 1000)
    if T is not None:
        tag += "_T%g_H%d" % (T, H)
    tzr, tzq = [], []
    for ph in ("rise", "ret"):
        lst = tzr if ph == "rise" else tzq
        for k in range(1, nb + 1):
            padr = tzr + [TZ_ANCH] * (nb - len(tzr))
            padq = tzq + [TZ_ANCH] * (nb - len(tzq))
            lines, S = deck(m, T or TPROBE, H or HPROBE, dv, l_nh=l_nh,
                            tzr=padr, tzq=padq, probe=(ph, k))
            fn = "p_%s_%s%d.cir" % (tag, ph, k)
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
                print("  probe %s%d NO ZERO" % (ph, k)); return None
            lst.append(z - t0)
            print("    %s%d t_zcs = %.4f ps (Ipk %.2f uA)" % (ph, k, lst[-1],
                                                              pk * 1e6), flush=True)
    return dict(m=m, dv=dv, L_nH=l_nh, tzr=tzr, tzq=tzq,
                T_probe=(T or TPROBE), H_probe=(H or HPROBE))


def do_probe_oddeven(m, dv, l_nh=L_REF, nb=NBANK):
    """REDUCED probe (4 runs instead of 8): measure bank 1's and bank 2's rise and
    return zeros with the same sequential protocol, then apply bank 1's to the ODD
    banks and bank 2's to the EVEN banks.

    Justification: banks differ electrically only in their pull-up/pull-down mix
    (the declared non-alternating pattern makes odd banks 5 pull-down / 3 pull-up
    and even banks 3/5) and in bank 1's ideal input sources.  The shortcut is
    VALIDATED at the primary point (m = 10, dV = 1.2), where the FULL 8-run
    sequential protocol is run and banks 3, 4 are compared against banks 1, 2 --
    and every measured row still carries the A6 |I(L)| <= 1 uA gate at each
    commanded open, which fails the row if a reused zero did not transfer."""
    tag = "m%g_dv%g" % (m, dv * 1000)
    tzr, tzq = [], []
    for ph in ("rise", "ret"):
        lst = tzr if ph == "rise" else tzq
        for k in (1, 2):
            padr = (tzr + [TZ_ANCH] * nb)[:nb]
            padq = (tzq + [TZ_ANCH] * nb)[:nb]
            lines, S = deck(m, TPROBE, HPROBE, dv, l_nh=l_nh,
                            tzr=padr, tzq=padq, probe=(ph, k))
            fn = "p_%s_%s%d.cir" % (tag, ph, k)
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
                print("  probe %s%d NO ZERO" % (ph, k)); return None
            lst.append(z - t0)
            print("    %s%d t_zcs = %.4f ps (Ipk %.2f uA)"
                  % (ph, k, lst[-1], pk * 1e6), flush=True)
        # odd banks take bank 1's zero, even banks bank 2's
        lst[:] = [lst[0] if (k % 2 == 1) else lst[1] for k in range(1, nb + 1)]
    return dict(m=m, dv=dv, L_nH=l_nh, tzr=tzr, tzq=tzq, protocol="oddeven4")


def tag_of(m, T, H, dv, mode):
    return "m%g_T%g_H%d_dv%g_%s" % (m, T, H, dv * 1000, mode)


def do_row(m, T, H, dv, mode, z, l_nh=L_REF):
    lines, S = deck(m, T, H, dv, mode=mode, l_nh=l_nh,
                    tzr=z["tzr"], tzq=z["tzq"])
    fn = "c_%s.cir" % tag_of(m, T, H, dv, mode)
    p, msg = run(fn, lines)
    print("  row %s" % msg, flush=True)
    return (p, S) if p else (None, None)


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] == "warm":
        sys.exit(0 if stage_warm() else 1)
    if a[0] in ("probe", "probe4", "probeT"):
        m, dv = float(a[1]), float(a[2])
        if a[0] == "probeT":
            T, H = float(a[3]), int(a[4])
            z = do_probe(m, dv, T=T, H=H)
            nm = "zeros_m%g_dv%g_T%g_H%d.json" % (m, dv * 1000, T, H)
        else:
            z = do_probe(m, dv) if a[0] == "probe" else do_probe_oddeven(m, dv)
            nm = "zeros_m%g_dv%g.json" % (m, dv * 1000)
        if z is None:
            sys.exit(1)
        open(os.path.join(HERE, nm), "w").write(json.dumps(z, indent=1))
        print(json.dumps(z))
    elif a[0] == "row":
        m, T, H, dv, mode = float(a[1]), float(a[2]), int(a[3]), float(a[4]), a[5]
        z = json.load(open(os.path.join(HERE, a[6])))
        p, S = do_row(m, T, H, dv, mode, z)
        sys.exit(0 if p else 1)
