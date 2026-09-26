#!/usr/bin/env python3
"""Dual-rail ECRL cell: logic check + T4(c) data-independence GO/NO-GO + T sweep.

T4(c) (qal_twobank.py:24-32, qal_a1f_inductive.py:76) is a GO/NO-GO, not a
tolerance: if the dual-rail cell's per-beat rail charge is data-MODULATED, the
fixed Cfly top-up cannot land every bank at dV and the whole QAL power-delivery
story fails. Transistor measurement was single-rail 100 % modulated, dual-rail 0 %.
Here we measure the spread of E_drawn across all four input patterns.

Everything printed is read back from Xyce .mt0 files.
"""
import os, re, subprocess, sys

HERE  = os.path.dirname(os.path.abspath(__file__))
XYCE  = "/usr/local/src/xyce-build/src/Xyce"
BASE  = os.path.join(HERE, "qal_gate_dr_probe.cir")
KEEP  = os.path.join(HERE, "probe_runs")
TGRID = [200, 500, 1000, 2000, 5000]
CY_F, DV = 10e-15, 1.2


def run(tag, t_ps, av, bv):
    txt = open(BASE).read()
    txt, n1 = re.subn(r'(?m)^\.param\s+TR=.*$', '.param TR=%gp' % t_ps, txt)
    txt, n2 = re.subn(r'(?m)^\.param\s+AV=.*$', '.param AV=%d BV=%d' % (av, bv), txt)
    if n1 != 1 or n2 != 1:
        sys.exit("could not patch TR/AV in %s" % BASE)
    deck = os.path.join(KEEP, "dr_%s.cir" % tag)
    open(deck, "w").write(txt)
    mt0 = deck + ".mt0"
    if os.path.exists(mt0):
        os.remove(mt0)
    r = subprocess.run([XYCE, deck], capture_output=True, text=True, timeout=170, cwd=KEEP)
    if not os.path.exists(mt0):
        print("  %s FAILED. Xyce tail:" % tag)
        print("\n".join(r.stdout.strip().split("\n")[-6:]))
        return None
    d = {}
    for ln in open(mt0):
        m = re.match(r'\s*(\w+)\s*=\s*(\S+)', ln)
        if m:
            try:
                d[m.group(1).upper()] = float(m.group(2))
            except ValueError:
                pass
    return d if "EDISS" in d else None


def main():
    os.makedirs(KEEP, exist_ok=True)
    ref = CY_F * DV * DV * 1e15
    print("qal_gate_dr (dual-rail ECRL AND2) -- UNFIT SEED PARAMETERS")
    print("  structure mirrors the transistor reference qal_ecrl_gate.py:56-64")
    print("  C*dV^2 per rail at CY=%gfF dV=%gV = %.3f fJ\n" % (CY_F * 1e15, DV, ref))

    print("--- LOGIC (yt must = a AND b at the rail hold) + T4(c) DATA-INDEPENDENCE ---")
    print("  %3s %3s %9s %9s %6s %10s %10s %10s %9s"
          % ("a", "b", "yt@hold", "yf@hold", "logic", "Ediss", "Edrawn", "Eret", "clos%"))
    draws, ok_logic = [], True
    for av, bv in [(0, 0), (0, 1), (1, 0), (1, 1)]:
        d = run("p%d%d" % (av, bv), 1000, av, bv)
        if d is None:
            ok_logic = False
            continue
        exp = av * bv
        got = 1 if d["YTSET"] > 0.6 * DV else 0
        good = (got == exp)
        ok_logic = ok_logic and good
        clos = abs(d["ECLOSE"]) / abs(d["ERAIL"]) * 100.0 if d["ERAIL"] else 0.0
        draws.append(d["EDRAWN"])
        print("  %3d %3d %9.4f %9.4f %6s %10.4f %10.4f %10.4f %8.3f%%"
              % (av, bv, d["YTSET"], d["YFSET"], "OK" if good else "FAIL",
                 d["EDISS"], d["EDRAWN"], d["EDRAWN"]-d["ERAIL"], clos))

    print("\n  logic: %s" % ("all 4 patterns correct" if ok_logic else "*** FAIL ***"))
    if len(draws) == 4:
        lo, hi = min(draws), max(draws)
        spread = (hi - lo) / ((hi + lo) / 2.0) * 100.0
        print("  T4(c) rail charge drawn per beat: min %.4f  max %.4f fJ" % (lo, hi))
        print("  spread = %.2f %% (GO/NO-GO wants < 2 %%)  -> %s"
              % (spread, "GO" if spread < 2.0 else "NO-GO"))

    print("\n--- ADIABATIC SIGNATURE vs ramp time (a=b=1) ---")
    print("  %7s %9s %9s %10s %10s %10s %8s %9s %9s"
          % ("T(ps)", "yt@hold", "yt@end", "Ediss", "Erail", "Eret", "recov%", "clos%", "Ed/CdV^2"))
    rows = []
    for t in TGRID:
        d = run("T%d" % t, t, 1, 1)
        if d is None:
            continue
        clos = abs(d["ECLOSE"]) / abs(d["ERAIL"]) * 100.0 if d["ERAIL"] else 0.0
        rec = (d["EDRAWN"] - d["ERAIL"]) / d["EDRAWN"] * 100.0 if d["EDRAWN"] else 0.0
        rows.append((t, d["YTSET"], d["YTEND"], d["EDISS"], d["ERAIL"], d["EDRAWN"]-d["ERAIL"],
                     rec, clos, d["EDISS"] / ref))
        print("  %7d %9.4f %9.4f %10.4f %10.4f %10.4f %7.1f%% %8.3f%% %9.4f" % rows[-1])

    if len(rows) >= 2:
        f, l = rows[0], rows[-1]
        print("\n  Ediss %.4f -> %.4f fJ (%.2fx down) for a %.1fx slower ramp"
              % (f[3], l[3], f[3] / l[3] if l[3] else 0, l[0] / f[0]))
        print("  recovered %.1f%% -> %.1f%%; stranded yt@end %.4f -> %.4f V"
              % (f[6], l[6], f[2], l[2]))
        worst = max(r[7] for r in rows)
        print("  T1 closure worst %.3f %% -> %s" % (worst, "PASS" if worst < 1.0 else "FAIL"))
    print("\n  decks + .mt0 kept in %s" % KEEP)
    return 0


if __name__ == "__main__":
    sys.exit(main())
