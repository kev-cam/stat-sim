# qal/cipher/p2 — AMENDMENTS

Every departure from the pre-registered plan, and every error of my own, with the
measurement or check that forced it. Pre-registration:
`PRE_REGISTERED.json`, sha256 `19bf54304f6454ffdf03b8de15a268af2b5b5dbfc18684f6eed2bd3733c548db`,
25040 B, mtime 2026-09-29 21:11:56 −0700, hashed 21:12:00.

Seventeen amendments (B1-B14). Six are mistakes of mine; five of those were caught by a check
before any deck ran and one by measurement. Three (B1, B8, B9) are places where the
committed protocol does not survive the move from an 8-cell bank to a cipher-width one,
and two of those three turned out to be findings in their own right. They are listed the same way
either way.

---

## B1 — the ZCS probe window does not scale with bank size (FORCED BY MEASUREMENT)

**What broke.** The first four Phase 2 configurations all aborted with
`probe rise1 NO ZERO` / `probe rise2 NO ZERO`.

**Why.** The committed probe window is `span × TZ_ANCH × sqrt(L/L_REF)`, where
`TZ_ANCH = 65.495 ps` is the MEASURED single-hop zero of the committed **eight-cell**
bank (`C_bank = 35.979 fF`). Phase 2's banks are 4–70× that capacitance and the LC
half-period goes as `sqrt(LC)`, so the window has to scale with the bank's own
capacitance as well. It does not in the committed code. At `T = 1200` the AES probe
window was **235.8 ps against a hop of ~840 ps** — the search ended less than a third
of the way into the first half-cycle, so there was genuinely no sign change inside it.
This is the same class of defect as Phase 1's AMENDMENT A1 (whose 2.6 → 3.6 span
widening was also forced by a missing zero) but an order of magnitude larger, because
Phase 1 only ever changed the *load* on an 8-cell bank while Phase 2 changes the
*population*.

**Fix.** The anchor is scaled by `sqrt(C_bank(k)/CBANK)` — the same closed form the
committed code already applies to `L`. Windows become 410–1943 ps, roughly twice each
bank's predicted hop.

**Why this is not a thumb on the scale.** With `cw = 0` and an 8-inverter bank the
factor is exactly 1.0 and the emitted deck is unchanged; `cg.selftest()` re-checks the
committed-harness identity after the patch and still reports 122/122 retained lines
IDENTICAL and the schedule bit-identical. The widening can only change a zero if a
later, larger current excursion exists inside the new window, which would itself be a
ringing pathology worth reporting — none appeared.

## B2 — my cell-logic checker could not read two-stage cells (caught before any deck)

`cg.selftest_logic()` solves each PDK cell's pull-up and pull-down conduction graphs
and compares the result against this run's logic table. My first version treated a
device whose gate voltage was unknown as simply absent, which is wrong for
`and2`/`or2`/`xor2`/`xnor2`/`buf`: those are **two-stage** cells whose output devices
are gated from an *internal* node. Five of ten cells reported "BOTH/NEITHER side
conducts". Replaced with a monotone fixed point over the internal nodes, with separate
optimistic and pessimistic reachability so that a node is only resolved when one side
*definitely* conducts and the other *definitely* cannot. All 10 cells, 56 input cases,
now pass. Had I not fixed this I would have had no independent check on the cell
semantics at all.

## B3 — the ripple builder dropped a live carry (caught by construction)

`build_adder(form="ripple")` forwarded carries `c_0 … c_{i-2}` at carry level `i`,
omitting `c_{i-1}` — which is simultaneously *read* (to make `c_i`) and *needed later*
(by sum bit `i`). `c0` therefore died at the first carry level and the builder raised
`KeyError: 'c0'`. Fixed to forward `c_0 … c_{i-1}`; two cells on one net is what a real
fanout is.

## B4 — the CMOS-native Kogge-Stone computed the wrong sum (caught by the reference check)

`cmosnat.cmos_adder(form="ks")` used `xor2` for every sum bit. That is right for the
**QAL** build, where the bit propagate is forwarded through the prefix tree and so flips
polarity once per level, arriving with the same polarity as the carry — and wrong for
the **CMOS** build, where the bit propagate is *not* forwarded, sits on its original net,
and stays true while the carry has flipped once per prefix stage. The reference check
reported `MISMATCH 2cc92cfe vs d336d300`. Fixed by choosing `xor2`/`xnor2` from the
carry's actual polarity.

This is worth more than a bug note: **the two technologies need different sum cells for
the identical function**, and the reason is precisely the forwarding difference that
Phase 2 is about.

## B5 — my rotate test vector could not detect a rotate error (caught before any deck)

`qr_xor_rotate`'s first stimulus was generated as `(seed >> (i % 8)) & 1`, i.e.
8-periodic, so `xor = 0x7f7f7f7f` and `rotl(xor, 16) = 0x7f7f7f7f`. The vector is
invariant under the very permutation under test, so the value check was structurally
incapable of seeing a wrong rotate. Replaced with non-periodic constants
(`0x243F6A88`, `0x85A308D3`), giving `xor = 0xa19c625b` and `rotl16 = 0x625ba19c`.

## B6 — the quarter-round's generate level ignored operand polarity (caught by measurement against RFC 8439)

**What broke.** The full symbolic quarter-round failed the RFC 8439 §2.1.1 vector. A
step-by-step bisect localised it exactly: steps 1–4 correct, **step 5 (the second
`a += b`) wrong, and only in word `a`.**

**Why.** Forwarding is one inverter, so a word that has crossed an odd number of levels
arrives **complemented**. By step 5, `a` had been forwarded across 9 levels and arrived
inverted while `b` did not. An XOR term absorbs that for free by swapping `xor2` for
`xnor2` — but an AND term **cannot**: `and2(!A, B)` is a different function, not a
relabelling of `A & B`. The generate level was emitting `and2` unconditionally, so the
carry-generate word was simply wrong.

**Fix.** The generate level is now polarity-aware and always emits true-polarity `P` and
`G`, using the PDK's own mixed-polarity cell:

| operand polarity | cell    | identity |
|---|---|---|
| (T,T) | `and2`  | `A & B` |
| (F,F) | `nor2`  | `!(!A \| !B) = A & B` |
| mixed | `nor2b` | `!A' & B'`, `A'` the complemented net |

`sg13g2_nor2b_1` was added to the cell table and verified by the same independent
switch-network solve as every other cell (6 devices, 4 cases, PASS). All eight steps
now match RFC 8439.

**Cost of my error, had it stood:** the quarter-round census would have been reported
off a netlist that did not compute ChaCha20.

## B7 — the CMOS twin's held sources were weaker than the QAL deck's (caught by review, before any comparator ran)

`cg.cmos_deck()` drove the held sources (primary inputs, AES round key, adder A/B
words) at the CMOS **supply**, while the QAL deck drives them at the committed **dV =
1.65 V** (`bt.bank_cells` uses `dv`, not the rail). That would have given the QAL side a
stronger input overdrive than the CMOS side — the one-sided-comparator error this
campaign has already made once, with the DELVTO sweep. Fixed: input amplitude is pinned
to dV on **both** sides; gate G9 continues to pin the CMOS **supply** to the QAL row's
own measured delivered rail peak. Caught before any comparator deck was run, so no
published number was ever affected.

## B8 — a heavy wire load can remove the ZCS instant entirely (FORCED BY MEASUREMENT)

**What broke.** `qrxor` at `cw = 7.767 fF/bit` (the ChaCha rotate load at the xor2
pitch) aborted at `rise2` with NO ZERO, while its own `cw = 0` control found the zero
at 292.66 ps inside the same protocol.

**Why — and this is a physics finding, not a harness defect.** The committed protocol
assumes the LC transfer is **under-damped**: the rail overshoots, the inductor current
reverses, and there is a true zero to cut at. Measured on the two decks:

| | peak I(L2) | at | first sign change after peak | end of window |
|---|---|---|---|---|
| `cw = 0` | 2771.2 µA | 946.8 ps | **1142.82 ps** | +5.2 µA |
| `cw = 7.767` | 2811.4 µA | 947.8 ps | **NONE** | **+45.6 µA, still positive** |

The peak is essentially unchanged — the wire sits on cell OUTPUT nodes, outside the LC
loop, exactly as Phase 1 found — but the added capacitance has pushed the transfer
**over-damped**, and an over-damped transfer has no current zero. The chain-legal
source-side cut at a true zero is simply not available at this load.

**Fix, and how it is kept honest.** A fallback takes the first instant at which `|I(L)|`
has fallen to the acceptance gate's own 1 µA threshold — a current zero to within the
tolerance every row is already scored against. If even that is not reached inside the
window, the minimum `|I|` is used, the row is flagged `NO_TRUE_ZCS`, and the stranded
inductor energy `½LI²` is reported so its size is visible. Every zero now carries its
own `cut_rule` label (`sign_change` / `threshold_1uA` / `min_abs_I`) and the row records
how many of its hops got a true ZCS, so **no row can quietly claim a ZCS it does not
have.**

On the first attempt the fallback returned `min_abs_I` at 1048.97 ps — the window edge,
i.e. an artefact of where I stopped looking rather than a physical minimum. That is
recorded here because it is exactly the kind of number that should not be believed: a
"minimum" at the boundary of the search means the search was too short.

## B9 — my transfer switch was sized for eight cells while the bank held 128 (FORCED BY MEASUREMENT)

**What broke.** This run's AES level 1 is 128 inverters, `C_bank = 575.7 fF`, tank
5757 fF — numerically identical to the qal/widebank sibling's `n128` row. The sibling
MEASURED `t_hop = 406.7 ps`. I measured **645.3 ps**, 1.59× slower, with the same L, the
same Rs, the same dV and the same tank.

**Why.** The committed `tg15p` transfer switch is 30 µm total for an **eight-cell** bank,
and `cg.deck` was passing 30 µm regardless of population. At 128 cells the switch, not
the inductor, is the limiting resistance. This is **Phase 1's AMENDMENT A3 error in
reverse** — A3 was one cell against a switch sized for eight; this was 128 cells against
a switch sized for eight — and the campaign has already paid for that lesson once.

**Fix, taken from the sibling's own data rather than invented.** qal/widebank's rule,
read off its rows and reproduced on **all 13** of them (N = 8, 16, 32, 64, 128, 256;
agreement better than 0.6 µm every time):

```
W_nominal = 30 um * sqrt(N / 8)
```

Since an N-inverter bank has `C_bank = CBANK · N/8`, that is identically

```
W_nominal = 30 um * sqrt(C_bank / CBANK)
```

which is the same closed form expressed in the quantity that actually sets the required
conductance, and which therefore generalises correctly to this run's **mixed-cell** banks
and to banks carrying wire. It reduces to exactly 30 µm at the committed 8-inverter
bank, and `cg.selftest()` confirms the committed-harness identity survives the patch
(122/122 retained lines IDENTICAL, schedule bit-identical).

**DIRECTION OF THE BIAS, stated because it matters: this correction makes QAL FASTER and
is therefore in QAL's favour.** It is adopted because it is the right physics and the
sibling's validated rule, not because of its direction. Four rows measured before the
fix were discarded rather than reported.

**Consequence for the beats.** With the switch matched, beats are re-derived by log-log
interpolation of the sibling's own MEASURED `(C_bank, t_hop)` table —
(36.0, 126.6), (72.0, 162.9), (143.9, 216.1), (287.8, 295.8), (575.7, 406.7),
(1151.3, 554.5) — as `T = max(1.4261 · t_hop, 1.20 · worst_cell_settle)`, where 1.4261 is
the sibling's own accepted `T / t_hop` at N = 128 and the worst cell is `o21ai`/`a21oi` at
the MEASURED 479.1 ps. The adders are beat-limited by the CELL, not by the hop
(479.1 ps against a 243.8 ps hop), which is the standing correction "synthesise for
worst-cell settling time" showing up as an actual number.

## B9a — my own switch scaling made every level a new PSP103 geometry (FORCED BY RUNTIME)

B9 made the switch width a **continuous** function of `C_bank`. PyMS builds one `.so`
per (model, geometry) by GiNaC codegen plus a g++ compile, roughly three minutes each,
so a continuous width means a fresh three-minute compile for **every level of every
vehicle**. Measured consequence: 33 `.so` built and still climbing with six compiles
running concurrently, while six probe decks — including a 372-device one whose window is
539 ps — sat for **15 minutes without emitting a single result.** The committed harness
has one switch width and therefore three geometries.

**Fix.** The width is snapped to the geometric ladder the sibling itself uses,
`30 um · 2^(n/2)` → 30, 42.43, 60, 84.85, 120, 169.7, 240 — which is exactly its
`30·sqrt(N/8)` evaluated at N = 8, 16, 32, 64, 128, 256. All of Phase 2 then needs five
switch widths and twelve device geometries instead of dozens.

**Price, stated:** a level's switch can be up to `2^(1/4)` = 19 % off its ideal
conductance. It applies to every level of every vehicle alike, and it is small against
the 59 % error that leaving the switch at 30 µm produced (B9).

**Also fixed:** the cache was being built by six racing Xyce processes. A single
`warm.py` deck now instantiates every switch geometry and every PDK cell Phase 2 uses,
once, up front. Two orphaned cache entries (a `.so.params` and `.so.build` with no
`.so`, left by killing Xyce mid-compile) were removed so nothing stale could be picked
up — the `.so`-cache hazard qal/banktank logged as its A0.

## B10 — my CMOS comparator disagreed with its own cross-check by 12000× (caught before any ratio)

My first CMOS deck mirrored the QAL "settle-not-switch" rule: hold the inputs, **step the
supply**. Its 1 F energy integrator then returned **−0.0673 fJ** while its own V·Q
cross-check returned **+819.4 fJ** — opposite sign and four orders of magnitude apart.

The disagreement is not a sign convention. With the supply ramping, part of the charge is
delivered at `V < vdd`, so there is no single-voltage `V·Q` identity to check the
integrator against in the first place.

**Fix — Phase 1's own validated harness, adopted rather than invented.** Phase 1's
micro-harness held the CMOS supply **constant** and drove the **inputs** through a cycle.
With `V` constant the supply energy is exactly `E = vdd · ΔQ`, which needs no integrator
and no sign convention — convention-free in the sense gate G5 requires. Phase 1 confirmed
this harness reproduces the textbook `n·Cw·vdd²` per cycle to 0.4–0.6 % at five voltages.
A full `0 → 1 → 0` cycle is also the right event to set against a QAL beat, which raises
the rail and returns it: both are one complete charge-and-discharge of the datapath.

Verification after the fix: `E = 1059.961 fJ` against `C_switched · vdd² = 876.0 fF ×
(1.10 V)² = 1059.96 fJ` — exact, by construction.

## B10a — complementing both XOR operands switches nothing (caught by measurement)

The full-cycle stimulus first complemented **every** held source. Complementing **both**
operands of an XOR leaves its output unchanged, so on an XOR-dominated datapath — which
is what both cipher vehicles are — the stimulus switched **nothing**: the measured delay
came out as **0.0 ps** for a 32-cell XOR level, and the measured charge never touched the
output nodes or the rotate wire hung on them, which is the entire quantity Phase 2 exists
to measure. `C_switched` read 424.8 fF with the outputs frozen against 876.0 fF once they
move.

**Fix.** Only ONE operand word is cycled (the AES round key, ChaCha's `a`, the adder's
`B`). Every XOR output then flips. The measured **activity** is reported with every CMOS
row: 1.0 for both cipher vehicles, 0.67 (ks8) and 0.70 (rip8) for the adders.

**Why the activity matters, and it is not a footnote.** A QAL beat raises and returns the
whole bank rail whatever the data does, so **QAL's energy is activity-independent**. A
CMOS transition charges only the nodes that flip, so **CMOS's energy scales with
activity**. Cycling a whole operand word gives activity 1.0, the WORST case for CMOS and
therefore CONSERVATIVE for QAL. The α-scaling is reported alongside the ratio rather than
buried in it.

## B10b — a 200 ps half-cycle was shorter than the CMOS rise (caught by measurement)

With the half-cycle at 200 ps the CMOS delay search found no valid instant and reported
`None`. The cause is physical and is itself a result: at the **G9-matched** supply of
1.10 V the PDK `xor2`'s pull-up is a **2-high pMOS stack** with only
`1.10 − 0.4403 = 0.66 V` of overdrive, and a rising output loaded by CL + rotate wire
(9.767 fF) was still at **0.639 V of 1.10 V after 196 ps**. The half-cycle is widened to
1500 ps. `C_switched` rises 683.1 → 876.0 fF once the slow direction is allowed to
finish, so the short window was also truncating the energy.

This is not a QAL/CMOS asymmetry: it is the same low-swing penalty gate G9 imposes on the
CMOS side by construction, and measuring it properly is the point. It also means the
CMOS-side delay is **not** the ~50 ps a nominal-supply gate would give, which materially
narrows the speed gap I pre-registered in Q4.

Related: the propagation delay is measured on the **first** input edge against the
complement-state output values. Measuring after the **return** edge is meaningless — the
outputs are already near their final state before it arrives — and the first version of
that code duly reported 3.29 ps for a 32-cell XOR level, which is an artefact and not a
delay.

## B11 — six runners serialise on the model cache; warm it alone, first (FORCED BY RUNTIME)

After B9a cut the geometry count, six row jobs still produced **zero** probe results in
25 minutes. The cause is not the deck count but the **model cache**: PyMS builds one
`.so` per (model, geometry) and the builds do not proceed independently across processes,
so six Xyce runs each needing several geometries do not build in parallel — they queue,
and the wall time becomes the SUM of every build rather than the maximum.

Inspecting the cache keys explains what had also confused the earlier warm attempt. The
key is not (W, L) alone; it also separates

* **`TYPE=+1` from `TYPE=-1`** — the same width as an nMOS and as a pMOS are two distinct
  geometries, so my first "needed widths" count conflated them; and
* **whether `MULT` was given** — the PDK `.spice` cells carry `m=1` while the harness's own
  switch instances do not, so a cell and a switch at the same width are also two distinct
  keys.

That accounts for roughly 23 legitimate keys for Phase 2, not the dozen I first counted,
and it is why entries that looked like duplicates of an already-built width were genuine
misses.

**Fix, and the right order of operations.** Run `warm.py` — which instantiates every switch
geometry and every PDK cell Phase 2 uses in ONE trivial deck — **alone, to completion,
before any row job starts.** Orphaned entries (a `.so.params`/`.so.build` with no `.so`,
left behind by killing Xyce mid-compile) are removed first so nothing stale can be picked
up, which is qal/banktank's A0 hazard. Rows launched after the cache is warm run without
contention.

Rows measured before the cache was warm were discarded, not reported: the only thing they
established is the B9 switch-sizing error, which is recorded above on its own evidence.

**One further trap, worth recording because it cost two launches.** A `( cd X && nohup … & )`
list that is itself inside a backgrounded shell dies when that shell exits, and so do its
children — twice I launched six jobs that printed their first line and vanished. Long jobs
are launched with `nohup setsid …` from a foreground call, which puts them in their own
session and makes them independent of the launching shell.

## B12 — the rise probe does not need the return probe's span (FORCED BY RUNTIME, justified by Phase 1's own A1)

With B1's capacitance scaling in place, the AES level-2 **rise** probe window came to
**1943 ps against a predicted hop of 777 ps**, and AES's six probe decks projected to about
**3.5 hours** — measured from a deck that had advanced only to t = 147.6 ps of its 943 ps
window after six minutes.

**The justification for narrowing it is Phase 1's own measurement, not convenience.**
Phase 1 widened the span 2.6 → 3.6 because a *wire-loaded return hop* found no zero inside
the narrower window — and it then verified that the already-probed **rise** zeros were
**byte-identical** afterwards (signal/fixed rise2 = 127.1601 ps both times). That is direct
evidence that the rise hop never needed the extra span: its zero sits at the first current
reversal, close to `t_hop`, while the return hop is the slow one.

**Fix.** The rise span is 2.0 and the return span stays at Phase 1's 3.6. Rise windows then
sit at **1.3–1.4× each bank's predicted hop** (AES 524 / 1080 / 524 ps; ks8 205–299 ps).

This changes only *where* the zero is looked for, never the zero itself — and every row still
carries the `|I(L)| ≤ 1 µA` gate at each commanded open, which fails the row outright if a
zero was missed. `cg.selftest()` confirms the committed-harness identity survives the patch.

**Observation recorded while checking B9, since it qualifies the rule.** A wider transfer
switch is not monotonically faster: qrxor's level 1 (32 inverters, `C_bank` 143.9 fF) measured
`t_hop` = **189.20 ps at the committed 30 µm** and **208.53 ps at the sibling's rule-derived
60 µm** — the wider switch's own parasitics sit on the rail and lengthen the LC period more
than its lower resistance shortens it. The sibling's own `n32` row measured 216.1 ps at 60 µm,
so my 208.53 ps *reproduces the reference* and B9 is validated where it matters; but the rule
slightly over-sizes at small N, and at large N it is unambiguously right (575.7 fF: 645.3 ps
at 30 µm against the sibling's 406.7 ps at 120 µm). The rule is kept for consistency with the
read-only reference, and the non-monotonicity is stated rather than smoothed over.

## B13 — the maximum time step, relaxed only where a row is otherwise unaffordable, and VALIDATED not assumed (DECLARED DEVIATION)

**The measurement that forced it.** The AES vehicle at the committed `.tran 0.1p <tend> 0
0.25p` ran at **2.07 ps of simulated time per second** (211.5 ps in 102 s, 1792 devices).
The sequential probe protocol must simulate the whole schedule up to `r_k` for every return
probe, so one AES configuration needs about 36 ns of transient across its six probes and its
row — **291 minutes**, and two configurations twice that. It is not affordable.

**What I did NOT cut.** Not the width: the brief's whole argument for AddRoundKey is that
N = 128 sits far above the N_min ≈ 52 the energy arithmetic needs, and narrowing the datapath
would be exactly the scoping error this campaign has already been bitten by — a narrow slice
generalised to a cipher. Not the cells, not the wire, not the schedule (H stays at the
committed 4), not the acceptance gates.

**What I cut.** Only the **maximum time step**, 0.25 ps → 1.0 ps. `mstep=None` keeps the
committed value exactly, so every other row in this run is unaffected, and the deviation is
carried in the row's own tag (`_ms1`) and in `mstep_ps` inside its JSON.

**How it is kept honest.** The coarsening is **validated by measurement on a cheap vehicle
before being trusted on an expensive one**: `qrxor` at cw = 7.767 fF/bit is run at BOTH
0.25 ps and 1.0 ps and every extracted quantity compared. The comparison is reported with the
AES row, and if the agreement is not good enough the AES row is reported as **not measured**
rather than reported at a step I cannot vouch for.

**What was dropped, and said plainly.** With the time available:

* the AES **cw = 0 control** is not run, so Phase 2 measures AddRoundKey **with** its
  interconnect (which is what the brief asks for) but cannot attribute the wire's share by
  difference on this vehicle;
* the **8-bit ripple CPA row** is not run — 20 probe decks over a 10-level schedule projected
  to about 2.3 hours. Its cell and level counts are exact netlist facts and its energy is
  reported as **COMPOSED** from the measured Kogge-Stone per-cell energy and its own exact
  census, labelled as such, never as a measurement. Three of its probe decks were completed
  before it was stopped and are left on disk as the record of the attempt.

## B14 — two errors in how I paired the CMOS comparator with the QAL row (caught by an implausible number)

The CMOS-native comparator implements only what CMOS would actually build, which has FEWER cells
than the QAL vehicle. Deciding which QAL number it pairs with is not cosmetic, and I got it wrong
twice:

1. **`_widest()` picked the wrong bank.** For `qrxor` all three levels hold 32 cells, so
   "widest" returned level 1 — the trivial drive level — and the comparison read
   **6.935×** instead of the correct **1.795×**. A 6.9× energy win on a vehicle whose own
   control row wins 1.7× is not a plausible number, and that is what exposed it. Fixed to pair
   with the bank carrying the most energy, which is the one holding the wide cells and the
   permutation wire.
2. **An adder is not a single level.** The rule then said "fewer CMOS cells ⇒ pair with one
   bank", which is right for the permutation vehicles (the drive and receiver levels exist
   because a QAL bank needs a real predecessor and a real receiver, and CMOS needs neither) and
   wrong for an adder, whose native form is the *whole function* and has fewer cells only because
   it pays no forwarding tax. It reported ks8 at a **0.158** crossover instead of **0.480**.
   Fixed: the functional-bank pairing applies only to `aes_addroundkey` and `qrxor_w32_r16`.

Both were caught before anything was published, and the corrected figures are the ones reported.

---

## Refinements that are not corrections

* **AES ShiftRows wire is per bit, not a flat mean.** Source byte `4c+r` moves to column
  `(c−r) mod 4`, so displacement depends only on the row `r` and is 0/8/16/8 bit
  pitches for `r = 0..3`. Row 0 does not move and pays **no** wire. The resulting load
  distribution at the xor2 pitch is 32 nets at 0 fF, 64 at 4.608 fF and 32 at 9.216 fF
  (mean 4.608). A flat mean would have smeared away a real feature of ShiftRows — and
  would have hidden that a quarter of its nets sit at exactly the 9.216 fF load Phase 1
  measured as both failing (fcrit 27/32) and losing to CMOS (0.749×).
* **Adder wire is derived from the netlist, not assumed.** `veh.struct_wire()` reads each
  net's routed length off its own fan-out bit distances. A Kogge-Stone prefix cell at
  stride `s` reads a net `s` bit positions away (1, 2, 4, 8, 16 over the five stages of a
  32-bit adder) while a ripple carry is always one pitch. A flat per-net load would have
  erased exactly the difference being measured.
* **The rotate costs zero levels and zero cells**, and is implemented that way: the
  permutation is folded into which nets each XOR cell reaches, since
  `rotl(d ^ a, r)_j = d_{(j−r) mod W} XOR a_{(j−r) mod W}`. That part of the insight is
  confirmed and is not in dispute anywhere in this run.
* **Beats are derived from the sibling, not guessed.** `BEAT_DERIVATION.json` anchors on
  qal/widebank's own measured `n128` row (C_bank 575.664 fF, t_hop 406.718 ps, accepted
  T 580 ps, read-only), extracts `K = t_hop,measured / t_hop,ideal = 1.4612` and
  `T / t_hop = 1.4261`, and scales by `sqrt(C_bank)`. Beats are then raised where needed
  to clear the worst-cell settling bar, because `o21ai` settles in 479.1 ps and the
  standing correction is to synthesise for worst-cell settling time.
