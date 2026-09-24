#!/usr/bin/env python3
"""Track-C: MEASURED power-delivery efficiency (replaces the projected 2.5% / Q=126 hop loss).
In the user's architecture there is no separate generator -- power moves by inductive recycle bank->bank
+ flycap top-up (recharged from the rail). The "Track-C number" = the measured efficiency of that
inductive delivery, which sets the QAL energy floor. Measured with REAL SG13G2 devices + realistic
inductor R (not ideal), via clean ENERGY BALANCE at the transfer peak.

--- MEASURED 2026-09-24 (SG13G2/PSP103; C=80fF banks, L=25nH, C_eff=40fF; energy balance) ---
SG13G2 nMOS switch on-resistance (Vgs=1.2, linear): Ron = 60 ohm @ w=10u (~1/W: ~15 @40u, ~150 @4u).
Per-hop inductive-transfer loss = 1/2 C (dV^2 - VAmin^2 - VBpk^2) / bank-energy, vs total series R
(Ron + inductor R~10), i.e. vs Q = sqrt(L/C_eff)/R:
   R(ohm)   Q     loss/hop
     15    31.6    6.8%      (wide w=40u switch + good inductor)
     30    19.8    9.2%
     60    11.3   13.6%      (REAL SG13G2 w=10u)
     90     7.9   17.4%
    150     4.9   24.0%      (narrow w=4u)
=> The inductive delivery is Q-LIMITED to ~7-14%/hop with real devices -- NOT the 2.5% projection
   (which needed Q=126, i.e. Ron~10 ohm, unphysical at this node). The real device Ron (60 ohm @w=10u)
   + a realistic on-chip inductor cap Q at ~10-32. Wider switches lower Ron but cost area + gate-drive.
Flycap RECHARGE (rail->flycap, inductive): 2nd-order -- the top-up is ~the per-hop loss (~10% of bank),
   and recharging it inductively loses ~the same Q-fraction of THAT (~1% of bank). Dominant term is the
   per-hop transfer loss above. (Full recharge-loop steady-state sim = a follow-up; the transfer floor dominates.)

*** IMPACT on the energy story (this is the load-bearing number the projections lacked):
 e_floor = delivery loss/hop ~= 0.07 (wide) to 0.14 (real w=10u). The QAL gate-energy advantage is capped
 at ~ alpha/e_floor = 0.5/e_floor ~= 3.6x (real) to 7x (wide) -- NOT the ~15-25x an ideal-topup projection
 suggested. So the honest measured energy ceiling for QAL vs CMOS (gate, iso-swing) is ~4-7x, Q-gated.
 The register/clock-tax ELIMINATION (the throughput + total-power win) is UNAFFECTED -- that lever stands.
"""
RON_w10 = 60.0            # ohm, measured, w=10u
DELIVERY = [(15,31.6,6.8),(30,19.8,9.2),(60,11.3,13.6),(90,7.9,17.4),(150,4.9,24.0)]  # R, Q, loss%/hop
E_FLOOR_real, E_FLOOR_wide = 0.136, 0.068
alpha = 0.5

if __name__=="__main__":
    print("Track-C MEASURED power-delivery efficiency (real SG13G2 + realistic inductor)")
    print("  SG13G2 nMOS switch Ron = %.0f ohm @ w=10u (measured, ~1/W)"%RON_w10)
    print("  %6s %6s %10s"%("R","Q","loss/hop"))
    for R,Q,l in DELIVERY:
        tag = " <- REAL w=10u" if R==60 else (" <- wide w=40u" if R==15 else "")
        print("  %6d %6.1f %9.1f%%%s"%(R,Q,l,tag))
    print("  => delivery Q-limited to ~7-14%%/hop (real devices), NOT the 2.5%% projection (Q=126 unphysical).")
    print("  => QAL energy-advantage ceiling = alpha/e_floor = %.1fx (real) to %.1fx (wide) -- was ~15-25x projected."%(
        alpha/E_FLOOR_real, alpha/E_FLOOR_wide))
    print("  => the THROUGHPUT / clock-tax-elimination win is UNAFFECTED; only the energy ceiling comes down.")
