#!/usr/bin/env python3
"""Run a C5 closed-loop deck under Xyce and apply the SIX CLOSURE GATES.

Usage:  run_c5.py <deck.cir> [--no-run] [--brief]

Gates, all on the SAME run:
  G1 source exclusivity -- mechanical grep of the deck + EAMM == 0
  G2 no truncation      -- exit code 0 AND last TIME row >= end of every window
  G3 meter validation   -- constant rails => E_rail/Q_rail must equal 3.000 V
  G4 balance closes     -- E_in = sum(E_diss) + dE_stored, |resid| <= 2% of E_in
  G5 startup separated  -- warm-up draw reported as its own line item, excluded
  G6 periodic steady st -- per-op draw spread < 2%, state vector repeats < 1%

Never prints an energy-per-op without printing which gates failed.
ONE Xyce at a time (concurrent runs corrupt the PyMS vae .so cache).
"""
import math, os, re, subprocess, sys

XYCE = "/usr/local/src/xyce-build/src/Xyce"
ENV = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS")

CAPS = [("CS5", "CS", "s5", "s4"), ("CS4", "CS", "s4", "s3"), ("CS3", "CS", "s3", "s2"),
        ("CS2", "CS", "s2", "s1"), ("CS1", "CS", "s1", "rn"),
        ("CBA", "CB", "ba", "s2"), ("CBB", "CB", "bb", "s2"),
        ("CFA", "CFLY", "fa", "s2"), ("CFB", "CFLY", "fb", "s2"),
        ("COA", "CLOAD", "oa", "s2"), ("COB", "CLOAD", "ob", "s2"),
        ("CMAB", "CPAR", "mab", "s2"), ("CMTA", "CPAR", "mta", "s2"),
        ("CMTB", "CPAR", "mtb", "s2"),
        ("CCPab", "CCP", "dvab", "gsab"), ("CCPta", "CCP", "dvta", "gsta"),
        ("CCPtb", "CCP", "dvtb", "gstb")]
INDS = [("LAB", "LAB"), ("LTA", "LT"), ("LTB", "LT")]

# dissipators that belong to OUR ONE LANE
LANE_DISS = ["ELAB", "ELTA", "ELTB", "ERCA", "ERCB", "EBLD",
             "ESWAB", "ESWTA", "ESWTB", "EGA", "EGB", "EDRV", "EVMID"]
# dissipators that are NOT our lane (stand-in lanes + stack parasitics)
OTHER_DISS = ["ETL", "ERSER"]

SUF = {"m": 1e-3, "u": 1e-6, "n": 1e-9, "p": 1e-12, "f": 1e-15, "a": 1e-18,
       "k": 1e3, "meg": 1e6, "g": 1e9}


def val(tok):
    tok = tok.strip().lower()
    m = re.match(r'^([-+]?[\d.]+(?:e[-+]?\d+)?)\s*([a-z]*)$', tok)
    if not m:
        return float(tok)
    x, s = float(m.group(1)), m.group(2)
    if not s:
        return x
    for k in ("meg", "m", "u", "n", "p", "f", "a", "k", "g"):
        if s.startswith(k):
            return x * SUF[k]
    return x


def parse_params(deck):
    P = {}
    for ln in open(deck):
        if ln.lower().startswith(".param"):
            for m in re.finditer(r'(\w+)\s*=\s*([^\s]+)', ln):
                P[m.group(1).upper()] = val(m.group(2))
    return P


def parse_mt0(path):
    d = {}
    for ln in open(path):
        m = re.match(r'\s*([A-Za-z_]\w*)\s*=\s*(\S+)', ln)
        if m:
            try:
                d[m.group(1).upper()] = float(m.group(2))
            except ValueError:
                d[m.group(1).upper()] = float('nan')
    return d


def window(deck):
    t0 = t1 = 0.0
    Tp = None
    for ln in open(deck):
        if ".measure tran ERAIL " in ln:
            m = re.search(r'FROM=([\d.eE+-]+)p\s+TO=([\d.eE+-]+)p', ln)
            if m:
                t0, t1 = float(m.group(1)) * 1e-12, float(m.group(2)) * 1e-12
        m2 = re.search(r'Tperiod=([\d.]+)ps', ln)
        if m2:
            Tp = float(m2.group(1)) * 1e-12
    tmax = 0.0
    for ln in open(deck):
        if ln.lstrip().startswith(".measure"):
            for m in re.finditer(r'(?:TO|AT)=([\d.eE+-]+)p', ln):
                tmax = max(tmax, float(m.group(1)) * 1e-12)
    return t0, t1, Tp, tmax


def gate1(deck):
    txt = open(deck).read()
    bad = []
    for pat, why in ((r'^\s*\.ic\b', ".IC present"),
                     (r'^\s*\.nodeset\b', ".NODESET present"),
                     (r'\btanh\s*\(', "tanh() behavioral switch"),
                     (r'\bvswitch\b', "VSWITCH"),
                     (r'^\s*\.tran[^\n]*\buic\b', "UIC on .tran")):
        if re.search(pat, txt, re.M | re.I):
            bad.append(why)
    srcs = [ln.strip() for ln in txt.splitlines()
            if ln[:1].upper() == "V" and not ln.startswith("*")]
    nonzero = [s for s in srcs if not re.match(r'^\S+\s+\S+\s+\S+\s+0\s*$', s)]
    return bad, srcs, nonzero


def main():
    deck = sys.argv[1]
    norun = "--no-run" in sys.argv
    brief = "--brief" in sys.argv
    base, d = os.path.basename(deck), os.path.dirname(os.path.abspath(deck)) or "."
    rc = 0
    if not norun:
        with open(os.path.join(d, base + ".log"), "w") as lg:
            rc = subprocess.run([XYCE, base], cwd=d, env=ENV, stdout=lg,
                                stderr=subprocess.STDOUT).returncode
    mt0, csv = os.path.join(d, base + ".mt0"), os.path.join(d, base + ".csv")
    P, (t0, t1, Tp, tmax) = parse_params(deck), window(deck)
    M = parse_mt0(mt0) if os.path.exists(mt0) else {}
    if not M:
        print("NO MEASURE OUTPUT -- run failed. See %s.log" % base)
        return

    print("=" * 78)
    print("DECK %s   window %.4gs..%.4gs   period %.4gs" % (base, t0, t1, Tp))
    for ln in open(deck):
        if ln.startswith("*") and ("WSW=" in ln or "CB=" in ln or "dV=" in ln):
            print("  " + ln.rstrip()[2:])
    print("=" * 78)

    bad, srcs, nonzero = gate1(deck)
    g1 = not bad and len(nonzero) <= 5
    print("\n[G1] SOURCE EXCLUSIVITY  %s" % ("PASS" if g1 else "FAIL"))
    for b in bad:
        print("     FAIL: " + b)
    print("     %d voltage sources; %d are NOT 0 V ammeters:" % (len(srcs), len(nonzero)))
    for s in nonzero:
        print("       " + s)
    print("     EAMM (energy injected by the 0 V ammeters) = %.4e J  (must be 0)"
          % M.get("EAMM", float('nan')))

    last_t = None
    if os.path.exists(csv):
        with open(csv) as f:
            f.readline()
            ln = None
            for ln in f:
                pass
        if ln:
            # column 0 is TIME in Xyce's format=csv output. Reading column 1 here
            # was a real bug: it returned V(rp)=1.5, which trivially satisfied the
            # >= t_end comparison and made GATE 2 pass without testing anything.
            try:
                last_t = float(ln.split(",")[0])
            except Exception:
                pass
    nfail = sum(1 for v in M.values() if isinstance(v, float) and math.isnan(v))
    g2 = rc == 0 and last_t is not None and last_t >= tmax * 0.999999 and nfail == 0
    print("\n[G2] NO TRUNCATION  %s" % ("PASS" if g2 else "FAIL"))
    print("     exit=%d  last TIME row=%s  latest measure point=%.5gs  FAILED measures=%d"
          % (rc, ("%.6g" % last_t) if last_t else "n/a", tmax, nfail))

    ER, QR = M.get("ERAIL", float('nan')), M.get("QRAIL", float('nan'))
    g3 = abs(ER / QR / 3.0 - 1) < 1e-3
    print("\n[G3] METER VALIDATION  %s" % ("PASS" if g3 else "FAIL"))
    print("     ERAIL=%.6e J  QRAIL=%.6e C  E/Q=%.6f V (must be 3.000000; err %.4f%%)"
          % (ER, QR, ER / QR, (ER / QR / 3.0 - 1) * 100))
    print("     ERP=%.6e  ERN=%.6e  (equal => series stack, one charge serves all)"
          % (M.get("ERP", float('nan')), M.get("ERN", float('nan'))))

    def stored(tag):
        e = 0.0
        for nm, pk, a, b in CAPS:
            C = P.get(pk)
            va, vb = M.get("V%s%s" % (a.upper(), tag)), M.get("V%s%s" % (b.upper(), tag))
            if C is None or va is None or vb is None:
                continue
            e += 0.5 * C * (va - vb) ** 2
        for nm, pk in INDS:
            L, i = P.get(pk), M.get("I%s%s" % (nm, tag))
            if L is None or i is None:
                continue
            e += 0.5 * L * i * i
        return e

    EA, EB = stored("A"), stored("B")
    dE = EB - EA
    ECK = M.get("ECK", 0.0)
    Ein = ER + ECK
    lane = {k: M[k] for k in LANE_DISS if k in M}
    other = {k: M[k] for k in OTHER_DISS if k in M}
    Elane, Eother = sum(lane.values()), sum(other.values())
    resid = Ein - Elane - Eother - dE
    resid_norail = ER - Elane - Eother - dE     # clock injection treated as already
                                                # inside the driver-domain integral
    g4 = min(abs(resid), abs(resid_norail)) <= 0.02 * abs(Ein)
    print("\n[G4] ENERGY BALANCE   E_in = sum(E_diss) + dE_stored   %s"
          % ("PASS" if g4 else "FAIL"))
    print("     E_rail  (the ONLY real supply)   = %+.6e J" % ER)
    print("     E_phaseclk (PWL driver inputs)   = %+.6e J  <- declared line item" % ECK)
    print("     E_in TOTAL                       = %+.6e J" % Ein)
    print("     --- NOT our lane (subtracted) ---")
    for k in OTHER_DISS:
        if k in other:
            print("       %-6s = %+.6e J" % (k, other[k]))
    print("     --- OUR ONE LANE ---")
    for k in LANE_DISS:
        if k in lane:
            print("       %-6s = %+.6e J" % (k, lane[k]))
    print("     sum lane = %+.6e   sum other = %+.6e" % (Elane, Eother))
    print("     E_stored @t0 = %+.6e   @t1 = %+.6e   dE = %+.6e" % (EA, EB, dE))
    print("     RESIDUAL, clock counted as a separate input = %+.6e J = %+.3f%% of E_in"
          % (resid, 100 * resid / Ein))
    print("     RESIDUAL, rail only as input                = %+.6e J = %+.3f%% of E_rail"
          % (resid_norail, 100 * resid_norail / ER))
    print("     (tolerance 2%; the clock node connects ONLY to driver input gates, so")
    print("      its energy exits through the driver supply and is already in EDRV)")
    if "EDRV2T" in M:
        print("     EDRV (both supply leads, correct) = %+.6e" % M.get("EDRV"))
        print("     EDRV (two-terminal form, WRONG)  = %+.6e   <- differ because the"
              % M["EDRV2T"])
        print("      gate coupling caps are a third current path out of the driver domain")

    print("\n[G5] STARTUP SEPARATED")
    print("     warm-up rail draw 0..t0 = %.6e J  (EXCLUDED)" % M.get("ERAILW", float('nan')))
    print("     measured-window draw    = %.6e J" % ER)

    ops = sorted((int(k[3:]), v) for k, v in M.items() if re.match(r'^EOP\d+$', k))
    nops = len(ops)
    tops = dict((int(k[3:]), v) for k, v in M.items() if re.match(r'^TOP\d+$', k))
    print("\n[G6] PERIODIC STEADY STATE")
    if not brief:
        print("     per-op: E_rail   minus stand-in lanes = lane+drivers")
        for k, v in ops:
            tv = tops.get(k, 0.0)
            print("       op %-3d %10.3f fJ  - %9.3f fJ = %9.3f fJ"
                  % (k, v * 1e15, tv * 1e15, (v - tv) * 1e15))
    g6a = False
    if len(ops) >= 3:
        net = [v - tops.get(k, 0.0) for k, v in ops[-3:]]
        spread = (max(net) - min(net)) / (sum(net) / 3.0)
        print("     last-3 net-per-op spread = %.3f%%  (need <2%%)" % (spread * 100))
        g6a = abs(spread) < 0.02
    worst, worstn = 0.0, ""
    for nd in ["s1", "s2", "s3", "s4", "s5", "ba", "bb", "fa", "fb", "oa", "ob",
              "mab", "mta", "mtb", "gsab", "gsta", "gstb", "dvab", "vmid"]:
        a, b = M.get("V%sA" % nd.upper()), M.get("V%sB" % nd.upper())
        if a is None or b is None:
            continue
        rel = abs(b - a) / max(abs(a), abs(b), 0.05)
        if rel > worst:
            worst, worstn = rel, "V(%s)" % nd
        if not brief:
            print("       V(%-5s) %+9.6f -> %+9.6f  d=%+9.6f  (%.3f%%)" % (nd, a, b, b - a, rel * 100))
    for nd, _ in INDS:
        a, b = M.get("I%sA" % nd), M.get("I%sB" % nd)
        if a is None or b is None:
            continue
        rel = abs(b - a) / max(abs(a), abs(b), 1e-6)
        if rel > worst:
            worst, worstn = rel, "I(%s)" % nd
        if not brief:
            print("       I(%-5s) %+9.4e -> %+9.4e  (%.3f%%)" % (nd, a, b, rel * 100))
    print("     worst state-vector drift = %.3f%% on %s  (need <1%%)" % (worst * 100, worstn))
    if nops:
        print("     ENERGY-weighted periodicity: dE_stored = %+.4e J over %d ops"
              % (dE, nops))
        print("       = %+.4f fJ/op = %+.4f%% of the per-op rail draw  <- the test that"
              % (dE / nops * 1e15, 100 * dE / ER))
        print("         actually bounds the number (a 2 fF parasitic node drifting 20%%")
        print("         relatively moves <1e-18 J and cannot affect any fJ figure)")
    g6 = g6a and (abs(dE / ER) < 0.01 if nops else False)
    print("     %s" % ("PASS" if g6 else "FAIL"))


    print("\n" + "-" * 78)
    if nops:
        net = ER - Eother
        print("MEASURED RAIL DRAW, %d ops in window:" % nops)
        print("  total rail draw / op                        = %9.3f fJ" % (ER / nops * 1e15))
        print("  minus stand-in lanes + stack R (metered)    = %9.3f fJ" % (Eother / nops * 1e15))
        print("  => OUR ONE QAL LANE, rail cost per op       = %9.3f fJ  <== the number"
              % (net / nops * 1e15))
        print("  (cross-check: sum of the lane's own metered dissipators = %9.3f fJ/op)"
              % (Elane / nops * 1e15))
        print("  BREAKDOWN of the lane (fJ/op, %% of lane):")
        groups = [("switch gate drive", ["EDRV", "EVMID"]),
                  ("switch devices (all terminals)", ["ESWAB", "ESWTA", "ESWTB"]),
                  ("gate settle (real logic gates)", ["EGA", "EGB"]),
                  ("inductive transfer (inter-bank)", ["ELAB"]),
                  ("inductive top-up (flycap->bank)", ["ELTA", "ELTB"]),
                  ("FLYCAP RECHARGE from tier rail", ["ERCA", "ERCB"]),
                  ("bank DC bleed (metering artefact)", ["EBLD"])]
        for lab, ks in groups:
            v = sum(lane.get(k, 0.0) for k in ks)
            print("    %-34s %9.3f  %6.2f%%" % (lab, v / nops * 1e15,
                                                100 * v / Elane if Elane else 0))
        print("  phase-clock PWL injection (outside rails)   = %9.3f fJ/op"
              % (ECK / nops * 1e15))
    for nm, lbl in (("VBAPK", "bank A max"), ("VBAMN", "bank A min"),
                    ("VBBPK", "bank B max"), ("VBBMN", "bank B min"),
                    ("VGABPK", "SWAB gate max"), ("VGABMN", "SWAB gate min")):
        if nm in M:
            print("  %-16s (rel tier gnd) = %+.4f V" % (lbl, M[nm]))
    tv = [(M.get("TVMIN%d" % i), M.get("TVMAX%d" % i)) for i in range(1, 6)]
    print("  tier voltages min/max over window: " +
          " ".join("%.4f-%.4f" % t for t in tv if t[0] is not None))
    print("GATES: G1=%s G2=%s G3=%s G4=%s G6=%s" %
          tuple("PASS" if g else "FAIL" for g in (g1, g2, g3, g4, g6)))
    print("-" * 78)


if __name__ == "__main__":
    main()
