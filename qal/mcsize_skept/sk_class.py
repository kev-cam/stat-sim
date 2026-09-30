#!/usr/bin/env python3
import sys,math,json,re
def load(p):
    L=[l for l in open(p).read().splitlines() if l.strip()]
    hdr=L[0].split(); rows=[]
    for l in L[1:]:
        t=l.split()
        if len(t)!=len(hdr): continue
        try: rows.append([float(x) for x in t])
        except ValueError: continue
    return hdr,rows
meta=json.load(open('/usr/local/src/stat-sim/qal/mcsize/bt_mc_2001.cir.meta.json'))
geo={d['name'].upper():d for d in meta['devices']}
files=sys.argv[1:]
cols={}
for f in files:
    hdr,rows=load(f)
    for j,h in enumerate(hdr):
        if h=='STEP': continue
        cols.setdefault(h,[]).extend(r[j] for r in rows)
def cls(nm):
    b=nm.split(':')[0].upper()
    g=geo[b]; return f"{g['kind']}_W{g['w_um']:g}u_L{g['l_um']:g}u", g
groups={}
for nm,v in cols.items():
    c,g=cls(nm); groups.setdefault(c,{'dev':[],'g':g})['dev'].append((nm,v))
print(f"{'class':22s} {'ndev':>4s} {'cmd_mV':>8s} {'pooled_sd_mV':>12s} {'ratio':>7s} {'SE_ratio':>8s} {'z':>6s}  {'grandmean_mV':>12s}")
out={}
for c in sorted(groups,key=lambda k:-groups[k]['g']['sigma_mV']):
    G=groups[c]; cmd=G['g']['sigma_mV']
    # pooled: within-device variance about each device's own mean, df-correct
    ss=0.0; df=0; allv=[]
    for nm,v in G['dev']:
        n=len(v); m=sum(v)/n
        ss+=sum((x-m)**2 for x in v); df+=n-1; allv+=v
    pooled=math.sqrt(ss/df)*1e3
    ndev=len(G['dev'])
    se_ratio=1/math.sqrt(2*df)     # rel SE of an sd estimate
    r=pooled/cmd
    print(f"{c:22s} {ndev:4d} {cmd:8.4f} {pooled:12.4f} {r:7.4f} {se_ratio:8.4f} {(r-1)/se_ratio:6.2f}  {sum(allv)/len(allv)*1e3:12.4f}")
    out[c]=dict(ndev=ndev,cmd_mV=cmd,pooled_mV=pooled,ratio=r,z=(r-1)/se_ratio)
json.dump(out,open('/usr/local/src/stat-sim/qal/mcsize_skept/sk_class.json','w'),indent=1)
