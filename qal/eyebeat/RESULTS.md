# qal/eyebeat — THE BEAT SWEEP: the eye of a per-bank-tank QAL wave vs the beat period T

MEASURED on the arrangement that computes (`qal/banktank` 0aae11e per-bank tanks;
m = 10, H = 4, dV = 1.65 V, L = 15 nH, free-running, 4 banks × 8 committed
1.12/0.74 µm inverter cells, CL 2 fF, no flop/latch/buffer/keeper between banks),
T = 60 / 90 / 120 / 150 / 200 / 250 / 300 ps at FIXED cell RC.

Pre-registration `PRE_REGISTERED.json`, sha256 `dddf7773e38a1fd1…`, mtime
**2026-09-29 23:33:36 −0700**, written when the directory held only
`DISK_STATE_BEFORE.txt` (23:32:14) — before the first deck. Amendments in
`AMENDMENT.md` (B1: my wrong zeros file in the first IC attempt, caught by the
byte-identity check; B2: the pre-registered probe protocol measurably fails at
short T and was replaced by Newton-on-the-row, A6 gate unchanged).

Language rule respected throughout: the quantities are TRACKING LAG, EYE
(width/height/centre) and MARGIN AT THE SAMPLING INSTANT. Committed names
appear only in quotes with reinterpretation.

---

## THE VERDICT ON THE PREDICTION, first

**The fixed-lag half of the model is CONFIRMED with startling precision; the
fraction-of-the-beat claim is CONFIRMED in sign but is small and partly
schedule-construction; the stranded-HIGH corollary is REFUTED as a
beat-dependence — the stranding was an ARRANGEMENT property (peer feeding), not
a slow-beat artefact.**

1. **Both eye edges are FIXED LAGS off the power schedule.** The data-eye
   opening after the bank's own rail start is **129.6 ± 0.1 ps** across
   T = 150–300 (0 mV: 129.654 / 129.641 / 129.612 / 129.583 at
   T = 150/200/250/300 — a 0.07 ps spread over a 2× beat change), and the
   3σ-threshold closing trails the return close by **148–161 ps** wherever it
   exists in-deck. The beat is a free knob BETWEEN two RC/LC-fixed lags —
   exactly the user's mechanism.
2. **The early-edge collision exists and is measured at T between 90 and
   120 ps.** At T = 120 the chain computes (32/32 gates value-correct, all
   three patterns) with **+2.6 ps** of setup slack at 3σ; at T = 90 and 60 the
   slack is **negative** (−12 to −37 ps), the receiver's rail starts before the
   driver's data is valid, and the chain stops computing (8–32 of 32 gates
   value-wrong at the one-beat boundary). The committed dv1650 banktank series
   (value-correct at T ≥ 120, margins collapsing below) says the same thing
   with its instrument-suspect zeros; this sweep says it with every row inside
   the 1 µA A6 gate.
3. **Fraction of the beat:** with both edges fixed, the in-deck 3σ eye is
   `W3σ ≈ H·T + (154 − 130) ps`, so `W3σ/T = 4 + ~24/T` — it GROWS as T
   shrinks: measured 4.089 → 4.100 → 4.117 → 4.120 at T = 300 → 250 → 200 → 150
   (worst measured bank, real edges, first contiguous interval). Confirmed in
   sign, **but the growth term is the fixed-edge residue (~24/T), riding on the
   H·T hold window that is itself a schedule knob.** At T ≤ 120 the 3σ eye
   never closes inside the deck at all (post-return margin floor 109–276 mV ≫
   19.3 mV), so its width there is only a lower bound.
4. **Stranded-HIGH: REFUTED as a beat effect, on this arrangement.** The
   minimum HIGH during the source bank's drain is **0.662–0.697 V at every T
   from 60 to 300 ps** — non-monotone (dip at T = 150), total spread 34 mV,
   and slightly LOWER at short T (0.686 V at 60 vs 0.696 V at 300): the
   opposite sign of the corollary, and nowhere near the committed peer-fed
   stranding band 0.336–0.455 V. Per-bank tanks do not strand the HIGH at ANY
   beat. See §(d) for the re-reading this forces.

---

## (b) Instrument checks — all pass

* **IC1, the committed row** (`IC1.json`): `c_m10_T200_H4_dv1200_free` deck
  regenerates BYTE-IDENTICALLY from bt.py + the committed own-T zeros
  (`zeros_m10_dv1200_T200_H4.json` — banktank A7); run under this study's own
  `PYMS_VAE_CACHE` built from empty: **440/440 `.mt0` keys within 1e-6, worst
  3.1e-07**; the quoted rails reproduce digit-for-digit
  **0.7544238 / 0.6767239 / 0.7312457 / 0.7200878** (the brief's …56/…77 are
  last-digit roundings, as qal/eye's IC also found). First attempt used the
  T=120-reference zeros file and FAILED byte-identity (AMENDMENT B1, kept in
  `IC1_wrongzeros.json`): an accidental sensitivity measurement — sub-ps zero
  changes move banks 2–4 rails by 0.6–1.1 mV.
* **IC2, the eye extractor** (`IC2_extractor.json`): this pipeline, run
  read-only over qal/eye's own P0/P1/P2 transients, reproduces EYE.json's
  per-pattern EYE2 openings for banks 1–3 to **4 × 10⁻⁵ ps** (bar 0.01 ps).
* **Continuity at T = 200**: my rows (0.1/0.25 ps steps, qal/eye's measured
  zeros) pass A6 at 0.027–0.040 µA on the first run and reproduce the eye
  study's headline numbers at reporting precision: openings 328.600/529.641
  (theirs 328.599/529.641), "setup slack" 71.400/70.359/70.618 (theirs
  71.401/70.359/70.618), 3σ closes 1153.6/1356.6 and widths 823.3/826.4
  (theirs 1153.6/1356.6, 823/826).
* **Convergence** (`CONVERGENCE.json`): T=60 P0 at 0.1/0.25 vs 0.05/0.10 ps,
  same zeros: eye openings agree to **0.0002 ps** (bar 1.0 ps).
* **Pattern-reduction guard** (`GUARD_P3.json`): mid-weight P3 at T=60 and
  T=300 opens 1.6–24 ps EARLIER than the {P0,P1,P2} intersection at every
  bank — the weight extremes bind, the qal/eye reduction transfers.
* **A6**: every row in every headline number ≤ 1 µA at every commanded open
  (worst 0.74 µA, at T=60).

### AMENDMENT B2 — what it took to measure short beats honestly
The pre-registered oddeven4-at-own-T probe protocol fails at T = 60 twice
over: its return-probe window is sized by the dv1.2 anchor (170 ps) and the
dv1650 return zeros run past it (NO ZERO); and even the full 8-run sequential
protocol leaves 12.7 µA in the row, because at T < ~130 ps the rise windows of
adjacent banks OVERLAP (c-spacing < tzr ≈ 125 ps) and the probe's environment
(later banks idle) no longer matches the row. Replaced at every T by
**Newton-on-the-row**: seed with measured zeros, read each conducting
current's crossing from the row's own waveform near the commanded open,
correct (trust region ±10 ps), re-run to the unchanged A6 gate. Converged in
1–4 iterations everywhere (e.g. T=60 P1: 81.9 → 20.9 → 0.74 µA). A by-product
measurement: the RISE zeros are beat-invariant above the overlap regime
(T=300 corrections −0.01 to −0.02 ps off T=200 seeds) while the RETURN zeros
move with T (+0.1 to +20 ps) — the charge left in the rail at the return
depends on the hold, the LC rise does not.

---

## (c) The T sweep — the eye per bank per T

EYE2 (fixed decision level `Trip_S(VR{k+1}B)`, the reference that bounds the
beat), intersection over {P0, P1, P2}, first contiguous interval, banks 1–3
(MEASURED receivers; bank 4 is DERIVED and never headline). Full per-bank
records incl. EYE1 in `T*/EYEBEAT.json`; margin curves derivable from the kept
transients.

| T ps | open−c 0mV (worst bank) | open−c 3σ | 3σ close−r | W3σ ps | W3σ/T | slack@3σ ps | HEIGHT at sampling (worst, mV) | floor after return mV | computes? |
|---|---|---|---|---|---|---|---|---|---|
| 60  | 87.7–94.5  | 90.0–96.7   | none in deck | ≥856 (LB) | ≥14.3 (LB) | **−30.0…−36.7** | **−224.8** | +272.1 | **NO** (24–32/32 wrong) |
| 90  | 100.6–102.9| 102.8–105.2 | none in deck | ≥984 (LB) | ≥10.9 (LB) | **−12.8…−15.2** | **−136.7** | +175.6 | **NO** (8–16/32 wrong) |
| 120 | 112.4–114.8| 114.8–117.4 | none in deck | ≥1122 (LB)| ≥9.3 (LB) | **+2.6…+5.2** | +46.5 | +109.3 | YES 32/32 |
| 150 | 128.7–129.7| 130.2–130.3 | +148.3–148.7 | 617.9 | 4.120 | +19.7 | +135.2 | **−17.8** (eye truly closes) | YES 32/32 |
| 200 | 128.6–129.6| 130.2–130.3 | +153.6–156.6 (bank3 none) | 823.3 | 4.117 | +69.7 | +174.7 | +14.9 | YES 32/32 |
| 250 | 128.5–129.6| 130.1–130.3 | +155.3–158.7 (bank3 none) | 1025.0 | 4.100 | +119.7 | +177.4 | +17.3 | YES 32/32 |
| 300 | 128.4–129.6| 130.0–130.3 | +157.0–161.0 (bank3 none) | 1226.8 | 4.089 | +169.7 | +178.5 | +18.0 | YES 32/32 |

**Closing mechanisms.** Early edge at every computing T: **M1** — the pull-up
has not had time at a rail that is itself still part-way up (transfer gate
conducting, margin climbing at 8.6–31.3 mV/ps). Late edge (3σ, T = 150–300):
**M3+M5** — the drain itself: the return switch is STILL CONDUCTING, the HIGH
output tracking the draining rail down through trip+3σ at −0.5 (T=200) to
−8.5 mV/ps (T=150); the closing instant is essentially `r_k + tzq`, the end of
the LC return. At T ≤ 120 there is no late edge in the deck at all.

**The openings at T ≤ 120 are NOT evidence of a faster cell.** They shrink
(129.7 → 114.8 → 102.9 → 94.5 ps) because the fixed decision level
`Trip_S(VR_rx B)` falls with the receiver's boundary rail (1.00–1.09 V at
T ≥ 150 down to a mid-ramp rail at T = 60): the data crosses a lower bar
earlier, but only because the receiver evaluating it is running on a rail that
is still rising. The negative slack is the honest number, and it is what kills
T = 60 and 90.

**Heights at the sampling instant saturate, they do not peak.** Worst-bank
HEIGHT at c+T: −224.8 / −136.7 / +46.5 / +135.2 / +174.7 / +177.4 / +178.5 mV
across the sweep — a steep climb into ~saturation past T = 200 (+3.8 mV from
200 to 300). The dv1.2 skip-chain series' FALL from T=200 to T=300 does NOT
reproduce here; see §(d).

## (c) The tracking lag itself, measured

Per bank, HIGH gates, both schedule sides (`TRACKING_LAG` in each
EYEBEAT.json; medians over gates×patterns, banks 1–3):

* **Rising, LAG_A** (rail vs output through the same 0.5·V_railpeak level):
  **55–72 ps** — mid-ramp tracking through the pull-up's large early-ramp
  R_on; not the handful of ps a small-signal R_on·C_out (~kΩ·2 fF) would give.
* **Rising, LAG_B** (rail up through its boundary value → HIGH up through the
  link's decision level — power-present to data-valid): **12–39 ps**.
* **Draining, LAG_A** (the side the user's premise rests on; rail vs output
  down through the same mid-drain level): **median 59–88 ps, ZERO censored
  gates at every T** — every HIGH follows its rail down through the mid-drain
  level, trailing it by ~60–90 ps. The premise's separation is REAL at this
  granularity: for ~60–90 ps after the rail passes any drain level, the output
  has not yet passed it — the data is still good while the power is leaving.
  What PRESERVES the data past the whole drain on this arrangement is not the
  lag but the drain's ENDPOINT: the recycle stops at the tank floor
  (rail ~0.68 V), so the tracked output stops at 0.66–0.70 V, still ≥ 2.3σ
  above the decision level at T ≥ 200.

## (d) The stranded-HIGH test — the corollary is REFUTED as a beat effect

Minimum HIGH during the source bank's drain (worst gate, worst pattern, banks
1–3), vs T:

| T ps | 60 | 90 | 120 | 150 | 200 | 250 | 300 |
|---|---|---|---|---|---|---|---|
| min HIGH V | 0.686 | 0.685 | 0.675 | **0.662** | 0.694 | 0.696 | 0.696 |

* **No beat dependence in the predicted direction**: the series is
  non-monotone with a 34 mV total spread, and the short-beat end is slightly
  LOWER, not higher. Short beats do keep the HIGH near the rail — but so do
  long beats. (The T = 150 dip, 30 mV deeper with the deepest post-return
  margin excursion of the sweep — floor −17.8 mV, the only T where the eye
  truly closes — is measured, systematic across banks, and NOT root-caused
  here; its closing record is M3+M5, the deepest drain excursion of the sweep
  coinciding with the receiver-boundary rail at its highest, 1.0009 V.)
* **Droop rate during the drain**: median 0.97–1.72 mV/ps across the sweep,
  T-invariant within its own spread — the committed peer-fed head-link
  "bleed" of **1.29 mV/ps sits inside this band**. The RATE at which a HIGH
  tracks a leaving rail is the same physics in both arrangements; what
  differed is the ENDPOINT: a peer-fed drain continues into the next transfer
  (endpoint ≈ Vtn-referenced strand, the committed 0.336–0.455 V), a
  tank-recycle drain stops at the tank floor (endpoint 0.66–0.70 V).
* **The re-reading this forces** — and it is NOT the one the corollary
  proposed. The committed stranded-HIGH chain failures were **arrangement
  (peer-fed) artefacts, not slow-beat artefacts**: no beat, fast or slow,
  reproduces stranding on the arrangement that computes. Specifically:
  * `qal/chain3` peer-fed rows (e.g. the f45 instrument-check row, bank-3 rail
    key 0.4443892 — inside the stranded band) — re-read as peer-fed drain,
    not beat choice; no beat would have saved them.
  * the committed peer-chain "no achievable beat at ANY T from 60–300 ps"
    verdict (45 rows) — its LATE-side failures (long T) are peer-fed
    stranding; its SHORT-side failures are the genuine early-edge collision
    this sweep confirms at T < ~120. Both halves were real, but only one of
    them was about the beat.
  * the dv1.2 skip-chain interior-optimum series the brief cites
    (23.63/27.48/31.62/25.18 committed "worst-gate %" at T = 60/120/200/300):
    the RISING branch 60→200 is the early-edge collision (confirmed here as
    beat physics: not-yet-risen at short T), but the FALLING branch 200→300 —
    the part read as "the eye closing as the output tracks the rail down" —
    does NOT reproduce on per-bank tanks (heights saturate: +174.7 →
    +178.5 mV from T=200 to 300). The interior optimum was HALF beat physics
    (early edge), HALF peer-fed architecture (late edge). On the arrangement
    that computes, only the early edge survives.

## (e) The optimum and the sustainable beat

* **Absolute 3σ eye width**: grows with T (823 → 1025 → 1227 ps at
  200/250/300); maximum at **T = 300** (edge-to-edge; it is H·T-dominated).
* **Fractional (W3σ/T), real edges, computing points**: **T = 150** (4.120,
  vs 4.089 at 300) — the smallest beat above the collision. T = 120 shows a
  larger clipped LOWER BOUND (≥9.3) with the eye unbounded in-deck, but its
  slack is +2.6 ps — inside one σ of anything; it is not an operating point.
* **Margin at the sampling instant**: saturates by T = 200–250; nothing is
  bought above 250.
* **The budget-composed sustainable beat** (pre-registered composition:
  61.6 ps worst-case data spread [GIVEN, N-invariant] + 4.6 ps drift
  [0.46 ps/K × ±10 K ASSUMED], charged against the 3σ setup slack;
  σ_trip = 6.441 mV lower bound already inside the 3σ threshold):
  * T = 150: slack 19.7 ps < 35.4 (even the random-data budget) — fails.
  * **T = 200: slack 69.7 ps > 66.2 — the fastest swept beat that passes, and
    it passes by only 3.5 ps** (an assumed ±17.6 K instead of ±10 K would
    erase it). Under the random-data variant (61.6/√N, N=4 → 30.8 + 4.6 =
    35.4 ps) T = 200 passes with 34.3 ps to spare, and 150 still fails.
  * Flag inherited from qal/eye, reported not resolved: the 61.6 ps figure
    does not reproduce at this operating point as a zero-crossing spread
    (their measured 7.8–9.2 ps p-p over all nine weights). If the LOCAL
    measured jitter is the right charge (9.2 + 4.6 = 13.8 ps), **T = 150
    passes** (19.7 > 13.8) and the sustainable beat improves 200 → 150. Which
    number is the correct charge is the standing Phase-2 question; both
    compositions are given.
* **CMOS comparisons** (THROUGHPUT only — the standing liability holds: the
  logic resolves inside the transfer at a delivered rail of ~0.95–1.19 V,
  below CMOS's supply; per-level LATENCY cannot beat CMOS and no latency win
  is claimed):
  * Load-matched level: **57.143 ps at 2 fF** (this deck's CL is 2 fF — that
    is the matched choice; 94.174 ps at 6.91 fF is context only). Sustainable
    beat T = 200 ⇒ the QAL level is **3.50× slower than the load-matched CMOS
    level** (150 would be 2.63×).
  * CMOS + flop tax (t_reg **307.1 / 335.7 / 390.0 ps MEASURED**; liberty
    1.11–1.21× optimistic): crossover depth D* = t_reg/(T − 57.143) =
    **2.15 / 2.35 / 2.73** at T = 200 (1.65–2.05 lower bound... at T = 150:
    3.31 / 3.61 / 4.20). Meaning: once CMOS must chop its pipeline finer than
    ~2–3 logic levels per stage to chase frequency, the flopless QAL wave
    out-throughputs it, DERIVED under one-datum-per-beat-per-level issue.
  * Honesty on issue rate: THIS deck's per-bank initiation interval is
    H·T = 800 ps (hold 4 beats), and the measured opening bounds the hold at
    H ≥ 1 + 130/T (H = 2 at T = 200). One datum per beat per level therefore
    requires interleaving ~H+1 bank sets — standard wave-pipeline bookkeeping,
    DERIVED, not demonstrated in this deck.

---

## Scorecard on my own pre-registered expectations (`SCORECARD.json`)

| | verdict |
|---|---|
| EXB1 opening T-invariant 129±8 for T≥150; collision 120–150 | **HIT on invariance** (129.6±0.1); collision band MISSED LOW — the collision is at 90–120 (T=120 computes, barely) |
| EXB2 fraction grows as T shrinks; physics carriers flat opening + late edge r+150±100 | **HIT** (4.089→4.120; opening flat; closes r+148–161) |
| EXB3 rising lag 5–25 ps; draining large/censored | **MISS on rising** (55–72 ps — mid-ramp R_on is far above the small-signal estimate); **half-right on draining**: large (59–88 ps) but ZERO censoring — the tank-floor endpoint, not the lag, is what preserves the data |
| EXB4 stranded-HIGH weakly T-dependent (<30 mV), milder at short T, ≥0.455 V everywhere | **mostly HIT** (34 mV spread, all ≥0.662 V) but the direction at the extremes is OPPOSITE (60 ps end 10 mV lower) and the T=150 dip was not anticipated |
| EXB5 fractional optimum T=150; absolute T=300; height interior 200–250 | **HIT / HIT / MISS** — heights saturate rather than peak |
| EXB6 sustainable beat 200 (slack ~68–70 vs 66.2); 150 fails at ~19 | **HIT** (69.7 vs 66.2; 150 at 19.7) — the T=150 slack landed within 0.7 ps of the guess |

## Liabilities and open items

* Bank 4 is DERIVED everywhere (no bank 5 exists); banks 1–3 carry every
  headline number.
* The T = 150 post-return dip (floor −17.8 mV, deepest HIGH drain excursion
  0.662 V) is measured, systematic, and NOT root-caused; until it is, T = 150
  operating claims should treat the post-return interval as closed (the
  pre-return eye and its 19.7 ps slack are unaffected).
* The 61.6 ps budget number remains unreconciled at this operating point
  (inherited flag); the sustainable-beat verdict is given under both readings.
* σ_trip = 6.441 mV is a LOWER bound (dw/dl excluded); leakage figures under
  `sg13lv_compat.sp` are lower bounds (PSP103 defaults, JUNCAP200 enabled,
  pMOS STI-edge clipped).
* `eyecalc.mechanism`'s `mgn_mV` field reports the EYE1-reference margin even
  in EYE2 records (its M-codes and derivative terms are reference-correct);
  quoted margins in this report come from the eye curves, not that field.
* Energy is reported in the kept `.mt0` integrators and is not a gate here
  (direction: SPEED). Nothing in this study claims a latency win.
