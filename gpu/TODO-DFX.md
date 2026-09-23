# TODO — DFX (defect simulation & analysis) tier

**Status:** design note / not started. Captures how the DFX methodology (user's patent
**US20230334213A1**, "Analog/mixed-signal defect simulation and analysis methodology") slots into
the GPU reliability engine built here. Pick up later.

## Where DFX fits
DFX is the **defect/fault sibling** of the parametric-variability tier already built (the Vt-mismatch
MC → SSTA timing-yield in this dir). Same architecture both sides: *characterize once at cell/block
level → reduce to a compact model → compose at scale without re-running transistor sim.*

| tier | characterize | compact model | compose → | fab needed? | status |
|------|--------------|---------------|-----------|-------------|--------|
| parametric variability | per-cell Vt mismatch → (μ,σ) | delay distribution | timing YIELD | no | **built, GPU-proven** |
| **DFT** (design-for-test) | per-block defects → behavioral **bins** | per-bin model + fault | defect COVERAGE / test grade | **no** | **buildable now** |
| DFY (design-for-yield) | + real defect density, test-escape | calibrated bin likelihoods | YIELD prediction/opt | **YES — fab partner** | gated |
| device engine | analytic LTI/NLDM stage | closed-form propagator | transistor-accurate MC | no | feasibility-proven |

## Scope split (user, 2026-09-23)
- **DFT — do this first, no fab.** The behavioral bins ARE the analog/MS fault list. Everything is
  in-sim: inject defects, bin behaviors, generate tests that separate the bins, grade coverage.
- **DFY — needs a fab partner.** Real defect densities + manufacturing test-escape correlation are
  external ground truth; predicting a yield number without them is self-baselining (avoid). Defer.

## DFT build plan (in-sim, on the GPU defect-lane engine)
1. **Defect injection + binning (patent core).** For a block, enumerate defects (opens/shorts/
   parametric shifts), transistor-sim each, categorize outputs into bins (fail/degraded/usable/good);
   collapse defects with equivalent behavior (the order-of-magnitude reduction). Reuse the mc/ +
   PSP103 machinery (see the DELVTO callback flow — and its cache-invalidation fix, xyce commit
   71d0b770). Note: emit per-bin behavioral models (NN/LMS or manual) for hierarchical reuse.
2. **GPU defect-lane batching.** Extend `ssta_alu.cu`: each LANE = a defect scenario (instead of a
   Vt-mismatch draw); the per-lane compact model is the bin behavior. Reuses the shared-driver +
   coherent-draw + lane-batching machinery already proven — a *defect axis* alongside instances × kvt.
3. **Test generation + grading.** Generate stimuli that flip bin boundaries; grade which tests detect
   which defect bins across the batch. This is the analog/MS fault-coverage the digital ATPG pipeline
   lacks — plug into the existing atalanta ATPG / verify-then-promote certificate work (stuck-at for
   digital, defect-bins for AMS).

## DFY plan (when a fab relationship exists)
- Ingest real defect-density maps + test-escape data; calibrate per-bin defect likelihoods.
- Close the synth↔sim yield-sensitivity feedback loop (patent's DFY); back-annotate parasitic defects
  via the same binning; mark blocks (e.g. metal-layer-insensitive) for the router.
- Validate against silicon (no self-baseline).

## For the north-star (older-node GPGPU at reduced power)
Defect/fault yield matters MORE on an older node (higher defect density) — DFY is a first-class
reliability dimension alongside the DVFS timing-yield work (see gpgpu_older_node_target). DFT is the
buildable-now down-payment; DFY unlocks with a fab.

## Start here
The smallest prove-or-kill: take one already-characterized block (e.g. the th23 cell or an add8
datapath), inject a handful of defect classes, bin the behaviors, and run the binned scenarios as GPU
lanes to produce a defect-coverage number for a candidate test set. That exercises inject→bin→batch→
grade end-to-end without a fab and reuses the existing PSP103/MC + GPU batching.
