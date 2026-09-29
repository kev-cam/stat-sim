#!/usr/bin/env python3
"""Build RESULTS_LSWEEP.json and the human tables from rows.json + cellcmp*.json."""
import json, math, os, sys
import lsw

HERE = os.path.dirname(os.path.abspath(__file__))

# pre-stated comparators (MEASURED anchors handed to this track, not re-derived)
CMOS_LEVEL_PS   = 92.8      # sha_slice 0.928 ns / depth 10, combinational, no flop
CMOS_INV_PS     = 34.81     # single inverter, 1.2 V, 2 fF, committed anchor
CMOS_INV_FJ     = 10.0831   # per full hi+lo cycle
NCELL           = 8


def F(v, n=3):
    return ("%%.%df" % n) % v if isinstance(v, float) and v == v else "n/a"


def main():
    R = json.load(open(os.path.join(HERE, "rows.json")))
    cc = json.load(open(os.path.join(HERE, "cellcmp.json")))
    cc2 = json.load(open(os.path.join(HERE, "cellcmp2.json")))

    def sel(**kw):
        out = []
        for t, r in R.items():
            if "error" in r:
                continue
            ok = True
            for k, v in kw.items():
                rv = r.get(k)
                if isinstance(v, float):
                    ok &= rv is not None and abs(rv - v) < 1e-9
                else:
                    ok &= rv == v
            if ok:
                out.append((t, r))
        return sorted(out, key=lambda kv: -kv[1]["L_nH"])

    COLS = [("L_nH", "L nH", 7, 4), ("total_um", "W um", 5, 0),
            ("t_hop_ps", "t_hop", 8, 3), ("t_hop_pred_ps", "pred", 8, 2),
            ("IPK_uA", "Ipk uA", 8, 1), ("VBPK", "VBpk", 7, 4),
            ("VBEND", "VBend", 7, 4), ("VA_open", "VAopen", 8, 4),
            ("t_rail90_ps", "trail90", 8, 2), ("t_valid90_ps", "tvalid90", 9, 2),
            ("t_settle90_ps", "tsettl90", 9, 2), ("t_level_cons_ps", "t_LEVEL", 8, 2),
            ("E_hop_open_fJ", "Ehop fJ", 8, 3), ("E_R_toC_fJ", "E_R", 6, 3),
            ("E_switchblock_toC_fJ", "E_swblk", 8, 3),
            ("cells_burn_fJ", "cells", 6, 3),
            ("Q_gate_drive_fC", "Qgate fC", 8, 3),
            ("E_gate_drive_fJ", "Egate fJ", 8, 3),
            ("FUNCTIONAL", "FUNC", 5, None)]

    def table(rowsel, cols=COLS):
        lines = [" ".join("%*s" % (w, h) for _, h, w, _ in cols)]
        for t, r in rowsel:
            cells = []
            for k, _, w, p in cols:
                v = r.get(k)
                if p is None:
                    cells.append("%*s" % (w, v))
                elif v is None or (isinstance(v, float) and v != v):
                    cells.append("%*s" % (w, "-"))
                else:
                    cells.append("%*.*f" % (w, p, v))
            lines.append(" ".join(cells))
        return "\n".join(lines)

    out = {}
    print("=" * 130)
    print("PRIMARY L SWEEP, committed optimum switch (tg15p: TG 5/10 um + 1 um park), dV=1.0, RS=10")
    print("=" * 130)
    p = [(t, r) for t, r in R.items() if "error" not in r and r.get("dv") == 1.0
         and r.get("total_um") == 15.0 and r.get("rs_ohm") == 10.0
         and r.get("edge_ps") == 2.0 and r.get("tail_ps") == 500.0
         and abs(r.get("ca_fF", 35.979) - 35.979) < 1e-9]
    p.sort(key=lambda kv: -kv[1]["L_nH"])
    print(table(p))

    print()
    print("=" * 130)
    print("SWITCH WIDTH SWEEP (the speed-vs-width trade), dV=1.0, RS=10")
    print("=" * 130)
    wsel = [(t, r) for t, r in R.items()
            if "error" not in r and r.get("dv") == 1.0 and r.get("rs_ohm") == 10.0
            and r.get("edge_ps") == 2.0 and r.get("tail_ps") == 500.0
            and abs(r.get("ca_fF", 35.979) - 35.979) < 1e-9
            and r["L_nH"] in (100.0, 30.0, 10.0, 3.0, 1.0)]
    wsel.sort(key=lambda kv: (-kv[1]["L_nH"], kv[1]["total_um"]))
    print(table(wsel))

    print()
    print("=" * 130)
    print("dV = 1.2 (raised pre-charge; same bank cap; PDK LV rail ceiling), W=15, RS=10")
    print("=" * 130)
    print(table([(t, r) for t, r in R.items() if "error" not in r
                 and r.get("dv") == 1.2 and abs(r.get("ca_fF", 35.979) - 35.979) < 1e-9],
                ))
    print()
    print("=" * 130)
    print("UNEQUAL-BANK EXCURSION (CA > committed 35.979 fF).  C2 rail-drain does NOT apply:")
    print("a source bank several times the receiving bank is not meant to drain in one hop.")
    print("=" * 130)
    ux = [(t, r) for t, r in R.items() if "error" not in r
          and abs(r.get("ca_fF", 35.979) - 35.979) >= 1e-9]
    ux.sort(key=lambda kv: (kv[1]["ca_fF"], -kv[1]["L_nH"], kv[1]["total_um"]))
    print(table(ux, [("ca_fF", "CA fF", 6, 0)] + COLS))

    print()
    print("=" * 130)
    print("SENSITIVITY (secondary; never a primary row)")
    print("=" * 130)
    ssel = [(t, r) for t, r in R.items()
            if "error" not in r and (r.get("rs_ohm") != 10.0 or r.get("edge_ps") != 2.0
                                     or r.get("tail_ps") != 500.0)]
    ssel = [(t, r) for t, r in ssel if abs(r.get("ca_fF", 35.979) - 35.979) < 1e-9]
    ssel.sort(key=lambda kv: kv[0])
    print(table(ssel))

    print()
    print("=" * 130)
    print("CELL FLOOR (cellcmp / cellcmp2): the SAME cell the hop feeds, 2 fF load")
    print("=" * 130)
    print("%-22s %9s %7s | %9s %9s %9s" % ("case", "VDD", "wp um", "t50 ps", "t90 ps", "t95 ps"))
    for nm, d in list(cc.items()):
        print("%-22s %9.5f %7.2f | %9.3f %9.3f %9.3f"
              % ("cellcmp/" + nm + " " + d["kind"], d["vdd"], 1.12,
                 d["t50_ps"], d["t90_ps"], d["t95_ps"]))
    for nm, d in list(cc2.items()):
        print("%-22s %9.5f %7.2f | %9.3f %9.3f %9.3f"
              % ("cellcmp2/" + nm + " " + d["kind"], d["vdd"], d["wp_um"],
                 d["t50_ps"], d["t90_ps"], d["t95_ps"]))

    # ---- headline -----------------------------------------------------------
    print()
    print("=" * 130)
    print("HEADLINE")
    print("=" * 130)
    func = [(t, r) for t, r in R.items()
            if "error" not in r and r.get("FUNCTIONAL") == "YES"
            and r.get("t_level_cons_ps")]
    func.sort(key=lambda kv: kv[1]["t_level_cons_ps"])
    allrows = [(t, r) for t, r in R.items() if "error" not in r and r.get("t_hop_ps")]
    fasthop = sorted(allrows, key=lambda kv: kv[1]["t_hop_ps"])
    funchop = sorted([(t, r) for t, r in func], key=lambda kv: kv[1]["t_hop_ps"])

    def line(lbl, t, r):
        print("%-34s %-20s L=%-7g W=%-5g t_hop %8.3f ps  t_level %8.2f ps  "
              "VBend %.4f  Ehop %7.3f fJ  (%.3f fJ/cell)"
              % (lbl, t, r["L_nH"], r["total_um"], r["t_hop_ps"],
                 r["t_level_cons_ps"] or float("nan"), r["VBEND"],
                 r["E_hop_open_fJ"], r["E_hop_open_fJ"] / NCELL))

    if fasthop:
        line("fastest t_hop ANY row:", *fasthop[0])
    if funchop:
        line("fastest t_hop FUNCTIONAL:", *funchop[0])
    if func:
        line("fastest t_level FUNCTIONAL:", *func[0])
        r = func[0][1]
        print()
        print("  vs sha_slice CMOS logic level  %.1f ps : t_hop %.2fx, t_level %.2fx"
              % (CMOS_LEVEL_PS, r["t_hop_ps"] / CMOS_LEVEL_PS,
                 r["t_level_cons_ps"] / CMOS_LEVEL_PS))
        print("  vs CMOS inverter floor         %.2f ps : t_hop %.2fx, t_level %.2fx"
              % (CMOS_INV_PS, r["t_hop_ps"] / CMOS_INV_PS,
                 r["t_level_cons_ps"] / CMOS_INV_PS))
        print("  energy: %.3f fJ for 8 cells vs %.2f fJ for 8 CMOS inverter cycles = %.3fx"
              % (r["E_hop_open_fJ"], NCELL * CMOS_INV_FJ,
                 r["E_hop_open_fJ"] / (NCELL * CMOS_INV_FJ)))
    json.dump(dict(primary=[t for t, _ in p],
                   fastest_functional=(func[0][0] if func else None)),
              open(os.path.join(HERE, "report_index.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
