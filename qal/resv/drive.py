#!/usr/bin/env python3
"""Sequenced runner: N concurrent heavy Xyce jobs (default 3 -- another workflow
shares this 16-core box).  Each job is `rv.py pt ...` in its own process, logging
to log_<tag>.txt, so a failure is isolated to one row.

usage: drive.py <maxpar> <tag> <L> <W> <dV> <CA_MULT> [cl] ; <tag> ... ; ...
       (arguments after the first are groups separated by the literal ';')
"""
import os, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))


def one(a):
    tag = a[0]
    cl = a[5] if len(a) > 5 else "6.91"
    cmd = ["python3", "rv.py", "pt", tag, a[1], a[2], a[3], a[4], "500", "inv", cl]
    t0 = time.monotonic()
    with open(os.path.join(HERE, "log_%s.txt" % tag), "w") as f:
        p = subprocess.run(cmd, cwd=HERE, stdout=f, stderr=subprocess.STDOUT)
    return "%-8s rc=%d %.0fs" % (tag, p.returncode, time.monotonic() - t0)


def main():
    maxpar = int(sys.argv[1])
    jobs, cur = [], []
    for w in sys.argv[2:]:
        if w == ";":
            if cur:
                jobs.append(cur); cur = []
        else:
            cur.append(w)
    if cur:
        jobs.append(cur)
    with ThreadPoolExecutor(max_workers=maxpar) as ex:
        for m in ex.map(one, jobs):
            print(m, flush=True)


if __name__ == "__main__":
    main()
