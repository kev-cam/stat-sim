# (d) Transistor count and area, with the n-well saving broken out

Rule values are **MEASURED** from the IHP-Open-PDK SG13G2 KLayout DRC source
(`libs.tech/klayout/tech/drc/{feol,sg13g2_maximal}.drc`), quoted by rule name.
The composition into a cell bounding box is **DERIVED**. Script `area.py`,
output `area.json`.

| rule | value (um) |
|---|---|
| Act.a min Activ width | 0.15 |
| Act.b min Activ space/notch | 0.21 |
| Act.c min Activ drain/source extension | 0.23 |
| Gat.a min GatPoly width (1.2 V) | 0.13 |
| Gat.c min GatPoly endcap over Activ | 0.18 |
| Cnt.a Cont width | 0.16 |
| Cnt.c Activ enclosure of Cont | 0.07 |
| Cnt.f Cont on Activ space to GatPoly | 0.11 |
| **NW.a min NWell width** | **0.62** |
| **NW.c NWell enclosure of P+Activ** | **0.31** |
| **NW.d NWell space to external N+Activ** | **0.31** |
| NW.e NWell enclosure of NWell tie | 0.24 |

## Device count

| cell | nMOS | pMOS | total | n-well |
|---|---|---|---|---|
| nMOS-only MUX2 / XOR2 | 2 | 0 | **2** | **none** |
| transmission-gate MUX2 / XOR2 | 2 | 2 | **4** | required |

Exactly **2×**, as pre-registered (E11).

## Area

x-extent is identical for both forms — one 2-input pass strip:
`0.34 (outer S/D) + 0.13 (gate) + 0.38 (shared node) + 0.13 + 0.34 = 1.32 um`.
**Because x is identical it cancels in the ratio**; the whole result is a
y-direction result, and y is where the n-well lives.

y-extent:
* nMOS-only: `W_n`
* TG: `W_n + NW.d(0.31) + NW.c(0.31) + W_p + NW.c(0.31) = W_n + W_p + 0.93`
* TG with its own well tie: `+ Act.b(0.21) + Act.a(0.15) + NW.e(0.24) = + 0.60`

| W_n = W_p | nMOS-only (um²) | TG (um²) | ratio | TG + own tie | ratio |
|---|---|---|---|---|---|
| 0.15 | 0.198 | 1.624 | **8.20×** | 2.416 | 12.20× |
| 0.30 | 0.396 | 2.020 | **5.10×** | 2.812 | 7.10× |
| 0.60 | 0.792 | 2.812 | **3.55×** | 3.604 | 4.55× |
| 1.20 | 1.584 | 4.396 | **2.77×** | 5.188 | 3.27× |
| 2.00 | 2.640 | 6.508 | **2.46×** | 7.300 | 2.77× |

E11 predicted 2.5–3.5×; **CONFIRMED at the widths a QAL mux would actually use
(0.6–2.0 um), and badly under-predicted at minimum width**, where the fixed
0.93 um of well overhead dwarfs the devices and the ratio reaches 8×.

## Honesty about the model

* The repeating poly pitch this model implies is `0.13 + 0.38 = 0.51 um`, against
  the real SG13G2 standard-cell width quantum of **0.48 um** — the model is
  **6.25 % pessimistic in x**. It does not reproduce the foundry's staggered /
  shared-contact packing. Irrelevant to the ratio (x cancels), relevant if anyone
  quotes the absolute um².
* **Cross-check against a real cell (MEASURED):** `sg13g2_inv_1` is the
  campaign's own 1.12p/0.74n inverter and occupies 5.4432 um² = 1.44 × 3.78 um.
  Its devices sum to 1.86 um of width in a 3.78 um row, so **51 % of a real
  standard-cell row is overhead** — power rails, n-well, well tie, substrate tie,
  endcaps. My TG model charges only 0.93–1.53 um of that, so the **absolute** TG
  areas above are optimistic; a row-based TG would be worse, not better.
* **The structural point the table understates:** a pass structure has no supply
  connection at all (confirmed by the E8 meter — see `MEASURED_bd_cells.md`), so
  an nMOS-only pass array needs **no VDD rail, no n-well, and no well tie** — only
  a substrate tie, which is shared across the whole array. The TG needs the well
  and its tie biased to VHI. In a row-based layout that is the difference between
  needing half a row and needing a full one.

## What the comparison does NOT say

`sg13g2_mux2_1` is **18.1440 um²** and `sg13g2_xor2_1` is **14.5152 um²**
(MEASURED, same PDK). It is tempting to quote 0.792 vs 18.144 um² as a 23×
saving. That would be wrong: those standard cells are **restoring and buffered** —
they drive a rail — and a pass structure is not. The saving is only real when a
restoring stage is present anyway, which in QAL it is (the next bank's cell). The
defensible statement is the **like-for-like** one: against a transmission gate
doing the identical job in the identical harness, the nMOS-only form is **half
the devices and 2.5–3.6× less area** at usable widths.
