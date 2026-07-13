<!-- SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0 -->
# HOW-TO: EM screen a real IHP pad end-to-end (`sg13g2_IOPadOut30mA`)

A runnable walkthrough of the hot-spot electromigration flow on the IHP Open-PDK
30 mA output pad: **extract** parasitics → **simulate** a driver into the pad →
**screen** every wire segment's current density against the foundry's limits →
**recolor the layout** by risk. Narrative + results are in
[`hotspot_iopad_demo.md`](hotspot_iopad_demo.md); this is the copy-paste version.

The committed outputs (`test/iopad30_ihp.*`) let you inspect every stage without
re-running anything.

## What runs where

| tool | why | where (this setup) |
|------|-----|--------------------|
| **klayout** (`pip install klayout`) | GDS extraction + layout recolor | Linux + a venv — here **clevo-lx** `/home/claude/klvenv/bin/python3` (klayout not on the Cygwin/WSL box) |
| **Xyce** (or ngspice) | the transient that produces the currents | **WSL** (Linux ELF); Cygwin can't run it |
| plain `python3` | annotate / testbench / render / the screen logic | anywhere (Cygwin, WSL, clevo) |

Paths below are relative to the repo root (`/usr/local/src/stat-sim`).
`$GDS = /usr/local/src/IHP-Open-PDK/ihp-sg13g2/libs.ref/sg13g2_io/gds/sg13g2_io.gds`.

## 0. No-toolchain sanity check (works anywhere, pure python)

```sh
python3 hotspot.py --self-test          # EM physics, SPEF pass, instrument, SVG
python3 klayout2spef.py --self-test     # SPEF writers + IHP/sky130 tech tables
bash run_tests.sh                        # + the synthetic sky130 pad on ngspice (WSL)
```

## 1. Extract the pad's parasitics  (klayout, on clevo-lx)

Per-layer/via distributed EM-SPEF + a geometry sidecar (widths for the EM limits):

```sh
/home/claude/klvenv/bin/python3 klayout2spef.py --pdk ihp-sg13g2 --detail --flatten \
    --top sg13g2_IOPadOut30mA "$GDS" -o test/iopad30_ihp.em.spef
# -> test/iopad30_ihp.em.spef  +  test/iopad30_ihp.em.spef.json   (17 nets, 105 segments)
```

`--pdk ihp-sg13g2` is a routing/EM connectivity tech (metal+via stack, no device
recognition); `--flatten` collapses the cell to one flat net set. Nets come out
generated-named (`$1`, `$2`, …).

## 2. Name the nets + build the testbench  (plain python)

```sh
python3 test/iopad30_ihp_annotate.py    # $1->pad, $25->iovdd, ... (from GDS text labels)
                                         #   rewrites the SPEF+geom, writes *.rename.json
python3 test/iopad30_ihp_tb.py          # driver push-pull + supplies + load -> *.harness.sp
                                         #   + *.sim.spef (geometry-realistic R for the solver)
```

Why two SPEFs: the extracted R (`RSH·perim²/4area`) is right for the EM *width* but
over-estimates a *solvable* network ~100×, so the testbench emits a `.sim.spef`
with `RSH·span/width` (parallel vias `RVIA/cuts`). The EM widths still come from the
geometry sidecar, unchanged.

## 3. Simulate → per-segment currents → EM screen  (Xyce, in WSL)

```sh
# one Xyce transient -> heat-map data (SVG+CSV); wrapper handles the absolute paths
bash test/run_iopad30_xyce.sh
# or directly:
python3 hotspot.py check test/iopad30_ihp.sim.spef --geom test/iopad30_ihp.em.spef.json \
    --em-rules rules/ihp_sg13g2.em.json --sim xyce --harness test/iopad30_ihp.harness.sp
```

`--sim xyce` runs Xyce in WSL; `--em-rules rules/ihp_sg13g2.em.json` are the **real
IHP limits** extracted from the PDK LEF's `DCCURRENTDENSITY` (or read a LEF live with
`--lef .../sg13g2_tech.lef`). The `check` prints ranked EM alerts (exit nonzero if any
segment is over); `heatmap` writes the per-segment `test/iopad30_ihp.xyce.csv` that
feeds the layout recolor in step 4. (hot-spot's built-in `-o` SVG is a rough per-net
line sketch that mangles real multi-shape nets — the real heat-map is step 4's
klayout recolor, `test/iopad30_ihp.em.{png,svg,gds}`.)

Expected: **9 / 105 segments over** — the pull-up output path (`iovdd → drv_o_p →
pad`) on 0.16 µm Metal1 at ~29×, the pull-down `drv_o_n` cool at 1.6×.

## 4. Recolor the layout by EM risk  (klayout, on clevo-lx)

Move each segment's real polygons onto a per-risk-tier GDS layer — **this is the
heat-map**, rendered by klayout, not an SVG redraw:

```sh
/home/claude/klvenv/bin/python3 klayout2spef.py --pdk ihp-sg13g2 --em-layout --flatten \
    --top sg13g2_IOPadOut30mA --csv test/iopad30_ihp.xyce.csv \
    --rename test/iopad30_ihp.rename.json "$GDS" -o test/iopad30_ihp.em.gds
# -> test/iopad30_ihp.em.gds + .em.lyp (+ .em.poly.json)

klayout test/iopad30_ihp.em.gds -l test/iopad30_ihp.em.lyp     # open the heat-map interactively
python3 test/render_em_png.py                                   # klayout render -> test/iopad30_ihp.em.png
python3 test/render_em_poly.py                                  # or a quick SVG view (no klayout)
```

`render_em_png.py` uses klayout's own headless renderer (`klayout.lay.LayoutView`,
no display needed) — the committed `test/iopad30_ihp.em.png` is that image.

Tier layers: `EM_ok` 200 (grey) · `EM_watch` 201 · `EM_over` 202 · `EM_high` 203 ·
`EM_crit` 204 (magenta). The pad lights up magenta on the thin driver-output metal
and stays grey on the wide power straps.

## Caveats (all honest, all in the demo write-up)

- **sky130 has no official EM rules** (periphery rule x.4 is NC) — its built-in table
  is an estimate. **IHP SG13G2 does** (`rules/ihp_sg13g2.em.json`, from the LEF); use
  `--lef`/`--em-rules` for real numbers.
- IHP's LEF gives only the **DC/average** limit, so rms/peak are left unscreened.
- The geometry-realistic sim R still over-estimates scattered supply nets, so the
  driver delivers ~5 mA (below the 30 mA rating); a real field-solver RCX would push
  more current and more segments over.

## The point

Pads are the simple case. The same four steps — extract → drive+simulate
(bfit-accelerated for large circuits) → screen → recolor — run on any design and
any PDK that ships current-density rules.
