# qal/eye/p2 — PHASE 2: the composed timing budget and the fastest sustainable wave

Arrangement UNCHANGED from Phase 1 and from `qal/banktank` `0aae11e`: m = 10
(C_tank 359.79 fF), **dV = 1.65 V**, L = 15 nH, Rs = 10 Ω, tg15p triple at W30,
A6 tank-referenced park, free-running, 4 banks × 8 committed inverter cells
(wp 1.12 µm / wn 0.74 µm, CL **2 fF**), bank k cell i's gate input *is*
`o{k-1}_{i}`, **no flop, latch, buffer, keeper or level shifter anywhere**.

Pre-registration `PRE_REGISTERED_P2.json` sha256
`b333ab252ba09c61ef846c16649e445b91b55949c56c5d1233a9daccbdc53471`, 24452 B,
mtime **2026-09-29 21:46:54 −0700**, written when `qal/eye/p2/` held only
`DISK_STATE_BEFORE.txt` (21:44:29) — no deck, `.cir`, `.prn` or result file
existed. Amendments in `AMENDMENT_P2.md`. Scorecard in `SCORECARD_P2.json`.

---

## Instrument check — INSTRUMENT OK, no simulation required

`INSTRUMENT_CHECK_P2.json`. All four checks were re-extractions or arithmetic.

| check | result |
|---|---|
| **IC-P2-1** re-extract Phase 1's eye from `MARGIN_bank{1,2,3}.csv.gz` with an **independently written reader** (does not import `eyecalc.py`) | **PASS** — 328.599 / 529.641 / 729.382 ps reproduced, worst deviation **0.00036 ps** against a 0.10 ps bar |
| **IC-P2-2** reproduce 61.6 ps and 16.9 % from their source | **PASS** — 61.612 ps and 16.9294 % exactly |
| **IC-P2-3** reproduce 0.46 ps/K and the 16.4 tracking ratio | **PASS** |
| **IC-P2-4** reproduce 57.143 / 94.174 ps and t_reg 307.1 / 335.7 / 390.0 ps | **PASS** |

A third independent confirmation came later: pointing the *Phase-2* extractor at
Phase 1's oracle rows reproduced **128.599 / 129.641 / 129.382 ps** and slacks
**71.401 / 70.359 / 70.618 ps** — Phase 1's handoff table, digit for digit.

---

## ★ THE 61.6 ps TERM IS RECONCILED — it is measured, but not at this operating point

Phase 1 flagged it unreconciled (6.7× larger than anything it measured) and said
Phase 2 must establish which quantity it is before composing it. **Located and
reproduced exactly:**

`qal/qal_bankN_zcs.json` (sha256 `fec5521ee11a2b7f`, mtime 2026-09-25 00:01:45),
cited by `qal/timer/PRE_REGISTERED.json` as *"N=8 zero data-spread 61.6 ps /
16.9 % **at dV = 0.8**"*. Its 9 rows are the Hamming weights 0…8; max − min =
392.144 − 330.532 = **61.612 ps**, and 61.612 / mean(363.9347) = **16.9294 %**.

| | the 61.6 ps figure's point | **this eye's point** |
|---|---|---|
| dV | **0.8 V** | **1.65 V** |
| L | **400 nH** | **15 nH** |
| C | **35.0025 fF** | **359.79 fF** |
| banks | **1** | **4 cascaded** |
| switch | **held ON** (freeze probe) | **opened at the true ZCS** |
| hop zero | ~364 ps | **125.5 ps** |

So "N-invariant" means invariant in the **gate count** of one bank for
worst-case data. It does **not** claim invariance in dV, L, C_tank or topology,
and its own citation says `at dV=0.8` on its face. Phase 1's 7.84–9.23 ps is the
*same quantity* at the eye's own operating point. **61.612 ps is 49 % of the hop
here**, not a perturbation — so I did not extrapolate it. I **measured** it
(below).

## ★ Phase 1's eye used an ORACLE TIMER. That is the largest correction Phase 2 makes.

`bt.schedule` (bt.py:101–130) sets `o_k = c_k + tzr_k`, and Phase 1's
`run_pattern.py` **re-probed `tzr`/`tzq` per data pattern**. Every pattern got
its own switch schedule, derived from its own measured zeros. A real machine has
**one** calibrated timer — `qal/sar` states the architecture's condition
explicitly: *"both options calibrate a fixed centered pattern"*.

So instead of arguing which number to charge, the experiment: **one schedule,
calibrated on the centred weight-4 pattern (P3), every data vector run on it.**

| T = 200 ps, all 9 Hamming weights | bank 1 | bank 2 | bank 3 |
|---|---|---|---|
| ORACLE t_valid (Phase 1) | 128.599 | 129.641 | 129.382 ps |
| **CALIBRATED t_valid** | **126.132** | **126.263** | **126.634 ps** |
| difference | **−2.490** | **−3.405** | **−2.777 ps** |

**The calibrated eye opens EARLIER.** That refutes my pre-registered EY1 on
*sign*. Because EYE2's decision level comes from each pattern's own `.mt0`, a
lower delivered rail would manufacture a spurious earliness — so I added a
control (**not pre-registered**, AMENDMENT A7): recompute the calibrated margins
against the **oracle's trip frozen**. Result **126.109 / 126.236 / 126.605 ps** —
**≈99 % of the shift is the driver, ≈1 % the decision level.** The earlier
opening is real. Mechanism: an off-zero switch leaves current still driving the
rail, so the pull-up resolves sooner.

**I decline to bank that credit.** U1 is charged as **0**, not −3.4 ps
(AMENDMENT A9) — it is an energy-for-time trade (**734–1042 µA** of off-zero
switching against a 1.17–1.31 mA peak) at one calibration choice, and banking a
credit for a timer error *helping* is fragile.

**A6 fails by construction on a data-blind schedule** — 26.3–128.4 µA residual at
the commanded open, exactly as pre-registered (B2). A6 is a *probe-validity*
gate; this is the measured **energy** cost of a calibrated timer, reported never
gated.

---

## (a) THE BUDGET, CHARGED

Constraint: **t_valid(schedule, mismatch contour, worst bank) + U_timer ≤ T**,
with `t_valid` measured from the driver's own rail start `c_k` and the sampling
instant at `c_k + T` (bt.py's own `bnd_k`, which equals `c_k + T` at H = 4).
Already inside `t_valid`: worst-case data (intersection over all 9 weights), the
calibrated-timer schedule error, and mismatch at the 3σ contour.

### U1 data — charged 0 ps, three readings all MEASURED at this point

The inherited term was charged by **deliberately mis-timing the schedule** on
this arrangement rather than extrapolating (AMENDMENT A8). A p-p spread S seen by
a centre-calibrated timer is at most ±S/2.

| schedule error | t_valid @ 3σ_total (bank 3) | charge |
|---|---|---|
| ±4.8 ps — **MEASURED actual** (R1) | **135.869 ps** | — |
| ±10.62 ps — inherited **fraction** 16.9294 % × 125.49 ps (R3) | 136.084 ps | **+0.215 ps** |
| ±30.806 ps — inherited **absolute** 61.612 ps p-p (R2) | **157.612 ps** | **+21.743 ps** |

**The binding limb is the EARLY (negative) offset** — the switch opens before the
true zero, the rail gets less charge, the pull-up weakens and the margin slope
collapses from 16.8 to **3.84 mV/ps**. That is the *same direction* as the
timer's cold corner, independently confirming the brief's saving sign.

**There is a knee between ±10.6 and ±30.8 ps**: below ~±10 ps the data term is
essentially free; at ±30 ps it costs 21.7 ps of beat.

### U2 timer — 7.272 ps, and it is ONE term, not two

* charge = 0.46 ps/K (MEASURED) × 16 K (MEASURED benign band) = **7.36 ps**,
  **one-sided cold**
* **ANTI-DOUBLE-COUNT, verified:** 0.46 × 60 = 27.6 ps on the 265.623 ps line =
  **10.391 %**, against the MEASURED RC-soft limb **10.23 %**. *The drift rate
  and the tracking ratio's soft limb are the same measurement.* Charged **once**.
* the **16.4 ratio's** role is that the term does **not cancel**: the timed
  quantity is LC-stiff (+0.736 %/85 °C), the timer RC-soft (+10.23 %/85 °C). The
  LC limb over the same band is **0.088 ps** — negligible. Differential =
  **7.272 ps**.
* **the saving sign**: hot → line slows → T grows → sampling later → *more* slack
  → benign; cold → early → bad. **Measured confirmation**: the stress test's
  binding limb is the early offset.

### U3 mismatch — 9.235 ps, and σ_trip alone understates it 5×

Read as the **shift of the opening between margin contours**, not by dividing by
a local slope — the local derivative is the wrong instrument (bank 2's curve
shows 37 mV/ps over one 0.1 ps cell but ~6 mV/ps over the next 20 ps).

| | σ (mV) | MEASURED time charge (bank 3) |
|---|---|---|
| σ_trip only — *the brief's term*, a **LOWER bound** (dw/dl excluded) | 6.441 | **1.757 ps** |
| + driver delivered-level σ, **MEASURED** `qal/mcsize` 300 samples | 22.4 | |
| **σ_total** | **23.308** | **9.235 ps** |

σ_trip charges only the **receiver's** decision level; the **driver's** delivered
level is a different random variable and is 3.5× larger. Phase 1's 0.53–1.71 ps
is reproduced exactly under σ_trip. **The 3σ right edge lands ~950 ps after
`c_k`** — it is a HOLD question and does not bind setup, as pre-registered.

### U4 exit receiver — 0 ps, a PRECONDITION not a term

`qal/mcsize`: at the chain exit, **RX_SKEW** (0.15 µm-p / 1.48 µm-n) **0/300**
failures vs **RX_STD** (1.12 / 0.74, the banktank cell) **191/300** = 36.33 %
yield [30.9, 42.1]. **Every beat here is conditional on the exit receiver being
the skewed cell**; with the standard cell the QAL→synchronous boundary is a coin
flip at any beat and timing is not the binding constraint. `qal/mcsize` also
measured **3694/3900 pull-UP** vs **0/3300 pull-DOWN** failures — independently
confirming, under mismatch on a different instrument, that the binding polarity
is **HIGH** at every bank.

---

## (b) ★ THE FASTEST SUSTAINABLE WAVE = **143.14 ps**

`t_valid` is **BEAT-PERIOD INVARIANT** — MEASURED, `TVALID_VS_T.json`. Bank 3
over T = 200→140 ps: 126.634 / 126.666 / 126.701 / 126.734 / 126.761 / 126.806,
a span of **0.171 ps**. The rail-transfer zero itself moves ≤ **0.0091 ps** and
the return zero ≤ 0.0861 ps. Its source is the LC half-period, set by L and
C_tank — not by the schedule. (Pattern reduction {P1,P2,P3} **VERIFIED** against
all 9 weights at T = 200: identical to **0.0000 ps**, binding patterns P1/P2 —
pre-registered F4 check passed.)

| reading | t_valid @ 3σ_total | + U2 | **T_SUSTAINABLE** | σ_trip-only variant |
|---|---|---|---|---|
| **R1 MEASURED HERE** (the machine's real condition) | 135.869 | 7.272 | **143.141 ps** | 135.664 ps |
| R3 inherited **fractional** | 136.084 | 7.272 | 143.356 ps | 133.493 ps |
| **R2 inherited absolute 61.612 ps** (stress) | 157.612 | 7.272 | **164.884 ps** | 137.013 ps |

**Closure demonstrated by measurement, not arithmetic:** budget = 16.507 ps.

* **T = 145 ps** → slack **18.239 ps** > budget → **OPEN**
* **T = 140 ps** → slack **13.194 ps** < budget → **CLOSED**

### How much larger than the single-point beat

The only apples-to-apples reference holds arrangement, dV **and** criterion fixed
and changes only whether the budget is charged:

| | ps |
|---|---|
| single-point beat (eye opens exactly at the sampling instant, budget **not** charged) | **126.634** |
| **sustainable beat (full budget charged)** | **143.141** |
| **larger by** | **+16.507 ps = 1.130×** |

Under the inherited-absolute reading it is **164.884 ps = 1.302×**.

*Other campaign beats are NOT this quantity and are not quoted against it:*
`qal/fcrit`'s measured banktank beat of **150 ps** is at **dV = 1.2 V** under its
*functional* receiver-referential criterion with a noise budget; banktank's
committed **200 ps** headline is the 32/32-value-correct beat at dV = 1.2 V.
`qal/fastwave`'s beats are a **different cell** (pass-gate TG-XOR, t_level
205–322 ps) and `qal/widebank`'s are N = 16…256.

### ★ A SECOND, INDEPENDENT LIMIT THAT MAY BIND FIRST

`A6_VS_BEAT.json` — the calibration pattern's **own** probe, A6-gated:

| T (ps) | worst RISE (µA) | worst RETURN (µA) | A6 ≤ 1 µA |
|---|---|---|---|
| 200 / 180 / 160 | 0.0081 / 0.0060 / 0.0095 | 0.0121 / 0.0126 / 0.0078 | pass |
| 150 | 0.0070 | 0.2682 | pass |
| **145** | 0.0052 | **1.4023** | **FAIL** |
| **140** | 0.0037 | **2.9486** | **FAIL** |

**F2 TRIGGERED.** A hard knee between 150 and 145 ps, **exclusively on the RETURN
zeros**; the rise side is clean at every beat. The setup budget depends on the
*rise* zero, so the `t_valid` numbers stand — but **below T ≈ 150 ps the
committed sequential return-ZCS protocol can no longer place the return zero
within the inherited 1 µA tolerance at this swing.** That constraint sits at
~150 ps, *above* the 143.14 ps the timing budget allows, so **on this arrangement
and at this swing the return-zero schedule, not the timing budget, is the first
thing to break.** Reported as its own finding, not folded into the budget.

---

## (c) LOAD-MATCHED CMOS AND THE FLOP TAX

**Load matching: 57.143 ps at 2 fF**, because the banktank cells this eye is
measured on carry **CL = 2.0 fF**. Quoting the 6.91 fF figure (94.174 ps) would
flatter QAL by **1.648×**. Same choice, same reason, as
`qal/sha256/p2/COMPARISON.json`.

### THE LIABILITY — stated first, and no latency win is claimed

| | ps per logic level |
|---|---|
| **QAL** (T_sustainable, 1 level/bank MEASURED) | **143.141** |
| **CMOS** load-matched level | **57.143** |
| **QAL is SLOWER by** | **2.505×** |

A QAL level is the rail transfer with the logic resolving **inside** it, at a
**lower rail** than CMOS's supply. **Per-level latency can never beat CMOS and no
latency win is claimed anywhere.** Any win must be **throughput**, via the absent
flop tax.

### The flop tax and the initiation interval

* `t_reg(2 fF)` = **315.378 ps**, DERIVED by linear interpolation between the
  MEASURED 307.1 ps @ 0 fF and 335.7 ps @ 6.91 fF. Liberty is **1.11–1.21×
  optimistic**, so this is a **LOWER bound** on the flop tax — the
  **conservative** choice for QAL. Inflated band 350.1–381.6 ps reported, not used.
* **II = H·T + tzq** = 4 × 143.141 + 153.539 = **726.10 ps**. A bank cannot accept
  a new datum until its return switch has opened at its own zero. `qal/fcrit`
  quotes II = H·T, which **omits the return**; both conventions are reported
  (AMENDMENT A11) and the headline uses the strict form.

### ★ CROSSOVER D — H = 4 (measured), strict II, 1 level/bank

| clock corner | CMOS stage (flop every level) | **D vs flop-every-level** | **D vs best iso-D CMOS** |
|---|---|---|---|
| ideal (unc = 0) — most hostile to QAL | 372.52 ps | **2** | **8** |
| tree (unc = 100) | 472.52 ps | **2** | **6** |
| flow (unc = 250) | 622.52 ps | **2** | **3** |

At 2 levels/bank (ARCHITECTURAL, not measured — banktank's cells are inverters)
the iso-D crossovers halve to **4 / 3 / 2**.

**Reading it honestly.** Against a CMOS pipeline flopped every level, QAL's
throughput wins from **D = 2** at every clock corner — that is the absent flop
tax doing exactly what it should. Against the *best* CMOS, free to flop only
every D levels and amortise the tax, QAL needs **D = 8** at an ideal clock, and
only reaches **D = 3** once a realistic flow-level clock uncertainty is charged.
**The win is real but it is narrow at an ideal clock and it lives entirely in
deep, streaming, flop-free pipelines** — which is the north-star GPU-lane shape,
not a latency-recurrence machine.

### H = 2 was ATTEMPTED and is NOT VALIDATED at this swing

H multiplies the beat in II, so it dominates this verdict. At H = 2 the
crossovers would be **2 / 3** (strict II) — but `H2_ATTEMPT.json`: at
H = 2, T = 145 ps, dV = 1.65 V the calibration probe **fails A6 on the RISE
side**, iz3 = **−8.763 µA**, iz4 = −8.295 µA, while iz1/iz2 are clean at
−0.0037/−0.0031 µA.

**Mechanism found, and it predicts which banks fail.** At H = 2,
`r_{k−2} = c_{k−2} + 2T = c_k`: bank k−2's return switch closes exactly when bank
k begins its raise, and its return window spans the whole raise —
bank 3 raise [490.0, 615.2] vs bank 1 return [490.0, 638.9]; bank 4 raise
[635.0, 759.5] vs bank 2 return [635.0, 786.0]. Only banks 3 and 4 have a k−2
predecessor, and **exactly those two fail**. (I first stated this with the wrong
index — k−1 rather than k−2 — and corrected it before publication.)

`qal/fcrit` measured that H = 2 clears down to T = 120 ps on real-receiver links
and that the best II is H = 2 / T = 160 ps — **but at dV = 1.2 V**. This study
does **not** reproduce H = 2 at dV = 1.65 V and says so rather than inheriting
the optimistic reading. Fixing it is a **schedule** question (stagger the return,
or H = 3), not a device limit, and is not run here.

---

## (d) THE SPEC ON THE TIMER

The eye is **not** narrower than the jitter: at T = 200 ps the setup slack is
73.37 ps against 61.6 ps. But **at the sustainable beat the entire slack is the
budget**, so the timer spec is what sets the speed:

1. **Drift/recalibration.** The timer's share is **7.272 ps of the 16.507 ps
   budget (44 %)**. To hold 143.14 ps, recalibrate at intervals no longer than
   **±16 K** of junction-temperature excursion at the MEASURED **0.46 ps/K** —
   equivalently, a drift rate ≤ **0.454 ps/K** if recalibration is every 16 K.
   Only the **cold/early** direction needs charging.
2. **A tracking replica does not help, and that is measured.** Tracking ratio
   **16.4** cold: the timed quantity is LC-stiff, the timer RC-soft. A replica
   line tracks *gate RC*, not the *LC* hop it is timing, so it cancels ~1 % of
   the term (0.088 of 7.36 ps). **The timing reference must be LC-derived or
   recalibrated against the hop itself — not an RC delay line.**
3. **Schedule (data) error: the actionable knee.** Hold the schedule error below
   **~±10 ps** and the data term is essentially free (**+0.215 ps**). At
   **±30.8 ps** — the inherited 61.6 ps p-p — it costs **+21.743 ps of beat**,
   i.e. the sustainable wave slows from 143.14 to **164.88 ps, a 15.2 % speed
   loss**. That is the price of the brief's dominant term, *measured at this
   operating point* rather than extrapolated.
4. **Mismatch is the largest single term and is not a timer problem.** 9.235 ps
   of the 16.507 ps budget (56 %) is mismatch, and σ_trip = 6.441 mV is a
   **lower** bound. It is bought with **device width at the receiver**, not with
   timing — and the exit receiver *must* be the skewed cell regardless (0/300 vs
   191/300).

**If the timer cannot hold ±10 ps of schedule error and ±16 K of recalibration,
the honest framing is a slower beat, not a failure of QAL.**

---

## Scorecard on my own pre-registered expectations

`SCORECARD_P2.json`. **ZERO clean unqualified hits**, as in Phase 1.

| | verdict |
|---|---|
| EY1 calibrated eye opens 5–25 ps **later** | **REFUTED** — wrong **sign**; opens 2.5–3.4 ps *earlier* |
| EY2 t_valid grows 0–15 ps, point +6 ps | **PARTIAL** — direction right and monotonic, magnitude wrong by **35×** (0.171 ps); stated mechanism did not manifest |
| EY3 T_sus 145–175 (R1) / 195–215 (R2) | **REFUTED** — 143.14 (miss by 1.86 ps) and 164.88 (miss by 30 ps) |
| EY4 crossover D ≥ 2 and ≥ 3 | **SPLIT** — D ≥ 2 **exactly right**; iso-D is 8 not 3 at the measured H = 4. My own stated low confidence, and my stated reason (II is the term most likely to sink it), were both right |
| EY5 mismatch < 5 ps even under σ_total | **REFUTED** — 9.235 ps, the **largest** term; my HIGH confidence was misplaced |
| EY6 bank 2 binds at every T | **REFUTED** — bank **3** binds on the calibrated schedule; the binding bank *changed* with the schedule |

Both consequential misses (EY1's sign, EY5's magnitude) came from reasoning off
Phase 1's **oracle-schedule** margin slopes (28–38 mV/ps), which do not survive
the change to a calibrated schedule (16.8–24.6 mV/ps, collapsing to 3.8 mV/ps
under a timer offset). Mechanism predictions again fared better than numbers.

---

## Liabilities and scope

* **Bank 4 is DERIVED** (no bank 5 in a 4-bank deck) and is never a headline
  number. Banks 1–3 have real measured receivers; **bank 3 is the binding bank**.
* **σ_trip = 6.441 mV is a LOWER bound** (dw/dl excluded), so U3 — the largest
  term — is **optimistic**, and with it the sustainable beat.
* **t_reg is a LOWER bound** (liberty 1.11–1.21× optimistic), so the flop tax and
  hence the QAL advantage are understated. Deliberately: it is the conservative
  direction.
* **H = 2 is not validated at this swing** (see above); the throughput verdict is
  at H = 4.
* **T = 145 and T = 140 are not validated operating points** — their return-zero
  probes fail A6 (F2). Their `t_valid` values are used only as evidence of
  T-invariance on the rise side.
* **Three rows were killed mid-simulation** and the cause is **not confirmed** —
  no `dmesg` access, 8.1 GB swap in use. Re-run cleanly; no truncated `.prn` ever
  reached an extraction (AMENDMENT A3).
* **Energy is REPORTED, never gated** (direction: speed, not efficiency). The
  measured 26–128 µA (calibrated) and 734–1042 µA (stressed) off-zero switching
  currents are energy facts, not gates.
* **Leakage under this shim is a LOWER bound** — `sg13lv_compat.sp` declares and
  discards ad/as/pd/ps, so PSP103 defaults apply, JUNCAP200 is enabled, and the
  default PD = 1.00 µm < the 1.12 µm pMOS clips the STI-edge term to zero.
* **No DTA corner was simulated.** Every temperature statement is arithmetic on
  `qal/timer`'s MEASURED drift, never a re-simulation.
* **NO LATENCY WIN IS CLAIMED ANYWHERE.**

## Files

`PRE_REGISTERED_P2.json` (+`.sha256`), `INSTRUMENT_CHECK_P2.json`,
`BUDGET.json`, `TVALID_VS_T.json`, `A6_VS_BEAT.json`, `H2_ATTEMPT.json`,
`SCORECARD_P2.json`, `AMENDMENT_P2.md`, `RESULTS_P2.md`,
`EYE_P2_T{200,180,160,150,145,140}_H4_calibrated_*.json`,
`EYE_P2_T200_H4_ORACLE_phase1.json`, `EYE_P2_STRESS_{±30.806,+61.612,−10.620}.json`,
`zeros_calib_T*_H*.json`, `DISK_STATE_{BEFORE,AFTER}.txt`;
code `p2run.py`, `p2eye.py`, `budget.py`, `compose.py`, `ic_p2.py`, `lanes*.sh`.
