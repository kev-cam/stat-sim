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
TC=52e-12; HOLD=293e-12
print("AT THE CAMPAIGN'S 293 ps HOLD WINDOW (the real operating timescale)  [MEASURED]")
print("%-8s | %-9s %-9s | %-9s %-9s | %-9s %-9s | %-8s"%(
   "rail","nMOS@293p","short mV","TG@293p","short mV","oper@293p","short mV","injres mV"))
res={}
for n in names:
    rows=readprn(f"{D}/{n}.cir.prn"); r=rows[-1]["V(R)"]
    a=at(rows,TC+HOLD,"V(OA)"); d=at(rows,TC+HOLD,"V(OD)"); e=at(rows,TC+HOLD,"V(OE)")
    injres=(rows[-1]["V(OC)"]-r)*1e3
    res[n]={"rail":r,"nmos293":a,"tg293":d,"oper293":e,"injres_mV":injres}
    print("%-8.4f | %-9.4f %-9.1f | %-9.4f %-9.1f | %-9.4f %-9.1f | %-8.3f"%(
      r,a,(r-a)*1e3,d,(r-d)*1e3,e,(r-e)*1e3,injres))
json.dump(res,open(f"{D}/sk_pass293.json","w"),indent=1)
print()
# crossover: largest rail whose 293ps shortfall stays under thresholds
for tol in (10.0,25.0,50.0):
    prev=None; cross=None
    for n in names:
        v=res[n]; s=(v["rail"]-v["nmos293"])*1e3
        if s>tol and cross is None and prev is not None:
            r0,s0=prev; cross=r0+(v["rail"]-r0)*(tol-s0)/(s-s0)
        prev=(v["rail"],s)
    print("CROSSOVER (293 ps window), shortfall = %5.1f mV  ->  rail = %.4f V"%(tol,cross if cross else float('nan')))
