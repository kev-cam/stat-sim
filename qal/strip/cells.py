#!/usr/bin/env python3
"""The STRIPPED cell family and the STATIC controls, as flat device lines.

STRIPPED = two grounded nMOS trees (f and f-bar) + two cross-coupled pMOS.
  node q{i}  = the cell's TRUE output  (same logic value as the static cell's Y/X)
  node n{i}  = its complement
  XPQ: rail -> q, gate = n, source AND bulk on the rail
  XPN: rail -> n, gate = q, source AND bulk on the rail
  TREE_Q conducts exactly when f = 0 (so it pulls q LOW)
  TREE_N conducts exactly when f = 1 (so it pulls n LOW)
There is NO footer, NO precharge device and NO keeper: the ramping rail is the
precharge (both output nodes start at 0 and rise with it until one tree wins).

STATIC controls are the sg13g2 std cells, device lines VERBATIM from
sg13g2_stdcell.spice, written FLAT (not as .subckt) so that internal nodes --
in particular the o21ai series-pMOS source node net14 -- can be probed for the
Vgs / body-bias comparison.  One explicit 0.1 fF per internal node, the committed
qal/sha256 census convention (the shim zeroes ad/as/pd/ps, so an internal node
would otherwise carry no capacitance at all).
"""

# ---------------------------------------------------------------- stripped
# Trees are SERIES-PARALLEL expressions, not sums of products, so that a literal
# shared by several cubes costs ONE transistor and not one per cube (an earlier
# SOP form of this table cost o21ai 9 devices instead of the factored 8 by
# duplicating B1; corrected before any cell deck was run).
#   ("S", [...]) series chain      ("P", [...]) parallel      "A" / "A#" literal
#   TQ : conducts when the output should be LOW   (pulls q down)
#   TN : conducts when the output should be HIGH  (pulls n down)
S = lambda *a: ("S", list(a))
P = lambda *a: ("P", list(a))
STRIP = {
    # inverter  f = A'
    "inv":   dict(ports=["A"], TQ="A", TN="A#"),
    # nand2    f = (A.B)'
    "nand2": dict(ports=["A", "B"], TQ=S("A", "B"), TN=P("A#", "B#")),
    # nor2     f = (A+B)'
    "nor2":  dict(ports=["A", "B"], TQ=P("A", "B"), TN=S("A#", "B#")),
    # xnor2    f = A xnor B   -> q low when A xor B
    "xnor2": dict(ports=["A", "B"],
                  TQ=P(S("A", "B#"), S("A#", "B")),
                  TN=P(S("A", "B"), S("A#", "B#"))),
    # mux2     f = S ? A1 : A0
    "mux2":  dict(ports=["A0", "A1", "S"],
                  TQ=P(S("S", "A1#"), S("S#", "A0#")),
                  TN=P(S("S", "A1"), S("S#", "A0"))),
    # o21ai    f = ((A1+A2).B1)'   -- B1 is SHARED, one device
    "o21ai": dict(ports=["A1", "A2", "B1"],
                  TQ=S(P("A1", "A2"), "B1"),
                  TN=P(S("A1#", "A2#"), "B1#")),
}


def _count(e):
    if isinstance(e, str):
        return 1
    return sum(_count(c) for c in e[1])


def _emit(e, top, bot, pfx, gn, w, lit, acc, ctr):
    """Emit a series-parallel nMOS network between `top` and `bot`."""
    if isinstance(e, str):
        ctr[0] += 1
        acc.append("X%s%d %s %s %s %s sg13_lv_nmos w=%gu l=0.13u"
                   % (pfx, ctr[0], top, lit(e), bot, gn, w))
        return
    kind, ch = e
    if kind == "P":
        for c in ch:
            _emit(c, top, bot, pfx, gn, w, lit, acc, ctr)
        return
    prev = top
    for j, c in enumerate(ch):
        nxt = bot if j == len(ch) - 1 else "%si%d" % (pfx, ctr[1])
        if nxt is not bot and nxt != bot:
            ctr[1] += 1
            acc.append("C%s%s %s %s 0.1f" % (pfx, ctr[1], nxt, gn))
        _emit(c, prev, nxt, pfx, gn, w, lit, acc, ctr)
        prev = nxt

# truth functions, used to derive the expected output of every vector
def f_of(fam, v):
    if fam == "inv":
        return 1 - v["A"]
    if fam == "nand2":
        return 1 - (v["A"] & v["B"])
    if fam == "nor2":
        return 1 - (v["A"] | v["B"])
    if fam == "xnor2":
        return 1 if v["A"] == v["B"] else 0
    if fam == "mux2":
        return v["A1"] if v["S"] else v["A0"]
    if fam == "o21ai":
        return 1 - ((v["A1"] | v["A2"]) & v["B1"])
    raise KeyError(fam)


def strip_devcount(fam):
    s = STRIP[fam]
    n = _count(s["TQ"]) + _count(s["TN"])
    return dict(n_nmos=n, n_pmos=2, n_dev=n + 2,
                n_tree_q=_count(s["TQ"]), n_tree_n=_count(s["TN"]))


def strip_cell(i, fam, rail, gn, wxc, wtree, cl, lit):
    """One stripped cell.  `lit(name)` maps a literal to its driving net."""
    s = STRIP[fam]
    L, q, n = [], "q%s" % i, "n%s" % i
    # cross-coupled pull-up: source AND bulk on the rail, gate on the opposite node
    L += ["XPQ%s %s %s %s %s sg13_lv_pmos w=%gu l=0.13u" % (i, q, n, rail, rail, wxc),
          "XPN%s %s %s %s %s sg13_lv_pmos w=%gu l=0.13u" % (i, n, q, rail, rail, wxc)]
    for tag, out, ex in (("Q", q, s["TQ"]), ("N", n, s["TN"])):
        _emit(ex, out, gn, "T%s%s_" % (tag, i), gn, wtree, lit, L, [0, 0])
    L += ["CLQ%s %s %s %gf" % (i, q, gn, cl), "CLN%s %s %s %gf" % (i, n, gn, cl)]
    return L, [q, n]


# ------------------------------------------------------------------ static
# (device, gate, w_um, l_um) with d/s given as ('OUT'|'VDD'|'VSS'|port|internal)
STATIC = {
    "inv": dict(ports=["A"], out="Y", devs=[
        ("n", "Y", "A", "VSS", "VSS", 0.74, 0.13),
        ("p", "Y", "A", "VDD", "VDD", 1.12, 0.13)], internal={}),
    "nand2": dict(ports=["A", "B"], out="Y", devs=[
        ("p", "Y", "B", "VDD", "VDD", 1.12, 0.13),
        ("p", "Y", "A", "VDD", "VDD", 1.12, 0.13),
        ("n", "net1", "B", "VSS", "VSS", 0.74, 0.13),
        ("n", "Y", "A", "net1", "VSS", 0.74, 0.13)], internal={"net1": "VSS"}),
    "nor2": dict(ports=["A", "B"], out="Y", devs=[
        ("n", "Y", "A", "VSS", "VSS", 0.74, 0.13),
        ("n", "Y", "B", "VSS", "VSS", 0.74, 0.13),
        ("p", "net1", "A", "VDD", "VDD", 1.12, 0.13),
        ("p", "Y", "B", "net1", "VDD", 1.12, 0.13)], internal={"net1": "VDD"}),
    "xnor2": dict(ports=["A", "B"], out="Y", devs=[
        ("p", "Y", "net1", "VDD", "VDD", 1.12, 0.13),
        ("p", "Y", "B", "net4", "VDD", 1.12, 0.13),
        ("p", "net4", "A", "VDD", "VDD", 1.12, 0.13),
        ("p", "net1", "B", "VDD", "VDD", 0.84, 0.13),
        ("p", "net1", "A", "VDD", "VDD", 0.84, 0.13),
        ("n", "Y", "net1", "net3", "VSS", 0.74, 0.13),
        ("n", "net2", "A", "VSS", "VSS", 0.64, 0.13),
        ("n", "net1", "B", "net2", "VSS", 0.64, 0.13),
        ("n", "net3", "B", "VSS", "VSS", 0.74, 0.13),
        ("n", "net3", "A", "VSS", "VSS", 0.74, 0.13)],
        internal={"net1": "VSS", "net2": "VSS", "net3": "VSS", "net4": "VDD"}),
    "mux2": dict(ports=["A0", "A1", "S"], out="X", devs=[
        ("p", "net4", "S", "VDD", "VDD", 1.00, 0.13),
        ("p", "X", "net6", "VDD", "VDD", 1.12, 0.13),
        ("p", "net6", "A1", "net5", "VDD", 1.00, 0.13),
        ("p", "Sb", "S", "VDD", "VDD", 0.84, 0.13),
        ("p", "net5", "Sb", "VDD", "VDD", 1.00, 0.13),
        ("p", "net6", "A0", "net4", "VDD", 1.00, 0.13),
        ("n", "net3", "S", "VSS", "VSS", 0.74, 0.13),
        ("n", "net1", "Sb", "VSS", "VSS", 0.74, 0.13),
        ("n", "X", "net6", "VSS", "VSS", 0.74, 0.13),
        ("n", "Sb", "S", "VSS", "VSS", 0.55, 0.13),
        ("n", "net6", "A1", "net3", "VSS", 0.74, 0.13),
        ("n", "net6", "A0", "net1", "VSS", 0.74, 0.13)],
        internal={"Sb": "VSS", "net1": "VSS", "net3": "VSS", "net4": "VDD",
                  "net5": "VDD", "net6": "VSS"}),
    # PDK o21ai is l = 150 nm
    "o21ai": dict(ports=["A1", "A2", "B1"], out="Y", devs=[
        ("p", "net14", "A1", "VDD", "VDD", 1.12, 0.15),
        ("p", "Y", "A2", "net14", "VDD", 1.12, 0.15),
        ("p", "Y", "B1", "VDD", "VDD", 1.12, 0.15),
        ("n", "net1", "A2", "VSS", "VSS", 0.74, 0.15),
        ("n", "net1", "A1", "VSS", "VSS", 0.74, 0.15),
        ("n", "Y", "B1", "net1", "VSS", 0.74, 0.15)],
        internal={"net1": "VSS", "net14": "VDD"}),
    # the COMMITTED qal/skept hand-built o21ai: identical topology at l = 130 nm
    # (the stronger device, i.e. GENEROUS to the static control).  This is the
    # cell the committed anchor numbers were measured on.
    "o21ai_hb": dict(ports=["A1", "A2", "B1"], out="Y", devs=[
        ("p", "net14", "A1", "VDD", "VDD", 1.12, 0.13),
        ("p", "Y", "A2", "net14", "VDD", 1.12, 0.13),
        ("p", "Y", "B1", "VDD", "VDD", 1.12, 0.13),
        ("n", "net1", "A2", "VSS", "VSS", 0.74, 0.13),
        ("n", "net1", "A1", "VSS", "VSS", 0.74, 0.13),
        ("n", "Y", "B1", "net1", "VSS", 0.74, 0.13)],
        internal={"net1": "VSS", "net14": "VDD"}),
}
STATIC["inv"]["internal"] = {}


def static_devcount(fam):
    d = STATIC[fam]
    return dict(n_nmos=sum(1 for x in d["devs"] if x[0] == "n"),
                n_pmos=sum(1 for x in d["devs"] if x[0] == "p"),
                n_dev=len(d["devs"]))


def static_cell(i, fam, rail, gn, cl, drv):
    """Flat static cell.  `drv(port)` maps an input port to its driving net."""
    d = STATIC[fam]
    L = []
    mapn = {"VDD": rail, "VSS": gn, d["out"]: "y%s" % i}
    for p in d["ports"]:
        mapn[p] = drv(p)
    for nm in d["internal"]:
        mapn[nm] = "%s_%s" % (nm, i)
    nd = lambda x: mapn.get(x, x)
    for k, (t, dr, g, s, b, w, l) in enumerate(d["devs"]):
        L.append("XD%s_%d %s %s %s %s sg13_lv_%smos w=%gu l=%gu"
                 % (i, k, nd(dr), nd(g), nd(s), nd(b), t, w, l))
    for k, (nm, ref) in enumerate(d["internal"].items()):
        L.append("CI%s_%d %s %s 0.1f" % (i, k, nd(nm), nd(ref)))
    L.append("CLY%s y%s %s %gf" % (i, i, gn, cl))
    return L, ["y%s" % i], {nm: nd(nm) for nm in d["internal"]}
