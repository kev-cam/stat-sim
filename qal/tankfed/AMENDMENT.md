# qal/tankfed — AMENDMENTS to PRE_REGISTERED.json

Pre-registration: `PRE_REGISTERED.json`, sha256 `78fc0ac0c3fec5ae7b4f47b1ddc1a8a207d275a382944be8e20e13b742cc1c73`,
21518 B, mtime **2026-09-29 09:02:10.626 −0700**, the **only file in this directory**
at that instant (`ls -A | wc -l` = 1, recorded in the same command).

Every amendment below is a deviation from that file or a clarification forced by
something measured afterwards. Each says what changed, why, and which direction
it biases the result.

---

## A1 — The chain head's pre-charge switch is scaled, and made of parallel copies

**Committed:** a fixed 1 µm nMOS / 1.12 µm pMOS pair, sized for the 36.6 fF 8-cell
bank of `chain3` (Ron·C ≈ 22 ps, fully charged inside the 160 ps pre-charge window).

**Here:** 5 parallel copies of the 10 µm tg15p nMOS (50 µm total) and 3 parallel
copies of the 20 µm tg15p pMOS (60 µm total), **fixed for every configuration**.

**Why it is forced.** The head node here is a 48-cell bank *plus its tank* — up to
~1.5 pF, ~40× the committed head node. A 1 µm gate has Ron·C ≈ 900 ps against a
160 ps window: it could not hold the head rail at dV at all, and it would hold it
at a *different* level in every tank configuration. That would put a
head-charging artefact inside the very comparison the matrix is supposed to make.
Fixing the head switch at one size for all configurations removes it as a variable.

**Why parallel copies of an existing width rather than one wide device.** PyMS
compiles a separate model shared object **per device width** (measured: the cache
key includes `W=`; each new width is a ~5 min ginac + g++ build). Parallel copies
of the 10 µm and 20 µm devices the deck already needs introduce **no new geometry**.

**Bias.** The head is the boundary of the modelled system — it is fed by the ideal
dV source. Every number that depends on the head rail is a **BOUND** either way.
A stiffer head makes bank 1 start closer to a clean dV, which *flatters* the chain.

## A2 — The beat period T is DERIVED, not inherited

The pre-registration already stated T would be derived from the measured slowest
hop. Recorded here as the concrete value: **T = 340 ps**, chosen before the first
chain deck from the DERIVED worst hop under matched sizing at m = 6
(C_ser ≈ 436 fF, π√(L·C_ser) ≈ 254 ps) with the pre-registered 1.25× margin, and
rounded up. It is held **global across every matrix cell** so the cells are
comparable, and is checked after the fact against the MEASURED zeros. The
committed chain studies ran T = 200 ps on 8-cell banks with no tanks; a tank of
m·C_bank lengthens the hop by √(1+m), so T = 200 ps is not an available choice here.

## A3 — The free control is STRICTER than the committed one

The committed `free` deck instantiates **no top-up device at all** on the topped
banks, while the clamp deck instantiates one **and** fires it. So the committed
"+113.565 mV attributable damage" conflates the top-up **existing** with the
top-up **firing** — and `chain3` measured that merely having the gate present
costs t_zcs +11.5 ps and VBEND2 −43.4 mV, so the conflation is not negligible.

Every free control in this directory carries the top-up devices **physically
present and parked off**, and shares its hop zeros with its own topped row. The
difference is therefore attributable to the firing alone. The committed anchor is
still reproduced on the *committed* convention in `INSTRUMENT.json` (that is what
anchors the instrument); the run's own numbers use the stricter convention. A
`bare` row (no top-up device at all) is run at one configuration to quantify the
presence term separately.

## A4 — Bank size is per-bank, and the profile forces fan-out

`PROFILE = [48, 19, 3, 1, 2]`, every entry drawn from the real sha_slice profile
48/22/19/3/2/4/2/3/1/1. Where a bank is **wider** than its predecessor (bank 5 has
2 gates behind a 1-gate bank 4) the predecessor's output **fans out**: gate *i* of
bank *k* reads `o{k-1}_{i mod M_{k-1}}`. **No buffer, latch or level shifter is
inserted** — the real profile is non-monotonic and a fan-out is what it actually
does. The 1-gate bank is at depth 4 and the 2-gate bank at depth 5 so that
intra-level HIGH/LOW separation stays **defined** at depth 5; a 1-gate level has
no intra-level separation by construction, and that is a property of the profile,
not of this deck.

## A5 — What "tank" means electrically, stated so it cannot drift

`CTK_k` from `ntk_k` to ground, plus `RTK_k` = **2 Ω** from `ntk_k` to `rail_k`.
No cell's supply, bulk, gate or output touches `ntk_k` — it is not a signal-path
node. The tank is therefore **inside the hop's resonant path** (through the strap),
which is exactly why `t_hop = π√(L·C_ser)` scales as √(C_bank) under matched
sizing, as the brief states. The 2 Ω strap is **ASSUMED** and deliberately small,
so that the strap is not doing the attenuation work by itself; if the coupling
verdict turned on it, the result would be about the strap and not about the tank.

## A6 — PROCESS NOTE: three jobs racing the PyMS cache were killed and restarted

At 09:13 three of this run's decks were launched concurrently before the model
shared objects were warm. Each Xyce process then tried to build the same
geometries, the box (shared with three other workflows, load 22, 38 GB of swap in
use) went to ~0.1 % CPU per process, and nothing completed. The jobs were killed
**by PID** (never `pkill -f`, which self-matches the killing command — the record
already root-caused that), a single `warm.cir` touching all seven geometries
(nMOS 0.74/2/5/10 µm, pMOS 1.12/10/20 µm) was run sequentially, and the sweep
restarted afterwards. No results were taken from the killed jobs.

## A7 — Anticipated, and recorded BEFORE it is measured: resonant step-up

Under **matched** sizing the hop's source and destination capacitances stand in
the ratio of the bank sizes, and a lossless resonant half-cycle delivers
`V_dst = 2·V_src·C_src/(C_src + C_dst)`. For the profile's first hop (48 → 19)
that factor is **1.43**, i.e. a delivered rail *above* dV, and above the 1.5 V
transfer-gate drive at dV = 1.2. The transfer gate will then partially turn
itself off, and the destination-side pMOS (bulk on `vhi` = 1.5 V) can forward-bias.
I record this **before** the first matrix deck so that, if it appears, it is read
as the mechanism it is — a consequence of matched tanks on a *shrinking* profile —
and not explained away afterwards; and so that any row where a rail exceeds
1.5 V is flagged as **outside the device envelope** rather than quoted.

This also flags a loose sentence in my own pre-registered E4. I wrote that under
`C_tank_k = m·C_bank_k` "the delivered rail should be size-INDEPENDENT". The
transfer ratio is independent of **m** and of the overall scale, but it is *not*
independent of the **ratio** `M_k / M_{k+1}`, which the sha_slice profile makes
wildly non-uniform. A **uniform** tank large enough to dominate drives every hop's
ratio toward 1 and would therefore equalise the delivered rail *better*. E4 as
pre-registered may well be refuted by its own mechanism; the measurement decides,
and the pre-registered text stands as written.

## A8 — The probe window had to be lengthened (and why that is a result, not a fudge)

The committed hop-ZCS probe runs to `close + 6*t_est` with `t_est` the committed
65.5 ps anchor. A matched tank raises C_ser until the loop approaches critical
damping, and a damped half-period `pi/omega_d` diverges as Q → 1/2. The window is
now `max(6*t_est, 5*pi*sqrt(L*C_ser))` from the configuration's own DERIVED hop.
Re-probed at 1213.6 ps, the matched-m=6 hop 1 **still has no current zero**: it
ends with rail1 = rail2 = 0.83178 V, a completed resistive charge-share.

## A9 — The coupling victim's boundary precedes the top-up in the ADJACENT schedule

The committed +113.565 mV anchor is measured in the skiptu **s4 = SKIP** schedule
(hops 1→3, 2→4): bank 3 is charged at 200 ps, its clamp fires 305.7–327.7 ps, and
bank 2 — which feeds it — is read at 399 ps, *after* the fire. This chain uses the
**ADJACENT** schedule, where the feeding stage's own boundary necessarily precedes
the fed bank's top-up (bank 2's boundary 538 ps, bank 3's top-up 761 ps). The
settled lift at the feeder's own boundary is therefore **structurally zero here**
and is reported as structural, not as "no damage". The physical coupling is
reported instead as the **time-domain divergence** on the feeder's outputs over the
top-up window, and as the settled **self-lift** of the topped bank's own pull-down
outputs — both measured after the fire.

## A10 — Depth-5 separation is DEGENERATE BY CONSTRUCTION in this profile

Bank 4 has one gate, bank 5 has two, and bank 5's two gates both read `o4_0`
through the fan-out. They therefore have identical inputs and compute identical
values: min(HIGH) − max(LOW) is exactly 0.0000 mV in every row, which is a
property of the netlist, not of the physics. **No depth-5 separation number from
this deck may be quoted.** The deepest bank with a meaningful intra-level
separation is bank 3. A9/A10 together mean the pre-registered A3 (separation ≥
6.44 mV at depth ≥ 5) is **NOT TESTABLE** on this profile; what replaces it is the
per-gate value check and pattern guard, which are defined at every depth.

## A11 — The CLAMP rows are not instrument-clean on hops 3 and 4

Every free row passes the A6 gate (|IZ| ≤ 0.034 µA on all four hops). Every clamp
row FAILS it on hops 3 and 4 (37.3–157.1 µA), because those hops' zeros were
probed with the top-up devices present but parked off, and a live top-up changes
the rail the next hop starts from. Bank 3's charging hop is hop 2, which IS clean
in every row (≤ 0.008 µA), so the headline coupling measurement is unaffected; the
bank-4 and bank-5 rails in the clamp rows carry this caveat and are reported with it.
