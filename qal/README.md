# QAL — Quasi-Adiabatic Logic as a third Mylex RTL backend

> **STATE OF PLAY (2026-10-01) — read the durable record first:**
> `/home/claude/qal_threeway/QAL-CAMPAIGN.md` (diagrams) + the "SG13G2 Energy–Delay Map" artifact
> (interactive, transistor-level schematics). One-line verdict, all MEASURED:
> **energy loses on every duty axis** (busy excluded; wide-bank ≤1.15×; bursty closed vs power-gated
> CMOS); **latency never wins** (structural); **throughput wins 12.0× per level** on a three-phase
> resonant-mesh clock (`qal/mesh3`, 5b9d05b) — **at a measured 2.2× system-energy price** for the
> flat-top driver (`qal/meshdrv`, 8d1fd18). A throughput-for-energy trade, for GP-GPU lanes.
> The sections below are the per-experiment appends in chronological order; the durable doc is the
> synthesis.

Feasibility A-track for the QAL backend (`~/QAL_PLAN.md`). One RTL, three backends:
**static** (clocked), **bundled-data async** (self-timed), and **QAL** (ephemeral wave
pipeline, low-swing ΔV², adiabatic recovery). The operating map that puts all three on
one axis lives in `../gpu/vortex_three_backend.py`; this directory grounds its QAL curve
from the physics up.

Partitioning rule (`QAL_PLAN §6`): `a_crit ≈ 2(RC/T)/η` (~20% duty). **Async for dark
silicon, QAL for what never stops** — complementary, not competing. The `RC/T` factor in
that rule is what A1 measures on real silicon.

## A-track sequence (do-first ordering)

| step | question | vehicle | status |
|------|----------|---------|--------|
| **A0** | does the RTL→wave transform compute the right answer? | SHA-256 σ0 (XOR-depth-2), functional | ✅ **PASS** |
| **A1** | does adiabatic recovery work on a real device, and what is `RC/T`? | ramped rail → SG13G2 nMOS → C_L, Xyce | ✅ **A1b PASS** |
| **A2** | how does the swing-vs-margin coefficient `k(ΔV)` behave down a chain? | depth-3/8 chain, Xyce | ✅ **increment 1** |
| **A3** | **GO/NO-GO**: does Vt-mismatch MC hold yield across the chain vs ΔV & k? | mismatch MC (the fixed cell-MC callback flow) | gated on A1/A2 |
| A4–A6 | window / thermal-in-loop / feedback loops | — | nothing above A3 is worth building until A3 reports |

## A0 — `qal_a0.py` (functional golden + certainty-plane necessity)

Vehicle: SHA-256 `σ0(x) = ROTR7(x) ^ ROTR18(x) ^ SHR3(x)` — pure XOR, depth 2, no carries,
so the schedule is the whole story. Result:

- **Functional**: wave-scheduled σ0 == SHA-256 reference over 20 000 random vectors — PASS.
  The RTL→wave transform is a faithful golden model before any transistor exists.
- **Balancing is concrete**: the DAG levelizes to XOR depth 2; `SHR3` (a level-0 wire)
  must reach the level-2 XOR **in-phase**, so it needs **1 balancing buffer/bit** (×32).
  This is the AQFP-style equal-arrival constraint made countable.
- **Why A0 needs 3D-Logic**: drop the buffer and the level-2 XOR reads `SHR3` one phase
  late — its rail has recovered, so the node is **UNCOMPUTED (MEANINGLESS)**, a third
  certainty state distinct from X. The certainty plane **flags this as a violation**;
  4-state logic would silently read a stale/undefined bit. The un-compute window is only a
  *checkable* state because certainty is a first-class plane (`l3dw` certainty enum).

## A1 — `qal_a1b_*.cir` (adiabatic recovery on SG13G2)

Ideal trapezoid rail ramps 0→ΔV (=0.6 V, low-swing regime) over time `T`, through an
SG13G2 nMOS switch into a `C_L = 2 fF` load, then ramps back. Metric per `QAL_PLAN A1b`:
**charge returned / charge delivered** (robust to integration-window definition, unlike
energy). Sweep `T`; recovery → 1 as `T ≫ R_on·C_L` (adiabatic), → low as `T → 0` (a step
dumps ½CΔV² irrecoverably). The knee locates `R_on·C_L`, giving a **measured `RC/T`** to
replace the illustrative `0.05` in the operating map's QAL curve.

Measured (SG13G2/PSP103 tt, ΔV=0.6V, C_L=10fF; non-adiabatic reference C·ΔV² = 3.60 fJ/cyc):

| T (ps) | E_cyc (fJ) | E / C·ΔV² | Vpk (V) | note |
|-------:|-----------:|----------:|--------:|------|
| 20 | 2.226 | 61.8% | 0.388 | RC-limited — C_L can't keep up |
| 100 | 1.687 | 46.9% | 0.526 | |
| 500 | 0.645 | 17.9% | 0.590 | |
| **1000** | **0.406** | **11.3%** | **0.599** | ~1 ns design ramp |
| 2000 | 0.237 | 6.6% | 0.600 | |
| 5000 | 0.123 | **3.4%** | 0.600 | deep adiabatic |

**Result**: energy falls monotonically with ramp time to **3.4% of the hard-step limit at
5 ns** — adiabatic recovery is real on SG13G2. The Vpk knee (~500–1000 ps) locates
`R_on·C_L`, giving **RC ≈ 60–85 ps**, hence **RC/T = 0.056 at a 1 ns stage ramp**. That
**validates the operating map's illustrative `RC/T = 0.05`** (right to first order) and grounds
`a_crit = 2(RC/T)/η` (→ 20.7% at full swing, matching the plan's ~20%). `RC/T` is ramp-time
dependent: ~0.11 @500ps, 0.056 @1ns, 0.033 @2ns, 0.017 @5ns — slower ramp, deeper adiabatic.

Reproduce: `python3 qal_a1b.py` prints the committed record; `python3 qal_a1b.py --run <compat.sp>`
regenerates the decks and re-runs against a live Xyce. Example deck: `qal_a1b_example.cir`.

## A2 — `qal_a2.py` (chain k(ΔV): does single-rail smooth-ramp cascade?)

Increment 1. Designed and adversarially verified as two workflows (a 5-agent design panel → a
hardened Xyce spec; a 4-agent refute panel that re-read the raw files and corrected the writeup).
The cell here is the **single-rail source-follower negative control** — deliberately *not* the
plan's flying-cap forward-transfer stage (A1f/B5). It exists to quantify *why* non-restoring
single-rail fails, i.e. to size the restoration boundary. Depth-3 chain (+depth-8 record), data-1,
T=1ns ramp / H=2ns hold / DLY=1ns phasing, on SG13G2/PSP103 tt. A1b is the anchor (same framework).

**k(ΔV), per-hop node level (bulk):**

| ΔV | N0 | N1 | N2 | usable hops |
|--:|--:|--:|--:|--:|
| **1.20** | 0.831 | 0.442 | 0.025 | ~2 (drop ≈0.39V/hop) |
| 0.60 | 0.206 | 0.064 | 0.002 | 0 (hop-0 marginal) |
| 0.50 | 0.114 | 0.049 | 0.001 | 0 |
| 0.45 | 0.084 | 0.042 | 0.001 | 0 |
| 0.40 | 0.070 | 0.037 | 0.001 | 0 |

- **Binding bound = amplitude (bound 3), not charge (bound 1).** The killer is *topological*:
  a source follower gives V_out = V_gate − Vt(Vsb), no positive fixed point, plus near-threshold
  starvation. Confirmed twice — the A1d DC probe clamps (offset 0.145→0.356V, incremental gain
  ~0.83), and the transient chain adds a ~0.10V/hop finite-settling shortfall on top. Charge
  attenuation never binds (its ratio is just noise once the level collapses). **dV_min ≈ 0.6V**
  for one marginal hop, ~1.2V (≈3Vt) for ~2 hops.
- **Scope:** it's the single-rail *non-restoring source-follower* cell on *bulk* that fails — not
  nMOS-pass as a class, not QAL in general. A drain-fed bootstrapped / full-rail-gate or dual-rail
  cell passes levels without this clamp — that is exactly what B5 supplies. **This is the
  quantitative motivation for the restoration boundary.**
- **Body-effect isolation probe** (ΔV=1.2, b=bulk 0.83/0.44/0.03 vs b=source 1.10/0.94/0.46):
  the body effect *compounds* the loss (isolates ~0.27V of the hop-0 drop) but is **not** the root —
  the Vsb=0 chain still decays (1.10→0.94→0.46). Direction for the north star is sound (FD-SOI helps
  QAL cascade), but only the **~0.27V delta** transfers, not the magnitudes: tying a bulk device's
  body to source is an *optimistic* bound (over-states junction C, keeps bulk DIBL, misses the
  back-gate). A quantitative FD-SOI number needs a real 22FDX/PSP card — **an A3 prerequisite**.
- **Energy per hop is quarantined** — a schedule artifact (stage-1 recovers only 58% because its
  gate collapses under the forward-order un-compute before its rail recovers; the un-compute wave
  must recede from the *front*). Not carried into A3; clean per-hop energy awaits ordered un-compute.

Reproduce: `python3 qal_a2.py` prints the record; `chain_deck(N, ΔV, bsrc=)` regenerates decks.

**A2 → A3 handoff:** the chain fails on amplitude (a Vt clamp), so the A3 GO/NO-GO (σ(Vt) mismatch)
must run on a **restored/dual-rail** cell and on a **real FDX card**, not this bulk source-follower —
the bulk body-effect-dominated numbers would bias the yield verdict.

## A1f — `qal_a1f.py` (flying-cap forward-transfer cell — the patentable core)

Increment 1. Designed + adversarially verified as two workflows (the verify pass was harsh and
corrected several over-claims — see the file docstring). Ideal-source Track-A study (behavioral
switch, ideal linear caps). **Honest scope: this establishes the charge-share floor and dual-rail's
data-signature suppression; it does _not_ yet demonstrate forward-transfer efficiency.**

**Has shown (verified):**
- **Tap validation** (`b2_share.cir`): direct charge-share gives V=0.300V, E_REL=1.350 / E_DEL=0.450 /
  E_SW=0.900 fJ, η_rel=1/3, **balance = 0.0000 fJ** — every energy tap is exact.
- **No single-shot energy free lunch (any topology):** an abrupt flying-cap transfer costs
  **E_SW = ½·C_eff·dV²**, and this is **RON-independent** (0.900 fJ = ½·5fF·0.6² to 6 digits at
  RON=50; C_eff = C1‖C2 = 5fF). A parallel single flying-cap dump _is_ hard charge-share:
  level k = R/(1+R), delivered/**released efficiency = R/(1+2R)** (= 1/3 at R=1). Note `[R/(1+R)]²`
  is a level² figure, **not** efficiency; the genuine efficiency ceiling→1 needs **ZVS / resonant /
  stepwise**, not a stiffer/slower passive dump.
- **Data-signature is a _dual-rail encoding_ property** (not a flying-cap one): single-rail tap is
  **100% data-modulated** (3.0 / 0.0 fC), dual-rail differential-sum is **0.00%** (2.0 / 2.0 fC).
  Flatness is complementary-code symmetry and **survives nonlinear C(V)**; it's a **mismatch-limited
  floor** (ΔC/C = x% → spread x%; ~0.1–few % for SG13G2 10fF caps, 30–200× below single-rail).
- **Crossing slack and data-signature are orthogonal.** A conservative **~112–158 ps** redistribution-
  timing tolerance (RON-independent term only) at a 1 ns ramp.

**Not yet shown (increment 2):** the **ZVS/crossing benefit itself** (the pulsed-switch sim was
numerically fragile — the claim currently rests on the STEP0 endpoint + algebra); the **finite-RON
tracking loss** `E_track ≈ (C_eff·dV/dt)²·RON·W_on` — invisible to ½CdV², doesn't vanish at the
crossing, and is the **real gate** (an RON·W_on ceiling) for any efficiency claim; therefore no
total-loss / efficiency number, and no "recovery runs with the data" energy demonstration; the series
(Marx/Dickson) level-boost; and the dual-rail leak under Pelgrom mismatch MC.

**Increment-2 recipe** (in the docstring): a real coupled cell — finite source R, flying cap, an
_actual_ receiver C_L (not a stiff rail), a **smooth** gate, a TX-tracking loss window, `.STEP` of TX
across the crossing + independent RON and W_on sweeps, per-run energy-balance guard — measuring the
tracking loss the static model omits. Commit to one topology and one C_eff before quoting a number.

## A1f (inductive) — `qal_a1f_inductive.py` — the *actual* forward-transfer mechanism

**Framing correction (from the user's actual scheme):** the capacitive A1f above is the **negative
result** — a passive cap-to-cap transfer can't beat the ½CΔV² floor (it moves only half the voltage,
wastes half the energy; at the "free" crossing it transfers ~nil, QDEL<0). The real mechanism uses an
**inductor** as the primary stage-to-stage transfer element (resonant LC), carrying charge *and* data
forward, with **flycaps only topping up the I²R loss** at the rail extremes.

Measured (Xyce, ideal L, CL=10fF each, dV=0.6V, C_eff=5fF; capacitive floor ½C_eff·dV² = 0.900 fJ):

| R (Ω) | Q | V(B) peak | E_loss | vs floor |
|--:|--:|--:|--:|--:|
| 50 | 283 | 0.598 | 0.044 fJ | **4.9%** |
| 100 | 141 | 0.597 | 0.086 fJ | 9.5% |
| 1000 | 14 | 0.568 | 0.568 fJ | 63% |

- The inductor moves the **full** charge/data pattern (V(A)→0, V(B)→dV — not the capacitive half-swing)
  with loss **~I²R ∝ 1/Q**; at Q=283 that's **20× below the capacitive floor** (~97.6% efficient).
  Energy balance conserves to 0.1%. Full cell (freeze switch at T_half + flycap top-up): per-cycle
  input = the **0.020 fJ I²R loss only**, ~46× below the 0.9 fJ floor.
- **Freeze-timing (fixed-time vs zero-cross detection):** V(B) peaks at the current zero-crossing and
  is quadratically flat — within 1% of peak over **±14 ps**, 2% over ±20 ps. But the penalty is
  **asymmetric**: opening *late* droops gently; opening *early* interrupts I(L) and dumps ½L·I²
  (10 ps early ≈ the whole transfer loss). **Verdict:** fixed-time disconnect works if biased slightly
  *late* and L/C is tuned (±10% L → ±11 ps, inside the window); a passive series diode is ruled out at
  low swing (0.3–0.7 V drop vs 0.6 V rail); active ZCS buys robustness at a comparator/stage. Lean
  fixed-time-late-biased, flycap absorbs the droop; escalate to ZCS only if L/C variation eats the window.
- Lever is **Q = √(L/C_eff)/R**; realistic on-chip L~nH → fast 7–70 ps transfers but lower Q, so
  inductor quality vs speed is the real tension ("needs magnetics").
- **Supra-CMOS speed:** single-hop frozen loss is **loss/floor = π/Q = π²·R·C_eff/T_half** (an early
  sweep wrongly read ~100% by integrating the full ring-down instead of the frozen half-cycle). So a
  20 ps hop (**2× faster than CMOS's ~42 ps**) with L=8 nH costs just **2.5% @ R=10Ω** (6% @ 25Ω); 10 ps
  (4×, L=2 nH) → 4.8% @ R=10Ω. QAL can be **faster *and* lower-energy than CMOS** — nH L buys the speed,
  low R buys the Q. The resonant hop is linear, so **T_half is amplitude/data-independent** (freeze
  instant doesn't move with signal value).
- **Dual-rail? Optional, not required (corrected).** If a stage is a *real static logic gate that settles
  adiabatically* — drive its output node with a ramping supply so the gate's own pull-up/pull-down settles
  to the answer (dissipating ~(RC/T)·CV² instead of ½CV², the settle-not-switch saving) — then **gate type
  is unrestricted (XOR fine) and no dual-rail is needed for completeness**. The "no gain → can't invert"
  limit applies *only* to the aggressive non-restoring pass-transistor / residual-charge variant (the
  plan's lowest-energy scheme that removes the restoring device layer). Dual-rail still *helps*
  (optional) for **constant generator load** and the **differential-sum power tap** (single-rail 100%
  data-modulated, dual 0%) — choose it for those, not for completeness.

**Not yet shown:** realistic on-chip L (nH, real R) efficiency; the return/reset path (re-arm A); a
multi-stage chain (does the wave propagate, does loss compound); explicit data-carrying; dual-rail;
device switches + Vt; the Track-C generator driving it.

## A1f (inductive chain) — `qal_a1f_chain.py` — "it's a wave" + repairs A2

Does the inductive transfer *cascade*? Six stages (C_L=10fF each), stage 0 = dV; each hop is an
L+R+freeze-switch resonant transfer, phased forward so the charge/data pattern travels as a front.

| stage | bare (no top-up) | with per-stage top-up |
|--|--:|--:|
| n0 | 0.6000 (src) | 0.6000 |
| n1 | 0.5966 | 0.6000 |
| n3 | 0.5900 | 0.6000 |
| n5 | 0.5834 | 0.6000 |

- **The wave propagates** at a uniform **−0.56%/hop** I²R droop (97.2% of dV still at stage 5;
  ~95% at depth 8) — vs A2's capacitive source-follower at **−65%/hop, dead by hop 2**. This is the
  mechanism A2's cell lacked.
- **Traveling front, not fan-out:** final V is ~0.003 V on n0–n4 (they *emptied* as charge passed
  forward) and 0.583 V only on n5 (holds the delivered data).
- **Energy conserves** (the decisive free-energy check): 1.800 fJ initial = 1.702 fJ final + 0.097 fJ
  total I²R loss (0.06%). Five-hop loss 0.097 fJ vs 4.5 fJ for five capacitive dumps — **46× less**.
- **Per-stage rail top-up arrests the droop entirely** — every stage holds full 0.6000 V, so the wave
  propagates lossless-in-level to arbitrary depth; the per-cycle input is just the I²R loss, supplied
  by the generator. This is exactly the restore/re-inject role of the k-block boundary (B5).

**Not yet shown:** realistic on-chip L (nH/real R → lower Q, larger droop/hop → shorter restore
interval k); dual-rail; real data patterns; device switches + Vt + charge injection; the Track-C
generator supplying the top-up; and reconciling the restore interval k with A2's k(ΔV).

## A1f (dual-rail, device switches) — `qal_a1f_dualrail.py` — the A3 precursor

Differential pair (T,F)→(T',F') via two inductors, each gated by a real **SG13G2 nMOS freeze switch** —
bringing in Ron, Vt, and gate feedthrough (what the A3 σ(Vt) MC needs).

*Numerical note:* PSP103 + inductor + UIC at fast speed (L=16 nH) **aborts** (timestep collapse at
~0.01 ps; ideal-switch runs converge fine at that speed, so it's the compact device in the resonant
loop). Converges by slowing to L=1µH (222 ps hop) + series damping + junction caps — so this run is the
*device-physics* run; the *speed* result stands on the ideal-switch runs.

Matched pair (both w=10µm), differential readout after freeze:

| case | Tp | Fp | DIFF (signal) | SUM (common-mode) |
|--|--:|--:|--:|--:|
| data=1 | 0.547 | 0.337 | **+0.365** | 0.239 |
| data=0 | 0.337 | 0.547 | **−0.365** | 0.239 |

- **The differential carries the data** (±0.365, sign flips with data) — the pattern transferred forward
  through real device switches.
- **Gate feedthrough is common-mode:** the wide device's Cgs couples the 1.2 V gate onto both rails
  (~0.12 V/rail, SUM=0.239), but SUM is *identical* for data=1 and data=0 → **rejected in the
  differential readout**. This is the concrete dual-rail payoff against a real device non-ideality, and
  it exposes the tradeoff: wide device = low Ron (high Q) *but* large feedthrough (Cgs~C_L); the
  differential cancellation is what makes the wide device usable.
- **Mismatch → A3 hook:** a 10% switch asymmetry (X_F 9µm vs 10µm) shifts DIFF by **+2.5 mV** and SUM by
  −2.5 mV — the asymmetry converts the common-mode feedthrough into a *differential* offset. That's the
  noise-margin erosion **A3's σ(Vt) Monte-Carlo quantifies**, on this exact cell; the PyMS DELVTO callback
  flow drives it.

**Next (A3):** swap the geometry-mismatch stand-in for the real DELVTO Vt-mismatch callback, run the MC →
yield(differential margin) vs σ(Vt) and swing — the GO/NO-GO — on a real 22FDX/PSP card (bulk SG13G2
over-states body-effect/feedthrough).

## Adiabatic NAND2 — `qal_nand_adiabatic.py` — "any gate, settle not switch"

Validates the QAL *baseline* (not the aggressive non-restoring variant): a **real static logic gate**
computes by *settling* to its answer on a ramping supply, not by hard-switching. Vehicle: a static
CMOS **NAND2** (universal → any function) on SG13G2, powered by a ramping power-clock.

**Truth table** (Y at the supply hold, Vdd=1.2, T=1ns ramp) — the gate settles to the correct value:

| A | B | Y | NAND |
|--|--|--:|--|
| 0 | 0 | 1.200 | 1 ✓ |
| 0 | 1 | 1.200 | 1 ✓ |
| 1 | 0 | 1.200 | 1 ✓ |
| 1 | 1 | 0.000 | 0 ✓ |

- **Confirms: any gate, no gate-type limit, no dual-rail for completeness.** A real gate settles to its
  logic value as the supply ramps — the "settle, don't switch" saving.
- **Recovery/hold:** the pMOS-only pull-up can't pull Y below |Vtp| on the reset ramp — but that's not a
  logic failure: the output settles onto the *following* gate's input cap, which **holds the value**
  during the valid window, and the next stage captures it before reset. Clean adiabatic *recovery* wants
  a cross-coupled / dual-rail latch (ECRL/PFAL) or forward transfer.
- **Energy:** the clean settle-not-switch saving is the **A1b RC/T primitive** (→3.4% of ½CV² at a slow
  ramp); a gate's pull-up is just that Ron. The NAND's *direct* full-cycle energy here is
  bookkeeping-contaminated (the fixed-well second supply port, w=1.12µm parasitics, incomplete recovery)
  — the trend is adiabatic (E_diss falls with T) but the magnitude is taken from A1b, not these numbers.

## System level — `qal_sigma0_system.py` — σ0 datapath, baseline-QAL vs CMOS

**v2 — redone for the bank / switched-inductor architecture** (inter-bank inductors move power+data
bank→bank, ZCS, L layout-tuned to a fixed T_half; a small phase/antiphase resonator drives the switch
gates with recovered energy; flycaps top up the per-hop loss — *no* separate power resonator). Structure
(A0): σ0 = 61 XOR2, depth 2 → 2 gate-banks, 2 inter-bank transfers. Grounded in the anchor, A1b
(resistive RC/T), A1f (inductive π/Q). Result is a **band, not a hero number.**

**The honest bottom line:** the inter-bank inductor recovers the **rail/supply** energy (the
clock-elimination win). But the **gate logic still settles *resistively* through its own Ron** — so the
gate-level adiabatic saving is **RC-limited and speed-traded**, not the inductive hop. σ0's intrinsic
compute is ~0.29 pJ; the big QAL win is eliminating the clock floor + the 4× swing — **not** a gate miracle.

| regime | CMOS | QAL-fast | ratio | what it really is |
|--|--:|--:|--:|--|
| A naive/rigged (64FF, 1.2V) | 2.09 pJ | 0.015 | ~136× | unfair |
| B fair-marginal (32FF, 1.2V) | 1.19 pJ | 0.015 | ~77× | ~90% no-clock + swing |
| C iso-swing (32FF, 0.6V) | 0.30 pJ | 0.015 | ~19× | mostly no-clock (rail recovery) |
| **D iso-swing logic-only (0FF, 0.6V)** | 0.072 pJ | 0.015 | **~4.7×** | pure gate adiabatic, **RC-limited** |
| D vs QAL-*slow* (deep-adiabatic) | 0.072 pJ | 0.004 | ~17× | but only at **1.7 GHz** (speed-energy trade) |

- **Regime D correction:** at gate-RC-limited speed (~7 GHz, T≈3·RC_g) the gates barely settle and pay
  ~resistive-hard, so the pure gate-level edge is only **~4.7×** — landing at ~the v1 number but for the
  *right* reason (v1 wrongly modeled gates as inductive hops + carried phantom generator/freeze overhead;
  v2 removes that overhead via the bank arch + resonant switch drive, and the resistive gate-settle floor
  replaces it). The gate breakdown @36ps: rail 0.72 fJ + **gate 14.6 fJ (resistive, dominant)** + switch
  0.04 fJ. Slowing to T≫RC_g gets ~17× but at 1.7 GHz (slower than CMOS) — the adiabatic speed-energy trade.
- **What actually wins:** the clock/rail recovery (regimes A/B/C, ~19–136×, dominantly no-clock + swing),
  which the inter-bank inductor delivers by recovering the supply energy CMOS dumps as clock power.
- **Provenance:** hop/settle terms measured single-stage-ideal (A1b/A1f); bank C, resonator Q, chain,
  reset are **modeled** — a **projection pending Track C**. A2 per-hop energy stays quarantined.

**One line:** the bank/switched-inductor architecture is cleaner (no separate generator, resonant switch
drive), but the **gate logic is still RC-limited**, so the pure iso-swing adiabatic edge is ~5× at speed
(~17× slowed). The headline ~19–136× is a **clock-elimination + swing** story the inductor enables — not
a gate-level miracle.

## Gate-level crossover map — `qal_crossover_map.py`

Sweeps the gate time-constant RC_g and the operating ramp T; everything **normalizes on τ = T/RC_g**
(RC_g only rescales the Hz/fJ axes). Designed + fairness-checked as a workflow — it caught an
apples-to-oranges bug (comparing QAL's output-only ½C_g·dV² to CMOS's *full cell* energy). The fair
comparison is cell-to-cell: CMOS pays α·E_cell (only toggling cells), QAL pays f_adia·E_cell **every
beat** (no activity discount), so **E_QAL/E_CMOS = 2·f_adia = 4/τ** — anchor- and swing-independent.

| τ = T/RC_g | E_QAL/E_CMOS | speed (cons/aggr) | note |
|--:|--:|--:|--|
| **3** (speed ceiling) | **1.33×** (hotter) | **1.5× / 3.0×** faster | fastest, but 33% *more* gate energy |
| **4** (energy break-even) | 1.00× | — | parity |
| 6 | 0.67× (1.5× cooler) | — | cheaper, 2× slower than ceiling |
| 16 | 0.25× (4× cooler) | — | cheaper, 5× slower |
| 32 | 0.12× (8× cooler)* | — | deep-adiabatic (*floor-capped) |

**Two non-coincident crossovers → faster *OR* cheaper, not both at one T:**
- **Speed:** QAL runs **1.5× (conservative) to 3.0× (aggressive, double-banked) faster** than CMOS —
  *device-independent* — purely by shedding the register/clock tax (t_reg = k_reg·RC_g). Set k_reg→0 and
  QAL loses (0.33×): **register-elimination is the whole lever.** ⚠️ This holds **only for streaming /
  independent-lane workloads** (bulk hashing, 61-wide σ0 across blocks, **GPU-batched MC/defect/SIMT lanes
  — exactly the north-star GPGPU workload**). For **latency-bound serial recurrences** (single-stream SHA
  W[t], a..h round feedback) it **inverts** — QAL's multi-phase latency ≥ CMOS's cycle, CMOS wins.
- **Energy:** QAL is cheaper **only by slowing below its own speed ceiling** (τ>4): 1.5× cooler at τ=6,
  4× at τ=16, up to a **floor-capped ~3–9.5×** (Q-dependent; the energy-recovering resonant generator is
  *unbuilt* — as-built η≈1/3). Leakage adds a minimum at T*, beyond which QAL gets *worse*. Plus a
  stackable ~4× low-swing lever (raced separately vs near-Vt CMOS).
- **Both-win window is razor-thin:** conservative 4<τ<4.5 (≤12.5% faster *and* ≤11% cooler); aggressive
  4<τ<9 (up to 2.25× faster while still cooler).

**One line:** QAL buys **throughput** (1.5–3×, register-tax elimination, streaming only) *or* **energy**
(up to ~3–9.5×, by running slow) — not both at once, and neither for a latency-bound recurrence. The
throughput win lands exactly on the GPU-batched independent-lane workloads the north star targets.
Projection pending Track C (the high-Q resonant generator is the load-bearing unbuilt piece).

## Two-bank recycle + flycap top-up — `qal_twobank.py` — the actual power mechanism

First sim of the real bank/switched-inductor architecture (not the single A1f hop). Bank A (charged,
holds data) recycles its rail charge to bank B via the inter-bank inductor; B's flycap (pre-charged from
the rail) dumps into B through a *separate* inductor *simultaneously*. Realistic switches (Ron=50) **and
realistic inductor series-R (RL=20)** — the latter damps the fast L–Cjunction parasitic ring that made
the ideal-switch case abort at the resonant peak (per your directive; the damping *is* the loss).

| | V(B) peak | loss |
|--|--:|--:|
| recycle only | 0.556 V (−44 mV) | 0.485 fJ |
| **recycle + flycap top-up (Cfly=15fF)** | **0.600 V (full ΔV)** | 0.405 + 0.020 = 0.425 fJ |

- The flycap top-up **exactly compensates the recycle loss** → B lands at full ΔV, so the wave doesn't
  decay. A drains to ~0 (recycled forward). Loss ~0.42 fJ/hop ≈ 3% of the 14.4 fJ bank energy (Q-set by
  Ron+RL). This is the "flycaps add energy to compensate loss" mechanism, demonstrated with real damping.
  *(A cosmetic post-peak tail abort remains with the behavioral switch; peak+energies captured pre-abort;
  the SG13G2 device would fully regularize.)*
- **Dual-rail is NEEDED here — for the power delivery, not completeness.** The fixed top-up covers the
  loss for *this* bank charge; a single-rail bank draws a **data-dependent** charge (measured 100%
  modulation), so a fixed top-up would over/under-compensate and the wave amplitude would wander with the
  data. Dual-rail's constant differential sum (0% spread) makes the per-bank charge data-independent, so
  one fixed top-up sustains a uniform wave. So the recycle+topup architecture drives the dual-rail
  requirement, even though a settling logic gate alone doesn't need it.

## Switch sweep — `swsweep/` — the hop's energy lever is the SWITCH (2026-09-27, skeptic-verified)

Of the committed hop's E_hop 10.81 fJ (dV=1.0 iso-current row), series R burns 0.15 fJ, the
cells 1.04 fJ, and **~9.6 fJ is switch-related** — so the transfer switch was swept at T0
(TG total width 7.5–120 µm, nMOS-only, 2:1 TG, ±1 µm park device; TRUE-ZCS protocol,
probe-then-hop per design; pre-registered, `PRE_REGISTERED_SWEEP.json` + `AMENDMENT.md`;
skeptic recomputed all 14 rows from raw mt0s, 0 mismatches, and re-ran two points — tg15p
bit-identical). MEASURED results:

- **No interior W-optimum in range**: E_hop_open falls monotonically 11.31 → 10.66 → 9.6 →
  8.4 → 7.5 fJ from 120 to 7.5 µm (conduction loss never bites at iso-current, ~0.05 fJ flat).
  The shrink is stopped by rail-drain completeness (VA_open; 7.5 µm FAILS) and, below ~30 µm,
  by post-open ring — a **1 µm parking nMOS** with its own control phase is REQUIRED there.
- **Constrained optimum tg15p** (TG 5/10 µm + 1 µm park, 16 µm total vs the committed 60):
  E_hop_open **8.38 fJ = −21.6%** vs the ring-robust 10.69 fJ anchor, and **8.4% faster**
  (true zero 266.8 vs 291.3 ps — the zero moves earlier as the switch shrinks; energy and
  speed improve together). Per-gate-settle **1.048 fJ/gate** (conservative tg30p 1.195).
  **Three qualifiers travel with that number**: delivered at VBEND 0.676 not the committed
  0.576 (one-sided completeness reading; by the pre-registered two-sided band the strict
  optimum is tg60 and 1.343 fJ/gate stands as the committed-swing anchor — iso-swing retune
  NOT measured); cells burn 1.70 fJ at that swing (swing physics, inside the total);
  ideal-rails bookkeeping (tg15p imports +7.9 fJ/hop park drive-rail energy — the same
  convention forgives the committed design's −14.5 fJ export).
- **nMOS-only FAILS at every width** (rail never drains — source-follower stall, feedthrough
  pump, post-open droop; its low E numbers are artifacts), as does the 2:1 reduced-pMOS TG.
- **Committed-record corrections (amendment A2)**: the committed t_zcs=342.0 ps = true zero
  291.3 ps + a **+50 ps late-open artifact**, benign only at 60 µm whose own ~55 fF parks the
  interrupted-current ring (the convention does not transfer to smaller switches; the tg15p
  park restores graceful +50 ps behavior, −0.9% E_hop). Ring-robust anchor restatement:
  E_hop **10.69 fJ** (vs 10.81 D-snapshot), 1.336 fJ/gate.

## Zero-current detector — `zcd/` — per-hop analog ZCS REFUTED (2026-09-27, skeptic-verified)

The QAL admission carried the ZCD at an ASSUMED 30–300 fJ/bank/hop; a real one was designed
and measured (3-stage armed comparator, SG13G2/PSP103, 1.2 V rail, pre-registered bands).
Result: the 74 µV/ps zero-crossing signal **defeats the simple continuous-comparator class**
— at ~120 µA armed bias (144.3 fJ/cycle cheapest full arm-detect-reset) it NEVER fires on the
true held-closed zero within 878 ps (GBW-limited, gm/C ≈ 2.5e10 /s; delay ≥ 538 ps vs the
342 ps beat); its only fires lock on the switch-OPENING transient ~431 ps late (200.5 fJ),
useless for ZCS. Admission restated: **N_min ≥ 221** (≈289 at the fired configuration) — the
old 50–400 UNDECIDABLE band resolves **upward: every block in it is NOT ADMITTED**, none
improves. Surviving alternative: per-bank calibrated predictive timer (abandons per-hop
tracking; the 61.6 ps data-dependent spread becomes a level/settling-margin cost — modest
mistiming is energetically cheap per the committed record's own +50 ps openings). Switch–ZCD
coupling (skeptic, measured): the tg15p optimum steepens the sensing signal 5.1× (−376 µV/ps),
relaxing the ±20 ps offset need to ±7.5 mV (marginal, no longer hopeless) — the delay
refutation stands. Full record: `zcd/README.md`, `zcd/RESULTS.json`.

## The last door — `park/` + `amp/` — QAL admission at SG13G2 **CLOSES** (2026-09-28, skeptic-verified)

**THE QUESTION IS CLOSED, NOT OPEN.** The standing 17.911 fJ exclusion (`recov/`, af53111)
rested on ONE ideal-source booking, the park driver, and that booking is now **opened by
measurement and it does not save the block** — because the *other* ideal-source booking, the
sustaining amplifier, was simulated for the first time in the same round and it is what
excludes. Best **complete measured** ledger **23.213 fJ/bank/hop → N_min 75.60 → fpsat_fma
min-bank-63 FAIL**, against the pre-stated **E ≤ 12.7467 fJ** line. Even the composition of
**only the two measured terms** — track A's resonant park row and track B's measured amplifier,
with bias, rails, well-rail and multi-mode all set to zero — is **13.877 fJ → N_min 64.40 →
FAIL**. Margin 1.8–2.4× before any DERIVED term. Confidence HIGH.

Pre-registrations written before the first deck of each track and verified by hash:
`park/PRE_REGISTERED.json` (sha256 `735bdf2d…`, mtime 13:01:20) and
`amp/PRE_REGISTERED_TRACKB.json` (sha256 `cb699a67…`, mtime 13:00:08). All admission
arithmetic re-run through the **committed unmodified** `zcd/restate_admission.py`
(sha256 `ab946e0d…`, commit 9cad797, `git diff HEAD` empty), driven as a subprocess.

### Track A — `park/` — the park term is genuinely CLOSED, and it is not the problem

- **(d) NO PARK AT ALL is refuted by measurement.** All five completeness gates PASS and it is
  the cheapest drive of everything (3.0871 fJ), but the un-parked ring never damps: the
  delivered rail bleeds **−3.6 mV/ns = −2.1 mV per beat, forever**, vs −0.12 mV/ns with the
  park (30×). H2 FAILS by 1.81 mV. **The resonant waveform does NOT relax the swsweep park
  requirement.** The brief's "cheapest possible park is no park" is answered: NO.
- **(d) MERGE onto the gtp tap FAILS catastrophically and cannot be re-phased.** VBEND 0.077141,
  VA_open 0.38043, 96.3% of bank A gone before the hop starts; transfer nMOS turns on 8.841 ps
  **before** the merged park releases (make-before-break). Structural, all measured: conduction
  window 293.285 ps + required park window 286.715 ps = **580.000 ps = exactly the beat**, so
  any beat-rate park has **zero timing margin by construction**.
- **(c) SUB-HARMONIC (f/2) park tap WORKS on energy.** One more chip-wide inductor
  (L = 4·L1 = 23.6 nH at B=64), **no new gate, no switch, no clamp — zero recursion**. Park-tap
  cost **0.3436–1.3195 fJ**, and **−0.0398 fJ (a net RECEIVER)** on the narrowed 46%-duty tap,
  against a 9.7727 fJ headroom and the 15.0–15.5 fJ conventional-driver floor. The gap that
  collapsed the previous round is gone by **11–44×**.
- Best rows (pair + park tap, trapezoid, all five gates PASS at the pre-registered **absolute**
  tD = 811.755 ps): `pa_sub_w2` **3.9702 fJ** (VBEND 0.688560, E_hop 7.98053, H1 settle 70.4 ps,
  H2 **+1.438 mV better than baseline**) and `pa_subn` **3.5122 fJ** (VBEND 0.688192,
  H2 +1.010 mV, H1 settle 356.9 ps — a resonant park closes on a 5.7–6.5 mV/ps edge instead of a
  2 ps step, so it is weak early). Rows `pa_sub_w3`, `pa_subn_w15`, `pa_subn_w2`, `pa_sub_e_w2`
  are reported **INVALID** — they breach the pre-registered VBEND ceiling 0.68941 even though the
  direction is favourable. A two-sided gate was not moved.
- **H3, the most damaging completeness result in the round, and it indicts the COMMITTED design:**
  on a genuinely *periodic* two-beat drive **no park in this campaign releases in time**, and the
  committed one **never releases at all** — it is a rising edge that never falls; the bank drains
  to 0.127 V by tD. The div-2 park is correct for a **two-phase** pipeline only (`pa_subn`'s ON
  window [430.03, 963.75] fits the required [422.150, 1002.150] with 7.88/38.40 ps margin) — and
  **that reading is DERIVED**: this fixture has one stage and cannot simulate two.
- Track A declared its own pre-registered **H1 defective** (the committed baseline fails it,
  max |V(sw)| 0.76501 V, because the window opens before the park's own pull-down transient),
  restated it as settle-delay + max-after-settle, and published the raw number for every row.
  Goalpost moved once, in the open, after the baseline proved it unmeetable. Accepted.

### Track B — `amp/` — the sustaining amplifier is now a DEVICE, and it is what excludes

- **η_amp = 25.44% MEASURED** (skeptic 25.444% on an independent re-run; track B 25.46%), against
  a required **35.1% (zero bias) to 44.6% (worst-case bias)**. Cross-coupled nMOS pair with a
  **real** tail nMOS on a DC bias (not an ideal current source — that is the booking this campaign
  has been burned by three times), single-resonance LC, sg13_lv/PSP103.
- **In the currency that matters: E_amp = 12.600 fJ/bank/hop** — with the park at zero, the bias at
  zero and the rails assumed free, **the amplifier alone consumes 98.8% of the entire 12.7467 fJ
  budget** and leaves 0.15 fJ for everything else.
- **Where the supply goes (measured, fJ/bank/beat):** delivery 3.5607 (25.4%); **the amplifier's own
  three transistors 6.8491 (48.7%)** — tail 3.4346, M1 2.2011, M2 1.2135; tank series R 3.6026
  (25.6%). **The device term is Q-INDEPENDENT** (7.82/7.22/6.88/6.72/6.65 fJ at Q = 8/12/19/30/50),
  so **no inductor, no tank refinement and no extra resonant mode recovers it.** Even at Q = 50,
  far beyond any real 1.7 GHz on-chip spiral, η is 33.0% — still under the floor.
- **NO CLOCK.** The amplifier's only inputs are three DC sources (VA 0.85 V, VB 0.41 V, VBG 0.56 V);
  it self-oscillates and self-limits at 0.787 V / 579.00 ps off pure DC, settled by beat 3, last-5-beat
  spread 0.124%. Loaded **Q = 10.70 measured** against the required ≥ 7 that the *cut order* sets —
  **Q is not the binding constraint; energy is.** The QAL clock-elimination premise SURVIVES.
- **Track B's own completeness row is INVALID and says so**: a fundamental-only tank makes a sine,
  not the 5-harmonic waveform (VBEND −0.0541, VA_open −0.356, park closes 509.7 ps *before* the
  nMOS cut — the v2a park-early failure). η stays valid as an **upper bound** because every extra
  mode adds a lossy inductor.

### The cross-track ledger — the composition **neither track computed**

Each track passed only by zeroing the other's term: track A's PASS rows assume η_amp ≥ 0.35 and
track B **measured 0.254**; track B's 12.600 fJ PASS sets the park to zero and track A **proved the
park cannot be zero**. Amplifier modelled by track B's **own measured marginal** (dD 1.252 for
dE_sup 3.031, η_marg 0.4131) anchored on the measured E_sup 13.9941 at D 3.5607.

| row | E fJ | N_min | fpsat-63 |
|---|---|---|---|
| **[LINE] pre-stated admission** | 12.747 | 63.00 | PASS |
| [A] track A alone, η_amp ASSUMED 1.0 | 3.512 | 51.90 | PASS |
| [B] track B alone, park 0, bias 0, rails free | 12.600 | 62.80 | PASS |
| **[X1] `pa_subn` park + MEASURED amplifier — both measured terms only** | **13.877** | **64.40** | **FAIL** |
| [X2] + MEASURED tap DC bias 1.169 | 15.046 | 65.80 | FAIL |
| [X3] + rail generation, switching ×1.11 (DERIVED) | 16.701 | 67.80 | FAIL |
| **[X4] + VHI 6.5125 MEASURED on this row — best COMPLETE measured row** | **23.213** | **75.60** | **FAIL** |
| [X5/X6] + multi-mode m = 1.637 (DERIVED) | 25.742 / 30.542 | 78.60 / 84.40 | FAIL |

Per-block verdicts move together: at E ≤ 12.7467 the alu_top bush is 29/37 (99.6% of gates) and
sha_slice 4/10 (87.6%); at **every** FAIL row the alu bush drops to 28/37 (99.5%), sha_slice
unchanged. The fpsat min-bank-63 criterion is the binding one and it fails from X1 onward.

**Break-even η_amp for `pa_subn`** (measured 25.44%): **79.0%** with every measured term counted
(3.1× measured); 34.1% with VHI discarded; 30.3% with VHI *and* rails discarded; **27.6% with the
ledger stripped to the two terms both tracks agree are real** — the measured amplifier still misses
by 8%. **The exclusion does not rest on any single term: remove any one of the amplifier, the bias,
the rails or VHI and the ledger still fails.**

### The ideal-source inventory after this round

The campaign's lesson held again, twice: **the term booked from an ideal source was, again, the
thing that decided the result.**

- **IS1 park driver — CLOSED as a cost, NOT closed as a class.** The winning tap is still
  `VPKS pks 0 PWL(…)` + `RPKS pks pk 25` — structurally the same ideal-PWL-through-25 Ω booking as
  gt/gtp. Track A replaced an ideal PWL *step* with an ideal PWL *sinusoid*; the tap's own draw is
  measured, the mode behind it is not.
- **IS2 sustaining amplifier — NOW MEASURED**, and it is the exclusion.
- **IS3 the gt/gtp NETTING — the round's most valuable find, and it sits INSIDE both headlines.**
  The 2.974 fJ everyone treats as measured-and-closed is the **arithmetic sum** of a net exporter
  (E_gt −2.749 fJ, the Miller harvest) and a net importer (E_gtp +5.723 fJ) that are **two
  electrically unconnected ideal voltage sources** — there is no gt–gtp conductive path in the
  netlist. Adding them books a lossless bidirectional combining tank that **has never been built,
  metered or drawn**. E_pair(η_net) = 5.7232 − 2.7489·η_net. Once the amplifier is a real device the
  same swing costs **6.65 fJ (marginal) to 10.80 fJ (average-η) — 52–85% of the entire budget.**
- **IS4 tap DC bias — MEASURED** for the first time: Q_net/cycle gt +0.6234 fC, gtp +1.1837 fC,
  park div-2 tap +0.5134 fC per 1160 ps → **1.169 fJ at-tap**; the old 2.71 fJ bound is recovered
  exactly if those rails are made by *linear* regulation, i.e. it was the linear-regulator case all
  along. (Metering trap, caught and corrected: integrating the div-2 tap over one 580 ps *beat*
  gives 2.26 fC — half a cycle of swing, not a DC component.)
- **NEW — RAIL GENERATION.** Never costed anywhere in this campaign. The 0.85 V / 0.41 V / 0.30 V
  levels are assumed free and now multiply the **largest line in the ledger**: **×1.765 linear
  (+10.8 fJ/bank/hop on the amplifier term alone)** or **×1.11 switching (+1.57 fJ)** — and a
  switching converter **needs a clock**, reintroducing at the supply exactly what QAL exists to
  eliminate in the datapath.
- **NEW — MULTI-MODE SUSTAINER COUNT.** Track B built and measured **one** resonance; the waveform
  needs f, 3f, 5f, plus track A's f/2 — each its own inductor, own finite Q, own stored energy.
  m = **1.533–1.691×** (DERIVED from ω·C·A² with measured amplitudes and measured 5.8 fF tap load),
  worth **+1.3 to +5.6 fJ**. No 3-inductor tank has ever been built by anyone.
- **NEW — OXIDE OVERVOLTAGE, and it is campaign-wide and PRE-EXISTING.** Tap swings are chosen with
  no device-rating constraint. Against the **1.5 V** sg13_lv rating: committed baseline **XSWP Vgb
  1.8393 V**, XSWN Vgb 1.6004 V, XPK Vgd 1.5471 V; track A's **winning** row `pa_subn` **XPK Vgd
  1.8978 V (27% over)**, its park tap spanning **2.400 V (−0.900 → +1.500, verified directly in the
  deck's PWL table)**. PSP103 models no breakdown and `sg13lv_compat.sp` zeroes the junctions, so
  **nothing complains**. Sharpest form: track A used the 1.5 V oxide limit to *reject* the
  narrow-duty merge and then did not apply it to the row it *accepted*. **No rating-compliant tap
  has ever been shown to pass the completeness gates**, and both fixes (thick oxide, reduced swing)
  move energy the wrong way — the swing is what sets the cut order.
- **NEW — SUB-GROUND TAP STRUCTURE.** Track B *proved* by measurement that a sub-ground tap cannot
  come from a supply-referenced core (a cross-coupled pair clamps its own drain at the tail node)
  and needs a DC-block capacitor, an RF choke and a separate rail — for a swing of only −0.34 V.
  Track A's winning tap is **−0.900 V, 2.6× deeper, and booked at zero devices.** So track A's
  "adds NO new device anywhere" is correct on *recursion* (nothing's width tracks its load; the
  M1-C mode has no foothold) but wrong as stated: the winning row needs one f/2 inductor, a
  DC-block, a choke/bias network, the 0.30 V reference itself, and a fourth sustaining amplifier.
  **No recursion, but not zero devices either.**
- **NEW — THE PARK RELEASE (H3 above)** and **VBG bias-reference generation** (booked at gate
  leakage −0.0025 fJ, which silently assumes a chip-shared reference; a per-bank PVT-tracking
  reference would be a genuine M1-C recursion and nobody has established which case applies).
- **IS7 VHI n-well rail — re-measured, still homeless, and WORSE on track A's own winning row.**
  Independently confirmed from the raw `.prn` (t=0-referenced, full 1000 ps): `pa_base` **4.49426**,
  `pa_subn` **6.51254 (+44.9%)**, `pa_sub_w2` **5.07659 (+13.0%)** fJ/hop. **The resonant park makes
  the unbooked term bigger.** It is 35% of the entire budget and any ADMITTED verdict that omits it
  is void.

### Policing and instrument hazards — read before running anything here

- **NO ROW ANYWHERE IN THIS CAMPAIGN HAS A REAL AMPLIFIER DRIVING A HOP THAT PASSES THE
  COMPLETENESS GATES.** Track A passes all five only with ideal PWL taps; track B's real amplifier
  fails them outright. The energy ledger and the completeness ledger have never been satisfied by
  the same circuit. "The scheme has never been demonstrated end-to-end" is the accurate status.
- **★ CONCURRENT `PYMS_VAE_CACHE` BUILDS GIVE SILENTLY WRONG PHYSICS.** The skeptic raced two Xyce
  lanes 2 s apart into one cache; the PSP103 VAE build fell back (`full build failed …; retrying
  without zero-valued params`) and the contaminated run read **VBEND 0.729279 instead of
  0.684413 — a 6.6% error, enough to flip a completeness gate — with no error surfaced to the
  caller.** Serialising on a warm cache reproduced the committed value to the digit. **Every agent
  gets its own cache, built serially.**
- **The 1F-integrator idiom has a DC defect that affects existing rows.** The can sits at its
  DC-operating-point equilibrium, so (a) it carries a **pedestal** that reads as energy — verified
  directly: `V(XEGTP)` at t=0 is **+12.13 fJ** of phantom energy, `V(XEHI)` **+28.03 fJ** — so every
  read must be **t=0-referenced**; and (b) if the metered source carries a *steady DC current* the
  can integrates only the **change** in power and a rail at constant 36 µA reads as **ZERO**. Fix:
  force every integrator to 0 with `.ic` **and** raise `.print PRECISION` to 17.
- **E_hop_open is not independent of VBEND** (it tracks 0.5·C_eff·VBEND² with C_eff ≈ 34.7 fF), so
  the five completeness gates are effectively **four**.
- 7 of 11 `park/*.prn` predate their own deck (`gen.py` rewrote the decks at 13:28:50 after a
  duplicate-`CXEPK` fix). The two load-bearing stale rows were re-run and reproduce exactly —
  benign, but that is luck, not process.
- **Junction capacitance is ZERO everywhere**: `sg13lv_compat.sp` declares ad/as/pd/ps and then
  drops them. **Every energy number in this campaign is a LOWER BOUND.**

### What would have to change — PROJECTION, not measurement

Break-even η_amp is **79.0%** with every measured term counted, 3.1× what was measured, and the
device term is Q-independent so the tank cannot deliver it. 25.44% is **one topology, one agent,
one day** — it is not a proven lower bound on sustainer efficiency, and a fundamentally better
sustainer could beat a cross-coupled pair. But the ask is not small, the exclusion survives
deleting any single term, and the round also *added* uncosted terms (rail generation, multi-mode,
oxide compliance) faster than it removed one. Candidates that could move it — **all projection**:
a device node with lower gate capacitance per unit drive; **FD-SOI back-gate** (lower Vt → lower
VGH → lower CV², and the oxide-overvoltage problem eases); a two-phase pipeline, which the park
analysis says is **required** in any case. **QAL at SG13G2 is EXCLUDED and the question is closed
at this node.** Full record: `park/PRE_REGISTERED.json` + `park/RESULTS.json`,
`amp/PRE_REGISTERED_TRACKB.json` + `amp/RESULTS_TRACKB.json`.

## Swing/L optimum — `dvopt/` + `dvopt/skept2/` + `dvopt/load691/` — there is **no optimum in swing**, the L-optimum is real, and at the **real load QAL is 1.24–1.31× SLOWER than a CMOS logic level** (2026-09-28, skeptic-verified, load-corrected)

The user's ask was "run it at 1.5 V too, and any others needed to see if there's an optimum."
The **"1.2 V is the LV ceiling" premise was FALSE** — `nom_voltage` read out of all six
`sg13g2_stdcell` liberty files gives **1.08 / 1.20 / 1.32 / 1.35 / 1.50 / 1.65 V** on the
*identical* 84-cell library. Grid: 102 single-hop rows (54 functional) over those six swings ×
L = 3–277.8 nH × W ∈ {15,30,60,120,240} µm, plus a 28-row skeptic re-run at 1 nH/6 µm refinement,
plus a 9-row real-load excursion. Pre-registered (`dvopt/PRE_REGISTERED.json` 19:08:33,
`skept2/PRE_REGISTERED_SKEPT2.json` 20:16:59, `load691/PRE_REGISTERED_LOAD.json` 21:41:04, each
before its own first deck). Instrument: the committed robust point re-runs **rel 0.00e+00 on 9–11
quantities in both re-runs**, and a cross-harness check at 1.8× finer timestep agrees to ≤4.6e-04,
so the 1.5–3% optimum margins are resolvable.

- **No interior optimum in dV.** Every surface falls monotonically to the envelope edge: best
  functional level time 151.3 / 123.4 / 108.1 / 105.3 / 87.5 / 75.9 ps at dV = 1.08 → 1.65 V
  (2 fF load). The last step 1.50 → 1.65 V still buys 1.15×. **It is the 1.65 V characterisation
  limit, not a turning point in the physics, that stops the sweep.** `dV=1.5 was wrongly ruled
  out` is confirmed: 1.41× faster than dV=1.2, measured.
- **Interior optimum in L, real and bracketed** at 2 fF: at dV=1.65/W=30 µm the overlap objective
  reads 58.4 / 54.4 / 53.1 / 54.2 / 66.4 ps at L = 3 / 6 / 8 / 10 / 15 nH. The mechanism is the
  pre-registered one — t_hop ∝ √L against a settle floor that falls with delivered swing.
- **The settling floor, extended to 1.50 V** (20 points, 0.489 → 1.50 V; inverter 1.12/0.74 µm,
  2 fF, stepped supply): **51.505 → 40.417 → 32.811 ps at 1.00 / 1.20 / 1.50 V**. It flattens hard
  above ~1.0 V — the last 50% of swing buys 1.57×. Swing saturates **twice**: in that flattening,
  and again in the rail arrival becoming the binding term (ramp probe: the in-bank settle is 2.1%
  above the 2 ps floor at 0.714 V but 44.4% above it at 0.896 V).
- **THE LOAD CHANGES THE ANSWER.** Every row above is at a 2 fF cell load; the ALU's **measured
  mean sink load is 6.91 fF**. Re-measured there (`load691/`, instrument gate reproduces the
  committed `cl691_dv150` row to every printed digit): t_hop is unchanged (+0.26%, the load is not
  in the resonance), 20% of the delivered swing is spent on the load (VBEND 1.011 → 0.811 V at
  L=15), and **the post-arrival settle goes FLAT in L** (84.1–88.5 ps over L = 3–22 nH), so the
  hop stops being the binding term. Best functional level time at dV=1.65: **121.15 ps
  (L=10 nH, W=30 µm, drain gate at t_open+7 ps) to 115.47 ps (L=4 nH, gate at the ZCS instant) =
  1.244×–1.305× the 92.8 ps CMOS logic level.** The sub-CMOS single-hop numbers are a 2 fF
  artefact. Width is still not a free lever and under load it is worse: 30 → 80 µm at L=6 buys
  swing and drain but costs the level time 116.8 → 125.2 ps, because the narrow switch's
  overshoot (VBPK/VBEND 1.415 vs 1.208) drives the cells harder while they settle.
- **The two objectives do NOT defensibly select different points.** The reported SUM/MAX split
  rests on a floor-curve surrogate measured in a *different circuit*; rebuilt from the bank's own
  measured post-arrival settle the two surfaces swap shapes, and at the real load both select the
  smallest L the drain gate permits. The split is a light-load artefact.
- **THE BINDING GATE IS A CHECKPOINT CHOICE.** C2 (`VA_open ≤ 0.1478 V`) binds the entire grid, and
  `lsw.py` evaluates it at **t_open + 7 ps** where `sk.py` evaluates the same-named quantity at the
  **ZCS instant** — 2.2×–6.9× apart (at the reported optimum V(bka) = +0.0615 at ZCS, +0.1368 at
  +7 ps, **+0.509 at +20 ps**, −0.0005 at the end: the gate reads a fast post-open ring, not a
  drained rail). 10 of 86 rows sit within ±10 mV of the line and two committed-FUNCTIONAL dV=1.50
  rows clear it by 0.5%/0.9%. **Every optimum LOCATION here rests on that checkpoint; the measured
  level times do not.** Pick one instant and justify it physically before the next track quotes L*.
- **2-high stacks: settling is RESCUED at dV=1.65, the speed case is not.** `sg13g2_o21ai_1`'s
  series-pMOS pull-up reaches 99.6–100% of rail at *every* characterised swing on an ideal supply —
  **no headroom cliff anywhere in the envelope**, it is simply 3.1–3.6× slower than an inverter at
  equal supply. In a real bank it settles inside the committed 500 ps window at dV=1.65
  (t_valid90 = 495.5 ps at L=15/W=30, 406.2 ps at L=6/W=120) and at dV=1.5 given a 710 ps window;
  the old "never settles at ANY operating point" was a **delivery + window** failure, not a
  headroom failure. But 406–507 ps is **4.4×–5.5×** the CMOS level against 0.80× for the
  shallow-stack bank at the same swing, and the convergence is 38% rail-falling-to-meet-the-output
  (`VA_open` is NEGATIVE on every o21ai row: the unsettled stack conducts DC). **So admitting
  2-high stacks is a CORRECTNESS option, not a speed one — QAL stays a shallow-stack
  (inverter/NAND2-class) backend, and the next lever is DELIVERY, not more swing.**
- **Cross-link, and it bounds everything above:** these are SINGLE hops with ideal cell gate drive.
  In a chain (`chain3/`, `skip4/`) nothing settles at any beat period at all — t_settle is not even
  finite — and raising dV to 1.65 V cannot fix it: scaling `skip4`'s measured rails by the
  dV-invariant delivered fraction lifts the depth-2 rail only from 0.56–0.58 V to ≈0.62–0.64 V
  (DERIVED), where this track's own floor curve says a cell needs ≈170–200 ps against a ~105 ps
  beat. **The optimum located here says where to operate a hop; it does not make a pipeline run.**

Full record: `dvopt/RESULTS.json` + `REPORT.txt` (102-row grid), `dvopt/skept2/REPORT_SKEPT2.txt`,
`dvopt/load691/RESULTS_LOAD.json` + `surfaces_load.json`, amendments alongside each.

## Threshold requirement — `vtreq/` — **a reachable threshold makes the QAL HOP faster than CMOS; no threshold makes the QAL PIPELINE exist** (2026-09-29)

The user asked plainly "can QAL be faster?"  The measured answer on SG13G2 was NO, and it reduced
to one device number: `|Vtp| = 0.4403 V` against a ~0.75 V hop-delivered rail.  This track turns
that into a **requirement** — what threshold would QAL need, and what does buying it cost — by
sweeping PSP103's `DELVTO` (an instance parameter that adds directly to the flatband voltage;
verified on disk in the generated `eval.cpp`: `VFB_T = ... + DELVTO_i - 0.69967...`) over
0 / −0.05 / −0.10 / −0.15 / −0.20 / −0.30 V applied to **pMOS only, nMOS only, and both**.
Pre-registered (`vtreq/PRE_REGISTERED.json`, sha256 `147e2964…`, 23604 B, 01:50:10, the only file
in the directory at that instant); eight amendments A1–A8.

**THE TRAP THE TRACK EXISTS TO AVOID — lowering Vt makes CMOS faster too.**  Every level row carries
a CMOS comparator measured under the **identical** shift, on the **identical** cell (1.12/0.74 µm)
and the **identical** 6.91 fF load.  The committed 92.8 ps figure is a *synthesis/STA* number and
cannot be `DELVTO`-swept, so it enters only through a relative-gain layer — and, usefully, the
device-level comparator lands within 1.5 % of it at `DELVTO = 0` (94.17 ps vs 92.8 ps).

- **INSTRUMENT: 14 of 14 committed anchors reproduced**, several to every printed digit — real-load
  level `115.467185 ps`, `VBEND 0.754572966`, `VA_open 0.11745601600934541`, the L=3 nH row
  `115.702871 ps`, the single hop's `VBEND`/`VBPK`/`IPK` at rel **exactly 0.0**, the dvopt floor
  deck's CMOS check `57.1427` vs `57.1429 ps`, `Vtn`/`|Vtp|` within 41/10 µV of `chain3/vt.json`,
  the o21ai bank's `495.51 ps`, and the 6-bank chain's committed separation series
  **528.68 / 22.89 / 1.52 / 0.122 / 0.010 / 0.001 mV including its sign pattern**.
- **THE PARAMETER REACHES THE DEVICES, and orthogonally.**  `d(Vtn)/d(DELVTO_N) = 1.000` V/V,
  `d(|Vtp|)/d(DELVTO_P) = 1.004` V/V, **cross terms exactly zero** (identical to 6 decimals).
  This campaign's oldest failure mode is closed by measurement, not assertion.
- **Q1 THE LEVEL — the wall MOVES.**  At the committed `L = 4 nH` the ratio only goes 1.2261 → 1.0052.
  But `t_hop = π√(LC/2)` has **no threshold in it** and is MEASURED invariant (+0.11 % over the whole
  sweep) while the settle term collapses ×0.42 — so the hop becomes 50 % of the level, and the
  binding lever is the inductor.  At `DELVTO = 0` the rail-drain gate C2 **excluded** small L
  (`VA_open +0.263` at L=1 nH); a lower threshold makes the switch strong enough to drain the source
  bank in a shorter hop and the same row reads `+0.099`.  **The threshold shift is what re-admits the
  small inductor** (EXPLORATORY, amendment A5).  With L re-optimised: **PARITY at |Vtp| ≤ 0.24 V /
  Vtn ≤ 0.32 V** (L\* = 1 nH, 0.743 V delivered rail, ratio 0.9426; within 0.2 % of parity already at
  |Vtp| = 0.29 V) and **a 12 % BEAT at |Vtp| = 0.139 V / Vtn = 0.224 V** (L\* = 0.7 nH, ratio 0.8782)
  = 0.891×–0.935× on the committed STA anchor.  **Caveat stated once and loudly:** on the MEAN-edge
  convention parity is never reached (best 1.0467), and the whole difference is the campaign cell's
  1.83:1 rise/fall imbalance — a *cell-sizing* property, not a QAL property.
- **Q2 THE CHAIN — the wall does NOT move, and the reason is not a threshold.**  Depth of usable
  logic (separation POSITIVE and above the PDK's σVt = 3.42 mV) goes **1 → 2 → 3 → 4 banks** as the
  shift deepens (0 → −0.15B → −0.20B → −0.30B).  Depth 5 is **unreachable at every swept point** —
  best +0.0597 mV, 57× below the floor, and of the **wrong sign** at the most favourable point.
  MECHANISM: the rails collapse by a MEASURED **0.61–0.66 per hop**, a charge-over-capacitance ratio
  that a threshold cannot touch and that gets *slightly worse* as Vt falls (0.659 → 0.611).  DERIVED:
  depth 10 sits at a **6–14 mV** supply, so it needs `|Vtp| ≲ 10 mV` — within ~3σ of **zero** against
  this PDK's own 3.42 mV threshold spread.  **That is a threshold nobody can build.**  σVt
  sensitivity: depth 4 flips only at 2.4× the PDK σVt; depth 5 would need σVt 57× smaller.
- **Q2 also refuted my own pre-stated mechanism, and it is recorded as a miss.**  E2 predicted the
  chain would get WORSE as |Vtp| fell, because the stranded HIGH tracks |Vtp|.  The DC physics is
  CONFIRMED (strand tracks |Vtp| at **0.81:1**; the receiver trip point moves **−0.485 V/V** of pMOS
  DELVTO and **+0.463 V/V** of nMOS DELVTO, so the DC gap `strand − trip` is opened by lowering |Vtp|
  and turns positive at Vtn ≤ 0.374 V) — but it is **not the binding term**: at a collapsed rail the
  limiter is the successor's own pMOS pull-up, which a lower |Vtp| repairs.  Right physics, wrong term.
- **Q3 THE COST — the cure does NOT cost more than the disease, anywhere.**  Static hold current per
  8-cell bank rises **4544×** (2.81e-10 → 1.28e-06 A) at **82 mV/decade**, but the held rail loses only
  **1.3–4.3 mV per 120 ps beat** against a 754 mV rail — 5–20× smaller than the committed settling-era
  −20.2/−28.6 mV hold droop.  DERIVED, the beat period at which leakage equals the measured
  15.2–29.1 fJ/bank/hop falls 72 µs → 16 ns, still ~130× longer than the beat.  My pre-stated E3
  ("> 100 mV of droop") is **magnitude-REFUTED**; direction and slope confirmed.
- **2-HIGH STACKS (`sg13g2_o21ai_1`, the Vortex ALU's dominant mapped cell): gains most, changes
  nothing.**  Its ratio to a same-load same-DELVTO CMOS level falls **8.671× → 4.772×** (×0.550)
  against the inverter bank's ×0.820 — E4 confirmed, two threshold drops in series instead of one —
  but 4.77× is still 4.77×.  **The shallow-stack library restriction STANDS and a threshold does not
  lift it.**
- **WHAT THIS CHANGES:** the committed line "at the real load QAL's level is SLOWER than a CMOS level
  everywhere in the PDK envelope" (`88a0306`) is a `DELVTO = 0` statement; at |Vtp| ≤ 0.24 V it is
  false, measured.  **WHAT IT DOES NOT CHANGE:** `MAX k = 1` (`e4c980b`) relaxes to roughly `MAX k = 4`
  at a threshold nobody has offered to build, and the throughput case needs depth 10.  **The next
  lever this run points at is NOT the threshold** — it is the rail-collapse ratio (a larger/unequal
  source bank, or a keeper per output, i.e. the register back).
- **Scope, restated:** body bias remains PARKED; there is no FDX PDK here and none is claimed.
  `DELVTO` is a device-parameter sensitivity sweep answering "what would be needed".  `shim_dvt.sp`
  inherits the committed shim's zeroed `ad/as/pd/ps`, so every number is a LOWER BOUND, and that cuts
  both ways here.  The committed energy EXCLUSION verdict (`c814e52`) is untouched.

Full record: `vtreq/RESULTS.json` + `vtreq/TABLE.txt` + `vtreq/SUMMARY.json`, per-point rows in
`vtreq/rowd/`, amendments in `vtreq/AMENDMENT.md`.

## Measurement discipline

Per `QAL_PLAN §7` and `feedback_no_self_baseline`: everything in Track A runs against an
**ideal trapezoid source** (no generator non-idealities folded in yet — that's Track C),
and validation is against transistor-level Xyce (SG13G2 / PSP103), never our own model.
