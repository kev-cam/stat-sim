#!/usr/bin/env python3
"""SKEPTIC driver: probe (sequential per point) then row, points in parallel.
Own directory, own PYMS_VAE_CACHE (set by the caller)."""
import json, os, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
PTS = [("skip", 60.0, 1.2), ("adj", 60.0, 1.2),
       ("skip", 160.0, 1.2), ("adj", 160.0, 1.2)]


def one(pt):
    scheme, T, dv = pt
    tag = "%s_T%g_dv%g" % (scheme, T, dv * 1000)
    t0 = time.monotonic()
    r = subprocess.run([sys.executable, "skip.py", "probe", scheme, "free",
                        str(T), str(dv)], capture_output=True, text=True, cwd=HERE)
    out = r.stdout.strip().splitlines()
    tz = None
    for ln in reversed(out):
        if ln.startswith("["):
            tz = json.loads(ln); break
    if tz is None:
        return tag, None, "PROBE FAIL: " + r.stdout[-400:] + r.stderr[-400:]
    r2 = subprocess.run([sys.executable, "skip.py", "row", scheme, "free",
                         str(T), str(dv), json.dumps(tz)],
                        capture_output=True, text=True, cwd=HERE)
    return tag, tz, "%s tz=%s (%.0fs)\n%s\n%s" % (
        tag, ["%.3f" % x for x in tz], time.monotonic() - t0,
        "\n".join(out), r2.stdout.strip())


if __name__ == "__main__":
    res = {}
    with ThreadPoolExecutor(max_workers=4) as ex:
        for tag, tz, msg in ex.map(one, PTS):
            print("=" * 60); print(msg, flush=True)
            res[tag] = tz
    json.dump(res, open(os.path.join(HERE, "tz2.json"), "w"), indent=1)
    print(json.dumps(res, indent=1))
