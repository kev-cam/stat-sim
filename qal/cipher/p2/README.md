# qal/cipher/p2 — PHASE 2: the two cipher datapaths, with interconnect

**What this run was asked to do.** Measure AES-128 AddRoundKey and a ChaCha20
quarter-round as QAL datapaths with interconnect included; measure the same ChaCha adder
as both a parallel-prefix (Kogge-Stone) and a ripple CPA so the wide-vs-narrow adder
difference is this campaign's number rather than an assertion; and say plainly whether
either vehicle puts QAL ahead of CMOS on energy, on speed, or on neither.

**Pre-registration:** `PRE_REGISTERED.json`,
sha256 `19bf54304f6454ffdf03b8de15a268af2b5b5dbfc18684f6eed2bd3733c548db`,
25040 B, mtime 2026-09-29 21:11:56 −0700, hashed 21:12:00 — written before the first
Xyce deck of Phase 2, after the generator, the vehicles, the reference implementations
and the wire arithmetic, all of which are pure Python and read only the PDK.

**Amendments:** `AMENDMENT.md` — seventeen, each with the measurement or check that forced
it. Eight are mistakes of mine. Three (B1, B8, B9) are places where the committed protocol
does not survive the move from an 8-cell bank to a cipher-width one, and two of those
turned out to be findings in their own right.

---

## The mechanism this phase adds: QAL converts wires into cells

The insight this campaign run exists to test is *"wiring does the rotate — a rotate costs
ZERO gates and ZERO levels."*

**Within one level boundary that is true, and this run confirms it.** The rotate is
implemented as exactly what it claims to be: the permutation is folded into which nets
each XOR cell reaches for, since

```
rotl(d ^ a, r)_j  =  d_{(j-r) mod W}  XOR  a_{(j-r) mod W}
```

so it costs no cells and no levels. That part is not in dispute anywhere in this run.

**Across level boundaries it is false, and that is the finding.** An unbuffered QAL bank
**returns its rail charge** at the end of its hold window. A cell's output is held up only
by its own pull-up from its own bank rail, so when that rail comes down the value is gone.
A signal produced at level *j* and consumed at level *k > j+1* cannot be routed there — it
must be **re-driven at every intervening level by a forwarding cell.** In CMOS that same
signal is a wire and costs nothing but capacitance, because a static gate holds its output
against a supply that never goes away.

So QAL converts wires into cells, at one cell per bit per level crossed. This is enforced,
not assumed: `cg.Chain.evaluate()` refuses a netlist in which any cell reads a level older
than *k−1*, so a vehicle that needs forwarding cannot be built without paying for it.

**Kogge-Stone is the favourable case and that is a real structural argument.** It is
uniform-depth — every prefix cell reads only the level directly above it — which is
exactly the property unbuffered QAL needs. A ripple CPA is not: bit *i*'s propagate must
survive *i* carry levels, so its forwarding cost grows as O(W²).

---

## Structural results — netlist facts, no simulation

Every number in this section is read off a netlist that was actually constructed and whose
output was checked against a published vector: **ChaCha20 against RFC 8439 §2.1.1** and
**AES ShiftRows against the FIPS-197 index permutation.** All ten PDK cells used were
independently verified by solving their own pull-up/pull-down switch networks from the
PDK netlist (10 cells, 56 input cases, all pass), which is also what catches a wrong
logic table.

### The two adder forms, 32-bit, same function

|  | QAL levels | QAL cells | QAL devices | CMOS cells | CMOS devices | CMOS gate depth | forwarding tax |
|---|---|---|---|---|---|---|---|
| Kogge-Stone | 7 | 504 | 2320 | 383 | 2140 | 7 | **+180 dev (+8.4 %)** |
| ripple CPA | 34 | 2576 | 5900 | 126 | 1070 | 32 | **+4830 dev (+451 %)** |

### The quarter-round, 32-bit, RFC 8439 verified

|  | QAL levels | QAL cells | QAL devices | forwarding share | CMOS cells | CMOS devices | CMOS gate depth |
|---|---|---|---|---|---|---|---|
| with Kogge-Stone | 32 | 5344 | 16960 | **74.2 %** | 1660 | 9840 | 32 |
| with ripple CPA | 140 | 24000 | 52024 | **97.4 %** | 632 | 5560 | 132 |

QAL/CMOS devices: **1.72×** with Kogge-Stone, **9.36×** with ripple.

### The adder form INVERTS between technologies

| | ripple / Kogge-Stone |
|---|---|
| **QAL** cells | **4.49×** — ripple is far worse |
| **QAL** levels | **4.38×** — ripple is far worse |
| **CMOS** cells | **0.38×** — ripple is *better* |
| **CMOS** devices | **0.57×** — ripple is *better* |

**This reframes the committed sha_slice result, and it reframes the brief's own claim
about it.** The brief says "the adder form was a harness choice, not a property of the
algorithm." Measured here: the form is not a free choice at all — it is *forced
differently in the two technologies*. A ripple CPA is the cheaper CMOS adder and the
catastrophically wrong QAL one, because its O(W²) forwarding tax is a QAL-only cost that
does not exist in CMOS.

### Corroboration of the committed 161-cell block

This run's **independently reconstructed** 8-bit ripple CPA is **164 cells over 10
levels**. The committed `qal/sha256` block that measured so badly was **161 cells over 14
banks** with an 8-bit ripple CPA. Two independent constructions landing on the same size
is evidence the reconstruction is faithful — and it explains the committed block's
tailing-off bank profile (6/5/3/7/4/7/3/4/1/1): those are forwarding levels.

---

## The wire, per bit, from the permutation

Phase 1's PDK-derived figures are inherited unchanged: **0.0930 / 0.15 / 0.2181 fF/µm**
(isolated min-width Metal2 from the LEF / the campaign figure, PDK-bracketed / min-pitch
bus), 0.515 Ω/µm.

**AES ShiftRows** — floorplan stated: 16 bytes in the natural 4×4 tile grid, 8 bit-slices
across a tile, so a column pitch is 8 bit pitches, wrap routed the short way. Source byte
`4c+r` moves to column `(c−r) mod 4`, so displacement depends only on the row: **0 / 8 /
16 / 8 bit pitches for r = 0..3**, mean 8.0. **Row 0 does not move and pays no wire at
all** — a real feature a flat mean would have erased.

At the `sg13g2_xor2_1` pitch of 3.84 µm (the cell that must physically fit per bit), the
per-bit load distribution is **32 nets at 0 fF, 64 at 4.608 fF, 32 at 9.216 fF** (mean
4.608, total 589.8 fF).

**A quarter of AddRoundKey's ShiftRows nets sit at exactly 9.216 fF — the load Phase 1
measured as both failing (fcrit 27/32) and losing the wire term to CMOS (0.749×).**

**ChaCha rotates** — `2r(W−r)/W` bit pitches: 16.0 / 15.0 / 12.0 / 10.94 for r = 16/12/8/7,
mean 13.48. At the xor2 pitch and the nominal figure, **7.767 fF per bit**.

**Adder-internal wire is derived from the netlist, not assumed.** `veh.struct_wire()` reads
each net's routed length off its own fan-out bit distances. A Kogge-Stone prefix cell at
stride *s* reads a net *s* bit positions away (1, 2, 4, 8, 16 over the five stages of a
32-bit adder) while a ripple carry is always one pitch:

| 32-bit adder | longest net | mean net | total wire |
|---|---|---|---|
| Kogge-Stone | 5.760 fF | 0.858 fF | 432.4 fF |
| ripple CPA | 0.360 fF | 0.360 fF | 927.4 fF |

So Kogge-Stone's individual wires are **16× longer** — that is the real price of its
shallow depth — and yet its **total** wire bill is **less than half** the ripple's, because
the ripple needs 2576 forwarding nets to Kogge-Stone's 504.

---

## Measured results

Beats are derived, not guessed: `BEAT_DERIVATION.json` anchors on the qal/widebank sibling's own
measured `(C_bank, t_hop)` table (read-only) and raises the beat where the worst-cell settling bar
demands it. Full data in `RESULTS.json` / `VERDICT.json` / `PAIRED.json` and the per-row
`ROW_*.json`, `TWIN_*.json`, `NAT_*.json`.

### QAL rows

| vehicle | levels | cells | wire fF/bit | E/beat fJ | E/gate fJ | level time ps | init. interval ps | rail @bound V | fcrit |
|---|---|---|---|---|---|---|---|---|---|
| AES-128 AddRoundKey | 3 | 384 | 4.608 | 2766 | 7.20 | 1647.3 | 5750 | 0.8869 | 384/384 |
| ChaCha XOR+rotate (control) | 3 | 96 | 0 | 693 | 7.22 | 875.5 | 3250 | 0.9304 | 96/96 |
| ChaCha XOR+rotate | 3 | 96 | 7.767 | 822 | 8.57 | 999.6 | 3250 | 0.8578 | 96/96 |
| Kogge-Stone adder, 8-bit | 5 | 76 | structural | 645 | 8.48 | 708.3 | 3000 | 0.8263 | 76/76 |

The AddRoundKey **bank alone** (level 2: 128 XOR2 + 589.8 fF of ShiftRows wire) is
**1858.2 fJ, 14.52 fJ per gate**.

**Every row fails G7.** The delivered rail sits below the Vtn + |Vtp| = 0.9642 V level-restoring
floor, and for AddRoundKey the rail *peak* is only **0.9446 V** — 128 XOR2 cells plus their
ShiftRows wire cannot be raised to the restoring floor at all. Every row nevertheless passes the
functional criterion with an exact value check, so these chains **compute**; they are simply not
formally restoring, and a deeper chain would degrade.

### The verdict — activity is what decides it

QAL raises and returns the whole bank rail whatever the data does, so its energy is
activity-**independent**; CMOS charges only the nodes that flip. One ratio is not a verdict — the
crossover activity is. A cipher word XOR flips about half its bits.

| vehicle | CMOS/QAL at α=1.0 | crossover α | at α=0.5 | latency | throughput |
|---|---|---|---|---|---|
| AES-128 AddRoundKey | 1.478× | **0.677** | **0.739× — QAL costlier** | 5.79× slower | 14.91× slower |
| ChaCha XOR + rotate | 1.795× | **0.557** | **0.897× — QAL costlier** | 3.44× slower | 8.95× slower |
| Kogge-Stone adder, 8-bit | 1.389× | 0.480 | 1.042× — a tie | 3.29× slower | 4.58× slower |

**The brief nominated depth-1, N = 128 AddRoundKey as "QAL's best possible case anywhere in
cryptography." Measured, it is the worst of the three** — crossover 0.677 against the adder's
0.480. QAL pays for *width* every beat and CMOS pays only for *activity*; depth costs QAL beats
but each beat buys computation, while width costs charge it cannot avoid. Wide-and-shallow is the
shape that suits QAL least.

### The wire term — the one term QAL wins, and it revises Phase 1

On the ChaCha rotate wire (248.5 fF over 32 signal nets), the incremental cost is **0.90× the
wire's own stored energy for QAL against 1.92× for CMOS — a 2.13× saving**, on a *signal* wire
sitting on cell output nodes.

Phase 1 concluded QAL "does essentially nothing for wire behind a driver" (net/stored 1.26–2.07,
ratios 0.749–1.792×) — on an **eight-cell** bank with a 124.66 ps ramp. It also named the
mechanism ("the committed cell's pull-up is too resistive for the committed ramp") and measured
that slowing the ramp to 257 ps takes net/stored to 0.721 and the ratio to 2.775×. A 32-bit cipher
bank is 20× the committed capacitance, so its ramp is **322–340 ps with no device change at all**.
At that ramp this run measures 0.90× and 2.13× — the direction and roughly the magnitude Phase 1's
own probe predicted. **Phase 1's headline is therefore revised: QAL does roughly halve signal-wire
cost, once the bank is wide enough that the ramp is slow.**

The mechanism is visible in the per-level recycle fractions: the wire-loaded level falls from
**21.80 % to 6.27 %** while its unloaded neighbours hold at 37–39 %. The wire's charge is partly
recovered *and* its presence degrades the recovery of everything else on that rail.

### Adder form — measured, composed where it had to be

The 8-bit Kogge-Stone adder was measured end to end (644.8 fJ/beat, 8.484 fJ/cell, 708.3 ps level
time, fcrit 76/76). The ripple row was not affordable, so its energy is **COMPOSED** from that
measured per-cell energy and its own exact census:

| width | ripple ÷ Kogge-Stone (energy) | ripple ÷ Kogge-Stone (time) |
|---|---|---|
| 8-bit | 2.16× | 2.00× |
| 32-bit | 5.11× | 4.86× |

### Instrument check on the one declared deviation (B13)

`qrxor` at cw = 7.767 fF/bit run at **both** the committed 0.25 ps max step and the 1.0 ps step the
AES row needed: 158 quantities compared, **worst headline deviation 2.07e-4** (E/beat 9e-6, E/gate
9e-6, worst-gate 4e-6, rail 1.9e-5, separation 2.3e-5), fcrit 96/96 both. The one large relative
outlier (8.5e-1) is on a residual inductor current of 0.0014 vs 0.0097 µA — both a thousand times
below the 1 µA gate, where a relative comparison is meaningless.

---

## Two CMOS comparators, because they answer different questions

* **SAME-NETLIST twin** (gate G9 strict) — the identical netlist, forwarding cells and all,
  on an ideal supply set to the QAL row's own measured rail peak. Isolates the
  *technology* at a fixed netlist.
* **CMOS-NATIVE** — the same *function* built the way CMOS would build it, with no
  forwarding cells. This is what an engineer would ship, so the ratio against it is the
  real one — and it favours CMOS further, making every QAL ratio conservative for QAL.

**The gap between the two IS the forwarding tax, measured.** Both are generated by the
same `flat_deck()`, and `flat_from_chain()` is checked to reproduce the chain's own
evaluated value on every cell, so symmetry is structural rather than promised.

Held-source amplitude is pinned to dV = 1.65 V on **both** sides (AMENDMENT B7); only the
*supply* is pinned to the QAL rail peak. Energy on the CMOS side is **convention-free**:
the supply is constant, so `E = vdd · ΔQ` exactly, verified against `C_switched · vdd²`
by construction.

**Activity is reported, not hidden.** A QAL beat raises and returns the whole bank rail
whatever the data does, so **QAL's energy is activity-independent**; a CMOS transition
charges only the nodes that flip, so **CMOS's energy scales with activity**. The CMOS rows
are measured with a full operand word toggled — activity 1.0 on both cipher vehicles,
which is the **worst case for CMOS and therefore conservative for QAL.**

---

## Bookings — every one a bound, with its direction named

| booking | direction |
|---|---|
| ideal CMOS supply | favours CMOS → ratios conservative for QAL |
| tank pre-charge not costed | **favours QAL** → every QAL row is a bound |
| ideal gate drives (VHI, transfer/park PWL), metered not generated | **favours QAL** |
| held sources ideal DC, identical both sides | cancels in the ratio; bounds the absolutes |
| first-cycle energy (Phase 1 A4: rails end at 0.72–0.88 V, not 0) | identical both sides; bounds interpretation |
| lumped wire C | applied identically; Phase 1 measured it worth 0.01 % vs a π ladder |
| no via or jog capacitance | understates the wire, hence understates whichever side it favours |
| switch width snapped to a √2 ladder (B9a) | ≤ 19 % off ideal conductance, every level alike |
| forwarding by one inverter | the **cheapest** physical forwarding → the tax is a LOWER bound |
| `sg13lv_compat.sp` discards ad/as/pd/ps | every implied leakage figure is a lower bound |

## What this run does NOT measure

* The **32-bit ripple CPA** is 34 levels and 2576 cells and needs 68 ZCS probe decks. It is
  reported **structurally only** — its level and cell counts are netlist facts, its energy
  is **not claimed.**
* The **full 4× quarter-round** is likewise structural. Its level structure and forwarding
  bill are exact; per-op energy composed from measured levels is labelled **COMPOSED**.
* The **steady-state cycle** (Phase 1 A4) — every energy here is a first-cycle energy.
