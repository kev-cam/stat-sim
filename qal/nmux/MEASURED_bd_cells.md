# (b)(d) The cells, the pass level, timing, energy, count and area

Decks `m_*.cir` / `w_*.cir`, built by `nm.py`, driven by `run_cells.py`,
extracted by `reextract.py` (AMENDMENT A10) into `cells_*_fixed.json`.

**Instrument gate G2 PASSES**: the committed peer deck
`qal/resv/h_I2_load691_L4.cir`, re-run **verbatim** in this study's own PyMS
cache, reproduces the committed record to
`VBEND −2.0e−6 %`, `VBPK 0.0 %`, `VA_open −0.0013 %`, `t_hop −4.7e−6 %`.

**Step sensitivity (AMENDMENT A5's obligation)**: the same configuration at the
committed 0.0177663 ps max step and at the relaxed 0.05 ps step gives
`pass_HIGH` differing by **0.74 µV** and `E_in` by 1.0e−6 fJ. The relaxation is
irrelevant at the scale of every effect reported here.

## The cells, and why there are only two of them

A pass-transistor **XOR2 is the same netlist as a pass-transistor MUX2**
(`Y = A ? Bbar : B`). Building a separate "nMOS XOR cell" would have simulated the
identical circuit twice. What actually distinguishes them is **who drives the
gates** — control (1.5 V rail) for a MUX select, an operand (QAL rail level) for
XOR. That is the `gate_src` axis below. See `DERIVED_gate_drive.md`.

* **nMOS-only**: 2 nMOS, sources on the two data legs, drains commoned on the
  output, gates on the complementary selects.
* **TG control**: the same, plus a pMOS in parallel with each nMOS, gates
  swapped, bodies to a 1.5 V n-well. **Like-for-like = equal nMOS width**, so the
  TG is literally "the nMOS-only cell plus a pMOS".

**Sizing (w = 0.60 µm primary), justified by the measured width sweep below:**
0.15 µm delivers only 0.642 V at the tank rail and takes 317 ps to 90 %; 1.20 µm
delivers 0.964 V in 233 ps but draws 10.07 fC and injects 71 mV. 0.60 µm sits at
the knee — 0.895 V in 261 ps, 8.15 fC, 40 mV injection — and is the width carried
through the chain study.

## Pass level, both polarities, both rails  — THE HEADLINE

| config | rail (V) | src HIGH (V) | **pass HIGH (V)** | shortfall | pass LOW (V) |
|---|---|---|---|---|---|
| **nMOS-only MUX2, peer-fed** | 0.6782 | 0.6743 | **0.6726** | **1.7 mV** | −0.00001 |
| TG MUX2, peer-fed | 0.6596 | 0.6419 | 0.6364 | 5.5 mV | −0.00004 |
| **nMOS-only MUX2, tank-fed** | 1.2996 | 1.2989 | **0.8951** | **403.8 mV** | −0.00001 |
| TG MUX2, tank-fed | 1.1851 | 1.1850 | **1.1850** | **0.0 mV** | −0.00000 |
| nMOS-only XOR2 (operand gate), peer-fed | 0.7096 | 0.7066 | **0.1689** | 537.7 mV | −0.00005 |
| nMOS-only XOR2 (operand gate), tank-fed | 1.3029 | 1.3022 | **0.7252** | 576.9 mV | −0.00002 |
| TG XOR2 (operand gate), peer-fed | 0.6944 | 0.6796 | 0.4745 | 205.1 mV | +0.0273 |
| TG XOR2 (operand gate), tank-fed | 1.2024 | 1.2024 | 1.2024 | 0.0 mV | −0.00000 |

**The answer to the user's suggestion, in one line: at the peer-fed rail the
nMOS-only MUX2 loses 1.7 mV — it is, to measurement precision, as good as the
transmission gate and beats it (the TG loses 5.5 mV, because its extra devices
tax the driving cell harder). At the tank-fed rail it loses 404 mV and the TG
loses nothing.**

Cross-checks on the clamp, from two independent routes:
* part (a)'s self-consistent ceiling `V* = VGH − Vtn(V*)` = **0.8832 V**;
* the transient measurement = **0.8951 V** (12 mV apart);
* the `locus.py` current-integration prediction for a 2 fF load = 0.862 V at
  100 ps, 0.916 V at 300 ps — the transient lands inside that window.

And for the operand-gated (XOR) case: derived 0.7237 V at the tank rail, measured
**0.7252 V** — **1.5 mV apart**. Derived 0.2060 V at the peer rail, measured
**0.1689 V**.

**Pass LOW is undegraded everywhere** — worst case −0.05 mV. E6 **CONFIRMED**.
The asymmetry is the entire story, exactly as expected.

## Timing

| config | t50 after close | t90 after close | rail t90 |
|---|---|---|---|
| nMOS-only, peer | 72.6 ps | 256.8 ps | — |
| TG, peer | 81.5 ps | 320.9 ps | — |
| nMOS-only, tank | 118.7 ps | 260.8 ps | — |
| TG, tank | 159.2 ps | 267.5 ps | — |
| nMOS-only tank, w=0.15 | 120.5 ps | 317.5 ps | |
| nMOS-only tank, w=0.30 | 120.9 ps | 306.3 ps | |
| nMOS-only tank, w=1.20 | 121.1 ps | 233.1 ps | |

The nMOS-only cell is **faster to 90 % than the TG at both rails** (256.8 vs
320.9 ps peer; 260.8 vs 267.5 ps tank) — it has half the capacitance to move.
Note the t90 is dominated by the rail's own settling, not by the pass device;
`t50` separates them and shows the same ordering.

## Energy — three meters, separated by construction

All 1 F integrators, t0-referenced. Units: a 1 F integrator holds `V = Q`, so the
node is coulombs/joules; the 1e15 scale is applied (AMENDMENT A10a).

| config | E_in HIGH (fJ) | Q_in (fC) | → onto load | **E_SUPPLY (fJ)** | Q_SUPPLY (fC) |
|---|---|---|---|---|---|
| nMOS-only, peer | 2.081 | 5.71 | 1.35 (24 %) | **0.000** | **0.000** |
| TG, peer | 3.024 | 8.26 | 1.27 (15 %) | −5.12 | −3.414 |
| nMOS-only, tank | 5.303 | 8.15 | 1.79 (22 %) | **0.000** | **0.000** |
| TG, tank | 11.933 | 16.24 | 2.37 (15 %) | −10.7 | −7.123 |

**E8 CONFIRMED, and rigorously**: for the nMOS-only cell the supply meter reads
`+0.000000 fC` at **every sampled time point**, not merely a small number — the
integrator never moves, because no path exists. Resolution against the
integrator pedestal is ~0.002 fJ, so the claim is "below 0.002 fJ", i.e. < 0.03 %
of the committed 8.408 fJ hop.

**The TG's n-well is NOT free.** Its meter moves −7.12 fC / −10.7 fJ per
operation at the tank rail. The trace *saturates* (−0.12 fC at 230 ps, −5.79 at
400 ps, −7.12 at 700 ps, flat thereafter), so this is **displacement charge the
well bias must supply**, not leakage. And this is a **lower bound**: the
`sg13lv_compat.sp` shim zeroes `ad/as/pd/ps`, so the pMOS junction capacitance —
which is entirely a TG cost — is absent from the model.

Input energy: the nMOS-only cell draws **2.25× less** from the driving cell at the
tank rail (5.30 vs 11.93 fJ) and **1.45×** less at the peer rail, tracking its
half device count. Only 15–24 % of the drawn charge reaches the load in either
form; the rest charges the pass devices' own capacitance.

**Gate drive — reported honestly, because the naive number is misleading.**
The select transition itself costs almost nothing (measured at the edge:
+0.006 fJ for the nMOS-only cell, +0.045 fJ for the TG) because the channels are
not yet formed. The large numbers in the table (`E_gate_hop_only` = −1.52 fJ
nMOS-only, −2.18 fJ TG) are the **data edge coupling charge back out of the gate
into the select source**, and they are negative because the select is an *ideal*
voltage source that absorbs it. A real select driver would dissipate that
instead. It is reported as a separate line rather than folded into a
"per-operation energy", and it is **larger for the TG** (−3.03 vs −1.60 fC).

## Charge injection from the select edge — and a real QAL-specific finding

| w (µm) | injection peak | residue when the data arrives |
|---|---|---|
| 0.15 | 9.5 mV | 9.47 mV |
| 0.30 | 20.1 mV | 20.12 mV |
| 0.60 | 39.9 mV | 39.95 mV |
| 1.20 | 70.8 mV | 70.84 mV |
| TG 0.60 | 50.7 mV | 50.66 mV |

Injection is **linear in width**, as expected. But the peak and the residue are
**identical** — the kick does not decay. The waveform shows why, and it is a
property of QAL rather than of pass transistors:

```
 t(ps)   V(sel)   V(o1)     V(yh)     V(rail)
 168.0   0.0000   0.00000   0.00000    0.0000
 170.0   1.5000   0.06588   0.00445   -0.0002      <- select edge
 175.0   1.5000   0.04689   0.03033   -0.0011
 195.0   1.5000   0.04001   0.03992   -0.0009      <- equalised, and STAYS
```

The injected channel charge splits between the mux output and the **driving
cell's output**, and neither has anywhere to put it: that cell is a pull-UP (its
nMOS is off), so its only path is through its pMOS to **the rail — which before
the hop is a floating LC node, not a supply**. The charge therefore sits there
until the rail arrives. On the pass-LOW side the residue is **−0.00001 V**,
because that cell is a pull-DOWN with its nMOS on and a real ground beneath it.

So: **injection persists on pull-up-driven nodes and is sunk on
pull-down-driven nodes.** At 10–71 mV against a 1.3 V rail it does not corrupt
the level here, but it is the same mechanism that pumped the bank in the
committed nMOS-only transfer switch (see `MEASURED_g_mechanism.md`), and it is
the one cost that genuinely carries over.

## Count and area

Full treatment in `MEASURED_d_area.md`. Summary: **2 devices vs 4**, and
**2.46×–8.20× less area** depending on width (3.55× at the chosen 0.60 µm), with
the entire difference coming from the n-well terms — NW.d 0.31 + NW.c 0.31 +
NW.c 0.31 = 0.93 µm of y-extent the nMOS-only cell does not need, plus 0.60 µm
more if the well needs its own tie.

## Verdict against the pre-registered expectations

| | prediction | measured | |
|---|---|---|---|
| E4 | peer-fed margin OPEN, ≥ 0.72 V, headroom ~+50 mV | 0.6726 V, shortfall **1.7 mV**, headroom +128 mV | **CONFIRMED**, better than predicted |
| E5 | tank-fed CLOSED, clamp ~0.80 V, crossover ~0.80 V | clamp **0.895 V**, crossover **0.883 V** | **CONFIRMED** in direction, crossover 83 mV higher |
| E6 | pass LOW undegraded ≤ 5 mV | ≤ 0.05 mV | **CONFIRMED** |
| E7 | TG reaches the rail within 10 mV both rails | tank 0.0 mV; **peer 5.5 mV — and worse than the nMOS-only cell** | **CONFIRMED** numerically, but the ordering at the peer rail was not anticipated |
| E8 | no static supply path; meter reads zero | reads `0.000000 fC` at every sample | **CONFIRMED** |
| E11 | area ratio 2.5–3.5× | 2.46–8.20× (3.55× at 0.60 µm) | **CONFIRMED** at usable widths, **under-predicted** at minimum width |
