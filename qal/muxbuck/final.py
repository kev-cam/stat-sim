#!/usr/bin/env python3
import json
import math

import analyse as A

# ------------------------------------------------- MEASURED (this run's decks)
Q_BEAT_8 = 35.420030256      # fC  mb_droop8 cycle 0, from the linear tank cap
Q_BEAT_48 = 152.104604526    # fC  mb_d48z1 cycle 0 (ZCS-corrected)
RAIL_AT_066 = 0.7664331      # V   delivered rail, tank pre-charge 0.66
RAIL_AT_058 = 0.6915544      # V   delivered rail, tank pre-charge 0.58
Q_BEAT_8_AT_058 = 31.832276334
DQ_TAP = (2.85878340299998 - (-57.92050531800002)) / 15.0   # fC per idle tap
Q_MUX_N1 = 2.85878340299998  # fC  my own buck+mux delivery into a tank

# -------------------------------------------------------- COMMITTED / derived
C_TANK = 359.79e-15
BAND_TOP_RAIL = 0.7656
BAND_FLOOR_RAIL = 0.6754
T_PULSE = 374.042 - 309.978          # ps MEASURED off the committed ptu buck gates
T_CYCLE = 1600.0                     # ps COMMITTED bank repetition (2*H*T, H=4, T=200)
K = T_CYCLE / T_PULSE

g = (RAIL_AT_066 - RAIL_AT_058) / (0.66 - 0.58)
off = RAIL_AT_066 - g * 0.66
band_rail = BAND_TOP_RAIL - BAND_FLOOR_RAIL
band_tank = band_rail / g
store = C_TANK * band_tank * 1e15    # fC

# effective rail capacitance, DERIVED from the measured LC half-periods
def crail(thalf_ps, L_H, Ctank_F):
    cs = (thalf_ps * 1e-12 / math.pi) ** 2 / L_H
    return 1.0 / (1.0 / cs - 1.0 / Ctank_F)

CR8 = crail(118.176, 15e-9, 359.79e-15)
CR48 = crail(69.432, 2.5e-9, 2158.74e-15)


def nmax(q, tax=True):
    b1 = K * q / (Q_BEAT_8 + (K * DQ_TAP if tax else 0.0))
    b2 = K * store / Q_BEAT_8
    return min(b1, b2)


MARKS = [
    ("a  MEASURED committed buck (qal/ptusk SK_COST)", 9.2578),
    ("b1 ideal buck on the measured 160.2 fC supply draw", 160.2 * 1.2 / 0.766),
    ("b2 ideal buck on the measured inductor ramp (I_pk 1169.11 uA, t_on 24 ps)",
     0.5 * 1169.11e-6 * 24e-12 * 1e15 * 1.2 / 0.766),
    ("c  MY OWN measurement, committed buck block + mux into a tank", Q_MUX_N1),
]

out = {
    "measured_inputs": {
        "Q_beat_8gate_fC": Q_BEAT_8,
        "Q_beat_48gate_fC": Q_BEAT_48,
        "gain_g_V_per_V": g, "offset_V": off,
        "band_rail_mV": band_rail * 1e3, "band_tank_mV": band_tank * 1e3,
        "tank_band_store_fC": store,
        "autonomy_beats": store / Q_BEAT_8,
        "dq_per_idle_tap_fC": DQ_TAP,
        "T_pulse_ps": T_PULSE, "T_cycle_ps": T_CYCLE, "K": K,
        "C_rail_8gate_fF": CR8 * 1e15, "C_rail_48gate_fF": CR48 * 1e15,
        "C_rail_marginal_fF_per_gate": (CR48 - CR8) * 1e15 / 40.0,
        "C_rail_fixed_switch_part_fF": CR8 * 1e15 - 8 * (CR48 - CR8) * 1e15 / 40.0,
        "C_rail_fixed_fraction": 1 - 8 * ((CR48 - CR8) / 40.0) / CR8,
    },
    "nmax_closed_form": {
        "with_shared_node_tax": f"N_max(q) = min({K/(Q_BEAT_8+K*DQ_TAP):.5f}*q , {K*store/Q_BEAT_8:.2f})",
        "no_tax": f"N_max(q) = min({K/Q_BEAT_8:.5f}*q , {K*store/Q_BEAT_8:.2f})",
        "saturation_q_with_tax_fC": (K * store / Q_BEAT_8) * (Q_BEAT_8 + K * DQ_TAP) / K,
        "saturation_q_no_tax_fC": store,
        "hard_ceiling_N": K * store / Q_BEAT_8,
    },
    "marked_points": [{"point": n, "q_fC": q,
                       "N_max_with_tax": nmax(q, True),
                       "N_max_no_tax": nmax(q, False)} for n, q in MARKS],
    "curve": [{"q_fC": q, "N_with_tax": nmax(q, True), "N_no_tax": nmax(q, False)}
              for q in (1, 2, 2.86, 5, 9.26, 15, 21.98, 35, 50, 75, 100, 140, 200, 251, 400, 800)],
}

# ------------------------------------------------------------- area ledger
C_1 = Q_BEAT_8 * 1e-15 * (T_PULSE / T_CYCLE) / band_tank
a1 = C_1 / A.CASPEC
ind1 = A.ind_geom(1e-9)
ind15 = A.ind_geom(15e-9)
out["area"] = {
    "C_1_one_pulse_interval_tank_fF": C_1 * 1e15,
    "marginal_tank_area_per_N_um2": a1,
    "N_knee_where_tank_must_start_growing": C_TANK / C_1,
    "A_recharge_inductor_1nH_um2_octagon": ind1["octagon_um2"],
    "A_recharge_inductor_1nH_um2_bbox": ind1["bbox_um2"],
    "recharge_inductor_R_PDK_ohm": ind1["R_series_ohm"],
    "A_transfer_inductor_15nH_um2_octagon": ind15["octagon_um2"],
    "transfer_inductor_R_PDK_ohm": ind15["R_series_ohm"],
    "transfer_over_recharge_area_ratio": ind15["octagon_um2"] / ind1["octagon_um2"],
    "A_tank_359.79fF_um2": A.mim_area_um2(C_TANK)[0],
    "tank_side_um": A.mim_area_um2(C_TANK)[1],
    "A_mux_switch_um2": A.cell_area(15.0),
    "A_buck_switches_um2": A.cell_area(20.0),
    "A_transfer_switch_plus_park_um2": A.cell_area(32.0),
    "area_crossover_N": A.area_crossover_N(C_TANK, C_1, 1e-9)[0],
    "rows": [A.area_ledger_growing(N, C_TANK, C_1, 1e-9)
             for N in (2, 4, 8, 16, 24, 26, 32, 64, 128, 256, 512, 1024)],
}

# ------------------------------------------------------------- scheduling
prof = [48, 22, 19, 3, 2, 4, 2, 3, 1, 1]
out["scheduling"] = {
    "profile": prof, "banks": len(prof), "gates": sum(prof),
    "plain_RR_utilisation": (sum(prof) / len(prof)) / max(prof),
    "plain_RR_penalty_x": max(prof) * len(prof) / sum(prof),
    "tank_unavailable_ps_per_cycle": 118.184 + 129.37,
    "tank_availability_duty": 1 - (118.184 + 129.37) / T_CYCLE,
    "Q_beat_ratio_48_over_8": Q_BEAT_48 / Q_BEAT_8,
    "gate_count_ratio": 6.0,
    "per_gate_draw_8_fC": Q_BEAT_8 / 8, "per_gate_draw_48_fC": Q_BEAT_48 / 48,
}
json.dump(out, open("RESULTS.json", "w"), indent=1)
print(json.dumps(out, indent=1))
