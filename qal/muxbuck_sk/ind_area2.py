#!/usr/bin/env python3
"""Same PDK estimator, now with the PDK's OWN legality rule inductor_minD applied."""
import math
MU = math.pi*4e-7
GRID = 0.005
def GridFix(x): return round(x/GRID)*GRID
def minD(w,s,nr):
    r2=math.sqrt(2)
    if nr==1: return GridFix((s+w+w)*(1+r2)/2+GRID*2)*2
    if nr==2: return GridFix((GridFix(w/r2+s/2)+GridFix(s*0.4143)+0.02+w)*2*(1+r2)+0.01)
    return GridFix(((GridFix(w/r2+s/2)+GridFix(s*0.4143))*2+2*s+4*w)*(1+r2))
def L_of(d,w,s,nr):
    da=d+nr*(w+s)-s; ro=(nr*(w+s)-s)/da
    return MU*0.5*1.07*nr*nr*da*(math.log(2.29/ro)+0.19*ro*ro)
def R_of(d,w,s,nr): return (nr*(d+w+(nr-1)*(s+w))*3.314+60e-6)/w*0.01
def d_for(L,w,s,nr,lo=1e-9,hi=0.05):
    for _ in range(300):
        m=.5*(lo+hi)
        if L_of(m,w,s,nr)<L: lo=m
        else: hi=m
    return .5*(lo+hi)
U=1e-6
def row(L,w,s,nr):
    d=d_for(L,w*U,s*U,nr)*1e6
    dmin=minD(w,s,nr)
    legal = d>=dmin
    rad=nr*(w+s)-s; dout=d+2*rad
    A=2*(math.sqrt(2)-1)*dout**2
    return d,dmin,legal,dout,A,R_of(d*U,w*U,s*U,nr)
for L,tag in ((1e-9,"1 nH RECHARGE"),(15e-9,"15 nH TRANSFER")):
    print(f"\n=== {tag} : legal windings only (PDK inductor_minD enforced), s=2.1u ===")
    print(f"{'w':>5} {'nr':>3} {'d_in':>9} {'d_min':>8} {'ok':>4} {'d_out':>9} {'A_oct um^2':>13} {'R ohm':>8}")
    best=None
    for nr in range(1,13):
        for w in (2,3,5,10):
            d,dm,ok,dout,A,R=row(L,w,2.1,nr)
            flag="OK" if ok else "--"
            if w==2 or ok:
                print(f"{w:5.1f} {nr:3d} {d:9.2f} {dm:8.2f} {flag:>4} {dout:9.2f} {A:13,.0f} {R:8.2f}")
            if ok and (best is None or A<best[0]): best=(A,w,nr,R,dout)
    print(f"  -> SMALLEST LEGAL: {best[0]:,.0f} um^2  (w={best[1]}u nr={best[2]}, R={best[3]:.2f} ohm, d_out={best[4]:.1f} um)")
