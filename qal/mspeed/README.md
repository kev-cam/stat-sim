# qal/mspeed -- speed ceiling of the three-phase driven-mesh wave

Pre-registered in `PRE_REGISTERED.json` before the first deck (predictions, bands, verdict rules).
Lineage: `qal/mesh3` (commit 5b9d05b) -- six restoring inverter banks on an ideal three-phase
trapezoid mesh (rise / hold / fall thirds), 1.65 V crest, bank k on phase (k-1) mod 3, outputs
direct-wired, no registers. **Ideal driven mesh = BOUND (ASSUMED, standing licence).** The flat-top
driver's measured 2.2x energy price (`qal/meshdrv`) applies and is not re-measured here.
Engine: **VACASK 0.3.4 primary**, Xyce cross-check on anchor rows. Energy REPORTED, never gated.
Model language: tracking lag / eye / margin at the sampling instant, never "settling".

Sweep: cell scale s in {1, 2, 4} (wp 1.12u*s / wn 0.74u*s, 2 fF external per output, next-level
gate load scales with s), T_third in {92, 80, 70, 60, 50, 40} ps, depth d in {2, 3, 4} inverter
levels per bank; P0 on the full grid, P1 (the killing mixed word) on every frontier cell; 30 ps
rows added beyond the grid where the frontier reached the grid edge. All numbers MEASURED unless
tagged.

## Verdict

* **Ceiling on this cell family: T_third = 40 ps at s >= 2, d = 2** (30 ps fails at s = 2 and 4):
  wavefront level-rate **18.4x** the CMOS chain level (1/367.888 ps), **8.33 G results/s per lane**
  (one result per 3 T_third), 20 ps per level. The same 18.4x is reached at d = 3, T_third = 60 ps
  (5.56 G/lane). d = 4 only ever passes at s = 4, 92 ps (16.0x).
* **Upsizing helps, bounded (prediction confirmed in sign, stronger than predicted at s = 2,
  saturating at s = 4):** the floor moves one grid step from s = 1 to s = 2 at both d = 2 (60 -> 40)
  and d = 3 (80 -> 60) and does not move again at s = 4; establishment (commit minus the bank's own
  rise) shrinks monotonically with s at every fixed (T_third, d) for d = 2 (e.g. 60 ps: 85.6 -> 73.8
  -> 69.5 ps). What is left at s = 4 is the rail-ramp wait, which is s-invariant.
* **Latency: a win against the campaign comparator, parity at iso-voltage** (prediction confirmed).
  True per-level latency (head edge to the real bank-6 receiver's commit, over 5d levels) is 21-33 ps
  = **0.56-0.74x the load-matched 1.2 V CMOS chain level** at the same s, and **0.88-1.15x the same
  chain at 1.65 V**. The win over the campaign comparator is a supply-voltage win (the mesh crest is
  1.65 V), not an architectural one. The standing rule "latency never wins" (tank physics, 105 ps
  per level) is stale for the driven mesh against 1.2 V CMOS and holds as parity at iso-voltage.
* **Droop:** at the fastest cells (40 ps, d = 2) a 10 ohm/bank mesh still passes (s = 2: 73 mV
  margin; s = 4: 356 mV); 100 ohm fails (predicted).
* **Energy (REPORTED, ideal-source books):** 159 fJ per bank per cycle (s = 1, 60/2) to 1050 fJ
  (s = 4, 92/4); 272 -> 462 fJ from s = 2 to s = 4 at the 40 ps frontier (1.7x per doubling,
  sub-linear against the predicted ~s).
* **Transfer to real logic (DERIVED, see `qal/mblocks`):** these ceilings are for the inverter
  cell class. The nand2 level is 1.50-1.59x the inverter level (both engines, both supplies), so
  nand2 logic takes two levels per bank where the inverter takes three; and real netlists need the
  level-order mapping rule found in `qal/mblocks` (a producer at level j may feed a next-bank
  consumer at level i only if j >= i), otherwise the wave is extinct regardless of T_third.

## Frontier (fastest T_third per (s, d) with P0 AND P1 passing; VACASK)

| s | d | T_third ps | level-rate vs CMOS | G results/s per lane | eye ps | worst margin mV | worst overlap ps | true latency / level ps | vs 1.2 V chain | vs 1.65 V chain | E fJ / bank / cycle |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2 | 60 | 12.26 | 5.56 | 79.7 | 372.6 | 19.7 | 32.6 | 0.62x | 1.02x | 159 |
| 1 | 3 | 80 | 13.80 | 4.17 | 96.6 | 243.1 | 16.6 | 29.3 | 0.56x | 0.92x | 253 |
| 1 | 4 | none (fails 92..40) | | | | | | | | | |
| 2 | 2 | **40** | **18.39** | **8.33** | 47.0 | 168.6 | 6.7 | 22.4 | 0.56x | 0.89x | 272 |
| 2 | 3 | 60 | 18.39 | 5.56 | 70.7 | 194.8 | 10.5 | 22.1 | 0.56x | 0.88x | 414 |
| 2 | 4 | none | | | | | | | | | |
| 4 | 2 | **40** | **18.39** | **8.33** | 54.9 | 416.4 | 14.9 | 21.5 | 0.63x | 0.98x | 462 |
| 4 | 3 | 60 | 18.39 | 5.56 | 86.4 | 532.3 | 26.2 | 21.0 | 0.62x | 0.95x | 639 |
| 4 | 4 | 92 | 16.00 | 3.62 | 104.2 | 160.2 | 11.8 | 25.3 | 0.74x | 1.15x | 1050 |

Pass map (P0; the pass set is contiguous from 92 downward in every row, no non-monotone passes):
s1: d2 passes 92..60, d3 92..80, d4 none; s2: d2 92..40, d3 92..60, d4 none; s4: d2 92..40,
d3 92..60, d4 92 only. 30 ps rows (beyond the grid): s2/d2 FAIL, s4/d2 FAIL. s1/d2 at 50: FAIL.

CMOS comparators (depth-12 chain of the same scaled cell, 2 fF per node, (t90(d8)-t90(d4))/4, VACASK):

| s | 1.2 V load-matched (campaign comparator) | 1.65 V iso-voltage |
|---|---|---|
| 1 | 52.64 ps (Xyce committed 52.510; +0.24%) | 31.87 ps |
| 2 | 39.74 ps | 25.12 ps |
| 4 | 34.10 ps | 22.06 ps |

Pre-registered predictions vs outcome: floors predicted s1 {50, 80, none} / s2 {50, 70, none} /
s4 {40, 70, none}; measured s1 {60, 80, none} / s2 {40, 60, none} / s4 {40, 60, 92}. The best-cell
prediction (s = 4, d = 2, 40 ps, 18.4x, 8.3 G/lane) is exact; s = 2 reaches it too. Latency
ratios predicted 0.45-0.6x (vs 1.2 V) and 0.85-1.15x (vs 1.65 V); measured 0.56-0.74x and 0.88-1.15x.

## Cross-engine certification (CERT.json; bands pre-stated)

Design point `trap_tt92_d3` (committed deck byte-identical; same offline extractor on both engines'
own grids): rails agree to < 6 uV; commit instants within 0.39 ps, die within 0.003 ps, eye widths
within 0.39 ps, overlaps within 0.39 ps; per-third charge/energy books within 0.45%; value 144/144
on both; acceptance identical (PASS, margin 509.67 Xyce / 503.66 VACASK). **One band miss,
explained:** 12 of 30 margin-at-commit rows differ by 6.0 mV (1.18% vs the 1%/5 mV band). Resampling
both engines at the same instant gives 0.064% agreement, so the 6 mV is the 0.3-0.4 ps commit-instant
shift on a 17.9 mV/ps ramp -- the instantaneous-sample class (OFFSET_TABLE Amendment 2), not a model
offset. Xyce's in-engine integrator reads equal the offline trapezoid to 7e-5 (the deck's +1 ps
FIND convention cancels the measured ~0.9 ps FIND-AT lag). VACASK reltol 1e-4 / 1e-5 / 1e-6 move
commit instants by < 0.002 ps. mesh3's extractor and this port give identical acceptance on the same
.prn (99 fields, 0 differ).

Frontier cross-check on Xyce: s2 / 40 ps / d2 PASS on both engines (eye 46.98 vs 47.44 ps, overlap
6.65 vs 7.16 ps, latency 22.38 vs 22.34 ps/level, E 271.9 vs 270.4 fJ; margin 168.6 vs 182.9 mV --
the same instantaneous-sample class on a 41 mV/ps ramp, reported as measured); the failing
neighbour s2 / 50 ps / d3 FAILS on both (margin -1113 vs -1110 mV). Verdicts agree.

Wall time, single-threaded, loaded box: design point Xyce 161.7 s vs VACASK 33.3 s (4.85x);
s2/40/d2 379 vs 15 s; s2/50/d3 94 vs 26 s. The 63-cell sweep ran in VACASK at 10-60 s per cell.

## Riders

Ideal driven mesh (BOUND); inverter cell class (nand2 logic: see `qal/mblocks`); 6-bank wave, waves
2..4 scored; energies are ideal-source books with the 2.2x driver price not applied here; the
1.65 V crest on 1.5 V LV devices and V_GH = 2.174 V remain ASSUMED for reliability.

## Files

`PRE_REGISTERED.json`, `cert.py` -> `CERT.json`, `mspeed.py` (decks for both engines, VACASK raw
loader, mesh3 extractor port), `agg.py` -> `RESULTS.json`, `runs/<tag>/` (deck + OUT_<engine>.json;
waveforms lived on the scratchpad and are not kept).
