#!/usr/bin/env python3
"""Render sar_sweep.json to a two-panel SVG (no matplotlib on this host)."""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
rows = json.load(open(os.path.join(HERE, "sar_sweep.json")))
R = sorted(rows.values(), key=lambda r: r["delta_ps"])
D = [r["delta_ps"] for r in R]

W, H, PW, PH, ML, MR, MT, GAP = 900, 720, 900 - 150, 250, 78, 72, 56, 90
FONT = "font-family='Helvetica,Arial,sans-serif'"


def sx(x):
    return ML + (x - (-85)) / (85 - (-85)) * PW


def liny(v, lo, hi, top):
    return top + PH - (v - lo) / (hi - lo) * PH


def poly(xs, ys, lo, hi, top, color, dash=""):
    pts = " ".join("%.1f,%.1f" % (sx(x), liny(y, lo, hi, top)) for x, y in zip(xs, ys))
    d = " stroke-dasharray='%s'" % dash if dash else ""
    return "<polyline points='%s' fill='none' stroke='%s' stroke-width='2.2'%s/>" % (pts, color, d)


def dots(xs, ys, lo, hi, top, color):
    return "".join("<circle cx='%.1f' cy='%.1f' r='3.2' fill='%s'/>" % (sx(x), liny(y, lo, hi, top), color)
                   for x, y in zip(xs, ys))


def yaxis(lo, hi, top, ticks, color, side, label, fmt="%g"):
    s, x = "", (ML if side == "l" else ML + PW)
    for t in ticks:
        y = liny(t, lo, hi, top)
        anchor = "end" if side == "l" else "start"
        dx = -8 if side == "l" else 8
        s += "<line x1='%d' y1='%.1f' x2='%d' y2='%.1f' stroke='%s' stroke-width='1'/>" % (x - 4, y, x + 4, y, color)
        s += "<text x='%.1f' y='%.1f' font-size='12' fill='%s' text-anchor='%s' %s>%s</text>" % (
            x + dx, y + 4, color, anchor, FONT, fmt % t)
    ymid = top + PH / 2
    xr = ML - 52 if side == "l" else ML + PW + 52
    rot = -90 if side == "l" else 90
    s += "<text x='%.1f' y='%.1f' font-size='13' fill='%s' text-anchor='middle' transform='rotate(%d %.1f %.1f)' %s>%s</text>" % (
        xr, ymid, color, rot, xr, ymid, FONT, label)
    return s


def frame(top, title):
    s = "<rect x='%d' y='%d' width='%d' height='%d' fill='none' stroke='#888' stroke-width='1'/>" % (ML, top, PW, PH)
    for xt in range(-80, 81, 20):
        s += "<line x1='%.1f' y1='%d' x2='%.1f' y2='%d' stroke='#ddd' stroke-width='0.7'/>" % (
            sx(xt), top, sx(xt), top + PH)
        s += "<text x='%.1f' y='%d' font-size='12' fill='#333' text-anchor='middle' %s>%+d</text>" % (
            sx(xt), top + PH + 16, FONT, xt)
    s += "<line x1='%.1f' y1='%d' x2='%.1f' y2='%d' stroke='#333' stroke-width='1.4' stroke-dasharray='5,4'/>" % (
        sx(0), top, sx(0), top + PH)
    s += "<text x='%d' y='%d' font-size='14' font-weight='bold' fill='#111' %s>%s</text>" % (ML, top - 10, FONT, title)
    return s


def vmark(x, top, color, txt, ty):
    return ("<line x1='%.1f' y1='%d' x2='%.1f' y2='%d' stroke='%s' stroke-width='1.2' stroke-dasharray='2,3'/>"
            "<text x='%.1f' y='%d' font-size='11.5' fill='%s' text-anchor='middle' %s>%s</text>"
            % (sx(x), top, sx(x), top + PH, color, sx(x), ty, color, FONT, txt))


S = ["<svg xmlns='http://www.w3.org/2000/svg' width='%d' height='%d' viewBox='0 0 %d %d'>" % (W, H, W, H),
     "<rect width='%d' height='%d' fill='white'/>" % (W, H),
     "<text x='%d' y='26' font-size='16' font-weight='bold' fill='#111' %s>tg15p hop, open-time sweep around the true zero (266.76 ps): the SAR calibration observables [MEASURED]</text>" % (ML - 40, FONT),
     "<text x='%d' y='44' font-size='12' fill='#444' %s>dV=1.0 iso-current row, L=277.8 nH, 8-gate bank; 15 Xyce/PSP103 runs; instrument gate: delta=0 digit-identical to committed tg15p_zcs</text>" % (ML - 40, FONT)]

# panel 1: ring + gap (mV, left), IZ (uA, right)
T1 = MT + 24
RQ = [r["ring_qtr_mV"] for r in R]
GP = [r["gap_pk_end_mV"] for r in R]
IZ = [r["IZ_uA"] for r in R]
lo1, hi1 = -500, 250
S.append(frame(T1, "Panel A - candidate error signals (left mV): ring-quarter sample SIGN-REVERSES; peak-minus-end does NOT"))
zy = liny(0, lo1, hi1, T1)
S.append("<line x1='%d' y1='%.1f' x2='%d' y2='%.1f' stroke='#aaa' stroke-width='1'/>" % (ML, zy, ML + PW, zy))
S.append(poly(D, RQ, lo1, hi1, T1, "#c0392b") + dots(D, RQ, lo1, hi1, T1, "#c0392b"))
S.append(poly(D, GP, lo1, hi1, T1, "#7d3c98", "6,3") + dots(D, GP, lo1, hi1, T1, "#7d3c98"))
lo1r, hi1r = -340, 170                 # uA axis aligned so 0 coincides; covers +151.5
S.append(poly(D, IZ, lo1r, hi1r, T1, "#95a5a6", "2,3"))
S.append(yaxis(lo1, hi1, T1, [-400, -200, 0, 200], "#c0392b", "l", "mV"))
S.append(yaxis(lo1r, hi1r, T1, [-300, -150, 0, 150], "#95a5a6", "r", "I(LT) at open, uA"))
S.append(vmark(-10.5, T1, "#c0392b", "ring crosses 0 at -10.5 ps (pedestal)", T1 + 14))
S.append("<text x='%.1f' y='%.1f' font-size='12' fill='#c0392b' %s>ring_qtr: V(bka)@open+157ps - V(bka)@open;  slope 4.67 mV/ps, monotone -80..+65</text>" % (sx(-78), T1 + PH - 68, FONT))
S.append("<text x='%.1f' y='%.1f' font-size='12' fill='#7d3c98' %s>VBPK - VBEND (peak minus end): min 24 mV at +50, never reverses sign - pre-guessed observable REFUTED</text>" % (sx(-78), T1 + PH - 50, FONT))
S.append("<text x='%.1f' y='%.1f' font-size='12' fill='#7f8c8d' %s>gray: interrupted current IZ (ground truth, -2.09 uA/ps)</text>" % (sx(-78), T1 + PH - 32, FONT))

# panel 2: VBEND (V, left), E_hop (fJ, right)
T2 = T1 + PH + GAP
VB = [r["VBEND"] for r in R]
EH = [r["E_hop_open_fJ"] for r in R]
lo2, hi2 = 0.555, 0.690
lo2r, hi2r = 8.1, 10.1
S.append(frame(T2, "Panel B - what the timing error COSTS: V(bkb) end level (blue) and E_hop (green)"))
S.append(poly(D, VB, lo2, hi2, T2, "#2471a3") + dots(D, VB, lo2, hi2, T2, "#2471a3"))
S.append(poly(D, EH, lo2r, hi2r, T2, "#1e8449", "6,3") + dots(D, EH, lo2r, hi2r, T2, "#1e8449"))
S.append(yaxis(lo2, hi2, T2, [0.56, 0.60, 0.64, 0.68], "#2471a3", "l", "VBEND, V", "%.2f"))
S.append(yaxis(lo2r, hi2r, T2, [8.5, 9.0, 9.5, 10.0], "#1e8449", "r", "E_hop_open, fJ"))
S.append(vmark(14, T2, "#2471a3", "VBEND peak +14 ps", T2 + 14))
S.append(vmark(25, T2, "#1e8449", "E min +25 ps (8.25 fJ)", T2 + 30))
S.append("<text x='%.1f' y='%.1f' font-size='12' fill='#333' %s>shallow basin: +-31 ps around +14 costs &lt;2.2%% VBEND / &lt;4.8%% E - mistiming stays cheap over the whole capture range</text>" % (sx(-78), T2 + PH - 14, FONT))
S.append("<text x='%.1f' y='%d' font-size='13' fill='#111' text-anchor='middle' %s>switch-open time minus true current zero, ps</text>" % (ML + PW / 2, T2 + PH + 40, FONT))
S.append("</svg>")
open(os.path.join(HERE, "sar_observables.svg"), "w").write("\n".join(S))
print("wrote sar_observables.svg")
