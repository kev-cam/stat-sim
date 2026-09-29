import json,re
D="/usr/local/src/stat-sim/qal/nmux_skept"
def readprn(p):
    hdr=None; rows=[]
    for line in open(p):
        s=line.split()
        if not s: continue
        if s[0]=="Index": hdr=[c.upper() for c in s]; continue
        if s[0].startswith("End") or hdr is None: continue
        try: v=[float(x) for x in s]
        except ValueError: continue
        if len(v)==len(hdr): rows.append(dict(zip(hdr,v)))
    return rows
V0=0.8832
print("HIGH-SIDE PASSED LEVEL by depth: the mux output that is supposed to be a logic 1")
print("  (bank j's HIGH g node = the bit whose own output o is LOW).")
print("  'source' = the driving cell output in bank j-1 that feeds it.  V* (100nA,293ps) = %.4f V"%V0)
print()
for v in ("sk_ch_nmos_std_w060","sk_ch_tg_std_w060","sk_ch_wire_std_w060"):
    rows=readprn(f"{D}/{v}.cir.prn")
    lbl=v.replace("sk_ch_","").replace("_w060","")
    print("%-10s  depth : "%lbl+"".join("%10d"%j for j in range(2,7)))
    ghi=[];src=[];rail_prev=[]
    for j in range(2,7):
        t=(200+300*(j-1)+300)*1e-12
        best=None
        for r in rows:
            d=abs(r["TIME"]-t)
            if best is None or d<best[0]: best=(d,r)
        r=best[1]
        hi0=(j%2==0)          # o{j}_0 high when j even (derived earlier from VI1_*)
        gname="V(G%d_%d)"%(j,1 if hi0 else 0)   # high g is the one whose o is LOW
        oname="V(O%d_%d)"%(j-1,1 if hi0 else 0) # its source: previous bank's output, same bit
        ghi.append(r.get(gname)); src.append(r.get(oname)); rail_prev.append(r["V(RAIL%d)"%(j-1)])
    print("%-10s  g(hi) : "%""+"".join(("%10.4f"%g) if g is not None else "     n/a  " for g in ghi))
    print("%-10s  source: "%""+"".join(("%10.4f"%s) if s is not None else "     n/a  " for s in src))
    print("%-10s  loss  : "%""+"".join(("%+10.1f"%((s-g)*1e3)) if (g is not None and s is not None) else "     n/a  "
                                        for g,s in zip(ghi,src))+"   mV")
    print("%-10s  src>V*: "%""+"".join(("%10s"%("YES" if (s is not None and s>V0) else "no")) for s in src))
    print()
