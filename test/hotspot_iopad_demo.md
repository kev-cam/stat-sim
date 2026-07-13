# hot-spot demo: electromigration on a sky130 GPIO output-pad slice

This is a runnable, end-to-end demo of `hot-spot` — the SPEF → **behavioral EM
models** + **layout heat-map** flow — on a sky130 I/O-pad output stage. It runs
here with **no klayout** (the SPEF + geometry are hand-authored, exactly the way
`spef.py` / `klayout2spef.py` self-test) and **no Verilog-A compiler** (the
default path is an ammeter + Python current-density reduction). The only external
tool is **ngspice** (WSL: `/usr/bin/ngspice`).

## The circuit

`test/iopad_em.spef` is a *distributed*-parasitic SPEF — one `*RES` row per
physical wire piece — for a GPIO output slice:

```
 IN ─[sig_in met1 0.3µm]─► driver ─┬─ pad_drv ─────────────────────────► PAD
                                   │  seg1 met1 0.5µm  (driver neck)
   VDD ─[vdd_rail met3 8µm]─► VDDIO│  seg2 mcon ×4     (li/met1→met2 via)
                                   │  seg3 met2 2µm    (main route)
   VSS ◄[vss_rail met3 8µm]─ VSSIO │  seg4 via2 ×2     (met2→met3 via)
                                   └─ seg5 met3 4µm    (wide metal to pad)
```

`test/iopad_em.spef.json` is the **geometry sidecar** (layer, width, length,
coordinates per segment) — the width is what turns a current into a current
density. `test/iopad_em.harness.sp` drives the pad with a pulsed VDDIO into a
low-impedance external load so real current flows through the whole chain.

## 1. Behavioral-model mode — print EM alerts

```sh
python3 hotspot.py check test/iopad_em.spef --harness test/iopad_em.harness.sp
```

hot-spot replaces every wire segment with an ammeter-wrapped `statsim_em_wire`
model, runs the deck on ngspice, reduces each segment's current to (avg, rms,
peak), and screens each against its layer/width limit:

```
=== hot-spot EM current-density report ===
segment               layer    w(um)      I_avg   Imax_avg   worst  verdict
pad_drv:1             met1       0.5  2.046e-02  3.950e-04   61.37  OVER-LIMIT (EM)
pad_drv:4             via2      2cut  2.046e-02  7.600e-04   32.34  OVER-LIMIT (EM)
pad_drv:2             mcon      4cut  2.046e-02  1.120e-03   20.82  OVER-LIMIT (EM)
pad_drv:3             met2         2  2.046e-02  1.580e-03   15.32  OVER-LIMIT (EM)
pad_drv:5             met3         4  2.046e-02  4.080e-03    5.60  OVER-LIMIT (EM)
vdd_rail:1            met3         8  2.046e-02  8.160e-03    2.80  OVER-LIMIT (EM)
vss_rail:1            met3         8  2.040e-02  8.160e-03    2.50  OVER-LIMIT (EM)
sig_in:1              met1       0.3  5.558e-07  2.370e-04    0.17  ok

7 segment(s) over EM limit (worst-first; worst = max of avg/rms/peak I over Imax).
  ALERT  pad_drv:1 (met1 0.5um): peak current 5.830e-02 A is 61.4x Imax (9.500e-04 A) -> ~0.0% of nominal EM lifetime
  ALERT  pad_drv:4 (via2 via):   peak current 5.822e-02 A is 32.3x Imax (1.800e-03 A) -> ~0.1% of nominal EM lifetime
  ...
  ALERT  vss_rail:1 (met3 8.0um): avg current 2.040e-02 A is 2.5x Imax (8.160e-03 A) -> ~16.0% of nominal EM lifetime
```

The tool doing its job: the **0.5 µm met1 driver neck is 61× over** its peak
current-density limit — a classic I/O EM failure site — and the `check` exits
nonzero. The wide met3 near the pad (5.6×) and the power rails (~2.5–2.8×) are
also over; the thin control signal `sig_in`, which only charges a gate, is `ok`.
Note the two limits diverge because the supply is pulsed: `vss_rail` is worst on
**avg** current (mass-transport EM), the neck on **peak**.

Inline, during-simulation alerts (the fuller "smart model") are available with
`--va`, which instantiates the portable `models/statsim_em_wire.vams` and lets it
`$strobe` the moment its current density crosses the limit — needs OpenVAF
(ngspice) or PyMS/VAE (Xyce).

## 2. Heat-map mode — where EM is worst on the layout

```sh
python3 hotspot.py heatmap test/iopad_em.spef --harness test/iopad_em.harness.sp \
        -o test/iopad_em.em.svg --csv test/iopad_em.em.csv
```

`test/iopad_em.em.svg` paints each segment at its layout coordinates, line width
∝ wire width, colour ∝ EM risk (`I/Imax`, log-scaled above 1× so the 61× neck
stands out from the 2× rails): **green** ok → **red** at the limit → **magenta/
pink** many× over. The neck lights up brightest; the rails run red; `sig_in` is
green. `test/iopad_em.em.csv` is the same data ranked worst-first, with every
metric (avg/rms/peak current, each ratio, relative MTTF, coordinates).

## How current density is judged

For a segment of width *W* on layer *L*, the limit is `Imax = Jlin[L,kind] · W`
(metals) or `Jcut[V,kind] · cuts` (vias), for `kind ∈ {avg (EM/mass transport),
rms (Joule self-heat), peak}` — exactly how a foundry states EM and how a sign-off
checker screens it, with no film thickness needed. The relative-MTTF figure is
Black's-equation `(Imax_avg/I_avg)ⁿ` (n≈2).

**Real numbers vs estimate.** sky130 publishes **no official EM rules** — its
periphery rules mark electromigration as rule x.4 *"NC"* (not checked by DRC), so
the built-in `hotspot.EM_RULES` sky130 table is an honest **estimate** (this run's
header says so). For real foundry numbers, hot-spot reads a PDK's LEF directly:

## Real IHP SG13G2 limits (from the PDK LEF)

The IHP Open-PDK SG13G2 tech LEF *does* carry current-density rules
(`DCCURRENTDENSITY AVERAGE`, DC/mass-transport, mA/µm of width and mA/via).
`em_rules_from_lef()` extracts them into `rules/ihp_sg13g2.em.json`; screening the
same circuit (relayered via `test/iopad_em.ihp.json`) against the **real** numbers:

```sh
hotspot.py check test/iopad_em.spef --harness test/iopad_em.harness.sp \
    --geom test/iopad_em.ihp.json --em-rules rules/ihp_sg13g2.em.json
    #  (or  --lef .../ihp-sg13g2/.../sg13g2_tech.lef  to read the PDK directly)
```

```
rules: REAL -- LEF DCCURRENTDENSITY AVERAGE (DC/mass-transport, mA/um width & mA/via) from sg13g2_tech.lef
segment               layer    w(um)      I_avg   Imax_avg   worst  verdict
pad_drv:1             Metal1     0.5  2.046e-02  5.000e-04   40.93  OVER-LIMIT (EM)   # 1.0 mA/um * 0.5um
pad_drv:4             Via2         0  2.046e-02  8.000e-04   25.58  OVER-LIMIT (EM)   # 0.4 mA/cut * 2
pad_drv:2             Via1         0  2.046e-02  1.600e-03   12.79  OVER-LIMIT (EM)   # 0.4 mA/cut * 4
pad_drv:3             Metal2       2  2.046e-02  4.000e-03    5.12  OVER-LIMIT (EM)   # 2.0 mA/um * 2um
pad_drv:5             Metal3       4  2.046e-02  8.000e-03    2.56  OVER-LIMIT (EM)
vdd_rail:1            Metal3       8  2.046e-02  1.600e-02    1.28  OVER-LIMIT (EM)
vss_rail:1            Metal3       8  2.040e-02  1.600e-02    1.27  OVER-LIMIT (EM)
sig_in:1              Metal1     0.3  5.558e-07  3.000e-04    0.00  ok
```

IHP's LEF specifies only the DC/average limit, so hot-spot screens **avg only** and
leaves rms/peak unscreened (not invented) — the Metal1 neck is 40.9× over the real
IHP limit. The `--em-rules`/`--lef` path is PDK-agnostic: any tech LEF with
`DCCURRENTDENSITY`, or any hand-written rules JSON, plugs in the same way.

## The real flow (on Linux, with klayout)

The hand-authored SPEF here stands in for what `klayout2spef.py --detail` emits
from a real GDS:

```sh
klayout2spef.py --detail sky130_ef_io__gpiov2_pad.gds -o gpio.em.spef
hotspot.py check   gpio.em.spef --harness <your stimulus>
hotspot.py heatmap gpio.em.spef -o gpio.em.svg
```

`--detail` writes the same distributed SPEF + geometry-sidecar contract, so the
EM screen is **SPEF-in / SPEF-out and tool-agnostic** — it also runs on OpenRCX,
magic, or a commercial extractor's SPEF once a matching sidecar is supplied.

## Real result: IHP `sg13g2_IOPadOut30mA`, simulated (clevo-lx klayout + Xyce)

The actual IHP Open-PDK 30 mA output pad, end-to-end — extracted with klayout on
**clevo-lx** (klayout 0.30.9 venv), then **simulated in Xyce** so the per-segment
currents come from a transient, not a hand-assigned budget:

```sh
# 1. extract the real pad GDS with the IHP tech (clevo-lx)
klayout2spef.py --pdk ihp-sg13g2 --detail --flatten \
    --top sg13g2_IOPadOut30mA sg13g2_io.gds -o iopad30.em.spef
# -> 17 nets, 105 per-layer/via segments (Metal1..TopMetal2, Via1..TopVia2)

# 2. name nets from GDS text labels; build a driver testbench + a simulatable-R SPEF
python3 test/iopad30_ihp_annotate.py     # pad/iovdd/iovss/drv_o_* via l2n.probe_net
python3 test/iopad30_ihp_tb.py           # push-pull driver + supplies + load; .sim.spef

# 3. SIMULATE in Xyce (WSL) -> per-segment currents -> EM screen + heat-map
hotspot.py heatmap test/iopad30_ihp.sim.spef --geom test/iopad30_ihp.em.spef.json \
    --em-rules rules/ihp_sg13g2.em.json --sim xyce --harness test/iopad30_ihp.harness.sp \
    --csv test/iopad30_ihp.xyce.csv -o /tmp/raw.svg   # the CSV feeds the layout recolor (step 4)
```

The port (`--pdk ihp-sg13g2`) is a routing/EM connectivity tech (metal+via stack,
**no device recognition** — diffusion left unconnected so a FET's S/D stay separate
metal nets). The **testbench** (`iopad30_ihp_tb.py`) wires a transistor push-pull
(Xyce-native MOS — IHP's PSP103 needs OpenVAF, absent here) across the extracted net
endpoints so `iovdd → drv_o_p → pad` is the pull-up path and `pad → drv_o_n → iovss`
the pull-down; a pulsed input toggles the output into a load, and Xyce solves the
current in every wire segment.

**Two things the simulation forced us to get right:**

- *Time-weighted current reduction.* Xyce's adaptive timestep makes a plain sample
  mean skew the average; hot-spot integrates avg/rms **trapezoidally over time**
  (sample-mean is the uniform-step fallback). Xyce and ngspice then agree on the
  synthetic case (20.6 vs 20.5 mA avg) instead of 7 vs 20.
- *Simulatable R.* klayout's analytic R (`RSH·perim²/4area` metal, `RVIA·cuts` via)
  is right for the lumped EM *width* but hugely over-estimates a solvable network —
  a supply net's perimeter inflates and parallel via cuts should **divide** R, not
  multiply. Segments hit **17 kΩ** and starved the driver to µA. The testbench emits
  a `.sim.spef` with a geometry-realistic R (`RSH·span/width`, `RVIA/cuts`); the EM
  *widths* still come from the geometry sidecar, unchanged.

Result (`test/iopad30_ihp.xyce.*`): **9 of 105 segments over the real IHP EM limit**,
and the distribution is one only a simulation gives —

| segment | layer | width | I_avg | worst |
|---------|-------|-------|-------|-------|
| `drv_o_p:1` | Metal1 | **0.16 µm** | 4.7 mA | **29.4×** |
| `iovdd:1` | Metal1 | 0.17 µm | 4.7 mA | 27.5× |
| `drv_o_p:2` | Metal2 | 0.22 µm | 4.7 mA | 10.7× |
| `iovdd:8` | Via1 | 2 cut | 4.7 mA | 5.9× |
| `pad:1` | Metal1 | 0.76 µm | 4.5 mA | 5.9× |
| `drv_o_n:1` (pull-down) | Metal1 | 0.16 µm | 0.25 mA | 1.6× |
| `pad:3–5` | Metal3–5 | 2.88 µm | 4.5 mA | 0.77× — safe |

The **pull-up** path (iovdd → drv_o_p → pad) carries the driver's DC into the load
and its thin Metal1 lights up (29×); the **pull-down** `drv_o_n` only sinks
cap-discharge current and stays cool (1.6×) — an asymmetry a fixed budget can't
show. Honest caveat: the geometry-realistic R still over-estimates the scattered
supply nets, so the driver delivers ~5 mA (below the 30 mA rating); a real
field-solver RCX would push more current and more segments over. IHP's LEF specifies
only the DC/average limit, so rms/peak are left unscreened.

**The heat-map is the real layout, recolored** — not an SVG redraw.
`klayout2spef --em-layout --csv <sim> --rename <names>` takes each segment's
`worst` from the sim and moves that net's actual metal polygons onto a risk-tier
GDS layer (`EM_ok` grey … `EM_crit` magenta), writing `test/iopad30_ihp.em.gds` +
a klayout `.lyp`. Open them in klayout and the pad lights up where EM is worst
(`test/render_em_poly.py` renders those tiers to `test/iopad30_ihp.em.svg` for a
quick look). Tiers here: 3 crit, 2 high, 2 over on the pull-up output path; 50 ok.

**This is the point of hot-spot**, and it scales past pads: extract a design's
parasitics, drive it with a real stimulus, simulate (bfit-accelerated for large
circuits), screen every wire segment's simulated current density against the
foundry's limits, and paint the result back onto the layout.
