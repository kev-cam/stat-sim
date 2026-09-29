# (a) Vtn(V_sb) — MEASURED on the PSP103 device

Deck family `vtb_*.cir`; extraction `vtb.py` (+ AMENDMENT A4 re-extraction);
fit `fit_body.py` -> `body_fit.json`. Device: `sg13_lv_nmos w=0.74u l=0.13u`
(the campaign's canonical nMOS), `Vds = 0.1 V`, bulk at 0, source lifted to V_sb.

**Instrument gate G1 PASSES**: Vtn(V_sb=0) = **0.5239874 V** against the
committed 0.5239460 V = **+0.041 mV**. (Independently, `qal/vtreq` got +41 uV on
the same check with a 1 mV grid — same number.)

## MEASURED

| V_sb (V) | Vtn @100nA·W/L | @10nA·W/L | @1nA·W/L | ΔVtn vs V_sb=0 |
|---|---|---|---|---|
| 0.00 | 0.523987 | 0.435715 | 0.353484 | +0.0 mV |
| 0.05 | 0.530318 | 0.442279 | 0.360364 | +6.3 mV |
| 0.10 | 0.536471 | 0.448642 | 0.367017 | +12.5 mV |
| 0.20 | 0.548292 | 0.460834 | 0.379709 | +24.3 mV |
| 0.30 | 0.559542 | 0.472395 | 0.391701 | +35.6 mV |
| 0.40 | 0.570294 | 0.483416 | 0.403095 | +46.3 mV |
| 0.50 | 0.580607 | 0.493966 | 0.413967 | +56.6 mV |
| 0.60 | 0.590529 | 0.504092 | 0.424379 | +66.5 mV |
| 0.70 | 0.600102 | 0.513844 | 0.434387 | +76.1 mV |
| **0.75** | **0.604767** | 0.518590 | 0.439254 | +80.8 mV |
| 0.80 | 0.609356 | 0.523259 | 0.444036 | +85.4 mV |
| 0.90 | 0.618324 | 0.532369 | 0.453353 | +94.3 mV |
| 1.00 | 0.627030 | 0.541203 | 0.462376 | +103.0 mV |
| 1.10 | 0.635490 | 0.549782 | 0.471130 | +111.5 mV |
| 1.20 | 0.643730 | 0.558127 | 0.479632 | +119.7 mV |
| **1.26** | **0.648573** | 0.563030 | 0.484623 | +124.6 mV |
| 1.30 | 0.651763 | 0.566254 | 0.487909 | +127.8 mV |

## Body-effect coefficient (DERIVED by least squares on the MEASURED points)

`Vt(V_sb) = Vt0 + gamma * ( sqrt(2*phi_F + V_sb) - sqrt(2*phi_F) )`

| criterion | gamma (V^0.5) | 2*phi_F (V) | Vt0 (V) | RMS residual |
|---|---|---|---|---|
| 100 nA·W/L (campaign) | **0.23038** | 0.800 | 0.523987 | **0.0127 mV** |
| 10 nA·W/L | 0.22936 | 0.735 | 0.435715 | 0.0142 mV |
| 1 nA·W/L | 0.22983 | 0.670 | 0.353484 | 0.0173 mV |

`gamma` is the same to 0.5 % at all three criteria; only the intercept moves.
The classical square-root law describes PSP103 here to **13 microvolts RMS** over
the full 0–1.3 V range, so the body effect needs no empirical correction.

**This refutes my pre-registered E2 in magnitude**: I assumed
`gamma in [0.35, 0.65]` and predicted Vtn(0.75) ≈ 0.69 V and Vtn(1.3) ≈ 0.78 V.
Measured: **0.605 V** and **0.652 V**. The real device's body effect is about
**2.2× weaker** than the textbook prior — total ΔVtn over 1.3 V of body bias is
only **128 mV**, not the ~260 mV I assumed. E2's *shape* prediction ("sub-sqrt,
flatter than textbook at high V_sb") was right in direction but for the wrong
reason: the curve is an excellent sqrt, it just has a small coefficient.

## The number that decides the study — the self-consistent pass ceiling

An nMOS passing a HIGH has its source at the OUTPUT, so it stalls where
`V* = VGH - Vtn(V*)`, with Vtn read AT that source level. Solved by bisection on
the MEASURED curve at VGH = 1.5 V:

| criterion | pass ceiling V* | margin at peer-fed 0.755 V | margin at tank-fed 1.26 V | at 1.326 V |
|---|---|---|---|---|
| 100 nA·W/L | **0.8832 V** | **+128.2 mV** | **−376.8 mV** | −442.8 mV |
| 10 nA·W/L | 0.9621 V | +207.1 mV | −297.9 mV | −363.9 mV |
| 1 nA·W/L | 1.0346 V | +279.6 mV | −225.4 mV | −291.4 mV |

Read this as a *rate*, not a wall: the 100 nA row is where conduction is still
fast, the 1 nA row where it has effectively stopped. A real pass node creeps
between the two depending on how long the valid window is — so the transient
measurement, not this table, is the arbiter of the delivered level. What the
table settles is the **sign** of the answer, and it is the same at every
criterion: **open at the peer-fed rail, closed at the tank-fed rail.**

E3 predicted V* ≈ 0.80 V; measured 0.883 V — pessimistic by 83 mV.
E4 (peer-fed open, ~+50 mV) — CONFIRMED, and the margin is 2.6× larger than
predicted at +128 mV.
E5 (tank-fed closed, crossover ~0.80 V) — CONFIRMED in direction; the measured
crossover rail is **0.883 V**, not 0.80 V.
