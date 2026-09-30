# Amendments to `qal/cipher/PRE_REGISTERED.json`

`sha256 81c1d78f0f71d5a92ee5cc3a6c007c53ecc52a1b35057ce2a3b5af06a5672166`,
17 419 B, written 2026-09-29 19:40:00 −0700, hashed 19:40:04.

Every amendment records the measurement that forced it and the mtime proving it
preceded the rows it affects. Nothing in any committed `qal/` directory was
written to; `qal/widebank/` was not touched.

---

## A1 — probe window widened, because the RETURN hop outran it (19:58 → 20:03)

**What was wrong.** The committed probe window is
`tend = t_close + 2.6 · TZ_ANCH · sqrt(L/15 nH)` = 170.3 ps. With a wire load the
return hop is longer than that, and the sequential probe aborted:

    probe ret2 ran p_signal_fixed_cw2400_..._ret2.cir in 41.7s
    probe ret2 NO ZERO

for both `signal/fixed` and `signal/matched`. (The four RISE zeros had already
come out fine — 124.9 / 127.2 / 124.5 / 126.2 ps.)

**The fix.** `probe_span` is a parameter of `btw.deck`, defaulting to the
committed 2.6, and every configuration in this run — **including the `cw = 0`
control** — is probed at 3.6 (235.8 ps), so one protocol produced every number.
The already-probed configurations were re-probed and compared: the rise zeros
came out **byte-identical** (`signal/fixed` rise2 = 127.1601 ps both times), which
is the check that mattered, because a wider window can only change a zero if a
LATER, LARGER current excursion exists — which would itself be a ringing
pathology worth reporting, and there is none.

**Independent check that the widening is benign**: the `cw = 0` control probed at
`T = 150` with span 3.6 gives `tzr = 124.569 / 126.550 / 124.117 / 125.345 ps`
against the committed `T = 120`-probed `124.569 / 126.493 / 124.182 / 125.392`.
The largest difference is 0.075 ps and it is the schedule-matching (banktank A7),
not the window.

## A2 — the return zeros needed a fixed-point iteration to clear gate G2

**The measurement.** With the committed SEQUENTIAL protocol every row's RISE
zeros were clean (`|I(L)| ≤ 0.01 µA` at all four commanded opens, all nine
configurations) but the RETURN zeros missed on banks 2 and 3 — up to
`IZQ2 = +8.63 µA` at `Cw = 3.489 fF`. Pre-registered gate G2 is `≤ 1.0 µA`, so
those rows were **instrument failures, not results**.

**The mechanism, identified rather than assumed.** The probe measures bank *k*'s
return zero with banks 1…*k*−1 returning at their own zeros and banks *k*+1…4
**idle**. In the row every bank returns, and with a wire load the return hop
(156–199 ps) is longer than the 150 ps beat, so bank *k*'s return is still in
progress when bank *k*+1's starts. This is the same class of error banktank A7
found for the rise. Bank 1 — whose gate inputs are ideal DC sources — stayed at
0.01 µA in every configuration, which localises it exactly.

**Physical size, so it is neither over- nor under-sold.** 8.63 µA against a return
peak of 94.8 µA strands `½ L I² = 0.00056 fJ` in the inductor: 2.4 × 10⁻⁶ of a
237 fJ row.

**The fix (`btk/iterate.py`).** The ROW'S OWN waveform is read, the true zero of
every `I(L_k)` is found **inside that bank's own conduction window**, a corrected
zeros file is written, and the row is re-run. The row's own waveform *is* the row
environment, so this is a fixed point, not a different protocol.

**Result.** All nine rows now pass G2. The measured shifts are −0.16 to −4.79 ps,
all on banks 2 and 3, exactly where the overlap is. **The headline energies moved
by less than 0.01 fJ** — `180.508 → 180.511`, `220.037 → 220.030`,
`206.457 → 206.462` fJ — i.e. 3 × 10⁻⁵ relative, and the fcrit S3 scores are
identical to the digit. The instrument gate is cleared *and* the headline is
demonstrated insensitive to it.

### A2a — self-correction inside the fix

My first `iterate.py` searched `[r_k, r_k + 1.6·tzq_k]`, which runs PAST the
commanded open. After the open the transfer gate is off and the tank-referenced
park has shorted `L` into the tank, so `I(L)` is a **park-loop** current; the
search returned a park-loop zero **+83.06 ps** late on banks 2 and 4. A +83 ps
"correction" to a 185 ps hop is not a plausible measurement, and that is what
exposed it. The window is now `[r_k, ro_k + 0.5 ps]` — the transfer zero can only
be inside the conduction window, and a residual of +6.4 µA *at* `ro_k` means the
crossing is just before it, which is what has to be found.

## A3 — my first micro-harness was mis-scaled; it is superseded, not used

`btk/micro.py` built the decisive comparison from **ONE** cell against the
committed `tg15p` transfer switch, which is sized for **eight** (wn = 10 µm /
wp = 20 µm / park = 2 µm driving a 4.50 fF load instead of a 35.98 fF one). The
switch's own parasitic capacitance then dominates the load: the delivered rail
collapsed to **0.78 V** against the chain's 1.18 V, and the incremental wire term
was diluted by a harness artefact rather than by physics.

Those two rows ran and are kept on disk under `btk/superseded_1cell/` rather than
deleted. **No ratio in this run comes from them.** `btk/micro8.py` is the
corrected harness: the full committed 8-cell bank, one hop, with the committed
switch driving the load it was sized for (delivered rail 1.2106 V, against the
chain's bank-1 peak of 1.1851 V).

## A4 — context the committed topology imposes, recorded because it bounds every
## per-cycle number here

The committed banktank deck is **single-shot**: `.ic` starts every rail at 0 V,
the rail is raised, held, and returned once, and the run ends. Measured, the rail
does **not** come back to 0: it ends at **0.724 / 0.750 / 0.773 / 0.769 V** in the
control row (peak 1.185 / 1.116 / 1.179 / 1.155 V), because the committed return
recovers only 17–25 % of what the rise delivered.

Consequence, stated rather than hidden: every energy in this run is a
**first-cycle** energy. A steady-state QAL cycle in this topology would start each
rail at ~0.75 V, so either the logic swing collapses to ~0.45 V or the rail must be
drained between cycles at a cost this deck family does not measure. That is a
property of the committed configuration, not of this study, and the brief's
instruction was to use only what is known to work — so it is reported, not fixed.

It does not weaken the comparison, because the comparison is a **difference**
between two decks that share it exactly, and because the CMOS comparator's node
makes exactly one full 0 → V → 0 excursion in the same window. It does bound the
interpretation, and the stranded-charge bracket (§ "TWO BOUNDS") is how.

## A5 — one "best case" bound is unbounded and is reported as such, not as a number

The stranded-charge credit `dE_QAL − E_wire_stranded_end` is meant as an upper
bound on QAL's advantage (the case where a node that stays HIGH keeps its charge
into the next cycle). For `rail/fixed/cw2.400` the credit (9.988 fJ) **exceeds**
the measured incremental cost (9.618 fJ), because with the wire on the resonant
node the rail's own end voltage also shifts and the credit formula attributes all
of the end-state charge to the wire. Rather than quote a negative or enormous
ratio, that cell is reported as **"unbounded"**, and the PRIMARY figure everywhere
is the no-credit one, which is fully convention-free and favours CMOS.
