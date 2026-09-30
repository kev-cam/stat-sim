# SKEPTIC amendments

SKEPTIC_ACCEPTANCE.json (23:45:25, sha256 12948f5c...) is NOT edited. Every
correction is here, with what forced it and when.

---

## SK-A1 — my own pre-stated S3a was too strong, and I am weakening it BEFORE running the point
**When:** 23:52, after the instrument check and before any sweep row.
**What forced it:** thinking the physics through instead of the accounting.

S3a pre-stated that the floor row's NEGATIVE driver term is a booking error and
that flooring it at zero is the correct fix, which would move the crossing from
N=64 to N=128.

On reflection the negative term is **physically real**: while the switch's
drain/source node swings, charge is pushed through C_gd / C_gs into the gate
driver's supply (the Miller path). Those joules left the tank — and so are
already inside the MEASURED tank droop — and arrive at the gate-drive supply. A
gate driver that is a lossless bidirectional converter really could return them.
So `E_tank_loss + E_gate_drive_net` with a negative `E_gate_drive_net` is a
defensible idealisation, not an arithmetic mistake.

What survives, and is what I will actually test:

* the credit is **small**: −4.528 fJ/bank at N=64 = −0.0708 fJ/gate, which is
  **1.7 %** of the 4.14 fJ/cell/op bar;
* the published crossing margin at N=64 is **0.9 %** (0.991×);
* so **the crossing at N=64 is smaller than the effect of one ledger
  convention on one term that the record itself labels a subsidy.**

REVISED CLAIM TO TEST: not "the crossing is fake" but "**N=64 is inside
convention noise and is the wrong place to put the crossing; the first
crossing with a margin larger than its own bookkeeping is N=128.**"
Reported either way.

## SK-A2 — the decisive booking is the CONVERTER, and it is robust to SK-A1
**When:** 23:52, same reasoning pass.

`E_tank_loss` is 98 %+ of the floor row at every N, and it is *precisely* the
energy a converter must resupply each cycle. No converter is simulated in any
row of either phase (declared). So the honest form of the crossing question is
not "does 4.10 beat 4.14" but "**at what converter efficiency does the crossing
survive**". That is one line of arithmetic on MEASURED quantities and it does
not depend on how the Miller credit is booked:

    E_per_gate(eta) = (E_tank_loss / eta + E_gate_drive_net) / N  <=  4.14

To be computed at every N I run, with the Miller credit LEFT IN (the generous
reading). Pre-stated expectation: N=64 needs eta ≈ 0.99, N=128 ≈ 0.92,
N=256 ≈ 0.87.

## SK-A3 — S3b is CONFIRMED in advance on the record's own stored row, and I say so
**When:** 23:50, from `upsize/row_n64_T440_H4_dv1650_free_nb3.json`.

I formed S3b (that `|Q_close| + |Q_open|` double-counts a conventional driver)
before looking, then checked it against the record's stored row to decide
whether it was worth building a control around. Measured there:
`|Q_open| / |Q_close| = 1.0133` on the rise hop, and
`|Q_close_rise| + |Q_close_return| = 312.36 fC` against the instrument's
per-hop `312.66 fC` and per-CYCLE `622.15 fC`.

So the arithmetic is: Phase 1's rise-hop conventional row was already the
correct FULL-CYCLE real-driver number (to 0.1 %), and Phase 2's amendment A1 —
presented as a correction — is a **1.99× overcharge**. This is a finding that
cuts in the record's FAVOUR and it will be reported as prominently as the ones
that cut against it.

I will re-derive all of it from MY OWN rows; the numbers above are only why the
control was worth building.

## SK-A4 — the well-rail sensitivity is the wrong SIGN of correction
**When:** 23:52.

`E_wellrail` is NEGATIVE (−38.873 fJ/bank at N=64): the ideal 1.5 V
pMOS-switch well supply **receives** charge. Same for bank 1's ideal DC inputs
(−111.99 fJ). Those are SINKS, and the charge they absorb transited the switch
from the tank, so those joules are **already inside the MEASURED tank droop**.
Adding `|E_wellrail|` as an extra cost — which is what the record's own
"charging it erases the crossing at N=64" sensitivity does — counts the same
joules twice.

Test: per-bank well metering (a new control, `SK-W`, adding a transparent 0 V
ammeter per bank's well lead) plus the A6 tank-closure residual. Reported with
the argument, and flagged as a correction that favours the record.

## SK-A5 — a UNIT MISMATCH in the CMOS bar that I did not pre-state, and it is the largest effect I have found
**When:** 00:00-00:02, while waiting on the warm; found by tracing the
provenance of `CMOS_BLOCK_PER_CELL_FJ = 4.14` instead of taking it as given.
**Not in my pre-registration.** Reported as an unplanned finding.

`upx.py` sets the hard bar as `4.14 = 232 fJ/op / 56 cells`. Traced:

* `qal/bound/PRE_REGISTERED.json` — sha_slice: 105 generic gates, depth 10,
  `cmos_fJ_per_op = 232`, `cmos_ns = 0.928`.
* `qal/sha256/REMAP.json` `committed` (= `qal/synth/threeway/work/sha_slice.cmos.v`)
  — **56 cells, depth 8**, profile 32/12/3/2/2/2/2/1, cell histogram
  xnor2 x10, mux2 x8, a21oi x6, nand2 x5, o21ai x5, nor2 x5, inv x3, or2 x3,
  and2 x3, a21o x3, nor2b x3, xor2 x2. So 53 of 56 are multi-input cells.
* `qal/sha256/REMAP.json` `nand_mindepth` — **161 cells, depth 14**, profile
  41/32/26/21/6/5/3/7/4/7/3/4/1/1. **This is exactly the profile the brief
  quotes**, and it is the remap the campaign's own standing correction
  requires ("synthesise for WORST-CELL SETTLING TIME... the most restrictive
  library gave the FASTEST block").

So the same function is **56 CMOS cells or 161 QAL cells**, a 2.875x cell
inflation, and the QAL "gate" in every row of both phases is a minimum-size
INVERTER. Scoring QAL per-inverter against 232 fJ / 56 complex cells charges
QAL for 56 cells when its own implementation needs 161.

The tell that this is an inconsistency rather than a choice: the record *does*
carry the other half of the same remap — it uses `max(profile) = 41` to cap the
bank width and concludes the crossing is unreachable for one block. The cell
count from that identical profile does not reach the energy normalisation.

Fair per-cell bar for a QAL block: **232/161 = 1.441 fJ/gate**, not 4.14.

To be computed from MY OWN rows by fitting `E_bank = b + a*N` and composing the
block over the real profile, at 1 lane and in the infinite-lane limit
(`sk_block.py`, written before the data landed).

## SK-A6 — both sides of the comparison are LOGIC ONLY, so QAL's no-clock win is excluded from both
**When:** 00:01. Verified, not assumed: the committed record states
"No timing hardware is counted in either -- that is Phase 2."

The 232 fJ CMOS figure carries no clock tree and no registers, and QAL's timer
is booked at 0. That makes the comparison internally consistent, and it means
the question these two phases answer is strictly **logic energy vs logic
energy**. QAL's largest claimed advantage in the committed record — clock
elimination, "regimes ~19-136x" in `threeway_gals_campaign` — is outside this
comparison on BOTH sides and neither phase's result speaks to it. I will say so
rather than let the negative read as a verdict on QAL as a whole.

## SK-A7 — the sweep measures an INVERTER-ONLY bank, which is the easiest possible case
**When:** 00:00.

Every bank in every row of both phases is N identical minimum-size inverters on
one lumped rail. Two consequences the record under-weights:

1. **The value check cannot fail per-gate.** N identical cells sharing a rail
   and driven by two input levels are electrically degenerate, which is why the
   measured intra-class spread is exactly 0.000 mV. "All 192 gates
   value-correct" is really "6 distinct node voltages correct". The real risk —
   a heterogeneous bank gated by its slowest cell — is not exercised at all.
2. **The level times are a lower bound for real logic.** The campaign's own
   standing correction says `sg13g2_o21ai_1` is 3.12-3.55x slower than an
   inverter and that a bank opens when its slowest cell has settled. A bank of
   real cells is therefore materially slower than these rows, which makes the
   SPEED verdict worse, not better.

One honest caveat in the OTHER direction: with a slow worst cell the level
would become SETTLE-bound at every N I ran, and the cell-upsizing lever is
untested in that regime. But it is still bounded: a cell cannot settle before
its own rail arrives, so `t_hop` is a hard floor under the level, and `t_hop`
grows with cell width. Upsizing therefore raises the floor while shrinking only
the excess above it — a win is possible only for a cell whose excess exceeds
roughly twice the hop, and then only at s=2. Stated as a gap, not a result.

## SK-A8 — a CLOBBER/WAIT trap found and cleared before it cost anything
**When:** 00:06-00:07, while the warm was still running.

I noticed TWO `warm_sk.py` processes on the box when I had launched one.
Traced by PID rather than assumed:

* mine — pid 1466030, cwd `/usr/local/src/stat-sim/qal/wbskept`,
  `PYMS_VAE_CACHE=.../vae_cache_wbskept`
* not mine — pid 1582482, cwd `/usr/local/src/stat-sim/qal/cipher/skept`,
  `PYMS_VAE_CACHE=.../vae_cache_ciphskept`

A DIFFERENT concurrent study happens to have a file with the same name
(`warm_sk.py`) writing a deck with the same name (`warm_sk.cir`). Separate
directories and separate caches, so there was no collision and no corrupted
library — verified, not assumed.

But my first `autolaunch.sh` waited on `pgrep -f "warm_sk.py"`, which matched
the OTHER study's process, so my whole sweep would have sat idle until an
unrelated study's warm finished. Rewritten to wait on `kill -0 $MYPID` with my
own PID passed in. This is the same family as the campaign's recorded
pkill-self-match trap: **match processes by PID, never by pattern, on a shared
box.**

Also added to the relaunched autolaunch, because a warm that dies half-way
would otherwise have every sweep point trigger its own concurrent PyMS compile:
a hard gate that refuses to launch unless all 20 `.so` exist AND every one is a
valid `ELF 64-bit LSB shared object`.

## SK-A9 — the PSP103 `.so` is NOT reproducible, and the non-reproducibility is NUMERICALLY CONSEQUENTIAL
**When:** 00:35-00:40, found because my re-run of the 32-point crux grid came
back with 31 points.

One deck of 32, `ck_r16500_D_s8.cir` (variant D, cell scale x8, rail 1.65 V),
**would not converge with my own freshly compiled PSP103 library.** Xyce exits 1
and the run dies at t = 198 ps, exactly the input edge.

Isolated to the compiled library, by control rather than by argument:

| | deck sha256 | `.so` | Xyce rc | .prn |
|---|---|---|---|---|
| my cache | 5aad67da... | mine | **1** | 950,592 B, stops at 198 ps |
| same dir, same deck | 5aad67da... | from `vae_cache_upsize` | **0** | 5,770,203 B, completes |

* the deck is **byte-identical** to the record's `cc_r16500_D_s8.cir`
  (same sha256 5aad67da...);
* the two libraries have **identical `.params`** and **different `.so` bytes**
  (`vae_PSP103VA_6170ff1210d23f12.so` and `...a401a3b8ea9560f4.so`, same
  filenames, same byte SIZE, `cmp` DIFFERENT);
* both runs were in the same directory, so the only variable is the library.

The record's Phase 2 amendment A6 had already noticed the `.so` are not
byte-reproducible ("the build path is embedded... same name does not mean same
bytes") but concluded only that this invalidated a *justification* for merging
caches. It did not test whether the difference **matters numerically**. It
does: it flips convergence on a committed deck.

SCOPE, measured not assumed. On every deck that DOES converge the numerics are
identical to the printed digits — my 31 independent points reproduce the
record's crux values exactly (A 72.734/60.592/55.074/52.218, ratio 0.7179;
k 6.4912 ps/fF; C_j 1.6133 fF; C_g1 4.1433 fF), and the recovered D s8 point
reads 45.3053 ps against the record's 45.305. So this is a **convergence-
robustness** defect, not a systematic numerical shift. But it means no result
in this campaign is guaranteed to re-run on a fresh cache, and that is a
standing reproducibility caveat for the whole campaign, not just for me.

The D s8 point in my grid is therefore extracted from the run that used the
record's library. Deck mine, extraction mine, compiled library not mine, and
labelled that way in `ck_ck_r16500_E_s8.json`... (in
`ck_ck_r16500_D_s8.json`, field `_CAVEAT`).

## SK-A10 — variant E fires, and the scale-invariance finding is STRONGER than published
**When:** 00:41.

The pre-stated S4 control (my own, not in the record) came out as pre-stated.
With an explicit `(s-1)*C_j` added at every cell output node to emulate the
`AD` proportional to `W` that `qal/sg13lv_compat.sp` prevents:

| variant | t_set90 s=1/2/4/8 (ps) | s8/s1 | asymptote |
|---|---|---|---|
| A real chain (as published) | 72.734 / 60.592 / 55.074 / 52.218 | 0.7179 | 0.677 |
| **E junction forced to scale** | 72.734 / 65.697 / 62.867 / 61.424 | **0.8445** | **0.821** |
| C fixed load (positive control) | 72.734 / 46.417 / 34.603 / 28.810 | 0.3961 | 0.305 |

So 8x the cell width buys **15.6 %** less settling, not the published 28.2 %,
and even INFINITE cell width can only buy 17.9 %. The record's own caveat that
its 28-32 % is an upper bound is correct, and now measured.

A second, independent confirmation of the load decomposition falls out of it:
the model requires `b_E = C_wire * k = 2.00 * 6.4912 = 12.9823 ps` with nothing
left to fit. **Measured 12.9699 ps, 0.1 % error.**

And my non-tautological cross-check passes at both rails: `a_B - a_A` predicted
from SLOPES as `C_wire*k`, measured from INTERCEPTS — 12.9823 vs 12.9330
(-0.38 %) at 1.65 V, 25.4521 vs 25.7596 (+1.21 %) at 0.9422 V. The record said
its own version of this check was tautological; this form is not, and the
decomposition survives it.

## SK-A11 — RESULT OF THE RE-RUN: the published rows are FULLY reproducible
**When:** 01:24, all simulation complete.

Six rows re-run from scratch in my own empty PyMS cache, in my own directory,
with a generator proven byte-identical to the one under audit. Every one
reproduces the record:

| row | worst relative error vs the record |
|---|---|
| N=32 T=330 | 5.36e-11 over 14 quantities |
| N=64 T=440 (the headline) | **1.50e-10 over 13 quantities** |
| N=128 T=580 | A2 449.4 mV, E/gate 3.8065, t_hop 406.72 — all as published |
| N=256 T=790 | A2 465.1 mV, E/gate 3.5980, t_hop 554.54 — all as published |
| E6 L=3.75 nH | level floor 152.322 ps, A2 283.47 mV, recycle -11.83 % |
| N=64 s=2 | E/gate 6.3788, t_hop 380.12, A2 504.3 mV |

and the derived quantities land on the record's own figures independently:
`N_min` interpolated in 1/sqrt(N) = **59.5** (record: 59.5); per-gate energy at
the N=41 composition cap = **4.3478 fJ = 1.050x** (record: 4.348, 1.050x);
32 crux points exact, including `k` = 6.4912 ps/fF and `C_j` = 1.6133 fF.

`ACCEPTED = True`, `A1_value_fail_count = 0` and `A2 n_pass_bare = N of N` on
every row. So (a) PASSES: nothing in the published arithmetic is a
transcription or extraction artefact. **The disagreements in my report are about
what the numbers MEAN, not about what they are.**

The one exception is SK-A9: one crux deck of 32 would not converge with my own
freshly built PSP103 library.

## SK-A12 — my own S3a was wrong, as SK-A1 anticipated, and here is the measured number
**When:** 01:24.

Measured `E_gate_drive_idealPWL_per_bank`: -2.195 / -4.528 / -7.110 / -10.213 fJ
at N = 32 / 64 / 128 / 256. Flooring it at zero moves the first crossing from
N=64 to N=128 (0.991 -> 1.008 at N=64; 0.919 -> 0.933 at N=128). But per SK-A1
the negative term is physically real recovered Miller charge, so I do NOT claim
this as an error. What I claim, and what the numbers support, is narrower and
survives either convention: **the N=64 crossing has a 0.9 % margin and one
defensible change of convention on one term flips its sign, while N=128 (0.933)
and N=256 (0.879) do not flip.** N=64 is the wrong place to put the crossing.

## SK-A13 — the well-rail double-count is CONFIRMED by measurement, and it favours the record
**When:** 01:24.

At every N, all three ideal sources are measured SINKS, not suppliers:
`E_gate_drive` -2.195..-10.213, `E_wellrail_total` -82.308..-231.490,
`E_ideal_inputs_bank1` -56.468..-440.917 fJ. And the A6 tank-closure residual is
**0.04-0.16 %** of the tank loss on every bank of every row, i.e. the measured
tank droop already accounts for everything that leaves the tank.

Combined with the topological fact that `vhi` touches nothing but the ideal
source and three switch-pMOS bulks (SK_TOPOLOGY.txt), the record's own
sensitivity — "charging the pMOS well rail puts N=64 at 4.711 fJ/gate = 1.138x
and ERASES THE CROSSING" — **double-counts joules already inside
`E_tank_loss`.** It is the wrong sign of correction and should be withdrawn.
