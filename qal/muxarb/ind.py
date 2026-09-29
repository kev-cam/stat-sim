import math
mu=math.pi*4e-7
def Lval(d_um,w,s,nr):
    d=d_um*1e-6; W=(nr*(w+s)-s)*1e-6
    davg=d+W; ro=W/davg
    return mu*0.5*1.07*nr*nr*davg*(math.log(2.29/ro)+0.19*ro*ro)
def Rval(d_um,w,s,nr):
    d=d_um*1e-6; ww=w*1e-6; ss=s*1e-6
    return (nr*(d+ww+(nr-1)*(ss+ww))*3.314+60e-6)/ww*0.01
def GridFix(x,g=0.005):  # 5nm grid, as SG13_GRID
    return round(x/g)*g
def minD(w,s,nr):
    r2=math.sqrt(2)
    if nr==1: return GridFix((s+2*w)*(1+r2)/2+g0*2)*2
    if nr==2: return GridFix((GridFix(w/r2+s/2)+GridFix(s*0.4143)+0.02+w)*2*(1+r2)+0.01)
    return GridFix(((GridFix(w/r2+s/2)+GridFix(s*0.4143))*2+2*s+4*w)*(1+r2))
g0=0.005
def solve(Ltgt,w,s,nr):
    lo,hi=0.1,20000.0
    for _ in range(200):
        mid=(lo+hi)/2
        if Lval(mid,w,s,nr)<Ltgt: lo=mid
        else: hi=mid
    return (lo+hi)/2
OCT=2*(math.sqrt(2)-1)
for Ltgt,name in [(1e-9,'1nH recharge'),(15e-9,'15nH transfer')]:
    print('===',name)
    for nr in range(1,13):
        w,s=2.0,2.1
        din=solve(Ltgt,w,s,nr)
        dmin=minD(w,s,nr)
        W=nr*(w+s)-s
        dout=din+2*W
        legal = din>=dmin
        print(f'  nr={nr:2d} d_in={din:9.2f} d_min={dmin:8.2f} {"LEGAL " if legal else "ILLEGAL"} d_out={dout:9.2f} oct={OCT*dout*dout:12.1f} um2  bbox={dout*dout:12.1f}  R={Rval(din,w,s,nr):7.2f} ohm')
