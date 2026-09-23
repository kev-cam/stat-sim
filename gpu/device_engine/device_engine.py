#!/usr/bin/env python3
"""Analytic device-engine PROVE-OR-KILL (numpy reference of the GPU kernel).

GPU-SIM.md's remaining member: replace Xyce's transient solve with a CLOSED-FORM LTI propagator
(no ODE integrator) so device-level Monte-Carlo runs on the GPU. Core primitive: a logic stage =
a first-order system H(s)=1/(1+s*tau) driven by a SATURATED RAMP; the threshold crossing (delay)
and 10-90% output transition (slew) are found ALGEBRAICALLY. Event-scheduling = propagate
(arrival, slew) stage->stage.

Two validations:
  (1) NOMINAL: tau calibrated from ONE transistor stage's output slew must reproduce the 40-stage
      transistor CHAIN delay (non-circular: one stage in, whole chain predicted).
  (2) DERIVE rho0: perturb per-stage tau (Vt-mismatch proxy) and MEASURE the emergent adjacent-
      stage delay correlation -- which exists ONLY because a slow stage hands a degraded slew to
      the next. Compare to the empirical rho0=0.10 the SSTA assumed. The device engine derives it.
"""
import math, sys
import numpy as np

VDD = 1.2
VTH = 0.5 * VDD
V10, V90 = 0.1 * VDD, 0.9 * VDD


def vout(t, Tin, tau):
    """Output of a first-order stage to a saturated ramp (0->VDD over Tin), at time t>=0."""
    if t <= 0:
        return 0.0
    if t <= Tin:
        return (VDD / Tin) * (t - tau * (1.0 - math.exp(-t / tau)))
    return VDD - (VDD * tau / Tin) * (1.0 - math.exp(-Tin / tau)) * math.exp(-(t - Tin) / tau)


def t_cross(level, Tin, tau):
    """Time the (monotone rising) output first crosses `level`. Bisection = algebraic, no ODE."""
    lo, hi = 0.0, Tin + 20.0 * tau
    while vout(hi, Tin, tau) < level:
        hi *= 1.5
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if vout(mid, Tin, tau) < level:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def stage(Tin, tau):
    """One stage: returns (delay input_Vth-cross -> output_Vth-cross, output transition time Tout)."""
    delay = t_cross(VTH, Tin, tau) - 0.5 * Tin      # input crosses VTH at Tin/2
    Tout = t_cross(V90, Tin, tau) - t_cross(V10, Tin, tau)
    return delay, Tout


def propagate(Tin0, taus):
    """Event-schedule a chain: returns per-stage delays and the running slew."""
    T = Tin0; delays = []
    for tau in taus:
        d, T = stage(T, tau)
        delays.append(d)
    return np.array(delays)


def main():
    # calibration from transistor sim (filled from invcal_flat.cir.mt0)
    import json, os
    cal = json.load(open("/home/claude/device_engine_proto/cal.json"))
    Tin0 = cal["in_slew_ps"]; slew_ss = cal["out_slew_ps"]; d_full = cal["chain_delay_ps"]
    d_stage_tr = cal["stage_delay_ps"]; N = cal["N"]
    tau = slew_ss / math.log(9.0)                    # 10-90% of first-order = ln(9)*tau
    print("=" * 90)
    print("Analytic device-engine prove-or-kill  (first-order LTI saturated-ramp propagator)")
    print("=" * 90)
    print("  calibration: input ramp=%.1f ps, transistor mid-stage out-slew(10-90)=%.1f ps -> tau=%.2f ps"
          % (Tin0, slew_ss, tau))
    # (1) NOMINAL: predict the whole chain from tau
    d = propagate(Tin0, [tau] * N)
    print("\n  (1) NOMINAL chain delay:")
    print("    device-engine (LTI)  : %.1f ps  (steady per-stage %.2f ps)" % (d.sum(), d[-1]))
    print("    transistor (Xyce)    : %.1f ps  (mid-stage %.2f ps)" % (d_full, d_stage_tr))
    print("    error                : %+.1f%% chain, %+.1f%% per-stage"
          % ((d.sum() - d_full) / d_full * 100, (d[-1] - d_stage_tr) / d_stage_tr * 100))
    # steady-state slew fixed point
    T = Tin0
    for _ in range(N): _, T = stage(T, tau)
    print("    model steady-state out-slew=%.1f ps (transistor %.1f ps)" % (T, slew_ss))

    # (2) DERIVE rho0 from slew coupling: perturb per-stage tau, measure adjacent-stage delay corr
    print("\n  (2) DERIVE rho0 (adjacent-stage delay correlation from slew coupling):")
    rng = np.random.default_rng(7)
    n_mc = 4000; Nchain = 24            # a mid-chain window (steady slew), skip warm-up
    # scale tau-jitter so per-stage delay sigma_frac matches the delay tier's th23 (~8% at kvt4)
    for target_sf in [0.02, 0.04, 0.06, 0.08]:
        # find tau-jitter that yields per-stage delay sigma_frac ~ target (linear search once)
        # d ~ delay(T,tau); ddelay/dtau approx via finite diff at steady state
        Tss = Tin0
        for _ in range(N): _, Tss = stage(Tss, tau)
        d0, _ = stage(Tss, tau); dp, _ = stage(Tss, tau * 1.01)
        dddtau = (dp - d0) / (0.01 * tau)                 # ps per ps-of-tau
        sig_tau = target_sf * d0 / max(dddtau, 1e-9)      # tau jitter for target per-stage delay sf
        D = np.zeros((n_mc, Nchain))
        for m in range(n_mc):
            taus = tau * (1.0 + rng.normal(0, sig_tau / tau, Nchain + 8))
            dd = propagate(Tin0, taus)[8:]                # drop 8-stage warm-up
            D[m] = dd
        # nearest-neighbor and next-nearest delay correlation across the window
        c1 = np.mean([np.corrcoef(D[:, i], D[:, i + 1])[0, 1] for i in range(Nchain - 1)])
        c2 = np.mean([np.corrcoef(D[:, i], D[:, i + 2])[0, 1] for i in range(Nchain - 2)])
        sf_meas = D[:, 5:].std(0).mean() / D[:, 5:].mean(0).mean()
        print("    per-stage sigma_frac=%.1f%% -> emergent adj-corr rho1=%.3f, next rho2=%.3f"
              % (sf_meas * 100, c1, c2))
    print("\n  If rho1 ~ 0.10 and rho2 ~ 0, the LTI slew-propagation DERIVES the nearest-neighbor")
    print("  correlation the SSTA put in by hand (rho0=0.10) -- from first principles, no fitting.")


if __name__ == "__main__":
    main()
