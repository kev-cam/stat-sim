import os, subprocess, json, math
D="/usr/local/src/stat-sim/qal/nmux_skept"
HDR='''.hdl "/usr/local/share/xyce/verilog-a/psp103/psp103.va"
.include "/usr/local/src/kestrel/sim/models/sg13g2_psp103_tt.lib"
.include "/usr/local/src/stat-sim/qal/sg13lv_compat.sp"
.OPTIONS TIMEINT METHOD=GEAR RELTOL=1e-6 ABSTOL=1e-15 CHGTOL=1e-17
'''
SB=[0.00,0.05,0.10,0.20,0.30,0.40,0.50,0.60,0.70,0.75,0.80,0.90,1.00,1.10,1.20,1.26,1.30]
names=[]
for sb in SB:
    n="sk_vt_%04d"%round(sb*1000)
    # source AND drain lifted to V_sb; bulk at 0 -> V_sb body bias. VG is g-to-s so it IS Vgs.
    body=HDR+f'''* V_sb = {sb} V ; bulk at 0 ; VG connected g->s so sweep var == Vgs
VS s 0 {sb:.6f}
VD d s 0.1
VG g s 0
XN d g s 0 sg13_lv_nmos w=0.74u l=0.13u
.dc VG 0.2 1.5 0.001
.print dc V(g) V(s) V(d) I(VD)
.end
'''
    open(f"{D}/{n}.cir","w").write(body)
    names.append(n)
json.dump(names,open(f"{D}/vtnames.json","w"))
print(len(names),"decks")
