#!/usr/bin/env python3
"""Stage driver for qal/vtreq.  Every stage writes its own per-point JSON so no
two processes ever read-modify-write one shared file (the qal/dvopt A3 race).

stages:
  g0                 instrument check at DELVTO = 0, both committed anchors
  dc                 G1 + Q2-mechanism + Q3-leakage, full 16-point grid
  cmos               the same-DELVTO CMOS comparator, full grid
  q1 <tag>           one QAL level point at the real 6.91 fF load
  o21 <tag>          one o21ai bank point
  merge              collect every rowd/*.json into rows.json
"""
import json, os, sys, time
from concurrent.futures import ThreadPoolExecutor

import vt

HERE = vt.HERE
ROWD = os.path.join(HERE, "rowd")
os.makedirs(ROWD, exist_ok=True)


def save(name, obj):
    json.dump(obj, open(os.path.join(ROWD, name + ".json"), "w"), indent=1)


# --------------------------------------------------------------------- G0
def g0():
    """Both committed anchors, at DVTN = DVTP = 0, under MY cache and MY shim."""
    out = {}
    r = vt.hop_point("g0a_robust", 15.0, 30.0, 1.2, 2.0, 0.0, 0.0)
    out["g0a_robust"] = r
    print("g0a", {k: r.get(k) for k in ("t_hop_ps", "VBEND", "VBPK", "VAEND",
                                        "IPK_uA", "IZ_uA", "s_end_min", "error")},
          flush=True)
    r2 = vt.hop_point("g0b_load691_L4", 4.0, 30.0, 1.65, 6.91, 0.0, 0.0)
    out["g0b_load691_L4"] = r2
    print("g0b", {k: r2.get(k) for k in ("t_hop_ps", "t_valid90_ps", "t_settle90_ps",
                                         "VBEND", "VBPK", "VA_open", "s_end_min",
                                         "error")}, flush=True)
    save("g0", out)
    return out


# --------------------------------------------------------------------- DC
def dc_one(pt):
    tag, dvtn, dvtp = pt
    p, msg = vt.run("dc_%s.cir" % tag, vt.dc_deck(dvtn, dvtp), timeout=900)
    if p is None:
        return tag, dict(error=msg)
    r = vt.dc_extract(p + ".prn")
    r.update(tag=tag, dvtn=dvtn, dvtp=dvtp)
    save("dc_" + tag, r)
    return tag, r


def dc_all(maxpar=4):
    pts = vt.grid()
    res = {}
    with ThreadPoolExecutor(max_workers=maxpar) as ex:
        for tag, r in ex.map(dc_one, pts):
            res[tag] = r
            print("%-8s Vtn %s |Vtp| %s Vstrand %s trip1.2 %s tripR4 %s"
                  % (tag,
                     _f(r.get("Vtn")), _f(r.get("Vtp_abs")), _f(r.get("V_strand")),
                     _f(r.get("trip_1p20")), _f(r.get("trip_rail_L4"))), flush=True)
    return res


def _f(x):
    return "None" if x is None else "%.6f" % x


# --------------------------------------------------------------------- CMOS
def cmos_one(pt):
    tag, dvtn, dvtp = pt
    p, msg = vt.run("cm_%s.cir" % tag, vt.cmos_deck(dvtn, dvtp), timeout=900)
    if p is None:
        return tag, dict(error=msg)
    r = vt.cmos_extract(p)
    r.update(tag=tag, dvtn=dvtn, dvtp=dvtp)
    save("cm_" + tag, r)
    return tag, r


def cmos_all(maxpar=4):
    pts = vt.grid()
    res = {}
    with ThreadPoolExecutor(max_workers=maxpar) as ex:
        for tag, r in ex.map(cmos_one, pts):
            res[tag] = r
            a = r.get("vdd1p2_cl6p91", {})
            b = r.get("vdd1p2_cl2", {})
            print("%-8s CL6.91 rise %s fall %s worst %s | CL2 rise %s"
                  % (tag, _f(a.get("t90_rise_ps")), _f(a.get("t90_fall_ps")),
                     _f(a.get("t90_worst_ps")), _f(b.get("t90_rise_ps"))), flush=True)
    return res


# --------------------------------------------------------------------- Q1
Q1_POINTS = dict(L_nH=4.0, W_um=30.0, dv=1.65, cl=6.91)
Q1X_POINTS = dict(L_nH=15.0, W_um=30.0, dv=1.2, cl=6.91)


def q1_one(pt, cfg=None, pref="q1"):
    cfg = cfg or Q1_POINTS
    tag, dvtn, dvtp = pt
    r = vt.hop_point("%s_%s" % (pref, tag), cfg["L_nH"], cfg["W_um"], cfg["dv"],
                     cfg["cl"], dvtn, dvtp, kind=cfg.get("kind", "inv"),
                     tail=cfg.get("tail", 500.0))
    r.update(dvtn=dvtn, dvtp=dvtp, point=cfg)
    save("%s_%s" % (pref, tag), r)
    print("%-10s t_hop %s t_valid90 %s VBEND %s smin %s hold300 %s %s"
          % (pref + "_" + tag, _f(r.get("t_hop_ps")), _f(r.get("t_valid90_ps")),
             _f(r.get("VBEND")), _f(r.get("s_end_min")),
             _f((r.get("held_rail") or {}).get("droop_300ps_mV")),
             r.get("error", "")), flush=True)
    return tag, r


def hold_one(pt):
    tag, dvtn, dvtp = pt
    p, msg = vt.run("hd_%s.cir" % tag, vt.hold_deck(dvtn, dvtp), timeout=900)
    if p is None:
        return tag, dict(error=msg)
    r = vt.hold_extract(p)
    r.update(tag=tag, dvtn=dvtn, dvtp=dvtp)
    save("hd_" + tag, r)
    return tag, r


def hold_all(maxpar=4):
    res = {}
    with ThreadPoolExecutor(max_workers=maxpar) as ex:
        for tag, r in ex.map(hold_one, vt.grid()):
            res[tag] = r
            print("%-8s I_hold %s A  I_swp %s  droop(DC,120ps) %s mV  float120 %s mV %s"
                  % (tag, r.get("I_hold_total_A"), r.get("I_swpmos_A"),
                     _f(r.get("droop_DC_120ps_mV")),
                     _f(r.get("float_droop_120ps_mV")), r.get("error", "")),
                  flush=True)
    return res


if __name__ == "__main__":
    c = sys.argv[1]
    if c == "g0":
        g0()
    elif c == "dc":
        dc_all(int(sys.argv[2]) if len(sys.argv) > 2 else 4)
    elif c == "cmos":
        cmos_all(int(sys.argv[2]) if len(sys.argv) > 2 else 4)
    elif c == "hold":
        hold_all(int(sys.argv[2]) if len(sys.argv) > 2 else 4)
    elif c == "q1":
        pts = {t[0]: t for t in vt.grid()}
        q1_one(pts[sys.argv[2]])
    elif c == "q1x":
        pts = {t[0]: t for t in vt.grid()}
        q1_one(pts[sys.argv[2]], Q1X_POINTS, "q1x")
    elif c == "q1L":
        # EXPLORATORY (not pre-stated): re-optimise L at a shifted threshold.
        # Lower Vt collapses the SETTLE term, so the L that balanced hop against
        # settle at DELVTO = 0 need not be the optimum any more.  It can only help
        # QAL, so running it strengthens a negative verdict and is a real finding
        # if it closes.
        pts = {t[0]: t for t in vt.grid()}
        q1_one(pts[sys.argv[2]],
               dict(L_nH=float(sys.argv[3]), W_um=30.0, dv=1.65, cl=6.91),
               "q1L%g" % float(sys.argv[3]))
    elif c == "o21":
        pts = {t[0]: t for t in vt.grid()}
        q1_one(pts[sys.argv[2]],
               dict(L_nH=15.0, W_um=30.0, dv=1.65, cl=2.0, kind="o21ai",
                    tail=900.0), "o21")
    elif c == "merge":
        rows = {}
        for fn in sorted(os.listdir(ROWD)):
            if fn.endswith(".json"):
                rows[fn[:-5]] = json.load(open(os.path.join(ROWD, fn)))
        json.dump(rows, open(os.path.join(HERE, "rows.json"), "w"), indent=1)
        print("merged", len(rows))
