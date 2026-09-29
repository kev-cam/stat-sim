#!/usr/bin/env python3
"""Grid runner: probe -> row -> extract for each (scheme, mode, T, dv) combo.

Each combo is a sequence of runs (hop zeros must be found in order), so the
parallelism is ACROSS combos.  MAXPAR is kept at 4 (sim discipline: ~4 concurrent
heavy jobs on this 16-core box, shared with two other workflows).
"""
import json, os, sys, time
from concurrent.futures import ThreadPoolExecutor

FREE_TZ = {}
import skip
import extract

HERE = os.path.dirname(os.path.abspath(__file__))
ROWS = os.path.join(HERE, "rows.json")
MAXPAR = int(os.environ.get("MAXPAR", "4"))
W, L = 30.0, 15.0


def one(combo):
    scheme, mode, T, dv = combo
    tag = skip.tag_of(scheme, mode, T, dv)
    t0 = time.monotonic()
    try:
        if mode == "dstheld":
            # the deepest bank's rail is pinned to dV, so the hop INTO it has no
            # current zero at all (it is a source driving a stiff node, not an LC
            # exchange).  This control's only job for that hop is to DRAIN the
            # source bank on schedule, so the switch opens at the zero MEASURED on
            # the corresponding free-running row.  Recorded, and the A6 IZ gate is
            # reported per hop so the pinned hop is never mistaken for a clean ZCS.
            tz = FREE_TZ[skip.tag_of(scheme, "free", T, dv)]
            print("  %s: tz reused from the free row %s" % (tag, tz))
        else:
            tz = skip.do_probe(scheme, mode, T, W, L, dv)
        if tz is None:
            return tag, dict(error="probe failed")
        got = skip.do_row(scheme, mode, T, W, L, dv, tz)
        if got is None:
            return tag, dict(error="row failed", tz_ps=tz)
        path, S = got
        r = extract.row_extract(scheme, mode, T, dv, tz, path)
        r["wall_s"] = round(time.monotonic() - t0, 1)
        return tag, r
    except Exception as e:                                          # noqa
        import traceback
        return tag, dict(error=repr(e), tb=traceback.format_exc()[-1500:])


def main():
    combos = []
    for arg in sys.argv[1:]:
        scheme, mode, T, dv = arg.split(",")
        combos.append((scheme, mode, float(T), float(dv)))
    rows = json.load(open(ROWS)) if os.path.exists(ROWS) else {}
    # snapshot the free-row zeros BEFORE the pool starts: reading rows.json from a
    # worker races the main thread's json.dump and returns a truncated file.
    global FREE_TZ
    FREE_TZ = {t: r["tz_ps"] for t, r in rows.items() if "tz_ps" in r}
    with ThreadPoolExecutor(max_workers=MAXPAR) as ex:
        for tag, r in ex.map(one, combos):
            rows[tag] = r
            if "error" in r:
                print("%-28s ERROR %s" % (tag, r["error"]))
            else:
                print("%-28s worst %6.2f%% (stage %d)  rails %s  PASS=%s  %.0fs"
                      % (tag, r["worst_gate_pct_all_stages"], r["worst_gate_stage"],
                         " ".join("%.3f" % v for _, v in
                                  sorted(r["rail_at_own_boundary_V"].items())),
                         r["PASS"], r["wall_s"]))
            json.dump(rows, open(ROWS, "w"), indent=1)
    print("rows.json now holds %d rows" % len(rows))


if __name__ == "__main__":
    main()
