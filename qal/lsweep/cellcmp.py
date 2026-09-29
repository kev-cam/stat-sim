#!/usr/bin/env python3
"""TRACK 1 companion: THE CELL FLOOR.

The L sweep can make the LC hop arbitrarily fast, but the 8 metered cells still
have to follow the rail, and (MEASURED on the committed anchor) they are already
25 ps slower than the hop.  This deck isolates that term with the SAME cell the
committed harness uses (pMOS 1.12u / nMOS 0.74u / 2 fF load, sg13_lv via
sg13lv_compat.sp, PSP103) and nothing else in the circuit:

  QAL settle path  -- input HELD (the QAL cell does not switch, it settles):
                      the SUPPLY node is stepped 0 -> VDD with a 2 ps edge and
                      we time the output reaching 90% of VDD.  Swept over the
                      delivered swing VDD in {0.6, 0.6759, 0.8, 1.0, 1.2}.
  CMOS reference   -- supply FIXED at VDD, the INPUT falls 1.2->0 (or VDD->0)
                      with a 2 ps edge; same 90%-of-VDD timing plus the 50%
                      propagation delay.  This is the like-for-like CMOS number.

Everything here is MEASURED; nothing is fitted.  Own PYMS_VAE_CACHE.
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

WP, WN, CL = 1.12, 0.74, 2.0
EDGE = 2.0
TSTEP = 100.0          # ps, when the stimulus edge starts
TEND  = 1100.0

# (tag, kind, vdd)   kind: "qal" = supply step, input held; "cmos" = input step
CASES = [("q060", "qal", 0.600), ("q0676", "qal", 0.6758936), ("q080", "qal", 0.800),
         ("q100", "qal", 1.000), ("q120", "qal", 1.200),
         ("c0676", "cmos", 0.6758936), ("c100", "cmos", 1.000), ("c120", "cmos", 1.200)]


def lines():
    L = ['.hdl "%s"' % VA, '.include "%s"' % MODEL, '.include "%s"' % SHIM,
         '.OPTIONS TIMEINT METHOD=GEAR RELTOL=1e-6 ABSTOL=1e-15 CHGTOL=1e-17']
    ms, pr = [], []
    for tag, kind, vdd in CASES:
        s, o, i = "s_" + tag, "o_" + tag, "i_" + tag
        if kind == "qal":
            # supply steps, input held at 0 (the lo-input cell: output must rise)
            L.append("VS%s %s 0 PWL(0 0 %gp 0 %gp %.7f)" % (tag, s, TSTEP, TSTEP + EDGE, vdd))
            L.append("VI%s %s 0 0" % (tag, i))
        else:
            # supply fixed, input falls vdd -> 0 (output must rise): the CMOS
            # pull-up transition, the like-for-like comparator
            L.append("VS%s %s 0 %.7f" % (tag, s, vdd))
            L.append("VI%s %s 0 PWL(0 %.7f %gp %.7f %gp 0)"
                     % (tag, i, vdd, TSTEP, vdd, TSTEP + EDGE))
        L.append("XP%s %s %s %s %s sg13_lv_pmos w=%gu l=0.13u" % (tag, o, i, s, s, WP))
        L.append("XN%s %s %s 0 0 sg13_lv_nmos w=%gu l=0.13u" % (tag, o, i, WN))
        L.append("CL%s %s 0 %gf" % (tag, o, CL))
        for frac, nm in ((0.5, "T50"), (0.8, "T80"), (0.9, "T90"), (0.95, "T95")):
            ms.append(".measure tran %s%s WHEN V(%s)=%.8f RISE=1"
                      % (nm, tag, o, frac * vdd))
        ms.append(".measure tran VOE%s FIND V(%s) AT=%gp" % (tag, o, TEND - 5))
        pr += ["V(%s)" % o, "V(%s)" % s]
    L.append(".tran 0.05p %gp 0 0.2p" % TEND)
    L += ms
    for k in range(0, len(pr), 8):
        L.append((".print tran " if k == 0 else "+ ") + " ".join(pr[k:k + 8]))
    L.append(".end")
    return L


def main():
    fn = "cellcmp.cir"
    open(os.path.join(HERE, fn), "w").write("\n".join(lines()) + "\n")
    t0 = time.monotonic()
    r = subprocess.run([XYCE, fn], capture_output=True, text=True, timeout=560,
                       cwd=HERE, env=ENV)
    print("ran %s in %.1fs rc=%d" % (fn, time.monotonic() - t0, r.returncode))
    if r.returncode != 0:
        print(r.stdout[-1500:])
        sys.exit(1)
    m = {}
    for ln in open(os.path.join(HERE, fn + ".mt0")):
        g = re.match(r"\s*(\w+)\s*=\s*(\S+)", ln)
        if g:
            try:
                m[g.group(1).upper()] = float(g.group(2))
            except ValueError:
                pass
    out = {}
    print("%-7s %-5s %7s | %9s %9s %9s %9s | %9s" %
          ("case", "kind", "VDD", "t50 ps", "t80 ps", "t90 ps", "t95 ps", "Vout_end"))
    for tag, kind, vdd in CASES:
        g = lambda k: (m.get((k + tag).upper(), float("nan")) * 1e12 - TSTEP)
        row = dict(kind=kind, vdd=vdd, t50_ps=g("T50"), t80_ps=g("T80"),
                   t90_ps=g("T90"), t95_ps=g("T95"),
                   vout_end=m.get(("VOE" + tag).upper()))
        out[tag] = row
        print("%-7s %-5s %7.4f | %9.3f %9.3f %9.3f %9.3f | %9.6f"
              % (tag, kind, vdd, row["t50_ps"], row["t80_ps"], row["t90_ps"],
                 row["t95_ps"], row["vout_end"]))
    json.dump(out, open(os.path.join(HERE, "cellcmp.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
