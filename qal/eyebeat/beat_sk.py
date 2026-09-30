#!/usr/bin/env python3
"""SKEPT: re-score the QAL beat end to end on the running chain, with MY scorer,
over every iso-swing banktank beat row including the primary's three new rows."""
import sys, os, json, glob, numpy as np
sys.path.insert(0,'/usr/local/src/stat-sim/qal/fcrit_skept')
import skscore, sklib
SIG=6.441; NB=3*SIG/1000.0*1000.0   # mV
rows=[]
srcs = [("/usr/local/src/stat-sim/qal/banktank", "committed"),
        ("/usr/local/src/stat-sim/qal/fcrit/btk", "primary_new")]
for d,prov in srcs:
    for p in sorted(glob.glob(os.path.join(d,"c_m10_T*_H*_dv1200_free.cir"))):
        if not os.path.exists(p+".prn"): continue
        b=os.path.basename(p)[:-4]
        T=int(b.split("_T")[1].split("_")[0]); H=int(b.split("_H")[1].split("_")[0])
        r=skscore.score(p,4)
        for inst,lab in (("RAILPEAK","railpeak"),("CK","ck"),("STRICT_last","strict")):
            pass
        def ok(inst,nb):
            for L in r["links"]:
                m=L.get("m_"+inst)
                if m is None or m<nb: return False,(m if m is not None else -9e9)
            return True, min(L.get("m_"+inst) for L in r["links"] if L.get("m_"+inst) is not None)
        o90 = all(L["pass90"] for L in r["links"])
        okr,wr = ok("RAILPEAK",NB); okc,wc = ok("CK",NB); oks,ws = ok("STRICT_last",NB)
        ok0,w0 = ok("RAILPEAK",0.0)
        rows.append(dict(deck=b,prov=prov,T=T,H=H,pass90=o90,
                         func=okr,worst_mV=round(wr,2),
                         func_ck=okc,worst_ck=round(wc,2),
                         func_strict=oks,worst_strict=round(ws,2),
                         func_NB0=ok0))
rows.sort(key=lambda r:(r["H"],r["T"]))
print("H   T   prov        pass90  FUNC(railpeak) worst_mV   FUNC(ck)  worst   STRICT  worst")
for r in rows:
    print("%d %4d  %-11s %-6s  %-5s %10.2f   %-5s %8.2f   %-5s %8.2f"
          %(r["H"],r["T"],r["prov"],r["pass90"],r["func"],r["worst_mV"],
            r["func_ck"],r["worst_ck"],r["func_strict"],r["worst_strict"]))
print()
for H in sorted(set(r["H"] for r in rows)):
    rr=[r for r in rows if r["H"]==H]
    e90=min([r["T"] for r in rr if r["pass90"]], default=None)
    ef =min([r["T"] for r in rr if r["func"]], default=None)
    print("H=%d  earliest correct beat: 90%%bar %s ps   FUNCTIONAL %s ps   II %s -> %s ps"
          %(H, e90, ef, (H*e90 if e90 else None), (H*ef if ef else None)))
json.dump(rows,open("BEAT_SKEPT.json","w"),indent=1)
