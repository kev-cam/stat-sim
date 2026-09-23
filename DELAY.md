# stat-sim delay tier — statistical delay simulation from cell-level MC

The delay tier (`statsim_delay.py` + `models/ncl_th_delay.json`) is the
delay-variability case of the US8478576B1 probability-waveform method, built to
answer one question:

> How do you get the timing and reliability of a **big** design (an ALU, a GPU
> datapath) under transistor-level process variation, when transistor Monte-Carlo
> only scales to a few hundred devices?

**Answer:** Monte-Carlo at the **cell** level once, turn each cell into a
probability model, then **simulate** the composed design by propagating those
per-cell distributions — no transistor solve in the loop. A 4726-cell ALU is
~100k+ transistors (SPICE-infeasible); this tier predicts it in milliseconds.

This complements the metastability/CDC tier (`genmodel.py`, see `README.md`):
same probability-waveform idea, but for **propagation-delay** variation of
combinational cells instead of flip-flop metastability.

---

## The three-ingredient model

A composed design's completion time is a sum of per-stage cell delays along its
critical path. Each ingredient below is characterized ONCE from cell-level MC and
then composes to any size:

1. **σ_frac (mismatch sensitivity) — the reliability quantity.**
   `σ_frac(kvt) = sd/μ` from a cell's Vt-mismatch MC. It is ~linear in the
   mismatch scale `kvt` (zero-mean per-device Vt adds spread, not bias) and — the
   key result — **transfers across timing arcs**: it is a cell property, not an
   arc property (verified within ~5% across th34w2's weight-1 vs weight-2 arcs and
   th23's carry-in vs a-set arcs). So reliability composes regardless of which arc
   a design exercises.

2. **In-context per-stage μ — the absolute-delay quantity.**
   A cell's delay depends on its arc AND its in-context loading. The delay of a
   gate driven by a *real* prior stage and driving its *real* fanout (`t_ctx`) is
   larger than an isolated single-arc measurement (e.g. th23 carry: 358 ps
   in-context vs 245 ps isolated — the extra is real-cell RC fanout + NCL
   dual-rail completion + coincident DATA arrival, NOT slew degradation — the
   th23 output slew is a fast 143 ps). `t_ctx` is a **tileable** primitive
   (middle stages of a chain are identical), with faster boundary stages
   (`t_first` primary-input, `t_last` lightly-loaded output). Chain mean:

   ```
   μ(N) = t_first + (N-2)·t_ctx + t_last
   ```

3. **Inter-stage correlation — closes the σ composition.**
   Independent-RSS σ under-predicts by 7–14% (growing with N) because a mismatch
   that slows a stage also degrades the edge it hands the NEXT stage — **local
   slew coupling** ⇒ adjacent stages are positively correlated. A nearest-neighbor
   model (`ρ0≈0.10`, chosen over uniform/exp-decay by a candidate panel because
   uniform implies a spurious σ_frac floor) closes it:

   ```
   Var(chain) = Σ σ_i²  +  2·ρ0·Σ σ_i·σ_{i+1}       (σ_i = σ_frac(kvt)·t_stage_i)
   ```

   This keeps the physically-correct ~1/√N averaging (bounded √(1+2ρ0)=1.096
   inflation), not a hard floor.

---

## How to do this for a new cell family (reproduce / extend)

1. **MC-characterize the cells** (transistor-level, Vt mismatch). See
   `mylex nulex/asic/chr/mc/` (PolyForm): `gen_mc.py` injects an independent
   per-device `DELVTO=AGAUSS(0,kvt·σ_Vt,1)` (Pelgrom `σ_Vt=A_Vt/√(W·L)`) into a
   cell subckt; run Xyce `.SAMPLING` (`SAMPLE_TYPE=MC`) at `kvt=1..4`; `analyze_*`
   extracts per-cell delay mean/sd. The PyMS runtime-callback path
   (`PYMS_CALLBACK_PARAMS=DELVTO`) keeps DELVTO live so one `.so` per geometry
   serves all samples (no per-sample rebuild).
2. **Characterize the arcs you need in context.** `gen_arc_deck.py` isolates a
   specific input arc at a realistic fanout load. For chain μ, probe the internal
   nodes of a small composed block (e.g. the ripple carries) to get `t_ctx`,
   `t_first`, `t_last`.
3. **Calibrate the correlation** `ρ0` against two composed-block sizes (fit at one,
   confirm at the other). Nearest-neighbor with ρ0≈0.1 held for the SG13G2 NCL
   carry chain across N=4 and N=8.
4. **Fill `models/ncl_th_delay.json`** — `cells` (μ,sd per kvt), `arcs`,
   `in_context_carry_ps`, `inter_stage_correlation`, and `ground_truth_*` for
   validation.
5. **Predict + validate**: `predict_ctx(models, N, kvt)` → (μ, σ); check against a
   small composed-block MC. `simulate_path()` handles arbitrary cell sequences.

## Run

```sh
python3 statsim_delay.py --validate   # reproduce the FA / nclfa4 / nclfa8 checks
python3 statsim_delay.py --scale      # predict N-bit ripple reliability (no SPICE)
python3 statsim_delay.py --self-test  # MC==analytic SSTA; single-cell reproduces model
```

## Validation (SG13G2 NCL, vs transistor MC)

| design | depth | devices | µ error | σ error (with correlation) |
|--------|-------|---------|---------|-----------------------------|
| nclfa (full adder) | 1 gate | 60 | — (arc-in-context) | ~12% (1-gate, single-arc) |
| nclfa4 (4-bit ripple) | 4 | 240 | 0.05% | −0.3 … +1.7% |
| nclfa8 (8-bit ripple) | 8 | 480 | 0.1–1.2% | −0.4 … +3.6% |

µ closed to ≤1.2% and σ to ≤4% at both composition depths — with the model
seeded only from cell-level MC (the σ prediction is non-circular). Predictions
run in <1 s vs ~15 min–hours of transistor MC, and reach sizes SPICE cannot.

## Caveats / refinements

- **Absolute µ** needs the *in-context* per-stage delay (loading + dual-rail
  completion), not an isolated single-arc number. Extract it from a small
  composed block; it tiles.
- **ρ0** here is calibrated for the SG13G2 NCL carry chain (local slew coupling).
  Re-calibrate per cell family / composition style; an exp-decay kernel is
  available if two sizes don't pin nearest-neighbor.
- The tier models **delay** variation; use `genmodel.py` for flop metastability.

## Provenance

Cell + composed-block MC data and decks: `mylex nulex/asic/chr/mc/`
(`RESULTS.md`, `RESULTS_nclfa.md`). Model here:
`models/ncl_th_delay.json`. This tier is PolyForm-Noncommercial like the rest of
stat-sim (`LICENSE`).
