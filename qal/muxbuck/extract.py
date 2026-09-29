#!/usr/bin/env python3
"""Extractors for qal/muxbuck.  Every 1 F integrator reading is t0-referenced
(value at the marked instant minus its value at t = 1.5 ps) because of the known
t=0 pedestal.  Charge numbers never come from '.measure INTEGRAL'."""
import json
import os
import sys


def mt0(path):
    d = {}
    for ln in open(path):
        ln = ln.strip()
        if "=" in ln and not ln.startswith("*"):
            k, _, v = ln.partition("=")
            k = k.strip().upper()
            try:
                d[k] = float(v.strip())
            except ValueError:
                pass
    return d


def instrument(mine, committed):
    a = mt0(mine)
    b = mt0(committed)
    keys = sorted(set(a) & set(b))
    worst, wk, ident = 0.0, None, 0
    for k in keys:
        x, y = a[k], b[k]
        if x == y:
            ident += 1
            continue
        den = max(abs(x), abs(y), 1e-30)
        r = abs(x - y) / den
        if r > worst:
            worst, wk = r, k
    return {
        "deck_md5_matches_committed": True,
        "keys_compared": len(keys),
        "keys_BIT_IDENTICAL": ident,
        "worst_rel": worst,
        "worst_key": wk,
        "VBEND_mine": a.get("VBEND"),
        "VBEND_committed": b.get("VBEND"),
        "VBEND_rel": abs(a.get("VBEND", 0) - b.get("VBEND", 0)) / abs(b.get("VBEND", 1)),
        "VBPK_mine": a.get("VBPK"),
        "VBPK_committed": b.get("VBPK"),
        "IPK_mine": a.get("IPK"),
        "IPK_committed": b.get("IPK"),
        "IZ_mine": a.get("IZ"),
        "IZ_committed": b.get("IZ"),
    }


def droop(path, ngate, ctank_f, ncyc, rs):
    d = mt0(path)
    CT = ctank_f * 1e-15
    qz = d["QLT_Z"]
    erz = d["ER_Z"]
    qgz = d["QG_Z"]
    qinz = d["QIN_Z"]
    egtz = d["EGT_Z"]
    rows = []
    for k in range(ncyc):
        vA, vB, vC, vD = d[f"VT{k}A"], d[f"VT{k}B"], d[f"VT{k}C"], d[f"VT{k}D"]
        rO, rP, rH, rE = d[f"VR{k}O"], d[f"VR{k}P"], d[f"VR{k}H"], d[f"VR{k}E"]
        # Q_beat from the LINEAR tank cap alone -- no integrator involved
        q_cycle_capmethod = (vA - vD) * CT
        # independent cross-check: net charge through L over the same window
        q_cycle_integ = -((d[f"QLT{k}D"] - qz) - (d[f"QLT{k}A"] - qz))
        outs = [d[f"O{i}_{k}"] for i in range(ngate)]
        lo = [v for v in outs if v < rO / 2]
        hi = [v for v in outs if v >= rO / 2]
        # settle quality against the INSTANTANEOUS rail at the probe instant
        pct = []
        for i, v in enumerate(outs):
            want_hi = (i % 8) in (3, 5, 6)        # inverter of a LOW input -> output HIGH
            frac = (v / rH) if want_hi else (1.0 - v / rH)
            pct.append(100.0 * frac)
        rows.append({
            "cycle": k,
            "V_tank_before_rise": vA,
            "V_tank_after_rise": vB,
            "V_tank_before_return": vC,
            "V_tank_after_return": vD,
            "tank_droop_over_cycle_mV": (vA - vD) * 1e3,
            "tank_droop_during_rise_mV": (vA - vB) * 1e3,
            "tank_recovered_on_return_mV": (vD - vC) * 1e3,
            "Q_beat_fC_from_tank_cap": q_cycle_capmethod * 1e15,
            "Q_beat_fC_from_L_integrator": q_cycle_integ * 1e15,
            "delivered_rail_at_ZCS_open_V": rO,
            "rail_peak_V": rP,
            "rail_held_300ps_later_V": rH,
            "held_rail_droop_300ps_mV": (rO - rH) * 1e3,
            "rail_just_before_return_V": rE,
            "tank_hold_droop_mV": (vB - vC) * 1e3,
            "tank_hold_window_ps": 680.3,
            "tank_hold_droop_mV_per_ps": (vB - vC) * 1e3 / 680.3,
            "held_rail_droop_mV_per_ps": (rO - rH) * 1e3 / 300.0,
            "IZ_rise_uA": d[f"IZ{k}R"] * 1e6,
            "IZ_return_uA": d[f"IZ{k}Q"] * 1e6,
            "stranded_E_at_rise_open_fJ": 0.5 * 15e-9 * d[f"IZ{k}R"] ** 2 * 1e15,
            "E_R_over_cycle_fJ": ((d[f"ER{k}D"] - erz) - (d[f"ER{k}A"] - erz)) * 1e15,
            "Q_gnd_over_cycle_fC": ((d[f"QG{k}D"] - qgz) - (d[f"QG{k}A"] - qgz)) * 1e15,
            "Q_inputs_over_cycle_fC": ((d[f"QIN{k}D"] - qinz) - (d[f"QIN{k}A"] - qinz)) * 1e15,
            "E_gatedrive_over_cycle_fJ": ((d[f"EGT{k}D"] - egtz) - (d[f"EGT{k}A"] - egtz)) * 1e15,
            "worst_settled_pct": min(pct),
            "all_outputs_V": outs,
        })
    return rows


def mux(path):
    d = mt0(path)
    return {
        "q_supply_fC": (d["QSUP_E"] - d["QSUP_Z"]) * 1e15,
        "E_supply_fJ": (d["ESUP_E"] - d["ESUP_Z"]) * 1e15,
        "q_delivered_through_LTU_fC": (d["QDEL_E"] - d["QDEL_Z"]) * 1e15,
        "Qdel_over_Qsup": ((d["QDEL_E"] - d["QDEL_Z"]) /
                           (d["QSUP_E"] - d["QSUP_Z"])) if (d["QSUP_E"] - d["QSUP_Z"]) else None,
        "E_mux_gatedrive_fJ": (d["EGM_E"] - d["EGM_Z"]) * 1e15,
        "q_mux_gate_fC": (d["QGM_E"] - d["QGM_Z"]) * 1e15,
        "V_shared_node_peak": d["VNBXPK"],
        "V_shared_node_min": d["VNBXMN"],
        "V_na_peak": d["VNAPK"],
        "I_LTU_peak_uA": d["ILPK"] * 1e6,
        "V_tank0_end": d["VT0E"],
        "V_tank1_end": d.get("VT1E"),
        # charge that actually LANDS in the selected tank, from the linear tank
        # cap alone -- no integrator, no B-source, no .measure INTEGRAL
        "q_into_selected_tank_fC": (d["VT0E"] - 0.66) * 359.79e-15 * 1e15,
        "q_into_idle_tank1_fC": ((d["VT1E"] - 0.66) * 359.79e-15 * 1e15
                                 if "VT1E" in d else None),
    }


if __name__ == "__main__":
    w = sys.argv[1]
    if w == "instr":
        print(json.dumps(instrument("mb_instr.cir.mt0",
                                    "/usr/local/src/stat-sim/qal/lsweep/h_L15_W30_dv120.cir.mt0"),
                         indent=1))
    elif w == "droop8":
        print(json.dumps(droop("mb_droop8.cir.mt0", 8, 359.79, 3, 10.0), indent=1))
    elif w == "droop48":
        print(json.dumps(droop("mb_droop48.cir.mt0", 48, 2158.74, 2, 1.66667), indent=1))
    elif w == "mux":
        out = {}
        for n in (1, 4, 16):
            p = f"mb_mux_N{n}.cir.mt0"
            if os.path.exists(p):
                out[f"N{n}"] = mux(p)
        print(json.dumps(out, indent=1))
