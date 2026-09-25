.subckt th22nk A B Y VDD VSS
MPA  N1 A VDD VDD sg13g2_pmos W=0.7u  L=0.13u
MPB  X  B N1  VDD sg13g2_pmos W=0.7u  L=0.13u
MNA  N2 A VSS VSS sg13g2_nmos W=0.35u L=0.13u
MNB  X  B N2  VSS sg13g2_nmos W=0.35u L=0.13u
MPY  Y  X VDD VDD sg13g2_pmos W=0.7u  L=0.13u
MNY  Y  X VSS VSS sg13g2_nmos W=0.35u L=0.13u
.ends th22nk
