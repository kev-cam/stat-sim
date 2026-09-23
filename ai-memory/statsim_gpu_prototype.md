---
name: statsim_gpu_prototype
description: "GPU stat-sim: was design-doc-only; now a PROVEN prototype in /home/claude/statsim_gpu_proto — shared-driver batched MC (MA(1) rho0 draw) reproduces transistor-MC ground truth; CUDA fat binary builds+ships"
metadata: 
  node_type: memory
  type: project
  originSessionId: 4921ad0c-f17b-4b84-986a-5917c9ebd2a6
  modified: 2026-09-23T07:13:51.083Z
---

**Status change:** a GPU version of stat-sim did NOT exist (design-doc-only in
`/usr/local/src/mylex/GPU-SIM.md`, which names stat-sim as the port target and lists the
analytic engine as "still to build"). As of 2026-09-22 there is a **PROVEN prototype** in
`/home/claude/statsim_gpu_proto/` (README has full results + ship cmds).

**User's premise (correct instinct, two words off):** they framed GPU accel as "two-phase eval
over clock cycles" and proposed "share the driver waveform across the warps rather than
two-phase." Corrections: (1) two-phase (sm_clock/sm_comb) is the DIGITAL gen_statemachine model,
NOT stat-sim — stat-sim's batchable tier is single-pass feed-forward (statsim_ssta.py arrival()),
nothing to "replace"; (2) the multi-step PWL the user named lives ONLY in the emitted Verilog-AMS
metastability tier (nvcgen.py) — branchy/event-driven, the WORST SIMT target; the GPU-friendly
delay tier carries scalar (mu,sd), not PWL. BUT the mechanism ("share one read-only driver, vary
the per-lane physics") IS stat-sim's ensemble MC shape and the documented 70-138x many-instance
regime. Right axis = **instances × kvt corners**, never within one design.

**The prototype (prove-or-kill):** one lane = one whole-chain MC draw; driver (in-context stage
means t_first/t_ctx/t_last + th23 sigma_frac) shared read-only (constant memory); per-lane Philox
RNG; the rho0=0.10 nearest-neighbor correlation carried by an **MA(1) draw** x_i=α·w_i+β·w_{i+1}
(α·β=rho0, α²+β²=1 → chain var Σσ²+2rho0·Σσᵢσᵢ₊₁ == predict_ctx, verified empirically). PROVEN:
(a) matches analytic golden 0.13%, (b) matches transistor-MC gt (nclfa4/nclfa8) within 4.1%,
(c) dropping rho0 under-predicts σ ~7% (the documented effect). Validates [[async_power_anchor]]'s
sibling reliability tier without a transistor solve.

**★ Make-or-break rule — reconvergent coherence:** one lane must be a WHOLE-DESIGN coherent draw.
Drawing a shared logic cone independently per reconvergent branch UNDER-reports σ 13% (silently
optimistic worst-case) — the same silent-wrong hazard we hunt in --accel. Sharing only the
primary-input driver is necessary but NOT sufficient. Only series-chain ground truth exists
(nclfa/nclfa4/nclfa8); reconvergent coherence shown for self-consistency, not vs transistor MC.

**Artifacts:** `gpu_statsim_ref.py` (numpy decider), `statsim_batch.cu` (SIMT kernel, same algo),
`gen_model_header.py`→`statsim_model.h`. Built a **fat sm_75 binary** via podman nvcc
([[gpu_container_build_flow]], `sv2ghdl/gpubuild/gpu-cc.sh`) — no GPU/driver to build; static
cudart, needs only libcuda.so.1. Uses double throughout (var=sumsq/n-mean² safe; fp32 loses 0.5%).
An adversarial CUDA review (2 medium fixes applied: CUDA_CHECK on every call so a silent GPU
failure can't fake PROVEN; the tight <1% analytic-golden gate baked into the header + on-device
DECISION).

**★ RAN ON THE REAL GPU 2026-09-22:** shipped to [[p620a_compute_node]] (P620A now at
192.168.223.247 — kept its DHCP lease; sweep-and-diff after a wake found it) NVIDIA T1000 sm_75,
driver 596.59, WSL. **On-device gate PROVEN:** (a) 0.24% (b) 4.0% (c) 6.9%; GPU moments == numpy
ref to sub-percent (Philox vs PCG64 = pure MC noise). Ship trick that avoids Cygwin↔WSL path
conversion: pipe the binary over ssh straight into WSL — `ssh claude@<p620a> 'wsl -e bash -c "cat >
/tmp/sb && chmod +x /tmp/sb && /tmp/sb 1000000"' < statsim_batch` (this sandbox is ON the LAN at
.250, so scp/ssh reach P620a directly). TRAP: P620a sleeps; when asleep .247 drops off ARP
entirely — don't scan/auth-probe other LAN hosts, just ask the user to wake it.

**★ STEP 1 DONE — design-scale SSTA on the Vortex ALU, on the T1000 (2026-09-22):** levelized
`mylex/nulex/mapper/alu/work/alu.json` (4533 comb cells MUX/AND/OR/XOR/NOT, 4999 nets, 34-deep crit
path, 340 endpoints). Per-cell COHERENT draw (one delay/cell/lane, reused across all reconvergent
fanout via a net-major arrival array — coherence by construction, no path expansion). GPU kernel
`ssta_alu.cu`: arr[net*L+lane] coalesced; one thread/lane sweeps the PRE-LEVELIZED DAG so every
input is already written → no __syncthreads. 1e5 lanes = 2GB arr on the 4GB T1000. GPU vs numpy
ref: mean **0.008%**, sd **0.4%** → PROVEN. Reconvergent signal: mean-of-max = single-critical-path
μ **+112 ps** (statistical max over 340 endpoints) + empirical p99.9=14885ps a single-path STA can't
give. Files in `/home/claude/statsim_gpu_proto/` (ssta_alu_ref.py numpy decider w/ --emit-header,
ssta_alu.cu, ssta_alu_data.h, ssta_alu binary). Only series chains have transistor-MC ground truth;
ALU golden = analytic SSTA + numpy MC.

**★ ρ0 IN THE DAG DONE (2026-09-22, "try 1"):** generalized the chain's MA(1) to a DAG — a cell's
delay shares a noise component with its CRITICAL PREDECESSOR (driver of the latest-arriving input):
x_C = α·z_C + β·z_pred (αβ=ρ0, α²+β²=1), reduces to predict_ctx exactly on a chain, nearest-neighbor
(zero at distance 2). Zero-delay NOT buffers pass the predecessor's noise through so they don't break
the coupling; source cells use their own fresh prefill noise. Needs a 2nd per-net array (each cell's
own iid noise, for successors) → 2× memory, so 50k lanes = 2GB on the 4GB T1000. RAN on T1000: GPU vs
numpy ref mean 0.006%, sd 0.1% → PROVEN. Effect: ALU crit-arrival σ 169→**184 ps (+8.9%)** (matches
the chain bound √(1+2ρ0)=1.095), μ+3σ sign-off +55ps. ρ0=0 recovers the independent σ (sanity).

**★ CUDA TRAP caught+fixed:** a one-thread-per-lane kernel must NOT `if(lane>=L) return;` before a
shared-mem block reduction — the last partial block (grid 391×256=100096 > L=100000) then reduces
UNINITIALIZED shared mem → corrupts sumsq → sd=**-nan** (mean survives as a large signal; variance
is a tiny difference of big numbers, flips negative). Fix: guard compute in `if(lane<L)`, default
my_sum/my_sq=0, ALL threads reach the reduction. (Chain kernel dodged it via a grid-stride loop.)

**★ WHOLE-VORTEX PROVEN on the T1000 (2026-09-22):** ran the same coherent+ρ0 SSTA over the entire
execute cluster `mylex/nulex/mapper/exec/work/exec.json` (40886 cells: 12731 AND/10419 MUX/7674
XOR/5562 OR/3828 DFF/672 NOT; 37058 comb, 42500 nets, 4586 endpoints, depth 47). ssta_alu_ref.py is
now netlist-generic (`--netlist`, big-stack thread for deep recursion, setrecursionlimit 400k).
Memory model solved by **LANE-BATCHING** not net-tiling: arr+znet = 2×42500×L×4 → 8000 lanes = 2.72GB
fits 4GB; kernel takes a per-batch RNG offset (loff), host accumulates sum/sumsq/hist across batches
(unbounded samples). **64000 samples (8000×8 batches) in ~6 s** on the 896-core T1000. GPU vs numpy
ref: mean 0.018%, sd 1.3% → PROVEN. Reconvergent mean-of-max inflation GROWS with size: **+365 ps
(1.8%)** vs the ALU's +112 (0.8%) — 4586 endpoints push the expected max far above any single path.
(Bigger-than-memory designs would need net-tiling; 42500 nets still fit.)

**★ INSTANCES × CORNERS DONE on the T1000 (2026-09-22):** ssta_alu_ref.py is now
corner-parameterized (bakes per-cell gate TYPE + tiny per-(type,kvt) μ table `type_mu_table` +
sigma_frac[kvt], not one frozen corner). GPU kernel loops all 4 kvt corners (builds per-corner
μ/σ on host from GATE_MU[type*NKVT+k], per-corner histogram), each corner × N batches. Whole-Vortex
(40886 cells): 4 corners × 24000 instances = **96000 whole-design samples in ~8.7 s**; GPU vs numpy
per corner: mean 0.00-0.02%, sd 1.1-1.8% → PROVEN at every corner. Per-corner timing-yield table
(clk@99%, clk@99.9%, fmax): σ tail widens 49→162 ps as σ_frac 1.94→8.08%; sign-off = worst corner
kvt4 clk@99.9%=21025 ps. This IS the many-instance regime GPU-SIM.md targets (instances × corners).
Note NCL fmax ~48 MHz (deep 47-level chain × ~360-650ps th-cell delays — the async NCL's slow speed).

**★ DEVICE-ENGINE PROVE-OR-KILL DONE (2026-09-23, `/home/claude/device_engine_proto/`):** the last
GPU-SIM.md member (replace Xyce transient with a closed-form LTI propagator, no ODE integrator).
Tested on the real sg13g2_inv_1 chain (SG13G2/PSP103). Findings: (1) closed-form LTI propagator works
(algebraic threshold crossing) BUT a single τ is insufficient — τ-from-slew mispredicts delay 41%
(inverter delay & slew aren't one pole); (2) a 2-PARAMETER NLDM-style stage (delay decoupled from
slew, rise/fall asymmetry; d=d0+c·Tin, sout=s0+b·Tin, calibrated from a transistor slew-sweep)
reproduces the transistor chain to **−4.5%**; (3) GPU-batches (device_engine.cu): **1e6 device
instances × 40 stages in 0.33 s** on the T1000, GPU vs numpy 0.006%/0.1%; (4) **DERIVES rho0's
origin** — per-stage Vt→drive mismatch scales delay+slew, slow stage hands slower slew to next →
emergent adjacent-stage delay corr **ρ1≈0.26, ρ2≈0.01** (positive, PURELY nearest-neighbor —
validates the SSTA candidate-panel's structural choice from first principles; magnitude cell-specific,
tracks slew-sensitivity c=0.35, vs the 0.10 fit for the different NCL TH-cell chain). SCOPE BOUNDARY:
transistor-accuracy for arbitrary designs needs full per-cell NLDM/Liberty characterization
(input-slew × load) — the real larger build. TRAP re-confirmed: PULSE rise-time as a .STEP param
didn't vary in this Xyce; use separate decks per slew.

DONE: whole delay/reliability tier + instances×corners + device-engine prove-or-kill. Remaining:
full library characterization for the device engine; net-tiling for designs bigger than GPU memory
(42500 nets still fit). Supersedes "increment to build" in [[statsim_scaling_directive]]. Vision:
[[phone_dev_environment_vision]].
