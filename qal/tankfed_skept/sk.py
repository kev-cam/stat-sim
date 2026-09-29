#!/usr/bin/env python3
"""qal/tankfed_skept -- INDEPENDENT SKEPTIC re-implementation of the tankfed
chain, written from the documented conventions, not imported from tf.py.

Conventions reproduced (committed harness, verbatim in intent):
  cell        sg13_lv_pmos w=1.12u / sg13_lv_nmos w=0.74u l=0.13u, CL 2 fF,
              supply AND pMOS bulk on rail_k, nMOS source/bulk on the 0 V
              ground meter gn_k.
  tg15p       TG 10/20 um + 2 um park, on BOTH the destination and the source
              side of every hop.  L = 15 nH, RS = 10 ohm.
  head        5 x 10um nMOS + 3 x 20um pMOS pre-charge gate from the ideal dV
              source (the BOUNDARY of the modelled system).
  tank        CTK_k ntk_k -> 0, strapped to rail_k through RSTRAP (real R).
  top-up      switched clamp, tg15p-sized, from the ideal dV source to the
              DESTINATION node (rail_k or ntk_k), 20 ps window at t_open+6*EDGE.
              PRESENT-AND-PARKED-OFF in the free control.
  metering    1F integrators only, every read t0-referenced by differencing.

NEW HERE (not in tankfed): a NOTANK arm (ctk=0 everywhere) -- the control the
2x2 lacks, because BOTH of its destinations carry the tank, so the 2x2 cannot
measure the brief's "the tank is large, so the same charge makes a smaller
step" claim at all.  Also a finite-RESERVOIR clamp arm, which tests whether the
amplitude null is a property of physics or of the ideal dV source.
"""
import json, os, re, subprocess, sys, time

HERE  = os.path.dirname(os.path.abspath(__file__))
XYCE  = "/usr/local/src/xyce-build/src/Xyce"
VA    = "/usr/local/share/xyce/verilog-a/psp103/psp103.va"
MODEL = "/usr/local/src/kestrel/sim/models/sg13g2_psp103_tt.lib"
SHIM  = "/usr/local/src/stat-sim/qal/sg13lv_compat.sp"
CACHE = "/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6/scratchpad/vae_cache_tfskept"
ENV   = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS", PYMS_VAE_CACHE=CACHE)

RS_REF, VGH   = 10.0, 1.5
WP, WN, CLOAD = 1.12, 0.74, 2.0
EDGE, LAG_PS  = 2.0, 1.0
HEAD_EDGE, HEAD_LEAD = 20.0, 40.0
HEAD_NREP, HEAD_PREP = 5, 3
TAIL, TOPUP_W, T1    = 500.0, 20.0, 200.0
TZ_ANCHOR, CHAIN_F   = 65.49500982344826, 1.35
PROFILE  = [48, 19, 3, 1, 2]
RSTRAP   = 2.0
TOPPED   = (3, 4)
HOPS     = [(1, 2), (2, 3), (3, 4), (4, 5)]
PRINT_BANKS = (2, 3, 4)


def widths(total_um):
    return dict(wn=total_um / 3.0, wp=2.0 * total_um / 3.0, park=total_um / 15.0)


def is_hi(k, i):
    """cell i of bank k has a logic-HIGH input (is a pull-DOWN) iff (i+k) odd."""
    return (i + k) % 2 == 1


def in_net(k, i, prof):
    if k == 1:
        return "in1_%d" % i
    return "o%d_%d" % (k - 1, i % prof[k - 2])


def true_input_hi(k, i, prof):
    """The input level this cell ACTUALLY receives, traced through the netlist
    rather than assumed from the (i+k) parity rule.  Bank 1's inputs are the
    ideal sources; for k>1 the input is the predecessor's OUTPUT, whose logic
    value is the inverse of that predecessor's own input.  Where a bank is wider
    than its predecessor the fan-out modulo makes the parity rule and the
    netlist DISAGREE, and this function is what catches it."""
    if k == 1:
        return is_hi(1, i)
    j = i % prof[k - 2]
    return not true_input_hi(k - 1, j, prof)


def schedule(T, tz=None, prof=PROFILE):
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
    return dict(nbank=nb, T=T, close=close, open=open_, c=c, d=d, bound=bound,
                tend=tend, tz=tz, prof=prof, head_cut={1: d[1] - HEAD_LEAD},
                pstep=0.1, mstep=min(0.25, te / 1000.0), t_est=te)


def head_lines():
    return ['.hdl "%s"' % VA, '.include "%s"' % MODEL, '.include "%s"' % SHIM,
            '.OPTIONS TIMEINT METHOD=GEAR RELTOL=1e-6 ABSTOL=1e-15 CHGTOL=1e-17']


def integ(tg, expr):
    return ["CX%s x%s 0 1" % (tg, tg), "BX%s 0 x%s I={ %s }" % (tg, tg, expr),
            "RX%s x%s 0 0.01" % (tg, tg)]


def bank_cells(k, dv, prof):
    M = prof[k - 1]
    L = ["VMG%d gn%d 0 0" % (k, k)]
    if k == 1:
        for i in range(M):
            L.append("VI%d_%d in%d_%d 0 %g" % (k, i, k, i, dv if is_hi(k, i) else 0.0))
    for i in range(M):
        s = in_net(k, i, prof)
        L.append("XP%d_%d o%d_%d %s rail%d rail%d sg13_lv_pmos w=%gu l=0.13u"
                 % (k, i, k, i, s, k, k, WP))
        L.append("XN%d_%d o%d_%d %s gn%d gn%d sg13_lv_nmos w=%gu l=0.13u"
                 % (k, i, k, i, s, k, k, WN))
        L.append("CL%d_%d o%d_%d gn%d %gf" % (k, i, k, i, k, CLOAD))
    return L


def tank(k, ctk):
    if not ctk:
        return []
    return ["CTK%d ntk%d 0 %.6gf" % (k, k, ctk),
            "RTK%d ntk%d rail%d %g" % (k, k, k, RSTRAP)]


def transfer_switch(h, src, dst, total_um):
    w = widths(total_um)
    return ["XSWN%d sw%d gt%d rail%d 0 sg13_lv_nmos w=%gu l=0.13u" % (h, h, h, dst, w["wn"]),
            "XSWP%d sw%d gtp%d rail%d vhi sg13_lv_pmos w=%gu l=0.13u" % (h, h, h, dst, w["wp"]),
            "XPK%d sw%d pk%d 0 0 sg13_lv_nmos w=%gu l=0.13u" % (h, h, h, w["park"]),
            "XSWSN%d a%d gt%d rail%d 0 sg13_lv_nmos w=%gu l=0.13u" % (h, h, h, src, w["wn"]),
            "XSWSP%d a%d gtp%d rail%d vhi sg13_lv_pmos w=%gu l=0.13u" % (h, h, h, src, w["wp"])]


def head_tg(k, cut):
    e, b = HEAD_EDGE, cut
    L = ["XHDN%d_%d rail%d hdn%d vdv 0 sg13_lv_nmos w=10u l=0.13u" % (k, j, k, k)
         for j in range(HEAD_NREP)]
    L += ["XHDP%d_%d rail%d hdp%d vdv vhi sg13_lv_pmos w=20u l=0.13u" % (k, j, k, k)
          for j in range(HEAD_PREP)]
    return L + ["VHDN%d hdn%d 0 PWL(0 %g %gp %g %gp 0)" % (k, k, VGH, b, VGH, b + e),
                "VHDP%d hdp%d 0 PWL(0 0 %gp 0 %gp %g)" % (k, k, b, b + e, VGH)]


def topup_clamp(k, dest, total_um, win, live, srcnode="vdv"):
    """The committed switched clamp.  PRESENT in both arms; `live` only decides
    whether it FIRES, so the difference is attributable to firing alone."""
    w = widths(total_um)
    L = ["XTUN%d %s tun%d %s 0 sg13_lv_nmos w=%gu l=0.13u" % (k, dest, k, srcnode, w["wn"]),
         "XTUP%d %s tup%d %s vhi sg13_lv_pmos w=%gu l=0.13u" % (k, dest, k, srcnode, w["wp"])]
    if not live or win is None:
        return L + ["VTUN%d tun%d 0 0" % (k, k), "VTUP%d tup%d 0 %g" % (k, k, VGH)]
    a, b, e = win[0], win[1], EDGE
    return L + ["VTUN%d tun%d 0 PWL(0 0 %gp 0 %gp %g %gp %g %gp 0)"
                % (k, k, a, a + e, VGH, b, VGH, b + e),
                "VTUP%d tup%d 0 PWL(0 %g %gp %g %gp 0 %gp 0 %gp %g)"
                % (k, k, VGH, a, VGH, a + e, b, b + e, VGH)]


def phases(h, tc, to, big):
    if tc is None:
        return ["VGT%d gt%d 0 0" % (h, h), "VGTP%d gtp%d 0 %g" % (h, h, VGH),
                "VPK%d pk%d 0 %g" % (h, h, VGH)]
    if to is None:
        return ["VGT%d gt%d 0 PWL(0 0 %gp 0 %gp %g %gp %g)" % (h, h, tc - EDGE, tc, VGH, big, VGH),
                "VGTP%d gtp%d 0 PWL(0 %g %gp %g %gp 0 %gp 0)" % (h, h, VGH, tc - EDGE, VGH, tc, big),
                "VPK%d pk%d 0 PWL(0 %g %gp %g %gp 0)" % (h, h, VGH, tc, VGH, tc + EDGE)]
    return ["VGT%d gt%d 0 PWL(0 0 %gp 0 %gp %g %gp %g %gp 0)"
            % (h, h, tc - EDGE, tc, VGH, to, VGH, to + EDGE),
            "VGTP%d gtp%d 0 PWL(0 %g %gp %g %gp 0 %gp 0 %gp %g)"
            % (h, h, VGH, tc - EDGE, VGH, tc, to, to + EDGE, VGH),
            "VPK%d pk%d 0 PWL(0 %g %gp %g %gp 0 %gp 0 %gp %g)"
            % (h, h, VGH, tc, VGH, tc + EDGE, to + EDGE, to + 2 * EDGE, VGH)]


def deck(cfg, tz=None, probe=None):
    T, dv = cfg["T"], cfg["dv"]
    prof = cfg.get("prof", PROFILE)
    total_um = cfg.get("total_um", 30.0)
    l_nh, rs = cfg.get("l_nh", 15.0), cfg.get("rs", RS_REF)
    S = schedule(T, tz, prof)
    big = S["tend"] * 4.0
    nb, nh = S["nbank"], len(HOPS)
    form, dest = cfg["form"], cfg["dest"]
    ctk = cfg["ctk"]
    # --- the RESERVOIR arm: the clamp is fed from a FINITE capacitor pre-charged
    #     to dv, not from the ideal source.  This is the booking test.
    res = cfg.get("reservoir_fF")
    src = "nres" if res else "vdv"
    L = head_lines() + ["VHI vhi 0 %g" % VGH, "VDV vdv 0 %g" % dv]
    if res:
        L += ["CRES nres 0 %.6gf" % res]
    for k in range(1, nb + 1):
        L += bank_cells(k, dv, prof)
    for k in range(1, nb + 1):
        L += tank(k, ctk.get(k))
    L += head_tg(1, S["head_cut"][1])
    for k in TOPPED:
        dn = ("rail%d" % k) if dest == "bank" else ("ntk%d" % k)
        t_open = S["open"][[t for _, t in HOPS].index(k)]
        t_fire = t_open + 6 * EDGE
        win = (t_fire, t_fire + TOPUP_W) if form == "clamp" else None
        L += topup_clamp(k, dn, total_um, win, form == "clamp", src)
    for h, (s, t) in enumerate(HOPS, 1):
        L += ["L%d a%d mid%d %gn" % (h, h, h, l_nh), "R%d mid%d sw%d %g" % (h, h, h, rs)]
        L += transfer_switch(h, s, t, total_um)
    for h in range(1, nh + 1):
        tc, to = S["close"][h - 1], S["open"][h - 1]
        if probe is None or h < probe:
            L += phases(h, tc, to, big)
        elif h == probe:
            L += phases(h, tc, None, big)
        else:
            L += phases(h, None, None, big)
    tags = []
    if probe is None:
        for h, (s, t) in enumerate(HOPS, 1):
            for nm, ex in (("qlt%d" % h, "I(L%d)" % h),
                           ("er%d" % h, "I(L%d)*I(L%d)*%g" % (h, h, rs))):
                L += integ(nm, ex); tags.append(nm)
        L += integ("qdv", "-I(VDV)"); tags.append("qdv")
        L += integ("egt", "-" + "-".join(
            "V(gt%d)*I(VGT%d)-V(gtp%d)*I(VGTP%d)-V(pk%d)*I(VPK%d)" % (h, h, h, h, h, h)
            for h in range(1, nh + 1))); tags.append("egt")
        L += integ("ehd", "-V(hdn1)*I(VHDN1)-V(hdp1)*I(VHDP1)"); tags.append("ehd")
        for k in TOPPED:
            L += integ("egtu%d" % k,
                       "-V(tun%d)*I(VTUN%d)-V(tup%d)*I(VTUP%d)" % (k, k, k, k))
            tags.append("egtu%d" % k)
    ic = " ".join("V(rail%d)=%g" % (k, dv if k == 1 else 0.0) for k in range(1, nb + 1))
    ic += "".join(" V(ntk%d)=%g" % (k, dv if k == 1 else 0.0)
                  for k in range(1, nb + 1) if ctk.get(k))
    if res:
        ic += " V(nres)=%g" % dv
    L.append(".ic " + ic + " " + " ".join("V(a%d)=0" % h for h in range(1, nh + 1)))
    tend = (S["close"][probe - 1] + cfg.get("probe_span", 6.0 * S["t_est"])) \
        if probe is not None else S["tend"]
    L.append(".tran %gp %gp 0 %gp" % (S["pstep"], tend, S["mstep"]))
    g = lambda t: t + LAG_PS
    if probe is None:
        cks = [("Z", 0.5)] + [("B%d" % h, S["open"][h - 1]) for h in range(1, nh + 1)] \
              + [("K%d" % k, S["bound"][k]) for k in range(1, nb + 1)] + [("D", tend - 5.0)]
        for tg in tags:
            for nm, tt in cks:
                L.append(".measure tran %s_%s FIND V(x%s) AT=%.6fp" % (tg.upper(), nm, tg, g(tt)))
        for nm, tt in cks:
            for k in range(1, nb + 1):
                L.append(".measure tran VR%d%s FIND V(rail%d) AT=%.6fp" % (k, nm, k, g(tt)))
                if ctk.get(k):
                    L.append(".measure tran VT%d%s FIND V(ntk%d) AT=%.6fp" % (k, nm, k, g(tt)))
        for k in range(1, nb + 1):
            for i in range(prof[k - 1]):
                L.append(".measure tran O%d_%dS FIND V(o%d_%d) AT=%.6fp"
                         % (k, i, k, i, g(S["bound"][k])))
                L.append(".measure tran G%d_%d FIND V(%s) AT=%.6fp"
                         % (k, i, in_net(k, i, prof), g(S["bound"][k])))
        for h in range(1, nh + 1):
            L.append(".measure tran IZ%d FIND I(L%d) AT=%.6fp" % (h, h, g(S["open"][h - 1])))
            L.append(".measure tran IPK%d MAX I(L%d) FROM=%gp TO=%gp" % (h, h, T1, tend))
        pr = ["V(rail%d)" % k for k in range(1, nb + 1)] + \
             ["V(ntk%d)" % k for k in range(1, nb + 1) if ctk.get(k)] + \
             ["I(L%d)" % h for h in range(1, nh + 1)] + \
             ["V(o%d_%d)" % (k, i) for k in PRINT_BANKS for i in range(prof[k - 1])]
    else:
        pr = ["I(L%d)" % h for h in range(1, nh + 1)] + \
             ["V(rail%d)" % k for k in range(1, nb + 1)] + \
             ["V(ntk%d)" % k for k in range(1, nb + 1) if ctk.get(k)]
    L.append(".print tran " + " ".join(pr))
    L.append(".end")
    return L, S


def run(fn, lines, timeout=1500, reuse=True):
    path = os.path.join(HERE, fn)
    body = "\n".join(lines) + "\n"
    if reuse and os.path.exists(path) and os.path.exists(path + ".prn") \
            and open(path).read() == body:
        return path, "reused %s" % fn
    open(path, "w").write(body)
    t0 = time.monotonic()
    try:
        r = subprocess.run([XYCE, fn], capture_output=True, text=True,
                           timeout=timeout, cwd=HERE, env=ENV)
    except subprocess.TimeoutExpired:
        return None, "TIMEOUT %gs" % timeout
    wall = time.monotonic() - t0
    if r.returncode != 0 or not os.path.exists(path + ".prn"):
        err = "; ".join(l.strip() for l in r.stdout.splitlines()
                        if "rror" in l or "bort" in l)[:400]
        return None, "XYCE FAIL %s (%.1fs): %s" % (fn, wall, err or r.stdout[-300:])
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
            t0, v0 = prev
            tz = t0 if r[ic] == v0 else t0 + (0.0 - v0) * (t - t0) / (r[ic] - v0)
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
    ic = hdr.index(col)
    s = [(r[1] * 1e12, r[ic]) for r in rows if ta <= r[1] * 1e12 <= tb]
    best, bt = 0.0, None
    for j in range(1, len(s) - 1):
        dt = s[j + 1][0] - s[j - 1][0]
        if dt <= 0:
            continue
        d = abs(s[j + 1][1] - s[j - 1][1]) / dt * 1e3
        if d > best:
            best, bt = d, s[j][0]
    return best, bt
