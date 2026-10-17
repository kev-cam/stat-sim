#!/usr/bin/env python3
"""qal/ldrive STEP 1 -- which CURRENT-source drive shapes sustain the 3-phase
mesh wave?  PRE_REGISTERED.json (sha256 8bc4cc56..., mtime 2026-10-16
21:22:47.498 -0700) was the ONLY file in qal/ldrive/ before this file existed.

Everything here is deliberately IDEAL (current sources, 1.65 V DC clamp rail,
VSWITCH clamps with RON = the committed 1 mOhm series RS, a floor
diode-switch standing in for the body diodes): every number is a BOUND on an
inductor-switched drive, never a buildable figure.

Per bank k (phase p = (k-1) mod 3, slot start a = m*T + p*tt):
  rise  [a, a+tt]      ideal current +I_r into the rail (0.5 ps edges)
  hold  [a+tt, a+2tt]  VSWITCH clamp to VH = 1.65 V DC
  fall  [a+2tt, a+3tt] ideal current -I_f; floor switch to 0 V at the end
  FIXED mode   : clamp on exactly [tt,2tt]; floor on [3tt-2ps, 3tt]
  LATCHED mode : source +I_r until V(rail) first reaches 1.649 V (comparator
                 latch, tau 0.2 ps) then clamp on until 2tt; -I_f until
                 V(rail) first reaches 1 mV then floor on until 3tt
  TWO_SLOPE    : FIXED clamp, rise = I1 for tt/2 then I2 for tt/2 (the
                 measured 0.86 -> 2.29 mA demand halves, same 144.9 fC)
The committed mesh3 deck is otherwise VERBATIM: VPHk kept as a 0 V ammeter
(same sign as the committed supply), RSk, cells, words, .tran, .options,
.print list and the QPH/EPH boundary reads are untouched, so the committed
extract() scores every row unchanged.
"""
import importlib.util, json, math, os, shutil, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
M3 = "/usr/local/src/stat-sim/qal/mesh3/mesh3.py"
spec = importlib.util.spec_from_file_location("mesh3", M3)
mesh3 = importlib.util.module_from_spec(spec)
sys.modules["mesh3"] = mesh3
spec.loader.exec_module(mesh3)

SCRATCH = ("/tmp/claude-1001/-usr-local-src/"
           "4921ad0c-f17b-4b84-986a-5917c9ebd2a6/scratchpad")
CACHE = os.path.join(SCRATCH, "vae_cache_ldrive")
RUNS = os.path.join(SCRATCH, "ldrive_runs")
os.makedirs(RUNS, exist_ok=True)
mesh3.ENV = dict(os.environ, PYMS_DIR="/usr/local/share/xyce/PyMS",
                 PYMS_VAE_CACHE=CACHE)

DV, TT, D = 1.65, 92.0, 3
T = 3 * TT
NB = mesh3.NB
LAG = mesh3.LAG_PS
EDGE = float(os.environ.get("LDRIVE_EDGE", "1.0"))   # ps, every boundary edge is [t_b, t_b+EDGE]
NOFLOOR = bool(os.environ.get("LDRIVE_NOFLOOR"))
NOMETER = bool(os.environ.get("LDRIVE_NOMETER"))
ERROPT = bool(os.environ.get("LDRIVE_ERROPT"))
GC = float(os.environ.get("LDRIVE_GC", "1.0"))   # S, clamp/floor conductance when engaged
GD = 1.0                   # S, floor diode conductance (V<0 only)
TEND_OVERRIDE = os.environ.get("LDRIVE_TEND")    # test-only truncation
FLOOR_PRE = 2.0            # ps, FIXED floor window before the trough
WOFF = 0.2                 # ps, LATCHED window-edge offset
LSET = float(os.environ.get("LDRIVE_LSET", "3.3"))   # latch set rate (A on 1 pF): tau = 1/LSET ps
LRST = float(os.environ.get("LDRIVE_LRST", "5"))     # latch reset rate
NOMEAS = bool(os.environ.get("LDRIVE_NOMEAS"))        # diagnostic only
LVAR = os.environ.get("LDRIVE_LVAR", "")              # diagnostic variants
TANHW = float(os.environ.get("LDRIVE_TANHW", "0.0025"))  # V, comparator band scale
VTOP = DV - 0.006          # latch band centre (top): 1.644 V, band ~1.639-1.649
VBOT = 0.006               # latch band centre (floor): 6 mV, band ~1-11 mV
BASE_DIR = "/usr/local/src/stat-sim/qal/mesh3/runs/trap_tt92_d3"
integ = mesh3.integ
g = lambda t: t + LAG

# the two-slope profile: DERIVED from current_drive.json banks 2-6 shape
# (first six twelfths mean 0.86 mA, last six 2.29 mA; total = 1.575 mA x 92 ps)
I2S = (0.86, 2.29)


# ------------------------------------------------------------ PWL helpers
def pwl_from_segments(segs, tend, on_wins_at_zero=None):
    """segs: list of (t_start, value) sorted, value held until the next start;
    edges [t_b, t_b+EDGE].  Points with t<0 fold into the t=0 value.  If
    on_wins_at_zero is set, the t=0 value is max(pre, post) (a clamp control
    that is ON on either side of t=0 stays ON for the DC operating point)."""
    segs = sorted(segs)
    pre = [v for t, v in segs if t < -1e-9]
    pre = pre[-1] if pre else segs[-1][1]      # periodic: value held before the first seg
    post = [v for t, v in segs if abs(t) <= 1e-9]
    if post:
        post = post[-1]
        v0 = max(pre, post) if on_wins_at_zero else pre
        pts = [(0.0, v0)]
        if abs(post - v0) > 1e-15:
            pts.append((EDGE, post))
        cur = post
    else:
        pts, cur = [(0.0, pre)], pre
    for t, v in segs:
        if t <= 1e-9 or t > tend + T:
            continue
        if abs(v - cur) < 1e-15:
            continue
        pts += [(t, cur), (t + EDGE, v)]
        cur = v
    return "PWL(" + " ".join("%gp %g" % (t, v) if t > 0 else "0 %g" % v
                             for t, v in pts) + ")"


def current_segments(p, Ir, If, tend, two_slope=False):
    segs = []
    for m in range(-2, int(tend / T) + 3):
        a = m * T + p * TT
        if two_slope:
            segs += [(a, I2S[0] * 1e-3), (a + TT / 2, I2S[1] * 1e-3)]
        else:
            segs.append((a, Ir * 1e-3))
        segs += [(a + TT, 0.0), (a + 2 * TT, -If * 1e-3)]
    return segs


def window_segments(p, tend, on_from, on_to):
    """control = 1 on [a+on_from, a+on_to] of every slot, else 0."""
    segs = []
    for m in range(-2, int(tend / T) + 3):
        a = m * T + p * TT
        segs += [(a + on_from, 1.0), (a + on_to, 0.0)]
    return sorted(segs)


# ---------------------------------------------------------------- the deck
def bank_lines(k, mode, Ir, If, tend, two_slope):
    p = mesh3.phase_of(k)
    L = []
    if mode == "F":
        L.append("IR%d 0 ir%d %s" % (k, k, pwl_from_segments(
            sorted(current_segments(p, Ir, If, tend, two_slope)), tend)))
        L.append("VCT%d ct%d 0 %s" % (k, k, pwl_from_segments(
            window_segments(p, tend, TT, 2 * TT), tend, on_wins_at_zero=True)))
        L.append("VCB%d cb%d 0 %s" % (k, k, pwl_from_segments(
            window_segments(p, tend, 3 * TT - FLOOR_PRE, 3 * TT), tend,
            on_wins_at_zero=True)))
    elif LVAR in ("1", "2"):
        # diagnostics: v1 = B-source current + FIXED PWL controls, no latches;
        # v2 = same, plus the latch nodes as pure observers (lt/lb)
        L.append("VWR%d wr%d 0 %s" % (k, k, pwl_from_segments(
            window_segments(p, tend, WOFF, 2 * TT + WOFF), tend, on_wins_at_zero=True)))
        L.append("VCT%d ct%d 0 %s" % (k, k, pwl_from_segments(
            window_segments(p, tend, TT, 2 * TT), tend, on_wins_at_zero=True)))
        L.append("VCB%d cb%d 0 %s" % (k, k, pwl_from_segments(
            window_segments(p, tend, 3 * TT - FLOOR_PRE, 3 * TT), tend,
            on_wins_at_zero=True)))
        L.append("BIR%d 0 ir%d I={ V(wr%d)*%g*(1-V(ct%d)) - "
                 "(1-V(wr%d))*%g*(1-V(cb%d)) }" % (k, k, k, Ir * 1e-3, k, k, If * 1e-3, k))
        if LVAR == "2":
            L.append("CLT%d lt%d 0 1p" % (k, k))
            L.append("BLT%d 0 lt%d I={ V(wr%d)*%g*(1-V(lt%d))*0.5*(1+tanh((V(drv%d)-%g)/%g)) "
                     "- (1-V(wr%d))*%g*(V(lt%d)-1e-6) }" % (k, k, k, LSET, k, k, VTOP, TANHW, k, LRST, k))
            L.append("CLB%d lb%d 0 1p" % (k, k))
            L.append("BLB%d 0 lb%d I={ (1-V(wr%d))*%g*(1-V(lb%d))*0.5*(1-tanh((V(drv%d)-%g)/%g)) "
                     "- V(wr%d)*%g*(V(lb%d)-1e-6) }" % (k, k, k, LSET, k, k, VBOT, TANHW, k, LRST, k))
            L.append(".ic V(lt%d)=%g V(lb%d)=%g" % (k, {0: 0.0, 1: 1.0, 2: 1.0}[p], k, {0: 1.0, 1: 0.0, 2: 0.0}[p]))
    else:
        # WOFF: LATCHED window knots offset off the third boundaries so no knot
        # coincides with a committed .measure breakpoint (boundary + 1 ps): both
        # LATCHED rows with knots AT 553.000 died there, MEASURED attempt 2
        L.append("VWR%d wr%d 0 %s" % (k, k, pwl_from_segments(
            window_segments(p, tend, WOFF, 2 * TT + WOFF), tend, on_wins_at_zero=True)))
        # wr is a smooth 0..1 multiplier (a comparator IF() on wr stepped the
        # source current and killed the step control at t=0.5 ps, MEASURED)
        L.append("BIR%d 0 ir%d I={ V(wr%d)*%g*(1-V(ct%d)) - "
                 "(1-V(wr%d))*%g*(1-V(cb%d)) }" % (k, k, k, Ir * 1e-3, k, k, If * 1e-3, k))
        L.append("CCT%d ct%d 0 1p" % (k, k))
        # smooth comparator bands (a hard IF() on V(drv) chattered inside the
        # Newton loop at the 1.649 V crossing and killed the run, MEASURED):
        # set-rate = 3.3*(1-ct)*0.5*(1+tanh((V-Vc)/2.5mV)), band ~10 mV
        L.append("BCT%d 0 ct%d I={ V(wr%d)*%g*(1-V(ct%d))*0.5*(1+tanh((V(drv%d)-%g)/%g)) "
                 "- (1-V(wr%d))*%g*(V(ct%d)-1e-6) }" % (k, k, k, LSET, k, k, VTOP, TANHW, k, LRST, k))
        L.append("CCB%d cb%d 0 1p" % (k, k))
        L.append("BCB%d 0 cb%d I={ (1-V(wr%d))*%g*(1-V(cb%d))*0.5*(1-tanh((V(drv%d)-%g)/%g)) "
                 "- V(wr%d)*%g*(V(cb%d)-1e-6) }" % (k, k, k, LSET, k, k, VBOT, TANHW, k, LRST, k))
        # the latch resets settle at +1e-6 (1 uS clamp/floor leak, ~0.15 fC per
        # third) instead of decaying to zero: an exp(-5t/ps) reset underflows to
        # denormals ~140 ps after release, and both under-driven LATCHED rows
        # died at the first knot after that point (553.000 ps) with or without
        # .measure breakpoints, MEASURED attempt 2
        ic = {0: (0.0, 0.0, 1.0), 1: (DV, 1.0, 0.0), 2: (DV, 1.0, 0.0)}[p]
        L.append(".ic V(drv%d)=%g V(ct%d)=%g V(cb%d)=%g" % (k, ic[0], k, ic[1],
                                                           k, ic[2]))
    # clamps as LINEAR conductances G*s(t)*dV (B-sources; a VSWITCH's 12-decade
    # log-resistance sweep broke Newton at every yank and at the 553 ps
    # measure breakpoint); the floor diode is a smooth min(V,0) conductance
    L += ["VAIR%d ir%d drv%d 0" % (k, k, k),
          "VPH%d phs%d drv%d 0" % (k, k, k),          # committed ammeter name/sign
          "VH%d vh%d 0 DC %g" % (k, k, DV),
          "BSH%d vh%d drv%d I={ %g*V(ct%d)*(V(vh%d)-V(drv%d)) }" % (k, k, k, GC, k, k, k),
          "VF%d fl%d 0 DC 0" % (k, k),
          "BSF%d drv%d fl%d I={ %g*V(cb%d)*V(drv%d) }" % (k, k, k, 0.0 if NOFLOOR else GC, k, k),
          "BSD%d drv%d fl%d I={ %g*0.5*(V(drv%d)-sqrt(V(drv%d)*V(drv%d)+1e-10)) }"
          % (k, k, k, GD, k, k, k)]                       # body-diode role
    return L


MSCALE = 1e-3     # observer integrators scaled BELOW ABSTOL (1e-15): fC-scale
                  # 1 F integrators with kinked integrands at the control knots
                  # drove the LTE step control to dt->0 (MEASURED: nometer and
                  # ERROPTION=1 variants both pass, floor-only fails); scaled
                  # down they ride the circuit's own steps (Gear on <=0.25 ps)


def integ_s(tg, expr):
    return ["CX%s x%s 0 1" % (tg, tg),
            "BX%s 0 x%s I={ %g*(%s) }" % (tg, tg, MSCALE, expr),
            "RX%s x%s 0 0.01" % (tg, tg)]


def meter_lines(k):
    L = []
    L += integ_s("qsr%d" % k, "I(VAIR%d)" % k)
    L += integ_s("esr%d" % k, "V(drv%d)*I(VAIR%d)" % (k, k))
    L += integ_s("qcl%d" % k, "-I(VH%d)" % k)
    L += integ_s("ecl%d" % k, "-V(vh%d)*I(VH%d)" % (k, k))
    L += integ_s("qfl%d" % k, "I(VF%d)" % k)
    return L


def meter_measures(k):
    L = []
    for tg in ("qsr", "esr", "qcl", "ecl", "qfl"):
        TG = tg.upper()
        for n in (2, 3, 4, 5):
            ts = mesh3.slot(k, n, T, TT)
            L.append(".measure tran %s%dT%d FIND V(x%s%d) AT=%.6fp"
                     % (TG, k, n, tg, k, g(ts)))
            if n < 5:
                L.append(".measure tran %s%dR%d FIND V(x%s%d) AT=%.6fp"
                         % (TG, k, n, tg, k, g(ts + TT)))
                L.append(".measure tran %s%dH%d FIND V(x%s%d) AT=%.6fp"
                         % (TG, k, n, tg, k, g(ts + 2 * TT)))
    return L


def deck(mode, Ir, If, pat="P0", two_slope=False):
    lines, S = mesh3.deck("trap", TT, D, pat)
    tend = S["tend"]
    out = ["* qal/ldrive %s Ir=%g If=%g two_slope=%s pat=%s -- committed "
           "trap_tt92_d3 deck with the VPH trapezoids replaced by ideal "
           "current-source drives (see ldrive.py)" % (mode, Ir, If, two_slope, pat)]
    done_models = False
    for ln in lines:
        if ln.startswith("VPH") and " PWL(" in ln:
            k = int(ln.split()[0][3:])
            out += bank_lines(k, mode, Ir, If, tend, two_slope)
            continue
        if ln.startswith(".tran"):
            if ERROPT:
                out.append(".OPTIONS TIMEINT ERROPTION=1")
            if TEND_OVERRIDE:                      # test-only, never a scored row
                ln = ".tran 0.1p %sp 0 0.25p" % TEND_OVERRIDE
            out.append(ln)
            continue
        if NOMEAS and ln.startswith(".measure"):
            continue
        if ln.startswith(".print tran"):
            # committed columns untouched; the drive split is APPENDED and
            # integrated on the extraction grid (B-source observer integrators
            # either broke the LTE step control at scale 1 or were swamped by
            # ABSTOL when scaled down -- both MEASURED in attempt 1)
            extra = (["I(VAIR%d)" % k for k in range(1, NB + 1)] +
                     ["I(VH%d)" % k for k in range(1, NB + 1)] +
                     ["I(VF%d)" % k for k in range(1, NB + 1)])
            out.append(ln + " " + " ".join(extra))
            continue
        out.append(ln)
    S.update(mode=mode, Ir=Ir, If=If, two_slope=two_slope,
             step_control=("ERROPTION=1 (LTE off; Newton-count control, maxstep 0.25 ps)"
                           if ERROPT else "committed (GEAR + LTE)"))
    return out, S


def tag_of(mode, Ir, If, pat="P0", two_slope=False):
    t = ("F2S_if%g" % If) if two_slope else "%s_ir%g_if%g" % (mode, Ir, If)
    if pat != "P0":
        t += "_" + pat
    if ERROPT:
        t += "_E1"      # scored with .OPTIONS TIMEINT ERROPTION=1 (LTE step control OFF)
    return t


# -------------------------------------------------------------- post-process
def arrival(rundir, S, C, n):
    """per bank per wave: top arrival (0.99 DV) vs tt, pre-boundary rail,
    rise peak, floor arrival (0.01 DV) vs 3tt, pre-floor residual, fall min."""
    G = mesh3.GRID
    res = {}
    for k in range(1, NB + 1):
        rail = C["V(PH%d)" % k]
        rows = []
        for nn in (2, 3, 4):
            ts = mesh3.slot(k, nn, T, TT)
            a0, a1 = int(ts / G), min(n - 1, int((ts + 2 * TT) / G))
            t_top = None
            for a in range(a0, a1 + 1):
                if rail[a] >= 0.99 * DV:
                    t_top = a * G
                    break
            f0, f1 = int((ts + 2 * TT) / G), min(n - 1, int((ts + 3 * TT) / G))
            t_fl = None
            for a in range(f0, f1 + 1):
                if rail[a] <= 0.01 * DV:
                    t_fl = a * G
                    break
            r = dict(
                wave=nn,
                t_top_arrival_minus_tt_ps=(round(t_top - ts - TT, 2)
                                           if t_top is not None else None),
                V_rail_at_tt_minus_0p3_V=round(rail[int((ts + TT - 0.3) / G)], 4),
                V_rail_peak_rise_V=round(max(rail[a0:int((ts + TT + 3) / G)]), 4),
                V_rail_at_2tt_minus_0p3_V=round(rail[int((ts + 2 * TT - 0.3) / G)], 4),
                t_floor_arrival_minus_3tt_ps=(round(t_fl - ts - 3 * TT, 2)
                                              if t_fl is not None else None),
                V_rail_at_3tt_minus_2p3_V=round(rail[min(n - 1, int((ts + 3 * TT - 2.3) / G))], 4),
                V_rail_min_fall_V=round(min(rail[f0:min(n - 1, int((ts + 3 * TT + 3) / G))]), 4))
            rows.append(r)
        res[k] = rows
    return res


def gint(y, a0, a1, w=None):
    """trapezoid on the extraction grid over [a0, a1] (indices), optional weight"""
    G = mesh3.GRID * 1e-12
    tot = 0.0
    for a in range(a0, a1):
        f0 = y[a] * (w[a] if w is not None else 1.0)
        f1 = y[a + 1] * (w[a + 1] if w is not None else 1.0)
        tot += 0.5 * (f0 + f1)
    return tot * G


def books(mt0, C, n):
    """per bank per third (means over waves 2-4): Q,E from the current source
    (I(VAIR)), the 1.65 V clamp rail (I(VH)), the floor (I(VF)); the same grid
    integration of the committed -I(VPH) over the committed .measure windows
    (boundary + LAG) is cross-checked against the exact QPH .mt0 reads."""
    G = mesh3.GRID
    out = {}
    for k in range(1, NB + 1):
        rail, isr, ih, ifl, iph = (C["V(PH%d)" % k], C["I(VAIR%d)" % k],
                                   C["I(VH%d)" % k], C["I(VF%d)" % k], C["I(VPH%d)" % k])
        acc = {tg: {"rise": [], "hold": [], "fall": []}
               for tg in ("QSR", "ESR", "QCL", "ECL", "QFL", "EFL", "QTOT")}
        xq, xe = [], []
        for nn in (2, 3, 4):
            ts = mesh3.slot(k, nn, T, TT)
            for th, (t0, t1) in (("rise", (ts, ts + TT)), ("hold", (ts + TT, ts + 2 * TT)),
                                 ("fall", (ts + 2 * TT, ts + 3 * TT))):
                a0, a1 = int(round(t0 / G)), min(n - 1, int(round(t1 / G)))
                acc["QSR"][th].append(gint(isr, a0, a1) * 1e15)
                acc["ESR"][th].append(gint(isr, a0, a1, rail) * 1e15)
                acc["QCL"][th].append(-gint(ih, a0, a1) * 1e15)
                acc["ECL"][th].append(-gint(ih, a0, a1) * DV * 1e15)
                acc["QFL"][th].append(gint(ifl, a0, a1) * 1e15)
                acc["EFL"][th].append(gint(ifl, a0, a1, rail) * 1e15)
                acc["QTOT"][th].append(-gint(iph, a0, a1) * 1e15)
                # cross-check: committed .measure window is [t0+LAG, t1+LAG]
                b0, b1 = int(round((t0 + LAG) / G)), min(n - 1, int(round((t1 + LAG) / G)))
                key = {"rise": ("T", "R"), "hold": ("R", "H"), "fall": ("H", None)}[th]
                m0 = mt0.get("QPH%d%s%d" % (k, key[0], nn))
                m1 = (mt0.get("QPH%d%s%d" % (k, key[1], nn)) if key[1]
                      else mt0.get("QPH%dT%d" % (k, nn + 1)))
                e0 = mt0.get("EPH%d%s%d" % (k, key[0], nn))
                e1 = (mt0.get("EPH%d%s%d" % (k, key[1], nn)) if key[1]
                      else mt0.get("EPH%dT%d" % (k, nn + 1)))
                if None not in (m0, m1):
                    xq.append((-gint(iph, b0, b1) * 1e15, (m1 - m0) * 1e15))
                if None not in (e0, e1):
                    xe.append((-gint(iph, b0, b1, rail) * 1e15, (e1 - e0) * 1e15))
        b = {}
        for tg, unit in (("QSR", "fC"), ("ESR", "fJ"), ("QCL", "fC"), ("ECL", "fJ"),
                         ("QFL", "fC"), ("EFL", "fJ"), ("QTOT", "fC")):
            b[tg] = {th: round(sum(v) / len(v), 3) for th, v in acc[tg].items()}
            b[tg]["cycle"] = round(sum(b[tg][th] for th in ("rise", "hold", "fall")), 3)
            b[tg]["unit"] = unit
        cq, ce = [], []
        for nn in (2, 3, 4):
            qt, qr, qh, qt2 = (mt0.get("QPH%dT%d" % (k, nn)), mt0.get("QPH%dR%d" % (k, nn)),
                               mt0.get("QPH%dH%d" % (k, nn)), mt0.get("QPH%dT%d" % (k, nn + 1)))
            et, er, eh, et2 = (mt0.get("EPH%dT%d" % (k, nn)), mt0.get("EPH%dR%d" % (k, nn)),
                               mt0.get("EPH%dH%d" % (k, nn)), mt0.get("EPH%dT%d" % (k, nn + 1)))
            if None not in (qt, qr, qh, qt2):
                cq += [(qr - qt) * 1e15, (qh - qr) * 1e15, (qt2 - qh) * 1e15]
            if None not in (et, er, eh, et2):
                ce += [(er - et) * 1e15, (eh - er) * 1e15, (et2 - eh) * 1e15]
        mq = [sum(cq[i::3]) / 3 for i in range(3)] if cq else None
        me = [sum(ce[i::3]) / 3 for i in range(3)] if ce else None
        gq = [b["QTOT"][th] for th in ("rise", "hold", "fall")]
        ge = [sum(acc[tg][th]) / 3 for th in ("rise", "hold", "fall")
              for tg in ("ESR",)]  # placeholder replaced below
        ge = [(sum(acc["ESR"][th]) + sum(acc["ECL"][th]) + sum(acc["EFL"][th])) / 3
              for th in ("rise", "hold", "fall")]
        b["xcheck_grid_vs_measure"] = dict(
            note="grid-integrated thirds (exact boundaries) vs committed .measure thirds "
                 "(boundary+1 ps reads): |diff| <= I*1ps shift; Q_tot and E_tot per third",
            Q_max_abs_err_fC=(round(max(abs(a - m) for a, m in zip(gq, mq)), 3) if mq else None),
            E_max_abs_err_fJ=(round(max(abs(a - m) for a, m in zip(ge, me)), 3) if me else None))
        out[k] = b
    return out


def run_row(mode, Ir, If, pat="P0", two_slope=False, force=False):
    tag = tag_of(mode, Ir, If, pat, two_slope)
    repo = os.path.join(HERE, "runs", tag)
    if os.path.exists(os.path.join(repo, "OUT.json")) and not force:
        print("  cached", tag)
        return json.load(open(os.path.join(repo, "OUT.json")))
    rundir = os.path.join(RUNS, tag)
    lines, S = deck(mode, Ir, If, pat, two_slope)
    p, msg = mesh3.run_xyce(rundir, "c_%s.cir" % tag, lines, timeout=5400)
    print("  %s %s" % (tag, msg), flush=True)
    os.makedirs(repo, exist_ok=True)
    if p is None:
        json.dump(dict(S, error=msg), open(os.path.join(repo, "OUT.json"), "w"),
                  indent=1)
        for f in os.listdir(rundir):
            if f.endswith(".cir"):
                shutil.copy2(os.path.join(rundir, f), repo)
        return dict(S, error=msg, acceptance=dict(PASS=False))
    o = mesh3.extract(rundir, S, keep_prn=True)
    prn = p + ".prn"
    n, C = mesh3.load_grid(prn, S["tend"])
    mt0 = mesh3.parse_mt0(p + ".mt0")
    o["ldrive"] = dict(arrival=arrival(rundir, S, C, n), books=books(mt0, C, n),
                       labels="arrival/books MEASURED on IDEAL sources = BOUND")
    json.dump(o, open(os.path.join(rundir, "OUT.json"), "w"), indent=1)
    os.remove(prn)                                   # NEVER into git
    for f in os.listdir(rundir):
        if f.endswith((".cir", ".mt0")) or f == "OUT.json":
            shutil.copy2(os.path.join(rundir, f), repo)
    a = o["acceptance"]
    e3 = o["erosion"][3]
    print("  %s value=%s eye=%s handoff=%s worst_margin=%s worst_ov=%s "
          "erosion=%s widths=%s -> %s"
          % (tag, a["A_value"], a["B_eye"], a["C_handoff"],
             a["worst_margin_at_commit_mV"], a["worst_overlap_ps"],
             e3["sign"], e3["width_0mV_ps_links"],
             "PASS" if a["PASS"] else "FAIL"), flush=True)
    return o


# ------------------------------------------------------------------- rows
ROWS = []
for Ir in (1.3, 1.57, 1.9):
    for If in (1.3, 1.6, 2.0):
        ROWS.append(("F", Ir, If, "P0", False))
for Ir, If in ((1.3, 1.3), (1.57, 1.6), (1.9, 2.0)):
    ROWS.append(("L", Ir, If, "P0", False))
ROWS.append(("F", 1.575, 1.6, "P0", True))


def parse_tag(tag):
    for r in ROWS + [("F", 1.57, 1.6, "P1", False)]:
        if tag_of(r[0], r[1], r[2], r[3], r[4]) in (tag, tag + "_E1"):
            return r
    raise SystemExit("unknown tag " + tag)


# ------------------------------------------------------------------- agg
BASE = dict(worst_margin_mV=509.67, worst_overlap_ps=37.021, standing_eye_ps=129.03,
            open_minus_srx_ps=[18.561, 24.79, 24.71, 25.047, 25.04, 23.274],
            widths_ps=[135.546, 129.259, 129.358, 129.022, 129.029, 123.666],
            overlaps_ps=[37.318, 37.338, 37.021, 37.029, 38.795],
            E_ledger_bank4_fJ=240.292)


def sk(d, k):
    return d[k] if k in d else d[str(k)]


def mean(v):
    v = [x for x in v if x is not None]
    return round(sum(v) / len(v), 3) if v else None


def summarize(o):
    a = o["acceptance"]
    e3 = sk(o["erosion"], 3)
    links = o["links"]
    row = dict(tag=o.get("tag"), mode=o["mode"], I_r_mA=o["Ir"], I_f_mA=o["If"],
               two_slope=o.get("two_slope", False), pat=o["pat"],
               clamp=("fixed third boundary" if o["mode"] == "F"
                      else "latched on arrival (1.644 V band)"),
               step_control=o.get("step_control", "committed (GEAR + LTE)"),
               value_PASS=a["A_value"], value_n_fail=o["value"]["n_fail"],
               B_eye=a["B_eye"], C_handoff=a["C_handoff"], PASS=a["PASS"],
               worst_margin_at_commit_mV=a["worst_margin_at_commit_mV"],
               worst_overlap_ps=a["worst_overlap_ps"],
               standing_eye_ps=e3["asymptotic_width_ps"], erosion_sign=e3["sign"],
               widths_ps=e3["width_0mV_ps_links"], overlaps_ps=e3["overlaps_ps"],
               open_minus_srx_ps=[sk(sk(links, k), 3).get("0mV", {}).get("open_minus_srx_ps")
                                  for k in range(1, NB + 1)],
               rising_lag_ps=o["rising_lag_ps"],
               hold_droop_mV_max=max(v["droop_from_dV_mV"] for v in o["hold_rail"].values()),
               hold_bump_worst_LOW_rise_mV=o["hold_bump"]["worst_LOW_rise_mV"])
    row["d_open_vs_base_ps_links2to5"] = [
        round(row["open_minus_srx_ps"][k] - BASE["open_minus_srx_ps"][k], 3)
        if row["open_minus_srx_ps"][k] is not None else None for k in range(1, 5)]
    row["d_standing_eye_vs_129p03_ps"] = (round(row["standing_eye_ps"] - BASE["standing_eye_ps"], 3)
                                         if row["standing_eye_ps"] is not None else None)
    ld = o.get("ldrive", {})
    arr = ld.get("arrival", {})
    keys = ["t_top_arrival_minus_tt_ps", "V_rail_at_tt_minus_0p3_V", "V_rail_peak_rise_V",
            "V_rail_at_2tt_minus_0p3_V", "t_floor_arrival_minus_3tt_ps",
            "V_rail_at_3tt_minus_2p3_V", "V_rail_min_fall_V"]
    arr26 = {}
    for key in keys:
        vals = [r[key] for k in range(2, NB + 1) for r in sk(arr, k)]
        nn = [v for v in vals if v is not None]
        arr26[key] = dict(mean=mean(nn), min=(round(min(nn), 3) if nn else None),
                          max=(round(max(nn), 3) if nn else None),
                          n_missing=len(vals) - len(nn))
    row["arrival_banks2to6"] = arr26
    row["arrival_per_bank_wave3"] = {k: sk(arr, k)[1] for k in range(1, NB + 1)} if arr else None
    bk = ld.get("books", {})
    cs = o["charge_spec_reported_not_gated"]
    b26 = {}
    for tg in ("QSR", "ESR", "QCL", "ECL", "QFL", "EFL", "QTOT"):
        b26[tg] = {th: mean([sk(bk, k)[tg][th] for k in range(2, NB + 1) if tg in sk(bk, k)])
                   for th in ("rise", "hold", "fall", "cycle")}
    row["books_banks2to6_mean"] = b26
    # sound cross-check (from fields in OUT.json): grid-integrated thirds at the exact
    # boundaries vs the committed .measure thirds (boundary + 1 ps reads); the 1 ps
    # read shift alone allows |I|*1 ps ~ 1.5-3 fC / 2-5 fJ of difference
    xq, xe = [], []
    for k in range(1, NB + 1):
        bb, cc = sk(bk, k), sk(cs, k)
        for th, qf, ef in (("rise", "Q_rise_fC", "E_rise_fJ"), ("hold", "Q_hold_fC", "E_hold_fJ"),
                           ("fall", "Q_fall_fC", "E_fall_fJ")):
            xq.append(abs(bb["QTOT"][th] - cc[qf]))
            xe.append(abs(bb["ESR"][th] + bb["ECL"][th] + bb["EFL"][th] - cc[ef]))
    row["books_xcheck_grid_vs_committed_measure_worst"] = dict(
        Q_fC=round(max(xq), 3), E_fJ=round(max(xe), 3), n=len(xq),
        note="grid thirds (exact boundaries) vs committed .measure thirds (boundary+1ps); "
             "the read shift alone allows ~|I|*1ps") if bk else None
    row["books_per_bank"] = bk
    row["committed_meter_QPH_EPH_banks2to6_mean"] = {
        f: mean([sk(cs, k)[f] for k in range(2, NB + 1)])
        for f in ("Q_rise_fC", "Q_hold_fC", "Q_fall_fC", "E_rise_fJ", "E_hold_fJ", "E_fall_fJ")}
    esr, ecl = b26["ESR"], b26["ECL"]
    if esr["cycle"] is not None and ecl["cycle"] is not None:
        drawn = (esr["rise"] or 0) + max(esr["hold"] or 0, 0) + (ecl["cycle"] or 0)
        row["energy_BOUND_banks2to6_fJ_per_cycle"] = dict(
            E_source_rise=esr["rise"], E_source_hold=esr["hold"], E_source_fall=esr["fall"],
            E_clamp_rail=ecl["cycle"],
            E_drawn_source_plus_clamp=round(drawn, 3),
            E_returned_to_source_in_fall=round(-(esr["fall"] or 0), 3),
            E_net=round(drawn + (esr["fall"] or 0) + min(esr["hold"] or 0, 0), 3),
            committed_ledger_bank4=BASE["E_ledger_bank4_fJ"],
            label="IDEAL sources: BOUND, energy REPORTED never gated")
    return row


def cmd_agg():
    rows = []
    rd = os.path.join(HERE, "runs")
    for tag in sorted(os.listdir(rd)):
        oj = os.path.join(rd, tag, "OUT.json")
        if not os.path.exists(oj):
            continue
        o = json.load(open(oj))
        o["tag"] = tag
        if "error" in o:
            rows.append(dict(tag=tag, mode=o.get("mode"), I_r_mA=o.get("Ir"),
                             I_f_mA=o.get("If"), error=o["error"], PASS=False))
            continue
        rows.append(summarize(o))
    rows.sort(key=lambda r: (r.get("pat", "P0"), r.get("mode", ""), r.get("two_slope", False),
                             r.get("I_r_mA") or 0, r.get("I_f_mA") or 0))
    F = [r for r in rows if r.get("mode") == "F" and not r.get("two_slope")
         and r.get("pat") == "P0" and "error" not in r]
    L = [r for r in rows if r.get("mode") == "L" and "error" not in r]
    passF = sorted({(r["I_r_mA"], r["I_f_mA"]) for r in F if r["PASS"]})
    failF = sorted({(r["I_r_mA"], r["I_f_mA"]) for r in F if not r["PASS"]})
    center = [r for r in F if r["I_r_mA"] == 1.57 and r["I_f_mA"] == 1.6]
    center = center[0] if center else None
    verdict = dict(
        FIXED_pass=passF, FIXED_fail=failF,
        LATCHED={r["tag"]: dict(
            PASS=r["PASS"], step_control=r["step_control"], arrival_err_ps=r["arrival_banks2to6"]["t_top_arrival_minus_tt_ps"],
            floor_err_ps=r["arrival_banks2to6"]["t_floor_arrival_minus_3tt_ps"],
            worst_overlap_ps=r["worst_overlap_ps"], worst_margin_mV=r["worst_margin_at_commit_mV"])
            for r in L},
        tolerance_band_FIXED=("I_r in [%g,%g] x I_f in [%g,%g] mA all PASS" % (
            min(p[0] for p in passF), max(p[0] for p in passF),
            min(p[1] for p in passF), max(p[1] for p in passF)) if passF and not failF
            else "see FIXED_pass/FIXED_fail"))
    if center:
        verdict["shape_question_center_FIXED_row"] = dict(
            d_open_vs_base_ps_links2to5=center["d_open_vs_base_ps_links2to5"],
            standing_eye_ps=center["standing_eye_ps"],
            d_standing_eye_ps=center["d_standing_eye_vs_129p03_ps"],
            worst_margin_mV=center["worst_margin_at_commit_mV"],
            worst_overlap_ps=center["worst_overlap_ps"],
            establishment_delayed=(any(x > 3.0 for x in center["d_open_vs_base_ps_links2to5"]
                                       if x is not None)))
    R = dict(campaign="qal/ldrive STEP 1 -- current-source drive shapes (IDEAL = BOUND)",
             baseline=BASE, n_rows=len(rows), rows=rows, verdict=verdict,
             labels=dict(MEASURED="acceptance, eyes, margins, overlaps, arrival times, Q/E books",
                         DERIVED="d_* deltas vs the committed baseline, energy sums",
                         ASSUMED="VSWITCH RON 1 mOhm (= committed RS), 0.5 ps edges, latch tau 0.2 ps, 0.99/0.01 DV arrival thresholds",
                         BOUND="every number: ideal current sources + ideal 1.65 V clamp rail"))
    json.dump(R, open(os.path.join(HERE, "RESULTS.json"), "w"), indent=1)
    for r in rows:
        if "error" in r:
            print("%-22s ERROR %s" % (r["tag"], r["error"][:80]))
            continue
        ar = r["arrival_banks2to6"]
        print("%-22s %s m=%7.2f ov=%6.2f eye=%7.2f dOpen=%s top_err=%s Vtt=%s pk=%s fl_err=%s Vfl=%s"
              % (r["tag"], "PASS" if r["PASS"] else "FAIL", r["worst_margin_at_commit_mV"],
                 r["worst_overlap_ps"], r["standing_eye_ps"] or -1,
                 r["d_open_vs_base_ps_links2to5"],
                 ar["t_top_arrival_minus_tt_ps"]["mean"], ar["V_rail_at_tt_minus_0p3_V"]["mean"],
                 ar["V_rail_peak_rise_V"]["max"], ar["t_floor_arrival_minus_3tt_ps"]["mean"],
                 ar["V_rail_at_3tt_minus_2p3_V"]["mean"]))
    print(json.dumps(verdict, indent=1))
    return 0



def cmd_table():
    """markdown sweep table for README.md from RESULTS.json"""
    R = json.load(open(os.path.join(HERE, "RESULTS.json")))
    hdr = ("| row | I_r | I_f | clamp | step ctl | value | worst margin mV | worst overlap ps | "
           "standing eye ps (d vs 129.03) | d_open links 2-5 ps | V(rail) at tt-0.3 ps | top arrival err ps | "
           "V(rail) at 3tt-2.3 | floor arrival err ps | E_src rise / E_clamp / E_src fall fJ | E_net fJ | PASS |")
    print(hdr)
    print("|" + "---|" * (hdr.count("|") - 1))
    for r in R["rows"]:
        if "error" in r:
            print("| %s | %s | %s | | | | | | | | | | | | | | XYCE FAIL |" % (r["tag"], r["I_r_mA"], r["I_f_mA"]))
            continue
        ar = r["arrival_banks2to6"]
        eb = r.get("energy_BOUND_banks2to6_fJ_per_cycle", {})
        top = ar["t_top_arrival_minus_tt_ps"]
        fl = ar["t_floor_arrival_minus_3tt_ps"]
        f = lambda d: ("%s [%s,%s]%s" % (d["mean"], d["min"], d["max"],
                                        (" miss %d/15" % d["n_missing"]) if d["n_missing"] else ""))
        print("| %s | %s | %s | %s | %s | %s | %s | %s | %s (%+.2f) | %s | %s | %s | %s | %s | %s / %s / %s | %s | %s |" % (
            r["tag"], r["I_r_mA"] if not r["two_slope"] else "0.86->2.29", r["I_f_mA"],
            "fixed" if r["mode"] == "F" else "latched",
            "LTE" if r["step_control"].startswith("committed") else "ERROPTION=1",
            "%d/144 fail" % r["value_n_fail"] if r["value_n_fail"] else "OK",
            r["worst_margin_at_commit_mV"], r["worst_overlap_ps"],
            r["standing_eye_ps"], r["d_standing_eye_vs_129p03_ps"] or 0,
            r["d_open_vs_base_ps_links2to5"],
            f(ar["V_rail_at_tt_minus_0p3_V"]), f(top), f(ar["V_rail_at_3tt_minus_2p3_V"]), f(fl),
            eb.get("E_source_rise"), eb.get("E_clamp_rail"), eb.get("E_source_fall"), eb.get("E_net"),
            "PASS" if r["PASS"] else "FAIL"))
    return 0



def cmd_finalize():
    """RESULTS.json = agg + instrument check + E1 calibration + the pre-stated
    vs measured scorecard (numbers from the rows; verdict text fixed here)."""
    cmd_agg()
    R = json.load(open(os.path.join(HERE, "RESULTS.json")))
    rows = {r["tag"]: r for r in R["rows"]}
    R["instrument_check"] = json.load(open(os.path.join(HERE, "IC.json")))
    a, b = rows["L_ir1.9_if2"], rows["L_ir1.9_if2_E1"]
    R["step_control_calibration_LTE_vs_ERROPTION1"] = dict(
        row="L 1.9/2.0 run both ways",
        worst_margin_mV=[a["worst_margin_at_commit_mV"], b["worst_margin_at_commit_mV"]],
        worst_overlap_ps=[a["worst_overlap_ps"], b["worst_overlap_ps"]],
        standing_eye_ps=[a["standing_eye_ps"], b["standing_eye_ps"]],
        top_arrival_err_ps=[a["arrival_banks2to6"]["t_top_arrival_minus_tt_ps"]["mean"],
                            b["arrival_banks2to6"]["t_top_arrival_minus_tt_ps"]["mean"]],
        E_net_fJ=[a["energy_BOUND_banks2to6_fJ_per_cycle"]["E_net"],
                  b["energy_BOUND_banks2to6_fJ_per_cycle"]["E_net"]],
        why="the under-driven LATCHED rows (1.3/1.3, 1.57/1.6) die under the committed "
            "GEAR+LTE step control at t=553.000 ps (the wave-2 input-word knot) once the "
            "latch state closes the loop onto the clamp conductance (observer latches and "
            "PWL-controlled clamps with the same B-source current both run clean; "
            "ERROPTION=1 runs clean); those two rows are scored with ERROPTION=1 and "
            "labelled; the calibration pair bounds the deviation at <1 mV / <0.1 ps")
    c = rows["F_ir1.57_if1.6"]
    R["pre_stated_vs_measured"] = {
        "shape_question (does constant-current rise delay establishment?)": dict(
            pre_stated="NO; establishment 5-15 ps EARLIER on links 2-5",
            measured_d_open_links2to5_ps=c["d_open_vs_base_ps_links2to5"],
            verdict="FALSIFIED in direction: not earlier; within -0.5..+4.7 ps of the linear ramp "
                    "(two links beyond the 3 ps falsifier). Cause: the rail is only at %.3f V at the "
                    "boundary, the demand is trajectory-dependent" % c["arrival_banks2to6"]["V_rail_at_tt_minus_0p3_V"]["mean"]),
        "standing_eye_center_row": dict(pre_stated="WIDER than 129.03 by 15-30 ps",
                                        measured_ps=c["standing_eye_ps"], d_ps=c["d_standing_eye_vs_129p03_ps"],
                                        verdict="FALSIFIED (narrower by 2.4 ps; widening appears only at I_f=1.3 or I_r=1.9)"),
        "fixed_mode_boundary_mismatch": dict(
            pre_stated="dV at tt: -0.16 V at 1.3 mA, +0.19 V overshoot at 1.9 mA",
            measured_V_at_tt={t: rows[t]["arrival_banks2to6"]["V_rail_at_tt_minus_0p3_V"]["mean"]
                              for t in ("F_ir1.3_if1.6", "F_ir1.57_if1.6", "F_ir1.9_if1.6", "F2S_if1.6")},
            measured_peak_V_max=max(rows[t]["arrival_banks2to6"]["V_rail_peak_rise_V"]["max"]
                                    for t in rows if "error" not in rows[t]),
            verdict="FALSIFIED: constant current ALWAYS under-delivers in voltage (1.235/1.375/1.468 V "
                    "at 1.3/1.57/1.9 mA), no overshoot anywhere; the same 145 fC as a 0.86->2.29 mA "
                    "two-slope reaches 1.577 V. Shape, not just charge, sets the arrival."),
        "latched_arrival_error": dict(
            pre_stated="Q/I arithmetic: +19.5 ps at 1.3, -0.3 ps at 1.57, -15.7 ps at 1.9; all PASS",
            measured={t: dict(PASS=rows[t]["PASS"], err=rows[t]["arrival_banks2to6"]["t_top_arrival_minus_tt_ps"])
                      for t in ("L_ir1.3_if1.3_E1", "L_ir1.57_if1.6_E1", "L_ir1.9_if2")},
            verdict="FALSIFIED: 1.9 mA arrives +32.8 ps LATE (needs ~237 fC vs the ramp's 145), "
                    "1.57 mA arrives +66 ps late where it arrives at all (9/15 bank-waves never), "
                    "1.3 mA never; both under-driven latched rows FAIL value/eye/handoff"),
        "tolerance_band": dict(
            pre_stated="FIXED: all 9 PASS; LATCHED PASS at 1.57 and 1.9, 1.3 at risk",
            measured_FIXED_pass=R["verdict"]["FIXED_pass"], measured_FIXED_fail=R["verdict"]["FIXED_fail"],
            measured_LATCHED={t: rows[t]["PASS"] for t in ("L_ir1.3_if1.3_E1", "L_ir1.57_if1.6_E1", "L_ir1.9_if2")},
            verdict="FIXED confirmed (9/9 PASS) but erosion is steep below 1.57 mA (I_r=1.3: margin "
                    "136-286 mV, overlap 8-28 ps, ERODES_SLOW at I_f=2.0); LATCHED falsified below 1.9 mA"),
        "energy_BOUND": dict(
            pre_stated="center: source rise 125-150, clamp 190-210, fall recovery 100-130 fJ",
            measured_center=c["energy_BOUND_banks2to6_fJ_per_cycle"],
            verdict="source rise 138.1 and recovery 117.2 inside the bands; clamp 223.8 above "
                    "(it makes up the 0.275 V boundary deficit); E_net 245.8 vs the 240.3 ledger (+2.3%)")}
    json.dump(R, open(os.path.join(HERE, "RESULTS.json"), "w"), indent=1)
    print("finalized", len(R["rows"]), "rows")
    return 0


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "list":
        for r in ROWS:
            print(tag_of(*r))
    elif a[0] == "one":
        r = parse_tag(a[1])
        o = run_row(*r, force=("--force" in a))
        sys.exit(0 if o.get("acceptance", {}).get("PASS") else 3)
    elif a[0] == "agg":
        sys.exit(cmd_agg())
    elif a[0] == "table":
        sys.exit(cmd_table())
    elif a[0] == "finalize":
        sys.exit(cmd_finalize())
    elif a[0] == "deck":
        r = parse_tag(a[1])
        lines, S = deck(r[0], r[1], r[2], r[3], r[4])
        print("\n".join(lines))
    else:
        print(__doc__)
