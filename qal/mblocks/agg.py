#!/usr/bin/env python3
"""qal/mblocks aggregator: runs/*/OUT.json + LEVEL.json + STA_*.json + IC.json
-> RESULTS.json and the README tables.  All labels MEASURED / DERIVED / ASSUMED
are carried from the sources; nothing is recomputed from a simulator here
except arithmetic on recorded numbers."""
import glob, json, math, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
T_REG = 315.378          # ps DERIVED (307.1 @0 fF, 335.7 @6.91 fF MEASURED)
UNC = 100.0              # ps clock-uncertainty corner
TT = 92.0
GATE_MV = 69.924


def load(p):
    return json.load(open(p)) if os.path.exists(p) else None


def nmin(vals):
    v = [x for x in vals if x is not None]
    return min(v) if v else None


def nmax(vals):
    v = [x for x in vals if x is not None]
    return max(v) if v else None


def fs(x, d=1):
    return "None" if x is None else ("%.*f" % (d, x) if isinstance(x, (int, float)) else str(x))


def merge_group_runs(runs):
    """union of CRC group runs (electrically disjoint trees, PRE_REGISTERED)."""
    runs = [r for r in runs if r and "acceptance" in r]
    if not runs:
        return None
    NB = runs[0]["NB"]
    waves = runs[0]["waves"]
    m = dict(NB=NB, tt=runs[0]["tt"], T=runs[0]["T"], waves=waves, groups=[r["tag"] for r in runs],
             n_groups=len(runs), fets=sum(r["fets"] for r in runs),
             gates=sum(r["stats"]["gates"] for r in runs),
             nand2=sum(r["stats"]["nand2"] for r in runs),
             delay_inverters=sum(r.get("delay_inverters", 0) for r in runs),
             wall_s_sum=round(sum(r["wall_s"] for r in runs), 1),
             wall_s_max=round(max(r["wall_s"] for r in runs), 1),
             npts=[r["npts"] for r in runs], ms_per_pt=[r["ms_per_pt"] for r in runs])
    # final words: OR of group words, compared to the full reference
    ref = runs[0]["value"]["reference"]
    words = {}
    for r in runs:
        for n, w in r["value"]["final_words_hw"].items():
            words[n] = words.get(n, 0) | (w or 0)
    mask = 0
    for r in runs:
        mask |= r["value"].get("output_bit_mask", 0xFFFFFFFF)
    bad = [[n, words[n], ref[n] & mask] for n in ref if words.get(n) != (ref[n] & mask)]
    m["output_bit_mask"] = mask
    vf = sum(r["value"]["n_fail"] for r in runs)
    vc = sum(r["value"]["checked"] for r in runs)
    m["value"] = dict(checked=vc, n_fail=vf, PASS=(vf == 0),
                      final_words_hw=words, reference=ref, words_in=runs[0]["value"]["words_in"],
                      final_vs_reference=dict(ok=len(ref) - len(bad), bad=bad, PASS=(not bad)))
    # acceptance: worst over groups
    acc = [r["acceptance"] for r in runs]
    wm = nmin(a["worst_margin_at_commit_mV"] for a in acc)
    wo = nmin(a["worst_overlap_ps"] for a in acc)
    eyes = [a["min_eye_0mV_real_links_ps"] for a in acc]
    st = [a["standing_eye_ps"] for a in acc if a["standing_eye_ps"]]
    m["acceptance"] = dict(A_value=m["value"]["PASS"] and m["value"]["final_vs_reference"]["PASS"],
                           B_eye=all(a["B_eye"] for a in acc), C_handoff=all(a["C_handoff"] for a in acc),
                           worst_margin_at_commit_mV=wm,
                           worst_margin_where=([(a["worst_margin_where"] or []) + [r["tag"]] for a, r in zip(acc, runs)
                                                if a["worst_margin_at_commit_mV"] == wm] or [None])[0],
                           worst_overlap_ps=wo,
                           min_eye_0mV_real_links_ps=nmin(eyes),
                           standing_eye_ps=(round(float(np.mean(st)), 2) if st else None),
                           standing_eye_per_group=st,
                           PASS=all(a["PASS"] for a in acc) and m["value"]["final_vs_reference"]["PASS"])
    m["latency_ps"] = dict(max_raw=nmax(r["latency_ps"]["max_raw"] for r in runs),
                           min_raw=nmin(r["latency_ps"]["min_raw"] for r in runs),
                           max_gate69=nmax(r["latency_ps"]["max_gate69"] for r in runs),
                           per_group=[r["latency_ps"]["max_raw"] for r in runs],
                           definition=runs[0]["latency_ps"]["definition"])
    lags = [r["rising_lag_ps"] for r in runs]
    m["rising_lag_ps"] = dict(min=nmin(l["min"] for l in lags), max=nmax(l["max"] for l in lags))
    # per-link eye / commit / overlap summary (worst over groups and waves)
    links = {}
    for k in range(1, NB + 1):
        ws, cs, ov, mg = [], [], [], []
        for r in runs:
            for n in waves:
                L = r["links"][str(k)][str(n)]
                if "width_ps" in L.get("0mV", {}):
                    ws.append(L["0mV"]["width_ps"])
                if L.get("commit_raw_ps"):
                    cs.append(L["commit_raw_ps"] - (n * r["T"] + (k - 1) * r["tt"]))
                if k < NB:
                    H = r["handoff"][str(k)][str(n)]
                    if H.get("overlap_ps") is not None:
                        ov.append(H["overlap_ps"])
                    if H.get("margin_at_commit_mV"):
                        mg.append(min(v for v in H["margin_at_commit_mV"].values() if v is not None))
        links[k] = dict(eye_0mV_ps_min=min(ws) if ws else None, eye_0mV_ps_max=max(ws) if ws else None,
                        commit_minus_slot_ps_min=round(min(cs), 2) if cs else None,
                        commit_minus_slot_ps_max=round(max(cs), 2) if cs else None,
                        overlap_ps_min=min(ov) if ov else None,
                        margin_at_commit_mV_min=min(mg) if mg else None,
                        derived_receiver=(k == NB))
    m["links_summary"] = links
    # charge books: SUM across groups (union circuit)
    ch = {}
    for k in range(1, NB + 1):
        ch[k] = dict(phase="ABC"[(k - 1) % 3])
        for key in ("Q_rise_fC", "Q_hold_fC", "Q_fall_fC", "E_rise_fJ", "E_hold_fJ", "E_fall_fJ"):
            vals = [r["charge_spec_reported_not_gated"][str(k)][key] for r in runs
                    if r["charge_spec_reported_not_gated"][str(k)][key] is not None]
            ch[k][key] = round(sum(vals), 3) if vals else None
    m["charge_spec_reported_not_gated"] = ch
    m["erosion_sign"] = sorted(set(e["sign"] for r in runs for e in r["erosion"].values()))
    return m


def single_run(r):
    if not r or "acceptance" not in r:
        return None
    m = dict(r)
    NB, waves = r["NB"], r["waves"]
    links = {}
    for k in range(1, NB + 1):
        ws, cs, ov, mg = [], [], [], []
        for n in waves:
            L = r["links"][str(k)][str(n)]
            if "width_ps" in L.get("0mV", {}):
                ws.append(L["0mV"]["width_ps"])
            if L.get("commit_raw_ps"):
                cs.append(L["commit_raw_ps"] - (n * r["T"] + (k - 1) * r["tt"]))
            if k < NB:
                H = r["handoff"][str(k)][str(n)]
                if H.get("overlap_ps") is not None:
                    ov.append(H["overlap_ps"])
                if H.get("margin_at_commit_mV"):
                    mg.append(min(v for v in H["margin_at_commit_mV"].values() if v is not None))
        links[k] = dict(eye_0mV_ps_min=min(ws) if ws else None, eye_0mV_ps_max=max(ws) if ws else None,
                        commit_minus_slot_ps_min=round(min(cs), 2) if cs else None,
                        commit_minus_slot_ps_max=round(max(cs), 2) if cs else None,
                        overlap_ps_min=min(ov) if ov else None,
                        margin_at_commit_mV_min=min(mg) if mg else None,
                        derived_receiver=(k == NB))
    m["links_summary"] = links
    m["erosion_sign"] = sorted(set(e["sign"] for e in r["erosion"].values()))
    m["gates"] = r["stats"]["gates"]
    m["nand2"] = r["stats"]["nand2"]
    for k in ("links", "handoff", "erosion"):
        m.pop(k, None)
    return m


def engine_agreement(vac, xy):
    """like-for-like on the waves both ran (2..5): commit instants, eyes,
    margins at commit, per-bank charges."""
    if not vac or not xy or "links" not in vac or "links" not in xy:
        return None
    waves = [n for n in xy["waves"] if n in vac["waves"]]
    NB = vac["NB"]
    rows, worst = [], dict(commit_ps=0.0, eye_ps=0.0, margin_rel=0.0, Q_rel=0.0)
    for k in range(1, NB + 1):
        for n in waves:
            a, b = vac["links"][str(k)][str(n)], xy["links"][str(k)][str(n)]
            dc = (a["commit_raw_ps"] or 0) - (b["commit_raw_ps"] or 0)
            de = a["0mV"].get("width_ps", 0) - b["0mV"].get("width_ps", 0)
            worst["commit_ps"] = max(worst["commit_ps"], abs(dc))
            worst["eye_ps"] = max(worst["eye_ps"], abs(de))
            row = dict(link=k, wave=n, d_commit_ps=round(dc, 3), d_eye_ps=round(de, 3))
            if k < NB:
                ha, hb = vac["handoff"][str(k)][str(n)], xy["handoff"][str(k)][str(n)]
                ma = nmin((ha.get("margin_at_commit_mV") or {}).values())
                mb = nmin((hb.get("margin_at_commit_mV") or {}).values())
                if ma is not None and mb is not None:
                    rel = abs(ma - mb) / max(abs(mb), 1e-9)
                    worst["margin_rel"] = max(worst["margin_rel"], rel)
                    worst["margin_abs_mV"] = max(worst.get("margin_abs_mV", 0.0), abs(ma - mb))
                    row.update(margin_vacask_mV=ma, margin_xyce_mV=mb, margin_rel=round(rel, 4))
                row.update(d_overlap_ps=round((ha.get("overlap_ps") or 0) - (hb.get("overlap_ps") or 0), 3))
            rows.append(row)
    qa = [vac["charge_spec_reported_not_gated"][str(k)]["Q_rise_fC"] for k in range(1, NB + 1)]
    qb = [xy["charge_spec_reported_not_gated"][str(k)]["Q_rise_fC"] for k in range(1, NB + 1)]
    qrel = []
    for x, y in zip(qa, qb):
        if x and y:
            qrel.append(round(abs(x - y) / abs(y), 4))
            worst["Q_rel"] = max(worst["Q_rel"], abs(x - y) / abs(y))
    worst["Q_rel_per_bank"] = qrel
    # value agreement
    va = vac["value"]["final_words_hw"]
    vb = xy["value"]["final_words_hw"]
    vals_same = all(va.get(str(n)) == vb.get(str(n)) for n in waves)
    return dict(waves=waves, worst=worst, value_words_identical=vals_same,
                Q_rise_vacask_fC=qa, Q_rise_xyce_fC=qb,
                xyce_note="Xyce charges here are from the SAME offline trapezoid on the .prn (no .measure); "
                          "VACASK run covers 24 words, Xyce the first 6 periods of the identical deck",
                bands=dict(commit_ps=1.0, eye_ps=1.0, margin_rel=0.01, Q_rel=0.02),
                PASS=dict(commit=worst["commit_ps"] < 1.0, eye=worst["eye_ps"] < 1.0,
                          margin=worst["margin_rel"] < 0.01, Q=worst["Q_rel"] < 0.02),
                rows=rows, wall=dict(vacask_s=vac["wall_s"], vacask_npts=vac["npts"],
                                     xyce_s=xy["wall_s"], xyce_npts=xy["npts"]))


def cmos_tables(L, t_levels, sta, nb_qal, lat_qal, tt=TT):
    """L = logic nand-levels; t_levels = {label: ps}; sta = STA json rows."""
    out = {}
    thr_qal = 1e3 / (3 * tt)            # Gresults/s per lane
    Ds = [3, 6, 9, L]
    for label, tl in t_levels.items():
        rows = {}
        for D in Ds:
            st = int(math.ceil(L / float(D)))
            per = D * tl + T_REG
            perc = per + UNC
            rows[str(D)] = dict(stages=st, period_ps=round(per, 1), period_corner_ps=round(perc, 1),
                                results_per_s_G=round(1e3 / per, 3), results_corner_G=round(1e3 / perc, 3),
                                latency_ps=round(st * per, 1), latency_corner_ps=round(st * perc, 1),
                                ratio_throughput_QAL_over_CMOS=round(thr_qal / (1e3 / per), 2),
                                ratio_throughput_corner=round(thr_qal / (1e3 / perc), 2),
                                ratio_latency_CMOS_over_QAL=(round(st * per / lat_qal, 2) if lat_qal else None))
        out[label] = dict(t_level_ps=tl, t_reg_ps=T_REG, rows=rows,
                          bare_chain_latency_ps=round(L * tl, 1),
                          ratio_bare_chain_over_QAL=(round(L * tl / lat_qal, 3) if lat_qal else None))
    if sta:
        for lib, _ in sta["rows"][str(Ds[0])].items():
            rows = {}
            for D in Ds:
                r = sta["rows"][str(D)][lib]
                per = r["min_period_ps"]
                rows[str(D)] = dict(stages=r["stages"], period_ps=per,
                                    period_headfree_ps=r["min_period_headfree_ps"],
                                    results_per_s_G=round(1e3 / per, 3),
                                    latency_ps=round(r["stages"] * per, 1),
                                    ratio_throughput_QAL_over_CMOS=round(thr_qal * per / 1e3, 2),
                                    ratio_latency_CMOS_over_QAL=(round(r["stages"] * per / lat_qal, 2) if lat_qal else None))
            out["STA_" + lib] = dict(rows=rows, note="OpenSTA, liberty pin loads, real fanout incl. the head "
                                     "(input registers fan out to the trees); head-free = false-path from "
                                     "the input registers (lower bound, head fanout removed as the wave's "
                                     "ideal head removes it); set_clock_transition 0.15 ns (ALU flow)")
    out["QAL"] = dict(results_per_s_G=round(thr_qal, 3), period_ps=3 * tt, T_third_ps=tt, latency_ps=lat_qal, banks=nb_qal,
                      note="one result per 3*T_third per lane (bank initiation interval); the wavefront "
                           "level-rate (d levels per T_third) is NOT a throughput")
    return out


def main():
    R = dict(study="qal/mblocks", T_third_ps=TT, period_ps=3 * TT)
    R["IC_harness_anchor"] = load(os.path.join(HERE, "IC.json"))
    LV = load(os.path.join(HERE, "LEVEL.json"))
    R["level"] = LV
    t_levels = {}
    if LV:
        for key, vdd in (("level_vacask_v1.2", 1.2), ("level_vacask_v1.65", 1.65)):
            r = LV.get(key)
            if r and "chains" in r:
                a = r["chains"]["a"]["half"]["per_level_4_to_10_ps"]
                b = r["chains"]["b"]["half"]["per_level_4_to_10_ps"]
                i = r["chains"]["i"]["half"]["per_level_4_to_10_ps"]
                t_levels["nand2_%gV" % vdd] = max(a, b)
                t_levels.setdefault("_detail", {})["%gV" % vdd] = dict(
                    nand2_both_inputs=a, nand2_one_tied_high=b, inverter=i,
                    xyce={arm: LV.get("level_xyce_v%g" % vdd, {}).get("chains", {}).get(arm, {}).get("half", {}).get("per_level_4_to_10_ps")
                          for arm in "abi"})
    detail = t_levels.pop("_detail", None)
    R["t_level_ps"] = dict(used=t_levels, detail=detail, inverter_reference_1p2V=52.51,
                           method="depth-12 chain @2 fF, (t_cross(stage10)-t_cross(stage4))/6 at VDD/2, "
                                  "2 ps input edge; worst of both-inputs-switching and one-input-tied-high; "
                                  "VACASK primary, Xyce alongside")
    runs = {os.path.basename(os.path.dirname(p)): load(p)
            for p in glob.glob(os.path.join(HERE, "runs", "*", "OUT.json"))}
    # nand2 cell-class lanes (6-bank nand2(x,x) chains, P0-alt, mesh3 harness)
    lanes = {}
    for tag, r in runs.items():
        if tag.startswith("icn") and r and "acceptance" in r:
            a = r["acceptance"]
            lanes[tag] = dict(d=r.get("d_levels"), tt=r["tt"], PASS=a["PASS"], A=a["A_value"], B=a["B_eye"], C=a["C_handoff"],
                              worst_margin_mV=a["worst_margin_at_commit_mV"], worst_overlap_ps=a["worst_overlap_ps"],
                              eye_min_ps=a["min_eye_0mV_real_links_ps"], standing_eye_ps=a["standing_eye_ps"],
                              commit_minus_slot_b2_ps=round(r["links"]["2"]["3"]["commit_raw_ps"] - (3 * r["T"] + r["tt"]), 1)
                              if r["links"]["2"]["3"].get("commit_raw_ps") else None,
                              rising_lag_ps=r["rising_lag_ps"], wall_s=r["wall_s"])
    R["nand2_lanes"] = lanes
    blocks = {}
    import re as _re
    cfgs = set()
    for tag in runs:
        m = _re.match(r"(crc_g\d|mul\d+_all)_tt(\d+)_nw(\d+)(_d(\d))?(_rl)?$", tag)
        if m:
            cfgs.add((int(m.group(2)), int(m.group(5)) if m.group(5) else 3, int(m.group(3)), bool(m.group(6))))
    for tt_, dlev, nw, rl in sorted(cfgs):
        dsuf = (("_d%d" % dlev) if dlev != 3 else "") + ("_rl" if rl else "")
        suf = "_nw%d%s" % (nw, dsuf)
        cfg = "d%d_tt%d" % (dlev, tt_) + ("_rl" if rl else "") + (("_nw%d" % nw) if nw != 24 else "")
        # ---- CRC
        crc_groups = [runs.get("crc_g%d_tt%d%s" % (g, tt_, suf)) for g in range(4)]
        crc = merge_group_runs(crc_groups)
        if crc:
            crc["config"] = cfg
            crc["d_levels"] = dlev
            crc["retime"] = "last(level-order rule)" if rl else "first(committed)"
            crc["levels_logic"] = 12
            xa = runs.get("xyce_crc_g0_tt%d_nw6%s" % (tt_, dsuf))
            crc["xyce_anchor"] = single_run(xa)
            crc["engine_agreement"] = engine_agreement(runs.get("crc_g0_tt%d%s" % (tt_, suf)), xa)
            crc["cmos"] = cmos_tables(12, t_levels, load(os.path.join(HERE, "STA_crc.json")), crc["NB"],
                                      crc["latency_ps"]["max_raw"], tt=tt_)
            crc["groups_detail"] = [single_run(g) for g in crc_groups]
            crc["groups_complete"] = all(g is not None for g in crc_groups)
            blocks["crc32_" + cfg] = crc
        # ---- MUL
        for N in (8, 16):
            r = runs.get("mul%d_all_tt%d%s" % (N, tt_, suf))
            s_ = single_run(r)
            if s_:
                s_["config"] = cfg
                s_["retime"] = "last(level-order rule)" if rl else "first(committed)"
                Lg = load(os.path.join(HERE, "STA_mul%d.json" % N))
                s_["levels_logic"] = Lg["levels_logic"] if Lg else None
                xa = runs.get("xyce_mul%d_all_tt%d_nw6%s" % (N, tt_, dsuf))
                s_["xyce_anchor"] = single_run(xa)
                s_["engine_agreement"] = engine_agreement(r, xa)
                s_["cmos"] = cmos_tables(s_["levels_logic"], t_levels, Lg, s_["NB"], s_["latency_ps"]["max_raw"], tt=tt_)
                blocks["mul%dx%d_%s" % (N, N, cfg)] = s_
    R["blocks"] = blocks
    R["other_runs"] = sorted(k for k in runs if k.startswith("xyce") or k.startswith("ic"))
    json.dump(R, open(os.path.join(HERE, "RESULTS.json"), "w"), indent=1, default=str)
    # ---- console summary
    print("t_level:", t_levels)
    for name, b in blocks.items():
        a = b["acceptance"]
        print("%s: NB=%d gates=%d fets=%d PASS=%s value=%s/%s ref_bad=%d worst_margin=%s mV worst_ov=%s ps "
              "standing_eye=%s latency_raw=%s..%s ps lat69=%s wall=%s"
              % (name, b["NB"], b["gates"], b["fets"], a["PASS"], b["value"]["checked"] - b["value"]["n_fail"],
                 b["value"]["checked"], len(b["value"]["final_vs_reference"]["bad"]),
                 fs(a["worst_margin_at_commit_mV"]), fs(a["worst_overlap_ps"], 2), a["standing_eye_ps"],
                 b["latency_ps"]["min_raw"], b["latency_ps"]["max_raw"], b["latency_ps"]["max_gate69"],
                 b.get("wall_s", b.get("wall_s_sum"))))
        for lab, c in b["cmos"].items():
            if lab == "QAL":
                continue
            print("   %-22s " % lab + " | ".join("D=%s: %s ps, %sG, lat %s, thr x%s, lat x%s"
                  % (D, r["period_ps"], fs(r["results_per_s_G"], 2), r["latency_ps"],
                     fs(r["ratio_throughput_QAL_over_CMOS"], 2), r["ratio_latency_CMOS_over_QAL"])
                  for D, r in c["rows"].items()))
        if b.get("engine_agreement"):
            print("   engine:", b["engine_agreement"]["worst"], b["engine_agreement"]["PASS"],
                  "words identical:", b["engine_agreement"]["value_words_identical"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
