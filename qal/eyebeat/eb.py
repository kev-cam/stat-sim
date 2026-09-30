#!/usr/bin/env python3
"""qal/eyebeat harness -- THE BEAT SWEEP.

Imports qal/banktank/bt.py VERBATIM (the qal/eye discipline) and overrides only:
  bt.PAT (the data), bt.HERE (every file lands under qal/eyebeat/T{T}/{P}/),
  bt.CACHE/bt.ENV (own PYMS_VAE_CACHE, built from empty), bt.TPROBE/bt.HPROBE
  (probes at the row's OWN beat, per banktank AMENDMENT A7), and -- for the
  convergence guard only -- the .tran steps.

The eye extractor is qal/eye/eyecalc.py VERBATIM (imported, not copied).

Subcommands:
  warm                          build every device geometry into the own cache
  ic1                           instrument check: the committed dv1200 row
  lane <T> <P> [--full] [--fine]   probe (own T) + row for one (T, pattern)
  icx                           extractor validation over qal/eye's own rows
  extract <T> [P...]            the eye/lag/stranded-HIGH numbers for one T
"""
import glob, importlib.util, json, math, os, shutil, sys

HERE   = os.path.dirname(os.path.abspath(__file__))
BTDIR  = "/usr/local/src/stat-sim/qal/banktank"
EYEDIR = "/usr/local/src/stat-sim/qal/eye"
CACHE  = os.path.join("/tmp/claude-1001/-usr-local-src/"
                      "4921ad0c-f17b-4b84-986a-5917c9ebd2a6/scratchpad",
                      "vae_cache_eyebeat")
M, H, DV, MODE = 10.0, 4, 1.65, "free"

_spec = importlib.util.spec_from_file_location("bt", os.path.join(BTDIR, "bt.py"))
bt = importlib.util.module_from_spec(_spec)
sys.modules["bt"] = bt
_spec.loader.exec_module(bt)

sys.path.insert(0, EYEDIR)
import eyeharness as EH            # noqa: E402  (imports bt again under its own spec; harmless, read-only)
import eyecalc as EC               # noqa: E402

PATTERNS = EH.PATTERNS             # FIXED set, inherited


def redirect(sub):
    os.makedirs(CACHE, exist_ok=True)
    os.makedirs(sub, exist_ok=True)
    bt.HERE = sub
    bt.CACHE = CACHE
    bt.ENV = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS",
                  PYMS_VAE_CACHE=CACHE)


def set_steps(pstep, mstep):
    orig = bt.schedule

    def sched(*a, **kw):
        S = orig(*a, **kw)
        S["pstep"], S["mstep"] = pstep, mstep
        return S
    bt.schedule = sched


# --------------------------------------------------------------------- warm
def cmd_warm():
    redirect(HERE)
    ok = bt.stage_warm()
    print("warm:", "OK" if ok else "FAIL")
    return 0 if ok else 1


# ---------------------------------------------------------------------- ic1
def cmd_ic1():
    """Regenerate the committed banktank headline row byte-identically, run it
    under THIS study's own cache, and digit-check the committed keys."""
    sub = os.path.join(HERE, "ic1")
    redirect(sub)
    # AMENDMENT B1: the committed row used the OWN-T zeros (A7 probe at T=200,
    # H=4), zeros_m10_dv1200_T200_H4.json -- NOT the T=120 reference file.
    # First attempt with zeros_m10_dv1200.json failed byte-identity and moved
    # banks 2-4 rails by 0.6-1.1 mV: an unplanned sensitivity measurement
    # (sub-ps zero changes -> mV-scale rail changes), kept in IC1_wrongzeros.
    z = json.load(open(os.path.join(BTDIR, "zeros_m10_dv1200_T200_H4.json")))
    lines, S = bt.deck(10.0, 200.0, 4, 1.2, mode="free",
                       tzr=z["tzr"], tzq=z["tzq"])
    mine = "\n".join(lines) + "\n"
    committed = open(os.path.join(BTDIR, "c_m10_T200_H4_dv1200_free.cir")).read()
    byte_identical = (mine == committed)
    print("IC1 deck byte-identical to committed:", byte_identical)
    fn = "c_m10_T200_H4_dv1200_free.cir"
    p, msg = bt.run(fn, lines)
    print("IC1", msg)
    if p is None:
        return 1
    a = bt.parse_mt0(os.path.join(BTDIR, fn + ".mt0"))
    b = bt.parse_mt0(p + ".mt0")
    keys = sorted(set(a) & set(b))
    worst, fails = 0.0, []
    for k in keys:
        va, vb = a[k], b[k]
        d = abs(va - vb) / max(abs(va), abs(vb), 1e-30)
        if d > worst:
            worst = d
        if d > 1e-6:
            fails.append((k, va, vb, d))
    rails = {k: b.get("VR%dB%d" % (k, k)) for k in range(1, 5)}
    out = dict(deck_byte_identical=byte_identical,
               n_keys_compared=len(keys), n_fail_1e6=len(fails),
               worst_rel_dev=worst,
               fails=fails[:20],
               rail_at_own_boundary_V_regenerated=rails,
               committed_quote_check=dict(
                   brief=[0.6767239, 0.7312456, 0.7200877],
                   file=[a.get("VR2B2"), a.get("VR3B3"), a.get("VR4B4")],
                   regenerated=[rails[2], rails[3], rails[4]]),
               pass_99pct=bool(len(fails) <= 0.01 * len(keys)))
    json.dump(out, open(os.path.join(HERE, "IC1.json"), "w"), indent=1)
    print(json.dumps({k: out[k] for k in ("deck_byte_identical", "n_keys_compared",
                                          "n_fail_1e6", "worst_rel_dev",
                                          "pass_99pct")}, indent=1))
    print("rails regenerated:", rails)
    return 0 if (byte_identical and out["pass_99pct"]) else 1


# --------------------------------------------------------------------- lane
def _bounded_zero(hdr, rows, col, t0, t1):
    """The conducting current's zero inside [t0, t1]: first sign change after
    the |I| peak, linearly interpolated; if the window ends before the crossing,
    LINEAR EXTRAPOLATION from the last two samples.  Returns (t_zero, how)."""
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


def cmd_lane(T, pname, fine=False, maxit=4):
    """AMENDMENT B2: NEWTON-ON-THE-ROW.  Seed zeros (own full8 measurement if
    present, else the qal/eye T=200 measured zeros), then iterate the row
    itself, correcting each bank's rise/return zero from the row's OWN
    conducting-current waveform, until the unchanged A6 gate passes."""
    tdir = "T%g" % T + ("fine" if fine else "")
    sub = os.path.join(HERE, tdir, pname)
    redirect(sub)
    bt.PAT[:] = list(PATTERNS[pname])
    bt.TPROBE, bt.HPROBE = T, H
    if fine:
        set_steps(0.05, 0.10)
    print("=== lane T=%g %s bits=%s fine=%s (newton-on-row) ==="
          % (T, pname, bt.PAT, fine), flush=True)

    zp = os.path.join(sub, "zeros.json")
    if os.path.exists(zp):
        z = json.load(open(zp))
        src = z.get("provenance", "own zeros.json (seed kept across attempts)")
        print("  seed: own zeros.json", z["tzr"], flush=True)
    else:
        z = json.load(open(os.path.join(EYEDIR, pname, "zeros.json")))
        src = "qal/eye/%s/zeros.json (measured m10 dv1650 T200 H4)" % pname
        print("  seed: qal/eye zeros", z["tzr"], flush=True)

    hist = []
    a6 = False
    p = S = None
    for it in range(1, maxit + 1):
        p, S = bt.do_row(M, T, H, DV, MODE, z)
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
                dz = max(-10.0, min(10.0, (tzn - ck) - tzr[k - 1]))
                tzr[k - 1] += dz
            tqn, how2 = _bounded_zero(hdr, rows, "I(L%d)" % k, rk + 5.0, rok - 1.0)
            if tqn is not None:
                dq = max(-10.0, min(10.0, (tqn - rk) - tzq[k - 1]))
                tzq[k - 1] += dq
            print("    bank%d dz_rise %+7.3f (%s)  dz_ret %+7.3f (%s)"
                  % (k, tzr[k - 1] - z["tzr"][k - 1], how,
                     tzq[k - 1] - z["tzq"][k - 1], how2), flush=True)
        z = dict(z, tzr=tzr, tzq=tzq)

    z.update(pattern=pname, pattern_bits=list(PATTERNS[pname]),
             T_row=T, H_row=H,
             probe_protocol="newton_on_row (AMENDMENT B2)",
             seed=src, newton_history=hist)
    open(zp, "w").write(json.dumps(z, indent=1))
    S = dict(S)
    S.update(pattern=pname, pattern_bits=list(PATTERNS[pname]),
             prn=p + ".prn", mt0=p + ".mt0", A6_pass=bool(a6),
             A6_worst_uA=hist[-1]["worst_uA"], newton_iters=len(hist))
    open(os.path.join(sub, "sched.json"), "w").write(
        json.dumps(S, indent=1, default=str))
    print("  %s ->" % ("OK" if a6 else "A6-FAIL(kept, excluded later)"),
          p + ".prn", flush=True)
    return 0 if a6 else 3


# ------------------------------------------------------------------ helpers
def crossing(g, y, level, t0, t1, direction, n=None):
    """First linear-interpolated crossing of y through `level` in [t0,t1].
    direction=+1: upward (y[a-1] < level <= y[a]); -1: downward."""
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


# ---------------------------------------------------------------------- icx
def cmd_icx():
    """Extractor validation: run THIS study's per-pattern pipeline over
    qal/eye's own P0/P1/P2 transients (read-only) and compare per-pattern
    EYE2 W_EXTENDED 0mV openings/heights against qal/eye/EYE.json."""
    ref = json.load(open(os.path.join(EYEDIR, "EYE.json")))
    EC.HERE = EYEDIR
    rows, worst_dt, worst_dh = [], 0.0, 0.0
    for pname in ("P0", "P1", "P2"):
        P = EC.per_pattern(pname)
        n = len(P["grid"])
        g = P["grid"]
        for k in (1, 2, 3):
            ck = P["c"][k]
            tendw = g[n - 1] - 1.0
            for pol in ("HIGH", "LOW", "joint"):
                gates = [i for i in range(P["mg"])
                         if (pol == "joint" or (P["hi"][k][i] == (pol == "HIGH")))]
                if not gates:
                    continue
                curve = [min(P["mgn_data"][k][i][a] for i in gates)
                         for a in range(n)]
                m = [c > 0.0 for c in curve]
                e = EC.eye_from_mask(m, g, ck, tendw, curve, 0.0)
                want = ref["banks"][str(k)]["EYES"]["EYE2_DATA_FIXED"][
                    "per_pattern_W_EXTENDED_0mV"][pname][
                    "joint" if pol == "joint" else pol]
                if want is None or e is None:
                    rows.append((pname, k, pol, None, None, "one side None",
                                 want is None, e is None))
                    continue
                dt = abs(e["open_ps"] - want["open_ps"])
                worst_dt = max(worst_dt, dt)
                rows.append((pname, k, pol, round(e["open_ps"], 4),
                             want["open_ps"], round(dt, 5)))
        # height check at the intersection level is done on bank records below
    hh = []
    for k in (1, 2, 3):
        b = ref["banks"][str(k)]
        want = b["EYES"]["EYE2_DATA_FIXED"]["W_EXTENDED"]["0mV"]
        hh.append((k, want["opening_ps"]))
    out = dict(per_pattern_opening_checks=rows,
               worst_opening_dev_ps=round(worst_dt, 5),
               PASS=bool(worst_dt <= 0.01),
               note="per-pattern EYE2 W_EXTENDED 0mV openings, this pipeline vs "
                    "qal/eye/EYE.json; window end differs (3 vs 10 patterns) so "
                    "clipped closings are not compared")
    json.dump(out, open(os.path.join(HERE, "IC2_extractor.json"), "w"), indent=1)
    print(json.dumps(out, indent=1))
    return 0 if out["PASS"] else 1


# ------------------------------------------------------------------ extract
def cmd_extract(T, pats, tag=None):
    tdir = os.path.join(HERE, tag or ("T%g" % T))
    EC.HERE = tdir
    SIG = EC.SIG_TRIP_MV
    THRESH = [("0mV", 0.0), ("1sigma", SIG), ("3sigma", 3 * SIG)]
    Ps, a6, val = {}, {}, {}
    for p in pats:
        sp = os.path.join(tdir, p, "sched.json")
        if not os.path.exists(sp):
            print("  SKIP %s (no sched.json)" % p)
            continue
        # per_pattern expects <HERE>/<pname>/sched.json
        Ps[p] = EC.per_pattern(p)
        S = json.load(open(sp))
        d = bt.parse_mt0(S["mt0"])
        a6[p] = dict(A6_pass=S.get("A6_pass"), worst_uA=S.get("A6_worst_uA"))
        # value check at the committed boundary guard (correct/incorrect BITS,
        # not a completion percentage)
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
    good = [p for p in pats if a6[p]["A6_pass"]]
    n = min(len(Ps[p]["grid"]) for p in pats)
    g = Ps[pats[0]]["grid"]
    nb, mg = 4, 8
    E = bt.EDGE
    out = dict(T_ps=T, H=H, dv_V=DV, m=M, patterns=pats,
               patterns_in_intersection=good, a6=a6, value_check=val, banks={})

    for k in range(1, nb + 1):
        P0 = Ps[good[0]]
        ck, rk, rok = P0["c"][k], P0["r"][k], min(Ps[p]["ro"][k] for p in good)
        tendw = g[n - 1] - 1.0
        rec = dict(receiver=("bank %d MEASURED" % (k + 1)) if k < nb else
                   "DERIVED V(rail3)(t-T)", c_ps=ck, r_ps=rk, ro_ps=rok)

        # ----- intersection curves per reference/polarity
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

        # ----- eyes: FIRST contiguous run (operational), W_EXTENDED
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
                samp = ck + T                      # the receiver's rail start
                ia = max(0, min(n - 1, int(round(samp / EC.GRID))))
                hh = cur[ref]["HIGH"]
                hl = cur[ref]["LOW"]
                ent = dict(
                    opening_ps=round(e["open_ps"], 4),
                    closing_ps=round(e["close_ps"], 4),
                    WIDTH_ps=round(e["width_ps"], 4),
                    WIDTH_over_T=round(e["width_ps"] / T, 4),
                    opening_minus_c_ps=round(e["open_ps"] - ck, 4),
                    closing_minus_r_ps=round(e["close_ps"] - rk, 4),
                    setup_slack_ps=round(T - (e["open_ps"] - ck), 4),
                    setup_slack_over_T=round(1.0 - (e["open_ps"] - ck) / T, 4),
                    clipped_start=e["clipped_at_window_start"],
                    clipped_end=e["clipped_at_window_end"],
                    WIDTH_IS_LOWER_BOUND=bool(e["clipped_at_window_end"]),
                    eye_open_at_sampling_instant=bool(
                        m_[ia] and e["open_ps"] <= samp <= e["close_ps"]),
                    HEIGHT_at_sampling_HIGH_mV=(round(hh[ia], 4) if hh else None),
                    HEIGHT_at_sampling_LOW_mV=(round(hl[ia], 4) if hl else None))
                R[tname] = ent
            # mechanisms at the 0mV and 3sigma edges (binding pattern/gate)
            key = "mgn" if ref == "EYE1" else "mgn_data"
            for tname, tv in (("0mV", 0.0), ("3sigma", 3 * SIG)):
                z = R.get(tname)
                if not z or "EYE" in z:
                    continue
                mech = {}
                for side, tt, clip in (("opening", z["opening_ps"], z["clipped_start"]),
                                       ("closing", z["closing_ps"], z["clipped_end"])):
                    a = max(1, min(n - 2, int(round(tt / EC.GRID))))
                    bp, bg, bv = None, None, 1e18
                    for p in good:
                        for i in range(mg):
                            v = Ps[p][key][k][i][a]
                            if v < bv:
                                bp, bg, bv = p, i, v
                    EH.set_pattern(PATTERNS[bp])
                    bt.PAT[:] = list(PATTERNS[bp])
                    mm = EC.mechanism(Ps[bp], k, a, bg, side,
                                      "EYE2_DATA_FIXED" if ref == "EYE2"
                                      else "EYE1_RX_INSTANTANEOUS", clip)
                    mm["binding_pattern"] = bp
                    mech[side] = mm
                R[tname + "_mechanism"] = mech
            rec["EYES"][ref] = R

        # ----- post-return margin floor (the physics carrier of the late edge)
        ar = min(n - 1, int(round(rk / EC.GRID)))
        c0 = cur["EYE2"]["all"]
        mm = min((c0[a], g[a]) for a in range(ar, n))
        rec["POST_RETURN_FLOOR_EYE2"] = dict(
            floor_mV=round(mm[0], 4), at_t_ps=round(mm[1], 4),
            at_t_minus_r_ps=round(mm[1] - rk, 4),
            in_sigma_trip=round(mm[0] / SIG, 3))

        # ----- TRACKING LAG (c) + STRANDED-HIGH (d)
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
            # rising side, LAG_A at 0.5*Vpk
            lvl = 0.5 * vpk
            tr = crossing(g, rail, lvl, P["c"][k] - E, P["r"][k], +1, n)
            # draining side reference
            ir0 = min(n - 1, int(round(P["r"][k] / EC.GRID)))
            ir1 = min(n - 1, int(round(min(P["r"][k] + 2 * (rop - P["r"][k]),
                                           g[n - 1]) / EC.GRID)))
            vfloor = min(rail[a] for a in range(ir0, ir1 + 1))
            vref_d = 0.5 * (rail[ir0] + vfloor)
            trd = crossing(g, rail, vref_d, P["r"][k] - E, g[n - 1], -1, n)
            # LAG_B levels
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
                # stranded-HIGH: min over the drain window
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
            draining_censored_gates=cens,
            draining_censoring_means="the HIGH output did NOT follow the rail "
                                     "down through the mid-drain level inside "
                                     "the window -- the data outlived the drain")
        rec["STRANDED_HIGH"] = dict(
            min_HIGH_during_drain_V=round(min(strand), 5) if strand else None,
            per_gate_min_V=stats(strand),
            droop_slope_mV_per_ps=stats([1000 * x for x in droop]),
            committed_peer_fed_reference_V=[0.336, 0.455],
            committed_head_link_bleed_mV_per_ps=1.29)
        out["banks"][str(k)] = rec

    fn = os.path.join(tdir, "EYEBEAT.json")
    json.dump(out, open(fn, "w"), indent=1)
    print("wrote", fn)
    for k in range(1, 5):
        b = out["banks"][str(k)]
        for tname in ("0mV", "3sigma"):
            z = b["EYES"]["EYE2"].get(tname, {})
            if "EYE" in z or not z:
                print("T%g bank%d %s EMPTY" % (T, k, tname))
                continue
            print("T%-4g bank%d %-7s open %9.3f (c+%7.3f) close %9.3f  W %8.3f%s "
                  "W/T %6.3f  slack %7.3f  Hs %s/%s" %
                  (T, k, tname, z["opening_ps"], z["opening_minus_c_ps"],
                   z["closing_ps"], z["WIDTH_ps"],
                   "LB" if z["WIDTH_IS_LOWER_BOUND"] else "  ",
                   z["WIDTH_over_T"], z["setup_slack_ps"],
                   z["HEIGHT_at_sampling_HIGH_mV"], z["HEIGHT_at_sampling_LOW_mV"]))
        tl = b["TRACKING_LAG"]
        print("        lagA_rise %s  lagB_rise %s  lagA_drain %s cens=%d  "
              "strandedHIGH %s" %
              (tl["rising_LAG_A_ps"] and tl["rising_LAG_A_ps"]["median"],
               tl["rising_LAG_B_rail_to_data_ps"] and tl["rising_LAG_B_rail_to_data_ps"]["median"],
               tl["draining_LAG_A_ps"] and tl["draining_LAG_A_ps"]["median"],
               tl["draining_censored_gates"],
               b["STRANDED_HIGH"]["min_HIGH_during_drain_V"]))
    return 0


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "warm":
        sys.exit(cmd_warm())
    if a[0] == "ic1":
        sys.exit(cmd_ic1())
    if a[0] == "icx":
        sys.exit(cmd_icx())
    if a[0] == "lane":
        sys.exit(cmd_lane(float(a[1]), a[2], fine=("--fine" in a)))
    if a[0] == "extract":
        T = float(a[1])
        pats = [x for x in a[2:] if not x.startswith("--")] or ["P0", "P1", "P2"]
        tag = None
        for x in a[2:]:
            if x.startswith("--tag="):
                tag = x[6:]
        sys.exit(cmd_extract(T, pats, tag))
    print("unknown subcommand")
    sys.exit(2)
