# VERDICT — "n-chan only muxes might work too"

**Yes, for muxes, at the peer-fed rail — and no, above ~0.88 V.**
The crossover is measured, not argued: **0.8832 V**.

| | peer-fed rail (0.68 V) | tank-fed rail (1.30 V) |
|---|---|---|
| nMOS-only MUX2 pass HIGH | **0.6726 V** (loses **1.7 mV**) | **0.8951 V** (loses **404 mV**) |
| TG MUX2 pass HIGH | 0.6364 V (loses 5.5 mV) | 1.1850 V (loses 0.0 mV) |
| pass LOW, both forms | ≤ 0.05 mV | ≤ 0.01 mV |

At the peer-fed rail the nMOS-only mux is **as good as the transmission gate and
slightly better** (its two fewer devices tax the driving cell less), while costing
half the devices, 3.55× less area, 1.45× less input energy, and **zero** n-well.

## The deciding number, and it is body effect, as the brief said

MEASURED on the PSP103 device, `Vds = 0.1 V`, bulk at 0, source lifted:

* `Vtn(0) = 0.523987 V` — reproduces the committed 0.5239460 V to **+0.041 mV** (gate G1)
* `Vtn(1.3) = 0.651763 V` — total shift over the full range only **+127.8 mV**
* **γ = 0.23038 V^0.5, 2φ_F = 0.800 V**, fitting the classical law to **0.013 mV RMS**

Body effect is **2.2× weaker** than my pre-registered textbook prior — which is
why the margin at the peer rail is 128 mV rather than the ~50 mV I predicted.
It does **not** eat the margin at the peer-fed rail. It does close it at the
tank-fed rail, because the ceiling `V* = 1.5 − Vtn(V*) = 0.8832 V` is **fixed by
the 1.5 V gate rail** and does not rise with the signal.

Confirmed three independent ways: self-consistent ceiling **0.8832 V**, current-locus
integration **0.862–0.916 V** over a 100–300 ps window, transient **0.8951 V**.

## The distinction the brief warned about — and it does NOT carry over

The committed nMOS-only **transfer switch** failed at every width (VA_open
0.336–0.641 V against a ~0.098 V target). Its failure has three mechanisms:
uncancelled gate-charge injection (**shared**, and measured here at 9.5–70.8 mV,
linear in width), top-of-swing conductance collapse (**shared** — it *is* the pass
ceiling), and failure to drain the sending rail while interrupting a resonant
inductor current bidirectionally (**not shared** — a logic mux is unidirectional
into 2 fF, never drains its source, and interrupts no inductor). Two of three
are properties of the resonator, not of nMOS pass transistors.

## What would have been easy to get wrong

* **XOR is not MUX.** A pass XOR2 is the same netlist, but one *operand* must
  drive the gates, so the gate rail collapses to the signal rail. Measured pass
  HIGH: **0.1689 V** peer-fed, **0.7252 V** tank-fed (derived 0.2060 / 0.7237 —
  within 1.5 mV at the tank rail). This is the campaign's own `qal_a2`
  source-follower clamp arriving by a second route.
* **The skewed receiver is the wrong cell inside the chain.** I predicted the
  opposite. `nmos` + standard 1.12p/0.74n survives all 6 depths at 61–198× the
  σ floor; `nmos` + skewed 0.15p/1.48n collapses to 3.2 mV by depth 6, because
  skewing for a low trip point cripples the **pull-up** that has to drive the rail.
* **The degraded high causes LESS contention, not more** — 0.119 µA / 0.50 % of
  the hop, against 8.786 µA / 36.74 % for the undegraded QAL high, because
  raising the input to 0.883 V puts the receiver pMOS *below* threshold. A skewed
  receiver removes it entirely (0.000 µA), and is needed only at a ≥1.33 V receiver rail.
* **In the chain the nMOS-only pass BEATS the TG** at depths 1–4, because the TG's
  four devices per bit load the resonant tank harder and the rail itself comes out
  lower (1.073 vs 1.284 V at depth 1).

## Where this is a lower bound

`sg13lv_compat.sp` zeroes `ad/as/pd/ps`, so junction capacitance is absent. The
TG has **twice** the junction area being omitted, so the shim flatters the **TG**
more than the nMOS-only cell — every comparison above is conservative in the
direction of the conclusion.
