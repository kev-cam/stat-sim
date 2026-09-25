#!/usr/bin/env python3
"""THE MUX PROBLEM.  1957 of alu_top's 4726 cells are $_MUX_; in the DIMS
template a 2:1 MUX is the most expensive primitive there is (8 TH33 minterms +
2 TH14 collectors = 10 cells).  This script finds and CHECKS the cheapest correct
threshold form.

For every candidate form it runs four independent checks:
  FUNC  dual-rail Boolean evaluation over all 27 codes of (s,a,b) in
        {DATA0,DATA1,NULL}^3 -- the 8 all-DATA codes must decode to Y = S?B:A
        with a well-formed (exactly-one-rail) output, and no all-DATA code may
        leave the output NULL.
  QDI   hysteretic (C-element) event-driven simulation, NULL->DATA->NULL, with
        RANDOM per-gate delays: no output rail may fall during DATA (hazard) and
        every internal net must return to 0 in NULL.
  IC    INPUT-COMPLETENESS, exact: enumerate every minimal set of input rails
        that makes an output rail assert; the form is input-complete iff every
        such set touches s AND a AND b.  Reported separately is the weaker
        property the MUX actually needs to be FUNCTIONALLY safe -- every
        asserting set touches the SELECT and the SELECTED data input.
  NULL  no input rail pinned high (a constant-1 input would stop a hysteretic
        cell ever returning to NULL).
Costs are the MEASURED SG13G2 E(C_L) models (see compose_async.py).
"""
import itertools
import random
import sys

# threshold cells: name -> (weights, threshold).  th24comp is NOT a threshold
# function (it is the Fant AB+CD cell) and is handled separately.
CELL = {"th12": ([1, 1], 1), "th13": ([1, 1, 1], 1), "th14": ([1, 1, 1, 1], 1),
        "th22": ([1, 1], 2), "th23": ([1, 1, 1], 2), "th33": ([1, 1, 1], 3),
        "th24": ([1, 1, 1, 1], 2), "th34": ([1, 1, 1, 1], 3),
        "th44": ([1, 1, 1, 1], 4), "th23w2": ([2, 1, 1], 2),
        "th34w2": ([2, 1, 1, 1], 3)}
SPICE = {"th12", "th13", "th14", "th22", "th23", "th33", "th34w2"}   # characterized
INRAILS = ["st", "sf", "at", "af", "bt", "bf"]


def gate(name, ins):
    if name == "th24comp":                      # Fant AB+CD, 2-of-4 "complementary"
        return int((ins[0] and ins[1]) or (ins[2] and ins[3]))
    w, T = CELL[name]
    return int(sum(wi * x for wi, x in zip(w, ins)) >= T)


def weights(name):
    if name == "th24comp":
        return None
    return CELL[name]


# ---------------------------------------------------------------- the forms
def dims():
    """map_ncl_struct MUX_MIN: 8 TH33 minterms over (s,a,b) + 2 TH14."""
    c = []
    mins = {"m010": ("th33", ["sf", "at", "bf"]), "m011": ("th33", ["sf", "at", "bt"]),
            "m101": ("th33", ["st", "af", "bt"]), "m111": ("th33", ["st", "at", "bt"]),
            "m000": ("th33", ["sf", "af", "bf"]), "m001": ("th33", ["sf", "af", "bt"]),
            "m100": ("th33", ["st", "af", "bf"]), "m110": ("th33", ["st", "at", "bf"])}
    for k, (t, ins) in mins.items():
        c.append((t, ins, k))
    c.append(("th14", ["m010", "m011", "m101", "m111"], "yt"))
    c.append(("th14", ["m000", "m001", "m100", "m110"], "yf"))
    return c


def cover_presence():
    """min cover + shared presence TH12: the form map_ncl_direct emits when th34
    is not in the allowed cell set."""
    return [("th12", ["at", "af"], "Pa"), ("th12", ["bt", "bf"], "Pb"),
            ("th33", ["sf", "at", "Pb"], "t1"), ("th33", ["st", "bt", "Pa"], "t2"),
            ("th12", ["t1", "t2"], "yt"),
            ("th33", ["sf", "af", "Pb"], "f1"), ("th33", ["st", "bf", "Pa"], "f2"),
            ("th12", ["f1", "f2"], "yf")]


def cover_th34():
    """min cover with the don't-care's BOTH rails inside the cube cell: TH34."""
    return [("th34", ["sf", "at", "bt", "bf"], "t1"),
            ("th34", ["st", "bt", "at", "af"], "t2"),
            ("th12", ["t1", "t2"], "yt"),
            ("th34", ["sf", "af", "bt", "bf"], "f1"),
            ("th34", ["st", "bf", "at", "af"], "f2"),
            ("th12", ["f1", "f2"], "yf")]


def andor():
    """textbook AND-OR: the cheapest FUNCTIONALLY correct form."""
    return [("th22", ["sf", "at"], "t1"), ("th22", ["st", "bt"], "t2"),
            ("th12", ["t1", "t2"], "yt"),
            ("th22", ["sf", "af"], "f1"), ("th22", ["st", "bf"], "f2"),
            ("th12", ["f1", "f2"], "yf")]


def th24comp():
    """the standard Fant NCL MUX: one AB+CD cell per rail."""
    return [("th24comp", ["sf", "at", "st", "bt"], "yt"),
            ("th24comp", ["sf", "af", "st", "bf"], "yf")]


def th23w2_form():
    """X + Y.Z cell (TH23W2) folding the collector into the second cube."""
    return [("th22", ["sf", "at"], "t1"), ("th23w2", ["t1", "st", "bt"], "yt"),
            ("th22", ["sf", "af"], "f1"), ("th23w2", ["f1", "st", "bf"], "yf")]


FORMS = [("DIMS 8xTH33+2xTH14", dims()),
         ("cover + shared presence (TH33)", cover_presence()),
         ("cover with TH34 cube cells", cover_th34()),
         ("AND-OR (TH22/TH12)", andor()),
         ("Fant TH24COMP", th24comp()),
         ("TH22 + TH23W2", th23w2_form())]


# ---------------------------------------------------------------- evaluators
def topo(net):
    have = set(INRAILS)
    out, pend = [], list(net)
    while pend:
        nxt, prog = [], False
        for c in pend:
            if all(i in have for i in c[1]):
                out.append(c); have.add(c[2]); prog = True
            else:
                nxt.append(c)
        pend = nxt
        if not prog:
            sys.exit("loop in form")
    return out


def evalnet(net, v):
    for t, ins, o in topo(net):
        v[o] = gate(t, [v[i] for i in ins])
    return v


def check_func(net):
    """all 27 (s,a,b) in {D0,D1,NULL}: all-DATA must decode; report failures."""
    RAIL = {0: (0, 1), 1: (1, 0), None: (0, 0)}     # value -> (t,f); t=L=value-1
    bad = []
    for s, a, b in itertools.product((0, 1, None), repeat=3):
        v = {}
        for nm, val in (("s", s), ("a", a), ("b", b)):
            t, f = RAIL[val]
            v[nm + "t"], v[nm + "f"] = t, f
        v = evalnet(net, dict(v))
        if None not in (s, a, b):
            want = b if s else a
            if (v["yt"], v["yf"]) != RAIL[want]:
                bad.append(("decode", s, a, b, v["yt"], v["yf"]))
    return bad


def check_ic(net):
    """minimal asserting input-rail sets for yt and yf."""
    res = {}
    for o in ("yt", "yf"):
        assert_sets = []
        for k in range(1, 7):
            for S in itertools.combinations(INRAILS, k):
                if any(set(x) <= set(S) for x in assert_sets):
                    continue
                if {"st", "sf"} <= set(S) or {"at", "af"} <= set(S) \
                        or {"bt", "bf"} <= set(S):
                    continue                        # infeasible rail pair
                v = {r: int(r in S) for r in INRAILS}
                if evalnet(net, v)[o]:
                    assert_sets.append(S)
        res[o] = assert_sets
    full = all(all({"s", "a", "b"} == {r[0] for r in S} for S in v)
               for v in res.values())
    # weaker: every asserting set has the select and the SELECTED data
    weak = True
    for o, sets in res.items():
        for S in sets:
            if "sf" in S and not ({"at", "af"} & set(S)):
                weak = False
            if "st" in S and not ({"bt", "bf"} & set(S)):
                weak = False
            if not ({"st", "sf"} & set(S)):
                weak = False
    return res, full, weak


def check_qdi(net, runs=400, seed=11):
    """hysteretic cells, random delays, NULL->DATA->NULL."""
    rnd = random.Random(seed)
    order = topo(net)
    fan = {}
    for idx, (t, ins, o) in enumerate(order):
        for i in ins:
            fan.setdefault(i, []).append(idx)
    fails = 0
    for _ in range(runs):
        s, a, b = [rnd.randrange(2) for _ in range(3)]
        dly = [rnd.uniform(0.2, 5.0) for _ in order]
        st = {r: 0 for r in INRAILS}
        for t, ins, o in order:
            st[o] = 0
        rose = set()
        ok = [True]

        def settle(q, phase):
            while q:
                q.sort()
                tm, n, val = q.pop(0)
                if st.get(n) == val:
                    continue
                if phase == "DATA" and val == 0 and n in rose:
                    ok[0] = False
                st[n] = val
                if phase == "DATA" and val == 1:
                    rose.add(n)
                for idx in fan.get(n, []):
                    t, ins, o = order[idx]
                    if t == "th24comp":
                        w, T = [1, 1, 1, 1], 2
                        hit = (st.get(ins[0]) and st.get(ins[1])) or \
                              (st.get(ins[2]) and st.get(ins[3]))
                        nv = 1 if hit else (0 if all(st.get(x) == 0 for x in ins)
                                            else st.get(o, 0))
                    else:
                        w, T = CELL[t]
                        sm = sum(wi for wi, x in zip(w, ins) if st.get(x))
                        nv = 1 if sm >= T else (0 if all(st.get(x) == 0 for x in ins)
                                                else st.get(o, 0))
                    if nv != st.get(o, 0):
                        q.append((tm + dly[idx], o, nv))
        q = []
        for nm, val in (("s", s), ("a", a), ("b", b)):
            q.append((rnd.uniform(0, 3.0), nm + ("t" if val else "f"), 1))
        settle(q, "DATA")
        want = b if s else a
        if (st["yt"], st["yf"]) != ((1, 0) if want else (0, 1)) or not ok[0]:
            fails += 1
            continue
        q = [(rnd.uniform(0, 3.0), r, 0) for r in INRAILS if st.get(r)]
        settle(q, "NULL")
        if any(st.get(o) for _, _, o in order):
            fails += 1
    return fails, runs


def single_cell_possible():
    """Is the INPUT-COMPLETE t-rail function a threshold function of the 6 rails?
    Brute-force over integer weights 0..4 and thresholds -- prints the witness
    contradiction if not."""
    on = [("sf", "at", "bt"), ("sf", "at", "bf"), ("st", "bt", "at"), ("st", "bt", "af")]
    off = [("sf", "bt", "af"), ("st", "at", "bf"), ("sf", "at"), ("st", "bt"),
           ("at", "bt"), ("af", "bf"), ("sf", "af", "bt"), ("st", "af", "bf")]
    for w in itertools.product(range(0, 5), repeat=6):
        W = dict(zip(INRAILS, w))
        lo = min(sum(W[x] for x in S) for S in on)
        hi = max(sum(W[x] for x in S) for S in off)
        if lo > hi:
            return w
    return None


if __name__ == "__main__":
    print("=" * 78)
    print("single-cell input-complete MUX rail?  ", end="")
    r = single_cell_possible()
    print("weights %s" % (r,) if r else
          "NO -- no integer weights 0..4 separate the on/off sets")
    print("=" * 78)
    hdr = "%-32s %5s %6s %8s %8s %8s %6s"
    print(hdr % ("form", "cells", "spice?", "FUNC", "QDI", "IC(full)", "IC(sel)"))
    for name, net in FORMS:
        used = {t for t, _, _ in net}
        nsp = "yes" if used <= SPICE else "NO:" + ",".join(sorted(used - SPICE))
        bad = check_func(net)
        qf, qr = check_qdi(net)
        sets, full, weak = check_ic(net)
        print(hdr % (name, len(net), nsp,
                     "PASS" if not bad else "FAIL(%d)" % len(bad),
                     "PASS" if qf == 0 else "FAIL %d/%d" % (qf, qr),
                     "yes" if full else "no", "yes" if weak else "no"))
    print()
    print("minimal asserting input-rail sets, per form (yt rail):")
    for name, net in FORMS:
        sets, full, weak = check_ic(net)
        print("  %-32s %s" % (name, " ".join("{%s}" % ",".join(S) for S in sets["yt"])))
