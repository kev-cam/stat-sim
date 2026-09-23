# GPU stat-sim: from a question to a whole-core reliability tool

**2026-09-22/23.** Consolidated result of building GPU-accelerated statistical timing/reliability
for the sv2ghdl/mylex stack, validated end-to-end on an NVIDIA T1000 against transistor-MC ground
truth and CPU oracles. Artifacts: `/home/claude/statsim_gpu_proto/` (delay/reliability tier) and
`/home/claude/device_engine_proto/` (device-engine prove-or-kill).

## The question
"Do we have a version of stat-sim that runs on GPU?" — **No.** A full-tree search found zero GPU
code; stat-sim is CPU Python and `ensemble.py` shells out to external Xyce. GPU work was
design-doc-only (`mylex/GPU-SIM.md` names stat-sim the port target, lists the analytic engine
"still to build").

The user's instinct — *"share the driver waveform across the warps, vary the physics per lane"* —
was the correct mechanism (and matches GPU-SIM.md's documented 70–138× many-instance regime). Two
framing corrections: stat-sim is single-pass feed-forward (there is no "two-phase eval" to replace),
and the multi-step PWL lives in the metastability tier (the *worst* SIMT target), not the scalar
delay tier (the right one). The build followed the corrected axis: **instances × corners, one shared
read-only driver, per-lane RNG, whole-design coherent draws.**

## The arc (each stage validated on the T1000)

| # | stage | scale | result |
|---|-------|-------|--------|
| 1 | Chain prove-or-kill | 8-stage NCL carry | vs transistor-MC gt 4.1%, vs analytic 0.24%, ρ₀ shift 6.9% — **PROVEN** |
| 2 | Design-scale SSTA | Vortex ALU, 4533 cells | GPU vs numpy 0.008%/0.4%; reconvergent +112 ps |
| 3 | ρ₀ in the DAG | ALU | σ 169→184 ps (+8.9%), matches chain √(1+2ρ₀)=1.095 |
| 4 | Whole-Vortex | 40886 cells, 42500 nets, depth 47 | 64k samples in ~6 s; 0.018%/1.3%; reconvergent +365 ps (1.8%) |
| 5 | Instances × corners | 4 kvt × 24k = 96k samples | ~8.7 s; per-corner yield; sign-off clk@99.9%=21025 ps |
| 6 | Device engine | inverter chain, PSP103 | 2-param LTI −4.5% vs transistor; 1M inst/0.33 s; derives ρ₀ |

### Method
- **Coherent draw**: each cell instance draws its delay once per lane; arrival propagates through
  the *levelized* DAG reusing it, so reconvergent paths sharing an upstream cone share its
  realization by construction. Breaking this under-reports σ by 13% (silently optimistic worst-case).
- **ρ₀ correlation**: the chain's MA(1) construction (`x=α·z+β·z_pred`, αβ=ρ₀, α²+β²=1) generalized
  to a DAG via the *critical predecessor* (driver of the latest-arriving input); nearest-neighbor,
  reduces to `predict_ctx` on a chain.
- **Memory**: net-major coalesced arrival array; lane-batching (independent MC chunks accumulating
  moments) so sample count is unbounded by GPU memory. 42500 nets × 8000 lanes = 2.72 GB/batch.
- **Certification**: every GPU run checked against a numpy oracle; the chain against the transistor-MC
  ground truth in `models/ncl_th_delay.json` (no-self-baseline). CUDA built via podman-nvcc (no GPU
  needed to build), shipped over ssh into WSL, run on the T1000 (sm_75, driver 596.59).

## Whole-Vortex multi-corner timing yield (the headline deliverable)
40886-cell execute cluster, 96000 whole-design coherent samples, one batched GPU sweep, ~8.7 s:

| kvt | σ_frac | mean (ps) | σ (ps) | clk@99% | clk@99.9% | GPU vs numpy |
|-----|--------|-----------|--------|---------|-----------|--------------|
| 1 | 1.94% | 19591 | 49.0 | 19714 | 19753 | 0.00% / 1.1% |
| 2 | 3.91% | 19769 | 91.6 | 20005 | 20085 | 0.01% / 1.5% |
| 3 | 5.94% | 20036 | 126.8 | 20369 | 20487 | 0.02% / 1.7% |
| 4 | 8.08% | 20445 | 161.8 | 20870 | 21025 | 0.02% / 1.8% |

Mismatch is zero-mean, so the median barely moves; the **yield tail** widens (σ 49→162 ps) and sets
the yield-bounded clock. The reconvergent max over 4586 endpoints inflates the mean +365 ps over the
single deterministic critical path — the whole-design effect a single-path STA cannot see.

## Device engine (prove-or-kill of the last unbuilt member)
Can a closed-form LTI propagator replace Xyce's transient solve (no ODE integrator)?
- **Single τ: killed** — calibrated from slew, mispredicts delay 41% (delay & slew aren't one pole).
- **2-parameter NLDM-style stage (delay decoupled from slew, rise/fall asymmetry): −4.5%** vs the
  transistor inverter chain.
- **GPU-batches**: 1,000,000 device instances × 40 stages in **0.33 s**, 0.006%/0.1% vs numpy.
- **Derives ρ₀'s origin**: per-stage Vt→drive mismatch scales delay *and* slew; slow stage hands
  slower slew to the next → emergent adjacent-stage delay correlation ρ₁≈0.26, ρ₂≈0.01 — *positive,
  purely nearest-neighbor*, deriving from first principles the structure the SSTA assumed. Magnitude
  is cell-specific (0.26 for inverters via slew-sensitivity c=0.35; the 0.10 was fit for TH cells).

## What's proven vs. what remains
**Proven**: shared-driver batched coherent-draw SSTA reproduces transistor-MC reliability; scales to
a whole 40.9k-cell core; multi-corner yield signoff; ρ₀ from first principles; the analytic device
primitive + GPU-batchability. All on real silicon-characterized data, on an actual GPU.

**Remaining**: (1) full per-cell NLDM/Liberty characterization (delay/slew vs input-slew × load) to
make the device engine production-accurate for arbitrary designs; (2) net-tiling for designs larger
than GPU memory (42500 nets still fit); (3) folding the batched analytic engine back into
`ensemble.py` to replace the Xyce subprocess.

## Traps recorded (for the next builder)
- One-thread-per-lane kernels must not `if(lane>=L) return;` before a shared-mem block reduction —
  the partial block reduces uninitialized memory → nan variance (mean survives). Guard compute, let
  all threads reduce; or grid-stride.
- `.STEP` of a PULSE rise-time param didn't vary in this Xyce — use separate decks per slew.
- P620a sleeps; when asleep its IP drops off ARP entirely — ask the user to wake it, don't scan.
- Run PSP103 decks sequentially until the vae `.so` cache is warm (concurrent g++ on one hash corrupts it).
