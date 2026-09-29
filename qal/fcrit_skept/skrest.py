import sys, os, glob, json, numpy as np
sys.path.insert(0,'/usr/local/src/stat-sim/qal/fcrit_skept')
import skscore, sklib
QAL="/usr/local/src/stat-sim/qal"; SIG=6.441; NB=3*SIG
DS=[]
for p in sorted(glob.glob(os.path.join(QAL,"skip4","c_*.cir"))):
    if os.path.exists(p+".prn"):
        b=os.path.basename(p)[:-4]; DS.append(("skip4",b,p,5 if b.startswith("c_skip") else 4,None,"free"))
for p in sorted(glob.glob(os.path.join(QAL,"skiptu","*.cir"))):
    b=os.path.basename(p)[:-4]
    if os.path.exists(p+".prn") and b.startswith(("r_","q3_","q4_")):
        DS.append(("skiptu",b,p,4,None,"tu" if ("_rtu_" in b or "_ptu_" in b or "tu" in b.split("_")[2:3]) else "free"))
for tag,sub in (("ctl","ch_ctl/c_ctl.cir"),("res20","ch_res20/c_res20.cir")):
    p=os.path.join(QAL,"resv",sub)
    if os.path.exists(p+".prn"): DS.append(("resv",tag,p,6,[0,1],"free"))
for p in sorted(glob.glob(os.path.join(QAL,"restore5","c_k*.cir"))):
    if os.path.exists(p+".prn"): DS.append(("restore5",os.path.basename(p)[:-4],p,6,[0,1],"free"))
# verify my deck-derived intended matches the committed oh_alt on every deck
bad=[]
for ds,tag,p,nb,gi,mode in DS:
    f=sklib.intended(p,nb)
    for k in range(1,nb+1):
        for i in (gi if gi else range(8)):
            a=f(k,i)
            if a is not None and a != ((i+k)%2==0): bad.append((ds,tag,k,i))
print("intended mismatches vs committed oh_alt:", len(bad), bad[:5])
out={}
for ds,tag,p,nb,gi,mode in DS:
    try: r=skscore.score(p,nb,gi)
    except Exception as e: print("ERR",ds,tag,e); continue
    r["mode"]=mode; r["has_active_topup"]=bool(sklib.topup_windows(p))
    out.setdefault(ds,{})[tag]=r
json.dump(out,open("SKSCORE_REST.json","w"))
print()
print("%-9s %-5s %-7s %-7s %-7s | %s"%("dataset","rows","pass90","guard","FUNC","link census PASS/budget/late/never"))
for ds,rows in out.items():
    p90=g=fn=0; cen={"PASS":0,"FAIL_budget":0,"FAIL_late":0,"FAIL_never":0}
    lp90=lg=0; n=0
    vp_ff=vf_fp=0
    for tag,r in rows.items():
        nb = NB + (184.671+28.6 if r["has_active_topup"] else 0.0)
        okg=True; okf=True
        for L in r["links"]:
            n+=1; lp90+=L["pass90"]; lg+=L["guard"]
            m=L["m_RAILPEAK"]
            c="PASS" if (m is not None and m>=nb) else ("FAIL_budget" if (m is not None and m>=0) else ("FAIL_late" if L["later_ok"] else "FAIL_never"))
            cen[c]+=1
            if not L["guard"]: okg=False
            if c!="PASS": okf=False
        p90+= all(L["pass90"] for L in r["links"]); g+=okg; fn+=okf
        if okg and not okf: vp_ff+=1
        if okf and not okg: vf_fp+=1
    print("%-9s %-5d %-7d %-7d %-7d | %d/%d/%d/%d   links n=%d pass90=%d guard=%d"
          %(ds,len(rows),p90,g,fn,cen["PASS"],cen["FAIL_budget"],cen["FAIL_late"],cen["FAIL_never"],n,lp90,lg))
    print("           SELF-TEST rows: VALUEpass_but_funcFAIL=%d   VALUEfail_but_funcPASS=%d"%(vp_ff,vf_fp))
