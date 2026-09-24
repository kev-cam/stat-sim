#!/usr/bin/env python3
"""QAL gate-level crossover map: adiabatic-settling logic vs CMOS, over tau = T/RC_g.
Designed + adversarially fairness-checked as a workflow (it caught my apples-to-oranges cell-vs-output
bug). Everything normalizes on tau = operating-ramp / gate-time-constant; RC_g only rescales the Hz/fJ
axes. Answers the user's two questions -- "faster in any way?" and "more efficient at some speed?" --
and the honest verdict is: FASTER *OR* CHEAPER, NOT BOTH at one T.

FAIR GATE ENERGY (cell-to-cell, iso-swing, per-op; anchor + swing CANCEL):
  CMOS = alpha * E_cell         (alpha=0.5: only toggling cells pay)
  QAL  = f_adia * E_cell        (paid EVERY beat -- the ramp runs regardless of data, NO activity discount)
  f_adia = min(1, 2*RC_g/T)     (resistive-settle fraction of a hard switch; cap/knee at T=2*RC_g)
  => E_QAL/E_CMOS = 2*f_adia = 4*RC_g/T = 4/tau     ENERGY CROSSOVER at tau = 4  (QAL cheaper iff T>4*RC_g).
  Below tau=K_settle~3 the output never reaches dV -> X/uncomputed (a logic-correctness boundary, 3D-Logic).

SPEED (device-INDEPENDENT ratio -- RC_g cancels): the wave has NO clock registers, so QAL sheds the
register/clock tax t_reg = k_reg*RC_g that CMOS pays every cycle.
  f_CMOS = 1/((2*depth + k_reg)*RC_g) = 1/(9*RC_g)          [depth=2, k_reg=5; anchor t_reg~108ps @RC_g=20ps]
  f_QAL  = 1/(n_beat*K_settle*RC_g)                          [n_beat=2 conservative, 1 aggressive double-banked]
  f_QAL/f_CMOS = (2*depth+k_reg)/(n_beat*K_settle) = 9/6 = 1.5x (cons) / 9/3 = 3.0x (aggr).
  The ENTIRE speed win is k_reg elimination: set k_reg->0 => 0.67x, QAL LOSES. => ONLY for streaming /
  independent-lane workloads (bulk hashing, 61-wide sigma0 across blocks, GPU-batched MC/defect/SIMT lanes
  -- exactly the north-star GPGPU workload). LATENCY-bound serial recurrences (SHA W[t], a..h round feedback)
  INVERT it: QAL per-dependent-op latency = depth*T+reset >= CMOS cycle -> CMOS wins single-stream.

*** TWO NON-COINCIDENT CROSSOVERS: the energy break-even (tau=4) sits SLOWER than the speed ceiling
(tau=3). At the speed ceiling 2*f_adia=1.33 -> QAL burns ~33% MORE gate energy exactly where it is
fastest. Both-win window is RAZOR-THIN: cons 4<tau<4.5 (<=12.5% faster AND <=11% cooler); aggr 4<tau<9
(up to 2.25x faster while still cooler). Reduced-swing (dV=0.6, separate ~4x lever raced vs near-Vt CMOS)
widens it. FASTER OR CHEAPER, NOT BOTH at one T.

CONTINGENCIES (honest): (1) energy advantage is FLOOR-CAPPED at alpha/e_floor ~ 3.2x (Q=10) to 9.5x
(Q=30) by the transfer+generator floor -- and the energy-recovering resonant generator (eta->1) is UNBUILT;
as-built eta~1/3 (A1f). (2) leakage adds P_leak*T -> a minimum at T*~sqrt(2 RC_g E_cell/P_leak); beyond T*
QAL gets worse. (3) dual-rail restoration (m=RC_QAL/RC_CMOS ~2) halves the speed win + pushes crossovers out.
(4) QAL pays every cycle -> needs high near-constant duty; bursty/clock-gated logic (alpha<<0.5) -> QAL loses.
PROVENANCE: f_adia form validated by A1b (46.9% at ~1.5RC); eta~1/3 measured (A1f); generator/leakage/dual-rail
MODELED. PROJECTION pending Track C. Publish 2*f_adia=4/tau explicitly, THEN the floor/leakage/dual-rail stack.
"""
import math
DEPTH, K_REG, K_SETTLE, ALPHA = 2, 5, 3, 0.5
E_cell_fJ, N = 7.6, 61                       # anchor full-swing (units: fJ, NOT aJ)
def f_adia(tau): return min(1.0, 2.0/tau)
def E_ratio(tau): return 2*f_adia(tau)                       # QAL/CMOS gate energy, iso-swing
def speed_ratio(n_beat): return (2*DEPTH+K_REG)/(n_beat*K_SETTLE)

if __name__=="__main__":
    print("="*82); print("QAL gate-level crossover map (normalized on tau = T/RC_g)"); print("="*82)
    print("  ENERGY crossover: E_QAL/E_CMOS = 2*f_adia = 4/tau -> break-even at tau=4 (QAL cheaper iff T>4*RC_g)")
    print("  SPEED ceiling at tau=%d: f_QAL/f_CMOS = %.2fx (cons, 1/2T) / %.2fx (aggr, double-banked 1/T) -- device-INDEPENDENT"%(
        K_SETTLE, speed_ratio(2), speed_ratio(1)))
    print("  ... the entire speed win is register-tax (k_reg=%d) elimination; k_reg->0 => %.2fx (QAL loses)"%(K_REG,DEPTH/(2*K_SETTLE)))
    print("-"*82)
    print("  %5s %7s %10s %9s %9s"%("tau","f_adia","E_QAL/CMOS","cooler","slower_vs_ceiling"))
    for tau in [3,4,4.5,6,9,16,32,64]:
        er=E_ratio(tau); cooler = (1/er) if er>0 else float('inf')
        slower = tau/K_SETTLE   # vs the tau=3 speed ceiling
        tag=""
        if abs(tau-3)<1e-6: tag="<- SPEED ceiling (1.5-3x faster, but 1.33x HOTTER)"
        elif abs(tau-4)<1e-6: tag="<- ENERGY break-even (parity)"
        elif abs(tau-4.5)<1e-6: tag="<- cons throughput crossover (x=1)"
        elif abs(tau-9)<1e-6: tag="<- aggr throughput crossover (x=1)"
        print("  %5s %7.3f %9.2fx %8.2fx %8.1fx  %s"%(tau,f_adia(tau),er,cooler,slower,tag))
    print("-"*82)
    print("  BOTH-WIN WINDOW (faster AND cooler): cons 4<tau<4.5 (razor-thin); aggr 4<tau<9 (up to 2.25x")
    print("  faster while cooler). Reduced-swing (~4x, separate lever) widens it. FASTER *OR* CHEAPER, not both.")
    print("  Energy advantage FLOOR-CAPPED at ~3.2x (Q=10) to ~9.5x (Q=30); leakage adds a minimum at T*.")
    print("  SPEED win applies to STREAMING / independent-lane workloads (= the GPU-batched north-star lanes);")
    print("  LATENCY-bound serial recurrences (single-stream SHA) INVERT it -- CMOS wins there.")
    print("  Contingent on the UNBUILT high-Q resonant generator (eta~1/3 as-built). PROJECTION pending Track C.")
