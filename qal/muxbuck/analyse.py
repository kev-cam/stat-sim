#!/usr/bin/env python3
"""qal/muxbuck -- the charge balance, the N_max curve and the area ledger.

Everything here is arithmetic on quantities that are either MEASURED (my own
decks), COMMITTED (a digit from a git-tracked .mt0 / README), PDK (a density or
formula read out of IHP-Open-PDK), or ASSUMED (my judgement, labelled).
Nothing is swept that can be computed.
"""
import json
import math

# ---------------------------------------------------------------- PDK models
CASPEC = 1.5e-15      # F/um^2   PDK cmim_caspec  = "1.5m" * 1e-12
CPSPEC = 40e-18       # F/um     PDK cmim_cpspec  = "40p"  * 1e-12
MIM_MIN_LW = 1.14     # um       PDK cmim_minLW
MIM_MAX_C = 8e-12     # F        PDK cmim_maxC

# std-cell footprint vs total device width, least-squares on the PDK's own
# sg13g2_inv_1 .. inv_16 LEF SIZE records against their CDL widths
A_CELL_A0 = 3.2508    # um^2
A_CELL_B = 1.0397     # um^2 per um of device width

MU0 = 3.1416 * 4e-7


def mim_area_um2(C_farad):
    """Square cmim of capacitance C.  PDK formula C = l*w*caspec + 2*(l+w)*cpspec."""
    c = C_farad
    # 1.5e-15 a^2 + 4*40e-18 a - c = 0
    A = CASPEC
    B = 4 * CPSPEC
    a = (-B + math.sqrt(B * B + 4 * A * c)) / (2 * A)
    return a * a, a


def ind_L(d_um, w=2.0, s=2.1, nr=2):
    d, w_, s_ = d_um * 1e-6, w * 1e-6, s * 1e-6
    davg = d + nr * (w_ + s_) - s_
    rho = (nr * (w_ + s_) - s_) / davg
    return MU0 * 0.5 * 1.07 * nr * nr * davg * (math.log(2.29 / rho) + 0.19 * rho * rho)


def ind_R(d_um, w=2.0, s=2.1, nr=2):
    d, w_, s_ = d_um * 1e-6, w * 1e-6, s * 1e-6
    return (nr * (d + w_ + (nr - 1) * (s_ + w_)) * 3.314 + 60e-6) / w_ * 0.01


def ind_geom(L_target, w=2.0, s=2.1, nr=2):
    lo, hi = 5.0, 3000.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if ind_L(mid, w, s, nr) < L_target:
            lo = mid
        else:
            hi = mid
    d = (lo + hi) / 2
    dout = d + 2 * (nr * (w + s) - s)
    return {"d_inner_um": d, "d_outer_um": dout,
            "bbox_um2": dout ** 2, "octagon_um2": 0.8284 * dout ** 2,
            "R_series_ohm": ind_R(d, w, s, nr)}


def cell_area(width_um):
    return A_CELL_A0 + A_CELL_B * width_um


# ------------------------------------------------------------ the N_max curve
def nmax_curve(q_fC, Q_beat_fC, C_tank_F, dV_band_tank_V, K, dq_tap_fC):
    """N_max as a function of charge delivered per buck pulse.

    Three ceilings, all with the SAME K = T_cycle/T_pulse prefactor:
      throughput  N <= K * q_eff / Q_beat           (the buck must resupply what N banks draw)
      tank store  N <= K * (C_tank*dV_band) / Q_beat (a pulse cannot usefully exceed the band)
      shared node q_eff = q - N*dq_tap              (idle taps are swung every pulse)
    Solving the first with q_eff gives N = K*q / (Q_beat + K*dq_tap).
    """
    store_fC = C_tank_F * dV_band_tank_V * 1e15
    n_thr = K * q_fC / (Q_beat_fC + K * dq_tap_fC)
    n_store = K * min(q_fC, store_fC) / Q_beat_fC
    n_store_tax = K * min(q_fC, store_fC) / (Q_beat_fC + K * dq_tap_fC)
    return {"q_fC": q_fC,
            "N_throughput_no_tax": K * q_fC / Q_beat_fC,
            "N_throughput_with_tax": n_thr,
            "tank_store_fC": store_fC,
            "N_binding": min(n_store_tax, n_thr),
            "which_binds": "tank store (band)" if q_fC > store_fC else "buck delivery"}


def area_ledger(N, C_tank_F, L_buck_H):
    ind = ind_geom(L_buck_H)
    a_ind = ind["octagon_um2"]
    a_tank, side = mim_area_um2(C_tank_F)
    a_mux = cell_area(15.0)                 # committed OUT/mux TG: nmos 5u + pmos 10u
    a_buck_sw = cell_area(20.0)             # HS pmos 10u + FW nmos 10u
    a_own = N * (a_ind + a_tank + a_mux + a_buck_sw)
    a_mux_arch = 1 * (a_ind + a_buck_sw) + N * (a_tank + a_mux)
    return {"N": N,
            "inductor": ind,
            "A_inductor_um2": a_ind,
            "A_tank_um2": a_tank, "tank_side_um": side,
            "A_mux_switch_um2": a_mux, "A_buck_switches_um2": a_buck_sw,
            "own_buck_per_bank_um2": a_own,
            "shared_muxed_buck_um2": a_mux_arch,
            "saving_um2": a_own - a_mux_arch,
            "saving_ratio": a_own / a_mux_arch if a_mux_arch else None}


def area_ledger_growing(N, C_stiff_F, C_1_F, L_buck_H):
    """Same ledger, but the tank is allowed to be the LARGER of its stiffness
    requirement and the autonomy requirement.  Under an OWN buck each tank only
    has to bridge one pulse interval; under a SHARED buck it has to bridge N of
    them, so the shared architecture's tanks grow once N*C_1 exceeds C_stiff."""
    ind = ind_geom(L_buck_H)
    a_ind = ind["octagon_um2"]
    a_mux = cell_area(15.0)
    a_bs = cell_area(20.0)
    C_own = max(C_stiff_F, C_1_F)
    C_shared = max(C_stiff_F, N * C_1_F)
    a_t_own, _ = mim_area_um2(C_own)
    a_t_shared, side = mim_area_um2(C_shared)
    own = N * (a_ind + a_bs + a_mux + a_t_own)
    shared = (a_ind + a_bs) + N * (a_mux + a_t_shared)
    return {"N": N, "C_tank_own_fF": C_own * 1e15, "C_tank_shared_fF": C_shared * 1e15,
            "tank_side_shared_um": side,
            "A_tank_own_um2": a_t_own, "A_tank_shared_um2": a_t_shared,
            "own_um2": own, "shared_um2": shared,
            "saving_um2": own - shared, "saving_ratio": own / shared,
            "mux_wins": shared < own,
            "MIM_over_max_C_8pF": C_shared > MIM_MAX_C}


def area_crossover_N(C_stiff_F, C_1_F, L_buck_H, nmax=100000):
    prev = None
    for N in range(2, nmax):
        r = area_ledger_growing(N, C_stiff_F, C_1_F, L_buck_H)
        if not r["mux_wins"]:
            return N, prev
        prev = r
    return None, prev


if __name__ == "__main__":
    print(json.dumps({"self_test_1nH": ind_geom(1e-9),
                      "tank_359.79fF": mim_area_um2(359.79e-15),
                      "mux_TG_um2": cell_area(15.0)}, indent=1))
