# qal/eye — PHASE 1: THE EYE of a per-bank-tank QAL wave

MEASURED on `qal/banktank` (commit `0aae11e`) at `m = 10`, `T = 200 ps`, `H = 4`,
`dV = 1.65 V`, `L = 15 nH`, free-running, 4 banks × 8 committed inverter cells,
**no flop, latch, buffer, keeper or level shifter anywhere between banks**.

Pre-registration `PRE_REGISTERED.json` sha256
`a053126c158053fb9624095c6ca122cff09f4e61b9230fd4960dd2e4ba450e1f`, 18499 B,
mtime **2026-09-29 20:03:31 −0700**, written when the directory held only
`DISK_STATE_BEFORE.txt` (20:01:44). Amendments in `AMENDMENT.md`, each with the
measurement or environment fact that forced it.

---

## (b) INSTRUMENT CHECK — the committed headline row reproduces exactly

`INSTRUMENT_CHECK.json`. The committed banktank headline row
(`m10_T200_H4_dv1200_free`) was regenerated from scratch in `qal/eye/` under this
study's **own `PYMS_VAE_CACHE`, built from empty**:

| check | result |
|---|---|
| IC1 deck regenerates BYTE-IDENTICALLY from `bt.py` | **TRUE** (30938 B, sha256 `ec034e1681c331b5…`) |
| IC2 `.mt0` numeric keys | **440 / 440 agree**, 0 fail, worst relative deviation **1.0 × 10⁻⁴⁵** |
| IC3 pre-stated derived scalars | **15 / 15 EXACT to every printed digit** |
| IC4 ≥ 99 % pass | **100.0 %** |

Reproduced digit-for-digit: `rail_at_own_boundary_V` = 0.7544238 / **0.6767239** /
**0.7312457** / **0.7200878**; `worst_gate_pct` = 90.54454610810019 at bank 3
gate o3; `per_bank_worst_pct` = 94.71062551313996 / 91.15563969293828 /
90.54454610810019 / 92.65559005443504; `separation_min_mV` = 612.378631;
`IZ_uA` = −0.007584775 / −0.001218682 / −0.0030863600 / −0.002971461.

**The brief's transcription of that row**, checked as pre-declared: bank 2
matches exactly; **banks 3 and 4 differ in the last printed digit** (brief
0.7312456 / 0.7200877 vs file 0.7312457 / 0.7200878, −1.0 × 10⁻⁷ V). Rounding in
the brief, not a discrepancy in the row.

**A cache note that went the good way.** banktank AMENDMENT A0 recorded one
geometry falling back to Xyce's `retrying without zero-valued params` path, hash
`vae_PSP103VA_638208eec0843539`. This study built **all five geometries on the
full path, zero fallbacks** — that hash included.

## Time resolution — and where the precision actually comes from

The committed banktank grid is already **0.25 ps**, not the 10.28 ps the brief
objects to (measured: 10889 points over 2249.32 ps, dt median = dt max =
0.250000 ps). This study refines the max-step ceiling to **0.10 ps** and locates
edges by **sub-grid interpolation of the root of margin(t) = threshold**
(AMENDMENT E1) — because the margin slope at an edge is 28–38 mV/ps, so the root
is located far better than the grid.

**Pre-registered convergence guard** (`CONVERGENCE.json`): the instrument-check
row run at 0.25 ps and at 0.10 ps gives eye openings agreeing to a worst
**0.0018 ps** — 550× inside the 1.0 ps bar. **The grid was never the limit.**

---

## (c)(d) THE EYE — intersection over the COMPLETE data space

Ten transients, **one per configuration**, swept by reading the dense waveform;
no deck was ever re-run for a different sampling instant. All ten pass the
inherited A6 ZCS gate (worst |I(L)| 0.0094–0.0290 µA against a 1 µA budget).

P4 (the pre-registered arrangement control) proved the eye depends **only on the
Hamming weight** of the data, not its arrangement: same weight as P0, ZCS
instants agreeing to 3 × 10⁻⁹ ps, all 76 rail `.measure` keys identical to
**exactly 0.000 V**, eye openings bit-identical. So the data space of an 8-gate
bank is **9 vectors, not 256** — and AMENDMENT E5 added the four missing weights
to make the intersection **complete over every data vector the bank can
present**. The complete-space eye is **identical** to the 6-pattern eye on banks
1–3: **the weight extremes (all-0 and all-1) already bind.**

### Two references, because the pre-registered one measures the receiver

| | early edge is set by |
|---|---|
| **EYE1** receiver's trip at its **instantaneous** rail (pre-registered) | the **RECEIVER'S POWER-UP** — opening lands at exactly `c_k + T + 1.0 ps` |
| **EYE2** the **DATA eye**, fixed level `Trip_S(VR{k+1}B)` (E3) | the **DRIVER's pull-up** — a genuine margin crossing |

The driver's data is fully resolved (HIGH margin +885 mV) ~70 ps *before* its
receiver is powered. **At this beat the data is not the constraint — the
receiver's own rail start is.** EYE2 is therefore the reference every headline
number is taken from.

### The eye (EYE2, all 9 weights, 0 mV, first contiguous run)

| bank | receiver | opens at | valid after own rail start | HEIGHT at the sampling instant | data jitter of the opening (p-p / σ) |
|---|---|---|---|---|---|
| 1 | bank 2 MEASURED | 328.599 ps | **c + 128.599 ps** | **185.8 mV** | 25.3 / 10.3 ps |
| 2 | bank 3 MEASURED | 529.641 ps | **c + 129.641 ps** | **180.7 mV** | 33.7 / 11.0 ps |
| 3 | bank 4 MEASURED | 729.382 ps | **c + 129.382 ps** | **174.7 mV** | 21.3 / 9.0 ps |
| 4 | *DERIVED* | 899.798 ps | c + 99.798 ps | 441.2 mV | 2.7 / 0.9 ps |

`HEIGHT` is the minimum over both polarities, all 8 gates and all 9 weights at
`t = c_k + T`, the instant the receiver's rail starts. In σ_trip units that is
**27 σ** — the height is not the problem.

**Both polarities, and they do not coincide.** The **HIGH (pMOS pull-up)** side
is the sole early-edge limiter: the LOW side opens at `c_k + 0.000 ps` with
**zero measured spread across all nine weights** and is never a constraint. The
binding gate is HIGH at every bank, under the pattern that puts the most cells
pulling **up** simultaneously (P1 for odd banks, P2 for even). This is the
measured form of "free-running chains bind on the pMOS pull-up". Under EYE1 the
polarity separation is 27–28 ps; under EYE2 it is ~129 ps.

### Width — a LOWER BOUND, and why

At zero margin **the eye never closes inside the deck.** The return moves charge
back to the tank but nothing pulls the rail to ground: bank 1's rail bottoms at
0.668 V, recovers to 0.724 V and holds there to 2240 ps with the margin flat.
The true right edge in a *pipelined* machine is the **next datum on the same
bank** at the initiation interval `H·T`, and this single-shot deck contains no
next datum (AMENDMENT E4).

* deck width: **≥ 1911 / ≥ 1710 / ≥ 1511 ps** (lower bounds, clipped)
* pipelined width, DERIVED as `H·T − opening`: **671.4 / 670.4 / 670.6 ps**

---

## (e) WHY THE EYE CLOSES AT EACH EDGE

### Too early — **M1, pull-up limited, into a rail that is itself still rising**

Bank 2, binding pattern P2, gate o0, HIGH, at t = 529.641 ps:
`d(margin)/dt = +27.72 mV/ps`, entirely `dVout/dt` (the fixed reference makes
`d(trip)/dt` exactly zero). The transfer gate **is** conducting and the driver's
own rail is still ramping at **107.8 mV/ps**; the tank is at 0.633 V. The
driver's gate input is 5.4 mV — nMOS overdrive **−0.519 V** (firmly off), pMOS
overdrive **+0.450 V**. Bank 3 is the same picture at +37.82 mV/ps with the rail
ramping at 154.4 mV/ps.

So "not yet distinguishable" is precisely: *the pull-up has not had time at a
rail that is itself only part-way up.*

### Too late — **M4+M5, free droop plus charge redistribution. NOT the return switch.**

This refutes my own pre-registered expectation EX5. At the post-return margin
minimum (bank 2, t = 1407.3 ps): **both the transfer gate and the return switch
are OPEN**, the rail is drooping at −0.73 mV/ps, the tank is *rising* at
+0.13 mV/ps and I(L) = −85.9 µA still circulating in the A6 tank-referenced park
loop. That instant is **207 ps after the return closes and 67 ps after it
opens** — the return switch has already finished. Bank 3: the same, −0.87 mV/ps,
+0.16 mV/ps, −96.9 µA.

The mechanism is also **reference-dependent**, which I did not anticipate: under
EYE1 the candidate is earlier and is M3+M5, because there the decision level
collapses together with the driver's rail and the two partly cancel (floor
71–73 mV instead of 15–20 mV).

### The late edge EXISTS once mismatch alone is charged

| bank | post-return margin floor | in σ_trip (σ = 6.441 mV, itself a LOWER bound) | right edge at 3σ = 19.323 mV? |
|---|---|---|---|
| 1 | **14.934 mV** at 1207.9 ps | **2.32 σ** | **YES** — closes at 1153.6 ps, eye SPLIT, width 823 ps |
| 2 | **16.255 mV** at 1407.3 ps | **2.52 σ** | **YES** — closes at 1356.6 ps, eye SPLIT, width 826 ps |
| 3 | **19.527 mV** at 1606.9 ps | **3.03 σ** | no, by **0.2 mV** |

At the early edge a 3σ bar costs only 0.53–1.71 ps, because the margin there
climbs at 28–38 mV/ps. At the late edge the margin is a nearly **flat plateau**,
so the same bar does not shave the eye — **it creates a right edge that does not
exist at zero margin**, and splits the eye. Of three measured banks, two acquire
a real right edge from the (lower-bound) mismatch term *alone*, before any other
Phase-2 term is charged.

---

## What Phase 2 is owed

`MARGIN_bank{1..4}.csv.gz` — 22 410 rows each at 0.10 ps, both references, both
polarities, with the driver rail, receiver rail and receiver trip alongside. Any
threshold's eye follows without re-simulating.

| bank | data valid after own rail start | **SETUP SLACK to the sampling instant** | ÷ 61.6 ps | pipelined width |
|---|---|---|---|---|
| 1 | 128.599 ps | **71.401 ps** | 1.159 | 671.4 ps |
| 2 | 129.641 ps | **70.359 ps** | 1.142 | 670.4 ps |
| 3 | 129.382 ps | **70.618 ps** | 1.146 | 670.6 ps |

**The binding comparison against the 61.6 ps jitter is the SETUP SLACK, not the
width.** Worst-case data is *already charged* in that 70.36 ps — the intersection
opening is the worst over all nine weights. What is left for timer drift
(0.46 ps/K), the 16.4× replica-tracking failure and mismatch is **70.4 ps**.

### A number I cannot reconcile, flagged rather than absorbed

My measured per-hop data-dependent **rise**-zero spread over all nine weights is
**7.84 / 9.23 / 8.68 / 7.29 ps** peak-to-peak (σ 2.49–3.13 ps), and the
**return**-zero spread is 13.63–24.32 ps. The brief's dominant Phase-2 term is
61.6 ps / 16.9 %, "N-invariant for worst-case data". **At N = 8, dV = 1.65 V,
T = 200 ps that does not reproduce as a zero-crossing spread** — it is 6.7×
larger than anything I measure. Either it is a different quantity (a stage time,
not a zero), or it does not hold at this operating point. **Phase 2 must
establish which before composing it**, because it decides the verdict: charged
against 70.4 ps of slack, 61.6 ps nearly closes the budget, while 9.2 ps leaves
room.

### Steady state — no accumulation, and what that test cannot show

The opening measured from each bank's own rail start is bank-invariant to
**1.04 / −0.26 ps** across banks 1→2→3. The wave is in steady state and the eye
edge does **not** degrade across hops. This test **cannot** separate M6
(propagating collapse) from a locally-set edge identical at every bank — that
needs a single-bank perturbation, which this study does not run.

---

## Scorecard on my own pre-registered expectations

`SCORECARD.json`, scored mechanically off `EYE.json`.

| | verdict |
|---|---|
| EX1 width vs jitter, 300–600 ps | **PARTIAL** — direction right, H-inflation caveat right and understated; point estimate wrong (670 ps) |
| EX2 opening 130–160 ps and earlier than banktank | **PARTIAL** — comparative claim right (21.6–21.9 ps earlier); band missed low by 1.4 ps |
| EX3 binding pattern = most pull-ups; width 60–90 % | **SPLIT** — mechanism **exactly right**; width ratio wrong and too pessimistic (96–97 %) |
| EX4 LOW opens earlier, 20–80 ps | **PARTIAL** — direction and reason right at every bank under both references; magnitude band holds only for EYE1 |
| EX5 late edge = M3 return switch | **REFUTED** — it is M4+M5 with both switches open |
| EX6 3σ eye within 20 ps of the 0 mV eye | **SPLIT** — early edge right; late edge flatly wrong, and wrong in the interesting direction |

**Zero clean unqualified hits. Every quantitative point estimate I made was
outside its band.** The mechanism predictions did better than the numbers.

---

## Liabilities and scope

* **This is Phase 1 only.** The Phase-2 budget composition, and shrinking the
  beat until the eye closes under it, are NOT done here and are not claimed.
* **Bank 4 is DERIVED** (no bank 5 exists in a 4-bank deck); its receiver rail is
  `V(rail3)(t − T)` and its fixed level is `VR4B4`. It is never a headline
  number. Banks 1–3 have real measured receivers.
* **Per-level latency can never beat CMOS** — a QAL level is the rail transfer
  with the logic resolving inside it, at a lower rail than CMOS's supply. Nothing
  here claims a latency win. Any win must be throughput via the absent flop tax.
* σ_trip = 6.441 mV is a **lower bound** (dw/dl excluded), so the 2.32–3.03 σ
  post-return floor is an **optimistic** reading of the late edge.
* Leakage figures under this shim are lower bounds: `sg13lv_compat.sp` declares
  and discards `ad/as/pd/ps`, so PSP103 defaults apply, JUNCAP200 is enabled, and
  the default PD = 1.00 µm is smaller than the 1.12 µm pMOS, clipping the
  STI-edge term to zero.
* Energy is **reported, never a gate** here (direction: speed, not efficiency).
  The 23.213 fJ/bank/hop vs 12.7467 fJ exclusion is an energy verdict and is not
  a gate in this study.

## Cross-campaign caution (reported, not acted on)

`bt.do_probe_oddeven`, the committed 4-run probe reduction, **does not transfer
to dV = 1.65 V at T = 200 ps for any data pattern including the committed one**:
measured residual |I(L)| of **13.8–45.0 µA** against a 1 µA budget, because a
0.5 ps schedule error costs ~12 µA at dI/dt ≈ 23 µA/ps. `qal/widebank` and
`qal/fastwave` are in flight at `dv1650` on this harness; if either uses that
reduction its zeros will not satisfy A6. Their directories were not touched.
Quarantined evidence: `P{1,2,3,4,5}/oddeven4_A6FAIL/`.
