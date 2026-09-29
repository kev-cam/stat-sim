#!/usr/bin/env python3
"""MEASUREMENT 1 -- THE COUPLING, at a LOGIC node, not at the injection point.

For each configuration this pairs the TOPPED row with its own FREE control (same
tank sizing, same m, same T, same zeros, and -- unlike the committed convention
-- the same top-up devices PHYSICALLY PRESENT, parked off).  That makes the
difference attributable to the top-up FIRING rather than to the top-up EXISTING.

Reported per configuration:
  low_lift_mV       max over the feeding stage's pull-DOWN gates of V(o) at that
                    stage's own boundary, TOPPED MINUS FREE.  The headline.
  step_at_logic_mV  the largest instantaneous divergence |V_topped(t)-V_free(t)|
                    on any of the feeding stage's outputs over the top-up window,
                    on a common interpolated time grid.  This is the step the
                    logic node actually sees, as opposed to the settled offset.
  slope_*           max |dV/dt| in V/ns at the injection node, at the bank rail,
                    and at the worst logic node.
"""
import json, os, sys
import tf

FEEDER = {3: 2, 4: 3}     # topped bank -> the stage that feeds it


def interp(series, t):
    """linear interpolation of a (t, v) list at t."""
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


def pair(free_row, top_row, topped_bank=3, win=None):
    """win = (ta, tb) the top-up window on the absolute timeline."""
    prof = tf.PROFILE
    kf = FEEDER[topped_bank]
    out = dict(topped_bank=topped_bank, feeding_stage=kf,
               free_deck=free_row.get("deck"), topped_deck=top_row.get("deck"))
    sf = free_row["stages"][kf - 1]
    st = top_row["stages"][kf - 1]
    out["max_LOW_free_V"] = sf["max_LOW_V"]
    out["max_LOW_topped_V"] = st["max_LOW_V"]
    if sf["max_LOW_V"] is not None and st["max_LOW_V"] is not None:
        out["low_lift_mV"] = (st["max_LOW_V"] - sf["max_LOW_V"]) * 1e3
    out["rail_feeder_free_V"] = sf["rail_at_bound_V"]
    out["rail_feeder_topped_V"] = st["rail_at_bound_V"]
    out["rail_topped_bank_free_V"] = free_row["stages"][topped_bank - 1]["rail_at_bound_V"]
    out["rail_topped_bank_topped_V"] = top_row["stages"][topped_bank - 1]["rail_at_bound_V"]
    # --- time-domain: the step actually seen at a LOGIC node
    pf = os.path.join(tf.HERE, free_row["deck"] + ".prn")
    pt = os.path.join(tf.HERE, top_row["deck"] + ".prn")
    if not (os.path.exists(pf) and os.path.exists(pt)):
        return out
    hf, rf = tf.read_prn(pf)
    ht, rt = tf.read_prn(pt)
    ta, tb = win if win else (0.0, 1e9)
    dest_tank = (top_row["cfg"]["dest"] == "tank")
    inj = ("V(NTK%d)" % topped_bank) if dest_tank else ("V(RAIL%d)" % topped_bank)
    for nm, cname in (("inject", inj), ("rail_topped", "V(RAIL%d)" % topped_bank),
                      ("rail_feeder", "V(RAIL%d)" % kf)):
        if cname in ht:
            s, t = tf.max_slope(ht, rt, cname, ta, tb)
            out["slope_%s_V_per_ns" % nm] = s
            out["slope_%s_at_ps" % nm] = t
        if cname in hf:
            s, _ = tf.max_slope(hf, rf, cname, ta, tb)
            out["slope_%s_FREE_V_per_ns" % nm] = s
    # every pull-DOWN output of the feeding stage
    worst, worstg, worst_sl, worst_slg = 0.0, None, 0.0, None
    per = {}
    for i in range(prof[kf - 1]):
        if not tf.is_hi(kf, i):
            continue
        cn = "V(O%d_%d)" % (kf, i)
        if cn not in hf or cn not in ht:
            continue
        a = col(hf, rf, cn)
        b = col(ht, rt, cn)
        grid = [t for t, _ in b if ta <= t <= tb]
        d = max((abs(interp(b, t) - interp(a, t)) for t in grid), default=0.0)
        sl, _ = tf.max_slope(ht, rt, cn, ta, tb)
        slf, _ = tf.max_slope(hf, rf, cn, ta, tb)
        per["o%d_%d" % (kf, i)] = dict(step_mV=d * 1e3, slope_V_per_ns=sl,
                                       slope_free_V_per_ns=slf)
        if d > worst:
            worst, worstg = d, "o%d_%d" % (kf, i)
        if sl > worst_sl:
            worst_sl, worst_slg = sl, "o%d_%d" % (kf, i)
    out["step_at_logic_mV"] = worst * 1e3
    out["step_at_logic_gate"] = worstg
    out["slope_logic_V_per_ns"] = worst_sl
    out["slope_logic_gate"] = worst_slg
    out["per_gate"] = per
    return out


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "ROWS_matrix.json"
    rows = json.load(open(os.path.join(tf.HERE, src)))
    idx = {}
    for r in rows:
        if "error" in r:
            continue
        c = r["cfg"]
        idx[(c["dest"], c["sizing"], c["m"], c["form"], c["dv"])] = r
    out = []
    for (dest, sizing, m, form, dv), r in sorted(idx.items()):
        if form == "free":
            continue
        f = idx.get((dest, sizing, m, "free", dv))
        if f is None:
            continue
        T = r["T_ps"]
        for kb in (3, 4):
            hop = [t for _, t in tf.HOPS].index(kb)
            t_open = tf.T1 + hop * T + r["tz_ps"][hop]
            t_fire = t_open + 6 * tf.EDGE
            if form == "clamp":
                win = (t_fire - 5.0, t_fire + tf.TOPUP_W + 20.0)
            else:
                a = t_fire + tf.SLEW + 4 * tf.EDGE
                win = (t_fire - 5.0, a + r["cfg"].get("ton", 24.0) + 200.0)
            p = pair(f, r, kb, win)
            p["cfg"] = r["cfg"]
            p["window_ps"] = win
            out.append(p)
    json.dump(out, open(os.path.join(tf.HERE, "COUPLING.json"), "w"), indent=1)
    for p in out:
        c = p["cfg"]
        print("%-6s %-8s m=%-3g %-6s dV=%-5g bank%d  low_lift %+8.3f mV   "
              "step@logic %8.3f mV   slope inj %8.1f / rail %8.1f / logic %8.1f V/ns"
              % (c["dest"], c["sizing"], c["m"], c["form"], c["dv"],
                 p["topped_bank"], p.get("low_lift_mV", float("nan")),
                 p.get("step_at_logic_mV", float("nan")),
                 p.get("slope_inject_V_per_ns", float("nan")),
                 p.get("slope_rail_topped_V_per_ns", float("nan")),
                 p.get("slope_logic_V_per_ns", float("nan"))))
    print("wrote COUPLING.json")


if __name__ == "__main__":
    main()
