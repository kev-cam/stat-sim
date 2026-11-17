#!/usr/bin/env python3
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# SPDX-FileCopyrightText: 2026 D. Kevin Cameron
# Part of stat-sim. PolyForm Noncommercial License 1.0.0; commercial use needs a separate license (see LICENSE, COMMERCIAL.md).
"""
layrc.py -- wiring parasitics for a KLayout-extracted netlist, from mylex's layopt.

KLayout's LVS deck gives the devices (MOS, poly resistors, MiM / finger capacitors) but no
wiring R/C; layopt gives per-net capacitance and a resistor mesh over the wiring rectangles
but only knows MOS devices.  This joins the two:

  1. layopt nets are matched to KLayout nets by position: every contact/via KLayout puts on a
     net is looked up in layopt's shapes.  (Several layopt nets may map to one KLayout net --
     layopt does not connect through the substrate -- but never the other way round.)
  2. every KLayout device terminal is located on layopt's shapes of that net.
  3. per net: C is layopt's area + fringe capacitance; R is the exact effective resistance
     between the terminals (sparse solve on the mesh), reduced to a star -- one resistor from
     each terminal to the net node -- by non-negative least squares.

Result (JSON, consumed by ext2xyce.py --rc):
    {"nets": {"<klayout net>": {"c_fF": .., "terms": {"<device id>:<terminal>": ohms}}}}

    layrc.py x.gds x.lvsdb -o x_rc.json [--top CELL] [--layopt /usr/local/src/mylex]
"""
import argparse
import collections
import json
import sys

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla
from scipy.optimize import nnls

# where a device terminal lands when several layers of the net overlap it: the lowest one
STACK = ["gate", "sd_n", "sd_p", "poly", "li", "met1", "met2", "met3", "capm", "met4", "cap2m", "met5"]
MAX_STAR = 500          # terminals per connected piece above which the star is not fitted


def star_fit(R):
    """r_i >= 0 minimising sum (r_i + r_j - R_ij)^2; returns (r, rms relative error)."""
    k = len(R)
    if k == 2:
        return np.array([R[0, 1] / 2, R[0, 1] / 2]), 0.0
    iu, ju = np.triu_indices(k, 1)
    A = np.zeros((len(iu), k))
    A[np.arange(len(iu)), iu] = 1.0
    A[np.arange(len(iu)), ju] = 1.0
    b = R[iu, ju]
    r, _ = nnls(A, b)
    err = float(np.sqrt(np.mean((A @ r - b) ** 2)) / max(np.sqrt(np.mean(b ** 2)), 1e-30))
    return r, err


def piece_stars(segs, groups):
    """segs: [(a, b, ohms)] over shape ids; groups: {terminal key: set of shape ids}.
    Returns ({terminal key: star ohms}, [fit errors]) -- one star per connected piece."""
    # contract each terminal's shapes into one node
    rep = {}
    for key, ids in groups.items():
        ids = sorted(ids)
        for s in ids:
            rep.setdefault(s, ids[0])
    nodes = {}
    def node(s):
        return nodes.setdefault(rep.get(s, s), len(nodes))
    rows, cols, vals = [], [], []
    for a, b, r in segs:
        i, j = node(a), node(b)
        if i == j:
            continue
        g = 1.0 / max(r, 1e-3)
        rows += [i, j, i, j]; cols += [i, j, j, i]; vals += [g, g, -g, -g]
    tnode = collections.defaultdict(list)           # mesh node -> terminal keys sharing it
    for key, ids in groups.items():
        tnode[node(min(ids))].append(key)
    n = len(nodes)
    out, errs = {k: 0.0 for k in groups}, []
    if n < 2 or not vals:
        return out, errs
    Lp = sp.csr_matrix((vals, (rows, cols)), shape=(n, n))
    ncomp, comp = sp.csgraph.connected_components(Lp, directed=False)
    by_comp = collections.defaultdict(list)
    for nd in tnode:
        by_comp[comp[nd]].append(nd)
    for c, tn in by_comp.items():
        k = len(tn)
        if k < 2 or k > MAX_STAR:
            continue
        members = np.flatnonzero(comp == c)
        ref = tn[0]
        keep = members[members != ref]
        pos = {m: i for i, m in enumerate(keep)}
        lu = spla.splu(Lp[keep][:, keep].tocsc())
        Z = np.zeros((k, k))                         # Z[i, j] = volts at tn[i] for 1 A into tn[j], ref grounded
        for j in range(1, k):
            rhs = np.zeros(len(keep)); rhs[pos[tn[j]]] = 1.0
            v = lu.solve(rhs)
            for i in range(1, k):
                Z[i, j] = v[pos[tn[i]]]
        d = np.diag(Z)
        R = d[:, None] + d[None, :] - Z - Z.T
        r, err = star_fit(R)
        errs.append((err, k, float(R.max())))
        for nd, ri in zip(tn, r):
            for key in tnode[nd]:
                out[key] = float(ri)
    return out, errs


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("gds")
    ap.add_argument("lvsdb")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--top")
    ap.add_argument("--tech", default="sky130")
    ap.add_argument("--layopt", default="/usr/local/src/mylex", help="directory holding the layopt package")
    a = ap.parse_args()
    sys.path.insert(0, a.layopt)
    import klayout.db as kdb
    from layopt import extract, gds, geom, rc, tech

    fl = gds.flatten(gds.read(a.gds), a.top)
    ex = extract.extract(fl, tech.get(a.tech))
    T = ex.tech
    print(f"layopt: {len(ex.shapes)} shapes, {len(ex.nets)} nets, {len(ex.devices)} MOS, {len(ex.res_bodies)} resistor bodies cut")
    index = {}
    for i, s in enumerate(ex.shapes):
        index.setdefault(s.layer, geom.BinIndex()).add(i, s.rect)
    gds2name = {v: k for k, v in T.layers.items()}

    lvs = kdb.LayoutVsSchematic()
    lvs.read(a.lvsdb)
    ckt = lvs.netlist().circuit_by_name(a.top or ex.top) or next(lvs.netlist().each_circuit_top_down())
    scale = lvs.internal_layout().dbu / ex.dbu_um     # klayout dbu -> layopt dbu
    cuts = {}
    for li in lvs.layer_indexes():
        info = lvs.layer_info(li)
        name = gds2name.get((info.layer, info.datatype))
        if name in set([T.diff_contact] + [c for _, c, _ in T.vias]):
            cuts[name] = lvs.layer_by_index(li)

    # 1. layopt net -> klayout net, through the cuts
    cand = collections.defaultdict(set)              # layopt net id -> klayout nets seen on its cuts
    knets = {}
    for net in ckt.each_net():
        kn = net.expanded_name()
        knets[kn] = net
        for lname, region in cuts.items():
            for poly in lvs.shapes_of_net(net, region, True).each():
                c = poly.bbox().center()
                x, y = int(round(c.x * scale)), int(round(c.y * scale))
                for sid in index[lname].candidates((x, y, x, y)) if lname in index else ():
                    r = ex.shapes[sid].rect
                    if r[0] <= x <= r[2] and r[1] <= y <= r[3]:
                        cand[ex.net_of_shape[sid]].add(kn)
                        break
    # The LVS deck leaves some cuts unconnected (e.g. via4 inside a finger-capacitor marker):
    # each becomes a one-shape net with no device on it.  Those are not real nets.
    live = lambda kn: knets[kn].terminal_count() + knets[kn].pin_count() > 0
    l_of = collections.defaultdict(list)             # klayout net -> layopt nets
    orphans = 0
    for ln, ks in sorted(cand.items()):
        real = sorted(k for k in ks if live(k))
        orphans += len(ks) - len(real)
        if len(real) == 1:
            l_of[real[0]].append(ln)
        elif len(real) > 1:
            print(f"  WARNING: layopt net {ln} spans klayout nets {real} (layopt shorts them); skipped")
    print(f"matched {sum(len(v) for v in l_of.values())} layopt nets to {len(l_of)} of "
          f"{sum(live(k) for k in knets)} klayout nets with devices ({orphans} device-less klayout fragments ignored)")

    # 2. device terminals -> layopt shapes
    terms = collections.defaultdict(dict)            # klayout net -> {"<dev>:<term>": set(shape ids)}
    unplaced = collections.Counter()
    for kn, net in knets.items():
        lset = set(l_of.get(kn, ()))
        if not lset:
            continue
        for tr in net.each_terminal():
            key = f"{tr.device().expanded_name()}:{tr.terminal_def().name}"
            found = collections.defaultdict(set)
            for region in lvs.shapes_of_terminal(tr).values():
                for poly in region.each():
                    b = poly.bbox()
                    q = (int(b.left * scale), int(b.bottom * scale), int(b.right * scale), int(b.top * scale))
                    for lname in STACK:
                        if lname in index:
                            for sid in index[lname].query_overlap(q):
                                if ex.net_of_shape[sid] in lset:
                                    found[lname].add(sid)
            for lname in STACK:
                if found[lname]:
                    terms[kn][key] = found[lname]
                    break
            else:
                unplaced[tr.device().device_class().name + "." + tr.terminal_def().name] += 1
    if unplaced:
        print("terminals with no wiring shape (bulk/well terminals are expected here): "
              + ", ".join(f"{k} x{v}" for k, v in sorted(unplaced.items())))

    # 3. per net C and star R
    out, allerr = {}, []
    for kn, lns in sorted(l_of.items()):
        if not lns:
            continue
        c = sum(rc.net_rc(ex, ln, with_segments=False).c_fF for ln in lns)
        star = {}
        for ln in lns:
            groups = {k: ids for k, ids in terms[kn].items() if ex.net_of_shape[min(ids)] == ln}
            if len(groups) < 2:
                star.update({k: 0.0 for k in groups})
                continue
            segs = [(s.a, s.b, s.r) for s in rc.net_segments(ex, ln)]
            r, errs = piece_stars(segs, groups)
            star.update(r)
            allerr += [(e, k, rmax, kn) for e, k, rmax in errs]
        out[kn] = {"c_fF": round(c, 4), "terms": {k: round(v, 4) for k, v in sorted(star.items())}}
    json.dump({"gds": a.gds, "lvsdb": a.lvsdb, "nets": out}, open(a.out, "w"), indent=1)
    rs = [v for n in out.values() for v in n["terms"].values()]
    print(f"{len(out)} nets, total C {sum(n['c_fF'] for n in out.values()):.1f} fF, {len(rs)} terminals, "
          f"star R median {np.median(rs):.1f} / max {max(rs):.1f} ohm")
    worst = sorted(allerr, reverse=True)[:5]
    if worst:
        print("star fit, worst rms relative error against the exact terminal-to-terminal resistances:")
        for e, k, rmax, kn in worst:
            print(f"  net {kn}: {k} terminals, largest R {rmax:.1f} ohm, error {100 * e:.1f} %")
    print(f"written to {a.out}")


if __name__ == "__main__":
    main()
