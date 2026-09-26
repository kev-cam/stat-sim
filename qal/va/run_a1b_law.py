#!/usr/bin/env python3
"""A1b settle-law validation of qal_gate in the NON-COLLAPSING configuration.

WHY THIS CONFIGURATION (and not the plain probe): the A1b anchor
(qal_a1b.py:20-36) is a bare nMOS pass switch whose gate is HELD ON while an
ideal trapezoid rail ramps up and back down; its network returns to its initial
state, so E_cyc == dissipation. A single-ended pMOS-pull-up QAL gate is NOT that
vehicle: its overdrive collapses with the rail and it strands charge at |Vtp|
every beat (skeptic audit, wf whti2g8l3, and qal_nand_adiabatic.py:21-25). So
the LAW comparison must pin the pull-up gate at -1.2 V (overdrive can never
collapse) -- the switch-held-on situation -- and the Vt stall is validated
SEPARATELY (T4(b), run_probe.py at the fitted VTP).

ANCHOR CONVENTION -- corrected per the skeptic audit: the campaign brief's
"3.4%@5ns / 5.6%@1ns / 11%@500ps of 1/2 C dV^2" MIXES E/(C*dV^2) with RC/T and
its 500 ps value is hand-written wrong even as RC/T (qal_a1b.py:36 wrote 0.11
where the table gives 17.9%/2 = 0.0895). The anchor used here is the MEASURED
E_cyc/(C*dV^2) column of qal_a1b.py:44-46 directly:
    17.9% @500ps, 11.3% @1ns, 3.4% @5ns   (and 32.7% @200ps, 6.6% @2ns)
and the law is E_cyc = 2*(RC/T)*C*dV^2 (qal_a1b.py:15,:72) -- NOT half of it.

FIT DISCIPLINE: RON_P is fitted at T=1ns ONLY (a single 1-D scale -- in the
adiabatic regime Ediss is ~linear in RON_P). Every other T is a HOLDOUT.

Usage: run_a1b_law.py [RON_P_ohm]      (default: the seed 5.0e3)
"""
import os, re, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
XYCE = "/usr/local/src/xyce-build/src/Xyce"
KEEP = os.path.join(HERE, "probe_runs")
TGRID = [200, 500, 1000, 2000, 5000]
A1B = {200: 0.327, 500: 0.179, 1000: 0.113, 2000: 0.066, 5000: 0.034}
CY_F, DV = 10e-15, 1.2
FIT_T = 1000            # RON_P is fitted here; all other T are holdouts

DECK = """* qal_gate A1b-law probe, NON-COLLAPSING pull-up (gate pinned -1.2V) T=%(T)dp
.hdl "%(here)s/qal_gate.va"
.param TR=%(T)dp
.param VDD=1.2 CYF=10e-15 ESC=1e15
.param H='2*TR' TEND='5*TR' TMEAS='4.8*TR' THOLD='2*TR'
* VTP=0.50 is the T4(b)-fitted stall; irrelevant here (overdrive pinned on).
* RON_P: fitted at T=1ns against A1b E/(C*dV^2)=0.113, holdouts elsewhere.
* NSS=1.85 (fitted, cliff): also irrelevant here -- overdrive >= 0.7V keeps the
* softplus in its linear region; this grid measured BIT-IDENTICAL pre/post tail.
.model qm qal_gate TOPO=1 RON_N=2.5e3 RON_P=%(ronp)g VTN=0.35 VTP=0.50 NSS=1.85
+ VREF=1.2 CY=10f CIN=2f CX=0.1f CW=0.1f GM0=1e-12 ESCALE=1e15
VPC pc 0 PWL(0 0 {TR} {VDD} {TR+H} {VDD} {2*TR+H} 0 {TEND} 0)
* THE NON-COLLAPSING LINE: leg-a gate at -1.2V -> overdrive >= 0.7V always
VA a 0 -1.2
VB b 0 {VDD}
YQAL_GATE X1 a b y pc 0 ed er eq 0 qm
BEST  est  0 V={ 0.5*CYF*V(y)*V(y)*ESC }
BECLO eclo 0 V={ V(ed) + V(est) - V(er) }
BEDRW edrw 0 V={ V(er) + V(eq) }
.tran {TR/200} {TEND} UIC
.measure tran YSET   FIND V(y)    AT={THOLD}
.measure tran YEND   FIND V(y)    AT={TMEAS}
.measure tran EDISS  FIND V(ed)   AT={TMEAS}
.measure tran ERAIL  FIND V(er)   AT={TMEAS}
.measure tran ERET   FIND V(eq)   AT={TMEAS}
.measure tran EDRAWN FIND V(edrw) AT={TMEAS}
.measure tran ECLOSE FIND V(eclo) AT={TMEAS}
.end
"""

def wait_xyce_free():
    for _ in range(60):
        if subprocess.run(["pgrep", "Xyce"], capture_output=True).stdout.strip() == b"":
            return
        time.sleep(5)
    sys.exit("Xyce never freed up")

def run_one(t_ps, ronp):
    deck = os.path.join(KEEP, "nc_T%d.cir" % t_ps)
    open(deck, "w").write(DECK % {"T": t_ps, "here": HERE, "ronp": ronp})
    wait_xyce_free()
    subprocess.run([XYCE, deck], capture_output=True, text=True, timeout=300, cwd=KEEP)
    d = {}
    for ln in open(deck + ".mt0"):
        m = re.match(r"\s*(\w+)\s*=\s*(\S+)", ln)
        if m:
            try:
                d[m.group(1).upper()] = float(m.group(2))
            except ValueError:
                pass
    return d

def main():
    ronp = float(sys.argv[1]) if len(sys.argv) > 1 else 5.0e3
    os.makedirs(KEEP, exist_ok=True)
    ref = CY_F * DV * DV * 1e15
    print("qal_gate vs A1b law, non-collapsing pull-up; RON_P=%g ohm" % ronp)
    print("  anchor: qal_a1b.py:44-46 measured E_cyc/(C*dV^2); FIT at T=%dps, others HOLDOUT" % FIT_T)
    print("%7s %9s %10s %10s %8s %9s %10s %9s %8s" %
          ("T(ps)", "Y@end", "Ediss(fJ)", "Erail(fJ)", "recov%", "clos%", "Ed/CdV^2", "A1b", "ratio"))
    for t in TGRID:
        d = run_one(t, ronp)
        recov = d["ERET"] / d["EDRAWN"] * 100.0 if d.get("EDRAWN") else 0.0
        clos = abs(d["ECLOSE"]) / abs(d["ERAIL"]) * 100.0 if d.get("ERAIL") else 0.0
        norm = d["EDISS"] / ref
        tag = "FIT" if t == FIT_T else "holdout"
        print("%7d %9.4f %10.4f %10.4f %7.1f%% %8.3f%% %10.4f %9.4f %7.2fx  %s" %
              (t, d["YEND"], d["EDISS"], d["ERAIL"], recov, clos, norm, A1B[t], norm / A1B[t], tag))

if __name__ == "__main__":
    main()
