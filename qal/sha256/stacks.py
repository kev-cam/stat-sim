#!/usr/bin/env python3
"""STATIC stack-depth analysis of the sha_slice cell census, read from the PDK SPICE.

No simulation.  For each cell in the committed mapped netlist's census this parses
sg13g2_stdcell.spice, builds the transistor graph, and for EVERY input vector works
out, by switch-level evaluation:

  * which internal/output nodes are driven to VDD (the QAL *rail*) and which to VSS
  * for every node that must RISE, the SERIES DEPTH of pMOS devices between it and
    VDD on the shallowest conducting path (the path that actually charges it)
  * the cell's logic function (for the census deck's expected-value check)

The QAL-relevant number is `pmos_rise_depth`: on a QAL rail the output (and every
internal node that gates it) has to be dragged UP by the pull-up network as the rail
itself rises, so a k-high pMOS series stack must hold |Vgs|>|Vt| on k devices with
the source of the upper one already below the rail.  A cell is "shallow" only if
EVERY node it must raise, for EVERY input vector, is raised through depth 1.

Outputs cells/stack_depths.json.
"""
import json, os, re, sys
from itertools import product

PDK = ("/usr/local/src/IHP-Open-PDK/ihp-sg13g2/libs.ref/sg13g2_stdcell/spice/"
       "sg13g2_stdcell.spice")
HERE = os.path.dirname(os.path.abspath(__file__))

# the census of the committed mapped netlist work/sha_slice.cmos.v
CENSUS = {"sg13g2_xnor2_1": 10, "sg13g2_mux2_1": 8, "sg13g2_a21oi_1": 6,
          "sg13g2_o21ai_1": 5, "sg13g2_nor2_1": 5, "sg13g2_nand2_1": 5,
          "sg13g2_or2_1": 3, "sg13g2_nor2b_1": 3, "sg13g2_inv_1": 3,
          "sg13g2_and2_1": 3, "sg13g2_a21o_1": 3, "sg13g2_xor2_1": 2}


def parse(path, want):
    """-> {cell: dict(ports=[...], devs=[(name,d,g,s,b,type,w,l)])}"""
    out, cur, buf = {}, None, []
    for ln in open(path):
        s = ln.strip()
        if s.lower().startswith(".subckt"):
            cur, buf = s.split()[1], []
            ports = s.split()[2:]
        elif s.lower().startswith(".ends"):
            if cur in want:
                out[cur] = dict(ports=ports, devs=buf)
            cur = None
        elif cur is not None and s and not s.startswith("*"):
            p = s.split()
            if len(p) >= 6 and p[0][0].upper() == "X":
                kw = dict(x.split("=") for x in p[6:] if "=" in x)
                out.setdefault("_", None)
                buf.append(dict(name=p[0], d=p[1], g=p[2], s=p[3], b=p[4],
                                typ="p" if "pmos" in p[5] else "n",
                                w=kw.get("w", "?"), l=kw.get("l", "?")))
    out.pop("_", None)
    return out


def inputs_of(cell, ports, devs):
    """input ports = ports that are not VDD/VSS and not driven by any device drain"""
    driven = {d["d"] for d in devs} | {d["s"] for d in devs if d["s"] not in ("VDD", "VSS")}
    ins = [p for p in ports if p not in ("VDD", "VSS") and p not in
           {d["d"] for d in devs}]
    return ins


def evaluate(devs, vec, supply=("VDD", "VSS")):
    """Switch-level solve.  Returns (node_levels, rise_depth) where rise_depth[n]
    is the minimum number of pMOS in series between VDD and n along a path whose
    every gate is ON, for nodes that resolve HIGH; and the nMOS series depth to VSS
    for nodes that resolve LOW (reported separately).

    Iterates to a fixed point because a node's level gates other devices."""
    VDD, VSS = supply
    lev = dict(vec)
    lev[VDD], lev[VSS] = 1, 0
    nodes = set()
    for d in devs:
        nodes |= {d["d"], d["s"], d["g"]}
    nodes -= {VDD, VSS}
    for n in nodes:
        lev.setdefault(n, None)

    def on(d):
        g = lev.get(d["g"])
        if g is None:
            return None                      # unknown gate -> unknown switch
        return (g == 0) if d["typ"] == "p" else (g == 1)

    for _ in range(40):
        # BFS from VDD through ON pMOS, from VSS through ON nMOS
        up, dn = {VDD: 0}, {VSS: 0}
        for _ in range(12):
            for d in devs:
                st = on(d)
                if st is not True:
                    continue
                if d["typ"] == "p":
                    for a, b in ((d["d"], d["s"]), (d["s"], d["d"])):
                        if a in up and up[a] + 1 < up.get(b, 99):
                            up[b] = up[a] + 1
                else:
                    for a, b in ((d["d"], d["s"]), (d["s"], d["d"])):
                        if a in dn and dn[a] + 1 < dn.get(b, 99):
                            dn[b] = dn[a] + 1
        new = dict(lev)
        for n in nodes:
            if n in vec:
                continue
            u, w = n in up, n in dn
            new[n] = 1 if (u and not w) else 0 if (w and not u) else \
                (1 if (u and w) else None)   # contention -> call it high (ratioed)
        if new == lev:
            break
        lev = new
    return lev, up, dn


def analyse(cell, info):
    ports, devs = info["ports"], info["devs"]
    ins = inputs_of(cell, ports, devs)
    outp = ports[0]              # IHP convention: first port is the output
    gates = {d["g"] for d in devs}          # nodes that CONTROL a device
    binding = gates | {outp}                # a pure series node need not settle
    rows = []
    for vals in product((0, 1), repeat=len(ins)):
        vec = dict(zip(ins, vals))
        lev, up, dn = evaluate(devs, vec)
        # every non-input, non-supply node that resolves HIGH must be RAISED
        rise = {n: up[n] for n in up if n not in ("VDD",) and n not in vec
                and lev.get(n) == 1}
        fall = {n: dn[n] for n in dn if n not in ("VSS",) and n not in vec
                and lev.get(n) == 0}
        brise = {n: v for n, v in rise.items() if n in binding}
        rows.append(dict(vec=vec, out=lev.get(outp), lev=lev,
                         rise=rise, fall=fall, brise=brise,
                         max_rise=max(rise.values()) if rise else 0,
                         bind_rise=max(brise.values()) if brise else 0,
                         out_rise=up.get(outp) if lev.get(outp) == 1 else None,
                         max_fall=max(fall.values()) if fall else 0))
    # worst vectors, ranked on the BINDING rise depth
    wr = max(rows, key=lambda r: (r["bind_rise"], r["out"] == 1))
    hi = [r for r in rows if r["out"] == 1]
    lo = [r for r in rows if r["out"] == 0]
    wr_hi = max(hi, key=lambda r: (r["out_rise"] or 0, r["bind_rise"])) if hi else None
    wr_lo = max(lo, key=lambda r: r["bind_rise"]) if lo else None
    return dict(
        cell=cell, count=CENSUS.get(cell), inputs=ins, output=outp,
        n_dev=len(devs), n_p=sum(1 for d in devs if d["typ"] == "p"),
        n_n=sum(1 for d in devs if d["typ"] == "n"),
        L_nm=sorted({d["l"] for d in devs}),
        gating_nodes=sorted(n for n in gates if n not in ins and n not in ("VDD", "VSS")),
        pmos_series_topological=max_series(devs, "p"),
        nmos_series_topological=max_series(devs, "n"),
        max_pmos_rise_depth=max(r["max_rise"] for r in rows),
        binding_pmos_rise_depth=max(r["bind_rise"] for r in rows),
        max_out_pmos_rise_depth=max((r["out_rise"] or 0) for r in rows),
        worst_rise_vec=wr["vec"], worst_rise_depth=wr["bind_rise"],
        worst_rise_nodes={k: v for k, v in wr["brise"].items()
                          if v == wr["bind_rise"]},
        vec_out_hi=wr_hi["vec"] if wr_hi else None,
        vec_out_hi_depth=wr_hi["out_rise"] if wr_hi else None,
        vec_out_hi_maxrise=wr_hi["bind_rise"] if wr_hi else None,
        vec_out_lo=wr_lo["vec"] if wr_lo else None,
        vec_out_lo_maxrise=wr_lo["bind_rise"] if wr_lo else None,
        vec_out_lo_nodes={k: v for k, v in (wr_lo or {}).get("brise", {}).items()
                          if v == (wr_lo or {}).get("bind_rise")},
        truth={"".join(str(v) for v in r["vec"].values()): r["out"] for r in rows},
    )


def max_series(devs, typ):
    """topological longest series run of `typ` devices from its supply, over the
    device graph ignoring gate values (an upper bound on stack height)."""
    sup = "VDD" if typ == "p" else "VSS"
    adj = {}
    for d in devs:
        if d["typ"] != typ:
            continue
        adj.setdefault(d["d"], []).append((d["s"], d["name"]))
        adj.setdefault(d["s"], []).append((d["d"], d["name"]))
    best = 0
    stack = [(sup, 0, frozenset())]
    while stack:
        n, k, used = stack.pop()
        best = max(best, k)
        if k > 6:
            continue
        for m, nm in adj.get(n, []):
            if nm in used:
                continue
            stack.append((m, k + 1, used | {nm}))
    return best


if __name__ == "__main__":
    cells = parse(PDK, set(CENSUS))
    res = {c: analyse(c, cells[c]) for c in CENSUS}
    os.makedirs(os.path.join(HERE, "cells"), exist_ok=True)
    json.dump(res, open(os.path.join(HERE, "cells", "stack_depths.json"), "w"),
              indent=1, default=str)
    print("%-18s %3s %3s %3s %5s %5s %6s %5s %5s  %s" %
          ("cell", "n", "nP", "nN", "pSER", "nSER", "BINDrise", "any", "out", "L"))
    for c, r in sorted(res.items(), key=lambda kv: -kv[1]["count"]):
        print("%-18s %3d %3d %3d %5d %5d %6d %5d %5d  L=%s  worst=%s -> %s"
              % (c, r["count"], r["n_p"], r["n_n"],
                 r["pmos_series_topological"], r["nmos_series_topological"],
                 r["binding_pmos_rise_depth"], r["max_pmos_rise_depth"],
                 r["max_out_pmos_rise_depth"], ",".join(r["L_nm"]),
                 r["worst_rise_vec"], r["worst_rise_nodes"]))
    sh = [c for c, r in res.items() if r["binding_pmos_rise_depth"] <= 1]
    tot = sum(r["count"] for r in res.values())
    shn = sum(res[c]["count"] for c in sh)
    print("\nSHALLOW (binding pMOS rise depth <= 1): %s" % sorted(sh))
    print("cells covered: %d of %d instances" % (shn, tot))
