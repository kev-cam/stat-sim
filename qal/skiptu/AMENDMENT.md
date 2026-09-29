# skiptu protocol amendments

Order of events on disk (mtimes are the proof; `ls -la --time-style=full-iso`):

1. `PRE_REGISTERED.json` **20:29:39** — the ONLY file in the directory at that moment
   (verified and printed at 20:29:42).
2. `instr_anchor.cir` / `instr_probe.cir` 20:30 — md5-verified byte copies of the
   committed `qal/lsweep/h_L15_W30_dv120.cir` / `p_L15_W30_dv120.cir`.
3. `tu.py`, `tuextract.py`, `go.py`, `instr.py`, `analyze.py` — the harness.
4. `INSTRUMENT.json` 20:5x — the digit check, PASS.
5. **This file, clause A1, written BEFORE any top-up row was reported** — the two
   smoke rows that exposed the defect are on disk and are the evidence for it.
6. `rows.json` — the measured rows.

---

## A1 — MY OWN TOP-UP WAS BROKEN, found by my own control, and the fix is a MEASUREMENT

The first two smoke rows (`r_s4_free_T160_dv1200_L5_W10_t24_f0` and
`r_s4_ptu_T160_dv1200_L5_W10_t24_f0`, both on disk) showed the top-up making the
chain **dramatically worse**, not better:

| | rail3 at its boundary | rail4 at its boundary | worst gate stage 4 | min delivered HIGH |
|---|--:|--:|--:|--:|
| free (control) | 0.759065 V | 0.673359 V | 63.19% | 0.4483 V |
| ptu (as first built) | **0.126283 V** | **0.067803 V** | **−31.75%** | 0.2371 V |

MEASURED cause, not inferred: the top-up's delivered charge came out **NEGATIVE**,
−37.718 fC into bank 3 and −16.078 fC into bank 4 (`q_delivered_into_rail_fC`), with
a peak inductor current of 2494.685 µA. The top-up was a net **SINK**. A settling
figure below zero is the signature: `1 − V(o)/V(rail)` goes negative when the RAIL
has been pulled below the outputs, which is exactly what a sink does.

**Why.** I set the freewheel window from an **ASSUMED** rail,
`tfw = t_on*(V_sup/V_rail_est − 1)` with `V_rail_est = 0.5*dV`. That is an assumption
where the campaign's own standing discipline requires a measurement: *"RE-PROBE the
true current zero per L AND PER HOP separately"* — and the top-up inductor **is
another hop**. Once the freewheel nMOS is still conducting past the inductor's true
current zero, the path `rail_k → Ltu → na_k → FW nMOS → ground` runs **backwards** and
pumps the bank's charge into ground. The analytic/assumed window was wrong in exactly
the way the standing note says analytic hop times are wrong (it cites a measured
353.79 ps against an analytic 266.76 ps, 33% early).

**Amended.** The top-up freewheel is cut at its **MEASURED** current zero, found by
the same probe-then-cut protocol the transfer hops already use:

* a probe deck is built per `(scheme, dv, Ltu, wsw, t_on)` in which the top-up on the
  bank under test fires and its freewheel nMOS is turned on and **never turned off**;
* `I(LTU_k)`'s first zero after its peak is found by the committed
  `zero_after_peak` rule (linear interpolation), measured **per bank** because the two
  banks sit at different rails;
* the measured window `tfw_k = t_zero_k − (t_fire_k + t_on)` is then used in the
  reported deck, and it is recorded in every row as `t_freewheel_ps` next to
  `tfw_source = "MEASURED"`.

This can only be described as a defect in my own first build. It was caught because I
ran the free control **first**, as pre-registered, so I had a same-harness number to
compare against; a top-up-only run would have been reported as a QAL result.

### A1 continued — it took FOUR corrections, all of them mine, and all found the same way

The first defect was not the only one. Fixing it exposed the next, and each was caught
by the same method: compare the top-up row against the free control row in the same
harness, and disbelieve any top-up that makes the chain worse. All four are recorded
because all four were live in a deck at some point, and three of them would have
produced a *plausible-looking* number.

| # | defect | how it showed | fix |
|---|---|---|---|
| A1a | freewheel window **assumed** (`tfw = t_on*(V_sup/(0.5·dV) − 1)`) rather than measured | delivered charge **−53.8 fC**; rail3 0.759 → 0.126 V; settling **−31.75%** | probe-then-cut at the top-up inductor's own MEASURED current zero |
| A1b | `Ltu` tied **permanently** to `rail_k`, so parking `na` to ground drained the bank *through the inductor* (`rail → Ltu → LS → gnd`) | still-negative delivered charge with a park added | added the **OUT switch** (tg-class, between inductor and rail) — the committed transfer hop's own shape, and what the record's shared-inductor σ0 architecture needs anyway |
| A1c | the pulse's **preparation** (park-off, OUT-close) landed 8 ps *before* `t_fire`, i.e. **inside the charging hop** | top-up became a second drain path on `rail3` while hop 1 was still delivering | whole sequence moved to `t_open + 6·EDGE`, so prep begins after the hop's switch is open and its park is on |
| A1d | OUT switch closed **2 ps before** the high side, so the **rail** energized the inductor backwards | `0.68 V / 5 nH × 2 ps = 272 µA` predicted reverse current; **−268 µA measured** — the pulse then spent its entire on-time undoing it | OUT closes **simultaneously** with the high side; the inductor is energized by the SUPPLY only |

The A1d arithmetic is worth keeping because it is the cleanest instance: a 2 ps gate
sequencing error produced a reverse current that matched the hand calculation to 1.5%,
and it was invisible in any summary statistic — it only showed up in the raw
`I(LTU3)` / `V(na3)` / `V(nb3)` trace. Every one of these was found by looking at the
waveform, not by reasoning about the schematic.

**Rows measured before A1d was fixed are invalid and are NOT reported.** They were
deleted from `rows.json` (which is regenerated from scratch), and the four affected
smoke rows are named here so the record is complete:
`r_s4_free_T160_dv1200_L5_W10_t12_f0`, `r_s4_ptu_T160_dv1200_L5_W10_t12_f0`,
`r_s4_ptu_T160_dv1200_L15_W10_t12_f0`, `r_s4_ptu_T160_dv1200_L50_W10_t12_f0`
(these read min-delivered-HIGH of 0.0344 / 0.0693 / −0.0436 V — all of them the
signature of a top-up that was still a net sink).

**Second consequence, also recorded now:** the peak current of 2494 µA against a bank
that needs only tens of fC says `t_on = 24 ps` at `Ltu = 5 nH` massively over-drives
this load. So the strength sweep is re-centred **downward and toward larger Ltu**,
where the delivered charge is commensurate with the bank:

```
pre-registered : Ltu in {2, 5, 15} nH x t_on in {6, 12, 24, 48} ps
amended        : Ltu in {5, 15, 50} nH x t_on in {3, 6, 12, 24} ps
```

Same number of points, same two knobs, same span in `Q ~ t_on^2/L`; the grid is moved
to where the delivered charge matches the measured load instead of overwhelming it.
The `t_on = 24 ps` column is retained at every Ltu so the over-drive edge stays on the
record rather than being quietly dropped.

## A2 — the 4-bank chain's stage-2 and stage-3 inputs are HEAD-REFERENCED, and that must be said beside every threshold number

Not a protocol change; a labelling rule, written now because the first control row
already makes it matter and it would be easy to quote a flattering number.

In the 4-bank topology the ask names (banks 1 and 2 are both power-chain heads),
stage 2's inputs come from bank 1 and stage 3's inputs come from bank 2 — and **both
of those are ideally pre-charged head banks**. So the delivered HIGH at stages 2 and 3
is referenced to a near-ideal `dV` rail, and it is *structurally* high: the control row
reads 0.4882 V at stage 2 and 1.0913 V at stage 3.

**Only stage 4 has a predecessor whose rail was supplied by a real inductive hop**
(bank 3, measured 0.759 V). Therefore:

* the binding threshold number in the 4-bank chain is **stage 4's**, and every
  threshold claim is reported per stage, never as a single chain minimum;
* the 5-bank rows (`s5`) are where stage 4 AND stage 5 both have hop-charged
  predecessors, and they are run for exactly that reason.

## A3 — top-up is applied to HOP-CHARGED banks only, and the heads keep only their pre-charge gate

Pre-registered as the attach rule; restated here because it is the difference between
this run and an ideal-source laundering. Banks 1 and 2 are heads: they already carry
the committed soft pre-charge gate to the ideal `dV` node. Adding a top-up there would
add ideal source to banks whose rails are already ideal, and would flatter every
downstream number. Top-up attaches to banks 3 and 4 only (3, 4, 5 in `s5`).

## A4 — the HOP zeros must be re-probed PER BEAT PERIOD, and the A6 gate is what caught it

Found by my own A6 instrument gate on the FREE control rows, before any top-up row was
reported, and fixed before any row in `rows.json` was kept.

I had probed each hop's true current zero once per `(scheme, dV)` and reused it at
every beat period. MEASURED consequence — hop 2's interrupted inductor current at its
switch open, against the pre-registered 1.0 µA A6 gate:

| beat period T | IZ hop 1 (µA) | IZ hop 2 (µA) | A6 |
|---|--:|--:|:--|
| 120 | −0.0021 | −0.0143 | PASS |
| 160 | −0.0409 | **−12.02** | FAIL |
| 200 | −0.0409 | **−19.93** | FAIL |
| 300 | −0.0409 | **−28.96** | FAIL |

The cause is structural, not numerical. Hop 2 drains **bank 2, a HEAD bank**, whose
rail keeps drifting from the instant its soft pre-charge gate cuts until the moment it
is drained. The longer the beat, the further it has drifted, so the LC initial
condition — and therefore the true current zero — **moves with T**. Hop 1's zero barely
moves (−0.0021 → −0.0409 µA) because bank 1's own head cut sits a fixed
`HEAD_LEAD` ahead of its drain. Reusing one zero across beat periods opens the switch
away from the zero, which strands charge in the inductor and corrupts both the
delivered rail and the energy accounting.

**Amended.** The hop-zero cache is keyed on `(scheme, dV, T, mode)` and a probe is run
for every beat period. The hop probes are also run in parallel with each other (they
are independent decks), which is what makes per-T probing affordable.

Every row measured under the single-zero scheme was **discarded**, not annotated: the
seven control rows in the first `rows.json` were deleted and re-measured.

**CORRECTION, entered after the re-measurement (I had written the opposite here first).**
I initially wrote that the `r_s4_free_T200_dv1500` row — worst gate 5.18%, delivered HIGH
0.0131 V, measured against a 24.5 µA stranded current — was "exactly the kind of number
that would have been reported as a physical collapse when it was an instrument artefact."
That was a guess dressed as a finding, and the re-measurement **refutes it**: with the
per-`T` zeros and a clean 0.0007 µA A6, the same row reads worst gate **5.18%** and
delivered HIGH **0.0129 V**. The collapse is REAL, not an artefact. The stranded current
and the collapse were two independent things that happened to co-occur in one row.
Recorded because the wrong version was written down first.

**Note on scope:** `tfw` (the top-up freewheel window, A1) is still probed at one beat
period and reused, and that reuse is JUSTIFIED on a different ground — the top-up pulse
begins and ends inside a single hold window with nothing else switching, so its own zero
does not depend on the beat. That justification is checked by a spot re-probe at a
second beat period, reported with the results.

### A4 verified after the fix

Re-measured with per-`T` hop zeros, same decks otherwise:

| T | IZ hop 1 (µA) | IZ hop 2 (µA) | A6 | hop-2 zero (ps) |
|---|--:|--:|:--|--:|
| 120 | −0.0021 | −0.0143 | PASS | 95.506 |
| 160 | −0.0027 | −0.0020 | PASS | 95.174 |
| 200 | −0.0027 | −0.0007 | PASS | 94.946 |
| 300 | −0.0027 | −0.0007 | PASS | 94.676 |

Two things worth keeping from this:

* **How sharp the zero is.** Hop 2's true zero moves only **0.83 ps** across the whole
  beat range (95.506 → 94.676 ps), and that 0.83 ps was enough to strand **29 µA**.
  This is the quantitative reason the standing instruction says to re-probe the zero per
  L and per hop rather than compute it.
* **Hop 1's zero does NOT move** (97.978 → 97.977 ps), exactly as the diagnosis
  predicted, because bank 1's head cut sits a fixed `HEAD_LEAD` ahead of its drain
  while bank 2's drift depends on the beat. The asymmetry between the two hops is the
  evidence that the cause is head-bank drift and not something numerical.

**Honest note on what the defect did and did not change:** the per-gate settling
percentages at dV = 1.2 came out **identical** before and after the fix (32.87 / 37.50 /
39.20 / 35.88%), so this defect did not move the physics conclusions at that dV. It was
still worth fixing and the affected rows were still discarded, for two reasons: the
dV = 1.5, T = 200 row *was* affected (it read a worst gate of 5.18% under the defect),
and an energy accounting that strands 29 µA in an inductor cannot be quoted as a cost
number. The settling metric was insensitive to the defect; the instrument gate was not.
That is what the instrument gate is for.

## A5 — the PARK-RELEASE KICK, and a charge meter in the wrong branch

Two more defects in my own top-up, both found the same way (compare against the free
control, disbelieve a top-up that makes things worse, then read the raw trace).

### A5a — releasing the park early kicks the inductor node to −0.33 V

With the park released 8 ps ahead of the pulse (an intentional "dead time"), the
measured `I(LTU3)` was **exactly 0.0 µA** up to the instant the park released at
301.978 ps and **−577 µA** three picoseconds later, peaking near −1110 µA — all of it
**before** the high side ever turned on at 309.978 ps.

MEASURED cause: `na` is a tiny node (one pMOS drain, one nMOS drain, one inductor
terminal) with almost no capacitance of its own. Released, it floats, and the park
gate's **own falling edge** capacitively kicks it to **−0.33 V**, which puts ~0.3 V
across a 1 nH inductor and pre-charges it with hundreds of µA of reverse current. The
pulse then spends itself undoing that.

A real buck tolerates dead time because its inductor current is continuous and a body
diode carries it through the gap. Here the current starts at **zero**, so there is
nothing to hold the node and the gate coupling wins. (And `sg13lv_compat.sp` zeroes
ad/as/pd/ps, so the junction that would clamp it is absent from the model — one more
place where every number here is a lower bound.)

**Amended.** Make-before-break: the LS turn-off, the HS turn-on and the OUT-switch
close all share ONE 2 ps window, so `na` hands off directly from ground to the supply
and never floats. The resulting brief HS/LS overlap is genuine shoot-through and it is
**metered** in `q_from_supply`, not hidden.

### A5b — the delivered charge was metered in the inductor, not at the rail

`q_delivered_into_rail_fC` was `∫I(LTU)`. That is the wrong branch. While the OUT
switch is OPEN the inductor branch is isolated from the bank, and current that merely
sloshes between `na`'s and `nb`'s parasitics was being counted as charge delivered to
(or stolen from) the bank, when none of it reaches the bank at all.

**Amended.** A 0 V series source `VMTU_k` sits in the rail leg, between the inductor's
`nb` node and the OUT switch, and `∫I(VMTU_k)` is the delivered charge. The inductor
current is still reported separately as `q_in_inductor_fC`, so the two can be compared
rather than conflated.

### Running count, stated plainly

This is the **fifth and sixth** correction to my own top-up (A1a–A1d, A5a, A5b). Every
one was caught by the free control, none by inspection of the schematic, and every one
of them would have produced a publishable-looking number. The top-up rows measured
before A5 are discarded; the eight `free` control rows are unaffected by A5 (they
contain no top-up devices at all) and are retained.

The discarded pre-A5 top-up rows are named so the record is complete, with the numbers
that should NOT be quoted: `L1/t6` 41.14%, `L1/t12` 36.96%, `L1/t24` 33.87%,
`L2/t12` 40.10%, `L2/t24` 34.25%, `L5/t6` 71.75%, `L5/t12` 71.13% — the last two of
which look like a large win over the 39.20% control and are entirely an artefact of a
rail being pulled down while the settling ratio is measured against it.

## A6 — THE COMPAT SHIM REMOVES THE CAPACITANCE THIS TOPOLOGY DEPENDS ON

This is the most consequential correction of the run, and it is a **model-scope** finding,
not a sequencing bug. It was found by moving the top-up onto a SMALL FIXTURE — one linear
capacitor standing in for a bank, no cells, no hops, no schedule — which I should have
done first (the standing directive is to prove a mechanism on a small fixture and use
full scale only as confirmation; I violated it and it cost several iterations).

**On the clean fixture the top-up still drained the bank**: 28.98 fF pre-charged to
0.700 V, supply 1.2 V, Ltu = 1 nH, t_on = 6 ps →
`q_delivered = −14.969 fC`, bank `0.7000 → 0.3835 V`, and the bank's voltage **never rose
above its starting value at any instant** (`V_max = 0.6156 V`). No chain, no schedule, no
hop could be blamed.

**The trace settles the cause.** With the HS gate fully low from t = 96 ps, the switch
node `na` nonetheless sat at **−0.2968 V** at t = 97.9 ps and did not reach 1.03 V until
t = 107.9 ps — *after* the 6 ps pulse had ended. The inductor voltage `V(na) − V(nb)` was
−0.17 V, which at 1 nH gives `dI/dt = −1.7e8 A/s` and −680 µA over 4 ps: the measured
current was **−670 µA**. The arithmetic closes. The inductor was being driven **backwards
by `na` itself**.

**Why `na` can be dragged anywhere:** `sg13lv_compat.sp` sets `ad=as=pd=ps=0`, so the
buck switch node has **no junction capacitance whatsoever** in this model. Its only
capacitance is the two switches' gate overlap. The gate-to-node coupling ratio is
therefore near unity, and a 1.5 V gate swing transfers almost entirely onto `na`.

This matters in a way the shim's standard caveat does not cover. Everywhere else in this
campaign the zeroed junctions make device numbers a **lower bound** — a second-order
effect in the conservative direction. For a **buck switch node** that capacitance is
**first-order**: it is the thing that holds the node against its own gate drive. Zeroing
it does not make the result conservative, it makes the topology **unsimulatable**, and any
number taken from it — in either direction — is an artefact of the shim.

**Amended.** An explicit switch-node capacitance `CNA` is added to `na` and **swept**,
because it is an assumption and is labelled ASSUMED:

```
DERIVED estimate: a w=10 um drain with ~0.3 um contacted extension is ~3 um^2;
at ~1 fF/um^2 that is ~3 fF per device, two devices ~6 fF, plus ~2 fF wiring ~= 8 fF.
SWEPT over Cna in {2, 8, 20} fF x Ltu in {1, 5} nH x t_on in {6, 12} ps.
```

Consequences recorded up front, before the sweep returns:

* every top-up number in this run is **conditional on an ASSUMED switch-node
  capacitance**, and the sensitivity to it is reported rather than buried;
* if the top-up only delivers positive charge at `Cna` values well above the DERIVED
  ~8 fF, then the mechanism is being carried by an assumption and must be reported as
  NOT DEMONSTRATED on this node with this model;
* the `free` control rows are **unaffected** — they contain no top-up switch node, and
  their devices are the same shallow-stack cells used throughout the campaign, where the
  shim's lower-bound caveat applies normally.

## A7 — the PULSED-INDUCTOR top-up is NOT DEMONSTRATED at this scale, and a BOUNDING form replaces it

### What the small fixture measured, after every fix

28.98 fF bank at 0.700 V, supply 1.2 V, `wsw = 10 µm`, with the switch-node capacitance
added and the low-side turn-off slew stretched to 24 ps:

| Cna (fF) | Ltu (nH) | t_on (ps) | tfw meas (ps) | q_delivered (fC) | q_from_supply (fC) | bank V0→Vf | Qmult |
|--:|--:|--:|--:|--:|--:|--:|--:|
| 2 | 1 | 6 | 6.94 | **−15.735** | 18.084 | 0.7000→0.3673 | −0.87 |
| 2 | 1 | 12 | 8.25 | −9.193 | 26.259 | 0.7000→0.5067 | −0.35 |
| 2 | 5 | 6 | 121.32 | −28.539 | 18.389 | 0.7000→0.0951 | −1.55 |
| 8 | 1 | 6 | 5.47 | **−2.560** | 57.173 | 0.7000→0.6474 | −0.045 |
| 8 | 1 | 12 | 6.29 | **−1.203** | 65.520 | 0.7000→0.6762 | −0.018 |

The fixes converge the delivery toward **zero, from below**. At the DERIVED switch-node
capacitance (8 fF) the top-up delivers **−1.2 to −2.6 fC** — i.e. nothing, slightly
negative — while drawing **57–65 fC from the supply**. Charge multiplication is
**−0.018 to −0.045** against a buck's whole purpose of `Qmult > 1`. The supply charge is
going into shoot-through and switch-node parasitics, not into the bank.

**VERDICT on the architecture's preferred form: NOT DEMONSTRATED at this scale on this
node.** Not "worse than expected" — not working at all. Two reasons, both measured:

1. **the switch node is unholdable in this model** (A6): with `ad/as/pd/ps = 0` its only
   capacitance is gate overlap, so its own gate drive moves it hundreds of mV;
2. **the path is resistance-dominated**, not inductance-dominated. The probe diagnostic
   prints how long after the pulse the current peaks: at `Ltu = 5 nH` the peak arrives
   **103.7 ps after the high side shut off**, which is an RL/RC charging curve and not a
   resonant ring-down. When resistance sets the dynamics the inductor performs no voltage
   conversion, and buck action — the entire reason this form was chosen over a flycap — is
   absent.

I am NOT claiming the pulsed inductor cannot work in principle, and the committed
`qal_pulse_topup.py` explicitly predicted this regime: *"Small Q + small L = unswitchably
short pulse. Relief comes from a BIGGER BANK and a LARGER inductor."* An 8-cell, 29 fF
bank is the small-Q corner it warned about. What is measured here is that it does not
work **on a bank this small with switches this size**, and every number is a lower bound
because the shim removes junction capacitance.

### The BOUNDING top-up, and why it makes the verdict independent of my buck

Because I could not get a defensible charge-multiplying top-up, the question the user
actually asked — *does topping up the held banks sustain the hold?* — is answered with a
form that is trivially correct and **upper-bounds** every top-up: chain3's **resistive
transmission gate to the supply**, its device and 20 ps window placement verbatim, fired
at the START of the bank's hold.

It is deliberately the *inefficient* form (charge-conserving, so it dissipates
`(V_sup − V_rail)·dQ` no matter how good the switch is; chain3 measured its booking at
15.2–29.1 fJ per bank per hop, 1.8–3.5× the loss it repairs). That is exactly why it
bounds: **it restores the rail as hard as a supply can.** If the chain still cannot reach
90% at all four stages with the rail held up by a stiff supply, then no top-up of any
efficiency rescues the schedule, and the verdict no longer depends on whether my
pulsed-inductor implementation works.

`rtu` rows are labelled as carrying an **ideal-source booking** and are never quoted as a
QAL operating point.

## A8 — the hop zeros must be probed in the ROW'S OWN MODE, not just per beat period

A4 keyed the hop-zero cache on `(scheme, dV, T)`. That is still not enough, and the A6
gate caught it again — this time on the bounding resistive top-up rows.

MEASURED: the first `rtu` rows, using hop zeros probed in `free` mode, left
**221.8 µA on hop 1 and 219.5 µA on hop 2** of interrupted inductor current at the
switch-open instant, against the pre-registered 1.0 µA gate. The `free` rows in the same
sweep were clean at 0.0007–0.0027 µA.

Cause: the resistive top-up's transmission gates sit on the **destination rail**, and
their drain capacitance loads that rail **even while the gates are off**. That extra
capacitance lowers the hop's LC resonant frequency and moves its true current zero. The
top-up does not have to conduct to change the hop — merely existing on the node is enough.

**Amended.**

* the hop-zero cache is keyed on `(scheme, dV, T, mode)` and, for `rtu`, also on the
  top-up window width, since that is part of the deck;
* in a PROBE deck the top-up **devices are still instantiated** (so their loading is in
  the measurement) but are held permanently OFF for the bank whose charging hop is under
  probe — firing it would clamp the very rail whose zero is being measured.

All ten `rtu` rows measured under the free-mode zeros were **discarded and re-measured**.
They are not reported. For the record, the discarded numbers were close to the re-measured
ones (e.g. `T=200, dV=1.2` read worst-gate 50.76% under the bad zeros), which is precisely
why the instrument gate rather than the headline metric has to be the thing that decides:
a row can look right and still be instrumentally wrong.

**General lesson, now measured twice (A4, A8):** the true-ZCS probe must be run under the
*same* deck conditions as the row it serves. Any device added to a rail — even an idle
one — changes that rail's resonance. Beat period (A4) and mode (A8) both qualify.
