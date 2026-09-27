#!/usr/bin/env python3
"""Q2 (hybrid timer): the post-open CALIBRATION OBSERVABLE, measured.

Sweeps the switch-open time of the tg15p TRUE-ZCS hop (committed optimum row,
swsweep/sweep_rows.json tg15p_zcs, true zero 266.755223 ps after close) by
DELTA in [-80,+80] ps and extracts every candidate post-open observable a SAR
calibration loop could use:

  - VBEND        V(bkb) at end        (frozen bank-B level; peak-shaped)
  - VBPK-VBEND   run peak minus end   (one-sided lateness detector)
  - ring samples V(bka) at open+T/4, +T/2 (interrupted-current ring polarity;
                 SIGN-REVERSING candidate; T ~ 2*pi*sqrt(L*CA) ~ 628 ps)
  - V(sw) post-open excursion (park-damped ring, max/min)
  - IZ           I(LT) at open        (ground truth for the sign, NOT cheaply
                 observable in hardware -- that is the refuted ZCD)

Energy per trial is booked with the swsweep A2 robust metric:
E_hop_open = EA_C - E_static_sup(VBEND), static curve from
swsweep/sw_calib.cir.prn (instrument-gated against the committed tg15p_zcs
row before any new run is trusted).

Deck/metering structure is sw_hop_meter.py VERBATIM (gateb harness) with the
open time parameterized; tg15p only. Private cache vae_cache_sar.

Stages:  gen | extract | gate
"""
import json, math, os, re, sys

HERE  = os.path.dirname(os.path.abspath(__file__))
SW    = os.path.normpath(os.path.join(HERE, "..", "swsweep"))
XYCE  = "/usr/local/src/xyce-build/src/Xyce"
VA    = "/usr/local/share/xyce/verilog-a/psp103/psp103.va"
MODEL = "/usr/local/src/kestrel/sim/models/sg13g2_psp103_tt.lib"
SHIM  = "/usr/local/src/stat-sim/qal/sg13lv_compat.sp"

DV, L_NH, RS = 1.0, 277.8, 10.0
VGH          = 1.5
WP, WN       = 1.12, 0.74
MGATE, CLOAD = 8, 2.0
CA_FF        = 35.979
T0           = 50.0
TZERO        = 266.755223          # tg15p probe zero (committed, swsweep)
WN_SW, WP_SW, W_PARK = 5.0, 10.0, 1.0

DELTAS = [-80, -60, -40, -25, -12, -6, -3, 0, 3, 6, 12, 25, 50, 65, 80]

HI = [i for i in range(MGATE) if i % 2 == 0]
LO = [i for i in range(MGATE) if i % 2 == 1]


def tag(delta):
    return ("m" if delta < 0 else "p") + "%03d" % abs(delta)


def head():
    return ['.hdl "%s"' % VA, '.include "%s"' % MODEL, '.include "%s"' % SHIM,
            '.OPTIONS TIMEINT METHOD=GEAR RELTOL=1e-6 ABSTOL=1e-15 CHGTOL=1e-17']


def switch_lines():
    return ["XSWN sw gt bkb 0 sg13_lv_nmos w=%gu l=0.13u" % WN_SW,
            "XSWP sw gtp bkb vhi sg13_lv_pmos w=%gu l=0.13u" % WP_SW,
            "XPK sw pk 0 0 sg13_lv_nmos w=%gu l=0.13u" % W_PARK]


def park_ctrl(t_open_ps):
    return ["VPK pk 0 PWL(0 0 %gp 0 %gp %g)" % (t_open_ps + 2, t_open_ps + 4, VGH)]


def cells_metered():
    L = ["VMGH gnh 0 0", "VMGL gnl 0 0"]
    for i in range(MGATE):
        gnd = "gnh" if i in HI else "gnl"
        L.append("VI%d in%d 0 %g" % (i, i, DV if i in HI else 0.0))
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


def path_integrators():
    L = []
    L += integ("qlt", "I(LT)") + integ("ea", "V(bka)*I(LT)") + integ("eb", "V(bkb)*I(LT)")
    tot = "(%s)+(%s)" % (_sup_expr("H"), _sup_expr("L"))
    L += integ("qbk", tot) + integ("ebk", "V(bkb)*(%s)" % tot)
    L += integ("er", "I(LT)*I(LT)*%g" % RS)
    L += integ("esw", "V(sw)*I(LT)")
    L += integ("qgt", "-I(VGT)") + integ("qgtp", "-I(VGTP)") + integ("qhi", "-I(VHI)")
    L += integ("egt", "-V(gt)*I(VGT)-V(gtp)*I(VGTP)-V(pk)*I(VPK)")
    L += integ("ehi", "-%g*I(VHI)" % VGH)
    return L


def hop_lines(t_half_ps):
    t_open = T0 + t_half_ps
    tend = t_open + 500.0
    L = head() + [
        ".param LT=%gn RS=%g CA=%gf" % (L_NH, RS, CA_FF),
        "CA bka 0 {CA}",
        "VHI vhi 0 %g" % VGH,
        "VGT  gt  0 PWL(0 0 %gp 0 %gp %g %gp %g %gp 0)"
            % (T0 - 2, T0, VGH, t_open, VGH, t_open + 2),
        "VGTP gtp 0 PWL(0 %g %gp %g %gp 0 %gp 0 %gp %g)"
            % (VGH, T0 - 2, VGH, T0, t_open, t_open + 2, VGH),
    ] + switch_lines() + park_ctrl(t_open) + [
        "LT bka mid {LT}", "RT mid sw {RS}",
    ] + cells_metered() + cell_integrators() + path_integrators() + [
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
          ".measure tran IZ    FIND I(LT) AT=%gp" % t_open,
          # post-open observables (ring period ~628 ps; T/4 ~ 157 ps)
          ".measure tran VKAOPEN FIND V(bka) AT=%gp" % t_open,
          ".measure tran VKAQ    FIND V(bka) AT=%gp" % (t_open + 157),
          ".measure tran VKAH    FIND V(bka) AT=%gp" % (t_open + 314),
          ".measure tran VKAMX  MAX V(bka) FROM=%gp TO=%gp" % (t_open + 10, tend),
          ".measure tran VKAMN  MIN V(bka) FROM=%gp TO=%gp" % (t_open + 10, tend),
          ".measure tran VSWMX  MAX V(sw) FROM=%gp TO=%gp" % (t_open + 6, t_open + 320),
          ".measure tran VSWMN  MIN V(sw) FROM=%gp TO=%gp" % (t_open + 6, t_open + 320),
          ".measure tran VBQ    FIND V(bkb) AT=%gp" % (t_open + 157)]
    cks = [("Z", 0.5), ("A", T0 + 5.0), ("B", t_open),
           ("C", t_open + 7.0), ("D", tend - 5.0)]
    for tg in INTEG_TAGS_CELLS + INTEG_TAGS_PATH:
        for nm, tt in cks:
            L.append(".measure tran %s_%s FIND V(x%s) AT=%gp" % (tg.upper(), nm, tg, tt))
    for i in range(MGATE):
        L.append(".measure tran O%dZ FIND V(o%d) AT=%gp" % (i, i, t_open))
        L.append(".measure tran O%dE FIND V(o%d) AT=%gp" % (i, i, tend - 5.0))
    prn = ["V(bka)", "V(bkb)", "V(sw)", "I(LT)"]
    L.append(".print tran " + " ".join(prn))
    L.append(".end")
    return L


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


def static_curve():
    """A2 static Q/E reference vs V(bkb), from the swsweep calib run (G1-gated
    there against the committed gateb record; read-only reuse here)."""
    hdr, rows = read_prn(os.path.join(SW, "sw_calib.cir.prn"))
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


def extract_one(mt0_path, t_half_ps, at):
    m = parse_mt0(mt0_path)
    f = 1e15
    def ck(tg):
        z = m["%s_Z" % tg.upper()]
        return [(m["%s_%s" % (tg.upper(), p)] - z) * f for p in ["A", "B", "C", "D"]]
    qlt, ea, er = ck("qlt"), ck("ea"), ck("er")
    ebk, eih = ck("ebk"), ck("eih")
    vbe = m["VBEND"]
    nan = float("nan")
    g = lambda k: m.get(k, nan)
    ref = at(vbe)
    e_hop_open = ea[2] - ref["E_sup"]           # A2 robust metric (cut at C)
    e_outa_exact = 0.5 * CA_FF * (DV * DV - m["VAEND"] ** 2)
    e_hop_D = e_outa_exact - ref["E_sup"]       # committed D metric (ring snapshot)
    cells_burn = (ebk[3] + eih[3]) - (ref["E_sup"] + ref["E_in"])
    va_open = DV - qlt[2] / CA_FF               # ring-free rail-drain figure
    return dict(
        t_open_ps=T0 + t_half_ps, t_half_ps=t_half_ps,
        delta_ps=t_half_ps - TZERO,
        IZ_uA=m["IZ"] * 1e6, IPK_uA=m["IPK"] * 1e6,
        VBEND=vbe, VBPK=m["VBPK"], gap_pk_end_mV=(m["VBPK"] - vbe) * 1e3,
        VAEND=m["VAEND"], VA_open_ringfree=va_open,
        VKAOPEN=g("VKAOPEN"), VKAQ=g("VKAQ"), VKAH=g("VKAH"),
        ring_qtr_mV=(g("VKAQ") - g("VKAOPEN")) * 1e3,
        VKAMX=g("VKAMX"), VKAMN=g("VKAMN"),
        VSWMX=g("VSWMX"), VSWMN=g("VSWMN"),
        VBQ=g("VBQ"),
        E_hop_open_fJ=e_hop_open, E_hop_D_fJ=e_hop_D,
        E_R_toC_fJ=er[2], cells_burn_fJ=cells_burn,
        outputs_end=[m["O%dE" % i] for i in range(MGATE)])


def main():
    stage = sys.argv[1]
    if stage == "gen":
        for d in DELTAS:
            fn = os.path.join(HERE, "sar_%s.cir" % tag(d))
            open(fn, "w").write("\n".join(hop_lines(TZERO + d)) + "\n")
            print("wrote", fn)
    elif stage == "gate":
        # extractor gate: recompute the committed tg15p_zcs row from ITS mt0
        at = static_curve()
        out = extract_one(os.path.join(SW, "sw_tg15p_z.cir.mt0"), TZERO, at)
        ref = json.load(open(os.path.join(SW, "RESULTS_SWEEP.json")))[
            "rows_TRUE_ZCS_MEASURED"]["tg15p"]
        checks = [
            ("E_hop_open_fJ", out["E_hop_open_fJ"], ref["E_hop_open_fJ"]),
            ("VBEND", out["VBEND"], ref["VBEND"]),
            ("VBPK", out["VBPK"], ref["VBPK"]),
            ("IZ_uA", out["IZ_uA"], ref["IZ_uA"]),
            ("VA_open", out["VA_open_ringfree"], ref["VA_open"]),
            ("cells_burn_fJ", out["cells_burn_fJ"], ref["cells_burn_fJ"]),
            ("E_R_toC_fJ", out["E_R_toC_fJ"], ref["E_R_toC_fJ"]),
        ]
        ok = True
        for nm, a, b in checks:
            rel = abs(a - b) / max(abs(b), 1e-30)
            flag = "OK " if rel < 1e-6 else "FAIL"
            if rel >= 1e-6:
                ok = False
            print("%s %-14s mine %.10g committed %.10g (rel %.2e)" % (flag, nm, a, b, rel))
        print("GATE", "PASS" if ok else "FAIL")
        sys.exit(0 if ok else 1)
    elif stage == "extract":
        at = static_curve()
        rows = {}
        for d in DELTAS:
            p = os.path.join(HERE, "sar_%s.cir.mt0" % tag(d))
            if not os.path.exists(p):
                print("MISSING", p)
                continue
            rows[tag(d)] = extract_one(p, TZERO + d, at)
        json.dump(rows, open(os.path.join(HERE, "sar_sweep.json"), "w"), indent=1)
        cols = ["delta_ps", "IZ_uA", "VBEND", "gap_pk_end_mV", "ring_qtr_mV",
                "VSWMX", "VSWMN", "E_hop_open_fJ", "cells_burn_fJ"]
        print(" ".join("%12s" % c for c in cols))
        for d in DELTAS:
            r = rows.get(tag(d))
            if r:
                print(" ".join("%12.5g" % r[c] for c in cols))


if __name__ == "__main__":
    main()
