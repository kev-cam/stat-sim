#!/usr/bin/env python3
"""The interaction the study treated as independent:
Rule 5 (use the SKEWED receiver, 0/300 vs 191/300) was measured at BASE geometry.
Phase 2 recommends upsizing the cells. But upsizing LOADS the resonant rail, so the
absolute output level FALLS -- and an absolute receiver trip does not scale with the
rail. Scored here: bank 4 HIGH-class level vs both fixed trips, for every geometry."""
import re,glob,math
import numpy as np
BT='/usr/local/src/stat-sim/qal/mcsize/'
PAT4=[1,1,1,0,1,0,0,1]
TRIPS={'RX_SKEW':0.4595,'RX_STD':0.6452}
def read_ms(p):
    v={}
    for ln in open(p):
        m=re.match(r'\s*([A-Za-z_0-9]+)\s*=\s*([-\d.eE+]+)\s*$',ln)
        if m: v[m.group(1).upper()]=float(m.group(2))
    return v
def sf(b):
    h=[x for x in glob.glob(b+'.mt*') if x[len(b)+3:].isdigit()]
    return sorted(h,key=lambda y:int(y[len(b)+3:]))
def cp(k,n,alpha=0.05):
    def cdf(p,kk,nn):
        if p<=0: return 1.0
        if p>=1: return 0.0 if kk<nn else 1.0
        return sum(math.comb(nn,i)*p**i*(1-p)**(nn-i) for i in range(kk+1))
    def bis(f,a,b):
        fa=f(a)
        for _ in range(300):
            m=.5*(a+b); fm=f(m)
            if (fm>0)==(fa>0): a,fa=m,fm
            else: b=m
        return .5*(a+b)
    lo=0.0 if k==0 else bis(lambda p: cdf(p,k-1,n)-(1-alpha/2),0.,1.)
    hi=1.0 if k==n else bis(lambda p: cdf(p,k,n)-alpha/2,0.,1.)
    return lo,hi
print(f"{'variant':9s} {'rail4':>7s} {'HIGHmin':>8s} {'sd_mV':>7s} | "
      + " | ".join(f"{t}: marg_mV  sig  fail/N  yieldCI" for t in TRIPS))
for tag,dk in [('base','p2_base'),('W x2','p2_wx2'),('W x4','p2_wx4'),('L x2','p2_lx2')]:
    S=[read_ms(p) for p in sf(BT+dk+'.cir')]; N=len(S)
    tg='M_L34G8_'
    rail=np.array([s.get(tg+'RAIL4',np.nan) for s in S])
    hi=[i for i in range(8) if PAT4[i]==1]
    lv=np.min([np.array([s.get(tg+f'O4_{i}',np.nan) for s in S]) for i in hi],axis=0)
    parts=[]
    for t,th in TRIPS.items():
        m=(lv-th)*1000
        f=int((m<0).sum()); lo,h=cp(N-f,N)
        parts.append(f"{np.nanmean(m):+8.2f} {np.nanmean(m)/np.nanstd(m,ddof=1):5.1f} {f:3d}/{N} "
                     f"[{lo*100:5.1f},{h*100:5.1f}]%")
    print(f"{tag:9s} {np.nanmean(rail):7.4f} {np.nanmean(lv):8.4f} {np.nanstd(lv,ddof=1)*1000:7.3f} | "
          + " | ".join(parts))
print("\nSame, at the 8x-sigma stress point (does the interaction worsen under mismatch?)")
for tag,dk in [('8x base','p2_k8'),('8x W x2','p2k8_wx2'),('8x W x4','p2k8_wx4'),('8x L x2','p2k8_lx2')]:
    S=[read_ms(p) for p in sf(BT+dk+'.cir')]; N=len(S)
    tg='M_L34G8_'
    rail=np.array([s.get(tg+'RAIL4',np.nan) for s in S])
    hi=[i for i in range(8) if PAT4[i]==1]
    lv=np.min([np.array([s.get(tg+f'O4_{i}',np.nan) for s in S]) for i in hi],axis=0)
    parts=[]
    for t,th in TRIPS.items():
        m=(lv-th)*1000; f=int((m<0).sum()); lo,h=cp(N-f,N)
        parts.append(f"{np.nanmean(m):+8.2f} {np.nanmean(m)/np.nanstd(m,ddof=1):5.1f} {f:3d}/{N} "
                     f"[{lo*100:5.1f},{h*100:5.1f}]%")
    print(f"{tag:9s} {np.nanmean(rail):7.4f} {np.nanmean(lv):8.4f} {np.nanstd(lv,ddof=1)*1000:7.3f} | "
          + " | ".join(parts))
