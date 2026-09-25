#!/usr/bin/env python3
"""QAL bank of REAL GATES, charged by a PULSED INDUCTOR with ZCS timing auto-tuned.

Two fixes over qal_pulse_topup.py (which had a lumped capacitor bank and a hand-guessed
disconnect time, giving eta=61.6% with 43 fJ lost to post-transfer ringing):

 1. REAL GATES IN THE BANK. The bank node IS the supply rail of M static CMOS inverters
    (same devices as every other anchor: wp=1.12u, wn=0.74u), each driving a real 2 fF
    load, inputs held valid from a notional previous stage. As the bank rail ramps the
    gates SETTLE to their logic values -- the user's "settle, don't switch". pMOS bulk is
    tied to the bank node (source and bulk together: no body effect, and no second supply
    port to leak energy into the accounting).
 2. ZCS TIMING AUTO-TUNED, not guessed. Pass 1 runs with no disconnect and measures the
    inductor-current zero crossing with '.measure tran TZ WHEN I(LT)=0 CROSS=...'. Pass 2
    opens a series disconnect switch AT that measured time. Hand-picking the time made
    things WORSE before (129 fJ vs 112 fJ) because the switch opened with current still
    flowing; this closes that loop with a measurement.

ENERGY ACCOUNTING -- how dissipation is obtained without knowing the bank capacitance.
A very slow ramp is the adiabatic limit: dissipation ~ RC/T -> 0, so the rail energy for a
slow ramp IS the stored energy. So:
    PASS 0 (calibration): drive the same bank with an ideal SLOW ramp to dV, measure
            E_slow = integral V*I and Q = integral I. Then E_stored ~= E_slow and the
            bank's effective capacitance C_eff = Q/dV (needed to size the pulse).
    E_diss(pulse) = E_rail + E_gatedrive - E_stored
Every joule is traced to the +1.5 V rail through real switches; no ideal source supplies
the bank in the pulsed runs (the error in qal_a1f_chain_topup.cir, whose top-up came from
"VTOP top 0 {dV}").

The adiabatic SIGNATURE is a sweep of the ramp time: E_diss must FALL as the ramp slows.
That is what distinguishes a measurement from a model that asserts f_adia.
"""
import os, re, subprocess, json, math

XYCE  = "/usr/local/src/xyce-build/src/Xyce"
VA    = "/usr/local/share/xyce/verilog-a/psp103/psp103.va"
MODEL = "/usr/local/src/kestrel/sim/models/sg13g2_psp103_tt.lib"
SHIM  = "/usr/local/src/stat-sim/qal/sg13lv_compat.sp"

VRAIL = 1.5      # V, PV-cell rail
DV    = 0.6      # V, bank swing
RL    = 10.0     # ohm, inductor series R
WSW   = 40.0     # um, power-switch width (Ron ~15 ohm; wider = less I^2R, more gate drive)
WP, WN = 1.12, 0.74     # um, the standard cell devices used by every other anchor
MGATE = 8        # gates in the bank
CLOAD = 2.0      # fF load per gate output
ENV   = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS")

def bank(supply="bk"):
    """M static inverters powered from `supply`; half the inputs high, half low, so the
    bank's draw is not a single-input special case. pMOS bulk = supply (no 2nd port)."""
    L = []
    for i in range(MGATE):
        hi = (i % 2 == 0)                      # alternate input levels
        L.append("VI%d in%d 0 %g" % (i, i, DV if hi else 0.0))
        L.append("XP%d o%d in%d %s %s sg13_lv_pmos w=%gu l=0.13u" % (i, i, i, supply, supply, WP))
        L.append("XN%d o%d in%d 0 0 sg13_lv_nmos w=%gu l=0.13u" % (i, i, i, WN))
        L.append("CL%d o%d 0 %gf" % (i, i, CLOAD))
    return L

def head(extra=()):
    return ['.hdl "%s"' % VA, '.include "%s"' % MODEL, '.include "%s"' % SHIM,
            '.OPTIONS TIMEINT METHOD=GEAR RELTOL=1e-6 ABSTOL=1e-15 CHGTOL=1e-17'] + list(extra)

def run(fn, txt, keys):
    open(fn, "w").write(txt)
    try:
        o = subprocess.run([XYCE, fn], capture_output=True, text=True, timeout=500, env=ENV).stdout
    except subprocess.TimeoutExpired:
        return None, "TIMEOUT"
    g = {}
    for k in keys:
        m = re.search(r"^%s\s*=\s*(\S+)" % k, o, re.M)
        if m:
            try: g[k] = float(m.group(1))
            except ValueError: pass
    if not g:
        err = "; ".join(l.strip() for l in o.splitlines() if "rror" in l or "bort" in l)[:250]
        return None, (err or "no measures")
    return g, None

# ---------------- PASS 0: slow-ramp calibration -> E_stored and C_eff ----------------
def calib(tramp_ns=20.0):
    t = tramp_ns * 1000.0      # ps
    L = head() + ['VS bk 0 PWL(0 0 %gp %g)' % (t, DV)] + bank() + [
        'Bp p 0 V={ -V(bk)*I(VS) }', 'Bq q 0 V={ -I(VS) }',
        '.tran %gp %gp' % (t/4000.0, t*1.05),
        '.measure tran ESLOW INTEGRAL V(p) FROM=0 TO=%gp' % t,
        '.measure tran QTOT  INTEGRAL V(q) FROM=0 TO=%gp' % t,
        '.end']
    return run("bg_calib.cir", "\n".join(L)+"\n", ("ESLOW","QTOT"))

# ---------------- pulsed-inductor charge of the gate bank ----------------
def pulse_deck(fn, l_nh, ton_ps, c_eff_ff, tzero_ps=None):
    t0   = 100.0
    tfw  = ton_ps * (VRAIL/DV - 1.0)
    tend = t0 + ton_ps + tfw + 600.0
    dc   = []
    if tzero_ps is None:          # pass 1: no disconnect, just find the current zero
        node_out = "bk"
        meas_tz  = ['.measure tran TZ WHEN I(LT)=0 CROSS=2']
    else:                          # pass 2: series disconnect opened AT the measured zero
        node_out = "dcn"
        dc = ['VGDC gdc 0 PWL(0 {VR} %gp {VR} %gp 0)' % (tzero_ps-2, tzero_ps+2),
              'XDC dcn gdc bk 0 sg13_lv_nmos w=%gu l=0.13u' % WSW]
        meas_tz = []
    gdrv = "-V(gp)*I(VGP) - V(gn)*I(VGN)" + (" - V(gdc)*I(VGDC)" if tzero_ps else "")
    L = head() + [
        '.param VR=%g LT=%gn RS=%g' % (VRAIL, l_nh, RL),
        'VRAIL rail 0 {VR}',
        'VGP gp 0 PWL(0 {VR} %gp {VR} %gp 0 %gp 0 %gp {VR})' % (t0-2, t0, t0+ton_ps, t0+ton_ps+2),
        'VGN gn 0 PWL(0 0 %gp 0 %gp {VR} %gp {VR} %gp 0)'
            % (t0+ton_ps, t0+ton_ps+2, t0+ton_ps+tfw, t0+ton_ps+tfw+2),
        'XSW sa gp rail rail sg13_lv_pmos w=%gu l=0.13u' % WSW,
        'XFW sa gn 0 0 sg13_lv_nmos w=%gu l=0.13u' % WSW,
        'LT sa mid {LT}', 'RT mid %s {RS}' % node_out,
    ] + dc + bank() + [
        'Bpr pr 0 V={ -V(rail)*I(VRAIL) }',
        'Bpg pg 0 V={ %s }' % gdrv,
        '.tran 0.05p %gp' % tend,
        '.measure tran ERAIL INTEGRAL V(pr) FROM=0 TO=%gp' % tend,
        '.measure tran EGATE INTEGRAL V(pg) FROM=0 TO=%gp' % tend,
        '.measure tran VBF MAX V(bk) FROM=%gp TO=%gp' % (t0, tend),
        '.measure tran VBE FIND V(bk) AT=%gp' % (tend-10),
        '.measure tran IPK MAX I(LT) FROM=0 TO=%gp' % tend,
    ] + meas_tz + ['.end']
    keys = ("ERAIL","EGATE","VBF","VBE","IPK") + (("TZ",) if tzero_ps is None else ())
    return run(fn, "\n".join(L)+"\n", keys)

def ton_for(l_nh, c_eff_ff):
    """on-time to deliver C_eff*dV with buck timing (t_total = t_on*VR/DV)."""
    q = (c_eff_ff*1e-15) * DV
    return math.sqrt(2.0*(l_nh*1e-9)*DV*q/((VRAIL-DV)*VRAIL)) * 1e12

def main():
    print("QAL bank of %d REAL static gates (wp=%.2fu wn=%.2fu, %gfF load each), "
          "pulsed-inductor charge, rail=%.1fV dV=%.1fV, switch w=%gu"
          % (MGATE, WP, WN, CLOAD, VRAIL, DV, WSW))

    g, err = calib()
    if g is None:
        print("CALIBRATION FAILED: %s" % err); return
    e_stored = g["ESLOW"]*1e15
    q_tot    = g["QTOT"]
    c_eff    = (q_tot/DV)*1e15
    print("\nPASS 0 slow-ramp calibration (20 ns, adiabatic limit):")
    print("  E_slow (= E_stored) = %.3f fJ ; Q = %.3f fC ; C_eff = %.2f fF"
          % (e_stored, q_tot*1e15, c_eff))
    print("  hard-switch reference 1/2 C_eff dV^2 = %.3f fJ" % (0.5*c_eff*1e-15*DV*DV*1e15))

    print("\nPASS 1/2 pulsed inductor, ZCS auto-tuned. E_diss = E_rail + E_gate - E_stored")
    print("    L     t_on |  TZ(ps) | E_rail  E_gate  V_bk  | E_diss  per-gate | vs 1/2CV^2")
    print("  (nH)    (ps) |         |  (fJ)    (fJ)   (V)   |  (fJ)     (fJ)   |    (x)")
    rows = []
    for l_nh in (100.0, 470.0, 1000.0):
        ton = ton_for(l_nh, c_eff)
        g1, e1 = pulse_deck("bg_p1_l%g.cir" % l_nh, l_nh, ton, c_eff, None)
        if g1 is None:
            print("  %5g %7.1f |  PASS1 FAILED: %s" % (l_nh, ton, e1)); continue
        tz = g1.get("TZ")
        if tz is None:
            print("  %5g %7.1f |  no current zero found (I never crosses) -- skipping ZCS"
                  % (l_nh, ton)); tzp = None
        else:
            tzp = tz*1e12
        g2, e2 = pulse_deck("bg_p2_l%g.cir" % l_nh, l_nh, ton, c_eff, tzp) if tzp else (g1, None)
        if g2 is None:
            print("  %5g %7.1f | %7.1f | PASS2 FAILED: %s" % (l_nh, ton, tzp, e2)); continue
        er, eg = g2["ERAIL"]*1e15, g2.get("EGATE",0.0)*1e15
        ediss  = er + eg - e_stored
        per    = ediss/MGATE
        halfcv = 0.5*c_eff*1e-15*DV*DV*1e15
        print("  %5g %7.1f | %7s | %6.2f %7.2f %5.3f | %6.2f %8.3f | %8.2f"
              % (l_nh, ton, ("%.1f"%tzp) if tzp else "-", er, eg, g2.get("VBE",0),
                 ediss, per, ediss/halfcv if halfcv else 0))
        rows.append({"L_nH": l_nh, "ton_ps": round(ton,2), "tz_ps": round(tzp,2) if tzp else None,
                     "E_rail_fJ": round(er,4), "E_gate_fJ": round(eg,4),
                     "V_bk_end": round(g2.get("VBE",0),4), "V_bk_peak": round(g2.get("VBF",0),4),
                     "E_diss_fJ": round(ediss,4), "E_diss_per_gate_fJ": round(per,4),
                     "Ipk_uA": round(g2.get("IPK",0)*1e6,3)})
    json.dump({"_doc": "QAL bank of real static gates charged by a pulsed inductor with "
                       "ZCS auto-tuned to the measured current zero. E_stored from a slow-ramp "
                       "(adiabatic-limit) calibration of the SAME bank, so no capacitance is "
                       "guessed. E_diss = E_rail + E_gate - E_stored, all traced to the rail.",
               "vrail": VRAIL, "dv": DV, "m_gates": MGATE, "cload_fF": CLOAD,
               "switch_w_um": WSW, "E_stored_fJ": round(e_stored,4),
               "C_eff_fF": round(c_eff,3), "runs": rows},
              open("qal_bank_gates.json","w"), indent=1)
    print("\nwrote qal_bank_gates.json")
    if len(rows) >= 2:
        falls = rows[-1]["E_diss_fJ"] < rows[0]["E_diss_fJ"]
        print("adiabatic signature: E_diss %s as the ramp slows -> %s"
              % ("FALLS" if falls else "does NOT fall",
                 "recovery/settling is real" if falls else "INVESTIGATE (overhead-dominated)"))

if __name__ == "__main__":
    main()
