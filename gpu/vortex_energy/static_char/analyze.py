#!/usr/bin/env python3
"""Static per-module characterization from a HIERARCHICAL yosys JSON netlist.

A cell is a SUBMODULE INSTANCE iff its type names a module in the design
(yosys specialisations are named "$paramod$<hash>\\NAME" or "$paramod\\NAME\\P=..",
so the leading '$' does NOT mean primitive). Everything else starting with '$'
is a primitive gate / memory.

Reports per BASE module (specialisations aggregated): own cell counts, primitive
mix, MUX share, sequential fraction, memory macros, port widths; plus a
whole-subtree rollup (own + all descendants x instance count).
"""
import json, sys, collections, re

SEQ_PREFIXES = ("$_DFF", "$_SDFF", "$_DLATCH", "$_ALDFF", "$_DFFSR")
MUX_TYPES = ("$_MUX_", "$_MUX4_", "$_MUX8_", "$_MUX16_", "$_NMUX_")
MEM_PREFIXES = ("$mem", "$memrd", "$memwr", "$meminit")
IGNORE = ("$scopeinfo",)


def base_name(t):
    """Strip yosys parameter specialisation to the RTL module name."""
    m = re.match(r"^\$paramod\$[0-9a-f]+\\(.+)$", t)
    if m:
        return m.group(1)
    m = re.match(r"^\$paramod\\([^\\]+)\\", t)
    if m:
        return m.group(1)
    return t


def classify(mods):
    stats, tree = {}, {}
    for name, m in mods.items():
        cnt, kids = collections.Counter(), collections.Counter()
        membits = 0
        for c in m.get("cells", {}).values():
            t = c["type"]
            if t in IGNORE:
                continue
            if t in mods:                      # submodule instance
                kids[t] += 1
                continue
            cnt[t] += 1
            if t.startswith("$mem"):
                p = c.get("parameters", {})
                def gi(k):
                    v = p.get(k, 0)
                    if isinstance(v, str):
                        try: return int(v, 2)
                        except ValueError: return 0
                    return int(v)
                membits += gi("SIZE") * gi("WIDTH")
        seq = sum(n for t, n in cnt.items() if t.startswith(SEQ_PREFIXES))
        mux = sum(n for t, n in cnt.items() if t in MUX_TYPES)
        mem = sum(n for t, n in cnt.items() if t.startswith(MEM_PREFIXES))
        gates = sum(n for t, n in cnt.items() if not t.startswith(MEM_PREFIXES))
        comb = gates - seq
        ports = m.get("ports", {})
        inb = sum(len(v["bits"]) for v in ports.values() if v["direction"] == "input")
        outb = sum(len(v["bits"]) for v in ports.values() if v["direction"] == "output")
        widest = max([len(v["bits"]) for v in ports.values()] or [0])
        stats[name] = dict(comb=comb, seq=seq, mux=mux, mem=mem, membits=membits,
                           mix=dict(cnt), in_bits=inb, out_bits=outb,
                           widest_port=widest, nports=len(ports))
        tree[name] = dict(kids)
    return stats, tree


def rollup(stats, tree, top):
    memo = {}
    FIELDS = ("comb", "seq", "mux", "mem", "membits")

    def go(name, path):
        if name in memo:
            return memo[name]
        s = stats.get(name)
        if s is None or name in path:
            return {f: 0 for f in FIELDS} | {"insts": 0}
        tot = {f: s[f] for f in FIELDS} | {"insts": 1}
        for k, n in tree.get(name, {}).items():
            sub = go(k, path | {name})
            for f in tot:
                tot[f] += n * sub[f]
        memo[name] = tot
        return tot

    go(top, frozenset())
    return memo


def main():
    path, top = sys.argv[1], sys.argv[2]
    mods = json.load(open(path))["modules"]
    stats, tree = classify(mods)
    roll = rollup(stats, tree, top)

    # count instances of each specialisation reachable from top
    inst = collections.Counter({top: 1})
    order, seen = [top], {top}
    while order:
        n = order.pop()
        for k, c in tree.get(n, {}).items():
            inst[k] += inst[n] * c
            if k not in seen:
                seen.add(k); order.append(k)

    T = roll[top]
    print("### modules(specialisations)=%d  top=%s" % (len(mods), top))
    print("### WHOLE-DESIGN ROLLUP: comb=%d seq=%d mux=%d memcells=%d membits=%d"
          % (T["comb"], T["seq"], T["mux"], T["mem"], T["membits"]))
    print("### (mux%% of comb = %.1f%% ; seq fraction = %.1f%%)"
          % (100.0*T["mux"]/T["comb"], 100.0*T["seq"]/(T["comb"]+T["seq"])))
    print()

    # aggregate by BASE module name, weighted by instance count
    agg = collections.defaultdict(lambda: collections.Counter())
    spec = collections.defaultdict(int)
    for name, s in stats.items():
        if name not in seen:
            continue
        b = base_name(name)
        n = inst[name]
        spec[b] += 1
        agg[b]["insts"] += n
        for f in ("comb", "seq", "mux", "mem", "membits"):
            agg[b]["tot_" + f] += n * s[f]
        agg[b]["one_comb"] = max(agg[b]["one_comb"], s["comb"])
        agg[b]["one_seq"] = max(agg[b]["one_seq"], s["seq"])
        agg[b]["in_b"] = max(agg[b]["in_b"], s["in_bits"])
        agg[b]["out_b"] = max(agg[b]["out_b"], s["out_bits"])
        agg[b]["wide"] = max(agg[b]["wide"], s["widest_port"])

    hdr = "%-34s %4s %5s %9s %8s %8s %6s %6s %6s %6s %6s" % (
        "base module", "spc", "insts", "tot_comb", "tot_seq", "tot_mux", "mux%",
        "seq%", "mem", "in_b", "out_b")
    print("OWN-LOGIC BY BASE MODULE (own cells only, x instance count; excludes submodules)")
    print(hdr); print("-" * len(hdr))
    for b, a in sorted(agg.items(), key=lambda kv: -(kv[1]["tot_comb"] + kv[1]["tot_seq"])):
        tc, ts, tm = a["tot_comb"], a["tot_seq"], a["tot_mux"]
        if tc + ts + a["tot_mem"] == 0:
            continue
        print("%-34s %4d %5d %9d %8d %8d %5.1f%% %5.1f%% %6d %6d %6d" % (
            b[:34], spec[b], a["insts"], tc, ts, tm,
            100.0*tm/tc if tc else 0.0, 100.0*ts/(tc+ts) if tc+ts else 0.0,
            a["tot_mem"], a["in_b"], a["out_b"]))

    print()
    print("SUBTREE ROLLUP for named hierarchy anchors (own + all descendants):")
    print("%-34s %5s %9s %8s %8s %6s %6s %8s" % ("module", "insts", "sub_comb", "sub_seq", "sub_mux", "mux%", "seq%", "membits"))
    anchors = ["Vortex", "VX_cluster", "VX_socket", "VX_core", "VX_execute", "VX_schedule",
               "VX_fetch", "VX_decode", "VX_issue", "VX_commit", "VX_operands", "VX_scoreboard",
               "VX_alu_unit", "VX_alu_int", "VX_alu_muldiv", "VX_lsu_unit", "VX_lsu_slice",
               "VX_sfu_unit", "VX_csr_unit", "VX_wctl_unit", "VX_fpu_unit", "VX_fpu_fpnew",
               "VX_lmem_unit", "VX_local_mem", "VX_cache_cluster", "VX_cache_wrap", "VX_cache",
               "VX_cache_bank", "VX_mem_coalescer", "VX_mem_scheduler", "VX_dispatch", "VX_ibuffer",
               "VX_split_join", "VX_ipdom_stack", "VX_dcr_data", "fpnew_top", "VX_stream_xbar"]
    byb = collections.defaultdict(list)
    for name in seen:
        byb[base_name(name)].append(name)
    for a in anchors:
        for nm in sorted(byb.get(a, []), key=lambda n: -roll.get(n, {}).get("comb", 0))[:2]:
            r = roll.get(nm)
            if not r:
                continue
            tc, ts, tm = r["comb"], r["seq"], r["mux"]
            print("%-34s %5d %9d %8d %8d %5.1f%% %5.1f%% %8d" % (
                a[:34], inst[nm], tc, ts, tm,
                100.0*tm/tc if tc else 0.0, 100.0*ts/(tc+ts) if tc+ts else 0.0, r["membits"]))


if __name__ == "__main__":
    main()
