#!/usr/bin/env python3
"""(e) FULL sizing cost audit: area, sigma, level time, AND nominal margin.
The committed study reported yield / area / level time / capacitance proxy.
It did NOT report what happens to the NOMINAL margin -- which is the thing the
sigma purchase was supposed to protect. Measured here at the identical bound
instant (G8 = 601/801/1001 ps) across all four geometries."""
import re,glob,json,math
import numpy as np
BT='/usr/local/src/stat-sim/qal/mcsize/'
PAT={2:[1,1,1,0,1,0,0,1],3:[0,0,0,1,0,1,1,0],4:[1,1,1,0,1,0,0,1]}
G=json.load(open(BT+'meas_bt_grid.json'))
def read_ms(p):
    v={}
    for ln in open(p):
        m=re.match(r'\s*([A-Za-z_0-9]+)\s*=\s*([-\d.eE+]+)\s*$',ln)
        if m: v[m.group(1).upper()]=float(m.group(2))
    return v
def sfiles(b):
    h=[x for x in glob.glob(b+'.mt*') if x[len(b)+3:].isdigit()]
    return sorted(h,key=lambda y:int(y[len(b)+3:]))
def load(deck):
    S=[read_ms(p) for p in sfiles(deck)]
    meta=json.load(open(deck+'.meta.json'))
    return S,meta
def margins(S,g):
    mg={}
    for (k,r) in [(1,2),(2,3),(3,4)]:
        tg=f'M_L{k}{r}G{g}_'
        rail=np.array([s.get(tg+f'RAIL{r}',np.nan) for s in S])
        for i in range(8):
            vr=np.array([s.get(tg+f'O{r}_{i}',np.nan) for s in S])
            sgn=1 if PAT[r][i]==1 else -1
            mg[f'{k}->{r}:o{r}_{i}']=(vr-rail/2)*1000*sgn
    return mg
def slackof(S,N):
    """level time = T - slack, slack = bound - earliest grid instant correct through bound"""
    per={}
    for (k,r) in [(1,2),(2,3),(3,4)]:
        ts=[G[f'L{k}{r}G{g}']['t_ps'] for g in range(9)]
        ok=np.ones((N,9),dtype=bool)
        for g in range(9):
            tg=f'M_L{k}{r}G{g}_'
            rail=np.array([s.get(tg+f'RAIL{r}',np.nan) for s in S])
            for i in range(8):
                vr=np.array([s.get(tg+f'O{r}_{i}',np.nan) for s in S])
                th=rail/2
                ok[:,g]&=((vr>th) if PAT[r][i]==1 else (vr<th))
        tv=np.full(N,np.nan)
        for j in range(N):
            if not ok[j,8]: tv[j]=np.inf; continue
            g=8
            while g>0 and ok[j,g-1]: g-=1
            tv[j]=ts[g]
        per[(k,r)]=ts[8]-tv
    return np.vstack([per[x] for x in per]).min(axis=0),per
print(f"{'variant':8s} {'area':>7s} {'dArea':>7s} {'sigN':>7s} {'dSig':>7s} | "
      f"{'nomWorst':>9s} {'dNom':>7s} {'pullupSD':>9s} {'marg/sig':>9s} | "
      f"{'slack':>7s} {'levelT':>8s} {'fail':>5s}")
res={}
for tag,deck in [('base',BT+'p2_base.cir'),('W x2',BT+'p2_wx2.cir'),
                 ('W x4',BT+'p2_wx4.cir'),('L x2',BT+'p2_lx2.cir')]:
    S,meta=load(deck); N=len(S)
    mg=margins(S,8); Wm=np.vstack(list(mg.values())); worst=Wm.min(axis=0)
    up=[k for k in mg if PAT[int(k.split('->')[1].split(':')[0])][int(k[-1])]==1]
    dn=[k for k in mg if k not in up]
    pu=float(np.mean([mg[k].std(ddof=1) for k in up]))
    pd=float(np.mean([mg[k].std(ddof=1) for k in dn]))
    sl,per=slackof(S,N)
    fin=np.isfinite(sl)
    sigN=[d['sigma_mV'] for d in meta['devices'] if d['w_nom_um']==0.74][0]
    res[tag]=dict(area=meta['total_device_area_um2'],sigN=sigN,nom=float(worst.mean()),
                  pu=pu,pd=pd,slack=float(sl[fin].mean()),N=N,
                  nfail=int((~fin).sum()),worst_min=float(worst.min()),
                  msig=float(worst.mean()/pu))
for tag,r in res.items():
    b=res['base']
    print(f"{tag:8s} {r['area']:7.3f} {100*(r['area']/b['area']-1):+6.1f}% {r['sigN']:7.3f} "
          f"{100*(r['sigN']/b['sigN']-1):+6.1f}% | {r['nom']:9.2f} {100*(r['nom']/b['nom']-1):+6.1f}% "
          f"{r['pu']:9.3f} {r['msig']:9.1f} | {r['slack']:7.2f} {200-r['slack']:8.2f} {r['nfail']:5d}")
print("\n=== per-gate sd at 1x sigma, pull-UP gates (the binding polarity) ===")
print(f"{'gate':16s} " + " ".join(f"{t:>10s}" for t in res))
allmg={}
for tag,deck in [('base',BT+'p2_base.cir'),('W x2',BT+'p2_wx2.cir'),
                 ('W x4',BT+'p2_wx4.cir'),('L x2',BT+'p2_lx2.cir')]:
    S,_=load(deck); allmg[tag]=margins(S,8)
for g in allmg['base']:
    r=int(g.split('->')[1].split(':')[0]); i=int(g[-1])
    if PAT[r][i]!=1: continue
    print(f"{g:16s} " + " ".join(f"{allmg[t][g].std(ddof=1):10.3f}" for t in res))
print("\n=== per-gate MEAN margin at 1x sigma, pull-UP gates ===")
for g in allmg['base']:
    r=int(g.split('->')[1].split(':')[0]); i=int(g[-1])
    if PAT[r][i]!=1: continue
    print(f"{g:16s} " + " ".join(f"{allmg[t][g].mean():10.3f}" for t in res))
print("\n=== pull-DOWN polarity sd (regime check) ===")
for tag,r in res.items(): print(f"  {tag:8s} pull-up sd {r['pu']:8.3f}  pull-down sd {r['pd']:8.3f}")
