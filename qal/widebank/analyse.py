#!/usr/bin/env python3
"""Build the WIDEBANK sweep table from the row JSONs and answer (d) and (e).

(d) where does per-gate cost stop falling, and which term defeats it
(e) is there an N where per-gate energy beats CMOS inside a usable level time

Nothing here simulates.  Every input is a row_*.json produced by wbx.py off a
.mt0/.prn in this directory.
"""
import glob, json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import wbx

CMOS_BLK = wbx.CMOS_BLOCK_PER_CELL_FJ          # 4.14 fJ/cell/op @1.2 V
CMOS_INV = wbx.CMOS_INV_CYCLE_FJ               # 10.0831 fJ/cycle @1.2 V
CMOS_LVL = wbx.CMOS_BLOCK_LEVEL_PS             # 92.8 ps/level


def load(pattern="row_n*_nb3.json"):
    rows = []
    for f in sorted(glob.glob(os.path.join(HERE, pattern))):
        try:
            rows.append(json.load(open(f)))
        except Exception as e:
            print("skip %s: %s" % (f, e))
    return rows


def lstsq3(N, Y):
    """fit Y = a + b/sqrt(N) + c/N by normal equations (3x3, no numpy)."""
    B = [[1.0, 1.0 / math.sqrt(n), 1.0 / n] for n in N]
    A = [[sum(B[k][i] * B[k][j] for k in range(len(N))) for j in range(3)]
         for i in range(3)]
    r = [sum(B[k][i] * Y[k] for k in range(len(N))) for i in range(3)]
    # gaussian elimination
    M = [A[i] + [r[i]] for i in range(3)]
    for i in range(3):
        p = max(range(i, 3), key=lambda x: abs(M[x][i]))
        M[i], M[p] = M[p], M[i]
        if abs(M[i][i]) < 1e-18:
            return None
        for j in range(i + 1, 3):
            f = M[j][i] / M[i][i]
            for k in range(i, 4):
                M[j][k] -= f * M[i][k]
    x = [0.0] * 3
    for i in (2, 1, 0):
        x[i] = (M[i][3] - sum(M[i][j] * x[j] for j in range(i + 1, 3))) / M[i][i]
    pred = [x[0] + x[1] / math.sqrt(n) + x[2] / n for n in N]
    ss = sum((Y[k] - pred[k]) ** 2 for k in range(len(N)))
    ybar = sum(Y) / len(Y)
    st = sum((y - ybar) ** 2 for y in Y)
    return dict(a_const=x[0], b_over_sqrtN=x[1], c_over_N=x[2],
                R2=(1 - ss / st) if st else None, pred=pred)


def main():
    rows = [r for r in load() if r.get("wmul", 1.0) == 1.0
            and r.get("N") and abs(r.get("dv", 0) - 1.65) < 1e-9]
    # keep the ACCEPTED (smallest passing) T per N; if none passes, keep the
    # largest T tried and mark the point NOT COMPUTING
    best = {}
    for r in rows:
        n = r["N"]
        cur = best.get(n)
        if cur is None:
            best[n] = r; continue
        if r["PASS"] and not cur["PASS"]:
            best[n] = r
        elif r["PASS"] and cur["PASS"] and r["T_ps"] < cur["T_ps"]:
            best[n] = r
        elif (not r["PASS"]) and (not cur["PASS"]) and r["T_ps"] > cur["T_ps"]:
            best[n] = r
    Ns = sorted(best)
    tab = []
    for n in Ns:
        r = best[n]
        LD = r["LEDGER"]
        e2 = r["energy_per_bank"]["2"] if "2" in r["energy_per_bank"] \
            else r["energy_per_bank"][2]
        A2 = r["A2_functional"] or {}
        f = LD["rows"]["idealPWL_floor_MEASURED__timer0_BOUND"]
        fc = LD["rows"]["conventional_from_own_measured_charge__timer0_BOUND"]
        ft = LD["rows"]["idealPWL_floor_MEASURED__timer_floor_ASSUMED_3p5227"]
        fct = LD["rows"]["conventional_from_own_measured_charge__"
                         "timer_floor_ASSUMED_3p5227"]
        tab.append(dict(
            N=n, T_ps=r["T_ps"], PASS=r["PASS"],
            A1_value=r["A1_value_all_banks_pass"],
            A2_bare=A2.get("PASS_bare"), A2_margin_min_mV=A2.get("margin_min_mV"),
            worst_gate_pct=r["worst_gate_pct"],
            rail_bank2_V=r["rail_at_own_boundary_V"]["2"]
            if "2" in r["rail_at_own_boundary_V"]
            else r["rail_at_own_boundary_V"][2],
            t_hop_ps=r["t_hop_rise_ps"], t_hop_ret_ps=r["t_hop_return_ps"],
            t_settle90_ps=r["LEVEL_TIME_measured_bank2_ps"],
            t_settle_func_ps=r["LEVEL_TIME_measured_functional_bank2_ps"],
            level_time_ps=r["T_ps"],
            x_CMOS_level=r["T_ps"] / CMOS_LVL,
            I_pk_uA=r["IPK_uA"]["2"] if "2" in r["IPK_uA"] else r["IPK_uA"][2],
            W_um=r["W_nominal_um"],
            Q_gate_measured_fC=LD["Q_gate_MEASURED_fC"],
            Q_gate_per_um=LD["Q_gate_MEASURED_per_um"],
            Q_gate_lsweep_fit_fC=LD["Q_gate_DERIVED_lsweep_fC"],
            E_tank_loss_fJ=LD["E_tank_loss_fJ"],
            E_switch_conduction_fJ=LD["E_switch_conduction_fJ"],
            E_seriesR_fJ=LD["E_seriesR_rise_fJ"],
            E_gd_idealPWL_fJ=LD["E_gate_drive_idealPWL_per_bank_fJ"],
            E_gd_conventional_fJ=LD["E_gate_drive_conventional_from_measured_fJ"],
            E_bank_floor_fJ=f["E_bank_per_hop_fJ"],
            E_per_gate_floor_fJ=f["E_per_gate_fJ"],
            E_per_gate_floor_x_CMOS=f["x_vs_CMOS_block_4p14"],
            E_per_gate_floor_x_CMOS_iso=f["x_vs_CMOS_block_isoswing_DERIVED"],
            E_per_gate_conv_fJ=fc["E_per_gate_fJ"],
            E_per_gate_conv_x_CMOS=fc["x_vs_CMOS_block_4p14"],
            E_per_gate_floor_timer_fJ=ft["E_per_gate_fJ"],
            E_per_gate_conv_timer_fJ=fct["E_per_gate_fJ"],
            E_per_gate_conv_timer_x_CMOS=fct["x_vs_CMOS_block_4p14"],
            beats_CMOS_block_floor=f["beats_CMOS_block"],
            beats_CMOS_block_conv=fc["beats_CMOS_block"],
            beats_CMOS_inv_floor=f["beats_CMOS_inv_cycle"],
            recycle_pct=e2["recycle_fraction_pct"],
            E_into_rail_fJ=e2["E_into_rail_rise_fJ"],
            E_out_of_tank_fJ=e2["E_out_of_tank_rise_fJ"],
            E_back_fJ=e2["E_back_into_tank_return_fJ"],
            seriesR_frac_pct=100.0 * LD["E_seriesR_rise_fJ"]
            / e2["E_out_of_tank_rise_fJ"] if e2["E_out_of_tank_rise_fJ"] else None,
            switch_frac_pct=100.0 * LD["E_switch_conduction_fJ"]
            / e2["E_out_of_tank_rise_fJ"] if e2["E_out_of_tank_rise_fJ"] else None,
            tank_area_um2=r["area"]["tank_um2"],
            tank_area_per_gate=r["area"]["tank_um2_per_gate"],
            A4_zcs=r["A4_zcs_pass"], A5_path=r["A5_path_identity_pass"],
            A6_close=r["A6_tank_closure_pass"], A7_cut=r["A7_source_side_cut_pass"],
            A9_Cbank_ratio=r["A9_C_bank_ratio_measured_over_derived"],
            intra_class_spread_mV=r["intra_class_spread_mV"],
            wall_s=r.get("wall_s")))

    out = dict(_doc="qal/widebank Phase 1 sweep table. MEASURED unless a key "
                    "says DERIVED/ASSUMED. Energy ledger per "
                    "PRE_REGISTERED.json : ENERGY LEDGER.",
               CMOS_refs=dict(block_per_cell_per_op_fJ_at_1p2V=CMOS_BLK,
                              inverter_cycle_fJ_at_1p2V=CMOS_INV,
                              block_level_ps=CMOS_LVL,
                              iso_swing_block_fJ_DERIVED=wbx.CMOS_BLOCK_PER_CELL_ISO_FJ,
                              iso_swing_inverter_fJ_DERIVED=wbx.CMOS_INV_CYCLE_ISO_FJ),
               table=tab)

    # ---- (d) scaling fits, only on points that COMPUTE
    ok = [t for t in tab if t["PASS"]]
    if len(ok) >= 3:
        N = [t["N"] for t in ok]
        fits = {}
        for key in ("E_per_gate_floor_fJ", "E_per_gate_conv_fJ",
                    "E_per_gate_conv_timer_fJ"):
            fits[key] = lstsq3(N, [t[key] for t in ok])
        out["D_fits_a_plus_b_over_sqrtN_plus_c_over_N"] = fits
        # power-law exponents between consecutive points
        expo = {}
        for key in ("E_per_gate_floor_fJ", "E_per_gate_conv_fJ",
                    "E_tank_loss_fJ", "E_gd_idealPWL_fJ",
                    "E_gd_conventional_fJ", "t_hop_ps", "I_pk_uA",
                    "Q_gate_measured_fC", "E_seriesR_fJ",
                    "E_switch_conduction_fJ"):
            e = []
            for a, b in zip(ok, ok[1:]):
                if a[key] and b[key] and a[key] > 0 and b[key] > 0:
                    e.append(dict(N_from=a["N"], N_to=b["N"],
                                  exponent=round(math.log(b[key] / a[key])
                                                 / math.log(b["N"] / a["N"]), 4),
                                  v_from=a[key], v_to=b[key]))
            expo[key] = e
        out["D_local_power_law_exponents"] = expo
        # where does it stop falling: improvement per doubling
        imp = []
        for a, b in zip(ok, ok[1:]):
            imp.append(dict(N_from=a["N"], N_to=b["N"],
                            pct_improvement_floor=round(
                                100.0 * (1 - b["E_per_gate_floor_fJ"]
                                         / a["E_per_gate_floor_fJ"]), 3),
                            pct_improvement_conv=round(
                                100.0 * (1 - b["E_per_gate_conv_fJ"]
                                         / a["E_per_gate_conv_fJ"]), 3),
                            pct_level_time_cost=round(
                                100.0 * (b["T_ps"] / a["T_ps"] - 1), 3)))
        out["D_improvement_per_step"] = imp
        knee = next((x["N_to"] for x in imp
                     if x["pct_improvement_floor"] < 10.0), None)
        out["D_knee_N_first_step_under_10pct_floor"] = knee

    # ---- (e) the crossing
    cross = {}
    for lbl, key in (("floor_timer0", "E_per_gate_floor_fJ"),
                     ("floor_timer3p5227", "E_per_gate_floor_timer_fJ"),
                     ("conventional_timer0", "E_per_gate_conv_fJ"),
                     ("conventional_timer3p5227", "E_per_gate_conv_timer_fJ")):
        hit = [t for t in ok if t[key] < CMOS_BLK]
        hit_iso = [t for t in ok if t[key] < wbx.CMOS_BLOCK_PER_CELL_ISO_FJ]
        hit_inv = [t for t in ok if t[key] < CMOS_INV]
        cross[lbl] = dict(
            crosses_block_4p14=bool(hit),
            first_N_block=(min(t["N"] for t in hit) if hit else None),
            value_at_first_N=(min((t[key], t["N"]) for t in hit)[0]
                              if hit else None),
            best_N=(min(ok, key=lambda t: t[key])["N"] if ok else None),
            best_value_fJ=(min(t[key] for t in ok) if ok else None),
            best_x_CMOS=(min(t[key] for t in ok) / CMOS_BLK if ok else None),
            crosses_block_isoswing_DERIVED=bool(hit_iso),
            first_N_block_isoswing=(min(t["N"] for t in hit_iso)
                                    if hit_iso else None),
            crosses_inverter_cycle=bool(hit_inv),
            first_N_inverter=(min(t["N"] for t in hit_inv) if hit_inv else None))
    out["E_CROSSING"] = cross
    open(os.path.join(HERE, "SWEEP.json"), "w").write(
        json.dumps(out, indent=1, default=str))

    # ---- text table
    hdr = ("  N    T_ps  PASS A1   A2bare  A2min_mV worst%%   rail2   t_hop  "
           "t_set90 I_pk_uA   W_um  Qg_fC  Etank   Egd_fl Egd_cv  "
           "E/g_fl  xCM  E/g_cv  xCM")
    print(hdr)
    for t in tab:
        print("%4d %7.0f %5s %-5s %-6s %8.2f %6.2f %7.4f %7.1f %7s %8.0f "
              "%6.1f %6.2f %7.1f %6.2f %6.2f %7.4f %5.2f %7.4f %5.2f"
              % (t["N"], t["T_ps"], t["PASS"], t["A1_value"], t["A2_bare"],
                 t["A2_margin_min_mV"] or float("nan"), t["worst_gate_pct"],
                 t["rail_bank2_V"], t["t_hop_ps"],
                 ("%.1f" % t["t_settle90_ps"]) if t["t_settle90_ps"] else "None",
                 t["I_pk_uA"], t["W_um"], t["Q_gate_measured_fC"],
                 t["E_tank_loss_fJ"], t["E_gd_idealPWL_fJ"],
                 t["E_gd_conventional_fJ"], t["E_per_gate_floor_fJ"],
                 t["E_per_gate_floor_x_CMOS"], t["E_per_gate_conv_fJ"],
                 t["E_per_gate_conv_x_CMOS"]))
    print()
    print("CROSSING:", json.dumps(out.get("E_CROSSING", {}), indent=1))
    print("KNEE:", out.get("D_knee_N_first_step_under_10pct_floor"))


if __name__ == "__main__":
    main()
