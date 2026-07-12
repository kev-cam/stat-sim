#!/usr/bin/env python3
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
"""Render the EM-risk layout to a viewable SVG from the REAL polygon hulls that
klayout2spef --em-layout dumped (iopad30_ihp.em.poly.json) -- the actual pad metal
shapes, coloured by risk tier. This is a faithful view of the recolored layout
(the GDS + .lyp is the primary deliverable to open in klayout); it is NOT the old
bbox redraw. Usage: python3 test/render_em_poly.py [poly.json] [out.svg]"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
POLY = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "iopad30_ihp.em.poly.json")
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "iopad30_ihp.em.svg")
ORDER = ["EM_ok", "EM_watch", "EM_over", "EM_high", "EM_crit"]   # cool first, hot on top
LABEL = {"EM_ok": "ok <0.5x", "EM_watch": "watch <1x", "EM_over": "over <3x",
         "EM_high": "high <10x", "EM_crit": "crit >=10x"}

poly = json.load(open(POLY))
pts = [p for t in poly.values() for pg in t["polys"] for p in pg]
xs, ys = [p[0] for p in pts], [p[1] for p in pts]
minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
W, pad = 860, 44
sc = (W - 2 * pad) / max(maxx - minx, 1e-9)
H = int((maxy - miny) * sc + 2 * pad + 64)
def X(x): return pad + (x - minx) * sc
def Y(y): return H - 64 - pad - (y - miny) * sc          # flip: +y up

b = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
     f'font-family="ui-monospace,Menlo,Consolas,monospace">',
     f'<rect width="{W}" height="{H}" fill="#0d1117"/>',
     f'<text x="{pad}" y="28" fill="#e6edf3" font-size="17">'
     f'sg13g2_IOPadOut30mA — EM heat-map (klayout polygons, Xyce currents)</text>']
for t in ORDER:                                          # draw cool tiers under hot ones
    if t not in poly:
        continue
    col = poly[t]["rgb"]
    op = 0.55 if t == "EM_ok" else 0.9
    for pg in poly[t]["polys"]:
        d = "M" + " L".join(f"{X(x):.1f},{Y(y):.1f}" for x, y in pg) + " Z"
        b.append(f'<path d="{d}" fill="{col}" fill-opacity="{op}" stroke="{col}" stroke-width="0.4"/>')
# legend
ly = H - 30
b.append(f'<text x="{pad}" y="{ly-6}" fill="#9aa4ad" font-size="12">'
         f'EM risk  I / Imax  (Xyce transient; grey = within limit)</text>')
for i, t in enumerate(ORDER):
    x = pad + i * 168
    c = poly.get(t, {}).get("rgb", "#565b61")
    b.append(f'<rect x="{x}" y="{ly}" width="15" height="15" fill="{c}"/>'
             f'<text x="{x+21}" y="{ly+12}" fill="#c9d1d9" font-size="12">{LABEL[t]}</text>')
b.append("</svg>")
open(OUT, "w", encoding="utf-8").write("\n".join(b))
print(f"wrote {OUT} ({sum(len(v['polys']) for v in poly.values())} polygons, "
      f"{maxx-minx:.0f}x{maxy-miny:.0f} um)")
