# Older-node GPGPU: DVFS power envelope + reduced-Vdd reliability

Probing the north-star (can an older node host a GPGPU at a 5nm power envelope, reliably?) with
the tools here. SG13G2 130nm as the older-node proxy (PSP103); GF FD-SOI is the real target.

## 1. DVFS envelope (measured — 40-inverter datapath, PSP103)
Voltage sweep of the inverter chain (`vdd_*.cir`, Vdd ramp input, chain delay + ∫I(VVDD)):

| Vdd | fmax | E/op | E/E@1.2V | f/f@1.2V |
|-----|------|------|----------|----------|
| 1.2 V | 586 MHz | 0.253 pJ | 1.00 | 1.00 |
| 1.0 V | 387 MHz | 0.175 pJ | 0.69 | 0.66 |
| 0.8 V | 181 MHz | 0.110 pJ | 0.44 | 0.31 |
| 0.6 V |  32 MHz | 0.060 pJ | **0.24** | 0.055 |

- **Energy/op scales as Vdd²** (measured 0.24 vs ideal 0.25 at 0.6 V — dynamic E = C·Vdd² confirmed).
- **fmax collapses 18×** (delay 1.705→30.8 ns); **near-threshold floor ~0.6 V** (0.5 V won't propagate, Vt≈0.45 V).
- Voltage scaling alone buys ~4.2× on E/op — NOT the full ~10–30× 130nm→5nm node gap. The path to a
  5nm *power envelope* (not per-op parity): voltage-scale + async (kill the clock floor) + GPGPU
  parallelism (recover throughput), paying in area, bounded by the ~0.6 V floor.

## 2. Reduced-Vdd reliability (whole-Vortex, on the T1000)
As Vdd→Vt the delay's Vt-mismatch sensitivity grows → σ_frac amplifies. Swept σ_frac ×1–3 (spanning the
physically-expected near-threshold amplification) through the whole-Vortex (40886-cell) instances×corners
yield kernel (`ssta_alu <lanes> <batches> <sfrac_scale>`). Worst corner (kvt4):

| σ_frac ×N | eff σ_frac | yield-margin (p99.9−mean)/mean | clk@99.9% |
|-----------|-----------|-------------------------------|-----------|
| ×1.0 | 8.1%  | 2.86% | 21.03 ns |
| ×1.5 | 12.1% | 3.90% | 21.57 ns |
| ×2.0 | 16.2% | 4.90% | 22.16 ns |
| ×3.0 | 24.2% | 6.48% | 23.37 ns |

- **Yield degrades gracefully — no cliff.** 3× mismatch amplification (deep near-threshold) needs only
  **+11% clock guardband**; the design still functions.
- Root cause: **scale-emergent self-averaging** — the 47-deep critical path and the max over 4586
  reconvergent endpoints wash out per-cell mismatch (1/√N). Deep datapaths are *relatively* robust.
- **You pay for the power in frequency, not in reliability** — and frequency is what GPGPU parallelism recovers.

## 3. Why bundled-data async is doubly right here
Its matched delay line **self-times to the actual (mismatch-inflated) delay** → it *provides* the +11%
guardband automatically, and it self-times through a **drooping/varying PV supply** (a fixed sync clock,
set for one Vdd, fails when the supply sags). Async is both the power lever (no clock floor) and the
robustness lever (supply + mismatch tolerance). Deployment target: compute run directly off PV at ~±1.5 V.

## Method + honest caveat
- DVFS: `vdd_{120,100,80,60}.cir` (Vdd hardcoded per deck; `.STEP` of a PULSE/param proved unreliable in
  this Xyce — separate decks per point).
- Reliability: the σ_frac ×N sweep is a **sensitivity proxy**, not a measured σ_frac(0.6 V). A rigorous
  σ_frac(Vdd) needs the proper per-device Vt-mismatch MC (`mc/ gen_mc.py` callback-DELVTO flow) re-run at
  0.6 V — an ad-hoc instance/global `DELVTO` was silently ignored (PyMS callback-param plumbing). The
  graceful-degradation conclusion holds across the whole ×1–3 range, so it is robust to the exact value.

## Whole-Vortex sync-vs-async operating map
`vortex_sync_async.py` computes the whole-cluster energy/cycle for sync vs bundled-data across
duty α and Vdd. Result: the 3828-DFF clock floor (108 pJ/cyc) dwarfs the delay-line tax (38 pJ,
cheap on wide 32-bit datapaths) → **crossover α*≈2.9 > 1, so bundled-data async wins at every
activity level** (−13% at α=1, −68% at α=0.1) — opposite of the narrow add8 ripple (α*≈0.5).
Interactive operating-map artifact: https://claude.ai/code/artifact/1c104c1f-27d6-4f4d-b296-c9cf3c890f15

## Three-backend operating map (static / async / QAL)
`vortex_three_backend.py` adds the QAL curve (QAL_PLAN §6: activity-independent
2(RC/T)/η·CΔV²/η) to the static/async models. Result: static is beaten everywhere (clock floor +
full CV², no recovery); **async owns the dark-silicon tail (duty < α*≈18%), QAL owns the busy
regime (duty > α*)** — the Mylex per-block partition. α* slides down with QAL swing (ΔV²). Energy/
cycle only; QAL's generator tax / ~2× area / +2N latency are separate axes; QAL coefficients are
illustrative pending the A3-gated A-track. Artifact: https://claude.ai/code/artifact/7108af61-f898-4823-8148-274774ad322e
