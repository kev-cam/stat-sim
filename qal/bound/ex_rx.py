#!/usr/bin/env python3
"""Extract the QAL->sync receiver TRANSIENT result (Track 3 H1).

Every integrator value is t0-referenced (the campaign's 1F pedestal trap): the
Z checkpoint at 5 ps is subtracted from every later checkpoint.

Checkpoints: Z=5 A=100 (pre-rise) B=end of rise S=end of hold minus 30 ps
             C=end of hold D=end of fall E=1195  (all ps)

The 'static' current is taken from the LAST 30 ps of the hold (C-S), not from
the whole hold window, because a slow receiver is still completing its switching
transient in the earlier part of the window; the DC deck (bd_dc) is the
authoritative instrument for true static contention and is reported beside it.
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
T_EDGE = 266.755223
T_HOLD = 293.245
T_B = 100.0 + T_EDGE
T_C = T_B + T_HOLD
VQAL = 0.6758936
TRIP12, TRIP09 = 0.6452, 0.4959       # MEASURED downstream trip points (bd_dc)

CELLS = {
    "A": ("QAL 0.6759 V -> STANDARD receiver 1.12p/0.74n @1.2V", VQAL, 1.2, T_EDGE, 1.12, 0.74, 1),
    "B": ("sync 1.2 V, SAME 266.8 ps slope -> 1.12p/0.74n (level control for A)", 1.2, 1.2, T_EDGE, 1.12, 0.74, 1),
    "C": ("QAL -> skewed 0.28p/0.74n @1.2V", VQAL, 1.2, T_EDGE, 0.28, 0.74, 1),
    "D": ("QAL -> strongly skewed 0.15p/1.48n @1.2V", VQAL, 1.2, T_EDGE, 0.15, 1.48, 1),
    "E": ("QAL -> STANDARD 1.12p/0.74n on a REDUCED 0.9 V rail", VQAL, 0.9, T_EDGE, 1.12, 0.74, 1),
    "F": ("sync 1.2 V, 34.81 ps edge -> 1.12p/0.74n (ANCHOR CHECK vs 10.0831 fJ)", 1.2, 1.2, 34.81, 1.12, 0.74, 1),
    "G": ("QAL -> most-skewed shared-geometry 0.15p/0.74n @1.2V", VQAL, 1.2, T_EDGE, 0.15, 0.74, 1),
    "H": ("sync 1.2 V, 266.8 ps slope -> 0.15p/1.48n (level control for D)", 1.2, 1.2, T_EDGE, 0.15, 1.48, 1),
    "K": ("QAL -> skewed 0.15p/1.48n on a REDUCED 0.9 V rail (skew AND rail)", VQAL, 0.9, T_EDGE, 0.15, 1.48, 1),
    "L": ("QAL -> 0.15p/2.96n @1.2V (skew + 2x nMOS)", VQAL, 1.2, T_EDGE, 0.15, 2.96, 2),
    "M": ("QAL -> 0.15p/5.92n @1.2V (skew + 4x nMOS, speed-limit probe)", VQAL, 1.2, T_EDGE, 0.15, 5.92, 4),
}


def parse_mt0(path):
    d = {}
    for ln in open(path):
        m = re.match(r"\s*(\w+)\s*=\s*(\S+)", ln)
        if m:
            try:
                d[m.group(1).upper()] = float(m.group(2))
            except ValueError:
                pass
    return d


def main(fn="bd_rx2.cir.mt0", out="rx_rows.json"):
    m = parse_mt0(os.path.join(HERE, fn))
    f = 1e15
    res = {}
    for tag, (lbl, vhi, vdd, edge, wp, wn, nn) in CELLS.items():
        if "E1%s_Z" % tag not in m:
            continue

        def ck(nm, l):
            return m["%s%s_%s" % (nm, tag, l)] - m["%s%s_Z" % (nm, tag)]

        d = dict(label=lbl, v_high=vhi, vdd=vdd, edge_ps=edge,
                 wp_um=wp, wn_um=wn, n_nmos_parallel=nn)
        d["E_stage1_cycle_fJ"] = (ck("E1", "E") - ck("E1", "A")) * f
        d["E_stage2_cycle_fJ"] = (ck("E2", "E") - ck("E2", "A")) * f
        d["E_both_stages_cycle_fJ"] = d["E_stage1_cycle_fJ"] + d["E_stage2_cycle_fJ"]
        d["E_stage1_whole_hold_fJ"] = (ck("E1", "C") - ck("E1", "B")) * f
        e30 = (ck("E1", "C") - ck("E1", "S")) * f
        d["E_stage1_last30ps_of_hold_fJ"] = e30
        d["I_near_steady_uA"] = e30 * 1e-15 / 30e-12 / vdd * 1e6
        qi = ck("QI", "B") * f
        d["Q_in_rise_fC"] = qi
        d["C_in_eff_fF"] = qi / vhi
        d["E_in_cycle_fJ"] = (ck("EI", "E") - ck("EI", "A")) * f
        d["Vout1_at_end_of_hold"] = m["O1AT%s" % tag]
        d["Vout1_min_during_hold"] = m["O1MIN%s" % tag]
        d["Vout2_at_end_of_hold"] = m["O2AT%s" % tag]
        for nm in ("TIN", "TO1", "TO2", "TRSV"):
            k = nm + tag
            d[nm + "_ps"] = m[k] * 1e12 if k in m and m[k] > 0 else None
        if d["TIN_ps"]:
            for a, b in (("TO1", "delay_in50_to_out1_50_ps"),
                         ("TO2", "delay_in50_to_out2_50_ps"),
                         ("TRSV", "delay_in50_to_stage1_below_downstream_trip_ps")):
                d[b] = (d[a + "_ps"] - d["TIN_ps"]) if d[a + "_ps"] else None
        trip = TRIP12 if abs(vdd - 1.2) < 1e-9 else TRIP09
        # does the receiver resolve INSIDE the measured 293 ps valid window?
        inside = (d["TRSV_ps"] is not None and d["TRSV_ps"] <= T_C)
        d["resolves_inside_valid_window"] = bool(inside)
        d["downstream_trip_used_V"] = trip
        v = []
        v.append("RESOLVES in-window" if inside else "DOES NOT RESOLVE in-window")
        v.append("Vout1@window_close=%.4f (needs <= %.4f to read as 0)"
                 % (d["Vout1_at_end_of_hold"], trip))
        v.append("I_near_steady %.3f uA" % d["I_near_steady_uA"])
        d["verdict_vs_H1"] = "; ".join(v)
        res[tag] = d
    json.dump(res, open(os.path.join(HERE, out), "w"), indent=1)
    hdr = ("%-3s %-58s %8s %8s %8s %8s %8s %7s %7s" %
           ("tag", "label", "E1_fJ", "E12_fJ", "Ein_fJ", "Cin_fF",
            "t_rsv", "Vo1end", "Ist_uA"))
    print(hdr)
    print("-" * len(hdr))
    for tag in sorted(res):
        d = res[tag]
        print("%-3s %-58s %8.3f %8.3f %8.3f %8.3f %8s %7.4f %7.3f  %s"
              % (tag, d["label"][:58], d["E_stage1_cycle_fJ"],
                 d["E_both_stages_cycle_fJ"], d["E_in_cycle_fJ"],
                 d["C_in_eff_fF"],
                 ("%.1f" % d["delay_in50_to_stage1_below_downstream_trip_ps"])
                 if d.get("delay_in50_to_stage1_below_downstream_trip_ps") else "none",
                 d["Vout1_at_end_of_hold"], d["I_near_steady_uA"],
                 "OK" if d["resolves_inside_valid_window"] else "FAIL"))
    print("\nwrote", out)


if __name__ == "__main__":
    main(*(sys.argv[1:] or []))
