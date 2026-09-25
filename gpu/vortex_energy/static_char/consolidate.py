#!/usr/bin/env python3
"""Consolidated per-island STATIC vector + the two DERIVED fields the rule needs.

W_eff = N_comb / D   -- average level population = the number of gates that settle
in parallel per logic level. This is the MEASURED replacement for the ASSUMED
W_eff = 24 at stat-sim/gpu/vortex_sync_async.py:27, and it is exactly the quantity
the bundled-data delay-line term amortizes over (vortex_sync_async.py:33 uses
Edl = (3.2/W)*Elog).

cyc_frac = registers that sit on a register-to-register dependency CYCLE / all
registers. A binary CYCLIC flag over-reports: most islands are feed-forward
except a small control core. This fraction says how much of the island must fall
back to --reg desync (matched delay) instead of --reg qdi (map_ncl_struct.py:342).
"""

# (island, ncomb, nseq, nmem, mux, D, regs_in_cycles, cut_bits_at_own_depth)
# all MEASURED from vortex_flat.json / vortex_hier.json this session
ROWS = [
    ("WHOLE CHIP",            291608, 35004, 90, 126649, 148, 2694, 1183),
    ("CORE (whole)",          227335, 22161, 60,  72293, 148, 2149, 1928),
    ("  execute (whole)",     182473, 14862, 28,  44597, 148,  776, 3764),
    ("    alu_unit",           45704,  2408,  0,   4485,  46,  144, None),
    ("      alu_int",           4145,   247,  0,   1544,  19,    0, None),
    ("      muldiv",           40421,  1809,  0,   1826,  46,  141, None),
    ("    fpu_unit (fpnew)",  126333,  8732, 25,  33623, 148,  521, None),
    ("    lsu_unit",            5259,  2051,  1,   2874,  28,   25, None),
    ("    sfu_unit",            5167,  1667,  2,   3612,  24,   82, None),
    ("  issue",                16777,  4240,  6,   8839,  21,  742, 2997),
    ("  schedule",              5740,   189,  5,   3544,  32,   73, None),
    ("  fetch",                 1700,    68,  0,   1156,  21,    1, None),
    ("  decode",                1021,     0,  1,     92,  21,    0, None),
    ("  commit",                3196,   160,  1,   2751,  13,    3, 1091),
    ("  lmem_unit",             6917,  2042,  4,   6274,  17,   42,  948),
    ("  mem_coalescer",         4371,   232,  0,   2475,  21,  196,  739),
    ("DCACHE",                 38516,  8233, 24,  30429,  27,  411, 1924),
    ("ICACHE",                  2706,  1290,  6,   1011,  27,  101, 1254),
    ("SOCKET mem_arb",         18058,  3315,  0,  17997,  10,    9, 1845),
    ("L2",                      4909,     0,  0,   4906,  10,    0, 1241),
    ("L3 (bypassed at NC=1)",      7,     0,  0,      6,   2,    0, 1241),
]

# campaign anchors
E_CLK  = 0.0282     # pJ/DFF/cycle  [vortex_sync_async.py:19]  MEASURED (add8-anchored)
E_CELL = 0.0076     # pJ/logic cell [vortex_sync_async.py:20]
E_REG  = 0.045      # pJ/DFF        [vortex_sync_async.py:21]
K_DL_2PH = 7.5      # delay-line coefficient, 2-phase   (brief: 3.2 is 2.35x too cheap)
K_DL_4PH = 15.1     # delay-line coefficient, 4-phase   (brief: 3.2 is 4.71x too cheap)
K_DL_ASIS = 3.2     # as coded at vortex_sync_async.py:33

SHA_N, SHA_D = 105, 10     # [work/levels.json] MEASURED

print("=" * 128)
print("PER-ISLAND STATIC VECTOR  (Vortex 'mini': 1 cluster / 1 core / 4 warps / 4 threads; "
      "rtlmeter descriptor.yaml configurations.mini)")
print("=" * 128)
h = ("%-22s %8s %7s %5s %7s %5s %5s %7s %8s %7s %8s" %
     ("island", "comb", "seq", "mem", "mux", "mux%", "D", "W_eff", "seq_frac", "cyc_fr", "cut_bits"))
print(h); print("-" * len(h))
for name, nc, ns, nm, mx, D, cyc, cut in ROWS:
    W = nc / D if D else 0
    sf = 100.0 * ns / (nc + ns) if nc + ns else 0
    cf = 100.0 * cyc / ns if ns else 0.0
    print("%-22s %8d %7d %5d %7d %4.1f%% %5d %7.0f %7.1f%% %6.1f%% %8s"
          % (name, nc, ns, nm, mx, 100.0*mx/nc if nc else 0, D, W, sf, cf,
             cut if cut is not None else "-"))

print()
print("=" * 128)
print("DERIVED: bundled-data DELAY-LINE tax, Edl/Elog = K/W_eff   "
      "(the whole point: W_eff is 35-75x larger than the ASSUMED 24)")
print("=" * 128)
print("%-22s %7s %10s %12s %12s %12s" %
      ("island", "W_eff", "vs sha", "K=3.2 (as-is)", "K=7.5 (2ph)", "K=15.1 (4ph)"))
print("-" * 80)
shaW = SHA_N / SHA_D
print("%-22s %7.1f %10s %11.1f%% %11.1f%% %11.1f%%"
      % ("sha_slice (the toy)", shaW, "1.0x",
         100*K_DL_ASIS/shaW, 100*K_DL_2PH/shaW, 100*K_DL_4PH/shaW))
for name, nc, ns, nm, mx, D, cyc, cut in ROWS:
    W = nc / D if D else 0
    if W < 1:
        continue
    print("%-22s %7.0f %9.0fx %11.2f%% %11.2f%% %11.2f%%"
          % (name, W, W/shaW, 100*K_DL_ASIS/W, 100*K_DL_2PH/W, 100*K_DL_4PH/W))

print()
print("=" * 128)
print("DERIVED: clock floor vs delay-line tax -- the crossover the model computes")
print("  F    = E_clk * N_dff                      (sync clock floor, pJ/cycle, activity-independent)")
print("  Elog = E_cell * N_comb ; Edl = (K/W)*Elog (bundled-data delay-line tax, pJ per op)")
print("  alpha* = F / Edl : below this activity the sync clock floor exceeds the async delay line")
print("=" * 128)
print("%-22s %10s %10s %10s %12s" % ("island", "F (pJ/cyc)", "Elog (pJ)", "Edl(4ph)", "alpha*"))
print("-" * 70)
for name, nc, ns, nm, mx, D, cyc, cut in ROWS:
    W = nc / D if D else 0
    if W < 1 or ns == 0:
        continue
    F = E_CLK * ns
    Elog = E_CELL * nc
    Edl = (K_DL_4PH / W) * Elog
    a = F / Edl if Edl else float("inf")
    print("%-22s %10.2f %10.2f %10.3f %12s"
          % (name, F, Elog, Edl,
             ("%.2f" % a) if a < 1 else ">1 (bd wins at ALL activity)"))
