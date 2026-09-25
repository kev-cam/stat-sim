#!/usr/bin/env python3
"""Analysis of qal_bankN_sqrtN.json: does single-rail rail-wander fall as 1/sqrt(N)?

Two independent readings of the same measured data:
  (A) DIRECT   -- sample spread of the rail over the 12 random input words actually simulated
                  at each (N, dV). This is exactly what the brief asked for. Its weakness is
                  that 12 draws estimate a sigma only to +-1/sqrt(2*11) = 21%.
  (B) COMPOSED -- the EXACT population spread over all 2^N equiprobable words, obtained by
                  weighting the MEASURED V(k) curve with Binomial(N, 1/2). This is legitimate
                  only because the rail was measured to depend on k alone (three placements of
                  k=4 at N=8 agreed to 5 decimals; two unrelated words with k=62 at N=128 both
                  gave 0.5845), which is reported here as a check rather than assumed.
Labels: MEASURED = straight from Xyce. COMPOSED-FROM-MEASURED = (B) and the sigma ratios.
"""
import json, math
from collections import defaultdict

DB   = json.load(open("/usr/local/src/stat-sim/qal/qal_bankN_sqrtN.json"))
VT   = 0.40          # project's own vt_est, NOT separately extracted (ASSUMED)
CLIFF= 0.50          # "bank rail must stay comfortably above ~0.5 V" from the brief

runs = DB["runs"]
by   = defaultdict(list)
for r in runs:
    by[(r["N"], r["dV"])].append(r)

def curve(rs):
    """measured rail(k) and gate-output(k), one entry per distinct k"""
    c, o, q = {}, {}, {}
    for r in rs:
        c.setdefault(r["k"], r["rail_900ps"])
        q.setdefault(r["k"], r["QTR_fC"])
        if r["O_sw_900ps"] is not None: o.setdefault(r["k"], r["O_sw_900ps"])
    return c, o, q

def interp(c, k):
    ks = sorted(c)
    if k in c: return c[k]
    lo = max([x for x in ks if x < k], default=ks[0])
    hi = min([x for x in ks if x > k], default=ks[-1])
    if hi == lo: return c[lo]
    return c[lo] + (c[hi]-c[lo])*(k-lo)/float(hi-lo)

def binom_pmf(N):
    lg = math.lgamma
    return [math.exp(lg(N+1)-lg(k+1)-lg(N-k+1) - N*math.log(2.0)) for k in range(N+1)]

print("="*100)
print("PLACEMENT CHECK -- is the rail a function of k alone?  (MEASURED)")
print("="*100)
for key in sorted(by):
    N, dv = key
    g = defaultdict(list)
    for r in by[key]: g[r["k"]].append((r["pattern_name"], r["rail_900ps"], r["QTR_fC"]))
    dup = {k: v for k, v in g.items() if len(v) > 1}
    for k in sorted(dup):
        vs = [x[1] for x in dup[k]]
        print("  N=%-4d dV=%.1f  k=%-4d  %d distinct words -> rail %s   spread %.2f uV"
              % (N, dv, k, len(vs), "/".join("%.5f" % v for v in vs),
                 1e6*(max(vs)-min(vs))))

print()
print("="*100)
print("(1) MEASURED: rail@900ps over the 12 RANDOM words actually simulated, and the two extremes")
print("="*100)
print("   N   dV |  random words: k range   rail min    max    mean   p-p(mV)  sd(mV) |"
      "  EXTREMES k=0 / k=N (V)   full-scale(mV)")
direct = {}
for key in sorted(by):
    N, dv = key
    rr = [r for r in by[key] if r["pattern_name"].startswith("r")
          and r["pattern_name"][1:].isdigit()]
    v  = [r["rail_900ps"] for r in rr]
    ks = [r["k"] for r in rr]
    m  = sum(v)/len(v)
    sd = math.sqrt(sum((x-m)**2 for x in v)/(len(v)-1))
    e0 = [r for r in by[key] if r["pattern_name"] == "allhi_k0"][0]["rail_900ps"]
    eN = [r for r in by[key] if r["pattern_name"] == "alllo_kN"][0]["rail_900ps"]
    direct[key] = dict(n=len(v), sd=sd, mean=m, pp=max(v)-min(v), e0=e0, eN=eN,
                       vmin=min(v), vmax=max(v))
    print("  %3d  %.1f |  n=%d  k=%d..%d      %.4f %.4f %.4f  %6.1f  %6.2f |"
          "   %.4f / %.4f    %6.1f"
          % (N, dv, len(v), min(ks), max(ks), min(v), max(v), m,
             1000*(max(v)-min(v)), 1000*sd, e0, eN, 1000*abs(eN-e0)))

print()
print("="*100)
print("(2) COMPOSED-FROM-MEASURED: exact spread over ALL 2^N words, measured V(k) x Binomial(N,1/2)")
print("="*100)
print("   N   dV | k range measured |  mean rail   sigma(mV)  sigma/mean | "
      "3-sigma low  |  worst case (a=1)")
comp = {}
for key in sorted(by):
    N, dv = key
    c, o, q = curve(by[key])
    pmf = binom_pmf(N)
    ks = sorted(c)
    tail = sum(pmf[k] for k in range(N+1) if k < min(ks) or k > max(ks))
    mu = sum(pmf[k]*interp(c, k) for k in range(N+1))
    var= sum(pmf[k]*(interp(c, k)-mu)**2 for k in range(N+1))
    sd = math.sqrt(var)
    comp[key] = dict(mu=mu, sd=sd, tail=tail)
    print("  %3d  %.1f |  %3d..%-3d          |  %.5f    %6.3f    %6.3f%%  |   %.4f    |   %.4f"
          % (N, dv, min(ks), max(ks), mu, 1000*sd, 100*sd/mu, mu-3*sd,
             [r for r in by[key] if r["pattern_name"] == "alllo_kN"][0]["rail_900ps"]))
    if tail > 1e-9:
        print("        (binomial mass outside the measured k range: %.2e -- interpolated)" % tail)

print()
print("="*100)
print("(3) THE 1/sqrt(N) TEST")
print("="*100)
for dv in (0.8, 1.0):
    print("  dV=%.1f" % dv)
    print("     N  | sigma direct(mV) n=12 | sigma composed(mV) | ratio to N=8: direct  composed"
          " | 1/sqrt(N) predicts")
    base_d = direct[(8, dv)]["sd"]; base_c = comp[(8, dv)]["sd"]
    for N in (8, 32, 128):
        pred = math.sqrt(8.0/N)
        print("    %4d |        %6.2f         |       %6.3f       |        %5.3f    %5.3f     "
              "|      %5.3f"
              % (N, 1000*direct[(N, dv)]["sd"], 1000*comp[(N, dv)]["sd"],
                 direct[(N, dv)]["sd"]/base_d, comp[(N, dv)]["sd"]/base_c, pred))
    print()

print("="*100)
print("(4) SCALE INVARIANCE of the rail vs ACTIVITY FRACTION a=k/N  (MEASURED)")
print("="*100)
print("   dV |   a    | rail N=8    N=32    N=128  | max spread across N (mV)")
for dv in (0.8, 1.0):
    for a in (0.0, 0.25, 0.375, 0.5, 0.625, 0.75, 1.0):
        vals = []
        for N in (8, 32, 128):
            c, o, q = curve(by[(N, dv)])
            k = int(round(a*N))
            vals.append(interp(c, k))
        print("  %.1f | %.3f  |  %.4f  %.4f  %.4f  |   %.2f"
              % (dv, a, vals[0], vals[1], vals[2], 1000*(max(vals)-min(vals))))
    print()

print("="*100)
print("(5) THE FUNCTIONAL CLIFF: the LOGIC-1 LEVEL the bank hands to the next stage  (MEASURED)")
print("      O_sw@900ps = a switching gate's output; margin to Vt_est=%.2f V" % VT)
print("="*100)
print("   N   dV |  a=0.125   a=0.5    a=1.0   | margin at a=0.5 (mV) | settle%% at a=0.5 |"
      " rail vs %.2f V cliff" % CLIFF)
for key in sorted(by):
    N, dv = key
    c, o, q = curve(by[key])
    def og(a):
        k = max(1, int(round(a*N)))
        return interp(o, k)
    st = [r for r in by[key] if r["k"] == N//2]
    stp = st[0]["settle_pct"] if st else None
    railh = interp(c, N//2)
    print("  %3d  %.1f |  %.4f   %.4f   %.4f  |       %+6.1f        |      %s      |  %.4f %s"
          % (N, dv, og(0.125), og(0.5), og(1.0), 1000*(og(0.5)-VT),
             ("%5.1f" % stp) if stp else "  n/a", railh,
             "OK" if railh > CLIFF else "BELOW"))

print()
print("="*100)
print("(6) CHARGE MODULATION QTR, full scale (k=0 -> k=N)  (MEASURED) -- cf. the N=1 claim of 100%")
print("="*100)
print("   N   dV |  QTR k=0     k=N    | full-scale modulation | per-gate QTR k=0 -> k=N")
for key in sorted(by):
    N, dv = key
    c, o, q = curve(by[key])
    q0, qN = q[0], q[N]
    print("  %3d  %.1f | %9.3f %9.3f |        %5.2f%%         |  %.4f -> %.4f fC"
          % (N, dv, q0, qN, 100*abs(qN-q0)/(0.5*(q0+qN)), q0/N, qN/N))

print()
print("="*100)
print("(7) SIGMA-COUNT TO THE Vt FLOOR (COMPOSED-FROM-MEASURED), and the BOUNDED worst case")
print("="*100)
for dv in (0.8, 1.0):
    for N in (8, 32, 128):
        c, o, q = curve(by[(N, dv)])
        pmf = binom_pmf(N)
        mu_o = sum(pmf[k]*interp(o, max(k, min(o))) for k in range(N+1))
        var_o= sum(pmf[k]*(interp(o, max(k, min(o)))-mu_o)**2 for k in range(N+1))
        sd_o = math.sqrt(var_o)
        worst= interp(o, N)
        print("  dV=%.1f N=%-4d  logic-1 level: mean %.4f  sigma %.3f mV  -> margin to Vt "
              "%+6.1f mV = %s sigma | BOUNDED worst case (a=1) %.4f = %+6.1f mV"
              % (dv, N, mu_o, 1000*sd_o, 1000*(mu_o-VT),
                 ("%6.1f" % ((mu_o-VT)/sd_o)) if sd_o > 0 else "  inf",
                 worst, 1000*(worst-VT)))
    print()

out = {"_doc": "Analysis of qal_bankN_sqrtN.json. DIRECT = sample spread over the 12 random "
               "words simulated at each (N,dV). COMPOSED = exact Binomial(N,1/2) weighting of "
               "the MEASURED V(k) curve, valid because the rail was measured to depend on k "
               "alone. Vt_est=0.40 V is the project's own estimate, not separately extracted.",
       "vt_est": VT, "cliff_V": CLIFF,
       "direct": {"N%d_dV%.1f" % k: {kk: (round(vv, 6) if isinstance(vv, float) else vv)
                                     for kk, vv in v.items()} for k, v in direct.items()},
       "composed": {"N%d_dV%.1f" % k: {kk: round(vv, 8) for kk, vv in v.items()}
                    for k, v in comp.items()},
       "sigma_ratio_to_N8": {
           "dV%.1f" % dv: {"N%d" % N: {
               "direct": round(direct[(N, dv)]["sd"]/direct[(8, dv)]["sd"], 4),
               "composed": round(comp[(N, dv)]["sd"]/comp[(8, dv)]["sd"], 4),
               "pred_1_over_sqrtN": round(math.sqrt(8.0/N), 4)} for N in (8, 32, 128)}
           for dv in (0.8, 1.0)}}
json.dump(out, open("/usr/local/src/stat-sim/qal/qal_bankN_sqrtN_analysis.json", "w"), indent=1)
print("wrote /usr/local/src/stat-sim/qal/qal_bankN_sqrtN_analysis.json")
