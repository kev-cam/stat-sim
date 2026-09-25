#!/usr/bin/env python3
"""QAL top-up by a PULSE THROUGH AN INDUCTOR (user's topology; replaces the flying cap).

WHY THIS BEATS A FLYING CAP -- the level mismatch.
A flycap moving charge from the +1.5 V rail into a bank swinging at dV=0.6 V is
CHARGE-CONSERVING: the same dQ leaves the rail at 1.5 V and lands at ~0.6 V, so
(1.5-0.6)*dQ is dissipated regardless of switch quality. For the MEASURED per-hop deficit
(qal_twobank.py: recycle loss 0.405 + topup 0.020 = 0.425 fJ on an 80 fF bank at dV=0.6),
the bank needs dQ = C*dV_deficit = 80f * 8.9m = 0.712 fC; the rail supplies that at 1.5 V
= 1.068 fJ to deliver 0.425 fJ -> ~60% lost to the level mismatch ALONE.

A pulsed inductor with a freewheel path is CHARGE-MULTIPLYING (buck action): the rail
sources current only during t_on, while the bank receives current during t_on AND the
freewheel phase. So Q_rail = D * Q_bank with D = V_bank/V_rail, and the rail pays
V_rail * D * Q_bank = V_bank * Q_bank -- the bank's OWN voltage. The inductor performs the
voltage conversion instead of dissipating it; what remains is I^2R only, which is small
because the currents are microamps.

WHAT IS MEASURED HERE (all from supply-current integrals, no formula constants):
  E_rail   = integral of V_rail * I_rail       (energy actually taken from the +1.5 V rail)
  dE_bank  = 1/2 C (Vf^2 - Vi^2)               (energy actually landed in the bank)
  eta      = dE_bank / E_rail                  (delivery efficiency of the top-up path)
  E_gate   = integral over the switch GATE drivers (the term that may dominate: a w=10um
             gate is ~17 fF; 1.5 V on 17 fF is ~20 fJ, ~46x the 0.43 fJ delivered. These
             switches are PER-BANK, not per-gate, so this cost amortizes over the bank --
             which makes BANK SIZE a first-order energy parameter. The user's optional
             phase/antiphase resonator exists to recover exactly this.)

DESIGN CONSTRAINT THIS EXPLORES. Delivering only ~0.71 fC through a small on-chip inductor
forces picosecond pulses: Q = 1/2*I_p*t_total with I_p = (V_rail-V_bank)*t_on/L and
t_total = t_on/D, so Q ~ t_on^2/L -> t_on ~ sqrt(Q*L). Small Q + small L = unswitchably
short pulse. Relief comes from a BIGGER BANK (more charge per top-up) and a LARGER
inductor, so the sweep covers both.

The bank starts at its post-recycle deficit voltage. That initial charge is NOT counted as
delivered energy -- only the INCREMENT dE_bank is, against the rail energy for the same
window -- so no ideal source is credited (the error in qal_a1f_chain_topup.cir, whose
top-up came from "VTOP top 0 {dV}").
"""
import os, re, subprocess, json, math

XYCE  = "/usr/local/src/xyce-build/src/Xyce"
VA    = "/usr/local/share/xyce/verilog-a/psp103/psp103.va"
MODEL = "/usr/local/src/kestrel/sim/models/sg13g2_psp103_tt.lib"
SHIM  = "/usr/local/src/stat-sim/qal/sg13lv_compat.sp"

VRAIL = 1.5          # V, the PV-cell rail
DV    = 0.6          # V, bank swing
RL    = 10.0         # ohm, inductor series resistance (realistic on-chip)
WSW   = 10.0         # um, switch width (Ron ~ 60 ohm measured at this width)
RHOP  = 0.425/14.4   # MEASURED bank-energy loss per hop (qal_twobank.py) = 2.95%
CGATE = 2.0          # fF per gate of bank capacitance (for per-gate amortization)

# (bank C [fF], inductor L [nH], K stages per top-up) -- t_on is DERIVED, not guessed.
# The top-up need NOT fire on every stage: firing every K stages multiplies the charge per
# pulse by ~K (so t_on relaxes as sqrt(K), since Q ~ t_on^2/L) and amortizes the switch
# gate-drive over K stages. The cost is amplitude DROOP: the wave sags to dV*(1-RHOP)^(K/2)
# before being restored, so K trades against the settling gates' noise margin.
CASES = [
    (80.0,   100.0, 1),    # small bank, per-stage top-up: the tight case
    (80.0,   100.0, 7),    # same bank, top up every 7 stages
    (2000.0, 1000.0, 1),   # big bank (~1000 gates x 2 fF), per-stage
    (2000.0, 1000.0, 7),   # big bank, every 7 stages -> the practical design point
]

def deficit_v(c_ff, k):
    """Bank voltage after K hops of the MEASURED per-hop loss, before the top-up fires.
    E after K hops = E_full*(1-RHOP)^K, and V ~ sqrt(E), so V = dV*(1-RHOP)^(K/2)."""
    return DV * ((1.0 - RHOP) ** (0.5 * k))

def ton_for(c_ff, l_nh, k):
    """DERIVE the on-time needed to deliver the K-hop deficit charge.
    Q = C*(dV - V_deficit); with buck timing t_total = t_on*VR/DV and
    I_p = (VR-DV)*t_on/L, Q = t_on^2*(VR-DV)*VR/(2*L*DV) -> t_on = sqrt(2*L*DV*Q/((VR-DV)*VR)).
    This is the constraint that makes a SMALL bank with a SMALL inductor unswitchable."""
    q = (c_ff * 1e-15) * (DV - deficit_v(c_ff, k))
    return math.sqrt(2.0 * (l_nh*1e-9) * DV * q / ((VRAIL - DV) * VRAIL)) * 1e12   # ps

def deck(c_ff, l_nh, k):
    ton_ps = ton_for(c_ff, l_nh, k)
    vi = deficit_v(c_ff, k)
    t0    = 100.0                     # ps, settle before the pulse
    tfw   = ton_ps * (VRAIL/DV - 1.0) # freewheel time so D = V_bank/V_rail
    tend  = t0 + ton_ps + tfw + 400.0
    # gate drives: high-side pMOS active-LOW during t_on; freewheel nMOS active-HIGH after
    L = ['* QAL top-up by a PULSE THROUGH AN INDUCTOR (buck action, no flying cap)',
         '.hdl "%s"' % VA, '.include "%s"' % MODEL, '.include "%s"' % SHIM,
         '.OPTIONS TIMEINT METHOD=GEAR RELTOL=1e-6 ABSTOL=1e-15 CHGTOL=1e-17',
         '.param VR=%g CB=%gf LT=%gn RS=%g VI=%.6f' % (VRAIL, c_ff, l_nh, RL, vi),
         'VRAIL rail 0 {VR}',
         # high-side pMOS: ON (gate low) from t0 for t_on
         'VGP gp 0 PWL(0 {VR} %gp {VR} %gp 0 %gp 0 %gp {VR})'
             % (t0-2, t0, t0+ton_ps, t0+ton_ps+2),
         # synchronous freewheel nMOS: ON (gate high) during the freewheel phase
         'VGN gn 0 PWL(0 0 %gp 0 %gp {VR} %gp {VR} %gp 0)'
             % (t0+ton_ps, t0+ton_ps+2, t0+ton_ps+tfw, t0+ton_ps+tfw+2),
         'XSW  sa gp rail rail sg13_lv_pmos w=%gu l=0.13u' % WSW,   # rail -> sa
         'XFW  sa gn 0    0    sg13_lv_nmos w=%gu l=0.13u' % WSW,   # sa  -> gnd (freewheel)
         'LT sa mid {LT}', 'RT mid bank {RS}',
         'CB bank 0 {CB}',
         # energy taken FROM the rail, and the two switch GATE drives
         'Bpr pr 0 V={ -V(rail)*I(VRAIL) }',
         'Bpg pg 0 V={ -V(gp)*I(VGP) - V(gn)*I(VGN) }',
         '.ic V(bank)={VI}',
         '.tran 0.05p %gp' % tend,
         '.measure tran ERAIL INTEGRAL V(pr) FROM=0 TO=%gp' % tend,
         '.measure tran EGATE INTEGRAL V(pg) FROM=0 TO=%gp' % tend,
         '.measure tran VBI  FIND V(bank) AT=%gp' % (t0-5),
         '.measure tran VBF  MAX V(bank) FROM=%gp TO=%gp' % (t0+ton_ps, tend),
         '.measure tran IPK  MAX I(LT) FROM=0 TO=%gp' % tend,
         '.end']
    return "\n".join(L) + "\n", vi, tfw

def run(tag, txt):
    fn = "pt_%s.cir" % tag
    open(fn, "w").write(txt)
    env = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS")
    try:
        o = subprocess.run([XYCE, fn], capture_output=True, text=True,
                           timeout=420, env=env).stdout
    except subprocess.TimeoutExpired:
        return None, "TIMEOUT"
    g = {}
    for k in ("ERAIL","EGATE","VBI","VBF","IPK"):
        m = re.search(r"^%s\s*=\s*(\S+)" % k, o, re.M)
        if m:
            try: g[k] = float(m.group(1))
            except ValueError: pass
    if "ERAIL" not in g:
        err = "\n".join(l for l in o.splitlines() if "rror" in l or "bort" in l)[:300]
        return None, (err or "no measures")
    return g, None

def main():
    print("QAL top-up via a PULSE THROUGH AN INDUCTOR (SG13G2/PSP103, rail=%.1fV, dV=%.1fV)"
          % (VRAIL, DV))
    print("flying-cap reference for the SAME delivery: charge-conserving 1.5V->0.6V loses")
    print("  (1.5-0.6)/1.5 = 60%% of the rail energy to the level mismatch alone.\n")
    print(" Cbank    L    K  t_on droop |  dE_bank  E_rail   eta  | E_gate  per-gate-per-stage")
    print("  (fF)  (nH)      (ps)  (%)  |    (fJ)     (fJ)   (%)  |  (fJ)        (fJ)")
    rows = []
    for (cb, ln, k) in CASES:
        txt, vi, tfw = deck(cb, ln, k)
        ton = ton_for(cb, ln, k)
        g, err = run("c%g_l%g_k%d" % (cb, ln, k), txt)
        if g is None:
            print("  %5g %5g %3d %5.1f      |  FAILED: %s" % (cb, ln, k, ton, err)); continue
        c = cb * 1e-15
        vbi, vbf = g.get("VBI", vi), g.get("VBF", vi)
        de = 0.5 * c * (vbf*vbf - vbi*vbi) * 1e15      # fJ landed in the bank
        er = g["ERAIL"] * 1e15                          # fJ from the rail
        eg = g.get("EGATE", 0.0) * 1e15                 # fJ of switch gate drive (per pulse)
        eta = (de/er*100.0) if er else 0.0
        ngate = cb / CGATE                              # gates in this bank
        # gate drive amortizes over K stages AND the bank's gates
        eg_per = eg / (k * ngate) if (k and ngate) else 0.0
        droop = (1.0 - vi/DV) * 100.0
        print("  %5g %5g %3d %5.0f %5.1f | %8.3f %8.3f %6.1f | %7.3f   %10.4f"
              % (cb, ln, k, ton, droop, de, er, eta, eg, eg_per))
        rows.append({"Cbank_fF": cb, "L_nH": ln, "K_stages": k, "ton_ps": round(ton,2),
                     "tfw_ps": round(tfw,2), "droop_pct": round(droop,2),
                     "V_init": round(vbi,6), "V_final": round(vbf,6),
                     "dE_bank_fJ": round(de,4), "E_rail_fJ": round(er,4),
                     "eta_pct": round(eta,2), "E_gate_fJ": round(eg,4),
                     "gates_in_bank": ngate,
                     "E_gate_per_gate_per_stage_fJ": round(eg_per,5),
                     "Ipk_uA": round(g.get("IPK",0)*1e6,3)})
    json.dump({"_doc": "QAL top-up delivered by a pulsed inductor (buck action) instead of a "
                       "flying cap. eta = dE_bank/E_rail from supply-current integrals. "
                       "E_gate = switch gate-drive energy, PER BANK (amortizes over the "
                       "bank's gates); the phase/antiphase resonator would recover it. "
                       "Flycap alternative loses ~60% to the 1.5V->0.6V level mismatch.",
               "vrail": VRAIL, "dv": DV, "RL_ohm": RL, "switch_w_um": WSW, "cases": rows},
              open("qal_pulse_topup.json","w"), indent=1)
    print("\nwrote qal_pulse_topup.json")

if __name__ == "__main__":
    main()
