#!/usr/bin/env python3
"""Extract Vt per device per .step from sk_a_indep.cir.prn by constant current.
sel=0 none shifted, 1..6 shift exactly one device by +10.000 mV.
Devices: XA,XB = base cell n (IDENTICAL geometry, the shared-draw trap);
XC = W x4 cell n; XD = L x2 cell n; XE = base cell p; XF = W x4 cell p."""
import re
DEV=[('XA','I(VDA)','n',0.74,0.13),('XB','I(VDB)','n',0.74,0.13),
     ('XC','I(VDC)','n',2.96,0.13),('XD','I(VDD2)','n',0.74,0.26),
     ('XE','I(VSE)','p',1.12,0.13),('XF','I(VSF)','p',4.48,0.13)]
SEL={0:'none',1:'XA',2:'XB',3:'XC',4:'XD',5:'XE',6:'XF'}
txt=open('sk_a_indep.cir.prn').read().splitlines()
hdr=None; steps=[]; cur=[]
for ln in txt:
    p=ln.split()
    if not p: continue
    if p[0]=='Index':
        if cur: steps.append(cur)
        hdr=p; cur=[]; continue
    if p[0].startswith('End'):
        if cur: steps.append(cur); cur=[]
        continue
    try: cur.append([float(x) for x in p])
    except ValueError: continue
if cur: steps.append(cur)
print(f"steps parsed: {len(steps)}  rows/step: {[len(s) for s in steps]}")
col={h:i for i,h in enumerate(hdr)}
VG=[0.002*i for i in range(601)]
def vt(rows,cname,kind,w,l):
    ic=100e-9*w/l
    j=col[cname]
    I=[abs(r[j]) for r in rows]
    V=[0.002*int(r[0]) for r in rows]
    if kind=='n':
        for i in range(1,len(I)):
            if I[i-1]<ic<=I[i]:
                return V[i-1]+(ic-I[i-1])/(I[i]-I[i-1])*(V[i]-V[i-1])
    else:
        for i in range(1,len(I)):
            if I[i-1]>=ic>I[i]:
                return V[i-1]+(I[i-1]-ic)/(I[i-1]-I[i])*(V[i]-V[i-1])
    return None
T={}
for si,rows in enumerate(steps):
    T[si]={nm:vt(rows,c,k,w,l) for nm,c,k,w,l in DEV}
print(f"\nVt (V) by step:\n{'sel':12s} " + " ".join(f"{d[0]:>10s}" for d in DEV))
for si in sorted(T):
    print(f"{si} ({SEL.get(si,'?'):>7s}) " + " ".join(f"{T[si][d[0]]:10.6f}" if T[si][d[0]] else "      None" for d in DEV))
print(f"\nSHIFT vs sel=0, in mV (+10.000 mV commanded on the named device only):")
print(f"{'shifted':12s} " + " ".join(f"{d[0]:>10s}" for d in DEV))
for si in sorted(T):
    if si==0: continue
    row=[]
    for d in DEV:
        a,b=T[si][d[0]],T[0][d[0]]
        row.append(f"{(a-b)*1000:10.6f}" if (a and b) else "      None")
    print(f"{SEL.get(si,'?'):12s} " + " ".join(row))
print(f"\n(d.1) d(Vt)/d(DELVTO) at each geometry -- must stay ~1.0 for the")
print(f"      sigma = A_VT/sqrt(WL) knob to mean the same thing after a resize:")
print(f"{'device':8s} {'kind':5s} {'W_um':>6s} {'L_um':>6s} {'WL':>7s} {'dVt/dDELVTO':>12s}")
for si,d in [(1,DEV[0]),(2,DEV[1]),(3,DEV[2]),(4,DEV[3]),(5,DEV[4]),(6,DEV[5])]:
    a,b=T[si][d[0]],T[0][d[0]]
    if a and b: print(f"{d[0]:8s} {d[2]:5s} {d[3]:6.2f} {d[4]:6.2f} {d[3]*d[4]:7.4f} {(a-b)/0.010:12.4f}")
