#!/usr/bin/env python3
"""Compose energy-per-useful-op vs duty, QAL vs clock-gated CMOS, from the
measured decks in this directory + committed coefficients (provenance named)."""
import json, os, math

os.chdir(os.path.dirname(os.path.abspath(__file__)))

W_OPS = 160.0                     # 20 beats x 8 gates, both sides
T_BURST_QAL = 5.459e-9            # s, topup schedule burst window (burst_end-T0)
T_BURST_CMOS = 5 * 486e-12        # s, DERIVED: 4x42.67 ps/level + 315.4 ps t_reg

# ---- MEASURED HERE -----------------------------------------------------------
P_IDLE_QAL = 0.900e-9             # W: 871 pW tank drain (4 x 240 pA @0.9075 V)
                                  #  + ~25 pW park/VHI rails (park24 + prn currents)
QAL_RECHARGE_TAX = 1.157          # DERIVED: parked drain re-supplied at wake
                                  # through the committed 86.4% recharge switch
E_CMOS_COMB_WAVE = 233.01e-15     # J/wave, measured cmos_burst (32 evals, alpha=1)
P_CMOS_CG_COMB = 427.4e-12        # W, measured 32-cell powered-idle leak
P_CMOS_PG = 18.85e-12             # W, measured 30um-header power-gated residual
# ---- MEASURED COMMITTED (cited) ---------------------------------------------
E_FF_FLOOR = 32.45e-15            # J/flop/cyc: E0_FF 59.10 liberty x C_FLOOR 0.549
E_FF_TREE = 38.34e-15             # J/flop/cyc: E_TREE 27.7 x C_TREE 1.384
E_FF_DATA = 63.70e-15             # J/flop at alpha_ff=1: S_FF 38.51 x C_DATA 1.654
E_FF_LO = 73.2e-15                # J/flop/cyc add8 anchor total (28.2 clk + 45 tog)
P_DFF_LEAK = 526.5e-12            # W/flop committed (junctions present)
P_SRAM_BIT = 12.09e-12            # W/bit committed
E_WAKE = 1.5e-12                  # J, committed SAR calibrate-on-wake [0.7,4.0]
E_WAKE_BAND = (0.7e-12, 4.0e-12)
E_TIMER_HOP = 328.4e-15           # J/bank-hop DERIVED: 302.8 taps + (97+5.4)/4
N_FF = 8
N_HOPS = 20

# ---- QAL burst energy from the topup cycle decks ----------------------------
cy = json.load(open("CYCLES_cytu.json"))
r = cy["cytu_tpre2000"]
sb = r["segments"]["burst"]
sp = r["segments"]["park_post"]
# positive draws only (IS3 rule: never net an ideal-source export)
def pos(x):
    return max(x, 0.0)
E_BURST_QAL_LB = (pos(sb.get("ETU", 0.0)) + pos(sb["EGT"]) + pos(sb["EHI"])
                  + pos(sb["EI1"]) + pos(sb["tank_dE_total_fJ"])
                  + pos(sp["tank_dE_total_fJ"])) * 1e-15   # settle tail booked to burst
EXPORTS = dict(EHI_fJ=min(sb["EHI"], 0.0), EGT_fJ=min(sb["EGT"], 0.0))
E_BURST_QAL_FULL = E_BURST_QAL_LB + N_HOPS * E_TIMER_HOP

# ---- CMOS burst variants ----------------------------------------------------
E_CMOS_CYCLE_CENTRAL = E_CMOS_COMB_WAVE + N_FF * (E_FF_FLOOR + E_FF_TREE + E_FF_DATA)
E_CMOS_CYCLE_LO = E_CMOS_COMB_WAVE + N_FF * E_FF_LO
E_BURST_CMOS = dict(central=5 * E_CMOS_CYCLE_CENTRAL, lo=5 * E_CMOS_CYCLE_LO)

# ---- CMOS idle variants -----------------------------------------------------
P_IDLE_CMOS = dict(
    pg=P_CMOS_PG,                                      # power-gated, state cancels
    pg_sram64=P_CMOS_PG + 64 * P_SRAM_BIT,             # + 64 retained bits
    cg_sameshim=P_CMOS_CG_COMB + N_FF * 170e-12,       # DERIVED: DFF ~12x measured
                                                       # inverter leak (width scale)
    cg_committed=32 * 124.25e-12 + N_FF * P_DFF_LEAK)  # committed mixed-logic band

# half-effective clock gating (sensitivity, defined in PRE_REGISTERED A6):
P_CG_HALF = 0.5 * N_FF * (E_FF_FLOOR + E_FF_TREE) / 486e-12

def e_op_qal(t_idle, e_burst, p_idle, e_wake=E_WAKE):
    return (e_burst + e_wake + p_idle * t_idle) / W_OPS

def e_op_cmos(t_idle, e_burst, p_idle):
    return (e_burst + p_idle * t_idle) / W_OPS

def crossover(e_bq, e_bc, p_q, p_c):
    """T_idle where curves meet; returns (T*, who_wins_low_duty)."""
    num = e_bq + E_WAKE - e_bc
    den = p_c - p_q
    if den == 0:
        return None, ("CMOS" if num > 0 else "QAL")
    t = num / den
    if t <= 0:
        return None, ("QAL at every duty" if num < 0 and den < 0 else
                      "CMOS at every duty" if num > 0 and den > 0 else
                      "QAL at every duty" if num < 0 else "CMOS at every duty")
    winner_low = "QAL" if den > 0 else "CMOS"
    return t, winner_low

def duty(t_idle):
    return T_BURST_QAL / (T_BURST_QAL + t_idle)

OUT = dict(
    useful_ops=W_OPS, t_burst_qal_s=T_BURST_QAL, t_burst_cmos_s=T_BURST_CMOS,
    E_burst_QAL_metered_pJ=E_BURST_QAL_LB * 1e12,
    E_burst_QAL_complete_pJ=E_BURST_QAL_FULL * 1e12,
    unbanked_exports_fJ=EXPORTS,
    E_burst_CMOS_pJ={k: v * 1e12 for k, v in E_BURST_CMOS.items()},
    P_idle_QAL_nW=P_IDLE_QAL * 1e9,
    P_idle_QAL_x10_nW=P_IDLE_QAL * 10e9,
    P_idle_CMOS_nW={k: v * 1e9 for k, v in P_IDLE_CMOS.items()},
    P_cg_half_effective_W=P_CG_HALF,
    crossovers={}, curves={})

scen = []
for qname, e_bq in (("metered", E_BURST_QAL_LB), ("complete", E_BURST_QAL_FULL)):
    for pq_name, pq in (("meas", P_IDLE_QAL), ("x10", 10 * P_IDLE_QAL)):
        for cname, e_bc in E_BURST_CMOS.items():
            for iname, pc in list(P_IDLE_CMOS.items()) + [("cg_half", P_CG_HALF)]:
                t, wl = crossover(e_bq, e_bc, pq, pc)
                key = "QAL_%s_idle%s__vs__CMOS_%s_%s" % (qname, pq_name, cname, iname)
                OUT["crossovers"][key] = dict(
                    T_idle_star_s=t, duty_star=(duty(t) if t else None),
                    low_duty_winner=wl,
                    dE_burst_pJ=(e_bq + E_WAKE - e_bc) * 1e12,
                    dP_idle_nW=(pc - pq) * 1e9)

# curves over duty 1 -> 1e-7 (both sensitivity cases included)
import numpy as np
duties = [1.0] + [10 ** (-x / 2.0) for x in range(1, 15)]
for nm, e_bq, pq in (("QAL_metered", E_BURST_QAL_LB, P_IDLE_QAL),
                     ("QAL_complete", E_BURST_QAL_FULL, P_IDLE_QAL),
                     ("QAL_complete_idle_x10", E_BURST_QAL_FULL, 10 * P_IDLE_QAL)):
    OUT["curves"][nm] = [
        dict(duty=d, t_idle_s=T_BURST_QAL * (1 - d) / d,
             fJ_per_op=e_op_qal(T_BURST_QAL * (1 - d) / d, e_bq, pq) * 1e15)
        for d in duties]
for nm, e_bc, pc in (("CMOS_central_pg", E_BURST_CMOS["central"], P_IDLE_CMOS["pg"]),
                     ("CMOS_central_cg_committed", E_BURST_CMOS["central"],
                      P_IDLE_CMOS["cg_committed"]),
                     ("CMOS_central_cg_half", E_BURST_CMOS["central"], P_CG_HALF),
                     ("CMOS_lo_pg", E_BURST_CMOS["lo"], P_IDLE_CMOS["pg"])):
    OUT["curves"][nm] = [
        dict(duty=d, t_idle_s=T_BURST_QAL * (1 - d) / d,
             fJ_per_op=e_op_cmos(T_BURST_QAL * (1 - d) / d, e_bc, pc) * 1e15)
        for d in duties]

json.dump(OUT, open("RESULTS.json", "w"), indent=1)

print("QAL burst: metered %.3f pJ (%.2f fJ/op), complete %.3f pJ (%.2f fJ/op); wake %.1f pJ"
      % (E_BURST_QAL_LB * 1e12, E_BURST_QAL_LB / W_OPS * 1e15,
         E_BURST_QAL_FULL * 1e12, E_BURST_QAL_FULL / W_OPS * 1e15, E_WAKE * 1e12))
print("CMOS burst: central %.3f pJ (%.2f fJ/op), lo %.3f pJ (%.2f fJ/op)"
      % (E_BURST_CMOS["central"] * 1e12, E_BURST_CMOS["central"] / W_OPS * 1e15,
         E_BURST_CMOS["lo"] * 1e12, E_BURST_CMOS["lo"] / W_OPS * 1e15))
print("P_idle QAL %.3f nW (x10: %.2f); CMOS: %s"
      % (P_IDLE_QAL * 1e9, P_IDLE_QAL * 10e9,
         {k: round(v * 1e9, 3) for k, v in P_IDLE_CMOS.items()}))
print("\nCROSSOVERS (headline set):")
for k in sorted(OUT["crossovers"]):
    c = OUT["crossovers"][k]
    if c["T_idle_star_s"]:
        print(" %-58s T*=%9.3g s  duty*=%8.2e  low-duty winner %s"
              % (k, c["T_idle_star_s"], c["duty_star"], c["low_duty_winner"]))
    else:
        print(" %-58s %s" % (k, c["low_duty_winner"]))
