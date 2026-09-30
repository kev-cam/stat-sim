#!/usr/bin/env python3
"""SKEPTIC ledger audit.  Reads MY OWN row_*.json (produced by the unmodified
upx.py in this directory) and rebuilds the energy ledger with the corrections
pre-stated in SKEPTIC_ACCEPTANCE.json S3.

Nothing here re-simulates.  Every input is a MEASURED field of a row I ran.
"""
import glob, json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
CMOS = 4.14            # fJ/cell/op  -- the HARD bar
CMOS_INV = 10.0831     # fJ/inverter hi+lo cycle -- the EASY bar
CMOS_LVL = 92.8        # ps/level
VGH = 1.5
TIMER = 3.5227


def load(pat="row_*.json"):
    out = []
    for f in sorted(glob.glob(os.path.join(HERE, pat))):
        r = json.load(open(f))
        r["_file"] = os.path.basename(f)
        out.append(r)
    return out


def qsplit(r):
    """Q_close / Q_open, rise and return, summed over the three switch devices
    of the SCORED bank.  This is what decides whether |Q_close|+|Q_open| is a
    double count of a conventional driver."""
    k2 = str(r["LEDGER"]["bank_scored"])
    gc = r["energy_per_bank"][k2]["gate_charge_MEASURED_fC"]
    z = dict(close_rise=0.0, open_rise=0.0, close_ret=0.0, open_ret=0.0,
             conduct_rise=0.0, net_rise=0.0)
    per = {}
    for src, d in gc.items():
        z["close_rise"] += abs(d["Q_close_fC"])
        z["open_rise"] += abs(d["Q_open_fC"])
        z["conduct_rise"] += d["Q_conduct_fC"]
        z["net_rise"] += d["Q_net_over_hop_fC"]
        if "Q_close_return_fC" in d:
            z["close_ret"] += abs(d["Q_close_return_fC"])
            z["open_ret"] += abs(d["Q_open_return_fC"])
        per[src] = dict(Q_close_fC=d["Q_close_fC"], Q_open_fC=d["Q_open_fC"],
                        ratio_open_over_close=(abs(d["Q_open_fC"])
                                               / abs(d["Q_close_fC"])
                                               if d["Q_close_fC"] else None),
                        Q_close_return_fC=d.get("Q_close_return_fC"),
                        Q_open_return_fC=d.get("Q_open_return_fC"))
    z["ratio_open_over_close_rise"] = (z["open_rise"] / z["close_rise"]
                                       if z["close_rise"] else None)
    z["per_device"] = per
    # A CONVENTIONAL driver pays Q_close*V when it RAISES the gate and nothing
    # from the supply when it lowers it (the stored half is dumped to ground).
    # One QAL cycle cycles the switch gate TWICE (deliver the rail, recover it).
    z["Q_real_driver_per_QALcycle_fC"] = z["close_rise"] + z["close_ret"]
    z["E_real_driver_per_QALcycle_fJ"] = VGH * z["Q_real_driver_per_QALcycle_fC"]
    return z


def audit(r):
    n = r["N"]
    L = r["LEDGER"]
    e_tank = L["E_tank_loss_fJ"]
    egd = L["E_gate_drive_idealPWL_per_bank_fJ"]
    q_rise = L["Q_gate_MEASURED_fC"]
    q_cyc = L.get("Q_gate_MEASURED_per_CYCLE_fC")
    well_tot = r["E_wellrail_total_fJ"]
    well_bank = well_tot / r["nb"]
    q = qsplit(r)

    rows = {}

    def put(name, e_drv, timer=0.0, note=""):
        tot = e_tank + e_drv + timer
        rows[name] = dict(E_drv_per_bank_fJ=e_drv, E_timer_fJ=timer,
                          E_bank_fJ=tot, E_per_gate_fJ=tot / n,
                          x_CMOS=tot / n / CMOS, crosses=bool(tot / n < CMOS),
                          note=note)

    # -- as published
    put("AS_PUBLISHED_idealPWL_floor_timer0", egd, 0.0,
        "the headline row; driver term is the MEASURED ideal-PWL energy")
    put("AS_PUBLISHED_idealPWL_floor_timerfloor", egd, TIMER)
    put("AS_PUBLISHED_conventional_rise_hop", VGH * q_rise, 0.0,
        "Phase 1's buildable row: (|Qclose|+|Qopen|) of the RISE hop x 1.5 V")
    if q_cyc:
        put("AS_PUBLISHED_conventional_FULL_CYCLE_A1", VGH * q_cyc, 0.0,
            "Phase 2 amendment A1: all four |Q| edges x 1.5 V")

    # -- S3a: the driver floored at its PHYSICAL minimum
    put("CORRECTED_driver_floored_at_zero", max(0.0, egd), 0.0,
        "a perfectly recovering driver nets ZERO, never negative")
    put("CORRECTED_driver_zero_plus_timerfloor", max(0.0, egd), TIMER)

    # -- S3b: what a conventional driver actually pays
    put("CORRECTED_real_conventional_driver",
        q["E_real_driver_per_QALcycle_fJ"], 0.0,
        "(|Qclose_rise| + |Qclose_return|) x 1.5 V")
    put("CORRECTED_real_conventional_driver_plus_timer",
        q["E_real_driver_per_QALcycle_fJ"], TIMER)

    # -- S3d: the well rail, added the way the record adds it (for comparison)
    put("RECORD_STYLE_floor_plus_wellrail", egd + abs(well_bank), 0.0,
        "reproduces the record's own sensitivity; I argue this DOUBLE-COUNTS")

    # -- S3c: buck sensitivity on the corrected floor row
    base = e_tank + max(0.0, egd)
    eta_be = (base / n) / CMOS       # eta at which the corrected floor row stops crossing
    buck = {}
    for eta in (1.0, 0.95, 0.90, 0.85, 0.80):
        tot = e_tank / eta + max(0.0, egd)
        buck["eta_%.2f" % eta] = dict(E_per_gate_fJ=tot / n,
                                      x_CMOS=tot / n / CMOS,
                                      crosses=bool(tot / n < CMOS))

    B = r["BOUND_BY"]
    A2 = r["A2_functional"] or {}
    return dict(
        tag=r["tag"], N=n, scale=r["scale"], T_ps=r["T_ps"],
        W_nominal_um=r["W_nominal_um"], ACCEPTED=r["ACCEPTED"],
        A1_fail=r["A1_value_fail_count"], A2_margin_mV=A2.get("margin_min_mV"),
        A4=r["A4_zcs_pass"], A5=r["A5_path_identity_pass"],
        A6=r["A6_tank_closure_pass"], worst_gate_pct=r["worst_gate_pct"],
        intra_class_spread_mV=r["intra_class_spread_mV"],
        t_hop_ps=r["t_hop_rise_ps"], t_settle90_ps=B["t_settle90_ps"],
        bound_by=B["bound_by"], level_floor_ps=B["level_floor_ps"],
        x_CMOS_level_scheduled=r["T_ps"] / CMOS_LVL,
        x_CMOS_level_floor=(B["level_floor_ps"] / CMOS_LVL
                            if B["level_floor_ps"] else None),
        stage_time_ps=r["stage_time_measured_ps"],
        E_tank_loss_fJ=e_tank, E_tank_per_gate_fJ=e_tank / n,
        E_gate_drive_idealPWL_per_bank_fJ=egd,
        driver_credit_per_gate_fJ=(-egd / n if egd < 0 else 0.0),
        E_wellrail_total_fJ=well_tot, E_wellrail_per_bank_fJ=well_bank,
        E_wellrail_per_gate_fJ=well_bank / n,
        E_ideal_inputs_bank1_fJ=r["E_ideal_inputs_bank1_fJ"],
        Q_gate_rise_fC=q_rise, Q_gate_cycle_fC=q_cyc,
        Q_split=q,
        tank_closure_residual_pct={
            k: (100.0 * v["tank_closure_residual_fJ"]
                / v["tank_energy_lost_fJ"] if v["tank_energy_lost_fJ"] else None)
            for k, v in r["energy_per_bank"].items()},
        recycle_pct={k: v["recycle_fraction_pct"]
                     for k, v in r["energy_per_bank"].items()},
        m_eff=r["m_eff_MEASURED"], A9_C_ratio=r["A9_C_bank_ratio_measured_over_derived"],
        area_um2_per_gate=r["area"]["total_active_um2_per_gate"],
        tank_um2_per_gate=r["area"]["tank_um2_per_gate"],
        LEDGER_ROWS=rows,
        eta_breakeven_corrected_floor=eta_be,
        buck_sensitivity=buck)


if __name__ == "__main__":
    pat = sys.argv[1] if len(sys.argv) > 1 else "row_*.json"
    out = [audit(r) for r in load(pat)]
    out.sort(key=lambda a: (a["N"], a["scale"] if isinstance(a["scale"], float)
                            else 0, a["tag"]))
    json.dump(out, open(os.path.join(HERE, "SK_LEDGER.json"), "w"), indent=1,
              default=str)
    hdr = ("tag", "N", "ACC", "A1f", "A2mV", "worst%", "t_hop", "t_s90",
           "bnd", "Etank/g", "egd/bank", "pub x", "zero x", "realdrv x",
           "well/g", "eta_be")
    print("%-42s %4s %4s %4s %7s %7s %7s %7s %6s %8s %9s %7s %7s %9s %7s %7s"
          % hdr)
    for a in out:
        R = a["LEDGER_ROWS"]
        print("%-42s %4d %4s %4d %7.1f %7.2f %7.1f %7.1f %6s %8.4f %9.3f "
              "%7.3f %7.3f %9.3f %7.3f %7.4f"
              % (a["tag"][:42], a["N"], a["ACCEPTED"], a["A1_fail"],
                 a["A2_margin_mV"] or float("nan"), a["worst_gate_pct"],
                 a["t_hop_ps"], a["t_settle90_ps"] or float("nan"),
                 a["bound_by"], a["E_tank_per_gate_fJ"],
                 a["E_gate_drive_idealPWL_per_bank_fJ"],
                 R["AS_PUBLISHED_idealPWL_floor_timer0"]["x_CMOS"],
                 R["CORRECTED_driver_floored_at_zero"]["x_CMOS"],
                 R["CORRECTED_real_conventional_driver"]["x_CMOS"],
                 a["E_wellrail_per_gate_fJ"],
                 a["eta_breakeven_corrected_floor"]))
    print("\nwrote SK_LEDGER.json")
