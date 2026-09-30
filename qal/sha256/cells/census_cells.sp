* census cells: device lines VERBATIM from /usr/local/src/IHP-Open-PDK/ihp-sg13g2/libs.ref/sg13g2_stdcell/spice/sg13g2_stdcell.spice
* plus one explicit CINT=0.1f per internal node (see census.py docstring)
.subckt sg13g2_inv_1 Y A VDD VSS
XN0 Y A VSS VSS sg13_lv_nmos w=740.00n l=130.00n
XP0 Y A VDD VDD sg13_lv_pmos w=1.12u l=130.00n
.ends
.subckt sg13g2_nand2_1 Y A B VDD VSS
XP1 Y B VDD VDD sg13_lv_pmos w=1.12u l=130.00n
XP0 Y A VDD VDD sg13_lv_pmos w=1.12u l=130.00n
XN1 net1 B VSS VSS sg13_lv_nmos w=740.00n l=130.00n
XN0 Y A net1 VSS sg13_lv_nmos w=740.00n l=130.00n
CINT0 net1 VSS 0.1f
.ends
.subckt sg13g2_nor2_1 Y A B VDD VSS
XN0 Y A VSS VSS sg13_lv_nmos w=740.00n l=130.00n
XN1 Y B VSS VSS sg13_lv_nmos w=740.00n l=130.00n
XP0 net1 A VDD VDD sg13_lv_pmos w=1.12u l=130.00n
XP1 Y B net1 VDD sg13_lv_pmos w=1.12u l=130.00n
CINT0 net1 VDD 0.1f
.ends
.subckt sg13g2_and2_1 X A B VDD VSS
XN0 net4 A net2 VSS sg13_lv_nmos w=640.00n l=130.00n
XN2 X net4 VSS VSS sg13_lv_nmos w=740.00n l=130.00n
XN1 net2 B VSS VSS sg13_lv_nmos w=640.00n l=130.00n
XP0 net4 B VDD VDD sg13_lv_pmos w=840.00n l=130.00n
XP2 X net4 VDD VDD sg13_lv_pmos w=1.12u l=130.00n
XP1 net4 A VDD VDD sg13_lv_pmos w=840.00n l=130.00n
CINT0 net2 VSS 0.1f
CINT1 net4 VSS 0.1f
.ends
.subckt sg13g2_or2_1 X A B VDD VSS
XP1 net2 B net3 VDD sg13_lv_pmos w=840.00n l=130.00n
XP0 net3 A VDD VDD sg13_lv_pmos w=840.00n l=130.00n
XP2 X net2 VDD VDD sg13_lv_pmos w=1.12u l=130.00n
XN1 net2 A VSS VSS sg13_lv_nmos w=550.00n l=130.00n
XN0 net2 B VSS VSS sg13_lv_nmos w=550.00n l=130.00n
XN2 X net2 VSS VSS sg13_lv_nmos w=740.00n l=130.00n
CINT0 net2 VSS 0.1f
CINT1 net3 VDD 0.1f
.ends
.subckt sg13g2_nor2b_1 Y A B_N VDD VSS
XN0 B B_N VSS VSS sg13_lv_nmos w=550.00n l=130.00n
XN1 Y A VSS VSS sg13_lv_nmos w=740.00n l=130.00n
XN2 Y B VSS VSS sg13_lv_nmos w=740.00n l=130.00n
XP0 B B_N VDD VDD sg13_lv_pmos w=840.00n l=130.00n
XP1 net1 B VDD VDD sg13_lv_pmos w=1.12u l=130.00n
XP2 Y A net1 VDD sg13_lv_pmos w=1.12u l=130.00n
CINT0 B VSS 0.1f
CINT1 net1 VDD 0.1f
.ends
.subckt sg13g2_xnor2_1 Y A B VDD VSS
XP4 Y net1 VDD VDD sg13_lv_pmos w=1.12u l=130.00n
XP3 Y B net4 VDD sg13_lv_pmos w=1.12u l=130.00n
XP2 net4 A VDD VDD sg13_lv_pmos w=1.12u l=130.00n
XP1 net1 B VDD VDD sg13_lv_pmos w=840.00n l=130.00n
XP0 net1 A VDD VDD sg13_lv_pmos w=840.00n l=130.00n
XN3 Y net1 net3 VSS sg13_lv_nmos w=740.00n l=130.00n
XN1 net2 A VSS VSS sg13_lv_nmos w=640.00n l=130.00n
XN0 net1 B net2 VSS sg13_lv_nmos w=640.00n l=130.00n
XN4 net3 B VSS VSS sg13_lv_nmos w=740.00n l=130.00n
XN2 net3 A VSS VSS sg13_lv_nmos w=740.00n l=130.00n
CINT0 net1 VSS 0.1f
CINT1 net2 VSS 0.1f
CINT2 net3 VSS 0.1f
CINT3 net4 VDD 0.1f
.ends
.subckt sg13g2_xor2_1 X A B VDD VSS
XN0 net1 A VSS VSS sg13_lv_nmos w=550.00n l=130.00n
XN3 X B net3 VSS sg13_lv_nmos w=740.00n l=130.00n
XN2 X net1 VSS VSS sg13_lv_nmos w=740.00n l=130.00n
XN4 net3 A VSS VSS sg13_lv_nmos w=740.00n l=130.00n
XN1 net1 B VSS VSS sg13_lv_nmos w=550.00n l=130.00n
XP0 net6 A VDD VDD sg13_lv_pmos w=1.000u l=130.00n
XP1 net1 B net6 VDD sg13_lv_pmos w=1.000u l=130.00n
XP2 net5 A VDD VDD sg13_lv_pmos w=1.12u l=130.00n
XP4 net5 B VDD VDD sg13_lv_pmos w=1.12u l=130.00n
XP3 X net1 net5 VDD sg13_lv_pmos w=1.12u l=130.00n
CINT0 net1 VSS 0.1f
CINT1 net3 VSS 0.1f
CINT2 net5 VDD 0.1f
CINT3 net6 VDD 0.1f
.ends
.subckt sg13g2_mux2_1 X A0 A1 S VDD VSS
XP1 net4 S VDD VDD sg13_lv_pmos w=1.000u l=130.00n
XP5 X net6 VDD VDD sg13_lv_pmos w=1.12u l=130.00n
XP4 net6 A1 net5 VDD sg13_lv_pmos w=1.000u l=130.00n
XP0 Sb S VDD VDD sg13_lv_pmos w=840.00n l=130.00n
XP3 net5 Sb VDD VDD sg13_lv_pmos w=1.000u l=130.00n
XP2 net6 A0 net4 VDD sg13_lv_pmos w=1.000u l=130.00n
XN4 net3 S VSS VSS sg13_lv_nmos w=740.00n l=130.00n
XN2 net1 Sb VSS VSS sg13_lv_nmos w=740.00n l=130.00n
XN5 X net6 VSS VSS sg13_lv_nmos w=740.00n l=130.00n
XN0 Sb S VSS VSS sg13_lv_nmos w=550.00n l=130.00n
XN3 net6 A1 net3 VSS sg13_lv_nmos w=740.00n l=130.00n
XN1 net6 A0 net1 VSS sg13_lv_nmos w=740.00n l=130.00n
CINT0 Sb VSS 0.1f
CINT1 net1 VSS 0.1f
CINT2 net3 VSS 0.1f
CINT3 net4 VDD 0.1f
CINT4 net5 VDD 0.1f
CINT5 net6 VSS 0.1f
.ends
.subckt sg13g2_a21oi_1 Y A1 A2 B1 VDD VSS
XN0 Y B1 VSS VSS sg13_lv_nmos w=740.00n l=130.00n
XN2 net1 A2 VSS VSS sg13_lv_nmos w=740.00n l=130.00n
XN1 Y A1 net1 VSS sg13_lv_nmos w=740.00n l=130.00n
XP2 Y B1 net2 VDD sg13_lv_pmos w=1.12u l=130.00n
XP1 net2 A2 VDD VDD sg13_lv_pmos w=1.12u l=130.00n
XP0 net2 A1 VDD VDD sg13_lv_pmos w=1.12u l=130.00n
CINT0 net1 VSS 0.1f
CINT1 net2 VDD 0.1f
.ends
.subckt sg13g2_a21o_1 X A1 A2 B1 VDD VSS
XN0 net1 A1 net2 VSS sg13_lv_nmos w=640.00n l=130.00n
XN1 net2 A2 VSS VSS sg13_lv_nmos w=640.00n l=130.00n
XN2 net1 B1 VSS VSS sg13_lv_nmos w=640.00n l=130.00n
XN3 X net1 VSS VSS sg13_lv_nmos w=740.00n l=130.00n
XP2 net1 B1 net3 VDD sg13_lv_pmos w=1.000u l=130.00n
XP0 net3 A1 VDD VDD sg13_lv_pmos w=1.000u l=130.00n
XP1 net3 A2 VDD VDD sg13_lv_pmos w=1.000u l=130.00n
XP3 X net1 VDD VDD sg13_lv_pmos w=1.12u l=130.00n
CINT0 net1 VSS 0.1f
CINT1 net2 VSS 0.1f
CINT2 net3 VDD 0.1f
.ends
.subckt sg13g2_o21ai_1 Y A1 A2 B1 VDD VSS
XP0 net14 A1 VDD VDD sg13_lv_pmos w=1.12u l=150.00n
XP1 Y A2 net14 VDD sg13_lv_pmos w=1.12u l=150.00n
XP2 Y B1 VDD VDD sg13_lv_pmos w=1.12u l=150.00n
XN0 net1 A2 VSS VSS sg13_lv_nmos w=740.00n l=150.00n
XN2 net1 A1 VSS VSS sg13_lv_nmos w=740.00n l=150.00n
XN1 Y B1 net1 VSS sg13_lv_nmos w=740.00n l=150.00n
CINT0 net1 VSS 0.1f
CINT1 net14 VDD 0.1f
.ends
.subckt sg13g2_buf_1 X A VDD VSS
XN0 net1 A VSS VSS sg13_lv_nmos w=550.00n l=130.00n
XN1 X net1 VSS VSS sg13_lv_nmos w=740.00n l=130.00n
XP1 X net1 VDD VDD sg13_lv_pmos w=1.12u l=130.00n
XP0 net1 A VDD VDD sg13_lv_pmos w=840.00n l=130.00n
CINT0 net1 VSS 0.1f
.ends
