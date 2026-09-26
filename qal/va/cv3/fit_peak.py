#!/usr/bin/env python3
"""PEAKED charge fit: floor + plateau-step + inversion-PEAK bump.

The measured C_inc(V) is floor(~23 fF) -> PEAK(~78 fF @0.45) -> plateau(~36 fF).
A monotone softplus (fit_q.py) captures floor->plateau but MISSES the peak
(-24% Q at V=0.5). This adds a bump = difference of two softplus turn-ons (a
smooth top-hat in C_inc between VA and VB), still a pure charge state.

    Q(V) = C0*V + CT*W*sp((V-VK)/W) + CP*WP*(sp((V-VA)/WP) - sp((V-VB)/WP))

Fit to the MEASURED CHARGE Q(V), dV=1.0 curve only; the total charge Q(dV) is
matched by construction via the plateau CT (as in fit_q.py). C0 fixed at the
measured C_quiet floor. The peak (CP, VA, VB) + plateau (CT, VK) fit the shape.
W = NSS*PHIT (conduction fit); WP a free peak width.
"""
import numpy as np, math, json
KEEP = "/usr/local/src/stat-sim/qal/va/probe_runs"
W = 1.85*0.02585

def curves(kind, dv):
    fn = "%s/cv_%s_dv%03d.cir.prn" % (KEEP, kind, int(round(dv*100)))
    rows=[]
    for ln in open(fn):
        p=ln.split()
        if len(p)>=5 and p[0][0].isdigit():
            try: rows.append([float(x) for x in p[1:5]])
            except ValueError: pass
    a=np.array(rows); t,v,pw,q=a[:,0],a[:,1],a[:,2],a[:,3]
    E=np.concatenate([[0],np.cumsum(0.5*(pw[1:]+pw[:-1])*np.diff(t))])
    Q=np.concatenate([[0],np.cumsum(0.5*(q[1:]+q[:-1])*np.diff(t))])
    return v,E,Q

def spn(z):
    return np.where(z>0,z,0.0)+np.log1p(np.exp(-np.abs(z)))

def qmodel(V,C0,CT,VK,CP,VA,VB,WP):
    return (C0*V + CT*W*spn((V-VK)/W)
            + CP*WP*(spn((V-VA)/WP)-spn((V-VB)/WP)))

def emodel(V,C0,CT,VK,CP,VA,VB,WP):
    V=np.atleast_1d(V).astype(float); out=np.empty_like(V)
    for i,vv in enumerate(V):
        g=np.linspace(0,vv,4001)
        def sg(z): return np.where(z>=0,1/(1+np.exp(-z)),np.exp(z)/(1+np.exp(z)))
        cinc=C0+CT*sg((g-VK)/W)+CP*(sg((g-VA)/WP)-sg((g-VB)/WP))
        out[i]=np.trapezoid(g*cinc,g)
    return out if out.size>1 else float(out[0])

def nelder(f,x0,step,it=1500):
    n=len(x0); S=[np.array(x0,float)]
    for i in range(n):
        x=np.array(x0,float); x[i]+=step[i]; S.append(x)
    fv=[f(x) for x in S]
    for _ in range(it):
        o=np.argsort(fv); S=[S[i] for i in o]; fv=[fv[i] for i in o]
        c=np.mean(S[:-1],axis=0); xr=c+(c-S[-1]); fr=f(xr)
        if fr<fv[0]:
            xe=c+2*(c-S[-1]); fe=f(xe); S[-1],fv[-1]=(xe,fe) if fe<fr else (xr,fr)
        elif fr<fv[-2]: S[-1],fv[-1]=xr,fr
        else:
            xc=c+0.5*(S[-1]-c); fc=f(xc)
            if fc<fv[-1]: S[-1],fv[-1]=xc,fc
            else:
                for i in range(1,n+1): S[i]=S[0]+0.5*(S[i]-S[0]); fv[i]=f(S[i])
        if max(abs(v-fv[0]) for v in fv)<1e-15: break
    o=np.argsort(fv); return S[o[0]],fv[o[0]]

def fit(kind,dv=1.0,C0fix=23.2):
    vt,Et,Qt=curves("tr",dv)
    grid=np.arange(0.10,dv+1e-9,0.02)
    Qtr=np.interp(grid,vt,Qt)
    if kind=="full":
        tgt=Qtr; qend=float(np.interp(dv,vt,Qt))
    else:
        vb,Eb,Qb=curves("bh",dv); tgt=Qtr-np.interp(grid,vb,Qb)
        qend=float(np.interp(dv,vt,Qt)-np.interp(dv,vb,Qb))
    # CT set so Q(dV) exact given the other params
    def ct_of(C0,VK,CP,VA,VB,WP):
        zb=(dv-VK)/W; spb=(zb if zb>0 else 0)+math.log1p(math.exp(-abs(zb)))
        za1=(dv-VA)/WP; sa=(za1 if za1>0 else 0)+math.log1p(math.exp(-abs(za1)))
        zb1=(dv-VB)/WP; sb=(zb1 if zb1>0 else 0)+math.log1p(math.exp(-abs(zb1)))
        qb=CP*WP*(sa-sb)
        return (qend - C0*dv - qb)/(W*spb)
    def sse(p):
        VK,CP,VA,VB,WP=p
        C0=C0fix*1e-15
        if CP<0 or WP<0.01 or WP>0.12 or not(0.15<VK<0.9) or not(0.2<VA<0.6) or not(VA<VB<0.75):
            return 1e30
        CT=ct_of(C0,VK,CP*1e-15,VA,VB,WP)
        if CT<0: return 1e30
        r=(qmodel(grid,C0,CT,VK,CP*1e-15,VA,VB,WP)-tgt)/np.maximum(Qtr,1e-16)
        return float(np.dot(r,r))
    best,bs=None,1e31
    for vk0 in (0.35,0.5):
        for cp0 in (20,40):
            x,s=nelder(sse,[vk0,cp0,0.40,0.52,0.03],[0.05,5,0.03,0.03,0.01])
            if s<bs: best,bs=x,s
    VK,CP,VA,VB,WP=best; C0=C0fix*1e-15
    CT=ct_of(C0,VK,CP*1e-15,VA,VB,WP)
    return dict(C0=C0,CT=CT,VK=VK,CP=CP*1e-15,VA=VA,VB=VB,WP=WP), math.sqrt(bs/len(grid))

def show(name,p,kind):
    print("%s: C0=%.3f CT=%.3f VK=%.4f | CP=%.3f VA=%.4f VB=%.4f WP=%.4f (fF,V)"%(
        name,p["C0"]*1e15,p["CT"]*1e15,p["VK"],p["CP"]*1e15,p["VA"],p["VB"],p["WP"]))
    args=(p["C0"],p["CT"],p["VK"],p["CP"],p["VA"],p["VB"],p["WP"])
    print("   Q(1.0)=%.3f fC  E(1.0)=%.3f fJ"%(qmodel(1.0,*args)*1e15, emodel(1.0,*args)*1e15))

def main():
    pA,rA=fit("full"); pB,rB=fit("deckB")
    print("PEAKED charge fit (dV=1.0 only), rms rel-Q A=%.2f%% B=%.2f%%"%(rA*100,rB*100))
    show("bank A (full) ",pA,"full"); show("deck B (floor)",pB,"deckB")
    # residual table composed deckB+cells
    for dv in (0.6,0.8,1.0,1.2):
        vt,Et,Qt=curves("tr",dv); vb,Eb,Qb=curves("bh",dv)
        if abs(dv-0.6)<1e-9: chk=[0.1,0.2,0.3,0.4,0.5,0.55,0.6]
        else: chk=[round(f*dv,4) for f in (0.167,0.333,0.5,0.667,0.833,0.917,1.0)]
        tag="FIT" if abs(dv-1.0)<1e-9 else "holdout"
        argsB=(pB["C0"],pB["CT"],pB["VK"],pB["CP"],pB["VA"],pB["VB"],pB["WP"])
        print("\n dV=%.1f (%s): V  Q_meas Q_mod errQ | E_meas E_mod errE (deckB+cells)"%(dv,tag))
        for v in chk:
            qm=np.interp(v,vt,Qt)*1e15
            qmod=(qmodel(v,*argsB)+np.interp(v,vb,Qb))*1e15
            em=np.interp(v,vt,Et)*1e15
            emod=(emodel(v,*argsB)+np.interp(v,vb,Eb))*1e15
            print("   %5.3f %7.3f %7.3f %+5.1f%% | %7.3f %7.3f %+6.1f%%"%(
                v,qm,qmod,(qmod/qm-1)*100 if qm else 0,em,emod,(emod/em-1)*100 if em else 0))
    def dump(p): return {k:(p[k]) for k in ("C0","CT","VK","CP","VA","VB","WP")}
    json.dump({"deckB":dump(pB),"bankA_full":dump(pA),"W":W},open("cv_fit_peak.json","w"),indent=1)
    print("\nwrote cv_fit_peak.json")

if __name__=="__main__": main()
