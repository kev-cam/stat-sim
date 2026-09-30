# Phase 1 protocol amendments and instrument defects found

Pre-registration: `PRE_REGISTERED.json`, sha256 `85de9785eceb6f84277789dad1fa9257758391ae14770db2ad574bfe688396b3`,
written `2026-09-29 11:29:41 -0700`. The only file of this track that predates it is
`stacks.py` (11:27:13) and its output `cells/stack_depths.json` (11:27:17) — both
**static analyses of the PDK netlist**, disclosed as such inside the pre-registration
itself (`what_had_been_read_before_writing_this`). **No SPICE deck of this track
existed** at 11:29:41; the first, `p_g0_o21ai_handbuilt_dv150.cir`, was written 11:31.

---

## C1 — the brief's shallow set is wrong, and the correction was made *before* any measurement

The brief states "Only inv + nand2 + nor2 (13 of 56) are unambiguously shallow."

Read straight out of `sg13g2_stdcell.spice`, **`sg13g2_nor2_1` has a 2-high pMOS
series stack** — `XP0 net1 A VDD VDD` in series with `XP1 Y B net1 VDD`. NOR is the
CMOS dual of NAND, and the dual puts the stack on the p-side, which is the side that
binds on a QAL rail because the pull-up network is what drags the output up as the
rail rises. Symmetrically, **`sg13g2_and2_1` IS shallow** — it is nand2+inv and every
rise path is depth 1.

So the shallow set is `{inv, nand2, and2}` = **11 of 56 instances**, not 13.

This is recorded as `declared_correction_1` in the pre-registration, *with* the
statement that the settling census would confirm or refute it.

## C2 — the brief's o21ai anchor is superseded by a committed result the brief does not cite

The brief calls `sg13g2_o21ai_1` "the exact cell MEASURED to NEVER SETTLE at any
operating point inside the PDK envelope". `qal/dvopt/RESULTS.json` (2026-09-28)
section `f_two_high_stack` **supersedes that**: on an ideal supply the 2-high stack
reaches 99.78–99.99 % of rail at every characterised swing from 0.60 V up, and in a
real bank at dV = 1.65 V it reaches `t_valid90 = 495.5 ps` inside the same 500 ps
window. The committed verdict there is that the failure was **delivery plus a too-short
window, not headroom**, and that the shallow-stack restriction survives on **speed**
(4.4–5.5× the CMOS logic level) rather than on impossibility.

Consequence, pre-registered: the census gates are **split** into correctness (C1 VALUE,
C2 SETTLE) and speed (C3), and a family can come back `MARGINAL`. A census reporting
one PASS/FAIL bit on settling would have re-published the superseded claim.

The brief's own anchor numbers are still reproduced exactly — see G0 below.

---

## R1 — MEASURED TOOL DEFECT: abc refuses a liberty with no buffer cell

`abc -liberty` on a 3-cell `{inv, nand2, and2}` library aborts with

```
ERROR: ABC failed with status B
```

Bisected: the same flow succeeds the moment `sg13g2_buf_1` is added, on both
`{inv,nand2,and2}` and `{inv,nand2}`. `buf_1` is two cascaded inverters; `stacks.py`
gives it `binding_pmos_rise_depth = 1`, so it belongs in the shallow set on the
census's own criterion rather than being a convenience.

**Amended:** every restricted library carries `sg13g2_buf_1`, and `buf` is measured in
the census like every other family (`cells/stack_depths_extra.json`; the
pre-registered `cells/stack_depths.json` stays frozen at the committed netlist's 12).
**No buf cell appears in any produced netlist** — abc needed it present, not used.

## R2 — one abc invocation is not a synthesis result

The default `abc -liberty` script is area-oriented. Reporting only its depth would
have charged the shallow library for a synthesis artefact. Seven abc variants were
run per library (`syn/sweep.py`) and **both Pareto ends are reported**: the minimum-cell
point and the minimum-depth point. The full library was swept identically — its best
depth is still 8, so the ratio is best-effort against best-effort, not best against
default.

## R3 — cell count is the wrong energy proxy, and it flatters the *complaint*

The brief anticipates "substantial growth" in cell count. Measured, the cell count
does grow 2.3–2.6× — but a NAND2 is 4 devices where an XNOR2 is 10 and a MUX2 is 12.
Summing the PDK's own device widths over each netlist (`REMAP_WIDTH.json`), the
shallow remap costs only **1.31–1.38× in total device width** and **1.26–1.32× in
device count**. Reporting the 2.6× cell figure as if it were an energy cost would
have overstated the penalty by about 2×. Both are reported; the width figure is the
one used for the energy consequence.

## R4 — yosys 0.58 cannot read the PDK's own Verilog cell models

Two independent parse failures, both in the PDK, neither in the netlist under test:

1. `sg13g2_udp.v` primitive tables — `ERROR: syntax error, unexpected TOK_ID`.
2. `ifnone` inside the `specify` blocks of `sg13g2_stdcell.v` — `ERROR: syntax error,
   unexpected '('`.

**Fix, recorded:** `verify/cells_min.v` carries the 13 combinational cells with every
function-defining gate primitive **verbatim**, the 13 `specify` blocks stripped (timing
only, no function), and the one UDP-bodied cell (`mux2`, whose body is
`ihp_mux2 (X, A0, A1, S)`) written out as its 2-state function. The **vector** run is
unaffected: `iverilog` reads the **real, unmodified** PDK `sg13g2_stdcell.v` and
`sg13g2_udp.v`, so the 4-state behaviour of the real models is what 155,600 vectors
were checked against.

## R5 — two harness bugs of my own, caught and fixed before any verdict

1. `prep -top gold` **deletes** the other module, so the first miter script died with
   ``ERROR: Module `gate' not found!``. Rebuilt on `design -stash` / `design -copy-from`.
   The failure was a missing module, never a wrong proof.
2. `yosys -q` suppresses the log, so my first pass read an **empty** log and scored a
   *successful* proof as `E1_SAT_MITER False`. Fixed by writing the log with `-l` and
   reading the file. **This one is the dangerous direction only by luck** — it happened
   to fail-closed; the same bug with an inverted test would have reported a green light
   on no evidence.
3. The port-fidelity check used a regex over the source. The RTL declares six names in
   one `input [7:0] a, b, c, e, f, g,`, which the regex truncated to `a`, so E5 read
   `False` on a netlist whose ports are identical. Replaced with a port list read back
   from **yosys itself** (`write_json`).

## R6 — the private VAE cache is a real, measurable cold-start tax

The first deck of this track took **774 s** for a probe whose warm cost is ~50 s,
entirely in `build_vae_so.py` compiling one PSP103 `.so` per distinct device geometry.
A pre-warm deck (`warm.cir`, 16 distinct `(type, w, l)` geometries) was run to move
that tax off the census. Two duplicate `warm.cir` processes appeared and were killed
**by PID**; nothing else on the box was touched.

---

## Declared, unchanged, repeated on every headline

- `sg13lv_compat.sp` **zeroes ad/as/pd/ps**. Junction capacitance is absent from every
  device: every time and every energy here is a **LOWER BOUND** on a real layout.
- The census cells add **one explicit 0.1 fF per internal node**, referenced to the
  nearest supply — without it the zeroed shim leaves pure series nodes with no
  capacitance at all. Same value and convention as the committed `sk.py` o21ai bank.
- The census drives cell inputs at the **pre-charge level dV** from ideal sources, the
  committed convention. `dvopt` measured this to be **pessimistic** for a 2-high stack,
  not generous.
- `LT` is an ideal inductor with a lumped `RS = 10 Ω`. No interconnect, no bank-to-bank
  routing, no inductor self-capacitance. Anything modelled as an ideal source is a
  **BOOKING** and its row is a **BOUND**.
- 1 F integrators carry a t=0 **pedestal**; every integral is t0-referenced. The true
  current zero is **re-probed** per operating point.
- The committed anchor uses a hand-built o21ai at `l = 0.13u`; the PDK cell is
  `l = 0.15u`. Both are run (G0 / G0b) and the delta is reported, not averaged away.
