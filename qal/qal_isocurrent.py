#!/usr/bin/env python3
"""ISO-CURRENT swing sweep: does lower dV buy SPEED when L is scaled with it?

THE CORRECTION THIS TESTS. The earlier dV sweep held L FIXED and found the hop time essentially
constant (392.3 / 396.7 / 400.4 / 404.8 ps for dV = 0.6 / 0.8 / 1.0 / 1.2 at L = 400 nH, a 3% span),
and I concluded "swing buys energy, not speed". That conclusion was an artefact of the experiment:
with L fixed the transfer is RESONANCE-limited, t = pi*sqrt(L*C), which is amplitude-INDEPENDENT --
lowering dV lowers the peak current proportionally and the time does not move. C_eff varies only 8.4%
across the sweep, so sqrt(C) predicts ~4% and 3% was measured. The sweep was measuring the LC period,
not a swing effect.

THE USER'S ARGUMENT, which is the CURRENT-limited regime: for a fixed current, dV is proportional to
dt (I = C dV/dt), so the lower the swing the faster you can reverse. Formally, peak current in the
hop is I_pk ~ dV*sqrt(C/L); hold that fixed while lowering dV and L may shrink as L ~ dV^2*C, giving
    t = pi*sqrt(L*C) ~ dV
so at constant current the hop time falls PROPORTIONALLY with swing.

ALREADY CONFIRMED from the fixed-L data, which happens to contain one iso-current pair:
    dV=1.2, L=400 nH -> I_pk 200.8 uA, t 404.8 ps
    dV=0.6, L=100 nH -> I_pk 179.2 uA, t 220.8 ps
    currents match to 11% (residual is C_eff 36.8 vs 33.94 fF); time ratio 1.83 vs predicted 2.00.
So t ~ dV holds. This script fills in the two intermediate points that were never run, to get the
whole iso-current line rather than its endpoints.

DESIGN RULE UNDER TEST: L = L_ref * (dV/dV_ref)^2, anchored at dV_ref = 1.2 V, L_ref = 400 nH.
    dV 0.6 -> 100 nH (have)   0.8 -> 178 nH (NEW)   1.0 -> 278 nH (NEW)   1.2 -> 400 nH (have)

THE CONSTRAINT THAT BOUNDS IT. Lower swing is only usable above the measured FUNCTIONAL CLIFF. With
the fixed (receiving-side) disconnect so the bank actually holds, measured gate settling is 34.8% at
dV=0.6, 77.1% at 0.8, 100% at 1.0 and 1.2 -- so the floor is dV ~ 1.0 V, where the pMOS still clears
its threshold. The speed available from low swing is therefore capped by the device Vt, and the
interesting operating point is dV=1.0 with L scaled to ~278 nH: predicted ~337 ps, versus 404.8 ps at
dV=1.2, while also being cheaper (1.303 vs 1.900 fJ/gate-settle).

Energies are integral-free throughout: E_hop = 1/2*C_A*(V_Ai^2 - V_Af^2) - E_stored_B(V_Bend), with
E_stored(V) from a slow-ramp calibration of the same bank. ('.measure INTEGRAL V(<B-source>)'
under-reports by 11-44% and is not used.)
"""
import json, math, re, sys
sys.path.insert(0, "/usr/local/src/stat-sim/qal")
import qal_hop_gates as hg

DV_REF, L_REF = 1.2, 400.0
DVS = [0.6, 0.8, 1.0, 1.2]
SETTLE = {0.6: 34.8, 0.8: 77.1, 1.0: 100.0, 1.2: 100.0}   # measured, fixed topology

def main():
    print("ISO-CURRENT line: L = %g nH * (dV/%.1f)^2, so peak current is held ~constant" % (L_REF, DV_REF))
    print("(the fixed-L sweep was resonance-limited: t = pi*sqrt(LC), amplitude-independent)\n")
    print("   dV   L(nH) | t_ZCS  I_pk  | V_Bend | E_hop  per-gate | settle | vs dV=1.2")
    print("  (V)         |  (ps)  (uA)  |   (V)  |  (fJ)    (fJ)   |  (%)   | speed  energy")
    rows, ref = [], None
    for dv in DVS:
        l_nh = L_REF * (dv/DV_REF)**2
        hg.DV = dv
        hg.VCHK = [round(x*dv, 4) for x in (0.167, 0.333, 0.5, 0.667, 0.833, 0.917, 1.0)]
        cal, err = hg.calib()
        if cal is None:
            print("  %.2f  %6.1f | CALIB FAILED: %s" % (dv, l_nh, err)); continue
        c_eff = (cal["QTOT"]/dv)*1e15
        curve = [(v, cal["E%03d" % int(round(v*1000))]*1e15)
                 for v in hg.VCHK if "E%03d" % int(round(v*1000)) in cal]
        def e_st(v, curve=curve):
            if v <= curve[0][0]: return curve[0][1]*(v/curve[0][0])**2 if curve[0][0] else 0.0
            for (v1,e1),(v2,e2) in zip(curve, curve[1:]):
                if v <= v2: return e1 + (e2-e1)*(v-v1)/(v2-v1)
            return curve[-1][1]*(v/curve[-1][0])**2
        tag = "iso%03d" % int(dv*1000)
        tz = hg.probe_zero(tag+"_p.cir", l_nh, c_eff)
        if tz is None:
            print("  %.2f  %6.1f | no current zero" % (dv, l_nh)); continue
        g, err = hg.hop_deck(tag+"_h.cir", l_nh, c_eff, tz)
        if g is None:
            print("  %.2f  %6.1f | HOP FAILED: %s" % (dv, l_nh, err)); continue
        va, vb = g.get("VAEND",0.0), g.get("VBEND",0.0)
        eout = 0.5*(c_eff*1e-15)*(dv*dv - va*va)*1e15
        ehop = eout - e_st(max(vb,0.0))
        ipk  = g.get("IPK",0.0)*1e6
        r = dict(dV=dv, L_nH=round(l_nh,1), t_zcs_ps=round(tz,2), Ipk_uA=round(ipk,2),
                 C_eff_fF=round(c_eff,3), V_A_end=round(va,5), V_B_end=round(vb,5),
                 E_hop_fJ=round(ehop,4), E_hop_per_gate_fJ=round(ehop/hg.MGATE,5),
                 settling_pct=SETTLE[dv], valid=SETTLE[dv] >= 90)
        if dv == DV_REF: ref = r
        rows.append(r)
        sp = en = ""
        if ref:
            sp = "%.2fx" % (ref["t_zcs_ps"]/tz)
            en = "%.2fx" % (ref["E_hop_per_gate_fJ"]/(ehop/hg.MGATE))
        print("  %.2f  %6.1f | %5.1f %6.1f | %6.3f | %6.3f %7.4f | %5.1f  | %-6s %s%s"
              % (dv, l_nh, tz, ipk, vb, ehop, ehop/hg.MGATE, SETTLE[dv], sp, en,
                 "" if SETTLE[dv] >= 90 else "   <- INVALID"))
    json.dump({"_doc": "Iso-current swing sweep: L scaled as dV^2 to hold peak current constant, so "
                       "the hop becomes CURRENT-limited and t ~ dV (the user's argument). The earlier "
                       "fixed-L sweep was RESONANCE-limited, t = pi*sqrt(LC), amplitude-independent, "
                       "which is why it showed a flat 3% span and wrongly suggested swing buys no "
                       "speed. Usable range is bounded below by the measured functional cliff: gate "
                       "settling 34.8% at dV=0.6, 77.1% at 0.8, 100% at 1.0 and 1.2.",
               "dV_ref": DV_REF, "L_ref_nH": L_REF, "rows": rows},
              open("qal_isocurrent.json","w"), indent=1)
    print("\nwrote qal_isocurrent.json")
    ok = [r for r in rows if r["valid"]]
    if len(ok) >= 2 and ref:
        b = min(ok, key=lambda r: r["E_hop_per_gate_fJ"])
        print("  best VALID point: dV=%.1f, L=%.0f nH -> %.1f ps, %.4f fJ/gate"
              % (b["dV"], b["L_nH"], b["t_zcs_ps"], b["E_hop_per_gate_fJ"]))
        print("  vs dV=1.2/L=400: %.2fx faster AND %.2fx cheaper"
              % (ref["t_zcs_ps"]/b["t_zcs_ps"], ref["E_hop_per_gate_fJ"]/b["E_hop_per_gate_fJ"]))

if __name__ == "__main__":
    main()
