#!/usr/bin/env python3
"""ONE code path for every reported row.  Settling is always the WORST gate, never
an average -- averaging is exactly how a non-computing bank passes.

1F integrators carry a t=0 PEDESTAL, so EVERY integral here is differenced against
its own Z checkpoint (0.5 ps).  Nothing is read absolutely."""
import os, sys
sys.path.insert(0, "/usr/local/src/stat-sim/qal/skip4")
import skip as SK
import tu

MGATE = SK.MGATE


def ig(m, tag, a, b):
    """t0-referenced 1F-integrator read: value at checkpoint b minus checkpoint a."""
    ka, kb = "%s_%s" % (tag.upper(), a), "%s_%s" % (tag.upper(), b)
    if ka not in m or kb not in m:
        return None
    return m[kb] - m[ka]


def row(scheme, mode, T, dv, m, S, fires, l_nh, total_um, ltu, wsw, ton, foff, tz):
    nb = S["nbank"]
    nh = len(S["hops"])
    out = dict(scheme=scheme, mode=mode, T_ps=T, dv=dv, L_nH=l_nh, W_um=total_um,
               ltu_nH=ltu, wsw_um=wsw, t_on_ps=ton, fire_off_ps=foff,
               nbank=nb, hops=S["hops"], heads=S["heads"], tz_ps=[round(z, 3) for z in tz],
               bound_ps={k: round(S["bound"][k], 2) for k in range(1, nb + 1)},
               close_ps=[round(c, 2) for c in S["close"]],
               open_ps=[round(o, 2) for o in S["open"]])

    # ---- 1. per-gate settling at EVERY stage, worst gate, from the raw measures
    st, stmin = {}, {}
    for k in range(1, nb + 1):
        vr = m.get("VR%dK%d" % (k, k))
        per = {}
        for i in range(MGATE):
            vo = m.get("O%d_%dS" % (k, i))
            if vo is None or not vr or vr <= 0.02:
                continue
            f = (1.0 - vo / vr) if SK.is_hi(k, i) else (vo / vr)
            per[i] = dict(v_o=round(vo, 6), kind="pulldown" if SK.is_hi(k, i) else "pullup",
                          settle_pct=round(100.0 * f, 2))
        st[k] = dict(rail_at_bound_V=round(vr, 6) if vr else None, per_gate=per,
                     worst_pct=round(min(p["settle_pct"] for p in per.values()), 2) if per else None,
                     worst_pullup_pct=round(min([p["settle_pct"] for p in per.values()
                                                 if p["kind"] == "pullup"] or [0]), 2) if per else None,
                     worst_pulldown_pct=round(min([p["settle_pct"] for p in per.values()
                                                   if p["kind"] == "pulldown"] or [0]), 2) if per else None)
        if per:
            stmin[k] = st[k]["worst_pct"]
    out["settling"] = st
    out["worst_gate_all_stages_pct"] = round(min(stmin.values()), 2) if stmin else None
    out["worst_gate_by_stage_pct"] = stmin

    # ---- 2. THE THRESHOLD TEST: delivered input HIGH at EVERY stage
    thr = {}
    for k in range(1, nb + 1):
        if k == 1:
            thr[k] = dict(source="IDEAL (chain head)", min_high_V=round(dv, 6),
                          clears_0p4400=True)
            continue
        his = [m["G%d_%d" % (k, i)] for i in range(MGATE)
               if SK.is_hi(k, i) and ("G%d_%d" % (k, i)) in m]
        los = [m["G%d_%d" % (k, i)] for i in range(MGATE)
               if not SK.is_hi(k, i) and ("G%d_%d" % (k, i)) in m]
        if not his:
            continue
        vr_src = m.get("VR%dK%d" % (k - 1, k - 1))
        thr[k] = dict(source="o%d_* (the predecessor's own outputs)" % (k - 1),
                      min_high_V=round(min(his), 6), all_high_V=[round(v, 6) for v in his],
                      max_low_V=round(max(los), 6) if los else None,
                      predecessor_rail_at_this_boundary_V=round(vr_src, 6) if vr_src else None,
                      required_V=0.4400,
                      margin_mV=round(1000.0 * (min(his) - 0.4400), 2),
                      clears_0p4400=bool(min(his) >= 0.4400))
    out["threshold_test"] = thr
    cl = [k for k, v in thr.items() if "clears_0p4400" in v]
    out["A2_all_stages_clear_0p4400"] = all(thr[k]["clears_0p4400"] for k in cl) if cl else None
    out["A2_min_delivered_high_V"] = round(min(thr[k]["min_high_V"] for k in cl), 6) if cl else None

    # ---- 3. THE HOLD: rail life and droop across the full window
    hold = {}
    for k in range(1, nb + 1):
        if k not in S["c"]:
            continue
        hop = [h for h, (s, t) in enumerate(S["hops"], 1) if t == k][0]
        t_open = S["open"][hop - 1]
        vb = m.get("VR%dB%d" % (k, hop))           # rail at its charging hop's zero
        vk = m.get("VR%dK%d" % (k, k))             # rail at its stage boundary
        vd = m.get("VR%dD" % k)                    # rail at the end of the run
        d_k = S["d"].get(k)
        hold[k] = dict(charging_hop=hop, t_charge_close_ps=round(S["close"][hop - 1], 2),
                       t_charge_open_ps=round(t_open, 2),
                       t_drain_ps=round(d_k, 2) if d_k else None,
                       rail_life_beats=round((d_k - S["close"][hop - 1]) / T, 3) if d_k else None,
                       hold_window_ps=round((d_k - t_open), 2) if d_k else None,
                       rail_at_hop_zero_V=round(vb, 6) if vb else None,
                       rail_at_stage_boundary_V=round(vk, 6) if vk else None,
                       rail_at_run_end_V=round(vd, 6) if vd else None,
                       droop_over_hold_mV=round(1000.0 * (vk - vb), 2) if (vb and vk) else None,
                       droop_over_hold_pct=round(100.0 * (vk - vb) / vb, 2) if (vb and vk) else None,
                       rail_peak_V=round(m["VR%dPK" % k], 6) if ("VR%dPK" % k) in m else None)
    out["hold"] = hold

    # ---- 4. beat period, measured directly, and the hop/settle OVERLAP
    ov = []
    for h, (s, t) in enumerate(S["hops"], 1):
        tc, to = S["close"][h - 1], S["open"][h - 1]
        ov.append(dict(hop=h, src=s, dst=t, t_close_ps=round(tc, 2), t_open_ps=round(to, 2),
                       t_hop_ps=round(to - tc, 3),
                       consumer_stage=t - 1,
                       consumer_boundary_ps=round(S["bound"][t - 1], 2),
                       # does the hop that powers bank t run CONCURRENTLY with the
                       # settling of the stage that feeds it?
                       settle_window_of_feeder_ps=[round(S["bound"][t - 1] - T, 2),
                                                   round(S["bound"][t - 1], 2)],
                       hop_overlaps_feeder_settle=bool(
                           tc < S["bound"][t - 1] and to > S["bound"][t - 1] - T)))
    out["hops_detail"] = ov
    out["t_hop_measured_ps"] = [round(o["t_hop_ps"], 3) for o in ov]
    out["beat_period_ps"] = T
    out["T_over_t_hop"] = round(T / max(o["t_hop_ps"] for o in ov), 3)
    out["boundary_inside_charging_hop"] = any(
        S["bound"][t] < S["open"][h - 1] for h, (s, t) in enumerate(S["hops"], 1)
        if t in S["bound"])

    # ---- 5. accumulated droop stage 1 -> last
    rails = {k: m.get("VR%dK%d" % (k, k)) for k in range(1, nb + 1)}
    out["rail_by_stage_at_its_boundary_V"] = {k: (round(v, 6) if v else None)
                                              for k, v in rails.items()}
    r1, rn = rails.get(1), rails.get(nb)
    out["accumulated_droop_stage1_to_stageN_mV"] = round(1000.0 * (r1 - rn), 2) \
        if (r1 and rn) else None
    out["accumulated_droop_vs_120mV_budget"] = (
        "OVER" if (r1 and rn and 1000.0 * (r1 - rn) > 120.0) else "within") \
        if (r1 and rn) else None

    # ---- 6. COST, including the top-up's OWN GATE DRIVE (the recursion trap)
    nhh = len(S["hops"])
    cost = dict(_units="fJ / fC", _lower_bound_note=(
        "sg13lv_compat.sp ZEROES ad/as/pd/ps, so junction capacitance is ABSENT. "
        "Every charge and energy number here is a LOWER BOUND."))
    for h in range(1, nhh + 1):
        ea, eb = ig(m, "ea%d" % h, "Z", "D"), ig(m, "eb%d" % h, "Z", "D")
        er = ig(m, "er%d" % h, "Z", "D")
        cost["hop%d" % h] = dict(
            E_from_source_rail_fJ=round(ea * 1e15, 4) if ea is not None else None,
            E_into_dest_rail_fJ=round(eb * 1e15, 4) if eb is not None else None,
            E_I2R_fJ=round(er * 1e15, 4) if er is not None else None,
            q_L_fC=round((ig(m, "qlt%d" % h, "Z", "D") or 0) * 1e15, 4))
    egt = ig(m, "egt", "Z", "D")
    cost["transfer_switch_gate_drive_all_hops_fJ"] = round(egt * 1e15, 4) if egt is not None else None
    qdv = ig(m, "qdv", "Z", "D")
    cost["head_precharge_charge_fC"] = round(qdv * 1e15, 4) if qdv is not None else None
    cost["head_precharge_E_fJ"] = round(qdv * dv * 1e15, 4) if qdv is not None else None

    topped = sorted(fires.keys())
    if topped:
        tot_del_q = tot_del_e = 0.0
        per = {}
        for k in topped:
            q = ig(m, "qtu%d" % k, "Z", "D")
            e = ig(m, "etu%d" % k, "Z", "D")
            q = 0.0 if q is None else q
            e = 0.0 if e is None else e
            tot_del_q += q; tot_del_e += e
            qi = ig(m, "qind%d" % k, "Z", "D")
            per[k] = dict(q_delivered_into_rail_fC=round(q * 1e15, 4),
                          _q_measured_at="the 0 V series source VMTU in the rail leg",
                          q_in_inductor_fC=round((qi or 0.0) * 1e15, 4),
                          E_landed_in_bank_fJ=round(e * 1e15, 4),
                          I_peak_uA=round(m.get("ITU%dPK" % k, 0.0) * 1e6, 3),
                          t_fire_ps=round(fires[k]["t_fire"], 2),
                          t_on_ps=fires[k]["t_on"],
                          t_freewheel_ps=round(fires[k]["tfw"], 2),
                          fires_after_its_hop_zero_by_ps=round(
                              fires[k]["t_fire"] - fires[k]["t_open"], 2),
                          fires_before_its_boundary_by_ps=round(
                              fires[k]["bound"] - fires[k]["t_fire"], 2))
        qs = ig(m, "qsup", "Z", "D") or 0.0
        eg = ig(m, "egtu", "Z", "D") or 0.0
        qga = ig(m, "qgabs", "Z", "D") or 0.0
        # |I| integral = 2*Q_gate over a full cycle -> E_real_driver = Q_gate*VGH
        q_gate = 0.5 * qga
        e_gate_real = q_gate * 1.5
        e_sup = qs * dv
        cost["topup"] = dict(
            form="PULSED INDUCTOR, buck action, synchronous freewheel (committed form)",
            banks=topped, per_bank=per,
            q_from_supply_fC=round(qs * 1e15, 4),
            E_from_supply_fJ=round(e_sup * 1e15, 4),
            q_delivered_total_fC=round(tot_del_q * 1e15, 4),
            E_landed_total_fJ=round(tot_del_e * 1e15, 4),
            charge_multiplication_Qdel_over_Qsup=round(tot_del_q / qs, 3) if qs else None,
            E_SWITCH_GATE_DRIVE_fJ=round(e_gate_real * 1e15, 4),
            _E_SWITCH_GATE_DRIVE_is=("Q_gate*VGH, the REAL-DRIVER cost, with Q_gate "
                                     "MEASURED as half the |I| integral over all four "
                                     "gate sources. This is the number to use."),
            Q_gate_total_fC=round(q_gate * 1e15, 4),
            E_gate_ideal_source_net_fJ=round(eg * 1e15, 4),
            _E_gate_ideal_source_net_is=("what the IDEAL PWL sources net out at. An "
                                         "ideal source RECLAIMS the discharge energy, "
                                         "so this tends to zero and would flatter the "
                                         "top-up. Reported only to show the gap."),
            _gate_drive_is_the_recursion_trap=(
                "THREE DRIVEN GATES per topped bank -- high-side pMOS, freewheel nMOS, "
                "and the park nMOS that pins the inductor island -- each switched twice "
                "per beat, drive NOT recovered. E_SWITCH_GATE_DRIVE_fJ counts all three."),
            devices_added_per_topped_bank=5,
            driven_gates_per_topped_bank=3,
            _devices=("1 high-side pMOS, 1 freewheel nMOS, 1 park nMOS, 1 inductor Ltu, "
                      "1 series R"),
            gate_drive_over_energy_landed=round(e_gate_real / tot_del_e, 2)
            if tot_del_e > 0 else None,
            total_topup_cost_fJ=round((e_sup + e_gate_real) * 1e15, 4),
            total_cost_over_energy_landed=round((e_sup + e_gate_real) / tot_del_e, 2)
            if tot_del_e > 0 else None,
            inductors_added=len(topped),
            inductors_for_transfer=nhh,
            inductor_total=len(topped) + nhh)
    else:
        cost["topup"] = None
    # the BOUNDING resistive top-up (mode "rtu"): its own gate drive is metered
    # directly; its SUPPLY charge is reported as a differential against the matched
    # free row in analyze.py, because it draws from the same ideal dV node as the head
    # pre-charge gates and the two cannot be separated inside one deck.
    erg = ig(m, "ergt", "Z", "D")
    qrg = ig(m, "qrga", "Z", "D")
    if erg is not None or qrg is not None:
        q_gate_r = 0.5 * (qrg or 0.0)
        cost["rtu"] = dict(
            form=("RESISTIVE transmission gate to the ideal dV node, chain3's device and "
                  "20 ps window placement VERBATIM, fired at the START of the hold. The "
                  "BOUNDING form: charge-conserving and therefore inefficient, but it "
                  "restores the rail as hard as a supply can."),
            _ideal_source_booking=True,
            Q_gate_total_fC=round(q_gate_r * 1e15, 4),
            E_SWITCH_GATE_DRIVE_fJ=round(q_gate_r * 1.5 * 1e15, 4),
            _E_gate_is="Q_gate*VGH, the REAL-DRIVER cost (ideal PWL sources reclaim the "
                       "discharge, so the net source integral would understate it)",
            E_gate_ideal_source_net_fJ=round((erg or 0.0) * 1e15, 4),
            devices_added_per_topped_bank=2,
            driven_gates_per_topped_bank=2,
            _devices="1 nMOS + 1 pMOS transmission gate to the dV node (no inductor)",
            inductors_added=0,
            q_from_dV_node_total_fC=round((qdv or 0.0) * 1e15, 4),
            _q_from_dV_caveat=("this dV-node total ALSO contains the head pre-charge "
                               "gates' charge; the top-up's own share is the differential "
                               "against the matched free row, computed in analyze.py"),
            chain3_measured_booking_fJ_per_bank_per_hop=[15.2, 29.1])
    else:
        cost["rtu"] = None
    out["cost"] = cost

    # ---- A6 instrument state
    iz = {h: m.get("IZ%d" % h) for h in range(1, nhh + 1)}
    out["A6_instrument"] = dict(
        IZ_uA={h: (round(v * 1e6, 4) if v is not None else None) for h, v in iz.items()},
        IZ_gate_1uA="PASS" if all(abs(v) < 1e-6 for v in iz.values() if v is not None)
        else "FAIL",
        IPK_uA={h: round(m.get("IPK%d" % h, 0.0) * 1e6, 2) for h in range(1, nhh + 1)})
    ident = {}
    for h in range(1, nhh + 1):
        ea, eb = ig(m, "ea%d" % h, "Z", "D"), ig(m, "eb%d" % h, "Z", "D")
        er, esw = ig(m, "er%d" % h, "Z", "D"), ig(m, "esw%d" % h, "Z", "D")
        ean = ig(m, "ean%d" % h, "Z", "D")
        if None in (ea, eb, er, ean):
            continue
        ident[h] = round((ean - esw - er) * 1e15, 6) if esw is not None else None
    out["A6_instrument"]["path_identity_fJ"] = ident

    # ---- the three acceptance criteria, scored
    out["ACCEPTANCE"] = dict(
        A1_all_four_stages_90pct=bool(out["worst_gate_all_stages_pct"] is not None
                                      and out["worst_gate_all_stages_pct"] >= 90.0),
        A1_worst_gate_pct=out["worst_gate_all_stages_pct"],
        A2_all_stages_clear_0p4400=out["A2_all_stages_clear_0p4400"],
        A2_min_delivered_high_V=out["A2_min_delivered_high_V"])
    return out
