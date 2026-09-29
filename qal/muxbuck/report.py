#!/usr/bin/env python3
"""qal/muxbuck final assembly: instrument gate, charge balance, N_max curve,
round-robin, area ledger.  Run after the decks land."""
import json
import math
import os

import analyse as A
import extract as E

BAND_TOP = 0.7656      # COMMITTED: banktank m=10 probe delivered rail
BAND_FLOOR = 0.6754    # pre-registered band floor (committed settling grid point)
BAND_RAIL_mV = (BAND_TOP - BAND_FLOOR) * 1e3

T_PULSE = 60.0         # ps  MEASURED off the committed ptu buck schedule (HS on 313.978 -> OUT off 374.042)
T_CYCLE = 1600.0       # ps  COMMITTED bank cycle (banktank bank 1: rise 200, return 1000, repeat 1800)
K = T_CYCLE / T_PULSE

C_TANK = 359.79e-15    # COMMITTED
C_TANK_STIFF = C_TANK

MARKS = {
    "a_measured_committed_buck": 9.26,
    "b1_ideal_buck_on_the_measured_160.2fC_supply_draw": 160.2 * 1.2 / 0.766,
    "b2_ideal_buck_on_the_measured_inductor_ramp": 0.5 * 1169.11e-6 * 24e-12 * 1e15 * 1.2 / 0.766,
}

out = {}

# ---------------------------------------------------------------- (b) instrument
if os.path.exists("mb_instr.cir.mt0"):
    out["b_instrument_check"] = E.instrument(
        "mb_instr.cir.mt0",
        "/usr/local/src/stat-sim/qal/lsweep/h_L15_W30_dv120.cir.mt0")

# ------------------------------------------------------------- (c) tank droop
if os.path.exists("mb_droop8.cir.mt0"):
    r8 = E.droop("mb_droop8.cir.mt0", 8, 359.79, 3, 10.0)
    out["c_tank_droop_8gate_rows"] = r8
    # incremental gain g = d(delivered rail)/d(tank voltage), from the cycle-to-cycle
    # movement of the two measured quantities -- a MEASURED slope, not a guess
    pts = [(row["V_tank_before_rise"], row["delivered_rail_at_ZCS_open_V"]) for row in r8]
    if len(pts) >= 2:
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        n = len(xs)
        sx, sy = sum(xs), sum(ys)
        sxx = sum(x * x for x in xs)
        sxy = sum(x * y for x, y in zip(xs, ys))
        g = (n * sxy - sx * sy) / (n * sxx - sx * sx)
    else:
        g = None
    Q_beat = r8[0]["Q_beat_fC_from_tank_cap"]
    out["c_summary"] = {
        "gain_g_drail_per_dtank_MEASURED": g,
        "band_rail_mV": BAND_RAIL_mV,
        "band_tank_mV": BAND_RAIL_mV / g if g else None,
        "Q_beat_fC_cycle0": Q_beat,
        "Q_beat_fC_all_cycles": [row["Q_beat_fC_from_tank_cap"] for row in r8],
        "Q_beat_cross_check_L_integrator_fC": [row["Q_beat_fC_from_L_integrator"] for row in r8],
        "tank_hold_droop_mV_per_ps": [row["tank_hold_droop_mV_per_ps"] for row in r8],
        "held_rail_droop_mV_per_ps": [row["held_rail_droop_mV_per_ps"] for row in r8],
        "committed_held_rail_droop_mV_per_ps": 28.6 / 300.0,
        "tank_over_bank_droop_ratio_MEASURED":
            [row["held_rail_droop_mV_per_ps"] / row["tank_hold_droop_mV_per_ps"]
             if row["tank_hold_droop_mV_per_ps"] else None for row in r8],
        "capacitive_ratio_prediction_Cbank_over_Ctank": 34.7 / 359.79,
    }

if os.path.exists("mb_droop48.cir.mt0"):
    r48 = E.droop("mb_droop48.cir.mt0", 48, 2158.74, 2, 1.66667)
    out["f_tank_droop_48gate_rows"] = r48

# --------------------------------------------------------------- (d) mux switch
muxes = {}
for n in (1, 4, 16):
    p = f"mb_mux_N{n}.cir.mt0"
    if os.path.exists(p):
        muxes[n] = E.mux(p)
if muxes:
    out["d_mux_rows"] = muxes
    if 1 in muxes and 16 in muxes:
        q1 = muxes[1]["q_into_selected_tank_fC"]
        q16 = muxes[16]["q_into_selected_tank_fC"]
        out["d_summary"] = {
            "q_into_tank_vs_Ntaps": {str(k): v["q_into_selected_tank_fC"] for k, v in muxes.items()},
            "dq_per_idle_tap_fC": (q1 - q16) / 15.0,
            "mux_gate_charge_fC": muxes[1]["q_mux_gate_fC"],
            "mux_gate_energy_fJ": muxes[1]["E_mux_gatedrive_fJ"],
            "mux_gate_energy_per_beat_if_fired_once_per_revolution":
                "E_gate / N -- amortises as 1/N by construction; the width does NOT grow with N",
        }

json.dump(out, open("RESULTS.json", "w"), indent=1)
print(json.dumps(out, indent=1)[:6000])
