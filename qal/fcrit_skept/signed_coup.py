import sys, os, json, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sklib
QAL="/usr/local/src/stat-sim/qal"
# tankfed profile: 5 stages [48,19,3,1,2]; intended value from bank1 inputs
def signed(ct, pt, pf, tail=24.0):
    wt=sklib.W(pt); wf=sklib.W(pf)
    oh = sklib.intended(ct, 5)
    res=[]
    for (k,ta,tb) in sklib.topup_windows(ct):
        kf=k-1; tb2=(tb if tb else wt.t[-1])+tail
        g=np.arange(ta,tb2,0.05); rows=[]
        for i in range(0,60):
            col="V(O%d_%d)"%(kf,i)
            if not (wt.has(col) and wf.has(col)): continue
            a=np.interp(g,wt.t,wt.s(col)); b=np.interp(g,wf.t,wf.s(col))
            d=(a-b)*1e3
            jmax=int(np.argmax(np.abs(d)))
            want=oh(kf,i)
            # HARMFUL: LOW node pushed UP, or HIGH node pushed DOWN
            harm = (-d if want else d)          # positive = harmful
            jh=int(np.argmax(harm))
            rows.append(dict(gate="o%d_%d"%(kf,i), want_hi=want,
                             signed_at_max_abs_mV=round(float(d[jmax]),3),
                             worst_HARMFUL_mV=round(float(harm[jh]),3),
                             at_ps=round(float(g[jh]),2)))
        res.append(dict(topped_bank=k, feeder=kf, gates=rows))
    return res
out={}
for tag,deck in (("matched_m2","r_bank_matched_m2"),("uniform_m6","r_bank_uniform_m6")):
    ct=os.path.join(QAL,"tankfed",deck+"_clamp_T340_dv1200.cir")
    pf=os.path.join(QAL,"tankfed",deck+"_free_T340_dv1200.cir.prn")
    out[tag]=signed(ct,ct+".prn",pf)
    print("=====",tag)
    for w in out[tag]:
        print("  topped bank",w["topped_bank"],"feeder",w["feeder"])
        for r in sorted(w["gates"], key=lambda r:-r["worst_HARMFUL_mV"]):
            print("    %-7s want_hi=%-5s signed@maxabs=%9.3f  worstHARMFUL=%9.3f mV @%.1f ps"
                  %(r["gate"],r["want_hi"],r["signed_at_max_abs_mV"],r["worst_HARMFUL_mV"],r["at_ps"]))
json.dump(out,open("SIGNED_COUPLING.json","w"),indent=1)
