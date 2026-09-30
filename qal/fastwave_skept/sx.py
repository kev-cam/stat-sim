import sys, math, json
def load(p):
    f=open(p); hdr=f.readline().split()
    cols={n.upper():i for i,n in enumerate(hdr)}
    rows=[]
    for ln in f:
        t=ln.split()
        if not t or t[0].startswith('End'): break
        try: rows.append([float(x) for x in t])
        except ValueError: break
    return cols, rows
def col(cols,rows,n):
    i=cols[n.upper()]; return [r[i] for r in rows]
def at(ts, ys, t):
    # linear interp
    for k in range(1,len(ts)):
        if ts[k]>=t:
            t0,t1=ts[k-1],ts[k]
            if t1==t0: return ys[k]
            f=(t-t0)/(t1-t0)
            return ys[k-1]+f*(ys[k]-ys[k-1])
    return ys[-1]
def firstcross(ts,ys,lev,rise=True,tmin=0.0):
    for k in range(1,len(ts)):
        if ts[k]<tmin: continue
        a,b=ys[k-1],ys[k]
        if (rise and a<lev<=b) or ((not rise) and a>lev>=b):
            if b==a: return ts[k]
            return ts[k-1]+(lev-a)/(b-a)*(ts[k]-ts[k-1])
    return None
