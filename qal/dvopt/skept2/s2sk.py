#!/usr/bin/env python3
"""SKEPTIC re-run, sk-path.  Thin wrapper over qal/skept/sk.py, which is an
INDEPENDENTLY WRITTEN deck generator + waveform-only extractor (it deliberately does
not import lsw.py).  Two things this buys that the lsw path cannot:

  1. CROSS-HARNESS resolution check.  sk's timestep ladder is ~1.8x finer than lsw's
     (sk mstep = min(0.10, pi*sqrt(LC)/1500); lsw mstep = min(0.25, t_est/1000)), so
     agreement at the same (dV, L, W) bounds the numerical resolution of the grid --
     which is what decides whether a 2-4% optimum margin is real.
  2. PER-CELL policing.  sk's hop deck prints V(o0)..V(o7); lsw's prints only
     V(o0),V(o1) and the committed settle times are taken on those two
     representatives.  A fast point that settles on average and fails one cell has
     failed, so all eight are needed.

Rebound: sk.HERE -> here, sk.ENV -> MY OWN cache, sk.VGH -> max(1.5,dV) (amendment P1).

usage: s2sk.py pt <tag> <L> <W> <dV> [tail_ps] [kind] [cl_fF]
"""
import json, os, sys, time

sys.path.insert(0, "/usr/local/src/stat-sim/qal/skept")
import sk                                                            # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = ("/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6"
         "/scratchpad/vae_cache_sk2b")
sk.HERE = HERE
sk.ENV = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS", PYMS_VAE_CACHE=CACHE)
ROWD = os.path.join(HERE, "skd")


def percell_times(prn, vbend, vbpk):
    """(b)(c) PER-CELL settling times off the raw waveform, all eight cells, three
    reference frames -- and the point of the exercise is that they differ:

      t_out90_final  time from switch CLOSE at which the cell is within 10% of VBEND
                     of its FINAL value and stays there                 (per cell)
      t_out90_inst   same but against the INSTANTANEOUS rail            (per cell)
      t_rail90       time from close at which V(bkb) reaches 0.9*VBEND and stays
      t_settle_after_rail = t_out90_final - t_rail90
                     the only quantity in the set that is a genuine POST-ARRIVAL
                     settle interval, i.e. the thing the floor curve claims to be.
    """
    w = sk.W(prn)
    ib = w.col("V(BKB)")
    oc = [w.col("V(o%d)" % i) for i in range(sk.MGATE)]
    tol = 0.10 * vbend
    per_f, per_i = {}, {}
    for i in range(sk.MGATE):
        tgt = 0.0 if i in sk.HI else vbend
        gf = None
        for k in range(len(w.t)):
            if w.t[k] < sk.T0:
                continue
            gf = (w.t[k] if gf is None else gf) if abs(w.rows[k][oc[i]] - tgt) <= tol else None
        per_f["o%d" % i] = None if gf is None else gf - sk.T0
        gi = None
        for k in range(len(w.t)):
            if w.t[k] < sk.T0 or w.rows[k][ib] < 0.05:
                continue
            v, vb = w.rows[k][oc[i]], w.rows[k][ib]
            s = (1.0 - v / vb) if i in sk.HI else (v / vb)
            gi = (w.t[k] if gi is None else gi) if s >= 0.90 else None
        per_i["o%d" % i] = None if gi is None else gi - sk.T0
    # rail arrival: LAST entry into the 0.9*VBEND band (so an overshoot-then-decay
    # rail is not credited with arriving early on the way down)
    gr = None
    for k in range(len(w.t)):
        if w.t[k] < sk.T0:
            continue
        gr = (w.t[k] if gr is None else gr) if w.rows[k][ib] >= 0.90 * vbend else None
    t_rail = None if gr is None else gr - sk.T0
    fin = [v for v in per_f.values() if v is not None]
    return dict(percell_t_out90_final=per_f, percell_t_out90_inst=per_i,
                t_rail90_lastentry_ps=t_rail,
                t_out90_final_max_ps=(max(fin) if len(fin) == sk.MGATE else None),
                t_out90_final_min_ps=(min(fin) if len(fin) == sk.MGATE else None),
                percell_spread_pct=(100.0 * (max(fin) - min(fin)) / max(fin)
                                    if len(fin) == sk.MGATE and max(fin) else None),
                t_settle_after_rail_ps=((max(fin) - t_rail)
                                        if len(fin) == sk.MGATE and t_rail else None),
                VBPK_over_VBEND=vbpk / vbend if vbend else None)


def run_pt(tag, L, W, dv, tail=500.0, kind="inv", cl=2.0):
    sk.VGH = max(1.5, dv)
    t0 = time.monotonic()
    lp, msg = sk.run("p_%s.cir" % tag, sk.probe(L, W, dv, kind=kind, cl=cl))
    print("  probe:", msg)
    if lp is None:
        return dict(tag=tag, error=msg)
    tz, ipk, tipk = sk.zero_of(lp + ".prn")
    if tz is None:
        return dict(tag=tag, error="no current zero after the peak")
    print("  true zero %.4f ps -> t_hop %.4f ps, Ipk %.2f uA" % (tz, tz - sk.T0, ipk))
    lines, meta = sk.hop(L, W, dv, tz - sk.T0, tail=tail, kind=kind, cl=cl)
    hp, msg = sk.run("h_%s.cir" % tag, lines, timeout=1200)
    print("  hop:", msg)
    if hp is None:
        return dict(tag=tag, error=msg)
    r = sk.extract_hop(hp + ".prn", meta, L, W, dv)
    r.update(tag=tag, cell_kind=kind, cl_fF=cl, tail_ps=tail, VGH=sk.VGH,
             probe_Ipk_uA=ipk, wall_s=round(time.monotonic() - t0, 1))
    try:
        r.update(percell_times(hp + ".prn", r["VBEND"], r["VBPK"]))
    except Exception as e:                                           # noqa
        r["percell_error"] = repr(e)
    # rail drain, PRINTED node, independent of the derived VA_open
    w = sk.W(hp + ".prn")
    r["VA_open_printed"] = w.at("V(bka)", meta["t_open"])
    r["VA_open_derived_minus_printed_mV"] = 1000.0 * (r["VA_open"] - r["VA_open_printed"])
    r["C2_abs"] = "PASS" if r["VA_open"] <= 0.1478 else "FAIL"
    r["C3_abs"] = "PASS" if r["VBEND"] >= 0.60 else "FAIL"
    r["s_end_min"] = min(r["s_end"].values())
    os.makedirs(ROWD, exist_ok=True)
    json.dump(r, open(os.path.join(ROWD, "%s.json" % tag), "w"), indent=1)
    print("  VBEND %.6f VBPK %.6f (ratio %.4f) VA_open derived %+.6f printed %+.6f "
          "(d %+.3f mV)" % (r["VBEND"], r["VBPK"], r["VBPK"] / r["VBEND"],
                            r["VA_open"], r["VA_open_printed"],
                            r["VA_open_derived_minus_printed_mV"]))
    print("  s_end all 8: %s  min %.3f%%"
          % (" ".join("%.2f" % v for k, v in sorted(r["s_end"].items())), r["s_end_min"]))
    print("  per-cell t_out90(final) : %s"
          % {k: (None if v is None else round(v, 2))
             for k, v in sorted(r.get("percell_t_out90_final", {}).items())})
    print("  t_rail90(last entry) %s  t_out90_final max %s  -> POST-ARRIVAL settle %s ps"
          % (r.get("t_rail90_lastentry_ps"), r.get("t_out90_final_max_ps"),
             r.get("t_settle_after_rail_ps")))
    print("  t_hop %.4f  t_valid80 %s t_valid90 %s t_settle90 %s"
          % (r["t_hop_ps"], r["t_valid80_ps"], r["t_valid90_ps"], r["t_settle90_ps"]))
    return r


def merge():
    rows = {}
    if os.path.isdir(ROWD):
        for fn in sorted(os.listdir(ROWD)):
            if fn.endswith(".json"):
                r = json.load(open(os.path.join(ROWD, fn)))
                rows[r["tag"]] = r
    json.dump(rows, open(os.path.join(HERE, "skrows.json"), "w"), indent=1)
    return rows


if __name__ == "__main__":
    c = sys.argv[1]
    if c == "pt":
        a = sys.argv
        run_pt(a[2], float(a[3]), float(a[4]), float(a[5]),
               float(a[6]) if len(a) > 6 else 500.0,
               a[7] if len(a) > 7 else "inv",
               float(a[8]) if len(a) > 8 else 2.0)
    elif c == "merge":
        print("merged %d" % len(merge()))
