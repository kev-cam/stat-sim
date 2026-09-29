#!/usr/bin/env python3
"""SUPPLEMENT to RAILDRAW: the SAME populations with the pass pMOS n-well taken
OFF the bank rail and put on the global +1.5 V supply.  Without this control the
PROPER row cannot distinguish 'a transmission gate draws from the rail' from
'a transmission gate whose WELL is tied to the rail draws from the rail'."""
import json, os, sys, time
import pg, raildraw as rd
from cells import XNOR_VEC, MUX_VEC, xnor_y, mux_x, CKPT, LONG
W = pg.TGW["tgM"]; v = pg.VREF


def c_proper_vhi(tag, hi):
    r, vs = "r_" + tag, "VS" + tag
    wn, wp = W
    L = rd.ramp("S" + tag, r, v)
    L += rd.ramp("G" + tag, "gn_" + tag, v)
    L += ["VGP%s gp_%s 0 0" % (tag, tag),
          "VD%s d_%s 0 %.7f" % (tag, tag, v if hi else 0.0)]
    L += pg._tg(tag, "d_" + tag, "y_" + tag, "gn_" + tag, "gp_" + tag, r, "0",
                wn, wp, pbulk="vhi")
    L += ["CL%s y_%s 0 %gf" % (tag, tag, pg.CL)]
    return L + rd.meter(tag, r, vs, [("VD" + tag, "d_" + tag)]), "y_" + tag


def c_whole_mux_vhi(tag, a0, a1, s):
    r, vs = "r_" + tag, "VS" + tag
    L = rd.ramp("S" + tag, r, v); ins = []
    for nm, bit in (("a0", a0), ("a1", a1), ("s", s)):
        L += ["VD%s%s %s_%s 0 %.7f" % (nm, tag, nm, tag, v if bit else 0.0)]
        ins.append(("VD%s%s" % (nm, tag), "%s_%s" % (nm, tag)))
    L += pg.tg_mux2(tag, "x_" + tag, "a0_" + tag, "a1_" + tag, "s_" + tag, r, "0",
                    W, pbulk="vhi")
    return L + rd.meter(tag, r, vs, ins), "x_" + tag


L = pg.head(with_sub=True) + ["VHI vhi 0 1.5"]
pr, meta = [], []


def add(tag, lines, node, **kw):
    L.extend(lines); pr.append("V(%s)" % node)
    pr.extend(["V(x%s%s)" % (p, tag) for p in ("q", "e", "qi", "ei")])
    meta.append(dict(tag=tag, node=node, vdd=v, **kw))


for hi in (0, 1):
    t = "qp%d" % hi
    ln, nd = c_proper_vhi(t, hi)
    add(t, ln, nd, pop="PROPER_VHI", cell="tg_only_vhiwell", vec=dict(D=hi),
        want=hi, path="transparent")
for a0, a1, s in MUX_VEC:
    t = "qm%d%d%d" % (a0, a1, s)
    ln, nd = c_whole_mux_vhi(t, a0, a1, s)
    add(t, ln, nd, pop="WHOLE_VHI", cell="tg_mux2_vhiwell",
        vec=dict(A0=a0, A1=a1, S=s), want=mux_x(a0, a1, s), path="transparent")
cl, cn = pg.companion(); L += cl; pr.append("V(%s)" % cn)
L.append(".tran 0.05p %gp 0 0.2p" % (pg.TSTEP + LONG + 100.0))
for k in range(0, len(pr), 8):
    L.append((".print tran " if k == 0 else "+ ") + " ".join(pr[k:k + 8]))
L.append(".end")
p = pg.run("D2_raildraw_vhi.cir", L, timeout=1200)
if p is None:
    sys.exit(1)
r = rd.extract(p, meta)
json.dump(r, open(os.path.join(pg.HERE, "RAILDRAW_VHI.json"), "w"), indent=1)
for k, d in r.items():
    print("%-7s %-18s q_rail %8.4f fC  e_rail %8.4f fJ  q_in %8.4f fC  ok %s"
          % (k, d["cell"], d["q_rail_fC"], d["e_rail_fJ"],
             d["q_in_fC"] if d["q_in_fC"] is not None else float("nan"),
             d["correct_ckpt"]))
