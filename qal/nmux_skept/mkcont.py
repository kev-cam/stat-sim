import json
D="/usr/local/src/stat-sim/qal/nmux_skept"
HDR='''.hdl "/usr/local/share/xyce/verilog-a/psp103/psp103.va"
.include "/usr/local/src/kestrel/sim/models/sg13g2_psp103_tt.lib"
.include "/usr/local/src/stat-sim/qal/sg13lv_compat.sp"
.OPTIONS TIMEINT METHOD=GEAR RELTOL=1e-6 ABSTOL=1e-15 CHGTOL=1e-17
'''
CELLS={"std":(1.12,0.74),"skew":(0.15,1.48)}
VDDS=[0.90,1.20,1.26,1.33]
names=[]
for cn,(wp,wn) in CELLS.items():
    for vdd in VDDS:
        n="sk_rx_%s_%04d"%(cn,round(vdd*1000))
        b=HDR+f'''* (d) receiver contention: {cn} cell pmos {wp}u / nmos {wn}u, VDD={vdd}
VDD vdd 0 {vdd:.4f}
VIN in 0 0
XP out in vdd vdd sg13_lv_pmos w={wp}u l=0.13u
XN out in 0 0 sg13_lv_nmos w={wn}u l=0.13u
.dc VIN 0 {vdd:.4f} 0.0005
.print dc V(in) V(out) I(VDD)
.end
'''
        open(f"{D}/{n}.cir","w").write(b); names.append(n)
json.dump(names,open(f"{D}/contnames.json","w"))
print(len(names),"contention decks")
