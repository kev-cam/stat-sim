# SKEPTIC audit — qal/sha256 SHA-256 QAL block

Pre-registration: `SKEPTIC_PREREG.json`
sha256 `c56e9967c92017ef861877963a89a1653ee972671a5a66b9d89f59d62afebeef`
written 2026-09-29 16:54:28 -0700. First SPICE deck of this track: 16:55.

Own dir `qal/sha256/sk3`. Own `PYMS_VAE_CACHE=/tmp/.../scratchpad/vae_cache_sk3`
(seeded by copying the track's warm cache — compiled device .so files keyed by
geometry, no circuit results; disclosed as a shared input).

---

## 1. Static structure — re-derived from the PDK SPICE, BEFORE any deck

Read directly out of
`/usr/local/src/IHP-Open-PDK/.../sg13g2_stdcell.spice`:

| cell | pMOS rise depth | nMOS pull-down depth | verdict |
|---|---|---|---|
| `sg13g2_inv_1` | 1 | 1 | shallow both sides |
| `sg13g2_nand2_1` | 1 (XP0,XP1 both Y←VDD, parallel) | **2** (XN1 net1←B←VSS in series with XN0 Y←A←net1) | shallow p-side ONLY |
| `sg13g2_nor2_1` | **2** (XP0 net1←A←VDD in series with XP1 Y←B←net1) | 1 | NOT shallow |
| `sg13g2_and2_1` | 1 (all three pull-ups single-device to VDD) | 2 on the internal node | shallow p-side |
| `sg13g2_o21ai_1` | **2** (XP0 net14←A1←VDD series XP1 Y←A2←net14), l=150n | 2 | NOT shallow |

**The brief's blocker is wrong, and REMAP's Correction 1 is CONFIRMED**: `nor2`
is a 2-high pMOS stack, `and2` is shallow. The shallow set is {inv, nand2, and2},
not {inv, nand2, nor2}.

**BUILD's central claim is also CONFIRMED structurally**: `nand2` — 115 of the
161 block cells — is depth-1 on the p-side and **depth-2 on the n-side**. Phase 1
selected the library on `binding_pmos_rise_depth`, a p-side-only metric, which
cannot see this. The shallow-stack remap moved the 2-high stack rather than
removing it.

My own evaluator's cell functions were checked against the vendor's own
`sg13g2_stdcell.v` behavioural models — `not`, `and`+`not`, `or`+`not`, `and`,
`or`, `buf` — and match.

---

## 2. Census recheck — MY OWN harness (`myc.py`), independent deck generator
and independent waveform extractor, not `census.py`/`sk.py`

Same physical point (dV=1.65 V, L=6 nH, TG 120 µm, VGH 1.65, CL 2 fF, 500 ps
tail, true-ZCS cut, PDK subckt verbatim + 0.1 fF/internal node).

| family | my t_valid90 | track | rel err | verdict |
|---|---|---|---|---|
| `nand2` | 59.9859 ps | 60.0 | 0.02 % | reproduced |
| `inv` | 75.8878 ps | 75.889 | 0.002 % | reproduced |
| `nor2` | 196.1736 ps | 196.2 | 0.01 % | reproduced |
| `o21ai` | 479.1059 ps | 479.1 | 0.001 % | reproduced |

C1 VALUE `True` on all 8 cells of all four banks. The **speed ordering**
`nand2 < inv < nor2 < o21ai` — the load-bearing claim, because it is what
selects the remap library — survives an independent harness. The depth-1 /
depth-2 partition is real.

I verified four families, not three: one PASS (`nand2`), the PASS reference
(`inv`), and two MARGINAL (`nor2`, `o21ai`). **No family FAILS**, so the brief's
"one that passed and one that failed" could not be honoured as asked; I
substituted the PASS/MARGINAL boundary and the brief's own `o21ai` anchor.

### 2b. A DEFECT IN THE CENSUS METHOD THAT I FOUND AND MEASURED

The census stimulus is the **maximum-DEPTH** input vector. For a depth-1 cell
with **parallel** pull-ups, the max-depth vector is the max-**DRIVE** vector.
`nand2`'s census vector is A=0,B=0 — *both* pMOS conducting, 2× pull-up drive.
The true worst-case rise is one input low.

Measured, my own deck, same point:

| `nand2` rise vector | pull-ups on | t_valid90 |
|---|---|---|
| A=0,B=0 (the census vector) | 2 | **59.99 ps** |
| A=0,B=1 (true worst case) | 1 | **89.31 ps** |

**1.49× slower, and slower than the inverter (75.89 ps), not faster.** REMAP's
headline flourish — "nand2 is FASTER than the inverter (two parallel pMOS
pull-ups into the same load)" and the `{inv,nand2}`-beats-`{inv,nand2,and2}`
inversion that rests on "nand2 only 60.0" — is an artefact of the stimulus
choice, not a property of the cell. Consequence for the composed block time
below.

### 2c. The census is blind to cascade drive degradation — in BOTH harnesses

Every cell input in the census is an **ideal source at the full swing**, so the
nMOS pull-down always has full overdrive and the n-side stack never binds. My
own degraded-drive probe (`drv.py`), output-LOW cells driven at the delivered
rail instead of the swing:

| rail | gate drive | t_valid90 | output-LOW v_end |
|---|---|---|---|
| dV=1.2 | 0.74 V | **195.69 ps** (3.3× the 60 ps census row) | 0.001 V — still pulls down |
| dV=1.65 | 1.10 V | 58.49 ps | −0.000 V |

So drive degradation is worth **3.3× on the n-side stack** — large, and invisible
to the census. It does **not** by itself make an isolated bank fail; the dV=1.2
block failure is a **compounding** effect across banks, which a single-bank
harness cannot reproduce by construction. I confirm the direction and the
magnitude of the mechanism; I did **not** independently reproduce the failure in
a single-bank deck, and I do not claim to have.

---

## 3. Equivalence recheck — all five criteria, my own route

Target: `syn/sw_nand_sc_resyn2.v` (the netlist Phase 2 actually simulated)
against the committed `qal/synth/threeway/sha_slice.v`.

- **E1 SAT miter** (my own `my_equiv.ys`, my own `my_cells.v` extracted from the
  PDK verilog with only the `specify` blocks stripped):
  `SAT proof finished - no model found: SUCCESS!`
- **E2 induction** (`equiv_make` + `equiv_simple -short` + `equiv_induct` +
  `equiv_status -assert`): 24 of 24 `$equiv` cells proven,
  `Equivalence successfully proven!`
- **E3 — STRONGER THAN THE TRACK'S.** My own `prove.py`: **1,048,576 vectors, 0
  mismatches**, and it is a **COMPLETE PROOF**, not a sample. Support sets
  computed by transitive fan-in give `sum[i] ← a[0..i],b[0..i]` (≤16 vars),
  `maj[i] ← a[i],b[i],c[i]`, `ch[i] ← e[i],f[i],g[i]`. A sweep of all 2^16 (a,b)
  pairs × c∈{0x00,0xFF} × 8 uniform (e,f,g) patterns therefore visits **every
  assignment of every output bit's entire support**. 155,600 vectors is a sample;
  this is exhaustive.
- **E4 closure**: histogram `{inv:46, nand2:115}` ⊂ {inv, nand2}, both census
  PASS. `sw_shallow_sc_resyn2.v` also proven (146 cells, depth 13,
  `{inv:40, nand2:91, and2:15}`), 0 mismatches.
- **E5 ports**: dumped from yosys's own `write_json` — `a,b,c,e,f,g` in [8],
  `maj,ch,sum` out [8], identical on gold and gate.

The reference is **my own** re-implementation of `sha_slice.v` read off the RTL
text. The failure mode I was hunting — a proof against a reference derived from
the netlist under test — is not present.

---

## 4. Block correctness policing — the DECK, not the .v file

`police.py` parses the SPICE deck as the netlist, so what is checked is exactly
what was simulated.

**The deck is the FULL BLOCK, not a slice**: 161 cells (46 `inv` + 115 `nand2`),
14 banks, 14 tanks, 14 inductors, 42 transfer-switch devices, 48 primary-input
sources. Verified by parsing.

**Vector read out of the deck itself**: a=0x5A b=0xA6 c=0x3C e=0x69 f=0x96
g=0xC3. My own reference gives maj=0x3E, ch=0x82, sum=0x00 (with carry-out) —
matching BUILD.

**The DECK is equivalent to the RTL**: 1,048,576 vectors, 0 mismatches, all 24
primary-output nodes identified (8 `ch` nodes pinned by support set, since
uniform e/f/g patterns make them functionally indistinguishable). So the thing
simulated is the thing proven — not merely the .v file upstream of it.

### Per-gate boundary value check, my own oracle and my own threshold

| deck | swing | half-rail fails (mine) | BUILD 50/10 guard | worst gate |
|---|---|---|---|---|
| `b_HF300` (headline) | 1.65 | **0 / 161** | 0 | 95.0695 % |
| `b_H300` | 1.65 | 0 / 161 | 0 | 95.0442 % |
| `b_H250` | 1.65 | 0 / 161 | 0 | 89.4367 % |
| `b_H200` | 1.65 | 0 / 161 | **2** | 77.9396 % |
| `b_T300` | 1.2 | **13 / 161** | **54** | 34.3423 % |
| `b_T260` | 1.2 | 16 / 161 | **59** | 33.9015 % |
| `b_T400` | 1.2 | 8 / 161 | 45 | 34.2928 % |

BUILD's counts (54, 59, 2, 0, 95.06/95.07, 89.44/89.46, 77.94) **reproduce
exactly** under their own guard. My independent symmetric logic-threshold check
agrees on **every verdict**.

The delta is fully explained: BUILD's guard (`xb.py`) is **asymmetric** —
`v ≥ 0.50·rail` if expected HIGH but `v ≤ 0.10·rail` if expected LOW. That is
**stricter** than a logic threshold, i.e. pessimistic about QAL. Not a
whitewash. One prose slip: BUILD says 54 fails "at T=300 and at T=400"; the
T=400 deck gives 45 under their own guard.

**End-of-run fails: 0.** So the dV=1.65 result is not a slow-combinational
artefact — the gates are right at their own bank boundaries, which is the
pipeline question.

**Separation**: min 803.7 mV (`b_H300`) / 805.9 mV (`b_HF300`) — reproduced. But
it is computable on only **8 of 14 banks**: with one input vector, six banks have
all-HIGH or all-LOW expected outputs and have no separation to measure. At
dV=1.2 I get 423.4 → 167.7 mV across banks 1→4, matching BUILD's compression
figure.

---

## 5. Timing recheck — my own levelizer, independent of `struct.py`

| quantity | mine | BUILD |
|---|---|---|
| DEPTH | 14 | 14 |
| bank profile | 41/32/26/21/6/5/3/7/4/7/3/4/1/1 | identical |
| max signal lifetime | 11 hops (level 3 → level 14) | 11 |
| H_k | {1:11, 2:4, 3:12, 4:11, 5:5, 6:9, 7:2, 8:7, 9:2, 10:5, 11:2, 12:3, 13:2, 14:1} | identical |
| **II = max_k H_k** | **12 beats** | 12 |
| relays for primary inputs | 34 | 34 |

From the deck's own `.measure AT=` schedule: beat 300 ps (±2 ps jitter),
boundaries 501…4399 ps, **latency 4198.0 ps**, II·T = 12×300 = **3600 ps**. The
comparison table uses 3600 ps as the throughput denominator — H·T is used
correctly, not T and not depth·T.

**Retime cost is convention-dependent and BUILD picked the pessimistic
convention.** My counts:

| convention | relay cells | total |
|---|---|---|
| per-cell shared chain, outputs not aligned | 114 | 309 (1.92×) |
| per-edge chains, outputs not aligned | 141 | 336 (2.09×) |
| **per-cell shared chain + all 24 output cells held to depth 14** | **296** | **491 (3.05×)** ← BUILD |
| per-edge + outputs held | 323 | 518 (3.22×) |

BUILD's 296/491 reproduces exactly under the convention that all 24 outputs must
be presented aligned at level 14. That is defensible and it is the **largest** of
the four — pessimistic about QAL. Honest range: 309–491 cells.

**II = 12 IS NOT EXERCISED BY ANY DECK.** The 48 primary inputs are DC constants
held for the whole run; one operation is simulated. II is a correct **structural**
derivation from the DAG, not a measurement. It must be labelled DERIVED.

---

## 6. Booking audit

### Every independent source in the headline deck, enumerated

| class | count | metered? | classification |
|---|---|---|---|
| `VPI0..47` primary inputs, DC 0/1.65 V | 48 | yes (`qi`, `ei`) | **IDEAL — BOOKING** |
| `VGT*/VGTP*/VPK*` switch gate drivers, PWL | 42 | yes (`egt`) | **IDEAL — BOOKING** |
| `VMG1..14` ground returns, DC 0 | 14 | yes (`qg*`) | measurement taps |
| `VHI` switch pMOS bulk, DC 1.65 | 1 | yes (`ehi`) | **IDEAL — BOOKING** |
| `VBK` buck supply, DC 1.2 (buck deck only) | 1 | yes (`qbk`,`ebk`) | metered supply |
| `VGTU*/VGTO*/VGTP_O*` buck gate drivers, PWL | 42 | yes (`egb`) | **IDEAL — BOOKING** |
| 1 F integrators (`B` sources) | 88 | — | instrumentation |

**No source is unmetered.** The metering is comprehensive; the problem is not
missing instrumentation, it is that six classes of source are ideal.

### The energy ledger reproduces exactly

Recomputed by me from the `.mt0` files, with the tank formula read out of
`xb.py` (V0 nominal → each bank's own post-**return** tank voltage `VT{k}Q{k}`):

| row | my per-op tank | BUILD |
|---|---|---|
| `b_H300` | 1262.335 fJ | 1262.3 |
| `b_HF300` | 1248.671 fJ | 1248.7 |
| `k_KH300` (buck) | 1243.804 fJ | 1243.8 |
| `b_T300` (dV=1.2) | 643.152 fJ | 643.2 |
| `k_K300` (dV=1.2) | 633.683 fJ | 633.7 |

Buck, `k_KH300`: E_supply **771.107 fJ** (771.1), Q_supply **642.59 fC**
(642.6), gate drive **70.828 fJ** (70.8), stored into tanks **321.092 fJ**
(321.1), **η = 0.41640** (0.4164), wall = 1243.804/0.4164 = **2987.01 fJ**
(2987.0). All exact.

### Is the timing hardware in the energy? — mostly YES

- **Tanks: YES.** The headline *is* the tank energy, and it is the
  convention-free number (linear capacitor).
- **Series resistance: YES** (E_R ≈ 84 fJ, inside the tank accounting).
- **Tank recharge: YES, as a DERIVED number.** The 1243.8 fJ is exactly the
  recharge requirement; the 2987 fJ wall figure is that divided by measured η.
  Only **25.8 %** of the per-operation cost was actually replaced by the one
  measured 35 ps pulse, so constant-η extrapolation to 100 % is an assumption.
- **Inductors: BOOKING.** 14 ideal `L`s; the only loss is the explicit 10 Ω.
  No DCR beyond that, no core loss, no Q limit. 14 discrete 4 nH inductors with
  Q high enough to matter are not an on-chip given.
- **Switch gate drive: NOT INCLUDED, and this is the big one — see below.**

### BOUNDS, WITH DIRECTION AND SIZE

The three signed integrals BUILD correctly excludes from the total, measured by
me on `b_HF300`:

| integral | my value | meaning |
|---|---|---|
| `E_gate_drive` (42 switch gates) | **−22.471 fJ** | ideal PWL sources net ABSORB |
| `E_VHI` (switch pMOS bulk) | **−355.5 fJ** | net absorbing; I cannot cleanly attribute this and I am not inventing a mechanism for it |
| `E_primary_inputs` (48 PIs) | **−142.814 fJ** | ideal sources net absorb |

BUILD says "every energy total is a LOWER BOUND" — correct. **But the size of
the bound it quotes is the recovered credit of an ideal source, which is not what
a real driver would pay.** The real unbooked cost is set by the switch gate
capacitance, and these switches are enormous: **42 devices, 736 µm total width,
95.68 µm² of gate area** across the 14 banks. That is being measured directly
(`gdrv.py`) — see §8.

### Two numbers carried across operating points

- `C_tank` total is **11.6465 pF** at the dV=1.65 working point
  (`CBANK_dv1650.json` × m=10, and the decks' own `CT*` values agree). BUILD's
  prose says **10.94 pF**, which is the **dV=1.2** sizing. The area claim
  therefore understates: at ~1.5 fF/µm² MIM it is **~7764 µm², 12.4×** the
  627.78 µm² CMOS logic area, not 7290 µm² / 11.6×. Direction: **flatters QAL.**
- The bank-profile spread is **41.3:1** at dV=1.65, not the quoted 42.2:1 (that
  is the dV=1.2 figure). Immaterial to any conclusion.
- `BUCK_BOOK.json` on disk is the **dV=1.2** book (V_tank0 = 0.66, η = 0.36277,
  wall 2093.15 fJ). The reported η = 0.4164 and wall 2987 fJ come from the
  `k_KH300` row instead. The reported numbers are the right ones; the stale file
  is a trap for the next reader.
- The wall figure mixes rows: 2987.0 = 1243.804/0.4164 uses the **buck row's**
  tank cost, but is quoted beside the **1262.3** headline. Consistently it would
  be 3031.5 fJ. 1.5 % — immaterial, but it is a mixed row.
- η = 0.4164 **excludes the buck's own gate drive**. BUILD discloses
  η = 0.3814 including it but headlines the higher one. At 0.3814 the wall figure
  is **3261 fJ**, not 2987. And the buck's gate drive is itself ideal PWL, so
  3261 fJ is still a lower bound.

### Chain-legality: BUILD's argument is topologically correct

I verified from the deck that each LC island touches exactly one rail:
`tnk_k` is touched only by `CT_k`, `L_k`, `XPK_k` (+ the buck output); `rail_k`
only by its own 41 cells and the transfer gate. There is no second terminal to
divert into, so the A3 source-side cut has nothing to cut. The argument holds.
The strict double-cut control was never run, so the alternative is unpriced —
BUILD says so.

---

## 7. THE COMPARISON BASELINE IS ITSELF FLAGGED — and BUILD did not carry it

The campaign's authoritative record
(`memory/threeway_gals_campaign.md:177`) states:

> CMOS 56 cells **232 fJ/op @ 0.928 ns** (liberty; **~2× low** per small-gate
> correction below)

and at line 447:

> Liberty internal term 1.5–3.7× low (self-capacitance); per-class: small gates
> ×1.87–2.31, buffers ×1.26–1.40 … **Delay also 26 % low.**

So **all four non-QAL rows in the comparison table (CMOS 232 fJ, QDI 2712 fJ,
QDI+CD 4385.7 fJ, DIMS 6972 fJ) are uncorrected liberty numbers known to be
~1.9–2.3× low, while the QAL row is a transistor-level PSP103 measurement.** The
comparison is liberty-vs-transistor across a ~2× systematic gap, and that gap
runs **against QAL** everywhere. Applying it uniformly:

| vs | uncorrected | with the ×1.87–2.31 liberty correction |
|---|---|---|
| CMOS energy | QAL 5.44× (tank) / 12.88× (wall) worse | **2.4–2.9× (tank) / 5.6–6.9× (wall) worse** |
| CMOS latency | QAL 4.52× worse (928 ps) | **3.59× worse** (delay +26 % → 1169 ps) |
| QDI energy | QAL 0.47× better | QAL ~0.22–0.25× better |
| DIMS energy | QAL 0.18× better | QAL ~0.08–0.10× better |

**The verdict does not flip under any correction — QAL still loses to CMOS on
both axes.** But the reported magnitudes (5.44×, 12.88×) are inflated against QAL
by roughly 2× and should not be quoted raw.

Two further load-matching notes: the load-matched CMOS row (571.4 ps) is a
DERIVED rescale (10 × 57.143), and it uses **depth 10** — the *generic* depth —
where the mapped CMOS netlist is **depth 8**. At depth 8 it would be 457 ps and
QAL's latency ratio 9.2× rather than 7.35×. Also 10 × 94.174 = 941.7 ≠ the
committed 928, a 1.5 % internal inconsistency. Both push in CMOS's disfavour,
i.e. flatter QAL.

Committed baselines I did verify: CMOS 56 cells / 627.782 µm²
(`work/cmos_stat.txt`), QDI direct 2533.41 ps, QDI+CD 4021.15 ps, DIMS 5574.52 ps
(`work/async_recost.json`). All match.

---

## 8. MEASURED gate-drive cost of the timing hardware — the biggest unbooked row

`gdrv.py`, geometry read out of the headline deck so it is the block's own
hardware: all **42** transfer-switch/park devices, **736 µm** total width,
**95.68 µm²** gate area, terminals held at a representative bias (rail 1.1 V),
gates ramped 0 → 1.65 V → 0 from a metered source. `GDRV_qgate_vr1100.json`:

| quantity | MEASURED |
|---|---|
| Q_gate, all 42 switch gates at 1.65 V | **1548.70 fC** |
| effective C_gate | **938.61 fF** |
| implied Cox | 9.81 fF/µm² |
| energy an ideal *ramped* source delivers on the rise | 1173.83 fJ |
| **energy a conventional driver dissipates per full cycle = Q·V** | **2555.36 fJ** |

Each bank's switch closes once and opens once per operation, so that is **one
full cycle per operation**.

**Consequence.** The reported per-operation energy is 1243.8–1262.3 fJ (tank,
MEASURED) and 2987 fJ (wall, DERIVED). The switch gate drive that the ideal PWL
sources book as **−22.5 fJ** actually costs **2555 fJ** with a conventional
driver — **2.03× the entire measured tank energy**, and 0.86× the derived wall
figure. A corrected wall-plug lower bound is **≥ 5542 fJ** (2987 + 2555), before
the 48 primary inputs and the buck's own drivers.

Honest counter-argument, stated because it is the strongest one against my
number: a *resonant/adiabatic* gate driver could recover much of that charge —
which is arguably QAL's own thesis applied one level up. But no such driver is
designed, sized, or measured here, it would need its own inductor and tank per
gate-drive net (i.e. more timing hardware, more area), and the honest reading is
that the real cost lies between "recovered" and 2555 fJ — it is certainly not
−22.5 fJ. The reported energies are lower bounds by a margin **larger than the
headline number itself**, which BUILD's wording ("a LOWER BOUND") is technically
correct about but does not convey.

**DID NOT LAND, declared.** `GDRV_realdrv_vr1100.json` — real CMOS inverter
drivers on the same 42 gates with a metered supply, to *measure* the dissipation
rather than infer it — was launched and **failed to converge in ~40 min** (no
`.prn` written; killed by PID). So the 2555 fJ figure is **DERIVED** (Q·V from a
MEASURED Q_gate of 1548.70 fC), not measured end-to-end. Q·V is the textbook
dissipation of a capacitance switched from a fixed supply and back, and Q_gate is
measured on the block's own geometry, so I stand behind the magnitude; I am not
claiming a measured driver-supply integral, because I do not have one.

---

## 8b. Phase 1's composed block time vs Phase 2's measurement

My own levelizer + composition reproduces REMAP's numbers **exactly** (967.0 ps
for `{inv,nand2}`, 1147.8 ps for `{inv,nand2,and2}`), which validates the method
before I perturb it. Re-composing with my corrected worst-case `nand2`:

| mapping | REMAP (nand2 = 59.99) | corrected (nand2 = 89.31) | change |
|---|---|---|---|
| `{inv,nand2}` 161 cells, d14 | **967.0 ps** | **1250.3 ps** | +29.3 % |
| `{inv,nand2,and2}` 146 cells, d13 | **1147.8 ps** | **1278.5 ps** | +11.4 % |

The **library choice survives** — `{inv,nand2}` is still the faster of the two —
but by 2 % rather than 16 %, and REMAP's stated *reason* ("and2 settles in 104.0
where inv takes 75.9 and **nand2 only 60.0**") is wrong: corrected, all 14 levels
are paced by nand2, not 8 by inv. REMAP's "1.04× the CMOS 928 ps" becomes 1.35×,
and "the remap BUYS 3.76× of block time" becomes 2.90×.

**But the far larger problem is that this composition method is 4.3× optimistic
and the same track's Phase 2 proved it.** Phase 1 composed 967 ps for exactly the
netlist Phase 2 then measured at a **300 ps beat × 14 levels = 4198 ps latency**.
REMAP did flag the mechanism honestly ("the per-level composition uses the census
t_level without re-solving the hop for the real bank capacitance … DERIVED at
block level, not measured") and predicted the chain-legal penalty would be ~1.36×
(103.378/75.889). The measured penalty is **4.34×**, because the census bank is a
fixed 36 fF source into 2 fF while the real banks are 6.5–270 fF. Phase 1's
headline speed claims should be treated as withdrawn, superseded by Phase 2's
measurement — which is exactly what the deliverable asked for.

---

## 9. Scoring my own pre-registration

- census reproduces + ordering holds: **HIT**. I predicted >5 % absolute drift on
  at least one family and got <0.02 % on all four — my harness agreed far more
  closely than I expected.
- equivalence all four criteria pass: **HIT**.
- "the failure mode I am hunting is a proof against the wrong thing": **not
  found** — the deck itself is proven, which is the stronger version.
- "II may be a static claim, never exercised": **HIT** — confirmed, one operation,
  48 DC inputs.
- "the wall-plug number could be worse than 2987 fJ": **HIT** — 3261 fJ with the
  buck's own gate drive, and materially worse once switch gate drive is booked.
- I did **not** predict that the comparison baseline itself is flagged ~2× low in
  the campaign's own memory, which is the largest single correction in this audit
  and runs in QAL's favour. **MISS.**
- I did not predict the census stimulus defect (max-depth ≠ max-delay for
  parallel pull-ups). **MISS**, and it is the one that touches a headline claim.
