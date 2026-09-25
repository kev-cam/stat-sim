* SG13G2 NAND2 (1x-ish) for CMOS liberty cross-check
.subckt nand2 A B Y VDD VSS
MP1 Y A VDD VDD sg13g2_pmos W=0.7u L=0.13u
MP2 Y B VDD VDD sg13g2_pmos W=0.7u L=0.13u
MN1 Y A N  VSS sg13g2_nmos W=0.35u L=0.13u
MN2 N B VSS VSS sg13g2_nmos W=0.35u L=0.13u
.ends nand2
