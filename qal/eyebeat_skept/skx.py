#!/usr/bin/env python3
"""SKEPTIC extractor -- an INDEPENDENT implementation of the pre-registered
eye / tracking-lag / stranded-HIGH definitions.  Shares NO code with
eyecalc.py / eb.py: numpy resampling, own Trip interpolation read directly
from qal/fcrit/TRIP.json, own crossing/edge logic.

Definitions implemented (from qal/eyebeat/PRE_REGISTERED.json):
  EYE2_DATA_FIXED: per link k -> k+1, decision level Trip_S(VR{k+1}B{k+1})
    with the receiver's delivered rail taken from EACH PATTERN'S OWN .mt0 and
    the trip INTERPOLATED on the 27 measured TRIP.json points.  Margin
    mgn(k,i,t) = +/-1000*(V(o_k_i)-trip) mV, sign by expected polarity.
  Eye mask at threshold thr: min over ALL 8 gates (both polarities) of the
    margin, INTERSECTED over patterns, > thr.  Window [c_k, tend-1ps]; the
    FIRST contiguous open run; edges sub-grid interpolated on the intersection
    curve.  Heights at the sampling instant c_k + T from the HIGH-only and
    LOW-only intersection curves.
  EYE1_RX_INSTANTANEOUS: trip interpolated at the receiver's INSTANTANEOUS
    rail, in-table condition part of the mask (reported for the policing
    check, not the headline).
  TRACKING LAG A (same-level): rising at 0.5*VRkPK; draining at
    vref = 0.5*(rail(r_k) + min rail over [r_k, r_k+2*(ro_k-r_k)]).
  TRACKING LAG B: rail up through VRkBk -> HIGH output up through the link's
    fixed decision level.
  STRANDED-HIGH: min HIGH output over [r_k-EDGE, min(ro_k+200, end)] + droop
    slope from r_k to the minimum.
  Value check: HIGH >= 0.5*rail, LOW <= 0.1*rail at the committed boundary
    (bits correct/incorrect, no completion language).

Usage: skx.py <T> [--root=DIR] [--pats=P0,P1,P2] [--out=FILE] [--banks=1,2,3]
  --root defaults to <this dir>/T{T}
"""
import json, math, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
TRIPJSON = "/usr/local/src/stat-sim/qal/fcrit/TRIP.json"
GRID = 0.10
SIG = 6.441
EDGE = 2.0
NB, MG = 4, 8


# ---------------------------------------------------------------- trip table
class TripS:
    def __init__(self):
        d = json.load(open(TRIPJSON))["S"]
        rows = sorted(((r["vdd"], r["trip_V"]) for r in d["rows"].values()
                       if r["trip_V"] is not None), key=lambda x: x[0])
        self.v = np.array([r[0] for r in rows])
        self.t = np.array([r[1] for r in rows])
        self.lo, self.hi = self.v[0], self.v[-1]

    def at(self, vdd):
        """scalar or array; proportional extrapolation outside the table,
        flagged by in_table."""
        vdd = np.asarray(vdd, dtype=float)
        inside = (vdd >= self.lo) & (vdd <= self.hi)
        out = np.interp(vdd, self.v, self.t)
        out = np.where(vdd < self.lo, self.t[0] * vdd / self.lo, out)
        out = np.where(vdd > self.hi, self.t[-1] * vdd / self.hi, out)
        return out, inside


TRIP = TripS()

PATTERNS = {"P0": [1, 1, 1, 0, 1, 0, 0, 1],
            "P1": [0, 0, 0, 0, 0, 0, 0, 0],
            "P2": [1, 1, 1, 1, 1, 1, 1, 1],
            "P3": [1, 0, 1, 0, 1, 0, 1, 0]}


def out_hi(pat, k, i):
    in_hi = (pat[i] == 1) if (k % 2 == 1) else (pat[i] == 0)
    return not in_hi


# --------------------------------------------------------------------- I/O
def read_mt0(path):
    d = {}
    for ln in open(path):
        if "=" in ln:
            a, _, b = ln.partition("=")
            try:
                d[a.strip().upper()] = float(b.split()[0])
            except (ValueError, IndexError):
                pass
    return d


def load_lane(root, pname):
    sub = os.path.join(root, pname)
    S = json.load(open(os.path.join(sub, "sched.json")))
    prn, mt0 = S["prn"], S["mt0"]
    hdr, data = None, []
    with open(prn) as f:
        for ln in f:
            p = ln.split()
            if hdr is None:
                if p and p[0].lower() == "index":
                    hdr = [h.upper() for h in p]
                continue
            if not p or p[0].lower().startswith("end"):
                continue
            if len(p) != len(hdr):
                continue
            try:
                data.append([float(x) for x in p])
            except ValueError:
                continue
    A = np.array(data)
    t = A[:, hdr.index("TIME")] * 1e12
    n = int(math.floor(float(S["tend"]) / GRID)) + 1
    g = np.arange(n) * GRID
    cols = {}
    for ci, nm in enumerate(hdr):
        if nm in ("INDEX", "TIME"):
            continue
        cols[nm] = np.interp(g, t, A[:, ci])
    sch = {key: {int(k): float(v) for k, v in S[key].items()}
           for key in ("c", "o", "r", "ro")}
    return dict(name=pname, bits=PATTERNS[pname], S=S, sch=sch, g=g, n=n,
                C=cols, mt0=read_mt0(mt0),
                A6=bool(S.get("A6_pass")), A6_worst=S.get("A6_worst_uA"))


# ---------------------------------------------------------------- crossings
def cross(g, y, level, t0, t1, direction):
    """First linear-interpolated crossing of y through level inside [t0,t1]."""
    a0 = max(1, int(math.ceil(t0 / GRID)))
    a1 = min(len(g) - 1, int(math.floor(t1 / GRID)))
    if a1 <= a0:
        return None
    seg0, seg1 = y[a0 - 1:a1], y[a0:a1 + 1]
    if direction > 0:
        hit = np.nonzero((seg0 < level) & (seg1 >= level))[0]
    else:
        hit = np.nonzero((seg0 > level) & (seg1 <= level))[0]
    if len(hit) == 0:
        return None
    a = a0 + hit[0]
    y0, y1 = y[a - 1], y[a]
    return g[a - 1] + (level - y0) * GRID / (y1 - y0)


def first_run(mask, a_lo, a_hi):
    idx = np.nonzero(mask[a_lo:a_hi + 1])[0]
    if len(idx) == 0:
        return None
    a = a_lo + idx[0]
    d = np.nonzero(~mask[a:a_hi + 1])[0]
    b = (a + d[0] - 1) if len(d) else a_hi
    return a, b


def edge_interp(curve, g, a, b, thr, a_lo, a_hi):
    ta, tb = g[a], g[b]
    clip_lo, clip_hi = (a == a_lo), (b == a_hi)
    if not clip_lo and a >= 1 and curve[a - 1] <= thr and curve[a] != curve[a - 1]:
        ta = g[a - 1] + (thr - curve[a - 1]) * GRID / (curve[a] - curve[a - 1])
    if not clip_hi and b + 1 < len(g) and curve[b + 1] <= thr and curve[b + 1] != curve[b]:
        ta2 = g[b] + (thr - curve[b]) * GRID / (curve[b + 1] - curve[b])
        tb = ta2
    return ta, tb, clip_lo, clip_hi


def st(vals):
    if not vals:
        return None
    v = sorted(vals)
    return dict(n=len(v), min=round(v[0], 4), max=round(v[-1], 4),
                median=round(v[len(v) // 2], 4),
                mean=round(sum(v) / len(v), 4))


# ------------------------------------------------------------------- main
def extract(T, root, pats, banks):
    lanes = {p: load_lane(root, p) for p in pats}
    good = [p for p in pats if lanes[p]["A6"]]
    n = min(lanes[p]["n"] for p in pats)
    g = lanes[good[0]]["g"][:n]
    out = dict(T_ps=T, root=root, patterns=pats, patterns_in_intersection=good,
               a6={p: dict(A6=lanes[p]["A6"], worst_uA=lanes[p]["A6_worst"])
                   for p in pats},
               banks={})

    # value check per pattern
    val = {}
    for p in pats:
        d = lanes[p]["mt0"]
        bad = []
        for k in range(1, NB + 1):
            rail = d.get("VR%dB%d" % (k, k))
            for i in range(MG):
                v = d.get("O%d_%dB" % (k, i))
                if v is None or rail is None:
                    bad.append([k, i, "missing"])
                elif out_hi(PATTERNS[p], k, i):
                    if v < 0.50 * rail:
                        bad.append([k, i, round(v, 5), round(rail, 5)])
                elif v > 0.10 * rail:
                    bad.append([k, i, round(v, 5), round(rail, 5)])
        val[p] = dict(bits_correct=32 - len(bad), bits_wrong=len(bad), fails=bad)
    out["value_check"] = val

    for k in banks:
        kr = k + 1 if k < NB else NB
        P0 = lanes[good[0]]
        ck, rk = P0["sch"]["c"][k], P0["sch"]["r"][k]
        tendw = g[-1] - 1.0
        rec = dict(c_ps=ck, r_ps=rk)

        # margins per pattern: EYE2 fixed-trip and EYE1 instantaneous
        m2_all, m2_hi, m2_lo, m1_all, intab_all = [], [], [], [], []
        tripfix = {}
        for p in good:
            L = lanes[p]
            vrb = L["mt0"]["VR%dB%d" % (kr, kr)]
            tf, _ = TRIP.at(vrb)
            tripfix[p] = float(tf)
            if k < NB:
                rx = L["C"]["V(RAIL%d)" % (k + 1)][:n]
            else:
                src = L["C"]["V(RAIL%d)" % (NB - 1)][:n]
                sh = int(round(T / GRID))
                rx = np.concatenate([np.full(sh, src[0]), src[:-sh]]) if sh else src
            tinst, inside = TRIP.at(rx)
            gm2, gm1 = [], []
            for i in range(MG):
                vo = L["C"]["V(O%d_%d)" % (k, i)][:n]
                sg = 1.0 if out_hi(L["bits"], k, i) else -1.0
                gm2.append(1000.0 * sg * (vo - tf))
                gm1.append(1000.0 * sg * (vo - tinst))
            hi_ = [i for i in range(MG) if out_hi(L["bits"], k, i)]
            lo_ = [i for i in range(MG) if not out_hi(L["bits"], k, i)]
            m2_all.append(np.min(gm2, axis=0))
            m1_all.append(np.min(gm1, axis=0))
            m2_hi.append(np.min([gm2[i] for i in hi_], axis=0) if hi_ else None)
            m2_lo.append(np.min([gm2[i] for i in lo_], axis=0) if lo_ else None)
            intab_all.append(inside)
        c2 = np.min(m2_all, axis=0)                 # intersection over patterns
        c1 = np.min(m1_all, axis=0)
        it = np.logical_and.reduce(intab_all)
        hi_curves = [x for x in m2_hi if x is not None]
        lo_curves = [x for x in m2_lo if x is not None]
        ch = np.min(hi_curves, axis=0) if hi_curves else None
        cl = np.min(lo_curves, axis=0) if lo_curves else None
        rec["tripfix_per_pattern_V"] = {p: round(tripfix[p], 6) for p in good}

        a_lo = int(round(ck / GRID))
        a_hi = min(int(round(tendw / GRID)), n - 1)
        samp = ck + T
        ia = max(0, min(n - 1, int(round(samp / GRID))))
        rec["EYES"] = {}
        for ref, curve, use_tab in (("EYE2", c2, False), ("EYE1", c1, True)):
            R = {}
            for tn, thr in (("0mV", 0.0), ("1sigma", SIG), ("3sigma", 3 * SIG)):
                mask = curve > thr
                if use_tab:
                    mask = mask & it
                fr = first_run(mask, a_lo, a_hi)
                if fr is None:
                    R[tn] = dict(EYE="EMPTY")
                    continue
                a, b = fr
                ta, tb, cl_, ch_ = edge_interp(curve, g, a, b, thr, a_lo, a_hi)
                R[tn] = dict(
                    opening_ps=round(float(ta), 4),
                    closing_ps=round(float(tb), 4),
                    WIDTH_ps=round(float(tb - ta), 4),
                    WIDTH_over_T=round(float(tb - ta) / T, 4),
                    opening_minus_c_ps=round(float(ta - ck), 4),
                    closing_minus_r_ps=round(float(tb - rk), 4),
                    setup_slack_ps=round(T - float(ta - ck), 4),
                    clipped_end=bool(ch_), WIDTH_IS_LOWER_BOUND=bool(ch_),
                    eye_open_at_sampling=bool(mask[ia] and ta <= samp <= tb),
                    HEIGHT_at_sampling_HIGH_mV=(round(float(ch[ia]), 4)
                                                if ch is not None else None),
                    HEIGHT_at_sampling_LOW_mV=(round(float(cl[ia]), 4)
                                               if cl is not None else None))
            rec["EYES"][ref] = R

        ar = min(n - 1, int(round(rk / GRID)))
        j = int(np.argmin(c2[ar:])) + ar
        rec["POST_RETURN_FLOOR_EYE2"] = dict(
            floor_mV=round(float(c2[j]), 4), at_t_ps=round(float(g[j]), 4),
            at_t_minus_r_ps=round(float(g[j] - rk), 4),
            in_sigma_trip=round(float(c2[j]) / SIG, 3))

        # ---- tracking lag + stranded-HIGH
        lagA_r, lagA_d, lagB_r, cens = [], [], [], 0
        strand, droop = [], []
        for p in good:
            L = lanes[p]
            rail = L["C"]["V(RAIL%d)" % k][:n]
            vpk = L["mt0"]["VR%dPK" % k]
            vrb_own = L["mt0"]["VR%dB%d" % (k, k)]
            rop = L["sch"]["ro"][k]
            rkp = L["sch"]["r"][k]
            ckp = L["sch"]["c"][k]
            lvl = 0.5 * vpk
            tr = cross(g, rail, lvl, ckp - EDGE, rkp, +1)
            ir0 = min(n - 1, int(round(rkp / GRID)))
            ir1 = min(n - 1, int(round(min(rkp + 2 * (rop - rkp), g[-1]) / GRID)))
            vfloor = float(np.min(rail[ir0:ir1 + 1]))
            vref_d = 0.5 * (float(rail[ir0]) + vfloor)
            trd = cross(g, rail, vref_d, rkp - EDGE, g[-1], -1)
            trb = cross(g, rail, vrb_own, ckp - EDGE, rkp, +1)
            wend = min(rop + 200.0, g[-1])
            i0 = max(0, int(round((rkp - EDGE) / GRID)))
            i1 = min(n - 1, int(round(wend / GRID)))
            for i in range(MG):
                if not out_hi(L["bits"], k, i):
                    continue
                vo = L["C"]["V(O%d_%d)" % (k, i)][:n]
                to = cross(g, vo, lvl, ckp - EDGE, rkp, +1)
                if tr is not None and to is not None:
                    lagA_r.append(to - tr)
                tob = cross(g, vo, tripfix[p], ckp - EDGE, rkp, +1)
                if trb is not None and tob is not None:
                    lagB_r.append(tob - trb)
                tod = cross(g, vo, vref_d, rkp - EDGE, wend, -1)
                if trd is not None:
                    if tod is not None:
                        lagA_d.append(tod - trd)
                    else:
                        cens += 1
                jm = int(np.argmin(vo[i0:i1 + 1])) + i0
                strand.append(float(vo[jm]))
                if g[jm] > rkp:
                    droop.append(1000.0 * (float(vo[ir0]) - float(vo[jm]))
                                 / max(g[jm] - rkp, 1e-9))
        rec["TRACKING_LAG"] = dict(rising_LAG_A_ps=st(lagA_r),
                                   rising_LAG_B_ps=st(lagB_r),
                                   draining_LAG_A_ps=st(lagA_d),
                                   draining_censored=cens)
        rec["STRANDED_HIGH"] = dict(
            min_HIGH_during_drain_V=(round(min(strand), 5) if strand else None),
            per_gate_min_V=st(strand),
            droop_slope_mV_per_ps=st(droop))
        out["banks"][str(k)] = rec
    return out


if __name__ == "__main__":
    T = float(sys.argv[1])
    root = os.path.join(HERE, "T%g" % T)
    pats, banks, ofn = ["P0", "P1", "P2"], [1, 2, 3, 4], None
    for x in sys.argv[2:]:
        if x.startswith("--root="):
            root = x[7:]
        elif x.startswith("--pats="):
            pats = x[7:].split(",")
        elif x.startswith("--banks="):
            banks = [int(y) for y in x[8:].split(",")]
        elif x.startswith("--out="):
            ofn = x[6:]
    out = extract(T, root, pats, banks)
    ofn = ofn or os.path.join(root, "SKX.json")
    json.dump(out, open(ofn, "w"), indent=1)
    print("wrote", ofn)
    for k in out["banks"]:
        b = out["banks"][k]
        for tn in ("0mV", "3sigma"):
            z = b["EYES"]["EYE2"].get(tn, {})
            if "EYE" in z:
                print("T%g bank%s %s EMPTY" % (T, k, tn))
                continue
            print("T%-4g bank%s %-7s open %9.3f (c+%8.4f) close %9.3f W %9.3f%s"
                  " W/T %7.4f slack %8.4f H %s/%s" %
                  (T, k, tn, z["opening_ps"], z["opening_minus_c_ps"],
                   z["closing_ps"], z["WIDTH_ps"],
                   "LB" if z["WIDTH_IS_LOWER_BOUND"] else "  ",
                   z["WIDTH_over_T"], z["setup_slack_ps"],
                   z["HEIGHT_at_sampling_HIGH_mV"], z["HEIGHT_at_sampling_LOW_mV"]))
        tl, sh = b["TRACKING_LAG"], b["STRANDED_HIGH"]
        print("   lagAr %s lagBr %s lagAd %s cens %d strand %s droop %s" %
              (tl["rising_LAG_A_ps"] and tl["rising_LAG_A_ps"]["median"],
               tl["rising_LAG_B_ps"] and tl["rising_LAG_B_ps"]["median"],
               tl["draining_LAG_A_ps"] and tl["draining_LAG_A_ps"]["median"],
               tl["draining_censored"], sh["min_HIGH_during_drain_V"],
               sh["droop_slope_mV_per_ps"] and sh["droop_slope_mV_per_ps"]["median"]))
    fl = {k: out["banks"][k]["POST_RETURN_FLOOR_EYE2"] for k in out["banks"]}
    print("floors:", json.dumps(fl))
    print("value:", json.dumps({p: (v["bits_wrong"]) for p, v in out["value_check"].items()}))
