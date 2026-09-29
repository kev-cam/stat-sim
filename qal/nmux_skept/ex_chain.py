import json,re,math
D="/usr/local/src/stat-sim/qal/nmux_skept"
VAR=["sk_ch_wire_std_w060","sk_ch_nmos_std_w060","sk_ch_tg_std_w060",
     "sk_ch_wire_skew_w060","sk_ch_nmos_skew_w060"]
FLOOR=6.44  # mV, the campaign's sigma floor
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
def gt_times(deck):
    t={}
    for line in open(deck):
        m=re.match(r'^VGT(\d) .*PWL\(([^)]*)\)',line,re.I)
        if m:
            j=int(m.group(1)); nums=[float(x.rstrip('pnum')) *(1e-12 if x.endswith('p') else 1)
                                     for x in m.group(2).split()]
            # PWL pairs: t v t v ...; close = 3rd time, open = 4th time
            ts=nums[0::2]
            t[j]=(ts[2],ts[3])   # (t_close_done, t_open_start)
    return t
# POLARITY derived from the deck's own bank-1 DC inputs, independently:
def polarity(deck):
    ins={}
    for line in open(deck):
        m=re.match(r'^VI1_(\d)\s+\S+\s+\S+\s+([\d.]+)',line,re.I)
        if m: ins[int(m.group(1))]=float(m.group(2))
    # o1_i = NOT(in1_i); o{j+1}_i = NOT(o{j}_i)  -> is_hi(j,i) = (in1_i low) XOR (j even)
    return {i:(lambda j,v=v: ((v<0.6) == (j%2==1))) for i,v in ins.items()}
print("(c) CHAIN SEPARATION BY DEPTH, re-run in my own PyMS cache, my own extractor")
print("    polarity DERIVED from each deck's own VI1_* inputs; sign convention independent")
print("    sample = instant the bank's transfer switch OPENS (end of its conduction window)")
print()
allres={}
for v in VAR:
    rows=readprn(f"{D}/{v}.cir.prn"); tt=gt_times(f"{D}/{v}.cir"); pol=polarity(f"{D}/{v}.cir")
    seps=[];rails=[];gins=[];maxs=[]
    for j in range(1,7):
        tc,to=tt[j]
        best=None
        for r in rows:
            d=abs(r["TIME"]-to)
            if best is None or d<best[0]: best=(d,r)
        r=best[1]
        o0=r["V(O%d_0)"%j]; o1=r["V(O%d_1)"%j]
        hi0=pol[0](j)
        sep=(o0-o1) if hi0 else (o1-o0)
        seps.append(sep*1e3); rails.append(r["V(RAIL%d)"%j])
        gins.append((r.get("V(G%d_0)"%j),r.get("V(G%d_1)"%j)))
        # max |sep| over the conduction window (robustness to sampling convention)
        m=0.0
        for rr in rows:
            if tc<=rr["TIME"]<=to:
                a=rr["V(O%d_0)"%j]; b=rr["V(O%d_1)"%j]
                s=(a-b) if hi0 else (b-a)
                if s>m: m=s
        maxs.append(m*1e3)
    allres[v]={"sep_at_open_mV":seps,"sep_max_in_window_mV":maxs,"rail_V":rails,"gin":gins}
    lbl=v.replace("sk_ch_","").replace("_w060","")
    print("%-12s sep@open  : "%lbl+" ".join("%8.1f"%s for s in seps))
    print("%-12s sep max   : "%""   +" ".join("%8.1f"%s for s in maxs))
    print("%-12s rail V    : "%""   +" ".join("%8.4f"%s for s in rails))
    depth=0
    for s in seps:
        if s>FLOOR: depth+=1
        else: break
    print("%-12s -> usable depth (sep>%.2f mV, correct sign) = %d ; margins x floor: %s"%(
        "",FLOOR,depth," ".join("%.0f"%(s/FLOOR) if s>0 else "NEG" for s in seps)))
    print()
json.dump(allres,open(f"{D}/sk_chain.json","w"),indent=1)
