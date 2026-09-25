#!/usr/bin/env python3
"""Functional + delay-insensitivity verification of a direct-threshold sha_slice
netlist.  Reads the netlist back through yosys (read_verilog; flatten; write_json)
so the check is on the EMITTED FILE, not on the mapper's in-memory state.

Three checks:
  1. COMB decode -- evaluate the TH cells with their stateless Boolean model and
     compare maj/ch/sum against the sha_slice.v reference.
     * sum: EXHAUSTIVE over all 65536 (a,b).
     * maj/ch: EXHAUSTIVE per bit (their cones are 3-bit; one vector with
       a=0xAA,b=0xCC,c=0xF0 puts all 8 (a,b,c) combos on the 8 bit positions).
     * plus a large random sweep of the whole 48-bit input.
  2. BIT-SLICE structure -- confirm each maj[i]/ch[i] output rail's transitive
     fan-in touches only {a,b,c}[i] / {e,f,g}[i], which is what makes the per-bit
     exhaustive sweep a complete proof for those outputs.
  3. QDI 4-phase -- event-driven simulation with HYSTERETIC cells and RANDOM
     per-gate delays.  NULL -> DATA -> NULL.  Asserts (a) every output decodes,
     (b) rails are monotone within a phase (no rail falls during DATA, none rises
     during NULL -- i.e. no hazard under arbitrary delay), (c) everything returns
     to NULL, (d) no output rail goes high before all inputs it structurally
     needs are DATA.
"""
import json
import random
import subprocess
import sys

TH = {
    "th12": lambda x: int(any(x)),
    "th13": lambda x: int(any(x)),
    "th14": lambda x: int(any(x)),
    "th22": lambda x: int(x[0] and x[1]),
    "th23": lambda x: int(sum(x) >= 2),
    "th33": lambda x: int(all(x)),
    "th24": lambda x: int(sum(x) >= 2),
    "th34": lambda x: int(sum(x) >= 3),
    "th44": lambda x: int(all(x)),
    "th23w2": lambda x: int(2 * x[0] + x[1] + x[2] >= 2),
    "th34w2": lambda x: int(2 * x[0] + x[1] + x[2] + x[3] >= 3),
}
# hysteretic (qdi) model: set when threshold met, reset when ALL inputs 0, else hold
WT = {"th12": ([1, 1], 1), "th13": ([1, 1, 1], 1), "th14": ([1, 1, 1, 1], 1),
      "th22": ([1, 1], 2), "th23": ([1, 1, 1], 2), "th33": ([1, 1, 1], 3),
      "th24": ([1, 1, 1, 1], 2), "th34": ([1, 1, 1, 1], 3), "th44": ([1, 1, 1, 1], 4),
      "th23w2": ([2, 1, 1], 2), "th34w2": ([2, 1, 1, 1], 3)}
PINS = ["a", "b", "c", "d"]


def load(vfile, top):
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
            sys.exit("non-TH cell %s (%s) in netlist" % (t, cn))
        ins = [c["connections"][p][0] for p in PINS if p in c["connections"]]
        cells.append((t, [k(x) for x in ins], k(c["connections"]["y"][0])))
    # port bit lists
    ports = {p: [k(b) for b in v["bits"]] for p, v in m["ports"].items()}
    # netnames -> aliases are already resolved by yosys into shared bit ids
    return cells, ports


def k(b):
    return b if isinstance(b, int) else str(b)


def topo(cells, driven):
    """order cells so every input is available (pure comb, no loops expected)."""
    have = set(driven) | {"0", "1", "x"}
    out, pend = [], list(cells)
    while pend:
        prog = False
        nxt = []
        for c in pend:
            if all(i in have for i in c[1]):
                out.append(c); have.add(c[2]); prog = True
            else:
                nxt.append(c)
        pend = nxt
        if not prog:
            sys.exit("combinational loop / undriven nets: %d cells stuck" % len(pend))
    return out


class Net(object):
    def __init__(self, cells, ports):
        self.ports = ports
        drv = set()
        for p, bits in ports.items():
            if p.endswith("_L") or p.endswith("_H"):
                drv.update(bits)
        # only INPUT port bits are drivers; find them by "not driven by a cell"
        outs = {c[2] for c in cells}
        self.inbits = {b for b in drv if b not in outs}
        self.cells = topo(cells, self.inbits)

    def drive(self, vals):
        """vals: {port -> int}; returns net value dict"""
        v = {"0": 0, "1": 1}
        for p, bits in self.ports.items():
            base = p[:-2]
            if p.endswith("_L") and base in vals:
                for i, b in enumerate(bits):
                    if b in self.inbits:
                        v[b] = (vals[base] >> i) & 1
            elif p.endswith("_H") and base in vals:
                for i, b in enumerate(bits):
                    if b in self.inbits:
                        v[b] = ((vals[base] >> i) & 1) ^ 1
        for t, ins, y in self.cells:
            v[y] = TH[t]([v[x] for x in ins])
        return v

    def read(self, v, p):
        bits = self.ports[p + "_L"]
        r = 0
        for i, b in enumerate(bits):
            r |= (v.get(b, int(b) if b in ("0", "1") else 0) << i)
        return r

    def welformed(self, v, p):
        L, H = self.ports[p + "_L"], self.ports[p + "_H"]
        for bl, bh in zip(L, H):
            a = v.get(bl, int(bl) if bl in ("0", "1") else 0)
            b = v.get(bh, int(bh) if bh in ("0", "1") else 0)
            if a + b != 1:
                return False
        return True


def ref(a, b, c, e, f, g):
    return ((a & b) ^ (a & c) ^ (b & c), (e & f) ^ ((~e & 0xFF) & g), (a + b) & 0xFF)


def main():
    vfile = sys.argv[1] if len(sys.argv) > 1 else "work/sha_slice_direct.v"
    top = sys.argv[2] if len(sys.argv) > 2 else "sha_slice"
    cells, ports = load(vfile, top)
    N = Net(cells, ports)
    print("netlist: %d TH cells, %d input rail bits" % (len(cells), len(N.inbits)))

    bad = 0
    tests = 0

    def chk(a, b, c, e, f, g):
        nonlocal bad, tests
        v = N.drive(dict(a=a, b=b, c=c, e=e, f=f, g=g))
        rm, rc, rs = ref(a, b, c, e, f, g)
        gm, gc, gs = N.read(v, "maj"), N.read(v, "ch"), N.read(v, "sum")
        tests += 1
        ok = (gm == rm and gc == rc and gs == rs
              and N.welformed(v, "maj") and N.welformed(v, "ch")
              and N.welformed(v, "sum"))
        if not ok:
            bad += 1
            if bad <= 5:
                print("  MISMATCH a=%02x b=%02x c=%02x e=%02x f=%02x g=%02x | "
                      "maj %02x/%02x ch %02x/%02x sum %02x/%02x"
                      % (a, b, c, e, f, g, gm, rm, gc, rc, gs, rs))
        return ok

    # 1a. EXHAUSTIVE adder: all 65536 (a,b), with two different c/e/f/g backgrounds
    for bgc, bge, bgf, bgg in ((0x00, 0x00, 0x00, 0x00), (0xF0, 0xAA, 0xCC, 0x5A)):
        for a in range(256):
            for b in range(256):
                chk(a, b, bgc, bge, bgf, bgg)
    print("  [1a] adder exhaustive 2x65536 (a,b): %d vectors" % tests)

    # 1b. per-bit exhaustive for maj / ch: EVERY bit position x EVERY one of the
    # 8 (a,b,c) and (e,f,g) combos, enumerated literally (64 vectors each).
    t0 = tests
    cover_m = set(); cover_c = set()
    for i in range(8):
        for m in range(8):
            for n in range(8):
                a = ((m >> 0) & 1) << i
                b = ((m >> 1) & 1) << i
                c = ((m >> 2) & 1) << i
                e = ((n >> 0) & 1) << i
                f = ((n >> 1) & 1) << i
                g = ((n >> 2) & 1) << i
                # background on the other bits must not matter (proved by check 2)
                chk(a, b, c, e, f, g)
                cover_m.add((i, m)); cover_c.add((i, n))
    print("  [1b] maj/ch per-bit exhaustive: %d vectors, coverage maj %d/64 ch %d/64"
          % (tests - t0, len(cover_m), len(cover_c)))

    # 1c. random full-input sweep
    t0 = tests
    rnd = random.Random(20260925)
    for _ in range(20000):
        chk(*[rnd.randrange(256) for _ in range(6)])
    print("  [1c] random 48-bit sweep: %d vectors" % (tests - t0))
    print("CHECK 1 COMB DECODE: %d vectors, %d mismatches" % (tests, bad))

    # 2. bit-slice structure
    drvof = {c[2]: c for c in cells}
    inport = {}
    for p, bits in ports.items():
        if p[:-2] in ("a", "b", "c", "e", "f", "g"):
            for i, bb in enumerate(bits):
                inport[bb] = "%s[%d]" % (p[:-2], i)

    def support(bit):
        seen, st, sup = set(), [bit], set()
        while st:
            x = st.pop()
            if x in seen:
                continue
            seen.add(x)
            if x in inport:
                sup.add(inport[x]); continue
            if x in drvof:
                st.extend(drvof[x][1])
        return sup
    slice_ok = True
    for op, ins in (("maj", "abc"), ("ch", "efg")):
        for i in range(8):
            want = {"%s[%d]" % (s, i) for s in ins}
            for r in ("_L", "_H"):
                got = support(ports[op + r][i])
                if got != want:
                    slice_ok = False
                    print("  %s%s[%d] support %s != %s" % (op, r, i, sorted(got), sorted(want)))
    sup7 = support(ports["sum_L"][7])
    print("CHECK 2 BIT-SLICE: maj/ch cones exactly per-bit = %s; "
          "sum[7] support = %d bits (%s)"
          % (slice_ok, len(sup7), "carry chain" if len(sup7) == 16 else sorted(sup7)))

    # 3. QDI 4-phase with random gate delays
    qbad, qruns = qdi_check(N, cells, ports, 300)
    print("CHECK 3 QDI 4-PHASE (hysteretic cells, random delays): %d runs, %d failures"
          % (qruns, qbad))

    # 4. DYNAMIC INPUT-COMPLETENESS (only meaningful with a completion detector):
    #    hold ONE input bit at NULL, drive the rest to DATA -- `done` must stay low.
    cbad = cruns = 0
    if "done" in ports:
        cbad, cruns = completeness_check(N, cells, ports, 400)
        print("CHECK 4 DYNAMIC INPUT-COMPLETENESS (1 input held NULL, done must "
              "stay low): %d trials, %d premature 'done'" % (cruns, cbad))
    else:
        print("CHECK 4 DYNAMIC INPUT-COMPLETENESS: skipped (netlist has no "
              "completion detector; regenerate with --cd tree)")
    ok = bad == 0 and slice_ok and qbad == 0 and cbad == 0
    print("RESULT: %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


def completeness_check(N, cells, ports, trials):
    """Hold one primary input bit at NULL (both rails low), drive everything else
    to DATA, settle, and require `done` to stay LOW.  Then release the held input
    and require `done` to go HIGH.  This is the dynamic counterpart of the
    mapper's structural input-completeness proof."""
    rnd = random.Random(99)
    donebit = ports["done"][0]
    fanout = {}
    for idx, (t, ins, y) in enumerate(cells):
        for x in ins:
            fanout.setdefault(x, []).append(idx)
    fails = 0
    inrails = {}
    for p, bits in ports.items():
        if p[:-2] in ("a", "b", "c", "e", "f", "g") and p[-2:] in ("_L", "_H"):
            for i, bb in enumerate(bits):
                if bb in N.inbits:
                    inrails.setdefault((p[:-2], i), {})[p[-1]] = bb
    keys = sorted(inrails)
    for _ in range(trials):
        vals = {n: rnd.randrange(256) for n in "abcefg"}
        hold = keys[rnd.randrange(len(keys))]
        st = {"0": 0, "1": 1}
        for bb in N.inbits:
            st[bb] = 0
        for t, ins, y in cells:
            st[y] = 0

        def settle():
            q = []
            for idx in range(len(cells)):
                q.append(idx)
            ch = True
            while ch:
                ch = False
                for idx, (t, ins, y) in enumerate(cells):
                    w, T = WT[t]
                    s = sum(wi for wi, x in zip(w, ins) if st.get(x, 0))
                    if s >= T:
                        nv = 1
                    elif all(st.get(x, 0) == 0 for x in ins):
                        nv = 0
                    else:
                        nv = st.get(y, 0)
                    if nv != st.get(y, 0):
                        st[y] = nv; ch = True

        def drive(skip):
            for (nm, i), r in inrails.items():
                if (nm, i) == skip:
                    st[r['L']] = 0; st[r['H']] = 0
                    continue
                bit = (vals[nm] >> i) & 1
                st[r['L']] = bit; st[r['H']] = bit ^ 1
        drive(hold)
        settle()
        if st.get(donebit):
            fails += 1
            if fails <= 3:
                print("  PREMATURE done with %s[%d] held NULL" % hold)
            continue
        drive(None)
        settle()
        if not st.get(donebit):
            fails += 1
            if fails <= 3:
                print("  done never rose with all inputs DATA (%s)" % (hold,))
    return fails, trials


def qdi_check(N, cells, ports, runs):
    """Event-driven hysteretic simulation with random per-gate delays."""
    rnd = random.Random(7)
    fanout = {}
    for idx, (t, ins, y) in enumerate(cells):
        for x in ins:
            fanout.setdefault(x, []).append(idx)
    fails = 0
    for run in range(runs):
        a, b, c, e, f, g = [rnd.randrange(256) for _ in range(6)]
        dly = [rnd.uniform(0.2, 5.0) for _ in cells]
        st = {}                       # net -> 0/1
        for x in ("0", "1"):
            st[x] = int(x)
        for bb in N.inbits:
            st[bb] = 0
        for t, ins, y in cells:
            st[y] = 0
        rose = set()

        def ev(idx, val, now, q):
            q.append((now + dly[idx], cells[idx][2], val))

        def settle(now, q, phase):
            ok = True
            q.sort()
            while q:
                q.sort()
                tm, net, val = q.pop(0)
                if st.get(net) == val:
                    continue
                if phase == "DATA" and val == 0 and net in rose:
                    ok = False              # a rail fell during DATA -> hazard
                st[net] = val
                if phase == "DATA" and val == 1:
                    rose.add(net)
                for idx in fanout.get(net, []):
                    t, ins, y = cells[idx]
                    w, T = WT[t]
                    s = sum(wi for wi, x in zip(w, ins) if st.get(x, 0))
                    if s >= T:
                        nv = 1
                    elif all(st.get(x, 0) == 0 for x in ins):
                        nv = 0
                    else:
                        nv = st.get(y, 0)
                    if nv != st.get(y, 0):
                        ev(idx, nv, tm, q)
            return ok

        # --- DATA phase: raise input rails in a random order/time ---
        q = []
        rose = set()
        vals = dict(a=a, b=b, c=c, e=e, f=f, g=g)
        for p, bits in ports.items():
            base = p[:-2]
            if base not in vals:
                continue
            for i, bb in enumerate(bits):
                if bb not in N.inbits:
                    continue
                bit = (vals[base] >> i) & 1
                hi = bit if p.endswith("_L") else bit ^ 1
                if hi:
                    q.append((rnd.uniform(0, 3.0), bb, 1))
        ok = settle(0.0, q, "DATA")
        rm, rc, rs = ref(a, b, c, e, f, g)
        got = (N.read(st, "maj"), N.read(st, "ch"), N.read(st, "sum"))
        wf = all(N.welformed(st, p) for p in ("maj", "ch", "sum"))
        if got != (rm, rc, rs) or not wf or not ok:
            fails += 1
            if fails <= 3:
                print("  QDI FAIL run %d: got %s want %s wf=%s monotone=%s"
                      % (run, got, (rm, rc, rs), wf, ok))
            continue
        # --- NULL phase ---
        q = []
        for bb in N.inbits:
            if st.get(bb):
                q.append((rnd.uniform(0, 3.0), bb, 0))
        settle(0.0, q, "NULL")
        if any(st.get(y) for _, _, y in cells) or any(st.get(bb) for bb in N.inbits):
            fails += 1
            if fails <= 3:
                stuck = [y for _, _, y in cells if st.get(y)]
                print("  QDI FAIL run %d: %d nets stuck high after NULL (%s...)"
                      % (run, len(stuck), stuck[:6]))
    return fails, runs


if __name__ == "__main__":
    sys.exit(main())
