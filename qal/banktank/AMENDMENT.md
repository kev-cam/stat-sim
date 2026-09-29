# Amendments to `PRE_REGISTERED.json` (sha256 `d343dfb0…`, 21647 B, 2026-09-29 08:45:54 -0700)

Every amendment is recorded here with the measurement or environment fact that
forced it and the mtime proving it preceded the rows it affects.

---

## A0 — environment note, not an amendment (2026-09-29 09:0x)

The box was memory-pressured while the anchors ran (24 of 31 GB resident, 37 of
48 GB swap in use, load average 19.4 on 16 cores, 23 concurrent `g++`/`cc1plus`
from three workflows). Xyce's PyMS/Verilog-A `.so` builder logged

    build_vae_so: full build failed (g++ … vae_PSP103VA_638208eec0843539.so …);
    retrying without zero-valued params

for one of the five device geometries. The retry path drops parameters whose
value is exactly zero, which is numerically equivalent, **but this is precisely
the shell/`.va` cache hazard this campaign has been bitten by before**
(`feedback_pyms_*`, `async_power_anchor.md`). It is therefore not taken on
trust: the instrument check (step b) digit-checks three committed rows against
their committed `.mt0` under this workflow's own cache, and any model
discrepancy would surface there. See `INSTRUMENT_CHECK.json`.

## A1 — ZCS probe protocol: probed once per `(m, dV)`, reused across the beat grid

Pre-registered: "the true current zero is RE-PROBED per L, per m and per hop".
The zeros are probed with the inherited SEQUENTIAL protocol (bank *k*'s zero
measured with banks 1…*k*−1 cut at their own measured zeros, later banks idle;
then the same for the four RETURN zeros with all rises cut) at a reference
schedule `T_probe = 120 ps, H_probe = 4` — and then REUSED across the whole
beat-period grid for that `(m, dV)`.

Justification and its guard: the zero is set by `L`, the tank capacitance and
the rail's own load, none of which is a function of the beat period. The
assumption is not taken on trust — **every measured row carries `IZ` and `IZQ`,
the actual `I(L)` at each commanded open**, and the pre-registered A6 gate
(`|I(L)| ≤ 1 µA`) fails the row if the reused zero did not transfer. Rows that
fail A6 are reported as instrument failures, not as results.

## A2 — the park device is present but held OFF for the whole run

Already stated in the pre-registration (`TOPOLOGY_pre_stated`); restated here
because it is a visible departure from `skip4`, where the park is HELD ON while
a hop is idle. In `skip4`/`chain3` the inductor island floated once the
mandatory source-side cut opened, and the park was what pinned it. Here the
tank is permanently attached to the far end of `L`, so `sw{k}` is pinned at
`V(tnk{k})` through `L + R` at DC and needs no park; turning the park on would
put `tank → L → R → park → gnd` across the tank and ring it down. The device
itself is kept (its capacitance is real and it is part of the committed `tg15p`
triple) with its gate tied to 0 V. `V(tnk{k})` and `V(sw{k})` are printed in
every row so this is checked, not assumed.

## A3 — a SECOND, directly-measured beat metric added BEFORE the first row ran

Forced by a probe measurement, not by a result: the measured rail-raise half
cycle at the primary point is **`t_zcs` = 117.46 / 117.74 / 115.75 / 115.22 ps**
(banks 1–4, `m` = 10, `L` = 15 nH, `dV` = 1.2, full sequential protocol), i.e.
the RAMP ALONE is longer than several beat periods on the pre-registered grid.

The pre-registered boundary rule `bound_k = c_k + T` ("one beat to become
valid", inherited verbatim from chain3/skip4) therefore evaluates bank *k*
**mid-ramp** at every `T < t_zcs`, and fails those rows for a reason that has
nothing to do with the proposal. That rule is KEPT as the pre-registered gate
and its verdict is reported as THE verdict — no criterion is being loosened to
manufacture a pass.

Added alongside it, and reported separately and explicitly as a second metric:

* `data_valid_instant_ps[k]` — MEASURED off the running chain's own waveform:
  the first instant at which ALL 8 gates of bank *k* are ≥ 90 % settled against
  the INSTANTANEOUS rail **and** pattern-correct under the committed guard.
* `steady_state_stage_time_ps` — the differences
  `t_dv(4) − t_dv(3)`, `t_dv(3) − t_dv(2)`, `t_dv(2) − t_dv(1)`.
  In a chain that is actually propagating, this converges to the rate at which
  valid data advances one stage. It is measured DIRECTLY off the running 4-bank
  chain, never composed from parts, and it is the quantity the brief asks for
  when it says "the resulting BEAT PERIOD measured directly".

Both are reported for every row. Where they disagree, both numbers are given
and the disagreement is explained, not resolved in QAL's favour.

## A4 — pre-registered expectation P2 is already in trouble, recorded before the rows

The pre-registration predicted the delivered rail would "rise monotonically with
`m`". The probe rails at the ZCS instant are **0.7343 (m=1) / 0.7072 (m=2) /
0.7656 (m=10) / 0.7905 V (m=20)** — NOT monotonic: `m` = 2 delivers LESS than
`m` = 1. Recorded here, before the sweep, as a miss on my own prediction. The
cause is visible in the same measurement: the pre-registered pre-charge
`V_t0 = dV(m+1)/2m` falls from 1.2 V (m=1) to 0.9 V (m=2) faster than the m=2
tank's extra stiffness repays, and only from `m` ≳ 5 does stiffness dominate.

## A5 — beat-period grid REFINED (points added, none removed)

The pre-registered grid is `T ∈ {45, 60, 75, 90, 120, 160, 300} ps`. Because the
measured ramp is ~117 ps (A3), the interesting region for the pre-registered
strict criterion lies between 120 and 300 ps, where the grid is coarse. **T = 200
and T = 240 ps are ADDED**; nothing is removed and no criterion is changed. This
can only locate the earliest correct beat period more precisely — it cannot
convert a failing row into a passing one.

## A6 — HARNESS DEFECT found by measurement and FIXED BEFORE the sweep: the park must be TANK-referenced

**What was wrong.** A2 above argued the park device could be held OFF because the
tank pins `sw{k}` through `L + R` at DC. That reasoning is wrong, and the first
measured row proved it: the tank pins `sw` at DC, but the **inductor sits between
them and carries its MAXIMUM voltage exactly at the ZCS instant** (at the current
zero the two capacitor voltages are at their extremes, so
`V_L = V(tnk) − V(rail) = 0.472 − 0.880 = −0.408 V`). Opening the transfer gate
there leaves `sw{k}` floating with only parasitic capacitance across a 0.41 V
inductor.

**The measurement (row `c_m10_T120_H4_dv1200_free`, now quarantined in
`pre_A6/`).** After bank 1's gate opened at 317.46 ps the island rang, hard and
undamped, for the whole hold window:

| t (ps) | I(L1) (µA) | V(sw1) | V(tnk1) |
|---|---|---|---|
| 320.3 | −80.0 | 0.9483 | 0.4726 |
| 350.6 | **−718.1** | 0.5813 | 0.5123 |
| 391.3 | +60.4 | 0.0931 | 0.5640 |
| 421.8 | **+700.6** | 0.4552 | 0.5257 |
| 532.6 | −1.0 | 0.1115 | 0.5620 |
| 642.8 | −653.5 | 0.4776 | 0.5233 |

≈7 GHz, ±700 µA, `V(sw1)` swinging 0.09 → 0.95 V and the tank oscillating
0.472 ↔ 0.564 V, with **no decay over 350 ps**. `½·L·I²` at the peak is 3.9 fJ —
the same order as the hop itself — so every energy number and every tank-droop
number in such a row is contaminated. This is the same pathology the campaign's
own SIM DIRECTIVE names ("ideal/unloaded switching causes unwanted LC ringing")
and the reason the committed decks park the floating node at all.

**The fix, and why it is not the committed one.** The committed park ties `sw` to
GROUND. That is right for a deck whose source cap is already drained to ~0.13 V,
but here it would put a charged tank across `tank → L → R → park → gnd` and ring
it down — dumping the very energy the topology exists to keep. The park is
therefore **referenced to the bank's own tank**:

    XPK{k} sw{k} pk{k} tnk{k} tnk{k} sg13_lv_nmos w=2u l=0.13u

closed whenever the transfer gate is open (the committed anti-phase, same 2 ps
edges). It shorts `L + R` into a loop across the tank, so the inductor voltage is
clamped to ≈0 and `sw{k}` is pinned at `V(tnk{k})`; it is a LOOP, not a path to
ground, so it cannot drain the tank. Its gate drive is now a real PWL source and
its energy is added to the `egt` integrator, so the fix is costed, not free.

**Consequence, applied honestly.** Every deck run before this fix is invalidated
and has been moved to `pre_A6/` rather than deleted — including all ZCS probes
(each `rise1` probe is technically unaffected, because in it no earlier bank ever
opens, but they are re-run anyway so that one protocol produced every number).
Every probe and every row in the reported sweep was produced AFTER this fix.

## A7 — A1's reuse assumption REFUTED by measurement; probes made SCHEDULE-MATCHED

A1 reused one set of ZCS zeros per `(m, dV)` across the whole beat grid, on the
argument that the zero is set by `L`, the tank and the rail's load, none of which
is a function of `T` — with the A6 `|I(L)| ≤ 1 µA` gate as its guard. **The guard
fired.** Row `m = 10, T = 200, H = 4` with `T = 120`-probed zeros:

| bank | I(L) at commanded open (µA) |
|---|---|
| 1 | **−0.0076** |
| 2 | +8.83 |
| 3 | +15.32 |
| 4 | +27.43 |

Bank 1 — the only bank whose gate inputs are ideal DC sources, hence
schedule-independent — is still at the sub-nanoamp level, which identifies the
mechanism exactly: a bank's INPUT levels during its own ramp depend on the beat
period, so its gate loading does, so its zero does. The argument in A1 was wrong
and its guard caught it.

**Fix**: `bt.py probeT <m> <dv> <T> <H>` runs the same sequential protocol at the
ROW'S OWN `T` and `H`, writing `zeros_m*_dv*_T*_H*.json`; the driver prefers a
schedule-matched zeros file when one exists and falls back to the reference set
otherwise. Every row is reported with its own measured `IZ`/`IZQ` so the reader
can see which set it used and how clean it was.

**Physical size of the error, stated so it is not over- or under-sold**: 27.4 µA
against a peak of ~814 µA is a ~1.25 ps timing error, and the inductor energy it
strands is `½·L·I² = 0.0055 fJ` — about 0.05 % of a hop. So the reused-zero rows
are not physically wrong; they fail a deliberately strict INSTRUMENT gate. The
decisive rows are nevertheless re-run schedule-matched, and both versions are
reported so the effect on the verdict can be seen rather than asserted.

### A7a — self-correction: the first schedule-matched probe run was a no-op

The first `probeT` implementation still passed the REFERENCE schedule into the
deck builder, so its "schedule-matched" zeros came out byte-identical to the
reference set at every `T` (`dtzr = dtzq = 0.000 ps` at T = 160/180/200/240).
That identity is what exposed the bug — a genuinely schedule-matched probe cannot
be exactly equal at four different beat periods when the reused zeros were
already known to miss by 1.25 ps. Fixed (`deck(m, T or TPROBE, H or HPROBE, …)`,
verified on the generated netlist: bank 2 now closes at 400 ps at `T` = 200, not
320 ps), the stale outputs deleted, and the probes re-run.

## A8 — metering defect in the COSTED-RECHARGE integrator, found and fixed

The `topup` variant metered the recharge supply with
`BXetu 0 xetu I={ -V(vtk)*I(VTK) }`, where `vtk` is the node of the independent
source `VTK`. The charge integrator on the same source read a sensible
**121.8 fC** delivered into the four tanks (independently corroborated: the tanks
each rose 0.5611 → 0.6388 V on a linear 359.79 fF cap ≈ 28 fC each, ≈ 112 fC
total), but the ENERGY integrator read **−0.157 fJ** — i.e. an effective supply
voltage of about −1.3 mV instead of 0.66 V. `V(vtk)` was not resolving to the
node under a name shared with the device. The node is renamed `vrch` and the
affected rows re-run. Reported alongside is the same number computed WITHOUT any
integrator, from two independently measured quantities — the charge through the
source and the tank-voltage change on a known linear capacitance — so the costed
recharge does not rest on the integrator that was just found wrong.
