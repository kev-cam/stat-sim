#!/usr/bin/env python3
"""Skeptic driver: zeros -> rows -> extraction.  Own decks, own cache."""
import json, os, sys, time
from concurrent.futures import ThreadPoolExecutor
import sk

HERE = sk.HERE
VTN, VTP, SIG, CLIFF = 0.5239, 0.4403, 6.44, 0.600


# --------------------------------------------------------------- zero probing
def zeros_for(cfg, tag, span=None):
    """Re-probe the TRUE current zero of every hop, sequentially, for THIS
    configuration.  Never the analytic pi*sqrt(LC)."""
    tz, log = [], []
    for h in range(1, len(sk.HOPS) + 1):
        c = dict(cfg)
        if span:
            c["probe_span"] = span
        L, S = sk.deck(c, tz=tz + [sk.TZ_ANCHOR * sk.CHAIN_F] * (len(sk.HOPS) - len(tz)),
                       probe=h)
        p, msg = sk.run("z%s_h%d.cir" % (tag, h), L, timeout=1200)
        if p is None:
            return None, log + [msg]
        hdr, rows = sk.read_prn(p + ".prn")
        z, pk = sk.zero_after_peak(hdr, rows, "I(L%d)" % h, S["close"][h - 1])
        if z is None:
            return None, log + ["%s hop %d: NO CURRENT ZERO (peak %s A) -- %s"
                                % (tag, h, pk, msg)]
        tz.append(z - S["close"][h - 1])
        log.append("%s hop %d t_zcs %.4f ps (peak %.4g A)  %s" % (tag, h, tz[-1], pk, msg))
    return tz, log


# ------------------------------------------------------------------ extraction
def stage(m, S, k):
    prof = S["prof"]
    M = prof[k - 1]
    vr = m.get("VR%dK%d" % (k, k))
    cells, ups, dns = [], [], []
    for i in range(M):
        vo = m.get("O%d_%dS" % (k, i))
        vg = m.get("G%d_%d" % (k, i))
        if vo is None:
            continue
        # the LABEL used by the committed extractor -- the (i+k) parity rule
        pd_rule = sk.is_hi(k, i)
        # the label the NETLIST actually implies, traced through the fan-out
        pd_true = sk.true_input_hi(k, i, prof)
        st = (1.0 - vo / vr) if pd_true else (vo / vr)
        drive = (vg - VTN) if pd_true else ((vr - vg) - VTP)
        cells.append(dict(i=i, kind_rule="pulldown" if pd_rule else "pullup",
                          kind_netlist="pulldown" if pd_true else "pullup",
                          label_conflict=(pd_rule != pd_true),
                          in_net=sk.in_net(k, i, prof), v_o=vo, v_gate=vg,
                          settle_pct=100.0 * st, drive_over_vt_V=drive,
                          guard_ok=drive > 0.0,
                          value_ok=(vo < 0.5 * vr) if pd_true else (vo > 0.5 * vr),
                          value_ok_rulelabel=(vo < 0.5 * vr) if pd_rule else (vo > 0.5 * vr)))
        (dns if pd_true else ups).append(vo)
    sts = [c["settle_pct"] for c in cells]
    # separation is only DEFINED when the stage carries at least one of each
    # class AND those cells are not electrically identical
    distinct = len({round(c["v_o"], 9) for c in cells}) > 1
    sep = (min(ups) - max(dns)) * 1e3 if (ups and dns) else None
    return dict(bank=k, M=M, rail_at_bound_V=vr, bound_ps=S["bound"][k],
                worst_settle_pct=min(sts) if sts else None,
                max_LOW_V=max(dns) if dns else None,
                min_HIGH_V=min(ups) if ups else None,
                separation_mV=sep, separation_defined=bool(ups and dns and distinct),
                n_distinct_outputs=len({round(c["v_o"], 9) for c in cells}),
                n_guard_fail=sum(1 for c in cells if not c["guard_ok"]),
                n_value_fail=sum(1 for c in cells if c["value_ok"] is False),
                n_value_fail_rulelabel=sum(1 for c in cells
                                           if c["value_ok_rulelabel"] is False),
                n_label_conflict=sum(1 for c in cells if c["label_conflict"]),
                cells=cells)


def row(cfg, m, S, path):
    nb = S["nbank"]
    r = dict(cfg={k: v for k, v in cfg.items() if k != "ctk"},
             ctk_fF={str(k): round(v, 4) for k, v in cfg["ctk"].items() if v},
             T_ps=S["T"], tz_ps=[round(z, 4) for z in S["tz"]],
             hop_spread=(max(S["tz"]) / min(S["tz"])) if S["tz"] else None,
             bound_ps={str(k): S["bound"][k] for k in S["bound"]},
             deck=os.path.basename(path))
    r["stages"] = [stage(m, S, k) for k in range(1, nb + 1)]
    r["rail_by_stage_V"] = [s["rail_at_bound_V"] for s in r["stages"]]
    r["worst_gate_by_stage_pct"] = [s["worst_settle_pct"] for s in r["stages"]]
    r["guard_fail_by_stage"] = [s["n_guard_fail"] for s in r["stages"]]
    r["value_fail_by_stage"] = [s["n_value_fail"] for s in r["stages"]]
    r["value_fail_rulelabel_by_stage"] = [s["n_value_fail_rulelabel"] for s in r["stages"]]
    r["sep_defined_by_stage"] = [s["separation_defined"] for s in r["stages"]]
    r["separation_by_depth_mV"] = [s["separation_mV"] for s in r["stages"]]
    rails = r["rail_by_stage_V"]
    r["collapse_ratio_by_hop"] = [rails[i + 1] / rails[i] for i in range(len(rails) - 1)]
    r["collapse_spread"] = (max(r["collapse_ratio_by_hop"]) /
                            min(r["collapse_ratio_by_hop"]))
    r["cliff_pass"] = all(v >= CLIFF for v in rails[1:])
    r["tank_by_stage_V"] = [m.get("VT%dK%d" % (k, k)) for k in range(1, nb + 1)]
    r["IZ_uA"] = [m.get("IZ%d" % h, 0.0) * 1e6 for h in range(1, len(sk.HOPS) + 1)]
    r["IZ_gate_pass"] = all(abs(x) < 1.0 for x in r["IZ_uA"])

    def dq(tag, ck):
        a, b = m.get("%s_Z" % tag.upper()), m.get("%s_%s" % (tag.upper(), ck))
        return None if (a is None or b is None) else (b - a)
    led = {}
    for h in range(1, len(sk.HOPS) + 1):
        led["hop%d_ER_fJ" % h] = (dq("er%d" % h, "B%d" % h) or 0) * 1e15
    led["Q_dv_source_fC"] = (dq("qdv", "D") or 0) * 1e15
    led["E_hop_gate_drive_fJ"] = (dq("egt", "D") or 0) * 1e15
    led["E_head_gate_drive_fJ"] = (dq("ehd", "D") or 0) * 1e15
    for k in sk.TOPPED:
        led["E_topup%d_gate_drive_fJ" % k] = (dq("egtu%d" % k, "D") or 0) * 1e15
    r["ledger"] = led
    return r


def run_row(args):
    cfg, tz, name = args
    L, S = sk.deck(cfg, tz=tz)
    p, msg = sk.run(name, L, timeout=1500)
    if p is None:
        return dict(cfg={k: v for k, v in cfg.items() if k != "ctk"}, error=msg)
    m = sk.parse_mt0(p + ".mt0")
    r = row(cfg, m, S, p)
    r["msg"] = msg
    return r


if __name__ == "__main__":
    print("use the stage scripts", file=sys.stderr)
