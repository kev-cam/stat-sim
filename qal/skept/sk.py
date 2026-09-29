#!/usr/bin/env python3
"""SKEPTIC harness -- independently written deck generator + WAVEFORM extractor.

Deliberately NOT importing lsw.py or sw_hop_meter.py: the topology is rebuilt from
the committed deck's netlist, and every SPEED number is taken from the .prn
waveform by my own code, so no speed claim can depend on .measure at all.

Stages:  i0  committed-deck re-run
         i2  .measure FIND AT= lag diagnostic
         pt <tag>   probe + hop for a named point
         rx  receiver DC sweep (trip points, contention current)
         comp <tag> composition: hop + 8 receivers on the real cell outputs
"""
import json, math, os, re, subprocess, sys, time

HERE  = "/usr/local/src/stat-sim/qal/skept"
XYCE  = "/usr/local/src/xyce-build/src/Xyce"
VA    = "/usr/local/share/xyce/verilog-a/psp103/psp103.va"
MODEL = "/usr/local/src/kestrel/sim/models/sg13g2_psp103_tt.lib"
SHIM  = "/usr/local/src/stat-sim/qal/sg13lv_compat.sp"
CACHE = "/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6/scratchpad/vae_cache_skept2"
ENV   = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS", PYMS_VAE_CACHE=CACHE)

# inherited committed constants
WP, WN = 1.12, 0.74
MGATE  = 8
CLOAD  = 2.0
CA_FF  = 35.979
T0     = 50.0
VGH    = 1.5
RS     = 10.0
EDGE   = 2.0
TAIL   = 500.0
HI = [i for i in range(MGATE) if i % 2 == 0]
LO = [i for i in range(MGATE) if i % 2 == 1]

# receiver families (Track 3 sizings, re-run here)
RX = {
    "std": dict(wp="1.12u", wn="0.74u", vdd=1.2),   # campaign standard generic inverter
    "K":   dict(wp="0.15u", wn="1.48u", vdd=0.9),   # Track 3's best
    "D":   dict(wp="0.15u", wn="1.48u", vdd=1.2),   # skewed on the full rail
}

POINTS = {
    # tag: L nH, TG total um, dV
    "anchor":   dict(L=277.8, tot=15.0, dv=1.0),
    "headline": dict(L=15.0,  tot=30.0, dv=1.2),
    "mid":      dict(L=45.0,  tot=15.0, dv=1.0),
    "hl_w15":   dict(L=15.0,  tot=15.0, dv=1.2),
    # real logic cells (Vortex ALU's dominant cell) at Track 1's FAST point
    "o21_fast": dict(L=15.0,  tot=30.0, dv=1.2, kind="o21ai"),
    # ... and at the COMMITTED energy-optimal point, to validate my o21ai bank
    # against Track 2's reported "never settles, 25.3% of rail at freeze"
    "o21_comm": dict(L=277.8, tot=15.0, dv=1.0, kind="o21ai"),
    # inverter bank at the ALU's MEASURED mean sink load, 6.91 fF
    "hl_cl691": dict(L=15.0,  tot=30.0, dv=1.2, cl=6.91),
    # dV = 1.5 V: the PDK ships the IDENTICAL 84-cell stdcell liberty at typ
    # 1.50 V (sg13g2_stdcell_typ_1p50V_25C.lib), so 1.2 V is NOT the LV ceiling.
    # Swing is the binding constraint on every result above; this tests the
    # vendor-supported step Track 1 never took.
    "o21_dv150": dict(L=15.0, tot=30.0, dv=1.5, kind="o21ai"),
    "hl_dv150":  dict(L=15.0, tot=30.0, dv=1.5),
    "cl691_dv150": dict(L=15.0, tot=30.0, dv=1.5, cl=6.91),
}


def head():
    return ['.hdl "%s"' % VA, '.include "%s"' % MODEL, '.include "%s"' % SHIM,
            '.OPTIONS TIMEINT METHOD=GEAR RELTOL=1e-6 ABSTOL=1e-15 CHGTOL=1e-17']


def widths(tot):
    return dict(wn=tot / 3.0, wp=2.0 * tot / 3.0, park=tot / 15.0)


def t_pred(L, ca=CA_FF):
    """pi*sqrt(L*C_ser) with C_ser = CA/2 (two equal banks in series)."""
    return math.pi * math.sqrt((L * 1e-9) * (ca / 2.0) * 1e-15) * 1e12


def sw_lines(tot):
    w = widths(tot)
    return ["XSWN sw gt bkb 0 sg13_lv_nmos w=%gu l=0.13u" % w["wn"],
            "XSWP sw gtp bkb vhi sg13_lv_pmos w=%gu l=0.13u" % w["wp"],
            "XPK sw pk 0 0 sg13_lv_nmos w=%gu l=0.13u" % w["park"]]


def cells(dv, kind="inv", cl=CLOAD):
    """kind='inv': the committed 8 metered inverters, VERBATIM.
       kind='o21ai': 8 sg13g2_o21ai_1-topology cells, Y=!((A1|A2)&B1).  The cells
       whose output must follow the rail up are driven through the 2-HIGH pMOS
       SERIES stack (A1=A2=0), which is the demanding case Track 2 found fails.
       L=0.13u here (the cached geometry) where Track 2 used the stdcell 0.15u:
       0.13u is the STRONGER device, so this is GENEROUS to QAL."""
    L = ["VMGH gnh 0 0", "VMGL gnl 0 0"]
    if kind == "inv":
        for i in range(MGATE):
            g = "gnh" if i in HI else "gnl"
            L += ["VI%d in%d 0 %g" % (i, i, dv if i in HI else 0.0),
                  "XP%d o%d in%d bkb bkb sg13_lv_pmos w=%gu l=0.13u" % (i, i, i, WP),
                  "XN%d o%d in%d %s %s sg13_lv_nmos w=%gu l=0.13u" % (i, i, i, g, g, WN),
                  "CL%d o%d %s %gf" % (i, i, g, cl)]
        return L
    for i in range(MGATE):
        g = "gnh" if i in HI else "gnl"
        # HI index -> output stays LOW (pull-down on);  LO index -> output follows rail
        a1 = dv if i in HI else 0.0
        L += ["VA1_%d a1_%d 0 %g" % (i, i, a1), "VA2_%d a2_%d 0 0" % (i, i),
              "VB1_%d b1_%d 0 %g" % (i, i, dv),
              "XP0_%d nt%d a1_%d bkb bkb sg13_lv_pmos w=%gu l=0.13u" % (i, i, i, WP),
              "XP1_%d o%d a2_%d nt%d bkb sg13_lv_pmos w=%gu l=0.13u" % (i, i, i, i, WP),
              "XP2_%d o%d b1_%d bkb bkb sg13_lv_pmos w=%gu l=0.13u" % (i, i, i, WP),
              "XN0_%d ns%d a2_%d %s %s sg13_lv_nmos w=%gu l=0.13u" % (i, i, i, g, g, WN),
              "XN2_%d ns%d a1_%d %s %s sg13_lv_nmos w=%gu l=0.13u" % (i, i, i, g, g, WN),
              "XN1_%d o%d b1_%d ns%d %s sg13_lv_nmos w=%gu l=0.13u" % (i, i, i, i, g, WN),
              "CX1_%d nt%d bkb 0.1f" % (i, i), "CX2_%d ns%d %s 0.1f" % (i, i, g),
              "CL%d o%d %s %gf" % (i, i, g, cl)]
    return L


def integ(tg, expr):
    return ["CX%s x%s 0 1" % (tg, tg), "BX%s 0 x%s I={ %s }" % (tg, tg, expr),
            "RX%s x%s 0 0.01" % (tg, tg)]


def rx_bank(kind, nodes):
    """one receiver per cell output.  Each receiver: stage1 (skewed, own rail) +
    stage2 (standard 1.12/0.74 on 1.2 V) + 2 fF load.  Own supply integrators."""
    r = RX[kind]
    L = ["VRD1 rd1 0 %g" % r["vdd"], "VRD2 rd2 0 1.2"]
    for i, nd in enumerate(nodes):
        L += ["XRP1_%d ra%d %s rd1 rd1 sg13_lv_pmos w=%s l=0.13u" % (i, i, nd, r["wp"]),
              "XRN1_%d ra%d %s 0 0 sg13_lv_nmos w=%s l=0.13u" % (i, i, nd, r["wn"]),
              "XRP2_%d rb%d ra%d rd2 rd2 sg13_lv_pmos w=1.12u l=0.13u" % (i, i, i),
              "XRN2_%d rb%d ra%d 0 0 sg13_lv_nmos w=0.74u l=0.13u" % (i, i, i),
              "CRL%d rb%d 0 2f" % (i, i)]
    L += integ("erd1", "-%g*I(VRD1)" % r["vdd"]) + integ("erd2", "-1.2*I(VRD2)")
    return L


# ------------------------------------------------------------------ probe/hop
def probe(L, tot, dv, ca=CA_FF, rs=RS, edge=EDGE, kind="inv", cl=CLOAD):
    tp = t_pred(L, ca)
    tend = T0 + 4.0 * tp
    ps = min(0.05, tp / 3000.0)
    ms = min(0.10, tp / 1500.0)
    return head() + [
        ".param LT=%gn RS=%g CA=%gf" % (L, rs, ca),
        "CA bka 0 {CA}", "VHI vhi 0 %g" % VGH,
        "VGT  gt  0 PWL(0 0 %gp 0 %gp %g %gp %g)" % (T0 - edge, T0, VGH, tend * 2, VGH),
        "VGTP gtp 0 PWL(0 %g %gp %g %gp 0 %gp 0)" % (VGH, T0 - edge, VGH, T0, tend * 2),
    ] + sw_lines(tot) + ["VPK pk 0 0", "LT bka mid {LT}", "RT mid sw {RS}"] \
      + cells(dv, kind, cl) + [".ic V(bka)=%g V(bkb)=0" % dv,
                     ".print tran I(LT) V(bkb) V(bka) V(sw)",
                     ".tran %gp %gp 0 %gp" % (ps, tend, ms), ".end"]


def hop(L, tot, dv, t_half, ca=CA_FF, rs=RS, edge=EDGE, tail=TAIL, rxkind=None,
        kind="inv", cl=CLOAD):
    tp = t_pred(L, ca)
    t_open = T0 + t_half
    tend = t_open + tail
    ps = min(0.05, tp / 3000.0)
    ms = min(0.10, tp / 1500.0)
    out = head() + [
        ".param LT=%gn RS=%g CA=%gf" % (L, rs, ca),
        "CA bka 0 {CA}", "VHI vhi 0 %g" % VGH,
        "VGT  gt  0 PWL(0 0 %gp 0 %gp %g %gp %g %gp 0)"
            % (T0 - edge, T0, VGH, t_open, VGH, t_open + edge),
        "VGTP gtp 0 PWL(0 %g %gp %g %gp 0 %gp 0 %gp %g)"
            % (VGH, T0 - edge, VGH, T0, t_open, t_open + edge, VGH),
    ] + sw_lines(tot) + [
        "VPK pk 0 PWL(0 0 %gp 0 %gp %g)" % (t_open + edge, t_open + 2 * edge, VGH),
        "LT bka mid {LT}", "RT mid sw {RS}"] + cells(dv, kind, cl)
    # path/energy integrators (independent of .measure -- read off the .prn)
    out += integ("qlt", "I(LT)") + integ("ea", "V(bka)*I(LT)")
    out += integ("eb", "V(bkb)*I(LT)") + integ("er", "I(LT)*I(LT)*%g" % rs)
    out += integ("esw", "V(sw)*I(LT)")
    if kind == "inv":
        sh = "I(VMGH)+" + "+".join("I(VI%d)" % i for i in HI)
        sl = "I(VMGL)+" + "+".join("I(VI%d)" % i for i in LO)
        out += integ("ebk", "V(bkb)*((%s)+(%s))" % (sh, sl))
        out += integ("eih", "-(" + "+".join("V(in%d)*I(VI%d)" % (i, i)
                                            for i in HI) + ")")
    else:
        # o21ai: no per-cell input source carries rail current; meter the
        # ground-return sources only.  Cell-energy split is not claimed here --
        # this point exists to answer a SETTLING question, not an energy one.
        out += integ("ebk", "V(bkb)*(I(VMGH)+I(VMGL))")
        out += integ("eih", "0")
    out += integ("egt", "-V(gt)*I(VGT)-V(gtp)*I(VGTP)-V(pk)*I(VPK)")
    if rxkind:
        out += rx_bank(rxkind, ["o%d" % i for i in range(MGATE)])
    out += [".ic V(bka)=%g V(bkb)=0" % dv]
    pr = ["V(bka)", "V(bkb)", "V(sw)", "I(LT)"] + ["V(o%d)" % i for i in range(MGATE)] \
         + ["V(xqlt)", "V(xea)", "V(xeb)", "V(xer)", "V(xesw)", "V(xebk)",
            "V(xeih)", "V(xegt)"]
    if rxkind:
        pr += ["V(ra%d)" % i for i in range(MGATE)] + ["V(rb%d)" % i for i in range(MGATE)]
        pr += ["V(xerd1)", "V(xerd2)"]
    for k in range(0, len(pr), 8):
        out.append((".print tran " if k == 0 else "+ ") + " ".join(pr[k:k + 8]))
    out.append(".tran %gp %gp 0 %gp" % (ps, tend, ms))
    out.append(".end")
    return out, dict(t_open=t_open, tend=tend, pstep=ps, mstep=ms)


# --------------------------------------------------------------------- runner
def run(fn, lines, timeout=560):
    p = os.path.join(HERE, fn)
    open(p, "w").write("\n".join(lines) + "\n")
    t = time.monotonic()
    try:
        r = subprocess.run([XYCE, fn], capture_output=True, text=True,
                           timeout=timeout, cwd=HERE, env=ENV)
    except subprocess.TimeoutExpired:
        return None, "TIMEOUT %gs" % timeout
    w = time.monotonic() - t
    if not os.path.exists(p + ".prn"):
        return None, "FAIL %s (%.0fs) %s" % (fn, w, r.stdout[-400:])
    return p, "%s ok %.0fs" % (fn, w)


def read_prn(path):
    hdr, rows = None, []
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


class W:
    """waveform accessor"""
    def __init__(self, path):
        self.hdr, self.rows = read_prn(path)
        self.ti = self.hdr.index("TIME")
        self.t = [r[self.ti] * 1e12 for r in self.rows]

    def col(self, name):
        n = name.upper()
        for i, h in enumerate(self.hdr):
            if h == n:
                return i
        for i, h in enumerate(self.hdr):
            if n in h:
                return i
        raise KeyError(name + " in " + str(self.hdr))

    def v(self, name):
        c = self.col(name)
        return [r[c] for r in self.rows]

    def at(self, name, tps):
        """linear interpolation at tps (picoseconds)"""
        y = self.v(name)
        if tps <= self.t[0]:
            return y[0]
        for k in range(1, len(self.t)):
            if self.t[k] >= tps:
                t0, t1 = self.t[k - 1], self.t[k]
                f = 0.0 if t1 == t0 else (tps - t0) / (t1 - t0)
                return y[k - 1] + f * (y[k] - y[k - 1])
        return y[-1]

    def cross(self, name, level, tmin=0.0, rising=True):
        """first interpolated crossing of `level` after tmin"""
        y = self.v(name)
        for k in range(1, len(self.t)):
            if self.t[k] < tmin:
                continue
            a, b = y[k - 1], y[k]
            if (rising and a < level <= b) or (not rising and a > level >= b):
                t0, t1 = self.t[k - 1], self.t[k]
                f = 0.0 if b == a else (level - a) / (b - a)
                return t0 + f * (t1 - t0)
        return None


def zero_of(path):
    """true ZCS zero: first interpolated I(LT) downward crossing of 0 after its peak."""
    w = W(path)
    i = w.v("I(LT)")
    ip = max(range(len(i)), key=lambda k: i[k])
    for k in range(ip + 1, len(i)):
        if i[k] <= 0.0 < i[k - 1]:
            t0, t1 = w.t[k - 1], w.t[k]
            f = i[k - 1] / (i[k - 1] - i[k])
            return t0 + f * (t1 - t0), i[ip] * 1e6, w.t[ip]
    return None, i[ip] * 1e6, w.t[ip]


# --------------------------------------------------------------- hop extractor
def extract_hop(path, meta, L, tot, dv, ca=CA_FF, rs=RS, rxkind=None, trip=None):
    w = W(path)
    to, te = meta["t_open"], meta["tend"]
    tE = te - 5.0
    vbe = w.at("V(bkb)", tE)
    vbo = w.at("V(bkb)", to)
    vae = w.at("V(bka)", tE)
    vbpk = max(w.v("V(bkb)"))
    ilt = w.v("I(LT)")
    ipk = max(ilt) * 1e6
    iz = w.at("I(LT)", to) * 1e6

    def dI(tg, t):   # t0-referenced integrator, fJ or fC
        return (w.at("V(x%s)" % tg, t) - w.at("V(x%s)" % tg, 0.5)) * 1e15

    qlt_o, qlt_E = dI("qlt", to), dI("qlt", tE)
    ea_o, ea_E = dI("ea", to), dI("ea", tE)
    eb_o = dI("eb", to)
    er_o = dI("er", to)
    esw_o = dI("esw", to)
    va_open = dv - qlt_o / ca

    # settling, from the waveform, per cell
    def s_of(i, t, ref):
        v = w.at("V(o%d)" % i, t)
        return 100.0 * ((1.0 - v / ref) if i in HI else (v / ref)), v
    s_open = {("o%d" % i): s_of(i, to, vbo)[0] for i in range(MGATE)}
    s_end = {("o%d" % i): s_of(i, tE, vbe)[0] for i in range(MGATE)}
    v_open = {("o%d" % i): w.at("V(o%d)" % i, to) for i in range(MGATE)}
    v_end = {("o%d" % i): w.at("V(o%d)" % i, tE) for i in range(MGATE)}

    # t_valid_f : all 8 simultaneously within f of the INSTANTANEOUS rail, and stay
    def t_valid(f):
        vb = w.v("V(bkb)")
        oc = [w.col("V(o%d)" % i) for i in range(MGATE)]
        good_from = None
        for k in range(len(w.t)):
            if w.t[k] < T0 or vb[k] < 0.05:
                continue
            ok = True
            for i in range(MGATE):
                v = w.rows[k][oc[i]]
                s = (1.0 - v / vb[k]) if i in HI else (v / vb[k])
                if s < f:
                    ok = False
                    break
            if ok and good_from is None:
                good_from = w.t[k]
            elif not ok:
                good_from = None
        return good_from

    def t_settle(f):
        oc = [w.col("V(o%d)" % i) for i in range(MGATE)]
        gf = None
        for k in range(len(w.t)):
            if w.t[k] < T0:
                continue
            ok = True
            for i in range(MGATE):
                v = w.rows[k][oc[i]]
                s = (1.0 - v / vbe) if i in HI else (v / vbe)
                if s < f:
                    ok = False
                    break
            if ok and gf is None:
                gf = w.t[k]
            elif not ok:
                gf = None
        return gf

    tr90 = w.cross("V(bkb)", 0.9 * vbe, tmin=T0)
    row = dict(L_nH=L, total_um=tot, dv=dv, ca_fF=ca, rs=rs, rx=rxkind,
               **{"w_" + k: v for k, v in widths(tot).items()},
               t_hop_ps=to - T0, t_pred_ps=t_pred(L, ca),
               t_open=to, tend=te,
               VBPK=vbpk, VBEND=vbe, VBOPEN=vbo, VAEND=vae, VA_open=va_open,
               IPK_uA=ipk, IZ_uA=iz,
               E_outA_exact_fJ=0.5 * ca * (dv * dv - vae * vae),
               ea_open_fJ=ea_o, ea_end_fJ=ea_E, eb_open_fJ=eb_o,
               E_R_fJ=er_o, E_swblk_fJ=esw_o - eb_o,
               ident_at_zero_fJ=ea_o - esw_o - er_o,
               qlt_open_fC=qlt_o, qlt_end_fC=qlt_E,
               closQ_pct=(qlt_E - ca * (dv - vae)) / (ca * (dv - vae)) * 100,
               closE_pct=(ea_E - 0.5 * ca * (dv * dv - vae * vae))
                         / (0.5 * ca * (dv * dv - vae * vae)) * 100,
               E_gate_drive_fJ=dI("egt", tE),
               cells_ebk_fJ=dI("ebk", tE), cells_eih_fJ=dI("eih", tE),
               s_open=s_open, s_end=s_end, v_open=v_open, v_end=v_end,
               t_rail90_ps=None if tr90 is None else tr90 - T0,
               t_valid80_ps=None, t_valid90_ps=None, t_valid95_ps=None,
               t_settle90_ps=None)
    for f, k in ((0.80, "t_valid80_ps"), (0.90, "t_valid90_ps"), (0.95, "t_valid95_ps")):
        tv = t_valid(f)
        row[k] = None if tv is None else tv - T0
    ts = t_settle(0.90)
    row["t_settle90_ps"] = None if ts is None else ts - T0
    row["t_level_ps"] = max([x for x in (row["t_hop_ps"], row["t_valid90_ps"]) if x])
    # absolute-margin test against a receiver trip point
    if trip is not None:
        lo_min = min(v_end["o%d" % i] for i in LO)
        hi_max = max(v_end["o%d" % i] for i in HI)
        row["trip_V"] = trip
        row["margin_hi_mV"] = (lo_min - trip) * 1e3
        row["margin_lo_mV"] = (trip - hi_max) * 1e3
        row["abs_margin_pass"] = bool(lo_min > trip and hi_max < trip)
    if rxkind:
        # receiver resolve: stage-1 output must cross the downstream trip; stage-2
        # must cross 50% of its own 1.2 V rail with the correct polarity.
        vdd1 = RX[rxkind]["vdd"]
        res = {}
        for i in range(MGATE):
            tgt = 0.6  # 50% of the 1.2 V stage-2 rail
            want_hi = (i in LO)   # QAL cell high -> rx stage1 low -> stage2 HIGH
            vend = w.at("V(rb%d)" % i, tE)
            vmax = max(w.v("V(rb%d)" % i))
            if want_hi:
                tc = w.cross("V(rb%d)" % i, tgt, tmin=T0, rising=True)
                ok = (vend > tgt) and tc is not None
                tres = None if tc is None else tc - T0
            else:
                # a stay-low receiver is RESOLVED FROM t=0: it never crosses the
                # threshold.  Charging it the hop time would be an artefact.
                ok = (vmax < tgt)
                tres = 0.0 if ok else None
            res["rb%d" % i] = dict(v_end=vend, v_max=vmax,
                                   v_at_open=w.at("V(rb%d)" % i, to),
                                   t_cross_ps=tres, correct=bool(ok), want_hi=want_hi)
        row["rx_resolve"] = res
        row["rx_E_stage1_fJ"] = dI("erd1", tE)
        row["rx_E_stage2_fJ"] = dI("erd2", tE)
        row["rx_vdd1"] = vdd1
        crs = [v["t_cross_ps"] for v in res.values()]
        row["rx_all_resolved"] = all(v["correct"] for v in res.values())
        row["rx_t_resolve_max_ps"] = (max(c for c in crs if c is not None)
                                      if row["rx_all_resolved"] else None)
        row["t_level_b_ps"] = (max(row["t_level_ps"], row["rx_t_resolve_max_ps"])
                               if row["rx_all_resolved"] else None)
    return row


# ------------------------------------------------------------------- stages
def stage_pt(tag, rxkind=None, store="rows.json"):
    p = POINTS[tag]
    kind = p.get("kind", "inv"); cl = p.get("cl", CLOAD)
    nm = tag + ("_rx" + rxkind if rxkind else "")
    lp, msg = run("p_%s.cir" % nm, probe(p["L"], p["tot"], p["dv"], kind=kind, cl=cl))
    print(" probe:", msg)
    tz, ipk, tipk = zero_of(lp + ".prn")
    print("  true zero %.4f ps (t_hop %.4f), Ipk %.2f uA at %.2f ps"
          % (tz, tz - T0, ipk, tipk))
    lines, meta = hop(p["L"], p["tot"], p["dv"], tz - T0, rxkind=rxkind,
                      kind=kind, cl=cl)
    hp, msg = run("h_%s.cir" % nm, lines)
    print(" hop:", msg)
    trip = None
    tf = os.path.join(HERE, "trips.json")
    if os.path.exists(tf):
        tr = json.load(open(tf))
        trip = tr.get(rxkind or "K", {}).get("trip_V")
    row = extract_hop(hp + ".prn", meta, p["L"], p["tot"], p["dv"],
                      rxkind=rxkind, trip=trip)
    row["cell_kind"] = kind; row["cl_fF"] = cl
    row["probe_Ipk_uA"] = ipk
    sf = os.path.join(HERE, store)
    d = json.load(open(sf)) if os.path.exists(sf) else {}
    d[nm] = row
    json.dump(d, open(sf, "w"), indent=1)
    print(json.dumps({k: v for k, v in row.items()
                      if k not in ("s_open", "s_end", "v_open", "v_end", "rx_resolve")},
                     indent=1))
    print(" s_open:", {k: round(v, 2) for k, v in row["s_open"].items()})
    print(" s_end :", {k: round(v, 2) for k, v in row["s_end"].items()})
    print(" v_end :", {k: round(v, 4) for k, v in row["v_end"].items()})
    if rxkind:
        print(" rx    :", json.dumps(row["rx_resolve"], indent=1))
    return row


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "pt":
        stage_pt(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
