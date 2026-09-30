# Amendments to `qal/fastwave/p2/PRE_REGISTERED.json` (PHASE 2)

Pre-registration: sha256 `ca778b4ea1c65e2a6fa4fc66498ead5e91d3703f2cb0a4b665bc3b2ab0dc03b5`,
23056 B, written **2026-09-29 21:45:52 -0700**, after `p2/DISK_STATE_BEFORE.txt`
(21:42) and before any Phase-2 deck. Phase 1's pre-registration and its ten
amendments are inherited verbatim and are not reopened here.

Each amendment records the fact that forced it and the mtime proving it preceded
the rows it affects.

---

## P1 — A SEVENTH BANK IS ADDED AS AN UNSCORED TERMINATOR LOAD

**What the pre-registration said.** Section C fixed `banks: 6`.

**What forced the change, before any chain deck was written.** In a 6-bank chain
bank 6 has no successor, so its four outputs drive only their own `CL = 2 fF`
while banks 1–5 each drive a successor's two input-inverter gates, that
successor's four transmission-gate source taps, and — the thing Phase 1
explicitly booked rather than paid — that successor's pass-gate **crowbar**
(Phase 1 measured 176 fC per transparent cell out of its own input, because both
TG pMOS conduct while the receiving rail is below the select separation). The
deepest bank would therefore have been the **least** loaded bank in the chain,
and the sustained beat is a max over depth. That is a systematic flattery at
exactly the depth the verdict rests on.

**The change.** Seven banks are built. Bank 7 is a real bank with its own tank,
its own inductor, its own switch triple and its own place in the schedule, so
bank 6 sees a genuine successor. **Only banks 1–6 are scored** against K1–K6,
exactly as pre-registered; bank 7's own value and settling are reported for the
record and are explicitly *not* gated, because bank 7 is itself the one bank with
no successor.

Bank 7 inherits bank 1's rotate and forms (`rot = 2`, `XOR/XNOR/XNOR/XOR`); the
value table extends to `y7 = (1, 1, 0, 0)` with the same uniform 3 RESTORED + 1
TRANSPARENT mix as every other bank, so the terminator is not a different kind of
load from the banks it terminates.

**Direction of the change: HARSHER.** It adds load to the deepest scored bank and
adds devices to the deck. It cannot make any scored row faster.

---

## P2 — THE `C_bank` USED FOR THE TANK IS PER-BANK-MEASURED, AND THE SPREAD IS REPORTED

**What the pre-registration said.** Section G required `C_bank_in_situ` to be
MEASURED in this directory, as one number per wire setting, metered at the rail
source per Phase 1 AMENDMENT A4.

**What forced the refinement.** The seven banks do not have identical rail loads:
their forms differ, their rotate lengths differ (`rot` ∈ {1, 2, 3}, and at the
PRIMARY wire setting a rotate segment is 11.29 fF against a straight segment's
0.84 fF), and the chain's own data word differs at every depth. A single number
would either over- or under-size six of the seven tanks.

**The change.** The rail load is measured **per bank, in situ** — bank *k* ramped
with its own forms, its own data, its own output wire segments and a real bank
*k+1* receiving them — and the tank is sized `CT_k = m · C_bank_k`. The seven
measured values and their spread are reported on every row. A uniform-tank
control at the mean is run at the primary point so the choice is measured rather
than argued.

---

## P3 — THE ZCS ZEROS ARE RE-PROBED PER BANK AT EVERY BEAT PERIOD, AND THE RETURN ZEROS ARE NOT

**What the pre-registration said.** Section G: every zero MEASURED per bank per
row by a probe deck in which that bank's switch closes at its beat and never
opens.

**The refinement, stated with its cost.** The **rise** zeros are re-probed per
bank at every `T`, because at short `T` bank *k* closes while bank *k−1* is still
moving and the zero genuinely shifts. That is 7 probe decks per `T`.

The **return** zeros are probed once per configuration and reused across `T`,
because the return fires `H·T` after the rise — four beats after every value in
this deck has already been read — so a return-cut error strands charge and
perturbs the energy ledger but cannot move a measured stage time. Any row whose
`|IZQ_k|` exceeds the K5 gate is re-probed rather than reported, and any row where
a return-cut error could reach a scored checkpoint is named.

This is a deliberate accuracy-for-runtime trade in the **energy** ledger only,
and energy gates nothing in this phase.

---

## P4 — THE SLOW-RAMP BANK CAPACITANCE WAS 30–51% A DC PATH, NOT A CAPACITANCE

**What the pre-registration said.** Section G: `C_bank_in_situ` MEASURED in this
directory, metered at the rail source per Phase 1 AMENDMENT A4.

**What the measurement said.** The first calibration returned 98.6–179.0 fF for
the seven in-situ banks against Phase 1's 52.77 fF for a bare N=4 bank, and its
secant capacitance **never flattened**:

| bank 1, W2 | 0.6 V | 0.8 V | 1.0 V | 1.2 V | 1.4 V | 1.65 V | C_diff(0.9–1.1) |
|---|---|---|---|---|---|---|---|
| C_secant, fF | 38.8 | 67.3 | 87.4 | 111.3 | 125.8 | **145.8** | **201.9** |

Phase 1's bare bank rose only 49.3 → 52.8 fF over the same span — it flattens,
which is what a capacitance does. Mine rose **+116%** from 0.8 V to dV, and
`C_diff > C_secant`. That is the A4 signature exactly.

**The decisive test.** Doubling the ramp from 4 ns to 8 ns changed the answer:
bank 5 read 179.0 fF at 4 ns and **269.7 fF at 8 ns**. A capacitance does not
depend on how slowly you charge it. Every bank moved the same way.

**Mechanism, and it is real physics.** The downstream bank's rail sits at 0 while
bank *k* transfers, so both of its transmission-gate pMOS conduct (their n-well is
on `vhi`, their gates on select nodes generated on a rail that is at 0) and its
cell **shorts its two data inputs** — which are two of bank *k*'s outputs. When
they differ, a DC current flows from bank *k*'s rail, through its restored cell,
along the A net, through the successor's crowbar, back along the B net and down
bank *k*'s own nMOS to ground. It is rail current, so metering at the rail source
does not remove it, and it is resistive, so it is not capacitance.

**The fix, which is exact rather than a fit.** Every bank is calibrated at TWO
ramp rates. For a linear ramp

  Q(T) = Q_cap + T·K,  K = (1/dV)·∫I_dc(V)dV

because stretching the ramp stretches the DC term in exact proportion and leaves
the capacitive term alone. Two rates give both terms with no fitting. MEASURED:
**K = 0.018–0.037 µA** (bank 6: 0.001 µA), and

| | Phase 1 bare | in situ, no wire (W0) | in situ, PDK wire (W2) |
|---|---|---|---|
| mean C_TRUE, fF | 52.768 | **68.829** | **81.586** |

so the successor's input load — the thing Phase 1 booked as an ideal source — adds
**+30.4%**, and the interconnect adds a further **+18.5%**. Per-bank spread 65–74%
(46.7–113.8 fF), which is why AMENDMENT P2's per-bank tanks were needed.

**And it corrects Phase 1's own worry in QAL's favour.** Phase 1 wrote that the
crowbar "is a BOOKING THAT HIDES A COST". Measured, the DC part is 0.02–0.04 µA,
i.e. **~0.004 fC over a 200 ps beat** — negligible at wave speed. It is a metering
hazard for a 4 ns calibration ramp, not a speed cost for the wave.

**Also fixed here:** the instrument check had been a hand re-implementation of
Phase 1's `cbank_deck` and came back at rel 7.05e-07, not 0, because it dropped
two of Phase 1's 1 F integrators. Re-implementing an instrument is not checking
it. Phase 1's `fw.cbank_deck` and `fw.cbank_extract` are now **imported and
called**, and the check is rel **0.000e+00** on every quantity.

---

## P5 — THE BEAT DECK DROPS THE RETURN CUTS, AND THE BOUNDARIES ARE PROVABLY UNCHANGED

**What forced it.** The full seven-bank H=4 deck at T=300 ps **did not converge**.
It stopped at t ≈ 1831 ps, where three switch events with 2 ps edges land inside
6 ps of one another: bank 6's rise cut at 1835.4 ps and bank 2's return cut at
1837.6 ps. The A8 retry at 4× resolution then advanced only 306 ps in 16 minutes
of a loaded box, so it is not a usable route.

**Why the returns can be dropped without touching a scored number.** The
inherited stage boundary is `bnd_k = min(c_k + T, r_k − EDGE, r_{k−1} − EDGE)`
with `r_k = c_k + H·T`. For H ≥ 3 that is exactly `c_k + T` for every k, since
`(H−2)·T ≥ 2` holds for every T in this grid. No return can therefore fall inside
any scored window. VERIFIED by computation as well as by argument: the boundary
dictionaries of the returns-enabled and returns-disabled schedules are **identical
at T = 150, 200, 250, 300 and 400 ps**, and `tend` falls 28–39%.

**The change.** Every reported beat, value, settling and separation number comes
from a BEAT DECK with the returns disabled — half the switch events, and it
converges. The returns, the ZCS return cuts and the energy ledger are measured on
a separate LEDGER DECK at the winning T; if that deck will not converge it is
reported as a **named convergence failure**, never estimated, and K5's `IZQ` gate
is reported as untested rather than passed.

**Direction:** neutral on the scored checkpoints (proved identical), and it
removes NOTHING from the chain's load — all seven banks, all tanks, all cells and
all interconnect are present on the beat deck.

---

## P6 — ENVIRONMENT, not an amendment

The box is shared and heavily loaded: 16 cores with 6–13 concurrent Xyce processes
belonging to other QAL runs (`p_aes_*`, `p_ks8_*`, `p_n64_*`, `c_n64_*`,
`t_twin_*`, `p_m10_*`, `p_n8_*`), 8 of 48 GB swap in use. Every wall-clock figure
in this directory is inflated by that and none of it affects an electrical result.
One consequence is procedural and worth recording: a 58-minute `timeout` wrapper
killed the first seed row after its probes had all completed, so the rise and
return zeros were re-extracted from the probe waveforms already on disk rather
than re-simulated.

## P7 — A SYNCHRONOUS-RAIL ARRANGEMENT WAS ADDED, because the pre-registered one is structurally dead

**What the measurement said.** All four pre-registered skewed rows (T = 200/250/300/350 ps) failed every scored bank by 100–524 mV, and bank 1 — whose inputs are IDEAL 1.20 V sources and whose binding cell is fully selected — delivered only 62.8% of its own rail. `DIAG_CROWBAR.json` then found the cause as a DC measurement, not an argument: with the successor's rail at 0 its select node `bb` cannot rise (measured 0.262 V), so BOTH its transmission-gate pMOS conduct and it ties the predecessor's output through TG1's pMOS to its own `y`, which TG2's pMOS ties to a grounded `ab`. The predecessor's output draws **−78.6 µA** (bank 1) and **−82.5 µA** (bank 3) of DC current and sits at 1.400/1.386 V instead of 1.648 V. With the successor's rail at dV the same output draws **−0.000 µA** at 1.6476 V. Identical at W2 and W0, so it is **not the interconnect**.

**The change.** A second arrangement is run in which every bank's rail is raised together and the wave is carried by the DATA alone. It removes the crowbar by construction. Both arrangements are reported; neither is dropped.

## P8 — AN INHERITED INSTRUMENT DEFECT IN THE PER-DECK COMPANION

Phase 1's companion drove its input UPWARD so its output FELL, while the measure asked for `V(o_zc)=1.08 RISE=1` and the committed reference 57.1428 ps is `cmos.cir`'s **T90R2**, the RISING output of a FALLING input. Three different things. Every Phase-2 skewed deck returned `T90ZC = FAILED`. Fixed by driving the input downward, reproducing `cmos.cir`'s `or2` arm exactly; the per-deck check then reads **57.1424–57.1428 ps, rel ≤ 5.3e-06**, and is a real check. The four skewed rows predating the fix carry `T90ZC = FAILED` and are labelled.

## P9 — THE RESTORING BANK, and it is INSIDE the user's stated budget

The user allowed "a maximum of two levels of transistor logic per bank". The TG-XOR spends one. Spending the second on an output inverter powered by the bank rail makes the bank level-restoring. The cell's FORM is flipped so the composite output is bit-identical to the pre-registered value table — the logic does not change, only the gain. Re-calibrated: the restoring bank's in-situ rail load is **117.05 fF at W2** against 81.59 fF, i.e. 1.43×.

## P10 — THE SYNC ROWS STAGGER THEIR CLOSES BY 5 ps

Seven switch closes at the same instant did not converge (the deck stalled at t = 198 ps; three of five sync rows failed). The sync rows stagger them by 5 ps — 4% of a 125 ps hop, against the 300 ps of crowbar exposure the skewed arrangement carries. Declared numerical measure, size reported on every row.

## P11–P14 — THE VALIDITY CRITERION MOVED THREE TIMES, AND TWO OF THE READINGS WERE ARTEFACTS

**P11.** Phase 1's rule — "correct AND STAYS correct through the stage boundary" — is right for a skewed deck and wrong for the synchronous one, where the boundary is one late instant common to all seven banks and the isolated rails have decayed 40–55% by then. Replaced by an interval scan.

**P12 — an artefact I nearly reported as physics.** With the scan capped at one beat, every correct interval ENDED EXACTLY AT THE CAP (bank 1 at T = 400: `[404.0, 600.0]` against `bound = 600.0`), so "hold" measured where I stopped looking, and the cascade margin came out identically equal to minus the successor's own level time — the algebraic signature of truncation, not a fact about the circuit. I had already drafted the reading "the rail decays faster than the wave propagates". **It is false.** Re-measured to the end of the deck, banks hold their correct values for **2049–2796 ps** against the 326–436 ps a successor needs: the cascade hold condition PASSES.

**P13.** The ARRIVAL had to come from the extended window too — capped at one beat, W0/T=400 bank 5 read "never correct" while it in fact holds a correct value for 765.4 ps.

**P14 — the definition, settled once and not moved again.** ARRIVAL(k) = the start of the **FIRST** contiguous correct interval searched from bank k's own rail start to the end of the deck. A "longest interval" rule was tried and MEASURED to misbehave: at W2/T=400 bank 3 it skipped a real 151.1 ps interval at 1247.6 ps for a later, longer one at 2234.9 ps that is the rail drifting into a state that happens to read correct, inflating that row's beat from 436 ps to 2194 ps. Every number in RESULTS.json uses the P14 definition.

## P15 — THE SEPARATION AT ARRIVAL IS PINNED BY CONSTRUCTION

Arrival is *defined* as the first instant the worst margin exceeds 3σ, so the margin at arrival is ≈3σ on every bank of every row and carries no information. The separation-by-depth table therefore reports the **peak margin reached inside the correct interval**, which is the free quantity.
