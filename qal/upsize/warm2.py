#!/usr/bin/env python3
"""TARGETED PARALLEL WARM.  PHASE 2 AMENDMENT A2.

Two facts forced this, both MEASURED not assumed:

  1. PyMS keys its .so cache on the FULL PSP103 parameter set, which includes
     TYPE (+1 nMOS / -1 pMOS).  So a geometry is a (width, TYPE) PAIR, not a
     width.  Phase 1's `stage_warm` instantiates BOTH types at EVERY width,
     which doubles the compile bill and spends half of it on pairs the study
     never instantiates (e.g. 0.74 um pMOS, 1.12 um nMOS, 160 um nMOS).
  2. PyMS SERIALISES within one cache directory: a second Xyce process that
     needs any geometry blocks on `do_wait` behind the first process's
     build_vae_so child, even for a geometry that is already built.  Measured
     directly: three cell-chain jobs sat at 0.0-0.8% CPU for 3+ minutes while
     the warm compiled something else.  That is the cache race Phase 1 warned
     about, showing up as benign blocking rather than corruption.

So: enumerate the EXACT (width, TYPE) pairs the Phase 2 decks instantiate, run
each missing one in its OWN PRIVATE cache directory so nothing contends, and
merge the results into the study cache, ADDING ONLY names that are absent.

WHAT THE MERGE TAUGHT ME (amendment A6), because I got the justification wrong
the first time.  I wrote that "the .so filename IS the hash of the parameter
set, so it is cache-location independent".  The filename IS content-addressed on
the parameter set -- verified: the .params files for a given hash are BYTE
IDENTICAL across two independent caches.  But the COMPILED .so for that same
hash is NOT reproducible: the same hash came out 384888 / 388984 / 393080 bytes
in different caches (multiples of one 4 KiB page apart), because the build path
is embedded in the object.  So a merge must never overwrite -- which this one
never does -- and "same name" cannot be read as "same bytes".

The merge is not trusted on any argument: acceptance B0b re-runs the Phase 1
deck against the merged cache and must reproduce Phase 1's row, which is what
actually licenses it.
"""
import glob, json, math, os, re, shutil, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import up

MAIN = "/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6" \
       "/scratchpad/vae_cache_upsize"
PRIV = "/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6" \
       "/scratchpad/warmpriv"

NMOS, PMOS = 1, -1


def needed():
    """the EXACT (width, TYPE) pairs the Phase 2 decks instantiate.  Derived
    from up.py's own generators, not from a hand-written list."""
    need = set()
    for s in up.SCALES:
        need.add((up.WP * s, PMOS))      # cell pull-up
        need.add((up.WN * s, NMOS))      # cell pull-down
        for n in (8, 64):
            w = up.widths(up.wtot(n, 1.0, s))
            need.add((w["wn"], NMOS))    # TG nMOS
            need.add((w["wp"], PMOS))    # TG pMOS
            need.add((w["park"], NMOS))  # park nMOS
    # E1 (scale 4,4,1) and E3 (L=3.75) reuse N=64 widths at s=4 and s=1; E2
    # changes only C_tank.  Nothing else is instantiated.
    return sorted(need)


def cache_rows(cache):
    """MEASURED from the cache itself: (W_um, TYPE, .so exists) per entry."""
    out = []
    for f in glob.glob(os.path.join(cache, "*.params")):
        try:
            d = dict(re.findall(r"^(\w+)=(\S+)$", open(f).read(), re.M))
            out.append((float(d["W"]) * 1e6, int(d["TYPE"]),
                        os.path.exists(f[:-7])))
        except Exception:
            continue
    return out


def has(rows, w, ty):
    """AMENDMENT A6: match on a TOLERANCE, not an exact round().

    The .params file stores W to 6 SIGNIFICANT FIGURES (`W=2.82843e-06`), so a
    full-precision sqrt(2)-family width from the generator (2.8284271247...)
    never equals its own round-tripped value.  Keying on round(w, 6) therefore
    reported every non-round width as MISSING even when its .so was sitting in
    the cache.  That is what made warm2.py rebuild 9 geometries it already had
    and then still report them missing after a merge that had nothing to add."""
    for (ww, tt, ok) in rows:
        if tt == ty and ok and abs(ww - w) <= 1e-5 * max(1.0, w):
            return True
    return False


def one_deck(w, ty):
    """a single device of exactly this geometry and type, nothing else."""
    L = up.head_lines() + ["VA a 0 0.5", "VB b 0 0.5"]
    if ty == NMOS:
        L += ["XW d a 0 0 sg13_lv_nmos w=%gu l=0.13u" % w, "RW d b 1k"]
    else:
        L += ["XW d a b b sg13_lv_pmos w=%gu l=0.13u" % w, "RW d 0 1k"]
    L += [".tran 1p 10p", ".print tran V(a)", ".end"]
    return L


def build(w, ty, idx):
    cache = os.path.join(PRIV, "c%03d" % idx)
    os.makedirs(cache, exist_ok=True)
    d = os.path.join(PRIV, "d%03d" % idx)
    os.makedirs(d, exist_ok=True)
    fn = "w_%g_%s.cir" % (w, "n" if ty == NMOS else "p")
    open(os.path.join(d, fn), "w").write("\n".join(one_deck(w, ty)) + "\n")
    env = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS",
               PYMS_VAE_CACHE=cache)
    t0 = time.monotonic()
    r = subprocess.run([up.XYCE, fn], capture_output=True, text=True,
                       cwd=d, env=env, timeout=3600)
    wall = time.monotonic() - t0
    ok = os.path.exists(os.path.join(d, fn + ".prn"))
    n_so = len(glob.glob(os.path.join(cache, "*.so")))
    print("  w=%-11g %s  %s  %.0fs  %d .so"
          % (w, "nmos" if ty == NMOS else "pmos", "OK" if ok else "FAIL",
             wall, n_so), flush=True)
    if not ok:
        print("    stdout tail: %s" % r.stdout[-400:], flush=True)
    return ok


def merge():
    """copy .so/.params/.build into the study cache, ADDING ONLY what is not
    already there.  Never overwrites: an existing .so in the study cache is
    the one Phase 1 validated."""
    added, skipped = [], []
    for cache in sorted(glob.glob(os.path.join(PRIV, "c*"))):
        for src in glob.glob(os.path.join(cache, "*")):
            dst = os.path.join(MAIN, os.path.basename(src))
            if os.path.exists(dst):
                skipped.append(os.path.basename(src))
                continue
            if os.path.isdir(src):
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)
            added.append(os.path.basename(src))
    return added, skipped


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "plan"
    need = needed()
    rows = cache_rows(MAIN)
    miss = [(w, t) for (w, t) in need if not has(rows, w, t)]
    print("Phase 2 instantiates %d (width,TYPE) geometries; %d already built; "
          "%d MISSING" % (len(need), len(need) - len(miss), len(miss)))
    for w, t in miss:
        print("   MISSING w=%-11g %s" % (w, "nmos" if t == NMOS else "pmos"))
    if mode == "plan":
        json.dump(dict(needed=[[w, t] for w, t in need],
                       missing=[[w, t] for w, t in miss]),
                  open(os.path.join(HERE, "WARM_PLAN.json"), "w"), indent=1)
        return 0
    if mode == "build":
        i = int(sys.argv[2])
        if i >= len(miss):
            print("index %d beyond missing list" % i)
            return 0
        w, t = miss[i]
        return 0 if build(w, t, i) else 1
    if mode == "merge":
        added, skipped = merge()
        print("merged: %d files added, %d already present" % (len(added),
                                                             len(skipped)))
        rows2 = cache_rows(MAIN)
        still = [(w, t) for (w, t) in need if not has(rows2, w, t)]
        print("after merge, MISSING %d" % len(still))
        for w, t in still:
            print("   STILL MISSING w=%-11g %s"
                  % (w, "nmos" if t == NMOS else "pmos"))
        json.dump(dict(added=added, n_skipped=len(skipped),
                       still_missing=[[w, t] for w, t in still]),
                  open(os.path.join(HERE, "WARM_MERGE.json"), "w"), indent=1)
        return 0 if not still else 1
    print("usage: warm2.py {plan|build IDX|merge}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
