#!/usr/bin/env python3
"""qal/mblocks -- REAL packet/DSP blocks on the committed three-phase wave.

Everything scored here was fixed in PRE_REGISTERED.json BEFORE this file
existed.  Blocks: CRC-32 (IEEE 0x04C11DB7) state update over a 32-bit word
(32 dual-rail nand2 XOR trees) and an NxN unsigned multiplier (AND array ->
Dadda CSA tree of nand2 full adders -> Kogge-Stone final adder).  Cells:
sg13g2_nand2_1 vendor sizing (= campaign inverter widths), campaign inverter
as delay element, CL 2 fF, ideal trapezoid phases A/B/C (mesh3 VERBATIM),
d = 3 nand-levels per bank, T_third = 92 ps.

Subcommands
  ic                       harness anchor: mesh3 trap_tt92_d3 re-extracted on VACASK
  crc  [group|all]         block A on VACASK (4 groups of 8 trees)
  mul  <N>                 block B on VACASK
  xyce crc|mul<N>          Xyce anchor row (same deck, truncated to 6 periods)
  level                    CMOS nand2 chain level (both engines, 1.2 V and 1.65 V)
  sta  crc|mul<N>          OpenSTA minimum period per D on the same netlist
  agg                      RESULTS.json
"""
import json, math, os, re, shutil, subprocess, sys, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SCRATCH = os.environ.get("MB_SCRATCH", "/tmp/claude-1001/-usr-local-src/"
                         "cf6756fa-e0c0-4fe1-ade0-e263361839c0/scratchpad/mblocks")
VACASK = "/usr/local/bin/vacask"
OSDI = "/usr/local/lib/vacask/mod"
MODELS_INC = "/usr/local/src/stat-sim/qal/p620a/vacask_port/sg13g2_models.inc"
XYCE = "/usr/local/src/xyce-build/src/Xyce"
XVA = "/usr/local/share/xyce/verilog-a/psp103/psp103.va"
XMODEL = "/usr/local/src/kestrel/sim/models/sg13g2_psp103_tt.lib"
XSHIM = "/usr/local/src/stat-sim/qal/sg13lv_compat.sp"
XENV = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS",
            PYMS_VAE_CACHE=os.path.join(os.path.dirname(SCRATCH), "vae_cache_mblocks"))
TRIPJSON = "/usr/local/src/stat-sim/qal/fcrit/TRIP.json"
sys.path.insert(0, "/usr/local/src/VACASK/python")

WP, WN, LCH = 1.12 * float(os.environ.get("MB_WP", "1")), 0.74, 0.13   # MB_WP: pMOS width scale (lane experiments)
CLOAD = 2.0            # fF
DV = 1.65
EDGE = 2.0             # ps
TT = 92.0              # ps, T_third
D_LEVELS = 3
GRID = 0.10            # ps
SIG_TOTAL_MV = 23.308
GATE_MV = 3 * SIG_TOTAL_MV   # 69.924
NW = 24                # words launched; waves 2..NW-1 scored
SEED = 20261016
POLY = 0x04C11DB7
T_REG_2FF = 315.378    # ps DERIVED (307.1 @0 fF, 335.7 @6.91 fF)
T_LEVEL_INV = 52.51    # ps MEASURED inverter level @2 fF, 1.2 V (fcrit_skept)


# ============================================================== netlist
class Net(object):
    """nand2/inv DAG with dual-rail bookkeeping. Constants '0'/'1' folded."""
    def __init__(self):
        self.gates = {}        # name -> dict(kind, ins, level)
        self.order = []
        self.pis = []          # primary input names (level 0)
        self.comp = {}         # name -> complement name (if known)
        self.outs = []         # primary outputs (name, bit index)
        self.n = 0

    def pi(self, name, cname=None):
        self.pis.append(name)
        if cname:
            self.pis.append(cname)
            self.comp[name] = cname
            self.comp[cname] = name
        return name

    def level(self, x):
        if x in ("0", "1"):
            return 0
        if x in self.gates:
            return self.gates[x]["level"]
        return 0

    def _new(self, kind, ins, tag="g"):
        self.n += 1
        name = "%s%d" % (tag, self.n)
        self.gates[name] = dict(kind=kind, ins=list(ins),
                                level=1 + max(self.level(i) for i in ins))
        self.order.append(name)
        return name

    def inv(self, a):
        if a == "0":
            return "1"
        if a == "1":
            return "0"
        return self._new("inv", [a], "i")

    def nand(self, a, b):
        if a == "0" or b == "0":
            return "1"
        if a == "1":
            return self.inv(b)
        if b == "1":
            return self.inv(a)
        return self._new("nand", [a, b], "n")

    def pair(self, y, yn):
        if y not in ("0", "1"):
            self.comp[y] = yn
        if yn not in ("0", "1"):
            self.comp[yn] = y

    def xor_dual(self, a, an, b, bn):
        """y = a^b, yn = ~(a^b) -- 6 nand2, depth 2 (constants folded)."""
        if a in ("0", "1"):
            return (b, bn) if a == "0" else (bn, b)
        if b in ("0", "1"):
            return (a, an) if b == "0" else (an, a)
        y = self.nand(self.nand(a, bn), self.nand(an, b))
        yn = self.nand(self.nand(a, b), self.nand(an, bn))
        self.pair(y, yn)
        return y, yn

    def and_dual(self, a, b):
        if a == "0" or b == "0":
            return "0", "1"
        if a == "1":
            return b, self.comp[b]
        if b == "1":
            return a, self.comp[a]
        cn = self.nand(a, b)
        c = self.inv(cn)
        self.pair(c, cn)
        return c, cn

    def fa_dual(self, a, an, b, bn, c, cn):
        """sum, sum~, cout, cout~ ; 16 nand2, depth 4 (constants folded)."""
        x, xn = self.xor_dual(a, an, b, bn)
        s, sn = self.xor_dual(x, xn, c, cn)
        # cout = ab | c(a^b)
        t1 = self.nand(a, b)
        t2 = self.nand(c, x)
        co = self.nand(t1, t2)
        # ~MAJ(a,b,c) = MAJ(~a,~b,~c) = ~a~b | ~c(~a ^ ~b) = ~a~b | ~c(a^b)
        t3 = self.nand(an, bn)
        t4 = self.nand(cn, x)
        con = self.nand(t3, t4)
        self.pair(co, con)
        return s, sn, co, con

    def ha_dual(self, a, an, b, bn):
        s, sn = self.xor_dual(a, an, b, bn)
        c, cn = self.and_dual(a, b)
        return s, sn, c, cn

    # ---- evaluation
    def eval(self, pivals):
        v = dict(pivals)
        v["0"], v["1"] = 0, 1
        for g in self.order:
            d = self.gates[g]
            if d["kind"] == "inv":
                v[g] = 1 - v[d["ins"][0]]
            else:
                v[g] = 1 - (v[d["ins"][0]] & v[d["ins"][1]])
        return v

    def stats(self):
        nn = sum(1 for g in self.gates.values() if g["kind"] == "nand")
        ni = len(self.gates) - nn
        return dict(nand2=nn, inv=ni, gates=len(self.gates), fets=4 * nn + 2 * ni,
                    levels=max(g["level"] for g in self.gates.values()))


def bank_of(level):
    return (level - 1) // D_LEVELS + 1 if level > 0 else 0


RETIME = os.environ.get("MB_RETIME", "first")
# "first": the committed rule -- a far source (bank gap >= 2) is carried by an
#          inverter chain ending at the FIRST level of bank(consumer)-1; an
#          adjacent-bank edge may leave the producing bank from ANY level.
# "last":  every cross-bank edge leaves the producing bank from its LAST level
#          (the structure of the calibration lanes). Added after the d=2 block
#          runs: a producer at level-in-bank 1 is destroyed (its own inputs
#          die with the bank before) one gate delay earlier than a last-level
#          producer, which a consumer at level-in-bank 2 of the next bank
#          cannot tolerate (edge census: mul8 has 78 such (1->2) edges, the
#          lane has none). Also makes every boundary set single-level, so the
#          bank-level eye/handoff scorer is exact instead of conservative.


def insert_delays(nl):
    """Enforce bank(consumer) - bank(producer) in {0,1} with inverter chains
    (shared per source+level). Returns the count of inserted inverters."""
    if RETIME == "last":
        return insert_delays_last(nl)
    chains = {}      # (src, level) -> node name of that polarity at that level
    added = 0

    def tap(src, lvl):
        """node carrying src's polarity at level lvl (lvl > level(src))."""
        nonlocal added
        key = (src, lvl)
        if key in chains:
            return chains[key]
        L0 = nl.level(src)
        m = lvl - L0
        # even m: chain from src; odd m: chain from comp(src) if it exists at
        # a level of the right parity, else chain from src with one more
        # stage (even)
        if m % 2 == 1 and src in nl.comp and nl.level(nl.comp[src]) == L0:
            start = nl.comp[src]
        elif m % 2 == 1:
            return tap(src, lvl + 1)
        else:
            start = src
        cur, L = start, L0
        while L < lvl:
            k2 = (start, L + 1, "chain")
            if k2 in chains:
                cur = chains[k2]
            else:
                nl.n += 1
                nm = "z%d" % nl.n
                nl.gates[nm] = dict(kind="inv", ins=[cur], level=L + 1, delay=True)
                nl.order.append(nm)
                chains[k2] = nm
                added += 1
                cur = nm
            L += 1
        chains[key] = cur
        return cur

    for g in list(nl.order):
        d = nl.gates[g]
        if d.get("delay"):
            continue
        bg = bank_of(d["level"])
        for ix, u in enumerate(d["ins"]):
            if u in ("0", "1"):
                continue
            bu = bank_of(nl.level(u))
            if bg - bu >= 2:
                lvl = D_LEVELS * (bg - 2) + 1        # first level of bank bg-1
                d["ins"][ix] = tap(u, lvl)
    # primary outputs produced before the last bank are carried to the last
    # bank by delay chains (the word must leave the final bank aligned)
    NB = bank_of(max(nl.gates[g]["level"] for g in nl.gates))
    new_outs = []
    for o, bi in nl.outs:
        if bank_of(nl.gates[o]["level"]) < NB:
            o2 = tap(o, D_LEVELS * (NB - 1) + 1)
            nl.gates[o2]["out"] = bi
            new_outs.append((o2, bi))
        else:
            new_outs.append((o, bi))
    nl.outs = new_outs
    # re-sort order topologically by level (delays were appended)
    nl.order.sort(key=lambda g: (nl.gates[g]["level"], g))
    return added


def insert_delays_last(nl):
    """RETIME=last (name kept; the rule is the level-ORDER rule): a producer at
    level-in-bank j of bank k may feed a consumer at level-in-bank i of bank
    k+1 only if j >= i. Reason (measured on the d=2 blocks): a bank's outputs
    are destroyed by the death of ITS inputs one gate delay per level after
    bank k-1 dies, i.e. at slot(k+1)+lag+j*d, while the consumer commits at
    slot(k+1)+r+i*d with r-lag ~ -20 ps; j >= i keeps the validity pulse
    stationary, j < i kills it (edge census: mul8 had 78 (1->2) edges, the
    calibration lane has none). Inputs are carried by inverter chains to the
    deepest level of bank k that the chain parity allows (nand-only logic has
    no same-level complement); a consumer whose input can only be delivered
    at a shallower level than its own level-in-bank is pushed one level later
    and the pass repeats (levels only increase -> terminates)."""
    chains = {}
    added = 0

    def tap(src, lvl):
        """node with src's polarity at level lvl (>= level(src)), or None if
        no inverter chain of the right parity ends exactly there."""
        nonlocal added
        if lvl == nl.level(src):
            return src
        key = (src, lvl)
        if key in chains:
            return chains[key]
        m = lvl - nl.level(src)
        c = nl.comp.get(src)
        if m % 2 == 0:
            start = src
        elif c is not None and c not in ("0", "1") and nl.level(c) < lvl and \
                (lvl - nl.level(c)) % 2 == 1:
            start = c
        else:
            return None
        cur, L = start, nl.level(start)
        while L < lvl:
            k2 = (start, L + 1, "chain")
            if k2 in chains:
                cur = chains[k2]
            else:
                nl.n += 1
                nm = "z%d" % nl.n
                nl.gates[nm] = dict(kind="inv", ins=[cur], level=L + 1, delay=True)
                nl.order.append(nm)
                chains[k2] = nm
                added += 1
                cur = nm
            L += 1
        chains[key] = cur
        return cur

    def lib(level):                     # level-in-bank, 1..D_LEVELS
        return (level - 1) % D_LEVELS + 1

    for _ in range(1000):
        nl.order.sort(key=lambda g: (nl.gates[g]["level"], g))
        changed = False
        for g in list(nl.order):
            d = nl.gates[g]
            if d.get("delay"):
                continue
            lg = d["level"]
            bg, ig = bank_of(lg), lib(lg)
            for ix, u in enumerate(d["ins"]):
                if u in ("0", "1"):
                    continue
                lu = nl.level(u)
                bu = bank_of(lu)
                if bu == bg:
                    continue
                if bu == bg - 1 and lib(lu) >= ig:
                    continue                                   # j >= i: valid as is
                # carry u to the deepest level of bank bg-1 with j >= i
                t = None
                for j in range(D_LEVELS, ig - 1, -1):
                    t = tap(u, D_LEVELS * (bg - 2) + j)
                    if t is not None:
                        break
                if t is None:                                  # push the consumer one level
                    d["level"] += 1
                    changed = True
                    break
                d["ins"][ix] = t
                changed = True
        nl.order.sort(key=lambda g: (nl.gates[g]["level"], g))
        for g in nl.order:                                     # pushes propagate
            d = nl.gates[g]
            lv = 1 + max(nl.level(i) for i in d["ins"])
            if d["level"] < lv:
                d["level"] = lv
                changed = True
        if not changed:
            break
    else:
        raise RuntimeError("retime pass did not converge")
    # primary outputs: carried into the last bank, as deep as parity allows
    NB = bank_of(max(nl.gates[g]["level"] for g in nl.gates))
    new_outs = []
    for o, bi in nl.outs:
        t = None
        for j in range(D_LEVELS, 0, -1):
            t = tap(o, D_LEVELS * (NB - 1) + j)
            if t is not None:
                break
        assert t is not None, ("output carry", o)
        nl.gates[t]["out"] = bi
        new_outs.append((t, bi))
    nl.outs = new_outs
    nl.order.sort(key=lambda g: (nl.gates[g]["level"], g))
    return added


def jsonable(x):
    if isinstance(x, dict):
        return {str(k): jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [jsonable(v) for v in x]
    if isinstance(x, (np.bool_,)):
        return bool(x)
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating,)):
        return float(x)
    return x


def boundary_sets(nl):
    """bank -> sorted list of gate names consumed by bank+1 (bank NB: outputs)."""
    NB = bank_of(nl.stats()["levels"])
    cons = {}
    for g in nl.order:
        bg = bank_of(nl.gates[g]["level"])
        for u in nl.gates[g]["ins"]:
            if u in nl.gates:
                bu = bank_of(nl.gates[u]["level"])
                assert bg - bu in (0, 1), (g, u, bg, bu)
                if bg == bu + 1:
                    cons.setdefault(bu, set()).add(u)
    out = {k: sorted(cons.get(k, set())) for k in range(1, NB)}
    out[NB] = [o for o, _ in nl.outs]
    for o, _ in nl.outs:
        assert bank_of(nl.gates[o]["level"]) == NB, (o, nl.gates[o]["level"], NB)
    return NB, out


# ============================================================== blocks
def crc32_ref(state, data):
    for b in range(32):
        bit = (data >> (31 - b)) & 1
        fb = ((state >> 31) & 1) ^ bit
        state = ((state << 1) & 0xFFFFFFFF) ^ (POLY if fb else 0)
    return state


def crc32_terms():
    st = [frozenset([i]) for i in range(32)]
    for b in range(32):
        d = frozenset([32 + b])
        fb = st[31] ^ d
        st = [((st[i - 1] if i > 0 else frozenset()) ^ fb) if (POLY >> i) & 1
              else (st[i - 1] if i > 0 else frozenset()) for i in range(32)]
    return st


def xor_tree(nl, leaves):
    """leaves: list of (y, yn). Leaves at depth D or D-1 only (PRE_REGISTERED):
    pair 2(n - 2^(D-1)) leaves first, then a perfect tree."""
    n = len(leaves)
    if n == 1:
        return leaves[0]
    D = math.ceil(math.log2(n))
    k = n - 2 ** (D - 1)        # number of pairs at the deepest level
    cur = []
    for i in range(k):
        a, b = leaves[2 * i], leaves[2 * i + 1]
        cur.append(nl.xor_dual(a[0], a[1], b[0], b[1]))
    cur += leaves[2 * k:]
    while len(cur) > 1:
        nxt = []
        for i in range(0, len(cur), 2):
            a, b = cur[i], cur[i + 1]
            nxt.append(nl.xor_dual(a[0], a[1], b[0], b[1]))
        cur = nxt
    return cur[0]


def build_crc(trees=None):
    nl = Net()
    names = {}
    for i in range(32):
        names[i] = (nl.pi("s%d" % i, "sn%d" % i), "sn%d" % i)
    for b in range(32):
        names[32 + b] = (nl.pi("d%d" % b, "dn%d" % b), "dn%d" % b)
    terms = crc32_terms()
    for i in (trees if trees is not None else range(32)):
        leaves = [names[j] for j in sorted(terms[i])]
        y, yn = xor_tree(nl, leaves)
        nl.gates[y]["out"] = i
        nl.outs.append((y, i))
    return nl


def crc_pivals(word):
    state, data = word >> 32, word & 0xFFFFFFFF
    v = {}
    for i in range(32):
        v["s%d" % i] = (state >> i) & 1
        v["sn%d" % i] = 1 - v["s%d" % i]
    for b in range(32):
        v["d%d" % b] = (data >> (31 - b)) & 1
        v["dn%d" % b] = 1 - v["d%d" % b]
    return v


def build_mul(N):
    nl = Net()
    A = [(nl.pi("a%d" % i, "an%d" % i), "an%d" % i) for i in range(N)]
    B = [(nl.pi("b%d" % i, "bn%d" % i), "bn%d" % i) for i in range(N)]
    cols = [[] for _ in range(2 * N)]
    for i in range(N):
        for j in range(N):
            p, pn = nl.and_dual(A[i][0], B[j][0])
            cols[i + j].append((p, pn))
    # Dadda heights
    heights = [2]
    while heights[-1] < N:
        heights.append(int(math.floor(1.5 * heights[-1])))
    for d in reversed(heights[:-1] if heights[-1] >= N else heights):
        if d >= N:
            continue
        newcols = [[] for _ in range(2 * N)]
        carry = []
        for j in range(2 * N):
            sig = sorted(cols[j] + carry, key=lambda s: nl.level(s[0]))
            carry = []
            while len(sig) > d:
                if len(sig) - d >= 2:
                    a, b, c = sig[0], sig[1], sig[2]
                    s, sn, co, con = nl.fa_dual(a[0], a[1], b[0], b[1], c[0], c[1])
                    sig = sig[3:]
                else:
                    a, b = sig[0], sig[1]
                    s, sn, co, con = nl.ha_dual(a[0], a[1], b[0], b[1])
                    sig = sig[2:]
                sig.append((s, sn))
                sig.sort(key=lambda s: nl.level(s[0]))
                carry.append((co, con))
            newcols[j] = sig
        cols = newcols
    # final adder: Kogge-Stone over columns with <= 2 entries
    W = 2 * N
    X, Y = [], []
    for j in range(W):
        c = cols[j]
        assert len(c) <= 2, (j, len(c))
        X.append(c[0] if len(c) > 0 else ("0", "1"))
        Y.append(c[1] if len(c) > 1 else ("0", "1"))
    G, P = [], []
    for j in range(W):
        g, gn = nl.and_dual(X[j][0], Y[j][0])
        p, pn = nl.xor_dual(X[j][0], X[j][1], Y[j][0], Y[j][1])
        G.append((g, gn))
        P.append((p, pn))
    P0 = list(P)
    span = 1
    while span < W:
        G2, P2 = list(G), list(P)
        for j in range(span, W):
            g, gn = G[j]
            p, pn = P[j]
            gl, gln = G[j - span]
            pl, pln = P[j - span]
            # G_new = g | p&gl ; Gn_new = gn & (pn | gln)
            if gl == "0":
                gnew, gnnew = g, gn
            elif g == "1":
                gnew, gnnew = "1", "0"
            elif p == "0":
                gnew, gnnew = g, gn
            elif p == "1":
                # g | gl
                gnew = nl.nand(gn, gln)
                gnnew = nl.inv(gnew) if gnew not in ("0", "1") else ("1" if gnew == "0" else "0")
                nl.pair(gnew, gnnew)
            else:
                t = nl.nand(p, gl)
                gnew = nl.nand(gn, t)
                u1 = nl.nand(gn, pn)
                u2 = nl.nand(gn, gln)
                gnnew = nl.nand(u1, u2)
                nl.pair(gnew, gnnew)
            if p == "0" or pl == "0":
                pnew, pnnew = "0", "1"
            elif p == "1":
                pnew, pnnew = pl, pln
            elif pl == "1":
                pnew, pnnew = p, pn
            else:
                pnnew = nl.nand(p, pl)
                pnew = nl.inv(pnnew)
                nl.pair(pnew, pnnew)
            G2[j] = (gnew, gnnew)
            P2[j] = (pnew, pnnew)
        G, P = G2, P2
        span *= 2
    # sums
    for j in range(W):
        p, pn = P0[j]
        if j == 0:
            s = p
        else:
            c, cn = G[j - 1]
            if c == "0":
                s = p
            elif c == "1":
                s = pn
            elif p == "0":
                s = c
            elif p == "1":
                s = cn
            else:
                s = nl.nand(nl.nand(p, cn), nl.nand(pn, c))
        if s in ("0", "1"):
            raise RuntimeError("constant output bit %d" % j)
        nl.gates[s]["out"] = j
        nl.outs.append((s, j))
    return nl


def mul_pivals(N, word):
    a, b = word >> N, word & ((1 << N) - 1)
    v = {}
    for i in range(N):
        v["a%d" % i] = (a >> i) & 1
        v["an%d" % i] = 1 - v["a%d" % i]
        v["b%d" % i] = (b >> i) & 1
        v["bn%d" % i] = 1 - v["b%d" % i]
    return v


def build_mesh3_ic(d=3, kind="inv", nb=6):
    """mesh3 trap_tt92_d3 VERBATIM topology: 8 inverter chains x 18 levels;
    kind='nand' -> nand2(x,x) chains (the nand2 cell-class traversal lane:
    each output loads the next cell's BOTH gate inputs + CL)."""
    nl = Net()
    fan = int(os.environ.get("MB_FANOUT", "1"))   # extra identical consumers per node (dummy loads)
    for i in range(8):
        nl.pi("in1_%d" % i)
    if kind == "nandh":          # nand2 with the other input held HIGH (one-pMOS pull-up); one HIGH
        for i in range(8):       # source per chain so its delay taps carry the chain's own fanout only
            nl.pi("hi_%d" % i)
    if kind == "xorh":           # the CRC primitive as a lane: dual-rail depth-2 XOR with a real
        for i in range(8):       # (HIGH, LOW) pair per chain (PIs, so nothing folds): y = a ^ 1 = a~
            nl.pi("hi_%d" % i)
            nl.pi("lo_%d" % i)
            nl.pi("in1n_%d" % i)
            nl.comp["in1_%d" % i] = "in1n_%d" % i
            nl.comp["in1n_%d" % i] = "in1_%d" % i
    for i in range(8):
        if kind == "xorh":
            cur, curn = "in1_%d" % i, "in1n_%d" % i
            for j in range(nb * d // 2):
                cur, curn = nl.xor_dual(cur, curn, "hi_%d" % i, "lo_%d" % i)
            nl.gates[cur]["out"] = i
            nl.outs.append((cur, i))
            continue
        cell = {"inv": nl.inv, "nand": lambda x: nl.nand(x, x),
                "nandh": lambda x, i=i: nl.nand(x, "hi_%d" % i)}[kind]
        cur = "in1_%d" % i
        for j in range(nb * d):
            nxt = cell(cur)
            for _ in range(fan - 1):
                cell(cur)
            cur = nxt
        nl.gates[cur]["out"] = i
        nl.outs.append((cur, i))
    return nl


# ============================================================== words
def make_words(block, N=8):
    rng = np.random.RandomState(SEED)
    words, refs = [], []
    for n in range(NW):
        if block == "crc":
            state = int(rng.randint(0, 1 << 32, dtype=np.uint64))
            data = int(rng.randint(0, 1 << 32, dtype=np.uint64))
            words.append((state << 32) | data)
            refs.append(crc32_ref(state, data))
        elif block == "mul":
            a = int(rng.randint(0, 1 << N))
            b = int(rng.randint(0, 1 << N))
            words.append((a << N) | b)
            refs.append(a * b)
        else:  # mesh3 IC: PAT / ~PAT alternating
            pat = [1, 1, 1, 0, 1, 0, 0, 1]
            w = sum(((pat[i] ^ (n & 1)) << i) for i in range(8))
            words.append(w)
            refs.append(None)
    return words, refs


def pivals_of(block, word, N=8):
    if block == "crc":
        return crc_pivals(word)
    if block == "mul":
        return mul_pivals(N, word)
    v = {"in1_%d" % i: (word >> i) & 1 for i in range(8)}
    for i in range(8):
        v["hi_%d" % i] = 1
        v["lo_%d" % i] = 0
        v["in1n_%d" % i] = 1 - v["in1_%d" % i]
    return v


# ============================================================== decks
def trap_pts(p, tt, T, tend):
    pts, m = [], -2
    while m * T + p * tt < tend + T:
        t0 = m * T + p * tt
        pts += [(t0, 0.0), (t0 + tt, DV), (t0 + 2 * tt, DV)]
        m += 1
    return sorted((t, v) for (t, v) in pts if t >= -1e-12)


def head_pts(vals, T, nw):
    """PWL for one head bit over waves 0..nw-1 (new value at n*T, 2 ps edge)."""
    pts, cur = [(0.0, DV * vals[0])], DV * vals[0]
    for n in range(1, nw):
        nxt = DV * vals[n]
        if nxt != cur:
            pts += [(n * T - EDGE / 2, cur), (n * T + EDGE / 2, nxt)]
            cur = nxt
    if len(pts) == 1:                      # VACASK pwl needs >= 2 points (constant bit)
        pts.append((nw * T, cur))
    return pts


def plan(block, nl, tt, nw, N=8):
    NB, bsets = boundary_sets(nl)
    T = 3.0 * tt
    tend = (nw - 1) * T + (NB - 1) * tt + 3 * tt + 50.0
    words, refs = make_words(block, N)
    words, refs = words[:nw], refs[:nw]
    piv = [pivals_of(block, w, N) for w in words]
    vals = [nl.eval(p) for p in piv]
    return dict(block=block, NB=NB, bsets=bsets, T=T, tt=tt, tend=tend, nw=nw,
                words=words, refs=refs, piv=piv, vals=vals,
                stats=nl.stats())


def deck_vacask(block, nl, P, title):
    NB, tt, T, tend, nw = P["NB"], P["tt"], P["T"], P["tend"], P["nw"]
    ps = 1e-12
    L = [title,
         'load "%s/psp103v4.osdi"' % OSDI, 'load "%s/capacitor.osdi"' % OSDI,
         'load "%s/spice/resistor.osdi"' % OSDI,
         'include "%s"' % MODELS_INC,
         "model v vsource", "model rmod sp_resistor", "model cmod capacitor",
         "subckt sg13_lv_nmos (d g s b)", "  parameters w=0.15u l=0.13u",
         "  m1 (d g s b) sg13g2_nmos w=w l=l", "ends",
         "subckt sg13_lv_pmos (d g s b)", "  parameters w=0.15u l=0.13u",
         "  m1 (d g s b) sg13g2_pmos w=w l=l", "ends"]
    for k in range(1, NB + 1):
        p = (k - 1) % 3
        pts = trap_pts(p, tt, T, tend)
        L.append("vph%d (phs%d 0) v type=\"pwl\" wave=[%s]"
                 % (k, k, ", ".join("%.6g,%g" % (t * ps, v) for t, v in pts)))
        L.append("rs%d (phs%d ph%d) rmod r=0.001" % (k, k, k))
        L.append("vmg%d (gn%d 0) v dc=0" % (k, k))
    for pi_ in nl.pis:
        vals = [pv[pi_] for pv in P["piv"]]
        pts = head_pts(vals, T, nw)
        L.append("vi_%s (%s 0) v type=\"pwl\" wave=[%s]"
                 % (pi_, pi_, ", ".join("%.6g,%g" % (t * ps, v) for t, v in pts)))
    for g in nl.order:
        d = nl.gates[g]
        k = bank_of(d["level"])
        if d["kind"] == "inv":
            a = d["ins"][0]
            L.append("xp_%s (%s %s ph%d ph%d) sg13_lv_pmos w=%gu l=%gu" % (g, g, a, k, k, WP, LCH))
            L.append("xn_%s (%s %s gn%d gn%d) sg13_lv_nmos w=%gu l=%gu" % (g, g, a, k, k, WN, LCH))
        else:
            a, b = d["ins"]
            L.append("xpa_%s (%s %s ph%d ph%d) sg13_lv_pmos w=%gu l=%gu" % (g, g, a, k, k, WP, LCH))
            L.append("xpb_%s (%s %s ph%d ph%d) sg13_lv_pmos w=%gu l=%gu" % (g, g, b, k, k, WP, LCH))
            L.append("xna_%s (%s %s m_%s gn%d) sg13_lv_nmos w=%gu l=%gu" % (g, g, a, g, k, WN, LCH))
            L.append("xnb_%s (m_%s %s gn%d gn%d) sg13_lv_nmos w=%gu l=%gu" % (g, g, b, k, k, WN, LCH))
        L.append("cl_%s (%s gn%d) cmod c=%gf" % (g, g, k, CLOAD))
    L.append("control")
    L.append('  options tran_method="gear" reltol=1e-5')
    sv = ["v(ph%d)" % k for k in range(1, NB + 1)] + \
         ["i(vph%d)" % k for k in range(1, NB + 1)] + \
         ["i(vmg%d)" % k for k in range(1, NB + 1)]
    for k in range(1, NB + 1):
        sv += ["v(%s)" % s for s in P["bsets"][k]]
    for i in range(0, len(sv), 20):
        L.append("  save " + " ".join(sv[i:i + 20]))
    L.append("  analysis tr tran step=0.1p stop=%.6gp maxstep=0.25p icmode=\"op\"" % tend)
    L.append("endc")
    return L


def deck_xyce(block, nl, P, title):
    NB, tt, T, tend, nw = P["NB"], P["tt"], P["T"], P["tend"], P["nw"]
    L = ["* " + title, '.hdl "%s"' % XVA, '.include "%s"' % XMODEL, '.include "%s"' % XSHIM,
         '.OPTIONS TIMEINT METHOD=GEAR RELTOL=1e-6 ABSTOL=1e-15 CHGTOL=1e-17']
    fmt = lambda pts: " ".join("%gp %g" % (t, v) if t > 1e-12 else "0 %g" % v for t, v in pts)
    for k in range(1, NB + 1):
        p = (k - 1) % 3
        L.append("VPH%d phs%d 0 PWL(%s)" % (k, k, fmt(trap_pts(p, tt, T, tend))))
        L.append("RS%d phs%d ph%d 0.001" % (k, k, k))
        L.append("VMG%d gn%d 0 0" % (k, k))
    for pi_ in nl.pis:
        vals = [pv[pi_] for pv in P["piv"]]
        L.append("VI_%s %s 0 PWL(%s)" % (pi_, pi_, fmt(head_pts(vals, T, nw))))
    for g in nl.order:
        d = nl.gates[g]
        k = bank_of(d["level"])
        if d["kind"] == "inv":
            a = d["ins"][0]
            L.append("XP_%s %s %s ph%d ph%d sg13_lv_pmos w=%gu l=%gu" % (g, g, a, k, k, WP, LCH))
            L.append("XN_%s %s %s gn%d gn%d sg13_lv_nmos w=%gu l=%gu" % (g, g, a, k, k, WN, LCH))
        else:
            a, b = d["ins"]
            L.append("XPA_%s %s %s ph%d ph%d sg13_lv_pmos w=%gu l=%gu" % (g, g, a, k, k, WP, LCH))
            L.append("XPB_%s %s %s ph%d ph%d sg13_lv_pmos w=%gu l=%gu" % (g, g, b, k, k, WP, LCH))
            L.append("XNA_%s %s %s m_%s gn%d sg13_lv_nmos w=%gu l=%gu" % (g, g, a, g, k, WN, LCH))
            L.append("XNB_%s m_%s %s gn%d gn%d sg13_lv_nmos w=%gu l=%gu" % (g, g, b, k, k, WN, LCH))
        L.append("CL_%s %s gn%d %gf" % (g, g, k, CLOAD))
    L.append(".tran 0.1p %gp 0 0.25p" % tend)
    pr = ["V(ph%d)" % k for k in range(1, NB + 1)] + \
         ["I(VPH%d)" % k for k in range(1, NB + 1)] + \
         ["I(VMG%d)" % k for k in range(1, NB + 1)]
    for k in range(1, NB + 1):
        pr += ["V(%s)" % s for s in P["bsets"][k]]
    L.append(".print tran " + " ".join(pr))
    L.append(".end")
    return L


# ============================================================== running
def run_vacask(rundir, fn, lines, timeout=4 * 3600):
    os.makedirs(rundir, exist_ok=True)
    path = os.path.join(rundir, fn)
    open(path, "w").write("\n".join(lines) + "\n")
    t0 = time.monotonic()
    try:
        r = subprocess.run([VACASK, fn], capture_output=True, text=True,
                           timeout=timeout, cwd=rundir)
    except subprocess.TimeoutExpired:
        return None, "TIMEOUT", timeout
    wall = time.monotonic() - t0
    raw = os.path.join(rundir, "tr.raw")
    open(path + ".log", "w").write(r.stdout + "\n--- stderr ---\n" + r.stderr)
    if r.returncode != 0 or not os.path.exists(raw):
        return None, "VACASK FAIL rc=%d: %s" % (r.returncode, (r.stderr or r.stdout)[-600:]), wall
    return raw, "ran %s in %.1fs" % (fn, wall), wall


def run_xyce(rundir, fn, lines, timeout=6 * 3600):
    os.makedirs(rundir, exist_ok=True)
    path = os.path.join(rundir, fn)
    open(path, "w").write("\n".join(lines) + "\n")
    t0 = time.monotonic()
    try:
        r = subprocess.run([XYCE, fn], capture_output=True, text=True,
                           timeout=timeout, cwd=rundir, env=XENV)
    except subprocess.TimeoutExpired:
        return None, "TIMEOUT", timeout
    wall = time.monotonic() - t0
    open(path + ".log", "w").write(r.stdout)
    if r.returncode != 0 or not os.path.exists(path + ".prn"):
        err = "; ".join(l.strip() for l in r.stdout.splitlines() if "rror" in l)[:600]
        return None, "XYCE FAIL: " + (err or r.stdout[-400:]), wall
    if "PSP103" not in r.stdout:
        return None, "XYCE ran WITHOUT PSP103 registration -- silently wrong, rejected", wall
    return path + ".prn", "ran %s in %.1fs" % (fn, wall), wall


class Waves(object):
    """engine-neutral waveform store: t (ps), columns by canonical name."""
    def __init__(self, t, cols):
        self.t = t
        self.cols = cols

    @staticmethod
    def from_raw(path):
        from rawfile import rawread
        p = rawread(path).get()
        names = list(p.names)
        data = np.asarray(p.data, dtype=np.float64)
        cols = {}
        for i, nm in enumerate(names):
            n = nm.lower()
            if n == "time":
                t = data[:, i] * 1e12
                continue
            m = re.match(r"(\w+):flow\(br\)", n)
            if m:
                cols["I(" + m.group(1).upper() + ")"] = data[:, i]
            else:
                cols["V(" + n.upper() + ")"] = data[:, i]
        return Waves(t, cols)

    @staticmethod
    def from_prn(path):
        hdr, rows = None, []
        for ln in open(path):
            p = ln.split()
            if hdr is None:
                if p and p[0].lower() == "index":
                    hdr = [h.upper() for h in p]
                continue
            if not p or p[0].lower().startswith("end"):
                continue
            try:
                rows.append([float(x) for x in p])
            except ValueError:
                continue
        a = np.array(rows)
        ti = hdr.index("TIME")
        cols = {hdr[i]: a[:, i] for i in range(len(hdr)) if hdr[i] not in ("INDEX", "TIME")}
        return Waves(a[:, ti] * 1e12, cols)

    def grid(self, names, t0, t1):
        """linear interpolation of the named columns on the 0.10 ps grid [t0,t1]."""
        a0 = max(0, int(math.floor(t0 / GRID)))
        a1 = int(math.floor(t1 / GRID))
        tg = np.arange(a0, a1 + 1) * GRID
        tg = np.minimum(tg, self.t[-1])
        idx = np.searchsorted(self.t, tg, side="right")
        idx = np.clip(idx, 1, len(self.t) - 1)
        ta, tb = self.t[idx - 1], self.t[idx]
        f = np.where(tb > ta, (tg - ta) / np.maximum(tb - ta, 1e-30), 0.0)
        f = np.clip(f, 0.0, 1.0)
        out = np.empty((len(names), len(tg)))
        for i, nm in enumerate(names):
            y = self.cols[nm]
            out[i] = y[idx - 1] + (y[idx] - y[idx - 1]) * f
        return a0, out

    def integ(self, name, t0, t1):
        """trapezoid integral of column over [t0,t1] ps on the engine grid (x1e-12 for s)."""
        t, y = self.t, self.cols[name]
        i0 = np.searchsorted(t, t0)
        i1 = np.searchsorted(t, t1)
        y0 = np.interp(t0, t, y)
        y1 = np.interp(t1, t, y)
        tt = np.concatenate(([t0], t[i0:i1], [t1]))
        yy = np.concatenate(([y0], y[i0:i1], [y1]))
        return float(np.sum(0.5 * (yy[1:] + yy[:-1]) * np.diff(tt))) * 1e-12


# ============================================================== trip
class Trip(object):
    def __init__(self, path=TRIPJSON, tag="S"):
        d = json.load(open(path))[tag]
        ks = sorted(d["rows"], key=float)
        v = [d["rows"][k]["vdd"] for k in ks]
        t = [d["rows"][k]["trip_V"] for k in ks]
        keep = [i for i in range(len(v)) if t[i] is not None]
        self.v = np.array([v[i] for i in keep])
        self.t = np.array([t[i] for i in keep])
        self.lo, self.hi = self.v[0], self.v[-1]

    def __call__(self, vdd):
        vdd = np.asarray(vdd, dtype=float)
        tr = np.interp(vdd, self.v, self.t)
        tr = np.where(vdd <= self.lo, self.t[0] * vdd / self.lo, tr)
        tr = np.where(vdd >= self.hi, self.t[-1] * vdd / self.hi, tr)
        return tr, (vdd >= self.hi)


TRIPF = Trip()


def runs_of(mask):
    m = np.concatenate(([0], mask.astype(np.int8), [0]))
    d = np.diff(m)
    starts = np.where(d == 1)[0]
    ends = np.where(d == -1)[0] - 1
    return list(zip(starts, ends))


def edge_interp(cur, a, b, thr):
    ta, tb = a * GRID, b * GRID
    n = len(cur)
    if a - 1 >= 0 and cur[a - 1] <= thr < cur[a]:
        ta = (a - 1) * GRID + (thr - cur[a - 1]) * GRID / (cur[a] - cur[a - 1])
    if b + 1 < n and cur[b + 1] <= thr < cur[b]:
        tb = b * GRID + (thr - cur[b]) * GRID / (cur[b + 1] - cur[b])
    return ta, tb


# ============================================================== extraction
def extract(W, nl, P, waves=None, keep_curves=False):
    NB, tt, T, bsets = P["NB"], P["tt"], P["T"], P["bsets"]
    co = 1.5 * tt
    if waves is None:
        waves = list(range(2, P["nw"]))
    slot = lambda k, n: n * T + (k - 1) * tt
    rxbank = lambda k: k + 1 if k < NB else (NB % 3) + 1
    out = dict(block=P["block"], NB=NB, tt=tt, T=T, nw=P["nw"], waves=waves,
               stats=P["stats"], n_boundary={k: len(bsets[k]) for k in bsets})
    links, handoff = {}, {}
    tcommit, tdie = {}, {}
    vfails, vchecked = [], 0
    final_words = {}
    lags = []
    for k in range(1, NB + 1):
        sigs = ["V(%s)" % s.upper() for s in bsets[k]]
        links[k] = {}
        for n in waves:
            srx = slot(k + 1, n)
            sk = srx - tt
            t0, t1 = sk - 10.0, srx + 2 * tt + 40.0
            a0, Y = W.grid(sigs + ["V(PH%d)" % rxbank(k), "V(PH%d)" % k], t0, t1)
            outs, rx_rail, own_rail = Y[:-2], Y[-2], Y[-1]
            trip, ex = TRIPF(rx_rail)
            intab = rx_rail >= TRIPF.lo
            bb = np.array([P["vals"][n][s] for s in bsets[k]])
            sg = np.where(bb == 1, 1.0, -1.0)[:, None]
            marg = 1000.0 * sg * (outs - trip[None, :])
            cur = marg.min(axis=0)
            his, los = np.where(bb == 1)[0], np.where(bb == 0)[0]
            curH = marg[his].min(axis=0) if len(his) else None
            curL = marg[los].min(axis=0) if len(los) else None
            rec = dict(rx_derived=(k == NB), wave=n, srx_ps=srx)
            for thr_name, thr in (("0mV", 0.0), ("gate", GATE_MV)):
                mask = intab & (cur > thr)
                rr = runs_of(mask)
                r0 = int(srx / GRID) - a0
                r1 = int((srx + co) / GRID) - a0
                pick = None
                for (a, b) in rr:
                    if b >= r0 and a <= r1 and (pick is None or (b - a) > (pick[1] - pick[0])):
                        pick = (a, b)
                if pick is None:
                    rec[thr_name] = dict(EYE="EMPTY_in_rise_window", n_runs=len(rr))
                    continue
                ta, tb = edge_interp(cur, pick[0], pick[1], thr)
                ta += a0 * GRID
                tb += a0 * GRID
                rec[thr_name] = dict(open_ps=round(ta, 3), close_ps=round(tb, 3),
                                     width_ps=round(tb - ta, 3),
                                     open_minus_srx_ps=round(ta - srx, 3),
                                     clipped_end=bool(pick[1] >= len(cur) - 1))
                if thr_name == "0mV":
                    rec["commit_gated_ps"] = round(ta, 3)
                    rec["die_ps"] = round(tb, 3)
                else:
                    rec["commit_gate69_ps"] = round(ta, 3)
            # commit_raw from the bank's OWN powered window [sk, sk+2tt]
            rr2 = runs_of(cur > 0.0)
            q0 = int(sk / GRID) - a0
            q1 = int((sk + 2 * tt) / GRID) - a0
            pick2 = None
            for (a, b) in rr2:
                if b >= q0 and a <= q1 and (pick2 is None or (b - a) > (pick2[1] - pick2[0])):
                    pick2 = (a, b)
            if pick2 is not None:
                ta2, tb2 = edge_interp(cur, pick2[0], pick2[1], 0.0)
                rec["commit_raw_ps"] = round(ta2 + a0 * GRID, 3)
                rec["die_raw_ps"] = round(tb2 + a0 * GRID, 3)
                tcommit[(k, n)] = ta2 + a0 * GRID
                tdie[(k, n)] = tb2 + a0 * GRID
                # gated-margin commit (69.924 mV) inside the same run
                m69 = np.where(cur[pick2[0]:pick2[1] + 1] > GATE_MV)[0]
                rec["commit_raw_gate69_ps"] = (round((pick2[0] + m69[0] + a0) * GRID, 3)
                                               if len(m69) else None)
            else:
                rec["commit_raw_ps"] = None
            probe = min(len(cur) - 1, int((srx + co) / GRID) - a0)
            rec["margin_at_rx_crest_mV"] = dict(
                all=round(float(cur[probe]), 2),
                HIGH=round(float(curH[probe]), 2) if curH is not None else None,
                LOW=round(float(curL[probe]), 2) if curL is not None else None)
            # value at the raw-validity midpoint
            if (k, n) in tcommit:
                am = int(0.5 * (tcommit[(k, n)] + tdie[(k, n)]) / GRID) - a0
                am = min(max(am, 0), len(cur) - 1)
                vchecked += len(sigs)
                bad = np.where(marg[:, am] <= 0.0)[0]
                for i in bad:
                    vfails.append([k, n, bsets[k][i], round(float(outs[i, am]), 4),
                                   round(float(trip[am]), 4)])
                if k == NB:
                    bitsv = {}
                    for i, (s, bi) in enumerate(nl.outs):
                        bitsv[bi] = int(outs[i, am] > trip[am])
                    word = sum(v << b for b, v in bitsv.items())
                    final_words[n] = word
            else:
                vfails.append([k, n, "NO_COMMIT"])
            # rising-side tracking lag (last boundary HIGH 50% after rail 50%)
            s0 = slot(k, n)
            i0 = max(1, int(s0 / GRID) - a0)
            i1 = min(len(cur) - 1, int((s0 + co) / GRID) - a0)
            r50 = np.where((own_rail[i0 - 1:i1] < 0.5 * DV) & (own_rail[i0:i1 + 1] >= 0.5 * DV))[0]
            if len(r50) and len(his):
                tr50 = (i0 + r50[0]) * GRID
                worst = None
                seg = outs[his][:, i0:min(len(cur), i1 + int(1.5 * tt / GRID))]
                cross = (seg[:, :-1] < 0.5 * DV) & (seg[:, 1:] >= 0.5 * DV)
                for row in cross:
                    w = np.where(row)[0]
                    if len(w):
                        worst = max(worst or 0.0, (i0 + w[0] + 1) * GRID - tr50)
                if worst is not None:
                    lags.append(round(worst, 1))
            links[k][n] = rec
    # handoff
    for k in range(1, NB):
        handoff[k] = {}
        for n in waves:
            tc_rx = tcommit.get((k + 1, n))
            die = links[k][n].get("die_ps")
            rec = dict(t_commit_rx_ps=(round(tc_rx, 3) if tc_rx else None), t_die_ps=die)
            if tc_rx is not None and die is not None:
                rec["overlap_ps"] = round(die - tc_rx, 3)
            if tc_rx is not None:
                sigs = ["V(%s)" % s.upper() for s in bsets[k]]
                a0, Y = W.grid(sigs + ["V(PH%d)" % rxbank(k)], tc_rx - 0.2, tc_rx + 0.2)
                a = min(len(Y[0]) - 1, int(tc_rx / GRID) - a0)
                t_, ex = TRIPF(Y[-1][a])
                bb = np.array([P["vals"][n][s] for s in bsets[k]])
                sg = np.where(bb == 1, 1.0, -1.0)
                mm = 1000.0 * sg * (Y[:-1, a] - t_)
                rec["margin_at_commit_mV"] = dict(
                    HIGH=(round(float(mm[bb == 1].min()), 2) if (bb == 1).any() else None),
                    LOW=(round(float(mm[bb == 0].min()), 2) if (bb == 0).any() else None))
                rec["trip_at_commit_V"] = round(float(t_), 4)
                rec["trip_extrapolated"] = bool(ex)
            handoff[k][n] = rec
    out["links"] = links
    out["handoff"] = handoff
    # final-word check vs software reference
    ref_ok, ref_bad = 0, []
    mask = sum(1 << bi for _, bi in nl.outs)
    for n in waves:
        ref = P["refs"][n]
        got = final_words.get(n)
        if ref is None:
            continue
        if got == (ref & mask):
            ref_ok += 1
        else:
            ref_bad.append([n, got, ref & mask])
    out["value"] = dict(checked=vchecked, n_fail=len(vfails), fails=vfails[:20],
                        PASS=(not vfails),
                        final_words_hw={n: final_words.get(n) for n in waves},
                        words_in={n: P["words"][n] for n in waves},
                        reference={n: P["refs"][n] for n in waves},
                        output_bit_mask=mask,
                        final_vs_reference=dict(ok=ref_ok, bad=ref_bad, PASS=(not ref_bad)))
    out["rising_lag_ps"] = dict(min=min(lags) if lags else None, max=max(lags) if lags else None,
                                median=sorted(lags)[len(lags) // 2] if lags else None)
    # latency per word
    lat = {}
    for n in waves:
        tc = tcommit.get((NB, n))
        tg = links[NB][n].get("commit_raw_gate69_ps")
        lat[n] = dict(commit_raw_ps=round(tc - n * T, 3) if tc else None,
                      commit_gate69_ps=round(tg - n * T, 3) if tg else None)
    lv = [v["commit_raw_ps"] for v in lat.values() if v["commit_raw_ps"] is not None]
    lg = [v["commit_gate69_ps"] for v in lat.values() if v["commit_gate69_ps"] is not None]
    out["latency_ps"] = dict(per_word=lat, max_raw=max(lv) if lv else None,
                             min_raw=min(lv) if lv else None,
                             max_gate69=max(lg) if lg else None,
                             definition="t_commit_raw(bank NB, word n) - n*T")
    # charge books per bank per third (offline trapezoid, scored waves)
    ch = {}
    for k in range(1, NB + 1):
        acc = {x: [] for x in ("qr", "qh", "qf", "er", "eh", "ef")}
        iname = "I(VPH%d)" % k
        rname = "V(PH%d)" % k
        for n in waves:
            s0 = slot(k, n)
            for key, (a, b) in (("r", (s0, s0 + tt)), ("h", (s0 + tt, s0 + 2 * tt)),
                                ("f", (s0 + 2 * tt, s0 + 3 * tt))):
                if b > W.t[-1]:
                    continue
                q = -W.integ(iname, a, b)
                # energy: integral of v*i
                t, iv, vv = W.t, W.cols[iname], W.cols[rname]
                i0 = np.searchsorted(t, a)
                i1 = np.searchsorted(t, b)
                tt_ = np.concatenate(([a], t[i0:i1], [b]))
                pp = np.concatenate(([np.interp(a, t, iv) * np.interp(a, t, vv)],
                                     iv[i0:i1] * vv[i0:i1],
                                     [np.interp(b, t, iv) * np.interp(b, t, vv)]))
                e = -float(np.sum(0.5 * (pp[1:] + pp[:-1]) * np.diff(tt_))) * 1e-12
                acc["q" + key].append(q * 1e15)
                acc["e" + key].append(e * 1e15)
        mean = lambda v: round(float(np.mean(v)), 3) if v else None
        ch[k] = dict(phase="ABC"[(k - 1) % 3], Q_rise_fC=mean(acc["qr"]), Q_hold_fC=mean(acc["qh"]),
                     Q_fall_fC=mean(acc["qf"]), E_rise_fJ=mean(acc["er"]), E_hold_fJ=mean(acc["eh"]),
                     E_fall_fJ=mean(acc["ef"]))
    out["charge_spec_reported_not_gated"] = ch
    # erosion / standing eye
    ero = {}
    for n in waves:
        wid = [links[k][n].get("0mV", {}).get("width_ps") for k in range(1, NB + 1)]
        ovs = [handoff[k][n].get("overlap_ps") for k in range(1, NB)]
        real = [w for w in wid[:NB - 1] if w is not None]
        sign = "EXTINCT"
        if len(real) == NB - 1 and real:
            sign = ("SUSTAINS" if real[-1] >= 0.85 * real[0] else
                    "ERODES_SLOW" if real[-1] >= 0.5 * real[0] else "ERODES")
        asym = None
        if len(real) >= 2 and real[-2] > 0 and abs(real[-1] - real[-2]) <= 0.15 * real[-2]:
            asym = round(0.5 * (real[-1] + real[-2]), 2)
        ero[n] = dict(width_0mV_ps_links=wid, overlaps_ps=ovs, sign=sign, asymptotic_width_ps=asym)
    out["erosion"] = ero
    # acceptance
    b_ok, c_ok, worst_m, worst_ov = True, True, None, None
    worst_m_where, worst_ov_where = None, None
    for k in range(1, NB):
        for n in waves:
            h = handoff[k][n]
            m = h.get("margin_at_commit_mV")
            if not m or all(v is None for v in m.values()):
                b_ok = False
                continue
            lo = min(v for v in m.values() if v is not None)
            if worst_m is None or lo < worst_m:
                worst_m, worst_m_where = lo, [k, n]
            if lo < GATE_MV:
                b_ok = False
            ov = h.get("overlap_ps")
            if ov is None or ov <= 0:
                c_ok = False
            if ov is not None and (worst_ov is None or ov < worst_ov):
                worst_ov, worst_ov_where = ov, [k, n]
    eyes = [links[k][n]["0mV"].get("width_ps") for k in range(1, NB) for n in waves
            if "width_ps" in links[k][n].get("0mV", {})]
    asyms = [e["asymptotic_width_ps"] for e in ero.values() if e["asymptotic_width_ps"]]
    out["acceptance"] = dict(
        A_value=bool(out["value"]["PASS"] and out["value"]["final_vs_reference"]["PASS"]),
        B_eye=b_ok, C_handoff=c_ok,
        worst_margin_at_commit_mV=worst_m, worst_margin_where=worst_m_where,
        worst_overlap_ps=worst_ov, worst_overlap_where=worst_ov_where,
        min_eye_0mV_real_links_ps=min(eyes) if eyes else None,
        standing_eye_ps=(round(float(np.mean(asyms)), 2) if asyms else None),
        PASS=bool(out["value"]["PASS"] and out["value"]["final_vs_reference"]["PASS"]
                  and b_ok and c_ok))
    return out


def summarize(o):
    a = o["acceptance"]
    return ("value=%s(ref %d ok/%d bad) eye=%s handoff=%s worst_margin=%s@%s worst_ov=%s@%s "
            "eye_min=%s standing=%s lat_raw=%s lat69=%s lag=%s -> %s"
            % (a["A_value"], o["value"]["final_vs_reference"]["ok"],
               len(o["value"]["final_vs_reference"]["bad"]), a["B_eye"], a["C_handoff"],
               a["worst_margin_at_commit_mV"], a["worst_margin_where"],
               a["worst_overlap_ps"], a["worst_overlap_where"],
               a["min_eye_0mV_real_links_ps"], a["standing_eye_ps"],
               o["latency_ps"]["max_raw"], o["latency_ps"]["max_gate69"],
               o["rising_lag_ps"], "PASS" if a["PASS"] else "FAIL"))


# ============================================================== block runs
def build_block(block, N=8, group=None):
    if block == "crc":
        trees = None if group is None else list(range(8 * group, 8 * group + 8))
        nl = build_crc(trees)
    elif block == "mul":
        nl = build_mul(N)
    elif block == "icn":
        nl = build_mesh3_ic(d=N, kind=os.environ.get("MB_ICN_KIND", "nand"))
    else:
        nl = build_mesh3_ic()
    nd = insert_delays(nl)
    return nl, nd


def functional_proof(block, N=8):
    nl, nd = build_block(block, N)
    rng = np.random.RandomState(1)
    bad = 0
    for _ in range(2000):
        if block == "crc":
            s, d = int(rng.randint(0, 1 << 32, dtype=np.uint64)), int(rng.randint(0, 1 << 32, dtype=np.uint64))
            v = nl.eval(crc_pivals((s << 32) | d))
            got = sum(v[o] << b for o, b in nl.outs)
            bad += (got != crc32_ref(s, d))
        else:
            a, b = int(rng.randint(0, 1 << N)), int(rng.randint(0, 1 << N))
            v = nl.eval(mul_pivals(N, (a << N) | b))
            got = sum(v[o] << bi for o, bi in nl.outs)
            bad += (got != a * b)
    st = nl.stats()
    NB, bs = boundary_sets(nl)
    return dict(block=block, N=N, vectors=2000, mismatches=bad, PASS=(bad == 0),
                stats=st, delay_inverters=nd, NB=NB,
                boundary_sizes={k: len(v) for k, v in bs.items()})


def keep(rundir, tag, o, extra=None):
    dst = os.path.join(HERE, "runs", tag)
    os.makedirs(dst, exist_ok=True)
    for f in os.listdir(rundir):
        if f.endswith((".sim", ".cir", ".log")):
            shutil.copy2(os.path.join(rundir, f), os.path.join(dst, f))
    if extra:
        o.update(extra)
    json.dump(jsonable(o), open(os.path.join(dst, "OUT.json"), "w"), indent=1)


def cmd_run(block, engine="vacask", N=8, group=None, nw=NW, tt=TT, tag=None, dlev=None, keep_raw=False):
    global D_LEVELS
    if dlev is not None:
        D_LEVELS = dlev
    nl, nd = build_block(block, N, group)
    P = plan(block, nl, tt, nw, N)
    P["delay_inverters"] = nd
    if tag is None:
        tag = "%s%s_%s_tt%g_nw%d" % (block, (N if block in ("mul", "icn") else ""),
                                     ("g%d" % group if group is not None else "all"), tt, nw)
        if D_LEVELS != 3:
            tag += "_d%d" % D_LEVELS
        if RETIME == "last":
            tag += "_rl"
        if block == "icn" and os.environ.get("MB_FANOUT", "1") != "1":
            tag += "_f%s" % os.environ["MB_FANOUT"]
        if block == "icn" and os.environ.get("MB_ICN_KIND", "nand") != "nand":
            tag += "_" + os.environ["MB_ICN_KIND"]
        if os.environ.get("MB_WP", "1") != "1":
            tag += "_wp%s" % os.environ["MB_WP"]
        if engine != "vacask":
            tag = engine + "_" + tag
    oj = os.path.join(HERE, "runs", tag, "OUT.json")
    if os.path.exists(oj):
        print("  cached", tag)
        return json.load(open(oj))
    rundir = os.path.join(SCRATCH, tag)
    title = "qal/mblocks %s" % tag
    print("  %s: %s NB=%d boundary=%s tend=%.0f" % (tag, P["stats"], P["NB"],
          {k: len(v) for k, v in P["bsets"].items()}, P["tend"]), flush=True)
    if engine == "vacask":
        raw, msg, wall = run_vacask(rundir, tag + ".sim", deck_vacask(block, nl, P, title))
    else:
        raw, msg, wall = run_xyce(rundir, tag + ".cir", deck_xyce(block, nl, P, title))
    print("  " + msg, flush=True)
    if raw is None:
        os.makedirs(os.path.dirname(oj), exist_ok=True)
        json.dump(dict(tag=tag, error=msg, wall_s=wall), open(oj, "w"), indent=1)
        return dict(error=msg, acceptance=dict(PASS=False))
    W = Waves.from_raw(raw) if engine == "vacask" else Waves.from_prn(raw)
    npts = len(W.t)
    o = extract(W, nl, P)
    o.update(tag=tag, engine=engine, wall_s=round(wall, 1), npts=npts,
             ms_per_pt=round(1000.0 * wall / npts, 2), delay_inverters=nd,
             fets=P["stats"]["fets"], group=group, N=N, d_levels=D_LEVELS, retime=RETIME,
             n_boundary={k: len(v) for k, v in P["bsets"].items()})
    keep(rundir, tag, o)
    if not (keep_raw or (os.environ.get("MB_KEEP_ON_FAIL") and not o["acceptance"]["PASS"])):
        os.remove(raw)
    print("  " + summarize(o), flush=True)
    return o


# ============================================================== IC
def cmd_ic():
    o = cmd_run("ic", "vacask", nw=7, tag="ic_mesh3_trap_tt92_d3_vacask")
    o = json.loads(json.dumps(jsonable(o)))     # string keys, as in the cached form
    o["links"] = {int(k): {int(n): v for n, v in d.items()} for k, d in o["links"].items()}
    o["charge_spec_reported_not_gated"] = {int(k): v for k, v in o["charge_spec_reported_not_gated"].items()}
    ref = json.load(open("/usr/local/src/stat-sim/qal/mesh3/runs/trap_tt92_d3/OUT.json"))
    ra = ref["acceptance"]
    chk = dict(
        value=(o["value"]["checked"], ref["value"]["checked"], o["value"]["n_fail"], ref["value"]["n_fail"]),
        worst_margin=(o["acceptance"]["worst_margin_at_commit_mV"], ra["worst_margin_at_commit_mV"]),
        worst_overlap=(o["acceptance"]["worst_overlap_ps"], ra["worst_overlap_ps"]),
        standing_eye=(o["acceptance"]["standing_eye_ps"], ref["erosion"]["3"]["asymptotic_width_ps"]),
        eye_link1_w2=(o["links"][1][2]["0mV"]["width_ps"], ref["links"]["1"]["2"]["0mV"]["width_ps"]),
        commit_raw_b2_w3=(o["links"][2][3]["commit_raw_ps"], ref["links"]["2"]["3"]["commit_raw_ps"]),
        Q_rise_b1=(o["charge_spec_reported_not_gated"][1]["Q_rise_fC"],
                   ref["charge_spec_reported_not_gated"]["1"]["Q_rise_fC"]),
        Q_hold_b1=(o["charge_spec_reported_not_gated"][1]["Q_hold_fC"],
                   ref["charge_spec_reported_not_gated"]["1"]["Q_hold_fC"]),
        E_rise_b1=(o["charge_spec_reported_not_gated"][1]["E_rise_fJ"],
                   ref["charge_spec_reported_not_gated"]["1"]["E_rise_fJ"]),
        rising_lag=(o["rising_lag_ps"], ref["rising_lag_ps"]))
    rel = lambda a, b: abs(a - b) / max(abs(b), 1e-12)
    res = dict(compare=chk,
               value_ok=(chk["value"][0] >= chk["value"][1] == 144 and chk["value"][2] == chk["value"][3] == 0),
               value_note="this harness scores waves 2..6 (240 checks); mesh3 scored 2..4 (144); zero fails on the superset",
               margin_ok=rel(*chk["worst_margin"]) < 0.01,
               margin_note="margin_at_commit is an INSTANTANEOUS sample at the commit instant (signal slope ~5-10 mV/ps): the OFFSET_TABLE Amendment-2 class that is not cross-engine interchangeable below ~1%; rel diff reported as measured",
               margin_rel=round(rel(*chk["worst_margin"]), 4),
               overlap_ok=abs(chk["worst_overlap"][0] - chk["worst_overlap"][1]) < 1.0,
               eye_ok=abs(chk["standing_eye"][0] - chk["standing_eye"][1]) < 1.0,
               commit_ok=abs(chk["commit_raw_b2_w3"][0] - chk["commit_raw_b2_w3"][1]) < 1.0,
               Q_ok=rel(*chk["Q_rise_b1"]) < 0.02,
               wall_s=o.get("wall_s"), npts=o.get("npts"), ms_per_pt=o.get("ms_per_pt"))
    res["PASS"] = all(res[k] for k in ("value_ok", "margin_ok", "overlap_ok", "eye_ok", "commit_ok", "Q_ok"))
    res = jsonable(res)
    json.dump(res, open(os.path.join(HERE, "IC.json"), "w"), indent=1)
    print(json.dumps(res, indent=1))
    return 0 if res["PASS"] else 1


# ============================================================== CMOS level
def level_decks(vdd, engine):
    """depth-12 nand2 chains at 2 fF, (A) both inputs tied together, (B) one
    input tied to VDD; plus the inverter chain (the 52.51 ps reference)."""
    T0 = 100.0
    if engine == "vacask":
        L = ["nand2 level chain vdd=%g" % vdd,
             'load "%s/psp103v4.osdi"' % OSDI, 'load "%s/capacitor.osdi"' % OSDI,
             'include "%s"' % MODELS_INC, "model v vsource", "model cmod capacitor",
             "subckt sg13_lv_nmos (d g s b)", "  parameters w=0.15u l=0.13u",
             "  m1 (d g s b) sg13g2_nmos w=w l=l", "ends",
             "subckt sg13_lv_pmos (d g s b)", "  parameters w=0.15u l=0.13u",
             "  m1 (d g s b) sg13g2_pmos w=w l=l", "ends",
             "vsup (sup 0) v dc=%g" % vdd,
             'vin (din 0) v type="pwl" wave=[0,0, %gp,0, %gp,%g]' % (T0, T0 + EDGE, vdd)]
        sv = []
        for arm in ("a", "b", "i"):
            prev = "din"
            for s in range(1, 13):
                o = "%s%d" % (arm, s)
                if arm == "i":
                    L.append("xp_%s (%s %s sup sup) sg13_lv_pmos w=%gu l=%gu" % (o, o, prev, WP, LCH))
                    L.append("xn_%s (%s %s 0 0) sg13_lv_nmos w=%gu l=%gu" % (o, o, prev, WN, LCH))
                else:
                    b = prev if arm == "a" else "sup"
                    L.append("xpa_%s (%s %s sup sup) sg13_lv_pmos w=%gu l=%gu" % (o, o, prev, WP, LCH))
                    L.append("xpb_%s (%s %s sup sup) sg13_lv_pmos w=%gu l=%gu" % (o, o, b, WP, LCH))
                    L.append("xna_%s (%s %s m_%s 0) sg13_lv_nmos w=%gu l=%gu" % (o, o, prev, o, WN, LCH))
                    L.append("xnb_%s (m_%s %s 0 0) sg13_lv_nmos w=%gu l=%gu" % (o, o, b, WN, LCH))
                L.append("cl_%s (%s 0) cmod c=%gf" % (o, o, CLOAD))
                sv.append("v(%s)" % o)
                prev = o
        L += ["control", '  options tran_method="gear" reltol=1e-5',
              "  save " + " ".join(sv),
              '  analysis tr tran step=0.1p stop=1500p maxstep=0.25p icmode="op"', "endc"]
    else:
        L = ["* nand2 level chain vdd=%g" % vdd, '.hdl "%s"' % XVA, '.include "%s"' % XMODEL,
             '.include "%s"' % XSHIM,
             '.OPTIONS TIMEINT METHOD=GEAR RELTOL=1e-6 ABSTOL=1e-15 CHGTOL=1e-17',
             "VSUP sup 0 %g" % vdd, "VIN din 0 PWL(0 0 %gp 0 %gp %g)" % (T0, T0 + EDGE, vdd)]
        pr = []
        for arm in ("a", "b", "i"):
            prev = "din"
            for s in range(1, 13):
                o = "%s%d" % (arm, s)
                if arm == "i":
                    L.append("XP_%s %s %s sup sup sg13_lv_pmos w=%gu l=%gu" % (o, o, prev, WP, LCH))
                    L.append("XN_%s %s %s 0 0 sg13_lv_nmos w=%gu l=%gu" % (o, o, prev, WN, LCH))
                else:
                    b = prev if arm == "a" else "sup"
                    L.append("XPA_%s %s %s sup sup sg13_lv_pmos w=%gu l=%gu" % (o, o, prev, WP, LCH))
                    L.append("XPB_%s %s %s sup sup sg13_lv_pmos w=%gu l=%gu" % (o, o, b, WP, LCH))
                    L.append("XNA_%s %s %s m_%s 0 sg13_lv_nmos w=%gu l=%gu" % (o, o, prev, o, WN, LCH))
                    L.append("XNB_%s m_%s %s 0 0 sg13_lv_nmos w=%gu l=%gu" % (o, o, b, WN, LCH))
                L.append("CL_%s %s 0 %gf" % (o, o, CLOAD))
                pr.append("V(%s)" % o)
                prev = o
        L += [".tran 0.1p 1500p 0 0.25p", ".print tran " + " ".join(pr), ".end"]
    return L


def level_extract(W, vdd):
    """per-level delay = (t_cross(stage 10) - t_cross(stage 4)) / 6 at VDD/2
    (same polarity every 2 stages; steady state by stage 4), plus trip-level."""
    trip = float(TRIPF(vdd)[0])
    res = {}
    for arm in ("a", "b", "i"):
        a0, Y = W.grid(["V(%s%d)" % (arm.upper(), s) for s in range(1, 13)], 0.0, W.t[-1] - 0.3)
        def tcross(s, lev):
            y = Y[s - 1]
            rising = (s % 2 == 0)
            i0 = int(100.0 / GRID) - a0
            if rising:
                w = np.where((y[i0:-1] < lev) & (y[i0 + 1:] >= lev))[0]
            else:
                w = np.where((y[i0:-1] > lev) & (y[i0 + 1:] <= lev))[0]
            if not len(w):
                return None
            j = i0 + w[0]
            return (j + (lev - y[j]) / (y[j + 1] - y[j]) + a0) * GRID
        out = {}
        for lname, lev in (("half", vdd / 2), ("trip", trip)):
            tc = [tcross(s, lev) for s in range(1, 13)]
            out[lname] = dict(
                per_level_4_to_10_ps=(round((tc[9] - tc[3]) / 6.0, 3) if tc[9] and tc[3] else None),
                per_level_6_to_12_ps=(round((tc[11] - tc[5]) / 6.0, 3) if tc[11] and tc[5] else None),
                rise_step_ps=[round(tc[s] - tc[s - 1], 3) if tc[s] and tc[s - 1] else None
                              for s in range(1, 12)],
                t_cross_ps=[round(x, 3) if x else None for x in tc])
        res[arm] = out
    return res


def cmd_level():
    R = {}
    for vdd in (1.2, 1.65):
        for engine in ("vacask", "xyce"):
            tag = "level_%s_v%g" % (engine, vdd)
            rundir = os.path.join(SCRATCH, tag)
            lines = level_decks(vdd, engine)
            if engine == "vacask":
                raw, msg, wall = run_vacask(rundir, tag + ".sim", lines)
            else:
                raw, msg, wall = run_xyce(rundir, tag + ".cir", lines)
            print(" ", tag, msg, flush=True)
            if raw is None:
                R[tag] = dict(error=msg)
                continue
            W = Waves.from_raw(raw) if engine == "vacask" else Waves.from_prn(raw)
            R[tag] = dict(vdd=vdd, engine=engine, wall_s=round(wall, 1), chains=level_extract(W, vdd))
            dst = os.path.join(HERE, "runs", tag)
            os.makedirs(dst, exist_ok=True)
            for f in os.listdir(rundir):
                if f.endswith((".sim", ".cir", ".log")):
                    shutil.copy2(os.path.join(rundir, f), os.path.join(dst, f))
            os.remove(raw)
    json.dump(jsonable(R), open(os.path.join(HERE, "LEVEL.json"), "w"), indent=1)
    for tag, r in R.items():
        if "chains" in r:
            print(tag, {arm: r["chains"][arm]["half"]["per_level_4_to_10_ps"] for arm in "abi"},
                  "trip:", {arm: r["chains"][arm]["trip"]["per_level_4_to_10_ps"] for arm in "abi"})
    return 0


# ============================================================== STA
def write_verilog(nl, D, path, modname):
    """structural Verilog of the nand2/inv netlist (delay inverters dropped)
    with sg13g2_dfrbp_1 registers at every D-level cut."""
    levels = {g: d["level"] for g, d in nl.gates.items() if not d.get("delay")}
    L = max(levels.values())
    cuts = list(range(D, L, D)) if D < L else []
    # resolve delay chains back to their logical source
    def src(u):
        while u in nl.gates and nl.gates[u].get("delay"):
            u = nl.gates[u]["ins"][0]
        return u
    pol = {}
    def src_pol(u):
        p = 0
        while u in nl.gates and nl.gates[u].get("delay"):
            u = nl.gates[u]["ins"][0]
            p ^= 1
        return u, p
    regs = []        # (q, d)
    wires = set()
    def ref(u, lvl_consumer):
        """name of u as seen at level lvl_consumer (registered across cuts)."""
        u0, p = src_pol(u)
        if u0 in ("0", "1"):
            return "1'b%s" % u0 if not p else "1'b%d" % (1 - int(u0))
        lu = levels.get(u0, 0)
        nm = u0
        for c in cuts:
            if lu <= c < lvl_consumer:
                q = "%s_r%d" % (u0, c)
                if q not in wires:
                    regs.append((q, nm))
                    wires.add(q)
                nm = q
        if p:
            # a dropped odd delay chain means the consumer wanted the complement:
            # emit an inverter cell (it is a real level in CMOS too)
            inv = "%s_pinv" % nm
            if inv not in wires:
                wires.add(inv)
                regs.append(("INV", inv, nm))
            nm = inv
        return nm
    body = []
    for g in nl.order:
        d = nl.gates[g]
        if d.get("delay"):
            continue
        if d["kind"] == "inv":
            body.append("  sg13g2_inv_1 U_%s (.A(%s), .Y(%s));" % (g, ref(d["ins"][0], d["level"]), g))
        else:
            body.append("  sg13g2_nand2_1 U_%s (.A(%s), .B(%s), .Y(%s));"
                        % (g, ref(d["ins"][0], d["level"]), ref(d["ins"][1], d["level"]), g))
    outs = []
    for o, bi in nl.outs:
        outs.append("  sg13g2_dfrbp_1 R_out%d (.D(%s), .CLK(clk), .RESET_B(1'b1), .Q(y%d), .Q_N());" % (bi, o, bi))
    reglines = []
    for r in regs:
        if r[0] == "INV":
            reglines.append("  sg13g2_inv_1 U_%s (.A(%s), .Y(%s));" % (r[1], r[2], r[1]))
        else:
            reglines.append("  sg13g2_dfrbp_1 R_%s (.D(%s), .CLK(clk), .RESET_B(1'b1), .Q(%s), .Q_N());" % (r[0], r[1], r[0]))
    pis = [p for p in nl.pis]
    hdr = ["module %s(clk, %s, %s);" % (modname, ", ".join("x_" + p for p in pis),
                                        ", ".join("y%d" % bi for _, bi in nl.outs)),
           "  input clk;", "  input %s;" % ", ".join("x_" + p for p in pis),
           "  output %s;" % ", ".join("y%d" % bi for _, bi in nl.outs),
           "  wire %s;" % ", ".join(sorted(set(list(levels.keys()) + list(wires)) | set(pis)))]
    inreg = ["  sg13g2_dfrbp_1 R_in_%s (.D(x_%s), .CLK(clk), .RESET_B(1'b1), .Q(%s), .Q_N());" % (p, p, p)
             for p in pis]
    open(path, "w").write("\n".join(hdr + inreg + reglines + body + outs + ["endmodule"]) + "\n")
    return len(regs), len(cuts) + 1


def cmd_sta(block, N=8):
    nl, nd = build_block(block, N)
    st = nl.stats()
    Lmax = max(d["level"] for d in nl.gates.values() if not d.get("delay"))
    wd = os.path.join(SCRATCH, "sta_%s%s" % (block, N if block == "mul" else ""))
    os.makedirs(wd, exist_ok=True)
    libs = {"typ_1p20V_25C": "/usr/local/src/IHP-Open-PDK/ihp-sg13g2/libs.ref/sg13g2_stdcell/lib/sg13g2_stdcell_typ_1p20V_25C.lib",
            "typ_1p50V_25C": "/usr/local/src/IHP-Open-PDK/ihp-sg13g2/libs.ref/sg13g2_stdcell/lib/sg13g2_stdcell_typ_1p50V_25C.lib",
            "fast_1p65V_m40C": "/usr/local/src/IHP-Open-PDK/ihp-sg13g2/libs.ref/sg13g2_stdcell/lib/sg13g2_stdcell_fast_1p65V_m40C.lib"}
    R = dict(block=block, N=N, levels_logic=Lmax, stats=st, rows={})
    for D in (3, 6, 9, Lmax):
        vpath = os.path.join(wd, "net_D%d.v" % D)
        nregs, nstages = write_verilog(nl, D, vpath, "blk")
        for lname, lib in libs.items():
            tcl = os.path.join(wd, "sta_D%d_%s.tcl" % (D, lname))
            open(tcl, "w").write("\n".join([
                "read_liberty %s" % lib, "read_verilog %s" % vpath, "link_design blk",
                "create_clock -name clk -period 10 [get_ports clk]",
                "set_clock_transition 0.15 [get_clocks clk]",
                "report_checks -path_delay max -group_count 1 -digits 4 -fields {capacitance fanout}",
                "report_worst_slack -max -digits 4",
                "puts HEADFREE",
                "set_false_path -from [get_pins R_in_*/CLK]",
                "report_checks -path_delay max -group_count 1 -digits 4 -fields {capacitance fanout}",
                "report_worst_slack -max -digits 4", "exit"]) + "\n")
            r = subprocess.run(["sta", "-no_splash", tcl], capture_output=True, text=True, cwd=wd)
            parts = r.stdout.split("HEADFREE")
            def slack_of(txt):
                m = re.search(r"worst slack max\s+(-?[\d.]+)", txt)
                return float(m.group(1)) if m else None
            s1 = slack_of(parts[0])
            s2 = slack_of(parts[1]) if len(parts) > 1 else None
            per = round((10.0 - s1) * 1000.0, 2) if s1 is not None else None
            per2 = round((10.0 - s2) * 1000.0, 2) if s2 is not None else None
            if per2 is not None and per2 < 1.0:
                per2 = None          # no reg-to-reg path left (single stage)
            def breakdown(txt):
                # first path report: pull clk->q, data arrival, setup
                m = re.search(r"data arrival time\s+(-?[\d.]+)", txt)
                arr = float(m.group(1)) if m else None
                m2 = re.search(r"library setup time\s+(-?[\d.]+)", txt)
                su = float(m2.group(1)) if m2 else None
                m3 = re.search(r"\n\s*(-?[\d.]+)\s+(-?[\d.]+)\s+[v^] R_\S+/Q ", txt)
                cq = float(m3.group(1)) if m3 else None
                return dict(arrival_ps=arr and round(arr * 1000, 1), setup_ps=su and round(-su * 1000, 1),
                            clk_to_q_ps=cq and round(cq * 1000, 1))
            R["rows"].setdefault(str(D), {})[lname] = dict(
                min_period_ps=per, min_period_headfree_ps=per2, n_regs=nregs, stages=nstages,
                latency_ps=(round(per * nstages, 2) if per else None),
                latency_headfree_ps=(round(per2 * nstages, 2) if per2 else None),
                path_all=breakdown(parts[0]), path_headfree=(breakdown(parts[1]) if len(parts) > 1 else None),
                path_tail=r.stdout[-1500:] if per is None else None)
            print("  STA %s D=%d %s: min period %s ps (head-free %s), stages %d"
                  % (block, D, lname, per, per2, nstages), flush=True)
    json.dump(R, open(os.path.join(HERE, "STA_%s%s.json" % (block, N if block == "mul" else "")), "w"), indent=1)
    return 0


# ============================================================== main
if __name__ == "__main__":
    a = sys.argv[1:]
    os.makedirs(SCRATCH, exist_ok=True)
    if a[0] == "proof":
        print(json.dumps(functional_proof(a[1], int(a[2]) if len(a) > 2 else 8), indent=1))
    elif a[0] == "ic":
        sys.exit(cmd_ic())
    elif a[0] == "crc":
        g = None if (len(a) < 2 or a[1] == "all") else int(a[1])
        nw = int(a[2]) if len(a) > 2 else NW
        tt = float(a[3]) if len(a) > 3 else TT
        dl = int(a[4]) if len(a) > 4 else None
        o = cmd_run("crc", "vacask", group=g, nw=nw, tt=tt, dlev=dl)
        sys.exit(0 if o.get("acceptance", {}).get("PASS") else 3)
    elif a[0] == "mul":
        N = int(a[1])
        nw = int(a[2]) if len(a) > 2 else NW
        tt = float(a[3]) if len(a) > 3 else TT
        dl = int(a[4]) if len(a) > 4 else None
        o = cmd_run("mul", "vacask", N=N, nw=nw, tt=tt, dlev=dl)
        sys.exit(0 if o.get("acceptance", {}).get("PASS") else 3)
    elif a[0] == "icn":          # nand2 cell-class traversal lane: icn <d> <tt>
        o = cmd_run("icn", "vacask", N=int(a[1]), nw=7, tt=float(a[2]), dlev=int(a[1]))
        sys.exit(0 if o.get("acceptance", {}).get("PASS") else 3)
    elif a[0] == "xyce":
        blk = a[1]
        nw = int(a[2]) if len(a) > 2 else 6
        tt = float(a[4]) if len(a) > 4 else TT
        dl = int(a[5]) if len(a) > 5 else None
        if blk == "crc":
            g = int(a[3]) if len(a) > 3 else 0
            o = cmd_run("crc", "xyce", group=g, nw=nw, tt=tt, dlev=dl)
        else:
            o = cmd_run("mul", "xyce", N=int(blk[3:]), nw=nw, tt=tt, dlev=dl)
        sys.exit(0 if o.get("acceptance", {}).get("PASS") else 3)
    elif a[0] == "level":
        sys.exit(cmd_level())
    elif a[0] == "sta":
        blk = a[1]
        sys.exit(cmd_sta("crc") if blk == "crc" else cmd_sta("mul", int(blk[3:])))
    else:
        print(__doc__)
        sys.exit(2)
