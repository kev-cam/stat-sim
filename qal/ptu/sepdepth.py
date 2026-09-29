#!/usr/bin/env python3
"""D6 -- THE SEPARATION TEST, with its comparator reproduced rather than quoted.

The brief's series 528.68 / 22.89 / 1.52 / 0.122 / 0.010 / 0.001 mV belongs to
qal/restore5's UNRESTORED ADJACENT cascade (k6_T300_control), NOT to the skip
chain.  It is reproduced here from restore5's own RESULTS.json so the comparison
is against a number this run has actually recomputed, and so the difference in
TOPOLOGY is explicit rather than implied.

Separation within a bank = min(pull-UP output) - max(pull-DOWN output), at that
bank's own boundary, in mV.  The floor is the PDK's sigma-Vt, 3.42 mV.
"""
import json, os, sys
sys.path.insert(0, "/usr/local/src/stat-sim/qal/skip4")
import skip as SK

HERE = os.path.dirname(os.path.abspath(__file__))
SIGMA = 3.42


def restore5_series():
    d = json.load(open("/usr/local/src/stat-sim/qal/restore5/RESULTS.json"))
    r = d["rows"]["k6_T300_control"]
    o = r["outputs_at_own_boundary_V"]
    out = {}
    for bk in sorted(o, key=lambda x: int(x)):
        vals = o[bk]
        hi = [v for k, v in vals.items() if not SK.is_hi(int(bk), int(k.split("_")[1]))]
        lo = [v for k, v in vals.items() if SK.is_hi(int(bk), int(k.split("_")[1]))]
        if hi and lo:
            out[bk] = dict(min_HIGH_V=round(min(hi), 7), max_LOW_V=round(max(lo), 7),
                           separation_mV=round(1e3 * (min(hi) - max(lo)), 4),
                           below_sigma_vt=bool(abs(1e3 * (min(hi) - max(lo))) < SIGMA))
    return out


def chain_series(r):
    out = {}
    for k, v in (r.get("settling") or {}).items():
        pg = v.get("per_gate", {})
        hi = [g["v_o"] for g in pg.values() if g["kind"] == "pullup"]
        lo = [g["v_o"] for g in pg.values() if g["kind"] == "pulldown"]
        if hi and lo:
            s = 1e3 * (min(hi) - max(lo))
            out[str(k)] = dict(min_HIGH_V=round(min(hi), 6), max_LOW_V=round(max(lo), 6),
                               separation_mV=round(s, 4),
                               below_sigma_vt=bool(abs(s) < SIGMA),
                               INVERTED=bool(s < 0))
    return out


def main():
    out = {"_what": __doc__.strip(), "_sigma_vt_mV": SIGMA,
           "RESTORE5_unrestored_ADJACENT_cascade": restore5_series(),
           "_restore5_note": "DIFFERENT TOPOLOGY: an adjacent, unbuffered cascade with "
                             "no stage-skipping and no top-up. Reproduced here from "
                             "restore5/RESULTS.json, not quoted.",
           "SKIP_CHAIN_by_mode": {}}
    src = [("committed", r) for r in
           json.load(open("/usr/local/src/stat-sim/qal/skiptu/rows.json"))]
    for f in sorted(os.listdir(HERE)):
        if f.startswith("ROWS_") and f.endswith(".json"):
            for r in json.load(open(os.path.join(HERE, f))):
                if "error" not in r:
                    src.append(("ptu_CORRECTED", r))
    for origin, r in src:
        mode = "ptu_CORRECTED" if origin != "committed" else r["mode"]
        nm = "%s|%s|T%g|dv%g|L%g|t%g" % (mode, r["scheme"], r["T_ps"], r["dv"],
                                         r.get("ltu_nH", 0), r.get("t_on_ps", 0))
        out["SKIP_CHAIN_by_mode"][nm] = chain_series(r)
    json.dump(out, open(os.path.join(HERE, "SEPARATION.json"), "w"), indent=1)

    print("=== restore5 UNRESTORED ADJACENT cascade (the brief's comparator) ===")
    for bk, v in out["RESTORE5_unrestored_ADJACENT_cascade"].items():
        print("  bank %s  sep %10.4f mV  %s" %
              (bk, v["separation_mV"], "BELOW sigma-Vt" if v["below_sigma_vt"] else ""))
    print("\n=== SKIP CHAIN separation by bank depth (mV) ===")
    for nm, s in out["SKIP_CHAIN_by_mode"].items():
        row = " ".join("%s:%.3f%s" % (k, v["separation_mV"],
                                      "*" if v["below_sigma_vt"] else
                                      ("!" if v["INVERTED"] else ""))
                       for k, v in sorted(s.items()))
        print("  %-38s %s" % (nm, row))
    print("\n  * below sigma-Vt %.2f mV   ! level INVERTED (LOW above HIGH)" % SIGMA)


if __name__ == "__main__":
    main()
