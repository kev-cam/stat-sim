import json
D="/usr/local/src/stat-sim/qal/nmux_skept"
HDR='''.hdl "/usr/local/share/xyce/verilog-a/psp103/psp103.va"
.include "/usr/local/src/kestrel/sim/models/sg13g2_psp103_tt.lib"
.include "/usr/local/src/stat-sim/qal/sg13lv_compat.sp"
.OPTIONS TIMEINT METHOD=GEAR RELTOL=1e-6 ABSTOL=1e-15 CHGTOL=1e-17
'''
RAILS=[0.60,0.70,0.755,0.80,0.85,0.8832,0.90,0.95,1.00,1.10,1.20,1.26,1.30]
names=[]
for r in RAILS:
    n="sk_ps_%04d"%round(r*1000)
    b=HDR+f'''* (b) CLEAN PASS TEST, ideal rail {r:.4f} V, VGH=1.5, w=0.60u, CL=2fF
* A: gate STEPPED at 50p (gate-charge injection INCLUDED)
* B: gate held at 1.5 from t=0 (conduction only, no step in window)
* C: output PRE-CHARGED to the rail, gate stepped -> PURE INJECTION (zero driving force)
* D: full transmission gate, equal nMOS width, stepped
* E: OPERAND-gated (gate driven only to the RAIL, the XOR2 case) -> source follower
VR r 0 {r:.6f}
VNW nw 0 1.5
VGA ga 0 PWL(0 0 50p 0 52p 1.5)
XNA r ga oa 0 sg13_lv_nmos w=0.60u l=0.13u
CLA oa 0 2f
VGB gb 0 1.5
XNB r gb ob 0 sg13_lv_nmos w=0.60u l=0.13u
CLB ob 0 2f
VGC gc 0 PWL(0 0 50p 0 52p 1.5)
XNC r gc oc 0 sg13_lv_nmos w=0.60u l=0.13u
CLC oc 0 2f
VGD gd 0 PWL(0 0 50p 0 52p 1.5)
VGDB gdb 0 PWL(0 1.5 50p 1.5 52p 0)
XND r gd od 0 sg13_lv_nmos w=0.60u l=0.13u
XPD r gdb od nw sg13_lv_pmos w=0.60u l=0.13u
CLD od 0 2f
VGE ge 0 PWL(0 0 50p 0 52p {r:.6f})
XNE r ge oe 0 sg13_lv_nmos w=0.60u l=0.13u
CLE oe 0 2f
.ic V(oa)=0 V(ob)=0 V(oc)={r:.6f} V(od)=0 V(oe)=0
.tran 0.2p 20n UIC
.print tran V(oa) V(ob) V(oc) V(od) V(oe) V(r)
.end
'''
    open(f"{D}/{n}.cir","w").write(b); names.append(n)
json.dump(names,open(f"{D}/passnames.json","w"))
print(len(names),"pass decks:", " ".join(names))
