* qal/vtreq/shim_dvt.sp
* IDENTICAL to the committed qal/sg13lv_compat.sp except that each device passes
* DELVTO from a GLOBAL .param the deck sets (DVTN for nMOS, DVTP for pMOS).
* DELVTO is a PSP103 INSTANCE parameter (PSP103_module.include:142).
* At DVTN=DVTP=0 this must reproduce the committed numbers -- that is gate G0.
* ad/as/pd/ps are still ZEROED, exactly as the committed shim does: every device
* number taken through this file is a LOWER BOUND.
.subckt sg13_lv_nmos d g s b l=0.13u w=0.15u ng=1 ad=0 as=0 pd=0 ps=0 m=1 trise=0
M1 d g s b sg13g2_nmos W={w} L={l} DELVTO={DVTN}
.ends
.subckt sg13_lv_pmos d g s b l=0.13u w=0.15u ng=1 ad=0 as=0 pd=0 ps=0 m=1 trise=0
M1 d g s b sg13g2_pmos W={w} L={l} DELVTO={DVTP}
.ends
