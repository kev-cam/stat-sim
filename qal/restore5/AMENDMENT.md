# restore5 protocol amendments

Each amendment states what forced it and when it was made. mtimes are in
`RESULTS.json._provenance.mtimes_proving_order`.

## A1 — the restoring stages are STRICTLY INTERNAL: no chain input buffer, no chain output buffer

Made **before any deck existed** (only `PRE_REGISTERED.json` was on disk; `rest.py` did not yet
exist), for two reasons, one of cost and one of experimental design.

The pre-registration said "the chain's FIRST bank is also driven through a restoring stage (whose
input is an ideal DC source), so EVERY segment-head bank has identical drive … exactly ONE reservoir
and ONE restoring stage per segment."

**Amended.** Restoring stages sit **only between segments**: for `S` segments there are `S − 1`
internal restoring stages. Bank 1 is driven by ideal DC sources — verbatim the chain3/skip4 chain
head — and bank 6 drives nothing, in **every** configuration.

Why:

1. **Experimental design.** With the input and output buffers removed, the four configurations
   (k = 1, 2, 3, no-restore) differ in **exactly one** respect: where the internal restoring stages
   sit. Bank 1's drive is identical in all four and therefore cancels out of every comparison, and so
   does bank 6's (absent) output load. With an input buffer present it would not cancel — the k = 1
   chain would carry 6 buffers against the control's 1, and the input buffer's own loading would
   differ between them.
2. **Cost.** An input plus an output buffer is 8 bits × 2 inverters × 2 devices × 2 = 64 extra
   PSP103 devices in a deck that is already ~220, for no information.
3. It also buys a **free control**: bank 1 has an *ideal* source on its gates and every other
   segment-head bank has a *real restoring buffer* on its gates. Comparing them measures directly
   whether the restoring stage's output is as good as an ideal source — a check the pre-registered
   arrangement would have hidden.

**What this does NOT change.** The economics still amortise **one restoring stage per segment**,
because that is the steady-state figure: an infinite chain restored every k banks has exactly one
restoring stage per segment. The deck's `S − 1` is the finite-chain edge effect and is stated
wherever a count appears.

## A2 — hop zeros are probed on a ONE-SEGMENT deck and validated in the full chain by the ZCS gate

Made before any measured row existed, together with A1.

The discipline requires the true current zero to be re-probed **per hop**, and the probe requires
that hop to close and never open. Probing all 6 hops of all 4 configurations that way is 24 nearly
full-length runs.

**Amended.** For each k, the zeros are probed on a **one-segment** deck (k hops, its own reservoir,
its own restored/ideal inputs, plus the trailing restoring stage that loads its last bank exactly as
the full chain does), then reused for every segment of the full 6-bank chain. This is sound because
the only path between segments is a restoring stage: its input is a high-impedance gate and its
output is driven by the fixed supply, so no segment's hop dynamics can see another segment.

**And it is not assumed — it is checked.** Pre-registered acceptance **A4** requires |I(L)| ≤ 1.0 µA
at *each* hop's own opening instant in the **full-chain** row, for all 6 hops. If the transferred
zeros were wrong for any segment, that hop's A4 would fail and be reported per hop. The no-restore
control is a single segment, so for it the one-segment deck *is* the full chain and nothing is
transferred at all.

## A3 — the reservoir hop carries NO source-side cut, so k = 1 IS the committed single hop

Made **before any measured row existed** (`rows.json` did not exist; only
`PRE_REGISTERED.json`, `AMENDMENT.md`, `rest.py`, `extract.py`, `go.py`, `ref.py`, `table.py`,
`econ.py` and the four reference/anchor decks were on disk, and no chain deck had been written).

The pre-registration said the mandatory chain3-A3 source-side cut applies to **every** hop, and
noted the consequence: "this makes even a segment's FIRST hop carry one more switch terminal than
the committed single hop, whose source was a bare lumped cap".

That consequence is not a detail — it is the difference between having a positive control and not
having one. chain3 MEASURED the source-side cut costing **t_zcs 266.76 → 353.79 ps (+32.6 %)** purely
in added capacitance on the source node, and the level time is set by how high the destination rail
**peaks** during the hop (committed VBPK 0.8369 V against a settled VBEND 0.7138 V — the pull-up's
overdrive during charging is 0.397 V, not 0.21 V, and its current goes as roughly the square of
that). Carrying an unnecessary 30 µm switch triple on the reservoir would lower that peak and make
k = 1 slower than the committed single hop **for a reason that has nothing to do with restoration**.

**And chain3's reason for the cut does not apply to a reservoir.** The measured failure it fixes is:
"the source bank stays permanently wired to its own outgoing inductor, so while bank N is being
*charged* its outgoing inductor is a shunt resonator hanging off it." A reservoir is **never charged
by a hop** — it is pre-charged in the DC operating point and drains exactly once — so it is never in
that state. The committed single hop has no source-side cut for precisely this reason and it passed
the instrument check.

**Amended.**

* **Reservoir hops** (a segment's first hop): the inductor connects **directly** to the reservoir
  node, `L{j} res{s} mid{j}` — no source switch, no `a{j}` node. The destination triple is the
  committed one, verbatim. The park phase reverts to the committed **srccut=False** form (OFF before
  and during conduction, ON only after the switch opens) because with the source permanently wired
  to the inductor an early park would discharge the reservoir to ground through L and R — which is
  exactly the committed single hop's own `VPK pk 0 PWL(0 0 117.495p 0 119.495p 1.5)`.
* **Bank→bank hops** (every later hop inside a segment): the chain3-A3 source-side triple is
  **retained unchanged and mandatory**, with the committed srccut park form.

So a k = 1 segment is `CA 35.979 fF → committed tg15p destination triple → 8-cell bank`, which is the
committed single hop's topology element for element, and the only remaining difference is that the
bank's inputs come from a real restoring stage instead of ideal DC sources.

**The reservoir also loses its head gate.** With no head gate the pre-charge is established in the DC
operating point, which is the committed chain3-A4 treatment ("the head pre-charge itself is
established in the DC operating point, so it is *not* metered in the transient") and the committed
single hop's own `.ic V(bka)=1.2`. chain3-A2's reason for a head gate — "a bare `.ic` lets bank 1's
cells charge their own outputs out of their own rail and drop it ~0.22 V" — is about a **bank**; a
lumped capacitor has no cells to charge. The per-segment pre-charge is therefore **not** idealised
away: it is MEASURED in its own dedicated deck (`qpre.cir`, with a real 1.0 µm/1.12 µm head gate and
its own metered supply) and carried into the economics from there. The reservoir's voltage at its own
hop's opening instant is reported on every row so that any drift away from dV across the run is
visible rather than assumed absent.

## A4 — the pre-registered restoring stage DOES NOT RESTORE. Its own input load pushes the QAL level below its own trip point

Forced by a MEASUREMENT, on the first one-segment deck ever run in this directory
(`s_k1_T300.cir`, the k = 1 positive control). The four k-sweep rows that were in flight when this was
found are kept as `rows_v1_standard_receiver.json` — they ARE this amendment's evidence.

MEASURED, k = 1 segment (reservoir → committed tg15p hop → 8-cell bank, bank's 8 outputs loaded by the
pre-registered restoring stage):

| | committed single hop, NO restore load | this deck, WITH the restoring stage on the outputs |
|---|--:|--:|
| rail peak `VBPK` | 0.8368896 V | **0.7601 V** |
| rail settled `VBEND` | 0.7138163 V | **0.6007 V** |
| bank pull-UP output, settled | = rail (100 %) | 0.6006 V (= rail, 100 %) |
| restoring stage, 1st inverter output | — | **1.1253 V — it never flips** |
| restoring stage output `rb` | — | **0.000 V — the HIGH is restored as a LOW** |

The bank itself is fine: its pull-UP output tracks its rail to 100 %, its pull-DOWN output sits at
−0.0002 V, and at the stage boundary the worst gate is 97.7 %. **The restoring stage is what fails**,
and it fails for a reason that was hiding one level down:

* the pre-registered restoring stage is the campaign's standard 1.12 µm pMOS / 0.74 µm nMOS inverter.
  Its MEASURED trip point is **0.6452 V** (committed `qal/bound/` H1 cell A1, DC sweep);
* putting that cell's 8 input gates on the bank's outputs is 8 × 1.86 µm of extra gate load on the
  bank's rail and outputs, and it drags the delivered level from 0.7138 V down to **0.6007 V**;
* 0.6007 V is **44.5 mV BELOW the restoring stage's own 0.6452 V trip point.** The restoring stage's
  own input capacitance lowers the level it exists to restore, to below the level it can resolve.

This is exactly the failure class the campaign has been bitten by twice (M2 stepwise: the step switches
own gates; M1-C: a freeze switch whose width tracked its load), and it was caught only because the
restoring stage was built at transistor level *inside* the deck instead of being represented by an
idealised source. Had it been idealised, k = 1 would have "passed" and the whole study would have been
wrong.

**It is also not a new discovery — the committed record already refuted this exact cell.** `qal/bound/`
H1 VERDICT: *"REFUTED for a standard gate; CONFIRMED for a re-sized one"*, on three independent
failures at a QAL high of 0.6759 V: **MARGIN** 31 mV; **STATIC** 8.78 µA of contention = 3.090 fJ per
bit over one 293 ps hold = 36.7 % of the whole hop; **SPEED** it never crosses the downstream trip
inside the 286.7 ps valid window. My 0.6007 V level is *worse* than the 0.6759 V that refutation was
measured at, so the failure is not merely reproduced, it is deeper.

**Amended.** The restoring stage becomes the receiver the committed track proved works, re-sized, not
re-invented:

* **first (receiving) inverter: pMOS w = 0.15 µm / nMOS w = 1.48 µm**, l = 0.13 µm, on the fixed
  1.2 V supply `vres` with its pMOS bulk on `vres`. This is `qal/bound/` H1 cell **A4**, MEASURED trip
  point **0.4595 V** — 141 mV below my delivered 0.6007 V, and below the campaign's worst measured
  VBEND (tg60, 0.5763 V) as well, so it works for the whole family and not just this row. Its MEASURED
  static current at a QAL high input is **0.0339 µA** against the standard cell's 8.78 µA, a 259×
  reduction in the contention term. It is also *lighter*: 0.15 + 1.48 = 1.63 µm of gate against the
  standard cell's 1.86 µm, so it loads the bank it reads LESS, which lifts the delivered level rather
  than lowering it.
* **second inverter: unchanged, the campaign standard 1.12 µm / 0.74 µm** on `vres`. Its input is now
  a full-swing 0/1.2 V node, so there is no reason to skew it, and keeping it standard means the pair
  is still non-inverting and the `is_hi` convention still carries across a restore unchanged.
* CL 2 fF stays on both the internal and the output node, so each inverter still carries exactly a
  bank cell's load.
* **No extra rail.** The committed track's chosen fix put the first stage on a *reduced 0.9 V rail*
  as well. I do not take that: A4's trip point at the full 1.2 V is already 141 mV clear of my level,
  and a second supply is a cost (a whole extra rail and its network) that I would then have to carry
  and justify. Reported as a knob that exists and was declined, not as a knob that was used.

**What this amendment costs, and I will measure all of it, not assume it:**

1. the 0.15 µm pMOS is a weak pull-up, so the receiving inverter's rising edge is slow — the committed
   track measured the whole two-stage conversion at **277.6 ps** and found a **latency FLOOR of
   ~145 ps** at SG13G2 that 4× nMOS upsizing cannot get below (and which costs 3.9× the input
   capacitance to approach). If that floor holds in my deck, the restoring stage's latency is LARGER
   than the QAL beat period itself, and that is the whole economics answer;
2. the receiver is skewed, so its own noise margin on the *low* side shrinks — reported;
3. its supply energy is still metered on `vres` by the same 1F integrator, switching and static
   together, and now also per beat-window, so the 500 ps tail cannot flatter it.

**The v1 rows are not discarded.** The no-restore control (k = 6) has no restoring stage in its data
path at all — its single restoring stage is a trailing LOAD on bank 6 and feeds nothing — so its
per-bank settling is unaffected by this amendment except through that load, and it is re-run under A4
anyway so that all four configurations carry the identical load. Every k = 1/2/3 v1 row whose
segment-head bank was fed by a restoring stage is reported as **VOID for acceptance** (its inputs were
the wrong logic values) and kept only as this amendment's evidence.

## A5 — the restoring stage's latency definition: correctness first, and the latency is SIGNED

Forced by the same first one-segment deck as A4, and by what happened when the pre-registered M3
definition was applied to it.

Pre-registered M3: *"t_res MEASURED … input edge to output crossing, 50% and 90% referred, for the
PAIR and for the single inverter … from the instant the driving segment's data is declared valid — that
bank's stage boundary — to the instant the restoring stage's OUTPUT reaches 90% of its final level."*

Two things are wrong with that, and both were exposed by measurement:

**(i) "90 % of its FINAL level" would have scored the A4 failure as a healthy number.** On
`s_k1_T300.cir` the restoring stage settled cleanly and quickly — on the WRONG logic value (`rb` = 0.000 V
for a bit whose datum was a HIGH). "Reaching 90 % of its final level" is satisfied by a stage that has
confidently restored the complement. **Amended: correctness is checked first and is not optional.** The
expected value of bit *i* out of bank *b* is `not is_hi(b, i)`; a restoring stage counts as restoring only
if its output settles on the matching rail to full swing (≥ 0.9·dV for a HIGH, ≤ 0.1·dV for a LOW). A row
whose restoring stages fail that is marked **VOID for acceptance**, because the banks they feed were
evaluating the wrong logic values and their settling percentages do not mean what the convention says.
All eight bits are checked, not only the two that are printed: for a segment-head bank the gate net *is*
the restoring stage's output, so the per-gate `G{j}_{i}B` measure already carries every restored level.

**(ii) Searching forward from the boundary reports None for a stage that is ALREADY done, and None
reads as a failure.** A restoring stage is **combinational**: it tracks its input continuously and flips
when that input crosses its trip point, which happens *partway through* the bank's settling, not after it.
MEASURED, its output can therefore be valid **before** the driving bank's own stage boundary. **Amended:**
the search starts at the driving bank's own hop close, and the latency is reported **signed** —
`cross − boundary`, negative meaning the restoring stage adds no pipeline latency at all. What the next
segment must actually wait for beyond its data being valid is `max(0, latency)`, and that is the term
that enters the economics. Both the pair and the single inverter (internal node) are reported, so a
cheaper half-restore can still be priced.

Neither change loosens anything: (i) adds a gate the pre-registration did not have, and (ii) replaces a
number that could only ever be *pessimistic-by-mistake* (None) with the measured signed value.

## A6 — the one-segment zero transfer FAILED its own check; the zeros are re-probed per structural class

Forced by acceptance **A4** on the k = 1 six-bank chain — i.e. by the check AMENDMENT A2 promised
would catch exactly this.

A2 probed the hop zeros on a ONE-SEGMENT deck and reused them for every segment of the full chain,
arguing that segments cannot see each other through a restoring stage, and stated: *"it is not assumed
— it is checked … If the transferred zeros were wrong for any segment, that hop's A4 would fail and be
reported per hop."*

MEASURED on `c_k1_T300.cir`, |I(L)| at each switch's own opening instant, against the 1.0 µA gate:

| hop | 1 | 2 | 3 | 4 | 5 | 6 |
|---|--:|--:|--:|--:|--:|--:|
| I_zcs (µA) | **−0.0045** | 11.17 | 18.04 | 17.97 | 17.97 | 16.25 |

Hop 1 passes; hops 2–6 fail by an order of magnitude. A2's reasoning was right about *coupling* and
wrong about *identity*: no segment sees another, but at k = 1 the six hops are not the same hop. They
differ in what loads their destination bank:

* **class A** (hop 1): destination's gates driven by IDEAL DC sources, outputs loaded by a restoring stage;
* **class B** (hops 2–5): destination's gates driven by a restoring stage's OUTPUT, outputs loaded by the next restoring stage;
* **class C** (hop 6): destination's gates driven by a restoring stage, outputs load NOTHING — it is the end of the chain.

A one-segment deck contains only class A, so it cannot produce the other two zeros.

**Amended.** The zeros are re-probed on a **three-segment** deck, which contains exactly one hop of
each class, and mapped **A, B, B, B, B, C** onto the six hops of the full chain; the row is re-run and
A4 re-checked per hop. Three short probes instead of six full-length ones, and no class is assumed.

**What this does and does not change.** It is an INSTRUMENT correction: the switch was opening a little
off the true zero, leaving 11–18 µA (1.1–1.8 % of the 975 µA peak) in the inductor. The affected row's
settling verdict was never close to its threshold — every gate in every bank read 98.39–100.03 %
against a 90 % line — so the acceptance outcome does not turn on it. The corrected row `k1_T300_zcs`
is the one quoted; the uncorrected row `k1_T300` is kept, with its failing per-hop A4 shown, because it
is this amendment's evidence. The same transfer was used for k = 2 and k = 3, whose rows are VOID for
acceptance on A5 anyway; their per-hop A4 is reported as measured and not corrected, and no number is
quoted from them beyond the level collapse that voids them.

## A6b — A6's three-class probe cleared 3 of 6 hops; the residue is closed with a MEASURED slope correction

A6 re-probed the zeros on a three-segment deck and the re-run row `k1_T300_zcs` MEASURED, per hop:

| hop | 1 | 2 | 3 | 4 | 5 | 6 |
|---|--:|--:|--:|--:|--:|--:|
| I_zcs (µA), after A6 | **−0.0022** | **−0.0066** | 7.006 | 6.939 | 6.940 | **−0.119** |
| I_zcs (µA), before A6 | −0.0045 | 11.17 | 18.04 | 17.97 | 17.97 | 16.25 |

Hops 1, 2 and 6 now pass the 1.0 µA gate. Hops 3–5 do not: 6.94–7.01 µA, i.e. 0.7 % of the 906 µA
peak. **A6's three-class model was incomplete.** Hop 2's destination is fed by a restoring stage that
reads an IDEAL-input bank; hops 3–5's destinations are fed by restoring stages that read
RESTORE-input banks. Those two produce slightly different gate-voltage trajectories during the hop,
hence slightly different zeros — a fourth class.

**Amended, without adding a fourth probe.** The residual offset is closed with a correction that is
itself MEASURED off the failing row: `dI/dt` is least-squares fitted to `I(L)` over the 6 ps
immediately before each switch's own opening instant (**MEASURED −40.72 µA/ps**, consistent across
hops 2–6 within 0.7 %), and the zero is shifted by `−I_zcs/(dI/dt)`, giving **+0.1720 / +0.1704 /
+0.1704 ps** on hops 3/4/5. No analytic `π·sqrt(LC)` enters at any point — the discipline's warning
that the analytic zero read 266.76 ps against a measured 353.79 ps stands and is respected.

The corrected row is `k1_T300_zcs2`. Both earlier rows are kept: `k1_T300` (one-segment transfer, the
evidence for A6) and `k1_T300_zcs` (three-class probe, the evidence for A6b). Throughout, the
acceptance verdict never turned on this: the worst gate in the worst bank read 98.39 % against a 90 %
line in all three versions, and a 0.17 ps switch-timing error is 0.26 % of a 65.8 ps hop.
