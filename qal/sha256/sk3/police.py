#!/usr/bin/env python3
"""SKEPTIC's value police for the BUILT BLOCK.

It reads the SPICE DECK as the netlist -- not the .v file, not struct.py -- so
what is checked is exactly what was simulated.  Three independent things:

 1. DECK FUNCTION: evaluate the deck's own gate graph from the deck's own VPI
    source values and check the 24 primary-output nodes against MY OWN
    re-implementation of sha_slice.v.  Then prove the DECK equals the RTL
    exhaustively over every output bit's support (bit-parallel, same complete
    argument as prove.py) -- so the thing simulated is the thing proven.
 2. BOUNDARY VALUE CHECK: for every one of the 161 cells, take its measured
    voltage at ITS OWN bank's boundary out of the .mt0 and require it on the
    correct side of half that bank's measured rail at the same instant.  This is
    the pipeline check.  Compared against the END-OF-RUN value too, so a block
    that only gets the right answer as a slow combinational network is caught.
 3. SCHEDULE: re-derive the beat, the boundary times and the latency from the
    deck's own .measure AT= times.
"""
import json, os, re, sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
M = (1 << 65536) - 1

FUN = {"sg13g2_inv_1": ("inv", 1), "sg13g2_nand2_1": ("nand2", 2)}


def parse_deck(path):
    txt = open(path).read()
    pi = {}
    for m in re.finditer(r"^VPI(\d+)\s+(pi\d+)\s+0\s+([\d.eE+-]+)\s*$", txt, re.M):
        pi[m.group(2)] = float(m.group(3))
    cells = []
    for m in re.finditer(r"^XC(\d+)\s+(\S+)\s+(\S+)(?:\s+(\S+))?\s+(rail\d+)\s+"
                         r"(gn\d+)\s+(sg13g2_\w+)\s*$", txt, re.M):
        cid, out, i1, i2, rail, gnd, typ = m.groups()
        kind, nin = FUN[typ]
        ins = [i1] if nin == 1 else [i1, i2]
        assert (i2 is None) == (nin == 1), (m.group(0), nin)
        cells.append(dict(cid=int(cid), out=out, ins=ins, rail=rail, typ=typ,
                          kind=kind))
    # bank membership + boundary time, from the deck's own measures
    gm = {}
    for m in re.finditer(r"^\.measure tran G(\d+)_(\d+)B FIND V\((\S+)\) "
                         r"AT=([\d.]+)p\s*$", txt, re.M):
        gm[m.group(3)] = dict(bank=int(m.group(1)), idx=int(m.group(2)),
                              tB=float(m.group(4)), name="G%s_%sB" % (m.group(1),
                                                                     m.group(2)))
    gd = {}
    for m in re.finditer(r"^\.measure tran G(\d+)_(\d+)D FIND V\((\S+)\) "
                         r"AT=([\d.]+)p\s*$", txt, re.M):
        gd[m.group(3)] = dict(name="G%s_%sD" % (m.group(1), m.group(2)),
                              tD=float(m.group(4)))
    rb = {}
    for m in re.finditer(r"^\.measure tran VR(\d+)B\d+ FIND V\(rail(\d+)\) "
                         r"AT=([\d.]+)p\s*$", txt, re.M):
        rb[int(m.group(1))] = dict(name="VR%sB%s" % (m.group(1), m.group(1)),
                                   tB=float(m.group(3)))
    ro = {}
    for m in re.finditer(r"^\.measure tran VR(\d+)O\d+ FIND V\(rail(\d+)\) "
                         r"AT=([\d.]+)p\s*$", txt, re.M):
        ro[int(m.group(1))] = float(m.group(3))
    tran = re.search(r"^\.tran ([\d.]+)p ([\d.]+)p", txt, re.M)
    return dict(pi=pi, cells=cells, gm=gm, gd=gd, rb=rb, ro=ro,
                tend=float(tran.group(2)))


def read_mt0(path):
    """Xyce .mt0: a header row of names then a row of values (possibly wrapped)."""
    txt = open(path).read()
    out = {}
    for m in re.finditer(r"^\s*(\w+)\s*=\s*([-+\d.eE]+|[Ff][Aa][Ii][Ll][Ee][Dd])",
                         txt, re.M):
        try:
            out[m.group(1).upper()] = float(m.group(2))
        except ValueError:
            out[m.group(1).upper()] = None
    if out:
        return out
    lines = [l for l in txt.splitlines() if l.strip()]
    hdr, vals = None, []
    for l in lines:
        p = l.split()
        if hdr is None and not p[0].replace(".", "").replace("-", "").isdigit():
            hdr = [x.upper() for x in p]
        else:
            vals += p
    for k, nm in enumerate(hdr or []):
        if k < len(vals):
            try:
                out[nm] = float(vals[k])
            except ValueError:
                out[nm] = None
    return out


def topo(cells):
    drv = {c["out"]: k for k, c in enumerate(cells)}
    order, st = [], {}
    sys.setrecursionlimit(100000)

    def visit(k):
        if st.get(k) == 2:
            return
        assert st.get(k) != 1, "loop"
        st[k] = 1
        for nd in cells[k]["ins"]:
            if nd in drv:
                visit(drv[nd])
        st[k] = 2
        order.append(k)
    for k in range(len(cells)):
        visit(k)
    return order, drv


def eval_deck(cells, order, drv, pival):
    v = dict(pival)
    for k in order:
        c = cells[k]
        a = v[c["ins"][0]]
        if c["kind"] == "inv":
            v[c["out"]] = 1 - a
        else:
            v[c["out"]] = 1 - (a & v[c["ins"][1]])
    return v


def eval_deck_par(cells, order, drv, pival):
    v = dict(pival)
    for k in order:
        c = cells[k]
        a = v[c["ins"][0]]
        if c["kind"] == "inv":
            v[c["out"]] = ~a & M
        else:
            v[c["out"]] = ~(a & v[c["ins"][1]]) & M
    return v


def primary_outputs(cells):
    used = set()
    for c in cells:
        used |= set(c["ins"])
    return [c["out"] for c in cells if c["out"] not in used]


def ref(a, b, c, e, f, g):
    return ((a & b) ^ (a & c) ^ (b & c)) & 0xFF, \
           ((e & f) ^ ((~e & 0xFF) & g)) & 0xFF, (a + b) & 0xFF


def main(deck, mt0):
    d = parse_deck(deck)
    cells, pi = d["cells"], d["pi"]
    order, drv = topo(cells)
    dvhi = max(pi.values())
    pib = {k: (1 if v > dvhi / 2 else 0) for k, v in pi.items()}
    words = {}
    for nm, base in (("a", 0), ("b", 8), ("c", 16), ("e", 24), ("f", 32), ("g", 40)):
        words[nm] = sum(pib["pi%d" % (base + i)] << i for i in range(8))
    gm, gc, gs = ref(words["a"], words["b"], words["c"],
                     words["e"], words["f"], words["g"])
    # ---- 1. DECK FUNCTION at the simulated vector
    val = eval_deck(cells, order, drv, pib)
    pos = primary_outputs(cells)
    # identify which PO node is which bit: match against the reference by
    # exhaustive functional identification (bit-parallel), not by name
    A = [0] * 8
    B = [0] * 8
    for lane in range(65536):
        a, b = lane & 0xFF, (lane >> 8) & 0xFF
        for i in range(8):
            if (a >> i) & 1:
                A[i] |= 1 << lane
            if (b >> i) & 1:
                B[i] |= 1 << lane
    ident, complete_fail = {}, []
    cand, passes, parvals = {}, [], []
    nvec = 0
    for cpat in (0x00, 0xFF):
        for efg in range(8):
            ep = 0xFF if efg & 1 else 0
            fp = 0xFF if efg & 2 else 0
            gp = 0xFF if efg & 4 else 0
            pv = {}
            for i in range(8):
                pv["pi%d" % i] = A[i]
                pv["pi%d" % (8 + i)] = B[i]
                pv["pi%d" % (16 + i)] = M if (cpat >> i) & 1 else 0
                pv["pi%d" % (24 + i)] = M if (ep >> i) & 1 else 0
                pv["pi%d" % (32 + i)] = M if (fp >> i) & 1 else 0
                pv["pi%d" % (40 + i)] = M if (gp >> i) & 1 else 0
            vv = eval_deck_par(cells, order, drv, pv)
            gmv, gcv, gsv = [0] * 8, [0] * 8, [0] * 8
            carry = 0
            for i in range(8):
                ai, bi = A[i], B[i]
                ci = M if (cpat >> i) & 1 else 0
                ei = M if (ep >> i) & 1 else 0
                fi = M if (fp >> i) & 1 else 0
                gi = M if (gp >> i) & 1 else 0
                gmv[i] = (ai & bi) ^ (ai & ci) ^ (bi & ci)
                gcv[i] = (ei & fi) ^ (~ei & M & gi)
                gsv[i] = ai ^ bi ^ carry
                carry = (ai & bi) | (carry & (ai ^ bi))
            gold = {}
            for nm, arr in (("maj", gmv), ("ch", gcv), ("sum", gsv)):
                for i in range(8):
                    gold["%s[%d]" % (nm, i)] = arr[i] & M
            # identify PO nodes by INTERSECTING the candidate set across every
            # pass -- a single pass cannot separate bits that happen to agree on
            # it (with e=f=g=0 all eight ch bits are identically 0).
            for nd in pos:
                hits = {k for k, gv in gold.items() if (vv[nd] ^ gv) == 0}
                cand[nd] = hits if nd not in cand else (cand[nd] & hits)
            passes.append(gold)
            parvals.append({nd: vv[nd] for nd in pos})
            nvec += 65536
    # resolve the identification.  Uniform e/f/g patterns make all eight ch
    # bits the SAME function, so the functional candidate set cannot separate
    # them.  Break the tie RIGOROUSLY by support set: a PO node whose transitive
    # fan-in over primary inputs is exactly {pi24+i, pi32+i, pi40+i} IS ch[i].
    sup = {}
    for k in order:
        c = cells[k]
        s_ = set()
        for nd in c["ins"]:
            s_ |= sup.get(nd, {nd} if nd.startswith("pi") else set())
        sup[c["out"]] = s_
    def bitof(nd, base):
        idx = {int(x[2:]) - base for x in sup[nd] if base <= int(x[2:]) < base + 8}
        return idx
    for nd, hits in cand.items():
        if len(hits) == 1:
            ident[nd] = next(iter(hits))
            continue
        if hits and all(h.startswith("ch[") for h in hits):
            e_i, f_i, g_i = bitof(nd, 24), bitof(nd, 32), bitof(nd, 40)
            if len(e_i) == 1 and e_i == f_i == g_i:
                ident[nd] = "ch[%d]" % next(iter(e_i))
    for gold, pv in zip(passes, parvals):
        for nd, bit in ident.items():
            if (pv[nd] ^ gold[bit]) != 0:
                complete_fail.append((nd, bit))
    unresolved = {nd: sorted(cand[nd]) for nd in pos if nd not in ident}

    # ---- 2. BOUNDARY VALUE CHECK from the .mt0
    mt = read_mt0(mt0)
    rows, fails, endfails = [], [], []
    for nd, g in sorted(d["gm"].items(), key=lambda x: (x[1]["bank"], x[1]["idx"])):
        k = g["bank"]
        vb = mt.get(g["name"].upper())
        rail = mt.get(d["rb"][k]["name"].upper())
        want = val[nd]
        if vb is None or rail is None:
            fails.append(dict(node=nd, bank=k, reason="measure missing"))
            continue
        ok = (vb > 0.5 * rail) if want else (vb < 0.5 * rail)
        vd = mt.get(d["gd"][nd]["name"].upper()) if nd in d["gd"] else None
        okd = None
        if vd is not None:
            okd = (vd > 0.5 * rail) if want else (vd < 0.5 * rail)
        rows.append(dict(node=nd, bank=k, want=want, vB=vb, rail=rail,
                         frac=(vb / rail if rail else None), okB=ok,
                         vD=vd, okD=okd))
        if not ok:
            fails.append(dict(node=nd, bank=k, want=want, vB=vb, rail=rail,
                              half=0.5 * rail))
        if okd is False:
            endfails.append(dict(node=nd, bank=k, want=want, vD=vd))
    # per-bank worst settling fraction, my own computation
    perbank = defaultdict(list)
    for r in rows:
        s = (r["frac"] if r["want"] else 1.0 - r["frac"])
        perbank[r["bank"]].append(s * 100.0)
    bankworst = {k: min(v) for k, v in perbank.items()}
    # ---- 3. SCHEDULE
    tB = {k: d["rb"][k]["tB"] for k in sorted(d["rb"])}
    beats = [tB[k + 1] - tB[k] for k in sorted(tB)[:-1]]
    res = dict(deck=os.path.basename(deck), mt0=os.path.basename(mt0),
               cells=len(cells), banks=len(d["rb"]),
               n_inv=sum(1 for c in cells if c["kind"] == "inv"),
               n_nand2=sum(1 for c in cells if c["kind"] == "nand2"),
               n_VPI=len(pi), pi_swing_V=dvhi,
               vector=dict(words, maj_expected="0x%02X" % gm,
                           ch_expected="0x%02X" % gc, sum_expected="0x%02X" % gs),
               deck_vs_RTL_vectors=nvec,
               deck_vs_RTL_identified_PO=len(ident),
               deck_vs_RTL_mismatches=len(complete_fail),
               deck_PO_nodes=len(pos), deck_PO_unresolved=unresolved,
               n_checked=len(rows), n_boundary_fail=len(fails),
               n_end_fail=len(endfails),
               boundary_fails=fails[:40], end_fails=endfails[:40],
               per_bank_worst_pct={str(k): round(bankworst[k], 4)
                                   for k in sorted(bankworst)},
               worst_gate_pct=round(min(bankworst.values()), 4) if bankworst else None,
               boundary_times_ps=tB, beats_ps=beats,
               t_fire_bank1_ps=tB[1] - (beats[0] if beats else 0),
               latency_ps=tB[max(tB)] - (tB[1] - (beats[0] if beats else 0)),
               tran_end_ps=d["tend"])
    return res, rows, ident


if __name__ == "__main__":
    res, rows, ident = main(sys.argv[1], sys.argv[2])
    tag = re.sub(r"\.cir$", "", os.path.basename(sys.argv[1]))
    json.dump(dict(summary=res, rows=rows,
                   po_identification={k: v for k, v in ident.items()}),
              open(os.path.join(HERE, "POLICE_%s.json" % tag), "w"), indent=1)
    for k in ("deck", "cells", "banks", "n_inv", "n_nand2", "n_VPI",
              "pi_swing_V", "vector", "deck_vs_RTL_vectors",
              "deck_vs_RTL_identified_PO", "deck_vs_RTL_mismatches",
              "n_checked", "n_boundary_fail", "n_end_fail", "worst_gate_pct",
              "beats_ps", "latency_ps", "tran_end_ps"):
        print("%-28s %s" % (k, res[k]))
    print("per_bank_worst_pct", res["per_bank_worst_pct"])
    if res["boundary_fails"]:
        print("BOUNDARY FAILS:", json.dumps(res["boundary_fails"][:10], indent=1))
