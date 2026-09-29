#!/usr/bin/env python3
"""Assemble every measured row into RESULTS.json + a console table.

Every row is reported, including rows that FAIL an instrument gate (A4) and rows
that refute a pre-registered prediction.  Nothing is dropped.
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROWD = os.path.join(HERE, "rowd")


def load(n):
    p = os.path.join(HERE, n)
    return json.load(open(p)) if os.path.exists(p) else None


def rows():
    out = {}
    if os.path.isdir(ROWD):
        for f in sorted(os.listdir(ROWD)):
            if f.endswith(".json"):
                out[f[:-5]] = json.load(open(os.path.join(ROWD, f)))
    return out


def cell_table(R):
    t = []
    for tag, r in sorted(R.items()):
        if "per_node" not in r:
            continue
        hi = [v for v in r["per_node"].values() if v["expect_hi"]]
        lo = [v for v in r["per_node"].values() if not v["expect_hi"]]
        pu = r.get("pullup", {})
        vg = [v.get("Vgs_over_rail_at_end") for v in pu.values()
              if v.get("Vgs_over_rail_at_end") is not None]
        vb = [v.get("Vbs_at_end_V") for v in pu.values()
              if v.get("Vbs_at_end_V") is not None]
        t.append(dict(
            tag=tag, mode=r["mode"], fam=r["fam"], dv=r["dv"],
            wxc_um=r.get("wxc_um"), vin_V=r.get("vin_V"),
            n_dev_per_cell=r["devcount"]["n_dev"],
            n_checked=r["devcount"]["n_checked"],
            VBEND=r["VBEND"], VBOPEN=r["VBOPEN"],
            pullup_overdrive_V=r["VBEND"] - 0.4402734454819182,
            t_hop_ps=r["t_hop_ps"],
            SETTLE_PASS=r["A2_settle_pass"],
            SETTLE_STRICT_PASS=r["A2_settle_strict_pass"],
            t_valid80_ps=r["t_valid80_ps"], t_valid90_ps=r["t_valid90_ps"],
            t_valid95_ps=r["t_valid95_ps"],
            worst_hi_s_end_pct=min((v["s_end_pct"] for v in hi), default=None),
            best_hi_s_end_pct=max((v["s_end_pct"] for v in hi), default=None),
            worst_lo_s_end_pct=min((v["s_end_pct"] for v in lo), default=None),
            s_end_min_pct=r["s_end_min_pct"],
            E_cell_per_op_fJ=r["E_cell_per_op_fJ"],
            E_tankout_fJ=r["E_tankout_fJ"],
            E_gate_per_op_fJ=r["E_gate_per_op_fJ"],
            E_total_per_op_fJ=r.get("E_total_per_op_fJ", r["E_cell_per_op_fJ"]),
            pullup_Vgs_over_rail_at_end=(min(vg) if vg else None),
            pullup_Vbs_at_end_V=(max(vb) if vb else None),
            A4_identity_pass=r["A4_identity_pass"],
            A4_identity_fJ=r["ident_at_zero_fJ"],
            A4_iz_pass=r["A4_iz_pass"], IZ_uA=r["IZ_uA"],
            per_node_s_end={n: round(v["s_end_pct"], 2)
                            for n, v in r["per_node"].items()}))
    return t


def main():
    R = rows()
    out = {
        "_study": "qal/strip -- static-CMOS stripping: nMOS tree + cross-coupled pMOS",
        "_pre_registration": "PRE_REGISTERED.json (sha256 in MTIMES.txt), the "
                             "only file in this directory when it was written",
        "LEAKAGE_dc": load("LEAK_DC.json"),
        "LEAKAGE_hold": load("LEAKAGE.json"),
        "LEAKAGE_null_control": load("LEAK_NULL.json"),
        "LEAKAGE_gmin_floor": load("LEAK_GMIN.json"),
        "RECEIVER": load("RECEIVER.json"),
        "CROSSOVER": load("CROSSOVER.json"),
        "CELLFLOOR": load("CELLFLOOR.json"),
        "DROOP": load("DROOP.json"),
        "CELL_TABLE": cell_table(R),
        "CHAIN": {k: v for k, v in R.items() if k.startswith("chain")},
        "_rows_failing_instrument_gates": [
            r["tag"] for r in cell_table(R)
            if not (r["A4_identity_pass"] and r["A4_iz_pass"])],
    }
    json.dump(out, open(os.path.join(HERE, "RESULTS.json"), "w"), indent=1,
              default=str)

    print("%-26s %-6s %-5s %-5s %7s %7s %8s %9s %9s %8s %8s" %
          ("row", "mode", "dv", "wxc", "VBEND", "ovdrv", "ndev",
           "tvalid90", "worstHI%", "bestHI%", "Etot/op"))
    for r in out["CELL_TABLE"]:
        print("%-26s %-6s %-5.2f %-5s %7.4f %7.4f %8d %9s %9s %8s %8.3f%s" %
              (r["tag"], r["mode"], r["dv"], r["wxc_um"] if r["mode"] == "strip"
               else "-", r["VBEND"], r["pullup_overdrive_V"],
               r["n_dev_per_cell"],
               ("%.1f" % r["t_valid90_ps"]) if r["t_valid90_ps"] else "NEVER",
               ("%.2f" % r["worst_hi_s_end_pct"]) if r["worst_hi_s_end_pct"]
               is not None else "-",
               ("%.2f" % r["best_hi_s_end_pct"]) if r["best_hi_s_end_pct"]
               is not None else "-",
               r.get("E_total_per_op_fJ", r["E_cell_per_op_fJ"]),
               "" if (r["A4_identity_pass"] and r["A4_iz_pass"])
               else "   <-- INSTRUMENT GATE FAIL"))
    print("\nrows failing an instrument gate:",
          out["_rows_failing_instrument_gates"] or "none")


if __name__ == "__main__":
    main()
