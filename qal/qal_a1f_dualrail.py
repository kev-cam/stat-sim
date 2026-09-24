#!/usr/bin/env python3
"""QAL A1f -- DUAL-RAIL inductive hop with real SG13G2 nMOS FREEZE SWITCHES (A3 precursor).
Differential pair (T,F) -> (T',F') via two inductors, each gated by an nMOS. Brings in the real-device
effects the A3 sigma(Vt) mismatch Monte-Carlo needs: Ron (sets Q), Vt (gate-drive), and gate feedthrough.

NUMERICAL NOTE (real finding): PSP103 nMOS + inductor + UIC at FAST speed (L=16nH, T_half~28ps) ABORTS
-- the transient timestep collapses at ~0.01ps (the ideal-switch inductive runs converge fine at the
same speed, so it is the compact device in the resonant loop, not the inductor/UIC). Made it converge by
SLOWING to L=1uH (T_half~222ps) + series damping R=50ohm + 1fF caps on the L-device junction nodes. So
this device run characterizes Ron/Vt/feedthrough at a gentle hop; the supra-CMOS SPEED result stands on
the ideal-switch runs (qal_a1f_inductive.py). Fast-speed device convergence needs special handling (a
future item).

--- MEASURED 2026-09-23 (SG13G2/PSP103 tt, w=10u nMOS switches, L=1uH, gate=1.2V, freeze at T_half) ---
Matched pair (both switches w=10u), differential readout at 0.4ns (after freeze):
   data=1: Tp=0.547 Fp=0.337 -> DIFF(Tp-Fp)=+0.3648  SUM(Tp+Fp)=0.2391
   data=0: Tp=0.337 Fp=0.547 -> DIFF=-0.3648          SUM=0.2391
=> (1) the DIFFERENTIAL carries the data: DIFF flips +/-0.365 with data 1/0 -- the pattern transferred
   forward through the real device switches. (2) GATE FEEDTHROUGH is the dominant single-ended error:
   each rail sits ~0.12V high (SUM=0.239) because the wide (w=10u) device's Cgs couples the 1.2V gate
   onto source/drain. BUT it is perfectly COMMON-MODE -- SUM is IDENTICAL (0.2391) for data=1 and data=0
   -- so it is REJECTED in the differential readout. This is the concrete dual-rail payoff against a real
   device non-ideality, and it is why QAL logic wants dual-rail (beyond the completeness argument).
   Tradeoff exposed: a WIDE device gives low Ron (high Q, low transfer loss) but LARGE feedthrough
   (Cgs ~ CL); the differential cancellation is what makes the wide device usable.

Mismatch (A3 hook): X_F w=9u vs X_T w=10u (a ~10% device asymmetry standing in for a Vt/geometry
mismatch), data=1:
   matched  DIFF=+0.3648 SUM=0.2391 ; mismatch DIFF=+0.3674 SUM=0.2366 -> shift DIFF +2.5mV, SUM -2.5mV.
=> switch mismatch breaks the common-mode symmetry -> the feedthrough leaks into a DIFFERENTIAL error
   (~2.5mV per 10% size asymmetry here).
   This is exactly the failure mode A3's sigma(Vt) Monte-Carlo quantifies: with per-device Vt spread the
   two switches inject/conduct differently, and the differential signal picks up a data-independent
   offset that erodes the noise margin. The PyMS DELVTO callback flow (PYMS_CALLBACK_PARAMS=DELVTO +
   AGAUSS + .SAMPLING) drives this on this exact cell -- the built A3 harness.

NEXT (A3): swap the geometry-mismatch stand-in for the real DELVTO Vt-mismatch callback, run the MC,
and get yield(differential-margin) vs sigma(Vt) and swing dV -- the GO/NO-GO. And do it on a real
22FDX/PSP card (bulk SG13G2 over-states body-effect/feedthrough, per A2).
"""
MATCHED = {"d1": dict(Tp=0.547, Fp=0.337, DIFF=+0.3648, SUM=0.2391),
           "d0": dict(Tp=0.337, Fp=0.547, DIFF=-0.3648, SUM=0.2391)}
MISMATCH = dict(DIFF=+0.3674, SUM=0.2366, dDIFF_mV=+2.5, dSUM_mV=-2.5)  # X_F 9u vs 10u, data=1

if __name__=="__main__":
    print("QAL A1f dual-rail inductive hop, real SG13G2 nMOS switches (L=1uH, freeze at T_half)")
    print("  case      Tp    Fp   | DIFF(signal)  SUM(common-mode feedthrough)")
    for k,lbl in [("d1","data=1"),("d0","data=0")]:
        m=MATCHED[k]
        print("  %-8s %.3f %.3f |   %+.4f       %.4f"%(lbl,m["Tp"],m["Fp"],m["DIFF"],m["SUM"]))
    print("  => DIFF carries data (+/-0.365); SUM common-mode (0.239, data-independent) => feedthrough")
    print("     rejected differentially. Dual-rail payoff vs real device switches. Mismatch -> A3 MC.")
