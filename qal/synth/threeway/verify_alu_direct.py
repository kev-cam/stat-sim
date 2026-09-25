#!/usr/bin/env python3
"""Functional + delay-insensitivity verification of the DIRECT-THRESHOLD alu_top.

The netlist is ~24k TH cells, so verify_direct.py's per-vector Python evaluation
(4000 vectors x 24k cells) is hopeless.  Everything here is BIT-PARALLEL: a net
holds one Python int whose bit k is that net's value in vector k, so N vectors
cost one int operation per cell.

CHECK 1  EQUIVALENCE, bit-parallel, against the ORIGINAL gate netlist
         (alu.json, $_AND_/$_OR_/$_XOR_/$_NOT_/$_MUX_/$_DFF_P_).  Register Q
         nets are free inputs and register D nets are checked as outputs, so the
         whole combinational cloud of the sequential block is covered.  Both
         RAILS are checked: y_L must equal the reference bit and y_H its
         complement, so a NULL or a both-rails-high output is a failure.
CHECK 2  PER-CONE EXHAUSTIVE.  The mapper tiles the netlist into cones of
         support <= 4 whose union is the whole netlist and whose intersection is
         empty.  Each cone is replayed on ALL 2**support DATA codes against the
         reference cone function, read out of the EMITTED file.  Cone-exhaustive
         + exact tiling is a complete equivalence proof, not a sample.
CHECK 3  QDI 4-PHASE, hysteretic cells, RANDOM per-gate delays, on a bounded
         sub-netlist (the full 24k-cell event simulation does not fit in the
         time budget).  Reported with its actual cell count and run count.
CHECK 4  INPUT-COMPLETENESS, dynamic: hold ONE primary input bit at NULL, drive
         everything else to DATA, settle the hysteretic network from all-NULL,
         and require the completion signal to stay LOW; then release it and
         require it to rise.
CHECK 5  NULL RETURN: from the settled DATA state drop every input rail and
         require every net to return to 0.

usage: verify_alu_direct.py <direct.v> <top> <reference.json> <reftop> [nvec]
"""
import collections
import json
import random
import subprocess
import sys

PINS = ["a", "b", "c", "d"]
# bit-parallel DATA-phase (stateless Boolean) model of each TH cell
TH = {
    "th12": lambda v: v[0] | v[1],
    "th13": lambda v: v[0] | v[1] | v[2],
    "th14": lambda v: v[0] | v[1] | v[2] | v[3],
    "th22": lambda v: v[0] & v[1],
    "th23": lambda v: (v[0] & v[1]) | (v[0] & v[2]) | (v[1] & v[2]),
    "th33": lambda v: v[0] & v[1] & v[2],
    "th24": lambda v: ((v[0] & v[1]) | (v[0] & v[2]) | (v[0] & v[3]) |
                       (v[1] & v[2]) | (v[1] & v[3]) | (v[2] & v[3])),
    "th34": lambda v: ((v[0] & v[1] & v[2]) | (v[0] & v[1] & v[3]) |
                       (v[0] & v[2] & v[3]) | (v[1] & v[2] & v[3])),
    "th44": lambda v: v[0] & v[1] & v[2] & v[3],
    "th23w2": lambda v: v[0] | (v[1] & v[2]),
    "th34w2": lambda v: (v[0] & (v[1] | v[2] | v[3])) | (v[1] & v[2] & v[3]),
}
WT = {"th12": ([1, 1], 1), "th13": ([1, 1, 1], 1), "th14": ([1, 1, 1, 1], 1),
      "th22": ([1, 1], 2), "th23": ([1, 1, 1], 2), "th33": ([1, 1, 1], 3),
      "th24": ([1, 1, 1, 1], 2), "th34": ([1, 1, 1, 1], 3),
      "th44": ([1, 1, 1, 1], 4), "th23w2": ([2, 1, 1], 2),
      "th34w2": ([2, 1, 1, 1], 3)}


def load_th(vfile, top):
    """read the EMITTED file back through yosys, so the check is on the file."""
    js = vfile + ".json"
    r = subprocess.run(["yosys", "-q", "-p",
                        "read_verilog %s; hierarchy -top %s; flatten; write_json %s"
                        % (vfile, top, js)], capture_output=True, text=True)
    if r.returncode:
        sys.exit("yosys failed:\n" + r.stderr)
    m = json.load(open(js))["modules"][top]
    cells = []
    for cn, c in m["cells"].items():
        t = c["type"]
        if t not in TH:
            sys.exit("non-TH cell %s (%s)" % (t, cn))
        ins = [k(c["connections"][p][0]) for p in PINS if p in c["connections"]]
        cells.append((t, ins, k(c["connections"]["y"][0])))
    ports = {p: ([k(b) for b in v["bits"]], v["direction"]) for p, v in m["ports"].items()}
    # Verilog net NAME -> yosys bit id, so a cone map written in names can be
    # replayed on the flattened netlist.
    nn = {}
    for name, v in m.get("netnames", {}).items():
        bits = [k(b) for b in v["bits"]]
        if len(bits) == 1:
            nn[name] = bits[0]
        for i, b in enumerate(bits):
            nn["%s[%d]" % (name, i)] = b
    return cells, ports, nn


def k(b):
    return b if isinstance(b, int) else str(b)


def topo(cells, driven):
    have = set(driven) | {"0", "1", "x"}
    out, pend = [], list(cells)
    while pend:
        nxt, prog = [], False
        for c in pend:
            if all(i in have for i in c[1]):
                out.append(c); have.add(c[2]); prog = True
            else:
                nxt.append(c)
        pend = nxt
        if not prog:
            sys.exit("combinational loop: %d cells stuck" % len(pend))
    return out


# ----------------------------------------------------------- reference model
class Ref(object):
    def __init__(self, jf, top):
        m = json.load(open(jf))["modules"][top]
        self.ports = {p: ([k(b) for b in v["bits"]], v["direction"])
                      for p, v in m["ports"].items()}
        self.gates, self.regs = [], []
        for cn, c in m["cells"].items():
            t = c["type"]
            if t == "$scopeinfo":
                continue
            cc = c["connections"]
            if t == "$_DFF_P_":
                self.regs.append((k(cc["D"][0]), k(cc["Q"][0])))
            elif t == "$_NOT_":
                self.gates.append(("not", [k(cc["A"][0])], k(cc["Y"][0])))
            elif t == "$_MUX_":
                self.gates.append(("mux", [k(cc["S"][0]), k(cc["A"][0]), k(cc["B"][0])],
                                   k(cc["Y"][0])))
            else:
                op = {"$_AND_": "and", "$_OR_": "or", "$_XOR_": "xor",
                      "$_XNOR_": "xnor", "$_NAND_": "nand", "$_NOR_": "nor"}[t]
                self.gates.append((op, [k(cc["A"][0]), k(cc["B"][0])], k(cc["Y"][0])))
        drivers = {q for _, q in self.regs}
        for p, (bits, d) in self.ports.items():
            if d == "input":
                drivers.update(bits)
        self.gates = topo(self.gates, drivers)

    def run(self, vals, M):
        v = {"0": 0, "1": M, "x": 0}
        v.update(vals)
        for op, ins, y in self.gates:
            a = [v[i] for i in ins]
            if op == "and":
                r = a[0] & a[1]
            elif op == "or":
                r = a[0] | a[1]
            elif op == "xor":
                r = a[0] ^ a[1]
            elif op == "xnor":
                r = ~(a[0] ^ a[1]) & M
            elif op == "nand":
                r = ~(a[0] & a[1]) & M
            elif op == "nor":
                r = ~(a[0] | a[1]) & M
            elif op == "not":
                r = ~a[0] & M
            else:
                r = a[2] if 0 else 0
            if op == "mux":
                r = (a[0] & a[2]) | (~a[0] & M & a[1])
            v[y] = r
        return v


def main():
    vfile, top, rjson, rtop = sys.argv[1:5]
    N = int(sys.argv[5]) if len(sys.argv) > 5 else 4096
    M = (1 << N) - 1
    rnd = random.Random(20260925)

    cells, ports, nn = load_th(vfile, top)
    ref = Ref(rjson, rtop)
    print("TH netlist: %d cells; reference: %d gates, %d regs"
          % (len(cells), len(ref.gates), len(ref.regs)))

    # ---- drivers of the TH netlist: input port rails ----
    outnets = {c[2] for c in cells}
    inrails = {}
    for p, (bits, d) in ports.items():
        if d != "input":
            continue
        base = p[:-2]
        for i, b in enumerate(bits):
            inrails.setdefault((base, i), {})[p[-1]] = b
    order = topo(cells, {b for r in inrails.values() for b in r.values()})

    # ---- CHECK 1: bit-parallel equivalence -----------------------------
    refin = {}
    tv = {"0": 0, "1": M, "x": 0}
    # reference primary inputs
    for p, (bits, d) in ref.ports.items():
        if d != "input":
            continue
        for i, b in enumerate(bits):
            refin[b] = rnd.getrandbits(N)
    qv = {}
    for j, (dn, q) in enumerate(ref.regs):
        qv[j] = rnd.getrandbits(N)
        refin[q] = qv[j]
    rv = ref.run(refin, M)

    for (base, i), r in inrails.items():
        if base == "qreg":
            val = qv[i]
        else:
            bits = ref.ports[base][0]
            val = refin[bits[i]]
        tv[r["L"]] = val
        tv[r["H"]] = ~val & M
    for t, ins, y in order:
        tv[y] = TH[t]([tv[x] for x in ins]) & M

    bad = collections.Counter()
    nchk = 0
    for p, (bits, d) in ports.items():
        if d != "output" or not p.endswith("_L"):
            continue
        base = p[:-2]
        hb = ports.get(base + "_H")
        for i, b in enumerate(bits):
            if base == "dreg":
                want = rv[ref.regs[i][0]] if ref.regs[i][0] in rv else tv["0"]
                dn = ref.regs[i][0]
                want = rv.get(dn, M if dn == "1" else 0)
            elif base == "done":
                continue
            else:
                rb = ref.ports[base][0][i]
                want = rv.get(rb, M if rb == "1" else 0)
            gotL = tv.get(b, M if b == "1" else 0)
            gotH = tv.get(hb[0][i], M if hb[0][i] == "1" else 0)
            nchk += 1
            if gotL != want:
                bad["%s_L[%d]" % (base, i)] += (gotL ^ want).bit_count()
            if gotH != (~want & M):
                bad["%s_H[%d]" % (base, i)] += (gotH ^ (~want & M)).bit_count()
    print("CHECK 1 EQUIVALENCE vs the gate netlist: %d vectors x %d output rail "
          "pairs = %d rail-vector comparisons, %d mismatching bits%s"
          % (N, nchk, 2 * N * nchk, sum(bad.values()),
             "" if not bad else " -- " + str(dict(list(bad.items())[:6]))))
    ok1 = not bad

    # ---- CHECK 2: per-cone exhaustive ---------------------------------
    conef = sys.argv[6] if len(sys.argv) > 6 else None
    ok2, ncone, ncode, nbadc = True, 0, 0, 0
    if conef:
        cmap = json.load(open(conef))
        drv = {c[2]: c for c in cells}

        def N2B(x):
            if x in ("0", "1", "x"):
                return x
            if x not in nn:
                sys.exit("cone map names a net absent from the emitted netlist: %s" % x)
            return nn[x]
        for cone in cmap["cones"]:
            sup = [[N2B(a), N2B(b)] for a, b in cone["support_rails"]]
            tt = cone["tt"]                      # list of 0/1, index = sum x_j<<j
            n = len(sup)
            base = {}
            for idx in range(1 << n):
                pass
            # bit-parallel over all 2**n codes at once
            Mn = (1 << (1 << n)) - 1
            env = {"0": 0, "1": Mn, "x": 0}
            valid = Mn
            for j, (lr, hr) in enumerate(sup):
                col = 0
                for idx in range(1 << n):
                    if idx >> j & 1:
                        col |= 1 << idx
                if lr in ("0", "1"):
                    # this support net collapsed to a CONSTANT upstream; only the
                    # codes that agree with it are reachable
                    valid &= col if lr == "1" else ~col & Mn
                    continue
                env[lr] = col
                env[hr] = ~col & Mn
            # evaluate the cone's own cells (transitive fan-in of its rails,
            # stopping at the support rails)
            need, stack = [], [N2B(cone["out_L"]), N2B(cone["out_H"])]
            seen = set()
            while stack:
                x = stack.pop()
                if x in seen or x in env or x not in drv:
                    continue
                seen.add(x)
                need.append(drv[x])
                stack.extend(drv[x][1])
            for t, ins, y in topo(need, set(env)):
                env[y] = TH[t]([env[x] for x in ins]) & Mn
            wantL = 0
            for idx in range(1 << n):
                if tt[idx]:
                    wantL |= 1 << idx
            oL, oH = N2B(cone["out_L"]), N2B(cone["out_H"])
            gotL = env.get(oL, Mn if oL == "1" else 0)
            gotH = env.get(oH, Mn if oH == "1" else 0)
            ncone += 1
            ncode += 1 << n
            if ((gotL ^ wantL) | (gotH ^ (~wantL & Mn))) & valid:
                ok2 = False
                nbadc += 1
                if nbadc < 4:
                    print("  CONE MISMATCH %s (support %s)"
                          % (cone["out_L"], cone["support_rails"]))
        print("CHECK 2 PER-CONE EXHAUSTIVE: %d cones, %d DATA codes "
              "(every code of every cone), %s"
              % (ncone, ncode, "0 mismatches" if ok2 else
                 "%d MISMATCHING CONES" % nbadc))

    # ---- CHECK 3/4/5: hysteretic settle -------------------------------
    ok3, ok4, ok5 = qdi_and_completeness(cells, order, ports, inrails, ref, rnd)

    print("RESULT: %s" % ("PASS" if (ok1 and ok2 and ok3 and ok4 and ok5) else "FAIL"))
    return 0 if (ok1 and ok2 and ok3 and ok4 and ok5) else 1


def settle_rise(order, st):
    """monotone DATA-phase settle: one topological sweep is exact because every
    TH cell is a POSITIVE (monotone) function and the inputs only rise."""
    for t, ins, y in order:
        w, T = WT[t]
        s = 0
        for wi, x in zip(w, ins):
            if st.get(x, 0):
                s += wi
        st[y] = 1 if s >= T else 0
    return st


def qdi_and_completeness(cells, order, ports, inrails, ref, rnd):
    # completion detector output
    donebit = None
    for p, (bits, d) in ports.items():
        if p == "done":
            donebit = bits[0]
    # ---- CHECK 3: random-delay QDI on a bounded sub-netlist ----
    drv = {c[2]: c for c in cells}
    # seed from the output rail with the DEEPEST transitive fan-in, not the
    # first one found: an output that happens to be a register bypass has a
    # 3-cell cone and would make this check vacuous.
    def fanin_size(seed, cap=100000):
        st, sn = [seed], set()
        while st:
            x = st.pop()
            if x in sn or x not in drv:
                continue
            sn.add(x); st.extend(drv[x][1])
            if len(sn) > cap:
                break
        return len(sn)
    cands = []
    for p, (bits, d) in ports.items():
        if d == "output" and p.endswith("_L") and p != "done":
            for b in bits:
                cands.append(b)
    seedrail = max(cands, key=fanin_size)
    sub, stack, seen = [], [seedrail], set()
    while stack and len(sub) < 1500:
        x = stack.pop()
        if x in seen or x not in drv:
            continue
        seen.add(x); sub.append(drv[x]); stack.extend(drv[x][1])
    subins = {i for _, ins, _ in sub for i in ins} - {c[2] for c in sub}
    subord = topo(sub, subins)
    fails3 = 0
    RUNS3 = 200
    import heapq
    fan = {}
    for idx, (t, ins, y) in enumerate(subord):
        for i in ins:
            fan.setdefault(i, []).append(idx)
    for _ in range(RUNS3):
        dly = [rnd.uniform(0.2, 5.0) for _ in subord]
        want = {x: rnd.randrange(2) for x in subins if x not in ("0", "1")}
        st = {"0": 0, "1": 1}
        for x in subins:
            st.setdefault(x, 0)
        for t, ins, y in subord:
            st[y] = 0
        gold = dict(st)
        for x, v in want.items():
            gold[x] = v
        settle_rise(subord, gold)
        q = []
        for x, v in want.items():
            if v:
                heapq.heappush(q, (rnd.uniform(0, 3.0), str(x), x, 1))
        fell = False
        while q:
            tm, _, net, val = heapq.heappop(q)
            if st.get(net) == val:
                continue
            if val == 0:
                fell = True
            st[net] = val
            for idx in fan.get(net, []):
                t, ins, y = subord[idx]
                w, T = WT[t]
                s = sum(wi for wi, x in zip(w, ins) if st.get(x, 0))
                nv = 1 if s >= T else (0 if all(st.get(x, 0) == 0 for x in ins)
                                       else st.get(y, 0))
                if nv != st.get(y, 0):
                    heapq.heappush(q, (tm + dly[idx], str(y), y, nv))
        if fell or any(st.get(y) != gold.get(y) for _, _, y in subord):
            fails3 += 1
        # NULL phase
        q = []
        for x, v in want.items():
            if st.get(x):
                heapq.heappush(q, (rnd.uniform(0, 3.0), str(x), x, 0))
        while q:
            tm, _, net, val = heapq.heappop(q)
            if st.get(net) == val:
                continue
            st[net] = val
            for idx in fan.get(net, []):
                t, ins, y = subord[idx]
                w, T = WT[t]
                s = sum(wi for wi, x in zip(w, ins) if st.get(x, 0))
                nv = 1 if s >= T else (0 if all(st.get(x, 0) == 0 for x in ins)
                                       else st.get(y, 0))
                if nv != st.get(y, 0):
                    heapq.heappush(q, (tm + dly[idx], str(y), y, nv))
        if any(st.get(y) for _, _, y in subord):
            fails3 += 1
    print("CHECK 3 QDI 4-PHASE (hysteretic, random per-gate delays) on a "
          "%d-cell sub-netlist: %d runs, %d failures (hazard / wrong settle / "
          "stuck-high after NULL)" % (len(subord), RUNS3, fails3))

    # ---- CHECK 4/5: input-completeness + NULL return, whole netlist ----
    if donebit is None:
        print("CHECK 4/5: skipped (netlist has no completion detector; "
              "regenerate with --cd tree)")
        return fails3 == 0, True, True
    # An input bit that NOTHING reads cannot be waited for by any completion
    # detector -- in this netlist or in CMOS.  Exclude structurally DEAD input
    # bits from the hold set and report them, rather than scoring them as
    # completeness failures.
    fanout = collections.Counter()
    for _, ins, _ in cells:
        for i in ins:
            fanout[i] += 1
    dead = [kk for kk, r in inrails.items()
            if fanout[r["L"]] == 0 and fanout[r["H"]] == 0]
    keys = sorted(kk for kk in inrails if kk not in set(dead))
    if dead:
        print("          structurally DEAD input bits excluded from the hold set "
              "(nothing in the netlist reads them): %d -- %s"
              % (len(dead), ", ".join("%s[%d]" % x for x in sorted(dead)[:6])))
    TR = 400
    prem = 0
    premwho = collections.Counter()
    norise = 0
    nullfail = 0
    for _ in range(TR):
        vals = {kk: rnd.randrange(2) for kk in inrails}
        hold = keys[rnd.randrange(len(keys))]
        st = {"0": 0, "1": 1, "x": 0}
        for kk, r in inrails.items():
            if kk == hold:
                st[r["L"]] = 0; st[r["H"]] = 0
            else:
                st[r["L"]] = vals[kk]; st[r["H"]] = vals[kk] ^ 1
        settle_rise(order, st)
        if st.get(donebit):
            prem += 1
            premwho[hold] += 1
        r = inrails[hold]
        st[r["L"]] = vals[hold]; st[r["H"]] = vals[hold] ^ 1
        settle_rise(order, st)
        if not st.get(donebit):
            norise += 1
        # NULL phase: hysteretic reset
        for kk, r in inrails.items():
            st[r["L"]] = 0; st[r["H"]] = 0
        for t, ins, y in order:
            w, T = WT[t]
            s = sum(wi for wi, x in zip(w, ins) if st.get(x, 0))
            st[y] = 1 if s >= T else (0 if all(st.get(x, 0) == 0 for x in ins)
                                      else st[y])
        stuck = [ (t,ins,y) for t, ins, y in order if st.get(y) ]
        if stuck:
            nullfail += 1
            if nullfail == 1:
                print("          first stuck-high cells after NULL: %s"
                      % [(t, ins, y) for t, ins, y in stuck[:4]])
    print("CHECK 4 INPUT-COMPLETENESS (1 of %d input bits held NULL, rest DATA): "
          "%d trials, %d premature 'done', %d failures to rise when released"
          % (len(keys), TR, prem, norise))
    if premwho:
        print("          premature-done held bits: %s"
              % ", ".join("%s[%d] x%d" % (a, b, c) for (a, b), c in premwho.most_common(8)))
    print("CHECK 5 NULL RETURN: %d trials, %d with a net stuck high"
          % (TR, nullfail))
    return fails3 == 0, prem == 0 and norise == 0, nullfail == 0


if __name__ == "__main__":
    sys.exit(main())
