#!/usr/bin/env python3
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
"""Render the EM heat-map layout (GDS + .lyp from klayout2spef --em-layout) to a
PNG with klayout's own renderer -- headless, no display needed. Run with a
klayout-enabled python (e.g. clevo `/home/claude/klvenv/bin/python3`):

    python3 test/render_em_png.py [in.gds] [in.lyp] [out.png] [width] [height]
"""
import sys
import klayout.lay as klay

gds = sys.argv[1] if len(sys.argv) > 1 else "test/iopad30_ihp.em.gds"
lyp = sys.argv[2] if len(sys.argv) > 2 else "test/iopad30_ihp.em.lyp"
png = sys.argv[3] if len(sys.argv) > 3 else "test/iopad30_ihp.em.png"
W = int(sys.argv[4]) if len(sys.argv) > 4 else 1000
H = int(sys.argv[5]) if len(sys.argv) > 5 else 2250

lv = klay.LayoutView()
lv.set_config("background-color", "#0d1117")
lv.set_config("grid-visible", "false")
lv.set_config("text-visible", "false")
lv.load_layout(gds, True)
lv.load_layer_props(lyp)
lv.max_hier()
lv.zoom_fit()
lv.save_image(png, W, H)
print(f"wrote {png} ({W}x{H})")
