#!/usr/bin/env python3
"""qal/mesh3 -- THREE-PHASE MESH WITH A HOLD PHASE (the named fix from 2be4644).

Everything scored here was fixed in PRE_REGISTERED.json (sha256 31201d45...,
mtime 2026-09-30 23:57:17.747 -0700, the ONLY file in qal/mesh3/ at that
instant) BEFORE this file existed.

Banks on phases A/B/C at 120 degrees (bank k on phase (k-1) mod 3), order
A -> B -> C -> A.  Cells are the campaign-standard restoring inverter VERBATIM
(identical lines to qal/mesh/mesh.py): pMOS 1.12u supply+bulk on the phase
node, nMOS 0.74u on metered ground, CL 2 fF.  NO switch, NO per-bank L, NO
timer, NO return schedule.  Xyce executes on the tmpfs scratchpad (root disk
99%); the repo keeps OUT.json + deck + .mt0 only, every .prn deleted after
extraction.

Subcommands:
  ica3                  anchor: committed two-phase sine_th130_d1 row re-run
                        from COMMITTED mesh.py code, byte/digit-checked
  icb3                  three-phase smoke, NB=3, T_third=130, d=1, both waveforms
  lane <wave> <tt>      one (waveform, T_third) lane, d = 1..4
  one  <wave> <tt> <d> <pat> [rs]   one config: run + extract + delete .prn
  agg                   aggregate: erosion tables + frontier + ratios
"""
import importlib.util, json, math, os, re, shutil, subprocess, sys, time
from array import array

HERE   = os.path.dirname(os.path.abspath(__file__))
MESHDIR = "/usr/local/src/stat-sim/qal/mesh"
XYCE   = "/usr/local/src/xyce-build/src/Xyce"
VA     = "/usr/local/share/xyce/verilog-a/psp103/psp103.va"
MODEL  = "/usr/local/src/kestrel/sim/models/sg13g2_psp103_tt.lib"
SHIM   = "/usr/local/src/stat-sim/qal/sg13lv_compat.sp"
SCRATCH = ("/tmp/claude-1001/-usr-local-src/"
           "4921ad0c-f17b-4b84-986a-5917c9ebd2a6/scratchpad")
CACHE  = os.path.join(SCRATCH, "vae_cache_mesh3")
RUNS_SCRATCH = os.path.join(SCRATCH, "mesh3_runs")
ENV    = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS",
              PYMS_VAE_CACHE=CACHE)
TRIPJSON = "/usr/local/src/stat-sim/qal/fcrit/TRIP.json"

WP, WN  = 1.12, 0.74          # the committed cell (bt.py VERBATIM)
CLOAD   = 2.0                 # fF
DV      = 1.65                # V, full mesh swing
EDGE    = 2.0                 # ps, input word edges (committed)
LAG_PS  = 1.0                 # ps, MEASURED .measure-FIND lag of this Xyce build
NB, MG  = 6, 8
GRID    = 0.10                # ps, extraction grid
SIG_TOTAL_MV = 23.308         # MEASURED qal/eye/p2 U3
GATE_MV = 3 * SIG_TOTAL_MV    # 69.924 mV -- the budget with the timer GONE
T_CMOS  = 367.888             # ps (MEASURED t_level + DERIVED t_reg)
T_CMOS_CORNER = 467.888       # ps, the 100 ps clock-uncertainty corner
PAT0    = [1, 1, 1, 0, 1, 0, 0, 1]
PATS    = {"P0": PAT0, "P1": [1, 0, 1, 0, 0, 1, 1, 0], "P2": [1] * 8}


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
    """qal/eye eyeharness Trip VERBATIM (fcrit/rescore lineage, as qal/mesh)."""
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


def slot(k, n, T, tt):
    return n * T + (k - 1) * tt


def phase_of(k):
    return (k - 1) % 3


def rxbank(k):
    """bank whose rail waveform equals the (k+1)-th bank's phase; for k=NB the
    receiver is the DERIVED ideal next-phase rail = bank (NB%3)+1's (periodic,
    same phase as the would-be bank NB+1)."""
    return k + 1 if k < NB else (NB % 3) + 1


def bits(pat, k, j, n, d):
    """expected bit of bank k level j, wave n (PRE_REGISTERED, carried)."""
    return [pat[i] ^ (n & 1) ^ (((k - 1) * d + j) & 1) for i in range(MG)]


def trap_pts(p, tt, T, tend):
    """trapezoid PWL knots for phase p: rise tt, hold tt, fall tt, shift p*tt.
    Exact knots exist at t=0 for all three phases."""
    pts = []
    m = -2
    while m * T + p * tt < tend + T:
        t0 = m * T + p * tt
        pts += [(t0, 0.0), (t0 + tt, DV), (t0 + 2 * tt, DV)]
        m += 1
    return sorted((t, v) for (t, v) in pts if t >= -1e-12)


def deck(wave, tt, d, patname, rs=0.001):
    T = 3.0 * tt
    pat = PATS[patname]
    tend = 7.0 * T
    L = head_lines()
    # ---- the mesh phases: one driven source per bank (identical per phase) so
    # per-bank charge is metered and per-bank series R can be inserted.
    for k in range(1, NB + 1):
        p = phase_of(k)
        if wave == "sine":
            L.append("VPH%d phs%d 0 SIN(%g %g %g 0 0 %g)"
                     % (k, k, DV / 2, DV / 2, 1e12 / T, -90.0 - 120.0 * p))
        else:
            pts = trap_pts(p, tt, T, tend)
            s = " ".join("%gp %g" % (t, v) if t > 1e-12 else "0 %g" % v
                         for t, v in pts)
            L.append("VPH%d phs%d 0 PWL(%s)" % (k, k, s))
        L.append("RS%d phs%d ph%d %g" % (k, k, k, rs))
    # ---- input words (chain head): alternate PAT / ~PAT at phase-A troughs
    for i in range(MG):
        pts, cur = [(0.0, DV * pat[i])], DV * pat[i]
        for n in range(1, 8):
            nxt = DV * (pat[i] ^ (n & 1))
            if nxt != cur:
                pts += [(n * T - EDGE / 2, cur), (n * T + EDGE / 2, nxt)]
                cur = nxt
        s = " ".join("%gp %g" % (t, v) if t > 0 else "0 %g" % v for t, v in pts)
        L.append("VI1_%d in1_%d 0 PWL(%s)" % (i, i, s))
    # ---- the banks: d series levels x 8 chains, cells VERBATIM
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
    # ---- measures
    g = lambda t: t + LAG_PS
    co = 1.5 * tt                        # sampling instant offset, both waveforms
    for n in (2, 3, 4):
        for k in range(1, NB + 1):
            tc = slot(k, n, T, tt) + co
            L.append(".measure tran VRK%dW%d FIND V(ph%d) AT=%.6fp"
                     % (k, n, k, g(tc)))
            for j in range(1, d + 1):
                for i in range(MG):
                    L.append(".measure tran VK%d_%d_%dW%d FIND V(o%d_%d_%d) AT=%.6fp"
                             % (k, j, i, n, k, j, i, g(tc)))
    # third-boundary integrator reads: T=trough/slot, R=rise end, H=hold end
    for k in range(1, NB + 1):
        for n in (2, 3, 4, 5):
            ts = slot(k, n, T, tt)
            L.append(".measure tran QPH%dT%d FIND V(xqph%d) AT=%.6fp" % (k, n, k, g(ts)))
            L.append(".measure tran EPH%dT%d FIND V(xeph%d) AT=%.6fp" % (k, n, k, g(ts)))
            if n < 5:
                L.append(".measure tran QPH%dR%d FIND V(xqph%d) AT=%.6fp"
                         % (k, n, k, g(ts + tt)))
                L.append(".measure tran EPH%dR%d FIND V(xeph%d) AT=%.6fp"
                         % (k, n, k, g(ts + tt)))
                L.append(".measure tran QPH%dH%d FIND V(xqph%d) AT=%.6fp"
                         % (k, n, k, g(ts + 2 * tt)))
                L.append(".measure tran EPH%dH%d FIND V(xeph%d) AT=%.6fp"
                         % (k, n, k, g(ts + 2 * tt)))
    pr = (["V(ph%d)" % k for k in range(1, NB + 1)] +
          ["V(o%d_%d_%d)" % (k, j, i) for k in range(1, NB + 1)
           for j in range(1, d + 1) for i in range(MG)] +
          ["I(VPH%d)" % k for k in range(1, NB + 1)] +
          ["I(VMG%d)" % k for k in range(1, NB + 1)])
    L.append(".print tran " + " ".join(pr))
    L.append(".end")
    return L, dict(wave=wave, tt=tt, T=T, d=d, pat=patname, rs=rs,
                   tend=tend, crestoff=co, nb=NB)


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
    ta, tb = a * GRID, b * GRID
    if a - 1 >= 0 and curve[a - 1] <= thr < curve[a]:
        y0, y1 = curve[a - 1], curve[a]
        ta = (a - 1) * GRID + (thr - y0) * GRID / (y1 - y0)
    if b + 1 < n and curve[b + 1] <= thr < curve[b]:
        y0, y1 = curve[b], curve[b + 1]
        tb = b * GRID + (thr - y0) * GRID / (y1 - y0)
    return ta, tb


def extract(rundir, S, keep_prn=False):
    d, T, tt, wave = S["d"], S["T"], S["tt"], S["wave"]
    pat = PATS[S["pat"]]
    co = S["crestoff"]
    fn = [f for f in os.listdir(rundir) if f.endswith(".cir.prn")][0]
    prn = os.path.join(rundir, fn)
    mt0 = parse_mt0(prn[:-4] + ".mt0")
    n, C = load_grid(prn, S["tend"])
    out = dict(S)

    # ---- crest diagnostic (M2c, from .mt0; sampling instant = mid-hold/crest)
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
    out["crest_diag"] = dict(checked=checked, n_fail=len(fails), fails=fails[:12],
                             note="M2c carried: diagnostic, not gating")

    # ---- eyes / commit / die / handoff per link per wave
    rails = {k: C["V(PH%d)" % k] for k in range(1, NB + 1)}
    outs = {k: {i: C["V(O%d_%d_%d)" % (k, d, i)] for i in range(MG)}
            for k in range(1, NB + 1)}
    links = {}
    tcommit, tdieraw = {}, {}
    for k in range(1, NB + 1):
        rx_rail = rails[rxbank(k)]
        links[k] = {}
        for nn in (2, 3, 4):
            srx = slot(k + 1, nn, T, tt)
            sk = srx - tt
            w0 = max(0, int((sk - 10.0) / GRID))
            w1 = min(n - 1, int((srx + 2 * tt + 40.0) / GRID))
            bb = bits(pat, k, d, nn, d)
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
                # M2a carried: LARGEST run intersecting [srx, srx+co]
                r0 = int(srx / GRID) - w0
                r1 = int((srx + co) / GRID) - w0
                pick = None
                for (a, b) in rr:
                    if b >= r0 and a <= r1:
                        if pick is None or (b - a) > (pick[1] - pick[0]):
                            pick = (a, b)
                if pick is None:
                    rec[thr_name] = dict(EYE="EMPTY_in_rise_window", n_runs=len(rr))
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
                    rec["commit_gated_ps"] = round(ta, 3)
                    rec["die_ps"] = round(tb, 3)
            # M4 carried: commit_raw from bank k's OWN powered window
            cur = mcur["all"]
            rmask = bytearray(w1 - w0 + 1)
            for a in range(w1 - w0 + 1):
                rmask[a] = 1 if cur[a] > 0.0 else 0
            rr2 = runs_of(rmask, 0, w1 - w0)
            q0 = int(sk / GRID) - w0
            q1 = int((sk + 2 * tt) / GRID) - w0        # powered window (M4c)
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

            # margins at the receiver sampling instant, both polarities
            probe = min(w1, int((srx + co) / GRID)) - w0
            rec["margin_at_rx_crest_mV"] = {
                sel: (round(mcur[sel][probe], 2) if mcur[sel] is not None else None)
                for sel in ("all", "HIGH", "LOW")}

            # ---- PRE-REGISTERED adjudicator: what dies first at link k's data?
            # (i) input-death: first instant after srx that the min expected-HIGH
            # INPUT to bank k (= bank k-1 last-level outputs) crosses below bank
            # k's OWN instantaneous trip; (ii) bank k's own fall start.
            if k >= 2:
                bbin = bits(pat, k - 1, d, nn, d)
                his = [i for i in range(MG) if bbin[i]]
                tid = None
                if his:
                    a0 = max(w0, int(srx / GRID))
                    for a in range(a0, w1 + 1):
                        town, _ = TRIPF(rails[k][a])
                        if min(outs[k - 1][i][a] for i in his) < town:
                            tid = round(a * GRID, 2)
                            break
                ofs = sk + (2 * tt if wave == "trap" else 1.5 * tt)
                rec["die_cause"] = dict(
                    t_inputdeath_ps=tid, own_fall_start_ps=round(ofs, 2),
                    first=("input_death" if (tid is not None and tid < ofs)
                           else "own_rail_fall"))
            links[k][nn] = rec

    # handoff: margin AT the commit sample + overlap, links 1..NB-1
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
                rx_rail = rails[rxbank(k)]
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
            handoff[k][nn] = rec
    out["links"] = links
    out["handoff"] = handoff

    # ---- value at the raw-validity MIDPOINT (M2b/M4b/M4d carried)
    allout = {k: {j: {i: C["V(O%d_%d_%d)" % (k, j, i)] for i in range(MG)}
                  for j in range(1, d + 1)} for k in range(1, NB + 1)}
    vfails, vchecked, interior_diag = [], 0, []
    min_high_V = None
    for k in range(1, NB + 1):
        for nn in (2, 3, 4):
            tc = tcommit.get((k, nn))
            td = tdieraw.get((k, nn))
            if tc is None:
                vfails.append([k, nn, "NO_COMMIT"])
                continue
            a = min(n - 1, int(0.5 * (tc + (td if td else tc)) / GRID))
            trx, _ = TRIPF(rails[rxbank(k)][a])
            town, _ = TRIPF(rails[k][a])
            for j in range(1, d + 1):
                bb = bits(pat, k, j, nn, d)
                tref = trx if j == d else town
                for i in range(MG):
                    v = allout[k][j][i][a]
                    ok = (v > tref) if bb[i] else (v < tref)
                    if j == d:
                        vchecked += 1
                        if bb[i]:
                            min_high_V = v if min_high_V is None else min(min_high_V, v)
                        if not ok:
                            vfails.append([k, j, i, nn, round(v, 4), round(tref, 4)])
                    elif not ok:
                        interior_diag.append([k, j, i, nn, round(v, 4), round(tref, 4)])
    out["value"] = dict(checked=vchecked, n_fail=len(vfails), fails=vfails[:20],
                        PASS=(not vfails),
                        interior_stale_diag_n=len(interior_diag),
                        interior_stale_diag=interior_diag[:10],
                        restored_HIGH_min_V=(round(min_high_V, 4)
                                             if min_high_V is not None else None),
                        note="M2b/M4b/M4d carried: last-level word at validity midpoint")

    # ---- rising-side tracking lag per bank (M2d carried)
    lags = []
    for k in range(1, NB + 1):
        for nn in (2, 3, 4):
            s0 = slot(k, nn, T, tt)
            a0 = max(1, int(s0 / GRID))
            a1 = min(n - 1, int((s0 + co) / GRID))
            tr50 = None
            for a in range(a0, a1 + 1):
                if rails[k][a - 1] < 0.5 * DV <= rails[k][a]:
                    tr50 = a * GRID
                    break
            bb = bits(pat, k, d, nn, d)
            his = [i for i in range(MG) if bb[i]]
            if his and tr50 is not None:
                worst = None
                for i in his:
                    y = allout[k][d][i]
                    for a in range(a0, min(n - 1, a1 + int(1.5 * tt / GRID))):
                        if y[a - 1] < 0.5 * DV <= y[a]:
                            worst = max(worst or 0, a * GRID - tr50)
                            break
                if worst is not None:
                    lags.append(round(worst, 1))
    out["rising_lag_ps"] = dict(
        min=min(lags) if lags else None, max=max(lags) if lags else None,
        median=sorted(lags)[len(lags) // 2] if lags else None)

    # ---- THE HOLD-THIRD BOOKS: rail droop + hold bump + per-third charge
    droop = {}
    for k in range(1, NB + 1):
        mins, means = [], []
        for nn in (2, 3, 4):
            h0 = int((slot(k, nn, T, tt) + tt + 1.0) / GRID)
            h1 = min(n - 1, int((slot(k, nn, T, tt) + 2 * tt - 1.0) / GRID))
            if h1 <= h0:
                continue
            seg = [rails[k][a] for a in range(h0, h1 + 1)]
            mins.append(min(seg))
            means.append(sum(seg) / len(seg))
        if mins:
            droop[k] = dict(rail_hold_min_V=round(min(mins), 4),
                            rail_hold_mean_V=round(sum(means) / len(means), 4),
                            droop_from_dV_mV=round(1000 * (DV - min(mins)), 2))
    out["hold_rail"] = droop

    bump = []
    for k in [b for b in (3, 4) if b <= NB]:
        for nn in (2, 3, 4):
            h0 = int((slot(k, nn, T, tt) + tt) / GRID)
            h1 = min(n - 1, int((slot(k, nn, T, tt) + 2 * tt) / GRID))
            bb = bits(pat, k, d, nn, d)
            lows = [i for i in range(MG) if bb[i] == 0]
            if not lows or h1 <= h0:
                continue
            ref = max(outs[k][i][h0] for i in lows)
            pk = max(outs[k][i][a] for i in lows for a in range(h0, h1 + 1))
            bump.append(dict(bank=k, wave=nn,
                             LOW_rise_over_hold_mV=round(1000 * (pk - ref), 2)))
    worstb = max((r["LOW_rise_over_hold_mV"] for r in bump), default=None)
    out["hold_bump"] = dict(worst_LOW_rise_mV=worstb, rows=bump[:12],
                            note="what the hold failed to hold: expected-LOW "
                                 "last-level lift across the holding bank's own "
                                 "hold third (diagnostic)")

    # ---- crowbar / trough-rail check (carried): banks 3 (C) and 4 (A)
    crow = {}
    for k in [b for b in (3, 4) if b <= NB] or [NB]:
        rows = []
        for nn in (3, 4):
            ts = slot(k, nn, T, tt)
            a0, a1 = max(0, int((ts - 2) / GRID)), min(n - 1, int((ts + 2) / GRID))
            img = [C["I(VMG%d)" % k][a] for a in range(a0, a1 + 1)]
            iph = [C["I(VPH%d)" % k][a] for a in range(a0, a1 + 1)]
            lo0 = ts
            while lo0 > 0 and rails[k][int(lo0 / GRID)] < 0.1 * DV:
                lo0 -= GRID
            hi0 = ts
            while hi0 < (n - 1) * GRID and rails[k][int(hi0 / GRID)] < 0.1 * DV:
                hi0 += GRID
            b0, b1 = max(0, int(lo0 / GRID)), min(n - 1, int(hi0 / GRID))
            imgw = [C["I(VMG%d)" % k][a] for a in range(b0, b1 + 1)]
            rows.append(dict(
                wave=nn, trough_ps=ts,
                Ignd_pk_uA=round(max(abs(x) for x in img) * 1e6, 3),
                Ignd_mean_uA=round(sum(img) / len(img) * 1e6, 4),
                Iph_pk_uA=round(max(abs(x) for x in iph) * 1e6, 3),
                rail_lt_10pct_window_ps=round(hi0 - lo0, 1),
                Ignd_mean_10pct_uA=round(sum(imgw) / len(imgw) * 1e6, 4),
                Q_gnd_10pct_fC=round(sum(imgw) * GRID * 1e3, 4)))
        crow[k] = rows
    out["crowbar"] = crow

    # ---- the mesh interface spec: per-third charge books per bank per phase
    ch = {}
    for k in range(1, NB + 1):
        acc = {x: [] for x in ("qr", "qh", "qf", "er", "eh", "ef")}
        for nn in (2, 3, 4):
            qt = mt0.get("QPH%dT%d" % (k, nn))
            qr = mt0.get("QPH%dR%d" % (k, nn))
            qh = mt0.get("QPH%dH%d" % (k, nn))
            qt2 = mt0.get("QPH%dT%d" % (k, nn + 1))
            et = mt0.get("EPH%dT%d" % (k, nn))
            er = mt0.get("EPH%dR%d" % (k, nn))
            eh = mt0.get("EPH%dH%d" % (k, nn))
            et2 = mt0.get("EPH%dT%d" % (k, nn + 1))
            if None not in (qt, qr, qh, qt2):
                acc["qr"].append((qr - qt) * 1e15)
                acc["qh"].append((qh - qr) * 1e15)
                acc["qf"].append((qt2 - qh) * 1e15)
            if None not in (et, er, eh, et2):
                acc["er"].append((er - et) * 1e15)
                acc["eh"].append((eh - er) * 1e15)
                acc["ef"].append((et2 - eh) * 1e15)
        if acc["qr"]:
            mean = lambda v: round(sum(v) / len(v), 3)
            ch[k] = dict(phase="ABC"[phase_of(k)],
                         Q_rise_fC=mean(acc["qr"]), Q_hold_fC=mean(acc["qh"]),
                         Q_fall_fC=mean(acc["qf"]),
                         E_rise_fJ=mean(acc["er"]) if acc["er"] else None,
                         E_hold_fJ=mean(acc["eh"]) if acc["eh"] else None,
                         E_fall_fJ=mean(acc["ef"]) if acc["ef"] else None)
    out["charge_spec_reported_not_gated"] = ch

    # ---- erosion series (THE HEADLINE): widths + overlaps + sign per wave
    ero = {}
    for nn in (2, 3, 4):
        wid = []
        for k in range(1, NB + 1):
            e = links[k][nn].get("0mV", {})
            wid.append(e.get("width_ps"))
        ovs = [handoff[k][nn].get("overlap_ps") for k in range(1, NB)]
        real = [w for w in wid[:NB - 1] if w is not None]   # exclude derived link
        sign = "EXTINCT"
        if len(real) == NB - 1:
            if real[-1] >= 0.85 * real[0]:
                sign = "SUSTAINS"
            elif real[-1] >= 0.5 * real[0]:
                sign = "ERODES_SLOW"
            else:
                sign = "ERODES"
        asym = None
        if len(real) >= 2 and real[-2] > 0 and \
           abs(real[-1] - real[-2]) <= 0.15 * real[-2]:
            asym = round(0.5 * (real[-1] + real[-2]), 2)
        ero[nn] = dict(width_0mV_ps_links=wid, overlaps_ps=ovs, sign=sign,
                       asymptotic_width_ps=asym)
    out["erosion"] = ero

    # ---- acceptance (PRE_REGISTERED A+B+C, carried form)
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
        os.remove(prn)
    return out


# ------------------------------------------------------------- subcommands
def tag_of(wave, tt, d, pat, rs=0.001):
    t = "%s_tt%g_d%d" % (wave, tt, d)
    if pat != "P0":
        t += "_" + pat
    if rs != 0.001:
        t += "_rs%g" % rs
    return t


def repo_keep(rundir, tag):
    dst = os.path.join(HERE, "runs", tag)
    os.makedirs(dst, exist_ok=True)
    for f in os.listdir(rundir):
        if f.endswith((".cir", ".mt0")) or f == "OUT.json":
            shutil.copy2(os.path.join(rundir, f), os.path.join(dst, f))


def cmd_one(wave, tt, d, patname, rs=0.001, keep_prn=False):
    tag = tag_of(wave, tt, d, patname, rs)
    oj_repo = os.path.join(HERE, "runs", tag, "OUT.json")
    if os.path.exists(oj_repo):
        print("  cached", tag)
        return json.load(open(oj_repo))
    rundir = os.path.join(RUNS_SCRATCH, tag)
    lines, S = deck(wave, tt, d, patname, rs)
    p, msg = run_xyce(rundir, "c_%s.cir" % tag, lines, timeout=1500 + 1100 * d)
    print("  %s %s" % (tag, msg), flush=True)
    if p is None:
        os.makedirs(os.path.dirname(oj_repo), exist_ok=True)
        json.dump(dict(S, error=msg), open(oj_repo, "w"), indent=1)
        return dict(S, error=msg, acceptance=dict(PASS=False))
    o = extract(rundir, S, keep_prn)
    repo_keep(rundir, tag)
    a = o["acceptance"]
    e3 = o["erosion"][3]
    print("  %s value=%s eye=%s handoff=%s worst_margin=%s worst_ov=%s "
          "erosion=%s widths=%s -> %s"
          % (tag, a["A_value"], a["B_eye"], a["C_handoff"],
             a["worst_margin_at_commit_mV"], a["worst_overlap_ps"],
             e3["sign"], e3["width_0mV_ps_links"],
             "PASS" if a["PASS"] else "FAIL"), flush=True)
    return o


def cmd_lane(wave, tt):
    for d in (1, 2, 3, 4):     # full grid, no early stop (committed M3)
        cmd_one(wave, tt, d, "P0")
    return 0


def cmd_ica3():
    """ANCHOR: the committed two-phase near-miss row sine_th130_d1 re-run from
    the COMMITTED qal/mesh/mesh.py code under qal/mesh3's own fresh cache;
    deck byte-checked, .mt0 digit-checked, OUT fields checked."""
    spec = importlib.util.spec_from_file_location(
        "mesh2p", os.path.join(MESHDIR, "mesh.py"))
    m2 = importlib.util.module_from_spec(spec)
    sys.modules["mesh2p"] = m2
    spec.loader.exec_module(m2)
    sub = os.path.join(RUNS_SCRATCH, "ica3")
    os.makedirs(sub, exist_ok=True)
    m2.HERE, m2.CACHE = sub, CACHE
    m2.ENV = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS",
                  PYMS_VAE_CACHE=CACHE)
    lines, S = m2.deck("sine", 130.0, 1, 0.2, "P0")
    mine = "\n".join(lines) + "\n"
    ref_dir = os.path.join(MESHDIR, "runs", "sine_th130_d1")
    committed = open(os.path.join(ref_dir, "c_sine_th130_d1.cir")).read()
    ident = (mine == committed)
    print("ICA3 deck byte-identical to committed:", ident, flush=True)
    o = m2.cmd_one("sine", 130.0, 1, 0.2, "P0")
    a = parse_mt0(os.path.join(ref_dir, "c_sine_th130_d1.cir.mt0"))
    b = parse_mt0(os.path.join(sub, "runs", "sine_th130_d1",
                               "c_sine_th130_d1.cir.mt0"))
    keys = sorted(set(a) & set(b))
    worst, fails = 0.0, []
    for k in keys:
        dd = abs(a[k] - b[k]) / max(abs(a[k]), abs(b[k]), 1e-30)
        worst = max(worst, dd)
        if dd > 1e-6:
            fails.append((k, a[k], b[k], dd))
    ref = json.load(open(os.path.join(ref_dir, "OUT.json")))
    cmp_fields = dict(
        value_checked=(o["value"]["checked"], ref["value"]["checked"]),
        value_nfail=(o["value"]["n_fail"], ref["value"]["n_fail"]),
        worst_margin=(o["acceptance"]["worst_margin_at_commit_mV"],
                      ref["acceptance"]["worst_margin_at_commit_mV"]),
        worst_overlap=(o["acceptance"]["worst_overlap_ps"],
                       ref["acceptance"]["worst_overlap_ps"]),
        link1_w2_eye=(o["links"][1][2]["0mV"]["width_ps"],
                      ref["links"]["1"]["2"]["0mV"]["width_ps"]))
    fields_ok = all(abs(x - y) < 5e-3 for x, y in cmp_fields.values())
    res = dict(deck_byte_identical=ident, n_keys=len(keys),
               n_fail_1e6=len(fails), worst_rel=worst, fails=fails[:20],
               out_fields={k: v for k, v in cmp_fields.items()},
               out_fields_ok=fields_ok,
               PASS=bool(ident and not fails and fields_ok))
    json.dump(res, open(os.path.join(HERE, "ICA3.json"), "w"), indent=1)
    print(json.dumps({k: res[k] for k in ("deck_byte_identical", "n_keys",
                                          "n_fail_1e6", "worst_rel",
                                          "out_fields_ok", "PASS")}))
    return 0 if res["PASS"] else 1


def cmd_icb3():
    """Three-phase smoke, NB=3 (smallest full phase set), T_third=130, d=1,
    both waveforms: waveform digit-checks, trip hand-checks, integrator sign,
    hold-book sanity."""
    global NB
    nb_save, NB = NB, 3
    tt = 130.0
    T = 3 * tt
    res = {}
    try:
        for wave in ("trap", "sine"):
            tag = "icb3_%s_tt130_d1" % wave
            rundir = os.path.join(RUNS_SCRATCH, tag)
            lines, S = deck(wave, tt, 1, "P0")
            p, msg = run_xyce(rundir, "c_%s.cir" % tag, lines, timeout=2400)
            print("ICB3", wave, msg, flush=True)
            if p is None:
                res[wave] = dict(error=msg, PASS=False)
                continue
            o = extract(rundir, S, keep_prn=True)
            n, C = load_grid(p + ".prn", S["tend"])
            at = lambda sig, t: C[sig][min(n - 1, int(t / GRID))]
            if wave == "trap":
                wf = dict(VA_0=at("V(PH1)", 0.05), VA_tt=at("V(PH1)", tt),
                          VA_2tt=at("V(PH1)", 2 * tt),
                          VA_mid_fall=at("V(PH1)", 2.5 * tt),
                          VB_0=at("V(PH2)", 0.05), VB_mid_fall=at("V(PH2)", 0.5 * tt),
                          VC_0=at("V(PH3)", 0.05), VC_mid_fall=at("V(PH3)", 1.5 * tt))
                wf_ok = (abs(wf["VA_0"]) < 2e-3 and abs(wf["VA_tt"] - DV) < 3e-3
                         and abs(wf["VA_2tt"] - DV) < 3e-3
                         and abs(wf["VA_mid_fall"] - DV / 2) < 0.02
                         and abs(wf["VB_0"] - DV) < 3e-3
                         and abs(wf["VB_mid_fall"] - DV / 2) < 0.02
                         and abs(wf["VC_0"] - DV) < 3e-3
                         and abs(wf["VC_mid_fall"] - DV / 2) < 0.02)
            else:
                wf = dict(VA_0=at("V(PH1)", 0.05), VA_crest=at("V(PH1)", 1.5 * tt),
                          VA_tt=at("V(PH1)", tt), VB_trough=at("V(PH2)", tt),
                          VC_trough=at("V(PH3)", 2 * tt))
                wf_ok = (abs(wf["VA_0"]) < 2e-3 and abs(wf["VA_crest"] - DV) < 3e-3
                         and abs(wf["VA_tt"] - 0.75 * DV) < 3e-3
                         and abs(wf["VB_trough"]) < 2e-3
                         and abs(wf["VC_trough"]) < 2e-3)
            tr165, ex165 = TRIPF(1.65)
            tr120, ex120 = TRIPF(1.20)
            q1 = o["charge_spec_reported_not_gated"].get(1, {})
            chk = dict(
                waveform={k: round(v, 5) for k, v in wf.items()}, waveform_ok=wf_ok,
                trip_1p65_V=round(tr165, 5), trip_1p65_extrapolated=ex165,
                trip_1p20_V=round(tr120, 5), trip_1p20_extrapolated=ex120,
                trip_ok=bool(abs(tr165 - 0.854453) < 5e-4 and ex165 is True
                             and abs(tr120 - 0.645162) < 5e-4 and ex120 is False),
                Q_rise_bank1_fC=q1.get("Q_rise_fC"),
                Q_hold_bank1_fC=q1.get("Q_hold_fC"),
                integrator_sign_ok=bool((q1.get("Q_rise_fC") or -1) > 0),
                hold_book_sane=(abs(q1.get("Q_hold_fC") or 1e9)
                                < 0.5 * abs(q1.get("Q_rise_fC") or 1)),
                value_pass=o["value"]["PASS"],
                erosion_w3=o["erosion"][3])
            chk["PASS"] = bool(wf_ok and chk["trip_ok"]
                               and chk["integrator_sign_ok"])
            res[wave] = chk
            os.remove(p + ".prn")
    finally:
        NB = nb_save
    res["PASS"] = all(res[w].get("PASS") for w in ("trap", "sine"))
    json.dump(res, open(os.path.join(HERE, "ICB3.json"), "w"), indent=1)
    print(json.dumps(res, indent=1))
    return 0 if res["PASS"] else 1


def cmd_agg():
    R = {}
    rd = os.path.join(HERE, "runs")
    for tag in sorted(os.listdir(rd)):
        oj = os.path.join(rd, tag, "OUT.json")
        if os.path.exists(oj):
            R[tag] = json.load(open(oj))
    tts = [70, 80, 92, 105, 117, 130]
    front, ero_tab = {}, {}
    for wave in ("trap", "sine"):
        front[wave], ero_tab[wave] = {}, {}
        for tt in tts:
            best = 0
            for d in (1, 2, 3, 4):
                t = tag_of(wave, tt, d, "P0")
                if t in R and R[t].get("acceptance", {}).get("PASS"):
                    best = d
            confirmed = None
            if best:
                t1 = tag_of(wave, tt, best, "P1")
                if t1 in R:
                    confirmed = bool(R[t1].get("acceptance", {}).get("PASS"))
            if any(tag_of(wave, tt, d, "P0") in R for d in (1, 2, 3, 4)):
                e = dict(max_d_P0=best, P1_confirmed=confirmed,
                         ratio_wave_advance=round(best * T_CMOS / tt, 3),
                         ratio_wave_advance_corner=round(best * T_CMOS_CORNER / tt, 3),
                         ratio_per_bank_II=round(best * T_CMOS / (3 * tt), 3),
                         latency_per_level_ps=round(tt / best, 2) if best else None)
                front[wave][tt] = e
                ero_tab[wave][tt] = {}
                for d in (1, 2, 3, 4):
                    t = tag_of(wave, tt, d, "P0")
                    if t in R and "erosion" in R[t]:
                        e3 = R[t]["erosion"]["3"] if "3" in R[t].get("erosion", {}) \
                            else R[t]["erosion"][3]
                        ero_tab[wave][tt][d] = dict(
                            sign=e3["sign"], widths=e3["width_0mV_ps_links"],
                            overlaps=e3["overlaps_ps"],
                            asymptotic=e3["asymptotic_width_ps"])
    json.dump(dict(frontier=front, erosion=ero_tab,
                   II_note="a bank evaluates once per period 3*T_third "
                           "(occupancy 1/3); the chain advances one bank per "
                           "T_third. ratio_wave_advance = d*367.888/T_third "
                           "(the wavefront per-level rate, the task's frontier "
                           "metric); ratio_per_bank_II = d*367.888/(3*T_third) "
                           "(per-bank initiation-interval rate). Never conflated."),
              open(os.path.join(HERE, "FRONTIER3.json"), "w"), indent=1)
    print(json.dumps(dict(frontier=front), indent=1))
    return 0


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "ica3":
        sys.exit(cmd_ica3())
    if a[0] == "icb3":
        sys.exit(cmd_icb3())
    if a[0] == "lane":
        sys.exit(cmd_lane(a[1], float(a[2])))
    if a[0] == "one":
        o = cmd_one(a[1], float(a[2]), int(a[3]), a[4],
                    float(a[5]) if len(a) > 5 else 0.001,
                    keep_prn=("--keep" in a))
        sys.exit(0 if o.get("acceptance", {}).get("PASS") else 3)
    if a[0] == "agg":
        sys.exit(cmd_agg())
    print("unknown subcommand")
    sys.exit(2)
