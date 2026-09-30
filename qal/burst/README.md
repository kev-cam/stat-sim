# qal/burst — wake→calibrate→burst→park, measured end-to-end; energy/op vs duty, QAL vs gated CMOS

Pre-registration: `PRE_REGISTERED.json`, sha256 `a3a194f7955c16e9f6d9262e7d0fdac4d6b664f0adebfa2d37badba6b239cd53`,
10 025 B, mtime **2026-09-30 11:41:39 −0700**, the only file in this directory at that instant.
Amendments `AMENDMENT.md` (A1 free-running collapse → top-up mode; A2 comb-leak band).
Own cache `vae_cache_burst` (warmed by COPY, never concurrent build). Machine record `RESULTS.json`,
cycle extraction `CYCLES_cy.json` / `CYCLES_cytu.json`, instrument `IC.json`.

## Instrument (b)
* Committed banktank dv1650 row regenerated **byte-identical**, re-run here: **440/440 .mt0 keys, worst rel 0.0** (`IC.json`).
* Parked-tank drain vs the committed leakage rate: measured **240 pA/tank** (∫I(L) and C·dV/dt agree to 0.4%) =
  **1.10e-5 % of tank charge per 150 ps beat** — the committed strip-class “1e-5 %/beat” REPRODUCES on the real banktank island.

## The QAL cycle (c) — MEASURED, three T_pre × two modes
* PARK: P_idle = **0.900 nW** for the 4-bank chain (871 pW = tank drain through L, 97%; park-gate rails 22 pW, VHI 3 pW
  by direct current; integrator-pedestal noise ±0.5 nW superseded by the direct reads). Null cap 0.000; tank+park-only
  island 1.3% → **the idle term is tank-leakage-only, proven from meters**. Linear: slopes 0.700/0.669/0.677 µV/ns over
  2–24 ns; cycle-deck pre-parks imply 769–895 pW at 1/2/4 ns. Drain path = the OFF transfer TG (8 pA/µm at Vds≈0.9 V);
  rails float to ≤0.13 mV. Junctions zeroed by the shim — LOWER BOUND, carried, ×10 sensitivity run.
* WAKE: committed SAR calibrate-on-wake **1.5 pJ [0.7, 4.0]** (committed-MEASURED pieces; not re-measured). At this run's
  deliberately short 160-op burst that is 9.4 fJ/op; it amortises as 1/burst-length.
* BURST (**A1**: per-wave tank top-up through a real tg15p TG from an ideal V_t0 rail — committed §8 costed convention;
  II 800→1000 ps for the ~240 ps recharge window): **160/160 value-correct, all 5 waves, all three decks**, first
  post-park wave included. Free-running control: wave 0 passes 32/32, waves 1+ collapse (67/128 fail) — the tanks are
  never refilled; the committed “tank droop IS the recharge requirement” composed over waves.
* Decomposition per burst (identical across T_pre to ≤2 aJ): top-up rail **763.4 fJ** + switch-gate booking (ideal PWL)
  **105.7 fJ** + inputs **6.9 fJ** + post-burst settle **0.8 fJ**; tanks end +22.7 fJ ABOVE start (credit NOT banked);
  E_vhi **−86.0 fJ export NOT banked** (IS3 rule). **Metered-only lower bound 0.877 pJ = 5.48 fJ/gate-op.**
  **Complete ledger** (+ committed timer 328.4 fJ/bank-hop × 20): **7.445 pJ = 46.5 fJ/op** (top-up gate drive still
  unmetered — the complete ledger UNDERSTATES by roughly another timer-class term; direction stated).
* Instrument note: reused ZCS zeros leave up to 181 µA at commanded opens under top-up; the waste is INSIDE the metered
  draw and the values still check — tuned zeros could only lower the QAL number.

## Gated CMOS done well (d) — every term's provenance
* Comb: **7.28 fJ/gate-op MEASURED HERE** (identical 32 cells, 1.2 V liberty nominal, same alternating patterns, α=1
  matched computation; 233.0 fJ/wave; inputs 0.14 fJ/op metered separately, symmetric with QAL's).
* Flop terms per active cycle, 8-flop output rank: central from the committed placed+CTS Vortex anchor — floor
  32.45 fJ (59.10 liberty × 0.549), tree 38.34 fJ (27.7 × 1.384, band 25.2–41.2), data 63.70 fJ at α_ff=1
  (38.51 × 1.654); lo from the committed add8 transistor anchor — 28.2 + 45 fJ. Burst: **central 6.55 pJ
  (40.9 fJ/op) / lo 4.09 pJ (25.6 fJ/op)** for the same 160 ops.
* Idle: power-gated **18.9 pW MEASURED HERE** (30 µm header held off, real device, chain on virtual rail at 30 mV);
  +64-bit SRAM retention 0.77 nW (committed 12.09 pW/bit; retained state cancels between sides); clock-gate-only:
  427 pW comb MEASURED HERE (13.4 pW/cell — **A2**: committed 117–131.5 pW/cell band does NOT reproduce on this
  junction-zeroed inverter fixture; both carried) + committed DFF 526.5 pW → **8.19 nW** committed-band variant.
* Generosity, stated: un-gate/re-gate FREE, wake FREE, α=1 comb is CMOS's most expensive booking of the same work.

## The curves and the crossover (e) — `RESULTS.json`
Duty = T_burst_QAL (5.46 ns) / cycle. E/op = (E_burst + E_wake + P_idle·T_idle)/160.

| QAL ledger | CMOS opponent | verdict |
|---|---|---|
| **complete** | **power-gate + SRAM (the committed selection-rule verdict)** | **CMOS wins at EVERY duty** — 55.9 vs 40.9 fJ/op at duty 1, and CMOS idle is 48× lower |
| complete | clock-gate-only (committed leak band) | QAL wins **below duty 1.7e-5** (T* 0.33 ms) |
| metered lower bound | power-gate + SRAM | QAL wins **above duty 1.2e-6** (14.9 vs 40.9 fJ/op at duty 1; CMOS re-takes the ultra-idle corner) |
| metered lower bound | any clock-gate-only variant | QAL at every duty |

DERIVED note: at T_idle beyond ~0.8 ms the QAL idle books CAP at the full-tank recharge (~0.69 pJ = 4·½CV²/0.864) —
the parked state degrades gracefully into a cold start, so the metered-ledger ultra-idle loss re-inverts below
duty ~1e-7. Not the headline; the complete-ledger verdicts are unchanged.

## Sensitivity (5)
* **QAL idle ×10** (9.0 nW — the junction-zeroed caveat made real): every QAL-complete win above dies except vs
  half-effective gating; the metered-ledger win shrinks to duty ∈ [1.2e-5, 1] vs power-gated CMOS.
* **CMOS clock gating half-effective** (half the flop floor+tree runs through idle at the 486 ps derived clock:
  0.58 mW): QAL complete wins below duty **0.57** — gating quality is the entire game, which is exactly why the
  comparator had to be gated-CMOS-done-well.

## Verdict
**The last open regime is CLOSED.** Against the committed selection-rule opponent — sync + clock-gate + power-gate,
state in SRAM, free re-gate — the complete measured QAL ledger loses at every duty: the bursty/mostly-idle workload
does not rescue QAL at SG13G2, because parked QAL (0.90 nW) idles 48× above a power-gated header (18.9 pW) while its
burst is 1.4× dearer once the measured timer hardware is paid. What survives, honestly labeled: (i) the metered-only
lower bound (no timer, recovered gate drive) wins 2.7× at duty 1 and above duty ~1e-6 — the timer/driver arc is the
whole distance between “QAL wins the burst” and “QAL never wins”; (ii) against merely clock-gated CMOS the brief's
motivating story is real and lands at duty* ≈ 1.7e-5. Park correctness is clean: tanks hold (1.1e-5 %/beat), the
first post-wake burst computes 32/32 everywhere, and nothing beyond the booked calibration needs re-establishing.
