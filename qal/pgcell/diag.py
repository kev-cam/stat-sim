#!/usr/bin/env python3
"""Diagnostic: print every internal node of the failing TG-XNOR2 vector."""
import json, sys, pg
from cells import CKPT, LONG
v = pg.VREF; w = pg.TGW["tgM"]
L = pg.head() + ["VHI vhi 0 1.5"]
pr = []
for well in ("rail", "vhi"):
    for (a, b) in ((1, 0), (0, 0)):
        t = "%s%d%d" % (well[0], a, b)
        L += ["VS%s r_%s 0 PWL(0 0 %gp 0 %gp %.7f)" % (t, t, pg.TSTEP, pg.TSTEP+pg.EDGE, v),
              "VDA%s a_%s 0 %.7f" % (t, t, v if a else 0.0),
              "VDB%s b_%s 0 %.7f" % (t, t, v if b else 0.0)]
        L += pg.tg_xnor2(t, "y_"+t, "a_"+t, "b_"+t, "r_"+t, "0", w,
                         pbulk=("vhi" if well == "vhi" else None))
        pr += ["V(y_%s)" % t, "V(ab_%s)" % t, "V(bb_%s)" % t, "V(r_%s)" % t]
cl, cn = pg.companion(); L += cl; pr.append("V(%s)" % cn)
L.append(".tran 0.05p %gp 0 0.2p" % (pg.TSTEP+LONG+100))
for k in range(0, len(pr), 8):
    L.append((".print tran " if k == 0 else "+ ") + " ".join(pr[k:k+8]))
L.append(".end")
p = pg.run("G_diag.cir", L, timeout=900)
hdr, rows = pg.read_prn(p+".prn")
for well in ("rail", "vhi"):
    for (a, b) in ((1, 0), (0, 0)):
        t = "%s%d%d" % (well[0], a, b)
        print("== well=%s A=%d B=%d   (Y should be %d)" % (well, a, b, 1 if a == b else 0))
        for lbl in ("y", "ab", "bb", "r"):
            ts, y = pg.col(hdr, rows, "V(%s_%s)" % (lbl, t))
            print("   %-3s  t=0 %8.5f | 99ps %8.5f | 110ps %8.5f | 200ps %8.5f | ckpt %8.5f | long %8.5f"
                  % (lbl, pg.at_t(ts,y,0.0), pg.at_t(ts,y,99.0), pg.at_t(ts,y,110.0),
                     pg.at_t(ts,y,200.0), pg.at_t(ts,y,pg.TSTEP+CKPT), pg.at_t(ts,y,pg.TSTEP+LONG)))
