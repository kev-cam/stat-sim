#!/usr/bin/env python3
"""Independent audit of per-device DELVTO independence from Xyce .res files."""
import sys, math, glob, json
def load(p):
    L=[l for l in open(p).read().splitlines() if l.strip()]
    hdr=L[0].split()
    rows=[]
    for l in L[1:]:
        t=l.split()
        if len(t)!=len(hdr): continue
        try: rows.append([float(x) for x in t])
        except ValueError: continue
    return hdr,rows
def stats(v):
    n=len(v); m=sum(v)/n
    sd=math.sqrt(sum((x-m)**2 for x in v)/(n-1)) if n>1 else 0.0
    return n,m,sd
def corr(a,b):
    n=len(a); ma=sum(a)/n; mb=sum(b)/n
    sa=math.sqrt(sum((x-ma)**2 for x in a)); sb=math.sqrt(sum((x-mb)**2 for x in b))
    if sa==0 or sb==0: return float('nan')
    return sum((a[i]-ma)*(b[i]-mb) for i in range(n))/(sa*sb)

files=sys.argv[1:]
allhdr=None; cols={}
for f in files:
    hdr,rows=load(f)
    if allhdr is None: allhdr=hdr
    assert hdr==allhdr, f"header mismatch {f}"
    for j,h in enumerate(hdr):
        if h=='STEP': continue
        cols.setdefault(h,[]).extend(r[j] for r in rows)
names=[h for h in allhdr if h!='STEP']
N=len(cols[names[0]])
print(f"files={len(files)} devices={len(names)} samples={N}")
# per-device stats + distinct counts
print(f"\n{'device':22s} {'n':>5s} {'distinct':>9s} {'mean_mV':>10s} {'sd_mV':>9s} {'min':>9s} {'max':>9s} {'minZ':>7s} {'maxZ':>7s}")
rep=[]
for nm in names:
    v=cols[nm]; n,m,sd=stats(v)
    d=len(set(v))
    z=[(x-m)/sd for x in v] if sd>0 else [0]
    rep.append(dict(name=nm,n=n,distinct=d,mean_mV=m*1e3,sd_mV=sd*1e3,minz=min(z),maxz=max(z)))
for r in rep[:6]+rep[30:34]+rep[-12:]:
    print(f"{r['name']:22s} {r['n']:5d} {r['distinct']:9d} {r['mean_mV']:10.4f} {r['sd_mV']:9.4f} "
          f"{min(cols[r['name']])*1e3:9.3f} {max(cols[r['name']])*1e3:9.3f} {r['minz']:7.2f} {r['maxz']:7.2f}")
# FAILURE MODE: shared param -> some pair has |r|=1 and identical values
print("\n--- SHARED-PARAM TEST: pairwise correlation over all device pairs ---")
worst=[]; cs=[]
ident=0
for i in range(len(names)):
    for j in range(i+1,len(names)):
        a=cols[names[i]]; b=cols[names[j]]
        if a==b: ident+=1
        c=corr(a,b); cs.append(c); worst.append((abs(c),c,names[i],names[j]))
worst.sort(reverse=True)
mc=sum(cs)/len(cs)
sdc=math.sqrt(sum((x-mc)**2 for x in cs)/(len(cs)-1))
print(f"pairs={len(cs)} identical-value pairs={ident}  mean r={mc:+.5f}  sd r={sdc:.5f}  "
      f"expected noise 1/sqrt(N)={1/math.sqrt(N):.5f}")
print(f"pairs with |r|>0.9: {sum(1 for x in cs if abs(x)>0.9)}   |r|>0.5: {sum(1 for x in cs if abs(x)>0.5)}")
print("top-5 |r|:", [f"{w[2]}~{w[3]}:{w[1]:+.4f}" for w in worst[:5]])
# sigma vs commanded, by class
print("\n--- per-class pooled sigma ---")
json.dump(dict(names=names,N=N,mean_r=mc,ident_pairs=ident,
               per_dev=rep), open('/usr/local/src/stat-sim/qal/mcsize_skept/sk_res_out.json','w'),indent=1)
