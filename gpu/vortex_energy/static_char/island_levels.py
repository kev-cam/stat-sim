#!/usr/bin/env python3
"""Per-ISLAND levelization (QAL bank-population profile) of the logic sv2v INLINED
into the top module, plus per-island register-cycle legality for QDI pipelining.

Scope note (honesty): this levelizes ONLY the primitives that live directly in the
top module -- i.e. every block sv2v inlined (alu_int, decode, schedule, commit,
fetch, branch glue, cache_bypass, arbiter glue ...). Cells inside modules that
SURVIVED as modules (fpnew, VX_multiplier, VX_cache_bank, VX_stream_arb ...) are
treated as island boundaries here and are levelized separately, standalone.

Level convention matches stat-sim/qal/synth/threeway/work/levels.json (validated:
this code reproduces its 48/22/19/3/2/4/2/3/1/1, D=10 exactly for sha_slice).
"""
import json, sys, collections, re

SEQ_PREFIXES = ("$_DFF", "$_SDFF", "$_DLATCH", "$_ALDFF", "$_DFFSR")
MUX_TYPES = ("$_MUX_", "$_MUX4_", "$_MUX8_", "$_MUX16_", "$_NMUX_")
MEM_PREFIXES = ("$mem", "$memrd", "$memwr", "$meminit")
OUT_PINS = ("Y", "Q", "DATA", "RD_DATA")


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
        if not p:
            continue
        for b in nn["bits"]:
            if isinstance(b, int) and b not in bitpath:
                bitpath[b] = p

    def lcp(ps):
        if not ps:
            return None
        sp = [p.split(".") for p in ps]
        out = []
        for i in range(min(len(s) for s in sp)):
            t = sp[0][i]
            if all(s[i] == t for s in sp):
                out.append(t)
            else:
                break
        return ".".join(out) if out else None

    assign, unass = {}, []
    for cn, c in cells.items():
        if c["type"] in mods:
            assign[cn] = norm(cn.lstrip("\\")) if "." in cn else "<TOP>"
            continue
        ps = {bitpath[b] for pin, cc in c["connections"].items() for b in cc
              if isinstance(b, int) and b in bitpath}
        a = lcp(ps)
        if a:
            assign[cn] = a
        else:
            unass.append(cn)

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
                            if o in assign:
                                v[assign[o]] += 1
            if v:
                assign[cn] = v.most_common(1)[0][0]; prog += 1
            else:
                still.append(cn)
        unass = still
        if not prog:
            break
    for cn in unass:
        assign[cn] = "<UNATTRIBUTED>"
    return mods, cells, assign


def island_profile(cells, assign, prefix, mods):
    """Levelize only the top-level primitives attributed under `prefix`."""
    sel = {cn: c for cn, c in cells.items()
           if assign.get(cn, "").startswith(prefix) and c["type"] not in mods}
    drv, boundary = {}, set()
    comb, seq = {}, {}
    for cn, c in sel.items():
        t = c["type"]
        if t.startswith(SEQ_PREFIXES):
            seq[cn] = c
            for b in c["connections"].get("Q", []):
                if isinstance(b, int):
                    boundary.add(b)
        elif t.startswith(MEM_PREFIXES):
            for pin in ("RD_DATA", "DATA"):
                for b in c["connections"].get(pin, []):
                    if isinstance(b, int):
                        boundary.add(b)
        else:
            comb[cn] = c
            for b in c["connections"].get("Y", []):
                if isinstance(b, int):
                    drv[b] = cn

    lvl, color = {}, collections.defaultdict(int)
    GREY, BLACK = 1, 2
    loops = set()

    def run(start):
        stack = [(start, False)]
        while stack:
            n, done = stack.pop()
            if done:
                best = -1
                for pin, cc in comb[n]["connections"].items():
                    if pin in OUT_PINS:
                        continue
                    for b in cc:
                        if isinstance(b, int) and b not in boundary:
                            d = drv.get(b)
                            if d is not None and d in lvl:
                                best = max(best, lvl[d])
                lvl[n] = best + 1; color[n] = BLACK; continue
            if color[n] == BLACK:
                continue
            if color[n] == GREY:
                loops.add(n); lvl.setdefault(n, 0); color[n] = BLACK; continue
            color[n] = GREY; stack.append((n, True))
            for pin, cc in comb[n]["connections"].items():
                if pin in OUT_PINS:
                    continue
                for b in cc:
                    if isinstance(b, int) and b not in boundary:
                        d = drv.get(b)
                        if d is not None and color[d] != BLACK:
                            stack.append((d, False))

    for n in comb:
        if color[n] != BLACK:
            run(n)

    # register-to-register dependency cycles (QDI pipeline legality)
    reg_of_q, reg_d = {}, {}
    for cn, c in seq.items():
        for b in c["connections"].get("Q", []):
            if isinstance(b, int):
                reg_of_q[b] = cn
        reg_d[cn] = [b for b in c["connections"].get("D", []) if isinstance(b, int)]

    def deps(dn):
        seen, st, rs = set(), list(dn), set()
        while st:
            n = st.pop()
            if not isinstance(n, int):
                continue
            if n in reg_of_q:
                rs.add(reg_of_q[n]); continue
            if n in seen:
                continue
            seen.add(n)
            cn = drv.get(n)
            if cn is None:
                continue
            for pin, cc in comb[cn]["connections"].items():
                if pin not in OUT_PINS:
                    st.extend(cc)
        return rs

    D = {r: deps(reg_d[r]) for r in reg_d}
    stage, cyc = {}, set()
    sys.setrecursionlimit(200000)

    def st_(r, path):
        if r in stage:
            return stage[r]
        if r in path:
            cyc.add(r); stage[r] = 0; return 0
        s = 0 if not D[r] else 1 + max(st_(x, path | {r}) for x in D[r])
        stage[r] = s
        return s

    for r in reg_d:
        if r not in stage:
            st_(r, frozenset())

    hist = collections.Counter(lvl.values())
    mix = collections.Counter(c["type"] for c in sel.values())
    return dict(ncomb=len(comb), nseq=len(seq), D=(max(hist) + 1 if hist else 0),
                hist=dict(sorted(hist.items())), loops=len(loops),
                cyclic=bool(cyc), ncyc=len(cyc),
                mux=sum(n for t, n in mix.items() if t in MUX_TYPES),
                maxstage=max(stage.values()) if stage else 0, mix=dict(mix))


def show(tag, r):
    h = r["hist"]
    if not h:
        print("%-42s  (no top-level comb cells)" % tag); return
    tot = sum(h.values())
    mx = max(h.values())
    print("== %s" % tag)
    print("   comb=%d seq=%d D=%d mux=%d (%.1f%%)  reg-graph=%s (cyc regs=%d, max stage=%d) comb-loop cells=%d"
          % (r["ncomb"], r["nseq"], r["D"], r["mux"], 100.0*r["mux"]/r["ncomb"] if r["ncomb"] else 0,
             "CYCLIC" if r["cyclic"] else "feed-forward", r["ncyc"], r["maxstage"], r["loops"]))
    line = []
    for k in sorted(h):
        line.append("L%d:%d" % (k, h[k]))
    print("   bank population: " + " ".join(line))
    small = sum(n for n in h.values() if n <= 4)
    big = sum(n for n in h.values() if n >= 32)
    print("   levels N<=4 (QAL-fatal): %d lvls / %d cells (%.1f%%) | levels N>=32 (amortizing): %d lvls / %d cells (%.1f%%)"
          % (sum(1 for n in h.values() if n <= 4), small, 100.0*small/tot,
             sum(1 for n in h.values() if n >= 32), big, 100.0*big/tot))


if __name__ == "__main__":
    mods, cells, assign = build(sys.argv[1], sys.argv[2])
    P = "clusters.cluster.sockets.socket."
    islands = [
        ("core.execute.alu_unit.alu_int (ALU_INT)", P + "cores.core.execute.alu_unit.alu_int"),
        ("core.execute.alu_unit (whole)", P + "cores.core.execute.alu_unit"),
        ("core.execute.lsu_unit", P + "cores.core.execute.lsu_unit"),
        ("core.execute.sfu_unit", P + "cores.core.execute.sfu_unit"),
        ("core.execute.fpu_unit", P + "cores.core.execute.fpu_unit"),
        ("core.execute (whole)", P + "cores.core.execute"),
        ("core.schedule", P + "cores.core.schedule"),
        ("core.fetch", P + "cores.core.fetch"),
        ("core.decode", P + "cores.core.decode"),
        ("core.issue", P + "cores.core.issue"),
        ("core.commit", P + "cores.core.commit"),
        ("core.mem_coalescer", P + "cores.core.mem_coalescer"),
        ("core.lmem_unit", P + "cores.core.lmem_unit"),
        ("core (WHOLE CORE)", P + "cores.core"),
        ("socket.dcache", P + "dcache"),
        ("socket.icache", P + "icache"),
        ("socket.mem_arb", P + "mem_arb"),
        ("cluster.l2cache", "clusters.cluster.l2cache"),
        ("l3cache", "l3cache"),
    ]
    for tag, pref in islands:
        show(tag, island_profile(cells, assign, pref, mods))
        print()
