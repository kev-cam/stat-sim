#!/usr/bin/env python3
"""qal/mesh -- RESONANT MESH CLOCKING across the whole design.  PURE SPEED.

Everything scored here was fixed in PRE_REGISTERED.json (sha256 02f4cdd1...,
mtime 2026-09-30 10:31:39.924 -0700, the ONLY file in qal/mesh/ at that
instant) BEFORE this file existed.

Cells are qal/banktank/bt.py bank_cells() VERBATIM (pMOS 1.12u supply+bulk on
the phase node, nMOS 0.74u, CL 2 fF, metered per-bank ground VMG).  There is
NO transfer switch, NO per-bank inductor, NO timer, NO return schedule: banks
hang DIRECTLY off the mesh phases, odd banks on A, even on antiphase B.

Subcommands:
  ica                      anchor: committed banktank row, byte-identical, digit-checked
  icb                      single-bank sine smoke at the LARGEST half-period (130)
  lane <wave> <th> [f]     one (waveform, half-period) lane, d ascending w/ early stop
  one  <wave> <th> <d> <f> <pat> [rs]   one config: run + extract + delete .prn
  sawi                     the fixed-I current-driven ramp side experiment
  agg                      aggregate tables + frontier + ratios
"""
import importlib.util, json, math, os, re, subprocess, sys, time
from array import array

HERE   = os.path.dirname(os.path.abspath(__file__))
BTDIR  = "/usr/local/src/stat-sim/qal/banktank"
XYCE   = "/usr/local/src/xyce-build/src/Xyce"
VA     = "/usr/local/share/xyce/verilog-a/psp103/psp103.va"
MODEL  = "/usr/local/src/kestrel/sim/models/sg13g2_psp103_tt.lib"
SHIM   = "/usr/local/src/stat-sim/qal/sg13lv_compat.sp"
SCRATCH = ("/tmp/claude-1001/-usr-local-src/"
           "4921ad0c-f17b-4b84-986a-5917c9ebd2a6/scratchpad")
CACHE  = os.path.join(SCRATCH, "vae_cache_mesh")
ENV    = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS",
              PYMS_VAE_CACHE=CACHE)
TRIPJSON = "/usr/local/src/stat-sim/qal/fcrit/TRIP.json"

WP, WN  = 1.12, 0.74          # the committed cell (bt.py VERBATIM)
CLOAD   = 2.0                 # fF
DV      = 1.65                # V, full mesh swing
EDGE    = 2.0                 # ps, input word edges (bt.py committed edge)
LAG_PS  = 1.0                 # ps, MEASURED .measure-FIND lag of this Xyce build
NB, MG  = 6, 8
GRID    = 0.10                # ps, extraction grid
SIG_TOTAL_MV = 23.308         # MEASURED qal/eye/p2 U3
GATE_MV = 3 * SIG_TOTAL_MV    # 69.924 mV -- the budget with the timer GONE
T_CMOS  = 367.888             # ps, t_level 52.510 MEASURED + t_reg 315.378 DERIVED
T_CMOS_CORNER = 467.888       # ps, the 100 ps good-tree corner
PAT0    = [1, 1, 1, 0, 1, 0, 0, 1]
PATS    = {"P0": PAT0, "P2": [1]*8}


# ------------------------------------------------------------------ utilities
def run_xyce(rundir, fn, lines, timeout=3600):
    os.makedirs(rundir, exist_ok=True)
    path = os.path.join(rundir, fn)
    open(path, "w").write("\n".join(lines) + "\n")
    t0 = time.monotonic()
    try:
        r = subprocess.run([XYCE, fn], capture_output=True, text=True,
                           timeout=timeout, cwd=rundir, env=ENV)
    except subprocess.TimeoutExpired:
        return None, "TIMEOUT after %gs" % timeout
    wall = time.monotonic() - t0
    if r.returncode != 0 or not os.path.exists(path + ".prn"):
        err = "; ".join(l.strip() for l in r.stdout.splitlines()
                        if "rror" in l or "bort" in l)[:400]
        return None, "XYCE FAIL %s (%.1fs): %s" % (fn, wall, err or r.stdout[-300:])
    return path, "ran %s in %.1fs" % (fn, wall)


def parse_mt0(path):
    d = {}
    for ln in open(path):
        mm = re.match(r"\s*(\w+)\s*=\s*(\S+)", ln)
        if mm:
            try:
                d[mm.group(1).upper()] = float(mm.group(2))
            except ValueError:
                pass
    return d


class Trip(object):
    """qal/eye/eyeharness.py class Trip VERBATIM (fcrit/rescore.py lineage)."""
    def __init__(self, path=TRIPJSON, tag="S"):
        import bisect as _b
        self._b = _b
        d = json.load(open(path))[tag]
        ks = sorted(d["rows"], key=float)
        v = [d["rows"][k]["vdd"] for k in ks]
        t = [d["rows"][k]["trip_V"] for k in ks]
        keep = [i for i in range(len(v)) if t[i] is not None]
        self.v = [v[i] for i in keep]
        self.t = [t[i] for i in keep]
        self.lo, self.hi = self.v[0], self.v[-1]

    def __call__(self, vdd):
        if vdd <= self.lo:
            return self.t[0] * vdd / self.lo, True
        if vdd >= self.hi:
            return self.t[-1] * vdd / self.hi, True
        j = self._b.bisect_left(self.v, vdd)
        a, b = self.v[j - 1], self.v[j]
        return self.t[j - 1] + (self.t[j] - self.t[j - 1]) * (vdd - a) / (b - a), False


# ------------------------------------------------------------------ the deck
def head_lines():
    return ['.hdl "%s"' % VA, '.include "%s"' % MODEL, '.include "%s"' % SHIM,
            '.OPTIONS TIMEINT METHOD=GEAR RELTOL=1e-6 ABSTOL=1e-15 CHGTOL=1e-17']


def integ(tg, expr):
    return ["CX%s x%s 0 1" % (tg, tg), "BX%s 0 x%s I={ %s }" % (tg, tg, expr),
            "RX%s x%s 0 0.01" % (tg, tg)]


def slot(k, n, T, th):
    return n * T + (k - 1) * th


def bits(pat, k, j, n, d):
    """expected bit of bank k level j, wave n (PRE_REGISTERED scoring_definitions)"""
    return [pat[i] ^ (n & 1) ^ (((k - 1) * d + j) & 1) for i in range(MG)]


def crestoff(wave, T, th, fly):
    return th if wave == "sine" else (1.0 - fly) * T


def deck(wave, th, d, fly, patname, rs=0.001, nper=8.5):
    T = 2.0 * th
    pat = PATS[patname]
    tend = nper * T
    L = head_lines()
    # ---- the mesh phases: one driven source per bank (identical per phase) so
    # per-bank charge is metered and per-bank series R can be inserted.
    for k in range(1, NB + 1):
        A = (k % 2 == 1)
        if wave == "sine":
            ph = -90.0 if A else 90.0
            L.append("VPH%d phs%d 0 SIN(%g %g %g 0 0 %g)"
                     % (k, k, DV / 2, DV / 2, 1e12 / T, ph))
        else:
            if A:
                pts = [(0.0, 0.0)]
                for n in range(10):
                    pts += [((n + 1 - fly) * T, DV), ((n + 1) * T, 0.0)]
            else:
                pts = [(0.0, DV * 0.5 / (1.0 - fly)),
                       ((0.5 - fly) * T, DV), (0.5 * T, 0.0)]
                for n in range(10):
                    pts += [((n + 1.5 - fly) * T, DV), ((n + 1.5) * T, 0.0)]
            s = " ".join("%gp %g" % (t, v) if t > 0 else "0 %g" % v for t, v in pts)
            L.append("VPH%d phs%d 0 PWL(%s)" % (k, k, s))
        L.append("RS%d phs%d ph%d %g" % (k, k, k, rs))
    # ---- input words (chain head): alternate PAT / ~PAT at phase-A troughs
    for i in range(MG):
        pts, cur = [(0.0, DV * pat[i])], DV * pat[i]
        for n in range(1, 10):
            nxt = DV * (pat[i] ^ (n & 1))
            if nxt != cur:
                pts += [(n * T - EDGE / 2, cur), (n * T + EDGE / 2, nxt)]
                cur = nxt
        s = " ".join("%gp %g" % (t, v) if t > 0 else "0 %g" % v for t, v in pts)
        L.append("VI1_%d in1_%d 0 PWL(%s)" % (i, i, s))
    # ---- the banks: d series levels x 8 chains, cells bt.py VERBATIM
    for k in range(1, NB + 1):
        L.append("VMG%d gn%d 0 0" % (k, k))
        for j in range(1, d + 1):
            for i in range(MG):
                if j == 1:
                    src = "in1_%d" % i if k == 1 else "o%d_%d_%d" % (k - 1, d, i)
                else:
                    src = "o%d_%d_%d" % (k, j - 1, i)
                o = "o%d_%d_%d" % (k, j, i)
                L.append("XP%d_%d_%d %s %s ph%d ph%d sg13_lv_pmos w=%gu l=0.13u"
                         % (k, j, i, o, src, k, k, WP))
                L.append("XN%d_%d_%d %s %s gn%d gn%d sg13_lv_nmos w=%gu l=0.13u"
                         % (k, j, i, o, src, k, k, WN))
                L.append("CL%d_%d_%d %s gn%d %gf" % (k, j, i, o, k, CLOAD))
    # ---- metering: t0-referenced 1F integrators ONLY
    for k in range(1, NB + 1):
        L += integ("qph%d" % k, "-I(VPH%d)" % k)
        L += integ("eph%d" % k, "-V(ph%d)*I(VPH%d)" % (k, k))
        L += integ("qg%d" % k, "I(VMG%d)" % k)
    L.append(".tran 0.1p %gp 0 0.25p" % tend)
    # ---- measures: value checks at crests (waves 2..4), rails, integrator reads
    g = lambda t: t + LAG_PS
    co = crestoff(wave, T, th, fly)
    for n in (2, 3, 4):
        for k in range(1, NB + 1):
            tc = slot(k, n, T, th) + co
            L.append(".measure tran VRK%dW%d FIND V(ph%d) AT=%.6fp"
                     % (k, n, k, g(tc)))
            for j in range(1, d + 1):
                for i in range(MG):
                    L.append(".measure tran VK%d_%d_%dW%d FIND V(o%d_%d_%d) AT=%.6fp"
                             % (k, j, i, n, k, j, i, g(tc)))
    for k in range(1, NB + 1):
        for n in (2, 3, 4, 5):
            tt = slot(k, n, T, th)
            L.append(".measure tran QPH%dT%d FIND V(xqph%d) AT=%.6fp" % (k, n, k, g(tt)))
            L.append(".measure tran EPH%dT%d FIND V(xeph%d) AT=%.6fp" % (k, n, k, g(tt)))
            if n < 5:
                tc = tt + co
                L.append(".measure tran QPH%dC%d FIND V(xqph%d) AT=%.6fp" % (k, n, k, g(tc)))
                L.append(".measure tran EPH%dC%d FIND V(xeph%d) AT=%.6fp" % (k, n, k, g(tc)))
    pr = (["V(ph%d)" % k for k in range(1, NB + 1)] +
          ["V(o%d_%d_%d)" % (k, j, i) for k in range(1, NB + 1)
           for j in range(1, d + 1) for i in range(MG)] +
          ["I(VPH%d)" % k for k in range(1, NB + 1)] +
          ["I(VMG%d)" % k for k in range(1, NB + 1)])
    L.append(".print tran " + " ".join(pr))
    L.append(".end")
    return L, dict(wave=wave, th=th, T=T, d=d, fly=fly, pat=patname, rs=rs,
                   tend=tend, crestoff=co)


# ------------------------------------------------------------- prn -> grid
def load_grid(prn, tmax):
    hdr, raw = None, None
    for ln in open(prn):
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
    t = array("d", (x * 1e12 for x in raw[ti]))
    nt = len(t)
    n = int(math.floor(min(tmax, t[nt - 1]) / GRID)) + 1
    idx = array("i", bytes(4 * n))
    j = 0
    for a in range(n):
        ta = a * GRID
        while j + 1 < nt and t[j + 1] < ta:
            j += 1
        idx[a] = j
    cols = {}
    for ci, name in enumerate(hdr):
        if name in ("INDEX", "TIME"):
            continue
        y = raw[ci]
        out = array("d", bytes(8 * n))
        for a in range(n):
            ta = a * GRID
            jj = idx[a]
            if ta <= t[0]:
                out[a] = y[0]
            elif ta >= t[nt - 1]:
                out[a] = y[nt - 1]
            else:
                t0, t1 = t[jj], t[jj + 1]
                out[a] = y[jj] if t1 == t0 else \
                    y[jj] + (y[jj + 1] - y[jj]) * (ta - t0) / (t1 - t0)
        cols[name] = out
        raw[ci] = None
    return n, cols


# ------------------------------------------------------------- extraction
TRIPF = Trip()


def runs_of(mask, lo, hi):
    out, a = [], lo
    while a <= hi:
        if mask[a]:
            b = a
            while b + 1 <= hi and mask[b + 1]:
                b += 1
            out.append((a, b))
            a = b + 1
        else:
            a += 1
    return out


def edge_interp(curve, a, b, thr, n):
    """E1 rule: linear-interpolated threshold roots at the run edges.
    a, b, n are indices INTO curve (window-rebased); returns ps offsets
    relative to curve[0]'s instant."""
    ta, tb = a * GRID, b * GRID
    if a - 1 >= 0 and curve[a - 1] <= thr < curve[a]:
        y0, y1 = curve[a - 1], curve[a]
        ta = (a - 1) * GRID + (thr - y0) * GRID / (y1 - y0)
    if b + 1 < n and curve[b + 1] <= thr < curve[b]:
        y0, y1 = curve[b], curve[b + 1]
        tb = b * GRID + (thr - y0) * GRID / (y1 - y0)
    return ta, tb


def extract(rundir, S, keep_prn=False):
    d, T, th, wave, fly = S["d"], S["T"], S["th"], S["wave"], S["fly"]
    pat = PATS[S["pat"]]
    co = S["crestoff"]
    fn = [f for f in os.listdir(rundir) if f.endswith(".cir.prn")][0]
    prn = os.path.join(rundir, fn)
    mt0 = parse_mt0(prn[:-4] + ".mt0")
    n, C = load_grid(prn, S["tend"])
    out = dict(S)

    # ---- A: value check (from .mt0, the committed criterion)
    fails, checked = [], 0
    for nn in (2, 3, 4):
        for k in range(1, NB + 1):
            rail = mt0.get("VRK%dW%d" % (k, nn))
            for j in range(1, d + 1):
                bb = bits(pat, k, j, nn, d)
                for i in range(MG):
                    v = mt0.get("VK%d_%d_%dW%d" % (k, j, i, nn))
                    checked += 1
                    if v is None or rail is None:
                        fails.append([k, j, i, nn, "missing"])
                        continue
                    ok = (v >= 0.50 * rail) if bb[i] else (v <= 0.10 * rail)
                    if not ok:
                        fails.append([k, j, i, nn, round(v, 5), round(rail, 5)])
    out["crest_diag"] = dict(checked=checked, n_fail=len(fails),
                             fails=fails[:12],
                             note="AMENDMENT M2c: post-die diagnostic, not gating")

    # ---- eyes / commit / die / handoff per link per wave
    rails = {k: C["V(PH%d)" % k] for k in range(1, NB + 1)}
    outs = {k: {i: C["V(O%d_%d_%d)" % (k, d, i)] for i in range(MG)}
            for k in range(1, NB + 1)}
    links = {}
    tcommit = {}          # tcommit[(bank, wave)] = commit_raw ps (M4)
    tdieraw = {}
    for k in range(1, NB + 1):
        rx_rail = rails[k + 1] if k < NB else rails[1]   # link 6: DERIVED ideal A
        links[k] = {}
        for nn in (2, 3, 4):
            srx = slot(k + 1, nn, T, th)
            sk = srx - th                       # bank k's own rise start
            w0 = max(0, int((sk - 10.0) / GRID))
            w1 = min(n - 1, int((srx + co + th + 30.0) / GRID))
            bb = bits(pat, k, d, nn, d)
            # margin curves (mV) vs instantaneous trip; in-table-from-below gate
            trip = array("d", bytes(8 * (w1 - w0 + 1)))
            intab = bytearray(w1 - w0 + 1)
            n_extrap_hi = 0
            for a in range(w0, w1 + 1):
                v = rx_rail[a]
                t_, ex = TRIPF(v)
                trip[a - w0] = t_
                if v >= TRIPF.lo:
                    intab[a - w0] = 1
                    if ex:
                        n_extrap_hi += 1
            mcur = {"all": None, "HIGH": None, "LOW": None}
            for sel in ("all", "HIGH", "LOW"):
                gs = [i for i in range(MG)
                      if sel == "all" or (bb[i] == 1) == (sel == "HIGH")]
                if not gs:
                    continue
                cur = array("d", bytes(8 * (w1 - w0 + 1)))
                for a in range(w0, w1 + 1):
                    m = 1e9
                    for i in gs:
                        sg = 1.0 if bb[i] else -1.0
                        mm = 1000.0 * sg * (outs[k][i][a] - trip[a - w0])
                        if mm < m:
                            m = mm
                    cur[a - w0] = m
                mcur[sel] = cur
            rec = dict(rx_derived=(k == NB), wave=nn, srx_ps=srx)
            cur = mcur["all"]
            for thr_name, thr in (("0mV", 0.0), ("gate", GATE_MV)):
                mask = bytearray(w1 - w0 + 1)
                for a in range(w1 - w0 + 1):
                    mask[a] = 1 if (intab[a] and cur[a] > thr) else 0
                rr = runs_of(mask, 0, w1 - w0)
                # AMENDMENT M2a: LARGEST run intersecting the receiver's rise
                # window [srx, srx+co] (committed qal/eye pick="largest").
                r0 = int(srx / GRID) - w0
                r1 = int((srx + co) / GRID) - w0
                pick = None
                for (a, b) in rr:
                    if b >= r0 and a <= r1:
                        if pick is None or (b - a) > (pick[1] - pick[0]):
                            pick = (a, b)
                if pick is None:
                    rec[thr_name] = dict(EYE="EMPTY_in_rise_window",
                                         n_runs=len(rr))
                    continue
                a, b = pick
                ta, tb = edge_interp(cur, a, b, thr, w1 - w0 + 1)
                ta += w0 * GRID
                tb += w0 * GRID
                rec[thr_name] = dict(
                    open_ps=round(ta, 3), close_ps=round(tb, 3),
                    width_ps=round(tb - ta, 3),
                    open_minus_srx_ps=round(ta - srx, 3),
                    clipped_end=bool(b + w0 >= w1),
                    extrap_hi_fraction=round(n_extrap_hi / float(w1 - w0 + 1), 3))
                if thr_name == "0mV":
                    rec["commit_gated_ps"] = round(ta, 3)   # M2 convention, kept
                    rec["die_ps"] = round(tb, 3)
            # ---- AMENDMENT M4: commit_raw -- B's OWN act, un-gated from C's
            # rail: largest margin-positive run (trip extrapolated below the
            # table) intersecting bank k's OWN rise window [sk, sk+co].
            cur = mcur["all"]
            rmask = bytearray(w1 - w0 + 1)
            for a in range(w1 - w0 + 1):
                rmask[a] = 1 if cur[a] > 0.0 else 0
            rr2 = runs_of(rmask, 0, w1 - w0)
            q0 = int(sk / GRID) - w0
            q1 = int((sk + co + 0.5 * th) / GRID) - w0   # M4c: POWERED window
            pick2 = None
            for (a, b) in rr2:
                if b >= q0 and a <= q1:
                    if pick2 is None or (b - a) > (pick2[1] - pick2[0]):
                        pick2 = (a, b)
            if pick2 is not None:
                ta2, tb2 = edge_interp(cur, pick2[0], pick2[1], 0.0, w1 - w0 + 1)
                rec["commit_raw_ps"] = round(ta2 + w0 * GRID, 3)
                rec["die_raw_ps"] = round(tb2 + w0 * GRID, 3)
                tcommit[(k, nn)] = ta2 + w0 * GRID
                tdieraw[(k, nn)] = tb2 + w0 * GRID
            else:
                rec["commit_raw_ps"] = None
                tcommit.pop((k, nn), None)

            # margins at the receiver crest instant, both polarities
            probe = int((srx + co) / GRID) - w0
            rec["margin_at_rx_crest_mV"] = {
                sel: (round(mcur[sel][probe], 2) if mcur[sel] is not None else None)
                for sel in ("all", "HIGH", "LOW")}
            links[k][nn] = rec

    # margin AT the commit sample (t_commit(k+1)) + handoff overlap, links 1..5
    handoff = {}
    for k in range(1, NB):
        handoff[k] = {}
        for nn in (2, 3, 4):
            tc_rx = tcommit.get((k + 1, nn))
            die = links[k][nn].get("die_ps")
            rec = dict(t_commit_rx_ps=tc_rx, t_die_ps=die)
            if tc_rx is not None and die is not None:
                rec["overlap_ps"] = round(die - tc_rx, 3)
            if tc_rx is not None:
                a = min(n - 1, int(tc_rx / GRID))
                srx = slot(k + 1, nn, T, th)
                w0 = max(0, int((srx - 10.0) / GRID))
                # recompute margins at that instant (cheap, per-gate)
                rx_rail = rails[k + 1]
                t_, ex = TRIPF(rx_rail[a])
                bb = bits(pat, k, d, nn, d)
                ms = {"HIGH": 1e9, "LOW": 1e9}
                for i in range(MG):
                    sg = 1.0 if bb[i] else -1.0
                    mm = 1000.0 * sg * (outs[k][i][a] - t_)
                    key = "HIGH" if bb[i] else "LOW"
                    ms[key] = min(ms[key], mm)
                rec["margin_at_commit_mV"] = {
                    kk: (round(v, 2) if v < 1e8 else None) for kk, v in ms.items()}
                rec["trip_at_commit_V"] = round(t_, 4)
                rec["trip_extrapolated"] = bool(ex)
            handoff[k] = handoff.get(k, {})
            handoff[k][nn] = rec
    out["links"] = links
    out["handoff"] = handoff

    # ---- AMENDMENT M2b: value AT THE COMMIT, all 6 links, waves 2..4
    allout = {k: {j: {i: C["V(O%d_%d_%d)" % (k, j, i)] for i in range(MG)}
                  for j in range(1, d + 1)} for k in range(1, NB + 1)}
    vfails, vchecked, interior_diag = [], 0, []
    for k in range(1, NB + 1):
        for nn in (2, 3, 4):
            tc = tcommit.get((k, nn))
            td = tdieraw.get((k, nn))
            if tc is None:
                vfails.append([k, nn, "NO_COMMIT"])
                continue
            a = min(n - 1, int(0.5 * (tc + (td if td else tc)) / GRID))  # M4b
            rx_rail = rails[k + 1] if k < NB else rails[1]
            trx, _ = TRIPF(rx_rail[a])
            town, _ = TRIPF(rails[k][a])
            for j in range(1, d + 1):
                bb = bits(pat, k, j, nn, d)
                tref = trx if j == d else town
                for i in range(MG):
                    v = allout[k][j][i][a]
                    ok = (v > tref) if bb[i] else (v < tref)
                    if j == d:                     # M4d: gate the WORD only
                        vchecked += 1
                        if not ok:
                            vfails.append([k, j, i, nn, round(v, 4),
                                           round(tref, 4)])
                    elif not ok:
                        interior_diag.append([k, j, i, nn, round(v, 4),
                                              round(tref, 4)])
    out["value"] = dict(checked=vchecked, n_fail=len(vfails),
                        fails=vfails[:20], PASS=(not vfails),
                        interior_stale_diag_n=len(interior_diag),
                        interior_stale_diag=interior_diag[:10],
                        note="M2b/M4b/M4d: last-level word at validity midpoint")

    # ---- AMENDMENT M2d: rising-side tracking lag per bank (waves 2..4)
    lags = []
    for k in range(1, NB + 1):
        for nn in (2, 3, 4):
            s0 = slot(k, nn, T, th)
            a0 = max(1, int(s0 / GRID))
            a1 = min(n - 1, int((s0 + co) / GRID))
            tr50 = to50 = None
            for a in range(a0, a1 + 1):
                if tr50 is None and rails[k][a - 1] < 0.5 * DV <= rails[k][a]:
                    tr50 = a * GRID
                    break
            bb = bits(pat, k, d, nn, d)
            his = [i for i in range(MG) if bb[i]]
            if his and tr50 is not None:
                worst = None
                for i in his:
                    y = allout[k][d][i]
                    for a in range(a0, min(n - 1, a1 + int(1.5 * th / GRID))):
                        if y[a - 1] < 0.5 * DV <= y[a]:
                            worst = max(worst or 0, a * GRID - tr50)
                            break
                if worst is not None:
                    lags.append(round(worst, 1))
    out["rising_lag_ps"] = dict(
        min=min(lags) if lags else None, max=max(lags) if lags else None,
        median=sorted(lags)[len(lags) // 2] if lags else None)

    # ---- coupling: aggressor edge into antiphase logic nodes
    coup = []
    if wave == "saw":
        for nn in (2, 3, 4):     # A-phase flyback aggressor windows
            fa0, fa1 = (nn + 1 - fly) * T, (nn + 1) * T
            for vk in (2, 4, 6):
                if vk > NB:
                    continue
                wn = nn - (vk - 2) // 2
                bb = bits(pat, vk, d, wn, d)
                lows = [i for i in range(MG) if bb[i] == 0]
                if not lows:
                    continue
                a0, a1 = int(fa0 / GRID), min(n - 1, int(fa1 / GRID))
                s0 = int(slot(vk, wn, T, th) / GRID)
                s1 = min(n - 1, int((slot(vk, wn, T, th) + co) / GRID))
                if not (s0 <= a0 <= s1):
                    continue
                inw = max(outs[vk][i][a] for i in lows for a in range(a0, a1 + 1))
                ref = max(outs[vk][i][a] for i in lows
                          for a in range(s0, s1 + 1)
                          if a < a0 - 50 or a > a1 + 50)
                coup.append(dict(wave=nn, victim_bank=vk,
                                 bump_LOW_mV=round(1000 * (inw - ref), 2)))
    else:
        for nn in (2, 3, 4):     # sine: antiphase max |dV/dt| at quarter periods
            tq = (nn + 0.75) * T          # A falling fastest
            for vk in (2, 4, 6):
                if vk > NB:
                    continue
                wn = nn - (vk - 2) // 2
                bb = bits(pat, vk, d, wn, d)
                lows = [i for i in range(MG) if bb[i] == 0]
                if not lows:
                    continue
                a0, a1 = int((tq - 5) / GRID), min(n - 1, int((tq + 5) / GRID))
                s0 = int(slot(vk, wn, T, th) / GRID)
                s1 = min(n - 1, int((slot(vk, wn, T, th) + co) / GRID))
                if not (s0 <= a0 <= s1):
                    continue
                inw = max(outs[vk][i][a] for i in lows for a in range(a0, a1 + 1))
                ref = max(outs[vk][i][a] for i in lows
                          for a in range(s0, s1 + 1)
                          if a < a0 - 50 or a > a1 + 50)
                coup.append(dict(wave=nn, victim_bank=vk,
                                 bump_LOW_mV=round(1000 * (inw - ref), 2)))
    worst = max((c["bump_LOW_mV"] for c in coup), default=None)
    out["coupling"] = dict(worst_bump_LOW_mV=worst, rows=coup[:12])

    # ---- crowbar check at trough, interior banks 3 (A) and 4 (B)
    crow = {}
    for k in [b for b in (3, 4) if b <= NB] or [NB]:
        rows = []
        for nn in (3, 4):
            tt = slot(k, nn, T, th)
            a0, a1 = max(0, int((tt - 2) / GRID)), min(n - 1, int((tt + 2) / GRID))
            img = [C["I(VMG%d)" % k][a] for a in range(a0, a1 + 1)]
            iph = [C["I(VPH%d)" % k][a] for a in range(a0, a1 + 1)]
            lo0 = tt
            while lo0 > 0 and rails[k][int(lo0 / GRID)] < 0.1 * DV:
                lo0 -= GRID
            hi0 = tt
            while hi0 < (n - 1) * GRID and rails[k][int(hi0 / GRID)] < 0.1 * DV:
                hi0 += GRID
            b0, b1 = max(0, int(lo0 / GRID)), min(n - 1, int(hi0 / GRID))
            imgw = [C["I(VMG%d)" % k][a] for a in range(b0, b1 + 1)]
            rows.append(dict(
                wave=nn, trough_ps=tt,
                Ignd_pk_uA=round(max(abs(x) for x in img) * 1e6, 3),
                Ignd_mean_uA=round(sum(img) / len(img) * 1e6, 4),
                Iph_pk_uA=round(max(abs(x) for x in iph) * 1e6, 3),
                rail_lt_10pct_window_ps=round(hi0 - lo0, 1),
                Ignd_mean_10pct_uA=round(sum(imgw) / len(imgw) * 1e6, 4),
                Q_gnd_10pct_fC=round(sum(imgw) * GRID * 1e3, 4)))
        crow[k] = rows
    out["crowbar"] = crow

    # ---- the mesh interface spec: charge per bank per phase (steady state)
    ch = {}
    for k in range(1, NB + 1):
        qr, qf, er = [], [], []
        for nn in (2, 3, 4):
            qt = mt0.get("QPH%dT%d" % (k, nn))
            qc = mt0.get("QPH%dC%d" % (k, nn))
            qt2 = mt0.get("QPH%dT%d" % (k, nn + 1))
            et = mt0.get("EPH%dT%d" % (k, nn))
            ec = mt0.get("EPH%dC%d" % (k, nn))
            if None not in (qt, qc, qt2):
                qr.append((qc - qt) * 1e15)      # fC sourced on the rise
                qf.append((qt2 - qc) * 1e15)     # fC on the fall (negative=reabsorbed)
            if None not in (et, ec):
                er.append((ec - et) * 1e15)      # fJ delivered on the rise
        if qr:
            ch[k] = dict(Q_rise_fC=round(sum(qr) / len(qr), 3),
                         Q_fall_fC=round(sum(qf) / len(qf), 3),
                         E_rise_fJ=round(sum(er) / len(er), 3) if er else None)
    out["charge_spec_reported_not_gated"] = ch

    # ---- acceptance (PRE_REGISTERED A+B+C)
    b_ok, c_ok, worst_m, worst_ov = True, True, None, None
    for k in range(1, NB):
        for nn in (2, 3, 4):
            h = handoff[k][nn]
            m = h.get("margin_at_commit_mV")
            if not m or all(v is None for v in m.values()):
                b_ok = False
                continue
            lo = min(v for v in m.values() if v is not None)
            worst_m = lo if worst_m is None else min(worst_m, lo)
            if lo < GATE_MV:
                b_ok = False
            ov = h.get("overlap_ps")
            if ov is None or ov <= 0:
                c_ok = False
            if ov is not None:
                worst_ov = ov if worst_ov is None else min(worst_ov, ov)
    out["acceptance"] = dict(A_value=out["value"]["PASS"], B_eye=b_ok,
                             C_handoff=c_ok,
                             worst_margin_at_commit_mV=worst_m,
                             worst_overlap_ps=worst_ov,
                             PASS=bool(out["value"]["PASS"] and b_ok and c_ok))
    json.dump(out, open(os.path.join(rundir, "OUT.json"), "w"), indent=1)
    if not keep_prn:
        subprocess.run(["gzip", "-f", prn])
    return out


# ------------------------------------------------------------- subcommands
def tag_of(wave, th, d, fly, pat, rs=0.001):
    t = "%s_th%g_d%d" % (wave, th, d)
    if wave == "saw":
        t += "_f%g" % (100 * fly)
    if pat != "P0":
        t += "_" + pat
    if rs != 0.001:
        t += "_rs%g" % rs
    return t


def cmd_one(wave, th, d, fly, patname, rs=0.001, keep_prn=False):
    tag = tag_of(wave, th, d, fly, patname, rs)
    rundir = os.path.join(HERE, "runs", tag)
    oj = os.path.join(rundir, "OUT.json")
    if os.path.exists(oj):
        print("  cached", tag)
        return json.load(open(oj))
    lines, S = deck(wave, th, d, fly, patname, rs)
    p, msg = run_xyce(rundir, "c_%s.cir" % tag, lines,
                      timeout=1200 + 900 * d)
    print("  %s %s" % (tag, msg), flush=True)
    if p is None:
        json.dump(dict(S, error=msg), open(oj, "w"), indent=1)
        return dict(S, error=msg, acceptance=dict(PASS=False))
    o = extract(rundir, S, keep_prn)
    a = o["acceptance"]
    print("  %s value=%s eye=%s handoff=%s worst_margin=%s worst_ov=%s -> %s"
          % (tag, a["A_value"], a["B_eye"], a["C_handoff"],
             a["worst_margin_at_commit_mV"], a["worst_overlap_ps"],
             "PASS" if a["PASS"] else "FAIL"), flush=True)
    return o


def cmd_lane(wave, th, fly):
    res = {}
    for d in (1, 2, 3, 4):     # AMENDMENT M3: full grid, no early stop
        o = cmd_one(wave, th, d, fly, "P0")
        res[d] = o["acceptance"]["PASS"] if "acceptance" in o else False
    return 0


def cmd_ica():
    """ANCHOR: committed banktank headline row, byte-identical, digit-checked
    (the rf.py cmd_ic1 protocol under qal/mesh's own cache)."""
    spec = importlib.util.spec_from_file_location("bt", os.path.join(BTDIR, "bt.py"))
    bt = importlib.util.module_from_spec(spec)
    sys.modules["bt"] = bt
    spec.loader.exec_module(bt)
    sub = os.path.join(HERE, "ica")
    os.makedirs(sub, exist_ok=True)
    bt.HERE, bt.CACHE = sub, CACHE
    bt.ENV = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS",
                  PYMS_VAE_CACHE=CACHE)
    bt.VGH = 1.5
    bt.PAT[:] = [1, 1, 1, 0, 1, 0, 0, 1]
    z = json.load(open(os.path.join(BTDIR, "zeros_m10_dv1200_T200_H4.json")))
    lines, S = bt.deck(10.0, 200.0, 4, 1.2, mode="free", tzr=z["tzr"], tzq=z["tzq"])
    mine = "\n".join(lines) + "\n"
    committed = open(os.path.join(BTDIR, "c_m10_T200_H4_dv1200_free.cir")).read()
    ident = (mine == committed)
    print("ICA deck byte-identical to committed:", ident, flush=True)
    fn = "c_m10_T200_H4_dv1200_free.cir"
    p, msg = bt.run(fn, lines)
    print("ICA", msg, flush=True)
    if p is None:
        return 1
    a = parse_mt0(os.path.join(BTDIR, fn + ".mt0"))
    b = parse_mt0(p + ".mt0")
    keys = sorted(set(a) & set(b))
    worst, fails = 0.0, []
    for k in keys:
        dd = abs(a[k] - b[k]) / max(abs(a[k]), abs(b[k]), 1e-30)
        worst = max(worst, dd)
        if dd > 1e-6:
            fails.append((k, a[k], b[k], dd))
    out = dict(deck_byte_identical=ident, n_keys=len(keys),
               n_fail_1e6=len(fails), worst_rel=worst, fails=fails[:20],
               rails_regenerated={k: b.get("VR%dB%d" % (k, k)) for k in range(1, 5)},
               committed_rails=[0.7544238, 0.6767239, 0.7312457, 0.7200878],
               PASS=bool(ident and len(fails) <= 0.01 * len(keys)))
    json.dump(out, open(os.path.join(HERE, "ICA.json"), "w"), indent=1)
    print(json.dumps({k: out[k] for k in ("deck_byte_identical", "n_keys",
                                          "n_fail_1e6", "worst_rel", "PASS")}))
    for f in [os.path.join(sub, x) for x in os.listdir(sub) if x.endswith(".prn")]:
        os.remove(f)
    return 0 if out["PASS"] else 1


def cmd_icb():
    """Single-bank sine smoke at the LARGEST half-period: waveform digit-check,
    integrator sign, trip extrapolation hand-check, extractor plumbing."""
    th, d = 130.0, 1
    tag = "icb_sine_th130_d1"
    rundir = os.path.join(HERE, "runs", tag)
    # one bank = NB temporarily 1?  No: run the FULL deck builder with NB=6 is
    # the sweep; the smoke uses a private 1-bank deck assembled from the same
    # pieces so the sweep code path itself is exercised at nb=1 scale.
    global NB
    nb_save = NB
    NB = 2                       # bank 1 (A) + bank 2 (B): smallest phase pair
    try:
        lines, S = deck("sine", th, d, 0.2, "P0")
        p, msg = run_xyce(rundir, "c_%s.cir" % tag, lines, timeout=2400)
        print("ICB", msg, flush=True)
        if p is None:
            return 1
        o = extract(rundir, S, keep_prn=True)
    finally:
        NB = nb_save
    # waveform digit checks off the dense grid
    n, C = load_grid(os.path.join(rundir, "c_%s.cir.prn" % tag), S["tend"])
    T = 2 * th
    v0a = C["V(PH1)"][0]
    vca = C["V(PH1)"][int(th / GRID)]
    v0b = C["V(PH2)"][0]
    tr165, ex165 = TRIPF(1.65)
    tr120, ex120 = TRIPF(1.20)
    q2 = o["charge_spec_reported_not_gated"].get(1, {})
    chk = dict(
        VA_at_0=round(v0a, 6), VA_at_crest=round(vca, 6), VB_at_0=round(v0b, 6),
        sine_ok=bool(abs(v0a) < 1e-3 and abs(vca - 1.65) < 2e-3
                     and abs(v0b - 1.65) < 1e-3),
        trip_1p65_V=round(tr165, 5), trip_1p65_extrapolated=ex165,
        trip_1p65_expected=0.85445, trip_1p20_V=round(tr120, 5),
        trip_1p20_extrapolated=ex120, trip_1p20_expected=0.64516,
        trip_ok=bool(abs(tr165 - 0.854453) < 5e-4 and (ex165 is True)
                     and abs(tr120 - 0.645162) < 5e-4 and (ex120 is False)),
        Q_rise_bank1_fC=q2.get("Q_rise_fC"),
        integrator_sign_ok=bool((q2.get("Q_rise_fC") or -1) > 0),
        value_pass=o["value"]["PASS"])
    chk["PASS"] = bool(chk["sine_ok"] and chk["trip_ok"]
                       and chk["integrator_sign_ok"])
    json.dump(chk, open(os.path.join(HERE, "ICB.json"), "w"), indent=1)
    print(json.dumps(chk, indent=1))
    return 0 if chk["PASS"] else 1


def cmd_sawi():
    """SAW-I: fixed-I current-driven ramp, ONE bank, d = 1..4.  I calibrated so
    d=1 reaches dV at ramp end (th=92, f=0.20); same I for every d."""
    th, fly = 92.0, 0.20
    T = 2 * th
    ramp = (1 - fly) * T
    res = dict(th=th, fly=fly, ramp_ps=ramp)
    ical = None
    for it in range(2):
        # calibration: start from the sweep-measured d=1 charge if present
        if ical is None:
            q1 = None
            oj = os.path.join(HERE, "runs", "saw_th92_d1_f20", "OUT.json")
            if os.path.exists(oj):
                q1 = json.load(open(oj))["charge_spec_reported_not_gated"].get("1") or \
                     json.load(open(oj))["charge_spec_reported_not_gated"].get(1)
            ical = (q1["Q_rise_fC"] * 1e-15 / (ramp * 1e-12)) if q1 else \
                (60e-15 * 1.65 / 1.65 / (ramp * 1e-12))
        tagc = "sawi_cal_it%d" % it
        o = _sawi_run(tagc, 1, ical, ramp)
        vend = o["v_end"]
        res["cal_iter%d" % it] = dict(I_uA=round(ical * 1e6, 3), v_end=vend)
        if abs(vend - DV) < 0.02 * DV:
            break
        ical *= DV / max(vend, 0.1)
    res["I_fixed_uA"] = round(ical * 1e6, 3)
    for d in (1, 2, 3, 4):
        o = _sawi_run("sawi_d%d" % d, d, ical, ramp)
        res["d%d" % d] = o
    r1 = res["d1"].get("t_90pct_ps")
    for d in (1, 2, 3, 4):
        t9 = res["d%d" % d].get("t_90pct_ps")
        res["d%d" % d]["ramp_stretch_vs_d1"] = round(t9 / r1, 4) \
            if (r1 and t9) else None
    json.dump(res, open(os.path.join(HERE, "SAWI.json"), "w"), indent=1)
    print(json.dumps(res, indent=1))
    return 0


def _sawi_run(tag, d, amps, ramp):
    rundir = os.path.join(HERE, "runs", tag)
    L = head_lines()
    L.append("IMESH 0 ph1 PWL(0 0 1p %g %gp %g %gp 0)" % (amps, ramp, amps, ramp + 1))
    L.append("RLK ph1 0 10e6")
    L.append("VMG1 gn1 0 0")
    for j in range(1, d + 1):
        for i in range(MG):
            src = "in1_%d" % i if j == 1 else "o1_%d_%d" % (j - 1, i)
            o = "o1_%d_%d" % (j, i)
            L.append("XP1_%d_%d %s %s ph1 ph1 sg13_lv_pmos w=%gu l=0.13u"
                     % (j, i, o, src, WP))
            L.append("XN1_%d_%d %s %s gn1 gn1 sg13_lv_nmos w=%gu l=0.13u"
                     % (j, i, o, src, WN))
            L.append("CL1_%d_%d %s gn1 %gf" % (j, i, o, CLOAD))
    for i in range(MG):
        L.append("VI1_%d in1_%d 0 %g" % (i, i, DV * PAT0[i]))
    L.append(".tran 0.1p %gp 0 0.25p" % (ramp + 40))
    L.append(".print tran V(ph1)")
    L.append(".end")
    p, msg = run_xyce(rundir, "c_%s.cir" % tag, L, timeout=1800)
    print("  %s %s" % (tag, msg), flush=True)
    if p is None:
        return dict(error=msg)
    n, C = load_grid(p + ".prn", ramp + 40)
    v = C["V(PH1)"]
    vend = v[min(n - 1, int(ramp / GRID))]
    def tcross(level):
        for a in range(1, n):
            if v[a - 1] < level <= v[a]:
                return round((a - 1) * GRID + (level - v[a - 1]) * GRID
                             / (v[a] - v[a - 1]), 2)
        return None
    out = dict(d=d, v_end=round(vend, 4),
               t_50pct_ps=tcross(0.5 * DV), t_90pct_ps=tcross(0.9 * DV),
               slope_10_90_V_per_ns=None)
    t10, t90 = tcross(0.1 * DV), tcross(0.9 * DV)
    if t10 and t90 and t90 > t10:
        out["slope_10_90_V_per_ns"] = round(0.8 * DV / (t90 - t10) * 1000, 2)
    os.remove(p + ".prn")
    return out


def cmd_agg():
    R = {}
    rd = os.path.join(HERE, "runs")
    for tag in sorted(os.listdir(rd)):
        oj = os.path.join(rd, tag, "OUT.json")
        if os.path.exists(oj) and not tag.startswith(("icb", "sawi")):
            R[tag] = json.load(open(oj))
    ths = [70, 80, 92, 105, 117, 130]
    front = {}
    for wave, fl in (("sine", 0.2), ("saw", 0.2), ("saw", 0.1), ("saw", 0.3)):
        key = wave if wave == "sine" else "saw_f%g" % (100 * fl)
        front[key] = {}
        for th in ths:
            best = 0
            for d in (1, 2, 3, 4):
                t = tag_of(wave, th, d, fl, "P0")
                if t in R and R[t].get("acceptance", {}).get("PASS"):
                    best = d
            if best or any(tag_of(wave, th, d, fl, "P0") in R for d in (1, 2, 3, 4)):
                e = dict(max_d=best,
                         ratio_headline=round(best * T_CMOS / (2 * th), 3),
                         ratio_corner=round(best * T_CMOS_CORNER / (2 * th), 3),
                         ratio_chain_advance=round(best * T_CMOS / th, 3),
                         latency_per_level_ps=round(th / best, 2) if best else None)
                front[key][th] = e
    json.dump(dict(frontier=front), open(os.path.join(HERE, "FRONTIER.json"), "w"),
              indent=1)
    print(json.dumps(front, indent=1))
    return 0


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "ica":
        sys.exit(cmd_ica())
    if a[0] == "icb":
        sys.exit(cmd_icb())
    if a[0] == "lane":
        sys.exit(cmd_lane(a[1], float(a[2]), float(a[3]) if len(a) > 3 else 0.2))
    if a[0] == "one":
        o = cmd_one(a[1], float(a[2]), int(a[3]), float(a[4]), a[5],
                    float(a[6]) if len(a) > 6 else 0.001,
                    keep_prn=("--keep" in a))
        sys.exit(0 if o.get("acceptance", {}).get("PASS") else 3)
    if a[0] == "sawi":
        sys.exit(cmd_sawi())
    if a[0] == "agg":
        sys.exit(cmd_agg())
    print("unknown subcommand")
    sys.exit(2)
