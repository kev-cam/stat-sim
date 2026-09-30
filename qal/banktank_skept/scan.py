#!/usr/bin/env python3
"""INDEPENDENT skeptic scanner.  Nothing imported from the study's extract.py.
Windows are derived from the WAVEFORMS, not from the schedule.
"""
import sys, json

PAT=[1,1,1,0,1,0,0,1]
NB=4; MG=8
def in_hi(k,i): return (PAT[i]==1) if (k%2==1) else (PAT[i]==0)

def read(p):
    hdr=None; rows=[]
    for ln in open(p):
        q=ln.split()
        if hdr is None and q and q[0].lower()=='index':
            hdr=[h.upper() for h in q]; continue
        if hdr is None or not q or q[0].lower().startswith('end'): continue
        try: rows.append([float(x) for x in q])
        except ValueError: continue
    return hdr,rows

def ov(a,b):
    return max(0.0, min(a[1],b[1])-max(a[0],b[0]))

def analyse(prn, T, label):
    hdr,rows=read(prn)
    C=lambda n: hdr.index(n.upper())
    t=[r[C('TIME')]*1e12 for r in rows]
    IL={k:[r[C('I(L%d)'%k)] for r in rows] for k in range(1,NB+1)}
    RL={k:[r[C('V(RAIL%d)'%k)] for r in rows] for k in range(1,NB+1)}
    OO={(k,i):[r[C('V(O%d_%d)'%(k,i))] for r in rows] for k in range(1,NB+1) for i in range(MG)}
    out={'label':label,'T':T,'n_pts':len(rows)}

    # ---- WAVEFORM conduction windows per inductor, several thresholds
    cond={}
    for th in (1e-6, 1e-5, 1e-4, 1e-3):
        segs={}
        for k in range(1,NB+1):
            s=[];cur=None
            for j,v in enumerate(IL[k]):
                on=abs(v)>th
                if on and cur is None: cur=t[j]
                if not on and cur is not None:
                    if t[j]-cur>0.5: s.append((cur,t[j]))
                    cur=None
            if cur is not None: s.append((cur,t[-1]))
            segs[k]=s
        # max simultaneous
        edges=sorted(set([x for k in segs for sg in segs[k] for x in sg]))
        mx=0;mxt=None;who=None
        for a,b in zip(edges,edges[1:]):
            mid=0.5*(a+b)
            act=[k for k in segs if any(s[0]<=mid<=s[1] for s in segs[k])]
            if len(act)>mx: mx,mxt,who=len(act),mid,act
        cond['th_%g'%th]={'segments':{k:[[round(x,2) for x in s] for s in segs[k]] for k in segs},
                          'max_simultaneous':mx,'at_ps':mxt,'which':who}
    out['inductor_conduction']=cond

    # ---- data-valid, rail-referenced, my own implementation
    def settle(k,i,v,rail): return 100.0*((1.0-v/rail) if in_hi(k,i) else (v/rail))
    def guard(k,i,v,rail): return (v<=0.10*rail) if in_hi(k,i) else (v>=0.50*rail)
    dv={}
    railstart={}
    for k in range(1,NB+1):
        # rail start = first time rail > 5% of its own peak
        pk=max(RL[k]); ts=None
        for j in range(len(t)):
            if RL[k][j]>0.05*pk: ts=t[j]; break
        railstart[k]=ts
        got=None
        for j in range(len(t)):
            rail=RL[k][j]
            if t[j]<ts or rail<=0.05: continue
            if all(settle(k,i,OO[(k,i)][j],rail)>=90.0 and guard(k,i,OO[(k,i)][j],rail) for i in range(MG)):
                got=t[j]; break
        dv[k]=got
    out['rail_start_waveform_ps']=railstart
    out['data_valid_ps']=dv

    # ---- ramp window from waveform: rail start -> rail peak
    ramp={}
    for k in range(1,NB+1):
        pk=max(RL[k]); jpk=RL[k].index(pk)
        ramp[k]=(railstart[k], t[jpk])
    out['ramp_waveform_ps']={k:[round(x,3) for x in ramp[k]] for k in ramp}

    # ---- resolving window: first motion of any output of bank k -> data valid
    resolve={}
    for k in range(1,NB+1):
        first=None
        for j in range(len(t)):
            if t[j]<railstart[k]-50: continue
            if any(abs(OO[(k,i)][j]-OO[(k,i)][0])>0.02 for i in range(MG)):
                first=t[j]; break
        resolve[k]=(first if first else railstart[k], dv[k] if dv[k] else t[-1])
    out['resolving_waveform_ps']={k:[round(x,3) for x in resolve[k]] for k in resolve}

    # ---- EXHAUSTIVE pairwise intersection, waveform windows
    sets={'ramp':ramp,'resolve':resolve}
    inter={}
    for na,A in sets.items():
        for nb_,B in sets.items():
            for ka in A:
                for kb in B:
                    if na==nb_ and ka==kb: continue
                    o=ov(A[ka],B[kb])
                    if o>1e-9: inter['%s%d_x_%s%d'%(na,ka,nb_,kb)]=round(o,3)
    out['pairwise_intersections_ps']=inter
    out['CROSS_BANK_ramp_x_resolve_pred_ps']={k: round(ov(ramp[k],resolve[k-1]),3) for k in range(2,NB+1)}
    out['CROSS_BANK_ramp_x_ramp_pred_ps']={k: round(ov(ramp[k],ramp[k-1]),3) for k in range(2,NB+1)}
    return out,hdr,rows,t,RL,OO,IL

if __name__=='__main__':
    prn=sys.argv[1]; T=float(sys.argv[2]); lab=sys.argv[3]
    o,_,_,_,_,_,_=analyse(prn,T,lab)
    print(json.dumps(o,indent=1,default=str))
