#!/usr/bin/env python3
"""qal/eyebeat_skept lane driver (SKEPTIC).

Reuses eb.py's Newton-on-the-row lane machinery VERBATIM (the deck itself is
bt.py verbatim either way, and the A6 gate is objective), but redirects every
file into qal/eyebeat_skept/ under this study's OWN PYMS_VAE_CACHE built from
empty.  The EXTRACTION is deliberately NOT reused: skx.py in this directory is
an independent implementation of the pre-registered definitions.

Subcommands:
  warm                      build the standard geometries into the own cache
  lane <T> <P>              Newton lane at (T, pattern) under eyebeat_skept/
  wwarm <scale>             warm the width-scaled cell geometries
  wlane <scale> <T> <P>     width-scaled discrimination lane (SK_B):
                            cell WP/WN x scale, CL fixed, tank/switch untouched,
                            files under w{scale*100}/T{T}/{P}/
"""
import importlib.util, os, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
EBDIR = "/usr/local/src/stat-sim/qal/eyebeat"
CACHE = os.path.join("/tmp/claude-1001/-usr-local-src/"
                     "4921ad0c-f17b-4b84-986a-5917c9ebd2a6/scratchpad",
                     "vae_cache_eyebeat_skept")

_spec = importlib.util.spec_from_file_location("eb", os.path.join(EBDIR, "eb.py"))
eb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(eb)


def repoint(root):
    eb.HERE = root
    eb.CACHE = CACHE


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "warm":
        repoint(HERE)
        sys.exit(eb.cmd_warm())
    if a[0] == "lane":
        repoint(HERE)
        sys.exit(eb.cmd_lane(float(a[1]), a[2]))
    if a[0] == "wwarm":
        sc = float(a[1])
        sub = os.path.join(HERE, "w%03d" % round(sc * 100))
        repoint(sub)
        eb.bt.WP, eb.bt.WN = 1.12 * sc, 0.74 * sc
        eb.redirect(sub)
        ok = eb.bt.stage_warm()
        print("wwarm %g:" % sc, "OK" if ok else "FAIL")
        sys.exit(0 if ok else 1)
    if a[0] == "wlane":
        sc, T, p = float(a[1]), float(a[2]), a[3]
        sub = os.path.join(HERE, "w%03d" % round(sc * 100))
        repoint(sub)
        eb.bt.WP, eb.bt.WN = 1.12 * sc, 0.74 * sc
        # seed from THIS study's own standard-width zeros at the same (T, P)
        # if available (own-T measurement; Newton corrects the width effect)
        seed_src = os.path.join(HERE, "T%g" % T, p, "zeros.json")
        dst_dir = os.path.join(sub, "T%g" % T, p)
        dst = os.path.join(dst_dir, "zeros.json")
        if os.path.exists(seed_src) and not os.path.exists(dst):
            os.makedirs(dst_dir, exist_ok=True)
            shutil.copy(seed_src, dst)
            print("seeded wlane zeros from", seed_src)
        sys.exit(eb.cmd_lane(T, p))
    print("unknown subcommand")
    sys.exit(2)
