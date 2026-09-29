#!/usr/bin/env python3
"""SKEPTIC re-run, lsw-path.  THIN wrapper over qal/lsweep/lsw.py, IMPORTED not
copied, exactly as dvopt/dvo.py is -- so a reproduction failure can only be a real
difference, never a transcription difference.

Rebound and nothing else:
  lsw.HERE  -> this directory (skept2/)        outputs land here
  lsw.ENV   -> MY OWN PYMS_VAE_CACHE (vae_cache_sk2b)
  lsw.VGH   -> max(1.5, dV)                    amendment P1, same rule as dvo.py
  lsw.save_row -> per-point file (no read-modify-write race)
  lsw.calib_path -> my own calib first, then dvopt's, then lsweep's

Stages: warm | calib <dv> | ga | pt <tag> <L> <W> <dV> | merge | show
"""
import json, math, os, sys, time

sys.path.insert(0, "/usr/local/src/stat-sim/qal/lsweep")
import lsw                                                          # noqa: E402
import reextract                                                    # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
DVOPT = os.path.normpath(os.path.join(HERE, ".."))
LSWEEP = "/usr/local/src/stat-sim/qal/lsweep"
CACHE = ("/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6"
         "/scratchpad/vae_cache_sk2b")
lsw.HERE = HERE
lsw.CACHE = CACHE
lsw.ENV = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS",
               PYMS_VAE_CACHE=CACHE)
VGH_BASE = 1.5
ROWD = os.path.join(HERE, "rowd")

_real_calib = lsw.calib_path


def calib_path(dv):
    if abs(dv - 1.0) < 1e-12:
        return _real_calib(dv)
    fn = "calib_dv%03d.cir.prn" % int(round(dv * 100))
    for d in (HERE, DVOPT, LSWEEP):
        p = os.path.join(d, fn)
        if os.path.exists(p):
            return p
    return os.path.join(HERE, fn)


lsw.calib_path = calib_path


def save_row(row):
    os.makedirs(ROWD, exist_ok=True)
    json.dump(row, open(os.path.join(ROWD, "%s.json" % row["tag"]), "w"), indent=1)


lsw.save_row = save_row


def merge():
    rows = {}
    if os.path.isdir(ROWD):
        for fn in sorted(os.listdir(ROWD)):
            if fn.endswith(".json"):
                r = json.load(open(os.path.join(ROWD, fn)))
                rows[r["tag"]] = r
    json.dump(rows, open(os.path.join(HERE, "rows.json"), "w"), indent=1)
    return rows


def rail_from_prn(tag, t_open, dv, ca=lsw.CA_FF):
    """(b) INDEPENDENT rail-drain check.  VA_open in the committed extractor is
    DERIVED: dV - Q_through_L/CA.  V(bka) is a PRINTED NODE.  They must agree."""
    prn = os.path.join(HERE, "h_%s.cir.prn" % tag)
    if not os.path.exists(prn):
        return None
    hdr, rows = lsw.read_prn(prn)
    ia = hdr.index("V(BKA)")
    ts = [r[1] * 1e12 for r in rows]
    def at(c, t):
        for k in range(1, len(ts)):
            if ts[k] >= t:
                f = 0.0 if ts[k] == ts[k - 1] else (t - ts[k - 1]) / (ts[k] - ts[k - 1])
                return rows[k - 1][c] + f * (rows[k][c] - rows[k - 1][c])
        return rows[-1][c]
    return dict(VA_open_printed=at(ia, t_open),
                VA_min_printed=min(r[ia] for r in rows),
                VA_end_printed=rows[-1][ia])


def point(tag, L, W, dv, tail=lsw.TAIL_REF, vgh_force=None):
    vgh = max(VGH_BASE, dv) if vgh_force is None else vgh_force
    lsw.VGH = vgh
    t0 = time.monotonic()
    r = lsw.point(tag, L, W, lsw.RS_REF, lsw.EDGE_REF, tail, True, dv)
    r["VGH"] = vgh
    r["VGH_FORCED"] = vgh_force is not None
    r["wall_s"] = round(time.monotonic() - t0, 1)
    prn = os.path.join(HERE, "h_%s.cir.prn" % tag)
    if "error" not in r and os.path.exists(prn):
        try:
            r.update(reextract.settle_times(prn, r["VBEND"]))
        except Exception as e:                                      # noqa
            r["settle_error"] = repr(e)
        ts, tv = r.get("t_settle90_ps"), r.get("t_valid90_ps")
        r["t_level_ps"] = max(r["t_hop_ps"], ts) if ts else None
        r["t_level_cons_ps"] = max(r["t_hop_ps"], ts, tv) if (ts and tv) else None
        r["C1_settle90_reached"] = "PASS" if ts else "FAIL"
        rp = rail_from_prn(tag, lsw.T0 + r["t_hop_ps"], dv)
        if rp:
            r.update(rp)
            r["VA_open_derived_minus_printed_mV"] = \
                1000.0 * (r["VA_open"] - rp["VA_open_printed"])
    va, vb = r.get("VA_open"), r.get("VBEND")
    if va is not None and vb is not None:
        r["C2_rail_drain_abs"] = "PASS" if va <= 0.1478 else "FAIL"
        r["C2_rail_drain_rel"] = "PASS" if va <= 0.1478 * dv else "FAIL"
        r["C3_swing_abs"] = "PASS" if vb >= 0.60 else "FAIL"
        r["C3_swing_rel"] = "PASS" if vb >= 0.60 * dv else "FAIL"
        f = []
        for k, nm in (("C1_settle_end", "C1_settle_end"),
                      ("C1_valid90_reached", "C1_valid90"),
                      ("C1_settle90_reached", "C1_settle90"),
                      ("C2_rail_drain_abs", "C2_drain_abs"),
                      ("C3_swing_abs", "C3_swing_abs"),
                      ("C4_instrument", "C4_instrument")):
            if r.get(k) != "PASS":
                f.append(nm)
        r["fails"] = f
        r["FUNCTIONAL"] = "YES" if not f else "NO"
        r["FUNCTIONAL_rel"] = ("YES" if not [x for x in f if x not in
                               ("C2_drain_abs", "C3_swing_abs")]
                               and r["C2_rail_drain_rel"] == "PASS"
                               and r["C3_swing_rel"] == "PASS" else "NO")
    lsw.save_row(r)
    return r


GA_REF = {"t_hop_ps": 65.49500982344826, "VBEND": 0.7138163,
          "t_valid90_ps": 123.44311400000001, "VBPK": 0.8368896,
          "VA_open": 0.1276800355763028, "IPK_uA": 971.3203,
          "E_hop_open_fJ": 14.843224450910004, "t_rail90_ps": 40.887047800000005,
          "t_settle90_ps": 115.570918, "t_level_cons_ps": 123.44311400000001}


def stage_ga():
    ok = True
    print("=== GA-1 imported extractor vs the COMMITTED swsweep mt0 (no sim) ===")
    out = lsw.extract(os.path.join(lsw.SW, "sw_tg15p_z.cir.mt0"), lsw.L_REF, 15.0,
                      lsw.TZ_REF)
    for k, ref in lsw.ANCHOR.items():
        rel = abs(out[k] - ref) / max(abs(ref), 1e-30)
        ok &= rel < 1e-6
        print("%s %-16s mine %.10g committed %.10g rel %.2e"
              % ("OK  " if rel < 1e-6 else "FAIL", k, out[k], ref, rel))
    print("=== GA-2 committed ROBUST POINT re-run HERE, MY cache (L=15 W=30 dV=1.2) ===")
    r = point("ga_L15_W30_dv120", 15.0, 30.0, 1.2)
    if "error" in r:
        print("FAIL %s" % r["error"])
        return False
    for k, ref in GA_REF.items():
        m = r.get(k)
        if m is None:
            print("FAIL %-16s MISSING" % k); ok = False; continue
        rel = abs(m - ref) / max(abs(ref), 1e-30)
        ok &= rel < 1e-6
        print("%s %-16s mine %.10g committed %.10g rel %.2e"
              % ("OK  " if rel < 1e-6 else "FAIL", k, m, ref, rel))
    print("  VA_open DERIVED %.7f vs PRINTED V(bka)@open %.7f  (delta %+.4f mV)"
          % (r["VA_open"], r["VA_open_printed"], r["VA_open_derived_minus_printed_mV"]))
    print("  gates %s  C1end %s C2abs %s C3abs %s C4 %s  wall %.0fs"
          % (r["FUNCTIONAL"], r["C1_settle_end"], r["C2_rail_drain_abs"],
             r["C3_swing_abs"], r["C4_instrument"], r["wall_s"]))
    print("GA %s" % ("PASS" if ok else "FAIL"))
    return ok


if __name__ == "__main__":
    st = sys.argv[1]
    if st == "warm":
        # widen the warmed geometry set to the INTERMEDIATE widths (d) needs
        tots = [15, 20, 24, 30, 60, 80, 90, 120, 150, 240]
        need_n, need_p = {lsw.WN}, {lsw.WP}
        for t in tots:
            w = lsw.widths(t)
            need_n |= {w["wn"], w["park"]}; need_p.add(w["wp"])
        L = lsw.head() + ["V1 a 0 0.5", "V2 b 0 0.5"]
        k = 0
        for w in sorted(need_n):
            L += ["XWN%d d%d a 0 0 sg13_lv_nmos w=%gu l=0.13u" % (k, k, w),
                  "RN%d d%d b 1k" % (k, k)]; k += 1
        for w in sorted(need_p):
            L += ["XWP%d e%d a b b sg13_lv_pmos w=%gu l=0.13u" % (k, k, w),
                  "RP%d e%d 0 1k" % (k, k)]; k += 1
        L += [".tran 1p 10p", ".print tran V(a)", ".end"]
        print("warming n=%s p=%s" % (sorted(need_n), sorted(need_p)))
        p, msg = lsw.run("warm.cir", L, timeout=3000)
        print(msg)
        sys.exit(0 if p else 1)
    elif st == "calib":
        dv = float(sys.argv[2]); lsw.VGH = max(VGH_BASE, dv)
        sys.exit(0 if lsw.stage_calib(dv) else 1)
    elif st == "ga":
        sys.exit(0 if stage_ga() else 1)
    elif st == "pt":
        tag, L, W, dv = sys.argv[2], float(sys.argv[3]), float(sys.argv[4]), float(sys.argv[5])
        r = point(tag, L, W, dv)
        print(lsw.brief(r) if "error" not in r else "%s ERROR %s" % (tag, r["error"]))
    elif st == "merge":
        print("merged %d" % len(merge()))
    elif st == "show":
        for k, r in sorted(merge().items()):
            print(lsw.brief(r))
