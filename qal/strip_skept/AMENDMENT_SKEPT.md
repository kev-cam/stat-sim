# SKEPT run: amendments, corrections and declared limitations

Pre-registration: `PRE_REGISTERED_SKEPT.json`
sha256 `e4b115d711b46cec152ac92c602229426c71240c7b1b52b474b060f1a67989eb`
mtime  `2026-09-29 15:27:34.482572546 -0700`, size 12545 B.
It was the ONLY file in this directory at that instant. Earliest `.cir` written
afterwards: `lk_def.cir` / `lk_zero.cir` / `lk_real.cir` at 15:38.

Own VAE cache: `/tmp/claude-1001/.../scratchpad/vae_cache_stripskept` (7 geometries).
Own directory: `/usr/local/src/stat-sim/qal/strip_skept`. `vt`/`gmin` NOT touched.
tt corner only. No `.measure` anywhere in the speed path — every settle/speed
number is read off the `.prn` by `ext_settle.py` / `ext_chain.py`.

## S1 — my own pre-registered prediction about the shim was HALF WRONG
I predicted the shim leaves junction leakage PRESENT and OVER-represented, so
the campaign's numbers were not lower bounds. Measurement says: present, yes —
but NOT over-represented, because the default `PD = 1.0e-6 m` is SMALLER than
the campaign-standard pMOS width `1.12e-6 m`, and PSP103 computes the STI-edge
length as `LSD = PD - W` CLIPPED AT ZERO. So the pMOS STI-edge junction term is
entirely absent at the default geometry. Net direction of the error is the one
the brief assumed, for a reason the brief did not state. Recorded as a
half-refutation of S1, not a confirmation.

## A1 — generator bug: format-string arity (caught before any deck ran)
`gen_leak.py` built pMOS device lines with 8 `%s` placeholders and 7 arguments.
Python raised `TypeError` at generation time, so no deck was ever written from
the broken code. Fixed by rewriting all device lines as f-strings.

## A2 — generator bug: gate nets not instance-qualified (caught before any deck ran)
`cellsk.emit_tree` emitted gate node names `A1`, `A1_B`, … with no instance
suffix, so every stripped cell in a multi-cell deck would have shared one
floating global input net. Caught by inspecting the emitted netlist for one
cell before launching. Fixed with `gate_net(lit, inst)`. No measured row used
the broken form — `st_*.cir` was regenerated before its first run.

## A3 — wrong card type for a `.subckt` (caught by Xyce, decks discarded)
`vt.cir`, `rcv.cir` and the first `st_*.cir` instantiated the compat-shim
`.subckt sg13_lv_nmos/pmos` on `M` cards. Xyce correctly rejected this
(364 and 2668 `MSG_ERROR`s, `Unrecognized parameter …`). Those two runs
produced no `.prn` and no number from them is used. Fixed to `X` cards
throughout; device counting switched from counting `M` cards to counting `X`
cards, and `audit_devcount.py` re-verified (13/13 families, 0 mismatches,
counts unchanged).

## A4 — extractor bug: off-by-one in the chain golden (caught by a degenerate reading)
`gen_chain.golden()` returned `banks[0] = HEAD` and the metadata then labelled
depth *k* with `banks[k-1]`, i.e. every depth was scored against its
PREDECESSOR's pattern. Symptom: `meanHI` and `meanLO` both came out at
0.30384 V = exactly rail/2 at every depth of every arm, because each 4-node
group was being averaged over a mixed set. I did NOT accept that reading —
0.3038 V on every node of every arm is not a circuit result. Direct inspection
of `ch_static.cir.prn` showed depth 1 producing `1,0,0,1` from head `0011`,
which is the CORRECT o21ai response, proving the netlist was right and only the
expectation map was wrong. Fixed so `banks[k]` is the output of depth *k*.
**Only metadata changed; the netlists are byte-identical, so the existing
`.prn` files remain valid and nothing was re-simulated.**

## A5 — gmin is a first-order contaminant and it scales with DEVICE COUNT
Every device contributes exactly `1e-12 S` from its node to ground. Proven, not
assumed: a known `1e12` ohm resistor in the same deck reads `rail x 1e-12 A`
exactly at all five rails; the NULL control (2 fF capacitor, nothing attached)
reads `0.00000 pA`; and the keeper arm minus the bare arm equals EXACTLY
`3 x rail x 1e-12 A` at all five rails (3 extra devices), to six decimals.
Consequences, both applied to every leakage number quoted:
 * the bare HIGH node's raw 1.94723 pA at 0.6077 V is 1.21540 pA gmin
   (2 devices) + **0.73183 pA real**;
 * the apparent "keeper costs 1.82 pA" is 100% artefact. With the node held at
   the rail the ON keeper pMOS has `Vds = 0` and therefore carries ZERO
   current. The keeper's real contribution to node leakage is zero, not small.
A leakage figure measured in this harness without subtracting `n_devices x gmin`
is wrong by ~62% on a 2-device node.

## A6 — a degenerate arm, kept and labelled rather than quoted
The "OFF cross-coupled pMOS on a HIGH node" arm has all four terminals at the
rail, so it must read zero real current. It does (gmin only). It is reported as
a DEGENERATE CONTROL establishing that the OFF pull-up contributes nothing to a
HIGH node's droop — not as a measurement of pMOS leakage.

## Declared limitations
1. **No energy number is produced or audited by this run.** Every deck here uses
   an ideal stiff rail, deliberately, to remove the tank-sizing confound. That
   makes settle/floor/propagation results clean and makes energy results
   impossible. The primary's fJ/op figures are neither reproduced nor disputed
   on measurement grounds.
2. **The committed 6-figure tank-fed anchor is NOT reproduced.** The committed
   harness parameters (tank C, probe/ZCS timing, transfer-gate sizing) are not
   fully specified in my brief and I did not read the primary's decks. So my
   acceptance criterion A1 is NOT met and no number of mine is offered as a
   reproduction of `qal/skept` row `o21_dv150`. What I offer instead is a
   fully-specified stiff-rail harness whose two inputs are (rail, input level).
3. `ch_*` runs at ONE rail (0.6077 V) and one wiring pattern.
4. The `REAL` junction arm used the nMOS's PDK geometry (`ad=2.516e-13`,
   `pd=2.16e-6`) for BOTH device types. The PDK's actual pMOS geometry is
   larger (`ad=3.808e-13`, `pd=2.92e-6`); `lk_iso.cir` arm `c` covers it and
   shows it leaks MORE, so the `REAL` arm understates the pMOS junction.
5. Settle windows are 4 ns; the chain window is 8 ns. Rows marked NEVER did not
   reach 90% within those windows and several were still moving at the end.
6. Concurrency held at <= 3 heavy Xyce jobs throughout (polled `/proc/loadavg`
   before each launch batch); peak load observed 11.26 with other workflows'
   jobs included, never more than 3 of mine.
