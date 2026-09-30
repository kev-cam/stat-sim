# qal/cipher — PHASE 1: the interconnect model, and whether QAL recovers wire charge

The insight under test: *"wiring does the rotate"* — a rotate costs zero gates and
zero levels but its wires carry capacitance, and that is supposed to be the one
capacitance QAL charges through the inductor and takes back, while CMOS dumps
½CV² into it every cycle.

**Verdict: half true, and the half that is true is not the half a cipher needs.**
QAL recovers wire charge only where the wire sits **on the resonant node**. A
rotate permutation is by construction on **signal nodes**, behind each driving
cell's own pull-up device, which is outside the LC loop. Measured on the
committed 4-bank chain with the same 32-bit-rotate capacitance:

| where the wire sits | net cost per cycle, as a multiple of its own stored energy | vs CMOS |
|---|---|---|
| **rail** (resonant node) | 0.400 – 0.994 | **2.01× – 5.00× better** |
| **signal nodes** (a real rotate) | 1.256 – 2.074 | 1.00× – 1.59× better |
| signal nodes at the PDK's own XOR2 bit pitch | 2.670 | **0.749× — a loss** |

CMOS is 2.000 by construction (½CV² in, ½CV² out) and the CMOS decks reproduce
that to 0.4–0.6 %.

## Order of work (mtimes are the witness)

| file | mtime | what |
|---|---|---|
| `DISK_STATE_BEFORE.txt` | 19:32:50 | sha256 + mtime of every committed input, before anything |
| `wire.py`, `WIRE_MODEL.json` | 19:34:28 | **(b)** the PDK extraction — pure arithmetic, **no simulation** |
| `btk/` byte-identity check | 19:36 | regenerated both committed netlists and byte-compared them — **no simulation** |
| `PRE_REGISTERED.json` | 19:40:00 | **(a)** acceptance, the wire figure, and my pre-stated expectations |
| `PRE_REGISTERED.sha256` | 19:40:04 | `81c1d78f0f71d5a92ee5cc3a6c007c53ecc52a1b35057ce2a3b5af06a5672166` |
| first Xyce deck | 19:40+ | — |

## (b) The wire figure, from the PDK

Min-width **Metal2**, read out of `sg13g2_tech.lef`
(`CPERSQDIST 1.81e-05 pF/um²`, `EDGECAPACITANCE 4.47e-05 pF/um` per edge):

* **0.0930 fF/µm** isolated over the plane below — **MEASURED-FROM-PDK**
* **0.2181 fF/µm** in the middle of a min-pitch bus — **DERIVED** (shielded
  ground from the OpenRCX table's own fringe entry + 2 × Sakurai coupling)
* the campaign's **0.15 fF/µm lies inside that band**, so it is no longer
  ASSUMED — it is **PDK-bracketed**, and both ends are run as rows

The OpenRCX `nom` min-spacing **coupling** entry (0.4599 fF/µm/side) is **4.5×
the Sakurai value and 5.9× a hard parallel-plate bound**. It is reported and
**flagged, not used** — and declining to use it is the conservative choice,
because it would make QAL's wire case look better.

Rotate length is **DERIVED**: `mean = 2r(W−r)/W` bit pitches. ChaCha20's
r = 16/12/8/7 give 16.0/15.0/12.0/10.94 pitches. At the brief's own geometry
(32-bit, r = 16, 1 µm bit pitch) that is 16 µm per bit → **2.400 fF/bit**, and
32 bits × 16 µm × 0.15 fF/µm = **76.8 fF** against the brief's "~75 fF".
Reproduced.

## (c) Instrument check — gate G1 PASS

Both committed banktank decks regenerated **byte-identically**, re-run here under
this run's own `PYMS_VAE_CACHE`, and digit-checked: **422/440 and 435/440 `.mt0`
quantities bit-identical**, worst relative deviation 5.79e-07. Every derived
metric — `PASS`, `worst_gate_pct`, separation, stage time, and every per-bank
energy — reproduces at relative difference **0.00e+00**.

## (d)/(e) What was measured, and the mechanism

* The **rise** hop time barely moves when signal wire is added (124.57 → 124.92 ps,
  +0.28 %) but the **return** grows a lot (bank 2: 155.74 → 176.06 ps, +13 %).
  The ZCS instant is set by the capacitance *inside* the loop; the inductor never
  sees a signal wire. Rail wire shifts the rise immediately (+4.2 %). **That pair
  of numbers is the whole mechanism.**
* Adding signal wire makes the bank's **existing** recycling worse — per-bank
  25.41/17.12/19.11/18.81 % → 19.62/9.42/13.73/11.87 %, an **incremental return of
  −54 %**. Adding rail wire **improves** it: → 28.32/22.26/22.37/23.94 %, +50 %.
* `|Vtp|` **never binds.** The output-node end voltages equal the rail end
  voltages to four decimals (0.7587/0.7871/0.8000/0.8000 both). The wire's
  recovery is capped by the **rail's** own recovery, not by a threshold — which
  refutes the mechanism I pre-registered.
* The loop quality factor `(2/π)√(L/C_eff)/R = 43.11×` is **the wrong model** for
  this topology: the measured series-R loss is 0.82–1.06 fJ per hop against ~43 fJ
  dissipated inside the bank. I quoted 43× in my own pre-registration and it was
  never reachable.
* **Two mechanism probes confirm the cause and give the lever**: a 2.07× slower
  ramp (L 15 → 60 nH) takes the signal-wire ratio 1.79× → **2.78×**, and a 4×
  wider pull-up (wp 1.12 → 4.48 µm) takes it to **2.56×**. Both cost exactly what
  the brief expected — speed, or area and baseline energy (+33 %).
* The **lumped-C booking is validated, not declared**: the same 2.400 fF as a
  3-segment π ladder carrying the PDK's own 8.24 Ω differs by **0.004 fJ = 0.01 %**.

Under the `qal/fcrit` functional criterion (reused from disk, trip tag `S`,
3σ = 19.323 mV) **8 of 9 rows still compute 32/32**. The only failure is
Cw = 9.216 fF — the PDK's XOR2 bit pitch — at 27/32, failing *inside* the noise
budget (+3.263 mV against 19.323 mV).

## Predictions: 2 right, 3 partly, 3 wrong

`RESULTS.json : H_MY_PRE_STATED_EXPECTATIONS_SCORED`. The two biggest misses:
I named the wrong device for the stranding limit (P1), and I predicted the
incremental recycle at 5–20 % when it is **negative** (P2).

## Files

`wire.py` · `PRE_REGISTERED.json` · `INSTRUMENT_CHECK.json` · `score.py` /
`SCORE.json` · `analyse.py` / `ANALYSIS.json` · `AMENDMENT.md` (A1–A5) ·
`RESULTS.json` · `btk/bt.py` (verbatim committed generator) · `btk/btw.py` (the
one extension, with a byte-identity selftest at Cw = 0) · `btk/micro8.py` (the
single-hop QAL-vs-CMOS harness) · `btk/iterate.py` (the A2 return-zero fixed
point) · `btk/superseded_1cell/` (A3, kept not deleted) · `btk/it0/`
(pre-iteration decks, kept so A2's insensitivity can be re-checked).

Nothing in any committed `qal/` directory was written to. `qal/widebank/` was not
touched.
