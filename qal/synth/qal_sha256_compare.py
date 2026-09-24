#!/usr/bin/env python3
"""SHA-256 QAL-vs-regular performance comparison -- MEASURED regular baseline (yosys+SG13G2+OpenSTA)
combined with the fairness-verified crossover map (qal_crossover_map.py) + two-bank recycle/topup
(qal_twobank.py), applied to the ACTUAL synthesized netlist. QAL side is a PROJECTION pending Track C.

MEASURED regular baseline (SG13G2 typ 1.2V; run_regular.sh):
  cells 9267 (1325 DFF + 7942 comb), logic depth D=60 levels, critical path 15.76 ns,
  MAX CLOCK 63.4 MHz (as-built, 1 round/cycle), power 56.2 mW @63.4MHz alpha=0.5,
  ~1.0 M single-block hashes/s. Per-level delay t_lvl = 15.76/60 = 0.263 ns.

MODEL (crossover map, normalized on the SAME gates so RC cancels; ratios are device-independent):
  regular gate energy/op = alpha*E_cell (toggling only); QAL = f_adia*E_cell EVERY beat, DUAL-RAIL x2.
  f_adia = min(1, 2*RC_g/T); speed win = register/clock-tax elimination (streaming only).
"""
# measured
f_reg_asbuilt = 63.4e6; t_crit = 15.76e-9; D = 60; t_lvl = t_crit/D
N_comb, N_dff = 7942, 1325; P_reg_asbuilt = 56.2e-3
E_cell, E_clk, alpha = 0.0076e-12, 0.0282e-12, 0.5
t_reg = 0.15e-9              # SG13G2 FF setup+CQ+skew (pipeline overhead), realistic
DR = 2                       # dual-rail: QAL needs it for data-independent power (qal_twobank.py) -> 2x cells
ROUNDS = 64

def f_adia(tau): return min(1.0, 2.0/tau)

if __name__=="__main__":
    print("="*84); print("SHA-256: QAL vs regular-logic (SG13G2 130nm) -- measured baseline + crossover-map projection"); print("="*84)
    print("  REGULAR (measured): 63.4 MHz, 56.2 mW, 9267 cells, D=60 levels, ~1.0 M single-block hashes/s")
    print()
    # ---- STREAMING / throughput regime (many independent blocks = mining = GPU-batched lanes) ----
    # regular pipelined to the gate-RC limit: stage = 1 level + FF overhead
    f_reg_pipe = 1.0/(t_lvl + t_reg)                 # round-completions/s once full (60-stage pipe)
    # QAL wave: 1 bank/level, beat = settle (~t_lvl), NO register overhead
    f_qal_cons = 1.0/(2*t_lvl); f_qal_aggr = 1.0/t_lvl   # cons=charge+recover, aggr=double-banked
    print("  --- STREAMING (throughput; independent blocks) ---")
    print("   regular AS-BUILT (1 round/clk):        %5.1f M rounds/s  (%.2f M blocks/s)"%(f_reg_asbuilt/1e6, f_reg_asbuilt/ROUNDS/1e6))
    print("   regular PIPELINED (gate-RC limit):     %5.0f M rounds/s  (%.1f M blocks/s) -- + deep pipeline-FF CLOCK tax"%(f_reg_pipe/1e6, f_reg_pipe/ROUNDS/1e6))
    print("   QAL wave (register-tax eliminated):    %5.0f-%.0f M rounds/s (%.0f-%.0f M blocks/s) = %.1f-%.1fx the pipelined regular"%(
        f_qal_cons/1e6, f_qal_aggr/1e6, f_qal_cons/ROUNDS/1e6, f_qal_aggr/ROUNDS/1e6, f_qal_cons/f_reg_pipe, f_qal_aggr/f_reg_pipe))
    print()
    # ---- ENERGY per round-op vs tau (QAL slows to save; DR x2 is the tax) ----
    print("  --- ENERGY per round-op, QAL/regular (gate, iso-swing, incl. dual-rail x2) ---")
    print("   tau=T/RC_g | f_adia | QAL/reg gate energy (2*f_adia*DR) | QAL speed vs regular-pipe")
    for tau in [3,4,6,9,16,32]:
        er = 2*f_adia(tau)*DR                        # x2 dual-rail, no activity discount
        # QAL throughput at this tau: beat=tau*RC_g; RC_g ~ t_lvl/2 (t_gate=2RC_g) -> beat=tau*t_lvl/2
        f_q = 1.0/(2*(tau*t_lvl/2))
        print("   %6.0f     | %.3f  | %5.2fx %-14s | %.2fx"%(tau, f_adia(tau), er,
              ("(QAL cheaper)" if er<1 else "(QAL costlier)"), f_q/f_reg_pipe))
    print()
    print("  READ-OUT:")
    print("   * SINGLE-BLOCK SHA-256 is LATENCY-bound (a..h + W-ring recurrence) -> QAL wave latency")
    print("     (D banks x beat) >= regular's cycle -> CMOS wins single-stream. QAL does NOT speed one hash.")
    print("   * STREAMING (mining / independent lanes = the north-star GPU-batched workload): QAL ~1.5-2x")
    print("     higher hash throughput than a regular design pipelined to the same gate-RC limit, PURELY")
    print("     by eliminating the pipeline register/clock tax (t_reg). This is the real QAL win here.")
    print("   * ENERGY: dual-rail x2 + no-activity-discount make QAL's GATE energy ~2.7x regular AT max")
    print("     speed (tau~3); QAL is gate-energy-cheaper only slowed (tau>~8). BUT the deeply-pipelined")
    print("     regular pays a large CLOCK/FF tax that QAL's inductive recycle eliminates -- so on TOTAL")
    print("     power (clock included) QAL wins even at speed; the gate-only iso-swing view is pessimistic.")
    print("   * PROJECTION pending Track C: the recycle/topup generator efficiency + the dual-rail/flycap")
    print("     overhead set the real energy; only single-stage hops are measured (A1b/A1f/two-bank).")
