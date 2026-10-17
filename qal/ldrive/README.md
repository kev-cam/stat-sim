# qal/ldrive -- STEP 1: which CURRENT-source drive shapes sustain the 3-phase mesh wave?

Everything in this directory is deliberately **IDEAL** and therefore a **BOUND**: ideal
current sources, an ideal 1.65 V DC clamp rail, 1 S (1 ohm) linear clamp/floor
conductances, a 1 S body-diode stand-in. Nothing here is a buildable number; it answers
"what current shape would an inductor have to deliver" at the committed design point
(qal/mesh3 trap_tt92_d3: T_third = 92 ps, d = 3, 6 banks, P0; commit 5b9d05b).

Pre-registered before the first deck: `PRE_REGISTERED.json` (sha256 8bc4cc56...,
mtime 2026-10-16 21:22:47.498 -0700). Instrument check `IC.json`: the committed
`mesh3.extract()` re-run on the parent's re-run of the committed deck reproduces the
committed OUT.json digit-for-digit (worst margin 509.67 mV, worst overlap 37.021 ps,
standing eye 129.03 ps, all six link widths, 570 .mt0 keys within 1e-7).

## Drive model (per bank, `ldrive.py`)

| third | FIXED clamp mode | LATCHED mode (inductor-until-arrival) |
|---|---|---|
| rise  | +I_r constant (0.5/1 ps edges) for exactly 92 ps | +I_r until V(rail) reaches the 1.644 V comparator band, then off |
| hold  | 1 S clamp to 1.65 V on exactly [tt, 2tt] | clamp engaged by the arrival latch, released at 2tt |
| fall  | -I_f constant for 92 ps; 1 S floor to 0 V on [3tt-2 ps, 3tt] | -I_f until V(rail) reaches the 6 mV band, then floor until 3tt |

TWO_SLOPE = FIXED clamp with the rise split 0.86 mA (46 ps) then 2.29 mA (46 ps) -- the
measured demand halves of the committed linear ramp (same 144.9 fC as 1.575 mA x 92 ps).
Everything else is the committed deck VERBATIM (cells, loads, words, node names, `.tran
0.1p 1932p 0 0.25p`, `.options`, the QPH/EPH integrators and reads); `VPHk` is kept as a
0 V ammeter in the committed sign so the committed `.print` columns and `extract()` are
unchanged; I(VAIRk)/I(VHk)/I(VFk) are APPENDED to `.print` and integrated on the 0.1 ps
extraction grid (grid thirds agree with the exact committed `.measure` thirds to <=0.41 fC
on all 17 rows; energy to <=2.3 fJ except the I_f = 1.3 rows, <=15 fJ, where the 0.44 V
floor-yank spike is under-resolved on the grid). A 1 S clamp is ideal-class: the
committed rs1 row (1 ohm series) scored 508.87 mV / 36.924 ps / 128.93 ps vs 509.67 /
37.021 / 129.03 at 1 mohm.

Acceptance (pre-registered, committed extract code, waves 2-4): A value-correct at every
bank, B margin at the commit sample >= 69.924 mV (3 sigma_total), C handoff overlap > 0 on
every link. Everything else is REPORTED, never gated (energy included).

## Sweep table (banks 2-6 means; d_open = eye-open minus receiver slot vs the committed 24.79/24.71/25.05/25.04 ps on links 2-5; arrival errors: top = first 0.99*DV crossing minus tt, floor = first 0.01*DV crossing minus 3tt; "miss" = never within the window)

| row | I_r | I_f | clamp | step ctl | value | worst margin mV | worst overlap ps | standing eye ps (d vs 129.03) | d_open links 2-5 ps | V(rail) at tt-0.3 ps | top arrival err ps | V(rail) at 3tt-2.3 | floor arrival err ps | E_src rise / E_clamp / E_src fall fJ | E_net fJ | PASS |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| F_ir1.3_if1.3 | 1.3 | 1.3 | fixed | LTE | OK | 286.11 | 27.875 | 124.97 (-4.06) | [13.799, 16.69, 16.447, 19.182] | 1.235 [1.209,1.313] | 0.6 [0.6,0.6] | 0.416 [0.268,0.516] | -1.36 [-1.4,-1.3] | 106.176 / 268.525 / -115.458 | 260.195 | PASS |
| F_ir1.3_if1.6 | 1.3 | 1.6 | fixed | LTE | OK | 232.31 | 17.464 | 113.55 (-15.48) | [11.251, 12.149, 13.926, 15.235] | 1.234 [1.202,1.3] | 0.6 [0.6,0.6] | 0.045 [-0.001,0.132] | -5.4 [-13.4,-1.5] | 101.629 / 269.926 / -114.75 | 257.757 | PASS |
| F_ir1.3_if2 | 1.3 | 2.0 | fixed | LTE | OK | 135.54 | 7.971 | 103.06 (-25.97) | [8.886, 8.591, 11.705, 12.559] | 1.238 [1.195,1.292] | 0.6 [0.6,0.6] | -0.002 [-0.002,-0.002] | -25.88 [-34.0,-18.5] | 99.119 / 270.909 / -105.744 | 265.237 | PASS |
| F_ir1.57_if1.3 | 1.57 | 1.3 | fixed | LTE | OK | 428.68 | 41.495 | 137.8 (+8.77) | [6.302, 5.621, 7.285, 6.565] | 1.37 [1.338,1.441] | 0.593 [0.5,0.6] | 0.441 [0.303,0.538] | -1.36 [-1.4,-1.3] | 142.971 / 225.05 / -117.366 | 251.852 | PASS |
| F_ir1.57_if1.6 | 1.57 | 1.6 | fixed | LTE | OK | 414.44 | 31.296 | 126.61 (-2.42) | [3.707, -0.521, 4.734, 0.636] | 1.375 [1.347,1.425] | 0.593 [0.5,0.6] | 0.055 [-0.001,0.144] | -4.187 [-11.1,-1.5] | 138.108 / 223.783 / -117.24 | 245.849 | PASS |
| F_ir1.57_if2 | 1.57 | 2.0 | fixed | LTE | OK | 351.48 | 20.69 | 116.13 (-12.90) | [1.255, -3.66, 2.634, -2.469] | 1.379 [1.353,1.416] | 0.6 [0.6,0.6] | -0.002 [-0.002,-0.002] | -25.027 [-33.1,-18.2] | 136.144 / 224.26 / -108.054 | 253.55 | PASS |
| F_ir1.9_if1.3 | 1.9 | 1.3 | fixed | LTE | OK | 574.74 | 55.645 | 152.02 (+22.99) | [-2.644, -7.234, -3.807, -8.037] | 1.462 [1.423,1.51] | 0.513 [0.5,0.6] | 0.447 [0.308,0.554] | -1.373 [-1.4,-1.3] | 193.264 / 174.53 / -118.783 | 250.498 | PASS |
| F_ir1.9_if1.6 | 1.9 | 1.6 | fixed | LTE | OK | 567.84 | 44.046 | 138.92 (+9.89) | [-5.702, -9.701, -7.132, -10.28] | 1.468 [1.429,1.5] | 0.513 [0.5,0.6] | 0.057 [-0.002,0.17] | -3.907 [-10.1,-1.5] | 189.042 / 169.323 / -119.11 | 240.745 | PASS |
| F_ir1.9_if2 | 1.9 | 2.0 | fixed | LTE | OK | 560.07 | 33.37 | 128.18 (-0.85) | [-8.615, -12.791, -9.827, -12.754] | 1.474 [1.443,1.507] | 0.5 [0.5,0.5] | -0.002 [-0.002,-0.002] | -24.407 [-32.3,-18.3] | 187.444 / 166.787 / -109.742 | 245.981 | PASS |
| F2S_if1.6 | 0.86->2.29 | 1.6 | fixed | LTE | OK | 450.65 | 34.256 | 129.15 (+0.12) | [3.246, -2.351, 1.233, -2.863] | 1.577 [1.559,1.602] | 0.413 [0.4,0.5] | 0.044 [-0.001,0.13] | -5.307 [-13.4,-1.5] | 147.533 / 200.333 / -114.414 | 235.304 | PASS |
| L_ir1.3_if1.3 | 1.3 | 1.3 | | | | | | | | | | | | | | XYCE FAIL |
| L_ir1.3_if1.3_E1 | 1.3 | 1.3 | latched | ERROPTION=1 | 11/144 fail | -810.61 | 19.765 | None (+0.00) | [42.66, None, None, None] | 1.41 [1.207,1.65] | 1.786 [-11.7,69.3] miss 8/15 | 0.233 [0.0,0.609] | -13.78 [-19.9,-8.5] miss 10/15 | 113.167 / 26.27 / -94.776 | 138.994 | FAIL |
| L_ir1.57_if1.6 | 1.57 | 1.6 | | | | | | | | | | | | | | XYCE FAIL |
| L_ir1.57_if1.6_E1 | 1.57 | 1.6 | latched | ERROPTION=1 | 4/144 fail | -172.88 | -15.56 | None (+0.00) | [22.882, 39.513, 47.466, 70.332] | 1.377 [1.333,1.546] | 65.9 [24.6,77.3] miss 9/15 | 0.016 [-0.0,0.118] | -14.592 [-25.9,-5.4] miss 2/15 | 138.838 / 14.888 / -95.368 | 243.61 | FAIL |
| L_ir1.9_if2 | 1.9 | 2.0 | latched | LTE | OK | 521.38 | 28.68 | 123.18 (-5.85) | [-4.151, -9.475, -2.82, -8.411] | 1.475 [1.44,1.504] | 32.807 [26.3,38.3] | 0.0 [0.0,0.0] | -23.853 [-31.9,-17.8] | 186.837 / 74.561 / -110.287 | 249.158 | PASS |
| L_ir1.9_if2_E1 | 1.9 | 2.0 | latched | ERROPTION=1 | OK | 521.99 | 28.625 | 123.17 (-5.86) | [-4.182, -9.543, -2.851, -8.478] | 1.475 [1.439,1.504] | 32.713 [26.2,38.2] | 0.0 [0.0,0.0] | -23.933 [-31.9,-17.9] | 186.977 / 74.666 / -110.078 | 249.099 | PASS |
| F_ir1.57_if1.6_P1 | 1.57 | 1.6 | fixed | LTE | OK | 425.43 | 33.697 | 126.84 (-2.19) | [3.542, -0.122, 3.45, 1.114] | 1.376 [1.351,1.417] | 0.6 [0.6,0.6] | 0.033 [-0.001,0.052] | -3.16 [-8.9,-1.6] | 138.348 / 222.888 / -116.572 | 245.863 | PASS |

`L_*` rows without `_E1` are the committed GEAR+LTE step control; the two under-driven
LATCHED rows die under it at t = 553.000 ps (the wave-2 input-word knot) once the latch
state closes the loop onto the clamp conductance (the same B-source current with PWL
clamps, and observer-only latches, both run clean; `ERROPTION=1` runs clean). They are
scored with `.OPTIONS TIMEINT ERROPTION=1` (Newton-count step control, maxstep 0.25 ps)
and labelled; the calibration pair `L_ir1.9_if2` vs `L_ir1.9_if2_E1` run both ways agrees
to 0.6 mV margin, 0.06 ps overlap, 0.01 ps eye, 0.1 ps arrival, 0.06 fJ.

## Verdict (MEASURED unless marked)

1. **Constant-current rise + boundary clamp sustains the wave at every grid point**: all
   9 FIXED rows PASS A+B+C (I_r in {1.3, 1.57, 1.9} x I_f in {1.3, 1.6, 2.0} mA), P1 on the
   centre row PASS (425.43 mV / 33.70 ps / 126.84 ps; the killing pattern is not worse than
   P0's 414.44 / 31.30 / 126.61). But the band is steeply asymmetric: at I_r = 1.3 mA the
   margin falls to 136-286 mV and the overlap to 8-28 ps (ERODES_SLOW at 1.3/2.0); at
   1.9 mA margins are 560-575 mV with 33-56 ps overlap. **Tolerance band: I_r >= 1.57 mA
   (-0 %/+21 % of the measured 1.57 mA mean) keeps SUSTAINS with overlap >= 20 ps; I_r = 1.3
   (-17 %) still passes the gate but erodes. I_f is tolerant over the whole 1.3-2.0 mA
   range; lower I_f widens the eye (I_f = 1.3: 137.8-152.0 ps) at the price of a 0.42-0.45 V
   residual the floor clamp must dump, higher I_f narrows it (I_f = 2.0: 103-128 ps) and
   over-draws 40-42 fC through the ground diode.**
2. **The clamp, not the current source, does the finishing.** With the boundary clamp the
   rail reaches only 1.235 / 1.375 / 1.468 V at the end of the rise third for 1.3 / 1.57 /
   1.9 mA (no overshoot anywhere, peak 1.648 V) and the clamp yanks it the rest of the way;
   the clamp then supplies 164 / 135 / 105 fC per cycle vs 124 fC on the ideal trapezoid.
   The two-slope 0.86->2.29 mA profile with the SAME 145 fC reaches 1.577 V: the demand is
   trajectory-dependent (a fast foot pulls extra current), so **charge amount alone does not
   set arrival; shape does**. The yank also lifts expected-LOW outputs during the hold by
   85 mV (centre) / 274-343 mV (I_r = 1.3) vs 10 mV (two-slope) and 0 (committed).
3. **Inductor-until-arrival (LATCHED) at the measured mean current does NOT sustain the
   wave.** 1.9/2.0 mA arrives +32.8 ps LATE (range 26-38) and still PASSes (521 mV / 28.7 ps
   / 123.2 ps) because the hold absorbs it; 1.57/1.6 mA arrives +66 ps late where it arrives
   at all (9/15 bank-waves never reach 1.6335 V inside rise+hold) and FAILS (4/144 value
   fails, margin -173 mV, overlap -15.6 ps, eye collapsing 127 -> 22 ps along the chain);
   1.3/1.3 is EXTINCT by link 3. DERIVED from the 1.9 mA arrival: a constant-current rise
   needs ~237 fC to reach 1.644 V vs the linear ramp's 145 fC (+63 %).
4. **Energy BOUND (per bank per cycle, banks 2-6, ideal sources):** centre row source rise
   138.1 fJ, clamp rail 223.8 fJ, returned to the sink in the fall 117.2 fJ (what an ideal
   inductor could recover), E_net 245.8 fJ vs the committed 240.3 fJ ledger (+2.3 %). E_net
   is nearly invariant over the grid (235-265 fJ): whatever the source does not deliver, the
   clamp does. The two-slope profile is the cheapest (235.3 fJ, -2 %), the clamp doing 121 fC.
5. **Establishment / standing eye vs the 129.03 ps baseline (centre row):** eye opens within
   -0.5..+4.7 ps of the linear ramp on links 2-5 (not earlier), standing eye 126.61 ps
   (-2.4 ps), overlap 31.3 ps (-5.7), margin 414 mV (-95 mV). Widths alternate by receiver
   phase (141/122/134/121/132/116 ps).

## Pre-stated expectation vs measured

| question | pre-stated | measured | verdict |
|---|---|---|---|
| constant-current rise delays establishment? | no; 5-15 ps EARLIER (fast foot) | links 2-5: +3.7/-0.5/+4.7/+0.6 ps (not earlier) | FALSIFIED in direction (two links beyond the 3 ps falsifier) |
| standing eye, centre row | wider by 15-30 ps (slow top of the constant-current fall) | 126.61 ps (-2.4) | FALSIFIED; widening only at I_f = 1.3 or I_r = 1.9 |
| FIXED boundary mismatch | -0.16 V at 1.3 mA, +0.19 V overshoot at 1.9 mA | 1.235 / 1.375 / 1.468 V, never any overshoot | FALSIFIED: always under-delivers; demand is trajectory-dependent |
| LATCHED arrival error | +19.5 / -0.3 / -15.7 ps, all PASS | never / +66 ps (FAIL) / +32.8 ps (PASS) | FALSIFIED: Q/I arithmetic with the ramp's Q is wrong by +63 % |
| tolerance band | 9/9 FIXED PASS; LATCHED PASS at 1.57, 1.9 | 9/9 FIXED PASS (steep erosion below 1.57); LATCHED PASS only at 1.9 | FIXED confirmed, LATCHED falsified |
| energy bound, centre | source 125-150, clamp 190-210, recovery 100-130 fJ | 138.1 / 223.8 / 117.2 fJ | clamp above band (it makes up the 0.275 V deficit) |

## What this means for "a few switched inductors"

- A current-limited (inductive) rise that is switched away by a TIMER at the third
  boundary and handed to a stiff 1.65 V clamp works at I_r >= 1.57 mA, with the clamp
  finishing the last 0.18-0.28 V and supplying 105-135 fC per cycle. The inductor has to
  be sized for ~1.9 mA to keep the margin/overlap headroom (575 mV / 56 ps at 1.9/1.3).
- An inductor that is released only ON ARRIVAL (comparator) must carry >= 1.9 mA and still
  lands 33 ps into the hold; at the measured-mean 1.57 mA it never arrives. The 63 % extra
  charge of a constant-current trajectory is the cost of the fast foot; a soft-start
  (two-slope) trajectory with the same charge gets within 73 mV of the rail.
- Fall: a constant -I_f leaves 0.42-0.45 V (1.3 mA) to a floor clamp, or over-draws
  40-42 fC through the body diode (2.0 mA); 1.6 mA lands within 0.05 V. In an inductor
  implementation the over-draw is circulating current, not loss (ideal), and the ~117 fJ
  absorbed in the fall is the recovery bound.

## Files

`PRE_REGISTERED.json` (pre-stated), `IC.json` (instrument check), `ldrive.py` (deck builder,
runner, `agg`/`table`/`finalize`; diagnostic env switches `LDRIVE_*` documented inline),
`RESULTS.json` (17 rows + calibration + scorecard), `runs/<tag>/` (deck, .mt0, OUT.json;
no .prn anywhere in the repo -- waveforms lived on the scratchpad and were deleted after
extraction). Run time per 6-bank deck ~3-4 min (FIXED) / ~6 min (LATCHED, LTE) on this box.

Model language: tracking lag / eye / margin at the sampling instant. Nothing here
"settles".
