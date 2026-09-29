#!/usr/bin/env python3
"""qal/strip common: deck head, runner, .prn reader, waveform accessor.

Independently written for this study (the topology constants are inherited from
the committed qal/skept/sk.py bank and are named as such), so that no settling or
speed number in this run depends on .measure or on another study's extractor.
"""
import os, re, subprocess, time

HERE  = os.path.dirname(os.path.abspath(__file__))
XYCE  = "/usr/local/src/xyce-build/src/Xyce"
VA    = "/usr/local/share/xyce/verilog-a/psp103/psp103.va"
MODEL = "/usr/local/src/kestrel/sim/models/sg13g2_psp103_tt.lib"
SHIM  = "/usr/local/src/stat-sim/qal/sg13lv_compat.sp"
CACHE = ("/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6"
         "/scratchpad/vae_cache_strip")
ENV = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS", PYMS_VAE_CACHE=CACHE)

# ---- inherited committed constants (qal/skept/sk.py; NOT retuned here) -------
WP, WN = 1.12, 0.74          # campaign-standard cell widths (um)
CLOAD  = 2.0                 # fF per output node
CA_FF  = 35.979              # fF, committed MEASURED secant C of the source tank
T0     = 50.0                # ps, transfer gate closes
VGH    = 1.5                 # V, switch gate drive rail
RS     = 10.0                # ohm, inductor series R
EDGE   = 2.0                 # ps, transfer-gate edge
TAIL   = 500.0               # ps, post-freeze eventual-settle tail
LAG_PS = 1.0                 # ps, MEASURED .measure-FIND lag of this Xyce build

# ---- this study's own pre-registered constants ------------------------------
WXC     = 0.56               # um, cross-coupled pMOS PRIMARY width
WTREE   = 0.74               # um, tree nMOS width (= campaign WN)
BEAT_PS = 200.0              # ps, pre-registered primary beat


def head(extra=()):
    return ['.hdl "%s"' % VA, '.include "%s"' % MODEL, '.include "%s"' % SHIM,
            '.OPTIONS TIMEINT METHOD=GEAR RELTOL=1e-6 ABSTOL=1e-15 CHGTOL=1e-17'] \
        + list(extra)


def run(fn, lines, timeout=420, cwd=None):
    cwd = cwd or HERE
    p = os.path.join(cwd, fn)
    open(p, "w").write("\n".join(lines) + "\n")
    t = time.monotonic()
    try:
        r = subprocess.run([XYCE, fn], capture_output=True, text=True,
                           timeout=timeout, cwd=cwd, env=ENV)
    except subprocess.TimeoutExpired:
        return None, "TIMEOUT %gs %s" % (timeout, fn), timeout
    w = time.monotonic() - t
    if not os.path.exists(p + ".prn"):
        return None, "FAIL %s (%.0fs) %s" % (fn, w, r.stdout[-500:]), w
    return p, "%s ok %.0fs" % (fn, w), w


def read_prn(path):
    hdr, rows = None, []
    for ln in open(path):
        p = ln.split()
        if hdr is None and p and p[0].lower() == "index":
            hdr = [h.upper() for h in p]
            continue
        if hdr and p and (p[0][0].isdigit()):
            try:
                rows.append([float(x) for x in p])
            except ValueError:
                pass
    return hdr, rows


class W:
    """waveform accessor -- linear interpolation, times in ps"""

    def __init__(self, path, tscale=1e12):
        self.hdr, self.rows = read_prn(path)
        ti = None
        for i, h in enumerate(self.hdr):
            if h in ("TIME", "V(V-SWEEP)", "SWEEP"):
                ti = i
                break
        self.ti = 1 if ti is None else ti
        self.t = [r[self.ti] * tscale for r in self.rows]

    def col(self, name):
        n = name.upper()
        for i, h in enumerate(self.hdr):
            if h == n:
                return i
        for i, h in enumerate(self.hdr):
            if n in h:
                return i
        raise KeyError(name + " not in " + str(self.hdr))

    def v(self, name):
        c = self.col(name)
        return [r[c] for r in self.rows]

    def at(self, name, tps):
        y = self.v(name)
        if tps <= self.t[0]:
            return y[0]
        for k in range(1, len(self.t)):
            if self.t[k] >= tps:
                t0, t1 = self.t[k - 1], self.t[k]
                f = 0.0 if t1 == t0 else (tps - t0) / (t1 - t0)
                return y[k - 1] + f * (y[k] - y[k - 1])
        return y[-1]

    def cross(self, name, level, tmin=0.0, rising=True):
        y = self.v(name)
        for k in range(1, len(self.t)):
            if self.t[k] < tmin:
                continue
            a, b = y[k - 1], y[k]
            if (rising and a < level <= b) or (not rising and a > level >= b):
                t0, t1 = self.t[k - 1], self.t[k]
                f = 0.0 if b == a else (level - a) / (b - a)
                return t0 + f * (t1 - t0)
        return None


def integ(tg, expr):
    """1F integrator.  ALWAYS read t0-referenced against a 0.5 ps checkpoint."""
    return ["CX%s x%s 0 1" % (tg, tg), "BX%s 0 x%s I={ %s }" % (tg, tg, expr),
            "RX%s x%s 0 0.01" % (tg, tg)]


def parse_mt0(path):
    d = {}
    for ln in open(path):
        m = re.match(r"\s*(\w+)\s*=\s*(\S+)", ln)
        if m:
            try:
                d[m.group(1).upper()] = float(m.group(2))
            except ValueError:
                pass
    return d
