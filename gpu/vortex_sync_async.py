#!/usr/bin/env python3
"""Whole-Vortex execute-cluster: synchronous vs bundled-data async comparison,
across activity (duty alpha) and supply voltage, grounded in the add8-anchored
power model (SG13G2 130nm proxy) + the real 40886-cell netlist counts.

Operating-map artifact (energy vs duty x Vdd, interactive):
  https://claude.ai/code/artifact/1c104c1f-27d6-4f4d-b296-c9cf3c890f15

Key insight vs the add8 anchor: the bundled-data delay-line overhead scales as
~3.2/W of the logic energy (W = datapath width), because the matched line shadows
the datapath DELAY (depth) while the logic energy scales with depth*width. The
Vortex's WIDE 32-bit datapaths make the delay line cheap -> the crossover flips
from the narrow add8 (alpha*~0.5) to broad async advantage, because the huge
3828-DFF clock floor dwarfs the small delay-line overhead.
"""
import math

# --- anchored coefficients (add8 transistor MC, SG13G2 1.2V PSP103) ---
E_clk = 0.0282     # pJ / DFF / cycle   (clock floor)
E_cell = 0.0076    # pJ / logic cell    (switch, alpha=1)
E_reg  = 0.045     # pJ / DFF           (register full toggle, alpha=1)

# --- whole-Vortex execute cluster (yosys gate netlist) ---
N_comb = 37058     # combinational cells
N_dff  = 3828      # pipeline registers
depth  = 47        # critical-path logic levels
W_eff  = 24        # effective datapath width (32b datapath + narrower control mix)

def report(W):
    F   = E_clk * N_dff                      # sync clock floor, pJ/cycle (activity-independent)
    D   = E_cell * N_comb + E_reg * N_dff    # dynamic per active op, pJ (logic + register toggle)
    Elog = E_cell * N_comb                   # logic-only energy
    Edl = (3.2 / W) * Elog                   # bundled-data delay-line overhead (shadows datapath depth)
    astar = F / Edl                          # crossover: sync floor == bd delay-line tax
    print("  W_eff=%d:  clock-floor F=%.1f pJ | dynamic D=%.1f pJ | delay-line Edl=%.1f pJ (%.0f%% of logic)"
          % (W, F, D, Edl, Edl/Elog*100))
    print("            crossover alpha* = F/Edl = %.2f  -> %s"
          % (astar, "bundled-data wins at ALL activity (alpha<=1)" if astar >= 1 else "sync wins above alpha*=%.2f"%astar))
    return F, D, Edl

print("="*90)
print("Whole-Vortex execute cluster (37058 comb, 3828 DFF, depth 47) — sync vs bundled-data")
print("="*90)
F, D, Edl = report(W_eff)
print("  sensitivity to datapath width:")
for W in (16, 24, 32, 48):
    Edl_w = (3.2/W)*E_cell*N_comb
    print("    W=%2d -> Edl=%5.1f pJ, alpha*=%.2f %s" % (W, Edl_w, F/Edl_w, "(async always wins)" if F/Edl_w>=1 else ""))

print("\n  ENERGY per cycle vs duty (fair, throughput-independent):")
print("   alpha | sync (pJ) | bundled-data (pJ) | bd saving")
for a in (1.0, 0.5, 0.25, 0.1, 0.03):
    e_sync = F + a*D
    e_bd   = a*(D + Edl)
    print("   %4.2f  |  %7.1f  |     %7.1f       |  %+5.0f%%" % (a, e_sync, e_bd, (e_bd-e_sync)/e_sync*100))

print("\n  DVFS: energy scales as Vdd^2 for BOTH -> alpha* is Vdd-independent; absolute energy drops.")
print("   Vdd  | sync@alpha=0.1 (pJ) | bd@alpha=0.1 (pJ) | note")
for vdd in (1.2, 0.8, 0.6):
    s = (vdd/1.2)**2
    a = 0.1
    print("   %.1f  |      %7.2f       |     %7.2f       | E*Vdd^2 (fmax also drops ~%s)"
          % (vdd, (F+a*D)*s, a*(D+Edl)*s, {1.2:"1x",0.8:"3x",0.6:"18x"}[vdd]))

print(f"""
READ-OUT
  * The 3828-DFF clock floor ({F:.0f} pJ/cyc, burned every cycle) DWARFS the bundled-data
    delay-line tax ({Edl:.0f} pJ, cheap because the 32-bit datapaths are WIDE) -> alpha*={F/Edl:.1f}>1,
    so bundled-data async beats synchronous at EVERY activity level for the whole cluster.
  * The win GROWS as activity falls: ~12% at alpha=1, ~68% at alpha=0.1 -- and a GPGPU
    spends many cycles at low duty (memory stalls, warp divergence, idle SMs), where the
    sync clock floor is pure waste. This is the OPPOSITE of the narrow add8 ripple (alpha*~0.5).
  * DVFS multiplies both by Vdd^2, so the async advantage PERSISTS across the voltage-scaled
    operating range (the older-node power lever). Reliability: both meet yield (graceful to
    sigma_frac 40%); the bundled-data delay line self-times the +24% mismatch guardband for free.
  * Throughput: bundled-data ~77% of sync fmax (delay margin), recovered by GPGPU parallelism.
""")
