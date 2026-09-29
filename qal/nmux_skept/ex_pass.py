import json
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
def at(rows,t,col):
    best=None
    for r in rows:
        d=abs(r["TIME"]-t)
        if best is None or d<best[0]: best=(d,r[col])
    return best[1]
names=json.load(open(f"{D}/passnames.json"))
TC=52e-12
out={}
print("(b) CLEAN PASS TEST  w=0.60u  CL=2fF  VGH=1.5 V   [all MEASURED]")
print("%-7s | %-8s %-8s %-8s %-8s | %-8s | %-7s | %-8s | %-8s"%(
  "rail","+100ps","+300ps","+1ns","+20ns","DCgate20n","inject","TG@20ns","operand"))
for n in names:
    rail=int(n.split("_")[-1])/1000.0
    rows=readprn(f"{D}/{n}.cir.prn")
    railm=rows[-1]["V(R)"]
    a100=at(rows,TC+100e-12,"V(OA)"); a300=at(rows,TC+300e-12,"V(OA)")
    a1=at(rows,TC+1e-9,"V(OA)");      aend=rows[-1]["V(OA)"]
    bend=rows[-1]["V(OB)"]
    inj=at(rows,TC+20e-12,"V(OC)")-railm      # pure injection kick, zero driving force
    injend=rows[-1]["V(OC)"]-railm
    dend=rows[-1]["V(OD)"]; eend=rows[-1]["V(OE)"]
    out[n]={"rail":railm,"a100":a100,"a300":a300,"a1n":a1,"a20n":aend,"b20n":bend,
            "inject_peak_mV":inj*1e3,"inject_resid_mV":injend*1e3,"tg20n":dend,"operand20n":eend}
    print("%-7.4f | %-8.4f %-8.4f %-8.4f %-8.4f | %-9.4f | %+6.1f | %-8.4f | %-8.4f"%(
        railm,a100,a300,a1,aend,bend,inj*1e3,dend,eend))
json.dump(out,open(f"{D}/sk_pass.json","w"),indent=1)
print()
print("SHORTFALL vs rail (mV), stepped-gate nMOS-only at +20ns, and TG:")
print("%-8s %-12s %-12s %-12s"%("rail","nMOS short","TG short","operand short"))
for n in names:
    e=out[n]; r=e["rail"]
    print("%-8.4f %-12.1f %-12.1f %-12.1f"%(r,(r-e["a20n"])*1e3,(r-e["tg20n"])*1e3,(r-e["operand20n"])*1e3))
