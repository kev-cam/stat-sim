* qal/mcsize/shim_mc.sp -- qal/sg13lv_compat.sp with a DELVTO PASS-THROUGH added.
* IDENTICAL to the committed shim in every other respect (ad/as/pd/ps still ZEROED,
* so junction capacitance is still absent and every number is still a LOWER bound).
* The ONLY change is the new `dvt` parameter, defaulting to 0 so that a deck that
* does not set it is bit-identical to the committed shim.
.subckt sg13_lv_nmos d g s b l=0.13u w=0.15u ng=1 ad=0 as=0 pd=0 ps=0 m=1 trise=0 dvt=0
M1 d g s b sg13g2_nmos W={w} L={l} DELVTO={dvt}
.ends
.subckt sg13_lv_pmos d g s b l=0.13u w=0.15u ng=1 ad=0 as=0 pd=0 ps=0 m=1 trise=0 dvt=0
M1 d g s b sg13g2_pmos W={w} L={l} DELVTO={dvt}
.ends
