#!/usr/bin/env python3
"""PRE-REGISTRATION predictions.  Built ONLY from ALREADY-COMMITTED measurements
(lsweep/RESULTS_LSWEEP.json + lsweep/cellcmp*.json).  No new deck has been run."""
import json, math

LS = json.load(open("/usr/local/src/stat-sim/qal/lsweep/RESULTS_LSWEEP.json"))
R  = LS["rows_equal_bank_MEASURED"]

# ---- committed cell floor: t90 of the 1.12/0.74 inverter, 2 fF, supply stepped
FLOOR = sorted([(0.4885216, 801.2661), (0.5422147, 397.8699), (0.5883760, 252.7525),
                (0.6196049, 197.0207), (0.6496840, 160.4934), (0.6754250, 137.7454),
                (0.8000000,  81.0429), (1.0000000,  51.5050), (1.2000000,  40.4175)])

def floor_t90(v):
    """log-t interpolation on the committed floor curve (convex, so log-linear
    interpolation is far better than linear).  Extrapolates on the end slope."""
    xs = [p[0] for p in FLOOR]; ys = [math.log(p[1]) for p in FLOOR]
    if v <= xs[0]:  i = 0
    elif v >= xs[-1]: i = len(xs) - 2
    else:
        i = max(k for k in range(len(xs) - 1) if xs[k] <= v)
    f = (v - xs[i]) / (xs[i+1] - xs[i])
    return math.exp(ys[i] + f * (ys[i+1] - ys[i]))

# ---- committed t_hop(L) per switch width:  t_hop = a_W * sqrt(L_nH)
def fit_a(rows):
    return sum(r["t_hop_ps"] / math.sqrt(r["L_nH"]) for r in rows) / len(rows)
byW = {}
for tag, r in R.items():
    if r.get("ca_fF", 35.979) != 35.979 or r["rs_ohm"] != 10.0 or r["edge_ps"] != 2.0:
        continue
    byW.setdefault(r["total_um"], []).append(r)
A = {w: fit_a(v) for w, v in byW.items()}
# ---- committed delivered-swing fraction  VBEND = dV * f_W(L),  f = p + q*ln L
def fit_f(rows):
    n = len(rows)
    x = [math.log(r["L_nH"]) for r in rows]; y = [r["VBEND"] / r["dv"] for r in rows]
    mx, my = sum(x)/n, sum(y)/n
    sxx = sum((a-mx)**2 for a in x) or 1e-30
    q = sum((a-mx)*(b-my) for a, b in zip(x, y)) / sxx
    return (my - q*mx, q)
F = {w: fit_f(v) for w, v in byW.items()}

def frac(w, L):
    p, q = F[w]; return p + q*math.log(L)

def t_hop(w, L):
    return A[w]*math.sqrt(L)

print("committed fits (MEASURED rows, equal bank, RS=10, edge=2ps, CA=35.979fF)")
for w in sorted(A):
    print("  W=%-4g n=%-2d  t_hop = %.4f*sqrt(L_nH) ps   VBEND/dV = %.5f %+.5f*ln(L)"
          % (w, len(byW[w]), A[w], F[w][0], F[w][1]))

DVS = [1.08, 1.20, 1.32, 1.35, 1.50, 1.65]
out = {}
for w in (15.0, 30.0, 60.0):
    for dv in DVS:
        lo, hi = 1.0, 400.0
        for _ in range(200):                       # bisect on t_hop - t_settle
            m = math.sqrt(lo*hi)
            if t_hop(w, m) - floor_t90(dv*frac(w, m)) < 0: lo = m
            else: hi = m
        Lb = math.sqrt(lo*hi)
        vb = dv*frac(w, Lb)
        out["W%g_dv%g" % (w, dv)] = dict(
            W_um=w, dv=dv, L_balance_nH=Lb, VBEND_pred=vb,
            t_hop_pred_ps=t_hop(w, Lb), t_settle_pred_ps=floor_t90(vb),
            MAX_pred_ps=max(t_hop(w, Lb), floor_t90(vb)),
            ratio_to_CMOS=max(t_hop(w, Lb), floor_t90(vb))/92.8)
        # SUM optimum by scan
        best = None
        L = 1.0
        while L <= 400.0:
            s = t_hop(w, L) + floor_t90(dv*frac(w, L))
            if best is None or s < best[1]: best = (L, s)
            L *= 1.01
        out["W%g_dv%g" % (w, dv)].update(
            L_sumopt_nH=best[0], SUM_pred_ps=best[1],
            SUM_t_hop_ps=t_hop(w, best[0]),
            SUM_t_settle_ps=floor_t90(dv*frac(w, best[0])),
            SUM_VBEND_pred=dv*frac(w, best[0]),
            SUM_ratio_to_CMOS=best[1]/92.8)
print()
print("%-12s %5s %5s | %8s %8s %8s %8s %7s | %8s %8s %8s %7s"
      % ("key","W","dV","L_bal","VBEND","t_hop","t_set","MAX/92.8","L_sum","SUM","VBEND","SUM/92.8"))
for k, v in out.items():
    print("%-12s %5g %5.2f | %8.2f %8.4f %8.2f %8.2f %7.3f | %8.2f %8.2f %8.4f %7.3f"
          % (k, v["W_um"], v["dv"], v["L_balance_nH"], v["VBEND_pred"],
             v["t_hop_pred_ps"], v["t_settle_pred_ps"], v["ratio_to_CMOS"],
             v["L_sumopt_nH"], v["SUM_pred_ps"], v["SUM_VBEND_pred"], v["SUM_ratio_to_CMOS"]))
json.dump(dict(floor_committed=FLOOR, a_W=A, f_W={str(k): v for k, v in F.items()},
               predictions=out), open("predictions.json", "w"), indent=1)
