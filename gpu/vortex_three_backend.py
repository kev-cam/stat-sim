#!/usr/bin/env python3
"""Whole-Vortex three-backend energy map: static / bundled-data async / QAL.
Extends vortex_sync_async.py with the QAL curve from QAL_PLAN.md sec.6.

Interactive three-backend operating-map artifact (energy vs duty, α* boundary, QAL-swing slider):
  https://claude.ai/code/artifact/7108af61-f898-4823-8148-274774ad322e

  static(a) = clock_floor + a*dynamic          (add8-anchored; a = duty)
  async(a)  = a*(dynamic + delay_line)         (add8-anchored; no clock floor)
  QAL       = 2*(RC/T)/eta * dynamic * (dV/Vdd)^2   (ACTIVITY-INDEPENDENT: the rail
              ramps every cycle; adiabatic recovery + low-swing dV^2; no clock, no FF)

QAL coefficients (RC/T, eta, dV) are ILLUSTRATIVE per QAL_PLAN sec.7 -- the real values
come from A2/A4/C5. static/async coefficients are transistor-anchored (add8, SG13G2 1.2V).
Energy-per-cycle only: QAL's generator tax, ~2x area, and 2N-phase latency are separate axes.
"""
F, D, Edl = 107.9, 453.9, 37.6          # clock floor, dynamic, delay-line (pJ) -- add8-anchored
RCT, ETA = 0.05, 0.5                     # QAL illustrative (QAL_PLAN sec.6 defaults)

def static(a): return F + D*a
def asyncbd(a): return (D + Edl)*a
def qal(sv): return 2*(RCT/ETA) * D * sv*sv        # sv = dV/Vdd (swing fraction)

print("="*84)
print("Vortex three-backend energy/cycle: static vs bundled-data async vs QAL")
print("="*84)
print("  static = %.1f floor + %.1f*a  |  async = %.1f*a  |  QAL = 0.2*%.1f*(dV/Vdd)^2 (flat)"
      % (F, D, D+Edl, D))
print("\n  QAL swing dV/Vdd -> QAL energy (pJ, flat) and async/QAL crossover a_crit:")
for sv in (1.0, 0.7, 0.5, 0.3):
    q = qal(sv); acrit = q/(D+Edl)
    print("    dV/Vdd=%.1f -> QAL=%6.1f pJ | a_crit(async/QAL)=%.1f%%  (< a_crit: async; > a_crit: QAL)"
          % (sv, q, acrit*100))
print("  (dV/Vdd=1.0 gives a_crit=18.5%% ~ QAL_PLAN's ~20%% illustration; lower swing pushes it down)")

print("\n  ENERGY per cycle vs duty (dV/Vdd=1.0), and the winning backend:")
print("   alpha | static | async  |  QAL  | winner")
for a in (1.0, 0.5, 0.25, 0.1, 0.05, 0.02):
    s, y, q = static(a), asyncbd(a), qal(1.0)
    w = min([("static",s),("async",y),("QAL",q)], key=lambda t:t[1])[0]
    print("   %5.2f | %6.1f | %6.1f | %5.1f | %s" % (a, s, y, q, w))

print("""
READ-OUT
  * STATIC is dominated everywhere: its clock floor (108 pJ) alone exceeds QAL, and async
    beats it at every duty -- static pays a floor AND full CV^2 with no recovery.
  * ASYNC wins the DARK-SILICON tail (duty < a_crit ~= 18% at full swing): energy -> 0 as
    activity -> 0, because there is no clock and nothing switches.
  * QAL wins the BUSY regime (duty > a_crit): activity-independent adiabatic energy, so at
    100% duty it pays ~0.2*(dV/Vdd)^2 of the switching energy while static/async pay it all.
  * Lower QAL swing (dV/Vdd) drops the QAL line and pushes a_crit down -> QAL wins over more
    of the range (the dV^2 headline). The exact a_crit awaits A-track (A2/A4/C5) measurement.
  * This is ENERGY/cycle only. QAL also carries a generator tax (SC/inductive), ~1.5-2x area,
    and +2N-phase latency (hidden by SIMT multithreading on a GPGPU) -- separate axes, per plan sec.7.
  Net: async for dark silicon, QAL for what never stops -- complementary, static beaten by both.
""")
