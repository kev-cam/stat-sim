# qal/fcrit — the functional commit criterion

Replaces the `>= 90 %-settled` **proxy** with a real, receiver-referenced commit
test, then re-scores every committed chain dataset under it.

**A signal is good enough if, at the instant the receiver commits, it is on the
correct side of *that* receiver's *measured* threshold, at *that* receiver's
delivered rail, by at least the noise budget.**

## Order of work (mtimes are the witness)

| file | mtime | what |
|---|---|---|
| `DISK_STATE_BEFORE.txt` | 14:33:44 | disk state + every committed input's sha256, before anything |
| `PRE_REGISTERED.json` | 14:35:08 | the criterion, the budget, the pre-stated flip counts |
| `PRE_REGISTERED.sha256` | 14:35 | `289ae498c527976e9e5f2d3dac2befe333ec7cccac99db9b53a2dc0fc375ce26` |
| `trip_S.cir` | 14:35 | **first deck** |

## Files

| file | what |
|---|---|
| `trip.py`, `trip_S.cir`, `trip_A.cir`, `TRIP.json` | **(a) the threshold** — DC sweep of both receiver cells at 27 delivered rails, 1 mV step |
| `rescore.py` | the criterion: threshold interpolation, commit instant from the waveform, the three scores |
| `run_rescore.py`, `RESCORE.json`, `RESCORE.log` | **(c) the re-score** — every gate of every committed chain deck |
| `analyse.py`, `ANALYSIS.json` | per-dataset tables + **(d) the self-test** against the committed VALUE check |
| `cmos.cir`, `level.py`, `level.cir` | **Phase 2** — the fairness test; CMOS and QAL under the *identical* bar |
| `beat.py`, `BEAT.json`, `BEAT_NEWROWS.json` | the beat measured end to end on the running chain |
| `justify.py`, `JUSTIFY.json`, `INSTANT_SENSITIVITY.json` | the pre-registered justification for the commit instant — **refuted**, and the sensitivity measured instead |
| `ii.py`, `ii2.py`, `II.json`, `II_ATTRIB.json` | **(d) the initiation interval** — `II = H·T` over every hold depth, plus the strict-last-bank sensitivity and the real-receiver-only floor |
| `btk/` | private copy of the committed banktank machinery for the three new beat rows |
| `RESULTS.json` | the record |

Nothing in any committed `qal/` directory was written to. Phase 1 re-simulates
nothing that was already on disk.

## The three scores, so the flip can be attributed

* **S1** — the committed 90 % bar: gate vs **its own** rail at **its own** checkpoint.
* **S2** — threshold only: same instant, same reference rail; only the bar changes.
* **S3** — full functional: **receiver's** measured trip at the **receiver's**
  delivered rail at the instant the **receiver** commits.

S1 and S3 cannot share an instant — the 90 % bar is self-referential and the
functional criterion is receiver-referential. S2 exists to separate the two effects.

## Headline

* **0 rows flip in chain3, skip4, restore5 or pgcell.** Every committed
  "does not compute" verdict survives the correct gate.
* **banktank goes 30 → 57 of 71 rows** and its beat shortens from 200 ps to
  **150 ps** (measured; T=140 fails *inside* the noise budget at 13.1 mV, T=130 fails
  by crossing *after* commit). That is the one configuration that already computed.
* **The fairness test splits.** At the *level* QAL gains more than CMOS
  (2.49× vs 1.74×, advantage 1.41× → 2.03×). At the *beat* QAL gains less
  (1.33× vs 1.81×) and the gap to CMOS widens from 2.12× to 2.89×,
  because a beat is mostly transfer and schedule and neither has a threshold in it.
* Both real failure modes are live: **510** links fail *inside the noise budget*
  and **189** cross the threshold *after* their receiver has committed.
* **The best initiation interval goes 500 → 320 ps** (`H` = 2, `T` = 250 → 160 ps),
  and the verdict survives that framing too: 1.56× QAL against 1.81× CMOS.
  The short beats are bound by the *terminal* bank; on the 24 links with a real
  in-deck receiver both `H` = 2 and `H` = 4 clear down to `T` = 120 ps.
  Scoring the last bank strictly fails *every* row including `T` = 300 ps, so the
  generous treatment is forced, not flattering. `RESULTS.json : K_…`

Corrections carried out of this run are in `RESULTS.json : I_CORRECTIONS`.

## One pre-registered claim of mine failed

I pre-registered that the commit instant is a genuine point of no return and
committed to measuring it. It is not: 499 of 738 receiving rails rise again
after it (worst +757.9 mV) and 3984 gate settling ratios still improve. So the
commit instant is the **end of charge delivery**, not an irreversibility, and I
do not call it one. The sensitivity was measured instead: scoring at the other
defensible instant (the receiving bank's own stage boundary) moves 318 of 5784
links and 2 of 188 rows, and moves them *harsher* — so no flip reported here is
an artefact of a flattering instant. `RESULTS.json : A…b_JUSTIFICATION…`
