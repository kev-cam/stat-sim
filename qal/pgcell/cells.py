#!/usr/bin/env python3
"""(c)+(e) BUILD AND CHARACTERISE the TG cells against the static PDK controls.

Stimulus = the campaign "settle not switch" convention VERBATIM: inputs held at
their logic level from t=0, SUPPLY stepped 0 -> V at TSTEP with a 2 ps edge.

Four decks:
  W  three TG pass-device widths x 12 vectors, at the committed delivered rail
  R  the default width x 12 vectors, at the other three rails
  S  the PDK static controls (sg13g2_xnor2_1, sg13g2_mux2_1) x 12 vectors x 4 rails
  V  the TG cells driven by a REAL rail-powered inverter instead of an ideal
     source, at the reference rail -- because an ideal source is a BOOKING and the
     level a pass gate can reach depends on what is holding its input up.

Checkpoints: t = TSTEP+495 ps (the committed settle-checkpoint convention) and
t = TSTEP+1000 ps (long tail).  Both reported on every row.
"""
import json, os, sys, time
from itertools import product
import pg

CKPT, LONG = 495.0, 1000.0
XNOR_VEC = [(a, b) for a in (0, 1) for b in (0, 1)]
MUX_VEC = [(a0, a1, s) for a0 in (0, 1) for a1 in (0, 1) for s in (0, 1)]


def xnor_y(a, b):  return 1 if a == b else 0
def mux_x(a0, a1, s): return a1 if s else a0


def src(tag, node, v):
    return ["V%s %s 0 %.7f" % (tag, node, v)]


def case_tg_xnor(tag, v, w, a, b, driven=False, well="rail"):
    """driven=False: A and B are ideal DC sources.  driven=True: A and B come from
    rail-powered inverters (their own inputs ideal), so the TG sees a REAL driver."""
    L = ["VS%s r_%s 0 PWL(0 0 %gp 0 %gp %.7f)"
         % (tag, tag, pg.TSTEP, pg.TSTEP + pg.EDGE, v)]
    r = "r_" + tag
    if driven:
        # invert twice so the polarity is right and the TG source is an inverter out
        L += src("DA%s" % tag, "ai_" + tag, 0.0 if a else v)
        L += src("DB%s" % tag, "bi_" + tag, 0.0 if b else v)
        L += pg._inv("DA" + tag, "a_" + tag, "ai_" + tag, r, "0")
        L += pg._inv("DB" + tag, "b_" + tag, "bi_" + tag, r, "0")
        L += ["CDA%s a_%s 0 %gf" % (tag, tag, pg.CL),
              "CDB%s b_%s 0 %gf" % (tag, tag, pg.CL)]
    else:
        L += src("DA%s" % tag, "a_" + tag, v if a else 0.0)
        L += src("DB%s" % tag, "b_" + tag, v if b else 0.0)
    L += pg.tg_xnor2(tag, "y_" + tag, "a_" + tag, "b_" + tag, r, "0", w,
                     pbulk=("vhi" if well == "vhi" else None))
    return L, "y_" + tag


def case_tg_mux(tag, v, w, a0, a1, s, driven=False, well="rail"):
    L = ["VS%s r_%s 0 PWL(0 0 %gp 0 %gp %.7f)"
         % (tag, tag, pg.TSTEP, pg.TSTEP + pg.EDGE, v)]
    r = "r_" + tag
    if driven:
        for nm, bit in (("a0", a0), ("a1", a1), ("s", s)):
            L += src("D%s%s" % (nm, tag), "%si_%s" % (nm, tag), 0.0 if bit else v)
            L += pg._inv("D%s%s" % (nm, tag), "%s_%s" % (nm, tag),
                         "%si_%s" % (nm, tag), r, "0")
            L += ["CD%s%s %s_%s 0 %gf" % (nm, tag, nm, tag, pg.CL)]
    else:
        for nm, bit in (("a0", a0), ("a1", a1), ("s", s)):
            L += src("D%s%s" % (nm, tag), "%s_%s" % (nm, tag), v if bit else 0.0)
    L += pg.tg_mux2(tag, "x_" + tag, "a0_" + tag, "a1_" + tag, "s_" + tag, r, "0", w,
                    pbulk=("vhi" if well == "vhi" else None))
    return L, "x_" + tag


def case_pdk(tag, v, cell, ports, bits):
    """the PDK's OWN cell as the control.  ports = [OUT, ins..., VDD, VSS]."""
    L = ["VS%s r_%s 0 PWL(0 0 %gp 0 %gp %.7f)"
         % (tag, tag, pg.TSTEP, pg.TSTEP + pg.EDGE, v)]
    out = "z_" + tag
    conn = [out]
    for p, bit in zip(ports[1:-2], bits):
        nd = "%s_%s" % (p.lower(), tag)
        L += src("D%s%s" % (p, tag), nd, v if bit else 0.0)
        conn.append(nd)
    conn += ["r_" + tag, "0"]
    L += ["XC%s %s %s" % (tag, " ".join(conn), cell),
          "CL%s %s 0 %gf" % (tag, out, pg.CL)]
    return L, out


def build(cases, tend):
    L = pg.head(with_sub=True)
    if any(c.get("well") == "vhi" for c in cases):
        # the global +1.5 V supply the architecture already carries for the
        # transfer-switch gate drive (VGH); used here as the pass pMOS n-well tie
        L.append("VHI vhi 0 1.5")
    pr, meta = [], []
    for c in cases:
        L += c["lines"]; pr.append("V(%s)" % c["node"])
        meta.append({k: v for k, v in c.items() if k != "lines"})
    cl, cn = pg.companion()
    L += cl; pr.append("V(%s)" % cn)
    meta.append(dict(tag="zc", kind="cmos_ref", vdd=1.2, node=cn, want=0))
    L.append(".tran 0.02p %gp 0 0.05p" % tend)
    for k in range(0, len(pr), 8):
        L.append((".print tran " if k == 0 else "+ ") + " ".join(pr[k:k + 8]))
    L.append(".end")
    return L, meta


def extract(p, meta):
    hdr, rows = pg.read_prn(p + ".prn")
    out = {}
    for d in meta:
        ts, y = pg.col(hdr, rows, "V(%s)" % d["node"])
        v = d["vdd"]
        vck = pg.at_t(ts, y, pg.TSTEP + CKPT)
        vlg = pg.at_t(ts, y, pg.TSTEP + LONG)
        r = dict(d)
        r.pop("node", None)
        r["v_ckpt"] = vck
        r["v_long"] = vlg
        if d.get("kind") == "cmos_ref":
            t = pg.cross(ts, y, 0.9 * v, rise=True, t_from=pg.TSTEP)
            r["t90_ps"] = (t - pg.TSTEP) if t else None
            out[d["tag"]] = r
            continue
        want = d["want"]
        # value gate: correct side of half the rail at the checkpoint
        r["correct_ckpt"] = bool(vck > 0.5 * v) if want else bool(vck < 0.5 * v)
        r["correct_long"] = bool(vlg > 0.5 * v) if want else bool(vlg < 0.5 * v)
        # level loss, signed so positive = loss, per the pre-registration
        r["loss_ckpt_mV"] = (v - vck) * 1e3 if want else vck * 1e3
        r["loss_long_mV"] = (v - vlg) * 1e3 if want else vlg * 1e3
        if want:
            for nm, fr in (("t50", .5), ("t80", .8), ("t90", .9), ("t95", .95)):
                t = pg.cross(ts, y, fr * v, rise=True, t_from=pg.TSTEP)
                r[nm + "_ps"] = (t - pg.TSTEP) if t is not None else None
        out[d["tag"]] = r
    return out


def tg_cases(wname, v, well, tagpfx, driven=False):
    w = pg.TGW[wname]; cs = []
    for a, b in XNOR_VEC:
        t = "%s_x%d%d" % (tagpfx, a, b)
        ln, nd = case_tg_xnor(t, v, w, a, b, driven=driven, well=well)
        cs.append(dict(tag=t, lines=ln, node=nd,
                       kind="tg_xnor2" + ("_driven" if driven else ""),
                       width=wname, well=well, vdd=v, vec=dict(A=a, B=b),
                       want=xnor_y(a, b), path=("transparent" if b else "restored")))
    for a0, a1, s in MUX_VEC:
        t = "%s_m%d%d%d" % (tagpfx, a0, a1, s)
        ln, nd = case_tg_mux(t, v, w, a0, a1, s, driven=driven, well=well)
        cs.append(dict(tag=t, lines=ln, node=nd,
                       kind="tg_mux2" + ("_driven" if driven else ""),
                       width=wname, well=well, vdd=v, vec=dict(A0=a0, A1=a1, S=s),
                       want=mux_x(a0, a1, s), path="transparent"))
    return cs


def deck_W():
    cs = []
    for wn in ("tgS", "tgM", "tgL"):
        cs += tg_cases(wn, pg.VREF, "rail", "w" + wn[2])
    return cs


def deck_B():
    return tg_cases("tgM", pg.VREF, "vhi", "b")


def deck_R1():
    cs = []
    for v in (0.68, 0.7544, 1.26):
        cs += tg_cases("tgM", v, "rail", "r%d" % round(v * 1000))
    return cs


def deck_R2():
    cs = []
    for v in (0.68, 0.7544, 1.26):
        cs += tg_cases("tgM", v, "vhi", "q%d" % round(v * 1000))
    return cs


def deck_V():
    return (tg_cases("tgM", pg.VREF, "rail", "vr", driven=True)
            + tg_cases("tgM", pg.VREF, "vhi", "vq", driven=True))


def deck_S(ports, rails=None):
    cs = []
    for v in (rails or pg.RAILS):
        vt = "%d" % round(v * 1000)
        for a, b in XNOR_VEC:
            t = "s%s_x%d%d" % (vt, a, b)
            ln, nd = case_pdk(t, v, "sg13g2_xnor2_1", ports["sg13g2_xnor2_1"], (a, b))
            cs.append(dict(tag=t, lines=ln, node=nd, kind="pdk_xnor2", width="pdk",
                           well="static", vdd=v, vec=dict(A=a, B=b),
                           want=xnor_y(a, b), path="static"))
        for a0, a1, s in MUX_VEC:
            t = "s%s_m%d%d%d" % (vt, a0, a1, s)
            ln, nd = case_pdk(t, v, "sg13g2_mux2_1", ports["sg13g2_mux2_1"],
                              (a0, a1, s))
            cs.append(dict(tag=t, lines=ln, node=nd, kind="pdk_mux2", width="pdk",
                           well="static", vdd=v, vec=dict(A0=a0, A1=a1, S=s),
                           want=mux_x(a0, a1, s), path="static"))
        for a in (0, 1):
            t = "s%s_i%d" % (vt, a)
            ln, nd = case_pdk(t, v, "sg13g2_inv_1", ports["sg13g2_inv_1"], (a,))
            cs.append(dict(tag=t, lines=ln, node=nd, kind="pdk_inv", width="pdk",
                           well="static", vdd=v, vec=dict(A=a), want=1 - a,
                           path="static"))
    return cs


if __name__ == "__main__":
    ports = pg.emit_pdk_subckts()
    which = sys.argv[1]
    cs = dict(W=deck_W, B=deck_B, R1=deck_R1, R2=deck_R2,
              S=lambda: deck_S(ports),
              S1=lambda: deck_S(ports, [pg.VREF]), V=deck_V)[which]()
    L, meta = build(cs, pg.TSTEP + LONG + 100.0)
    t0 = time.monotonic()
    p = pg.run("C_%s.cir" % which, L, timeout=1500)
    if p is None:
        sys.exit(1)
    r = extract(p, meta)
    r["_wall_s"] = round(time.monotonic() - t0, 1)
    json.dump(r, open(os.path.join(pg.HERE, "CELLS_%s.json" % which), "w"), indent=1)
    bad = [k for k, v in r.items() if isinstance(v, dict)
           and v.get("kind") != "cmos_ref" and v.get("correct_ckpt") is False]
    print("deck %s: %d cases, %d wrong at checkpoint: %s"
          % (which, len(cs), len(bad), bad[:12]))
    print("cmos_ref t90 = %s (committed 57.143)" % r["zc"].get("t90_ps"))
