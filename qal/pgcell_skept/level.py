#!/usr/bin/env python3
"""(a)/(b) LEVEL LOSS: one cell, and a cascade, on a FIXED rail.

Supporting measurement for the tank-fed chain.  Four 4-deep cascades on a rail
that ramps 0 -> VREF at TSTEP:
  TGC   tg_mux2, S=0, off path = an ADVERSARIAL neighbour at the opposite level
        (the wiring the run used)
  TGB   tg_mux2, S=0, off path tied to the ON path  (no data contention)
  ALT   inv, tg, inv, tg  with the adversarial off path
  ALTB  inv, tg, inv, tg  with the benign off path
Each in BOTH well ties and BOTH input polarities.  Level is read at every depth,
so 'does the loss grow with depth' is answered per stage rather than inferred.

The chain head is an IDEAL source -- declared: those rows are BOUNDS.  A second
head variant drives the chain from a REAL rail-powered inverter, because what a
pass gate can reach depends on what is holding its input up.
"""
import json, os, sys, time
import sk

V = sk.VREF
DEPTH = 4


def ramp(tag, node, v=V):
    return ["VS%s %s 0 PWL(0 0 %gp 0 %gp %.7f)" % (tag, node, sk.TSTEP,
                                                   sk.TSTEP + sk.EDGE, v)]


def cascade(tag, kinds, well, hi, offmode, head):
    """returns (lines, [node at each depth], meta)"""
    r = "r_" + tag
    pb = "vhi" if well == "vhi" else r
    L = ramp(tag, r)
    if head == "ideal":
        L += ["VH%s h_%s 0 %.7f" % (tag, tag, V if hi else 0.0),
              "VO%s ho_%s 0 %.7f" % (tag, tag, 0.0 if hi else V)]
    else:                       # a REAL rail-powered inverter drives the chain
        L += ["VH%s hi_%s 0 %.7f" % (tag, tag, 0.0 if hi else V),
              "VO%s hoi_%s 0 %.7f" % (tag, tag, V if hi else 0.0)]
        L += sk.inv("H" + tag, "h_" + tag, "hi_" + tag, r, "0")
        L += sk.inv("O" + tag, "ho_" + tag, "hoi_" + tag, r, "0")
        L += ["CH%s h_%s 0 %gf" % (tag, tag, sk.CL),
              "CO%s ho_%s 0 %gf" % (tag, tag, sk.CL)]
    cur, off = "h_" + tag, "ho_" + tag
    nodes, want = [], []
    lvl = hi
    for d, kind in enumerate(kinds, 1):
        o = "n%d_%s" % (d, tag)
        t = "%d%s" % (d, tag)
        if kind == "inv":
            L += sk.inv(t, o, cur, r, "0")
            L += ["CL%s %s 0 %gf" % (t, o, sk.CL)]
            lvl = 1 - lvl
            off = cur                       # previous stage level, opposite sense
        else:
            a1 = off if offmode == "adv" else cur
            L += ["VD%s sel_%s 0 0" % (t, t)]
            L += sk.tg_mux2(t, o, cur, a1, "sel_" + t, r, "0", pb)
            L += ["CSB%s sb_%s 0 %gf" % (t, t, sk.CINT)]
            off = a1
        nodes.append(o)
        want.append(lvl)
        cur = o
    return L, nodes, want


def build():
    L = sk.head() + ["VHI vhi 0 %g" % sk.VHI]
    pr, meta = [], []
    for well in ("vhi", "rail"):
        for hi in (0, 1):
            for cname, kinds in (("TGC", ["tg"] * DEPTH),
                                 ("ALT", ["inv", "tg", "inv", "tg"])):
                for offmode in ("adv", "ben"):
                    for head in ("ideal", "real"):
                        if head == "real" and offmode == "ben":
                            continue        # keep the deck inside its budget
                        tag = "%s%s%d%s%s" % (cname[:3].lower(), well[0], hi,
                                              offmode[0], head[0])
                        ln, nodes, want = cascade(tag, kinds, well, hi, offmode, head)
                        L += ln
                        pr += ["V(%s)" % n for n in nodes]
                        meta.append(dict(tag=tag, chain=cname, kinds=kinds,
                                         well=well, head_hi=hi, off=offmode,
                                         head=head, nodes=nodes, want=want))
    cl, cn = sk.companion()
    L += cl
    pr.append("V(%s)" % cn)
    L.append(".tran 0.02p %gp 0 0.05p" % (sk.TSTEP + sk.LONG + 100.0))
    for k in range(0, len(pr), 8):
        L.append((".print tran " if k == 0 else "+ ") + " ".join(pr[k:k + 8]))
    L.append(".end")
    return L, meta


def extract(p, meta):
    hdr, rows = sk.read_prn(p + ".prn")
    out = {}
    for d in meta:
        r = dict(d)
        vs, ok = [], []
        for n, w in zip(d["nodes"], d["want"]):
            ts, y = sk.col(hdr, rows, "V(%s)" % n)
            vck = sk.at_t(ts, y, sk.TSTEP + sk.CKPT)
            vlg = sk.at_t(ts, y, sk.TSTEP + sk.LONG)
            loss_ck = (V - vck) if w else (vck - 0.0)
            loss_lg = (V - vlg) if w else (vlg - 0.0)
            vs.append(dict(node=n, want_hi=w, v_ckpt=vck, v_long=vlg,
                           loss_ckpt_mV=1e3 * loss_ck, loss_long_mV=1e3 * loss_lg,
                           correct=bool(vck > .5 * V) if w else bool(vck < .5 * V)))
            ok.append(vs[-1]["correct"])
        r["by_depth"] = vs
        r["all_correct"] = bool(all(ok))
        r["loss_ckpt_by_depth_mV"] = [x["loss_ckpt_mV"] for x in vs]
        r["loss_long_by_depth_mV"] = [x["loss_long_mV"] for x in vs]
        r["loss_grows_with_depth"] = bool(
            all(abs(vs[j + 1]["loss_long_mV"]) >= abs(vs[j]["loss_long_mV"]) - 1e-9
                for j in range(len(vs) - 1)))
        out[d["tag"]] = r
    ts, y = sk.col(hdr, rows, "V(O_ZC)")
    out["_instr_inv1p2_t90_ps"] = sk.t_cross(ts, y, 0.9 * 1.2, sk.TSTEP)
    return out


if __name__ == "__main__":
    L, meta = build()
    t0 = time.monotonic()
    p = sk.run("L_level.cir", L, timeout=1800)
    if p is None:
        sys.exit(1)
    r = extract(p, meta)
    r["_wall_s"] = round(time.monotonic() - t0, 1)
    json.dump(r, open(os.path.join(sk.HERE, "LEVEL_SKEPT.json"), "w"), indent=1)
    for k, d in r.items():
        if not isinstance(d, dict):
            continue
        print("%-12s %-4s %-5s well=%-4s hi=%d off=%-3s head=%-5s loss@ckpt %s  ok=%s"
              % (k, d["chain"], "", d["well"], d["head_hi"], d["off"], d["head"],
                 ["%.2f" % x for x in d["loss_ckpt_by_depth_mV"]], d["all_correct"]))
    print("INSTRUMENT 1.2V inverter t90 = %.4f ps" % r["_instr_inv1p2_t90_ps"])
