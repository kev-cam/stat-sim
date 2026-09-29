import sys, os, json, numpy as np
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import sklib
w=sklib.W("sk_level.cir.prn")
T0=100.0
TRIP=0.6451618          # MY measured trip, std cell, 1.2 V rail
SIG=6.441; NB=3*SIG/1000.0
BAR_R=TRIP+NB; BAR_F=TRIP-NB
def tcross(col, level, rising):
    t=w.t; y=w.s(col)
    m=t>=T0
    t=t[m]; y=y[m]
    if rising: s=np.where((y[:-1]<level)&(y[1:]>=level))[0]
    else:      s=np.where((y[:-1]>level)&(y[1:]<=level))[0]
    if len(s)==0: return None
    j=s[0]
    return float(t[j]+(t[j+1]-t[j])*(level-y[j])/(y[j+1]-y[j])) - T0
R={}
# ---- A CMOS switch 2 fF
R["A_CMOS_switch_2fF"]=dict(
  rise_t90=tcross("V(OAR)",1.08,True), rise_tcommit=tcross("V(OAR)",BAR_R,True),
  rise_tNB0=tcross("V(OAR)",TRIP,True),
  fall_t90=tcross("V(OAF)",0.12,False), fall_tcommit=tcross("V(OAF)",BAR_F,False),
  fall_tNB0=tcross("V(OAF)",TRIP,False))
# ---- B QAL settle 2 fF
R["B_QAL_settle_2fF"]=dict(
  up_t90=tcross("V(OBU)",1.08,True), up_tcommit=tcross("V(OBU)",BAR_R,True),
  up_tNB0=tcross("V(OBU)",TRIP,True),
  down_peak_mV=float(np.max(w.s("V(OBD)")[w.t>=T0])*1e3))
# ---- C CMOS comparator 6.91 fF
R["C_CMOS_comparator_6p91fF"]=dict(
  rise_t90=tcross("V(OCR)",1.08,True), rise_tcommit=tcross("V(OCR)",BAR_R,True),
  rise_tNB0=tcross("V(OCR)",TRIP,True),
  fall_t90=tcross("V(OCF)",0.12,False), fall_tcommit=tcross("V(OCF)",BAR_F,False),
  fall_tNB0=tcross("V(OCF)",TRIP,False))
# ---- D CMOS depth-8 chain  *** the arm the primary did not build ***
ch={}
for n in range(1,9):
    col="V(D%d)"%n
    rising = (n%2==0)          # di rises -> d1 falls, d2 rises, ...
    if rising:
        ch[n]=dict(t90=tcross(col,1.08,True), tc=tcross(col,BAR_R,True), t0=tcross(col,TRIP,True))
    else:
        ch[n]=dict(t90=tcross(col,0.12,False), tc=tcross(col,BAR_F,False), t0=tcross(col,TRIP,False))
R["D_CMOS_chain_depth8"]=ch
json.dump(R,open("LEVEL_SKEPT.json","w"),indent=1)

def g(a,b): return (a/b) if (a and b) else None
print("MY trip 1.2 V = %.7f ; NB = %.3f mV ; rise bar %.6f ; fall bar %.6f"%(TRIP,NB*1e3,BAR_R,BAR_F))
print()
a=R["A_CMOS_switch_2fF"]; b=R["B_QAL_settle_2fF"]; c=R["C_CMOS_comparator_6p91fF"]
print("A CMOS switch 2 fF : rise t90=%.4f  tcommit=%.4f  GAIN %.4f   (NB0 %.4f -> %.4f)"
      %(a["rise_t90"],a["rise_tcommit"],a["rise_t90"]/a["rise_tcommit"],a["rise_tNB0"],a["rise_t90"]/a["rise_tNB0"]))
print("                     fall t90=%.4f  tcommit=%.4f  GAIN %.4f"
      %(a["fall_t90"],a["fall_tcommit"],a["fall_t90"]/a["fall_tcommit"]))
print("   worst-of-rise/fall: %.4f -> %.4f  GAIN %.4f"
      %(max(a["rise_t90"],a["fall_t90"]),max(a["rise_tcommit"],a["fall_tcommit"]),
        max(a["rise_t90"],a["fall_t90"])/max(a["rise_tcommit"],a["fall_tcommit"])))
print()
print("B QAL settle 2 fF  : t90=%.4f  tcommit=%.4f  GAIN %.4f   (NB0 %.4f -> %.4f)"
      %(b["up_t90"],b["up_tcommit"],b["up_t90"]/b["up_tcommit"],b["up_tNB0"],b["up_t90"]/b["up_tNB0"]))
print("   pull-DOWN cell peak = %.3f mV"%b["down_peak_mV"])
print()
print("C CMOS comparator  : rise t90=%.4f tcommit=%.4f | fall t90=%.4f tcommit=%.4f"
      %(c["rise_t90"],c["rise_tcommit"],c["fall_t90"],c["fall_tcommit"]))
print("   worst-of: %.4f -> %.4f  GAIN %.4f"
      %(max(c["rise_t90"],c["fall_t90"]),max(c["rise_tcommit"],c["fall_tcommit"]),
        max(c["rise_t90"],c["fall_t90"])/max(c["rise_tcommit"],c["fall_tcommit"])))
print()
print("RATIO QAL/CMOS at the LEVEL (same cell, same load, same run):")
print("   90%% bar   : %.4f / %.4f = %.4f"%(b["up_t90"],a["rise_t90"],b["up_t90"]/a["rise_t90"]))
print("   commit bar: %.4f / %.4f = %.4f"%(b["up_tcommit"],a["rise_tcommit"],b["up_tcommit"]/a["rise_tcommit"]))
print()
print("D *** CMOS depth-8 CHAIN -- the pipeline analogue ***")
print(" n   t90(ps)   tcommit(ps)  per-stage90  per-stageC")
p90=pc=0.0
for n in range(1,9):
    d=ch[n]
    s90 = d["t90"]-p90 if d["t90"] else None
    sc  = d["tc"]-pc  if d["tc"]  else None
    print(" %d  %8.4f   %9.4f    %8.4f    %8.4f"%(n,d["t90"],d["tc"],s90,sc))
    p90,pc=d["t90"],d["tc"]
print("  end-to-end depth-8: t90=%.4f  tcommit=%.4f  GAIN %.4f"
      %(ch[8]["t90"],ch[8]["tc"],ch[8]["t90"]/ch[8]["tc"]))
ss90=(ch[8]["t90"]-ch[2]["t90"])/6.0; ssc=(ch[8]["tc"]-ch[2]["tc"])/6.0
print("  STEADY-STATE per-stage (stages 3..8): 90%%bar %.4f ps  commitbar %.4f ps  GAIN %.4f"
      %(ss90,ssc,ss90/ssc))
