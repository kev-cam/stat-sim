#!/usr/bin/env python3
"""Does the ZERO-CURRENT instant move with the DATA? -- the one dual-rail argument left standing.

CONTEXT. qal_a1f_inductive.py:75 asserts "PER-BIT TIMING: not a dual-rail reason (the resonant hop
is linear -> T_half data-independent, measured)". That was measured on IDEAL LINEAR CAPS (CL=10 fF,
ideal L). qal_hop_gates.py:121-125 contradicts it once REAL GATES load the bank: "the analytic
pi*sqrt(L*Cser) ... is 36% early (158.5 ps predicted vs 214.84 ps measured) ... a gate-loaded bank's
capacitance is strongly NONLINEAR ... so the zero is not at pi*sqrt(LC)" and "FIXED ANALYTIC TIMING
IS NOT ENOUGH -- the zero moves with load and swing."

Neither of those measured the zero against DATA at fixed swing. That is what this does: the same
8-gate bank, k of 8 outputs charging, switch held ON throughout, and the true inductor-current zero
read off I(LT). If t_ZCS is flat in k, single-rail can use one fixed freeze time and dual-rail's
"constant generator load" argument dies too. If it moves, that is a real (and quantified) dual-rail
benefit -- and it also sets how much of the rail wander in qal_bankN_modulation.py is mistimed-freeze
rather than data-dependent charge.
"""
import os, re, subprocess, json, math, sys

XYCE  = "/usr/local/src/xyce-build/src/Xyce"
VA    = "/usr/local/share/xyce/verilog-a/psp103/psp103.va"
MODEL = "/usr/local/src/kestrel/sim/models/sg13g2_psp103_tt.lib"
SHIM  = "/usr/local/src/stat-sim/qal/sg13lv_compat.sp"
ENV   = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS")

MGATE, WP, WN, CLOAD = 8, 1.12, 0.74, 2.0
WSW, VGH, RS, L_NH = 20.0, 1.5, 10.0, 400.0
CASES = [(0.8, 35.0025), (1.0, 35.9790), (1.2, 36.8010)]

def probe(fn, dv, ca, k):
    """Switch ON from 50 ps and held ON; read the FIRST zero of I(LT) after 60 ps."""
    tend = 1200.0
    L = ['.hdl "%s"' % VA, '.include "%s"' % MODEL, '.include "%s"' % SHIM,
         '.OPTIONS TIMEINT METHOD=GEAR RELTOL=1e-6 ABSTOL=1e-15 CHGTOL=1e-17',
         '.param LT=%gn RS=%g CA=%gf' % (L_NH, RS, ca),
         'CA bka 0 {CA}', 'VHI vhi 0 %g' % VGH,
         'VGT  gt  0 PWL(0 0 48p 0 50p %g %gp %g)' % (VGH, tend, VGH),
         'VGTP gtp 0 PWL(0 %g 48p %g 50p 0 %gp 0)' % (VGH, VGH, tend),
         'XSWN bka gt  sw 0   sg13_lv_nmos w=%gu l=0.13u' % WSW,
         'XSWP bka gtp sw vhi sg13_lv_pmos w=%gu l=0.13u' % (2*WSW),
         'LT sw mid {LT}', 'RT mid bkb {RS}']
    for i in range(MGATE):
        L += ['VI%d in%d 0 %g' % (i, i, 0.0 if i < k else dv),
              'XP%d o%d in%d bkb bkb sg13_lv_pmos w=%gu l=0.13u' % (i, i, i, WP),
              'XN%d o%d in%d 0 0 sg13_lv_nmos w=%gu l=0.13u' % (i, i, i, WN),
              'CL%d o%d 0 %gf' % (i, i, CLOAD)]
    L += ['.ic V(bka)=%g V(bkb)=0' % dv, '.print tran I(LT) V(bkb)',
          '.tran 0.1p %gp' % tend, '.end']
    open(fn, 'w').write("\n".join(L) + "\n")
    try:
        subprocess.run([XYCE, fn], capture_output=True, text=True, timeout=600, env=ENV)
    except subprocess.TimeoutExpired:
        return None, None
    try:
        rows = open(fn + '.prn').read().strip().split('\n')
    except Exception:
        return None, None
    hdr = rows[0].split()
    ii = [i for i, h in enumerate(hdr) if 'LT' in h.upper()]
    jj = [i for i, h in enumerate(hdr) if 'BKB' in h.upper()]
    if not ii: return None, None
    ii = ii[0]; jj = jj[0] if jj else None
    prev = prevt = prevv = None
    for ln in rows[1:]:
        f = ln.split()
        if len(f) <= ii: continue
        try:
            t, cur = float(f[1]), float(f[ii])
            v = float(f[jj]) if jj is not None and len(f) > jj else 0.0
        except ValueError:
            continue
        if prev is not None and prev > 0 and cur <= 0 and t > 60e-12:
            # linear interpolation onto the exact zero
            frac = prev / (prev - cur) if (prev - cur) else 0.0
            return (prevt + frac*(t - prevt))*1e12, prevv + frac*(v - prevv)
        prev, prevt, prevv = cur, t, v
    return None, None

def main():
    only = float(sys.argv[1]) if len(sys.argv) > 1 else None
    out = []
    for dv, ca in CASES:
        if only is not None and abs(dv - only) > 1e-9: continue
        print("\n=== t_ZCS vs DATA, dV=%.1f V, C_A=%.4f fF, L=%g nH, %d-gate bank ==="
              % (dv, ca, L_NH, MGATE))
        print("   k | t_ZCS(ps)  V_B@zero")
        rows = []
        for k in range(MGATE + 1):
            tz, vb = probe("zc_dv%d_k%d.cir" % (int(dv*1000), k), dv, ca, k)
            if tz is None:
                print("   %d | no zero found" % k); continue
            print("   %d | %8.2f   %7.4f" % (k, tz, vb))
            rows.append({"k": k, "t_zcs_ps": round(tz, 3), "V_B_at_zero": round(vb, 5)})
        if len(rows) >= 2:
            ts = [r["t_zcs_ps"] for r in rows]
            mean = sum(ts)/len(ts)
            print("   SPREAD k=0..%d: %.2f -> %.2f ps, full-scale %.2f ps (%.1f%% of mean %.1f ps)"
                  % (MGATE, ts[0], ts[-1], max(ts)-min(ts), 100*(max(ts)-min(ts))/mean, mean))
            mid = [r for r in rows if r["k"] in (MGATE//2-1, MGATE//2+1)]
            if len(mid) == 2:
                print("   SLOPE at the mean: %+.2f ps/gate" %
                      ((mid[1]["t_zcs_ps"] - mid[0]["t_zcs_ps"])/2.0))
        out.append({"dV": dv, "C_A_fF": ca, "L_nH": L_NH, "m_gates": MGATE, "rows": rows})
        fn = "qal_bankN_zcs.json"
        prev = []
        if os.path.exists(fn):
            try: prev = json.load(open(fn)).get("cases", [])
            except Exception: prev = []
        json.dump({"_doc": "Zero-current (freeze) instant vs DATA for a real 8-gate QAL bank, switch "
                           "held ON. Tests qal_a1f_inductive.py:75 ('T_half data-independent'), which "
                           "was measured on ideal linear caps, against a gate-loaded bank.",
                   "cases": [c for c in prev if abs(c["dV"]-dv) > 1e-9] + out[-1:]},
                  open(fn, "w"), indent=1)
        print("   wrote %s" % fn)

if __name__ == "__main__":
    main()
