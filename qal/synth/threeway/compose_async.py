#!/usr/bin/env python3
"""COMPOSED-FROM-MEASURED async cost for sha_slice.

Composes block energy and delay for a TH-cell netlist from the MEASURED per-arc
E(C_L) = E0 + k*C_L models and the MEASURED per-arc delay models, using:

  * PER-INSTANCE loads     C_L(inst) = sum of driven pin caps from the SPICE-gold
                           liberty th_cells_sg13g2_spice.lib (pF -> fF), or the
                           external-load assumption for a primary-output driver.
  * PER-INSTANCE arcs      each instance is classified EVERY VECTOR into the arc
                           that was actually characterized (which inputs are
                           asserted), so firing and NON-firing energy are both
                           counted, and correlation between "does it fire" and
                           "what does it drive" is preserved.
  * UNMEASURED arcs        are never silently folded into a measured one: they
                           are counted, bracketed [lo,hi], and reported.

This supersedes spice/compose_direct.py, which costed a HAND-DERIVED 96-cell mix
(th23 majority + a th22/th12 Ch mux) rather than the netlist the mapper actually
emitted, and which used a hand-estimated 8.402 fF carry load instead of the real
11.86 fF.  Nothing here runs SPICE.

usage: compose_async.py [netlist.v ...]
"""
import collections
import json
import random
import sys

sys.path.insert(0, "/usr/local/src/stat-sim/qal/synth/threeway")
import cost_inputs as C
import verify_direct as V

EXT = 2.0          # external load on a primary-output rail, fF (ASSUMED)
NV = 4000          # random DATA vectors

# ---------------------------------------------------------------------------
# MEASURED arc models.  (E0 fJ, k fJ/fF) for energy; (t0 ps, s ps/fF) for delay.
# Energy sources:
#   th22/th12/th13  spice/ce_th*.mt0          (prior session, refit here)
#   th23/th33/th34w2/th14  spice/cell_energy_th_direct.json  (this campaign)
# Delay sources: TD in the same .mt0 files.  th12/th13/th22 delay fits are done
# here from the three stored points (the fitter reproduces the published th22 and
# th12 ENERGY models exactly, which is the instrument check).
# ---------------------------------------------------------------------------
E = {
    "th22.2":   (39.3980, 1.7369),   "th22.1":   (0.0072, 0.0),
    "th12.1":   (23.0040, 1.4697),
    "th13.1":   (31.8610, 1.4688),
    "th14.1":   (44.8556, 1.4731),
    "th23.2":   (53.1111, 1.7567),   "th23.3":   (48.7470, 1.7364),
    "th23.1":   (0.0637, 0.0),
    "th33.3":   (40.9801, 1.7565),   "th33.2":   (0.0014, 0.0),
    "th34w2.A1m1": (65.4279, 1.8008),   # weight-2 arc, fires
    "th34w2.A0m3": (56.2279, 1.8268),   # 3-series BCD arc, fires
    "th34w2.A1m0": (0.0805, 0.0),       # no fire
    "th34w2.A0m2": (6.0884, 0.0),       # NO FIRE but 6.09 fJ -- real, load-indep
}
D = {                                    # delay, last-input-to-output
    "th23":   (204.27, 6.616),   # cin-late arc: the in-context ripple arc
    "th23s":  (239.78, 6.479),   # simultaneous 2-of-3
    "th33":   (315.87, 7.389),
    "th34w2": (284.44, 8.723),   # BCD arc, the slower of the two firing arcs
    "th14":   (236.93, 7.451),
    "th12":   (148.387, 6.1413), "th13": (186.267, 6.6638), "th22": (319.506, 7.2643),
}
# arcs with NO measurement: (nominal, lo, hi) as a function of the measured ones
UNMEAS = {
    # th12 is a plain NOR+inverter (th_gates.sp:17-24), no hysteresis: with both
    # inputs high the output swing is identical, only internal node N1 differs.
    "th12.2":      lambda cl: (E["th12.1"][0] + E["th12.1"][1] * cl,
                               E["th12.1"][0] + E["th12.1"][1] * cl,
                               1.15 * (E["th12.1"][0] + E["th12.1"][1] * cl)),
    # A high plus >=2 of BCD: fires through 2-3 PARALLEL A.X branches.
    "th34w2.A1m2": lambda cl: (E["th34w2.A1m1"][0] + E["th34w2.A1m1"][1] * cl,
                               E["th34w2.A1m1"][0] + E["th34w2.A1m1"][1] * cl,
                               E["th34w2.A1m1"][0] + E["th34w2.A1m1"][1] * cl + 6.0884),
    "th34w2.A1m3": lambda cl: (E["th34w2.A1m1"][0] + E["th34w2.A1m1"][1] * cl,
                               E["th34w2.A1m1"][0] + E["th34w2.A1m1"][1] * cl,
                               E["th34w2.A1m1"][0] + E["th34w2.A1m1"][1] * cl + 6.0884),
    # A low, exactly ONE of BCD: one pull-up PMOS off instead of two.  Bracket
    # between the measured A-only (0.0805) and the measured A0m2 (6.0884).
    "th34w2.A0m1": lambda cl: (3.0445, 0.0805, 6.0884),
    "th33.1":      lambda cl: (0.0014, 0.0, 0.0014),
}
PINS = ["a", "b", "c", "d"]


def arc(t, hi):
    """hi = list of 0/1 for pins a,b,c,d (present ones).  Return arc key or None."""
    n = sum(hi)
    if t in ("th12", "th13", "th14"):
        return None if n == 0 else "%s.%d" % (t, n)
    if t == "th22":
        return None if n == 0 else "th22.%d" % n
    if t == "th23":
        return None if n == 0 else "th23.%d" % n
    if t == "th33":
        return None if n == 0 else "th33.%d" % n
    if t == "th34w2":
        m = sum(hi[1:])
        if hi[0] == 0 and m == 0:
            return None
        return "th34w2.A%dm%d" % (hi[0], m)
    raise SystemExit("no arc model for cell type %s" % t)


def energy(key, cl):
    """-> (nominal, lo, hi, measured?)"""
    if key is None:
        return 0.0, 0.0, 0.0, True
    if key in E:
        e0, k = E[key]
        v = e0 + k * cl
        return v, v, v, True
    if key in UNMEAS:
        n, lo, hi = UNMEAS[key](cl)
        return n, lo, hi, False
    ct, _, k = key.partition(".")
    if ct in ("th12", "th13", "th14") and int(k) >= 2:
        # collector with >1 input asserted: NOR+inverter, same output swing;
        # only an internal series node differs.  Nominal = the measured 1-of-N
        # arc, upper bracket +15%.
        e0, kk = E["%s.1" % ct]
        v = e0 + kk * cl
        return v, v, 1.15 * v, False
    raise SystemExit("unhandled arc %s" % key)


def run(vfile, top="sha_slice", nv=NV, seed=4242):
    cells, ports = V.load(vfile, top)
    caps = C.pin_caps()
    # ---- per-instance load ------------------------------------------------
    sink = collections.defaultdict(list)
    for t, ins, y in cells:
        for p, n in zip(PINS, ins):
            sink[n].append((t, p))
    CL = {}
    missing = set()
    for t, ins, y in cells:
        cl = EXT if not sink[y] else 0.0
        for st, sp in sink[y]:
            if (st, sp) in caps:
                cl += caps[(st, sp)]
            else:
                missing.add("%s.%s" % (st, sp))
        CL[y] = cl
    net = V.Net(cells, ports)
    rnd = random.Random(seed)
    # ---- arc census over random DATA vectors ------------------------------
    hist = collections.Counter()
    en = collections.defaultdict(lambda: [0.0, 0.0, 0.0])   # type -> nom,lo,hi
    fire = collections.Counter()
    unmeas = collections.Counter()
    for _ in range(nv):
        val = net.drive({k: rnd.randrange(256) for k in "abcefg"})
        for t, ins, y in net.cells:
            hi = [val[i] for i in ins]
            key = arc(t, hi)
            n, lo, h, meas = energy(key, CL[y])
            b = en[t]
            b[0] += n; b[1] += lo; b[2] += h
            if val[y]:
                fire[t] += 1
            hist[(t, key)] += 1
            if not meas:
                unmeas[key] += 1
    ncell = collections.Counter(t for t, _, _ in cells)
    tot = [sum(en[t][i] for t in en) / nv for i in range(3)]
    return dict(vfile=vfile, cells=cells, ncell=ncell, CL=CL, nv=nv,
                hist=hist, en={t: [v / nv for v in b] for t, b in en.items()},
                fire={t: fire[t] / nv for t in ncell}, total=tot,
                unmeas={k: v / nv for k, v in unmeas.items()}, missing=missing,
                net=net, ports=ports)


def timing(r):
    """max-arrival longest path, per-arc measured delays at per-instance C_L."""
    cells, CL = r["cells"], r["CL"]
    drv = {y: (t, ins) for t, ins, y in cells}
    at, path = {}, {}

    def a(n):
        if n in at:
            return at[n]
        if n not in drv:
            at[n] = 0.0; path[n] = []
            return 0.0
        at[n] = 0.0
        t, ins = drv[n]
        # key on arrival ONLY: net ids are a mix of int and str ("0"/"1" for the
        # tied constant pins), so a tuple sort would compare them and blow up.
        arr = sorted(ins, key=a, reverse=True)
        best, bi = a(arr[0]), arr[0]
        second = a(arr[1]) if len(arr) > 1 else best
        # th23 has BOTH arcs measured: use the simultaneous-arrival arc when the
        # last two inputs land together, the (faster) late-input arc when the
        # last one is genuinely late.  Measured: late 204.27+6.616*CL is FASTER
        # than simultaneous 239.78+6.479*CL, because the early input has already
        # discharged its branch internal node.
        key = "th23s" if (t == "th23" and best - second < 50.0) else t
        t0, s = D[key]
        at[n] = best + t0 + s * CL[n]
        path[n] = path[bi] + [(t, CL[n], t0 + s * CL[n])]
        return at[n]
    worst, wname = 0.0, None
    for p, bits in r["ports"].items():
        for i, b in enumerate(bits):
            if b in drv and a(b) > worst:
                worst, wname = a(b), "%s[%d]" % (p, i)
    return worst, wname, path[r["ports"][wname.split("[")[0]][int(wname.split("[")[1][:-1])]]


def report(r):
    print("=" * 78)
    print("%s -- %d cells, ext load %.1f fF, %d vectors"
          % (r["vfile"], sum(r["ncell"].values()), EXT, r["nv"]))
    if r["missing"]:
        print("  !! NO LIBERTY PIN CAP (driver load UNDER-counted): %s"
              % ", ".join(sorted(r["missing"])))
    print("  %-8s %4s %8s %10s %10s %10s" % ("cell", "n", "fire/op", "E nom fJ", "E lo", "E hi"))
    for t in sorted(r["ncell"]):
        n, lo, hi = r["en"][t]
        print("  %-8s %4d %8.3f %10.2f %10.2f %10.2f"
              % (t, r["ncell"][t], r["fire"][t], n, lo, hi))
    nf = sum(r["fire"].values())
    nc = sum(r["ncell"].values())
    print("  TOTAL    %4d %8.2f firings/op (alpha=%.4f)" % (nc, nf, nf / nc))
    print("  BLOCK ENERGY  nominal %8.1f fJ/op   bracket [%.1f, %.1f]"
          % (r["total"][0], r["total"][1], r["total"][2]))
    print("  arc census (firings/op per arc):")
    for (t, k), v in sorted(r["hist"].items(), key=lambda x: -x[1]):
        if k is None:
            continue
        tag = "MEASURED" if k in E else "*** UNMEASURED ***"
        print("     %-14s %8.3f /op   %s" % (k, v / r["nv"], tag))
    if r["unmeas"]:
        print("  unmeasured-arc events/op: %.3f of %.2f firing-class events"
              % (sum(r["unmeas"].values()), nf))
    d, w, p = timing(r)
    print("  CRITICAL PATH  %.3f ns forward (to %s), %d TH levels" % (d / 1000.0, w, len(p)))
    for t, cl, dd in p:
        print("     %-8s CL=%6.3f fF  %7.2f ps" % (t, cl, dd))
    return r


if __name__ == "__main__":
    files = sys.argv[1:] or [
        "/usr/local/src/stat-sim/qal/synth/threeway/work/sha_slice_th_clean.v",
        "/usr/local/src/stat-sim/qal/synth/threeway/work/sha_slice_direct_spice.v",
        "/usr/local/src/stat-sim/qal/synth/threeway/work/sha_slice_direct_cd.v",
    ]
    out = {}
    for f in files:
        r = report(run(f))
        out[f] = dict(total=r["total"], alpha=sum(r["fire"].values()) / sum(r["ncell"].values()),
                      cells=dict(r["ncell"]), delay_ps=timing(r)[0])
        print()
    json.dump(out, open("/usr/local/src/stat-sim/qal/synth/threeway/work/async_recost.json", "w"), indent=1)
