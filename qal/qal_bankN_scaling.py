#!/usr/bin/env python3
"""Does the per-gate rail sensitivity really scale as 1/N? -- the load-bearing assumption.

The whole 1/sqrt(N) argument multiplies two factors: the per-gate rail sensitivity (assumed to
fall as 1/N for a proportionally scaled bank) and sigma_k = sqrt(N p(1-p)) (binomial). Only the
second is arithmetic. The first is a SCALING ASSUMPTION and it is the one that can be wrong, so
it is measured here rather than asserted.

TEST. Double the bank: N=16 gates instead of 8, with C_A doubled (70.005 fF) and L halved
(200 nH) so the LC half-cycle -- and therefore the ramp the gates see -- is unchanged
(t ~ pi*sqrt(L*Cser); Cser doubles, L halves, product constant). Everything else identical to
qal_bankN_modulation.py.

PREDICTIONS if the 1/N scaling holds:
  * nominal rail at k=N/2 is UNCHANGED (0.5174 V at dV=0.8)
  * per-gate slope HALVES: 28.6 -> ~14.3 mV/gate
  * the full-scale endpoints k=0 and k=N are UNCHANGED (0.6795 / 0.4468 V), i.e. the worst case
    is scale-invariant while the typical wander shrinks. This second prediction is the one that
    decides the verdict, because a bounded worst case that is already functional makes the
    statistical argument a bonus rather than a load-bearing step.
"""
import os, re, subprocess, json

XYCE  = "/usr/local/src/xyce-build/src/Xyce"
VA    = "/usr/local/share/xyce/verilog-a/psp103/psp103.va"
MODEL = "/usr/local/src/kestrel/sim/models/sg13g2_psp103_tt.lib"
SHIM  = "/usr/local/src/stat-sim/qal/sg13lv_compat.sp"
ENV   = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS")

WP, WN, CLOAD, WSW, VGH, RS = 1.12, 0.74, 2.0, 20.0, 1.5, 10.0
DV, TZ = 0.8, 367.51
N, CA, L_NH = 16, 70.005, 200.0            # doubled bank, doubled C_A, halved L
KS = [0, 6, 8, 10, 16]

def run(k):
    fn = "bs_n%d_k%d.cir" % (N, k)
    t0, tend, topen = 50.0, 50.0 + TZ + 500.0, 50.0 + TZ + 2
    L = ['.hdl "%s"' % VA, '.include "%s"' % MODEL, '.include "%s"' % SHIM,
         '.OPTIONS TIMEINT METHOD=GEAR RELTOL=1e-6 ABSTOL=1e-15 CHGTOL=1e-17',
         '.param LT=%gn RS=%g CA=%gf' % (L_NH, RS, CA),
         'CA bka 0 {CA}', 'VHI vhi 0 %g' % VGH,
         'VGT  gt  0 PWL(0 0 %gp 0 %gp %g %gp %g %gp 0)' % (t0-2, t0, VGH, t0+TZ, VGH, t0+TZ+2),
         'VGTP gtp 0 PWL(0 %g %gp %g %gp 0 %gp 0 %gp %g)' % (VGH, t0-2, VGH, t0, t0+TZ, t0+TZ+2, VGH),
         'XSWN bka gt  sw 0   sg13_lv_nmos w=%gu l=0.13u' % WSW,
         'XSWP bka gtp sw vhi sg13_lv_pmos w=%gu l=0.13u' % (2*WSW),
         'LT sw mid {LT}', 'RT mid bkb {RS}']
    for i in range(N):
        L += ['VI%d in%d 0 %g' % (i, i, 0.0 if i < k else DV),
              'XP%d o%d in%d bkb bkb sg13_lv_pmos w=%gu l=0.13u' % (i, i, i, WP),
              'XN%d o%d in%d 0 0 sg13_lv_nmos w=%gu l=0.13u' % (i, i, i, WN),
              'CL%d o%d 0 %gf' % (i, i, CLOAD)]
    L += ['Bqt qt 0 V={ I(LT) }', '.ic V(bka)=%g V(bkb)=0' % DV, '.tran 0.1p %gp' % tend,
          '.measure tran QTR   INTEGRAL V(qt) FROM=0 TO=%gp' % tend,
          '.measure tran VBEND FIND V(bkb) AT=%gp' % (tend-5),
          '.measure tran BKE   FIND V(bkb) AT=900p',
          '.measure tran VBMIN MIN V(bkb) FROM=%gp TO=%gp' % (topen, tend),
          '.measure tran VBMAX MAX V(bkb) FROM=%gp TO=%gp' % (topen, tend)]
    if k > 0: L.append('.measure tran OSW FIND V(o0) AT=900p')
    L.append('.end')
    open(fn, 'w').write("\n".join(L) + "\n")
    try:
        o = subprocess.run([XYCE, fn], capture_output=True, text=True, timeout=600, env=ENV).stdout
    except subprocess.TimeoutExpired:
        return None
    g = {}
    for key in ("QTR", "VBEND", "BKE", "VBMIN", "VBMAX", "OSW"):
        m = re.search(r"^%s\s*=\s*(\S+)" % key, o, re.M)
        if m:
            try: g[key] = float(m.group(1))
            except ValueError: pass
    return g if "BKE" in g else None

def main():
    print("N=%d bank (C_A=%.3f fF, L=%g nH, t_ZCS=%.2f ps, dV=%.1f) -- 1/N scaling test"
          % (N, CA, L_NH, TZ, DV))
    print("REFERENCE N=8: rail k=0 0.6795 | k=N/2 0.5174 | k=N 0.4468 V; slope 28.6 mV/gate")
    print("   k | QTR(fC)  rail@900p  O_sw@900p  settle%  ring[min..max]")
    R = {}
    for k in KS:
        g = run(k)
        if g is None:
            print("   %d | FAILED" % k); continue
        rail = g["BKE"]
        st = 100.0*g["OSW"]/rail if ("OSW" in g and rail) else None
        print("   %2d | %7.3f  %7.4f    %s  %s  [%.4f..%.4f]"
              % (k, g["QTR"]*1e15, rail,
                 ("%7.4f" % g["OSW"]) if "OSW" in g else "    n/a",
                 ("%6.1f" % st) if st is not None else "   n/a",
                 g.get("VBMIN", 0), g.get("VBMAX", 0)))
        R[k] = {"k": k, "QTR_fC": round(g["QTR"]*1e15, 4), "rail_900ps": round(rail, 5),
                "O_switching_900ps": round(g["OSW"], 5) if "OSW" in g else None,
                "settle_pct_of_rail": round(st, 2) if st is not None else None,
                "V_B_min_postopen": round(g.get("VBMIN", 0), 5),
                "V_B_max_postopen": round(g.get("VBMAX", 0), 5)}
    if all(k in R for k in (6, 8, 10)):
        slope = abs(R[10]["rail_900ps"] - R[6]["rail_900ps"])/4.0
        print("\n   MEASURED slope at k=N/2: %.1f mV/gate   (N=8 was 28.6; 1/N predicts 14.3)"
              % (1000*slope))
        print("   ratio to N=8 slope: %.3f   (1/N scaling predicts 0.500)" % (slope/0.0286))
        print("   nominal rail at k=N/2: %.4f V   (N=8 was 0.5174)" % R[8]["rail_900ps"])
    if 0 in R and N in R:
        print("   full-scale endpoints: %.4f -> %.4f V   (N=8 was 0.6795 -> 0.4468)"
              % (R[0]["rail_900ps"], R[N]["rail_900ps"]))
        print("   worst-case settling at k=N: %s%%   (N=8 was 90.1)"
              % R[N]["settle_pct_of_rail"])
    json.dump({"_doc": "1/N scaling test for the per-gate rail sensitivity: N=16 bank with C_A "
                       "doubled and L halved so the LC half-cycle is unchanged. Compared against "
                       "the N=8 case in qal_bankN_modulation.json at the same dV=0.8.",
               "N": N, "dV": DV, "C_A_fF": CA, "L_nH": L_NH, "t_zcs_ps": TZ,
               "rows": [R[k] for k in sorted(R)]},
              open("qal_bankN_scaling.json", "w"), indent=1)
    print("   wrote qal_bankN_scaling.json")

if __name__ == "__main__":
    main()
