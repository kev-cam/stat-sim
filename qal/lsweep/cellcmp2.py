#!/usr/bin/env python3
"""TRACK 1 companion 2: the cell floor AT THE SWINGS THE L SWEEP ACTUALLY
DELIVERED, plus what upsizing the cell buys.

Part A: QAL settle path (input HELD, supply stepped with a 2 ps edge) at exactly
the VBEND values MEASURED by the L sweep -- so the cell floor can be laid against
the measured t_valid90 at each L and the decomposition
   t_level ~ max(t_hop, cell floor at the delivered swing)
can be checked rather than asserted.

Part B: pMOS upsizing (1.12 / 2.24 / 4.48 um, nMOS and 2 fF load unchanged) at
the committed delivered swing and at 1.2 V CMOS, to test whether the QAL-vs-CMOS
speed ratio is size-invariant (i.e. whether the floor can simply be bought down).
"""
import json, os, re, subprocess, sys, time

HERE  = os.path.dirname(os.path.abspath(__file__))
XYCE  = "/usr/local/src/xyce-build/src/Xyce"
VA    = "/usr/local/share/xyce/verilog-a/psp103/psp103.va"
MODEL = "/usr/local/src/kestrel/sim/models/sg13g2_psp103_tt.lib"
SHIM  = "/usr/local/src/stat-sim/qal/sg13lv_compat.sp"
CACHE = os.environ.get("PYMS_VAE_CACHE") or \
    "/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6/scratchpad/vae_cache_lsweep"
ENV = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS", PYMS_VAE_CACHE=CACHE)

WN, CL, EDGE = 0.74, 2.0, 2.0
TSTEP, TEND = 100.0, 1600.0

# MEASURED VBEND, one per L-sweep primary row (tg15p switch, dV=1.0)
VB = [("L278", 0.6754250), ("L100", 0.6496840), ("L30", 0.6196049),
      ("L10", 0.5883760), ("L3", 0.5422147), ("L1", 0.4885216)]

CASES = []
for nm, v in VB:                                  # part A
    CASES.append(("a" + nm, "qal", v, 1.12))
for wp in (1.12, 2.24, 4.48):                     # part B
    CASES.append(("bq%s" % str(wp).replace(".", ""), "qal", 0.6754250, wp))
    CASES.append(("bc%s" % str(wp).replace(".", ""), "cmos", 1.2, wp))


def lines():
    L = ['.hdl "%s"' % VA, '.include "%s"' % MODEL, '.include "%s"' % SHIM,
         '.OPTIONS TIMEINT METHOD=GEAR RELTOL=1e-6 ABSTOL=1e-15 CHGTOL=1e-17']
    ms, pr = [], []
    for tag, kind, vdd, wp in CASES:
        s, o, i = "s_" + tag, "o_" + tag, "i_" + tag
        if kind == "qal":
            L.append("VS%s %s 0 PWL(0 0 %gp 0 %gp %.7f)" % (tag, s, TSTEP, TSTEP + EDGE, vdd))
            L.append("VI%s %s 0 0" % (tag, i))
        else:
            L.append("VS%s %s 0 %.7f" % (tag, s, vdd))
            L.append("VI%s %s 0 PWL(0 %.7f %gp %.7f %gp 0)"
                     % (tag, i, vdd, TSTEP, vdd, TSTEP + EDGE))
        L.append("XP%s %s %s %s %s sg13_lv_pmos w=%gu l=0.13u" % (tag, o, i, s, s, wp))
        L.append("XN%s %s %s 0 0 sg13_lv_nmos w=%gu l=0.13u" % (tag, o, i, WN))
        L.append("CL%s %s 0 %gf" % (tag, o, CL))
        for frac, n in ((0.5, "T50"), (0.9, "T90"), (0.95, "T95")):
            ms.append(".measure tran %s%s WHEN V(%s)=%.8f RISE=1" % (n, tag, o, frac * vdd))
        pr.append("V(%s)" % o)
    L.append(".tran 0.05p %gp 0 0.2p" % TEND)
    L += ms
    for k in range(0, len(pr), 8):
        L.append((".print tran " if k == 0 else "+ ") + " ".join(pr[k:k + 8]))
    L.append(".end")
    return L


def main():
    fn = "cellcmp2.cir"
    open(os.path.join(HERE, fn), "w").write("\n".join(lines()) + "\n")
    t0 = time.monotonic()
    r = subprocess.run([XYCE, fn], capture_output=True, text=True, timeout=560,
                       cwd=HERE, env=ENV)
    print("ran %s in %.1fs rc=%d" % (fn, time.monotonic() - t0, r.returncode))
    if r.returncode != 0:
        print(r.stdout[-1500:]); sys.exit(1)
    m = {}
    for ln in open(os.path.join(HERE, fn + ".mt0")):
        g = re.match(r"\s*(\w+)\s*=\s*(\S+)", ln)
        if g:
            try:
                m[g.group(1).upper()] = float(g.group(2))
            except ValueError:
                pass
    out = {}
    print("%-10s %-5s %8s %6s | %9s %9s %9s" %
          ("case", "kind", "VDD", "wp um", "t50 ps", "t90 ps", "t95 ps"))
    for tag, kind, vdd, wp in CASES:
        g = lambda k: (m.get((k + tag).upper(), float("nan")) * 1e12 - TSTEP)
        row = dict(kind=kind, vdd=vdd, wp_um=wp, t50_ps=g("T50"), t90_ps=g("T90"),
                   t95_ps=g("T95"))
        out[tag] = row
        print("%-10s %-5s %8.5f %6.2f | %9.3f %9.3f %9.3f"
              % (tag, kind, vdd, wp, row["t50_ps"], row["t90_ps"], row["t95_ps"]))
    json.dump(out, open(os.path.join(HERE, "cellcmp2.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
