#!/usr/bin/env python3
"""Extract the adjudication ramp sweep.

Settle definition is the SAME as both runs used (polarity-aware, sustained):
HIGH node s = V/rail_instantaneous, LOW node s = 1 - V/rail_instantaneous;
a row settles at t90 when EVERY checked node has s >= 0.90 and stays there.
Referenced to the instantaneous rail, which is what "within 10% of the rail"
must mean while the rail is still moving.
"""
import glob, json, os, sys, collections

HERE = os.path.dirname(os.path.abspath(__file__))


def read(p):
    with open(p) as f:
        lines = [l for l in f if l.strip()]
    hdr = lines[0].split()
    rows = []
    for l in lines[1:]:
        q = l.split()
        if len(q) != len(hdr):
            continue
        try:
            rows.append([float(x) for x in q])
        except ValueError:
            continue
    return {h.upper(): i for i, h in enumerate(hdr)}, rows


def first_sustained(ok):
    i = len(ok)
    while i > 0 and ok[i - 1]:
        i -= 1
    return i if i < len(ok) else None


def main():
    out = []
    for cir in sorted(glob.glob(os.path.join(HERE, "rmp_r*_t*.cir"))):
        tag = os.path.basename(cir)[:-4]
        prn, mf = cir + ".prn", cir[:-4] + ".meta.json"
        if not (os.path.exists(prn) and os.path.exists(mf)):
            continue
        cols, rows = read(prn)
        if len(rows) < 50:
            continue
        meta = json.load(open(mf))
        rail_nom = float(tag.split("_r")[1].split("_t")[0].replace("p", "."))
        tr = float(tag.split("_t")[1])
        ri = cols.get("V(RAIL)")
        ts = [r[0] for r in rows]
        railv = [r[ri] for r in rows]
        # only judge once the rail is up (>=99% of nominal)
        i0 = next((i for i, v in enumerate(railv) if v >= 0.99 * rail_nom), 0)
        bytopo = collections.defaultdict(list)
        for m in meta:
            bytopo[m["topo"]].append(m)
        for topo, nodes in bytopo.items():
            s = {}
            for m in nodes:
                ci = cols.get("V(%s)" % m["node"].upper())
                if ci is None:
                    continue
                if m["expect"] == "HI":
                    s[m["node"]] = [r[ci] / railv[i] if railv[i] > 1e-6 else 0.0
                                    for i, r in enumerate(rows)]
                else:
                    s[m["node"]] = [1.0 - r[ci] / railv[i] if railv[i] > 1e-6
                                    else 1.0 for i, r in enumerate(rows)]
            ok = [all(s[n][i] >= 0.90 for n in s) for i in range(i0, len(ts))]
            k = first_sustained(ok)
            fin = {n: s[n][-1] for n in s}
            worst = min(fin, key=lambda x: fin[x])
            out.append(dict(tag=tag, rail=rail_nom, ramp_ps=tr, topo=topo,
                            t90_ps=None if k is None else ts[i0 + k] * 1e12,
                            worst_node=worst, worst_pct=100 * fin[worst],
                            per_node={n: round(100 * fin[n], 2)
                                      for n in sorted(fin)}))
    json.dump(out, open(os.path.join(HERE, "RAMP_ADJ.json"), "w"), indent=1)
    print("%-8s %-7s %-9s %-11s %-14s %8s" %
          ("rail", "ramp", "topo", "t90_ps", "worst_node", "worst%"))
    for r in sorted(out, key=lambda x: (x["rail"], x["ramp_ps"], x["topo"])):
        print("%-8.4f %-7g %-9s %-11s %-14s %8.2f" %
              (r["rail"], r["ramp_ps"], r["topo"],
               "NEVER" if r["t90_ps"] is None else "%.1f" % r["t90_ps"],
               r["worst_node"], r["worst_pct"]))


if __name__ == "__main__":
    main()
