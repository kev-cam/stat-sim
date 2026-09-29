# Per-bank tank capacitors — `qal/banktank/`

> **The user's proposal, verbatim:** *"Another area/speed trade is to give each bank
> its own tank capacitor, rather than feeding the next stage, so the following stage
> can start sooner."*

**VERDICT IN ONE LINE.** Per-bank tanks **do** what the proposal says at the level of
*correctness* — they produce **the first ≥90 %-all-gates-all-stages pass with a clean
value check that this campaign has ever obtained from an unbuffered multi-bank chain**,
and they eliminate rail fade with depth entirely. They **do not** do what the proposal
says at the level of *speed*: an exhaustive interval scan finds that **every picosecond
of ramp/predecessor overlap costs correctness, and the chain computes correctly only at
exactly zero overlap** — so the "following stage starts sooner" mechanism does not
survive measurement, and the concurrent-inductor count at every correct operating point
is **1**, not more. The area/speed trade curve is attached, and it is a **negative on
speed with a decisive positive on function**.

---

## 0. Provenance

| item | value |
|---|---|
| pre-registration | `PRE_REGISTERED.json`, sha256 `d343dfb012b4c583bf4a1c211b63dcdc0ef082c3a4aea18f5c1a65be0f51545d`, 21 647 B, **2026-09-29 08:45:54 −0700** — the **only** file in `qal/banktank/` at that instant (`ls -la` recorded) |
| amendments | `AMENDMENT.md` — A0…A8, each with the measurement that forced it |
| netlist proof | `NETLIST_PROOF.txt`, generated from the measured deck itself |
| instrument check | `INSTRUMENT_CHECK.json` |
| rows | `row_*.json` (70 measured rows, 32 passing), aggregate `RESULTS.json` |
| quarantined | `pre_A6/` — every deck run before the A6 harness fix, preserved, not deleted, not used |
| cache | own `PYMS_VAE_CACHE=…/vae_cache_banktank`; own directory; nothing written to `qal/resv/` or `qal/tsweep/` |

---

## 1. Instrument check (brief step b) — **17 of 18 committed quantities EXACT**

Three committed decks were copied **byte-identical** (md5 verified) and re-run under this
workflow's own cache and working directory — two positive anchors and, as the brief asks,
**one failing peer-chain row, so the harness is anchored to the known negative too**.

| deck | quantity | committed | mine | |
|---|---|---|---|---|
| `lsweep/h_L15_W30_dv120` | **VBEND** | 0.7138163 | 0.7138163 | **EXACT** |
| | VBPK / VAEND / VBOPEN | 0.8368896 / −0.004296807 / 0.7348984 | identical | **EXACT** |
| | IPK / IZ | 971.3203 µA / −0.4958676 nA | identical | **EXACT** |
| | VSWPK / VSWMN | 1.2 / −0.07782217 | identical | **EXACT** |
| `dvopt/load691/h_cl_d165_L4_W30` | **real-load level t_valid90** | **115.467185 ps** | **115.467185 ps** | **EXACT** |
| | VBEND / VBPK | 0.754572966 / 1.0881874 | identical | **EXACT** |
| | VA_open | 0.11745601600934541 | 0.117454442 | NEAR (1.3 × 10⁻⁵ rel; interpolation grid) |
| `chain3/c_f45` **(the FAILING peer chain)** | VR1K1 / VR2K2 / VR3K3 | 1.005949 / 0.5829686 / 0.4443892 | identical | **EXACT** |
| | VR1PK / VR2PK / VR3PK | 0.864047 / 0.6371363 / 0.4515553 | identical | **EXACT** |

The `chain3` row reproduces **248 of 256 `.mt0` keys bit-identically**; the 8 that differ
are last-printed-digit noise on integrator pedestals at the 10⁻²¹–10⁻³³ level. The
`load691` deck carries no `.measure` statements (that workflow extracted from the raw
`.prn`), so its anchor is reproduced from the `.prn` with `load691/post.py`'s own
conventions. **This also closes amendment A0**: the environment's `.so` builder logged one
`full build failed … retrying without zero-valued params`, and the digit-exact
reproduction proves the retry path changed nothing numerically.

---

## 2. What was built (brief step c)

Four banks, eight committed inverter cells each (32 cells), **nothing between banks**.
Full proof in `NETLIST_PROOF.txt`; the load-bearing lines:

```
VI1_0 in1_0 0 1.2                                       <- bank 1 ONLY: ideal source
XP1_0 o1_0 in1_0 rail1 rail1 sg13_lv_pmos w=1.12u l=0.13u
XN1_0 o1_0 in1_0 gn1   gn1   sg13_lv_nmos w=0.74u l=0.13u
CL1_0 o1_0 gn1 2f
XP2_0 o2_0 o1_0  rail2 rail2 sg13_lv_pmos w=1.12u l=0.13u   <- bank 2's gate input IS o1_0
XN2_0 o2_0 o1_0  gn2   gn2   sg13_lv_nmos w=0.74u l=0.13u
XP3_0 o3_0 o2_0  rail3 rail3 …      XP4_0 o4_0 o3_0 rail4 rail4 …
```

No flop, latch, buffer, keeper or level shifter appears anywhere in the file.
Each bank owns its tank, its inductor and its switch — **every line in the deck that
mentions `tnk1` is one of these plus metering**:

```
CT1  tnk1 0 359.79f                                  <- C_tank = m·C_bank = 10·35.979 fF
L1   tnk1 mid1 15n
R1   mid1 sw1 10
XSWN1 sw1 gt1  rail1 0    sg13_lv_nmos w=10u l=0.13u  <- committed tg15p, wn 10 u
XSWP1 sw1 gtp1 rail1 vhi  sg13_lv_pmos w=20u l=0.13u  <-                  wp 20 u
XPK1  sw1 pk1  tnk1  tnk1 sg13_lv_nmos w=2u  l=0.13u  <- park, TANK-referenced (A6)
```

The **return to that same tank** is the same transfer gate closing a second time, so the
rail is rung back down through the same `L1`:

```
VGT1  gt1  0 PWL(0 0 198p 0 200p 1.5 318.184p 1.5 320.184p 0
                       998p 0 1000p 1.5 1129.37p 1.5 1131.37p 0)
```

**Where the recharge comes from.** In the free-running rows: nowhere — the tanks are
pre-charged by `.ic` and never refilled, so the measured tank droop *is* the recharge
requirement. In the costed rows (§8) a real `tg15p`-class gate from a rail at the tank's
own operating voltage feeds each tank, metered at the supply.

Cells, switch, `L = 15 nH`, `RS = 10 Ω`, `VGH = 1.5 V`, 2 ps edges, 1 F-integrator
metering with t₀ reference, true-ZCS probe-then-cut, and the per-gate settling convention
are all `skip4`/`chain3`/`lsweep`/`swsweep`/`gateb` **verbatim**.

### Two harness defects found by measurement and fixed *before* the sweep

* **A6 — the park must be TANK-referenced.** My first design held the park off, arguing
  the tank pins `sw` through `L+R` at DC. Wrong: the inductor carries its *maximum*
  voltage exactly at the ZCS instant (`V(tnk) − V(rail) = 0.472 − 0.880 = −0.408 V`), so
  opening there left the island ringing at **≈7 GHz, ±700 µA, undamped for 350 ps**
  (`½LI² = 3.9 fJ`, the same order as the hop). Ground-referenced parking — the committed
  choice — would have dumped the tank through `L`. The park now closes an `L+R` **loop
  across the tank**: it clamps the inductor voltage to ≈0 and cannot drain anything.
  Every pre-fix deck is quarantined in `pre_A6/`.
* **A7 — ZCS zeros are beat-period dependent.** Reusing one zero set across the grid left
  `|I(L)| = 8.8 / 15.3 / 27.4 µA` on banks 2/3/4 at `T = 200` while bank 1 — the only bank
  with schedule-independent ideal inputs — stayed at 0.0076 µA. Probes are now
  schedule-matched; the decisive rows are re-run and read **IZ = −0.0076 / −0.0012 /
  −0.0031 / −0.0030 µA, IZQ ≤ 0.0059 µA, path identity closed to 10⁻⁴ fJ — A6 PASS.**
  (A7a records that my first "schedule-matched" implementation was a silent no-op, caught
  because its zeros came out *identical* at four different beat periods.)

---

## 3. THE HEADLINE — the earliest correct rail start, and the beat period

Pre-registered operating point: `m = 10`, `dV = 1.2`, `L = 15 nH`, free-running, `H = 4`.
Every row: per-gate settling at **all 8 gates of all 4 banks**, never aggregated, plus the
value check against the expected bit pattern.

| T (ps) | worst gate | value check | **PASS** | overlap ramp∩pred (ps) | concurrent L |
|---|---|---|---|---|---|
| 45 | 25.45 % | fail | ✗ | 118.26 | 3 |
| 60 | 25.04 % | fail | ✗ | 116.32 | 3 |
| 75 | 26.73 % | fail | ✗ | 116.32 | 2 |
| 90 | 29.22 % | fail | ✗ | 115.76 | 2 |
| 120 | 40.47 % | fail | ✗ | 115.76 | 2 |
| 160 | 72.21 % | fail | ✗ | 115.76 | 1 |
| 170 | 78.60 % | fail | ✗ | 115.76 | 1 |
| 180 | 83.36 % | fail | ✗ | 13.62 | 1 |
| 190 | 87.35 % | fail | ✗ | 2.60 | 1 |
| **200** | **90.54 %** | **pass** | **✓** | **0.00** | **1** |
| 220 | 95.12 % | pass | ✓ | 0.00 | 1 |
| 240 | 97.19 % | pass | ✓ | 0.00 | 1 |
| 300 | 98.38 % | pass | ✓ | 0.00 | 1 |

**EARLIEST CORRECT BEAT PERIOD = 200 ps** (190 ps fails at 87.35 %).

Expressed as the brief asks — as a **rail-start offset relative to the predecessor's
measured data-valid instant** — the earliest correct start is
**+13.62 ps (bank 2), +0.67 ps (bank 3), +0.24 ps (bank 4)**: *after*, not before.
In steady state the rail may begin rising **a quarter of a picosecond after** its
predecessor's data is valid, and not one picosecond sooner.

**The beat period measured DIRECTLY off the running chain** (amendment A3: the interval
between successive banks' measured data-valid instants, never composed from parts):
**212.95 / 200.43 / 190.71 ps** for banks 2−1, 3−2, 4−3 — converging to ≈191 ps, i.e. the
chain really does advance valid data one stage per beat.

### Against the two baselines the brief names

| baseline | value | this chain |
|---|---|---|
| committed peer chain (`chain3`, `skip4`) | **no achievable beat at any T from 60 to 300 ps**; 45 rows, zero passes at 90 %, 75 % *or* 50 %; best worst-gate anywhere 36.12 % | **200 ps, PASS at 90 %** |
| CMOS logic level, same convention | 94.174 ps | **2.124 × SLOWER** |
| committed QAL single-hop level | 123.443 ps | **1.620 × slower** |

So the honest summary of the speed axis: per-bank tanks turn *"no beat period exists"*
into *"a beat period exists, and it is 2.1 × the CMOS level."*

---

## 4. THE OVERLAP — proven the way the skip study disproved its own

Exhaustive scan over **every** (rail ramp) × (other bank's evaluation window) pair, using
both the schedule intervals and the **measured** resolving windows (rail start → that
bank's measured data-valid instant). The full dump is in each row's
`interval_scan_intersections_ps`.

**At `T = 200` — the earliest correct beat — the only non-zero intersections in the whole
scan are each ramp with its OWN bank's window:**

```
ramp1_x_eval_measured_to_valid1   118.184 ps
ramp2_x_eval_measured_to_valid2   118.760 ps
ramp3_x_eval_measured_to_valid3   117.170 ps
ramp4_x_eval_measured_to_valid4   117.267 ps
                                  (…and nothing else at all)
ramp_k ∩ eval_j for every k ≠ j = 0.000 ps
```

Contrast `T = 120`, which **does** overlap — and does not compute (40.47 %):

```
ramp2_x_eval_measured_to_valid1    53.932 ps
ramp3_x_eval_measured_to_valid2    60.975 ps
ramp4_x_eval_measured_to_valid3   115.759 ps
return1_x_eval_measured_to_valid3  81.326 ps
return1_x_eval_measured_to_valid4 107.076 ps
```

**The overlap column and the PASS column are anti-correlated over the whole sweep**:
115.76 → 13.62 → 2.60 → **0.00 ps** across `T` = 170/180/190/**200**, and the chain flips
from failing to passing at exactly the point where the overlap reaches zero.

**★ MAXIMUM OVERLAP ON ANY PASSING ROW, ACROSS ALL 70 ROWS — every `m`, every `H`, both
swings, free and costed: 0.000 ps.** My pre-registered prediction **P4** ("real overlap
exists, > 20 ps at the earliest correct T") is **REFUTED by its own instrument**, in the
same way and by the same test that refuted the stage-skipping study's concurrency claim.
The claim is withdrawn.

**Why, mechanically.** Cutting the serial *charge* dependency is real and it is exactly
what the tanks do. But the binding serial dependency was never the charge — it is the
**data**: a settling gate cannot produce a correct output before its input is correct, and
the input is the predecessor's output. A bank whose rail is raised early merely settles to
the stale value and then has to re-settle, and the re-settle is what sets the beat.

---

## 5. Correctness at the passing point — per gate, never aggregated

`m = 10, T = 200, H = 4, dV = 1.2`, schedule-matched zeros, instrument clean.

```
per-gate settling (%) at each bank's OWN boundary, all 8 cells:
  bank 1:  98.9  98.9  98.9  94.7  98.9  94.7  94.7  98.9
  bank 2:  91.2  91.2  91.2  99.3  91.2  99.3  99.3  91.2
  bank 3:  94.2  94.2  94.2  90.5  94.2  90.5  90.5  94.2
  bank 4:  92.7  92.7  92.7 100.6  92.7 100.6 100.6  92.7      -> min 90.5 %

value check vs the expected pattern (pull-down ≤ 0.10·rail, pull-up ≥ 0.50·rail):
  bank 1 expected 00010110   guard ........
  bank 2 expected 11101001   guard ........
  bank 3 expected 00010110   guard ........
  bank 4 expected 11101001   guard ........      -> 32 / 32 correct

gate drive vs Vt (the guard that caught skip4's non-computing banks):
  bank 2  min nMOS overdrive +0.2338 V     bank 3  +0.1526 V     bank 4  +0.2000 V
```

The pull-down transistors are genuinely **on** at every stage — this is computation, not
an undisturbed node. **Stated limit, inherited from the committed fixture**: 8 identical
inverters with identical loads give only **two electrically distinct classes per bank**, so
"per gate, never aggregated" yields two numbers per stage and cannot catch a single-gate
outlier. The guard that does the work here is the 8-bit **pattern** check, which is why
the pre-registration replaced the committed alternating input with
`P = [1,1,1,0,1,0,0,1]`.

---

## 6. FADE — eliminated, and this is the strongest result in the study

HIGH/LOW separation `min(HIGH) − max(LOW)` at each bank's own boundary, against the
**corrected 6.44 mV 1σ floor** (`vtaudit/AUDIT.md`; *not* 3.42 mV):

| bank | rail at own boundary | min(HIGH) | max(LOW) | **separation** | × the 6.44 mV floor |
|---|---|---|---|---|---|
| 1 | 0.7544 V | 0.7145 | +0.0080 | **706.56 mV** | 110 × |
| 2 | 0.6767 V | 0.6169 | +0.0045 | **612.38 mV** | 95 × |
| 3 | 0.7312 V | 0.6621 | +0.0426 | **619.51 mV** | 96 × |
| 4 | 0.7201 V | 0.6672 | −0.0042 | **671.43 mV** | 104 × |

**There is no depth dependence at all.** Bank 4's separation is *larger* than bank 2's and
bank 3's; the rail spread across all four banks is 77.7 mV with bank 4 only 34 mV below
bank 1, and that spread is a fixed odd/even pattern-loading difference, not a decline.

Against the committed peer chain measured on the identical cells: rails
**1.005949 / 0.582969 / 0.444389 V**, a **0.61–0.66× collapse per hop**, with bank-3
separation **negative (−6 to −15 mV) at every L**. Per-bank tanks remove that mechanism by
construction — no charge is ever taken from a bank to power its successor — and the
measurement confirms it. **Pre-registered prediction P2's depth clause: CONFIRMED.**
(P2's *monotonic-in-m* clause was already refuted before the sweep — see A4 and §7.)

---

## 7. THE TRADE CURVE (brief steps e, f) — the deliverable

### 7a. Concurrent inductors vs overlap vs beat period (`m = 10`, `dV = 1.2`, `H = 4`)

| T (ps) | overlap ramp∩pred (ps) | **concurrent inductors** (schedule) | ramps only | waveform > 1 µA | PASS |
|---|---|---|---|---|---|
| 45 | 118.26 | **3** | 3 | 4 | ✗ |
| 60 | 116.32 | **3** | 2 | 4 | ✗ |
| 75 | 116.32 | **2** | 2 | 4 | ✗ |
| 90 | 115.76 | **2** | 2 | 4 | ✗ |
| 120 | 115.76 | **2** | 1 | 3 | ✗ |
| 160–170 | 115.76 | **1** | 1 | 2–3 | ✗ |
| 180 | 13.62 | **1** | 1 | 2 | ✗ |
| 190 | 2.60 | **1** | 1 | 2 | ✗ |
| **200 → 300** | **0.00** | **1** | 1 | 2 | **✓** |

The schedule-exact count is the maximum number of transfer switches conducting at once,
computed from the deck's own phases and the measured zeros. The waveform column counts
`|I(L)| > 1 µA` simultaneously and is one higher because the tank-referenced park leaves a
decaying `τ = L/(R+R_on) ≈ 250 ps` tail in the parked loop — that is the park doing its
job, not a second active transfer.

**This is the answer to the question the brief said was the deliverable.** The relationship
"degree of overlap → number of simultaneously active inductors" is real and it is
`N_L = ⌈t_hop / T⌉` with a measured `t_hop ≈ 116–118 ps` — but **the beat period each
level of overlap buys is worse, not better**. Overlap is available only at `T < t_hop`, and
at every such `T` the chain does not compute. **No correct operating point in this study
requires more than one inductor at a time**, which means the `σ0` architecture's
one-shared-switched-inductor assumption survives intact; per-bank tanks do not force the
scarce component to multiply. That is the one genuinely good piece of news on the cost
axis, and it arrives for the disappointing reason that the concurrency was never usable.

### 7b. Area: tank size vs earliest correct beat (`dV = 1.2`, `H = 4`, PDK MIM 1.5 fF/µm²)

| m | C_tank | **tank area / bank** | tank area / 4-bank chain | measured t_hop | **earliest correct T** | highest failing T |
|---|---|---|---|---|---|---|
| 1 | 35.98 fF | **23.99 µm²** | 95.94 µm² | 69.9 ps | **240 ps** | 230 (89.74 %) |
| 2 | 71.96 fF | **47.97 µm²** | 191.89 µm² | 82.6 ps | **400 ps** | 360 (89.04 %) |
| 5 | 179.90 fF | **119.93 µm²** | 479.72 µm² | 104.7 ps | **260 ps** | 240 (89.44 %) |
| 10 | 359.79 fF | **239.86 µm²** | 959.44 µm² | 117.1 ps | **200 ps** | 190 (87.35 %) |
| 20 | 719.58 fF | **479.72 µm²** | 1918.88 µm² | 126.0 ps | **200 ps** | 190 (89.38 %) |

`cap_carea = 1.5 × 10⁻¹⁵ F/µm²`, read out of the PDK
(`ihp-sg13g2/libs.tech/xyce/models/cornerCAP.lib`).

**The area/speed trade is real, weak, and non-monotonic.** Twenty times the tank area buys
**240 → 200 ps, i.e. 17 %** — and it saturates: `m = 20` is no faster than `m = 10` while
costing twice the area. `m = 2` is the **worst** point in the whole sweep (400 ps), worse
than a tank one-half its size. Two mechanisms fight, both measured here:

* a stiffer tank delivers a higher rail (0.734 → 0.791 V at the ZCS instant from
  `m` = 1 → 20) and a higher rail settles faster;
* **but a bigger tank lengthens the LC ramp**: `t_hop` rises `69.9 → 126.0 ps`, i.e.
  `×1.80`, against the lossless-linear `√(2m/(m+1)) = ×1.38` — the excess is the nonlinear
  gate load, consistent with this campaign's standing finding that `π√(LC)` reads early.

The `m = 2` pathology is the pre-registered pre-charge rule showing through: `V_t0 =
dV(m+1)/2m` drops 1.2 → 0.9 V from `m` = 1 → 2 faster than two banks' worth of stiffness
repays. **This is a confound, by pre-registered construction — the m sweep moves tank SIZE
and tank PRE-CHARGE together — and it was separated by measurement, not argument:**

### 7c. The control that separates size from swing

| configuration | delivered rail | earliest correct T |
|---|---|---|
| `m = 10`, pre-registered pre-charge `V_t0 = 0.66 V` | 0.68–0.75 V | **200 ps** |
| `m = 10`, **`V_t0` held at the full `dV` = 1.2 V** (`vfull` control) | 1.29–1.45 V | **140 ps** |
| `m = 10`, `dV = 1.65` (the PDK cross-check) | 0.95–1.08 V | **150 ps** |

**The beat period tracks the DELIVERED RAIL, not the tank size.** That is the same
conclusion this campaign's own schedule-free `cellfloor` control reached from the other
direction (`t90` = 38.4 ps @ 1.2 V, 111.2 ps @ 0.714 V, 164.3 ps @ 0.644 V on an ideal
stiff rail). **The `vfull` 140 ps must not be quoted as a speed result**: it delivers a
1.45 V rail, so it is a *1.45 V swing* number, not iso-swing with the 94.174 ps CMOS
comparator. The legitimate in-envelope cross-check is `dV = 1.65 → 150 ps`, still
**1.59 × the CMOS level**.

### 7d. Hold depth, and the throughput number that actually matters

A bank is occupied for `H` beats (rise → hold → return), so an unreplicated pipeline's
**initiation interval is `H·T`, not `T`** — pre-stated, and it is the number a throughput
claim must use.

| H | earliest correct T | **initiation interval `H·T`** | concurrent L |
|---|---|---|---|
| 2 | 250 ps (240 fails at 89.85 %) | **500 ps** | 2 |
| 3 | 200 ps | 600 ps | 2 |
| 4 | 200 ps | 800 ps | 1 |

**`H` = 2 — the minimum hold — gives the best throughput**, 500 ps per item, despite the
longer beat. Two pre-registered predictions die here:

* **P6 is REFUTED in both directions.** I predicted `H` = 2 would pass at short `T` and
  fail at long `T`. It fails at *short* `T` (the schedule becomes infeasible below
  `H·T < t_hop + 2·edge` — at `T` = 60, `H` = 2 the return would have to close before the
  rise has opened, and the deck will not build) and **passes at long `T`**.
* My pre-sweep worry that the hold must be **depth-proportional** (bank 1 held until bank
  4 lands, or the corruption released by an early return propagates forward through the
  unlatched chain) is **refuted by measurement**: at `H` = 2, bank 1 returns at 720 ps
  while bank 4's boundary is at 1238 ps, and bank 4 still reads 92.95 % with 639.55 mV of
  separation. The corruption loses the race — a drain plus a gate delay is slower than the
  remaining boundary margin. **Honest limit: this is a 4-bank result. The race margin is
  not measured as a function of depth and must not be extrapolated.**

---

## 8. ENERGY (brief step g) — reported, and **not** a gate

Per bank per beat, `dV = 1.2`, `H = 4`, at each `m`'s comparable beat (`T = 240`); all
from 1 F integrators with t₀ reference, path identity closed to `10⁻⁴…10⁻³ fJ`:

| m | into rail (rise) | **back into tank (return)** | **recycle** | tank net loss / cycle | switch block | series R |
|---|---|---|---|---|---|---|
| 1 | 22.33 fJ | 0.85 fJ | **3.8 %** | **19.99 fJ** | 1.54 fJ | ≈0.3 fJ |
| 2 | 23.49 fJ | 1.52 fJ | **6.5 %** | **19.36 fJ** | 1.51 fJ | |
| 5 | 28.51 fJ | 3.02 fJ | **10.6 %** | **21.60 fJ** | 1.91 fJ | |
| 10 | 33.04 fJ | 4.57 fJ | **13.8 %** | **23.82 fJ** | 2.34 fJ | 0.38–0.51 fJ |
| 20 | 36.70 fJ | 5.91 fJ | **16.1 %** | **25.62 fJ** | 2.70 fJ | |

* **Energy per hop RISES with `m`** (19.4 → 25.6 fJ, +32 %). **Pre-registered P7:
  CONFIRMED** — the area/speed trade is also an area/**energy** trade.
* **Local recycling recovers only 3.8–16.1 % of what it delivers.** The recycle fraction
  improves with tank size but the absolute cost still rises, because a stiffer tank pushes
  *more* charge into the rail and the gates burn most of it. **Local recycling does NOT
  preserve adiabatic behaviour at this operating point** — consistent with this campaign's
  own finding that a settling gate dissipates resistively through its own `R_on` and only
  the rail is recoverable.
* The tank net loss is computed **convention-free** from `½·C_tank·(V₀² − V₁²)` on a known
  linear capacitor, not from an integrator.

### The tank recharge, COSTED (not booked)

`m = 10`, `T = 200`, `H = 4`, `mode = topup`: a real `tg15p`-class transmission gate from a
rail at the tank's own 0.66 V into each tank, 60 ps after that tank's return completes,
supply current metered.

| quantity | value | how |
|---|---|---|
| charge delivered, 4 banks | 121.587 fC | 1 F integrator on the supply |
| **energy drawn from the recharge rail** | **80.247 fJ = 20.06 fJ / bank / beat** | integrator |
| the same number, **integrator-free** | **80.247 fJ** | `Q × V_rail`, agreeing to 6 digits |
| energy actually stored in the tanks | 69.351 fJ | `½C(V² − V²)`, linear caps |
| **lost in the recharge switch** | **10.896 fJ (13.6 %)** | difference of the two above |
| does the top-up restore the tank? | **no** — 0.660 → 0.639 V | measured |
| **DERIVED** full-restore requirement | **≈ 26.8 fJ / bank / beat** | 23.15 fJ stored ÷ 86.4 % switch efficiency |

The costed row also **passes** (91.69 %, 626.30 mV separation), slightly better than
free-running, so the recharge is not bought at the cost of function.

**What remains a BOUND, labelled as such**

* The 0.66 V recharge rail is itself an ideal source. **Generating it is NOT costed here.**
  The `20.06 fJ` is therefore a LOWER BOUND on the recharge, not a closed result.
* The `m = 1` and `m = 20` costed rows are **reported as instrument-flawed and their
  efficiencies withheld**: `m` = 1 ends with tanks at 1.31–1.38 V *above* its own 1.2 V
  recharge rail, and `m` = 20 computes a **102.4 % switch efficiency**. A recharge cannot
  be more than 100 % efficient, so by this study's own rule that is a defect, not a
  finding — the post-return window I integrate over also catches the parked-loop tail. Only
  the `m` = 10 row, where the two independent routes agree to six digits, is quoted.
* **Switch gate drive is an ideal-PWL BOOKING and is not reported as a cost.** The
  campaign's committed conventional-driver floor is **15.0–15.5 fJ per driver**, against
  which its own sub-harmonic resonant park tap measures 0.34–1.32 fJ. At 15 fJ per driver,
  gate drive would *dominate* the 20–27 fJ recharge — which is why it is flagged rather
  than folded in.
* **A8**: the recharge energy integrator was initially reading ≈0 because `V(vtk)` shared a
  name with the source `VTK`; found by cross-checking against the charge integrator, fixed
  by renaming the node, and the affected rows re-run. Both routes now agree.

---

## 9. Scorecard against the pre-registration

| | prediction | outcome |
|---|---|---|
| **P1** | A1+A2 pass at every gate of every bank at some point | **CONFIRMED** — 200 ps, 90.54 %, 32/32 values correct. The first such pass in the campaign. |
| **P2** | rail rises monotonically with m; **no depth dependence** | depth clause **CONFIRMED** (spread 77.7 mV, no decline); monotonic clause **REFUTED before the sweep** (A4: 0.734 / 0.707 / 0.766 / 0.791 V for m = 1/2/10/20). |
| **P3** | earliest correct beat 60–110 ps, most likely 75 ps | **BADLY WRONG. 200 ps** — 2.7 × my stated single most likely value, and 2.12 × the CMOS level rather than below it. |
| **P4** | real overlap exists, > 20 ps at the earliest correct T | **REFUTED by the interval scan.** 0.000 ps on all 32 passing rows of 70. Claim withdrawn. |
| **P5** | 2 concurrent inductors at the earliest correct T | **REFUTED — 1.** Right that ⌈t_hop/T⌉ governs; wrong that a correct beat would ever land inside it. |
| **P6** | H = 2 passes at short T, fails at T = 300 | **REFUTED in both directions.** H = 2 fails at short T (schedule infeasible) and passes at 250–300 ps, giving the best initiation interval, 500 ps. |
| **P7** | energy per hop rises with m | **CONFIRMED** — 19.4 → 25.6 fJ. |

---

## 10. Limits, stated here and not after

* **Shallow stack only.** Every number is an inverter number. The ALU's dominant mapped
  cell `sg13g2_o21ai_1` never settles at any operating point in the PDK envelope. Nothing
  here is generalised to it.
* `sg13lv_compat.sp` **zeroes `ad/as/pd/ps`** — junction capacitance is absent, so every
  time is optimistic and every charge a lower bound. It cuts both ways: the missing drain
  junction cap is part of what would hold a collapsing HIGH up *and* part of what would
  slow a creeping LOW.
* **Bank 1 is an ideal-source head** and its stage is optimistic by construction; bank 4 is
  the representative one and the comparisons are drawn there.
* **Depth 4 only.** The `H` = 2 corruption race and the flat-fade result are measured at
  four banks. The fade mechanism is structural (no bank is ever drained to power another)
  and should hold at depth; the race margin is a timing quantity and should not be
  extrapolated without measuring it.
* **Two electrical classes per bank** in the committed fixture; the 8-bit pattern check,
  not the per-gate spread, is what catches a non-computing bank here.
* The `vfull` 140 ps row is a **1.45 V swing** result and is not iso-swing with the CMOS
  comparator.
* The tank-recharge rail and the switch gate drivers remain ideal sources — **BOUNDS**.

---

## 11. What this means for the architecture

The proposal is **right about the mechanism it names and wrong about the consequence it
expects.** Giving each bank its own tank does exactly what it promises to the charge path:
it cuts the serial charge dependency, removes rail depth, removes compounding fade, and —
for the first time in this campaign — lets an unbuffered chain of real gate banks actually
compute, with 95–110 × the σ margin at every depth. That is a genuine and load-bearing
result: it identifies **the forward charge transfer, not the schedule and not the device
thresholds, as the thing that was killing the unbuffered chain.**

But "so the following stage can start sooner" does not survive its own interval scan. The
serial dependency that sets the beat is the **data**, not the charge, and no amount of
local energy storage shortens it. The rail may start **+0.24 ps** after the predecessor is
valid; every configuration where it starts earlier is measurably wrong. The price is
239.86 µm² of MIM per bank for a 17 % beat improvement that saturates at `m` = 10,
20–27 fJ per bank per beat of recharge that only 3.8–16.1 % of the delivered energy offsets,
and a pipeline initiation interval of 500 ps. The one thing the architecture does **not**
have to pay is more inductors: the correct operating points need exactly one active at a
time, so the `σ0` shared-switched-inductor assumption stands.
