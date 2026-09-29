#!/usr/bin/env python3
"""(f) THE 2-HIGH STACK IN A REAL BANK, across the characterised swings.

Thin wrapper over qal/skept/sk.py (IMPORTED not copied): its o21ai bank topology,
its waveform-only extractor, its true-ZCS probe.  Rebound here and nothing else:
  sk.HERE -> this directory,  sk.ENV -> own PYMS_VAE_CACHE,
  sk.VGH  -> max(1.5, dV)    [amendment P1, same rule as dvo.py]

The ideal-supply companion (floor.py PART O) has already MEASURED the stack's own
requirement.  This measures what a bank DELIVERS to it, which is the other half of
the pre-registered separation.

  i0            reproduce the COMMITTED o21_dv150 row (instrument check)
  pt <tag> <L> <W> <dV> [tail_ps] [kind]
"""
import json, os, sys, time

sys.path.insert(0, "/usr/local/src/stat-sim/qal/skept")
import sk                                                          # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = ("/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6"
         "/scratchpad/vae_cache_dvopt")
sk.HERE = HERE
sk.ENV = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS",
              PYMS_VAE_CACHE=CACHE)
ROWD = os.path.join(HERE, "o21d")


def run_pt(tag, L, W, dv, tail=500.0, kind="o21ai", cl=2.0):
    sk.VGH = max(1.5, dv)
    t0 = time.monotonic()
    lp, msg = sk.run("p_%s.cir" % tag, sk.probe(L, W, dv, kind=kind, cl=cl))
    print(" probe:", msg)
    if lp is None:
        return dict(tag=tag, error=msg)
    tz, ipk, tipk = sk.zero_of(lp + ".prn")
    if tz is None:
        return dict(tag=tag, error="no current zero after the peak")
    print("  true zero %.4f ps (t_hop %.4f), Ipk %.2f uA" % (tz, tz - sk.T0, ipk))
    lines, meta = sk.hop(L, W, dv, tz - sk.T0, tail=tail, kind=kind, cl=cl)
    hp, msg = sk.run("h_%s.cir" % tag, lines, timeout=900)
    print(" hop:", msg)
    if hp is None:
        return dict(tag=tag, error=msg)
    r = sk.extract_hop(hp + ".prn", meta, L, W, dv)
    r.update(tag=tag, cell_kind=kind, cl_fF=cl, tail_ps=tail, VGH=sk.VGH,
             VGH_AMENDED=bool(abs(sk.VGH - 1.5) > 1e-12),
             probe_Ipk_uA=ipk, wall_s=round(time.monotonic() - t0, 1))
    os.makedirs(ROWD, exist_ok=True)
    json.dump(r, open(os.path.join(ROWD, "%s.json" % tag), "w"), indent=1)
    print(" s_end:", {k: round(v, 2) for k, v in r["s_end"].items()})
    print(" t_valid80 %s  t_valid90 %s  VBEND %.5f  VA_open %+.5f"
          % (r["t_valid80_ps"], r["t_valid90_ps"], r["VBEND"], r["VA_open"]))
    return r


def stage_i0():
    """instrument check on the o21ai path: the COMMITTED skept row o21_dv150
    (L=15 nH, W=30 um, dV=1.5, tail 500 ps) must come back with
    VBEND 0.6076701932, t_hop 67.31716163, s_end(lo) 82.99%, t_valid80 515.148911 ps,
    t_valid90 None."""
    REF = dict(VBEND=0.6076701932224732, t_hop_ps=67.31716163004057,
               VA_open=-0.17394619083354046, t_valid80_ps=515.148911,
               IPK_uA=1435.09869)
    r = run_pt("i0_o21_dv150", 15.0, 30.0, 1.5)
    if "error" in r:
        print("FAIL", r["error"])
        return False
    ok = True
    for k, ref in REF.items():
        rel = abs(r[k] - ref) / max(abs(ref), 1e-30)
        ok &= rel < 1e-6
        print("%s %-14s mine %.10g committed %.10g (rel %.2e)"
              % ("OK  " if rel < 1e-6 else "FAIL", k, r[k], ref, rel))
    s = min(r["s_end"].values())
    rel = abs(s - 82.99) / 82.99
    ok &= rel < 1e-3
    print("%s s_end(min)    mine %.4f committed 82.99 (rel %.2e)"
          % ("OK  " if rel < 1e-3 else "FAIL", s, rel))
    print("%s t_valid90 mine %s committed None"
          % ("OK  " if r["t_valid90_ps"] is None else "FAIL", r["t_valid90_ps"]))
    ok &= r["t_valid90_ps"] is None
    print("O21 INSTRUMENT %s" % ("PASS" if ok else "FAIL"))
    return ok


def merge():
    rows = {}
    if os.path.isdir(ROWD):
        for fn in sorted(os.listdir(ROWD)):
            if fn.endswith(".json"):
                r = json.load(open(os.path.join(ROWD, fn)))
                rows[r["tag"]] = r
    json.dump(rows, open(os.path.join(HERE, "o21.json"), "w"), indent=1)
    return rows


if __name__ == "__main__":
    c = sys.argv[1]
    if c == "i0":
        sys.exit(0 if stage_i0() else 1)
    elif c == "pt":
        a = sys.argv
        run_pt(a[2], float(a[3]), float(a[4]), float(a[5]),
               float(a[6]) if len(a) > 6 else 500.0,
               a[7] if len(a) > 7 else "o21ai")
    elif c == "merge":
        print("merged %d o21 rows" % len(merge()))
