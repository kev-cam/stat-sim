#!/usr/bin/env python3
"""batch runner + extractor for the TRACK B amplifier decks."""
import os, sys, subprocess, math, json
HERE = os.path.dirname(os.path.abspath(__file__))
SP = ("/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6/"
      "scratchpad/vae_cache_ampB")
XYCE = "/usr/local/src/xyce-build/src/Xyce"
ENV = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS", PYMS_VAE_CACHE=SP)

def run(deck, timeout=900):
    t0 = os.times()
    p = subprocess.run([XYCE, deck], cwd=HERE, env=ENV, capture_output=True,
                       text=True, timeout=timeout)
    return p.returncode

def runall(decks, jobs=8):
    procs = []
    for d in decks:
        procs.append((d, subprocess.Popen(
            [XYCE, d], cwd=HERE, env=ENV,
            stdout=open(os.path.join(HERE, d.replace('.cir', '.log')), 'w'),
            stderr=subprocess.STDOUT)))
        while len([1 for _, q in procs if q.poll() is None]) >= jobs:
            os.wait()
    for d, q in procs: q.wait()
    return [(d, q.returncode) for d, q in procs]

# ---------------- prn io ----------------
def read_prn(p):
    rows, hdr = [], None
    for ln in open(p):
        f = ln.split()
        if hdr is None and f and f[0].lower() == 'index':
            hdr = [h.upper() for h in f]; continue
        if hdr and f and f[0][0].isdigit():
            try: rows.append([float(x) for x in f])
            except ValueError: pass
    return hdr, rows

class W:
    def __init__(self, path):
        self.hdr, self.rows = read_prn(path)
        self.t = [r[1] for r in self.rows]
    def has(self, n): return n.upper() in self.hdr
    def c(self, n): return self.hdr.index(n.upper())
    def v(self, n):
        i = self.c(n); return [r[i] for r in self.rows]
    def at(self, n, tps):
        i = self.c(n); prev = None
        for r in self.rows:
            if prev is not None and prev[0] <= tps*1e-12 <= r[1]:
                f = (tps*1e-12-prev[0])/(r[1]-prev[0]) if r[1] != prev[0] else 0.0
                return prev[1] + f*(r[i]-prev[1])
            prev = (r[1], r[i])
        return self.rows[-1][i]
    def E(self, n, t1, t0=0.0):
        """t=0-referenced 1F integrator read, in fJ."""
        return (self.at(n, t1) - self.at(n, t0))*1e15
    def env(self, n, t0, t1):
        """min,max of a node over a window (ps)."""
        i = self.c(n)
        s = [r[i] for r in self.rows if t0*1e-12 <= r[1] <= t1*1e-12]
        return (min(s), max(s)) if s else (float('nan'),)*2
    def zeros(self, n, lvl, t0=0.0):
        """rising crossings of lvl, in ps."""
        i = self.c(n); out = []; prev = None
        for r in self.rows:
            if prev is not None and r[1] > t0*1e-12 and prev[1] < lvl <= r[i]:
                f = (lvl-prev[1])/(r[i]-prev[1]) if r[i] != prev[1] else 0
                out.append((prev[0] + f*(r[1]-prev[0]))*1e12)
            prev = (r[1], r[i])
        return out
