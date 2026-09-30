import sys,os,math,re,json
sys.path.insert(0,'/usr/local/src/stat-sim/qal/fastwave_skept')
from sx import load,col,at,firstcross
H='/usr/local/src/stat-sim/qal/fastwave/'
def one(tag):
    f=H+'h_'+tag+'.cir.prn'; d=H+'h_'+tag+'.cir'
    if not os.path.exists(f): return None
    src=open(d).read()
    L=float(re.search(r'LT=([0-9.]+)n',src).group(1))*1e-9
    dv=1.65
    cols,rows=load(f); T=col(cols,rows,'TIME')
    try:
        bka,bkb,sw,ilt=[col(cols,rows,n) for n in ('V(BKA)','V(BKB)','V(SW)','I(LT)')]
        xea,xesw,xer,xeb=[col(cols,rows,n) for n in ('V(XEA)','V(XESW)','V(XER)','V(XEB)')]
    except KeyError: return None
    tz=firstcross(T,ilt,0.0,rise=False,tmin=52e-12)
    if tz is None: return None
    th=tz-50e-12
    t0=1.5e-12
    def dd(v): return at(T,v,tz)-at(T,v,t0)
    EA,ESW,ER,EB=dd(xea),dd(xesw),dd(xer),dd(xeb)
    Ron=10.0*(ESW-EB)/ER if ER>0 else float('nan')
    Cser=(th/math.pi)**2/L
    Z0=math.sqrt(L/Cser)
    Q=Z0/(Ron+10.0)
    ipk=max(ilt); kpk=ilt.index(ipk)
    Rinst=(sw[kpk]-bkb[kpk])/ipk if ipk!=0 else float('nan')
    return dict(tag=tag,L_nH=L*1e9,t_hop_ps=th*1e12,Cser_fF=Cser*1e15,Z0=Z0,
                Ron=Ron,Rinst=Rinst,Q=Q,VBPK=max(bkb),
                VBEND=at(T,bkb,T[-1]-5e-12),VA_open=at(T,bka,tz),IPK=ipk)
if __name__=='__main__':
    for t in sys.argv[1:]:
        r=one(t)
        if r is None: print('%-24s  (no data)'%t); continue
        print('%-24s L=%5.1fnH t_hop=%7.2fps Cser=%7.2ffF Z0=%7.1f Ron=%7.2f Rinst=%7.2f Q=%6.2f VBPK=%.4f VBEND=%.4f VAopen=%.4f IPK=%.4fmA'
              %(r['tag'],r['L_nH'],r['t_hop_ps'],r['Cser_fF'],r['Z0'],r['Ron'],r['Rinst'],r['Q'],r['VBPK'],r['VBEND'],r['VA_open'],r['IPK']*1e3))
