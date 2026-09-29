#!/usr/bin/env python3
"""(e) THE COMPOSITION, recomputed by the skeptic from both tracks.

Everything here is either MEASURED (named row + file), DERIVED (arithmetic on
measured values, labelled), or ASSUMED (labelled).  Nothing is taken from either
track's prose.
"""
CMOS_LEVEL_PS = 94.174        # MEASURED qal/vtreq/cm_d000.cir.mt0 T901P26P91R - 100 ps
CMOS_E_120 = 40.9815          # MEASURED tsweep/rowd/cm_anch_v120.json, 8 cells, CL=2fF, 1.2V
CMOS_E_100 = 30.1626          # MEASURED tsweep/rowd/cm_*_v100, iso-voltage control

# ---- Track A, the 6-bank RESERVOIR CHAIN (the only config where the fade stops)
#      dV = 1.2 V, CL = 2.0 fF, 8 cells/bank -- IDENTICAL cells/load/voltage to the
#      CMOS comparator above (verified: rest.py WP/WN/CLOAD/DV vs tsw.py + tb.py).
TANK_FF = 719.58              # MEASURED
V0, V6 = 1.200, 0.341068      # MEASURED tank start / end (chaind/res20.json)
NHOP = 6
BEAT_PS = 300.0               # the chain's per-stage beat (pre-registered schedule)

dQ = TANK_FF * (V0 - V6)
dE = 0.5 * TANK_FF * (V0 * V0 - V6 * V6)
print("=" * 104)
print("(e) COMPOSITION -- recomputed independently by the skeptic")
print("=" * 104)
print("RESERVOIR CHAIN, MEASURED from the tank's own terminal voltage:")
print("   tank %.2f fF, %.4f -> %.6f V over %d hops" % (TANK_FF, V0, V6, NHOP))
print("   charge drawn   %8.2f fC total = %7.2f fC / bank-hop" % (dQ, dQ / NHOP))
print("   ENERGY drawn   %8.2f fJ total = %7.2f fJ / bank-hop   <-- MEASURED" % (dE, dE / NHOP))
E_tank = dE / NHOP

print()
print("CMOS comparator, MEASURED on the SAME 8 cells, SAME CL = 2 fF, SAME 1.2 V:")
print("   %.4f fJ per 8-cell transition   (T-INVARIANT: 42.54 -> 43.27 fJ over a 10x")
print("   period range, and identical to 6 s.f. from 506 ps on -- so this number does")
print("   not move when QAL slows down, and every ratio below is like-for-like.)"
      % ())
print("   value used: %.4f fJ (campaign 34.81 ps edge convention)" % CMOS_E_120)

print()
print("-" * 104)
print("PER-OP DRIVER LADDER.  A SHARED TANK NEEDS TWO transmission gates per hop")
print("(source-side cut + receiving-side cut).  The committed ledgers were measured")
print("for the ONE-cut committed topology, so the reservoir's floor is taken as 2x.")
print("The 2x is DERIVED by gate count, NOT re-measured -- flagged as such.")
print("-" * 104)
LADDER = [
    ("ideal-PWL, as the harness drives it (MEASURED, LOWER BOUND)", 17.456, False),
    ("resonant gt/gtp pair 2.974 fJ x2 cuts (COMMITTED, x2 DERIVED)", 5.948, True),
    ("75%-recovery resonant driver 10.9 fJ x2 (COMMITTED-DERIVED, never built)", 21.8, True),
    ("COMPLETE timer ledger 23.213 fJ x2 cuts (the only COMPLETE one)", 46.426, True),
    ("conventional CMOS driver off 1.5 V, 43.5 fJ x2 (COMMITTED)", 87.0, True),
]
print("%-72s %9s %9s %8s" % ("driver rung", "E_QAL", "vs CMOS", "verdict"))
for name, drv, _d in LADDER:
    q = E_tank + drv
    r = CMOS_E_120 / q
    print("%-72s %9.2f %8.3fx %8s"
          % (name, q, r, "QAL wins" if r > 1 else "QAL LOSES"))
print()
print("NOTE the ideal-PWL rung already uses the MEASURED E_gate_drive of the")
print("actual 2-cut reservoir deck (rowd/SC_m20_L3.json = 17.456 fJ), so that rung")
print("is measured, not doubled.")

print()
print("-" * 104)
print("SPEED SIDE")
print("-" * 104)
print("  CMOS logic level (same convention)                  : %8.3f ps  MEASURED" % CMOS_LEVEL_PS)
print("  best IN-ENVELOPE shared-tank-realisable single hop  : %8.3f ps  MEASURED"
      % 103.378)
print("       (CA_MULT=20, L=3 nH, W=30um, dV=1.65, cl=6.91fF; VBPK 1.5498 V, 6%% margin)")
print("       -> %.3fx of CMOS, i.e. CMOS is %.1f%% FASTER" % (CMOS_LEVEL_PS / 103.378,
                                                              100 * (103.378 / CMOS_LEVEL_PS - 1)))
print("  the CHAIN's actual per-stage beat                   : %8.3f ps  (schedule)" % BEAT_PS)
print("       -> %.2fx SLOWER than the CMOS level" % (BEAT_PS / CMOS_LEVEL_PS))
print("       and at depth 5/6 even 300 ps is NOT enough (see settling audit), so")
print("       300 ps is a LOWER bound on the usable beat at depth, not an upper one.")

print()
print("-" * 104)
print("ISO-PERFORMANCE?")
print("-" * 104)
print("  There is NO measured QAL operating point at or below %.3f ps:" % CMOS_LEVEL_PS)
print("    Track A, shared-tank-realisable, in envelope : best 103.378 ps  (0.911x)")
print("    Track A, receiving-cut-only (NOT chain-legal): best  70.209 ps  (1.341x)")
print("    Track B, dV = 1.0, functional                : best 176.9   ps  (0.532x)")
print("  => the iso-performance energy ratio CANNOT BE FORMED FROM MEASUREMENT.")
print("     Everything below is a BOUND at the fastest legal point, not a result.")

print()
print("ENERGY-DELAY at the fastest legal reservoir point, against CMOS:")
for name, drv, _d in LADDER:
    q = E_tank + drv
    ed_e = q / CMOS_E_120
    ed_t = BEAT_PS / CMOS_LEVEL_PS
    print("   %-64s E %5.2fx  x  T %4.2fx  =  E*T %6.2fx worse"
          % (name[:64], ed_e, ed_t, ed_e * ed_t))

print()
print("-" * 104)
print("DOES THE 1/T KNOB RESCUE IT?  (Track B, re-fit independently)")
print("-" * 104)
print("  E_hop over the WHOLE 24.3x functional T range: 9.273 -> 7.357 fJ = 1.260x.")
print("  So the entire speed-for-energy trade is worth 1.26x.")
print("  Moving ONE RUNG of the driver ladder above is worth up to %.2fx."
      % ((E_tank + LADDER[-1][1]) / (E_tank + LADDER[1][1])))
print("  => the driver choice dominates the 1/T knob by ~%.0fx.  DVFS on T cannot"
      % (((E_tank + LADDER[-1][1]) / (E_tank + LADDER[1][1])) / 1.260))
print("     convert a speed gain into an efficiency win here, and there is no speed")
print("     gain in the legal topology to convert.")
