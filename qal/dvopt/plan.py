#!/usr/bin/env python3
"""Refine the PRE-REGISTERED balance predictions with the MEASURED extended floor
curve, and emit the grid.  The pre-registered numbers stay on disk untouched;
this prints both so a miss is visible."""
import json, math

FL = json.load(open("floor.json"))
PRE = json.load(open("predictions.json"))

# MEASURED floor: t90 vs delivered supply (2 ps step), this track
pts = sorted((r["vdd"], r["t90_ps_measure"]) for t, r in FL["inv"].items()
             if r["kind"] == "inv" and r["edge_ps"] == 2.0)
print("MEASURED floor curve (inverter 1.12/0.74, 2 fF, 2 ps supply step), %d points" % len(pts))
for v, t in pts:
    print("   %.5f V -> %8.3f ps" % (v, t))

def floor90(v):
    xs = [p[0] for p in pts]; ys = [math.log(p[1]) for p in pts]
    if v <= xs[0]: i = 0
    elif v >= xs[-1]: i = len(xs) - 2
    else: i = max(k for k in range(len(xs)-1) if xs[k] <= v)
    f = (v - xs[i])/(xs[i+1]-xs[i])
    return math.exp(ys[i] + f*(ys[i+1]-ys[i]))

A = {float(k): v for k, v in PRE["a_W"].items()}
F = {float(k): tuple(v) for k, v in PRE["f_W"].items()}
def frac(w, L): p, q = F[w]; return p + q*math.log(L)
def thop(w, L): return A[w]*math.sqrt(L)

DVS = [1.08, 1.20, 1.32, 1.35, 1.50, 1.65]
print("\nREFINED balance points (MEASURED floor) vs PRE-REGISTERED (committed floor)")
print("%5s %4s | %8s %8s | %8s %8s %8s | %8s"
      % ("dV","W","L_pre","L_ref","VBEND","t_hop","t_set","MAX/92.8"))
grid = {}
for w in (15.0, 30.0, 60.0):
    for dv in DVS:
        lo, hi = 1.0, 400.0
        for _ in range(200):
            m = math.sqrt(lo*hi)
            if thop(w, m) - floor90(dv*frac(w, m)) < 0: lo = m
            else: hi = m
        Lb = math.sqrt(lo*hi); vb = dv*frac(w, Lb)
        pre = PRE["predictions"]["W%g_dv%g" % (w, dv)]["L_balance_nH"]
        mx = max(thop(w,Lb), floor90(vb))
        grid["W%g_dv%g" % (w,dv)] = dict(L_bal=Lb, VBEND=vb, t_hop=thop(w,Lb),
                                         t_set=floor90(vb), MAX=mx, L_pre=pre)
        print("%5.2f %4g | %8.2f %8.2f | %8.4f %8.2f %8.2f | %8.3f"
              % (dv, w, pre, Lb, vb, thop(w,Lb), floor90(vb), mx/92.8))
json.dump(dict(floor_measured=pts, refined=grid), open("plan.json","w"), indent=1)
