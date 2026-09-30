#!/usr/bin/env python3
"""Build the PHASE 2 (cell-upsizing) table and answer (b), (c) and (d).

Nothing here simulates.  Every input is a row_*.json written by upx.py off a
.mt0/.prn in this directory, plus CRUX.json from crux.py.

(b) t_hop, level time end to end MEASURED, energy per gate and per op, area
(c) the trade curve: level time vs area vs energy, exchange rate if one exists
(d) per-gate settling and a VALUE check at every scale
"""
import glob, json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import upx

CMOS_BLK = upx.CMOS_BLOCK_PER_CELL_FJ     # 4.14 fJ/cell/op @1.2 V
CMOS_INV = upx.CMOS_INV_CYCLE_FJ          # 10.0831 fJ/cycle @1.2 V
CMOS_LVL = upx.CMOS_BLOCK_LEVEL_PS        # 92.8 ps/level
ETIMER = upx.E_TIMER_FLOOR_FJ             # 3.5227


def load():
    rows = []
    for f in sorted(glob.glob(os.path.join(HERE, "row_*.json"))):
        try:
            rows.append(json.load(open(f)))
        except Exception as e:
            print("skip %s: %s" % (f, e))
    return rows


def flat(r):
    LD = r["LEDGER"]
    B = r["BOUND_BY"]
    A2 = r["A2_functional"] or {}
    e2 = r["energy_per_bank"].get("2") or r["energy_per_bank"].get(2)
    f = LD["rows"]["idealPWL_floor_MEASURED__timer0_BOUND"]
    ft = LD["rows"]["idealPWL_floor_MEASURED__timer_floor_ASSUMED_3p5227"]
    fc = LD["rows"]["conventional_from_own_measured_charge__timer0_BOUND"]
    fct = LD["rows"]["conventional_from_own_measured_charge__"
                     "timer_floor_ASSUMED_3p5227"]
    # PHASE 2 AMENDMENT A1: the row a buildable driver actually pays -- the FULL
    # CYCLE (two close/open pairs), not the rise hop alone.
    fcy = LD["rows"].get("conventional_FULL_CYCLE_measured_charge__"
                         "timer0_BOUND")
    fcyt = LD["rows"].get("conventional_FULL_CYCLE_measured_charge__"
                          "timer_floor_ASSUMED_3p5227")
    ar = r["area"]
    sc = r["scale_scored_bank"]
    lvl_floor = B["level_floor_ps"]
    # the WELL-CHARGED variant: the pMOS well rail is uncharged under the
    # committed ideal-rails convention.  Phase 1 showed charging it erases its
    # crossing, so it is carried as a named column at every point.
    ewell = abs(r["E_wellrail_total_fJ"]) / r["nb"] / r["N"]
    return dict(
        tag=r["tag"], N=r["N"], scale=r["scale"], sc_scored=sc,
        scale_per_bank=r["scale_per_bank"],
        WP_um=r["WP_um"], WN_um=r["WN_um"], L_nH=r["L_nH"],
        ct_override=r["ct_override_fF"], cload_fF=r["cload_fF"],
        extra=r.get("extra", ""),
        T_ps=r["T_ps"], ACCEPTED=r["ACCEPTED"],
        A1=r["A1_value_all_banks_pass"], A1_fail=r["A1_value_fail_count"],
        A2=A2.get("PASS_bare"), A2_mV=A2.get("margin_min_mV"),
        A2_3sig=A2.get("PASS_3sigma_CONTINUITY_ONLY"),
        A4=r["A4_zcs_pass"], A5=r["A5_path_identity_pass"],
        A6=r["A6_tank_closure_pass"],
        worst_gate_pct=r["worst_gate_pct"],
        worst_per_bank=r["settling_worst_per_bank_pct"],
        intra_class_spread=r["intra_class_spread_mV"],
        sep_min_mV=r["separation_min_mV"],
        # ---- TIME, all MEASURED
        t_hop_ps=r["t_hop_rise_ps"], t_hop_ret_ps=r["t_hop_return_ps"],
        t_set90_ps=B["t_settle90_ps"], t_setfunc_ps=B["t_settle_functional_ps"],
        bound_by=B["bound_by"], slack_ps=B["slack_hop_minus_settle90_ps"],
        level_floor_ps=lvl_floor,
        stage_time_ps=r["stage_time_measured_ps"],
        stage_time_func_ps=r["stage_time_measured_functional_ps"],
        x_CMOS_level_floor=(lvl_floor / CMOS_LVL) if lvl_floor else None,
        x_CMOS_level_T=r["T_ps"] / CMOS_LVL,
        x_CMOS_level_stage=(r["stage_time_measured_ps"] / CMOS_LVL
                            if r["stage_time_measured_ps"] else None),
        # ---- ENERGY
        E_tank_fJ=LD["E_tank_loss_fJ"],
        E_sw_cond_fJ=LD["E_switch_conduction_fJ"],
        E_seriesR_fJ=LD["E_seriesR_rise_fJ"],
        E_park_fJ=LD["E_out_of_tank_via_park_cycle_fJ"],
        E_gd_floor_fJ=LD["E_gate_drive_idealPWL_per_bank_fJ"],
        E_gd_conv_fJ=LD["E_gate_drive_conventional_from_measured_fJ"],
        Qg_fC=LD["Q_gate_MEASURED_fC"], Qg_per_um=LD["Q_gate_MEASURED_per_um"],
        Qg_cycle_fC=LD.get("Q_gate_MEASURED_per_CYCLE_fC"),
        Qg_cycle_per_um=LD.get("Q_gate_MEASURED_per_CYCLE_per_um"),
        Qg_return_over_rise=LD.get("Q_gate_return_over_rise"),
        E_gd_conv_cycle_fJ=LD.get("E_gate_drive_conventional_FULL_CYCLE_fJ"),
        E_g_convcyc=(fcy or {}).get("E_per_gate_fJ"),
        x_convcyc=(fcy or {}).get("x_vs_CMOS_block_4p14"),
        E_g_convcyc_t=(fcyt or {}).get("E_per_gate_fJ"),
        x_convcyc_t=(fcyt or {}).get("x_vs_CMOS_block_4p14"),
        W_um=r["W_nominal_um"], I_pk_uA=r["IPK_uA"]["2"]
        if "2" in r["IPK_uA"] else r["IPK_uA"][2],
        E_g_floor=f["E_per_gate_fJ"], x_floor=f["x_vs_CMOS_block_4p14"],
        E_g_floor_t=ft["E_per_gate_fJ"], x_floor_t=ft["x_vs_CMOS_block_4p14"],
        E_g_conv=fc["E_per_gate_fJ"], x_conv=fc["x_vs_CMOS_block_4p14"],
        E_g_conv_t=fct["E_per_gate_fJ"], x_conv_t=fct["x_vs_CMOS_block_4p14"],
        x_floor_iso=f["x_vs_CMOS_block_isoswing_DERIVED"],
        x_floor_inv=f["x_vs_CMOS_inv_cycle"],
        E_well_per_gate_fJ=ewell,
        E_g_floor_wellcharged=f["E_per_gate_fJ"] + ewell,
        x_floor_wellcharged=(f["E_per_gate_fJ"] + ewell) / CMOS_BLK,
        E_bank_floor_fJ=f["E_bank_per_hop_fJ"],
        recycle_pct=e2["recycle_fraction_pct"],
        m_eff=r["m_eff_MEASURED"], C_meas_fF=r["A9_C_bank_measured_secant_fF"],
        C_nom_fF=r["C_bank_fF_DERIVED"], C_tank_fF=r["C_tank_fF_DERIVED"],
        A9_ratio=r["A9_C_bank_ratio_measured_over_derived"],
        # ---- AREA
        tank_um2=ar["tank_um2"], tank_um2_pg=ar["tank_um2_per_gate"],
        cells_um2_pg=ar["cells_um2_per_gate"],
        switch_um2_pg=ar["switch_um2_per_gate"],
        total_um2_pg=ar["total_active_um2_per_gate"],
        wall_s=r.get("wall_s"), mstep_ps=r["mstep_ps"])


def expo(S, Y):
    if len(S) < 2 or any(y is None or y <= 0 for y in Y):
        return None
    return dict(
        exponent_end_to_end=math.log(Y[-1] / Y[0]) / math.log(S[-1] / S[0]),
        per_step=[dict(s_from=S[i], s_to=S[i + 1],
                       exponent=round(math.log(Y[i + 1] / Y[i])
                                      / math.log(S[i + 1] / S[i]), 4),
                       v_from=Y[i], v_to=Y[i + 1])
                  for i in range(len(S) - 1)],
        v_first=Y[0], v_last=Y[-1], ratio=Y[-1] / Y[0])


def series(tab, n, key="scale"):
    """the MAIN series at a given N: uniform scale, nominal L, no overrides."""
    sel = [t for t in tab if t["N"] == n and abs(t["L_nH"] - 15.0) < 1e-9
           and t["ct_override"] is None and t["cload_fF"] == 2.0
           and not t["extra"]                      # no control label
           and not isinstance(t["scale"], (list, tuple))
           and len(set(t["scale_per_bank"])) == 1]
    sel = sorted(sel, key=lambda t: t["sc_scored"])
    seen, out = set(), []
    for t in sel:                                  # belt and braces
        if t["sc_scored"] in seen:
            raise SystemExit("duplicate scale %g in the N=%d main series: %s"
                             % (t["sc_scored"], n, t["tag"]))
        seen.add(t["sc_scored"]); out.append(t)
    return out


def pareto(pts, tkey, ekey):
    """a point is DOMINATED if another has BOTH lower time and lower energy."""
    out = []
    for p in pts:
        dom = [q["tag"] for q in pts
               if q is not p and q[tkey] is not None and p[tkey] is not None
               and q[ekey] <= p[ekey] and q[tkey] <= p[tkey]
               and (q[ekey] < p[ekey] or q[tkey] < p[tkey])]
        out.append(dict(tag=p["tag"], scale=p["sc_scored"],
                        time_ps=p[tkey], energy_fJ_per_gate=p[ekey],
                        dominated_by=dom, on_frontier=not dom))
    return out


def main():
    rows = load()
    tab = [flat(r) for r in rows]
    tab.sort(key=lambda t: (t["N"], t["sc_scored"], t["L_nH"], t["tag"]))

    out = dict(
        _doc="qal/upsize PHASE 2 -- CELL UPSIZING AS THE SPEED LEVER. MEASURED "
             "unless a key says DERIVED or ASSUMED. Energy ledger per "
             "PRE_REGISTERED_PHASE2.json : ENERGY_LEDGER. Switch conduction "
             "and series R are INSIDE E_tank_loss and are NOT added again.",
        CMOS_REFERENCES=dict(
            HARD_BAR_fJ_per_cell_per_op=CMOS_BLK,
            hard_basis="232 fJ/op / 56 cells, SG13G2 typ 1.2 V",
            EASY_BAR_fJ_per_inverter_cycle=CMOS_INV,
            easy_basis="one hi+lo cycle of the same 1.12p/0.74n cell at 1.2 V; "
                       "Phase 1 showed QAL is below it at EVERY N, reported "
                       "only so it cannot be presented as the result",
            LEVEL_ps=CMOS_LVL, level_basis="928 ps / 10 levels",
            iso_swing_block_fJ_DERIVED=upx.CMOS_BLOCK_PER_CELL_ISO_FJ,
            swing_note="QAL at 1.65 V vs CMOS at 1.2 V is the PRIMARY and "
                       "non-flattering comparison; the swing is a requirement "
                       "of QAL, not a free parameter."),
        _time_keys=dict(
            level_floor_ps="MEASURED max(t_hop_rise, t_settle90) -- the "
                           "rule-independent floor under any beat, and the "
                           "right quantity for the trade curve",
            stage_time_ps="MEASURED bank3-valid minus bank2-valid, the "
                          "end-to-end level time actually observed",
            T_ps="the SCHEDULED beat from the committed analytic rule "
                 "T = ceil10(TZ8*sqrt(N/8)*sqrt(s)*sqrt(L/15) + 73.5), which "
                 "reproduces Phase 1's accepted T at every N"),
        TABLE=tab)

    # ---------- (c) the trade, per N
    trade = {}
    for n in sorted(set(t["N"] for t in tab)):
        S = series(tab, n)
        ok = [t for t in S if t["ACCEPTED"]]
        use = ok if len(ok) >= 2 else S
        sc = [t["sc_scored"] for t in use]
        d = dict(N=n, scales=sc, n_accepted=len(ok), n_points=len(S),
                 all_accepted=bool(len(ok) == len(S) and S))
        for key, lbl in (("level_floor_ps", "LEVEL_FLOOR_measured"),
                         ("stage_time_ps", "stage_time_measured"),
                         ("T_ps", "T_scheduled"),
                         ("t_hop_ps", "t_hop"),
                         ("t_set90_ps", "t_settle90"),
                         ("E_g_floor", "E_per_gate_floor_timer0"),
                         ("E_g_conv", "E_per_gate_conventional"),
                         ("E_g_convcyc", "E_per_gate_conventional_FULL_CYCLE"),
                         ("E_tank_fJ", "E_tank_loss_bank"),
                         ("Qg_fC", "Q_gate_measured"),
                         ("I_pk_uA", "I_pk"),
                         ("tank_um2_pg", "tank_area_per_gate"),
                         ("cells_um2_pg", "cell_area_per_gate"),
                         ("total_um2_pg", "total_active_area_per_gate"),
                         ("m_eff", "m_eff_measured"),
                         ("recycle_pct", "recycle_fraction")):
            d["exp_" + lbl] = expo(sc, [t[key] for t in use])
        # bound_by per scale -- the whole question
        d["bound_by_per_scale"] = {t["sc_scored"]: t["bound_by"] for t in use}
        d["slack_ps_per_scale"] = {t["sc_scored"]: t["slack_ps"] for t in use}
        # PARETO: does ANY upsized point beat s=1 on both axes?
        d["PARETO_level_floor_vs_E_floor"] = pareto(use, "level_floor_ps",
                                                    "E_g_floor")
        d["PARETO_stage_time_vs_E_floor"] = pareto(use, "stage_time_ps",
                                                   "E_g_floor")
        base = next((t for t in use if t["sc_scored"] == 1.0), None)
        if base:
            d["VS_S1"] = []
            for t in use:
                if t["sc_scored"] == 1.0:
                    continue
                dt = ((t["level_floor_ps"] / base["level_floor_ps"] - 1) * 100
                      if base["level_floor_ps"] else None)
                de = (t["E_g_floor"] / base["E_g_floor"] - 1) * 100
                da = (t["total_um2_pg"] / base["total_um2_pg"] - 1) * 100
                # EXCHANGE RATE: % level-time CHANGE per % area and per %
                # energy.  NEGATIVE numerator = slower.  A real
                # area-for-speed trade needs this to be negative-over-positive.
                d["VS_S1"].append(dict(
                    scale=t["sc_scored"],
                    pct_level_floor_change=dt, pct_energy_change=de,
                    pct_area_change=da,
                    faster=bool(dt is not None and dt < 0),
                    cheaper=bool(de < 0),
                    smaller=bool(da < 0),
                    speedup_x=(base["level_floor_ps"] / t["level_floor_ps"]
                               if t["level_floor_ps"] else None),
                    EXCHANGE_pct_speed_per_pct_area=(-dt / da
                                                     if (da and dt is not None)
                                                     else None),
                    EXCHANGE_pct_speed_per_pct_energy=(-dt / de
                                                       if (de and dt is not None)
                                                       else None),
                    verdict=("BUYS SPEED" if (dt is not None and dt < 0)
                             else "COSTS SPEED AND ENERGY AND AREA")))
        trade[str(n)] = d
    out["TRADE_per_N"] = trade

    # ---------- the MATCHED PAIR: identical tank and switch, 8x gate count
    a = next((t for t in tab if t["N"] == 8 and t["sc_scored"] == 8.0
              and t["ct_override"] is None and abs(t["L_nH"] - 15) < 1e-9), None)
    b = next((t for t in tab if t["N"] == 64 and t["sc_scored"] == 1.0
              and t["ct_override"] is None and abs(t["L_nH"] - 15) < 1e-9), None)
    if a and b:
        out["MATCHED_PAIR_same_tank_same_switch"] = dict(
            _why="C_bank_nominal = 35.979*(N/8)*s, so (N=8,s=8) and (N=64,s=1) "
                 "have IDENTICAL nominal C_bank (287.832 fF), IDENTICAL C_tank "
                 "(2878.32 fF) and IDENTICAL switch width (84.853 um). The "
                 "resonant cost is the same by construction and the ONLY "
                 "difference is how it is SPENT: 8 gates of 8x width, or 64 "
                 "gates of 1x width. This is the user's challenge in its "
                 "cleanest form.",
            few_big=dict(tag=a["tag"], N=8, scale=8.0,
                         E_bank_floor_fJ=a["E_bank_floor_fJ"],
                         E_per_gate_fJ=a["E_g_floor"], x_CMOS=a["x_floor"],
                         level_floor_ps=a["level_floor_ps"],
                         t_hop_ps=a["t_hop_ps"], t_set90_ps=a["t_set90_ps"],
                         bound_by=a["bound_by"],
                         total_um2_pg=a["total_um2_pg"],
                         C_tank_fF=a["C_tank_fF"], W_um=a["W_um"],
                         ACCEPTED=a["ACCEPTED"]),
            many_small=dict(tag=b["tag"], N=64, scale=1.0,
                            E_bank_floor_fJ=b["E_bank_floor_fJ"],
                            E_per_gate_fJ=b["E_g_floor"], x_CMOS=b["x_floor"],
                            level_floor_ps=b["level_floor_ps"],
                            t_hop_ps=b["t_hop_ps"], t_set90_ps=b["t_set90_ps"],
                            bound_by=b["bound_by"],
                            total_um2_pg=b["total_um2_pg"],
                            C_tank_fF=b["C_tank_fF"], W_um=b["W_um"],
                            ACCEPTED=b["ACCEPTED"]),
            ratio_E_per_gate_fewbig_over_manysmall=(a["E_g_floor"]
                                                    / b["E_g_floor"]),
            ratio_level_floor_fewbig_over_manysmall=(a["level_floor_ps"]
                                                     / b["level_floor_ps"]
                                                     if b["level_floor_ps"]
                                                     else None),
            C_tank_identical=bool(abs(a["C_tank_fF"] - b["C_tank_fF"]) < 1e-6),
            W_identical=bool(abs(a["W_um"] - b["W_um"]) < 1e-9))

    # ---------- controls
    ctl = {}
    for t in tab:
        if isinstance(t["scale"], (list, tuple)) or \
                len(set(t["scale_per_bank"])) > 1:
            ctl.setdefault("E1_load_not_scaled", []).append(t)
        elif t["ct_override"] is not None:
            ctl.setdefault("E2_tank_from_measured_C", []).append(t)
        elif abs(t["L_nH"] - 15.0) > 1e-9:
            ctl.setdefault("E3_iso_hop", []).append(t)
        elif t["mstep_ps"] and t["N"] == 64 and t["sc_scored"] == 8.0 and \
                abs(t["mstep_ps"] - 0.7071067811865476) > 1e-9:
            ctl.setdefault("E4_half_step", []).append(t)
    out["CONTROLS"] = {k: v for k, v in ctl.items()}

    # ---------- crux, folded in so the answer is in one file
    cp = os.path.join(HERE, "CRUX.json")
    if os.path.exists(cp):
        out["CRUX"] = json.load(open(cp))["ANSWER"]

    open(os.path.join(HERE, "RESULTS_PHASE2.json"), "w").write(
        json.dumps(out, indent=1, default=str))

    # ---------- text
    print("%-34s %4s %5s %7s %8s %8s %-7s %7s %8s %8s %7s %8s %8s %6s %5s %5s"
          % ("tag", "N", "s", "T", "t_hop", "t_set90", "bound", "slack",
             "lvlfloor", "stage", "E/g_fl", "xCMOS", "E/g_cv", "um2/g",
             "ACC", "A4"))
    for t in tab:
        print("%-34s %4d %5g %7g %8.2f %8.2f %-7s %+7.2f %8.2f %8.2f %7.4f "
              "%8.3f %8.3f %6.1f %5s %5s"
              % (t["tag"][:34], t["N"], t["sc_scored"], t["T_ps"],
                 t["t_hop_ps"], t["t_set90_ps"] or float("nan"),
                 t["bound_by"] or "?", t["slack_ps"] or float("nan"),
                 t["level_floor_ps"] or float("nan"),
                 t["stage_time_ps"] or float("nan"),
                 t["E_g_floor"], t["x_floor"], t["E_g_conv"],
                 t["total_um2_pg"], t["ACCEPTED"], t["A4"]))
    print()
    for n, d in trade.items():
        print("=== N=%s ===  scales %s  accepted %d/%d"
              % (n, d["scales"], d["n_accepted"], d["n_points"]))
        print("  bound_by: %s" % d["bound_by_per_scale"])
        for k in ("exp_LEVEL_FLOOR_measured", "exp_E_per_gate_floor_timer0",
                  "exp_total_active_area_per_gate", "exp_t_hop",
                  "exp_t_settle90"):
            e = d.get(k)
            if e:
                print("  %-34s exponent_in_s %+.4f  %.4g -> %.4g (x%.3f)"
                      % (k, e["exponent_end_to_end"], e["v_first"],
                         e["v_last"], e["ratio"]))
        for v in d.get("VS_S1", []):
            print("  s=%g vs s=1: level %+.1f%%  energy %+.1f%%  area %+.1f%%"
                  "  -> %s" % (v["scale"], v["pct_level_floor_change"],
                               v["pct_energy_change"], v["pct_area_change"],
                               v["verdict"]))
        fr = [p["scale"] for p in d["PARETO_level_floor_vs_E_floor"]
              if p["on_frontier"]]
        print("  Pareto frontier (level_floor vs E/gate): scales %s" % fr)
        print()


if __name__ == "__main__":
    main()
