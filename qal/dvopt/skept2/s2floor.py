#!/usr/bin/env python3
"""SKEPTIC, INDEPENDENT settling-floor deck.  Written from the netlist up -- it does
NOT import dvopt/floor.py.  Same physical conventions so the numbers are comparable:

  cell        1.12u/0.74u inverter, l=0.13u, 2 fF load  (the campaign's cell)
  stimulus    input HELD low, SUPPLY stepped 0 -> V with a 2 ps edge at TSTEP=100 ps
  t90         interval from the START of the step (TSTEP) to V(o) = 0.90*V, rising
  .OPTIONS    GEAR RELTOL=1e-6 ABSTOL=1e-15 CHGTOL=1e-17  (committed)
  companion   one DC-biased CMOS case per deck -- MEASURED trap: an all-stepped deck
              has every node at 0 V at t=0 and Gear rejects the step.  The companion
              is also a per-deck instrument check (1.2 V CMOS ref = 57.143 ps).

t90 is extracted TWICE and both are reported: Xyce .measure WHEN, and my own
interpolation off the .prn.

The 2-high-stack case (kind o21) is the sg13g2_o21ai_1 pull-up in the state that
exercises the SERIES pMOS stack: A1=A2=0, so Y rises through XP0(A1) in series with
XP1(A2).  bhi sets the B1 high level (default = the supply).

usage: s2floor.py <deckname> <spec.json>
spec = [[tag, kind, vdd, edge, bhi_or_null], ...]   kind in inv|cmos|o21
"""
import json, os, re, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
XYCE = "/usr/local/src/xyce-build/src/Xyce"
VA = "/usr/local/share/xyce/verilog-a/psp103/psp103.va"
MODEL = "/usr/local/src/kestrel/sim/models/sg13g2_psp103_tt.lib"
SHIM = "/usr/local/src/stat-sim/qal/sg13lv_compat.sp"
CACHE = ("/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6"
         "/scratchpad/vae_cache_sk2b")
ENV = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS", PYMS_VAE_CACHE=CACHE)
WP, WN, CL, EDGE, TSTEP = 1.12, 0.74, 2.0, 2.0, 100.0


def head():
    return ['.hdl "%s"' % VA, '.include "%s"' % MODEL, '.include "%s"' % SHIM,
            '.OPTIONS TIMEINT METHOD=GEAR RELTOL=1e-6 ABSTOL=1e-15 CHGTOL=1e-17']


def inv_case(tag, vdd, edge):
    s, o, i = "s_" + tag, "o_" + tag, "i_" + tag
    return [
        "VS%s %s 0 PWL(0 0 %gp 0 %gp %.7f)" % (tag, s, TSTEP, TSTEP + edge, vdd),
        "VI%s %s 0 0" % (tag, i),
        "XP%s %s %s %s %s sg13_lv_pmos w=%gu l=0.13u" % (tag, o, i, s, s, WP),
        "XN%s %s %s 0 0 sg13_lv_nmos w=%gu l=0.13u" % (tag, o, i, WN),
        "CL%s %s 0 %gf" % (tag, o, CL)], o


def cmos_case(tag, vdd, edge):
    s, o, i = "s_" + tag, "o_" + tag, "i_" + tag
    return [
        "VS%s %s 0 %.7f" % (tag, s, vdd),
        "VI%s %s 0 PWL(0 %.7f %gp %.7f %gp 0)" % (tag, i, vdd, TSTEP, vdd, TSTEP + edge),
        "XP%s %s %s %s %s sg13_lv_pmos w=%gu l=0.13u" % (tag, o, i, s, s, WP),
        "XN%s %s %s 0 0 sg13_lv_nmos w=%gu l=0.13u" % (tag, o, i, WN),
        "CL%s %s 0 %gf" % (tag, o, CL)], o


def o21_case(tag, vdd, edge, bhi):
    s, o = "s_" + tag, "o_" + tag
    b = vdd if bhi is None else bhi
    return [
        "VS%s %s 0 PWL(0 0 %gp 0 %gp %.7f)" % (tag, s, TSTEP, TSTEP + edge, vdd),
        "VA1%s a1_%s 0 0" % (tag, tag), "VA2%s a2_%s 0 0" % (tag, tag),
        "VB1%s b1_%s 0 %.7f" % (tag, tag, b),
        "XP0%s nt_%s a1_%s %s %s sg13_lv_pmos w=%gu l=0.13u" % (tag, tag, tag, s, s, WP),
        "XP1%s %s a2_%s nt_%s %s sg13_lv_pmos w=%gu l=0.13u" % (tag, o, tag, tag, s, WP),
        "XP2%s %s b1_%s %s %s sg13_lv_pmos w=%gu l=0.13u" % (tag, o, tag, s, s, WP),
        "XN0%s ns_%s a2_%s 0 0 sg13_lv_nmos w=%gu l=0.13u" % (tag, tag, tag, WN),
        "XN2%s ns_%s a1_%s 0 0 sg13_lv_nmos w=%gu l=0.13u" % (tag, tag, tag, WN),
        "XN1%s %s b1_%s ns_%s 0 sg13_lv_nmos w=%gu l=0.13u" % (tag, o, tag, tag, WN),
        "CX1%s nt_%s %s 0.1f" % (tag, tag, s), "CX2%s ns_%s 0 0.1f" % (tag, tag),
        "CL%s %s 0 %gf" % (tag, o, CL)], o


def build(spec, tend):
    L, ms, pr, meta = head(), [], [], []
    spec = list(spec) + [["zc", "cmos", 1.2, EDGE, None]]
    for tag, kind, vdd, edge, bhi in spec:
        if kind == "inv":
            ln, o = inv_case(tag, vdd, edge)
        elif kind == "cmos":
            ln, o = cmos_case(tag, vdd, edge)
        else:
            ln, o = o21_case(tag, vdd, edge, bhi)
        L += ln
        for fr, n in ((0.5, "T50"), (0.8, "T80"), (0.9, "T90"), (0.95, "T95")):
            ms.append(".measure tran %s%s WHEN V(%s)=%.8f RISE=1"
                      % (n, tag, o, fr * vdd))
        pr.append("V(%s)" % o)
        meta.append(dict(tag=tag, kind=kind, vdd=vdd, edge_ps=edge, bhi=bhi, node=o))
    L.append(".tran 0.05p %gp 0 0.2p" % tend)
    L += ms
    for k in range(0, len(pr), 8):
        L.append((".print tran " if k == 0 else "+ ") + " ".join(pr[k:k + 8]))
    L.append(".end")
    return L, meta


def read_prn(p):
    hdr, rows = None, []
    for ln in open(p):
        q = ln.split()
        if hdr is None and q and q[0].lower() == "index":
            hdr = [h.upper() for h in q]; continue
        if hdr and q and q[0][0].isdigit():
            try:
                rows.append([float(x) for x in q])
            except ValueError:
                pass
    return hdr, rows


def wave_t(hdr, rows, node, level):
    c = hdr.index("V(%s)" % node.upper())
    ts = [r[1] * 1e12 for r in rows]
    y = [r[c] for r in rows]
    for k in range(1, len(ts)):
        if y[k - 1] < level <= y[k]:
            f = (level - y[k - 1]) / (y[k] - y[k - 1]) if y[k] != y[k - 1] else 0.0
            return ts[k - 1] + f * (ts[k] - ts[k - 1]) - TSTEP
    return None


def main():
    name, specfn = sys.argv[1], sys.argv[2]
    spec = json.load(open(specfn))
    tend = float(sys.argv[3]) if len(sys.argv) > 3 else 1200.0
    L, meta = build(spec, tend)
    fn = os.path.join(HERE, "%s.cir" % name)
    open(fn, "w").write("\n".join(L) + "\n")
    t0 = time.monotonic()
    r = subprocess.run([XYCE, "%s.cir" % name], capture_output=True, text=True,
                       timeout=900, cwd=HERE, env=ENV)
    w = time.monotonic() - t0
    if not os.path.exists(fn + ".prn"):
        print("FAIL %s (%.0fs)\n%s" % (name, w, r.stdout[-1500:])); sys.exit(1)
    print("ran %s in %.0fs" % (name, w))
    m = {}
    if os.path.exists(fn + ".mt0"):
        for ln in open(fn + ".mt0"):
            g = re.match(r"\s*(\w+)\s*=\s*(\S+)", ln)
            if g:
                try:
                    m[g.group(1).upper()] = float(g.group(2))
                except ValueError:
                    pass
    hdr, rows = read_prn(fn + ".prn")
    out = {}
    for d in meta:
        row = dict(d)
        for fr, n in ((0.5, "t50"), (0.8, "t80"), (0.9, "t90"), (0.95, "t95")):
            k = ("T%d%s" % (int(fr * 100), d["tag"])).upper()
            mv = m.get(k)
            row[n + "_measure"] = (mv * 1e12 - TSTEP) if mv is not None else None
            row[n + "_wave"] = wave_t(hdr, rows, d["node"], fr * d["vdd"])
        c = hdr.index("V(%s)" % d["node"].upper())
        row["v_end"] = rows[-1][c]
        row["settled_pct_end"] = 100.0 * rows[-1][c] / d["vdd"]
        out[d["tag"]] = row
        print("  %-14s %-5s V=%-9.7f edge=%-5g t90 measure %10s wave %10s  "
              "end %.4f V = %.2f%%"
              % (d["tag"], d["kind"], d["vdd"], d["edge_ps"],
                 "None" if row["t90_measure"] is None else "%.4f" % row["t90_measure"],
                 "None" if row["t90_wave"] is None else "%.4f" % row["t90_wave"],
                 row["v_end"], row["settled_pct_end"]))
    json.dump(out, open(os.path.join(HERE, "%s.json" % name), "w"), indent=1)


if __name__ == "__main__":
    main()
