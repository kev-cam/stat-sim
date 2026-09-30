import sys,json,os,math
sys.path.insert(0,'/usr/local/src/stat-sim/qal/fastwave_skept')
from sx import load,col,at,firstcross
TRIP=json.load(open('/usr/local/src/stat-sim/qal/fcrit/TRIP.json'))
rr=TRIP['S']['rows']
pts=sorted((v['vdd'], v['trip_V']) for v in rr.values())
def trip(rail):
    if rail<=pts[0][0]: return pts[0][1]*rail/pts[0][0]
    if rail>=pts[-1][0]: return pts[-1][1]*rail/pts[-1][0]
    for k in range(1,len(pts)):
        if pts[k][0]>=rail:
            (x0,y0),(x1,y1)=pts[k-1],pts[k]
            return y0+(rail-x0)/(x1-x0)*(y1-y0)
NB=19.323e-3
def analyse(prn, want, starts, nb=NB, tend=None, label=''):
    cols,rows=load(prn); T=col(cols,rows,'TIME')
    if tend is None: tend=T[-1]
    out={}
    for k in range(1,7):
        rail=col(cols,rows,'V(RAIL%d)'%k)
        ys=[col(cols,rows,'V(Y%d_%d)'%(k,i)) for i in range(4)]
        t0=starts[k-1]
        ok=[]
        for j,t in enumerate(T):
            if t<t0 or t>tend: ok.append(False); continue
            tr=trip(rail[j])
            good=True
            for i in range(4):
                if want[k-1][i]==1:
                    if ys[i][j] < tr+nb: good=False; break
                else:
                    if ys[i][j] > tr-nb: good=False; break
            ok.append(good)
        # first contiguous interval
        arr=None; hold=None; pk=None
        j=0
        while j<len(T):
            if ok[j]:
                a=j
                while j+1<len(T) and ok[j+1]: j+=1
                arr=T[a]; hold=T[j]-T[a]
                # peak margin inside interval
                m=1e9
                for jj in range(a,j+1):
                    tr=trip(rail[jj]); 
                    mm=min((ys[i][jj]-(tr+nb)) if want[k-1][i]==1 else ((tr-nb)-ys[i][jj]) for i in range(4))
                    m=min(m,mm) if False else m
                # peak of the per-instant min margin
                pk=max(min((ys[i][jj]-tr_) if want[k-1][i]==1 else (tr_-ys[i][jj]) for i in range(4))
                       for jj,tr_ in ((jj,trip(rail[jj])) for jj in range(a,j+1)))
                break
            j+=1
        out[k]=dict(arrival_ps=None if arr is None else arr*1e12,
                    own_level_ps=None if arr is None else (arr-t0)*1e12,
                    hold_ps=None if hold is None else hold*1e12,
                    peak_margin_mV=None if pk is None else pk*1e3,
                    rail_at_arrival=None if arr is None else at(T,rail,arr),
                    y_at_arrival=None if arr is None else [at(T,ys[i],arr) for i in range(4)],
                    y_at_end=[ys[i][-1] for i in range(4)],
                    rail_end=rail[-1])
    return out
