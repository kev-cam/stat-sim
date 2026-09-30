#!/usr/bin/env python3
"""Re-rank DUT_B on the BINDING half only. rx6.py's response is the mean over 8 lanes
of the sign-corrected margin -- but 4 lanes FAIL (~-115 mV) and 4 pass hugely (~+397 mV),
so the mean is +140 mV while every sample fails. That is the same near-cancellation the
study caught for the receiver OUTPUT (A10 #3) and did not catch here."""
import re,glob,json,math,sys
import numpy as np
BT='/usr/local/src/stat-sim/qal/mcsize/'
ABST=0.4595
WANT6=[1,0,1,0,1,0,1,0]
def read_ms(p):
    v={}
    for ln in open(p):
        m=re.match(r'\s*([A-Za-z_0-9]+)\s*=\s*([-\d.eE+]+)\s*$',ln)
        if m: v[m.group(1).upper()]=float(m.group(2))
    return v
def sfiles(b):
    h=[x for x in glob.glob(b+'.mt*') if x[len(b)+3:].isdigit()]
    return sorted(h,key=lambda y:int(y[len(b)+3:]))
def read_res(p):
    L=open(p).read().splitlines(); hdr=L[0].split()
    nm=[h.split(':')[0].upper() for h in hdr[1:]]
    rows=[[float(x) for x in ln.split()[1:]] for ln in L[1:]
          if len(ln.split())==len(hdr) and ln.split()[0].isdigit()]
    return nm,np.array(rows)*1000.0
S=[];names=None;draws=[]
for d in ['rv_mc_3001.cir','rv_mc_3002.cir','rv_mc_3003.cir']:
    for p in sfiles(BT+d): S.append(read_ms(p))
    nm,dd=read_res(BT+d+'.res')
    if names is None: names=nm
    draws.append(dd)
D=np.vstack(draws); N=len(S)
print(f"N={N} devices={len(names)}")
tg='M_L56BOUND_'
lanes={}
for i in range(8):
    v=np.array([s.get(tg+f'O6_{i}',np.nan) for s in S])
    lanes[i]=(v, (v-ABST)*1000*(1 if WANT6[i]==1 else -1))
print(f"\n{'lane':5s} {'want':>5s} {'level_V':>9s} {'sd_mV':>8s} {'margin_mV':>10s} {'fails':>6s}")
for i in range(8):
    v,m=lanes[i]
    print(f"o6_{i:<2d} {WANT6[i]:5d} {np.nanmean(v):9.5f} {np.nanstd(v,ddof=1)*1000:8.3f} {np.nanmean(m):10.3f} {int((m<0).sum()):6d}")
mean8=np.mean([lanes[i][1] for i in range(8)],axis=0)
high=np.min([lanes[i][1] for i in range(8) if WANT6[i]==1],axis=0)
low =np.min([lanes[i][1] for i in range(8) if WANT6[i]==0],axis=0)
worst=np.min([lanes[i][1] for i in range(8)],axis=0)
print(f"\nrx6.py response  (mean over 8 lanes): {mean8.mean():+9.3f} mV  sd {mean8.std(ddof=1):.3f}  -> POSITIVE while 30/30 fail")
print(f"HIGH-lane worst  (the binding half) : {high.mean():+9.3f} mV  sd {high.std(ddof=1):.3f}  fails {int((high<0).sum())}/{N}")
print(f"LOW-lane  worst                     : {low.mean():+9.3f} mV  sd {low.std(ddof=1):.3f}  fails {int((low<0).sum())}/{N}")
print(f"TRUE worst over 8 lanes             : {worst.mean():+9.3f} mV  sd {worst.std(ddof=1):.3f}  fails {int((worst<0).sum())}/{N}")
def cls(nm):
    if re.match(r'XRP\d+_\d+A$',nm): return 'rxSkewP_0u15'
    if re.match(r'XRN\d+_\d+A$',nm): return 'rxSkewN_1u48'
    if re.match(r'XRP\d+_\d+B$',nm): return 'restP_1u12'
    if re.match(r'XRN\d+_\d+B$',nm): return 'restN_0u74'
    if nm.startswith('XSWSN'): return 'srcSwN_10u'
    if nm.startswith('XSWSP'): return 'srcSwP_20u'
    if nm.startswith('XSWN'): return 'swN_10u'
    if nm.startswith('XSWP'): return 'swP_20u'
    if nm.startswith('XPK'): return 'park_2u'
    if re.match(r'XP\d',nm): return 'cellP_1u12'
    if re.match(r'XN\d',nm): return 'cellN_0u74'
    return 'other'
def rank(y,label):
    m=np.isfinite(y); yy=y[m]; X=D[m]
    byc={}; ind=[]
    for j,nm in enumerate(names):
        x=X[:,j]
        if x.std(ddof=1)<1e-12: continue
        b=np.polyfit(x,yy,1)[0]; s=x.std(ddof=1); v=(b*s)**2
        ind.append((nm,b,s,v))
        c=byc.setdefault(cls(nm),{'n':0,'var':0.0}); c['n']+=1; c['var']+=v
    A=np.column_stack([X,np.ones(len(yy))])
    co,_,_,_=np.linalg.lstsq(A,yy,rcond=None); r2=1-((yy-A@co)**2).sum()/((yy-yy.mean())**2).sum()
    tot=sum(c['var'] for c in byc.values())
    print(f"\n--- ranking on: {label}   (multivar R2 = {r2:.4f}) ---")
    for k,c in sorted(byc.items(),key=lambda z:-z[1]['var']):
        print(f"   {k:14s} n={c['n']:3d} share={c['var']/tot:.4f} rms={math.sqrt(c['var']):8.3f}")
    ind.sort(key=lambda z:-z[3])
    print("   top5:", ", ".join(f"{n}({math.sqrt(v):.2f})" for n,b,s,v in ind[:5]))
rank(mean8,"rx6.py's mean-over-8-lanes (CONTAMINATED)")
rank(high,"HIGH-lane worst margin (the FAILING/binding half)")
rank(low,"LOW-lane worst margin (the passing half)")
rank(worst,"true worst over all 8 lanes")
