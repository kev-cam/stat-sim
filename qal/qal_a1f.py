#!/usr/bin/env python3
"""QAL A1f (increment 1) -- flying-cap FORWARD-TRANSFER cell, the patentable core (QAL_PLAN A1f).
Ideal-source Track-A study in Xyce (behavioral B-source switch, ideal linear caps). Designed +
adversarially verified as two workflows. HONEST SCOPE: this increment establishes the charge-share
floor and dual-rail's data-signature suppression; it does NOT yet demonstrate forward-transfer
EFFICIENCY (the ZVS/crossing benefit was not cleanly measured and the finite-RON tracking loss is
unmodeled). See NOT-YET-SHOWN. Anchor discipline: taps validated on an analytic charge-share, never
self-baselined.

Node convention: caps CL=10fF, swing dV=0.6V, R=C_fly/C_L. C_eff for a two-cap share = C1||C2.

=== HAS SHOWN (verified) ===

(1) TAP VALIDATION (b2_share.cir) -- direct C1->C2 hard charge-share, C1=C2=10fF, C1 at 0.6V:
    V_final=0.3000V, E_REL=1.350fJ, E_DEL=0.450fJ, E_SW=0.900fJ, eta_rel=E_DEL/E_REL=0.3333,
    energy balance E_REL-E_DEL-E_SW = 0.0000fJ. Every B-source tap sign is exact.

(2) NO SINGLE-SHOT ENERGY FREE LUNCH (any topology). An abrupt flying-cap transfer costs
    E_SW = 1/2 * C_eff * dV_switch^2, and this is RON-INDEPENDENT (b2 at RON=50 returns
    9.000016e-16 J = 1/2*5fF*0.6^2 to 6 digits; C_eff = C1||C2 = 5fF). The ground-referenced
    PARALLEL single flying-cap dump is algebraically identical to hard charge-share:
      delivered level      k        = R/(1+R)      (0.50 @ R=1, 0.67 @ R=2 -> clears A2's clamp)
      delivered/RELEASED eta        = R/(1+2R)     (= 1/3 @ R=1, matches STEP0; -> 1/2 as R->inf)
    NB [R/(1+R)]^2 is a level^2 / bucket-fullness figure, NOT efficiency. The genuine efficiency
    ceiling -> 1 is NOT reachable by stiffening/slowing the passive dump (its loss is speed- and
    R-independent); it requires ZVS (ramped crossing), resonant L-C, or stepwise distinct levels.
    A series/bootstrapped (Marx/Dickson) reconnection buys LEVEL (boosted > R/(1+R)) but not
    efficiency -- asserted algebraically here, not yet simulated.

(3) DATA-SIGNATURE: a DUAL-RAIL ENCODING property, not a flying-cap one (sr_*, dr_* decks).
    single-rail flying-cap tap: QDEL(data1)=3.0fC / QDEL(data0)=0.0fC  -> 100% data-modulated (worst case)
    dual-rail differential-SUM tap: QDEL=2.0fC / 2.0fC -> 0.00% spread (matched, ideal)
    The flatness is complementary-code symmetry (exactly one 0->dV swing/cycle) and SURVIVES a
    nonlinear MOScap C(V) (C(V) curvature is a red herring). It is a MISMATCH-LIMITED floor, not
    exact zero: ΔC/C of {0.5,1,2,5}% -> spread {0.50,1.00,2.00,5.00}%. For SG13G2 ~10fF caps this is
    ~0.1-few %, i.e. ~30-200x below single-rail. (The flying cap's own contribution is level-shift /
    galvanic isolation -- required for forward transfer -- but it too costs full 1/2 C_eff dV^2.)

(4) CROSSING slack and data-signature are ORTHOGONAL axes: ZVS timing governs 1/2 C dV^2 switching
    ENERGY; the tap CHARGE modulation is separate (lossless switching still leaves single-rail 100%
    modulated). A conservative O(100ps) REDISTRIBUTION-timing tolerance for the RON-independent term:
    ~112-158ps at a 1ns ramp (E_SW < 0.09fJ needs |dV_switch|<0.134V; DVX(t) crosses 0 with slope
    ~1.2V/ns). This bounds ONLY the redistribution term.

=== NOT YET SHOWN (increment 2) ===
 * The ZVS/crossing benefit itself was NEVER cleanly measured -- the pulsed-switch E_SW sweep was
   numerically fragile (hand-rolled clamp conductance: mostly exact-zero reads + two spikes). The ZVS
   claim currently rests on the STEP0 endpoint + algebra alone.
 * The finite-RON TRACKING loss E_track ~ (C_eff*dV/dt)^2 * RON * W_on -- invisible to 1/2CdV^2, scales
   with RON and on-time, does NOT vanish at the crossing. This (an RON*W_on ceiling), not the 112ps,
   is the real gate for a loss<5% / efficiency claim. Unmodeled here.
 * Therefore: NO total-loss / efficiency number, and no forward-transfer "recovery runs with the data"
   energy demonstration. Genuine ceiling->1 (ZVS/resonant/stepwise) not built.
 * Series (Marx/Dickson) level boost vs parallel dump: asserted, not simulated.
 * Dual-rail residual leak under realistic Pelgrom Vt/C mismatch MC: not characterized.

=== INCREMENT-2 RECIPE (from the verify) ===
Build the REAL coupled cell: rails through finite source R, a flying cap, and an ACTUAL receiver C_L
(not a stiff rail); a SMOOTH gate G(t) (raised-cosine/tanh ~20-50ps, or Xyce VSWITCH) replacing the
discontinuous clamp; a loss-integration window that TRACKS TX (or a cumulative integral); one .STEP of
TX across the crossing PLUS independent RON and W_on sweeps; a per-run energy-balance guard
(E_rel-E_del-E_loss=0, discard failing runs). The TX width where cumulative E_loss<0.09fJ, overlaid on
the RON/W_on sweeps, IS the measured tolerance and yields the RON*W_on ceiling -- the real efficiency
gate, tracking loss included, no extrapolation. Commit to ONE topology and ONE C_eff before quoting.
"""
# Baked verified records (see decks b2_share.cir, sr_d1/d0.cir, dr_d1/d0.cir).
STEP0   = dict(Vfinal=0.3000, E_REL_fJ=1.350, E_DEL_fJ=0.450, E_SW_fJ=0.900, eta_rel=1/3, balance_fJ=0.0)
C_EFF_fF, dV = 5.0, 0.6                         # series C1||C2; E_SW = 1/2 C_eff dV^2 = 0.900 fJ (RON-indep)
DATADEP = dict(sr_d1_fC=3.0, sr_d0_fC=0.0, dr_d1_fC=2.0, dr_d0_fC=2.0)   # 100% vs 0.00% (matched)
MISMATCH_floor = {0.5:0.50, 1.0:1.00, 2.0:2.00, 5.0:5.00}               # ΔC/C(%) -> dual-rail spread(%)

def eff(R):                                     # delivered/released energy efficiency of one passive dump
    return R/(1+2*R)
def level(R):                                   # delivered level fraction k
    return R/(1+R)

if __name__=="__main__":
    print("QAL A1f increment 1 -- flying-cap forward transfer (HONEST scope)")
    print("  loss floor  E_SW = 1/2*C_eff*dV^2 = %.3f fJ (C_eff=%.0ffF, RON-INDEPENDENT, verified)"%(
          0.5*C_EFF_fF*1e-15*dV*dV*1e15, C_EFF_fF))
    print("  single-shot: R    level k=R/(1+R)   eff=R/(1+2R)")
    for R in (0.5,1,2,4):
        print("               %-4g  k=%.3f          eff=%.3f"%(R,level(R),eff(R)))
    print("  data-signature: single-rail 100%% modulated (3.0/0.0 fC) vs dual-rail 0.00%% (2.0/2.0 fC),")
    print("                  mismatch-limited (ΔC/C=x%% -> spread x%%), survives nonlinear C(V).")
    print("  NOT YET SHOWN: ZVS benefit (sim was fragile), finite-RON tracking loss, efficiency number.")
