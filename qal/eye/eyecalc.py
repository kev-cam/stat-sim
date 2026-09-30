#!/usr/bin/env python3
"""THE EYE.  Extracted from the DENSE WAVEFORM of one transient per pattern --
never by re-simulating per sampling instant.

Definitions are PRE_REGISTERED.json STEP_d, verbatim:

  link(k -> k+1, gate i): signal V(o{k}_{i}); receiver bank k+1; decision level
  Trip_S(V(rail{k+1})(t)) linearly interpolated on the 27 MEASURED points of
  qal/fcrit/TRIP.json cell S at the receiver's INSTANTANEOUS rail.

  mgn(k,i,t) = +1000*(V(o_k_i) - trip)  if bank k cell i's expected output is HIGH
             = -1000*(V(o_k_i) - trip)  if it is LOW                      [mV]

  bank k's eye is OPEN at t iff min over the 8 gates of mgn > threshold AND the
  receiver rail is IN the measured table domain [0.20, 1.50] V.

  the eye is the LARGEST CONTIGUOUS open interval in [c_k, ro_k]; the reported
  eye is the INTERSECTION over patterns of the open sets.

Bank 4 has no bank 5: its receiver rail is the DERIVED V(rail3)(t - T).  Labelled
DERIVED everywhere.  Banks 1-3 are MEASURED.
"""
import gzip, json, math, os, sys
from array import array
import eyeharness as EH

HERE = EH.HERE
GRID = 0.10                  # ps, PRE_REGISTERED TIME_RESOLUTION
SIG_TRIP_MV = 6.441          # MEASURED qal/vtaudit (LOWER bound, dw/dl excluded)
VTN, VTP = 0.5240, 0.4402    # MEASURED; Vtn is the BINDING threshold (qal/strip)
TRIP = EH.Trip()


# ------------------------------------------------------------------ prn -> grid
def load_grid(prn, tmax):
    """Read the .prn and resample every column onto the COMMON uniform 0.10 ps
    grid by linear interpolation.  A common grid is required because different
    patterns produce different solver points and the eye is their INTERSECTION.
    The solver's own ceiling is 0.10 ps, so no interpolation step ever spans
    more than one grid cell.

    Streamed and stored as array('d') -- the box is memory-pressured and six
    patterns x 48 columns x ~22500 points as Python floats would be ~1.2 GB."""
    hdr, t, raw = None, array("d"), None
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
    dtmax = max(t[i + 1] - t[i] for i in range(nt - 1))
    n = int(math.floor(tmax / GRID)) + 1
    g = array("d", (i * GRID for i in range(n)))
    # one shared index map: grid point -> left solver point
    idx = array("i", bytes(4 * n))
    j = 0
    for a in range(n):
        ta = g[a]
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
            ta = g[a]
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
    return g, cols, dict(n_solver_points=nt, solver_tmax_ps=t[nt - 1],
                         solver_dt_max_ps=dtmax)


# --------------------------------------------------------------- per pattern
def per_pattern(pname):
    sub = os.path.join(HERE, pname)
    S = json.load(open(os.path.join(sub, "sched.json")))
    T = float(S["T"])
    c = {int(k): float(v) for k, v in S["c"].items()}
    o = {int(k): float(v) for k, v in S["o"].items()}
    r = {int(k): float(v) for k, v in S["r"].items()}
    ro = {int(k): float(v) for k, v in S["ro"].items()}
    tend = float(S["tend"])
    g, C, meta = load_grid(S["prn"], tend)
    EH.set_pattern(EH.PATTERNS[pname])
    nb, mg = EH.bt.NBANK, EH.bt.MGATE

    # receiver rail per driving bank, on the same grid
    ng = len(g)
    shift = int(round(T / GRID))
    rx = {}
    for k in range(1, nb + 1):
        if k < nb:
            rx[k] = C["V(RAIL%d)" % (k + 1)]
        else:                                  # DERIVED: V(rail3)(t - T)
            src = C["V(RAIL%d)" % (nb - 1)]
            rx[k] = array("d", (src[max(0, a - shift)] for a in range(ng)))

    trip, intab = {}, {}
    for k in range(1, nb + 1):
        tv = array("d", bytes(8 * ng))
        it = bytearray(ng)
        rr = rx[k]
        for a in range(ng):
            v = rr[a]
            t_, ex = TRIP(v)
            tv[a] = t_
            it[a] = 0 if (ex or not (TRIP.lo <= v <= TRIP.hi)) else 1
        trip[k], intab[k] = tv, it

    mgn = {}                                    # mgn[k][i] over the grid, mV
    for k in range(1, nb + 1):
        mgn[k] = {}
        tk = trip[k]
        for i in range(mg):
            v = C["V(O%d_%d)" % (k, i)]
            sg = 1.0 if EH.bt.out_hi(k, i) else -1.0
            mgn[k][i] = array("d", (1000.0 * sg * (v[a] - tk[a]) for a in range(ng)))

    # ---- AMENDMENT E3: the DATA eye.  A FIXED decision level per link, so the
    # driver is isolated from when its receiver happens to be switched on.
    # Trip_S(VR{k+1}B) -- VR{k+1}B is the committed banktank .measure key
    # rail_at_own_boundary_V, MEASURED from THIS pattern's own .mt0.
    # Sensitivity to that choice is reported, not hidden: the same eye is also
    # taken at the min and the max of the receiver's live trip trajectory.
    d = EH.bt.parse_mt0(S["mt0"])
    tripfix, tripspan, mgnd = {}, {}, {}
    for k in range(1, nb + 1):
        kr = k + 1 if k < nb else nb           # bank nb: DERIVED, uses its own
        # bt.py's .measure keys are VR{bank}{checkpoint}; the receiver's rail at
        # ITS OWN boundary is VR{kr}B{kr} (this is the committed row field
        # rail_at_own_boundary_V[kr] -- digit-checked in INSTRUMENT_CHECK.json).
        vrb = d["VR%dB%d" % (kr, kr)]
        tf, _ = TRIP(vrb)
        live = [trip[k][a] for a in range(ng) if intab[k][a]]
        tripfix[k] = tf
        tripspan[k] = dict(rail_at_receiver_boundary_V=vrb,
                           trip_fixed_V=tf,
                           trip_min_over_live_window_V=(min(live) if live else None),
                           trip_max_over_live_window_V=(max(live) if live else None),
                           receiver_is_derived=(k == nb))
        mgnd[k] = {}
        for i in range(mg):
            v = C["V(O%d_%d)" % (k, i)]
            sg = 1.0 if EH.bt.out_hi(k, i) else -1.0
            mgnd[k][i] = array("d", (1000.0 * sg * (v[a] - tf) for a in range(ng)))

    return dict(pattern=pname, bits=EH.PATTERNS[pname], grid=g, C=C, meta=meta,
                T=T, c=c, o=o, r=r, ro=ro, tend=tend, rx=rx, trip=trip,
                intab=intab, mgn=mgn, mgn_data=mgnd, tripfix=tripfix,
                tripspan=tripspan, nb=nb, mg=mg,
                hi={k: {i: EH.bt.out_hi(k, i) for i in range(mg)}
                    for k in range(1, nb + 1)})


# ------------------------------------------------------------------ eye maths
def largest_run(mask, lo_idx, hi_idx, pick="largest"):
    """pick='largest' is the PRE-REGISTERED rule.  pick='first' returns the FIRST
    contiguous open interval in the window, which is the OPERATIONALLY relevant
    one: a receiver samples the first time the data is valid, not whichever
    later interval happens to be longest.  Both are reported."""
    best = None
    a = lo_idx
    while a <= hi_idx:
        if mask[a]:
            b = a
            while b + 1 <= hi_idx and mask[b + 1]:
                b += 1
            if pick == "first":
                return (a, b)
            if best is None or (b - a) > (best[1] - best[0]):
                best = (a, b)
            a = b + 1
        else:
            a += 1
    return best


def eye_from_mask(mask, g, lo, hi, curve=None, thresh=0.0, pick="largest"):
    """AMENDMENT E1: the edge is the ROOT of margin(t) = thresh, located by LINEAR
    INTERPOLATION between the two grid points that bracket it -- NOT by grid
    quantisation.  The margin slope at an edge is of order 5 mV/ps, so on a
    0.10 ps grid the root is located to ~0.01 ps.  The grid-quantised edges are
    returned alongside so the two can be compared."""
    li, hi_i = int(round(lo / GRID)), min(int(round(hi / GRID)), len(g) - 1)
    run = largest_run(mask, li, hi_i, pick)
    if run is None:
        return None
    a, b = run
    ta, tb = g[a], g[b]
    clip_lo, clip_hi = (a == li), (b == hi_i)
    # The sub-grid interpolation (AMENDMENT E1) is only VALID when the edge is a
    # MARGIN crossing.  If the mask edge was set by the AUXILIARY in-table
    # condition instead -- the receiver's rail entering the measured trip table --
    # then the margin at the neighbouring grid point is ALREADY past the
    # threshold, and solving margin(t)=thresh there EXTRAPOLATES BACKWARDS and
    # reports an edge a couple of ps too early.  Caught by an internal
    # consistency check against the emitted margin curve; see AMENDMENT E6.
    src_lo = src_hi = "margin_crossing"
    if curve is not None:
        if not clip_lo and a - 1 >= 0:                 # rising through thresh
            y0, y1 = curve[a - 1], curve[a]
            if y0 > thresh:
                src_lo = "auxiliary_condition_not_a_margin_crossing"
            elif y1 != y0:
                ta = g[a - 1] + (thresh - y0) * GRID / (y1 - y0)
        elif clip_lo:
            src_lo = "clipped_at_window_start"
        if not clip_hi and b + 1 < len(g):             # falling through thresh
            y0, y1 = curve[b], curve[b + 1]
            if y1 > thresh:
                src_hi = "auxiliary_condition_not_a_margin_crossing"
            elif y1 != y0:
                tb = g[b] + (thresh - y0) * GRID / (y1 - y0)
        elif clip_hi:
            src_hi = "clipped_at_window_end"
    return dict(pick=pick, open_ps=ta, close_ps=tb, width_ps=tb - ta,
                opening_edge_set_by=src_lo, closing_edge_set_by=src_hi,
                open_ps_gridquant=g[a], close_ps_gridquant=g[b],
                width_ps_gridquant=g[b] - g[a],
                i_open=a, i_close=b,
                clipped_at_window_start=clip_lo,
                clipped_at_window_end=clip_hi)


def d_dt(y, a):
    if a <= 0:
        return (y[1] - y[0]) / GRID
    if a >= len(y) - 1:
        return (y[-1] - y[-2]) / GRID
    return (y[a + 1] - y[a - 1]) / (2 * GRID)


def switch_state(P, k, t):
    E = EH.bt.EDGE
    rise = (P["c"][k] - E) <= t <= (P["o"][k] + E)
    ret = (P["r"][k] - E) <= t <= (P["ro"][k] + E)
    return rise, ret


def mechanism(P, k, a, gate, side, ref="EYE1_RX_INSTANTANEOUS", clipped=False):
    """Decompose d(mgn)/dt into its two exact terms at the edge and assign the
    PRE-REGISTERED M-code.

    ref selects the decision reference, because the decomposition differs:
      EYE1_RX_INSTANTANEOUS -- trip moves, so BOTH terms are live, and M7
                               (out-of-table) is part of that eye's definition.
      EYE2_DATA_FIXED       -- the trip is a CONSTANT, so d(trip)/dt is exactly
                               zero and the whole of d(mgn)/dt is dVout/dt.
                               M7 can never apply: the in-table condition is not
                               part of this eye's definition.
    clipped=True means the eye ran into a window bound rather than crossing the
    threshold, so there is no edge here and no mechanism to assign."""
    g = P["grid"]
    t = g[a]
    s = 1.0 if P["hi"][k][gate] else -1.0
    data_ref = (ref == "EYE2_DATA_FIXED")
    vo = P["C"]["V(O%d_%d)" % (k, gate)]
    dvo = 1000.0 * s * d_dt(vo, a)                  # mV/ps
    dtr = 0.0 if data_ref else -1000.0 * s * d_dt(P["trip"][k], a)   # mV/ps
    drk = d_dt(P["C"]["V(RAIL%d)" % k], a) * 1000.0
    drx = d_dt(P["rx"][k], a) * 1000.0
    dtk = d_dt(P["C"]["V(TNK%d)" % k], a) * 1000.0
    rise, ret = switch_state(P, k, t)
    il = P["C"]["I(L%d)" % k][a] * 1e6
    vin = (P["C"]["V(O%d_%d)" % (k - 1, gate)][a] if k > 1 else None)
    if (not data_ref) and (not P["intab"][k][a]):
        code = "M7"
    elif abs(dvo) >= abs(dtr):
        if rise:
            code = "M1"
        elif ret:
            code = "M3"
        elif drk < -0.05:
            code = "M4"
        else:
            code = "M1"
    else:
        if drx > 0.05:
            code = "M2"
        elif drx < -0.05:
            code = "M3" if ret else "M4"
        else:
            code = "M2"
    if code in ("M3", "M4") and dtk > 0.05 and il < 0:
        code = code + "+M5"
    if clipped:
        code = "NO_EDGE_WITHIN_DECK"
    return dict(M=code, reference=ref, t_ps=t,
                V_trip_used=(round(P["tripfix"][k], 7) if data_ref
                             else round(P["trip"][k][a], 7)),
                trip_is_constant_for_this_reference=bool(data_ref), gate="o%d" % gate, polarity=("HIGH" if P["hi"][k][gate] else "LOW"),
                mgn_mV=round(P["mgn"][k][gate][a], 4),
                d_mgn_dt_mV_per_ps=round(dvo + dtr, 5),
                term_dVout_dt_mV_per_ps=round(dvo, 5),
                term_minus_dtrip_dt_mV_per_ps=round(dtr, 5),
                dominant_term=("dVout/dt" if abs(dvo) >= abs(dtr) else "-dtrip/dt"),
                V_out=round(vo[a], 7),
                V_trip_rx=round(P["trip"][k][a], 7),
                V_rail_driver=round(P["C"]["V(RAIL%d)" % k][a], 7),
                dV_rail_driver_dt_mV_per_ps=round(drk, 5),
                V_rail_rx=round(P["rx"][k][a], 7),
                dV_rail_rx_dt_mV_per_ps=round(drx, 5),
                V_tank_driver=round(P["C"]["V(TNK%d)" % k][a], 7),
                dV_tank_dt_mV_per_ps=round(dtk, 5),
                I_L_driver_uA=round(il, 4),
                transfer_gate_conducting=bool(rise),
                return_switch_conducting=bool(ret),
                V_in_driver_gate=(round(vin, 7) if vin is not None else "ideal DC source (bank 1)"),
                overdrive_vs_Vtn_V=(round(vin - VTN, 7) if vin is not None else None),
                overdrive_vs_absVtp_V=(round(P["C"]["V(RAIL%d)" % k][a] - vin - VTP, 7)
                                       if vin is not None else None))
