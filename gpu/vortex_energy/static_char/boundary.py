#!/usr/bin/env python3
"""MEASURED island cut widths: how many net BITS cross each hierarchy boundary.

The GALS converter tax is O(width) (124.7 fJ/bit round trip), so the cut width
between candidate islands -- not the module count -- decides whether a partition
pays for itself. This counts, for every net bit in the top module, the set of
islands whose cells touch it; a bit touched by >1 island is a crossing bit.

Cells inside modules that survived as modules are represented by their instance,
which is attributed exactly by its hierarchical instance name, so the top-level
net graph is a complete cut model.
"""
import json, sys, collections, re

def norm(p):
    p = re.sub(r"\[[0-9]+\]", "", p)
    return ".".join(x for x in p.split(".") if not re.fullmatch(r"genblk\d*", x))


def main():
    path, top, depth = sys.argv[1], sys.argv[2], int(sys.argv[3])
    mods = json.load(open(path))["modules"]
    m = mods[top]
    cells = {k: v for k, v in m["cells"].items() if v["type"] != "$scopeinfo"}

    bitpath = {}
    for nname, nn in m.get("netnames", {}).items():
        if nname.startswith("$") or "." not in nname:
            continue
        p = norm(nname.rsplit(".", 1)[0])
        if p:
            for b in nn["bits"]:
                if isinstance(b, int) and b not in bitpath:
                    bitpath[b] = p

    def lcp(ps):
        if not ps: return None
        sp = [p.split(".") for p in ps]; out = []
        for i in range(min(len(s) for s in sp)):
            t = sp[0][i]
            if all(s[i] == t for s in sp): out.append(t)
            else: break
        return ".".join(out) if out else None

    assign, unass = {}, []
    for cn, c in cells.items():
        if c["type"] in mods:
            assign[cn] = norm(cn.lstrip("\\")) if "." in cn else "<TOP>"
            continue
        ps = {bitpath[b] for pin, cc in c["connections"].items() for b in cc
              if isinstance(b, int) and b in bitpath}
        a = lcp(ps)
        if a: assign[cn] = a
        else: unass.append(cn)

    netcells = collections.defaultdict(list)
    for cn, c in cells.items():
        for pin, cc in c["connections"].items():
            for b in cc:
                if isinstance(b, int):
                    netcells[b].append(cn)
    for _ in range(12):
        still, prog = [], 0
        for cn in unass:
            v = collections.Counter()
            for pin, cc in cells[cn]["connections"].items():
                for b in cc:
                    if isinstance(b, int):
                        for o in netcells[b]:
                            if o in assign: v[assign[o]] += 1
            if v: assign[cn] = v.most_common(1)[0][0]; prog += 1
            else: still.append(cn)
        unass = still
        if not prog: break
    for cn in unass: assign[cn] = "<UNATTRIBUTED>"

    def isl(cn):
        return ".".join(assign[cn].split(".")[:depth])

    # top-level ports are an external island
    portbits = set()
    for p, v in m["ports"].items():
        for b in v["bits"]:
            if isinstance(b, int): portbits.add(b)

    pair = collections.Counter()
    per_island_cut = collections.Counter()
    for b, cl in netcells.items():
        s = {isl(c) for c in cl}
        if b in portbits: s.add("<EXTERNAL_PINS>")
        if len(s) <= 1: continue
        for i in s: per_island_cut[i] += 1
        for a in sorted(s):
            for c2 in sorted(s):
                if a < c2: pair[(a, c2)] += 1

    print("### ISLAND CUT WIDTH (net bits touched by >1 island), depth=%d" % depth)
    print("%-58s %9s" % ("island", "cut_bits")); print("-"*69)
    for i, n in per_island_cut.most_common(24):
        print("%-58s %9d" % (i[:58], n))
    print()
    print("### LARGEST ISLAND-PAIR CUTS (shared net bits)")
    print("%-40s %-40s %8s" % ("island A", "island B", "bits")); print("-"*90)
    for (a, b), n in pair.most_common(26):
        print("%-40s %-40s %8d" % (a[-40:], b[-40:], n))


if __name__ == "__main__":
    main()
