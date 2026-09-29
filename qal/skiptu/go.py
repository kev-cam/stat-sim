#!/usr/bin/env python3
"""Driver.  Stages:  anchor | probe <scheme> <dv> | row <spec> | grid <name>

Rows are appended to rows.json as they finish, so an interrupted sweep loses
nothing.  <= 4 concurrent Xyce jobs (the box is shared).
"""
import json, os, sys, time, itertools, threading
from concurrent.futures import ThreadPoolExecutor, as_completed
sys.path.insert(0, "/usr/local/src/stat-sim/qal/skip4")
sys.path.insert(0, "/usr/local/src/stat-sim/qal/skiptu")
import skip as SK
import tu, tuextract as extract

HERE = tu.HERE
ROWS = os.path.join(HERE, "rows.json")
ZCACHE = os.path.join(HERE, "zeros.json")
TUZ = os.path.join(HERE, "tu_zeros.json")
L_NH, W_UM = 15.0, 30.0
LK = threading.Lock()   # the tfw/zeros caches are written from the probe pool
NPROC = 4


def load(p, d):
    if os.path.exists(p):
        try:
            return json.load(open(p))
        except Exception:
            return d
    return d


def save(p, o):
    json.dump(o, open(p, "w"), indent=1, default=str)


def zeros_for(scheme, dv, T, mode="free", **kw):
    """RE-PROBED per scheme, dv AND BEAT PERIOD -- never the analytic pi*sqrt(LC).

    T is part of the key, and that is a CORRECTION, not a nicety.  MEASURED: with one
    T=120 probe reused at every beat, hop 2's interrupted current at its switch open
    was -12.0 uA at T=160, -19.9 at T=200 and -29.0 at T=300, against a 1.0 uA A6
    gate -- because hop 2 drains bank 2, a HEAD whose rail has drifted further by the
    time it drains, so the LC initial condition and hence the true zero move with T.
    Reusing one zero across beat periods strands charge and corrupts both the rail and
    the energy accounting.  One probe per (scheme, dv, T, mode)."""
    with LK:
        z = load(ZCACHE, {})
    key = "%s_dv%d_T%d_%s%s" % (scheme, round(dv * 1000), round(T), mode,
                                ("_t%g" % kw["t_on"]) if "t_on" in kw else "")
    if key in z:
        return z[key]
    tz = tu.probe_zeros(scheme, T, W_UM, L_NH, dv, key, mode=mode, **kw)
    if tz is None:
        return None
    with LK:
        z = load(ZCACHE, {})
        z[key] = tz
        save(ZCACHE, z)
    return tz


T_TFW = 200.0   # the beat period at which every tfw is probed, then reused.
# JUSTIFIED, and checked: the top-up inductor's current zero is set by its own
# hardware (Ltu, switch width, t_on) and the rail it discharges into, not by the
# beat period -- the pulse happens entirely inside one hold window and nothing else
# is switching while it decays.  One T=200 probe per (scheme, dv, Ltu, wsw, t_on)
# therefore serves every T, and a spot re-probe at T=300 is run as a check.


def tfw_for(scheme, mode, T, dv, ltu, wsw, ton, foff, tz, force_T=None):
    """AMENDMENT A1: the MEASURED freewheel window, probed per bank and cached."""
    if not mode.startswith("ptu"):
        return None
    with LK:
        z = load(TUZ, {})
    Tp = force_T or T_TFW
    key = "%s_T%d_dv%d_L%g_W%g_t%g_%s" % (
        scheme, Tp, round(dv * 1000), ltu, wsw, ton, mode)
    if key in z:
        return {int(k): v for k, v in z[key].items()}
    tag = key
    tzp = zeros_for(scheme, dv, Tp)
    tfw = tu.probe_topup_zeros(scheme, Tp, W_UM, L_NH, dv, tag, tzp, ltu, wsw, ton,
                               fire_off=0.0)
    if tfw is None:
        return None
    with LK:
        z = load(TUZ, {})
        z[key] = tfw
        save(TUZ, z)
    return tfw


def one_row(spec):
    scheme, mode, T, dv, ltu, wsw, ton, foff = spec
    # The hop zeros MUST be probed in the ROW'S OWN MODE.  MEASURED: the resistive
    # top-up's transmission gates load the destination rail with their drain
    # capacitance even while OFF, which shifts the hop's LC resonance and moves its
    # true zero; reusing the free-mode zeros left 221.8 / 219.5 uA of interrupted
    # inductor current against the 1.0 uA A6 gate.
    zmode = "rtu" if mode == "rtu" else "free"
    tz = zeros_for(scheme, dv, T, mode=zmode,
                   **({"t_on": ton} if zmode == "rtu" else {}))
    if tz is None:
        return dict(spec=list(spec), ERROR="probe failed")
    tag = "r_%s_%s_T%d_dv%d_L%g_W%g_t%g_f%g" % (
        scheme, mode, T, round(dv * 1000), ltu, wsw, ton, foff)
    tfw = tfw_for(scheme, mode, T, dv, ltu, wsw, ton, foff, tz)
    if mode.startswith("ptu") and tfw is None:
        return dict(tag=tag, spec=list(spec), ERROR="top-up ZCS probe failed")
    lines, S, fires = tu.deck(scheme, mode, T, W_UM, L_NH, dv, tz=tz,
                              ltu_nh=ltu, wsw=wsw, t_on=ton, fire_off=foff,
                              tfw=tfw)
    p, msg = tu.run(tag + ".cir", lines)
    if p is None:
        return dict(tag=tag, spec=list(spec), ERROR=msg)
    m = SK.parse_mt0(p + ".mt0")
    r = extract.row(scheme, mode, T, dv, m, S, fires, L_NH, W_UM, ltu, wsw, ton, foff, tz)
    r["tag"] = tag
    r["deck"] = os.path.basename(p)
    r["run_msg"] = msg
    return r


def grid(specs, label):
    rows = load(ROWS, [])
    # ERROR rows are NOT treated as done -- they are retried, so that a row lost to a
    # harness bug comes back once the bug is fixed instead of silently staying absent.
    have = {r.get("tag") for r in rows if "ERROR" not in r}
    todo = []
    for s in specs:
        scheme, mode, T, dv, ltu, wsw, ton, foff = s
        tag = "r_%s_%s_T%d_dv%d_L%g_W%g_t%g_f%g" % (
            scheme, mode, T, round(dv * 1000), ltu, wsw, ton, foff)
        if tag not in have:
            todo.append(s)
    print("grid %s: %d specs, %d already done, %d to run"
          % (label, len(specs), len(specs) - len(todo), len(todo)), flush=True)
    # probe every (scheme,dv) pair serially FIRST so the parallel rows all reuse
    # one cached set of measured zeros (and the probe decks never race).
    hop_keys = sorted({(s_[0], s_[3], s_[2],
                        "rtu" if s_[1] == "rtu" else "free",
                        s_[6] if s_[1] == "rtu" else 0.0) for s_ in todo})
    print("  %d distinct HOP ZCS probes (per scheme/dv/T/mode)" % len(hop_keys), flush=True)
    with ThreadPoolExecutor(max_workers=NPROC) as ex:
        fs = {ex.submit(zeros_for, sc, dv, T, md,
                        **({"t_on": tn} if md == "rtu" else {})): (sc, dv, T, md)
              for sc, dv, T, md, tn in hop_keys}
        for f in as_completed(fs):
            try:
                r = f.result()
            except Exception as e:
                r = None
                print("  HOP-PROBE EXC %s: %s" % (fs[f], e), flush=True)
            if r is None:
                print("  HOP-PROBE FAILED for %s" % (fs[f],), flush=True)
    # the top-up ZCS probes, run in PARALLEL (they are independent decks) but
    # de-duplicated first, since tfw is reused across beat periods.
    need = {}
    for s_ in todo:
        scheme, mode, T, dv, ltu, wsw, ton, foff = s_
        if mode.startswith("ptu"):
            need[(scheme, mode, dv, ltu, wsw, ton)] = s_
    if need:
        print("  %d distinct top-up ZCS probes to run" % len(need), flush=True)
        with ThreadPoolExecutor(max_workers=NPROC) as ex:
            fs = {}
            for kk, s_ in need.items():
                scheme, mode, T, dv, ltu, wsw, ton, foff = s_
                tz = zeros_for(scheme, dv, T_TFW)
                if tz is None:
                    continue
                fs[ex.submit(tfw_for, scheme, mode, T, dv, ltu, wsw, ton, 0.0, tz)] = kk
            for f in as_completed(fs):
                try:
                    r = f.result()
                except Exception as e:
                    r = None
                    print("  TU-PROBE EXC %s: %s" % (fs[f], e), flush=True)
                if r is None:
                    print("  TU-PROBE FAILED for %s" % (fs[f],), flush=True)
    with ThreadPoolExecutor(max_workers=NPROC) as ex:
        futs = {ex.submit(one_row, s): s for s in todo}
        for f in as_completed(futs):
            try:
                r = f.result()
            except Exception as e:
                r = dict(spec=list(futs[f]), ERROR="EXC %s" % e)
            with LK:
                rows = load(ROWS, [])
                rows = [x for x in rows if x.get("tag") != r.get("tag")]
                rows.append(r)
                save(ROWS, rows)
            if "ERROR" in r:
                print("  %-52s ERROR %s" % (r.get("tag", "?"), r["ERROR"][:90]), flush=True)
            else:
                a = r["ACCEPTANCE"]
                print("  %-52s worst %6.2f%%  minHIGH %.4f V  A1=%s A2=%s"
                      % (r["tag"], a["A1_worst_gate_pct"] or -1,
                         a["A2_min_delivered_high_V"] or -1,
                         a["A1_all_four_stages_90pct"], a["A2_all_stages_clear_0p4400"]),
                      flush=True)


# ------------------------------------------------------------------- the grids
# Ltu is centred on the MEASURED scaling tfw ~ sqrt(Ltu) (141 / 230 / 424 ps at
# 5 / 15 / 50 nH): the pulse must COMPLETE inside the bank's hold window, which is
# 62 ps at T=160 and 202 ps at T=300, so Ltu ~ 1-2 nH is the only part of the range
# that can fit at a short beat.  That is a measurement driving the grid, not a guess.

def g_ctrl():
    """(d) WITHOUT held-bank top-up FIRST: my own control, both dV, every beat."""
    return [("s4", "free", T, dv, 5.0, 10.0, 12.0, 0.0)
            for dv in (1.2, 1.5) for T in (120, 160, 200, 300)]


def g_str():
    """STRENGTH sweep: Q ~ t_on^2/Ltu.  Monotone, or an interior optimum?"""
    return [("s4", "ptu", 200, 1.2, ltu, 10.0, ton, 0.0)
            for ltu in (1.0, 2.0, 5.0, 15.0) for ton in (6.0, 12.0, 24.0)]


def g_wid():
    """Switch WIDTH: the top-up path is resistance-dominated, so width is a real
    strength knob -- and a width that must track the load is the B-invariant cost
    the brief warns about.  Measured against its own gate-drive energy."""
    return [("s4", "ptu", 200, 1.2, 2.0, w, 12.0, 0.0) for w in (5.0, 20.0, 40.0)]


def g_dv15():
    """dV = 1.5, the level the PDK actually characterises the same 84 cells at."""
    return [("s4", "ptu", 200, 1.5, ltu, 10.0, ton, 0.0)
            for ltu in (1.0, 2.0, 5.0) for ton in (12.0, 24.0)]


def g_beat():
    """Does a top-up that FITS the hold window buy a shorter beat?"""
    return [("s4", "ptu", T, dv, 1.0, 10.0, 12.0, 0.0)
            for dv in (1.2, 1.5) for T in (120, 160, 300)]


def g_tim():
    """TIMING sweep + the deliberate LATE negative control (chain3's goalpost)."""
    out = [("s4", "ptu", 200, 1.2, 1.0, 10.0, 12.0, f) for f in (10.0, 25.0, 50.0)]
    out += [("s4", "ptulate", 200, dv, 1.0, 10.0, 12.0, 0.0) for dv in (1.2, 1.5)]
    return out


def g_dv10():
    """dV = 1.0 -- ONLY so that measurement 5 (accumulated droop against the ~120 mV
    budget = cliff + 44 mV) can be answered at the dV the budget was stated at.
    Not a headline operating point."""
    return [("s4", m, 200, 1.0, 1.0, 10.0, 12.0, 0.0) for m in ("free", "ptu")]


def g_rtu():
    """THE BOUNDING TOP-UP: chain3's resistive tg to the supply, device and window
    placement verbatim, 20 ps window at the START of the hold.  It restores the rail as
    hard as a supply can, so it upper-bounds what ANY top-up can do for settling."""
    out = [("s4", "rtu", T, dv, 1.0, 10.0, 20.0, 0.0)
           for dv in (1.2, 1.5) for T in (120, 160, 200, 300)]
    out += [("s4", "rtu", 200, 1.2, 1.0, 10.0, w, 0.0) for w in (10.0, 40.0)]
    return out


def g_h5b():
    """The 5-bank chain, free and BOUNDING-top-up: the only topology here in which a
    HOP-CHARGED bank experiences the full two-beat charge-THEN-DRAIN hold."""
    return [("s5", m, T, 1.2, 1.0, 10.0, 20.0, 0.0)
            for m in ("free", "rtu") for T in (200, 300)]


def g_dv10b():
    """dV = 1.0, for measurement 5 against the ~120 mV budget at its own dV."""
    return [("s4", m, 200, 1.0, 1.0, 10.0, 20.0, 0.0) for m in ("free", "rtu")]


def g_h5():
    """The 5-bank chain: the ONLY topology here in which a HOP-CHARGED bank actually
    experiences the full two-beat charge-THEN-DRAIN hold that measurement 3 asks
    about.  In the 4-bank chain bank 3 is charged and never drained."""
    return [("s5", m, T, 1.2, 1.0, 10.0, 12.0, 0.0)
            for m in ("free", "ptu") for T in (200, 300)]


GRIDS = dict(ctrl=g_ctrl, str=g_str, wid=g_wid, dv15=g_dv15,
             beat=g_beat, tim=g_tim, h5=g_h5, dv10=g_dv10,
             rtu=g_rtu, h5b=g_h5b, dv10b=g_dv10b)

if __name__ == "__main__":
    what = sys.argv[1]
    if what == "grid":
        for nm in sys.argv[2:]:
            grid(GRIDS[nm](), nm)
    elif what == "probe":
        print(zeros_for(sys.argv[2], float(sys.argv[3]), float(sys.argv[4])))
