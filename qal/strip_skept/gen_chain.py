#!/usr/bin/env python3
"""SKEPTIC cascade: 6 depths x 4 cells, stripped vs static, on an IDEAL STIFF
RAIL.

This is NOT a reproduction of the committed tank-fed chain and makes no energy
claim.  It is deliberately MORE GENEROUS than tank-fed: the rail never droops,
never sags under the bank's switched capacitance, and is identical for both
topologies.  So if a topology fails to propagate HERE, it cannot propagate on a
tank-fed rail either -- the result is a fortiori.

Depth 1 is driven by ideal DC sources (the head).  For k > 1 the gate nets ARE
the predecessor bank's output nets: no flop, latch, buffer or level shifter, and
no ideal source anywhere past depth 1.  That makes every stage past the head
RAIL-REFERENCED by construction, which is the real chain condition.

Stripped cells take both polarities from the predecessor's q and qb -- i.e. the
FULLY DUAL-RAIL FABRIC, the regime most favourable to the stripped form and the
one its device-count tie depends on.

Wiring (following the campaign's rotating pattern so the bank state ROTATES
rather than alternating, which is what lets the deck catch a single-cell
outlier):  cell i of bank k takes A1 <- cell i, A2 <- cell i+2, B1 <- cell i+1
of bank k-1 (indices mod 4).
"""
import os, json, itertools
import cellsk as K

NC = 4          # cells per bank
ND = 6          # depths
HEAD = [0, 0, 1, 1]
CL = "2f"

HDR = """.hdl "/usr/local/share/xyce/verilog-a/psp103/psp103.va"
.include "/usr/local/src/kestrel/sim/models/sg13g2_psp103_tt.lib"
.include "/usr/local/src/stat-sim/qal/sg13lv_compat.sp"
.OPTIONS TIMEINT METHOD=GEAR RELTOL=1e-6 ABSTOL=1e-15 CHGTOL=1e-17
"""


def o21ai(a1, a2, b1):
    return 0 if ((a1 or a2) and b1) else 1


def golden():
    """Boolean evolution, computed independently of SPICE.

    banks[0] = HEAD = the INPUT pattern presented to depth 1.
    banks[k] = the OUTPUT pattern of depth k, for k = 1..ND.
    So the list has ND+1 entries and the expected output of depth k is
    banks[k], NOT banks[k-1].  (An earlier revision of this file used
    banks[k-1] and so labelled every depth with its predecessor's pattern;
    that shifted every expectation by one stage and made meanHI and meanLO
    average over the same mixed set, which read out as every node sitting at
    rail/2.  The netlist was correct; only the expectation map was wrong.)
    """
    banks = [list(HEAD)]
    for k in range(1, ND + 1):
        prev = banks[-1]
        cur = []
        for i in range(NC):
            cur.append(o21ai(prev[i], prev[(i + 2) % NC], prev[(i + 1) % NC]))
        banks.append(cur)
    return banks


def build(topo, rail, wxc="1.12u"):
    g = golden()
    nl = [f"* SKEPT cascade, topo={topo} rail={rail:.4f} wxc={wxc}",
          "* ideal stiff rail: DECLARED, and deliberately generous to both arms",
          HDR.rstrip()]
    nl.append("VRAIL rail 0 %.6f" % rail)
    nl.append("RHI hi rail 0.001")
    meta = []
    for k in range(ND):
        for i in range(NC):
            inst = f"{'x' if topo=='strip' else 's'}k{k+1}c{i}"
            q = f"q{inst}"
            qb = f"n{inst}"
            if topo == "strip":
                sub, n = K.strip_cell("o21ai", inst, "rail", q, qb, wxc)
            else:
                sub, n = K.static_o21ai(inst, "rail", q)
            nl += sub
            nl.append(f"C{q} {q} 0 {CL}")
            if topo == "strip":
                nl.append(f"C{qb} {qb} 0 {CL}")
            # drive the three inputs
            srcmap = [("A1", i), ("A2", (i + 2) % NC), ("B1", (i + 1) % NC)]
            for nm, j in srcmap:
                if k == 0:
                    lvl = "hi" if g[0][j] else "0"
                    nl.append(f"R{nm}{inst} {nm}{inst} {lvl} 0.001")
                    if topo == "strip":
                        lvlb = "0" if g[0][j] else "hi"
                        nl.append(f"R{nm}B{inst} {nm}{inst}_B {lvlb} 0.001")
                else:
                    pinst = f"{'x' if topo=='strip' else 's'}k{k}c{j}"
                    nl.append(f"R{nm}{inst} {nm}{inst} q{pinst} 0.001")
                    if topo == "strip":
                        nl.append(f"R{nm}B{inst} {nm}{inst}_B n{pinst} 0.001")
            meta.append(dict(depth=k + 1, cell=i, inst=inst, node=q,
                             expect="HI" if g[k + 1][i] else "LO", devices=n,
                             topo=topo, rail=rail, kind="true"))
            if topo == "strip":
                meta.append(dict(depth=k + 1, cell=i, inst=inst, node=qb,
                                 expect="LO" if g[k + 1][i] else "HI", devices=n,
                                 topo=topo, rail=rail, kind="comp"))
    ic = [m["node"] for m in meta]
    nl.append(".ic " + " ".join("V(%s)=0" % x for x in ic))
    nl.append(".tran 2p 8n 0 4p")
    nl.append(".print tran format=noindex " + " ".join("V(%s)" % m["node"] for m in meta))
    nl.append(".end")
    return "\n".join(nl) + "\n", meta


if __name__ == "__main__":
    d = os.path.dirname(os.path.abspath(__file__))
    gl = golden()
    print("GOLDEN patterns (independent Boolean evolution):")
    print("  HEAD (input to depth 1): %s" % "".join(str(x) for x in gl[0]))
    for k in range(1, ND + 1):
        print("  depth %d output      : %s" % (k, "".join(str(x) for x in gl[k])))
    allm = []
    for topo, wxc, tag in (("strip", "1.12u", "strip112"),
                           ("strip", "0.56u", "strip56"),
                           ("static", None, "static")):
        txt, meta = build(topo, 0.6077, wxc or "1.12u")
        nm = "ch_%s.cir" % tag
        open(os.path.join(d, nm), "w").write(txt)
        for m in meta:
            m["deck"] = nm
            m["tag"] = tag
        allm += meta
        nd = sum(1 for l in txt.splitlines() if l.startswith("X") and "sg13_lv" in l)
        print("wrote %-16s devices=%3d checked_nodes=%d" % (nm, nd, len(meta)))
    json.dump(dict(golden=gl, nodes=allm),
              open(os.path.join(d, "CHAIN_META.json"), "w"), indent=1)
