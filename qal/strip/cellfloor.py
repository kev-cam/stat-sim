#!/usr/bin/env python3
"""THE CELL FLOOR -- stripped vs static on an IDEAL STIFF RAIL.

Every row in st.py couples two things that must be separated before any verdict:

  (1) the CELL's own ability to settle at a given rail, and
  (2) what rail the bank actually gets, which depends on the bank's load against
      a source tank this study holds FIXED at the committed 35.979 fF.

A stripped bank has twice as many output nodes as a static one, so at a fixed
tank it is delivered a LOWER rail -- measured at 48-159 mV lower depending on
the family.  That depresses the pull-up's overdrive (rail - |Vtp|) and is a
property of the harness's fixed tank, not of the topology: a designer would
size the tank to the bank.

This deck removes (2) entirely.  The rail is an IDEAL voltage source stepped to
a chosen level and held there; there is no tank, no inductor, no transfer switch
and nothing to droop.  Inputs are RAIL-REFERENCED (vin = rail), the realistic
chain condition, not the committed 1.5 V drive.  What is left is (1) alone: at
this rail, does this cell settle, and how fast.

This is the same instrument qal/skip4's skeptic used to show that every beat
<= 160 ps was already impossible at a chain-delivered rail for reasons having
nothing to do with the power schedule.
"""
import json, os, re, sys
import common as C
import cells as K
import st

HERE = C.HERE
RAILS = [0.5217, 0.5594, 0.6077, 0.70, 0.80, 1.00]
TEND = 3000.0


def deck(mode, fam, rail, wxc=C.WXC):
    d = dict(fam=fam, mode=mode, wxc=wxc, cl=C.CLOAD, vin=rail)
    L = C.head() + ["VRL rl 0 PWL(0 0 2p 0 4p %g %gp %g)" % (rail, TEND * 2, rail)]
    bl, checked, meta = st.bank(dict(d, dv=rail))
    # st.bank names the rail node 'bkb'; rename EVERY occurrence (including the
    # pMOS BULK terminal, which is the rail too) to the ideal source node.  A
    # first attempt used str.replace(" bkb ", ...) and silently left the trailing
    # bulk terminal on a now-floating 'bkb' node; word-boundary regex instead,
    # and the caller asserts no 'bkb' survives.
    bl = [re.sub(r"\bbkb\b", "rl", ln) for ln in bl]
    assert not any("bkb" in ln for ln in bl), "rail rename incomplete"
    L += bl
    L.append(".ic " + " ".join("V(%s)=0" % n for n, _, _ in checked))
    pr = ["V(%s)" % n for n, _, _ in checked]
    for k in range(0, len(pr), 8):
        L.append((".print tran " if k == 0 else "+ ") + " ".join(pr[k:k + 8]))
    L += [".tran 1p %gp 0 2p" % TEND, ".end"]
    return L, checked


def row(mode, fam, rail, wxc=C.WXC):
    tag = "%s_%s_r%s%s" % (mode, fam, ("%.4f" % rail).replace(".", "p"),
                           ("_w%g" % (wxc * 100)) if mode == "strip" else "")
    L, checked = deck(mode, fam, rail, wxc)
    p, msg, wall = C.run("cf_%s.cir" % tag, L, timeout=600)
    print(" ", tag, msg, flush=True)
    if not p:
        return {"tag": tag, "error": msg}
    w = C.W(p + ".prn")
    per = {}
    for n, hi, ci in checked:
        ve = w.at("V(%s)" % n, TEND - 5.0)
        s = 100.0 * ((ve / rail) if hi else (1.0 - ve / rail))
        tgt = 0.9 * rail if hi else 0.1 * rail
        tc = w.cross("V(%s)" % n, tgt, tmin=0.0, rising=hi)
        per[n] = dict(cell=ci, expect_hi=hi, V_end=ve, s_end_pct=s,
                      t90_ps=tc)
    t90 = [v["t90_ps"] for v in per.values()]
    return dict(tag=tag, mode=mode, fam=fam, rail_V=rail, wxc_um=wxc,
                n_dev=(K.strip_devcount(st.STRIP_FAM.get(fam, fam))
                       if mode == "strip"
                       else K.static_devcount(fam))["n_dev"],
                overdrive_V=rail - 0.4402734454819182,
                all_reached_90=all(t is not None for t in t90),
                t90_worst_ps=(max(t for t in t90) if all(t is not None
                                                         for t in t90) else None),
                s_end_min_pct=min(v["s_end_pct"] for v in per.values()),
                per_node=per, wall_s=wall)


def main():
    fams = sys.argv[1:] or ["o21ai_hb"]   # l=0.13u hand-built: the ANCHOR cell,
    # the stronger device (PDK o21ai is l=0.15u), i.e. generous to static CMOS,
    # and its geometries are already in the PyMS cache.
    out = {"_method": __doc__.strip(), "rows": []}
    fp = os.path.join(HERE, "CELLFLOOR.json")
    if os.path.exists(fp):
        out = json.load(open(fp))
    for fam in fams:
        for rail in RAILS:
            for mode, wxc in (("static", C.WXC), ("strip", 0.56),
                              ("strip", 1.12)):
                if mode == "static" and wxc != C.WXC:
                    continue
                r = row(mode, fam, rail, wxc)
                out["rows"].append(r)
                if "error" not in r:
                    print("   %-8s %-6s rail %.4f ovdrv %.4f  t90 %-9s  smin %.2f%%"
                          % (fam, mode + ("%g" % (wxc * 100) if mode == "strip"
                                          else ""), rail, r["overdrive_V"],
                             ("%.1f" % r["t90_worst_ps"]) if r["t90_worst_ps"]
                             else "NEVER", r["s_end_min_pct"]), flush=True)
                json.dump(out, open(fp, "w"), indent=1)


if __name__ == "__main__":
    main()
