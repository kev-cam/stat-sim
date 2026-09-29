# TRACK 1 protocol amendments

Both amendments below were made AFTER the instrument check on the **committed anchor row only**
(qal/swsweep/sw_tg15p_z.cir + .mt0 + .prn, stat-sim c814e52) and **BEFORE any new sweep deck was
generated or run**. No new measurement informed them.

## A1 -- the pre-registered path-identity gate was specified at the wrong checkpoint

Pre-registration G1(iii) said: `|ea_C - esw_C - er_C| <= 0.02 fJ (exact at zero inductor current)`.

MEASURED on the committed anchor mt0, that residual per checkpoint is:

| checkpoint | when | ea - esw - er (fJ) |
|---|---|---|
| A | close + 5 ps | +0.0073 |
| **B** | **the true zero (switch open)** | **-0.00004** |
| C | open + 7 ps | +0.0434 |
| D | open + 495 ps | +0.1142 |

`ea - esw = dE_L + E_R`, so `ea - esw - er = dE_L`, which vanishes **only where the inductor
current is zero** -- checkpoint **B**, not C. At C the interrupted current is still ringing, so the
residual is real physics, not instrument error. The gate as written would have failed a correct
instrument.

**Amended:** the path identity is evaluated at **B**, gate unchanged at 0.02 fJ. It reads
-4e-5 fJ on the committed anchor. The energy *ledger* still cuts at C, exactly as the committed
A2 metric does -- only the identity check moves.

## A2 -- the speed metric: t_hop is NOT the level time; t_valid90 is

The pre-registration made C1 (cell settling >= 90%) a pass/fail **at the open checkpoint** and said
the headline would use it. MEASURED on the committed anchor:

- `V(bkb)` at the open checkpoint = 0.66978 V, 99.1% of its final 0.67589 V -- **the rail arrives
  essentially inside the hop.**
- but the lo-input cell output `o1` at the open checkpoint = 0.54955 V = **82.09%** of the rail.
  The hi-input cells are at 100.1%.

So **the committed, shipped, "all 8 cells settle" optimum row FAILS a 90%-at-open criterion**, at
82.1%. Applying C1(open) as a binary gate would have thrown away the entire sweep, including its
own anchor, and would have measured the wrong thing: the cells lag the rail because the cell pMOS
is barely above Vt at a 0.676 V supply (measured approach time constant ~25 ps after the rail
settles), not because the hop is incomplete.

**Amended:** C1 becomes a *measured time* rather than a pass/fail at a fixed instant. Per point the
harness extracts, from the hop `.prn`:

- `t_rail90` -- time after switch close at which `V(bkb)` first reaches 90% of its final value.
- `t_valid80 / t_valid90 / t_valid95` -- time after switch close at which **all** cell outputs are
  simultaneously within that fraction of the *instantaneous* rail, and stay there (lo-input cells:
  `V(o)/V(bkb)`; hi-input cells: `1 - V(o)/V(bkb)`).
- `t_level = max(t_hop, t_valid90)` -- **the primary speed metric.** A QAL level is not finished
  until the switch has opened at its zero (the hop must complete for the charge to be recovered)
  *and* the outputs are valid (they are the next level's inputs).

MEASURED on the committed anchor: `t_hop` 266.76 ps, `t_rail90` 165.28 ps, `t_valid90` **292.15 ps**,
`t_level` **292.15 ps**. The committed row's own cells were already the binding constraint, by
25 ps, before L was touched.

The pass/fail form of C1 is retained but moved to the settle checkpoint (`C1_settle_end`, the
committed convention, which the anchor passes at 100%), and every row reports the open-checkpoint
percentages as raw data. C2 (rail drain), C3 (swing) and C4 (instrument) are unchanged, and
FUNCTIONAL is now `C1_settle_end AND C2 AND C3 AND C4` with `t_valid90` required to exist (i.e. the
outputs must actually reach 90% of the rail within the run).

**Consequence for the pre-stated comparators.** The pre-registration's "faster" test compared
`t_hop` against 92.8 ps/level and 34.81 ps. Those CMOS numbers are input-change-to-output-valid
quantities, so the like-for-like QAL quantity is `t_level`, not `t_hop`. Both are reported against
both comparators; **the verdict is taken on `t_level`**, which is the stricter, less flattering
choice.
