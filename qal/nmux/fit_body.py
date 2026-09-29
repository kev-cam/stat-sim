#!/usr/bin/env python3
"""(a) fit the body-effect coefficient to the MEASURED Vtn(V_sb) curve and solve
the self-consistent nMOS pass ceiling  V* = VGH - Vtn(V*)  at VGH = 1.5 V.

Fit form (classical):  Vt(Vsb) = Vt0 + gamma * ( sqrt(2*phi_F + Vsb) - sqrt(2*phi_F) )
2*phi_F is fitted too (grid search) because the textbook 0.85 V is an ASSUMPTION
and this PDK need not honour it.  The residual is reported so the reader can see
whether the classical law actually describes PSP103 here.
"""
import json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
VGH = 1.5


def fit(vsb, vt):
    best = None
    for i in range(1, 4001):                 # 2*phi_F from 0.005 to 20 V
        phi = i * 0.005
        d = [math.sqrt(phi + v) - math.sqrt(phi) for v in vsb]
        sxx = sum(x * x for x in d)
        if sxx <= 0:
            continue
        # Vt0 pinned to the measured Vsb = 0 point, gamma by least squares
        vt0 = vt[0]
        g = sum(x * (y - vt0) for x, y in zip(d, vt)) / sxx
        r = sum((vt0 + g * x - y) ** 2 for x, y in zip(d, vt))
        if best is None or r < best[0]:
            best = (r, phi, g, vt0)
    r, phi, g, vt0 = best
    n = len(vt)
    return {"two_phi_F_V": phi, "gamma_V_sqrt": g, "Vt0_V": vt0,
            "rms_residual_mV": 1e3 * math.sqrt(r / n),
            "max_residual_mV": 1e3 * max(abs(vt0 + g * (math.sqrt(phi + v) -
                                          math.sqrt(phi)) - y)
                                         for v, y in zip(vsb, vt))}


def interp(xs, ys, x):
    if x <= xs[0]:
        return ys[0]
    for i in range(1, len(xs)):
        if xs[i] >= x:
            f = (x - xs[i - 1]) / (xs[i] - xs[i - 1])
            return ys[i - 1] + f * (ys[i] - ys[i - 1])
    return ys[-1]


def ceiling(vsb, vt, vgh=VGH):
    """solve V* = vgh - Vtn(V*) by bisection on the MEASURED curve"""
    f = lambda v: vgh - interp(vsb, vt, v) - v
    lo, hi = 0.0, max(vsb)
    if f(hi) > 0:
        return None, "no crossing below V_sb=%.2f: ceiling exceeds the probed range" % hi
    if f(lo) < 0:
        return 0.0, "ceiling at or below 0 V"
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if f(mid) > 0:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi), "bisection on the measured curve"


def main():
    rows = json.load(open(os.path.join(HERE, "vtb_rows.json")))["rows"]
    out = {"_doc": "(a) body effect fit + self-consistent nMOS pass ceiling",
           "MEASURED_curve": {}, "fits": {}, "ceilings": {}}
    for crit, lab in (("vt_c100", "100nA*W/L (campaign criterion)"),
                      ("vt_c10", "10nA*W/L"), ("vt_c1", "1nA*W/L")):
        pts = [(r["vsb"], r[crit]) for r in rows if r.get(crit)]
        if len(pts) < 4:
            out["fits"][crit] = {"SKIP": "only %d usable points" % len(pts)}
            continue
        vsb = [p[0] for p in pts]; vt = [p[1] for p in pts]
        out["MEASURED_curve"][crit] = {"criterion": lab,
                                       "Vsb_V": vsb, "Vtn_V": vt,
                                       "dVt_total_mV": (vt[-1] - vt[0]) * 1e3}
        out["fits"][crit] = fit(vsb, vt)
        v, how = ceiling(vsb, vt)
        out["ceilings"][crit] = {
            "pass_ceiling_V": v, "how": how,
            "_meaning": "the highest level an nMOS with its gate at %.2f V can "
                        "hold on its source; body effect is included because "
                        "Vtn is read AT that source level" % VGH}
        # margins at the two rails of interest
        for lab2, rail in (("peer_fed_0.755", 0.755), ("tank_fed_1.26", 1.26),
                           ("tank_fed_1.326", 1.326)):
            out["ceilings"][crit]["margin_" + lab2 + "_mV"] = \
                (v - rail) * 1e3 if v is not None else None
    json.dump(out, open(os.path.join(HERE, "body_fit.json"), "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
