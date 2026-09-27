# timer/ — the tapped-line pulse-width timer, costed on the real tg15p hop

Q1 of the hybrid architecture ("pulse-width generator tuned occasionally on a
representative piece of logic, not ZCD everywhere") plus the N-spread half of Q3.
Pre-registered acceptance: `PRE_REGISTERED.json` (written before any timer deck ran).
This is the FIRST deck in the campaign where the switch gates are driven by transistors
instead of ideal PWL sources — the bookkeeping hole named in the brief.

All decks SG13G2/PSP103 tt via PyMS; the hop is a text patch of the committed
`swsweep/sw_tg15p_z.cir` (only the three ideal drive sources and their three integrator
expressions replaced — gate G2). Post-processing reproduced the committed tg15p_zcs row
to the digit before anything new ran (gate G0: E_hop_open 8.382817 fJ, cells 1.695475 fJ).

## Instrument checks (all MEASURED)

- **G1 line-vs-anchor**: 24-stage FO1 `sg13g2_inv_1` chain at 1.2 V: **42.67 ps/stage,
  6.32/6.42 fJ/stage-transition** vs the async_power_anchor 42–45 ps / ~6.3 fJ — PASS.
  Design point 1.5 V: **29.43 ps/stage, 9.9/10.1 fJ/stage-transition** (`tl_cal.json`).
- **Temperature plumbing** (three mechanisms tried, two REFUTED): `.OPTIONS DEVICE TEMP`
  never reaches the PyMS-compiled PSP103 (zeros at 0/27/85 C byte-identical; every cached
  .so carries TR=27). Model-card `dta=` is silently DROPPED (absent from the .so.params
  `__GIVEN__` list — Xyce registers DTA instance-level only). Instance `dta` WORKS
  (Id 321.7 → 305.0 uA at +58 K; `dta_test*.cir`). Corners therefore go through
  `sg13lv_dta.sp`, whose device default `dta={GDTA}` picks up a deck-level
  `.param GDTA` — and the shim must NOT define GDTA itself (a local `.param GDTA=0`
  shadows the deck's; measured).

## The timer (v2, `tl_hop.py`)

trigger →inv_1→inv_2→ s →[N × inv_1 line, CTRIM cap-DAC on two mid nodes]→ line_out;
g1 = nand2_1(s, line_out) (N odd); **gtp** = g1→inv_1→inv_4 (pMOS cut ~21 ps EARLY —
harmless, the nMOS carries the near-zero current); **gt** = g1→inv_1→inv_1→inv_2 (nMOS
cut LAST, tuned to the zero); **pk** = line_out→6×inv_1→inv_1 (lands ~36 ps after the
nMOS cut). Four metered rails: VTL line, VTG gt-tap, VTP gtp-tap, VTK park-tap.

v1 (single-NAND, inv_4/inv_8 drivers at fanout<1, nMOS-first cut) FAILED completeness:
the pMOS hung on 55 ps past the nMOS and the LC rang to −70 uA — un-transferring the
rail (VBEND 0.651) — and burned 508 fJ. Both defects are recorded in `tl_hop.json`.

## Q1 results (27 C, tuned row `tl_hop_v2_n7_c25`, both completeness gates PASS)

| | ideal-drive anchor (tg15p_zcs) | real drives (N=7, CTRIM=25 fF) |
|---|---|---|
| conduction window (gt 50%–50%) | 266.76 ps + 2 ps edges | 269.84 ps, edges 30.5/16.3 ps |
| I(L) at the cut | −0.38 uA | −15.0 uA at 50%-fall (7.7% IPK; ~0 at the 80% point where the nMOS actually stops) |
| VBEND / VBPK | 0.6759 / 0.7374 | 0.6846 (+1.3%) / 0.7774 |
| E_hop_open | 8.383 fJ | **8.109 fJ (−3.3%)** |
| cells burn | 1.695 fJ | 1.927 fJ |
| booked drive energy | 3.56 fJ (ideal-source artifact) | **399.8 fJ measured** |

- **The tg15p win survives real edges** (E_hop 8.11 vs the 10.69 fJ tg60 ring-robust
  anchor = −24%). Caveat, measured by elimination on the charge books: the real drives
  INJECT ~3.3 fC into bank B through the TG parasitics during transfer (through-L charge
  matches the ideal run: 32.05 vs 32.52 fC at the open; the cells' non-L charge does
  not), of which ~0.6 fC survives post-open — that is the +1.3% VBEND and part of the
  −3.3% E_hop. The subsidy's cost is booked in E_timer, so the books close.
- **THE TIMER COST (the previously uncosted hardware), stdcells at 1.5 V**:
  **E_timer = 399.8 fJ/hop = 302.8 per-bank taps (gt 118.0 + gtp 109.8 + pk 75.0)
  + 97.0 line + 5.4 trigger (shared by every bank on the chain)**. The ideal decks'
  3.56 fJ "drive energy" hid two orders of magnitude — ideal sources RECOVER CV² that
  real drivers dissipate. Floor arithmetic: the switch gates alone are
  (7.7+15.4+1.5) fF × 1.5 V² ≈ 55 fJ/hop/bank; the rest is stdcell tax (2 transitions
  per pulse gate, crowbar, internal parasitics) — real lever left: lower-VGH drive,
  smaller switch (tg7p5p halves the gate charge), starved/long-L line stages.
- **Admission** (N_min = (39.6+E_timer_per_bank)/(0.867−0.0361)): as built,
  B banks sharing one line: N_min = (39.6 + 302.8 + 102.4/B)/0.831 → **412 (B→∞) …
  535 (B=1) gates/bank — WORSE than the ZCD verdict's ≥221 at stdcell/1.5 V**. At the
  55+10 fJ tap floor it would be ~126. The hybrid beats ZCD on *mechanism* (no
  per-hop comparator, calibration amortizes) but NOT yet on measured per-bank energy.
- **Mistiming sensitivity WITH real edges** (same timer, different width): −30.7 ps
  early → VBEND −4.0%, E_hop +6.4%; +7.5 ps late → VBEND +2.4%, E_hop −5.7%;
  +65.7 ps late → VBEND −0.6%, E_hop −9.6%. Early stays the bad direction (interrupted
  forward current), late stays benign/cheap — consistent with the +50 ps ideal-edge row.
- **Park with real edges** (`b` deliverable): the all-off float window before the park
  grows 9→41 ps and the interrupted current builds −23.5→−102.5 uA, so the A-side ring
  doubles (V(bka) pk-pk 0.29→0.71 V, I(L) ring ±50→±120 uA); the park still clamps sw
  identically (−0.04..0.63 V) and the DELIVERED rail is quiet: V(bkb) ripple after park
  2.1 mV (vs 47 mV post-open excursion in the ideal run). Slow edges hurt the corpse of
  bank A, not the payload.
- **Calibration DAC**: CTRIM measured linear at ~2.06 ps/fF (10 fF → +20.6 ps,
  25 fF → +49.6 ps), stage granularity 2×29.4 ps; two SAR iterations landed 269.8 on a
  271.5 target. Achievable widths = odd stage-multiples only (both tap parities give
  odd-multiple windows — even parity needs the extra nd inverter).

## Replica tracking (c) — see `tl_probe.json`, `tl_cal.json`, `tl_hop.json` t85/t0 rows

The hop zero is LC-governed, the line RC-governed; the pre-registered expectation was
that the naive replica FAILS in magnitude across temperature — CONFIRMED:

| | 0 C | 27 C | 85 C |
|---|---|---|---|
| ideal-probe zero (ps) | 264.842 (−0.29%) | 265.623 | 267.578 (+0.74%) |
| loaded timer width, N=9 (ps) | 265.546 (−4.82%) | 278.996 | 307.537 (+10.23%) |
| FO1 line cal (ps/stage) | 28.006 (−4.85%) | 29.432 | 32.531 (+10.53%) |

**Tracking ratio ≈ 16.4 (cold) / 13.9 (hot)** — the line is a replica of gate RC, not of
the zero. The SIGN saves the architecture: heat lengthens the width (LATE = the measured
benign direction; a 27 C-calibrated timer at 85 C is ~+24 ps late ≈ −7% E_hop, VBEND
fine), cold shortens it (EARLY = the bad direction; ~−14 ps at 0 C ≈ −1.8% VBEND ≈
−12 mV/hop against the ~120 mV chain budget). Drift ≈ 0.46 ps/K: ±16 K between
calibrations holds the ±7.5 ps measured-benign residual, ±33 K holds the pre-registered
±15 ps band. Cadence conclusion: temperature drift is ms-scale vs ~600 ps hops, so even
sparse calibration tracks it — but the calibration must measure the HOP observable (SAR
on V_bank), never trust the line as a replica of the zero.

## N-spread (d) — `zc_bankN.py`, `zc_bankN.json`, `zc_bankN_analysis.json`

Zero-cross vs data at N=8/32/128 (dV=0.8, parallel-copy scaling of the committed zcs
unit, switch held ON, TON=10 ps uniform; TON offset vs the committed 2 ps N=8 rows:
−2.65 ps, uniform across k).

| N | full-scale k=0..N | slope at mid | σ (8 random words) | σ composed (binomial × slope) |
|---|---|---|---|---|
| 8 | 61.61 ps (17.1%) | 60.2 ps/a | 8.74 ps | 10.65 ps |
| 32 | 63.65 ps (17.6%) | 62.4 ps/a | 4.63 ps | 5.51 ps |
| 128 | 64.84 ps (17.9%) | 63.6 ps/a | 1.93 ps | 2.81 ps |

- **1/sqrt(N) HOLDS for random data**: fitted exponents −0.545 (direct) / −0.480
  (composed), both inside the pre-registered [−0.65, −0.35] band.
- **The FULL-SCALE spread does NOT shrink** (61.6→64.8 ps, ~17–18% of the mean): the
  worst-case pair (all-quiet vs all-switching) is scale-invariant by construction. A
  shared timer must either budget the full ±32 ps (costing, by the measured sensitivity,
  ~−4% VBEND at the early edge) or the architecture must guarantee near-random data
  (then ±3σ at N=128 is ±5.8 ps ≈ free).
- t(a) is one N-invariant curve (max deviation 2.4 ps across N at same a); the zero is a
  function of k alone — 3 placement permutations at k=N/2 are byte-identical at every N.

## Files

`tl_line_cal.py` (G1 + corners) · `tl_probe.py` (ideal probe zero vs T) · `tl_hop.py`
(timer + patched hop, v1/v2) · `zc_bankN.py` (N-spread; NOTE its three parallel lanes
raced on the JSON save — rows recovered from the lane logs, marked in the JSON) ·
`dta_test*.cir` (the temperature-plumbing evidence; the sed-corner model libs were REMOVED -- model-card dta is silently dropped, only the GDTA shim works) · `RESULTS.json` (machine-readable
summary). VAE caches per corner under the session scratchpad (`vae_cache_timer*`).
