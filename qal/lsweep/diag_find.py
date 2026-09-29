#!/usr/bin/env python3
"""DIAGNOSTIC: the C4 instrument gate failed at L=3 and L=1 nH.

Symptom: at L=1 the hop .prn shows I(LT) = +0.012 uA at the open checkpoint
t_open = 65.9281 ps (the breakpoint is visibly there), but the .mt0 reports
  IZ = .measure tran IZ FIND I(LT) AT=65.9281p  ->  +423.2 uA
and the 1F-integrator books agree with the .mt0, not the .prn:
  identity_at_B = ea_B - esw_B - er_B = 0.08954 fJ = 0.5*L*(423.2uA)^2 exactly.

So .prn and .measure disagree about WHICH INSTANT 65.9281 ps is, and the
disagreement looks like ~1 ps of lag.  This deck settles it: the same run
carries (a) FIND I(LT) at a ladder of offsets around t_open, (b) the same
current read as a B-source node voltage, and (c) the integrator nodes on the
.print list so the ledger can be rebuilt from the waveform and compared with
the .mt0 that the harness actually uses.
"""
import os, re, subprocess, sys, time
import lsw

HERE = os.path.dirname(os.path.abspath(__file__))
L_NH, W, TZ = 1.0, 15.0, None

OFFS = [-4.0, -2.0, -1.0, -0.5, -0.2, -0.05, 0.0, 0.05, 0.2, 0.5, 1.0]


def main():
    pr, st = lsw.probe("diag", L_NH, W, verbose=True)
    th = pr["t_half"]
    t_open = lsw.T0 + th
    print("probe zero t_half = %.6f ps  ->  t_open = %.6f ps (%s)" % (th, t_open, st))
    L, meta = lsw.hop_lines(L_NH, W, th)
    extra = []
    for k, d in enumerate(OFFS):
        extra.append(".measure tran IZO%02d FIND I(LT) AT=%.6fp" % (k, t_open + d))
        extra.append(".measure tran IQO%02d FIND V(qt) AT=%.6fp" % (k, t_open + d))
    extra.append(".measure tran EAB2 FIND V(xea) AT=%.6fp" % t_open)
    extra.append(".measure tran ESWB2 FIND V(xesw) AT=%.6fp" % t_open)
    extra.append(".measure tran ERB2 FIND V(xer) AT=%.6fp" % t_open)
    # splice the extra measures in before .print / .end, and widen .print
    out = []
    for ln in L:
        if ln.startswith(".print tran"):
            out += extra
            out.append(".print tran V(bka) V(bkb) V(sw) I(LT) V(qt) V(xqlt) V(xea) "
                       "V(xesw) V(xer) V(o0) V(o1)")
            continue
        out.append(ln)
    fn = "diag_find.cir"
    open(os.path.join(HERE, fn), "w").write("\n".join(out) + "\n")
    t0 = time.monotonic()
    r = subprocess.run([lsw.XYCE, fn], capture_output=True, text=True, timeout=560,
                       cwd=HERE, env=lsw.ENV)
    print("ran %s in %.1fs rc=%d" % (fn, time.monotonic() - t0, r.returncode))
    if r.returncode != 0:
        print(r.stdout[-1200:]); sys.exit(1)
    m = lsw.parse_mt0(os.path.join(HERE, fn + ".mt0"))

    hdr, rows = lsw.read_prn(os.path.join(HERE, fn + ".prn"))
    il, iq = hdr.index("I(LT)"), hdr.index("V(QT)")
    def wave(col, t):
        prev = None
        for rr in rows:
            tt = rr[1] * 1e12
            if prev is not None and prev[1] <= t <= tt:
                f = (t - prev[1]) / (tt - prev[1]) if tt != prev[1] else 0.0
                return prev[0] + f * (rr[col] - prev[0])
            prev = (rr[col], tt)
        return float("nan")

    print("\n%9s | %14s %14s | %14s   %14s" %
          ("offset ps", "mt0 FIND I(LT)", "mt0 FIND V(qt)", "prn I(LT) interp", "prn V(qt) interp"))
    for k, d in enumerate(OFFS):
        a = m.get("IZO%02d" % k, float("nan")) * 1e6
        b = m.get("IQO%02d" % k, float("nan")) * 1e6
        c = wave(il, t_open + d) * 1e6
        e = wave(iq, t_open + d) * 1e6
        print("%9.3f | %14.4f %14.4f | %14.4f   %14.4f" % (d, a, b, c, e))

    # ledger at B: .mt0 vs waveform
    f = 1e15
    z = {t: m["%s_Z" % t.upper()] for t in ("ea", "esw", "er", "qlt")}
    print("\n%8s | %14s %14s" % ("integ", "mt0 at B (fJ)", "prn at B (fJ)"))
    for t, col in (("ea", "V(XEA)"), ("esw", "V(XESW)"), ("er", "V(XER)")):
        a = (m["%s_B" % t.upper()] - z[t]) * f
        b = (wave(hdr.index(col), t_open) - z[t]) * f
        print("%8s | %14.6f %14.6f" % (t, a, b))
    a_id = ((m["EA_B"] - z["ea"]) - (m["ESW_B"] - z["esw"]) - (m["ER_B"] - z["er"])) * f
    b_id = ((wave(hdr.index("V(XEA)"), t_open) - z["ea"])
            - (wave(hdr.index("V(XESW)"), t_open) - z["esw"])
            - (wave(hdr.index("V(XER)"), t_open) - z["er"])) * f
    print("identity ea-esw-er at B:  mt0 %.6f fJ   prn %.6f fJ" % (a_id, b_id))


if __name__ == "__main__":
    main()
