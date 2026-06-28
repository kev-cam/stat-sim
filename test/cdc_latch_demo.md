# CDC detection demo — `cdc_latch_tb`

A minimal, runnable clock-domain-crossing test case: a level-sensitive **latch**
clocked at one frequency samples a **data line that is itself a clock** at a
slightly different frequency. The two are asynchronous, so the data edge
periodically drifts into the latch's aperture as it closes — and the stat-sim
latch **flags the metastability** each time.

## Signal flow

A regular 4-state (01XZ) testbench drives the two clocks; **stat-sim inverters**
lift the 01XZ logic into the probability domain; the **stat-sim latch** flags the
hazard.

```
 clk_v  2.00 ns  ──►[ statsim_inv ]──► clk_p ┐  (latch enable, probability)
 (01XZ, latch clk)                           │
                                             ├─►[ statsim_latch ]──► q_p
 dat_v  2.20 ns  ──►[ statsim_inv ]──► dat_p ┘        │
 (01XZ, async data)                                   └─► drives PL_X (px=1) and reports
                                                          "CDC metastability risk" when the
                                                          data is unsettled at the latch close
```

- `lib/statsim_io.vhd` — `statsim_inv` (01XZ→probability, inverting) and
  `statsim_latch` (metastable level-sensitive D-latch).
- `test/cdc_latch_tb.vhd` — the runnable testbench (this demo).
- `test/cdc_latch_tb.v` — the same testbench in Verilog. It elaborates but a
  Verilog-instantiates-VHDL design hits a known nvc `--std=2040` toolchain bug
  (`sv2ghdl/BUG_2040_cross_instantiation.md`); run the `.vhd` driver instead.

## Run

```sh
NVC="/usr/local/src/nvc-build/bin/nvc --std=2040 -L /usr/local/src/nvc-build/lib --work=statsim:build/statsim"
$NVC -a lib/statsim_disc.vhd lib/statsim_taps.vhd lib/statsim_io.vhd test/cdc_latch_tb.vhd
$NVC -e cdc_latch_tb
$NVC -r cdc_latch_tb --wave=test/cdc_latch_tb.fst --format=fst   # waveform -> FST
```

Artifacts (committed): **`test/cdc_latch_tb.log`** (full run log) and
**`test/cdc_latch_tb.fst`** (waveform, open in gtkwave/surfer).

## Log — the flagged CDC hazards

Over 200 ns the latch flags the async crossing **18 times**, at the beat points
where the data edge lands in the aperture as the latch closes. Each carries the
randomized `Exp(τ)` metastable-plateau duration of that event (`SEED=1`, so the run
is deterministic):

| t (ns) | plateau | t (ns) | plateau | t (ns) | plateau |
|:------:|:-------:|:------:|:-------:|:------:|:-------:|
| 11  | 1 fs    | 87  | 38.8 ps | 153 | 34.4 ps |
| 21  | 0.4 ps  | 99  | 24.9 ps | 165 | 19.0 ps |
| 33  | 6.8 ps  | 109 | 28.1 ps | 175 | 20.8 ps |
| 43  | 17.3 ps | 121 | 6.6 ps  | 187 | 5.6 ps  |
| 55  | 51.8 ps | 131 | 32.2 ps | 197 | 0.8 ps  |
| 65  | 28.6 ps | 143 | 1.5 ps  |     |         |
| 77  | 6.4 ps  |     |         |     |         |

```
** Warning: 55ns+1: statsim_latch: CDC metastability risk -- data unsettled at latch close (px=1 plateau 51784 fs)
   Process :cdc_latch_tb:lat:_p0 at lib/statsim_io.vhd:52
...
** Note: 200ns+0: cdc_latch_tb DONE: latch output went metastable 20 times over 200 ns -- the stat-sim latch flagged the async data crossing.
```

(18 distinct `CDC metastability risk` warnings; the summary counts 20 `px>0.5`
transitions — the 2 extra are mid-transparency propagations of an invalid input.)

## Waveform — the largest hazard (t = 55 ns)

At t = 55 ns the latch clock edge and the data edge **coincide** (`clk_v` rises as
`dat_v` toggles), so the latch closes on a moving data line → its output goes to an
invalid mid-rail level (`q_p.px = 1`) for 51.8 ps before resolving. Captured live
at 20 ps resolution:

```
 time(ns) │ 54.90  54.96  55.00  55.04  55.06  55.08  55.10  55.12  55.16  55.20
──────────┼──────────────────────────────────────────────────────────────────────
 clk_v    │  0      0    ┌─1─────1──────1──────1──────1──────1──────1──────1───   (latch clk; rises @55.0)
          │             │
 dat_v    │  1      1    └─0─────0──────0──────0──────0──────0──────0──────0───   (async data; falls @55.0)
          │             ▲                     ┌────────────┐
 q_p.px   │  0      0    0      0      0    ┌──1──────1──┐  0      0      0        (latch output INVALID:
          │             │                   │            │                          px=1 for ~52 ps)
          │      latch closes here   55.06─┘            └─55.11
          │      (clk_p falls, data mid-transition)        resolves
```

- Before 55.0 ns the latch is transparent (`clk_v=0 ⇒ clk_p=1`), output clean.
- At **55.0 ns** `clk_v` rises (so `clk_p` falls — the latch **closes**) at the
  exact instant `dat_v` is switching → setup/hold aperture violated.
- After `TCQ0 = 60 ps`, `q_p.px` jumps to **1** (the metastable plateau — an invalid
  logic level on the node) and stays there `Exp(τ)`-distributed time (51.8 ps here),
  then resolves. That `px = 1` window is exactly what a downstream sampler would
  capture wrong, and exactly what the trap/latch flags.

This is the tool's job: a structural CDC linter would only note a *missing
synchronizer*; stat-sim shows the metastability **propagating**, per event, with a
quantified invalid-level window.
