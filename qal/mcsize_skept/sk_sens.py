#!/usr/bin/env python3
"""SKEPTIC independent re-derivation of the per-device sensitivity ranking.
Key departure from score.py: score.py regresses the MIN over 24 gates on each draw.
min() is nonlinear, so that regression is ATTENUATED. Here every gate is regressed
SEPARATELY (linear, un-attenuated), and the class ranking is built by summing the
per-gate variance contributions. R^2 is reported for every response so attenuation
is visible rather than hidden."""
import re,os,glob,json,math,sys
import numpy as np
BT='/usr/local/src/stat-sim/qal/mcsize/'
PAT={1:[0,0,0,1,0,1,1,0],2:[1,1,1,0,1,0,0,1],3:[0,0,0,1,0,1,1,0],4:[1,1,1,0,1,0,0,1]}
LINKS=[(1,2),(2,3),(3,4)]
def read_ms(p):
    v={}
    for ln in open(p):
        m=re.match(r'\s*([A-Za-z_0-9]+)\s*=\s*([-\d.eE+]+)\s*$',ln)
        if m:
            try: v[m.group(1).upper()]=float(m.group(2))
            except ValueError: pass
    return v
def sfiles(base):
    for ext in ('.mt','.ms'):
        h=[x for x in glob.glob(base+ext+'*') if x[len(base)+len(ext):].isdigit()]
        if h: return [(int(x[len(base)+len(ext):]),x) for x in sorted(h,key=lambda y:int(y[len(base)+len(ext):]))]
    return []
def read_res(p):
    L=open(p).read().splitlines(); hdr=L[0].split()
    names=[h.split(':')[0].upper() for h in hdr[1:]]
    rows=[[float(x) for x in ln.split()[1:]] for ln in L[1:]
          if len(ln.split())==len(hdr) and ln.split()[0].isdigit()]
    return names,np.array(rows)
decks=sys.argv[1:] or [BT+'bt_mc_2001.cir',BT+'bt_mc_2002.cir',BT+'bt_mc_2003.cir']
S=[];names=None;draws=[]
for d in decks:
    for _i,p in sfiles(d): S.append(read_ms(p))
    nm,dd=read_res(d+'.res')
    if names is None: names=nm
    assert nm==names
    draws.append(dd)
D=np.vstack(draws)*1000.0   # mV
N=len(S); assert len(D)==N, f"{len(D)} draws vs {N} measures"
print(f"N={N} devices={len(names)}")
def cls(nm):
    if nm.startswith('XSWN'): return 'swN_10u'
    if nm.startswith('XSWP'): return 'swP_20u'
    if nm.startswith('XPK'):  return 'park_2u'
    if re.match(r'XP\d',nm):  return 'cellP_1u12'
    if re.match(r'XN\d',nm):  return 'cellN_0u74'
    return 'other'
CL=[cls(n) for n in names]
def decomp(y,label,verbose=False):
    """variance decomposition of response y over independent draws, + R^2 of the
    full linear model (multivariate OLS) so attenuation is explicit."""
    y=np.asarray(y,float); m=np.isfinite(y)
    yy=y[m]; X=D[m]
    if yy.std(ddof=1)<1e-12: return None
    contrib={}; 
    for j,nm in enumerate(names):
        x=X[:,j]
        if x.std(ddof=1)<1e-12: continue
        b=np.polyfit(x,yy,1)[0]
        contrib[nm]=(b,x.std(ddof=1),(b*x.std(ddof=1))**2)
    # multivariate R^2
    A=np.column_stack([X,np.ones(len(yy))])
    coef,res,rank,sv=np.linalg.lstsq(A,yy,rcond=None)
    pred=A@coef
    r2=1-((yy-pred)**2).sum()/((yy-yy.mean())**2).sum()
    tot=sum(c[2] for c in contrib.values())
    byc={}
    for nm,(b,s,v) in contrib.items():
        c=byc.setdefault(cls(nm),{'n':0,'var':0.0}); c['n']+=1; c['var']+=v
    obs=yy.var(ddof=1)
    out=dict(label=label,n=len(yy),mean=float(yy.mean()),sd=float(yy.std(ddof=1)),
             sum_contrib_var=tot,observed_var=obs,frac_explained_univ=tot/obs,r2_multivar=r2,
             by_class={k:dict(n=v['n'],share=v['var']/tot,rms=math.sqrt(v['var'])) for k,v in byc.items()},
             top=sorted(((nm,b,s,v) for nm,(b,s,v) in contrib.items()),key=lambda z:-z[3])[:8])
    return out
# ---- per-gate margins, and the min ----
rows=[]
gm={}
for (k,r) in LINKS:
    tg=f'M_L{k}{r}BOUND_'
    rail=np.array([s.get(tg+f'RAIL{r}',np.nan) for s in S])
    for i in range(8):
        vr=np.array([s.get(tg+f'O{r}_{i}',np.nan) for s in S])
        sgn=1 if PAT[r][i]==1 else -1
        marg=(vr-rail/2.0)*1000.0*sgn
        gm[f'{k}->{r}:o{r}_{i}']=marg
worst=np.min(np.vstack(list(gm.values())),axis=0)
print("\n=== A. response = MIN over 24 gates (score.py's response) ===")
o=decomp(worst,'min-margin')
print(f"mean={o['mean']:.3f} sd={o['sd']:.3f}  univariate sum(b*sig)^2/var = {o['frac_explained_univ']:.4f}  multivar R2 = {o['r2_multivar']:.4f}")
for kk,v in sorted(o['by_class'].items(),key=lambda z:-z[1]['share']):
    print(f"   {kk:14s} n={v['n']:3d} share={v['share']:.4f} rms={v['rms']:7.3f}")
print("\n=== B. response = EACH GATE separately (un-attenuated), pooled decomposition ===")
agg={}; r2s=[]; pol={}
for g,marg in gm.items():
    o=decomp(marg,g)
    r2s.append(o['r2_multivar'])
    for kk,v in o['by_class'].items():
        a=agg.setdefault(kk,{'n':v['n'],'var':0.0}); a['var']+=v['rms']**2
    # polarity of this gate
    k,r=g.split('->')[0],int(g.split('->')[1].split(':')[0]); i=int(g[-1])
    pol[g]=('pull-UP(HIGH)' if PAT[r][i]==1 else 'pull-DOWN(LOW)')
tot=sum(a['var'] for a in agg.values())
print(f"per-gate multivariate R2: min={min(r2s):.4f} median={float(np.median(r2s)):.4f} max={max(r2s):.4f}")
print(f"{'class':14s} {'n':>4s} {'share':>8s} {'rms_mV':>9s}")
for kk,a in sorted(agg.items(),key=lambda z:-z[1]['var']):
    print(f"{kk:14s} {a['n']:4d} {a['var']/tot:8.4f} {math.sqrt(a['var']):9.3f}")
print("\n=== C. per-gate stats, margin and polarity ===")
print(f"{'gate':18s} {'polarity':16s} {'mean_mV':>10s} {'sd_mV':>8s} {'min_mV':>9s} {'sigma_to_fail':>13s} {'fails':>6s}")
for g,marg in gm.items():
    mu=marg.mean(); sd=marg.std(ddof=1)
    print(f"{g:18s} {pol[g]:16s} {mu:10.3f} {sd:8.3f} {marg.min():9.3f} {mu/sd:13.2f} {int((marg<0).sum()):6d}")
json.dump({'agg':{k:{'n':v['n'],'share':v['var']/tot,'rms':math.sqrt(v['var'])} for k,v in agg.items()}},
          open('/usr/local/src/stat-sim/qal/mcsize_skept/sk_sens.json','w'),indent=1)
