import sys, os, json, numpy as np
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import sklib
RAILS=[0.20,0.25,0.30,0.35,0.40,0.45,0.50,0.55,0.60,0.65,0.70,0.75,0.80,0.85,0.90,
       0.95,1.00,1.05,1.10,1.15,1.20,1.25,1.30,1.35,1.40,1.45,1.50]
names,_,d = sklib.read_prn("sk_trip.cir.prn")
iv = names.index("V(IN)")
vin = d[:,iv]
out={}
for tag,pref in (("S","S"),("A","A")):
    rows={"vdd":[], "trip_V":[], "frac":[], "window_10_90_mV":[]}
    for i,r in enumerate(RAILS):
        col="V(%s%d)"%(pref,i)
        y=d[:,names.index(col.upper())]
        def cross(level):
            # Vout is monotone DECREASING in Vin -> find Vin where Vout=level
            s=np.where((y[:-1]>=level)&(y[1:]<level))[0]
            if len(s)==0: return None
            j=s[0]
            if y[j]==y[j+1]: return float(vin[j])
            return float(vin[j]+(vin[j+1]-vin[j])*(y[j]-level)/(y[j]-y[j+1]))
        tr=cross(r/2.0); v9=cross(0.9*r); v1=cross(0.1*r)
        rows["vdd"].append(r)
        rows["trip_V"].append(tr)
        rows["frac"].append(round(tr/r,6) if tr else None)
        rows["window_10_90_mV"].append(round((v1-v9)*1e3,3) if (v1 and v9) else None)
    out[tag]=rows
json.dump(out,open("TRIP_SKEPT.json","w"),indent=1)
print("rail   S_trip    S_frac  S_win   A_trip    A_frac")
for i,r in enumerate(RAILS):
    s=out["S"]; a=out["A"]
    print("%.2f  %s  %s  %s   %s  %s"%(r,
      ("%.6f"%s["trip_V"][i]) if s["trip_V"][i] else "  None  ",
      ("%.4f"%s["frac"][i]) if s["frac"][i] else " None ",
      ("%7.3f"%s["window_10_90_mV"][i]) if s["window_10_90_mV"][i] else "  None ",
      ("%.6f"%a["trip_V"][i]) if a["trip_V"][i] else "  None  ",
      ("%.4f"%a["frac"][i]) if a["frac"][i] else " None "))
print()
print("INSTRUMENT CHECK vs committed qal/bound/dc_rows.json")
comm={1.20:0.6451630261834231,1.00:0.546696061776791,0.90:0.4958921397750707,0.80:0.4452317}
for v,c in comm.items():
    i=RAILS.index(v); m=out["S"]["trip_V"][i]
    print("  S @%.2f V  mine %.7f  committed %.7f  rel %.2e"%(v,m,c,abs(m-c)/c))
i=RAILS.index(1.20); print("  A @1.20 V mine %.7f  committed 0.4594805  rel %.2e"
      %(out["A"]["trip_V"][i],abs(out["A"]["trip_V"][i]-0.4594805)/0.4594805))
