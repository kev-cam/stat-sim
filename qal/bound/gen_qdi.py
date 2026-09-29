#!/usr/bin/env python3
"""Track 3 deck generator: sync <-> QDI (dual-rail) boundary adapters, H3.

ENCODER (sync -> QDI), per bit:  T = D.EN ,  F = /D.EN
   = INV(D) + NAND2(D,EN) + INV + NAND2(/D,EN) + INV   (3 INV + 2 NAND2)
DECODER (QDI -> sync), per bit:  data = T (a wire);  completion C = T + F
   = NOR2(T,F) + INV                                    (1 NOR2 + 1 INV)
COMPLETION TREE node:            AND2 of two per-bit completions
   = NAND2 + INV

Two bits are instantiated (D=1 and D=0) so the reported per-bit number is the
mean over a 50/50 data mix -- the same convention the QAL bank decks use
(alternating cell inputs).  Each block type has its own VDD source; energies are
1F-integrator supply integrals, t0-referenced at extraction.
"""
import sys

VDD = 1.2
T_EN_R, T_EN_F, T_END = 100.0, 600.0, 1000.0
EDGE = 20.0

HDR = """sync<->QDI boundary adapters (Track 3 H3)
.hdl "/usr/local/share/xyce/verilog-a/psp103/psp103.va"
.include "/usr/local/src/kestrel/sim/models/sg13g2_psp103_tt.lib"
.include "/usr/local/src/stat-sim/qal/sg13lv_compat.sp"
.OPTIONS TIMEINT METHOD=GEAR RELTOL=1e-6 ABSTOL=1e-15 CHGTOL=1e-17
"""

WP, WN = 1.12, 0.74          # campaign generic inverter


def inv(nm, a, y, d):
    return (f"XP{nm} {y} {a} {d} {d} sg13_lv_pmos w={WP}u l=0.13u\n"
            f"XN{nm} {y} {a} 0 0 sg13_lv_nmos w={WN}u l=0.13u\n")


def nand2(nm, a, b, y, d):
    m = f"m{nm}"
    return (f"XP{nm}A {y} {a} {d} {d} sg13_lv_pmos w={WP}u l=0.13u\n"
            f"XP{nm}B {y} {b} {d} {d} sg13_lv_pmos w={WP}u l=0.13u\n"
            f"XN{nm}A {y} {a} {m} 0 sg13_lv_nmos w={2*WN}u l=0.13u\n"
            f"XN{nm}B {m} {b} 0 0 sg13_lv_nmos w={2*WN}u l=0.13u\n")


def nor2(nm, a, b, y, d):
    m = f"m{nm}"
    return (f"XP{nm}A {m} {a} {d} {d} sg13_lv_pmos w={2*WP}u l=0.13u\n"
            f"XP{nm}B {y} {b} {m} {d} sg13_lv_pmos w={2*WP}u l=0.13u\n"
            f"XN{nm}A {y} {a} 0 0 sg13_lv_nmos w={WN}u l=0.13u\n"
            f"XN{nm}B {y} {b} 0 0 sg13_lv_nmos w={WN}u l=0.13u\n")


def integ(tag, expr):
    return (f"C{tag} {tag} 0 1\nB{tag} 0 {tag} I={{ {expr} }}\nR{tag} {tag} 0 0.01\n")


def main(path):
    n = HDR
    # ---- stimulus -------------------------------------------------------
    n += (f"VEN en 0 PWL(0 0 {T_EN_R}p 0 {T_EN_R+EDGE}p {VDD} "
          f"{T_EN_F}p {VDD} {T_EN_F+EDGE}p 0 {T_END}p 0)\n")
    n += f"VD0 d0 0 {VDD}\n"          # bit 0 carries a 1
    n += "VD1 d1 0 0\n"               # bit 1 carries a 0
    # ---- encoders (own rail) --------------------------------------------
    n += f"VDE de 0 {VDD}\n"
    for b in (0, 1):
        n += inv(f"EI{b}", f"d{b}", f"db{b}", "de")
        n += nand2(f"EA{b}", f"d{b}", "en", f"nt{b}", "de")
        n += inv(f"ET{b}", f"nt{b}", f"t{b}", "de")
        n += nand2(f"EB{b}", f"db{b}", "en", f"nf{b}", "de")
        n += inv(f"EF{b}", f"nf{b}", f"f{b}", "de")
        # dual-rail routing capacitance stand-in: 2 fF per RAIL (2 rails/bit)
        n += f"CWT{b} t{b} 0 2f\nCWF{b} f{b} 0 2f\n"
    # ---- decoders (own rail): data is a wire, completion is the circuit --
    n += f"VDD2 dd 0 {VDD}\n"
    for b in (0, 1):
        n += nor2(f"DN{b}", f"t{b}", f"f{b}", f"nc{b}", "dd")
        n += inv(f"DC{b}", f"nc{b}", f"c{b}", "dd")
        n += f"CLC{b} c{b} 0 2f\n"
    # ---- one completion-tree node (AND2 of the two per-bit completions) --
    n += f"VDT dt 0 {VDD}\n"
    n += nand2("TN", "c0", "c1", "ntree", "dt")
    n += inv("TI", "ntree", "ctree", "dt")
    n += "CLT ctree 0 2f\n"
    # ---- metering --------------------------------------------------------
    n += integ("eenc", f"-{VDD}*I(VDE)")
    n += integ("edec", f"-{VDD}*I(VDD2)")
    n += integ("etre", f"-{VDD}*I(VDT)")
    n += integ("een2", f"-V(en)*I(VEN)")          # what the sync side pays to drive EN
    n += f".tran 0.1p {T_END}p 0 0.5p\n"
    for tag in ("eenc", "edec", "etre", "een2"):
        for lbl, t in (("Z", 5.0), ("A", T_EN_R - 5), ("B", T_EN_F - 5),
                       ("C", T_END - 5)):
            n += f".measure tran {tag.upper()}_{lbl} FIND V({tag}) AT={t}p\n"
    n += f".measure tran TEN WHEN V(en)={VDD/2} RISE=1\n"
    n += f".measure tran TT0 WHEN V(t0)={VDD/2} RISE=1\n"
    n += f".measure tran TF1 WHEN V(f1)={VDD/2} RISE=1\n"
    n += f".measure tran TC0 WHEN V(c0)={VDD/2} RISE=1\n"
    n += f".measure tran TC1 WHEN V(c1)={VDD/2} RISE=1\n"
    n += f".measure tran TCT WHEN V(ctree)={VDD/2} RISE=1\n"
    n += f".measure tran T0END FIND V(t0) AT={T_EN_F-5}p\n"
    n += f".measure tran F0END FIND V(f0) AT={T_EN_F-5}p\n"
    n += f".measure tran T1END FIND V(t1) AT={T_EN_F-5}p\n"
    n += f".measure tran F1END FIND V(f1) AT={T_EN_F-5}p\n"
    n += f".measure tran CTEND FIND V(ctree) AT={T_EN_F-5}p\n"
    n += f".measure tran T0NUL FIND V(t0) AT={T_END-5}p\n"
    n += f".measure tran CTNUL FIND V(ctree) AT={T_END-5}p\n"
    n += (".print tran V(en) V(t0) V(f0) V(t1) V(f1) V(c0) V(c1) V(ctree)\n"
          "+ V(eenc) V(edec) V(etre) V(een2)\n")
    n += ".end\n"
    open(path, "w").write(n)
    print(f"wrote {path}: {len(n.splitlines())} lines")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "bd_qdi.cir")
