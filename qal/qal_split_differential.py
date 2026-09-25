#!/usr/bin/env python3
"""DIFFERENTIAL: recover the path-vs-gate loss split without unreliable integrals.

WHY. The per-hop loss is now measured integral-free and exactly:
    E_hop = [1/2*C_A*(V_Ai^2 - V_Af^2)]  -  E_stored_B(V_Bend)
i.e. energy that left the sending bank minus energy now stored in the receiving bank. That total
is trustworthy, but it does NOT say how much was burned in the transfer path (switch Ron +
inductor Rs) versus in the gates' own channels as they settle. The previous split came from
'.measure INTEGRAL V(<B-source>)', which was shown to under-report by 11-44% against the exact
linear-cap energy drop (7 of 8 rows off by >15%) and to produce impossible NEGATIVE switch
gate-drive energy. So the split is recovered here by DIFFERENCE between runs instead.

TWO REFERENCES, because they bracket the answer and disagreeing would itself be informative:

  REF-P  "passive": the gate bank is replaced by a PLAIN LINEAR CAPACITOR of the same C_eff.
         No gates at all, so nothing dissipates except the path ->  E_hop(REF-P) = E_path.
         Weakness: a linear cap does not reproduce the gate bank's strongly NONLINEAR C(V)
         (the calibration curve knees hard at the device threshold), so the current waveform,
         t_ZCS and V_Bend differ somewhat -> the path loss is measured on a slightly different
         trajectory. Mismatch is reported, not hidden.

  REF-Q  "quiescent": the SAME gates with the SAME devices, but every input tied HIGH so every
         nMOS holds its output at 0 and no output ever charges. Device loading and topology are
         identical to the working case; only the switching work is removed. So
         E_hop(REF-Q) = E_path + gate PARASITIC charging, and
         E_settling = E_hop(working) - E_hop(REF-Q) is cleanly the logic work.
         Weakness: it still contains the parasitic part of the gate term, so it is an upper
         bound on path loss, where REF-P is a lower bound.

Between them: E_path lies in [E_hop(REF-P), E_hop(REF-Q)], and the gate term in
[E_hop(work) - E_hop(REF-Q), E_hop(work) - E_hop(REF-P)]. If the two references land close, the
split is well determined; if they diverge, the parasitic share is large and that is the finding.

Run only at FUNCTIONALLY VALID swings. Measured gate-output settling against the bank rail:
64% at dV=0.6 (rail 0.382 V, below the ~0.4 V threshold -> invalid), then 97.6% / 94.8% / 95.1%
at dV = 0.8 / 1.0 / 1.2. So dV=0.6 is excluded.
"""
import json, math, sys
sys.path.insert(0, "/usr/local/src/stat-sim/qal")
import qal_hop_gates as hg

DVS = [0.8, 1.0, 1.2]     # functionally valid swings only
L_NH = 400.0              # the better (slower, cheaper) hop of the two studied
ORIG = hg.bank            # the working, alternating-input bank

def bank_quiescent(supply):
    """REF-Q: identical devices, every input HIGH -> nMOS clamps every output to 0, no output
    ever charges, so the logic work is removed while the loading stays exactly the same."""
    L = []
    for i in range(hg.MGATE):
        L.append("VI%d in%d 0 %g" % (i, i, hg.DV))          # ALL high
        L.append("XP%d o%d in%d %s %s sg13_lv_pmos w=%gu l=0.13u" % (i, i, i, supply, supply, hg.WP))
        L.append("XN%d o%d in%d 0 0 sg13_lv_nmos w=%gu l=0.13u" % (i, i, i, hg.WN))
        L.append("CL%d o%d 0 %gf" % (i, i, hg.CLOAD))
    return L

def make_passive(c_ff):
    """REF-P: a plain linear capacitor of the same C_eff, no devices at all."""
    def f(supply):
        return ["CBK %s 0 %gf" % (supply, c_ff)]
    return f

def calib_curve(tag):
    g, err = hg.calib()
    if g is None: return None, err
    q = g["QTOT"]; c_eff = (q/hg.DV)*1e15
    curve = []
    for v in hg.VCHK:
        nm = "E%03d" % int(round(v*1000))
        if nm in g: curve.append((v, g[nm]*1e15))
    return (c_eff, curve), None

def interp(curve, v):
    if v <= curve[0][0]: return curve[0][1]*(v/curve[0][0])**2 if curve[0][0] else 0.0
    for (v1,e1),(v2,e2) in zip(curve, curve[1:]):
        if v <= v2: return e1 + (e2-e1)*(v-v1)/(v2-v1)
    return curve[-1][1]*(v/curve[-1][0])**2

def one_hop(tag, c_eff, estored):
    """probe the true current zero, then run the hop; return the integral-free E_hop."""
    tz = hg.probe_zero("sp_%s_probe.cir" % tag, L_NH, c_eff)
    if tz is None: return None, "no current zero"
    g, err = hg.hop_deck("sp_%s_hop.cir" % tag, L_NH, c_eff, tz)
    if g is None: return None, err
    va, vb = g.get("VAEND"), g.get("VBEND")
    ca = c_eff*1e-15                       # sending bank is a plain cap of the same value
    e_out = 0.5*ca*(hg.DV*hg.DV - va*va)*1e15
    e_st  = estored(max(vb, 0.0))
    return {"t_zcs_ps": round(tz,2), "V_A_end": round(va,5), "V_B_end": round(vb,5),
            "E_outA_fJ": round(e_out,4), "E_storedB_fJ": round(e_st,4),
            "E_hop_fJ": round(e_out-e_st,4)}, None

def main():
    print("DIFFERENTIAL path/gate split, L = %g nH, integral-free accounting" % L_NH)
    print("  REF-P = plain linear cap (no gates)      -> lower bound on E_path")
    print("  REF-Q = same gates, all inputs high      -> upper bound on E_path (adds gate parasitics)")
    print("  E_settling = E_hop(working) - E_hop(REF-Q)\n")
    print("   dV |  run   | t_ZCS  V_Bend | E_hop  | E_path band   E_gate band | E_settling")
    print("  (V) |        |  (ps)    (V)  |  (fJ)  |     (fJ)          (fJ)    |    (fJ)")
    rows = []
    for dv in DVS:
        hg.DV = dv
        hg.VCHK = [round(x*dv, 4) for x in (0.167, 0.333, 0.5, 0.667, 0.833, 0.917, 1.0)]

        # --- working bank (alternating inputs): its own calibration curve ---
        hg.bank = ORIG
        cal, err = calib_curve("work")
        if cal is None: print("  %.2f  CALIB(work) FAILED: %s" % (dv, err)); continue
        c_eff, curve = cal
        work, err = one_hop("w%03d" % int(dv*1000), c_eff, lambda v: interp(curve, v))
        if work is None: print("  %.2f  HOP(work) FAILED: %s" % (dv, err)); continue

        # --- REF-Q: quiescent gates, needs its OWN calibration (different C(V)) ---
        hg.bank = bank_quiescent
        calq, err = calib_curve("quiet")
        if calq is None: print("  %.2f  CALIB(quiet) FAILED: %s" % (dv, err)); continue
        c_q, curve_q = calq
        refq, err = one_hop("q%03d" % int(dv*1000), c_q, lambda v: interp(curve_q, v))
        if refq is None: print("  %.2f  HOP(quiet) FAILED: %s" % (dv, err)); continue

        # --- REF-P: passive linear cap of the working C_eff; E_stored is exact ---
        hg.bank = make_passive(c_eff)
        refp, err = one_hop("p%03d" % int(dv*1000), c_eff,
                            lambda v: 0.5*(c_eff*1e-15)*v*v*1e15)
        if refp is None: print("  %.2f  HOP(passive) FAILED: %s" % (dv, err)); continue

        e_w, e_q, e_p = work["E_hop_fJ"], refq["E_hop_fJ"], refp["E_hop_fJ"]
        settle = e_w - e_q
        for nm, r in (("work", work), ("REF-Q", refq), ("REF-P", refp)):
            print("  %.2f | %-6s | %6.1f %6.3f | %6.3f |" % (dv, nm, r["t_zcs_ps"], r["V_B_end"], r["E_hop_fJ"]),
                  end="")
            if nm == "work":
                print("  %.3f-%.3f   %.3f-%.3f | %8.3f" % (e_p, e_q, e_w-e_q, e_w-e_p, settle))
            else:
                print()
        rows.append({"dV": dv, "L_nH": L_NH, "C_eff_fF": round(c_eff,3), "C_quiet_fF": round(c_q,3),
                     "working": work, "ref_quiescent": refq, "ref_passive": refp,
                     "E_path_lo_fJ": round(e_p,4), "E_path_hi_fJ": round(e_q,4),
                     "E_gate_lo_fJ": round(e_w-e_q,4), "E_gate_hi_fJ": round(e_w-e_p,4),
                     "E_settling_fJ": round(settle,4),
                     "E_settling_per_gate_fJ": round(settle/hg.MGATE,5),
                     "path_pct_of_hop_lo": round(100*e_p/e_w,2) if e_w else None,
                     "path_pct_of_hop_hi": round(100*e_q/e_w,2) if e_w else None})
        print()
    hg.bank = ORIG
    json.dump({"_doc": "Differential recovery of the path-vs-gate loss split, integral-free. "
                       "REF-P (plain linear cap, no gates) lower-bounds E_path; REF-Q (same gates, "
                       "all inputs high so nothing switches) upper-bounds it by also containing the "
                       "gates' parasitic charging. E_settling = E_hop(working) - E_hop(REF-Q) is the "
                       "logic work. dV=0.6 excluded: measured gate settling is only 64% there "
                       "(bank rail 0.382 V, below the ~0.4 V threshold).",
               "L_nH": L_NH, "m_gates": hg.MGATE, "rows": rows},
              open("qal_split_differential.json","w"), indent=1)
    print("wrote qal_split_differential.json")
    for r in rows:
        print("  dV=%.2f: E_path %.3f-%.3f fJ (%.0f-%.0f%% of hop), settling %.3f fJ = %.4f fJ/gate"
              % (r["dV"], r["E_path_lo_fJ"], r["E_path_hi_fJ"],
                 r["path_pct_of_hop_lo"], r["path_pct_of_hop_hi"],
                 r["E_settling_fJ"], r["E_settling_per_gate_fJ"]))

if __name__ == "__main__":
    main()
