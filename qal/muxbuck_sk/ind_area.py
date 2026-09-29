#!/usr/bin/env python3
"""Independent re-implementation of the IHP-Open-PDK inductor estimator
(libs.tech/klayout/python/sg13g2_pycell_lib/callbacks/inductor_cb.tcl, proc
inductor_L / rEstim) so I can (i) reproduce the balance run's two footprints and
(ii) test how far the area crossover N moves under DIFFERENT winding choices.

All lengths in metres inside, printed in um.
"""
import math

MU = math.pi * 4e-7


def L_of(d_in, w, s, nr):
    """d_in = inner diameter (the PDK's 'd' parameter). Returns H."""
    d_avg_term = d_in + nr * (w + s) - s
    ro = (nr * (w + s) - s) / d_avg_term
    return MU * 0.5 * 1.07 * nr * nr * d_avg_term * (math.log(2.29 / ro) + 0.19 * ro * ro)


def R_of(d_in, w, s, nr):
    return (nr * (d_in + w + (nr - 1) * (s + w)) * 3.314 + 60e-6) / w * 0.01


def d_in_for(L_target, w, s, nr, lo=1e-6, hi=5e-2):
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if L_of(mid, w, s, nr) < L_target:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def geom(L_target, w, s, nr):
    d_in = d_in_for(L_target, w, s, nr)
    radial = nr * (w + s) - s
    d_out = d_in + 2 * radial
    a_oct = 2 * (math.sqrt(2) - 1) * d_out ** 2      # regular octagon, across-flats = d_out
    a_box = d_out ** 2
    return dict(d_in=d_in * 1e6, d_out=d_out * 1e6, A_oct=a_oct * 1e12,
                A_box=a_box * 1e12, R=R_of(d_in, w, s, nr))


U = 1e-6
print("=== REPRODUCTION of the balance run's two footprints (w=2u, s=2.1u, nr=2) ===")
for L, tag in ((1e-9, "1 nH recharge"), (15e-9, "15 nH transfer")):
    g = geom(L, 2 * U, 2.1 * U, 2)
    print(f"{tag:16s} d_in {g['d_in']:9.1f} um  d_out {g['d_out']:9.1f} um  "
          f"A_oct {g['A_oct']:12,.0f} um^2  A_bbox {g['A_box']:12,.0f}  R {g['R']:7.2f} ohm")

print()
print("=== SENSITIVITY: the SAME 1 nH under other legal winding choices ===")
print(f"{'w(um)':>6} {'s(um)':>6} {'nr':>3} {'d_in(um)':>10} {'d_out(um)':>10} {'A_oct(um^2)':>14} {'R(ohm)':>8}")
best = None
for nr in (1, 2, 3, 4, 5, 6, 8):
    for w in (2, 3, 5, 10, 20, 30):
        for s in (2.1,):
            try:
                g = geom(1e-9, w * U, s * U, nr)
            except Exception:
                continue
            if g['d_in'] <= 0.5:      # unphysical / below the PDK's own Dmin
                continue
            print(f"{w:6.1f} {s:6.1f} {nr:3d} {g['d_in']:10.2f} {g['d_out']:10.2f} "
                  f"{g['A_oct']:14,.0f} {g['R']:8.2f}")
            if best is None or g['A_oct'] < best[0]:
                best = (g['A_oct'], w, s, nr, g['R'])
print(f"\nSMALLEST 1 nH found in this grid: {best[0]:,.0f} um^2 at w={best[1]}u s={best[2]}u "
      f"nr={best[3]} (R = {best[4]:.2f} ohm)")

print()
print("=== SENSITIVITY: the SAME 15 nH under other legal winding choices ===")
best15 = None
for nr in (2, 3, 4, 5, 6, 8, 10):
    for w in (2, 3, 5, 10):
        g = geom(15e-9, w * U, 2.1 * U, nr)
        if g['d_in'] <= 0.5:
            continue
        print(f"w={w:4.1f}u nr={nr:2d}  d_out {g['d_out']:9.1f} um  A_oct {g['A_oct']:12,.0f} um^2  R {g['R']:7.2f} ohm")
        if best15 is None or g['A_oct'] < best15[0]:
            best15 = (g['A_oct'], w, nr, g['R'])
print(f"\nSMALLEST 15 nH found: {best15[0]:,.0f} um^2 at w={best15[1]}u nr={best15[2]} (R = {best15[3]:.2f} ohm)")
