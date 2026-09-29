#!/usr/bin/env python3
"""TRACK 1c: the (dV, L, W) optimum sweep.

This file is a THIN WRAPPER.  Every deck line, every integrator, every extracted
number comes from qal/lsweep/lsw.py, IMPORTED not copied, so the instrument check
reproduces the committed rows by construction.

What is rebound, and nothing else (PRE_REGISTERED.json / protocol):
  lsw.HERE   -> this directory (outputs land here, calib curves are looked up here)
  lsw.ENV    -> own PYMS_VAE_CACHE
  lsw.VGH    -> max(1.5, dV)   [amendment P1: binds at dV=1.65 only]

Stages: warm | instr | calib <dv> | pt <tag> <L> <W> <dV> | show
"""
import json, math, os, sys, time

sys.path.insert(0, "/usr/local/src/stat-sim/qal/lsweep")
import lsw                                                        # noqa: E402
import reextract                                                  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = ("/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6"
         "/scratchpad/vae_cache_dvopt")
lsw.HERE = HERE
lsw.CACHE = CACHE
lsw.ENV = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS",
               PYMS_VAE_CACHE=CACHE)

VGH_BASE = 1.5


def set_vgh(dv):
    """amendment P1: VGH = max(1.5, dV).  At dV=1.65 the bank node would otherwise
    start above the transfer pMOS bulk (vhi = VGH) and forward-bias its
    source-bulk junction."""
    lsw.VGH = max(VGH_BASE, dv)
    return lsw.VGH


# committed dV=1.2 calib lives in lsweep; symlinking is banned by house rule, so
# point lsw at the right directory per dV instead.
_real_calib_path = lsw.calib_path


def calib_path(dv):
    if abs(dv - 1.0) < 1e-12:
        return _real_calib_path(dv)
    fn = "calib_dv%03d.cir.prn" % int(round(dv * 100))
    mine = os.path.join(HERE, fn)
    if os.path.exists(mine):
        return mine
    return os.path.join("/usr/local/src/stat-sim/qal/lsweep", fn)


lsw.calib_path = calib_path

# lsw.save_row rewrites one shared rows.json, which LOSES ROWS under the 4-way
# parallel driver (read-modify-write race; it cost the floor deck a collection pass).
# Each point therefore writes its OWN file and `merge` combines them.
ROWD = os.path.join(HERE, "rowd")


def save_row(row):
    os.makedirs(ROWD, exist_ok=True)
    json.dump(row, open(os.path.join(ROWD, "%s.json" % row["tag"]), "w"), indent=1)


lsw.save_row = save_row


def merge_rows():
    rows = {}
    if os.path.isdir(ROWD):
        for fn in sorted(os.listdir(ROWD)):
            if fn.endswith(".json"):
                r = json.load(open(os.path.join(ROWD, fn)))
                rows[r["tag"]] = r
    json.dump(rows, open(os.path.join(HERE, "rows.json"), "w"), indent=1)
    return rows


def point(tag, L, W, dv, tail=lsw.TAIL_REF, vgh_force=None):
    vgh = set_vgh(dv) if vgh_force is None else vgh_force
    lsw.VGH = vgh
    t0 = time.monotonic()
    r = lsw.point(tag, L, W, lsw.RS_REF, lsw.EDGE_REF, tail, True, dv)
    r["VGH"] = vgh
    r["VGH_AMENDED"] = bool(abs(vgh - VGH_BASE) > 1e-12)
    r["VGH_FORCED"] = vgh_force is not None
    r["wall_s"] = round(time.monotonic() - t0, 1)
    # committed reextract.py convention, imported not copied:
    #   t_settle90   -- outputs within 10% of VBEND of their FINAL value
    #   t_level_ps      = max(t_hop, t_settle90)          "settling" definition
    #   t_level_cons_ps = max(t_hop, t_settle90, t_valid90)  conservative, the
    #                     one the committed verdict is taken on
    prn = os.path.join(HERE, "h_%s.cir.prn" % tag)
    if "error" not in r and os.path.exists(prn):
        try:
            r.update(reextract.settle_times(prn, r["VBEND"]))
        except Exception as e:                                     # noqa
            r["settle_error"] = repr(e)
        ts, tv = r.get("t_settle90_ps"), r.get("t_valid90_ps")
        r["t_level_ps"] = max(r["t_hop_ps"], ts) if ts else None
        r["t_level_cons_ps"] = max(r["t_hop_ps"], ts, tv) if (ts and tv) else None
        r["C1_settle90_reached"] = "PASS" if ts else "FAIL"
    # pre-registered gate set, both forms
    va, vb = r.get("VA_open"), r.get("VBEND")
    if va is not None and vb is not None:
        r["C2_rail_drain_abs"] = "PASS" if va <= 0.1478 else "FAIL"
        r["C2_rail_drain_rel"] = "PASS" if va <= 0.1478 * dv else "FAIL"
        r["C3_swing_abs"] = "PASS" if vb >= 0.60 else "FAIL"
        r["C3_swing_rel"] = "PASS" if vb >= 0.60 * dv else "FAIL"
        fails = []
        if r.get("C1_settle_end") != "PASS":
            fails.append("C1_settle_end")
        if r.get("C1_valid90_reached") != "PASS":
            fails.append("C1_valid90")
        if r.get("C1_settle90_reached") != "PASS":
            fails.append("C1_settle90")
        if r["C2_rail_drain_abs"] != "PASS":
            fails.append("C2_drain_abs")
        if r["C3_swing_abs"] != "PASS":
            fails.append("C3_swing_abs")
        if r.get("C4_instrument") != "PASS":
            fails.append("C4_instrument")
        r["fails"] = fails
        r["FUNCTIONAL"] = "YES" if not fails else "NO"
        r["FUNCTIONAL_rel"] = "YES" if not [f for f in fails
                                            if f not in ("C2_drain_abs", "C3_swing_abs")] \
            and r["C2_rail_drain_rel"] == "PASS" and r["C3_swing_rel"] == "PASS" else "NO"
    lsw.save_row(r)
    return r


def stage_instr():
    """(b) INSTRUMENT CHECK.  Two halves:
    G0a  -- the imported extractor against the COMMITTED swsweep mt0 (no sim).
    G0e  -- the committed ROBUST POINT re-run end to end in THIS directory with
            THIS cache: L=15 nH, W=30 um (TG 10/20 + 2 um park), dV=1.2.
            Gate: t_hop 65.49500982 ps, VBEND 0.7138163, t_valid90 123.443114 ps,
            VBPK 0.8368896, VA_open 0.1276800, IPK 971.3203 uA,
            E_hop_open 14.8432245 fJ -- digit-checked at rel < 1e-6."""
    ok = True
    print("=== G0a: imported extractor vs the committed tg15p mt0 (no sim) ===")
    out = lsw.extract(os.path.join(lsw.SW, "sw_tg15p_z.cir.mt0"), lsw.L_REF, 15.0,
                      lsw.TZ_REF)
    for k, ref in lsw.ANCHOR.items():
        rel = abs(out[k] - ref) / max(abs(ref), 1e-30)
        ok &= rel < 1e-6
        print("%s %-16s mine %.10g committed %.10g (rel %.2e)"
              % ("OK  " if rel < 1e-6 else "FAIL", k, out[k], ref, rel))

    print("=== G0e: the committed ROBUST POINT re-run here (L=15nH W=30um dV=1.2) ===")
    REF = {"t_hop_ps": 65.49500982344826, "VBEND": 0.7138163,
           "t_valid90_ps": 123.44311400000001, "VBPK": 0.8368896,
           "VA_open": 0.1276800355763028, "IPK_uA": 971.3203,
           "E_hop_open_fJ": 14.843224450910004, "t_rail90_ps": 40.887047800000005,
           "t_settle90_ps": 115.570918, "t_level_ps": 115.570918,
           "t_level_cons_ps": 123.44311400000001}
    r = point("instr_L15_W30_dv120", 15.0, 30.0, 1.2)
    if "error" in r:
        print("FAIL  %s" % r["error"])
        return False
    for k, ref in REF.items():
        mine = r.get(k)
        if mine is None:
            print("FAIL  %-14s MISSING" % k)
            ok = False
            continue
        rel = abs(mine - ref) / max(abs(ref), 1e-30)
        g = 1e-6
        ok &= rel < g
        print("%s %-14s mine %.10g committed %.10g (rel %.2e, gate %g)"
              % ("OK  " if rel < g else "FAIL", k, mine, ref, rel, g))
    print("  gates: %s  (C1_end %s, C2abs %s, C3abs %s, C4 %s) VGH=%.2f wall %.0fs"
          % (r["FUNCTIONAL"], r["C1_settle_end"], r["C2_rail_drain_abs"],
             r["C3_swing_abs"], r["C4_instrument"], r["VGH"], r["wall_s"]))
    print("INSTRUMENT %s" % ("PASS" if ok else "FAIL"))
    return ok


if __name__ == "__main__":
    st = sys.argv[1]
    if st == "warm":
        sys.exit(0 if lsw.stage_warm() else 1)
    elif st == "instr":
        sys.exit(0 if stage_instr() else 1)
    elif st == "calib":
        dv = float(sys.argv[2])
        set_vgh(dv)
        sys.exit(0 if lsw.stage_calib(dv) else 1)
    elif st == "pt":
        tag, L, W, dv = sys.argv[2], float(sys.argv[3]), float(sys.argv[4]), float(sys.argv[5])
        r = point(tag, L, W, dv)
        print(lsw.brief(r) if "error" not in r else "%s ERROR %s" % (tag, r["error"]))
    elif st == "ptv":          # explicit VGH: the amendment-P1 control
        tag, L, W, dv, vg = (sys.argv[2], float(sys.argv[3]), float(sys.argv[4]),
                             float(sys.argv[5]), float(sys.argv[6]))
        r = point(tag, L, W, dv, vgh_force=vg)
        print(lsw.brief(r) if "error" not in r else "%s ERROR %s" % (tag, r["error"]))
    elif st == "merge":
        rows = merge_rows()
        print("merged %d rows" % len(rows))
    elif st == "show":
        for k, r in sorted(merge_rows().items()):
            print(lsw.brief(r))
