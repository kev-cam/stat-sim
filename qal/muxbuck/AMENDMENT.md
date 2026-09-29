# Amendments to `qal/muxbuck/PRE_REGISTERED.json`

Pre-registration: sha256 `2943081d642afade0b4bcf0764935d0e7c779768a07042fc1836cf127fc2c9c6`,
11819 B, mtime **2026-09-29 10:49:15.631109403 -0700**, written when the only
other thing in this directory was an empty `vae_cache_muxbuck/`.
First deck file written **10:50** (`mb_instr.cir`), first result `.mt0` **11:03**.

---

## A1 — a deck ADDED that was not in the pre-registered plan: `mb_gain_v58.cir`

The pre-registration says the band is converted to tank volts "by the MEASURED
incremental gain `g = dV_rail/dV_tank`". One operating point cannot give a slope.
`mb_gain_v58.cir` is `mb_droop8` with the tank pre-charge at **0.58 V** instead
of 0.66 V, one cycle. Two measured points → `g` by construction, not by a ratio.

  | tank pre-charge | delivered rail at ZCS |
  |---|---|
  | 0.66 V | 0.7664331 V |
  | 0.58 V | 0.6915544 V |

  **g = 0.93598 V/V, offset 0.14868 V.**  Sanity: the committed pre-charge 0.66 V
  maps to rail 0.7664, and my pre-registered band TOP 0.7656 maps back to tank
  0.6591 V — i.e. the committed pre-charge sits essentially exactly at the top of
  the band I chose before measuring. That was not arranged.

## A2 — `mb_droop8` cycles 1 and 2 are INVALID and are not used

The deck runs three repeated rise/return cycles on the committed bank-1 window.
Only **cycle 0** is valid. Measured, in the waveform:

* The return hop does **not** bring the rail back to 0. It takes the rail from
  0.7977 V down to 0.4797 V, the gate opens, feedthrough puts it back to 0.5141 V.
  The rail then stays there.
* So cycle 1 starts with the rail already at ~0.52 V and cycle 2 at ~0.60 V, and
  the measured "Q_beat" collapses 35.42 → 9.72 → 6.72 fC for that reason alone.
* Mechanism, not mystery: an LC return can only swing the rail symmetrically about
  the tank voltage, so from a 0.52 V tank it can reach at best ~2·V_tank − V_rail,
  never 0. The committed park in this topology is **tank-referenced** (banktank A6)
  and pins `sw`, not the rail; nothing drains the rail to ground. In the committed
  chain the un-compute wave does that job, and the committed banktank deck only
  ever runs ONE rise+return per bank, so it never exercised this.

**Reported, not fixed** — repairing the un-compute is the sibling runs' territory.
`Q_beat` is taken from cycle 0, whose initial condition (`rail = 0`, tank 0.66 V)
is the committed one, and it is corroborated twice from outside this directory:

* delivered rail **0.76643 V** vs the committed banktank m=10 probe **0.7656 V** (0.11%);
* **35.42 fC** vs banktank A8's independent "tanks each rose 0.5611 → 0.6388 V on
  359.79 fF ≈ 28 fC", whose implied one-cycle loss 0.66 → 0.5611 V is **35.6 fC** (0.5%).

## A3 — the whole-cycle L-integrator cross-check is invalid by construction

`Q_beat` from the linear tank cap and `Q_beat` from `∫I(L)dt` disagree by 29% over
a full cycle. That is **correct behaviour**, not a metering fault: during the hold
the tank-referenced park closes the loop `tnk → L → R → sw → park → tnk`, so
current circulates **through L without changing the tank's charge**. Over the RISE
sub-window, where the park is open and the two must agree, they do:
`∫I(L) = 69.0 fC` against `ΔV_tank·C_T = 69.55 fC` (**0.8%**). The tank-cap method
is therefore the primary one and the integrator corroborates it where it can.

## A4 — `mb_droop48` FAILED the pre-registered A3 ZCS gate and was re-run

Pre-registered gate: flag any row with `|I(L)| > 30 µA` at a commanded open.

* `mb_droop48` (committed 118.184 ps rise window, scaled L=2.5 nH / C=2158.74 fF):
  **IZ_rise = −490.2 µA**, stranded `½LI² = 1.80 fJ`. **FAILS.**
* Cause, measured off its own `.prn`: the true current zero is at **269.432 ps**,
  i.e. a **69.43 ps** half-period, not 118.18 ps. My pre-run scaling argument
  ("L/6 with C×6 preserves the half-period") assumed the bank rail capacitance
  scales with gate count. **It does not** — see A5.
* Re-run as `mb_d48z1.cir` at the measured zero. `IZ_rise = +96.6 µA` — still
  above the 30 µA gate, so this row is **still flagged**; stranded energy is now
  **0.070 fJ**, ~0.5% of the hop, i.e. physically minor. A second ZCS iteration
  would clear it; it was not run, and the 48-gate number is reported as FLAGGED.

## A5 — a measured fact that was not anticipated: the bank rail is switch-dominated

From the two measured LC half-periods (118.176 ps at L=15 nH, C_T=359.79 fF;
69.432 ps at L=2.5 nH, C_T=2158.74 fF):

  **C_rail(8 gates) = 127.86 fF, C_rail(48 gates) = 214.82 fF.**

Marginal **2.174 fF per inverter**, fixed part **110.5 fF** — i.e. **86.4 % of the
bank rail's capacitance is the transfer switch (TG 10u/20u + 2u park = 32 µm),
not the logic it feeds.** This explains, rather than excuses, why `Q_beat` scales
**4.29×** for a **6×** gate count.

## A6 — pre-stated expectation E2 is REFUTED, recorded as a miss

E2 predicted the tank would droop 8–12× more slowly than the held bank rail,
"because the droop ratio is set by capacitance ratio". Measured on the 48-gate row
(the only one where the rail is genuinely under load): tank **0.01375 mV/ps**,
rail **0.44600 mV/ps** → **32.4×**, not 8–12×. The named mechanism: the two nodes
are **not losing the same charge**. During the hold the transfer gate is open, so
the tank is isolated and only leaks, while the rail is still supplying settling
current to cells that have not finished. Right direction, wrong term — the same
shape of miss as `vtreq`'s E2.

Corollary, and it reconciles a committed number: the committed **−28.6 mV/300 ps**
held-rail droop is a **settling-era** figure, not a leakage figure. In my 8-gate
row the cells are quiescent at the ZCS instant and the rail is flat to **< 1 µV
over 554 ps**; in my 48-gate row, where settling is genuinely unfinished, the rail
droops **−133.8 mV over 300 ps**. The committed figure sits between them.

## A7 — pre-stated expectation E3 was right in direction, wrong in framing

E3 predicted the committed 359.79 fF tank holds band for "only about 1–2 beats"
and concluded "the tank must be RE-SIZED as C_tank ∝ N". The first half is
**confirmed**: band store = 34.67 fC against `Q_beat` = 35.42 fC → **0.979 beats**
of autonomy. The conclusion was **mis-framed**: the interval a tank must bridge is
the interval between BUCK VISITS, and the buck's pulse cadence is **64.06 ps**
(measured off the committed ptu gate schedule), not the 1600 ps bank cycle. A tank
therefore only has to bridge `N × 64.06 ps` of draw, and the committed tank does
not have to grow until **N > 24.4**. My pre-registered `C_tank ∝ N` and its `N²`
area consequence are correct only **above** that knee. Recorded as a miss.

## A8 — the +31.2 mV switch-open feedthrough, and which rail the band is applied to

At the ZCS open the 2 ps gate ramp injects the TG's own channel/overlap charge into
the floating rail: 0.76643 V at the ZCS instant → **0.79771 V** once the switch is
fully open, and then flat. Both are real. The pre-registered band is stated against
the **delivered rail at the ZCS instant**, because that is the convention the
committed settling series (40.4 ps @ 1.200 V … 801.3 ps @ 0.4885 V) uses. The
+31.2 mV is reported as a separate measured fact and is **not** spent as margin.

## A9 — the gate-drive ENERGY integrator does not reconcile; no conclusion rests on it

The integrator expression `-V(g)*I(Vg) …` is **verbatim** from the committed
`lsweep` deck. It returns **−9.3 fJ per cycle** (negative) on the droop decks and
**+2.28 fJ** on the mux deck, against a `Cox·W·L·V²` estimate for the mux TG of
**73.8 fJ** (PSP103 `toxo` = 2.2404 nm n / 1.9704 nm p → 15.41 / 17.53 fF/µm²;
5u + 10u at l = 0.13u → 32.8 fF; ×1.5² V). The plausible reading is that with an
**ideal** PWL gate source the reciprocal CV² returns to the source and only the
irreversible part remains — which makes 2.28 fJ the *adiabatically-driven* cost and
73.8 fJ the *conventionally-driven* cost. I report both, flag the discrepancy for
the campaign, and **base no conclusion on gate-drive energy**. Charge numbers are
unaffected (they come from linear capacitors, not from this integrator).

## A10 — the mux N-sweep measures the COMMITTED buck, which is under audit

`mb_mux_N{1,4,16}.cir` use the committed `qal/ptu` buck block verbatim (HS pmos 10u,
FW nmos 10u, LTU 1 nH, RTU 10 Ω, OUT TG 5u/10u), time-shifted by −300 ps. My own
run reproduces the audit's complaint independently: **Qdel/Qsup = 0.0417**, against
the ideal DCM bound 1.5666. Only the **N-DIFFERENCE** between these three decks is
claimed as this run's result; the absolute delivery is the sibling audit's to settle.
