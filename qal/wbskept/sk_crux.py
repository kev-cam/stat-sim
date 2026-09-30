#!/usr/bin/env python3
"""SKEPTIC crux: does t_settle fall when driver AND load scale together?

Two jobs:
  (1) RE-RUN up.py's own cellchain variants A/B/C/D at s = 1/2/4/8 and
      re-extract with an INDEPENDENTLY WRITTEN measurement, so a coding bug in
      the record's crux.py would show up as a disagreement.
  (2) ADD variant E, which the record did NOT run.  qal/sg13lv_compat.sp
      DECLARES ad/as/pd/ps and DISCARDS them, so AD = AS = 1e-12 m^2 for EVERY
      device at EVERY width and junction capacitance is W-INDEPENDENT in every
      deck in this campaign.  A fixed self-load is exactly what 1/s dilution
      feeds on.  Variant E is variant A plus an EXPLICIT lumped capacitor of
      (s-1)*C_j at every cell output node, which is what AD proportional to W
      would have given.  C_j comes from MY OWN variant solve, not from a fit.

      PRE-STATED: if the record's caveat is right, E is FLATTER than A (ratio
      closer to 1) and the scale-invariance finding is STRONGER than the
      record's own numbers show.  If E is STEEPER, the caveat is backwards.
"""
import json, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import up

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, "/usr/local/src/stat-sim/qal/fcrit")
import rescore as FC
TRIP = FC.Trip("/usr/local/src/stat-sim/qal/fcrit/TRIP.json", "S")

MEAS = 3
SCALES = (1.0, 2.0, 4.0, 8.0)
C_WIRE = 2.00          # fF, EXACT: set in the deck by up.CLOAD


# ----------------------------------------------------- variant E deck
def deck_E(scale, rail, cj_fF, nstg=5):
    """variant A, plus (s-1)*cj_fF at every cell output node.  Built from
    up.cellchain_deck's variant A text and then patched, so the only difference
    from A is the added capacitors."""
    L = list(up.cellchain_deck(scale, rail, "A", nstg=nstg))
    add = (float(scale) - 1.0) * cj_fF
    if add <= 0:
        return L                      # s=1: E IS A, by construction
    out = []
    for ln in L:
        out.append(ln)
        if ln.startswith("CL"):       # right after each cell's wiring load
            j = ln.split()[0][2:]
            out.append("CJX%s s%s gnd0 %.9gf" % (j, j, add))
    return out


# ----------------------------------------------------- my own extraction
def read(path):
    hdr, rows = up.read_prn(path)
    ts = [r[1] * 1e12 for r in rows]
    ci = hdr.index("V(S%d)" % (MEAS - 1))
    co = hdr.index("V(S%d)" % MEAS)
    return ts, [r[ci] for r in rows], [r[co] for r in rows]


def xing(ts, vs, lvl, rising, t_from):
    """first linearly interpolated crossing of lvl at or after t_from."""
    for i in range(1, len(ts)):
        if ts[i] < t_from:
            continue
        a, b = vs[i - 1], vs[i]
        if rising and a < lvl <= b:
            return ts[i - 1] + (lvl - a) * (ts[i] - ts[i - 1]) / (b - a)
        if (not rising) and a > lvl >= b:
            return ts[i - 1] + (lvl - a) * (ts[i] - ts[i - 1]) / (b - a)
    return None


def stay_settled(ts, vs, rail, to_hi, t_from, t_to):
    """first instant in [t_from, t_to] at which the node is >=90% settled AND
    remains so through t_to.  Written as a BACKWARD scan -- deliberately a
    different implementation from the record's forward scan-and-reset, so the
    two disagree if either is wrong."""
    lvl = 0.90 * rail if to_hi else 0.10 * rail
    idx = [i for i in range(len(ts)) if t_from <= ts[i] <= t_to]
    if not idx:
        return None
    last = None
    for i in reversed(idx):
        good = (vs[i] >= lvl) if to_hi else (vs[i] <= lvl)
        if not good:
            break
        last = ts[i]
    return last


def one(path, rail):
    ts, vin, vout = read(path)
    vt, extrap = TRIP(rail)
    o = {}
    for lbl, t0, t1, in_rise in (("out_rise", 195.0, 495.0, False),
                                 ("out_fall", 495.0, ts[-1], True)):
        ti = xing(ts, vin, vt, in_rise, t0)
        t50i = xing(ts, vin, 0.5 * rail, in_rise, t0)
        t50o = xing(ts, vout, 0.5 * rail, not in_rise, t0)
        to_hi = not in_rise
        tset = stay_settled(ts, vout, rail, to_hi, ti, t1) if ti else None
        tfun = xing(ts, vout, vt, to_hi, ti) if ti else None
        o[lbl] = dict(t_in_trip_ps=ti,
                      t_pd50_ps=(t50o - t50i) if (t50o and t50i) else None,
                      t_set90_ps=(tset - ti) if (tset and ti) else None,
                      t_func_ps=(tfun - ti) if (tfun and ti) else None)
    for key in ("t_pd50_ps", "t_set90_ps", "t_func_ps"):
        v = [o[e][key] for e in ("out_rise", "out_fall") if o[e][key] is not None]
        o["worst_" + key] = max(v) if v else None
    o["vtrip_V"] = vt
    o["vtrip_frac"] = vt / rail
    o["vtrip_extrapolated"] = bool(extrap)
    return o


def fit(S, Y):
    """least squares t = a + b/s."""
    x = [1.0 / s for s in S]
    n = len(S)
    sx, sy = sum(x), sum(Y)
    sxx = sum(v * v for v in x)
    sxy = sum(v * w for v, w in zip(x, Y))
    d = n * sxx - sx * sx
    b = (n * sxy - sx * sy) / d
    a = (sy - b * sx) / n
    ybar = sy / n
    sst = sum((w - ybar) ** 2 for w in Y)
    ssr = sum((w - (a + b * v)) ** 2 for v, w in zip(x, Y))
    return a, b, (1.0 - ssr / sst if sst else None)


def run_variant(rail, v, s, cj=None):
    if v == "E":
        tag = "ck_r%d_E_s%g" % (round(rail * 10000), s)
        lines = deck_E(s, rail, cj)
    else:
        tag = "ck_r%d_%s_s%g" % (round(rail * 10000), v, s)
        lines = up.cellchain_deck(s, rail, v)
    p, msg = up.run("%s.cir" % tag, lines, timeout=1800)
    print("  %s %s" % (tag, msg), flush=True)
    return (tag, p)


if __name__ == "__main__":
    rail = float(sys.argv[1])
    v = sys.argv[2]
    s = float(sys.argv[3])
    cj = float(sys.argv[4]) if len(sys.argv) > 4 else None
    tag, p = run_variant(rail, v, s, cj)
    if p is None:
        sys.exit(1)
    o = one(p + ".prn", rail)
    o.update(rail=rail, variant=v, scale=s, tag=tag)
    json.dump(o, open(os.path.join(HERE, "ck_%s.json" % tag), "w"), indent=1)
    print("%s worst_t_set90=%.4f ps worst_pd50=%.4f ps"
          % (tag, o["worst_t_set90_ps"] or float("nan"),
             o["worst_t_pd50_ps"] or float("nan")), flush=True)
