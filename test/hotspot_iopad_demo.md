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
Black's-equation `(Imax_avg/I_avg)ⁿ` (n≈2). The per-layer numbers in
`hotspot.EM_RULES` are **representative** sky130 figures (order-of-magnitude, in
the project's inter-engine ~1 % tolerance spirit) — refine them from the PDK's
current-density rules or pass `--em-rules rules.json`.

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
