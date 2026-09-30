# qal/sha256 PHASE 2 — AMENDMENT

Every protocol change, every defect and every miss of this track, each with its
bisection. Pre-registration: `PRE_REGISTERED.json`, sha256
`a580f3d2efbf4a916c1bcec608c63667ea0caf2be28b2735cc1ce892b2a191de`, written
2026-09-29 12:35:45 −0700. The ONLY files of this track that predate it are
`struct.py` (12:31:58) and its output `STRUCT_sw_nand_sc_resyn2.json` (12:31:58) —
both STATIC analyses of a committed netlist, disclosed inside the pre-registration
itself. No SPICE deck of this track existed at 12:35:45; the first,
`c_m10_T200_H4_dv1200_free.cir`, was written at 12:36.

---

## G0 — INSTRUMENT CHECK: PASS, digit-exact

The committed `qal/banktank` row `m=10, T=200 ps, H=4, dV=1.2, free` was re-run in
this directory under this track's own `PYMS_VAE_CACHE`, using the committed zeros
file `zeros_m10_dv1200_T200_H4.json`. **24 of 24 floats reproduce with relative
error exactly 0.0**, including `worst_gate_pct = 90.54454610810019`,
`worst_gate_where = [3, 'o3']`, `separation_min_mV = 612.378631`, all four
`rail_at_own_boundary_V`, all four `IPK_uA`, all four `IZ_uA`, all four `IZQ_uA`,
and `stage_time_deepest_ps = 190.710838`. `value_fail_list` is empty and **32 of 32
gates were value-checked**. `IC_VERDICT.json`.

The harness is therefore anchored to the known-good configuration before any block
number is believed.

---

## DECLARED CORRECTIONS (stated in the pre-registration, before any deck)

### C1 — THE HOLD IS NOT A FREE PARAMETER. This is the finding the synthetic bank could not produce.

In every prior deck of this campaign a bank fed **only the next bank**, because all
eight gates were inverters in lockstep, so `H` was a knob swept over {2,3,4} and
`II = H·T` was a design choice. A real mapped netlist is a DAG with cross-level
edges. In `sw_nand_sc_resyn2.v` the maximum **signal lifetime** — deepest consumer
level minus producer level — is **11**: a cell in bank 3 is read by bank 14. The
per-bank hold is therefore *forced by the netlist*:

```
H_k = {1:11, 2:4, 3:12, 4:11, 5:5, 6:9, 7:2, 8:7, 9:2, 10:5, 11:2, 12:3, 13:2, 14:1}
II  = max_k H_k = 12 beats,  not 4.
```

The alternative is to retime the DAG so every signal is consumed by the very next
bank. Measured statically: 296 relay cells for the cell-to-cell edges plus 34 for
the primary inputs, i.e. **161 → 491 cells (3.05×)** to buy `II = 2·T`.
`RETIME_COST.json`.

### C2 — the brief's buck figure

The brief says the fixed buck "raises the rail +219 mV above the no-top-up
control". The committed record (`qal/buckfix/VERDICT.json`,
`F_THE_RE_MEASURED_HEADLINE`) gives free control 0.765884 V and FIXED_C9
0.949960 V, i.e. **+184.076 mV**. The string `219` does not occur anywhere in
`qal/buckfix`. I use the committed 184.076 mV and the committed C9 sequencing.
Nothing in Phase 2 depends on which is right; this is a citation correction.

### C3 — what "chain-legal" means under per-bank tanks

The A3 source-side cut exists because in a *peer-fed* chain the source is the
previous bank's rail, and cutting only at the receiving side leaves that rail wired
to an idle downstream inductor to divert into. Under per-bank tanks the source is a
private tank and the tank/L/R/switch island touches exactly **one** rail, so there
is no second terminal to divert into. The headline deck therefore uses the
committed banktank cut (rail side, tank-referenced park, banktank A6) — the
configuration the instrument check anchors to.

---

## DEFECTS FOUND, ALL BISECTED

### P2-R1 — `zero_after_peak` scanned an unbounded window (mine)

`bt.zero_after_peak(hdr, rows, "I(Lk)", c_k)` takes the largest `|I(L_k)|`
*anywhere* after `c_k`. In a row deck that includes the bank's **own return**,
whose peak can exceed the rise peak — in which case the function returns the
*return's* zero as the rise's. Fixed by restricting the scan to
`[c_k, r_k − EDGE]`. Not proven to have fired (the val300 diagnostic shows the rise
peaks happened to dominate on that row), so this is a defensive fix, and it is
recorded as such rather than as a bug that changed a number.

### P2-R2 — THE REAL ONE: the return zero cannot be iterated, and an aggregate A6 hid which half was broken

I seeded the return zero `tzq = tzr` (the rise hop time) and relied on the
full-deck iteration to correct it. Measured behaviour of the A6 residual across
iterations: **243 → 193 → 210 → 218 µA — it got WORSE**. Bisection: splitting the
aggregate `A6 worst |I(L)|` into rise and return showed the rise had already
converged (worst 12.3 µA, ten of fourteen banks below 1 µA) while the return sat at
210 µA. The mechanism is that seeding `tzq = tzr` cuts the return **early** (the
measured returns are 15–45 % longer than the rises: bank 1 is 189.5 ps against
131.5 ps), and when a switch is cut early the post-cut ring-down crosses zero just
after the commanded open, so re-reading "the zero" off that waveform returns
approximately the cut time itself. The iteration creeps instead of converging.

Fixed with a dedicated **single-bank return probe** (`stage_retprobe`): the bank
starts in its MEASURED held state — rail at its measured delivered value, tank at
its measured post-rise value, inputs at their held levels — the switch is open for
200 ps so the outputs settle onto that rail, then it closes and **never opens**, so
the first current zero after the peak is the true return ZCS. This is the same
protocol the committed `bt.do_probe` uses for the rise, applied to the return.

**A one-number A6 gate would have reported "not converged" and told me nothing
about which half to fix.** The per-phase split is now reported on every row.

### P2-R3 — a correction I made that turned out not to be the cause

The first single-bank rise probe held HIGH inputs at `dV = 1.2 V`, but the block's
delivered rails are 0.61–0.81 V, so a HIGH input in the block sits well below `dV`.
I fixed it (`in_levels()`, which takes a HIGH input driven by bank *j* to bank *j*'s
measured delivered rail) **and predicted it would close the A6 gap. It did not** —
the hop times moved by less than 2 % (bank 14: 30.34 → 29.79 ps) and the A6
residual went 243 → 193 µA, nowhere near 1 µA. The fix is kept because it is more
faithful, but my attribution was wrong and the real cause was P2-R2. Recorded as a
MISS.

### P2-R6 — the single-bank rise probe cannot see the downstream fanout load

After P2-R2 was fixed the A6 residual fell to **93.0635 µA and was bit-identical at
T = 400, 300 and 260 ps**. A residual that does not move with the beat period can
only come from bank 1, whose inputs are ideal sources and therefore
schedule-independent — the same reasoning the committed `bt.do_probe` A7 amendment
uses. Bank 1's rise was also the one switch open the iteration could not close,
because it opens **early**, and re-reading a zero off a waveform that was cut before
that zero returns approximately the cut time.

Measured directly, with a full-block deck in which bank 1's transfer switch closes
at its beat and **never opens** (`NOOPEN=1`), all other banks cut at their converged
zeros:

| | bank 1 rise zero |
|---|---|
| single-bank probe | 131.4651 ps |
| **true, in the block** | **132.8482 ps** |
| delta | **+1.3831 ps** |

I had predicted the *opposite sign*, on the argument that in the block a bank's
outputs also drive downstream gates whose rails are still at 0, so the outputs lag
further and draw less charge out of the rail during a ~130 ps hop. The measurement
says the fanout-heavy widest bank is **slower** in the block (+1.38 ps), while banks
2–14 are **faster** (−0.14 to −3.69 ps). The single-bank probe is accurate to ±4 ps
either way; that is 0.03 % of the beat, and it matters only because `dI/dt` near the
zero is ~60 µA/ps, so 1.4 ps is 93 µA. **I do not have a single mechanism that
explains both signs and I am not going to invent one** — the sign is reported as
measured and the zero is taken from the full block where it matters.

### P2-R4 — shell cwd trap (mine), the committed one, hit again

`cd X && nohup A & nohup B &` runs `B` in the **session** cwd, not in `X`, because
`&&` binds tighter than `&`. The second probe job died instantly with
`python3: can't open file '/usr/local/src/stat-sim/blk.py'` and was noticed only
because its log file did not exist. This is the same class as the committed
`feedback_multirepo_push_cwd_trap`. One background launch per `cd` from now on.

### P2-R5 — `__main__` appended before the functions it dispatches (mine)

Appending a new stage function *after* the `if __name__ == "__main__":` block leaves
the dispatch executing before the function exists. Caught by grepping for the new
branch and finding the dispatch unchanged. The block is now kept last in the file.

### P2-R7 — A BOOKING ERROR OF MINE: abs() turned energy credits into costs

The first version of the energy ledger summed `abs(E_gate_drive_total)` and
`abs(E_vhi_total)` into the per-operation total, giving 860.7 fJ at dV = 1.2.
**Both integrals are NEGATIVE** under the committed sign convention (`-V·I(Vsrc)`
is positive when the source *delivers*), i.e. those ideal sources are net
**absorbing** — an ideal PWL gate driver recovers its gate charge at the end of the
cycle. Taking `abs()` booked a recovered credit as a dissipated cost and inflated
the total by 34 %.

Caught by checking the raw signs against the committed banktank row, which reports
the same quantities with the same signs (`E_vhi_total_fJ = −39.309`,
`E_gate_drive_total_fJ = −4.103`) and — correctly — never folds them into a total.

Fixed: every signed integral is now reported RAW and BY SIGN and is excluded from
the headline. The headline is the **one convention-free number**: the tank energy,
because `C_tank` is a LINEAR capacitor, so ½C(V₀²−V₁²) needs no integrator
convention at all. That also makes every total a **LOWER BOUND**, because a real
gate driver dissipates the switch gate charge each cycle where these ideal sources
recover it — and the direction of that bound is stated wherever a total appears.

---

## DECLARED METHODOLOGY DELTA

### P2-C1 — my C_bank instrument reads 7–10 % below the committed `CBANK = 35.979 fF`

Applying my quasi-static charge-secant instrument (`stage_capcheck`: ramp the rail
0 → dV over 500 ps with an ideal source, integrate the current into the rail,
`C = Q/dV`) to the **committed 8-inverter banktank bank** gives:

| dV | mine | committed constant |
|---|---|---|
| 1.2 V | 33.3847 fF | 35.979 (bt.py uses this at dV = 1.2) |
| 1.0 V | 32.4006 fF | 35.979 |

So it is **not** a dV-convention mismatch. Trace: `qal/qal_bankN_zcs.py` line 28
pairs `CASES = [(0.8, 35.0025), (1.0, 35.9790), (1.2, 36.8010)]`, where the second
element is the **source capacitor `CA`**, sized per swing — not a bank secant.
`bt.py`'s comment "committed MEASURED secant C of one 8-cell bank" is therefore
describing a different object from the one its number came from. I do **not** claim
to have reconciled the two physically; I report the delta and its trace.

Why it does not move any measured outcome here: `C_bank(k)` is used only to size
`C_tank(k) = m·C_bank(k)` and to scale `L`, both of which are **design choices**. A
uniform bias in the instrument mis-sizes every tank by the same factor, which the
`m` multiplier absorbs. The measured quantities — hop times, settling, values,
energies — are read off the circuit, not off `C_bank`. Every C in this track is
measured with **one** instrument, so the relative sizing across the 42.2:1 profile
is internally consistent.

---

## THE FINDING THAT OVERTURNS PHASE 1's OWN SELECTION CRITERION

This is not a defect in the deck; it is a result, and it contradicts the criterion by
which the Phase-1 library was chosen, so it belongs here as well as in `RESULTS.md`.

Phase 1 selected `{inv, nand2}` on **`binding_pmos_rise_depth`** — the p-side — and
said so explicitly: *"on a QAL rail the pull-up network is what drags the output up as
the rail rises, so it is the p-side depth that binds, not the n-side."* That census
measured ONE bank of EIGHT IDENTICAL cells driven by **ideal DC sources at the full
dV**, so every nMOS had full gate overdrive and the n-side stack never bound.

In a cascade the input HIGH level is **the previous bank's delivered rail**. Measured
here at dV = 1.2: rails 0.63–0.81 V against Vtn = 0.5239 V, i.e. 0.11–0.29 V of
overdrive — and `sg13g2_nand2_1`, 115 of the 161 cells, is depth-1 on the p-side and
**depth-2 on the n-side**. Measured failure rates at the bank boundary:

| | expected LOW (pull-down) | expected HIGH (pull-up) |
|---|---|---|
| `inv_1` | 11/26 = **42 %** | 4/20 = 20 % |
| `nand2_1` | 36/41 = **88 %** | 8/74 = 11 % |

The failures are on the **n-side**, and they are worse for the 2-high n-side. The
shallow-stack remap did not remove the 2-high stack — **it moved it from the p-side to
the n-side, which is the side that binds in a cascade.** Phase 1's metric was the right
metric for a single bank with ideal inputs and the wrong metric for a block.

The threshold is a device constant and it is crisp on the peak rail: below
Vtn + |Vtp| = 0.9642 V a static CMOS stage has no gain at mid-rail. At dV = 1.2, 0 of
14 banks reach it and 54 of 161 gates are wrong; at dV = 1.65, 14 of 14 clear it and 0
of 161 are wrong.

---

## STANDING BOUNDS — these bind every number in this track

- **The 48 primary inputs are ideal DC sources held for the whole run.** This is a
  BOOKING and every row carrying it is a BOUND: the block is charged nothing for
  relaying a primary input to a deep bank. The 34 relay cells that would cost are
  in `RETIME_COST.json`, not in the measured row.
- **`sg13lv_compat.sp` zeroes `ad/as/pd/ps`**, so every time here is a LOWER bound
  on a real layout, and switch-node capacitance is only what is written explicitly
  (`CL = 2 fF` per cell output, `0.1 fF` per internal cell node).
- **No wire capacitance and no place-and-route** anywhere.
- **The buck's own input rail is not costed** — only the charge and energy it draws
  from that rail, through metered devices.
- **One input vector.** Every correctness number is for the pre-registered vector
  `a=0x5A b=0xA6 c=0x3C e=0x69 f=0x96 g=0xC3`. The gate netlist's own Maj/Ch/CPA
  functions were confirmed against it independently in Python (maj = 0x3E,
  ch = 0x82, sum = 0x00 with a full 8-bit carry propagation), which is a check on
  the remap, not on the circuit.
- **Wall time.** One pass of the full 14-bank block deck (2066 lines, 203 subckt
  and switch instances expanding to ~594 PSP103 devices, 1282 `.measure` statements,
  tend 3.6–5.4 ns at a 0.25 ps maximum step) is 540–790 s. Nothing here is a slice:
  all 161 cells and all 14 banks are in every row deck.
