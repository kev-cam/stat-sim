#!/usr/bin/env python3
"""qal/burst -- wake->calibrate->burst->park composition on the committed
banktank arrangement (bt.py reused as a library, emitter untouched).

Stages:
  ic          regenerate committed dv1650 row byte-identical, run HERE, digit-check
  park        dedicated parked-chain drain deck (~24 ns, relaxed max step, null cap)
  cycle <ns>  park(T_pre) -> burst(5 waves, alternating pattern) -> park deck
  cmosburst   same 32 cells, static 1.2 V, same alternating pattern (5 flips)
  cmosidle    same 32 cells held + 30um pMOS header off-leak + null
"""
import json, math, os, sys, importlib.util, hashlib

HERE = os.path.dirname(os.path.abspath(__file__))
BT_DIR = os.path.join(HERE, "..", "banktank")
spec = importlib.util.spec_from_file_location("bt", os.path.join(BT_DIR, "bt.py"))
bt = importlib.util.module_from_spec(spec)
CACHE = "/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6/scratchpad/vae_cache_burst"
os.environ["PYMS_VAE_CACHE"] = CACHE
spec.loader.exec_module(bt)
bt.HERE = HERE                      # run decks in qal/burst, never in banktank/
bt.ENV = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS",
              PYMS_VAE_CACHE=CACHE)

Z = json.load(open(os.path.join(BT_DIR, "zeros_m10_dv1650.json")))
M, T, H, DV = 10.0, 150.0, 4, 1.65
VT0 = bt.vtank0(M, DV)              # 0.9075

# ---------------------------------------------------------------- stage: ic
def stage_ic():
    lines, S = bt.deck(M, T, H, DV, mode="free", tzr=Z["tzr"], tzq=Z["tzq"])
    mine = "\n".join(lines) + "\n"
    committed = open(os.path.join(BT_DIR, "c_m10_T150_H4_dv1650_free.cir")).read()
    ident = (mine == committed)
    print("deck byte-identical to committed:", ident)
    if not ident:
        # show first diff line for the record
        a, b = mine.splitlines(), committed.splitlines()
        for i, (x, y) in enumerate(zip(a, b)):
            if x != y:
                print("first diff at line", i, "\n mine:", x, "\n comm:", y); break
        return False
    p, msg = bt.run("ic_row_dv1650.cir", lines, timeout=3600)
    print(msg)
    if p is None:
        return False
    mm = bt.parse_mt0(p + ".mt0")
    cm = bt.parse_mt0(os.path.join(BT_DIR, "c_m10_T150_H4_dv1650_free.cir.mt0"))
    worst, worst_k, nfail, ncmp = 0.0, None, 0, 0
    for k, v in cm.items():
        if k not in mm:
            continue
        ncmp += 1
        d = abs(mm[k] - v) / max(abs(v), 1e-30)
        if abs(v) < 1e-25 and abs(mm[k] - v) < 1e-25:
            d = 0.0
        if d > worst:
            worst, worst_k = d, k
        if d > 1e-6:
            nfail += 1
    res = dict(deck_byte_identical=ident, n_keys=ncmp, n_fail_1e6=nfail,
               worst_rel=worst, worst_key=worst_k,
               rails={k: mm.get("VR%dB" % k) for k in range(1, 5)},
               PASS=(ident and nfail == 0))
    json.dump(res, open(os.path.join(HERE, "IC.json"), "w"), indent=1)
    print(json.dumps(res, indent=1))
    return res["PASS"]

# ------------------------------------------------------------- stage: park
def stage_park():
    """Dedicated parked-chain drain deck, ~24 ns, relaxed 10 ps max step
    (justified: no fast transient present; gated by the null control).
    Islands: A = the full parked 4-bank chain (the real thing, x4 samples);
    B = tank+park device only (park/GMIN pedestal); C = floating null cap."""
    L = bt.head_lines() + ["VHI vhi 0 %g" % bt.VGH]
    for k in range(1, 5):
        L += bt.bank_cells(k, DV)
    for k in range(1, 5):
        L += bt.tank_branch(k, M, 30.0, bt.L_REF, bt.RS_REF)
        L += ["VGT%d gt%d 0 0" % (k, k), "VGTP%d gtp%d 0 %g" % (k, k, bt.VGH),
              "VPK%d pk%d 0 %g" % (k, k, bt.VGH)]
    # island B: tank + park device only
    L += ["CTB tnkb 0 %gf" % (M * bt.CBANK),
          "XPKB swb pkb tnkb tnkb sg13_lv_nmos w=2u l=0.13u",
          "VPKB pkb 0 %g" % bt.VGH]
    # island C: null
    L += ["CNULL nl 0 %gf" % (M * bt.CBANK)]
    # meters: 1F t0-referenced integrators on every source + I(L)
    tags = []
    for k in range(1, 5):
        for nm, ex in (("qlt%d" % k, "I(L%d)" % k),
                       ("ea%d" % k, "V(tnk%d)*I(L%d)" % (k, k)),
                       ("qg%d" % k, "I(VMG%d)" % k)):
            L += bt.integ(nm, ex); tags.append(nm)
    L += bt.integ("qi1", "-(" + "+".join("I(VI1_%d)" % i for i in range(8)) + ")")
    L += bt.integ("ei1", "-(" + "+".join("V(in1_%d)*I(VI1_%d)" % (i, i)
                                         for i in range(8)) + ")")
    L += bt.integ("egt", "-" + "-".join(
        "V(gt%d)*I(VGT%d)-V(gtp%d)*I(VGTP%d)-V(pk%d)*I(VPK%d)"
        % (k, k, k, k, k, k) for k in range(1, 5)))
    L += bt.integ("ehi", "-%g*I(VHI)" % bt.VGH)
    L += bt.integ("epkb", "-%g*I(VPKB)" % bt.VGH)
    tags += ["qi1", "ei1", "egt", "ehi", "epkb"]
    ic = " ".join("V(tnk%d)=%g V(rail%d)=0 V(sw%d)=%g" % (k, VT0, k, k, VT0)
                  for k in range(1, 5))
    L.append(".ic " + ic + " V(tnkb)=%g V(swb)=%g V(nl)=%g" % (VT0, VT0, VT0))
    L.append(".tran 1p 24000p 0 10p")
    marks = [500.0, 2000.0, 4000.0, 8000.0, 12000.0, 16000.0, 20000.0, 23990.0]
    g = lambda t: t + bt.LAG_PS
    for j, t in enumerate(marks):
        for k in range(1, 5):
            L.append(".measure tran VT%dM%d FIND V(tnk%d) AT=%.3fp" % (k, j, k, g(t)))
            L.append(".measure tran VR%dM%d FIND V(rail%d) AT=%.3fp" % (k, j, k, g(t)))
        L.append(".measure tran VTBM%d FIND V(tnkb) AT=%.3fp" % (j, g(t)))
        L.append(".measure tran VNLM%d FIND V(nl) AT=%.3fp" % (j, g(t)))
        for tg in tags:
            L.append(".measure tran %s_M%d FIND V(x%s) AT=%.3fp" % (tg.upper(), j, tg, g(t)))
    L.append(".print tran precision=17 " + " ".join(
        ["V(tnk%d)" % k for k in range(1, 5)] + ["V(rail1)", "V(sw1)",
         "V(tnkb)", "V(nl)", "I(L1)", "I(L2)", "I(VHI)", "I(VPK1)"]))
    L.append(".end")
    p, msg = bt.run("park24.cir", L, timeout=7200)
    print(msg)
    return p is not None

# ------------------------------------------------------------ stage: cycle
II, NW, TPOST = 800.0, 5, 800.0
II_TU = 1000.0          # amendment A1: top-up needs a real window

def wave_pat(w):
    return bt.PAT if w % 2 == 0 else [1 - b for b in bt.PAT]

def in_hi_w(k, i, w):
    pw = wave_pat(w)
    return (pw[i] == 1) if (k % 2 == 1) else (pw[i] == 0)

def zeros_for_wave(w):
    zr, zq = Z["tzr"], Z["tzq"]
    if w % 2 == 0:
        return zr, zq
    return [zr[1], zr[2], zr[1], zr[2]], [zq[1], zq[2], zq[1], zq[2]]

def cycle_sched(tpre_ps, ii=II):
    T0 = tpre_ps + 200.0
    c, o, r, ro, bnd = {}, {}, {}, {}, {}
    for w in range(NW):
        zr, zq = zeros_for_wave(w)
        for k in range(1, 5):
            c[(k, w)] = T0 + (k - 1) * T + w * ii
            o[(k, w)] = c[(k, w)] + zr[k - 1]
            r[(k, w)] = c[(k, w)] + H * T
            ro[(k, w)] = r[(k, w)] + zq[k - 1]
            bnd[(k, w)] = c[(k, w)] + T
    burst_end = max(ro.values()) + (260.0 if ii > II else 60.0)
    tend = burst_end + TPOST
    return dict(T0=T0, ii=ii, c=c, o=o, r=r, ro=ro, bnd=bnd,
                burst_end=burst_end, tend=tend)

def cycle_deck(tpre_ps, mode="free"):
    S = cycle_sched(tpre_ps, II_TU if mode == "topup" else II)
    big = S["tend"] * 4.0
    L = bt.head_lines() + ["VHI vhi 0 %g" % bt.VGH]
    for k in range(1, 5):
        cl = bt.bank_cells(k, DV)
        if k == 1:                       # replace DC inputs with per-wave PWLs
            cl = [x for x in cl if not x.startswith("VI1_")]
        L += cl
    ii = S["ii"]
    for i in range(8):                   # alternating-pattern inputs
        pts = []
        v = lambda w: DV if wave_pat(w)[i] == 1 else 0.0
        pts.append((0.0, v(0)))
        for w in range(1, NW):
            tf = S["T0"] + w * ii - 40.0
            pts += [(tf - 1.0, v(w - 1)), (tf + 1.0, v(w))]
        f = " ".join("%gp %g" % (t, x) if t > 0 else "0 %g" % x for t, x in pts)
        L.append("VI1_%d in1_%d 0 PWL(%s)" % (i, i, f))
    for k in range(1, 5):
        L += bt.tank_branch(k, M, 30.0, bt.L_REF, bt.RS_REF)
        wins = [(S["c"][(k, w)], S["o"][(k, w)]) for w in range(NW)]
        wins += [(S["r"][(k, w)], S["ro"][(k, w)]) for w in range(NW)]
        wins.sort()
        L += bt.phase_pwl(k, wins, big)
    if mode == "topup":
        # committed §8 costed recharge, per wave (amendment A1): real tg15p-class
        # TG from an ideal rail at V_t0; window ro+2 .. next-rise-10 (~240 ps).
        w_ = bt.widths(30.0)
        L.append("VTK vrch 0 %g" % VT0)
        for k in range(1, 5):
            L += ["XTUN%d tnk%d tun%d vrch 0 sg13_lv_nmos w=%gu l=0.13u"
                  % (k, k, k, w_["wn"]),
                  "XTUP%d tnk%d tup%d vrch vhi sg13_lv_pmos w=%gu l=0.13u"
                  % (k, k, k, w_["wp"])]
            pn, pp = [(0.0, 0.0)], [(0.0, bt.VGH)]
            for w in range(NW):
                a = S["ro"][(k, w)] + 2.0
                b = (S["c"][(k, w + 1)] - 10.0) if w < NW - 1 else (a + 240.0)
                pn += [(a, 0.0), (a + bt.EDGE, bt.VGH), (b, bt.VGH), (b + bt.EDGE, 0.0)]
                pp += [(a, bt.VGH), (a + bt.EDGE, 0.0), (b, 0.0), (b + bt.EDGE, bt.VGH)]
            f = lambda pts: " ".join("%gp %g" % (t, x) if t > 0 else "0 %g" % x
                                     for t, x in pts)
            L += ["VTUN%d tun%d 0 PWL(%s)" % (k, k, f(pn)),
                  "VTUP%d tup%d 0 PWL(%s)" % (k, k, f(pp))]
    ig, tags = bt.integrators(4, bt.RS_REF, mode == "topup")
    L += ig
    L.append(".ic " + " ".join("V(tnk%d)=%g V(rail%d)=0 V(sw%d)=%g"
                               % (k, VT0, k, k, VT0) for k in range(1, 5)))
    L.append(".tran 0.1p %gp 0 0.25p" % S["tend"])
    g = lambda t: t + bt.LAG_PS
    seg = [("Z", 0.5), ("PS", S["T0"] - 10.0), ("BE", S["burst_end"]),
           ("D", S["tend"] - 5.0)]
    for tg in tags:
        for nm, tt in seg:
            L.append(".measure tran %s_%s FIND V(x%s) AT=%.6fp"
                     % (tg.upper(), nm, tg, g(tt)))
    for k in range(1, 5):
        for nm, tt in seg:
            L.append(".measure tran VT%d%s FIND V(tnk%d) AT=%.6fp" % (k, nm, k, g(tt)))
        for w in range(NW):
            L.append(".measure tran VR%dW%d FIND V(rail%d) AT=%.6fp"
                     % (k, w, k, g(S["bnd"][(k, w)])))
            L.append(".measure tran IZ%dW%d FIND I(L%d) AT=%.6fp"
                     % (k, w, k, g(S["o"][(k, w)])))
            L.append(".measure tran IZQ%dW%d FIND I(L%d) AT=%.6fp"
                     % (k, w, k, g(S["ro"][(k, w)])))
            for i in range(8):
                L.append(".measure tran O%d_%dW%d FIND V(o%d_%d) AT=%.6fp"
                         % (k, i, w, k, i, g(S["bnd"][(k, w)])))
    L.append(".print tran " + " ".join(
        ["V(rail%d)" % k for k in range(1, 5)] +
        ["V(tnk%d)" % k for k in range(1, 5)] +
        ["I(L%d)" % k for k in range(1, 5)] +
        ["V(o4_%d)" % i for i in range(8)] + ["V(o1_0)", "V(o2_0)", "V(o3_0)"]))
    L.append(".end")
    return L, S

def stage_cycle(tpre_ps, mode="free"):
    L, S = cycle_deck(tpre_ps, mode)
    fn = "cy_tpre%d.cir" % int(tpre_ps) if mode == "free" \
        else "cytu_tpre%d.cir" % int(tpre_ps)
    p, msg = bt.run(fn, L, timeout=7200)
    print(msg)
    if p is None:
        return False
    json.dump(dict(tpre_ps=tpre_ps, mode=mode, ii=S["ii"], T0=S["T0"],
                   burst_end=S["burst_end"], tend=S["tend"]),
              open(os.path.join(HERE, fn + ".sched.json"), "w"))
    return True

# ------------------------------------------------------- stage: cmos decks
def cmos_chain(vddnode, sfx):
    L = []
    for k in range(1, 5):
        for i in range(8):
            src = ("i%s_%d" % (sfx, i)) if k == 1 else "o%s%d_%d" % (sfx, k - 1, i)
            L.append("XP%s%d_%d o%s%d_%d %s %s %s sg13_lv_pmos w=%gu l=0.13u"
                     % (sfx, k, i, sfx, k, i, src, vddnode, vddnode, bt.WP))
            L.append("XN%s%d_%d o%s%d_%d %s gn%s gn%s sg13_lv_nmos w=%gu l=0.13u"
                     % (sfx, k, i, sfx, k, i, src, sfx, sfx, bt.WN))
            L.append("CL%s%d_%d o%s%d_%d gn%s 2f" % (sfx, k, i, sfx, k, i, sfx))
    return L

def stage_cmosburst():
    VDD = 1.2
    L = bt.head_lines() + ["VDDA vdda 0 %g" % VDD, "VMGA gna 0 0"]
    L += cmos_chain("vdda", "a")
    for i in range(8):
        pts = [(0.0, VDD if bt.PAT[i] == 1 else 0.0)]
        for w in range(1, 6):
            tf = 200.0 + w * II - 40.0
            pw = bt.PAT[i] if w % 2 == 0 else 1 - bt.PAT[i]
            prev = bt.PAT[i] if (w - 1) % 2 == 0 else 1 - bt.PAT[i]
            pts += [(tf - 1.0, VDD * prev), (tf + 1.0, VDD * pw)]
        f = " ".join("%gp %g" % (t, x) if t > 0 else "0 %g" % x for t, x in pts)
        L.append("VIA_%d ia_%d 0 PWL(%s)" % (i, i, f))
    L += bt.integ("evd", "-%g*I(VDDA)" % VDD)
    L += bt.integ("eia", "-(" + "+".join("V(ia_%d)*I(VIA_%d)" % (i, i)
                                         for i in range(8)) + ")")
    g = lambda t: t + bt.LAG_PS
    marks = [("Z", 0.5)] + [("W%d" % w, 200.0 + w * II - 50.0) for w in range(1, 6)] \
        + [("D", 200.0 + 5 * II + 590.0)]
    for nm, tt in marks:
        L.append(".measure tran EVD_%s FIND V(xevd) AT=%.4fp" % (nm, g(tt)))
        L.append(".measure tran EIA_%s FIND V(xeia) AT=%.4fp" % (nm, g(tt)))
    for w in range(1, 6):
        tt = 200.0 + w * II + 400.0
        for i in range(8):
            L.append(".measure tran OA4_%dW%d FIND V(oa4_%d) AT=%.4fp"
                     % (i, w, i, g(tt)))
    L.append(".tran 0.1p %gp 0 0.25p" % (200.0 + 5 * II + 600.0))
    L.append(".print tran V(oa4_0) V(oa4_3) I(VDDA) V(xevd)")
    L.append(".end")
    p, msg = bt.run("cmos_burst.cir", L, timeout=7200)
    print(msg)
    return p is not None

def stage_cmosidle():
    VDD = 1.2
    L = bt.head_lines()
    # island 1: powered, inputs held (clock-gated CMOS leakage of the block)
    L += ["VDDA vdda 0 %g" % VDD, "VMGA gna 0 0"]
    L += cmos_chain("vdda", "a")
    for i in range(8):
        L.append("VIA_%d ia_%d 0 %g" % (i, i, VDD if bt.PAT[i] == 1 else 0.0))
    # island 2: power-gated behind a 30 um pMOS header held OFF
    L += ["VDDB vddbs 0 %g" % VDD, "VHG hgb 0 %g" % VDD, "VMGB gnb 0 0",
          "XHDR vvddb hgb vddbs vddbs sg13_lv_pmos w=30u l=0.13u"]
    L += cmos_chain("vvddb", "b")
    for i in range(8):
        L.append("VIB_%d ib_%d 0 %g" % (i, i, VDD if bt.PAT[i] == 1 else 0.0))
    L += ["CNULL nl 0 359.79f"]
    L += bt.integ("eva", "-%g*I(VDDA)" % VDD)
    L += bt.integ("evb", "-%g*I(VDDB)" % VDD)
    L.append(".ic V(nl)=%g" % VT0)
    L.append(".tran 1p 20000p 0 10p")
    g = lambda t: t + bt.LAG_PS
    for j, t in enumerate([500.0, 2000.0, 10000.0, 19990.0]):
        L.append(".measure tran EVA_M%d FIND V(xeva) AT=%.3fp" % (j, g(t)))
        L.append(".measure tran EVB_M%d FIND V(xevb) AT=%.3fp" % (j, g(t)))
        L.append(".measure tran IVA_M%d FIND I(VDDA) AT=%.3fp" % (j, g(t)))
        L.append(".measure tran IVB_M%d FIND I(VDDB) AT=%.3fp" % (j, g(t)))
        L.append(".measure tran VNL_M%d FIND V(nl) AT=%.3fp" % (j, g(t)))
        L.append(".measure tran VVB_M%d FIND V(vvddb) AT=%.3fp" % (j, g(t)))
    L.append(".print tran precision=17 I(VDDA) I(VDDB) V(vvddb) V(nl)")
    L.append(".end")
    p, msg = bt.run("cmos_idle.cir", L, timeout=7200)
    print(msg)
    return p is not None

if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "ic":
        sys.exit(0 if stage_ic() else 1)
    if a and a[0] == "park":
        sys.exit(0 if stage_park() else 1)
    if a and a[0] == "cycle":
        sys.exit(0 if stage_cycle(float(a[1])) else 1)
    if a and a[0] == "cycletu":
        sys.exit(0 if stage_cycle(float(a[1]), "topup") else 1)
    if a and a[0] == "cmosburst":
        sys.exit(0 if stage_cmosburst() else 1)
    if a and a[0] == "cmosidle":
        sys.exit(0 if stage_cmosidle() else 1)
    print("stage?")
