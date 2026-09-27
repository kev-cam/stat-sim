# TRACK 3 — a real zero-current detector (ZCD) for the QAL bank hop

The QAL admission test (SELECTION-RULE.md §3 G2) carried the zero-current
detector at an ASSUMED 30–300 fJ/bank/hop — no comparator had ever been
simulated. This directory designs and measures one in SG13G2/PSP103 at T0,
on the committed iso-current hop (dV=1.0, L=277.8 nH, gateb-instrumented).

**RESULT (2026-09-27, RESULTS.json): the signal defeats the class.** The
final 3-stage armed comparator attaches cleanly (Ipk 0.03%, zero −0.74 ps)
but never fires against the true held-closed zero within 878 ps at ~120 µA
armed bias (~144 fJ/cycle); its only fires lock on the switch-OPENING
transient, ~431 ps late. Measured stage lags (120/170 ps) match the GBW
ledger gm/C ≈ 2.5e10 /s: resolving 74 µV/ps to a rail edge inside ~50 ps
needs ~mA bias ≈ 580 fJ/hop. N_min ≥ 221 on the measured-energy basis and
the per-hop-ZCS assumption itself is refuted for simple continuous
comparators here. Every block in the old 50–400 UNDECIDABLE band resolves
to NOT ADMITTED.

Pre-registration (bands stated before any run): `PRE_REGISTERED.json`.

**Skeptic verification (2026-09-27, independent cache/decks):** regenerated
decks byte-identical; no-fire, energies (144.83/144.34/200.53 fJ), fire
times (779.06/773.54 ps), signal facts (true zero 340.16 ps, −74.2 µV/ps,
+8.27 ps composite crossing) and the N_min arithmetic all reproduce
(288.9 → 289.0 is rounding); the bank DP was verified by brute force over
all span≤4 partitions; the ±18 mV offset tolerance (record extrapolated
from ±2 mV at 1.10 ps/mV) was confirmed by DIRECT runs at ±18 mV
(+19.82/−19.77 ps) — and belongs to the opening-transient lock, not
true-zero detection. **Switch–ZCD coupling (skeptic, MEASURED):** the
Track-2 switch optimum tg15p steepens the sensing signal 5.1×
(−376 µV/ps, R_eff 179 Ω, cm 0.679 V; pre-edge window tz−14..−4 ps — a
±6 ps window straddles the gate edge and reads a bogus 1495 µV/ps),
relaxing the ±20 ps true-zero offset need from ±1.48 mV to ±7.5 mV
(marginal vs the 3–17 mV systematics, no longer hopeless) at −100 mV
pMOS-pair headroom. DERIVED, does not flip the verdict: ~one gain-stage
(≈120–170 ps) saved of the ≥538 ps shortfall while the tg15p beat is 8.4%
shorter — still ≥1 beat late. If tg15p's per-gate number feeds h,
N_min(144.3) ≈ 163 [DERIVED] — no admission verdict flips either way.

## Files
- `qal_zcd.py`     — deck generator + stages (wave / sa / hop / hopall)
- `restate_admission.py` — N_min = (39.6+E_ZCD)/(0.867−0.0361) + bank DP
- `zcd_wave.json`  — inp/inn replay tables extracted from gateb/gb_hop.cir.prn
- `za_*.cir`       — standalone comparator (measured-waveform replay)
- `zh_*.cir`       — full committed hop + comparator attached to mid/sw
- `RESULTS.json`   — the measured record and the restated admission

## Signal (MEASURED, gateb/gb_hop.cir.prn)
Sense across the EXISTING 10 Ω series R (nodes mid–sw): differential
= I(LT)×10 Ω, peak 1.95 mV, slope −20.7 µV/ps at the zero, common mode
0.578 V. NOTE: the transmission gate's own drop does NOT null at I=0
(+0.62 mV displacement residual) — do not sense across the TG.

## Topology
Armed-per-hop two-stage continuous-time comparator, 1.2 V logic rail:
pMOS diff pair → nMOS diode + partial cross-coupled load (clamped
regeneration); second pMOS pair → nMOS mirror → single-ended; CMOS output
inverter. pMOS tail switches arm it; an nMOS equalizer and a pMOS keeper
pin the idle state. Idle output LOW, fires HIGH.

## Cache trap (cost of iteration)
PYMS compiles ONE PSP103 `.so` per distinct device WIDTH (W is in the hash,
`.so.params` line 755). A new width = a ~2.5 min compile before the sim
starts. Iterate within the already-compiled width set
{0.5, 0.9, 1, 2, 4, 6, 8, 0.74, 1.12, 20, 40} µm or budget the compile.
The compat shim (`sg13lv_compat.sp`) SILENTLY DROPS `m=` — parallel copies
must be separate X-instances.
