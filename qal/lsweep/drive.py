#!/usr/bin/env python3
"""Parallel driver for the TRACK 1 L-down sweep.  Each point gets its own deck
filenames; the PyMS cache is pre-warmed (lsw.py warm) so no worker compiles."""
import json, os, sys
from concurrent.futures import ProcessPoolExecutor, as_completed
import lsw

HERE = os.path.dirname(os.path.abspath(__file__))


def one(spec):
    tag, kw = spec
    try:
        r = lsw.point(tag, verbose=False, **kw)
    except Exception as e:                                       # noqa
        r = dict(tag=tag, error="exception %r" % e, **{k: v for k, v in kw.items()})
        r.setdefault("L_nH", kw.get("l_nh"))
        r.setdefault("total_um", kw.get("total_um"))
    return r


def main():
    specs = json.load(open(sys.argv[1]))
    jobs = [(t, kw) for t, kw in specs]
    nw = int(os.environ.get("NW", "6"))
    out = {}
    with ProcessPoolExecutor(max_workers=nw) as ex:
        futs = {ex.submit(one, j): j[0] for j in jobs}
        for f in as_completed(futs):
            r = f.result()
            out[r["tag"]] = r
            print(lsw.brief(r), flush=True)
    fn = os.path.join(HERE, "rows.json")
    rows = json.load(open(fn)) if os.path.exists(fn) else {}
    rows.update(out)
    json.dump(rows, open(fn, "w"), indent=1)
    print("wrote %d rows" % len(out))


if __name__ == "__main__":
    main()
