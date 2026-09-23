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
| A2 | how does the swing-vs-margin coefficient `k(ΔV)` behave down a chain? | stage chain | pending A1 |
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

## Measurement discipline

Per `QAL_PLAN §7` and `feedback_no_self_baseline`: everything in Track A runs against an
**ideal trapezoid source** (no generator non-idealities folded in yet — that's Track C),
and validation is against transistor-level Xyce (SG13G2 / PSP103), never our own model.
