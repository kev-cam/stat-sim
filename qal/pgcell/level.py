#!/usr/bin/env python3
"""(d)(b) LEVEL LOSS -- both polarities, one cell and CHAINED, with NO restoring
cell between the stages.

Three cascades of 4 cells each, at the committed delivered rail, in both
polarities and from two kinds of source:

  TGMUX   tg_mux2 with S = 0 -> X = A0.  PURE pass-gate: the data path never
          touches the rail.  This is the worst case and the one that decides
          whether pass-gate loss is ADDITIVE (charge division per stage) or
          SUB-ADDITIVE (one RC from one driven source), which is the
          pre-registered fork.
  TGXNOR  tg_xnor2 with B = 0 -> Y = Abar.  The passed node is this cell's OWN
          rail-powered inverter output, so this cascade IS restoring -- it is the
          built-from-the-same-cell control that isolates "pass gate" from
          "non-restoring".
  PDKMUX  sg13g2_mux2_1 with S = 0.  The static control.

The off path of every mux is tied to the OPPOSITE logic level through its own
ideal source, so the non-conducting transmission gate sees real data on its far
side rather than a convenient ground.
"""
import json, os, sys, time
import pg
from cells import CKPT, LONG

W = pg.TGW["tgM"]
NDEPTH = 4


def chain(tag, v, kind, hi, driven, well="rail", ports=None):
    """returns (lines, [node at each depth], expected logic value at each depth)"""
    r = "r_" + tag
    L = ["VS%s %s 0 PWL(0 0 %gp 0 %gp %.7f)"
         % (tag, r, pg.TSTEP, pg.TSTEP + pg.EDGE, v)]
    # the head source
    if driven:
        L += ["VH%s h_%s 0 %.7f" % (tag, tag, 0.0 if hi else v)]
        L += pg._inv("H" + tag, "s_" + tag, "h_" + tag, r, "0")
        L += ["CH%s s_%s 0 %gf" % (tag, tag, pg.CL)]
    else:
        L += ["VH%s s_%s 0 %.7f" % (tag, tag, v if hi else 0.0)]
    # the OFF-path data source: the opposite level, its own ideal source
    L += ["VOFF%s off_%s 0 %.7f" % (tag, tag, 0.0 if hi else v)]
    nodes, want, src = [], [], "s_" + tag
    val = 1 if hi else 0
    for d in range(1, NDEPTH + 1):
        t = "%s_%d" % (tag, d)
        o = "n%s" % t
        if kind == "TGMUX":
            L += ["VSEL%s sel_%s 0 0" % (t, t)]
            L += pg.tg_mux2(t, o, src, "off_" + tag, "sel_" + t, r, "0", W,
                            pbulk=("vhi" if well == "vhi" else None))
        elif kind == "TGXNOR":
            L += ["VB%s b_%s 0 0" % (t, t)]
            L += pg.tg_xnor2(t, o, src, "b_" + t, r, "0", W,
                             pbulk=("vhi" if well == "vhi" else None))
            val = 1 - val
        else:
            L += ["VSEL%s sel_%s 0 0" % (t, t)]
            L += ["XC%s %s %s %s %s %s %s sg13g2_mux2_1"
                  % (t, o, src, "off_" + tag, "sel_" + t, r, "0"),
                  "CL%s %s 0 %gf" % (t, o, pg.CL)]
        nodes.append(o); want.append(val); src = o
    return L, nodes, want


def build(v=pg.VREF):
    ports = pg.emit_pdk_subckts()
    L = pg.head(with_sub=True) + ["VHI vhi 0 1.5"]
    pr, meta = [], []
    for kind in ("TGMUX", "TGXNOR", "PDKMUX"):
        wells = ("rail",) if kind == "PDKMUX" else ("rail", "vhi")
        for well in wells:
            for hi in (1, 0):
                for driven in (0, 1):
                    tag = "%s%s%s%s" % (kind[:3].lower(), well[0],
                                        "h" if hi else "l", "d" if driven else "i")
                    ln, nodes, want = chain(tag, v, kind, hi, driven, well, ports)
                    L += ln
                    pr += ["V(%s)" % n for n in nodes]
                    meta.append(dict(tag=tag, kind=kind, well=well, hi=hi,
                                     driven=bool(driven), vdd=v, nodes=nodes,
                                     want=want))
    cl, cn = pg.companion()
    L += cl; pr.append("V(%s)" % cn)
    L.append(".tran 0.05p %gp 0 0.2p" % (pg.TSTEP + LONG + 100.0))
    for k in range(0, len(pr), 8):
        L.append((".print tran " if k == 0 else "+ ") + " ".join(pr[k:k + 8]))
    L.append(".end")
    return L, meta


def extract(p, meta):
    hdr, rows = pg.read_prn(p + ".prn")
    out = {}
    for d in meta:
        v = d["vdd"]
        depths = []
        for j, n in enumerate(d["nodes"]):
            ts, y = pg.col(hdr, rows, "V(%s)" % n)
            vck = pg.at_t(ts, y, pg.TSTEP + CKPT)
            vlg = pg.at_t(ts, y, pg.TSTEP + LONG)
            w = d["want"][j]
            depths.append(dict(
                depth=j + 1, want=w, v_ckpt=vck, v_long=vlg,
                loss_ckpt_mV=((v - vck) if w else vck) * 1e3,
                loss_long_mV=((v - vlg) if w else vlg) * 1e3,
                correct_ckpt=bool(vck > .5 * v) if w else bool(vck < .5 * v),
                t90_ps=(lambda t: (t - pg.TSTEP) if t else None)(
                    pg.cross(ts, y, (0.9 if w else 0.1) * v, rise=bool(w),
                             t_from=pg.TSTEP))))
        r = dict(d); r.pop("nodes"); r.pop("want")
        r["by_depth"] = depths
        out[d["tag"]] = r
    return out


if __name__ == "__main__":
    L, meta = build()
    t0 = time.monotonic()
    p = pg.run("E_level.cir", L, timeout=1500)
    if p is None:
        sys.exit(1)
    r = extract(p, meta)
    r["_wall_s"] = round(time.monotonic() - t0, 1)
    json.dump(r, open(os.path.join(pg.HERE, "LEVEL.json"), "w"), indent=1)
    for k, d in r.items():
        if not isinstance(d, dict) or "by_depth" not in d:
            continue
        print("%-9s %-7s well=%-4s %s src=%-6s  loss_ckpt(mV) by depth: %s"
              % (k, d["kind"], d.get("well", "-"), "HIGH" if d["hi"] else "LOW ",
                 "inv" if d["driven"] else "ideal",
                 " ".join("%7.3f" % x["loss_ckpt_mV"] for x in d["by_depth"])))
