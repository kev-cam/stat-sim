#!/usr/bin/env python3
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# SPDX-FileCopyrightText: 2026 D. Kevin Cameron
# Part of stat-sim. PolyForm Noncommercial License 1.0.0; commercial use needs a separate license (see LICENSE, COMMERCIAL.md).
"""
rffit.py -- fit a behavioural spectral model to a transistor-level RF circuit.

The circuit is characterised with Xyce harmonic balance: the tool rewrites the
stimulus of an existing SPICE netlist, sweeps drive level and frequency, and
reads back the complex output spectrum.  From that it fits a model of the form
nvc's spectral RF signals need: complex amplitude out, per frequency bin, as a
function of complex amplitude in.

  amp    one-tone drive.  For input phasor a at frequency f, output harmonic h is
             b_h = (a/|a|)^h * |a|^h * G_h(|a|, f)
         (the phase law is exact for any time-invariant circuit; G_h carries the
         AM/AM and AM/PM behaviour).  G_h is kept both as a table and as a
         polynomial in |a|^2; the VHDL package (fundamental only) uses the table.

  vhdl   regenerate the VHDL package from a saved model .json.

  mixer  two-tone drive (LO fixed, RF swept).  Product (m, n) at m*f_lo + n*f_rf is
             b_mn = u_lo^m * u_rf^n * |a_rf|^|n| * G_mn(|a_rf|)

Validation: every other drive level is held out of the fit; (amp only) the gain at
the lowest drive level is compared with Xyce's .ac analysis, which is a different
code path from harmonic balance; and the fitted one-tone model is asked to predict
a two-tone intermodulation test that Xyce then simulates directly.

Phasor convention: x(t) = Re{ b * exp(j 2 pi f t) }, amplitudes are peak volts.
"""

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from scipy.interpolate import PchipInterpolator

DROP = (".hb", ".tran", ".ac", ".dc", ".op", ".print", ".mpde", ".step", ".end",
        ".measure", ".meas", ".four", ".noise", ".probe", ".plot", ".save", ".sens", ".result")


# ----------------------------------------------------------------------------
# netlist handling
# ----------------------------------------------------------------------------

# Source values of the control state being characterised: {source_name_lower: dc_value}.
# An RF block is treated as a few quasi-static control states (enable, gain step, supply),
# each with its own level-dependent spectral transfer function.
STATE_SET = {}


def logical_lines(text):
    """Join '+' continuation lines; drop ngspice .control blocks."""
    out, in_ctl = [], False
    for raw in text.splitlines():
        s = raw.strip()
        low = s.lower()
        if low.startswith(".control"):
            in_ctl = True
            continue
        if in_ctl:
            in_ctl = not low.startswith(".endc")
            continue
        if s.startswith("+") and out:
            out[-1] += " " + s[1:].strip()
        else:
            out.append(raw.rstrip())
    return out


def source_dc(rest):
    """DC value of an independent source from the text after its two nodes."""
    m = re.search(r"\bdc\s*=?\s*([^\s()]+)", rest, re.I)
    if m:
        return m.group(1)
    m = re.search(r"\b(?:sin|pulse|pwl)\s*\(\s*([^\s,)]+)", rest, re.I)
    if m and rest.lower().lstrip().startswith("sin"):
        return m.group(1)
    tok = rest.split()
    if tok and re.match(r"^[-+0-9.]", tok[0]):
        return tok[0]
    return "0"


def prepare(netlist, tones, analysis, title, dc_override=None):
    """Return netlist text with analysis statements stripped, the named sources
    re-driven and `analysis` appended.

    tones: {source_name: [(amp, freq), ...]}; a source given two tones is split
    into two sources in series.  Returns (text, {source_name: (n+, n-)}).
    """
    base = os.path.dirname(os.path.abspath(netlist))
    lines = logical_lines(open(netlist, errors="replace").read())
    want = {k.lower(): v for k, v in tones.items()}
    nodes, out = {}, [f"* {title}", ".preprocess replaceground true"]   # GND means node 0, as in ngspice
    for i, ln in enumerate(lines):
        if i == 0:
            continue                       # SPICE title line
        s = ln.strip()
        low = s.lower()
        if not s or s.startswith("*"):
            continue
        tok = s.split()
        if tok[0].lower() in DROP or (low.startswith(".options") and len(tok) > 1 and tok[1].lower() == "hbint"):
            continue
        m = re.match(r"\.(include|inc|lib)\s+['\"]?([^'\"\s]+)['\"]?(.*)", s, re.I)
        if m and not os.path.isabs(m.group(2)):
            s = f".{m.group(1)} \"{os.path.join(base, m.group(2))}\"{m.group(3)}"
        name = tok[0].lower()
        if name in STATE_SET and name not in want:
            out.append(f"{tok[0]} {tok[1]} {tok[2]} DC {STATE_SET[name]}")      # control/supply value of this state
            continue
        if name in want:
            npos, nneg = tok[1], tok[2]
            dc = source_dc(" ".join(tok[3:]))
            if dc_override and name in dc_override:
                dc = dc_override[name]
            nodes[name] = (npos, nneg)
            tl = want[name]
            if name[0] not in "vi":
                sys.exit(f"{tok[0]} is not an independent source")
            if len(tl) == 1:
                out.append(f"{tok[0]} {npos} {nneg} DC {dc} SIN({dc} {tl[0][0]:.9g} {tl[0][1]:.9g} 0 0)")
            else:
                mid = f"rffit_mid_{name}"
                out.append(f"{tok[0]} {npos} {mid} DC {dc} SIN({dc} {tl[0][0]:.9g} {tl[0][1]:.9g} 0 0)")
                out.append(f"{tok[0]}_t2 {mid} {nneg} DC 0 SIN(0 {tl[1][0]:.9g} {tl[1][1]:.9g} 0 0)")
            continue
        out.append(s)
    missing = set(want) - set(nodes)
    if missing:
        sys.exit(f"source(s) not found in {netlist}: {', '.join(sorted(missing))}")
    out += analysis + [".end"]
    return "\n".join(out) + "\n", nodes


def run_xyce(text, workdir, tag, xyce, timeout):
    """Run one HB job; return (freqs, {column: complex two-sided coefficients}) or None."""
    d = os.path.join(workdir, tag)
    os.makedirs(d, exist_ok=True)
    cir = os.path.join(d, "run.cir")
    open(cir, "w").write(text)
    try:
        with open(os.path.join(d, "log.txt"), "w") as log:
            rc = subprocess.run([xyce, "run.cir"], cwd=d, stdout=log, stderr=subprocess.STDOUT,
                                timeout=timeout, env=XYCE_ENV).returncode
    except subprocess.TimeoutExpired:
        return None
    prn = cir + ".HB.FD.prn"
    if rc != 0 or not os.path.exists(prn):
        return None
    rows = [l.split() for l in open(prn) if l.strip() and not l.startswith("End")]
    hdr, data = rows[0], np.array(rows[1:], dtype=float)
    if data.size == 0:
        return None
    cols = {}
    for c in range(2, len(hdr), 2):
        cols[hdr[c][3:-1].upper()] = data[:, c] + 1j * data[:, c + 1]
    return data[:, 1], cols


def coef(freqs, col, f):
    """Phasor (peak) at frequency f >= 0 from two-sided Fourier coefficients."""
    i = int(np.argmin(np.abs(freqs - f)))
    tol = 1e-6 * max(abs(f), float(np.max(np.abs(freqs))), 1.0)
    if abs(freqs[i] - f) > tol:
        return complex("nan")
    return col[i] if f == 0 else 2 * col[i]


def xname(expr):
    return expr.upper().replace(" ", "")


XYCE_ENV = None         # set in main: BLAS threads per Xyce job, so parallel jobs do not oversubscribe the CPUs
HB_DIRECT = False        # --hb-direct: direct instead of iterative linear solves in HB


def hb_lines(freqs, numfreq, extra, prints):
    nf = ",".join(str(n) for n in numfreq)
    opts = f".options hbint numfreq={nf}"
    if len(freqs) > 1:
        opts += f" intmodmax={max(numfreq)}"
    if extra:
        opts += " " + extra
    if HB_DIRECT:
        opts += "\n.options linsol-hb type=direct"
    return [".hb " + " ".join(f"{f:.12g}" for f in freqs), opts, ".print hb_fd " + " ".join(prints)]


# ----------------------------------------------------------------------------
# fitting
# ----------------------------------------------------------------------------

def fit_poly(mag, G, order, scale, w):
    """Complex least squares G(|a|) ~ sum_d c_d (|a|/scale)^(2d).  The weights w turn
    the residual into output error relative to the carrier (dBc), so numerically
    empty points far below the carrier do not steer the fit."""
    x = (mag / scale) ** 2
    A = np.vander(x, order + 1, increasing=True).astype(complex)
    c, *_ = np.linalg.lstsq(A * w[:, None], G * w, rcond=None)
    return c


def eval_poly(c, mag, scale):
    x = (np.asarray(mag, float) / scale) ** 2
    return sum(ck * x ** d for d, ck in enumerate(c))


class Table:
    """Shape-preserving interpolation of a complex gain against drive level."""

    def __init__(self, mag, G):
        o = np.argsort(mag)
        self.mag = np.asarray(mag, float)[o]
        G = np.asarray(G, complex)[o]
        self.re, self.im = PchipInterpolator(self.mag, G.real), PchipInterpolator(self.mag, G.imag)

    def __call__(self, mag):
        m = np.clip(mag, self.mag[0], self.mag[-1])
        return self.re(m) + 1j * self.im(m)


def db(x):
    return 20 * np.log10(np.maximum(np.abs(x), 1e-300))


def log_amps(spec):
    lo, hi, n = spec.split(":")
    return np.geomspace(float(lo), float(hi), int(n))


def run_all(jobs, args):
    """jobs: [(tag, text)] -> {tag: result}"""
    with ThreadPoolExecutor(args.jobs) as ex:
        res = list(ex.map(lambda j: run_xyce(j[1], args.work, j[0], args.xyce, args.timeout), jobs))
    return {j[0]: r for j, r in zip(jobs, res)}


def fit_products(mag, G, order, w):
    """Fit one product over drive level, holding out every other point.
    w[k] converts an error in G at level k into output error relative to the carrier.
    Returns (model dict, held-out mask, held-out error of table and of poly)."""
    scale = float(mag.max())
    train = np.arange(len(mag)) % 2 == 0
    train[-1] = True                                    # never extrapolate past the top level
    test = ~train
    tab, pc = Table(mag[train], G[train]), fit_poly(mag[train], G[train], order, scale, w[train])
    e_tab = tab(mag[test]) - G[test]
    e_pol = eval_poly(pc, mag[test], scale) - G[test]
    full = fit_poly(mag, G, order, scale, w)
    model = {"scale": scale, "poly_re": full.real.tolist(), "poly_im": full.imag.tolist(),
             "table_mag": mag.tolist(), "table_re": G.real.tolist(), "table_im": G.imag.tolist()}
    return model, test, e_tab, e_pol


def src_dc(args):
    return {args.src.lower(): args.src_dc} if args.src_dc is not None else None


def cmd_amp(args):
    out, amps = xname(args.out), log_amps(args.amps)
    freqs = [float(f) for f in args.freqs.split(",")]
    H = args.harm
    jobs, src_nodes = [], None
    for fi, f in enumerate(freqs):
        for ai, a in enumerate(amps):
            text, nodes = prepare(args.netlist, {args.src: [(a, f)]}, [], f"rffit amp f={f:g} a={a:g}", src_dc(args))
            npos, nneg = nodes[args.src.lower()]
            vin = f"V({npos},{nneg})" if nneg.lower() not in ("0", "gnd") else f"V({npos})"
            text = text.replace(".end\n", "\n".join(hb_lines([f], [H], args.hbopts, [vin, args.out])) + "\n.end\n")
            jobs.append((f"f{fi}_a{ai}", text))
            src_nodes = vin
    print(f"running {len(jobs)} Xyce HB jobs ({len(freqs)} freq x {len(amps)} levels), input {src_nodes}, output {args.out}")
    res = run_all(jobs, args)

    model = {"kind": "amp", "name": args.name, "netlist": os.path.abspath(args.netlist), "source": args.src,
             "output": args.out, "harmonics": H, "order": args.order, "freqs": [], "per_freq": []}
    print(f"\n{'freq':>10} {'h':>2} {'small-sig':>20} {'at max drive':>20} {'holdout err, dBc':>22}")
    print(f"{'':>10} {'':>2} {'gain dB / deg':>20} {'gain dB / deg':>20} {'table':>10} {'poly':>10}")
    for fi, f in enumerate(freqs):
        mag, ph, B = [], [], []
        for ai, a in enumerate(amps):
            r = res[f"f{fi}_a{ai}"]
            if r is None:
                print(f"  f={f:g} a={a:g}: Xyce failed (see {args.work}/f{fi}_a{ai}/log.txt)")
                continue
            fr, cols = r
            ain = coef(fr, cols[xname(src_nodes)], f)
            mag.append(abs(ain)); ph.append(ain / abs(ain))
            B.append([coef(fr, cols[out], h * f) for h in range(H + 1)])
        if len(mag) < 4:
            print(f"  f={f:g}: too few converged points, skipped")
            continue
        mag, ph, B = np.array(mag), np.array(ph), np.array(B)
        pf = {"freq": f, "dc0": float(B[0, 0].real), "harm": {}}
        b1 = np.abs(B[:, 1])
        for h in range(H + 1):
            g = B[:, h] / ph ** h                         # phase-normalised output phasor
            if h == 0:
                g = g - B[0, 0]                           # DC shift relative to the smallest drive
                G = g / mag ** 2
            else:
                G = g / mag ** h
            w = mag ** (2 if h == 0 else h) / b1
            m, test, e_tab, e_pol = fit_products(mag, G, args.order, w)
            et, ep = db(e_tab * w[test]).max(), db(e_pol * w[test]).max()
            pf["harm"][str(h)] = m
            if h:
                print(f"{f:10.4g} {h:2d} {db(G[0] * mag[0] ** (h - 1)):9.2f} /{np.degrees(np.angle(G[0])):8.1f}"
                      f" {db(G[-1] * mag[-1] ** (h - 1)):10.2f} /{np.degrees(np.angle(G[-1])):8.1f} {et:10.1f} {ep:10.1f}")
        # 1 dB compression point (input referred)
        g1 = db(B[:, 1] / mag)
        below = np.where(g1 <= g1[0] - 1.0)[0]
        if len(below) and below[0] > 0:
            k = below[0]
            p1 = np.exp(np.interp(g1[0] - 1.0, [g1[k], g1[k - 1]], [np.log(mag[k]), np.log(mag[k - 1])]))
            pf["p1db_in_vpk"] = float(p1)
            print(f"{'':10} input 1 dB compression at {p1 * 1e3:.3g} mV peak")
        model["freqs"].append(f)
        model["per_freq"].append(pf)
    if not model["per_freq"]:
        sys.exit("no frequency converged")

    if not args.no_ac_check:
        ac_check(args, model, src_nodes)
    if args.twotone:
        twotone(args, model, src_nodes)
    save(args, model)


def ac_check(args, model, vin):
    """Independent check of the small-signal end of the fit: Xyce .ac at each fitted frequency
    against the HB gain at the lowest drive level.  They must agree if that level is small
    signal; a difference that does not depend on level means HB and AC are not simulating the
    same circuit (Xyce's BSIM3/BSIM4 skip their charge model in HB unless patched)."""
    m = re.match(r"^\s*[vV]\((.+)\)\s*$", args.out)
    mi = re.match(r"^\s*[vV]\((.+)\)\s*$", vin)
    if not m or not mi:
        print("AC cross-check skipped: output is not a node voltage")
        return
    prints = f"vr({mi.group(1)}) vi({mi.group(1)}) vr({m.group(1)}) vi({m.group(1)})"

    def one(f):
        text, _ = prepare(args.netlist, {args.src: [(0.0, f)]}, [], f"rffit ac check f={f:g}", src_dc(args))
        text = text.replace(" SIN(", " AC 1 SIN(", 1)
        text = text.replace(".end\n", f".ac lin 1 {f:.12g} {f:.12g}\n.print ac format=noindex {prints}\n.end\n")
        d = os.path.join(args.work, f"ac_{f:g}")
        os.makedirs(d, exist_ok=True)
        open(os.path.join(d, "run.cir"), "w").write(text)
        try:
            with open(os.path.join(d, "log.txt"), "w") as log:
                subprocess.run([args.xyce, "run.cir"], cwd=d, stdout=log, stderr=subprocess.STDOUT,
                               timeout=args.timeout, env=XYCE_ENV)
            row = [l.split() for l in open(os.path.join(d, "run.cir.FD.prn")) if l.strip()][1]
            v = [float(x) for x in row[1:5]]
            return complex(v[2], v[3]) / complex(v[0], v[1])
        except (subprocess.TimeoutExpired, OSError, IndexError, ValueError, ZeroDivisionError):
            return None

    with ThreadPoolExecutor(max_workers=args.jobs) as ex:
        acs = list(ex.map(one, model["freqs"]))
    print("\nAC cross-check: HB gain at the lowest drive level against Xyce .ac")
    rows, worst = [], 0.0
    for pf, g_ac in zip(model["per_freq"], acs):
        t = pf["harm"]["1"]
        k = int(np.argmin(t["table_mag"]))
        g_hb = complex(t["table_re"][k], t["table_im"][k])
        if g_ac is None or abs(g_ac) == 0:
            print(f"  {pf['freq']:10.4g}  .ac run failed")
            continue
        if db(g_ac) < -150 and db(g_hb) < -150:
            print(f"  {pf['freq']:10.4g}  HB {db(g_hb):8.1f} dB, AC {db(g_ac):8.1f} dB: both numerically zero, not compared")
            continue
        d_db, d_deg = float(db(g_hb / g_ac)), float(np.degrees(np.angle(g_hb / g_ac)))
        worst = max(worst, abs(d_db), abs(d_deg) / 10)
        rows.append({"freq": pf["freq"], "ac_db": float(db(g_ac)), "ac_deg": float(np.degrees(np.angle(g_ac))),
                     "hb_minus_ac_db": d_db, "hb_minus_ac_deg": d_deg})
        print(f"  {pf['freq']:10.4g}  HB {db(g_hb):8.2f} dB {np.degrees(np.angle(g_hb)):7.1f} deg   AC {db(g_ac):8.2f} dB"
              f" {np.degrees(np.angle(g_ac)):7.1f} deg   HB - AC {d_db:+6.2f} dB {d_deg:+6.1f} deg")
    model["ac_check"] = rows
    if worst > 0.1:
        print("  WARNING: HB and AC disagree by more than 0.1 dB / 1 deg.  Either the lowest drive level is not\n"
              "  small-signal, or HB is not loading the device charges (Xyce BSIM3/BSIM4 without the\n"
              "  blockAnalysisFlag fix): compare a transient run before trusting the fit.")


def amp_fund(model, f, mag, which="table"):
    """Fundamental output gain G_1(|a|) of a fitted amp model at the nearest fitted frequency."""
    pf = min(model["per_freq"], key=lambda p: abs(p["freq"] - f))
    h = pf["harm"]["1"]
    if which == "poly":
        return eval_poly(np.array(h["poly_re"]) + 1j * np.array(h["poly_im"]), mag, h["scale"])
    return Table(np.array(h["table_mag"]), np.array(h["table_re"]) + 1j * np.array(h["table_im"]))(mag)


def twotone(args, model, vin):
    """Ask the one-tone model to predict a two-tone IM test, then run the test in Xyce."""
    fc = model["freqs"][len(model["freqs"]) // 2]
    df = args.twotone
    f1, f2 = fc - df / 2, fc + df / 2
    top = max(model["per_freq"][len(model["freqs"]) // 2]["harm"]["1"]["table_mag"])
    levels = [a for a in log_amps(args.amps)[::2] if 2 * a <= top * 1.0001]
    jobs = []
    for i, a in enumerate(levels):
        text, _ = prepare(args.netlist, {args.src: [(a, f1), (a, f2)]}, [], f"rffit two-tone a={a:g}", src_dc(args))
        n = max(args.harm, 5)
        text = text.replace(".end\n", "\n".join(hb_lines([f1, f2], [n, n], args.hbopts, [vin, args.out])) + "\n.end\n")
        jobs.append((f"tt{i}", text))
    print(f"\ntwo-tone check at {f1:g} / {f2:g} Hz: {len(jobs)} Xyce 2-tone HB jobs")
    res = run_all(jobs, args)
    N = 256
    t = np.arange(N) / N
    print(f"{'per-tone':>10} {'tone out, dBV':>24} {'IM3, dBc':>24} {'IM5, dBc':>24}")
    print(f"{'mV pk':>10} {'xyce':>8}{'table':>8}{'poly':>8} {'xyce':>8}{'table':>8}{'poly':>8} {'xyce':>8}{'table':>8}{'poly':>8}")
    rec = []
    for i, a in enumerate(levels):
        r = res[f"tt{i}"]
        if r is None:
            print(f"{a * 1e3:10.4g}  Xyce failed (see {args.work}/tt{i}/log.txt)")
            continue
        fr, cols = r
        o = cols[xname(args.out)]
        x = [abs(coef(fr, o, f)) for f in (f2, 2 * f2 - f1, 3 * f2 - 2 * f1)]
        row = [a]
        cell = {}
        for which in ("table", "poly"):
            env = a * (np.exp(2j * np.pi * t) + np.exp(-2j * np.pi * t)) + 1e-30   # beat envelope, +/- df/2
            y = env * amp_fund(model, fc, np.abs(env), which)
            Y = np.fft.fft(y) / N
            cell[which] = [abs(Y[1]), abs(Y[3]), abs(Y[5])]
        print(f"{a * 1e3:10.4g} {db(x[0]):8.2f}{db(cell['table'][0]):8.2f}{db(cell['poly'][0]):8.2f}"
              f" {db(x[1] / x[0]):8.1f}{db(cell['table'][1] / cell['table'][0]):8.1f}{db(cell['poly'][1] / cell['poly'][0]):8.1f}"
              f" {db(x[2] / x[0]):8.1f}{db(cell['table'][2] / cell['table'][0]):8.1f}{db(cell['poly'][2] / cell['poly'][0]):8.1f}")
        rec.append({"amp": float(a), "xyce": x, "table": cell["table"], "poly": cell["poly"]})
    model["twotone"] = {"f1": f1, "f2": f2, "rows": rec}


def cmd_mixer(args):
    out, amps = xname(args.out), log_amps(args.amps)
    flo, frf = args.flo, args.frf
    prods = [tuple(int(v) for v in p.split(":")) for p in args.products.split(",")]
    jobs = []
    for ai, a in enumerate(amps):
        text, nodes = prepare(args.netlist, {args.lo: [(args.lo_amp, flo)], args.rf: [(a, frf)]}, [],
                              f"rffit mixer a_rf={a:g}")
        vs = []
        for s in (args.lo, args.rf):
            p, n = nodes[s.lower()]
            vs.append(f"V({p},{n})" if n.lower() not in ("0", "gnd") else f"V({p})")
        text = text.replace(".end\n", "\n".join(hb_lines([flo, frf], [args.nlo, args.nrf], args.hbopts, vs + [args.out])) + "\n.end\n")
        jobs.append((f"a{ai}", text))
    print(f"running {len(jobs)} Xyce 2-tone HB jobs, LO {vs[0]} {args.lo_amp:g} V @ {flo:g} Hz, RF {vs[1]} @ {frf:g} Hz, output {args.out}")
    res = run_all(jobs, args)
    mag, ulo, urf, cols_all = [], [], [], []
    for ai, a in enumerate(amps):
        r = res[f"a{ai}"]
        if r is None:
            print(f"  a_rf={a:g}: Xyce failed (see {args.work}/a{ai}/log.txt)")
            continue
        fr, cols = r
        lo, rf = coef(fr, cols[xname(vs[0])], flo), coef(fr, cols[xname(vs[1])], frf)
        mag.append(abs(rf)); ulo.append(lo / abs(lo)); urf.append(rf / abs(rf)); cols_all.append((fr, cols[out]))
    if len(mag) < 4:
        sys.exit("too few converged points")
    mag, ulo, urf = np.array(mag), np.array(ulo), np.array(urf)
    model = {"kind": "mixer", "name": args.name, "netlist": os.path.abspath(args.netlist), "lo": args.lo, "rf": args.rf,
             "output": args.out, "flo": flo, "frf": frf, "lo_amp": args.lo_amp, "order": args.order, "products": {}}
    ref = None
    print(f"\n{'product':>9} {'freq':>11} {'small-sig':>20} {'at max drive':>20} {'holdout err, dBc':>22}")
    print(f"{'m_lo:n_rf':>9} {'Hz':>11} {'gain dB / deg':>20} {'gain dB / deg':>20} {'table':>10} {'poly':>10}")
    for (m, n) in prods:
        F = m * flo + n * frf
        if F < 0:
            m, n, F = -m, -n, -F
        b = np.array([coef(fr, c, F) for fr, c in cols_all])
        g = b * ulo ** (-m) * urf ** (-n)
        G = g / mag ** abs(n)
        if ref is None:
            ref = np.abs(b)                                # first product is the dBc reference
        w = mag ** abs(n) / ref
        md, test, e_tab, e_pol = fit_products(mag, G, args.order, w)
        md["freq"] = F
        model["products"][f"{m}:{n}"] = md
        k = max(abs(n) - 1, 0)
        print(f"{m:>5d}:{n:<3d} {F:11.5g} {db(G[0] * mag[0] ** k):9.2f} /{np.degrees(np.angle(G[0])):8.1f}"
              f" {db(G[-1] * mag[-1] ** k):10.2f} /{np.degrees(np.angle(G[-1])):8.1f}"
              f" {db(e_tab * w[test]).max():10.1f} {db(e_pol * w[test]).max():10.1f}")
    print("(gain of an n_rf=1 product is conversion gain in V/V; n_rf=0 products are absolute dBV;"
          " errors are relative to the first product)")
    save(args, model)


# ----------------------------------------------------------------------------
# output
# ----------------------------------------------------------------------------

def vreal(v):
    s = f"{v:.12e}"
    return s if v >= 0 else f"({s})"


def vagg(items):
    """VHDL aggregate; a one-element aggregate has to use named association."""
    items = list(items)
    return "(" + ("others => " + items[0] if len(items) == 1 else ", ".join(items)) + ")"


def vhdl_amp(name, states, npt=65):
    """Fundamental-tone table model as a VHDL package for nvc's rf library (rf_signal).

    states is [(state name, amp model)]; with more than one state the apply function takes the
    control state as a second argument.  The fitted gain table is resampled (PCHIP) onto npt
    points uniform in log|a|, so the VHDL side indexes it directly and interpolates linearly.
    """
    name = re.sub(r"\W", "_", name)
    m0 = states[0][1]
    freqs = [p["freq"] for p in m0["per_freq"]]
    multi = len(states) > 1
    lo, hi, tre, tim = [], [], [], []
    for sname, m in states:
        if [p["freq"] for p in m["per_freq"]] != freqs:
            raise SystemExit(f"state {sname}: fitted frequencies differ from state {states[0][0]}")
        l, h, r, i = [], [], [], []
        for p in m["per_freq"]:
            t = p["harm"]["1"]
            mag = np.array(t["table_mag"])
            g = np.geomspace(mag.min(), mag.max(), npt)
            G = Table(mag, np.array(t["table_re"]) + 1j * np.array(t["table_im"]))(g)
            l.append(vreal(math.log(mag.min()))); h.append(vreal(math.log(mag.max())))
            r.append(vagg(vreal(v) for v in G.real)); i.append(vagg(vreal(v) for v in G.imag))
        lo.append(vagg(l)); hi.append(vagg(h)); tre.append(vagg(r)); tim.append(vagg(i))
    enum = ", ".join("ST_" + re.sub(r"\W", "_", sn).upper() for sn, _ in states)
    sets = "; ".join(f"{sn}: {m.get('set', '')}" for sn, m in states) if multi else ""
    L = [f"-- Generated by rffit.py from {m0['netlist']}",
         f"-- Fundamental-tone AM/AM + AM/PM model, output {m0['output']} for drive on {m0['source']}.",
         "-- Complex gain against drive level |a| (peak volts): table uniform in ln|a|, linear interpolation,",
         "-- held at the end values outside the fitted range; nearest fitted frequency is used."]
    if multi:
        L.append(f"-- Control states: {sets}")
    L += ["library ieee;", "use ieee.math_real.all;", "library rf;", "use rf.rf_signal_pkg.all;", "",
          f"package {name}_fit_pkg is",
          "    constant Z0 : real := 50.0;   -- reference impedance used to turn field amplitude into volts",
          f"    type {name}_state is ({enum});",
          f"    constant N_FREQ : natural := {len(freqs)};", f"    constant N_PT : natural := {npt};",
          "    type freq_table is array (0 to N_FREQ - 1) of real;",
          f"    type range_table is array ({name}_state, 0 to N_FREQ - 1) of real;",
          f"    type gain_table is array ({name}_state, 0 to N_FREQ - 1, 0 to N_PT - 1) of real;",
          "    constant FREQS : freq_table := " + vagg(vreal(f) for f in freqs) + ";",
          "    constant LN_A_LO : range_table := " + vagg(lo) + ";   -- ln of lowest fitted |a|",
          "    constant LN_A_HI : range_table := " + vagg(hi) + ";",
          "    constant G_RE : gain_table := " + vagg(tre) + ";",
          "    constant G_IM : gain_table := " + vagg(tim) + ";",
          f"    function {name}_apply(s : rf_signal" + (f"; st : {name}_state" if multi else "") + ") return rf_signal;",
          "end package;", "",
          f"package body {name}_fit_pkg is",
          f"    function {name}_apply(s : rf_signal" + (f"; st : {name}_state" if multi else "") + ") return rf_signal is"]
    if not multi:
        L.append(f"        constant st : {name}_state := {name}_state'left;")
    L += ["        variable fi : natural := 0;",
          "        variable k : natural := 0;",
          "        variable a, x, w, gr, gi : real;",
          "        variable r : rf_signal := s;",
          "    begin",
          "        for i in FREQS'range loop",
          "            if abs(FREQS(i) - s.freq) < abs(FREQS(fi) - s.freq) then fi := i; end if;",
          "        end loop;",
          "        -- field amplitude is sqrt(W); peak volts across Z0 is sqrt(2 Z0 P)",
          "        a := sqrt(2.0 * Z0 * rf_power(s));",
          "        x := 0.0;                                     -- position in the table, 0 .. N_PT - 1",
          "        if a > 0.0 then",
          "            x := (log(a) - LN_A_LO(st, fi)) / (LN_A_HI(st, fi) - LN_A_LO(st, fi)) * real(N_PT - 1);",
          "        end if;",
          "        if x <= 0.0 then",
          "            k := 0; w := 0.0;                         -- small-signal gain",
          "        elsif x >= real(N_PT - 1) then",
          "            k := N_PT - 2; w := 1.0;                  -- do not extrapolate the fit",
          "        else",
          "            k := integer(floor(x)); w := x - real(k);",
          "        end if;",
          "        gr := G_RE(st, fi, k) + w * (G_RE(st, fi, k + 1) - G_RE(st, fi, k));",
          "        gi := G_IM(st, fi, k) + w * (G_IM(st, fi, k + 1) - G_IM(st, fi, k));",
          "        r.eh_re := cmul_re(s.eh_re, s.eh_im, gr, gi);",
          "        r.eh_im := cmul_im(s.eh_re, s.eh_im, gr, gi);",
          "        r.ev_re := cmul_re(s.ev_re, s.ev_im, gr, gi);",
          "        r.ev_im := cmul_im(s.ev_re, s.ev_im, gr, gi);",
          "        return r;",
          "    end function;", "end package body;", ""]
    return name, "\n".join(L)


def write_vhdl(outdir, model, npt=65):
    if model["kind"] == "amp":
        states = [("fit", model)]
    elif model["kind"] == "amp_states":
        states = [(sn, dict(v["model"], set=v["set"])) for sn, v in model["states"].items()]
    else:
        return
    name, text = vhdl_amp(model["name"], states, npt)
    v = os.path.join(outdir, name + "_fit_pkg.vhd")
    open(v, "w").write(text)
    print(f"VHDL package written to {v}")


def save(args, model):
    os.makedirs(args.outdir, exist_ok=True)
    p = os.path.join(args.outdir, args.name + ".json")
    json.dump(model, open(p, "w"), indent=1)
    print(f"\nmodel written to {p}")
    if not getattr(args, "state", None):
        write_vhdl(args.outdir, model, args.vhdl_points)


def cmd_vhdl(args):
    for p in args.model:
        write_vhdl(args.outdir or os.path.dirname(os.path.abspath(p)), json.load(open(p)), args.vhdl_points)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("--netlist", required=True)
        p.add_argument("--out", required=True, help="output to fit, e.g. 'V(out)' or 'V(5,3)'")
        p.add_argument("--amps", required=True, help="drive levels lo:hi:n, peak volts, log spaced")
        p.add_argument("--order", type=int, default=3, help="polynomial order in |a|^2")
        p.add_argument("--name", required=True)
        p.add_argument("--outdir", default="models")
        p.add_argument("--work", default=None, help="scratch directory for Xyce runs")
        p.add_argument("--hbopts", default="tahb=1", help="extra '.options hbint' settings")
        p.add_argument("--hb-direct", action="store_true",
                       help="direct HB linear solver: slower (dense), a fallback when the iterative one stalls")
        p.add_argument("--xyce", default=shutil.which("Xyce") or "Xyce")
        p.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) // 2))
        p.add_argument("--timeout", type=float, default=120, help="seconds per Xyce run")
        p.add_argument("--vhdl-points", type=int, default=65, help="gain-table points per frequency in the VHDL package")

    a = sub.add_parser("amp", help="one-tone amplifier / two-port characterisation")
    common(a)
    a.add_argument("--src", required=True, help="input source to drive")
    a.add_argument("--freqs", required=True, help="comma-separated drive frequencies")
    a.add_argument("--harm", type=int, default=5, help="harmonics to keep")
    a.add_argument("--src-dc", default=None, help="DC bias for the driven source (default: keep the netlist value)")
    a.add_argument("--state", action="append", help="NAME:SRC=value[,SRC=value...]; repeat to fit one transfer function per control state")
    a.add_argument("--twotone", type=float, default=0, help="tone spacing in Hz for the two-tone check")
    a.add_argument("--no-ac-check", action="store_true", help="skip the .ac cross-check of the small-signal gain")
    a.set_defaults(fn=cmd_amp)

    m = sub.add_parser("mixer", help="two-tone mixer characterisation")
    common(m)
    m.add_argument("--rf", required=True); m.add_argument("--lo", required=True)
    m.add_argument("--frf", type=float, required=True); m.add_argument("--flo", type=float, required=True)
    m.add_argument("--lo-amp", type=float, required=True)
    m.add_argument("--nlo", type=int, default=7); m.add_argument("--nrf", type=int, default=5)
    m.add_argument("--products", default="1:-1,1:1,0:1,1:0,1:-3,3:-1",
                   help="m_lo:n_rf products to fit; the first is the dBc reference")
    m.set_defaults(fn=cmd_mixer)

    v = sub.add_parser("vhdl", help="regenerate the VHDL package from a fitted model .json")
    v.add_argument("model", nargs="+")
    v.add_argument("--outdir", default=None, help="default: next to the model")
    v.add_argument("--vhdl-points", type=int, default=65)
    v.set_defaults(fn=cmd_vhdl)

    args = ap.parse_args()
    if args.cmd == "vhdl":
        args.fn(args)
        return
    global HB_DIRECT, XYCE_ENV
    HB_DIRECT = args.hb_direct
    nt = str(max(1, (os.cpu_count() or 1) // max(1, args.jobs)))
    XYCE_ENV = dict(os.environ, OMP_NUM_THREADS=nt, OPENBLAS_NUM_THREADS=nt, MKL_NUM_THREADS=nt)
    states = getattr(args, "state", None)
    if not states:
        if args.work is None:
            args.work = os.path.join(args.outdir, "work_" + args.name)
        args.fn(args)
        return
    base, work, combined = args.name, args.work, {"kind": "amp_states", "name": args.name, "states": {}}
    for st in states:
        sname, _, assigns = st.partition(":")
        setv = dict(x.split("=", 1) for x in assigns.split(",") if x)
        STATE_SET.clear()
        STATE_SET.update({k.lower(): v for k, v in setv.items()})
        args.name = f"{base}__{sname}"
        args.work = os.path.join(work or args.outdir, "work_" + args.name) if work is None else os.path.join(work, sname)
        print(f"\n=== state {sname}: {setv}")
        args.fn(args)
        p = os.path.join(args.outdir, args.name + ".json")
        combined["states"][sname] = {"set": setv, "model": json.load(open(p))}
        os.remove(p)
    p = os.path.join(args.outdir, base + ".json")
    json.dump(combined, open(p, "w"), indent=1)
    print(f"\nall states written to {p}")
    write_vhdl(args.outdir, combined, args.vhdl_points)


if __name__ == "__main__":
    main()
