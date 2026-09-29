#!/usr/bin/env python3
"""(a) RE-MEASURE the bank-supply draw and the level loss of the pass-gate cells.

The claim under test: "a transmission gate draws EXACTLY NOTHING from the bank
rail -- 0.0000 fC / 0.0000 fJ -- provided its n-well is not on the bank rail."

FIRST, two controls the original run did not carry, because a meter that reads
zero is only evidence if the meter is shown to read correctly and to read
something when there IS something:
  CALC   a bare 5 fF capacitor across a rail source.  q_rail MUST come back
         5 fF * VREF = 3.56908 fC exactly.  This pins the meter's SIGN and SCALE
         against an analytic answer.
  CALO   a rail source with NOTHING on its node -- the exact topology of the
         run's PROPER_VHI case.  q_rail is 0 by Kirchhoff on a one-element node,
         for any device model, any PDK, any physics.  If CALO and PROPER_VHI read
         the same, the "0.0000 fC" is a property of the DECK, not of the device.

SECOND, the charge the "draws nothing" framing leaves out: a transmission gate
has four MOS gates, and in a real cell those gates are driven by rail-powered
logic.  Charging them IS bank-rail charge.  Metered here explicitly:
  GD_none  a rail-powered inverter with no load at all
  GD_cl2   the same inverter with the campaign 2 fF load
  GD_tg2   the same inverter driving ONE TG's gate pair (as the cell's own
           control inverter does)
  GD_sel2  a second inverter driving the OTHER gate pair (the SELECT line, which
           the run's decks supplied from an IDEAL source -- so that half of a
           TG's gate-drive charge was never charged to any rail at all)
"""
import json, os, sys, time
from itertools import product
import sk

V = sk.VREF
PB_VHI, PB_RAIL = "vhi", None      # None => tie to that case's own rail
SUB = os.path.join(sk.HERE, "pdk_cells.sp")
MUXV = [(a0, a1, s) for a0 in (0, 1) for a1 in (0, 1) for s in (0, 1)]
XNV = [(a, b) for a in (0, 1) for b in (0, 1)]
meta, pr, L = [], [], None


def ramp(tag, node, v=V):
    return ["VS%s %s 0 PWL(0 0 %gp 0 %gp %.7f)" % (tag, node, sk.TSTEP,
                                                   sk.TSTEP + sk.EDGE, v)]


def meter(tag, rail, ins):
    M = sk.integ("q" + tag, "-I(VS%s)" % tag)
    M += sk.integ("e" + tag, "-V(%s)*I(VS%s)" % (rail, tag))
    if ins:
        M += sk.integ("qi" + tag, "-(%s)" % "+".join("I(%s)" % s for s, _ in ins))
    return M


def add(tag, lines, node, **kw):
    L.extend(lines)
    pr.append("V(%s)" % node)
    pr.extend(["V(x%s%s)" % (p, tag) for p in ("q", "e")])
    if kw.pop("has_in", True):
        pr.append("V(xqi%s)" % tag)
        kw["has_in"] = True
    else:
        kw["has_in"] = False
    meta.append(dict(tag=tag, node=node, **kw))


def build():
    global L, pr, meta
    ports = sk.pdk_subckts(["sg13g2_xnor2_1", "sg13g2_mux2_1", "sg13g2_inv_1"], SUB)
    L = sk.head(SUB) + ["VHI vhi 0 %g" % sk.VHI]
    pr, meta = [], []

    # ---------------- CONTROLS
    t = "calc"
    add(t, ramp(t, "r_" + t) + ["CTST r_%s 0 5f" % t] + meter(t, "r_" + t, []),
        "r_" + t, pop="CONTROL", cell="bare 5 fF cap", want=None, has_in=False,
        analytic_q_fC=5.0 * V)
    t = "calo"
    add(t, ramp(t, "r_" + t) + meter(t, "r_" + t, []), "r_" + t, pop="CONTROL",
        cell="rail source on a node with NOTHING on it", want=None, has_in=False,
        analytic_q_fC=0.0)

    # ---------------- GATE-DRIVE ACCOUNTING
    # gdn / gdc pin the reference inverter with no load and with the campaign
    # 2 fF load.  gdm is the one the run never metered: an inverter on its OWN
    # rail driving the SELECT input of a complete fixed-well tg_mux2 (the mux
    # sits on a SECOND rail source so the two draws cannot mix).  The select line
    # feeds 2 of the TG's 4 MOS gates, and in the run's decks it came from an
    # IDEAL source -- i.e. that charge was never charged to any rail at all.
    for t in ("gdn", "gdc", "gdm"):
        r = "r_" + t
        ln = ramp(t, r) + ["VI%s i_%s 0 0" % (t, t)] + sk.inv(t, "o_" + t, "i_" + t, r, "0")
        if t == "gdc":
            ln += ["CLgd o_gdc 0 %gf" % sk.CL]
        if t == "gdm":
            r2 = "r2_" + t
            ln += ["VQ%s %s 0 PWL(0 0 %gp 0 %gp %.7f)"
                   % (t, r2, sk.TSTEP, sk.TSTEP + sk.EDGE, V),
                   "VA0%s a0_%s 0 0" % (t, t),
                   "VA1%s a1_%s 0 %.7f" % (t, t, V)]
            ln += sk.tg_mux2("mx" + t, "x_" + t, "a0_" + t, "a1_" + t, "o_" + t,
                             r2, "0", "vhi")
        add(t, ln + meter(t, r, []), "o_" + t, pop="GATEDRIVE", has_in=False,
            cell={"gdn": "inverter, NO load",
                  "gdc": "inverter + 2 fF",
                  "gdm": "inverter driving the SELECT line of a fixed-well tg_mux2"
                         " (2 of the TG's 4 gates)"}[t],
            want=1)

    # ---------------- WHOLE CELLS, both well ties
    for wname, pb in (("vhi", "vhi"), ("rail", None)):
        for a0, a1, s in MUXV:
            t = "m%s%d%d%d" % (wname[0], a0, a1, s)
            r = "r_" + t
            ln = ramp(t, r)
            ins = []
            for nm, bit in (("a0", a0), ("a1", a1), ("s", s)):
                ln += ["VD%s%s %s_%s 0 %.7f" % (nm, t, nm, t, V if bit else 0.0)]
                ins.append(("VD%s%s" % (nm, t), "%s_%s" % (nm, t)))
            ln += sk.tg_mux2(t, "x_" + t, "a0_" + t, "a1_" + t, "s_" + t, r, "0",
                             pb or r)
            add(t, ln + meter(t, r, ins), "x_" + t, pop="WHOLE_MUX", well=wname,
                cell="tg_mux2", vec=dict(A0=a0, A1=a1, S=s),
                want=(a1 if s else a0), src_hi=(a1 if s else a0))
        for a, b in XNV:
            t = "x%s%d%d" % (wname[0], a, b)
            r = "r_" + t
            ln = ramp(t, r)
            ins = []
            for nm, bit in (("a", a), ("b", b)):
                ln += ["VD%s%s %s_%s 0 %.7f" % (nm, t, nm, t, V if bit else 0.0)]
                ins.append(("VD%s%s" % (nm, t), "%s_%s" % (nm, t)))
            ln += sk.tg_xnor2(t, "y_" + t, "a_" + t, "b_" + t, r, "0", pb or r)
            add(t, ln + meter(t, r, ins), "y_" + t, pop="WHOLE_XNOR", well=wname,
                cell="tg_xnor2", vec=dict(A=a, B=b), want=(1 if a == b else 0),
                path=("transparent" if b else "restored"))

    # ---------------- TG PROPER, both well ties, gates from IDEAL sources
    # (the run's own topology, reproduced so the two readings can be compared)
    for wname, pb in (("vhi", "vhi"), ("rail", None)):
        for hi in (0, 1):
            t = "p%s%d" % (wname[0], hi)
            r = "r_" + t
            ln = ramp(t, r) + ramp("G" + t, "gn_" + t)
            ln[-1] = ln[-1].replace("VSG" + t, "VG" + t)
            ln += ["VP%s gp_%s 0 0" % (t, t),
                   "VD%s d_%s 0 %.7f" % (t, t, V if hi else 0.0)]
            ln += sk.tg(t, "d_" + t, "y_" + t, "gn_" + t, "gp_" + t, "0", pb or r)
            ln += ["CL%s y_%s 0 %gf" % (t, t, sk.CL)]
            add(t, ln + meter(t, r, [("VD" + t, "d_" + t)]), "y_" + t,
                pop="PROPER", well=wname, cell="tg alone", vec=dict(D=hi), want=hi)

    # ---------------- STATIC CONTROLS
    for cell, vecs, key in (("sg13g2_mux2_1", MUXV, "sm"),
                            ("sg13g2_xnor2_1", XNV, "sx"),
                            ("sg13g2_inv_1", [(0,), (1,)], "si")):
        for vec in vecs:
            t = key + "".join(str(x) for x in vec)
            r = "r_" + t
            ln = ramp(t, r)
            conn, ins = ["z_" + t], []
            for p, bit in zip(ports[cell][1:-2], vec):
                nd = "%s_%s" % (p.lower(), t)
                ln += ["VD%s%s %s 0 %.7f" % (p, t, nd, V if bit else 0.0)]
                ins.append(("VD%s%s" % (p, t), nd))
                conn.append(nd)
            ln += ["XC%s %s %s %s %s" % (t, " ".join(conn), r, "0", cell),
                   "CL%s z_%s 0 %gf" % (t, t, sk.CL)]
            want = (vec[1] if vec[2] else vec[0]) if key == "sm" else (
                (1 if vec[0] == vec[1] else 0) if key == "sx" else 1 - vec[0])
            add(t, ln + meter(t, r, ins), "z_" + t, pop="STATIC", cell=cell,
                vec=vec, want=want)

    cl, cn = sk.companion()
    L.extend(cl)
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
        t = d["tag"]
        ts, y = sk.col(hdr, rows, "V(%s)" % d["node"])
        r = dict(d)
        r["v_ckpt"] = sk.at_t(ts, y, sk.TSTEP + sk.CKPT)
        r["v_long"] = sk.at_t(ts, y, sk.TSTEP + sk.LONG)
        if d.get("want") is not None:
            r["correct_ckpt"] = (bool(r["v_ckpt"] > .5 * V) if d["want"]
                                 else bool(r["v_ckpt"] < .5 * V))
        for nm, pre, sc in (("q_rail_fC", "q", 1e15), ("e_rail_fJ", "e", 1e15),
                            ("q_in_fC", "qi", 1e15)):
            key = "V(X%s%s)" % (pre.upper(), t.upper())
            if key not in hdr:
                r[nm] = None
                continue
            tt, yy = sk.col(hdr, rows, key)
            p0 = sk.ped(tt, yy)
            r[nm] = (sk.at_t(tt, yy, sk.TSTEP + sk.CKPT) - p0) * sc
            r[nm.replace("_f", "_long_f")] = (sk.at_t(tt, yy, sk.TSTEP + sk.LONG) - p0) * sc
        out[t] = r
    # per-deck instrument check
    ts, y = sk.col(hdr, rows, "V(O_ZC)")
    out["_instr_inv1p2_t90_ps"] = sk.t_cross(ts, y, 0.9 * 1.2, sk.TSTEP)
    return out


if __name__ == "__main__":
    L, meta = build()
    t0 = time.monotonic()
    p = sk.run("R_rail.cir", L, timeout=1500)
    if p is None:
        sys.exit(1)
    r = extract(p, meta)
    r["_wall_s"] = round(time.monotonic() - t0, 1)
    json.dump(r, open(os.path.join(sk.HERE, "RAIL.json"), "w"), indent=1)
    for pop in ("CONTROL", "GATEDRIVE", "PROPER", "WHOLE_MUX", "WHOLE_XNOR", "STATIC"):
        print("== %s" % pop)
        for k, d in r.items():
            if isinstance(d, dict) and d.get("pop") == pop:
                print("  %-7s %-52s well=%-4s q_rail %9.4f fC  e_rail %8.4f fJ  ok %s"
                      % (k, d["cell"][:52], d.get("well", "-"), d["q_rail_fC"],
                         d["e_rail_fJ"], d.get("correct_ckpt")))
    print("INSTRUMENT 1.2V inverter t90 = %.4f ps (committed 57.143)"
          % r["_instr_inv1p2_t90_ps"])
