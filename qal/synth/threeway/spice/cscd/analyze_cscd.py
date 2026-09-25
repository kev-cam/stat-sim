#!/usr/bin/env python3
"""Analyse a CSCD .prn: supply-current signature per vector window.

Xyce prints I(VDD) as current INTO the + node of VDD, so the block's drawn
supply current is I_blk = -I(VDD).  All reported currents are I_blk.
"""
import sys, os, json, math

def load(prn):
    f = open(prn)
    hdr = f.readline().split()
    cols = {n: i for i, n in enumerate(hdr)}
    rows = []
    for line in f:
        p = line.split()
        if not p or p[0].lower().startswith('end'):
            continue
        try:
            rows.append([float(x) for x in p])
        except ValueError:
            continue
    return hdr, cols, rows

def analyze(prn, tvec_ns, nwin, census=None, label=""):
    hdr, cols, rows = load(prn)
    ti = cols.get('TIME', 0)
    ii = None
    for k in cols:
        if k.upper().startswith('I(VDD'):
            ii = cols[k]
    assert ii is not None, "no I(VDD) column in %s: %s" % (prn, hdr)
    outcols = [(k, cols[k]) for k in hdr if k.upper().startswith('V(')]

    t = [r[ti] for r in rows]
    raw = [-r[ii] for r in rows]         # block supply current, positive = drawn
    # Trapezoidal integration rings at the Nyquist of the capped timestep: in the
    # settled tail the printed current alternates +7.35/-4.20 nA about a 1.57 nA
    # mean. A 2-point moving average cancels exactly that alternation and leaves
    # the physical waveform (whose features are >=10 samples wide) untouched.
    ib = [raw[0]] + [0.5 * (raw[k] + raw[k-1]) for k in range(1, len(raw))]

    res = {"file": os.path.basename(prn), "label": label, "n_points": len(rows),
           "t_end_ns": t[-1] * 1e9, "windows": []}

    for w in range(1, nwin):
        t0 = w * tvec_ns * 1e-9
        t1 = (w + 1) * tvec_ns * 1e-9
        idx = [k for k in range(len(t)) if t0 <= t[k] <= t1]
        if not idx:
            continue
        tw = [t[k] for k in idx]
        iw = [ib[k] for k in idx]

        # Quiescent floor = mean over the last 20% of the window BY TIME.
        # (Xyce's output points are NOT uniform -- 13252 points for a 20 ns run
        # requested at 5 ps -- so "last 20% of points" spans far more than the
        # last 20% of time wherever the solver stepped finely, and reported a
        # 47.6 uA "floor" where Xyce's own time-based .measure said 2.12 uA.)
        tcut = tw[-1] - 0.2 * (tw[-1] - tw[0])
        tail = [k for k in range(len(tw)) if tw[k] >= tcut]
        if len(tail) < 3:
            tail = list(range(len(tw) - 3, len(tw)))
        num = den = 0.0
        for k in tail[1:]:
            dt = tw[k] - tw[k-1]
            num += 0.5 * (iw[k] + iw[k-1]) * dt
            den += dt
        iq = num / den if den else iw[-1]

        ipk = max(iw)
        # charge above quiescent (trapezoid)
        q = 0.0
        for k in range(1, len(tw)):
            q += 0.5 * (iw[k] + iw[k-1]) * (tw[k] - tw[k-1])
        q_dyn = q - iq * (tw[-1] - tw[0])

        # LAST REAL TRANSITION: latest time any printed output crosses Vdd/2
        t_last_out = None
        out_cross = []
        for name, ci in outcols:
            prev = rows[idx[0]][ci]
            last = None
            for k in idx[1:]:
                v = rows[k][ci]
                if (prev - 0.6) * (v - 0.6) < 0:
                    last = t[k]
                    t_last_out = t[k] if t_last_out is None else max(t_last_out, t[k])
                prev = v
            if last is not None:
                out_cross.append((name, (last - t0) * 1e12))
        out_cross.sort(key=lambda x: x[1])

        # decay: first time after the peak that |I| falls below thr*Ipk and stays
        tpk = tw[iw.index(ipk)]
        def first_below(frac):
            thr = iq + frac * (ipk - iq)
            for k in range(len(tw)):
                if tw[k] < tpk:
                    continue
                if all(iw[j] < thr for j in range(k, len(tw))):
                    return tw[k]
            return None
        crossings = {}
        for frac in (0.5, 0.1, 0.01, 0.003, 0.001):
            c = first_below(frac)
            crossings["t_below_%g" % frac] = (c * 1e9) if c else None

        # LULL STRUCTURE: local minima of the current between the first rise and
        # the final decay -- these are the false-completion hazards.
        lulls = []
        arm = iq + 0.02 * (ipk - iq)
        # restrict to the active span
        act = [k for k in range(len(tw)) if iw[k] > arm]
        if act:
            a0, a1 = act[0], act[-1]
            k = a0 + 1
            while k < a1 - 1:
                if iw[k] < iw[k-1] and iw[k] <= iw[k+1]:
                    # confirm it is a real dip: peak on both sides
                    lmax = max(iw[a0:k+1]); rmax = max(iw[k:a1+1])
                    depth = min(lmax, rmax)
                    if depth > 0 and iw[k] < 0.5 * depth:
                        lulls.append({"t_ns": tw[k] * 1e9, "i_A": iw[k],
                                      "frac_of_peak": iw[k] / ipk,
                                      "ratio_to_iq": iw[k] / iq if iq else None})
                k += 1
        # pulse shape: FWHM of the current burst above the quiescent floor
        half = iq + 0.5 * (ipk - iq)
        above = [k for k in range(len(tw)) if iw[k] >= half]
        fwhm = (tw[above[-1]] - tw[above[0]]) if len(above) > 1 else 0.0
        # total time the current stays above 10x quiescent (the "busy" span)
        busy = [k for k in range(len(tw)) if iw[k] > 10 * iq]
        t_busy = (tw[busy[-1]] - tw[busy[0]]) if len(busy) > 1 else 0.0

        # keep the deepest few
        lulls.sort(key=lambda d: d["i_A"])
        res["windows"].append({
            "window": w,
            "name": census[w-1]["name"] if census else "",
            "hd_in": census[w-1]["hd_in"] if census else None,
            "net_toggles": census[w-1]["internal_node_toggles"] if census else None,
            "I_peak_A": ipk,
            "I_quiescent_A": iq,
            "peak_over_quiescent": ipk / iq if iq else None,
            "Q_window_C": q,
            "Q_dynamic_C": q_dyn,
            "E_dynamic_J": q_dyn * 1.2,
            "t_peak_ns": tpk * 1e9,
            "fwhm_ps": fwhm * 1e12,
            "t_above_10x_iq_ps": t_busy * 1e12,
            "t_last_output_cross_ns": (t_last_out * 1e9) if t_last_out else None,
            "output_cross_ps_rel": out_cross,
            "decay": crossings,
            "n_lulls": len(lulls),
            "deepest_lulls": lulls[:5],
        })
    return res

if __name__ == "__main__":
    prn = sys.argv[1]
    tvec = float(sys.argv[2]); nwin = int(sys.argv[3])
    lab = sys.argv[4] if len(sys.argv) > 4 else ""
    cen = None
    cf = os.path.join(os.path.dirname(os.path.abspath(prn)), "activity_census.json")
    if os.path.exists(cf):
        cen = json.load(open(cf))["windows"]
    r = analyze(prn, tvec, nwin, cen, lab)
    out = prn.replace(".prn", "") + ".sig.json"
    json.dump(r, open(out, "w"), indent=1)
    print("=== %s  (%d points, t_end=%.3f ns) ===" % (r["file"], r["n_points"], r["t_end_ns"]))
    print("%-3s %-16s %4s %5s %11s %11s %9s %11s %9s %8s"
          % ("W", "vector", "HDin", "togs", "Ipeak", "Iquies", "pk/q",
             "Qdyn(fC)", "tlastout", "lulls"))
    for w in r["windows"]:
        print("%-3d %-16s %4s %5s %9.4f mA %9.3f nA %9.0f %11.2f %9s %8d"
              % (w["window"], w["name"], w["hd_in"], w["net_toggles"],
                 w["I_peak_A"] * 1e3, w["I_quiescent_A"] * 1e9,
                 w["peak_over_quiescent"] or 0, w["Q_dynamic_C"] * 1e15,
                 ("%.3f" % w["t_last_output_cross_ns"]) if w["t_last_output_cross_ns"] else "-",
                 w["n_lulls"]))
        print("      pulse FWHM=%.1f ps   time above 10x quiescent=%.1f ps"
              % (w["fwhm_ps"], w["t_above_10x_iq_ps"]))
        d = w["decay"]
        print("      decay past peak (t_peak=%.3f ns): 50%%=%s  10%%=%s  1%%=%s  0.3%%=%s  0.1%%=%s"
              % (w["t_peak_ns"],
                 *[("%.3f" % d[k]) if d[k] else "-" for k in
                   ("t_below_0.5", "t_below_0.1", "t_below_0.01",
                    "t_below_0.003", "t_below_0.001")]))
        if w["output_cross_ps_rel"]:
            print("      output arrivals (ps after window start): %s"
                  % ", ".join("%s@%.0f" % (n.replace("V(", "").replace(")", ""), p)
                              for n, p in w["output_cross_ps_rel"]))
        for L in w["deepest_lulls"][:3]:
            print("      LULL t=%.3f ns  I=%.4g A  = %.3f%% of peak, %.1fx quiescent"
                  % (L["t_ns"], L["i_A"], 100 * L["frac_of_peak"], L["ratio_to_iq"] or 0))
    print("wrote", out)
