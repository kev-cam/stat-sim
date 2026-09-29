#!/usr/bin/env python3
"""SKEPTIC's OWN extractor.  Reads the RAW .prn ONLY -- never the .mt0.

Conventions are the COMMITTED ones, re-implemented here rather than imported from
tuextract.py, so that agreement between the two is evidence and not tautology:

  settling, pull-DOWN cell : 100*(1 - V(o_k_i)/V(rail_k))
  settling, pull-UP   cell : 100*(    V(o_k_i)/V(rail_k))
  kind                     : SK.is_hi(k,i) True  -> HIGH input  -> PULL-DOWN cell
  rail_k                   : read at the SAME instant as the output
  instant                  : bound_k, the TRUE stage boundary.

TIME CONVENTION, VERIFIED ON DISK BEFORE USE: the committed decks emit
`.measure ... AT=(bound_k + LAG_PS)` with LAG_PS = 1 ps, and that measure returns
the sample at bound_k itself (checked against qal/ptu's own .prn/.mt0 pair:
VR3K3 = 0.6689726 and the .prn at t = 400.0 ps = 0.66897258).  So this extractor
reads at bound_k and is directly comparable to the committed numbers.

Sampling uses LINEAR INTERPOLATION between printed points, not nearest-sample, so
a coarse print grid cannot bias a boundary read.  `at_nearest` is kept alongside
for the digit check against committed .mt0 values.
"""
import bisect
import sys

sys.path.insert(0, "/usr/local/src/stat-sim/qal/skip4")
import skip as SK


# ----------------------------------------------------------------- prn access
class PRN(object):
    def __init__(self, path):
        self.hdr, self.rows = SK.read_prn(path)
        self.t = [r[1] * 1e12 for r in self.rows]          # ps
        self.idx = {h: i for i, h in enumerate(self.hdr)}

    def col(self, name):
        n = name.upper()
        if n in self.idx:
            return self.idx[n]
        raise KeyError("%s not in prn (have e.g. %s)"
                       % (name, [h for h in self.hdr[:12]]))

    def at(self, name, tt):
        """Linear interpolation at tt (ps)."""
        ic = self.col(name)
        j = bisect.bisect_left(self.t, tt)
        if j <= 0:
            return self.rows[0][ic]
        if j >= len(self.t):
            return self.rows[-1][ic]
        t0, t1 = self.t[j - 1], self.t[j]
        v0, v1 = self.rows[j - 1][ic], self.rows[j][ic]
        if t1 == t0:
            return v1
        return v0 + (v1 - v0) * (tt - t0) / (t1 - t0)

    def at_nearest(self, name, tt):
        ic = self.col(name)
        best, bt = None, None
        for k, t in enumerate(self.t):
            if bt is None or abs(t - tt) < abs(bt - tt):
                bt, best = t, self.rows[k][ic]
        return best

    def window(self, name, ta, tb):
        ic = self.col(name)
        return [(self.t[k], self.rows[k][ic])
                for k in range(len(self.t)) if ta <= self.t[k] <= tb]


# ------------------------------------------------------------- the quantities
def settling(p, S, nb, use_interp=True):
    """Per-gate settling at every stage's own boundary.  NEVER aggregated."""
    rd = p.at if use_interp else p.at_nearest
    out = {}
    for k in range(1, nb + 1):
        bk = S["bound"][k]
        vr = rd("V(RAIL%d)" % k, bk)
        per = {}
        for i in range(8):
            vo = rd("V(O%d_%d)" % (k, i), bk)
            if vr is None or abs(vr) < 0.02:      # tuextract's own rail guard
                per[i] = dict(v_o=vo, kind="pulldown" if SK.is_hi(k, i) else "pullup",
                              settle_pct=None)
                continue
            f = (1.0 - vo / vr) if SK.is_hi(k, i) else (vo / vr)
            per[i] = dict(v_o=vo, kind="pulldown" if SK.is_hi(k, i) else "pullup",
                          settle_pct=100.0 * f)
        got = [v["settle_pct"] for v in per.values() if v["settle_pct"] is not None]
        out[k] = dict(bound_ps=bk, rail_at_bound_V=vr, per_gate=per,
                      worst_pct=(min(got) if got else None),
                      rail_below_guard=bool(vr is not None and abs(vr) < 0.02))
    return out


def separation(p, S, nb):
    """min(pull-UP output) - max(pull-DOWN output) within each bank, mV,
    each read at that bank's OWN boundary."""
    out = {}
    for k in range(1, nb + 1):
        bk = S["bound"][k]
        ups = [p.at("V(O%d_%d)" % (k, i), bk) for i in range(8) if not SK.is_hi(k, i)]
        dns = [p.at("V(O%d_%d)" % (k, i), bk) for i in range(8) if SK.is_hi(k, i)]
        sep = (min(ups) - max(dns)) * 1000.0
        out[k] = dict(min_pullup_V=min(ups), max_pulldown_V=max(dns),
                      separation_mV=sep,
                      below_sigma_vt_3p42=bool(abs(sep) < 3.42),
                      inverted=bool(sep < 0.0))
    return out


def delivered(p, S, nb):
    """Stage k's DELIVERED INPUT: the predecessor's outputs read at bound_k.
    HIGH inputs are the ones SK.is_hi(k,i) marks; the A2 gate is on their MINIMUM."""
    out = {}
    for k in range(2, nb + 1):
        bk = S["bound"][k]
        hi = [p.at("V(O%d_%d)" % (k - 1, i), bk) for i in range(8) if SK.is_hi(k, i)]
        lo = [p.at("V(O%d_%d)" % (k - 1, i), bk) for i in range(8) if not SK.is_hi(k, i)]
        out[k] = dict(min_delivered_HIGH_V=min(hi), max_delivered_LOW_V=max(lo),
                      A2_pass=bool(min(hi) >= 0.4400))
    return out


def predecessor_low(p, S, k_feeder):
    """D2/S2: the FEEDING stage's own pull-DOWN outputs at ITS OWN boundary --
    the victim of the step coupling.  max over the pull-down gates."""
    bk = S["bound"][k_feeder]
    vs = {i: p.at("V(O%d_%d)" % (k_feeder, i), bk)
          for i in range(8) if SK.is_hi(k_feeder, i)}
    return dict(bound_ps=bk, per_gate_V=vs, max_pulldown_V=max(vs.values()),
                mean_pulldown_V=sum(vs.values()) / len(vs))


def max_slope(p, name, ta, tb):
    """S1: max RISING dV/dt on a node over [ta, tb], V/ns, by centred finite
    difference on the printed grid.  Also returns the max |dV/dt|."""
    w = p.window(name, ta, tb)
    if len(w) < 3:
        return None
    best_up, best_abs, t_up = None, None, None
    for j in range(1, len(w) - 1):
        t0, v0 = w[j - 1]
        t1, v1 = w[j + 1]
        if t1 == t0:
            continue
        d = (v1 - v0) / (t1 - t0) * 1000.0            # V/ps -> V/ns
        if best_up is None or d > best_up:
            best_up, t_up = d, w[j][0]
        if best_abs is None or abs(d) > best_abs:
            best_abs = abs(d)
    return dict(max_rising_V_per_ns=best_up, at_ps=t_up,
                max_abs_V_per_ns=best_abs,
                window_ps=[ta, tb], n_samples=len(w))
