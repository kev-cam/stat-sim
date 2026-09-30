#!/usr/bin/env python3
"""qal/rfast harness -- THE (L, T) SWEEP ON RESTORING BANKS AT VGH = 2.174 V.

Imports qal/banktank/bt.py VERBATIM (the qal/eye + qal/eyebeat discipline) and
overrides ONLY what PRE_REGISTERED.json declares:
  bt.VGH   -> 2.174 V   (lever 2: ALL transfer-switch and park gate PWLs, the
                         switch-pMOS n-well rail VHI, the ehi integrator const;
                         set UNCONDITIONALLY per call -- the fastwave A9 lesson)
  l_nh     -> 15/10/6/3 (lever 3, threaded through bt.deck's own parameter)
  total_um -> W* per L  (lever 3b, bt.deck's own parameter; widths() committed)
  bt.PAT   -> the pattern (the qal/eye discipline)
  bt.HERE / bt.CACHE / bt.ENV -> qal/rfast/L*W*/T*/P* under the OWN cache

The eye extractor is qal/eye/eyecalc.py VERBATIM (imported, not copied).
The Newton-on-the-row zero protocol is qal/eyebeat AMENDMENT B2, A6 gate
unchanged (|I(L)| <= 1 uA at every commanded open).

Subcommands:
  warmone <cache> <kind> <w_um>   build ONE geometry into a private cache
  ic1                             instrument anchor: committed banktank row, OLD drive
  ic2                             instrument anchor: fastwave fg2174_n4_L6_W30, 2.174 V
  lane <L> <W> <T> <P>            Newton lane for one (L, W, T, pattern)
  extract <L> <W> <T> [P...]     eye/slack/floor extraction for one (L, W, T)
  seqprobe <L> <W> <T>            the COMMITTED sequential full-8 probe (window
                                  4.0x -- pre-registered amendment) + P0 row A6 read
"""
import importlib.util, json, math, os, shutil, sys

HERE   = os.path.dirname(os.path.abspath(__file__))
BTDIR  = "/usr/local/src/stat-sim/qal/banktank"
EYEDIR = "/usr/local/src/stat-sim/qal/eye"
FWDIR  = "/usr/local/src/stat-sim/qal/fastwave"
SCRATCH = ("/tmp/claude-1001/-usr-local-src/"
           "4921ad0c-f17b-4b84-986a-5917c9ebd2a6/scratchpad")
CACHE  = os.path.join(SCRATCH, "vae_cache_rfast")

M, H, DV, MODE = 10.0, 4, 1.65, "free"
VGH_NEW = 2.174               # V = dV + Vtn = 1.65 + 0.5240 (fastwave H spec)
SIG_TOTAL_MV = 23.308         # MEASURED qal/eye/p2 U3 (6.441 trip + 22.4 driver)
TIMER_PS = 7.272              # INHERITED qal/eye/p2 U2 (0.454 ps/K x +/-16 K)
JIT_WC, DRIFT = 61.6, 4.6     # the eyebeat worst-case budget, reported alongside
CMOS_LVL = 52.510             # fcrit_skept corrected comparator, 2 fF load-matched

_spec = importlib.util.spec_from_file_location("bt", os.path.join(BTDIR, "bt.py"))
bt = importlib.util.module_from_spec(_spec)
sys.modules["bt"] = bt
_spec.loader.exec_module(bt)

sys.path.insert(0, EYEDIR)
import eyeharness as EH            # noqa: E402
import eyecalc as EC               # noqa: E402

PATTERNS = EH.PATTERNS


def redirect(sub, cache=CACHE):
    os.makedirs(cache, exist_ok=True)
    os.makedirs(sub, exist_ok=True)
    bt.HERE = sub
    bt.CACHE = cache
    bt.ENV = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS",
                  PYMS_VAE_CACHE=cache)


def tdirname(L, W, T):
    return os.path.join(HERE, "L%gW%g" % (L, W), "T%g" % T)


# --------------------------------------------------------------------- warm
def cmd_warmone(cache, kind, w):
    """Build ONE PSP103 geometry into a PRIVATE cache (merged later by
    filename -- the .so name is a parameter hash, so the merge is a copy)."""
    sub = os.path.join(HERE, "warm", "%s_%g" % (kind, w))
    redirect(sub, cache)
    L = bt.head_lines() + ["V1 a 0 0.5", "V2 b 0 0.5"]
    if kind == "n":
        L += ["XW d a 0 0 sg13_lv_nmos w=%gu l=0.13u" % w, "RN d b 1k"]
    else:
        L += ["XW e a b b sg13_lv_pmos w=%gu l=0.13u" % w, "RP e 0 1k"]
    L += [".tran 1p 10p", ".print tran V(a)", ".end"]
    p, msg = bt.run("w.cir", L, timeout=1800)
    print("warm %s %g: %s" % (kind, w, msg))
    return 0 if p else 1


# ---------------------------------------------------------------------- ic1
def cmd_ic1():
    """ANCHOR 1: the committed banktank headline row at the OLD drive,
    byte-identical deck, run under THIS study's own cache, digit-checked."""
    sub = os.path.join(HERE, "ic1")
    redirect(sub)
    bt.VGH = 1.5                        # the OLD drive -- set explicitly
    bt.PAT[:] = [1, 1, 1, 0, 1, 0, 0, 1]
    z = json.load(open(os.path.join(BTDIR, "zeros_m10_dv1200_T200_H4.json")))
    lines, S = bt.deck(10.0, 200.0, 4, 1.2, mode="free",
                       tzr=z["tzr"], tzq=z["tzq"])
    mine = "\n".join(lines) + "\n"
    committed = open(os.path.join(BTDIR, "c_m10_T200_H4_dv1200_free.cir")).read()
    ident = (mine == committed)
    print("IC1 deck byte-identical to committed:", ident, flush=True)
    fn = "c_m10_T200_H4_dv1200_free.cir"
    p, msg = bt.run(fn, lines)
    print("IC1", msg, flush=True)
    if p is None:
        return 1
    a = bt.parse_mt0(os.path.join(BTDIR, fn + ".mt0"))
    b = bt.parse_mt0(p + ".mt0")
    keys = sorted(set(a) & set(b))
    worst, fails = 0.0, []
    for k in keys:
        d = abs(a[k] - b[k]) / max(abs(a[k]), abs(b[k]), 1e-30)
        worst = max(worst, d)
        if d > 1e-6:
            fails.append((k, a[k], b[k], d))
    rails = {k: b.get("VR%dB%d" % (k, k)) for k in range(1, 5)}
    out = dict(deck_byte_identical=ident, n_keys=len(keys),
               n_fail_1e6=len(fails), worst_rel=worst, fails=fails[:20],
               rails_regenerated=rails,
               committed_rails=[0.7544238, 0.6767239, 0.7312457, 0.7200878],
               PASS=bool(ident and len(fails) <= 0.01 * len(keys)))
    json.dump(out, open(os.path.join(HERE, "IC1.json"), "w"), indent=1)
    print(json.dumps({k: out[k] for k in
                      ("deck_byte_identical", "n_keys", "n_fail_1e6",
                       "worst_rel", "PASS")}, indent=1))
    print("rails:", rails)
    return 0 if out["PASS"] else 1


# ---------------------------------------------------------------------- ic2
def cmd_ic2():
    """ANCHOR 2: the fastwave 2.174 V frontier row, fw.py unmodified, own cache."""
    fspec = importlib.util.spec_from_file_location(
        "fw", os.path.join(FWDIR, "fw.py"))
    fw = importlib.util.module_from_spec(fspec)
    sys.modules["fw"] = fw
    fspec.loader.exec_module(fw)
    sub = os.path.join(HERE, "ic2")
    os.makedirs(sub, exist_ok=True)
    fw.HERE = sub
    fw.CACHE = CACHE
    fw.ENV = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS",
                  PYMS_VAE_CACHE=CACHE)
    row = fw.point("fg2174_n4_L6_W30", n=4, l_nh=6.0, total_um=30.0,
                   ca_fF=52.767867, vgh=2.174)
    ref = json.load(open(os.path.join(FWDIR, "ROWS.json")))["fg2174_n4_L6_W30"]
    checks, ok = {}, True
    for k, tol in (("t_hop_ps", 1e-4), ("VBEND", 1e-4), ("VBPK", 1e-3),
                   ("VA_open", 1e-3), ("t_level_fcrit_ps", 1e-3),
                   ("Ron_sw_eff_ohm", 1e-3), ("t_level_ps", 1e-3)):
        va, vb = ref.get(k), row.get(k)
        d = (abs(va - vb) / max(abs(va), abs(vb), 1e-30)
             if (va is not None and vb is not None) else None)
        checks[k] = dict(committed=va, rerun=vb, rel=d, tol=tol,
                         ok=bool(d is not None and d <= tol))
        ok = ok and checks[k]["ok"]
    out = dict(row_tag=row.get("tag"), error=row.get("error"),
               checks=checks, PASS=bool(ok and not row.get("error")))
    json.dump(out, open(os.path.join(HERE, "IC2.json"), "w"), indent=1)
    print(json.dumps(out, indent=1))
    return 0 if out["PASS"] else 1


# --------------------------------------------------------------------- lane
def _bounded_zero(hdr, rows, col, t0, t1):
    """eyebeat B2 verbatim: conducting current's zero in [t0, t1] off the row's
    own waveform; linear extrapolation if the window ends first."""
    ic = hdr.index(col)
    seg = [(r[1] * 1e12, r[ic]) for r in rows if t0 <= r[1] * 1e12 <= t1]
    if len(seg) < 4:
        return None, "empty window"
    pk = max(range(len(seg)), key=lambda i: abs(seg[i][1]))
    for i in range(pk + 1, len(seg)):
        (ta, va), (tb, vb) = seg[i - 1], seg[i]
        if vb == 0.0 or (va > 0) != (vb > 0):
            return (ta if vb == va else ta + (0.0 - va) * (tb - ta) / (vb - va)), \
                "crossing"
    (ta, va), (tb, vb) = seg[-2], seg[-1]
    if vb == va:
        return None, "flat tail, no slope"
    tz = tb + (0.0 - vb) * (tb - ta) / (vb - va)
    if tz <= tb:
        return None, "extrapolation went backwards"
    return tz, "extrapolated %.2f ps past window" % (tz - tb)


def _row(L, W, T, z):
    lines, S = bt.deck(M, T, H, DV, mode=MODE, l_nh=L, total_um=W,
                       tzr=z["tzr"], tzq=z["tzq"])
    fn = "c_%s.cir" % bt.tag_of(M, T, H, DV, MODE)
    p, msg = bt.run(fn, lines)
    print("  row %s" % msg, flush=True)
    return (p, S) if p else (None, None)


def cmd_lane(L, W, T, pname, maxit=None):
    sub = os.path.join(tdirname(L, W, T), pname)
    redirect(sub)
    bt.VGH = VGH_NEW                   # LEVER 2, set UNCONDITIONALLY (A9 lesson)
    bt.PAT[:] = list(PATTERNS[pname])
    bt.TPROBE, bt.HPROBE = T, H
    print("=== lane L=%g W=%g T=%g %s bits=%s VGH=%.3f (newton-on-row) ==="
          % (L, W, T, pname, bt.PAT, bt.VGH), flush=True)

    # AMENDMENT A3 seed order: own zeros -> same-(L,W) T=200 zeros -> sqrt-scaled
    # qal/eye zeros.  AMENDMENT A1: maxit 8 for cross-seeded lanes (A6 untouched).
    zp = os.path.join(sub, "zeros.json")
    z200 = os.path.join(tdirname(L, W, 200.0), pname, "zeros.json")
    if os.path.exists(zp):
        z = json.load(open(zp))
        src = "own zeros.json (kept; prior seed: %s)" % z.get("seed", "?")[:60]
        maxit = maxit or 8
        print("  seed: own zeros.json", [round(x, 2) for x in z["tzr"]], flush=True)
    elif T != 200.0 and os.path.exists(z200):
        ze = json.load(open(z200))
        z = dict(tzr=list(ze["tzr"]), tzq=list(ze["tzq"]))
        src = "own (L,W) T=200 %s measured zeros (AMENDMENT A3)" % pname
        maxit = maxit or 8
        print("  seed:", src, [round(x, 2) for x in z["tzr"]], flush=True)
    else:
        s = math.sqrt(L / 15.0)
        ze = json.load(open(os.path.join(EYEDIR, pname, "zeros.json")))
        z = dict(tzr=[x * s for x in ze["tzr"]], tzq=[x * s for x in ze["tzq"]])
        src = ("qal/eye/%s/zeros.json (measured m10 dv1650 L15 T200 H4) "
               "scaled by sqrt(L/15)=%.4f" % (pname, s))
        maxit = maxit or 8             # cross-drive seed (AMENDMENT A1)
        print("  seed:", src, [round(x, 2) for x in z["tzr"]], flush=True)

    hist, a6, p, S = [], False, None, None
    for it in range(1, maxit + 1):
        p, S = _row(L, W, T, z)
        if p is None:
            print("  ROW FAILED (Xyce)")
            return 1
        d = bt.parse_mt0(p + ".mt0")
        res = dict(rise={k: d.get("IZ%d" % k, 0) * 1e6 for k in range(1, 5)},
                   ret={k: d.get("IZQ%d" % k, 0) * 1e6 for k in range(1, 5)})
        worst = max(max(abs(v) for v in res["rise"].values()),
                    max(abs(v) for v in res["ret"].values()))
        hist.append(dict(iter=it, tzr=list(z["tzr"]), tzq=list(z["tzq"]),
                         residual_uA={a: {str(k): round(v, 4) for k, v in
                                          res[a].items()} for a in res},
                         worst_uA=round(worst, 4)))
        a6 = worst <= 1.0
        print("  iter %d: worst |I(L)| at opens = %.4f uA -> %s"
              % (it, worst, "A6 PASS" if a6 else "correcting"), flush=True)
        shutil.copy(p + ".mt0", os.path.join(sub, "mt0_iter%d" % it))
        if a6 or it == maxit:
            break
        hdr, rows = bt.read_prn(p + ".prn")
        tzr, tzq = list(z["tzr"]), list(z["tzq"])
        for k in range(1, 5):
            ck, ok_ = S["c"][k], S["o"][k]
            rk, rok = S["r"][k], S["ro"][k]
            tzn, how = _bounded_zero(hdr, rows, "I(L%d)" % k, ck + 5.0, ok_ - 1.0)
            if tzn is not None:
                tzr[k - 1] += max(-10.0, min(10.0, (tzn - ck) - tzr[k - 1]))
            tqn, how2 = _bounded_zero(hdr, rows, "I(L%d)" % k, rk + 5.0, rok - 1.0)
            if tqn is not None:
                tzq[k - 1] += max(-10.0, min(10.0, (tqn - rk) - tzq[k - 1]))
            print("    bank%d dz_rise %+7.3f (%s)  dz_ret %+7.3f (%s)"
                  % (k, tzr[k - 1] - z["tzr"][k - 1], how,
                     tzq[k - 1] - z["tzq"][k - 1], how2), flush=True)
        z = dict(z, tzr=tzr, tzq=tzq)

    z.update(pattern=pname, pattern_bits=list(PATTERNS[pname]),
             L_nH=L, W_um=W, T_row=T, H_row=H, vgh=bt.VGH,
             probe_protocol="newton_on_row (eyebeat B2, A6 gate unchanged)",
             seed=src, newton_history=hist)
    open(zp, "w").write(json.dumps(z, indent=1))
    S = dict(S)
    S.update(pattern=pname, pattern_bits=list(PATTERNS[pname]),
             L_nH=L, W_um=W, vgh=bt.VGH,
             prn=p + ".prn", mt0=p + ".mt0", A6_pass=bool(a6),
             A6_worst_uA=hist[-1]["worst_uA"], newton_iters=len(hist))
    open(os.path.join(sub, "sched.json"), "w").write(
        json.dumps(S, indent=1, default=str))
    print("  %s ->" % ("OK" if a6 else "A6-FAIL(kept, excluded later)"),
          p + ".prn", flush=True)
    return 0 if a6 else 3


# ------------------------------------------------------------------ extract
def crossing(g, y, level, t0, t1, direction, n=None):
    n = n or len(g)
    a0 = max(1, int(math.ceil(t0 / EC.GRID)))
    a1 = min(n - 1, int(math.floor(t1 / EC.GRID)))
    for a in range(a0, a1 + 1):
        y0, y1 = y[a - 1], y[a]
        if direction > 0 and y0 < level <= y1:
            return g[a - 1] + (level - y0) * EC.GRID / (y1 - y0)
        if direction < 0 and y0 > level >= y1:
            return g[a - 1] + (level - y0) * EC.GRID / (y1 - y0)
    return None


def stats(vals):
    if not vals:
        return None
    vs = sorted(vals)
    return dict(n=len(vs), min=round(vs[0], 4), max=round(vs[-1], 4),
                median=round(vs[len(vs) // 2], 4),
                mean=round(sum(vs) / len(vs), 4))


def cmd_extract(L, W, T, pats):
    tdir = tdirname(L, W, T)
    EC.HERE = tdir
    SIG = EC.SIG_TRIP_MV
    THRESH = [("0mV", 0.0), ("1sigma", SIG), ("3sigma", 3 * SIG),
              ("3sigma_total", 3 * SIG_TOTAL_MV)]
    Ps, a6, val = {}, {}, {}
    for p in pats:
        sp = os.path.join(tdir, p, "sched.json")
        if not os.path.exists(sp):
            print("  SKIP %s (no sched.json)" % p)
            continue
        Ps[p] = EC.per_pattern(p)
        S = json.load(open(sp))
        d = bt.parse_mt0(S["mt0"])
        a6[p] = dict(A6_pass=S.get("A6_pass"), worst_uA=S.get("A6_worst_uA"))
        EH.set_pattern(PATTERNS[p])
        bt.PAT[:] = list(PATTERNS[p])
        bad = []
        for k in range(1, 5):
            rail = d.get("VR%dB%d" % (k, k))
            for i in range(8):
                v = d.get("O%d_%dB" % (k, i))
                if v is None or rail is None:
                    bad.append((k, i, "missing"))
                    continue
                ok = (v >= 0.50 * rail) if bt.out_hi(k, i) else (v <= 0.10 * rail)
                if not ok:
                    bad.append((k, i, round(v, 5), round(rail, 5)))
        val[p] = dict(all_32_gates_value_correct=(not bad), fails=bad)
    pats = [p for p in pats if p in Ps]
    if not pats:
        print("nothing to extract")
        return 1
    # AMENDMENT A5: the eye INTERSECTION is over ALL ran patterns, always.
    # The A6 flag rides alongside (a6 record + patterns_A6_pass) and the strict
    # per-row verdict is reported separately.  Forced by measurement: at L <= 6
    # the A2 instrument floor (static 1.0-1.23 uA, ~0.012 ps of commanded-open
    # timing, 4e-9 fJ stranded) straddles the 1 uA line, so membership by A6
    # flag made the intersection pattern set vary ROW BY ROW -- P0-only eyes at
    # L=6 vs three-pattern eyes at L=15, not comparable across L.
    good = pats
    n = min(len(Ps[p]["grid"]) for p in pats)
    g = Ps[pats[0]]["grid"]
    nb, mg = 4, 8
    E = bt.EDGE
    out = dict(L_nH=L, W_um=W, T_ps=T, H=H, dv_V=DV, m=M, vgh=VGH_NEW,
               patterns=pats, patterns_in_intersection=good,
               patterns_A6_pass=[p for p in pats if a6[p]["A6_pass"]],
               a6=a6, value_check=val, banks={})

    for k in range(1, nb + 1):
        P0 = Ps[good[0]]
        ck, rk, rok = P0["c"][k], P0["r"][k], min(Ps[p]["ro"][k] for p in good)
        tendw = g[n - 1] - 1.0
        rec = dict(receiver=("bank %d MEASURED" % (k + 1)) if k < nb else
                   "DERIVED V(rail3)(t-T)", c_ps=ck, r_ps=rk, ro_ps=rok)

        cur = {}
        for ref, key in (("EYE1", "mgn"), ("EYE2", "mgn_data")):
            cur[ref] = {}
            for nm in ("all", "HIGH", "LOW"):
                per = []
                for p in good:
                    gates = [i for i in range(mg)
                             if (nm == "all" or Ps[p]["hi"][k][i] == (nm == "HIGH"))]
                    if gates:
                        M_ = Ps[p][key][k]
                        per.append([min(M_[i][a] for i in gates) for a in range(n)])
                cur[ref][nm] = ([min(c[a] for c in per) for a in range(n)]
                                if per else None)
        intab = [all(Ps[p]["intab"][k][a] for p in good) for a in range(n)]

        rec["EYES"] = {}
        for ref in ("EYE2", "EYE1"):
            use_tab = (ref == "EYE1")
            R = {}
            for tname, tv in THRESH:
                c0 = cur[ref]["all"]
                m_ = [c0[a] > tv and (intab[a] if use_tab else True)
                      for a in range(n)]
                e = EC.eye_from_mask(m_, g, ck, tendw, c0, tv, pick="first")
                if e is None:
                    R[tname] = dict(EYE="EMPTY")
                    continue
                samp = ck + T
                ia = max(0, min(n - 1, int(round(samp / EC.GRID))))
                hh = cur[ref]["HIGH"]
                hl = cur[ref]["LOW"]
                R[tname] = dict(
                    opening_ps=round(e["open_ps"], 4),
                    closing_ps=round(e["close_ps"], 4),
                    WIDTH_ps=round(e["width_ps"], 4),
                    WIDTH_over_T=round(e["width_ps"] / T, 4),
                    opening_minus_c_ps=round(e["open_ps"] - ck, 4),
                    closing_minus_r_ps=round(e["close_ps"] - rk, 4),
                    setup_slack_ps=round(T - (e["open_ps"] - ck), 4),
                    clipped_start=e["clipped_at_window_start"],
                    clipped_end=e["clipped_at_window_end"],
                    WIDTH_IS_LOWER_BOUND=bool(e["clipped_at_window_end"]),
                    eye_open_at_sampling_instant=bool(
                        m_[ia] and e["open_ps"] <= samp <= e["close_ps"]),
                    HEIGHT_at_sampling_HIGH_mV=(round(hh[ia], 4) if hh else None),
                    HEIGHT_at_sampling_LOW_mV=(round(hl[ia], 4) if hl else None))
            rec["EYES"][ref] = R

        # ---- the composed-budget verdict (PRE_REGISTERED G3) off EYE2
        z0 = rec["EYES"]["EYE2"].get("0mV", {})
        zt = rec["EYES"]["EYE2"].get("3sigma_total", {})
        if "opening_minus_c_ps" in z0 and "opening_minus_c_ps" in zt:
            mism = zt["opening_minus_c_ps"] - z0["opening_minus_c_ps"]
            budget = mism + TIMER_PS
            slack0 = T - z0["opening_minus_c_ps"]
            rec["BUDGET_G3"] = dict(
                opening_0mV_ps=z0["opening_minus_c_ps"],
                opening_3sig_total_ps=zt["opening_minus_c_ps"],
                mismatch_term_MEASURED_ps=round(mism, 4),
                timer_term_INHERITED_ps=TIMER_PS,
                budget_ps=round(budget, 4),
                setup_slack_0mV_ps=round(slack0, 4),
                PASS_local=bool(slack0 >= budget),
                worstcase_budget_ps=JIT_WC + DRIFT,
                PASS_worstcase=bool(slack0 >= JIT_WC + DRIFT))
        else:
            rec["BUDGET_G3"] = dict(EYE="EMPTY at 0mV or 3sigma_total")

        ar = min(n - 1, int(round(rk / EC.GRID)))
        c0 = cur["EYE2"]["all"]
        mm = min((c0[a], g[a]) for a in range(ar, n))
        rec["POST_RETURN_FLOOR_EYE2"] = dict(
            floor_mV=round(mm[0], 4), at_t_ps=round(mm[1], 4),
            at_t_minus_r_ps=round(mm[1] - rk, 4),
            in_sigma_trip=round(mm[0] / SIG, 3))

        # ---- tracking lag + stranded-HIGH (anomaly diagnostics, eyebeat verbatim)
        lagA_r, lagA_d, lagB_r, cens = [], [], [], 0
        strand, droop = [], []
        for p in good:
            P = Ps[p]
            d = bt.parse_mt0(json.load(open(os.path.join(tdir, p, "sched.json")))["mt0"])
            vpk = d.get("VR%dPK" % k)
            rail = P["C"]["V(RAIL%d)" % k]
            EH.set_pattern(PATTERNS[p])
            bt.PAT[:] = list(PATTERNS[p])
            hi_gates = [i for i in range(mg) if bt.out_hi(k, i)]
            rop = P["ro"][k]
            lvl = 0.5 * vpk
            tr = crossing(g, rail, lvl, P["c"][k] - E, P["r"][k], +1, n)
            ir0 = min(n - 1, int(round(P["r"][k] / EC.GRID)))
            ir1 = min(n - 1, int(round(min(P["r"][k] + 2 * (rop - P["r"][k]),
                                           g[n - 1]) / EC.GRID)))
            vfloor = min(rail[a] for a in range(ir0, ir1 + 1))
            vref_d = 0.5 * (rail[ir0] + vfloor)
            trd = crossing(g, rail, vref_d, P["r"][k] - E, g[n - 1], -1, n)
            vrb = d.get("VR%dB%d" % (k, k))
            trb = crossing(g, rail, vrb, P["c"][k] - E, P["r"][k], +1, n)
            tripfix = P["tripfix"][k]
            wend = min(rop + 200.0, g[n - 1])
            for i in hi_gates:
                vo = P["C"]["V(O%d_%d)" % (k, i)]
                to = crossing(g, vo, lvl, P["c"][k] - E, P["r"][k], +1, n)
                if tr is not None and to is not None:
                    lagA_r.append(to - tr)
                tob = crossing(g, vo, tripfix, P["c"][k] - E, P["r"][k], +1, n)
                if trb is not None and tob is not None:
                    lagB_r.append(tob - trb)
                tod = crossing(g, vo, vref_d, P["r"][k] - E, wend, -1, n)
                if trd is not None:
                    if tod is not None:
                        lagA_d.append(tod - trd)
                    else:
                        cens += 1
                i0 = max(0, int(round((P["r"][k] - E) / EC.GRID)))
                i1 = min(n - 1, int(round(wend / EC.GRID)))
                vmin, amin = min((vo[a], a) for a in range(i0, i1 + 1))
                strand.append(vmin)
                if g[amin] > P["r"][k]:
                    droop.append((vo[ir0] - vmin) / max(g[amin] - P["r"][k], 1e-9))
        rec["TRACKING_LAG"] = dict(
            rising_LAG_A_ps=stats(lagA_r),
            rising_LAG_B_rail_to_data_ps=stats(lagB_r),
            draining_LAG_A_ps=stats(lagA_d),
            draining_censored_gates=cens)
        rec["STRANDED_HIGH"] = dict(
            min_HIGH_during_drain_V=round(min(strand), 5) if strand else None,
            per_gate_min_V=stats(strand),
            droop_slope_mV_per_ps=stats([1000 * x for x in droop]))
        out["banks"][str(k)] = rec

    # ---- energy, reported never gated (mt0 integrators, t0-referenced)
    en = {}
    for p in good:
        d = bt.parse_mt0(json.load(open(os.path.join(tdir, p, "sched.json")))["mt0"])
        def tz(tag):
            z_ = d.get(tag + "_Z")
            e_ = d.get(tag + "_D")
            return None if (z_ is None or e_ is None) else (e_ - z_) * 1e15
        en[p] = dict(E_gate_drive_fJ=tz("EGT"), E_vhi_fJ=tz("EHI"),
                     note="egt at the ACTUAL 2.174 V PWLs; committed 0.155 fC/um "
                          "gate-charge fit is WRONG 24x (measured 3.635-3.739 fC/um)")
    out["energy_reported_not_gated"] = en

    fn = os.path.join(tdir, "EYEBEAT.json")
    json.dump(out, open(fn, "w"), indent=1)
    print("wrote", fn)
    for k in ("1", "2", "3"):
        b = out["banks"][k]
        for tn in ("0mV", "3sigma_total"):
            z = b["EYES"]["EYE2"].get(tn, {})
            if "EYE" in z or not z:
                print("L%g W%g T%-4g bank%s %-12s EMPTY" % (L, W, T, k, tn))
                continue
            print("L%g W%g T%-4g bank%s %-12s open c+%8.3f  slack %8.3f  W %8.3f%s"
                  % (L, W, T, k, tn, z["opening_minus_c_ps"], z["setup_slack_ps"],
                     z["WIDTH_ps"], "LB" if z["WIDTH_IS_LOWER_BOUND"] else ""))
        bd = b.get("BUDGET_G3", {})
        if "budget_ps" in bd:
            print("           bank%s BUDGET %6.3f (mism %5.3f + timer %5.3f)  "
                  "slack0 %7.3f  local %s  wc %s   floor %8.3f mV"
                  % (k, bd["budget_ps"], bd["mismatch_term_MEASURED_ps"],
                     TIMER_PS, bd["setup_slack_0mV_ps"],
                     "PASS" if bd["PASS_local"] else "FAIL",
                     "PASS" if bd["PASS_worstcase"] else "FAIL",
                     b["POST_RETURN_FLOOR_EYE2"]["floor_mV"]))
    return 0


# ----------------------------------------------------------------- seqprobe
def cmd_seqprobe(L, W, T):
    """Target (d): the COMMITTED sequential full-8 probe at the row's own T
    (banktank A7 protocol), at VGH = 2.174, with the probe window multiplier
    4.0 (pre-registered amendment; dv1650 return zeros outrun the committed
    2.6x dv1.2-anchored window -- eyebeat B2).  Zeros then applied to a P0 row
    and the A6 residuals read -- the committed instrument's own shape."""
    sub = os.path.join(HERE, "seqA6", "L%gW%g_T%g" % (L, W, T))
    redirect(sub)
    bt.VGH = VGH_NEW
    bt.PAT[:] = [1, 1, 1, 0, 1, 0, 0, 1]        # the calibration pattern (P0)
    tag = "m%g_dv%g_T%g_H%d" % (M, DV * 1000, T, H)
    tzr, tzq = [], []
    nb = 4
    for ph in ("rise", "ret"):
        lst = tzr if ph == "rise" else tzq
        for k in range(1, nb + 1):
            padr = tzr + [bt.TZ_ANCH] * (nb - len(tzr))
            padq = tzq + [bt.TZ_ANCH] * (nb - len(tzq))
            lines, S = bt.deck(M, T, H, DV, l_nh=L, total_um=W,
                               tzr=padr, tzq=padq, probe=(ph, k))
            # PRE-REGISTERED WINDOW AMENDMENT: 2.6x -> 4.0x
            base = (S["c"][k] if ph == "rise" else S["r"][k])
            tend = base + 4.0 * bt.TZ_ANCH * math.sqrt(L / bt.L_REF)
            lines = [(".tran %gp %gp 0 %gp" % (S["pstep"], tend, S["mstep"])
                      if l.startswith(".tran") else l) for l in lines]
            fn = "p_%s_%s%d.cir" % (tag, ph, k)
            p, msg = bt.run(fn, lines)
            print("  probe %s%d %s" % (ph, k, msg), flush=True)
            if p is None:
                return 1
            hdr, rows = bt.read_prn(p + ".prn")
            t0 = S["c"][k] if ph == "rise" else S["r"][k]
            z, pk = bt.zero_after_peak(hdr, rows, "I(L%d)" % k, t0)
            if z is None:
                print("  probe %s%d NO ZERO (window 4.0x)" % (ph, k))
                json.dump(dict(L=L, W=W, T=T, vgh=VGH_NEW, error="NO ZERO %s%d" % (ph, k)),
                          open(os.path.join(sub, "SEQA6.json"), "w"), indent=1)
                return 1
            lst.append(z - t0)
            print("    %s%d t_zcs = %.4f ps (Ipk %.2f uA)"
                  % (ph, k, lst[-1], pk * 1e6), flush=True)
            os.remove(p + ".prn")                      # disk discipline
    z = dict(m=M, dv=DV, L_nH=L, W_um=W, tzr=tzr, tzq=tzq, vgh=VGH_NEW,
             T_probe=T, H_probe=H, protocol="sequential full8, window 4.0x")
    open(os.path.join(sub, "zeros_seq.json"), "w").write(json.dumps(z, indent=1))
    p, S = _row(L, W, T, z)
    if p is None:
        return 1
    d = bt.parse_mt0(p + ".mt0")
    res = dict(rise={k: d.get("IZ%d" % k, 0) * 1e6 for k in range(1, 5)},
               ret={k: d.get("IZQ%d" % k, 0) * 1e6 for k in range(1, 5)})
    worst_rise = max(abs(v) for v in res["rise"].values())
    worst_ret = max(abs(v) for v in res["ret"].values())
    out = dict(L_nH=L, W_um=W, T_ps=T, H=H, dv=DV, vgh=VGH_NEW,
               protocol="COMMITTED sequential full-8 probe at own T "
                        "(banktank A7), window 4.0x (pre-registered), "
                        "zeros applied to a P0 row, residuals read from the row",
               zeros=z, residual_uA=res,
               worst_rise_uA=round(worst_rise, 4),
               worst_return_uA=round(worst_ret, 4),
               A6_pass=bool(max(worst_rise, worst_ret) <= 1.0),
               committed_reference_VGH1p5=dict(
                   T145_worst_return_uA=1.4023, T140_worst_return_uA=2.9486,
                   source="qal/eye/p2 A6_VS_BEAT"))
    json.dump(out, open(os.path.join(sub, "SEQA6.json"), "w"), indent=1)
    print(json.dumps({k: out[k] for k in ("T_ps", "worst_rise_uA",
                                          "worst_return_uA", "A6_pass")}))
    return 0


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "warmone":
        sys.exit(cmd_warmone(a[1], a[2], float(a[3])))
    if a[0] == "ic1":
        sys.exit(cmd_ic1())
    if a[0] == "ic2":
        sys.exit(cmd_ic2())
    if a[0] == "lane":
        sys.exit(cmd_lane(float(a[1]), float(a[2]), float(a[3]), a[4]))
    if a[0] == "extract":
        L, W, T = float(a[1]), float(a[2]), float(a[3])
        pats = [x for x in a[4:]] or ["P0", "P1", "P2"]
        sys.exit(cmd_extract(L, W, T, pats))
    if a[0] == "seqprobe":
        sys.exit(cmd_seqprobe(float(a[1]), float(a[2]), float(a[3])))
    print("unknown subcommand")
    sys.exit(2)
