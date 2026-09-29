#!/usr/bin/env python3
"""(c)(d)(e) THE SINGLE-HOP BANK HARNESS -- stripped cells vs static controls.

Topology inherited VERBATIM from the committed qal/skept/sk.py single hop:
source tank CA -> L -> RS -> tg15p transfer triple -> bank rail -> 8 cells.
True-ZCS protocol: a PROBE deck whose switch closes at T0 and never opens gives
the first interpolated downward zero of I(LT) after its peak; the HOP deck then
freezes the switch at exactly that instant and lets the bank settle for TAIL.

Everything about the transfer network is inherited and untouched.  The ONLY
thing this study varies is WHAT IS ON THE BANK NODE.

Stages:
  probe <row>      probe only (true ZCS zero)
  row   <row>      probe + hop + extract  -> rowd/<row>.json
"""
import json, math, os, sys, time
import common as C
import cells as K

HERE = C.HERE
ROWD = os.path.join(HERE, "rowd")
MGATE = 8

# expected-LOW / expected-HIGH input vectors per family.
# even cell index -> VEC[0] (output LOW), odd -> VEC[1] (output HIGH).
# The HIGH vectors are the `vec_out_hi` worst-rise vectors of
# qal/sha256/cells/stack_depths.json: the case that drives the output up through
# the deepest pMOS series stack.
VEC = {
    "inv":   ({"A": 1}, {"A": 0}),
    "nand2": ({"A": 1, "B": 1}, {"A": 0, "B": 0}),
    "nor2":  ({"A": 0, "B": 1}, {"A": 0, "B": 0}),
    "xnor2": ({"A": 0, "B": 1}, {"A": 0, "B": 0}),
    "mux2":  ({"A0": 0, "A1": 0, "S": 0}, {"A0": 0, "A1": 1, "S": 1}),
    "o21ai": ({"A1": 0, "A2": 1, "B1": 1}, {"A1": 0, "A2": 0, "B1": 1}),
    # the COMMITTED qal/skept anchor vectors, reproduced exactly:
    #   even index a1=dv a2=0 b1=dv -> output LOW
    #   odd  index a1=0  a2=0 b1=dv -> output HIGH  (= vec_out_hi)
    "o21ai_hb": ({"A1": 1, "A2": 0, "B1": 1}, {"A1": 0, "A2": 0, "B1": 1}),
}
STRIP_FAM = {"o21ai_hb": "o21ai"}     # stripped equivalent of a control family

ROWS = {
    # tag: family, mode ('strip'|'static'), dv, L, tot, wxc, tail, vin
    # ---- (c) ANCHOR: reproduce the committed static o21ai never-settles result
    "anchor_static_o21ai_hb_dv150": dict(fam="o21ai_hb", mode="static", dv=1.5),
    "anchor_static_o21ai_hb_dv120": dict(fam="o21ai_hb", mode="static", dv=1.2),
    # ---- (d) the five+one stripped cells and their static controls, dV = 1.5
    "s_inv_dv150":    dict(fam="inv",   mode="strip"),
    "s_nand2_dv150":  dict(fam="nand2", mode="strip"),
    "s_nor2_dv150":   dict(fam="nor2",  mode="strip"),
    "s_xnor2_dv150":  dict(fam="xnor2", mode="strip"),
    "s_mux2_dv150":   dict(fam="mux2",  mode="strip"),
    "s_o21ai_dv150":  dict(fam="o21ai", mode="strip"),
    "c_inv_dv150":    dict(fam="inv",   mode="static"),
    "c_nand2_dv150":  dict(fam="nand2", mode="static"),
    "c_nor2_dv150":   dict(fam="nor2",  mode="static"),
    "c_xnor2_dv150":  dict(fam="xnor2", mode="static"),
    "c_mux2_dv150":   dict(fam="mux2",  mode="static"),
    "c_o21ai_dv150":  dict(fam="o21ai", mode="static"),
    # ---- the harder secondary point, where static o21ai reaches only 57.47%
    "s_o21ai_dv120":  dict(fam="o21ai", mode="strip", dv=1.2),
    "c_o21ai_dv120":  dict(fam="o21ai", mode="static", dv=1.2),
    # ---- pre-registered cross-coupled pMOS width controls, o21ai row only
    "s_o21ai_dv150_wxc015": dict(fam="o21ai", mode="strip", wxc=0.15),
    "s_o21ai_dv150_wxc112": dict(fam="o21ai", mode="strip", wxc=1.12),
    # ---- RAIL-REFERENCED INPUTS: the realistic chain condition.  The committed
    # bank drives gates at dV (1.5 V) while the rail only reaches ~0.61 V; that
    # is generous to BOTH cells but it is not what a chain sees.
    "s_o21ai_dv150_vinrail": dict(fam="o21ai", mode="strip",  vin=0.6077),
    "c_o21ai_dv150_vinrail": dict(fam="o21ai", mode="static", vin=0.6077),
    # ---- POST-HOC SWEEP EXTENSION, added AFTER seeing s_o21ai_dv150 (declared
    # as post-hoc, not pre-registered).  The pre-registered width set
    # {0.15, 0.56, 1.12} was chosen on the DCVSL convention "the latch must be
    # weaker than the tree".  The measured row shows the tree wins easily (every
    # pull-DOWN node settles to 100.1%) and it is the PULL-UP that is short, so
    # the pre-registered set does not bracket the optimum and is extended upward.
    "s_o21ai_dv150_wxc224": dict(fam="o21ai", mode="strip", wxc=2.24),
    "s_o21ai_dv150_wxc448": dict(fam="o21ai", mode="strip", wxc=4.48),
    # ---- POST-HOC: does restoring the RAIL rescue it?  The stripped bank
    # depresses the delivered rail (dual-rail = twice the output nodes on one
    # tank), and the pull-up's overdrive is rail - |Vtp| = 0.119 V at dV = 1.5.
    # dV = 1.65 is the qal/sha256 census operating swing and restores the rail.
    "s_o21ai_dv165": dict(fam="o21ai", mode="strip",  dv=1.65),
    "c_o21ai_dv165": dict(fam="o21ai", mode="static", dv=1.65),
    "s_o21ai_dv165_wxc224": dict(fam="o21ai", mode="strip", dv=1.65, wxc=2.24),
    # ---- POST-HOC: the fair head-to-head.  wxc = 1.12 um is the sizing at which
    # the stripped o21ai settles, AND it is the same pMOS width the static cell
    # uses, so device sizing is matched.  vin = rail removes the committed 1.5 V
    # input convention, which flatters BOTH cells and the stripped one more (the
    # inputs drive only its nMOS trees).
    "s_o21ai_dv150_vinrail_wxc112": dict(fam="o21ai", mode="strip",
                                         wxc=1.12, vin=0.6077),
}
DEF = dict(dv=1.5, L=15.0, tot=30.0, wxc=C.WXC, tail=C.TAIL, vin=None,
           cl=C.CLOAD, rs=C.RS)


def cfg(tag):
    d = dict(DEF)
    d.update(ROWS[tag])
    d["tag"] = tag
    if d["vin"] is None:
        d["vin"] = d["dv"]
    return d


def widths(tot):
    return dict(wn=tot / 3.0, wp=2.0 * tot / 3.0, park=tot / 15.0)


def t_pred(L, ca=C.CA_FF):
    return math.pi * math.sqrt((L * 1e-9) * (ca / 2.0) * 1e-15) * 1e12


# ------------------------------------------------------------------ the bank
def bank(d):
    """Returns (lines, checked, meta).  `checked` = [(node, expect_hi, cellidx)]."""
    fam, vin, gn = d["fam"], d["vin"], "gn"
    L = ["VMG %s 0 0" % gn]
    checked, srcs, extra_pr = [], [], []
    vlo, vhi = VEC[fam]

    if d["mode"] == "static":
        base = fam
        for i in range(MGATE):
            v = vlo if i % 2 == 0 else vhi
            for p, bit in v.items():
                srcs.append(("VS%s_%d" % (p, i), "s%s_%d" % (p, i),
                             vin if bit else 0.0))
            drv = lambda p, i=i: "s%s_%d" % (p, i)
            ln, outs, inter = K.static_cell(i, base, "bkb", gn, d["cl"], drv)
            L += ln
            exp_hi = bool(K.f_of(fam.replace("_hb", ""), v))
            checked.append((outs[0], exp_hi, i))
            if i in (0, 1):
                extra_pr += ["V(%s)" % n for n in inter.values()]
        dc = K.static_devcount(base)
        dc["n_cells"] = MGATE
        dc["n_checked"] = MGATE
    else:
        sf = STRIP_FAM.get(fam, fam)
        for i in range(MGATE):
            v = vlo if i % 2 == 0 else vhi
            for p, bit in v.items():
                srcs.append(("VS%s_%d" % (p, i), "s%s_%d" % (p, i),
                             vin if bit else 0.0))
                srcs.append(("VSB%s_%d" % (p, i), "sb%s_%d" % (p, i),
                             0.0 if bit else vin))
            def lit(l, i=i):
                return ("sb%s_%d" % (l[:-1], i)) if l.endswith("#") \
                    else ("s%s_%d" % (l, i))
            ln, outs = K.strip_cell(i, sf, "bkb", gn, d["wxc"], C.WTREE,
                                    d["cl"], lit)
            L += ln
            exp = bool(K.f_of(sf, v))
            checked.append((outs[0], exp, i))        # q  = the true output
            checked.append((outs[1], not exp, i))    # n  = its complement
        dc = K.strip_devcount(sf)
        dc["n_cells"] = MGATE
        dc["n_checked"] = 2 * MGATE
    for nm, nd, val in srcs:
        L.append("%s %s 0 %g" % (nm, nd, val))
    return L, checked, dict(devcount=dc, srcs=srcs, extra_pr=extra_pr, gn=gn)


def sw_lines(tot):
    w = widths(tot)
    return ["XSWN sw gt bkb 0 sg13_lv_nmos w=%gu l=0.13u" % w["wn"],
            "XSWP sw gtp bkb vhi sg13_lv_pmos w=%gu l=0.13u" % w["wp"],
            "XPK sw pk 0 0 sg13_lv_nmos w=%gu l=0.13u" % w["park"]]


def probe_deck(d):
    tp = t_pred(d["L"])
    tend = C.T0 + 4.0 * tp
    ps, ms = min(0.05, tp / 3000.0), min(0.10, tp / 1500.0)
    bl, checked, meta = bank(d)
    ic = ".ic V(bka)=%g V(bkb)=0 " % d["dv"] + \
         " ".join("V(%s)=0" % n for n, _, _ in checked)
    return C.head() + [
        ".param LT=%gn RS=%g CA=%gf" % (d["L"], d["rs"], C.CA_FF),
        "CA bka 0 {CA}", "VHI vhi 0 %g" % C.VGH,
        "VGT  gt  0 PWL(0 0 %gp 0 %gp %g %gp %g)"
        % (C.T0 - C.EDGE, C.T0, C.VGH, tend * 2, C.VGH),
        "VGTP gtp 0 PWL(0 %g %gp %g %gp 0 %gp 0)"
        % (C.VGH, C.T0 - C.EDGE, C.VGH, C.T0, tend * 2),
    ] + sw_lines(d["tot"]) + ["VPK pk 0 0", "LT bka mid {LT}", "RT mid sw {RS}"] \
        + bl + [ic, ".print tran I(LT) V(bkb) V(bka) V(sw)",
                ".tran %gp %gp 0 %gp" % (ps, tend, ms), ".end"]


def hop_deck(d, t_half):
    tp = t_pred(d["L"])
    t_open = C.T0 + t_half
    tend = t_open + d["tail"]
    ps, ms = min(0.05, tp / 3000.0), min(0.10, tp / 1500.0)
    bl, checked, meta = bank(d)
    out = C.head() + [
        ".param LT=%gn RS=%g CA=%gf" % (d["L"], d["rs"], C.CA_FF),
        "CA bka 0 {CA}", "VHI vhi 0 %g" % C.VGH,
        "VGT  gt  0 PWL(0 0 %gp 0 %gp %g %gp %g %gp 0)"
        % (C.T0 - C.EDGE, C.T0, C.VGH, t_open, C.VGH, t_open + C.EDGE),
        "VGTP gtp 0 PWL(0 %g %gp %g %gp 0 %gp 0 %gp %g)"
        % (C.VGH, C.T0 - C.EDGE, C.VGH, C.T0, t_open, t_open + C.EDGE, C.VGH),
    ] + sw_lines(d["tot"]) + [
        "VPK pk 0 PWL(0 0 %gp 0 %gp %g)"
        % (t_open + C.EDGE, t_open + 2 * C.EDGE, C.VGH),
        "LT bka mid {LT}", "RT mid sw {RS}"] + bl
    # transfer-path integrators (the committed set) + the cell-block meter
    out += C.integ("qlt", "I(LT)") + C.integ("ea", "V(bka)*I(LT)")
    out += C.integ("eb", "V(bkb)*I(LT)") + C.integ("er", "I(LT)*I(LT)*%g" % d["rs"])
    out += C.integ("esw", "V(sw)*I(LT)")
    # E delivered from the RAIL into the whole cell block (stored + dissipated).
    # I(VMG) is the cells' entire ground-return current: every device source and
    # every CL is referenced to `gn`, so this is exact.
    out += C.integ("ecell", "V(bkb)*I(VMG)")
    out += C.integ("qcell", "I(VMG)")
    # input (gate-drive) energy, metered on the input sources themselves
    ie = "+".join("V(%s)*I(%s)" % (nd, nm) for nm, nd, v in meta["srcs"] if v != 0.0)
    out += C.integ("egin", "-(%s)" % ie if ie else "0")
    out += C.integ("egt", "-V(gt)*I(VGT)-V(gtp)*I(VGTP)-V(pk)*I(VPK)")
    out += [".ic V(bka)=%g V(bkb)=0 " % d["dv"] +
            " ".join("V(%s)=0" % n for n, _, _ in checked)]
    pr = ["V(bka)", "V(bkb)", "V(sw)", "I(LT)"] \
        + ["V(%s)" % n for n, _, _ in checked] + meta["extra_pr"] \
        + ["V(xqlt)", "V(xea)", "V(xeb)", "V(xer)", "V(xesw)", "V(xecell)",
           "V(xqcell)", "V(xegin)", "V(xegt)"]
    for k in range(0, len(pr), 8):
        out.append((".print tran " if k == 0 else "+ ") + " ".join(pr[k:k + 8]))
    out += [".tran %gp %gp 0 %gp" % (ps, tend, ms), ".end"]
    return out, dict(t_open=t_open, tend=tend, checked=checked, meta=meta)


# ---------------------------------------------------------------- extraction
def zero_of(path):
    w = C.W(path)
    i = w.v("I(LT)")
    ip = max(range(len(i)), key=lambda k: i[k])
    for k in range(ip + 1, len(i)):
        if i[k] <= 0.0 < i[k - 1]:
            t0, t1 = w.t[k - 1], w.t[k]
            f = i[k - 1] / (i[k - 1] - i[k])
            return t0 + f * (t1 - t0), i[ip] * 1e6, w.t[ip]
    return None, i[ip] * 1e6, w.t[ip]


def extract(path, d, hm):
    w = C.W(path)
    to, te = hm["t_open"], hm["tend"]
    tE = te - 5.0
    checked = hm["checked"]
    vbe, vbo = w.at("V(bkb)", tE), w.at("V(bkb)", to)
    vae = w.at("V(bka)", tE)

    def dI(tg, t):
        return (w.at("V(x%s)" % tg, t) - w.at("V(x%s)" % tg, 0.5)) * 1e15

    r = dict(tag=d["tag"], fam=d["fam"], mode=d["mode"], dv=d["dv"], L_nH=d["L"],
             tot_um=d["tot"], wxc_um=d["wxc"], vin_V=d["vin"], cl_fF=d["cl"],
             tail_ps=d["tail"], t_hop_ps=to - C.T0, t_open_ps=to, tend_ps=te,
             VBPK=max(w.v("V(bkb)")), VBEND=vbe, VBOPEN=vbo, VAEND=vae,
             IPK_uA=max(w.v("I(LT)")) * 1e6, IZ_uA=w.at("I(LT)", to) * 1e6,
             devcount=hm["meta"]["devcount"])
    # ---- A4 instrument gates
    ea_o, esw_o, er_o = dI("ea", to), dI("esw", to), dI("er", to)
    r["ea_open_fJ"], r["esw_open_fJ"], r["er_open_fJ"] = ea_o, esw_o, er_o
    r["E_swblk_fJ"] = esw_o - dI("eb", to)
    r["ident_at_zero_fJ"] = ea_o - esw_o - er_o
    r["A4_identity_pass"] = bool(abs(r["ident_at_zero_fJ"]) < 0.05)
    r["A4_iz_pass"] = bool(abs(r["IZ_uA"]) < 1.0)
    # ---- energy per operation
    ncell = hm["meta"]["devcount"]["n_cells"]
    r["E_tankout_fJ"] = 0.5 * C.CA_FF * (d["dv"] ** 2 - vae ** 2)
    r["E_cellblock_fJ"] = dI("ecell", tE)
    r["Q_cellblock_fC"] = dI("qcell", tE)
    # SIGN: Xyce's I(Vsrc) is positive when the source DELIVERS here, so the
    # raw integral of -(V*I) comes out negative for a source doing work.
    # Verified against c_inv_dv150, where the input source must deliver energy
    # to charge the pMOS gate against a swinging rail.  Flipped to "energy
    # delivered by the input sources, positive".
    r["E_gatedrive_fJ"] = -dI("egin", tE)
    r["E_switchdrive_fJ"] = dI("egt", tE)
    r["E_cell_per_op_fJ"] = r["E_cellblock_fJ"] / ncell
    r["E_gate_per_op_fJ"] = r["E_gatedrive_fJ"] / ncell
    r["E_tankout_per_cell_fJ"] = r["E_tankout_fJ"] / ncell
    # TOTAL per operation from every metered source.  NOTE the PARTITION between
    # these two terms is NOT comparable across topologies: in a static cell the
    # input source drives the pMOS gate, whose other plate is the SWINGING RAIL,
    # so that displacement energy lands in E_gatedrive; in a stripped cell the
    # inputs drive ONLY nMOS gates referenced to ground and the pMOS gates are
    # driven by the cell's own output nodes, so the same energy lands in
    # E_cellblock.  Only the TOTAL may be compared -- and even that is inflated
    # for the static cell by the committed 1.5 V input convention (see the
    # _vinrail rows).
    r["E_total_per_op_fJ"] = (r["E_cellblock_fJ"] + r["E_gatedrive_fJ"]) / ncell
    stored = sum(0.5 * d["cl"] * w.at("V(%s)" % n, tE) ** 2 for n, _, _ in checked)
    r["E_stored_end_lowerbound_fJ"] = stored
    r["E_cell_dissipated_upperbound_fJ"] = r["E_cellblock_fJ"] - stored

    # ---- per-node settling, PER GATE (never aggregated)
    def s_of(v, hi, ref):
        return 100.0 * ((v / ref) if hi else (1.0 - v / ref))
    per = {}
    for n, hi, ci in checked:
        vo, ve = w.at("V(%s)" % n, to), w.at("V(%s)" % n, tE)
        per[n] = dict(cell=ci, expect_hi=hi, v_open=vo, v_end=ve,
                      s_open_pct=s_of(vo, hi, vbo), s_end_pct=s_of(ve, hi, vbe))
    r["per_node"] = per
    r["s_end_min_pct"] = min(v["s_end_pct"] for v in per.values())
    r["s_open_min_pct"] = min(v["s_open_pct"] for v in per.values())

    # ---- t_valid / t_settle against the INSTANTANEOUS rail
    vb = w.v("V(bkb)")
    cols = [(w.col("V(%s)" % n), hi) for n, hi, _ in checked]

    def t_valid(f):
        gf = None
        for k in range(len(w.t)):
            if w.t[k] < C.T0 or vb[k] < 0.05:
                continue
            ok = all((w.rows[k][c] / vb[k] if hi else 1.0 - w.rows[k][c] / vb[k]) >= f
                     for c, hi in cols)
            if ok and gf is None:
                gf = w.t[k]
            elif not ok:
                gf = None
        return gf

    def t_settle(f):
        gf = None
        for k in range(len(w.t)):
            if w.t[k] < C.T0:
                continue
            ok = all((w.rows[k][c] / vbe if hi else 1.0 - w.rows[k][c] / vbe) >= f
                     for c, hi in cols)
            if ok and gf is None:
                gf = w.t[k]
            elif not ok:
                gf = None
        return gf

    for f, k in ((0.80, "t_valid80_ps"), (0.90, "t_valid90_ps"),
                 (0.95, "t_valid95_ps")):
        tv = t_valid(f)
        r[k] = None if tv is None else tv - C.T0
    ts = t_settle(0.90)
    r["t_settle90_ps"] = None if ts is None else ts - C.T0
    tr90 = w.cross("V(bkb)", 0.9 * vbe, tmin=C.T0)
    r["t_rail90_ps"] = None if tr90 is None else tr90 - C.T0
    # ---- A2 pass/fail
    r["A2_settle_pass"] = bool(r["t_valid90_ps"] is not None)
    r["A2_settle_strict_pass"] = bool(r["t_valid90_ps"] is not None
                                      and r["t_valid90_ps"] <= C.BEAT_PS)

    # ---- pull-up Vgs at the moment it conducts
    #   DEFINITION (corrected): the raw max dV/dt of a rising node lands at the
    #   very start of the rail ramp, where every node is being dragged up by the
    #   rail itself and the pull-up has done nothing.  The instant that actually
    #   isolates the pull-up's own action is the max of d(V_node - V_rail)/dt --
    #   the node gaining ON the rail.  Reported alongside the node's 50%
    #   crossing, the freeze instant and the end, so no single definition carries
    #   the claim.
    vg = {}
    rise = [(n, ci) for n, hi, ci in checked if hi]
    vbv = w.v("V(bkb)")
    for n, ci in rise[:4]:
        y = w.v("V(%s)" % n)
        best, tb = -1e30, None
        for k in range(1, len(w.t)):
            dt = w.t[k] - w.t[k - 1]
            if dt <= 0 or w.t[k] < C.T0:
                continue
            s = ((y[k] - vbv[k]) - (y[k - 1] - vbv[k - 1])) / dt
            if s > best:
                best, tb = s, w.t[k]
        ve = w.at("V(%s)" % n, tE)
        t50 = w.cross("V(%s)" % n, 0.5 * ve, tmin=C.T0) or tb
        e = dict(t_conduct_ps=tb, rel_slope_V_per_ps=best, t_50pct_ps=t50,
                 rail_at_t=w.at("V(bkb)", tb) if tb else None)
        if d["mode"] == "strip":
            # the pull-up driving node n is gated by the OPPOSITE node
            opp = ("n%d" % ci) if n.startswith("q") else ("q%d" % ci)
            for lbl, t in (("at_conduct", tb), ("at_50pct", t50),
                           ("at_open", to), ("at_end", tE)):
                rr = w.at("V(bkb)", t)
                e["Vgs_%s_V" % lbl] = w.at("V(%s)" % opp, t) - rr
                e["Vgs_over_rail_%s" % lbl] = (w.at("V(%s)" % opp, t) - rr) / rr
                e["Vbs_%s_V" % lbl] = 0.0      # source AND bulk are the rail node
            e["gate_node"] = opp
        else:
            # the binding series pMOS of the static cell: its source is the
            # internal node, its bulk is the rail -> reverse body bias.
            inter = {"o21ai": "net14", "o21ai_hb": "net14", "nor2": "net1",
                     "xnor2": "net4", "mux2": "net5"}.get(d["fam"])
            if inter:
                nd = "%s_%d" % (inter, ci)
                try:
                    for lbl, t in (("at_conduct", tb), ("at_50pct", t50),
                                   ("at_open", to), ("at_end", tE)):
                        rr = w.at("V(bkb)", t)
                        vs = w.at("V(%s)" % nd, t)
                        e["series_src_V_%s" % lbl] = vs
                        e["Vsg_%s_V" % lbl] = vs - 0.0   # gate of the series
                        e["Vbs_%s_V" % lbl] = rr - vs    # bulk - source > 0
                        e["Vgs_%s_V" % lbl] = 0.0 - vs
                        e["Vgs_over_rail_%s" % lbl] = (0.0 - vs) / rr
                    e["series_src_node"] = nd
                except KeyError:
                    e["series_src_node"] = None
        vg[n] = e
    r["pullup"] = vg
    return r


# -------------------------------------------------------------------- stages
def do_row(tag):
    d = cfg(tag)
    os.makedirs(ROWD, exist_ok=True)
    t0 = time.monotonic()
    p, msg, wp = C.run("p_%s.cir" % tag, probe_deck(d), timeout=600)
    print(" probe:", msg, flush=True)
    if not p:
        return {"tag": tag, "error": msg}
    tz, ipk, tipk = zero_of(p + ".prn")
    if tz is None:
        return {"tag": tag, "error": "no ZCS zero"}
    print("  zero %.4f ps (hop %.4f), Ipk %.1f uA" % (tz, tz - C.T0, ipk), flush=True)
    lines, hm = hop_deck(d, tz - C.T0)
    h, msg, wh = C.run("h_%s.cir" % tag, lines, timeout=900)
    print(" hop:", msg, flush=True)
    if not h:
        return {"tag": tag, "error": msg}
    r = extract(h + ".prn", d, hm)
    r["probe_Ipk_uA"] = ipk
    r["wall_probe_s"], r["wall_hop_s"] = wp, wh
    json.dump(r, open(os.path.join(ROWD, tag + ".json"), "w"), indent=1)
    print(json.dumps({k: v for k, v in r.items()
                      if k not in ("per_node", "pullup")}, indent=1), flush=True)
    return r


def reextract(tag):
    """Re-run the extractor on a hop .prn already on disk -- no re-simulation."""
    d = cfg(tag)
    hp = os.path.join(HERE, "h_%s.cir.prn" % tag)
    pp = os.path.join(HERE, "p_%s.cir.prn" % tag)
    if not (os.path.exists(hp) and os.path.exists(pp)):
        return None
    tz, ipk, _ = zero_of(pp)
    _, hm = hop_deck(d, tz - C.T0)
    r = extract(hp, d, hm)
    r["probe_Ipk_uA"] = ipk
    old = os.path.join(ROWD, tag + ".json")
    if os.path.exists(old):
        o = json.load(open(old))
        for k in ("wall_probe_s", "wall_hop_s"):
            if k in o:
                r[k] = o[k]
    json.dump(r, open(old, "w"), indent=1)
    return r


if __name__ == "__main__":
    if sys.argv[1] == "reext":
        tags = sys.argv[2:] or [f[:-5] for f in sorted(os.listdir(ROWD))
                                if f.endswith(".json")]
        for t in tags:
            r = reextract(t)
            print(t, "reextracted" if r else "SKIP (no .prn)")
    elif sys.argv[1] == "row":
        for t in sys.argv[2:]:
            do_row(t)
    elif sys.argv[1] == "list":
        print("\n".join(ROWS))
