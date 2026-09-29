# load691 protocol amendments

Order on disk is the proof (`ls -la --time-style=+%H:%M:%S`): `PRE_REGISTERED_LOAD.json`
21:41:04, `s3.py` next, then the gate deck, then the first three measured points, then
this file, then the L-extension points.

## L1 — the pre-stated CONDITIONAL did not fire; the extension goes the OTHER way

Pre-registration said: *"if L=22 is still improving on MAX or on t_valid90, add L=30 W=30
and (if needed) L=45 W=30. No other points."*

MEASURED, it is not improving: at 6.91 fF, dV=1.65, W=30 um the end-to-end level time is
121.148 ps (L=10), 127.005 (L=15), 134.790 (L=22) — monotone **worse** with larger L. So the
pre-stated conditional is dead, and the pre-stated grid has its minimum at its own smallest
L, which is exactly the situation the dvopt pre-registration called a boundary optimum.

**Amended, and this is POST-HOC:** extend DOWNWARD in L instead — L = 8 and L = 6 nH at
W = 30 um, and the pre-stated L = 6 nH at W = 80 um. Two measured facts justify it and both
are on the record above:

1. prediction **P5 CONFIRMED** — the heavier cell load draws more charge out of the source
   bank, so bank A drains *more* completely: VA_open (ZCS instant) is 0.0516 V at L=10 and
   0.0269 V at L=15 against 0.0615 / 0.0382 V at the same points with a 2 fF load. The drain
   constraint that bounded the 2 fF grid at small L is **looser** under load, so small L at a
   narrow switch may now be admissible where it was not at 2 fF.
2. the post-arrival settle interval is **flat in L** under load — 84.196 / 84.087 / 84.326 ps
   at L = 10 / 15 / 22 — so the objective is carried entirely by t_hop, which falls as
   sqrt(L). There is no interior balance point to bracket from above.

**P4 is REFUTED by these three rows.** I predicted the optimum would move to LARGER L under
load (t_settle grows, t_hop does not, so the balance moves up). Measured, t_settle stops
depending on the delivered swing once the load dominates, so the balance disappears and the
optimum runs to the drain boundary at SMALL L. Recorded as a miss.

## L2 — C2 is reported under BOTH checkpoint conventions, computed here

The sk path evaluates `VA_open` at the **ZCS instant**; the lsw path that produced the dvopt
grid evaluates the same-named quantity at **t_open + 7 ps** (`lsw.py` line 188, checkpoint C).
They are 2.2x-6.9x apart and the gate binds the whole grid, so every row here carries both:
the harness's ZCS value and `V(bka)` read off this row's own `.prn` at `t_open + 7 ps` by
`post.py`. No verdict here rests on one convention alone.

## L3 — what this excursion does NOT do

No new dV, no chain, no o21ai at load, no energy gate. The energy EXCLUSION verdict
(23.213 fJ/bank/hop vs a pre-stated <= 12.7467 fJ, stat-sim c814e52) is untouched: these hops
are still ideal-source driven.
