# Amendments to `qal/fastwave/PRE_REGISTERED.json`

Pre-registration: sha256 `c23021e9e97089bf60826b118ec44ddaa874dd1f51049df1ae226c062cc05638`,
20450 B, written **2026-09-29 19:50:27 -0700**, after `DISK_STATE_BEFORE.txt`
(19:46:26) and before any deck in this directory.

Every amendment below records the measurement or environment fact that forced it
and the mtime proving it preceded the rows it affects. **No sweep row existed in
this directory when A1–A3 were written** — the only decks on disk were the two
byte-identical committed anchors (`F1_cmos_anchor.cir`, `F2_hop_anchor.cir`), the
five geometry-warming decks, and one bank-capacitance calibration deck
(`cb_n2.cir`, 20:34).

---

## A0 — environment note, not an amendment

The box is shared and loaded: load average 7.4–8.0 on 16 cores, 18.2 of 31.8 GB
resident and 8 of 48 GB swap in use, with a sibling QAL run (`qal/widebank/`,
`PRE_REGISTERED.json` mtime 19:21:28) and other workflows running concurrently.
This inflates every wall-clock figure quoted in this directory and is the reason
the PyMS geometry builds below cost 400–500 s each rather than the ~140 s the
campaign record suggests. It affects no electrical result.

**MEASURED, and the reason `warm.py` exists at all:** in this Xyce build the
PyMS/Verilog-A `.so` is built **per (card TYPE, W, L) geometry** — confirmed by
reading the cache's own `.params` files, which carry `TYPE=1/-1`, `L=1.3e-07`
and a distinct `W=` per artefact. The build costs ~400–500 s of the
"Instantiate" phase while the transient solve itself is 1.4 s (F1: 5 m 42 s
wall, of which 5 m 27 s Instantiate). A parallel sweep worker hitting a cold
geometry would therefore blow the 4-minute rule **and** race other workers on
the shared cache — the exact `.va`-cache hazard this campaign has been bitten by
before. Every geometry is pre-warmed in its own private cache and merged; the
`.so` filename is a parameter hash, so the same geometry always yields the same
filename and the merge is a copy, not a race. `fw.run()` writes a WARNING to
stderr if any sweep deck ever triggers a build.

---

## A1 — THE BANK VECTOR SET, forced by a measurement, changed BEFORE any sweep row

**What the pre-registration said.** Section C chose the pass-gate TG-XOR cell and
`fw.VEC` cycled the four XOR input vectors over the bank in the order
`[(0,0), (1,0), (0,1), (1,1)]`, justified in the code comment as giving the
smallest bank "both logic values AND both transmission-gate paths".

**That justification was WRONG, and the first calibration deck proved it.**
`cb_n2.cir.prn` (N = 2, the rail ramped 0 → 1.65 V over 4 ns) reads:

| V(bkb) rail | V(y0) | V(y1) |
|---|---|---|
| 0.0000 | 0.00009 | **0.98440** |
| 0.3185 | 0.00770 | **1.02375** |
| 0.9785 | 0.00061 | **1.20058** |

`y1` is at 0.984 V **while its own bank rail is at ZERO**, and ends at 1.2006 V
= `VINHI`. It is not being driven by the rail at all.

**The mechanism, which the committed record already names.** `qal/pgcell/pg.py`
documents that a TG-XOR2 has two structurally different paths: with the select
`B` on one value the conducting transmission gate passes `Abar` — the input
inverter's output, which IS on the bank rail (**RESTORED**); with `B` on the
other value it passes `A` — the raw input, which is not (**TRANSPARENT**). In
`xor_form` the taps are exchanged, so:

* `B = 0` → TG1 conducts → passes `A` → **TRANSPARENT**, output rail-independent
* `B = 1` → TG2 conducts → passes `Abar` → **RESTORED**, output follows the rail

The pre-registered order put `(0,0)` and `(1,0)` — **both `B = 0`, both
TRANSPARENT** — in the N = 2 bank. An N = 2 bank built that way contains no cell
that waits for the rail, so it would have reported a near-zero settle time and a
flatteringly short level time, as an artefact of my vector choice and not as
physics. N = 2 is the corner the whole run is aimed at, so this would have
corrupted the headline.

**The fix, applied before any sweep row ran.** `fw.VEC` is reordered so the
RESTORED pair comes first and the binding cell is present at every N:

```
VEC = [(0, 1),   # RESTORED,    want 1  -- THE BINDING CELL: must follow the rail UP
       (1, 1),   # RESTORED,    want 0
       (1, 0),   # TRANSPARENT, want 1
       (0, 0)]   # TRANSPARENT, want 0
```

* N = 2 → both cells RESTORED, one wanting 1 and one wanting 0. This is the
  **harshest** admissible 2-cell bank: it contains the binding rail-following
  cell and no free-riding transparent cell. It cannot flatter the corner.
* N = 4, 8, 16 → all four vectors present in equal proportion, which is the
  data-representative mix.

The amendment makes the small-N rows HARSHER, not easier, and it is applied to
every N identically.

---

## A2 — the 90 %-of-rail settling bar CANNOT be the gate for a pass-gate bank

**Forced by the same measurement.** A TRANSPARENT cell's output is pinned near
`VINHI`, not near the rail. Its ratio `V(y)/V(bkb)` is therefore a function of
the *delivered rail* and nothing else: at a delivered rail of 1.05 V a correct
transparent HIGH reads 94 % settled and passes; at 1.35 V the **same correct
instantaneous output** reads 89 % and fails. The bar would fail a cell that is
logically perfect and has no delay at all, and it would do so *harder* the
better the transfer is — i.e. it is anti-correlated with the thing the run is
optimising.

**This is not a new discovery and the amendment is not an invention of this run.**
`qal/fcrit` (committed `0ec8de5`) already adjudicated exactly this: "the
90 %-settled bar WAS the wrong discriminator", and replaced it with a
receiver-referenced FUNCTIONAL criterion — a signal is good enough if, at the
instant the receiver commits, it is on the correct side of *that* receiver's
*measured* threshold, at *that* receiver's *delivered* rail, by the noise budget
`NB = 3σ = 19.323 mV`. `qal/fcrit` also MEASURED that the trip fraction is not a
constant (0.7281 at 0.20 V falling to 0.5179 at 1.50 V), so the threshold is
interpolated at each row's own delivered rail from `qal/fcrit/TRIP.json` and
never assumed.

**Amended:** pre-registered gate **K4** is evaluated on the FUNCTIONAL criterion
(`value_check` — every cell on the correct side of its receiver's measured trip
at the delivered rail, by NB) instead of on the 90 %-of-instantaneous-rail bar.

**Nothing is dropped and nothing is loosened by omission.** Every row still
carries, and RESULTS.json still reports:

* `settling_end_pct` per cell and `settling_end_min_pct` — the inherited 90 %
  reading, so the committed comparison is still available;
* `t_valid80/90/95_ps` — the inherited lsweep A2 times;
* `t_level_ps` = `max(t_hop, t_valid90)` — the inherited primary metric;
* `t_commit_fcrit_ps` and `t_level_fcrit_ps` — the functional times.

**Both level times are reported on every row and the frontier is stated under
both.** Where they disagree the disagreement is reported, not resolved in QAL's
favour. Each cell is additionally labelled `TRANSPARENT` or `RESTORED` so a
reader can see which class set the row's time, and the `RESTORED`-only settle
time is reported separately — that number is not affected by this amendment at
all, and it is the one the cascade depends on.

---

## A3 — the transfer-gate park device width is FIXED at 1 um, not scaled with W

The inherited convention (`qal/lsweep/lsw.py widths`) scales the park device as
`W/15`, giving park widths 0.5 / 1 / 2 / 4 / 8 / 16 um across this run's W
ladder — five additional PSP103 geometries at ~450 s of build each (A0), for a
device that is held OFF during the hop and only pins the floating `sw` node
afterwards. Its width therefore cannot affect `t_hop`, `Q`, `VBEND` or
`VA_open`, all of which are measured at or before the switch-open instant.

**Fixed at `PARK_W = 1.0 um` for every W**, which is the committed `tg15p`
value, so the `W = 15 um` column remains the committed triple exactly. The cost
is that the park's own capacitance no longer scales with the switch it parks;
that capacitance sits on `sw`, is ~0.1 fF, and is present identically in every
row of the W ladder, so it cannot bias the widening comparison this run is
making. Declared here rather than left as an undocumented difference from the
inherited convention.

---

## A4 — METERING DEFECT found by measurement and FIXED BEFORE the first sweep row

**What was wrong.** The bank-capacitance calibration deck metered the charge the
bank draws from its rail by KCL over the bank's non-rail terminals,
`I(VMG) + Σ(I(VA_i) + I(VB_i))` — the form `qal/lsweep/lsw.py::_sup_expr` uses,
where it is correct because a static inverter's only non-rail terminals are its
metered ground and its gate input.

**The measurement that caught it.** The first calibration run returned
capacitances that are not physics: 31.9 / 216.4 / 430.3 / 860.6 fF for
N = 2/4/8/16 — a **6.8× jump for a 2× cell count** between N = 2 and N = 4, and
430 fF for eight cells whose rail-connected devices are sixteen 1.12 µm pMOS.
The implied `dQ/dV` was also *constant* at ~290 fF from 0.6 V to 1.65 V, i.e. a
constant current, which is a DC path and not a capacitance.

**Diagnosed by measurement, not by argument** (`diag_n4.cir`, one deck with a
per-source integrator on every terminal of every cell):

| V(bkb) | Q at the RAIL source | Q to ground | Qa0 | Qa1 | **Qa2** | Qa3 |
|---|---|---|---|---|---|---|
| 0.641 | 25.81 | 22.95 | 0.89 | 1.10 | **31.00** | 1.47 |
| 1.301 | 66.95 | 57.27 | 3.20 | 1.65 | **176.00** | 5.05 |

Cell 2 — vector (1,0), the TRANSPARENT want-1 cell — draws **176 fC from its own
A input source** while every other input draws 1.6–5 fC, and **none of it comes
from the rail**. The KCL form folded that current into the "rail" charge.

**The mechanism, and it is REAL PHYSICS, not a harness artefact.** A
transmission-gate pair is selected by complementary signals `b` and `bb`, and
`bb` is generated by an inverter **on the bank rail**. On a QAL rail that starts
at ZERO, `bb` starts at zero too — so for cell (1,0) *both* TG pMOS gates (`b`
= 0 and `bb` ≈ 0) are low, *both* pMOS devices conduct, and the mux is not
selecting: there is a static path
`VA2 → TG1 pMOS → y2 → TG2 pMOS → ab2 → IA nMOS → gcell`.
The node waveforms show it directly — at t = 0, `ab2` sits at **0.096 V** instead
of 0 V (it is being held up through the conducting TG2), and `y2` at 0.984 V. It
extinguishes as the rail rises and separates the selects: by V(bkb) = 1.30 V,
`bb2` = 1.298 V, TG2's pMOS has `Vgs` = +0.097 V and is off.

**The fix.** The rail charge is metered **at the rail source**, `-I(VS)`. The
corrected capacitances are physics: **29.43 / 52.77 / 105.54 / 211.07 fF** for
N = 2/4/8/16, i.e. affine in N at **13.19 fF per cell with an offset of
essentially zero** (N = 2 sits 3.0 fF above 2 × 13.19 because it is the
all-RESTORED bank, whose rail-driven output loads are a larger fraction of it —
the harsher bank, per A1).

**Scope of the defect, stated exactly.** It affected the **calibration stage
only**. Every pre-registered gate and every speed number in the sweep is metered
on the TRANSFER PATH — `qlt` = ∫I(LT), `ea`, `eb`, `esw`, `er` — never through
the bank's terminals, so no sweep row was ever exposed to it. The contaminated
KCL integrator is RETAINED in both decks and reported as
`Q_KCL_contaminated_at_dV_fC` / `crowbar_excess_at_dV_fC` precisely so the size
of the crowbar is visible rather than hidden. It gates nothing.

**And it is a finding against my own pre-registered cell justification.**
`PRE_REGISTERED.json` C.why_4 argued the TG-XOR cell is chosen partly because
its data path never touches the rail, so it is light on the rail. That is
confirmed (13.19 fF/cell). But the cell is **not free**: while the rail is below
the level that separates its select signals it SHORTS ITS TWO DATA INPUTS
TOGETHER, and the measured cost is **~67 fC per transparent want-1 cell over a
4 ns ramp** (crowbar excess 4.1 / 270 / 536 / 1072 fC at N = 2/4/8/16 — note
N = 2 has no transparent cell and therefore almost none of it). In Phase 1 that
current is supplied by an IDEAL INPUT SOURCE, so it is a **BOOKING THAT HIDES A
COST**: in a real chain it would be drawn out of the PREDECESSOR bank's outputs
and would degrade the very levels the cascade depends on. Energy gates nothing
in this run so it does not move the beat, but it is a real strike against the
pass-gate cell that `qal/pgcell` did not surface, and Phase 2 must pay it.

---

## A5 — the ledger is read from the WAVEFORM, not the `.mt0`

Found by the pre-registered K5 instrument gate FAILING on the first sweep point
and then chased to its cause rather than being loosened.

**What the gate saw.** `|ea - esw - er|` at the current zero read **0.0935 fJ**
against a 0.02 fJ gate, while the same deck's `IZ` read **0.0005 µA** — i.e. the
inductor current at the commanded open was essentially zero, so the true residual
`½·L·I²` is 7.5e-13 fJ. The two readings are irreconcilable, so one of them is
an instrument.

**The cause, read out of the raw `.mt0`.** A 1 F integrator shunted by the
committed 0.01 Ω resistor sits at a DC operating point `V = R·I(t=0)`, and this
deck has 41.2 nA of leakage through the transfer path at `t = 0`. The `ea` and
`esw` integrators therefore carry a **t = 0 pedestal of 6.8019e-10** against a
**38 fJ** signal — a ratio of 1.8e4. The `.mt0` prints 7 significant digits, so
after the campaign's mandatory pedestal subtraction its absolute resolution is
~0.1 fJ. The path identity is a difference of two nearly-equal pedestal-heavy
numbers, so that quantisation destroys it. The `.prn`, at 9 significant digits,
gives **0.00050414 fJ** — 40× inside the gate.

**The fix.** Every pedestal-sensitive quantity (`qlt`, `ea`, `eb`, `esw`, `er`,
and hence `VA_open`, `R_on_eff`, `Q`, the closures and the identity) is read from
the WAVEFORM at full `.prn` precision. The `.mt0` is still used, and still
reported per row as `ledger_mt0` and `mt0_vs_waveform_ea_pct`, for the quantities
that have no pedestal — `VBEND`, `VBOPEN`, `VAEND`, `VBPK`, `IPK`, `IZ` are node
voltages and branch currents, not integrals. **The gate was not relaxed**: it is
still 0.02 fJ, and it now PASSES on a correct reading rather than failing on a
quantisation.

---

## A6 — the delivered RAIL and the delivered LOGIC LEVEL are different quantities

**Forced by a measurement.** At the first sweep point the rail PEAKS at
`VBPK = 1.3257 V` — comfortably above the 0.9642 V level-restoring floor — and
then falls to `VBEND = 0.8830 V` by the end of the settle window. That is a
33 % decline, and whether the row is "complete" appears to depend entirely on
when you look.

**Attributed by measurement, not by argument** (`diag_hop.cir`, one deck with a
per-terminal integrator on every source in the bank). Between the rail peak and
the tail, 10.3 fC leaves the rail node, and it is accounted for:

| destination | charge |
|---|---|
| the bank's internal nodes, via the metered ground | +4.34 fC |
| back into the `vhi` n-well supply | +4.15 fC |
| onto the output load `y0` (2 fF × 0.636 V) | +1.27 fC |
| **total** | **≈ 9.8 fC of the 10.3 fC** |

So the decline is **charge redistribution, not leakage**: the bank's
quasi-static rail capacitance (29.43 fF at N = 2, measured in A4) understates
the charge the bank ultimately absorbs, because its internal nodes `ab`, `bb`
and `y` cannot follow a ~36 ps hop and go on drawing from the rail for another
100–200 ps. The output `y0` and the rail converge: 0.8818 V and 0.8830 V.

**What is reported, and what gates.** The pre-registered gates K1 and K2 are on
`VBEND`, the tail rail, and they are evaluated **exactly as written** — that is
the verdict. Alongside them every row now carries the same completeness question
asked at the two other defensible instants, so the verdict can be seen NOT to
depend on the choice:

* `K1_on_PEAK_rail_most_generous` — the most generous reading available;
* `K1_on_DELIVERED_LEVEL_strictest` — the minimum over want-1 cells of `V(y)` at
  the instant the receiver commits, which is the level a CASCADE is actually
  handed, and the strictest form;
* `V_hi_min_at_tail`, `V_lo_max_at_tail`, and the rail at each instant.

The three readings bracket the verdict rather than replacing it.

---

## A7 — the N axis was CONFOUNDED with the bank's data mix; a control was added

**Forced by the first sweep's own numbers.** At W = 15 µm, L = 15 nH the
delivered rail went 0.9359 / 0.9709 / 0.9504 / 0.8894 V at N = 2/4/8/16 —
non-monotonic, and *better* at N = 4 than at N = 2, which contradicts the
pre-registered mechanism.

**The confound.** Per A1 the data mix cycles all four XOR vectors, so an N = 2
bank is **100 % RESTORED** while every N ≥ 4 bank is only **50 % RESTORED**. A
TRANSPARENT cell does not load the rail with an output load at all, so it is a
free rider that *raises* the delivered rail. The N axis and the mix axis were
moving together.

**The control.** `fw.MIX = "restored"` builds banks from the two RESTORED vectors
only, so N can be swept at a FIXED 100 %-restored mix. MEASURED at W = 15 µm,
L = 15 nH: `VBEND` = 0.9359 / 0.8807 / 0.8492 / 0.7917 V at N = 2/4/8/16 —
**monotonically decreasing in N**, which is the pre-registered mechanism and the
opposite of what the confounded comparison showed. Both series are reported.

---

## A8 — convergence: a stalled deck is retried with a FINER timestep, nothing else

Nine of the first sixty-eight points stalled at exactly `t = 50.000 ps`, the
transfer-gate close — all large-bank/wide-switch combinations. Refining the
timestep 4× converges; so does relaxing `RELTOL` from 1e-6 to 1e-4, and the two
agree to ≤ 1.3e-4 relative on every headline (`try_s4.cir` vs
`try_reltol4.cir`). **The finer step is the one used**, because it leaves the
committed `.OPTIONS` tolerances untouched and is strictly MORE accurate. `run()`
retries at 4× and then 16×, and a deck that still stalls is reported as an
**omitted point with its reason** — never estimated. Sixteen points never
converged and are listed by name in `RESULTS.json : C_THE_SWEEP`.

A consequence, reported rather than hidden: two rows (`sg2174_n4_L3_W30`,
`sg2400_n4_L3_W30`) fail K5 on the `|IZ| ≤ 1 µA` sub-gate at 1.08 and 1.25 µA,
because their PROBE ran at `div = 1` while their HOP deck was retried at
`div = 4`, so the zero was located on a coarser grid than the deck that used it.
The stranded inductor energy is `½·L·I² = 2.3e-6 fJ`, so these rows are not
physically wrong — they fail a deliberately strict INSTRUMENT gate, the
mechanism is identified, and neither row is feasible on the physics gates
anyway, so the frontier does not move.

---

## A9 — A CONTAMINATION BUG I INTRODUCED, found by audit and fully re-run

**What was wrong.** `VGH` and `MIX` are module globals read by the deck builders,
and `drive.py` runs points in a `ProcessPoolExecutor` **whose worker processes
are reused between tasks**. `fw.point()` defaulted `vgh=None` and assigned the
global only `if vgh is not None` — so a point that did not name a gate drive
**inherited the previous point's gate drive from the same worker**.

**What it corrupted.** Eight rows in the W-ladder completion group (`n4_L15_W7p5`
/ `W30` / `W120` / `W240` and `n16_L15_W7p5` / `W30` / `W120` / `W240`) were
built at **VHI = 2.4 V instead of the committed 1.5 V**. One of them,
`n4_L15_W30`, appeared as the ONLY feasible row at the committed gate drive and
would have become the reported frontier — a wrong headline.

**How it was caught.** Not by inspection: `n4_L15_W30` came back byte-identical
to `sg2400_n4_L15_W30` (`t_hop` 76.88 ps, `Q` 15.00, `VBEND` 1.0416 V on both),
and two rows at different gate drives cannot agree to five digits.

**The fix and the check.** Both globals are now set UNCONDITIONALLY from the
arguments on every call. `audit.py` re-reads the `VHI` line and the cell input
sources out of **every generated netlist** and compares them against the spec
that asked for the point — all 118 decks with data, not a sample. The eight
contaminated rows were re-run at the correct 1.5 V and the audit now reports
ALL CLEAN.

**The corrected number.** At its true VGH = 1.5 V, `n4_L15_W30` has
`VBEND` = 0.9885 V and `VA_open` = 0.2180 V, and it **FAILS** K2 (the 0.990 V
swing floor) by 1.5 mV. **The feasible frontier at the committed gate drive is
EMPTY**, as the unconta minated rows already said.

(The audit's mix witness is applied only at N ≥ 4: by A1 the DATA mix's first two
vectors ARE the two RESTORED vectors, so an N = 2 data-mix deck is legitimately
byte-identical to an N = 2 restored-mix deck.)
