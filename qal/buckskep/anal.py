#!/usr/bin/env python3
"""SKEPTIC analysis. Reads .prn / .mt0 that I produced and computes every
number myself. Nothing is read from the prior agent's JSON."""
import sys, os, math, json

def read_prn(path):
    """-> (colnames, list-of-rows). Handles the Xyce .prn trailer line."""
    cols = None
    rows = []
    with open(path) as f:
        for ln in f:
            if cols is None:
                cols = ln.split()
                continue
            if ln.startswith("End of"):
                break
            p = ln.split()
            if len(p) != len(cols):
                continue
            try:
                rows.append([float(x) for x in p])
            except ValueError:
                continue
    return cols, rows

def read_mt0(path):
    d = {}
    with open(path) as f:
        for ln in f:
            if "=" in ln:
                k, v = ln.split("=", 1)
                k = k.strip().upper()
                v = v.strip().split()[0]
                try:
                    d[k] = float(v)
                except ValueError:
                    pass
    return d

class Trace:
    def __init__(self, path):
        self.cols, self.rows = read_prn(path)
        self.up = [c.upper() for c in self.cols]
        self.ti = self.up.index("TIME")
        self.t = [r[self.ti] for r in self.rows]
    def has(self, name):
        return name.upper() in self.up
    def col(self, name):
        j = self.up.index(name.upper())
        return [r[j] for r in self.rows]
    def at(self, name, tq):
        """linear interpolation at time tq (seconds)"""
        y = self.col(name); t = self.t
        if tq <= t[0]: return y[0]
        if tq >= t[-1]: return y[-1]
        lo, hi = 0, len(t) - 1
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if t[mid] <= tq: lo = mid
            else: hi = mid
        if t[hi] == t[lo]: return y[lo]
        f = (tq - t[lo]) / (t[hi] - t[lo])
        return y[lo] + f * (y[hi] - y[lo])
    def integ(self, name, t0, t1):
        """MY OWN trapezoidal integral of a printed current between t0 and t1
        (seconds). Independent of the deck's 1F integrators -- used to
        cross-check them."""
        y = self.col(name); t = self.t
        tot = 0.0
        for i in range(len(t) - 1):
            a, b = t[i], t[i+1]
            if b <= t0 or a >= t1: continue
            aa, bb = max(a, t0), min(b, t1)
            if bb <= aa: continue
            # interpolate endpoints
            fa = (aa - a) / (b - a) if b > a else 0.0
            fb = (bb - a) / (b - a) if b > a else 0.0
            ya = y[i] + fa * (y[i+1] - y[i])
            yb = y[i] + fb * (y[i+1] - y[i])
            tot += 0.5 * (ya + yb) * (bb - aa)
        return tot
    def window(self, name, t0, t1):
        y = self.col(name); t = self.t
        return [(t[i], y[i]) for i in range(len(t)) if t0 <= t[i] <= t1]

P = 1e-12
FC = 1e-15
