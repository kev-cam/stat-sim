# qal/widebank — amendments to PRE_REGISTERED.json

`PRE_REGISTERED.json` sha256 `c98fa10887b91177194b59a1d994ec7b83b18561658563f02fab7e09f6ef2f3f`,
20808 B, mtime **2026-09-29 19:21:28.688875958 -0700**, the second file written in
this directory after `DISK_STATE_BEFORE.txt` (19:19:10) and before any deck.

Each amendment records what forced it and when. Nothing in the pre-registration
is edited.

---

## A1 — iso-swing CMOS column added (before the first sweep deck)

**When:** written into `wbx.py` at 19:5x, before the first sweep deck.

**What forced it:** both committed CMOS references are measured at **1.2 V** —
`bound/PRE_REGISTERED.json : CMOS_inverter_anchor_fJ_per_full_cycle = 10.0831`
on the *same* 1.12 p / 0.74 n cell, and the 232 fJ / 928 ps / 56-cell block on
the SG13G2 typ 1.2 V synthesis. The sweep runs QAL at **dV = 1.65 V** because the
brief and the block require it (below Vtn + |Vtp| = 0.9642 V the cascade is not
level-restoring; the 161-cell block fails 59/161 at dV = 1.2). Energy goes as
V², so a bare comparison charges QAL a 1.891× swing penalty that CMOS does not
pay.

**What was added:** two DERIVED columns per ledger row,
`x_vs_CMOS_block_isoswing_DERIVED` and `x_vs_CMOS_inv_isoswing_DERIVED`, against
`4.14 × 1.890625 = 7.8272` fJ/cell/op and `10.0831 × 1.890625 = 19.0634` fJ/cycle.

**What did NOT change:** the pre-registered bar. The **primary** comparison stays
QAL @ 1.65 V against CMOS @ 1.2 V, because the swing is a *requirement of QAL on
this node*, not a free parameter — so charging it to QAL is the honest reading and
the iso-swing column is the flattering one. Any crossing claimed on the iso-swing
column alone will be labelled as such.

---

## A2 — digit correction to the brief's quoted committed rails

**When:** 19:4x, from the A0a re-extraction, before the first sweep deck.

The brief quotes the committed banktank row's rails as
`0.6767239 / 0.7312456 / 0.7200877 V`. The committed
`banktank/row_m10_T200_H4_dv1200_free.json` (sha256 `584ee49e…`) contains
`0.6767239 / 0.7312457 / 0.7200878 V`. The last digit of the second and third is
**7 and 8, not 6 and 7**. The re-extraction reproduces the committed file exactly
(`INSTR_A0a_reextract.json`, diffs = 0), so the file is the authority and the
brief's last digits are a truncation. Worst gate `90.54454610810019 %` and
`IPK₁ 937.4588 µA` match the brief exactly.

---

## A3 — `m=` is declared and DISCARDED by the shim, so device multipliers cannot
be used to avoid geometry recompiles

**When:** 19:5x, while planning the warm pass, before the first sweep deck.

`qal/sg13lv_compat.sp` declares `m=1` on both `sg13_lv_nmos` and `sg13_lv_pmos`
and **does not pass it to the PSP103 instance**:

```
.subckt sg13_lv_nmos d g s b l=0.13u w=0.15u ng=1 ad=0 as=0 pd=0 ps=0 m=1 trise=0
M1 d g s b sg13g2_nmos W={w} L={l}
.ends
```

So writing `m=4` on a switch device would be **silently ignored** — the deck
would simulate a 1× device while the ledger charged 4×. The same class of trap as
the shim's discarded `ad/as/pd/ps` already recorded in the brief. Consequence for
this study: every distinct switch width is a distinct PyMS geometry and needs its
own `.so`. The sweep therefore pays a one-time ~18-geometry sequential warm, and
**no `m=` multiplier appears anywhere in `wb.py`.**

---

## A4 — the switch is scaled by WIDTH, not by parallel copies

Recorded for completeness because it is the obvious alternative and it was
considered and rejected: scaling the switch as ⌈√(N/8)⌉ *parallel copies of the
committed 30 µm triple* would need only one geometry, but √(N/8) = 1, 1.414, 2,
2.828, 4, 5.657 is not integral, so rounding it would distort the very exponent
under test. Continuous width scaling is used instead and the geometry cost is
paid.

---

## A5 — a PARK-BRANCH AMMETER was added, because the committed tank-closure
identity cannot close without it

**When:** 19:5x, before the first sweep deck (the instrument-check deck in
`btk/` is the *committed* harness and is untouched).

**What forced it:** the committed deck's park device sits between `sw{k}` and
`tnk{k}` and is therefore a **second conduction path that does not go through
L**. The committed closure cross-check — ∫V(tnk)·I(L) against the linear tank's
own ½C(V₀²−V₁²) — is blind to it. In the committed dV=1.65 row it misses
**11.87 fJ of a 47.29 fJ per-cycle loss (25.1 %)**, and the committed extractor
reports that as `tank_closure_residual_fJ` without a gate on it.

**What was added:** an ideal 0 V source in the park's source lead
(`VPKA{k} pks{k} tnk{k} 0`; the bulk stays on `tnk{k}`, the same potential) plus
charge and energy integrators on it.

**Result, and it is a new term, not a bookkeeping tidy-up:** with the park branch
metered the closure residual falls to **−0.178 fJ on a 47.13 fJ loss (0.38 %)**
and the missing 25 % is identified: **12.40 fJ/cycle of the N=8 tank loss leaves
through the park, not resonantly** — the parked L–R–park loop ringing down
(τ = 2L/R = 3 ns, so it never damps inside a beat). The committed ledger had this
inside its tank number but never separated it. Measured across the sweep the
park path is **NOT** the term that defeats the amortisation: per gate it falls as
N^−0.55, the fastest-falling term in the study.

**TRANSPARENCY VERIFIED, not asserted:** `WB_NO_PARK_AMMETER=1` regenerates the
committed wiring. At N=8, T=200 the two decks agree on every reported quantity —
E/gate 6.0106 both, t_hop 126.57 both, A2 margin 461.09 mV both, worst-gate
99.26 % both. `row_n8_T200_H4_dv1650_free_nb3_noamm.json`.

---

## A6 — the gate-charge integrators are referenced PRE-CLOSE, not to t = 0

**When:** after the first N=8 row, before the sweep proper. That first N=8 row
was **re-run** under the corrected reference; nothing from the uncorrected one
is reported.

Referencing bank k's close-edge charge to the t = 0 integrator zero puts every
*earlier* bank's whole hop inside bank k's "close" window. A checkpoint 3 ps
before the close edge was added (`QGT{k}_P` etc.). Effect at N=8: 109.09 →
109.06 fC, i.e. the contamination was 0.03 %, but the window is now correct by
construction rather than by luck.

---

## A7 — the pre-registered source-side-cut gate was MIS-SPECIFIED; restated,
and the structural claim verified a different way

**When:** after the N=8 row, from its own measurement.

A7 as pre-registered required |I(L_j)| ≤ 5 µA on every non-hopping inductor at
bank 2's rise ZCS. **Measured: it fails at N=8 (|I(L₁)| = 19.6 µA at T=200,
89.7 µA at T=130) and passes at N=32, 64, 128 and 256 (2.4, 0.18, 0.07, 0.39
µA).** The 5 µA threshold was measuring the wrong thing: bank 1's inductor is
*parked* at that instant, its L–R loop shorted across its own tank by the park
device, so what the probe sees is **bank 1's own ring-down**, not charge diverted
out of bank 2's hop. τ = 2L/R = 3 ns, so a hop that ended one beat earlier is
still ringing.

The claim A7 existed to test — that with per-bank tanks the source-side cut is
structural — is instead verified where it actually lives, in the topology: bank
k's tank island is `{CT{k}, L{k}, R{k}, sw{k}, XSWN/XSWP{k}, XPK{k}}` and shares
**no node** with bank k±1's island; the rails are coupled only through the cells'
gate capacitance, with no DC path. That is mechanically checkable in the deck and
is why chain3's finding-(d) diversion path (42.3 % of hop charge into the next
bank's idle inductor) does not exist here. The ICROSS numbers are still reported
— relabelled as the **parked ring-down current of a non-hopping bank** — and they
*improve* monotonically with N, i.e. the regime under test is the clean one.

---

## A8 — timestep falsification PASSED

Pre-registered: at N = 64 the scaled max step (0.707 ps) and the unscaled
0.25 ps must agree within 0.5 % on E_tank_loss and 1 mV on the delivered rail.
**Measured: E/gate 4.1034 vs 4.1035 (0.002 %), A2 margin 438.50 mV vs 438.50 mV
(identical), t_hop 295.83 vs 295.83.** The scaled step stands.
`row_n64_T440_H4_dv1650_free_nb3_ms025.json`.

---

## A9 — the C_bank tolerance was wrong, and the committed m = 10 is really
m_eff = 3.6 … 6.5

A9 as pre-registered required the measured secant bank capacitance to sit within
2× of the DERIVED 35.979 × N/8 fF. **It fails at N = 8 and N = 16 (ratio 2.762
and 2.287) and passes at 32…256 (1.980, 1.771, 1.632, 1.536).** The committed
`CBANK = 35.979 fF` basis measures the rail node alone; the charge that actually
comes through L also fills the cells' output nodes and the switch's own
junctions, which is 2.76× more at N = 8.

The sweep AXIS is not damaged — what matters is proportionality, and
Q_through_L/swing is 99.4 / 164.6 / 284.9 / 509.8 / 939.4 / 1767.9 fF, i.e. it
rises monotonically and smoothly with N. What IS damaged is the committed tank
ratio: **the real tank-to-bank ratio is m_eff = 3.62 at N = 8, rising to 6.51 at
N = 256**, not the nominal 10. That is why the measured recycle fraction is only
17.3 % at N = 8 and why it *improves* to 36.1 % at N = 256 — the same tank sizing
rule gets relatively more effective as the bank widens, because the N-independent
part of the bank capacitance is diluted. Reported, not corrected: retuning
C_tank per N to hold m_eff fixed is a design lever this phase did not pull.

---

## A10 — a row must clear A4 as well as A1 and A2 to be ACCEPTED

The pre-registration listed A1…A9 but did not say which combination makes a
point ACCEPTED. Fixed here, before RESULTS.json was written:
**ACCEPTED = A1 ∧ A2 ∧ A4 ∧ A5 ∧ A6.** Consequence: the tight-beat rows
(N=8 T=130/140, N=16 T=180, N=32 T=230, N=64 T=310, N=256 T=570) are reported
**A4-FLAGGED, not accepted**, because their return-hop residual is 1.59–7.72 µA
against the committed 1 µA gate. The flag is recorded with what it is worth:
½LI² at 7.72 µA is **4.5 × 10⁻⁴ fJ**, i.e. 1 × 10⁻⁵ of the row's own 47 fJ, and
the flagged rows' energies agree with the accepted ones to 4 decimal places. The
mechanism is the committed probe protocol's return-zero transfer degrading as the
beat shortens (in the `ret` probe the *later* banks never return, and at small T
their returns crowd the window); the fix is an iterated probe and it was not run.
Both beat sets are reported separately and neither is presented as the other.

---

## A11 — the random-pattern fixture control had to be run TWICE

The first `--rnd 7` run computed the shuffled pattern and **did not pass it into
the deck generator or the extractor**, so it silently re-ran the tiled pattern
(which is why its numbers were identical to 14 significant figures). Caught by
that identity, fixed (`P=P` threaded through `do_probe`/`do_row`/`row_extract`,
and the zeros filename now carries the pattern), and re-run.

The corrected control is reported and its result is the same identity **for a
real reason**: the patterns genuinely differ
(`1110100111101001…` vs `1111001000111111…`, both 40 HIGH of 64) and every
measured quantity still matches to the digit — E/gate 4.1034, A2 margin
438.50 mV, t_hop 295.83, worst gate 99.40 %. So the declared two-class
degeneracy is now **MEASURED, not assumed**: a bank of identical cells on one
lumped rail is a function of the HIGH *count* only, and the arrangement is
electrically irrelevant. `row_n64_T440_H4_dv1650_free_nb3_rnd7.json`.
