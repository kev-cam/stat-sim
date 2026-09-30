# qal/eye/p2 — AMENDMENTS (PHASE 2)

Every entry names the measurement or environment fact that forced it. Where an
amendment postdates rows it affected, that is said explicitly. Pre-registration:
`PRE_REGISTERED_P2.json`, sha256 `b333ab252ba09c61ef846c16649e445b91b55949c56c5d1233a9daccbdc53471`,
24452 B, mtime 2026-09-29 21:46:54 −0700, written when `qal/eye/p2/` held only
`DISK_STATE_BEFORE.txt` (21:44:29).

---

## A1 — A BUG IN MY OWN INSTRUMENT CHECK, self-caught before any deck ran

IC-P2-4 read the CMOS anchors with `cmp_.get("CMOS_level_at_2fF_ps")` and
returned **FAIL**, overall verdict `INSTRUMENT PROBLEM`. The keys are **nested**
in `qal/sha256/p2/COMPARISON.json`, not top-level — a bug in *my reader*, not a
missing anchor. Fixed by using the same recursive `find()` IC-P2-3 already used;
the anchors then reproduced exactly (57.143 / 94.174). **Effect on results:
none** — this ran before any simulation. Recorded because a green instrument
check that was red five minutes earlier is exactly the kind of thing that should
not be quietly overwritten.

## A2 — `p2eye` crashed on the ORACLE set: the patterns do not share a time grid

`IndexError: array index out of range`. On the **calibrated** schedule every
pattern shares one zeros vector, so `tend = max(ro) + TAIL` — and hence the grid
length — is identical. On Phase 1's **oracle** schedule each pattern carries its
*own* zeros, so `tend` differs per pattern and the grids have different lengths.
My first version sized the intersection off the *first* pattern. Fixed by
truncating to the **shortest** grid, which is the only correct intersection
domain, and the truncation is now reported in every output
(`intersection_domain.truncated_to_common_span`). For the T = 200 oracle set the
common span is 2240.9 ps. **Effect:** none on any published number — the crash
happened before any oracle number existed, and the fix was verified by the
oracle eye then reproducing Phase 1 exactly (128.599 / 129.641 / 129.382 ps).

## A3 — THREE ROWS WERE KILLED MID-SIMULATION AND THE CAUSE IS NOT CONFIRMED

`T200_H4/{P0,P1,P2}` launched 22:00:30 and all three Xyce processes terminated
together at ~22:01, ~70 s in: `.prn` truncated at t = 1.035 ns / 11 270 rows, **no
`.mt0`, no `End of Xyce(TM) Simulation` marker**, and `p2run.py` exited without
writing `sched.json`. A good row (W3) has 23 951 rows and the end marker.

I **cannot confirm the cause.** `dmesg` is not readable in this container and
`journalctl` returned nothing, so I have no OOM record. The circumstantial
context: the box was at load 16 with 13 foreign Xyce, **8.1 GB of swap in use**,
and my first (crashing) oracle extraction was running at that moment. I state
this as unexplained rather than assert an OOM.

**Remedy:** the three directories were deleted and the rows re-run alone, all
three completing normally (185.9 / 199.8 / 215.2 s). **Effect on results: none** —
no truncated `.prn` ever reached an extraction, because the missing `sched.json`
made those patterns invisible to `p2eye`, which reports `patterns_missing`. The
failure mode was fail-closed, but only by luck of the file-writing order, and
that is worth saying.

## A4 — the calibration row's `sched.json` lacked keys `eyecalc` needs

`do_calib` wrote `prn` but not `mt0`, and `eyecalc.per_pattern` needs `mt0` for
the EYE2 fixed decision level (`parse_mt0` → `VR{k+1}B{k+1}`). Caught as a
`KeyError: 'mt0'` on the first T = 180/160/150 extraction. Fixed by deriving the
`.mt0` path from the `.prn` path and verifying the file exists. **Effect:** none
— no number was produced before the fix.

## A5 — **F2 TRIGGERED**: below T ≈ 150 ps the calibration probe fails its own A6 gate

Pre-registered F2 said that if A6 fails on the *calibration* pattern's own probe,
the schedule is invalid. It **does** fail, at T = 145 and T = 140:

| T (ps) | worst RISE \|I(L)\| (µA) | worst RETURN \|I(L)\| (µA) | A6 ≤ 1 µA |
|---|---|---|---|
| 200 | 0.0081 | 0.0121 | **pass** |
| 180 | 0.0060 | 0.0126 | **pass** |
| 160 | 0.0095 | 0.0078 | **pass** |
| 150 | 0.0070 | 0.2682 | **pass** |
| 145 | 0.0052 | **1.4023** | **FAIL** |
| 140 | 0.0037 | **2.9486** | **FAIL** |

The failures are **exclusively on the RETURN zeros** (`izq2`, `izq3`); the
rail-raise zeros stay at ≤ 0.0095 µA at *every* beat. There is a hard knee
between 150 and 145 ps.

**How I handled it, and the limit it exposes.** The setup budget depends on the
**rail-raise** zero, which is what sets `t_valid`; the return zero sets the
initiation interval and the late edge. So the T = 145/140 `t_valid` numbers stand
— but I do **not** present those beats as validated operating points. Instead
this is reported as a **separate constraint on the beat**: at dV = 1.65 V the
committed sequential return-ZCS protocol stops locating the return zero to the
inherited 1 µA tolerance below T ≈ 150 ps. That constraint may bind before the
timing budget does, and it is stated as its own finding in `A6_VS_BEAT.json`
rather than folded into the budget. I did **not** re-probe with a modified
protocol, because changing the probe protocol mid-study would break comparability
with Phase 1 and with the committed rows.

## A6 — a key-name mismatch in my own A6-vs-beat script, self-caught

Wrote `worst_RISE_uA` into the dict and read `r['worst_RISE']` out of it;
`KeyError`. Also T = 200's A6 record came from Phase 1's `EYE.json` and carries
only the aggregate, so per-bank rise/return currents had to be taken from that
file's `_patterns.P3.IZ_uA` / `IZQ_uA`. Both fixed. **Effect:** none — the table
above is the first and only published version.

## A7 — MY PRE-REGISTERED EY1 HAD THE **SIGN** WRONG, AND I ADDED A CONTROL THAT WAS NOT PRE-REGISTERED

EY1 predicted the calibrated eye would open **5–25 ps LATER** than Phase 1's
oracle eye. Measured: it opens **2.49 / 3.41 / 2.78 ps EARLIER** (banks 1/2/3).

Because EYE2's decision level is taken from **each pattern's own `.mt0`**, a
lower delivered rail would lower the trip and manufacture a spurious "earlier"
opening. That would have been a reference artifact of exactly the kind Phase 1's
E3 was written about. **This control was not pre-registered — I added it because
the measurement surprised me**, and it is an amendment, not foresight.

The control: recompute the calibrated margin curves against the **oracle's**
fixed trip, frozen per (pattern, bank), so only the driver can move the edge.

| bank | calibrated, oracle trip frozen | driver part | reference part |
|---|---|---|---|
| 1 | 126.1090 ps | **−2.4900 ps** | +0.0230 ps |
| 2 | 126.2364 ps | **−3.4050 ps** | +0.0266 ps |
| 3 | 126.6052 ps | **−2.7768 ps** | +0.0288 ps |

**≈99 % of the shift is the driver, ≈1 % is the decision level.** The earlier
opening is real. EY1 is REFUTED on sign and magnitude.

## A8 — I CHANGED HOW THE INHERITED 61.6 ps TERM IS CHARGED, from extrapolation to direct measurement

`PRE_REGISTERED_P2.json` B1 said R2 would be charged by transferring 61.612 ps
"through the MEASURED sensitivity" dΔ/d(schedule error). Once A7 showed Δ is
**negative**, that sensitivity is negative and transferring 61.612 ps through it
would have produced a large spurious *credit*. That would have been absurd.

**Replaced with a direct measurement**: the schedule was deliberately mis-timed
by the inherited magnitude on this arrangement (a p-p spread S seen by a
centre-calibrated timer is at most ±S/2, so ±30.806 ps), and the eye re-measured.
Also run at ±10.62 ps (R3, the fractional reading) and +61.612 ps. This is a
strict improvement — it converts an untransferable inherited number into a
measurement at this operating point — but it is a **change of method after
seeing data** and is recorded as such.

It also changed the verdict's direction: the **early** (negative) offset is the
binding limb, and it is the *only* term that moved the answer materially.

## A9 — I DECLINED TO BANK A MEASURED CREDIT, and that is a judgment call made after seeing the sign

The calibrated schedule's 2.5–3.4 ps *earlier* opening is a measured credit. I
charge U1 = **0**, not −3.4 ps. Reasons: it is an energy-for-time trade
(734–1042 µA of off-zero switching current at the commanded open, against a
1.17–1.31 mA peak), measured at one calibration choice, and banking a credit for
a timer error *helping* is fragile. A reader who disagrees can subtract 3.4 ps
from the headline; the number is in `BUDGET.json`. Stated because the choice was
made **after** the sign was known.

## A10 — H = 2 is not measured at this swing by this study

The initiation interval `II = H·T + tzq` multiplies the beat by H, so H dominates
the throughput verdict, and the crossover D swings from 2 to 8 across H and the
II convention. `qal/fcrit` MEASURED that both H = 2 and H = 4 clear down to
T = 120 ps on the 24 links with a real in-deck receiver, and that the best
initiation interval is H = 2, T = 160 ps — **but at dV = 1.2 V**. This study
attempted an H = 2 calibration probe at T = 145, dV = 1.65 V; its disposition is
recorded in `RESULTS_P2.md`. Where H = 2 is quoted from fcrit it is labelled
EVIDENCE FROM ELSEWHERE AT A DIFFERENT SWING, never a measurement of this point.

## A11 — the II convention differs from the campaign's and both are reported

`qal/fcrit` quotes "best initiation interval 320 ps (H = 2, T = 160 ps)", i.e.
`II = H·T`. That **omits the return**: a bank cannot accept a new datum until its
return switch has opened at its own zero, `ro_k = c_k + H·T + tzq`, and the
MEASURED worst `tzq` here is 153.54 ps. I report **both** `H·T` (the campaign's
convention, so my numbers can be compared to theirs) and `H·T + tzq` (the
physically correct one), and the headline uses the strict form. This is not a
correction of fcrit — its framing may suit its own question — but the two must
not be mixed.
