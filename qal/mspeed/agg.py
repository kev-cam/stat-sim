#!/usr/bin/env python3
"""Aggregate qal/mspeed runs -> RESULTS.json (frontier, ratios, upsizing and
latency verdicts, droop rows, Xyce cross-checks)."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mspeed as M

HERE = M.HERE
RD = os.path.join(HERE, "runs")
T_CMOS = M.T_CMOS


def load(tag, eng="vacask"):
    f = os.path.join(RD, tag, "OUT_%s.json" % eng)
    return json.load(open(f)) if os.path.exists(f) else None


def cell_row(o):
    if o is None:
        return None
    if "error" in o:
        return dict(error=o["error"])
    a = o["acceptance"]
    e3 = o["erosion"]["3"] if "3" in o["erosion"] else o["erosion"][3]
    lat = o["latency_reported"]
    return dict(PASS=a["PASS"], A_value=a["A_value"], B_eye=a["B_eye"], C_handoff=a["C_handoff"],
                value_fails=o["value"]["n_fail"], worst_margin_mV=a["worst_margin_at_commit_mV"],
                worst_overlap_ps=a["worst_overlap_ps"], standing_eye_ps=e3["asymptotic_width_ps"],
                widths_0mV_ps=e3["width_0mV_ps_links"], erosion=e3["sign"],
                establish_minus_srx_max_ps=lat["establish_minus_srx_ps_max"],
                establish_minus_own_rise_max_ps=lat["establish_minus_own_rise_ps_max"],
                true_per_level_latency_ps=lat["true_per_level_latency_ps"],
                true_latency_head_to_link5_ps=lat["true_latency_head_to_link5_commit_ps"],
                rising_lag_ps=o["rising_lag_ps"], E_bank_cycle_fJ=o["energy_reported"]["E_bank_cycle_net_fJ_mean"],
                E_per_cell_eval_fJ=o["energy_reported"]["E_per_cell_eval_fJ"],
                Q_rise_plus_hold_fC=o["energy_reported"]["Q_supplied_rise_plus_hold_fC_mean"],
                hold_bump_mV=o["hold_bump"]["worst_LOW_rise_mV"], wall_s=o.get("wall_s"))


R = dict(study="qal/mspeed", labels="MEASURED unless tagged; ideal driven mesh = BOUND")
chains = {}
for s in M.S_GRID:
    for vdd in (1.2, 1.65):
        for eng in ("vacask", "xyce"):
            f = os.path.join(RD, "chain_s%g_v%g" % (s, vdd), "CHAIN_%s.json" % eng)
            if os.path.exists(f):
                chains["s%g_v%g_%s" % (s, vdd, eng)] = json.load(open(f))["per_stage_90_d4_d8_ps"]
R["cmos_chain_level_ps_MEASURED"] = chains
R["cmos_chain_committed_reference_ps"] = dict(s1_v1p2_xyce_fcrit_skept=52.510)

grid, frontier = {}, {}
for s in M.S_GRID:
    for d in M.D_GRID:
        key = "s%g_d%d" % (s, d)
        rows = {}
        for tt in M.TT_GRID:
            r = cell_row(load(M.tag_of(s, tt, d, "P0")))
            if r is None:
                continue
            p1 = cell_row(load(M.tag_of(s, tt, d, "P1")))
            r["P1"] = p1
            rows[tt] = r
        grid[key] = rows
        # contiguous passing run from 92 downward (pre-registered frontier rule)
        fast, nonmono = None, []
        passing = [tt for tt in M.TT_GRID if tt in rows and rows[tt].get("PASS")]
        run_ok = True
        for tt in M.TT_GRID:
            if tt not in rows:
                break
            if rows[tt].get("PASS") and run_ok:
                fast = tt
            elif not rows[tt].get("PASS"):
                run_ok = False
            elif rows[tt].get("PASS") and not run_ok:
                nonmono.append(tt)
        conf = None
        if fast is not None:
            p1 = rows[fast].get("P1")
            conf = (p1 or {}).get("PASS")
            if conf is False:
                # drop to the next slower passing cell with P1 confirmed
                for tt in M.TT_GRID:
                    if tt > fast and rows.get(tt, {}).get("PASS") and (rows[tt].get("P1") or {}).get("PASS"):
                        fast, conf = tt, True
                        break
        cl = chains.get("s%g_v1.2_vacask" % s)
        ci = chains.get("s%g_v1.65_vacask" % s)
        fr = dict(frontier_T_third_ps=fast, P1_confirmed=conf, nonmonotone_passes=nonmono)
        if fast:
            r = rows[fast]
            fr.update(wavefront_level_rate_vs_cmos=round(d * T_CMOS / fast, 2),
                      per_lane_results_per_s_G=round(1e3 / (3 * fast), 3),
                      wavefront_per_level_ps=round(fast / d, 2),
                      true_per_level_latency_ps=r["true_per_level_latency_ps"],
                      worst_margin_mV=r["worst_margin_mV"], worst_overlap_ps=r["worst_overlap_ps"],
                      standing_eye_ps=r["standing_eye_ps"], E_bank_cycle_fJ=r["E_bank_cycle_fJ"],
                      cmos_level_1p2V_loadmatched_ps=cl, cmos_level_1p65V_isovoltage_ps=ci,
                      latency_ratio_vs_1p2V=(round(r["true_per_level_latency_ps"] / cl, 3) if cl and r["true_per_level_latency_ps"] else None),
                      latency_ratio_vs_1p65V=(round(r["true_per_level_latency_ps"] / ci, 3) if ci and r["true_per_level_latency_ps"] else None))
        frontier[key] = fr
R["grid"] = grid
R["frontier"] = frontier

# upsizing verdict: establishment shrink at fixed (tt,d) + floor movement
ups = {}
for d in M.D_GRID:
    for tt in M.TT_GRID:
        es = {}
        for s in M.S_GRID:
            r = grid["s%g_d%d" % (s, d)].get(tt)
            if r and "error" not in r:
                es["s%g" % s] = r["establish_minus_own_rise_max_ps"]
        if len(es) == 3:
            ups["tt%g_d%d" % (tt, d)] = es
R["establishment_vs_s_reported"] = ups
floors = {("s%g" % s): {("d%d" % d): frontier["s%g_d%d" % (s, d)]["frontier_T_third_ps"] for d in M.D_GRID} for s in M.S_GRID}
R["floors"] = floors

# droop + xyce cross-check rows (whatever exists)
extra = {}
for tag in sorted(os.listdir(RD)):
    if "_rs" in tag or os.path.exists(os.path.join(RD, tag, "OUT_xyce.json")):
        extra[tag] = {eng: cell_row(load(tag, eng)) for eng in ("vacask", "xyce") if load(tag, eng)}
R["droop_and_xyce_rows"] = extra
if os.path.exists(os.path.join(HERE, "CERT.json")):
    C = json.load(open(os.path.join(HERE, "CERT.json")))
    R["certification_summary"] = dict(summary=C["summary"], violations=C["violations"], wall=C["wall_s"],
                                      rail=C["rail_waveforms"]["PASS"], ladder=C["vacask_reltol_ladder_vs_1e-5"],
                                      same_instant_margin_worst_rel=C["margin_same_instant_resample"]["worst_rel"],
                                      integrator=C["xyce_integrator_vs_offline"]["worst_rel_like_for_like"])
json.dump(R, open(os.path.join(HERE, "RESULTS.json"), "w"), indent=1)
print(json.dumps(dict(floors=floors, frontier=frontier), indent=1))
