# QAL behavioural Verilog-A cells (`stat-sim/qal/va/`)

Behavioural (Verilog-A) cells for the **QAL arm** of the three-way gate-level
campaign (CMOS vs QAL vs async QDI, all on IHP SG13G2 / PSP103).

**Why QAL cannot use stat-sim.** CMOS and async QDI are rail-to-rail switched
capacitance: `E = alpha*C*V^2` per transition, so a full-swing event/statistical
model represents them fine. QAL is **adiabatic** — partial swing, the gate
*settles* on a ramping power-clock rail, and most of `1/2 C V^2` is **recovered,
not dissipated**. A full-swing model has no way to express "the charge came back".
These cells exist so that QAL energy comes out of an **actual current integral
against a ramping rail**, which is a number, not a formula.

Concretely, from the sweep below: the returned-charge fraction rises
**0.1% → 65.4%** as the ramp slows from 20 ps to 5 ns. No `alpha*C*V^2`, VCD, or
Liberty model can produce that column at all.

---

## 1. Files

| File | What it is | Status |
|---|---|---|
| `qal_gate.va` | single-ended settling QAL gate; INV / NAND2 / NOR2 via `TOPO`; 3 energy integrators | **source-reference FIXED 2026-09-26; VTP + RON_P fitted; mechanism + stall + cliff validated** |
| `qal_gate_dr.va` | dual-rail ECRL (cross-coupled) variant, `yt = a AND b`, `yf = NAND(a,b)` | **runs, logic correct on all 4 patterns** |
| `qal_hop.va` | bank-to-bank transfer switch + its I²R loss integrator | **runs, T6 PASSES to 0.14 pp** |
| `qal_gate_probe.cir` | single-ended probe, one ramp time per deck | runs |
| `qal_gate_dr_probe.cir` | dual-rail logic + T4(c) data-independence probe | runs |
| `qal_hop_probe.cir` | one inductive hop, vs the measured `qal_trackC.py:32` table | runs |
| `run_probe.py` | sweeps `qal_gate_probe.cir` over the A1b T grid, prints the law comparison | — |
| `run_a1b_law.py` | A1b settle-law validation, NON-COLLAPSING config; RON_P fit at 1 ns, holdouts elsewhere | — |
| `run_cliff.py` | functional-cliff probe vs the measured 34.8/77.1/100/100 % settling anchor | — |
| `run_bankhop.py` | 8-cell behavioural bank hop vs `qal_isocurrent.json` dV=1.0 row | — |
| `run_dr_probe.py` | all 4 input patterns + T sweep, prints the T4(c) GO/NO-GO | — |
| `run_hop_probe.py` | sweeps hop series R, compares to the measured loss table | — |
| `probe_runs/` | generated decks + `.mt0` from the runs reported here | — |

Run them: `python3 run_probe.py`, `python3 run_dr_probe.py`, `python3 run_hop_probe.py`.
Each is well under a minute once the PyMS cache is warm.

---

## 2. What the model is

A **conservative (charge-conserving) macromodel**, not a signal-flow one. Every
element is a real branch between real electrical nodes, and the power-clock `pc`
is a real electrical **port carrying real current**. That single design decision
makes three of the four hard requirements *emerge from the solve* instead of being
coded:

1. **Settle loss falling as 1/T.** A series on-conductance charging `CY` from a
   node ramping `dV` in time `T` dissipates `∫i²R` with `i ~ CY·dV/T`, giving the
   adiabatic `1/T` law with no fitted constant. **Measured** (section 4.2): 4.02×
   and 4.77× energy reduction per 5× ramp increase, 19.2× over 25×.
2. **Charge returned to the rail.** When `V(pc)` falls below `V(y)` the pull-up
   branch current reverses and charge flows back out the `pc` port. This is the
   thing a full-swing model structurally cannot do.
3. **The un-settled (X) boundary.** When `T` is not >> `R·CY` the output simply
   never reaches `dV`. **Measured**: `Y@hold` = 0.372 V at T=20 ps rising to
   1.2000 V at T≥1 ns. The model cannot silently certify an over-clocked block.

**The one thing modelled explicitly, because it does not emerge:** the
**source-referenced pull-up overdrive on a ramping rail**. In CMOS the pMOS
source sits on a fixed supply; in QAL the rail ramps, and a pMOS source is its
HIGHER-potential terminal — the rail while it is above the output, the OUTPUT
once the rail falls below it. So the overdrive is
`max(V(pc), V(drain)) − V(gate) − VTP` (smooth max, knee `VSM`), each pull-up
leg referenced to **its own drain** (`y` for INV/NAND legs, `w` for the NOR2
upper leg, `max(w,y)` for the NOR2 lower); the NAND2 series nMOS gets the dual
smooth **min**. Compare `stdcell2bfit.py:63-65`, whose CMOS form is
`((vsup-V(gate))/vsup)/ron+gmin` — substituting the source-referenced ramping
rail is what turns a CMOS behavioural cell into a QAL one. On the down-ramp
conduction continues until the OUTPUT reaches `|Vtp|`, so the cell stalls at
exactly `VTP` at every ramp time — matching the measured Vt stall of
`qal_nand_adiabatic.py:21-25` ("Y stalls ~0.5V at pc=0") without being told to.

> **FIX RECORD (2026-09-26).** The first cut referenced the overdrive to the
> RAIL alone (`V(pc,gate) − VTP`), so the pull-up shut off when the *rail*
> crossed `VTP` instead of when the *output* did — in the exact half-cycle the
> model exists to predict. Measured impact on seed params: `E_rail_net` ~19 %
> pessimistic at every ramp time (8.203→6.922 fJ @500 ps, 6.049→5.053 @1 ns,
> 3.014→2.532 @5 ns), recovery 40.8 %→50.6 % @1 ns, and the stall was a
> T-DEPENDENT ARTIFACT (0.812/0.685/0.499 V at 0.5/1/5 ns) — fitting `VTP` to a
> measured stall would have fit a fiction. Found by the skeptic audit of
> workflow wf_e790a9cd (verdict JSON `whti2g8l3.output`); fix regression-checked
> bit-close against the skeptic's corrected-cell runs (6.9223/5.0531/2.5315 fJ
> vs 6.922/5.053/2.532). The pre-fix seed-run `.mt0` are preserved under
> `probe_runs/seed_vtp035/`. Same fix applied to `qal_gate_dr.va`
> (cross-coupled pull-ups), which remains QUARANTINED for magnitudes (§6).

Topology is selected by **pure arithmetic Lagrange weights** on `TOPO`
(0=INV, 1=NAND2, 2=NOR2), never a parameter-valued `if/else`, so nothing depends
on whether PyMS resolves parameter conditionals at codegen or at runtime. All
three branch sets are present; the two unselected are multiplied by exactly 0.

---

## 3. Energy accounting

Energy is a current integral, never a formula. Three integrator nodes per
instance (`qal_gate.va`; see §6 for why the dual-rail cell has two):

```
ed : E_dissipated = ESCALE * ∫ (Σ over EVERY branch of i·v) dt     [rises only]
er : E_rail_net   = ESCALE * ∫ V(pc,gnd)·i_pc dt   [FALLS when charge returns]
eq : E_returned   = ESCALE * ∫ max(0, −V(pc,gnd)·i_pc) dt          [rises only]
```

At `ESCALE=1e15` these read **fJ directly**. `E_drawn = V(er) + V(eq)`.
`eq` exists so recovery is a *per-instance* number rather than a two-timestamp
subtraction. Mechanism: PyMS has **no `idt()`**, so each integrator is a 1 F
capacitor fed a current equal to the instantaneous power —
`ddt(V(ed,eg)) = ESCALE·pdiss`.

Block totals are a **sum of per-instance current integrals**, formed in the
netlist:

```
Btot etot 0 V={ V(x1:ed)+V(x2:ed)+ ... +V(hop1:ed) }
```

### The closure identity — this is what makes the model trustworthy

```
E_rail_net  ==  E_diss + (stored reactive energy now − at start)
```

For a QAL beat the stored term is the **stranded charge the Vt stall leaves on
CY**, `= 1/2·CY·V(y)²`. A QAL gate does *not* return to its initial state, so
unlike `qal_a1b.py:10-15` that term cannot be assumed zero — carrying it
explicitly turns the identity into a **test** (T1). Two independent integrators
must agree, so a bookkeeping error cannot hide. It is computed **live in the
netlist** (`BEST`/`BECLO` B-sources), so T1 is a measured number in every run, not
a post-hoc check.

---

## 4. Measured results (2026-09-26, post source-reference fix)

Xyce `DEVELOPMENT-202607082310`, `.hdl`/PyMS. Parameter status:
**`VTP=0.50` FITTED** against the T0 stall anchor (`qal_nand_adiabatic.py:21-25`
— the corrected cell stalls at exactly `VTP` at every T, so `VTP` reads
directly off the transistor's ~0.5 V stall); **`RON_P=6229` FITTED at T=1 ns
ONLY** against the A1b measured law (holdouts below); `RON_N`, `VTN`, `CY`,
`CIN` remain **UNFIT SEEDS**. VACASK / ngspice / OpenVAF are still not
installed (checked 2026-09-26), so Xyce is the only live engine lane —
per-engine reporting a la `bfit/benchmarks/perf.md` is not yet possible here.

### 4.1 Single-ended `qal_gate`, A1b ramp-time grid (fitted params)

`TOPO=1` (NAND2), `a=0`, `b=Vdd` → exactly one pull-up leg, no pull-down.
`Vdd=1.2 V`, `CY=10 fF`, `C·dV² = 14.400 fJ`. Energies in fJ
(`probe_runs/probe_T*.cir.mt0`):

| T (ps) | Y@hold | Y@end | Ediss | Erail | Eret | Edrawn | recov% | clos% |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 20 | 0.2458 | 0.4413 | 4.1567 | 5.1301 | 0.0000 | 5.1301 | 0.0% | 0.008% |
| 50 | 0.5271 | 0.6756 | 6.9556 | 9.2367 | 0.1319 | 9.3686 | 1.4% | 0.019% |
| 100 | 0.8213 | 0.6537 | 9.1515 | 11.2851 | 0.9131 | 12.1982 | 7.5% | 0.046% |
| 200 | 1.0794 | 0.5620 | 9.4099 | 10.9835 | 2.2654 | 13.2490 | 17.1% | 0.052% |
| 500 | 1.1962 | 0.5058 | 7.6034 | 8.8763 | 3.6086 | 12.4849 | 28.9% | 0.070% |
| 1000 | 1.2000 | 0.4996 | 5.8501 | 7.0933 | 4.4190 | 11.5122 | 38.4% | 0.066% |
| 2000 | 1.2000 | 0.5000 | 4.3138 | 5.5553 | 5.0127 | 10.5680 | 47.4% | 0.148% |
| 5000 | 1.2000 | 0.5000 | 2.9583 | 4.2006 | 5.4955 | 9.6961 | 56.7% | 0.184% |

* **T1 closure: PASS** — worst residual **0.184 %** (wants < 1 %).
* **T4(b) stall: PASS** — `Y@end` = 0.4996–0.5058 V for T ≥ 500 ps against the
  ~0.5 V transistor anchor (bar: 50 mV), and it is **T-independent**, as the
  transistor's is. (Pre-fix it drifted 0.812→0.499 V with T — the artifact.)
* **The central requirement, measured on the fixed cell** (T=1 ns `.mt0`):
  V(er) rises to **11.1896 fJ** at the top of the ramp (`EUPRMP`) and falls to
  **7.0933 fJ** at the end — the rail-current integral ran NEGATIVE on the
  down-ramp. The independently rectified integrator agrees: `ERET = 4.4190` vs
  the 4.4190 fall (T=1 ns run at RON_P=5k gave 11.1896→6.5641 with
  ERET=4.6256; both agree to 1e-4). No `f_adia` anywhere in the cell.
* **X boundary appears**: not settled at 20–200 ps, settled from 500 ps.

**Direct comparison against A1b is MIS-FRAMED for this configuration** — the
single-ended pMOS pull-up strands charge at `|Vtp|` every beat (real physics,
§4.2's stall), while A1b's vehicle is a bare pass switch whose gate never turns
off and whose network returns to its initial state. The law comparison
run_probe.py prints (0.47×→6.04× drift) measures that framing mismatch, not
model error. The law validation is §4.2.

### 4.2 A1b settle law — non-collapsing configuration, fit + holdouts

`run_a1b_law.py`: same cell, pull-up gate pinned to −1.2 V so the overdrive can
never collapse (= A1b's switch-held-on vehicle). **Anchor convention corrected
per the skeptic audit**: the campaign brief's "3.4 %@5 ns / 5.6 %@1 ns /
11 %@500 ps of ½·C·dV²" mixes `E/(C·dV²)` with `RC/T` and its 500 ps value is
hand-written wrong even as `RC/T` (`qal_a1b.py:36` wrote 0.11 where its own
table gives 0.0895); the anchor used is the MEASURED `E_cyc/(C·dV²)` column of
`qal_a1b.py:44-46`, and the law is `E_cyc = 2(RC/T)·C·dV²` (not half of it).
`RON_P` fitted at **T=1 ns only**; every other row is a **holdout**
(`probe_runs/nc_T*.cir.mt0`):

| T (ps) | Y@end | Ediss (fJ) | recov% | Ed/CdV² | A1b | ratio | role |
|---:|---:|---:|---:|---:|---:|---:|:--|
| 200 | 0.0571 | 5.6918 | 44.2% | 0.3953 | 0.327 | 1.21× | holdout |
| 500 | 0.0023 | 2.9044 | 66.7% | 0.2017 | 0.179 | 1.13× | holdout |
| 1000 | −0.0001 | 1.5940 | 80.1% | 0.1107 | 0.113 | **0.98×** | **FIT** |
| 2000 | 0.0000 | 0.8413 | 89.0% | 0.0584 | 0.066 | 0.89× | holdout |
| 5000 | −0.0000 | 0.3495 | 95.3% | 0.0243 | 0.034 | 0.71× | holdout |

* **Stated tolerance, honestly**: ±13 % over 500 ps–2 ns (a 4× window around
  the 1 ns design ramp), degrading to **+21 % at 200 ps** and **−29 % at 5 ns**.
* The residual SHAPE is systematic: the linear-conductance cell falls as clean
  ~1/T (4.56× per 5× from 1→5 ns) where the transistor falls sub-1/T (3.32×) —
  the long-T gap is the disclosed missing subthreshold/leak physics (§7), the
  short-T gap the knee of a conductance that silicon modulates and the model
  fixes. One scale parameter cannot fix a shape; recorded for T2 to carry.
* Recovery emerges: 44 %→95 % with zero stranded charge — the A1b situation.

### 4.3 Dual-rail ECRL `qal_gate_dr`

> **STALE NUMBERS + QUARANTINE.** The table below was measured 2026-09-24 with
> the PRE-FIX source reference; the cell has since received the same fix as
> `qal_gate.va`. Re-checked 2026-09-26 (`probe_runs/dr_fixcheck.cir.mt0`): the
> fixed cell converges in the fragile 12-port shape, logic stays correct
> (a=b=1 → yt=1.2000/yf=0), closure 0.163 %, and yt now stalls at exactly its
> `VTP` (0.3503 V at the probe's seed VTP=0.35) — but the table has NOT been
> re-swept, and the cell remains QUARANTINED for magnitudes by the dangling
> `eq`-port defect (§6) regardless.

Structure mirrors `qal_ecrl_gate.py:56-64` device-for-device. `T=1 ns`, PRE-FIX:

| a | b | yt@hold | yf@hold | logic | Ediss | Edrawn | Eret | clos% |
|---:|---:|---:|---:|:--|---:|---:|---:|---:|
| 0 | 0 | 0.0000 | 1.2000 | OK | 4.6212 | 11.1327 | 4.1813 | 0.150% |
| 0 | 1 | 0.0000 | 1.2000 | OK | 4.7604 | 11.2699 | 4.1814 | 0.168% |
| 1 | 0 | 0.0000 | 1.2000 | OK | 4.8225 | 11.3740 | 4.1750 | 0.296% |
| 1 | 1 | 1.2000 | −0.0000 | OK | 5.0106 | 11.5259 | 4.1782 | 0.152% |

* **Logic: all four patterns correct** (`yt = a AND b`). **T1: PASS.**
* **T4(c) data-independence: spread = 3.47 % → NO-GO** against the < 2 % bar.
  Mechanism identified: the two N-trees differ in strength (parallel `an||bn` vs
  series `a&b`), which modulates the early crowbar through the *losing* rail
  before the latch resolves. Caveats: parameters are unfit, and the 0 %
  transistor reference (`qal_a1f_inductive.py:76`) is for the dual-rail
  **inductive forward transfer**, not for an ECRL gate — so the comparison target
  may itself be the wrong reference. **Treat as an open item, not a verdict.**

Ramp sweep (a=b=1): `Ediss` 12.5498 → 1.9269 fJ (**6.51× down** for 25× slower
ramp), recovery **8.9 % → 64.1 %**, `yt@end` 0.9820 → **0.5017 V**. T1 worst 0.307 %.

**The model predicts ECRL does NOT cure the stall.** The cross-coupled pull-up of
`yt` is gated by `yf`, which sits near 0 while the rail is high, so its overdrive
is still `V(pc) − V(yf) − VTP` and still collapses below `|Vtp|`. Cross-coupling
fixes the *logic* (both polarities, restoring); it does not by itself buy complete
recovery. **This prediction is unverified** — see §7.

### 4.4 Hop cell `qal_hop` vs the measured delivery-loss table — **T6 PASSES**

Re-build of `qal_trackC_hop.cir` with its time-driven `Bsw` replaced by `qal_hop`
driven by a control ramp. `C_bank=80 fF`, `L=25 nH`, `RL=10 Ω`, `dV=0.6 V`.
`loss = 1 − (VAmin² + VBpk²)/dV²`.

| Ron (Ω) | Q | VBpk | VAmin | modelled loss | measured (`qal_trackC.py:32`) | Δ (pp) |
|---:|---:|---:|---:|---:|---:|---:|
| 15 | 31.6 | 0.5789 | 0.0216 | 6.79% | 6.8% | −0.01 |
| 30 | 19.8 | 0.5712 | 0.0295 | 9.13% | 9.2% | −0.07 |
| 60 | 11.3 | 0.5564 | 0.0447 | 13.46% | 13.6% | −0.14 |
| 90 | 7.9 | 0.5423 | 0.0592 | 17.34% | 17.4% | −0.06 |
| 150 | 4.9 | 0.5163 | 0.0858 | 23.92% | 24.0% | −0.08 |

**Worst deviation 0.14 percentage points** (T6 wants < 2.0 pp) → **PASS**, across
a 10× span of series resistance, with Q reproduced exactly.

Two findings fell out of this:

* **The reference's ambiguous R column is resolved by its own Q column.**
  `qal_trackC.py:10-11` says loss is plotted against "total series R (Ron +
  inductor R~10)", but the real-device row is labelled `R=60` while the deck sets
  `RON=60` *and* `Rlab=10`. Since `sqrt(25nH/40fF) = 790.6` and `790.6/(R+10)`
  yields exactly the table's 31.6 / 19.8 / 11.3 / 7.9 / 4.9 (whereas `790.6/R`
  does not), the **R column is Ron alone** and total series R is `Ron+10`.
* **Do not double-count the switch parasitic.** `qal_trackC_hop.cir:7` already
  carries `Cmab mab 0 2f` as a netlist element. Leaving `CJ=2f` inside the cell
  double-counts it *and* wrongly adds 2 fF to the receiving bank: measured cost is
  **+2.3 to +4.0 pp** on every point, turning a 0.14 pp PASS into a 3.98 pp FAIL.
  Rule: **either** the deck owns the parasitic (`CJ=0`, as shipped) **or** the cell
  does (`CJ=2f`, drop `Cmab`) — never both.

---

### 4.5 Functional cliff — qualitative PASS, sharper than silicon

`run_cliff.py`: INV settling on a hop-like 400 ps ramp to the ACHIEVED bank
voltages of the transistor hop (`qal_hop_corrected.json` L=400 rows), settling
% = V(y)/V(rail) at hold (the `qal_bodybias.py:33` definition). T0 anchor:
34.8 % @dV=0.6, 77.1 % @0.8, 100 % @1.0/1.2:

| dV | rail (V) | model settle | T0 settle |
|---:|---:|---:|---:|
| 0.6 | 0.3725 | 0.0% | 34.8% |
| 0.8 | 0.4669 | 0.0% | 77.1% |
| 1.0 | 0.5829 | **100.0%** | 100.0% |
| 1.2 | 0.7179 | **100.0%** | 100.0% |

The cliff LOCATION is exactly right (collapse iff the rail cannot clear
`VTP=0.50`; the usable floor lands at dV≈1.0 as measured) — but the model's
cliff is a hard step where silicon's is graded: the transistor's 34.8 %/77.1 %
partial settling below the cliff IS subthreshold conduction, which this cell
does not have (hard overdrive clamp + linear `GM0`). Qualitative requirement
met; the graded edge is a recorded gap (§7).

### 4.6 8-cell bank hop vs the measured dV=1.0 row — QUANTITATIVE FAIL, root cause identified

`run_bankhop.py`, mirroring `qal_hop_gates.py` hop_deck: bank A (35.979 fF, the
measured C_eff) → L=277.8 nH + Rs=10 → behavioural switch (`qal_hop`, RON=15,
opened at the MEASURED I(L) zero) → bank B = the rail of 8 `qal_gate` INVs
(CY=2f, inputs alternating), deck-owned CBANK=28 fF making the composed C_eff
match the transistor's 35.979 fF. T0 anchor: `qal_isocurrent.json` dV=1.0 row,
regenerated and CONFIRMED this session (VBEND 0.5763 / VAEND 0.0485 / IPK
195.18 uA reproduce the committed row exactly; deck + log in the session
scratchpad `t0hop/`):

| | model | transistor | Δ |
|:--|---:|---:|---:|
| t_zcs (ps) | 227.6 | 342.0 | **−33.5%** |
| Ipk (uA) | 236.9 | 195.2 | +21.4% |
| V_A_end (V) | 0.0922 | 0.0485 | +90% |
| V_B_end (V) | 0.9073 | 0.5763 | **+57.4%** |
| E_hop (fJ) | 3.0203 | 10.7416 | **−71.9%** |
| per gate-settle (fJ) | 0.3775 | 1.3427 | −71.9% |

**Do not use the behavioural composition for bank-hop energy yet.** The books
close on the model side (E_outA 17.84 = stored 14.82 + gates 2.74 + switch 0.23
+ 0.05 residue), so this is not bookkeeping — it is missing device physics,
and the transistor run says exactly which: the silicon bank peaks at only
0.611 V (VBPK) while absorbing ~34 fC — i.e. it swallows nearly all of bank A's
charge by 0.6 V where the slow-ramp curve stores only ~26 fC, and it burns
`E_inB − E_stored = 16.26 − 7.35 = 8.9 fJ` INSIDE the gates during the 342 ps
event. That is near-threshold resistive output charging plus subthreshold
through-current actively clamping the over-swing — the same subthreshold
physics the cliff probe showed missing, here costing 3.6× on hop energy. The
switch/path machinery itself is NOT the problem: the cap-to-cap T6 hop passes
to 0.14 pp (§4.4). Consequence for T2: bank-hop energy at the dV=1.0 design
point must keep coming from the transistor tier
(`qal_hop_corrected.json` / `qal_isocurrent.json`), with the behavioural tier
carrying only the per-gate settle terms, until the cell gains a subthreshold
conduction term and a rail-side parasitic.

**Speed at this scale (measured)**: behavioural hop deck 0.5 s (+ 4.0 s zero
probe) vs 12.95 s for the identical transistor deck — ~26× at 8 gates + switch
(overhead-dominated; the C6288 result in `bfit/benchmarks/perf.md` sets the
block-scale expectation of ×93–200 at 10k transistors).

## 5. What each parameter is fit against

Nothing here has been through `bfit` yet; this is the intended mapping.

| Parameter | Reference |
|---|---|
| `RON_P` **FITTED 2026-09-26** (=6229, at T=1 ns only, holdouts recorded §4.2), `RON_N`, `CY` | `qal_a1b.py:44-46` (8-point measured table, `C·dV²=3.600 fJ` at `:30`); deck pattern `qal_a1b_example.cir:9-11` |
| `VTP` **FITTED 2026-09-26** (=0.50 — the corrected cell stalls at exactly VTP, so it reads directly off the anchor; §4.1 T4(b) PASS), `VTN`, truth table | `qal_nand_tt_{00,01,10,11}.cir` (real SG13G2 pMOS w=1.12u / nMOS w=0.74u on a PWL rail); stall at `qal_nand_adiabatic.py:21-25`; truth table `:41` |
| `RON` (hop) | `qal_trackC_ron.cir` — a `.dc` on a real `sg13_lv_nmos` w=10u at Vgs=1.2 → **60 Ω**, ~1/W (`qal_trackC.py:31`) |
| hop loss vs Q | `qal_trackC.py:32` — **validated, §4.4** |
| `VTAU`, `CJ`, top-up sizing | `qal_twobank_recycle_topup.cir`; `qal_twobank.py:36-37` |
| dual-rail data-independence | `qal_a1f_dualrail_{matched,mismatch}.cir`; `qal_a1f_inductive.py:74-76` |
| `DELVTO` mismatch MC | `qal_a3_mc.cir:27,35` (`DELVTO={AGAUSS(0,kvt*3.0697e-03,1)}`), `:52` `.SAMPLING useExpr=true` |

**Do NOT fit energy to `qal_nand_adiabatic.py:43` `EDISS_TREND`.** Its own
docstring (`:27-34`) declares those numbers **CONTAMINATED** — the pc-only
integral misses the fixed-well second supply port, pMOS parasitics are 10-30 % of
CL, and recovery is incomplete. Trend only; magnitude from A1b.

`sigma_Vt` correction for the record: the campaign brief states 3.42 mV, but the
deck says `A_Vt/sqrt(W*L) = 3.5 mV·um / sqrt(10u·0.13u) = 3.0697e-3 V`
(`qal_a3_mc.cir:5`, used at `:27,35`). Use the deck's value with its geometry.

---

## 6. Xyce / PyMS rules these cells obey (all measured, several newly)

* **Every `ddt()` alone in its contribution.** A statement mixing `ddt` with a
  non-`ddt` term is silently rewritten as a pure charge contribution
  (`ginac_emitter.py:1271-1288` extracts the `ddt` argument and rebuilds the whole
  statement). No warning, no error, wrong answer.
* **One module per `.va` file. NEW, measured 2026-09-24.** A two-module file
  registered only the first: `Netlist warning: .HDL: compiled and registered
  mm_one` followed by `Netlist error: Unrecognized parameter B for device
  YMM_TWO!X2`. This is why the dual-rail variant is a separate file rather than a
  parameter — the Y-device port list is positional, so `(yt,yf)` replacing `y`
  cannot be a switch on one module.
* **No `$` comments on `.measure` lines. NEW, measured.** A trailing `$ comment`
  makes Xyce reject the measure outright (`Error in .MEASURE line. Could not parse
  measured variable` / `Incomplete .MEASURE line`). Strip them.
* **`.tran ... UIC` is mandatory.** With `ddt` inactive at the DCOP the operating
  point starts the integrator at `Rleak·ESCALE·pdiss` (a predecessor probe read
  5e23). The cells carry their own weak `GLK_E` anchor so decks need no external
  `Rleak` resistors per monitor node — but UIC is still required.
* **Smooth the returned-power rectifier.** A hard `if (pret<0) pret=0` clamp has a
  discontinuous derivative exactly at `prail=0`, which is where t=0 sits;
  **measured**, it made the dual-rail cell abort at t=0. `qal_gate.va` uses
  `pret = -prail*0.5*(1 - tanh(prail/PSCL))`. Verified numerically benign: the
  smooth form reproduced the hard-clamp sweep to 4-5 significant figures.
* **No `idt()`/`idtmod()`** (absent from all of `PyMS/vae/`), **no `$abstime`**,
  **no `@(cross())`** (`bfit.py:247-249`), **no `$strobe`/`initial_step`**
  (parsed then skipped, `ginac_emitter.py:1159-1163`). Energy is therefore exposed
  as electrical **nodes**, which is also what makes it usable by `.measure`,
  `.print`, and netlist B-source summation.
* **No Verilog-A inductor.** It does not compile under PyMS and fails
  silently-wrong (GiNaC build error in the log, device dead, Xyce continues). L,
  damping R, flycaps and rails stay netlist elements.
* **Never `gmin` or `vt` as parameter names** — reserved as Xyce `.param` names.
  These cells use `GM0` and `VTN`/`VTP`.
* **Clear the PyMS cache when editing a `.va`.** `/tmp/pyms_vae_cache` (and
  `~/.vae/cache`); `qal_a3_mc.cir:9-10` records the MC form of the same trap
  ("stale-shell → silent sigma=0"). Any fit loop **must** clear it per candidate
  or Nelder-Mead optimises against a frozen model.
* **Source names must differ from node names.** With a source named like its node,
  Xyce silently returned the source *current* for `V(node)`.

### Open toolchain defect: the dual-rail cell's third integrator

`qal_gate_dr.va` declares `eq` as a **port that carries no contributions**. That
is deliberate and load-bearing. Bisected:

* **Adding** the `eq` integrator aborts every pattern with `Maximum number of
  failures at time 0`. Not the integrand (`pret = 0.0`, a literal, aborts too),
  not `ESCALE` (1.0 aborts), not `PSCL` (1e-9…1e-2 all abort), not the monitor
  B-sources, not the cross-coupling (gating pull-ups from the inputs aborts too),
  not having two rail-driven outputs, and **not node count** — `qal_gate.va` runs
  with three integrators at 11, 12, 13 and 14 nodes.
* **Removing** the `eq` port also breaks it: at 11 ports even a=b=1, which solves
  fine at 12 ports, aborts.
* The 12-port list with `eq` present-but-unused solves **all four** patterns.

Almost certainly a PyMS codegen/indexing artifact, **root cause not established**.
Recovery is still measured exactly, because all gates share one power clock so all
draw is on the up-ramp and all return on the down-ramp:
`E_drawn = MAX(V(er))`, `E_returned = MAX(V(er)) − V(er)@end`. Validated against
the `eq` integrator on `qal_gate.va`, where both routes exist: **10.2243 fJ vs
10.2242 fJ**, agreement to 1e-5.

---

## 7. NOT VALIDATED — do not build on these

* **Fit status (2026-09-26): `VTP` and `RON_P` are fitted (see §4 header);
  `RON_N`, `VTN`, `CY`, `CIN` are still seeds.** `bfit` itself has not been run
  on these cells (its energy-fitting defects below still stand); both fits were
  1-D reads against single T0 anchors with holdouts recorded.
* **T2/T3 settle-loss law: PASSES at ±13 % only inside 500 ps–2 ns** (§4.2),
  degrading to +21 %@200 ps / −29 %@5 ns; the residual is a SHAPE error (clean
  1/T vs the transistor's sub-1/T tail = missing subthreshold/leak physics), so
  do not quote the behavioural cell outside that window without the band.
* **T4(a) recovered fraction has no nominal.** `qal_ecrl_gate.py` (the recovering
  ECRL reference) **exists but has produced no numbers**: its log
  (`qal_ecrl.log`) stops after the header, `qal_ecrl_measured.json` was never
  written, and no Xyce process is running. So the dual-rail cell's
  recovered-fraction and the §4.3 prediction that ECRL still strands at `|Vtp|`
  are **unanchored**. Running that script is the single highest-value next step.
  *(Note: the campaign design brief states no recovering deck exists anywhere in
  `qal/` — that is now stale; the script was added at 17:30 today.)*
* **T4(b) stall level: PASSES post-fix** (§4.1) — 0.4996–0.5058 V, T-independent,
  vs the ~0.5 V anchor at a 50 mV bar.
* **T4(c) is NO-GO on seeds** (3.47 % vs < 2 %), and the reference it is being
  compared against may be the wrong one (§4.3).
* **T5 not fully run.** The X boundary appears and the dual-rail truth table is
  correct, but the single-ended truth table over all 4 patterns at
  `T ≥ 4·RC` was not swept.
* **T7 (6-stage chain), T8 (speed vs transistors), T9 (DELVTO/`.SAMPLING` MC on a
  custom `.va`) NOT ATTEMPTED.** In particular T9's prerequisite — that a *user*
  `.va` instance param can be driven by `AGAUSS` the way PSP103 device params can
  — remains **untested**; `DELVTO` is wired into both gate cells but never
  exercised.
* **NO SUBTHRESHOLD CONDUCTION — now the single most expensive omission,
  MEASURED twice (2026-09-26).** The overdrive clamps are hard zeros below
  `VTN`/`VTP` and the only leak is the linear `GM0=1e-12`. Consequences:
  (a) the functional cliff is a step where silicon grades (0 % vs 34.8 %/77.1 %
  below the cliff, §4.5); (b) the 8-cell bank hop under-predicts per-hop energy
  3.6× at the dV=1.0 design point because silicon burns ~8.9 fJ of
  near/sub-threshold clamping current inside the gates during the hop (§4.6);
  (c) the settle law's long-T tail is −29 % at 5 ns (§4.2). A subthreshold
  exponential tail on the overdrive (with its own fitted slope) is the next
  model-form change, and it must be re-validated against ALL of §4 when it
  lands.
* **The bank-hop composition needs a rail-side nonlinear parasitic.** The
  deck-owned linear `CBANK` reproduces the slow-ramp C_eff but not the dynamic
  charge absorption (silicon bank: ~34 fC by 0.61 V vs the composed 36 fF
  linear plant reaching 0.907 V, §4.6). Until then bank-level hop energy stays
  T0-sourced.
* **Pull-up parasitic capacitance to the rail is NOT modelled.** A `CPC` branch
  was deliberately omitted because its `ddt` current cannot be recovered as a real
  variable for the `prail` integral, which would break the exact closure identity.
  `qal_nand_adiabatic.py:32` cites pMOS parasitics at 10-30 % of CL, so this is a
  real omission — fold it into `CY` at fit time and treat absolute energies as
  missing that term.
* **`CIN` is unconstrained.** Every existing reference deck drives inputs from
  ideal sources, so nothing yet pins the input capacitance. Needs a
  stage-drives-stage deck.
* **Only 2-input INV/NAND2/NOR2 exist.** XOR, AOI/OAI, MUX and DFF — needed for a
  56-cell `sha_slice`, let alone Vortex — are not covered. Compound cells need
  topology-derived instances (the `stdcell2bfit.py` approach).
* **Reference decks #1, #3, #4 and #5 from the design still do not exist**: the
  A1b-redo at the gate with *all* supply ports counted; the input-loading deck for
  `CIN`; the per-branch energy-split deck; and the flycap-recharge steady-state
  deck. Per `qal_crossover_map.py:33` the energy-recovering generator is UNBUILT
  and as-built `eta ~ 1/3`, so **every QAL block total must quote the generator
  term as a separate explicit line** until #5 exists.
* **`bfit` cannot fit energy as it stands.** Its objective has an absolute `+1e-9`
  floor that reports a 4.8× femtojoule error as `+0.0%`; its feature kinds are
  amplitude-only (no `final`, and QAL rail energy is non-monotonic); and the Xyce
  driver cannot print a current or read `.mt0`. A patch exists at
  `/home/claude/bfit_energy_fixtures/bfit_energy_feature.patch` against a **copy**
  — the repo is unmodified, and its `integ` and `.print`-passthrough hunks are
  untested.
* **VACASK, OpenVAF and ngspice are not installed** in this container, so those
  are paper options; Xyce `.hdl`/PyMS is the only live path.

### Files changed outside this directory
None. Only `/usr/local/src/stat-sim/qal/va/` was created. PyMS cache entries under
`/tmp/pyms_vae_cache` were deleted and rebuilt for the cells developed here.
