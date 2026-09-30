#!/usr/bin/env python3
"""SKEPTIC's own gate-level netlist parser + evaluator + levelizer for the
sg13g2-mapped sha_slice.  Written from scratch: it does NOT import struct.py,
levelize_mapped.py, or anything from the track.

Used for three independent jobs:
  * a COMPLETE cone-wise exhaustive equivalence proof (proof by support-set
    decomposition, structurally different from yosys miter/equiv)
  * the levelization / bank profile / signal-lifetime / II re-derivation
  * the expected-value oracle for the block value check
"""
import itertools, json, re, sys

FUN = {
    "sg13g2_inv_1":   (["A"], "Y", lambda v: 1 - v["A"]),
    "sg13g2_buf_1":   (["A"], "X", lambda v: v["A"]),
    "sg13g2_nand2_1": (["A", "B"], "Y", lambda v: 1 - (v["A"] & v["B"])),
    "sg13g2_and2_1":  (["A", "B"], "X", lambda v: v["A"] & v["B"]),
    "sg13g2_nor2_1":  (["A", "B"], "Y", lambda v: 1 - (v["A"] | v["B"])),
    "sg13g2_or2_1":   (["A", "B"], "X", lambda v: v["A"] | v["B"]),
}


class Net:
    def __init__(self, path):
        txt = open(path).read()
        txt = re.sub(r"/\*.*?\*/", " ", txt, flags=re.S)
        txt = re.sub(r"//[^\n]*", " ", txt)
        self.inputs, self.outputs = {}, {}     # name -> width
        for kind, dct in (("input", self.inputs), ("output", self.outputs)):
            for m in re.finditer(r"\b%s\s+(?:\[(\d+):(\d+)\]\s*)?([A-Za-z_][\w$]*)\s*;"
                                 % kind, txt):
                hi, lo, nm = m.group(1), m.group(2), m.group(3)
                dct[nm] = 1 if hi is None else (int(hi) - int(lo) + 1)
        self.cells = []                        # (type, inst, {port: net})
        for m in re.finditer(r"(sg13g2_\w+)\s+(\S+)\s*\(([^;]*?)\)\s*;", txt, re.S):
            typ, inst, body = m.group(1), m.group(2), m.group(3)
            conn = {}
            for pm in re.finditer(r"\.(\w+)\s*\(\s*([^),]*?)\s*\)", body):
                conn[pm.group(1)] = pm.group(2).strip()
            self.cells.append((typ, inst, conn))
        self.assigns = []                      # (lhs, rhs) pure aliases
        for m in re.finditer(r"assign\s+(\S+)\s*=\s*([^;]+);", txt):
            self.assigns.append((m.group(1).strip(), m.group(2).strip()))

    # ---- flat bit names
    def bits(self, dct):
        out = []
        for nm, w in dct.items():
            out += [nm] if w == 1 else ["%s[%d]" % (nm, i) for i in range(w)]
        return out

    def in_bits(self):
        return self.bits(self.inputs)

    def out_bits(self):
        return self.bits(self.outputs)

    # ---- dependency graph, topological order
    def build(self):
        self.driver = {}                        # net -> (idx or ('alias', rhs))
        for k, (typ, inst, conn) in enumerate(self.cells):
            ins, o, _ = FUN[typ]
            self.driver[conn[o]] = ("cell", k)
        for lhs, rhs in self.assigns:
            self.driver[lhs] = ("alias", rhs)
        # topo sort over cells
        self.deps = []
        for typ, inst, conn in self.cells:
            ins, o, _ = FUN[typ]
            self.deps.append([conn[p] for p in ins])
        order, state = [], {}

        def visit(k):
            st = state.get(k)
            if st == 2:
                return
            assert st != 1, "combinational loop at cell %d" % k
            state[k] = 1
            for nd in self.deps[k]:
                d = self.driver.get(nd)
                while d is not None and d[0] == "alias":
                    d = self.driver.get(d[1])
                if d is not None and d[0] == "cell":
                    visit(d[1])
            state[k] = 2
            order.append(k)
        sys.setrecursionlimit(100000)
        for k in range(len(self.cells)):
            visit(k)
        self.order = order
        return self

    def resolve(self, nd, val):
        """value of a net, following aliases and constants."""
        if nd in ("1'b0", "1'h0", "0"):
            return 0
        if nd in ("1'b1", "1'h1", "1"):
            return 1
        if nd in val:
            return val[nd]
        d = self.driver.get(nd)
        if d is not None and d[0] == "alias":
            return self.resolve(d[1], val)
        raise KeyError(nd)

    def eval(self, invals):
        """invals: {bitname: 0/1}.  returns (outbits dict, per-cell out dict)"""
        val = dict(invals)
        cellout = {}
        for k in self.order:
            typ, inst, conn = self.cells[k]
            ins, o, fn = FUN[typ]
            v = {p: self.resolve(conn[p], val) for p in ins}
            r = fn(v)
            val[conn[o]] = r
            cellout[inst] = r
        outs = {nd: self.resolve(nd, val) for nd in self.out_bits()}
        return outs, val, cellout

    # ---- support sets per output bit (transitive fan-in, primary inputs only)
    def support(self):
        pin = set(self.in_bits())
        memo = {}

        def sup(nd):
            if nd in pin:
                return frozenset([nd])
            if nd in ("1'b0", "1'b1", "1'h0", "1'h1", "0", "1"):
                return frozenset()
            if nd in memo:
                return memo[nd]
            memo[nd] = frozenset()              # loop guard
            d = self.driver.get(nd)
            if d is None:
                return frozenset()
            if d[0] == "alias":
                r = sup(d[1])
            else:
                typ, inst, conn = self.cells[d[1]]
                ins, o, _ = FUN[typ]
                r = frozenset().union(*[sup(conn[p]) for p in ins]) if ins else frozenset()
            memo[nd] = r
            return r
        return {nd: sup(nd) for nd in self.out_bits()}

    # ---- levelize: level = 1 + max(level of driving cells of its inputs)
    def levelize(self):
        lev = {}
        for k in self.order:
            typ, inst, conn = self.cells[k]
            ins, o, _ = FUN[typ]
            L = 0
            for p in ins:
                nd = conn[p]
                d = self.driver.get(nd)
                while d is not None and d[0] == "alias":
                    d = self.driver.get(d[1])
                if d is not None and d[0] == "cell":
                    L = max(L, lev[d[1]])
            lev[k] = L + 1
        self.lev = lev
        return lev

    def consumers(self):
        """cell idx -> set of consumer cell idxs (and 'PO' for primary outputs)"""
        net2cells = {}
        for k, (typ, inst, conn) in enumerate(self.cells):
            ins, o, _ = FUN[typ]
            for p in ins:
                net2cells.setdefault(conn[p], []).append(k)
        # aliases: a consumer reading an alias reads its rhs
        alias_of = {l: r for l, r in self.assigns}
        cons = {k: set() for k in range(len(self.cells))}
        po_of = set()
        for k, (typ, inst, conn) in enumerate(self.cells):
            ins, o, _ = FUN[typ]
            nd = conn[o]
            for c in net2cells.get(nd, []):
                cons[k].add(c)
            # who aliases this net onward
            for l, r in self.assigns:
                if r == nd:
                    for c in net2cells.get(l, []):
                        cons[k].add(c)
            obits = set(self.out_bits())
            if nd in obits or any(l in obits and r == nd for l, r in self.assigns):
                po_of.add(k)
        return cons, po_of


# ------------------------------------------------- my own reference model (RTL)
def ref(a, b, c, e, f, g):
    """sha_slice.v, re-implemented from the RTL text by hand."""
    maj = (a & b) ^ (a & c) ^ (b & c)
    ch = (e & f) ^ ((~e & 0xFF) & g)
    s = (a + b) & 0xFF
    return maj & 0xFF, ch & 0xFF, s


def pack(nm, val, w=8):
    return sum(val.get("%s[%d]" % (nm, i), 0) << i for i in range(w))


def unpack(nm, x, w=8):
    return {"%s[%d]" % (nm, i): (x >> i) & 1 for i in range(w)}
