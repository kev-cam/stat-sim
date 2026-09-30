#!/usr/bin/env python3
"""Collate the census rows into the PASS/MARGINAL/FAIL table and score the
pre-registered predictions.  Applies the gates exactly as PRE_REGISTERED.json
states them; nothing is decided here that was not fixed before the first deck."""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
PRE = json.load(open(os.path.join(HERE, "PRE_REGISTERED.json")))
DEPTH = json.load(open(os.path.join(HERE, "cells", "stack_depths.json")))
DEPTH.update(json.load(open(os.path.join(HERE, "cells", "stack_depths_extra.json"))))
FAMS = ["inv", "buf", "nand2", "and2", "nor2", "or2", "nor2b", "xnor2", "xor2",
        "mux2", "a21oi", "a21o", "o21ai"]
C3_FACTOR = 2.0


def load():
    rows = {}
    d = os.path.join(HERE, "rowd")
    for fn in sorted(os.listdir(d)):
        if fn.endswith(".json"):
            r = json.load(open(os.path.join(d, fn)))
            rows[r["tag"]] = r
    return rows


def main():
    rows = load()
    fam = {r["family"]: r for r in rows.values()
           if r.get("family") and not r.get("handbuilt") and r["tag"].startswith("f_")}
    ref = fam.get("inv")
    out = {}
    print("%-7s %4s %9s %9s %9s %8s %8s %7s %6s  %s"
          % ("family", "bind", "t_hop", "tv80", "tv90", "t_level", "xINV",
             "VBEND", "VAopen", "verdict"))
    for f in FAMS:
        r = fam.get(f)
        if r is None:
            print("%-7s  --  (no row)" % f)
            continue
        c1, c2 = r["C1_VALUE"], r["C2_SETTLE"]
        tl = r["t_level_meas_ps"]
        x = (tl / ref["t_level_meas_ps"]) if (tl and ref and ref["t_level_meas_ps"]) else None
        c3 = bool(x is not None and x <= C3_FACTOR)
        v = "PASS" if (c1 and c2 and c3) else ("MARGINAL" if (c1 and c2) else "FAIL")
        out[f] = dict(cell=r["cell"], binding_pmos_rise_depth=r["binding_pmos_rise_depth"],
                      t_hop_ps=r["t_hop_ps"], t_valid80_ps=r["t_valid80_ps"],
                      t_valid90_ps=r["t_valid90_ps"], t_level_meas_ps=tl,
                      x_vs_inv=x, VBEND=r["VBEND"], VA_open=r["VA_open"],
                      settled_min_pct=min(r["s_end"].values()),
                      C1_VALUE=c1, C2_SETTLE=c2, C3_SPEED=c3, verdict=v,
                      vec_out_hi=r["vec_out_hi"], vec_out_lo=r["vec_out_lo"],
                      value_check=r["value_check"], v_end=r["v_end"],
                      wall_s=r.get("wall_s"))
        print("%-7s %4d %9.3f %9s %9s %8s %8s %7.4f %+6.3f  %s"
              % (f, r["binding_pmos_rise_depth"], r["t_hop_ps"],
                 _f(r["t_valid80_ps"]), _f(r["t_valid90_ps"]), _f(tl),
                 ("%.2fx" % x) if x else "--", r["VBEND"], r["VA_open"], v))
    json.dump(out, open(os.path.join(HERE, "CENSUS_TABLE.json"), "w"), indent=1)

    # score the pre-registered per-family predictions
    pred = PRE["PRE_STATED_PREDICTIONS"]["census_verdicts"]
    print("\nPREDICTION SCORING")
    hit = tot = 0
    for f, r in out.items():
        p = pred.get(f)
        if not p:
            continue
        p0 = p.split()[0]
        tot += 1
        ok = (p0 == r["verdict"])
        hit += ok
        print("  %-7s predicted %-9s measured %-9s %s"
              % (f, p0, r["verdict"], "HIT" if ok else "MISS"))
    print("  %d/%d" % (hit, tot))
    return out


def _f(x):
    return "never" if x is None else "%.1f" % x


if __name__ == "__main__":
    main()
