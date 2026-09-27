# recov/ — the gate-charge RECOVERY measurement (M1 resonant / M2 stepwise / M3 lower VGH)

> **SUPERSEDED VERDICT — read this first (2026-09-27, report round).** §(e) below concludes
> **ADMITTED at 5.273 fJ / 87.87 % / N_min 54.0**. That conclusion **does not stand**. The
> skeptic audit in `skeptic/` (`SKEPTIC_RESULTS.json`) reproduced every number in this file
> (G0 to the digit, G1a 129/129 bit-identical, G1b worst 1.4e−8) and then **measured the one
> thing this round booked from an ideal source: the park pulse driver.** Its floor is
> **15.0–15.5 fJ** (one minimum sg13g2_inv_1, zero junction cap, free ideal input, no delay
> chain) against a **9.77 fJ headroom**. Complete measured ledger = **17.911 fJ/bank/hop,
> η 58.81 %, N_min 69.22 → fpu min-bank-63 EXCLUDED.** Even the campaign's own cheapest
> per-stage figure (FO1 6.316 fJ @1.2 V → 9.87 fJ @1.5 V) gives E = 12.843 fJ, N_min 63.12,
> still past the line. **What survives:** the resonant **gt/gtp pair** itself — 2.974 fJ net,
> ledger closed to 1e−12, re-metered by a trapezoid path that never touches the 1F
> instrument (0.19 %), transfer intact (EA_C −0.22 %), **all five gates PASS at the
> pre-registered checkpoint** tD = 811.755 ps (which this round did not evaluate — it used
> 556.8 ps; immaterial, but a procedural breach). **η ≥ 71 % was cleared; E ≤ 12.7467 fJ was
> not.** Those were only ever the same criterion by the assumption that a driver costs what
> the gate charge it delivers costs — the campaign's own as-built ratio is 7.0×
> (302.8 fJ of driver for 43.5 fJ of load charge). See `skeptic/` for the full audit.

The one number that decides QAL's admission at SG13G2. Pre-registered acceptance in
`PRE_REGISTERED.json`, written **before** the first recovery deck existed — at the
moment it was written it was the **only file in this directory**:

```
drwxrwxr-x  2 claude claude  4096 2026-09-27 14:45:14 .
-rw-rw-r--  1 claude claude 10282 2026-09-27 14:45:14 PRE_REGISTERED.json
--- files in dir: 1
```

`rv.py` (harness), `drives.py` (candidate networks), `screen.py`, `go.py`, `cutorder.py`,
`assemble.py` and every `*.cir` are all **later** mtimes. Machine-readable results:
`RESULTS.json` (assembled + verdict), `RESULTS_RECOV.json` (per-row), `RESULTS_SCREEN.json`
(device screen).

Every hop deck is a **TEXT PATCH** of the committed `swsweep/sw_tg15p_z.cir` (gate G3):
the only removed lines are `VGT`/`VGTP`/`VPK` and the three drive-integrator B-sources that
reference them; the only additions are the candidate drive network, its integrators and
`.print` columns. The patch script prints the removed lines on every stage.

## The handed-down threshold, and the arithmetic I reconstructed for it

`N_min = (39.6 + E)/(0.867 − 0.0361)`; the fpu `min-bank-63` block admits iff
`N_min ≤ 63`, i.e. **E ≤ 63·0.8309 − 39.6 = 12.747 fJ/bank/hop** — the handed-down
12.75 fJ, confirmed to three digits. Against the pre-stated conventional reference
`CV² = 29.0 fC × 1.5 V = 43.481 fJ` that is **η ≥ 70.7 %** with zero shared overhead and
**η ≥ 73.9 %** with 1.40 fJ/bank of shared overhead (B ≥ 8) — the handed-down 71–74 %.
The rider reproduces **exactly** if the switch must scale per gate: a 63-gate bank needs
63/8 = 7.875× the tg15p switch (which meters 8 cells), so `CV² = 342.6 fJ` and
`(1−η)·342.6 ≤ 11.35` → **η ≥ 96.69 %**. That reconstruction is mine, not handed down.

**η is quoted against the PRE-STATED 43.481 fJ so the threshold is not moved.** The
rectified charge integral measures the charge a real driver actually moves per hop as
**35.5 fC (53.27 fJ conventional)** — 22 % more than the 29.0 fC one-way figure, because
Miller re-supply *while the switch conducts* is real charge the one-way number omits.
Using 53.27 would raise every η, so 43.481 is the conservative choice. **No verdict
depends on the denominator**: `N_min` is computed from `E_drive` directly.

## (a) Instrument checks

| gate | result |
|---|---|
| **G0** postprocessing vs the committed `sw_tg15p_z.cir.mt0` | **PASS to the digit**: E_hop_open 8.382817177 (committed 8.3828171771408, Δ = +0.00e+00 %), cells_burn 1.69547461 (Δ −2.2e−14 %), VBEND 0.6758936, VBPK 0.7374377, E_R_toC 0.04954303486, VA_open_from_QLT 0.09778203952, IPK 194.3655 µA — **all exact**. Trap found and fixed in my own code first: every 1F integrator carries a DC-op residual (V = I_dc·0.01; V(xea) starts at 908.37 fJ because the `.ic` puts 90.8 nA through L at DC), so the Z checkpoint **must** be subtracted. |
| **G1** byte-identical re-run of the committed deck, my own `PYMS_VAE_CACHE` | **PASS**: 125/129 `.measure` values bit-identical; the 4 differences are the ~−5 nV settled cell outputs at 1e−15 V absolute (2e−7 relative). |
| **G2** committed real-drive timer row (`tl_hop` v2, N=7, CTRIM=25 fF, 27 C) | **PASS to the digit** (807 s; the stdcell library forces one PyMS `.so` per geometry): E_hop_open **8.10914** (−0.000 %), VBEND **0.684632** (+0.000 %), VA_open 0.107822, cells_burn 1.92709, **E_timer_D 399.842** (−0.000 %), **taps gt 118.041 + gtp 109.797 + pk 75.0045 = 302.8**, **line 97.0001**, **trigger 5.41006**, width 269.842 ps, gt edge 30.5382 ps — every one of the 12 checked metrics inside its tolerance |
| **control** ideal PWL at close = 50 ps and 100 ps | E_hop 8.3927 / 8.3927, VBEND 0.67543 / 0.67543, ideal floor 3.573 / 3.522 fJ — **the 50→100 ps close shift used by every slow-edge row is immaterial** |

Digit-checked anchors reproduced from the committed `.mt0`: **Q_gt(close) 10.4982 fC**
(brief 10.50), **Q_gtp(open) 16.3786 fC** (brief 16.38), **ideal-PWL floor EGT_D−EGT_Z =
3.5627 fJ** (brief 3.56).

### The ceiling nobody can beat (pre-registered P2)

The ideal-PWL floor is **3.52–3.56 fJ** of genuinely exported energy per gate cycle, so
**η_max = 1 − 3.52/43.481 = 91.9 %** for *any* drive mechanism at VGH = 1.5 V. The
71–74 % bar is inside that window; the **96.7 % rider is not**. Under the rider the
floor alone is 7.875 × 3.52 = 27.7 fJ against an 11.35 fJ allowance — so the rider is
refuted by the switch's own gate dissipation, *independently of mechanism*. **P2 CONFIRMED.**

## Device screen — the constant both recursions hinge on

`Ron·W` and `Cgate/W` are size-invariant over 0.74–10 µm (measured), so τ = Ron·Cgate is
a single device constant:

| | Ron·W (Ω·µm) | Cgate/W (fF/µm) | τ (ps) |
|---|---|---|---|
| nMOS | 554 | 1.520 | 0.84 |
| pMOS | 1792 | 1.993 | 3.57 |
| **1:2 CMOS TG** | **342 (at wn = 1 µm)** | **5.505 (per wn µm)** | **1.884** |

Pre-registered estimate was τ ≈ 3 ps; **measured 1.884 ps** — i.e. the recursion is
*cheaper* than I assumed, which makes M2/M1-C's failure a stronger result, not a weaker one.
(Cross-check: the 5 µm nMOS screen gives Cgate 7.672 fF vs the brief's 7.7 fF. The 10 µm
pMOS gives 20.1 fF quasi-static vs the brief's nominal 15.4 fF and the hop-measured
16.379 fC/1.5 V = 10.9 fF effective — three conditions, three numbers; the **hop-measured
charge is the one in the ledger**.)

## (b) M3 — lower VGH: P1 CONFIRMED, admits nothing

| VGH | Q_total (fC) | CV²_conv (fJ) | VBEND | VA_open | E_hop | verdict |
|---|---|---|---|---|---|---|
| 1.50 | 35.52 | 53.27 | 0.67543 ✓ | 0.0961 ✓ | 8.393 ✓ | complete |
| 1.35 | 33.12 | 44.71 | 0.66708 ✓ | 0.1011 ✓ | 8.579 **✗ (+5.8 %)** | E_hop out of band |
| 1.20 | 30.87 | 37.05 | 0.64363 **✗** | 0.1267 ✓ | 9.035 ✗ | broken |
| 1.05 | 28.41 | 29.84 | 0.61523 **✗** | 0.1749 **✗** | 9.429 ✗ | broken |

CV² scales as V^1.86 (measured), so reaching 12.747 fJ by voltage alone needs VGH ≈ 0.81 V
— but VBEND leaves its band already at **1.20 V** and E_hop leaves ±5 % at **1.35 V**. The
lowest completeness-passing row is still **37–45 fJ**, i.e. N_min 89–100. **M3 alone admits
nothing**; its honest role is a ×0.84 multiplier bought for a +5.8 % E_hop penalty on the
same ledger — close to free-standing zero.

## (c) M2 — stepwise capacitive charging: P3 CONFIRMED, fails and fails worse with n

Measured with the step-switch gate drives charged **conventionally** (rectified integral
`∫|I|dt/2 × V`, so the count is automatic however many pulses a control makes), tanks at
2 pF with their **stored-energy deficit booked as cost**:

| n | t_step | E_drive | rails | tank deficit | **step-switch gates** | park | η | N_min |
|---|---|---|---|---|---|---|---|---|
| 2 | 66.5 ps | **121.98 fJ** | +60.11 | +2.45 | **56.99** | 2.42 | **−180.5 %** | 194.5 |
| 4 | 33.2 ps | **183.36 fJ** | +71.96 | +3.93 | **105.09** | 2.39 | **−321.7 %** | 268.3 |

`residual/CV² = 1/n + 2ατn²/T_edge`: the saving saturates as 1−1/n while the recursion
grows as **n²** (count n, *and* size n, because t_step = T_edge/n forces W ∝ n). With the
measured τ = 1.884 ps and T_edge ≤ 133 ps the optimum is n ≈ 2. **Analytic best case**
(minimum-width 0.15/0.30 µm step switches, ideal tanks, no hold-switch Miller traffic —
strictly better than anything buildable): **E = 39.00 fJ, η = 10.3 %, N_min = 94.6**.
M2 is dead at SG13G2 by a factor of 3 even in its idealised form.

## (d) M1 — the resonant family: three distinct architectures, two verdicts

### M1-A — adiabatic (raised-cosine) edges, resonator ideal, **no aux hardware counted**

This is the **upper bound** on M1, not an architecture. First run put the cut at the 50 %
point and *every* row failed completeness — chased, not rationalised: a cosine edge crosses
the nMOS conduction threshold (~1.13 V for a 0.68 V bank) at f0 + 0.331·te, i.e.
**0.169·te before** the 50 % point, so the naive centring cuts **early** — the measured-bad
direction (interrupted forward current: VBEND −5.3 %, E_hop +9.4 %, matching the committed
mistiming map's −30.7 ps row). With `dcut = +0.169·te` every row passes:

| te (ps) | 20–80 % edge | E_drive | η | N_min | VBEND | VA_open | E_hop | order |
|---|---|---|---|---|---|---|---|---|
| 30 | 12.4/12.2 | 4.707 | 89.18 % | 53.3 | 0.67392 ✓ | 0.0978 ✓ | 8.416 ✓ | ✓ |
| 60 | 24.7/24.5 | 4.387 | 89.91 % | 52.9 | 0.67191 ✓ | 0.1021 ✓ | 8.440 ✓ | ✓ |
| 100 | 41.1/40.9 | 4.237 | 90.26 % | 52.8 | 0.66839 ✓ | 0.1116 ✓ | 8.474 ✓ | ✓ |
| 133 | 54.6/54.4 | **4.181** | **90.39 %** | **52.7** | 0.66496 ✓ | 0.1228 ✓ | 8.494 ✓ | ✓ |

**Slow edges are benign — but only when the cut instant is corrected for them.** That
refines the brief's convergence claim: at the real stdcell 30.5/16.3 ps the correction is
5 ps and invisible; at 133 ps it is 22 ps and costs 5 % of VBEND if ignored.

Measured loss law (te = 133, corrected cut), R = the total network series resistance
referred to one bank's tap: **`E_drive = 4.0759 + 5.5532e−3 · R[Ω]` fJ** — **0.79× the
linear-RC prediction** (2.468·R·C/te·CV² per node), lower because the MOS C(V) is nonlinear.
E ≤ 12.747 fJ on energy alone would allow **R ≤ 1561 Ω (Q ≈ 2.4)**.

**The required Q is set by the CUT ORDER, not by the energy.** The energy limit is
Q ≈ 2.4 — *not* the brief's ~11, because the brief's π/Q is quoted per ½CV² per transition
while this topology's coefficient is π/4 of that. But the gtp tap RC-lags the gt tap, so
large R makes the **pMOS cut late** — the v1 failure mode:

| R (Ω) | gtp − gt (ps) | order |
|---|---|---|
| 25 | +0.1 | PASS |
| 200 | +1.1 | PASS |
| 560 | +4.7 | PASS |
| 1000 | +9.8 | **FAIL** |

So **R ≤ 560–1000 Ω**. With the measured C_net = 22.61 fF/bank and the 534 ps beat that is a
lumped network **Q between 3.8 and 6.7** — where energy alone would have accepted Q ≈ 2.4.
So the brief's "Q ≳ 11" guess is within a factor of ~2 of the truth, but for a completely
different reason than the one it gave.

### M1-C — the same edges built as a **switched** resonator: FAIL (pre-registered P4)

A real CMOS freeze TG + 4 real clamps, all conventionally driven and counted:

| freeze TG | freeze gates | clamp gates | E_drive | η | N_min |
|---|---|---|---|---|---|
| 0.74/1.12 µm | 35.57 fJ | 18.24 fJ | **73.79 fJ** | **−69.7 %** | 136.5 |
| 5/10 µm | 301.2 fJ | 19.65 fJ | **389.73 fJ** | −796.3 % | 516.7 |

Cost scales linearly in W exactly as predicted. Analytic optimum from the measured
constants: freeze-cost × R is invariant at **18 546 fJ·Ω**, so R_opt = **1827 Ω** →
**E = 24.36 fJ, + min-width clamps = 28.06 fJ, η = 35.5 %, N_min = 81.4** — and R_opt
(Q ≈ 2.1) **exceeds the cut-order limit**, so the optimum is not even reachable; at the
560 Ω order limit E = 40.3 fJ.
**The freeze switch is a B-INVARIANT recursion**: its width must track the load it drives,
so its gate charge tracks too and the per-bank cost does not amortise over B. Switched
resonant is dead.

### M1-B / M1-D — the **free-running** network: no per-edge switch, hence no recursion

M1-B, plain 0→1.5 V anti-phase sines at the 534 ps beat: energy excellent (4.573 fJ,
η 89.5 %) and the 50 % window is a perfect 266.9 ps — but **completeness fails**
(VBEND 0.583, VA_open 0.158, cells FAIL). Chased to the mechanism from the waveforms: a
sine is only *above the nMOS conduction threshold* for 177 ps of the 267 ps needed, and —
the killer — its **quarter-period fall leaves the transfer nMOS still conducting when the
park pulls `sw` to 0**, so bank B drains to ground (V(bkb) 0.703 → 0.527 over 100 ps). A
threshold-centred sine widens the window but makes the drain worse (VA_open 0.307). A pure
sinusoid has one degree of freedom and three constraints; it is over-determined.

**M1-D — multi-harmonic resonant taps** (Σ_{k odd ≤ nh} sin kθ / k: flat top for the
window, fast edges for the park, still every component a resonance, still **no switch**):

| row | beat | E_drive | η | N_min | VBEND | VA_open | E_hop | cells | pMOS−nMOS | park−nMOS |
|---|---|---|---|---|---|---|---|---|---|---|
| nh=3 | 534 | 5.616 | 87.08 % | 54.4 | 0.66830 ✓ | 0.0843 ✓ | 7.151 ✗ | ✓ | +11.3 ✗ | +44.0 ✓ |
| nh=5 | 534 | 5.615 | 87.09 % | 54.4 | 0.66948 ✓ | 0.0663 ✓ | 8.609 ✗ | ✓ | +9.0 ✗ | +28.7 ✓ |
| nh=5, R=200 | 534 | 8.039 | 81.51 % | 57.3 | 0.66845 ✓ | 0.0683 ✓ | 8.629 ✗ | ✓ | +10.0 ✗ | +28.7 ✓ |
| **nh=5** | **580** | **5.306** | **87.80 %** | **54.0** | **0.68068 ✓** | **0.0965 ✓** | **8.200 ✓** | **✓** | +7.4 ✗ | +30.4 ✓ |
| nh=5, adv=12 ps | 580 | 5.087 | 88.30 % | 53.8 | 0.69188 ✗(+2.4 %) | 0.0922 ✓ | 7.940 ✓ | ✓ | **−0.9 ✓** | +33.2 ✓ |
| nh=5, adv=24 ps | 580 | 4.631 | 89.35 % | 53.2 | 0.70639 ✗ | 0.1142 ✓ | 7.457 ✗ | ✓ | −11.2 ✓ | +34.2 ✓ |
| **nh=5, adv=6 ps** | **580** | **5.273** | **87.87 %** | **54.0** | **0.68570 ✓** | **0.0916 ✓** | **8.098 ✓** | **✓** | **+3.2 ✓** | **+31.8 ✓** |
| **nh=5, adv=8 ps** | **580** | **5.225** | **87.98 %** | **53.9** | **0.68763 ✓** | **0.0902 ✓** | **8.056 ✓** | **✓** | **+1.9 ✓** | **+32.3 ✓** |

**The `adv = 6` and `adv = 8` rows pass ALL FIVE pre-registered gates** (VBEND band,
VA_open drain, E_hop ±5 %, cells settled, cut order). `adv = 6` delivers E_hop = 8.098 fJ
against the 8.109 fJ real-drive reference — **−0.14 %**, i.e. the transfer is untouched
while the drive cost falls from 399.8 fJ to 5.27 fJ.

The ordering rule needs a **phase-advanced gtp tap** (a second phase on the same network,
not a second network). VBEND is linear in the advance
(`0.68068 + 9.33e−4·adv`) and so is the ordering margin (`+7.4 − 0.775·adv`), so
**adv ∈ [3.1, 9.4] ps satisfies both** the pre-registered two-sided VBEND band and the
pMOS-cuts-early rule — the `adv = 6/8 ps` rows measure that directly.

The 580 ps beat (vs the campaign's 534 ps) is a **real, measured cost: 8.6 % slower**, and
it is what a sinusoidal-family waveform charges for spending beat time on its own edges.

Device-referenced cut order (the *last conducting instant*, not the first threshold
crossing — the committed design's pMOS overdrive dips mid-transfer as the bank fills,
which is not a cut) is in `cutorder.py`; the ideal-PWL control measures −0.1/+2.2 ps and
the te=133 adiabatic row −6.1/+28.9 ps, both PASS, which validates the detector.

### The architectural prize, quantified

With B banks on **one** network the shared series R is R/B while C is B·C_net, so
**Q = 1/(ω·C_net·R) is B-INVARIANT**: sharing buys a *realisable* inductance without making
Q harder. The measured loss law for the harmonic waveform is **`E_drive = 5.2688 + 1.385e−2 · R[Ω]`
fJ** — steeper than the raised-cosine law because harmonic content raises dv/dt hence I²R —
so E ≤ 12.747 fJ needs **R ≤ 540 Ω, i.e. lumped network Q ≥ 7.0**. The delivered rows sit
at R = 25 Ω (Q ≈ 150), so the margin is ~20×. Measured C_net = **22.61 fF/bank** (gt+gtp),
so at the 580 ps beat

| B | 1 | 8 | 16 | 64 | 256 |
|---|---|---|---|---|---|
| L₁ (nH) | 377 | 47.1 | 23.6 | 5.89 | 1.47 |

with L₃ = L₁/9 and L₅ = L₁/25 (0.65 / 0.24 nH at B = 64) — the harmonic inductors are the
easy ones. **Inventory: 3 resonant modes, 3–4 inductors TOTAL for the whole chip**, shared
by every bank — the same order the σ0 architecture already assumes for the rail, and it is
exactly what divides the per-bank tap cost by B. At B = 64 the network needs
L₁ = 5.9 nH with a **shared series R ≤ 8.4 Ω** for Q = 7 — an on-chip spiral at 1.7 GHz
typically reaches Q 8–15, so this is plausible but **ASSUMED, not measured here: the
inductor is ideal in every deck and its ESR is folded into the swept series R. No metal
inductor Q is measured by this deck.** A free-running network also needs a **sustaining
amplifier**; only the resonant part of the ledger (2.87 fJ of the 5.27 fJ; the park's
2.40 fJ is conventional) passes through it, so admission survives any sustaining
efficiency **above 27.7 %**.

**Reliability flag (measured, adverse):** the harmonic waveform runs gt to **+1.60 V** and
gtp to **−0.34 V**, i.e. a worst gate–bulk stress of −1.84 V on a 1.5 V-rated thin oxide
(+23 %). The offsets are what make the above-threshold window equal half the beat; shrinking
them shortens the window. This is an unpriced cost on the M1-D row.

### Where the surviving 5.27 fJ actually goes (same accounting, every row)

| row | E_gt | E_gtp | park (conventional) | total |
|---|---|---|---|---|
| ideal-PWL control (close 100) | **−3.000** | +3.867 | 2.396 | **3.263** |
| M1-A adiabatic te=133 R=25 | −2.008 | +3.797 | 2.391 | 4.181 |
| **M1-D harmonic 580 adv=6** | **−2.756** | **+5.626** | **2.403** | **5.273** |

`E_gt` is **negative in the ideal control too** — the gt drive is a net energy *receiver*,
because Miller coupling from the rising bank and the swinging `sw` node pumps charge back
into it while the gate is held high. That is a property of the topology, not of my waveform,
which is why the same sign appears in every row.

Under this accounting the **floor is 3.263 fJ (η_max 92.5 %)**, so the M1-D row's 5.273 fJ
sits 2.01 fJ above it: 0.35 fJ of that is the R loss at 25 Ω (from the measured slope) and
~1.66 fJ is the extra dissipation the harmonic waveform's larger, slower gate excursion
causes in the nonlinear MOS gate. **That 1.66 fJ is the real, measured price of going
switch-free** — and it is affordable.

**Park-accounting sensitivity (adverse direction):** I charge the park at `Q_pk·V` =
2.403 fJ, but its measured ideal-source export is 2.611 fJ (the park never discharges
inside the window, so no recovery is possible either way). Charging the larger figure gives
**E = 5.481 fJ, η = 87.4 %, N_min = 54.2** — no verdict changes.

## (e) VERDICT — **SUPERSEDED, see the banner at the top of this file**

Everything below is the round's own reading and is left verbatim for audit. The rows are
correct as *gate-node* numbers; the **ADMITTED** cells are wrong because the `E_timer`
column omits the park's driver. Corrected table (skeptic, measured):

| architecture | E_timer (fJ/bank/hop) | η | N_min | fpu min-bank-63 |
|---|---|---|---|---|
| M1-D resonant gt/gtp pair ALONE (this round's 5.273 minus the park booking) | 2.974 | — | — | not a complete ledger |
| M1-D + park at this round's ideal-source booking | 5.273 | 87.87 % | 54.0 | *claimed* ADMITTED — **omits the park driver** |
| M1-D + park at the deck's own energy integrator | 5.634 | 87.04 % | 54.4 | same omission |
| M1-D + park at the campaign's cheapest real stage (FO1 @1.5 V) | 12.843 | 70.5 % | 63.1 | **EXCLUDED** |
| **M1-D + park driver MEASURED (1 min inverter, slow input)** | **17.911** | **58.81 %** | **69.22** | **EXCLUDED** |
| M1-D + measured park + 50 %-efficient sustaining amp | 21.313 | 50.98 % | 73.31 | EXCLUDED |
| M1-D + measured park + amp + 1.5 V-referenced DC bias | 24.023 | 44.75 % | 76.57 | EXCLUDED |
| *if* a resonant park tap existed at ~1.5 fJ — **UNMEASURED, the open door** | 4.474 | 89.71 % | 53.04 | ADMITTED |

**Best achieved recovery on a row that passes every pre-registered gate: 87.9 %
(E_timer = 5.273 fJ/bank/hop, N_min = 54.0)**; 88.0 % / 5.225 fJ on its neighbour. That is
far above the pre-stated 71–74 % line and within 4 points of the 91.9 % ceiling the
switch's own gate dissipation imposes. But it is only achievable in **one** of the three
M1 architectures:

| architecture | E_timer (fJ/bank/hop) | η | N_min | fpu min-bank-63 |
|---|---|---|---|---|
| committed as-built stdcell tap (B=8) | 315.60 | −625.8 % | 427.5 | EXCLUDED |
| conventional CMOS tap, gate charge only | 43.481 | 0 % | 100.0 | EXCLUDED |
| M3 lowest completeness-passing VGH (1.35) | 44.710 | −2.8 % | 101.5 | EXCLUDED |
| M2 stepwise, measured best (n=2) | 121.976 | −180.5 % | 194.5 | EXCLUDED |
| M2 analytic best case (n=2, min width) | 38.995 | 10.3 % | 94.6 | EXCLUDED |
| M1-C switched resonant, measured | 73.789 | −69.7 % | 136.5 | EXCLUDED |
| M1-C analytic optimum | 28.062 | 35.5 % | 81.4 | EXCLUDED |
| **M1-D free-running harmonic, ALL 5 gates PASS** | **5.273 / 5.225** | **87.87 / 87.98 %** | **54.0 / 53.9** | **ADMITTED** |
| M1-A idealised bound (no aux counted) | 4.181 | 90.39 % | 52.7 | ADMITTED |
| ideal-PWL floor, all 3 taps ideal (unbeatable) | 3.522 | 91.90 % | 51.9 | ADMITTED |
| ideal-PWL floor, park charged conventionally | 3.263 | 92.50 % | 51.6 | ADMITTED |

At N_min ≈ 54: **fpu min-bank-63 ADMITTED**; **alu_top bush 29/37 levels = 99.6 % of gates**;
**sha_slice bush 4/10 levels = 87.6 % of gates** (its whole-block best min-bank is 7, so
sha_slice never admits whole at any E — that is a block-shape fact, not an energy fact).

**The two pre-stated bars give opposite answers, and that is the result:**

- Against the **base** threshold (12.747 fJ, switch sized as the committed tg15p — which
  meters 8 cells): **ADMITTED with 2.4× margin.** The mechanism is a *free-running*
  multi-harmonic resonant gate network — clock-like, shared by every bank, 3–4 inductors
  chip-wide, no per-edge switch anywhere.
- Against the **per-gate-scaling rider** (switch ×7.875 for a 63-gate bank → E ≤ 11.35 fJ
  of a 342.6 fJ reference, η ≥ 96.7 %): **EXCLUDED, and refuted for every mechanism** —
  the ideal-PWL floor alone scales to 27.7 fJ, so no drive scheme whatsoever can clear the
  rider at SG13G2. Whether the switch must in fact scale with bank gate count is an
  assumption of the rider that this deck does not test (no 63-gate bank was simulated).

**What would break it, in order of exposure:**
1. **Any per-edge switch.** A freeze/clamp is a B-invariant recursion: 35.5 % at its
   analytic best, −70 % as measured. The whole result depends on the network being
   *free-running*.
2. **The inductor Q** — needs **≥ 7.0** (energy) and ≥ 3.8–6.7 (cut order). ASSUMED, not
   measured. At B = 64 that is L₁ = 5.9 nH with shared series R ≤ 8.4 Ω.
3. **The sustaining amplifier** — needs ≥ 27.7 % efficiency.
4. **Gate over-stress**: −1.84 V gate–bulk on a 1.5 V oxide (+23 %), unpriced.
5. **The 8.6 % beat penalty** (580 vs 534 ps) that the harmonic waveform charges for its
   own edges.
6. **The park**, still conventional at 2.40 fJ = **46 % of the surviving 5.27 fJ**. It
   needs a pulse, not a sinusoid; no recovery was ever credited to it.
7. **The 63-gate bank was never simulated.** Every row meters the committed 8-cell bank.
