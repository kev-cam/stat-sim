#!/usr/bin/env python3
"""SKEPTIC policing pass: everything is recomputed from MY OWN decks' raw .prn
with sk_extract.py.  Nothing here reads a committed summary."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, "/usr/local/src/stat-sim/qal/skip4")
import skip as SK
import sk_extract as EX

SK.SCHED["s4"] = dict(nbank=4, hops=[(1, 3), (2, 4)], heads=[1, 2])
SK.SCHED["s5"] = dict(nbank=5, hops=[(1, 3), (2, 4), (3, 5)], heads=[1, 2])
SLEW, PREP = 24.0, 24.0 + 4 * SK.EDGE
VTP = 0.4402734          # MEASURED |Vtp| for this PDK (committed)
SIGMA_VT_MV = 3.42       # PDK sigma-Vt floor (stat-sim e4c980b, qal/restore5)


def rise_in(p, node, ta, tb):
    w = p.window(node, ta, tb)
    if not w:
        return None
    vs = [v for _, v in w]
    return 1e3 * (max(vs) - vs[0])


def analyse(rec):
    tag, nb = rec["tag"], rec["nbank"]
    S = SK.schedule(rec["scheme"], rec["T_ps"], rec["dv"], rec["tz_ps"])
    p = EX.PRN(os.path.join(HERE, rec["prn"]))
    o = dict(tag=tag, mode=rec["mode"], T_ps=rec["T_ps"], dv=rec["dv"],
             t_on_ps=rec["t_on_ps"], ltu_nH=rec["ltu_nH"], Cna_fF=rec["Cna_fF"],
             tz_ps=rec["tz_ps"], A6_worst_IZ_uA=rec.get("A6_worst_IZ_uA"),
             A6_pass=rec.get("A6_pass"))

    st = EX.settling(p, S, nb)
    o["settling_worst_pct_by_stage"] = {k: (None if st[k]["worst_pct"] is None
                                            else round(st[k]["worst_pct"], 2))
                                        for k in st}
    o["settling_per_gate"] = {k: {i: round(v["settle_pct"], 3)
                                  for i, v in st[k]["per_gate"].items()
                                  if v["settle_pct"] is not None} for k in st}
    o["rail_at_own_boundary_V"] = {k: round(st[k]["rail_at_bound_V"], 6) for k in st}
    got = [st[k]["worst_pct"] for k in st if st[k]["worst_pct"] is not None]
    o["A1_worst_gate_all_stages_pct"] = round(min(got), 2) if got else None
    o["A1_pass_all_90"] = bool(got and min(got) >= 90.0)

    dl = EX.delivered(p, S, nb)
    o["delivered_min_HIGH_V_by_stage"] = {k: round(dl[k]["min_delivered_HIGH_V"], 6)
                                          for k in dl}
    o["A2_min_delivered_HIGH_V"] = round(min(v["min_delivered_HIGH_V"]
                                             for v in dl.values()), 6)
    o["A2_pass_all_stages"] = bool(all(v["A2_pass"] for v in dl.values()))

    sep = EX.separation(p, S, nb)
    o["separation_mV_by_bank"] = {k: round(sep[k]["separation_mV"], 4) for k in sep}
    o["separation_below_floor_by_bank"] = {k: sep[k]["below_sigma_vt_3p42"]
                                           for k in sep}
    o["separation_inverted_by_bank"] = {k: sep[k]["inverted"] for k in sep}
    o["separation_floor_mV"] = SIGMA_VT_MV

    # ---- the coupling measurement, on bank 3's hold window
    ta = S["open"][0] + SK.EDGE
    tb = min(S["bound"][3], S["close"][1]) - SK.EDGE
    o["coupling_window_ps"] = [round(ta, 3), round(tb, 3)]
    sl = EX.max_slope(p, "V(RAIL3)", ta, tb)
    o["S1_rail3_max_rising_V_per_ns"] = round(sl["max_rising_V_per_ns"], 3)
    o["S1_at_ps"] = round(sl["at_ps"], 3)
    o["S1_rail3_rise_in_window_mV"] = round(rise_in(p, "V(RAIL3)", ta, tb), 4)

    low = EX.predecessor_low(p, S, 2)
    o["S2_victim_max_pulldown_at_bound2_V"] = round(low["max_pulldown_V"], 6)
    o["S2_victim_lift_in_window_mV"] = round(
        max(rise_in(p, "V(O2_%d)" % i, ta, tb) for i in range(8) if SK.is_hi(2, i)), 4)
    o["S4_predecessor_rail2_at_bound2_V"] = round(p.at("V(RAIL2)", S["bound"][2]), 6)
    o["S5_rail3_at_bound3_V"] = round(p.at("V(RAIL3)", S["bound"][3]), 6)
    o["S5_pmos_overdrive_over_Vtp_V"] = round(o["S5_rail3_at_bound3_V"] - VTP, 6)

    # ---- pulse phase decomposition (pulsed rows only)
    if rec["mode"].startswith("ptu") and rec.get("tfw_ps"):
        tf = S["open"][0] + 6 * SK.EDGE
        a = tf + PREP
        b = a + rec["t_on_ps"]
        z = b + float(rec["tfw_ps"]["3"])
        ph = {}
        for nm, (x, y) in (("at_OUT_close", (a - 4, a + 4)),
                           ("during_pulse_HS_on", (a + 1, b)),
                           ("during_freewheel", (b, max(b + 0.5, z - 1))),
                           ("at_OUT_open", (z - 4, z + 4))):
            s = EX.max_slope(p, "V(RAIL3)", x, y)
            if s:
                ph[nm] = dict(max_rising_V_per_ns=round(s["max_rising_V_per_ns"], 3),
                              at_ps=round(s["at_ps"], 3))
        o["pulse_phases_ps"] = dict(t_fire=round(tf, 3), OUT_closes=round(a, 3),
                                    pulse=[round(a, 3), round(b, 3)],
                                    OUT_opens=round(z, 3),
                                    prep_ps=PREP,
                                    bound3_ps=S["bound"][3],
                                    pulse_end_minus_bound3_ps=round(b - S["bound"][3], 3))
        o["S1_by_pulse_phase"] = ph
        o["I_LTU3_uA"] = {"at_OUT_close": round(p.at("I(LTU3)", a) * 1e6, 3),
                          "at_pulse_end": round(p.at("I(LTU3)", b) * 1e6, 3),
                          "at_OUT_open": round(p.at("I(LTU3)", z) * 1e6, 3)}
    elif rec["mode"] == "rtu":
        t0 = S["open"][0] + SK.EDGE
        t1 = t0 + rec["t_on_ps"]
        ph = {}
        for nm, (x, y) in (("during_conduction", (t0, t1)),
                           ("at_switch_open", (t1 - 4, t1 + 4))):
            s = EX.max_slope(p, "V(RAIL3)", x, y)
            if s:
                ph[nm] = dict(max_rising_V_per_ns=round(s["max_rising_V_per_ns"], 3),
                              at_ps=round(s["at_ps"], 3))
        o["S1_by_pulse_phase"] = ph
        o["clamp_window_ps"] = [round(t0, 3), round(t1, 3)]
    return o


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "SK_ROWS_triple.json"
    rows = json.load(open(os.path.join(HERE, src)))
    out = []
    for r in rows:
        if r.get("error") or not r.get("prn"):
            out.append(dict(tag=r["tag"], error=r.get("error", "no prn")))
            continue
        try:
            out.append(analyse(r))
        except Exception as e:
            out.append(dict(tag=r["tag"], error="%s: %s" % (type(e).__name__, e)))
    json.dump(out, open(os.path.join(HERE, "SK_POLICE.json"), "w"), indent=1)

    print("=== A1 per-stage worst-gate settling (MY extractor, MY decks, raw .prn) ===")
    for o in out:
        if "error" in o:
            print("  %-34s ERROR %s" % (o["tag"], o["error"])); continue
        s = o["settling_worst_pct_by_stage"]
        print("  %-34s %s   worst %s  A1=%s" % (
            o["tag"], " / ".join("%6.2f" % s[k] if s[k] is not None else "  n/a "
                                 for k in sorted(s)),
            o["A1_worst_gate_all_stages_pct"], o["A1_pass_all_90"]))
    print("\n=== A2 delivered HIGH (>= 0.4400 V at EVERY stage) ===")
    for o in out:
        if "error" in o:
            continue
        print("  %-34s min %.6f V  A2=%s   by stage %s" % (
            o["tag"], o["A2_min_delivered_HIGH_V"], o["A2_pass_all_stages"],
            {k: round(v, 4) for k, v in o["delivered_min_HIGH_V_by_stage"].items()}))
    print("\n=== A6 ZCS hygiene (|IZ| < 1.0 uA) ===")
    for o in out:
        if "error" in o:
            continue
        print("  %-34s worst |IZ| = %s uA   A6=%s"
              % (o["tag"], o["A6_worst_IZ_uA"], o["A6_pass"]))
    print("\n=== S1 rail3 max rising dV/dt, and S2 victim damage ===")
    for o in out:
        if "error" in o:
            continue
        print("  %-34s slope %8.3f V/ns at %8.3f ps | rail3_rise %8.3f mV | "
              "victim_lift %7.3f mV | rail3@bound %.6f | overdrive %+.4f"
              % (o["tag"], o["S1_rail3_max_rising_V_per_ns"], o["S1_at_ps"],
                 o["S1_rail3_rise_in_window_mV"], o["S2_victim_lift_in_window_mV"],
                 o["S5_rail3_at_bound3_V"], o["S5_pmos_overdrive_over_Vtp_V"]))
    print("\n=== S6 separation by bank depth (mV), floor %.2f mV ===" % SIGMA_VT_MV)
    for o in out:
        if "error" in o:
            continue
        s = o["separation_mV_by_bank"]
        print("  %-34s %s" % (o["tag"], "  ".join(
            "b%s %9.3f%s" % (k, s[k], "!" if o["separation_below_floor_by_bank"][k]
                             else ("I" if o["separation_inverted_by_bank"][k] else " "))
            for k in sorted(s))))
    print("\n=== pulse-phase decomposition ===")
    for o in out:
        if "error" in o or "S1_by_pulse_phase" not in o:
            continue
        print("  %s" % o["tag"])
        for nm, v in o["S1_by_pulse_phase"].items():
            print("      %-22s %8.3f V/ns at %.3f ps"
                  % (nm, v["max_rising_V_per_ns"], v["at_ps"]))
        if "I_LTU3_uA" in o:
            print("      I(LTU3) uA: %s" % o["I_LTU3_uA"])
            print("      pulse ends %+.2f ps vs bound_3"
                  % o["pulse_phases_ps"]["pulse_end_minus_bound3_ps"])
    print("\nwrote SK_POLICE.json")


if __name__ == "__main__":
    main()
