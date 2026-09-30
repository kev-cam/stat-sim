# qal/upsize — amendments to PRE_REGISTERED_PHASE2.json

`PRE_REGISTERED_PHASE2.json` sha256
`621f7289e7c2f7edf00e995d8bd92ab6af9f3cb7fcb29acf74952ce5cb340143`, 23166 B,
mtime **2026-09-29 21:45:42.842902396 -0700** — written after
`DISK_STATE_BEFORE.txt` (21:42:33) and before any `.cir` existed in this
directory.

Each amendment records what forced it and when. Nothing in the pre-registration
is edited.

---

## A0 — the beat rule in the brief is not the rule Phase 1 actually used

**When:** 21:5x, before the first sweep deck, while writing `do_point`.

The brief states the beat rule as `T(N) = ceil10(t_zcs + 73.5)`. Taken literally
with the **measured** `t_zcs` this does not reproduce Phase 1's accepted series:
it would give T = 210/240/290/370/490/630 against Phase 1's actual
160/260/330/440/580/790.

Reverse-engineering the accepted series shows the rule is evaluated on the
**ANALYTIC seed** `TZ8·√(N/8)`, not on the measured zero:

| N | Phase 1 T | ceil10(TZ8·√(N/8)+73.5) | ceil10(t_hop_measured+73.5) |
|---|---|---|---|
| 8 | 160 | 200 | 210 |
| 16 | 260 | **260** | 240 |
| 32 | 330 | **330** | 290 |
| 64 | 440 | **440** | 370 |
| 128 | 580 | **580** | 490 |
| 256 | 790 | **790** | 630 |

The seed rule reproduces five of six exactly; N=8's 160 is Phase 1 separately
walking that beat *down* below the seed (its tight-beat exercise).

**What changed:** `up.beat_of()` uses the analytic seed, extended to Phase 2 by
the same √C argument that sets it (`C ~ N·s`, `t ~ √(LC)`), so
`T = ceil10(TZ8·√(N/8)·√s·√(L/15) + 73.5)`. My first draft iterated T from the
measured zero to a fixed point; that was **discarded before any deck ran**
because it would have shifted every Phase 2 beat relative to Phase 1 and made
the s=1 point incomparable with Phase 1's.

**Bonus:** the analytic seed is not a function of the probe, so probing *at* that
T is self-consistent by construction — the circularity that an iterated rule
would have introduced does not arise.

**Consequence, and it is reported not hidden:** T is a *scheduling* choice, so
the trade curve is quoted primarily on the **rule-independent MEASURED floor**
`max(t_hop_rise, t_settle90)`, with T and the measured stage time alongside.

---

## A1 — the conventional-driver ledger row was a ~2× lower bound on its own
terms, because only the RISE hop's gate charge was ever metered

**When:** 22:0x, before the first sweep deck, while reading the inherited ledger.

**What forced it:** Phase 1 measures the switch gate charge at four checkpoints
around the **rise** hop (`P/A/B/C`: pre-close, post-close, pre-open, post-open)
and forms `Q_abs_per_hop = |Q_close| + |Q_open|`. It then charges the
conventional-driver ledger row that single figure. But a full QAL cycle closes
and opens the switch **twice** — once to deliver the rail and once to recover it
— so a conventional (non-recovering) driver pays that charge on **four**
transitions per cycle, not two. Meanwhile `E_tank_loss`, the other term in the
same sum, *is* a per-cycle quantity (`½C(V₀²−V₁²)` across the whole cycle). The
row was therefore mixing a per-hop driver cost with a per-cycle tank cost.

**What was added:** four more checkpoints per device around the **return** hop
(`RP/RA/RB/RC`, mirroring the rise exactly), a
`Q_abs_per_CYCLE = rise(|close|+|open|) + return(|close|+|open|)` per device, and
a new named ledger row **`conventional_FULL_CYCLE_measured_charge`**.

**What did NOT change:** the inherited
`conventional_from_own_measured_charge` row is still computed and reported
unchanged, so every Phase 2 number stays directly comparable with Phase 1's.
Both rows appear at every point and the full-cycle one is labelled as the row a
buildable driver actually pays.

**Ordering and transparency, both verified not asserted:**
- B0a had **already passed** on the unamended generator, and its hashes are
  recorded above and in `INSTRUMENT_CHECK_PHASE2.json`.
- With `UP_NO_RETQG=1` the generator still emits the Phase 1 deck
  **byte-identically** (`4a4c4ace…`), re-checked after the amendment landed.
- The amendment adds exactly **36 lines** to the N=64 deck and **all 36 are
  `.measure tran` statements** (`diff | grep "^>" | grep -vc "^> .measure tran"`
  = 0). `.measure` is passive and cannot change the solution.
- B0b re-runs the amended deck and reproduces Phase 1's row, so transparency is
  measured as well as argued.

---

## A2 — the PyMS cache is keyed on (width, **TYPE**), and it SERIALISES; the
warm was rebuilt as a targeted parallel one

**When:** 22:08–22:12, during the warm, before any sweep deck.

**What forced it — two things, both measured, not argued:**

**(i) a geometry is a (width, TYPE) PAIR.** `PYMS_VAE_CACHE/*.so.params` carries
the *full* PSP103 parameter set, and it includes `TYPE` (`+1` nMOS / `-1` pMOS)
alongside `W`. Dumping all 41 `.params` in the cache and keying on `(W, TYPE)`
shows two distinct hashes per width. Phase 1's `stage_warm` instantiates **both**
types at **every** width, so half its compile bill is spent on pairs the study
never instantiates — 0.74 µm pMOS, 1.12 µm nMOS, 160 µm nMOS and so on. Counting
the pairs the Phase 2 decks *actually* instantiate gives **29 geometries, of
which 15 were already built and 14 were missing** — not the "8 new widths" the
width count suggested. My own earlier progress metric ("new `.so`/8") was
therefore wrong and is withdrawn.

**(ii) PyMS serialises within one cache directory.** Three cell-chain jobs
launched alongside the warm sat at **0.0–0.8 % CPU for over three minutes**, in
`do_wait`, each blocked on its own `build_vae_so.py` child while the warm
compiled an unrelated geometry. This is the cache race Phase 1 warned about,
appearing as benign blocking rather than corruption. Those three jobs were
**killed by PID** (never `pkill -f` inside a compound command — it matches the
shell) and their results discarded.

**Cache integrity after two kills was VERIFIED, not assumed:** every one of the
39 `.so` present is a valid `ELF 64-bit LSB shared object` (`file -b` on each),
so PyMS installs atomically and a killed compile leaves no truncated library.
The three killed/in-flight compiles left `.params` with **no** `.so` and a
1-file `.build` (complete ones have 4), i.e. they are simply absent and get
rebuilt — there is no half-built library that could load and give wrong numbers.

**What replaced it (`warm2.py`):** enumerate the exact `(width, TYPE)` pairs from
`up.py`'s own generators rather than a hand list; build each missing one in its
**own private cache directory** so nothing contends; then merge into the study
cache, **adding only files that do not already exist** so an existing `.so` that
Phase 1 validated is never overwritten. The `.so` filename is the hash of the
parameter set and so is cache-location independent, which is what makes the
merge sound.

**The merge is NOT trusted on that argument alone.** Acceptance **B0b** re-runs
the Phase 1 deck against the merged cache and must reproduce Phase 1's row to
≤0.01 % — that measurement, not the argument, is what licenses the merge.

**Cost recovered:** 14 compiles at ~3.5 min each, 5 at a time ≈ 11 min, against
~46 min sequential for the same 14 (or ~92 min for the both-types 28 the
inherited warm would have done).

---

## A3 — a fourth crux variant (D, QAL-BIAS LOAD) was added

**When:** 22:0x, before any crux deck was kept (the two early s=1 decks run
before the cache merge were DELETED, so no crux result predates this).

**What forced it:** variants A/B/C all power the load stages at the same fixed
rail as the driver. But in the real QAL chain, bank k+1's rail has **not yet
been raised** while bank k settles, so the gate load the measured cell actually
drives is an **unpowered** one — its pMOS sits in accumulation rather than
inversion, and C_gg is correspondingly different. A models the load as powered;
D ties the load stages' rail to 0 V and models it as QAL does.

**Why it does not weaken the crux:** in D the driver and the load still scale
together, so the *scaling* conclusion should be unchanged and only the absolute
settling time should move. That is a prediction, so D is measured rather than
assumed, and it is reported as INFORMATIVE alongside A rather than replacing it.

---

## A4 — a control the pre-registration missed: reducing L is the speed lever
that cell upsizing has to beat, and it must be measured at s=1

**When:** 22:18, while the warm was still running and before any sweep deck.

**What forced it:** an argument I had not closed. Phase 1's data makes
`t_hop = k·√C_bank` with k constant to **4.5 %** over a 32× range of N
(`t_hop/√C_bank` = 12.70, 12.70, 12.80, 13.10, 13.27, 13.19 ps/√fF for
N = 8…256), and the measured exponents agree to 2.6 %: C_bank ~ N^0.831 and
t_hop ~ N^0.426 against the predicted 0.415. So the hop is set by **C_bank —
the cells** — and not by C_tank, which means no tank-sizing or switch-width
choice can escape the √s hop penalty of upsizing. Only **L** can.

That raises the obvious question the pre-registration did not ask: if you want a
shorter hop, why not just **shrink L at s=1** instead of growing the cells?
E3 (s=4, L=15/4) holds t_hop at its s=1 value, so E3 vs the s=1 baseline is the
**iso-speed** comparison. But the stronger test is whether L reduction at s=1
**dominates** upsizing outright.

**What was added — E6:** N=64, **s=1**, L = 3.75 nH, T = 260 ps. Predicted
t_hop = 295.8·√(3.75/15) = 147.9 ps, i.e. **2× faster than the s=1 baseline** at
the same cell size. If E6 is both faster *and* cheaper than E3 (s=4, L=3.75,
predicted t_hop 295.8 ps), then cell upsizing is **strictly dominated** by L
reduction on the speed axis and the exchange rate for upsizing is not merely
poor but irrelevant.

Recorded here so that running it is not a silent addition. It is an EXTENSION
beyond the brief's fixed-L configuration, reported separately and never folded
into the main series.

---

## A5 — the inherited PROBE deck tag omits scale and L, so three Phase 2 points
would have silently overwritten the main series' probe decks

**When:** 22:21, before any sweep deck.

**What forced it:** `do_probe`'s tag is
`"n%d_dv%g_T%g_H%d" % (N, dv*1000, T, H)` plus `wmul` — and nothing else. But
the beat T is a *function* of scale and L, so different configurations land on
the same T and therefore the same `p_*.cir` filenames:

| collision | T |
|---|---|
| main N=64 s=4 vs **E1** (scale 4,4,1) | 790 |
| main N=64 s=8 vs **E4** (half timestep) | 1090 |
| main N=64 s=1 vs **E3** (s=4, L=3.75) | 440 |

`do_probe` re-runs whenever the deck text differs, so the later point would have
**overwritten** the earlier one's probe decks. Harmless for rows already
extracted, a provenance loss on disk, and outright corruption if two such points
ever ran concurrently. Caught by enumerating every probe basename the study will
write and asserting uniqueness, **before** running any of them.

**Fix:** scale, L and the tank override now all enter the probe tag. The
enumeration then gives 72 probe decks over 66 unique names — the only remaining
overlap being main s=8 vs E4, which is **benign and desirable**: their probe
decks are byte-identical by construction (a probe's `.tran` always uses the
default max step), so E4 now **reuses the main s=8 zeros** via a new
`pt.py rowonly` mode instead of re-probing. That makes the max timestep the ONLY
difference between the two rows, which is exactly what B11 is supposed to test,
and saves six redundant simulations.

---

## A6 — MY OWN checker had a float-precision bug, and it cost ~25 minutes of
redundant compiles

**When:** 22:28–22:30, at the merge, before any sweep deck.

**What happened:** `warm2.py merge` reported *"11 files added, 31 already
present ... after merge, MISSING 9"* — self-contradictory, since all 14 builds
had reported OK. The 9 were exactly and only the √2-family widths
(2.82843, 5.65685, 11.3137, 14.1421, 28.2843, 56.5685, 113.137).

**Cause, verified not guessed:** the `.so.params` file stores W to **6
significant figures** (`W=2.82843e-06`). My `present()` keyed on
`round(W_um, 6)`, giving `2.82843`, while `needed()` keyed on the generator's
full-precision `2.8284271247461903` → `2.828427`. Those are different dict keys,
so **every non-round width was reported MISSING even when its `.so` was already
in the cache**. Re-checking with a `1e-5` relative tolerance: **29 needed
geometries, 29 present, 0 missing.**

**Consequence, stated plainly:** the original plan's "14 missing" was inflated by
this bug. At least 9 of the 14 compiles I ran were rebuilding libraries the cache
already held — roughly **25 minutes of wasted wall time**. No result is affected:
the merge's never-overwrite rule meant the pre-existing, Phase-1-validated `.so`
files stayed in place, and the redundant private copies were simply skipped.

**A second thing the merge taught me, and I had it wrong:** I justified the merge
by saying "the `.so` filename IS the hash of the parameter set, so it is
cache-location independent". The *filename* is indeed content-addressed on the
parameter set — the `.params` files for a given hash are **byte-identical** across
two independent caches, which I checked. But the **compiled `.so` for that hash
is not reproducible**: the same hash came out **384888 / 388984 / 393080 bytes**
in different caches, one 4 KiB page apart, because the build path is embedded in
the object. So "same name" does **not** mean "same bytes", and a merge must never
overwrite. This one never does. Both the docstring and `present()` are corrected.

**What actually licenses the cache:** not either argument, but **B0b** — re-running
the Phase 1 deck against the merged cache and reproducing Phase 1's row.

---

## A7 — MY extractor used the SCORED bank's C_tank for every bank, which failed
A6 on the E1 control for a purely bookkeeping reason

**When:** 23:20, after E1 landed and before the analysis.

**What happened:** E1 (per-bank scale 4,4,1) came back **ACC=False** on **A6
(tank closure)** while A1, A2, A4 and A5 all passed. The residuals localise it
immediately: bank 1 −0.42 fJ on 699.6 (−0.06 %), bank 2 −0.30 fJ on 691.0
(−0.04 %), **bank 3 −611.0 fJ on 853.4 (−71.6 %)**.

**Cause:** `row_extract` computed one `ct = m·cbank(N, scale_of_scored_bank)`
and used it for **every** bank's `tank_energy_lost = ½·ct·(V₀²−V₁²)`. The *deck*
correctly sizes bank k's tank from **bank k's own** scale, so under E1 bank 3's
real tank is **2878.3 fF** while the extractor scored it against **11513.3 fF** —
4× too large. Harmless for every uniform-scale row (all banks equal), wrong only
where the scale differs per bank, i.e. only for E1.

**Fix:** a per-bank `ct_k`, plus a new reported field `C_tank_this_bank_fF` so
the value used is visible in every row rather than implied.

**The scored bank was never affected**, so E1's energy numbers did not move.
After the fix E1 is **ACCEPTED** (A6 passes) with E/gate 10.7310 fJ unchanged.

**Verified as a no-op everywhere else, by measurement not argument:** all 11 rows
were re-extracted from their existing `.prn`/`.mt0` (no re-simulation) and
**B0b still PASSES 30/30 against Phase 1 at worst relative error 0.000e+00**. The
row files' bytes did change, and the diff is exactly three **added** keys
(`C_tank_this_bank_fF`, `Q_gate_abs_total_per_CYCLE_fC`,
`Q_gate_return_over_rise_ratio`) with none removed and no value altered.

---

## A8 — a hypothesis I formed about E6 and then FALSIFIED with my own data

**When:** 23:18, while checking whether E6 could be quoted as a positive result.

E6 (N=64, s=1, L=3.75 nH) came back with a **negative recycle fraction
(−11.8 %)** and a rail that **droops** from 0.8469 V at its own ZCS to 0.7405 V
at its sampling boundary (−106.4 mV), against the baseline's *rise* of +29.2 mV.

**My hypothesis:** E6 is SETTLE-bound (slack −26.45 ps), so the cells are still
drawing charge when the switch cuts and they finish the job by pulling it off
the now-floating rail — hence droop, hence a rail below the tank, hence a return
hop that pushes charge the wrong way.

**FALSIFIED.** Tested on all 10 rows: every one of the 8 HOP-bound rows rises
(+19.7 to +69.3 mV) as the hypothesis requires, but the study's *other*
settle-bound row — **N=8 s=1, slack −24.17 ps, an almost identical deficit** —
**rises +17.7 mV with a healthy +17.3 % recycle**. Settle-bound does not imply
droop.

What distinguishes E6 is its **inductance**, not its slack: it is the only row at
L = 3.75 nH, its I_pk is 4951 µA (1.85× the baseline at the same bank), its
Q = (1/R)·√(L/C) is halved with R_S pinned at 10 Ω, and its parked L–R–park
ring-down time constant 2L/R falls from 3 ns to 0.75 ns, so far more of the
parked energy dissipates inside a beat.

**Consequence for what I may claim:** E6 is **not** a clean positive result. It
is accepted on every criterion (A1 0/192 failures, A2 +283.5 mV, A4/A5/A6 pass)
and it really is 1.94× faster on the measured level floor for +15.6 % energy —
but its delivered rail is 21 % lower and its charge recovery has gone **negative**,
i.e. it has stopped being adiabatic. Priced at iso-swing (energy ∝ V², a DERIVED
correction) it costs ≈7.7 fJ/gate, so the 1.94× speed is bought at ≈1.9× the
energy: roughly a 1:1 exchange. That is reported as a bound, with the mechanism,
and never as "1.94× faster for 15.6 % more".
