import json,re
D="/usr/local/src/stat-sim/qal/nmux_skept"
VAR=["sk_ch_wire_std_w060","sk_ch_nmos_std_w060","sk_ch_tg_std_w060",
     "sk_ch_wire_skew_w060","sk_ch_nmos_skew_w060"]
REC={ # the record's published rows, for a like-for-like check
 "sk_ch_wire_std_w060":[1502.7,1225.7,1049.4,883.9,730.9,639.6],
 "sk_ch_nmos_std_w060":[1278.2,980.8,786.2,610.1,394.9,399.2],
 "sk_ch_tg_std_w060":[1048.9,857.0,772.8,634.1,401.6,389.0],
 "sk_ch_wire_skew_w060":[1182.4,901.4,699.1,511.6,331.6,49.4],
 "sk_ch_nmos_skew_w060":[571.9,410.4,266.5,110.3,29.2,3.2]}
FLOOR=6.44
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
def polarity_hi0(deck,j):
    ins={}
    for line in open(deck):
        m=re.match(r'^VI1_(\d)\s+\S+\s+\S+\s+([\d.]+)',line,re.I)
        if m: ins[int(m.group(1))]=float(m.group(2))
    return (ins[0]<0.6)==(j%2==1)
out={}
print("(c) CHAIN SEPARATION, sample = bank close + 300 ps (one phase period)  [MEASURED, my re-run]")
print()
for v in VAR:
    rows=readprn(f"{D}/{v}.cir.prn")
    seps=[];rails=[];gin=[]
    for j in range(1,7):
        t=(200+300*(j-1)+300)*1e-12
        best=None
        for r in rows:
            d=abs(r["TIME"]-t)
            if best is None or d<best[0]: best=(d,r)
        r=best[1]; hi0=polarity_hi0(f"{D}/{v}.cir",j)
        o0=r["V(O%d_0)"%j]; o1=r["V(O%d_1)"%j]
        seps.append(((o0-o1) if hi0 else (o1-o0))*1e3)
        rails.append(r["V(RAIL%d)"%j])
        g=r.get("V(G%d_0)"%j); gin.append(g)
    depth=0
    for s in seps:
        if s>FLOOR: depth+=1
        else: break
    out[v]={"sep_mV":seps,"rail_V":rails,"g0_V":gin,"depth":depth}
    lbl=v.replace("sk_ch_","").replace("_w060","")
    print("%-11s mine   : %s   depth %d"%(lbl," ".join("%8.1f"%s for s in seps),depth))
    print("%-11s record : %s"%(""," ".join("%8.1f"%s for s in REC[v])))
    print("%-11s delta  : %s"%(""," ".join("%+8.1f"%(a-b) for a,b in zip(seps,REC[v]))))
    print("%-11s rail V : %s"%(""," ".join("%8.4f"%s for s in rails)))
    print("%-11s x floor: %s"%(""," ".join(("%.0f"%(s/FLOOR)) if s>0 else "NEG" for s in seps)))
    print()
json.dump(out,open(f"{D}/sk_chain2.json","w"),indent=1)
print("PASSED-NODE LEVEL (g{j}_0, the mux output feeding bank j) vs that bank's rail:")
for v in ("sk_ch_nmos_std_w060","sk_ch_tg_std_w060"):
    e=out[v]
    print("  %-10s g0: %s"%(v.replace("sk_ch_","").replace("_w060",""),
        " ".join(("%7.4f"%g) if g is not None else "  n/a  " for g in e["g0_V"])))
    print("  %-10s rail:%s"%(""," ".join("%7.4f"%r for r in e["rail_V"])))
