* map IHP std-cell devices to the PSP103 device our async cells use (same PDK)
.subckt sg13_lv_nmos d g s b l=0.13u w=0.15u ng=1 ad=0 as=0 pd=0 ps=0 m=1 trise=0
M1 d g s b sg13g2_nmos W={w} L={l}
.ends
.subckt sg13_lv_pmos d g s b l=0.13u w=0.15u ng=1 ad=0 as=0 pd=0 ps=0 m=1 trise=0
M1 d g s b sg13g2_pmos W={w} L={l}
.ends
