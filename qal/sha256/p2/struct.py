#!/usr/bin/env python3
"""STATIC structure of the remapped netlist.  Reads the COMMITTED Phase-1 output
syn/sw_nand_sc_resyn2.v (161 cells, {inv,nand2}) with the SAME levelisation rule as
the committed levelize_mapped.py, and reports what a QAL wave pipeline actually has
to carry: per-bank cell lists, per-cell fanout, and -- the thing eight identical
inverters can never show -- the SIGNAL LIFETIME (how many beats a value must stay
valid because a later bank consumes it)."""
import collections, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SYN = os.path.join(HERE, "..", "syn")
OUTPINS = ("X", "Y")


def parse(path):
    src = open(path).read()
    body = src[src.index("module sha_slice("):]
    body = body[:body.index("endmodule")]
    pin, outp = set(), set()
    for kind, S in (("input", pin), ("output", outp)):
        for m in re.finditer(r"^\s*%s\s+(?:\[(\d+):(\d+)\]\s+)?(\\?[\w$.:\[\]]+)\s*;" % kind,
                             body, re.M):
            hi, lo, nm = m.groups()
            if hi is None:
                S.add(nm)
            else:
                for i in range(int(lo), int(hi) + 1):
                    S.add("%s[%d]" % (nm, i))
    cells, drv = {}, {}
    for m in re.finditer(r"^\s*(sg13g2_\w+)\s+(\\?\S+)\s*\((.*?)\);", body, re.M | re.S):
        ct, cn, conns = m.groups()
        pins = {k: v.strip() for k, v in re.findall(r"\.(\w+)\(([^)]*)\)", conns)}
        cells[cn] = (ct, pins)
        for p in OUTPINS:
            if p in pins:
                drv[pins[p]] = cn
    # assigns (yosys can emit `assign out = wire;`)
    alias = dict(re.findall(r"^\s*assign\s+(\S+)\s*=\s*(\S+)\s*;", body, re.M))
    return pin, outp, cells, drv, alias


def levelize(pin, cells, drv):
    lvl = {}
    for start in list(cells):
        st = [start]
        while st:
            k = st[-1]
            if lvl.get(k, 0) > 0:
                st.pop(); continue
            ct, pins = cells[k]
            ins = [v for p, v in pins.items() if p not in OUTPINS]
            pend = [drv[n] for n in ins if n not in pin and n in drv
                    and lvl.get(drv[n], 0) == 0]
            if pend:
                st.extend(pend); continue
            lvl[k] = 1 + max([lvl[drv[n]] for n in ins
                              if n not in pin and n in drv] or [0])
            st.pop()
    return lvl


def main():
    path = os.path.join(SYN, sys.argv[1] if len(sys.argv) > 1 else "sw_nand_sc_resyn2.v")
    pin, outp, cells, drv, alias = parse(path)
    lvl = levelize(pin, cells, drv)
    D = max(lvl.values())
    banks = collections.defaultdict(list)
    for c, l in sorted(lvl.items()):
        banks[l].append(c)

    # fanout of every cell output, counted as GATE INPUTS driven inside the block
    fan = collections.Counter()
    for cn, (ct, pins) in cells.items():
        for p, n in pins.items():
            if p not in OUTPINS and n in drv:
                fan[drv[n]] += 1
    # a primary output that is also consumed internally still needs its own pad load

    # SIGNAL LIFETIME: for each cell, the deepest consumer level minus its own
    lifetime = {}
    for cn, (ct, pins) in cells.items():
        for p, n in pins.items():
            if p in OUTPINS:
                continue
            if n in drv:
                src = drv[n]
                lifetime[src] = max(lifetime.get(src, 0), lvl[cn] - lvl[src])
    for cn in cells:
        lifetime.setdefault(cn, 0)
    # primary-output cells must hold to the end of the block
    for cn, (ct, pins) in cells.items():
        for p, n in pins.items():
            if p in OUTPINS and (n in outp or alias.get(n) in outp or
                                 any(alias.get(o) == n for o in outp)):
                lifetime[cn] = max(lifetime[cn], D - lvl[cn])

    prof = [len(banks[l]) for l in range(1, D + 1)]
    types = {l: dict(collections.Counter(cells[c][0] for c in banks[l]))
             for l in range(1, D + 1)}
    # devices / width per bank (PDK: inv_1 = 2 dev, nand2_1 = 4 dev)
    out = dict(
        netlist=os.path.basename(path), cells=len(cells), depth=D,
        profile=prof, spread="%d:1" % (max(prof) // max(1, min(prof))),
        types_by_bank=types,
        cell_type_hist=dict(collections.Counter(ct for ct, _ in cells.values())),
        fanout_hist=dict(collections.Counter(fan[c] for c in cells)),
        max_fanout=max(fan.values()) if fan else 0,
        lifetime_hist=dict(collections.Counter(lifetime.values())),
        max_lifetime=max(lifetime.values()),
        lifetime_by_bank={l: max([lifetime[c] for c in banks[l]]) for l in range(1, D + 1)},
        cells_by_bank={l: [[c, cells[c][0], fan[c], lifetime[c]] for c in banks[l]]
                       for l in range(1, D + 1)},
        n_primary_inputs=len(pin), n_primary_outputs=len(outp),
    )
    json.dump(out, open(os.path.join(HERE, "STRUCT_%s.json" %
                                     os.path.basename(path).replace(".v", "")), "w"),
              indent=1)
    print("netlist   ", out["netlist"])
    print("cells     ", out["cells"], " depth", D, " profile", prof)
    print("types     ", out["cell_type_hist"])
    print("fanout    ", sorted(out["fanout_hist"].items()), "max", out["max_fanout"])
    print("LIFETIME  ", sorted(out["lifetime_hist"].items()), "MAX", out["max_lifetime"])
    print("lifetime/bank", out["lifetime_by_bank"])
    for l in range(1, D + 1):
        print("  bank %2d  n=%-3d %s" % (l, len(banks[l]), types[l]))


if __name__ == "__main__":
    main()
