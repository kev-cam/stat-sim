#!/usr/bin/env python3
"""Track 3 deck generator: QAL -> sync receiver ("is a plain inverter the whole adapter?").

Every cell is an independent island: its own PWL driver, its own stage-1 and stage-2 VDD
sources (so stage-1 alone can be costed as the adapter), its own 2 fF load, and its own
1F integrators.  Integrators are t0-referenced at extraction time (the campaign's pedestal
trap: a 1F integrator carries a t=0 offset).
"""
import sys

# ---- envelope (ps) -----------------------------------------------------------
T_SETTLE = 100.0
T_EDGE   = 266.755223     # MEASURED QAL hop time, tg15p_zcs
T_HOLD   = 293.245        # park-measured park window (beat 580 - conduction 293) rounded
T_END    = 1200.0
T_A = T_SETTLE
T_B = T_SETTLE + T_EDGE
T_C = T_B + T_HOLD
T_D = T_C + T_EDGE
T_E = T_END - 5.0

VQAL = 0.6758936          # MEASURED QAL cell high level (== VBEND), tg15p_zcs
VSY  = 1.2                # synchronous rail

HDR = """QAL->sync boundary receiver transient (Track 3 H1)
.hdl "/usr/local/share/xyce/verilog-a/psp103/psp103.va"
.include "/usr/local/src/kestrel/sim/models/sg13g2_psp103_tt.lib"
.include "/usr/local/src/stat-sim/qal/sg13lv_compat.sp"
.OPTIONS TIMEINT METHOD=GEAR RELTOL=1e-6 ABSTOL=1e-15 CHGTOL=1e-17
"""

def pwl(name, node, vhi, edge):
    """rise/hold/fall envelope; edge in ps"""
    t1 = T_SETTLE
    t2 = T_SETTLE + edge
    t3 = T_C
    t4 = T_C + edge
    return (f"V{name} {node} 0 PWL(0 0 {t1}p 0 {t2}p {vhi} {t3}p {vhi} "
            f"{t4}p 0 {T_END}p 0)\n")

def integ(tag, expr):
    return (f"C{tag} {tag} 0 1\n"
            f"B{tag} 0 {tag} I={{ {expr} }}\n"
            f"R{tag} {tag} 0 0.01\n")

def cell(tag, vhi, edge, wp1, wn1, vdd, wp2="1.12u", wn2="0.74u", l1="0.13u",
         np1=1, nn1=1):
    """one boundary island.  returns (netlist, print-nodes, measure-lines)

    np1/nn1 put np1 (resp. nn1) IDENTICAL devices in parallel, which is how this
    harness reaches widths outside the shared geometry set without triggering a
    fresh PyMS .so build (the vae cache is keyed on the instance W).
    """
    q, o1, o2 = f"q{tag}", f"a{tag}", f"b{tag}"
    d1, d2 = f"d1{tag}", f"d2{tag}"
    n = pwl(f"Q{tag}", q, vhi, edge)
    n += f"VD1{tag} {d1} 0 {vdd}\n"
    n += f"VD2{tag} {d2} 0 {vdd}\n"
    for k in range(np1):
        n += f"XP1{tag}{k} {o1} {q} {d1} {d1} sg13_lv_pmos w={wp1} l={l1}\n"
    for k in range(nn1):
        n += f"XN1{tag}{k} {o1} {q} 0 0 sg13_lv_nmos w={wn1} l=0.13u\n"
    n += f"XP2{tag} {o2} {o1} {d2} {d2} sg13_lv_pmos w={wp2} l=0.13u\n"
    n += f"XN2{tag} {o2} {o1} 0 0 sg13_lv_nmos w={wn2} l=0.13u\n"
    n += f"CL{tag} {o2} 0 2f\n"
    # energies: supply-current integral x rail voltage (exact, rail is a constant source)
    n += integ(f"e1{tag}", f"-{vdd}*I(VD1{tag})")
    n += integ(f"e2{tag}", f"-{vdd}*I(VD2{tag})")
    # charge and energy the adapter draws BACK out of the QAL domain (its input load)
    n += integ(f"qi{tag}", f"-I(VQ{tag})")
    n += integ(f"ei{tag}", f"-V({q})*I(VQ{tag})")
    pr = [f"V({q})", f"V({o1})", f"V({o2})"]
    m = ""
    for nm, node in (("E1", f"e1{tag}"), ("E2", f"e2{tag}"),
                     ("QI", f"qi{tag}"), ("EI", f"ei{tag}")):
        for lbl, t in (("Z", 5.0), ("A", T_A), ("B", T_B), ("C", T_C),
                       ("S", T_C - 30.0), ("D", T_D), ("E", T_E)):
            m += f".measure tran {nm}{tag}_{lbl} FIND V({node}) AT={t}p\n"
    half = vhi / 2.0
    m += f".measure tran TIN{tag} WHEN V({q})={half:.6f} RISE=1\n"
    m += f".measure tran TO1{tag} WHEN V({o1})={vdd/2:.4f} FALL=1\n"
    m += f".measure tran TO2{tag} WHEN V({o2})={vdd/2:.4f} RISE=1\n"
    # functional resolve time: when stage 1 falls through the MEASURED trip point
    # of a standard downstream SG13G2 gate on the same rail (bd_dc: 0.6452 V at
    # 1.2 V, 0.4959 V at 0.9 V)
    trip = 0.6452 if abs(vdd - 1.2) < 1e-9 else (0.4959 if abs(vdd - 0.9) < 1e-9
                                                 else vdd / 2.0)
    m += f".measure tran TRSV{tag} WHEN V({o1})={trip:.4f} FALL=1\n"
    m += f".measure tran O1MIN{tag} MIN V({o1}) FROM={T_B}p TO={T_C}p\n"
    m += f".measure tran O1AT{tag} FIND V({o1}) AT={T_C-1}p\n"
    m += f".measure tran O2AT{tag} FIND V({o2}) AT={T_C-1}p\n"
    return n, pr, m

CELLS = {
    # tag : (v_high, edge_ps, wp1, wn1, vdd, n_pmos_parallel, n_nmos_parallel)
    "A": (VQAL, T_EDGE, "1.12u", "0.74u", 1.2, 1, 1),  # QAL level -> STANDARD receiver
    "B": (VSY,  T_EDGE, "1.12u", "0.74u", 1.2, 1, 1),  # sync level, SAME slope (level control for A)
    "C": (VQAL, T_EDGE, "0.28u", "0.74u", 1.2, 1, 1),  # skewed receiver (4x weaker pMOS)
    "D": (VQAL, T_EDGE, "0.15u", "1.48u", 1.2, 1, 1),  # strongly skewed receiver
    "E": (VQAL, T_EDGE, "1.12u", "0.74u", 0.9, 1, 1),  # standard receiver on a REDUCED rail
    "F": (VSY,  34.81,  "1.12u", "0.74u", 1.2, 1, 1),  # anchor check vs 10.0831 fJ
    "G": (VQAL, T_EDGE, "0.15u", "0.74u", 1.2, 1, 1),  # most-skewed shared-geometry receiver
    "H": (VSY,  T_EDGE, "0.15u", "1.48u", 1.2, 1, 1),  # sync level into D's sizing (level control for D)
    "K": (VQAL, T_EDGE, "0.15u", "1.48u", 0.9, 1, 1),  # skew AND reduced rail together
    "L": (VQAL, T_EDGE, "0.15u", "1.48u", 1.2, 1, 2),  # skew + 2x nMOS (2.96u, via parallel devices)
    "M": (VQAL, T_EDGE, "0.15u", "1.48u", 1.2, 1, 4),  # skew + 4x nMOS (5.92u) -- speed limit probe
}

def main(path):
    net, prs, ms = HDR, [], ""
    for tag, (vhi, edge, wp, wn, vdd, np1, nn1) in CELLS.items():
        n, pr, m = cell(tag, vhi, edge, wp, wn, vdd, np1=np1, nn1=nn1)
        net += f"* ---- cell {tag}: vhi={vhi} edge={edge}ps wp={wp}x{np1} wn={wn}x{nn1} vdd={vdd} ----\n"
        net += n
        prs += pr
        ms += m
    net += f".tran 0.1p {T_END}p 0 0.5p\n"
    net += ms
    # print in chunks so no line is absurdly long
    for i in range(0, len(prs), 8):
        kw = ".print tran" if i == 0 else "+"
        net += kw + " " + " ".join(prs[i:i+8]) + "\n"
    net += ".end\n"
    open(path, "w").write(net)
    print(f"wrote {path}: {len(net.splitlines())} lines, "
          f"{6*4} devices, T_A={T_A} T_B={T_B} T_C={T_C} T_D={T_D} T_E={T_E}")

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "bd_rx.cir")
