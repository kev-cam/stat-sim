#!/usr/bin/env python3
"""COMPOSED-FROM-MEASURED async energy and latency for a large TH-cell netlist.

Same cost model as compose_async.py (same MEASURED E(C_L)=E0+k*C_L arc models,
same MEASURED delay models, same SPICE-gold liberty pin caps, same treatment of
unmeasured arcs as an explicit [lo,hi] bracket) but scaled to ~25k cells:

  * the arc census is BIT-PARALLEL.  Every net holds one Python int whose bit k
    is that net's value in DATA vector k, so N vectors cost one int op per cell;
    the per-cell arc histogram is then read out with 2**arity mask AND-popcounts.
    compose_async.py's per-vector Python loop would be 4000 x 25000 evaluations.
  * NON-FIRING arcs are counted and charged exactly as in compose_async.py
    (th22.1 = 0.0072 fJ, th23.1 = 0.0637 fJ, th33.2 = 0.0014 fJ ... and for the
    direct form on sha_slice th34w2.A0m2 = 6.0884 fJ while NOT firing).
  * boundary cell types (--boundary ncl_dff) have their outputs treated as free
    primary inputs, so a netlist with a register binding already in it can still
    be costed as a combinational cloud.

usage: compose_alu.py <netlist.v> <top> [--nv 1024] [--ext 2.0]
                      [--boundary ncl_dff] [--json out.json] [--label NAME]
"""
import collections
import json
import random
import subprocess
import sys

sys.path.insert(0, "/usr/local/src/stat-sim/qal/synth/threeway")
import cost_inputs as C

PINS = ["a", "b", "c", "d"]
ARITY = {"th12": 2, "th13": 3, "th14": 4, "th22": 2, "th23": 3, "th33": 3,
         "th24": 4, "th34": 4, "th44": 4, "th23w2": 3, "th34w2": 4}
WT = {"th12": ([1, 1], 1), "th13": ([1, 1, 1], 1), "th14": ([1, 1, 1, 1], 1),
      "th22": ([1, 1], 2), "th23": ([1, 1, 1], 2), "th33": ([1, 1, 1], 3),
      "th24": ([1, 1, 1, 1], 2), "th34": ([1, 1, 1, 1], 3),
      "th44": ([1, 1, 1, 1], 4), "th23w2": ([2, 1, 1], 2),
      "th34w2": ([2, 1, 1, 1], 3)}

# ---- MEASURED arc energy models, verbatim from compose_async.py ----------
E = {
    "th22.2":   (39.3980, 1.7369),   "th22.1":   (0.0072, 0.0),
    "th12.1":   (23.0040, 1.4697),
    "th13.1":   (31.8610, 1.4688),
    "th14.1":   (44.8556, 1.4731),
    "th23.2":   (53.1111, 1.7567),   "th23.3":   (48.7470, 1.7364),
    "th23.1":   (0.0637, 0.0),
    "th33.3":   (40.9801, 1.7565),   "th33.2":   (0.0014, 0.0),
    "th34w2.A1m1": (65.4279, 1.8008), "th34w2.A0m3": (56.2279, 1.8268),
    "th34w2.A1m0": (0.0805, 0.0),     "th34w2.A0m2": (6.0884, 0.0),
}
D = {"th23": (204.27, 6.616), "th23s": (239.78, 6.479), "th33": (315.87, 7.389),
     "th34w2": (284.44, 8.723), "th14": (236.93, 7.451),
     "th12": (148.387, 6.1413), "th13": (186.267, 6.6638), "th22": (319.506, 7.2643),
     "th34": (284.44, 8.723)}   # DERIVED: th34w2's measured 4-input BCD arc


# DERIVED BRACKET for TH34 (3-of-4).  TH34 has NO SG13G2 characterization.  Its
# firing arc is a 3-transistor series stack with four parallel branches, which
# sits structurally between the two MEASURED neighbours: TH33 (3-of-3, one
# 3-series branch) and TH34W2's A0m3 arc (its 3-series BCD branch).  Everything
# that uses this is labelled DERIVED-BRACKET, never MEASURED.
TH34_LO = (40.9801, 1.7565)      # = measured th33.3
TH34_HI = (56.2279, 1.8268)      # = measured th34w2.A0m3
TH34_NOFIRE_HI = 6.0884          # = measured th34w2.A0m2 (non-firing but real)


def energy(key, cl):
    """-> (nominal, lo, hi, measured?)  Identical policy to compose_async.py."""
    if key is None:
        return 0.0, 0.0, 0.0, True
    if key in E:
        e0, k = E[key]
        v = e0 + k * cl
        return v, v, v, True
    ct, _, k = key.partition(".")
    if ct == "th33" and k == "1":
        return 0.0014, 0.0, 0.0014, False
    if ct in ("th12", "th13", "th14") and k.isdigit() and int(k) >= 2:
        e0, kk = E["%s.1" % ct]
        v = e0 + kk * cl
        return v, v, 1.15 * v, False
    if ct == "th22" and k == "1":
        return E["th22.1"][0], E["th22.1"][0], E["th22.1"][0], True
    if ct == "th34w2":
        if k in ("A1m2", "A1m3"):
            e0, kk = E["th34w2.A1m1"]
            v = e0 + kk * cl
            return v, v, v + 6.0884, False
        if k == "A0m1":
            return 3.0445, 0.0805, 6.0884, False
    if ct == "th34":
        if k.isdigit() and int(k) >= 3:
            lo = TH34_LO[0] + TH34_LO[1] * cl
            hi = TH34_HI[0] + TH34_HI[1] * cl
            return 0.5 * (lo + hi), lo, hi, False
        return TH34_NOFIRE_HI / 2.0, 0.0, TH34_NOFIRE_HI, False
    if ct in ("th24", "th44", "th23w2"):
        return None, None, None, False       # no characterization at all
    raise SystemExit("unhandled arc %s" % key)


def arckey(t, hi):
    n = sum(hi)
    if n == 0:
        return None
    if t == "th34w2":
        return "th34w2.A%dm%d" % (hi[0], sum(hi[1:]))
    return "%s.%d" % (t, n)


def load(vfile, top, boundary):
    js = vfile + ".cost.json"
    stub = ""
    if boundary:
        stub = "".join("(* blackbox *) module %s(input clk, input d_L, input d_H,"
                       " output q_L, output q_H); endmodule\n" % b for b in boundary)
        open("/tmp/_stub.v", "w").write(stub)
    src = ("/tmp/_stub.v " if boundary else "") + vfile
    r = subprocess.run(["yosys", "-q", "-p",
                        "read_verilog %s; hierarchy -top %s; flatten; write_json %s"
                        % (src, top, js)], capture_output=True, text=True)
    if r.returncode:
        sys.exit("yosys failed:\n" + r.stderr)
    m = json.load(open(js))["modules"][top]
    cells, bcells, bsinks = [], [], []
    for cn, c in m["cells"].items():
        t = c["type"]
        if t in boundary:
            bcells.append([k(c["connections"][p][0]) for p in ("q_L", "q_H")
                           if p in c["connections"]])
            bsinks.extend(k(c["connections"][p][0]) for p in ("d_L", "d_H")
                          if p in c["connections"])
            continue
        if t not in ARITY:
            sys.exit("unknown cell type %s (%s)" % (t, cn))
        ins = [k(c["connections"][p][0]) for p in PINS if p in c["connections"]]
        cells.append((t, ins, k(c["connections"]["y"][0])))
    ports = {p: ([k(b) for b in v["bits"]], v["direction"]) for p, v in m["ports"].items()}
    return cells, ports, bcells, bsinks


def k(b):
    return b if isinstance(b, int) else str(b)


def topo(cells, driven):
    have = set(driven) | {"0", "1", "x"}
    out, pend = [], list(cells)
    while pend:
        nxt, prog = [], False
        for c in pend:
            if all(i in have for i in c[1]):
                out.append(c); have.add(c[2]); prog = True
            else:
                nxt.append(c)
        pend = nxt
        if not prog:
            sys.exit("combinational loop: %d cells stuck" % len(pend))
    return out


def run(vfile, top, nv, ext, boundary, label, clamp=0.0, tie1=()):
    cells, ports, bcells, bsinks = load(vfile, top, boundary)
    caps = C.pin_caps()
    sink = collections.defaultdict(list)
    for t, ins, y in cells:
        for p, n in zip(PINS, ins):
            sink[n].append((t, p))
    # A net that leaves the block carries the external load IN ADDITION to any
    # cell it drives inside it.  compose_async.py's rule (ext only when there is
    # no internal sink) silently zeroes the external load on, e.g., a register
    # output rail that also feeds its own is-DATA detector.
    outbits = set()
    for p, (bits, d) in ports.items():
        if d == "output":
            outbits.update(bits)
    CL, missing = {}, set()
    for t, ins, y in cells:
        cl = ext if (y in outbits or not sink[y]) else 0.0
        for st, sp in sink[y]:
            if (st, sp) in caps:
                cl += caps[(st, sp)]
            else:
                missing.add("%s.%s" % (st, sp))
        CL[y] = min(cl, clamp) if clamp else cl

    # ---- bit-parallel DATA evaluation -------------------------------------
    rnd = random.Random(424242)
    M = (1 << nv) - 1
    driven = set()
    inr = {}
    single = []
    tie = {}
    for p, (bits, d) in ports.items():
        if d != "input":
            continue
        if not (p.endswith("_L") or p.endswith("_H")):
            # a non-rail input (e.g. a clock in a sync-bound netlist): it plays
            # no part in the DATA-phase evaluation, drive it low and say so.
            single.append(p)
            for b in bits:
                driven.add(b)
                tie[b] = M if p in tie1 else 0
            continue
        base, r = p[:-2], p[-1]
        for i, b in enumerate(bits):
            inr.setdefault((base, i), {})[r] = b
            driven.add(b)
    if single:
        print("  non-rail inputs during the DATA census: %s"
              % ", ".join("%s=%d" % (p, 1 if p in tie1 else 0) for p in single))
    for pair in bcells:
        driven.update(pair)
    order = topo(cells, driven)
    v = {"0": 0, "1": M, "x": 0}
    for b, x in tie.items():
        v[b] = x
    for (base, i), r in inr.items():
        if "L" not in r or "H" not in r:
            continue
        val = rnd.getrandbits(nv)
        v[r["L"]] = val
        v[r["H"]] = ~val & M
    for pair in bcells:
        val = rnd.getrandbits(nv)
        if len(pair) == 2:
            v[pair[0]] = val; v[pair[1]] = ~val & M
    for t, ins, y in order:
        w, T = WT[t]
        vs = [v[x] for x in ins]
        if t in ("th12", "th13", "th14"):
            r = 0
            for x in vs:
                r |= x
        elif t == "th22":
            r = vs[0] & vs[1]
        elif t == "th33":
            r = vs[0] & vs[1] & vs[2]
        elif t == "th23":
            r = (vs[0] & vs[1]) | (vs[0] & vs[2]) | (vs[1] & vs[2])
        elif t == "th34":
            r = ((vs[0] & vs[1] & vs[2]) | (vs[0] & vs[1] & vs[3]) |
                 (vs[0] & vs[2] & vs[3]) | (vs[1] & vs[2] & vs[3]))
        elif t == "th34w2":
            r = (vs[0] & (vs[1] | vs[2] | vs[3])) | (vs[1] & vs[2] & vs[3])
        else:
            sys.exit("no bit-parallel model for %s" % t)
        v[y] = r & M

    # ---- arc histogram, bit-parallel --------------------------------------
    en = collections.defaultdict(lambda: [0.0, 0.0, 0.0])
    hist = collections.Counter()
    fire = collections.Counter()
    unmeas = collections.Counter()
    nocost = collections.Counter()
    bucket = {"hi": [0, 0.0], "lo": [0, 0.0]}
    for t, ins, y in cells:
        a = ARITY[t]
        vs = [v[x] for x in ins]
        neg = [~x & M for x in vs]
        for pat in range(1 << a):
            m = M
            for j in range(a):
                m &= vs[j] if (pat >> j & 1) else neg[j]
                if not m:
                    break
            if not m:
                continue
            cnt = m.bit_count()
            hi = [(pat >> j) & 1 for j in range(a)]
            key = arckey(t, hi)
            n, lo, h, meas = energy(key, CL[y])
            if n is None:
                nocost[t] += cnt
                continue
            b = en[t]
            b[0] += n * cnt; b[1] += lo * cnt; b[2] += h * cnt
            bucket["hi" if CL[y] > 50.0 else "lo"][1] += n * cnt
            hist[(t, key)] += cnt
            if not meas and key is not None:
                unmeas[key] += cnt
        fire[t] += v[y].bit_count()
        bucket["hi" if CL[y] > 50.0 else "lo"][0] += 1
    ncell = collections.Counter(t for t, _, _ in cells)
    total = [sum(en[t][i] for t in en) / nv for i in range(3)]
    return dict(label=label, vfile=vfile, cells=cells, ncell=ncell, CL=CL, nv=nv,
                hist=hist, en={t: [x / nv for x in b] for t, b in en.items()},
                fire={t: fire[t] / nv for t in ncell}, total=total,
                unmeas={kk: x / nv for kk, x in unmeas.items()},
                nocost={kk: x / nv for kk, x in nocost.items()},
                missing=missing, ports=ports, bcells=bcells, bucket=bucket,
                bsinks=bsinks, ext=ext)


def timing(r):
    cells, CL = r["cells"], r["CL"]
    drv = {y: (t, ins) for t, ins, y in cells}
    at, pth = {}, {}
    driven = set()
    for p, (bits, d) in r["ports"].items():
        if d == "input":
            driven.update(bits)
    for pair in r["bcells"]:
        driven.update(pair)
    order = topo(cells, driven)
    # iterative, in topological order (recursion would blow the stack at 25k)
    for t, ins, y in order:
        arr = sorted((at.get(x, 0.0) for x in ins), reverse=True)
        best = arr[0]
        second = arr[1] if len(arr) > 1 else best
        key = "th23s" if (t == "th23" and best - second < 50.0) else t
        t0, s = D[key]
        at[y] = best + t0 + s * CL[y]
        bi = max(ins, key=lambda x: at.get(x, 0.0))
        pth[y] = pth.get(bi, []) + [(t, CL[y], t0 + s * CL[y])]
    # ENDPOINTS: primary outputs AND the data inputs of any boundary cell (a
    # register's D rails).  Without the second set a netlist whose registers are
    # instantiated cells reports only PI->PO paths and silently omits every
    # PI->register path -- which on a 188-register block is most of them.
    ends = []
    for p, (bits, d) in r["ports"].items():
        if d == "output":
            for i, b in enumerate(bits):
                ends.append(("%s[%d]" % (p, i), b))
    for i, b in enumerate(r.get("bsinks", [])):
        ends.append(("regD[%d]" % i, b))
    worst, wn, wb = 0.0, None, None
    for nm, b in ends:
        if at.get(b, 0.0) > worst:
            worst, wn, wb = at[b], nm, b
    return worst, wn, pth.get(wb, [])


def report(r):
    nc = sum(r["ncell"].values())
    print("=" * 78)
    print("%s  --  %s" % (r["label"], r["vfile"]))
    print("  %d TH cells, %d DATA vectors, external load %.3f fF"
          % (nc, r["nv"], r["ext"]))
    if r["missing"]:
        print("  !! NO LIBERTY PIN CAP (driver load UNDER-counted): %s"
              % ", ".join(sorted(r["missing"])))
    if r["nocost"]:
        print("  !! CELLS WITH NO CHARACTERIZATION AT ALL: %s" % dict(r["nocost"]))
    print("  %-8s %6s %9s %10s %12s %12s %12s"
          % ("cell", "n", "meanCL", "fire/op", "E nom fJ", "E lo", "E hi"))
    for t in sorted(r["ncell"]):
        n, lo, hi = r["en"][t]
        L = [r["CL"][y] for tt, _, y in r["cells"] if tt == t]
        print("  %-8s %6d %9.3f %10.4f %12.1f %12.1f %12.1f"
              % (t, r["ncell"][t], sum(L) / len(L), r["fire"][t] / r["ncell"][t],
                 n, lo, hi))
    nf = sum(r["fire"].values())
    print("  TOTAL    %6d %9s %10.4f  (alpha = firings per cell per op)"
          % (nc, "", nf / nc))
    print("  BLOCK ENERGY  nominal %9.1f fJ/op   bracket [%.1f, %.1f]"
          % (r["total"][0], r["total"][1], r["total"][2]))
    bk = r["bucket"]
    print("  ENERGY SPLIT by driver load: %d cells with C_L > 50 fF (UNBUFFERED "
          "high fan-out) burn %.1f fJ/op = %.1f%%; the other %d cells burn %.1f fJ/op"
          % (bk["hi"][0], bk["hi"][1] / r["nv"], 100.0 * bk["hi"][1] /
             max(1e-9, bk["hi"][1] + bk["lo"][1]), bk["lo"][0], bk["lo"][1] / r["nv"]))
    if r.get("bsinks"):
        print("  NOTE: %d boundary-cell (register) input rails are timing endpoints; "
              "their pin capacitance is NOT in the SPICE-gold liberty, so the "
              "drivers of those rails are load-UNDERCOUNTED." % len(r["bsinks"]))
    print("  arc census (firings/op):")
    for (t, kk), x in sorted(r["hist"].items(), key=lambda z: -z[1])[:14]:
        if kk is None:
            continue
        print("     %-14s %10.3f /op   %s"
              % (kk, x / r["nv"], "MEASURED" if kk in E else "*** UNMEASURED ***"))
    if r["unmeas"]:
        print("  unmeasured-arc events/op: %.3f  (%s)"
              % (sum(r["unmeas"].values()),
                 ", ".join("%s %.2f" % (a, b) for a, b in
                           sorted(r["unmeas"].items(), key=lambda z: -z[1])[:5])))
    d, w, p = timing(r)
    print("  FORWARD LATENCY (DATA wavefront) %.3f ns to %s, %d TH levels"
          % (d / 1000.0, w, len(p)))
    lv = collections.Counter(t for t, _, _ in p)
    print("     path composition: %s" % dict(lv))
    return d


if __name__ == "__main__":
    a = sys.argv[1:]

    def opt(n, dd):
        return a[a.index(n) + 1] if n in a else dd
    nv = int(opt("--nv", "1024"))
    clamp = float(opt("--clamp", "0"))
    tie1 = set(x for x in opt("--tie1", "").split(",") if x)
    ext = float(opt("--ext", "2.0"))
    bnd = opt("--boundary", "")
    lab = opt("--label", "")
    jout = opt("--json", None)
    fl = ("--nv", "--ext", "--boundary", "--json", "--label", "--clamp", "--tie1")
    pos = [x for i, x in enumerate(a) if x not in fl and (i == 0 or a[i - 1] not in fl)]
    r = run(pos[0], pos[1], nv, ext, set(bnd.split(",")) - {""}, lab or pos[0], clamp, tie1)
    if clamp:
        print("  NOTE: per-instance loads CLAMPED at %.1f fF -- this stands in for a"
              " buffer tree on the high-fan-out nets; the buffers' OWN delay and"
              " energy are NOT included, so this is a LOWER BOUND." % clamp)
    dly = report(r)
    if jout:
        json.dump({"label": r["label"], "vfile": r["vfile"],
                   "cells": dict(r["ncell"]), "total_cells": sum(r["ncell"].values()),
                   "energy_fJ": r["total"], "alpha": sum(r["fire"].values()) / sum(r["ncell"].values()),
                   "fire_per_type": {t: r["fire"][t] for t in r["ncell"]},
                   "per_type_energy_fJ": r["en"],
                   "forward_latency_ps": dly,
                   "unmeasured_arc_events_per_op": sum(r["unmeas"].values()),
                   "nv": r["nv"]}, open(jout, "w"), indent=1)
