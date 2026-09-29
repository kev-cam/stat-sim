#!/usr/bin/env python3
"""SKEPTIC settle deck: static o21ai_hb vs stripped o21ai-equivalent on an
IDEAL STIFF RAIL.

Why a stiff rail.  On a tank-fed rail the delivered rail voltage DEPENDS on the
bank's switched capacitance, and the stripped bank has twice as many output
nodes as the static bank.  So a tank-fed comparison confounds "does this
topology settle" with "how much rail did this topology get".  A stiff rail
removes that confound completely and is fully specified by two numbers (rail,
input level), so it is reproducible without knowing any committed harness.

Both input conventions are built, because they give OPPOSITE answers:
  RAILREF  inputs swing 0 -> rail        (the real chain condition: a gate is
                                          driven by a predecessor output, which
                                          cannot exceed the rail)
  DV       inputs swing 0 -> dV (=1.5 V) (the committed bank convention, which
                                          gives the gates MORE drive than the
                                          rail they are charging)

All 8 input vectors of the 3-input cell are instantiated, one cell per vector,
so every row checks the whole truth table: 8 checked nodes for static, 16 for
stripped (both rails of every cell).

Every output node starts at 0 V (.ic) -- the real QAL condition, where the rail
ramps up from zero and there is NO precharge device.
"""
import os, sys, itertools
import cellsk as K

RAILS = [0.5217, 0.5594, 0.6077, 0.7000, 0.8000, 1.0000]
DV = 1.5
CL = "2f"
TSTOP = "4n"

HDR = """.hdl "/usr/local/share/xyce/verilog-a/psp103/psp103.va"
.include "/usr/local/src/kestrel/sim/models/sg13g2_psp103_tt.lib"
.include "/usr/local/src/stat-sim/qal/sg13lv_compat.sp"
.OPTIONS TIMEINT METHOD=GEAR RELTOL=1e-6 ABSTOL=1e-15 CHGTOL=1e-17
"""

INS = ["A1", "A2", "B1"]


def fnum(x):
    return ("%0.4f" % x).replace(".", "p")


def build(rail):
    nl = []
    pr = []
    ic = []
    meta = []
    nl.append("* SKEPT settle deck, IDEAL STIFF RAIL = %.4f V" % rail)
    nl.append("* declared: VRAIL is an ideal source.  That is the POINT of this deck")
    nl.append("* (it removes the tank-sizing confound); no energy claim is made here.")
    nl.append(HDR.rstrip())
    nl.append("VRAIL rail 0 %.6f" % rail)
    nl.append("VDVS dvs 0 %.6f" % DV)

    # input level nets, one per (convention, level)
    # RAILREF high = rail ; DV high = DV
    nl.append("* input-level nets")
    nl.append("RHI_R hi_r rail 0.001")
    nl.append("RHI_D hi_d dvs 0.001")

    for conv, hinet in (("rr", "hi_r"), ("dv", "hi_d")):
        for vec in itertools.product([0, 1], repeat=3):
            vid = "".join(str(b) for b in vec)
            v = dict(zip(INS, vec))
            yexp = not ((v["A1"] or v["A2"]) and v["B1"])

            # ---------------- static control
            inst = f"s{conv}{vid}"
            q = f"q{inst}"
            sub, n = K.static_o21ai(inst, "rail", q)
            nl += sub
            nl.append(f"C{q} {q} 0 {CL}")
            for nm in INS:
                src = hinet if v[nm] else "0"
                nl.append(f"R{nm}{inst} {nm}{inst} {src} 0.001")
            ic.append(q)
            pr.append(f"V({q})")
            meta.append(dict(row=f"static_{conv}", vec=vid, node=q,
                             expect="HI" if yexp else "LO", devices=n,
                             topo="static", wxc=None, conv=conv, rail=rail))

            # ---------------- stripped, two cross-coupled widths
            for wxc, wtag in (("0.56u", "56"), ("1.12u", "112")):
                inst = f"x{wtag}{conv}{vid}"
                q = f"q{inst}"
                qb = f"n{inst}"
                sub, n = K.strip_cell("o21ai", inst, "rail", q, qb, wxc)
                nl += sub
                nl.append(f"C{q} {q} 0 {CL}")
                nl.append(f"C{qb} {qb} 0 {CL}")
                for nm in INS:
                    src = hinet if v[nm] else "0"
                    srcb = "0" if v[nm] else hinet
                    nl.append(f"R{nm}{inst} {nm}{inst} {src} 0.001")
                    nl.append(f"R{nm}B{inst} {nm}{inst}_B {srcb} 0.001")
                ic += [q, qb]
                pr += [f"V({q})", f"V({qb})"]
                meta.append(dict(row=f"strip{wtag}_{conv}", vec=vid, node=q,
                                 expect="HI" if yexp else "LO", devices=n,
                                 topo=f"strip{wtag}", wxc=wxc, conv=conv, rail=rail))
                meta.append(dict(row=f"strip{wtag}_{conv}", vec=vid, node=qb,
                                 expect="LO" if yexp else "HI", devices=n,
                                 topo=f"strip{wtag}", wxc=wxc, conv=conv, rail=rail))

    # every output node starts at 0 V: the rail ramps from zero in the real
    # circuit and there is NO precharge device in any stripped cell here.
    nl.append(".ic " + " ".join("V(%s)=0" % x for x in ic))
    nl.append(f".tran 1p {TSTOP} 0 2p")
    nl.append(".print tran format=noindex " + " ".join(pr))
    nl.append(".end")
    return "\n".join(nl) + "\n", meta


if __name__ == "__main__":
    import json
    d = os.path.dirname(os.path.abspath(__file__))
    allmeta = []
    for r in RAILS:
        txt, meta = build(r)
        nm = "st_%s.cir" % fnum(r)
        with open(os.path.join(d, nm), "w") as f:
            f.write(txt)
        for m in meta:
            m["deck"] = nm
        allmeta += meta
        ndev = sum(1 for ln in txt.splitlines() if ln.startswith("X") and "sg13_lv" in ln)
        print("wrote", nm, "M-cards:", ndev, "checked nodes:", len(meta))
    with open(os.path.join(d, "SETTLE_META.json"), "w") as f:
        json.dump(allmeta, f, indent=1)
