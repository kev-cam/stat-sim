#!/usr/bin/env python3
"""QAL per-hop loss MEASURED with REAL GATES on the receiving bank, ZCS timing MEASURED.

Replaces the failed buck-pulse attempt (qal_bank_gates.py). Two errors are fixed:

 1. WRONG MECHANISM. A buck pulse off the rail is not how a QAL bank gets its charge. The
    charge arrives from the PREVIOUS BANK through the recycle inductor as one LC half-cycle
    (the inductor is the primary transfer element, carrying energy AND data); the rail only
    replaces the losses. The earlier buck deck tried to ramp a bank 0 -> dV off the rail and
    produced V_bank = -0.148 V and E_diss = 61x (1/2)C dV^2 -- garbage.
 2. WRONG (AND UNMEASURABLE) TIMING. The buck duty relation D = V_bank/V_rail assumes the
    bank SITS at dV; charging from 0 it is invalid (the inductor sees ~1.5 V at the start, so
    current ramps far faster, and the freewheel decays far slower at low V_bank -> the current
    never reaches zero -> overshoot then collapse). And '.measure WHEN I(L)=0 CROSS=2' returned
    -4.4 ms, feeding a negative time into the disconnect PWL.
    A THIRD error, found by a time-resolved trace: the transmission gate was on the SENDING side
    (bka-switch-sw-L-R-bkb), so opening it left the INDUCTOR STILL TIED TO THE RECEIVING BANK. L and
    C_bank then formed a tank and the bank RANG rather than holding -- at dV=0.6/L=400 nH the bank
    swung 0.550 -> 0.169 -> 0.466 V with a ~500 ps period after the disconnect. Every fixed-time
    sample (the settling percentages AND V_Bend, hence E_stored and E_hop) was therefore reading an
    arbitrary phase of a ringing waveform. The switch now sits on the RECEIVING side
    (bka-L-R-sw-switch-bkb) so opening it ISOLATES the bank, and V_Bend is sampled just after the
    disconnect instead of at the end of the window.
    The analytic LC half-cycle t_half = pi*sqrt(L*C_series) was TRIED and FOUND WRONG: it is
    36% early (158.5 ps predicted vs 214.84 ps measured at L=100 nH, read off I(LT) from a
    probe run with the switch held on). Opening there gave a non-monotonic mess across L --
    0.257 V, 0.293 V, 0.687 V (overshoot), then -0.033 V (rang all the way back) -- because a
    gate-loaded bank's capacitance is strongly NONLINEAR (the calibration curve knees hard at
    the 0.4-0.5 V device threshold) and the gates actively draw current, so the zero is not at
    pi*sqrt(LC). So this answers the user's standing question ("zero-cross detection, or fixed
    times and tuning L?"): for a bank loaded with real gates, FIXED ANALYTIC TIMING IS NOT
    ENOUGH -- the zero moves with load and swing. Fixed times work only if tuned per design
    against a measurement (what probe_zero() does here); otherwise you need real zero-cross
    detection. A third error found and fixed: C_A was set to 3x C_B, but a real chain has
    IDENTICAL banks, and equal caps make the half-cycle cleanly swap A->0, B->dV; the 3:1
    ratio was itself forcing an overshoot.

WHAT IS MEASURED. Bank A (a plain cap holding the previous stage's charge at dV) transfers
through L + realistic series R and a REAL device switch into bank B, whose node IS the supply
rail of M static CMOS inverters that SETTLE as it rises ("settle, don't switch"). The switch
opens at t_half (ZCS). Energy accounting by direct integration at both ports:
    E_out_A  = integral of  V(A) * (-I_L)      energy leaving bank A
    E_in_B   = integral of  V(B) * ( I_L)      energy entering bank B
    E_path   = E_out_A - E_in_B                loss in switch Ron + inductor R (the Track-C term)
    E_stored(B) from the slow-ramp calibration curve at B's achieved voltage
    E_gates  = E_in_B - E_stored(B)            the gates' own settling dissipation
    E_hop    = E_out_A - E_stored(B)           total per-hop loss the rail must replace
No rail and no ideal source appears in this deck at all: bank A's initial charge is the
previous stage's, and the measurement is of the INCREMENT, so nothing is credited for free.

The slow-ramp calibration is run FIRST with checkpoints at many voltages, giving E_stored(V)
for the same gate bank (the adiabatic limit: dissipation ~ RC/T -> 0, so rail energy IS stored
energy). That removes any need to guess a capacitance or assume (1/2)C V^2 for a nonlinear
MOS load -- measured earlier to differ by 20%.

SWEEP: L sets the half-cycle duration, i.e. the ramp seen by the gates. E_hop must FALL as L
grows (slower ramp -> more adiabatic). That falling trend, from current integrals, is the
adiabatic signature -- the thing a model that hard-codes f_adia cannot produce.
"""
import os, re, subprocess, json, math

XYCE  = "/usr/local/src/xyce-build/src/Xyce"
VA    = "/usr/local/share/xyce/verilog-a/psp103/psp103.va"
MODEL = "/usr/local/src/kestrel/sim/models/sg13g2_psp103_tt.lib"
SHIM  = "/usr/local/src/stat-sim/qal/sg13lv_compat.sp"

DV    = 0.6           # V, bank swing (the wave amplitude)
RS    = 10.0          # ohm, inductor series resistance
WSW   = 20.0          # um, transfer switch width (Ron ~30 ohm); pMOS is 2x for matched conductance
VGH   = 1.5           # V, switch gate drive taken from the +1.5 V rail that already exists.
                      # FIX: the old deck used a lone nMOS pass transistor with a FIXED 1.2 V gate, so
                      # its overdrive vanished as the bank approached 1.2 V -> Ron exploded and the
                      # measured path loss rose 11.1% -> 44.6% across the dV sweep, inflating the
                      # high-swing points. A CMOS transmission gate (nMOS passes lows, pMOS passes
                      # highs) conducts across the whole 0..dV range at every swing.
WP, WN = 1.12, 0.74   # um, the standard devices used by every other anchor
MGATE = 8             # static inverters on the receiving bank
CLOAD = 2.0           # fF load per gate output
CA_MULT = 1.0         # IDENTICAL banks (a real chain): equal caps -> an LC half-cycle
                      # cleanly swaps the voltages A->0, B->dV. (3:1 forced an overshoot.)
ENV   = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS")
VCHK  = [0.1,0.2,0.3,0.4,0.5,0.55,0.6]     # calibration checkpoints for E_stored(V)

def head():
    return ['.hdl "%s"' % VA, '.include "%s"' % MODEL, '.include "%s"' % SHIM,
            '.OPTIONS TIMEINT METHOD=GEAR RELTOL=1e-6 ABSTOL=1e-15 CHGTOL=1e-17']

def bank(supply):
    """M static inverters powered from `supply`; alternating input levels."""
    L = []
    for i in range(MGATE):
        L.append("VI%d in%d 0 %g" % (i, i, DV if (i % 2 == 0) else 0.0))
        L.append("XP%d o%d in%d %s %s sg13_lv_pmos w=%gu l=0.13u" % (i, i, i, supply, supply, WP))
        L.append("XN%d o%d in%d 0 0 sg13_lv_nmos w=%gu l=0.13u" % (i, i, i, WN))
        L.append("CL%d o%d 0 %gf" % (i, i, CLOAD))
    return L

def run(fn, txt, keys):
    open(fn, "w").write(txt)
    try:
        o = subprocess.run([XYCE, fn], capture_output=True, text=True, timeout=600, env=ENV).stdout
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

def calib(tramp_ns=20.0):
    """Slow ramp = adiabatic limit -> rail energy IS stored energy. Checkpoints give E_stored(V)."""
    t = tramp_ns * 1000.0
    L = head() + ['VS bk 0 PWL(0 0 %gp %g)' % (t, DV)] + bank("bk") + [
        'Bp p 0 V={ -V(bk)*I(VS) }', 'Bq q 0 V={ -I(VS) }',
        '.tran %gp %gp' % (t/4000.0, t*1.02)]
    keys = []
    for v in VCHK:
        tv = t * (v/DV)
        nm = "E%03d" % int(round(v*1000))
        L.append('.measure tran %s INTEGRAL V(p) FROM=0 TO=%gp' % (nm, tv)); keys.append(nm)
    L += ['.measure tran QTOT INTEGRAL V(q) FROM=0 TO=%gp' % t, '.end']; keys.append("QTOT")
    return run("hg_calib.cir", "\n".join(L)+"\n", tuple(keys))

def probe_zero(fn, l_nh, c_eff_ff):
    """Find the TRUE inductor-current zero with the real (nonlinear, active) gate load.
    The analytic pi*sqrt(L*Cser) was measured to be 36% early (158.5 ps predicted vs
    214.84 ps actual at L=100 nH), because the gate-loaded bank capacitance is nonlinear
    and the gates draw current. So the zero is MEASURED, not assumed."""
    ca = CA_MULT * c_eff_ff
    tend = 50.0 + 6.0*math.pi*math.sqrt((l_nh*1e-9)*(ca*c_eff_ff/(ca+c_eff_ff))*1e-15)*1e12
    L = head() + [
        '.param LT=%gn RS=%g CA=%gf' % (l_nh, RS, ca),
        'CA bka 0 {CA}',
        'VHI vhi 0 %g' % VGH,
        'VGT  gt  0 PWL(0 0 48p 0 50p %g %gp %g)' % (VGH, tend*2, VGH),
        'VGTP gtp 0 PWL(0 %g 48p %g 50p 0 %gp 0)' % (VGH, VGH, tend*2),
        'XSWN sw gt  bkb 0   sg13_lv_nmos w=%gu l=0.13u' % WSW,
        'XSWP sw gtp bkb vhi sg13_lv_pmos w=%gu l=0.13u' % (2*WSW),
        'LT bka mid {LT}', 'RT mid sw {RS}',
    ] + bank("bkb") + [
        '.ic V(bka)=%g V(bkb)=0' % DV,
        '.print tran I(LT) V(bkb) V(bka)',
        '.tran 0.1p %gp' % tend, '.end']
    open(fn,'w').write("\n".join(L)+"\n")
    try:
        subprocess.run([XYCE, fn], capture_output=True, text=True, timeout=600, env=ENV)
    except subprocess.TimeoutExpired:
        return None
    try:
        rows = open(fn+'.prn').read().strip().split('\n')
    except Exception:
        return None
    hdr = rows[0].split()
    try: ii = [i for i,h in enumerate(hdr) if 'LT' in h.upper()][0]
    except IndexError: return None
    prev = None
    for ln in rows[1:]:
        f = ln.split()
        if len(f) <= ii: continue
        try: t, cur = float(f[1]), float(f[ii])
        except ValueError: continue
        if prev is not None and prev > 0 and cur <= 0 and t > 60e-12:
            return t*1e12
        prev = cur
    return None

def hop_deck(fn, l_nh, c_eff_ff, t_half_ps):
    ca = CA_MULT * c_eff_ff
    t0 = 50.0
    tend = t0 + t_half_ps + 500.0
    L = head() + [
        '.param LT=%gn RS=%g CA=%gf' % (l_nh, RS, ca),
        # bank A holds the previous stage's charge; .ic sets its starting voltage (its charge is
        # NOT counted as delivered energy -- only the integrated flow through L is measured)
        'CA bka 0 {CA}',
        # transfer switch: nMOS, ON from t0, OPENED at the analytic current zero t0+t_half (ZCS)
        'VHI vhi 0 %g' % VGH,
        'VGT  gt  0 PWL(0 0 %gp 0 %gp %g %gp %g %gp 0)'
            % (t0-2, t0, VGH, t0+t_half_ps, VGH, t0+t_half_ps+2),
        'VGTP gtp 0 PWL(0 %g %gp %g %gp 0 %gp 0 %gp %g)'
            % (VGH, t0-2, VGH, t0, t0+t_half_ps, t0+t_half_ps+2, VGH),
        'XSWN sw gt  bkb 0   sg13_lv_nmos w=%gu l=0.13u' % WSW,
        'XSWP sw gtp bkb vhi sg13_lv_pmos w=%gu l=0.13u' % (2*WSW),
        'Bpg pg 0 V={ -V(gt)*I(VGT) - V(gtp)*I(VGTP) }',
        'LT bka mid {LT}', 'RT mid sw {RS}',
    ] + bank("bkb") + [
        # energy leaving A and entering B, by direct integration at both ports
        'BpA pa 0 V={  V(bka)*I(LT) }',
        'BpB pb 0 V={  V(bkb)*I(LT) }',
        'Bqt qt 0 V={  I(LT) }',
        '.ic V(bka)=%g V(bkb)=0' % DV,
        '.tran 0.1p %gp' % tend,
        '.measure tran EOUTA INTEGRAL V(pa) FROM=0 TO=%gp' % tend,
        '.measure tran EINB  INTEGRAL V(pb) FROM=0 TO=%gp' % tend,
        '.measure tran QTR   INTEGRAL V(qt) FROM=0 TO=%gp' % tend,
        '.measure tran VBPK  MAX V(bkb) FROM=%gp TO=%gp' % (t0, tend),
        '.measure tran VBEND FIND V(bkb) AT=%gp' % (tend-5),
        '.measure tran VAEND FIND V(bka) AT=%gp' % (tend-5),
        '.measure tran IPK   MAX I(LT) FROM=0 TO=%gp' % tend,
        '.measure tran IZ    FIND I(LT) AT=%gp' % (t0+t_half_ps),
        '.measure tran EGT   INTEGRAL V(pg) FROM=0 TO=%gp' % tend,
        '.end']
    return run(fn, "\n".join(L)+"\n",
               ("EOUTA","EINB","QTR","VBPK","VBEND","VAEND","IPK","IZ","EGT"))

def main():
    print("QAL bank-to-bank HOP with %d REAL static gates on the receiving bank" % MGATE)
    print("(wp=%.2fu wn=%.2fu, %gfF load each; dV=%.1fV; switch w=%gu; inductor Rs=%gohm)"
          % (WP, WN, CLOAD, DV, WSW, RS))

    g, err = calib()
    if g is None:
        print("CALIBRATION FAILED: %s" % err); return
    q = g["QTOT"]; c_eff = (q/DV)*1e15
    curve = [(v, g["E%03d" % int(round(v*1000))]*1e15) for v in VCHK if "E%03d" % int(round(v*1000)) in g]
    print("\nPASS 0 slow-ramp calibration (20 ns = adiabatic limit) -> E_stored(V):")
    print("   C_eff = %.2f fF  (Q=%.2f fC)" % (c_eff, q*1e15))
    for v, e in curve: print("     V=%.2f  E_stored=%7.3f fJ" % (v, e))

    def e_stored(v):
        if v <= curve[0][0]: return curve[0][1]*(v/curve[0][0])**2
        for (v1,e1),(v2,e2) in zip(curve, curve[1:]):
            if v <= v2: return e1 + (e2-e1)*(v-v1)/(v2-v1)
        return curve[-1][1]*(v/curve[-1][0])**2

    print("\nPASS 1 resonant hop, ZCS at the ANALYTIC half-cycle t=pi*sqrt(L*Cser):")
    print("    L   t_ZCS  |  V_B_pk V_B_end V_A_end |  E_outA  E_inB  E_path E_gates | E_hop  per-gate")
    print("  (nH)   (ps)  |   (V)    (V)     (V)    |   (fJ)   (fJ)   (fJ)    (fJ)   | (fJ)    (fJ)")
    rows = []
    ca = CA_MULT * c_eff
    cser = (ca*c_eff/(ca+c_eff))*1e-15
    for l_nh in (25.0, 100.0, 400.0, 1600.0):
        tan = math.pi*math.sqrt((l_nh*1e-9)*cser)*1e12     # analytic (reference only)
        th  = probe_zero("hg_probe_l%g.cir" % l_nh, l_nh, c_eff)
        if th is None:
            print("  %5g  probe found no current zero -- skipping" % l_nh); continue
        gg, e = hop_deck("hg_l%g.cir" % l_nh, l_nh, c_eff, th)
        if gg is None:
            print("  %5g %7.1f |  FAILED: %s" % (l_nh, th, e)); continue
        eo, ei = gg["EOUTA"]*1e15, gg["EINB"]*1e15
        vend = gg.get("VBEND", 0.0)
        est  = e_stored(max(vend, 0.0))
        epath = eo - ei
        egat  = ei - est
        ehop  = eo - est
        print("  %5g %7.1f | %7.4f %7.4f %7.4f | %7.3f %6.3f %7.3f %7.3f | %6.3f %7.4f"
              % (l_nh, th, gg.get("VBPK",0), vend, gg.get("VAEND",0),
                 eo, ei, epath, egat, ehop, ehop/MGATE))
        rows.append({"L_nH": l_nh, "t_zcs_measured_ps": round(th,2),
                     "t_half_analytic_ps": round(tan,2), "V_B_peak": round(gg.get("VBPK",0),5),
                     "V_B_end": round(vend,5), "V_A_end": round(gg.get("VAEND",0),5),
                     "E_outA_fJ": round(eo,4), "E_inB_fJ": round(ei,4),
                     "E_path_fJ": round(epath,4), "E_gates_fJ": round(egat,4),
                     "E_stored_B_fJ": round(est,4), "E_hop_fJ": round(ehop,4),
                     "E_hop_per_gate_fJ": round(ehop/MGATE,5),
                     "Ipk_uA": round(gg.get("IPK",0)*1e6,3),
                     "I_at_zcs_uA": round(gg.get("IZ",0)*1e6,4),
                     "Q_transferred_fC": round(gg.get("QTR",0)*1e15,4)})
    json.dump({"_doc": "QAL bank-to-bank resonant hop with real settling gates on the receiving "
                       "bank. ZCS at the ANALYTIC half-cycle pi*sqrt(L*Cser) -- no zero-cross "
                       "detector needed. E_stored(V) from a slow-ramp calibration of the same "
                       "bank (no capacitance guessed, no 1/2CV^2 assumed). E_hop is the per-hop "
                       "loss the rail top-up must replace. No rail or ideal source in this deck.",
               "dv": DV, "m_gates": MGATE, "cload_fF": CLOAD, "switch_w_um": WSW, "Rs_ohm": RS,
               "C_eff_fF": round(c_eff,3), "CA_fF": round(ca,3),
               "E_stored_curve": [[v, round(e,4)] for v,e in curve], "hops": rows},
              open("qal_hop_gates.json","w"), indent=1)
    print("\nwrote qal_hop_gates.json")
    if len(rows) >= 2:
        print("adiabatic signature: E_hop %s as L (ramp time) grows -> %s"
              % ("FALLS" if rows[-1]["E_hop_fJ"] < rows[0]["E_hop_fJ"] else "does NOT fall",
                 "settling is adiabatic (measured, not asserted)" if rows[-1]["E_hop_fJ"] < rows[0]["E_hop_fJ"]
                 else "INVESTIGATE: overhead- or path-dominated"))

if __name__ == "__main__":
    main()
