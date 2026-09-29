#!/usr/bin/env python3
"""(c) THE CELL SETTLING FLOOR vs DELIVERED SUPPLY, extended upward.

Deck shape is lsweep/cellcmp2.py VERBATIM (same cell, same 2 fF load, same
supply-step edge, same .OPTIONS, same WHEN measures).  What changes: the list of
supply voltages, and three additions that cost nothing:

  PART A  the curve itself, 0.60 -> 1.50 V, covering what dV = 1.08..1.65 deliver.
  PART R  three COMMITTED points re-run (0.4885216 / 0.5883760 / 0.6754250 V) as a
          digit-check of this deck against the committed floor curve.
  PART P  the RAMP probe: the same cell at the two swings whose in-bank settle time
          is already MEASURED (0.7138163 V = the committed robust point, 0.8961157 V
          = the dV=1.5 point), with the supply edge stretched 2 -> 25 -> 50 ps.
          PRE_REGISTERED.json predicted the 2 ps-step floor UNDER-predicts the
          in-bank t_valid90 because in a bank the cells cannot start settling until
          the rail arrives.  This measures that directly instead of asserting it.
  PART O  the o21ai 2-HIGH pMOS STACK against an IDEAL supply, 0.60 -> 1.65 V.
          This is the decisive separation pre-registered in the two-high-stack
          question: it measures the STACK's own swing requirement with no bank in
          the loop, so 'the stack cannot settle' and 'the bank cannot deliver'
          stop being confounded.

Every t90 is extracted TWICE: by Xyce's own .measure WHEN (the committed path) and
independently off the .prn waveform by interpolation here.  The measured 1.0 ps
FIND-AT lag defect (lsweep) is a FIND-AT defect; WHEN is a different code path, and
running both proves it.
"""
import json, math, os, re, subprocess, sys, time

HERE  = os.path.dirname(os.path.abspath(__file__))
XYCE  = "/usr/local/src/xyce-build/src/Xyce"
VA    = "/usr/local/share/xyce/verilog-a/psp103/psp103.va"
MODEL = "/usr/local/src/kestrel/sim/models/sg13g2_psp103_tt.lib"
SHIM  = "/usr/local/src/stat-sim/qal/sg13lv_compat.sp"
CACHE = ("/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6"
         "/scratchpad/vae_cache_dvopt")
ENV = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS", PYMS_VAE_CACHE=CACHE)

WP, WN, CL, EDGE = 1.12, 0.74, 2.0, 2.0
TSTEP = 100.0

# PART A -- the curve.  Spans every delivered swing the dV grid can produce.
VA_LIST = [0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95, 1.00, 1.05, 1.10,
           1.20, 1.30, 1.40, 1.50]
# PART R -- committed reproduction points (lsweep cellcmp2.json, same deck shape)
VR_LIST = [(0.4885216, 801.2661), (0.5883760, 252.7525), (0.6754250, 137.7454)]
# PART P -- ramp probe at the two swings with a MEASURED in-bank settle time
VP_LIST = [(0.7138163, [2.0, 25.0, 50.0]), (0.8961157, [2.0, 25.0, 50.0])]
# PART O -- o21ai 2-high pMOS stack, ideal supply
VO_LIST = [0.60, 0.70, 0.80, 0.90, 1.00, 1.10, 1.20, 1.32, 1.35, 1.50, 1.65]


def head():
    return ['.hdl "%s"' % VA, '.include "%s"' % MODEL, '.include "%s"' % SHIM,
            '.OPTIONS TIMEINT METHOD=GEAR RELTOL=1e-6 ABSTOL=1e-15 CHGTOL=1e-17']


def inv_case(tag, vdd, edge=EDGE, wp=WP):
    """committed cellcmp2 'qal' case: input HELD low, supply STEPPED."""
    s, o, i = "s_" + tag, "o_" + tag, "i_" + tag
    return [
        "VS%s %s 0 PWL(0 0 %gp 0 %gp %.7f)" % (tag, s, TSTEP, TSTEP + edge, vdd),
        "VI%s %s 0 0" % (tag, i),
        "XP%s %s %s %s %s sg13_lv_pmos w=%gu l=0.13u" % (tag, o, i, s, s, wp),
        "XN%s %s %s 0 0 sg13_lv_nmos w=%gu l=0.13u" % (tag, o, i, WN),
        "CL%s %s 0 %gf" % (tag, o, CL)], o


def o21_case(tag, vdd, bhi=None, edge=EDGE):
    """sg13g2_o21ai_1 topology, Y = !((A1|A2)&B1), in the state whose output must
    follow the rail UP: A1=A2=0 so the pull-up is the 2-HIGH pMOS SERIES stack.
    Topology + widths + l=0.13u are qal/skept/sk.py cells(kind='o21ai') VERBATIM.
    bhi is the B1 logic-high level; default = the supply (chain-consistent: the
    input comes from a previous bank that delivered the same swing)."""
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


def cmos_case(tag, vdd=1.2, edge=EDGE, wp=WP):
    """committed cellcmp2 'cmos' case: supply HELD DC, input stepped DOWN.
    MANDATORY COMPANION -- see MEASURED_CONVERGENCE_TRAP below."""
    s, o, i = "s_" + tag, "o_" + tag, "i_" + tag
    return [
        "VS%s %s 0 %.7f" % (tag, s, vdd),
        "VI%s %s 0 PWL(0 %.7f %gp %.7f %gp 0)" % (tag, i, vdd, TSTEP, vdd, TSTEP + edge),
        "XP%s %s %s %s %s sg13_lv_pmos w=%gu l=0.13u" % (tag, o, i, s, s, wp),
        "XN%s %s %s 0 0 sg13_lv_nmos w=%gu l=0.13u" % (tag, o, i, WN),
        "CL%s %s 0 %gf" % (tag, o, CL)], o


# MEASURED_CONVERGENCE_TRAP (this track, bisected):  a deck containing ONLY
# supply-stepped 'qal' cases has EVERY node at 0 V at t=0, and under the committed
# .OPTIONS (GEAR, RELTOL 1e-6, ABSTOL 1e-15, CHGTOL 1e-17) Xyce then aborts at the
# step with "Gear12::rejectStep: Maximum number of failures at time 1e-10".  It does
# so for ONE case alone and at EVERY voltage, including the committed 0.6754250 V.
# The committed cellcmp2 deck converges only because it happens to carry three DC
# biased 'cmos' cases alongside its nine stepped ones.  A single DC-biased companion
# is sufficient: bisected 1 qal + 1 cmos -> converges, and returns t90 = 137.7454 ps
# at 0.6754250 V, DIGIT-IDENTICAL to the committed aL278, plus 57.1429 ps for the
# 1.2 V CMOS reference vs the committed bc112 57.1432 ps.  So one companion is added
# to EVERY chunk, which also makes that committed CMOS number a per-deck instrument
# check.  Nothing about the measured cell or its stimulus changes.
def build(cases, tend):
    L = head()
    ms, pr, meta = [], [], []
    cases = list(cases) + [("zc", "cmos", 1.2, EDGE, None)]
    for tag, kind, vdd, edge, extra in cases:
        if kind == "inv":
            ln, o = inv_case(tag, vdd, edge)
        elif kind == "cmos":
            ln, o = cmos_case(tag, vdd, edge)
        else:
            ln, o = o21_case(tag, vdd, extra, edge)
        L += ln
        for frac, n in ((0.5, "T50"), (0.8, "T80"), (0.9, "T90"), (0.95, "T95")):
            ms.append(".measure tran %s%s WHEN V(%s)=%.8f RISE=1" % (n, tag, o, frac * vdd))
        pr.append("V(%s)" % o)
        meta.append(dict(tag=tag, kind=kind, vdd=vdd, edge_ps=edge, bhi=extra, node=o))
    L.append(".tran 0.05p %gp 0 0.2p" % tend)
    L += ms
    for k in range(0, len(pr), 8):
        L.append((".print tran " if k == 0 else "+ ") + " ".join(pr[k:k + 8]))
    L.append(".end")
    return L, meta


def run(fn, lines, timeout=560):
    p = os.path.join(HERE, fn)
    open(p, "w").write("\n".join(lines) + "\n")
    t0 = time.monotonic()
    r = subprocess.run([XYCE, fn], capture_output=True, text=True, timeout=timeout,
                       cwd=HERE, env=ENV)
    w = time.monotonic() - t0
    if r.returncode != 0:
        print("FAIL %s (%.0fs)\n%s" % (fn, w, r.stdout[-1200:]))
        return None
    print("ran %s in %.0fs" % (fn, w))
    return p


def parse_mt0(p):
    d = {}
    for ln in open(p):
        g = re.match(r"\s*(\w+)\s*=\s*(\S+)", ln)
        if g:
            try:
                d[g.group(1).upper()] = float(g.group(2))
            except ValueError:
                pass
    return d


def read_prn(p):
    hdr, rows = None, []
    for ln in open(p):
        q = ln.split()
        if hdr is None and q and q[0].lower() == "index":
            hdr = [h.upper() for h in q]
            continue
        if hdr and q and q[0][0].isdigit():
            try:
                rows.append([float(x) for x in q])
            except ValueError:
                pass
    return hdr, rows


def wave_t(hdr, rows, node, level):
    """INDEPENDENT extraction: first interpolated rising crossing of `level`."""
    c = hdr.index("V(%s)" % node.upper())
    ts = [r[1] * 1e12 for r in rows]
    y = [r[c] for r in rows]
    for k in range(1, len(ts)):
        if y[k - 1] < level <= y[k]:
            f = (level - y[k - 1]) / (y[k] - y[k - 1]) if y[k] != y[k - 1] else 0.0
            return ts[k - 1] + f * (ts[k] - ts[k - 1]) - TSTEP
    return None


def collect(p, meta):
    m = parse_mt0(p + ".mt0")
    hdr, rows = read_prn(p + ".prn")
    out = {}
    for d in meta:
        tag, v = d["tag"], d["vdd"]
        row = dict(d)
        for n, fr in (("t50", 0.5), ("t80", 0.8), ("t90", 0.9), ("t95", 0.95)):
            k = ("T%d%s" % (int(fr * 100), tag)).upper()
            mv = m.get(k)
            row[n + "_ps_measure"] = (mv * 1e12 - TSTEP) if mv is not None else None
            row[n + "_ps_wave"] = wave_t(hdr, rows, d["node"], fr * v)
        row["v_end"] = rows[-1][hdr.index("V(%s)" % d["node"].upper())]
        row["settled_pct_end"] = 100.0 * row["v_end"] / v
        out[tag] = row
    return out


def vbend_cases():
    """(d) t_settle at the EXACT measured delivered swing of every grid row, so the
    headline carries no interpolation of the floor curve."""
    lf = os.path.join(HERE, "vb_cases.json")
    if os.path.exists(lf):
        vs = json.load(open(lf))
    else:
        rows = json.load(open(os.path.join(HERE, "rows.json")))
        vs = sorted({round(r["VBEND"], 7) for r in rows.values() if "error" not in r})
        json.dump(vs, open(lf, "w"), indent=1)
    return [("v%08d" % round(v * 1e7), "inv", v, EDGE, None) for v in vs]


def inv_cases():
    cases = [("a%03d" % round(v * 1000), "inv", v, EDGE, None) for v in VA_LIST]
    cases += [("r%07d" % round(v * 1e7), "inv", v, EDGE, None) for v, _ in VR_LIST]
    for v, edges in VP_LIST:
        for e in edges:
            cases.append(("p%07d_e%03d" % (round(v * 1e7), round(e * 10)),
                          "inv", v, e, None))
    return cases


def o21_cases():
    cases = [("o%03d" % round(v * 1000), "o21", v, EDGE, None) for v in VO_LIST]
    # insensitivity control: B1 held at the 1.65 V max instead of at the supply
    cases += [("ob%03d" % round(v * 1000), "o21", v, EDGE, 1.65)
              for v in (0.80, 1.20, 1.65)]
    return cases


# CHUNK_N: 27 supply sources all stepping at the same instant made Gear fail to
# converge AT the step ("Maximum number of failures at time 1e-10").  The committed
# cellcmp2 deck carried 12 cases.  Splitting into chunks of CHUNK_N is a
# DECK-PARTITION change only -- identical case content, identical .OPTIONS, and the
# committed PART R points reproduce, which is what proves the partition is inert.
CHUNK_N = 6


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    only = sys.argv[2] if len(sys.argv) > 2 else None
    res = {}
    plan = []
    if which in ("all", "inv"):
        plan.append(("inv", inv_cases(), 1600.0))
    if which in ("all", "o21"):
        plan.append(("o21", o21_cases(), 3000.0))
    if which in ("vb", "COLLECTVB"):
        plan.append(("vb", vbend_cases(), 1600.0))   # o21ai is slow; longer window
    for grp, cases, tend in plan:
        got = {}
        for ci in range(0, len(cases), CHUNK_N):
            nm = "floor_%s_c%d" % (grp, ci // CHUNK_N)
            if only and only not in (nm, "COLLECT"):
                continue
            L, meta = build(cases[ci:ci + CHUNK_N], tend)
            p = os.path.join(HERE, "%s.cir" % nm)
            if only == "COLLECT":
                # the chunk decks are already simulated; COLLECT re-reads them in
                # ONE process.  (Running the chunks in parallel had each process
                # rewrite floor.json from its own partial view, so only the last
                # chunk survived -- no measurement was affected, the .prn/.mt0
                # files are the record and are re-read here untouched.)
                if not os.path.exists(p + ".mt0"):
                    print("MISSING %s.mt0" % nm)
                    continue
            else:
                p = run("%s.cir" % nm, L)
            if p:
                one = collect(p, meta)
                got.update(one)
                json.dump(dict(group=grp, rows=one),
                          open(os.path.join(HERE, "part_%s.json" % nm), "w"), indent=1)
        if got:
            res[grp] = got
    if which == "MERGEPARTS":
        for fn2 in sorted(os.listdir(HERE)):
            if fn2.startswith("part_floor_") and fn2.endswith(".json"):
                d = json.load(open(os.path.join(HERE, fn2)))
                res.setdefault(d["group"], {}).update(d["rows"])
    fn = os.path.join(HERE, "floor.json")
    old = json.load(open(fn)) if os.path.exists(fn) else {}
    for grp, rows in res.items():                  # MERGE, never replace
        old.setdefault(grp, {}).update(rows)
    res = {g: old[g] for g in res}
    json.dump(old, open(fn, "w"), indent=1)
    for grp, rows in res.items():
        print("\n=== %s ===" % grp)
        print("%-16s %8s %6s %6s | %9s %9s | %9s %9s | %8s"
              % ("tag", "VDD", "edge", "bhi", "t90 meas", "t90 wave", "t80 meas",
                 "t95 wave", "end %"))
        for tag, r in rows.items():
            nn = lambda x: float("nan") if x is None else x
            print("%-16s %8.5f %6.1f %6s | %9.3f %9.3f | %9.3f %9.3f | %8.2f"
                  % (tag, r["vdd"], r["edge_ps"], str(r["bhi"]),
                     nn(r["t90_ps_measure"]), nn(r["t90_ps_wave"]),
                     nn(r["t80_ps_measure"]), nn(r["t95_ps_wave"]),
                     r["settled_pct_end"]))
    # per-deck instrument check: the committed 1.2 V CMOS reference, bc112 t90
    print("\n=== per-deck companion check (committed bc112 t90 = 57.1432 ps) ===")
    for grp, rows in res.items():
        if "zc" in rows:
            mine = rows["zc"]["t90_ps_measure"]
            rel = abs(mine - 57.1432) / 57.1432
            print("%s %-4s zc t90 %.4f ps (rel %.2e)"
                  % ("OK  " if rel < 1e-4 else "FAIL", grp, mine, rel))
    # digit-check against the committed floor
    if "inv" in res:
        print("\n=== PART R: committed reproduction ===")
        for v, ref in VR_LIST:
            r = res["inv"]["r%07d" % round(v * 1e7)]
            mine = r["t90_ps_measure"]
            rel = abs(mine - ref) / ref
            print("%s V=%.7f  t90 mine %.4f committed %.4f  rel %.2e"
                  % ("OK  " if rel < 1e-4 else "FAIL", v, mine, ref, rel))


if __name__ == "__main__":
    main()
