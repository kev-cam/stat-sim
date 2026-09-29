#!/usr/bin/env python3
"""REAL-LOAD excursion harness.  Thin wrapper that IMPORTS the skeptic's s2sk.py
(which itself imports qal/skept/sk.py, the independently written generator +
waveform-only extractor).  Nothing is copied, so every number is produced by the
same code path that reproduced the committed rows bit-identically.

Rebound: sk.HERE / s2sk.HERE / s2sk.ROWD -> this directory, PYMS_VAE_CACHE -> my own.
The cl_fF argument already exists in s2sk.run_pt; the load is the only new axis.

usage: s3.py pt <tag> <L_nH> <W_um> <dV> [tail_ps] [kind] [cl_fF]
       s3.py merge
"""
import json, os, sys

sys.path.insert(0, "/usr/local/src/stat-sim/qal/dvopt/skept2")
sys.path.insert(0, "/usr/local/src/stat-sim/qal/skept")
import sk                                                            # noqa: E402
import s2sk                                                          # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = ("/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6"
         "/scratchpad/vae_cache_load691")
sk.HERE = HERE
sk.ENV = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS", PYMS_VAE_CACHE=CACHE)
s2sk.HERE = HERE
s2sk.ROWD = os.path.join(HERE, "rowd")


def merge():
    rows = {}
    d = s2sk.ROWD
    if os.path.isdir(d):
        for fn in sorted(os.listdir(d)):
            if fn.endswith(".json"):
                r = json.load(open(os.path.join(d, fn)))
                rows[r["tag"]] = r
    json.dump(rows, open(os.path.join(HERE, "rows.json"), "w"), indent=1)
    return rows


if __name__ == "__main__":
    c = sys.argv[1]
    if c == "pt":
        a = sys.argv
        r = s2sk.run_pt(a[2], float(a[3]), float(a[4]), float(a[5]),
                        float(a[6]) if len(a) > 6 else 500.0,
                        a[7] if len(a) > 7 else "inv",
                        float(a[8]) if len(a) > 8 else 2.0)
        print("DONE", r.get("tag"), r.get("error", ""))
    elif c == "merge":
        print("merged %d" % len(merge()))
