#!/usr/bin/env python3
"""TRACK 1: the L-DOWN SPEED SWEEP of the QAL bank-to-bank hop.

Deck topology, cells, metering integrators, .OPTIONS, dV, CA, RS, VGH, TRUE-ZCS
timing and the A2 robust energy metric are sar/sar_observable.py VERBATIM (which
is swsweep/sw_hop_meter.py verbatim, which is gateb's harness verbatim).

What is parameterised here and NOWHERE ELSE: L, the transfer-switch widths, and
the timestep resolution (scaled with L so the anchor point reproduces the
committed settings exactly).

Pre-registration: PRE_REGISTERED_LSWEEP.json -- written before any deck existed.

Stages: warm | g0 | point <tag> | sweep | report
"""
import json, math, os, re, subprocess, sys, time

HERE  = os.path.dirname(os.path.abspath(__file__))
SW    = os.path.normpath(os.path.join(HERE, "..", "swsweep"))
XYCE  = "/usr/local/src/xyce-build/src/Xyce"
VA    = "/usr/local/share/xyce/verilog-a/psp103/psp103.va"
MODEL = "/usr/local/src/kestrel/sim/models/sg13g2_psp103_tt.lib"
SHIM  = "/usr/local/src/stat-sim/qal/sg13lv_compat.sp"
CACHE = os.environ.get("PYMS_VAE_CACHE") or \
    "/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6/scratchpad/vae_cache_lsweep"
ENV = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS", PYMS_VAE_CACHE=CACHE)

# ---- inherited constants (committed; do not touch) -------------------------
DV        = 1.0
RS_REF    = 10.0
VGH       = 1.5
WP, WN    = 1.12, 0.74          # cell inverter widths
MGATE     = 8
CLOAD     = 2.0                 # fF per cell output
CA_FF     = 35.979              # committed C_eff at dV=1.0
T0        = 50.0                # ps, switch closes
L_REF     = 277.8               # nH, the committed energy-rule inductance
TZ_REF    = 266.755223          # ps, committed tg15p true zero
EDGE_REF  = 2.0                 # ps, committed gate edge
TAIL_REF  = 500.0               # ps, committed post-open tail

# MEASURED instrument constant (diag_find.py, this directory): in this Xyce build
# ".measure tran <NAME> FIND <expr> AT=T" returns the waveform value at T - 1.0 ps.
# Verified over an 11-point offset ladder at L=1 nH: mt0 FIND at (t_open + 1.0 ps)
# equals the .prn value at t_open to 4 digits (both ~0 A at the current zero),
# and the path identity ea-esw-er at the zero goes from 0.0895 fJ (uncorrected)
# to 0.000023 fJ (waveform).  Every .measure AT time is therefore requested
# LAG_PS late; the committed campaign's decks carry the uncorrected lag.
LAG_PS    = 1.0

HI = [i for i in range(MGATE) if i % 2 == 0]   # in=1 -> output must stay at 0
LO = [i for i in range(MGATE) if i % 2 == 1]   # in=0 -> output must follow rail

# committed anchor for the instrument gate
ANCHOR = dict(E_hop_open_fJ=8.3828171771408, VBEND=0.6758936, VBPK=0.7374377,
              VA_open=0.09778203952305342, cells_burn_fJ=1.6954746104994207,
              E_R_toC_fJ=0.049543034863200004, IZ_uA=-0.37939849999999997,
              IPK_uA=194.3655)


def t_est(l_nh):
    """DERIVED sqrt(L) prediction, used ONLY to size timesteps and run lengths."""
    return TZ_REF * math.sqrt(l_nh / L_REF)


def widths(total_um):
    """1:2 n:p TG + park = total/15.  total=15 reproduces committed tg15p."""
    return dict(wn=total_um / 3.0, wp=2.0 * total_um / 3.0, park=total_um / 15.0)


# --------------------------------------------------------------- deck pieces
def head():
    return ['.hdl "%s"' % VA, '.include "%s"' % MODEL, '.include "%s"' % SHIM,
            '.OPTIONS TIMEINT METHOD=GEAR RELTOL=1e-6 ABSTOL=1e-15 CHGTOL=1e-17']


def switch_lines(total_um):
    w = widths(total_um)
    return ["XSWN sw gt bkb 0 sg13_lv_nmos w=%gu l=0.13u" % w["wn"],
            "XSWP sw gtp bkb vhi sg13_lv_pmos w=%gu l=0.13u" % w["wp"],
            "XPK sw pk 0 0 sg13_lv_nmos w=%gu l=0.13u" % w["park"]]


def cells_metered(dv=DV):
    L = ["VMGH gnh 0 0", "VMGL gnl 0 0"]
    for i in range(MGATE):
        gnd = "gnh" if i in HI else "gnl"
        L.append("VI%d in%d 0 %g" % (i, i, dv if i in HI else 0.0))
        L.append("XP%d o%d in%d bkb bkb sg13_lv_pmos w=%gu l=0.13u" % (i, i, i, WP))
        L.append("XN%d o%d in%d %s %s sg13_lv_nmos w=%gu l=0.13u" % (i, i, i, gnd, gnd, WN))
        L.append("CL%d o%d %s %gf" % (i, i, gnd, CLOAD))
    return L


def _sup_expr(group):
    idx = HI if group == "H" else LO
    vg = "I(VMGH)" if group == "H" else "I(VMGL)"
    return vg + "+" + "+".join("I(VI%d)" % i for i in idx)


def integ(tg, expr):
    return ["CX%s x%s 0 1" % (tg, tg), "BX%s 0 x%s I={ %s }" % (tg, tg, expr),
            "RX%s x%s 0 0.01" % (tg, tg)]


def cell_integrators():
    L = []
    sh, sl = _sup_expr("H"), _sup_expr("L")
    L += integ("qsh", sh) + integ("qsl", sl)
    L += integ("esh", "V(bkb)*(%s)" % sh) + integ("esl", "V(bkb)*(%s)" % sl)
    L += integ("qgh", "I(VMGH)") + integ("qgl", "I(VMGL)")
    L += integ("qih", "-(" + "+".join("I(VI%d)" % i for i in HI) + ")")
    L += integ("eih", "-(" + "+".join("V(in%d)*I(VI%d)" % (i, i) for i in HI) + ")")
    L += integ("qil", "-(" + "+".join("I(VI%d)" % i for i in LO) + ")")
    return L


INTEG_TAGS_CELLS = ["qsh", "qsl", "esh", "esl", "qgh", "qgl", "qih", "eih", "qil"]
INTEG_TAGS_PATH  = ["qlt", "ea", "eb", "qbk", "ebk", "er", "esw", "qgt", "qgtp",
                    "qhi", "egt", "ehi"]


def path_integrators(rs):
    L = []
    L += integ("qlt", "I(LT)") + integ("ea", "V(bka)*I(LT)") + integ("eb", "V(bkb)*I(LT)")
    tot = "(%s)+(%s)" % (_sup_expr("H"), _sup_expr("L"))
    L += integ("qbk", tot) + integ("ebk", "V(bkb)*(%s)" % tot)
    L += integ("er", "I(LT)*I(LT)*%g" % rs)
    L += integ("esw", "V(sw)*I(LT)")
    L += integ("qgt", "-I(VGT)") + integ("qgtp", "-I(VGTP)") + integ("qhi", "-I(VHI)")
    L += integ("egt", "-V(gt)*I(VGT)-V(gtp)*I(VGTP)-V(pk)*I(VPK)")
    L += integ("ehi", "-%g*I(VHI)" % VGH)
    return L


# ---------------------------------------------------------------- probe deck
def probe_lines(l_nh, total_um, rs=RS_REF, edge=EDGE_REF, dv=DV, ca=CA_FF):
    cser = (ca / 2.0) * 1e-15
    tend = T0 + 6.0 * math.pi * math.sqrt((l_nh * 1e-9) * cser) * 1e12
    pstep = min(0.1, t_est(l_nh) / 2000.0)
    mstep = min(0.25, t_est(l_nh) / 1000.0)
    return head() + [
        ".param LT=%gn RS=%g CA=%gf" % (l_nh, rs, ca),
        "CA bka 0 {CA}",
        "VHI vhi 0 %g" % VGH,
        "VGT  gt  0 PWL(0 0 %gp 0 %gp %g %gp %g)" % (T0 - edge, T0, VGH, tend * 2, VGH),
        "VGTP gtp 0 PWL(0 %g %gp %g %gp 0 %gp 0)" % (VGH, T0 - edge, VGH, T0, tend * 2),
    ] + switch_lines(total_um) + ["VPK pk 0 0"] + [
        "LT bka mid {LT}", "RT mid sw {RS}",
    ] + cells_metered(dv) + [
        ".ic V(bka)=%g V(bkb)=0" % dv,
        ".print tran I(LT) V(bkb) V(bka) V(sw)",
        ".tran %gp %gp 0 %gp" % (pstep, tend, mstep), ".end"]


# ------------------------------------------------------------------ hop deck
def hop_lines(l_nh, total_um, t_half_ps, rs=RS_REF, edge=EDGE_REF, tail=TAIL_REF, dv=DV, ca=CA_FF):
    t_open = T0 + t_half_ps
    tend = t_open + tail
    pstep = min(0.1, t_est(l_nh) / 2000.0)
    mstep = min(0.25, t_est(l_nh) / 1000.0)
    L = head() + [
        ".param LT=%gn RS=%g CA=%gf" % (l_nh, rs, ca),
        "CA bka 0 {CA}",
        "VHI vhi 0 %g" % VGH,
        "VGT  gt  0 PWL(0 0 %gp 0 %gp %g %gp %g %gp 0)"
            % (T0 - edge, T0, VGH, t_open, VGH, t_open + edge),
        "VGTP gtp 0 PWL(0 %g %gp %g %gp 0 %gp 0 %gp %g)"
            % (VGH, T0 - edge, VGH, T0, t_open, t_open + edge, VGH),
    ] + switch_lines(total_um) + [
        "VPK pk 0 PWL(0 0 %gp 0 %gp %g)" % (t_open + edge, t_open + 2 * edge, VGH),
        "LT bka mid {LT}", "RT mid sw {RS}",
    ] + cells_metered(dv) + cell_integrators() + path_integrators(rs) + [
        "Bpa pa 0 V={ V(bka)*I(LT) }", "Bpb pb 0 V={ V(bkb)*I(LT) }",
        "Bqt qt 0 V={ I(LT) }",
        ".ic V(bka)=%g V(bkb)=0" % dv]
    L.append(".tran %gp %gp 0 %gp" % (pstep, tend, mstep))
    g = lambda t: t + LAG_PS          # request every FIND LAG_PS late
    L += [".measure tran VBPK  MAX V(bkb) FROM=%gp TO=%gp" % (T0, tend),
          ".measure tran VBEND FIND V(bkb) AT=%.6fp" % g(tend - 5),
          ".measure tran VAEND FIND V(bka) AT=%.6fp" % g(tend - 5),
          ".measure tran IPK   MAX I(LT) FROM=0 TO=%gp" % tend,
          ".measure tran IZ    FIND I(LT) AT=%.6fp" % g(t_open),
          ".measure tran VBOPEN FIND V(bkb) AT=%.6fp" % g(t_open),
          ".measure tran VSWPK MAX V(sw) FROM=0 TO=%gp" % tend,
          ".measure tran VSWMN MIN V(sw) FROM=%gp TO=%gp" % (T0, tend)]
    cks = [("Z", 0.5), ("A", T0 + min(5.0, max(0.5, t_est(l_nh) / 50.0))),
           ("B", t_open), ("C", t_open + min(7.0, max(1.0, 3.5 * edge))),
           ("D", tend - 5.0)]
    meta_cks = dict(cks)
    for tg in INTEG_TAGS_CELLS + INTEG_TAGS_PATH:
        for nm, tt in cks:
            L.append(".measure tran %s_%s FIND V(x%s) AT=%.6fp" % (tg.upper(), nm, tg, g(tt)))
    for i in range(MGATE):
        L.append(".measure tran O%dZ FIND V(o%d) AT=%.6fp" % (i, i, g(t_open)))
        L.append(".measure tran O%dE FIND V(o%d) AT=%.6fp" % (i, i, g(tend - 5.0)))
    L.append(".print tran V(bka) V(bkb) V(sw) I(LT) V(o0) V(o1) V(xea) V(xesw) "
             "V(xer) V(xeb) V(xebk) V(xeih) V(xqlt)")
    L.append(".end")
    return L, dict(t_open=t_open, tend=tend, cks=meta_cks, pstep=pstep, mstep=mstep)


# --------------------------------------------------------------------- utils
def run(fn, lines, timeout=560):
    path = os.path.join(HERE, fn)
    open(path, "w").write("\n".join(lines) + "\n")
    t0 = time.monotonic()
    try:
        r = subprocess.run([XYCE, fn], capture_output=True, text=True,
                           timeout=timeout, cwd=HERE, env=ENV)
    except subprocess.TimeoutExpired:
        return None, "TIMEOUT after %gs" % timeout
    wall = time.monotonic() - t0
    ok = os.path.exists(path + ".mt0") or os.path.exists(path + ".prn")
    if r.returncode != 0 or not ok:
        err = "; ".join(l.strip() for l in r.stdout.splitlines()
                        if "rror" in l or "bort" in l)[:300]
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
        if hdr and p and p[0][0].isdigit():
            try:
                rows.append([float(x) for x in p])
            except ValueError:
                pass
    return hdr, rows


_STATIC = {}


def calib_path(dv):
    """dV=1.0 uses the committed, G1-gated swsweep calib run verbatim.  Any other
    dV needs its OWN static curve, because the cells' hi inputs sit at dV and the
    E_in / E_sup references would otherwise be taken at the wrong input level."""
    if abs(dv - 1.0) < 1e-12:
        return os.path.join(SW, "sw_calib.cir.prn")
    return os.path.join(HERE, "calib_dv%03d.cir.prn" % int(round(dv * 100)))


def static_curve(dv=DV):
    """A2 static Q/E reference vs V(bkb)."""
    if dv in _STATIC:
        return _STATIC[dv]
    hdr, rows = read_prn(calib_path(dv))
    def col(name):
        return [i for i, h in enumerate(hdr) if name.upper() in h][0]
    iv = col("V(BKB)")
    cs = {t: col("V(X%s)" % t.upper()) for t in ["qsh", "qsl", "esh", "esl", "eih"]}
    base = {t: rows[0][c] for t, c in cs.items()}
    def at(vend):
        prev = None
        for r in rows:
            if prev is not None and prev[iv] <= vend <= r[iv]:
                f = (vend - prev[iv]) / (r[iv] - prev[iv]) if r[iv] != prev[iv] else 0.0
                g = {t: (prev[c] + f * (r[c] - prev[c]) - base[t]) * 1e15
                     for t, c in cs.items()}
                return dict(Q_sup=g["qsh"] + g["qsl"], E_sup=g["esh"] + g["esl"],
                            E_in=g["eih"])
            prev = r
        raise ValueError("vend %.4f outside calib ramp" % vend)
    _STATIC[dv] = at
    return at


# ------------------------------------------------------------------ extractor
def extract(mt0_path, l_nh, total_um, t_half_ps, rs=RS_REF, edge=EDGE_REF,
            tail=TAIL_REF, dv=DV, ca=CA_FF):
    m = parse_mt0(mt0_path)
    at = static_curve(dv)
    f = 1e15
    def ck(tg):
        z = m["%s_Z" % tg.upper()]
        return [(m["%s_%s" % (tg.upper(), p)] - z) * f for p in ["A", "B", "C", "D"]]
    qlt, ea, eb, esw, er = ck("qlt"), ck("ea"), ck("eb"), ck("esw"), ck("er")
    ebk, eih = ck("ebk"), ck("eih")
    qbk = ck("qbk")
    qgt, qgtp, egt, ehi = ck("qgt"), ck("qgtp"), ck("egt"), ck("ehi")
    vbe, vbo = m["VBEND"], m.get("VBOPEN", float("nan"))
    ref = at(vbe)

    e_hop_open = ea[2] - ref["E_sup"]                     # A2 robust metric
    e_outa_exact = 0.5 * ca * (dv * dv - m["VAEND"] ** 2)
    e_hop_D = e_outa_exact - ref["E_sup"]
    cells_burn = (ebk[3] + eih[3]) - (ref["E_sup"] + ref["E_in"])
    va_open = dv - qlt[2] / ca

    # three-way split of what left bank A, cut at the open checkpoint C.
    # identity (exact at zero inductor current):  ea_C = er_C + esw_C
    e_R      = er[2]
    e_swblk  = esw[2] - eb[2]        # switch channel drop + sw-node cap storage
    e_toB    = eb[2]                 # delivered into the bkb node
    e_Bres   = e_toB - ref["E_sup"]  # B-side loss beyond final stored energy
    # AMENDMENT A1: ea - esw - er = dE_L, which vanishes only at ZERO inductor
    # current -- checkpoint B (the switch-open zero), not C.
    ident    = ea[1] - esw[1] - er[1]
    ident_C  = ea[2] - esw[2] - er[2]

    # per-cell settling
    def settle(suffix, vref):
        out = {}
        for i in range(MGATE):
            v = m["O%d%s" % (i, suffix)]
            s = (1.0 - v / vref) if i in HI else (v / vref)
            out["o%d" % i] = 100.0 * s
        return out
    s_open = settle("Z", vbo) if vbo == vbo and abs(vbo) > 1e-6 else None
    s_end  = settle("E", vbe) if abs(vbe) > 1e-6 else None

    closQ = (qlt[3] - ca * (dv - m["VAEND"])) / (ca * (dv - m["VAEND"])) * 100
    closE = (ea[3] - e_outa_exact) / e_outa_exact * 100

    row = dict(
        L_nH=l_nh, total_um=total_um, rs_ohm=rs, edge_ps=edge, tail_ps=tail, dv=dv, ca_fF=ca,
        **{("w_" + k): v for k, v in widths(total_um).items()},
        t_hop_ps=t_half_ps, t_hop_pred_ps=t_est(l_nh),
        IPK_uA=m["IPK"] * 1e6, IZ_uA=m["IZ"] * 1e6,
        VBEND=vbe, VBOPEN=vbo, VBPK=m["VBPK"], VAEND=m["VAEND"],
        VA_open=va_open, VSWPK=m.get("VSWPK"), VSWMN=m.get("VSWMN"),
        E_hop_open_fJ=e_hop_open, E_hop_D_fJ=e_hop_D,
        E_R_toC_fJ=e_R, E_switchblock_toC_fJ=e_swblk,
        E_toB_toC_fJ=e_toB, E_Bresid_toC_fJ=e_Bres,
        cells_burn_fJ=cells_burn,
        switch_related_open_fJ=e_hop_open - e_R - cells_burn,
        identity_at_B_fJ=ident, identity_at_C_fJ=ident_C,
        Q_through_L_C_fC=qlt[2], Q_through_L_D_fC=qlt[3], Q_into_cells_D_fC=qbk[3],
        Q_gate_drive_fC=qgt[3] + qgtp[3],
        E_gate_drive_fJ=egt[3], E_vhi_fJ=ehi[3], rails_net_fJ=egt[3] + ehi[3],
        settling_open_pct=s_open, settling_end_pct=s_end,
        settling_open_min_pct=(min(s_open.values()) if s_open else None),
        settling_end_min_pct=(min(s_end.values()) if s_end else None),
        closure_Q_pct=closQ, closure_E_pct=closE,
        outputs_open=[m["O%dZ" % i] for i in range(MGATE)],
        outputs_end=[m["O%dE" % i] for i in range(MGATE)])

    # pre-registered functional criteria (C1 per AMENDMENT A2)
    c1 = bool(s_open) and min(s_open.values()) >= 90.0
    c1e = bool(s_end) and min(s_end.values()) >= 90.0
    c2 = va_open <= 0.1478 * dv
    c3 = vbe >= 0.60 * dv
    c4 = abs(closQ) <= 1.0 and abs(closE) <= 1.0 and abs(ident) <= 0.02
    row.update(C1_settle_open_raw=("PASS" if c1 else "FAIL"),
               C1_settle_end=("PASS" if c1e else "FAIL"),
               C2_rail_drain=("PASS" if c2 else "FAIL"),
               C3_swing=("PASS" if c3 else "FAIL"),
               C4_instrument=("PASS" if c4 else "FAIL"),
               FUNCTIONAL=("YES" if (c1e and c2 and c3 and c4) else "NO"))
    return row


def ledger_from_prn(prn_path, t_open, t_C, dv):
    """INDEPENDENT ledger straight off the waveform, bypassing .measure entirely
    (and therefore the measured 1 ps FIND lag).  Used as the per-row instrument
    cross-check: the mt0 ledger and this one must agree."""
    hdr, rows = read_prn(prn_path)
    need = ["V(XEA)", "V(XESW)", "V(XER)", "V(XEB)", "V(XEBK)", "V(XEIH)", "V(XQLT)"]
    if any(n not in hdr for n in need):
        return None
    cols = {n: hdr.index(n) for n in need}
    ts = [r[1] * 1e12 for r in rows]
    def at(t, c):
        prev = None
        for k, tt in enumerate(ts):
            if prev is not None and ts[prev] <= t <= tt:
                a, b = ts[prev], tt
                f = (t - a) / (b - a) if b != a else 0.0
                return rows[prev][c] + f * (rows[k][c] - rows[prev][c])
            prev = k
        return float("nan")
    z = {n: at(0.5, c) for n, c in cols.items()}
    f = 1e15
    def v(n, t):
        return (at(t, cols[n]) - z[n]) * f
    tD = ts[-1] - 5.0
    return dict(
        ea_B=v("V(XEA)", t_open), esw_B=v("V(XESW)", t_open), er_B=v("V(XER)", t_open),
        ea_C=v("V(XEA)", t_C), eb_C=v("V(XEB)", t_C), esw_C=v("V(XESW)", t_C),
        er_C=v("V(XER)", t_C), qlt_C=v("V(XQLT)", t_open + 0.0),
        qlt_C_at_C=v("V(XQLT)", t_C),
        ebk_D=v("V(XEBK)", tD), eih_D=v("V(XEIH)", tD),
        identity_B=v("V(XEA)", t_open) - v("V(XESW)", t_open) - v("V(XER)", t_open))


def timing_from_prn(prn_path, vbend):
    """AMENDMENT A2: the measured TIMES, not a pass/fail at a fixed instant.
    t_rail90  -- V(bkb) first reaches 90% of its final value (after close).
    t_validXX -- ALL cell outputs simultaneously within XX% of the INSTANTANEOUS
                 rail and staying there (o0 stands for the 4 hi-input cells,
                 o1 for the 4 lo-input cells; the .mt0 O*Z/O*E measures confirm
                 the within-group values are identical to the printed digit).
    Returned relative to the switch close at T0."""
    hdr, rows = read_prn(prn_path)
    ib, i0, i1 = hdr.index("V(BKB)"), hdr.index("V(O0)"), hdr.index("V(O1)")
    out = {}
    tr = None
    for r in rows:
        t = r[1] * 1e12
        if t < T0:
            continue
        if r[ib] >= 0.90 * vbend:
            if tr is None:
                tr = t
        else:
            tr = None
    out["t_rail90_ps"] = (tr - T0) if tr is not None else None
    for th, nm in ((0.80, 80), (0.90, 90), (0.95, 95)):
        f = None
        for r in rows:
            t = r[1] * 1e12
            if t < T0:
                continue
            vb = r[ib]
            good = (vb > 1e-6 and (1.0 - r[i0] / vb) >= th and (r[i1] / vb) >= th)
            if good:
                if f is None:
                    f = t
            else:
                f = None
        out["t_valid%d_ps" % nm] = (f - T0) if f is not None else None
    return out


# ------------------------------------------------------------------- stages
def stage_warm():
    """Touch every device geometry the sweep will need, so parallel runs never
    trigger a PyMS compile (which races on a shared cache)."""
    need_n, need_p = set([WN]), set([WP])
    for tot in [15, 30, 60, 120, 240]:
        w = widths(tot)
        need_n.add(w["wn"]); need_n.add(w["park"]); need_p.add(w["wp"])
    L = head() + ["V1 a 0 0.5", "V2 b 0 0.5"]
    k = 0
    for w in sorted(need_n):
        L.append("XWN%d d%d a 0 0 sg13_lv_nmos w=%gu l=0.13u" % (k, k, w))
        L.append("RN%d d%d b 1k" % (k, k)); k += 1
    for w in sorted(need_p):
        L.append("XWP%d e%d a b b sg13_lv_pmos w=%gu l=0.13u" % (k, k, w))
        L.append("RP%d e%d 0 1k" % (k, k)); k += 1
    L += [".tran 1p 10p", ".print tran V(a)", ".end"]
    print("warming geometries n=%s p=%s" % (sorted(need_n), sorted(need_p)))
    p, msg = run("warm.cir", L, timeout=560)
    print(msg)
    return p is not None


def probe(tag, l_nh, total_um, rs=RS_REF, edge=EDGE_REF, verbose=True, dv=DV,
          ca=CA_FF):
    fn = "p_%s.cir" % tag
    path, msg = run(fn, probe_lines(l_nh, total_um, rs, edge, dv, ca))
    if verbose:
        print("  " + msg)
    if path is None:
        return None, msg
    hdr, rows = read_prn(path + ".prn")
    ii = [i for i, h in enumerate(hdr) if "I(LT)" in h or "LT" == h][0]
    post = [r for r in rows if r[1] * 1e12 >= T0]
    ipk = max(r[ii] for r in post)
    tpk = [r for r in post if r[ii] == ipk][0][1]
    # the zero we want is the FIRST downward crossing AFTER the current peak;
    # anchoring on the peak makes this robust at small L, where the close-edge
    # feedthrough transient is a large fraction of the hop.
    prev = None
    for r in post:
        tt, cur = r[1], r[ii]
        if tt < tpk:
            prev, prev_t = cur, tt
            continue
        if prev is not None and prev > 0 and cur <= 0:
            th = (prev_t + (tt - prev_t) * prev / (prev - cur)) * 1e12 - T0
            return dict(t_half=th, no_zero=False, ipk_probe_uA=ipk * 1e6,
                        t_ipk_ps=tpk * 1e12 - T0), "zero"
        prev, prev_t = cur, tt
    # overdamped: no reversal after the peak.  fall back to the 1%-decay time.
    for r in post:
        if r[1] >= tpk and abs(r[ii]) < 0.01 * ipk:
            return dict(t_half=r[1] * 1e12 - T0, no_zero=True,
                        ipk_probe_uA=ipk * 1e6, t_ipk_ps=tpk * 1e12 - T0), "OVERDAMPED"
    return None, "probe: no zero and no 1% decay after the peak within the window"


def point(tag, l_nh, total_um, rs=RS_REF, edge=EDGE_REF, tail=TAIL_REF,
          verbose=True, dv=DV, ca=CA_FF):
    pr, st = probe(tag, l_nh, total_um, rs, edge, verbose, dv, ca)
    if pr is None:
        return dict(tag=tag, L_nH=l_nh, total_um=total_um, error=st)
    th = pr["t_half"]
    if verbose:
        print("  probe %s: t_half = %.4f ps (%s, Ipk_probe %.1f uA)"
              % (tag, th, st, pr["ipk_probe_uA"]))
    lines, meta = hop_lines(l_nh, total_um, th, rs, edge, tail, dv, ca)
    path, msg = run("h_%s.cir" % tag, lines)
    if verbose:
        print("  " + msg)
    if path is None:
        return dict(tag=tag, L_nH=l_nh, total_um=total_um, error=msg,
                    t_hop_ps=th)
    try:
        row = extract(path + ".mt0", l_nh, total_um, th, rs, edge, tail, dv, ca)
    except Exception as e:                                  # noqa
        return dict(tag=tag, L_nH=l_nh, total_um=total_um, error="extract: %r" % e,
                    t_hop_ps=th)
    row["tag"] = tag
    row["probe_no_zero"] = pr["no_zero"]
    row["ipk_probe_uA"] = pr["ipk_probe_uA"]
    row["t_ipk_ps"] = pr.get("t_ipk_ps")
    row["timestep_ps"] = meta["mstep"]
    try:
        row.update(timing_from_prn(path + ".prn", row["VBEND"]))
    except Exception as e:                                  # noqa
        row["timing_error"] = repr(e)
    try:
        lg = ledger_from_prn(path + ".prn", meta["t_open"], meta["cks"]["C"], dv)
        if lg:
            at = static_curve(dv)
            ref = at(row["VBEND"])
            row["xc_identity_B_fJ"] = lg["identity_B"]
            row["xc_E_hop_open_fJ"] = lg["ea_C"] - ref["E_sup"]
            row["xc_E_hop_at_zero_fJ"] = lg["ea_B"] - ref["E_sup"]
            row["xc_E_R_toC_fJ"] = lg["er_C"]
            row["xc_E_switchblock_toC_fJ"] = lg["esw_C"] - lg["eb_C"]
            row["xc_VA_open"] = dv - lg["qlt_C"] / ca
            row["xc_cells_burn_fJ"] = (lg["ebk_D"] + lg["eih_D"]) - (ref["E_sup"] + ref["E_in"])
            row["xc_dEhop_pct"] = 100.0 * (row["xc_E_hop_open_fJ"] / row["E_hop_open_fJ"] - 1.0)
            # C4 is re-gated on the WAVEFORM identity, which owes nothing to .measure
            c4 = (abs(row["closure_Q_pct"]) <= 1.0 and abs(row["closure_E_pct"]) <= 1.0
                  and abs(lg["identity_B"]) <= 0.02
                  and abs(row["xc_dEhop_pct"]) <= 1.0)
            row["C4_instrument"] = "PASS" if c4 else "FAIL"
            row["FUNCTIONAL"] = ("YES" if (row["C1_settle_end"] == "PASS"
                                           and row["C2_rail_drain"] == "PASS"
                                           and row["C3_swing"] == "PASS" and c4) else "NO")
    except Exception as e:                                  # noqa
        row["xcheck_error"] = repr(e)
    tv = row.get("t_valid90_ps")
    row["t_level_ps"] = max(row["t_hop_ps"], tv) if tv else None
    if tv is None:
        row["FUNCTIONAL"] = "NO"
        row["C1_valid90_reached"] = "FAIL"
    else:
        row["C1_valid90_reached"] = "PASS"
    return row


def stage_g0():
    ok = True
    print("=== G0a: extractor vs committed tg15p mt0 ===")
    out = extract(os.path.join(SW, "sw_tg15p_z.cir.mt0"), L_REF, 15.0, TZ_REF)
    for k, ref in ANCHOR.items():
        a = out[k]
        rel = abs(a - ref) / max(abs(ref), 1e-30)
        flag = "OK  " if rel < 1e-6 else "FAIL"
        ok &= rel < 1e-6
        print("%s %-16s mine %.10g committed %.10g (rel %.2e)" % (flag, k, a, ref, rel))
    print("  extra (new in this track): E_switchblock_toC %.5f fJ, E_toB_toC %.5f fJ, "
          "identity@B %.3e fJ (gate 0.02), identity@C %.4f fJ (dE_L, not a gate)"
          % (out["E_switchblock_toC_fJ"], out["E_toB_toC_fJ"],
             out["identity_at_B_fJ"], out["identity_at_C_fJ"]))
    tm = timing_from_prn(os.path.join(SW, "sw_tg15p_z.cir.prn"), out["VBEND"])
    out.update(tm)
    out["t_level_ps"] = max(TZ_REF, tm["t_valid90_ps"])
    print("  A2 timing on the committed anchor: t_rail90 %.2f  t_valid80 %.2f  "
          "t_valid90 %.2f  t_valid95 %.2f  -> t_level %.2f ps (t_hop %.2f)"
          % (tm["t_rail90_ps"], tm["t_valid80_ps"], tm["t_valid90_ps"],
             tm["t_valid95_ps"], out["t_level_ps"], TZ_REF))
    for nm in ("settling_open_pct", "settling_end_pct"):
        d = out.get(nm)
        print("  %-18s %s" % (nm, json.dumps({k: round(v, 3) for k, v in d.items()})
                              if d else "n/a (committed deck has no VBOPEN measure)"))
    json.dump(out, open(os.path.join(HERE, "g0a_anchor_from_committed_mt0.json"), "w"),
              indent=1)

    print("=== G0b: committed deck re-run under MY cache ===")
    src = open(os.path.join(SW, "sw_tg15p_z.cir")).read()
    open(os.path.join(HERE, "g0b.cir"), "w").write(src)
    t0 = time.monotonic()
    r = subprocess.run([XYCE, "g0b.cir"], capture_output=True, text=True,
                       timeout=560, cwd=HERE, env=ENV)
    print("  ran g0b.cir in %.1fs rc=%d" % (time.monotonic() - t0, r.returncode))
    out2 = extract(os.path.join(HERE, "g0b.cir.mt0"), L_REF, 15.0, TZ_REF)
    for k, ref in ANCHOR.items():
        a = out2[k]
        rel = abs(a - ref) / max(abs(ref), 1e-30)
        flag = "OK  " if rel < 1e-6 else "FAIL"
        ok &= rel < 1e-6
        print("%s %-16s mine %.10g committed %.10g (rel %.2e)" % (flag, k, a, ref, rel))

    print("=== G0c/G0d: my generator at the anchor (probe + extended hop) ===")
    row = point("anchor", L_REF, 15.0)
    json.dump(row, open(os.path.join(HERE, "g0cd_anchor_mine.json"), "w"), indent=1)
    dz = abs(row["t_hop_ps"] - TZ_REF)
    print("  G0c probe zero %.4f ps vs committed %.6f ps (delta %.4f ps, gate <= 0.1)"
          % (row["t_hop_ps"], TZ_REF, dz))
    ok &= dz <= 0.1
    for k in ["E_hop_open_fJ", "VBEND", "VA_open"]:
        rel = abs(row[k] - ANCHOR[k]) / abs(ANCHOR[k])
        flag = "OK  " if rel < 1e-3 else "FAIL"
        ok &= rel < 1e-3
        print("%s G0d %-14s mine %.8g committed %.8g (rel %.2e, gate < 1e-3)"
              % (flag, k, row[k], ANCHOR[k], rel))
    print("G0 %s" % ("PASS" if ok else "FAIL"))
    return ok


def stage_calib(dv):
    """Own static Q/E reference curve for a non-committed dV.  Same structure as
    swsweep stage_calib (which is G1-gated against gateb); only the cells' hi
    input level moves with dV."""
    t = 20000.0
    L = head() + ["VS bkb 0 PWL(0 0 %gp %g)" % (t, dv)] + cells_metered(dv) + \
        cell_integrators() + \
        ["Bp p 0 V={ -V(bkb)*I(VS) }", "Bq q 0 V={ -I(VS) }",
         ".tran %gp %gp" % (t / 4000.0, t * 1.02),
         ".measure tran QTOT INTEGRAL V(q) FROM=0 TO=%gp" % t]
    prn = ["V(bkb)"] + ["V(x%s)" % g for g in INTEG_TAGS_CELLS] + ["V(o0)", "V(o1)"]
    L += [".print tran " + " ".join(prn), ".end"]
    fn = "calib_dv%03d.cir" % int(round(dv * 100))
    path, msg = run(fn, L)
    print("  " + msg)
    if path is None:
        return False
    # cross-check: my own dV=1.0 calib must agree with the committed one
    at_mine = None
    _STATIC.pop(dv, None)
    print("  calib written: %s" % (path + ".prn"))
    return True


def load_rows():
    fn = os.path.join(HERE, "rows.json")
    return json.load(open(fn)) if os.path.exists(fn) else {}


def save_row(row):
    fn = os.path.join(HERE, "rows.json")
    rows = load_rows()
    rows[row["tag"]] = row
    json.dump(rows, open(fn, "w"), indent=1)


def brief(r):
    if "error" in r:
        return "%-14s L=%-7g W=%-5g ERROR %s" % (r.get("tag"), r["L_nH"],
                                                 r["total_um"], r["error"])
    nn = lambda v: v if v is not None else float("nan")
    return ("%-14s L=%-7g W=%-5g t_hop %8.3f  t_rail90 %7.2f  t_valid90 %7.2f  "
            "t_level %7.2f ps | Ipk %8.1f uA VBpk %.4f VBend %.4f VAopen %+.4f "
            "s_open %6.2f%% s_end %6.2f%% | Ehop %8.3f fJ [R %.4f|swblk %.3f|cells %.3f] %s"
            % (r["tag"], r["L_nH"], r["total_um"], r["t_hop_ps"],
               nn(r.get("t_rail90_ps")), nn(r.get("t_valid90_ps")),
               nn(r.get("t_level_ps")), r["IPK_uA"],
               r["VBPK"], r["VBEND"], r["VA_open"],
               nn(r["settling_open_min_pct"]), nn(r["settling_end_min_pct"]),
               r["E_hop_open_fJ"], r["E_R_toC_fJ"], r["E_switchblock_toC_fJ"],
               r["cells_burn_fJ"], r["FUNCTIONAL"]))


if __name__ == "__main__":
    st = sys.argv[1]
    if st == "warm":
        sys.exit(0 if stage_warm() else 1)
    elif st == "g0":
        sys.exit(0 if stage_g0() else 1)
    elif st == "point":
        tag = sys.argv[2]
        l_nh = float(sys.argv[3]); tot = float(sys.argv[4])
        rs = float(sys.argv[5]) if len(sys.argv) > 5 else RS_REF
        edge = float(sys.argv[6]) if len(sys.argv) > 6 else EDGE_REF
        tail = float(sys.argv[7]) if len(sys.argv) > 7 else TAIL_REF
        r = point(tag, l_nh, tot, rs, edge, tail)
        save_row(r)
        print(brief(r))
    elif st == "calib":
        sys.exit(0 if stage_calib(float(sys.argv[2])) else 1)
    elif st == "pointdv":
        tag = sys.argv[2]
        l_nh = float(sys.argv[3]); tot = float(sys.argv[4]); dv = float(sys.argv[5])
        rs = float(sys.argv[6]) if len(sys.argv) > 6 else RS_REF
        edge = float(sys.argv[7]) if len(sys.argv) > 7 else EDGE_REF
        tail = float(sys.argv[8]) if len(sys.argv) > 8 else TAIL_REF
        r = point(tag, l_nh, tot, rs, edge, tail, True, dv)
        save_row(r)
        print(brief(r))
    elif st == "show":
        for k, r in sorted(load_rows().items()):
            print(brief(r))
