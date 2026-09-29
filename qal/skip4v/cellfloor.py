#!/usr/bin/env python3
"""SKEPTIC's OWN cell-floor control -- the one number the verdict turns on.

The report asserts that no beat period exists because a 1.12 um pMOS cannot pull
a 2 fF node to the delivered QAL rail inside a beat, and cites the COMMITTED
lsweep table for it.  This deck measures it here, from scratch, with an IDEAL
rail (a stiff source, no inductor, no droop) and an IDEAL gate (a DC source):
the most generous possible conditions.  If the cell cannot make 90% at the
delivered rail even here, no power schedule can rescue it.

Each case is an independent copy of the committed cell (pMOS w=1.12u with supply
AND bulk on its own rail, nMOS w=0.74u, CL 2 fF), driven by its own ideal rail
that STEPS at t=2 ps -- which is strictly kinder than the chain, whose rail
arrives as a ~100 ps resonant half-sine.
"""
import os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
XYCE = "/usr/local/src/xyce-build/src/Xyce"
VA = "/usr/local/share/xyce/verilog-a/psp103/psp103.va"
MODEL = "/usr/local/src/kestrel/sim/models/sg13g2_psp103_tt.lib"
SHIM = "/usr/local/src/stat-sim/qal/sg13lv_compat.sp"

# (label, rail V, gate V, why this point)
CASES = [
    ("dv12_ideal",   1.2000, 0.0000, "full supply, ideal LOW gate -- the reference"),
    ("committed_rail", 0.7138163, 0.0000, "the committed single-hop delivered rail"),
    ("depth1_T120",  0.6441, 0.0000, "MEASURED skip bank-3 rail, ideal gate (term A alone)"),
    ("depth1_T120_creep", 0.6441, 0.1740, "same rail, gate at the MEASURED crept LOW (term A+B)"),
    ("depth1_T160_creep", 0.6486, 0.3039, "MEASURED skip bank-3 rail and crept LOW at T=160"),
    ("depth2_T120",  0.4486, 0.0000, "MEASURED skip bank-5 rail, ideal gate"),
    ("depth2_T120_creep", 0.4486, 0.2137, "same rail, MEASURED crept LOW"),
    ("adj_depth1_T120", 0.6406, 0.0016, "MEASURED adj bank-2 rail and its (clean) LOW"),
    ("adj_depth2_T120", 0.4007, 0.1061, "MEASURED adj bank-3 rail and its crept LOW"),
]
TEND = 3000.0


def build():
    L = ['.hdl "%s"' % VA, '.include "%s"' % MODEL, '.include "%s"' % SHIM,
         ".OPTIONS TIMEINT METHOD=GEAR RELTOL=1e-6 ABSTOL=1e-15 CHGTOL=1e-17"]
    for n, (lab, vr, vg, _) in enumerate(CASES):
        L += ["VR%d r%d 0 PWL(0 0 2p %g %gp %g)" % (n, n, vr, TEND, vr),
              "VG%d g%d 0 %g" % (n, n, vg),
              "VM%d s%d 0 0" % (n, n),
              "XP%d o%d g%d r%d r%d sg13_lv_pmos w=1.12u l=0.13u" % (n, n, n, n, n),
              "XN%d o%d g%d s%d s%d sg13_lv_nmos w=0.74u l=0.13u" % (n, n, n, n, n),
              "CL%d o%d s%d 2f" % (n, n, n)]
    L.append(".ic " + " ".join("V(o%d)=0" % n for n in range(len(CASES))))
    L.append(".tran 0.1p %gp 0 0.25p" % TEND)
    L.append(".print tran " + " ".join("V(o%d) V(r%d)" % (n, n)
                                       for n in range(len(CASES))))
    L.append(".end")
    return L


if __name__ == "__main__":
    fn = "cellfloor.cir"
    open(os.path.join(HERE, fn), "w").write("\n".join(build()) + "\n")
    r = subprocess.run([XYCE, fn], capture_output=True, text=True, cwd=HERE,
                       env=dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS"))
    if not os.path.exists(os.path.join(HERE, fn + ".prn")):
        print("FAIL", r.stdout[-800:]); sys.exit(1)
    hdr, rows = None, []
    for ln in open(os.path.join(HERE, fn + ".prn")):
        p = ln.split()
        if hdr is None:
            if p and p[0].lower() == "index":
                hdr = [h.upper() for h in p]
            continue
        if not p or p[0].lower().startswith("end"):
            continue
        try:
            rows.append([float(x) for x in p])
        except ValueError:
            pass
    it = hdr.index("TIME")
    print("%-20s %8s %8s  %10s %10s %10s %10s   %s"
          % ("case", "rail_V", "gate_V", "t50_ps", "t75_ps", "t90_ps", "Vfinal_pct", "why"))
    for n, (lab, vr, vg, why) in enumerate(CASES):
        io = hdr.index("V(O%d)" % n)
        ts = {}
        for frac in (0.50, 0.75, 0.90):
            tgt = frac * vr
            t = None
            prev = None
            for rw in rows:
                tt, v = rw[it] * 1e12, rw[io]
                if prev is not None and prev[1] < tgt <= v:
                    t = prev[0] + (tgt - prev[1]) * (tt - prev[0]) / (v - prev[1])
                    break
                prev = (tt, v)
            ts[frac] = (t - 2.0) if t is not None else None
        vf = rows[-1][io]
        print("%-20s %8.4f %8.4f  %10s %10s %10s %9.2f%%   %s" % (
            lab, vr, vg,
            "%.1f" % ts[0.50] if ts[0.50] else "NEVER",
            "%.1f" % ts[0.75] if ts[0.75] else "NEVER",
            "%.1f" % ts[0.90] if ts[0.90] else "NEVER",
            100.0 * vf / vr, why))
