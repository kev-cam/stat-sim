# stat-sim GPU-batching prototype — "share the driver across warps"

Prove-or-kill prototype for GPU-accelerating stat-sim's delay/reliability tier, per the
design review (see memory `statsim_gpu_prototype`). Answers: does shared-driver batched
Monte-Carlo — one lane = one whole-chain draw, driver broadcast read-only, per-lane RNG,
the ρ0=0.10 nearest-neighbor correlation carried by an MA(1) draw — reproduce the
transistor-MC ground truth, and does dropping ρ0 break it?

## Result: PROVEN — on CPU reference AND on the real GPU

**Ran on P620a NVIDIA T1000 (sm_75, driver 596.59, WSL) 2026-09-22, 1e6 lanes/launch:**
on-device gate passed all three legs — (a) vs analytic golden 0.24% (<1%), (b) vs transistor-MC
ground truth 4.0% (<6%), (c) rho0 sd-shift 6.9% (>4%) → "PROVEN on GPU". GPU moments match the
numpy reference to sub-percent (N=4/kvt1 sd: GPU 14.2 / numpy 14.3 / analytic 14.26; N=8/kvt4 sd:
GPU 86.7 == numpy 86.7). CUDA error-checking confirms the GPU actually executed (not a silent 0).
Shipped by piping the binary over ssh into WSL /tmp (sidesteps Cygwin<->WSL path conversion):
`ssh claude@<p620a> 'wsl -e bash -c "cat > /tmp/sb && chmod +x /tmp/sb && /tmp/sb 1000000"' < statsim_batch`

`python3 gpu_statsim_ref.py` (numpy reference of the per-lane kernel, 1e6 lanes):

| check | result |
|---|---|
| (a) MC-with-ρ0 vs analytic golden `predict_ctx` | worst \|sd err\| **0.13%** — the MA(1) reduction is faithful |
| (b) MC-with-ρ0 vs transistor-MC ground truth (nclfa4/nclfa8) | worst \|sd err\| **4.1%** (residual = the known in-context-μ model bias at N=8, present in `predict_ctx` too, NOT the batching) |
| (c) ρ0-induced σ shift (drop it → lose this) | **≥6.9%** — dropping ρ0 under-predicts, exactly the documented 7–14% effect |

MA(1) construction verified empirically: `x_i = α·w_i + β·w_{i+1}`, α·β=ρ0, α²+β²=1 →
Corr(x_i,x_{i+1})=0.0998≈ρ0, Corr(x_i,x_{i+2})=0, Var=1. Chain variance
`Σσ² + 2ρ0·Σσᵢσᵢ₊₁` == `predict_ctx` exactly.

## Make-or-break rule (highest-severity risk): reconvergent coherence

One lane must be a WHOLE-DESIGN coherent draw. The demo (two paths sharing a 4-stage cone):
drawing the shared cone independently per branch UNDER-reports σ by **13%** (69.4→60.4 ps).
Sharing only the primary-input driver is not enough — the shared logic cone must be drawn
once per lane. This is what makes reconvergent (ALU/Vortex) SSTA correct vs silently optimistic.

## Files
- `gpu_statsim_ref.py` — numpy reference (the decider). Run it; it prints the decision.
- `statsim_batch.cu` — the SIMT kernel (one thread = one lane), same algorithm. Constant-memory
  driver, curand Philox per-lane RNG, MA(1) draw, shared-mem block reduction.
- `gen_model_header.py` → `statsim_model.h` — bakes the driver + ground truth into the binary.
- `statsim_batch` — built fat binary (sm_75 SASS), static cudart, needs only libcuda.so.1.

## Build & ship (no GPU needed to build)
```
python3 gen_model_header.py
/usr/local/src/sv2ghdl/gpubuild/gpu-cc.sh -O2 -arch=sm_75 -o statsim_batch statsim_batch.cu
# ship + run on a GPU host (P620a T1000 sm_75, or Vast.ai):
/usr/local/src/sv2ghdl/gpubuild/ship_run.sh user@p620a 'cd ~ && ./statsim_batch 1000000' statsim_batch
VAST_API_KEY=... /usr/local/src/sv2ghdl/gpubuild/vast_run.sh <id> './statsim_batch 1000000' statsim_batch
```
The numpy reference is the kernel's oracle: on a GPU the printed (mu,sd) per (N,kvt) must match
`gpu_statsim_ref.py` and the ground truth in `statsim_model.h`.

## Step 1 — design-scale SSTA on the Vortex ALU (DONE, on the T1000)

`ssta_alu_ref.py` (numpy) / `ssta_alu.cu` (GPU) run coherent-draw SSTA on the real 4533-cell ALU
netlist (`mylex/nulex/mapper/alu/work/alu.json`, levelized: 4999 nets, 34-deep critical path, 340
endpoints). One lane = one whole-design coherent sample: each cell draws its delay ONCE, arrival
propagates through the levelized DAG reusing it, so reconvergent paths share their cone's
realization by construction. GPU: net-major `arr[net*L+lane]` (coalesced), one thread/lane, no
`__syncthreads` (pre-levelized → every input already written). 1e5 lanes = 2 GB on the 4 GB T1000.

| | mean | sd | p99.9 |
|---|---|---|---|
| GPU (1e5 coherent samples) | 14335.5 | 169.4 | 14885.0 ps |
| numpy reference | 14334.3 | 168.7 | 14876.9 ps |
| **GPU vs numpy** | **0.008%** | **0.4%** | 0.05% |

Reconvergent signal: mean-of-max = single deterministic critical path (14223 ps) **+112 ps** — the
statistical max over 340 reconvergent endpoints — plus the empirical p99.9 a single-path STA can't
produce. Build: `python3 ssta_alu_ref.py --kvt 4 --lanes 30000 --emit-header` then
`gpu-cc.sh -O2 -arch=sm_75 -o ssta_alu ssta_alu.cu`; run `./ssta_alu 50000` on the GPU host.
Trap fixed: never `if(lane>=L) return;` before a block reduction (partial block reduces
uninitialized shared mem → nan variance); guard compute, let all threads reduce.

### ρ₀ in the DAG (fidelity — done)

Nearest-neighbor correlation propagates through the DAG: a cell's delay shares a noise component
with its CRITICAL PREDECESSOR (driver of the latest-arriving input), `x_C = α·z_C + β·z_pred`
(αβ=ρ₀, α²+β²=1) — the chain's MA(1) generalized, reducing to `predict_ctx` on a chain, zero at
distance 2. Zero-delay NOT buffers pass their predecessor's noise through; source cells use fresh
prefill noise. Needs a 2nd per-net array (each cell's own iid noise) → 2× memory (50k lanes = 2 GB).

| ρ₀=0.10 | mean | sd | p99.9 |
|---|---|---|---|
| GPU (50k) | 14344.8 | 183.9 | 14947.1 ps |
| numpy ref | 14344.0 | 184.1 | 14938.5 ps |
| **GPU vs numpy** | **0.006%** | **0.1%** | 0.06% |

Effect: ALU critical-arrival σ **169 → 184 ps (+8.9%)** (matches the chain bound √(1+2ρ₀)=1.095);
μ+3σ sign-off +55 ps. ρ₀=0 recovers the independent σ (sanity).

## Whole-Vortex — the entire 40886-cell execute cluster (DONE, on the T1000)

`ssta_alu_ref.py --netlist .../exec/work/exec.json` and the same `ssta_alu.cu` (netlist-generic;
regenerate `ssta_alu_data.h` from exec, rebuild). 40886 cells (37058 comb, 42500 nets, 4586
endpoints, depth 47). Memory solved by **lane-batching** (not net-tiling): `ssta_alu <lanes> <batches>`
runs independent MC batches with a per-batch RNG offset and accumulates moments, so sample count is
unbounded by GPU memory. 8000 lanes = 2.72 GB per batch on the 4 GB T1000.

| whole-Vortex, ρ₀=0.10 | mean | sd | p99.9 |
|---|---|---|---|
| GPU (8000×8 = 64000 samples) | 20444.1 | 162.7 | 21035.3 ps |
| numpy ref (6000) | 20440.5 | 164.9 | 21057.6 ps |
| **GPU vs numpy** | **0.018%** | 1.3% | 0.1% |

**64000 whole-design coherent samples of a 40886-cell core in ~6 s** on a 896-core T1000. The
reconvergent mean-of-max inflation grows with design size: **+365 ps (1.8%)** over the single
critical path (vs +112 ps / 0.8% on the ALU) — 4586 endpoints push the expected max far above any
one path.

## Instances × corners — multi-corner timing yield (DONE, on the T1000)

The reference is now corner-parameterized (bakes per-cell gate TYPE + a tiny per-(type,kvt) μ table
+ sigma_frac[kvt]); `ssta_alu <lanes> <batches>` loops all 4 kvt mismatch corners (per-corner μ/σ
built on host, per-corner histogram), each corner × batches — the many-instance regime GPU-SIM.md
targets. Whole-Vortex: 4 corners × 24000 instances = **96000 whole-design samples in ~8.7 s**.

| kvt | σ_frac | GPU mean | GPU sd | clk@99% | clk@99.9% | vs numpy (mean/sd) |
|---|---|---|---|---|---|---|
| 1 | 1.94% | 19591.4 | 49.0 | 19714 | 19753 | 0.00% / 1.1% |
| 2 | 3.91% | 19768.9 | 91.6 | 20005 | 20085 | 0.01% / 1.5% |
| 3 | 5.94% | 20035.5 | 126.8 | 20369 | 20487 | 0.02% / 1.7% |
| 4 | 8.08% | 20444.7 | 161.8 | 20870 | 21025 | 0.02% / 1.8% |

PROVEN at every corner. Sign-off = worst corner (kvt4) clk@99.9% = 21025 ps. The σ tail widens
49→162 ps with σ_frac — mismatch barely moves the median but fattens the yield-bounding tail.
Build: `python3 ssta_alu_ref.py --netlist <exec.json> --lanes 6000 --emit-header`,
`gpu-cc.sh -O2 -arch=sm_75 -o ssta_alu ssta_alu.cu`, `./ssta_alu 8000 3`.

## Scope / what this does NOT yet do
- Validated on SERIES ripple chains (the only designs with transistor-MC ground truth).
  Reconvergent coherence is demonstrated for self-consistency, not against transistor MC.
- Accelerates the ANALYTIC delay tier. At cell/path scale that tier is already closed-form and
  free on CPU; the GPU payoff is at DESIGN scale (empirical tails, non-Gaussian reconvergent max).
- Does NOT touch stat-sim's expensive ensemble.py tier (external Xyce subprocess per member) —
  that needs the batched analytical device engine GPU-SIM.md:74 calls "still to build".
