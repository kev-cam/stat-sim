#!/usr/bin/env python3
"""FUNCTIONAL COMMIT CRITERION -- re-score every committed chain dataset.

Nothing here re-simulates.  Every input is a committed .cir/.prn already on
disk; the only new measurement is qal/fcrit/TRIP.json (receiver threshold vs
delivered rail, measured by trip.py in this directory).

Three scores are produced for every gate so the flip can be ATTRIBUTED:

  S1  COMMITTED 90% BAR      gate output vs ITS OWN rail at ITS OWN committed
                             checkpoint; pass iff >= 90% settled.
                             (Also carries the committed VALUE guard:
                              LOW <= 0.10*rail, HIGH >= 0.50*rail.)
  S2  THRESHOLD ONLY         SAME instant, SAME reference rail; only the BAR
                             changes, 90%-settled -> MEASURED trip + noise
                             budget.  This isolates the criterion change.
  S3  FULL FUNCTIONAL        sender output vs the RECEIVER's measured trip at
                             the RECEIVER's delivered rail, at the instant the
                             RECEIVER commits (its charge delivery ends).

Wiring is literal in every deck: bank k cell i drives bank k+1 cell i
(bt.in_net / chain.in_net -> o{k-1}_{i}).  The LAST bank has no receiver inside
any deck; it is scored against its OWN rail and flagged GENEROUS (a real
successor's rail would be lower still, so this can only flatter the chain).
"""
import bisect, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
QAL = os.path.dirname(HERE)

SIGMA_TRIP_MV = 6.441          # MEASURED  qal/vtaudit/AUDIT.md (LOWER bound)
COUPLE_M6_MV = 31.1            # MEASURED  qal/tankfed/COUPLING_m6.json
COUPLE_M2_MV = 249.0           # MEASURED  qal/tankfed/COUPLING_m2.json
DROOP_MV = 28.6                # MEASURED  qal/skip4 held-rail droop, T105

NB = {
    "zero":        0.0,
    "sigma1":      SIGMA_TRIP_MV / 1000.0,
    "free":        3 * SIGMA_TRIP_MV / 1000.0,
    "hold":        (3 * SIGMA_TRIP_MV + DROOP_MV) / 1000.0,
    "topup_m6":    (3 * SIGMA_TRIP_MV + COUPLE_M6_MV + DROOP_MV) / 1000.0,
    "topup_worst": (3 * SIGMA_TRIP_MV + COUPLE_M2_MV + DROOP_MV) / 1000.0,
}


# ----------------------------------------------------------------- threshold
class Trip(object):
    def __init__(self, path, tag="S"):
        d = json.load(open(path))[tag]
        self.tag = tag
        self.wp, self.wn = d["wp"], d["wn"]
        ks = sorted(d["rows"], key=float)
        v = [d["rows"][k]["vdd"] for k in ks]
        t = [d["rows"][k]["trip_V"] for k in ks]
        w = [d["rows"][k]["window_10_90_mV"] for k in ks]
        keep = [i for i in range(len(v)) if t[i] is not None]
        self.v = [v[i] for i in keep]
        self.t = [t[i] for i in keep]
        self.w = [w[i] for i in keep]
        self.lo, self.hi = self.v[0], self.v[-1]

    def __call__(self, vdd):
        """(V_trip, extrapolated?) at this delivered rail."""
        if vdd <= self.lo:
            return self.t[0] * vdd / self.lo, True
        if vdd >= self.hi:
            return self.t[-1] * vdd / self.hi, True
        j = bisect.bisect_left(self.v, vdd)
        a, b = self.v[j - 1], self.v[j]
        return self.t[j - 1] + (self.t[j] - self.t[j - 1]) * (vdd - a) / (b - a), False

    def window(self, vdd):
        j = min(range(len(self.v)), key=lambda i: abs(self.v[i] - vdd))
        return self.w[j]


# ------------------------------------------------------------------- prn I/O
class Wave(object):
    def __init__(self, path):
        f = open(path)
        self.hdr = [h.upper() for h in f.readline().split()]
        self.rows = []
        for ln in f:
            p = ln.split()
            if not p or p[0].lower().startswith("end"):
                continue
            try:
                self.rows.append([float(x) for x in p])
            except ValueError:
                continue
        f.close()
        self.it = self.hdr.index("TIME")
        self.t = [r[self.it] * 1e12 for r in self.rows]

    def has(self, name):
        return name.upper() in self.hdr

    def s(self, name):
        j = self.hdr.index(name.upper())
        return [r[j] for r in self.rows]

    def idx(self, tt):
        i = bisect.bisect_left(self.t, tt)
        if i <= 0:
            return 0
        if i >= len(self.t):
            return len(self.t) - 1
        return i if abs(self.t[i] - tt) < abs(self.t[i - 1] - tt) else i - 1

    def at(self, name, tt):
        """linear interpolation at tt (ps)"""
        y = self.s(name)
        i = bisect.bisect_left(self.t, tt)
        if i <= 0:
            return y[0]
        if i >= len(self.t):
            return y[-1]
        t0, t1 = self.t[i - 1], self.t[i]
        if t1 == t0:
            return y[i]
        return y[i - 1] + (y[i] - y[i - 1]) * (tt - t0) / (t1 - t0)


def zero_after_peak(w, sig):
    """committed protocol (chain.zero_after_peak): first downward zero crossing
    after the current peak."""
    I = w.s(sig)
    ipk = max(I)
    if ipk <= 0:
        return None, None
    ip = I.index(ipk)
    for i in range(ip + 1, len(I)):
        if I[i - 1] > 0 >= I[i]:
            t0, t1 = w.t[i - 1], w.t[i]
            return t0 + (t1 - t0) * I[i - 1] / (I[i - 1] - I[i]), w.t[ip]
    return None, w.t[ip]


def commit_instants(w, nbank):
    """t_commit(k) for every bank, MEASURED from the waveform.

    A bank charged by an inductor commits at that hop's ZCS (its charge
    delivery ends).  The charging inductor is identified EMPIRICALLY -- the one
    whose [peak, zero] window raised this rail the most -- so no wiring is
    assumed.  A bank with no charging inductor (a precharged head) commits at
    the first stationary point of its own rail after it passes half its peak.
    """
    zs = {}
    for j in range(1, 13):
        if w.has("I(L%d)" % j):
            tz, tp = zero_after_peak(w, "I(L%d)" % j)
            if tz is not None:
                zs[j] = (tz, tp)
    out = {}
    for k in range(1, nbank + 1):
        r = w.s("V(RAIL%d)" % k)
        pk = max(r)
        best, bj, brise = None, None, 0.0
        for j, (tz, tp) in zs.items():
            rise = w.at("V(RAIL%d)" % k, tz) - w.at("V(RAIL%d)" % k, tp)
            if rise > brise:
                brise, best, bj = rise, tz, j
        if best is not None and brise > 0.05 * pk:
            out[k] = dict(t=best, src="ZCS I(L%d)" % bj, rise_V=round(brise, 6))
            continue
        # precharged head: first stationary point after half-peak
        half = 0.5 * pk
        i0 = next((i for i in range(len(r)) if r[i] >= half), 0)
        tb = w.t[max(range(len(r)), key=lambda i: r[i])]
        for i in range(i0 + 1, len(r) - 3):
            if r[i] >= r[i + 1] and r[i] - r[i + 3] > 2e-4:
                tb = w.t[i]
                break
        out[k] = dict(t=tb, src="rail stationary point (precharged head)",
                      rise_V=None)
    return out


CK_RE = re.compile(r"^\.measure\s+tran\s+O(\d+)_(\d+)[SB]\s+FIND\s+V\(o\d+_\d+\)"
                   r"\s+AT=([0-9.eE+-]+)p", re.I)


def committed_checkpoints(cir):
    """{bank: t_ps} -- the instant the committed extractor sampled that bank."""
    ck = {}
    for ln in open(cir):
        m = CK_RE.match(ln.strip())
        if m:
            ck[int(m.group(1))] = float(m.group(3))
    return ck


# ------------------------------------------------------------------- scoring
def score_deck(cir, nbank, mgate, out_hi, trip, nb, gate_idx=None,
               label="", prn=None):
    prn = prn or (cir + ".prn")
    w = Wave(prn)
    ck = committed_checkpoints(cir)
    tc = commit_instants(w, nbank)
    gi = gate_idx if gate_idx is not None else list(range(mgate))

    links = []
    for k in range(1, nbank + 1):
        if k not in ck:
            continue
        rk = w.at("V(RAIL%d)" % k, ck[k])
        rx = k + 1 if (k + 1) <= nbank else k
        generous = (rx == k)
        # The LAST bank has no receiver inside the deck.  Its own commit instant
        # is the WRONG proxy -- a receiver always commits one stage LATER, so
        # sampling the last bank at its own ZCS charges it for a tail its real
        # successor would never have seen (MEASURED: it mis-flags 5 bank-4 gates
        # in banktank rows that the committed VALUE check passes 32/32, and they
        # cross the trip 5.0 ps later).  For k == N the functional score is taken
        # at the committed stage boundary -- the last instant that bank is valid,
        # exactly where the committed extractor sampled it -- and flagged
        # GENEROUS, because a real successor's rail would be lower still.
        trx = ck[k] if generous else tc[rx]["t"]
        Rrx = w.at("V(RAIL%d)" % rx, trx)
        vt_rx, ex_rx = trip(Rrx)
        vt_own, ex_own = trip(rk)
        for i in gi:
            col = "V(O%d_%d)" % (k, i)
            if not w.has(col):
                continue
            want_hi = bool(out_hi(k, i))
            v1 = w.at(col, ck[k])                     # committed instant
            v3 = w.at(col, trx)                       # receiver commit instant

            # --- S1 committed 90% bar + committed value guard
            s1 = 100.0 * ((v1 / rk) if want_hi else (1.0 - v1 / rk)) if rk else None
            s1_pass = (s1 is not None and s1 >= 90.0)
            guard = ((v1 >= 0.50 * rk) if want_hi else (v1 <= 0.10 * rk)) if rk else False

            # --- S2 threshold only, same instant, same reference rail
            d2 = (v1 - vt_own) if want_hi else (vt_own - v1)
            s2_pass = d2 >= nb

            # --- S3 full functional
            d3 = (v3 - vt_rx) if want_hi else (vt_rx - v3)
            s3_pass = d3 >= nb
            later = None
            if d3 < 0:
                y = w.s(col)
                ib = w.idx(trx)
                for j in range(ib + 1, len(y)):
                    dd = (y[j] - vt_rx) if want_hi else (vt_rx - y[j])
                    if dd >= 0:
                        later = w.t[j]
                        break
            mode = ("PASS" if s3_pass else
                    "FAIL_budget" if d3 >= 0 else
                    "FAIL_late" if later is not None else "FAIL_never")

            links.append(dict(
                k=k, i=i, want_hi=want_hi, rx_bank=rx, rx_generous=generous,
                t_committed_ps=round(ck[k], 3), rail_own_V=round(rk, 6),
                v_at_committed_V=round(v1, 6), settle_pct=(round(s1, 3) if s1 is not None else None),
                S1_pass90=bool(s1_pass), value_guard_pass=bool(guard),
                vtrip_own_V=round(vt_own, 6), S2_margin_mV=round(1000 * d2, 3),
                S2_pass=bool(s2_pass),
                t_commit_ps=round(trx, 3), rail_rx_V=round(Rrx, 6),
                v_at_commit_V=round(v3, 6), vtrip_rx_V=round(vt_rx, 6),
                S3_margin_mV=round(1000 * d3, 3), S3_pass=bool(s3_pass),
                S3_mode=mode, crosses_at_ps=(round(later, 3) if later else None),
                trip_extrapolated=bool(ex_rx or ex_own)))

    def agg(key):
        return sum(1 for L in links if L[key])
    return dict(
        label=label, deck=os.path.basename(cir), n_gates=len(links),
        commit_instants={k: dict(t_ps=round(tc[k]["t"], 3), src=tc[k]["src"])
                         for k in tc},
        committed_checkpoints={k: round(v, 3) for k, v in ck.items()},
        S1_pass=agg("S1_pass90"), S2_pass=agg("S2_pass"), S3_pass=agg("S3_pass"),
        value_guard_pass=agg("value_guard_pass"),
        S3_FAIL_budget=sum(1 for L in links if L["S3_mode"] == "FAIL_budget"),
        S3_FAIL_late=sum(1 for L in links if L["S3_mode"] == "FAIL_late"),
        S3_FAIL_never=sum(1 for L in links if L["S3_mode"] == "FAIL_never"),
        ROW_S1=bool(links) and agg("S1_pass90") == len(links),
        ROW_VALUE=bool(links) and agg("value_guard_pass") == len(links),
        ROW_S2=bool(links) and agg("S2_pass") == len(links),
        ROW_S3=bool(links) and agg("S3_pass") == len(links),
        links=links)
