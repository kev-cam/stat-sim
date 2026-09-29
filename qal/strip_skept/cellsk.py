#!/usr/bin/env python3
"""SKEPTIC cell library: static controls and stripped (nMOS tree + cross-coupled
pMOS) equivalents, generated from the FUNCTION, with the trees verified
exhaustively against that function before any deck is emitted.

Device counting is done by counting emitted M-cards, never by intent.
"""
import itertools

L = "0.13u"
WN = "0.74u"
WP = "1.12u"

# ---------------------------------------------------------------------------
# Boolean functions, taken from the sg13g2 liberty 'function' strings.
# Each entry: (inputs, python lambda over a dict, liberty string)
# NOTE these are the CELL OUTPUT functions.  Verified against the liberty text
# in the PDK at /usr/local/src/IHP-Open-PDK/.../sg13g2_stdcell_typ_1p20V_25C.lib
# ---------------------------------------------------------------------------
FUNCS = {
    "inv":   (["A"],            lambda v: not v["A"],                                    "!A"),
    "buf":   (["A"],            lambda v: v["A"],                                        "A"),
    "nand2": (["A", "B"],       lambda v: not (v["A"] and v["B"]),                       "!(A*B)"),
    "nor2":  (["A", "B"],       lambda v: not (v["A"] or v["B"]),                        "!(A+B)"),
    "and2":  (["A", "B"],       lambda v: v["A"] and v["B"],                             "A*B"),
    "or2":   (["A", "B"],       lambda v: v["A"] or v["B"],                              "A+B"),
    "nor2b": (["A", "B_N"],     lambda v: (not v["A"]) and v["B_N"],                     "!A*B_N"),
    "xor2":  (["A", "B"],       lambda v: bool(v["A"]) != bool(v["B"]),                  "A^B"),
    "xnor2": (["A", "B"],       lambda v: bool(v["A"]) == bool(v["B"]),                  "!(A^B)"),
    "mux2":  (["A0", "A1", "S"],lambda v: v["A1"] if v["S"] else v["A0"],                "A0*!S+A1*S"),
    "a21oi": (["A1", "A2", "B1"], lambda v: not ((v["A1"] and v["A2"]) or v["B1"]),      "!((A1*A2)+B1)"),
    "a21o":  (["A1", "A2", "B1"], lambda v: (v["A1"] and v["A2"]) or v["B1"],            "(A1*A2)+B1"),
    "o21ai": (["A1", "A2", "B1"], lambda v: not ((v["A1"] or v["A2"]) and v["B1"]),      "!((A1+A2)*B1)"),
}

# ---------------------------------------------------------------------------
# nMOS pull-down TREES, written FACTORED (series-parallel), never as a sum of
# products.  A tree is a nested structure:
#    ("s", [child, ...])  series stack
#    ("p", [child, ...])  parallel branches
#    ("d", literal)       one nMOS gated by `literal`
# A literal is an input name, optionally with a leading "!" meaning the
# COMPLEMENT RAIL of that input (which must then be supplied -- charged in the
# device-count audit).
# The tree CONDUCTS when its boolean evaluates true; that pulls its node LOW.
# ---------------------------------------------------------------------------
def d(lit):
    return ("d", lit)


def s(*kids):
    return ("s", list(kids))


def p(*kids):
    return ("p", list(kids))


def tree_eval(t, v):
    k = t[0]
    if k == "d":
        lit = t[1]
        if lit.startswith("!"):
            return not v[lit[1:]]
        return bool(v[lit])
    if k == "s":
        return all(tree_eval(c, v) for c in t[1])
    return any(tree_eval(c, v) for c in t[1])


def tree_ndev(t):
    if t[0] == "d":
        return 1
    return sum(tree_ndev(c) for c in t[1])


def tree_lits(t, out=None):
    if out is None:
        out = set()
    if t[0] == "d":
        out.add(t[1])
    else:
        for c in t[1]:
            tree_lits(c, out)
    return out


# f tree pulls the TRUE-rail node LOW  -> conducts when f == 0
# g tree pulls the COMPLEMENT node LOW -> conducts when f == 1
TREES = {
    # inv: Y=!A.  Y low when A.  Yb low when !A.
    "inv":   (d("A"),                       d("!A")),
    "buf":   (d("!A"),                      d("A")),
    "nand2": (s(d("A"), d("B")),            p(d("!A"), d("!B"))),
    "nor2":  (p(d("A"), d("B")),            s(d("!A"), d("!B"))),
    "and2":  (p(d("!A"), d("!B")),          s(d("A"), d("B"))),
    "or2":   (s(d("!A"), d("!B")),          p(d("A"), d("B"))),
    # nor2b: Y = !A & B_N.  Y low when A | !B_N.  Yb low when !A & B_N.
    "nor2b": (p(d("A"), d("!B_N")),         s(d("!A"), d("B_N"))),
    # xor2: Y = A^B.  Y low when A==B  -> (A&B)|(!A&!B)
    "xor2":  (p(s(d("A"), d("B")), s(d("!A"), d("!B"))),
              p(s(d("A"), d("!B")), s(d("!A"), d("B")))),
    "xnor2": (p(s(d("A"), d("!B")), s(d("!A"), d("B"))),
              p(s(d("A"), d("B")), s(d("!A"), d("!B")))),
    # mux2: Y = S ? A1 : A0.  Y low when (!S & !A0) | (S & !A1)
    "mux2":  (p(s(d("!S"), d("!A0")), s(d("S"), d("!A1"))),
              p(s(d("!S"), d("A0")),  s(d("S"), d("A1")))),
    # a21oi: Y = !((A1&A2)|B1).  Y low when (A1&A2)|B1
    "a21oi": (p(s(d("A1"), d("A2")), d("B1")),
              s(p(d("!A1"), d("!A2")), d("!B1"))),
    # a21o : Y =  (A1&A2)|B1.  Y low when !((A1&A2)|B1)
    "a21o":  (s(p(d("!A1"), d("!A2")), d("!B1")),
              p(s(d("A1"), d("A2")), d("B1"))),
    # o21ai: Y = !((A1|A2)&B1).  Y low when (A1|A2)&B1
    # Series order matched to the PDK sg13g2_o21ai_1 pull-down (XN1/B1 is the
    # TOP device adjacent to Y, XN0||XN2 = A2||A1 sit at the bottom) so the
    # stripped f-tree and the static control discharge the same internal node.
    "o21ai": (s(d("B1"), p(d("A1"), d("A2"))),
              p(s(d("!A1"), d("!A2")), d("!B1"))),
}


def verify_trees():
    """Exhaustive check: f-tree conducts iff f==0, g-tree conducts iff f==1."""
    rep = {}
    for fam, (ins, fn, lib) in FUNCS.items():
        tf, tg = TREES[fam]
        bad = 0
        for bits in itertools.product([0, 1], repeat=len(ins)):
            v = dict(zip(ins, bits))
            f = bool(fn(v))
            if tree_eval(tf, v) != (not f):
                bad += 1
            if tree_eval(tg, v) != f:
                bad += 1
        rep[fam] = dict(vectors=2 ** len(ins), mismatches=bad,
                        n_f=tree_ndev(tf), n_g=tree_ndev(tg),
                        stripped_devices=tree_ndev(tf) + tree_ndev(tg) + 2,
                        needs_complement=sorted(x[1:] for x in
                                                (tree_lits(tf) | tree_lits(tg))
                                                if x.startswith("!")),
                        liberty=lib)
    return rep


# ---------------------------------------------------------------------------
# Netlist emission
# ---------------------------------------------------------------------------
def gate_net(lit, inst):
    """Gate net for a literal, INSTANCE-QUALIFIED.  The complement rail of input
    X is the separate net X<inst>_B, which the caller must drive; that it has to
    be driven at all is the dual-rail cost charged in the device-count audit."""
    if lit.startswith("!"):
        return f"{lit[1:]}{inst}_B"
    return f"{lit}{inst}"


def emit_tree(t, top, gnd, pfx, wn, l, nl, ctr, inst):
    """Emit nMOS devices for tree `t` between node `top` and `gnd`."""
    k = t[0]
    if k == "d":
        ctr[0] += 1
        g = gate_net(t[1], inst)
        nl.append(f"X{pfx}{ctr[0]} {top} {g} {gnd} 0 sg13_lv_nmos w={wn} l={l}")
        return
    if k == "p":
        for c in t[1]:
            emit_tree(c, top, gnd, pfx, wn, l, nl, ctr, inst)
        return
    # series: chain top -> i1 -> i2 ... -> gnd
    kids = t[1]
    cur = top
    for i, c in enumerate(kids):
        last = (i == len(kids) - 1)
        nxt = gnd if last else f"{pfx}i{ctr[0]}_{i}"
        emit_tree(c, cur, nxt, pfx, wn, l, nl, ctr, inst)
        cur = nxt


def strip_cell(fam, inst, rail, q, qb, wxc, wn=WN, l=L):
    """Stripped cell: 2 grounded nMOS trees + 2 cross-coupled pMOS.
    Gate nets for input X are  X  and  X_B  (the complement rail).
    Returns (netlist_lines, n_devices)."""
    tf, tg = TREES[fam]
    nl = [f"* stripped {fam} inst={inst} wxc={wxc}"]
    ctr = [0]
    emit_tree(tf, q, "0", f"{inst}F", wn, l, nl, ctr, inst)
    ctr = [0]
    emit_tree(tg, qb, "0", f"{inst}G", wn, l, nl, ctr, inst)
    # cross-coupled pull-up: SOURCE AND BULK on the rail.  No keeper, no
    # precharge device, no footer.
    nl.append(f"XXA{inst} {q} {qb} {rail} {rail} sg13_lv_pmos w={wxc} l={l}")
    nl.append(f"XXB{inst} {qb} {q} {rail} {rail} sg13_lv_pmos w={wxc} l={l}")
    n = sum(1 for x in nl if x.startswith("X"))
    return nl, n


def static_o21ai(inst, rail, q, wn=WN, wp=WP, l=L):
    """Hand-built o21ai at campaign-standard widths, structure taken verbatim
    from the PDK sg13g2_o21ai_1 netlist (XP0/XP1 series stack, XP2 parallel;
    XN0||XN2 then XN1 in series).  l=0.13u not the PDK's 0.15u -> the STRONGER
    device, i.e. generous to the static control."""
    nl = [f"* static o21ai_hb inst={inst}"]
    nl.append(f"XP0{inst} {inst}n14 A1{inst} {rail} {rail} sg13_lv_pmos w={wp} l={l}")
    nl.append(f"XP1{inst} {q} A2{inst} {inst}n14 {rail} sg13_lv_pmos w={wp} l={l}")
    nl.append(f"XP2{inst} {q} B1{inst} {rail} {rail} sg13_lv_pmos w={wp} l={l}")
    nl.append(f"XN0{inst} {inst}n1 A2{inst} 0 0 sg13_lv_nmos w={wn} l={l}")
    nl.append(f"XN2{inst} {inst}n1 A1{inst} 0 0 sg13_lv_nmos w={wn} l={l}")
    nl.append(f"XN1{inst} {q} B1{inst} {inst}n1 0 sg13_lv_nmos w={wn} l={l}")
    n = sum(1 for x in nl if x.startswith("X"))
    return nl, n


if __name__ == "__main__":
    import json
    rep = verify_trees()
    bad = {k: v for k, v in rep.items() if v["mismatches"]}
    print(json.dumps(rep, indent=1))
    print("FAMILIES:", len(rep), " MISMATCHES:", sum(v["mismatches"] for v in rep.values()))
    assert not bad, bad
