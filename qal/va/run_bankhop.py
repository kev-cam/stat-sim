#!/usr/bin/env python3
"""8-cell bank hop: behavioural qal_gate bank vs the MEASURED transistor row.

T0 ANCHOR: qal_isocurrent.json dV=1.0 row (SG13G2/PSP103, 8 real static
inverters on the receiving bank, fixed receiving-side disconnect, ZCS measured):
    L=277.8 nH, t_zcs=342.0 ps, Ipk=195.19 uA, V_A_end=0.04853,
    V_B_end=0.57632, E_hop=10.7416 fJ, E_hop_per_gate=1.34269 fJ
(qal_hop_corrected.json L=400/dV=1.0 is the companion: t_zcs=400.41 ps,
 E_hop=10.4246 fJ, per-gate 1.30308.)

TOPOLOGY (mirrors qal_hop_gates.py hop_deck): bank A (plain cap CA holding the
previous stage's charge at dV) -> L -> Rs -> behavioural transfer switch
(qal_hop) -> bank B, whose node IS the supply rail of 8 behavioural INV cells
(qal_gate TOPO=0), inputs alternating dV/0 exactly as bank(). The switch opens
at the MEASURED inductor-current zero (probe pass first, as probe_zero() --
the analytic pi*sqrt(LC) was measured 36% early on the transistor bank).

COMPOSITION CHOICES (record them, they are part of the residual):
 * CY=2f = the deck CLOAD per gate output; device parasitics on the output
   nodes are NOT modelled (README |7).
 * CBANK=28f deck-owned: the transistor bank's slow-ramp C_eff is 35.979 fF at
   dV=1.0 (qal_isocurrent.json), of which only ~8 fF (4 charging outputs x 2fF)
   is represented by the cells; the rest is switch/well/junction parasitics the
   behavioural cells do not model, so the DECK owns it as a linear cap. CA is
   set to the same 35.979 fF (identical banks, as the reference).
 * switch RON=15: the reference transmission gate is w=20u nMOS + 2x pMOS at
   Vg=1.5; qal_trackC.py:31 gives 60 ohm at w=10u/Vgs=1.2 scaling ~1/W -> ~30
   for the nMOS alone, roughly halved by the parallel pMOS. CJ=0 (CBANK owns
   all bank-node parasitics; never double-count, README |4.4).

ENERGY, integral-free (the '.measure INTEGRAL V(<B-source>)' under-report trap,
qal_isocurrent.py:38-40): E_hop = 0.5*CA*(V_Ai^2 - V_Af^2) - E_stored_B(end),
with E_stored_B computed EXACTLY in-netlist (all caps linear + the cells'
stranded charge): 0.5*CBANK*V(bkb)^2 + sum 0.5*CY*V(oi)^2. The cells' own ed
integrators give the gate/switch dissipation split for free, and the books must
close: E_outA = E_stored_B + E_diss_total + E_left_in_L_and_CA_ring (small).
"""
import os, re, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
XYCE = "/usr/local/src/xyce-build/src/Xyce"
KEEP = os.path.join(HERE, "probe_runs")

DV = 1.0
L_NH = 277.8
RS = 10.0
RON = 15.0
CA_F = 35.979e-15
CBANK_F = 28e-15
CY_F = 2e-15
MGATE = 8
T0 = 50.0            # ps, switch closes
REF = {"t_zcs": 342.0, "Ipk_uA": 195.19, "V_A_end": 0.04853,
       "V_B_end": 0.57632, "E_hop_fJ": 10.7416, "per_gate_fJ": 1.34269}


def head(t_half_ps=None, tend_ps=2400.0):
    """Common deck: banks, switch, inductor, 8 cells. t_half None = switch stays on."""
    # off level is -1.2 V, NOT 0: at ctl=0 the tanh soft switch still leaks
    # ~22 uS ((0-VON)/VTAU = -4); at -1.2 the residual conductance is ~1e-16 S.
    if t_half_ps is None:
        ctl = "VCT ctl 0 PWL(0 -1.2 %gp -1.2 %gp 1.2 %gp 1.2)" % (T0 - 2, T0, tend_ps)
    else:
        ctl = ("VCT ctl 0 PWL(0 -1.2 %gp -1.2 %gp 1.2 %gp 1.2 %gp -1.2)"
               % (T0 - 2, T0, T0 + t_half_ps, T0 + t_half_ps + 2))
    L = ["* behavioural 8-cell bank hop dV=%g L=%gnH" % (DV, L_NH),
         '.hdl "%s/qal_gate.va"' % HERE,
         '.hdl "%s/qal_hop.va"' % HERE,
         # VTP=0.50 fitted (stall anchor); RON_P=6229 fitted (A1b law @1ns);
         # NSS=1.85 fitted (cliff) -- hop measured INSENSITIVE to it (E_hop
         # -0.5%, t_zcs 0.0ps): the -72% is C(V), not conduction (README |4.6)
         ".model qm qal_gate TOPO=0 RON_N=2.5e3 RON_P=6229 VTN=0.35 VTP=0.50 NSS=1.85",
         "+ VREF=1.2 CY=2f CIN=2f CX=0.1f CW=0.1f GM0=1e-12 ESCALE=1e15",
         ".model hm qal_hop RON=%g VON=0.6 VTAU=0.15 CJ=0 GM0=1e-12 ESCALE=1e15" % RON,
         "CAP bka 0 %gf" % (CA_F * 1e15),
         "CBB bkb 0 %gf" % (CBANK_F * 1e15),
         "LT bka mid %gn" % L_NH,
         "RT mid sw %g" % RS,
         ctl,
         "YQAL_HOP XSW sw bkb ctl 0 edsw 0 hm"]
    for i in range(MGATE):
        vin = DV if (i % 2 == 0) else 0.0
        L.append("VI%d in%d 0 %g" % (i, i, vin))
        # per-instance ed/er/eq nodes -- NEVER share integrator nodes across
        # instances (they would parallel the 1F caps and read the MEAN)
        L.append("YQAL_GATE XG%d in%d in%d o%d bkb 0 ed%d er%d eq%d 0 qm"
                 % (i, i, i, i, i, i, i))
    # block totals as sums of per-instance current integrals
    L.append("BSED sed 0 V={" + "+".join("V(ed%d)" % i for i in range(MGATE)) + "}")
    # exact stored energy on bank B: deck cap + the cells' output charge
    L.append("BSTB stb 0 V={ 0.5*%g*V(bkb)*V(bkb)*1e15 + "
             % (CBANK_F * 1e15 / 1e15 * 1e0) +
             "+".join("0.5*%g*V(o%d)*V(o%d)*1e15" % (CY_F, i, i)
                      for i in range(MGATE)) + " }")
    L.append(".ic V(bka)=%g V(bkb)=0" % DV)
    return L


def wait_xyce_free():
    for _ in range(120):
        if subprocess.run(["pgrep", "Xyce"], capture_output=True).stdout.strip() == b"":
            return
        time.sleep(5)
    sys.exit("Xyce never freed up")


def run(fn, lines):
    open(fn, "w").write("\n".join(lines) + "\n")
    wait_xyce_free()
    t0 = time.time()
    r = subprocess.run([XYCE, fn], capture_output=True, text=True, timeout=590, cwd=KEEP)
    wall = time.time() - t0
    return r, wall


def parse_mt0(fn):
    d = {}
    for ln in open(fn):
        m = re.match(r"\s*(\w+)\s*=\s*(\S+)", ln)
        if m:
            try:
                d[m.group(1).upper()] = float(m.group(2))
            except ValueError:
                pass
    return d


def probe_zero():
    """Switch held on; find the true I(LT) zero with the behavioural bank load."""
    fn = os.path.join(KEEP, "bh_probe.cir")
    lines = head(None, 2400.0) + [
        ".print tran I(LT) V(bkb) V(bka)",
        ".tran 0.1p 2400p UIC", ".end"]
    r, wall = run(fn, lines)
    rows = open(fn + ".prn").read().strip().split("\n")
    hdr = rows[0].split()
    ii = [i for i, h in enumerate(hdr) if "LT" in h.upper()][0]
    prev = None
    for ln in rows[1:]:
        f = ln.split()
        if len(f) <= ii:
            continue
        try:
            t, cur = float(f[1]), float(f[ii])
        except ValueError:
            continue
        if prev is not None and prev > 0 and cur <= 0 and t > 60e-12:
            return (t * 1e12 - T0), wall
        prev = cur
    return None, wall


def main():
    os.makedirs(KEEP, exist_ok=True)
    print("behavioural 8-cell bank hop, dV=%g, L=%gnH, Rs=%g, RON=%g" % (DV, L_NH, RS, RON))
    th, wall_probe = probe_zero()
    if th is None:
        sys.exit("no inductor-current zero found")
    print("  probe pass: I(LT) zero at t_half = %.2f ps (transistor MEASURED %.1f ps)"
          % (th, REF["t_zcs"]))
    tend = T0 + th + 500.0
    fn = os.path.join(KEEP, "bh_hop.cir")
    lines = head(th, tend) + [
        ".tran 0.1p %gp UIC" % tend,
        ".measure tran VBPK  MAX V(bkb) FROM=%gp TO=%gp" % (T0, tend),
        ".measure tran VBEND FIND V(bkb) AT=%gp" % (tend - 5),
        ".measure tran VAEND FIND V(bka) AT=%gp" % (tend - 5),
        ".measure tran IPK   MAX I(LT) FROM=0 TO=%gp" % tend,
        ".measure tran ESTB  FIND V(stb) AT=%gp" % (tend - 5),
        ".measure tran EDGAT FIND V(sed) AT=%gp" % (tend - 5),
        ".measure tran EDSW  FIND V(edsw) AT=%gp" % (tend - 5),
        ".measure tran O0END FIND V(o0)  AT=%gp" % (tend - 5),
        ".measure tran O1END FIND V(o1)  AT=%gp" % (tend - 5),
        ".end"]
    r, wall_hop = run(fn, lines)
    mt0 = fn + ".mt0"
    if not os.path.exists(mt0):
        print(r.stdout[-2000:])
        sys.exit("hop run failed")
    d = parse_mt0(mt0)
    e_outa = 0.5 * CA_F * (DV * DV - d["VAEND"] ** 2) * 1e15
    e_stb = d["ESTB"]
    e_hop = e_outa - e_stb
    e_diss = d["EDGAT"] + d["EDSW"]
    print("\n%22s %12s %12s" % ("", "model", "transistor"))
    for k, mv, rv in [("t_zcs (ps)", th, REF["t_zcs"]),
                      ("Ipk (uA)", d["IPK"] * 1e6, REF["Ipk_uA"]),
                      ("V_A_end (V)", d["VAEND"], REF["V_A_end"]),
                      ("V_B_end (V)", d["VBEND"], REF["V_B_end"]),
                      ("E_hop (fJ)", e_hop, REF["E_hop_fJ"]),
                      ("per gate (fJ)", e_hop / MGATE, REF["per_gate_fJ"])]:
        print("%22s %12.4f %12.4f   (%+.1f%%)" % (k, mv, rv, (mv / rv - 1) * 100))
    print("\n  split (model bonus): E_outA=%.4f fJ, E_stored_B=%.4f, "
          "E_diss gates=%.4f + switch=%.4f" % (e_outa, e_stb, d["EDGAT"], d["EDSW"]))
    resid = e_outa - e_stb - e_diss
    print("  closure: E_outA - E_stored - E_diss = %.4f fJ (ring/inductor residue)" % resid)
    print("  settled outputs: o0(in=%g)=%.4f  o1(in=0)=%.4f" % (DV, d["O0END"], d["O1END"]))
    print("  wall: probe %.1fs, hop %.1fs" % (wall_probe, wall_hop))


if __name__ == "__main__":
    main()
