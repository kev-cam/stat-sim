import json, math
D="/usr/local/src/stat-sim/qal/nmux_skept"
rows=json.load(open(f"{D}/sk_vt_rows.json"))
pts=sorted([(v["V_sb_nominal"],v["Vt_100n"],v["Vt_10n"],v["Vt_1n"]) for v in rows.values()])
COMMITTED_VT0=0.5239460
print("G1 INSTRUMENT GATE: Vtn(0)=%.7f vs committed %.7f -> %+.4f mV"%(pts[0][1],COMMITTED_VT0,(pts[0][1]-COMMITTED_VT0)*1e3))
print("TOTAL SHIFT 0->1.3 V: %+.2f mV"%((pts[-1][1]-pts[0][1])*1e3))
print()
def fit(idx):
    xs=[p[0] for p in pts]; ys=[p[idx] for p in pts]; vt0=ys[0]
    best=None
    # scan 2phi_F, closed-form least-squares gamma at each
    p=0.05
    while p<3.0:
        b=[math.sqrt(p+x)-math.sqrt(p) for x in xs]
        num=sum(bi*(y-vt0) for bi,y in zip(b,ys)); den=sum(bi*bi for bi in b)
        g=num/den
        r=[(vt0+g*bi)-y for bi,y in zip(b,ys)]
        ss=sum(e*e for e in r)
        if best is None or ss<best[0]: best=(ss,g,p,max(abs(e) for e in r))
        p+=0.0005
    ss,g,p,mx=best
    return g,p,vt0,math.sqrt(ss/len(xs)),mx
res={}
for nm,idx in [("100n",1),("10n",2),("1n",3)]:
    g,p,vt0,rms,mx=fit(idx)
    res[nm]=(g,p,vt0)
    print("crit %-5s: gamma=%.5f V^0.5  2phi_F=%.4f V  Vt0=%.6f  RMS resid=%.4f mV  max=%.4f mV"%(nm,g,p,vt0,rms*1e3,mx*1e3))
print()
VGH=1.5
print("SELF-CONSISTENT PASS CEILING  V* = VGH - Vtn(V*),  VGH=%.2f V"%VGH)
print("%-6s %-10s %-14s %-14s %-14s"%("crit","V*(V)","marg@peer .755","marg@tank 1.26","marg@1.326"))
ceil={}
for nm in ("100n","10n","1n"):
    g,p,vt0=res[nm]
    f=lambda v: VGH-(vt0+g*(math.sqrt(p+v)-math.sqrt(p)))-v
    lo,hi=0.0,1.5
    for _ in range(200):
        m=(lo+hi)/2
        if f(m)>0: lo=m
        else: hi=m
    V=(lo+hi)/2; ceil[nm]=V
    print("%-6s %-10.4f %+13.1f %+13.1f %+13.1f"%(nm,V,(0.755-V)*-1e3,(1.26-V)*-1e3,(1.326-V)*-1e3))
json.dump({"fit":res,"ceiling":ceil},open(f"{D}/sk_body_fit.json","w"),indent=1)
