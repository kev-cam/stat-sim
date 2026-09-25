#!/usr/bin/env python3
"""DECISIVE TEST: does QAL gate settling become adiabatic at higher swing?

THE FINDING THIS TESTS. qal_hop_gates.py measured, on a bank of real settling gates fed by a
resonant bank-to-bank hop, that the gates dissipate E_gates = 4.74-7.23 fJ against
E_stored(full dV) = 7.32 fJ -- i.e. f_adia ~ 0.65-1.0, essentially NO adiabatic saving -- and
that slowing the hop 29x (L = 25 -> 1600 nH) does not reduce it.

THE HYPOTHESIS. At dV = 0.6 V with SG13G2 Vt ~ 0.4 V the gate devices have only ~0.2 V of
overdrive, so their on-resistance is huge and RC_gate exceeds any hop time an on-chip inductor
can produce. If that is the cause, then raising dV (more overdrive -> smaller RC_gate) must make
E_gates/E_stored FALL sharply. If it does not fall, the cause is something else and the
near-threshold story is wrong.

WHY IT MATTERS. The north-star plan wants low power via low swing. But adiabatic settling needs
T >> RC_gate, and lowering the swing toward Vt raises RC_gate. If both cannot hold at once, the
minimum viable swing on this node is set by the device Vt, not by the energy target -- and the
recharge topology (flycap vs pulsed inductor vs series tiers) is optimising a second-order term.

METHOD. For each dV, the whole measurement is redone self-consistently, because nothing here can
be scaled analytically -- the bank capacitance is nonlinear and the gate input levels are dV:
  1. slow-ramp calibration at THIS dV -> E_stored(V) curve + C_eff (the adiabatic limit, so rail
     energy IS stored energy; no capacitance is guessed and 1/2 C V^2 is never assumed)
  2. probe run with the transfer switch held on -> the MEASURED inductor-current zero (the
     analytic pi*sqrt(L*Cser) was measured 1.4-1.9x early for a gate-loaded bank)
  3. hop run with ZCS at that measured zero -> E_outA, E_inB by direct port integration
Two L values per dV so the swing effect is separated from the ramp-time effect.

KEY COLUMN: E_gates / E_stored(full dV). That ratio IS the measured f_adia. It must fall with dV
for the hypothesis to hold.
"""
import json, math, sys
sys.path.insert(0, "/usr/local/src/stat-sim/qal")
import qal_hop_gates as hg

DVS    = [0.6, 0.8, 1.0, 1.2]     # V, bank swing (1.2 = the SG13G2 nominal rail)
LS     = [100.0, 400.0]           # nH, two hop speeds
VT_EST = 0.4                      # V, approximate SG13G2 threshold (for the overdrive column)

def sweep():
    out = []
    print("QAL swing sweep: does gate settling become adiabatic at higher dV?")
    print("bank = %d real static inverters (wp=%.2fu wn=%.2fu, %gfF load each); "
          "switch w=%gu; inductor Rs=%gohm"
          % (hg.MGATE, hg.WP, hg.WN, hg.CLOAD, hg.WSW, hg.RS))
    print("KEY COLUMN is E_gates/E_stored = the MEASURED f_adia; it must FALL with dV\n")
    print("   dV  ovdrv | C_eff  E_stor |    L   t_ZCS  V_Bend |  E_outA  E_path  E_gates | "
          "f_adia  path%   E_swgate")
    print("  (V)   (V)  |  (fF)   (fJ)  | (nH)   (ps)    (V)   |   (fJ)    (fJ)     (fJ)  |   (x)    (%)")
    for dv in DVS:
        hg.DV = dv                                    # re-run everything at this swing
        hg.VCHK = [round(x*dv, 4) for x in (0.167, 0.333, 0.5, 0.667, 0.833, 0.917, 1.0)]
        g, err = hg.calib()
        if g is None:
            print("  %4.2f  CALIBRATION FAILED: %s" % (dv, err)); continue
        q = g["QTOT"]; c_eff = (q/dv)*1e15
        curve = []
        for v in hg.VCHK:
            nm = "E%03d" % int(round(v*1000))
            if nm in g: curve.append((v, g[nm]*1e15))
        if not curve:
            print("  %4.2f  no calibration checkpoints parsed" % dv); continue
        e_full = curve[-1][1]

        def e_stored(v):
            if v <= curve[0][0]: return curve[0][1]*(v/curve[0][0])**2 if curve[0][0] else 0.0
            for (v1,e1),(v2,e2) in zip(curve, curve[1:]):
                if v <= v2: return e1 + (e2-e1)*(v-v1)/(v2-v1)
            return curve[-1][1]*(v/curve[-1][0])**2

        ca   = hg.CA_MULT * c_eff
        for l_nh in LS:
            tz = hg.probe_zero("dv%03d_probe_l%g.cir" % (int(dv*1000), l_nh), l_nh, c_eff)
            if tz is None:
                print("  %4.2f  %5.2f | %6.2f %6.2f | %4g   probe found no current zero"
                      % (dv, dv-VT_EST, c_eff, e_full, l_nh)); continue
            gg, e2 = hg.hop_deck("dv%03d_hop_l%g.cir" % (int(dv*1000), l_nh), l_nh, c_eff, tz)
            if gg is None:
                print("  %4.2f  %5.2f | %6.2f %6.2f | %4g %7.1f  HOP FAILED: %s"
                      % (dv, dv-VT_EST, c_eff, e_full, l_nh, tz, e2)); continue
            eo, ei = gg["EOUTA"]*1e15, gg["EINB"]*1e15
            vend   = gg.get("VBEND", 0.0)
            est    = e_stored(max(vend, 0.0))
            epath  = eo - ei
            egat   = ei - est
            fad    = egat/e_full if e_full else 0.0
            pathp  = 100.0*epath/eo if eo else 0.0
            print("  %4.2f  %5.2f | %6.2f %6.2f | %4g %7.1f %6.3f | %7.3f %7.3f %8.3f | "
                  "%6.3f %6.1f %8.2f"
                  % (dv, dv-VT_EST, c_eff, e_full, l_nh, tz, vend, eo, epath, egat, fad, pathp,
                     gg.get("EGT",0.0)*1e15))
            out.append({"dV": dv, "overdrive_V": round(dv-VT_EST,3),
                        "C_eff_fF": round(c_eff,3), "E_stored_full_fJ": round(e_full,4),
                        "L_nH": l_nh, "t_zcs_ps": round(tz,2),
                        "V_B_end": round(vend,5), "V_B_peak": round(gg.get("VBPK",0),5),
                        "E_outA_fJ": round(eo,4), "E_inB_fJ": round(ei,4),
                        "E_path_fJ": round(epath,4), "E_gates_fJ": round(egat,4),
                        "E_stored_at_Vend_fJ": round(est,4),
                        "E_switch_gate_fJ": round(gg.get("EGT",0.0)*1e15,4),
                        "f_adia_measured": round(fad,4),
                        "path_loss_pct": round(pathp,2),
                        "Ipk_uA": round(gg.get("IPK",0)*1e6,3)})
    return out

def main():
    rows = sweep()
    json.dump({"_doc": "QAL swing sweep. For each dV the slow-ramp calibration, the ZCS probe and "
                       "the hop are ALL redone, because the bank capacitance is nonlinear and the "
                       "gate input levels are dV -- nothing scales analytically. f_adia_measured = "
                       "E_gates/E_stored(full dV) is the measured adiabatic fraction; it must fall "
                       "with dV if the near-threshold (low-overdrive) diagnosis is correct.",
               "vt_est": VT_EST, "m_gates": hg.MGATE, "cload_fF": hg.CLOAD,
               "switch_w_um": hg.WSW, "Rs_ohm": hg.RS, "rows": rows},
              open("qal_dv_sweep.json","w"), indent=1)
    print("\nwrote qal_dv_sweep.json")
    # verdict per L, comparing lowest vs highest dV at the same hop speed
    for l_nh in LS:
        r = [x for x in rows if x["L_nH"] == l_nh]
        if len(r) < 2: continue
        lo, hi = r[0], r[-1]
        print("  L=%gnH: f_adia %.3f at dV=%.2f -> %.3f at dV=%.2f  =>  %s"
              % (l_nh, lo["f_adia_measured"], lo["dV"], hi["f_adia_measured"], hi["dV"],
                 "FALLS: near-threshold diagnosis CONFIRMED" if hi["f_adia_measured"] < 0.8*lo["f_adia_measured"]
                 else "does NOT fall materially: near-threshold diagnosis REJECTED -- look elsewhere"))

if __name__ == "__main__":
    main()
