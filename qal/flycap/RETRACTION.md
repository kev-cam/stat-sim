# RETRACTION — the two "measured QAL energy/op" headline numbers are NOT measurements

Both numbers committed in `1bf70fe` and `18a721d` are withdrawn. They were produced by
subagents in an automated run; an adversarial review of the same run found them invalid, and
each disqualifier below was then re-verified by hand against the files in this tree. Nothing
was pushed. The decks are kept because the *topology* result in them is real (see the bottom
of this file) — but the headline energies must not be quoted, cited, or built on.

## Retracted claim 1 — "TRUE QAL ENERGY PER OP = 1.966 fJ/hop"

`qal/qal_flycap_recharge.py:42`, commit `1bf70fe`.

It rests on `qal/qal_fc_perm.cir`, whose per-tier "bank top-up load" is five **ideal current
sources**:

    I1 t1 vn {IL}
    I2 t2 t1 {IL}
    ...
    I5 t5 t4 {IL}          (qal_fc_perm.cir:25-29)

There are **no banks, no switches, no gates, no flycaps and no hop anywhere in that deck**.
The solution is DC-constant (IRMAX == IRAIL to all digits). What it computes is Kirchhoff on a
series RC string: five tiers in series across 3.0 V reuse one charge, so E_rail = V_span*Q.
That is exact and true, but true **by construction** of 3.0/0.6 = 5 — it is not a measurement
of QAL, and "eta = 99.82% measured" overstates an algebraic identity. No `.mt0` for any
`qal_fc_*.cir` is tracked, so the claim's evidence file is absent from the tree as well.

## Retracted claim 2 — "193.755 fJ/op"

`qal/flycap/` + `run_c5.py`, commit `18a721d`. The deck itself is honestly built (no `.IC` /
`.NODESET` / `UIC`, DCOP solved, 13 real PSP103 devices, bulks tied) and is bit-reproducible.
The number is still wrong, for four independent reasons:

1. **It is a clock buffer, not QAL.** `c5_main.cir.mt0` gives `EDRV/20 = 193.804 fJ/op`
   against the 193.755 fJ/op headline — the figure equals the gate-driver domain's own supply
   draw to 0.025%. The QAL mechanism is the 2.95 fJ/op remainder, **1.5% of the quoted
   number**. The drivers also run at 3.0 V, 2.5x the SG13G2 1.2 V oxide rating.
2. **The energy does not take the architecture's path.** Per op, the flycap recharge path
   carries +0.0301 fJ while the switch-gate coupling caps carry +2.9225 fJ — so **99.0% of the
   lane's energy arrives through gate-drive coupling and 1.0% through the flying caps.** The
   defining premise ("all the energy in a running QAL goes through the flying caps") measures
   at one percent here. Flycap A even runs backwards (−0.434 fJ/op, pumping into the tier rail)
   while B draws +0.465.
3. **The closure gates cannot fail.** `run_c5.py:34` puts `EDRV` — a supply *input* to the
   driver domain — into `LANE_DISS`, the dissipation list. With only VRP/VRN on node 0,
   `ERAIL = EDRV + ETL + ERSER` is just KCL, so the G4 "residual" restates "the QAL physics is
   1.28% of the rail draw": it would FAIL on a perfectly correct circuit whose physics exceeded
   2% of rail draw, and a *missing* dissipator makes it look *better*. G3 is likewise an
   identity. And `run_c5.py:203` reads
   `g4 = min(abs(resid), abs(resid_norail)) <= 0.02*abs(Ein)` — it programmatically selects
   whichever accounting flatters. `run_c5.py:205` prints "E_rail (the ONLY real supply)", which
   is false: `ECK = 26.548 fJ/op` enters from three ideal 3.0 V PULSE sources
   (`c5_main.cir:128-130`) and is excluded. On the deck's own terms the honest input total is
   220.303 fJ/op, so the quoted figure is 13.7% low.
4. **Wrong operating point, and not settled.** The bank swing is 0.3656 V peak-to-peak on a
   0.600 V target, sitting on a 0.407 V pedestal — not a 0 -> dV hop, so no loss term in it is
   comparable to A1b, Track-C or twobank. The 20 per-op values *alternate* even/odd
   (194.846, 193.151, 194.797, 193.113, ... 192.833) rather than converging; the "last-3 spread
   = 0.822%" that G6 passes on IS that hop asymmetry. The DC-restore node is RDC*CCP = 6 ns
   against a 9.6 ns run, and V(gsab) drifts −13.6% inside the measured window.

Also note `qal_flycap_recharge.py:9-13` "corrects" `qal_twobank.py:15` from 0.425 to
1.96 fJ/hop. That correction is **not** established by these decks either; treat the twobank
number as open, not as superseded.

## What DOES survive — and it is worth keeping

**The rail/swing ratio makes the level-mismatch loss identically zero, by construction.**
For a DC rail, `E_rail = V_rail*Q` is exact, so a hard switch from 1.5 V into a 0.6 V swing
dissipates `(V_rail - dV)*q` — a **conduction** loss, first order in the droop and
**speed-independent**. Unlike the A1b settle loss (2RC/T, measured down to 3.4% at a 5 ns
ramp, `qal_a1b.py:29`), it cannot be removed by ramping, and a PV-cell rail cannot be ramped.
So a naive single-switch recharge is capped at `eta = dV/V_rail = 40%` permanently.

But the ±1.5 V rails and the 0.6 V swing are already in an exact **5:1** ratio. Five tiers in
series across the 3.0 V span give `eta_mismatch = N*dV/V_span = 100%` exactly, and the
mismatch term vanishes identically. Verified by re-running `qal_fc_perm.cir`: tier spacing
0.600 V, `IRAIL = 32.76 uA` = **one** tier-load current for five tiers.

This is a **topological identity (algebra + topology), not an empirical result** — the tiers in
that deck are loaded by ideal current sources, and in `c5_main` by plain 10 kOhm resistors.
Charge reuse is demonstrated for ideal sinks and for resistors; **never for QAL banks.** Label
it that way wherever it is used.

Corollary (also free, also structural): **never level-shift a flycap out of its tier.** A
floating cap tolerates common mode; its bottom plate does not. Keep every tier's common mode
static.

## What is still missing before a QAL energy/op number exists

1. A switch gate drive that is simultaneously **in oxide rating** and stack-balanced.
2. A loop in which the **flycap path actually carries the energy** (currently 1%).
3. At least 10 tau of settling (>= 60 ns, not 9.6 ns).
4. A per-gate-op denominator with a **filled bank**.
5. Real switching data, and the dual-rail version.
6. **A closure test that is not an algebraic identity** — one that can actually fail.

## Independent results that are NOT affected by this retraction

Measured separately in `qal/qal_hop_gates.py` (bank-to-bank resonant hop, real settling gates
on the receiving bank, ZCS at the *measured* current zero, `E_stored(V)` from a slow-ramp
calibration of the same bank — no ideal top-up source anywhere in that deck):

* **Transfer-path loss = 11.1% / 14.9% / 15.5%** of the energy leaving the sending bank
  (L = 100 / 400 / 25 nH). This **independently corroborates Track-C's measured 13.6%/hop** at
  the real w=10 um device, from a different deck by a different method, with real gates present.
* **The gates do not settle adiabatically at dV = 0.6 V on SG13G2.** `E_gates` = 4.74-7.23 fJ
  against `E_stored(full dV)` = 7.32 fJ, i.e. `f_adia ~ 0.65-1.0`, and slowing the hop 29x
  (25 -> 1600 nH) does **not** reduce it. Likely cause: at dV = 0.6 V with Vt ~ 0.4 V the gates
  have only ~0.2 V of overdrive, so RC_gate exceeds any hop time an on-chip inductor can give.
  Open test: sweep dV (0.6 -> 1.2 V) and see whether `E_gates/E_stored` falls sharply.
* **The analytic ZCS time is wrong for a gate-loaded bank**: the true current zero is
  **1.4-1.9x later** than `pi*sqrt(L*C_ser)` (121 vs 64.7 ps; 204 vs 129; 376 vs 259;
  717 vs 518). The gate-loaded bank capacitance knees hard at the device threshold and the
  gates draw current, so fixed analytic timing is not sufficient — tune per design against a
  measurement, or use real zero-cross detection.
* **A bank needs explicit rail capacitance** >> the gates' settling charge demand: with only
  the gates' own (nonlinear, small-at-low-V) capacitance, V_bank overshoots to 0.77-0.86 V and
  then sags to 0.04-0.51 V as the gates draw their charge out of the node.
