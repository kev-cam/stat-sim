# On-host engine offset table: P620A-XYCE vs P620A-VACASK (tg15p anchor)

Same host (P620a WSL2), same circuit (tg15p anchor; port per
vacask_port/CORRESPONDENCE.md), same model source (PSP 103.4.0 CMC), same
card (kestrel tt, verbatim minus the 10 params Xyce itself ignores). The
offset is therefore PURE ENGINE DIFFERENCE (PyMS-GiNaC/Xyce-GEAR vs
openvaf-OSDI/VACASK-gear), plus the documented solver-tolerance residue.

P620A-XYCE = the certified binary (gate G1 DIGIT-IDENTICAL to the committed
LOCAL-XYCE record, so these rows are simultaneously offsets to the committed
anchors). Xyce values from the in-engine mt0 (solver-grid measures); VACASK
values from tg15ptr.raw metered offline (offline_meter.py, validated below).
VACASK run: final port deck (gear, reltol=1e-5, op-forced 4-node island).

| Quantity (class) | P620A-XYCE | P620A-VACASK | rel offset | pre-stated band | verdict |
|---|---|---|---|---|---|
| VBEND (V) | 0.6758936 | 0.6760236 | +0.019% | 0.5% | PASS |
| VBPK (V, ringing peak) | 0.7374377 | 0.7407486 | +0.449% | 0.5% | PASS (worst row) |
| VAEND (V) | -0.09025661 | -0.09037411 | +0.130% | 0.5% | PASS |
| O1E = delivered cell rail (V) | 0.6758936 | 0.6760236 | +0.019% | 0.5% | PASS |
| t_zcs (ps, this deck's own I(LT) zero, offline both sides) | 265.598 | 265.674 | +0.028% | 1% | PASS |
| IPK (A) | 1.943655e-4 | 1.943464e-4 | -0.010% | (timing/current class, 1%) | PASS |
| EOUTA (J) | 1.785814e-14 | 1.785569e-14 | -0.014% | 2% | PASS |
| EINB (J) | 2.149297e-14 | 2.151458e-14 | +0.101% | 2% | PASS |
| QTR (C) | 3.905386e-14 | 3.908256e-14 | +0.073% | 2% | PASS |
| IZ (A, near-zero crossing sample) | -3.793985e-7 (mt0) / -2.412e-6 (offline prn) | -2.255e-6 | n/a | none pre-stated | reported only: zero-crossing sample, denominator ~0; method-dependent (mt0 uses solver grid, offline uses print grid); NOT a certified quantity |

Notes, all MEASURED:
- t_zcs here is the z-deck's own interpolated I(LT) downward zero (265.6 ps),
  NOT the committed probe-deck zero 266.755 ps that set the deck's open time;
  both engines are compared like-for-like on the same definition.
- Convergence: VACASK reltol 1e-3 -> 1e-4 -> 1e-5 moves VBEND 0.6760851 ->
  0.6760823 -> 0.6760236 (<2e-4 V); the offsets above are not
  tolerance-limited at the quoted digits.
- FIRST PORT ATTEMPT (uic) was silently wrong by +20% on VBEND because the
  bank rail floated at t=0; the pre-stated bands caught it. See
  vacask_port/CORRESPONDENCE.md row 14. Never quote the uic-run numbers.

## Metering validation (pre-stated closed form, both engines, same host)
RC discharge C=1pF V0=1V R=1kOhm tau=1ns, E_R(10ns) analytic 4.99999999e-13 J:
- P620A-VACASK raw + offline trapezoid: 4.999902e-13 J -> rel err -1.96e-5 (0.002%) PASS (band 0.5%)
- P620A-XYCE offline trapezoid on the .prn: 5.000017e-13 J -> +3.4e-6 PASS.
- P620A-XYCE `.measure INTEGRAL`: 5.000017e-13 J -> +3.4e-6. The standing
  "under-reports 11-44%" failure did NOT reproduce on this closed form
  (P620a build 1c36edca); it is evidently deck/window-shaped, and the
  campaign's cap-integrator/delta idiom stays the recording convention.
- Cap-integrator idiom, IMPORTANT mechanics re-verified: the idiom is
  DELTA-BASED (X_at_instant minus X_at_Z-baseline). Its 1F node carries an
  OP offset = I_integrand(op) * R_leak (committed decks: ~9e-13 V, leak
  negligible over 817 ps; the deltas are exact -- committed EA_D - EA_Z =
  1.78e-14 = EOUTA). A single-FIND read WITHOUT the Z-baseline is wrong on
  any deck whose integrand is nonzero at the OP (this RC case: t=0 current
  1 mA -> offset 1e-5 V and the leak of that offset swamps the pJ integral).
- Offline meter cross-checked against the Xyce in-engine mt0 on the tg15p
  anchor itself: EOUTA offline 1.7858143e-14 vs mt0 1.785814e-14;
  VBPK/VBEND/IPK identical at printed digits.
=> VACASK energies are QUOTABLE via the offline path (pre-stated criterion met).

## Standing rules
- Committed anchors remain LOCAL-XYCE quantities; P620A-XYCE is digit-
  identical (gate G1/G2); P620A-VACASK carries THIS table's offsets.
- Nothing crosses engines without these offsets attached.
- Per-device DELVTO MC stays Xyce-only (no PyMS callback path in VACASK).
