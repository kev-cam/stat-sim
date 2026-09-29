#!/usr/bin/env python3
"""Warm MY OWN PyMS vae cache.  The .so cache key folds the DEVICE PARAMETERS and
W is one of them, so each (type, width) pair is one GiNaC C++ compile (3-5 min).
Distinct keys build concurrently; same key must not.  Kept to 4 at a time."""
import os, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor

HERE  = os.path.dirname(os.path.abspath(__file__))
XYCE  = "/usr/local/src/xyce-build/src/Xyce"
VA    = "/usr/local/share/xyce/verilog-a/psp103/psp103.va"
MODEL = "/usr/local/src/kestrel/sim/models/sg13g2_psp103_tt.lib"
SHIM  = "/usr/local/src/stat-sim/qal/sg13lv_compat.sp"
CACHE = ("/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6"
         "/scratchpad/vae_cache_pgcell_SKEPT")
ENV = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS", PYMS_VAE_CACHE=CACHE)
os.makedirs(CACHE, exist_ok=True)

# every (type, width) that any deck of this run uses
NW = [0.74, 1.0, 2.0, 10.0]
PW = [1.12, 1.0, 2.0, 20.0]
JOBS = [("n", w) for w in NW] + [("p", w) for w in PW]


def one(job):
    t, w = job
    tag = "%s%s" % (t, str(w).replace(".", "p"))
    fn = "warm_%s.cir" % tag
    dev = "sg13_lv_nmos" if t == "n" else "sg13_lv_pmos"
    L = ['* warm %s' % tag, '.hdl "%s"' % VA, '.include "%s"' % MODEL,
         '.include "%s"' % SHIM,
         '.OPTIONS TIMEINT METHOD=GEAR RELTOL=1e-6 ABSTOL=1e-15 CHGTOL=1e-17',
         'VD d 0 1.2', 'VG g 0 1.2', 'VB b 0 %s' % ("0" if t == "n" else "1.2"),
         'X1 d g s b %s w=%gu l=0.13u' % (dev, w),
         'RS s 0 1k', 'CS s 0 1f',
         '.tran 1p 20p', '.print tran V(s)', '.end']
    open(os.path.join(HERE, fn), "w").write("\n".join(L) + "\n")
    t0 = time.monotonic()
    r = subprocess.run([XYCE, fn], capture_output=True, text=True,
                       cwd=HERE, env=ENV, timeout=1800)
    return tag, r.returncode, time.monotonic() - t0


if __name__ == "__main__":
    with ThreadPoolExecutor(max_workers=4) as ex:
        for tag, rc, w in ex.map(one, JOBS):
            print("warm %-10s rc=%d %.0fs" % (tag, rc, w), flush=True)
    print("CACHE", CACHE, len([f for f in os.listdir(CACHE) if f.endswith(".so")]),
          "so files")
