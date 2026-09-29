.subckt sg13g2_xnor2_1 Y A B VDD VSS
XP4 Y net1 VDD VDD sg13_lv_pmos w=1.12u l=130.00n ng=1 ad=3.808e-13 as=3.808e-13 pd=2.92e-06 ps=2.92e-06 m=1
XP3 Y B net4 VDD sg13_lv_pmos w=1.12u l=130.00n ng=1 ad=3.808e-13 as=3.808e-13 pd=2.92e-06 ps=2.92e-06 m=1
XP2 net4 A VDD VDD sg13_lv_pmos w=1.12u l=130.00n ng=1 ad=3.808e-13 as=3.808e-13 pd=2.92e-06 ps=2.92e-06 m=1
XP1 net1 B VDD VDD sg13_lv_pmos w=840.00n l=130.00n ng=1 ad=2.856e-13 as=2.856e-13 pd=2.36e-06 ps=2.36e-06 m=1
XP0 net1 A VDD VDD sg13_lv_pmos w=840.00n l=130.00n ng=1 ad=2.856e-13 as=2.856e-13 pd=2.36e-06 ps=2.36e-06 m=1
XN3 Y net1 net3 VSS sg13_lv_nmos w=740.00n l=130.00n ng=1 ad=2.516e-13 as=2.516e-13 pd=2.16e-06 ps=2.16e-06 m=1
XN1 net2 A VSS VSS sg13_lv_nmos w=640.00n l=130.00n ng=1 ad=2.176e-13 as=2.176e-13 pd=1.96e-06 ps=1.96e-06 m=1
XN0 net1 B net2 VSS sg13_lv_nmos w=640.00n l=130.00n ng=1 ad=2.176e-13 as=2.176e-13 pd=1.96e-06 ps=1.96e-06 m=1
XN4 net3 B VSS VSS sg13_lv_nmos w=740.00n l=130.00n ng=1 ad=2.516e-13 as=2.516e-13 pd=2.16e-06 ps=2.16e-06 m=1
XN2 net3 A VSS VSS sg13_lv_nmos w=740.00n l=130.00n ng=1 ad=2.516e-13 as=2.516e-13 pd=2.16e-06 ps=2.16e-06 m=1
CINT0 net1 VSS 0.1f
CINT1 net2 VSS 0.1f
CINT2 net3 VSS 0.1f
CINT3 net4 VDD 0.1f
.ends
.subckt sg13g2_mux2_1 X A0 A1 S VDD VSS
XP1 net4 S VDD VDD sg13_lv_pmos w=1.000u l=130.00n ng=1 ad=3.4e-13 as=3.4e-13 pd=2.68e-06 ps=2.68e-06 m=1
XP5 X net6 VDD VDD sg13_lv_pmos w=1.12u l=130.00n ng=1 ad=3.808e-13 as=3.808e-13 pd=2.92e-06 ps=2.92e-06 m=1
XP4 net6 A1 net5 VDD sg13_lv_pmos w=1.000u l=130.00n ng=1 ad=3.4e-13 as=3.4e-13 pd=2.68e-06 ps=2.68e-06 m=1
XP0 Sb S VDD VDD sg13_lv_pmos w=840.00n l=130.00n ng=1 ad=2.856e-13 as=2.856e-13 pd=2.36e-06 ps=2.36e-06 m=1
XP3 net5 Sb VDD VDD sg13_lv_pmos w=1.000u l=130.00n ng=1 ad=3.4e-13 as=3.4e-13 pd=2.68e-06 ps=2.68e-06 m=1
XP2 net6 A0 net4 VDD sg13_lv_pmos w=1.000u l=130.00n ng=1 ad=3.4e-13 as=3.4e-13 pd=2.68e-06 ps=2.68e-06 m=1
XN4 net3 S VSS VSS sg13_lv_nmos w=740.00n l=130.00n ng=1 ad=2.516e-13 as=2.516e-13 pd=2.16e-06 ps=2.16e-06 m=1
XN2 net1 Sb VSS VSS sg13_lv_nmos w=740.00n l=130.00n ng=1 ad=2.516e-13 as=2.516e-13 pd=2.16e-06 ps=2.16e-06 m=1
XN5 X net6 VSS VSS sg13_lv_nmos w=740.00n l=130.00n ng=1 ad=2.516e-13 as=2.516e-13 pd=2.16e-06 ps=2.16e-06 m=1
XN0 Sb S VSS VSS sg13_lv_nmos w=550.00n l=130.00n ng=1 ad=1.87e-13 as=1.87e-13 pd=1.78e-06 ps=1.78e-06 m=1
XN3 net6 A1 net3 VSS sg13_lv_nmos w=740.00n l=130.00n ng=1 ad=2.516e-13 as=2.516e-13 pd=2.16e-06 ps=2.16e-06 m=1
XN1 net6 A0 net1 VSS sg13_lv_nmos w=740.00n l=130.00n ng=1 ad=2.516e-13 as=2.516e-13 pd=2.16e-06 ps=2.16e-06 m=1
CINT0 Sb VSS 0.1f
CINT1 net1 VSS 0.1f
CINT2 net3 VSS 0.1f
CINT3 net4 VDD 0.1f
CINT4 net5 VDD 0.1f
CINT5 net6 VSS 0.1f
.ends
.subckt sg13g2_inv_1 Y A VDD VSS
XN0 Y A VSS VSS sg13_lv_nmos w=740.00n l=130.00n ng=1 ad=2.516e-13 as=2.516e-13 pd=2.16e-06 ps=2.16e-06 m=1
XP0 Y A VDD VDD sg13_lv_pmos w=1.12u l=130.00n ng=1 ad=3.808e-13 as=3.808e-13 pd=2.92e-06 ps=2.92e-06 m=1
.ends
.subckt sg13g2_nand2_1 Y A B VDD VSS
XP1 Y B VDD VDD sg13_lv_pmos w=1.12u l=130.00n ng=1 ad=3.808e-13 as=3.808e-13 pd=2.92e-06 ps=2.92e-06 m=1
XP0 Y A VDD VDD sg13_lv_pmos w=1.12u l=130.00n ng=1 ad=3.808e-13 as=3.808e-13 pd=2.92e-06 ps=2.92e-06 m=1
XN1 net1 B VSS VSS sg13_lv_nmos w=740.00n l=130.00n ng=1 ad=2.516e-13 as=2.516e-13 pd=2.16e-06 ps=2.16e-06 m=1
XN0 Y A net1 VSS sg13_lv_nmos w=740.00n l=130.00n ng=1 ad=2.516e-13 as=2.516e-13 pd=2.16e-06 ps=2.16e-06 m=1
CINT0 net1 VSS 0.1f
.ends
.subckt sg13g2_o21ai_1 Y A1 A2 B1 VDD VSS
XP0 net14 A1 VDD VDD sg13_lv_pmos w=1.12u l=150.00n ng=1 ad=3.808e-13 as=3.808e-13 pd=2.92e-06 ps=2.92e-06 m=1
XP1 Y A2 net14 VDD sg13_lv_pmos w=1.12u l=150.00n ng=1 ad=3.808e-13 as=3.808e-13 pd=2.92e-06 ps=2.92e-06 m=1
XP2 Y B1 VDD VDD sg13_lv_pmos w=1.12u l=150.00n ng=1 ad=3.808e-13 as=3.808e-13 pd=2.92e-06 ps=2.92e-06 m=1
XN0 net1 A2 VSS VSS sg13_lv_nmos w=740.00n l=150.00n ng=1 ad=2.516e-13 as=2.516e-13 pd=2.16e-06 ps=2.16e-06 m=1
XN2 net1 A1 VSS VSS sg13_lv_nmos w=740.00n l=150.00n ng=1 ad=2.516e-13 as=2.516e-13 pd=2.16e-06 ps=2.16e-06 m=1
XN1 Y B1 net1 VSS sg13_lv_nmos w=740.00n l=150.00n ng=1 ad=2.516e-13 as=2.516e-13 pd=2.16e-06 ps=2.16e-06 m=1
CINT0 net1 VSS 0.1f
CINT1 net14 VDD 0.1f
.ends
