# SKEPTIC amendments — deviations from PRE_REGISTERED_SKEPT2.json, and how my own predictions fared

Pre-registration: `PRE_REGISTERED_SKEPT2.json`, written 20:16:59 with sha256 of all 22
consumed inputs frozen. First deck of this track ran 20:33. Nothing below was written
before the pre-registration; nothing in the pre-registration was edited after.

## A1 — grid additions made ADAPTIVELY, disclosed
The pre-registration committed to "both optima re-run, >=1 L-neighbour each side, >=1
W-neighbour each side, and intermediate widths at L=10 (W=24) and L=6 (W=80, W=90)".
Those were all run. In addition I ran, chosen from earlier rows in this same session and
therefore NOT blind: L=9/12 at W=30; W=20/36 at L=10; W=36/60 at L=9; W=40 at L=8;
W=45 at L=7; W=150/240 at L=5; W=150/240 at L=4; and dV=1.50 controls at L=5/W=120 and
L=4/W=240. Every one of them is reported whether or not it helped the case, and the four
that CHANGED a verdict (L=9/W=36, L=6/W=80, L=5/W=150, L=5/W=120@dV1.50) are named in
the findings.

## A2 — NOT done
dV = 1.08 / 1.32 / 1.35 were not re-run. The task was the two claimed optima plus
neighbours; dV=1.50 is the dV-neighbour of both and was re-run. So my monotone-in-dV
statement covers 1.20 / 1.50 / 1.65 only and I say so.

## A3 — my own predictions, scored
| # | prediction (written before any deck) | outcome |
|---|---|---|
| P1 | GA/GB/GD pass, GC agrees within tolerance | **HIT** — GA bit-identical (rel 0.00e+00 on 10 quantities), GD bit-identical, GC <= 4.6e-04 on every timing |
| P2 | d165_L10_W30 reproduces; L=12/W=30 lands 58-60 ps so L=10 stays best at W=30 | **HIT** — L=12 MAX 59.39 |
| P3 | L=9/W=30 fails C2 narrowly, VA_open ~0.150 | **HIT** — 0.15215, misses by 2.9% |
| P4 | W=24 at L=10 fails C2, VA_open ~0.171 | **HIT in direction, MISS in magnitude** — 0.15941, not 0.171 |
| P5 | W=80 at L=6 PASSES, SUM ~101-102 ps, i.e. the claimed SUM optimum is a width-ladder artefact | **HIT, and exactly** — VA_open 0.14468 PASS, SUM 101.56 ps |
| P6 | the two SUM terms overlap; model SUM ~26% above the measured level time | **HIT in direction, MISS in magnitude** — over-states by 34-37%, not 26% |
| P7 | 2-high stack confirms on correctness; much of the o21ai "settling" is the rail falling onto the output | **HIT** — from the rail peak to the meeting point, 38% is rail-down / 62% output-up; the output's own asymptote is 70% of the delivered peak |

## A4 — findings that were NOT pre-registered (found during the work)
1. **The C2 gate quantity is checkpoint-sensitive.** `VA_open` in `lsw.py` is
   `dV - Q_L(checkpoint C)/CA` and checkpoint C is `t_open + min(7, 3.5*edge)` = **7 ps
   after the switch starts opening**. The campaign's own independent harness
   (`skept/sk.py`) computes the identically-named `VA_open` **at the ZCS instant**. They
   differ by 2.2x at the MAX optimum and 6.8x at the SUM optimum. Found first by a
   read-only inspection of committed `.prn` files, then confirmed by re-run (my GA row
   reports derived 0.1276800 vs printed-at-open 0.0919931, delta +35.69 mV).
2. **The interior/monotone verdict on both surfaces reverses with the t_settle surrogate.**
   Not something I thought to predict. See the findings.

## A5 — standing limitations, unchanged and repeated
`sg13lv_compat.sp` zeroes ad/as/pd/ps, so junction capacitance is absent and every time
and energy here is a **LOWER bound** on a real layout. `LT` is ideal with a lumped
RS=10 ohm. No interconnect, no bank-to-bank routing, no inductor self-capacitance. This
is ONE hop with a real bank. Own cache throughout (`vae_cache_sk2b`, seeded by copying
`vae_cache_dvopt`); never more than 4 concurrent Xyce jobs of mine.
