# qal/lsteer — can the 12× three-phase wave be driven by a FEW STEERED INDUCTORS?

Transistor-level Xyce (IHP SG13G2, PSP103), the mesh3 `trap_tt92_d3` chain VERBATIM (6 banks × d=3,
T_third = 92 ps, 12.0× per level, committed 5b9d05b) with ONLY the six ideal trapezoid rail sources
replaced by: three phase nodes, ONE inductor per 3-phase group steered falling-bank → L → rising-bank
every third, a 1.65 V DC clamp on the holding bank, and a 0 V clamp / 1.65 V in-feed for the exhausted
falling bank. Pre-registration: `PRE_REGISTERED.json` (written before any deck). Harness: `lsteer.py`
(imports `qal/mesh3/mesh3.py`'s `deck()`/`extract()` unchanged). Per-row evidence: `runs/<tag>/{OUT.json,
*.cir, *.mt0}`; `.prn` waveforms lived on the scratchpad and were deleted after extraction.
Instrument check `ICHECK.json`: `extract()` on a byte-identical re-run of the committed deck reproduces the
committed OUT.json digit-for-digit in every rounded field (509.67 mV / 37.021 ps / 129.03 ps / 144/144).

**Numbers first.** IDEAL-switch rows (BOUNDS): the wave SURVIVES every steered-inductor shape tried —
value 144/144 on P0 and on P1, margin at commit 250–697 mV (gate 69.924), overlap 28–41 ps, standing eye
124–137 ps vs the 129.0 ps baseline — at L = 120 nH per 6 banks (N=2 per phase) / 30 nH per 24 banks (N=8),
I0 = 3.5 mA (N=2) / 13.4 mA (N=8) = N × 1.7 mA, per-third ripple 5.8 % (120 nH, N=2) / 6.8 % (30 nH, N=8), energy
245–290 fJ/bank/cycle from the 1.65 V rail (mesh3 ideal-rail ledger 240.3; harmonic flat-top driver 534).
REAL sg13_lv switches at the binding V_GH = 2.174 V spec: FAIL (value 6–7/144 wrong; nMOS-only −28 mV
margin) — the W=30 µm transfer gates' own capacitance (metered 2.0–3.0 fC/µm per turn-on edge) loads each
phase node with as much capacitance as the bank pair; re-seeded wider rows (W=50/78 µm at 7–9 mA) crash
Xyce at the first high-current handover. Gate bill alone, metered: 328 (nMOS) / 495 (TG) fJ/bank/cycle.
Energy is REPORTED, never gated.

## 1. The construction (fixed before the first deck, see PRE_REGISTERED.json)

Third schedule (mod T = 276 ps): third 0: A rises, B falls, C holds → L steered B→A; third 1: C→B, A holds;
third 2: A→C, B holds. Per phase the sequence is R,H,F,R,H,F — a fallen bank starts rising IMMEDIATELY, so
the "0 V clamp" can only act while the bank is still on the inductor (pulse) or after the bank is taken off
the inductor early (the steered-buck split, §3). Per 3-phase group: 3 in-switches (pX–lin), 3 out-switches
(lout–pX), 3 hold clamps (pX–1.65 V), 3 zero clamps, [+1 in-feed switch 1.65 V–lin in buck mode]; the
switch count is N-invariant, their width scales with N. Ideal rows: Xyce VSWITCH RON 0.05 Ω, ROFF 1e8,
control ramps 0.3 ps, break-before-make 0.4 ps at EVERY boundary (asserted by the harness from the PWL
knots: no instant shorts vddh, 0 V or two phase nodes; the only simultaneously-closing pair is in+out across
L). An inductor cannot be open-circuited, so terminal caps C_t (ASSUMED 20 fF; 5 fF and 50/200 fF variants)
absorb the dead-time current. Series R_L = 10 Ω (campaign convention) and 1 Ω. Soft start: wave 0 on the
ideal trapezoid rails with the inductor freewheeling at its seed, handover at t = T with the same BBM rule
(waves 2–4 are scored; the first seed-sweep rows had no soft start and the UIC cold start cost them a
third — they still PASS and converge to the same current). The DC rail's current, the 0 V rail's charge,
I²R in R_L, every switch's V·I (through 0 V ammeters) and the inductor current are metered with 1 F
t0-referenced integrators read at n·T; energy balance (sources − ΔE_L = banks + losses) closes within 0.3–2.7 %
on every row.

## 2. Regime (i) CCM — steered standing current

| row (N=2, 6 banks, one L) | L nH | R_L | C_t | construction | I_mean mA | drift %/cyc | ripple/third | land. at hold clamp mV | fall residual mV | value | margin mV | overlap ps | eye ps | E_dc | E_R | E_sw | E_total fJ/bank |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| I0 2.8 (pre-reg. pulse clamp) | 120 | 10 | 20 | F→L→R + 4 ps 0 V pulse | 2.46 | −0.6 | ~10 %* | −459 | +520 | 144/144 | 250.6 | 28.3 | 126.2 | 270 | 2.8 | 32.7 | **270.4** |
| I0 3.15 (same) | 120 | 10 | 20 | same | 2.48 | −1.2 | ~11 %* | −455 | +517 | 144/144 | 251.8 | 28.4 | 126.3 | 268 | 2.8 | 32.4 | **269.0** |
| I0 3.5 (same) | 120 | 10 | 20 | same | 2.50 | −1.8 | ~13 %* | −452 | +514 | 144/144 | 253.1 | 28.4 | 126.3 | 265 | 2.9 | 32.1 | **267.6** |
| I0 3.15, R_L = 1 Ω | 120 | 1 | 20 | same | 2.54 | −1.1 | ~11 %* | −440 | +488 | 144/144 | 253.1 | 28.0 | 125.6 | 264 | 0.3 | 31.5 | **265.1** |
| I0 3.15, C_t = 5 fF | 120 | 10 | 5 | same (soft start) | 2.72 | −3.4 | ~18 %* | −389 | +425 | 144/144 | 341.7 | 31.8 | 129.5 | 240 | 3.4 | 15.8 | **244.8** |
| I0 3.15, NO zero clamp | 120 | 10 | 20 | plain F→L→R | 2.30 | **−11.4** | — | −396 | +740 (trough never < 0.33 V) | 144/144 | 299.8 | 39.3 | 173.8 | 246 | 2.5 | 12.1 | 258.2 (transient, not steady) |
| buck t1 = 0.95 | 120 | 10 | 20 | F→L→R to 0.95 tt, then 1.65 V→L, F zero-clamped | 3.04 | −2.8 | 15 %* | −316 | +420 | 144/144 | 402.4 | 36.3 | 133.3 | 252 | 4.3 | 25.1 | 256.9 |
| buck t1 = 0.9 | 120 | 10 | 20 | same | 3.19 | −2.0 | 12 %* | −282 | +403 | 144/144 | 448.7 | 37.1 | 133.9 | 254 | 4.7 | 25.2 | 257.8 |
| **buck t1 = 0.8 (best speed row)** | 120 | 10 | 20 | same | **3.49** | **−0.6** | **5.76 %** (0.201 mA) | **−226** | +387 | 144/144 | **525.5** | **39.7** | **135.0** | 260 | 5.6 | 25.7 | **261.6** |
| buck t1 = 0.8, **P1** (killing word) | 120 | 10 | 20 | same | 3.48 | −0.07 | 6 %* | −227 | +388 | 144/144 | 529.4 | 40.9 | 134.8 | 259 | 5.6 | 25.7 | 258.8 |
| buck t1 = 0.8, R_L = 1 Ω | 120 | 1 | 20 | same | 3.56 | −0.2 | 7 %* | −216 | +349 | 144/144 | 541.2 | 40.0 | 135.3 | 256 | 0.6 | 25.6 | 256.9 |
| buck t1 = 0.8, C_t = 5 fF | 120 | 10 | 5 | same | 3.41 | −1.0 | 9 %* | −235 | +283 | 144/144 | 511.3 | 36.0 | 132.1 | 243 | 5.3 | 12.9 | **245.4** |
| buck t1 = 0.6 | 120 | 10 | 20 | same | 4.11 | +2.6 | 3.39 % | −122 | +435 | 144/144 | 654.4 | 40.8 | 137.8 | 284 | 7.8 | 27.7 | 275.7 |
| **buck t1 = 0.5 (landing regulated)** | 120 | 10 | 20 | same | 4.42 | +4.1 | 2.59 % | **−31 (−134..+38)** | +517 | 144/144 | **697.5** | 38.9 | **137.1** | 304 | 9.0 | 30.1 | 288.0 |

`*` = 3-cycle max−min / mean, which also contains the secular drift (overstates ripple); the per-third
metric was added after those rows ran and their waveforms were already deleted. Landing = rail at the
instant before the hold clamp closes minus 1.65 V (negative = short, the clamp finishes with a step of
that size — the "yank"); fall residual = rail when the zero clamp / in-switch acts. E_total = DC-rail
energy minus inductor stored-energy drift, per bank per cycle (gate drive priced separately, §5).

What the CCM rows MEASURE (all pre-stated claims checked, three overturned):

* **Self-regulating, but not to full swing.** With the pre-registered 4 ps zero-clamp pulse the loop
  converges within ONE period to I ≈ 2.46–2.54 mA from every seed (2.8/3.15/3.5), ripple ~10 %, drift
  −0.6..−1.8 %/cycle — but the rising phase lands at 1.19–1.21 V and the hold clamp yanks it 430–476 mV;
  the fallen phase is dumped from ~0.5 V. Cause (from the waveforms): the volt-second balance of a plain
  F→L→R loop is satisfied for ANY swing equal to the post-handover voltage separation (the F and R
  trajectories are mirror images), so it has no full-swing attractor; the pulse adds −5 fWb/third (L fed
  from 0 V while lout sits at ~1.2 V) and pins the current where the in-third asymmetry supplies +5 fWb.
  Without the pulse the current simply decays (−11.4 %/cycle) and the troughs float up to 0.33–0.9 V:
  "self-sustaining" was DERIVED-and-WRONG. R_L does not set the landing (−226 mV at 10 Ω vs −216 at 1 Ω).
* **Constant current under-delivers** (the same finding qal/ldrive made with ideal current sources): the
  bank's C(V) grows as cells turn on and it draws its internal "hold" current during the rise; under
  current drive the rising phase swings ~0.9 V per 92 ps at 2.5 mA (C_eff ≈ 245 fF per phase ≈ 122
  fF/bank, vs 88 fF from the voltage-driven Q_rise). The terminal caps cost another ~0.3 V of separation
  per side at each handover (5 fF: +60 mV landing, −16 fJ/bank).
* **The regulator is the 1.65 V in-feed phase** (steered buck): taking the exhausted falling bank off L at
  t1 and feeding L from the DC rail for the rest of the third keeps V_L > 0 while V_R < 1.65 V, so the
  current rises through the third (exactly the rising-current shape ldrive found optimal) until the rail
  lands. t1 = 0.8 is the speed optimum found (eye 135.0 ps > 129.0, margin 525.5 mV, overlap 39.7 ps,
  stationary within −0.6 %/cycle, P1 confirmed 529/40.9/134.8); t1 = 0.5 lands within −31 mV mean
  (−134..+38) with margin 697 mV and eye 137 ps, at +10 % energy and I0 = 4.4 mA (still rising +4 %/cycle
  towards its equilibrium — the yank is gone, the clamp engages with no step, which is what the
  coordinator's timing-hazard note asks for). The price of the early split is the falling bank's residual
  (0.4–0.5 V) dumped by the zero clamp: E_sw 26–30 fJ/bank.
* **Trough check**: with the clamps the fallen rail sits at −17..−23 mV (pMOS bulk on the phase node)
  for ≤ 4 ps; bank-4 ground current around the trough is bounded discharge, not crowbar (crowbar block in
  each OUT.json).

## 3. Regime (ii) DCM — resonant half-swing

PRE-REGISTERED CORRECTION: the brief's "L ~ 2.2 nH per bank pair" is an arithmetic slip;
π√(L·C_ser) = 92 ps with C_ser = 44 fF gives L = 19.5 nH per pair, 9.7 nH at N=2.

| row (N=2) | L nH | clamp | I_mean | third peak mA | zero at third end? | landing mV | fall residual | value | margin | overlap | eye | E_total |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| L 9.7, 4 ps 0 V pulse | 9.7 | pulse | 2.41 | 3.3–3.7 | NO (no zero crossing in waves 2–4) | −535 | +515 | 144/144 | 327.5 | 28.6 | 124.4 | 264.9 |
| L 9.7, pulse, soft start | 9.7 | pulse | 2.41 (−7 %/cyc) | 3.3–3.7 | NO | −535 | +517 | 144/144 | 328.8 | 28.8 | 124.5 | 264.4 |
| L 9.7, no clamp | 9.7 | none | 1.59 (−16 %/cyc) | 2.6 | NO | −484 | **+988 (trough 0.84 V)** | 144/144 | 348.4 | 69.5 | 167.1 | 270.1 |
| L 6, no clamp | 6 | none | 1.48 | 2.0–2.6, peak at +30..40 ps | NO | −519 | +1043 (trough 0.90 V) | 144/144 | 351.4 | 69.6 | 167.3 | 272.8 |

MEASURED: the resonant exchange is charge-bound — the rising bank can only receive what the falling bank
gives up, which with the bank's own hold current lands it at 1.1–1.3 V; the current never returns to zero
at the third's end (the pulse clamp kicks it, −1.2 mA at L 9.7; without a clamp it carries ~0.4–0.7 mA
over), so "switching at current zeros" never materialised and both DCM "no clamp" rows degenerate into a
0.84–1.65 V half-swing that is still decaying (not a steady state; the wide 167 ps eye is that of rails
that never fall). The pulse-clamped DCM row is a legitimate PASS (eye 124.4, margin 328) but inferior to
CCM-buck on every speed metric and not stationary. Pre-stated pick (i) CCM: CONFIRMED.

## 4. The sharing law (N = 2 vs N = 8 banks per phase, one inductor)

| row | banks on L | L nH | I_mean mA | per-third ripple | 3-cycle max−min (incl. drift) | drift %/cyc | landing | value (copies) | margin | eye | E_total |
|---|---|---|---|---|---|---|---|---|---|---|---|
| N=2 buck 0.8 | 6 | 120 | 3.49 | **0.201 mA = 5.76 %** | 0.25 mA (7.2 %) | −0.57 | −226 | 144/144 | 525.5 | 135.0 | 261.6 |
| N=8 buck 0.8 | 24 | 120 | 13.44 | **0.241 mA = 1.80 %** | 0.80 mA (6.0 %) | −1.57 | −235 | 144/144 + copies 432/432 | 491.9 | 132.7 | 260.6 |
| N=8 buck 0.8 | 24 | 30 | 12.74 | **0.861 mA = 6.76 %** | 1.46 mA (11.4 %) | −1.87 | −271 | 144/144 + copies 432/432 | 470.1 | 131.7 | 259.4 |

MEASURED: at fixed L = 120 nH the ABSOLUTE per-third ripple is the same within 20 % (0.20 vs 0.24 mA,
pre-registered tolerance 25 %) while the current is 3.85× larger, so the RELATIVE ripple falls 3.2×
(predicted 4×), and dropping L to 30 nH = 120/(N/2) at N=8 brings the relative ripple back to 6.76 % vs 5.76 % at N=2/120 nH (ratio 1.17): the 1/N law for L at constant relative ripple holds to ~20 %. ONE inductor serves 3N
banks (24 banks at N=8 with 13 switches); the per-bank energy is N-invariant (260.6 vs 261.6 fJ) and the
per-bank stored energy ½LI² is too (~730 fJ at N=2 → ~10.8 pJ/24 banks at N=8, 120 nH). Caveat: the
3-cycle max−min metric is dominated by drift at N=8 (0.80 mA of which 0.63 is drift) — the per-third
numbers are the ripple.

## 5. Real switches (sg13_lv, V_GH = 2.174 V binding spec) — the construction FAILS

| row (buck t1 0.8, L 120, C_t 50 fF) | steering | hold clamp | I0 | status | rail swing V | hold droop | landing | value | margin | E_dc | E_sw | gate metered | E_total + gate |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| nMOS W=30 @2.174 V | nMOS 30 µm | pMOS 60 µm | 3.5 | ran | 0.48–1.89 | 775 mV | −340 | **7 fails / 144** | **−28.0** | 393 | 168 | 328 | 736 |
| TG W=30 (n @2.174, p @0) | TG 30+30 | pMOS 60 µm | 3.5 | ran | 0.66–1.78 | 564 mV | −312 | **6 fails** | 197.7 | 416 | 188 | 495 | 925 |
| TG W=50, re-seeded | TG 50+50 | pMOS 90 | 7 | Xyce "time step too small" at 735.5 ps (first wave-2 handover) | 0.64–1.83 before the crash | — | — | — | — | — | — | — | — |
| TG W=78, re-seeded | TG 78+78 | pMOS 120 | 9 | same crash, same instant; −241 mA crowbar INTO vddh as the rail hits 1.83 V (pMOS wells) | — | — | — | — | — | — | — | — | — |
| TG W=78, C_t 200 fF | TG 78+78 | pMOS 120 | 9 | did not converge at start | — | — | — | — | — | — | — | — | — |

Diagnosis (a 3T diagnostic deck with every switch current and gate voltage printed, plus a DC probe):
the OFF transfer gates leak < 3 nA and the ON TG measures Ron = 38 Ω at W=30 µm (nMOS alone 44 Ω, hold
pMOS 60 µm 42–80 Ω) — the devices are fine. What fails is capacitance: each 30 µm TG draws 0.3 mA of
displacement current from the moving phase node while OFF, the metered turn-on gate charge is 2.0–2.4
fC/µm (nMOS at 2.174 V) and 2.9–3.0 fC/µm (pMOS at 1.65 V), i.e. ~1.3–1.8 fF/µm of switch capacitance,
so the four switches on a phase node add ≈ 250–300 fF — as much as the bank pair (≈ 245 fF effective)
— and the 3.5 mA steered current swings the node only ~0.4 V per third while the 120 nH loop re-converges
at just +0.3 mA/third. Scaling W with I (needed to hold the Ron drop at ~130 mV) keeps C_sw/C_bank fixed
at ≈ Ron·W × C'_sw × 4 × (1.65 V/92 ps)/ΔV_allowed ≈ 1.6 for a 100 mV drop budget, so there is no width
that escapes it — the same TG intrinsic-RC floor qal/meshdrv hit (its 3.4 kΩ·µm × 1.4 fF/µm). The wider
re-seeded rows then die at the first 7–9 mA handover because the current has nowhere to go for ~3 ps of
transistor dead time (lout spikes, the rail exceeds 1.65 V, the pMOS wells forward-bias into vddh).
Pre-stated risk (nMOS cut-off over the top of the swing) is confirmed as the nMOS-only row's −28 mV.

Gate-drive pricing (per bank per cycle, N=2, 13 switch edges per group / 6 banks): metered Q_up × V_G =
328 fJ (nMOS steering + pMOS hold + nMOS zero) / 495 fJ (TG); the 3.7 fC/µm fit gives 455 (nMOS) /
709 (TG) fJ — the fit overstates the sg13_lv gate charge by 1.3–1.8× at these biases (committed 0.155
fC/µm never used). Even a working real version would therefore sit at ≈ 260 + 328..495 + conduction =
~600–900 fJ/bank/cycle, above the 534 fJ harmonic driver.

## 6. Energy ledger (per bank per cycle, REPORTED, never gated)

| | E_dc rail | I²R_L | switch cond. + charge sharing | E_total sources | gate | total | vs 240.3 | vs 534 |
|---|---|---|---|---|---|---|---|---|
| mesh3 ideal rails (ledger) | — | — | — | 240.3 | 0 | 240.3 | 0 | −55 % |
| meshdrv harmonic flat top | — | — | — | — | — | 534 | +122 % | 0 |
| lsteer ideal, pre-reg. pulse (I0 3.15) | 267.6 | 2.8 | 32.4 | 269.0 | 0 (ideal) | 269.0 | +12 % | −50 % |
| lsteer ideal, buck 0.8 (best speed) | 260.2 | 5.6 | 25.7 | 261.6 | 0 (ideal) | 261.6 | +9 % | −51 % |
| lsteer ideal, buck 0.8, C_t 5 fF (cheapest) | 243.1 | 5.3 | 12.9 | 245.4 | 0 | 245.4 | +2 % | −54 % |
| lsteer ideal, buck 0.5 (no yank) | 303.8 | 9.0 | 30.1 | 288.0 | 0 | 288.0 | +20 % | −46 % |
| lsteer real nMOS (FAILS) | 392.9 | 3.5 | 168.1 | 408.3 | 328 metered | 736 | +206 % | +38 % |
| lsteer real TG (FAILS) | 416.2 | 5.1 | 188.3 | 430.0 | 495 metered | 925 | +285 % | +73 % |

Why the ideal construction cannot beat 240.3: the mesh3 ledger's rail is an ideal RECOVERING source
(E_fall = −115 fJ is credited back), so 240.3 is already the bank's own net draw; a lossless inductor can
only approach it. The DC rail pays the hold charge (150–185 fC/bank at 1.65 V ≈ 250–300 fJ gross) plus
the landing shortfall; what the inductor recycles is the rise/fall edge pair. The ideal-switch rows land
within +2..+20 % of the ledger, 46–54 % below the harmonic driver — consistent with ldrive's 235–265
fJ band for a DC-clamp-finished rise.

## 7. Verdict

Can the 12× wave be driven by a few steered inductors? **In principle yes, as an ideal-switch BOUND; with
real transfer gates at the campaign's binding spec, no.** One inductor per 3N banks (120 nH for 6 banks,
30 nH for 24 — L = 240 nH/N, sharing law measured to 20 %), carrying N × 1.7 mA (3.5 mA at N=2, 13.4 mA
at N=8) with 5.8 % per-third ripple, steered F→L→R every third with the holding bank on a 1.65 V clamp,
sustains the mesh3 wave at every bank on P0 and P1 with a WIDER standing eye than the baseline (135.0 ps
vs 129.0; margin 525 mV vs 509.67; overlap 39.7 vs 37.0 ps) at 245–262 fJ/bank/cycle (ledger 240.3,
harmonic 534). It is NOT self-sustaining as a plain loop (neutrally stable, R-decaying; the pre-registered
zero-clamp pulse pins it at a 0.72 swing with a 450 mV clamp yank): the inductor must be fed from the
1.65 V rail for the last 20–50 % of each third (steered buck), which is also what makes the current rise
through the third as the bank's C(V) demands; t1 = 0.5 lands the rail within −31 mV with no yank (margin
697 mV, eye 137 ps) at 288 fJ. DCM (9.7 nH, corrected from the brief's 2.2 nH) is charge-bound, never
reaches a current zero at the third's end, lands 535 mV short and is not stationary. With real sg13_lv
switches (nMOS at 2.174 V or TG, W = 30 µm, Ron 38 Ω MEASURED) the construction fails value at every
width tried: the switches' own capacitance (2.0–3.0 fC/µm metered) equals the bank load, the rails swing
0.65–1.8 V, and wider/higher-current rows crash at the first handover; the metered gate bill alone
(328–495 fJ/bank) would put any working real version at 600–900 fJ, above the harmonic driver. The
steered inductor is therefore a cheaper IDEAL than the harmonic sustainer (−50 %) but not a buildable one
in this device set; what would change the answer is a transfer switch with a far lower Ron·C product (or
a much larger per-bank load so the bank dominates the node capacitance), not a different L, I or N.

## Files
`PRE_REGISTERED.json` (acceptance, L/ripple/pick pre-stated, corrections dated) · `ICHECK.json` ·
`lsteer.py` (deck/switch/extract harness; `one`, `agg`, `regate`, `deck`) · `results.py`, `finalize.py`
(tables → `TABLES.json`, `RESULTS_rows.json`, `RESULTS.json`) · `runs/<tag>/` (OUT.json, deck, .mt0; the
three `BUG_indd_phaseA_only_*` rows are the quarantined first buck attempt whose 1.65 V in-feed covered
phase A only — recorded, not scored).
