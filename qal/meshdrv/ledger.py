#!/usr/bin/env python3
"""qal/meshdrv ledger -- applies the PRE_REGISTERED booking rules to run
OUT.jsons and emits the priced comparison.  Rules (fixed before any deck):
 R1 metered DC rails at 1.0x (net draw; same convention as the committed
    mesh3 ideal-rail ledger -- rail-generation multiplier is a rider on BOTH
    sides).
 R2 free-running resonant sources: E_net_delivered / eta_amp (MEASURED
    25.46%, qal/amp headline, Q_ind=19).  AMENDMENT A2: negative net
    credited ZERO (both readings reported).
 R3 gate drive: metered up-edge charge x VGH(1.65) x 1.33 chain tax;
    cross-check vs the corrected committed fit 3.635 fC/um.
 R4 control pulse generation: 15.5 fJ (MEASURED park-driver band) per
    generator per cycle / N_banks.
E_overhead = E_driver_total - E_ledger(bank4) = total - 240.292 fJ.
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
E_LEDGER = 240.292
ETA = 0.2546
VGH = 1.65
TAX = 1.33
EPG = 15.5


def load(tag):
    return json.load(open(os.path.join(HERE, "runs", tag, "OUT.json")))


def common(o, bank=4):
    ch = o["charge_spec_reported_not_gated"][str(bank)] \
        if isinstance(o["charge_spec_reported_not_gated"], dict) and \
        str(bank) in o["charge_spec_reported_not_gated"] \
        else o["charge_spec_reported_not_gated"][bank]
    er = o["erosion"]["3"] if "3" in o.get("erosion", {}) else o["erosion"][3]
    acc = o["acceptance"]
    drv = o.get("driver", {})
    dn = drv.get("drv_node", {})
    key = sorted(dn)[0] if dn else None
    return dict(
        bank_books=ch,
        Q_hold_vs_committed_pct=round(100*(ch["Q_hold_fC"]/124.903 - 1), 2),
        value_PASS=o["value"]["PASS"],
        acceptance_PASS=acc["PASS"],
        worst_margin_mV=acc["worst_margin_at_commit_mV"],
        erosion_sign=er["sign"],
        widths_w3=er["width_0mV_ps_links"],
        asymptotic_eye_ps=er["asymptotic_width_ps"],
        droop_mV=(dn[key]["droop_mV"] if key else None),
        ripple_over_mV=(dn[key]["ripple_over_mV"] if key else None),
        trough_min_V=(dn[key]["trough_min_V"] if key else None),
        hold_rail_bank4=o["hold_rail"].get("4", o["hold_rail"].get(4)),
    )


def price_A(tag):
    o = load(tag)
    c = common(o)
    cyc = o["driver"]["cycles"]
    rows, tot_pos, tot_neg, supply = {}, 0.0, 0.0, 0.0
    for tg, v in cyc.items():
        if not tg.startswith("ea"):
            continue
        e = v["mean_f"]
        rows[tg] = round(e, 3)
        if tg.endswith("h0"):
            supply += e                     # DC rail: R1
        elif e > 0:
            tot_pos += e
            supply += e / ETA               # R2
        else:
            tot_neg += e                    # A2: credited zero
    e_del = sum(v for v in rows.values())
    tot = supply
    return dict(tag=tag, kind="A", common=c, per_source_net_fJ=rows,
                E_delivered_net_fJ=round(e_del, 3),
                E_absorbed_credited_zero_fJ=round(tot_neg, 3),
                E_driver_total_fJ=round(tot, 2),
                E_overhead_fJ=round(tot - E_LEDGER, 2),
                overhead_frac_of_ledger=round((tot - E_LEDGER)/E_LEDGER, 3),
                sharing="eta is B-invariant (qal/amp B_scaling, I10): "
                        "per-bank cost does not amortise with N",
                recursion_audit="no switches, no controls; sustainer "
                                "topology has no gate-driver recursion "
                                "(qal/amp design rationale); its cost IS "
                                "the 1/eta factor")


def gate_term(o, keys):
    ge = o["driver"]["gate_edge_fC"]
    tot, det = 0.0, {}
    for k, q in ge.items():
        if any(k.startswith(p) for p in keys):
            det[k] = q
            tot += abs(q)
    return tot, det


def price_B(tag, N=1):
    o = load(tag)
    c = common(o)
    cyc = o["driver"]["cycles"]
    e_sb = cyc["esb4"]["mean_f"]
    q_sb = cyc["qsb4"]["mean_f"]
    e_vh = cyc["evh4"]["mean_f"]
    q_vh = cyc["qvh4"]["mean_f"]
    # clamp gate: up edges only (NCLUP for nccl, PCLUP... pccl up at open)
    ge = o["driver"]["gate_edge_fC"]
    qg = abs(ge.get("QGNCL4_CLNUP", 0)) + abs(ge.get("QGPCL4_CLPUP", 0))
    e_gate = qg * VGH * TAX
    e_sine_book = (e_sb / ETA) if e_sb > 0 else 0.0
    tot = e_vh + e_sine_book + e_gate + EPG / N
    tot_etaneg = e_vh + e_sb / ETA + e_gate + EPG / N   # the other A2 reading
    return dict(tag=tag, kind="B", common=c,
                E_sine_net_fJ=round(e_sb, 3), Q_sine_net_fC=round(q_sb, 3),
                E_vhold_net_fJ=round(e_vh, 3), Q_vhold_net_fC=round(q_vh, 3),
                clamp_gate_up_fC=round(qg, 3), E_gate_fJ=round(e_gate, 3),
                E_pulsegen_fJ=round(EPG / N, 3),
                E_driver_total_fJ=round(tot, 2),
                E_driver_total_if_negative_net_credited_at_eta=round(
                    tot_etaneg, 2),
                E_overhead_fJ=round(tot - E_LEDGER, 2),
                overhead_frac_of_ledger=round((tot - E_LEDGER)/E_LEDGER, 3))


def price_C(tag, N=1, sf="4"):
    o = load(tag)
    c = common(o)
    cyc = o["driver"]["cycles"]
    e_vm = cyc["evm%s" % sf]["mean_f"]
    q_vm = cyc["qvm%s" % sf]["mean_f"]
    e_vh = cyc["evh%s" % sf]["mean_f"]
    q_vh = cyc["qvh%s" % sf]["mean_f"]
    ge = o["driver"]["gate_edge_fC"]
    up = {k: v for k, v in ge.items()
          if k.endswith(("SSNUP", "SSPUP", "CLNUP", "CLPUP"))
          and k.split("_")[1] == k.split("_")[1]}
    qg = (abs(ge.get("QGNSS%s_SSNUP" % sf, 0)) +
          abs(ge.get("QGPSS%s_SSPUP" % sf, 0)) +
          abs(ge.get("QGNCL%s_CLNUP" % sf, 0)) +
          abs(ge.get("QGPCL%s_CLPUP" % sf, 0)))
    e_gate = qg * VGH * TAX
    # rails and gates are per-driver totals; a driver serving N banks
    # amortises them /N; the two pulse generators amortise /N too.
    per_bank = (e_vm + e_vh + e_gate) / N + 2 * EPG / N
    return dict(tag=tag, kind="C", common=c,
                E_vmid_net_fJ=round(e_vm, 3), Q_vmid_net_fC=round(q_vm, 3),
                E_vhold_net_fJ=round(e_vh, 3), Q_vhold_net_fC=round(q_vh, 3),
                gate_up_fC=round(qg, 3), gate_detail=up,
                E_gate_fJ=round(e_gate, 3),
                E_pulsegen_fJ=round(2 * EPG / N, 3),
                zcs_zero_after_slot_ps=o["driver"].get(
                    "zcs_zero_after_slot_ps"),
                IL_pk_uA=o["driver"].get("IL_pk_uA_w3"),
                E_driver_per_bank_fJ=round(per_bank, 2),
                E_overhead_fJ=round(per_bank - E_LEDGER, 2),
                overhead_frac_of_ledger=round(
                    (per_bank - E_LEDGER)/E_LEDGER, 3))


if __name__ == "__main__":
    kind = sys.argv[1]
    tag = sys.argv[2]
    N = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    fn = {"a": price_A, "b": price_B, "c": price_C}[kind]
    r = fn(tag) if kind == "a" else fn(tag, N)
    print(json.dumps(r, indent=1))
