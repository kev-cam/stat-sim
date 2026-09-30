#!/usr/bin/env python3
"""SKEPTIC margin extractor.  Written from the DEFINITION, not imported from the
audited study.  eyecalc.py / eyerun.py / p2eye.py are never imported.

DEFINITION (the audited study's own, restated so it can be checked):
  link (bank k -> bank k+1, gate i): signal V(o{k}_{i}); receiver bank k+1.
  margin(k,i,t) = +1000*(V(o_k_i) - L)  if bank k cell i's expected output HIGH
                = -1000*(V(o_k_i) - L)  if LOW                            [mV]
  DATA reference (EYE2):  L = Trip_S( VR{k+1}B{k+1} ), a CONSTANT per link,
        VR{k+1}B{k+1} read from THIS row's own .mt0.
  RX reference (EYE1):    L = Trip_S( V(rail{k+1})(t) ), moving, plus the
        in-table mask V(rail{k+1}) in [0.20, 1.50] V.
  bank k's eye is OPEN at t iff min over the 8 gates of margin > threshold.
  the reported eye is the pointwise INTERSECTION over data patterns.

Everything below is min-over-gates FIRST (so both polarities present in a
pattern are inside the curve), then min-over-patterns.  The per-polarity curves
are computed too, but only as a DIAGNOSTIC -- the headline is always the
all-gates curve, which is the strictest.
"""
import bisect, gzip, json, math, os, sys
from array import array
import skharness as SK

GRID = 0.10
SIG_TRIP = 6.441          # mV  DERIVED-from-MEASURED, LOWER bound
SIG_LEVEL = 22.4          # mV  MEASURED qal/mcsize, driver delivered level
SIG_TOT = math.sqrt(SIG_TRIP ** 2 + SIG_LEVEL ** 2)
CONTOURS = [("0mV", 0.0),
            ("1sigma_trip", SIG_TRIP),
            ("3sigma_trip", 3.0 * SIG_TRIP),
            ("3sigma_total", 3.0 * SIG_TOT)]
TRIP = SK.Trip()


def load_prn(path, tmax):
    """Read .prn, resample every column onto a uniform GRID by linear
    interpolation.  A common grid is needed because the intersection is
    pointwise across patterns and the solver points differ."""
    hdr, raw = None, None
    for ln in open(path):
        p = ln.split()
        if hdr is None:
            if p and p[0].lower() == "index":
                hdr = [h.upper() for h in p]
                raw = [array("d") for _ in hdr]
            continue
        if not p or p[0].lower().startswith("end"):
            continue
        try:
            v = [float(x) for x in p]
        except ValueError:
            continue
        if len(v) != len(hdr):
            continue
        for ci in range(len(hdr)):
            raw[ci].append(v[ci])
    ti = hdr.index("TIME")
    t = [x * 1e12 for x in raw[ti]]
    nt = len(t)
    dtmax = max(t[i + 1] - t[i] for i in range(nt - 1))
    n = int(math.floor(tmax / GRID)) + 1
    idx = array("i", bytes(4 * n))
    j = 0
    for a in range(n):
        ta = a * GRID
        while j + 1 < nt and t[j + 1] < ta:
            j += 1
        idx[a] = j
    cols = {}
    for ci, nm in enumerate(hdr):
        if nm in ("INDEX", "TIME"):
            continue
        y = raw[ci]
        out = array("d", bytes(8 * n))
        for a in range(n):
            ta, jj = a * GRID, idx[a]
            if ta <= t[0]:
                out[a] = y[0]
            elif ta >= t[nt - 1]:
                out[a] = y[nt - 1]
            else:
                t0, t1 = t[jj], t[jj + 1]
                out[a] = y[jj] if t1 == t0 else \
                    y[jj] + (y[jj + 1] - y[jj]) * (ta - t0) / (t1 - t0)
        cols[nm] = out
        raw[ci] = None
    return cols, n, dict(n_solver_pts=nt, solver_dt_max_ps=dtmax,
                         solver_tmax_ps=t[nt - 1])


def margins(prn_path, mt0_path, bits, T, tend):
    """Return per-bank margin curves for ONE pattern.  min over the 8 gates is
    taken here, so the curve already spans both polarities present."""
    SK.set_pattern(bits)
    nb, mg = SK.bt.NBANK, SK.bt.MGATE
    C, n, meta = load_prn(prn_path, tend)
    d = SK.bt.parse_mt0(mt0_path)

    out = {}
    for k in range(1, nb):          # banks 1..3 only: MEASURED receivers
        kr = k + 1
        vrb = d["VR%dB%d" % (kr, kr)]
        Lfix, ex_fix = TRIP(vrb)
        rxrail = C["V(RAIL%d)" % kr]
        Lrx = array("d", bytes(8 * n))
        intab = bytearray(n)
        for a in range(n):
            v = rxrail[a]
            tv, ex = TRIP(v)
            Lrx[a] = tv
            intab[a] = 0 if (ex or not (TRIP.lo <= v <= TRIP.hi)) else 1

        pol = {i: bool(SK.bt.out_hi(k, i)) for i in range(mg)}
        dat_all = array("d", (1e9,) * n)
        rx_all = array("d", (1e9,) * n)
        dat_pol = {"HIGH": None, "LOW": None}
        rx_pol = {"HIGH": None, "LOW": None}
        for i in range(mg):
            v = C["V(O%d_%d)" % (k, i)]
            sg = 1.0 if pol[i] else -1.0
            nm = "HIGH" if pol[i] else "LOW"
            for a in range(n):
                md = 1000.0 * sg * (v[a] - Lfix)
                mr = 1000.0 * sg * (v[a] - Lrx[a])
                if md < dat_all[a]:
                    dat_all[a] = md
                if mr < rx_all[a]:
                    rx_all[a] = mr
            if dat_pol[nm] is None:
                dat_pol[nm] = array("d", (1e9,) * n)
                rx_pol[nm] = array("d", (1e9,) * n)
            for a in range(n):
                md = 1000.0 * sg * (v[a] - Lfix)
                mr = 1000.0 * sg * (v[a] - Lrx[a])
                if md < dat_pol[nm][a]:
                    dat_pol[nm][a] = md
                if mr < rx_pol[nm][a]:
                    rx_pol[nm][a] = mr
        out[k] = dict(DATA_all=dat_all, RX_all=rx_all,
                      DATA_pol=dat_pol, RX_pol=rx_pol,
                      intab=intab, L_fixed_V=Lfix, L_fixed_extrapolated=ex_fix,
                      rail_at_rx_boundary_V=vrb,
                      n_HIGH=sum(1 for i in range(mg) if pol[i]),
                      n_LOW=sum(1 for i in range(mg) if not pol[i]))
    return out, C, n, meta


def intersect(curves):
    """Pointwise min over patterns -- the INTERSECTION.  Truncated to the
    SHORTEST grid, the only correct common domain."""
    n = min(len(c) for c in curves)
    return array("d", (min(c[a] for c in curves) for a in range(n))), n


def first_run_edge(curve, n, lo_ps, thresh, mask=None):
    """FIRST contiguous open interval at or after lo_ps, with the opening edge
    located by SUB-GRID interpolation of the root of curve(t)=thresh.

    The guard the audited study needed (its AMENDMENT E6): interpolate ONLY if
    the previous grid point is on the FAILING side.  If it is already past the
    threshold, the mask edge was set by the auxiliary in-table condition and
    solving for the root would extrapolate BACKWARDS.
    """
    a0 = max(0, int(math.ceil(lo_ps / GRID)))
    a = a0
    while a < n:
        ok = curve[a] > thresh and (mask[a] if mask is not None else 1)
        if ok:
            if a == a0:
                return dict(open_ps=a * GRID, set_by="clipped_at_window_start")
            y0, y1 = curve[a - 1], curve[a]
            if y0 > thresh:
                return dict(open_ps=a * GRID,
                            set_by="auxiliary_condition_not_a_margin_crossing")
            if y1 == y0:
                return dict(open_ps=a * GRID, set_by="flat")
            return dict(open_ps=(a - 1) * GRID + (thresh - y0) * GRID / (y1 - y0),
                        set_by="margin_crossing")
        a += 1
    return None
