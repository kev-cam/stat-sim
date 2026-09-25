#!/usr/bin/env python3
"""Compare candidate GALS partitions by MEASURED total crossing bits.

Converter tax is O(width) at 124.7 fJ/bit round trip [campaign anchor], so the
figure of merit for a partition is the total number of net bits that cross any
island boundary. Finer partitions expose more crossings; this measures how many.
"""
import json, sys, collections, re

TAX_FJ_PER_BIT = 124.7   # fJ per bit, round trip (campaign anchor, ASSUMED here)


def norm(p):
    p = re.sub(r"\[[0-9]+\]", "", p)
    return ".".join(x for x in p.split(".") if not re.fullmatch(r"genblk\d*", x))


def build(path, top):
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
        sp = [q.split(".") for q in ps]; out = []
        for i in range(min(len(s) for s in sp)):
            t = sp[0][i]
            if all(s[i] == t for s in sp): out.append(t)
            else: break
        return ".".join(out) if out else None

    assign, unass = {}, []
    for cn, c in cells.items():
        if c["type"] in mods:
            assign[cn] = norm(cn.lstrip("\\")) if "." in cn else "<TOP>"; continue
        ps = {bitpath[b] for pin, cc in c["connections"].items() for b in cc
              if isinstance(b, int) and b in bitpath}
        a = lcp(ps)
        if a: assign[cn] = a
        else: unass.append(cn)
    netcells = collections.defaultdict(list)
    for cn, c in cells.items():
        for pin, cc in c["connections"].items():
            for b in cc:
                if isinstance(b, int): netcells[b].append(cn)
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
    return mods, m, cells, assign, netcells


def crossings(cells, assign, netcells, mapper, portbits):
    tot = 0
    pair = collections.Counter()
    for b, cl in netcells.items():
        s = {mapper(assign[c]) for c in cl}
        s.discard(None)
        if b in portbits: s.add("<EXT>")
        if len(s) > 1:
            tot += 1
            for a in sorted(s):
                for c2 in sorted(s):
                    if a < c2: pair[(a, c2)] += 1
    return tot, pair


def main():
    path, top = sys.argv[1], sys.argv[2]
    mods, m, cells, assign, netcells = build(path, top)
    portbits = {b for v in m["ports"].values() for b in v["bits"] if isinstance(b, int)}
    P = "clusters.cluster.sockets.socket."
    CORE = P + "cores.core"

    def depth_mapper(d):
        return lambda a: ".".join(a.split(".")[:d])

    # ---- P1: coarse. core | dcache | icache | mem_arb | l2 | l3
    def p1(a):
        if a.startswith(CORE): return "CORE"
        if a.startswith(P + "dcache"): return "DCACHE"
        if a.startswith(P + "icache"): return "ICACHE"
        if a.startswith(P + "mem_arb"): return "SOCKET_MEM_ARB"
        if a.startswith("clusters.cluster.l2cache"): return "L2"
        if a.startswith("l3cache"): return "L3"
        return "GLUE"

    # ---- P2: core split into pipeline blocks, uncore as in P1
    CORE_BLOCKS = ["execute", "issue", "commit", "schedule", "fetch", "decode",
                   "lmem_unit", "mem_coalescer", "lsu_adapter", "dcr_data"]
    def p2(a):
        if a.startswith(CORE):
            rest = a[len(CORE):].lstrip(".")
            head = rest.split(".")[0] if rest else ""
            return "CORE." + (head if head in CORE_BLOCKS else "glue")
        return p1(a)

    # ---- P3: P2 but execute further split into functional units
    EX = CORE + ".execute"
    EXU = ["alu_unit", "fpu_unit", "lsu_unit", "sfu_unit"]
    def p3(a):
        if a.startswith(EX):
            rest = a[len(EX):].lstrip(".")
            head = rest.split(".")[0] if rest else ""
            return "EX." + (head if head in EXU else "glue")
        return p2(a)

    # ---- P4: whole chip = ONE island (lower bound: only external pins cross)
    def p4(a):
        return "CHIP"

    for tag, fn in [("P4  whole chip = 1 island", p4),
                    ("P1  core | dcache | icache | mem_arb | l2 | l3  (6 islands)", p1),
                    ("P2  P1 with core split into pipeline blocks", p2),
                    ("P3  P2 with execute split into ALU/FPU/LSU/SFU", p3)]:
        tot, pair = crossings(cells, assign, netcells, fn, portbits)
        nis = len({fn(a) for a in assign.values()})
        print("=== %s" % tag)
        print("    islands=%d   crossing net bits=%d   converter tax @124.7 fJ/bit = %.1f pJ per full round trip"
              % (nis, tot, tot * TAX_FJ_PER_BIT / 1000.0))
        for (a, b), n in pair.most_common(8):
            print("        %-22s <-> %-22s %6d bits" % (a, b, n))
        print()


if __name__ == "__main__":
    main()
