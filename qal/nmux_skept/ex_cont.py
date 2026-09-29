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
def iat(rows,vin):
    best=None
    for r in rows:
        d=abs(r["V(IN)"]-vin)
        if best is None or d<best[0]: best=(d,abs(r["I(VDD)"]),r["V(OUT)"])
    return best[1],best[2]
def trip(rows):
    prev=None
    for r in rows:
        f=r["V(OUT)"]-r["V(IN)"]
        if prev and ((prev[1]>=0)!=(f>=0)):
            x0,f0=prev; return x0+(r["V(IN)"]-x0)*(-f0)/(f-f0)
        prev=(r["V(IN)"],f)
    return None
HOLD=293e-12
names=json.load(open(f"{D}/contnames.json"))
PASS_LVL=0.8832; COMMIT_QAL_HI=0.6759; HOP=8.408e-15
out={}
print("(d) RECEIVER CONTENTION over the campaign's %g ps hold, vs the 8.408 fJ hop  [MEASURED]"%(HOLD*1e12))
print("%-6s %-6s %-8s | %-10s %-9s %-8s | %-10s %-9s %-8s"%(
  "cell","VDD","trip V","I@0.8832","E fJ","%hop","I@0.6759","E fJ","%hop"))
for n in names:
    cn=n.split("_")[2]; vdd=int(n.split("_")[-1])/1000.0
    rows=readprn(f"{D}/{n}.cir.prn")
    tp=trip(rows)
    i1,o1=iat(rows,PASS_LVL); i2,o2=iat(rows,COMMIT_QAL_HI)
    e1=i1*vdd*HOLD; e2=i2*vdd*HOLD
    ok1 = PASS_LVL<=vdd; ok2 = COMMIT_QAL_HI<=vdd
    out[n]={"cell":cn,"vdd":vdd,"trip":tp,"I_pass_uA":i1*1e6,"E_pass_fJ":e1*1e15,
            "pct_pass":e1/HOP*100,"I_qalhi_uA":i2*1e6,"E_qalhi_fJ":e2*1e15,"pct_qalhi":e2/HOP*100,
            "vout_at_pass":o1,"vout_at_qalhi":o2}
    print("%-6s %-6.2f %-8.4f | %-10.3f %-9.3f %-8.2f | %-10.3f %-9.3f %-8.2f"%(
      cn,vdd,tp,i1*1e6,e1*1e15,e1/HOP*100,i2*1e6,e2*1e15,e2/HOP*100))
json.dump(out,open(f"{D}/sk_cont.json","w"),indent=1)
print()
print("INSTRUMENT CHECK vs committed boundary study (std cell, VDD 1.2, Vin 0.6759):")
e=out["sk_rx_std_1200"]
print("  measured %.3f uA / %.4f fJ / %.2f%%   committed 8.780 uA / 3.0896 fJ / 36.75%%"%(
  e["I_qalhi_uA"],e["E_qalhi_fJ"],e["pct_qalhi"]))
print("  delta: %+.3f%% on current"%((e["I_qalhi_uA"]/8.780-1)*100))
print()
print("LOGIC-LEVEL HAZARD: does the receiver still READ the input as a 1? (Vout should be LOW)")
for n in names:
    e=out[n]
    print("  %-5s VDD %.2f : trip %.4f | QAL hi 0.6759 -> Vout %.4f %s | nMOS-pass 0.8832 -> Vout %.4f %s"%(
      e["cell"],e["vdd"],e["trip"],e["vout_at_qalhi"],
      "OK" if e["vout_at_qalhi"]<e["vdd"]*0.3 else "** MISREAD **",
      e["vout_at_pass"],"OK" if e["vout_at_pass"]<e["vdd"]*0.3 else "** MISREAD **"))
