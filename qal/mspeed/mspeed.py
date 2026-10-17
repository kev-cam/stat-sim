#!/usr/bin/env python3
"""qal/mspeed -- SPEED CEILING of the three-phase DRIVEN-mesh wave.

VACASK is the PRIMARY engine, Xyce the cross-check on anchor rows.  Everything
scored here was fixed in PRE_REGISTERED.json BEFORE this file existed.

Design and scoring are qal/mesh3 (commit 5b9d05b) VERBATIM: mesh3.py is
imported as a module; its deck() produces the Xyce deck lines (with WP/WN
scaled by s) and its scoring helpers (Trip, runs_of, edge_interp, bits, slot,
...) are the ones used here.  The extractor below is mesh3.extract() with
exactly two changes, both pre-stated:
  * the grid loader accepts either a Xyce .prn or a VACASK .raw;
  * the two mt0-sourced diagnostics (crest FINDs, third-boundary integrator
    reads) are replaced by grid / offline-trapezoid reads at the SAME nominal
    instants on BOTH engines (no +1 ps FIND lag on either side).
The gated quantities (eye / commit / die / margins / value / handoff /
erosion) are computed by the same code lines on both engines.

Subcommands:
  cert                    task 1: design point trap_tt92_d3 on BOTH engines,
                          offsets, bands, reltol ladder, wall times
  cell <eng> <s> <tt> <d> <pat> [rs]   one cell on one engine (vacask|xyce)
  sweep                   task 2 grid on VACASK, 3 workers
  chain <eng> <s> <vdd>   load-matched CMOS chain level comparator
  agg                     RESULTS.json + README tables
"""
import importlib.util, json, math, os, shutil, subprocess, sys, time, threading
from array import array
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
M3DIR = "/usr/local/src/stat-sim/qal/mesh3"
SCRATCH = ("/tmp/claude-1001/-usr-local-src/"
           "4921ad0c-f17b-4b84-986a-5917c9ebd2a6/scratchpad/mspeed")
CACHE = os.path.join(SCRATCH, "vae_cache_mspeed")
RUNS = os.path.join(SCRATCH, "runs")
XYCE = "/usr/local/src/xyce-build/src/Xyce"
VACASK = "/usr/local/bin/vacask"
MODELS_INC = "/usr/local/src/stat-sim/qal/p620a/vacask_port/sg13g2_models.inc"
ENV = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS", PYMS_VAE_CACHE=CACHE)
RELTOL = 1e-5                      # pre-stated VACASK setting (p620a port)

spec = importlib.util.spec_from_file_location("mesh3", os.path.join(M3DIR, "mesh3.py"))
m3 = importlib.util.module_from_spec(spec)
sys.modules["mesh3"] = m3
spec.loader.exec_module(m3)

GRID, NB, MG, DV, GATE_MV = m3.GRID, m3.NB, m3.MG, m3.DV, m3.GATE_MV
PATS, TRIPF = m3.PATS, m3.TRIPF
slot, bits, rxbank, phase_of = m3.slot, m3.bits, m3.rxbank, m3.phase_of
runs_of, edge_interp = m3.runs_of, m3.edge_interp
T_CMOS = m3.T_CMOS
T_CMOS_LEVEL_12 = 52.510           # ps, fcrit_skept CHAIN_SKEPT d4_d8 (1.2 V, 2 fF, s=1)
WP0, WN0 = 1.12, 0.74
_lock = threading.Lock()


# ------------------------------------------------------------------ decks
def deck_xyce(tt, d, pat, s=1.0, rs=0.001):
    """mesh3.deck() with the cell widths scaled by s (s=1 -> committed lines)."""
    with _lock:
        m3.WP, m3.WN = WP0 * s, WN0 * s
        lines, S = m3.deck("trap", tt, d, pat, rs)
        m3.WP, m3.WN = WP0, WN0
    S["s"] = s
    return lines, S


def _pwl_v(pts):
    return ", ".join("%gp,%g" % (t, v) if t > 1e-12 else "0,%g" % v for t, v in pts)


def deck_vacask(tt, d, pat, s=1.0, rs=0.001, reltol=RELTOL):
    """Element-for-element port of deck_xyce (metering networks omitted)."""
    T = 3.0 * tt
    P = PATS[pat]
    tend = 7.0 * T
    wp, wn = WP0 * s, WN0 * s
    L = ["mspeed trap tt=%g d=%d pat=%s s=%g rs=%g (port of qal/mesh3 deck)" % (tt, d, pat, s, rs),
         'load "psp103v4.osdi"', 'load "capacitor.osdi"', 'load "spice/resistor.osdi"',
         'include "%s"' % MODELS_INC,
         "model v vsource", "model rmod sp_resistor", "model cmod capacitor",
         "subckt sg13_lv_nmos (d g s b)", "  parameters w=0.15u l=0.13u",
         "  m1 (d g s b) sg13g2_nmos w=w l=l", "ends",
         "subckt sg13_lv_pmos (d g s b)", "  parameters w=0.15u l=0.13u",
         "  m1 (d g s b) sg13g2_pmos w=w l=l", "ends"]
    for k in range(1, NB + 1):
        pts = m3.trap_pts(phase_of(k), tt, T, tend)
        L.append('vph%d (phs%d 0) v type="pwl" wave=[%s]' % (k, k, _pwl_v(pts)))
        L.append("rs%d (phs%d ph%d) rmod r=%g" % (k, k, k, rs))
    for i in range(MG):
        pts, cur = [(0.0, DV * P[i])], DV * P[i]
        for n in range(1, 8):
            nxt = DV * (P[i] ^ (n & 1))
            if nxt != cur:
                pts += [(n * T - m3.EDGE / 2, cur), (n * T + m3.EDGE / 2, nxt)]
                cur = nxt
        L.append('vi1_%d (in1_%d 0) v type="pwl" wave=[%s]' % (i, i, _pwl_v(pts)))
    for k in range(1, NB + 1):
        L.append("vmg%d (gn%d 0) v dc=0" % (k, k))
        for j in range(1, d + 1):
            for i in range(MG):
                if j == 1:
                    src = "in1_%d" % i if k == 1 else "o%d_%d_%d" % (k - 1, d, i)
                else:
                    src = "o%d_%d_%d" % (k, j - 1, i)
                o = "o%d_%d_%d" % (k, j, i)
                L.append("xp%d_%d_%d (%s %s ph%d ph%d) sg13_lv_pmos w=%gu l=0.13u" % (k, j, i, o, src, k, k, wp))
                L.append("xn%d_%d_%d (%s %s gn%d gn%d) sg13_lv_nmos w=%gu l=0.13u" % (k, j, i, o, src, k, k, wn))
                L.append("cl%d_%d_%d (%s gn%d) cmod c=%gf" % (k, j, i, o, k, m3.CLOAD))
    L += ["control", '  options tran_method="gear" reltol=%g' % reltol]
    sv = ["v(ph%d)" % k for k in range(1, NB + 1)]
    sv += ["v(o%d_%d_%d)" % (k, j, i) for k in range(1, NB + 1) for j in range(1, d + 1) for i in range(MG)]
    sv += ["i(vph%d)" % k for k in range(1, NB + 1)] + ["i(vmg%d)" % k for k in range(1, NB + 1)]
    for a in range(0, len(sv), 8):
        L.append("  save " + " ".join(sv[a:a + 8]))
    L.append('  analysis tr tran step=0.1p stop=%gp maxstep=0.25p icmode="op"' % tend)
    L += ["endc", ""]
    S = dict(wave="trap", tt=tt, T=T, d=d, pat=pat, rs=rs, tend=tend, crestoff=1.5 * tt, nb=NB, s=s)
    return L, S


# ------------------------------------------------------------------ runners
def run_vacask(rundir, fn, lines, timeout=7200):
    os.makedirs(rundir, exist_ok=True)
    path = os.path.join(rundir, fn)
    open(path, "w").write("\n".join(lines))
    t0 = time.monotonic()
    try:
        r = subprocess.run([VACASK, "-qp", fn], capture_output=True, text=True, timeout=timeout, cwd=rundir)
    except subprocess.TimeoutExpired:
        return None, "TIMEOUT", timeout
    wall = time.monotonic() - t0
    raw = os.path.join(rundir, "tr.raw")
    if r.returncode != 0 or not os.path.exists(raw):
        return None, "VACASK FAIL (%.1fs): %s" % (wall, (r.stdout + r.stderr)[-600:]), wall
    return raw, "ran %s in %.1fs" % (fn, wall), wall


def run_xyce(rundir, fn, lines, timeout=7200):
    os.makedirs(rundir, exist_ok=True)
    path = os.path.join(rundir, fn)
    open(path, "w").write("\n".join(lines) + "\n")
    t0 = time.monotonic()
    try:
        r = subprocess.run([XYCE, fn], capture_output=True, text=True, timeout=timeout, cwd=rundir, env=ENV)
    except subprocess.TimeoutExpired:
        return None, "TIMEOUT", timeout
    wall = time.monotonic() - t0
    if r.returncode != 0 or not os.path.exists(path + ".prn"):
        err = "; ".join(l.strip() for l in r.stdout.splitlines() if "rror" in l or "bort" in l)[:400]
        return None, "XYCE FAIL (%.1fs): %s" % (wall, err or r.stdout[-300:]), wall
    return path + ".prn", "ran %s in %.1fs" % (fn, wall), wall


# ------------------------------------------------------------------ loaders
def load_native_prn(prn):
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
    cols = {}
    for ci, name in enumerate(hdr):
        if name == "INDEX":
            continue
        if name == "TIME":
            t = array("d", (x * 1e12 for x in raw[ci]))
        else:
            cols[name] = raw[ci]
    return t, cols


def load_native_raw(rawpath):
    sys.path.insert(0, "/usr/local/src/VACASK/python")
    from rawfile import rawread
    plot = rawread(rawpath).get()
    cols, t = {}, None
    for nm in plot.names:
        y = array("d", (float(x) for x in plot[nm]))
        low = nm.lower()
        if low == "time":
            t = array("d", (x * 1e12 for x in y))
        elif low.endswith(":flow(br)"):
            cols["I(%s)" % low[:-9].upper()] = y
        else:
            cols["V(%s)" % low.upper()] = y
    return t, cols


def to_grid(t, cols, tmax):
    """mesh3.load_grid resampling VERBATIM, from native arrays."""
    nt = len(t)
    n = int(math.floor(min(tmax, t[nt - 1]) / GRID)) + 1
    idx = array("i", bytes(4 * n))
    j = 0
    for a in range(n):
        ta = a * GRID
        while j + 1 < nt and t[j + 1] < ta:
            j += 1
        idx[a] = j
    out = {}
    for name, y in cols.items():
        g = array("d", bytes(8 * n))
        for a in range(n):
            ta = a * GRID
            jj = idx[a]
            if ta <= t[0]:
                g[a] = y[0]
            elif ta >= t[nt - 1]:
                g[a] = y[nt - 1]
            else:
                t0, t1 = t[jj], t[jj + 1]
                g[a] = y[jj] if t1 == t0 else y[jj] + (y[jj + 1] - y[jj]) * (ta - t0) / (t1 - t0)
        out[name] = g
    return n, out


def interp_native(t, y, tt):
    import bisect
    k = bisect.bisect_left(t, tt)
    if k <= 0:
        return y[0]
    if k >= len(t):
        return y[-1]
    if t[k] == t[k - 1]:
        return y[k]
    f = (tt - t[k - 1]) / (t[k] - t[k - 1])
    return y[k - 1] + f * (y[k] - y[k - 1])


def trapz_native(t, y, t0, t1):
    """trapezoid on the engine's own timegrid with exact end interpolation."""
    import bisect
    a = bisect.bisect_right(t, t0)
    b = bisect.bisect_left(t, t1)
    s = 0.0
    ya, yb = interp_native(t, y, t0), interp_native(t, y, t1)
    tp, yp = t0, ya
    for k in range(a, min(b, len(t))):
        s += 0.5 * (y[k] + yp) * (t[k] - tp)
        tp, yp = t[k], y[k]
    s += 0.5 * (yb + yp) * (t1 - tp)
    return s


# ------------------------------------------------------------------ extractor
def extract(engine, path, S, keep=False):
    """mesh3.extract() with the loader generalised and the two mt0 diagnostics
    replaced by same-instant offline reads (see module doc)."""
    d, T, tt, wave = S["d"], S["T"], S["tt"], S["wave"]
    pat = PATS[S["pat"]]
    co = S["crestoff"]
    t_nat, cols_nat = load_native_prn(path) if engine == "xyce" else load_native_raw(path)
    n, C = to_grid(t_nat, cols_nat, S["tend"])
    out = dict(S, engine=engine, n_native_points=len(t_nat))
    at = lambda sig, tp: C[sig][min(n - 1, int(round(tp / GRID)))]

    # ---- crest diagnostic (M2c): grid read at the sampling instant, NO lag
    fails, checked = [], 0
    for nn in (2, 3, 4):
        for k in range(1, NB + 1):
            tc = slot(k, nn, T, tt) + co
            rail = at("V(PH%d)" % k, tc)
            for j in range(1, d + 1):
                bb = bits(pat, k, j, nn, d)
                for i in range(MG):
                    v = at("V(O%d_%d_%d)" % (k, j, i), tc)
                    checked += 1
                    ok = (v >= 0.50 * rail) if bb[i] else (v <= 0.10 * rail)
                    if not ok:
                        fails.append([k, j, i, nn, round(v, 5), round(rail, 5)])
    out["crest_diag"] = dict(checked=checked, n_fail=len(fails), fails=fails[:12],
                             note="M2c carried: diagnostic, not gating; grid read at the sampling instant")

    # ======== FROM HERE TO 'erosion' : mesh3.extract VERBATIM ========
    rails = {k: C["V(PH%d)" % k] for k in range(1, NB + 1)}
    outs = {k: {i: C["V(O%d_%d_%d)" % (k, d, i)] for i in range(MG)} for k in range(1, NB + 1)}
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
                gs = [i for i in range(MG) if sel == "all" or (bb[i] == 1) == (sel == "HIGH")]
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
                rec[thr_name] = dict(open_ps=round(ta, 3), close_ps=round(tb, 3), width_ps=round(tb - ta, 3),
                                     open_minus_srx_ps=round(ta - srx, 3), clipped_end=bool(b + w0 >= w1),
                                     extrap_hi_fraction=round(n_extrap_hi / float(w1 - w0 + 1), 3))
                if thr_name == "0mV":
                    rec["commit_gated_ps"] = round(ta, 3)
                    rec["die_ps"] = round(tb, 3)
            cur = mcur["all"]
            rmask = bytearray(w1 - w0 + 1)
            for a in range(w1 - w0 + 1):
                rmask[a] = 1 if cur[a] > 0.0 else 0
            rr2 = runs_of(rmask, 0, w1 - w0)
            q0 = int(sk / GRID) - w0
            q1 = int((sk + 2 * tt) / GRID) - w0
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
            probe = min(w1, int((srx + co) / GRID)) - w0
            rec["margin_at_rx_crest_mV"] = {sel: (round(mcur[sel][probe], 2) if mcur[sel] is not None else None)
                                            for sel in ("all", "HIGH", "LOW")}
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
                rec["die_cause"] = dict(t_inputdeath_ps=tid, own_fall_start_ps=round(ofs, 2),
                                        first=("input_death" if (tid is not None and tid < ofs) else "own_rail_fall"))
            # (mspeed addition, reported only) establishment relative instants
            if rec.get("commit_raw_ps") is not None:
                rec["establish_minus_srx_ps"] = round(rec["commit_raw_ps"] - srx, 3)
                rec["establish_minus_own_rise_ps"] = round(rec["commit_raw_ps"] - sk, 3)
            links[k][nn] = rec

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
                rec["margin_at_commit_mV"] = {kk: (round(v, 2) if v < 1e8 else None) for kk, v in ms.items()}
                rec["trip_at_commit_V"] = round(t_, 4)
                rec["trip_extrapolated"] = bool(ex)
            handoff[k][nn] = rec
    out["links"] = links
    out["handoff"] = handoff

    allout = {k: {j: {i: C["V(O%d_%d_%d)" % (k, j, i)] for i in range(MG)} for j in range(1, d + 1)}
              for k in range(1, NB + 1)}
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
    out["value"] = dict(checked=vchecked, n_fail=len(vfails), fails=vfails[:20], PASS=(not vfails),
                        interior_stale_diag_n=len(interior_diag), interior_stale_diag=interior_diag[:10],
                        restored_HIGH_min_V=(round(min_high_V, 4) if min_high_V is not None else None),
                        note="M2b/M4b/M4d carried: last-level word at validity midpoint")

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
    out["rising_lag_ps"] = dict(min=min(lags) if lags else None, max=max(lags) if lags else None,
                                median=sorted(lags)[len(lags) // 2] if lags else None)

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
            droop[k] = dict(rail_hold_min_V=round(min(mins), 4), rail_hold_mean_V=round(sum(means) / len(means), 4),
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
            bump.append(dict(bank=k, wave=nn, LOW_rise_over_hold_mV=round(1000 * (pk - ref), 2)))
    worstb = max((r["LOW_rise_over_hold_mV"] for r in bump), default=None)
    out["hold_bump"] = dict(worst_LOW_rise_mV=worstb, rows=bump[:12])

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
            rows.append(dict(wave=nn, trough_ps=ts, Ignd_pk_uA=round(max(abs(x) for x in img) * 1e6, 3),
                             Ignd_mean_uA=round(sum(img) / len(img) * 1e6, 4),
                             Iph_pk_uA=round(max(abs(x) for x in iph) * 1e6, 3),
                             rail_lt_10pct_window_ps=round(hi0 - lo0, 1),
                             Ignd_mean_10pct_uA=round(sum(imgw) / len(imgw) * 1e6, 4),
                             Q_gnd_10pct_fC=round(sum(imgw) * GRID * 1e3, 4)))
        crow[k] = rows
    out["crowbar"] = crow

    # ---- charge/energy books: OFFLINE trapezoid on the engine's own timegrid
    # (replaces the mt0 integrator reads; same nominal instants, both engines)
    ch = {}
    tot_e, tot_q = [], []
    for k in range(1, NB + 1):
        iph = cols_nat["I(VPH%d)" % k]
        vph = cols_nat["V(PH%d)" % k]
        pw = array("d", (-a * b for a, b in zip(vph, iph)))
        iq = array("d", (-a for a in iph))
        acc = {x: [] for x in ("qr", "qh", "qf", "er", "eh", "ef")}
        for nn in (2, 3, 4):
            ts = slot(k, nn, T, tt)
            b = [ts, ts + tt, ts + 2 * tt, ts + T]
            acc["qr"].append(trapz_native(t_nat, iq, b[0], b[1]) * 1e3)   # ps*A -> fC
            acc["qh"].append(trapz_native(t_nat, iq, b[1], b[2]) * 1e3)
            acc["qf"].append(trapz_native(t_nat, iq, b[2], b[3]) * 1e3)
            acc["er"].append(trapz_native(t_nat, pw, b[0], b[1]) * 1e3)   # ps*W -> fJ
            acc["eh"].append(trapz_native(t_nat, pw, b[1], b[2]) * 1e3)
            acc["ef"].append(trapz_native(t_nat, pw, b[2], b[3]) * 1e3)
        mean = lambda v: round(sum(v) / len(v), 3)
        ch[k] = dict(phase="ABC"[phase_of(k)], Q_rise_fC=mean(acc["qr"]), Q_hold_fC=mean(acc["qh"]),
                     Q_fall_fC=mean(acc["qf"]), E_rise_fJ=mean(acc["er"]), E_hold_fJ=mean(acc["eh"]),
                     E_fall_fJ=mean(acc["ef"]),
                     E_cycle_net_fJ=round(mean(acc["er"]) + mean(acc["eh"]) + mean(acc["ef"]), 3))
        tot_e.append(ch[k]["E_cycle_net_fJ"])
        tot_q.append(ch[k]["Q_rise_fC"] + ch[k]["Q_hold_fC"])
    out["charge_spec_reported_not_gated"] = ch
    out["energy_reported"] = dict(E_bank_cycle_net_fJ_mean=round(sum(tot_e) / NB, 3),
                                  E_per_cell_eval_fJ=round(sum(tot_e) / NB / (MG * d), 4),
                                  Q_supplied_rise_plus_hold_fC_mean=round(sum(tot_q) / NB, 3),
                                  method="offline trapezoid of -V(ph)*I(VPH) on the engine's native timegrid, "
                                         "per third, mean of waves 2..4; REPORTED, never gated")

    ero = {}
    for nn in (2, 3, 4):
        wid = []
        for k in range(1, NB + 1):
            e = links[k][nn].get("0mV", {})
            wid.append(e.get("width_ps"))
        ovs = [handoff[k][nn].get("overlap_ps") for k in range(1, NB)]
        real = [w for w in wid[:NB - 1] if w is not None]
        sign = "EXTINCT"
        if len(real) == NB - 1:
            if real[-1] >= 0.85 * real[0]:
                sign = "SUSTAINS"
            elif real[-1] >= 0.5 * real[0]:
                sign = "ERODES_SLOW"
            else:
                sign = "ERODES"
        asym = None
        if len(real) >= 2 and real[-2] > 0 and abs(real[-1] - real[-2]) <= 0.15 * real[-2]:
            asym = round(0.5 * (real[-1] + real[-2]), 2)
        ero[nn] = dict(width_0mV_ps_links=wid, overlaps_ps=ovs, sign=sign, asymptotic_width_ps=asym)
    out["erosion"] = ero

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
    out["acceptance"] = dict(A_value=out["value"]["PASS"], B_eye=b_ok, C_handoff=c_ok,
                             worst_margin_at_commit_mV=worst_m, worst_overlap_ps=worst_ov,
                             PASS=bool(out["value"]["PASS"] and b_ok and c_ok))
    # ======== end of the mesh3 VERBATIM block ========

    # ---- mspeed additions (reported): latency and rates
    lat5, lat6, est_srx, est_own = [], [], [], []
    for nn in (2, 3, 4):
        if (5, nn) in tcommit:
            lat5.append(tcommit[(5, nn)] - nn * T)
        if (6, nn) in tcommit:
            lat6.append(tcommit[(6, nn)] - nn * T)
        for k in range(1, NB):
            if (k, nn) in tcommit:
                est_srx.append(tcommit[(k, nn)] - slot(k + 1, nn, T, tt))
                est_own.append(tcommit[(k, nn)] - slot(k, nn, T, tt))
    out["latency_reported"] = dict(
        wavefront_per_level_ps=round(tt / d, 3),
        true_latency_head_to_link5_commit_ps=(round(max(lat5), 3) if lat5 else None),
        true_per_level_latency_ps=(round(max(lat5) / (5 * d), 3) if lat5 else None),
        true_per_level_latency_link6_derived_ps=(round(max(lat6) / (6 * d), 3) if lat6 else None),
        establish_minus_srx_ps_max=(round(max(est_srx), 3) if est_srx else None),
        establish_minus_own_rise_ps_max=(round(max(est_own), 3) if est_own else None),
        note="true latency = commit_raw(link 5) - n*T (head edge at n*T to the REAL bank-6 receiver's "
             "commit), per level over 5d levels; worst of waves 2..4")
    out["rates"] = dict(wavefront_level_rate_vs_cmos=round(d * T_CMOS / tt, 3),
                        per_lane_results_per_s=round(1e12 / (3 * tt)),
                        per_bank_II_rate_vs_cmos=round(d * T_CMOS / (3 * tt), 3))
    with _lock:
        json.dump(out, open(os.path.join(os.path.dirname(path), "OUT_%s.json" % engine), "w"), indent=1)
    if not keep:
        os.remove(path)
    return out


# ------------------------------------------------------------------ cells
def tag_of(s, tt, d, pat, rs=0.001):
    t = "s%g_tt%g_d%d" % (s, tt, d)
    if pat != "P0":
        t += "_" + pat
    if rs != 0.001:
        t += "_rs%g" % rs
    return t


def repo_dir(tag):
    p = os.path.join(HERE, "runs", tag)
    os.makedirs(p, exist_ok=True)
    return p


def cmd_cell(engine, s, tt, d, pat, rs=0.001, keep=False, reltol=RELTOL, force=False):
    tag = tag_of(s, tt, d, pat, rs)
    if reltol != RELTOL:
        tag += "_rt%g" % reltol
    oj = os.path.join(HERE, "runs", tag, "OUT_%s.json" % engine)
    if os.path.exists(oj) and not force:
        o = json.load(open(oj))
        if "error" not in o:
            print("  cached", engine, tag, flush=True)
            return o
    rundir = os.path.join(RUNS, tag + "_" + engine)
    if engine == "vacask":
        lines, S = deck_vacask(tt, d, pat, s, rs, reltol)
        path, msg, wall = run_vacask(rundir, "c_%s.sim" % tag, lines)
    else:
        lines, S = deck_xyce(tt, d, pat, s, rs)
        path, msg, wall = run_xyce(rundir, "c_%s.cir" % tag, lines)
    print("  %s %s %s (load %.1f)" % (engine, tag, msg, os.getloadavg()[0]), flush=True)
    rd = repo_dir(tag)
    if path is None:
        json.dump(dict(S, engine=engine, error=msg, wall_s=wall), open(oj, "w"), indent=1)
        return dict(S, engine=engine, error=msg, acceptance=dict(PASS=False))
    o = extract(engine, path, S, keep)
    o["wall_s"] = round(wall, 2)
    o["loadavg_at_end"] = os.getloadavg()[0]
    json.dump(o, open(oj, "w"), indent=1)
    for f in os.listdir(rundir):
        if f.endswith((".sim", ".cir", ".mt0")):
            shutil.copy2(os.path.join(rundir, f), os.path.join(rd, f))
    a, e3 = o["acceptance"], o["erosion"][3]
    print("  %s %s value=%s eye=%s handoff=%s worst_margin=%s worst_ov=%s erosion=%s widths=%s E=%s fJ -> %s"
          % (engine, tag, a["A_value"], a["B_eye"], a["C_handoff"], a["worst_margin_at_commit_mV"],
             a["worst_overlap_ps"], e3["sign"], e3["width_0mV_ps_links"],
             o["energy_reported"]["E_bank_cycle_net_fJ_mean"], "PASS" if a["PASS"] else "FAIL"), flush=True)
    return o


# ------------------------------------------------------------------ CMOS chain comparator
def chain_decks(s, vdd, depth=12):
    wp, wn = WP0 * s, WN0 * s
    X = ['.hdl "%s"' % m3.VA, '.include "%s"' % m3.MODEL, '.include "%s"' % m3.SHIM,
         '.OPTIONS TIMEINT METHOD=GEAR RELTOL=1e-6 ABSTOL=1e-15 CHGTOL=1e-17',
         "VSUP sup 0 %g" % vdd, "VDI di 0 PWL(0 0 100p 0 102p %g)" % vdd]
    V = ["cmos chain comparator s=%g vdd=%g" % (s, vdd), 'load "psp103v4.osdi"', 'load "capacitor.osdi"',
         'include "%s"' % MODELS_INC, "model v vsource", "model cmod capacitor",
         "subckt sg13_lv_nmos (d g s b)", "  parameters w=0.15u l=0.13u", "  m1 (d g s b) sg13g2_nmos w=w l=l", "ends",
         "subckt sg13_lv_pmos (d g s b)", "  parameters w=0.15u l=0.13u", "  m1 (d g s b) sg13g2_pmos w=w l=l", "ends",
         "vsup (sup 0) v dc=%g" % vdd, 'vdi (di 0) v type="pwl" wave=[0,0, 100p,0, 102p,%g]' % vdd]
    prev = "di"
    for nnode in range(1, depth + 1):
        o = "d%d" % nnode
        X.append("XP%d %s %s sup sup sg13_lv_pmos w=%gu l=0.13u" % (nnode, o, prev, wp))
        X.append("XN%d %s %s 0 0 sg13_lv_nmos w=%gu l=0.13u" % (nnode, o, prev, wn))
        X.append("CD%d %s 0 2f" % (nnode, o))
        V.append("xp%d (%s %s sup sup) sg13_lv_pmos w=%gu l=0.13u" % (nnode, o, prev, wp))
        V.append("xn%d (%s %s 0 0) sg13_lv_nmos w=%gu l=0.13u" % (nnode, o, prev, wn))
        V.append("cd%d (%s 0) cmod c=2f" % (nnode, o))
        prev = o
    X += [".tran 0.02p 1000p 0 0.1p", ".print tran V(di) " + " ".join("V(d%d)" % k for k in range(1, depth + 1)), ".end"]
    V += ["control", '  options tran_method="gear" reltol=%g' % RELTOL,
          "  save v(di) " + " ".join("v(d%d)" % k for k in range(1, depth + 1)),
          '  analysis tr tran step=0.02p stop=1000p maxstep=0.1p icmode="op"', "endc", ""]
    return X, V


def tcross(t, y, thr, rising):
    for k in range(1, len(t)):
        if rising and y[k - 1] < thr <= y[k] or (not rising) and y[k - 1] > thr >= y[k]:
            return t[k - 1] + (thr - y[k - 1]) * (t[k] - t[k - 1]) / (y[k] - y[k - 1])
    return None


def cmd_chain(engine, s, vdd):
    tag = "chain_s%g_v%g" % (s, vdd)
    rundir = os.path.join(RUNS, tag + "_" + engine)
    X, V = chain_decks(s, vdd)
    if engine == "vacask":
        path, msg, wall = run_vacask(rundir, tag + ".sim", V)
    else:
        path, msg, wall = run_xyce(rundir, tag + ".cir", X)
    print("  chain", engine, tag, msg, flush=True)
    if path is None:
        return dict(error=msg)
    t, cols = load_native_prn(path) if engine == "xyce" else load_native_raw(path)
    t90, t50 = {}, {}
    for nnode in range(1, 13):
        y = cols["V(D%d)" % nnode]
        rising = (nnode % 2 == 0)
        t90[nnode] = tcross(t, y, (0.9 if rising else 0.1) * vdd, rising)
        t50[nnode] = tcross(t, y, 0.5 * vdd, rising)
    r = dict(engine=engine, s=s, vdd=vdd, wall_s=round(wall, 2),
             per_stage_90_d4_d8_ps=round((t90[8] - t90[4]) / 4, 4),
             per_stage_90_d6_d10_ps=round((t90[10] - t90[6]) / 4, 4),
             per_stage_50_d4_d8_ps=round((t50[8] - t50[4]) / 4, 4),
             t90_ps={k: round(v, 4) for k, v in t90.items()},
             definition="fcrit_skept CHAIN_SKEPT: (t90(d8)-t90(d4))/4, t90 = 0.9*VDD rising crossing on even "
                        "nodes; depth-12 chain of the scaled cell, 2 fF per node, 2 ps input edge")
    rd = repo_dir(tag)
    json.dump(r, open(os.path.join(rd, "CHAIN_%s.json" % engine), "w"), indent=1)
    for f in os.listdir(rundir):
        if f.endswith((".sim", ".cir")):
            shutil.copy2(os.path.join(rundir, f), os.path.join(rd, f))
    os.remove(path)
    print("  ", json.dumps({k: r[k] for k in ("per_stage_90_d4_d8_ps", "per_stage_90_d6_d10_ps", "per_stage_50_d4_d8_ps")}))
    return r


# ------------------------------------------------------------------ sweep
S_GRID, TT_GRID, D_GRID = (1, 2, 4), (92, 80, 70, 60, 50, 40), (2, 3, 4)


def cmd_sweep(workers=3):
    cells = [(s, tt, d) for s in S_GRID for d in D_GRID for tt in TT_GRID]
    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(lambda c: cmd_cell("vacask", c[0], c[1], c[2], "P0"), cells))
    return 0


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "cell":
        o = cmd_cell(a[1], float(a[2]), float(a[3]), int(a[4]), a[5],
                     float(a[6]) if len(a) > 6 and not a[6].startswith("--") else 0.001,
                     keep=("--keep" in a),
                     reltol=float(a[a.index("--reltol") + 1]) if "--reltol" in a else RELTOL,
                     force=("--force" in a))
        sys.exit(0 if o.get("acceptance", {}).get("PASS") else 3)
    if a[0] == "chain":
        cmd_chain(a[1], float(a[2]), float(a[3]))
        sys.exit(0)
    if a[0] == "sweep":
        sys.exit(cmd_sweep(int(a[1]) if len(a) > 1 else 3))
    print("unknown subcommand")
    sys.exit(2)
