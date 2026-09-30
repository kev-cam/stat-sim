# qal/widebank — PHASE 1, the bank-width sweep

**The user's challenge was well founded, and GAP 1 was a real gap.** Wide banks
*do* amortise. The campaign's ≥23.9× energy ratio for `sha_slice` was a
consequence of measuring 1–7-gate banks, not a property of QAL: at N = 64 gates
per bank the per-gate energy crosses below CMOS, and the campaign's own
admission arithmetic (N_min ≈ 51.9 at the ideal timer floor) is vindicated by
direct measurement at **N_min = 59.5**.

**And the crossing is shallow, conditional, and bought entirely with time and
area.** It exists only when the switch's gate charge is assumed fully recovered.
With a conventional (buildable) switch gate driver, and using the gate charge
this study *measures* — **3.64–3.74 fC/µm, 23.5–24.1× the committed
0.155 fC/µm fit** — **no N up to 256 crosses.** And nothing in a bank-width
sweep makes a level faster: level time rises as N^0.46, so every energy step is
paid for in throughput and in ~30 µm² of MIM tank per gate that never amortises
at all.

> The trade the user described — *higher performance at an area/power cost* — is
> **not** what this axis delivers. Widening the bank trades **area and speed for
> a little energy**: the opposite sign on two of the three axes. The
> area/power-for-speed lever is cell upsizing, which is Phase 2.

---

## Order of work (mtimes are the witness)

| file | mtime (−0700) | what |
|---|---|---|
| `DISK_STATE_BEFORE.txt` | 2026-09-29 19:19:10 | disk state, `df`, git HEAD, sha256 of every committed input |
| `PRE_REGISTERED.json` | 19:21:28 | acceptance, ledger, scaling laws, **and the pre-stated crossing prediction** |
| `PRE_REGISTERED.sha256` | 19:21:36 | `c98fa10887b91177194b59a1d994ec7b83b18561658563f02fab7e09f6ef2f3f`, 20808 B |
| `btk/c_m10_T200_H4_dv1200_free.cir` | 19:36 | **first deck** — the instrument-check re-run |
| `AMENDMENT.md` | 19:5x → end | A1–A11, each with what forced it |

At 19:21:36 this directory contained exactly `DISK_STATE_BEFORE.txt`,
`PRE_REGISTERED.json`, `PRE_REGISTERED.sha256` and an empty `btk/`.

## (b) Instrument check — PASSES, 31/31 digit-identical

`INSTRUMENT_CHECK.json`. Two independent levels:

1. **Re-extraction** of the committed row from the committed `.prn`/`.mt0` with
   the committed `extract.py` → **0 diffs** on every reported quantity.
2. **Re-run** of a **byte-identical** deck (sha256
   `ec034e1681c331b5483b91eb3a31c0213d56afc4a93cf6dea7c9cf641cdf3021`, matching
   `banktank/c_m10_T200_H4_dv1200_free.cir` exactly) in this study's **own**
   private PyMS vae cache → **31/31 quantities identical to every decimal place
   present in the committed file**, relative error `0.0e+00` on all: worst gate
   `90.54454610810019 %`, rails `0.7544238 / 0.6767239 / 0.7312457 / 0.7200878`
   V, `IPK₁ 937.4588 µA`, `IZ`/`IZQ` all four banks, `E_vhi −39.30899999999999`
   fJ, `E_gt −4.102599999999989` fJ, separation `612.378631` mV, stage time
   `190.71083799999997` ps.

**One digit correction to the brief** (AMENDMENT A2): the brief quotes the rails
as `0.7312456 / 0.7200877`; the committed file says `0.7312457 / 0.7200878`. The
re-extraction reproduces the file.

**A0b — the NBANK 3-vs-4 reduction is validated, not asserted.** At N=8,
dV=1.65: bank-2 rail 0.9541151 vs 0.9540702 V (0.005 %), I_pk 1185 vs 1184.94
µA, tank loss 47.133 vs 47.292 fJ (0.34 %), t_hop 126.566 vs 126.493 ps
(0.058 %). All inside the pre-registered 0.5 %.

## Configuration (only what is known to work)

Per-bank tanks (`banktank` 0aae11e) verbatim: m = 10, L = 15 nH **held fixed**,
R_S = 10 Ω **held fixed**, dV = 1.65 V, cell 1.12 p / 0.74 n with supply *and*
bulk on the bank rail, C_L = 2 fF, committed tg15p triple with the A6
tank-referenced park, V_GH = 1.5 V, 2 ps edges, committed true-ZCS
probe-then-cut with zeros probed at **each row's own T and H**, 1F integrators
all t0-referenced, PSP103 + `sg13g2_psp103_tt.lib` + `sg13lv_compat.sp`, tt only.
NBANK = 3: ideal head / **bank under test** / real receiver. The **source-side
cut is structural** here — bank k's tank island shares no node with k±1 — which
is why chain3's diversion path does not exist (AMENDMENT A7).

Scoring is `qal/fcrit`'s criterion, **imported unmodified** (`rescore.Trip`):
bank 2's gates against bank 3's *measured* trip at bank 3's *delivered* rail at
the instant bank 3 commits. Noise budget = **deterministic terms only**; the bare
threshold is primary and the 3σ_trip = 19.323 mV column is shown for continuity
only, because it double-counts mismatch when mismatch is not drawn.

---

## (c) The sweep — every point COMPUTES

ACCEPTED = A1 (all N gates value-correct, individually) ∧ A2 (functional) ∧ A4
(ZCS ≤ 1 µA) ∧ A5 (path identity) ∧ A6 (tank closure). `RESULTS.json :
C_SWEEP_ACCEPTED_SERIES`.

| N | T (ps) | t_hop (ps) | t_settle90 (ps) | I_pk (µA) | W (µm) | **Q_gate (fC)** | E_tank (fJ) | **E/gate floor** | ×CMOS | **E/gate conv.** | ×CMOS | ×CMOS level |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 8 | 160 | 126.5 | 150.7 | 1185 | 30.0 | 109.1 | 47.1 | **6.0090** | 1.451 | **26.340** | 6.362 | 1.72 |
| 16 | 260 | 162.9 | 176.6 | 1531 | 42.4 | 155.0 | 81.9 | **5.1006** | 1.232 | **19.650** | 4.746 | 2.80 |
| 32 | 330 | 216.1 | 196.3 | 2012 | 60.0 | 220.0 | 146.5 | **4.5094** | 1.089 | **14.890** | 3.597 | 3.56 |
| **64** | 440 | 295.8 | 229.9 | 2681 | 84.9 | 312.7 | 267.1 | **4.1034** | **0.991** | **11.502** | 2.778 | 4.74 |
| 128 | 580 | 406.7 | 272.1 | 3614 | 120.0 | 445.5 | 494.3 | **3.8065** | 0.919 | **9.0823** | 2.194 | 6.25 |
| 256 | 790 | 554.5 | 331.2 | 4926 | 169.7 | 634.5 | 931.3 | **3.5980** | 0.869 | **7.3557** | 1.777 | 8.51 |

*floor* = measured ideal-PWL switch gate drive, E_timer = 0 (a strict **BOUND**).
*conv.* = the same tank loss plus this study's **own measured** gate charge
× 1.5 V. ×CMOS is against 4.14 fJ/cell/op; ×CMOS level against 92.8 ps.

**Every gate of every bank at every N is individually value-correct** and every
point passes the functional criterion with **436–465 mV** of bare margin
(373–529 mV across the whole study including the switch-width sub-sweep) — at
dV = 1.65 V the signal is fully restored, so **the functional criterion is not
the binding constraint anywhere in this sweep; the hop time is.** Per-gate
settling is 95.2–99.8 % worst gate (reported, not the discriminator, per
`fcrit` 0ec8de5).

**A metric trap, named so it cannot be quoted:** gates/ps rises 0.050 → 0.324
across the sweep, which *looks* like a 5.4× throughput win over the CMOS block's
56 cells / 928 ps = 0.060 gates/ps. It is not one. Both technologies evaluate a
level's gates in parallel, so the fair time unit is **one level**, and per level
QAL is 1.7–8.5× slower *regardless of how wide the bank is*. Widening the bank
buys energy, never level rate.

**Tight beats** (`RESULTS.json : C_TIGHT_BEAT_ROWS_A4_FLAGGED`) — these pass A1
and A2 but carry a 1.59–7.72 µA return-hop residual against the committed 1 µA
gate (worth 4.5 × 10⁻⁴ fJ of stored energy, 10⁻⁵ of the row; AMENDMENT A10):
T = 130 / 180 / 230 / 310 / — / 570 ps → **1.40 / 1.94 / 2.48 / 3.34 / — / 6.14×
the CMOS level time**, with energies matching the accepted rows to 4 decimals.
The true minimum beat is bounded below by t_hop and lies between these two sets.

### Controls, all measured

* **A8 timestep** — N=64 at the scaled 0.707 ps vs the unscaled 0.25 ps: E/gate
  4.1034 vs 4.1035 (0.002 %), margins identical. **PASSES.**
* **Park ammeter transparency** — N=8 with and without: identical on every
  reported quantity. **PASSES.**
* **Random-pattern fixture control** — N=64, genuinely different arrangement,
  same 40-of-64 HIGH count: *every* quantity identical to the digit. This makes
  the declared two-class degeneracy **MEASURED**: a bank of identical cells on
  one lumped rail is a function of the HIGH **count** only. The intra-class
  spread is exactly 0.000 mV in every bank of every row — so "per gate" yields
  two trajectories here and cannot catch a single-gate outlier. Inherited
  knowingly; the N-wide VALUE and functional checks are still per-node.

---

## (d) Where per-gate cost stops falling, and what defeats the amortisation

**It stops at N = 64.** Improvement per doubling: 15.1 % → 11.6 % → **9.0 %** →
7.2 % → 5.5 %. The 32→64 step is the first under 10 %, and each step costs
27–36 % of level time. The measured local exponent of E/gate decays −0.237 →
−0.081: this is **not** 1/N amortisation and never was.

Measured per-gate exponents in N (`RESULTS.json : D_SCALING_EXPONENTS_in_N`):

| term | per-gate exponent, 8→256 | reading |
|---|---:|---|
| park-path ring-down | **−0.549** | amortises fastest — **not** the defeater |
| switch gate charge (conventional drive) | **−0.492** | ≈1/√N, and it is the biggest term |
| tank loss | −0.139 | falling, and *decelerating* (−0.203 → −0.086) |
| switch conduction | **−0.059** | **flat** — the constant-Q floor, as pre-stated |
| inductor series R | **+0.249** | **grows**, as pre-stated |

**Three mechanisms, in order of size:**

1. **The switch gate charge is the defeater, and it is 24× larger than the
   record says.** Measured **3.635 → 3.739 fC/µm** — dead linear in W, and
   23.45–24.12× the committed `lsweep` 0.155 fC/µm fit that the brief and the
   admission rule both use. Q_gate ∝ N^0.508 (exactly √N, because W ∝ √N by
   construction), so per gate it falls only as 1/√N and is still **3.72 fJ/gate
   at N = 256** — most of the whole CMOS budget. This is the campaign's own
   `per_gate_scaling_rider` ("does 16 µm of switch serve only 8 gates?"),
   answered: **no, and the charge is 24× worse than booked.**

   *Independent cross-check that my number, not the fit, is the right one:*
   first principles for a 0.13 µm sg13g2 LV device gives C_ox ≈ 1.95 fF/µm of
   width, so C_ox·V_GH ≈ 2.93 fC/µm, plus gate–drain/gate–source overlap at
   1.5 V ≈ 0.9–1.5 fC/µm ⇒ **3.8–4.4 fC/µm expected**. The measurement
   (3.64–3.74) lands inside that window; 0.155 fC/µm does not come within 20×
   of it. The likely origin of the fit is a *net* charge over a full
   close-then-open (which cancels) — but a conventional driver pays the full
   |Q| in **each** direction, which is what the admission arithmetic needs and
   what this study integrates (close and open edges metered separately against
   a pre-close reference, AMENDMENT A6). The consequence for the campaign is
   direct: the `E_tap` term in
   `N_min = (39.6 + E_timer)/0.8309` is understated, and on the per-gate
   reading the denominator is negative, i.e. **gate-charge recovery is
   existential for QAL admission, not a tuning knob** — which is exactly what
   `sar/RESULTS_SAR.json : per_gate_scaling_rider` warned and this sweep now
   measures.
2. **A hard constant-Q conduction floor.** Switch conduction per gate is flat
   (N^−0.059) because holding Q constant holds the fractional resonant loss
   π/Q constant. Nothing about width helps it.
3. **A term that actively grows.** The 10 Ω inductor series resistance is *not*
   scaled with the bank, so its loss goes as N^1.249 — **+0.249 per gate**. It is
   small in absolute terms (0.108 → 0.254 fJ/gate) but it is the sign that puts
   a floor under everything else.

**Extrapolated floor** (DERIVED, two-point solve of a + b/√N on N = 128, 256):
**3.095 fJ/gate = 0.748× CMOS.** Even at infinite bank width, at the ideal-PWL
gate-drive floor with a free timer, the best QAL can be is **1.34× cheaper than
CMOS per gate.**

**Two favourable deviations from my own pre-registration, both real:**
* t_hop grows as **N^0.426**, not N^0.5, and I_pk as N^0.411 — the measured
  secant bank capacitance per gate *falls* with N (ratio 2.762 → 1.536, so
  m_eff rises 3.62 → 6.51; AMENDMENT A9), so the hop dilutes its own fixed
  parasitics. The time penalty is milder than predicted.
* Recycle fraction **rises** 17.3 % → 36.1 % for the same reason.

**Two BOOKINGS that flatter the floor row and are named, not hidden:**
* The ideal-PWL gate-drive integrator goes **negative** (−0.30 → −10.21 fJ/bank)
  — the PWL sources *receive* energy. A perfectly recovering driver nets zero,
  not negative, so the "floor" row is subsidised by up to 0.04 fJ/gate.
* The pMOS well rail draws **−13.5 → −77.2 fJ/bank** (1.68 → 0.30 fJ/gate),
  uncharged under the committed ideal-rails convention. At N = 64 that is
  **0.607 fJ/gate**: charging it puts the point at 4.710 fJ/gate = 1.138× CMOS
  and **erases the crossing outright.**
* The converter that must resupply the tank loss, and the timer, are not
  simulated. Every row is a **BOUND**.

---

## (e) THE CROSSING

`RESULTS.json : E_CROSSING`, `G_BEST_MEASURED_POINT_ANY_WIDTH`.

| ledger row | crosses 4.14 fJ/cell/op? | first N | ×CMOS there | N_min interpolated | best measured |
|---|---|---:|---:|---:|---|
| ideal-PWL floor, timer = 0 (**BOUND**) | **YES** | **64** | **0.991** | **59.5** | N=256, 3.598 fJ, 0.869× |
| ideal-PWL floor, timer = 3.5227 fJ | **YES** | **128** | 0.926 | 66.2 | N=256, 3.612 fJ, 0.872× |
| conventional driver, measured Q_gate, timer = 0 | **NO** | — | — | — | N=256, 7.356 fJ, **1.777×** |
| conventional driver + timer floor | **NO** | — | — | — | N=256, 7.370 fJ, **1.780×** |

**The answer, in one line: the crossing exists at N = 64 and it exists only if
the switch's gate charge is fully recovered.**

* **N = 64, W = 84.9 µm, T = 440 ps: 4.1034 fJ/gate = 0.991× the CMOS
  4.14 fJ/cell/op**, all 192 gates value-correct, functional margin 438.5 mV,
  t_hop 295.8 ps. Measured N_min = **59.5** gates/bank — the campaign's own
  arithmetic said 51.9, so **its admission rule was right to within 15 %.**
* The **level time** is **4.74× CMOS** at that point (3.34× at the A4-flagged
  tight beat T = 310). At the best energy point, N = 256, it is **8.51×**
  (6.14× tight). There is no speed win anywhere in this sweep, and by
  construction there cannot be — I pre-stated that.
* Against the *easy* bar (10.0831 fJ per inverter hi+lo cycle) QAL is below at
  **every** N including N = 8 (0.596× at N = 8). **That crossing means nothing**
  and is reported only so it cannot be quoted as the result.
* On the **iso-swing** DERIVED column (CMOS forced to 1.65 V, 7.827 fJ) QAL is
  below at every N. That column flatters QAL — the 1.65 V swing is *QAL's*
  requirement, not CMOS's — and is not the headline.

### The switch-width sub-sweep changes the conventional answer materially

`RESULTS.json : F_SWITCH_WIDTH_SUBSWEEP`. The pre-registered constant-Q width
**over-sizes** the switch at small N; the pre-registered falsification signature
"if W/2 costs nothing the amortisation is better than I predicted" **fired**.

| N | energy-optimal W (floor) | energy-optimal W (conventional) | speed-optimal W |
|---:|---|---|---|
| 32 | 0.5× (30 µm) | 0.5× | 0.5× |
| 64 | ≤0.5× (42 µm) | ≤0.5× | 1.0× |
| 256 | 1.0× (170 µm) | **0.25× (42 µm)** | 1.0× |

The optima **split** as N grows: on the buildable ledger the energy optimum runs
toward the smallest switch that still computes, and pays for it in hop time.
**Best conventional-driver point measured anywhere: N = 256, W = 42.4 µm →
4.689 fJ/gate = 1.133× CMOS at t_hop = 971.9 ps = 10.47× the CMOS level time**
(A1 and A2 pass, margin 385 mV, worst gate 99.81 %; A4-flagged at 1.6 µA).
It still does not cross. DERIVED extrapolation puts the conventional-row
crossing at **N of order 10³ gates per bank at a ~2 ns hop** — a bank width no
level of any real block has.

### And the area, which is the part that does not amortise at all

| | per gate | at N = 256 per bank |
|---|---:|---:|
| MIM tank (1.5 fF/µm²) | **29.98 µm², constant in N** | 7675 µm² |
| switch active | 0.092 µm² (falls as 1/√N) | 23.5 µm² |
| cell active | 0.242 µm² | 61.9 µm² |
| **tank / cell active** | **124×, at every N** | |

Plus **one 15 nH inductor per bank**, not area-modelled here and described in the
committed record as "the architecture's largest/scarcest component". The tank
area per gate is *exactly* constant because C_tank ∝ N by construction — so the
one cost that a width sweep cannot amortise is the dominant one.

### The structural objection that outranks all of the above

The amortisation needs **wide banks**, and the `sha_slice` `nand_mindepth`
profile is **41 / 32 / 26 / 21 / 6 / 5 / 3 / 7 / 4 / 7 / 3 / 4 / 1 / 1**. A bank
may only hold gates that are *independent*, so for a single block instance N is
capped by the widest level = **41**, and at N = 41 the floor-row energy
interpolated in 1/√N between the measured N = 32 and N = 64 points is
**4.35 fJ/gate — still above 4.14, so the crossing is unreachable for one
block**, and that is on the subsidised floor row. N ≥ 64 is reachable only by packing **independent instances** into
one bank: at level width 3 that needs ~22 lanes. That is precisely the
GPU-batched / SIMT independent-lane workload the north star targets — and it is
the only place this result lives.

---

## Files

| file | what |
|---|---|
| `PRE_REGISTERED.json` / `.sha256` | the pre-registration, incl. the pre-stated crossing prediction |
| `AMENDMENT.md` | A1–A11 with what forced each |
| `DISK_STATE_BEFORE.txt` | order-of-work witness + input hashes |
| `INSTRUMENT_CHECK.json`, `INSTR_A0a_reextract.json` | (b), both levels |
| `wb.py` | deck generator (banktank verbatim + the N axis, the park ammeter, the gate-charge integrators) |
| `wbx.py` | per-row extractor; imports `fcrit/rescore.Trip` unmodified |
| `drive.py` | one sweep point end to end |
| `warmset.py` | disjoint PyMS geometry warm (18 geometries; `m=` is discarded by the shim, A3) |
| `analyse.py`, `SWEEP.json` | sweep table + fits |
| `results.py`, `RESULTS.json` | the record |
| `row_*.json`, `POINT_*.json`, `zeros_*.json`, `log_*.txt` | per-row extractions, per-point logs, measured zeros |
| `btk/` | private copy of the committed banktank machinery for the instrument check |

## Pre-registration scored

| pre-stated | outcome |
|---|---|
| per-gate energy falls, as a + b/√N + c/N with a > 0, **not** 1/N | **RIGHT.** Local exponent decays −0.237 → −0.081; extrapolated a = 3.095 fJ/gate |
| the switch defeats it *through its width requirement*, not a fixed charge | **RIGHT**, and worse than stated: the charge is 24× the booked fit |
| knee at N = 64–128 | **RIGHT: 64** |
| a second, *growing* term: fixed R_S, and hold-time loss | **RIGHT on R_S** (+0.249/gate). The park/hold term instead amortises fastest (−0.549) — that half was **WRONG** |
| crossing exists, at **N = 64** | **RIGHT — N = 64, N_min 59.5** |
| value there 2.5–4.0 fJ/gate at the floor | **NARROWLY WRONG: 4.103 fJ**, just above the band |
| 3.5–5.5 fJ/gate conventional, "marginal-to-absent" | **WRONG, too optimistic: 11.50 fJ/gate**, absent at every N |
| t_zcs 340–380 ps, T 420–460, I_pk 3.2–3.6 mA, W 84.9 µm, Q_gate 13.2 fC at N=64 | t_zcs **295.8** (below band), T 440 ✓, I_pk **2.68 mA** (below), W 84.9 ✓, Q_gate **312.7 fC** (**23.8× my figure**) |
| the easy bar is crossed at N=8 and means nothing | **RIGHT** |
| no speed win of any kind from this axis | **RIGHT** |
| W/2 "costing nothing" would mean better and earlier | **FIRED** at N = 32 and 64 |
