# Amendments to `qal/mcsize/PRE_REGISTERED.json`

Pre-registration: sha256 `a99fdd70e0e0b9f64812d55502ae53a78b7c3e4f8dd2a69f12f607e95ab4ef6b`,
17208 B, mtime **2026-09-29 14:38:29.545 -0700**. Every amendment below records the
fact that forced it and the mtime proving the ordering.

---

## A1 — `qal/fcrit` EXISTS after all, and its criterion is ADOPTED

My pre-registration states (§4) "CHECKED FOR AND ABSENT: no qal/fcrit … exists under
/usr/local/src/stat-sim as of this file's mtime". That was true of the directory listing
I took, but **incomplete as a claim about the sibling run**: `qal/fcrit/` was created at
**14:33** and its `PRE_REGISTERED.json` written at **14:35:08.042 -0700**, i.e. 3 min 21 s
BEFORE mine. I discovered it at 14:41 when a process listing showed
`Xyce /usr/local/src/stat-sim/qal/fcrit/trip_S.cir` running.

**The brief's instruction is to use fcrit's criterion if it is on disk. It is, and I do.**
§4 of my pre-registration is superseded by `qal/fcrit/PRE_REGISTERED.json` §THE_CRITERION,
with the two declared departures A3 and A4 below. This is the correct outcome, but I
record it as a miss: I asserted absence from one `ls` instead of re-checking before
locking the file.

## A2 — N raised 200 → 300 for DUT_A (allowed in advance by §5)

§5 pre-authorised raising N "if a DUT's per-run cost measures cheaper than budgeted".
MEASURED per-sample cost for the stripped DUT_A deck: **17.74 s of solver time**
(`bt_nom.log`, "Total Simulation Solvers Run Time: 17.7383 seconds"); the 201 s wall of
that run was a one-time PyMS `.so` build, not per-sample cost. N = 300 in 3 concurrent
chunks of 100 (seeds 2001/2002/2003) therefore costs ~30 min wall.

Consequence for the headline: rule-of-three upper bound on the failure rate at 0 failures
improves from 1.50 % to **1.00 %**.

## A3 — the noise budget is NOT fcrit's full NB, because that would DOUBLE-COUNT

fcrit's `NB = 3*sigma_trip + coupling_step + held_rail_droop`, with
`3*sigma_trip = 19.323 mV`. That first term is a **static allowance for exactly the
random Vt mismatch this study draws explicitly per sample**. Charging it again inside an
MC that has already drawn the mismatch counts the same physics twice.

The MC is therefore scored at **NB = the deterministic terms only** (coupling + droop;
both are ZERO for DUT_A, a free-running no-top-up chain — fcrit's own `NB_notopup`
configuration reduces to `3*sigma_trip` alone). That is fcrit's own "NB = 0, pure
threshold crossing" column, which fcrit already commits to reporting beside every table.
fcrit's full 19.323 mV budget is **also** reported for every point, labelled as the
conservative variant that double-counts the random term. Neither is hidden.

## A4 — CORRECTION to fcrit's commit instant, and both instants reported

fcrit sets `t_commit` = the receiving bank's ZCS/open instant, justified by its claim (ii):
"the receiving cells' pull-up path can no longer reach any level it has not already
reached, so a receiver output on the wrong side … can only get relatively worse."

**Claim (ii) is false on the committed waveform.** In `qal/resv/ch_res20/c_res20.cir.prn`,
`V(o6_0)` rises **0.15906 → 0.34466 V** between the open instant (1821.43 ps) and the
committed boundary (2000 ps) — a 186 mV improvement AFTER the charge island is cut. The
mechanism is that the cells keep settling out of the now-floating rail's OWN capacitance;
the inductor is not the only source. The same effect is decisive in DUT_A: at the open
instant the nominal chain's worst margin is **−55.43 mV (13 of 24 gates wrong)**, and at
the bound instant it is **+278.51 mV (0 of 24 wrong)**.

fcrit's own document invites this: it says of claim (ii) "if [it does] not hold, the
definition is wrong and I will say so." It does not hold.

Both instants are scored and both reported. **`bound` (= c_k + T) is PRIMARY** — it is
what every committed extractor samples, and it is the instant the beat schedule actually
allows the next stage to look. `open` is reported as the harsher variant and its nominal
failure is reported as a nominal failure, not smoothed over.

## A5 — cache isolation instead of the prescribed cache CLEAR

`qal/run_a3_mc.sh` prescribes `rm -f /tmp/pyms_hdl_cache/pyms_*.so` to defeat the
stale-device-shell trap. At 14:41 **five** Xyce processes from three other workflows were
live against that shared directory (`p_anchor_static_o21ai_hb_dv150.cir`, `leak_bias.cir`,
`b_T260.cir`, `b_T300.cir`, `fcrit/trip_S.cir`). Deleting a shell out from under them
would have corrupted other people's runs.

Instead this study sets **`PYMS_CACHE=/usr/local/src/stat-sim/qal/mcsize/pyms_shell`**
(the env var `N_DEV_PyMS.C:546` honours, defaulting to `/tmp/pyms_hdl_cache` only when
unset) plus its own `PYMS_VAE_CACHE=.../mcsize/vae_cache`. Both were empty directories, so
the shell was built from scratch — which is what the clear was FOR — with zero blast radius.
Verified: `nm -D pyms_shell/pyms_PSP103VA.so | grep -c getCbParam` = **1**, i.e. the freshly
built shell exports the runtime-callback getter.

## A6 — CORRECTION: the compat shim does NOT eat the random parameter

`qal/qal_a3_mc.cir`'s header states the devices are inlined as direct M-lines because the
"compat shim would eat the random param" and the nested-subckt wrapper "silently kills
AGAUSS sampling". **Measured here, that is not so.** `shim_mc.sp` is the committed
`sg13lv_compat.sp` with one added `dvt=0` parameter forwarded to `DELVTO`, and in
`b1_indep.cir` the shim path and the direct M-line path give **identical** sensitivity to
6 decimal places (both +9.991166 mV for a commanded +10 mV). Both chain DUTs are therefore
MC'd through the shim they were committed with, rather than being re-netlisted — which
removes a whole class of "did you change the DUT" doubt.

## A7 — CORRECTION: A_VT was ASSUMED in the inherited harness and is wrong for both polarities

`qal/qal_a3_mc.cir` header: "sigVt = A_Vt/sqrt(W*L) = 3.5mV.um / sqrt(10u*0.13u)". The
3.5 mV·µm was never read from the PDK. The PDK's own mismatch lib carries **0.0039 V·µm
for nMOS and 0.0022 V·µm for pMOS** — so the inherited constant is 11 % low for nMOS and
59 % HIGH for pMOS, and applying one number to both polarities is wrong in principle.
See PRE_REGISTERED §1 for the extraction and its three-way cross-check against
`qal/vtaudit/AUDIT.md`.

## A8 — three declared cost reductions to the DUT decks, with a digit-level self-test

`mkmc.py` drops (1) the `.print` block, (2) the 1F energy integrators `CX*/BX*/RX*` and
their `.measure` lines, (3) the transient tail past the last commit instant the criterion
needs. (2) is electrically inert: those elements hang on their own isolated nodes and
drive nothing. (1) and (3) are output/duration only.

**Self-test, DUT_A** — the stripped, truncated deck reproduces the committed
`HEADLINE_pre_registered_point` rails:

| quantity | mcsize `bt_nom` | committed banktank | delta |
|---|---|---|---|
| rail2 @ bound_2 | 0.676724 V | 0.67672 V | +0.0039 mV |
| rail3 @ bound_3 | 0.731246 V | 0.73125 V | −0.0044 mV |
| rail4 @ bound_4 | 0.720088 V | 0.72009 V | −0.0023 mV |

84 integrator lines dropped, 76 mismatched devices, 102 measures.

## A9 — DUT_B's depth is cut by a NOMINAL failure, exactly as pre-stated in §6

PRE_REGISTERED §6 `expectation_about_DUT_B_nominal` predicted DUT_B would fail the
functional criterion at bank 6 with zero mismatch. **It does, and through its own in-deck
receiver** — but the mechanism is not the one I guessed. Details in RESULTS; the
pre-stated prediction was right about the outcome and wrong about which threshold does it
(I said both candidate trips; in fact the rail-referenced criterion PASSES at bank 6 and
the absolute/hard-supplied one FAILS). DUT_B's mismatch yield is therefore reported at the
deepest bank that passes nominally, and the bank-6 nominal failure is reported as a
nominal failure.

## A10 — three errors in MY OWN analysis code/reasoning, caught and fixed in-flight

Recorded because the campaign's rule is that a caught error goes on the record, not just
the fix.

1. **Clopper-Pearson upper bound silently returned 0.0 whenever k < n.** My no-scipy
   fallback used one bisection convention for both bounds, but the binomial CDF is
   *decreasing* in p, so the upper-bound solve ran the wrong way. It was caught by checking
   the implementation against the closed form before using it (300/300 must give
   lower = 0.025^(1/300) = 98.778 %, which the lower bound matched while `hi` printed
   `0.000`). Replaced with a direction-detecting bisection; both bounds now verified against
   the closed form. **No reported interval was ever produced by the broken version.**

2. **`.ms*` vs `.mt*`: the first scoring run read ZERO measure sets and did not notice.**
   Xyce names per-sample `.measure` output by ANALYSIS TYPE — `.msN` for `.dc`, `.mtN` for
   `.tran`. The instrument-gate decks are DC, so `.ms*` worked there; both chain DUTs are
   transient, so all 300 measure sets were `.mtN` and my glob found none. This surfaced only
   because an assertion I had put in for exactly this class of mistake
   (`assert len(D) == N`) fired with "300 draws vs 0 measure sets". **Without that assert the
   run would have scored 0 samples and reported something.** `sample_files()` now accepts
   both extensions. The assert earned its keep.

3. **A near-cancellation reported as a margin (DUT_B).** See README §7: I first reported the
   resv boundary receiver as "−5.59 ± 0.13 mV, 43 σ on the wrong side". That average was
   taken over 8 lanes in which four terms are ≈ −609 mV and four ≈ +598 mV, so both the mean
   and its tiny σ were artefacts of the cancellation. Replaced with the class separation,
   which is the data-carrying quantity. This is the same shape as the campaign's committed
   "0.0000 fC was a tautology of the deck" correction.

## A11 — concurrency held, but the shared box was tighter than the disk note assumed

The ≤ 3-concurrent-heavy-jobs rule (§8) was held throughout: DUT_A 3 chunks, DUT_B 3 chunks,
Phase 2 in waves of 3. Two facts worth recording for the next run on this box:
the root filesystem was at **97 % (8.4 GB free)** while three other workflows were writing
multi-MB `.prn` files, and dropping `.print` from the MC decks (A8) kept this whole study to
**44 MB**. Per-sample costs measured: DUT_A 17.5 s, DUT_B 150 s, Phase-2 resized decks
16–23 s (L×2 slowest at 1126 s / 50 samples).

## A12 — Phase 2 gained a pure-σ axis that was not pre-registered

PRE_REGISTERED §9 specified only a geometry grid (W ×{1,2,4}, L ×{1,2}). During the run it
became clear that grid **cannot answer the yield question at all**, because the baseline has
16.45 σ of margin and every variant scores 0/50. A `--kvt` axis was therefore added — every
σ scaled with **geometry unchanged** — for two reasons: it isolates mismatch from the
"bigger cell is also slower" confound, and it is the only way to get a *yield* difference
between sizings (§8c, at 8× σ). The 8× multiplier is a **stress test, not a process claim**,
and is labelled as such everywhere it appears. The pre-registered geometry grid was also run
in full, at both 1× and 8× σ.
