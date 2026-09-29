# skip4 protocol amendments

Order of events on disk (mtimes are the proof; `ls -la --time-style=+%H:%M:%S`):

1. `PRE_REGISTERED.json` 19:04:51 — the only file in the directory at that moment.
2. `skip.py` / `extract.py` / `go.py` — the harness.
3. This file — **A1 and A2 below were written before any measured chain row existed**
   (`rows.json` did not exist; the only Xyce artifacts in the directory were the two
   instrument-check decks, which are byte copies of committed files).
4. `rows.json` — the measured rows.

---

## A1 — the stage-boundary rule, made STRICT

Pre-registration `ACCEPTANCE_CRITERIA.A1_stage_boundary_definition` said: bank *k*'s
boundary is `c_k + T`, where `c_k` is the close of the hop that charges bank *k*, "and for
the ideally seeded head banks, the instant their pre-charge gate begins to cut".

Two problems, both visible from the schedule algebra alone, with no simulation:

* a **head** bank is held at `dV` by an ideal gate from *t = 0*, so "`c_k + T`" for a head
  bank lands ~`T − HEAD_LEAD` past the instant its own rail starts to drain — it would read
  a dead rail and report a meaningless settling percentage;
* in the **adjacent** scheme a bank is drained exactly one beat after it is charged
  (`d_k = c_k + T`), so `c_k + T` is the instant its rail *starts to move*. Reading the
  bank's data there is reading it one edge too late.

**Amended.** The boundary is

```
bound_k = min(c_k + T, d_k - EDGE)      for a hop-charged bank
bound_k = d_k - EDGE                    for a head bank (no c_k)
```

with `EDGE = 2 ps`, the committed transfer-gate edge. `d_k - EDGE` is the last instant
bank *k*'s data is still undisturbed — chain3's own convention, verbatim. This clause can
only move a checkpoint **EARLIER**, i.e. it gives every bank **less** settling time, in both
schemes, symmetrically. It is the harsher reading and it is the one gated on.

Consequence worth stating up front: in the **skip** scheme `d_k = c_k + 2T`, so
`d_k − EDGE > c_k + T` and the binding term is `c_k + T` — one beat, exactly as
pre-registered. In the **adjacent** scheme `d_k = c_k + T`, so the binding term is
`c_k + T − EDGE`. The two schemes are therefore compared on the same one-beat rule, with
adjacent given 2 ps less. That 2 ps is not what decides anything here.

## A2 — an IDEAL-RAIL CONTROL on the deepest bank, INSTEAD of a per-beat top-up

*(This amendment was first written as "add chain3's per-beat top-up as a secondary mode".
It was replaced, before any `topup` row was ever run, by the measurement in A3 below.
The reasoning that forced the replacement is recorded here in full.)*

The pre-registration describes only the free-running chain. The sibling chain3 workflow has
measured that a free-running adjacent chain delivers rails below the 0.60 V functional
cliff, so every gate fails there for a rail reason and the scheduling question the user
asked would be unanswerable — both schemes would die of rail collapse before the schedule
mattered. Something has to separate a SCHEDULING failure from a RAIL-COLLAPSE failure.

chain3's answer was a per-beat top-up placed in the inter-hop gap. **That cannot be used
here, and the reason is MEASURED:** the chain hop at this operating point takes
94.4–103.7 ps (A3) while the beat periods that decide the headline are 105–160 ps, so the
gap between a hop's own zero and the next boundary is 1–16 ps. A 20 ps top-up window
therefore either (a) overlaps the hop, clamping the destination rail and suppressing the
very inductive transfer under test, or (b) restores the rail a few ps before the boundary —
which is chain3's own A5 artifact, "it moves the goalpost", measured there to read 44.7% on
a chain whose rail was fine. Neither is admissible.

**Amended.** Two things replace it, and neither needs a top-up:

1. **The primary comparison is at MATCHED POWER-HOP DEPTH**, where the rails are matched by
   construction and no ideal source is added at all. Bank *k* is *n* hops from an ideal head;
   skip's bank 3 and adjacent's bank 2 are both *n = 1*; skip's bank 5 and adjacent's bank 3
   are both *n = 2*. Same L, same switch, same dV, same cells, same number of hops of droop —
   so any settling difference between them is the SCHEDULE. Both decks also report the
   per-bank power depth and data depth explicitly, so no reader can be misled by comparing
   a bank at one depth against a bank at another.
2. **Mode `dstheld`: an IDEAL-RAIL CONTROL on the deepest bank only.** That bank's rail is
   pinned to `dV` by a permanently-on supply transmission gate for the whole run, while its
   INPUTS stay fully realistic (its data-source bank still has its own source drained on
   schedule). Because the deepest bank has no successor, pinning it removes no drain event
   from the deck. It separates "the delivered rail is too low for the pull-ups" from "the
   inputs are degraded" in one run. It is an ideal-source CONTROL, labelled as such, and it
   is never quoted as a QAL operating point.

## A2-superseded — the per-beat TOPPED-UP variant (never run)

The pre-registration describes only the free-running chain (heads ideally pre-charged,
"every other bank charged ONLY by a real inductive hop"). The sibling chain3 workflow has
since measured that its free-running adjacent chain delivers bank-3 rails of
0.364–0.509 V — **below the 0.60 V functional cliff** — so *every* gate fails there for a
rail reason, and the scheduling question the user asked would be unanswerable: both schemes
would die of rail collapse before the schedule mattered.

**Amended.** A second mode, `topup`, is added, using chain3's per-beat top-up device and
window placement **verbatim** (tg15p-sized TG to the ideal `dV` node, 20 ps conduction
window placed at the START of the bank's own beat, so the rail is restored first and the
cells then settle against a restored rail — chain3's A5). It exists for exactly one purpose:
to separate a SCHEDULING failure from a RAIL-COLLAPSE failure, which is the only way the
skip-vs-adjacent comparison isolates the mechanism the proposal is about.

`free` remains the primary mode and the headline. `topup` numbers are labelled as carrying
an ideal-source booking (chain3 measured that booking at 15.2–29.1 fJ per bank per hop,
1.8–3.5× the loss it repairs) and are never quoted as a QAL operating point.

## A3 — the beat-period grid, after the MEASURED chain hop time

*Written after the topology-calibration probe runs and before any measured row.*

Pre-registered grid: `T in {45, 60, 75, 90, 120, 300} ps`, chosen on the DERIVED
expectation that the chain's own `t_hop` would be ≈ 87 ps (the committed 65.495 ps single
hop × the sibling's measured 1.326 chain penalty), so that `t_hop/2 ≈ 43 ps` would be the
floor the interleaved hop constraint allows.

MEASURED (probe runs `p1/p2/p3_skip_free_T120_dv1200.cir`): the chain hop at
L = 15 nH / W = 30 µm / dV = 1.2 takes

| hop | src -> dst | t_zcs (ps) | I_pk (uA) | x committed 65.495 ps |
|---|---|--:|--:|--:|
| 1 | rail1 -> rail3 | **103.681** | 1385.69 | 1.583 |
| 2 | rail2 -> rail4 | **95.659** | 1230.34 | 1.460 |
| 3 | rail3 -> rail5 | **94.386** | 676.33 | 1.441 |

i.e. **1.44–1.58×** the committed single hop, not the 1.33× the sibling measured at
L = 277.8 nH on a three-bank chain. Every middle bank here carries two 30 µm transfer-switch
terminals where chain3's bank 3 carried one, and junction capacitance is absent from both
(`sg13lv_compat.sp` zeroes ad/as/pd/ps), so both are lower bounds.

Consequence: at any `T < t_zcs` a bank's boundary `c_k + T` falls **inside its own
charging hop** — the bank has not finished being charged when it is required to be valid.
Those rows are structurally doomed for a reason that has nothing to do with the schedule,
and spending the run budget on three of them would measure nothing.

**Amended grid**, same span, re-centred on the region that decides the headline (the
123.4 ps committed adjacent baseline and the 92.8 ps CMOS level):

```
free    : T in {60, 105, 120, 140, 160, 200, 300} ps   (60 kept as the recorded hop-floor row)
dstheld : T in {120, 160} ps                           (ideal-rail CONTROL, both schemes)
```

`T = 60 ps` is retained deliberately as one recorded row per scheme, so that the
"boundary inside the charging hop" failure is on the record and is not confused with a
settling failure. Rows in that condition are flagged
`boundary_inside_charging_hop = true`.

## A4 — the `dataheld` CAUSAL CONTROL, added AFTER measured rows existed

Stated plainly: this control was **added after** the first 16 measured rows were on disk,
because those rows produced a mechanism I had not pre-registered and that had to be tested
rather than asserted. It is an ADDITION, not a re-definition: no pre-registered criterion,
threshold, boundary or grid point was changed, and every `free` row stands exactly as first
measured.

What the rows showed: under the skip schedule the consuming stage's **pull-UP** became the
laggard, and its gate — the held predecessor's logic LOW — was measured CREEPING UP
(+179 mV at T = 120 ps, +689 mV at T = 300 ps). The obvious attribution is "the creep causes
the pull-up failure". That is an attribution, so it needed its own measurement.

`dataheld` (skip only): bank 2's eight gate inputs come from ideal DC sources at the correct
pattern instead of from bank 1's outputs — i.e. bank 2's own predecessor is never drained out
from under it, so bank 2's LOW outputs cannot creep. Everything else is identical: bank 1
still drains on schedule, hop 1 still charges bank 3, same L, same switch, same phases.
It is an ideal-source control, labelled, never quoted as an operating point.

MEASURED, and it **partly refuted my own attribution**: removing the creep moved bank 3's
pull-up from 27.48% to 30.25% at T = 120 (worth only 2.8 points) but from 25.18% to 67.62%
at T = 300 (worth 42.4 points). So the creep is NOT the dominant term at short beats — the
pMOS's own speed at the delivered rail is — and it IS the dominant term at long beats. Both
terms are reported, with the boundary between them.

## A5 — the `dstheld` ideal-rail control ABORTED and was dropped

An ideal-rail control that pins the DEEPEST bank's rail to `dV` was attempted (mode
`dstheld`, both schemes, T = 120). Two problems, both MEASURED:

1. the probe found **no current zero** for the hop into the pinned bank, because a hop into a
   stiff voltage source is not an LC exchange at all. Worked around by opening that switch at
   the zero measured on the corresponding `free` row (its only job in the control is to drain
   the source bank on schedule);
2. with that fix the run still **aborted at t = 198 ps**, the first transfer-gate edge, in
   both schemes (`c_skip_dstheld_T120_dv1200.cir.prn` stops at 1.98e-10 s). This is the same
   class of failure chain3 documented for an under-pinned inductor island.

It was **not pursued**, and the reason is a positive one: the `dataheld` control of A4 answers
the same question (rail-limited vs input-limited) without pinning any rail, and the pMOS
cell floor it implies was independently cross-checked against the committed `lsweep`
cell-floor table. The two aborted rows are left on disk as `ERROR` entries in `rows.json`
rather than deleted.

## A6 — the A6 instrument gate does NOT pass on three rows, and that is a finding

An earlier draft of `RESULTS.json` said A6 passed on every reported row. A full re-extraction
of all 24 rows through one code path showed that was **wrong**. It is corrected in
`RESULTS.json.b2_TOPOLOGY_calibration_MEASURED.instrument_state_A6`, and the correction is
recorded here because the claim had already been written down once.

A6 passes on 19 of 22 measured rows (max |IZ| 0.0252 µA against a 1.0 µA gate, max path
identity 6.6e-05 fJ against 0.02 fJ). It fails on `adj_free_T60_dv1200` (badly: 286 µA,
0.614 fJ), and marginally on `skip_free_T60_dv1200` (2.15 µA) and `skip_free_T105_dv1500`
(1.23 µA against a 1.0 µA gate).

The cause is not the instrument. The true-ZCS probe-then-cut protocol measures each hop's
zero with the later hops idle, which is only valid if a later beat cannot disturb an earlier
hop. An explicit collision check over the schedule shows that at T = 60 ps the ADJACENT
schedule charges and drains the SAME BANK at once (hop 1 charges bank 2 over [200.0, 304.6] ps
while hop 2 drains bank 2 at 260.0 ps), so its switch is forced open far from any zero. The
same check finds NO collision anywhere in the interleaved schedule at the same beat period,
and its interrupted currents are 133–149× smaller. That is the pre-registered
`2T >= t_hop` claim, measured — so the failed gate converted into a result.

No conclusion rests on those three rows: they were already flagged
`boundary_inside_charging_hop`, they are the worst rows in the study, and discarding all
three leaves the verdict unchanged (the remaining 19 rows peak at 36.12% worst-gate settling).
