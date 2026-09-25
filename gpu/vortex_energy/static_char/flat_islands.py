#!/usr/bin/env python3
"""Per-island STATIC vector from the FULLY FLATTENED, in-context Vortex netlist.

After `flatten`, yosys prefixes every cell name with its instance path, so each
gate carries its exact RTL hierarchy location -- no attribution heuristic needed,
and every cell is parameterised exactly as the design instantiates it.

Per island reports: comb / seq / mem cell counts, MUX share, sequential fraction,
combinational logic depth D, the per-level bank-population histogram (the QAL
input), and whether the register-to-register dependency graph is FEED-FORWARD
(map_ncl_struct.py --reg qdi legal) or CYCLIC (qdi raises at :342; only the
matched-delay --reg desync applies).
"""
import json, sys, collections, re

SEQ_PREFIXES = ("$_DFF", "$_SDFF", "$_DLATCH", "$_ALDFF", "$_DFFSR")
MUX_TYPES = ("$_MUX_", "$_MUX4_", "$_MUX8_", "$_MUX16_", "$_NMUX_")
MEM_PREFIXES = ("$mem", "$memrd", "$memwr", "$meminit")
OUT_PINS = ("Y", "Q", "DATA", "RD_DATA")


def norm(p):
    p = re.sub(r"\[[0-9]+\]", "", p)
    return ".".join(x for x in p.split(".") if not re.fullmatch(r"genblk\d*", x))


def cell_path(cn):
    """Hierarchy path of a flattened cell.

    yosys `flatten` renames a pulled-up cell to  $flatten\\<inst.path>.<leafname>
    (with '\\' escapes before components needing them). Cells that were ALREADY in
    the top module keep a bare $auto$... name and carry no path -> return None so
    the caller falls back to net-name attribution for those.
    """
    if cn.startswith("$flatten\\"):
        s = cn[len("$flatten\\"):]
    elif cn.startswith("\\"):
        s = cn[1:]
    else:
        return None
    s = s.replace("\\", "")
    keep = []
    for p in s.split("."):
        if p.startswith("$"):
            break
        keep.append(p)
    return norm(".".join(keep)) if keep else None


def profile(cells, sel_names):
    sel = {cn: cells[cn] for cn in sel_names}
    drv, boundary = {}, set()
    comb, seq, nmem = {}, {}, 0
    for cn, c in sel.items():
        t = c["type"]
        if t.startswith(SEQ_PREFIXES):
            seq[cn] = c
            for b in c["connections"].get("Q", []):
                if isinstance(b, int): boundary.add(b)
        elif t.startswith(MEM_PREFIXES):
            nmem += 1
            for pin in ("RD_DATA", "DATA"):
                for b in c["connections"].get(pin, []):
                    if isinstance(b, int): boundary.add(b)
        else:
            comb[cn] = c
            for b in c["connections"].get("Y", []):
                if isinstance(b, int): drv[b] = cn

    lvl, color, loops = {}, collections.defaultdict(int), set()
    GREY, BLACK = 1, 2

    def run(start):
        stack = [(start, False)]
        while stack:
            n, done = stack.pop()
            if done:
                best = -1
                for pin, cc in comb[n]["connections"].items():
                    if pin in OUT_PINS: continue
                    for b in cc:
                        if isinstance(b, int) and b not in boundary:
                            d = drv.get(b)
                            if d is not None and d in lvl: best = max(best, lvl[d])
                lvl[n] = best + 1; color[n] = BLACK; continue
            if color[n] == BLACK: continue
            if color[n] == GREY:
                loops.add(n); lvl.setdefault(n, 0); color[n] = BLACK; continue
            color[n] = GREY; stack.append((n, True))
            for pin, cc in comb[n]["connections"].items():
                if pin in OUT_PINS: continue
                for b in cc:
                    if isinstance(b, int) and b not in boundary:
                        d = drv.get(b)
                        if d is not None and color[d] != BLACK: stack.append((d, False))

    for n in comb:
        if color[n] != BLACK: run(n)

    reg_of_q, reg_d = {}, {}
    for cn, c in seq.items():
        for b in c["connections"].get("Q", []):
            if isinstance(b, int): reg_of_q[b] = cn
        reg_d[cn] = [b for b in c["connections"].get("D", []) if isinstance(b, int)]

    def deps(dn):
        seen, st, rs = set(), list(dn), set()
        while st:
            n = st.pop()
            if not isinstance(n, int): continue
            if n in reg_of_q: rs.add(reg_of_q[n]); continue
            if n in seen: continue
            seen.add(n)
            cn = drv.get(n)
            if cn is None: continue
            for pin, cc in comb[cn]["connections"].items():
                if pin not in OUT_PINS: st.extend(cc)
        return rs

    D = {r: deps(reg_d[r]) for r in reg_d}
    stage, cyc = {}, set()
    sys.setrecursionlimit(300000)

    def st_(r, path):
        if r in stage: return stage[r]
        if r in path: cyc.add(r); stage[r] = 0; return 0
        s = 0 if not D[r] else 1 + max(st_(x, path | {r}) for x in D[r])
        stage[r] = s; return s

    for r in reg_d:
        if r not in stage: st_(r, frozenset())

    hist = collections.Counter(lvl.values())
    mix = collections.Counter(c["type"] for c in sel.values())
    return dict(ncomb=len(comb), nseq=len(seq), nmem=nmem,
                D=(max(hist) + 1 if hist else 0), hist=dict(sorted(hist.items())),
                loops=len(loops), cyclic=bool(cyc), ncyc=len(cyc),
                mux=sum(n for t, n in mix.items() if t in MUX_TYPES),
                maxstage=max(stage.values()) if stage else 0,
                mix=dict(collections.Counter(mix).most_common(8)))


def show(tag, r):
    h = r["hist"]
    tot = sum(h.values())
    print("== %s" % tag)
    if not tot:
        print("   (empty)"); return
    print("   comb=%-7d seq=%-6d mem=%-3d mux=%-7d (%.1f%% of comb)  seq_frac=%.1f%%"
          % (r["ncomb"], r["nseq"], r["nmem"], r["mux"],
             100.0*r["mux"]/r["ncomb"], 100.0*r["nseq"]/(r["ncomb"]+r["nseq"])))
    print("   logic depth D=%d   comb-loop cells=%d   reg graph=%s (regs in cycles=%d, max reg-to-reg stage=%d)"
          % (r["D"], r["loops"], "CYCLIC -> QDI-pipeline ILLEGAL, desync only" if r["cyclic"]
             else "FEED-FORWARD -> QDI pipeline legal", r["ncyc"], r["maxstage"]))
    ks = sorted(h)
    comp = " ".join("L%d:%d" % (k, h[k]) for k in ks[:14])
    if len(ks) > 14: comp += "  ... " + " ".join("L%d:%d" % (k, h[k]) for k in ks[-6:])
    print("   bank population: " + comp)
    small = sum(n for n in h.values() if n <= 4)
    mid = sum(n for n in h.values() if 4 < n < 32)
    big = sum(n for n in h.values() if n >= 32)
    print("   QAL bank fill: N<=4 %d cells (%.2f%%, FATAL 6-9x) | 4<N<32 %d (%.2f%%) | N>=32 %d (%.2f%%, 25-37%% tax)"
          % (small, 100.0*small/tot, mid, 100.0*mid/tot, big, 100.0*big/tot))
    print("   mix:", r["mix"])


def main():
    path, top = sys.argv[1], sys.argv[2]
    mods = json.load(open(path))["modules"]
    m = mods[top]
    cells = {k: v for k, v in m["cells"].items() if v["type"] != "$scopeinfo"}
    print("### flattened cells in %s: %d" % (top, len(cells)))

    # --- attribution: flatten-name path where present, else net-name fallback ---
    paths = {cn: cell_path(cn) for cn in cells}
    named = sum(1 for p in paths.values() if p)
    print("### cells with a $flatten hierarchy path: %d ; needing net-name fallback: %d"
          % (named, len(cells) - named))

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

    todo = [cn for cn, p in paths.items() if not p]
    for cn in todo:
        ps = {bitpath[b] for pin, cc in cells[cn]["connections"].items() for b in cc
              if isinstance(b, int) and b in bitpath}
        a = lcp(ps)
        if a:
            paths[cn] = a
    netcells = collections.defaultdict(list)
    for cn, c in cells.items():
        for pin, cc in c["connections"].items():
            for b in cc:
                if isinstance(b, int):
                    netcells[b].append(cn)
    for _ in range(10):
        rest, prog = [], 0
        for cn in [c for c in todo if not paths[c]]:
            v = collections.Counter()
            for pin, cc in cells[cn]["connections"].items():
                for b in cc:
                    if isinstance(b, int):
                        for o in netcells[b]:
                            if paths.get(o): v[paths[o]] += 1
            if v:
                paths[cn] = v.most_common(1)[0][0]; prog += 1
            else:
                rest.append(cn)
        if not prog: break
    unattr = sum(1 for p in paths.values() if not p)
    print("### unattributed after fallback: %d (%.2f%%)" % (unattr, 100.0*unattr/len(cells)))

    byprefix = collections.defaultdict(list)
    for cn, p in paths.items():
        byprefix[p or "<UNATTRIBUTED>"].append(cn)

    P = "clusters.cluster.sockets.socket."
    islands = [
        ("WHOLE CHIP", ""),
        ("CORE (whole)", P + "cores.core"),
        ("  core.execute (whole)", P + "cores.core.execute"),
        ("    execute.alu_unit", P + "cores.core.execute.alu_unit"),
        ("      alu_unit.alu_int", P + "cores.core.execute.alu_unit.alu_int"),
        ("      alu_unit.muldiv", P + "cores.core.execute.alu_unit.muldiv"),
        ("    execute.fpu_unit (fpnew)", P + "cores.core.execute.fpu_unit"),
        ("    execute.lsu_unit", P + "cores.core.execute.lsu_unit"),
        ("    execute.sfu_unit", P + "cores.core.execute.sfu_unit"),
        ("  core.issue", P + "cores.core.issue"),
        ("  core.schedule", P + "cores.core.schedule"),
        ("  core.fetch", P + "cores.core.fetch"),
        ("  core.decode", P + "cores.core.decode"),
        ("  core.commit", P + "cores.core.commit"),
        ("  core.lmem_unit", P + "cores.core.lmem_unit"),
        ("  core.mem_coalescer", P + "cores.core.mem_coalescer"),
        ("DCACHE", P + "dcache"),
        ("ICACHE", P + "icache"),
        ("SOCKET mem_arb", P + "mem_arb"),
        ("L2", "clusters.cluster.l2cache"),
        ("L3", "l3cache"),
    ]
    for tag, pref in islands:
        sel = [cn for p, lst in byprefix.items() if p.startswith(pref) for cn in lst] if pref \
              else list(cells)
        if not sel:
            print("== %s\n   (no cells matched prefix %r)\n" % (tag, pref)); continue
        show(tag, profile(cells, sel))
        print()


if __name__ == "__main__":
    main()
