#!/usr/bin/env python3
"""QAL A1f -- multi-stage INDUCTIVE chain: does the wave PROPAGATE and does loss COMPOUND?
Builds on qal_a1f_inductive.py (single-hop resonant transfer). This answers the system question and
REPAIRS A2: the inductive cell cascades where A2's single-rail capacitive source-follower died.

CHAIN (chain6.cir): stages n0..n5 (each C_L=10fF), stage 0 pre-charged to dV=0.6V (data '1').
Between consecutive stages: inductor L=1uH + series R=100 + a FREEZE switch. Hop i (n_i -> n_{i+1})
is enabled over a window [t_i, t_i+T_half] (T_half=222ps, C_eff=5fF), and the freeze switch opens at
t_i+T_half -- the current zero-crossing -- trapping the charge on n_{i+1}. Hops are phased forward
(t_i = T0 + i*period) so the charge/data pattern travels as a front.

--- MEASURED 2026-09-23 (Xyce GEAR, ideal L, R=100 => Q~141) ---
Traveling wave: peak level reached at each stage (bare chain, no top-up):
   n0 0.6000 (source) | n1 0.5966 | n2 0.5933 | n3 0.5900 | n4 0.5867 | n5 0.5834
   => UNIFORM -0.56%/hop droop (I^2R). 97.2% of dV still at stage 5; extrapolates to ~95% at depth 8.
   It is a TRAVELING wave, not fan-out: final V (@1.4ns) is ~0.003V on n0..n4 (they EMPTIED as the
   charge passed forward) and 0.583V only on n5 (holds the delivered data).
   Contrast A2's capacitive single-rail source-follower: -65%/hop, DEAD by hop 2.

Energy conservation (no free-energy trap; the decisive check given the earlier bootstrap trap):
   initial 1/2*C*dV^2 = 1.800 fJ (on n0). final = 1/2*C*(5*0.0033^2 + 0.5834^2) = 1.702 fJ + total
   I^2R loss 0.097 fJ = 1.799 fJ. Conserves to 0.05%. Total 5-hop loss 0.097 fJ vs the capacitive
   floor 0.9 fJ PER hop (= 4.5 fJ for 5 hops): ~46x less.

With per-stage RAIL TOP-UP (chain6_topup.cir): a GAP between hops lets a dV rail restore each stage to
FULL dV (supplying only the ~0.5% I^2R deficit) before it transfers onward:
   n0..n5 ALL = 0.6000 V  => the -0.56%/hop droop is ARRESTED; the wave holds full dV to arbitrary
   depth. Per-cycle energy input = the I^2R loss only, supplied by the generator (Track C), NOT
   1/2*C*dV^2. This is the 'it is a wave' result: forward transfer + periodic top-up = lossless-in-level
   propagation, exactly the restore/re-inject role the k-block boundary (B5) plays.

FREEZE TIMING carries over from qal_a1f_inductive.py: opening at the ZC is clean; fixed-time-late-biased
is viable (peak flat +/-14ps@1%), else active ZCS. Loss lever = Q = sqrt(L/C_eff)/R.

NOT YET SHOWN: realistic on-chip L (nH/real R -> lower Q, more droop/hop -> shorter restore interval);
dual-rail (data-independent tap); actual data PATTERNS (not just a single '1'); device switches + Vt +
their charge injection; the Track-C generator that supplies the top-up; and reconciling the restore
interval k with A2's k(dV). But the core claim -- the inductive wave PROPAGATES with ~1/Q loss/hop and
top-up makes it lossless-in-level -- is shown, and it is the mechanism A2's capacitive cell lacked.
"""
CL, dV, R, Q = 10e-15, 0.6, 100, 141
BARE   = [0.6000,0.5966,0.5933,0.5900,0.5867,0.5834]   # peak level per stage, no top-up
TOPUP  = [0.6000]*6                                     # with per-stage rail top-up
DROOP_PER_HOP = 0.56          # %/hop (I^2R), uniform
LOSS_5HOP_fJ, FLOOR_PER_HOP_fJ = 0.097, 0.900
E_INIT_fJ, E_FINAL_fJ = 1.800, 1.702                    # conserves: 1.702 + 0.097 = 1.799

if __name__=="__main__":
    print("QAL A1f inductive CHAIN (6 stages, 5 hops, R=%d, Q~%d)"%(R,Q))
    print("  stage   bare(no top-up)   with top-up")
    for i in range(6):
        print("   n%d      %.4f          %.4f"%(i,BARE[i],TOPUP[i]))
    print("  bare: uniform -%.2f%%/hop I^2R droop; TRAVELING wave (stages empty, last holds data)."%DROOP_PER_HOP)
    print("  top-up: rail restores full dV each hop -> zero net decay to arbitrary depth.")
    print("  energy conserves: %.3f init = %.3f final + %.3f loss (%.2f%%); 5-hop loss %.3ffJ vs %.1ffJ (5x cap floor)."%(
        E_INIT_fJ, E_FINAL_fJ, LOSS_5HOP_fJ, (E_INIT_fJ-E_FINAL_fJ-LOSS_5HOP_fJ)/E_INIT_fJ*100,
        LOSS_5HOP_fJ, FLOOR_PER_HOP_fJ*5))
    print("  REPAIRS A2: inductive cell CASCADES; A2's capacitive source-follower was -65%%/hop, dead by hop 2.")
