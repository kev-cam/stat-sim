#!/usr/bin/env python3
"""STAGE-SKIPPING (INTERLEAVED) QAL POWER SCHEDULE vs the ADJACENT schedule.

Cells, transfer switch (with the source-side cut), series R, .OPTIONS, dV, gate
phases, park phase, head pre-charge gate, top-up gate, the TRUE-ZCS
probe-then-cut protocol, the 1F-integrator metering discipline and the
per-gate settling convention are qal/chain3/chain.py VERBATIM, which is
qal/lsweep/lsw.py verbatim, which is swsweep/sw_hop_meter.py verbatim, which is
gateb's committed harness verbatim.

WHAT IS NEW HERE AND NOWHERE ELSE: the POWER SCHEDULE is a parameter.

  scheme "skip" : 5 banks, hops 1->3, 2->4, 3->5 at beats 1,2,3.
                  Two interleaved power chains (odd 1->3->5, even 2->4).
                  Banks 1 AND 2 are power-chain heads (ideally pre-charged).
  scheme "adj"  : 4 banks, hops 1->2, 2->3, 3->4 at beats 1,2,3.
                  One power chain. Bank 1 only is a head.

DATA is identical in both: bank 1's 8 inputs are ideal sources, and thereafter
o{k}_{i} IS in of bank k+1 -- the same net. No flop, latch, buffer or level
shifter anywhere.

Pre-registration: PRE_REGISTERED.json (written before this file existed).
Amendments: AMENDMENT.md.

Stages: warm | probe <scheme> <mode> <T> | row <scheme> <mode> <T> | show
"""
import json, math, os, re, subprocess, sys, time

HERE  = os.path.dirname(os.path.abspath(__file__))
XYCE  = "/usr/local/src/xyce-build/src/Xyce"
VA    = "/usr/local/share/xyce/verilog-a/psp103/psp103.va"
MODEL = "/usr/local/src/kestrel/sim/models/sg13g2_psp103_tt.lib"
SHIM  = "/usr/local/src/stat-sim/qal/sg13lv_compat.sp"
CACHE = os.environ.get("PYMS_VAE_CACHE") or \
    "/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6/scratchpad/vae_cache_skip4"
ENV = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS", PYMS_VAE_CACHE=CACHE)

# ---- inherited constants (committed; not touched) --------------------------
RS_REF    = 10.0
VGH       = 1.5
WP, WN    = 1.12, 0.74          # cell inverter widths
MGATE     = 8
CLOAD     = 2.0                 # fF per cell output
EDGE      = 2.0                 # ps, committed transfer-gate edge
LAG_PS    = 1.0                 # MEASURED .measure-FIND lag in this Xyce build
HEAD_EDGE = 20.0                # chain3 A2: soft head cut (2 ps aborts the run)
HEAD_LEAD = 40.0                # ps, head cut STARTS this far before its beat
HEAD_WN, HEAD_WP = 1.0, 1.12    # um, small head pre-charge gate
TAIL      = 500.0               # ps, post-last-stage eventual-settle tail
TOPUP_W   = 20.0                # ps, top-up conduction window at the beat START
T1        = 200.0               # ps, beat 1 closes (pre-roll for the chain head)
L_REF     = 277.8
TZ_REF    = 266.755223          # ps, committed tg15p true zero at L_REF
TZ_ANCHOR = 65.49500982344826   # ps, committed L=15/W30/dV1.2 single-hop zero
CHAIN_F   = 1.35                # DERIVED sizing factor only (chain3 measured 1.326x)

# the two schedules.  (src, dst) per hop, hop h closes at T1 + (h-1)*T.
SCHED = {"skip": dict(nbank=5, hops=[(1, 3), (2, 4), (3, 5)], heads=[1, 2]),
         "adj":  dict(nbank=4, hops=[(1, 2), (2, 3), (3, 4)], heads=[1])}


def widths(total_um):
    """1:2 n:p TG + park = total/15.  total=15 reproduces committed tg15p."""
    return dict(wn=total_um / 3.0, wp=2.0 * total_um / 3.0, park=total_um / 15.0)


def is_hi(k, i):
    """Bank k cell i has a logic-HIGH input (pull-DOWN cell) iff (i+k) is odd.
    Bank 1's inputs alternate 1,0,1,0..., every bank inverts, so EVERY bank has
    4 pull-UP and 4 pull-DOWN cells at EVERY stage."""
    return (i + k) % 2 == 1


def in_net(k, i):
    """THE POINT OF THE WHOLE DECK.  k==1 -> ideal source (chain head);
    k>1 -> literally o{k-1}_{i}, the predecessor's output net."""
    return "in1_%d" % i if k == 1 else "o%d_%d" % (k - 1, i)


# ------------------------------------------------------------------ schedule
def schedule(scheme, T, dv, tz=None):
    """Every time in the deck, derived from the beat period T alone.

    c_k       = close of the hop that charges bank k (None for a head bank)
    d_k       = close of the hop that DRAINS bank k (None if it never drains)
    bound_k   = bank k's stage boundary = min(c_k + T, d_k - EDGE); for a head
                bank, d_k - EDGE.  AMENDMENT A1: the 'c_k + T' rule of the
                pre-registration, made STRICT by the last-undisturbed-instant
                clause, which can only move a checkpoint EARLIER.
    """
    S = SCHED[scheme]
    nb, hops = S["nbank"], S["hops"]
    tz = tz or [TZ_ANCHOR * CHAIN_F] * len(hops)
    close = [T1 + h * T for h in range(len(hops))]
    open_ = [close[h] + tz[h] for h in range(len(hops))]
    c, d = {}, {}
    for h, (s, t) in enumerate(hops):
        c[t] = close[h]
        d[s] = close[h]
    bound = {}
    for k in range(1, nb + 1):
        if k in c:
            b = c[k] + T
            if k in d:
                b = min(b, d[k] - EDGE)
        else:                                     # head bank
            b = d[k] - EDGE
        bound[k] = b
    tend = max(max(bound.values()), max(open_)) + TAIL
    te = TZ_ANCHOR * CHAIN_F
    return dict(nbank=nb, hops=hops, heads=S["heads"], T=T, close=close,
                open=open_, c=c, d=d, bound=bound, tend=tend, tz=tz,
                head_cut={k: d[k] - HEAD_LEAD for k in S["heads"]},
                pstep=0.1, mstep=min(0.25, te / 1000.0), t_est=te)


# --------------------------------------------------------------- deck pieces
def head_lines():
    return ['.hdl "%s"' % VA, '.include "%s"' % MODEL, '.include "%s"' % SHIM,
            '.OPTIONS TIMEINT METHOD=GEAR RELTOL=1e-6 ABSTOL=1e-15 CHGTOL=1e-17']


def bank_cells(k, dv, ideal_data=()):
    """One level of logic.  Committed cell verbatim: pMOS w=1.12u with supply AND
    bulk on the bank rail, nMOS w=0.74u, CL 2 fF.

    ideal_data: banks whose gate inputs come from ideal DC sources instead of the
    predecessor's outputs.  Bank 1 is always in that set (it is the chain head).
    Any OTHER bank in it is a deliberate CAUSAL CONTROL, labelled as such: it asks
    'if this bank's inputs were NOT degraded by its own predecessor being drained,
    would its successor recover?'"""
    L = ["VMG%d gn%d 0 0" % (k, k)]
    if k == 1 or k in ideal_data:
        for i in range(MGATE):
            L.append("VI%d_%d in%d_%d 0 %g"
                     % (k, i, k, i, dv if is_hi(k, i) else 0.0))
    for i in range(MGATE):
        s = ("in%d_%d" % (k, i)) if (k == 1 or k in ideal_data) else in_net(k, i)
        L.append("XP%d_%d o%d_%d %s rail%d rail%d sg13_lv_pmos w=%gu l=0.13u"
                 % (k, i, k, i, s, k, k, WP))
        L.append("XN%d_%d o%d_%d %s gn%d gn%d sg13_lv_nmos w=%gu l=0.13u"
                 % (k, i, k, i, s, k, k, WN))
        L.append("CL%d_%d o%d_%d gn%d %gf" % (k, i, k, i, k, CLOAD))
    return L


def transfer_switch(h, src, dst, total_um):
    """Hop h between rail{src} and rail{dst}.  DESTINATION side: the committed
    tg15p triple between the inductor node sw{h} and rail{dst}.  SOURCE side
    (chain3 finding d, MANDATORY): an IDENTICAL triple between rail{src} and the
    inductor's near node a{h}, on the SAME phases.  No park on a{h}."""
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


def supply_tg(k, total_um, win, kind):
    """Bank k's connection to the ideal dV rail.  kind='head' -> the small soft
    pre-charge gate that seeds a power-chain head; kind='topup' -> the optional
    per-beat tg15p-sized top-up; kind=None -> the device is absent entirely
    (free-running bank)."""
    if kind is None:
        return []
    w = widths(total_um)
    wn, wp = (HEAD_WN, HEAD_WP) if kind == "head" else (w["wn"], w["wp"])
    e = HEAD_EDGE if kind == "head" else EDGE
    L = ["XTUN%d rail%d tun%d vdv 0 sg13_lv_nmos w=%gu l=0.13u" % (k, k, k, wn),
         "XTUP%d rail%d tup%d vdv vhi sg13_lv_pmos w=%gu l=0.13u" % (k, k, k, wp)]
    if kind == "hold":                           # IDEAL-RAIL CONTROL: always on
        return L + ["VTUN%d tun%d 0 %g" % (k, k, VGH), "VTUP%d tup%d 0 0" % (k, k)]
    if win is None:
        L += ["VTUN%d tun%d 0 0" % (k, k), "VTUP%d tup%d 0 %g" % (k, k, VGH)]
    elif win[0] <= 0.0:                          # on from t=0 (a chain head)
        b = win[1]
        L += ["VTUN%d tun%d 0 PWL(0 %g %gp %g %gp 0)" % (k, k, VGH, b, VGH, b + e),
              "VTUP%d tup%d 0 PWL(0 0 %gp 0 %gp %g)" % (k, k, b, b + e, VGH)]
    else:
        a, b = win
        L += ["VTUN%d tun%d 0 PWL(0 0 %gp 0 %gp %g %gp %g %gp 0)"
              % (k, k, a, a + e, VGH, b, VGH, b + e),
              "VTUP%d tup%d 0 PWL(0 %g %gp %g %gp 0 %gp 0 %gp %g)"
              % (k, k, VGH, a, VGH, a + e, b, b + e, VGH)]
    return L


def integ(tg, expr):
    return ["CX%s x%s 0 1" % (tg, tg), "BX%s 0 x%s I={ %s }" % (tg, tg, expr),
            "RX%s x%s 0 0.01" % (tg, tg)]


def hop_integrators(S, rs, topup):
    L, tags = [], []
    for h, (s, t) in enumerate(S["hops"], 1):
        for nm, ex in (("qlt%d" % h, "I(L%d)" % h),
                       ("ea%d" % h, "V(rail%d)*I(L%d)" % (s, h)),
                       ("ean%d" % h, "V(a%d)*I(L%d)" % (h, h)),
                       ("eb%d" % h, "V(rail%d)*I(L%d)" % (t, h)),
                       ("er%d" % h, "I(L%d)*I(L%d)*%g" % (h, h, rs)),
                       ("esw%d" % h, "V(sw%d)*I(L%d)" % (h, h))):
            L += integ(nm, ex); tags.append(nm)
    for k in range(1, S["nbank"] + 1):
        L += integ("qg%d" % k, "I(VMG%d)" % k); tags.append("qg%d" % k)
    L += integ("qdv", "-I(VDV)"); tags.append("qdv")
    L += integ("qi1", "-(" + "+".join("I(VI1_%d)" % i for i in range(MGATE)) + ")")
    tags.append("qi1")
    nh = len(S["hops"])
    L += integ("egt", "-" + "-".join(
        "V(gt%d)*I(VGT%d)-V(gtp%d)*I(VGTP%d)-V(pk%d)*I(VPK%d)" % (h, h, h, h, h, h)
        for h in range(1, nh + 1)))
    tags.append("egt")
    return L, tags


def phases(h, tc, to, big):
    """Committed phase set.  tc=None -> hop idle (park HELD ON, which pins the
    otherwise-floating inductor island -- safe and necessary once the source side
    is cut).  to=None -> closes and never opens (the ZCS probe)."""
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
def deck(scheme, mode, T, total_um, l_nh, dv, rs=RS_REF, tz=None, probe=None):
    """probe = h  -> hops 1..h-1 cut at their measured zeros, hop h closes at its
                     beat and NEVER opens (the true-ZCS probe for hop h), later
                     hops idle.  probe=None -> the measured deck."""
    S = schedule(scheme, T, dv, tz)
    big = S["tend"] * 4.0
    L = head_lines() + [".param LT=%gn RS=%g" % (l_nh, rs),
                        "VHI vhi 0 %g" % VGH, "VDV vdv 0 %g" % dv]
    # CAUSAL CONTROL 'dataheld': the bank that feeds the first hop-charged bank has
    # ideal DC inputs, i.e. its own predecessor is never drained out from under it.
    # skip: bank 2 feeds bank 3.  adj: bank 1 already has ideal inputs and feeds
    # bank 2, so the adjacent scheme has NO such bank -- which is the point.
    ideal_data = (2,) if (mode == "dataheld" and scheme == "skip") else ()
    for k in range(1, S["nbank"] + 1):
        L += bank_cells(k, dv, ideal_data)
    # --- supply devices: head pre-charge on the power-chain heads; per-beat
    #     top-up on every hop-charged bank only in mode 'topup'
    for k in range(1, S["nbank"] + 1):
        if k in S["heads"]:
            L += supply_tg(k, total_um, (0.0, S["head_cut"][k]), "head")
        elif mode == "dstheld" and k == S["nbank"]:
            # AMENDMENT A2 (revised): IDEAL-RAIL CONTROL on the DEEPEST bank only.
            # Its rail is pinned to dV for the whole run while its INPUTS stay
            # fully realistic (its data source bank still has its own source
            # drained on schedule).  That separates 'the delivered rail is too low
            # for the pull-ups' from 'the inputs are degraded'.  The deepest bank
            # has no successor, so pinning it removes no drain event from the deck.
            L += supply_tg(k, total_um, None, "hold")
        else:
            L += supply_tg(k, total_um, None, None)
    # --- the hops
    for h, (s, t) in enumerate(S["hops"], 1):
        L += ["L%d a%d mid%d {LT}" % (h, h, h), "R%d mid%d sw%d {RS}" % (h, h, h)]
        L += transfer_switch(h, s, t, total_um)
    nh = len(S["hops"])
    for h in range(1, nh + 1):
        tc, to = S["close"][h - 1], S["open"][h - 1]
        if probe is None:
            L += phases(h, tc, to, big)
        elif h < probe:
            L += phases(h, tc, to, big)
        elif h == probe:
            L += phases(h, tc, None, big)
        else:
            L += phases(h, None, None, big)
    tend = S["tend"] if probe is None else (S["close"][probe - 1] + 1.8 * S["t_est"])
    tags = []
    if probe is None:
        ig, tags = hop_integrators(S, rs, mode == "topup")
        L += ig
    ic = " ".join("V(rail%d)=%g" % (k, dv if k in S["heads"] else 0.0)
                  for k in range(1, S["nbank"] + 1))
    L.append(".ic " + ic + " " + " ".join("V(a%d)=0" % h for h in range(1, nh + 1)))
    L.append(".tran %gp %gp 0 %gp" % (S["pstep"], tend, S["mstep"]))
    g = lambda t: t + LAG_PS
    if probe is None:
        cks = [("Z", 0.5)] + [("B%d" % h, S["open"][h - 1]) for h in range(1, nh + 1)] \
              + [("K%d" % k, S["bound"][k]) for k in range(1, S["nbank"] + 1)] \
              + [("D", tend - 5.0)]
        for tg in tags:
            for nm, tt in cks:
                L.append(".measure tran %s_%s FIND V(x%s) AT=%.6fp"
                         % (tg.upper(), nm, tg, g(tt)))
        for nm, tt in cks:
            for k in range(1, S["nbank"] + 1):
                L.append(".measure tran VR%d%s FIND V(rail%d) AT=%.6fp"
                         % (k, nm, k, g(tt)))
        for k in range(1, S["nbank"] + 1):
            L.append(".measure tran VR%dPK MAX V(rail%d) FROM=%gp TO=%gp"
                     % (k, k, T1, tend))
            for i in range(MGATE):
                L.append(".measure tran O%d_%dS FIND V(o%d_%d) AT=%.6fp"
                         % (k, i, k, i, g(S["bound"][k])))
                L.append(".measure tran O%d_%dE FIND V(o%d_%d) AT=%.6fp"
                         % (k, i, k, i, g(tend - 5.0)))
        for h in range(1, nh + 1):
            L.append(".measure tran IZ%d FIND I(L%d) AT=%.6fp"
                     % (h, h, g(S["open"][h - 1])))
            L.append(".measure tran IPK%d MAX I(L%d) FROM=%gp TO=%gp"
                     % (h, h, T1, tend))
        pr = ["V(rail%d)" % k for k in range(1, S["nbank"] + 1)] + \
             ["I(L%d)" % h for h in range(1, nh + 1)] + \
             ["V(o%d_%d)" % (k, i) for k in range(1, S["nbank"] + 1)
              for i in range(MGATE)] + \
             ["V(sw%d)" % h for h in range(1, nh + 1)] + \
             ["V(a%d)" % h for h in range(1, nh + 1)]
    else:
        pr = ["I(L%d)" % h for h in range(1, nh + 1)] + \
             ["V(rail%d)" % k for k in range(1, S["nbank"] + 1)] + \
             ["V(sw%d)" % h for h in range(1, nh + 1)] + \
             ["V(a%d)" % h for h in range(1, nh + 1)]
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
    linearly interpolated (lsweep's refined rule; the committed next-print-point
    rule is one solver step late)."""
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
    """(t, v) samples of one column on [ta, tb]."""
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
def stage_warm():
    """Touch every geometry so parallel runs never trigger a PyMS compile."""
    w = widths(30.0)
    need_n = sorted(set([WN, w["wn"], w["park"], HEAD_WN]))
    need_p = sorted(set([WP, w["wp"], HEAD_WP]))
    L = head_lines() + ["V1 a 0 0.5", "V2 b 0 0.5"]
    k = 0
    for x in need_n:
        L.append("XWN%d d%d a 0 0 sg13_lv_nmos w=%gu l=0.13u" % (k, k, x))
        L.append("RN%d d%d b 1k" % (k, k)); k += 1
    for x in need_p:
        L.append("XWP%d e%d a b b sg13_lv_pmos w=%gu l=0.13u" % (k, k, x))
        L.append("RP%d e%d 0 1k" % (k, k)); k += 1
    L += [".tran 1p 10p", ".print tran V(a)", ".end"]
    print("warming n=%s p=%s" % (need_n, need_p))
    p, msg = run("warm.cir", L, timeout=900)
    print(msg)
    return p is not None


def tag_of(scheme, mode, T, dv):
    return "%s_%s_T%g_dv%g" % (scheme, mode, T, dv * 1000)


def do_probe(scheme, mode, T, total_um, l_nh, dv):
    """Sequential true-ZCS probe: hop 1's zero, then hop 2's with hop 1 cut at
    its own zero, then hop 3's with 1 and 2 cut.  Inherited protocol."""
    tg = tag_of(scheme, mode, T, dv)
    nh = len(SCHED[scheme]["hops"])
    tz = []
    for h in range(1, nh + 1):
        lines, S = deck(scheme, mode, T, total_um, l_nh, dv,
                        tz=tz + [TZ_ANCHOR * CHAIN_F] * (nh - len(tz)), probe=h)
        fn = "p%d_%s.cir" % (h, tg)
        path = os.path.join(HERE, fn)
        cached = (os.path.exists(path) and os.path.exists(path + ".prn")
                  and open(path).read() == "\n".join(lines) + "\n")
        if cached:
            p, msg = path, "reused %s (byte-identical deck already run)" % fn
        else:
            p, msg = run(fn, lines)
        print("  probe%d %s" % (h, msg))
        if p is None:
            return None
        hdr, rows = read_prn(p + ".prn")
        z, pk = zero_after_peak(hdr, rows, "I(L%d)" % h, S["close"][h - 1])
        if z is None:
            print("  probe%d NO ZERO" % h)
            return None
        tz.append(z - S["close"][h - 1])
        print("    hop%d t_zcs = %.4f ps (Ipk %.2f uA)" % (h, tz[-1], pk * 1e6))
    return tz


def do_row(scheme, mode, T, total_um, l_nh, dv, tz):
    tg = tag_of(scheme, mode, T, dv)
    lines, S = deck(scheme, mode, T, total_um, l_nh, dv, tz=tz)
    fn = "c_%s.cir" % tg
    p, msg = run(fn, lines)
    print("  row %s" % msg)
    if p is None:
        return None
    return p, S


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] == "warm":
        sys.exit(0 if stage_warm() else 1)
    if a[0] == "probe":
        scheme, mode, T, dv = a[1], a[2], float(a[3]), float(a[4])
        tz = do_probe(scheme, mode, T, 30.0, 15.0, dv)
        print(json.dumps(tz))
    elif a[0] == "row":
        scheme, mode, T, dv = a[1], a[2], float(a[3]), float(a[4])
        tz = json.loads(a[5])
        do_row(scheme, mode, T, 30.0, 15.0, dv, tz)
