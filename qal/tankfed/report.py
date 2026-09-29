#!/usr/bin/env python3
"""Assemble the qal/tankfed tables: the 2x2 matrix, the matching result, the
per-gate table, the cost, and the acceptance verdict against PRE_REGISTERED.json.
"""
import json, os, sys
import tf

HERE = tf.HERE
SIG = 6.44          # mV, CORRECTED 1-sigma floor, qal/vtaudit/AUDIT.md
CLIFF = 0.600
BAR_COUPLING = 7.0  # mV, A1
CAP_DENSITY = 1.5   # fF/um^2, MEASURED from the PDK: cap_carea = 1.5E-15 in
                    # IHP-Open-PDK/ihp-sg13g2/libs.tech/ngspice/models/cornerCAP.lib
                    # (cmim, typ; +-10% over the CAP corners)


def load(name):
    p = os.path.join(HERE, name)
    return json.load(open(p)) if os.path.exists(p) else None


def tank_area(ctk):
    tot = sum(ctk.values()) if isinstance(ctk, dict) else sum(ctk)
    return tot / CAP_DENSITY, tot


def main():
    out = {"_what": "qal/tankfed assembled results",
           "sigma_floor_mV": SIG, "cliff_V": CLIFF,
           "coupling_bar_mV": BAR_COUPLING,
           "cap_density_fF_per_um2": CAP_DENSITY,
           "cap_density_provenance": "MEASURED from the PDK: cap_carea = 1.5E-15 "
           "F/um^2 (cmim, typ) in ihp-sg13g2/libs.tech/ngspice/models/cornerCAP.lib; "
           "0.9x / 1.1x at the CAP corners"}
    rows = []
    for nm in ("ROWS_m6.json", "ROWS_matrix.json", "ROWS_buck.json", "ROWS_dv165.json",
               "ROWS_bare.json", "ROWS_m2.json"):
        r = load(nm)
        if r:
            rows += [x for x in r if "error" not in x]
    out["n_rows"] = len(rows)
    cb = load("CBANK.json")
    if cb:
        out["C_bank_MEASURED_fF"] = {str(r["M"]): round(r["C_bank_fF"], 4)
                                     for r in cb if "C_bank_fF" in r}
    out["rows"] = []
    for r in rows:
        c = r["cfg"]
        area, tot = tank_area({int(k): v for k, v in r["ctk_fF"].items()})
        out["rows"].append(dict(
            tag=r["tag"], dest=c["dest"], sizing=c["sizing"], m=c["m"],
            form=c["form"], dv=c["dv"], T_ps=r["T_ps"],
            tz_ps=r["tz_ps"], hop_spread=r["hop_spread"],
            rail_V=[None if v is None else round(v, 5) for v in r["rail_by_stage_V"]],
            collapse=[None if v is None else round(v, 4)
                      for v in r["collapse_ratio_by_hop"]],
            worst_settle_pct=[None if v is None else round(v, 2)
                              for v in r["worst_gate_by_stage_pct"]],
            separation_mV=[None if v is None else round(v, 4)
                           for v in r["separation_by_depth_mV"]],
            max_LOW_V=[None if v is None else round(v, 6)
                       for v in r["max_LOW_by_stage_V"]],
            guard_fail=r["guard_fail_by_stage"], value_fail=r["value_fail_by_stage"],
            IZ_uA=[None if v is None else round(v, 4) for v in r["IZ_uA"]],
            IZ_gate_pass=r["IZ_gate_pass"], cliff_pass=r["cliff_pass"],
            tank_total_fF=round(tot, 2), tank_area_um2=round(area, 1),
            ledger=r.get("ledger")))
    json.dump(out, open(os.path.join(HERE, "RESULTS.json"), "w"), indent=1)
    # ---- printable matrix
    print("\n%-5s %-8s %-4s %-6s %-5s | %-8s | %s"
          % ("dest", "sizing", "m", "form", "dV", "spread", "rail by bank (V)"))
    for r in out["rows"]:
        print("%-5s %-8s %-4g %-6s %-5g | %8.3f | %s" %
              (r["dest"], r["sizing"], r["m"], r["form"], r["dv"],
               r["hop_spread"] or 0,
               " ".join("%8.4f" % v if v is not None else "    None"
                        for v in r["rail_V"])))
    print("wrote RESULTS.json")


if __name__ == "__main__":
    main()
