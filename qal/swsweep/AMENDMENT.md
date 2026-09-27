# Protocol amendment 1 (recorded 2026-09-27, after tg30/tg15 as-committed rows, before any ZCS run)

## What was pre-registered
Primary rows on the "as-committed" timing convention: switch opens at (probe zero + 50 ps),
because the committed t_zcs=342.0 row does exactly that (true zero measured 291.34 ps after
close; IZ = -100 uA at open — the quirk gateb RESULTS.json recorded), and the completeness
band [0.56479, 0.58785] was anchored to the committed V_B_end = 0.5763 produced by that
convention.

## What the data showed (MEASURED, as-committed rows)
- tg30: V_A_end = 0.328, Q through L = 24.2 fC, switch "hold" phase re-injects 8.2 fC.
- tg15: V_A_end = 0.590. The tg15 PROBE (switch closed) shows the transfer itself is fine:
  V_A = 0.085 at the zero. In the HOP, after the +50 ps-late open interrupts ~-98 uA, bank A
  RECOVERS from ~0.12 to 0.59: the interrupted inductor current forces the off switch to
  clamp-conduct and the LC keeps sloshing, un-transferring the rail.
- tg60 (baseline): same convention is benign — its own ~55 fF of switch capacitance parks
  the interrupted-current ring (V_B 0.611 -> 0.576, V_A 0.10 -> 0.048).

## The inference
The +50 ps-late-open convention is not a transferable protocol: it embeds the 60 um switch's
parasitics as a hidden protective element. Off-baseline it measures the artifact, not the
switch. The pre-registered completeness band was mis-anchored for the same reason.

## Amended protocol (before any ZCS run was made)
1. Primary rows: TRUE ZCS — open the switch exactly at the design's own probe zero
   (probe-then-hop per design, as the brief demands). Suffix `_zcs` in sweep_rows.json.
2. tg60 gets a true-ZCS row too; the committed-convention tg60 row is kept as the anchor that
   reproduced the committed record (instrument gate G2).
3. Completeness is re-anchored to the true-ZCS baseline: V_B_end within 2% of tg60_zcs's
   V_B_end, AND V_A_end must show the rail actually drained (V_A_end <= tg60_zcs V_A_end
   + 0.05 V). Both raw values reported for every design; the original pre-registered band is
   also evaluated and reported for the as-committed rows so nothing is silently dropped.
4. The as-committed rows are retained and reported as the late-open sensitivity study
   (negative result, first-class).
