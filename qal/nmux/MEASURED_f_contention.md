# (f) The static-power trap — contention into a following static CMOS cell

DC sweeps `rx_*.cir`, driver `cont.py`, results `cont.json`. Energy is over the
campaign's 293 ps hold, quoted against the committed 8.408 fJ hop.

**Free instrument check (not pre-registered, found and recorded):** the standard
1.12p/0.74n receiver at 1.2 V with a 0.6759 V input measures **8.786 µA /
3.089 fJ / 36.74 % of the hop**, against the committed boundary study's
**8.780 µA / 3.0896 fJ / 36.75 %** — agreement to **0.06 %**.

## Standard receiver, 1.12 µm p / 0.74 µm n

| receiver VDD | trip (V) | input 0.6759 V (committed QAL high) | input **0.8832 V** (nMOS pass) | 0.9621 V | 1.0346 V |
|---|---|---|---|---|---|
| 0.90 | 0.4936 | 0.006 µA / 0.002 fJ / 0.02 % | 0.000 / 0.000 / 0.00 % | 0.000 | 0.000 |
| 1.20 | 0.6428 | **8.786 µA / 3.089 fJ / 36.74 %** | **0.119 µA / 0.042 fJ / 0.50 %** | 0.012 / 0.004 | 0.001 |
| 1.26 | 0.6709 | 13.602 µA / 5.022 fJ / 59.72 % | 0.678 µA / 0.250 fJ / 2.98 % | 0.073 / 0.027 | 0.009 |
| 1.33 | 0.7027 | 17.675 µA / 6.888 fJ / 81.92 % **(reads as 0!)** | 3.323 µA / 1.295 fJ / 15.40 % | 0.576 / 0.225 | 0.073 |

## Skewed receiver, 0.15 µm p / 1.48 µm n (the boundary study's fix)

| receiver VDD | trip (V) | input 0.6759 V | input **0.8832 V** | 0.9621 V | 1.0346 V |
|---|---|---|---|---|---|
| 0.90 | 0.3405 | 0.000 µA / 0.000 fJ | 0.000 / 0.000 | 0.000 | 0.000 |
| 1.20 | 0.4665 | 0.034 µA / 0.012 fJ / 0.14 % | **0.000 / 0.000 / 0.00 %** | 0.000 | 0.000 |
| 1.26 | 0.4854 | 0.191 µA / 0.071 fJ / 0.84 % | 0.000 / 0.000 | 0.000 | 0.000 |
| 1.33 | 0.5053 | 0.841 µA / 0.328 fJ / 3.90 % | 0.004 µA / 0.001 fJ / 0.02 % | 0.000 | 0.000 |

## ANSWER

**A degraded nMOS-pass high causes LESS contention than the undegraded QAL high,
not more — by a factor of 74× at the 1.2 V receiver rail.** 8.786 µA becomes
0.119 µA; 36.74 % of the hop becomes 0.50 %.

**My pre-registered E10 predicted exactly this counter-intuitive direction and
the mechanism, and is CONFIRMED** (predicted < 1 µA and < 5 % of the hop;
measured 0.119 µA and 0.50 %). Contention needs the receiver pMOS to be on, i.e.
`VDD − V_in > |Vtp| = 0.4403 V`. The committed case had `1.2 − 0.6759 = 0.524 V`,
comfortably above threshold. An nMOS pass *raises* the input to 0.883 V, giving
`1.2 − 0.883 = 0.317 V` — **below** threshold, so only subthreshold current flows.
The nMOS-only pass structure's degradation is in the direction that *helps* the
receiver.

**Where it stops helping**, measured: as the receiver rail rises, `VDD − 0.8832`
climbs back toward `|Vtp|`. At VDD = 1.26 V the margin is 0.377 V (still below
threshold, 0.678 µA / 2.98 %); at VDD = 1.33 V it is 0.447 V — just **above**
|Vtp| — and contention returns at 3.323 µA / 1.295 fJ / **15.40 %** of the hop.
So a QAL receiving cell sitting on the full tank rail does pay a real contention
cost, though still **5.3× less** than the committed boundary case.

**Does a skewed receiver remove it? Yes, completely.** The 0.15p/1.48n cell draws
**0.000 µA at 1.2 and 1.26 V and 0.004 µA at 1.33 V** from a 0.8832 V input — its
pMOS is 7.5× smaller and its trip point is 0.4665 V at 1.2 V, so the level is
read correctly with no crowbar path. Contention as a percentage of the hop is
**0.02 % at worst**.

## A separate hazard the same sweep exposes

At a **1.33 V** receiver rail the standard cell's trip point rises to **0.7027 V**,
which is **above** the committed QAL high of 0.6759 V. On that row the receiver
reads a QAL logic 1 as a **0** while burning 17.675 µA. This is the boundary
study's MARGIN failure re-appearing at a higher receiver rail, and it is *not*
caused by the pass structure — it is caused by feeding a static cell from a rail
higher than the one that produced the datum. The nMOS-pass level of 0.8832 V is
comfortably above that trip and reads correctly, so on this specific axis the
pass structure **improves** margin as well as contention.

## Practical consequence

For nMOS-only pass logic the receiver choice is rail-dependent, and both halves
are measured:
* receiver at ≤ 1.26 V: the **standard** 1.12p/0.74n cell is fine (≤ 2.98 % of
  the hop) — no skewing needed;
* receiver at the full tank rail (~1.33 V): skew it, or pay 15.4 %.

And note the tension with part (c): the skewed cell is the right **receiver** at
the boundary and the **wrong restoring cell** inside the chain, where its weak
pull-up collapses the separation. These are different roles for the same
geometry and the campaign has now measured both.
