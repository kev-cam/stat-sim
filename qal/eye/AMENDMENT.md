# Amendments to `qal/eye/PRE_REGISTERED.json`

`PRE_REGISTERED.json` — sha256 `a053126c158053fb9624095c6ca122cff09f4e61b9230fd4960dd2e4ba450e1f`,
18499 B, mtime **2026-09-29 20:03:31.191825350 -0700**. At that instant the only
other file in `qal/eye/` was `DISK_STATE_BEFORE.txt` (mtime 20:01:44), which
records the directory as otherwise empty. **No deck, `.cir`, `.prn` or result
file existed.**

Every amendment below names the measurement or environment fact that forced it
and the mtime proving it preceded the rows it affects. Following the
`qal/banktank/AMENDMENT.md` precedent.

---

## E0 — environment note, not an amendment (2026-09-29 20:04–20:12)

Recorded because it is the exact hazard `qal/banktank` AMENDMENT A0 flagged.

The box was already saturated when this study's cache build started: **load
average 11.33 rising to 23.43, 14 → 20 concurrent `Xyce` from other workflows on
16 cores, and 33 concurrent `cc1plus`/`g++`** (three campaigns —
`qal/fastwave`, `qal/widebank`, `qal/cipher` — are in flight). `qal/eye` owns its
own `PYMS_VAE_CACHE` at
`…/scratchpad/vae_cache_eye`, **built from empty** (verified: the directory did
not exist at 20:04).

The second geometry Xyce asked for hashes to
`vae_PSP103VA_638208eec0843539.so` — **the very hash banktank A0 recorded as
having failed its full build and fallen back to the "retrying without
zero-valued params" path.** That path is numerically equivalent (it drops
parameters whose value is exactly zero) but it is the `.va`/shell cache hazard
this campaign has been bitten by before (`feedback_pyms_*`,
`async_power_anchor.md`). It is therefore **not taken on trust**: step (b)'s
instrument check digit-checks the committed headline row against its committed
`.mt0` under *this* cache, so any model discrepancy surfaces there before a
single eye number is computed. See `INSTRUMENT_CHECK.json`.

## E1 — edge location is by SUB-GRID INTERPOLATION of the margin curve, not by grid quantisation

**Not a loosening — a strengthening, and it corrects a misconception in my own
pre-registration.** `PRE_REGISTERED.json` treats the 0.10 ps grid as the source
of edge precision ("616 samples across the 61.6 ps jitter"). That is the wrong
account of where the precision comes from.

The measured fact that forced the correction: the margin slope at an eye edge is
of order **5 mV/ps** (a HIGH output traverses ~500 mV in ~100 ps). The eye edge
is the root of `margin(t) = threshold`. Linearly interpolating that root between
two grid points 0.10 ps apart locates it to far better than the grid — of order
**0.01 ps** — because the margin curve is smooth and near-linear over one cell.
Grid quantisation was never the limit.

So the reported edges are the **interpolated roots**, and the grid-quantised
edges are reported alongside them (`opening_ps_gridquant`, etc.) so the two can
be compared. The 0.10 ps ceiling is retained exactly as pre-registered, and its
real function is what the pre-registration's own CONVERGENCE_GUARD says it is:
a check that the *integration* is converged, run against the committed 0.25 ps
ceiling on the instrument-check row.

Written **before** any row deck ran.

## E2 — probe protocol: FULL 8-run for P0, the committed 4-run `oddeven` reduction for P1–P5, with A6 as the catch

**Forced by the environment, and gated.** `PRE_REGISTERED.json`
STEP_c_EYE_PROTOCOL specifies "the FULL 8-run sequential true-ZCS probe …, per
pattern, never the reduced oddeven4 shortcut" — 6 × (8 probes + 1 row).

The cost, measured from the schedule rather than guessed: the probe decks'
transient lengths are `rise k → c_k + 170.3 ps` and `ret k → c_k + H·T + 170.3
ps`, i.e. **8560 ps of transient per pattern for the probes alone** against 2250
ps for the row itself. The four RETURN probes are 5880 ps of that. At six
patterns that is 64.9 ns of transient at a 0.10 ps ceiling on a box already at
load 23 with 20 other `Xyce`.

**What is kept.** The FULL 8-run sequential protocol is run for **P0, the
committed banktank pattern** — the anchor that ties this study to the
instrument.

**What is reduced.** P1–P5 use `bt.do_probe_oddeven`, the **committed, already
validated** reduction (bank 1's zeros applied to the odd banks, bank 2's to the
even banks), with `bt.TPROBE/HPROBE` patched to this study's own `T = 200`,
`H = 4` so the reduction is taken at the row's own schedule and not at the
inherited 120 ps reference. bt.py's own justification for the reduction is that
banks differ electrically only in their pull-up/pull-down mix and in bank 1's
ideal input sources — which is *exactly* the structure a pattern sweep varies,
so the odd/even split is the right one here.

**Why this is not taken on trust.** The pre-registered **A6 gate is unchanged**:
`|IZ_k| ≤ 1 µA` and `|IZQ_k| ≤ 1 µA` at every commanded open, checked on every
row. A6 exists precisely to fail a row whose reused zero did not transfer, and
it has already demonstrated that it works: it is what caught the committed
`row_m10_T200_H4_dv1650_free.json` reusing `T_probe = 120` zeros at `T = 200`
(`A6_zcs_pass = false`, `|I(L)| = 1.79 / 2.72 / 0.38 µA` on banks 2/3/4). **Any
pattern whose row fails A6 under the reduction is RE-PROBED with the full 8-run
protocol**, and if it still fails it is reported as an instrument failure for
that pattern under pre-declared failure handling F1 — never dropped silently.

Written **before** any probe or row deck ran.

## E3 — a SECOND decision reference added BEFORE the first row ran: the DATA eye, because the pre-registered eye's early edge turned out to be the RECEIVER'S POWER-UP, not the data

**Forced by measurement, on the COMMITTED waveform, read-only, before any deck of
mine existed.** `PRE_REGISTERED.json` STEP_d defines the decision level as
`Trip_S(V(rail{k+1})(t))` — the receiver's trip at the receiver's
*instantaneous* rail. That is the right definition of what a receiver has to
tolerate, and it is KEPT as THE pre-registered eye. But run against the
committed `qal/banktank/c_m10_T200_H4_dv1650_free.cir.prn` (a dry run of the
extraction pipeline, no simulation of my own), it does not measure what the
brief is asking for, and the reason is worth stating precisely.

**The measurement.** For bank 2 → bank 3 (a real measured link), at the
committed pattern:

| t (ps) | V(rail2) | V(rail3) = receiver | trip | in-table | min margin | worst |
|---|---|---|---|---|---|---|
| 400 | 0.12877 | 0.00382 | 0.00278 | no | **−14.793 mV** | o3 LOW |
| 450 | 0.62809 | 0.01507 | 0.01098 | no | −3.621 | o3 LOW |
| 550 | 0.99799 | 0.08331 | 0.06066 | no | +64.634 | o3 LOW |
| 595 | 0.95206 | 0.08370 | 0.06095 | no | +61.625 | o3 LOW |
| 600 | 0.95407 | 0.14255 | 0.10379 | no | +97.184 | o3 LOW |
| **605** | 0.96501 | **0.37645** | 0.23364 | **yes** | +209.411 | o3 LOW |

The driver's data is **already fully resolved at 595 ps**: its HIGH margin is
**+885 mV** and its LOW margin **+61.6 mV**, both comfortably positive. What
changes at ~600 ps is not the data — it is that **bank 3's own rail crosses
0.20 V**, the lower edge of the MEASURED trip table, i.e. *the receiver becomes
powered*. Bank 2's first in-table instant is 600.5 ps = `c_3 + 0.5`; bank 3's is
800.6 ps = `c_4 + 0.6`. Both banks' pre-registered eyes therefore "open"
exactly one beat period after their own rail start, and the number 200 ps is
**the beat period fed back to me by my own instrument**, not a property of the
data.

The negative margins before that instant are the same artifact seen from the
other side: with the receiver unpowered the trip is ~3 mV, so any millivolt of
residue on a LOW output scores as a failure. Neither the −14.8 mV nor the
+200 ps is a statement about the wave.

**Therefore, and this is an ADDITION, not a change** (precedent: banktank
AMENDMENT A3, which added a second directly-measured beat metric before its
first row ran, reported both, and explained the disagreement rather than
resolving it in QAL's favour):

* **EYE 1 — the RECEIVER-REFERENCED eye.** Exactly as pre-registered. Reported
  as THE pre-registered eye. Its early edge is the receiver's power-up and is
  labelled as such. It answers: *over what window is the driver on the correct
  side of a live receiver's moving threshold?*
* **EYE 2 — the DATA eye.** The same signed-margin machinery against a **fixed**
  decision level per link: `Trip_S(VR{k+1}B)`, the receiver's trip at the
  receiver's rail at **its own pre-registered boundary instant**. `VR{k+1}B` is
  not a new quantity — it is a committed banktank `.measure` key, reported in
  every committed row as `rail_at_own_boundary_V`, and it is MEASURED per
  pattern from that pattern's own `.mt0`. This isolates the DRIVER: it answers
  *when is the driver's output actually ready, and for how long does it stay
  ready*, independently of when its receiver happens to be switched on. **It is
  the quantity that bounds the beat**, and therefore the one Phase 2 needs.
* Because the choice of a fixed level is a choice, the **sensitivity is
  reported, not hidden**: the data eye is also evaluated at the minimum and the
  maximum of `Trip_S(V(rail{k+1})(t))` over the receiver's in-table window, and
  the three edges are given side by side.

**No simulation is added.** Both eyes come from the same single transient per
pattern, by reading the same dense waveform.

## E4 — the LATE edge does not exist at zero margin in the committed single-shot deck. Measured, and stated as a deck limit, not as a width.

Same dry run, same read-only committed waveform, before any deck of mine.

The pre-registered search window ends at `ro_k`, the return-switch open. The dry
run reports every bank's eye as **clipped at that window end** — so the
"closing" instant was my window boundary, not a measured edge. Extending the
window to the end of the transient shows why: **the margin never crosses zero.**

| bank | V(rail_k) at 990/1000 ps | at `ro_k` | after | worst post-return margin |
|---|---|---|---|---|
| 1 | 1.09800 → 0.93517 | 0.66771 | recovers to 0.72398 | **+156.2 mV** at `ro_1` = 1145.1 ps |
| 2 | — | — | — | **+133.8 mV** at `ro_2` = 1356.1 ps |
| 3 | — | — | — | **+152.4 mV** at `ro_3` = 1550.5 ps |

The return moves charge back to the tank but **nothing pulls the rail to
ground**: bank 1's rail bottoms at 0.668 V at the return ZCS, recovers to
0.724 V, and holds there to the end of the transient (2240 ps), with the min
margin flat at +304.9 mV. The outputs stay on the correct side of the trip
indefinitely, at a degraded level.

So in the committed single-shot deck **the eye's right edge is not physical.**
The true right edge in a *pipelined* machine is set by the arrival of the NEXT
datum on the same bank — at the initiation interval `H·T` — and this deck
contains no next datum. Reported accordingly:

* the zero-margin right edge is **ABSENT within the deck**, and the width is
  reported as a **LOWER BOUND** with the bound named;
* the measured right-edge *structure* is given as the worst post-return margin
  dip and the instant it occurs (`ro_k`, the return ZCS), so a right edge
  appears only once a Phase-2 budget charged against the eye **exceeds
  133.8–156.2 mV**;
* the width that is *operationally* meaningful — the slack the receiver actually
  has — is reported as the DATA eye (E2 above) measured against the receiver's
  own evaluation aperture `[c_{k+1}, t_dv(k+1)]`.

This is written before any row of mine exists so that the right-edge lower bound
cannot be mistaken for a measured width later.

## E2-followthrough — the committed `oddeven4` probe reduction DOES NOT TRANSFER to dV = 1.65 V at T = 200 ps, for ANY data pattern including the committed one. A6 caught it; all five patterns RE-PROBED in full.

E2 said: "Any pattern whose row fails A6 under the reduction is RE-PROBED with
the full 8-run protocol." **All five did.** Measured `|I(L)|` at the commanded
opens (A6 budget: ≤ 1 µA):

| pattern | weight | probe | worst \|I(L)\| | IZ banks 1-4 (µA) | IZQ banks 1-4 (µA) |
|---|---|---|---|---|---|
| **P0** | 5 | **full 8-run** | **0.0128 µA — PASS** | −0.0128 −0.0001 −0.0096 −0.0086 | 0.0070 0.0021 0.0016 0.0016 |
| P1 | 0 | oddeven4 | **18.44 µA** FAIL | −0.006 −0.014 **−18.44** 0.699 | 0.008 0.015 −9.25 −1.73 |
| P2 | 8 | oddeven4 | **45.03 µA** FAIL | −0.009 −0.001 **−45.03** **−39.94** | 0.029 0.008 −17.64 24.67 |
| P3 | 4 | oddeven4 | **25.93 µA** FAIL | −0.004 −0.006 −6.23 −21.78 | 0.001 0.018 −20.11 **25.93** |
| P4 | 5 | oddeven4 | **28.15 µA** FAIL | −0.013 −0.000 −11.59 −26.73 | 0.007 0.007 −19.64 **28.15** |
| P5 | 1 | oddeven4 | **13.83 µA** FAIL | −0.008 −0.005 −8.93 −5.38 | 0.010 0.003 **−13.83** 6.12 |

**This is an instrument finding, not a pattern finding.** P4 has the SAME Hamming
weight as P0, and its bank-1 and bank-2 zeros come out **bit-identical** to P0's
(124.5675 / 126.5751 ps) — yet substituting those for banks 3 and 4 costs 11.6
and 26.7 µA. The reason is quantitative and clean: P0's FULL protocol measures
bank 3's zero at 124.0626 ps against bank 1's 124.5675 ps, a **0.5 ps**
difference, and `dI/dt` at the zero crossing is ≈ 23 µA/ps
(`I_pk·ω` ≈ 1.2 mA × π/125 ps), so **0.5 ps of schedule error is ~12 µA of
residual** — twelve times the A6 budget. The reduction was validated at
`m = 10, dV = 1.2`; that validation does not extend to `dV = 1.65` at `T = 200`,
where the peak currents are ~1.2-1.3 mA rather than ~0.9 mA.

The failing rows and their zeros are **quarantined, not deleted**, in
`P{n}/oddeven4_A6FAIL/`. All five patterns are re-run with the FULL 8-run
sequential protocol, the same one P0 used and passed.

**Cross-campaign caution, reported not acted on:** `qal/widebank` and
`qal/fastwave` are in flight at `dv1650` on the same harness. If either uses
`bt.do_probe_oddeven`, this measurement says its zeros will not satisfy A6 at
this swing. Their directories were not touched.

## E5 — the pattern set is EXTENDED to every Hamming weight, because P4 proved the eye depends only on the WEIGHT of the data, not its arrangement. The intersection becomes COMPLETE over the whole data space.

**Forced by a measurement, and it can only TIGHTEN the intersection.**

P4 was pre-registered as the arrangement control: `[0,1,1,0,1,1,0,1]`, the same
Hamming weight (5) as the committed P0 `[1,1,1,0,1,0,0,1]`, different
arrangement. The measured answer is that the two are the *same circuit*:

* the two decks differ **only** in which of the eight `VI1_i` sources carries
  1.65 V (verified by diff with those eight lines masked: no other line differs);
* the true-ZCS instants agree to **3 × 10⁻⁹ ps** (`tzr` 124.56753089 / 126.57512478
  / 124.06259381 / 125.37363665 ps for both) — solver noise, not physics;
* all **76** rail `.measure` keys agree with worst difference **exactly 0.000 V**;
* the data-eye opening instants agree **bit-for-bit** (bank 1 303.2822, bank 2
  509.6460, bank 3 708.1180 ps).

The reason is structural: the eight cells in a bank are identical and their only
coupling is the single shared rail, so permuting which cells hold which bit is a
relabelling. **The data space of an 8-gate bank is therefore not 2⁸ = 256
vectors; it is 9 — one per Hamming weight 0…8.**

The pre-registered set covers weights {0, 1, 4, 5, 5, 8}, i.e. five distinct
weights of nine. **Four patterns are ADDED to complete it** — nothing is removed
and no criterion changes:

| tag | bits | weight |
|---|---|---|
| W2 | `[1,1,0,0,0,0,0,0]` | 2 |
| W3 | `[1,1,1,0,0,0,0,0]` | 3 |
| W6 | `[1,1,1,1,1,1,0,0]` | 6 |
| W7 | `[1,1,1,1,1,1,1,0]` | 7 |

With these the INTERSECTION is over **every distinct data vector the bank can
present**, so the reported eye stops being a sample of the data space and
becomes the true worst case over it. Adding patterns to an intersection can only
make the eye narrower or leave it unchanged — it cannot manufacture a pass.
Both the 6-pattern (pre-registered) and the 9-weight (complete) eyes are
reported, so the effect of the extension is visible rather than absorbed.

All four use the FULL 8-run sequential probe protocol (per E2-followthrough) and
carry the unchanged A6 gate.

Written before the four decks ran; the pre-registered six had already completed
and are unaffected.

## E6 — a BUG IN MY OWN E1 REFINEMENT, caught by an internal consistency check and fixed. The headline numbers are unaffected; the pre-registered eye's numbers moved by ~2-3 ps.

E1 replaced grid-quantised eye edges with the **interpolated root of
`margin(t) = threshold`**. That is correct only when the edge actually IS a
margin crossing. The pre-registered eye (EYE1) has a SECOND condition in its
mask — the receiver's rail must be inside the MEASURED trip table — and when
*that* condition is what turns the mask on, the margin at the neighbouring grid
point is **already past the threshold**, so solving `margin(t) = 0` there
**extrapolates backwards** and reports an edge a couple of picoseconds too early.

**How it was caught.** Not by inspection — by checking the emitted
`MARGIN_bank2.csv.gz` against the reported edge. The curve shows
`in_table` flipping 0 → 1 at t = 601.0 ps and never returning, while the
reported opening was 598.065 ps: an opening 2.9 ps *before* the first instant
the eye's own mask allows. The margin at 600.9 ps was already +118 mV, so the
root-find had nothing to find and extrapolated.

**The fix.** Interpolate an edge only when the neighbouring grid point is on the
*failing* side of the threshold; otherwise report the grid-quantised edge and
label it. Every edge now carries `opening_edge_set_by` /
`closing_edge_set_by` ∈ {`margin_crossing`,
`auxiliary_condition_not_a_margin_crossing`, `clipped_at_window_start/end`}.

**Effect, stated plainly:**

| | before | after |
|---|---|---|
| EYE1 opening, banks 1/2/3 | 398.178 / 598.065 / 797.491 ps | **401.000 / 601.000 / 801.000 ps** |
| EYE2 (DATA) opening, banks 1/2/3 | 328.599 / 529.641 / 729.382 ps | **328.599 / 529.641 / 729.382 ps — UNCHANGED** |

The DATA eye is untouched because it has no auxiliary condition: its edges were
genuine margin crossings all along, and it is the reference every headline
number and the whole Phase-2 handoff is taken from. The pre-registered eye's
corrected opening is now *exactly* `c_k + T + 1.0 ps` — the beat period plus one
grid step — which makes E3's finding sharper rather than weaker: that edge is
the receiver's power-up, to the grid.
