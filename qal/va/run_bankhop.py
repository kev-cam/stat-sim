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
import math, os, re, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
XYCE = "/usr/local/src/xyce-build/src/Xyce"
KEEP = os.path.join(HERE, "probe_runs")

DV = 1.0
L_NH = 277.8
RS = 10.0
RON = 15.0
CA_F = 35.979e-15
CBANK_F = 28e-15    # (v2 linear deck cap -- superseded by the nonlinear C(V) below)
CY_F = 2e-15
MGATE = 8
T0 = 50.0            # ps, switch closes
REF = {"t_zcs": 342.0, "Ipk_uA": 195.19, "V_A_end": 0.04853,
       "V_B_end": 0.57632, "E_hop_fJ": 10.7416, "per_gate_fJ": 1.34269}

# --- v3 NONLINEAR bank C(V) (qal_bankcap.va), FITTED to the STATIC slow-ramp
#     calibration curve ONLY (characterization, NOT the hop -- the hop stays a
#     holdout).  Constrained charge fit (cv3/fit_q.py): CT set so Q(dV=1.0)
#     matches the measured operating-point charge EXACTLY; (C0,VK) fit the shape;
#     W=NSS*PHIT carried from the conduction fit (NOT refit). C0 == measured
#     C_quiet floor (~23.2 fF) to ~1 fF. --------------------------------------
WV = 1.85 * 0.02585                                  # = 0.047823 V
# PEAKED C(V): floor + plateau-step + inversion-PEAK bump (measured C_inc spikes
# to ~78 fF at the 0.43-0.49 V inversion knee, which a monotone softplus misses).
# Fit cv3/fit_peak.py; Q(dV=1.0) exact; C0 = measured C_quiet floor (23.2 fF).
BCA = dict(C0=23.200e-15, CT=12.964e-15, VK=0.3720, WV=WV,
           CP=71.315e-15, VA=0.4278, VB=0.4930, WP=0.0119)   # bank A: full C(V), no cells
BCB = dict(C0=23.200e-15, CT=1.823e-15,  VK=0.1500, WV=WV,
           CP=72.378e-15, VA=0.4141, VB=0.4588, WP=0.0100)   # bank B floor: cells add the rest


def _cinc(v, p):
    z = (v - p["VK"]) / p["WV"]
    s = 1.0/(1.0+math.exp(-z)) if z >= 0 else math.exp(z)/(1.0+math.exp(z))
    za = (v - p["VA"]) / p["WP"]
    sa = 1.0/(1.0+math.exp(-za)) if za >= 0 else math.exp(za)/(1.0+math.exp(za))
    zb = (v - p["VB"]) / p["WP"]
    sb = 1.0/(1.0+math.exp(-zb)) if zb >= 0 else math.exp(zb)/(1.0+math.exp(zb))
    return p["C0"] + p["CT"]*s + p["CP"]*(sa - sb)


def estored(V, p, n=4000):
    """EXACT stored energy of the qal_bankcap at V: E(V)=int_0^V u C_inc(u) du
    (Q is a state function, so this is a deterministic function of the params --
    the same route qal_hop_gates.py:225 uses on the measured curve)."""
    if V <= 0:
        return 0.0
    h = V / n
    e = 0.0
    for i in range(n + 1):
        u = i * h
        w = 0.5 if (i == 0 or i == n) else 1.0
        e += w * u * _cinc(u, p) * h
    return e


def head(t_half_ps=None, tend_ps=2400.0):
    """Common deck: banks, switch, inductor, 8 cells. t_half None = switch stays on."""
    # off level is -1.2 V, NOT 0: at ctl=0 the tanh soft switch still leaks
    # ~22 uS ((0-VON)/VTAU = -4); at -1.2 the residual conductance is ~1e-16 S.
    if t_half_ps is None:
        ctl = "VCT ctl 0 PWL(0 -1.2 %gp -1.2 %gp 1.2 %gp 1.2)" % (T0 - 2, T0, tend_ps)
    else:
        ctl = ("VCT ctl 0 PWL(0 -1.2 %gp -1.2 %gp 1.2 %gp 1.2 %gp -1.2)"
               % (T0 - 2, T0, T0 + t_half_ps, T0 + t_half_ps + 2))
    def bcmodel(name, p):
        return (".model %s qal_bankcap C0=%g CT=%g VK=%g WV=%g CP=%g VA=%g VB=%g WP=%g GM0=1e-12"
                % (name, p["C0"], p["CT"], p["VK"], p["WV"], p["CP"], p["VA"], p["VB"], p["WP"]))
    L = ["* behavioural 8-cell bank hop dV=%g L=%gnH -- v3 NONLINEAR bank C(V)" % (DV, L_NH),
         '.hdl "%s/qal_gate.va"' % HERE,
         '.hdl "%s/qal_hop.va"' % HERE,
         '.hdl "%s/qal_bankcap.va"' % HERE,
         # VTP=0.50 fitted (stall anchor); RON_P=6229 fitted (A1b law @1ns);
         # NSS=1.85 fitted (cliff). v2 showed the hop is INSENSITIVE to conduction
         # (E_hop -0.5%, t_zcs 0.0ps): the -72% was pinned on the LINEAR bank
         # plant -> v3 replaces both banks with the nonlinear qal_bankcap C(V).
         ".model qm qal_gate TOPO=0 RON_N=2.5e3 RON_P=6229 VTN=0.35 VTP=0.50 NSS=1.85",
         "+ VREF=1.2 CY=2f CIN=2f CX=0.1f CW=0.1f GM0=1e-12 ESCALE=1e15",
         ".model hm qal_hop RON=%g VON=0.6 VTAU=0.15 CJ=0 GM0=1e-12 ESCALE=1e15" % RON,
         bcmodel("bca", BCA),   # bank A: full measured C(V), no cells
         bcmodel("bcb", BCB),   # bank B: parasitic floor + sub-knee; 8 cells add the rest
         "YQAL_BANKCAP XCA bka 0 bca",
         "YQAL_BANKCAP XCB bkb 0 bcb",
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
    # CELLS' stranded charge on bank B (the bank-cap C(V) stored energy is added
    # in python via the EXACT quadrature estored() -- Q(V) is a state function so
    # its stored energy is deterministic, not 0.5 C V^2). fJ.
    L.append("BSTBG stbg 0 V={ "
             + "+".join("0.5*%g*V(o%d)*V(o%d)*1e15" % (CY_F, i, i)
                        for i in range(MGATE)) + " }")
    # DIRECT (fit-independent) cross-check of energy leaving bank A: integrate
    # V(bka)*I(LT) on a 1F cap (accurate, unlike .measure INTEGRAL which
    # under-reports -- README |4.6). I(LT) flows bka->mid = charge leaving A.
    L.append("BPA pa 0 V={ V(bka)*I(LT) }")
    L.append("CIA eia 0 1")
    L.append("BIA 0 eia I={ V(pa) }")
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
        ".measure tran ESTBG FIND V(stbg) AT=%gp" % (tend - 5),
        ".measure tran EDGAT FIND V(sed) AT=%gp" % (tend - 5),
        ".measure tran EDSW  FIND V(edsw) AT=%gp" % (tend - 5),
        ".measure tran EOUTAD FIND V(eia) AT=%gp" % (tend - 5),
        ".measure tran O0END FIND V(o0)  AT=%gp" % (tend - 5),
        ".measure tran O1END FIND V(o1)  AT=%gp" % (tend - 5),
        ".end"]
    r, wall_hop = run(fn, lines)
    mt0 = fn + ".mt0"
    if not os.path.exists(mt0):
        print(r.stdout[-2000:])
        sys.exit("hop run failed")
    d = parse_mt0(mt0)
    # energy leaving bank A: the NONLINEAR stored-energy drop as A drains DV->VAEND
    e_outa = (estored(DV, BCA) - estored(d["VAEND"], BCA)) * 1e15
    e_outa_direct = abs(d["EOUTAD"]) * 1e15         # fit-independent cross-check
    # stored on bank B: nonlinear bank-cap C(V) at VBEND + the cells' stranded charge
    e_stb_cap = estored(d["VBEND"], BCB) * 1e15
    e_stb = e_stb_cap + d["ESTBG"]
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
    print("\n  V_B_peak (V)  %12.4f %12.4f   (%+.1f%%)"
          % (d["VBPK"], 0.611, (d["VBPK"] / 0.611 - 1) * 100))
    print("\n  split: E_outA=%.4f fJ (direct-integrator cross-check %.4f, %.1f%%), "
          "E_stored_B=%.4f (cap %.4f + cells %.4f), E_diss gates=%.4f + switch=%.4f"
          % (e_outa, e_outa_direct, (e_outa_direct / e_outa - 1) * 100 if e_outa else 0,
             e_stb, e_stb_cap, d["ESTBG"], d["EDGAT"], d["EDSW"]))
    resid = e_outa - e_stb - e_diss
    print("  closure: E_outA - E_stored - E_diss = %.4f fJ (ring/inductor residue)" % resid)
    print("  settled outputs: o0(in=%g)=%.4f  o1(in=0)=%.4f" % (DV, d["O0END"], d["O1END"]))
    print("  wall: probe %.1fs, hop %.1fs" % (wall_probe, wall_hop))


if __name__ == "__main__":
    main()
