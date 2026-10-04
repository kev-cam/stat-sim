#!/usr/bin/env python3
"""Analyze the self-timed vs clocked accumulator: functional match + energy/duty.

Functional: decode state s3..s0 over time; both decks must reach the same running
count (x=1, N ops -> state N). Energy: EVDD per deck (supply integral); the ratio
golden/self-timed vs duty is the clock-floor win — it should grow with idle duty.
"""
import json, glob, sys, re

def load(prn):
    f=open(prn); hdr=f.readline().split(); cols={n:i for i,n in enumerate(hdr)}; rows=[]
    for line in f:
        p=line.split()
        if not p or p[0].lower().startswith('end'): continue
        try: rows.append([float(x) for x in p])
        except ValueError: continue
    return cols, rows

def col(cols, want):
    for k in cols:
        if k.upper().startswith(want.upper()): return cols[k]
    return None

def at(t, ts, vs):
    if t<=ts[0]: return vs[0]
    for k in range(1,len(ts)):
        if ts[k]>=t:
            f=(t-ts[k-1])/(ts[k]-ts[k-1]) if ts[k]!=ts[k-1] else 0
            return vs[k-1]+f*(vs[k]-vs[k-1])
    return vs[-1]

def state_at(t, ts, S):
    v=0
    for i in range(4):
        if at(t, ts, S[i])>0.6: v|=(1<<i)
    return v

def evdd(base):
    for fn in glob.glob(base+".cir.mt0")+glob.glob(base+".mt0"):
        m=re.search(r'EVDD\s*=\s*([-+0-9.eE]+)', open(fn).read())
        if m: return float(m.group(1))
    return None

def analyze(base):
    meta=json.load(open(base+".meta.json"))
    cols,rows=load(base+".cir.prn")
    ti=col(cols,'TIME'); ts=[r[ti] for r in rows]
    S=[[r[col(cols,'V(s%d)'%i)] for r in rows] for i in range(4)]
    Tc=meta['Tc_ns']*1e-9; d=meta['duty_cycles']; n=meta['nops']; Ttot=meta['Ttot_ns']*1e-9
    # sample state just before each op's successor (end of its settle), + final
    traj=[]
    for k in range(n):
        # op k's capture edge is at 0.5n + k*d*Tc; sample ~1 ns later (settled,
        # before the next op which is d*Tc >= 2 ns away)
        t = min(0.5e-9 + (1+k*d)*Tc + 1.0e-9, Ttot-0.05e-9)
        traj.append(state_at(t, ts, S))
    final=state_at(Ttot-0.05e-9, ts, S)
    return {"mode":meta['mode'],"duty":d,"nops":n,"final":final,"traj":traj,
            "E_fJ": (evdd(base) or 0)*1e15, "Ttot_ns":meta['Ttot_ns']}

if __name__=="__main__":
    duties=[2,4,10]
    print("=== FUNCTIONAL (x=1, %d ops -> state should = op index) ==="%6)
    allmatch=True
    res={}
    for d in duties:
        g=analyze("g_d%d"%d); st=analyze("st_d%d"%d); res[d]=(g,st)
        match = g['traj']==st['traj'] and g['final']==st['final']==g['nops']
        allmatch = allmatch and match
        print("duty 1/%-2d  golden traj=%s final=%d | selftimed traj=%s final=%d  %s"
              %(d,g['traj'],g['final'],st['traj'],st['final'],"MATCH" if match else "*** MISMATCH ***"))
    print("FUNCTIONAL:", "PASS" if allmatch else "*** FAIL ***")
    print("\n=== ENERGY vs DUTY (EVDD over the window; same %d ops each) ==="%6)
    print("%-8s %12s %12s %10s %s"%("duty","golden fJ","selftimed fJ","ratio","window"))
    for d in duties:
        g,st=res[d]
        ratio = g['E_fJ']/st['E_fJ'] if st['E_fJ'] else float('nan')
        print("1/%-6d %12.1f %12.1f %9.2fx  %s ns"%(d,g['E_fJ'],st['E_fJ'],ratio,g['Ttot_ns']))
    print("\nThe clocked (golden) deck clocks every cycle incl. idle; the self-timed")
    print("deck captures only on ops. Ratio>1 and GROWING with duty = the clock-floor win.")
