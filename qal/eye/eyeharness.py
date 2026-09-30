#!/usr/bin/env python3
"""qal/eye harness.  Imports qal/banktank/bt.py VERBATIM and overrides exactly the
three things PRE_REGISTERED.json declares:

  (1) bt.PAT          -- the DATA (the pattern sweep IS the study)
  (2) the .tran print step / max step  -- 0.1/0.25 ps -> 0.05/0.10 ps
  (3) bt.HERE, bt.CACHE, bt.ENV  -- so every file this harness writes lands in
      qal/eye/ under qal/eye's OWN PYMS_VAE_CACHE, and NOTHING is written into
      qal/banktank (or qal/fastwave, qal/widebank, qal/cipher, all in flight).

Nothing in the netlist is added, removed or re-sized.  The .print list, the
.measure list, the cells, the tg15p triple, the A6 tank-referenced park, the
true-ZCS probe protocol and the 1F-integrator metering are bt.py's, untouched.
"""
import bisect, importlib.util, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
BTDIR = "/usr/local/src/stat-sim/qal/banktank"
TRIPJSON = "/usr/local/src/stat-sim/qal/fcrit/TRIP.json"
CACHE = os.path.join(
    "/tmp/claude-1001/-usr-local-src/4921ad0c-f17b-4b84-986a-5917c9ebd2a6",
    "scratchpad", "vae_cache_eye")

# ---- import bt.py verbatim, then redirect its filesystem side effects -------
_spec = importlib.util.spec_from_file_location("bt", os.path.join(BTDIR, "bt.py"))
bt = importlib.util.module_from_spec(_spec)
sys.modules["bt"] = bt
_spec.loader.exec_module(bt)

_COMMITTED_PAT = list(bt.PAT)               # [1,1,1,0,1,0,0,1]
_orig_schedule = bt.schedule


def redirect():
    os.makedirs(CACHE, exist_ok=True)
    bt.HERE = HERE
    bt.CACHE = CACHE
    bt.ENV = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS",
                  PYMS_VAE_CACHE=CACHE)


def set_steps(pstep, mstep):
    """Override ONLY the .tran print step and max-step ceiling."""
    def sched(*a, **kw):
        S = _orig_schedule(*a, **kw)
        S["pstep"], S["mstep"] = pstep, mstep
        return S
    bt.schedule = sched


def set_pattern(bits):
    bt.PAT[:] = list(bits)


PATTERNS = {                       # FIXED in PRE_REGISTERED.json, not editable
    "P0": [1, 1, 1, 0, 1, 0, 0, 1],
    "P1": [0, 0, 0, 0, 0, 0, 0, 0],
    "P2": [1, 1, 1, 1, 1, 1, 1, 1],
    "P3": [1, 0, 1, 0, 1, 0, 1, 0],
    "P4": [0, 1, 1, 0, 1, 1, 0, 1],
    "P5": [1, 0, 0, 0, 0, 0, 0, 0],
    # AMENDMENT E5: the remaining Hamming weights, so the INTERSECTION is over
    # EVERY distinct data vector an 8-gate bank can present (P4 proved the eye
    # depends only on the weight, not the arrangement).
    "W2": [1, 1, 0, 0, 0, 0, 0, 0],
    "W3": [1, 1, 1, 0, 0, 0, 0, 0],
    "W6": [1, 1, 1, 1, 1, 1, 0, 0],
    "W7": [1, 1, 1, 1, 1, 1, 1, 0],
}

# ---- the MEASURED trip curve: qal/fcrit/rescore.py class Trip, verbatim -----
class Trip(object):
    def __init__(self, path=TRIPJSON, tag="S"):
        d = json.load(open(path))[tag]
        self.tag, self.wp, self.wn = tag, d["wp"], d["wn"]
        ks = sorted(d["rows"], key=float)
        v = [d["rows"][k]["vdd"] for k in ks]
        t = [d["rows"][k]["trip_V"] for k in ks]
        w = [d["rows"][k]["window_10_90_mV"] for k in ks]
        keep = [i for i in range(len(v)) if t[i] is not None]
        self.v = [v[i] for i in keep]
        self.t = [t[i] for i in keep]
        self.w = [w[i] for i in keep]
        self.lo, self.hi = self.v[0], self.v[-1]

    def __call__(self, vdd):
        """(V_trip, extrapolated?) at this delivered rail."""
        if vdd <= self.lo:
            return self.t[0] * vdd / self.lo, True
        if vdd >= self.hi:
            return self.t[-1] * vdd / self.hi, True
        j = bisect.bisect_left(self.v, vdd)
        a, b = self.v[j - 1], self.v[j]
        return self.t[j - 1] + (self.t[j] - self.t[j - 1]) * (vdd - a) / (b - a), False
