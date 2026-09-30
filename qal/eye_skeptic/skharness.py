#!/usr/bin/env python3
"""SKEPTIC harness.  Imports qal/banktank/bt.py VERBATIM -- the ARRANGEMENT must
be bit-identical to the audited study or I am auditing a different circuit.

Overrides exactly three declared things, the same three the audited harness
overrode (so a difference in my numbers cannot be a harness difference):
  (1) bt.PAT      -- the data vector
  (2) the .tran print step / max step -> 0.05 / 0.10 ps
  (3) bt.HERE, bt.CACHE, bt.ENV -> qal/eye_skeptic/<sub> under MY OWN
      PYMS_VAE_CACHE (vae_cache_skeptic, built FROM EMPTY, distinct from the
      audited study's vae_cache_eye).

The MARGIN EXTRACTOR is NOT imported from them.  eyecalc.py / eyerun.py /
p2eye.py are never imported here; skcalc.py is written from the definition.
fcrit/TRIP.json IS read, because the measured decision curve is DATA.
"""
import bisect, importlib.util, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
BTDIR = "/usr/local/src/stat-sim/qal/banktank"
TRIPJSON = "/usr/local/src/stat-sim/qal/fcrit/TRIP.json"
CACHE = os.path.join(
    "/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6",
    "scratchpad", "vae_cache_skeptic")

_spec = importlib.util.spec_from_file_location("bt", os.path.join(BTDIR, "bt.py"))
bt = importlib.util.module_from_spec(_spec)
sys.modules["bt"] = bt
_spec.loader.exec_module(bt)

_orig_schedule = bt.schedule

PATTERNS = {
    "P0": [1, 1, 1, 0, 1, 0, 0, 1],   # committed, weight 5
    "P1": [0, 0, 0, 0, 0, 0, 0, 0],   # weight 0
    "P2": [1, 1, 1, 1, 1, 1, 1, 1],   # weight 8
    "P3": [1, 0, 1, 0, 1, 0, 1, 0],   # weight 4 -- the CALIBRATION pattern
}


def redirect(sub=None):
    d = os.path.join(HERE, sub) if sub else HERE
    os.makedirs(d, exist_ok=True)
    os.makedirs(CACHE, exist_ok=True)
    bt.HERE = d
    bt.CACHE = CACHE
    bt.ENV = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS",
                  PYMS_VAE_CACHE=CACHE)
    return d


def set_steps(pstep=0.05, mstep=0.10):
    def sched(*a, **kw):
        S = _orig_schedule(*a, **kw)
        S["pstep"], S["mstep"] = pstep, mstep
        return S
    bt.schedule = sched


def set_pattern(bits):
    bt.PAT[:] = list(bits)


class Trip(object):
    """Re-implemented from fcrit/TRIP.json.  Same DEFINITION as fcrit's class
    Trip (linear in trip_V vs vdd, proportional extrapolation outside), written
    out here rather than imported so the interpolation is independently coded.
    SK3 checks my table against the brief's quoted endpoints."""

    def __init__(self, path=TRIPJSON, tag="S"):
        d = json.load(open(path))[tag]
        self.tag, self.wp, self.wn = tag, d["wp"], d["wn"]
        rows = [(r["vdd"], r["trip_V"]) for r in d["rows"].values()
                if r["trip_V"] is not None]
        rows.sort()
        self.v = [a for a, _ in rows]
        self.t = [b for _, b in rows]
        self.n = len(rows)
        self.lo, self.hi = self.v[0], self.v[-1]

    def __call__(self, vdd):
        if vdd <= self.lo:
            return self.t[0] * vdd / self.lo, True
        if vdd >= self.hi:
            return self.t[-1] * vdd / self.hi, True
        j = bisect.bisect_left(self.v, vdd)
        v0, v1 = self.v[j - 1], self.v[j]
        t0, t1 = self.t[j - 1], self.t[j]
        return t0 + (t1 - t0) * (vdd - v0) / (v1 - v0), False

    def frac(self, vdd):
        t, ex = self(vdd)
        return t / vdd, ex
