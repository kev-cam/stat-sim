#!/usr/bin/env python3
"""Energy-vs-duty COMPOSITION for full SHA-256 as a self-timed static-CMOS FSM.

Composes the per-round and whole-hash energy of a round-iterative SHA-256 core from
MEASURED transistor anchors, and prints the clocked-golden vs self-timed ledger across
duty. The approach under test (MEASURED on a 4-bit accumulator, FSM_NUMBERS.txt):
a self-timed static-CMOS FSM holds state and dissipates only on transitions, so it
sheds the clock floor at low duty -> a DUTY-SHAPED lower-power win; per-op it is
~parity with clocked CMOS. This script asks what that means for a register-heavy
crypto round.

PROVENANCE TAGS on every figure:
  [MEAS]     measured on SG13G2/PSP103 transistors (Xyce), this campaign
  [COMPOSED] derived this session: yosys synth (same recipe as the sha_slice anchor)
             + OpenSTA, scaled by the [MEAS] sha_slice per-area/per-cell energy
  [EST]      honest structural estimate (flop count, activity factor, detector cost)

Run:  python3 compose_sha256.py
No SPICE is launched here. The round/schedule equations behind the synthesized cell
counts are the verified SHA-256 round (work/verify_round_eqs.py: PASS vs hashlib).
"""

# ============================================================================
# 1. MEASURED ANCHORS  [MEAS]
# ============================================================================
E_SHA_SLICE   = 232.0    # fJ/op, static-CMOS 8b round core {maj,ch,add} @ alpha=0.476
A_SHA_SLICE_M = 627.78   # um^2, the MEASURED deck (56 cells)                     [MEAS]
N_SHA_SLICE_M = 56       # cells, the MEASURED deck                              [MEAS]
T_SHA_SLICE   = 0.928    # ns, sha_slice CMOS critical path                      [MEAS]
E_CLK         = 28.2     # fJ/DFF/cycle  (clock-pin+internal, idle)              [MEAS add8]
E_REGTOG      = 45.0     # fJ/DFF/toggle (Q switches + its load)                 [MEAS add8]
SYNC8_IDLE    = 255.0    # fJ, 9-DFF idle floor -> 28.3 fJ/DFF (confirms E_CLK)  [MEAS]
# accumulator duty sweep (golden/self-timed energy ratio), for sanity:          [MEAS]
ACC_RATIO     = {1: 0.44, 4: 0.89, 10: 1.88}
E_CMP_DONE    = (144.0, 400.0)   # fJ, per-op analog completion comparator       [MEAS/EST]
E_DLINE_ADD8  = 500.0    # fJ for a 1.97 ns (44-inv) replica delay line          [MEAS add8]
T_DLINE_ADD8  = 1.968    # ns that 500 fJ line spans -> 254 fJ/ns of replica

# ============================================================================
# 2. SYNTHESIZED STRUCTURE  [COMPOSED]  (yosys, same recipe as the anchor; this session)
#    recipe: synth -flatten; abc -liberty sg13g2_typ_1p20V_25C; opt_clean; stat
# ============================================================================
N_SHA_SLICE_S = 63       # cells, sha_slice re-synth (my recipe) -> calibration basis
A_SHA_SLICE_S = 644.11   # um^2
N_ROUND       = 1328     # cells, sha256_round_dp (full 32b round next-state logic)
A_ROUND       = 14458.95 # um^2
T_ROUND       = 5.638    # ns, round_dp critical path (ripple-carry synth; OpenSTA)
N_SCHED       = 557      # cells, sha256_msgsched (W[t] from the 16-word window)
A_SCHED       = 6475.56  # um^2
T_SCHED       = 4.251    # ns, schedule critical path (OpenSTA)

# ============================================================================
# 3. STRUCTURAL ESTIMATES  [EST]
# ============================================================================
N_FLOP_AH     = 8 * 32   # a..h working registers                               = 256
N_FLOP_W      = 16 * 32  # W[t-16..t-1] schedule window (shift register)         = 512
N_FLOP_CTR    = 6        # round counter 0..63
N_FLOP        = N_FLOP_AH + N_FLOP_W + N_FLOP_CTR                                # = 774
ALPHA_TOG     = 0.50     # fraction of flops toggling per active round (random data)
SCHED_ACTIVE  = 48 / 64  # schedule computes only rounds 16..63; 0..15 just load
N_ROUNDS      = 64

# --- per-cell / per-area energy from the MEASURED sha_slice, SAME-recipe basis ---
e_per_cell = E_SHA_SLICE / N_SHA_SLICE_S          # fJ/cell/op  (recipe-consistent)
e_per_area = E_SHA_SLICE / A_SHA_SLICE_S          # fJ/um^2/op

def comb_energy(ncells, area):
    """Composed combinational energy (fJ/op): bracket = [cell-scaled, area-scaled]."""
    return ncells * e_per_cell, area * e_per_area

# ============================================================================
# 4. COMPOSE per-round and per-hash active energy
# ============================================================================
r_cell, r_area = comb_energy(N_ROUND, A_ROUND)        # round_dp combinational
s_cell, s_area = comb_energy(N_SCHED, A_SCHED)         # schedule combinational
E_comb_round = (r_cell + r_area) / 2                   # fJ, midpoint
E_comb_sched = (s_cell + s_area) / 2
E_cap_round  = N_FLOP * (E_CLK + ALPHA_TOG * E_REGTOG) # fJ, capture all state once
E_active_round = E_comb_round + E_comb_sched * SCHED_ACTIVE + E_cap_round   # fJ/round

# whole hash (one 512b block = 64 rounds; schedule active 48 of them)
E_hash_comb = N_ROUNDS * E_comb_round + 48 * E_comb_sched
E_hash_cap  = N_ROUNDS * E_cap_round
E_hash      = E_hash_comb + E_hash_cap                 # fJ/hash (active, duty-flat)

# clock floor the self-timed form SHEDS: every flop clocked every idle cycle
E_IDLE_CYC  = N_FLOP * E_CLK                           # fJ/idle-cycle

F_ROUND = 1.0 / (T_ROUND * 1e-9)                       # Hz, back-to-back round rate

def duty_to_idle_cycles(d):
    # active = 64 rounds; total cycles = 64/d; idle = 64*(1-d)/d
    return N_ROUNDS * (1 - d) / d

def energy_per_hash(d, e_det_fJ=0.0, gate_residual=1.0):
    """Returns (E_clocked, E_selftimed) in fJ/hash at duty d.
    e_det_fJ: self-timed completion-detector cost per round.
    gate_residual: clocked idle-clock fraction NOT removed by clock-gating (1 = none)."""
    idle = duty_to_idle_cycles(d)
    e_clk = E_hash + idle * E_IDLE_CYC * gate_residual
    e_st  = E_hash + N_ROUNDS * e_det_fJ
    return e_clk, e_st

def power(d, e_det_fJ=0.0, gate_residual=1.0):
    """Average power (W) at a fixed round rate F_ROUND (clock runs continuously for the
    clocked part; self-timed quiesces between bursts). Throughput matched at duty d."""
    # per-cycle: active round costs E_active_round; idle cycle costs E_IDLE_CYC (clk only)
    p_clk = F_ROUND * (E_active_round * d + E_IDLE_CYC * gate_residual * (1 - d)) * 1e-15
    p_st  = F_ROUND * ((E_active_round + e_det_fJ) * d) * 1e-15
    return p_clk, p_st


def banner(s):
    print("\n" + "=" * 78 + "\n" + s + "\n" + "=" * 78)


if __name__ == "__main__":
    banner("SHA-256 as a self-timed static-CMOS FSM  -  ENERGY-vs-DUTY COMPOSITION")
    print("SG13G2 130nm / PSP103 / 1.2V. Figures tagged [MEAS]/[COMPOSED]/[EST].")
    print("Round equations verified vs hashlib (work/verify_round_eqs.py: PASS).")

    banner("A. PER-ROUND / PER-HASH ACTIVE ENERGY  (same for clocked & self-timed)")
    print("per-cell energy  [MEAS/COMPOSED] %.3f fJ/cell  (= %.0f fJ / %d cells, my-recipe)"
          % (e_per_cell, E_SHA_SLICE, N_SHA_SLICE_S))
    print("per-area energy  [MEAS/COMPOSED] %.4f fJ/um^2 (= %.0f fJ / %.1f um^2)"
          % (e_per_area, E_SHA_SLICE, A_SHA_SLICE_S))
    print("%-42s %10s %10s" % ("block [COMPOSED]", "cell-scaled", "area-scaled"))
    print("%-42s %9.0ffJ %9.0ffJ  x%.1f area vs sha_slice"
          % ("  round_dp  (1328 cells, full 32b round)", r_cell, r_area, A_ROUND/A_SHA_SLICE_S))
    print("%-42s %9.0ffJ %9.0ffJ  x%.1f area vs sha_slice"
          % ("  msgsched  (557 cells, W schedule)", s_cell, s_area, A_SCHED/A_SHA_SLICE_S))
    print("-" * 66)
    print("E_comb_round   [COMPOSED] %7.0f fJ  (round_dp, midpoint)" % E_comb_round)
    print("E_comb_sched   [COMPOSED] %7.0f fJ  (x %.2f active = %.0f fJ/round avg)"
          % (E_comb_sched, SCHED_ACTIVE, E_comb_sched * SCHED_ACTIVE))
    print("E_cap_round    [EST]      %7.0f fJ  (%d flops x (%.1f + %.2f*%.0f) fJ, alpha_tog=%.2f)"
          % (E_cap_round, N_FLOP, E_CLK, ALPHA_TOG, E_REGTOG, ALPHA_TOG))
    print("                          %s" %
          ("state = 256 (a..h) + 512 (W window) + 6 (ctr) = %d flops [EST]" % N_FLOP))
    print("-" * 66)
    print("E_active_round [COMPOSED] %7.0f fJ/round   (logic %.0f%%, registers %.0f%%)"
          % (E_active_round,
             100*(E_comb_round+E_comb_sched*SCHED_ACTIVE)/E_active_round,
             100*E_cap_round/E_active_round))
    print("E_active_hash  [COMPOSED] %7.0f fJ/hash = %.2f nJ / 512b block  (DUTY-FLAT)"
          % (E_hash, E_hash/1e6))
    print("   ** register capture DOMINATES (%.0f%%): SHA state is 774 flops -> a big"
          % (100*E_cap_round/E_active_round))
    print("      clock floor to shed. This is why the duty win is stronger than the toy.")
    print("round critical path [COMPOSED/STA] %.2f ns -> round rate %.0f MHz (ripple synth)"
          % (T_ROUND, F_ROUND/1e6))

    banner("B. CLOCK FLOOR the self-timed form SHEDS  [MEAS coefficient]")
    print("E_idle_cycle = %d flops x %.1f fJ(E_clk) = %.2f pJ / idle cycle  [MEAS/EST]"
          % (N_FLOP, E_CLK, E_IDLE_CYC/1e3))
    print("floor / active-round = %.2f / %.1f = %.3f  (accumulator was ~0.22; SHA is"
          % (E_IDLE_CYC/1e3, E_active_round/1e3, E_IDLE_CYC/E_active_round))
    print("   bigger because it is register-heavy -> a LARGER relative floor to delete)")

    banner("C. ENERGY & POWER vs DUTY   (clocked-golden free-running vs self-timed)")
    print("duty d = active-round fraction. WITHIN a hash d~1 (every round active) -> NO")
    print("win there; the win is BETWEEN blocks/messages (idle). Detector = 0 here.")
    print("%-9s %13s %13s %8s %11s %11s %8s" %
          ("duty", "E_clk nJ/hash", "E_st nJ/hash", "E ratio", "P_clk mW", "P_st mW", "P ratio"))
    for d in (1.0, 0.5, 0.1, 0.01, 0.001):
        ec, es = energy_per_hash(d)
        pc, ps = power(d)
        print("%-9s %13.2f %13.2f %7.2fx %11.3f %11.4f %7.2fx"
              % (("%.3g" % d), ec/1e6, es/1e6, ec/es, pc*1e3, ps*1e3, pc/ps))
    print("clocked power never falls below the floor P_floor = %.3f mW (clock keeps running);"
          % (F_ROUND * E_IDLE_CYC * 1e-15 * 1e3))
    print("self-timed power -> leakage as d->0. Crossover: parity at d=1, self-timed wins")
    print("for ALL d<1 (no per-op penalty once the detector is cheap -- see D).")

    banner("D. CHARGE THE COMPLETION-DETECTOR FLOOR  [EST]  (the QAL guardrail)")
    print("Self-timed pays a 'done' every ACTIVE round x64, recovered by shed idle clock.")
    print("Break-even: E_det < E_idle_cycle * (1-d)/d = %.1f*(1-d)/d fJ/round." % E_IDLE_CYC)
    print("Max tolerable detector & crossover duty d* = floor/(floor+E_det):")
    dets = [("embedded/sparse tap", 50.0),
            ("in-kind replica slice (round/32)", N_ROUND/32*e_per_cell),
            ("per-op analog comparator (lo)", E_CMP_DONE[0]),
            ("per-op analog comparator (hi)", E_CMP_DONE[1]),
            ("full buffer replica line (5.6ns)", T_ROUND * (E_DLINE_ADD8/T_DLINE_ADD8))]
    print("%-38s %10s %9s %12s" % ("detector [EST]", "E_det fJ", "d*", "penalty@d=1"))
    for nm, ed in dets:
        dstar = E_IDLE_CYC / (E_IDLE_CYC + ed)
        pen = N_ROUNDS * ed / E_hash
        print("%-38s %10.0f %8.4f %11.2f%%" % (nm, ed, dstar, 100*pen))
    print("** Even the priciest replica (d*=0.94) and the 're-dominating' comparator")
    print("   (d*=0.98) still win across almost the whole sub-unity duty range: SHA's")
    print("   774-flop clock floor (21.8 pJ/cyc) dwarfs any detector (<=1.4 pJ). The")
    print("   QAL-cliff that killed the 4-flop accumulator does NOT bite SHA-256.")

    banner("E. HONESTY: vs a CLOCK-GATED CMOS opponent  [EST sensitivity]")
    print("The free-running baseline (A-D) is the naive clocked core. A clock-gated CMOS")
    print("core recovers most of the idle floor too; residual r = idle-clock NOT gated")
    print("(clock-tree root + ICG + leaf). Energy ratio = 1 + r*%.3f*(1-d)/d."
          % (E_IDLE_CYC/E_active_round))
    print("%-10s %12s %12s %12s" % ("duty", "r=1 (none)", "r=0.3", "r=0.1 (good)"))
    for d in (0.5, 0.1, 0.01):
        row = [1 + r * (E_IDLE_CYC/E_active_round) * (1-d)/d for r in (1.0, 0.3, 0.1)]
        print("%-10s %11.2fx %11.2fx %11.2fx" % (("%.3g" % d), *row))
    print("'gating quality is the entire CMOS game' [[threeway_gals_campaign]]: self-timed")
    print("still wins, but against GOOD gating the margin is ~r smaller + leakage-capped.")

    banner("BOTTOM LINE")
    print("Self-timed static-CMOS SHA-256 LOWERS POWER in the IDLE/INTERMITTENT regime,")
    print("NOT in sustained hashing. At d=1 (back-to-back) it is ~parity (loses only the")
    print("<1%% detector overhead). The win grows with idle: ~%.1fx energy/hash at d=0.1,"
          % (energy_per_hash(0.1)[0]/energy_per_hash(0.1)[1]))
    print("~%.0fx at d=0.01, vs a free-running clock; ~%.1fx / ~%.1fx vs GOOD (r=0.1)"
          % (energy_per_hash(0.01)[0]/energy_per_hash(0.01)[1],
             1+0.1*(E_IDLE_CYC/E_active_round)*(1-0.1)/0.1,
             1+0.1*(E_IDLE_CYC/E_active_round)*(1-0.01)/0.01))
    print("clock-gating. Register-heavy state (774 flops) makes the floor large and the")
    print("detector negligible -> SHA is a BETTER fit for self-timed than the accumulator.")
    print("Real continuous-miner / streaming SHA sits at d~1 => no win there; the target")
    print("is bursty/event-driven hashing (wake, hash a message, sleep).")
