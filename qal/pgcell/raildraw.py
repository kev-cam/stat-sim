#!/usr/bin/env python3
"""(d)(a) THE BANK-SUPPLY DRAW, METERED SEPARATELY FROM THE INPUT-CHARGE DRAW.

The pre-registered question: does a transmission-gate cell draw anything from the
bank rail at all?  If it does not, its energy model differs from every cell this
campaign has measured and the bank population arithmetic changes.

Three populations are metered on the SAME deck, at the committed delivered rail:

  WHOLE    the complete TG cell -- its control inverter(s) ARE rail-powered static
           CMOS, so this is what a bank would actually carry.
  PROPER   the transmission gates ALONE.  Their gate control comes from EXTERNAL
           sources whose waveform is the rail's own ramp (what the control inverter
           would have produced), so the ONLY remaining connection to the rail is the
           pass pMOS n-well (bulk).  This isolates the question.
  STATIC   the PDK's own sg13g2_xnor2_1 / sg13g2_mux2_1 / sg13g2_inv_1 -- the
           controls, and the campaign's unit of bank membership.

Metering: 1 F integrators, t0-referenced (they carry a t=0 pedestal).
  q_rail = INTEG(-I(VS))          fC delivered by the rail source
  e_rail = INTEG(-V(rail)*I(VS))  fJ delivered by the rail source
  q_in   = INTEG(-sum I(Vin))     fC delivered by the INPUT sources
  e_in   = INTEG(-sum V*I(Vin))   fJ delivered by the INPUT sources
DECLARED: sg13lv_compat.sp ZEROES ad/as/pd/ps, so junction capacitance is absent.
The pass pMOS n-well junction is EXACTLY the term that is missing, and it is the
term PROPER would be most inflated by.  Every PROPER number is a LOWER BOUND.
"""
import json, os, sys, time
import pg
from cells import XNOR_VEC, MUX_VEC, xnor_y, mux_x, CKPT, LONG

W = pg.TGW["tgM"]


def ramp(tag, node, v):
    return ["V%s %s 0 PWL(0 0 %gp 0 %gp %.7f)"
            % (tag, node, pg.TSTEP, pg.TSTEP + pg.EDGE, v)]


def meter(tag, rail, vs, ins):
    """ins = [(srcname, node)] ; returns integrator lines + tag names"""
    L = pg.integ("q" + tag, "-I(%s)" % vs)
    L += pg.integ("e" + tag, "-V(%s)*I(%s)" % (rail, vs))
    if ins:
        L += pg.integ("qi" + tag, "-(" + "+".join("I(%s)" % s for s, _ in ins) + ")")
        L += pg.integ("ei" + tag,
                      "-(" + "+".join("V(%s)*I(%s)" % (n, s) for s, n in ins) + ")")
    return L


def c_whole_xnor(tag, v, a, b):
    r, vs = "r_" + tag, "VS" + tag
    L = ramp("S" + tag, r, v)
    ins = []
    for nm, bit in (("a", a), ("b", b)):
        L += ["VD%s%s %s_%s 0 %.7f" % (nm, tag, nm, tag, v if bit else 0.0)]
        ins.append(("VD%s%s" % (nm, tag), "%s_%s" % (nm, tag)))
    L += pg.tg_xnor2(tag, "y_" + tag, "a_" + tag, "b_" + tag, r, "0", W)
    return L + meter(tag, r, vs, ins), "y_" + tag


def c_whole_mux(tag, v, a0, a1, s):
    r, vs = "r_" + tag, "VS" + tag
    L = ramp("S" + tag, r, v)
    ins = []
    for nm, bit in (("a0", a0), ("a1", a1), ("s", s)):
        L += ["VD%s%s %s_%s 0 %.7f" % (nm, tag, nm, tag, v if bit else 0.0)]
        ins.append(("VD%s%s" % (nm, tag), "%s_%s" % (nm, tag)))
    L += pg.tg_mux2(tag, "x_" + tag, "a0_" + tag, "a1_" + tag, "s_" + tag, r, "0", W)
    return L + meter(tag, r, vs, ins), "x_" + tag


def c_proper(tag, v, hi):
    """ONE transmission gate, data in = hi/lo, gates driven EXTERNALLY by the rail
    ramp and its complement.  Only the pass pMOS bulk touches the rail."""
    r, vs = "r_" + tag, "VS" + tag
    wn, wp = W
    L = ramp("S" + tag, r, v)
    L += ramp("G" + tag, "gn_" + tag, v)              # nMOS gate: follows the rail ON
    L += ["VGP%s gp_%s 0 0" % (tag, tag)]             # pMOS gate: held at 0 = ON
    L += ["VD%s d_%s 0 %.7f" % (tag, tag, v if hi else 0.0)]
    L += pg._tg(tag, "d_" + tag, "y_" + tag, "gn_" + tag, "gp_" + tag, r, "0", wn, wp)
    L += ["CL%s y_%s 0 %gf" % (tag, tag, pg.CL)]
    return L + meter(tag, r, vs, [("VD" + tag, "d_" + tag)]), "y_" + tag


def c_pdk(tag, v, cell, ports, bits):
    r, vs = "r_" + tag, "VS" + tag
    L = ramp("S" + tag, r, v)
    out = "z_" + tag
    conn, ins = [out], []
    for p, bit in zip(ports[1:-2], bits):
        nd = "%s_%s" % (p.lower(), tag)
        L += ["VD%s%s %s 0 %.7f" % (p, tag, nd, v if bit else 0.0)]
        ins.append(("VD%s%s" % (p, tag), nd)); conn.append(nd)
    conn += [r, "0"]
    L += ["XC%s %s %s" % (tag, " ".join(conn), cell),
          "CL%s %s 0 %gf" % (tag, out, pg.CL)]
    return L + meter(tag, r, vs, ins), out


def build(v=pg.VREF):
    ports = pg.emit_pdk_subckts()
    L = pg.head(with_sub=True)
    pr, meta = [], []

    def add(tag, lines, node, **kw):
        L.extend(lines); pr.append("V(%s)" % node)
        pr.extend(["V(x%s%s)" % (p, tag) for p in ("q", "e", "qi", "ei")
                   if p != "qi" or kw.get("has_in", True)])
        meta.append(dict(tag=tag, node=node, vdd=v, **kw))

    for a, b in XNOR_VEC:
        t = "wx%d%d" % (a, b)
        ln, nd = c_whole_xnor(t, v, a, b)
        add(t, ln, nd, pop="WHOLE", cell="tg_xnor2", vec=dict(A=a, B=b),
            want=xnor_y(a, b), path=("transparent" if b else "restored"))
    for a0, a1, s in MUX_VEC:
        t = "wm%d%d%d" % (a0, a1, s)
        ln, nd = c_whole_mux(t, v, a0, a1, s)
        add(t, ln, nd, pop="WHOLE", cell="tg_mux2", vec=dict(A0=a0, A1=a1, S=s),
            want=mux_x(a0, a1, s), path="transparent")
    for hi in (0, 1):
        t = "pp%d" % hi
        ln, nd = c_proper(t, v, hi)
        add(t, ln, nd, pop="PROPER", cell="tg_only", vec=dict(D=hi), want=hi,
            path="transparent")
    for a, b in XNOR_VEC:
        t = "sx%d%d" % (a, b)
        ln, nd = c_pdk(t, v, "sg13g2_xnor2_1", ports["sg13g2_xnor2_1"], (a, b))
        add(t, ln, nd, pop="STATIC", cell="sg13g2_xnor2_1", vec=dict(A=a, B=b),
            want=xnor_y(a, b), path="static")
    for a0, a1, s in MUX_VEC:
        t = "sm%d%d%d" % (a0, a1, s)
        ln, nd = c_pdk(t, v, "sg13g2_mux2_1", ports["sg13g2_mux2_1"], (a0, a1, s))
        add(t, ln, nd, pop="STATIC", cell="sg13g2_mux2_1", vec=dict(A0=a0, A1=a1, S=s),
            want=mux_x(a0, a1, s), path="static")
    for a in (0, 1):
        t = "si%d" % a
        ln, nd = c_pdk(t, v, "sg13g2_inv_1", ports["sg13g2_inv_1"], (a,))
        add(t, ln, nd, pop="STATIC", cell="sg13g2_inv_1", vec=dict(A=a),
            want=1 - a, path="static")

    cl, cn = pg.companion()
    L += cl; pr.append("V(%s)" % cn)
    L.append(".tran 0.02p %gp 0 0.05p" % (pg.TSTEP + LONG + 100.0))
    for k in range(0, len(pr), 8):
        L.append((".print tran " if k == 0 else "+ ") + " ".join(pr[k:k + 8]))
    L.append(".end")
    return L, meta


def extract(p, meta):
    hdr, rows = pg.read_prn(p + ".prn")
    out = {}
    for d in meta:
        t = d["tag"]
        ts, y = pg.col(hdr, rows, "V(%s)" % d["node"])
        r = dict(d); r.pop("node")
        v = d["vdd"]
        r["v_ckpt"] = pg.at_t(ts, y, pg.TSTEP + CKPT)
        r["v_long"] = pg.at_t(ts, y, pg.TSTEP + LONG)
        r["correct_ckpt"] = (bool(r["v_ckpt"] > .5 * v) if d["want"]
                             else bool(r["v_ckpt"] < .5 * v))
        for nm, pre, sc in (("q_rail_fC", "q", 1e15), ("e_rail_fJ", "e", 1e15),
                            ("q_in_fC", "qi", 1e15), ("e_in_fJ", "ei", 1e15)):
            key = "V(X%s%s)" % (pre.upper(), t.upper())
            if key not in hdr:
                r[nm] = None; continue
            tt, yy = pg.col(hdr, rows, key)
            p0 = pg.ped(tt, yy)
            r[nm] = (pg.at_t(tt, yy, pg.TSTEP + CKPT) - p0) * sc
            r[nm.replace("_f", "_long_f")] = (pg.at_t(tt, yy, pg.TSTEP + LONG) - p0) * sc
        out[t] = r
    return out


if __name__ == "__main__":
    L, meta = build()
    t0 = time.monotonic()
    p = pg.run("D_raildraw.cir", L, timeout=1500)
    if p is None:
        sys.exit(1)
    r = extract(p, meta)
    r["_wall_s"] = round(time.monotonic() - t0, 1)
    json.dump(r, open(os.path.join(pg.HERE, "RAILDRAW.json"), "w"), indent=1)
    for pop in ("WHOLE", "PROPER", "STATIC"):
        print("== %s" % pop)
        for k, d in r.items():
            if isinstance(d, dict) and d.get("pop") == pop:
                print("  %-8s %-16s q_rail %8.4f fC  e_rail %8.4f fJ  q_in %8.4f fC  ok %s"
                      % (k, d["cell"], d["q_rail_fC"], d["e_rail_fJ"],
                         d["q_in_fC"] if d["q_in_fC"] is not None else float("nan"),
                         d["correct_ckpt"]))
