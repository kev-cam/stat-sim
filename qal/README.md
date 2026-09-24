# QAL — Quasi-Adiabatic Logic as a third Mylex RTL backend

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

**Not yet shown:** realistic on-chip L (nH, real R) efficiency; the return/reset path (re-arm A); a
multi-stage chain (does the wave propagate, does loss compound); explicit data-carrying; dual-rail;
device switches + Vt; the Track-C generator driving it.

## Measurement discipline

Per `QAL_PLAN §7` and `feedback_no_self_baseline`: everything in Track A runs against an
**ideal trapezoid source** (no generator non-idealities folded in yet — that's Track C),
and validation is against transistor-level Xyce (SG13G2 / PSP103), never our own model.
