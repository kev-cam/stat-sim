# qal/strip — amendments, corrections and post-hoc additions

Every change made after `PRE_REGISTERED.json` was written, in the order it
happened, with what forced it. `PRE_REGISTERED.json` was the only file in this
directory at 2026-09-29 14:20:05 −0700, sha256
`c1f039a2227da6823dd0ace2be6926296708e96b95d89a1cb834a5f2984166ef`.

## A1 — factored trees, not sums of products (before any cell deck ran)

The first `cells.py` expressed each nMOS tree as a sum of products, which
duplicates a literal shared by several cubes: o21ai's pull-down came out as
`(A1·B1) ∥ (A2·B1)` = **4** devices instead of the factored
`(A1 ∥ A2) · B1` = **3**, so the stripped o21ai counted 9 devices instead of 8
and would have made the pre-registered device-count prediction look wrong for
an implementation reason. Corrected to a series-parallel expression tree with a
recursive emitter. Caught by the device-count self-check, **before the first
cell deck was generated**; no measured row used the SOP form. Every tree is now
verified exhaustively against that cell's own PDK truth table
(`crossover.py`, 13/13 families, all vectors).

## A2 — `.DC` abandoned for constant-bias transients

`leak_off.cir` and `leak_gate.cir` used `.DC`. Neither returned inside 300 s
under the PyMS-compiled PSP103 here; both were abandoned and are **left on disk
as the record of the attempt** (`leak_off.cir`, `leak_gate.cir`, no `.prn`).
Replaced by `leak2.py`: N independent copies of the device, each at its own
constant bias, in one deck, read at a true steady state. A slow ramp was
rejected on the arithmetic, not by trial — the displacement current through a
2 fF node on even a 20 ns ramp is ~40 nA, which swamps the sub-nA quantity being
measured.

## A3 — the null control, forced by the first leakage number

L3 measured a 2 fF node holding 0.5571 V for 2 ns and reported a droop of
575 nV. `RELTOL = 1e-6` on that rail is 557 nV. **The measurement sat on the
solver's own voltage resolution**, so it could not be quoted. `leak3.py` adds a
NULL control — a 2 fF capacitor with nothing attached — and a 100 ns hold.
Result: the null node droops **0.00 µV over 100 ns**, so the droop on the real
node is modelled leakage, not drift, and the 100 ns window puts the signal 50×
clear of the floor. The 2 ns number is superseded by the 100 ns slope.

## A4 — the GMIN floor, forced by the gate-current reading

`LEAK_DC.json`'s gate-terminal current came out at **exactly `rail × 1e-12 A`**
for every nMOS width and every rail — the signature of a 1e-12 S conductance,
not of gate tunnelling. That put the off-state numbers in question too, so
`gmintest.py` measures what a known 1e12 Ω path looks like in this harness and
what a hard-off device (Vgs = −0.3 V) still shows. Note the direction of the
bias: any GMIN component **inflates** the measured leakage, so the leakage
budget is an upper bound however the split lands. Gate leakage is reported as
*below the floor of this setup*, not as a measured value. `vt`/`gmin` were not
touched (campaign rule).

## A5 — "the moment it conducts" redefined (re-extraction only, no re-simulation)

The first extractor took the pull-up's conduction instant as the maximum
`dV/dt` of the rising node. That lands at the very start of the rail ramp, where
every node is being dragged up by the rail itself and the pull-up has done
nothing — the anchor row reported it at t = 50.000001 ps with the rail at
0.043 V. Redefined as the maximum of `d(V_node − V_rail)/dt`, the node gaining
*on* the rail, and reported alongside the node's 50% crossing, the freeze
instant and the end, so no single definition carries the claim. Applied by
re-extraction from the `.prn` files already on disk (`st.py reext`); no row was
re-simulated and no deck changed.

## A6 — POST-HOC sweep extension (declared post-hoc, not pre-registered)

The pre-registered cross-coupled pMOS width set was {0.15, 0.56, 1.12} µm,
chosen on the DCVSL convention *"the latch must be weaker than the tree"*.
The first measured row (`s_o21ai_dv150`, wxc = 0.56) shows that convention is
**the wrong way round for this application**: every pull-DOWN node settles to
100.06–100.12% — the trees win easily — and it is the PULL-UP that is short
(75.46% on the worst node). The pre-registered set therefore does not bracket
the optimum. Added, and labelled post-hoc wherever quoted:

* `s_o21ai_dv150_wxc224`, `s_o21ai_dv150_wxc448` — extend the width sweep upward.
* `s_o21ai_dv165`, `c_o21ai_dv165`, `s_o21ai_dv165_wxc224` — restore the RAIL.
  The stripped bank depresses the delivered rail (dual-rail puts twice as many
  output nodes on one tank), and the pull-up's overdrive is only
  `VBEND − |Vtp|` = 0.119 V at dV = 1.5. dV = 1.65 is the committed qal/sha256
  census swing and is the lever that separates *"the cell is slow"* from
  *"the rail is low"*.

## A7 — chain head pattern and wiring chosen by exhaustive search

`qal/skip4` found that a bank of 8 electrically identical cells has intra-class
spread 0.000 pp in every row, so a per-gate rule cannot catch a single-gate
outlier in such a deck. To avoid inheriting that defect, the chain's input
offsets and bank-1 pattern were chosen by exhaustive search over all distinct
offset triples and all 16 bank-1 output patterns, for a combination that keeps
the chain both MIXED at every depth (never all-HIGH or all-LOW, which would make
separation vacuous) and NON-ALTERNATING. The chosen wiring (A1←i, A2←i+2,
B1←i+1) rotates the bank pattern through four distinct states
0011 → 1001 → 1100 → 0110.

## Standing declared biases (from the pre-registration, restated where they bite)

* `sg13lv_compat.sp` zeroes `ad/as/pd/ps`. Junction leakage is **absent**, so
  every leakage number is a lower bound. Quantified rather than waved at: from
  the model card's own `idsatrbot = 6.3087e-08 A/m²` and
  `idsatrsti = 1.9278e-15 A/m`, with an ASSUMED contacted-diffusion geometry of
  0.34 µm (AD = 0.2516 µm², PD = 2.16 µm), the omitted reverse-bias junction
  term is ~2.0e-20 A (1.59e-20 bottom + 4.2e-21 sidewall).

  **CORRECTION.** An earlier revision of this file called that "about eleven
  orders of magnitude" below the measured subthreshold path. That was wrong — it
  divided by the wrong reference. Against the measured leakage of 0.3–0.62 pA
  (3e-13 to 6.2e-13 A) the ratio is ~5e-8, i.e. **about seven orders of
  magnitude** below. The conclusion is unchanged (the omission does not move the
  leakage verdict) but the figure was overstated by four orders and is corrected
  here. GIDL is *not* omitted (`swgidl = 1`, `cgidlo = 0.06641` nMOS /
  `0.02068` pMOS) and is inside the measurement. The junction-geometry numbers
  are ASSUMED, not read from the PDK's tech/LEF, so this is an order-of-magnitude
  bound and is labelled DERIVED-from-ASSUMED, not MEASURED.
* The same omission removes drain junction capacitance, so every node is lighter
  than reality. That **overstates** the lost charge fraction (bias cuts the
  other way) and it removes capacitance that would have helped hold a collapsing
  node.
* The committed bank drives input gates at dV (1.5 V) while the rail only
  reaches ~0.61 V. That is generous to BOTH the stripped cell and the static
  control, so the head-to-head is fair, but it is not what a chain sees — hence
  the `_vinrail` rows and the chain itself, where inputs are rail-referenced.
