#!/usr/bin/env python3
"""Independent adjudication extractor: reads a Xyce .prn, returns t90 for named
columns against a given target level.  No reliance on either run's code."""
import sys


def load(path):
    with open(path) as f:
        hdr = f.readline().split()
    # drop a leading 'Index' if present
    names = [h.upper() for h in hdr]
    rows = []
    with open(path) as f:
        f.readline()
        for ln in f:
            p = ln.split()
            if not p or p[0].lower().startswith('end'):
                continue
            try:
                rows.append([float(x) for x in p])
            except ValueError:
                continue
    return names, rows


def col(names, want):
    want = want.upper()
    for i, n in enumerate(names):
        if n == want or n == "V(%s)" % want:
            return i
    return None


def t90(names, rows, cname, target, frac=0.90, tcol=None):
    ci = col(names, cname)
    if ci is None:
        return None, None, None
    ti = tcol if tcol is not None else col(names, 'TIME')
    thr = frac * target
    # last time at which it is BELOW thr -> settles after that (monotone-safe:
    # require it to stay above for the remainder)
    tlast = None
    for r in rows:
        if len(r) <= max(ci, ti):
            continue
        if r[ci] < thr:
            tlast = r[ti]
    final = rows[-1][ci]
    if tlast is None:
        return 0.0, final, final / target * 100.0
    if tlast >= rows[-1][ti] - 1e-18:
        return None, final, final / target * 100.0  # never
    # first sample after tlast
    for r in rows:
        if r[ti] > tlast:
            return r[ti] * 1e12, final, final / target * 100.0
    return None, final, final / target * 100.0


if __name__ == '__main__':
    path = sys.argv[1]
    target = float(sys.argv[2])
    for cname in sys.argv[3:]:
        t, final, pct = t90(*load(path), cname=cname, target=target)
        print("%-16s t90=%-12s final=%.6f V  = %.2f%% of %.4f" % (
            cname, ("%.1f ps" % t) if t is not None else "NEVER", final, pct, target))
