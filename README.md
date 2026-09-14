# stat-sim

A **standalone tool that generates Verilog-AMS models** carrying *silicon
variability*, aimed at **finding clock-domain-crossing (CDC) bugs** by
simulation rather than by structural lint alone.

The premise: a CDC bug is a *metastability* event. When a signal launched in
clock domain A is sampled by a flip-flop in domain B whose clock is
asynchronous, the data edge can land inside B's setup/hold aperture. B's flop
then goes **metastable** — its output sits at an invalid mid-rail level and
resolves to a real logic value only after a *random* settling time with an
exponential tail. A bug is any place a design samples or fans out that
not-yet-resolved level. Structural CDC checkers find *missing synchronizers*;
stat-sim finds what actually *propagates*, with a quantified failure rate
(MTBF), by putting a physically-characterized metastable model into the sim.

This implements **US8478576B1** "Including Variability in Simulation of Logic
Circuits" (D. K. Cameron) — the *probability-waveform* method — with
**US20230334213A1** (analog/MS defect binning) as a later layer for binning
synchronizer failure modes.

## The metastability model

For a flop with resolution time constant `tau` and aperture constant `T0`,
sampling a data edge `f_d` against a clock `f_c` with settling slack `t_r`:

```
P(still metastable after t)   = exp(-t / tau)
rate of entering metastability = T0 * f_c * f_d
MTBF(t_r)                      = exp(t_r / tau) / (T0 * f_c * f_d)
```

`tau` and `T0` are *not* guessed — they are extracted per-cell, per-corner from
transistor-level Monte Carlo on a real PDK (sky130 today; its `mc_pr_switch` /
`mc_mm_switch` AGAUSS process+mismatch models). The generated Verilog-AMS model
reproduces that behavior: on a setup/hold violation the output enters a mid-rail
plateau for a duration drawn from `Exp(tau)`, then resolves. Aggregated over
Monte Carlo trials, that executable model *is* the patent's probability
waveform `P(out = 1, t)`.

## This is an extension of bfit's standard-cell fitter

stat-sim is **not** a from-scratch generator — it is the *sequential-cell +
metastability* extension of bfit's existing standard-cell model fitter
(`/usr/local/src/sv2ghdl/bfit`), which replaces SPICE-level cells with portable
Verilog-AMS models. What bfit already does and what stat-sim adds:

| stage | bfit today | stat-sim adds |
|-------|-----------|---------------|
| parse cell | `tools/stdcell2bfit.py` parses the cell, classifies FET polarity, fits `ron/gmin/cin` via the ATPG+MC flow | reuse as-is |
| **combinational** cells | per-FET gate-programmed conductances → behavioral `.subckt`/`.vams` (49 sg13g2 cells validated) | — |
| **sequential** cells | **flagged "not valid as-is"** — pull-net model misses feedback/state; roadmap item: *"emit a latch/FF behavioral primitive"* | **this is the gap stat-sim fills** |
| storage element | `merge.recognize_xcoupled()` finds the cross-coupled regenerative pair (`A.gate==B.out && B.gate==A.out` — SRAM latch / sense-amp / FF core) and folds its feedback into one coupled Jacobian | characterize that pair's **regeneration time constant = metastability τ** |
| model output | deterministic macromodel, per-corner cached | **probabilistic** metastable DFF + synchronizer (`genmodel.py`) |
| application | speedup (≈7–24× per engine) | **find CDC bugs** with quantified MTBF |

The insight: the cross-coupled pair bfit's `merge.py` already isolates *is* the
metastable element. Its small-signal regeneration time constant near the
balance point (the inverse of the positive real eigenvalue of the linearized
qa↔qb loop) is exactly the `tau` in `P(metastable after t)=exp(−t/τ)`. So we
extend the same pipeline one stage further instead of building anew.

## Pipeline

```
            ┌─────────────┐     ┌──────────────┐     ┌───────────────┐
 PDK cell ─►│ characterize│ ──► │   genmodel   │ ──► │     check     │──► CDC bugs
 (sky130)   │ MC τ,T0,    │ τ,T0│ emit .vams   │.vams│ compose prob- │    + MTBF
            │ tsu,th,tcq  │ ... │ metastable   │     │ waveforms,    │
   ▲        │ from xc pair│     │ DFF + sync2  │     │ find bad      │
   │        └──────┬──────┘     └──────────────┘     │ samples       │
 merge.recognize_  │                                 └───────────────┘
 xcoupled()  shim layer (bfit SimDriver):
             qspice / ltspice / spectre / xyce / ngspice+OpenVAF
```

- **`characterize`** — takes the regenerative pair from
  `merge.recognize_xcoupled()`, drives it through bfit's `SimDriver`/shim layer,
  and extracts `tau, T0, tsetup, thold, tcq` across MC corners. *(interface +
  extraction method defined in `characterize.py`; the bisect-to-balance-point MC
  loop is the next increment.)*
- **`genmodel`** — **the headline deliverable.** Emits a parameterized
  Verilog-AMS metastable D-flop and a 2-stage synchronizer from a `CellSpec`.
  This *is* the "latch/FF behavioral primitive" bfit's roadmap calls for, plus
  metastability. *Working now* — see `genmodel.py`.
- **`check`** — the **CDC trap**: at every latch/flop **clock transition** (the
  sampling instant) it tests whether the data node is at a clean rail. A value in
  the invalid band `(vlo, vhi)` — neither a clean 0 nor 1 — is a captured
  metastability / CDC hazard. The trap accumulates the empirical probability over
  the run; aggregated over Monte Carlo seeds, `p_bad` is the failure probability,
  and with the sampling rate it gives the MTBF. This is the US8478576B1
  probability-waveform overlap evaluated at the clock. The metastable DFF's
  mid-rail plateau during its unresolved window is exactly what the trap catches.
  Generated now as `<name>_cdc_trap.vams`; the DUT-instrumentation + MC-aggregation
  driver targets the Xyce+nvc / PyMS cosim path (next increment).

### The trap, precisely

```
at each cross(V(clk) - vth):          // clock in transition on a sampled latch
    if  vlo < V(data) < vhi:          // not exactly 0 or 1
        bad++                         // a CDC hazard fired
p_bad = bad / samples                 // -> failure probability over MC seeds
```

## Runtime: PWL event-driven in nvc (not analog)

The models are **authored in Verilog-AMS** (portable, the spec), but they **run
event-driven under nvc** — no analog solver. The vehicle already exists in the
tree: `sv2vhdl.logic3da` (`resolved_logic3da`), the Thevenin
`(voltage, resistance, flags)` record used by
`xyce/utils/simetrix_vhdl/xspice_digital.vhd`. A `logic3da` signal carries a
*real voltage*, so a net can legitimately sit in the **invalid band (mid-rail)**
during metastability while everything stays discrete VHDL events.

Two things make the metastable flop pure-event-driven (`nvcgen.py`):

- **PWL plateau-then-resolve is one multi-transaction assignment** —
  `q <= mid_rail after TCQ, resolved after TCQ + TMETA;` schedules the invalid
  plateau and its resolution as two events. No integration.
- **Setup/hold aperture is the `d'last_event` attribute** — a violation is just
  "data changed within `TSETUP` of the sampling clock edge."

This is the *same* nvc digital runtime as `simetrix_cosim`, but run **stand-alone
without the Xyce analog master** — fast enough for whole-chip CDC.

### Multi-UDN node: the bidirectional conjugate `prob_load` discipline

nvc's multi-UDN (user-defined-nature) resolution lets **one node carry and
resolve several disciplines at once**. stat-sim defines its own — a **bond-graph
0-junction** carrying a conjugate pair, `prob_load` in `lib/statsim_disc.vhd`
(Python reference + validator: `disc.py`, kept numerically lock-step):

| field | direction | meaning |
|-------|-----------|---------|
| `p0` / `p1` | forward (effort) | P(node is a clean logic 0 / 1) |
| `px` | forward | **P(node at an invalid / metastable level)** — `p0+p1+px=1` |
| `gdrv` | forward | drive conductance `1/R_drive` (S); weights the vote; `0` = pure load |
| `cload` | **backward (flow)** | capacitance this port presents back (F); resolves additively |
| `rwire` | backward | lumped series wire R (ohm) |

This mirrors `logic3da`'s Thevenin `(voltage, resistance)` record and lifts it to
the probability simplex: the **forward** signal is the logic probability a gate
drives; the **backward** signal is the capacitance-like load the fan-out + wiring
present back. `px` is the CDC-trap quantity ("probability the value is not 0 or
1") carried natively — the US8478576B1 probability waveform.

**Resolution (one pass):** forward = `gdrv`-weighted mix of the active drivers'
simplices + a `2·p0·p1` contention term (two drivers fighting 0-vs-1 push
probability into `px` — contention → metastable); backward = additive sums
`C=Σcload`, `Rw=Σrwire`, `G=Σgdrv` over *all* taps (parallel caps add →
`R_out=1/G`, exactly logic3da). No algebraic loop: the backward load is
topology-static and only feeds a scheduled delay.

On a shared node nvc resolves `prob_load` together with **`electrical` (V/I)** and
**`logic3da` (3D-logic)** via the bridges (`from_electrical`, `from_logic3da`,
`to_electrical`) — flop output, analog net, and digital net meet on one node with
**no explicit A2D/D2A**.

### On-the-fly delay (SPEF as load, not a constant)

Propagation delay is **computed at event time** from the resolved backward load,
not baked into the netlist:

```
t_pd = TCQ0 + ln2·(R_DRIVE + node.rwire)·node.cload      # 50% delay
t_slew =      ln9·(R_DRIVE + node.rwire)·node.cload      # 10–90% edge
```

`spef.py` stops collapsing each net to `delay = R·C`. Its primary product is
`net_loads → {net: (c_wire, r_wire)}`; the binder drops one `statsim_pl_wire`
tap + one `statsim_pl_load` per fan-out receiver (`lib/statsim_taps.vhd`) onto the
node, and the resolver sums them so **adding a fan-out raises the delay
automatically** (`C_node = c_wire + Σ Cin`).

**Where the SPEF comes from:** `klayout2spef.py` extracts per-net RC from a real
GDS via KLayout's `LayoutToNetlist` (per-net connectivity) + analytic sky130
geometry R/C, and writes the SPEF that `spef.py` reads — closing the loop from
layout to CDC timing. The extraction recipe mirrors the proven kestrel flow
(`kestrel/layout/{extract,parasitics}.py`); the SPEF writer is verified by
round-tripping through `spef.py` (`klayout2spef.py --self-test`, no KLayout
needed). **Validated end-to-end on a Linux box** (Debian 13, python3.13 venv,
klayout 0.30.9): `klayout2spef.py kestrel/layout/kestrel_pll.gds -o pll.spef`
extracted **247 nets** (top net 67.9 fF / 1.4 kΩ, VCO 34.7 fF, delay-cell/Mtail
1–2 fF), round-tripped through `spef.py`. Needs a klayout wheel —
`python3 -m venv v && v/bin/pip install klayout` on Linux py3.10–3.13 (this dev
box's py3.14 / Cygwin-py3.9 have none). `klayout2spef.py design.gds -o design.spef`. Worked example (SPEF net `sync_d`:
12 fF wire, 350 Ω; R_DRIVE=100 Ω): 3 fan-outs @2 fF → 18 fF → **5.61 ps**; a 4th →
20 fF → **6.24 ps**. The old constant `R·C = 4.2 ps` was fan-out- and drive-blind.

```
 .vams (authored) ──nvcgen──► prob_load .vhd ──┐
 cell Cin + SPEF (R,C) ──────► pl_load/pl_wire ─┼─► nvc event-driven run ─► p_bad / MTBF
                              taps on the node ─┘   (delay & traps on real timing)
```

### Cell subtraction (routing-only wiring) and RC-in-path

The full extraction carries R/C for *every* net — including the metal *inside*
each cell. But the behavioral cell models already own their intrinsic Cin/delay,
so the SPEF should contribute only the **inter-cell routing**. Two reusable steps:

- **Subtract the cells** (`klayout2spef.py --routing-only`): a "cell" is any
  circuit that contains devices (or is named in `--model-cells`); its internal
  nets are dropped, the inter-cell routing nets are kept (wire-only by
  construction). The output is a routing-only SPEF **plus a `*CONN` block** (the
  per-net driver/receiver pin map) and a `.json` sidecar. Because the cell/route
  split rides in the SPEF (`*CONN`), the downstream steps are **SPEF-in/SPEF-out
  and tool-agnostic** — they run on any RCX source (OpenRCX, magic, commercial),
  not just klayout. `spef.net_conn()` reads `*CONN`; `spef.parse()`/`net_loads()`
  ignore it, so RC parsing is unchanged.

- **Pull the R-C into the path** (`statsim_pl_rc`, `lib/statsim_taps.vhd`): a
  2-port element straddling a near node `a` (driver) and far node `b`
  (receivers). The **receiver sees the RC-delayed forward probability**
  (`transport` after `ln2·R·(α·C+ΣCin)`, α=0.5 Elmore / 1.0 legacy anchor; px
  passes through) while the **driver sees C+ΣCin as backward load**. `resolve_pl`
  and the generated DFF are *unchanged* — the wire R simply moves off the driver
  node into the element. No algebraic loop: the forward (delayed) and backward
  (static load) channels are orthogonal. `spef.taps_for_net(..., mode="rc")`
  emits the binding. Measured: driver→receiver flight of exactly **2911 fs** for a
  12 fF/350 Ω net (`test/statsim_rc_tb.vhd`); the CDC latch still flags
  metastability with a wire on the data path (`test/cdc_latch_wire_tb.vhd`).

**Verified end-to-end under nvc:** `disc.py` ↔ `lib/statsim_disc.vhd` run
numerically identical (`test/statsim_disc_tb.vhd`: px=0.5, gdrv=0.02, cload=18 fF,
t_pd 5.6145 ps), and the full waveform demo `test/statsim_cdc_tb.vhd` passes —
clean capture leaves `q` at logic-1, a setup violation drives the PL_X plateau,
and the CDC trap fires exactly once, at the intended invalid sample.

*nvc gotcha (load-bearing):* nvc resolves a resolved **record** signal
**per sub-element** and only re-resolves a field when that field's own driver
changes. So a resolution function's single-source (`length=1`) path **must be the
identity** (`return drivers(low)`, like `logic3da`) — a result that depends on a
*different* field tears the record during staggered init and never recovers. The
"a lone passive tap floats" semantic therefore lives in the `PL_LOAD`/`PL_WIRE`
constructors (px=1, gdrv=0), not in a cross-field branch.

**Known model refinements (documented, not yet implemented):** hold-violation
detection (the backward-looking `d'last_event` can't see data moving *after* the
clock — `THOLD` is plumbed but unused); metastable resolution always settles to
the sampled value (no 50/50 wrong-capture); `T0` feeds the analytic MTBF
(`genmodel.mtbf`), not per-trial entry, which is deterministic within the setup
aperture; the `d.p1 >= d.p0` tie-break is 1-biased.

## hot-spot — electromigration screening from SPEF

The same layout→SPEF→behavioral-model machinery answers a second reliability
question: **electromigration (EM)**. `hot-spot` (`hotspot.py`) is the `-bfit`
pattern applied to *interconnect* — the "structure" it recognizes is a wire
segment and the smart behavioral model it substitutes is an **EM-aware wire that
knows its own current-density limit** (from its layer + width) and alerts when the
current through it is likely to migrate metal. Two modes, both driven from the
extracted-parasitic SPEF:

- **`instrument` / `check`** — replace every SPEF wire segment with a
  `statsim_em_wire` model (an ammeter-wrapped resistor by default; the portable
  `models/statsim_em_wire.vams` with `--va`), simulate on any engine (ngspice /
  Xyce via bfit's `SimDriver`), reduce each segment's current to **(avg, rms,
  peak)** and **print EM alerts** for every segment over limit — exit nonzero if
  any is. The node names are the SPEF's own, so the instrumented deck either
  back-annotates your design or runs stand-alone with a `--harness`.
- **`heatmap`** — the same risk numbers painted onto the layout: a self-contained
  SVG coloured by `I/Jmax` (log-scaled above the limit) with the wire drawn at its
  real coordinates and width, plus a ranked CSV of the worst segments.

**How EM is judged.** A foundry states EM as a maximum current per micron of wire
width (metals) or per via cut (vias), separately for average current (mass
transport / Black), rms (Joule self-heat) and peak. So for width *W* on layer *L*,
`Imax = Jlin[L,kind]·W` — no film thickness needed, exactly what a sign-off EM
checker screens. The width comes from geometry: `klayout2spef.py`'s analytic model
already derives per-layer `avg_w = 2·area/perimeter`, so the extractor that
produces the RC also produces the widths.

**Where the limit numbers come from — real vs estimate.** sky130 publishes **no
official EM rules**: its periphery rules mark electromigration as rule x.4 *"NC"*
(not checked by DRC), so hot-spot's built-in sky130 table (`hotspot.EM_RULES`) is
an honest **estimate** (Al cross-section), fine for the demo but not sign-off. For
**real foundry numbers**, point hot-spot at a PDK that ships them:
`--lef <pdk>_tech.lef` reads `DCCURRENTDENSITY` straight from the LEF. The IHP
Open-PDK **SG13G2** does — `em_rules_from_lef()` extracts its real limits
(Metal1 1.0, Metal2–5 2.0, TopMetal1/2 15/16 mA/µm; vias 0.4–10 mA/cut, DC/average
only) into `rules/ihp_sg13g2.em.json`. A rules JSON with `metal`/`via` **replaces**
the estimate; a kind the PDK doesn't specify (IHP gives only avg) is **not
screened** rather than guessed. The report header always prints which ruleset was
used.

```sh
# screen with REAL IHP SG13G2 limits (straight from the PDK LEF, or the cached json)
hotspot.py check design.em.spef --harness stim.sp \
  --lef .../IHP-Open-PDK/ihp-sg13g2/libs.ref/sg13g2_stdcell/lef/sg13g2_tech.lef
hotspot.py check design.em.spef --harness stim.sp --em-rules rules/ihp_sg13g2.em.json
```

**Where the geometry comes from.** EM is per-segment (the narrow neck fails first),
so hot-spot reads a *distributed* SPEF (one `*RES` per wire piece) plus a JSON
**geometry sidecar** (layer/width/length/coordinates per segment).
`klayout2spef.py --detail design.gds` emits both from a real GDS — the same
SPEF-in/SPEF-out, tool-agnostic contract as the routing-only flow, so it also runs
on OpenRCX / magic / commercial SPEF with a matching sidecar. `spef.py`'s
`net_loads()` still sums the distributed rows to the same `(c_wire, r_wire)`, so
the CDC timing path is unaffected.

```sh
# real flow (Linux + klayout):
klayout2spef.py --detail sky130_ef_io__gpiov2_pad.gds -o gpio.em.spef
hotspot.py check   gpio.em.spef --harness stim.sp          # -> EM alerts, nonzero exit if over
hotspot.py heatmap gpio.em.spef --harness stim.sp -o gpio.em.svg --csv gpio.em.csv

# runnable here with no klayout (WSL ngspice) -- the sky130 IO-pad test case:
hotspot.py check   test/iopad_em.spef --harness test/iopad_em.harness.sp
hotspot.py --self-test           # physics + SPEF pass + instrument + SVG, no simulator
```

**Worked example** (`test/hotspot_iopad_demo.md`): a GPIO output slice's 0.5 µm
met1 driver neck runs **61× over** its peak EM limit (≈0 % of nominal lifetime),
the via array 32×, the met2 route 15×, the wide met3 pad metal 5.6×, and the power
rails ~2.5–2.8× — while the thin control signal stays green. The heat-map
(`test/iopad_em.em.svg`) shows exactly where on the pad the metal is at risk.

**Real end-to-end on an IHP pad** — extract (klayout) → simulate a driver into the
pad (Xyce) → screen → recolor the layout by EM risk: step-by-step copy-paste guide
in **[`test/HOWTO_em_iopad.md`](test/HOWTO_em_iopad.md)** (the actual
`sg13g2_IOPadOut30mA`; committed outputs `test/iopad30_ihp.*`).

## CDC detection test case

`test/cdc_latch_tb.vhd` is a runnable end-to-end CDC demo. A regular 4-state
(01XZ) testbench drives two clocks at slightly different frequencies — a **latch
clock** (2.0 ns) and a **data line that is itself a clock** (2.2 ns, asynchronous).
Two **stat-sim inverters** (`lib/statsim_io.vhd`, `statsim_inv`) lift the 01XZ
logic into the probability domain, and the **stat-sim latch** (`statsim_latch`)
flags the CDC metastability risk: each time the data is transitioning (or already
invalid) as the latch closes, it drives `PL_X` and reports.

```
clk (2.0ns) ─►[statsim_inv]─► clk_p ┐
                                     ├─►[statsim_latch]─► q_p   (flags PL_X +
dat (2.2ns) ─►[statsim_inv]─► dat_p ─┘                          "CDC metastability risk")
```

Run:
```sh
nvc --std=2040 -L /usr/local/src/nvc-build/lib --work=statsim:build/statsim \
    -a lib/statsim_disc.vhd lib/statsim_taps.vhd lib/statsim_io.vhd test/cdc_latch_tb.vhd
nvc ... -e cdc_latch_tb && nvc ... -r cdc_latch_tb
```

Result: the latch flags the async crossing **18 times over 200 ns** — at the
beat-frequency points where the data edge drifts through the latch's aperture as
it closes — each with its randomized `Exp(τ)` plateau (1 fs … ~52 ps). That is
the tool doing its job: catching the metastability a structural CDC lint would
only flag as a *missing synchronizer*, here with a per-event hazard.

See **[`test/cdc_latch_demo.md`](test/cdc_latch_demo.md)** for the full write-up
with the hazard log and an annotated waveform of the t=55 ns event. Committed
artifacts: `test/cdc_latch_tb.log` (run log) and `test/cdc_latch_tb.fst`
(waveform, viewable in gtkwave/surfer).

`test/cdc_latch_tb.v` is the same testbench in **Verilog** (+ `cdc_latch_dut.vhd`,
a `logic3d`-boundary wrapper). It elaborates under nvc, but the nvc/sv2ghdl
Verilog→VHDL *instantiation* boundary doesn't yet propagate port values (pure
Verilog and pure VHDL both simulate; only cross-language port binding is the gap —
a toolchain item). Use the `.vhd` driver to run the demo today.

## Finding the critical paths by raising the clock (`bind.py`, `sweep.py`)

A gate netlist (Yosys or OpenROAD `write_verilog`) is bound to prob_load cell
models generated from the Liberty -- each combinational cell type an entity
evaluating its function as a truth table on the inputs' probability
simplexes, driving its output with the Liberty-fitted drive resistance of the
edge and the on-the-fly load delay; the flops as the metastable `sky130_dfxtp`
(an enable flop as a mux in front); a `statsim_pl_load` tap per receiver pin
(the Liberty's pin capacitance) and, with a SPEF, the wiring as taps. The
generated testbench has a clock `PERIOD` generic, random vectors on the primary
inputs after each rising edge, and a probe that writes per cycle each flop's
D-node `px` at the capture edge and every output. `sweep.py` runs it at a list
of periods with the same vectors and reports, against the slowest run, the
first period at which each flop's D is caught moving and each output differs:
those flops are the ends of the critical paths, found by simulation alone.

```sh
python3 bind.py gcd_pnr.v --top gcd --lib sky130_fd_sc_hd__tt_025C_1v80.lib [--spef gcd.spef --spef-mode lump] -o build/gcd
python3 sweep.py build/gcd --top gcd --periods 8,6,5,4.5,4,3.5,3,2.5,2,1.6,1.2
```

gcd (222 cells, 35 flops) at tt, 300 cycles a period, 4 s a run
(`test/sweep_gcd.log`, `test/sweep_gcd_spef.log`): clean down to 3.5 ns; at
3.0 ns 32 flops' D nodes are caught moving, first among them `_265_`..`_272_`,
and 18 outputs go wrong. OpenROAD's timer on the same routed design
(`test/sweep_gcd_sta_ends.rpt`) puts its worst endpoints at `_267_`..`_279_`
with a 3.33 ns arrival -- the same flops, the same clock. With the OpenRCX SPEF
as lumped wire taps the top of the list is unchanged and the deeper flops
(`_297_`..`_299_`) fail earlier (2.0 instead of 1.2 ns). `--spef-mode tree` binds each
receiver to its own node of the SPEF's RC tree, one `statsim_pl_rc` per
resistor above `--r-min` (30 ohm by default: the pieces below it are merged
away, gcd 820 -> 140 elements, the ALU 21k -> 3100; `test/sweep_gcd_tree.log`).
The cell delay carries the switching input's transition (estimated from its
node's driver conductance and load, `KAPPA` 0.4 as layopt's drive fit): without
it the load-only delay matched the timer on gcd's short paths but was three
times optimistic on the ALU's 30-stage carry chain (`test/sweep_alu_noslew.log`:
outputs wrong from 2.5 ns against the timer's 7.3); with it gcd's endpoints are
caught at 3.75 ns and clean at 4.0 against the timer's 3.33 ns arrival plus
90 ps of setup (`test/sweep_gcd_tree_slew.log`). The probe counts metastable
captures directly: a process on each flop's Q counts its PL_X plateaus, so a
setup violation at that flop is seen at that flop, not a cycle later through
its fan-out (`_297_`, gcd's ready flop, is caught at every period: the three
captures at reset release).

The ALU (4036 cells, 188 flops, reduced trees, `--kappa 0.4`;
`test/sweep_alu_tree_counters.log`, 200 cycles a period, about ten minutes a
run): 85 flops are caught metastable on some cycles at every period from 10 ns
down -- the result register (enable `net44`/`net45`) and the input-ready flops
-- and the timer's worst endpoint `_7065_` is among them; the outputs go wrong
from 3 ns. So the sweep names the same endpoints as the timer on both designs;
what it does not do is put them at the timer's period: with the transition
share at 0.4 the ALU's adder path is caught at 10 ns where the timer has
7.3 + setup, and gcd's at 3.75 against 3.4. The transition estimate from a
node's driver conductance and load is crude, and 30 stages of it compound; the
share is a calibration knob (`--kappa`; at 0.2 gcd is caught at 3.25 ns,
`test/sweep_gcd_k02.log`, but the ALU's adder register is still caught at 10 ns,
`test/sweep_alu_k02.log`).

So the cells are now timed the way a timer times them, at event time: each
combinational cell carries its Liberty delay and transition tables per input
and output edge, interpolates them on (input transition, load) for the
switching input, and publishes its output transition in the node's `gdrv`
(`LN9 * cload / transition`) so the next stage reads it back as its input
transition -- an NLDM evaluation inside the prob_load discipline, no fitted R
(`--fitted` keeps the R-and-share model). The testbench moves the inputs the
SDC's input delay after the edge (`INPUT_DELAY`, 400 ps): moving them a
picosecond after it had them racing the clock tree into the flops with short
paths. gcd so timed (`test/sweep_gcd_nldm.log`): clean at 4.0 ns, its
endpoints caught at 3.75, against the timer's 3.33 ns arrival plus 90 ps of
setup. Cost of the table-timed cells: a cell schedules an output event only when
its value changes (with an event per input event the whole fan-out cone was
re-timed at every toggle: 100 s a cycle on the ALU); so timed, the ALU
elaborates in 5.5 minutes a period (the tables are constants of 4000
instances; nvc needs `-H 2g`) and simulates at 5.5 s a cycle, gcd in 22 s a
period. The ALU so timed, 100 random cycles a period
(`test/sweep_alu_nldm_random.log`): no flop caught and no output wrong down to
4 ns, where the timer's static worst path is 7.3 ns. That is the difference
between a simulation and a timer: the sweep finds the critical paths the
vectors *exercise*, and random operands rarely send a carry the length of a
32-bit adder. The testbench therefore has a second vector mode (`--stim alt`:
the data bits all 0 and all 1 on alternate cycles with three random bits
flipped, so carry chains see their full length); the ALU with it is running. The
fitted model with the same random vectors and the corrected testbench agrees
with the table-timed cells: nothing caught down to 4 ns
(`test/sweep_alu_fit_random.log`), and the alternating vectors change nothing
either (`test/sweep_alu_nldm_alt.log`): the ALU's long paths sit behind its
operation field and its valid/ready protocol, which a generic testbench does
not drive -- data bits all 0 or all 1 select no add. The sweep is only as good
as its vectors; for a design with a protocol the stimulus has to be the
design's own (the async translation will come with one). What the alternating
vectors do exercise fails at 2 ns (`test/sweep_alu_nldm_alt_low.log`: two flops
caught, four outputs wrong), so the model is judging; it is the paths it is
shown. Not done yet: the hold side.

## Forward-compatible with the second patent (DFX / defect coverage)

US20230334213A1 (defect simulation, hierarchical binning) is a later layer, but
the architecture is designed now so it drops in rather than forcing a rewrite.
Its requirements and where each lands:

| '213 requirement | how stat-sim already accommodates it |
|------------------|--------------------------------------|
| switch between **good and bad (defective) models** | the multi-UDN node resolves *multiple selectable drivers*; a defect is a per-instance `VARIANT`/`DEFECT` generic (good = -1) selecting which model drives — switchable mid-sim, no restart |
| **hierarchical processing** | bfit's recognizer/substituter gives the level hierarchy; a defective bin model at a low level propagates upward as an input to the next |
| **minimal flow: drop/disable each SPICE-level component in turn** | `stdcell2bfit.py` enumerates the cell's per-device conductances; defect variant *k* = open (g→0) or short that one device — a one-line variation of the generated model |
| **defect coverage** | the CDC trap generalizes from "is the node non-rail" to "does this variant's output differ observably from the good model"; coverage = fraction of dropped-device variants that are detected |

**Design rule (held across all stat-sim code):** model generation stays
*variant-parameterized* and runtime model-selection is a *first-class seam* — every
generated cell carries a `VARIANT`/`DEFECT` generic (default = good), and the node
can host a selectable "defect mux" driver. The probability/load conjugate nature
makes this natural: a defective model simply drives a different probability
distribution onto the shared node, and the observer reads the divergence.

## Built on

- `bfit` (`/usr/local/src/sv2ghdl/bfit`) — `stdcell2bfit.py` (cell→model),
  `merge.recognize_xcoupled()` (regenerative-pair detector), the engine-neutral
  `SimDriver`, and per-corner caching. stat-sim imports these directly.
- The simulator **shims** (qspice / ltspice / spectre / `~/bin/Xyce` WSL bridge /
  ngspice+OpenVAF) — uniform "run netlist, parse raw" contract.
- **sky130** PDK statistical models at `/opt/pdk/sky130A` — the silicon
  variability source (`mc_pr_switch`/`mc_mm_switch` AGAUSS process+mismatch).
  (IHP-Open-PDK at `/usr/local/src/IHP-Open-PDK` is a second option.)

## Usage

```sh
# generate a metastable synchronizer model from a cell spec
python3 statsim.py genmodel --spec specs/sky130_dfxtp.json --out models/

# self-test the generator (no simulator needed)
python3 genmodel.py --self-test
```

## Status

`genmodel` generates models now. `characterize` and `check` have defined
interfaces and are the next increments.

## License

stat-sim is **dual-licensed**:

- **Noncommercial and personal use is free** under the
  [PolyForm Noncommercial License 1.0.0](LICENSE) — research, teaching, personal
  study, hobby, and evaluation use, and use by nonprofit / academic / government
  organizations. Every source file carries an
  `SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0` header.
- **Commercial use requires a separate, paid license** (royalty-based terms are
  available). See **[COMMERCIAL.md](COMMERCIAL.md)**.

Why two: stat-sim implements the author's patented methods — **US 8,478,576 B1**
(probability-waveform variability; the LEAD method) and **US 2023/0334213 A1**
(analog/MS defect binning). A commercial user needs both a copyright license to
the code *and* a patent license to practice the methods; the PolyForm patent
grant is scoped to noncommercial use only, so the patents remain an independent
right for commercial use. Both are conveyed by the commercial license.

Copyright (c) 2026 D. Kevin Cameron. Commercial licensing: cameron.eda@gmail.com.
