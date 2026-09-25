#!/usr/bin/env python3
"""ASCII render of the measured supply current so the waveform itself can be
pasted into the report. Log-scale option shows the lull structure and the
decay into the leakage floor, which linear scale hides."""
import sys, math
from analyze_cscd import load

def render(prn, t0ns, t1ns, rows_=40, cols=110, log=True, dec=None):
    hdr, cols_i, rows = load(prn)
    ti = cols_i['TIME']
    ii = [cols_i[k] for k in hdr if k.upper().startswith('I(VDD')][0]
    pts = [(r[ti] * 1e9, -r[ii]) for r in rows if t0ns <= r[ti] * 1e9 <= t1ns]
    if not pts:
        print("no points in window"); return
    # bucket by column
    buckets = [[] for _ in range(cols)]
    for t, i in pts:
        c = int((t - t0ns) / (t1ns - t0ns) * (cols - 1))
        buckets[c].append(i)
    vals = [max(b) if b else None for b in buckets]
    fin = [v for v in vals if v is not None]
    lo, hi = min(fin), max(fin)
    if log:
        floor = max(1e-12, lo if lo > 0 else 1e-12)
        f = lambda v: math.log10(max(v, floor))
        ylo, yhi = f(floor), f(hi)
    else:
        f = lambda v: v
        ylo, yhi = 0.0, hi
    grid = [[' '] * cols for _ in range(rows_)]
    for c, v in enumerate(vals):
        if v is None: continue
        y = (f(v) - ylo) / (yhi - ylo) if yhi > ylo else 0
        r = rows_ - 1 - int(round(y * (rows_ - 1)))
        r = max(0, min(rows_ - 1, r))
        grid[r][c] = '*'
    print("  window %.3f..%.3f ns   %s scale   I_blk = -I(VDD)" %
          (t0ns, t1ns, "LOG" if log else "LIN"))
    for r in range(rows_):
        if log:
            v = 10 ** (yhi - (yhi - ylo) * r / (rows_ - 1))
        else:
            v = yhi - (yhi - ylo) * r / (rows_ - 1)
        lab = "%9.3g" % v if (r % 4 == 0 or r == rows_ - 1) else " " * 9
        print("%s |%s" % (lab, "".join(grid[r])))
    print("%9s +%s" % ("", "-" * cols))
    print("%9s  %-*s%s" % ("", cols - 10, "%.3f ns" % t0ns, "%.3f ns" % t1ns))

if __name__ == "__main__":
    prn = sys.argv[1]; a = float(sys.argv[2]); b = float(sys.argv[3])
    log = (len(sys.argv) < 5 or sys.argv[4] != "lin")
    render(prn, a, b, log=log)
