---
name: gpgpu_older_node_target
description: "★ NORTH STAR: build an NVIDIA-grade GP-GPU on an OLDER node by dropping power to match 5nm silicon. GF FD-SOI (FDX) is the real target; SkyWater sky130 is the only PDK in hand"
metadata: 
  node_type: memory
  type: project
  originSessionId: 4921ad0c-f17b-4b84-986a-5917c9ebd2a6
  modified: 2026-09-23T08:08:47.239Z
---

★ THE GOAL behind the async-power + GPU-sim work (user, 2026-09-23): **can we build an
NVIDIA-grade GP-GPU on an OLDER process node by reducing its power level to match what 5nm
silicon draws?** If an older/cheaper node can hit the power envelope, it can host a modern
GPGPU. **GF FD-SOI (FDX, e.g. 22FDX) is the ACTUAL target** (proprietary, not in hand);
**SkyWater sky130 is the only PDK we have** for the full open layout flow.

**★ DEPLOYMENT (user, 2026-09-23): run the compute DIRECTLY off a couple of PV cells at ~±1.5 V**
— an UNREGULATED supply that droops under load and varies with illumination. Reinforces the whole
approach: (1) low-power/voltage-scaled regime is the operating point, not an option; (2) the design
must tolerate a Vdd RANGE, not a fixed rail — which is a strong argument for ASYNC/bundled-data,
since it SELF-TIMES to the actual Vdd-dependent delay (a fixed-frequency sync clock set for one Vdd
fails when the PV supply sags; async just runs slower/faster and stays correct). So the reliability
check should span Vdd, and async is the robustness lever against supply variation, not just a power lever.

**How the pieces serve this:**
- [[vortex_test_vehicle]] — Vortex (open RISC-V GPGPU) is the GPGPU stand-in / device under test.
- Bundled-data async binding [[async_power_anchor]] — cuts the synchronous CLOCK-FLOOR power (the
  duty-dependent win, crossover α*≈0.51 for deep datapaths); the power lever for the envelope.
- [[statsim_gpu_prototype]] — verifies TIMING/RELIABILITY holds at whole-core scale on the node's
  Vt-mismatch (the reliability the power reduction must not break); the GPU makes it tractable.
- [[nulex_layout_tooling]] sky130 + OpenROAD = the open layout path we can actually run.
- [[phone_dev_environment_vision]] / [[scaling_direction_federation_fpga_asyncfsm]] — the endgame.

**PDK note:** transistor sims to date used **IHP SG13G2 (130nm)** for device-level power/delay
(PSP103); layout uses **sky130**. Neither is FDX — FD-SOI's back-gate bias + lower active power is
the real reason it's the target. Treat SG13G2/sky130 numbers as the OLDER-NODE proxy; the method
(async power reduction + GPU-verified reliability) is what transfers to FDX when a PDK is available.

**★ MEASURED DVFS envelope (2026-09-23, SG13G2 40-inv datapath, `device_engine_proto/vdd_*.cir`):**
Vdd 1.2→1.0→0.8→0.6 V: E/op **0.253→0.175→0.110→0.060 pJ** (ratio 1.0/0.69/0.44/**0.24** — tracks
Vdd² [1,0.69,0.44,0.25] almost exactly, i.e. dynamic E=C·Vdd² confirmed); fmax **586→387→181→32 MHz**
(delay 1.705→30.8 ns, 18× slower). 0.5 V FAILED to propagate in 40 ns → **near-threshold floor ~0.6 V**
(Vt≈0.45). IMPLICATION for the north-star: voltage scaling gets only ~4.2× on E/op (NOT the full
~10-30× 130nm→5nm node gap), and costs 18× frequency. So the older-node path to a 5nm POWER ENVELOPE
(not per-op parity) = voltage-scale for E/op + async to kill the clock floor [[async_power_anchor]] +
recover throughput with GPGPU PARALLELISM (more cores/area) — paying in AREA, bounded below by the
~0.6 V near-threshold floor. RELIABILITY RISK: σ_frac(Vt-mismatch) GROWS as Vdd→Vt, so the low-Vdd
operating point is exactly where timing yield is at risk.

**★ REDUCED-Vdd RELIABILITY CHECK DONE (2026-09-23) — the power win is USABLE.** Whole-Vortex
(40886-cell) 99.9%-yield sweep vs σ_frac amplification (the near-threshold effect), on the T1000:
worst corner yield-margin (p99.9-mean)/mean = 2.86%→3.90%→4.90%→6.48% as σ_frac ×1→1.5→2→3
(eff σ_frac 8→12→16→24%); clk@99.9% 21.0→21.6→22.2→23.4 ns. **Yield degrades GRACEFULLY, NO CLIFF:**
even 3× mismatch amplification (deep near-threshold) needs only **+11% clock guardband**, design still
functions. Root cause = scale-emergent self-averaging (47-deep path + max over 4586 endpoints wash out
per-cell mismatch, the 1/√N property). So: voltage-scaling for power is timing-reliable on the older
node — you pay in FREQUENCY (18× slower at 0.6V, recovered by GPGPU parallelism), NOT in yield. And the
bundled-data delay line self-times to the actual (mismatch-inflated) delay → it PROVIDES the guardband
automatically, which is also the robustness lever for the drooping PV supply.

**HONESTY:** σ_frac(0.6V) not rigorously measured — the ad-hoc DELVTO perturbation was silently ignored
(PyMS callback needs the proper gen_mc.py wiring [[pyms_callback_params]] / [[feedback_pyms_setparams]],
NOT a plain instance or global .param). Used a σ_frac-SCALE sweep (×1-3) spanning the physically-expected
near-threshold amplification (lit. ~2-4×) instead — answer holds across the range. Rigorous σ_frac(Vdd)
via mc/ gen_mc.py at 0.6V is the clean follow-up.
