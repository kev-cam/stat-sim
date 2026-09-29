#!/usr/bin/env python3
"""
SKEPTIC probe-deck builder.

Takes a chain deck and inserts EXACT 0 V ammeters on every terminal of the
bank-3 top-up cell, plus 1F integrators, so that the charge ledger can be
checked as a set of IDENTITIES with NO term computed as a residual.

Ammeters inserted (all 0 V sources == ideal wires, topologically exact):
  VMHSS3  tsup -> shs3    charge from the supply into the HS source+bulk
  VMHS3   nhs3 -> na3     charge out of the HS drain into the switch node
  VMFWS3  sfw3 -> 0       charge dumped from the FW source to ground
  VMFW3   nfw3 -> na3     charge out of the FW drain into the switch node
  VMCNA3  ncx3 -> 0       charge out of na3 through the explicit switch-node cap

Already present in the base deck and reused:
  I(LTU3)   charge out of na3 into the inductor
  I(VMTU3)  charge through the OUT switch into rail3
  I(VGTU3), I(VGFW3)   gate-drive currents
  I(VTSUP)  total supply current

Identities checked (every term independently metered):
  (i)   na3 KCL       Qhsd + Qfwd - QL - Qcna            == 0
  (ii)  HS device     Qhsd - Qsup3 + Qgtu                == 0
  (iii) FW device     Qfwd + Qfws + Qgfw                 == 0
"""
import re, sys, os

def build(src, dst, phase_times):
    txt = open(src).read()
    lines = txt.split("\n")
    out = []
    for ln in lines:
        s = ln.strip()
        # --- HS device: break out source/bulk and drain ---
        if s.startswith("XTUSW3 "):
            p = s.split()
            # XTUSW3 na3 gtu3 tsup tsup sg13_lv_pmos w=.. l=..
            assert p[1] == "na3" and p[3] == "tsup" and p[4] == "tsup", s
            rest = " ".join(p[5:])
            out.append("XTUSW3 nhs3 gtu3 shs3 shs3 " + rest)
            out.append("VMHSS3 tsup shs3 0")
            out.append("VMHS3 nhs3 na3 0")
            continue
        # --- FW device: break out source/bulk and drain ---
        if s.startswith("XTUFW3 "):
            p = s.split()
            # XTUFW3 na3 gfw3 0 0 sg13_lv_nmos w=.. l=..
            assert p[1] == "na3" and p[3] == "0" and p[4] == "0", s
            rest = " ".join(p[5:])
            out.append("XTUFW3 nfw3 gfw3 sfw3 sfw3 " + rest)
            out.append("VMFWS3 sfw3 0 0")
            out.append("VMFW3 nfw3 na3 0")
            continue
        # --- switch-node cap: put an ammeter in series ---
        if s.startswith("CNA3 "):
            p = s.split()
            assert p[1] == "na3" and p[2] == "0", s
            out.append("CNA3 na3 ncx3 " + p[3])
            out.append("VMCNA3 ncx3 0 0")
            continue
        out.append(ln)
    txt = "\n".join(out)

    # --- integrators, appended before .end ---
    integ = []
    def add(name, expr):
        integ.append("CXq%s xq%s 0 1" % (name, name))
        integ.append("BXq%s 0 xq%s I={ %s }" % (name, name, expr))
        integ.append("RXq%s xq%s 0 0.01" % (name, name))

    add("sup3",  "I(VMHSS3)")          # supply -> HS source+bulk
    add("hsd",   "I(VMHS3)")           # HS drain -> na3
    add("fws",   "I(VMFWS3)")          # FW source -> ground
    add("fwd",   "I(VMFW3)")           # FW drain -> na3
    add("cna",   "I(VMCNA3)")          # na3 -> cap -> ground
    add("ind",   "I(LTU3)")            # na3 -> inductor
    add("gtu",   "I(VGTU3)")           # HS gate drive
    add("gfw",   "I(VGFW3)")           # FW gate drive
    add("supt",  "-I(VTSUP)")          # total supply (name avoids the base deck's xqsup)
    # energies
    add("esup",  "-1.2*I(VTSUP)")                  # energy out of the 1.2 V supply
    add("ebnk",  "V(rail3)*I(VMTU3)")              # energy into bank 3
    add("ehsd",  "V(na3)*I(VMHS3)")
    add("egdrv", "-V(gtu3)*I(VGTU3)-V(gfw3)*I(VGFW3)-V(gto3)*I(VGTO3)-V(gtop3)*I(VGTOP3)")
    add("er",    "I(LTU3)*I(LTU3)*10")             # I^2 R in RTU3

    # --- measures at the phase boundaries ---
    meas = []
    names = ["sup3","hsd","fws","fwd","cna","ind","gtu","gfw","supt",
             "esup","ebnk","ehsd","egdrv","er"]
    for i, t in enumerate(phase_times):
        for n in names:
            meas.append(".measure tran S%s_P%d FIND V(xq%s) AT=%.6fp" % (n.upper(), i, n, t))
    # instantaneous currents across the windows, for the two-device overlap test
    meas.append(".measure tran SIHSMAX MAX I(VMHS3) FROM=300p TO=400p")
    meas.append(".measure tran SIFWMAX MAX I(VMFWS3) FROM=300p TO=400p")

    body = "\n".join(integ) + "\n" + "\n".join(meas) + "\n"
    txt = txt.replace("\n.end", "\n" + body + ".end")

    # print the probe currents so I can integrate them myself from the raw trace
    txt = txt.replace(
        ".print tran V(rail1)",
        ".print tran I(VMHS3) I(VMFW3) I(VMHSS3) I(VMFWS3) I(VMCNA3) I(VGTU3) I(VGFW3) I(VTSUP) I(VMTU3) V(gtu3) V(gfw3) V(gto3) V(rail1)")

    # new nodes need initial conditions consistent with na3
    txt = txt.replace("V(na3)=0", "V(na3)=0 V(nhs3)=0 V(nfw3)=0 V(ncx3)=0 V(shs3)=1.2 V(sfw3)=0")

    open(dst, "w").write(txt)
    return dst

if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    times = [float(x) for x in sys.argv[3].split(",")]
    print(build(src, dst, times))
