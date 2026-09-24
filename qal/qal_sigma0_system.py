#!/usr/bin/env python3
"""QAL system-level (v2): SHA-256 sigma0 datapath, baseline-QAL vs CMOS -- REDONE for the
bank / switched-inductor architecture (user-specified), replacing the v1 "separate generator +
32 per-gate freezes" model. Designed + fairness-checked as a workflow; corrected twice by the user.

ARCHITECTURE (as specified):
 * BANKS of gates, each with its own Vdd rail. An inter-bank SWITCHED INDUCTOR transfers the rail
   charge (POWER) forward bank->bank, cycling zero-current->zero-current (ZCS, one LC half-cycle);
   the data advances through the logic in lockstep. NO separate power resonator -- the inductor IS the
   power delivery. L is layout-tuned so T_half=pi*sqrt(L*C_bank) = a fixed switch time; balancing the
   bank capacitance keeps every bank on that one period (within the +/-14ps freeze window, A1f).
 * A small PHASE/ANTIPHASE RESONATOR drives the inductor-switch GATES (2-phase, complementary), so the
   switch-control (gate-drive) energy is RECOVERED, not dumped as a per-cycle clock tax. Its period sets
   the fixed T_half.
 * Flycaps top up the per-hop I^2R loss (the only net energy input; not additive overhead).

*** THE KEY HONEST CORRECTION (v1 -> v2), and why last-turn's "15-40x" was too rosy: the inductor
recovers the RAIL/SUPPLY energy efficiently (pi/Q) -- that is the clock-elimination win. But the GATE
LOGIC still SETTLES RESISTIVELY, charging its output through the gate's own on-resistance as the rail
ramps: loss = ~2*(RC_g/T)*(1/2 C_g dV^2), adiabatic ONLY for T>>RC_g. With RC_g~12ps (2fF, few-kohm),
the gates need T>~3*RC_g~36ps just to SETTLE, and full adiabatic needs T>~150ps (SLOWER than CMOS's
84ps). So the gate-level saving is SPEED-ENERGY-TRADED, not free -- the inductor's fast low-loss is for
the POWER RAIL, not the gate logic. Net: the big QAL win is CLOCK/RAIL RECOVERY + swing (regimes A/B/C);
the pure gate-level adiabatic edge (regime D) is ~4-5x at gate-RC-limited speed, ~17x only if slowed.

STRUCTURE (A0): 61 XOR2, depth 2 -> 2 gate-banks (2 XOR levels), N_bank_bd=2 inter-bank transfers.
GROUNDED: E_clk=0.0282pJ/DFF, E_logic=0.0076pJ/cell, k=1.25, t_XOR2=84ps (anchor); pi/Q=2.5% inductive
rail transfer (A1f); resistive gate settle 2*(RC/T)*C*dV^2 (A1b); C_g=2fF, RC_g~12ps.
PROVENANCE: hop/settle terms measured single-stage-ideal (A1b/A1f); bank C, resonator Q, chain, reset
MODELED -> PROJECTION pending Track C. A2 per-hop energy quarantined.
"""
# ---- shared ----
N_XOR2, DEPTH, N_BANK_BD = 61, 2, 2
C_g, RC_g, C_bank = 2e-15, 12e-12, 80e-15
Vdd, dV, alpha = 1.2, 0.6, 0.5
E_clk, E_logic, k_size = 0.0282e-12, 0.0076e-12, 1.25
t_XOR2, t_reg = 84e-12, 108e-12
piQ = 0.025            # inductive rail-transfer loss fraction (A1f, good L / R<=10ohm)
Q_res = 0.05           # phase/antiphase switch-drive resonator loss fraction (modeled)
def halfCV2(C,V): return 0.5*C*V*V

# ---- CMOS ----
def cmos(n_ff, V):
    s=(V/Vdd)**2
    Esw=alpha*N_XOR2*E_logic*k_size*s
    Eck=n_ff*E_clk*s
    return Esw+Eck
def cmos_fmax(V):
    Vt=0.4; slow=(V/(V-Vt)**2)/(Vdd/(Vdd-Vt)**2)
    return 1.0/((DEPTH*t_XOR2+t_reg)*slow)

# ---- QAL (bank / switched-inductor) ----
def qal(T):
    E_rail = N_BANK_BD*piQ*halfCV2(C_bank,dV)              # inter-bank inductor recovers rail to pi/Q
    f_adia = min(2*RC_g/T, 1.0)                            # gate settles RESISTIVELY; adiabatic iff T>>RC_g
    E_gate = N_XOR2*f_adia*halfCV2(C_g,dV)                 # the speed-energy-traded term (dominant)
    E_sw   = N_BANK_BD*Q_res*halfCV2(C_g,dV)               # phase/antiphase resonant switch drive (recovered)
    return E_rail+E_gate+E_sw
def qal_fmax(T): return 1.0/(DEPTH*2*T)

if __name__=="__main__":
    p=lambda J: J*1e12
    T_fast=36e-12   # gate-RC-limited (T~3*RC_g, gates just settle) -> fastest valid
    T_slow=150e-12  # deep-adiabatic (T>>RC_g) -> lowest gate energy, but slow
    Ef,Es=qal(T_fast),qal(T_slow)
    print("="*80); print("QAL sigma0 vs CMOS (v2: bank/switched-inductor arch) -- fair energy/throughput"); print("="*80)
    print("  CMOS: 64FF=%.2f 32FF=%.2f 0FF=%.3f pJ @1.2V (%.2f GHz); 0FF@0.6V=%.3f pJ (%.2f GHz)"%(
        p(cmos(64,1.2)),p(cmos(32,1.2)),p(cmos(0,1.2)),cmos_fmax(1.2)/1e9,p(cmos(0,0.6)),cmos_fmax(0.6)/1e9))
    print("  QAL breakdown @T=%dps: rail=%.2f gate=%.2f sw=%.3f fJ (gate = RESISTIVE settle, dominant)"%(
        T_fast*1e12, p(N_BANK_BD*piQ*halfCV2(C_bank,dV))*1e3, p(N_XOR2*min(2*RC_g/T_fast,1)*halfCV2(C_g,dV))*1e3, p(N_BANK_BD*Q_res*halfCV2(C_g,dV))*1e3))
    print("  QAL fast (T=36ps, gate-RC-limited): %.3f pJ @ %.1f GHz"%(p(Ef),qal_fmax(T_fast)/1e9))
    print("  QAL slow (T=150ps, deep-adiabatic):  %.3f pJ @ %.1f GHz"%(p(Es),qal_fmax(T_slow)/1e9))
    print("-"*80)
    print("  FOUR REGIMES (ratio = CMOS / QAL-fast):")
    print("   A naive/rigged (64FF 1.2V):        %.2f / %.3f = %.0fx  [unfair]"%(p(cmos(64,1.2)),p(Ef),cmos(64,1.2)/Ef))
    print("   B fair-marginal (32FF 1.2V):       %.2f / %.3f = %.0fx  (~90%% no-clock+swing)"%(p(cmos(32,1.2)),p(Ef),cmos(32,1.2)/Ef))
    print("   C iso-swing (32FF 0.6V):           %.3f / %.3f = %.0fx  (mostly no-clock)"%(p(cmos(32,0.6)),p(Ef),cmos(32,0.6)/Ef))
    print("   D iso-swing LOGIC-ONLY (0FF 0.6V): %.3f / %.3f = %.1fx  (pure gate adiabatic, RC-limited)"%(p(cmos(0,0.6)),p(Ef),cmos(0,0.6)/Ef))
    print("     ... same regime D vs QAL-SLOW:   %.3f / %.3f = %.1fx  (deep-adiabatic, but %.1f GHz -- slower)"%(p(cmos(0,0.6)),p(Es),cmos(0,0.6)/Es,qal_fmax(T_slow)/1e9))
    print("-"*80)
    print("  CORRECTED VERDICT: the inter-bank inductor recovers the RAIL/supply energy (the clock-")
    print("  elimination win) -- that drives regimes A/B/C (~19-135x, dominantly no-clock + swing).")
    print("  The GATE logic settles RESISTIVELY (RC_g-limited) -> the pure gate-level adiabatic edge")
    print("  (regime D) is only ~4-5x at gate-RC-limited speed, ~17x if slowed (speed-energy trade).")
    print("  v1's separate generator + 32 freezes were removed (bank arch + resonant switch drive), but")
    print("  the resistive gate-settle floor replaces them -> regime D lands ~same ~5x, for the correct")
    print("  reason. The architecture is cleaner; the gate-level miracle isn't there. PROJECTION (Track C).")
