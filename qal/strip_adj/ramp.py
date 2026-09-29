#!/usr/bin/env python3
"""ADJUDICATION DECK: rail-ramp-rate sweep.

The two runs disagree on the static o21ai cell floor.  Their harnesses differ in
ONE way that matters and neither controlled for it:

  PRIMARY  qal/strip/cellfloor.py : rail = PWL 0 -> rail in 2 ps, then held.
  SKEPTIC  qal/strip_skept/gen_settle.py : rail = DC constant at full value from t=0.

A 2 ps edge is ~30x faster than the committed tank-fed hop (~67 ps) and ~50-100x
faster than a 150-300 ps QAL beat.  A DC source has no edge at all.  Neither is
the QAL condition.  This deck sweeps the ramp and holds everything else fixed.

Also fixed here, and wrong in both runs' cell-floor decks: EVERY node starts at
0 V, internal tree/stack nodes included.  That is what "no precharge device, the
ramping rail is the precharge" actually means.  The primary .ic'd only outputs;
the skeptic .ic'd only outputs while holding the rail at full value from t=0,
which lets the DC solve pre-charge the internal nodes inconsistently.

Inputs are RAIL-REFERENCED and ramp WITH the rail (the real chain condition).
"""
import os, re, subprocess, sys, time, json

HERE = os.path.dirname(os.path.abspath(__file__))
XYCE = "/usr/local/src/xyce-build/src/Xyce"
CACHE = os.path.join(HERE, "vae_cache_strip")
ENV = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS",
           PYMS_VAE_CACHE=CACHE)
HDR = """.hdl "/usr/local/share/xyce/verilog-a/psp103/psp103.va"
.include "/usr/local/src/kestrel/sim/models/sg13g2_psp103_tt.lib"
.include "/usr/local/src/stat-sim/qal/sg13lv_compat.sp"
.OPTIONS TIMEINT METHOD=GEAR RELTOL=1e-6 ABSTOL=1e-15 CHGTOL=1e-17
"""
WP, WN = 1.12, 0.74
L = 0.13
TEND = 3000.0

# o21ai:  Y = !((A1+A2) . B1)
def fn(a1, a2, b1):
    return 0 if ((a1 or a2) and b1) else 1


def static(inst, rail, q, ins):
    """sg13g2_o21ai_1 structure, l=0.13u (the anchor cell, stronger device).
    pMOS internal node cap referenced to the RAIL (n-well is the rail: this is
    the physically correct reference, and it is the coupling path the ramp
    sweep is probing).  nMOS internal node cap to ground (p-substrate)."""
    n14, n1 = inst + "n14", inst + "n1"
    a1, a2, b1 = ins
    return [
        f"XP0{inst} {n14} {a1} {rail} {rail} sg13_lv_pmos w={WP}u l={L}u",
        f"XP1{inst} {q} {a2} {n14} {rail} sg13_lv_pmos w={WP}u l={L}u",
        f"XP2{inst} {q} {b1} {rail} {rail} sg13_lv_pmos w={WP}u l={L}u",
        f"XN0{inst} {n1} {a2} 0 0 sg13_lv_nmos w={WN}u l={L}u",
        f"XN2{inst} {n1} {a1} 0 0 sg13_lv_nmos w={WN}u l={L}u",
        f"XN1{inst} {q} {b1} {n1} 0 sg13_lv_nmos w={WN}u l={L}u",
        f"CI0{inst} {n14} {rail} 0.1f",
        f"CI1{inst} {n1} 0 0.1f",
    ], [n14, n1]


def strip(inst, rail, q, n, ins, insb, wxc):
    """nMOS tree f + nMOS tree f-bar + cross-coupled pMOS, source AND bulk on
    the rail.  Structure taken verbatim from the skeptic's cellsk.py emission
    (which the primary's cells.py matches): f  = q pulled down by B1.(A1|A2);
    f-bar = n pulled down by !B1 | (!A1.!A2)."""
    fi, gi = inst + "Fi", inst + "Gi"
    a1, a2, b1 = ins
    a1b, a2b, b1b = insb
    return [
        f"X{inst}F1 {q} {b1} {fi} 0 sg13_lv_nmos w={WN}u l={L}u",
        f"X{inst}F2 {fi} {a1} 0 0 sg13_lv_nmos w={WN}u l={L}u",
        f"X{inst}F3 {fi} {a2} 0 0 sg13_lv_nmos w={WN}u l={L}u",
        f"X{inst}G1 {n} {a1b} {gi} 0 sg13_lv_nmos w={WN}u l={L}u",
        f"X{inst}G2 {gi} {a2b} 0 0 sg13_lv_nmos w={WN}u l={L}u",
        f"X{inst}G3 {n} {b1b} 0 0 sg13_lv_nmos w={WN}u l={L}u",
        f"XXA{inst} {q} {n} {rail} {rail} sg13_lv_pmos w={wxc}u l={L}u",
        f"XXB{inst} {n} {q} {rail} {rail} sg13_lv_pmos w={wxc}u l={L}u",
        f"CIF{inst} {fi} 0 0.1f",
        f"CIG{inst} {gi} 0 0.1f",
    ], [fi, gi]


VECS = [(0, 0, 1), (1, 0, 1), (0, 1, 1), (1, 0, 0)]


def build(rail, tr):
    nl = [f"* ADJUDICATION ramp sweep: rail {rail:.4f} V, ramp {tr:g} ps",
          "* every node starts at 0 V (internal nodes included); inputs ramp WITH the rail",
          HDR.rstrip()]
    if tr <= 0:
        nl.append(f"VRAIL rail 0 {rail:.6f}")
    else:
        # ramp starts at t=0: no sharp PWL corner to trip step control, and
        # the DC operating point at rail=0 is still the all-zero state.
        nl.append(f"VRAIL rail 0 PWL(0 0 {tr:g}p {rail:.6f} "
                  f"{TEND*2:g}p {rail:.6f})")
    nl.append("RHI hi rail 0.001")
    ic, pr, meta = [], [], []
    for vec in VECS:
        vid = "".join(map(str, vec))
        exp = fn(*vec)
        # --- static control
        inst = f"s{vid}"
        ins = [f"A1{inst}", f"A2{inst}", f"B1{inst}"]
        sub, inodes = static(inst, "rail", f"q{inst}", ins)
        nl += sub + [f"Cq{inst} q{inst} 0 2f"]
        for nm, b in zip(ins, vec):
            nl.append(f"R{nm} {nm} {'hi' if b else '0'} 0.001")
        ic += [f"q{inst}"] + inodes
        pr.append(f"q{inst}")
        meta.append(dict(node=f"q{inst}", topo="static", vec=vid,
                         expect="HI" if exp else "LO"))
        # --- stripped, both sizings
        for wxc, wt in ((1.12, "112"), (0.56, "56")):
            inst = f"x{wt}{vid}"
            ins = [f"A1{inst}", f"A2{inst}", f"B1{inst}"]
            insb = [f"A1B{inst}", f"A2B{inst}", f"B1B{inst}"]
            sub, inodes = strip(inst, "rail", f"q{inst}", f"n{inst}",
                                ins, insb, wxc)
            nl += sub + [f"Cq{inst} q{inst} 0 2f", f"Cn{inst} n{inst} 0 2f"]
            for nm, b in zip(ins, vec):
                nl.append(f"R{nm} {nm} {'hi' if b else '0'} 0.001")
            for nm, b in zip(insb, vec):
                nl.append(f"R{nm} {nm} {'0' if b else 'hi'} 0.001")
            ic += [f"q{inst}", f"n{inst}"] + inodes
            pr += [f"q{inst}", f"n{inst}"]
            meta.append(dict(node=f"q{inst}", topo="strip" + wt, vec=vid,
                             expect="HI" if exp else "LO"))
            meta.append(dict(node=f"n{inst}", topo="strip" + wt, vec=vid,
                             expect="LO" if exp else "HI"))
    # NO .ic.  The rail PWL sits at 0 V until t=2 ps, so the DC operating point
    # IS the all-zero state -- every node, internal ones included, starts at 0
    # self-consistently.  That is what "the ramping rail is the precharge"
    # means, and it is strictly better than forcing nodes with .ic against a
    # DC solve that wants something else (which is what both runs did, and
    # which does not converge here at the first PWL breakpoint).
    if tr <= 0:
        nl.append(".ic " + " ".join(f"V({x})=0" for x in ic))
    for k in range(0, len(pr), 8):
        nl.append((".print tran format=noindex " if k == 0 else "+ ")
                  + " ".join(f"V({x})" for x in pr[k:k + 8]))
    nl.append("+ V(rail)")
    nl += [f".tran 1p {TEND:g}p 0 0.5p", ".end"]
    return nl, meta


def run(tag, nl):
    p = os.path.join(HERE, tag + ".cir")
    open(p, "w").write("\n".join(nl) + "\n")
    t0 = time.time()
    r = subprocess.run([XYCE, p], env=ENV, capture_output=True, text=True,
                       timeout=900)
    return p, r.returncode, time.time() - t0


if __name__ == "__main__":
    rail = float(sys.argv[1]); tr = float(sys.argv[2])
    tag = "rmp_r%s_t%s" % (("%.4f" % rail).replace(".", "p"), ("%g" % tr))
    nl, meta = build(rail, tr)
    json.dump(meta, open(os.path.join(HERE, tag + ".meta.json"), "w"))
    p, rc, w = run(tag, nl)
    print(tag, "rc=%d" % rc, "%.1fs" % w, flush=True)
