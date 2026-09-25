"""Activity-weighted composition for a TH-cell netlist.

The DIMS arm's alpha=0.250 correction came from DIMS MINTERM MUTUAL EXCLUSIVITY
(1 of the 4 TH22 minterms of a 2-input gate fires per op).  That justification
does NOT carry over to a direct-threshold netlist, which has no minterm sets --
its cells ARE the function, so nearly every cell is on the real path.  This tool
measures the firing probability per cell type directly, by evaluating the
netlist over random DATA vectors, and composes energy only from the cells whose
E(C_L) has actually been measured.  Unmeasured cells are reported as a firing
count, never as an energy number.

usage: activity.py [netlist.v ...]
"""
import sys,json,random,collections
sys.path.insert(0,'/usr/local/src/stat-sim/qal/synth/threeway')
import verify_direct as V, cost_inputs as C
E={"th22":(39.398,1.7369),"th12":(23.004,1.4697),"th13":(31.861,1.4688)}
caps=C.pin_caps()
def run(v,top,ext=2.0,NV=4000):
    cells,ports=V.load(v,top); N=V.Net(cells,ports)
    sink=collections.defaultdict(list)
    for t,ins,y in cells:
        for p,n in zip(['a','b','c','d'],ins): sink[n].append((t,p))
    CL={}
    for t,ins,y in cells:
        cl = ext if not sink[y] else 0.0
        for st,sp in sink[y]: cl += caps.get((st,sp),0.0)
        CL[y]=cl
    rnd=random.Random(4242)
    fir=collections.defaultdict(float); firCL=collections.defaultdict(float)
    for _ in range(NV):
        val=N.drive({k:rnd.randrange(256) for k in 'abcefg'})
        for t,ins,y in N.cells:
            if val[y]: fir[t]+=1; firCL[t]+=CL[y]
    print('== %s  (%d cells)'%(v,len(cells)))
    tot=0.0; unk=collections.Counter(); unkCL=0.0; nfire=0.0
    for t in sorted(fir):
        n=fir[t]/NV; scl=firCL[t]/NV; nfire+=n
        if t in E:
            E0,k=E[t]; e=n*E0+k*scl; tot+=e
            print('   %-8s firings/op=%6.2f  sum CL of firing=%7.2f fF  E=%8.1f fJ  [MEASURED]'%(t,n,scl,e))
        else:
            unk[t]=n; unkCL+=scl
            print('   %-8s firings/op=%6.2f  sum CL of firing=%7.2f fF  E=  UNKNOWN  [NO MEASUREMENT]'%(t,n,scl))
    print('   TOTAL firings/op=%.2f of %d cells (alpha=%.4f)'%(nfire,len(cells),nfire/len(cells)))
    print('   energy from MEASURED cells = %.1f fJ/op ; unmeasured firings/op = %.2f (sum CL %.1f fF)'
          %(tot,sum(unk.values()),unkCL))
    return tot,nfire,dict(unk),unkCL
FILES=sys.argv[1:] or ['work/sha_slice_th_clean.v','work/sha_slice_direct_spice.v',
                       'work/sha_slice_direct_full.v','work/sha_slice_direct_cd.v']
for f in FILES:
    run(f,'sha_slice'); print()
