# chain3 protocol amendments

Five amendments, A1-A5. **A1 and A2** were made after the instrument check (which passed
bit-identically) and after the first two topology-calibration PROBE runs, but **BEFORE any measured
chain row existed** (`rows.json` did not exist; the only chain artifacts on disk were
`p1_a277_free.cir`, `p2_a277_free.cir` and one aborted `c_a277_free.cir`) — no measured chain result
informed them. **A3 and A4** were made during the pre-registered validation at the known-good slow
point, before any swept-L row existed. **A5** was made after the first top-up row, which was then
re-run; every reported top-up row uses the amended placement. Each amendment states the MEASUREMENT
that forced it. mtimes are in `RESULTS.json._provenance.mtimes_proving_order`.

## A1 — the pre-registered per-bank symmetry devices inflate the bank by ~2× and move the anchor

Pre-registration `TOPOLOGY_pre_stated.symmetry_devices` put a tg15p-sized supply transmission gate
on **every** bank (disabled on banks 2 and 3 in the free-running chain) plus a dummy always-off
incoming transfer switch on bank 1, so that all three rails would carry identical parasitics.

MEASURED consequence, from the two probe runs at L = 277.8 nH:

| | t_zcs hop 1 | t_zcs hop 2 |
|---|--:|--:|
| committed single hop (frozen comparator) | 266.76 ps | — |
| chain, pre-registered heavy topology | **369.23 ps** | **362.55 ps** |

The transfer switch and the supply TG are **15 µm of device width each**, against a bank of
8 × (1.12 + 0.74) = **14.9 µm** of cell width. Carrying a supply TG on every bank plus a dummy input
switch on bank 1 therefore roughly **doubles to triples** each bank's capacitance and pushes the
resonant half-period **+38%** away from the frozen single-hop comparator. The whole point of the
L sweep is to compare the chain against that comparator at the same L; a 38% capacitance offset
would have made every row non-comparable and the headline meaningless.

**Amended.** The free-running chain is MINIMAL and matches the committed single hop's own
asymmetry, which is the configuration the anchor was measured in:

* source of hop 1 = bank 1 = 8 cells + a small head pre-charge gate — capacitively the counterpart
  of the committed hop's lumped `CA` (MEASURED 35.98 fF = the 8-cell bank's own secant C at 1.0 V);
* destination of each hop = 8 cells + that hop's transfer-switch drain — exactly the committed
  destination node;
* **no dummy input switch**, **no supply TG on banks 2 or 3** in the free-running chain.

The supply TGs on banks 2 and 3 appear **only** in the top-up variant, where they are the top-up
device. They therefore make the topped-up banks heavier than the free-running ones, which is a
**real cost of top-up** (it slows the hop) and is reported, not hidden: the pre-registered control
run (`TOPUP_pre_stated.control_run`) is kept and inverted — it now runs the chain with the banks-2/3
supply TGs **present but disabled**, isolating the added capacitance from the top-up's effect.

Hop 2's source (bank 2 = cells + switch-1 drain) stays heavier than hop 1's source (bank 1 = cells +
head gate) by one switch drain. That asymmetry is not removed: it is what a steady-state pipeline
stage actually looks like, hop 2 is the row used for the steady-state per-hop droop estimate, and
both hops' zeros are probed separately anyway.

## A2 — the head pre-charge gate is small, and its cut edge is 20 ps

With the head gate at tg15p size (5 µm / 10 µm), the measured deck **aborted**: `Time step too
small near step number 722`, 7 nonlinear convergence failures, at **t = 180.00 ps** — the exact
instant the head gate's 2 ps cut edge fires. A 15 µm gate dumping its channel charge into a
floating ~36 fF node in 2 ps is a stiff event, and the node has no DC path once the gate is open.

**Amended.** The head gate is built from geometries already in this run's PyMS cache — nMOS
w = 1 µm + pMOS w = 1.12 µm — and its cut edge is **20 ps**, over [T1 − 40, T1 − 20] ps, leaving
20 ps of float before hop 1's gate moves. Justification: the head gate's only job is to pre-charge
36 fF during a 180 ps pre-roll (≈ 0.2 µA), so 2 µm of width is ample, and at 2 µm its channel
charge is ~7× smaller. The committed **2 ps edge is retained unchanged for every transfer-switch
phase** (`VGT*`, `VGTP*`, `VPK*`) — the head gate is not a committed element and its edge was never
part of the committed protocol. `vt` and `gmin` were not touched; `.OPTIONS TIMEINT METHOD=GEAR
RELTOL=1e-6 ABSTOL=1e-15 CHGTOL=1e-17` is unchanged.

`HEAD_LEAD` becomes 40 ps (was 20), so the pre-roll before hop 1 is still 200 ps and bank 1's
measured settling at its checkpoint is reported as the check that the pre-roll was long enough.

## A3 — a SOURCE-side cut is required; the committed receiving-side-only switch does not compose

Made during the pre-registered validation at L = 277.8 nH, **before any swept-L row existed**
(`rows.json` held one row, `a277_rxonly`, and nothing else).

MEASURED on `c_a277_rxonly.cir` — the A1/A2-amended chain, differing from the working chain **only**
by the absence of a source-side cut:

| | hop-1 charge through L1 | through the **idle** L2 | peak idle \|I(L2)\| | hop-2 rail drain |
|---|--:|--:|--:|--:|
| receiving-side cut only (committed) | 44.231 fC | **18.72 fC (42.31 %)** | **103.80 µA** | 0.442 residual |
| + source-side cut | 62.216 fC | **2.4e-5 fC (0.00004 %)** | **0.000 µA** | −0.0012 residual |

With the cut only on the receiving side the source bank stays permanently wired to its own outgoing
inductor, so while bank N is being *charged* its outgoing inductor is a shunt resonator hanging off
it. The branch rings with τ = 2L/R = 55.6 ns, so it **cannot** damp inside any usable inter-hop gap:
hop 2 measurably opened with −34.9 µA already circulating and left 44.2 % of bank 2's rail undrained.

**Amended.** Each hop gets an **identical tg15p triple on the source side**, sharing that hop's same
gate phases — `XSWSN{k}/XSWSP{k}` between `rail{k}` and the inductor's near node `a{k}`. The
destination triple is unchanged (committed, verbatim). Conduction cost is negligible (I²R 0.137 fJ of
a 23.8 fJ hop). The capacitance cost is not: a chainable bank now carries two switch terminals
instead of one, and t_zcs at the anchor goes 266.76 → 353.79 ps (+32.6 %). That is reported on every
row, and the `a277_rxonly` row is kept as the row that motivates it.

Two corollaries, both MEASURED:
* the **source-side node needs no park**. Releasing one before the switch closes leaves `a{k}`
  momentarily isolated → abort at exactly that instant; releasing it after shorts the source rail to
  ground through it for one edge (~3 fC, 9 % of the bank charge). It floats, pinned by `.ic`.
* the committed **destination park can now be HELD ON while a hop is idle**. The committed
  AMENDMENT-A3 hazard (park shorts the source rail to ground through the inductor) is exactly what
  the source cut removes, and holding it is what pins the otherwise-floating inductor island
  `{a,mid,sw}` — leaving that island floating aborts the run at the first gate edge.

## A4 — the supply charge is metered on the dV source, not on a series 0 V source

`BXqtu1 0 xqtu1 I={ I(VTU1) }` reads the branch current of a 0 V source feeding an **open circuit**
once the head gate cuts. That is degenerate, and MEASURED it aborted the run (`Time step too small`,
7 nonlinear convergence failures) at the first gate edge. A bisection over all 18 integrators
isolated it to **that one**: dropping `qtu1` alone ran the deck to completion, and dropping any other
single group did not. `RX` 0.01 → 1 Ω did not help either, so it was not integrator conditioning.

**Amended.** The 0 V series sources are removed and the supply charge is metered once, on the
always-connected ideal source (`qdv = −I(VDV)`), then split by **disjoint** checkpoint windows — the
head window, bank 2's top-up window and bank 3's are disjoint by construction, so differencing `qdv`
between checkpoints gives each exactly. Note the head pre-charge itself is established in the DC
operating point, so it is *not* metered in the transient; the chain's input energy is quoted from the
bank's own measured static stored energy at its checkpoint instead.

## A5 — the top-up sits at the START of the inter-hop gap

Made after the first top-up row, which was then **re-run**; every top-up row reported uses the
amended placement.

The window first spanned the whole gap, ending 2 ps before the stage boundary. That restores the rail
immediately before settling is read, and the committed settling convention is a ratio to the
**instantaneous** rail — so it moves the goalpost: MEASURED 46.3 % at bank 2 on a chain whose rail was
fine (0.792 V), because the outputs had not followed the jump.

**Amended.** The top-up conducts for a 20 ps window at the **start** of the gap (`TOPUP_W`, clamped to
the gap), restoring the rail first and letting the cells settle against the restored rail for the
rest of the gap. This is also the placement that exposes the real tension, which is reported rather
than tuned away: a short window lets the rail sag as the bank pays for its own gates out of its own
charge (0.792 → 0.701 V), while a long window clamps the bank to the supply and the top-up simply
*is* the power supply.
