# Analytic device-engine prove-or-kill (GPU-SIM.md's remaining member)

Can Xyce's transient solve be replaced by a CLOSED-FORM LTI propagator (no ODE integrator) so
device-level Monte-Carlo runs on the GPU? Prove-or-kill on a real transistor circuit — the
sg13g2_inv_1 chain (SG13G2/PSP103 @1.2V), the same cells as the bundled-data delay line.

## Verdict: VIABLE, with a clear scope boundary

1. **Closed-form LTI propagator works — no ODE integrator.** Each stage: first-order saturated-ramp
   response, threshold crossing found algebraically (bisection). Event-schedule (arrival, slew)
   stage→stage. But a **single τ is insufficient** (v1): calibrating τ from output slew mispredicts
   delay by **41%** — an inverter's delay and slew aren't tied by one pole. **Killed the naive form.**
2. **2-parameter NLDM-style stage fixes it (v2).** Decouple delay from slew, per polarity (rise/fall
   asymmetry), each `d = d0 + c·Tin`, `sout = s0 + b·Tin`, calibrated from a transistor slew-sweep
   (slew_10/slew_150.cir). Chain delay **1628 ps vs transistor 1705 ps = −4.5%**. The closed-form
   propagator reproduces the real chain to a few % once properly characterized.
3. **GPU-batches (device_engine.cu).** 1,000,000 device instances × 40 stages in **0.33 s** on the
   T1000; GPU vs numpy mean 0.006%, sd 0.1%. The many-instance regime, on real hardware.
4. **Derives ρ₀'s origin.** Per-stage mismatch g (Vt→drive strength) scales delay AND slew; a slow
   stage hands a slower slew to the next, whose delay rises via c. Emergent adjacent-stage delay
   correlation: **ρ₁≈0.26, ρ₂≈0.01** — a *positive, purely nearest-neighbor* coupling. This derives
   from first principles the STRUCTURE the SSTA candidate-panel chose empirically (nearest-neighbor,
   not exp-decay/uniform). Magnitude is cell-specific (0.26 for inverters, tracks c=0.35; the SSTA's
   0.10 was fit for the different NCL TH-cell chain) — i.e. ρ₀ is *derivable per cell*, not just fit.

## Scope boundary (the real remaining build)
Transistor-*accuracy* needs proper per-cell delay/slew characterization vs input-slew × load — i.e.
NLDM/Liberty-style library characterization — before the device engine can replace Xyce for arbitrary
designs. This prove-or-kill validated the primitive + GPU-batchability + the ρ₀ derivation on one cell;
full library characterization is the larger effort the ensemble device engine ultimately requires.

## Files
- `device_engine.py` (v1 single-pole — shows the 41% miss), `device_engine2.py` (v2 2-param + ρ₀),
  `device_engine.cu` (GPU batch), `cal_*.cir`/`slew_*.cir` (transistor calibration), `cal.json`/`de_ref.json`.
- Calibration (sg13g2_inv_1, fanout-1, 2fF): fall `d=16.78+0.352·Tin`, `sout=26.23+0.154·Tin`;
  rise `d=40.87+0.079·Tin`, `sout=56.99+0.040·Tin` (Tin = 10-90% input slew, ps).
