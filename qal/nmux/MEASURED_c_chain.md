# (c) The degradation question — does a restoring cell repair the degraded high?

Six tank-fed banks, alternating [restoring QAL cell bank] → [pass structure] →
[next bank]. Decks `ch_*.cir`, driver `chain.py`, results `chain_rows_w060.json`.
**TANK-FED only**, per pre-registration P5 — the campaign record says peer-fed
fails for everything, so testing there would measure the rail, not the cell.

**Geometry is REDUCED** (AMENDMENT A7): 6 banks kept, 4 bits per bank instead of
8, 0.2 ps max step instead of 0.0884183 ps, and the rail deliberately **not**
compensated for the removed cells — so the rail runs *higher* than the committed
1.326 V, which makes the nMOS-only case **harder**. Numbers here are therefore
**not** comparable digit-for-digit with the committed `ch_res20` chain; every
comparison below is against the **`wire` control run in the same reduced
geometry**.

**ZCS check**: seeded with the committed `res20` zeros and re-probed; every bank
in every variant converged to within **0.04 ps** of the seed, so the committed
open times are valid for this geometry.

## Separation by depth (mV), against the 6.44 mV σ floor

| variant | d1 | d2 | d3 | d4 | d5 | d6 | depth above floor, correct sign |
|---|---|---|---|---|---|---|---|
| `wire` + **std** (control) | 1502.7 | 1225.7 | 1049.4 | 883.9 | 730.9 | 639.6 | **6** |
| **`nmos` + std** | 1278.2 | 980.8 | 786.2 | 610.1 | 394.9 | 399.2 | **6** |
| `tg` + std | 1048.9 | 857.0 | 772.8 | 634.1 | 401.6 | 389.0 | **6** |
| `wire` + **skew** (control) | 1182.4 | 901.4 | 699.1 | 511.6 | 331.6 | 49.4 | **6** |
| **`nmos` + skew** | 571.9 | 410.4 | 266.5 | 110.3 | 29.2 | **3.2** | **5** |

Margin over the 6.44 mV floor for the headline row (`nmos` + std):
**198× / 152× / 122× / 95× / 61× / 62×**.

Rail delivered at each depth (V) — the reservoir droops, as in the committed run:

| variant | d1 | d2 | d3 | d4 | d5 | d6 |
|---|---|---|---|---|---|---|
| `wire` + std | 1.5033 | 1.2260 | 1.0495 | 0.8841 | 0.7349 | 0.6473 |
| `nmos` + std | 1.2837 | 0.9893 | 0.8079 | 0.6920 | 0.6304 | 0.6488 |
| `tg` + std | 1.0733 | 0.8852 | 0.8049 | 0.7056 | 0.6373 | 0.6485 |

Pass-structure output (HIGH / LOW, V) feeding each bank, `nmos` + std:
`0.9196/−0.0006`, `0.8760/−0.0001`, `0.7951/−0.0006`, `0.6587/−0.0006`,
`0.5351/+0.0259`.

## ANSWER: yes — the restoring cell repairs it, and the chain survives to depth 6

**`nmos` + std keeps the correct sign and stays 61–198× above the σ floor at every
one of the six depths.** The degraded high is repaired at every hop: bank 2's
input is 0.9196 V (clamped, against a 1.2837 V rail) and bank 2's own output
comes back up to 0.9799 V — the cell settles to *its* rail, which is what a
restoring cell is for.

Two further results worth stating plainly:

**1. The nMOS-only pass BEATS the transmission gate in the chain.** `nmos` + std
delivers more separation than `tg` + std at every depth from 1 to 4 (1278 vs
1049, 981 vs 857, 786 vs 773, 610 vs 634 — the last is the only reversal, 4 %).
The reason is visible in the rail row: the TG's four devices per bit load the
resonant bank harder, so the **rail itself** comes out lower (1.073 vs 1.284 V at
depth 1). The TG's better pass fidelity is more than paid for by the extra
capacitance it hangs on the tank. That is a QAL-specific inversion of the usual
CMOS trade and it only shows up in a resonant-rail harness.

**2. The clamp stops binding as the chain gets deeper.** The rail droops past the
0.883 V ceiling by depth 4 (0.692 V), so from there on the nMOS-only pass is in
the peer-fed-like regime where it loses almost nothing. The nMOS-only penalty is
therefore **front-loaded**: worst at depth 1 where the rail is highest.

## MY PRE-REGISTERED E9 IS REFUTED — and backwards

E9 predicted the chain would **survive with the SKEWED restoring cell** (0.15p /
1.48n) and **fail by depth 2–3 with the STANDARD cell** (1.12p / 0.74n), on the
reasoning that the clamped ~0.80 V high would sit too close to the standard
cell's trip point at a 1.3 V rail.

**Measured: exactly the opposite.** `nmos` + std survives all six depths;
`nmos` + skew collapses to 3.2 mV — *below* the floor — by depth 6.

The reason I got it backwards is a role confusion I should have caught from the
campaign's own record. The skewed 0.15p/1.48n cell was designed in the boundary
study as a **receiver**: it reads a QAL level into a static 1.2 V domain, where
its job is to *resolve a low trip point fast* and its pull-up strength is
irrelevant. Inside a QAL chain the same cell is a **restoring driver**: its job
is to pull its output **up to the resonant rail**, and that is done by the pMOS —
which skewing has made **7.5× smaller**. The `wire` + skew control proves the
damage is the cell, not the pass structure: with a plain wire it reaches only
1.1819 V from a 1.5298 V rail, and by depth 6 only 0.2643 V from 0.7552 V.

The committed `qal/chain3` record said this in advance — *"Limiting device =
pull-UP at every stage and every L"* — and I inverted it. **The skewed receiver
is the right fix at the QAL→sync boundary and the wrong cell inside the QAL
chain.**

## What this does not show

The reduced geometry (A7) means these separations cannot be compared with the
committed `ch_res20` numbers, only with the `wire` control here. The chain was
run at one pass width (0.60 µm) and one select source (the 1.5 V control rail);
an operand-gated (XOR) chain was **not** run, and `DERIVED_gate_drive.md` plus
the part (d) measurement say it would collapse — the committed `qal_a2`
source-follower study already measured that failure directly.
