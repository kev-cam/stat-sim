#!/usr/bin/env python3
"""Does a SWITCHED-CAP BODY-BIAS rail move the QAL functional cliff?

THE PROBLEM IT ATTACKS (all measured):
The lowest-energy, fastest QAL operating point is dV = 0.6 V -- 0.326 fJ/gate-settle and a 325.9 ps
hop, versus 0.429 fJ and 367.5 ps at dV = 0.8. But dV = 0.6 IS FUNCTIONALLY INVALID: the bank rail
only reaches 0.382 V against SG13G2's Vt ~ 0.4 V, so the pMOS never turns on and the gate output
settles to just 64% of the rail (0.244 V on a 0.382 V rail). At dV = 0.8 the rail reaches 0.516 V and
settling is 97.6%. So a device threshold, not the energy target, is what forces the higher swing --
and it costs 1.3x the energy and 13% of the speed.

THE IDEA (user's): "You can use switch-cap to create extra rails as needed, so you can limit the use
to where it's needed." A BODY-BIAS rail is the ideal switched-cap load, because it carries no DC
current at all -- only junction leakage -- so a charge pump supplies it almost for free, unlike a
power rail. Forward-biasing the wells lowers Vt directly, which moves the cliff DOWN instead of paying
for swing. That is "limiting the use to where it's needed" in its purest form: the expensive high
voltage is applied only to the wells, never to the switched capacitance.

HOW IT IS MODELLED. Forward body bias needs the well to sit BELOW the pMOS source, and the pMOS source
here IS the ramping bank node. So the bias rail must RIDE on the bank -- exactly what a flying
switched-cap rail does. That is modelled as a floating source referenced to the bank node:
    VBP nwp <bank> {-VFB}     ->  V(nwp) = V(bank) - VFB      (pMOS well, rides the bank)
    VBN pwn 0     {+VFB}      ->  V(pwn) = +VFB               (nMOS well, referenced to ground)
Its current is measured, so the claim "a switched-cap rail can supply this" is checked rather than
assumed: if the source-bulk junction starts conducting the current will show it.

CAUTION: forward bias beyond roughly 0.5 V turns the source-bulk diode on, which would inject real
current and defeat the point. The sweep deliberately runs past the safe region (0 / 0.2 / 0.3 / 0.4 V)
so the onset is visible in the measured well current rather than assumed.

WHAT IS MEASURED PER POINT:
  V_bank(end), V(o1) -- the gate whose input is LOW, so its pMOS must pull the output up to the rail.
  settling % = V(o1)/V_bank. Below ~90% the gate is not computing.
  I_well on both bias rails -> whether a charge pump could actually supply it.
  E_hop, integral-free, as everywhere else in this campaign:
     E_hop = 1/2*C_A*(V_Ai^2 - V_Af^2) - E_stored_B(V_Bend)
"""
import json, math, os, re, subprocess, sys
sys.path.insert(0, "/usr/local/src/stat-sim/qal")
import qal_hop_gates as hg

DVS  = [0.6, 0.8]                 # the invalid point, and the current best
VFBS = [0.0, 0.2, 0.3, 0.4]       # V of forward body bias (0.4 approaches diode turn-on)
L_NH = 400.0
ORIG = hg.bank

def bank_fbb(vfb):
    """Same bank, but both wells driven by flying bias rails. The pMOS well rides the bank node
    (a switched-cap rail referenced to the supply it biases); the nMOS well is ground-referenced."""
    def f(supply):
        L = ["VBP nwp %s %g" % (supply, -vfb),     # V(nwp) = V(supply) - vfb
             "VBN pwn 0 %g" % vfb]                 # V(pwn) = +vfb
        for i in range(hg.MGATE):
            L.append("VI%d in%d 0 %g" % (i, i, hg.DV if (i % 2 == 0) else 0.0))
            L.append("XP%d o%d in%d %s nwp sg13_lv_pmos w=%gu l=0.13u" % (i, i, i, supply, hg.WP))
            L.append("XN%d o%d in%d 0 pwn sg13_lv_nmos w=%gu l=0.13u" % (i, i, i, hg.WN))
            L.append("CL%d o%d 0 %gf" % (i, i, hg.CLOAD))
        return L
    return f

def hop_with_probes(fn, l_nh, c_eff, tz, vfb):
    """hg.hop_deck + extra measures for settling and well current."""
    g, err = hg.hop_deck(fn, l_nh, c_eff, tz)
    if g is None: return None, err
    txt = open(fn).read().replace(".end",
        ".measure tran O1E  FIND V(o1) AT=%gp\n" % (tz + 400) +
        ".measure tran BKE  FIND V(bkb) AT=%gp\n" % (tz + 400) +
        ".measure tran IWP  AVG I(VBP)\n.measure tran IWN AVG I(VBN)\n.end")
    fn2 = fn.replace(".cir", "_probe.cir")
    open(fn2, "w").write(txt)
    try:
        o = subprocess.run([hg.XYCE, fn2], capture_output=True, text=True,
                           timeout=600, env=hg.ENV).stdout
    except subprocess.TimeoutExpired:
        return g, None
    for k in ("O1E", "BKE", "IWP", "IWN"):
        m = re.search(r"^%s\s*=\s*(\S+)" % k, o, re.M)
        if m:
            try: g[k] = float(m.group(1))
            except ValueError: pass
    return g, None

def main():
    print("Switched-cap BODY-BIAS rail: does it move the QAL functional cliff?")
    print("bank = %d static inverters (wp=%.2fu wn=%.2fu, %gfF load); L = %g nH" %
          (hg.MGATE, hg.WP, hg.WN, hg.CLOAD, L_NH))
    print("the cliff today: dV=0.6 -> rail 0.382 V, settling 64%% (INVALID); "
          "dV=0.8 -> rail 0.516 V, 97.6%%\n")
    print("   dV   V_FB | t_ZCS  V_bank  V(o1) settle | E_hop  per-gate | I_well(pMOS/nMOS)")
    print("  (V)   (V)  |  (ps)    (V)    (V)    (%)  |  (fJ)    (fJ)   |      (A)")
    rows = []
    for dv in DVS:
        hg.DV = dv
        hg.VCHK = [round(x*dv, 4) for x in (0.167, 0.333, 0.5, 0.667, 0.833, 0.917, 1.0)]
        for vfb in VFBS:
            hg.bank = bank_fbb(vfb)
            cal, err = hg.calib()
            if cal is None:
                print("  %.2f  %.2f | CALIB FAILED: %s" % (dv, vfb, err)); continue
            q = cal["QTOT"]; c_eff = (q/dv)*1e15
            curve = [(v, cal["E%03d" % int(round(v*1000))]*1e15)
                     for v in hg.VCHK if "E%03d" % int(round(v*1000)) in cal]
            if not curve:
                print("  %.2f  %.2f | no calibration points" % (dv, vfb)); continue
            def e_st(v, curve=curve):
                if v <= curve[0][0]: return curve[0][1]*(v/curve[0][0])**2 if curve[0][0] else 0.0
                for (v1,e1),(v2,e2) in zip(curve, curve[1:]):
                    if v <= v2: return e1 + (e2-e1)*(v-v1)/(v2-v1)
                return curve[-1][1]*(v/curve[-1][0])**2
            tag = "fbb%03d_%03d" % (int(dv*1000), int(vfb*1000))
            tz = hg.probe_zero(tag + "_p.cir", L_NH, c_eff)
            if tz is None:
                print("  %.2f  %.2f | no current zero" % (dv, vfb)); continue
            g, err = hop_with_probes(tag + "_h.cir", L_NH, c_eff, tz, vfb)
            if g is None:
                print("  %.2f  %.2f | HOP FAILED: %s" % (dv, vfb, err)); continue
            va, vb = g.get("VAEND", 0.0), g.get("VBEND", 0.0)
            eout = 0.5*(c_eff*1e-15)*(dv*dv - va*va)*1e15
            ehop = eout - e_st(max(vb, 0.0))
            o1, bk = g.get("O1E", 0.0), g.get("BKE", vb)
            pct = 100.0*o1/bk if bk else 0.0
            print("  %.2f  %.2f | %6.1f %6.3f %6.3f %6.1f | %6.3f %7.4f | %9.2e / %8.2e"
                  % (dv, vfb, tz, bk, o1, pct, ehop, ehop/hg.MGATE,
                     g.get("IWP", 0.0), g.get("IWN", 0.0)))
            rows.append({"dV": dv, "V_FB": vfb, "t_zcs_ps": round(tz,2),
                         "C_eff_fF": round(c_eff,3), "V_bank": round(bk,5),
                         "V_o1": round(o1,5), "settling_pct": round(pct,2),
                         "E_hop_fJ": round(ehop,4), "E_hop_per_gate_fJ": round(ehop/hg.MGATE,5),
                         "I_well_pmos_A": g.get("IWP"), "I_well_nmos_A": g.get("IWN"),
                         "valid": pct > 90})
    hg.bank = ORIG
    json.dump({"_doc": "Switched-cap forward-body-bias sweep. A body rail draws no DC current (only "
                       "junction leakage) so a charge pump supplies it nearly free -- the measured "
                       "I_well columns test that claim rather than assuming it. The question is "
                       "whether lowering Vt moves the functional cliff below dV=0.8, unlocking the "
                       "cheaper AND faster dV=0.6 operating point (0.326 fJ / 325.9 ps vs 0.429 fJ / "
                       "367.5 ps). Forward bias past ~0.5 V turns on the source-bulk diode; the sweep "
                       "runs to 0.4 V so the onset shows up in I_well.",
               "L_nH": L_NH, "m_gates": hg.MGATE, "rows": rows},
              open("qal_bodybias.json","w"), indent=1)
    print("\nwrote qal_bodybias.json")
    for dv in DVS:
        r = [x for x in rows if x["dV"] == dv]
        if len(r) >= 2:
            print("  dV=%.2f: settling %.1f%% at V_FB=0 -> %.1f%% at V_FB=%.2f  => %s"
                  % (dv, r[0]["settling_pct"], r[-1]["settling_pct"], r[-1]["V_FB"],
                     "CLIFF MOVED, dV=0.6 is now usable" if (dv==0.6 and r[-1]["settling_pct"]>90)
                     else "still below the 90% bar" if dv==0.6 else "already valid"))

if __name__ == "__main__":
    main()
