#!/usr/bin/env python3
"""Attribute the cells sv2v INLINED into the top module back to RTL hierarchy paths.

sv2v inlines every module that has SystemVerilog interface ports (VX_core,
VX_execute, VX_alu_int, VX_schedule, VX_cache, ...) into its parent, so the
yosys netlist has no module for them. But sv2v preserves the full hierarchical
signal name (clusters[0].cluster.sockets[0].socket.cores[0].core.execute....),
so each named net bit carries its block path.

Attribution: seed each cell from the named nets it touches (longest common
hierarchy prefix), then flood unlabelled cells from their labelled neighbours.
Submodule INSTANCES that survived as real modules are attributed exactly, by
their instance name, and their subtree cell counts are added to that path.

This is a DERIVED attribution, not an exact per-module synthesis. Cells on a
boundary land on the common ancestor, which is the desired behaviour (glue
belongs to the parent). Totals are conserved and reported.
"""
import json, sys, collections, re

SEQ_PREFIXES = ("$_DFF", "$_SDFF", "$_DLATCH", "$_ALDFF", "$_DFFSR")
MUX_TYPES = ("$_MUX_", "$_MUX4_", "$_MUX8_", "$_MUX16_", "$_NMUX_")
MEM_PREFIXES = ("$mem", "$memrd", "$memwr", "$meminit")
OUT_PINS = ("Y", "Q", "DATA", "RD_DATA")


def base_name(t):
    m = re.match(r"^\$paramod\$[0-9a-f]+\\(.+)$", t) or re.match(r"^\$paramod\\([^\\]+)\\", t)
    return m.group(1) if m else t


def norm(path):
    """Drop array indices and sv2v genblk noise: clusters[0].cluster -> clusters.cluster."""
    p = re.sub(r"\[[0-9]+\]", "", path)
    parts = [x for x in p.split(".") if not re.fullmatch(r"genblk\d*", x)]
    return ".".join(parts)


def subtree_totals(mods):
    """cells in each module's whole subtree (own + descendants)."""
    memo = {}
    F = ("comb", "seq", "mux", "mem", "membits")

    def own(name):
        m = mods[name]
        cnt = collections.Counter()
        kids = collections.Counter()
        membits = 0
        for c in m.get("cells", {}).values():
            t = c["type"]
            if t == "$scopeinfo":
                continue
            if t in mods:
                kids[t] += 1; continue
            cnt[t] += 1
            if t.startswith("$mem"):
                p = c.get("parameters", {})
                def gi(k):
                    v = p.get(k, 0)
                    return int(v, 2) if isinstance(v, str) and set(v) <= set("01") else (int(v) if not isinstance(v, str) else 0)
                membits += gi("SIZE") * gi("WIDTH")
        seq = sum(n for t, n in cnt.items() if t.startswith(SEQ_PREFIXES))
        mux = sum(n for t, n in cnt.items() if t in MUX_TYPES)
        mem = sum(n for t, n in cnt.items() if t.startswith(MEM_PREFIXES))
        gates = sum(n for t, n in cnt.items() if not t.startswith(MEM_PREFIXES))
        return dict(comb=gates - seq, seq=seq, mux=mux, mem=mem, membits=membits), kids

    def go(name, path):
        if name in memo:
            return memo[name]
        if name in path or name not in mods:
            return {f: 0 for f in F}
        o, kids = own(name)
        for k, n in kids.items():
            sub = go(k, path | {name})
            for f in F:
                o[f] += n * sub[f]
        memo[name] = o
        return o

    return go, own


def main():
    path, top, depth = sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 99
    mods = json.load(open(path))["modules"]
    m = mods[top]
    go, own = subtree_totals(mods)

    # ---- net bit -> hierarchy path, from public (named) nets ----
    bitpath = {}
    for nname, nn in m.get("netnames", {}).items():
        if nname.startswith("$") or "." not in nname:
            continue
        p = norm(nname.rsplit(".", 1)[0])
        if not p:
            continue
        for b in nn["bits"]:
            if isinstance(b, int) and b not in bitpath:
                bitpath[b] = p

    cells = {k: v for k, v in m["cells"].items() if v["type"] != "$scopeinfo"}

    def lcp(paths):
        if not paths:
            return None
        sp = [p.split(".") for p in paths]
        out = []
        for i in range(min(len(s) for s in sp)):
            t = sp[0][i]
            if all(s[i] == t for s in sp):
                out.append(t)
            else:
                break
        return ".".join(out) if out else None

    # ---- seed from named nets ----
    assign, unass = {}, []
    for cn, c in cells.items():
        ps = set()
        for pin, conns in c["connections"].items():
            for b in conns:
                if isinstance(b, int) and b in bitpath:
                    ps.add(bitpath[b])
        a = lcp(ps)
        if a:
            assign[cn] = a
        else:
            unass.append(cn)

    # ---- flood unassigned from neighbours (via shared nets) ----
    netcells = collections.defaultdict(list)
    for cn, c in cells.items():
        for pin, conns in c["connections"].items():
            for b in conns:
                if isinstance(b, int):
                    netcells[b].append(cn)
    for _ in range(12):
        prog = 0
        still = []
        for cn in unass:
            votes = collections.Counter()
            for pin, conns in cells[cn]["connections"].items():
                for b in conns:
                    if not isinstance(b, int):
                        continue
                    for o in netcells[b]:
                        if o in assign:
                            votes[assign[o]] += 1
            if votes:
                assign[cn] = votes.most_common(1)[0][0]; prog += 1
            else:
                still.append(cn)
        unass = still
        if not prog:
            break

    # ---- tally ----
    tally = collections.defaultdict(collections.Counter)
    for cn, c in cells.items():
        p = assign.get(cn, "<UNATTRIBUTED>")
        t = c["type"]
        if t in mods:                                # a surviving submodule instance
            sub = go(t, frozenset())
            # instance names keep the full sv2v hierarchical path -> attribute EXACTLY
            key = norm(cn.lstrip("\\")) if "." in cn else (p if p != "<UNATTRIBUTED>" else "<TOPLEVEL>")
            for f in ("comb", "seq", "mux", "mem", "membits"):
                tally[key][f] += sub[f]
            tally[key]["subinsts"] += 1
            continue
        if t.startswith(MEM_PREFIXES):
            tally[p]["mem"] += 1
            continue
        if t.startswith(SEQ_PREFIXES):
            tally[p]["seq"] += 1
        else:
            tally[p]["comb"] += 1
            if t in MUX_TYPES:
                tally[p]["mux"] += 1

    # ---- roll to requested depth ----
    roll = collections.defaultdict(collections.Counter)
    for p, c in tally.items():
        key = ".".join(p.split(".")[:depth]) if p != "<UNATTRIBUTED>" else p
        roll[key].update(c)

    TC = sum(c["comb"] for c in roll.values())
    TS = sum(c["seq"] for c in roll.values())
    print("### attributed: comb=%d seq=%d mux=%d mem=%d membits=%d  (unattributed cells=%d)"
          % (TC, TS, sum(c["mux"] for c in roll.values()), sum(c["mem"] for c in roll.values()),
             sum(c["membits"] for c in roll.values()), len(unass)))
    print()
    hdr = "%-62s %9s %8s %8s %6s %6s %5s %9s %6s" % ("hierarchy path", "comb", "seq", "mux", "mux%", "seq%", "mem", "membits", "%tot")
    print(hdr); print("-" * len(hdr))
    for p, c in sorted(roll.items(), key=lambda kv: -(kv[1]["comb"] + kv[1]["seq"])):
        tot = c["comb"] + c["seq"]
        if tot == 0 and c["mem"] == 0:
            continue
        print("%-62s %9d %8d %8d %5.1f%% %5.1f%% %5d %9d %5.1f%%" % (
            p[:62], c["comb"], c["seq"], c["mux"],
            100.0*c["mux"]/c["comb"] if c["comb"] else 0.0,
            100.0*c["seq"]/tot if tot else 0.0, c["mem"], c["membits"],
            100.0*tot/(TC+TS)))


if __name__ == "__main__":
    main()
