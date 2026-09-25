#!/usr/bin/env python3
"""LOWER BOUND for an INPUT-COMPLETE dual-rail 2:1 MUX rail.

The t-rail of an input-complete MUX, as a MONOTONE function of the six input
rails (st,sf,at,af,bt,bf), is the up-closure of its four prime implicants
  {sf,at,bt} {sf,at,bf} {st,bt,at} {st,bt,af}
(each one names all three inputs, which is exactly input-completeness; the
first two merge into sf.at.P_b and the last two into st.bt.P_a once a presence
signal exists).  Codes that assert both rails of one input are unreachable in a
dual-rail protocol and are treated as DON'T CARE.

Exhaustive search over networks of 1 and 2 cells drawn from the SEVEN cells that
have an SG13G2 transistor characterization, over every ordered input assignment.
"""
import itertools

CELL = {"th12": ([1, 1], 1), "th13": ([1, 1, 1], 1), "th14": ([1, 1, 1, 1], 1),
        "th22": ([1, 1], 2), "th23": ([1, 1, 1], 2), "th33": ([1, 1, 1], 3),
        "th34w2": ([2, 1, 1, 1], 3),
        # uncharacterized but in the standard NCL library, for contrast
        "th24": ([1, 1, 1, 1], 2), "th34": ([1, 1, 1, 1], 3),
        "th44": ([1, 1, 1, 1], 4), "th23w2": ([2, 1, 1], 2)}
SPICE = ["th12", "th13", "th14", "th22", "th23", "th33", "th34w2"]
ALL = SPICE + ["th24", "th34", "th44", "th23w2"]
R = ["st", "sf", "at", "af", "bt", "bf"]
PAIRS = [(0, 1), (2, 3), (4, 5)]
PRIMES = [("sf", "at", "bt"), ("sf", "at", "bf"), ("st", "bt", "at"), ("st", "bt", "af")]

CODES = list(range(64))
FEAS = [c for c in CODES if not any((c >> i & 1) and (c >> j & 1) for i, j in PAIRS)]


def target_mask():
    m = 0
    for c in CODES:
        S = {R[i] for i in range(6) if c >> i & 1}
        if any(set(p) <= S for p in PRIMES):
            m |= 1 << c
    return m


FEASMASK = 0
for c in FEAS:
    FEASMASK |= 1 << c
TGT = target_mask()


def cellmask(name, ins):
    """ins: list of source masks (64-bit) -> output mask."""
    w, T = CELL[name]
    out = 0
    for c in CODES:
        s = sum(wi for wi, m in zip(w, ins) if m >> c & 1)
        if s >= T:
            out |= 1 << c
    return out


RAILMASK = []
for i in range(6):
    m = 0
    for c in CODES:
        if c >> i & 1:
            m |= 1 << c
    RAILMASK.append(m)


def search(lib, depth):
    """all networks of <= depth cells; sources = 6 rails + previously made nets."""
    hits = []
    lvl1 = []
    for name in lib:
        k = len(CELL[name][0])
        for ins in itertools.permutations(range(6), k):
            m = cellmask(name, [RAILMASK[i] for i in ins])
            lvl1.append((m, [(name, [R[i] for i in ins])]))
    for m, net in lvl1:
        if (m ^ TGT) & FEASMASK == 0:
            hits.append(("1 cell", net))
    if depth >= 2:
        for m1, net1 in lvl1:
            src = [RAILMASK[i] for i in range(6)] + [m1]
            nm = R + ["c1"]
            for name in lib:
                k = len(CELL[name][0])
                for ins in itertools.permutations(range(7), k):
                    if 6 not in ins:
                        continue                       # must use c1
                    m = cellmask(name, [src[i] for i in ins])
                    if (m ^ TGT) & FEASMASK == 0:
                        hits.append(("2 cells", net1 + [(name, [nm[i] for i in ins])]))
                        if len(hits) > 5:
                            return hits
    return hits


if __name__ == "__main__":
    for tag, lib in (("SG13G2-CHARACTERIZED (7 cells)", SPICE),
                     ("FULL NCL library (11 cells)", ALL)):
        h = search(lib, 2)
        print("%-34s  networks of <=2 cells realizing the input-complete "
              "t-rail: %d" % (tag, len(h)))
        for t, net in h[:6]:
            print("     %s: %s" % (t, net))
    print()
    print("3-cell existence check (the forms in mux_forms.py):")
    print("  TH34 cover  th12(th34(sf,at,bt,bf), th34(st,bt,at,af)) -> ", end="")
    a = cellmask("th34", [RAILMASK[1], RAILMASK[2], RAILMASK[4], RAILMASK[5]])
    b = cellmask("th34", [RAILMASK[0], RAILMASK[4], RAILMASK[2], RAILMASK[3]])
    y = cellmask("th12", [a, b])
    print("EXACT" if (y ^ TGT) & FEASMASK == 0 else "MISMATCH")
    print("  presence    th12(th33(sf,at,Pb), th33(st,bt,Pa)) + 2 shared TH12 -> ", end="")
    Pa = cellmask("th12", [RAILMASK[2], RAILMASK[3]])
    Pb = cellmask("th12", [RAILMASK[4], RAILMASK[5]])
    a = cellmask("th33", [RAILMASK[1], RAILMASK[2], Pb])
    b = cellmask("th33", [RAILMASK[0], RAILMASK[4], Pa])
    y = cellmask("th12", [a, b])
    print("EXACT" if (y ^ TGT) & FEASMASK == 0 else "MISMATCH")
