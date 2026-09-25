#!/usr/bin/env python3
"""Levelization / bank-population profile + QDI-pipeline legality for a FLATTENED
yosys gate netlist (generic $_AND_/$_OR_/$_XOR_/$_MUX_/$_NOT_ cells).

Matches the convention of stat-sim/qal/synth/threeway/work/levels.json:
  level(cell) = 0 if every input net is a boundary net (primary input, constant,
  register Q, or memory read-data); else 1 + max(level of the comb cells driving it).
  D = max level + 1 ; bylvl = population histogram.

Also computes the register-to-register dependency graph, reporting whether it is
FEED-FORWARD (map_ncl_struct.py --reg qdi is legal) or CYCLIC (qdi raises at
map_ncl_struct.py:342; only --reg desync applies, which re-imports a matched delay).
"""
import json, sys, collections

SEQ_PREFIXES = ("$_DFF", "$_SDFF", "$_DLATCH", "$_ALDFF", "$_DFFSR")
MEM_PREFIXES = ("$mem", "$memrd", "$memwr")
OUT_PINS = ("Y", "Q", "DATA", "RD_DATA")


def is_seq(t):
    return t.startswith(SEQ_PREFIXES)


def is_mem(t):
    return t.startswith(MEM_PREFIXES)


def analyze(path, top):
    m = json.load(open(path))["modules"][top]
    cells = {k: v for k, v in m["cells"].items() if v["type"] != "$scopeinfo"}

    drv = {}            # net -> comb cell name driving it
    boundary = set()    # nets that start a cone (reg Q, mem rd data)
    comb, seq, mem = {}, {}, {}
    for name, c in cells.items():
        t = c["type"]
        if is_seq(t):
            seq[name] = c
            for b in c["connections"].get("Q", []):
                if isinstance(b, int):
                    boundary.add(b)
        elif is_mem(t):
            mem[name] = c
            for pin in ("RD_DATA", "DATA"):
                for b in c["connections"].get(pin, []):
                    if isinstance(b, int):
                        boundary.add(b)
        else:
            comb[name] = c
            for b in c["connections"].get("Y", []):
                if isinstance(b, int):
                    drv[b] = name

    # ---- combinational levelization (iterative, cycle-tolerant) ----
    lvl = {}
    WHITE, GREY, BLACK = 0, 1, 2
    color = collections.defaultdict(int)
    comb_loop_cells = set()

    def level_of(start):
        stack = [(start, False)]
        while stack:
            n, done = stack.pop()
            if done:
                best = -1
                for pin, conns in comb[n]["connections"].items():
                    if pin in OUT_PINS:
                        continue
                    for b in conns:
                        if not isinstance(b, int) or b in boundary:
                            continue
                        d = drv.get(b)
                        if d is not None and d in lvl:
                            best = max(best, lvl[d])
                lvl[n] = best + 1
                color[n] = BLACK
                continue
            if color[n] == BLACK:
                continue
            if color[n] == GREY:            # combinational loop
                comb_loop_cells.add(n)
                lvl.setdefault(n, 0)
                color[n] = BLACK
                continue
            color[n] = GREY
            stack.append((n, True))
            for pin, conns in comb[n]["connections"].items():
                if pin in OUT_PINS:
                    continue
                for b in conns:
                    if not isinstance(b, int) or b in boundary:
                        continue
                    d = drv.get(b)
                    if d is not None and color[d] != BLACK:
                        stack.append((d, False))

    for n in comb:
        if color[n] != BLACK:
            level_of(n)

    bylvl = collections.Counter(lvl.values())
    D = (max(bylvl) + 1) if bylvl else 0

    # ---- register-to-register dependency graph (QDI pipeline legality) ----
    reg_of_q, reg_d = {}, {}
    for name, c in seq.items():
        for b in c["connections"].get("Q", []):
            if isinstance(b, int):
                reg_of_q[b] = name
        dc = c["connections"].get("D", [])
        reg_d[name] = [b for b in dc if isinstance(b, int)]

    def deps_of(dnets):
        seen, stack, regs = set(), list(dnets), set()
        while stack:
            n = stack.pop()
            if not isinstance(n, int):
                continue
            if n in reg_of_q:
                regs.add(reg_of_q[n]); continue
            if n in seen:
                continue
            seen.add(n)
            cn = drv.get(n)
            if cn is None:
                continue
            for pin, conns in comb[cn]["connections"].items():
                if pin in OUT_PINS:
                    continue
                stack.extend(conns)
        return regs

    deps = {r: deps_of(reg_d[r]) for r in reg_d}
    stage, cyc = {}, []

    def st(r, path):
        if r in stage:
            return stage[r]
        if r in path:
            cyc.append(r)
            stage[r] = 0
            return 0
        s = 0 if not deps[r] else 1 + max(st(x, path | {r}) for x in deps[r])
        stage[r] = s
        return s

    sys.setrecursionlimit(100000)
    for r in reg_d:
        if r not in stage:
            st(r, frozenset())

    stages = collections.Counter(stage.values())
    return dict(top=top, ncomb=len(comb), nseq=len(seq), nmem=len(mem),
                D=D, bylvl={k: bylvl[k] for k in sorted(bylvl)},
                comb_loops=len(comb_loop_cells),
                reg_cyclic=bool(cyc), n_cyc_regs=len(set(cyc)),
                reg_stages={k: stages[k] for k in sorted(stages)},
                max_reg_stage=(max(stages) if stages else 0),
                mix=dict(collections.Counter(c["type"] for c in cells.values())))


if __name__ == "__main__":
    r = analyze(sys.argv[1], sys.argv[2])
    hist = r["bylvl"]
    print("TOP=%s  comb=%d seq=%d mem=%d  D=%d  comb_loop_cells=%d"
          % (r["top"], r["ncomb"], r["nseq"], r["nmem"], r["D"], r["comb_loops"]))
    print("  reg graph: %s ; regs in cycles=%d ; max reg-to-reg stage=%d"
          % ("CYCLIC (qdi pipeline ILLEGAL -> desync only)" if r["reg_cyclic"]
             else "FEED-FORWARD (qdi pipeline legal)", r["n_cyc_regs"], r["max_reg_stage"]))
    print("  bank population by level:")
    tot = sum(hist.values())
    run = 0
    for k in sorted(hist):
        n = hist[k]; run += n
        bar = "#" * min(60, max(1, n * 60 // max(hist.values())))
        print("    L%-3d %7d  (%5.2f%%, cum %5.1f%%)  %s" % (k, n, 100.0*n/tot, 100.0*run/tot, bar))
    tails = sum(n for k, n in hist.items() if n <= 4)
    lv = sorted(hist)
    print("  levels with population <=4 (QAL-fatal tails): %d of %d levels, %d cells (%.2f%% of comb)"
          % (sum(1 for k in lv if hist[k] <= 4), len(lv), tails, 100.0*tails/tot))
    print("  levels with population >=32 (QAL-amortizing): %d of %d levels, %d cells (%.2f%%)"
          % (sum(1 for k in lv if hist[k] >= 32), len(lv),
             sum(n for n in hist.values() if n >= 32),
             100.0*sum(n for n in hist.values() if n >= 32)/tot))
    print("  primitive mix:", dict(sorted(r["mix"].items(), key=lambda kv: -kv[1])))
    print("  reg stage histogram:", r["reg_stages"])
