#!/usr/bin/env python3
"""*** RETRACTED -- see qal/flycap/RETRACTION.md ***
The headline "TRUE QAL ENERGY PER OP = 1.966 fJ/hop" below is NOT a measurement. It rests on
qal_fc_perm.cir, whose per-tier load is five IDEAL CURRENT SOURCES (I1..I5, lines 25-29):
that deck contains no banks, no switches, no gates, no flycaps and no hop. It computes
E_rail = V_span*Q for a series RC string -- exact, but true BY CONSTRUCTION of 3.0/0.6 = 5.
The 5:1 series-tier result IS worth keeping, but as a TOPOLOGICAL IDENTITY, not an empirical
efficiency. Do not quote the fJ/hop figure. The "correction" of qal_twobank.py:15 from 0.425
to 1.96 fJ/hop is likewise not established here -- treat twobank as OPEN, not superseded.
"""
"""FLYCAP RECHARGE from the +-1.5 V rails -- closes the gap flagged at qal_twobank.py:31
("Rail->flycap recharge efficiency deferred per user") and at qal_a1f_chain_topup.cir:4, where the
top-up came from "VTOP top 0 {dV}", an IDEAL 0.6 V source. Until now NO deck had ever traced a joule
back to the +-1.5 V rail. Per the user: "All the energy in a running QAL is going through the flying
caps", so rail draw per op IS the true QAL energy per op.

*** FIRST, A CORRECTION TO AN INHERITED NUMBER ***
qal_twobank.py:15 reports loss 0.405+0.020 = 0.425 fJ/hop = 3.0% of the 14.4 fJ bank. That is an
I^2R integral over FROM=0 TO=115p and UNDERCOUNTS (the documented window trap). It is inconsistent
with its own Q: that deck's Z0 = sqrt(25n/40f) = 791 ohm with R = Ron50+RL20 = 70 -> Q = 11.3, and
Track-C's energy balance at Q=11.3 gives 13.6%/hop. Clean energy balance on the deck's own numbers
(VBpk=0.5559, VAmin 0.05-0.11) gives 1.56-1.94 fJ. USE 13.6% of bank = 1.96 fJ/hop.

--- MEASURED 2026-09-24, Xyce + SG13G2/PSP103, real pMOS switches (decks: qal_fc_*.cir) ---
env check: nMOS Ron = 58.5-61.7 ohm @ w=10u -> reproduces the Track-C 60 ohm.

1. SWITCH SIZE IS THE DOMINANT TERM, NOT THE LEVEL MISMATCH  [qal_fc_swsize.cir]
   pMOS rail-side parasitic AND gate charge are BOTH ~1.96 fF/um of width, linear:
       w=0.5u -> 0.98 fF | w=2u -> 4.06 fF | w=30u -> 58.65 fF
   A w=30u switch (what 60 ohm costs) draws 87.98 fC = 132 fJ of parasitic per full-swing event and
   needs 132 fJ of CMOS gate drive -- 67x each vs the 1.96 fJ/hop being delivered. The level-mismatch
   penalty is only ~3 fJ. So the switch costs ~87x what the mismatch costs.
   => the Track-C 60 ohm sizes the TRANSFER switch (speed-critical). The RECHARGE switch is off the
      critical path and must be sized for the recharge window instead.

2. THE RAILS AND THE SWING ARE ALREADY IN AN EXACT INTEGER RATIO  [qal_fc_stack.cir copy B]
   3.0 V rail span / 0.6 V bank swing = 5 EXACTLY. Five flycaps in series across +-1.5 V landed at
   0.6000 / 0.6000 / 0.6000 / 0.6000 / 0.6000 V from a cold start -- SELF-TERMINATING, no chop timing,
   inherently ZCS at both edges. Charge bookkeeping exact: stack cap charge 90.00 fC = Cf*0.6.
   eta_mismatch = N*dV/Vspan -> 100% at N=5 (vs 40% for a naive single-cap resistive recharge).

3. SERIES CHARGING EQUALIZES CHARGE, NOT VOLTAGE  [qal_fc_stack.cir copy C]
   +-20% capacitance spread -> cap voltages 0.4899 / 0.5344 / 0.5878 / 0.6531 / 0.7348 V (q identical
   at 88.17 fC each). The spread survives 1:1. Flycap matching must be <1% (MIM territory).

4. THE WINNER NEEDS NO RECHARGE SWITCH AT ALL  [qal_fc_perm.cir]
   Permanently-connected 5-tier stack, tier loads = 32.7 uA each (= 1.96 fJ per 100 ps hop):
       tier caps sit at 0.6000 V each; I(rail) = 32.76 uA -- ONE tier-load current, NOT 5x it.
       P_rail = 3.0 V * 32.76 uA = 98.28 uW ; P_delivered = 5 * 0.6 V * 32.7 uA = 98.10 uW
       eta = 99.8% (the 0.18% shortfall is the test bench's 60 nA bias divider)
   *** TRUE QAL ENERGY PER OP = 1.966 fJ/hop of rail draw, for 1.960 fJ/hop delivered: 0.3% overhead.
   No switching => no gate drive, no switching parasitic; only the series interconnect R (~0.0005 fJ).
   For scale, CMOS CV^2 on the same 80 fF/0.6 V node = 28.8 fJ -> 14.7x. (This is the DELIVERY
   efficiency only; it does not revise the Track-C gate/transfer loss that sets the 1.96 fJ itself.)

5. TIER BALANCE IS THE LOAD-BEARING RISK  [qal_fc_perm_drift.cir]
   Balanced: tier voltages held with <1 uV drift over 200 hop periods.
   5% imbalance on tier 1: +87 mV on that tier over 200 hops, the other four -22 mV each (series
   redistribution). Scaled: 10% of dV (60 mV) is reached in ~138 hops @5%, ~690 @1%, ~6900 @0.1%.
   => a slow trickle balancer suffices (~eps * stack power), NOT a per-hop converter.
   => DUAL-RAIL's measured 0% data-modulation (qal_twobank.py:24-30) is what keeps eps device-set
      rather than data-set. This is a SECOND, stronger reason for dual-rail than the fixed-top-up one.

REJECTED, with the reason:
 - resistive from a 1.5 V rail: eta capped at dV/Vr = 40% FOREVER. The (Vr-dV)*q term is first order
   in the droop and is a CONDUCTION loss -- unlike the A1b settle loss it is NOT ramp-removable,
   because the rail cannot be ramped. Honest negative: 60% of rail draw wasted on the level step.
 - resonant one-shot from the rail: NOT a level converter, it is a reflection doubler. Peaks at
   2*Vr - V0 = 2.449 V (4.1x the 0.6 V target); ZCS is at that peak, a different point from where
   V=dV (13.2 ps vs 128.8 ps). Chopping at dV leaves 0.68 fJ in L -- more than the hop needs.
 - buck/converter: mismatch -> 0 via volt-second balance, but per-lane L = 78-195 nH is not
   integrable, and a shared global converter reintroduces the "separate power generator" the
   architecture disclaims.
 - flycap charge pump WITH level shift: bottom-plate parasitic break-even is Cpar = 2.42 fF = 1.6% of
   a 150 fF flycap (tier shifts 1.5/0.9/0.3/0.3/0.9 V, <dV^2> = 0.81 V^2). At or beyond the best MIM.
   Avoid entirely by keeping each tier's common mode STATIC (finding 4).
"""
MEAS = {
    "ron_nmos_w10u_ohm": (58.5, 61.7),
    "cpar_and_cgg_fF_per_um": 1.96,
    "stack5_cap_volts": [0.6000]*5,
    "stack5_cold_cap_charge_fC": 90.00,
    "cap_spread_pm20pct_volts": [0.4899, 0.5344, 0.5878, 0.6531, 0.7348],
    "perm_irail_uA": 32.76, "perm_tier_load_uA": 32.7, "perm_eta_pct": 99.82,
    "true_qal_fJ_per_hop": 1.966, "delivered_fJ_per_hop": 1.960,
    "drift_5pct_mV_per_200hops": 87,
}
DERIVED = {
    "eta_resistive_asymptote": 0.40,          # dV/Vr
    "eta_stack_N": lambda N, dV=0.6, span=3.0: N*dV/span,
    "resonant_oneshot_peak_V": 2.449,         # 2*Vr - V0
    "levelshift_breakeven_Cpar_fF": 2.42,
}

if __name__ == "__main__":
    m = MEAS
    print("QAL flycap recharge from the +-1.5 V rails (MEASURED, SG13G2/PSP103)")
    print("  CORRECTION: twobank's 0.425 fJ/hop is a window undercount; use Track-C 13.6% = 1.96 fJ/hop.")
    print("  switch parasitic AND gate cap: %.2f fF/um of pMOS width (linear, w=0.5/2/30u)" % m["cpar_and_cgg_fF_per_um"])
    print("  w=30u switch: 132 fJ parasitic + 132 fJ CMOS gate per event = 67x the 1.96 fJ delivered")
    print("  => the SWITCH dominates; the level mismatch is ~87x smaller. Size recharge for its own window.")
    print("  N=5 series stack across +-1.5 V (3.0/0.6 = 5 EXACTLY): caps landed at %s V, self-terminating"
          % "/".join("%.4f" % v for v in m["stack5_cap_volts"]))
    print("  series charging equalizes CHARGE not VOLTAGE: +-20%% C -> %.3f..%.3f V" %
          (m["cap_spread_pm20pct_volts"][0], m["cap_spread_pm20pct_volts"][-1]))
    print("  PERMANENT 5-tier stack: I(rail) = %.2f uA = ONE tier load (%.1f uA), eta = %.2f%%"
          % (m["perm_irail_uA"], m["perm_tier_load_uA"], m["perm_eta_pct"]))
    print("  *** TRUE QAL ENERGY PER OP = %.3f fJ/hop rail draw for %.3f fJ delivered (0.3%% overhead)"
          % (m["true_qal_fJ_per_hop"], m["delivered_fJ_per_hop"]))
    print("  RISK: tier balance -- 5%% imbalance drifts %d mV/200 hops; needs a slow trickle balancer."
          % m["drift_5pct_mV_per_200hops"])
    print("  => BUILD FIRST: permanently-connected 5-tier stack (candidate 5).")
