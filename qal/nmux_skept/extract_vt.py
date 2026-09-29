import json, math, os
D="/usr/local/src/stat-sim/qal/nmux_skept"
W,L=0.74,0.13
names=json.load(open(f"{D}/vtnames.json"))
def readprn(p):
    rows=[];hdr=None
    for line in open(p):
        s=line.split()
        if not s: continue
        if s[0]=="Index":
            hdr=[c.upper() for c in s]; continue
        if s[0].startswith("End"): continue
        if hdr is None: continue
        try: vals=[float(x) for x in s]
        except ValueError: continue
        rows.append(dict(zip(hdr,vals)))
    return hdr,rows
def vt_at(rows, crit):
    # axis = Vgs = V(G)-V(S)  (A4 fix). current magnitude.
    pts=[(r["V(G)"]-r["V(S)"], abs(r["I(VD)"])) for r in rows]
    pts.sort()
    for i in range(1,len(pts)):
        if pts[i][1]>=crit>pts[i-1][1]:
            (x0,y0),(x1,y1)=pts[i-1],pts[i]
            if y0<=0: return x1
            f=(math.log(crit)-math.log(y0))/(math.log(y1)-math.log(y0))
            return x0+f*(x1-x0)
    return None
out={}
crits={"100n":100e-9*W/L, "10n":10e-9*W/L, "1n":1e-9*W/L}
canary_fail=[]
for n in names:
    sb=int(n.split("_")[-1])/1000.0
    hdr,rows=readprn(f"{D}/{n}.cir.prn")
    imax=max(abs(r["I(VD)"]) for r in rows)
    # NULL-MODEL CANARY: peak current must be >> integrator floor
    if imax < 1e-6: canary_fail.append((n,imax))
    vsb_meas = rows[0]["V(S)"]      # verify the actual source lift
    e={"V_sb_nominal":sb,"V_sb_measured":vsb_meas,"Imax_A":imax,"nrows":len(rows)}
    for k,c in crits.items(): e["Vt_"+k]=vt_at(rows,c)
    out[n]=e
json.dump(out,open(f"{D}/sk_vt_rows.json","w"),indent=1)
print("CANARY FAILURES:",canary_fail if canary_fail else "NONE - all decks show real current")
print()
print("%-8s %-12s %-12s %-12s %-12s"%("V_sb","V_sb_meas","Vt@100nW/L","Vt@10n","Vt@1n"))
for n in names:
    e=out[n]
    print("%-8.3f %-12.4f %-12.7f %-12.7f %-12.7f"%(e["V_sb_nominal"],e["V_sb_measured"],e["Vt_100n"],e["Vt_10n"],e["Vt_1n"]))
