# qal/rfast amendments — each forced by a measurement

Pre-registration sha256 `70fac658375bcb564c94858ca464b258bbc31fc3890d857d332b4100ba9ee0bb`,
13847 B, mtime 2026-09-30 09:01:23 -0700, written when the directory held only
`DISK_STATE_BEFORE.txt` (08:59:41) — before any deck.

## A1 — Newton iteration budget raised 4 → 8 for CROSS-SEEDED lanes; the A6 gate is untouched

Pre-registered: Newton-on-the-row, "max 4 iterations, else the row is EXCLUDED".
That budget was inherited from eyebeat B2, where every seed was a MEASURED zero
at the row's own (L, VGH).  Here the seeds are qal/eye zeros measured at
VGH = 1.5 and sqrt-scaled across L, and the first screening lanes measured the
seed error to exceed the ±10 ps/iteration trust region several times over:

* `L15W15/T200/P0`: the four RETURN zeros converge MONOTONICALLY at exactly the
  trust-region rate (worst residual 193 → 159 → 84 → 11.8 µA over iters 1–4,
  tzq marching −10 ps/iter from the 145–156 ps VGH=1.5 seeds), still moving at
  iter 4.  The new drive moves the return zeros by ≥ 30 ps at W = 15 — more
  than the pre-registered budget can traverse from a cross-drive seed.

Fix: `maxit = 8` whenever the seed is not an own-(L,W,T,VGH) measurement, and a
lane may be re-entered once with its own kept `zeros.json` as seed (which is the
same thing).  The A6 gate (|I(L)| ≤ 1 µA at every commanded open) is UNTOUCHED;
iterations were added, acceptance was not loosened.

## A2 — the A6 gate is an ~8× stricter TIMING gate at L = 3, and row (3, 30) fails it on an instrument floor

`L3W30/T200/P0` converges to a STATIC rise-side residual of +1.1017 / +1.0434 /
+0.9608 / +0.9020 µA (banks 1–4) that iterations 3 and 4 reproduce IDENTICALLY
while tzr no longer moves at 0.01 ps resolution.  At L = 3 nH the conducting
current's slope at its zero is ≈ 170 µA/ps (Ipk ≈ 3 mA, t_half ≈ 55 ps), so
1.1 µA corresponds to ≈ 0.006 ps of timing — below the 0.1 ps print grid and
the ±grid-interpolation of the `.measure FIND` lag calibration (LAG_PS = 1.0 ps,
a measured whole-build constant with its own sub-grid error).  The stranded
inductor energy at the commanded open is ½·L·I² = 1.8e-9 fJ.

The gate is applied AS PRE-REGISTERED: the row is excluded (F1) and
W*(L=3) = 45 µm is selected from the passing ladder.  Recorded here: at fixed
1 µA the A6 gate tightens as 1/slope ∝ sqrt(L)·Z0 — at L = 3 it is in effect a
±6 attosecond timing gate, ~8× stricter than the L = 15 gate it was calibrated
on.  This is the same class as fastwave A8's probe/hop grid-mismatch rows: a
deliberately strict INSTRUMENT gate, not physics.

## A3 — lane seed order: own zeros → same-(L, W) T=200 zeros → sqrt-scaled qal/eye zeros

Forced by A1's measurement (cross-drive seeds are the slow step).  Rise zeros
are beat-invariant above the overlap regime (eyebeat measured −0.01 to
−0.02 ps corrections off T=200 seeds) while return zeros move with T, so lower-T
lanes seed from the SAME (L, W) pattern's T = 200 measured zeros when they
exist.  Protocol and gate unchanged; this only shortens the Newton path.

## A4 — the W ladder was extended DOWN by measurement (points ADDED, none removed)

The pre-registered ladders bottomed at 30 µm (45 at L = 3), and the first
screen measured the opening still improving at every ladder's bottom edge
(L=10: 87.2 → 73.9 ps from W=30 → 15; L=6: 73.6 → 62.0).  W = 15 was added at
L = 15/10/6, W = 30 at L = 3, and W = 7.5 at L = 10/6 as the boundary probe
(fastwave measured W = 7.5 failing rail-drain completeness on the pass-gate
bank; whether the restoring bank's W floor sits there too is a measurement,
not an inheritance).  Selection rule unchanged: smallest-opening W subject to
G1 + G2, ties to the smaller W.

## A5 — the eye INTERSECTION is over ALL ran patterns; the A6 flag rides alongside

Forced by measurement, found during the first sweep read-out: at L ≤ 6 the A2
instrument floor (a STATIC 1.0–1.23 µA residual = ~0.012 ps of commanded-open
timing at the ≥ 97 µA/ps zero-crossing slope, ½·L·I² ≈ 4e-9 fJ stranded)
straddles the 1 µA A6 line, so the extractor's original membership rule (only
A6-passing patterns join the intersection) made the pattern set vary ROW BY
ROW: the L = 6 cells were silently P0-only eyes while the L = 15 cells were
three-pattern eyes — not comparable across L, and flattering exactly the cells
whose instrument was weakest.  Fixed: the intersection is ALWAYS over all ran
patterns; `patterns_A6_pass` and the per-pattern residuals are reported
alongside, and the STRICT per-row A6 verdict is unchanged and reported
separately.  Every (L, T) cell was re-extracted under the fixed rule; no
simulation was re-run (the fix is extraction-only).

## A6 — the pre-registered W selector picks a W that does not BANK; W* is re-selected on the full gate set, both selections reported

Forced by measurement.  The pre-registered rule selected W* by MINIMUM
worst-bank 0 mV opening subject to G1+G2, and at L = 6 it selected W = 15 µm
(opening 82.0 vs 88.0 ps at W = 30).  The sweep then measured that the W = 15
eye, while opening earliest, is too SHALLOW to bank: HEIGHT at the sampling
instant 81–106 mV (≈ 3.5–4.5 σ_total) against W = 30's 150–168 mV, so the
3σ_total-margined opening lands 46–77 ps after the 0 mV opening and the G3
budget balloons (36–84 ps at T = 85–160) — G3 fails at EVERY swept T ≤ 180 at
W = 15/L = 6, while W = 30/L = 6 passes the ENTIRE strict gate set at T = 130
(A6 3/3 at 0.61 µA — clear of the A2 instrument floor — value 96/96, slack
42.0 ≥ budget 19.4, post-return floor +21.2 mV).  The delivered boundary rail
tells the mechanism: 0.86 V (worst bank, W = 15) vs a stiffer delivery at
W = 30 — the small switch starves the level even though it shortens the ramp.

Consequence: the frontier is taken over BOTH W's per L (every ladder cell is
reported), and the L = 3 analogue (W = 60 vs 45) is measured the same way.
Nothing pre-registered is removed; the selection criterion's failure is itself
a finding: OPENING is not the quantity that banks — height-margined slack is.
