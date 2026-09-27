#!/usr/bin/env python3
"""TRACK 2: switch-design sweep of the committed iso-current hop (dV=1.0,
L=277.8 nH), adapted from gateb/qal_hop_meter.py with the transfer switch
PARAMETERIZED (TG width sweep at 1:2 n:p, nMOS-only, reduced-pMOS TG).

Everything else -- cells, metering, integrators, options, timing structure --
is the gateb harness verbatim.  Pre-registration: swsweep/PRE_REGISTERED_SWEEP.json.

Stages: calib -> per design (probe -> hop) -> report.
"""
import json, math, os, re, subprocess, sys, time

HERE  = os.path.dirname(os.path.abspath(__file__))
XYCE  = "/usr/local/src/xyce-build/src/Xyce"
VA    = "/usr/local/share/xyce/verilog-a/psp103/psp103.va"
MODEL = "/usr/local/src/kestrel/sim/models/sg13g2_psp103_tt.lib"
SHIM  = "/usr/local/src/stat-sim/qal/sg13lv_compat.sp"
CACHE = os.environ.get("PYMS_VAE_CACHE") or \
    "/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6/scratchpad/vae_cache_track2"
ENV = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS", PYMS_VAE_CACHE=CACHE)

DV, L_NH, RS = 1.0, 277.8, 10.0
VGH          = 1.5
WP, WN       = 1.12, 0.74
MGATE, CLOAD = 8, 2.0
CA_FF        = 35.979          # committed C_eff at dV=1.0 (qal_isocurrent.json)
T0           = 50.0            # ps, switch closes
VCHK = [0.167, 0.333, 0.5, 0.667, 0.833, 0.917, 1.0]   # committed checkpoints

HI = [i for i in range(MGATE) if i % 2 == 0]
LO = [i for i in range(MGATE) if i % 2 == 1]

# ------------------------------------------------------------ switch designs
# topo: "tg" (nMOS+pMOS), "nmos" (nMOS only). wn/wp in um.
DESIGNS = {
    "tg60":  dict(topo="tg",   wn=20.0, wp=40.0),   # committed baseline
    "tg30":  dict(topo="tg",   wn=10.0, wp=20.0),
    "tg15":  dict(topo="tg",   wn=5.0,  wp=10.0),
    "tg7p5": dict(topo="tg",   wn=2.5,  wp=5.0),
    "nm40":  dict(topo="nmos", wn=40.0, wp=0.0),
    "nm20":  dict(topo="nmos", wn=20.0, wp=0.0),
    "nm10":  dict(topo="nmos", wn=10.0, wp=0.0),
    "nm5":   dict(topo="nmos", wn=5.0,  wp=0.0),
    "tgap":  dict(topo="tg",   wn=10.0, wp=5.0),    # reduced-pMOS TG
    "tg120": dict(topo="tg",   wn=40.0, wp=80.0),   # upper bracket
    # park variants: small nMOS clamps node sw to 0 AFTER the switch opens
    # (own control phase pk: 0 throughout the transfer, 1.5 from open+2ps).
    # First attempt tied the park gate to gtp -- WRONG: gtp is high BEFORE the
    # hop, so the park shorted bank A through L pre-close (~170uA pre-current,
    # bogus ~100ps zeros, 2 Xyce aborts). w=1u: Ron~600 ohm damps the residual
    # A-side ring (critical ~5.5k) with ~19mV excursion on sw at ~32uA ring.
    "tg30p":  dict(topo="tg", wn=10.0, wp=20.0, park=1.0),
    "tg15p":  dict(topo="tg", wn=5.0,  wp=10.0, park=1.0),
    "tg7p5p": dict(topo="tg", wn=2.5,  wp=5.0,  park=1.0),
}


def head():
    return ['.hdl "%s"' % VA, '.include "%s"' % MODEL, '.include "%s"' % SHIM,
            '.OPTIONS TIMEINT METHOD=GEAR RELTOL=1e-6 ABSTOL=1e-15 CHGTOL=1e-17']


def switch_lines(design):
    """Transfer switch between node sw (path side) and bkb (bank side).
    Gate-drive sources VGT/VGTP and body rail VHI are ALWAYS present so the
    path integrators' expressions stay well-defined; for nmos-only the pMOS
    is simply absent (I(VGTP), I(VHI) then integrate leakage-free zeros
    through the 1G keepers)."""
    d = DESIGNS[design]
    L = ["XSWN sw gt bkb 0 sg13_lv_nmos w=%gu l=0.13u" % d["wn"]]
    if d["topo"] == "tg":
        L.append("XSWP sw gtp bkb vhi sg13_lv_pmos w=%gu l=0.13u" % d["wp"])
    else:
        L += ["RKGTP gtp 0 1e9", "RKVHI vhi 0 1e9"]
    if d.get("park"):
        L.append("XPK sw pk 0 0 sg13_lv_nmos w=%gu l=0.13u" % d["park"])
    return L


def park_ctrl(design, t_open_ps=None):
    """Park control source: held at 0 in the probe (t_open None) and until
    the switch opens in the hop; 1.5 from open+2ps."""
    if not DESIGNS[design].get("park"):
        return []
    if t_open_ps is None:
        return ["VPK pk 0 0"]
    return ["VPK pk 0 PWL(0 0 %gp 0 %gp %g)" % (t_open_ps + 2, t_open_ps + 4, VGH)]


def cells_metered(pinned=False, supply="bkb"):
    """gateb verbatim: 8 inverters, pMOS S/B directly on the bank node
    (no meter may touch bkb -- Xyce silently drops .ic on V-source nodes)."""
    L = ["VMGH gnh 0 0", "VMGL gnl 0 0"]
    if pinned:
        L += ["VPPH pinph 0 1.2", "VPPL pinpl 0 1.2",
              "VPNH pinnh 0 0",   "VPNL pinnl 0 0"]
    for i in range(MGATE):
        gnd = "gnh" if i in HI else "gnl"
        if pinned:
            gp = "pinph" if i in HI else "pinpl"
            gn = "pinnh" if i in HI else "pinnl"
        else:
            L.append("VI%d in%d 0 %g" % (i, i, DV if i in HI else 0.0))
            gp = gn = "in%d" % i
        L.append("XP%d o%d %s %s %s sg13_lv_pmos w=%gu l=0.13u" % (i, i, gp, supply, supply, WP))
        L.append("XN%d o%d %s %s %s sg13_lv_nmos w=%gu l=0.13u" % (i, i, gn, gnd, gnd, WN))
        L.append("CL%d o%d %s %gf" % (i, i, gnd, CLOAD))
    return L


def _sup_expr(group, pinned):
    if pinned:
        vg = "I(VMGH)" if group == "H" else "I(VMGL)"
        pins = ("I(VPPH)+I(VPNH)") if group == "H" else ("I(VPPL)+I(VPNL)")
        return "%s+%s" % (vg, pins)
    idx = HI if group == "H" else LO
    vg = "I(VMGH)" if group == "H" else "I(VMGL)"
    return vg + "+" + "+".join("I(VI%d)" % i for i in idx)


def integ(tag, expr):
    return ["CX%s x%s 0 1" % (tag, tag), "BX%s 0 x%s I={ %s }" % (tag, tag, expr),
            "RX%s x%s 0 0.01" % (tag, tag)]


def cell_integrators(pinned=False, supply="bkb"):
    L = []
    sh, sl = _sup_expr("H", pinned), _sup_expr("L", pinned)
    L += integ("qsh", sh) + integ("qsl", sl)
    L += integ("esh", "V(%s)*(%s)" % (supply, sh)) + integ("esl", "V(%s)*(%s)" % (supply, sl))
    L += integ("qgh", "I(VMGH)") + integ("qgl", "I(VMGL)")
    if pinned:
        L += integ("qih", "-(I(VPPH)+I(VPPL))")
        L += integ("eih", "-1.2*(I(VPPH)+I(VPPL))")
        L += integ("qil", "-(I(VPNH)+I(VPNL))")
    else:
        L += integ("qih", "-(" + "+".join("I(VI%d)" % i for i in HI) + ")")
        L += integ("eih", "-(" + "+".join("V(in%d)*I(VI%d)" % (i, i) for i in HI) + ")")
        L += integ("qil", "-(" + "+".join("I(VI%d)" % i for i in LO) + ")")
    return L


INTEG_TAGS_CELLS = ["qsh", "qsl", "esh", "esl", "qgh", "qgl", "qih", "eih", "qil"]
INTEG_TAGS_PATH  = ["qlt", "ea", "eb", "qbk", "ebk", "er", "esw", "qgt", "qgtp",
                    "qhi", "egt", "ehi"]


def path_integrators(pinned=False, park=False):
    L = []
    L += integ("qlt", "I(LT)") + integ("ea", "V(bka)*I(LT)") + integ("eb", "V(bkb)*I(LT)")
    tot = "(%s)+(%s)" % (_sup_expr("H", pinned), _sup_expr("L", pinned))
    L += integ("qbk", tot) + integ("ebk", "V(bkb)*(%s)" % tot)
    L += integ("er", "I(LT)*I(LT)*%g" % RS)
    L += integ("esw", "V(sw)*I(LT)")
    L += integ("qgt", "-I(VGT)") + integ("qgtp", "-I(VGTP)") + integ("qhi", "-I(VHI)")
    egt = "-V(gt)*I(VGT)-V(gtp)*I(VGTP)"
    if park:
        egt += "-V(pk)*I(VPK)"     # park drive energy books into egt
    L += integ("egt", egt)
    L += integ("ehi", "-%g*I(VHI)" % VGH)
    return L


def run(fn, lines, timeout=580):
    path = os.path.join(HERE, fn)
    open(path, "w").write("\n".join(lines) + "\n")
    t0 = time.monotonic()
    r = subprocess.run([XYCE, fn], capture_output=True, text=True,
                       timeout=timeout, cwd=HERE, env=ENV)
    wall = time.monotonic() - t0
    ok = os.path.exists(path + ".mt0") or os.path.exists(path + ".prn")
    if r.returncode != 0 or not ok:
        err = "; ".join(l.strip() for l in r.stdout.splitlines()
                        if "rror" in l or "bort" in l)[:400]
        print("XYCE FAILED %s (%.1fs): %s" % (fn, wall, err or r.stdout[-400:]))
        sys.exit(1)
    print("  ran %s in %.1fs" % (fn, wall))
    return path


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


# ---------------------------------------------------------------- stage: calib
def stage_calib():
    t = 20000.0
    L = head() + ["VS bkb 0 PWL(0 0 %gp %g)" % (t, DV)] + cells_metered() + \
        cell_integrators() + \
        ["Bp p 0 V={ -V(bkb)*I(VS) }", "Bq q 0 V={ -I(VS) }",
         ".tran %gp %gp" % (t / 4000.0, t * 1.02)]
    for v in VCHK:
        nm = "E%03d" % int(round(v * 1000))
        L.append(".measure tran %s INTEGRAL V(p) FROM=0 TO=%gp" % (nm, t * v / DV))
    L.append(".measure tran QTOT INTEGRAL V(q) FROM=0 TO=%gp" % t)
    prn = ["V(bkb)"] + ["V(x%s)" % g for g in INTEG_TAGS_CELLS] + ["V(o0)", "V(o1)"]
    L.append(".print tran " + " ".join(prn))
    L.append(".end")
    run("sw_calib.cir", L)
    m = parse_mt0(os.path.join(HERE, "sw_calib.cir.mt0"))
    committed_E = dict(zip(VCHK, [0.337, 1.278, 5.562, 9.217, 13.745, 16.386, 19.232]))
    print("QTOT %.4f fC (committed 35.979, %+0.2f%%)"
          % (m["QTOT"] * 1e15, (m["QTOT"] * 1e15 / 35.979 - 1) * 100))
    for v in VCHK:
        nm = "E%03d" % int(round(v * 1000))
        e = m[nm] * 1e15
        print("E(V=%.3f) %.4f fJ (committed %.3f, %+0.2f%%)"
              % (v, e, committed_E[v], (e / committed_E[v] - 1) * 100))


# ---------------------------------------------------------------- stage: probe
def stage_probe(design):
    ca = CA_FF
    cser = (ca * ca / (2 * ca)) * 1e-15
    tend = 50.0 + 6.0 * math.pi * math.sqrt((L_NH * 1e-9) * cser) * 1e12
    L = head() + [
        ".param LT=%gn RS=%g CA=%gf" % (L_NH, RS, ca),
        "CA bka 0 {CA}",
        "VHI vhi 0 %g" % VGH,
        "VGT  gt  0 PWL(0 0 48p 0 50p %g %gp %g)" % (VGH, tend * 2, VGH),
        "VGTP gtp 0 PWL(0 %g 48p %g 50p 0 %gp 0)" % (VGH, VGH, tend * 2),
    ] + switch_lines(design) + park_ctrl(design) + [
        "LT bka mid {LT}", "RT mid sw {RS}",
    ] + cells_metered() + [
        ".ic V(bka)=%g V(bkb)=0" % DV,
        ".print tran I(LT) V(bkb) V(bka)",
        ".tran 0.1p %gp" % tend, ".end"]
    path = run("sw_%s_p.cir" % design, L)
    hdr, rows = read_prn(path + ".prn")
    ii = [i for i, h in enumerate(hdr) if "LT" in h][0]
    prev = None
    for r in rows:
        tt, cur = r[1], r[ii]
        if prev is not None and prev > 0 and cur <= 0 and tt > 60e-12:
            th = tt * 1e12 - T0
            print("probe zero: t_half = %.2f ps" % th)
            return th
        prev = cur
    print("probe: NO ZERO FOUND within %gp" % tend)
    return None


# ------------------------------------------------------------------ stage: hop
def hop_lines(design, t_half_ps):
    tend = T0 + t_half_ps + 500.0
    L = head() + [
        ".param LT=%gn RS=%g CA=%gf" % (L_NH, RS, CA_FF),
        "CA bka 0 {CA}",
        "VHI vhi 0 %g" % VGH,
        "VGT  gt  0 PWL(0 0 %gp 0 %gp %g %gp %g %gp 0)"
            % (T0 - 2, T0, VGH, T0 + t_half_ps, VGH, T0 + t_half_ps + 2),
        "VGTP gtp 0 PWL(0 %g %gp %g %gp 0 %gp 0 %gp %g)"
            % (VGH, T0 - 2, VGH, T0, T0 + t_half_ps, T0 + t_half_ps + 2, VGH),
    ] + switch_lines(design) + park_ctrl(design, T0 + t_half_ps) + [
        "LT bka mid {LT}", "RT mid sw {RS}",
    ] + cells_metered() + cell_integrators() + \
        path_integrators(park=bool(DESIGNS[design].get("park"))) + [
        "Bpa pa 0 V={ V(bka)*I(LT) }", "Bpb pb 0 V={ V(bkb)*I(LT) }",
        "Bqt qt 0 V={ I(LT) }",
        ".ic V(bka)=%g V(bkb)=0" % DV]
    L.append(".tran 0.1p %gp 0 0.25p" % tend)
    L += [".measure tran EOUTA INTEGRAL V(pa) FROM=0 TO=%gp" % tend,
          ".measure tran EINB  INTEGRAL V(pb) FROM=0 TO=%gp" % tend,
          ".measure tran QTR   INTEGRAL V(qt) FROM=0 TO=%gp" % tend,
          ".measure tran VBPK  MAX V(bkb) FROM=%gp TO=%gp" % (T0, tend),
          ".measure tran VBEND FIND V(bkb) AT=%gp" % (tend - 5),
          ".measure tran VAEND FIND V(bka) AT=%gp" % (tend - 5),
          ".measure tran IPK   MAX I(LT) FROM=0 TO=%gp" % tend,
          ".measure tran IZ    FIND I(LT) AT=%gp" % (T0 + t_half_ps)]
    cks = [("Z", 0.5), ("A", T0 + 5.0), ("B", T0 + t_half_ps),
           ("C", T0 + t_half_ps + 7.0), ("D", tend - 5.0)]
    for tag in INTEG_TAGS_CELLS + INTEG_TAGS_PATH:
        for nm, tt in cks:
            L.append(".measure tran %s_%s FIND V(x%s) AT=%gp" % (tag.upper(), nm, tag, tt))
    for i in range(MGATE):
        L.append(".measure tran O%dZ FIND V(o%d) AT=%gp" % (i, i, T0 + t_half_ps))
        L.append(".measure tran O%dE FIND V(o%d) AT=%gp" % (i, i, tend - 5.0))
    prn = ["V(bka)", "V(bkb)", "V(sw)", "I(LT)",
           "I(VMGH)", "I(VMGL)", "V(xqlt)", "V(xqbk)", "V(xqsh)", "V(xqsl)",
           "V(xqgh)", "V(xqgl)", "V(o0)", "V(o1)"]
    L.append(".print tran " + " ".join(prn))
    L.append(".end")
    return L, tend


def stage_hop(design, t_half_ps, suffix="h"):
    fn = "sw_%s_%s.cir" % (design, suffix)
    L, tend = hop_lines(design, t_half_ps)
    run(fn, L)
    print("%s done (tend=%gp)" % (fn, tend))


# --------------------------------------------------------------- stage: report
def static_curve():
    """Static Q/E references vs V(bkb) from the calib .prn (linear interp).
    Integrator nodes carry DC-op pre-charges at t=0 (e.g. V(XQSH) -80 fC,
    V(XEIH) +80 fC) -- subtract the t=0 baseline, same role as the hop's
    Z checkpoint."""
    hdr, rows = read_prn(os.path.join(HERE, "sw_calib.cir.prn"))
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
        raise ValueError("vend %.4f outside ramp" % vend)
    return at


def report(design, t_half_ps, suffix="h", key=None):
    m = parse_mt0(os.path.join(HERE, "sw_%s_%s.cir.mt0" % (design, suffix)))
    at = static_curve()
    f = 1e15
    def ck(tag):
        z = m["%s_Z" % tag.upper()]
        return [(m["%s_%s" % (tag.upper(), p)] - z) * f for p in ["A", "B", "C", "D"]]
    qlt, qbk = ck("qlt"), ck("qbk")
    ea, ebk, eih, er = ck("ea"), ck("ebk"), ck("eih"), ck("er")
    vbe, vae, vbp = m["VBEND"], m["VAEND"], m["VBPK"]
    ref = at(vbe)
    e_outa_exact = 0.5 * CA_FF * (DV * DV - vae * vae)
    e_hop = e_outa_exact - ref["E_sup"]
    cells_burn = (ebk[3] + eih[3]) - (ref["E_sup"] + ref["E_in"])
    sw_rel = e_hop - er[3] - cells_burn
    swq = dict(turn_on=qbk[0] - qlt[0],
               traverse=(qlt[1] - qlt[0]) - (qbk[1] - qbk[0]),
               turn_off=(qlt[2] - qlt[1]) - (qbk[2] - qbk[1]),
               hold_ring=(qlt[3] - qlt[2]) - (qbk[3] - qbk[2]),
               net=qlt[3] - qbk[3])
    d = DESIGNS[design]
    out = dict(design=design, topo=d["topo"], wn_um=d["wn"], wp_um=d["wp"],
               total_um=d["wn"] + d["wp"], t_zcs_ps=t_half_ps,
               IZ_uA=m["IZ"] * 1e6, IPK_uA=m["IPK"] * 1e6,
               VBPK=vbp, VBEND=vbe, VAEND=vae,
               E_outA_exact_fJ=e_outa_exact,
               E_sup_static_at_Vend_fJ=ref["E_sup"], E_in_static_at_Vend_fJ=ref["E_in"],
               Q_sup_static_at_Vend_fC=ref["Q_sup"],
               E_hop_fJ=e_hop, E_R_fJ=er[3], cells_burn_fJ=cells_burn,
               switch_related_fJ=sw_rel,
               Q_into_cells_D_fC=qbk[3], Q_through_L_D_fC=qlt[3],
               cells_excess_Q_fC=qbk[3] - ref["Q_sup"],
               switch_Q_per_phase_fC=swq,
               closure_Q_pct=(qlt[3] - CA_FF * (DV - vae)) / (CA_FF * (DV - vae)) * 100,
               closure_E_pct=(ea[3] - e_outa_exact) / e_outa_exact * 100,
               completeness="PASS" if 0.56479 <= vbe <= 0.58785 else "FAIL",
               outputs_end=[m["O%dE" % i] for i in range(MGATE)])
    fn = os.path.join(HERE, "sweep_rows.json")
    rows = json.load(open(fn)) if os.path.exists(fn) else {}
    rows[key or design] = out
    json.dump(rows, open(fn, "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    stage = sys.argv[1]
    if stage == "calib":
        stage_calib()
    elif stage == "probe":
        stage_probe(sys.argv[2])
    elif stage == "hop":
        stage_hop(sys.argv[2], float(sys.argv[3]))
    elif stage == "report":
        report(sys.argv[2], float(sys.argv[3]))
    elif stage == "full":
        # as-committed timing convention: switch opens at true zero + 50 ps
        # (every committed row carries this offset; tg60 at 342.0 = 291.34+50.66
        # reproduced the committed record exactly). True zero recorded per row.
        des = sys.argv[2]
        d = stage_probe(des)
        if d is None:
            sys.exit(2)
        t_open = d + T0
        stage_hop(des, t_open)
        report(des, t_open)
        fn = os.path.join(HERE, "sweep_rows.json")
        rows = json.load(open(fn))
        rows[des]["true_zero_ps"] = d
        rows[des]["timing_convention"] = "open at true zero + 50 ps (as committed)"
        json.dump(rows, open(fn, "w"), indent=1)
    elif stage == "zcsfull":
        # amended protocol end-to-end: probe, then open exactly at the zero
        des = sys.argv[2]
        d = stage_probe(des)
        if d is None:
            sys.exit(2)
        stage_hop(des, d, suffix="z")
        report(des, d, suffix="z", key=des + "_zcs")
        fn = os.path.join(HERE, "sweep_rows.json")
        rows = json.load(open(fn))
        rows[des + "_zcs"]["true_zero_ps"] = d
        rows[des + "_zcs"]["timing_convention"] = "TRUE ZCS: open at the probe zero"
        json.dump(rows, open(fn, "w"), indent=1)
    elif stage == "zcs":
        # PROTOCOL AMENDMENT (see AMENDMENT.md): true-ZCS run -- open exactly
        # at the design's own probe zero. Deck/mt0 kept separate (suffix z);
        # row keyed <design>_zcs.
        des, d = sys.argv[2], float(sys.argv[3])
        stage_hop(des, d, suffix="z")
        report(des, d, suffix="z", key=des + "_zcs")
        fn = os.path.join(HERE, "sweep_rows.json")
        rows = json.load(open(fn))
        rows[des + "_zcs"]["true_zero_ps"] = d
        rows[des + "_zcs"]["timing_convention"] = "TRUE ZCS: open at the probe zero"
        json.dump(rows, open(fn, "w"), indent=1)
