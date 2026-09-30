# PHASE 2 — THE QAL SHA-256 BLOCK, BUILT AND MEASURED

161 cells, 14 banks, all of them, in every deck. **Nothing here is a slice.**

Pre-registration `PRE_REGISTERED.json`, sha256 `a580f3d2…`, 2026-09-29 12:35:45 −0700.
Defects, corrections and misses: `AMENDMENT.md`. Machine-readable: `COMPARISON.json`.

---

## (a) INSTRUMENT CHECK — PASS, DIGIT-EXACT

The committed `qal/banktank` row `m=10, T=200 ps, H=4, dV=1.2, free`, re-run here on
this track's own cache with the committed zeros file: **24 of 24 floats reproduce at
relative error exactly 0.0**, `value_fail_list` empty, **32 of 32 gates** value-checked.

| | mine | committed |
|---|---|---|
| worst_gate_pct | 90.54454610810019 | 90.54454610810019 |
| worst_gate_where | [3, 'o3'] | [3, 'o3'] |
| separation_min_mV | 612.378631 | 612.378631 |
| per_bank_worst_pct | 94.71062551313996 / 91.15563969293828 / 90.54454610810019 / 92.65559005443504 | identical |
| IPK_uA | 937.4588 / 840.0786 / 814.6336 / 826.186 | identical |

---

## (b) THE BLOCK — and the thing eight identical inverters could never show

`syn/sw_nand_sc_resyn2.v`: 161 cells (46 `inv_1`, 115 `nand2_1`), DEPTH 14, profile
41/32/26/21/6/5/3/7/4/7/3/4/1/1. The flow reproduces the committed Phase-1 profile
exactly. The netlist's own Maj/Ch/CPA functions check out independently in Python for
the pre-registered vector `a=5A b=A6 c=3C e=69 f=96 g=C3` → maj=0x3E, ch=0x82,
sum=0x00 with a full 8-bit carry propagation.

**THE HOLD IS NOT A FREE PARAMETER.** In every prior deck a bank fed only the next
bank. A real DAG has cross-level edges: the maximum **signal lifetime** here is **11**
(a cell in bank 3 is read by bank 14), so

```
H_k = {1:11, 2:4, 3:12, 4:11, 5:5, 6:9, 7:2, 8:7, 9:2, 10:5, 11:2, 12:3, 13:2, 14:1}
II  = max_k H_k = 12 beats — forced by the netlist, not chosen.
```

Retiming to `II = 2·T` needs 296 relay cells for the cell-to-cell edges plus 34 for
the primary inputs: **161 → 491 cells, 3.05×**.

**Per-bank matched tanks.** `C_bank(k)` MEASURED per bank (quasi-static charge secant,
`stage_cap`), spanning **42.2:1** — 255.5 fF (bank 1, 41 cells) to 6.05 fF (bank 14).
`C_tank(k) = 10·C_bank(k)`, total **10.94 pF**.

**Inductor.** The committed 15 nH was sized for a 36 fF bank. Swept on the widest bank:
L = 2/3/4/5/8/15/30 nH → t_level = 268.0/255.1/**252.3**/253.7/266.6/307.5/391.9 ps.
**L = 4 nH is a real measured minimum** and is used uniformly.

---

## (c) MEASURED

### THE RESULT THAT DECIDES THE RUN: the rail must clear Vtn + |Vtp|

| | dV = 1.20 V (the banktank-anchored point) | dV = 1.65 V |
|---|---|---|
| rail PEAK, 14 banks | 0.740 – 0.875 V | 1.032 – 1.212 V |
| banks clearing Vtn+\|Vtp\| = **0.9642 V** | **0 of 14** | **14 of 14** |
| gates wrong at their own boundary | **54 of 161** | **0 of 161** |
| worst gate | 34.34 % | **95.04 %** |
| min separation | 167.7 mV | **803.7 mV** |

At dV = 1.20 the block **does not compute per-beat at any beat period**: 59/54 of 161
gates fail at T = 260/300 ps, and a per-gate settle scan out to 2000 ps shows **six
banks (2, 6, 8, 10, 12, 14) never reach the guard at any offset** — bank 8's worst cell
sits flat at 45 % from 100 ps to 2000 ps. It is a stalled DC state, not slow settling.
The block's final answer is still correct, because it eventually settles as a slow
combinational network. **That is not pipelining.**

**The mechanism, measured.** The failures are overwhelmingly expected-LOW outputs
failing to pull down: **88 % of NAND2 pull-downs and 42 % of inverter pull-downs**,
against 11 % / 20 % for pull-ups. On a QAL rail a pull-down's gate drive is the
**previous bank's delivered rail**, not a full supply — 0.63–0.81 V against
Vtn = 0.5239 V, i.e. 0.11–0.29 V of overdrive, split across two series devices in a
NAND2. Below Vtn + |Vtp| a static CMOS stage has no gain at mid-rail and the cascade
is **not level-restoring**: the levels compress with depth (separation 423 → 168 mV
from bank 1 to bank 4), and a trace of the worst cell walks the degradation back one
bank at a time to bank 1, which is clean only because its inputs are ideal full-dV
sources.

**This overturns Phase 1's own selection criterion.** Phase 1 chose `{inv, nand2}` by
`binding_pmos_rise_depth` — the p-side — arguing explicitly that "it is the p-side
depth that binds, not the n-side," and measured it with ideal full-dV inputs so the
n-side never bound. `nand2_1` is depth-1 on the p-side and **depth-2 on the n-side**.
The shallow-stack remap did not remove the 2-high stack; **it moved it to the side that
binds in a cascade.**

### Beat period and initiation interval, at the working swing dV = 1.65 V

| beat T | A1 (≥90 % settle) | A2 (value, 161 gates) | worst gate | latency | II | E_tank |
|---|---|---|---|---|---|---|
| 200 ps | ✗ 77.94 % | ✗ 2/161 (bank 8) | 77.94 % | 2798 ps | 2400 ps | 1248.1 fJ |
| **250 ps** ×2 rows | ✗ 89.44 / 89.46 % | **✓ 0/161** | 89.44 % | 3498 ps | 3000 ps | 1248.6 / 1248.3 fJ |
| **300 ps** ×3 rows | **✓** | **✓ 0/161** | **95.04 / 95.06 / 95.07 %** | **4198 ps** | **3600 ps** | 1262.3 / 1243.8 / 1248.7 fJ |

**Earliest value-correct beat 250 ps; earliest beat that also clears the committed 90 %
settling gate 300 ps.** II = 12 × 300 = **3600 ps**, because the hold is forced.

**Reproducibility:** the T = 300 result is three independently-seeded rows — `H300`
(probe-seeded), `KH300` (with the buck present), `HF300` (seeded from the exact
full-block bank-1 zero) — agreeing to **1.5 % on energy** and **0.03 points on the worst
gate**. On `HF300` the rise zeros close to **1.07 µA** and the whole A6 residual is worth
**0.044 fJ**, 0.003 % of the per-operation energy.

A settle scan also shows a transient dip 50–100 ps *after* each bank's boundary,
coincident with the next bank's rail rise coupling back through the gate capacitance of
the cells it feeds — one gate in bank 3 and one in bank 8 drop below guard for ≲100 ps
and recover. It lands inside the consumer's own evaluation window and every consumer is
still valid at its own boundary, so it does not break the pipeline; it is reported
because a wider design would have to check it.

### Energy per operation, timing hardware INCLUDED

The one convention-free number is the tank energy: `C_tank` is a linear capacitor, so
½C(V₀²−V₁²) needs no integrator convention.

| | dV = 1.65, T = 300 |
|---|---|
| tank energy the operation TAKES (MEASURED) | **1262.3 fJ** (1243.8 fJ on the buck row) |
| buck supply energy, one 35 ps C9 pulse (MEASURED) | 771.1 fJ, replacing 25.8 % of it |
| buck efficiency η (MEASURED) | **0.4164** (0.3814 incl. its own gate drive) |
| buck output ZCS residual | 0.201 µA — **passes** |
| **wall-plug per operation (DERIVED at measured η)** | **2987.0 fJ** |

The switch gate-drive and VHI integrals are **negative** — ideal PWL drivers recover
their gate charge — so they are reported raw by sign and excluded, which makes every
total above a **LOWER BOUND**. A6 residual: all 14 **rise** zeros ≤ 0.3 µA; returns up
to 57 µA; total trapped inductor energy **0.93 fJ = 0.07 %** of the per-op energy.

### Hop-time spread across the 42.2:1 bank profile — and the brief's law is wrong

| | min | max | spread |
|---|---|---|---|
| uniform L = 4 nH (dV 1.2 / 1.65) | 29.8 / 31.8 ps | 132.8 / 145.2 ps | **4.46× / 4.57×** |
| tuned L_k ∝ 1/C_bank | 130.1 ps | 198.5 ps | 1.53× |

`t_hop` does **not** scale as √C_bank: √42.2 = 6.50× predicted, **4.46× measured** — the
quantised transfer-gate width leaves the small banks Ron-limited rather than LC-limited.
And tuning L per bank is the **wrong** move: it collapses the spread by making the small
banks slow (bank 14: 29.8 → 198.5 ps), raising the beat-setting maximum from 132.8 to
198.5 ps, **+49 %**. Coherence is not needed, because every bank is cut at its own
measured zero. **The wave is left incoherent on purpose.**

### Area of the timing hardware

10.94 pF of tank = **7290 µm² of MIM**, against the committed CMOS 56-cell logic area of
627.78 µm² → **11.6×**, plus **14 inductors**.

---

## (d) THE THREE-WAY COMPARISON — load-matched, and said so

This deck loads every cell output with **CL = 2.0 fF** (the committed banktank/skept
convention). The load-matched CMOS comparator is therefore the **2 fF** one,
57.143 ps/level → DEPTH 10 × 57.143 = **571.4 ps**. The committed 928 ps figure is the
**6.91 fF** convention. Both are given; quoting 928 ps against a 2 fF QAL deck would
flatter QAL by 1.62×.

QAL measured: **1262.3 fJ tank / 2987.0 fJ wall**, latency **4198 ps**, II **3600 ps**.

| reference | their E | their T | QAL E / theirs | QAL wall / theirs | QAL latency / theirs | QAL II / theirs |
|---|---|---|---|---|---|---|
| **CMOS 56 cells** | 232 fJ | 928 ps | **5.44× worse** | **12.88× worse** | **4.52× worse** | 3.88× worse |
| CMOS, load-matched (571.4 ps) | 232 fJ | 571.4 ps | 5.44× worse | 12.88× worse | **7.35× worse** | 6.30× worse |
| QDI direct-threshold | 2712 fJ | 2533 ps | 0.47× better | 1.10× worse | 1.66× worse | 1.42× worse |
| QDI + completion detection | 4385.7 fJ | 4021 ps | 0.29× better | 0.68× better | 1.04× ≈ equal | 0.90× better |
| DIMS | 6972 fJ | 5575 ps | 0.18× better | 0.43× better | 0.75× better | 0.65× better |
| **QAL composed PROJECTION** | 136.8 fJ | 4004 ps | **9.23× low** | **21.8× low** | 1.05× | 0.90× |

**The projection is replaced by a measurement.** It got the *time* nearly right
(4004 vs 4198 ps, 5 % low) and the *energy* wrong by **9.2× (tank) to 21.8× (wall)** —
exactly because it excluded the timing hardware, which is the cost.

**Ranking on energy:** CMOS 232 < **QAL 1262 (tank) / 2987 (wall)** < QDI 2712 <
QDI+CD 4386 < DIMS 6972. QAL beats both asynchronous styles by 2.1–5.5× and **loses to
CMOS by 5.4–12.9×**. It does not win on either axis against CMOS.

---

## PRE-REGISTERED PREDICTIONS, SCORED

| prediction | outcome |
|---|---|
| instrument check reproduces | **HIT** (exactly 0.0 rel err, 24/24) |
| earliest correct beat 240 ps, range [200, 400] | **HIT on the number** (250 ps value-correct, 300 ps for A1) — but I did **not** predict that at the pre-registered dV = 1.2 there is **no** correct beat at all |
| worst gate 88 %, range [80, 95] | **MARGINAL MISS** — 95.04 % at T=300, just above the range; 89.44 % at T=250, inside |
| all 161 pass A2 | **PARTIAL MISS** — yes at dV 1.65, no at dV 1.2; I predicted no swing dependence |
| hop spread uniform L 6.4×, range [3.0, 8.0] | number **in range** (4.46×) but my stated √(L·C) reasoning is **REFUTED** by the measurement |
| hop spread tuned L 1.15×, range [1.0, 1.6] | number **in range** (1.53×) but my reading was wrong: tuning makes the block **slower**, not better |
| energy 520 fJ, range [250, 1200] | **MISS, LOW** — 1262 fJ tank (above the range), 2987 fJ wall (2.5× the range top) |
| II = 12 beats | **HIT** (it was a static consequence, so this is not a forecast) |
| **headline: "QAL will WIN on energy and LOSE on latency and throughput"** | **HALF WRONG.** The latency/throughput half is right. It **loses on energy too**, 5.4× (tank) to 12.9× (wall). |
| **pre-registered NEGATIVE condition** | **BOTH CLAUSES FIRED.** At the pre-registered dV=1.2 the block does not compute at any beat; at the swing where it does, 1262 fJ ≫ 232 fJ. The composed 136.8 fJ projection is **refuted by measurement**. |

---

## WHAT THIS IS AND IS NOT

**IS:** the first QAL block on a real netlist measured end to end — 161 cells, 14 banks,
per-bank matched tanks, per-bank forced holds, value-checked on every gate in every
bank against an independent evaluation of the netlist, with the buck top-up metered
inside the energy number.

**IS NOT, and each is a BOUND in the stated direction:**
`sg13lv_compat.sp` zeroes ad/as/pd/ps and there is no wire capacitance or P&R, so every
time is a LOWER bound · the 48 primary inputs are ideal DC sources held all run, so the
block is charged nothing for relaying an input to a deep bank (34 relay cells, not
counted) · ideal PWL gate drivers recover their gate charge, so the energy totals are
LOWER bounds · the wall figure scales the MEASURED buck efficiency and is DERIVED, not
measured, because one pulse replaced 25.8 % of the per-op cost · one input vector · L
was optimised at dV = 1.2 and re-used at 1.65 · the A6 return residual is unclosed at
≤57 µA, worth 0.93 fJ.
