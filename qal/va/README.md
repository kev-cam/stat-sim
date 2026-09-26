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
| `qal_gate.va` | single-ended settling QAL gate; INV / NAND2 / NOR2 via `TOPO`; 3 energy integrators; **softplus subthreshold tail** | **source-reference FIXED + subthreshold tail LANDED 2026-09-26; VTP + RON_P + NSS fitted; cliff now GRADED; stall re-anchored as measured log-t droop; residuals.json v2** |
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
**`VTP=0.50` FITTED** against the T0 stall anchor (`qal_nand_adiabatic.py:21-25`);
**`RON_P=6229` FITTED at T=1 ns ONLY** against the A1b measured law (holdouts
below); **`NSS=1.85` FITTED (subthreshold slope factor of the softplus tail,
2026-09-26)** by equal-weight pp-LSQ over the two below-cliff settle anchors —
full trajectory and the measured insensitivity of the stated third target in
`residuals.json` v2 `fit_provenance`; `PHIT=0.02585` is kT/q at 300 K, a
constant, not a fit knob; `RON_N`, `VTN`, `CY`, `CIN` remain **UNFIT SEEDS**.
The softplus (`ov_eff = n·vT·ln(1+limexp(ov/(n·vT)))`, coded overflow-safe)
reproduces the strong-inversion linear-overdrive law with the SAME `RON_P`
by construction — measured: the §4.2 grid is bit-identical pre/post tail.
VACASK / ngspice / OpenVAF are still not installed (checked 2026-09-26), so
Xyce is the only live engine lane — per-engine reporting a la
`bfit/benchmarks/perf.md` is not yet possible here.

> **The stall re-anchor (2026-09-26, transistor MEASURED).** The committed
> stall anchor deck ends AT pc=0, so "~0.5 V" carried zero information about
> what happens after arrival. An extended-hold PSP103 run (tt00 + 4 ns tail)
> shows **silicon droops too**: Y = 0.5139 at pc=0, then 0.4945 / 0.4821 /
> 0.4663 / 0.4420 / 0.4227 V at +0.2/0.4/0.8/2/4 ns — a log-t decay,
> ~24 mV per e-fold (an effective stall-droop slope n≈1.0). The v1 "stalls at
> exactly VTP, T-independent" PASS was therefore an artifact of the missing
> tail. The v2 check compares droop at MATCHED offsets (below).

### 4.1 Single-ended `qal_gate`, A1b ramp-time grid (fitted params)

`TOPO=1` (NAND2), `a=0`, `b=Vdd` → exactly one pull-up leg, no pull-down.
`Vdd=1.2 V`, `CY=10 fF`, `C·dV² = 14.400 fJ`. Energies in fJ
(`probe_runs/probe_T*.cir.mt0`):

| T (ps) | Y@hold | Y@end | Ediss | Erail | Eret | Edrawn | recov% | clos% |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 20 | 0.2483 | 0.4397 | 4.1634 | 5.1297 | 0.0001 | 5.1297 | 0.0% | 0.009% |
| 50 | 0.5271 | 0.6754 | 6.9551 | 9.2346 | 0.1331 | 9.3677 | 1.4% | 0.021% |
| 100 | 0.8234 | 0.6528 | 9.1462 | 11.2742 | 0.9135 | 12.1876 | 7.5% | 0.040% |
| 200 | 1.0796 | 0.5582 | 9.4274 | 10.9812 | 2.2433 | 13.2245 | 17.0% | 0.052% |
| 500 | 1.1961 | 0.4706 | 7.7413 | 8.8427 | 3.6067 | 12.4494 | 29.0% | 0.073% |
| 1000 | 1.1999 | 0.4247 | 6.1450 | 7.0393 | 4.4186 | 11.4579 | 38.6% | 0.112% |
| 2000 | 1.1999 | 0.3890 | 4.7267 | 5.4743 | 5.0519 | 10.5262 | 48.0% | 0.173% |
| 5000 | 1.1999 | 0.3452 | 3.4902 | 4.0772 | 5.6243 | 9.7015 | 58.0% | 0.223% |

* **T1 closure: PASS** — worst residual **0.223 %** at T=5 ns at the deck's
  default tolerances (≤0.173 % for T≤2 ns; v1 was 0.184 %). MEASURED to be
  solver tolerance, not bookkeeping: with `RELTOL=1e-6 ABSTOL=1e-13` the T=5 ns
  residual is **6.5e-8 (0.0000065 %)**; step-halving alone (TR/400) does not
  move it (0.219 %). The identity is exact.
* **T4(b) stall, RE-ANCHORED (see §4 header): PASS on the corrected check.**
  At pc=0 arrival the model reads **0.5199 V vs silicon 0.5139 V (+6 mV)**.
  Droop at matched offsets after pc=0 (TR=1 ns): model 0.4777/0.4539/0.4250/
  0.3849/0.3542 V vs silicon 0.4945/0.4821/0.4663/0.4420/0.4227 V at
  +0.2/0.4/0.8/2/4 ns → **−17/−28/−41/−57/−69 mV**; the model droops ~1.7×
  faster (~41 mV/e-fold = the cliff-fitted NSS=1.85, where silicon's
  stall-droop slope reads n≈1.0 — recorded in §7 as the linear-Vds tail
  limitation). The `Y@end` column above is NOT T-dependence: those values
  (0.4706/0.4247/0.3890/0.3452 at 0.4/0.8/1.6/4 ns after pc=0) lie on the one
  log-t droop curve — same corrected T-independence silicon shows.
* **The central requirement, unchanged** (T=1 ns `.mt0`, post-tail): V(er)
  rises to **11.4579 fJ** at the top of the ramp (`EUPRMP`) and falls to
  **7.0393 fJ** at the end — the rail-current integral ran NEGATIVE on the
  down-ramp. The independently rectified integrator agrees: `ERET = 4.418598`
  vs the 4.418608 fall (**0.0002 %**; T=5 ns: 5.624304 vs 5.624363, 0.001 % —
  bar 0.16 %, PASS). No `f_adia` anywhere in the cell (grep re-verified).
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

* **This table is BIT-IDENTICAL pre/post the subthreshold tail** (re-run
  2026-09-26 with NSS=1.85): the pinned gate keeps the overdrive ≥ 0.7 V, deep
  in the softplus's linear region, so the strong-inversion constraint (`RON_P`
  reproduced, T=1 ns untouched at −2 % WITHOUT refitting) is verified by
  MEASUREMENT, not just by construction.
* **The −29 % @5 ns row was a stated fit target for the tail and turned out
  INSENSITIVE to it** (0.0243 flat over NSS 1.5–2.0, measured during the fit):
  in this vehicle — as in silicon A1b, whose switch gate is also held on —
  there is no subthreshold device in play. The v1/§7 attribution of the long-T
  gap to "missing subthreshold physics" is **RETRACTED**; the silicon sub-1/T
  tail's source is unidentified (candidates: PSP103 gate/junction leakage
  floor — unverified). The residual stands.
* **Stated tolerance, honestly**: ±13 % over 500 ps–2 ns (a 4× window around
  the 1 ns design ramp), degrading to **+21 % at 200 ps** and **−29 % at 5 ns**.
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

| dV | rail (V) | model settle | T0 settle | role |
|---:|---:|---:|---:|:--|
| 0.6 | 0.3725 | **29.8%** | 34.8% | **FIT (NSS)** |
| 0.8 | 0.4669 | **87.7%** | 77.1% | **FIT (NSS)** |
| 1.0 | 0.5829 | 99.9% | 100.0% | holdout |
| 1.2 | 0.7179 | 100.0% | 100.0% | holdout |

The cliff LOCATION is exactly right (collapse iff the rail cannot clear
`VTP=0.50`; the usable floor lands at dV≈1.0 as measured), and with the
subthreshold tail the cliff now **GRADES** as silicon does (v1: 0 %/0 % hard
step). Residual: −5.0 pp / +10.6 pp on the two below-cliff points — these are
the NSS fit targets and no single n closes both (s@0.3725 wants NSS≈1.95,
s@0.4669 wants ≈1.49; pp-LSQ picked 1.85): the model's graded edge is
SHALLOWER than silicon's between the two rails. Two recorded contributors
(§7): the tail's linear-Vds form (silicon weak-inversion current saturates in
Vds), and a probe-fidelity mismatch — this probe ramps monotonically to the
END rail value while the transistor bank RANG above it during the hop
(VBpk 0.611 vs V_B_end 0.576 at dV=1.0, `qal_isocurrent.json`), so silicon
settled part of its fraction at a higher instantaneous rail than the probe
ever presents.

### 4.6 8-cell bank hop vs the measured dV=1.0 row — QUANTITATIVE FAIL, root cause now MEASURED BY ELIMINATION

`run_bankhop.py`, mirroring `qal_hop_gates.py` hop_deck: bank A (35.979 fF, the
measured C_eff) → L=277.8 nH + Rs=10 → behavioural switch (`qal_hop`, RON=15,
opened at the MEASURED I(L) zero) → bank B = the rail of 8 `qal_gate` INVs
(CY=2f, inputs alternating), deck-owned CBANK=28 fF making the composed C_eff
match the transistor's 35.979 fF. T0 anchor: `qal_isocurrent.json` dV=1.0 row,
regenerated and CONFIRMED this session (VBEND 0.5763 / VAEND 0.0485 / IPK
195.18 uA reproduce the committed row exactly; deck + log in the session
scratchpad `t0hop/`):

All rows HOLDOUTS (never fitted). Post-tail (2026-09-26, NSS=1.85); v1
pre-tail values in parentheses where they differ:

| | model | transistor | Δ |
|:--|---:|---:|---:|
| t_zcs (ps) | 227.6 (227.6) | 342.0 | **−33.5%** |
| Ipk (uA) | 237.0 (236.9) | 195.2 | +21.4% |
| V_A_end (V) | 0.0910 (0.0922) | 0.0485 | +88% |
| V_B_end (V) | 0.9079 (0.9073) | 0.5763 | **+57.5%** |
| V_B_peak (V) | 0.9389 | 0.611 | +53.7% |
| E_hop (fJ) | 3.0050 (3.0203) | 10.7416 | **−72.0%** |
| per gate-settle (fJ) | 0.3756 (0.3775) | 1.3427 | −72.0% |

**Prize question, answered against PRE-COMMITTED thresholds** (recorded before
the run: promote hop energy/timing to T1-with-band iff |err| ≤ 15 % on E_hop
AND ≤ 10 % on t_zcs): **NOT MET** — −72.0 % / −33.5 %. Bank-hop energy and
timing **stay T0-sourced** (`qal_hop_corrected.json` / `qal_isocurrent.json`).

**The elimination finding — this is what v2 bought here.** v1 attributed the
miss to "subthreshold conduction + nonlinear bank C(V)". The subthreshold
conduction is now PRESENT and FITTED, and the hop numbers did not move
(E_hop −0.5 %, t_zcs 0.0 ps): the −72 % is owned by the charge-absorption
physics the composition still lacks — **nonlinear bank C(V)** (+ wp-scaled
switch/well parasitics). The evidence was already in the v1 table and stands:
the model bank sails to VBpk 0.939 V where silicon peaks at 0.611 V while
absorbing ~34 fC (the linear 36 fF plant stores only ~26 fC at 0.611 V) — a
CAPACITANCE shortfall at high V, which simultaneously explains the t_zcs
−33.5 % (π√LC with too-small effective C) and the energy miss (the resistive
near-threshold charging window silicon spends 8.9 fJ in barely exists when
the rail overshoots past strong inversion in a shorter event).

**Do not use the behavioural composition for bank-hop energy yet.** The books
still close on the model side (E_outA 17.8405 = stored 14.8355 + gates 2.7268
+ switch 0.2276 + 0.0506 residue), so this is not bookkeeping. The silicon
side of the picture is unchanged: the bank peaks at only 0.611 V while
absorbing ~34 fC and burns `E_inB − E_stored = 16.26 − 7.35 = 8.9 fJ` inside
the gates during the 342 ps event. What v2 establishes is that the
SUBTHRESHOLD share of that burn is small — the fitted tail reproduced the
graded cliff yet moved hop energy only 0.5 % — so the 8.9 fJ is dominated by
near-threshold RESISTIVE charging of charge the linear plant never absorbs:
the C(V) term. The switch/path machinery itself is NOT the problem: the
cap-to-cap T6 hop passes to 0.14 pp (§4.4). Consequence for T2 (unchanged):
bank-hop energy AND timing at the dV=1.0 design point keep coming from the
transistor tier (`qal_hop_corrected.json` / `qal_isocurrent.json`), with the
behavioural tier carrying only the per-gate settle terms, until the
composition gains a rail-side NONLINEAR C(V) parasitic — now the single
highest-leverage model-form change for the hop (§7).

**Speed at this scale (measured)**: behavioural hop deck 0.5 s (+ 4.0 s zero
probe) vs 12.95 s for the identical transistor deck — ~26× at 8 gates + switch
(overhead-dominated; the C6288 result in `bfit/benchmarks/perf.md` sets the
block-scale expectation of ×93–200 at 10k transistors).

## 5. What each parameter is fit against

Nothing here has been through `bfit` yet; this is the intended mapping.

| Parameter | Reference |
|---|---|
| `RON_P` **FITTED 2026-09-26** (=6229, at T=1 ns only, holdouts recorded §4.2), `RON_N`, `CY` | `qal_a1b.py:44-46` (8-point measured table, `C·dV²=3.600 fJ` at `:30`); deck pattern `qal_a1b_example.cir:9-11` |
| `VTP` **FITTED 2026-09-26** (=0.50; §4.1 T4(b) re-anchored PASS: +6 mV at pc=0 arrival), `VTN`, truth table | `qal_nand_tt_{00,01,10,11}.cir` (real SG13G2 pMOS w=1.12u / nMOS w=0.74u on a PWL rail); stall at `qal_nand_adiabatic.py:21-25`; truth table `:41` |
| `NSS` **FITTED 2026-09-26** (=1.85, weighting band 1.85–1.95; equal-weight pp-LSQ on the two below-cliff settle anchors; trajectory in `residuals.json` v2). `PHIT`=kT/q, constant | `qal_hop_corrected.json` L=400 dV=0.6/0.8 rows (34.8 % @rail 0.37251, 77.1 % @0.46688) via `run_cliff.py`; stall-droop slope measured but NOT fitted (silicon reads n≈1.0 — the 1.7× droop-rate residual is recorded, §4.1/§7) |
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
  1/T vs the transistor's sub-1/T tail), so do not quote the behavioural cell
  outside that window without the band. **The long-T gap's v1 attribution to
  subthreshold physics is RETRACTED** — measured insensitive to the fitted
  tail (§4.2); source unidentified (candidates: PSP103 gate/junction leakage
  floor — unverified).
* **T4(a) recovered fraction has no nominal.** `qal_ecrl_gate.py` (the recovering
  ECRL reference) **exists but has produced no numbers**: its log
  (`qal_ecrl.log`) stops after the header, `qal_ecrl_measured.json` was never
  written, and no Xyce process is running. So the dual-rail cell's
  recovered-fraction and the §4.3 prediction that ECRL still strands at `|Vtp|`
  are **unanchored**. Running that script is the single highest-value next step.
  *(Note: the campaign design brief states no recovering deck exists anywhere in
  `qal/` — that is now stale; the script was added at 17:30 today.)*
* **T4(b) stall level: PASSES on the RE-ANCHORED check** (§4.1) — +6 mV at
  pc=0 arrival; droop tracked within 41 mV to +0.8 ns, 69 mV to +4 ns, but at
  1.7× silicon's rate (the cliff-fitted NSS=1.85 vs silicon's stall-droop
  slope n≈1.0). The v1 "0.4996–0.5058 V, T-independent" PASS is superseded:
  both silicon and the model droop log-t after pc=0; only the pc=0-arrival
  value and the one-universal-curve property are anchored.
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
* **SUBTHRESHOLD TAIL LANDED 2026-09-26 (softplus, NSS=1.85 fitted) — with two
  recorded LIMITATIONS of the shipped form.** Of v1's three consequences:
  (a) the cliff now GRADES (29.8 %/87.7 % vs 34.8 %/77.1 %, §4.5) — fixed in
  shape, ±11 pp in magnitude; (b) the bank hop DID NOT MOVE (−0.5 % on E_hop,
  §4.6) — attribution retracted, see the C(V) bullet below; (c) the −29 %@5 ns
  settle tail DID NOT MOVE — attribution retracted (§4.2). Limitations:
  (1) **linear-Vds tail**: the model conducts I = g(ov)·Vds where silicon
  weak-inversion current saturates in Vds; measured consequences are the
  shallow graded edge (no single n closes both cliff anchors, band 1.85–1.95)
  and a stall-droop rate 1.7× silicon's (silicon's slope reads n≈1.0, §4.1).
  A saturating `(1−limexp(−Vds/vT))` factor is the candidate refinement IF the
  cliff/stall band must tighten. (2) `VTN`'s tail is live with a SEED
  threshold — the nMOS subthreshold leak is unanchored.
* **The bank-hop composition needs a rail-side NONLINEAR C(V) parasitic — now
  the MEASURED dominant hop omission** (§4.6 elimination finding: conduction
  is silicon-shaped and the −72 % barely moved). The deck-owned linear `CBANK`
  reproduces the slow-ramp C_eff but not the dynamic charge absorption
  (silicon bank: ~34 fC by 0.611 V vs the composed 36 fF linear plant sailing
  to VBpk 0.939 V, §4.6). Until it exists, bank-level hop energy AND timing
  stay T0-sourced. This is the next model-form change for the hop.
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
