# qal/fastwave — PHASE 1: the self-consistent (N_bank, W_switch, L) corner search for MINIMUM BEAT

The objective is the **beat period**. Energy is reported on every row and gates
nothing, anywhere.

This run goes the **opposite way from every committed deck**. Every committed
deck uses 8 static inverters per bank, a 15–30 µm switch and L = 15–278 nH — a
bank sized so the transfer energy amortises, with a deliberately slow hop. The
sibling `qal/widebank/` sweeps N upward for energy. This one sweeps N **down**
for speed, on a pass-gate XOR bank, at dV = 1.65 V.

## Order of work (mtimes are the witness)

| file | mtime | what |
|---|---|---|
| `DISK_STATE_BEFORE.txt` | 19:46:26 | disk state + sha256 of every committed input, before anything |
| `PRE_REGISTERED.json` | 19:50:27 | acceptance, the grid, the cell choice, six pre-stated predictions |
| `PRE_REGISTERED.sha256` | 19:50 | `c23021e9e97089bf60826b118ec44ddaa874dd1f51049df1ae226c062cc05638` |
| `F1_cmos_anchor.cir` | 19:51 | **first deck** — a byte-identical copy of a committed one |
| `AMENDMENT.md` | 20:4x → | ten amendments, each with the measurement that forced it |
| `RESULTS.json` | — | the record |

## The headline

**The feasible frontier is EMPTY at the committed gate drive, and the constraint
that empties it is NOT Q.**

Of 64 measured (N, W, L) points at dV = 1.65 V and the committed VGH = 1.5 V,
**none** clears all five pre-registered gates. The binding gates are the
delivered-rail ones. Q is not binding at all: the frontier sits at Q = 8.81 and
**Q = 39.19 was measured** on a row that is still infeasible because its
delivered rail is only 0.8981 V. Over the width ladder at N = 2, L = 15 nH,
Q goes 18.96 → 27.98 → 39.19 while the delivered rail goes 0.9641 → 0.9273 →
0.8981 V. **Raising Q lowers the delivered rail.**

### The missing degree of freedom was the gate drive, not (N, W, L)

dV = 1.65 V **exceeds** the committed VGH = 1.5 V, so the transfer nMOS has
Vgs < 0 over the top of the swing and is cut off there. The measured
loss-equivalent channel resistance is **179–190 Ω at W = 15 µm** across every N
and every L — 1.45× the 96–130 Ω `qal/lsweep` measured at dV = 1.0, and ~3× its
13.7 Ω at W = 240 µm. Swept as a declared fourth axis, VGH has an **interior
optimum at exactly dV + Vtn = 1.65 + 0.5240 = 2.174 V**, and more is worse:

| VGH (V) | Ron (Ω) | Q | VBEND (V) | VA_open (V) | verdict |
|---|---|---|---|---|---|
| 1.500 | 103.0 | 4.36 | 0.9059 | 0.1717 | fails rail |
| **2.174** | **34.3** | **8.81** | **0.9935** | **0.2344** | **FEASIBLE** |
| 2.400 | 30.5 | 9.65 | 0.9975 | 0.2497 | fails drain |
| 2.800 | 27.6 | 10.41 | 0.9998 | 0.2874 | fails drain |

(N = 4, L = 6 nH, W = 30 µm.) **The device ask is a gate drive of dV + Vtn — not
a lower Ron.** A 2.174 V drive on a 1.5 V-tolerant LV device is an overdrive and
an oxide-reliability question this run does **not** answer.

### Three beats, and only the last one may be quoted for a wave

| beat | value | (N, W, L, VGH) | what it means |
|---|---|---|---|
| functional, single hop | **130.91 ps** | 4, 30 µm, 6 nH, 2.174 V | hands on a **0.597 V** level |
| inherited 90 %-of-rail bar | 230.66 ps | same | the committed comparable |
| **level-restoring (cascadable)** | **243.64 ps** | 4, 30 µm, 15 nH, 2.4 V | outputs clear 0.9642 V |

The 130.91 ps beat is real for one hop scored against a receiver's measured trip,
and it is **not cascadable**: at that instant the bank's own outputs are 367 mV
below the Vtn + |Vtp| floor the next bank needs to restore. The hop is only
36.9 % of it — the level is **settle-bound, not hop-bound**.

### Against CMOS, at the cascadable beat

The load-matched comparator is the **2 fF / 57.1428 ps** one — this run's TG-XOR
cells each carry CL = 2 fF, the same load the 2 fF arm of `qal/fcrit/cmos.cir`
drives. (The 6.91 fF / 94.1745 ps figure is the committed headline but flatters
QAL, and is reported alongside.)

* level: **4.26× slower** than CMOS (2.59× against the 6.91 fF comparator).
* with the flop tax, `t_level + t_reg/D` at t_reg = 315.38 ps (interpolated to
  2 fF from the measured 307.1 / 335.7 / 390.0 ps): **crossover D\* = 1.69
  levels** — 2.25 against the 6.91 fF comparator. Removing the liberty's
  1.11–1.21× optimism moves D\* only to 1.87–2.05.

**QAL wins only at D = 1**, a flop after every single logic level, which is not a
design point. At the *functional* single-hop beat D\* = 4.28, but that beat
cannot be cascaded, so it is not a pipeline number.

## The mechanism, measured

The rail **peaks above the floor and then sags**. At the frontier row VBPK =
1.3011 V and VBEND = 0.9935 V. `diag_hop.cir` attributes the 10.3 fC that leaves
the rail node: **4.34 fC** to the bank's internal nodes via the metered ground,
**4.15 fC** back into the `vhi` n-well supply, **1.27 fC** onto the output load —
≈ 9.8 of 10.3 fC. It is charge **redistribution inside the destination bank**,
not leakage: `ab`, `bb` and `y` cannot follow a ~48 ps hop and go on drawing from
the rail for another 100–200 ps.

That is why small N loses. `C_ser_eff` **is** affine in N, to 0.79 % —
`C_ser = 8.510 + 6.5877·N` fF at W = 15 µm, L = 15 nH, and the slope is half the
independently measured 13.19 fF/cell bank capacitance to 0.1 %, exactly the
symmetric-series prediction. So halving N does cut t_hop and raise Q, as
pre-registered. But a smaller bank has **less stored charge to hold its rail up**
against the same per-cell redistribution, and the rail is what binds.

## Three of six pre-registered predictions are wrong

* **P0 falsified** — symmetric banks did *not* lift the delivered-rail fraction
  to ≥ 0.80; it saturates at 0.54–0.60, *worse* than the committed ~0.69. My
  hypothesised mechanism (a source/destination capacitance mismatch) was also
  wrong; the measured mechanism is the redistribution above.
* **P1 half right** — the affine-in-N mechanism is confirmed to 0.79 %; the
  conclusion that the frontier sits at the *smallest* N is **falsified** (it is
  at N = 4, and every N = 2 row fails at every W, L and gate drive up to 2.8 V).
  The L half is confirmed: L_opt = 6 nH and all ten L ≤ 0.5 nH rows are
  infeasible.
* **P2 falsified** — I pre-stated a 70–95 ps minimum feasible beat; it is
  130.91 ps. The sub-prediction that the hop would be under 45 % of the level is
  confirmed (36.9 %).
* **P3 headline right, reason overturned** — the load-matched comparator is the
  2 fF one, QAL loses at the level, and the case rests on the flop tax: all as
  pre-stated. But I said **Q forbids it, and Q does not**. Q is not the binding
  constraint anywhere in this run.
* **P4 falsified as stated** — widening penalises the level time monotonically in
  only one of six (N, L) cells; elsewhere there is an **interior optimum in W**
  (at N = 2, L = 1 nH the widest is 17.3 % *faster* than the narrowest). The
  penalty and its mechanism are confirmed *above* the optimum width: the rail
  peak falls monotonically with W at every (N, L).

Full scoring in `RESULTS.json : K_PREDICTIONS_SCORED`.

## Instrument

PASS at rel **0.00e+00** on all 22 digit-checked quantities, before any sweep
point: the fourteen `.mt0` measures of `qal/fcrit/cmos.cir` (reproducing
94.1745 ps at 6.91 fF and 57.1428 ps at 2 fF) and the eight committed `tg15p`
hop headlines of `qal/swsweep/sw_tg15p_z.cir` — the latter extracted with
`qal/lsweep/lsw.py`'s own `extract` **imported**, not re-implemented. Both decks
are byte-identical copies, re-run under this run's private `PYMS_VAE_CACHE`.

## What is a BOOKING, and what this run does not license

* The **source bank is a lumped CA**, set to the measured rail capacitance of the
  same N-cell bank. Every row is a **BOUND**.
* The **cell inputs are ideal DC sources** at a fixed 1.20 V. This hides a real
  cost: a TG-XOR cell **shorts its two data inputs together** while the rail is
  below the level that separates its select signals (measured: 176 fC out of one
  input over a 4 ns ramp). In a chain that current comes out of the
  predecessor's outputs. `AMENDMENT.md A4`.
* **No interconnect anywhere.** Phase 1 numbers are bounds in the optimistic
  direction; the shim also drops `ad/as/pd/ps`, so every leakage figure is a
  lower bound.
* **Phase 1 measures ONE hop into ONE bank.** No row here is a beat for a wave,
  and no row is quoted as a chain result.
* 16 of 134 points never converged and are listed by name in
  `RESULTS.json : C_THE_SWEEP`; two rows fail the strict `|IZ| ≤ 1 µA` instrument
  gate at 1.08 and 1.25 µA (stranding 2.3e-6 fJ) and are reported as instrument
  failures, not results.

## Files

| file | what |
|---|---|
| `fw.py` | the harness — decks, probe, extractor, gates |
| `warm.py` | pre-warms all 15 PSP103 geometries (the `.so` is per (card, W, L), ~450 s each) |
| `instr.py`, `INSTRUMENT_CHECK.json` | the two committed anchors, digit-checked |
| `CBANK.json` | the MEASURED bank rail capacitance vs N |
| `drive.py`, `spec_*.json`, `ROWS.json` | the sweep |
| `audit.py`, `AUDIT.json` | re-reads the gate drive and bank content out of **every** netlist and compares it to the spec that asked for it |
| `reextract.py` | re-extracts every row from decks on disk, no re-simulation |
| `diag_n4.cir`, `diag_hop.cir` | the two attribution decks behind amendments A4 and A6 |
| `try_s4/s16/reltol4.cir` | the convergence cross-check behind A8 |
| `T_RESTORING.json` | the measured cascadable beat per feasible row |
| `analyse.py`, `RESULTS.json` | the record |

A contamination bug I introduced — reused pool workers leaking the previous
point's gate drive into eight rows, one of which would have become a wrong
headline — is written up in `AMENDMENT.md A9` together with how it was caught
and the audit that now covers every deck.
