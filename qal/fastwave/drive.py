#!/usr/bin/env python3
"""Parallel driver.  Every geometry is pre-warmed (warm.py) so no worker ever
triggers a PyMS build; fw.run() prints a WARNING to stderr if one ever does."""
import json, os, sys, time
from concurrent.futures import ProcessPoolExecutor, as_completed
import fw

HERE = os.path.dirname(os.path.abspath(__file__))
ROWS = os.path.join(HERE, "ROWS.json")


def one(spec):
    tag, kw = spec
    try:
        return fw.point(tag, verbose=False, **kw)
    except Exception as e:                                             # noqa
        return dict(tag=tag, error="exception %r" % e,
                    N=kw.get("n"), L_nH=kw.get("l_nh"),
                    total_um=kw.get("total_um"))


def save(new):
    rows = json.load(open(ROWS)) if os.path.exists(ROWS) else {}
    rows.update(new)
    json.dump(rows, open(ROWS, "w"), indent=1)
    return len(rows)


def main():
    specs = json.load(open(sys.argv[1]))
    nw = int(os.environ.get("NW", "4"))
    done, t0 = {}, time.monotonic()
    with ProcessPoolExecutor(max_workers=nw) as ex:
        futs = {ex.submit(one, s): s[0] for s in specs}
        for f in as_completed(futs):
            r = f.result()
            done[r["tag"]] = r
            print("[%5.0fs] %s" % (time.monotonic() - t0, fw.brief(r)), flush=True)
            if len(done) % 4 == 0:
                save(done)
    print("total rows on disk: %d  (%.0fs)" % (save(done), time.monotonic() - t0))


if __name__ == "__main__":
    main()
