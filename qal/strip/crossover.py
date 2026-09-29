#!/usr/bin/env python3
"""(d, part 2) THE DEVICE-COUNT CROSSOVER, as a library rule rather than six
anecdotes.

For every family of the committed qal/sha256 mapped-netlist census, the factored
series-parallel nMOS tree of f and of f-bar is written down, VERIFIED EXHAUSTIVELY
against that cell's own truth table from qal/sha256/cells/stack_depths.json, and
counted.  The static count is the PDK cell's own device count from
qal/sha256/cells/cell_widths.json.

  stripped = n(tree f) + n(tree f-bar) + 2
  static   = n_nmos + n_pmos                     (the PDK cell as shipped)

For a single-stage complementary CMOS gate realising a series-parallel function,
n_nmos = n_pmos = N and the two trees of the stripped form are duals of the same
size, so stripped - static = 2 - ovh where ovh is whatever the PDK cell spends
BEYOND one complementary pair -- an internal inverter, an output stage, an input
inverter.  The crossover is therefore at ovh = 2, and it is a statement about
INVERSION OVERHEAD, not about gate complexity.
"""
import json, os, itertools

PDKDIR = "/usr/local/src/stat-sim/qal/sha256/cells"
S = lambda *a: ("S", list(a))
P = lambda *a: ("P", list(a))

# TQ conducts exactly when f = 0; TN conducts exactly when f = 1.
TREES = {
    "inv":   (["A"], "A", "A#"),
    "buf":   (["A"], "A#", "A"),
    "nand2": (["A", "B"], S("A", "B"), P("A#", "B#")),
    "nor2":  (["A", "B"], P("A", "B"), S("A#", "B#")),
    "and2":  (["A", "B"], P("A#", "B#"), S("A", "B")),
    "or2":   (["A", "B"], S("A#", "B#"), P("A", "B")),
    "nor2b": (["A", "B_N"], P("A", "B_N#"), S("A#", "B_N")),
    "xnor2": (["A", "B"], P(S("A", "B#"), S("A#", "B")),
              P(S("A", "B"), S("A#", "B#"))),
    "xor2":  (["A", "B"], P(S("A", "B"), S("A#", "B#")),
              P(S("A", "B#"), S("A#", "B"))),
    "mux2":  (["A0", "A1", "S"], P(S("S", "A1#"), S("S#", "A0#")),
              P(S("S", "A1"), S("S#", "A0"))),
    "a21oi": (["A1", "A2", "B1"], P(S("A1", "A2"), "B1"),
              S(P("A1#", "A2#"), "B1#")),
    "a21o":  (["A1", "A2", "B1"], S(P("A1#", "A2#"), "B1#"),
              P(S("A1", "A2"), "B1")),
    "o21ai": (["A1", "A2", "B1"], S(P("A1", "A2"), "B1"),
              P(S("A1#", "A2#"), "B1#")),
}
CELL = {f: "sg13g2_%s_1" % f for f in TREES}


def count(e):
    return 1 if isinstance(e, str) else sum(count(c) for c in e[1])


def conducts(e, v):
    if isinstance(e, str):
        return (v[e[:-1]] == 0) if e.endswith("#") else (v[e] == 1)
    kind, ch = e
    return (any if kind == "P" else all)(conducts(c, v) for c in ch)


def main():
    depth = json.load(open(os.path.join(PDKDIR, "stack_depths.json")))
    depth.update(json.load(open(os.path.join(PDKDIR, "stack_depths_extra.json"))))
    wid = json.load(open(os.path.join(PDKDIR, "cell_widths.json")))
    rows, bad = [], []
    for fam, (ports, tq, tn) in TREES.items():
        c = CELL[fam]
        info = depth.get(c, {})
        truth = info.get("truth")
        # ---- exhaustive verification of the tree against the PDK truth table
        ok, checked = True, 0
        if truth:
            keys = info["inputs"]
            for bits in itertools.product([0, 1], repeat=len(keys)):
                v = dict(zip(keys, bits))
                f = truth["".join(str(b) for b in bits)]
                a, b = conducts(tq, v), conducts(tn, v)
                checked += 1
                if not (a == (f == 0) and b == (f == 1) and a != b):
                    ok = False
                    bad.append((fam, v, f, a, b))
        nq, nn = count(tq), count(tn)
        strip = nq + nn + 2
        st_nd = wid.get(c, {}).get("n_dev")
        st_n = info.get("n_n")
        st_p = info.get("n_p")
        ovh = None if (st_nd is None or st_n is None) else st_nd - 2 * nq
        rows.append(dict(
            family=fam, cell=c,
            tree_f_bar_devs=nq, tree_f_devs=nn,
            stripped_n_dev=strip, static_n_dev=st_nd,
            static_n_nmos=st_n, static_n_pmos=st_p,
            delta_stripped_minus_static=None if st_nd is None else strip - st_nd,
            inversion_overhead_ovh=ovh,
            static_binding_pmos_rise_depth=info.get("binding_pmos_rise_depth"),
            static_pmos_series_topological=info.get("pmos_series_topological"),
            tree_verified_against_pdk_truth=ok, truth_vectors_checked=checked))
    rows.sort(key=lambda r: (r["delta_stripped_minus_static"] is None,
                             r["delta_stripped_minus_static"], r["family"]))
    out = {
        "_method": __doc__.strip(),
        "_all_trees_verified": all(r["tree_verified_against_pdk_truth"]
                                   for r in rows),
        "_mismatches": bad,
        "rows": rows,
        "RULE": {
            "arithmetic": "stripped - static = 2 - ovh, ovh = static devices "
                          "beyond one complementary pair of the factored tree",
            "loses_by_2": [r["family"] for r in rows
                           if r["delta_stripped_minus_static"] == 2],
            "ties": [r["family"] for r in rows
                     if r["delta_stripped_minus_static"] == 0],
            "wins_by_2": [r["family"] for r in rows
                          if r["delta_stripped_minus_static"] == -2],
        }}
    open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "CROSSOVER.json"), "w").write(json.dumps(out, indent=1))
    print("%-7s %5s %5s %7s %7s %6s %5s %6s" %
          ("fam", "tQ", "tN", "strip", "static", "delta", "ovh", "pdep"))
    for r in rows:
        print("%-7s %5d %5d %7d %7s %6s %5s %6s   %s" %
              (r["family"], r["tree_f_bar_devs"], r["tree_f_devs"],
               r["stripped_n_dev"], r["static_n_dev"],
               r["delta_stripped_minus_static"], r["inversion_overhead_ovh"],
               r["static_binding_pmos_rise_depth"],
               "verified" if r["tree_verified_against_pdk_truth"] else "TREE BAD"))
    print("\nall trees verified against PDK truth tables:",
          out["_all_trees_verified"])
    print("RULE:", json.dumps(out["RULE"], indent=1))


if __name__ == "__main__":
    main()
