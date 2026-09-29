# qal/fcrit_skept — skeptic audit of the functional commit criterion

Own directory, own `PYMS_VAE_CACHE`. Nothing in `qal/fcrit` or any other
committed `qal/` directory was written to. Every number below is from my own
deck or my own analysis code; `skscore.py` shares no code with `fcrit/rescore.py`.

## What I confirm

* **The threshold.** My own DC deck (`sk_trip.cir`, 0.5 mV step, both receivers
  in one run) reproduces `qal/bound/dc_rows.json` to ≤ 4.8e-05 and reproduces
  the primary's whole trip-vs-rail and window-vs-rail curve. All three of its
  threshold corrections stand.
* **The re-score.** My independent scorer reproduces the primary's `pass90`
  **link** counts EXACTLY on all six datasets I ran (chain3 284, banktank 1555,
  skip4 392, skiptu 980, resv 12, restore5 52) and its row verdicts
  (banktank 57, skip4 0, resv 1 = res20, restore5 4).
* **The beat.** H=2 250→160, H=3 200→200, H=4 200→150 ps; II 500→320 ps.
* **Both failure modes, link by link.** T=150 all 32 pass (+74.44 mV);
  T=140 fails *inside* the budget (+13.14 mV); T=130 fails by crossing *after*
  commit (−53.02 mV). Neither was taken.
* **The self-test.** ZERO rows where the committed VALUE guard passes and the
  functional criterion fails, in every dataset I re-scored.
* **The generous last bank is forced, not flattering.** Scoring it strictly
  fails every iso-swing row including T=300 (−68.13 mV).
* **The brief's "319.9 mV (no tank)" is not in `qal/tankfed`** — verified by my
  own scan. The primary's correction is right.

## What I overturn

1. **chain3's verdict DOES change** (`F_CHAIN3_VERDICT_DOES_CHANGE`). The
   primary said its coupling term could not be measured in chain3's own
   topology and imported 249.0 mV from `qal/tankfed`. It is one deck away:
   `park_g100_topup.cir` / `park_g10_topup.cir` are the committed topped-up
   decks with **four lines changed** — the two top-up gate PWLs — parking the
   devices off with the schedule byte-identical (verified: 0.00000 mV rail
   difference before the top-up fires). chain3's OWN harmful coupling step is
   **32.9–37.4 mV** at feeder 1 and **119.3–124.8 mV** at feeder 2, not 249.0.
   **2 to 11 of 23 chain3 rows flip to PASS — never 0.** `g10_topup` and
   `m10_d180` pass under every variant I tried.
   My differential was validated against the committed numbers first
   (matched m2 250.745 vs 248.997; uniform m6 31.411 vs 31.411).
2. **The Phase-2 beat verdict REVERSES** (`G_PHASE2_FAIRNESS…`). The bars are
   genuinely identical on both sides — but the *objects* are not. The QAL side
   is a pipeline beat; the CMOS side is one gate's rise time from an ideal step,
   where ~46 % of the measured interval is tail. I built the arm the primary did
   not (`sk_chain.cir` depth 12 @2 fF, `sk_chain691.cir` depth 10 @6.91 fF
   iso-load). **CMOS steady-state per-logic-level delay is 52.5100 → 52.5100 ps,
   GAIN 1.00000×** (iso-load 76.6193 → 76.6097, 1.00012×); depth-8 end to end
   1.0989×; only depth-1-from-an-ideal-step gives the primary's 1.8146×.
   Against QAL's 1.3333×, **QAL gains more at the beat too**, and the
   per-logic-level ratio **narrows 25.0 %** (3.8088 → 2.8566) rather than
   widening 36 %. My CMOS chain has no register tax at all, so the correction is
   conservative against QAL and flips anyway.
3. **The coupling term is read off the wrong polarity.** `tankfed/coupling.py`
   scans one polarity only. In the *uniform m=6* configuration the primary used
   31.1 mV; the worst **harmful** excursion in that same configuration, same
   window, is **+218.380 mV** on `o3_1` (a node intended LOW pushed UP). In
   matched m=2 the primary's 249.0 mV is conservative — the worst harmful
   excursion is 184.671 mV. Wrong in both configurations, opposite directions.
4. **The budget double-counts deterministic terms already in the waveform.**
   The criterion reads the actual signal against the actual rail at the actual
   instant on the committed transient, so held-rail droop is already there.

## What I tested and it vindicated the primary

**Worst-over-window is ill-posed, not merely strict.** Requiring the margin to
hold throughout the receiving rail's charging window passes ZERO rows in either
dataset — a HIGH link is structurally below any threshold before its own rail
has risen. The single-instant criterion is the right one.

## Files

`sk_trip.cir`/`TRIP_SKEPT.json` · `sk_level.cir`/`LEVEL_SKEPT.json` ·
`sk_chain.cir`, `sk_chain691.cir`/`CHAIN_SKEPT.json` ·
`skscore.py`, `skan.py`, `skrest.py`/`SKSCORE*.json` ·
`diff_coup.py`, `signed_coup.py`, `coup.py` ·
`park_g100_topup.cir`, `park_g10_topup.cir`/`CHAIN3_OWN_COUPLING.json` ·
`beat_sk.py`/`BEAT_SKEPT.json` · `RESULTS_SKEPT.json`
