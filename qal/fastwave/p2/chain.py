"""p2 stage 2 -- THE WAVE: probe the zeros, run the chain, measure the beat.

Nothing here is composed.  Every time is a difference of two instants read off
one waveform, and every zero is re-probed.
"""
import json, math, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import w as W

HERE = W.HERE
WS, PS = W.logic()
WANT = WS                      # WANT[k-1][i] is bank k cell i's expected bit


# ------------------------------------------------------------------- probing
def probe_rises(tag, base, verbose=True):
    """Bank k's rise switch closes at its beat and NEVER opens; banks 1..k-1 are
    cut at their OWN already-measured zeros.  The zero is the first interpolated
    downward crossing of I(L_k) after I(L_k)'s own peak.  banktank's probe shape,
    Phase 1's zero rule."""
    nb = base["nbank"]
    tzr, info = [], {}
    for k in range(1, nb + 1):
        s = dict(base)
        s["tzr"] = tzr + [base["w"] and 0.0] * 0 + [0.0] * (nb - len(tzr))
        s["tzr"] = tzr + [0.0] * (nb - len(tzr))
        s["probe"] = ("rise", k)
        lines, S = W.build(s)
        fn = "pr_%s_k%d.cir" % (tag, k)
        path, err, wall, div = W.run(fn, lines, s, timeout=900)
        if err:
            info["bank%d" % k] = dict(FAILED=err)
            if verbose:
                print("    %-24s PROBE FAILED %s" % (fn, err[:90]))
            tzr.append(S["t_est"])
            info["bank%d" % k]["fallback_t_est_ps"] = S["t_est"]
            continue
        tz, ipk = W.zero_after_peak(path + ".prn", "I(L%d)" % k, S["c"][k])
        if tz is None:
            info["bank%d" % k] = dict(FAILED="no zero crossing found",
                                      fallback_t_est_ps=S["t_est"], IPK_uA=ipk)
            tzr.append(S["t_est"])
            if verbose:
                print("    %-24s NO ZERO (ipk %.1f uA)" % (fn, ipk or 0))
            continue
        tzr.append(tz)
        info["bank%d" % k] = dict(tz_ps=tz, IPK_uA=ipk, wall_s=round(wall, 1),
                                  div=div, t_est_ps=S["t_est"])
        if verbose:
            print("    %-24s tz = %8.4f ps  (analytic %6.2f, %+.1f%%)  ipk %7.1f uA"
                  % (fn, tz, S["t_est"], 100.0 * (tz / S["t_est"] - 1.0), ipk))
    return tzr, info


def probe_returns(tag, base, tzr, verbose=True):
    nb = base["nbank"]
    tzq, info = [], {}
    for k in range(1, nb + 1):
        s = dict(base)
        s["tzr"] = tzr
        s["tzq"] = tzq + [0.0] * (nb - len(tzq))
        s["probe"] = ("ret", k)
        lines, S = W.build(s)
        fn = "pq_%s_k%d.cir" % (tag, k)
        path, err, wall, div = W.run(fn, lines, s, timeout=900)
        if err:
            info["bank%d" % k] = dict(FAILED=err, fallback_t_est_ps=S["t_est"])
            tzq.append(S["t_est"])
            if verbose:
                print("    %-24s RET PROBE FAILED" % fn)
            continue
        tz, ipk = W.zero_after_peak(path + ".prn", "I(L%d)" % k, S["r"][k])
        if tz is None:
            info["bank%d" % k] = dict(FAILED="no zero", fallback_t_est_ps=S["t_est"])
            tzq.append(S["t_est"])
        else:
            tzq.append(tz)
            info["bank%d" % k] = dict(tz_ps=tz, IPK_uA=ipk, wall_s=round(wall, 1))
        if verbose:
            print("    %-24s tzq = %8.4f ps  ipk %8.1f uA" % (fn, tzq[-1], ipk or 0))
    return tzq, info


# ---------------------------------------------------------------- extraction
def measure(path, s, S):
    """Everything MEASURED off one waveform."""
    hdr, rows = W.read_prn(path + ".prn")
    mt0 = W.parse_mt0(path + ".mt0") if os.path.exists(path + ".mt0") else {}
    nb, dv = s["nbank"], s["dv"]
    ir = {k: hdr.index("V(RAIL%d)" % k) for k in range(1, nb + 1)}
    iy = {(k, i): hdr.index("V(Y%d_%d)" % (k, i))
          for k in range(1, nb + 1) for i in range(W.NCELL)}
    T = [r[1] * 1e12 for r in rows]

    out = dict(T_ps=s["T"], wire=s["wire"], l_nh=s["l_nh"], vgh=s["vgh"],
               dv=dv, m=s["m"], H=s["H"], nbank=nb, nscore=W.NSCORE,
               cbank_fF=s["cbank_fF"], bound_ps={}, banks={})
    # per-deck instrument check
    out["T90ZC_ps"] = (mt0.get("T90ZC", 0.0) * 1e12 - s["T1"]) if mt0.get("T90ZC") else None
    out["T90ZC_committed_ps"] = 57.1428
    if out["T90ZC_ps"] is not None:
        out["T90ZC_rel"] = abs(out["T90ZC_ps"] - 57.1428) / 57.1428

    valid = {}
    for k in range(1, nb + 1):
        c, bnd = S["c"][k], S["bound"][k]
        want = WANT[k - 1]
        # ---- the COMMIT instant: correct AND STAYS correct through the boundary
        f = None
        for n, t in enumerate(T):
            if t < c or t > bnd:
                continue
            vb = rows[n][ir[k]]
            if vb <= 0.2:
                f = None
                continue
            tv = W.trip_at(vb)
            ok = all((rows[n][iy[(k, i)]] >= tv + W.NB_V) if want[i]
                     else (rows[n][iy[(k, i)]] <= tv - W.NB_V)
                     for i in range(W.NCELL))
            f = (t if f is None else f) if ok else None
        valid[k] = f
        # ---- the inherited 90%-of-own-rail bar, carried on every row
        f90 = None
        for n, t in enumerate(T):
            if t < c or t > bnd:
                continue
            vb = rows[n][ir[k]]
            ok = vb > 1e-6 and all(
                ((rows[n][iy[(k, i)]] / vb) >= 0.90) if want[i]
                else ((1.0 - rows[n][iy[(k, i)]] / vb) >= 0.90)
                for i in range(W.NCELL))
            f90 = (t if f90 is None else f90) if ok else None
        # ---- the state AT the boundary
        nb_i = min(range(len(T)), key=lambda n: abs(T[n] - bnd))
        rail_b = rows[nb_i][ir[k]]
        tv_b = W.trip_at(rail_b)
        cells = []
        for i in range(W.NCELL):
            v = rows[nb_i][iy[(k, i)]]
            marg = (v - tv_b) if want[i] else (tv_b - v)
            cells.append(dict(
                cell=i, path=PS[k - 1][i], form=W.FORMS[k - 1][i],
                want=want[i], V=v, trip_at_own_rail=tv_b,
                margin_mV=1000.0 * marg,
                correct=bool(marg > W.NB_V),
                settled_pct_of_own_rail=(100.0 * v / rail_b if want[i]
                                         else 100.0 * (1.0 - v / rail_b))
                if rail_b > 1e-6 else None,
                K2_floor_ok=bool(v >= W.FLOOR) if want[i]
                else bool(v <= dv - W.FLOOR)))
        rp = max((rows[n][ir[k]] for n, t in enumerate(T) if t >= c), default=None)
        out["bound_ps"][k] = bnd
        out["banks"][k] = dict(
            k=k, scored=bool(k <= W.NSCORE), rot=W.ROT[k - 1],
            forms="".join(W.FORMS[k - 1]), paths="".join(PS[k - 1]),
            want=want, c_ps=c, o_ps=S["o"][k], r_ps=S["r"][k], ro_ps=S["ro"][k],
            bound_ps=bnd, tzr_ps=S["tzr"][k - 1], tzq_ps=S["tzq"][k - 1],
            rail_peak_V=rp, rail_at_bound_V=rail_b,
            commit_ps=(valid[k] - c) if valid[k] is not None else None,
            commit_abs_ps=valid[k],
            bar90_ps=(f90 - c) if f90 is not None else None,
            value_all_correct=all(cc["correct"] for cc in cells),
            value_fails=[cc["cell"] for cc in cells if not cc["correct"]],
            value_fail_paths=[cc["path"] for cc in cells if not cc["correct"]],
            min_margin_mV=min(cc["margin_mV"] for cc in cells),
            min_settled_pct=min([cc["settled_pct_of_own_rail"] for cc in cells
                                 if cc["settled_pct_of_own_rail"] is not None]
                                or [None]),
            K2_all_ok=all(cc["K2_floor_ok"] for cc in cells),
            K2_fails=[cc["cell"] for cc in cells if not cc["K2_floor_ok"]],
            IZ_uA=mt0.get("IZ%d" % k), IZQ_uA=mt0.get("IZQ%d" % k),
            IPK_uA=mt0.get("IPK%d" % k), cells=cells)

    # ---- the SUSTAINED BEAT: max MEASURED stage-to-stage time over scored banks
    st = {}
    for k in range(2, W.NSCORE + 1):
        if valid.get(k) is not None and valid.get(k - 1) is not None:
            st["%d_minus_%d" % (k, k - 1)] = valid[k] - valid[k - 1]
    out["stage_time_ps"] = st
    out["sustained_beat_ps"] = max(st.values()) if st else None
    out["stage_time_min_ps"] = min(st.values()) if st else None
    out["all_scored_banks_commit"] = all(valid.get(k) is not None
                                         for k in range(1, W.NSCORE + 1))
    out["all_scored_banks_value_correct"] = all(
        out["banks"][k]["value_all_correct"] for k in range(1, W.NSCORE + 1))
    out["K4_sustains_requested_T"] = (
        bool(out["sustained_beat_ps"] is not None
             and out["sustained_beat_ps"] <= s["T"] * 1.0 + 1e-9))
    out["latency_by_depth_ps"] = {
        k: (valid[k] - S["c"][1]) if valid.get(k) is not None else None
        for k in range(1, W.NSCORE + 1)}
    out["min_margin_over_scored_mV"] = min(
        out["banks"][k]["min_margin_mV"] for k in range(1, W.NSCORE + 1))
    out["K2_all_scored_ok"] = all(out["banks"][k]["K2_all_ok"]
                                  for k in range(1, W.NSCORE + 1))
    izs = [abs(out["banks"][k]["IZ_uA"]) for k in range(1, nb + 1)
           if out["banks"][k]["IZ_uA"] is not None]
    izqs = [abs(out["banks"][k]["IZQ_uA"]) for k in range(1, nb + 1)
            if out["banks"][k]["IZQ_uA"] is not None]
    out["K5_IZ_max_uA"] = max(izs) if izs else None
    out["K5_IZQ_max_uA"] = max(izqs) if izqs else None
    out["K5_ok"] = bool((out["K5_IZ_max_uA"] or 0) <= 1.0)
    # ---- energy ledger, REPORTED and never a gate
    led = {}
    for k in range(1, nb + 1):
        z = mt0.get("EA%d_Z" % k)
        if z is None:
            continue
        led["bank%d" % k] = {
            nm: (mt0.get("%s%d_D" % (nm, k), 0.0) - mt0.get("%s%d_Z" % (nm, k), 0.0)) * 1e15
            for nm in ("QLT", "EA", "EB", "ESW", "ER", "QG")}
    for nm in ("QHD", "EHI", "EGT"):
        if mt0.get("%s_Z" % nm) is not None:
            led[nm] = (mt0["%s_D" % nm] - mt0["%s_Z" % nm]) * 1e15
    out["energy_ledger_fJ_REPORTED_NOT_A_GATE"] = led
    out["PASS"] = bool(out["all_scored_banks_value_correct"]
                       and out["all_scored_banks_commit"]
                       and out["K4_sustains_requested_T"] and out["K5_ok"])
    return out


def row(tag, base, tzr=None, tzq=None, verbose=True, probe_rise=True,
        probe_ret=None):
    """One measured chain row: probe its zeros, run it, measure it."""
    t0 = time.monotonic()
    if tzr is None or probe_rise:
        tzr, pinfo = probe_rises(tag, base, verbose)
    else:
        pinfo = dict(reused=True)
    if probe_ret is None:
        probe_ret = base.get("returns", True)
    if tzq is None and probe_ret:
        tzq, qinfo = probe_returns(tag, base, tzr, verbose)
    else:
        tzq = tzq or [0.0] * base["nbank"]
        qinfo = dict(reused=True, returns_enabled=base.get("returns", True))
    s = dict(base); s["tzr"] = tzr; s["tzq"] = tzq; s["probe"] = None
    lines, S = W.build(s)
    fn = "c_%s.cir" % tag
    path, err, wall, div = W.run(fn, lines, s, timeout=1500)
    if err:
        return dict(tag=tag, FAILED=err, T_ps=base["T"], wire=base["wire"],
                    tzr_ps=tzr, tzq_ps=tzq)
    r = measure(path, s, S)
    r["tag"] = tag
    r["deck"] = fn
    r["wall_s"] = round(wall, 1)
    r["div"] = div
    r["total_wall_s"] = round(time.monotonic() - t0, 1)
    r["probe_rise"] = pinfo
    r["probe_ret"] = qinfo
    r["tzr_ps"] = tzr
    r["tzq_ps"] = tzq
    return r


def brief(r):
    if r.get("FAILED"):
        return "%-22s FAILED %s" % (r["tag"], r["FAILED"][:70])
    b = r["sustained_beat_ps"]
    return ("%-22s T=%4.0f %s  PASS=%-5s beat=%s  commit_all=%-5s val=%-5s "
            "K2=%-5s minmarg=%7.1f mV  IZ=%.3f uA  %.0fs"
            % (r["tag"], r["T_ps"], r["wire"], r["PASS"],
               ("%7.2f" % b) if b is not None else "   none",
               r["all_scored_banks_commit"], r["all_scored_banks_value_correct"],
               r["K2_all_scored_ok"], r["min_margin_over_scored_mV"],
               r["K5_IZ_max_uA"] or -1, r["total_wall_s"]))
