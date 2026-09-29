#!/usr/bin/env python3
"""Row extraction for qal/tankfed.  Every convention inherited verbatim:

  settling   = V(o)/V(rail_k) for a pull-UP cell, 1 - V(o)/V(rail_k) for a
               pull-DOWN cell, read at bound_k.  PER GATE, never aggregated.
  value      = the expected inversion pattern; a gate that settles to the wrong
               side is a FAIL regardless of how fast it got there.
  guard      = the cell only counts as COMPUTING if its own delivered gate drive
               is on the conducting side of the MEASURED device threshold
               (Vtn 0.5239 V for the nMOS, |Vtp| 0.4403 V for the pMOS).
  separation = min(pull-UP outputs) - max(pull-DOWN outputs) within one stage.
"""
import json, os
import tf

VTN  = 0.5239        # MEASURED cell threshold (qal/chain3/vt.json)
VTP  = 0.4403        # MEASURED |Vtp|
SIG  = 6.44          # mV, CORRECTED 1-sigma floor (qal/vtaudit/AUDIT.md)
CLIFF = 0.600        # V, absolute cliff


def stage(m, S, k):
    """Everything about bank k at its own boundary."""
    prof = S["prof"]
    M = prof[k - 1]
    vr = m.get("VR%dK%d" % (k, k))
    cells, ups, dns = [], [], []
    for i in range(M):
        vo = m.get("O%d_%dS" % (k, i))
        vg = m.get("G%d_%d" % (k, i))
        if vo is None:
            continue
        pulldown = tf.is_hi(k, i)
        st = None
        if vr:
            st = (1.0 - vo / vr) if pulldown else (vo / vr)
        # the PATTERN GUARD: is the driving device actually on?
        if pulldown:
            drive = (vg - VTN) if vg is not None else None      # nMOS overdrive
        else:
            drive = ((vr - vg) - VTP) if (vg is not None and vr is not None) else None
        cells.append(dict(i=i, kind="pulldown" if pulldown else "pullup",
                          v_o=vo, v_gate=vg,
                          settle_pct=(None if st is None else 100.0 * st),
                          drive_over_vt_V=drive,
                          guard_ok=(drive is not None and drive > 0.0),
                          value_ok=(vo < 0.5 * vr if pulldown else vo > 0.5 * vr)
                          if vr else None))
        (dns if pulldown else ups).append(vo)
    sts = [c["settle_pct"] for c in cells if c["settle_pct"] is not None]
    sep = (min(ups) - max(dns)) * 1e3 if (ups and dns) else None
    return dict(bank=k, M=M, rail_at_bound_V=vr, bound_ps=S["bound"][k],
                n_cells=len(cells),
                worst_settle_pct=(min(sts) if sts else None),
                best_settle_pct=(max(sts) if sts else None),
                intra_class_spread_pp=(max(sts) - min(sts)) if sts else None,
                max_LOW_V=(max(dns) if dns else None),
                min_HIGH_V=(min(ups) if ups else None),
                separation_mV=sep,
                separation_over_sigma=(None if sep is None else sep / SIG),
                n_guard_fail=sum(1 for c in cells if not c["guard_ok"]),
                n_value_fail=sum(1 for c in cells if c["value_ok"] is False),
                cells=cells)


def row(cfg, m, S, path=None):
    nb = S["nbank"]
    r = dict(cfg={k: v for k, v in cfg.items() if k != "ctk"},
             ctk_fF={str(k): round(v, 4) for k, v in cfg["ctk"].items()},
             T_ps=S["T"], bound_ps={str(k): S["bound"][k] for k in S["bound"]},
             tz_ps=[round(z, 4) for z in S["tz"]],
             hop_spread=(max(S["tz"]) / min(S["tz"])) if S["tz"] else None)
    r["stages"] = [stage(m, S, k) for k in range(1, nb + 1)]
    r["worst_gate_by_stage_pct"] = [s["worst_settle_pct"] for s in r["stages"]]
    r["rail_by_stage_V"] = [s["rail_at_bound_V"] for s in r["stages"]]
    r["separation_by_depth_mV"] = [s["separation_mV"] for s in r["stages"]]
    r["max_LOW_by_stage_V"] = [s["max_LOW_V"] for s in r["stages"]]
    r["guard_fail_by_stage"] = [s["n_guard_fail"] for s in r["stages"]]
    r["value_fail_by_stage"] = [s["n_value_fail"] for s in r["stages"]]
    rails = r["rail_by_stage_V"]
    r["collapse_ratio_by_hop"] = [
        (rails[i + 1] / rails[i] if (rails[i] and rails[i + 1]) else None)
        for i in range(len(rails) - 1)]
    r["cliff_pass"] = all((v is not None and v >= CLIFF) for v in rails[1:])
    # tank nodes
    r["tank_by_stage_V"] = [m.get("VT%dK%d" % (k, k)) for k in range(1, nb + 1)]
    # ZCS hygiene
    r["IZ_uA"] = [None if m.get("IZ%d" % h) is None else m["IZ%d" % h] * 1e6
                  for h in range(1, len(S["hops"]) + 1)]
    r["IPK_uA"] = [m["IPK%d" % h] * 1e6 for h in range(1, len(S["hops"]) + 1)
                   if ("IPK%d" % h) in m]
    r["IZ_gate_pass"] = all(abs(x) < 1.0 for x in r["IZ_uA"] if x is not None)
    # charge / energy ledger, t0-referenced (every integrator differenced from Z)
    def dq(tag, ck):
        a, b = m.get("%s_Z" % tag.upper()), m.get("%s_%s" % (tag.upper(), ck))
        return None if (a is None or b is None) else (b - a)
    r["ledger"] = {}
    for h in range(1, len(S["hops"]) + 1):
        ck = "B%d" % h
        r["ledger"]["hop%d" % h] = dict(
            q_fC=(dq("qlt%d" % h, ck) or 0) * 1e15,
            E_src_fJ=(dq("ea%d" % h, ck) or 0) * 1e15,
            E_dst_fJ=(dq("eb%d" % h, ck) or 0) * 1e15,
            E_R_fJ=(dq("er%d" % h, ck) or 0) * 1e15)
    ckD = "D"
    r["ledger"]["E_hop_gate_drive_fJ"] = (dq("egt", ckD) or 0) * 1e15
    r["ledger"]["Q_dv_source_fC"] = (dq("qdv", ckD) or 0) * 1e15
    for k in tf.TOPPED:
        if k > nb:
            continue
        r["ledger"]["topup%d" % k] = dict(
            q_delivered_fC=(dq("qtu%d" % k, ckD) or 0) * 1e15
            if ("QTU%d_D" % k) in m else None,
            E_delivered_fJ=(dq("etu%d" % k, ckD) or 0) * 1e15
            if ("ETU%d_D" % k) in m else None,
            E_gate_drive_fJ=(dq("egtu%d" % k, ckD) or 0) * 1e15
            if ("EGTU%d_D" % k) in m else None)
    if ("QSUP_D" in m):
        r["ledger"]["Q_supply_fC"] = (dq("qsup", ckD) or 0) * 1e15
        r["ledger"]["E_supply_fJ"] = (dq("esup", ckD) or 0) * 1e15
        qd = sum((r["ledger"]["topup%d" % k]["q_delivered_fC"] or 0.0)
                 for k in tf.TOPPED if k <= nb)
        qs = r["ledger"]["Q_supply_fC"]
        r["ledger"]["Qdel_over_Qsup"] = (qd / qs) if qs else None
    if path:
        r["deck"] = os.path.basename(path)
    return r
