# qal/vtreq protocol amendments

Order on disk is the proof (`ls -la --time-style=+%H:%M:%S`): `PRE_REGISTERED.json`
01:50:10 was the **only** file in this directory at the moment it was written
(sha256 `147e29645b305348c510ed059da2c14f867cbaee5c2b5bb27d8f9b669982fd9f`, 23604 B);
`shim_dvt.sp` 01:50:53; `warm.py` 01:51; the first warm-up deck 01:51; `vt.py`,
`drive.py`, `analyse.py`, `chain.py` after that; the first *result* deck (`dc_*.cir`)
at 02:2x. Every amendment below is forced by a measurement and states it.

---

## A1 — the committed single-hop `t_hop` anchor I quoted is from the OTHER harness path

**Pre-registered:** gate G0(a) requires the robust single hop to reproduce
`t_hop = 65.49500982344826 ps` at rel < 1e-6.

**MEASURED, rel 1.88e-06 — which would have failed the gate as written.** Bisected,
and the cause is a documented cross-harness convention, not an instrument fault:

| quantity | mine (sk path, this dir) | `qal/skept/rows.json` `headline` (sk path, committed) | rel |
|---|---|---|---|
| `t_hop_ps` | 65.49488693068957 | 65.4948869306443 | **6.9e-13** |
| `VBEND` | 0.713816259 | 0.713816259 | **0.0** |
| `VBPK` | 0.836889358 | 0.836889358 | **0.0** |
| `VAEND` | -0.004293553919758978 | -0.004293553919743036 | 3.7e-12 |
| `IPK_uA` | 971.3200730000001 | 971.3200730000001 | **0.0** |

The `65.49500982344826` figure I pre-registered is `rest.py`'s `TZ_ANCHOR`, which
comes from the **lsw / `.measure`** path (that path carries a MEASURED +1.0 ps
`.measure FIND` lag correction; `restore5/rest.py` `LAG_PS = 1.0`). The **sk path**,
which is the one this study uses and the one that generated `load691`, reads the
zero off the waveform. The two differ by 1.2e-4 ps.

**Amended:** G0(a) is judged against the **same-path** committed anchor,
`qal/skept/rows.json` `headline`, and it passes at **rel 6.9e-13 on t_hop and
exactly 0.0 on VBEND / VBPK / IPK**. The lsw-path number is recorded above as a
cross-path difference of 1.9e-6, which is smaller than every effect this study
reports, and is not used as a gate.

**G0(b) needed no amendment and is exact:** the real-load level reproduces
`t_valid90 = 115.467185 ps`, `t_settle90 = 100.330297 ps`, `VBEND = 0.754572966`,
`VA_open = 0.11745601600934541` — every printed digit of
`qal/dvopt/load691/rows.json` `cl_d165_L4_W30` — and `t_hop` at rel 1.5e-12.

**So the DELVTO shim is a strict superset of the committed shim at DVTN = DVTP = 0.**

---

## A2 — Xyce's `.DC` `.prn` does not carry the sweep source, and the first DC pass was void

The first 16-deck DC pass extracted the sweep axis from `.prn` column 1, which for a
`.DC` run is the first **printed variable**, not the swept source. Every threshold
and trip point came out as noise (`Vtn = -1e-6`, all trip points `None`). Caught
immediately because the DELVTO = 0 row did not reproduce the committed
`Vtn = 0.5239460 / |Vtp| = 0.4402734`.

**Fixed:** `V(g)` is printed explicitly and is the sweep axis. All 16 decks re-run
from scratch. After the fix the DELVTO = 0 row reads **Vtn = 0.523987** against the
committed **0.5239460** (41 µV apart, this study's grid is 1 mV where
`chain3/vt.cir` swept 5 mV) and **|Vtp| = 0.440283** against the committed
**0.4402734** (10 µV apart). That is an independent instrument check the
pre-registration did not ask for and it passes.

No number from the voided pass is used anywhere.

---

## A3 — `V_strand` is reported at FOUR current criteria, not one

Pre-registered: the strand level at "the campaign criterion". Kept as the headline
so it is directly comparable to `|Vtp|` (same criterion, same device). But the
physically relevant end is much lower current: a held 2 fF output node moving 1 mV
over a 300 ps beat needs only ~6.7 nA, so the campaign's 861.5 nA criterion
describes where conduction has become *fast*, not where it has stopped. All four
(861.5 nA / 100 nA / 10 nA / 1 nA) are therefore reported. **The conclusion does not
depend on the choice**: the SHIFT per volt of DELVTO is what the verdict uses, and
it is 0.81 / 0.80 / 0.72 / 0.53 V/V at the four criteria — same sign, same order,
and the tightest criterion is the one that flatters QAL least.

---

## A4 — the mode split turned out to be load-bearing, and it changed which question is which

Pre-registered expectation E2 predicted the chain would get WORSE as `|Vtp|` falls,
because the stranded HIGH tracks `|Vtp|` while the receiver's trip point barely
moves. **MEASURED: the first half is right and the second half is wrong, and the
error is in QAL's favour on a device I did not expect.**

- stranded HIGH tracks `|Vtp|` at **0.81 : 1** (MEASURED) — E2's mechanism CONFIRMED;
- the receiver's trip point at the delivered rail moves **−0.485 V per volt of pMOS
  DELVTO** (MEASURED), i.e. **4× more than E2's derived 0.12**, and in the direction
  that makes the requirement HARDER;
- but it moves **+0.463 V per volt of nMOS DELVTO** — and the stranded HIGH does not
  move at all with nMOS DELVTO (MEASURED: identical to 6 decimals on all five N rows).

So the pMOS and nMOS shifts are **not two views of one knob**; they act on opposite
sides of the same inequality. That is a finding, it is reported as one, and it is why
the three-mode split the brief insisted on was necessary. E2 is scored as
**mechanism confirmed, magnitude wrong, and the repair found on the other device**.

**A4 was written from the DC grid alone, before the chain decks finished. The chain
then refuted the conclusion A4 was heading toward — see A6, which supersedes this
paragraph's implication that lowering |Vtp| damages the chain. A4 is left standing as
written so the order of belief is visible.**

---

## A5 — L IS RE-OPTIMISED at each threshold, and that is EXPLORATORY

Pre-registered: "L per the committed optimum for that load/point." **Amended, and the
amendment is declared EXPLORATORY and reported separately from the pre-registered
fixed-L form, which is also reported in full.**

Reason, and it is a MEASURED one, not a convenience: the QAL level decomposes as
`t_hop + t_settle`, and `t_hop = pi*sqrt(L*C/2)` contains **no threshold**. MEASURED,
it moves +0.11% (34.286 -> 34.324 ps) across the entire DELVTO sweep while `t_settle`
collapses x0.42. So at a shifted threshold the hop becomes the majority of the level
(50% at the most aggressive point) and the L that balanced the two at DELVTO = 0 is no
longer the balance point. Re-optimising L is the only lever that can attack the residue,
and it can only HELP QAL — so running it strengthens a negative verdict and is a genuine
finding if it closes. Both forms are tabled.

MEASURED, and this is the mechanism that makes the re-optimisation legitimate rather
than a free parameter: at DELVTO = 0 the committed grid **could not use** small L,
because the rail-drain gate C2 (`VA_open <= 0.1478 V`) excluded it — L = 1 nH reads
`VA_open = +0.263`, L = 2 nH `+0.181`. A lower threshold makes the transfer switch
strong enough to drain the source bank inside a shorter hop, and the same L = 1 nH row
reads `+0.099` at DELVTO_B = -0.30. **The threshold shift is what re-admits the small
inductor.** That is a real coupling, not a knob.

Declared with it: C2 is evaluated at the **ZCS instant** (the `sk` convention). Under the
`lsw` convention (`t_open + 7 ps`) **every row in this study fails C2, including the
committed DELVTO = 0 optimum itself** (`VA = +0.293 V`), which the committed campaign
reports as functional — so that convention cannot serve as an absolute gate here. The
committed record already flags the two as 2.2x-6.9x apart and the later one as reading a
post-open RING rather than a drained rail. Every row's source bank is drained to
`|VAEND| < 0.3 mV` by the end of its tail. **The level times do not depend on the choice;
the location of L\* does.**

---

## A6 — E2 and E3 SCORED AGAINST THE MEASUREMENT: one mechanism confirmed but mis-attributed, one magnitude refuted

**E2 (the chain gets worse as |Vtp| falls): the DC mechanism is CONFIRMED, the
CONCLUSION is REFUTED.**

- CONFIRMED as DC physics: the stranded HIGH tracks `|Vtp|` at **0.81 : 1** MEASURED, and
  the receiver's trip point at the delivered rail moves **-0.485 V per volt of pMOS
  DELVTO** and **+0.463 V per volt of nMOS DELVTO**. So the DC inequality
  `strand - trip` is OPENED by lowering `|Vtp|` (-58.8 mV -> -445.4 mV at P(-0.30)) and
  CLOSED by lowering `Vtn` (it turns POSITIVE at N(-0.15), +10.9 mV).
- REFUTED as the binding term: the MEASURED 6-bank chain gets **better**, not worse, when
  `|Vtp|` falls. Depth passed goes 1 -> 2 -> 3 -> 4 as the shift deepens, and the single
  best row is the one with BOTH thresholds at their lowest. The reason is visible in the
  same data: the chain's rails collapse to 0.58 / 0.32 / 0.19 / 0.12 V, and at rails that
  low the limiter is the successor's own **pMOS PULL-UP**, which a lower `|Vtp|` repairs
  directly. The strand-vs-trip inequality is real but it is not what the chain is dying of.

**I had the right physics attached to the wrong term, and I say so rather than quoting
the half that came out right.**

**E3 (leakage/droop crossover around 0.20-0.30 V): DIRECTION AND SLOPE CONFIRMED,
MAGNITUDE REFUTED.** Static hold current rises **4544x** at **82 mV/decade** (I predicted
80-100 mV/decade), but from a base so small that the held-rail droop over a 120 ps beat
reaches only **1.26 mV (measured) / 4.26 mV (DC-implied)** at the most aggressive point,
against a 754 mV rail. I predicted >100 mV. **The cure does not cost more than the disease
anywhere in the swept space**, and that is a result in QAL's favour that I did not expect.

**E4 (the 2-high stack gains more): CONFIRMED.** x0.550 against the inverter bank's x0.820
at the same shift. It does not change the class (4.77x a same-DELVTO, same-load CMOS
level), so the shallow-stack library restriction stands.

**E0 (no single threshold satisfies both Q1 and Q2): REFUTED IN ITS STATED FORM.** The
two do not pull in opposite directions in the measured system — the deepest shift is the
best answer for both. What survives is the different, harder statement in RESULTS.json:
the chain's wall is not a threshold at all, it is a rail-collapse ratio.

---

## A7 — the chain grid is 8 of the 16 points, chosen before the data and stated here

The 6-bank chain deck costs ~15 min/point (6 sequential ZCS probes + the row). Eight
points were run: `d000` (the reproduction), `d150B`, `d200N`, `d200P`, `d200B`, `d300N`,
`d300P`, `d300B` — i.e. the DELVTO = 0 control plus the -0.20 and -0.30 rows in all three
modes plus one -0.15 bracket. The full 16-point grid IS covered for the DC mechanism, Q1
and Q3. No chain point was dropped after being run.

---

## A8 — raw `.prn` waveforms are stored GZIPPED

Every `.prn` over 1 MB in this directory is gzipped in place (`*.prn.gz`). Nothing is
deleted: every deck (`*.cir`), every `.mt0`, every extracted row (`rowd/*.json`) and every
raw waveform is on disk. The host filesystem was at 95% when this ran and the
uncompressed set is 1.3 GB. `gunzip -k <file>.prn.gz` restores byte-identical input for
any of the extractors, all of which read plain text.
