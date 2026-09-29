#!/usr/bin/env python3
"""Extract settle results from the SKEPT st_*.cir.prn decks.

Settle definition (pre-registered A2): for a node expected HIGH,
s = V/rail; for a node expected LOW, s = 1 - V/rail.  A ROW settles at t90 =
the first time at which EVERY checked node in that row has s >= 0.90 and STAYS
>= 0.90 for the rest of the window.  A node still moving at the end has not
settled; a row with any such node reports t90 = NEVER and its worst final s.

All numbers are read off the .prn by this code.  No .measure is used anywhere
in the speed path.
"""
import os, sys, json, collections

THRESH = {"t80": 0.80, "t90": 0.90}


def read_prn(p):
    with open(p) as f:
        lines = [l for l in f if l.strip()]
    hdr = lines[0].split()
    rows = []
    for l in lines[1:]:
        parts = l.split()
        if len(parts) != len(hdr):
            continue
        try:
            rows.append([float(x) for x in parts])
        except ValueError:
            continue
    cols = {h.lower(): i for i, h in enumerate(hdr)}
    return cols, rows


def first_sustained(ts, ok):
    """First index i such that ok[j] is True for all j >= i; None if never."""
    n = len(ok)
    i = n
    while i > 0 and ok[i - 1]:
        i -= 1
    return i if i < n else None


def main():
    d = os.path.dirname(os.path.abspath(__file__))
    meta = json.load(open(os.path.join(d, "SETTLE_META.json")))
    bydeck = collections.defaultdict(list)
    for m in meta:
        bydeck[m["deck"]].append(m)

    out = []
    for deck in sorted(bydeck):
        p = os.path.join(d, deck + ".prn")
        if not os.path.exists(p):
            continue
        cols, rows = read_prn(p)
        ts = [r[0] for r in rows]
        rail = bydeck[deck][0]["rail"]
        byrow = collections.defaultdict(list)
        for m in bydeck[deck]:
            byrow[m["row"]].append(m)
        for rowname in sorted(byrow):
            nodes = byrow[rowname]
            svecs = {}
            bad = False
            for m in nodes:
                ci = cols.get(("V(%s)" % m["node"]).lower())
                if ci is None:
                    bad = True
                    break
                if m["expect"] == "HI":
                    svecs[m["node"]] = [r[ci] / rail for r in rows]
                else:
                    svecs[m["node"]] = [1.0 - r[ci] / rail for r in rows]
            if bad:
                continue
            res = dict(deck=deck, rail=rail, row=rowname,
                       nodes=len(nodes), devices=nodes[0]["devices"],
                       conv=nodes[0]["conv"], topo=nodes[0]["topo"],
                       wxc=nodes[0]["wxc"])
            for lbl, th in THRESH.items():
                ok = [all(svecs[n][i] >= th for n in svecs) for i in range(len(ts))]
                i = first_sustained(ts, ok)
                res[lbl + "_ps"] = None if i is None else ts[i] * 1e12
            finals = {n: svecs[n][-1] for n in svecs}
            worst = min(finals, key=lambda k: finals[k])
            res["worst_node"] = worst
            res["worst_final_pct"] = finals[worst] * 100.0
            res["best_final_pct"] = max(finals.values()) * 100.0
            # is the worst node still moving?  compare last 10% of window
            k = max(2, len(ts) // 10)
            res["worst_still_moving_mV"] = (svecs[worst][-1] - svecs[worst][-k]) * rail * 1000.0
            res["per_node_final_pct"] = {n: round(finals[n] * 100.0, 3) for n in sorted(finals)}
            out.append(res)

    json.dump(out, open(os.path.join(d, "SETTLE_SKEPT.json"), "w"), indent=1)

    order = ["static", "strip56", "strip112"]
    print("SETTLE ON AN IDEAL STIFF RAIL   (t90 = all nodes >= 90%% of rail and staying)")
    print("conv rr = inputs swing to the RAIL (real chain condition)")
    print("conv dv = inputs swing to dV = 1.5 V (the committed bank convention)\n")
    for conv in ("rr", "dv"):
        print("### input convention = %s" % conv)
        print("%-8s %-9s %5s %5s %10s %10s %9s %9s %12s" % (
            "rail", "topo", "dev", "nodes", "t80_ps", "t90_ps",
            "worst%", "best%", "still_mv/win"))
        for r in sorted(set(x["rail"] for x in out)):
            for topo in order:
                m = [x for x in out if x["rail"] == r and x["topo"] == topo
                     and x["conv"] == conv]
                if not m:
                    continue
                x = m[0]
                print("%-8.4f %-9s %5d %5d %10s %10s %9.2f %9.2f %12.3f" % (
                    r, topo, x["devices"], x["nodes"],
                    "NEVER" if x["t80_ps"] is None else "%.1f" % x["t80_ps"],
                    "NEVER" if x["t90_ps"] is None else "%.1f" % x["t90_ps"],
                    x["worst_final_pct"], x["best_final_pct"],
                    x["worst_still_moving_mV"]))
        print()


if __name__ == "__main__":
    main()
