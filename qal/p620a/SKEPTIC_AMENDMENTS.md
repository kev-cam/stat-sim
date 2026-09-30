# Skeptic pass — independent re-verification and THREE AMENDMENTS
Run 2026-09-30 00:19–00:33 PDT on P620a, independent driver, OWN fresh caches
(wiped+recreated vae/shell caches; freshness proven by 517 s cold-JIT wall,
5 vae .so built into the fresh cache, in-log PyMS registration, and exactly
the 20 expected ignored-param lines). Raw outputs: skeptic/ (this dir);
P620a transient copies in /home/claude/skeptic-v2/. Certification UPHELD;
the amendments below are folded into OFFSET_TABLE.md and
p620a_xyce_offset.json in the same commit as this file.

## Re-verification results (all MEASURED)
- G1 tg15p: fresh mt0 BYTE-IDENTICAL to the committed LOCAL-XYCE record
  (md5 4d9f72f108e711ebc077aa3d694c4970), 129/129; vae cache-key hash set
  identical to the certification run (content-deterministic codegen
  re-confirmed).
- G2 banktank: row re-derivation with the committed extract.py — ALL 62 keys
  EXACTLY equal the committed row (worst_gate_pct 90.54454610810019, rails
  0.7544238/0.6767239/0.7312457/0.7200878, sep 612.378631, PASS=True).
  mt0: 432/440 digit-identical, 8 one-ulp movers → AMENDMENT 1.
- G1b headline: gates3 record re-diffed vs committed — VBEND 0.713816259,
  VBPK 0.836889358, IPK_uA bit-equal; t_hop rel 3.5e-13. PASS. (Record nit:
  "rest differ at 1e-12..1e-16" overlooked IZ_uA at 6.8e-6 rel — a 1e-15 A
  wiggle on a near-zero steep-crossing sample; no gate consequence.)
- Port audit: all 44 main-circuit elements 1:1 vs sw_tg15p_z.cir (nodes,
  bulk ties, PWLs verbatim, widths/lengths, CA/LT/RT/CL, input pattern);
  model cards re-parsed independently — 351 surviving params numerically
  verbatim, dropped set exactly {level} + the 10 Xyce-ignored params; row-14
  forced-ic set verified = Xyce's own OP from the committed prn; OSDI
  recompile from the committed recipe md5-IDENTICAL to certification
  artifacts (b7aca876/f64c2097/21313aa2/630418ef).
- Offset table: all 9 rows reproduced exactly on fresh runs of BOTH engines;
  VACASK bit-deterministic run-to-run (0 quantities differ at >1e-12 rel).
- Metering closed form re-run both engines: Xyce offline +3.4e-6, .measure
  INTEGRAL +3.4e-6 (the standing 11–44% under-report again did NOT appear on
  this form), VACASK offline −1.96e-5 — all PASS. ER_CAPINT single-FIND read
  9.999991e-06 = exactly the predicted OP-offset artifact (I_op·R_leak),
  independently confirming the delta-idiom mechanics note.

## AMENDMENT 1 — the banktank "movers" are NOT a host offset
The skeptic re-run produced a DIFFERENT set of 8 one-ulp movers vs the
committed mt0 (EB2_Z EB4_Z ER1_Z ER2_Z ER4_Z QG4_Z VR3Z VR4Z) — and also
8 movers vs the certification's OWN v3 P620a mt0, with QG3_Z swapping in.
So the recorded 4 "offsets" are RUN-TO-RUN JITTER at the noise floor:
all movers are t=0.5 ps Z-baseline samples (native magnitudes 3.2e-9 V down
to 7.6e-39), printed-digit rel 1.3–3.9e-7 = last printed digit.
p620a_xyce_offset.json is RE-LABELED accordingly: a noise-floor
reproducibility band (~±4e-7 printed-rel) on Z-baseline samples, not a
per-quantity host offset. The >1e-4 STOP rule is untripped;
gate_comparison.json's mechanical banktank PASS:false is this same benign
class. The physical record (62/62 row keys exact) is untouched.

## AMENDMENT 2 — the VAEND offset row is VOID as recorded
The OFFSET_TABLE VAEND row mixed Xyce's lagged FIND-AT sample with VACASK's
interp-at-AT. LIKE-FOR-LIKE (offline meter both sides, confirmed on fresh
runs): VAEND = +0.897%, OUTSIDE the pre-stated 0.5% band. Per the
pre-stated violation rule: ringing-instant instantaneous samples (the
VAEND/IZ class) are NOT cross-engine interchangeable and stay Xyce-only.
The other 8 rows use settled/max/integral definitions that are lag-immune
(proven: mt0 vs offline agree at printed digits for VBEND/VBPK/IPK/EOUTA)
and stand as recorded.

## AMENDMENT 3 — Xyce mt0 FIND-AT returns a LAGGED sample (measured)
Proven digit-exactly twice on the anchor deck (mt0 VAEND −0.09025661 = prn
value at t=810.8977p vs AT=811.755p; mt0 IZ −3.793985e-7 = prn value at
t=315.780p vs AT=316.755p) and reproduced on the RC deck (mt0 V_TAU
0.3680665 = +0.051% early-read vs offline 0.3678775 / analytic 0.3678794).
The prn provably contains every accepted step incl. breakpoint micro-steps,
so the earlier IZ footnote blaming "solver grid vs print grid" was a WRONG
attribution — the grids are the same; the cause is the FIND-AT lag
(~0.86–0.98 ps early on this deck). Harmless intra-Xyce (deterministic,
digit-identical across hosts), but FORBIDS any cross-method or cross-engine
comparison of FIND-AT samples on moving signals without offline re-metering.

## Standing consequences (fold into practice)
- P620A-XYCE results may be mixed with committed LOCAL-XYCE anchors for all
  physical/headline quantities (byte-identical gate re-proven).
- P620A-VACASK: 8 of 9 offset rows certified (worst VBPK +0.449%); energies
  quotable via the validated offline_meter path only. VAEND/IZ-class
  instantaneous ringing samples: Xyce-only.
- Per-device DELVTO MC: Xyce-only. XOR-bank-scale trajectories: ENGINE label
  (pre-charge caveat, not re-audited by the skeptic).
- Anchor decks (sw_tg15p_z.cir, banktank .cir) are UNTRACKED local working
  files — every future P620a run must ship md5-verified copies
  (b8a83484 / 5e575356, extract.py e90def79, zeros df84b860,
  tg15p.sim 3b1804c9).
- P620a never pushes; this record is committed from the local box.
