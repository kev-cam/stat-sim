#!/usr/bin/env python3
"""Per-row extraction for the stage-skipping study.

Every number here is MEASURED off a .mt0 or a .prn.  Conventions inherited
verbatim from qal/chain3/extract.py (which inherits lsweep/swsweep/gateb):

  * per-gate settling at the bank's OWN stage boundary, NEVER aggregated:
      pull-DOWN cell (input HIGH):  pct = 100*(1 - V(o)/rail_k)
      pull-UP   cell (input LOW ):  pct = 100*(V(o)/rail_k)
    with rail_k = V(rail k) at that same boundary instant.
  * data-pattern guard: pull-DOWN output <= 0.10*rail, pull-UP >= 0.50*rail.
  * margin budget 120 mV, cumulative and compounding-only; absolute cliff 0.60 V.
"""
import json, math, os, sys
from skip import (MGATE, SCHED, EDGE, TAIL, T1, is_hi, in_net, schedule,
                  parse_mt0, read_prn, zero_after_peak, trace, at)

CLIFF   = 0.60          # V, absolute functional floor (device-Vt fact)
BUDGET  = 120.0         # mV, pre-registered rail-depression allowance
VB_REF  = {1.0: 0.6758936, 1.2: 0.7138163}   # committed delivered rail per dV


def settle_pct(k, i, v, rail):
    return 100.0 * ((1.0 - v / rail) if is_hi(k, i) else (v / rail))


def guard_ok(k, i, v, rail):
    return (v <= 0.10 * rail) if is_hi(k, i) else (v >= 0.50 * rail)


def row_extract(scheme, mode, T, dv, tz, path):
    m = parse_mt0(path + ".mt0")
    hdr, rows = read_prn(path + ".prn")
    S = schedule(scheme, T, dv, tz)
    nb, hops, nh = S["nbank"], S["hops"], len(S["hops"])
    r = dict(scheme=scheme, mode=mode, T_ps=T, dv=dv, tz_ps=tz,
             nbank=nb, hops=hops, bound_ps=S["bound"], close_ps=S["close"],
             open_ps=S["open"], tend_ps=S["tend"])

    # ---------------- rails at every bank's own boundary (MEASURED)
    rail = {k: m["VR%dK%d" % (k, k)] for k in range(1, nb + 1)}
    r["rail_at_own_boundary_V"] = rail
    r["rail_at_hop_open_V"] = {h: {k: m["VR%dB%d" % (k, h)] for k in range(1, nb + 1)}
                               for h in range(1, nh + 1)}
    r["rail_peak_V"] = {k: m["VR%dPK" % k] for k in range(1, nb + 1)}
    r["rail_end_of_tail_V"] = {k: m["VR%dD" % k] for k in range(1, nb + 1)}

    # ---------------- per-hop droop: delivered rail vs its source's rail at close
    droop = {}
    for h, (s, t) in enumerate(hops, 1):
        vs = at(hdr, rows, "V(RAIL%d)" % s, S["close"][h - 1] - EDGE)
        vd = m["VR%dB%d" % (t, h)]
        droop[h] = dict(src=s, dst=t, src_rail_at_close_V=vs,
                        dst_rail_at_open_V=vd,
                        droop_pct=100.0 * (vd / vs - 1.0) if vs else None)
    r["per_hop_droop"] = droop

    # ---------------- per-gate settling at each bank's own boundary
    st, grp, pat = {}, {}, {}
    for k in range(1, nb + 1):
        st[k], pat[k] = {}, {}
        up, dn = [], []
        for i in range(MGATE):
            v = m["O%d_%dS" % (k, i)]
            s = settle_pct(k, i, v, rail[k])
            st[k]["o%d_%d" % (k, i)] = s
            pat[k]["o%d_%d" % (k, i)] = guard_ok(k, i, v, rail[k])
            (dn if is_hi(k, i) else up).append(s)
        grp[k] = dict(pullup_min=min(up), pullup_max=max(up),
                      pulldown_min=min(dn), pulldown_max=max(dn),
                      worst=min(min(up), min(dn)),
                      limiting="pull-down" if min(dn) < min(up) else "pull-up",
                      gap_pct=abs(min(dn) - min(up)),
                      guard_all_pass=all(pat[k].values()))
    r["settling_pct_per_gate"] = st
    r["settling_groups"] = grp
    # the INPUT drive each bank actually has at its own boundary -- the mechanism
    # number.  A pull-DOWN cell's gate is its predecessor's HIGH output (referenced
    # to the PREDECESSOR's rail, which the schedule may be draining); a pull-UP
    # cell's gate is its predecessor's LOW output (ground-referenced).
    drive = {}
    for k in range(2, nb + 1):
        pd = [at(hdr, rows, "V(O%d_%d)" % (k - 1, i), S["bound"][k])
              for i in range(MGATE) if is_hi(k, i)]
        pu = [at(hdr, rows, "V(O%d_%d)" % (k - 1, i), S["bound"][k])
              for i in range(MGATE) if not is_hi(k, i)]
        drive[k] = dict(pulldown_gate_min_V=min(pd), pulldown_gate_max_V=max(pd),
                        pullup_gate_min_V=min(pu), pullup_gate_max_V=max(pu),
                        pulldown_overdrive_V=min(pd) - 0.5239,      # Vtn MEASURED
                        pullup_overdrive_V=rail[k] - max(pu) - 0.4403)   # |Vtp|
    r["input_drive_at_boundary"] = drive
    # a boundary that falls inside the bank's OWN charging hop is a structural
    # failure of the beat period, not of settling.  Flagged, never hidden.
    ins = {}
    for k in range(1, nb + 1):
        hin = [h for h, (s, t) in enumerate(hops, 1) if t == k]
        ins[k] = bool(hin and S["bound"][k] < S["open"][hin[0] - 1])
    r["boundary_inside_charging_hop_per_bank"] = ins
    r["boundary_inside_charging_hop"] = any(ins.values())
    r["pattern_guard"] = pat
    r["outputs_at_own_boundary_V"] = {
        k: {"o%d_%d" % (k, i): m["O%d_%dS" % (k, i)] for i in range(MGATE)}
        for k in range(1, nb + 1)}
    r["outputs_end_of_tail_V"] = {
        k: {"o%d_%d" % (k, i): m["O%d_%dE" % (k, i)] for i in range(MGATE)}
        for k in range(1, nb + 1)}
    r["worst_gate_pct_all_stages"] = min(grp[k]["worst"] for k in range(1, nb + 1))
    r["worst_gate_stage"] = min(range(1, nb + 1), key=lambda k: grp[k]["worst"])
    hop_charged = sorted(S["c"].keys())
    r["hop_charged_banks"] = hop_charged
    r["worst_gate_pct_hop_charged"] = min(grp[k]["worst"] for k in hop_charged)
    r["deepest_bank"] = nb
    r["deepest_worst_pct"] = grp[nb]["worst"]

    # ---------------- A1 acceptance
    r["A1_all_gates_90_all_stages"] = all(
        grp[k]["worst"] >= 90.0 for k in range(1, nb + 1))
    r["A1_all_gates_90_hop_charged"] = all(
        grp[k]["worst"] >= 90.0 for k in hop_charged)
    r["A2_pattern_guard_all"] = all(grp[k]["guard_all_pass"] for k in range(1, nb + 1))
    r["PASS"] = bool(r["A1_all_gates_90_all_stages"] and r["A2_pattern_guard_all"])

    # ---------------- A5 margin budget
    hopr = [rail[k] for k in hop_charged]
    r["margin_cumulative_mV"] = 1000.0 * (VB_REF.get(dv, VB_REF[1.2]) - min(hopr))
    r["margin_compounding_mV"] = 1000.0 * (max(hopr) - min(hopr))
    r["budget_used_pct_of_120mV"] = 100.0 * r["margin_cumulative_mV"] / BUDGET
    r["cliff_floor_PASS"] = min(hopr) >= CLIFF
    r["rails_below_cliff"] = [k for k in hop_charged if rail[k] < CLIFF]

    # ---------------- A6 instrument
    r["IZ_uA"] = {h: m["IZ%d" % h] * 1e6 for h in range(1, nh + 1)}
    r["IPK_uA"] = {h: m["IPK%d" % h] * 1e6 for h in range(1, nh + 1)}
    # path identity ean - esw - er = dE_L, which vanishes ONLY where I(L)=0, i.e.
    # at that hop's own zero.  TWO corrections over the first pass:
    #  (i) the inductor's NEAR node is a{h}, not rail{src} -- with the source-side
    #      cut the source TG sits between them, so EAN is the correct term (chain3);
    # (ii) the 1F integrators carry a t=0 PEDESTAL, so every term is t0-referenced
    #      against its own Z checkpoint.
    def d(tg, nm):
        return m["%s_%s" % (tg.upper(), nm)] - m["%s_Z" % tg.upper()]
    r["identity_at_own_zero_fJ"] = {
        h: (d("ean%d" % h, "B%d" % h) - d("esw%d" % h, "B%d" % h)
            - d("er%d" % h, "B%d" % h)) * 1e15 for h in range(1, nh + 1)}
    r["A6_IZ_PASS"] = all(abs(v) <= 1.0 for v in r["IZ_uA"].values())
    r["A6_identity_PASS"] = all(abs(v) <= 0.02
                                for v in r["identity_at_own_zero_fJ"].values())

    # ---------------- A3 HOLD TEST: every bank that is charged by a hop AND
    # drained by a later hop holds its rail from its own charge-open to its
    # drain-close.  In skip that window is ~2 beats; in adjacent ~1 beat.
    hold = {}
    for k in range(1, nb + 1):
        if k not in S["c"] or k not in S["d"]:
            continue
        hop_in = [h for h, (s, t) in enumerate(hops, 1) if t == k][0]
        ta, tb = S["open"][hop_in - 1], S["d"][k]
        v0 = at(hdr, rows, "V(RAIL%d)" % k, ta)
        v1 = at(hdr, rows, "V(RAIL%d)" % k, tb - EDGE)
        tr = trace(hdr, rows, "V(RAIL%d)" % k, ta, tb - EDGE)
        vmin = min(v for _, v in tr) if tr else None
        # HIGH outputs of this bank across the same window (the data it must hold)
        hi = [i for i in range(MGATE) if not is_hi(k, i)]   # pull-UP cells -> HIGH out
        ho = {}
        for i in hi:
            a0 = at(hdr, rows, "V(O%d_%d)" % (k, i), ta)
            a1 = at(hdr, rows, "V(O%d_%d)" % (k, i), tb - EDGE)
            ho["o%d_%d" % (k, i)] = dict(at_charge_open_V=a0, at_drain_close_V=a1,
                                         change_mV=1000.0 * (a1 - a0))
        hold[k] = dict(window_ps=[ta, tb - EDGE], window_len_ps=tb - EDGE - ta,
                       beats_held=(tb - EDGE - ta) / T,
                       rail_at_charge_open_V=v0, rail_at_drain_close_V=v1,
                       rail_min_in_window_V=vmin,
                       droop_mV=1000.0 * (v1 - v0),
                       droop_pct=100.0 * (v1 / v0 - 1.0) if v0 else None,
                       high_outputs=ho,
                       above_cliff=(vmin is not None and vmin >= CLIFF))
    r["hold_test"] = hold

    # ---------------- the DRAIN-vs-HOLD conflict, measured in BOTH schemes.
    # For each hop h (src s, dst t): the bank whose OUTPUTS are t's data is t-1.
    # adj : t-1 == s  -> the draining bank IS the data source (zero grace).
    # skip: t-1 == s+1 -> the data source is a DIFFERENT, held bank (one gate of
    #       grace).  Report both the draining bank's HIGH outputs and the data
    #       source bank's HIGH outputs over the SAME window, plus t's settling.
    conf = {}
    for h, (s, t) in enumerate(hops, 1):
        src_of_data = t - 1
        ta, tb = S["close"][h - 1], S["bound"][t]
        def hi_outs(bank):
            """the outputs of `bank` that feed bank t's pull-DOWN cells, i.e. the
            nets that must stay HIGH for t to evaluate."""
            if bank < 1:
                return {}
            out = {}
            for i in range(MGATE):
                if not is_hi(t, i):
                    continue
                net = "V(O%d_%d)" % (bank, i) if bank >= 1 else None
                if net is None or net.replace("V(", "").replace(")", "") \
                        not in [c.replace("V(", "").replace(")", "") for c in hdr]:
                    continue
                v0 = at(hdr, rows, net, ta)
                v1 = at(hdr, rows, net, tb)
                tr = trace(hdr, rows, net, ta, tb)
                out["o%d_%d" % (bank, i)] = dict(
                    at_beat_close_V=v0, at_boundary_V=v1,
                    min_in_window_V=min(v for _, v in tr) if tr else None,
                    collapse_pct=100.0 * (v1 / v0 - 1.0) if v0 else None)
            return out
        def lo_outs(bank):
            """the outputs of `bank` that feed bank t's pull-UP cells, i.e. the
            nets that must stay LOW (ground-referenced) for t to evaluate.  These
            turned out to be the binding term: a LOW that CREEPS UP steals the
            successor's pMOS overdrive, rail - V(gate) - |Vtp|."""
            if bank < 1:
                return {}
            out = {}
            for i in range(MGATE):
                if is_hi(t, i):
                    continue
                net = "V(O%d_%d)" % (bank, i)
                v0 = at(hdr, rows, net, ta)
                v1 = at(hdr, rows, net, tb)
                tr = trace(hdr, rows, net, ta, tb)
                out["o%d_%d" % (bank, i)] = dict(
                    at_beat_close_V=v0, at_boundary_V=v1,
                    max_in_window_V=max(v for _, v in tr) if tr else None,
                    creep_mV=1000.0 * (v1 - v0))
            return out
        conf[h] = dict(
            src=s, dst=t, data_source_bank=src_of_data,
            data_source_low_outputs=lo_outs(src_of_data),
            draining_bank_low_outputs=lo_outs(s),
            data_source_is_the_draining_bank=(src_of_data == s),
            window_ps=[ta, tb],
            draining_bank_high_outputs=hi_outs(s),
            data_source_high_outputs=hi_outs(src_of_data),
            data_source_rail=dict(
                at_beat_close_V=at(hdr, rows, "V(RAIL%d)" % src_of_data, ta),
                at_boundary_V=at(hdr, rows, "V(RAIL%d)" % src_of_data, tb))
            if src_of_data >= 1 else None,
            dst_pulldown_min_pct=grp[t]["pulldown_min"],
            dst_pullup_min_pct=grp[t]["pullup_min"],
            dst_limiting=grp[t]["limiting"])
    r["drain_vs_hold"] = conf

    # ---------------- A7 energy (reported, gates nothing)
    en = {}
    for h in range(1, nh + 1):
        z = lambda tg, nm: m["%s_%s" % (tg.upper(), nm)] * 1e15
        b = "B%d" % h
        en[h] = dict(
            E_out_of_source_fJ=z("ea%d" % h, b) - z("ea%d" % h, "Z"),
            E_into_dest_fJ=-(z("eb%d" % h, b) - z("eb%d" % h, "Z")),
            E_series_R_fJ=z("er%d" % h, b) - z("er%d" % h, "Z"),
            E_switch_block_fJ=(z("ea%d" % h, b) - z("ea%d" % h, "Z"))
                              - (z("ean%d" % h, b) - z("ean%d" % h, "Z")),
            Q_through_L_fC=z("qlt%d" % h, b) - z("qlt%d" % h, "Z"))
    r["energy_per_hop_fJ"] = en
    r["Q_from_ideal_dV_supply_fC"] = (m["QDV_D"] - m["QDV_Z"]) * 1e15
    r["E_from_ideal_dV_supply_fJ"] = dv * (m["QDV_D"] - m["QDV_Z"]) * 1e15
    r["E_transfer_gate_drive_fJ"] = (m["EGT_D"] - m["EGT_Z"]) * 1e15
    return r


if __name__ == "__main__":
    scheme, mode, T, dv = sys.argv[1], sys.argv[2], float(sys.argv[3]), float(sys.argv[4])
    tz = json.loads(sys.argv[5])
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "c_%s_%s_T%g_dv%g.cir" % (scheme, mode, T, dv * 1000))
    print(json.dumps(row_extract(scheme, mode, T, dv, tz, path), indent=1))
