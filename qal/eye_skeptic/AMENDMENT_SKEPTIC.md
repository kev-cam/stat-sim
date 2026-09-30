# SKEPTIC AMENDMENTS

Each carries the forcing measurement and the mtime proving it preceded the rows
it affects.

## SA1 — MY OWN PRE-REGISTERED F1 WOULD HAVE MANUFACTURED THE VERY BIAS I AM AUDITING

**Forcing measurement** (log_row_P2.txt, mtime 2026-09-29 23:05, before any eye of
mine was extracted): on the SHARED calibrated schedule at T=200, H=4, dV=1.65 V,

| pattern | A6 worst \|I(L)\| at a commanded open | bt.py's 1 µA gate |
|---|---|---|
| P3 (the calibration pattern) | 0.0121 µA | PASS |
| P2 (all-one, the claimed binding pattern) | **123.68 µA** | FAIL, 124× |

My pre-registered **F1** said: *"If my probe fails bt.py's A6 gate I QUARANTINE the
row and re-probe with the FULL 8-run protocol; I never relax the gate."*

Applied literally to a **calibrated row**, F1 would have thrown out P2 — the
binding pattern — and left me intersecting over patterns that happen to sit near
the calibration vector. That is precisely the best-case-envelope error I was sent
to police. **F1 was written for a PROBE and I am overriding it for a ROW**, with
the reason stated:

A6 asks whether the transfer/return switch opens at the *true* current zero. On a
**data-blind** schedule it cannot, by construction, for any vector other than the
calibration vector — that is what "one calibrated timer instead of a per-pattern
oracle" *means*. So A6 on a calibrated row is not a validity gate on the
transient; it is a restatement of the schedule's definition. The audited study
reached the same conclusion and pre-declared it ("A6 is a PROBE-VALIDITY gate and
this is an ENERGY cost, reported never gated"), and my 123.68 µA sits inside their
stated calibrated band of 26.3–128.4 µA, so I **reproduce** their finding rather
than contradicting it.

**Decision:** every calibrated row enters the intersection, A6 pass or fail, with
its A6 current carried in SKEPTIC_EYE.json `_A6`. My probe-stage F1 stands
unchanged (and the probe did pass, at 0.0121 µA on the calibration vector).

**But one thing the audited study does not say, and should:** the off-zero current
that fails A6 is the *same* current they identify as the mechanism of their own
headline correction — *"an off-zero switch leaves current still driving the rail,
so the pull-up resolves sooner"*, worth −2.5 to −3.4 ps. So the A6 failure is not
*only* an energy cost. It is also the physical cause of the calibrated eye opening
earlier than the oracle eye. They declined to bank that credit (their A9), which
is the right call; the residual point is that "energy cost, reported never gated"
understates the coupling — the same off-zero current that costs energy is buying
the timing result that the beat is computed from.

## SA2 — THE ROW SET IS 3 PATTERNS, NOT 9, AND I SAY WHAT THAT COSTS

I ran P0, P1, P2, P3 (weights 5, 0, 8, 4) on one calibrated schedule, not all
nine Hamming weights. Justification, and its limit: the audited study MEASURED
that the reduced set {P1, P2, P3} reproduces the all-nine-weight intersection to
**0.0000 ps at every bank** at T=200 (their pre-registered F4 check), and
separately that the eye depends only on the Hamming weight and not the
arrangement (their P4 control: ZCS instants agreeing to 3e-9 ps, all 76 rail
`.measure` keys identical to 0.000 V). I am **relying on** that reduction, not
re-verifying it — re-running six more rows was not affordable at ≤3 concurrent
heavy jobs on a box at load 9–12 with 11 foreign Xyce.

Consequence, stated rather than hidden: my intersection is over the weight
extremes plus two interior vectors. Adding vectors to an intersection can only
narrow an eye, never widen it, so **my openings are upper bounds on the
true-intersection opening** — i.e. if anything my eye is slightly optimistic, in
the same direction as theirs, and by at most the 0.0000 ps they measured.

## SA3 — I AUDIT A CLOSING EDGE AT A CONTOUR NOBODY HAS TAKEN A WIDTH AT

Not in my pre-registration. Added after reading BUDGET.json's own contour
definition (`p2eye.py` line 25) and noticing that every published width is taken
at **0 mV** or at **3σ_trip = 19.323 mV**, while the *budget* charges
**3σ_total = 69.923 mV**. A width quoted at 0 mV alongside a beat charged at
69.923 mV is two different eyes. I therefore compute the closing edge and width
at all four contours, including the budget's own. Added BEFORE any row of mine
was extracted (skeye.py mtime precedes the first `skeye.py` run).
