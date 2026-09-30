#!/usr/bin/env python3
"""(d) Does sigma = A_VT/sqrt(WL) reproduce IN SIMULATION when a device is upsized,
or is it only applied on paper?
Paper part : sigma is COMMANDED by mkmc.py, so the DRAW sigma is true by construction.
Sim part   : the testable prediction is that the CIRCUIT-LEVEL response spread must
             fall by the same factor. Check realized draw sigma AND realized margin sd
             across the geometry grid at 8x sigma (where spread is resolvable)."""
import re,glob,json,math,sys
import numpy as np
BT='/usr/local/src/stat-sim/qal/mcsize/'
PAT={1:[0,0,0,1,0,1,1,0],2:[1,1,1,0,1,0,0,1],3:[0,0,0,1,0,1,1,0],4:[1,1,1,0,1,0,0,1]}
def read_ms(p):
    v={}
    for ln in open(p):
        m=re.match(r'\s*([A-Za-z_0-9]+)\s*=\s*([-\d.eE+]+)\s*$',ln)
        if m: v[m.group(1).upper()]=float(m.group(2))
    return v
def sfiles(b):
    for ext in ('.mt','.ms'):
        h=[x for x in glob.glob(b+ext+'*') if x[len(b)+len(ext):].isdigit()]
        if h: return sorted(h,key=lambda y:int(y[len(b)+len(ext):]))
    return []
def read_res(p):
    L=open(p).read().splitlines(); hdr=L[0].split()
    nm=[h.split(':')[0].upper() for h in hdr[1:]]
    rows=[[float(x) for x in ln.split()[1:]] for ln in L[1:]
          if len(ln.split())==len(hdr) and ln.split()[0].isdigit()]
    return nm,np.array(rows)*1000.0
def grid_last(deck):
    """the BOUND instant measures in a slack.py grid deck are the LAST grid index"""
    txt=open(deck).read()
    gs=sorted(set(int(m) for m in re.findall(r'M_L12G(\d+)_',txt,re.I)))
    return gs[-1] if gs else None
def analyse(tag,deck):
    S=[read_ms(p) for p in sfiles(deck)]
    nm,D=read_res(deck+'.res')
    N=len(S)
    meta=json.load(open(deck+'.meta.json'))
    cellN=[d for d in meta['devices'] if d['kind']=='n' and abs(d['w_um']-d['w_nom_um']*(meta.get('sizing',{}).get('0.74:n',{}).get('w',1.0)))<1e-9 and d['w_nom_um']==0.74]
    sigN=cellN[0]['sigma_mV'] if cellN else None
    # realized draw sigma for the cell-n class
    idx=[i for i,x in enumerate(nm) if re.match(r'XN\d',x)]
    ss=0.0;df=0
    for i in idx:
        v=D[:,i]; ss+=((v-v.mean())**2).sum(); df+=len(v)-1
    real=math.sqrt(ss/df)
    # margin per gate at the LAST grid instant (= bound)
    g=grid_last(deck)
    mg={}
    for (k,r) in [(1,2),(2,3),(3,4)]:
        tg=f'M_L{k}{r}G{g}_'
        rail=np.array([s.get(tg+f'RAIL{r}',np.nan) for s in S])
        for i in range(8):
            vr=np.array([s.get(tg+f'O{r}_{i}',np.nan) for s in S])
            sgn=1 if PAT[r][i]==1 else -1
            mg[f'{k}->{r}:o{r}_{i}']=(vr-rail/2)*1000*sgn
    W=np.vstack(list(mg.values())); worst=W.min(axis=0)
    # pooled per-gate sd over pull-UP gates only (the binding polarity)
    up=[k for k in mg if PAT[int(k.split('->')[1].split(':')[0])][int(k[-1])]==1]
    pu=np.mean([mg[k].std(ddof=1) for k in up])
    return dict(tag=tag,N=N,area=meta['total_device_area_um2'],kvt=meta.get('kvt',1.0),
                sizing=meta.get('sizing',{}),cmd_sigN=sigN,real_sigN=real,
                worst_mean=worst.mean(),worst_sd=worst.std(ddof=1),worst_min=worst.min(),
                pullup_gate_sd=pu,nfail=int((worst<0).sum()))
rows=[]
for tag,deck in [('8x base',BT+'p2_k8.cir'),('8x W x2',BT+'p2k8_wx2.cir'),
                 ('8x W x4',BT+'p2k8_wx4.cir'),('8x L x2',BT+'p2k8_lx2.cir'),
                 ('1x base',BT+'p2_base.cir'),('1x W x2',BT+'p2_wx2.cir'),
                 ('1x W x4',BT+'p2_wx4.cir'),('1x L x2',BT+'p2_lx2.cir')]:
    try: rows.append(analyse(tag,deck))
    except Exception as e: print(f"{tag}: {type(e).__name__} {e}")
print(f"{'variant':9s} {'N':>3s} {'area':>7s} {'cmd_sigN':>9s} {'real_sigN':>9s} {'ratio':>6s} | "
      f"{'pullupSD':>9s} {'worstSD':>8s} {'worstMean':>10s} {'worstMin':>9s} {'fail':>5s}")
for r in rows:
    print(f"{r['tag']:9s} {r['N']:3d} {r['area']:7.3f} {r['cmd_sigN']:9.4f} {r['real_sigN']:9.4f} "
          f"{r['real_sigN']/r['cmd_sigN']:6.4f} | {r['pullup_gate_sd']:9.4f} {r['worst_sd']:8.4f} "
          f"{r['worst_mean']:10.3f} {r['worst_min']:9.3f} {r['nfail']:5d}")
print("\n=== (d) THE TEST: does a commanded sigma reduction of 1/sqrt(2) produce a")
print("    1/sqrt(2) reduction in the CIRCUIT-LEVEL spread? (8x sigma, resolvable) ===")
by={r['tag']:r for r in rows}
for a,b,pred in [('8x base','8x W x2',1/math.sqrt(2)),('8x base','8x W x4',0.5),
                 ('8x base','8x L x2',1/math.sqrt(2)),
                 ('1x base','1x W x2',1/math.sqrt(2)),('1x base','1x W x4',0.5),
                 ('1x base','1x L x2',1/math.sqrt(2))]:
    if a in by and b in by:
        A,B=by[a],by[b]
        rs=B['real_sigN']/A['real_sigN']; rp=B['pullup_gate_sd']/A['pullup_gate_sd']
        print(f"  {a} -> {b}: predicted {pred:.4f} | realized DRAW sigma ratio {rs:.4f} "
              f"| realized PULL-UP margin sd ratio {rp:.4f}   (miss {100*(rp/pred-1):+.1f}%)")
