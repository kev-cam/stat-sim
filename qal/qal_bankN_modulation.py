#!/usr/bin/env python3
"""DATA MODULATION OF A REAL GATE BANK -- the measurement the dual-rail claim was missing.

WHY. qal_twobank.py:24-31 argues dual-rail is REQUIRED for the POWER mechanism, citing
"measured 100% modulation, qal_a1f.py". That citation resolves (qal_a1f.py:69, decks
sr_d1.cir / sr_d0.cir) to ONE ideal 10 fF flying capacitor dumping onto ONE 10 fF linear
load through a behavioral switch -- no transistors, no gates, N=1, two data values. The
100% is simply "a cap charged to dV delivers 3 fC, a cap at 0 delivers 0 fC". It is an
N=1 number and says nothing about a bank.

WHAT THIS MEASURES. The SAME 8-inverter bank, devices and loads as every other anchor
(qal_hop_gates.py:68-72), receiving the SAME resonant hop, with the number k of gates whose
output actually charges swept 0..8. k is the data. Reported per k:
    QTR     charge actually delivered through the inductor   <- the analogue of QDEL
    V_B_end the rail the next stage inherits                 <- the functional-cliff quantity
    BKE     the rail at 900 ps (the anchors' readout time, lc_800.cir:61-62)
    O_SW    a switching gate's output at 900 ps (settling check)

TWO THINGS ARE HELD FIXED ON PURPOSE, because a real pipeline cannot re-tune per data word:
  * C_A and V_A(0) = dV  -> identical source charge every cycle. This stands in for "recycle +
    one FIXED flycap top-up": the bank receives the same energy regardless of data, which is
    exactly the condition the dual-rail argument says single-rail cannot meet.
  * t_ZCS fixed at the corrected-topology value for that swing (396.68 / 400.41 / 404.78 ps,
    qal_hop_corrected.json). Holding it fixed is the faithful choice AND it deliberately
    captures the second data-dependence noted at qal_hop_gates.py:121-125 -- the current zero
    itself moves with load. qal_bankN_zcs.py MEASURES that movement: 330.5 -> 392.1 ps across
    k=0..8 at dV=0.8 (61.6 ps, 16.9% of mean, +7.5 ps/gate). Every one of those zeros is
    EARLIER than the fixed 396.68 ps, so the fixed freeze is always on the cheap LATE side --
    which is why the penalty stays inside the quadratically-flat peak (qal_a1f_inductive.py:
    44-50) instead of trapping 1/2*L*I^2.

RESULT (corrected topology): full-scale charge modulation between the two absolute data
extremes is 2.7% / 2.1% / 1.0% at dV = 0.8 / 1.0 / 1.2 -- against the 100% the dual-rail
claim cites from an N=1 ideal-cap deck.

Everything else (devices, Rs=10, switch 20u/40u, VGH=1.5, 2 fF loads) is unchanged from the
anchor decks so the result composes with them.
"""
import os, re, subprocess, json, sys

XYCE  = "/usr/local/src/xyce-build/src/Xyce"
VA    = "/usr/local/share/xyce/verilog-a/psp103/psp103.va"
MODEL = "/usr/local/src/kestrel/sim/models/sg13g2_psp103_tt.lib"
SHIM  = "/usr/local/src/stat-sim/qal/sg13lv_compat.sp"
ENV   = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS")

MGATE = 8
WP, WN, CLOAD = 1.12, 0.74, 2.0
WSW, VGH, RS, L_NH = 20.0, 1.5, 10.0, 400.0

# (dV, C_A fF from the working-bank calibration, t_ZCS ps measured on the k=4 working case)
# t_ZCS values re-taken from the CORRECTED topology (qal_hop_corrected.json, L=400 nH,
# main session 2026-09-25): 396.68 / 400.41 / 404.78 ps. The old ringing-topology values
# (367.51/400.63/411.23) do not apply to this deck.
CASES = [(0.8, 35.0025, 396.68),
         (1.0, 35.9790, 400.41),
         (1.2, 36.8010, 404.78)]

def deck(fn, dv, ca, tz, k):
    """k gates have input LOW  -> their pMOS charges the 2 fF load to the rail (they 'switch');
       8-k gates have input HIGH -> their nMOS holds the output at 0 (no charging)."""
    t0, tend = 50.0, 50.0 + tz + 500.0
    L = ['.hdl "%s"' % VA, '.include "%s"' % MODEL, '.include "%s"' % SHIM,
         '.OPTIONS TIMEINT METHOD=GEAR RELTOL=1e-6 ABSTOL=1e-15 CHGTOL=1e-17',
         '.param LT=%gn RS=%g CA=%gf' % (L_NH, RS, ca),
         'CA bka 0 {CA}',
         'VHI vhi 0 %g' % VGH,
         'VGT  gt  0 PWL(0 0 %gp 0 %gp %g %gp %g %gp 0)'
             % (t0-2, t0, VGH, t0+tz, VGH, t0+tz+2),
         'VGTP gtp 0 PWL(0 %g %gp %g %gp 0 %gp 0 %gp %g)'
             % (VGH, t0-2, VGH, t0, t0+tz, t0+tz+2, VGH),
         # CORRECTED TOPOLOGY (matches qal_hop_gates.py:187-190 as fixed 2026-09-25): the
         # disconnect switch sits on the RECEIVING side, so opening it isolates bank B and B
         # actually HOLDS its charge. In the earlier arrangement (switch on the sending side)
         # the L-Rs branch stayed tied to bkb after the open and the bank rang with a ~500 ps
         # period, so every fixed-time sample read an arbitrary ring phase.
         'XSWN sw gt  bkb 0   sg13_lv_nmos w=%gu l=0.13u' % WSW,
         'XSWP sw gtp bkb vhi sg13_lv_pmos w=%gu l=0.13u' % (2*WSW),
         'LT bka mid {LT}', 'RT mid sw {RS}']
    for i in range(MGATE):
        lo = (i < k)                      # input low -> output charges high
        L += ['VI%d in%d 0 %g' % (i, i, 0.0 if lo else dv),
              'XP%d o%d in%d bkb bkb sg13_lv_pmos w=%gu l=0.13u' % (i, i, i, WP),
              'XN%d o%d in%d 0 0 sg13_lv_nmos w=%gu l=0.13u' % (i, i, i, WN),
              'CL%d o%d 0 %gf' % (i, i, CLOAD)]
    # READOUT CONVENTION matches the existing anchors: the rail and the gate output are read at
    # 900 ps (lc_800.cir:61-62 -> BKE=0.5165, O1E=0.5039 = the 97.6% settling figure), and VBEND
    # at tend-5 (qal_hop_gates.py:194). After the switch opens the L-Rs branch is still tied to
    # bkb with the open switch's device capacitance at the far end, so V(bkb) RINGS; VBMIN/VBMAX
    # over the post-open window report that ring explicitly instead of hiding it in one sample.
    topen = t0 + tz + 2
    L += ['Bqt qt 0 V={ I(LT) }',
          '.ic V(bka)=%g V(bkb)=0' % dv,
          '.tran 0.1p %gp' % tend,
          '.measure tran QTR   INTEGRAL V(qt) FROM=0 TO=%gp' % tend,
          '.measure tran VBPK  MAX V(bkb) FROM=%gp TO=%gp' % (t0, tend),
          '.measure tran VBEND FIND V(bkb) AT=%gp' % (tend-5),
          '.measure tran VAEND FIND V(bka) AT=%gp' % (tend-5),
          '.measure tran BKE   FIND V(bkb) AT=900p',
          '.measure tran VBMIN MIN V(bkb) FROM=%gp TO=%gp' % (topen, tend),
          '.measure tran VBMAX MAX V(bkb) FROM=%gp TO=%gp' % (topen, tend)]
    if k > 0:
        L.append('.measure tran OSW FIND V(o0) AT=900p')       # a switching gate, anchor time
    L.append('.end')
    open(fn, 'w').write("\n".join(L) + "\n")
    keys = ("QTR", "VBPK", "VBEND", "VAEND", "BKE", "VBMIN", "VBMAX", "OSW")
    try:
        o = subprocess.run([XYCE, fn], capture_output=True, text=True, timeout=600,
                           env=ENV).stdout
    except subprocess.TimeoutExpired:
        return None, "TIMEOUT"
    g = {}
    for key in keys:
        m = re.search(r"^%s\s*=\s*(\S+)" % key, o, re.M)
        if m:
            try: g[key] = float(m.group(1))
            except ValueError: pass
    if "VBEND" not in g:
        err = "; ".join(l.strip() for l in o.splitlines() if "rror" in l or "bort" in l)[:200]
        return None, (err or "no measures")
    return g, None

def main():
    only = float(sys.argv[1]) if len(sys.argv) > 1 else None
    out = []
    for dv, ca, tz in CASES:
        if only is not None and abs(dv - only) > 1e-9:
            continue
        print("\n=== dV=%.1f V, C_A=%.4f fF, t_ZCS=%.2f ps FIXED, L=%g nH, %d-gate bank ==="
              % (dv, ca, tz, L_NH, MGATE))
        print("   k | QTR(fC)  V_B_end  rail@900p  O_sw@900p  settle%  ring[min..max]")
        rows = []
        for k in range(MGATE + 1):
            g, err = deck("bnf_dv%d_k%d.cir" % (int(dv*1000), k), dv, ca, tz, k)
            if g is None:
                print("   %d | FAILED: %s" % (k, err)); continue
            q, rail = g["QTR"]*1e15, g.get("BKE", 0)
            st = (100.0*g["OSW"]/rail) if ("OSW" in g and rail) else None
            print("   %d | %7.3f  %7.4f   %7.4f    %s  %s  [%.4f..%.4f]"
                  % (k, q, g["VBEND"], rail,
                     ("%7.4f" % g["OSW"]) if "OSW" in g else "    n/a",
                     ("%6.1f" % st) if st is not None else "   n/a",
                     g.get("VBMIN", 0), g.get("VBMAX", 0)))
            rows.append({"k": k, "QTR_fC": round(q, 4),
                         "V_B_end": round(g["VBEND"], 5),
                         "V_B_peak": round(g.get("VBPK", 0), 5),
                         "rail_900ps": round(rail, 5),
                         "O_switching_900ps": round(g["OSW"], 5) if "OSW" in g else None,
                         "settle_pct_of_rail": round(st, 2) if st is not None else None,
                         "V_B_min_postopen": round(g.get("VBMIN", 0), 5),
                         "V_B_max_postopen": round(g.get("VBMAX", 0), 5),
                         "V_A_end": round(g.get("VAEND", 0), 5)})
        out.append({"dV": dv, "C_A_fF": ca, "t_zcs_ps": tz, "L_nH": L_NH,
                    "m_gates": MGATE, "rows": rows})
        if len(rows) >= 2:
            q0, qN = rows[0]["QTR_fC"], rows[-1]["QTR_fC"]
            v0, vN = rows[0]["rail_900ps"], rows[-1]["rail_900ps"]
            print("   FULL-SCALE (k=0 -> k=%d, the absolute worst case, all-quiet vs all-switch):"
                  % MGATE)
            print("     QTR       %.3f -> %.3f fC  = %.1f%% of mean  (cf. the N=1 claim of 100%%)"
                  % (q0, qN, 100*abs(qN-q0)/(0.5*(q0+qN))))
            print("     rail@900p %.4f -> %.4f V  = %.0f mV  (%.1f%% of mean)"
                  % (v0, vN, 1000*(vN-v0), 100*abs(vN-v0)/(0.5*(v0+vN))))
            mid = [r for r in rows if r["k"] in (MGATE//2 - 1, MGATE//2 + 1)]
            if len(mid) == 2:
                dq = (mid[1]["QTR_fC"] - mid[0]["QTR_fC"]) / 2.0
                dvr = (mid[1]["rail_900ps"] - mid[0]["rail_900ps"]) / 2.0
                k4 = [r for r in rows if r["k"] == MGATE//2][0]
                print("     SLOPE at the mean (k=%d): dQ/dk = %+.4f fC/gate (%.2f%%/gate), "
                      "dV_rail/dk = %+.1f mV/gate (%.2f%%/gate)"
                      % (MGATE//2, dq, 100*dq/k4["QTR_fC"], 1000*dvr,
                         100*abs(dvr)/k4["rail_900ps"]))
        fn = "qal_bankN_modulation_fixed.json"
        prev = []
        if os.path.exists(fn):
            try: prev = json.load(open(fn)).get("cases", [])
            except Exception: prev = []
        keep = [c for c in prev if abs(c["dV"] - dv) > 1e-9]
        json.dump({"_doc": "Data modulation of a REAL 8-gate QAL bank: k of 8 gate outputs "
                           "actually charge. Source charge (C_A, V_A(0)=dV) and switch timing "
                           "t_ZCS are HELD FIXED across k, standing in for recycle + a fixed "
                           "flycap top-up and for fixed (non-re-tuned) switch timing. QTR is "
                           "the delivered charge -- the bank-scale analogue of the N=1 QDEL in "
                           "sr_d1/sr_d0.cir that the '100% modulation' claim rests on.",
                   "cases": keep + out[-1:]}, open(fn, "w"), indent=1)
        print("   wrote %s (CORRECTED receiving-side-switch topology)" % fn)

if __name__ == "__main__":
    main()
