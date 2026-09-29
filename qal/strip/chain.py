#!/usr/bin/env python3
"""(f) THE CHAIN, TANK-FED -- stripped o21ai vs static o21ai, six banks deep.

The transfer configuration is the committed qal/banktank PER-BANK-TANK scheme at
its HEADLINE PASSING POINT (RESULTS.json HEADLINE_pre_registered_point):
    m = 10, T = 200 ps, H = 4, dv = 1.2, mode 'free'
    per-bank local tank C_tank = m * C_bank -> own inductor L = 15 nH -> RS = 10
    -> tg15p transfer triple (wn 10u / wp 20u / park 2u) -> that bank's rail,
    charge RETURNED to the same tank at c_k + H*T,
    park referenced to THAT BANK'S TANK (banktank AMENDMENT A6, not to ground),
    true-ZCS probe-then-cut for both the raise and the return of every bank.
That point carried 4 banks of 8 inverters 32/32 value-correct.  NOTHING about the
transfer network is retuned here.  The ONLY change is what sits on the bank node:
o21ai-function cells, stripped or static, and SIX banks instead of four.

DATA: bank 1's inputs are ideal DC sources (it is the chain head, and only it).
For k > 1 the gate input nets of bank k ARE the predecessor's output nets.  No
flop, latch, buffer, keeper or level shifter anywhere.  The stripped cell needs
both polarities of each input and PRODUCES both, so the dual-rail chain needs no
extra inverters -- that is the point of the topology and it is why the device
count comparison is the honest one.

PEER-FED IS NOT TESTED (pre-registered exclusion: it fails for everything).
"""
import json, math, os, re, sys, time
import common as C
import cells as K

HERE = C.HERE
ROWD = os.path.join(HERE, "rowd")

# ---- committed banktank constants, inherited verbatim -----------------------
NBANK = 6
MGATE = 4
CBANK = 35.979          # fF, the committed MEASURED secant C of one bank
L_REF = 15.0            # nH
RS_REF = 10.0           # ohm
TOT_UM = 30.0           # tg15p total width
VGH = 1.5
EDGE = 2.0
TAIL = 500.0
T1 = 200.0              # ps, bank 1's rail-raise closes (pre-roll)
TZ_ANCH = 65.49500982344826   # ps, committed L=15/W30/dV1.2 single-hop zero
VTN = 0.5239460152201223      # MEASURED, qal/chain3/vt.json
VTP_ABS = 0.4402734454819182  # MEASURED, qal/chain3/vt.json
SEP_FLOOR_MV = 6.44           # the campaign's quoted separation floor
# The STATIC control chain uses the HAND-BUILT o21ai (l = 0.13 um), i.e. the
# very cell the committed anchor was measured on and the STRONGER device (the
# PDK cell is l = 0.15 um), so the control is GENEROUS to static CMOS.
STATFAM = "o21ai_hb"
WXC = C.WXC                   # overridable: the cross-coupled pMOS width

# bank 1 head vectors, one per cell.  Chosen (see pick_head) so that no bank in
# the chain becomes all-HIGH or all-LOW, which would make separation vacuous.
HEAD = [{"A1": 1, "A2": 0, "B1": 1},     # -> 0
        {"A1": 0, "A2": 1, "B1": 1},     # -> 0
        {"A1": 0, "A2": 0, "B1": 1},     # -> 1  (vec_out_hi: the 2-high pMOS case)
        {"A1": 1, "A2": 1, "B1": 0}]     # -> 1


def widths(tot):
    return dict(wn=tot / 3.0, wp=2.0 * tot / 3.0, park=tot / 15.0)


def wiring(i):
    """cell i of bank k takes A1,A2,B1 from predecessor cells i, i+2, i+1.

    These offsets and the HEAD above were chosen by exhaustive search over all
    distinct offset triples and all 16 bank-1 output patterns, for the ONLY
    combination that keeps the chain both MIXED at every depth (never all-HIGH
    or all-LOW, which would make separation vacuous) and NON-ALTERNATING: the
    bank pattern rotates through 4 distinct states 0011 -> 1001 -> 1100 -> 0110,
    so the 4 cells of a bank are not one electrical class repeated.  That is the
    fixture defect qal/skip4 flagged (intra-class spread 0.000 pp in every bank,
    so a per-gate rule could not catch a single-gate outlier); this deck is built
    so it can."""
    return {"A1": i % MGATE, "A2": (i + 2) % MGATE, "B1": (i + 1) % MGATE}


def expected(head=None):
    """Propagate the head pattern through the chain.  Returns exp[k][i] in 0/1."""
    head = head or HEAD
    exp = {1: [K.f_of("o21ai", v) for v in head]}
    for k in range(2, NBANK + 1):
        prev = exp[k - 1]
        exp[k] = []
        for i in range(MGATE):
            w = wiring(i)
            exp[k].append(K.f_of("o21ai", {p: prev[w[p]] for p in w}))
    return exp


def pick_head():
    """Report whether the pre-registered head keeps a mix at every depth."""
    e = expected()
    return {str(k): dict(bits=e[k], mixed=bool(0 < sum(e[k]) < MGATE))
            for k in e}


def vtank0(m, dv):
    """Committed banktank DERIVED pre-charge: dV_rail = 2*V_t0*m/(m+1)."""
    return dv * (m + 1.0) / (2.0 * m)


# ------------------------------------------------------------------ schedule
def schedule(T, H, dv, tzr=None, tzq=None):
    tzr = tzr or [TZ_ANCH] * NBANK
    tzq = tzq or [TZ_ANCH] * NBANK
    c = {k: T1 + (k - 1) * T for k in range(1, NBANK + 1)}
    o = {k: c[k] + tzr[k - 1] for k in range(1, NBANK + 1)}
    r = {k: c[k] + H * T for k in range(1, NBANK + 1)}
    ro = {k: r[k] + tzq[k - 1] for k in range(1, NBANK + 1)}
    bnd = {}
    for k in range(1, NBANK + 1):
        b = min(c[k] + T, r[k] - EDGE)
        if k > 1:
            b = min(b, r[k - 1] - EDGE)
        bnd[k] = b
    tend = max(max(ro.values()), max(bnd.values())) + TAIL
    return dict(T=T, H=H, dv=dv, c=c, o=o, r=r, ro=ro, bound=bnd, tend=tend,
                tzr=tzr, tzq=tzq)


def tank_branch(k, m, l_nh, rs):
    w = widths(TOT_UM)
    return ["CT%d tnk%d 0 %gf" % (k, k, m * CBANK),
            "L%d tnk%d mid%d %gn" % (k, k, k, l_nh),
            "R%d mid%d sw%d %g" % (k, k, k, rs),
            "XSWN%d sw%d gt%d rail%d 0 sg13_lv_nmos w=%gu l=0.13u"
            % (k, k, k, k, w["wn"]),
            "XSWP%d sw%d gtp%d rail%d vhi sg13_lv_pmos w=%gu l=0.13u"
            % (k, k, k, k, w["wp"]),
            # banktank AMENDMENT A6: park referenced to THIS BANK'S TANK
            "XPK%d sw%d pk%d tnk%d tnk%d sg13_lv_nmos w=%gu l=0.13u"
            % (k, k, k, k, k, w["park"])]


def phase_pwl(k, wins, big):
    pn, pp, pk = [(0.0, 0.0)], [(0.0, VGH)], [(0.0, VGH)]
    for (tc, to) in wins:
        pn += [(tc - EDGE, 0.0), (tc, VGH)]
        pp += [(tc - EDGE, VGH), (tc, 0.0)]
        pk += [(tc - EDGE, VGH), (tc, 0.0)]
        if to is None:
            pn += [(big, VGH)]; pp += [(big, 0.0)]; pk += [(big, 0.0)]
            break
        pn += [(to, VGH), (to + EDGE, 0.0)]
        pp += [(to, 0.0), (to + EDGE, VGH)]
        pk += [(to, 0.0), (to + EDGE, VGH)]
    f = lambda p: " ".join("%gp %g" % (t, v) if t > 0 else "0 %g" % v for t, v in p)
    return ["VGT%d gt%d 0 PWL(%s)" % (k, k, f(pn)),
            "VGTP%d gtp%d 0 PWL(%s)" % (k, k, f(pp)),
            "VPK%d pk%d 0 PWL(%s)" % (k, k, f(pk))]


# --------------------------------------------------------------------- cells
def bank_cells(k, mode, dv):
    """One level of logic.  Returns (lines, checked, drive_probe).
    checked: [(node, expect_hi, cell)] ; drive_probe: [(node, cell, role)]"""
    L, checked, drv_pr = ["VMG%d gn%d 0 0" % (k, k)], [], []
    gn = "gn%d" % k
    exp = expected()

    def src(nm, nd, v):
        L.append("V%s %s 0 %g" % (nm, nd, v))

    if k == 1:
        for i, vec in enumerate(HEAD):
            for p, b in vec.items():
                src("I1%s_%d" % (p, i), "i1%s_%d" % (p, i), dv if b else 0.0)
                if mode == "strip":
                    src("J1%s_%d" % (p, i), "j1%s_%d" % (p, i), 0.0 if b else dv)

    def nets(i, p):
        """(true, complement) driving nets for input p of bank k cell i."""
        if k == 1:
            return "i1%s_%d" % (p, i), "j1%s_%d" % (p, i)
        j = wiring(i)[p]
        return ("q%d_%d" % (k - 1, j), "n%d_%d" % (k - 1, j)) if mode == "strip" \
            else ("y%d_%d" % (k - 1, j), None)

    for i in range(MGATE):
        if mode == "strip":
            def lit(l, i=i):
                t, c = nets(i, l[:-1] if l.endswith("#") else l)
                return c if l.endswith("#") else t
            ln, outs = K.strip_cell("%d_%d" % (k, i), "o21ai", "rail%d" % k,
                                    gn, WXC, C.WTREE, C.CLOAD, lit)
            L += ln
            e = bool(exp[k][i])
            checked += [(outs[0], e, i), (outs[1], not e, i)]
        else:
            def drv(p, i=i):
                return nets(i, p)[0]
            ln, outs, inter = K.static_cell("%d_%d" % (k, i), STATFAM,
                                            "rail%d" % k, gn, C.CLOAD, drv)
            L += ln
            checked.append((outs[0], bool(exp[k][i]), i))
        for p in ("A1", "A2", "B1"):
            drv_pr.append((nets(i, p)[0], i, p))
    return L, checked, drv_pr


def deck(mode, m, T, H, dv, l_nh=L_REF, rs=RS_REF, tzr=None, tzq=None, probe=None):
    S = schedule(T, H, dv, tzr, tzq)
    vt0 = vtank0(m, dv)
    big = S["tend"] * 4.0
    L = C.head() + ["VHI vhi 0 %g" % VGH]
    checked, drv_pr = [], []
    for k in range(1, NBANK + 1):
        ln, ch, dp = bank_cells(k, mode, dv)
        L += ln; checked += [(n, h, (k, i)) for n, h, i in ch]; drv_pr += dp
    for k in range(1, NBANK + 1):
        L += tank_branch(k, m, l_nh, rs)
    for k in range(1, NBANK + 1):
        if probe is None:
            wins = [(S["c"][k], S["o"][k]), (S["r"][k], S["ro"][k])]
        elif probe[0] == "rise":
            wins = ([(S["c"][k], S["o"][k])] if k < probe[1]
                    else ([(S["c"][k], None)] if k == probe[1] else []))
        else:
            wins = [(S["c"][k], S["o"][k])]
            if k < probe[1]:
                wins.append((S["r"][k], S["ro"][k]))
            elif k == probe[1]:
                wins.append((S["r"][k], None))
        if not wins:
            L += ["VGT%d gt%d 0 0" % (k, k), "VGTP%d gtp%d 0 %g" % (k, k, VGH),
                  "VPK%d pk%d 0 %g" % (k, k, VGH)]
        else:
            L += phase_pwl(k, wins, big)

    if probe is None:
        for k in range(1, NBANK + 1):
            L += C.integ("qlt%d" % k, "I(L%d)" % k)
            L += C.integ("ea%d" % k, "V(tnk%d)*I(L%d)" % (k, k))
            L += C.integ("esw%d" % k, "V(sw%d)*I(L%d)" % (k, k))
            L += C.integ("er%d" % k, "I(L%d)*I(L%d)*%g" % (k, k, rs))
            L += C.integ("ec%d" % k, "V(rail%d)*I(VMG%d)" % (k, k))
        tend = S["tend"]
    elif probe[0] == "rise":
        tend = S["c"][probe[1]] + 2.6 * TZ_ANCH * math.sqrt(l_nh / L_REF)
    else:
        tend = S["r"][probe[1]] + 2.6 * TZ_ANCH * math.sqrt(l_nh / L_REF)

    L.append(".ic " + " ".join("V(tnk%d)=%g V(rail%d)=0 V(sw%d)=%g"
                               % (k, vt0, k, k, vt0) for k in range(1, NBANK + 1))
             + " " + " ".join("V(%s)=0" % n for n, _, _ in checked))
    L.append(".tran 0.1p %gp 0 0.25p" % tend)
    if probe is None:
        pr = (["V(rail%d)" % k for k in range(1, NBANK + 1)]
              + ["V(tnk%d)" % k for k in range(1, NBANK + 1)]
              + ["I(L%d)" % k for k in range(1, NBANK + 1)]
              + ["V(%s)" % n for n, _, _ in checked]
              + ["V(x%s%d)" % (t, k) for k in range(1, NBANK + 1)
                 for t in ("qlt", "ea", "esw", "er", "ec")])
    else:
        pr = (["I(L%d)" % k for k in range(1, NBANK + 1)]
              + ["V(rail%d)" % k for k in range(1, NBANK + 1)]
              + ["V(tnk%d)" % k for k in range(1, NBANK + 1)])
    for j in range(0, len(pr), 8):
        L.append((".print tran " if j == 0 else "+ ") + " ".join(pr[j:j + 8]))
    L.append(".end")
    return L, S, checked, drv_pr


# --------------------------------------------------------------------- zeros
def zero_after(w, col, t_close):
    y = w.v(col)
    pk, tpk = 0.0, None
    for k, t in enumerate(w.t):
        if t < t_close:
            continue
        if abs(y[k]) > abs(pk):
            pk, tpk = y[k], t
    if tpk is None:
        return None, None
    prev = None
    for k, t in enumerate(w.t):
        if t <= tpk:
            prev = (t, y[k]); continue
        if prev is not None and (y[k] == 0.0 or (prev[1] > 0) != (y[k] > 0)):
            t0, v0 = prev
            return (t0 if y[k] == v0 else
                    t0 + (0.0 - v0) * (t - t0) / (y[k] - v0)), pk
        prev = (t, y[k])
    return None, pk


def measure_zeros(mode, m, T, H, dv):
    """True-ZCS probe-then-cut: find every raise zero, then every return zero."""
    tzr, tzq = [TZ_ANCH] * NBANK, [TZ_ANCH] * NBANK
    for k in range(1, NBANK + 1):
        L, S, _, _ = deck(mode, m, T, H, dv, tzr=tzr, tzq=tzq, probe=("rise", k))
        p, msg, _ = C.run("zr_%s%s_%d.cir"
                          % (mode, ("_w%g" % (WXC * 100)) if mode == "strip" else "",
                             k), L, timeout=900)
        print("  probe rise %d: %s" % (k, msg), flush=True)
        if not p:
            return None, None
        z, pk = zero_after(C.W(p + ".prn"), "I(L%d)" % k, S["c"][k])
        if z is None:
            return None, None
        tzr[k - 1] = z - S["c"][k]
        print("   tzr[%d] = %.4f ps (Ipk %.1f uA)" % (k, tzr[k - 1], pk * 1e6),
              flush=True)
    for k in range(1, NBANK + 1):
        L, S, _, _ = deck(mode, m, T, H, dv, tzr=tzr, tzq=tzq, probe=("ret", k))
        p, msg, _ = C.run("zq_%s%s_%d.cir"
                          % (mode, ("_w%g" % (WXC * 100)) if mode == "strip" else "",
                             k), L, timeout=900)
        print("  probe ret %d: %s" % (k, msg), flush=True)
        if not p:
            return None, None
        z, pk = zero_after(C.W(p + ".prn"), "I(L%d)" % k, S["r"][k])
        if z is None:
            return None, None
        tzq[k - 1] = z - S["r"][k]
        print("   tzq[%d] = %.4f ps" % (k, tzq[k - 1]), flush=True)
    return tzr, tzq


# ------------------------------------------------------------------- the row
def row(mode, m=10.0, T=200.0, H=4, dv=1.2, tag=None):
    tag = tag or ("chain_%s_m%g_T%g_H%d_dv%g%s"
                  % (mode, m, T, H, dv * 1000,
                     ("_wxc%g" % (WXC * 100)) if mode == "strip" else ""))
    os.makedirs(ROWD, exist_ok=True)
    zf = os.path.join(HERE, "zeros_%s%s.json"
                      % (mode, ("_wxc%g" % (WXC * 100)) if mode == "strip" else ""))
    if os.path.exists(zf):
        z = json.load(open(zf)); tzr, tzq = z["tzr"], z["tzq"]
        print(" zeros: cached", flush=True)
    else:
        tzr, tzq = measure_zeros(mode, m, T, H, dv)
        if tzr is None:
            return {"tag": tag, "error": "zero probe failed"}
        json.dump({"tzr": tzr, "tzq": tzq}, open(zf, "w"), indent=1)
    L, S, checked, drv_pr = deck(mode, m, T, H, dv, tzr=tzr, tzq=tzq)
    p, msg, wall = C.run("c_%s.cir" % tag, L, timeout=1800)
    print(" chain:", msg, flush=True)
    if not p:
        return {"tag": tag, "error": msg}
    w = C.W(p + ".prn")
    exp = expected()
    r = dict(tag=tag, mode=mode, m=m, T_ps=T, H=H, dv=dv, nbank=NBANK,
             mgate=MGATE, wall_s=wall, tzr=tzr, tzq=tzq,
             bound_ps=S["bound"], head_pattern=HEAD,
             expected_bits={str(k): exp[k] for k in exp},
             head_mix=pick_head(), banks={})
    for k in range(1, NBANK + 1):
        tb = S["bound"][k]
        rail = w.at("V(rail%d)" % k, tb)
        nodes, ups, dns = {}, [], []
        for n, hi, (kk, i) in checked:
            if kk != k:
                continue
            v = w.at("V(%s)" % n, tb)
            s = 100.0 * ((v / rail) if hi else (1.0 - v / rail))
            nodes[n] = dict(cell=i, expect_hi=hi, V=v, settle_pct=s)
            (ups if hi else dns).append(v)
        sep = (min(ups) - max(dns)) if (ups and dns) else None
        # PATTERN GUARD (the skip4 lesson): a node can sit at the right value
        # merely because nothing disturbed it.  Check the gate drive of the
        # literals that are supposed to be conducting against the MEASURED Vtn.
        drives = {}
        for nd, i, port in drv_pr:
            if k == 1:
                continue
            try:
                drives["%s_c%d_%s" % (nd, i, port)] = w.at("V(%s)" % nd, tb)
            except KeyError:
                pass
        hi_drives = [v for v in drives.values() if v > rail * 0.5]
        r["banks"][str(k)] = dict(
            t_bound_ps=tb, rail_V=rail, nodes=nodes,
            sep_mV=None if sep is None else sep * 1e3,
            sep_x_floor=None if sep is None else sep * 1e3 / SEP_FLOOR_MV,
            sep_pct_rail=None if sep is None else sep / rail * 100.0,
            worst_gate_pct=min(v["settle_pct"] for v in nodes.values()),
            worst_gate=min(nodes, key=lambda x: nodes[x]["settle_pct"]),
            all_values_correct=bool(all(
                (v["V"] > rail * 0.5) == v["expect_hi"] for v in nodes.values())),
            per_gate_correct={n: bool((v["V"] > rail * 0.5) == v["expect_hi"])
                              for n, v in nodes.items()},
            pattern_guard_min_hi_drive_V=(min(hi_drives) if hi_drives else None),
            pattern_guard_pass=(None if k == 1 else
                                bool(hi_drives and min(hi_drives) > VTN)),
            Vtn_ref=VTN)
        iz = w.at("I(L%d)" % k, S["c"][k] + tzr[k - 1])
        r["banks"][str(k)]["IZ_uA"] = iz * 1e6
        r["banks"][str(k)]["A4_iz_pass"] = bool(abs(iz * 1e6) < 1.0)
    r["all_banks_value_correct"] = bool(
        all(b["all_values_correct"] for b in r["banks"].values()))
    r["sep_min_mV"] = min(b["sep_mV"] for b in r["banks"].values()
                          if b["sep_mV"] is not None)
    r["worst_gate_pct_any_bank"] = min(b["worst_gate_pct"]
                                       for b in r["banks"].values())
    json.dump(r, open(os.path.join(ROWD, tag + ".json"), "w"), indent=1)
    print(json.dumps({k: v for k, v in r.items() if k != "banks"}, indent=1),
          flush=True)
    for k, b in r["banks"].items():
        print(" bank %s rail %.4f sep %.1f mV (%.0fx floor) worst %.2f%% corr %s"
              % (k, b["rail_V"], b["sep_mV"] or 0, b["sep_x_floor"] or 0,
                 b["worst_gate_pct"], b["all_values_correct"]), flush=True)
    return r


if __name__ == "__main__":
    if sys.argv[1] == "head":
        print(json.dumps(pick_head(), indent=1))
    else:
        if len(sys.argv) > 2:
            WXC = float(sys.argv[2])
        row(sys.argv[1])
