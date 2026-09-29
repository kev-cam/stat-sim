#!/usr/bin/env python3
"""THE COUPLING, re-measured at a LOGIC node -- and with the question the 2x2
cannot answer added back.

The committed 2x2 varies the top-up DESTINATION (bank vs tank) with the tank
PRESENT IN BOTH ARMS.  But the brief's claim is that "the tank is LARGE, so the
same injected charge makes a far smaller voltage step".  That is a claim about
HAVING a tank, not about WHERE the charge lands -- and the 2x2 holds the tank
fixed, so it cannot measure it.  The NOTANK arm restores that control.

Reported per (topped bank, arrangement), topped minus its OWN free control with
the top-up devices physically present and parked off in both:

  step_at_logic_mV   max over the feeding stage's pull-down outputs of the
                     instantaneous |V_topped(t) - V_free(t)| over the top-up
                     window, on a common interpolated grid.  A LOGIC node.
  lift_at_logic_mV   the same difference at the END of the window (the settled
                     part of the step, as opposed to the transient peak).
  slope_*            max |dV/dt| V/ns at the injection node, the bank rail, and
                     the worst logic node.
"""
import json, os, sys
import sk

FEEDER = {3: 2, 4: 3}


def interp(series, t):
    lo, hi = 0, len(series) - 1
    if t <= series[0][0]:
        return series[0][1]
    if t >= series[-1][0]:
        return series[-1][1]
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if series[mid][0] <= t:
            lo = mid
        else:
            hi = mid
    t0, v0 = series[lo]; t1, v1 = series[hi]
    return v0 if t1 == t0 else v0 + (v1 - v0) * (t - t0) / (t1 - t0)


def col(hdr, rows, name):
    ic = hdr.index(name)
    return [(r[1] * 1e12, r[ic]) for r in rows]


def pair(free_row, top_row, kb, win):
    prof = sk.PROFILE
    kf = FEEDER[kb]
    out = dict(topped_bank=kb, feeding_stage=kf, window_ps=list(win),
               free_deck=free_row["deck"], topped_deck=top_row["deck"],
               dest=top_row["cfg"]["dest"], sizing=top_row["cfg"]["sizing"],
               m=top_row["cfg"]["m"])
    sf, st = free_row["stages"][kf - 1], top_row["stages"][kf - 1]
    out["max_LOW_free_V"], out["max_LOW_topped_V"] = sf["max_LOW_V"], st["max_LOW_V"]
    out["low_lift_at_feeder_bound_mV"] = (st["max_LOW_V"] - sf["max_LOW_V"]) * 1e3
    out["feeder_bound_ps"] = sf["bound_ps"]
    out["feeder_bound_precedes_fire"] = sf["bound_ps"] < win[0] + 5.0
    # the TOPPED bank's own settled LOW lift (measured AFTER the fire, so it is
    # not structurally zero the way the feeder's boundary is)
    stb_f, stb_t = free_row["stages"][kb - 1], top_row["stages"][kb - 1]
    if stb_f["max_LOW_V"] is not None and stb_t["max_LOW_V"] is not None:
        out["self_lift_topped_bank_mV"] = (stb_t["max_LOW_V"] - stb_f["max_LOW_V"]) * 1e3
    out["rail_topped_free_V"] = stb_f["rail_at_bound_V"]
    out["rail_topped_topped_V"] = stb_t["rail_at_bound_V"]
    pf = os.path.join(sk.HERE, free_row["deck"] + ".prn")
    pt = os.path.join(sk.HERE, top_row["deck"] + ".prn")
    hf, rf = sk.read_prn(pf)
    ht, rt = sk.read_prn(pt)
    ta, tb = win
    inj = ("V(NTK%d)" % kb) if top_row["cfg"]["dest"] == "tank" else ("V(RAIL%d)" % kb)
    for nm, cn in (("inject", inj), ("rail_topped", "V(RAIL%d)" % kb),
                   ("rail_feeder", "V(RAIL%d)" % kf)):
        if cn in ht:
            s, t = sk.max_slope(ht, rt, cn, ta, tb)
            out["slope_%s_V_per_ns" % nm], out["slope_%s_at_ps" % nm] = s, t
        if cn in hf:
            s, _ = sk.max_slope(hf, rf, cn, ta, tb)
            out["slope_%s_FREE_V_per_ns" % nm] = s
    worst, worstg, wsl, wslg, wlift = 0.0, None, 0.0, None, 0.0
    per = {}
    for i in range(prof[kf - 1]):
        if not sk.true_input_hi(kf, i, prof):
            continue                      # pull-UP cells are not the LOW-lift victims
        cn = "V(O%d_%d)" % (kf, i)
        if cn not in hf or cn not in ht:
            continue
        a, b = col(hf, rf, cn), col(ht, rt, cn)
        grid = [t for t, _ in b if ta <= t <= tb]
        d = max((abs(interp(b, t) - interp(a, t)) for t in grid), default=0.0)
        lift = interp(b, tb) - interp(a, tb)
        sl, _ = sk.max_slope(ht, rt, cn, ta, tb)
        slf, _ = sk.max_slope(hf, rf, cn, ta, tb)
        per["o%d_%d" % (kf, i)] = dict(step_mV=d * 1e3, lift_end_mV=lift * 1e3,
                                       slope_V_per_ns=sl, slope_free_V_per_ns=slf)
        if d > worst:
            worst, worstg = d, "o%d_%d" % (kf, i)
        if sl > wsl:
            wsl, wslg = sl, "o%d_%d" % (kf, i)
        if abs(lift) > abs(wlift):
            wlift = lift
    out["step_at_logic_mV"] = worst * 1e3
    out["step_at_logic_gate"] = worstg
    out["lift_at_logic_end_mV"] = wlift * 1e3
    out["slope_logic_V_per_ns"] = wsl
    out["slope_logic_gate"] = wslg
    out["per_gate"] = per
    return out


def main(src, dst):
    rows = json.load(open(os.path.join(sk.HERE, src)))
    idx = {}
    for r in rows:
        if "error" in r:
            continue
        c = r["cfg"]
        idx[(c["dest"], c["sizing"], c["m"], c["form"])] = r
    out = []
    for (dest, sizing, m, form), r in sorted(idx.items(), key=lambda x: str(x[0])):
        if form == "free":
            continue
        f = idx.get((dest, sizing, m, "free"))
        if f is None:
            continue
        T = r["T_ps"]
        for kb in (3, 4):
            hop = [t for _, t in sk.HOPS].index(kb)
            t_open = sk.T1 + hop * T + r["tz_ps"][hop]
            t_fire = t_open + 6 * sk.EDGE
            win = (t_fire - 5.0, t_fire + sk.TOPUP_W + 20.0)
            p = pair(f, r, kb, win)
            p["cfg"] = r["cfg"]
            out.append(p)
    json.dump(out, open(os.path.join(sk.HERE, dst), "w"), indent=1)
    for p in out:
        c = p["cfg"]
        print("%-7s %-8s m=%-3g bank%d  step@logic %8.3f mV  lift@end %+8.3f mV  "
              "selflift %+9.3f mV  slope inj %7.1f / rail %7.1f / logic %7.2f V/ns"
              % (c["dest"], c["sizing"], c["m"], p["topped_bank"],
                 p["step_at_logic_mV"], p["lift_at_logic_end_mV"],
                 p.get("self_lift_topped_bank_mV", float("nan")),
                 p.get("slope_inject_V_per_ns", float("nan")),
                 p.get("slope_rail_topped_V_per_ns", float("nan")),
                 p.get("slope_logic_V_per_ns", float("nan"))))
    print("wrote " + dst)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "ROWS_SKEPT.json",
         sys.argv[2] if len(sys.argv) > 2 else "COUPLING_SKEPT.json")
