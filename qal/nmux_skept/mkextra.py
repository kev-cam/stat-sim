import json
D="/usr/local/src/stat-sim/qal/nmux_skept"
HDR='''.hdl "/usr/local/share/xyce/verilog-a/psp103/psp103.va"
.include "/usr/local/src/kestrel/sim/models/sg13g2_psp103_tt.lib"
.include "/usr/local/src/stat-sim/qal/sg13lv_compat.sp"
.OPTIONS TIMEINT METHOD=GEAR RELTOL=1e-6 ABSTOL=1e-15 CHGTOL=1e-17
'''
names=[]
for r in (0.755,0.8832,1.26):
    n="sk_x_%04d"%round(r*1000)
    b=HDR+f'''* EXTRA: cases the record did not build. rail {r:.4f}, VGH=1.5, w=0.60u
* F = 2-deep nMOS cascade (4:1 mux tree). internal node cap 0.5 fF ASSUMED (shim zeroes junctions)
* H = 2-deep full-TG cascade, same topology, equal nMOS width
* G = DYNAMIC select: out was passed LOW, select flips, must rise to rail (charge sharing)
* K = 3-deep nMOS cascade (8:1 tree)
VR r 0 {r:.6f}
VLO lo 0 0
VNW nw 0 1.5
VGF gf 0 PWL(0 0 50p 0 52p 1.5)
VGFB gfb 0 PWL(0 1.5 50p 1.5 52p 0)
XNF1 r gf mf 0 sg13_lv_nmos w=0.60u l=0.13u
CMF mf 0 0.5f
XNF2 mf gf of 0 sg13_lv_nmos w=0.60u l=0.13u
CLF of 0 2f
XNH1 r gf mh 0 sg13_lv_nmos w=0.60u l=0.13u
XPH1 r gfb mh nw sg13_lv_pmos w=0.60u l=0.13u
CMH mh 0 0.5f
XNH2 mh gf oh 0 sg13_lv_nmos w=0.60u l=0.13u
XPH2 mh gfb oh nw sg13_lv_pmos w=0.60u l=0.13u
CLH oh 0 2f
XNK1 r gf mk1 0 sg13_lv_nmos w=0.60u l=0.13u
CMK1 mk1 0 0.5f
XNK2 mk1 gf mk2 0 sg13_lv_nmos w=0.60u l=0.13u
CMK2 mk2 0 0.5f
XNK3 mk2 gf ok 0 sg13_lv_nmos w=0.60u l=0.13u
CLK ok 0 2f
XNG1 r gf og 0 sg13_lv_nmos w=0.60u l=0.13u
XNG2 lo gfb og 0 sg13_lv_nmos w=0.60u l=0.13u
CLG og 0 2f
.ic V(of)=0 V(oh)=0 V(ok)=0 V(og)=0 V(mf)=0 V(mh)=0 V(mk1)=0 V(mk2)=0
.tran 0.2p 20n UIC
.print tran V(of) V(oh) V(ok) V(og) V(mf) V(r)
.end
'''
    open(f"{D}/{n}.cir","w").write(b); names.append(n)
json.dump(names,open(f"{D}/xnames.json","w")); print(names)
