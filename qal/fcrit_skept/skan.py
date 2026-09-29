#!/usr/bin/env python3
import json, numpy as np, sys
D = json.load(open("SKSCORE.json"))
SIG = 6.441
B = {                      # mV
 "NB0": 0.0,
 "sigma1": SIG,
 "free_3sig": 3*SIG,
 "free+droop": 3*SIG + 28.6,
 "primary_topup_m6": 3*SIG + 31.1 + 28.6,
 "SKEPT_topup_m6_harmful": 3*SIG + 218.380 + 28.6,
 "primary_topup_worst": 3*SIG + 249.0 + 28.6,
 "SKEPT_topup_worst_harmful": 3*SIG + 184.671 + 28.6,
}
INST = "RAILPEAK"
def cls(L, nb):
    m = L.get("m_"+INST)
    if m is None: return "NODATA"
    if m >= nb: return "PASS"
    if m >= 0:  return "FAIL_budget"
    return "FAIL_late" if L.get("later_ok") else "FAIL_never"

print("=== INSTANT CROSS-CHECK: my rail-peak instant vs the primary's ZCS ===")
dif=[]
for ds,rows in D.items():
    for tag,r in rows.items():
        for k,v in r["rail_peak_ps"].items():
            z = r["zcs_ps"].get(k)
            if v and z: dif.append(abs(v-z))
dif=np.array(dif)
print("  n=%d  median |rail_peak - ZCS| = %.3f ps  mean %.3f  p95 %.3f  max %.3f"
      %(len(dif),np.median(dif),dif.mean(),np.percentile(dif,95),dif.max()))

print()
print("=== ROWS PASSING, per dataset, at each budget (instant = rail peak) ===")
hdr = "%-9s %-4s "%("dataset","n") + " ".join("%22s"%k for k in B)
print(hdr)
for ds,rows in D.items():
    line="%-9s %-4d "%(ds,len(rows))
    for nb_name,nb in B.items():
        c=0
        for tag,r in rows.items():
            if all(cls(L,nb)=="PASS" for L in r["links"]): c+=1
        line+="%22d"%c
    print(line)

print()
print("=== CONFIG-MATCHED (coupling term ONLY where a top-up actually fires) ===")
for ds,rows in D.items():
    for scheme,lbl in (("NODOUBLE","no double-count: 3sig everywhere, coupling already in the .prn"),
                       ("PRIMARY","primary's: topup_worst for mode=topup/vfull, free otherwise"),
                       ("SKEPT","mine: 3sig + MEASURED-HARMFUL coupling only for decks whose top-up FIRES")):
        npass=0; details=[]
        for tag,r in rows.items():
            if scheme=="NODOUBLE": nb=3*SIG
            elif scheme=="PRIMARY":
                nb = B["primary_topup_worst"] if r["mode"]=="topup" else (
                     B["primary_topup_m6"] if r["mode"]=="vfull" else 3*SIG)
                if ds=="banktank": nb = B["primary_topup_m6"] if r["mode"] in ("topup","vfull") else 3*SIG
                if ds=="chain3" and r["mode"]=="hold": nb = 3*SIG+28.6
            else:
                nb = (3*SIG + 184.671 + 28.6) if r["has_active_topup"] else 3*SIG
            ok = all(cls(L,nb)=="PASS" for L in r["links"])
            if ok: npass+=1; details.append(tag)
        print("  %-9s %-9s rows PASS = %2d / %2d"%(ds,scheme,npass,len(rows)))
print()
print("=== FAILURE-MODE CENSUS at the config-matched PRIMARY budget ===")
for ds,rows in D.items():
    tot={"PASS":0,"FAIL_budget":0,"FAIL_late":0,"FAIL_never":0,"NODATA":0}
    p90=0; g=0
    for tag,r in rows.items():
        nb = 3*SIG
        if ds=="banktank" and r["mode"] in ("topup","vfull"): nb=B["primary_topup_m6"]
        if ds=="chain3":
            nb = B["primary_topup_worst"] if r["mode"]=="topup" else (3*SIG+28.6 if r["mode"]=="hold" else 3*SIG)
        for L in r["links"]:
            tot[cls(L,nb)]+=1
            p90+=L["pass90"]; g+=L["guard"]
    n=sum(tot.values())
    print("  %-9s links=%4d  pass90=%4d guard=%4d | PASS=%4d FAIL_budget=%4d FAIL_late=%4d FAIL_never=%4d"
          %(ds,n,p90,g,tot["PASS"],tot["FAIL_budget"],tot["FAIL_late"],tot["FAIL_never"]))
print()
print("=== SELF-TEST vs the committed VALUE guard (row level) ===")
for ds,rows in D.items():
    agree=vf_fp=vp_ff=0
    for tag,r in rows.items():
        nb = 3*SIG
        if ds=="banktank" and r["mode"] in ("topup","vfull"): nb=B["primary_topup_m6"]
        if ds=="chain3":
            nb = B["primary_topup_worst"] if r["mode"]=="topup" else (3*SIG+28.6 if r["mode"]=="hold" else 3*SIG)
        gp = all(L["guard"] for L in r["links"])
        fp = all(cls(L,nb)=="PASS" for L in r["links"])
        if gp==fp: agree+=1
        elif fp and not gp: vf_fp+=1
        else: vp_ff+=1
    print("  %-9s agree=%2d  VALUEfail_but_funcPASS=%2d  VALUEpass_but_funcFAIL=%2d"%(ds,agree,vf_fp,vp_ff))
print()
print("=== WORST-OVER-WINDOW vs AT-INSTANT (was the ramp checked?) ===")
for ds,rows in D.items():
    nb=3*SIG
    ai=ww=0; worst=(1e9,None)
    for tag,r in rows.items():
        aok = all(cls(L,nb)=="PASS" for L in r["links"])
        wok = all((L.get("m_WORSTWIN") is not None and L["m_WORSTWIN"]>=nb) for L in r["links"])
        ai+=aok; ww+=wok
        for L in r["links"]:
            if L.get("m_WORSTWIN") is not None and L["m_WORSTWIN"]<worst[0]:
                worst=(L["m_WORSTWIN"],"%s b%d g%d"%(tag,L["k"],L["i"]))
    print("  %-9s rows PASS at-instant=%2d   rows PASS worst-over-window=%2d   worst window margin %.1f mV (%s)"
          %(ds,ai,ww,worst[0],worst[1]))
print()
print("=== INSTANT SENSITIVITY (rows passing at 3sig, each instant) ===")
for ds,rows in D.items():
    out=[]
    for inst in ("RAILPEAK","ZCS","CK","STRICT_last"):
        c=0
        for tag,r in rows.items():
            ok=True
            for L in r["links"]:
                m=L.get("m_"+inst)
                if m is None or m < 3*SIG: ok=False; break
            c+=ok
        out.append("%s=%d"%(inst,c))
    print("  %-9s %s"%(ds," ".join(out)))
