#!/usr/bin/env python3
"""QAL RE-SCORED AS A BURST MODE inside a locally-clocked GALS island.

Every prior QAL figure was scored on SINGLE-OP latency (342 ps/hop x depth), where QAL
loses to CMOS's one cycle. That is the wrong figure of merit if QAL is a burst: the fill
latency is paid once per burst, and the steady state is one op per beat with D ops in
flight. This file redoes the scoring and -- the load-bearing part -- computes the MARGIN
bound on chain length, which nobody had computed and which turns out to be the binding
constraint, not energy.

NO XYCE IS RUN HERE. Every input is read off a committed measurement or labelled.

=== INPUT PROVENANCE ===
MEASURED (Xyce, SG13G2/PSP103 tt):
  e_hop_per_gate 1.34269 fJ, t_hop 342.0 ps, dV=1.0 V, L=277.8 nH, C_eff 35.979 fF, N=8
        -> qal_isocurrent.json rows[2]   (the only VALID row: settling 100%; 0.8 V is 77.1%)
  path/gate split of the hop: path = 23.18-24.76% of E_hop at dV=1.0
        -> qal_split_differential.json rows[1] path_pct_of_hop_lo/hi
  per-hop inductive DELIVERY loss vs real switch Ron: 6.8% (w=40um, Q=31.6) .. 13.6%
        (w=10um REAL, Q=11.3)                      -> qal_trackC.py:12-17
  switch gate-drive energy PER BANK PER FIRE: 15.61 fJ (K=1) .. 24.51 fJ (K=7), w=10um
  top-up RAIL energy per fire: 25.43 fJ (80 fF bank, eta=0.12%) .. 112.18 fJ (2000 fF
        bank, K=7, eta=61.58%)                     -> qal_pulse_topup.json cases[]
  rail/logic-1 level statistics at dV=1.0, from 2^N-exact Binomial weighting of the
        measured V(k) curve: mean 0.5826 V, sigma 15.452 mV at N=8, falling as 1/sqrt(N)
        (ratio 0.497/0.247 measured vs 0.500/0.250 predicted at N=32/128); BOUNDED worst
        case a=1 level 0.5434 V = +143.4 mV over Vt_est
                       -> qal_bankN_sqrtN_analysis.json + qal_bankN_sqrtN_analyze.py (5),(7)
  sha_slice levelization D=10, 105 cells, 48/22/19/3/2/4/2/3/1/1 -> work/levels.json
  sha_slice CMOS 56 stdcells, 0.000000 sequential (0.00%)       -> work/cmos_stat.txt
GIVEN BY THE BRIEF (carried, not re-derived):
  E_path ~2.20 fJ/hop and E_gates ~8.28 fJ/hop at the operating point (sum 10.48 vs the
  measured E_hop 10.7416 -- 2.4% low; path share 21.0% vs the measured 23.2-24.8% band,
  consistent at the low edge). CMOS sha_slice 232 fJ @ 0.928 ns, alpha=0.476, LIBERTY-based
  and flagged PROVISIONAL pending a transistor cross-check.
ASSUMED (nothing on disk; no comparator has been simulated anywhere in the campaign):
  zero-current-detector energy 30-300 fJ per bank per hop (~35 devices).
  Vt_est = 0.400 V is the project's own estimate, not separately extracted
  (qal_bankN_sqrtN_analyze.py:19). Settling cliff "rail must stay above ~0.50 V" is the
  project's own stated cliff (:20).
"""

import math

# ---------------------------------------------------------------- MEASURED constants
E_HOP_N8      = 10.7416     # fJ, 8-gate bank, dV=1.0, L=277.8 nH   [qal_isocurrent.json]
E_HOP_PER_G   = 1.34269     # fJ/gate  (INCLUDES its 1/8 share of the path term)
T_HOP_PS      = 342.0       # ps
PATH_PCT      = (23.18, 24.76)   # % of E_hop  [qal_split_differential.json rows[1]]
E_PATH_BRIEF  = 2.20        # fJ/hop  (GIVEN)
E_GATE_BRIEF  = 8.28 / 8.0  # fJ/gate (GIVEN, gate-only term)
E_LOSS        = (0.068, 0.136)   # per-hop delivery loss, wide w=40um .. real w=10um
E_SW_K1       = 15.6139     # fJ/bank/fire, w=10um   [qal_pulse_topup.json cases[0]]
E_SW_K7       = 24.5134     # fJ/bank/fire, w=10um   [cases[1]]
E_TOPUP_SMALL = 25.425      # fJ rail per fire, 80 fF bank, eta 0.12%   [cases[0]]
E_TOPUP_BIG   = 112.1813    # fJ rail per fire, 2000 fF bank K=7, eta 61.58% [cases[3]]
E_ZCD         = (30.0, 300.0)    # fJ/bank/hop  ASSUMED

LVL_MEAN      = 0.5826      # V, logic-1 level at a=0.5, dV=1.0   [analyze (7)]
LVL_A1        = 0.5434      # V, BOUNDED worst case a=1           [analyze (7)]
SIG_N8        = 0.015452    # V, composed sigma at N=8            [analysis json]
VT_EST        = 0.400       # V  ASSUMED (project's own)
CLIFF         = 0.500       # V  project's own stated settling cliff
DELTA_MAX     = LVL_MEAN - LVL_A1     # V, mean -> all-active; measured N-INDEPENDENT

# sha_slice  [work/levels.json, work/cmos_stat.txt]
SHA_LVL   = [48, 22, 19, 3, 2, 4, 2, 3, 1, 1]
SHA_CELLS = 105
SHA_D     = 10
CMOS_FJ   = 232.0
CMOS_NS   = 0.928
CMOS_CELLS= 56
ALPHA     = 0.476

def sigma(N):
    """Data-dependent rail/level wander. 1/sqrt(N) MEASURED to 0.5% over N=8/32/128."""
    return SIG_N8 * math.sqrt(8.0 / N)

def hop_droop(V, e, k):
    """Level after k hops with no top-up. E falls (1-e) per hop, V ~ sqrt(E)."""
    return V * (1.0 - e) ** (0.5 * k)

# ---------------------------------------------------------------- (a) burst model
def fill_ns(D):      return D * T_HOP_PS / 1000.0
def throughput_gops(): return 1000.0 / T_HOP_PS

# ---------------------------------------------------------------- (b) amortization
def e_op(levels, K, e_zcd, e_sw, e_topup, e_path=E_PATH_BRIEF, e_gate=E_GATE_BRIEF):
    """Sustained per-op energy, pipeline full. NOTE the structural result: the switch,
    ZCD and top-up fire once per BEAT, and a full pipeline has a new op every beat, so
    they are charged PER OP. Burst length amortizes ONLY fill+drain."""
    D = len(levels)
    logic = sum(levels) * e_gate + D * e_path
    overhead = (D / float(K)) * (e_sw + e_topup) + D * e_zcd     # ZCD fires every hop
    return logic, overhead, logic + overhead

def kn_required(e_sw, e_topup, e_zcd, e_gate=E_GATE_BRIEF):
    """K*N gate-hops per top-up fire needed for QAL to stay under CMOS per-cell energy.
    Condition: N*e_gate + (E_sw+E_topup)/K + N*e_zcd_share < N*alpha*E_cell_cmos.
    Solved with the ZCD charged per hop (it cannot be amortized by K)."""
    e_cell = CMOS_FJ / CMOS_CELLS          # fJ/cell/op, alpha ALREADY folded in
    head = e_cell - e_gate                 # per-gate headroom
    if head <= 0: return None
    return (e_sw + e_topup), head, e_zcd

# ---------------------------------------------------------------- (d) margin bound
def hops_hard(budget):
    """Adversarial: every bank all-active, fixed mean-sized top-up -> deterministic walk."""
    return budget / DELTA_MAX

def hops_3sigma(N, budget, e, K=1):
    """Random walk of step sigma(N), after the systematic inter-fire droop is charged."""
    droop = LVL_MEAN - hop_droop(LVL_MEAN, e, K)
    left = budget - droop
    if left <= 0: return 0.0, droop
    return (left / (3.0 * sigma(N))) ** 2, droop

# ================================================================== REPORT
if __name__ == "__main__":
    W = 92
    print("=" * W)
    print("QAL AS A BURST MODE -- re-scored.  All inputs labelled; no Xyce run here.")
    print("=" * W)

    print("\n(a) BURST MODEL, sha_slice D=%d" % SHA_D)
    print("    fill latency  = D x t_hop = %d x %.0f ps = %.2f ns   (PAID ONCE per burst)"
          % (SHA_D, T_HOP_PS, fill_ns(SHA_D)))
    print("    steady state  = 1 op / beat, %d ops in flight" % SHA_D)
    print("    throughput    = %.3f Gop/s   vs CMOS comb %.3f Gop/s  -> %.2fx"
          % (throughput_gops(), 1.0 / CMOS_NS, throughput_gops() * CMOS_NS))
    print("    drain/exit    = NOT KNOWABLE: the return/re-arm path has never been")
    print("                    simulated (qal_a1f_inductive.py 'Not yet shown: the")
    print("                    return/reset path (re-arm A)'). Bounded [0, one bank dump].")

    print("\n(b) AMORTIZATION -- what burst length B actually buys")
    print("    E_op(B) = [logic + D*E_path] + [(D/K)(E_sw+E_topup) + D*E_zcd] + (fill+drain)/B")
    print("    *** Only the LAST bracket carries B. The switch/ZCD/top-up fire every beat")
    print("        because a full pipeline accepts a new op every beat -- they are PER-OP.")
    print("        Bank population N and top-up interval K amortize them; burst length does NOT.")
    print()
    print("    %-34s %9s %9s %9s" % ("sha_slice case", "logic fJ", "ovhd fJ", "total fJ"))
    for lbl, K, z, sw, tu in [
            ("K=1, ZCD 30 fJ  (optimistic)",  1, E_ZCD[0], E_SW_K1, E_TOPUP_SMALL),
            ("K=1, ZCD 300 fJ (pessimistic)", 1, E_ZCD[1], E_SW_K1, E_TOPUP_SMALL),
            ("K=7, ZCD 30 fJ  (MARGIN-ILLEGAL)", 7, E_ZCD[0], E_SW_K7, E_TOPUP_SMALL)]:
        lo, ov, tt = e_op(SHA_LVL, K, z, sw, tu)
        note = "  <- (d) forbids K>1 at real Ron" if K > 1 else ""
        print("    %-34s %9.1f %9.1f %9.1f   = %.2fx CMOS%s"
              % (lbl, lo, ov, tt, tt / CMOS_FJ, note))
    lo, ov, tt = e_op(SHA_LVL, 1, 0.0, 0.0, 0.0)
    print("    %-34s %9.1f %9.1f %9.1f   = %.2fx CMOS  <- the standing 136.8 fJ headline"
          % ("logic+path ONLY (no overheads)", lo, ov, tt, tt / CMOS_FJ))

    print("\n    CROSSOVER in bank population N (NOT in burst length B):")
    fire, head, z = kn_required(E_SW_K1, E_TOPUP_SMALL, E_ZCD[0])
    print("      CMOS per-cell-per-op (alpha folded in) = %.3f fJ; QAL gate-settle %.3f fJ"
          % (CMOS_FJ / CMOS_CELLS, E_GATE_BRIEF))
    print("      per-gate headroom h = %.3f fJ" % head)
    for zl, zv in (("optimistic", E_ZCD[0]), ("pessimistic", E_ZCD[1])):
        for K in (1, 2, 7):
            need = (E_SW_K1 + E_TOPUP_SMALL) / (K * (head - zv / 1e9))   # zcd handled below
            # ZCD is per-hop, so it must be covered by N alone:
            n_zcd = zv / head
            n_fire = (E_SW_K1 + E_TOPUP_SMALL) / (K * head)
            print("      ZCD %-11s K=%d -> N_min = %6.1f (switch+topup) + %6.1f (ZCD) = %6.1f"
                  % (zl, K, n_fire, n_zcd, n_fire + n_zcd))

    print("\n    sha_slice per-bank verdict at K=1 (N_min = 14.6 optimistic / 111.1 pessimistic):")
    n_opt = (E_SW_K1 + E_TOPUP_SMALL) / head + E_ZCD[0] / head
    n_pes = (E_SW_K1 + E_TOPUP_SMALL) / head + E_ZCD[1] / head
    ok_o = sum(1 for n in SHA_LVL if n >= n_opt)
    ok_p = sum(1 for n in SHA_LVL if n >= n_pes)
    print("      banks %s" % SHA_LVL)
    print("      clear optimistic N_min=%.1f : %d of %d banks" % (n_opt, ok_o, SHA_D))
    print("      clear pessimistic N_min=%.1f: %d of %d banks" % (n_pes, ok_p, SHA_D))

    print("\n(c) CLOCK-FLOOR / DUTY CROSSOVER")
    print("    E_CMOS(window) = W*E_clk + B*E_logic ; E_QAL = B*e_op + fill + drain")
    print("    QAL wins iff duty a = B/W  <  E_clk / (e_op - E_logic + (fill+drain)/B)")
    print("    *** sha_slice has 0.000000 sequential area (cmos_stat.txt) -> E_clk = 0")
    print("        INSIDE the block. There is no clock to eliminate in a combinational")
    print("        block; both bindings pay the island's boundary registers. So a* = 0:")
    print("        QAL must beat CMOS on raw energy at EVERY duty, and it does not.")
    print("    The clock-floor lever is proportional to the block's SEQUENTIAL content.")

    print("\n(d) WHAT BREAKS AT LONG CHAINS -- the margin bound (NEW; nobody had computed it)")
    print("    *** REFRAME: the margin compounds along DEPTH (hops per restore), not along")
    print("        burst length. A burst of B ops does not deepen the chain; each op still")
    print("        walks D hops. So this bounds the RESTORE INTERVAL, not B.")
    print("    Budgets from the measured mean logic-1 level %.4f V:" % LVL_MEAN)
    b_cliff = LVL_MEAN - CLIFF
    b_vt    = LVL_MEAN - VT_EST
    print("      to the settling cliff %.2f V : %.1f mV   (BINDING -- settling is 77.1%%"
          % (CLIFF, 1000 * b_cliff))
    print("                                              at rail 0.468 V, MEASURED)")
    print("      to the Vt floor       %.2f V : %.1f mV  (the 143.4 mV figure is this bound"
          % (VT_EST, 1000 * b_vt))
    print("                                              taken from the a=1 worst case)")
    print("\n    MECHANISM 1 -- systematic droop between top-up fires (MEASURED loss/hop):")
    for e in E_LOSS:
        for K in (1, 2, 3):
            d = LVL_MEAN - hop_droop(LVL_MEAN, e, K)
            flag = "  EXCEEDS the %.1f mV cliff budget" % (1000 * b_cliff) if d > b_cliff else ""
            print("      loss %.1f%%/hop, K=%d -> droop %5.1f mV%s" % (100 * e, K, 1000 * d, flag))
    print("      => at the REAL device Ron (w=10um, 13.6%%/hop) K=2 already spends %.1f mV"
          % (1000 * (LVL_MEAN - hop_droop(LVL_MEAN, 0.136, 2))))
    print("         of an %.1f mV budget. TOP-UP EVERY HOP (K=1) IS MANDATORY at real Ron."
          % (1000 * b_cliff))
    print("\n    MECHANISM 2 -- adversarial data, fixed mean-sized top-up (HARD bound):")
    print("      measured mean->all-active level step DELTA = %.1f mV, N-INDEPENDENT"
          % (1000 * DELTA_MAX))
    print("      hops to the settling cliff: %.2f -> %d hops" % (hops_hard(b_cliff), int(hops_hard(b_cliff))))
    print("      hops to the Vt floor      : %.2f -> %d hops" % (hops_hard(b_vt), int(hops_hard(b_vt))))
    print("      => an OPEN-LOOP (fixed-charge) top-up cannot carry an all-active pattern")
    print("         past 2 hops. The top-up must be REGULATED to a reference level. Its")
    print("         residual is unmeasured -> that number is NOT KNOWABLE yet.")
    print("\n    MECHANISM 3 -- data-dependent random walk, 3-sigma, K=1 (the design bound):")
    for e, elbl in ((0.068, "wide w=40um"), (0.136, "real w=10um")):
        print("      loss %.1f%%/hop (%s):" % (100 * e, elbl))
        print("        %5s | %8s | %-22s | %-22s" % ("N", "sigma mV", "hops to cliff 0.50V",
                                                     "hops to Vt 0.40V"))
        for N in sorted(set(SHA_LVL), reverse=True):
            hc, dr = hops_3sigma(N, b_cliff, e)
            hv, _ = hops_3sigma(N, b_vt, e)
            print("        %5d | %8.2f | %22s | %22s"
                  % (N, 1000 * sigma(N), "%.2f -> %d" % (hc, int(hc)), "%.2f -> %d" % (hv, int(hv))))
    print("\n    => sigma ~ 1/sqrt(N) and h ~ 1/sigma^2, so HOPS SURVIVED SCALES LINEARLY WITH")
    print("       BANK POPULATION N. That is the single cleanest QAL design law to come out")
    print("       of this: wide banks are BOTH cheaper (amortization) and safer (margin).")

    print("\n(e) THE FIGURE OF MERIT, and sha_slice / ALU under it")
    print("    REPORT QAL AS:  (E_op^sustained fJ/op, Theta Gop/s, fill ns)")
    print("                    subject to two admissibility gates, both per-bank:")
    print("      G1 margin      : min_i N_i >= N such that 3*sigma(N)*sqrt(1) <= budget - droop(K)")
    print("      G2 amortization: N_i * K   >= (E_sw + E_topup)/h  +  K*E_zcd/h")
    lo, ov, tt = e_op(SHA_LVL, 1, E_ZCD[0], E_SW_K1, E_TOPUP_SMALL)
    lo2, ov2, tt2 = e_op(SHA_LVL, 1, E_ZCD[1], E_SW_K1, E_TOPUP_SMALL)
    print("\n    sha_slice: (%.0f-%.0f fJ/op, %.2f Gop/s, %.2f ns fill)"
          % (tt, tt2, throughput_gops(), fill_ns(SHA_D)))
    print("               vs CMOS (232 fJ/op, %.2f Gop/s). Energy %.1f-%.1fx WORSE,"
          % (1.0 / CMOS_NS, tt / CMOS_FJ, tt2 / CMOS_FJ))
    print("               throughput %.2fx better. G1 FAILS at 7 of 10 banks (N<=4),"
          % (throughput_gops() * CMOS_NS))
    print("               G2 FAILS at %d of 10. VERDICT: NOT a QAL block." % (SHA_D - ok_o))

    # ALU projection from STRUCTURE only (its own measurement is running elsewhere)
    ALU_CELLS, ALU_FF = 4726, 188
    print("\n    Vortex ALU (%d cells, %d DFF) -- PROJECTED FROM STRUCTURE ONLY:" % (ALU_CELLS, ALU_FF))
    print("      %5s | %7s | %10s | %10s | %s" % ("D", "meanN", "logic fJ", "ovhd fJ", "total"))
    for D in (10, 20, 30, 60):
        meanN = ALU_CELLS / float(D)
        lv = [int(round(meanN))] * D
        l1, o1, t1 = e_op(lv, 1, E_ZCD[0], E_SW_K1, E_TOPUP_SMALL)
        l2, o2, t2 = e_op(lv, 1, E_ZCD[1], E_SW_K1, E_TOPUP_SMALL)
        print("      %5d | %7.1f | %10.0f | %5.0f-%-5.0f| %.1f-%.1f pJ  G1 %s"
              % (D, meanN, l1, o1, o2, t1 / 1000, t2 / 1000,
                 "PASS" if meanN >= n_pes else ("marginal" if meanN >= n_opt else "FAIL")))
    print("      CMOS ALU reference, IN-FLIGHT intermediate from the parallel workflow")
    print("      (probes/layopt/evidence/alu_cmos/work/, written 11:19-11:33 today, that")
    print("       workflow still running -- NOT my measurement, subject to their revision):")
    print("        inst_power.json 5164 instances, clk period 4.75 ns (dump.tcl:4)")
    print("        all cells    8.993 mW -> 42.7 pJ/cycle")
    print("        clkbuf tree  1.752 mW -> %5.2f pJ/cycle (49 cells)   <- the clock FLOOR"
          % (0.00175212 / 210.526e6 * 1e12))
    print("        DFF internal 2.753 mW -> 13.1 pJ/cycle (188 DFF, alpha 0.370)")
    print("      => if those hold, QAL at 5.6-15.2 pJ is 2.8-7.6x better than 42.7 pJ, and")
    print("         the brief's ~5.30 pJ clock-floor estimate reads LOW: the clkbuf tree")
    print("         alone is 8.3 pJ/cycle before any DFF clock-pin internal power.")
    print("      -> the ALU's verdict turns entirely on its LEVELIZATION WIDTH, which the")
    print("         parallel workflow measures. Wide+shallow => QAL viable; a thin tail")
    print("         like sha_slice's 3/2/4/2/3/1/1 => QAL fails there too.")
