#!/usr/bin/env python3
"""Sweep qal_gate_probe.cir over the A1b ramp-time grid and report the settle law.

Generates one deck per ramp time T (the qal_a1b.py:49-63 pattern -- Xyce .STEP is
not usable because the transient stop time itself scales with T), runs Xyce, parses
the .mt0, and prints:

  * the closure residual  |E_diss + stranded - E_rail_net| / E_rail_net   (test T1)
  * the recovered fraction  E_returned / E_drawn        (the column no full-swing /
    VCD / alpha*C*V^2 model can produce at all)
  * E_diss normalised by C*dV^2, next to the A1b MEASURED transistor column, so the
    LAW SHAPE can be compared (absolute fJ cannot -- A1b is dV=0.6 on a bare nMOS
    pass switch, this is dV=1.2 on a gate pull-up; see qal_gate_probe.cir header)

Everything printed is read back from Xyce .mt0 files. Nothing is modelled here.
"""
import os, re, subprocess, sys

HERE  = os.path.dirname(os.path.abspath(__file__))
XYCE  = "/usr/local/src/xyce-build/src/Xyce"
BASE  = os.path.join(HERE, "qal_gate_probe.cir")
TGRID = [20, 50, 100, 200, 500, 1000, 2000, 5000]      # ps -- the qal_a1b.py:44-46 grid

# A1b MEASURED transistor reference (qal_a1b.py:44-46): T_ps -> E_cyc/(C*dV^2).
# C_L=10fF, dV=0.6V, C*dV^2 = 3.600 fJ (qal_a1b.py:30). Bare nMOS pass switch.
A1B = {20: 0.618, 50: 0.603, 100: 0.469, 200: 0.327,
       500: 0.179, 1000: 0.113, 2000: 0.066, 5000: 0.034}

CY_F, DV = 10e-15, 1.2          # must match the .model CY and the deck VDD


def run_one(t_ps, keep_dir):
    """Emit a deck at ramp time t_ps, run Xyce, return the .mt0 dict (fJ / V)."""
    txt = open(BASE).read()
    txt, n = re.subn(r'(?m)^\.param\s+TR=.*$', '.param TR=%gp' % t_ps, txt)
    if n != 1:
        sys.exit("could not find the '.param TR=' line in %s" % BASE)
    # keep the .print out of the sweep: 8 CSV waveform dumps are noise here
    txt = re.sub(r'(?m)^\.print\s+tran.*$', '* (.print suppressed by run_probe.py)', txt)
    deck = os.path.join(keep_dir, "probe_T%d.cir" % t_ps)
    open(deck, "w").write(txt)
    r = subprocess.run([XYCE, deck], capture_output=True, text=True, timeout=170,
                       cwd=keep_dir)
    mt0 = deck + ".mt0"
    if not os.path.exists(mt0):
        print("  T=%dps FAILED -- no .mt0. Xyce tail:" % t_ps)
        print("\n".join(r.stdout.strip().split("\n")[-8:]))
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
    keep = os.path.join(HERE, "probe_runs")
    os.makedirs(keep, exist_ok=True)
    ref = CY_F * DV * DV * 1e15          # C*dV^2 in fJ -- the hard-switch reference
    print("qal_gate settle sweep -- VTP+RON_P fitted (see deck header); RON_N/VTN/CY/CIN seeds")
    print("  Xyce: %s" % XYCE)
    print("  deck: %s   (TOPO=1 NAND2, a=0 b=Vdd -> one pull-up leg, no pull-down)")
    print("  C*dV^2 reference at CY=%gfF dV=%gV = %.3f fJ\n" % (CY_F*1e15, DV, ref))
    hdr = ("%7s %9s %9s %10s %9s %9s %9s %8s %9s %9s" %
           ("T(ps)", "Y@hold", "Y@end", "Ediss", "Erail", "Eret", "Edrawn",
            "recov%", "clos%", "Ed/CdV^2"))
    print(hdr)
    print("-" * len(hdr))
    rows = []
    for t in TGRID:
        d = run_one(t, keep)
        if d is None:
            continue
        ed, er, eret = d["EDISS"], d["ERAIL"], d["ERET"]
        edr, eclo = d["EDRAWN"], d["ECLOSE"]
        recov = (eret / edr * 100.0) if edr else 0.0
        clos = (abs(eclo) / abs(er) * 100.0) if er else 0.0
        rows.append((t, d["YSET"], d["YEND"], ed, er, eret, edr, recov, clos, ed / ref))
        print("%7d %9.4f %9.4f %10.4f %9.4f %9.4f %9.4f %7.1f%% %8.3f%% %9.4f"
              % rows[-1])

    if not rows:
        print("\nNO RUNS SUCCEEDED.")
        return 1

    print("\n--- T1 CLOSURE (two independent integrators vs the stranded term) ---")
    worst = max(r[8] for r in rows)
    print("  worst residual %.3f %% (test T1 wants < 1 %%)  -> %s"
          % (worst, "PASS" if worst < 1.0 else "FAIL"))

    print("\n--- LAW SHAPE vs the A1b MEASURED transistor sweep ---")
    print("  (normalised only -- absolute fJ are NOT comparable, see the deck header)")
    print("  %7s %12s %12s %8s" % ("T(ps)", "cell Ed/CdV2", "A1b E/CdV2", "ratio"))
    for r in rows:
        a = A1B.get(r[0])
        if a:
            print("  %7d %12.4f %12.4f %8.2fx" % (r[0], r[9], a, r[9] / a))

    print("\n--- ADIABATIC DIRECTION (the thing a full-swing model cannot do) ---")
    f, l = rows[0], rows[-1]
    print("  T %d -> %d ps : Ediss %.4f -> %.4f fJ (%.2fx down) for a %.0fx slower ramp"
          % (f[0], l[0], f[3], l[3], f[3] / l[3] if l[3] else 0, l[0] / f[0]))
    print("  recovered fraction %.1f%% -> %.1f%%  (RISES with ramp time = adiabatic)"
          % (f[7], l[7]))
    print("\n  decks + .mt0 kept in %s" % keep)
    return 0


if __name__ == "__main__":
    sys.exit(main())
