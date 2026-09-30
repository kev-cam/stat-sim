#!/usr/bin/env python3
"""qal/rfast_skept -- skeptic driver.  Imports qal/rfast/rf.py VERBATIM as the
instrument and redirects ONLY the working directory and the cache:
  rf.HERE  -> qal/rfast_skept   (lanes land in rfast_skept/L*W*/T*/P*)
  cache    -> scratchpad/vae_cache_skept  (OWN, empty-start, warmed privately)
Nothing in qal/rfast/ is written.  Subcommands: warmone / lane / extract /
seqprobe (pass-through), plus police (raw-waveform value + A6 check).
"""
import importlib.util, json, math, os, sys

SKHERE = os.path.dirname(os.path.abspath(__file__))
SCRATCH = ("/tmp/claude-1001/-usr-local-src/"
           "4921ad0c-f17b-4b84-986a-5917c9ebd2a6/scratchpad")
MYCACHE = os.path.join(SCRATCH, "vae_cache_rfskept_20260930")
# NOTE (caught in-run): scratchpad/vae_cache_skept AND vae_cache_skept2 both
# already existed, holding .so files built Sep 28 by an EARLIER session that
# used the same names.  Using either would have broken the empty-start claim,
# so this study minted the date-stamped name above, verified non-existence,
# and merged ONLY today's 11 private per-geometry builds (22 files).  The
# Sep-28 same-hash .so files byte-DIFFER from today's rebuilds (embedded
# timestamps/paths -- the build is not byte-reproducible), which is exactly
# why a name-collided cache cannot be verified by content and had to be
# abandoned.

_spec = importlib.util.spec_from_file_location(
    "rf", "/usr/local/src/stat-sim/qal/rfast/rf.py")
rf = importlib.util.module_from_spec(_spec)
sys.modules["rf"] = rf
_spec.loader.exec_module(rf)

rf.HERE = SKHERE          # call-time global: tdirname, warm, seqA6 all follow
rf.CACHE = MYCACHE


def _redirect(sub, cache=None):
    cache = MYCACHE if cache is None else cache
    os.makedirs(cache, exist_ok=True)
    os.makedirs(sub, exist_ok=True)
    rf.bt.HERE = sub
    rf.bt.CACHE = cache
    rf.bt.ENV = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS",
                     PYMS_VAE_CACHE=cache)


rf.redirect = _redirect   # rf.cmd_* resolve `redirect` at call time


def _interp(rows, it, ic, t_ps):
    """linear interpolation of column ic at time t_ps from raw .prn rows"""
    prev = None
    for r in rows:
        t = r[it] * 1e12
        if t >= t_ps:
            if prev is None or t == t_ps:
                return r[ic]
            t0, v0 = prev
            return v0 + (r[ic] - v0) * (t_ps - t0) / (t - t0)
        prev = (t, r[ic])
    return None


def cmd_police(L, W, T, pname):
    """INDEPENDENT raw-waveform check of one lane: per-gate value at the
    boundary instants and |I(L)| at the commanded opens, by interpolation of
    the final .prn -- no .measure output is trusted."""
    sub = os.path.join(rf.tdirname(L, W, T), pname)
    S = json.load(open(os.path.join(sub, "sched.json")))
    hdr, rows = rf.bt.read_prn(S["prn"])
    it = hdr.index("TIME")
    d = rf.bt.parse_mt0(S["mt0"])
    rf.bt.PAT[:] = list(rf.PATTERNS[pname])
    out = dict(L=L, W=W, T=T, pattern=pname, banks={})
    ok_all, a6_all = True, True
    for k in range(1, 5):
        ck, ok_ = S["c"][str(k)], S["o"][str(k)]
        rk, rok = S["r"][str(k)], S["ro"][str(k)]
        bnd = S["bound"][str(k)]
        iL = hdr.index("I(L%d)" % k)
        iR = hdr.index("V(RAIL%d)" % k)
        iz = _interp(rows, it, iL, ok_) * 1e6
        izq = _interp(rows, it, iL, rok) * 1e6
        # true zero instants off the raw waveform (lsweep refined rule)
        zr, _ = rf.bt.zero_after_peak(hdr, rows, "I(L%d)" % k, ck)
        zq, _ = rf.bt.zero_after_peak(hdr, rows, "I(L%d)" % k, rk)
        rail = _interp(rows, it, iR, bnd)
        gates, nbad = [], 0
        for i in range(8):
            io = hdr.index("V(O%d_%d)" % (k, i))
            v = _interp(rows, it, io, bnd)
            hi = rf.bt.out_hi(k, i)
            g_ok = (v >= 0.50 * rail) if hi else (v <= 0.10 * rail)
            if not g_ok:
                nbad += 1
                gates.append(dict(i=i, hi=bool(hi), v=round(v, 5),
                                  rail=round(rail, 5)))
        mt_iz = d.get("IZ%d" % k, 0) * 1e6
        mt_izq = d.get("IZQ%d" % k, 0) * 1e6
        out["banks"][str(k)] = dict(
            raw_I_at_open_uA=round(iz, 4), raw_I_at_return_open_uA=round(izq, 4),
            mt0_IZ_uA=round(mt_iz, 4), mt0_IZQ_uA=round(mt_izq, 4),
            mt0_vs_raw_uA=round(max(abs(iz - mt_iz), abs(izq - mt_izq)), 4),
            true_rise_zero_minus_open_ps=(None if zr is None
                                          else round(zr - ok_, 4)),
            true_return_zero_minus_open_ps=(None if zq is None
                                            else round(zq - rok, 4)),
            rail_at_boundary_V=round(rail, 5), value_fails=gates,
            value_8_8=bool(nbad == 0))
        ok_all = ok_all and (nbad == 0)
        a6_all = a6_all and (abs(iz) <= 1.0) and (abs(izq) <= 1.0)
    out["value_32_32_raw"] = bool(ok_all)
    out["A6_raw_all_opens"] = bool(a6_all)
    fn = os.path.join(sub, "POLICE.json")
    json.dump(out, open(fn, "w"), indent=1)
    print(json.dumps({k: out[k] for k in ("pattern", "value_32_32_raw",
                                          "A6_raw_all_opens")}),
          "->", fn)
    return 0 if (ok_all and a6_all) else 3


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "warmone":
        sys.exit(rf.cmd_warmone(a[1], a[2], float(a[3])))
    if a[0] == "lane":
        sys.exit(rf.cmd_lane(float(a[1]), float(a[2]), float(a[3]), a[4]))
    if a[0] == "extract":
        L, W, T = float(a[1]), float(a[2]), float(a[3])
        pats = [x for x in a[4:]] or ["P0", "P1", "P2"]
        sys.exit(rf.cmd_extract(L, W, T, pats))
    if a[0] == "seqprobe":
        sys.exit(rf.cmd_seqprobe(float(a[1]), float(a[2]), float(a[3])))
    if a[0] == "police":
        sys.exit(cmd_police(float(a[1]), float(a[2]), float(a[3]), a[4]))
    print("unknown subcommand")
    sys.exit(2)
